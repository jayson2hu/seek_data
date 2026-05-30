from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from l1_data_processing.contracts import ContentInput


class StubContentProvider:
    def __init__(self, fixture_dir: Path | None = None) -> None:
        self.fixture_dir = fixture_dir or Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "content"

    def get(self, content_id: str) -> ContentInput:
        fixture_path = self.fixture_dir / f"{content_id}.json"
        if not fixture_path.exists():
            raise KeyError(f"content fixture not found: {content_id}")

        payload = json.loads(fixture_path.read_text(encoding="utf-8"))
        return self._from_payload(payload)

    @staticmethod
    def _from_payload(payload: dict[str, Any]) -> ContentInput:
        published_at = payload.get("published_at")
        return ContentInput(
            content_id=payload["content_id"],
            title=payload["title"],
            body=payload["body"],
            source_url=payload.get("source_url"),
            author=payload.get("author"),
            published_at=datetime.fromisoformat(published_at) if published_at else None,
            metadata=payload.get("metadata", {}),
        )
