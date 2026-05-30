from l1_data_processing.events import CONTENT_ANALYZED, InMemoryOutbox
from l1_data_processing.graph import enrich
from l1_data_processing.input import StubContentProvider
from l1_data_processing.llm import FakeLLM


def test_completed_enrichment_writes_one_content_analyzed_event() -> None:
    outbox = InMemoryOutbox()

    state = enrich("demo-article", provider=StubContentProvider(), llm=FakeLLM(), outbox=outbox)
    enrich("demo-article", provider=StubContentProvider(), llm=FakeLLM(), outbox=outbox)

    assert state.status == "COMPLETED"
    assert outbox.count() == 1
    event = outbox.unsent()[0]
    assert event.event_id == "content.analyzed:demo-article"
    assert event.topic == CONTENT_ANALYZED
    assert event.aggregate_id == "demo-article"
    assert event.payload["content_id"] == "demo-article"
    assert event.payload["graph_version"] == state.graph_version


def test_outbox_relay_marks_event_as_sent() -> None:
    outbox = InMemoryOutbox()
    enrich("demo-article", provider=StubContentProvider(), llm=FakeLLM(), outbox=outbox)
    event = outbox.unsent()[0]

    outbox.mark_sent(event.event_id)

    assert outbox.unsent() == []
    assert outbox.get(event.event_id).sent_at is not None


def test_cancelled_content_does_not_emit_analyzed_event() -> None:
    outbox = InMemoryOutbox()
    llm = FakeLLM({"ContentFilter": {"ignore": True, "reason": "low quality", "value": "low"}})

    state = enrich("demo-article", provider=StubContentProvider(), llm=llm, outbox=outbox)

    assert state.status == "CANCELLED"
    assert outbox.count() == 0
