# OmicHub Agent 思考—工具闭环优化实施计划与编码 Agent 提示词

> 版本：v1.0  
> 日期：2026-08-18  
> 依据文档：`AI助手-AI工作台-协助室思考工具闭环详细排查报告.md`  
> 适用范围：OmicHub 普通 AI 助手、AI 工作台（Studio）、AgentTeams 协助室、Case/Overdrive 执行链、前端 AgentHub/房间时间线及相关测试体系  
> 核心原则：**在现有实现上优化，不推倒重写；先统一语义和可观测性，再补协助室工具路由，最后完善防护与端到端测试。**

---

## 0. 一页结论

当前 OmicHub 的核心能力已经不是“只有思考动画而没有循环”。普通 AI 助手、AI 工作台以及 AgentTeams Worker 后端都已经具备实质性的多轮工具调用能力，工具结果也会以 `role=tool` 等形式回灌模型上下文。

现阶段与常用生产级 Agent 流程的主要差距不在“有没有 ReAct 闭环”，而在：

1. **多条执行路径并存**：legacy 手写循环、LangGraph 循环、Studio 分流、协助室 Manager 会诊、Worker 子 Agent 循环同时存在，但缺少统一的执行语义。
2. **协助室普通 Manager 会诊不是完整工具执行路径**：它适合纯讨论和解释，但用户明确要求读取文件、检索、复核或执行时，应进入受控工具循环。
3. **后端闭环与前端可见闭环不一致**：Worker 后端可能在真实执行工具，但房间前端不一定能完整看到 reasoning、tool_call、tool_result、再 reasoning 的关系。
4. **缺少统一轮次与上下文回灌事件**：仅靠 `tool_call`、`tool_result` 很难审计“工具结果是否真的进入了下一次模型调用”。
5. **工程化保护不足**：目前更依赖 `max_rounds`，还需要补重复调用检测、无进展检测、预算、超时、取消、失败降级等机制。
6. **自动化闭环测试不足**：静态代码证明循环存在，但不能证明所有 Provider、工具、入口和配置组合在真实环境中稳定闭环。

本次优化的目标不是重做一套 Agent，而是把现有能力收敛为一套**统一、可观测、可控、可测试、对用户可解释**的 Agent 工作流。

---

## 1. 背景与目标

### 1.1 已确认的现状

根据排查报告，当前主要路径如下：

| 场景 | 当前状态 | 主要问题 |
|---|---|---|
| 普通 AI 助手 legacy | 已有多轮工具循环，工具结果回灌 | 与其他路径缺少统一事件和轮次抽象 |
| 普通 AI 助手 LangGraph | `llm_call → tool_exec → llm_call` 图循环 | 需与 legacy 保持行为一致 |
| AI 工作台 Studio | 复用 ChatService 循环，支持沙盒/工作区工具 | 沙盒完成不等于任务完成，需要强化结果回灌验证 |
| 协助室普通 Manager 会诊 | 主要是上下文会诊，不保证工具调用 | 需要区分纯讨论与需要工具的受控执行 |
| 协助室 Case/Overdrive Worker | 后端具备受限 ReAct 子循环 | 前端过程展示不完整，审计语义不统一 |

### 1.2 优化目标

本次优化要达到六个目标：

1. **统一执行语义**：所有入口都能明确标识自己属于哪条 `execution_path`。
2. **统一事件链**：普通助手、Studio、协助室 Worker 都发出一致的轮次、工具、回灌和收敛事件。
3. **协助室路由更清晰**：纯讨论走会诊；需要工具的房间消息进入受控工具执行路径；复合任务进入 Case。
4. **前端可见闭环**：用户能看到结构化进度，不必阅读原始 reasoning 才能判断任务是否推进。
5. **运行过程可控**：补充预算、超时、重复调用、无进展循环和失败降级机制。
6. **自动化可验收**：用 fake provider、fake tool、真实沙盒和事件投影测试覆盖关键闭环。

### 1.3 非目标

以下事项不属于本次第一阶段范围：

- 不推倒现有 ChatService、LangGraph、Studio、AgentTeams 架构重写；
- 不改变普通聊天“无工具时直接回答”的基本行为；
- 不强制所有协助室消息都调用工具；
- 不把原始 reasoning 默认完整暴露给普通用户；
- 不调整无关页面视觉样式；
- 不引入与现有权限体系冲突的新工具通道。

---

## 2. 现阶段流程与常用 Agent 流程的差异

### 2.1 流程对应关系

| OmicHub 当前流程 | 常见对应模式 | 判断 |
|---|---|---|
| 普通问答流程 | Direct LLM Response | 基本一致，无需大改 |
| 单工具流程 | Function Calling / Tool Calling | 基本一致，继续保留 |
| 多工具、多轮分析流程 | ReAct Loop / Agent Loop | 核心一致，需加强控制和观测 |
| AgentTeams Case 流程 | Orchestrator-Workers / Planner-Executor-Critic | 方向正确，需统一事件与展示 |
| 协助室普通 Manager 会诊 | Consultation / Read-only Router | 不能误称为完整执行 Agent，需要显式分流 |

### 2.2 与常见生产级流程的关键差异

#### 差异 1：多套循环并存，而不是统一 Runtime

当前更像是：

```text
普通助手 legacy 循环
普通助手 LangGraph 循环
Studio 工具分流循环
协助室 Manager 会诊
协助室 Worker ReAct 循环
```

常见生产级做法更倾向于：

```text
所有业务入口
  ↓
统一 Agent Runtime / Execution Engine
  ↓
统一状态、轮次、事件、预算、错误、恢复、审计
```

本阶段不要求立刻合并全部实现，但必须先建立统一抽象和事件规范。

#### 差异 2：后端有闭环，但缺少“上下文已回灌”的显式证据

当前已有 `tool_call` 和 `tool_result`，但还缺少类似：

```text
agent_context_reinjected
agent_turn_continued
```

的事件来证明：

- 工具结果已被写入模型上下文；
- 下一次模型调用确实发生在工具结果之后；
- 本轮循环是基于工具结果继续推进，而不是重新开启无关联回答。

#### 差异 3：协助室普通会话的路由粒度不够

目前普通 Manager 会诊更偏只读分析：

```text
读取 Case 上下文
→ Manager/会诊 Agent 分析
→ 返回结构化结论
→ 写入房间
```

更合理的目标流程是：

```text
房间用户消息
  ↓
意图与能力路由
  ├─ 纯讨论/解释 → Manager 会诊
  ├─ 信息不足 → room.ask_user
  ├─ 明确需要读取/检索/复核 → 工具型受控执行
  ├─ 明确需要代码/文件产物 → Studio/沙盒执行
  └─ 多步骤复合任务 → Case/Planner/Worker
```

