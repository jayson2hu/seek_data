from __future__ import annotations

from dataclasses import dataclass, field


WAIT_ANALYSIS = "WAIT_ANALYSIS"
WAIT_SCORE = "WAIT_SCORE"
CANCELLED = "CANCELLED"
FAILED = "FAILED"

ALLOWED_TRANSITIONS = {
    WAIT_ANALYSIS: {WAIT_SCORE, CANCELLED, FAILED},
    WAIT_SCORE: set(),
    CANCELLED: set(),
    FAILED: set(),
}


class InvalidStatusTransition(ValueError):
    pass


@dataclass
class ContentStatusMachine:
    statuses: dict[str, str] = field(default_factory=dict)

    def initialize(self, content_id: str, status: str = WAIT_ANALYSIS) -> str:
        self.statuses.setdefault(content_id, status)
        return self.statuses[content_id]

    def transition(self, content_id: str, target: str) -> str:
        current = self.statuses.get(content_id, WAIT_ANALYSIS)
        if target not in ALLOWED_TRANSITIONS.get(current, set()):
            raise InvalidStatusTransition(f"invalid status transition: {current} -> {target}")
        self.statuses[content_id] = target
        return target

    def get(self, content_id: str) -> str:
        return self.statuses.get(content_id, WAIT_ANALYSIS)
