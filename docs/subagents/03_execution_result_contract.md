# 子 Agent 执行结果契约（WP1 交付）

> 日期：2026-10-28｜实现：`parallel_subagent_service.py`（v2 字段为增量附加，旧字段语义不变）
> 目标：杜绝「子循环返回了文字 = 任务成功」的假成功；三个成功维度分开判定。

## 1. 三个成功维度（不等价）

| 维度 | 字段 | 取值 | 判定者 |
|---|---|---|---|
| 运行生命周期 | `status`（旧字段，兼容保留） | `ok / failed / timeout / blocked / guarded / awaiting_input / approval_pending / paused / terminated / budget_exhausted` | 子循环（是否正常结束） |
| 业务结果 | `outcome_status`（新增，仅契约任务携带） | `succeeded / partial / blocked / failed / answered_unverified / not_evaluated` | 服务端 `_evaluate_outcome`，**不靠 LLM 自评** |
| 产物结果 | `artifact_status`（新增，仅契约任务携带） | `not_required / not_created / produced`（verified/published 待 WP2） | 服务端，基于工具回执 |

仅当子任务在 `tasks[].requires` 声明能力契约时，附加上述两个新字段（`outcome_status/reason_code/artifact_status/capabilities_required/capabilities_granted/tool_receipts`）；未声明的旧任务保持原信封不变（向后兼容，存量单测守护）。

## 2. 能力契约与准入（R11）

- tasks item 可选 `requires: string[]`，合法值：`research.retrieve / workspace.read / python.execute / artifact.write / artifact.publish / approval.request`（schema 枚举，未知名在校验阶段拒绝 `SUBAGENT_INVALID_TASKS`）。
- `prepare()` 按装配后有效工具求交（`_CAPABILITY_SATISFY_TOOLS`）：缺失能力 → 该子任务 spawn 前阻断，返回 `status=blocked` + `outcome_status=blocked` + `reason_code=CAPABILITY_MISSING`，**子循环不启动、不产生 provider 调用**；同批其他任务不受影响。
- 普通聊天 fan-out 的 code Agent 无 `sandbox_execute`/`workspace_write`，声明 `python.execute` 即被正确阻断（与「code 无执行器」证据吻合）。

## 3. Outcome 判定规则（`_evaluate_outcome`）

按顺序：

1. `blocked_capabilities` 非空 → `blocked / CAPABILITY_MISSING / not_created`
2. `status ∈ {failed, timeout, paused, terminated}` → `failed`（`EXECUTION_FAILED / TOOL_TIMEOUT / EXECUTION_CANCELLED`）
3. `status ∈ {awaiting_input, approval_pending}`（暂停态，非终态）→ `blocked / AWAITING_USER`
4. 声明 `python.execute` 但无 `sandbox_execute` 成功回执 → `blocked / EXECUTION_NOT_VERIFIED`（**「我能写代码」≠「执行了代码」**）
5. 声明 `artifact.write/publish`：无写回执 → `blocked / ARTIFACT_NOT_VERIFIED`；有写无发布回执 → `partial / ARTIFACT_NOT_PUBLISHED / produced`；有发布回执 → `succeeded / ARTIFACT_RECEIPT_VERIFIED`
6. 有执行回执且无产物要求 → `succeeded / EXECUTION_RECEIPT_VERIFIED`
7. `status=ok` 纯文本回答 → `answered_unverified / ANSWER_WITHOUT_VERIFIER`
8. `budget_exhausted/guarded` 阶段性收尾 → `partial / RESULT_PARTIAL`

## 4. 汇总口径

- 契约任务（任一路声明 requires）：summary =「X 已验证完成，Y 受阻，Z 未验证问答，W 部分完成，V 失败/超时；总墙钟 Ts」，**不再出现 "4/4 成功" 覆盖失败的口径**。
- 旧任务：保持「N/N 个子任务成功」原口径。
- 附加诊断：`body_missing=true`（ok 却无正文，R15 退化检测）；`payload_truncated=true`（被预算降级）。

## 5. 正文回灌（R15/R16）

- 子结果正文 ≥2000 字 → 落盘 `{storage}/subagents/{run_id}/{index}/result.json`，信封附 `detail_ref`（相对路径，含 answer/thought/回执/outcome 全量）。
- `llm_payload` 预算 10,000 字符：超出时按 answer 长度降序逐路降级为 500 字摘要 + `detail_ref` 引用 + `payload_truncated=true`（packet.final_answer 一并降级）——**父轮回灌永不静默截断**，chat_service 12k 兜底处另有 `...[PAYLOAD_TRUNCATED_BY_CHAT]` 显式标记。
- `ui_payload.progress[]` 透出 `answer_summary(200字)/detail_ref/payload_truncated/body_missing/outcome_status/reason_code`，供 WP3 前端三态展示。

## 6. 配额与幂等

- 存量：`FanoutAdmission` 校验先于占用、同轮 5→4 修正重试（预算 2）、受理后拒不同集合、统一意图预分派与双引擎共享语义。
- 新增（R04/R05）：显式 `request_key`（≤128 字符，schema 可选）启用进程级重放缓存（128 条目 / 30min TTL，scope=user:session）：
  - 同 key 同 payload（canonical digest 覆盖 context+全部子任务字段）→ 返回原 envelope + `replayed=true`，**不重复执行、回执不增加**；
  - 同 key 异 payload → `SUBAGENT_REQUEST_CONFLICT`；
  - 无 key 同 payload → 视为新业务请求（用户「再跑一次」合法），不隐式重放。
- 限制：进程内实现；多 worker 部署需共享存储（WP4 决策）。

## 7. 状态机速查

```
prepare: validate → spawnable → capability 求交(记录 blocked) → FanoutPrepared
execute: replay 检查(request_key) → [blocked 子任务: worker_started→worker_finished(blocked)]
         → 其余 acquire semaphore → worker_started → ReAct 循环 → worker_finished
聚合:    views → body_missing 检测 → 契约 summary / 旧 summary → 预算降级 → envelope → replay 存储
```
