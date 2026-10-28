# AI 助手架构更新：统一入口「智能助手」+ 菜单栏默认隐藏（2026-07-22）

> 关联文档：`docs/26.7.21/ai_assistant_review.md`（LangGraph 引擎）、
> `docs/26.7.21/mcp_ai_assistant_integration.md`（MCP 联动）、
> `docs/26.7.21/studio_hitl_design.md`（HITL 审批）。
> 本文 §1 是本次变更记录；§2 是当前 AI 助手模块的详细架构描述；§3 是待修改清单。

## 1. 本次更新内容

### 1.1 单一入口：不再让用户逐个挑专家

落地 `/ai` 时自动开启一个「智能助手」（`agent-router`，`features.router: true`）会话，
用户直接描述需求即可；每条消息由 router LLM 从候选专家中挑选最合适的一位回答
（`chat_service.py` `_route_to_agent`，SSE `route` 事件 + 气泡路由徽标）。
专家集市（AgentHub 卡片页）降级为备选入口，仅通过侧边栏「选择专家」按钮进入。

| 文件 | 改动 |
|---|---|
| `frontend/src/components/agent-workspace/AgentWorkspace.vue` | 资产加载后无当前会话时 `ensureDefaultSession()` 自动开启 router 会话（回退链：`agent-router` → `features.router` → `is_default` → 第一个 active Agent，`:17-28`）；「新建对话」同样直接进智能助手；新增 `handleOpenHub` 打开集市 |
| `frontend/src/components/agent-workspace/AgentSidebar.vue` | 新增「选择专家」图标按钮（`AppsOutline`，emit `openHub`）；空历史文案改为"暂无会话，直接向智能助手提问吧" |
| `frontend/src/types/agent.ts` | `AgentFeatures` 补充 `router?: boolean` 开关 |

### 1.2 菜单栏默认隐藏

`AgentWorkspace.vue:12` `collapsed = ref(true)`：侧边栏默认收成 60px 窄条
（仅保留 菜单 / 新建对话 / 选择专家 三个图标），对话区占满宽度；
点菜单图标可展开查看历史会话。

### 1.3 更新后的交互流程

```
打开 /ai
  → initAssets() 加载 Agent/MCP/技能/模型/会话/Studio 会话集合
  → 无当前会话 → 自动开启「智能助手」临时会话（sess-，首发消息后回填真实 ID）
  → AgentSandbox 展示欢迎语，用户直接提问
      → 每条消息：router LLM 路由 → 专家回答 + 路由徽标
侧边栏（默认折叠 60px）
  → ☰ 展开历史会话 / ＋ 新建智能助手对话 / ▦ 选择专家（AgentHub 卡片页）
```

---

## 2. 详细架构

### 2.1 总览

```
[前端 /ai]  AgentWorkspace → agentHub store → useAgentChatStream (fetch SSE, JWT Bearer)
      │ POST /api/v1/chat/stream {agent_id, messages, session_id, ...}
      ▼
[API 层]    api/v1/chat.py  ── 有 agent_id → stream_agent_chat（Agent 调度中枢）
      │                     └─ 无 agent_id → stream_chat（直连模型，旧路径）
      ▼
[应用服务]  chat_service.stream_agent_chat
      │  assemble_context → 会话/mode 判定 → router 路由 → 工具集组装 → 引擎分流
      ▼
┌─────────────────────────────┬──────────────────────────────────┐
│ 手写 ReAct 循环（默认/Studio）│ LangGraph 引擎（features.engine） │
│ max_rounds=8，工具结果截 4000│ llm_call ⇄ tool_exec 状态图       │
└─────────────┬───────────────┴────────────────┬─────────────────┘
              ▼                                ▼
[基础设施]  MCPClient（builtin preset 进程内 / stdio·sse 外部 server）
            StudioSandboxManager（Docker 沙盒 + 审批闸）
            ProviderManager（OpenAI 兼容 SSE，httpx 直连）
      ▼
[数据]     agent_templates / chat_sessions / chat_messages / ai_provider_configs
           / skills / mcp_servers   + Redis（审批决议、任务日志）
```

