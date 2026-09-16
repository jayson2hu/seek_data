# L1 恢复开发与跨层契约记录

日期：2026-09-12。基线提交：`dcbb21572a84ae5c9943bda638774116d3fffef3`。位置：`D:\fayun\code\codepick\seek_data`。

## 原始状态与本次验证

Python 3.12.14 独立 `.venv`，先安装 `.[dev]`；原始 55 项测试、smoke/DoD 通过。历史 README 的“两步最小管道”已不能完整描述代码，现已有过滤、分块、校验、缓存、成本、内存持久化/事件等功能。

本次新增和修复后，未安装 L0 时 **83 passed、1 skipped**；安装相邻 `deepdata` 后 **84 passed、0 skipped**。独立 `L1 PIPELINE: PASS`、`L1 DOD: PASS` 和新增 `L0 -> L1 CONTRACT: PASS` 均重新执行通过。

## 实际开发

- `consumer.py`：兼容 L0 实际发出的正整数 ID，转换为 L1 内部字符串；保留原有字符串 fixture；拒绝布尔值、非正整数、浮点和空值。
- `graph.py`：缓存按正文/graph_version 共用时，分析输出使用当前内容 ID，并隔离嵌套可变列表，避免写错 repository/outbox 对象；重复投递到相同终态不重复执行状态转移。
- `input/l0.py`：新增 `L0ContentProvider`。普通构造接收已绑定的 L0 查询函数；`from_session(session, object_store)` 延迟导入 L0，绑定其真实只读 `get_content`。会话和对象存储生命周期由调用方管理，不创建或修改 L0 数据。
- `l0_smoke.py`：新建临时数据库/存储和本地 RSS/HTML，运行实际 L0 采集、查询、outbox relay，再调用 L1；验证整数事件、正文来自对象存储、分析产物、重复投递无模型调用、L0 内容和 raw 不被 L1 修改。结束关闭数据库后清理新建临时目录。

## 使用真实 provider

从 L1 环境安装相邻 L0 包：`python -m pip install -e ../deepdata`。运行方建立好 L0 Session 与 ObjectStore 后，将 `L0ContentProvider.from_session(session, object_store)` 注入现有 `enrich` / `consume_content_ingested` 即可；未提供隐式配置或失败回退。

跨层命令：`python -m l1_data_processing.l0_smoke`。标准测试中的 `test_l0_integration.py` 在缺少 L0 包时说明原因并 skip，不阻塞 L1 独立开发。

L0 `title` 允许为空；只要正文存在即可读取。无正文的 TREND 明确报错，不拿标题伪装完整文章。`LookupError` 转换为 provider 的 `KeyError`；存储故障继续向调用方报告；返回错误 ID 的查询结果被拒绝。来源、语言和上游状态保留在输入 metadata 中，作者不在 L0 当前公开查询契约中，因此不虚构。

## 仍未完成

- SQL 分析存储、持久状态/缓存/成本/outbox、原子提交与持续消费 worker；本轮仅证明实际 L0 读取和事件合同。
- 实际 L1 → L2 schema 和字段映射、真实模型、PostgreSQL/Redis 集成；不把 FakeLLM 输出称为真实模型效果。
- graph_version/内容版本变化后的新事件：当前 outbox 仅按内容 ID 去重，已发送内容重处理会缺少新的通知，需要独立设计。
- FAILED/CANCELLED/已完成内容的显式重处理状态策略；本次只使相同终态重复投递幂等，未开放任意终态迁移。
- TREND/短标题专用处理分支；生产内容的适用状态和数据权限需要由持续运行入口约束。

下一轮建议先完成 L1 持久化及 L1 → L2 实际契约，详见[平台开发计划](../../codepick-docs/DEVELOPMENT_PLAN.md)。
