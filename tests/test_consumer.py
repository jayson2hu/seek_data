import pytest

from l1_data_processing.cache import InMemoryEnrichmentCache
from l1_data_processing.consumer import CONTENT_INGESTED, consume_content_ingested, parse_content_ingested
from l1_data_processing.events import CONTENT_ANALYZED, InMemoryOutbox, OutboxEvent
from l1_data_processing.input.stub import StubContentProvider
from l1_data_processing.llm.fake import FakeLLM
from l1_data_processing.persistence import InMemoryContentBaseAnalysisRepository


def test_parse_content_ingested_validates_contract() -> None:
    event = OutboxEvent(
        event_id="content.ingested:demo-article",
        topic=CONTENT_INGESTED,
        aggregate_id="demo-article",
        payload={"content_id": " demo-article ", "graph_version": "v2", "reprocess": True},
    )

    message = parse_content_ingested(event)

    assert message.content_id == "demo-article"
    assert message.graph_version == "v2"
    assert message.reprocess is True


def test_parse_content_ingested_rejects_wrong_topic() -> None:
    event = OutboxEvent(
        event_id="content.analyzed:demo-article",
        topic=CONTENT_ANALYZED,
        aggregate_id="demo-article",
        payload={"content_id": "demo-article"},
    )

    with pytest.raises(ValueError, match="unsupported topic"):
        parse_content_ingested(event)


def test_consume_content_ingested_runs_enrichment_and_writes_outputs() -> None:
    repository = InMemoryContentBaseAnalysisRepository()
    outbox = InMemoryOutbox()
    event = OutboxEvent(
        event_id="content.ingested:demo-article",
        topic=CONTENT_INGESTED,
        aggregate_id="demo-article",
        payload={"content_id": "demo-article"},
    )

    state = consume_content_ingested(
        event,
        provider=StubContentProvider(),
        llm=FakeLLM(),
        repository=repository,
        outbox=outbox,
    )

    assert state.status == "COMPLETED"
    assert repository.get("demo-article") is not None
    assert outbox.count() == 1
    assert outbox.unsent()[0].topic == CONTENT_ANALYZED


def test_consume_content_ingested_is_idempotent_with_cache_and_outbox() -> None:
    cache = InMemoryEnrichmentCache()
    outbox = InMemoryOutbox()
    event = OutboxEvent(
        event_id="content.ingested:demo-article",
        topic=CONTENT_INGESTED,
        aggregate_id="demo-article",
        payload={"content_id": "demo-article"},
    )

    first_llm = FakeLLM()
    first = consume_content_ingested(
        event,
        provider=StubContentProvider(),
        llm=first_llm,
        cache=cache,
        outbox=outbox,
    )
    second_llm = FakeLLM()
    second = consume_content_ingested(
        event,
        provider=StubContentProvider(),
        llm=second_llm,
        cache=cache,
        outbox=outbox,
    )

    assert first.status == "COMPLETED"
    assert second.status == "COMPLETED"
    assert second.intermediate["cache"]["hit"] is True
    assert dict(second_llm.calls) == {}
    assert outbox.count() == 1


@pytest.mark.parametrize("content_id, expected", [(1, "1"), (42, "42"), ("demo-article", "demo-article")])
def test_parse_content_ingested_accepts_l0_integer_ids(content_id, expected):
    event = OutboxEvent("event", CONTENT_INGESTED, str(content_id), {"content_id": content_id})
    assert parse_content_ingested(event).content_id == expected


@pytest.mark.parametrize("content_id", [None, True, False, 0, -1, 1.5, [], {}, "", " "])
def test_parse_content_ingested_rejects_invalid_ids(content_id):
    event = OutboxEvent("event", CONTENT_INGESTED, "invalid", {"content_id": content_id})
    with pytest.raises(ValueError, match="content_id"):
        parse_content_ingested(event)


def test_duplicate_delivery_with_shared_status_machine_is_idempotent():
    from l1_data_processing.status import WAIT_SCORE, ContentStatusMachine

    machine = ContentStatusMachine()
    cache = InMemoryEnrichmentCache()
    repository = InMemoryContentBaseAnalysisRepository()
    outbox = InMemoryOutbox()
    event = OutboxEvent("event", CONTENT_INGESTED, "demo-article", {"content_id": "demo-article"})
    for _ in range(2):
        result = consume_content_ingested(
            event, provider=StubContentProvider(), llm=FakeLLM(), status_machine=machine,
            cache=cache, repository=repository, outbox=outbox,
        )
        assert result.status == "COMPLETED"
    assert machine.get("demo-article") == WAIT_SCORE
    assert repository.count() == outbox.count() == 1
