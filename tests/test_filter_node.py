from l1_data_processing.graph import clean_normalize_node, enrich, filter_node, load_content_node
from l1_data_processing.input import StubContentProvider
from l1_data_processing.llm import FakeLLM, ModelRouter
from l1_data_processing.state import GraphState


def test_filter_node_passes_normal_content() -> None:
    state = GraphState(content_id="demo-article")
    llm = FakeLLM({"ContentFilter": {"ignore": False, "reason": "", "value": "normal"}})
    router = ModelRouter()

    state = load_content_node(state, provider=StubContentProvider())
    state = clean_normalize_node(state)
    state = filter_node(state, llm=llm, router=router)

    assert state.status == "FILTER_PASSED"
    assert state.intermediate["filter"]["ignore"] is False
    assert [trace.node for trace in state.traces] == ["filter"]


def test_filter_node_cancels_and_short_circuits_expensive_nodes() -> None:
    llm = FakeLLM({"ContentFilter": {"ignore": True, "reason": "marketing only", "value": "low"}})

    state = enrich("demo-article", provider=StubContentProvider(), llm=llm)

    assert state.status == "CANCELLED"
    assert state.cancel_reason == "marketing only"
    assert state.analysis is None
    assert [trace.node for trace in state.traces] == ["filter"]
    assert llm.calls["structured"] == 1
    assert llm.calls["embed"] == 0
