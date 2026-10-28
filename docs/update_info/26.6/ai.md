# OmicHub AI 助手架构文档

> 本文档汇总当前 AI 助手的完整实现，供后续架构优化参考。
> 最后更新：2026-07-04

---

## 1. 架构总览

系统经历两代架构演进：

| 代际 | 名称 | 通信协议 | 核心 Provider | 状态 |
|------|------|----------|---------------|------|
| Legacy | AI Copilot | WebSocket | `LiteLLMProvider` / `KimiProvider` | 保留但非主力 |
| Current | Agent-first | SSE (Server-Sent Events) | `OpenAICompatibleProvider` + Agent 调度 + MCP 工具调用 | **生产主力** |

整体分层：

```
┌─────────────────────────────────────────────────┐
│  Frontend (Vue 3 + Pinia + Composables)         │
│  AgentWorkspace → AgentHub / AgentSandbox       │
│  SSE via fetch + ReadableStream                 │
├─────────────────────────────────────────────────┤
│  API Layer (FastAPI routers)                    │
│  /api/v1/chat/stream  (SSE)                     │
│  /api/v1/ai/ws        (WebSocket, legacy)       │
│  /api/v1/agents, /api/v1/admin/ai-providers ... │
├─────────────────────────────────────────────────┤
│  Application Layer                              │
│  ChatService · AgentService · AIProviderService  │
├─────────────────────────────────────────────────┤
│  Domain Layer (DDD)                             │
│  Conversation · Message · AIProviderConfig       │
│  ContextWindow · AIDomainService                │
├─────────────────────────────────────────────────┤
│  Infrastructure Layer                           │
│  OpenAICompatibleProvider · LiteLLMProvider      │
│  MCPClient · SQLAlchemy Repositories            │
└─────────────────────────────────────────────────┘
```

---

## 2. 后端文件清单

### 2.1 Domain 层

| 文件 | 职责 |
|------|------|
| `domain/ai/entities.py` | `Message`（role/content/tool_calls）、`ContextWindow`（max_tokens + truncate）、`Conversation`（聚合根） |
| `domain/ai/services.py` | `AIDomainService` — 会话生命周期：创建、追加消息、构建上下文、压缩历史 |
| `domain/ai/repositories.py` | `IConversationRepository` 接口 |
| `domain/ai/value_objects.py` | 枚举：`RoleType`、`ToolCallStatus`、`ToolName`（SUBMIT_TASK / QUERY_STATUS / LIST_SAMPLES） |
| `domain/ai_provider/entities.py` | `AIProviderConfig` 实体（name/model/base_url/api_key/temperature/max_tokens 等） |
| `domain/ai_provider/services.py` | Provider 配置域服务（校验、设默认） |
| `domain/ai_provider/repositories.py` | `IAIProviderConfigRepository` 接口 |
| `domain/ai_provider/value_objects.py` | `ProviderType` 枚举（OPENAI_COMPATIBLE / KIMI / DEEPSEEK / OPENAI / ANTHROPIC / AZURE / OLLAMA / VLLM） |

### 2.2 Application 层

**Schemas（DTO）：**

| 文件 | 内容 |
|------|------|
| `application/schemas/ai.py` | Legacy：`MessageDTO`、`ConversationDTO`、`SendChatDTO`、`ToolCallResultDTO` |
| `application/schemas/chat.py` | Cherry Studio：`ChatStreamRequest`（messages/model_id/agent_id/session_id/temperature/stream 等）、`ChatSessionDTO`、`ChatAssistantDTO` |
| `application/schemas/ai_provider.py` | Provider CRUD DTO，含 API Key 脱敏逻辑 |
| `application/schemas/agent.py` | Agent 模板 DTO：agent_id/name/system_prompt/mcp_ids/skill_ids |

**Services：**

