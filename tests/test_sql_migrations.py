from __future__ import annotations

from importlib.resources import files

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.schema import CreateTable

from l1_data_processing.migrations import downgrade, upgrade
from l1_data_processing.sql_schema import OWNED_TABLE_NAMES, metadata


def test_sql_migration_roundtrip_preserves_l0_and_unrelated_tables(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'migration.db'}")
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE content_items (id INTEGER PRIMARY KEY, title TEXT)")
        connection.exec_driver_sql("INSERT INTO content_items VALUES (1, 'L0 owned')")
        connection.exec_driver_sql("CREATE TABLE unrelated (id INTEGER PRIMARY KEY)")
    upgrade(engine)
    upgrade(engine)
    assert set(OWNED_TABLE_NAMES).issubset(inspect(engine).get_table_names())
    required = {"schema_version", "content_id", "input_snapshot", "analysis", "graph_version",
                "content_hash", "run_id", "status", "updated_at"}
    assert required.issubset({column["name"] for column in inspect(engine).get_columns("content_base_analysis")})
    downgrade(engine)
    assert set(inspect(engine).get_table_names()) == {"content_items", "unrelated"}
    with engine.connect() as connection:
        assert connection.exec_driver_sql("SELECT title FROM content_items WHERE id=1").scalar_one() == "L0 owned"
    upgrade(engine)
    assert set(OWNED_TABLE_NAMES).issubset(inspect(engine).get_table_names())
    engine.dispose()


def test_migration_refuses_unmanaged_colliding_table(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'unmanaged.db'}")
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE content_base_analysis (legacy_id INTEGER)")
    with pytest.raises(RuntimeError, match="unmanaged"):
        upgrade(engine)
    with pytest.raises(RuntimeError, match="unmanaged"):
        downgrade(engine)
    assert inspect(engine).get_table_names() == ["content_base_analysis"]
    engine.dispose()


@pytest.mark.parametrize("dialect", [sqlite.dialect(), postgresql.dialect()], ids=["sqlite", "postgresql"])
def test_packaged_sql_matches_the_dialect_schema(dialect):
    script = files("l1_data_processing.migrations").joinpath(f"0001_{dialect.name}.up.sql").read_text()
    normalized_script = " ".join(script.split())
    for table in metadata.sorted_tables:
        compiled_table = " ".join(str(CreateTable(table).compile(dialect=dialect)).split())
        assert compiled_table in normalized_script
    assert "INSERT INTO l1_schema_migrations (version) VALUES (1)" in script


def test_migration_ddl_error_rolls_back_sqlite_schema(tmp_path, monkeypatch):
    from l1_data_processing import migrations

    engine = create_engine(f"sqlite:///{tmp_path / 'broken.db'}")
    original_script = migrations._script

    def broken_script(dialect, direction):
        return original_script(dialect, direction) + "; THIS IS INVALID SQL;"

    monkeypatch.setattr(migrations, "_script", broken_script)
    with pytest.raises(Exception):
        upgrade(engine)
    assert inspect(engine).get_table_names() == []
    engine.dispose()
