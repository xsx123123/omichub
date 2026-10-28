# 子 Agent 当前运行时审计（WP0）

> 日期：2026-10-28｜审计基线：分支 `feat/chat-message-queue`，commit `51003efa`（工作区有大量未提交改动，均为文档/配置类，子 Agent 相关代码无未提交修改）。
> 方法：纯静态代码审计 + 既有单测清单盘点，未改动任何代码，未对 Agent 提权，未运行会改变生产状态的命令。
> 依据资料包：`docs/info/26.10.27/CygnusX_SubAgent_优化与测试资料包_2026-10-27/`（优化方案 v1.0 / 测试矩阵 R01–R34 / 主提示词）。

## 0. 结论摘要

| 问题域 | 现状判定 | 证据强度 |
|---|---|---|
| 假成功（4/4 ok 掩盖未执行） | **仍然存在，结构性**：`status=ok` 只代表子循环以文本收尾 | 代码逐行确认 |
| B/C/D 正文丢失 | **根因定位**：父轮回灌 12,000 字符静默截断 + ui_payload 本就不含正文 | 代码逐行确认 |
| Capability Preflight | **不存在**：无能力声明/求交/blocked 语义 | 代码逐行确认 |
| 产物闭环 | **完全缺失**：workdir 已建但无人消费（`subagent_workdir` extra 零引用），无 manifest/发布/父回读 | grep 全仓零命中 |
| 配额时机 | **P0 大部分已修复**：`FanoutAdmission` 校验先于占用、同轮 5→4 可重试；但**无 request_key 幂等重放**（R04/R05 未覆盖） | 代码逐行确认 |
| schema 漂移 | maxItems=4 与运行时一致（有单测守护）；但 schema 任务描述「2000 字」vs 运行时 20,000 字漂移 | 代码逐行确认 |
| 子任务级并行实测 | 无子任务级 spans；semaphore=3、queued 状态对前端不可见 | 代码逐行确认 |
| SSE/UI | rejected/started/child_*/aggregated 相位已通；无 queued、无 verified 区分、无产物字段 | 前后端代码确认 |
| `shania` 非 spawnable | 确认：`data/ai/shania.yaml` 未声明 `subagents_spawnable`，prepare 将拒 `SUBAGENT_NOT_SPAWNABLE` | 代码确认 |

既有单测 `tests/unit/test_parallel_subagent_service.py`（34 个用例）已覆盖：工具过滤、workspace_access 门控、safe_only 只读、失败隔离、超时、validation 规则、prepare 无副作用、schema maxItems 一致性、usage 合并。未覆盖：outcome 验收（R12）、capability preflight（R11）、产物生命周期（R21–R27）、截断标记（R15/R16）、并行 spans（R17–R19）。

## 1. 运行基线

### 1.1 配置（`src/cygnusx/core/config.py:333-353`）

| 配置 | 默认值 | 说明 |
|---|---|---|
| `subagent_fanout_enabled` | `False` | env 开关；管理端 DB 开关任一为真即启用（prepare 内判定，`parallel_subagent_service.py:291-297`） |
| `subagent_max_parallel` | 4 | 单批任务数上限（`_validate_tasks`，`:515-519`） |
| `subagent_max_concurrent` | 3 | 实际并发 semaphore（`execute()` `:366`） |
| `subagent_child_timeout_seconds` | 1200 | 单任务墙钟 |
| `subagent_max_rounds_per_child` | 24 | 子循环工具轮数 |
| `subagent_max_children_per_message` | 1 | 父单轮工具回合 fan-out 受理次数上限 |
| `overdrive_subagent_max_rounds` | 25 | 超频专家放宽轮数 |

### 1.2 工具 schema（`tool_configs/tools_schema.yaml:85-112`）

- `maxItems: 4`、`minItems: 1` 与运行时默认一致；`test_parallel_subagents_schema_max_items_matches_settings_default` 守护。
- **漂移**：`task` 描述「不超过 2000 字」，运行时 `_TASK_INSTRUCTION_MAX_CHARS = 20_000`（`parallel_subagent_service.py:124`）。
- tasks item 仅暴露 `agent_id`/`task` 两个字段：LLM 无法（也不应）请求 `workspace_access`；该标志只由内部调用方（超频/会诊）注入。

### 1.3 可派生 Agent（`data/ai/*.yaml` 的 `features.subagents_spawnable`）

