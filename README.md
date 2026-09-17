# CodePick L1 数据加工

[开发指南](DEVELOPMENT.md) · [M1 持久化记录](docs/2026-09-12-m1-persistence.md) · [平台进度](../codepick-docs/PROJECT_STATUS.md)

L1 已实现清洗、过滤、长文分块、摘要/标签/向量、校验重试与缓存。独立 graph 路径继续支持 StubContentProvider/FakeLLM；L0ContentProvider 可读取实际 L0 存储的正文。

M1 新增 SQLAlchemy 持久入口：输入快照、分析、缓存、处理状态/成本和版本 outbox 原子提交；成功请求重启幂等，失败可重试，正文/graph 更新和明确 reprocess_key 产生独立通知，并拒绝过时并发写。版本消息闭环新增 Redis L0 consumer 和 L1 outbox relay；模型仍为 FakeLLM。

```sh
python -m pip install -e '.[dev]'
python -m pytest
python -m l1_data_processing.smoke
python -m l1_data_processing.dod
```

当前 131 项测试通过。跨实际 L0 需 Python 3.12+ 并安装相邻包：

```sh
python -m pip install -e ../deepdata
python -m l1_data_processing.l0_smoke
```

持久入口：`SqlAlchemyEnrichmentStore(engine)`、`store.create_schema()` 与 `process_content(content_id, store=..., provider=..., llm=..., graph_version=..., reprocess_key=...)`。显式迁移使用 `python -m l1_data_processing.migrations upgrade --database-url sqlite:///new-l1.db`，只创建 L1 自有表。库连接由调用方明确选择，不从隐式环境变量推断。

持续消费 L0 事件：

```sh
L0_DATABASE_URL=sqlite:////tmp/codepick/l0.db \
L0_OBJECT_STORE_PATH=/tmp/codepick/objects \
L1_DATABASE_URL=sqlite:////tmp/codepick/l1.db \
L1_REDIS_URL=redis://127.0.0.1:6379/0 \
python -m l1_data_processing.worker
```

持续投递 L1 outbox：

```sh
L1_DATABASE_URL=sqlite:////tmp/codepick/l1.db \
L1_REDIS_URL=redis://127.0.0.1:6379/0 \
python -m l1_data_processing.relay
```

两个入口均支持 `--once`。processing 队列在进程重启时恢复，解析失败进入
`:dead` 队列；L1 会忽略已被更新快照取代的迟到 L0 旧版本。整条链路见
[平台版本消息闭环](../codepick-docs/VERSIONED_EVENT_LOOP.md)。

## 真实公开内容的离线抽取

真实内容预览不得使用固定 `FakeLLM` 摘要。显式入口使用
`DeterministicExtractiveLLM` + `ExtractiveContentProvider`，把原文句子摘录、
规则标签和本地词哈希向量写入既有 durable SQL 管线：

```bash
.venv/bin/python -m l1_data_processing.real_preview \
  --l0-database-url sqlite:////tmp/codepick-real-preview-20260917/l0/l0.db \
  --l0-object-store /tmp/codepick-real-preview-20260917/l0/objects \
  --l1-database-url sqlite:////tmp/codepick-real-preview-20260917/l1/l1.db \
  --report /tmp/codepick-real-preview-20260917/l1-report.json
```

最终 `extractive-v3` 在 `input_snapshot.metadata.processing` 声明
`model=null/generated=false`；不提供翻译、评分或模型质量承诺。摘要最多约 800 字符，
关键点最多 5 条，真实预览当前每篇 3 条且均可在输入原文中精确定位。详见
[真实公开内容离线抽取记录](docs/2026-09-17-extractive-public-preview.md)。