| 文件 | 职责 |
|------|------|
| `application/services/chat_service.py` | **主力服务** — `stream_chat()`（模型直连 SSE）、`stream_agent_chat()`（Agent 调度 + MCP 工具循环，最多 8 轮） |
| `application/services/agent_service.py` | Agent 模板 CRUD + `assemble_context()`（解析模型、收集 MCP 工具、拼装 system prompt） |
| `application/services/ai_service.py` | **Legacy** — WebSocket 编排：构建 system prompt → LLM 流式调用 → 工具提取 → 二次 LLM |
| `application/services/ai_tools.py` | Legacy 工具执行：submit_task / query_status / list_samples |
| `application/services/ai_provider_service.py` | Provider 配置 CRUD、测试连通性、设默认 |
| `application/services/ai_provider_yaml_loader.py` | YAML → DB 同步，支持 `${ENV_VAR}` 插值 |

### 2.3 Infrastructure 层

**LLM Provider 适配器：**

| 文件 | 说明 |
|------|------|
| `infrastructure/ai_provider/openai_compatible.py` | **主力 Provider** — httpx SSE 流式，OpenAI function calling 格式，支持 DeepSeek reasoning_content，`ProviderManager` 单例缓存 |
| `infrastructure/ai_provider/litellm_provider.py` | LiteLLM 库，支持 100+ 供应商，含 `stream_chat_with_tools()` |
| `infrastructure/ai_provider/kimi.py` | Moonshot/Kimi 直连，工具调用降级为非流式 |
| `infrastructure/ai_provider/base.py` | `StreamEvent` 数据类、`LLMProvider` Protocol 接口 |
| `infrastructure/ai_provider/__init__.py` | `get_llm_provider()` 工厂（lru_cache） |

**MCP 客户端：**

| 文件 | 说明 |
|------|------|
| `infrastructure/mcp/client.py` | `MCPClient` — 支持 builtin / stdio / sse 三种 transport，Agent 工具循环中调用 |

**数据库模型（SQLAlchemy）：**

| 文件 | 表 | 关键字段 |
|------|---|---------|
| `infrastructure/database/models/ai.py` | `ai_conversations` | user_id, title, model, assistant_id |
| | `ai_messages` | conversation_id, role, content, tool_calls(JSON), tool_call_id |
| `infrastructure/database/models/chat.py` | `chat_sessions` | session_id, user_id, assistant_id(FK), agent_id(FK), model_id(FK), message_count, total_tokens, status |
| | `chat_messages` | session_id, role, content, content_type, metadata_json(JSONB), status(streaming/complete/error) |
| | `chat_assistants` | assistant_id, name, system_prompt, default_model_id(FK), icon, category, is_builtin |
| `infrastructure/database/models/ai_provider.py` | `ai_provider_configs` | name, provider_type, model, base_url, api_key(**加密存储**), is_default |

**Repositories：**

| 文件 | 说明 |
|------|------|
| `infrastructure/database/repositories/ai_repository.py` | 会话 + 消息 CRUD，ON CONFLICT DO UPDATE |
| `infrastructure/database/repositories/ai_provider_repository.py` | Provider CRUD，API Key Fernet 加密存取 |

### 2.4 API 路由

| 前缀 | 文件 | 关键端点 |
|------|------|---------|
| `/api/v1/chat` | `api/v1/chat.py` | `POST /stream`（SSE，有 agent_id → Agent 模式，否则模型直连）、`GET /models`、Session/Assistant CRUD |
| `/api/v1/ai` | `api/v1/ai.py` | `WebSocket /ws`（Legacy，JWT query param 鉴权）、Conversation CRUD |
| `/api/v1/agents` | `api/v1/agents.py` | `GET /`（Agent 市场列表）、`GET /{id}`（详情） |
| `/api/v1/llm` | `api/v1/llm.py` | `POST /generate-welcome`（管理员，预生成欢迎语） |
| `/api/v1/admin/ai-providers` | `api/v1/admin/ai_providers.py` | Provider 配置管理 CRUD + 测试 + 设默认 |
| `/api/v1/admin/assistants` | `api/v1/admin/assistants.py` | Assistant 管理 CRUD |
| `/api/v1/admin/agents` | `api/v1/admin/agents.py` | Agent 模板管理 CRUD |

