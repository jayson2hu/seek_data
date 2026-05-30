from l1_data_processing.config import GraphConfig
from l1_data_processing.graph import enrich
from l1_data_processing.input import StubContentProvider
from l1_data_processing.llm import FakeLLM


def test_graph_config_model_tiers_route_each_node_without_code_changes() -> None:
    config = GraphConfig(
        model_tiers={
            "cheap": "configured-filter-model",
            "standard": "configured-analysis-model",
            "embed": "configured-embedding-model",
        }
    )

    state = enrich("demo-article", provider=StubContentProvider(), llm=FakeLLM(), config=config)

    assert [(trace.node, trace.model) for trace in state.traces] == [
        ("filter", "configured-filter-model"),
        ("base_analysis:attempt:1", "configured-analysis-model"),
        ("embedding", "configured-embedding-model"),
    ]


def test_graph_config_requires_all_model_tiers() -> None:
    try:
        GraphConfig(model_tiers={"cheap": "small", "standard": "middle"})
    except ValueError as exc:
        assert "embed" in str(exc)
    else:
        raise AssertionError("GraphConfig accepted missing embed tier")
