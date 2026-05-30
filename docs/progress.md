# L1 Progress Log

## 2026-05-30

### F0.1 Service Scaffold

- Status: done
- Evidence: `src/l1_data_processing` package, `pyproject.toml`, `Makefile`, pytest configuration.
- Acceptance: importable package and runnable test entrypoints are present.

### F0.2 LLMClient + ModelRouter + FakeLLM

- Status: done
- Evidence: `l1_data_processing.llm` module and `tests/test_llm.py`.
- Acceptance: tier routing is configurable and `FakeLLM` can replace a real client without business code changes.

### F1.1 ContentProvider Abstraction

- Status: done
- Evidence: `l1_data_processing.input` module, fixture content, and `tests/test_content_provider.py`.
- Acceptance: graph code depends on the `ContentProvider` protocol; `StubContentProvider` reads fixtures.

### Minimal Graph Smoke

- Status: done
- Evidence: `l1_data_processing.graph`, `l1_data_processing.smoke`, and `tests/test_graph_smoke.py`.
- Acceptance: standalone stub + fake LLM path produces a schema-valid `BaseAnalysis` and smoke prints `L1 PIPELINE: PASS`.
