# AI 助手模块梳理与 Agent 框架化升级设计（2026-07-21）

## 1. 现状梳理

### 1.1 后端架构（FastAPI，DDD 分层）

| 层 | 关键文件 | 职责 |
|---|---|---|
| API | `api/v1/chat.py` | 主聊天入口 `POST /chat/stream`（SSE），会话/消息 CRUD |
| API | `api/v1/agents.py`、`admin/agents.py` | Agent 模板前台读取 / 管理端 CRUD |
| API | `api/v1/ai.py` | 旧版 Copilot（WebSocket `/ai/ws`），待废弃 |
| 应用服务 | `application/services/chat_service.py`（1472 行） | `stream_chat`（直连模型）+ `stream_agent_chat`（Agent 调度中枢） |
| 应用服务 | `application/services/agent_service.py` | Agent 模板 CRUD、`ensure_builtin_agents()`（YAML 幂等落库）、`assemble_context()` |
| 基础设施 | `infrastructure/ai_provider/openai_compatible.py` | 主力 Provider：httpx 直连 OpenAI 兼容 SSE，`provider_manager` 单例 |
| 基础设施 | `infrastructure/config/prompt_loader.py` | 提示词仓库（`data/ai/prompts/registry.yaml`，mtime 热重载） |
| 基础设施 | `infrastructure/config/agent_loader.py` | `data/ai/*.yaml` 内置 Agent 声明加载 |
| 基础设施 | `infrastructure/mcp/` | MCP client + 内置 omichub-tools 预设 server |
| 数据表 | `agent_templates` / `chat_sessions` / `chat_messages` / `ai_provider_configs` / `skills` / MCP / MAS | — |

### 1.2 现有 Agent 是"提示词 + 手写循环"

- Agent = `agent_templates` 一行记录（system_prompt + tools + MCP/Skill 绑定 + features）。
- `stream_agent_chat`（`chat_service.py:439-1026`）手写 ReAct 闭环：LLM 流式调用 → 收集 `tool_calls` → 本进程执行（MCP / Studio 沙盒 / web_search / MAS 计划）→ `role: tool` 回灌，最多 8 轮。
- 无状态图、无检查点、无子图，多轮工具编排全靠一个 for 循环，扩展（人机协作、分支、恢复）都要改这个循环。

### 1.3 前端

- `/ai` → `AgentWorkspace.vue`：无会话显示 Agent 集市（`AgentHub.vue`），有会话显示 `AgentSandbox.vue`；流式用 fetch + SSE（`composables/useAgentChatStream.ts`），事件协议 `text/tool_call/tool_result/tool_output/plan/done`。
- 会话绑定 `agent_id`，切换 Agent = 开新会话；管理端在 `/admin/ai-resources` 配置模板。
- 旧 Model-first 代码（`ai-chat/legacy/`、`stores/chatAssistant.ts`、`stores/chatSession.ts`、`useChatStream.ts`）已 deprecated。

## 2. 易用性问题与优化建议

| # | 问题 | 建议 | 本次是否实施 |
|---|---|---|---|
| U1 | `stream_chat` 直连路径里"[极简测试]"把系统提示词整段注释禁用（`chat_service.py:328-347`），行为与注释不符 | 恢复正常 system_prompt 逻辑或删除死代码 | 是（删除死代码，恢复 prompt） |
| U2 | 旧 Copilot（`/ai/ws`、AIService、`ai_conversations` 表）与前端 legacy 代码双轨并存，认知负担大 | 标记废弃计划，新功能只走 Agent-first；后续版本删除 | 否（仅文档记录） |
| U3 | 切换 Agent 必须开新会话，集市卡片无分类筛选 | AgentHub 按 `category` 分组展示（analysis/通用等） | 否（前端后续迭代） |
| U4 | Agent 能力对用户不透明 | 已有 `AgentCapabilityDrawer`，保持；新 Agent 上线时在 `description`/`welcome_message` 写清输入要求 | 是（scrna 文案） |

## 3. 框架化升级设计（可实现性）

### 3.1 选型

引入 **LangGraph**（已加入 `pyproject.toml`，`langgraph>=0.2`）。落地方案以既有评估成果
`docs/Kimi_Agent_平台架构升级评估/langgraph_integration/`（2026-07-06，含 15 个参考实现文件）为准，
分期采纳：

- **本期（阶段 1）**：`AgentState` 状态定义 + `assemble/llm_call/tool_exec` 节点 + `LangGraphRuntimeService`（SSE 事件生成），接入 `stream_agent_chat`。
- **后续阶段**：PostgreSQL 检查点持久化、HITL 人工在环（param_confirm/task_submit/result_review）、`LangGraphExecutor` 注册进 flows 执行器 registry、前端 `HITLDialog`。

参考方案要点：

- 与现有 SSE 协议解耦：图节点只负责"调模型 / 执行工具"，流式事件透出为现有 `ChatChunk`，**前端零改动**。
- 不引入 langchain 模型封装：模型节点继续走 `provider_manager.chat_stream`（OpenAI 兼容 httpx），国产模型兼容性不变。
- 后续可平滑获得：checkpointer 会话恢复、interrupt 人机协作、子图（单细胞 QC→聚类→注释工作流）。

### 3.2 接入方式（最小侵入，对齐参考方案的目录分层）

- `src/omichub/domain/execution/agent_state.py`：AgentState 状态定义（参考 `langgraph_integration/backend/src/omichub/domain/execution/agent_state.py`，裁剪 HITL 字段）。
- `src/omichub/infrastructure/execution/langgraph_nodes.py`：`llm_call` / `tool_exec` 节点 + 条件边（assemble 阶段本期留在 ChatService，不进图）。
- `src/omichub/infrastructure/execution/langgraph_runtime.py`：运行时服务，驱动图执行并产出与 legacy 循环一致的 `ChatChunk` 流。
- `stream_agent_chat` 分流：`ctx.features["engine"] == "langgraph"` 且非 Studio 模式 → 走 LangGraph 运行时；其余（含 Studio 沙盒模式）保持现有手写循环，能力加载/MAS 等复杂逻辑零风险。
- Agent 声明：`data/ai/<agent>.yaml` 增加 `features: {engine: langgraph}` 即切换到框架引擎，`agent_service.ensure_builtin_agents` 已原样同步 features，无需迁移。

### 3.3 单细胞分析 Agent

- `data/ai/scrna.yaml`：`features.engine: langgraph`，保留 `studio.runtime_profile: analysis-scrna`（Studio 模式下仍用沙盒镜像跑 Scanpy）。
- `data/ai/prompts/scrna.md`：升级为结构化工作流提示词（质控 → 归一化 → HVG → PCA/聚类 → 注释 → 差异/轨迹，明确输入要求与产物规范）。
- Docker 镜像需重建以装入 langgraph（`make docker-reload` / `make docker-start` 会基于 pyproject 重新安装依赖）。

### 3.4 后续路线

1. Studio 沙盒工具循环也迁入图节点（把 `_studio_runtime` 能力加载封装为 graph middleware）。
2. 引入 checkpointer（Postgres）实现断线恢复。
3. 单细胞子图：把 QC/聚类/注释拆成确定性节点，模型只做参数决策与结果解读。
