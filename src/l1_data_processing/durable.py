"""Durable processing entrypoint; the standalone graph stays independently usable."""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
from time import perf_counter
from typing import Any

from l1_data_processing.cache import EnrichmentCacheEntry, InMemoryEnrichmentCache, content_hash
from l1_data_processing.config import GraphConfig
from l1_data_processing.contracts import BaseAnalysis, ContentInput, UsageTrace
from l1_data_processing.graph import enrich
from l1_data_processing.input.provider import ContentProvider
from l1_data_processing.llm.client import LLMClient, LLMResponse
from l1_data_processing.llm.router import ModelRouter
from l1_data_processing.sql_store import RequestConflictError, SqlAlchemyEnrichmentStore
from l1_data_processing.state import GRAPH_VERSION, GraphState
from l1_data_processing.text import clean_normalize_text


@dataclass(frozen=True)
class ProcessingResult:
    run_id: str
    content_id: str
    status: str
    analysis: dict[str, Any] | None
    replayed: bool
    cache_hit: bool
    error: str | None


def _result(run: dict[str, Any], *, replayed: bool) -> ProcessingResult:
    return ProcessingResult(
        run_id=run["run_id"], content_id=run["content_id"], status=run["status"],
        analysis=run["analysis"], replayed=replayed, cache_hit=bool(run["cache_hit"]),
        error=run["error"],
    )


