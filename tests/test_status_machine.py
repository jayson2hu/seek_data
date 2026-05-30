import pytest

from l1_data_processing.graph import enrich
from l1_data_processing.input import StubContentProvider
from l1_data_processing.llm import FakeLLM
from l1_data_processing.status import CANCELLED, WAIT_ANALYSIS, WAIT_SCORE, ContentStatusMachine, InvalidStatusTransition


def test_status_machine_allows_success_and_cancel_terminal_paths() -> None:
    machine = ContentStatusMachine()

    assert machine.initialize("success") == WAIT_ANALYSIS
    assert machine.transition("success", WAIT_SCORE) == WAIT_SCORE

    assert machine.initialize("cancelled") == WAIT_ANALYSIS
    assert machine.transition("cancelled", CANCELLED) == CANCELLED


def test_status_machine_rejects_invalid_transition_from_terminal_state() -> None:
    machine = ContentStatusMachine()
    machine.transition("cid", WAIT_SCORE)

    with pytest.raises(InvalidStatusTransition):
        machine.transition("cid", CANCELLED)


def test_enrich_success_transitions_content_to_wait_score() -> None:
    machine = ContentStatusMachine()

    state = enrich("demo-article", provider=StubContentProvider(), llm=FakeLLM(), status_machine=machine)

    assert state.status == "COMPLETED"
    assert state.content_status == WAIT_SCORE
    assert machine.get("demo-article") == WAIT_SCORE


def test_enrich_cancelled_transitions_content_to_cancelled() -> None:
    machine = ContentStatusMachine()
    llm = FakeLLM({"ContentFilter": {"ignore": True, "reason": "low quality", "value": "low"}})

    state = enrich("demo-article", provider=StubContentProvider(), llm=llm, status_machine=machine)

    assert state.status == "CANCELLED"
    assert state.content_status == CANCELLED
    assert machine.get("demo-article") == CANCELLED
