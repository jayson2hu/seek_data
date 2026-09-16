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


def test_same_text_with_different_ids_keeps_outputs_on_each_content():
    from dataclasses import replace

    from l1_data_processing.events import InMemoryOutbox
    from l1_data_processing.persistence import InMemoryContentBaseAnalysisRepository

    class SameTextProvider:
        def get(self, content_id):
            return replace(StubContentProvider().get("demo-article"), content_id=content_id)

    cache = InMemoryEnrichmentCache()
    outbox = InMemoryOutbox()
    repository = InMemoryContentBaseAnalysisRepository()
    first = enrich("first", provider=SameTextProvider(), llm=FakeLLM(), cache=cache, outbox=outbox, repository=repository)
    second_llm = FakeLLM()
    second = enrich("second", provider=SameTextProvider(), llm=second_llm, cache=cache, outbox=outbox, repository=repository)

    assert second.intermediate["cache"]["hit"] and not second_llm.calls
    assert first.analysis.content_id == "first"
    assert second.analysis.content_id == "second"
    assert repository.count() == 2 and outbox.count() == 2 and cache.count() == 1
    assert repository.get("second").analysis.content_id == "second"
    assert outbox.get("content.analyzed:second").payload["analysis"]["content_id"] == "second"
    second.analysis.key_points.append("change second only")
    assert "change second only" not in first.analysis.key_points
