from __future__ import annotations

import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from threading import Barrier

import pytest
from sqlalchemy import create_engine, event, func, select

from l1_data_processing.durable import process_content
from l1_data_processing.input import StubContentProvider
from l1_data_processing.llm import FakeLLM
from l1_data_processing.sql_schema import (
    content_base_analysis, enrichment_cache, outbox_events, processing_runs,
)
from l1_data_processing.sql_store import (
    ConcurrentProcessingError, RequestConflictError, SqlAlchemyEnrichmentStore,
)
from l1_data_processing.state import GraphState


class FixedProvider:
    def __init__(self, *, suffix="", metadata=None):
        self.content = StubContentProvider().get("demo-article")
        self.content = replace(self.content, body=self.content.body + suffix,
                               metadata=metadata if metadata is not None else self.content.metadata)
        self.calls = 0

    def get(self, content_id):
        self.calls += 1
        return replace(self.content, content_id=content_id)


@pytest.fixture()
def store(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'l1.db'}")
    result = SqlAlchemyEnrichmentStore(engine)
    result.create_schema()
    yield result
    engine.dispose()


def process(store, *, content_id="42", provider=None, llm=None, **kwargs):
    return process_content(content_id, store=store, provider=provider or FixedProvider(),
                           llm=llm or FakeLLM(), **kwargs)


def counts(store):
    with store.engine.connect() as connection:
        return [connection.scalar(select(func.count()).select_from(table)) for table in
                (content_base_analysis, processing_runs, enrichment_cache, outbox_events)]


def test_success_commits_snapshot_analysis_cost_cache_and_versioned_outbox(store):
    provider = FixedProvider()
    result = process(store, provider=provider)
    row = store.get("42")
    run = store.runs("42")[0]
    events = store.pending_events()

    assert result.status == "WAIT_SCORE" and not result.replayed and not result.cache_hit
    assert counts(store) == [1, 1, 1, 1]
    assert row["schema_version"] == 1 and row["revision"] == 1
    assert row["input_snapshot"] == GraphState("42", content=provider.get("42")).to_dict()["content"]
    assert row["analysis"] == result.analysis and row["analysis"]["content_id"] == "42"
    assert run["prompt_tokens"] > 0 and run["completion_tokens"] > 0
    assert run["cost_units"] == run["prompt_tokens"] + run["completion_tokens"]
    assert run["llm_calls"] > 0 and run["cost_complete"] == 1
    assert events[0].event_id == f"content.analyzed:{result.run_id}"
    assert events[0].payload["analysis"] == row["analysis"]
    assert events[0].payload["run_id"] == row["run_id"] == run["run_id"]


def test_success_replays_across_store_instances_without_new_call_or_cost(store):
    first = process(store)
    old_cost = store.runs()[0]["cost_units"]
    store.engine.dispose()
    engine = create_engine(str(store.engine.url))
    try:
        restored = SqlAlchemyEnrichmentStore(engine)
        llm = FakeLLM()
        second = process(restored, llm=llm)
        assert second.replayed and second.run_id == first.run_id
        assert not llm.calls and counts(restored) == [1, 1, 1, 1]
        assert restored.runs()[0]["cost_units"] == old_cost
    finally:
        engine.dispose()


def test_success_replays_in_a_fresh_python_process(store):
    original = process_content("demo-article", store=store,
                               provider=StubContentProvider(), llm=FakeLLM())
    script = """
import json, sys
from sqlalchemy import create_engine
from l1_data_processing.sql_store import SqlAlchemyEnrichmentStore
from l1_data_processing.durable import process_content
from l1_data_processing.input import StubContentProvider
from l1_data_processing.llm import FakeLLM
engine = create_engine(sys.argv[1])
store = SqlAlchemyEnrichmentStore(engine)
llm = FakeLLM()
result = process_content('demo-article',store=store,provider=StubContentProvider(),llm=llm)
print(json.dumps({'run_id':result.run_id,'status':result.status,'replayed':result.replayed,'calls':dict(llm.calls)}))
engine.dispose()
"""
    completed = subprocess.run([sys.executable, "-c", script, str(store.engine.url)],
                               capture_output=True, text=True, check=True, timeout=20)
    payload = json.loads(completed.stdout)
    assert payload == {"run_id": original.run_id, "status": "WAIT_SCORE", "replayed": True, "calls": {}}
    assert counts(store) == [1, 1, 1, 1]


