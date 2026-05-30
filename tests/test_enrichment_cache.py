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


def test_graph_version_upgrade_invalidates_cache_and_reprocesses() -> None:
    cache = InMemoryEnrichmentCache()
    enrich("demo-article", provider=StubContentProvider(), llm=FakeLLM(), cache=cache, graph_version="v1")

    second_llm = FakeLLM()
    state = enrich("demo-article", provider=StubContentProvider(), llm=second_llm, cache=cache, graph_version="v2")

    assert state.graph_version == "v2"
    assert state.intermediate["cache"]["hit"] is False
    assert cache.count() == 2
    assert second_llm.calls["structured"] > 0
    assert second_llm.calls["embed"] == 1


def test_reprocess_bypasses_same_version_cache() -> None:
    cache = InMemoryEnrichmentCache()
    enrich("demo-article", provider=StubContentProvider(), llm=FakeLLM(), cache=cache, graph_version="v1")

    second_llm = FakeLLM()
    state = enrich(
        "demo-article",
        provider=StubContentProvider(),
        llm=second_llm,
        cache=cache,
        graph_version="v1",
        reprocess=True,
    )

    assert state.intermediate["cache"] == {"hit": False, "bypassed": True}
    assert cache.count() == 1
    assert second_llm.calls["structured"] > 0
    assert second_llm.calls["embed"] == 1
