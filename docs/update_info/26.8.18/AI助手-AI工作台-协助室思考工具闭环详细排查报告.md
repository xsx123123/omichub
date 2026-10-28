# AI 助手、AI 工作台与协助室 Agent 思考-工具闭环详细排查报告

> 排查日期：2026-08-18  
> 排查范围：OmicHub 普通 AI 助手、AI 工作台（Studio）、AgentTeams 协助室及 Case/Overdrive 执行链  
> 关联截图：`docs/info/26.8.18/image copy 7.png`  
> 排查方式：代码静态追踪、事件链追踪、前端状态处理追踪、既有测试入口核对  
> 本报告不替代真实环境端到端压测；凡标记为“代码已具备”的结论，仍建议按文末验收用例在真实模型和真实工具环境复测。

---

## 1. 用户关心的问题

本次重点核对下面这条循环是否真正存在，而不是只在界面上显示“思考中”：

```text
用户输入
  ↓
模型思考
  ↓
模型决定调用工具
  ↓
工具执行
  ↓
工具结果回到模型上下文
  ↓
模型结合结果再次思考
  ↓
必要时再次调用工具
  ↓
模型输出最终结果
```

其中需要区分四个概念：

1. **模型 reasoning stream**：模型或兼容网关返回的 `reasoning_content`，属于模型推理内容流。
2. **工具调用循环**：模型是否实际产生 `tool_calls`，后端是否执行工具并把结果重新写入上下文。
3. **编排流程**：Manager、Planner、Worker、QC 等角色之间的计划、派发和汇总。
4. **前端展示**：用户是否看得到 reasoning、工具调用、工具结果和各轮次之间的关系。

“界面显示思考”只能证明第 1 项或展示逻辑存在，不能单独证明第 2 项闭环存在。本报告因此分别核对。

---

## 2. 总体结论

| 场景 | 后端是否有思考流 | 是否有工具结果回灌 | 是否支持多轮继续调用 | 前端是否完整展示 | 结论 |
|---|---:|---:|---:|---:|---|
| 普通 AI 助手 | ✅ | ✅ | ✅ | ✅ 基本支持 | 完整闭环 |
| LangGraph 普通 Agent | ✅ | ✅ | ✅ | ✅ 基本对齐 legacy | 完整闭环 |
| AI 工作台 Studio | ✅ | ✅ | ✅ | ✅ 工具卡片/产物较完整 | 完整闭环，工具类型更受控 |
| 协助室普通 Manager 会话 | ✅/取决于模型 | ⚠️ 不保证每条消息使用工具 | ⚠️ 主要是一次会诊调用 | ⚠️ 主要展示最终房间发言 | 不是每条消息都走完整 ReAct |
| 协助室 Case/Overdrive Worker | ✅ | ✅ | ✅ | ⚠️ 中间过程展示不完全统一 | 后端闭环，展示层不完整 |

最重要的结论是：

> **普通 AI 助手和 AI 工作台已经实现了“思考 → 工具 → 结果回灌 → 再思考”的真正循环。AgentTeams 协助室的 Worker 执行链后端也具备该循环，但协助室普通 Manager 会话不是每次都走该循环，且前端没有把所有 Worker reasoning/tool result 统一呈现出来。**

---

## 3. 核心事件与数据结构

### 3.1 Provider 层：reasoning 与正文分流

OpenAI 兼容 Provider 在流式响应中分别读取：

- `reasoning_content`：作为 `ChatChunk(type="text", metadata={"is_reasoning": True})`
- `content`：作为普通正文 `ChatChunk(type="text")`
- `tool_calls`：累积后作为 `ChatChunk(type="tool_calls")`
- 流结束：作为 `ChatChunk(type="done")`

证据：

- `src/omichub/infrastructure/ai_provider/openai_compatible.py:494-511`
- 工具调用分片累积：`src/omichub/infrastructure/ai_provider/openai_compatible.py:513` 附近