#### 差异 4：前端展示偏“原始过程”，而不是“结构化进度”

当前普通助手和 Studio 展示较完整，但 Overdrive/Worker 仍以 Worker 发言、进度卡和结果卡为主。更稳定的产品展示应该是：

```text
正在分析任务
→ 正在读取输入文件
→ 已获得文件检查结果
→ 正在根据结果调整分析方案
→ 正在执行第二步分析
→ 已完成结果复核
```

原始 reasoning 更适合放入调试模式或折叠详情，不建议作为唯一用户反馈。

#### 差异 5：只有轮次上限，还缺少“是否有效推进”的判断

成熟 Agent Loop 不只看轮数，还应判断：

- 是否重复调用同一工具和相同参数；
- 工具结果是否没有带来新信息；
- 是否反复出现同类错误；
- 是否超过时间、Token 或成本预算；
- 是否应请求用户确认后继续；
- 是否应终止并说明无法完成的原因。

---

## 3. 问题清单与优先级

### P0：执行路径语义混淆

**问题**：普通助手、Studio、Manager、Worker 都被称为 Agent，但实际执行模式不同。

**影响**：

- 用户无法判断当前消息到底会不会使用工具；
- 日志和前端事件难以统一；
- 编码和测试时容易把不同路径混为一谈。

**优化方向**：引入明确的 `execution_path`，并在后端事件、日志、前端状态中透传。

建议枚举：

```text
chat_legacy
chat_langgraph
studio_chat_loop
agentteams_manager_consultation
agentteams_tool_execution
agentteams_worker_react
```

---

### P1：协助室普通会话缺少受控工具执行路径

**问题**：普通 Manager 会诊中 `requested_tools=[]`，更偏只读会诊。对于明确要求“读取文件、查询、复核”的房间消息，不能保证工具闭环。

**优化方向**：增加房间级工具意图路由，不要求所有消息调用工具，但要求明确需要工具的消息进入工具路径。

---

### P1：Overdrive/Worker 前端展示不完整

**问题**：后端已产生 Worker reasoning/tool 事件，但前端更多展示 Worker 发言、进度和结果，用户无法稳定确认工具结果是否影响了下一步。

**优化方向**：建立结构化 Worker 时间线，不默认铺开原始 reasoning，而是展示阶段、工具、结果摘要和轮次关系。

---

### P1：缺少统一 loop round / context reinjected 事件

**问题**：只有工具调用和工具结果，不足以审计“工具结果是否进入下一次模型调用”。

**优化方向**：新增统一事件模型，并在 legacy、LangGraph、Studio、Worker 中适配。

---

### P1：运行保护不足

**问题**：已有 `max_rounds`，但缺少重复调用、无进展、预算、超时、取消、失败降级等保护。

**优化方向**：在统一 Runtime 或各执行路径的公共层中加入 Loop Guard。

---

### P2：reasoning 展示偏原始

**问题**：原始 reasoning 可能中英文混杂、暴露内部实现细节，且不能清楚表达当前执行阶段。

**优化方向**：用户态默认展示结构化阶段状态；debug 模式才展示工具参数摘要和 reasoning 摘要；internal 信息只写审计日志。

---

### P2：端到端测试不足

**问题**：静态代码证据不能覆盖所有 Provider、工具、入口和配置组合。

**优化方向**：增加 fake provider、多轮工具调用、Studio 沙盒回灌、Worker 子循环、房间事件投影、legacy/LangGraph 一致性测试。

---

## 4. 目标架构设计

### 4.1 目标执行拓扑

```text
用户输入
  ↓
统一入口层
  ├─ 普通 AI 助手
  ├─ AI 工作台 Studio
  └─ AgentTeams 协助室
        ↓
执行路径判定 Execution Path Resolver
  ├─ chat_legacy
  ├─ chat_langgraph
  ├─ studio_chat_loop
  ├─ agentteams_manager_consultation
  ├─ agentteams_tool_execution
  └─ agentteams_worker_react
        ↓
统一 Agent Loop Runtime / Adapter
  ├─ 模型调用
  ├─ reasoning 分流
  ├─ tool_call 收集
  ├─ 工具执行
  ├─ tool_result 写入上下文
  ├─ context_reinjected 事件
  ├─ 下一轮模型调用
  └─ 最终收敛
        ↓
统一事件总线 / SSE / 审计日志
        ↓
前端结构化时间线
```

### 4.2 统一事件模型

建议统一抽象以下事件：

```text
agent_turn_started
agent_reasoning_delta
agent_tool_call
agent_tool_started
agent_tool_result
agent_context_reinjected
agent_turn_continued
agent_loop_guard_triggered
agent_final_result
agent_turn_failed
```

推荐基础字段：

```json
{
  "session_id": "...",
  "case_id": "...",
  "work_item_id": "...",
  "run_id": "...",
  "agent_id": "...",
  "execution_path": "studio_chat_loop",
  "round": 2,
  "phase": "after_tool_result",
  "tool_call_id": "...",
  "tool_name": "...",
  "visibility": "user|debug|internal",
  "timestamp": "..."
}
```

### 4.3 visibility 语义

| visibility | 用途 | 前端表现 |
|---|---|---|
| `user` | 用户需要知道的阶段进度 | 展示为简洁阶段状态 |
| `debug` | 开发/管理员排查 | 折叠面板展示工具名、参数摘要、结果摘要 |
| `internal` | 审计、安全、原始上下文 | 默认不展示，只写日志或审计存储 |

### 4.4 `agent_context_reinjected` 判定语义

该事件不是“工具执行完了就发”，而应在以下条件满足后发出：

1. 工具结果已生成；
2. 工具结果已追加到模型消息历史；
3. 系统即将进入下一次模型调用；
4. 事件中能关联 `tool_call_id`、当前 `round` 和目标 `execution_path`。

推荐语义：

```text
tool_result stored
→ assistant/tool messages appended
→ next llm call prepared
→ emit agent_context_reinjected
→ emit agent_turn_continued
→ next llm call starts
```

### 4.5 协助室目标路由

```text
room.user_message
  ↓
RoomIntentRouter
  ├─ chat：纯讨论、解释、总结
  │    ↓
  │  agentteams_manager_consultation
  │
  ├─ clarify：缺少文件、参数或目标
  │    ↓
  │  room.ask_user
  │
  ├─ tool_execute：明确读取/检索/复核/运行
  │    ↓
  │  agentteams_tool_execution
  │    ↓
  │  Manager 读取结果并回复房间
  │
  └─ case_execute：多步骤、多角色、多产物任务
       ↓
     Planner → Case → Worker → Manager → QC → Delivery
```

