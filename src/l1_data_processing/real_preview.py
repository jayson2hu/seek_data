from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from l1_data_processing.config import GraphConfig
from l1_data_processing.durable import process_content
from l1_data_processing.input import L0ContentProvider
from l1_data_processing.llm import DeterministicExtractiveLLM, ExtractiveContentProvider
from l1_data_processing.llm.router import ModelRouter
from l1_data_processing.sql_store import SqlAlchemyEnrichmentStore


def _ensure_sqlite_parent(database_url: str) -> None:
    if database_url.startswith("sqlite:///") and not database_url.endswith(":memory:"):
        Path(database_url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)


def _content_ids(session: Session, requested: list[str] | None) -> list[str]:
    if requested:
        return requested
    from core_data.query.api import list_contents

    ids: list[str] = []
    cursor: str | None = None
    while True:
        page = list_contents(
            session,
            status="WAIT_FILTER",
            since=None,
            limit=500,
            cursor=cursor,
        )
        ids.extend(str(item.id) for item in page.items)
        cursor = page.next_cursor
        if cursor is None:
            return ids


def run(
    *,
    l0_database_url: str,
    l0_object_store: Path,
    l1_database_url: str,
    report_path: Path,
    requested_content_ids: list[str] | None = None,
) -> dict[str, Any]:
    from core_data.storage.object_store import FileObjectStore

    _ensure_sqlite_parent(l1_database_url)
    l0_engine = create_engine(l0_database_url)
    l1_engine = create_engine(l1_database_url)
    store = SqlAlchemyEnrichmentStore(l1_engine)
    store.create_schema()
    llm = DeterministicExtractiveLLM()
    router = ModelRouter(
        {
            "cheap": "extractive-filter-v3",
            "standard": "extractive-v3",
            "embed": "extractive-hash-v1",
        }
    )
    config = GraphConfig(
        split_threshold_chars=1_000_000,
        model_tiers={
            "cheap": "extractive-filter-v3",
            "standard": "extractive-v3",
            "embed": "extractive-hash-v1",
        }
    )
    processed: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []

    try:
        with Session(l0_engine) as l0_session:
            base_provider = L0ContentProvider.from_session(
                l0_session,
                FileObjectStore(l0_object_store),
            )
            provider = ExtractiveContentProvider(base_provider)
            content_ids = _content_ids(l0_session, requested_content_ids)
            for content_id in content_ids:
                try:
                    result = process_content(
                        content_id,
                        store=store,
                        provider=provider,
                        llm=llm,
                        graph_version=DeterministicExtractiveLLM.method,
                        config=config,
                        router=router,
                    )
                    if result.status != "WAIT_SCORE" or result.analysis is None:
                        failures.append(
                            {
                                "content_id": content_id,
                                "error": result.error or f"unexpected status: {result.status}",
                            }
                        )
                        continue
                    row = store.get(content_id)
                    if row is None:
                        raise RuntimeError("committed result is missing")
                    snapshot = row["input_snapshot"]
                    metadata = snapshot.get("metadata", {})
                    source = metadata.get("source", {})
                    processed.append(
                        {
                            "content_id": content_id,
                            "run_id": result.run_id,
                            "revision": row["revision"],
                            "replayed": result.replayed,
                            "cache_hit": result.cache_hit,
                            "title": snapshot.get("title"),
                            "source_name": source.get("name"),
                            "source_url": snapshot.get("source_url"),
                            "published_at": snapshot.get("published_at"),
                            "processing": metadata.get("processing"),
                            "summary": result.analysis["summary"],
                            "key_points": result.analysis["key_points"],
                            "tags": result.analysis["base_tags"],
                        }
                    )
                except Exception as exc:
                    failures.append(
                        {"content_id": content_id, "error": f"{type(exc).__name__}: {exc}"}
                    )
    finally:
        l0_engine.dispose()
        l1_engine.dispose()

    source_names = {
        item["source_name"] for item in processed if isinstance(item.get("source_name"), str)
    }
    report = {
        "schema_version": 1,
        "kind": "codepick-l1-extractive-public-preview",
        "created_at": datetime.now(UTC).isoformat(),
        "l0_database_url": l0_database_url,
        "l0_object_store": str(l0_object_store),
        "l1_database_url": l1_database_url,
        "processing": {
            "method": DeterministicExtractiveLLM.method,
            "provider": DeterministicExtractiveLLM.model,
            "model": None,
            "generated": False,
            "translation": False,
            "scoring": False,
        },
        "totals": {
            "requested": len(processed) + len(failures),
            "processed": len(processed),
            "replayed": sum(bool(item["replayed"]) for item in processed),
            "failed": len(failures),
            "sources": len(source_names),
        },
        "items": processed,
        "failures": failures,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if not processed:
        raise RuntimeError(f"extractive preview produced no L1 snapshots; inspect {report_path}")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Build durable extractive L1 snapshots from L0")
    parser.add_argument("--l0-database-url", required=True)
    parser.add_argument("--l0-object-store", type=Path, required=True)
    parser.add_argument("--l1-database-url", required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--content-id", action="append", dest="content_ids")
    args = parser.parse_args()
    report = run(
        l0_database_url=args.l0_database_url,
        l0_object_store=args.l0_object_store,
        l1_database_url=args.l1_database_url,
        report_path=args.report,
        requested_content_ids=args.content_ids,
    )
    print(
        "L1 EXTRACTIVE PREVIEW: "
        f"processed={report['totals']['processed']}/"
        f"{report['totals']['requested']} "
        f"sources={report['totals']['sources']} "
        f"failed={report['totals']['failed']}"
    )


if __name__ == "__main__":
    main()
