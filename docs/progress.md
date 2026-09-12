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

### F1.3 content.ingested Consumer

- Status: done
- Evidence: `l1_data_processing.consumer.consume_content_ingested`, `CONTENT_INGESTED`, and `tests/test_consumer.py`.
- Acceptance: `content.ingested` events validate topic and payload, trigger `enrich(content_id)`, pass through graph version/reprocess controls, and remain idempotent with cache and outbox injection.

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

### F4.1 Length Branch

- Status: done
- Evidence: `GraphConfig`, `branch_by_length_node`, and `tests/test_length_branch.py`.
- Acceptance: short content routes to `full`, long content routes to `split`, and the threshold is configurable.

### F4.2 Chunk Map + Aggregate

- Status: done
- Evidence: `split_text_into_chunks`, `analyze_chunk_node`, `aggregate_chunks_node`, FakeLLM sequenced responses, and `tests/test_chunk_aggregation.py`.
- Acceptance: long content is split into chunks, each chunk is analyzed deterministically, and aggregation preserves each chunk's marker key point without duplicates.

### F5.1 Structured Extraction Schema

- Status: done
- Evidence: `l1_data_processing.schema`, `build_base_analysis`, and `tests/test_base_analysis_schema.py`.
- Acceptance: `BaseAnalysis` payloads must satisfy required non-empty fields, typed string lists, optional empty quotes, numeric embeddings, and schema-normalized output.

### F5.2 Validation Retry and Fallback

- Status: done
- Evidence: `request_valid_structured`, `GraphConfig.structured_max_attempts`, and `tests/test_structured_retry.py`.
- Acceptance: invalid structured payloads trigger retry; repeated failures mark state `FAILED`, record schema errors, skip embedding/persistence, and do not create a polluted `BaseAnalysis`.

### F6.1 Embedding

- Status: done
- Evidence: `embedding_input_text`, dimension validation in `embedding_node`, stable FakeLLM bag-of-words embeddings, and `tests/test_embedding.py`.
- Acceptance: embeddings are generated from `title + summary`, dimension mismatches fail fast, and similar content ranks closer than unrelated content by cosine similarity.

### F6.2 Language Detection + Base Tags

- Status: done
- Evidence: `l1_data_processing.tagging`, `language_and_tags_node`, `BaseAnalysis.lang`, and `tests/test_tagging.py`.
- Acceptance: Chinese and English samples are classified as `zh`/`en`; base tags are normalized to a general controlled vocabulary and vertical-specific tags are filtered out.

### F7.1 Write content_base_analysis

- Status: done
- Evidence: `ContentBaseAnalysisRecord`, `InMemoryContentBaseAnalysisRepository`, repository injection in `enrich`, and `tests/test_persistence.py`.
- Acceptance: completed artifacts are persisted with graph version, model names, token/cost fields, and repeated processing upserts by `content_id` without duplicate rows.

### F7.2 Content Status Transitions

- Status: done
- Evidence: `ContentStatusMachine`, status integration in `enrich`, and `tests/test_status_machine.py`.
- Acceptance: success transitions `WAIT_ANALYSIS -> WAIT_SCORE`, filtered content transitions `WAIT_ANALYSIS -> CANCELLED`, and illegal transitions from terminal states are rejected.

### F7.3 content.analyzed Outbox

- Status: done
- Evidence: `OutboxEvent`, `InMemoryOutbox`, `content_analyzed_event`, outbox injection in `enrich`, and `tests/test_outbox.py`.
- Acceptance: completed content writes exactly one `content.analyzed` event by content_id, repeated processing is idempotent, relay marks events as sent, and cancelled content does not emit analyzed events.

### F8.1 Model Routing by Tier

- Status: done
- Evidence: `GraphConfig.model_tiers`, `ModelRouter(config.model_tiers)` in `enrich`, and `tests/test_model_routing.py`.
- Acceptance: filter, analysis, and embedding nodes use their configured model tiers; changing configuration switches models without graph code changes.

### F8.2 Cost Metering and Alerts

- Status: done
- Evidence: `CostRecord`, `InMemoryCostLedger`, `summarize_trace_cost`, cost ledger injection in `enrich`, and `tests/test_costing.py`.
- Acceptance: each completed content records prompt/completion token cost, daily cost is aggregatable, and records exceeding `GraphConfig.cost_alert_threshold_units` produce alerts.

### F9.1 enrichment_cache

- Status: done
- Evidence: `EnrichmentCacheEntry`, `InMemoryEnrichmentCache`, content hash cache lookup/store in `enrich`, and `tests/test_enrichment_cache.py`.
- Acceptance: identical normalized content with the same graph version hits cache on the second run and performs zero LLM calls while still returning a completed analysis.

### F9.2 Reprocess and Version Invalidation

- Status: done
- Evidence: `graph_version` and `reprocess` inputs on `enrich`, reprocess cache bypass, versioned cache keys, and `tests/test_enrichment_cache.py`.
- Acceptance: upgrading graph version creates a new cache key and reruns processing; explicit reprocess bypasses same-version cache and reruns LLM work.

### E10 DoD Smoke

- Status: done
- Evidence: `l1_data_processing.dod`, upgraded `l1_data_processing.smoke`, `make l1-dod`, and `tests/test_dod.py`.
- Acceptance: one command verifies standalone execution, cache hit, reprocess, filter cancellation, long-content split, persistence/outbox/status/cost side effects, and prints `L1 DOD: PASS`.

### Final Documentation

- Status: done
- Evidence: `docs/issues.md` and `docs/acceptance.md`.
- Acceptance: development issues are recorded with resolutions, and final acceptance evidence lists reproducible commands, latest results, DoD coverage, and integration notes.
