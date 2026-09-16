from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import TYPE_CHECKING, Protocol

from l1_data_processing.contracts import ContentInput

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from core_data.storage.object_store import ObjectStore


class L0Source(Protocol):
    id: int | None
    name: str | None


class L0Content(Protocol):
    id: int
    title: str | None
    clean_text: str
    canonical_url: str
    published_at: datetime | None
    lang: str | None
    status: str
    source: L0Source


class L0ContentProvider:
    """Read L0's frozen get_content contract without writing lower-layer data.

    A bound query callable keeps standalone L1 free of L0 dependencies.
    from_session binds a real L0 SQLAlchemy session and object store; callers
    own their lifetimes. It never falls back to fixtures when L0 fails.
    """

    def __init__(self, get_content: Callable[[int], L0Content]) -> None:
        self._get_content = get_content

    @classmethod
    def from_session(cls, session: Session, object_store: ObjectStore) -> L0ContentProvider:
        from core_data.query.api import get_content

        return cls(lambda content_id: get_content(session, object_store, content_id))

    def get(self, content_id: str) -> ContentInput:
        if (
            not isinstance(content_id, str)
            or not content_id.isascii()
            or not content_id.isdecimal()
            or int(content_id) <= 0
        ):
            raise ValueError("L0 content_id must be a positive decimal integer string")
        numeric_id = int(content_id)
        try:
            content = self._get_content(numeric_id)
        except LookupError as exc:
            raise KeyError(f"L0 content not found: {content_id}") from exc
        if content.id != numeric_id:
            raise ValueError("L0 returned a different content_id")
        if not content.clean_text.strip():
            raise ValueError("L0 content has no clean_text; title-only TREND enrichment is not supported")
        return ContentInput(
            content_id=content_id,
            title=content.title or "",
            body=content.clean_text,
            source_url=content.canonical_url,
            published_at=content.published_at,
            metadata={
                "lang": content.lang,
                "status": content.status,
                "source": {"id": content.source.id, "name": content.source.name},
            },
        )