这说明平台没有把 reasoning 和最终正文混成同一段文本。后端可以做到：

```text
reasoning_content → thought / reasoning 展示通道
content           → 正文展示通道
tool_calls        → 工具调用事件通道
tool result       → 工具结果事件通道
```

### 3.2 前端层：思考与正文分开保存

普通助手和 AgentHub 在收到文本事件时：

- `isReasoning=true` 时写入 `streamingThought` / `aiMsg.thought`
- 普通正文写入 `streamingContent` / `aiMsg.content`
- 工具调用写入 `toolCalls` 和交错 `timeline`
- 工具结果按 `tool_call_id` 找回对应工具卡片

证据：

- `frontend/src/stores/agentHub.ts:2007-2024`
- 工具调用事件：`frontend/src/stores/agentHub.ts:2260-2278`
- 工具结果事件：`frontend/src/stores/agentHub.ts:2279` 附近
- 普通聊天 Store：`frontend/src/stores/chatSession.ts:201-208`

### 3.3 “思考已完成”不是工具循环完成

截图 `image copy 7.png` 中出现的“思考已完成”可以证明前端收到了或正在展示 reasoning 状态，但仍需要同时看到以下事件，才能证明完整闭环：

```text
text(is_reasoning)
→ tool_call
→ tool_result
→ text(is_reasoning)
→ tool_call / 正文
→ done
```

如果只有：

```text
text(is_reasoning)
→ text(正文)
→ done
```

则只是一次带思考流的普通回答，并没有发生工具循环。

---

## 4. 普通 AI 助手详细排查

### 4.1 路由入口

普通 Agent 根据配置选择两种后端执行引擎：

1. **legacy 手写循环**：默认路径。
2. **LangGraph 图运行时**：当 Agent 的 `features.engine == "langgraph"` 且不是 Studio、不是 MAS Orchestrator 时启用。

证据：

- LangGraph 分流：`src/omichub/application/services/chat_service.py:6425-6453`
- 手写循环入口：`src/omichub/application/services/chat_service.py:6455-6467`

### 4.2 手写循环的实际时序

代码中的核心循环是：

```text
for _round in range(max_rounds):
    调用 provider_manager.chat_stream(...)
    收集正文、reasoning 和 tool_calls
    如果没有 tool_calls：完成并返回
    如果有 tool_calls：
        将 assistant(tool_calls) 写入上下文
        逐个执行工具
        将 role=tool 的结果写入上下文
        进入下一轮
```

证据拆解：

| 环节 | 代码证据 | 说明 |
|---|---|---|
| 轮次循环 | `chat_service.py:6460` | 默认最多 100 轮，确认后最多 1000 轮 |
| 调用模型 | `chat_service.py:6467-6474` | 传入工具、温度、最大 Token、深度思考开关 |
| 接收 reasoning | `chat_service.py:6476-6481` | reasoning 不混入最终正文，但继续透传 |
| 无工具时结束 | `chat_service.py:6515-6539` | 生成最终消息并发出 done |
| 有工具时回灌 | `chat_service.py:6541-6552` | 写入 assistant 的 tool_calls 和 reasoning_content |
| 工具执行 | `chat_service.py:6564` 起 | 根据工具类型分流到 Studio、MCP、子 Agent、沙盒等 |
| 工具结果回灌 | `chat_service.py:6615` 附近及后续 | 追加 `role: tool` 消息，进入下一次模型调用 |

### 4.3 DeepSeek/兼容模型的关键处理

当上一轮同时有 reasoning 和 tool call 时，系统会把上一轮 reasoning 写回：

```python
assistant_tool_message["reasoning_content"] = round_reasoning
```

证据：`src/omichub/application/services/chat_service.py:6548-6552`

这是必要的兼容处理。如果只回灌工具结果而丢掉上一轮 reasoning，部分 DeepSeek/方舟兼容接口可能在下一轮出现空响应或无法继续生成。

### 4.4 普通助手结论

