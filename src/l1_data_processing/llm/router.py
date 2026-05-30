from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ModelRouter:
    tiers: dict[str, str] = field(
        default_factory=lambda: {
            "cheap": "fake-cheap",
            "standard": "fake-standard",
            "embed": "fake-embed",
        }
    )

    def model_for(self, tier: str) -> str:
        try:
            return self.tiers[tier]
        except KeyError as exc:
            raise ValueError(f"unknown model tier: {tier}") from exc
