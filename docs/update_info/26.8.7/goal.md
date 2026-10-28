# OmicHub Goal 模式与 Multi-Agent 自主闭环架构调研

> 调研日期：2026-08-07  
> 范围：当前 Chat / Studio / Agent 路由 / 工具调用 / 记忆 / 并行子 Agent / Overdrive / AgentTeams Case。  
> 结论先行：当前 `/goal` **真实进入模型上下文**，但它是“单轮目标提示”，不是可持久化、可续跑、可验收的 Goal 自主闭环模式。现有 multi-agent 能力已经足以作为基础，但需要新增 Goal 状态机、Continuation 调度器、终结工具和跨 Agent 工作单元协议，不能把循环简单塞进当前 SSE 请求。

---

## 1. 结论摘要

### 1.1 当前 `/goal` 到底做了什么

当前前端会从用户文本中解析：

```text
/goal 帮我汇总一下当前平台的功能呀
```

并把目标随本轮消息的 `metadata.star_command` 提交给后端；后端白名单化后持久化，再把以下上下文附加到**本轮送给 LLM 的最后一条用户消息**：

```text
[Star AI 命令上下文]
模式：chat | plan | run | research
权限：safe | read | analysis | full
模式规则：...
权限规则：...
当前用户目标：...
请严格遵守以上上下文，不要自行提升权限。
```

因此 `/goal` 不是无效 UI。它确实影响本轮模型输入；但是：

- `/goal` **不创建 `Goal` 实体**，没有 `goal_id`。
- `/goal` **不是独立 mode**；当前 mode 仍是 `chat`、`plan`、`run` 或 `research`。
- 它不保存 Goal 生命周期、成功标准、预算、轮次、暂停状态或完成证据。
- 它不会在工具调用后自行唤醒下一轮推理；当前循环结束后仍等待用户下一条消息。
- 后续用户消息若不再次带 `metadata.star_command`，系统没有“当前活动目标”的持久化注入机制。

对会话 `348ed550-b09b-470b-844b-55c88d11fca6` 的只读运行态核查证实：用户消息已持久化：

```json
{
  "goal": "帮我汇总一下当前平台的功能呀",
  "mode": "chat",
  "permission": "safe"
}
```

所以该请求真实使用的是 **Chat + Safe + Goal Hint**，并不是“Goal autonomous mode”。

### 1.2 当前 multi-agent 不是一种能力，而是四条能力链

| 链路 | 当前用途 | 执行模型 | 是否可作为 Goal 基础 |
|---|---|---|---|
| Router + `transfer_to_agent` | 单专家分诊与交接 | 同一会话中串行换 Agent | 可用于 Goal Manager 的专家切换 |
| `parallel_subagents` | 独立子任务 fan-out | 父 Agent 单次工具调用，受限子 ReAct 并行 | 最适合改造成 Goal 的并行 Work Unit |
| Overdrive | Manager 组织 Worker 的即时协作 | 当前请求/SSE 中的 manager-worker 编排 | 可作为 Goal 的前台交互与执行策略 |
| AgentTeams Case | 跨系统、长生命周期生信交付 | Bridge + Matrix/Element + Celery watch | 可作为需要外部流程/人工审批的“外部执行器” |

当前运行态快照（2026-08-07，只读聚合）：

- 活跃 Chat 会话：`135`。
- 已使用过 Overdrive 的会话：`7`。
- 带 `multi_agent` 标记的会话：`3`。
- 活跃 Agent：`10`；其中可作为子 Agent 分派的 Agent：`7`；Router Agent：`1`。
- 站点开关：`subagent_fanout_enabled=true`、`agentteams_chat_entry_enabled=true`、`agent_memory_enabled=true`；`multi_expert_consultation_enabled=false`、`unified_intent_router_enabled=false`。

这说明 multi-agent 基础设施不是概念验证，而是已经可用；Goal 设计应复用它，而不是重造第二套 Agent 框架。

### 1.3 推荐的目标态

引入一个**持久化 Goal Runtime**：

```text
用户 /goal start
  -> Goal API / GoalService 创建 Goal
  -> GoalExecutionEngine 领取 Goal lease
  -> Goal Manager 规划 Work Unit DAG
  -> 串行/并行执行 Worker、工具、Case
  -> Evaluator 检验 success_criteria 与证据
  -> goal_complete | goal_blocked
  -> 写入可审计结果，并把摘要回推聊天流
```

其中：

- Goal Manager 是唯一能改变 Goal 终态的角色。
- 子 Agent 只能提交结构化结果、阻塞或审批请求，不能直接完成/取消父 Goal。
- 所有外部副作用走现有权限与审批体系；Goal 不能绕过 `requires_confirm`、Studio HITL 或 AgentTeams Case 确认。
- Continuation 由后台队列驱动，不依赖用户浏览器长期持有 SSE。

---

## 2. 调研证据与范围

本文件以运行中代码与数据库只读查询为准，重点证据位置如下。

| 范畴 | 主要证据 |
|---|---|
| `/goal` 命令解析 | `frontend/src/components/ai-chat/commandState.ts` |
| 消息元数据发送 | `frontend/src/components/ai-chat/KimiChatInput.vue` |
| 流式入口 | `src/omichub/api/v1/chat.py` |
| Agent 主编排 / ReAct / Goal Hint 注入 | `src/omichub/application/services/chat_service.py` |
| Session / Message 持久化 | `src/omichub/infrastructure/database/models/chat.py` |
| Agent 上下文组装 | `src/omichub/application/services/agent_service.py` |
| 工具注册与桥接 | `src/omichub/tools/schema_loader.py`、`src/omichub/application/services/tool_bridge_service.py` |
| 长期记忆 | `src/omichub/application/services/agent_memory_service.py`、`src/omichub/infrastructure/database/models/agent_memory.py` |
| 并行子 Agent | `src/omichub/application/services/parallel_subagent_service.py` |
| AgentTeams / Case | `src/omichub/application/services/agentteams_*`、`src/omichub/api/v1/agentteams.py` |
| 已有风险审查 | `docs/26.8.7/01_跨模式共性问题.md`、`02_模式1_AI助手与路由.md`、`04_模式3_AgentTeams.md` |

本文中的“当前状态”是已实现代码或运行态数据；“建议”是待实施设计，二者明确区分。

---

## 3. 当前 Agent 框架架构

### 3.1 总体模块图

```text
Vue / Pinia
  KimiChatInput
    ├─ /chat /plan /run /research /safe /read /analysis /full
    └─ /goal <objective> -> message.metadata.star_command
              |
              v
POST /api/v1/chat/stream (SSE)
  src/omichub/api/v1/chat.py
              |
              v
ChatService.stream_agent_chat(...)
  ├─ Session / User message / AI placeholder
  ├─ AgentService.assemble_context(agent_id)
  │    ├─ Model config
  │    ├─ Agent system prompt + Skill prompt
  │    ├─ Builtin tools + MCP tools
  │    └─ Features / policy
  ├─ Router / handoff / Overdrive / fan-out decision
  ├─ LLM stream + tool-call ReAct loop
  ├─ ToolBridge / Studio tools / MCP / AgentTeams tools
  ├─ AgentMemory prompt context + async memory work
  └─ ChatChunk -> SSE text/tool_call/tool_output/tool_result/done
              |
              v
PostgreSQL
  chat_sessions / chat_messages / agent_memories / agent_templates
  + sandbox_meta(JSONB) / AgentTeams external Case state
```

