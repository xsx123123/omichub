# MCP 架构 × AI 助手融合方案 与 Agent 扩展手册（2026-07-21）

> 关联文档：`docs/26.7.21/ai_assistant_review.md`（LangGraph 引擎）、
> `docs/26.7.21/studio_hitl_design.md`（Studio HITL 审批）、`mcp-server/ARCHITECTURE.md`（外部 MCP 服务）。

## 1. 两个 MCP 平面的定位

```
┌────────────────────────────────────────────────────────────┐
│  平面 A：平台内部 AI（/ai 助手 + /studio 工作台）            │
│    Agent → ChatService/LangGraph 引擎 → MCPClient           │
│      → omichub-tools builtin preset（进程内，零网络开销）    │
│        presets.py → tool_bridge_service → application 服务   │
│      → 其他已注册 MCP server（admin UI 管理，stdio/sse）     │
│    强制管控：StudioApprovalService 审批闸 + ask_user + 权限模式│
├────────────────────────────────────────────────────────────┤
│  平面 B：外部 MCP 客户端（Claude Desktop 等第三方）           │
│    mcp-server/（FastMCP 独立进程）                           │
│      → 平台 REST API（X-API-Key 认证，api_key_service）      │
│    管控：user_confirmed 参数约定（模型层软约束）+ API 权限    │
└────────────────────────────────────────────────────────────┘
```

两个平面**能力同源**：都收敛到平台 application services / REST API。
mcp-server 是"对外门面"，内部 preset 是"对内直连"，新增能力时双侧同步（见 §4）。

## 2. 融合策略

### 2.1 确认门统一（关键）

| 层 | 机制 | 强度 |
|---|---|---|
| 平面 A（Studio） | `StudioApprovalService`：审批卡片 + Redis 决议 + 后端挂起等待 | **强制**（后端闸） |
| 平面 A（chat 模式 analysis_flow） | `tool_confirmation_service` 两段式 prepare/confirm | 强制 |
| 平面 B（外部 MCP） | `user_confirmed: bool` 参数约定 | 软约束（靠模型自觉） |

策略：

- **保持平面 B 的 `user_confirmed` 约定不变**——外部 MCP 协议没有交互通道，无法做强审批，软约定 + API Key 权限收敛是正确边界。
- **平面 A 的审批闸不依赖工具自觉**：目前闸的是 4 个 Studio 内置工具
  （`APPROVAL_REQUIRED_TOOLS`）。后续要把闸扩展到 MCP 工具时，在 MCP server 注册
  （admin UI / mcp-server 的 tools.yaml）增加 `requires_confirmation: true` 元数据，
  chat 循环按工具元数据走同一个 `StudioApprovalService`（P2 工作，事件协议已就绪）。
- **Studio 内置工具（sandbox_execute/ask_user 等）永不暴露给平面 B**——它们依赖
  SSE 交互通道（审批卡片/问题卡片），外部客户端无法承载。

### 2.2 LangGraph 引擎与 MCP 的关系

`LangGraphRuntimeService` 的 tool_executor 与 legacy 循环共用同一路由：
MCP server 匹配 → `MCPClient.call_tool`。**Agent 绑定任何 MCP server（内置 preset
或外部注册的 stdio/sse server）后，LangGraph 引擎零改动可用**。
平面 B 的 mcp-server 如果注册为平台的 SSE MCP server，也可以被平台 Agent 复用
（一般不推荐——内部走 preset 直连更高效；该路径主要给第三方客户端用）。

### 2.3 新增能力的同步点（写代码时）

| 改动 | 平面 A | 平面 B |
|---|---|---|
| 新平台能力 | REST API + application service | 复用同一 REST API |
| 内部工具 | `presets.py` 的 `PLATFORM_PRESET_TOOLS` + `PLATFORM_HANDLERS` | — |
| 外部工具组 | — | `mcp-server/tools/<group>.py` + `tools/__init__.py` 注册 + config.yaml/tools.yaml 声明 |

## 3. 新增 Agent：纯配置即可，自动加载（无需改代码、无需重启）

**机制**：`AgentService.list_agents()` 每次调用都会先跑 `ensure_builtin_agents()`
（`agent_service.py:72`），把 `data/OmicHub.yaml` 的 `agents.enabled` 列表对应的
`data/ai/<name>.yaml` 幂等落库。前端 Agent 集市每次加载都会触发，
所以**改完配置刷新页面即生效**；提示词由 PromptRegistry 按 mtime 热重载。

### 四步新增一个 Agent（以"ATAC 分析师"为例）

```bash
# 1. Agent 声明：data/ai/atac.yaml
cat > data/ai/atac.yaml <<'EOF'
agent_id: agent-atac
name: ATAC 分析师
description: 染色质可及性分析：质控、peak calling、motif 与差异可及性。
avatar: "🧬"
color: "#9b59b6"
category: analysis
model: qwen3.7-max
prompt_ref: agents.atac          # 对应 registry.yaml 的 key
welcome_message: "你好！请提供 ATAC-seq 数据或分析目标。"
temperature: 0.3
max_tokens: 4096
mcp_ids: []                       # 空 = 默认挂 omichub-tools 内置 preset
skill_ids: []
features:
  engine: langgraph               # 可选：走 LangGraph 引擎（默认 legacy）
studio:
  enabled: true
  runtime_profile: analysis-core  # 对应 data/ai/runtime_images.yaml 的 profile
  required_capabilities: [python]
EOF

# 2. 提示词：data/ai/prompts/atac.md（自由编写）

# 3. 注册提示词 key：data/ai/prompts/registry.yaml 增加
#   agents.atac:
#     file: agents/atac.md
#     kind: system
#     owners: [agent, studio]

# 4. 启用：data/OmicHub.yaml 的 agents.enabled 列表加一行 `- atac`
```

刷新前端 → Agent 集市出现新卡片，点开即用；进 Studio 用对应运行时镜像。

### 字段速查（data/ai/*.yaml）

| 字段 | 说明 |
|---|---|
| `prompt_ref` | registry.yaml 中的提示词 key |
| `mcp_ids` | 绑定的 MCP server UUID（admin UI 可查）；空 = 默认 omichub-tools |
| `skill_ids` | 绑定技能（注入提示词后缀） |
| `features.engine` | `langgraph` 启用框架引擎；缺省走 legacy 循环 |
| `features.enable_web_search` / `mas_orchestrator` | 功能开关（见 agent_service 注释） |
| `studio.runtime_profile` | `data/ai/runtime_images.yaml` 的 profile（决定沙盒镜像与能力） |

### 什么时候才需要写代码

- **新工具能力**（如调用一个新的数据库/算法）：按 §2.3 加内部 preset handler
  （+ 可选的外部 MCP 工具组），然后 Agent yaml 的 `mcp_ids` 挂上即可。
- **新沙盒运行时**（如新依赖环境）：`deploy/runtime-images/` 加 Dockerfile +
  `data/ai/runtime_images.yaml` 加 profile。
- **新交互类型**：才需要动 chat_service / 前端（极少）。
