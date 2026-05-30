import pytest

from l1_data_processing.graph import run_enrichment
from l1_data_processing.input import StubContentProvider
from l1_data_processing.llm import FakeLLM


@pytest.mark.graph
def test_run_enrichment_with_stub_and_fake_llm() -> None:
    llm = FakeLLM()
    analysis = run_enrichment("demo-article", provider=StubContentProvider(), llm=llm)

    assert analysis.content_id == "demo-article"
    assert analysis.status == "COMPLETED"
    assert analysis.one_liner
    assert analysis.summary
    assert analysis.key_points
    assert len(analysis.embedding) == 8
    assert [trace.node for trace in analysis.traces] == ["base_analysis", "embedding"]
    assert llm.calls["structured"] == 1
    assert llm.calls["embed"] == 1