路由结果应落库或至少进入事件流：

```json
{
  "route": "tool_execute",
  "reason": "用户明确要求读取输入文件并判断结果",
  "confidence": 0.91,
  "requires_tool": true,
  "requested_capabilities": ["workspace_read"]
}
```

### 4.6 前端目标状态模型

普通助手、Studio、协助室房间都应能投影为统一时间线节点：

```text
ThoughtStep
ToolCallStep
ToolResultStep
ContextReinjectedStep
GuardWarningStep
FinalResultStep
```

前端默认展示：

- 当前执行路径；
- 当前轮次；
- 当前阶段；
- 工具名称和执行状态；
- 工具结果摘要；
- 是否已进入下一轮模型调用；
- 最终结论和产物。

debug 模式额外展示：

- 工具参数摘要；
- 原始工具结果摘要；
- reasoning 摘要；
- 事件 ID 和调用链关系。

internal 内容不直接展示。

---

## 5. 分阶段实施计划

## 阶段 0：基线核查与最小止血

### 目标

在不改业务逻辑的前提下，先确认各路径的事件、上下文和前端投影现状，为后续改造建立基线。

### 改动点

1. 阅读并确认以下入口：
   - `src/omichub/application/services/chat_service.py`
   - `src/omichub/infrastructure/execution/langgraph_nodes.py`
   - `src/omichub/infrastructure/execution/langgraph_runtime.py`
   - `src/omichub/application/services/parallel_subagent_service.py`
   - `src/omichub/application/services/agentteams_room_response_service.py`
   - `frontend/src/stores/agentHub.ts`
   - `frontend/src/stores/chatSession.ts`
   - `frontend/src/views/AgentTeamsRoomView.vue`
2. 建立现有事件清单：事件名、产生位置、消费位置、是否包含 run_id/round/tool_call_id。
3. 建立现有工具结果回灌链路表。
4. 输出基线报告，不大规模重构。

### 验收标准

- [ ] 能列出每条执行路径的事件链。
- [ ] 能列出每条路径的工具结果如何回灌模型。
- [ ] 能指出哪些事件缺少 `round`、`execution_path` 或 `tool_call_id`。
- [ ] 不修改或只做注释级/测试级修改，不影响线上行为。

---

## 阶段 1：统一执行路径与事件模型

### 目标

为所有执行路径增加统一的 `execution_path`、轮次事件和上下文回灌事件，先解决“看不见、分不清”的问题。

### 改动范围

- 后端事件模型；
- legacy 循环事件；
- LangGraph 节点事件；
- Studio 分流事件；
- Worker 子 Agent 事件；
- SSE/房间事件投影；
- 前端 Store 的基础兼容。

### 必做任务

1. 定义统一事件 schema。
2. 定义 `execution_path` 枚举。
3. 在普通 legacy 循环中补充：
   - `agent_turn_started`；
   - `agent_context_reinjected`；
   - `agent_turn_continued`；
   - `agent_final_result`；
   - `agent_turn_failed`。
4. 在 LangGraph `llm_call`、`tool_exec` 中补充相同语义事件。
5. 在 Worker 循环中补充 `execution_path=agentteams_worker_react`。
6. 在 Studio 分流中补充 `execution_path=studio_chat_loop`。
7. 所有事件至少携带 `session_id`、`run_id`、`agent_id`、`round`、`timestamp`。
8. 工具相关事件必须携带 `tool_call_id`，无法获得时明确说明原因。
9. 保持旧事件兼容，不删除现有前端依赖事件。

### 对应提示词

见 **附录 A：阶段 1 编码提示词**。

### 验收标准

- [ ] 每条路径都能输出唯一 `execution_path`。
- [ ] 一次多轮工具调用中，能看到第 1 轮、第 2 轮、第 3 轮关系。
- [ ] 工具结果写回上下文后有 `agent_context_reinjected`。
- [ ] 下一次模型调用前有 `agent_turn_continued`。
- [ ] 旧前端不因新增事件报错。
- [ ] 新增事件有单元测试或事件序列测试。

---

## 阶段 2：协助室普通消息工具路由

### 目标

让协助室普通消息明确区分“纯会诊”和“需要工具的受控执行”，避免用户要求读取/复核时只得到一次无工具会诊。

### 改动范围

- `agentteams_room_response_service.py`；
- 房间意图判断；
- Manager 会诊能力配置；
- 房间事件与前端消息状态；
- 工具失败和缺文件场景处理。

### 必做任务

1. 增加 `RoomIntentRouter` 或等价轻量路由层。
2. 路由结果至少包含：
   - `chat`；
   - `clarify`；
   - `tool_execute`；
   - `case_execute`；
   - `degraded`。
3. 对 `tool_execute` 路径启用受控工具集：
   - 工作区读取；
   - 检索；
   - 必要的只读复核工具；
   - 明确获批后的执行工具。
4. 对纯讨论仍使用 `agentteams_manager_consultation`，不强制工具调用。
5. 对缺文件、缺参数、目标不清的情况使用 `room.ask_user`。
6. 工具失败时，Manager 必须明确说明失败，不得生成“已完成”。
7. 工具结果必须回灌给 Manager 或工具执行 Agent，再生成房间回复。
8. 房间消息中记录路由原因和执行路径。

### 对应提示词

见 **附录 B：阶段 2 编码提示词**。

### 验收标准

- [ ] “你怎么看这个方案”不强制工具调用。
- [ ] “读取这个文件并判断”进入工具路径。
- [ ] “文件不存在”触发 `room.ask_user` 或明确失败说明。
- [ ] 工具失败不会伪造成功。
- [ ] Manager 最终回复能体现工具结果，而不是忽略工具结果。
- [ ] 房间事件能显示 `agentteams_tool_execution`。

---

## 阶段 3：Overdrive/Worker 结构化时间线

### 目标

让用户在协助室中看到 Worker 的结构化执行过程，而不是只看到 Worker 发言和结果卡。

### 改动范围

- `frontend/src/stores/agentHub.ts`；
- `frontend/src/views/AgentTeamsRoomView.vue`；
- Worker/Overdrive 事件投影；
- 房间时间线组件；
- debug 展示模式。

### 必做任务

1. 增加 Worker 结构化时间线节点。
2. 将 Worker 事件映射为：
   - 正在分析；
   - 正在调用工具；
   - 工具执行中；
   - 工具执行完成；
   - 工具结果已纳入下一步；
   - Worker 输出阶段结果。
