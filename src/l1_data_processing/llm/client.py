from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class LLMResponse:
    text: str
    data: dict[str, Any]
    prompt_tokens: int = 0
    completion_tokens: int = 0
    model: str = "fake"


class LLMClient(Protocol):
    def complete(self, prompt: str, *, model: str) -> LLMResponse:
        """Return free-form completion text."""

    def structured(self, prompt: str, *, schema_name: str, model: str) -> LLMResponse:
        """Return schema-shaped data."""

    def embed(self, text: str, *, model: str) -> list[float]:
        """Return embedding vector."""
