# OmicHub AI 驱动转型 — 全面优化报告

> 日期: 2026-07-22
> 范围: 前端布局/框架 + 后端架构/服务
> 前置文档: `ai_assistant_review.md`, `mcp_ai_assistant_integration.md`, `studio_hitl_design.md`

---

## 一、现状评估

### 1.1 已实现 AI 驱动的能力

| 模块 | 状态 | 说明 |
|------|------|------|
| Agent Hub (`/ai`) | ✅ 成熟 | Agent-first 架构，SSE 流式 + tool_call 协议 |
| OmicStudio (`/studio`) | ✅ 成熟 | AI 编码工作台，Docker 沙箱 + HITL 审批 |
| MAS 多智能体编排 | ✅ 成熟 | DAG 执行引擎 + 质量门 + A2A 事件溯源 |
| MCP 工具协议 | ✅ 成熟 | 内置 + 外部 MCP Server，双通道输出 |
| LangGraph 运行时 | 🔄 初期 | 仅 scrna agent 启用，Studio 仍用旧循环 |
| 报告生成 | ✅ AI 辅助 | AI 撰写生物分析报告 |

### 1.2 仍为传统 CRUD 的模块

| 模块 | 路由 | 问题 |
|------|------|------|
| 生信工具集 | `/tools/*` (15+) | 表单提交 → 等待 → 查看结果，与 AI 割裂 |
| 分析流程 | `/flows` → `/tasks` | 手动选参数、提交、轮询状态 |
| 文件管理 | `/files` | 纯文件浏览器，无 AI 数据探索 |
| 仪表盘 | `/dashboard` | 静态统计卡片，无 AI 洞察 |
| 知识库 | `/knowledge` | 文档 CRUD，仅 `knowledge_search` 工具可被 AI 调用 |
| 下载中心 | `/downloads` | 手动触发 EBI 下载 |
| 工作流监控 | `/workflow-monitor` | 被动监控，无 AI 异常解读 |

### 1.3 核心矛盾

**平台拥有强大的 AI 执行能力（Agent + MCP + Studio + MAS），但用户交互入口仍是传统的导航栏 + 表单 + 列表。** AI 被"藏"在 `/ai` 和 `/studio` 两个独立页面里，其余 80% 的功能页面与 AI 无交互通道。

---

## 二、前端优化方案

### 2.1 布局重构：从"导航驱动"到"AI 驱动 + 导航辅助"

#### 现状问题
- 顶部导航 4 个快捷入口 + 左侧 220px 侧边栏分组导航 → 用户需要"知道功能在哪"才能使用
- AI 助手 (`/ai`) 和工作台 (`/studio`) 是全屏独立页面，与其他功能完全隔离
- 生信工具、流程提交、文件管理各自为政，AI 无法跨模块串联

#### 目标布局

```
┌─────────────────────────────────────────────────────────────────┐
│  TopBar: Logo | 全局 AI 输入框 (⌘K) | 通知 | 用户              │
├────────────┬────────────────────────────────────────────────────┤
│            │                                                    │
│  侧边栏    │            主内容区                                 │
│  (可折叠)   │                                                    │
│            │  ┌──────────────────────────────────────────────┐  │
│  • AI 首页  │  │  根据路由渲染:                                │  │
│  • 工作台   │  │  - AI Home: 对话 + 快捷卡片 + 最近任务       │  │
│  • 任务     │  │  - Studio: 三栏工作台                        │  │
│  • 数据     │  │  - 工具: 表单 (结果可"发送到 AI 解读")       │  │
│  • 工具     │  │  - 任务: 列表 (AI 状态摘要列)               │  │
│  • 报告     │  └──────────────────────────────────────────────┘  │
│  • 知识     │                                                    │
│  • 设置     │  ┌──────────────────────────────────────────────┐  │
│            │  │  底部: 全局 AI Dock (可展开的对话条)           │  │
│            │  └──────────────────────────────────────────────┘  │
└────────────┴────────────────────────────────────────────────────┘
```

