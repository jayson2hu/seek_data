from __future__ import annotations

from time import perf_counter

from l1_data_processing.config import GraphConfig
from l1_data_processing.contracts import BaseAnalysis, UsageTrace
from l1_data_processing.input.provider import ContentProvider
from l1_data_processing.llm.client import LLMClient
from l1_data_processing.llm.router import ModelRouter
from l1_data_processing.state import GraphState
from l1_data_processing.text import clean_normalize_text


def load_content_node(state: GraphState, *, provider: ContentProvider) -> GraphState:
    content = provider.get(state.content_id)
    state.content = content
    state.text = content.normalized_text()
    state.status = "CONTENT_LOADED"
    return state


def clean_normalize_node(state: GraphState) -> GraphState:
    if not state.text:
        raise ValueError("text must be present before clean normalize")

    cleaned, stats = clean_normalize_text(state.text)
    state.text = cleaned
    state.intermediate["clean_stats"] = stats
    state.status = "CLEANED"
    return state


def filter_node(state: GraphState, *, llm: LLMClient, router: ModelRouter) -> GraphState:
    if not state.text:
        raise ValueError("text must be present before filter")

    started = perf_counter()
    filter_model = router.model_for("cheap")
    response = llm.structured(
        "Judge whether this content is low-quality or marketing-only. "
        "Return {ignore, reason, value}.\n\n"
        f"{state.text}",
        schema_name="ContentFilter",
        model=filter_model,
    )
    result = response.data
    state.intermediate["filter"] = result
    state.add_trace(
        UsageTrace(
            node="filter",
            model=filter_model,
            prompt_tokens=response.prompt_tokens,
            completion_tokens=response.completion_tokens,
            elapsed_ms=int((perf_counter() - started) * 1000),
        )
    )

    if bool(result.get("ignore")):
        state.status = "CANCELLED"
        state.cancel_reason = str(result.get("reason", "filtered"))
    else:
        state.status = "FILTER_PASSED"
    return state


def branch_by_length_node(state: GraphState, *, config: GraphConfig) -> GraphState:
    if not state.text:
        raise ValueError("text must be present before length branch")

    char_count = len(state.text)
    route = "split" if char_count > config.split_threshold_chars else "full"
    state.route = route
    state.intermediate["length_branch"] = {
        "route": route,
        "char_count": char_count,
        "threshold": config.split_threshold_chars,
    }
    state.status = "BRANCHED"
    return state


def split_text_into_chunks(text: str, *, chunk_size_chars: int, overlap_chars: int) -> list[str]:
    if chunk_size_chars <= 0:
        raise ValueError("chunk_size_chars must be positive")
    if overlap_chars < 0 or overlap_chars >= chunk_size_chars:
        raise ValueError("overlap_chars must be non-negative and smaller than chunk_size_chars")

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size_chars, len(text))
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end == len(text):
            break
        start = end - overlap_chars
    return chunks


def analyze_chunk_node(state: GraphState, *, llm: LLMClient, router: ModelRouter, config: GraphConfig) -> GraphState:
    if state.route != "split":
        return state
    if not state.text:
        raise ValueError("text must be present before chunk analysis")

    chunks = split_text_into_chunks(
        state.text,
        chunk_size_chars=config.chunk_size_chars,
        overlap_chars=config.chunk_overlap_chars,
    )
    chunk_results: list[dict[str, object]] = []
    analysis_model = router.model_for("standard")
    for index, chunk in enumerate(chunks):
        started = perf_counter()
        response = llm.structured(
            f"Analyze chunk {index + 1}/{len(chunks)} for content_id={state.content_id}.\n\n{chunk}",
            schema_name="ChunkAnalysis",
            model=analysis_model,
        )
        chunk_results.append(response.data)
        state.add_trace(
            UsageTrace(
                node=f"analyze_chunk:{index}",
                model=analysis_model,
                prompt_tokens=response.prompt_tokens,
                completion_tokens=response.completion_tokens,
                elapsed_ms=int((perf_counter() - started) * 1000),
            )
        )

    state.intermediate["chunks"] = chunks
    state.intermediate["chunk_analyses"] = chunk_results
    state.status = "CHUNKS_ANALYZED"
    return state