普通 AI 助手满足目标流程：

```text
思考 → 使用工具 → 读取工具结果 → 再思考 → 再使用工具或回答
```

但有三个边界：

1. **不是每次都多轮**：只有模型真的返回 `tool_calls` 才进入下一轮。
2. **不是每个模型都有 reasoning stream**：取决于模型、Provider 和 `deep_thinking` 配置。
3. **工具结果是否足够**由模型判断，后端不会强制模型一定再思考一次。

---

## 5. LangGraph 普通 Agent 详细排查

LangGraph 不是另一种业务逻辑，而是把 legacy 手写循环图化。

### 5.1 图节点职责

`src/omichub/infrastructure/execution/langgraph_nodes.py` 文件头部明确说明：

- `llm_call`：调用模型，透出 text/reasoning，收集 tool_calls，追加 assistant 消息。
- `tool_exec`：逐个执行 tool_call，透出 tool_call/tool_result，追加 role=tool 消息。

证据：`src/omichub/infrastructure/execution/langgraph_nodes.py:1-10`

### 5.2 图循环

```text
START
  ↓
llm_call
  ├─ 没有 tool_calls → END
  └─ 有 tool_calls
        ↓
      tool_exec
        ↓
      llm_call
        ├─ 没有 tool_calls → END
        └─ 有 tool_calls → 继续循环
```

工具节点把工具结果拆成两条通道：

- `llm_payload`：给模型继续推理的内容。
- `ui_payload`：给前端渲染图表、文件、工具卡片等 UI 内容。

证据：`src/omichub/infrastructure/execution/langgraph_nodes.py:176-212`

运行时还使用：

```text
recursion_limit = 2 * max_rounds + 2
```

证据：`src/omichub/infrastructure/execution/langgraph_runtime.py:102-114`

### 5.3 LangGraph 结论

LangGraph 路径满足同样的闭环，且比简单的一次 LLM 调用更明确：

```text
llm_call → conditional routing → tool_exec → llm_call
```

目前它与 legacy 路径的主要差异是：

- legacy 在 `ChatService` 中直接写循环。
- LangGraph 将同样的逻辑拆成图节点。
- 两者都将 reasoning 透传、工具结果回灌、工具事件发送到前端。

---

## 6. AI 工作台（Studio）详细排查

### 6.1 Studio 是否单独实现了另一套循环

结论：**没有完全另起一套循环，而是复用 ChatService 核心循环。**

代码在同一个工具处理循环中通过 `studio_mode` 分流：

- `STUDIO_TOOL_NAMES`：Studio 工具。
- `CAPABILITY_TOOL_NAMES`：能力加载和能力工具。
- `ask_user`：普通会话和 Studio 都可使用的澄清工具。
- 其他工具：按 MCP server、handoff、subagent、skill 等通道处理。

证据：`src/omichub/application/services/chat_service.py:6573-6629`

### 6.2 Studio 工具闭环

典型 Studio 流程如下：

```text
用户提出分析目标
  ↓
模型思考并选择 sandbox_execute / workspace_read / datahub_import 等工具
  ↓
ChatService 将工具路由至 Studio capability 或沙盒
  ↓
工具返回 stdout、stderr、文件、图表、错误或状态
  ↓
结果以 tool result 写回模型上下文
  ↓
模型复核结果
  ↓
必要时修正代码或再次读取文件
  ↓
输出最终分析结论和产物
```

沙盒代码执行本身是流式的：

- 创建/获取沙盒会话：`src/omichub/application/services/sandbox_service.py:55-84`
- 执行代码：`src/omichub/application/services/sandbox_service.py:99-135`
- 支持 Python、R、Bash。

### 6.3 Studio 与普通助手的差别

