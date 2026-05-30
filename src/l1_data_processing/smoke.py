from __future__ import annotations

from l1_data_processing.graph import run_enrichment
from l1_data_processing.input import StubContentProvider
from l1_data_processing.llm import FakeLLM


def main() -> None:
    analysis = run_enrichment("demo-article", provider=StubContentProvider(), llm=FakeLLM())
    analysis.validate()
    print(f"L1 PIPELINE: PASS content_id={analysis.content_id} traces={len(analysis.traces)}")


if __name__ == "__main__":
    main()