---

## 3. 前端文件清单

### 3.1 视图

| 文件 | 说明 |
|------|------|
| `views/AIChatView.vue` | AI 页面入口，渲染 `<AgentWorkspace />` |
| `views/AdminAIProvidersView.vue` | Provider 管理后台（NaiveUI DataTable） |
| `views/AdminAIResourceCenterView.vue` | 资源中心 Tab：MCP 服务 / Skills / Agents |

### 3.2 Agent Workspace 组件

| 文件 | 说明 |
|------|------|
| `components/agent-workspace/AgentWorkspace.vue` | 顶层布局：Sidebar + 主区域（Hub 或 Sandbox） |
| `components/agent-workspace/AgentHub.vue` | Agent 市场网格 |
| `components/agent-workspace/AgentSandbox.vue` | 活跃会话沙箱：Header + MessageList + ChatInput + CapabilityDrawer |
| `components/agent-workspace/AgentSidebar.vue` | 会话历史侧边栏（今天/昨天/更早分组） |
| `components/agent-workspace/AgentCard.vue` | 单张 Agent 卡片 |
| `components/agent-workspace/AgentCapabilityDrawer.vue` | Agent 能力抽屉（MCP 工具 + Skills） |

### 3.3 Chat UI 组件

| 文件 | 说明 |
|------|------|
| `components/ai-chat/KimiChatInput.vue` | 输入框：textarea + slash commands + 文件上传 + web search 触发 |
| `components/ai-chat/KimiMessageList.vue` | 虚拟滚动消息列表，流式渲染，自动滚底 |
| `components/ai-chat/KimiMessageItem.vue` | 消息气泡（user/assistant），工具调用展示，Markdown 渲染 |
| `components/ai-chat/types.ts` | 前端类型：`ChatMessage`（含 toolCalls/charts/attachments/feedback）、`ToolCall`、`ChatSession` |
| `components/ai-chat/SlashCommandMenu.vue` | Slash 命令弹出菜单 |
| `components/ai-chat/PromptSidebar.vue` | Prompt 模板侧边栏 |
| `components/ai-chat/bioPrompts.ts` | 生物信息学 Prompt 模板 |
| `components/ai-chat/modelCapabilities.ts` | 模型能力定义 |

### 3.4 Pinia Stores

| 文件 | 说明 | 状态 |
|------|------|------|
| `stores/agentHub.ts` | **主力** — Agent/MCP/Skills 资产、客户端 Session、SSE 流式（via `useAgentChatStream`）。`sendMessage()` 编排完整流程 | Active |
| `stores/chat.ts` | UI/设置 Store — 模型选择、深度思考开关、temperature/maxTokens、收藏模型、LocalStorage 持久化 | Active |
| `stores/chatSession.ts` | Cherry Studio Session Store — SSE 流式（via `useChatStream`），Session CRUD | Deprecated |
| `stores/chatAssistant.ts` | Assistant Store — 分组列表、选择 | Deprecated |
| `stores/ai.ts` | Legacy AI Copilot Store — WebSocket 流式 | Legacy |

### 3.5 Composables

| 文件 | 说明 |
|------|------|
| `composables/useAgentChatStream.ts` | **主力** — POST `/api/v1/chat/stream`（含 agent_id），fetch + ReadableStream 解析 SSE，支持 AbortController |
| `composables/useChatStream.ts` | 模型直连 SSE composable（含 model_id） |
| `composables/useAIWebSocket.ts` | Legacy WebSocket composable，指数退避重连 |

### 3.6 API 客户端 & 类型

| 文件 | 说明 |
|------|------|
| `api/agent.ts` | Agent API：`agentApi.list/get`、`adminAgentApi` CRUD |
| `types/agent.ts` | `McpService`、`McpTool`、`SkillItem`、`AgentTemplate` |
| `types/chat.ts` | `ChatSessionDTO`、`ChatMessageDTO`、`ChatAssistantDTO`、`DisplayMessage` |
| `types/index.ts` | `Conversation`、`AIMessage`、`AIEvent`（WebSocket 事件联合类型）、`AIProviderConfig` |

