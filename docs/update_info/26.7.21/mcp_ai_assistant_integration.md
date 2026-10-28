# 平台 MCP 与 AI 助手联动设计（2026-07-22）

## 1. 背景

平台已完成统一 MCP Server 建设（`mcp-server/`，28 个工具 + 4 Resources + 5 Prompts），
同时 AI 助手模块正从"手写 ReAct 循环"向 LangGraph 框架化升级（见 `ai_assistant_review.md`）。
本文档设计两者的联动方案，使 AI 助手获得完整的平台操作能力。

## 2. 现有集成点

### 2.1 AI 助手如何调用 MCP 工具

```
用户消息 → chat_service.stream_agent_chat()
  → AgentService.assemble_context() 获取 ctx.mcp_servers (绑定的 MCP 预设)
  → LLM 返回 tool_calls
  → 匹配 active_mcp_servers 中的 server
  → MCPClient.call_tool(server, tool_name, args, user_id, context)
  → 结果回灌 LLM (role: tool, 截断 4000 字符)
  → 下一轮 LLM 调用
```

### 2.2 当前 MCP 预设覆盖

| Preset | 工具 | AI 助手可用 |
|--------|------|------------|
| `omichub-tools` | KEGG 富集、火山图、Flow 提交/状态 | 是（绑定到 Agent） |
| `omichub-platform` (新增) | 任务列表/详情、流程查询、沙箱执行、文件读取 | 是（需绑定） |
| `literature` / `genome` / `code` / `knowledge` | 文献/基因/代码/知识库 | 是 |
| 独立 MCP Server (`mcp-server/`) | 完整 28 工具 | 外部 AI 助手 (QoderCN CLI) |

### 2.3 缺口

AI 助手（内部）目前**无法**：
- 主动查看所有任务及进度（仅有 `omichub_get_analysis_task_status` 单任务查询）
- 提交数据下载
- 浏览用户文件/读取分析结果
- 在沙箱中执行自定义代码（Studio 模式除外）
- 查看/解读报告

## 3. 联动架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        AI 助手 (内部)                            │
│  chat_service.stream_agent_chat() / LangGraph Runtime           │
│                                                                 │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────────────┐  │
│  │ omichub-tools│  │omichub-platform│ │ Studio 沙箱工具       │  │
│  │ (生信工具箱) │  │ (平台操作)    │  │ (sandbox_execute等)   │  │
│  └──────┬──────┘  └──────┬───────┘  └───────────┬───────────┘  │
│         │                │                       │              │
│         ▼                ▼                       ▼              │
│  ToolBridgeService   直接调用 Services    StudioSandboxManager  │
│  (MCP builtin)       (零网络开销)         (Docker 容器)         │
└─────────────────────────────────────────────────────────────────┘
                              │
                    ┌─────────┴─────────┐
                    │   平台服务层       │
                    │ TaskService        │
                    │ DownloadService    │
                    │ FlowService        │
                    │ FileService        │
                    │ ReportService      │
                    │ SandboxService     │
                    └─────────┬─────────┘
                              │
┌─────────────────────────────────────────────────────────────────┐
│                   外部 AI 助手 (QoderCN CLI)                     │
│                                                                 │
│  mcp-server/ (FastMCP, stdio/SSE)                               │
│  28 tools → httpx → 平台 REST API (X-API-Key 认证)              │
└─────────────────────────────────────────────────────────────────┘
```

## 4. 联动方案（按 AI 助手升级阶段）

### 4.1 阶段 1：Builtin Preset 绑定（本期，零前端改动）

**目标**：让现有 Agent（rnaseq、general 等）立即获得平台操作能力。

**实施**：
1. 在 `data/ai/rnaseq.yaml`、`data/ai/general.yaml` 等 Agent 声明中绑定 `omichub-platform` preset：
   ```yaml
   mcp_servers:
     - omichub-tools
     - omichub-platform   # 新增
   ```
2. `agent_service.ensure_builtin_agents()` 已支持从 YAML 同步 `mcp_servers`，无需代码改动。
3. `assemble_context()` 自动将 `omichub-platform` 的 5 个工具注入 LLM tools 列表。

**效果**：Agent 对话中可调用：
- `platform_list_tasks` — "我有哪些正在跑的任务？"
- `platform_get_task` — "这个任务跑到哪了？"
- `platform_list_flows` — "平台支持哪些分析？"
- `platform_sandbox_execute` — "帮我画个火山图"
- `platform_read_file` — "看一下差异基因结果"

### 4.2 阶段 2：LangGraph 节点化（对齐框架升级）

**目标**：MCP 工具调用成为 LangGraph 图中的标准 `tool_exec` 节点。

**设计**（对齐 `ai_assistant_review.md` 3.2 节）：

```python
# infrastructure/execution/langgraph_nodes.py

