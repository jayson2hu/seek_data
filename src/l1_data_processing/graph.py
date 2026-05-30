from __future__ import annotations

from time import perf_counter

from l1_data_processing.contracts import BaseAnalysis, UsageTrace
from l1_data_processing.input.provider import ContentProvider
from l1_data_processing.llm.client import LLMClient
from l1_data_processing.llm.router import ModelRouter


def run_enrichment(content_id: str, *, provider: ContentProvider, llm: LLMClient, router: ModelRouter | None = None) -> BaseAnalysis:
    router = router or ModelRouter()
    content = provider.get(content_id)
    text = content.normalized_text()

    started = perf_counter()
    analysis_model = router.model_for("standard")
    response = llm.structured(
        f"Create BaseAnalysis for content_id={content.content_id}\n\n{text}",
        schema_name="BaseAnalysis",
        model=analysis_model,
    )
    analysis_elapsed = int((perf_counter() - started) * 1000)

    started = perf_counter()
    embed_model = router.model_for("embed")
    embedding = llm.embed(text, model=embed_model)
    embed_elapsed = int((perf_counter() - started) * 1000)

    analysis = BaseAnalysis(
        content_id=content.content_id,
        one_liner=str(response.data["one_liner"]),
        summary=str(response.data["summary"]),
        key_points=list(response.data["key_points"]),
        quotes=list(response.data.get("quotes", [])),
        entities=list(response.data.get("entities", [])),
        base_tags=list(response.data["base_tags"]),
        embedding=embedding,
        traces=[
            UsageTrace(
                node="base_analysis",
                model=analysis_model,
                prompt_tokens=response.prompt_tokens,
                completion_tokens=response.completion_tokens,
                elapsed_ms=analysis_elapsed,
            ),
            UsageTrace(
                node="embedding",
                model=embed_model,
                prompt_tokens=len(text.split()),
                completion_tokens=0,
                elapsed_ms=embed_elapsed,
            ),
        ],
    )
    analysis.validate()
    return analysis
