from __future__ import annotations

import json

from l1_data_processing.relay import RedisEventPublisher


class FakeRedis:
    def __init__(self) -> None:
        self.accepted: set[str] = set()
        self.items: list[str] = []

    def eval(self, script, numkeys, *values):
        del script
        assert numkeys == 2
        accepted_key, queue_name, serialized, ttl = values
        assert queue_name == "codepick:l1:events"
        assert ttl > 0
        if accepted_key in self.accepted:
            return 0
        self.items.append(serialized)
        self.accepted.add(accepted_key)
        return 1


def test_redis_event_publisher_preserves_event_identity_and_deduplicates() -> None:
    redis = FakeRedis()
    publisher = RedisEventPublisher(redis)
    payload = {
        "content_id": "42",
        "run_id": "run-v2",
        "revision": 2,
    }

    publisher("content.analyzed", payload, "content.analyzed:run-v2")
    publisher("content.analyzed", payload, "content.analyzed:run-v2")

    assert len(redis.items) == 1
    assert json.loads(redis.items[0]) == {
        "topic": "content.analyzed",
        "payload": payload,
        "idempotency_key": "content.analyzed:run-v2",
    }