async def tool_exec_node(state: AgentState) -> AgentState:
    """工具执行节点：统一处理 MCP builtin / Studio / 外部 MCP 调用"""
    tool_calls = state.pending_tool_calls
    for tc in tool_calls:
        tool_name = tc["function"]["name"]
        args = json.loads(tc["function"]["arguments"])

        # 路由: Studio 工具 → stream_studio_tool
        #        MCP builtin → mcp_client.call_tool (omichub-platform/omichub-tools)
        #        外部 MCP → mcp_client.call_tool (stdio/sse server)
        result = await route_and_execute(tool_name, args, state)

        state.tool_results.append({
            "tool_call_id": tc["id"],
            "content": truncate(result["llm_payload"], 4000),
        })
        state.events.append(ChatChunk(type="tool_result", ...))
    return state
```

**与 MCP 的关系**：
- `omichub-platform` preset 的工具在图中作为**内置节点**执行（零网络开销）
- 外部 MCP Server 的工具通过 `MCPClient` stdio/sse 调用（进程隔离）
- 确认门工具（`omichub_submit_analysis`）触发 LangGraph `interrupt`（HITL）

### 4.3 阶段 3：HITL 审批 × MCP 确认门融合

**目标**：MCP 工具的 `user_confirmed` 确认门与 Studio 审批协议统一。

**对齐 `studio_hitl_design.md`**：

| MCP 确认门 | Studio 审批协议 | 融合方案 |
|-----------|---------------|---------|
| `user_confirmed=False` 返回预览 | `approval_request` SSE 事件 | LangGraph interrupt 节点 |
| 用户确认后重新调用 | `POST /approvals/{id}/approve` | 统一为 interrupt resume |
| 仅 analysis_flow 有确认 | supervised 模式所有写工具 | 扩展到所有 `requires_confirm` 工具 |

**实现路径**：
```python
# langgraph_nodes.py 中的条件边
def should_approve(state: AgentState) -> str:
    tool = state.pending_tool_calls[0]
    if tool_needs_confirmation(tool["function"]["name"]):
        if state.permissions_mode == "supervised":
            return "approval_gate"  # → interrupt, 等用户批准
    return "execute"
```

- `approval_gate` 节点发出 `approval_request` SSE → 前端审批卡片
- 用户批准 → resume 图执行 → 调用 MCP 工具（带 `user_confirmed=True`）
- 用户拒绝 → 结果回灌 LLM → AI 修改方案

### 4.4 阶段 4：外部 MCP Server × 平台 AI 双向感知

**目标**：外部 AI 助手（QoderCN CLI）和平台内部 AI 共享任务状态。

**场景**：
1. 用户在 QoderCN CLI 中通过 MCP Server 提交分析任务
2. 平台 AI 助手（rnaseq Agent）通过 `platform_list_tasks` 感知到新任务
3. 任务完成后，平台 AI 主动推送通知 + 结果解读
4. 用户在 CLI 中通过 `omichub_sandbox_execute` 做二次分析

**实现**：
- 任务状态变更通过 Redis PubSub 广播（已有 `task_logs:{task_id}` 通道）
- 平台 AI 的 `notification` 系统已支持任务完成通知
- 外部 MCP Server 的 `omichub_get_task_progress` 轮询即可感知进度
- 两侧通过**共享的用户数据目录**（`/data/omichub/users/{uid}/`）交换数据

## 5. Agent 声明升级示例

### rnaseq.yaml（升级后）

```yaml
id: rnaseq
name: RNA-seq 分析助手
category: analysis
system_prompt: prompts/agents/rnaseq.md
mcp_servers:
  - omichub-tools        # 生信工具箱 (KEGG, 火山图, Flow 提交)
  - omichub-platform     # 平台操作 (任务/文件/沙箱)  ← 新增
  - knowledge            # 知识库