### 2.2 API 层（`api/v1/chat.py`，前缀 `/api/v1/chat`）

| 端点 | 方法 | 职责 |
|---|---|---|
| `/stream` | POST | 核心 SSE 流式聊天。有 `agent_id` → `stream_agent_chat`；否则需 `model_id` → `stream_chat` 直连（chat.py:43-106） |
| `/models` | GET | 启用中模型列表（查 `ai_provider_configs`，默认模型优先） |
| `/sessions` | POST/GET | 创建会话 / 会话列表 |
| `/sessions/{id}/messages` | GET | 会话消息（service 层复核归属） |
| `/sessions/{id}/title` | PUT | 改标题 |
| `/sessions/{id}` | DELETE | 软删除（status="deleted"） |
| `/assistants`、`/skills` | GET… | 旧助手体系 / 技能列表 |

SSE 请求体 `ChatStreamRequest`（schemas/chat.py:21-44）：`messages[]`、`model_id`、`agent_id`、
`session_id`、`temperature`、`max_tokens`、`attachments[{type,url,name,mime_type}]`、
`enable_web_search`、`deep_thinking`、`mode(chat/studio)` 等。
响应为 `data: {type, content, ...metadata}` JSON 行，`done` 后断开，响应头 `X-Accel-Buffering: no`。

Agent / Studio 端点：`api/v1/agents.py`（前台列表/详情）、`api/v1/admin/agents.py`
（管理端 CRUD + toggle + set-default，内置 Agent 软删 + 默认转移）、
`api/v1/studio.py`（1001 行：会话、审批 approve/reject、权限 PATCH、沙盒 hibernate/run、
工作区文件 CRUD、产物、分享、技能沉淀、导出）。

### 2.3 应用服务层：`stream_agent_chat` 主流程（chat_service.py:567-1315）

1. **装配**：`AgentService.assemble_context(agent_id)`；请求显式 `model_id` 可覆盖 Agent
   默认模型；模型未绑定/无 API key 直接 error。
2. **会话与模式**：取/建会话并判定 `studio_mode`（已有会话以会话行 `mode` 为准）。
   Studio 会话从 `sandbox_meta` 读 `image`、`context_pack`、`permissions.mode`
   （默认 `supervised`）、`capabilities` 状态。
3. **落库**：用户消息脱敏（`core.sanitizer`，不可逆）落库 → AI 占位消息。
4. **智能路由**：`ctx.features["router"]` 为真 → `_route_to_agent`（见 §2.4），
   替换 ctx/模型/绑定能力，落库 `routed_agent` 元数据并 yield `route` 事件。
   会话落库的 agent_id 始终是路由器，每条消息重新路由。
5. **多模态附件**：`_build_multimodal_messages`（:1454-1538）——纯文本附件拼字符串
   （单文件预览截 8000 字符）；含图片走 OpenAI 多模态 list 格式；附件 URL 有 SSRF
   防护 `_is_internal_url`。
6. **工具集组装**：`WEB_SEARCH_TOOL`（开关时追加）+ `ctx.tools`；Studio 模式换工作台
   工具集（12 个 `STUDIO_TOOL_NAMES`）+ capability 元工具（`studio_capabilities_list` /
   `studio_capability_load` 渐进披露）+ 已加载 MCP 工具 + `STUDIO_SYSTEM_PROMPT_SUFFIX`
   + context_pack hint；MAS 开启时追加 `mas_plan_preview` 工具。
7. **引擎分流**（:838-855）：`features.engine=="langgraph"` 且**非 Studio** → LangGraph
   运行时（§2.5）；否则手写循环（Studio 永远走手写循环）。
8. **手写工具循环**：`max_rounds = 8`；每轮 `provider_manager.chat_stream`；无
   tool_calls → 落库 complete + usage + `done`；有 tool_calls → 逐个执行、
   `role:tool` 回灌（JSON 截 4000 字符）。超轮次落 warning 后 done。
