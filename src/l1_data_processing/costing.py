from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Protocol

from l1_data_processing.contracts import UsageTrace


@dataclass(frozen=True)
class CostRecord:
    content_id: str
    graph_version: str
    prompt_tokens: int
    completion_tokens: int
    cost_units: int
    model_names: list[str]
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    alert: str | None = None

    @property
    def day(self) -> date:
        return self.created_at.date()


class CostLedger(Protocol):
    def record(self, record: CostRecord) -> CostRecord:
        """Record or replace cost by content_id."""

    def total_for_day(self, target_day: date) -> int:
        """Return total cost units for a day."""

    def alerts(self) -> list[CostRecord]:
        """Return records that exceeded the configured threshold."""


class InMemoryCostLedger:
    def __init__(self) -> None:
        self._records: dict[str, CostRecord] = {}

    def record(self, record: CostRecord) -> CostRecord:
        self._records[record.content_id] = record
        return record

    def total_for_day(self, target_day: date) -> int:
        return sum(record.cost_units for record in self._records.values() if record.day == target_day)

    def alerts(self) -> list[CostRecord]:
        return [record for record in self._records.values() if record.alert is not None]

    def get(self, content_id: str) -> CostRecord | None:
        return self._records.get(content_id)


def summarize_trace_cost(content_id: str, *, graph_version: str, traces: list[UsageTrace], alert_threshold: int) -> CostRecord:
    prompt_tokens = sum(trace.prompt_tokens for trace in traces)
    completion_tokens = sum(trace.completion_tokens for trace in traces)
    cost_units = prompt_tokens + completion_tokens
    model_names: list[str] = []
    seen: set[str] = set()
    for trace in traces:
        if trace.model not in seen:
            seen.add(trace.model)
            model_names.append(trace.model)
    alert = None
    if cost_units > alert_threshold:
        alert = f"cost_units {cost_units} exceeded threshold {alert_threshold}"
    return CostRecord(
        content_id=content_id,
        graph_version=graph_version,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        cost_units=cost_units,
        model_names=model_names,
        alert=alert,
    )
