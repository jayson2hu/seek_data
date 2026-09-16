"""Relay durable L1 events to the shared Redis event queue."""
from __future__ import annotations

import argparse
import json
import os
import time
from typing import Any, Protocol, cast

from redis import Redis
from sqlalchemy import create_engine

from l1_data_processing.sql_store import SqlAlchemyEnrichmentStore

_PUBLISH_LUA = """
if redis.call('EXISTS', KEYS[1]) == 1 then
    return 0
end
redis.call('RPUSH', KEYS[2], ARGV[1])
redis.call('SET', KEYS[1], '1', 'EX', ARGV[2])
return 1
"""


class RedisLike(Protocol):
    def eval(
        self, script: str, numkeys: int, *keys_and_args: str | int
    ) -> object: ...


class RedisEventPublisher:
    def __init__(
        self,
        redis_client: RedisLike,
        *,
        queue_name: str = "codepick:l1:events",
        key_prefix: str = "codepick:l1:published",
        ttl_sec: int = 7 * 24 * 3600,
    ) -> None:
        self.redis = redis_client
        self.queue_name = queue_name
        self.key_prefix = key_prefix
        self.ttl_sec = ttl_sec

    def __call__(
        self, topic: str, payload: dict[str, Any], event_id: str
    ) -> None:
        envelope = {
            "topic": topic,
            "payload": payload,
            "idempotency_key": event_id,
        }
        serialized = json.dumps(envelope, ensure_ascii=False, sort_keys=True)
        self.redis.eval(
            _PUBLISH_LUA,
            2,
            f"{self.key_prefix}:{event_id}",
            self.queue_name,
            serialized,
            self.ttl_sec,
        )


def relay_once_to_redis(
    database_url: str,
    redis_url: str,
    *,
    queue_name: str = "codepick:l1:events",
) -> int:
    engine = create_engine(database_url)
    try:
        store = SqlAlchemyEnrichmentStore(engine)
        client = cast(RedisLike, Redis.from_url(redis_url, decode_responses=True))
        return store.relay_once(
            RedisEventPublisher(
                client,
                queue_name=queue_name,
                key_prefix=f"{queue_name}:published",
            )
        )
    finally:
        engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--database-url",
        default=os.getenv("L1_DATABASE_URL"),
    )
    parser.add_argument(
        "--redis-url",
        default=os.getenv("L1_REDIS_URL", "redis://127.0.0.1:6379/0"),
    )
    parser.add_argument(
        "--queue-name",
        default=os.getenv("L1_EVENT_QUEUE", "codepick:l1:events"),
    )
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--poll-interval", type=float, default=1.0)
    args = parser.parse_args()
    if not args.database_url:
        raise SystemExit("L1_DATABASE_URL or --database-url is required")
    if args.poll_interval <= 0:
        raise SystemExit("--poll-interval must be positive")
    while True:
        count = relay_once_to_redis(
            args.database_url,
            args.redis_url,
            queue_name=args.queue_name,
        )
        print(f"L1 RELAY: published={count}")
        if args.once:
            return
        time.sleep(args.poll_interval)


if __name__ == "__main__":
    main()