9. **工具路由**（:960-1217）：MAS plan 工具 → adapter；capability 工具 → 更新
   `CapabilityState` 持久化到 `sandbox_meta.capabilities`（审计保留最近 100 条）；
   `update_plan` → `plan` 事件 + `sandbox_meta.plan`；`ask_user` → `ask_request` 事件、
   本轮收尾等用户下条消息；其他 Studio 工具 → **审批闸** → 沙盒执行
   （`sandbox_execute` 边跑边推 `tool_output`）；`web_search` → 占位实现（:1678-1694，
   返回模拟结果）；其余按绑定 MCP server 匹配 → `MCPClient.call_tool`。
10. **双通道拆分**：结果含 `llm_payload`/`ui_payload` 时前者给 LLM、后者给前端；
    Studio/MAS 调用累积进 `metadata.tool_invocations` 落库（供历史重建工具卡）。

**审批闸**（:1127-1185）：`supervised` 且工具 ∈ `APPROVAL_REQUIRED_TOOLS`
（`sandbox_execute`/`workspace_write`/`workspace_edit`/`artifact_register`）时：
Redis 建审批记录（`studio:approval:{id}`，TTL 1800s）→ yield `approval_request`
（含 risk_hint、timeout_seconds）→ BLPOP `studio:approval:result:{id}` 等决议
（不阻塞事件循环、跨进程安全）→ yield `approval_resolved`
（approved/rejected/edited/timeout）；`edited` 带 `modified_args` 替换参数执行；
非 approved 以 rejected 信封回灌 LLM 让其修改后重试。决议由
`POST /studio/approvals/{id}/approve|reject` 写入。

### 2.4 智能路由 `_route_to_agent`（chat_service.py:478-565）

- **候选筛选**：`list_agents(active_only=True)` 排除自身带 `features.router` 的 Agent；
  无候选或路由器无模型 → 返回 None 按原 Agent 继续。
- **Router 调用**：`ROUTER_SYSTEM_PROMPT`（:97-106）内嵌候选清单 JSON
  （agent_id/name/description/category），要求输出一行 `{"agent_id","reason"}`；
  temperature=0、max_tokens=200、不带 tools，路由输出全部消费不外发。
- **解析**：`_extract_route_json`（:109-123）容错提取所有 `{...}` 片段，取最后一个
  可解析且含 agent_id 的对象。
- **回退**：目标不在候选 → general 类候选（否则第一个）；`assemble_context` 失败再
  回退一次；**任何异常静默回落，绝不抛出**。
- **route 事件载荷**：`{agent_id, name, avatar, color, reason, session_id, message_id}`。

### 2.5 LangGraph 引擎（阶段 1 已落地）

- **状态**（`domain/execution/agent_state.py`）：`AgentState(TypedDict)` 四字段——
  `messages`（`operator.add` reducer 累加，节点只返回增量）、`rounds`、`usage`、
  `error`（非空即路由到 END）。
- **图结构**（`langgraph_runtime.py:45-72`）：
  `__start__ → llm_call ──[有 tool_calls]→ tool_exec ──[未达上限]→ llm_call`，
  出错/无工具/达上限 → END；`recursion_limit = 2*max_rounds+2`。
- **事件透出**：节点内 `emit` 实时写入 `asyncio.Queue`（保打字机实时性），后台 task
  `ainvoke` 图；异常产 error chunk 优雅结束；**不产 done**（由 ChatService 收尾）；
  图结束后暴露 `last_usage/last_messages/error`。
- **NodeDeps**（`langgraph_nodes.py:41-58`）：model_config / system_prompt /
  temperature / max_tokens / tools / deep_thinking + 三个回调（`tool_executor`
  与手写循环同路由、`channel_resolver`、`chat_stream=provider_manager.chat_stream`）。
- **接入点**（`chat_service.py:1317-1450` `_stream_agent_chat_langgraph`）：构造
  NodeDeps → `LangGraphRuntimeService(deps)`（默认 max_rounds=8）→ 消费 chunk：
  text 累积落库（推理 chunk 透传不入正文）、tool_call/tool_result 透传、结束后用
  `runtime.last_usage` 落库 + yield done。