#### 具体改动

| # | 改动 | 优先级 | 影响范围 |
|---|------|--------|----------|
| F1 | **全局 AI 命令面板 (⌘K)** — 顶部搜索框升级为 AI 入口，支持自然语言指令（"帮我跑 RNA-seq"、"查看任务 #42 进度"），路由到对应功能或直接由 AI 执行 | P0 | 新增组件 `GlobalCommandPalette.vue` |
| F2 | **全局 AI Dock** — 页面底部可折叠对话条（类 Intercom），任何页面都可唤起 AI 对话，上下文自动注入当前页面信息 | P1 | 新增 `AiDock.vue` + composable `useGlobalAiContext` |
| F3 | **AI 首页替代传统 Dashboard** — `/` 路由改为 AI 对话首页 + 智能卡片（最近任务状态、待审批、AI 建议），取代静态统计 | P1 | 重构 `HomeView.vue` |
| F4 | **侧边栏精简** — 移除"核心功能/系统管理/管理员"三级分组，改为扁平化: AI 首页 / 工作台 / 任务 / 数据 / 工具 / 报告 / 知识 / 设置 | P2 | 修改 `DefaultLayout.vue` |
| F5 | **工具结果 → AI 解读按钮** — 每个生信工具的结果页增加"让 AI 解读"按钮，将结果数据作为上下文发送到 AI Dock | P1 | 各工具 View 增加 action |
| F6 | **任务列表 AI 摘要列** — 任务表格增加 AI 生成的状态摘要列（"QC 通过，比对率 92%，等待下游分析"） | P2 | `TasksView.vue` + 后端 API |
| F7 | **清理 Legacy 代码** — 移除 `chatSession.ts`、`chatAssistant.ts`、`ai-chat/legacy/`、`useChatStream.ts`、`useAIWebSocket.ts` | P2 | 删除 ~8 个文件 |

### 2.2 组件架构优化

#### 现状问题
- `ai-chat/` 下 18 个文件混合了新旧两套 UI（legacy/ 子目录）
- `agent-workspace/` 和 `studio/` 各自维护消息渲染逻辑
- 工具调用卡片（`tool_call`/`tool_result`）渲染散落在 `KimiMessageList.vue` 中，无统一注册机制

#### 目标架构

```
src/components/
├── ai-core/                    # 统一 AI 交互层 (合并 ai-chat + agent-workspace)
│   ├── ChatContainer.vue       # 对话容器 (消息列表 + 输入框)
│   ├── ChatInput.vue           # 统一输入 (附件、斜杠命令、模型选择)
│   ├── MessageList.vue         # 消息渲染 (虚拟滚动)
│   ├── MessageItem.vue         # 单条消息
│   ├── ToolCallCard.vue        # 工具调用卡片 (统一注册制)
│   ├── ToolResultRenderer.vue  # 工具结果渲染 (按 tool_name 分发到注册组件)
│   ├── ApprovalCard.vue        # HITL 审批卡片
│   ├── AskCard.vue             # AI 提问卡片
│   ├── PlanCard.vue            # 执行计划卡片
│   ├── ReasoningBlock.vue      # 思维链折叠块
│   └── registry/               # 工具结果渲染器注册表
│       ├── index.ts            # registerToolRenderer(name, component)
│       ├── ChartRenderer.vue   # ECharts/Plotly 结果
│       ├── TableRenderer.vue   # 表格数据
│       ├── FileRenderer.vue    # 文件/图片
│       └── CodeRenderer.vue    # 代码执行结果
├── studio/                     # Studio 专属 (保留，但消息层复用 ai-core)
├── command-palette/            # 全局 ⌘K 命令面板
├── ai-dock/                    # 全局底部 AI Dock
└── ...                         # 其余业务组件不变
```

#### 关键设计