### 3.2 核心模块与职责

| 模块 | 职责 | 关键说明 |
|---|---|---|
| `ChatStreamRequest` | 请求契约 | 包含 `messages`、`agent_id`、session、附件、MCP、`multi_agent`、`overdrive`、`extend_max_rounds`。 |
| `chat_stream` | SSE HTTP 边界 | 建立 `ChatService`，把 `ChatChunk` 编码成 SSE。当前在收到 `done` 后提交请求级 DB 会话。 |
| `ChatService` | 主编排器 | 保存消息、解析 metadata、路由、组装 LLM 输入、运行工具循环、生成 UI 事件、更新会话状态。 |
| `AgentService` | Agent 上下文工厂 | 将模板、模型、系统提示词、技能、内置工具、MCP、feature policy 组装为 `AgentContext`。 |
| Provider Manager | 模型适配 | 将 OpenAI-compatible provider 的流式文本/工具调用统一输出。 |
| `schema_loader` | 工具 schema 注册 | 将仓库内工具 schema 转为 OpenAI function tools，并提供系统提示词提示。 |
| `ToolBridgeService` | 受控工具执行 | 注入 `ToolInvocationContext`，执行 builtin/MCP 类工具并生成 LLM/UI payload。 |
| Studio tools | 工作区执行 | 沙盒读写、命令执行、产物等，能流式推送 `tool_output`。 |
| Memory service | 跨会话记忆 | 提供 profile/preference/project/summary 等作用域的检索、写入与 prompt context。 |
| Parallel subagent | 请求内 fan-out | 对独立任务建立临时子 ReAct 循环，结果回到父 Manager。 |
| AgentTeams | 外部协作 Case | 创建/管理跨系统 Case、Matrix room、Bridge 事件、Celery watch。 |

### 3.3 当前生命周期与循环机制

当前不是“后台持续自主任务”，而是**一条用户请求驱动的 SSE ReAct 循环**：

1. 前端把消息、附件、用户控制元数据送到 `POST /chat/stream`。
2. `ChatService.stream_agent_chat` 创建或加载 `chat_sessions`；用户消息和 AI 占位消息进入 `chat_messages`。
3. 解析用户消息 `metadata`：仅允许的字段（如 `star_command`、确认标记）会被白名单保留。
4. `AgentService.assemble_context` 取得当前 Agent 的模型、Prompt、MCP 和工具列表。
5. 如启用 Router，选择目标 Agent；如启用 Overdrive / multi-agent，进入对应即时编排分支。
6. 对 LLM 发起流式请求；文本 token 直接转成 SSE `text`。
7. 若模型返回 tool call：推送 `tool_call`，受控执行工具，推送 `tool_output` / `tool_result`，并把结构化工具结果回灌模型上下文。
8. 重复第 6–7 步，默认工具轮次上限为 `100`；用户确认扩展时可到 `1000`。
9. 结束时更新 AI 消息、会话 token、模型信息，并推送 `done`。
10. SSE 生成器完成后，HTTP 层提交请求级 DB 事务。

关键边界：

- `ask_user`、HITL 审批或外部 Case 会让当前链路等待用户/外部状态；没有一个持久化的 continuation scheduler 来在“下一步已知”时自动重入模型。
- 浏览器 `AbortController` 能停止当前流；现有审查已指出长 SSE + 请求级事务、会话并发锁不足等风险。Goal Runtime 必须先规避这些边界，不能复用长请求作为永久循环容器。

### 3.4 Session、Context、Memory 与工具结果

#### Session / Message

| 存储 | 当前字段/用途 | Goal 缺口 |
|---|---|---|
| `chat_sessions` | `session_id`、agent/model、`mode`、`workspace_id`、`sandbox_meta`、时间与计数 | 没有活动 `goal_id`、Goal 状态、预算或 lease。 |
| `chat_messages` | `role`、内容、状态、`metadata_json`、创建时间 | 可保存 `star_command`，但只是一条消息元数据，不能表达 Goal 生命周期。 |
| `sandbox_meta` | Studio / Overdrive / Case 的多类 JSON 元数据 | 已存在并发 read-modify-write 风险，不适合继续堆 Goal 高频状态。 |

#### Prompt Context

当前每轮主要由以下部分组成：

```text
Agent system prompt
+ Skill / MCP / workspace prompt suffix
+ 当前会话 messages（经脱敏）
+ 当前 user message 的 Star command context（可选）
+ 附件多模态内容
+ 长期记忆检索块（可选）
+ 工具调用及结果回灌
```

当前 `AgentMemoryService.build_prompt_context()` 以用户、Agent、项目和 scope 构建受限记忆块；它适合“偏好/事实/项目摘要”，但不是 Goal 的强一致进度账本。

#### 工具结果

工具调用既有两类表达：

- 给模型：`llm_payload`，作为下一轮 reasoning 的证据。
- 给前端：`ui_payload` 和 SSE 事件，用于 tool card、进度、审批、产物等展示。

这为 Goal 提供了重要基础：Goal 引擎不应重做工具执行；应把“本次工具调用属于哪个 Goal / Work Unit / Attempt”写入审计上下文，并将已有 payload 投影为 Goal 事件。

### 3.5 工具注册与执行机制

```text
工具 schema 文件 / 内置 schema
  -> schema_loader.to_openai_tools()
  -> AgentService.assemble_context()
  -> Provider 的 function calling
  -> ChatService 解析 tool_calls
  -> ToolInvocationContext(user/session/agent/db/permission/extra)
  -> ToolBridgeService 或专用分支
  -> result.llm_payload + result.ui_payload
  -> 模型回灌与 SSE
```

专用分支包括 Studio 代码工具、`parallel_subagents`、AgentTeams Case 工具、审批工具等。当前 `ParallelSubAgentService` 特意绕过 ToolBridge 的短 payload 包装，以防多子任务结果被截断；这是未来 Goal Work Unit 汇总需要保留的经验。

---

## 4. 当前 `/goal`：事实、效果与 Gap

### 4.1 现有命令协议

前端 `commandState.ts` 当前定义：

| 命令类别 | 值 |
|---|---|
| Mode | `/chat`、`/plan`、`/run`、`/research` |
| Permission | `/safe`、`/read`、`/analysis`、`/full` |
| Goal | `/goal <单行目标>` |

`/goal` 使用正则从本行提取文本；`resolveStarCommandContext()` 把 mode / permission 回退到前端当前选择，并把 goal 作为可选字段。`KimiChatInput` 仅当有 Star 上下文时发送 `messageMetadata.star_command`。

### 4.2 后端消费与安全边界

后端 `_extract_user_message_metadata()`：

- 校验 mode 只能为 `chat/plan/run/research`。
- 校验 permission 只能为 `safe/read/analysis/full`。
- 限制 goal 为非空字符串，最大 `500` 字符。
- 只持久化白名单化后的 JSON。

在进入 LLM 前，`ChatService` 从当前 `user_metadata.star_command` 读取值，并在最后一条用户消息上追加 mode、permission、goal 和“不自行提升权限”的约束。

### 4.3 它已经提供的价值