3. 默认不展开完整原始 reasoning。
4. debug 模式可查看：
   - reasoning 摘要；
   - 工具参数摘要；
   - 工具结果摘要；
   - tool_call_id；
   - round；
   - execution_path。
5. 保持现有 Worker 发言、进度卡、结果卡兼容。
6. 工具失败和 Guard 触发要显示明确警示。

### 对应提示词

见 **附录 C：阶段 3 编码提示词**。

### 验收标准

- [ ] Worker 工具调用在房间时间线可见。
- [ ] 工具结果和下一次 Worker 思考之间有关联。
- [ ] 默认视图不刷屏，不直接暴露长段原始 reasoning。
- [ ] debug 模式可以追溯工具调用详情。
- [ ] Overdrive 不影响普通助手/Studio 现有展示。

---

## 阶段 4：Loop Guard 与运行保护

### 目标

避免多轮 Agent 在高轮次下出现重复调用、无进展循环、成本失控或失败后误判成功。

### 改动范围

- 普通 legacy 循环；
- LangGraph Runtime；
- Studio 工具循环；
- Worker ReAct 循环；
- 前端 Guard 提示。

### 必做任务

1. 增加重复工具调用检测：
   - 同一工具；
   - 等价参数；
   - 连续重复次数；
   - 无新增结果。
2. 增加无进展检测：
   - 连续多轮没有新增文件、检索结果、执行产物或有效结论；
   - 工具结果重复；
   - 模型反复生成相似 tool_call。
3. 增加预算控制：
   - 最大轮次；
   - 最大工具调用次数；
   - 最大耗时；
   - 最大 Token/成本预算（如已有 usage 统计则接入）。
4. 增加工具超时与取消语义。
5. 增加 Guard 触发后的行为：
   - 终止并解释；
   - 请求用户确认继续；
   - 降级为阶段性结果；
   - 转人工/Manager 处理。
6. Guard 事件必须进入统一事件链：

```text
agent_loop_guard_triggered
```

### 对应提示词

见 **附录 D：阶段 4 编码提示词**。

### 验收标准

- [ ] 重复调用同一工具不会无限循环。
- [ ] 达到预算时有明确失败或确认事件。
- [ ] Guard 触发后不会继续盲目调用工具。
- [ ] 前端能看到 Guard 原因。
- [ ] 不影响正常多轮任务继续执行。

---

## 阶段 5：自动化闭环测试

### 目标

把“代码看起来有循环”升级为“测试证明闭环存在且稳定”。

### 测试范围

1. 普通 AI 助手 legacy；
2. 普通 AI 助手 LangGraph；
3. Studio 沙盒；
4. 协助室普通工具路由；
5. AgentTeams Worker；
6. 前端事件投影。

### 必做测试

#### 5.1 fake provider 多轮工具调用测试

固定返回：

```text
第 1 轮：reasoning + tool_call(workspace_read_file)
工具结果：文件包含 3 个 sheet
第 2 轮：reasoning + tool_call(sandbox_execute)
工具结果：统计结果
第 3 轮：reasoning + final content
```

断言：

- [ ] 发生 3 次模型调用；
- [ ] 第 2 轮上下文包含第 1 个工具结果；
- [ ] 第 3 轮上下文包含第 1、2 个工具结果；
- [ ] 最终正文不混入 reasoning；
- [ ] 事件链包含 context reinjected 和 turn continued。

#### 5.2 Studio 沙盒回灌测试

任务：读取 CSV、计算分组均值、输出图表。

断言：

- [ ] 原始文件未被覆盖；
- [ ] stdout/stderr 正确进入工具结果；
- [ ] 图表产物路径进入最终上下文；
- [ ] 代码失败后模型能基于 stderr 修正；
- [ ] 不允许伪造执行成功。

#### 5.3 协助室普通会话测试

用例：

1. 纯讨论问题：不应强制工具调用；
2. 明确要求读取文件：应进入工具路径；
3. 缺文件：应触发 `room.ask_user`；
4. 工具失败：Manager 应明确失败，不得说“已完成”。

#### 5.4 Worker 多轮工具测试

固定 Worker 返回：

```text
第 1 轮：reasoning + tool_call
工具结果：部分结果
第 2 轮：reasoning + tool_call
工具结果：完整结果
第 3 轮：final answer
```

断言：

- [ ] 产生 Worker reasoning 事件；
- [ ] 产生 Worker tool_call/tool_result；
- [ ] 第二次模型调用包含第一轮 `role=tool`；
- [ ] Manager 收到 Worker 最终结构化结果；
- [ ] Manager 不直接采信未验证的工具参数。

#### 5.5 legacy 与 LangGraph 一致性测试

同一 fake provider、同一工具、同一消息历史分别运行 legacy 与 LangGraph，断言：

- [ ] 工具调用次数一致；
- [ ] 工具结果回灌次数一致；
- [ ] 最终正文一致；
- [ ] ask_user/handoff 终止行为一致；
- [ ] usage 统计一致或可解释；
- [ ] 统一事件语义一致。

### 对应提示词

见 **附录 E：阶段 5 编码提示词**。

---

## 阶段 6：产品化打磨与文档收口

### 目标

将技术闭环转化为用户可理解、研发可维护、审计可追踪的产品能力。

### 任务

1. 为普通助手、Studio、协助室统一阶段文案规范。
2. 为 debug 模式增加事件详情面板说明。
3. 为运维/研发补充 execution_path 排查手册。
4. 为测试人员补充标准验收用例。
5. 将关键事件写入审计日志。
6. 更新产品说明：哪些场景会调用工具，哪些场景只是会诊。

### 验收标准

- [ ] 用户能看懂当前执行阶段。
- [ ] 研发能根据事件链定位问题。
- [ ] 测试能按标准用例复验。
- [ ] 文档中的路径名、事件名与代码一致。

---

# 附录 A：阶段 1 编码提示词——统一执行路径与事件模型