1. **工具结果注册制**: 后端 `ui_payload` 已包含 `render_type` 字段，前端按 `render_type` 从注册表取对应渲染组件。新增工具无需改消息列表代码。
2. **对话容器复用**: AI 首页、Studio、AI Dock 共用 `ChatContainer`，通过 props 控制功能子集（是否显示文件树、是否显示代码编辑器）。
3. **上下文注入**: `useGlobalAiContext` composable 根据当前路由自动收集上下文（当前任务 ID、当前文件路径、当前工具结果），注入到 AI 对话的 system context。

### 2.3 状态管理优化

| 现状 | 问题 | 优化 |
|------|------|------|
| `agentHub.ts` (核心) + `chat.ts` (UI 设置) + `mcp.ts` + `ai.ts` (legacy) | 4 个 AI 相关 store 职责重叠 | 合并为 `ai.ts` (会话+流式) + `aiSettings.ts` (UI 偏好)，删除 legacy |
| `chatSession.ts` / `chatAssistant.ts` 标记 deprecated 但未删除 | 死代码 | 直接删除 |
| 工具结果无全局状态 | 工具结果只在消息流中，无法跨组件引用 | 新增 `toolResultCache` (Map<callId, result>)，供"发送到 AI"功能引用 |

### 2.4 路由优化

```typescript
// 目标路由结构 (精简 + AI-first)
const routes = [
  // 公开
  { path: '/login', ... },
  { path: '/register', ... },
  { path: '/setup', ... },
  { path: '/studio/shared/:token', ... },

  // AI 核心 (默认首页)
  { path: '/', name: 'ai-home', component: AiHomeView },        // AI 对话首页
  { path: '/studio/:sessionId?', component: StudioView },       // AI 工作台

  // 数据 & 任务 (AI 可操作)
  { path: '/tasks', component: TasksView },
  { path: '/tasks/:taskId', component: TaskDetailView },
  { path: '/files', component: FilesView },
  { path: '/reports', component: ReportsView },
  { path: '/downloads', component: DownloadsView },

  // 工具 (结果可流入 AI)
  { path: '/tools', component: ToolsHubView },
  { path: '/tools/:toolId', component: DynamicToolView },       // 动态工具路由

  // 知识 & 参考
  { path: '/knowledge', component: KnowledgeView },
  { path: '/database', component: ReferenceGenomesView },

  // 系统
  { path: '/profile', ... },
  { path: '/settings', ... },
  { path: '/admin/*', ... },
]
```

**关键变化:**
- 删除 `/dashboard`（合并到 AI 首页）
- 删除 `/ai`（`/` 就是 AI）
- 删除 `/flows`（流程提交通过 AI 对话或工具页触发）
- `/tools/:toolId` 动态路由替代 15 个硬编码工具路由

---

## 三、后端优化方案

### 3.1 执行引擎统一：全面迁移 LangGraph

#### 现状问题
- `chat_service.py` 1472 行，`stream_agent_chat` (439-1026 行) 是手写 ReAct 循环
- Studio 模式走另一套 `stream_studio_chat` 逻辑
- LangGraph 运行时仅 scrna agent 启用
- 三套工具分发路径: Studio 内置工具 / MCP 工具 / 平台工具，各自独立

#### 目标: 统一 LangGraph 执行图

```
                    ┌─────────────┐
                    │  llm_call   │ ← 流式 LLM 调用
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │  route_tool │ ← 条件路由
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
       ┌──────▼───┐ ┌─────▼─────┐ ┌───▼────────┐
       │ studio   │ │ mcp_tool  │ │ platform   │
       │ _tool    │ │ _exec     │ │ _tool      │
       └──────┬───┘ └─────┬─────┘ └───┬────────┘
              │            │            │
              └────────────┼────────────┘
                           │
                    ┌──────▼──────┐
                    │  hitl_gate  │ ← interrupt (supervised 模式)
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │  llm_call   │ ← 下一轮
                    └─────────────┘
```

#### 具体改动

