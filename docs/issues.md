# L1 Issue Log

## 2026-05-30

- Issue: Initial `workdir` execution resolved to `D:\vscodefile`, causing pytest to discover unrelated projects.
  Resolution: Use explicit `D:\vscodefile\seek_data` paths for pytest and module commands.

- Issue: HTML entity `&nbsp;` produced non-breaking spaces that bypassed whitespace normalization.
  Resolution: Expanded whitespace normalization to include `\u00a0`.

- Issue: Long-content aggregation duplicated repeated chunk summaries.
  Resolution: Deduplicated aggregated summaries and key points.

- Issue: Structured retry refactor changed trace names from node names to attempt-aware names.
  Resolution: Updated tests to assert attempt-aware trace contract.

## 2026-05-31

- Issue: Cache-hit path had a completed `BaseAnalysis` but no intermediate `base_analysis`/`embedding`, causing persistence to fail.
  Resolution: `persist_placeholder_node` now uses existing `state.analysis` when present.

- Issue: Direct DoD command hit intermittent Windows sandbox process startup failure.
  Resolution: Re-ran with approved elevated command; command passed.
