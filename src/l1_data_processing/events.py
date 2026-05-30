from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol

from l1_data_processing.contracts import BaseAnalysis


CONTENT_ANALYZED = "content.analyzed"


@dataclass
class OutboxEvent:
    event_id: str
    topic: str
    aggregate_id: str
    payload: dict[str, object]
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    sent_at: datetime | None = None

    def mark_sent(self) -> None:
        self.sent_at = datetime.now(UTC)


class Outbox(Protocol):
    def add_once(self, event: OutboxEvent) -> OutboxEvent:
        """Insert event only once by event_id."""

    def unsent(self) -> list[OutboxEvent]:
        """Return unsent events."""

    def mark_sent(self, event_id: str) -> None:
        """Mark an event as relayed."""

    def count(self) -> int:
        """Return total events."""


class InMemoryOutbox:
    def __init__(self) -> None:
        self._events: dict[str, OutboxEvent] = {}

    def add_once(self, event: OutboxEvent) -> OutboxEvent:
        self._events.setdefault(event.event_id, event)
        return self._events[event.event_id]

    def unsent(self) -> list[OutboxEvent]:
        return [event for event in self._events.values() if event.sent_at is None]

    def mark_sent(self, event_id: str) -> None:
        self._events[event_id].mark_sent()

    def count(self) -> int:
        return len(self._events)

    def get(self, event_id: str) -> OutboxEvent | None:
        return self._events.get(event_id)


def content_analyzed_event(analysis: BaseAnalysis, *, graph_version: str) -> OutboxEvent:
    return OutboxEvent(
        event_id=f"{CONTENT_ANALYZED}:{analysis.content_id}",
        topic=CONTENT_ANALYZED,
        aggregate_id=analysis.content_id,
        payload={
            "content_id": analysis.content_id,
            "status": analysis.status,
            "lang": analysis.lang,
            "base_tags": analysis.base_tags,
            "graph_version": graph_version,
            "analysis": analysis.to_dict(),
        },
    )