1. 目标不会只是前端标签，而会影响实际模型 prompt。
2. 与权限组合后能阻止“目标很激进，但本轮权限是 safe”的越权执行。
3. 不需要迁移即可为轻量、单轮目标引导服务。
4. 现有 UI 已能展示 Goal context tag，便于用户看见本轮控制信号。

### 4.4 它尚未满足的 Goal Mode 能力

| 能力 | 当前 `/goal` | Goal Runtime 应有能力 |
|---|---|---|
| 目标 ID | 无 | 每个目标有稳定 `goal_id`。 |
| 生命周期 | 无 | Pending / In progress / Waiting user / Paused / Completed / Blocked / Cancelled。 |
| 成功标准 | 无 | 显式字段、可评估、可展示。 |
| 自主续跑 | 无 | 每次工具结果、Worker 完成、Case 状态变化均可产生 continuation。 |
| 完成证据 | 仅自然语言回复 | 终结工具提交结构化 evidence / artifact refs / criteria evaluation。 |
| 暂停、恢复、取消 | 无 | 用户命令与安全策略共同控制。 |
| 预算 | 仅单请求 max rounds | Goal 级 turn / token / wall-clock / tool-cost 预算。 |
| 多 Agent 协作 | 仅当前请求级能力 | 持久 Work Unit、依赖、负责人、结果汇总与复核。 |
| 重启恢复 | 无 | 进程/浏览器重启后从数据库和队列恢复。 |

### 4.5 与现代自治 Agent Runtime 的对照

本节对照的是成熟编码/研究 Agent 常见的**运行时抽象**，不是要求 OmicHub 复制任何特定产品的 UI、SDK 或私有实现。无论是 CLI 型 coding agent 还是研究型 autonomous agent，稳定的 Goal 闭环通常都具备以下共性：

| 通用能力 | 成熟自主 Runtime 的抽象 | OmicHub 当前对应物 | Goal 改造目标 |
|---|---|---|---|
| 显式目标 | Objective 与 done definition 是状态，不只是 prompt 文本 | `/goal` metadata hint | 持久 `agent_goals.objective + success_criteria`。 |
| 连续推进 | 工具结果/子任务结果可驱动下一次决策 | 当前 ReAct 只在单个 SSE 请求内循环 | `Continuation Loop Engine` 以事件驱动短任务续跑。 |
| 终结信号 | 由专门终结动作声明完成/阻塞 | 只有自然语言最终回答 | `goal_complete` / `goal_blocked` + Evaluator。 |
| 上下文压缩 | 保留任务事实和证据，压缩低价值历史 | 会话文本和记忆各自存在 | GoalContextPacket + 版本化 compaction。 |
| 安全边界 | 预算、权限、人工确认是控制面 | mode/permission、ToolBridge、HITL 已存在 | Goal 复用并强化为 Goal 级限制。 |
| 子 Agent | 有负责人、边界、结果回传和汇总 owner | `parallel_subagents` 已有受限 worker | Work Unit DAG + Manager-only terminal 权限。 |
| 可恢复性 | 进程/终端中断后可从状态恢复 | 当前聊天依赖请求/SSE 生命周期 | DB event log、lease、幂等 continuation。 |

因此最重要的差距不是“再加一个 `/goal` 提示词”，而是把目标、工作单元、事件、预算和终结证据从瞬时对话文本提升为可恢复的运行时状态。

---

## 5. 现阶段 multi-agent 架构与边界

### 5.1 Router + Handoff：串行专家切换

`ChatService._route_to_agent()` 会通过 Router 判断意图，获取目标 `AgentContext`；`transfer_to_agent` 则把会话交给白名单中的下一位 Agent，并保存 handoff 审计信息。它适用于“谁最适合回答下一步”，而不是并行执行。

优点：

- 同一 session，用户体验连续。
- 已有 Agent 身份、模型、Prompt 与权限链路。
- 可将 Goal Manager 在阶段间换成特定领域专家。

限制：

- 当前每个用户消息可能重新路由；没有 Goal 层的 owner 固化与阶段性责任边界。
- handoff 是对话上下文概念，不是可调度任务实体。

### 5.2 `parallel_subagents`：受控并行 fan-out

这是与 Goal 最接近的现有能力。父 Agent 提交 `{agent_id, task}` 列表，服务为每个子任务建立独立 AsyncSession 与受限子 ReAct 循环，然后将结构化摘要汇总回父上下文。

已实现的重要安全约束：

- 子循环不共享父 `AsyncSession`。
- 移除递归 `parallel_subagents`，深度固定为 `1`。
- 移除 `transfer_to_agent`、创建 AgentTeams Case、写/改/删长期记忆等控制工具。
- `ask_user` 与 `requires_confirm` 升级回父 Manager。
- 工具结果和回答有长度上限；子任务有并发与轮次限制。
- 可把子任务产物隔离到子目录。

这说明未来不应从零开发 Worker sandbox；应该将 `parallel_subagents` 扩展为可持久化的 `GoalWorkUnit` 执行器。

### 5.3 Overdrive：请求内 Manager / Worker 即时协作

Overdrive 以会话开关形式存在。当前 Chat Service 会选择 Manager，并从标记 `subagents_spawnable` 的 Agent 中构建候选目录；Manager 决定拆分任务，子 Worker 的进度和结果以 sender/worker 事件回到聊天流。

它的优势是交互强、前端已有可视化；但它仍属于当前 `/chat/stream` 请求的生命周期。浏览器断流、请求取消、单轮预算耗尽、SSE 事务边界都会影响它，不可直接等价为后台 Goal Runner。

### 5.4 AgentTeams Case：长生命周期外部工作流

AgentTeams 支持创建 Case、前置检查、人工提交任务、事件流、Matrix/Element 房间和 Celery 定期 watch。它适合运行时间长、外部系统参与、需要审批的生信流程。

它不是通用 Goal engine：Case 以具体 flow/project 为中心，状态来自 Bridge；但 Goal 可以把它视作一种**外部 Work Unit executor**。例如：Goal Manager 创建 Case 后进入 `WAITING_EXTERNAL`，收到 watch 事件后再发 continuation 给 Manager 进行验收或下一步。

### 5.5 当前已知风险，Goal 不能继承

已在本目录既有审查中记录的风险，需要成为 Goal Phase 0 的前置条件：

1. `/chat/stream` 目前存在请求级长事务问题；不能让 Goal 的无限续跑继续扩大事务长度。
2. 同一 session 的服务端并发锁仍是必要能力；Goal continuation 与用户消息必须串行化。
3. `sandbox_meta` 已承载多种并发更新，不能继续写入 Goal event cursor、lease、progress 等高频状态。
4. Case / room / watch 的外部事件需要幂等、立即提交和可恢复 cursor。
5. 任何“自动继续”都必须通过现有高风险工具审批策略，不能因 Goal 状态为 IN_PROGRESS 而自动放权。

---

## 6. 目标态：Goal State Model

### 6.1 状态机

```text
PENDING
  -> IN_PROGRESS
  -> WAITING_USER        (ask_user / approval / missing input)
  -> WAITING_EXTERNAL    (AgentTeams Case / 异步任务)
  -> PAUSED              (用户暂停 / 预算保护)
  -> COMPLETED           (终结工具 + Evaluator 通过)
  -> BLOCKED             (终结工具 + 阻塞证据)
  -> CANCELLED           (用户取消)
  -> FAILED              (不可恢复系统错误 / 预算耗尽)

WAITING_* / PAUSED -> IN_PROGRESS
IN_PROGRESS -> COMPLETED | BLOCKED | FAILED | PAUSED | WAITING_*
```

