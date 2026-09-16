import json

import pytest

from l1_data_processing.worker import parse_envelope


def test_parse_versioned_l0_event_envelope() -> None:
    event = parse_envelope(json.dumps({
        "topic": "content.ingested",
        "payload": {
            "content_id": 42,
            "content_version": 2,
            "content_hash": "body-v2",
        },
        "idempotency_key": "content.ingested:42:v2",
    }))

    assert event.event_id == "content.ingested:42:v2"
    assert event.aggregate_id == "42"
    assert event.payload["content_version"] == 2


@pytest.mark.parametrize("value", [
    [],
    {"payload": {}, "idempotency_key": "event"},
    {"topic": "content.ingested", "payload": [], "idempotency_key": "event"},
    {"topic": "content.ingested", "payload": {}},
])
def test_parse_envelope_rejects_malformed_messages(value) -> None:
    with pytest.raises(ValueError):
        parse_envelope(json.dumps(value))