def test_shared_text_cache_keeps_identity_and_has_zero_new_cost(store):
    first = process(store, content_id="42")
    llm = FakeLLM()
    second = process(store, content_id="43", llm=llm)
    assert second.cache_hit and not second.replayed and not llm.calls
    assert first.analysis["content_id"] == "42" and second.analysis["content_id"] == "43"
    assert store.get("43")["input_snapshot"]["content_id"] == "43"
    run = store.runs("43")[0]
    assert run["cost_units"] == run["llm_calls"] == 0 and run["traces"] == []
    assert counts(store) == [2, 2, 1, 2]


def test_snapshot_graph_and_explicit_request_versions_have_distinct_notifications(store):
    results = [process(store)]
    assert process(store).replayed
    # Metadata changes require a fresh L2 snapshot, but reuse text analysis.
    changed_metadata = FixedProvider(metadata={"source": {"name": "new source"}})
    llm = FakeLLM()
    results.append(process(store, provider=changed_metadata, llm=llm))
    assert results[-1].cache_hit and not llm.calls
    changed_text = FixedProvider(suffix=" A newly updated body.")
    results.append(process(store, provider=changed_text))
    results.append(process(store, provider=changed_text, graph_version="graph.v2"))
    results.append(process(store, provider=changed_text, graph_version="graph.v2", reprocess_key="request-1"))
    replay_llm = FakeLLM()
    replay = process(store, provider=changed_text, graph_version="graph.v2",
                     reprocess_key="request-1", llm=replay_llm)
    assert replay.replayed and not replay_llm.calls and replay.run_id == results[-1].run_id
    results.append(process(store, provider=changed_text, graph_version="graph.v2", reprocess_key="request-2"))
    assert all(result.status == "WAIT_SCORE" for result in results)
    assert len({result.run_id for result in results}) == 6
    assert len(store.runs()) == len(store.pending_events()) == 6
    assert store.runs()[-1]["llm_calls"] > 0
    with pytest.raises(RequestConflictError):
        process(store, provider=changed_text, graph_version="graph.v3", reprocess_key="request-1")
    with pytest.raises(RequestConflictError):
        process(store, graph_version="graph.v2", reprocess_key="request-1")
    assert len(store.runs()) == 6


def test_failed_schema_attempt_is_recorded_and_retry_succeeds(store):
    invalid = FakeLLM(preset_responses={"BaseAnalysis": {"summary": "invalid"}})
    first = process(store, llm=invalid)
    assert first.status == "FAILED" and first.analysis is None
    assert store.get("42")["status"] == "FAILED"
    assert counts(store) == [1, 1, 0, 0]
    failed = store.runs()[0]
    assert failed["cost_units"] > 0 and failed["cost_complete"] == 1
    second = process(store)
    assert second.status == "WAIT_SCORE" and not second.replayed
    assert first.run_id != second.run_id
    attempts = store.runs()
    assert [run["attempt"] for run in attempts] == [1, 2]
    assert attempts[0]["request_id"] == attempts[1]["request_id"]
    assert counts(store) == [1, 2, 1, 1]


def test_failed_external_call_keeps_known_usage_and_marks_billing_incomplete(store):
    class BrokenEmbedding(FakeLLM):
        def embed(self, text, *, model):
            raise OSError("embedding temporarily unavailable")

    failed = process(store, llm=BrokenEmbedding())
    assert failed.status == "FAILED" and "temporarily unavailable" in failed.error
    run = store.runs()[0]
    assert run["cost_units"] > 0 and run["llm_calls"] > len(run["traces"])
    assert run["cost_complete"] == 0 and not store.pending_events()
    assert process(store).status == "WAIT_SCORE"


