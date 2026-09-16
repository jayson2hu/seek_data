# L1 M1：SQL 持久化与可重试处理（2026-09-12）

## 本轮结论

L1 新增独立 SQLAlchemy 持久化入口，SQLite 已实际运行并验证跨进程重放；PostgreSQL 使用同一 SQLAlchemy 模型及专用 SQL 迁移，尚未连接真实 PostgreSQL 实例验收。原 `enrich` 独立接口和此前未提交的 L0 桥接改动保持原有工作方式。

每次成功提交将输入快照、当前分析、处理状态及成本记录、分析缓存、版本化 outbox 写入同一个数据库事务。模型/图处理失败保存可重试的 FAILED 记录；持久化事务失败则整体回滚，不留下已处理标记或半条通知。M1 不调用真实模型、不发送外部通知，也不改写 L0 表。

## 使用入口

运行依赖已加入 `sqlalchemy>=2.0`；使用 PostgreSQL 时安装 `.[postgres]` 获得 psycopg 驱动。每个仓库继续使用自己的 `.venv`。

```python
from pathlib import Path
from sqlalchemy import create_engine
from l1_data_processing.sql_store import SqlAlchemyEnrichmentStore
from l1_data_processing.durable import process_content
from l1_data_processing.input import StubContentProvider
from l1_data_processing.llm import FakeLLM

Path(".runtime").mkdir(exist_ok=True)
engine = create_engine("sqlite:///./.runtime/l1.db")
store = SqlAlchemyEnrichmentStore(engine)
store.create_schema()
result = process_content(
    "demo-article", store=store, provider=StubContentProvider(), llm=FakeLLM(),
    graph_version="l1.graph.v0",
)
assert result.status == "WAIT_SCORE"
record = store.get("demo-article")
events = store.pending_events()
engine.dispose()
```

此例使用仓库 fixture。实际 L0 数据使用 `L0ContentProvider.from_session(l0_session, object_store)`，并传入 L0 正整数 ID 的字符串形式；L0 session 与对象存储的生命周期由调用方管理。

冻结签名：

```text
SqlAlchemyEnrichmentStore(engine)
  create_schema() -> None
  get(content_id: str) -> dict | None
  get_run(run_id: str) -> dict | None
  runs(content_id: str | None = None) -> list[dict]
  pending_events() -> list[DurableOutboxEvent]
  relay_once(publisher(topic, payload, event_id)) -> int

process_content(content_id: str, *, store, provider, llm,
                graph_version="l1.graph.v0", reprocess_key=None,
                config=None, router=None) -> ProcessingResult
```

ProcessingResult 包含 `run_id/content_id/status/analysis/replayed/cache_hit/error`；analysis 是与 BaseAnalysis.to_dict 相同的 JSON 字典。`replayed` 表示复用了已提交处理，`cache_hit` 表示被返回的原处理是否通过文本分析缓存完成，两者含义不同。

## L2 读取契约与表归属

本轮 schema_version 固定为整数 1。L2 只读 `content_base_analysis`，只接受 `status=WAIT_SCORE` 且 analysis 非空的行，不需要读取 L0 表。

| 列 | 类型/含义 |
| --- | --- |
| schema_version | Integer，值为 1。 |
| content_id | String(255) 主键；三处身份：行、input_snapshot、analysis 必须一致。 |
| input_snapshot | JSON，字段与 GraphState.to_dict()['content'] 相同：content_id、title、body、source_url、author、published_at、metadata。 |
| analysis | JSON 或 SQL NULL；字段与 BaseAnalysis.to_dict 相同，含 one_liner、summary、key_points、quotes、entities、base_tags、embedding、lang、status、created_at、traces。分析内部 status=COMPLETED，行级可消费状态为 WAIT_SCORE。 |
| graph_version | String，调用方声明的图/配置版本。 |
| content_hash | 清理规范化后的标题与正文的 SHA-256；用于文本分析缓存。 |
| run_id | 当前成功或失败处理的唯一版本 ID。 |
| status | WAIT_SCORE、FAILED 或 CANCELLED。 |
| updated_at | 当前投影更新时间。 |
| request_id、revision | L1 请求归组与乐观并发控制字段；L2 无需写入。 |

L1 独立 provider 可以使用非空字符串 ID。当前 L2 评分域将 ID 存为 BIGINT，因此 L0→L2 链路仅使用可无损映射为 BIGINT 的正整数字符串；非数字 fixture 不属于该评分入口。

L1 拥有且迁移只管理以下 5 张表：

- `content_base_analysis`：每个内容的当前分析投影与完整输入快照。
- `enrichment_cache`：以规范化正文 hash + graph_version 为复合主键的分析缓存。
- `l1_processing_runs`：每个请求的每次已提交 attempt，包括 FAILED/CANCELLED、成本、输入快照和错误。
- `l1_outbox_events`：版本化 `content.analyzed` 通知及投递时间。
- `l1_schema_migrations`：L1 SQL 迁移版本。

没有指向 L0 表的外键，迁移往返会保留 `content_items` 等 L0 表和无关表。

## 请求、版本、失败与成本语义

自动请求由 content_id、完整输入快照的 hash、graph_version 确定。输入元数据变化也会形成新请求，让 L2 读到最新来源快照；如果正文相同，可复用文本分析缓存。graph_version 应随影响分析行为的模型/提示词/GraphConfig 变更而变更。

