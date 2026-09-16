from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from xml.sax.saxutils import escape

from l1_data_processing.cache import InMemoryEnrichmentCache
from l1_data_processing.consumer import consume_content_ingested
from l1_data_processing.events import InMemoryOutbox, OutboxEvent
from l1_data_processing.input import L0ContentProvider
from l1_data_processing.llm import FakeLLM
from l1_data_processing.persistence import InMemoryContentBaseAnalysisRepository
from l1_data_processing.status import WAIT_SCORE, ContentStatusMachine


def run_l0_integration_checks() -> list[str]:
    """Exercise real L0 code/storage with local fixtures and L1's FakeLLM.

    Uses only a new temporary SQLite database and object directory. No runtime
    DATABASE_URL, external network, real model, or existing L0 data is used.
    L1 repositories and delivery remain in memory: this is a contract gate,
    not a persistent worker or production end-to-end acceptance.
    """
    from sqlalchemy import URL, create_engine, func, select
    from sqlalchemy.orm import Session

    from core_data.db.bootstrap import create_all
    from core_data.db.models import ContentItem, RawDocument
    from core_data.events.outbox import relay_once
    from core_data.ingest.pipeline import crawl_source
    from core_data.sources.repository import create_source
    from core_data.storage.object_store import FileObjectStore

    with TemporaryDirectory(prefix="codepick-l0-l1-") as temporary:
        root = Path(temporary)
        engine = create_engine(URL.create("sqlite", database=str(root / "l0.db")))
        try:
            create_all(engine)
            store = FileObjectStore(root / "objects")
            article = root / "article.html"
            article.write_text(
                "<html><head><title>CodePick integration</title></head><body><article>"
                "<h1>CodePick integration</h1><p>A reproducible local pipeline reads stored "
                "article text from the data foundation. Integer events reach enrichment "
                "without losing the content identity, and duplicate delivery reuses the "
                "analysis. This fixture does not make any external model requests.</p>"
                "</article></body></html>", encoding="utf-8",
            )
            feed = root / "feed.xml"
            feed.write_text(
                '<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel>'
                '<title>Integration feed</title><link>https://example.test</link>'
                '<description>Local fixture</description><item><title>CodePick integration</title>'
                f'<link>{escape(article.as_uri())}</link><guid>codepick-l0-l1</guid>'
                '</item></channel></rss>', encoding="utf-8",
            )
            with Session(engine) as session:
                source = create_source(session, name="Integration feed", feed_url=feed.as_uri())
                stats = crawl_source(session, store, source)
                session.commit()
                assert stats["content"] == 1 and stats["failed"] == 0, stats
                item = session.scalar(select(ContentItem))
                assert item is not None
                raw_count = session.scalar(select(func.count()).select_from(RawDocument))
                assert raw_count and item.clean_text_ref and store.exists(item.clean_text_ref)
                original_status = item.status
                provider = L0ContentProvider.from_session(session, store)
                cache = InMemoryEnrichmentCache()
                repository = InMemoryContentBaseAnalysisRepository()
                outbox = InMemoryOutbox()
                machine = ContentStatusMachine()
                delivered = []

                def deliver(topic, payload, key):
                    assert type(payload["content_id"]) is int
                    event = OutboxEvent(
                        event_id=key, topic=topic, aggregate_id=str(payload["content_id"]), payload=payload,
                    )
                    state = consume_content_ingested(
                        event, provider=provider, llm=FakeLLM(), repository=repository,
                        cache=cache, outbox=outbox, status_machine=machine,
                    )
                    assert state.status == "COMPLETED"
                    delivered.append(event)

                assert relay_once(session, deliver) == 1
                session.commit()
                assert repository.count() == 1 and outbox.count() == 1
                record = repository.get(str(item.id))
                assert record is not None and record.analysis.content_id == str(item.id)
                assert provider.get(str(item.id)).body == store.get_bytes(item.clean_text_ref).decode("utf-8")
                duplicate_llm = FakeLLM()
                replay = consume_content_ingested(
                    delivered[0], provider=provider, llm=duplicate_llm, repository=repository,
                    cache=cache, outbox=outbox, status_machine=machine,
                )
                assert replay.intermediate["cache"]["hit"] and not duplicate_llm.calls
                assert machine.get(str(item.id)) == WAIT_SCORE
                assert repository.count() == 1 and outbox.count() == 1
                session.refresh(item)
                assert item.status == original_status
                assert session.scalar(select(func.count()).select_from(RawDocument)) == raw_count
        finally:
            engine.dispose()
    return ["L0 ingestion", "stored content", "integer event", "L1 analysis", "duplicate delivery", "L0 read-only"]


def main() -> None:
    try:
        checks = run_l0_integration_checks()
    except ModuleNotFoundError as exc:
        if exc.name not in {"core_data", "sqlalchemy"}:
            raise
        raise SystemExit("Install the sibling L0 package first: python -m pip install -e ../deepdata") from exc
    print(f"L0 -> L1 CONTRACT: PASS checks={','.join(checks)}")


if __name__ == "__main__":
    main()
