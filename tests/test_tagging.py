from l1_data_processing.graph import language_and_tags_node
from l1_data_processing.state import GraphState
from l1_data_processing.tagging import GENERAL_TAGS, detect_language, infer_general_tags, normalize_general_tags


def test_detect_language_for_chinese_and_english_samples() -> None:
    assert detect_language("这是一个关于人工智能和数据平台的中文样本") == "zh"
    assert detect_language("This is an English sample about technology and data.") == "en"


def test_general_tags_are_limited_to_controlled_vocabulary() -> None:
    tags = infer_general_tags(
        "AI platform data analytics for business users",
        existing_tags=["ai", "vertical-insurance", "DATA"],
    )

    assert tags == ["ai", "data", "business", "technology"]
    assert set(tags) <= GENERAL_TAGS


def test_normalize_general_tags_filters_vertical_specific_tags() -> None:
    assert normalize_general_tags(["finance", "insurance-claim", "technology"]) == ["finance", "technology"]


def test_language_and_tags_node_updates_state_and_payload() -> None:
    state = GraphState(content_id="cid", text="AI data platform research")
    state.intermediate["base_analysis"] = {
        "summary": "Technology research summary",
        "key_points": ["data platform"],
        "base_tags": ["vertical-crm", "research"],
    }

    state = language_and_tags_node(state)

    assert state.status == "TAGGED"
    assert state.lang == "en"
    assert state.intermediate["base_analysis"]["base_tags"] == ["research", "ai", "data", "technology"]
    assert set(state.intermediate["language_tags"]["base_tags"]) <= GENERAL_TAGS