---

## 4. 数据流（Agent 模式，当前主力路径）

```
用户在 KimiChatInput 输入消息
    │
    ▼
AgentSandbox → store.sendMessage(content)
    │
    ▼
agentHub store (stores/agentHub.ts):
  1. 追加用户消息到 session
  2. 创建 AI 占位消息
  3. 截取最近 N 条上下文
  4. 调用 useAgentChatStream().streamChat({agentId, messages, sessionId})
    │
    ▼
POST /api/v1/chat/stream (SSE, fetch + ReadableStream)
    │
    ▼
chat.py → ChatService.stream_agent_chat()
  1. AgentService.assemble_context(agent_id)
     ├─ 解析模型配置 (agent.model_id → ai_provider_configs)
     ├─ 收集 MCP 服务 & 工具 (OpenAI function calling 格式)
     └─ 拼装 system prompt (agent prompt + skill prompts)
  2. 敏感词脱敏 (sanitizer)
  3. 创建/获取 chat_session，持久化用户消息
  4. 创建 AI 占位消息 (status="streaming")
  5. 工具调用循环 (最多 8 轮):
     a. provider_manager.chat_stream(config, messages, system_prompt, tools)
        → OpenAICompatibleProvider: HTTP POST {base_url}/chat/completions (stream=true)
        → 解析 SSE "data: {...}" 块
        → 文本 token → ChatChunk(type="text")
        → tool_calls 按 index 累积 → ChatChunk(type="tool_calls")
     b. 若有 tool_calls:
        → 追加 assistant tool_calls 到 llm_messages
        → 逐个 tool_call: 匹配 MCP server → MCPClient.call_tool()
        → 追加 tool result 到 llm_messages
        → yield tool_call / tool_result 事件
        → 回到 (a) 继续下一轮
     c. 若无 tool_calls: 标记消息 "complete"，yield done
  6. 文本内容每 5 chunk 增量写入 DB
    │
    ▼
前端接收 SSE 事件:
  text       → 更新 streamingContent，实时渲染
  tool_call  → 添加到 aiMsg.toolCalls（显示执行中）
  tool_result→ 更新工具状态（成功/失败）
  done       → 最终化消息，释放 session lock
```

---

## 5. 配置体系

### 5.1 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `LLM_PROVIDER` | `"kimi"` | Provider 选择回退 |
| `KIMI_API_KEY` / `KIMI_BASE_URL` / `KIMI_MODEL` | Moonshot 默认 | Kimi 配置 |
| `OPENAI_API_KEY` / `OPENAI_BASE_URL` / `OPENAI_MODEL` | OpenAI 默认 | OpenAI 配置 |
| `AI_SYSTEM_PROMPT` | 多组学分析助手 prompt | 基础 system prompt |
| `AI_MAX_CONTEXT_MESSAGES` | `20` | 上下文压缩阈值 |
| `AI_TEMPERATURE` | `0.7` | 默认温度 |
| `AI_DEFAULT_PROVIDER_ID` | `""` | DB 中默认 Provider UUID |
| `AI_PROVIDER_KEY_ENCRYPTION_KEY` | `""` | Fernet 密钥，API Key 加密存储 |
| `AI_PROVIDER_CONFIG_YAML` | `"data/ai/providers.yaml"` | 外部 YAML 配置路径 |
| `SENSITIVE_KEYWORDS` | `[]` | 敏感词列表，发送给 LLM 前脱敏 |

### 5.2 YAML 配置

| 文件 | 说明 |
|------|------|
| `data/ai/providers.yaml` | Provider 定义，支持 `${ENV_VAR}` 插值 |
| `data/ai/general.yaml` | 通用助手 Agent |
| `data/ai/rnaseq.yaml` | RNA-seq 分析 Agent |
| `data/ai/viz.yaml` | 可视化 Agent |
| `data/ai/code.yaml` | 代码助手 Agent |

### 5.3 Provider 选择优先级