`PENDING / IN_PROGRESS / COMPLETED / BLOCKED` 是对外最小必备集合；`WAITING_USER`、`WAITING_EXTERNAL`、`PAUSED`、`CANCELLED`、`FAILED` 用于避免把不同原因混进 `BLOCKED`。

### 6.2 新增表

#### `agent_goals`

| 字段 | 说明 |
|---|---|
| `goal_id` | UUID / 对外稳定 ID。 |
| `session_id`, `user_id`, `project_id` | 所属边界与授权检查。 |
| `parent_goal_id` | 支持未来目标分解，但第一期不允许无限嵌套。 |
| `objective` | 用户确认的目标原文。 |
| `success_criteria` | JSON 列表：可验证条件、权重、是否必须。 |
| `status`, `status_reason` | 状态机与可展示原因。 |
| `mode`, `permission` | 创建时固定的执行契约；升权必须生成审批事件。 |
| `manager_agent_id` | Goal Owner；只有它可发终结工具。 |
| `plan_snapshot` | 版本化计划摘要，不存高频日志。 |
| `turn_count`, `token_budget`, `tokens_used`, `max_turns`, `deadline_at` | 预算和限额。 |
| `lease_owner`, `lease_expires_at`, `version` | 分布式领取与乐观锁。 |
| `created_at`, `started_at`, `completed_at`, `updated_at` | 审计时间线。 |

#### `agent_goal_work_units`

| 字段 | 说明 |
|---|---|
| `work_unit_id`, `goal_id` | 工作单元身份与归属。 |
| `kind` | `llm_step` / `parallel_fanout` / `agentteams_case` / `tool_wait` / `evaluation`。 |
| `title`, `instruction`, `depends_on` | DAG 节点与依赖。 |
| `owner_agent_id`, `attempt` | 负责人和重试。 |
| `status` | Pending / Running / Waiting / Succeeded / Failed / Blocked / Skipped。 |
| `input_ref`, `output_ref`, `evidence_refs` | 大文本/产物使用引用，避免 JSONB 无限增长。 |
| `started_at`, `finished_at` | 调度与可观测性。 |

#### `agent_goal_events`

不可变 append-only 事件表：`created`、`planned`、`continued`、`tool_started`、`tool_finished`、`worker_result`、`waiting_user`、`budget_exhausted`、`terminal_claimed`、`completed`、`blocked` 等。它既是 UI 时间线来源，也是恢复和审计依据。

#### `agent_goal_artifacts`（可选但推荐）

统一关联 Studio artifact、报告、Case、文件、URL、评估证据。避免只把路径藏入对话文本。

### 6.3 Session 的改造原则

第一阶段采用严格的非侵入式方案：**不修改 `chat_sessions`、`chat_messages` 的既有字段和接口契约**。Goal 与会话的关联由新增的 `agent_goals.session_id`、`user_id` 以及状态索引表达；读取某个会话的活动 Goal 时查询 Goal 表，而不是给旧表增加 `active_goal_id`。

其余 Goal 状态放新表。不要把 `goal_runs`、cursor、worker progress 或 event list 继续塞进 `sandbox_meta`。如果未来为了列表查询需要冗余引用，也只能作为可重建的投影字段，在独立迁移和回滚方案明确后再评估，不能成为 Goal 正确性的单一来源。

---

## 7. Continuation Loop Engine

### 7.1 为什么不能直接 while True + SSE

当前 SSE 是用户浏览器请求的响应。用它承载 Goal 无限循环会导致：

- 浏览器断开即中止后台工作。
- 请求级 DB 会话与事务被长时间占用。
- 用户消息、自动 continuation、Case watch 回调会互相竞争同一会话。
- 无法可靠实现延迟重试、暂停、恢复、进程重启恢复和预算治理。

因此 Goal Engine 必须是“**短事务 + 可恢复后台 job + 前端订阅事件**”。

### 7.2 调度模型

```text
GoalCommand API / Chat `/goal start`
  -> GoalService.create_goal()             # 短事务，立即提交
  -> enqueue(goal_id, cause='created')

Celery / Redis worker
  -> GoalExecutionEngine.run_once(goal_id, cause)
  -> acquire_lease(goal_id, version)
  -> load GoalContextPacket
  -> run one bounded manager decision step
  -> persist events / work units / status  # 短事务
  -> enqueue next continuation if needed

SSE / WebSocket
  -> 只订阅 agent_goal_events
  -> 浏览器断开不停止 Goal
```

`run_once` 必须有边界：一次只处理一个 manager decision、一个可同步工具链或一个已完成 Work Unit 的汇总。不要让一个 Celery task 自己无限 ReAct。

### 7.3 Continuation 触发源

| 事件 | 触发的下一步 |
|---|---|
| Goal 创建 | Manager 产出计划 / 首个 Work Unit。 |
| 同步工具完成 | Manager 评估结果，决定完成、重试、拆分或下一步。 |
| 并行子代理全部结束 | 汇总结果并调度 Manager。 |
| `ask_user` / HITL 审批 | 状态进入 `WAITING_USER`；用户决议后继续。 |
| AgentTeams / 异步任务事件 | 状态进入 `WAITING_EXTERNAL`；事件幂等落库后继续。 |
| 预算/Deadline 告警 | Manager 收敛、请求用户扩预算，或进入 `PAUSED/BLOCKED`。 |
| 用户 `/goal resume` | 重新入队，使用相同 Goal ID。 |

### 7.4 幂等与并发

必须具备：

1. Redis Goal lease，例如 `goal:{goal_id}:lease`，并设置心跳/TTL。
2. 数据库 `version` 乐观锁，防止旧 Worker 覆盖新状态。
3. 每个 continuation event 有 `event_id` / `dedupe_key`。
4. 用户手工发消息与 Goal continuation 的调度优先级和冲突策略：默认人工命令优先，Goal 自动步骤退让。
5. 同一 Work Unit 的 side effect 使用 idempotency key；尤其是 Case 创建、任务提交、文件写入。

---

## 8. Terminal Tools 与 Evaluator

### 8.1 新增终结工具

```python
GOAL_COMPLETE_TOOL = {
    "type": "function",
    "function": {
        "name": "goal_complete",
        "description": "仅当所有必需成功标准均有证据支持时，提交 Goal 完成声明。",
        "parameters": {
            "type": "object",
            "properties": {
                "summary": {"type": "string"},
                "criteria_results": {"type": "array"},
                "evidence_refs": {"type": "array", "items": {"type": "string"}},
                "remaining_risks": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["summary", "criteria_results", "evidence_refs"],
        },
    },
}

GOAL_BLOCKED_TOOL = {
    "type": "function",
    "function": {
        "name": "goal_blocked",
        "description": "仅当目标无法继续且需要用户或外部条件介入时，提交结构化阻塞声明。",
        "parameters": {
            "type": "object",
            "properties": {
                "reason": {"type": "string"},
                "blocked_by": {"type": "string", "enum": ["user", "approval", "external", "budget", "policy", "system"]},
                "required_input": {"type": "string"},
                "evidence_refs": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["reason", "blocked_by"],
        },
    },
}
```

