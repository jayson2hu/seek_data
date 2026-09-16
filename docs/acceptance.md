# L1 Acceptance Report

Date: 2026-06-01

## Scope

L1 data processing is implemented as a standalone, deterministic service using `StubContentProvider` and `FakeLLM`. It does not require L0 or real model calls.

## Verified Commands

```powershell
python -m pytest D:\vscodefile\seek_data\tests -c D:\vscodefile\seek_data\pyproject.toml
$env:PYTHONPATH='D:\vscodefile\seek_data\src'; python -m l1_data_processing.smoke
$env:PYTHONPATH='D:\vscodefile\seek_data\src'; python -m l1_data_processing.dod
```

Latest results:

- `55 passed`
- `L1 PIPELINE: PASS checks=standalone pipeline,cache hit,reprocess,filter cancel,long content`
- `L1 DOD: PASS checks=standalone pipeline,cache hit,reprocess,filter cancel,long content`

## DoD Evidence

- Independent run: `run_dod_checks` uses fixtures, `StubContentProvider`, and `FakeLLM`.
- Event intake: `tests/test_consumer.py` covers `content.ingested` contract validation, enrichment dispatch, and duplicate handling through cache/outbox idempotency.
- Initial filter: low-quality content returns `CANCELLED` and no analysis artifact.
- Schema extraction: `tests/test_base_analysis_schema.py` and structured retry tests validate required fields and bad-output handling.
- Long content: split route and chunk aggregation are covered by `tests/test_chunk_aggregation.py`.
- Embedding and tags: embedding dimensions/similarity and general tag vocabulary are covered by `tests/test_embedding.py` and `tests/test_tagging.py`.
- Artifact contract: repository upsert, status transition, and outbox event tests cover `content_base_analysis`, `WAIT_SCORE`, and `content.analyzed`.
- Cost: model tier routing, per-content cost records, daily totals, and threshold alerts are covered by `tests/test_model_routing.py` and `tests/test_costing.py`.
- Idempotency and replay: cache hit, graph version invalidation, and explicit reprocess are covered by `tests/test_enrichment_cache.py`.

## Integration Notes

- Replace `StubContentProvider` with an L0-backed provider at integration time.
- Replace in-memory repository, outbox, cache, and cost ledger with platform storage implementations.
- Keep the frozen contracts: `BaseAnalysis`, `content.analyzed`, and L1-owned `content_base_analysis` / `enrichment_cache`.


## 2026-09-12 continuation

本轮已完成真实 L0 provider、整数事件契约、缓存身份与重复投递修复；安装相邻 L0 后 84 项测试和三项 smoke/DoD 通过。完整新证据与未完成范围见 [本轮开发记录](2026-09-12-continuation.md)。上文的旧机器路径与 55 项结果保留为历史记录。