| # | 改动 | 优先级 | 文件 |
|---|------|--------|------|
| B1 | **所有 Agent 启用 LangGraph** — 移除 `features.engine` 条件判断，`LangGraphRuntimeService` 成为唯一执行路径 | P0 | `chat_service.py`, `langgraph_runtime.py` |
| B2 | **Studio 迁入 LangGraph** — `stream_studio_chat` 改为 Studio 专用 StateGraph（增加 `sandbox_exec` 节点、`workspace_sync` 节点） | P1 | 新增 `studio_graph.py` |
| B3 | **统一工具路由节点** — 合并 `tool_bridge_service` + `studio_tools` + `mcp_service.call_tool` 为单一 `tool_exec_node`，按 tool 来源分发 | P1 | `langgraph_nodes.py` |
| B4 | **PostgreSQL Checkpointer** — 会话状态持久化，支持断线恢复、历史回放 | P2 | 新增 `checkpointer.py` |
| B5 | **删除手写 ReAct 循环** — `chat_service.py` 瘦身到 < 300 行（仅保留会话管理 + SSE 格式化） | P1 | `chat_service.py` |

### 3.2 MCP 平台能力全面绑定

#### 现状问题（来自 `mcp_ai_assistant_integration.md` 已识别的 Gap）
- AI 助手无法: 列出所有任务/进度、提交下载、浏览用户文件、执行沙箱代码（非 Studio）、查看/解读报告
- `omichub-platform` preset 已设计但未绑定到 Agent YAML

#### 具体改动

| # | 改动 | 优先级 | 文件 |
|---|------|--------|------|
| B6 | **绑定 `omichub-platform` 到所有 Agent** — 在 `data/ai/*.yaml` 的 `mcp_servers` 字段添加 `omichub-platform` | P0 | `data/ai/*.yaml` |
| B7 | **补充平台工具** — 实现 `platform_list_tasks`, `platform_get_task`, `platform_submit_flow`, `platform_list_files`, `platform_read_file`, `platform_get_report`, `platform_submit_download` | P0 | `mcp-server/platform.py` |
| B8 | **工具结果增加 `render_type`** — 所有平台工具的 `ui_payload` 标准化为 `{render_type, data, actions}`，前端按类型渲染 | P1 | 各 tool 实现 |
| B9 | **外部 MCP Server 生产化** — `mcp-server/` 增加认证中间件、速率限制、OpenAPI 文档，支持 QoderCN CLI 远程调用 | P2 | `mcp-server/` |

### 3.3 AI 主动能力（Proactive AI）

#### 现状问题
- AI 完全被动：用户不问，AI 不动
- 任务完成/失败无 AI 解读推送
- 无跨会话记忆（每次对话从零开始）

#### 具体改动

| # | 改动 | 优先级 | 说明 |
|---|------|--------|------|
| B10 | **任务完成 → AI 解读通知** — Celery task 完成后触发 AI 生成结果摘要，推送到通知系统 + AI Dock 气泡 | P1 | `task_service.py` + `notification_service.py` |
| B11 | **会话记忆层** — 基于 Redis 的用户级短期记忆（最近 5 次对话摘要）+ PostgreSQL 长期记忆（用户偏好、常用参数） | P2 | 新增 `memory_service.py` |
| B12 | **AI 建议引擎** — 基于用户最近操作（上传了 FASTQ → 建议跑 QC；任务失败 → 建议排查步骤），在 AI 首页展示智能建议卡片 | P2 | 新增 `suggestion_service.py` |
| B13 | **工作流异常 AI 诊断** — workflow-monitor 检测到异常时，自动调用 AI 分析日志并生成诊断报告 | P3 | `workflow_monitor_service.py` |

### 3.4 API 层优化