```text
你是一名资深全栈架构师，熟悉 Python 后端、LangGraph、SSE 事件流、Vue3/Pinia 前端和多 Agent 系统。

任务：在现有 OmicHub 代码基础上，为普通 AI 助手、AI 工作台 Studio、AgentTeams Worker 增加统一的执行路径标识和 Agent Loop 事件模型。先阅读现有代码再修改，禁止推倒重写，禁止修改无关模块。

## 背景

当前代码已经存在多轮工具调用循环，但不同路径的事件语义不统一：

- 普通 AI 助手 legacy 循环在 `src/omichub/application/services/chat_service.py`
- 普通 AI 助手 LangGraph 路径在 `src/omichub/infrastructure/execution/langgraph_nodes.py` 和 `langgraph_runtime.py`
- Studio 复用 ChatService，并通过 `studio_mode` 分流工具
- AgentTeams Worker 循环在 `src/omichub/application/services/parallel_subagent_service.py`
- 前端事件处理在 `frontend/src/stores/agentHub.ts` 和 `frontend/src/stores/chatSession.ts`

需要先统一执行语义，而不是重写业务逻辑。

## 实现要求

### 1. 定义统一 execution_path

至少支持以下值：

- `chat_legacy`
- `chat_langgraph`
- `studio_chat_loop`
- `agentteams_manager_consultation`
- `agentteams_tool_execution`（本阶段先预留）
- `agentteams_worker_react`

要求：

- 每个执行入口明确写入自己的 execution_path。
- 后续事件、日志和前端状态都能透传该字段。
- 不要仅在前端猜测路径，后端必须提供权威字段。

### 2. 定义统一事件模型

新增或适配以下事件：

- `agent_turn_started`
- `agent_reasoning_delta`
- `agent_tool_call`
- `agent_tool_started`
- `agent_tool_result`
- `agent_context_reinjected`
- `agent_turn_continued`
- `agent_final_result`
- `agent_turn_failed`

推荐基础字段：

```json
{
  "session_id": "...",
  "case_id": "...",
  "work_item_id": "...",
  "run_id": "...",
  "agent_id": "...",
  "execution_path": "studio_chat_loop",
  "round": 2,
  "phase": "after_tool_result",
  "tool_call_id": "...",
  "tool_name": "...",
  "visibility": "user|debug|internal",
  "timestamp": "..."
}
```

### 3. 明确 context reinjected 语义

`agent_context_reinjected` 必须在以下条件满足后发出：

1. 工具结果已经生成；
2. 工具结果已经追加到模型消息历史；
3. 系统准备进入下一次模型调用；
4. 事件能关联 tool_call_id、round 和 execution_path。

不要在工具刚执行完但尚未写入上下文时发该事件。

### 4. 适配各执行路径

- legacy：在 ChatService 的工具循环中插入统一事件。
- LangGraph：在 `llm_call` 和 `tool_exec` 节点中插入统一事件。
- Studio：标记为 `studio_chat_loop`，保留现有工具分流逻辑。
- Worker：标记为 `agentteams_worker_react`，保留现有安全边界。

### 5. 兼容性要求

- 不删除现有事件。
- 不破坏现有前端对 `tool_call`、`tool_result`、reasoning 的处理。
- 旧事件和新事件可以并存，但新事件字段必须一致。
- 对无法获得 case_id/work_item_id/tool_call_id 的场景，字段可为空，但不要伪造。

### 6. 测试要求

增加事件序列测试，至少覆盖：

1. 无工具直接回答；
2. 一次工具调用；
3. 两次连续工具调用后最终回答；
4. LangGraph 与 legacy 的事件语义一致性；
5. Worker 工具结果回灌后继续下一轮。

## 交付要求

1. 修改代码并补充必要测试。
2. 输出变更文件清单。
3. 输出每条 execution_path 的事件序列示例。
4. 说明哪些旧事件保留、哪些新事件新增。
5. 如果某条路径暂时无法补统一事件，明确列出代码位置和原因，不要静默跳过。

## 验收标准

- [ ] 每条执行路径都有权威 execution_path。
- [ ] 多轮工具调用能看到 round 递增。
- [ ] 工具结果回灌后有 agent_context_reinjected。
- [ ] 下一次模型调用前有 agent_turn_continued。
- [ ] 旧前端不出现新增事件导致的异常。
- [ ] 新测试通过。
```

---

# 附录 B：阶段 2 编码提示词——协助室普通消息工具路由

```text
你是一名资深后端/全栈工程师，熟悉多 Agent 编排、房间会话路由、工具调用闭环和权限控制。

任务：在现有 OmicHub AgentTeams 协助室普通消息流程中，增加明确的意图与工具执行路由。先阅读现有代码再修改，禁止重写整个 AgentTeams 模块。

## 背景

当前房间普通消息由 `src/omichub/application/services/agentteams_room_response_service.py` 处理。普通 Manager 会诊更接近：

- capability="interpretation"
- requested_tools=[]

这适合纯讨论和解释，但当用户明确要求“读取文件、查询数据、复核结果、执行检查”时，不能只走一次无工具会诊。

## 目标

建立清晰路由：

```text
room.user_message
  ↓
RoomIntentRouter
  ├─ chat：纯讨论/解释 → Manager 会诊
  ├─ clarify：信息不足 → room.ask_user
  ├─ tool_execute：明确需要读取/检索/复核 → 受控工具执行
  ├─ case_execute：多步骤复合任务 → Case/Planner/Worker
  └─ degraded：异常降级 → 明确说明降级原因
```

## 实现要求

### 1. 增加路由结果结构

路由结果至少包含：

```json
{
  "route": "chat|clarify|tool_execute|case_execute|degraded",
  "reason": "...",
  "confidence": 0.0,
  "requires_tool": false,
  "requested_capabilities": []
}
```

要求：

- 路由结果进入房间事件或审计日志。
- 前端至少能知道当前是 chat、clarify、tool_execute 还是 case_execute。
- 不要用模糊字符串散落在多个判断里，尽量集中定义。

### 2. tool_execute 路径

当用户明确要求读取、检索、复核、检查、执行时：

- 走 `agentteams_tool_execution`。
- 启用受控工具集，不开放高风险工具。
- 工具结果必须回灌 Manager 或工具执行 Agent。
- Manager 最终回复必须体现工具结果。
- 工具失败时明确说明失败，不得生成“已完成”。

### 3. chat 路径

纯讨论、解释、总结仍走 `agentteams_manager_consultation`：

- 不强制调用工具。
- 保留现有会诊能力。
- 但事件和日志中要明确它是 consultation，而不是完整执行链。

### 4. clarify 路径

当缺少文件、参数、目标或权限时：

- 产生 `room.ask_user`。
- 不要编造文件内容或执行结果。
- ask_user 的问题要具体说明缺什么。

### 5. case_execute 路径

当任务明显包含多个阶段、多个产物或需要多个 Worker 时：

- 转入现有 Case/Planner/Worker 流程。
- 不要在普通房间消息里硬执行长任务。
- 保留现有用户确认计划机制。

### 6. 前端事件

房间消息中至少展示：

- 当前处理路径；
- 正在等待用户补充；
- 正在读取/检索/复核；
- 工具执行失败；
- Manager 基于工具结果完成回复。

默认不展开原始 reasoning。

## 测试要求

至少增加以下测试：

1. 纯讨论问题不强制工具调用；
2. “读取这个文件并判断”进入 tool_execute；
3. 文件不存在触发 room.ask_user 或明确失败；
4. 工具失败不伪造成功；
5. 多步骤任务进入 Case，而不是普通会诊；
6. 工具结果进入 Manager 最终回复上下文。

## 交付要求

1. 修改代码并补充测试。
2. 输出路由决策表。
3. 输出各路由的事件序列示例。
4. 明确 tool_execute 允许使用哪些工具，哪些工具仍禁止。
5. 不要改变现有 Case/Planner/Worker 的核心结构。

## 验收标准

- [ ] 普通讨论和工具执行路径明确分离。
- [ ] 需要工具的房间消息不再只做无工具会诊。
- [ ] 工具结果会影响 Manager 最终回复。
- [ ] 缺信息时会 ask_user。
- [ ] 工具失败不会误报成功。
- [ ] 新路由有自动化测试。
```