- **可派生（12）**：code、data、qc、viz、atacseq、rnaseq、cloud_ops、delivery、general、scrna、scrna_advanced、scrna_integration、scrna_upstream（实际 13 个 yaml 标记 true）。
- **不可派生**：agentteams_manager（false）、explorer（false）、shania（未声明 → 默认 falsy → prepare 拒绝 `SUBAGENT_NOT_SPAWNABLE`，`:321-328`）。
- 前端展示 ID 与 registry ID 的映射未在本轮核实（DB registry 为运行时真相源），R06 类测试须以 `assemble_context` 实际解析为准。

## 2. 八类入口矩阵

| # | 入口 | 代码位置 | 调用方式 | 关键差异 |
|---|---|---|---|---|
| 1 | Legacy 工具调用 | `chat_service.py:4630-4859` | admission → prepare → rejected/started → execute（事件队列转发）→ aggregated | 回灌 12k 截断（见 §3.2） |
| 2 | 统一意图预分派 | `chat_service.py:4136-4173` | `intent=fanout` 且 ≥2 任务时直接 `run_parallel_subagents`，成功后把全量 llm_payload 注入 system_prompt 并置 `fanout_preexecuted` | **失败静默回退**（无 rejected chunk、不告知模型）；成功路径无 12k 截断 |
| 3 | LangGraph | `runtimes/langgraph_runtime.py:633-797`（admission box `:950-1024`） | 与 Legacy 逐点对齐（注释 `:634-637` 自述） | 语义一致，同一 FanoutAdmission 类 |
| 4 | 超频前台 Wave | `chat_service.py:~1970-2030`（wave_tasks 含 `workspace_access`，`:1978`） | tool service + on_event 队列 + 整链 deadline 取消 | assignment 驱动，workspace_access 由计划决定 |
| 5 | 超频 Celery | `infrastructure/celery_app/tasks/overdrive.py:1105-1135` | `service.run(..., runtime_authorized=True)`，task 级 `workspace_access = not sandbox_unavailable_reason` | 后台高权限路径 |
| 6 | AgentTeams 会诊 | `agent_consultation_service.py:~410-435` | `service.run(..., safe_only=(readonly_consultation), runtime_authorized=True, allow_non_spawnable_target=True, 单任务)` | 只读/工作台双模式；非 spawnable 目标单任务豁免 |
| 7 | Goal Fan-out | `goal_adapters/fanout_adapter.py` | 经 tool service，持久化幂等键 `parent_key = f"{work_unit_key or 'goal'}:fanout"`（`:41`） | 带持久化执行记录（fanout_started/finished） |
| 8 | MAS DAG | 不经本服务 | 长时管道走独立 MAS 编排 | 与本服务授权边界独立 |

**准入顺序（Legacy/LangGraph 工具路径，当前真实实现）**：
`check_preexecuted → begin_validation(预算 2) → prepare(validate shape/count + spawnable + 预组装) → [拒绝: mark_rejected + rejected chunk] → try_commit(占 accepted) → started chunk → execute → aggregated chunk`

与方案 §5.1 目标顺序的差异：① 无 capability preflight 步骤；② 无 request_key/digest 幂等；③ 统一意图预分派在 admission 建立**之前**执行，靠 `extra["fanout_preexecuted"]` 回填占用（`chat_service.py:4368-4372`），语义正确但属隐式耦合。

## 3. P0 问题逐项核查

### 3.1 假成功：确认存在（结构性）

- 子循环只要「以文本收尾且无待处理工具调用」即返回 `status: "ok"`（`parallel_subagent_service.py:1074-1082`）。子 Agent 回答"当前无执行器，未运行代码"同样落 `ok`。
- 汇总口径：`ok_count` 只统计 `status=="ok"`（`:428`），summary 输出 `"{ok}/{total} 个子任务成功"`（`:436-442`），`success = ok+interrupted > 0`（`:444`）。
- 另有 `guarded` 保护（连续相同工具结果）也返回 `status: "ok", partial: True`（`:1255-1280`）计入成功数。
- **不存在** outcome evaluator：没有任何基于任务契约 / 工具 receipts / 文件校验的判定（`evaluate_outcome` 全仓无实现）；`verified_evidence_refs` 只是若干只读工具的引用标签（`:1412-1438`），不构成验收。
- 后果：执行/产物型任务与普通问答共用同一成功口径，`4/4 ok` 可完全掩盖"未执行"。R11/R12/R13/R20 均无法满足。

