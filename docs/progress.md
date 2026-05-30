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

### F2.1 GraphState Definition

- Status: done
- Evidence: `l1_data_processing.state.GraphState` and `tests/test_graph_state.py`.
- Acceptance: state serializes to plain dictionaries and accumulates traces/token cost across nodes.

### F2.2 Graph Assembly + enrich()

- Status: done
- Evidence: `l1_data_processing.graph.enrich` plus explicit load, analysis, embedding, and placeholder persistence nodes.
- Acceptance: `enrich(content_id)` runs the standalone path end to end and returns a completed `GraphState` with a valid analysis artifact.

### F3.1 clean_normalize Node

- Status: done
- Evidence: `l1_data_processing.text.clean_normalize_text`, `clean_normalize_node`, and `tests/test_clean_normalize.py`.
- Acceptance: HTML tags/entities and extra whitespace are normalized; graph state records character, word, and paragraph counts.

### F3.2 Initial Filter Node

- Status: done
- Evidence: `filter_node`, `ContentFilter` FakeLLM preset support, and `tests/test_filter_node.py`.
- Acceptance: obvious low-quality/marketing content can be marked `CANCELLED`; cancelled state short-circuits expensive base analysis and embedding nodes.