---

# 附录 C：阶段 3 编码提示词——Overdrive/Worker 结构化时间线

```text
你是一名资深前端工程师，熟悉 Vue3、Pinia、SSE 事件流、复杂状态同步和多 Agent 执行过程可视化。

任务：在现有 AgentTeams 房间页面基础上，为 Overdrive/Worker 增加结构化执行时间线。先阅读现有代码再修改，禁止重做整个房间页面，禁止破坏现有 Worker 发言、进度卡、计划卡、审批卡和交付卡。

## 背景

后端 Worker 已经具备 reasoning、tool_call、tool_result 和多轮 ReAct 循环，但当前前端更多展示 Worker 发言、进度和结果，用户无法稳定确认：

- Worker 是否真的读取了输入；
- Worker 是否真的执行了工具；
- 工具结果是否影响了下一步；
- 当前处于第几轮；
- 最终结论来自哪次工具结果。

## 改动范围

优先阅读：

- `frontend/src/stores/agentHub.ts`
- `frontend/src/views/AgentTeamsRoomView.vue`
- Worker/Overdrive 相关事件模型和组件

## 实现要求

### 1. 增加统一 Worker 时间线节点

将 Worker 执行过程投影为：

- `WorkerThoughtStep`
- `WorkerToolCallStep`
- `WorkerToolResultStep`
- `WorkerContextReinjectedStep`
- `WorkerGuardWarningStep`
- `WorkerFinalResultStep`

如果现有组件已有类似抽象，优先复用，不要重复造组件。

### 2. 默认用户态展示

默认展示简洁阶段状态，例如：

- 正在分析任务
- 正在调用工具：读取工作区文件
- 工具执行完成
- 已将工具结果纳入下一步分析
- 正在复核结果
- Worker 已提交阶段结果

要求：

- 不默认展开大段原始 reasoning。
- 不让工具事件刷屏。
- 同一 Worker 的连续过程要聚合或按时间线清晰排列。

### 3. debug 模式

debug 模式可展开查看：

- execution_path
- round
- tool_call_id
- tool_name
- 工具参数摘要
- 工具结果摘要
- reasoning 摘要
- 失败原因
- Guard 触发原因

internal 内容不直接展示。

### 4. Overdrive 特殊处理

当前 Overdrive 中 reasoning 可能跳过普通 thought 展示。改造后：

- 不要把 Worker reasoning 强行塞回普通消息气泡；
- 应进入 Worker 结构化时间线；
- 保持 Overdrive 房间主界面清爽；
- 用户可展开查看执行详情。

### 5. 状态和边界

必须处理：

- 工具执行中；
- 工具成功；
- 工具失败；
- 工具超时；
- Guard 触发；
- Worker 达到轮次上限；
- Worker 输出阶段性结果；
- 事件乱序或重复到达。

### 6. 兼容性

- 不影响普通 AI 助手和 Studio 的现有展示。
- 不删除现有房间消息类型。
- 旧事件缺失新字段时要能降级展示。
- 不要因为新增 debug 字段导致普通用户界面异常。

## 测试要求

至少覆盖：

1. Worker 一次工具调用的时间线展示；
2. Worker 两次工具调用后最终完成；
3. 工具失败时的展示；
4. Guard 触发时的展示；
5. debug 展开和收起；
6. Overdrive 与普通聊天模式互不污染。

## 交付要求

1. 修改前端代码并补充组件/状态测试。
2. 输出事件到 UI 节点的映射表。
3. 输出默认态和 debug 态的展示说明。
4. 明确哪些内容普通用户可见，哪些只在 debug 模式可见。

## 验收标准

- [ ] Worker 工具调用过程可见。
- [ ] 工具结果与下一轮分析之间有关联。
- [ ] 默认界面不被原始 reasoning 刷屏。
- [ ] debug 模式能追溯工具调用详情。
- [ ] 现有房间功能不回归。
```

---

# 附录 D：阶段 4 编码提示词——Loop Guard 与运行保护

```text
你是一名资深 Agent Runtime 工程师，熟悉多轮工具调用、成本控制、超时取消、循环检测和生产级可靠性设计。

任务：在现有 OmicHub Agent 循环基础上增加 Loop Guard 与运行保护机制。先阅读现有代码再修改，禁止重写整个执行框架。

## 背景

当前普通助手、LangGraph、Studio、Worker 都存在多轮工具循环，并已有 max_rounds 之类的基础限制。但生产级 Agent Loop 不能只限制轮数，还需要识别：

- 重复工具调用；
- 无进展循环；
- 重复错误；
- 预算超限；
- 工具超时；
- 用户取消；
- 达到上限后的降级和解释。

## 实现要求

### 1. 重复工具调用检测

检测维度至少包括：

- tool_name 相同；
- 参数等价或高度相似；
- 连续重复次数达到阈值；
- 工具结果没有新增信息。

触发后不要继续盲目调用，应进入 Guard 处理。

### 2. 无进展检测

以下情况应视为潜在无进展：

- 连续多轮没有新增文件、检索结果、执行产物或有效结论；
- 多轮工具结果基本相同；
- 模型反复生成相似 tool_call；
- 同类错误重复出现且没有被修正。

### 3. 预算控制

在现有能力允许范围内增加：

- 最大轮次；
- 最大工具调用次数；
- 最大执行耗时；
- 最大 Token/成本预算（如果当前已有 usage 统计则接入，没有则预留接口）。

### 4. Guard 事件

新增统一事件：

```text
agent_loop_guard_triggered
```

事件字段至少包含：

```json
{
  "execution_path": "...",
  "round": 3,
  "guard_type": "duplicate_tool_call|no_progress|budget_exceeded|tool_timeout|cancelled",
  "reason": "...",
  "tool_call_id": "...",
  "recommended_action": "stop|ask_user|degrade|handoff"
}
```

### 5. Guard 行为

触发 Guard 后支持以下至少一种明确行为：

- stop：终止并说明原因；
- ask_user：请求用户确认是否继续；
- degrade：输出阶段性结果；
- handoff：交给 Manager 或人工处理。

不得静默继续循环。

### 6. 前端展示

前端应展示：

- Guard 类型；
- 简明原因；
- 当前轮次；
- 建议操作；
- 如果允许继续，提供明确确认入口。

### 7. 路径适配

Guard 应适配：

- chat_legacy
- chat_langgraph
- studio_chat_loop
- agentteams_worker_react

可以先通过公共工具函数/Guard Service 实现，不要求本阶段强制合并所有 Runtime。

## 测试要求

至少覆盖：

1. 同一工具同一参数连续调用触发 Guard；
2. 多轮无新信息触发 no_progress；
3. 达到工具调用预算触发 budget_exceeded；
4. 工具超时触发 tool_timeout；
5. Guard 后不继续盲目调用工具；
6. 前端能展示 Guard 原因。

## 交付要求

1. 修改代码并补充测试。
2. 输出 Guard 类型和触发条件表。
3. 输出每种 Guard 的默认处理策略。
4. 明确哪些路径已接入，哪些路径暂未接入及原因。

## 验收标准

- [ ] 重复工具调用不会无限循环。
- [ ] 无进展任务能被识别。
- [ ] 达到预算后有明确终止或确认机制。
- [ ] Guard 事件进入统一事件链。
- [ ] 前端能理解并展示 Guard 状态。
```