### 3.2 B/C/D 正文丢失：根因定位（两级）

1. **父模型上下文层**：工具结果回灌时 `llm_content = json.dumps(llm_result)`，fan-out 走 12,000 字符上限且**静默截断、无 `payload_truncated` 标记**（`chat_service.py:5761-5779`）。llm_payload.results 每路 answer 上限 100k 字符（`:1076`），四路长正文必然截断，后段子任务（B/C/D）整段消失。
2. **前端层**：`ui_payload` 只有 `fanout_run_id/elapsed_s/progress[{index,agent_id,status,elapsed_s}]`（`:450-462`），**本就不含 answer**；aggregated chunk 同（`chat_service.py:4829-4849`）。前端 `useAgentChatStream.ts` aggregated 分支只渲染 progress（`:918-920`）。即正文从未设计流向 UI。
3. 统一意图预分派路径反而把全量 llm_payload 注入 system_prompt（`chat_service.py:4154-4158`），两条入口行为不一致。
4. 无 `detail_ref` 持久化：子结果仅存在于内存信封与子循环的 AgentTeamsTurnRecorder 审计（`:1350-1394`），父会话/前端无按 ref 读取通道。

### 3.3 Capability Preflight：不存在

- `_prepare_child_tools`（`:555-652`）只做控制工具剥离 + safe_only 只读过滤 + workspace_access 追加，**无能力声明、无求交、无 blocked/CAPABILITY_MISSING 语义**。
- 普通 fan-out（入口 1/2/3）的 task item 无 `workspace_access`（schema 不暴露），子 code Agent 实际工具集 = 自身 backend_sync 工具 + knowledge_search + web_search + skills + ask_user（`:583-595`）——**无 sandbox_execute / 无写文件工具**，与「code 子 Agent 无执行器」证据吻合。
- 缺失能力的唯一表现是子 Agent 自己在正文里说明，随后仍按 `ok` 计成功（§3.1）。

### 3.4 产物闭环：完全缺失

- workdir：`{storage}/subagents/{run_id}/{index}`（`:344, :389`），执行前 mkdir（`:695`）。
- **C6 未接线**：`ToolInvocationContext.extra["subagent_workdir"]`（`:1509`）全仓 grep 仅 1 处定义、0 处消费——没有任何 builtin/MCP 工具按该目录写产物。
- 无 manifest：`_execute_child_tool` 只调用 `normalize_tool_artifact_payload`（`:1603`）；`artifact_manifest.py` 的 `build_manifest/reconcile_declared` 仅服务于前台 `chat_sandbox_tools` 与 studio archive（`archive_storage.py`），子 Agent 服务未接入。
- 无 Produced→Verified→Registered→Published→父回读任何一环；ui_payload 无 artifacts 字段；父工作区不复制子产物（与 TODO 中「fan-out 子 Agent 产物不回灌父会话」一致，仅 `studio_tools._workspace_write` 的 output/ 回填已在 2026-10-27 修复）。
- 超频 workspace 工具路径（`:1485-1502`）经 `studio_sandbox_manager.register_workdir_mount` 挂载后由 Studio 沙盒真实执行，但产物同样只留在沙盒/workdir，无登记发布。

### 3.5 配额时机：大部分已修复，幂等缺失

已修复（与方案 §5.1 一致）：
- 校验先于占用：prepare 拒绝返回信封并 `mark_rejected()`（`chat_service.py:4714-4727`），不占 accepted、发 rejected chunk（前端不画幽灵卡）。
- 同轮修正重试：`begin_validation` 预算 2（`fanout_admission.py:35-43`），5→4 同轮可受理（R02 路径存在）。
- 受理后二次不同集合：`try_commit` 拒（`:48-53`）。
- 统一意图预分派与工具调用共享 admission（`mark_preexecuted` ↔ `check_preexecuted`，R10 路径存在）；预分派失败不占用（`chat_service.py:4153` 仅在 success 时置标）。

未覆盖：
- **R04/R05**：无 request_key / canonical_digest / 重放返回原 run / 冲突检测。同 key 重放会走第二次 `begin_validation`（预算内）再 `try_commit` 被拒——既不返回原结果也不报 conflict；跨轮重放则直接再执行一次（无跨轮幂等）。
- unified 预分派失败路径静默（`chat_service.py:4172-4173` 仅 logger.warning）：模型不知道预派失败，可能再以 2 任务重试——语义可接受但可观测性差。
- prepare 内 `_validate_tasks` 的上限取 `settings.subagent_max_parallel`，与 schema maxItems 独立维护（现一致，靠单测守护）。