| # | 改动 | 优先级 | 说明 |
|---|------|--------|------|
| B14 | **SSE 协议 v2** — 增加 `context_update` 事件（AI 主动更新页面状态）、`suggestion` 事件（AI 建议）、`memory_recall` 事件（AI 引用历史） | P1 | `chat_service.py` SSE 格式 |
| B15 | **统一对话 API** — 合并 `/chat/stream`、`/studio/chat`、`/ai/ws`(deprecated) 为单一 `/ai/chat` 端点，通过 `mode` 参数区分 (chat/studio/copilot) | P1 | 新增 `api/v1/ai_chat.py` |
| B16 | **工具结果 WebSocket 推送** — 长时间运行的工具（BLAST、pipeline）通过 WS 推送中间进度到 AI 对话流 | P2 | `tool_bridge_service.py` |
| B17 | **GraphQL 或 tRPC 评估** — 当前 30+ REST 端点，前端 API 层 17 个文件。评估是否引入类型安全的查询层减少胶水代码 | P3 | 架构评估 |

### 3.5 数据层优化

| # | 改动 | 优先级 | 说明 |
|---|------|--------|------|
| B18 | **向量存储** — 知识库文档 + 用户文件元数据 → embedding 向量化，支持 AI 语义检索（当前 `knowledge_search` 是关键词匹配） | P2 | 新增 `infrastructure/vector_store/` |
| B19 | **会话状态表** — 将 Redis 中的审批状态、会话上下文持久化到 PostgreSQL（Redis 仅做缓存），支持审计和恢复 | P2 | 新增 migration |
| B20 | **工具调用分析表** — 记录每次 tool_call 的输入/输出/耗时/成功率，用于优化 prompt 和工具推荐 | P3 | 新增 `tool_analytics` 表 |

---

## 四、生信工具 AI 化改造

### 4.1 现状

15+ 独立工具页面，每个都是: 表单填参 → POST 提交 → 轮询结果 → 查看图表。与 AI 系统完全隔离。

### 4.2 目标: 工具即 AI 技能

```
用户: "帮我对这个 RNA-seq 数据做差异表达分析"
  ↓
AI 识别意图 → 调用 tool_bridge → 执行 DESeq2/edgeR
  ↓
结果返回:
  - llm_payload: "找到 342 个差异基因, top5: TP53, BRCA1..."
  - ui_payload: {render_type: "volcano_plot", data: {...}}
  ↓
前端: 火山图组件渲染 + AI 文字解读
  ↓
用户: "把 |log2FC| > 2 的基因做 KEGG 富集"
  ↓
AI 自动串联上一步结果 → 调用富集工具 → 返回通路图
```

### 4.3 具体改动

| # | 改动 | 优先级 | 说明 |
|---|------|--------|------|
| T1 | **所有工具注册为 MCP 工具** — 在 `omichub-tools` preset 中补全: volcano_plot, kegg_enrichment, go_enrichment, fastq_qc, seq_manipulate, format_convert, id_convert, primer_design | P0 | `infrastructure/mcp/presets.py` |
| T2 | **工具参数 AI 推断** — AI 根据用户自然语言 + 上下文数据自动填充工具参数，用户仅需确认 | P1 | prompt engineering + `ask_user` |
| T3 | **工具链式调用** — AI 可自动串联多个工具（QC → 比对 → 定量 → 差异 → 富集），每步结果作为下步输入 | P1 | LangGraph sub-graph |
| T4 | **工具页面保留但降级** — `/tools/*` 页面保留给需要手动精确控制的用户，但默认入口变为 AI 对话 | P2 | 路由调整 |
| T5 | **结果可追溯** — 每次 AI 工具调用生成可复现的"分析步骤"记录（参数 + 版本 + 输入输出哈希） | P2 | 新增 `analysis_step` 表 |

---

## 五、实施路线图

### Phase 1: 基础打通 (1-2 周)

**目标: AI 获得平台全部操作能力，前端零改动**

- [ ] B6: 绑定 `omichub-platform` 到所有 Agent YAML
- [ ] B7: 实现 7 个平台 MCP 工具
- [ ] B1: 所有 Agent 启用 LangGraph（移除条件判断）
- [ ] T1: 生信工具注册为 MCP 工具
- [ ] F7: 清理前端 legacy 代码

**验收标准:** 用户在 `/ai` 对话中说"查看我的任务列表"、"帮我跑 fastq QC"，AI 能正确执行并返回结果。