### 8.2 不信任模型的终结声明

终结工具不是直接改数据库状态：

```text
Manager 调用 goal_complete
  -> GoalTerminalService.validate_claim()
  -> GoalEvaluator.evaluate()
  -> 所有 required criteria 通过且 evidence 可解析
       -> COMPLETED
     否则
       -> IN_PROGRESS，创建“补齐证据”Work Unit
```

第一期 Evaluator 可以是确定性检查：

- 必需 criteria 都被提交。
- 每个 criteria 至少有一个有效 evidence reference。
- 引用的 artifact / tool result / case / message 确实属于该 Goal。
- 没有未处理的 `WAITING_USER` / `PENDING_APPROVAL` work unit。
- 预算没有被越过。

第二期再引入 LLM reviewer，但 reviewer 只能提出“缺口”或“通过建议”，最终状态仍由服务端策略决定。

---

## 9. Context Engineering 与 Compaction

### 9.1 GoalContextPacket

每个 Manager 和 Worker 的系统上下文都必须从稳定结构重建：

```python
@dataclass(frozen=True)
class GoalContextPacket:
    goal_id: str
    objective: str
    success_criteria: list[GoalCriterion]
    status: GoalStatus
    mode: GoalMode
    permission: GoalPermission
    manager_agent_id: str
    budget: GoalBudget
    plan_summary: str
    completed_work_units: list[WorkUnitDigest]
    open_work_units: list[WorkUnitDigest]
    blocking_state: BlockingState | None
    artifact_refs: list[ArtifactRef]
```

不把 Goal 仅保存在“某一轮用户文本”中；每次 continuation 都从数据库加载并注入系统层或最高优先级受控上下文。

### 9.2 分层上下文与压缩

| 层级 | 内容 | 策略 |
|---|---|---|
| L0 不可丢 | objective、criteria、permission、预算、终态约束 | 每轮完整注入。 |
| L1 当前计划 | DAG、进行中/依赖未完成单元 | 结构化摘要，完整保留。 |
| L2 近期执行 | 最近 N 个决策、工具结果、失败原因 | token 配额内保留原文。 |
| L3 历史 | 已完成阶段的原始对话/大工具输出 | 写 event/artifact storage，仅注入可验证摘要与 refs。 |
| L4 长期记忆 | profile / preference / project facts | 继续复用 `AgentMemoryService`，但不承担 Goal 状态。 |

压缩应是事件驱动、版本化的 `goal_compaction` 产物；禁止覆盖原始审计事件。每次摘要要标明覆盖的 event 序号区间，Evaluator 可以回查原始证据。

### 9.3 Prompt 锁定模板

```text
## Goal Runtime Contract
你是 Goal {goal_id} 的 {manager|worker|reviewer}。

目标：{objective}
成功标准：{success_criteria}
当前状态：{status}
权限上限：{permission}
剩余预算：{budget}

不可违反：
1. 不得修改目标、成功标准或权限；若需要变更，使用 goal_request_change。
2. 只能处理分配给你的 Work Unit；Worker 不得结束父 Goal。
3. 所有外部副作用必须使用受控工具，并遵循审批策略。
4. 使用证据引用表达结论，不把猜测标记为完成。
5. 只有 Manager 可调用 goal_complete / goal_blocked。
6. 目标尚未达到且无阻塞时，必须选择下一项可执行工作，不要向用户无意义地等待。
```

---

## 10. Multi-Agent Goal 模式设计

### 10.1 角色与所有权

```text
                    +---------------------+
                    |  Goal Manager        |
                    |  owns state/terminal |
                    +----------+----------+
                               |
             +-----------------+-----------------+
             |                 |                 |
             v                 v                 v
      Planner / Router      Worker A          Worker B
      (可选)               (domain/tool)     (domain/tool)
             |                 |                 |
             +-------- Work Unit results --------+
                               |
                               v
                    Evaluator / Policy Gate
                               |
                    completed | blocked | continue
```

规则：

- Goal Manager 对 `agent_goals` 有唯一写权限。
- Planner 可以由 Manager 自己承担；第一期不要强制再加一个 LLM。
- Worker 运行已有 Agent Template；每个 Worker 得到最小必要 Goal Context 和自己的 Work Unit。
- Reviewer / Evaluator 不执行副作用，不能提升权限。
- `parallel_subagents` 的 `ask_user`、审批和高风险操作继续升级回 Manager，保持当前安全约束。

### 10.2 Work Unit DAG

示例：

```text
G: “完成 RNA-seq 差异表达并交付可复现报告”

W1 读取元数据与输入检查                 (worker: RNA QC)
W2 确认对照组、阈值、注释版本             (worker: Manager / ask_user)
W3 运行质控与比对                         (depends_on: W1,W2)
W4 定量和差异表达                         (depends_on: W3)
W5 生成图表/报告                          (depends_on: W4)
W6 验收：产物存在、指标完整、标准满足     (depends_on: W5, evaluator)
```

满足依赖的节点才可以进入队列；相互独立节点可以复用现有 `parallel_subagents` 受限 fan-out。跨系统流程则生成 `agentteams_case` Work Unit，而不是让 Worker 直接无限等待。

### 10.3 与既有能力的映射

| Goal 能力 | 复用现有实现 | 必须新增 |
|---|---|---|
| Manager Agent Context | `AgentService.assemble_context` | Goal prompt suffix / owner 校验。 |
| Worker 并行 | `ParallelSubAgentService` | Work Unit 持久化、结果关联、重试策略。 |
| 专家切换 | Router / handoff | Goal 阶段路由策略、owner 固化。 |
| 工作区工具 | Studio tools / ToolBridge | Goal idempotency key、产物归属。 |
| 外部流水线 | AgentTeams Case | Case -> continuation event adapter。 |
| 长期偏好 | AgentMemoryService | Goal-specific compaction，不污染长期记忆。 |
| 前端时间线 | 现有 SSE tool/event cards | Goal event feed、控制按钮、恢复状态。 |

### 10.4 禁止的实现方式

1. 不在 `stream_agent_chat` 末尾递归调用自己来实现自动续跑。
2. 不让子 Agent 直接写 `chat_sessions.sandbox_meta` 表示完成。
3. 不通过“模型说我完成了”直接标记 COMPLETED。
4. 不让 Goal 自动批准 `requires_confirm`、文件删除、费用型任务或 Case 提交。
5. 不在每次 continuation 重放全部聊天历史和所有工具原文。
6. 不通过前端定时 `sendMessage('继续')` 驱动系统；浏览器不是调度器。

---

## 11. 用户命令、控制面与 HITL

推荐命令协议（兼容当前 `/goal <text>`）：

| 命令 | 行为 |
|---|---|
| `/goal <objective>` | 第一阶段保持现状：单轮 Goal Hint；功能开关开启后可显示“转为持久 Goal”确认。 |
| `/goal start <objective>` | 创建持久 Goal，默认 `safe`，必须带成功标准或先进入 intake。 |
| `/goal status [id]` | 展示状态、当前 Work Unit、预算、阻塞、证据。 |
| `/goal pause [id]` | 停止派发新的 continuation；不杀不可中断外部任务。 |
| `/goal resume [id]` | 通过 lease 重新入队。 |
| `/goal cancel [id]` | 终止未开始单元；对已提交外部任务创建补偿/取消请求。 |
| `/goal criteria <...>` | 修改成功标准，产生版本化 change request；不原地覆盖。 |
| `/goal adopt <session>` | 将已有会话/Studio 产物作为 Goal 初始上下文，需用户确认。 |

