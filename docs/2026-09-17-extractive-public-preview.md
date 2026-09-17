# 真实公开内容的离线抽取：问题与实施计划

日期：2026-09-17。本文记录 L1 面向真实公开内容的首轮业务处理改造。

## 已确认问题

- `FakeLLM` 的固定摘要适合测试 graph 契约，不适合真实内容预览；固定文案会掩盖正文差异。
- 当前真实 L0 输入没有统一声明来源类型和处理方法，上层可能误把规则结果理解为模型结果。
- 缺少从一份真实 L0 数据库批量生成 durable L1 SQL 快照、逐条失败和来源统计的可复现入口。

## 本轮范围

1. 保留 `FakeLLM` 默认测试契约，新增调用者显式选择的 `DeterministicExtractiveLLM`。
2. `extractive-v3` 只做可复现的原文句子摘录、规则标签/实体和词哈希向量；不做翻译、主观评分或模型推断。
3. L0 输入快照写入：
   - `metadata.source_kind = "public_feed"`
   - `metadata.processing = {"method":"extractive-v3","provider":"deterministic-extractive","model":null,"generated":false}`
   - 来源、原文 URL、feed URL、发布时间、抓取时间、内容版本和 L0 hash。
4. 批处理 CLI 读取 L0 查询契约，逐条调用既有 `process_content`，以同一事务规则保存快照、分析、run、cache 和 outbox。
5. 报告必须列出 requested、processed、replayed、failed、content IDs 和错误；没有成功内容时非零退出。

## 语义边界

- `summary`、`one_liner`、`key_points`、`quotes` 均为原文摘录，可回溯到输入正文。
- `entities` 是大小写/词形规则命中的技术名称；`base_tags` 来自确定性关键词规则。
- embedding 是本地确定性词哈希，用于契约和本机检索预览，不表示语义模型质量。
- token/cost 计数是本地处理量记录，`model` 使用 `extractive-*` 名称；不得展示为真实模型成本。

## 验收输出

```bash
seek_data/.venv/bin/python -m l1_data_processing.real_preview \
  --l0-database-url sqlite:////tmp/codepick-real-preview-20260917/l0/l0.db \
  --l0-object-store /tmp/codepick-real-preview-20260917/l0/objects \
  --l1-database-url sqlite:////tmp/codepick-real-preview-20260917/l1/l1.db \
  --report /tmp/codepick-real-preview-20260917/l1-report.json
```

产物 `l1.db` 可由 L2 的 SQL provider 读取。上层必须依据 `input_snapshot.metadata.processing` 标识结果来源。

## 2026-09-17 实际结果

最终 L1 数据库为 `/tmp/codepick-real-preview-20260917/l1/l1.db`，报告为同级
`l1-report.json`。它读取相邻 L0 的 10 篇真实公开内容，不含提交到仓库的原文。

- 10/10 条处理成功，失败 0，来自 GitHub Changelog 和 GitHub Engineering 两个官方来源；内容 ID 为 1–10。
- 最终 10 条当前投影均为 `revision=3`、`graph_version=extractive-v3`、`WAIT_SCORE`。
- 每条 processing metadata 为
  `{method: extractive-v3, provider: deterministic-extractive, model: null, generated: false}`。
- 摘要长度 299–696 字符，每篇 3 个关键点；30/30 个关键点均为输入标题或正文中的精确子串。
- 正文及摘要/关键点均不含 GitHub 导航和 Related posts；SSO、SCIM 内容不再因通用 `model` 一词误标 AI。
- 经过三轮真实版本演进，`l1_processing_runs` 和 `l1_outbox_events` 各 30 行。新 graph 版本通过正常 durable 提交形成 revision，没有直接更新 SQL。
- embedding 仍是 `extractive-hash-v1` 本地词哈希；没有真实模型调用、翻译或主观评分。

L2 应读取当前投影或对应最新 run，并依据 `metadata.processing.generated=false`
展示规则结果边界。历史 revision 保留用于验证旧结果不会覆盖新版本。



仓库级最终检查为 131 项测试通过；`l1_data_processing.smoke`、
`l1_data_processing.dod` 和实际 `L0 -> L1 CONTRACT` 均通过。

## 幂等重放验证

在同一份 L0/L1 数据库上再次以 `extractive-v3` 执行真实内容批处理，报告保存为
`/tmp/codepick-real-preview-20260917/l1-replay-report.json`。

- 10/10 条输入均命中已有处理结果：`processed=10`、`replayed=10`、失败 0。
- `l1_processing_runs` 保持 30 行，重放前后没有新增 run。
- `l1_outbox_events` 保持 30 行，重放前后没有新增事件。
- 10 条当前投影的 revision 全部保持为 3。
- 每条内容对应的 run ID 前后完全一致。
- 报告中的 `replay_verification.idempotent=true`。

这证明相同内容版本、相同 graph 版本的重复执行会复用已有 durable 结果，不会覆盖
当前投影，也不会重复产生 outbox 事件。
