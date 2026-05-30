from l1_data_processing.graph import enrich
from l1_data_processing.input import StubContentProvider
from l1_data_processing.llm import FakeLLM
from l1_data_processing.persistence import ContentBaseAnalysisRecord, InMemoryContentBaseAnalysisRepository


def test_content_base_analysis_repository_upserts_by_content_id() -> None:
    repository = InMemoryContentBaseAnalysisRepository()

    first = enrich("demo-article", provider=StubContentProvider(), llm=FakeLLM(), repository=repository)
    second = enrich("demo-article", provider=StubContentProvider(), llm=FakeLLM(), repository=repository)

    assert repository.count() == 1
    record = repository.get("demo-article")
    assert isinstance(record, ContentBaseAnalysisRecord)
    assert record.analysis.content_id == "demo-article"
    assert record.analysis.summary == second.analysis.summary
    assert first.analysis is not None


def test_persisted_content_base_analysis_record_has_required_fields() -> None:
    repository = InMemoryContentBaseAnalysisRepository()

    state = enrich("demo-article", provider=StubContentProvider(), llm=FakeLLM(), repository=repository)

    record = repository.get("demo-article")
    assert record is not None
    assert record.graph_version == state.graph_version
    assert record.prompt_tokens > 0
    assert record.completion_tokens > 0
    assert record.cost_units == record.prompt_tokens + record.completion_tokens
    assert record.model_names == ["fake-cheap", "fake-standard", "fake-embed"]
    assert record.to_dict()["analysis"]["content_id"] == "demo-article"
    assert state.intermediate["content_base_analysis_record"]["content_id"] == "demo-article"
