"""Transactional L1 storage for SQLite and PostgreSQL."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Engine, Connection, insert, select, update
from sqlalchemy.exc import IntegrityError, OperationalError

from l1_data_processing.sql_schema import (
    content_base_analysis, enrichment_cache, outbox_events, processing_runs,
)


class ConcurrentProcessingError(RuntimeError):
    """A newer committed revision won. Reload input before retrying."""


class RequestConflictError(ValueError):
    """A caller reused a reprocess key for different input or graph versions."""


@dataclass(frozen=True)
class DurableOutboxEvent:
    event_id: str
    run_id: str
    topic: str
    aggregate_id: str
    payload: dict[str, Any]
    created_at: datetime
    sent_at: datetime | None


class SqlAlchemyEnrichmentStore:
    def __init__(self, engine: Engine) -> None:
        if engine.dialect.name not in {"sqlite", "postgresql"}:
            raise ValueError("L1 durable storage supports SQLite and PostgreSQL")
        self.engine = engine

    def create_schema(self) -> None:
        from l1_data_processing.migrations import upgrade

        upgrade(self.engine)

    def get(self, content_id: str) -> dict[str, Any] | None:
        with self.engine.connect() as connection:
            row = connection.execute(select(content_base_analysis).where(
                content_base_analysis.c.content_id == content_id,
            )).mappings().first()
            return dict(row) if row is not None else None

    def latest_run(self, request_id: str) -> dict[str, Any] | None:
        with self.engine.connect() as connection:
            row = connection.execute(select(processing_runs).where(
                processing_runs.c.request_id == request_id,
            ).order_by(processing_runs.c.attempt.desc()).limit(1)).mappings().first()
            return dict(row) if row is not None else None

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        with self.engine.connect() as connection:
            row = connection.execute(select(processing_runs).where(
                processing_runs.c.run_id == run_id,
            )).mappings().first()
            return dict(row) if row is not None else None

    def runs(self, content_id: str | None = None) -> list[dict[str, Any]]:
        statement = select(processing_runs).order_by(
            processing_runs.c.started_at, processing_runs.c.attempt,
        )
        if content_id is not None:
            statement = statement.where(processing_runs.c.content_id == content_id)
        with self.engine.connect() as connection:
            return [dict(row) for row in connection.execute(statement).mappings()]

    def cached_analysis(self, content_hash: str, graph_version: str) -> dict[str, Any] | None:
        with self.engine.connect() as connection:
            return connection.execute(select(enrichment_cache.c.analysis).where(
                enrichment_cache.c.content_hash == content_hash,
                enrichment_cache.c.graph_version == graph_version,
            )).scalar_one_or_none()

    def pending_events(self) -> list[DurableOutboxEvent]:
        with self.engine.connect() as connection:
            rows = connection.execute(select(outbox_events).where(
                outbox_events.c.sent_at.is_(None),
            ).order_by(outbox_events.c.created_at, outbox_events.c.event_id)).mappings()
            return [DurableOutboxEvent(**row) for row in rows]

    def relay_once(self, publisher: Callable[[str, dict[str, Any], str], None]) -> int:
        """At-least-once delivery: the receiver must deduplicate event_id.

        A failed callback leaves its event pending. A crash after acceptance and
        before this database commit may redeliver with the identical event_id.
        """
        count = 0
        for event in self.pending_events():
            publisher(event.topic, event.payload, event.event_id)
            with self.engine.begin() as connection:
                result = connection.execute(update(outbox_events).where(
                    outbox_events.c.event_id == event.event_id,
                    outbox_events.c.sent_at.is_(None),
                ).values(sent_at=datetime.now(UTC)))
                count += result.rowcount
        return count

    def commit_run(
        self, run: dict[str, Any], *, expected_revision: int | None,
    ) -> dict[str, Any]:
        """Commit the run, visible result, cache and notification as one unit.

        The optimistic revision is captured BEFORE model work. A stale worker
        cannot replace a newer result. Concurrent duplicate successes are read
        from the winner's committed run after rollback.
        """
        try:
            with self.engine.begin() as connection:
                values = {
                    "schema_version": 1,
                    "content_id": run["content_id"],
                    "input_snapshot": run["input_snapshot"],
                    "analysis": run["analysis"],
                    "graph_version": run["graph_version"],
                    "content_hash": run["content_hash"],
                    "run_id": run["run_id"],
                    "request_id": run["request_id"],
                    "status": run["status"],
                    "revision": (expected_revision or 0) + 1,
                    "updated_at": run["finished_at"],
                }
                if expected_revision is None:
                    connection.execute(insert(content_base_analysis).values(**values))
                else:
                    result = connection.execute(update(content_base_analysis).where(
                        content_base_analysis.c.content_id == run["content_id"],
                        content_base_analysis.c.revision == expected_revision,
                    ).values(**values))
                    if result.rowcount != 1:
                        raise ConcurrentProcessingError("content changed during processing")
                connection.execute(insert(processing_runs).values(**run))
                if run["status"] == "WAIT_SCORE" and run["analysis"] is not None:
                    self._save_cache(connection, run)
                    connection.execute(insert(outbox_events).values(
                        event_id=f"content.analyzed:{run['run_id']}",
                        run_id=run["run_id"], topic="content.analyzed",
                        aggregate_id=run["content_id"],
                        payload={
                            "schema_version": 1, "content_id": run["content_id"],
                            "run_id": run["run_id"], "graph_version": run["graph_version"],
                            "content_hash": run["content_hash"], "status": "WAIT_SCORE",
                            "analysis": run["analysis"],
                        },
                        created_at=run["finished_at"], sent_at=None,
                    ))
            return run
        except (IntegrityError, ConcurrentProcessingError) as exc:
            winner = self._accepted_winner(run)
            if winner is not None:
                return winner
            raise ConcurrentProcessingError(
                "another worker committed first; reload input and retry",
            ) from exc
        except OperationalError as exc:
            if self.engine.dialect.name == "sqlite" and "locked" in str(exc).lower():
                winner = self._accepted_winner(run)
                if winner is not None:
                    return winner
                raise ConcurrentProcessingError("SQLite writer busy; retry after reload") from exc
            raise

    def _accepted_winner(self, run: dict[str, Any]) -> dict[str, Any] | None:
        winner = self.latest_run(run["request_id"])
        self._check_winner_request(winner, run)
        if (
            winner is None or winner["status"] not in {"WAIT_SCORE", "CANCELLED"}
            or winner["attempt"] < run["attempt"]
        ):
            return None
        if run["reprocess_key"] is None:
            head = self.get(run["content_id"])
            if head is None or head["run_id"] != winner["run_id"]:
                return None
        return winner

    @staticmethod
    def _check_winner_request(winner: dict[str, Any] | None, run: dict[str, Any]) -> None:
        if winner is not None and (
            winner["input_hash"] != run["input_hash"]
            or winner["graph_version"] != run["graph_version"]
        ):
            raise RequestConflictError("reprocess_key concurrently used for different input/version")

    def _save_cache(self, connection: Connection, run: dict[str, Any]) -> None:
        if self.engine.dialect.name == "sqlite":
            from sqlalchemy.dialects.sqlite import insert as dialect_insert
        else:
            from sqlalchemy.dialects.postgresql import insert as dialect_insert
        statement = dialect_insert(enrichment_cache).values(
            content_hash=run["content_hash"], graph_version=run["graph_version"],
            analysis=run["analysis"], updated_at=run["finished_at"],
        )
        connection.execute(statement.on_conflict_do_update(
            index_elements=[enrichment_cache.c.content_hash, enrichment_cache.c.graph_version],
            set_={"analysis": statement.excluded.analysis, "updated_at": statement.excluded.updated_at},
        ))
