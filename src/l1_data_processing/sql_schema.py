"""Only L1-owned tables. No foreign keys or writes into L0-owned tables."""
from __future__ import annotations

from sqlalchemy import (
    JSON, CheckConstraint, Column, DateTime, Index, Integer, MetaData, String,
    Table, Text, UniqueConstraint,
)

metadata = MetaData()

schema_migrations = Table(
    "l1_schema_migrations", metadata,
    Column("version", Integer, primary_key=True),
)

content_base_analysis = Table(
    "content_base_analysis", metadata,
    Column("schema_version", Integer, nullable=False),
    Column("content_id", String(255), primary_key=True),
    Column("input_snapshot", JSON, nullable=False),
    Column("analysis", JSON(none_as_null=True)),
    Column("graph_version", String(255), nullable=False),
    Column("content_hash", String(64), nullable=False),
    Column("run_id", String(64), nullable=False),
    Column("request_id", String(64), nullable=False),
    Column("status", String(32), nullable=False),
    Column("revision", Integer, nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    CheckConstraint("schema_version = 1", name="ck_l1_analysis_schema_version"),
    CheckConstraint("status IN ('WAIT_SCORE', 'FAILED', 'CANCELLED')", name="ck_l1_analysis_status"),
)

enrichment_cache = Table(
    "enrichment_cache", metadata,
    Column("content_hash", String(64), primary_key=True),
    Column("graph_version", String(255), primary_key=True),
    Column("analysis", JSON, nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

processing_runs = Table(
    "l1_processing_runs", metadata,
    Column("run_id", String(64), primary_key=True),
    Column("request_id", String(64), nullable=False),
    Column("attempt", Integer, nullable=False),
    Column("content_id", String(255), nullable=False),
    Column("graph_version", String(255), nullable=False),
    Column("content_hash", String(64), nullable=False),
    Column("input_hash", String(64), nullable=False),
    Column("input_snapshot", JSON, nullable=False),
    Column("reprocess_key", String(255)),
    Column("status", String(32), nullable=False),
    Column("analysis", JSON(none_as_null=True)),
    Column("cache_hit", Integer, nullable=False),
    Column("prompt_tokens", Integer, nullable=False),
    Column("completion_tokens", Integer, nullable=False),
    Column("cost_units", Integer, nullable=False),
    Column("llm_calls", Integer, nullable=False),
    Column("cost_complete", Integer, nullable=False),
    Column("traces", JSON, nullable=False),
    Column("error", Text),
    Column("started_at", DateTime(timezone=True), nullable=False),
    Column("finished_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("request_id", "attempt", name="uq_l1_run_request_attempt"),
    CheckConstraint("attempt >= 1", name="ck_l1_run_attempt"),
    CheckConstraint("status IN ('WAIT_SCORE', 'FAILED', 'CANCELLED')", name="ck_l1_run_status"),
)
Index("ix_l1_runs_content", processing_runs.c.content_id, processing_runs.c.finished_at)

outbox_events = Table(
    "l1_outbox_events", metadata,
    Column("event_id", String(100), primary_key=True),
    Column("run_id", String(64), nullable=False, unique=True),
    Column("topic", String(100), nullable=False),
    Column("aggregate_id", String(255), nullable=False),
    Column("payload", JSON, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("sent_at", DateTime(timezone=True)),
)
Index("ix_l1_outbox_pending", outbox_events.c.sent_at, outbox_events.c.created_at)

OWNED_TABLE_NAMES = tuple(metadata.tables)