---

# 附录 E：阶段 5 编码提示词——自动化闭环测试

```text
你是一名资深测试架构师，熟悉 Python 后端测试、异步事件流测试、fake provider、fake tool、LangGraph、沙盒执行和前端状态测试。

任务：为 OmicHub Agent 思考—工具—结果回灌—再思考闭环补齐自动化测试。先阅读现有测试结构和相关实现，禁止为了测试方便重写业务逻辑。

## 背景

静态代码已经显示多条路径存在工具循环，但还缺少端到端断言来证明：

- 工具结果确实写入模型上下文；
- 下一轮模型调用确实使用了工具结果；
- Studio 沙盒结果没有丢失；
- Worker 子 Agent 确实继续执行；
- legacy 和 LangGraph 行为一致；
- 前端事件投影能反映真实闭环。

## 测试任务

### 1. 普通 AI 助手 fake provider 多轮测试

构造 fake provider，固定返回：

```text
第 1 轮：reasoning + tool_call(workspace_read_file)
工具结果：文件包含 3 个 sheet
第 2 轮：reasoning + tool_call(sandbox_execute)
工具结果：统计结果
第 3 轮：reasoning + final content
```

断言：

- 发生 3 次模型调用；
- 第 2 轮上下文包含第 1 个工具结果；
- 第 3 轮上下文包含第 1、2 个工具结果；
- 最终正文不混入 reasoning；
- 事件链包含 agent_context_reinjected 和 agent_turn_continued。

### 2. Studio 沙盒回灌测试

测试任务：读取 CSV，计算分组均值，输出图表。

断言：

- 原始文件没有被覆盖；
- stdout/stderr 正确进入工具结果；
- 图表产物路径进入最终上下文；
- 代码失败后模型能基于 stderr 修正；
- 不允许伪造执行成功。

### 3. 协助室普通会话测试

覆盖：

1. 纯讨论问题：不强制工具调用；
2. 明确要求读取文件：进入 tool_execute；
3. 文件不存在：触发 room.ask_user 或明确失败；
4. 工具失败：Manager 明确说明失败，不说“已完成”；
5. 工具结果进入 Manager 最终回复上下文。

### 4. AgentTeams Worker 测试

固定 Worker 返回：

```text
第 1 轮：reasoning + tool_call
工具结果：部分结果
第 2 轮：reasoning + tool_call
工具结果：完整结果
第 3 轮：final answer
```

断言：

- 产生 Worker reasoning 事件；
- 产生 Worker tool_call/tool_result；
- 第二次模型调用包含第一轮 role=tool；
- Manager 收到 Worker 最终结构化结果；
- Manager 不直接采信未验证的工具参数。

### 5. legacy 与 LangGraph 一致性测试

同一 fake provider、同一工具、同一消息历史分别运行：

- legacy 手写循环；
- LangGraph 循环。

断言：

- 工具调用次数一致；
- 工具结果回灌次数一致；
- 最终正文一致；
- ask_user/handoff 终止行为一致；
- usage 统计一致或差异可解释；
- 统一事件语义一致。

### 6. 前端事件投影测试

至少测试：

- tool_call 能匹配 tool_result；
- context_reinjected 后展示“已进入下一步分析”；
- Worker 时间线能按 round 分组；
- Guard 事件能正确显示；
- 事件乱序或重复时不崩溃。

## 交付要求

1. 增加测试文件和必要测试工具。
2. 输出测试矩阵。
3. 标记哪些测试是单元测试、集成测试、端到端测试。
4. 如果某项真实环境测试暂时无法自动化，说明原因并给出手动验收脚本。
5. 不要通过放宽断言来让测试通过。

## 验收标准

- [ ] fake provider 多轮工具闭环测试通过。
- [ ] Studio 沙盒结果回灌测试通过。
- [ ] 协助室普通消息路由测试通过。
- [ ] Worker 多轮工具测试通过。
- [ ] legacy 与 LangGraph 一致性测试通过。
- [ ] 前端事件投影测试通过。
```

---

# 附录 F：总体验收 Checklist

## 执行路径

- [ ] 普通 AI 助手 legacy 标记为 `chat_legacy`。
- [ ] 普通 AI 助手 LangGraph 标记为 `chat_langgraph`。
- [ ] AI 工作台标记为 `studio_chat_loop`。
- [ ] 协助室普通会诊标记为 `agentteams_manager_consultation`。
- [ ] 协助室工具执行标记为 `agentteams_tool_execution`。
- [ ] Worker 子 Agent 标记为 `agentteams_worker_react`。

## 统一事件

- [ ] 每轮开始有 `agent_turn_started`。
- [ ] 工具调用有 `agent_tool_call` / `agent_tool_started`。
- [ ] 工具结果有 `agent_tool_result`。
- [ ] 工具结果回灌后有 `agent_context_reinjected`。
- [ ] 下一轮模型调用前有 `agent_turn_continued`。
- [ ] 最终完成有 `agent_final_result`。
- [ ] 失败有 `agent_turn_failed`。
- [ ] Guard 有 `agent_loop_guard_triggered`。

