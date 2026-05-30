from l1_data_processing.cache import InMemoryEnrichmentCache
from l1_data_processing.graph import enrich
from l1_data_processing.input import StubContentProvider
from l1_data_processing.llm import FakeLLM


def test_same_content_and_graph_version_hits_cache_without_llm_calls() -> None:
    cache = InMemoryEnrichmentCache()

    first_llm = FakeLLM()
    first = enrich("demo-article", provider=StubContentProvider(), llm=first_llm, cache=cache)
    second_llm = FakeLLM()
    second = enrich("demo-article", provider=StubContentProvider(), llm=second_llm, cache=cache)

    assert first.status == "COMPLETED"
    assert second.status == "COMPLETED"
    assert second.intermediate["cache"]["hit"] is True
    assert second.analysis == first.analysis
    assert cache.count() == 1
    assert second_llm.calls["structured"] == 0
    assert second_llm.calls["embed"] == 0