- **关键性质**：不引入 langchain 模型封装（继续走 OpenAI 兼容 httpx）；SSE 协议与
  legacy 完全一致，前端零改动；Agent YAML 加 `features.engine: langgraph` 即切换，
  目前仅 `agent-scrna` 启用。

### 2.6 Agent 装配（`agent_service.py`）

- **`ensure_builtin_agents`**（:72-140，`list_agents` 每次调用前执行）：读
  `data/OmicHub.yaml` 的 `agents.enabled` 列表 → 逐个加载 `data/ai/{name}.yaml`；
  `prompt_ref` 经 PromptRegistry 解析为 system_prompt（失败则跳过该 Agent）。
  **幂等策略**：已存在的内置 Agent 只同步 `features`（含 `studio` 子段），**不覆盖
  管理员调整过的模型/提示词/绑定**；不存在的按 YAML 落库（`model` 名称匹配
  `ai_provider_configs.name` 出 model_id；`mcp_ids` 为空默认注入 omichub-tools
  preset UUID）。因此改 YAML 刷新页面即生效，无需重启。
- **`assemble_context`**（:335-405）：严格按 `agent.model_id` 解析模型（无 fallback）
  → 绑定 MCP server 工具转 OpenAI function schema → omichub-tools 自动注入
  （显式选中或 mcp_ids 为空时）→ 系统词 = Agent 设定 + skills prompt 后缀 +
  omichub-tools 清单 hint。

### 2.7 MCP 层（`infrastructure/mcp/`，仅 client.py + presets.py）

| Preset | 工具 | 说明 |
|---|---|---|
| `omichub-tools` | KEGG 富集、火山图、系统发育树等静态工具（`tools_schema.yaml`）+ 动态编译的 `ai.enabled` Flow 工具 + status/summary 查询 | 确定性 UUID（uuid5）；handler 统一走 `ToolBridgeService.execute` |
| `omichub-platform` | `platform_list_tasks` / `platform_get_task` / `platform_list_flows` / `platform_sandbox_execute` / `platform_read_file`（带路径越权校验） | **尚未绑定到任何 Agent YAML（待办 P0）** |

`MCPClient.call_tool` 按 transport 分流：`builtin` 进程内直调 preset handler
（按签名注入 user_id/context，零网络开销）；`stdio`/`sse` 经 MCP SDK 建会话，
**绝不传 context**，错误隔离（超时=server.timeout，失败返回 error 信封不影响主流程）。
安全：stdio 禁 shell 解释器/绝对路径/路径遍历；SSE URL 仅 http/https 且禁内网。

### 2.8 Provider 层（`infrastructure/ai_provider/openai_compatible.py`）

- `ProviderManager` 单例按 `config.id` 缓存 provider；`chat_stream(config, messages,
  system_prompt, **kwargs)` 统一入口，httpx 直连 `{base_url}/chat/completions` SSE。
- 协议细节：`stream_options.include_usage`；有 tools 时 `tool_choice=auto`；
  `deep_thinking` 注入 `enable_thinking`；`reasoning_content` → text chunk
  （`is_reasoning:True` 不入正文）；tool_calls 按 index 累积分片、流末统一产一个
  内部 `tool_calls` chunk；usage 归一化 prompt/completion/total。
- 健壮性：首次带 tools 空响应 → 不带 tools 重试一次；retryable 网络错误且未输出
  也重试一次；错误映射 401/429/404/content_filter。

### 2.9 配置加载

- **PromptRegistry**（`prompt_loader.py`）：读 `data/ai/prompts/registry.yaml`，按 mtime
  缓存热重载；`render(key, **variables)` 做 `{{var}}` 安全替换（未声明/缺变量抛错）；
  约 20 个 key（agents.*、studio.*、tools.omichub_system_hint、skills.* 等）。
- **agent_loader**：加载 `data/ai/*.yaml`，`studio.runtime_profile` 经
  runtime_image_loader 解析沙盒镜像；失败容错（缺文件/解析失败 → 跳过记日志）。