## 协助室路由

- [ ] 纯讨论不强制工具调用。
- [ ] 明确读取/检索/复核进入工具路径。
- [ ] 多步骤任务进入 Case。
- [ ] 缺信息触发 `room.ask_user`。
- [ ] 工具失败不伪造成功。

## 前端展示

- [ ] 默认展示结构化阶段状态。
- [ ] debug 模式可查看工具参数和结果摘要。
- [ ] 原始 reasoning 不作为唯一用户反馈。
- [ ] Worker 工具过程在房间时间线可见。
- [ ] Overdrive 与普通助手/Studio 展示互不污染。

## 运行保护

- [ ] 重复工具调用能被识别。
- [ ] 无进展循环能被识别。
- [ ] 轮次、工具次数、耗时和预算有上限。
- [ ] Guard 触发后不会静默继续。
- [ ] 用户能看懂 Guard 原因和下一步选择。

## 测试

- [ ] fake provider 多轮闭环测试通过。
- [ ] Studio 沙盒回灌测试通过。
- [ ] 协助室工具路由测试通过。
- [ ] Worker 多轮工具测试通过。
- [ ] legacy 与 LangGraph 一致性测试通过。
- [ ] 前端事件投影测试通过。

---

# 附录 G：风险与回退

| 风险 | 影响 | 应对 | 回退 |
|---|---|---|---|
| 新事件过多导致前端刷屏 | 用户体验下降 | 通过 visibility 控制默认展示 | 前端隐藏新事件，仅保留日志 |
| execution_path 漏标 | 仍无法审计 | 在入口层强制注入默认值 | 使用 `unknown` 并输出告警日志 |
| 协助室路由误判 | 纯讨论被强制工具化 | 保守策略：不明确时不强行工具化 | 回退到原 Manager 会诊 |
| Worker 时间线信息过多 | 房间界面混乱 | 聚合展示，debug 折叠 | 回退到现有进度卡 |
| Guard 阈值过严 | 正常任务被中断 | 先告警不终止，再逐步收紧 | 只记录 Guard，不改变执行 |
| legacy/LangGraph 行为不一致 | 双路径维护成本增加 | 建立一致性测试 | 暂以 legacy 为默认路径 |
| 工具结果摘要泄漏敏感信息 | 安全风险 | debug/internal 分级，摘要脱敏 | 默认只显示工具状态，不显示内容 |

---

# 附录 H：推荐实施顺序

```text
阶段 0：基线核查
  ↓
阶段 1：统一 execution_path 与事件模型
  ↓
阶段 2：协助室普通消息工具路由
  ↓
阶段 3：Overdrive/Worker 结构化时间线
  ↓
阶段 5：先补关键自动化闭环测试
  ↓
阶段 4：Loop Guard 逐步收紧
  ↓
阶段 6：产品化文案、审计和文档收口
```

说明：阶段 5 原本在阶段 4 后，但建议把关键闭环测试前置。原因是统一事件和协助室路由改动都可能影响上下文回灌，必须先用测试锁定核心行为，再增加 Guard，避免 Guard 把真正的问题掩盖掉。

---

# 附录 I：给编码 Agent 的总控提示词

如果希望编码 Agent 按整个计划分阶段执行，可以粘贴下面这段作为总控提示词，再根据当前阶段追加附录 A～E 的对应提示词。

```text
你是一名资深全栈架构师和编码 Agent，负责在现有 OmicHub 项目中优化 Agent 思考—工具—结果回灌—再思考闭环。

## 总体原则

1. 先阅读现有代码，再修改。
2. 在现有架构上优化，禁止推倒重写。
3. 不改变无关模块和无关页面样式。
4. 每一步都必须保留兼容性，旧事件和旧前端不能因为新增能力直接崩溃。
5. 所有结论和修改都要能落到文件路径、事件名和测试用例上。
6. 不允许伪造工具执行结果；工具失败必须明确暴露。
7. 原始 reasoning 默认不作为唯一用户反馈，用户态优先展示结构化阶段状态。

## 优化目标

将普通 AI 助手、AI 工作台 Studio、AgentTeams 协助室和 Worker 的执行链统一为可观测、可控制、可测试的 Agent 工作流：

```text
用户输入
→ 执行路径判定
→ 模型思考
→ 工具调用
→ 工具执行
→ 工具结果写入上下文
→ context_reinjected 事件
→ 模型继续思考
→ 必要时继续调用工具
→ Guard / 汇总 / QC
→ 最终结果
```

## 分阶段执行

请严格按以下顺序执行，每个阶段完成后先输出变更说明和测试结果，再进入下一阶段：

1. 阶段 0：基线核查与现有事件清单；
2. 阶段 1：统一 execution_path 与 Agent Loop 事件模型；
3. 阶段 2：协助室普通消息工具路由；
4. 阶段 3：Overdrive/Worker 结构化时间线；
5. 阶段 5：自动化闭环测试前置；
6. 阶段 4：Loop Guard 与运行保护；
7. 阶段 6：产品化文案、审计和文档收口。

## 每阶段交付格式

每个阶段都必须输出：

1. 本阶段目标；
2. 修改文件清单；
3. 核心实现说明；
4. 事件序列或路由序列示例；
5. 新增/修改测试；
6. 验收 checklist；
7. 暂未完成的项和原因。

## 禁止事项

- 禁止不读代码直接重构；
- 禁止删除旧事件导致前端失联；
- 禁止把普通 Manager 会诊伪装成完整工具执行；
- 禁止工具失败后仍输出“已完成”；
- 禁止为了让测试通过而放宽关键断言；
- 禁止把 internal 信息默认展示给普通用户。

请先执行阶段 0，并在完成后等待我确认，再继续阶段 1。
```

---

## 最终建议

本次优化不要一开始就追求“把所有执行路径合并成一个 Runtime”。更稳妥的顺序是：

1. **先统一语言**：所有路径都知道自己是谁，轮到第几轮，工具结果去了哪里。
2. **再补关键缺口**：协助室普通消息需要工具时，必须能真正进入工具路径。
3. **然后让用户看见**：Worker 的执行过程以结构化方式进入房间时间线。
4. **用测试锁行为**：先把闭环行为固化，再逐步加 Guard 和预算控制。
5. **最后再谈统一 Runtime**：等事件、测试、路由都稳定后，再考虑进一步合并 legacy 与 LangGraph 的实现细节。

这样可以最大限度降低重构风险，同时最快解决当前最影响信任和可维护性的几个问题。
