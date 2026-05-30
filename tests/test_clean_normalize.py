from l1_data_processing.graph import clean_normalize_node
from l1_data_processing.state import GraphState
from l1_data_processing.text import clean_normalize_text


def test_clean_normalize_text_removes_html_and_tracks_stats() -> None:
    cleaned, stats = clean_normalize_text("<h1>Hello&nbsp;L1</h1>\n<p> first   paragraph </p>\n\n<p>second</p>")

    assert "<h1>" not in cleaned
    assert "<p>" not in cleaned
    assert "Hello L1" in cleaned
    assert "first paragraph" in cleaned
    assert stats == {
        "char_count": len(cleaned),
        "word_count": len(cleaned.split()),
        "paragraph_count": 3,
    }


def test_clean_normalize_node_updates_state_text_and_stats() -> None:
    state = GraphState(content_id="demo")
    state.text = "Title\n\n<div>Body    with&nbsp;spaces</div>"

    state = clean_normalize_node(state)

    assert state.status == "CLEANED"
    assert state.text == "Title\nBody with spaces"
    assert state.intermediate["clean_stats"]["char_count"] == len(state.text)
