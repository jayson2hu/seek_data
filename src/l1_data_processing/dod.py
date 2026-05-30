from __future__ import annotations

from l1_data_processing.cache import InMemoryEnrichmentCache
from l1_data_processing.config import GraphConfig
from l1_data_processing.costing import InMemoryCostLedger
from l1_data_processing.events import InMemoryOutbox
from l1_data_processing.graph import enrich
from l1_data_processing.input import StubContentProvider
from l1_data_processing.llm import FakeLLM
from l1_data_processing.persistence import InMemoryContentBaseAnalysisRepository
from l1_data_processing.status import CANCELLED, WAIT_SCORE, ContentStatusMachine


def run_dod_checks() -> list[str]:
    checks: list[str] = []
    provider = StubContentProvider()
    repository = InMemoryContentBaseAnalysisRepository()
    outbox = InMemoryOutbox()
    status_machine = ContentStatusMachine()
    cost_ledger = InMemoryCostLedger()
    cache = InMemoryEnrichmentCache()

    state = enrich(
        "demo-article",
        provider=provider,
        llm=FakeLLM(),
        repository=repository,
        outbox=outbox,
        status_machine=status_machine,
        cost_ledger=cost_ledger,
        cache=cache,
    )
    assert state.status == "COMPLETED"
    assert state.analysis is not None
    assert state.content_status == WAIT_SCORE
    assert repository.count() == 1
    assert outbox.count() == 1
    assert cost_ledger.get("demo-article") is not None
    checks.append("standalone pipeline")

    cached_llm = FakeLLM()
    cached = enrich("demo-article", provider=provider, llm=cached_llm, cache=cache)
    assert cached.status == "COMPLETED"
    assert cached.intermediate["cache"]["hit"] is True
    assert cached_llm.calls["structured"] == 0
    assert cached_llm.calls["embed"] == 0
    checks.append("cache hit")

    reprocess_llm = FakeLLM()
    reprocessed = enrich("demo-article", provider=provider, llm=reprocess_llm, cache=cache, reprocess=True)
    assert reprocessed.intermediate["cache"]["bypassed"] is True
    assert reprocess_llm.calls["structured"] > 0
    checks.append("reprocess")

    cancelled_machine = ContentStatusMachine()
    cancelled = enrich(
        "demo-article",
        provider=provider,
        llm=FakeLLM({"ContentFilter": {"ignore": True, "reason": "low quality", "value": "low"}}),
        status_machine=cancelled_machine,
    )
    assert cancelled.status == "CANCELLED"
    assert cancelled.content_status == CANCELLED
    assert cancelled.analysis is None
    checks.append("filter cancel")

    long_state = enrich(
        "demo-article",
        provider=provider,
        llm=FakeLLM(),
        config=GraphConfig(split_threshold_chars=10, chunk_size_chars=70, chunk_overlap_chars=0),
    )
    assert long_state.route == "split"
    assert long_state.analysis is not None
    assert long_state.analysis.key_points
    checks.append("long content")

    return checks


def main() -> None:
    checks = run_dod_checks()
    print(f"L1 DOD: PASS checks={','.join(checks)}")


if __name__ == "__main__":
    main()