| 项目 | 普通助手 | AI 工作台 |
|---|---|---|
| 工具来源 | MCP、平台工具、技能、子 Agent、聊天沙盒等 | Studio capability、沙盒、工作区工具为主 |
| 结果类型 | 文本、结构化结果、检索结果 | stdout、图表、文件、代码、工作区产物 |
| 循环机制 | ChatService / LangGraph | ChatService 手写循环，Studio 模式不进入普通 LangGraph 分流 |
| 用户确认 | ask_user、工具审批 | 计划确认、代码/工具审批、ask_user |
| 最终输出 | 文本或工具卡片 | 文本 + 图表 + 文件/报告产物 |

### 6.4 Studio 结论

AI 工作台已经具备目标闭环，而且是平台中最适合验证该闭环的场景：

```text
模型思考
→ 读文件/执行代码
→ 获取实际输出
→ 模型复核输出
→ 修改代码或继续调用工具
→ 形成可验收产物
```

需要注意：沙盒执行完成并不等于整个任务完成，必须确认后续模型确实收到并使用了沙盒结果。现有代码已经提供了回灌机制，但建议增加自动化事件链测试。

---

## 7. 协助室普通会话详细排查

### 7.1 房间普通消息流程

AgentTeams 房间收到 `room.user_message` 后，由 `AgentTeamsRoomResponseService` 处理：

```text
获取 Case 快照和最近事件
  ↓
判断是否为执行请求
  ├─ clarify：落 room.ask_user，等待用户补充
  ├─ execute：触发 planning / Case 执行
  ├─ degraded：降级成普通会诊
  └─ none：走普通 Manager 会诊
  ↓
调用 AgentConsultationService
  ↓
落 room.agent_message 或 room.ask_user
  ↓
SSE / 房间消息流展示
```

证据：

- 房间响应入口和互斥锁：`src/omichub/application/services/agentteams_room_response_service.py:95-117`
- 执行意图分流：`src/omichub/application/services/agentteams_room_response_service.py:218-239`
- Manager 会诊调用：`src/omichub/application/services/agentteams_room_response_service.py:163-175`
- 会诊结果落库：`src/omichub/application/services/agentteams_room_response_service.py:185-211`

### 7.2 普通 Manager 会诊不是固定 ReAct 循环

普通房间会诊调用中使用：

```python
capability="interpretation"
requested_tools=[]
```

证据：`src/omichub/application/services/agentteams_room_response_service.py:165-174`

因此这条路径更接近：

```text
读取 Case 上下文
→ Manager/会诊 Agent 分析
→ 返回结构化结论
→ 写入房间
```

不能简单认为每一条协助室消息都必然执行：

```text
思考 → 工具 → 结果 → 再思考
```

原因是：

1. 有些房间消息只是讨论或澄清，不需要工具。
2. 普通 Manager 会诊接口本身使用只读会诊模式。
3. 工具是否暴露给下游 Agent 还取决于该 Agent 的能力注册和工具配置。
4. 如果意图判断为执行请求，消息会转入 Case/Work Item 路径，而不是继续普通会诊。

### 7.3 协助室前端展示

前端房间主要处理：

- `room_speech`
- `room.ask_user`
- `overdrive_progress`
- Manager/Worker 发言
- 计划、审批、质控和交付卡片

证据：

- 房间消息事件处理：`frontend/src/stores/agentHub.ts:327-340`
- 房间消息模型：`frontend/src/stores/agentHub.ts:243-256`
- 房间时间线渲染：`frontend/src/views/AgentTeamsRoomView.vue:1172-1224`

当前房间展示重点是“谁说了什么、执行到哪一步、结果是什么”，而不是把 Manager 每一段 reasoning 和每次工具回灌完全展开。

---

## 8. 协助室 Case / Overdrive 详细排查

### 8.1 Worker 具备真实子循环

`ParallelSubAgentService` 的设计说明明确写出：子 Agent 运行受限的 ReAct 循环，并且可以调用 builtin 工具。

证据：`src/omichub/application/services/parallel_subagent_service.py:1-15`

核心循环：

