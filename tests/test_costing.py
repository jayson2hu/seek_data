from datetime import UTC, datetime

from l1_data_processing.config import GraphConfig
from l1_data_processing.costing import InMemoryCostLedger, summarize_trace_cost
from l1_data_processing.contracts import UsageTrace
from l1_data_processing.graph import enrich
from l1_data_processing.input import StubContentProvider
from l1_data_processing.llm import FakeLLM


def test_summarize_trace_cost_records_tokens_models_and_alerts() -> None:
    traces = [
        UsageTrace("filter", "small", 10, 3, 1),
        UsageTrace("analysis", "middle", 20, 9, 1),
        UsageTrace("embedding", "embed", 4, 0, 1),
    ]

    record = summarize_trace_cost("cid", graph_version="v1", traces=traces, alert_threshold=40)

    assert record.prompt_tokens == 34
    assert record.completion_tokens == 12
    assert record.cost_units == 46
    assert record.model_names == ["small", "middle", "embed"]
    assert record.alert == "cost_units 46 exceeded threshold 40"


def test_cost_ledger_accumulates_daily_cost_and_alerts() -> None:
    ledger = InMemoryCostLedger()
    first = summarize_trace_cost("a", graph_version="v1", traces=[UsageTrace("n", "m", 3, 2, 1)], alert_threshold=10)
    second = summarize_trace_cost("b", graph_version="v1", traces=[UsageTrace("n", "m", 8, 5, 1)], alert_threshold=10)

    ledger.record(first)
    ledger.record(second)

    assert ledger.total_for_day(datetime.now(UTC).date()) == 18
    assert ledger.alerts() == [second]


def test_enrich_records_per_content_cost_and_alert() -> None:
    ledger = InMemoryCostLedger()

    state = enrich(
        "demo-article",
        provider=StubContentProvider(),
        llm=FakeLLM(),
        config=GraphConfig(cost_alert_threshold_units=1),
        cost_ledger=ledger,
    )

    record = ledger.get("demo-article")
    assert record is not None
    assert record.cost_units == state.cost["prompt_tokens"] + state.cost["completion_tokens"]
    assert record.alert is not None
    assert state.intermediate["cost_record"]["alert"] == record.alert