### 11.1 安全策略

| 风险 | 处理 |
|---|---|
| max turns | Goal 级默认 `20` 个 manager decision；每个 Work Unit 再有独立重试限制。 |
| Token 预算 | 默认上限按部署策略配置；达到 80% 进入 `budget_warning`，达到上限暂停。 |
| wall-clock deadline | 建议默认 30 分钟；外部 Case 例外但需明确 `WAITING_EXTERNAL`。 |
| 高风险工具 | 继续使用 `ToolBridge` / Studio approval；Goal 只记录等待，不能自动确认。 |
| 用户输入 | `ask_user` 生成结构化 `WAITING_USER`，收到指定 answer event 后恢复。 |
| 并发 | 每 Goal 单 lease；用户手工聊天可插队或选择“将消息作为 Goal 指令”。 |
| 失败 | 可重试错误有退避和 attempt；不可重试转 `BLOCKED/FAILED`，携带证据。 |

---

## 12. 具体实施路线图

### Phase 0：先补自治运行前置条件

这些事项不能被 Goal 绕过：

1. 会话级 Redis 流式锁与 409 冲突契约。
2. 将 Goal 高频状态从 `sandbox_meta` 分离。
3. 确认用户消息、审计事件、Goal 事件使用短事务/独立 session 提交。
4. SSE heartbeat、可恢复事件 cursor、前端退避重连。
5. 明确 AgentTeams Case / room callback 的幂等键和提交边界。

### Phase 1：单 Agent 持久 Goal（不做自动写副作用）

1. 新建 migration 与 Goal ORM / repository / schemas。
2. 实现 `/goals` API 与 `/goal start/status/pause/resume/cancel` command parser。
3. 实现 `GoalExecutionEngine.run_once`，只支持 Manager + 只读/安全工具。
4. 新增 `goal_complete`、`goal_blocked`，做确定性 evaluator。
5. 建立 `agent_goal_events` SSE，前端增加 Goal timeline / 状态卡。
6. 覆盖创建、暂停、恢复、重启恢复、预算耗尽与阻塞测试。

**2026 年 8 月 7 日已落地（第一期核心）**：新增 `agent_goals`、`agent_goal_work_units`、`agent_goal_events` 及迁移；新增 `/api/v1/goals/start`、查询、暂停、恢复、取消和“DB cursor 恢复 + Redis Pub/Sub 即时投递”的 SSE；Celery 以 DB lease 驱动单步 continuation，并复用 `ChatService.stream_agent_chat` 执行 Manager 回合。`goal_complete` / `goal_blocked` 只在 Goal Manager 回合动态暴露，服务端会校验 Goal 归属和逐条 evidence；普通自然语言完成宣称不会结束 Goal。

**2026 年 8 月 7 日已落地（Phase 3 fan-out 子集）**：`GOAL_FANOUT_ENABLED=true` 时，Goal Manager 可调用既有 `parallel_subagents`；Goal adapter 会为一次 fan-out 建立父 `parallel_fanout` Work Unit 和逐 Worker 的 `parallel_worker` Work Unit，保存输入、attempt、幂等键、聚合输出、Worker answer/workspace evidence，并写入 `fanout_started`、`worker_result`、`fanout_finished` 事件。Goal Worker 继续禁止递归 fan-out、控制工具、写入/执行类 workspace 工具以及无法证明只读的 MCP 工具。AgentTeams Case adapter 仍属于后续阶段，不能误称为已经交付。

第一期启动契约固定为 `mode=chat`、`permission=safe`，并仅向 Goal 回合暴露明确只读的工具及终结工具；`studio`、非安全权限、写入与外部提交仍由后续 HITL 阶段处理。

`ask_user` 会把 Goal 置为 `waiting_user` 并持久化请求；用户只能通过 `POST /api/v1/goals/{goal_id}/answer` 提交审计化回答来恢复续跑，不能用普通 `resume` 跳过该输入。

### Phase 2：接入 Studio 与受控副作用

1. Work Unit 关联 Studio artifact / workspace path。
2. 任何写工具都走现有审批；等待审批时进入 `WAITING_USER`。
3. 引入 context compaction、artifact evidence 和完整可复现报告。
4. 支持将普通 `/goal <text>` 提示显式升级为 persistent Goal。

### Phase 3：接入 parallel subagents / Overdrive

1. 将 fan-out task 映射到 `agent_goal_work_units`。
2. 父 Goal 负责 Worker 派发与结果汇总；保留既有“禁止递归/控制工具上收”约束。
3. Worker result 转化为 `worker_result` 事件；Manager 得到 continuation。
4. 加入 DAG、失败隔离、重试、最大并发和 reviewer。

当前完成第 1～3 项的基础闭环，并复用既有 fan-out 的失败隔离、超时和并发上限；通用 DAG 调度、Goal 级重试策略与 reviewer 尚未交付。

### Phase 4：接入 AgentTeams Case

1. `create_agentteams_case` 创建关联 Work Unit。
2. Case watch 事件以 idempotency key 写入 Goal event。
3. Goal 在外部 Case 运行时进入 `WAITING_EXTERNAL`。
4. Case 成功后由 Manager/Evaluator 验收，并决定下一步或终结。

---

## 13. 文件变更清单

### 13.1 新增

| 文件 | 职责 |
|---|---|
| `alembic/versions/<rev>_add_agent_goals.py` | 只新增 Goal / Work Unit / Event / Artifact 表及索引，不改写旧聊天表。 |
| `src/omichub/infrastructure/database/models/goal.py` | SQLAlchemy Goal 模型。 |
| `src/omichub/application/schemas/goal.py` | API、命令、事件 DTO。 |
| `src/omichub/application/services/goal_service.py` | 创建、读取、控制、状态转换和审计。 |
| `src/omichub/application/services/goal_execution_engine.py` | 短生命周期 `run_once` continuation engine。 |
| `src/omichub/application/services/goal_evaluator.py` | 成功标准和 terminal claim 验证。 |
| `src/omichub/application/services/goal_context_service.py` | ContextPacket、压缩与 prompt 注入。 |
| `src/omichub/application/services/goal_work_unit_service.py` | DAG、claim、fan-out / Case adapter。 |
| `src/omichub/application/services/goal_terminal_tools.py` | `goal_complete` / `goal_blocked` 工具实现。 |
| `src/omichub/infrastructure/celery_app/tasks/goals.py` | continuation、超时、预算 watchdog。 |
| `src/omichub/infrastructure/cache/goal_pubsub.py` | Goal event pub/sub。 |
| `src/omichub/api/v1/goals.py` | Goal REST / SSE 控制面。 |
| `frontend/src/api/goals.ts` | Goal API client。 |
| `frontend/src/stores/goalRuntime.ts` | Goal 事件与控制状态。 |
| `frontend/src/components/ai-chat/GoalStatusCard.vue` | Chat / Studio 状态卡。 |
| `frontend/src/components/ai-chat/GoalTimeline.vue` | 事件/Work Unit 时间线。 |