### 2.10 数据模型

| 表 | 关键字段 |
|---|---|
| `agent_templates` | `agent_id` unique、name/avatar/color/category、`model_id` FK、`system_prompt/welcome_message`、`mcp_ids/skill_ids` JSONB、`features` JSONB（router/engine/studio/web_search 开关）、temperature/max_tokens、is_builtin/is_active/is_default |
| `chat_sessions` | `session_id` unique、user_id、`agent_id` FK、title、`model_id`、message_count/total_tokens、status、`mode(chat/studio)`、`sandbox_meta` JSONB（image/permissions/capabilities/plan/context_pack）、分享三字段 |
| `chat_messages` | `message_id` unique、session_id FK CASCADE、role、content、`metadata_json` JSONB（usage/routed_agent/tool_invocations/attachments）、status(streaming/complete/error) |
| `ai_provider_configs` | name、provider_type、model、base_url、api_key、temperature/max_tokens/timeout、is_active/is_default、extra_params |
| `skills` | skill_id unique、prompt（纯注入型）、tool_definition JSON、is_active/is_builtin |
| `mcp_servers` | name unique、transport(builtin/stdio/sse)、command/args/url/env、tools JSON 缓存、status、is_preset |

### 2.11 SSE 事件协议（ChatChunk.type）

| type | 载荷 | 产生处 |
|---|---|---|
| `text` | 增量文本；`is_reasoning` 表示推理流；首个 chunk 带 session_id/message_id | provider / chat_service |
| `tool_calls` | 完整 tool_calls 列表（内部事件，chat_service 消费后不外发） | provider 流末合并 |
| `tool_call` | tool_call_id、tool_name、arguments(dict)、mcp_server | chat_service / langgraph_nodes |
| `tool_output` | tool、tool_call_id、stream(stdout/stderr)、data（仅 sandbox_execute 流式；UI 单通道上限 20000 字符） | studio_tools |
| `tool_result` | tool_call_id、success、result(llm_payload)、ui_payload | chat_service / langgraph_nodes |
| `plan` | steps（update_plan 待办，驱动右栏面板） | chat_service |
| `route` | agent_id、name、avatar、color、reason | chat_service |
| `approval_request` | approval_id、tool_call_id、arguments、risk_hint、timeout_seconds(1800) | chat_service |
| `approval_resolved` | approval_id、action(approved/rejected/edited/timeout) | chat_service |
| `ask_request` | question、options[]（用户下一条消息回答） | chat_service |
| `done` | session_id、message_id、usage、finish_reason | chat_service / provider |
| `error` | content 错误描述；瞬时网络错误带 retryable | 各处 |

### 2.12 前端架构

**路由**（`router/index.ts`）：`/ai` → `AIChatView.vue`（全屏壳子，直接渲染
AgentWorkspace，:108-113）；`/studio/:sessionId?` → `StudioView.vue`；
`/studio/shared/:token` → 免登录只读分享页。

**组件树**（`components/agent-workspace/`）：

```
AgentWorkspace（编排根：资产加载 + 默认进 router 会话 + 侧栏折叠态）
├── AgentSidebar（默认折叠 60px；会话按 今天/昨天/更早 分组；
│    Studio 会话打 📊 点击跳 /studio；emits toggleCollapse/newChat/openHub/…）
└── 主区
    ├── AgentSandbox（有会话）
    │    ├── 顶栏：返回 / Agent 信息 / 会话内模型切换 n-select（availableModels，
    │    │    仅改前端态）/「工作台模式」按钮（建 Studio 会话跳 /studio）/ 能力抽屉
    │    ├── 欢迎卡片（空会话显示，关闭状态按 agent 存 localStorage）
    │    ├── KimiMessageList（虚拟滚动；监听 confirm-tool / open-tool-page）
    │    └── KimiChatInput（slash 命令、附件上传、联网/深度思考开关）
    └── AgentHub（无会话且手动进入：4 列卡片 NGrid，AgentCard hover
         显示挂载 MCP/Skill 清单）
```

