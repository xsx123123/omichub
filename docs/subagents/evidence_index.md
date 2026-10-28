# 子 Agent 审计证据索引（WP0）

> 日期：2026-10-28｜基线：分支 `feat/chat-message-queue` @ `51003efa`（工作区有未提交改动，与本域无关）。所有证据为静态代码证据 + 单测清单；未运行 E2E、未改动代码、未提权。

## A. 环境证据

| ID | 证据 | 位置/命令 |
|---|---|---|
| E-env-1 | 分支与 commit | `git rev-parse --short HEAD` → `51003efa`；branch → `feat/chat-message-queue` |
| E-env-2 | 工作区脏但无关 | `git status --short`：改动集中于 docs/配置/frontend 资产，子 Agent 相关源码 0 修改 |

## B. 配置与 schema 证据

| ID | 证据 | 位置 |
|---|---|---|
| E-cfg-1 | subagent 六项配置默认值 | `src/cygnusx/core/config.py:333-353` |
| E-cfg-2 | tools_schema maxItems=4 / minItems=1 / tasks 仅 agent_id+task | `tool_configs/tools_schema.yaml:85-112` |
| E-cfg-3 | schema task「2000 字」vs 运行时 `_TASK_INSTRUCTION_MAX_CHARS=20000` | `tools_schema.yaml:110` vs `parallel_subagent_service.py:124` |
| E-cfg-4 | spawnable 名单（12 个 true；manager/explorer false；shania 未声明） | `data/ai/*.yaml` grep `subagents_spawnable`；`data/ai/shania.yaml` 无该键 |

## C. 问题根因证据

| ID | 问题 | 根因位置 | 关键行 |
|---|---|---|---|
| E-p0-1 | 假成功 | `_child_loop` 文本收尾即 `status:"ok"`；`execute` 按 ok 计数 | `parallel_subagent_service.py:1074-1082, :428, :436-444`；guard 触发也返 ok `:1255-1280` |
| E-p0-2 | B/C/D 正文丢失 | 父轮回灌 12k 静默截断 | `chat_service.py:5761-5779`（`llm_limit=12000`，无 truncated 标记） |
| E-p0-3 | 正文不到前端 | ui_payload 无 answer 字段 | `parallel_subagent_service.py:450-462`；`chat_service.py:4829-4849`；`useAgentChatStream.ts:918-920` |
| E-p0-4 | 无 capability preflight | 无能力求交/blocked 语义 | `parallel_subagent_service.py:555-652`（仅过滤，无准入判定） |
| E-p0-5 | 产物闭环缺失 | workdir 消费方为零 | `subagent_workdir` 全仓 grep：仅 `parallel_subagent_service.py:1509` 1 处定义，0 消费 |
| E-p0-6 | 产物闭环缺失 | 无 manifest/发布/回读 | `artifact_manifest.py` 仅被 `chat_sandbox_tools.py:26` 与 `archive_storage.py:88` 使用；子服务仅 `normalize_tool_artifact_payload`（`:1603`） |
| E-p0-7 | 配额时机（已修复侧） | validate 先于 reserve | `chat/fanout_admission.py` 全文；`chat_service.py:4630-4741`；`langgraph_runtime.py:633-736` |
| E-p0-8 | 配额幂等缺失 | 无 request_key/digest | 全仓 grep `request_key` 于 fanout 域无命中；admission 无重放语义 |
| E-p0-9 | unified 预分派失败静默 | 仅 logger.warning | `chat_service.py:4172-4173` |

## D. SSE / UI 证据

| ID | 证据 | 位置 |
|---|---|---|
| E-ui-1 | 无 queued 事件：worker_started 在 acquire 后发 | `parallel_subagent_service.py:700-701` |
| E-ui-2 | 事件映射仅 started/retrying/done | `subagent_child_event_metadata` `:203-227` |
| E-ui-3 | 前端相位白名单与 status 映射（ok→succeeded） | `useAgentChatStream.ts:889-950` |
| E-ui-4 | 无 seq 去重字段 | `subagent_child_event_metadata` 与前端 case 'subagents' 均无 seq |

## E. 既有单测盘点（tests/unit/test_parallel_subagent_service.py，34 用例）

- 已覆盖：工具过滤/追加（598-662）、safe_only（662-768）、workspace 门控（622-661, 769-802）、MCP 子上下文（803-834）、失败隔离（835-867）、开关（868-912）、非 spawnable 拒绝（913-959）、超时（960-988）、轮内工具往返（989-1041）、缺参停止（1042-1088）、confirm 升级（1089-1127）、validation 规则（1128-1157）、prepare 无副作用（1158-1192）、schema maxItems 一致（1193-1203）、事件相位映射（1204-1227）、usage 合并（518-567）、长输出保留（215-239）、空响应重试（459-517）、JSON 围栏截断（1228-1234）。
- 未覆盖：R11 capability、R12 outcome、R13 伪产物、R15/R16 截断标记与 detail_ref、R17-R19 并行 spans、R21-R27 产物生命周期、R04/R05 幂等重放。

## F. 本轮未复跑/未核查项（如实列缺）

| 项 | 说明 |
|---|---|
| cached_tokens 合并回归 | 单测存在（`:518`），本轮未执行 pytest；Gate 5 复跑 |
| 工具开关关闭后暴露缝隙 | 方案 §1.1 提及，本轮未专项核查 R08 运行时行为 |
| 超频前后台 gate 一致性（R33） | 未专项核查 |
| 前端展示 ID ↔ registry ID 映射（agent-code vs code） | 需 DB registry 运行时确认 |
| 断线重连 snapshot/replay（R28） | 未专项核查 |
| 运行时有效工具 dump | 能力矩阵为静态推导，待 WP1 实测替换 |

## G. 复现指引（WP1 Gate 0 最小复现）

1. **假成功**：mock provider 返回「当前环境无 Python 执行器，未运行代码」文本（无工具调用）→ `execute()` summary 输出 `1/1 个子任务成功`。
2. **B/C/D 截断**：4 个子任务各返回 >4k 字 answer → 父轮回灌 JSON 在 12,000 字符处截断且无标记。
3. **无执行器**：普通 fan-out 派生 `code`，观察 `child_tools` 不含 `sandbox_execute`/`workspace_write`（单测 `test_child_tools_add_workspace_execution_only_after_explicit_access` 已静态佐证）。
4. **配额**：同轮先 5 任务（拒、不占）再 4 任务（受理）；第 6 任务集合再投（拒）；无重放语义（再投相同 4 任务被拒而非返回原 run）。