def test_cancelled_request_is_terminal_until_an_explicit_new_request(store):
    ignore = FakeLLM(preset_responses={"ContentFilter": {"ignore": True, "reason": "low value"}})
    first = process(store, llm=ignore)
    llm = FakeLLM()
    second = process(store, llm=llm)
    assert first.status == second.status == "CANCELLED" and second.replayed and not llm.calls
    assert counts(store) == [1, 1, 0, 0]
    assert process(store, reprocess_key="review-again").status == "WAIT_SCORE"
    assert len(store.pending_events()) == 1


@pytest.mark.parametrize("existing_head", [False, True])
@pytest.mark.parametrize("failure_stage", ["outbox", "commit"])
def test_transaction_failure_rolls_back_every_mutation(store, existing_head, failure_stage):
    if existing_head:
        process(store)
    before = counts(store)
    old_head = store.get("42")

    def fail_statement(connection, cursor, statement, parameters, context, executemany):
        if statement.lower().startswith("insert into l1_outbox_events"):
            raise RuntimeError("forced transaction failure")

    def fail_commit(connection):
        raise RuntimeError("forced transaction failure")

    hook = "before_cursor_execute" if failure_stage == "outbox" else "commit"
    callback = fail_statement if failure_stage == "outbox" else fail_commit
    event.listen(store.engine, hook, callback)
    try:
        with pytest.raises(RuntimeError, match="forced transaction failure"):
            process(store, reprocess_key="rollback-check")
    finally:
        event.remove(store.engine, hook, callback)
    assert counts(store) == before and store.get("42") == old_head
    assert process(store, reprocess_key="rollback-check").status == "WAIT_SCORE"


def test_concurrent_duplicate_has_one_committed_run_and_notification(store):
    barrier = Barrier(2)

    class OverlappingLLM(FakeLLM):
        def structured(self, prompt, *, schema_name, model):
            if schema_name == "ContentFilter":
                barrier.wait(timeout=10)
            return super().structured(prompt, schema_name=schema_name, model=model)

    def work():
        engine = create_engine(str(store.engine.url))
        try:
            return process(SqlAlchemyEnrichmentStore(engine), llm=OverlappingLLM())
        finally:
            engine.dispose()

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(work) for _ in range(2)]
        results = [future.result(timeout=20) for future in futures]
    assert {result.run_id for result in results} == {store.get("42")["run_id"]}
    assert sorted(result.replayed for result in results) == [False, True]
    assert counts(store) == [1, 1, 1, 1]


def test_stale_worker_cannot_overwrite_a_newer_committed_revision(store):
    process(store)
    newer = []

    class DelayedLLM(FakeLLM):
        def structured(self, prompt, *, schema_name, model):
            if schema_name == "ContentFilter":
                newer.append(process(store, provider=FixedProvider(suffix=" newest"), graph_version="v3"))
            return super().structured(prompt, schema_name=schema_name, model=model)

    with pytest.raises(ConcurrentProcessingError):
        process(store, provider=FixedProvider(suffix=" older"), graph_version="v2", llm=DelayedLLM())
    assert store.get("42")["run_id"] == newer[0].run_id
    assert store.get("42")["graph_version"] == "v3"
    assert counts(store) == [1, 2, 2, 2]


def test_concurrent_manual_key_reuse_for_different_input_is_rejected(store):
    class DelayedLLM(FakeLLM):
        def structured(self, prompt, *, schema_name, model):
            if schema_name == "ContentFilter":
                process(store, provider=FixedProvider(suffix=" winning input"), reprocess_key="job-1")
            return super().structured(prompt, schema_name=schema_name, model=model)

    with pytest.raises(RequestConflictError):
        process(store, llm=DelayedLLM(), reprocess_key="job-1")
    assert "winning input" in store.get("42")["input_snapshot"]["body"]
    assert counts(store) == [1, 1, 1, 1]