### 13.2 修改

| 文件 | 改造 |
|---|---|
| `frontend/src/components/ai-chat/commandState.ts` | 解析 `/goal start/status/pause/resume/cancel`，保留旧 `/goal <text>` 兼容。 |
| `frontend/src/components/ai-chat/KimiChatInput.vue` | Goal command UX、状态入口、控制事件。 |
| `frontend/src/stores/agentHub.ts` | Goal SSE 订阅与普通消息/Goal 控制分流。 |
| `src/omichub/api/v1/chat.py` | 零修改；普通 Chat 和旧 `/goal <text>` 继续走原生 SSE 链路。 |
| `src/omichub/application/services/chat_service.py` | 零修改为优先；Goal Runtime 通过稳定的单轮执行边界或独立调用适配，不在此处实现无限循环。 |
| `src/omichub/application/services/parallel_subagent_service.py` | 零修改为优先；由 `goal_adapters/fanout_adapter.py` 复用其公开能力，并在 Goal 侧记录 Work Unit/evidence。 |
| `src/omichub/application/services/agentteams_case_watch_service.py` | 零修改为优先；由 Case adapter 订阅/关联已有 Case 结果，非 Goal Case 完全忽略。 |
| `src/omichub/tools/schema_loader.py` | 不污染全局注册；终结工具仅在 Goal Manager 的专属上下文中动态暴露。 |
| `src/omichub/application/services/tool_bridge_service.py` | 保持工具执行语义不变；仅在确认兼容后给 `ToolInvocationContext` 增加可选 Goal 元数据。 |
| `src/omichub/core/config.py` | Goal 默认 budget、lease、worker 并发、compaction 阈值。 |

---

## 14. 核心代码骨架（伪代码）

### 14.1 GoalExecutionEngine

```python
class GoalExecutionEngine:
    def __init__(self, db_factory, queue, evaluator, context_service):
        self._db_factory = db_factory
        self._queue = queue
        self._evaluator = evaluator
        self._context_service = context_service

    async def run_once(self, goal_id: str, cause: GoalContinuationCause) -> None:
        async with self._db_factory() as db:
            goal = await GoalRepository(db).claim_lease(
                goal_id=goal_id,
                owner=current_worker_id(),
                ttl_seconds=settings.goal_lease_seconds,
            )
            if goal is None or goal.status.is_terminal:
                return

            if goal.status in {WAITING_USER, WAITING_EXTERNAL, PAUSED}:
                return

            await GoalBudgetPolicy.assert_can_continue(goal)
            packet = await self._context_service.build_packet(db, goal)
            next_unit = await GoalWorkUnitService(db).claim_ready_unit(goal)
            await GoalEventService(db).append(goal, "continuation_started", cause=cause)
            await db.commit()

        if next_unit is not None:
            await self._dispatch_work_unit(goal_id, next_unit.work_unit_id)
            return

        decision = await self._run_manager_decision(goal_id, packet)
        await self._persist_decision_and_schedule(goal_id, decision)

    async def _persist_decision_and_schedule(self, goal_id: str, decision: ManagerDecision) -> None:
        async with self._db_factory() as db:
            goal = await GoalRepository(db).get_for_update(goal_id)
            result = await GoalDecisionApplier(db).apply(goal, decision)
            await db.commit()

        if result.next_cause is not None:
            await self._queue.enqueue_goal(goal_id, cause=result.next_cause)
```

### 14.2 Work Unit 与并行子 Agent

```python
async def dispatch_parallel_unit(goal: AgentGoal, unit: GoalWorkUnit) -> None:
    tasks = unit.payload["tasks"]
    result = await ParallelSubAgentToolService().run_parallel_subagents(
        context_summary=GoalContextService.worker_summary(goal, unit),
        tasks=tasks,
        context=ToolInvocationContext(
            user_id=goal.user_id,
            session_id=goal.session_id,
            agent_id=goal.manager_agent_id,
            db=db,
            extra={
                "goal_id": goal.goal_id,
                "work_unit_key": unit.work_unit_key,
                "idempotency_key": unit.idempotency_key,
                "goal_safe_only": True,
                "goal_fanout_enabled": True,
            },
        ),
    )
    await GoalWorkUnitService(db).record_result(unit, result)
    await GoalEventService(db).append(goal, "fanout_finished", work_unit_id=unit.work_unit_id)
    await queue.enqueue_goal(goal.goal_id, cause="workers_finished")
```

### 14.3 终结工具

```python
class GoalTerminalToolService:
    async def goal_complete(self, *, summary, criteria_results, evidence_refs, context, **_):
        goal = await self._load_manager_goal(context)
        claim = await GoalTerminalClaimService(context.db).create_complete_claim(
            goal=goal,
            summary=summary,
            criteria_results=criteria_results,
            evidence_refs=evidence_refs,
        )
        verdict = await GoalEvaluator(context.db).evaluate_complete_claim(goal, claim)
        if verdict.passed:
            await GoalService(context.db).transition(goal, COMPLETED, evidence=verdict.evidence)
        else:
            await GoalWorkUnitService(context.db).create_evidence_gap_unit(goal, verdict.gaps)
        return verdict.to_tool_payload()

    async def goal_blocked(self, *, reason, blocked_by, required_input="", context, **_):
        goal = await self._load_manager_goal(context)
        await GoalService(context.db).transition(
            goal,
            WAITING_USER if blocked_by in {"user", "approval"} else BLOCKED,
            reason=reason,
            required_input=required_input,
        )
        return {"success": True, "status": goal.status.value}
```

---

## 15. System Prompt 模板

### 15.1 Manager

```text
你是 OmicHub Goal Manager，负责一个可审计的目标执行运行。

Goal ID: {goal_id}
目标：{objective}
成功标准：{success_criteria}
权限：{permission}
剩余预算：{budget}
当前计划：{plan_summary}
完成工作：{completed_work_units}
进行中/可执行工作：{open_work_units}

工作原则：
- 先检查成功标准和已有证据，再决定下一步。
- 能并行的独立工作必须拆成明确 Work Unit；有依赖的工作保持串行。
- 高风险、副作用、外部提交必须遵守审批策略，绝不能因为目标在运行而自动批准。
- 缺少用户输入时使用 ask_user；缺少外部结果时创建/等待受控 Work Unit。
- 不得用普通自然语言宣称完成。只有所有必需标准有可验证证据时调用 goal_complete。
- 无法继续时调用 goal_blocked，说明阻塞来源、已尝试内容和用户需要提供的最小输入。
```

### 15.2 Worker

```text
你是 Goal {goal_id} 的 Worker，不拥有父 Goal 的终结权。
你的 Work Unit：{work_unit}
允许工具与权限：{tool_policy}
输入证据：{input_refs}

只执行本 Work Unit。输出结构化结果：结论、证据引用、产物路径、风险、是否需要用户输入。
不要调用 goal_complete 或 goal_blocked；不要改变目标、预算或其他 Work Unit。
```

### 15.3 Evaluator

```text
你是只读 Evaluator。逐条核验成功标准是否由归属该 Goal 的证据支持。
不得执行工具、副作用或修改计划。输出 passed / failed / gaps 及证据引用。
```

---

## 16. 验收标准与测试矩阵

