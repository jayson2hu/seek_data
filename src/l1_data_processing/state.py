from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from l1_data_processing.contracts import BaseAnalysis, ContentInput, UsageTrace


GRAPH_VERSION = "l1.graph.v0"


@dataclass
class GraphState:
    content_id: str
    graph_version: str = GRAPH_VERSION
    content: ContentInput | None = None
    text: str = ""
    lang: str | None = None
    intermediate: dict[str, Any] = field(default_factory=dict)
    cost: dict[str, int] = field(default_factory=lambda: {"prompt_tokens": 0, "completion_tokens": 0})
    traces: list[UsageTrace] = field(default_factory=list)
    analysis: BaseAnalysis | None = None
    status: str = "PENDING"
    cancel_reason: str | None = None

    def add_trace(self, trace: UsageTrace) -> None:
        self.traces.append(trace)
        self.cost["prompt_tokens"] += trace.prompt_tokens
        self.cost["completion_tokens"] += trace.completion_tokens

    def to_dict(self) -> dict[str, Any]:
        return {
            "content_id": self.content_id,
            "graph_version": self.graph_version,
            "content": None
            if self.content is None
            else {
                "content_id": self.content.content_id,
                "title": self.content.title,
                "body": self.content.body,
                "source_url": self.content.source_url,
                "author": self.content.author,
                "published_at": self.content.published_at.isoformat() if self.content.published_at else None,
                "metadata": self.content.metadata,
            },
            "text": self.text,
            "lang": self.lang,
            "intermediate": self.intermediate,
            "cost": self.cost,
            "traces": [trace.to_dict() for trace in self.traces],
            "analysis": self.analysis.to_dict() if self.analysis else None,
            "status": self.status,
            "cancel_reason": self.cancel_reason,
        }
