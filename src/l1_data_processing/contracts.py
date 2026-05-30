from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True)
class ContentInput:
    content_id: str
    title: str
    body: str
    source_url: str | None = None
    author: str | None = None
    published_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def normalized_text(self) -> str:
        return "\n\n".join(part.strip() for part in [self.title, self.body] if part.strip())


@dataclass(frozen=True)
class UsageTrace:
    node: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    elapsed_ms: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "node": self.node,
            "model": self.model,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "elapsed_ms": self.elapsed_ms,
        }


@dataclass(frozen=True)
class BaseAnalysis:
    content_id: str
    one_liner: str
    summary: str
    key_points: list[str]
    quotes: list[str]
    entities: list[str]
    base_tags: list[str]
    embedding: list[float]
    lang: str | None = None
    status: str = "COMPLETED"
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    traces: list[UsageTrace] = field(default_factory=list)

    def validate(self) -> None:
        if not self.content_id:
            raise ValueError("content_id is required")
        if not self.one_liner.strip():
            raise ValueError("one_liner is required")
        if not self.summary.strip():
            raise ValueError("summary is required")
        if not self.key_points:
            raise ValueError("key_points must not be empty")
        if not self.base_tags:
            raise ValueError("base_tags must not be empty")
        if not self.embedding:
            raise ValueError("embedding must not be empty")

    def to_dict(self) -> dict[str, Any]:
        return {
            "content_id": self.content_id,
            "one_liner": self.one_liner,
            "summary": self.summary,
            "key_points": self.key_points,
            "quotes": self.quotes,
            "entities": self.entities,
            "base_tags": self.base_tags,
            "embedding": self.embedding,
            "lang": self.lang,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "traces": [trace.to_dict() for trace in self.traces],
        }
