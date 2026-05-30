from l1_data_processing.config import GraphConfig
from l1_data_processing.graph import enrich, split_text_into_chunks
from l1_data_processing.input import StubContentProvider
from l1_data_processing.llm import FakeLLM


def test_split_text_into_chunks_uses_overlap() -> None:
    chunks = split_text_into_chunks("abcdefghij", chunk_size_chars=4, overlap_chars=1)

    assert chunks == ["abcd", "defg", "ghij"]


def test_long_content_aggregates_each_chunk_marker_without_duplicates() -> None:
    llm = FakeLLM(
        {
            "ContentFilter": {"ignore": False, "reason": "", "value": "normal"},
            "ChunkAnalysis": [
                {
                    "one_liner": "chunk one",
                    "summary": "Summary one.",
                    "key_points": ["marker one", "shared"],
                    "quotes": ["quote one"],
                    "entities": ["EntityOne"],
                    "base_tags": ["analysis"],
                },
                {
                    "one_liner": "chunk two",
                    "summary": "Summary two.",
                    "key_points": ["marker two", "shared"],
                    "quotes": ["quote two"],
                    "entities": ["EntityTwo"],
                    "base_tags": ["analysis", "long-form"],
                },
            ],
        }
    )
    config = GraphConfig(split_threshold_chars=10, chunk_size_chars=70, chunk_overlap_chars=0)

    state = enrich("demo-article", provider=StubContentProvider(), llm=llm, config=config)

    assert state.route == "split"
    assert state.status == "COMPLETED"
    assert state.analysis is not None
    assert state.analysis.key_points == ["marker one", "shared", "marker two"]
    assert state.analysis.summary == "Summary one. Summary two."
    chunks = state.intermediate["chunks"]
    assert chunks
    assert [trace.node for trace in state.traces] == [
        "filter",
        *[f"analyze_chunk:{index}:attempt:1" for index in range(len(chunks))],
        "embedding",
    ]
    assert llm.calls["structured:ChunkAnalysis"] == len(chunks)
