import pytest

from l1_data_processing.config import GraphConfig
from l1_data_processing.graph import branch_by_length_node
from l1_data_processing.state import GraphState


def test_length_branch_routes_short_text_to_full() -> None:
    state = GraphState(content_id="short", text="short text")

    state = branch_by_length_node(state, config=GraphConfig(split_threshold_chars=20))

    assert state.status == "BRANCHED"
    assert state.route == "full"
    assert state.intermediate["length_branch"] == {
        "route": "full",
        "char_count": len("short text"),
        "threshold": 20,
    }


def test_length_branch_routes_long_text_to_split_with_configurable_threshold() -> None:
    state = GraphState(content_id="long", text="x" * 21)

    state = branch_by_length_node(state, config=GraphConfig(split_threshold_chars=20))

    assert state.route == "split"
    assert state.intermediate["length_branch"]["threshold"] == 20


def test_graph_config_rejects_invalid_threshold() -> None:
    with pytest.raises(ValueError, match="split_threshold_chars"):
        GraphConfig(split_threshold_chars=0)