features:
  engine: langgraph      # 使用 LangGraph 引擎
  web_search: true
tools:
  - submit_task          # 保留旧工具兼容
welcome_message: |
  我是 RNA-seq 分析助手，可以帮你：
  - 查看/提交分析任务
  - 下载公共数据库数据
  - 运行标准 RNA-seq 流程
  - 在沙箱中做自定义分析和可视化
  - 解读差异表达结果
```

### scrna.yaml（单细胞，对齐 review 3.3 节）

```yaml
id: scrna
name: 单细胞分析助手
category: analysis
system_prompt: prompts/agents/scrna.md
mcp_servers:
  - omichub-tools
  - omichub-platform     # 任务管理 + 结果读取
  - knowledge
features:
  engine: langgraph
studio:
  runtime_profile: analysis-scrna  # Studio 模式用专用镜像
```

## 6. 数据流全景

```
[外部 AI (QoderCN CLI)]
        │ stdio/SSE
        ▼
[mcp-server/ (FastMCP)]
        │ httpx + X-API-Key
        ▼
[平台 REST API] ←────────────────────────────────┐
        │                                        │
        ▼                                        │
[Application Services]                           │
  TaskService / DownloadService / SandboxService │
        │                                        │
        ▼                                        │
[Celery Workers + Docker Sandbox]                │
        │                                        │
        ▼                                        │
[用户数据目录 /data/omichub/users/{uid}/]         │
        ▲                                        │
        │ 直接读取 (零网络)                       │
        │                                        │
[omichub-platform builtin preset]                │
        ▲                                        │
        │ MCPClient.call_tool (in-process)       │
        │                                        │
[chat_service / LangGraph Runtime] ──────────────┘
        ▲
        │ SSE (ChatChunk)
        ▼
[前端 AgentWorkspace.vue]
```

## 7. 实施优先级

| 优先级 | 内容 | 工作量 | 依赖 |
|--------|------|--------|------|
| P0 | Agent YAML 绑定 `omichub-platform` | 改 2-3 个 YAML 文件 | 无 |
| P1 | `omichub-platform` 补充 download/report 工具 | 扩展 presets.py | 无 |
| P2 | LangGraph `tool_exec` 节点统一 MCP 路由 | 新增 langgraph_nodes.py | LangGraph 基础框架 |
| P3 | HITL interrupt × MCP 确认门融合 | 条件边 + approval 节点 | Studio 审批协议 |
| P4 | 外部 MCP 任务变更通知 → 平台 AI 感知 | Redis 事件 + notification | 无 |

## 8. 与现有设计的兼容性

| 现有设计 | 兼容情况 | 说明 |
|---------|---------|------|
| SSE 事件协议 (ChatChunk) | 完全兼容 | MCP 工具结果仍走 `tool_result` 事件 |
| 双通道输出 (llm_payload/ui_payload) | 完全兼容 | builtin preset 已遵循此约定 |
| Studio 能力懒加载 | 兼容 | `omichub-platform` 可作为 capability 按需加载 |
| 前端零改动原则 | 保持 | 新工具通过现有 `tool_call/tool_result` 事件透出 |
| LangGraph 分流 (features.engine) | 对齐 | MCP 调用封装在 tool_exec 节点内 |
| 审批协议 (supervised/auto) | 对齐 | MCP 确认门映射为 interrupt 节点 |

## 9. 总结

平台 MCP 与 AI 助手的联动核心是**两条路径、一个协议**：

- **内部路径**：`omichub-platform` builtin preset → 直接调用 Services（零开销）
- **外部路径**：独立 MCP Server → REST API（进程隔离，可远程）
- **统一协议**：双通道输出 + 确认门 + SSE 事件（前端零改动）

阶段 1 只需修改 Agent YAML 绑定即可让 AI 助手获得完整平台操作能力，
后续随 LangGraph 升级逐步实现节点化、HITL 融合和双向感知。