- **AgentCapabilityDrawer**：右侧抽屉展示当前 Agent 的引擎/分类/挂载 MCP
  （含在线状态与工具标签）/技能/System Prompt。
- **ShaniaChatBackground**：「傻妞」专属全息投影背景（纯 CSS 动画）。

**SSE 客户端**（`composables/useAgentChatStream.ts`）：原生 fetch POST + ReadableStream
按行解析 `data:` 前缀（非 EventSource）；`localStorage.access_token` 作 Bearer 头；
支持事件：text（is_reasoning 区分思考流、首个 text 触发 onSessionCreated）、tool_call、
tool_result（ui_payload）、tool_output、plan、approval_request/resolved、ask_request、
route、error、done；AbortController 取消；流意外中断（无 done/error）兜底 onError。

**Store**（`stores/agentHub.ts`）：临时会话 `sess-` ID + `pendingSessionIdPromise` 锁
（防回填前重复建会话）；附件在 KimiChatInput 先 `POST /files/chat-upload` 再随 SSE
payload 发送；历史消息从 `metadata_json.tool_invocations / routed_agent` 重建工具卡与
路由徽标；`workspace_write/edit` 成功时 `dispatchEvent('omichub:studio-file-changed')`
通知 Studio 编辑器。

**渲染链**（`components/ai-chat/`，/ai 与 /studio 复用）：`KimiMessageItem.vue`
（1609 行渲染中枢）——markdown-it + DOMPurify、思考折叠块、Plotly/ECharts/表格按
uiPayload 渲染、工具卡按序分流：`ApprovalCard`（有 approval 时）→ `StudioCodeCard`
（仅 /studio 注入 StudioContext 时）→ `MasPlanPreviewCard` → artifact 登记卡 → 通用
工具卡（含 confirm_card 二次确认、TaskProgressCard 异步进度）；**routed_agent 徽标**
在 assistant 头部显示专家 avatar+name（边框用专家色，title 提示路由理由）；
**ask_user 卡**点击选项即作为下一条消息发送。`ApprovalCard` 三按钮
【批准运行 / 编辑后运行（modified_args）/ 让 AI 修改（填理由）】，乐观更新 + 失败回滚。

**样式**：`styles/chat-theme.css` 定义 `--chat-*` 变量（dark/light 两套，
`<html data-theme>` 切换），暗色完整支持；强调色桥接平台 `--arco-primary*`。

**权限/模型 UI 位置**：会话内模型切换仅在 /ai 顶栏；supervised/auto 权限开关仅在
/studio 顶栏（`POST /studio/sessions/{id}/permissions`）。

### 2.13 Agent 清单（`data/ai/`，`OmicHub.yaml:84-92` 启用列表）

| Agent | ID | 引擎 | 备注 |
|---|---|---|---|
| 智能助手 | `agent-router` | legacy + router | **统一入口（本次默认）**；Studio: analysis-core（本分支补齐） |
| 通用助手 | `agent-general` | **langgraph**（本分支切换） | Studio: analysis-core |
| 代码助手 | `agent-code` | legacy | Studio: analysis-core |
| 可视化助手 | `agent-viz` | legacy | |
| RNA-seq 分析师 | `agent-rnaseq` | legacy | Studio: analysis-core |
| 单细胞分析师 | `agent-scrna` | **langgraph** | Studio: analysis-scrna，框架引擎首个试点 |
| 傻妞 | `agent-shania` | legacy | 专属背景 |
| 多智能体编排器 | `agent-orchestrator` | legacy + MAS | 仅 MAS Feature Flag 开启时启用 |

另：旧「助手」体系（`BUILTIN_ASSISTANTS` 5 个 + `chat_assistants` 表）与 Agent 模板是
两套并存体系——助手走 `stream_chat`，Agent 走 `stream_agent_chat`；新功能全部 Agent-first。

---

## 3. 待修改清单（按优先级）

> 2026-07-22 更新：P0 preset 回填、P1 router Studio、P1 LangGraph 扩展（general）、
> P2 AgentHub 分组已在分支 `feat/ai-assistant-framework` 落地（见下方"已落地"小节）。