### 3.6 SSE / 前端状态机：部分可用，三态与 queued 缺失

- 后端事件映射 `subagent_child_event_metadata`（`:203-227`）：仅 worker_started→child_started / worker_retrying / worker_finished→child_done；heartbeat 丢弃；**无 queued 事件**——`worker_started` 在 acquire semaphore **之后**才发（`:700-701`），第 4 个任务的排队期对前端不可见。R17/R30 的「3 running + 1 queued」前端无法呈现（前端 started 相位把全部任务初始置 queued，但 child_started 到来即翻 running，无运行数上限语义）。
- 前端 `useAgentChatStream.ts:889-950`：`status==='ok' → 'succeeded'`，其他状态字面透传、空则 'completed'；无 `verified` 维度；aggregated 只有 progress 状态数组。
- 无 seq 去重（metadata 无 `seq` 字段）；断线恢复依赖既有快照机制（未专项核查）。
- 取消：`control_check`/`SubagentControlError` 存在于子循环安全点（`:1440-1450`），但 Legacy fan-out 执行循环（`chat_service.py:4793-4812`）未见 terminate 透传；超频路径有 deadline/terminate（`:2021-2029`）。

## 4. P1 问题核查

- **超时/重试**：`_run_child` 仅对 `timeout/failed` 且错误串含 timeout/502/503/504/5xx 时重试（`:740-758`），指数退避由 task.retry 控制，幂等键核对不存在；1200s/24 轮为全局默认，未按 source/mode 拆分。
- **计费**：`merge_token_usage` 跨轮跨子合并（`:432-434`），`cached_tokens` 合并单测存在（`test_fanout_merges_token_usage_across_rounds_and_children`）；方案提及的历史红灯在本轮未复跑（见 evidence_index「未复跑项」）。
- **装配性能**：prepare 内逐子任务串行 `assemble_context`（`:304-339`），N 个子任务 N 次串行 DB/装配，无 asyncio.gather。
- **审计**：子循环轮次经 AgentTeamsTurnRecorder 落审计；工具异常不回写敏感参数（截断 2000 字 args_summary）；workdir 绝对路径出现在 llm_payload.workdir（`_llm_view` `:1640-1641`），对父模型可见，符合内部但需注意外部泄露面。

## 5. 与资料包 §9 快照的漂移对照

| 快照断言 | 当前代码 | 漂移 |
|---|---|---|
| 单批 4 / semaphore 3 | 一致 | 无 |
| 父消息一次 accepted fan-out | 已由 FanoutAdmission 实现 | **快照后的修复** |
| shania 未标记 spawnable | 确认 | 无 |
| 超频 workspace_access 追加工作台工具 | 确认（`_OVERDRIVE_WORKSPACE_TOOL_NAMES`） | 无 |
| 子任务 SSE 复用超频泳道 | 普通 fan-out 已有独立 `subagents` chunk 相位 | **快照后的修复** |
| cached_tokens 单测红灯 | 存在合并单测；本轮未复跑 | 待 Gate 5 验证 |
| 工具关闭后仍暴露 / 前后台 gate 分裂 | 本轮未专项核查 | 列入 WP1 待办 |

## 6. WP1 待办（基于本审计）

1. ChildResult v2 + outcome evaluator（不改旧 status 字段，新增 execution/outcome/artifact 三态与 reason_code）。
2. 正文回灌：detail_ref 持久化 + 父轮短摘要引用 + `payload_truncated` 标记；统一两条入口（unified 预分派 vs 工具调用）的注入口径。
3. Capability preflight：task contract 声明 required capabilities，服务端按装配后有效工具求交，缺失即 blocked/CAPABILITY_MISSING。
4. 产物闭环：接通 `subagent_workdir` 消费方（workspace 工具写子目录）+ manifest（复用 `artifact_manifest.build_manifest`）+ 父发布 + 父回读 hash。
5. 配额幂等：request_key + payload digest 的 accept_once 语义（R04/R05）。
6. SSE：queued 事件（semaphore acquire 前后各发一帧）、seq 字段、子任务 started/finished 时间戳透出。
7. unified 预分派失败时向模型回传结构化失败信息（替代静默）。
8. schema `task` 描述 2000 字 ↔ 运行时 20000 字漂移修正。
