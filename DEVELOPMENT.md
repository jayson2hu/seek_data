# L1 异地开发指南

本仓库属于 [CodePick 四层平台](https://github.com/jayson2hu/codepick-docs)。建议四个代码仓库保持同级目录，以便查阅关联实现；每个项目使用独立虚拟环境。

## 克隆与环境

需要 Git 和 Python 3.12。以下命令都从本仓库根目录执行。

```sh
git clone https://github.com/jayson2hu/seek_data.git
cd seek_data
python -m venv .venv
```

激活环境：Windows PowerShell 使用 `.venv\Scripts\Activate.ps1`；macOS/Linux 使用 `source .venv/bin/activate`。随后执行：

```sh
python -m pip install -e ".[dev]"
python -m pytest
python -m l1_data_processing.smoke
python -m l1_data_processing.dod
```

## 当前运行模式

当前默认使用 StubContentProvider、FakeLLM 和内存存储。2026-09-12 已新增 L0ContentProvider 与实际 L0 本地契约检查：在本环境安装相邻 L0 包 `python -m pip install -e ../deepdata`，再运行 `python -m l1_data_processing.l0_smoke`。

版本闭环模式使用持久 SQL 和 Redis：

```sh
python -m l1_data_processing.worker
python -m l1_data_processing.relay
```

worker 需要 `L0_DATABASE_URL`、`L0_OBJECT_STORE_PATH`、
`L1_DATABASE_URL` 和 `L1_REDIS_URL`；relay 需要后两项。两个入口均支持
`--once`。当前 worker 明确使用 FakeLLM，不会调用付费模型。

## 交接范围

提交包括当前源码、测试、迁移、配置示例与项目文档。依赖目录、构建产物、本地数据库、采集运行数据、日志和凭据不随仓库分发，需要在新环境重新安装或配置。

各层状态与验收证据见项目 README 和 docs；本文提供恢复开发的入口，不代表本次发布重新完成生产环境验收。


## M1 持久化更新

本轮已新增 SQLAlchemy 持久入口与 SQL 迁移，分析/输入快照/缓存/处理状态成本/outbox 不再只能存内存。原 graph API 仍可独立运行；需要持久化时使用 `sql_store.SqlAlchemyEnrichmentStore` 和 `durable.process_content`。详见 [M1 记录](docs/2026-09-12-m1-persistence.md) 与 [平台七阶段检查](../codepick-docs/M1_INTEGRATION.md)。前文关于原默认路径的说明保留，但 L1 SQL 存储与实际 L2 读取已在本轮完成本地验证。
