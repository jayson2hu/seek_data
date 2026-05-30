from l1_data_processing.graph import base_analysis_node, embedding_node, load_content_node
from l1_data_processing.config import GraphConfig
from l1_data_processing.input import StubContentProvider
from l1_data_processing.llm import FakeLLM, ModelRouter
from l1_data_processing.state import GRAPH_VERSION, GraphState


def test_graph_state_serializes_and_accumulates_across_nodes() -> None:
    state = GraphState(content_id="demo-article")
    provider = StubContentProvider()
    llm = FakeLLM()
    router = ModelRouter()

    state = load_content_node(state, provider=provider)
    assert state.status == "CONTENT_LOADED"
    assert state.text

    state = base_analysis_node(state, llm=llm, router=router, config=GraphConfig())
    state = embedding_node(state, llm=llm, router=router)
    serialized = state.to_dict()

    assert serialized["graph_version"] == GRAPH_VERSION
    assert serialized["content"]["content_id"] == "demo-article"
    assert serialized["intermediate"]["base_analysis"]["one_liner"]
    assert len(serialized["intermediate"]["embedding"]) == 8
    assert "L1 standalone data processing fixture" in serialized["intermediate"]["embedding_input"]
    assert [trace["node"] for trace in serialized["traces"]] == ["base_analysis:attempt:1", "embedding"]
    assert serialized["cost"]["prompt_tokens"] > 0


def test_enrich_returns_completed_state() -> None:
    from l1_data_processing.graph import enrich

    state = enrich("demo-article", provider=StubContentProvider(), llm=FakeLLM())

    assert state.status == "COMPLETED"
    assert state.analysis is not None
    assert state.analysis.content_id == "demo-article"
    assert state.to_dict()["analysis"]["status"] == "COMPLETED"
