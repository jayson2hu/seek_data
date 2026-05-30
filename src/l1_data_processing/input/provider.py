from __future__ import annotations

from typing import Protocol

from l1_data_processing.contracts import ContentInput


class ContentProvider(Protocol):
    def get(self, content_id: str) -> ContentInput:
        """Return content by id or raise KeyError when unavailable."""