自动模式优先复用当前投影对应的同快照、同 graph 终态处理，包括最近一次手动重处理结果。若内容从 A→B→A，或 graph 版本切换后再切回，会形成新的 attempt/run、更新当前投影并产生新通知；可以复用历史文本缓存，不会直接返回历史 A 而让 SQL 仍停留在 B。

显式 `reprocess_key` 用于强制重处理，必须是调用方保存的稳定非空字符串。它绕过分析缓存；同一 key 重试已成功或已取消的处理时不调用模型、不新增通知；同版本的新 key 可以触发新处理。相同 key 若配不同输入快照或 graph_version，抛 RequestConflictError。显式 key 的历史重放严格对应原请求，不回退当前投影。没有默认随机 request key。

FAILED 不会成为成功幂等标记。相同请求重试会增加 attempt，并保留此前失败状态、已知成本和错误。CANCELLED 是终态；如需重新评估，应使用新的显式 key 或新 graph/input 版本。输入读取失败直接抛出异常，不调用模型，也不插入已接受请求。

每个已提交 run 记录实际成功模型响应的 prompt/completion tokens、调用数、traces 与 cost_units。缓存复用记录零次新调用、零新成本；幂等重放不新增 run，也不覆盖原成本。远端调用抛错时无法确认其真实账单，`cost_complete=0` 表示记录的是已知响应成本，不能把未知部分当成免费。cost_units 是现有 token 计数指标，不是货币价格。

## 事务、并发和投递边界

处理开始时记录当前投影 revision；模型计算不持有数据库写锁。最终提交使用 revision 的条件更新；并发插入依赖主键及 request_id+attempt 唯一约束。过时 worker 全事务回滚；只有重读到不早于本 attempt 的同请求成功结果，且自动模式中它仍是当前投影时，才视为并发重复成功。否则抛 ConcurrentProcessingError，调用方需重新读源数据后重试。

此控制防止处理期间有新提交时旧结果覆盖它，不能推断任意延迟快照在业务上是否更旧。若队列直接携带旧快照，生产端还需按 content_id 保序或引入上游单调版本。并发计算、提交失败或进程崩溃可能已经产生外部模型费用；SQL 无法回滚外部调用。竞争失败/提交失败的计算没有被标记为成功 run，运营账单仍需结合模型供应商请求记录核对。

outbox 的 event_id 为 `content.analyzed:{run_id}`。内容、graph、显式 request 或重新激活版本产生新通知；同一成功处理的重复调用不新增通知。`relay_once` 逐条投递，回调成功后标记 sent_at；回调失败保留待投递状态。接收方必须使用 event_id 幂等：接收成功到数据库标记之间崩溃、多 relay 并发均可能重投。消费积压事件时还应核对 payload.run_id 与 SQL 当前版本，明确处理该事件版本还是仅处理最新版本。

本轮提供持久化处理和可重试 outbox API，尚未部署真实模型 worker、消息总线消费进程或跨服务事务。

## SQL 迁移与分发

包内包含 SQLite/PostgreSQL 各自的 0001 up/down SQL。`store.create_schema()` 使用这些 SQL，不是只调用内存模型 create_all。SQL 资源已配置为 wheel package data。

```powershell
.\.venv\Scripts\python.exe -m l1_data_processing.migrations upgrade --database-url "$env:L1_DATABASE_URL"
```

降级会删除 L1 自有表和数据，只用于明确隔离的开发/测试数据库。本次只在新临时数据库中验证 upgrade→downgrade→upgrade。已有同名表却没有 L1 迁移版本记录时会拒绝自动接管或删除，避免覆盖旧 schema。

## 本轮验证证据

| 验证 | 结果 |
| --- | --- |
| L1 完整既有 + 新增测试 | 112 passed，无 skip/deselect。 |
| M1 新增测试 | 28 passed；其中真实 SQLite、独立 Python 进程重放、双 engine/线程竞争。 |
| 独立 L1 smoke | 通过：pipeline、cache、reprocess、filter cancel、long content。 |
| 真实 L0→L1 契约 smoke | 通过，使用临时 SQLite/文件存储和 FakeLLM。 |
| SQL 迁移往返 | 通过；保留 L0/无关表、拒绝接管同名旧表、SQLite DDL 异常整体回滚。 |
| PostgreSQL schema | 专用 SQL 按 dialect 编译并逐表核对通过；未连接真实 PostgreSQL。 |
| wheel | 构建成功，内含 4 份 SQL；直接从 wheel 加载并执行 SQLite up/down 通过。 |
| 迁移 CLI | 临时数据库 upgrade→downgrade→upgrade 通过。 |
| 依赖检查 | pip check 通过。 |

回归还覆盖：写 outbox 前/事务 commit 时强制异常无半成品；失败可重试且保留成本；同文不同 ID 的持久缓存不串身份；输入/graph 回退与手动后自动 current 一致；历史旧 attempt 不会吞掉并发冲突；请求 key 的并发误复用被拒绝；非法模型数值不形成可消费分析；outbox 接受后丢响应仍以稳定 event_id 重投。

下一步是接入真实 PostgreSQL 并验证运行时锁/故障恢复、选定持久消息消费与模型调用设施、落实每个内容的上游版本/保序策略及模型账单对账。生产验收不能由本轮 SQLite/FakeLLM 测试替代。