### Phase 2: 前端 AI 化 (2-4 周)

**目标: AI 成为主要交互入口**

- [ ] F1: 全局 ⌘K 命令面板
- [ ] F2: 全局 AI Dock
- [ ] F3: AI 首页替代 Dashboard
- [ ] F5: 工具结果"让 AI 解读"按钮
- [ ] B5: 删除手写 ReAct，chat_service 瘦身
- [ ] B14: SSE 协议 v2
- [ ] B15: 统一对话 API

**验收标准:** 用户在任何页面可通过 ⌘K 或 Dock 唤起 AI，AI 能感知当前页面上下文。

### Phase 3: 深度集成 (4-6 周)

**目标: AI 主动、有记忆、可信赖**

- [ ] B2: Studio 迁入 LangGraph
- [ ] B3: 统一工具路由节点
- [ ] B10: 任务完成 AI 解读通知
- [ ] B11: 会话记忆层
- [ ] T2: 工具参数 AI 推断
- [ ] T3: 工具链式调用
- [ ] F4: 侧边栏精简
- [ ] F6: 任务 AI 摘要列

**验收标准:** AI 能自动串联"上传数据 → QC → 比对 → 差异分析 → 富集 → 报告"全流程。

### Phase 4: 智能化 (6-10 周)

**目标: 平台具备自主智能**

- [ ] B4: PostgreSQL Checkpointer（断线恢复）
- [ ] B12: AI 建议引擎
- [ ] B13: 工作流异常 AI 诊断
- [ ] B18: 向量存储（语义检索）
- [ ] B9: 外部 MCP Server 生产化
- [ ] T5: 分析步骤可追溯
- [ ] B20: 工具调用分析

**验收标准:** 平台能主动建议分析方案、诊断失败原因、记住用户偏好。

---

## 六、技术风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| LangGraph 全面迁移引入回归 | 现有 Agent 对话中断 | 逐 Agent 灰度切换，保留 fallback 开关 |
| 全局 AI Dock 性能 | 每页额外 SSE 连接 | 懒加载 + 共享连接池 + 无对话时断开 |
| 工具链式调用失控 | AI 执行非预期操作 | supervised 模式默认开启 + 链式调用需用户确认计划 |
| 记忆层隐私 | 用户数据泄露 | 记忆隔离到用户级 + 可清除 + 不跨用户 |
| 前端大幅重构 | 开发周期长、回归多 | 渐进式: 先加新组件，再迁移旧页面，最后删旧代码 |

---

## 七、成功指标

| 指标 | 当前基线 | Phase 2 目标 | Phase 4 目标 |
|------|----------|-------------|-------------|
| AI 交互占比（AI 对话次数 / 总操作次数） | ~15% | 40% | 70% |
| 工具调用 via AI（AI 触发 / 总工具使用） | ~5% | 30% | 60% |
| 平均分析流程完成时间 | 手动 30min+ | AI 辅助 15min | AI 自主 5min |
| 用户需切换页面次数（单次分析） | 6-8 次 | 3-4 次 | 1-2 次 |
| AI 首次响应准确率（工具选择正确） | N/A | 80% | 90% |

---

## 八、总结

OmicHub 已具备 AI 驱动的**执行能力**（LangGraph + MCP + Studio + MAS），但缺乏 AI 驱动的**交互范式**。核心转型不是"加更多 AI 功能"，而是**将 AI 从独立页面提升为全局交互层**：

1. **前端**: AI 从"一个页面"变为"一个层"——⌘K 命令面板 + AI Dock + 上下文注入，让 AI 触达每个功能角落
2. **后端**: 执行引擎统一（LangGraph 全面迁移）+ 平台能力全面暴露（MCP 绑定）+ 主动智能（通知/建议/记忆）
3. **工具**: 从"用户操作工具"变为"AI 操作工具、用户确认结果"

三步走: **打通能力 → 改变入口 → 建立信任**。
