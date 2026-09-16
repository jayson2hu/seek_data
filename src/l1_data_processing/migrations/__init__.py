"""Versioned SQL migrations, restricted to tables owned by L1."""
from __future__ import annotations

from importlib.resources import files

from sqlalchemy import Engine, inspect, select

from l1_data_processing.sql_schema import OWNED_TABLE_NAMES, schema_migrations


def _script(dialect: str, direction: str) -> str:
    if dialect not in {"sqlite", "postgresql"}:
        raise ValueError("L1 migrations support SQLite and PostgreSQL")
    return files(__package__).joinpath(f"0001_{dialect}.{direction}.sql").read_text(encoding="utf-8")


def upgrade(engine: Engine) -> None:
    with engine.begin() as connection:
        existing = set(inspect(connection).get_table_names())
        if schema_migrations.name in existing:
            versions = connection.execute(select(schema_migrations.c.version)).scalars().all()
            if versions == [1] and set(OWNED_TABLE_NAMES).issubset(existing):
                return
            raise RuntimeError("unsupported or incomplete L1 schema; refusing automatic changes")
        conflicts = existing.intersection(OWNED_TABLE_NAMES)
        if conflicts:
            raise RuntimeError(f"unmanaged L1 tables already exist: {sorted(conflicts)}")
        # sqlite3 legacy mode does not automatically BEGIN for DDL. Explicitly
        # begin so a migration error rolls back the whole SQLite schema change.
        if engine.dialect.name == "sqlite" and not connection.connection.driver_connection.in_transaction:
            connection.exec_driver_sql("BEGIN")
        for statement in _script(engine.dialect.name, "up").split(";"):
            if statement.strip():
                connection.exec_driver_sql(statement)


def downgrade(engine: Engine) -> None:
    """Remove the L1 v1 schema only. Intended for disposable development DBs."""
    with engine.begin() as connection:
        existing = set(inspect(connection).get_table_names())
        if schema_migrations.name not in existing:
            if existing.intersection(OWNED_TABLE_NAMES):
                raise RuntimeError("unmanaged L1 tables exist; refusing to drop them")
            return
        versions = connection.execute(select(schema_migrations.c.version)).scalars().all()
        if versions != [1]:
            raise RuntimeError("unknown L1 schema version; refusing to downgrade")
        if engine.dialect.name == "sqlite" and not connection.connection.driver_connection.in_transaction:
            connection.exec_driver_sql("BEGIN")
        for statement in _script(engine.dialect.name, "down").split(";"):
            if statement.strip():
                connection.exec_driver_sql(statement)
