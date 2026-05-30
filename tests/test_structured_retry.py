from l1_data_processing.config import GraphConfig
from l1_data_processing.graph import enrich
from l1_data_processing.input import StubContentProvider
from l1_data_processing.llm import FakeLLM


INVALID_BASE_ANALYSIS = {
    "one_liner": "",
    "summary": "bad",
    "key_points": [],
    "quotes": [],
    "entities": [],
    "base_tags": [],
}


VALID_BASE_ANALYSIS = {
    "one_liner": "valid after retry",
    "summary": "A valid summary.",
    "key_points": ["retry succeeded"],
    "quotes": [],
    "entities": ["L1"],
    "base_tags": ["retry"],
}


def test_invalid_structured_output_retries_and_then_succeeds() -> None:
    llm = FakeLLM(
        {
            "ContentFilter": {"ignore": False, "reason": "", "value": "normal"},
            "BaseAnalysis": [INVALID_BASE_ANALYSIS, VALID_BASE_ANALYSIS],
        }
    )

    state = enrich(
        "demo-article",
        provider=StubContentProvider(),
        llm=llm,
        config=GraphConfig(structured_max_attempts=2),
    )

    assert state.status == "COMPLETED"
    assert state.analysis is not None
    assert state.analysis.one_liner == "valid after retry"
    assert [trace.node for trace in state.traces] == [
        "filter",
        "base_analysis:attempt:1",
        "base_analysis:attempt:2",
        "embedding",
    ]
    assert llm.calls["structured:BaseAnalysis"] == 2


def test_repeated_invalid_structured_output_fails_without_polluting_artifact() -> None:
    llm = FakeLLM(
        {
            "ContentFilter": {"ignore": False, "reason": "", "value": "normal"},
            "BaseAnalysis": [INVALID_BASE_ANALYSIS, INVALID_BASE_ANALYSIS],
        }
    )

    state = enrich(
        "demo-article",
        provider=StubContentProvider(),
        llm=llm,
        config=GraphConfig(structured_max_attempts=2),
    )

    assert state.status == "FAILED"
    assert state.analysis is None
    assert state.error is not None
    assert "BaseAnalysis validation failed" in state.error
    assert "embedding" not in [trace.node for trace in state.traces]
    assert llm.calls["embed"] == 0
