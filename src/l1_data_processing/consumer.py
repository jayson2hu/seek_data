from __future__ import annotations

from dataclasses import dataclass

from l1_data_processing.cache import EnrichmentCache
from l1_data_processing.config import GraphConfig
from l1_data_processing.costing import CostLedger
from l1_data_processing.events import Outbox, OutboxEvent
from l1_data_processing.graph import enrich
from l1_data_processing.input.provider import ContentProvider
from l1_data_processing.llm.client import LLMClient
from l1_data_processing.llm.router import ModelRouter
from l1_data_processing.persistence import ContentBaseAnalysisRepository
from l1_data_processing.state import GraphState
from l1_data_processing.status import ContentStatusMachine


CONTENT_INGESTED = "content.ingested"


@dataclass(frozen=True)
class ContentIngestedMessage:
    content_id: str
    content_version: int | None = None
    content_hash: str | None = None
    graph_version: str | None = None
    reprocess: bool = False


def parse_content_ingested(event: OutboxEvent) -> ContentIngestedMessage:
    if event.topic != CONTENT_INGESTED:
        raise ValueError(f"unsupported topic: {event.topic}")

    content_id = event.payload.get("content_id")
    # L0 emits positive integer database IDs; fixture IDs remain supported.
    # bool is an int subclass and must not become content 1 or 0.
    if type(content_id) is int and content_id > 0:
        content_id = str(content_id)
    elif not isinstance(content_id, str) or not content_id.strip():
        raise ValueError("content.ingested payload requires a positive integer or non-empty string content_id")

    graph_version = event.payload.get("graph_version")
    if graph_version is not None and not isinstance(graph_version, str):
        raise ValueError("content.ingested payload graph_version must be a string")

    reprocess = event.payload.get("reprocess", False)
    if not isinstance(reprocess, bool):
        raise ValueError("content.ingested payload reprocess must be a boolean")

    content_version = event.payload.get("content_version")
    if content_version is not None and (
        isinstance(content_version, bool)
        or not isinstance(content_version, int)
        or content_version < 1
    ):
        raise ValueError("content.ingested payload content_version must be a positive integer")

    content_hash = event.payload.get("content_hash")
    if content_hash is not None and (
        not isinstance(content_hash, str) or not content_hash.strip()
    ):
        raise ValueError("content.ingested payload content_hash must be a non-empty string")

    return ContentIngestedMessage(
        content_id=content_id.strip(),
        content_version=content_version,
        content_hash=content_hash.strip() if content_hash is not None else None,
        graph_version=graph_version,
        reprocess=reprocess,
    )


def consume_content_ingested(
    event: OutboxEvent,
    *,
    provider: ContentProvider,
    llm: LLMClient,
    router: ModelRouter | None = None,
    config: GraphConfig | None = None,
    repository: ContentBaseAnalysisRepository | None = None,
    status_machine: ContentStatusMachine | None = None,
    outbox: Outbox | None = None,
    cost_ledger: CostLedger | None = None,
    cache: EnrichmentCache | None = None,
) -> GraphState:
    message = parse_content_ingested(event)
    return enrich(
        message.content_id,
        provider=provider,
        llm=llm,
        router=router,
        config=config,
        repository=repository,
        status_machine=status_machine,
        outbox=outbox,
        cost_ledger=cost_ledger,
        cache=cache,
        graph_version=message.graph_version,
        reprocess=message.reprocess,
    )