```text
for _round in range(max_rounds):
    provider_manager.chat_stream(...)
    收集 reasoning / 正文 / tool_calls
    没有 tool_calls → 结束本子任务
    有 tool_calls → 执行工具
    将工具结果追加为 role=tool
    进入下一轮
```

证据：

- 子循环：`src/omichub/application/services/parallel_subagent_service.py:610-623`
- reasoning 事件：`src/omichub/application/services/parallel_subagent_service.py:623-635`
- tool call 事件：`src/omichub/application/services/parallel_subagent_service.py:646-659`
- 工具执行：`src/omichub/application/services/parallel_subagent_service.py:765-778`
- 工具结果回灌：`src/omichub/application/services/parallel_subagent_service.py:789-801`
- 达到轮次上限的阶段性结果：`src/omichub/application/services/parallel_subagent_service.py:802-810`

### 8.2 Worker 的完整流程

```text
Manager 规划
  ↓
拆分 Work Item
  ↓
Worker 启动
  ↓
Worker reasoning
  ↓
Worker tool_call
  ↓
执行工作区、沙盒、检索或平台工具
  ↓
worker_tool_result
  ↓
Worker 再次 reasoning
  ↓
继续工具调用或输出结论
  ↓
提交 Worker 结果
  ↓
Manager 汇总 / QC / 交付
```

这部分后端确实实现了用户要求的多轮闭环。

### 8.3 Worker 工具安全边界

子 Agent 会剥离部分控制类工具，避免：

- 子 Agent 递归调用 `parallel_subagents`。
- 子 Agent 改变父会话的 Agent 身份。
- 子 Agent 自己创建新的 AgentTeams Case。
- 子 Agent 直接修改长期记忆。

证据：`src/omichub/application/services/parallel_subagent_service.py:56-67`

这属于正确的能力收敛，不是工具循环缺失。

### 8.4 Overdrive 前端展示缺口

在 AgentHub 中，Overdrive 模式收到 reasoning 时会直接跳过普通消息的 thought 展示：

```typescript
if (effectiveOverdrive) return
```

证据：`frontend/src/stores/agentHub.ts:2007-2012`

这意味着：

- Worker 后端可能真的在思考。
- Worker 后端可能真的在调用工具并接收结果。
- 但用户不一定能在普通消息气泡里看到完整 reasoning。
- 用户更多看到的是 Worker 发言、进度卡和结果卡。

因此“后端闭环”和“前端可见闭环”目前不是同一个概念。

---

## 9. 四种常规流程梳理

### 9.1 普通问答流程

适用于不需要工具的问题：

```text
用户输入
  ↓
构造历史上下文
  ↓
调用模型
  ↓
模型返回 reasoning（可选）
  ↓
模型返回正文
  ↓
保存并展示
```

### 9.2 单工具流程

适用于一次查询或一次文件读取：

```text
用户输入
  ↓
模型思考
  ↓
调用 workspace_read / Europe PMC / web_search 等工具
  ↓
得到工具结果
  ↓
工具结果回灌模型
  ↓
模型基于结果回答
```

### 9.3 多工具、多轮分析流程

适用于分析、绘图、文献研究和代码执行：

```text
用户目标
  ↓
模型识别缺口
  ↓
读取文件或检索资料
  ↓
结合结果判断下一步
  ↓
执行代码或调用第二个工具
  ↓
读取实际输出
  ↓
发现问题时修改参数/代码并重试
  ↓
结果通过质量检查
  ↓
输出结论和产物
```

### 9.4 AgentTeams Case 流程

适用于长流程、需要多个专家或需要审批的任务：

```text
用户提出复合任务
  ↓
Manager 判断 chat / clarify / execute
  ↓
必要时 ask_user 澄清
  ↓
Planner 形成计划
  ↓
用户确认计划
  ↓
创建 Case / Work Item
  ↓
招募 Worker
  ↓
Worker 各自执行多轮工具循环
  ↓
Worker 提交阶段结果
  ↓
Manager 汇总
  ↓
QC 检查
  ↓
交付结果
```