def aggregate_chunks_node(state: GraphState) -> GraphState:
    if state.route != "split":
        return state
    chunk_results = state.intermediate.get("chunk_analyses")
    if not isinstance(chunk_results, list) or not chunk_results:
        raise ValueError("chunk analyses are required before aggregation")

    key_points: list[str] = []
    quotes: list[str] = []
    entities: list[str] = []
    base_tags: list[str] = []
    summaries: list[str] = []
    for result in chunk_results:
        if not isinstance(result, dict):
            raise ValueError("chunk analysis must be a dictionary")
        summaries.append(str(result.get("summary", "")).strip())
        key_points.extend(str(item).strip() for item in result.get("key_points", []) if str(item).strip())
        quotes.extend(str(item).strip() for item in result.get("quotes", []) if str(item).strip())
        entities.extend(str(item).strip() for item in result.get("entities", []) if str(item).strip())
        base_tags.extend(str(item).strip() for item in result.get("base_tags", []) if str(item).strip())

    def dedupe(values: list[str]) -> list[str]:
        seen: set[str] = set()
        output: list[str] = []
        for value in values:
            key = value.casefold()
            if key not in seen:
                seen.add(key)
                output.append(value)
        return output

    deduped_points = dedupe(key_points)
    deduped_summaries = dedupe([summary for summary in summaries if summary])
    state.intermediate["base_analysis"] = {
        "one_liner": deduped_points[0] if deduped_points else "Aggregated long-form analysis",
        "summary": " ".join(deduped_summaries).strip() or "Aggregated long-form summary.",
        "key_points": deduped_points,
        "quotes": dedupe(quotes),
        "entities": dedupe(entities),
        "base_tags": dedupe(base_tags) or ["long-form"],
    }
    state.status = "AGGREGATED"
    return state


def base_analysis_node(state: GraphState, *, llm: LLMClient, router: ModelRouter) -> GraphState:
    if state.content is None or not state.text:
        raise ValueError("content must be loaded before base analysis")

    started = perf_counter()
    analysis_model = router.model_for("standard")
    response = llm.structured(
        f"Create BaseAnalysis for content_id={state.content.content_id}\n\n{state.text}",
        schema_name="BaseAnalysis",
        model=analysis_model,
    )
    state.intermediate["base_analysis"] = response.data
    state.add_trace(
        UsageTrace(
            node="base_analysis",
            model=analysis_model,
            prompt_tokens=response.prompt_tokens,
            completion_tokens=response.completion_tokens,
            elapsed_ms=int((perf_counter() - started) * 1000),
        )
    )
    state.status = "ANALYZED"
    return state


def embedding_node(state: GraphState, *, llm: LLMClient, router: ModelRouter) -> GraphState:
    if not state.text:
        raise ValueError("text must be present before embedding")

    started = perf_counter()
    embed_model = router.model_for("embed")
    embedding = llm.embed(state.text, model=embed_model)
    state.intermediate["embedding"] = embedding
    state.add_trace(
        UsageTrace(
            node="embedding",
            model=embed_model,
            prompt_tokens=len(state.text.split()),
            completion_tokens=0,
            elapsed_ms=int((perf_counter() - started) * 1000),
        )
    )
    state.status = "EMBEDDED"
    return state


def persist_placeholder_node(state: GraphState) -> GraphState:
    if state.content is None:
        raise ValueError("content must be loaded before persistence")
    data = state.intermediate.get("base_analysis")
    embedding = state.intermediate.get("embedding")
    if not isinstance(data, dict) or not isinstance(embedding, list):
        raise ValueError("analysis data and embedding are required before persistence")

    analysis = BaseAnalysis(
        content_id=state.content.content_id,
        one_liner=str(data["one_liner"]),
        summary=str(data["summary"]),
        key_points=list(data["key_points"]),
        quotes=list(data.get("quotes", [])),
        entities=list(data.get("entities", [])),
        base_tags=list(data["base_tags"]),
        embedding=embedding,
        traces=list(state.traces),
    )
    analysis.validate()
    state.analysis = analysis
    state.status = "COMPLETED"
    return state


def enrich(
    content_id: str,
    *,
    provider: ContentProvider,
    llm: LLMClient,
    router: ModelRouter | None = None,
    config: GraphConfig | None = None,
) -> GraphState:
    router = router or ModelRouter()
    config = config or GraphConfig()
    state = GraphState(content_id=content_id)
    state = load_content_node(state, provider=provider)
    state = clean_normalize_node(state)
    state = filter_node(state, llm=llm, router=router)
    if state.status == "CANCELLED":
        return state
    state = branch_by_length_node(state, config=config)
    if state.route == "split":
        state = analyze_chunk_node(state, llm=llm, router=router, config=config)
        state = aggregate_chunks_node(state)
    else:
        state = base_analysis_node(state, llm=llm, router=router)
    state = embedding_node(state, llm=llm, router=router)
    return persist_placeholder_node(state)


def run_enrichment(
    content_id: str,
    *,
    provider: ContentProvider,
    llm: LLMClient,
    router: ModelRouter | None = None,
    config: GraphConfig | None = None,
) -> BaseAnalysis:
    state = enrich(content_id, provider=provider, llm=llm, router=router, config=config)
    if state.analysis is None:
        raise ValueError(f"enrichment finished without analysis: status={state.status}")
    return state.analysis
