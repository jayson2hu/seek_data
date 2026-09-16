# CodePick L1 数据加工

[开发指南](DEVELOPMENT.md) · [M1 持久化记录](docs/2026-09-12-m1-persistence.md) · [平台进度](../codepick-docs/PROJECT_STATUS.md)

L1 已实现清洗、过滤、长文分块、摘要/标签/向量、校验重试与缓存。独立 graph 路径继续支持 StubContentProvider/FakeLLM；L0ContentProvider 可读取实际 L0 存储的正文。

M1 新增 SQLAlchemy 持久入口：输入快照、分析、缓存、处理状态/成本和版本 outbox 原子提交；成功请求重启幂等，失败可重试，正文/graph 更新和明确 reprocess_key 产生独立通知，并拒绝过时并发写。模型仍为 FakeLLM，真实 worker/模型/PG 未联调。

```sh
python -m pip install -e '.[dev]'
python -m pytest
python -m l1_data_processing.smoke
python -m l1_data_processing.dod
```

本轮 112 项测试通过。跨实际 L0 需 Python 3.12+ 并安装相邻包：

```sh
python -m pip install -e ../deepdata
python -m l1_data_processing.l0_smoke
```

持久入口：`SqlAlchemyEnrichmentStore(engine)`、`store.create_schema()` 与 `process_content(content_id, store=..., provider=..., llm=..., graph_version=..., reprocess_key=...)`。显式迁移使用 `python -m l1_data_processing.migrations upgrade --database-url sqlite:///new-l1.db`，只创建 L1 自有表。库连接由调用方明确选择，不从隐式环境变量推断。

整条 L0 → L1 → L2 跨进程检查见[平台 M1 指南](../codepick-docs/M1_INTEGRATION.md)。L0 自动更新通知和 L2 版本重评分仍待开发，不能将本轮显式调用测试视为持续全平台运行。