---

## 10. 当前实现的主要问题

### P0：路径语义容易混淆

普通 AI 助手、Studio、AgentTeams 普通会诊、AgentTeams Case 都存在“Agent”概念，但实际循环不同：

| 名称 | 实际含义 |
|---|---|
| 普通 AI 助手 Agent | 单 Agent 多轮工具循环 |
| Studio Agent | 单 Agent 多轮工具循环 + 沙盒能力 |
| 协助室 Manager | Case 级路由、会诊、计划和汇总角色 |
| 协助室 Worker | 受限子 Agent 多轮工具循环 |

建议在日志和前端事件中明确增加 `execution_path`，例如：

```text
chat_legacy
chat_langgraph
studio_chat_loop
agentteams_manager_consultation
agentteams_worker_react
```

### P1：协助室普通会话不保证工具闭环

普通 Manager 会诊以 `requested_tools=[]` 调用，属于“上下文会诊优先”路径。对于用户明确要求检索、读取文件、复核结果的房间消息，最好显式进入受控工具循环，而不是只做一次会诊。

### P1：Overdrive 的 reasoning 和工具事件展示不完整

后端已产生 Worker reasoning/tool 事件，但前端主要展示 Worker speech、进度和结果。用户无法始终确认：

```text
Worker 是否真的读取了输入
Worker 是否真的执行了工具
Worker 是否根据工具结果修正了下一步
```

### P1：缺少统一的“循环轮次”事件

当前可以看到 `tool_call`、`tool_result`、`room_speech` 等事件，但没有统一的：

```json
{
  "type": "agent_loop_step",
  "path": "studio_chat_loop",
  "round": 2,
  "phase": "after_tool_result",
  "agent_id": "agent-general",
  "tool_call_id": "..."
}
```

没有统一轮次事件时，审计者很难仅凭前端判断“工具结果是否真的进入了下一次模型调用”。

### P2：reasoning 展示偏原始

截图中的 reasoning 是模型原始思考文本，存在以下问题：

- 中英文混杂。
- 可能包含内部实现细节。
- 可能暴露文件名、代码修改过程或系统判断。
- 用户看到“思考已完成”，但不一定知道工具调用结果是否已纳入。

更稳定的产品形态应是结构化阶段状态：

```text
正在分析任务
→ 正在读取输入文件
→ 已得到文件检查结果
→ 正在根据结果调整分析方案
→ 正在执行第二步分析
→ 已完成结果复核
```

原始 reasoning 可以作为调试模式或折叠详情，不建议作为唯一用户反馈。

### P2：现有代码证据还缺少真实端到端链路断言

静态代码可以证明循环存在，但不能证明每个 Provider、每个工具和每种 Agent 配置都能稳定完成闭环。当前应补：

- fake provider 多轮 tool call 测试。
- Studio 沙盒结果回灌测试。
- Worker tool result 后再次调用测试。
- 协助室 room event 投影测试。
- LangGraph 与 legacy 结果一致性测试。

---

## 11. 建议的统一事件链

为了让三个入口的行为可观测，建议统一抽象以下事件：

```text
agent_turn_started
agent_reasoning_delta
agent_tool_call
agent_tool_started
agent_tool_result
agent_context_reinjected
agent_turn_continued
agent_final_result
agent_turn_failed
```

推荐每个事件至少携带：

```json
{
  "session_id": "...",
  "case_id": "...",
  "run_id": "...",
  "agent_id": "...",
  "execution_path": "studio_chat_loop",
  "round": 2,
  "tool_call_id": "...",
  "timestamp": "...",
  "visibility": "user|debug|internal"
}
```

其中：

- `user`：展示为简化后的阶段状态。
- `debug`：展示工具名称、参数摘要、结果摘要。
- `internal`：只写审计日志，不直接展示原始 reasoning。

---

## 12. 建议的验收用例

### 12.1 普通 AI 助手

构造一个 fake provider，固定返回：