```
1. AI_DEFAULT_PROVIDER_ID 已设 → DB 配置 via LiteLLMProvider
2. DB 有活跃 Provider 且含 API Key → provider_manager via OpenAICompatibleProvider
3. LLM_PROVIDER=openai → KimiProvider + OpenAI 环境变量
4. 回退 → LiteLLMProvider + Kimi 环境变量
```

---

## 6. 安全机制

| 机制 | 实现 | 文件 |
|------|------|------|
| API Key 加密存储 | Fernet 对称加密，DB 中密文存储 | `core/security.py` |
| API Key 接口脱敏 | GET 返回 `"********"`，PUT 忽略哨兵值 | `ai_provider_repository.py` |
| 敏感词脱敏 | 关键字不区分大小写替换为 `[REDACTED]`，不可逆 | `core/sanitizer.py` |
| WebSocket 鉴权 | Query param JWT 验证 | `api/v1/ai.py` |
| SSE 鉴权 | 复用 FastAPI Bearer token 依赖 | `api/deps.py` |

---

## 7. 数据库 ER 关系

```
ai_provider_configs (1) ──────< chat_sessions
       │                            │
       │                            ├──< chat_messages
       │                            │
       ├──────< chat_assistants     │
       │                            │
       └──────< agent_templates ────┘
                      │
                      └── mcp_ids (JSON array)
                      └── skill_ids (JSON array)

ai_conversations (Legacy) ──< ai_messages (Legacy)
```

---

## 8. 扩展点分析（面向后续优化）

以下是当前架构中预留的扩展点和待优化方向：

### 8.1 深度思考 (Deep Thinking / Reasoning)
- **已有基础**：`OpenAICompatibleProvider` 已支持 DeepSeek `reasoning_content` 字段的独立解析；前端 `stores/chat.ts` 已有深度思考开关
- **待完善**：reasoning 内容的前端渲染（折叠面板/思考过程展示）、更多推理模型适配（如 o1/o3 的 reasoning tokens）

### 8.2 联网搜索 (Web Search)
- **已有基础**：`KimiChatInput` 已预留 web search 触发 UI；MCP 架构天然支持将搜索作为 MCP Server 接入
- **待完善**：搜索结果的流式展示、引用来源标注、搜索结果缓存策略

### 8.3 MCP 工具调用
- **已有基础**：`MCPClient` 支持 builtin/stdio/sse 三种 transport；Agent 调度循环已实现最多 8 轮工具调用；`AgentCapabilityDrawer` 已展示工具列表
- **待完善**：工具执行进度的细粒度反馈、工具结果的结构化渲染（表格/图表）、工具权限控制

### 8.4 其他架构优化方向
- **Legacy 清理**：`stores/chatSession.ts`、`stores/chatAssistant.ts`、`stores/ai.ts` 已 Deprecated，可移除
- **Provider 统一**：3 套 Provider 实现可收敛为 `OpenAICompatibleProvider` 一套（已覆盖绝大多数场景）
- **消息存储**：`chat_messages` 的 `metadata_json(JSONB)` 已预留多模态内容（图片/文件/图表）的存储能力
- **上下文管理**：`ContextWindow.truncate()` 目前为简单截断，可升级为摘要压缩或 token 级管理

---

## 9. 统计概览

| 维度 | 数量 |
|------|------|
| 后端 AI 文件 | ~30 个 Python 文件（4 层 DDD） |
| 前端 AI 文件 | ~25 个 TS/Vue 文件（5 stores + 3 composables + 3 views + 12+ 组件） |
| 数据库表 | 6 张（2 Legacy + 4 Current） |
| API 路由组 | 7 组（chat / ai / agents / llm / admin × 3） |
| LLM Provider 实现 | 3 套（OpenAICompatible / LiteLLM / Kimi），类型枚举覆盖 8 类 |
| 通信协议 | SSE（主力）+ WebSocket（Legacy） |
| 工具调用 | OpenAI function calling + 文本 tool code block 回退 + MCP 工具执行 |
