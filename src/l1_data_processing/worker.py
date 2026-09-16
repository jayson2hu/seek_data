"""Continuously consume L0 version events into durable L1 processing."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from redis import Redis
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from l1_data_processing.durable import process_content_ingested
from l1_data_processing.events import OutboxEvent
from l1_data_processing.input import L0ContentProvider
from l1_data_processing.llm import FakeLLM
from l1_data_processing.sql_store import SqlAlchemyEnrichmentStore


def parse_envelope(raw: str | bytes) -> OutboxEvent:
    text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
    value = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError("event envelope must be an object")
    topic = value.get("topic")
    payload = value.get("payload")
    event_id = value.get("idempotency_key")
    if not isinstance(topic, str) or not topic:
        raise ValueError("event envelope topic is required")
    if not isinstance(payload, dict):
        raise ValueError("event envelope payload must be an object")
    if not isinstance(event_id, str) or not event_id:
        raise ValueError("event envelope idempotency_key is required")
    content_id = payload.get("content_id")
    return OutboxEvent(
        event_id=event_id,
        topic=topic,
        aggregate_id=str(content_id),
        payload={str(key): item for key, item in payload.items()},
    )


def recover_inflight(redis: Redis, queue: str, processing: str) -> int:
    recovered = 0
    while redis.rpoplpush(processing, queue) is not None:
        recovered += 1
    return recovered


def consume(
    *,
    l0_database_url: str,
    l0_object_store_path: str,
    l1_database_url: str,
    redis_url: str,
    queue: str,
    once: bool,
) -> int:
    from core_data.storage.object_store import FileObjectStore

    redis = Redis.from_url(redis_url, decode_responses=False)
    l0_engine = create_engine(l0_database_url)
    l1_engine = create_engine(l1_database_url)
    store = SqlAlchemyEnrichmentStore(l1_engine)
    object_store = FileObjectStore(Path(l0_object_store_path))
    processing = f"{queue}:processing"
    dead = f"{queue}:dead"
    handled = 0
    try:
        store.create_schema()
        recover_inflight(redis, queue, processing)
        while True:
            raw = redis.blmove(
                queue, processing, timeout=1, src="LEFT", dest="RIGHT"
            )
            if raw is None:
                if once:
                    return handled
                continue
            try:
                event = parse_envelope(raw)
                with Session(l0_engine) as session:
                    process_content_ingested(
                        event,
                        store=store,
                        provider=L0ContentProvider.from_session(
                            session, object_store
                        ),
                        llm=FakeLLM(),
                    )
            except (json.JSONDecodeError, ValueError):
                with redis.pipeline(transaction=True) as pipeline:
                    pipeline.lpush(dead, raw)
                    pipeline.lrem(processing, 1, raw)
                    pipeline.execute()
                if once:
                    return handled
                continue
            except Exception:
                with redis.pipeline(transaction=True) as pipeline:
                    pipeline.lrem(processing, 1, raw)
                    pipeline.rpush(queue, raw)
                    pipeline.execute()
                raise
            redis.lrem(processing, 1, raw)
            handled += 1
            if once:
                return handled
    finally:
        redis.close()
        l0_engine.dispose()
        l1_engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--l0-database-url",
        default=os.getenv("L0_DATABASE_URL"),
    )
    parser.add_argument(
        "--l0-object-store-path",
        default=os.getenv("L0_OBJECT_STORE_PATH"),
    )
    parser.add_argument(
        "--l1-database-url",
        default=os.getenv("L1_DATABASE_URL"),
    )
    parser.add_argument(
        "--redis-url",
        default=os.getenv("L1_REDIS_URL", "redis://127.0.0.1:6379/0"),
    )
    parser.add_argument(
        "--queue",
        default=os.getenv("L0_EVENT_QUEUE", "codepick:l0:events"),
    )
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    required = {
        "L0_DATABASE_URL": args.l0_database_url,
        "L0_OBJECT_STORE_PATH": args.l0_object_store_path,
        "L1_DATABASE_URL": args.l1_database_url,
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise SystemExit(f"missing required configuration: {', '.join(missing)}")
    handled = consume(
        l0_database_url=args.l0_database_url,
        l0_object_store_path=args.l0_object_store_path,
        l1_database_url=args.l1_database_url,
        redis_url=args.redis_url,
        queue=args.queue,
        once=args.once,
    )
    print(f"L1 EVENT CONSUMER: handled={handled}")


if __name__ == "__main__":
    main()