```text
第 1 轮：reasoning + tool_call(workspace_read_file)
工具结果：文件包含 3 个 sheet
第 2 轮：reasoning + tool_call(sandbox_execute)
工具结果：统计结果
第 3 轮：reasoning + final content
```

验收：

- 收到 3 段模型调用。
- 每轮都有正确的 assistant/tool 消息顺序。
- 第 2 轮能看到第 1 个工具结果。
- 第 3 轮能看到第 1、2 个工具结果。
- 最终正文不混入 reasoning。

### 12.2 AI 工作台

测试任务：读取 CSV，计算分组均值，再输出图表。

验收顺序：

```text
workspace/datahub_import
→ sandbox_execute(read)
→ sandbox_execute(statistics)
→ sandbox_execute(plot)
→ 模型读取执行结果
→ 输出图表和报告
```

同时断言：

- 原始文件没有被覆盖。
- stdout/stderr 正确进入工具结果。
- 产物路径进入最终上下文。
- 失败后模型能基于错误修正代码，而不是直接伪造成功。

### 12.3 协助室普通会话

分别测试：

1. 纯讨论问题：不应强制创建工具调用。
2. “读取这个文件并判断”：应进入受控工具读取路径。
3. 缺文件：应产生 `room.ask_user`，而不是编造读取结果。
4. 工具失败：Manager 应明确说明失败，不应生成“已完成”。

### 12.4 AgentTeams Worker

固定 Worker 返回：

```text
第 1 轮：reasoning + tool_call
工具结果：部分结果
第 2 轮：reasoning + tool_call
工具结果：完整结果
第 3 轮：final answer
```

验收：

- 产生 `worker_reasoning_delta`。
- 产生 `worker_tool_call`。
- 产生 `worker_tool_result`。
- 第二次模型调用的 messages 包含第一轮 `role=tool`。
- Manager 收到的是 Worker 最终结构化结果，而不是未验证的工具参数。

### 12.5 LangGraph 与 legacy 一致性

同一 fake provider、同一工具、同一消息历史分别运行：

- legacy 手写循环。
- LangGraph 循环。

要求两条路径至少一致：

- 工具调用次数。
- 工具结果回灌次数。
- 最终正文。
- ask_user / handoff 的终止行为。
- usage 统计。

---

## 13. 最终判断清单

- [x] Provider 能区分 reasoning、正文、tool_calls、done。
- [x] 普通助手 legacy 路径存在多轮工具循环。
- [x] 普通助手 LangGraph 路径存在 llm_call/tool_exec 循环。
- [x] 普通助手将工具结果作为 `role=tool` 回灌模型。
- [x] AI 工作台复用核心循环并把工具路由到沙盒/Studio capability。
- [x] Worker 子 Agent 存在受限多轮 ReAct 循环。
- [x] Worker 将工具结果回灌下一轮模型上下文。
- [ ] 协助室普通 Manager 会话保证每条消息都进入工具循环。
- [ ] 协助室前端完整展示 reasoning → tool_call → tool_result → 再 reasoning。
- [ ] 三条入口使用统一的 loop round / context reinjected 事件。
- [ ] 已有端到端测试覆盖所有 Provider、工具和 Agent 配置组合。

## 14. 结论摘要

当前 OmicHub 不是“只有一个思考动画而没有循环”。普通 AI 助手、AI 工作台以及 AgentTeams Worker 后端都已经具备实质性的多轮工具调用能力，工具结果也确实会回灌模型上下文。

当前最需要继续优化的是协助室的一致性和可观测性：

1. 普通协助室 Manager 会诊要区分“纯对话”和“需要工具的受控执行”。
2. Worker 的 reasoning/tool 事件要在房间时间线中以结构化方式展示或至少记录可审计摘要。
3. 三条路径应统一 loop round、工具回灌和最终收敛事件。
4. 用 fake provider + fake tool 补齐自动化闭环测试，避免只通过静态代码推断行为。