| 场景 | 必须证明的行为 |
|---|---|
| 创建 Goal | `agent_goals`、初始 event、`session_id/user_id` 关联一次性提交；旧聊天表不变。 |
| 浏览器断开 | 后台 Goal 继续；重连后从 event cursor 补齐。 |
| Worker fan-out | 每个 Worker 独立事务/上下文；父 Manager 得到一次聚合 continuation。 |
| ask_user | Goal 进入 `WAITING_USER`，没有用户答复时绝不继续。 |
| 审批 | 高风险工具保持 pending，批准后才恢复对应 Work Unit。 |
| Case watch | 同一 Case event 重放不创建重复 continuation。 |
| 完成声明 | 缺证据不可 COMPLETED；证据齐全才终结。 |
| 预算 | 达到 max_turns/token/deadline 后不再自动入队。 |
| 并发 | 两个 Worker / 用户命令竞争同一 Goal 时 lease + version 保证单一状态转换。 |
| 重启恢复 | kill Worker 后可从 DB Event / Work Unit 恢复，不重复副作用。 |
| 权限 | `/goal` 不得越过 safe/read/analysis/full 和现有 HITL。 |

建议新增测试：

- `tests/unit/application/test_goal_service.py`
- `tests/unit/application/test_goal_execution_engine.py`
- `tests/unit/application/test_goal_evaluator.py`
- `tests/unit/application/test_goal_terminal_tool_service.py`
- `tests/integration/test_goal_continuation_recovery.py`
- `tests/integration/test_goal_parallel_subagents.py`
- `tests/integration/test_goal_agentteams_adapter.py`
- `frontend/src/stores/__tests__/goalRuntime.test.ts`

---

## 17. 推荐决策

1. **保留**当前 `/goal <text>` 作为轻量 Goal Hint，避免破坏既有用户习惯。
2. **新增**显式 `/goal start` 作为持久自治运行入口；第一期必须由 UI 展示成功标准、预算与权限。
3. **先做单 Agent Goal Runtime，再接 fan-out**。先证明状态机、恢复、审计和安全正确，再提升并行度。
4. **把 parallel_subagents 作为 Worker executor，而不是把整个 Overdrive 复制进 Goal。**
5. **把 AgentTeams Case 当作外部异步 Work Unit。** Case 状态变化触发 continuation，不在 Chat SSE 内长等。
6. **完成/阻塞必须走终结工具 + 服务端 Evaluator。** 不信任自然语言完成宣告。
7. **Phase 0 的事务、锁、JSONB 分拆是硬前置。** 若跳过，会将现有跨模式并发风险放大成不可审计的自治执行风险。

这条路线能把 OmicHub 现有的会话、Agent、Studio、工具、记忆与 multi-agent 能力统一到同一个可恢复、可观测、可安全控制的 Goal Runtime，而不是再增加一个只靠 Prompt 维持的“伪自主模式”。

---

## 18. 与补充方案融合后的最终落地边界

补充方案的方向正确，但“不可变基础设施”应理解为**不重写既有控制流和业务语义**，而不是禁止任何向后兼容的可选扩展。最终采用“新路由 + 新状态表 + 适配器 + 可选上下文”的四层融合方式：

```text
旧请求: POST /api/v1/chat/stream
  -> ChatService.stream_agent_chat
  -> Router / Overdrive / parallel_subagents / AgentTeams
  -> 原有 SSE、session、message 事务

新请求: POST /api/v1/goals/start
  -> GoalService.create_goal
  -> GoalExecutionEngine.run_once (Celery + Redis/DB lease)
  -> GoalContextPacket + Goal adapters
  -> AgentService / ToolBridge / ParallelSubAgent / AgentTeams
  -> agent_goal_events + Goal SSE/轮询
```

### 18.1 四条必须守住的兼容边界

1. **API 边界**：不改变 `POST /api/v1/chat/stream` 的请求、响应和 SSE 事件语义；`/goal <text>` 仍然只是现有 Star Prompt Hint。持久 Goal 使用新增的 `/api/v1/goals/*` 控制面。
2. **数据边界**：第一阶段不新增 `chat_sessions.active_goal_id`，也不把 Goal 事件写入 `chat_messages`。`agent_goals.session_id` 负责关联，Goal 表和事件表负责事实来源。
3. **执行边界**：Goal 由短事务后台 step 驱动，不把 `while True` 放进聊天 SSE；浏览器断开、Worker 重启、暂停和恢复都由 Goal 状态机处理。
4. **工具边界**：Goal 不复制工具执行逻辑、不绕过现有权限和 HITL。Goal 只通过 `ToolInvocationContext` 的可选元数据传递 `goal_id`、`work_unit_id` 和幂等键。

### 18.2 适配器的职责，而不是复制一套 Agent

Goal Runtime 不应该重新实现 Router、Fan-out 或 Case Watcher。三个适配器只负责把 Goal 生命周期映射到现有能力：

| 适配器 | 复用对象 | Goal 侧新增职责 |
|---|---|---|
| `GoalRouterAdapter` | `AgentService` 的 Agent/模型/工具上下文组装与已有路由能力 | 选择 Manager，保存路由快照，失败时回退默认 Agent |
| `GoalFanoutAdapter` | `ParallelSubAgentService` | 把每个子任务登记为 Work Unit，收集结构化 evidence，避免递归 Goal |
| `GoalCaseAdapter` | AgentTeams Case API 与 watch 结果 | 将 Goal 创建的 Case 关联到 Work Unit，幂等地唤醒 continuation |

适配器不能修改普通调用的默认参数，也不能通过“检测到 Goal”改变旧请求的并发、权限、工具过滤或消息落库行为。Goal 专属参数由 Goal Runtime 显式传入，并且只在新路由调用链中生效。

### 18.3 建议的最小实现顺序

1. 先新增 `goal.py` 模型、migration、`GoalService`、`GoalExecutionEngine`、Goal API 和事件查询；先支持单 Manager、单步 continuation、暂停/恢复/取消和预算。
2. 再增加 `GoalTerminalTools`、`GoalEvaluator`、`GoalContextPacket`，把“完成必须有证据”和“阻塞必须说明原因”固化为状态机规则。
3. 最后接入三个 adapter：先 Fan-out，再 Case，再 Router 优化；每次只打开一个 Feature Flag，保持普通 Chat 回归可比。
4. 只有当现有 `ChatService` 存在稳定且可测试的单轮调用边界时，才复用该边界；否则在 Goal Runtime 内建立薄的单轮执行包装，不为了 Goal 改写 `stream_agent_chat`。

### 18.4 失败隔离与回滚

Goal Runtime 的数据库表、Celery task、Redis key 前缀、API 路由和前端状态订阅都使用独立命名空间。`goal_runtime_enabled=false` 时，旧 Chat 链路不加载 Goal service、不注册 Goal 工具、不改变现有 SSE。关闭新 Feature Flag 只停止创建新的 Goal；已运行 Goal 按明确策略暂停或继续，不得静默伪装成普通聊天。

因此，本方案不是把现有 Agent 框架“改造成 Goal 框架”，而是让 Goal 成为一个能够编排现有 Agent 能力的上层运行时：**旧链路保持原样，新链路通过组合和适配复用能力，Goal 状态由自己的 ledger、lease 和 event stream 负责。**