| 优先级 | 事项 | 位置 | 说明 |
|---|---|---|---|
| ~~P0~~ | ~~空历史文案仍指向"应用集市"~~ | `AgentSidebar.vue` | ✅ 已修 |
| ~~P0~~ | ~~Agent YAML 未绑定 `omichub-platform` preset~~ | `data/ai/*.yaml` | ✅ 本分支落地（见下） |
| ~~P1~~ | ~~router 会话的 Studio 能力路径未明~~ | `data/ai/router.yaml` | ✅ 本分支补齐 analysis-core；按被路由专家动态切换镜像留作后续 |
| P1 | LangGraph 引擎扩展中 | `data/ai/*.yaml` `features.engine` | ✅ general 已切换（本分支）；router/code/rnaseq/viz/shania 观察后跟进；Studio 模式仍排除在分流之外（`chat_service.py:838`），沙盒工具循环入图未做 |
| P1 | `web_search` 是占位实现 | `chat_service.py:1678-1694` | 返回模拟结果，需选定搜索源（API key）后实施，本分支未动 |
| P2 | 旧 Copilot 双轨待删除 | `api/v1/ai.py`（`/ai/ws`）、`ai_conversations` 表、`BUILTIN_ASSISTANTS`/`chat_assistants`、前端 `ai-chat/legacy/`、`stores/chatAssistant.ts`、`stores/chatSession.ts` | review U2：删除面较大，建议单独版本排期，本分支未动 |
| ~~P2~~ | ~~AgentHub 无分类筛选~~ | `AgentHub.vue` | ✅ 本分支按 `category` 分组展示 |
| P2 | HITL × LangGraph 融合 | `langgraph_nodes.py` | 阶段 3：审批闸改 interrupt 节点、Postgres checkpointer 断线恢复 |
| P3 | 单细胞子图 | — | QC/聚类/注释拆确定性节点，模型只做参数决策与解读（review §3.4-3） |

### 3.1 本分支已落地（`feat/ai-assistant-framework`，相对 main）

| 事项 | 实现 |
|---|---|
| 存量 Agent 回填 omichub-platform | alembic 数据迁移 `a5b6c7d8e9f0`：内置 Agent 且 mcp_ids 保持默认绑定（含 omichub-tools 不含 platform）的行追加 platform preset UUID；管理员自定义过绑定的行不动。新 Agent 由 `agent_service.py:114` 默认注入两个 preset，无需处理 |
| router 会话 Studio 能力 | `data/ai/router.yaml` 增加 `studio: {enabled, runtime_profile: analysis-core, required_capabilities: [python, r, bash]}`；`ensure_builtin_agents` 对已存在内置 Agent 同步 features（含 studio 段），刷新即生效。限制：转接到 scrna 等专家后仍用 router 的镜像 |
| LangGraph 扩展 | `data/ai/general.yaml` 增加 `features.engine: langgraph`（features 幂等同步，即时生效） |
| AgentHub 分类分组 | `AgentHub.vue` 按 通用/分析/编程/可视化 分组渲染，未知分类归末尾 |

## 4. 验证

- `vue-tsc --noEmit` 类型检查通过（2026-07-22，两次）。
- 本分支验证（2026-07-22）：`scripts/check_migrations.py` 迁移链检查通过（head 唯一）；
  `pytest tests/unit/test_agent_loader_studio.py test_agent_router.py
  test_langgraph_runtime.py test_prompt_config_contract.py` 21 个用例全过；
  `vue-tsc --noEmit` 本分支改动文件无错误（`kimi-message-item.ssr.test.ts`
  有一处类型错误来自工作区他人未提交的 finishReason 改动，与本分支无关）。
- 手动验证路径：打开 `/ai` → 默认折叠窄侧栏 + 直接进入智能助手对话 →
  提问触发路由徽标 → ▦ 按钮进集市（分类分组）选指定专家；
  迁移后对话中可问"我有哪些正在跑的任务？"验证 platform 工具。