def test_input_snapshot_is_frozen_before_model_work(store):
    provider = FixedProvider()
    original_body = provider.content.body

    class MutatingLLM(FakeLLM):
        def structured(self, prompt, *, schema_name, model):
            provider.content = replace(provider.content, body="replacement during model work")
            return super().structured(prompt, schema_name=schema_name, model=model)

    assert process(store, provider=provider, llm=MutatingLLM()).status == "WAIT_SCORE"
    assert provider.calls == 1
    assert store.get("42")["input_snapshot"]["body"] == original_body


def test_lookup_failure_leaves_no_accepted_request(store):
    class MissingProvider:
        def get(self, content_id):
            raise KeyError(content_id)

    with pytest.raises(KeyError):
        process(store, provider=MissingProvider())
    assert counts(store) == [0, 0, 0, 0]
    assert process(store).status == "WAIT_SCORE"


def test_outbox_failure_and_replay_keep_stable_event_identity(store):
    process(store)
    accepted = set()

    def crash_after_accept(topic, payload, key):
        accepted.add(key)
        raise RuntimeError("receiver accepted, response lost")

    with pytest.raises(RuntimeError, match="response lost"):
        store.relay_once(crash_after_accept)
    assert len(store.pending_events()) == 1
    assert store.relay_once(lambda topic, payload, key: accepted.add(key)) == 1
    assert len(accepted) == 1 and not store.pending_events()
    assert store.relay_once(lambda *args: pytest.fail("already relayed")) == 0


def test_nonfinite_model_output_is_failed_without_notification(store):
    class InvalidEmbedding(FakeLLM):
        def embed(self, text, *, model):
            return [float("nan")]

    assert process(store, llm=InvalidEmbedding()).status == "FAILED"
    assert store.get("42")["analysis"] is None and not store.pending_events()


@pytest.mark.parametrize("change_graph", [False, True], ids=["input", "graph"])
def test_returning_to_historical_version_creates_new_current_and_notification(store, change_graph):
    first = process(store)
    middle = process(store, graph_version="v2") if change_graph else process(
        store, provider=FixedProvider(suffix=" version B"),
    )
    llm = FakeLLM()
    returned = process(store, llm=llm)
    assert returned.status == "WAIT_SCORE" and returned.cache_hit and not returned.replayed
    assert not llm.calls
    assert len({first.run_id, middle.run_id, returned.run_id}) == 3
    assert store.get("42")["run_id"] == returned.run_id
    assert store.get("42")["analysis"] == returned.analysis
    assert store.get_run(returned.run_id)["attempt"] == 2
    assert len(store.pending_events()) == 3


def test_automatic_replay_uses_latest_manual_analysis_for_same_input(store):
    process(store)
    changed_output = FakeLLM(preset_responses={"BaseAnalysis": {
        "one_liner": "Manually refreshed", "summary": "New refreshed summary",
        "key_points": ["refreshed"], "entities": ["CodePick"], "base_tags": ["updated"],
    }})
    manual = process(store, reprocess_key="refresh-1", llm=changed_output)
    llm = FakeLLM()
    automatic = process(store, llm=llm)
    assert automatic.replayed and automatic.run_id == manual.run_id and not llm.calls
    assert automatic.analysis["summary"] == "New refreshed summary"
    assert store.get("42")["analysis"] == automatic.analysis
    assert len(store.runs()) == len(store.pending_events()) == 2


def test_old_successful_attempt_does_not_swallow_a_new_activation_conflict(store, monkeypatch):
    first = process(store)
    process(store, provider=FixedProvider(suffix=" version B"))
    original_commit = store.commit_run
    winning = []

    def overlap_commit(run, *, expected_revision):
        if run["request_id"] == store.get_run(first.run_id)["request_id"]:
            winning.append(process(store, provider=FixedProvider(suffix=" version C")))
        return original_commit(run, expected_revision=expected_revision)

    monkeypatch.setattr(store, "commit_run", overlap_commit)
    with pytest.raises(ConcurrentProcessingError):
        process(store)
    assert store.get("42")["run_id"] == winning[0].run_id
    assert len(store.runs()) == len(store.pending_events()) == 3
