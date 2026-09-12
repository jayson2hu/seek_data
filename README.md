# L1 Data Processing

[异地开发指南](DEVELOPMENT.md) · [平台总文档与关联仓库](https://github.com/jayson2hu/codepick-docs)

L1 data processing service scaffold built from the delivery documents in `L1数据加工/`.

The current implementation is intentionally standalone:

- `StubContentProvider` reads fixtures and does not depend on L0.
- `FakeLLM` provides deterministic responses and embeddings.
- `run_enrichment` runs a minimal two-step pipeline and produces a `BaseAnalysis`.

## Quick checks

```powershell
python -m pytest
python -m l1_data_processing.smoke
```

The smoke command prints `L1 PIPELINE: PASS` when the standalone path works.