def _json_hash(value: object) -> str:
    serialized = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _required_text(value: str, name: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > 255:
        raise ValueError(f"{name} must be a non-empty string of at most 255 characters")
    return value.strip()


def _analysis_from_dict(payload: dict[str, Any]) -> BaseAnalysis:
    values = deepcopy(payload)
    values["created_at"] = datetime.fromisoformat(values["created_at"])
    values["traces"] = [UsageTrace(**trace) for trace in values["traces"]]
    analysis = BaseAnalysis(**values)
    analysis.validate()
    return analysis


class _SnapshotProvider:
    def __init__(self, content: ContentInput) -> None:
        self.content = content

    def get(self, content_id: str) -> ContentInput:
        if content_id != self.content.content_id:
            raise ValueError("input snapshot content identity changed")
        return deepcopy(self.content)


class _TrackedLLM:
    """Retain known usage even when the graph raises before returning state.

    A failed remote call has unknown billing: cost_complete is false, rather
    than asserting the recorded successful-response usage is its full cost.
    """
    def __init__(self, client: LLMClient) -> None:
        self.client = client
        self.calls = 0
        self.cost_complete = True
        self.traces: list[UsageTrace] = []

    def structured(self, prompt: str, *, schema_name: str, model: str) -> LLMResponse:
        started = perf_counter()
        self.calls += 1
        try:
            response = self.client.structured(prompt, schema_name=schema_name, model=model)
        except Exception:
            self.cost_complete = False
            raise
        self.traces.append(UsageTrace(schema_name, model, response.prompt_tokens,
                                      response.completion_tokens, int((perf_counter() - started) * 1000)))
        return response

    def complete(self, prompt: str, *, model: str) -> LLMResponse:
        started = perf_counter()
        self.calls += 1
        try:
            response = self.client.complete(prompt, model=model)
        except Exception:
            self.cost_complete = False
            raise
        self.traces.append(UsageTrace("complete", model, response.prompt_tokens,
                                      response.completion_tokens, int((perf_counter() - started) * 1000)))
        return response

    def embed(self, text: str, *, model: str) -> list[float]:
        started = perf_counter()
        self.calls += 1
        try:
            embedding = self.client.embed(text, model=model)
        except Exception:
            self.cost_complete = False
            raise
        self.traces.append(UsageTrace("embedding", model, len(text.split()), 0,
                                      int((perf_counter() - started) * 1000)))
        return embedding


def process_content(
    content_id: str, *, store: SqlAlchemyEnrichmentStore, provider: ContentProvider,
    llm: LLMClient, graph_version: str = GRAPH_VERSION, reprocess_key: str | None = None,
    config: GraphConfig | None = None, router: ModelRouter | None = None,
) -> ProcessingResult:
    """Process one frozen input and atomically publish its durable outcome.

    Without a reprocess key, content snapshot + graph version define a request.
    A provided key explicitly bypasses cache but retries that key reuse success.
    Reusing an explicit key for a different snapshot/version is an error.
    Input lookup failures and transaction failures propagate with no acceptance
    marker. Model/graph failures are recorded as FAILED and may be retried.
    """
    content_id = _required_text(content_id, "content_id")
    graph_version = _required_text(graph_version, "graph_version")
    if reprocess_key is not None:
        reprocess_key = _required_text(reprocess_key, "reprocess_key")
    started_at = datetime.now(UTC)
    # Capture the head revision before input/model work, rejecting a stale result
    # if another worker commits while this request is reading or computing.
    head = store.get(content_id)
    expected_revision = head["revision"] if head is not None else None
    content = deepcopy(provider.get(content_id))
    if content.content_id != content_id:
        raise ValueError("provider returned a different content_id")
    snapshot = GraphState(content_id=content_id, content=content).to_dict()["content"]
    input_hash = _json_hash(snapshot)
    cleaned, _ = clean_normalize_text(content.normalized_text())
    digest = content_hash(cleaned)
    request_id = _json_hash([
        content_id, "manual" if reprocess_key is not None else "automatic",
        reprocess_key if reprocess_key is not None else [input_hash, graph_version],
    ])
    previous = store.latest_run(request_id)
    if reprocess_key is None and head is not None:
        if (
            head["status"] in {"WAIT_SCORE", "CANCELLED"}
            and head["graph_version"] == graph_version
            and _json_hash(head["input_snapshot"]) == input_hash
        ):
            current_run = store.get_run(head["run_id"])
            if current_run is None:
                raise RuntimeError("current analysis points at a missing processing run")
            return _result(current_run, replayed=True)
    if previous is not None:
        if previous["input_hash"] != input_hash or previous["graph_version"] != graph_version:
            raise RequestConflictError("reprocess_key already belongs to a different snapshot/version")
        if reprocess_key is not None and previous["status"] in {"WAIT_SCORE", "CANCELLED"}:
            return _result(previous, replayed=True)
    attempt = previous["attempt"] + 1 if previous is not None else 1
    run_id = _json_hash([request_id, attempt])
    cache = InMemoryEnrichmentCache()
    cached = None if reprocess_key is not None else store.cached_analysis(digest, graph_version)
    if cached is not None:
        cache.set(EnrichmentCacheEntry(digest, graph_version, _analysis_from_dict(cached)))
    tracked = _TrackedLLM(llm)
    try:
        state = enrich(
            content_id, provider=_SnapshotProvider(content), llm=tracked, config=config,
            router=router, cache=cache, graph_version=graph_version,
            reprocess=reprocess_key is not None,
        )
        analysis = state.analysis.to_dict() if state.analysis is not None else None
        if analysis is not None:
            # Reject NaN/Infinity and invalid JSON before any database mutations.
            _json_hash(analysis)
        status = state.content_status
        if status not in {"WAIT_SCORE", "CANCELLED", "FAILED"}:
            raise ValueError(f"graph returned an unsupported terminal status: {status}")
        if status == "WAIT_SCORE" and analysis is None:
            raise ValueError("WAIT_SCORE requires analysis")
        error = state.error or state.cancel_reason
        cache_hit = bool(state.intermediate.get("cache", {}).get("hit"))
    except Exception as exc:
        status, analysis, cache_hit = "FAILED", None, False
        error = f"{type(exc).__name__}: {exc}"
    prompt_tokens = sum(trace.prompt_tokens for trace in tracked.traces)
    completion_tokens = sum(trace.completion_tokens for trace in tracked.traces)
    run = {
        "run_id": run_id, "request_id": request_id, "attempt": attempt,
        "content_id": content_id, "graph_version": graph_version,
        "content_hash": digest, "input_hash": input_hash,
        "input_snapshot": snapshot, "reprocess_key": reprocess_key,
        "status": status, "analysis": analysis, "cache_hit": int(cache_hit),
        "prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens,
        "cost_units": prompt_tokens + completion_tokens, "llm_calls": tracked.calls,
        "cost_complete": int(tracked.cost_complete),
        "traces": [trace.to_dict() for trace in tracked.traces], "error": error,
        "started_at": started_at, "finished_at": datetime.now(UTC),
    }
    committed = store.commit_run(run, expected_revision=expected_revision)
    return _result(committed, replayed=committed is not run)
