from __future__ import annotations

from sqlalchemy import create_engine

from l1_data_processing.contracts import ContentInput
from l1_data_processing.durable import process_content
from l1_data_processing.llm import DeterministicExtractiveLLM, ExtractiveContentProvider
from l1_data_processing.llm.router import ModelRouter
from l1_data_processing.sql_store import SqlAlchemyEnrichmentStore


class PublicContentProvider:
    def get(self, content_id: str) -> ContentInput:
        return ContentInput(
            content_id=content_id,
            title="OpenAI and GitHub improve coding agents",
            body=(
                "GitHub published a concrete engineering update for coding agents. "
                "OpenAI APIs now support a documented workflow for developer tools. "
                "The release notes describe migration steps and observable behavior."
            ),
            source_url="https://example.test/official-update",
            metadata={
                "source_kind": "public_feed",
                "source": {"name": "Official engineering feed"},
            },
        )


def test_extractive_provider_uses_source_excerpts_and_marks_processing(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'l1.db'}")
    store = SqlAlchemyEnrichmentStore(engine)
    store.create_schema()
    llm = DeterministicExtractiveLLM()

    result = process_content(
        "42",
        store=store,
        provider=ExtractiveContentProvider(PublicContentProvider()),
        llm=llm,
        graph_version="extractive-v3",
        router=ModelRouter(
            {
                "cheap": "extractive-filter-v3",
                "standard": "extractive-v3",
                "embed": "extractive-hash-v1",
            }
        ),
    )

    assert result.status == "WAIT_SCORE"
    assert result.analysis is not None
    assert "FakeLLM" not in result.analysis["summary"]
    assert "GitHub published a concrete engineering update" in result.analysis["summary"]
    assert set(result.analysis["entities"]) == {"OpenAI", "GitHub"}
    assert {"ai", "engineering"} <= set(result.analysis["base_tags"])
    assert all(
        point in PublicContentProvider().get("42").normalized_text()
        for point in result.analysis["key_points"]
    )
    row = store.get("42")
    assert row is not None
    assert row["input_snapshot"]["metadata"]["processing"] == {
        "method": "extractive-v3",
        "provider": "deterministic-extractive",
        "model": None,
        "generated": False,
    }
    run = store.runs("42")[0]
    assert run["llm_calls"] == 3
    assert {trace["model"] for trace in run["traces"]} == {
        "extractive-filter-v3",
        "extractive-v3",
        "extractive-hash-v1",
    }
    engine.dispose()


def test_extractive_output_is_deterministic_and_embedding_is_local() -> None:
    llm = DeterministicExtractiveLLM()
    prompt = (
        "Create BaseAnalysis\n\n"
        "GitHub documents an AI coding workflow. OpenAI publishes API migration guidance."
    )

    first = llm.structured(prompt, schema_name="BaseAnalysis", model="ignored")
    second = llm.structured(prompt, schema_name="BaseAnalysis", model="ignored")

    assert first.data == second.data
    assert first.data["summary"] in prompt
    assert llm.embed("same local text", model="ignored") == llm.embed(
        "same local text", model="another-ignored-model"
    )
