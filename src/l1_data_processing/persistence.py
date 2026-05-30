from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol

from l1_data_processing.contracts import BaseAnalysis


@dataclass(frozen=True)
class ContentBaseAnalysisRecord:
    content_id: str
    analysis: BaseAnalysis
    graph_version: str
    prompt_tokens: int
    completion_tokens: int
    cost_units: int
    model_names: list[str]
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, object]:
        return {
            "content_id": self.content_id,
            "analysis": self.analysis.to_dict(),
            "graph_version": self.graph_version,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "cost_units": self.cost_units,
            "model_names": self.model_names,
            "updated_at": self.updated_at.isoformat(),
        }


class ContentBaseAnalysisRepository(Protocol):
    def upsert(self, record: ContentBaseAnalysisRecord) -> ContentBaseAnalysisRecord:
        """Insert or replace by content_id."""

    def get(self, content_id: str) -> ContentBaseAnalysisRecord | None:
        """Return a record by content_id."""

    def count(self) -> int:
        """Return persisted row count."""


class InMemoryContentBaseAnalysisRepository:
    def __init__(self) -> None:
        self._records: dict[str, ContentBaseAnalysisRecord] = {}

    def upsert(self, record: ContentBaseAnalysisRecord) -> ContentBaseAnalysisRecord:
        self._records[record.content_id] = record
        return record

    def get(self, content_id: str) -> ContentBaseAnalysisRecord | None:
        return self._records.get(content_id)

    def count(self) -> int:
        return len(self._records)
