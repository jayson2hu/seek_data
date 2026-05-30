from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol

from l1_data_processing.contracts import BaseAnalysis


@dataclass(frozen=True)
class EnrichmentCacheEntry:
    content_hash: str
    graph_version: str
    analysis: BaseAnalysis
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class EnrichmentCache(Protocol):
    def get(self, content_hash: str, graph_version: str) -> EnrichmentCacheEntry | None:
        """Return cached analysis by content hash and graph version."""

    def set(self, entry: EnrichmentCacheEntry) -> EnrichmentCacheEntry:
        """Store cache entry."""

    def count(self) -> int:
        """Return cache entry count."""


class InMemoryEnrichmentCache:
    def __init__(self) -> None:
        self._entries: dict[tuple[str, str], EnrichmentCacheEntry] = {}

    def get(self, content_hash: str, graph_version: str) -> EnrichmentCacheEntry | None:
        return self._entries.get((content_hash, graph_version))

    def set(self, entry: EnrichmentCacheEntry) -> EnrichmentCacheEntry:
        self._entries[(entry.content_hash, entry.graph_version)] = entry
        return entry

    def count(self) -> int:
        return len(self._entries)


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
