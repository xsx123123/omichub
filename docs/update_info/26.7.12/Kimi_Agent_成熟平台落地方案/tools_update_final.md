# OmicHub AI 助手与工具联动架构设计（增强版）

> 目标：让 AI 助手能够发现当前可用的生信工具，并在对话中直接调用这些工具产出结果。
> 本文档基于 2026-07-12 的代码现状，结合可行性评审结论与业界深度调研结果，给出可落地的架构与分阶段实现建议。
> 输出日期：2026-07-12 | 修订：2026-07-12（整合调研后深度增强）
> **变更标记**：新增/修改内容以 `> **更新**` 标注

---

## 〇、可行性结论（摘要）

| 维度 | 评分 | 说明 |
|------|------|------|
| 现状分析 | 9/10 | Agent/MCP/工具箱路径与职责判断准确 |
| 架构设计 | 8/10 | Schema + Bridge 正确；大结果回灌与异步策略需约束 |
| 与代码契合 | 9/10 | 可插在现有 `stream_agent_chat` / builtin MCP 上 |
| 工期估计 | 7/10 | Phase 1 合理；全覆盖偏紧 |
| 安全设计 | 8/10 | 与现有 user 隔离一致；需补配额与确认 |

**总体：可行，且与现有代码契合度高（约 8/10）。**

最大坑不是「能不能调工具」，而是：

1. **大结果回灌**：`chat_service.py` 把 `tool_result` 截断到 **4000 字符**，Plotly figure 会碎。
2. **前后端双实现**：`volcanoProcessor.ts` 等纯前端逻辑重，后端 shim 易漂移。
3. **长任务占 SSE**：异步工具若在 Bridge 内同步轮询，会拖死流式连接、占 worker。

**推荐主线**：builtin MCP `omichub-tools` + ToolBridge（进程内调 service）+ **摘要回灌 / 完整结果走前端 metadata**；落地顺序 **先 KEGG → 再轻量绘图 shim → 异步只 submit**。

---

## 〇+一、业界调研关键发现摘要

> **更新**：本节汇总 4 份调研报告的核心结论。

### 1. 生信平台工具集成模式 [调研A]

| 平台 | 核心发现 | 对 OmicHub 的启示 |
|------|---------|------------------|
| **Galaxy** | XML Schema + Tool Shed 注册 + Job Runner 插件化调度 | YAML/JSON 替代 XML；schema 与执行逻辑解耦 [调研A] |
| **Terra** | Dockstore (GA4GH TRS) + WDL + Cromwell 异步执行 | MCP Server 作为 AI 接口层比传统 API 更 AI-native [调研A] |
| **Seqera** | Co-Scientist AI CLI 支持自然语言构建/调试 Nextflow 管道 | 上下文感知 AI 助手是生信平台的差异化方向 [调研A] |

**关键结论**：所有主流平台均采用「异步提交 + 状态追踪」模式执行重计算任务；MCP 已成为生信平台 AI 集成的首选协议。

### 2. AI Agent 工具调用架构 [调研B]

- **MCP 2025-06-18 版本**引入 Tool Annotations（`readOnlyHint`/`destructiveHint`/`openWorld`）、结构化输出、Progress 通知与 Cancellation 支持 [调研B]
- **Anthropic Tool Use** 的 `is_error` 语义错误标记和两阶段工具路由适合 OmicHub 大量生信工具场景 [调研B]
- **OpenAI Responses API** 支持 MCP 远程接入，`strict` 模式减少参数幻觉 [调研B]

### 3. 异步任务与大结果渲染 [调研C]

- **分层结果策略**：< 4KB 直接内联 / 4KB~1MB SSE 分块 / > 1MB Result Reference + MinIO [调研C]
- **ARQ 优于 Celery**：延迟低 45%、原生 async、与 FastAPI 无缝集成 [调研C]
- **Plotly.js** 适合 AI 生成（声明式 JSON、首次成功率 85%+），但体积大需按需加载 [调研C]

### 4. 具体案例深度分析 [调研D]

- **NVIDIA BioNeMo** 采用企业级 Agent Toolkit + NIM Microservices + 容器化工具封装 [调研D]
- **BioNext-MCP**（国内开发者）展示了中文生信 MCP 插件的可行性 [调研D]
- **OpenBioLLM** 的多智能体架构延迟降低 40-50% [调研D]

---

## 一、现状概览

### 1.1 AI 助手现状

OmicHub 已经具备一套现代的 **Agentic 对话流**：

- **前端入口**：`frontend/src/views/AIChatView.vue` 挂载 `AgentWorkspace`，最终由 `AgentSandbox` 渲染 `KimiMessageList` + `KimiChatInput`。
- **通信协议**：前端通过 `POST /api/v1/chat/stream` 发起 **Server-Sent Events (SSE)** 流式请求；后端返回 `text` / `tool_call` / `tool_result` / `error` / `done` 事件（`frontend/src/composables/useAgentChatStream.ts`）。
- **后端编排**：`src/omichub/application/services/chat_service.py:436` 的 `stream_agent_chat()` 实现了最多 **8 轮**的工具调用闭环：
  1. 调用 `AgentService.assemble_context(agent_id)` 组装模型、系统提示词、MCP 工具列表；
  2. 把工具转成 OpenAI `tools` 格式传给 LLM；
  3. LLM 返回 `tool_calls` 后，在绑定的 MCP server 中查找并 `mcp_client.call_tool()`；
  4. 将 `tool_result` **截断到 4000 字符**后回灌 LLM 上下文并继续生成（`:688`）。
- **MCP 生态**：领域层（`src/omichub/domain/mcp/`）、客户端（`src/omichub/infrastructure/mcp/client.py`）支持 **builtin / stdio / sse**。4 个内置 preset（`presets.py`：literature、genome、code、knowledge）通过 `handlers` 在进程内执行。Agent 经 `mcp_ids` 挂载 server。
- **结果渲染**：`KimiMessageItem.vue` 已展示 `message.toolCalls` 卡片；`message.charts` 当前类型为 **`echarts` only**（`frontend/src/components/ai-chat/types.ts:45`），**尚无 Plotly 渲染路径**。

### 1.2 工具箱现状

工具箱注册在 `tool_configs/tools_setting.yaml`，由 `src/omichub/tools/registry/config.py` 按 mtime 热加载，`GET /api/v1/tools` 返回。字段只有展示元数据：`key`、`title`、`description`、`icon`、`gradient`、`route`、`group`、`enabled`、`order`、`config_dir`。

现有工具可按执行位置分为三类：

| 类型 | 代表工具 | 执行方式 | 输入/输出特点 |
|------|---------|---------|--------------|
| **纯前端工具** | volcano、manhattan、gene-expression-explorer、seq-manipulator、format-converter、plot | 数据解析 + 计算 + 绘图在 `frontend/src/utils/*Processor.ts` | 输入：CSV/TSV + 配置；输出：Plotly figure JSON + 统计 |
| **后端同步工具** | kegg-enrichment | `POST /enrichment/submit` 同步返回；实现在 `src/omichub/tools/enrichments/`（service/runner） | 输入：物种、基因列表；输出：Plotly JSON + 表格；结果落用户目录 |
| **后端异步工具** | phylogenetic-tree、RNA-seq / ATAC-seq flows | `POST .../submit` → `task_id`，再 status/result | 输入：文件/参数；输出：任务状态、结果文件、统计 |

### 1.3 当前 disconnect

**AI 助手和工具箱目前没有连接**：

- `tools_setting.yaml` 只告诉前端「有哪些工具卡片」，没有参数 schema、执行端点、返回格式。
- `assemble_context()` 只从 Agent 绑定的 MCP 拿 tools；工具箱对 LLM 不可见。
- 纯前端工具只能在各自 Vue 页运行，Agent 无法触发。
- 后端工具虽有 service/API，但 Agent 没有统一适配层去调用并把结果以 LLM 友好方式回灌。
- 聊天附件已可注入多模态（`_build_multimodal_messages`），但尚未作为工具入参的标准 `upload://` 引用。

---

## 二、目标架构

### 2.1 核心思路

把工具箱升级为 **「可被 LLM 理解和调用」的工具集合**，复用现有 Agent/MCP 闭环，**优先走 builtin MCP**，避免在 `stream_agent_chat` 里再开一套并行分发（除非调试需要）。

> **更新**：补充 MCP 能力协商与分层工具发现机制

```
┌─────────────────────────────────────────────────────────────────────┐
│                        AI 助手对话前端                                │
│  AgentSandbox → useAgentChatStream → SSE /api/v1/chat/stream       │
│  渲染：toolCalls 卡 + Plotly/ECharts + 任务卡 + 下载链接              │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     ChatService.stream_agent_chat()                 │
│  1. assemble_context() 组装 tools（含 omichub-tools）                │
│     ├─ MCP initialize 能力协商                                       │
│     └─ 分层工具发现：类别路由 → 具体工具 schema                       │
│  2. provider_manager.chat_stream() 调用 LLM                         │
│  3. tool_calls → MCPClient.call_tool()（builtin → ToolBridge）      │
│     ├─ cancellation 支持 + progress 通知                            │
│  4. 回灌 LLM：仅摘要；完整载荷走 SSE metadata                        │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│              builtin MCP: omichub-tools  +  Tool Schema Registry    │
│  tools_schema.yaml → OpenAI function schema + invocation_mode       │
│  ToolBridgeService：校验参数 → 按 mode 分发 → 摘要化输出              │
│  Tool Annotations：readOnly / destructive / openWorld 语义标注       │
└─────────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────────────┐
              ▼               ▼                       ▼
   ┌─────────────────┐ ┌──────────────┐ ┌──────────────────────────┐
   │ backend_shim    │ │ backend_sync │ │ backend_async            │
   │ volcano 等      │ │ 直接调       │ │ ARQ enqueue → job_id     │
   │ pandas/plotly   │ │ Enrichment   │ │ 前端/任务中心看进度      │
   │ 核心路径即可    │ │ Service      │ │ 不在 SSE 内长轮询        │
   └─────────────────┘ └──────────────┘ └──────────────────────────┘
              │
              ▼（非核心 / 未 shim 的纯前端工具）
   ┌─────────────────────────────────────┐
   │ open_tool_page fallback             │
   │ 返回 route + 预填参数提示，引导用户 │
   └─────────────────────────────────────┘
```

### 2.2 关键组件

#### 2.2.1 Tool Schema Registry（工具模式注册表）

> **更新**：补充 MCP 能力协商、Tool Annotations、分层工具发现

**双文件方案**，不破坏现有卡片语义：

- `tool_configs/tools_setting.yaml`：前端 ToolsHub 卡片（保持现状）。
- `tool_configs/tools_schema.yaml`：LLM 可调用的 schema（新建，支持 mtime 热重载）。

**命名约定**：工具 function `name` 统一加前缀 `omichub_`，避免与 MCP preset 或 web_search 撞名。

**MCP 能力协商（Capability Negotiation）** [调研B]：

```python
# MCP initialize 阶段交换 capabilities
{"jsonrpc": "2.0", "method": "initialize",
 "params": {"protocolVersion": "2025-06-18",
  "capabilities": {"tools": {"listChanged": true}},
  "clientInfo": {"name": "OmicHub", "version": "1.0"}}}
# Server 返回：tools.listChanged + progress + cancellation capabilities
```

**Tool Annotations** [调研B]：每个工具附加语义标注，指导 LLM 何时需要用户确认：

```yaml
tools:
  - key: kegg-enrichment
    name: omichub_run_kegg_enrichment
    description: 对基因列表进行 KEGG 通路富集分析。
    invocation_mode: backend_sync
    service: omichub.tools.enrichments.service.EnrichmentService
    method: submit
    requires_confirm: false
    annotations:
      readOnlyHint: false
      destructiveHint: false
      openWorld: false
      idempotent: true
    input_schema:
      type: object
      properties:
        species_id: {type: string, description: "物种 ID，如 human"}
        gene_text: {type: string, description: "每行一个基因符号"}
      required: [species_id, gene_text]
    llm_result_fields: [task_id, stats, top_pathways, success, error]
    ui_result_fields: [plotly_json, table_data, download_urls]

  - key: volcano
    name: omichub_plot_volcano
    description: 根据差异表达结果绘制交互式火山图。
    invocation_mode: backend_shim
    shim_module: omichub.tools.shims.volcano
    requires_confirm: false
    annotations: {readOnlyHint: false, destructiveHint: false, openWorld: false}
    input_schema:
      type: object
      properties:
        data_ref: {type: string, description: "upload://<file_id> 引用"}
        pval_cutoff: {type: number, default: 0.05}
        lfc_cutoff: {type: number, default: 1.0}
    llm_result_fields: [stats, top_up_genes, top_down_genes, success, error]
    ui_result_fields: [plotly_figure, result_ref]

  - key: phylogenetic-tree
    name: omichub_build_phylogenetic_tree
    description: 提交系统发育树构建任务（异步），返回 task_id。
    invocation_mode: backend_async
    service: omichub.tools.phylogenetic_tree.service.PhyloService
    requires_confirm: true
    annotations: {readOnlyHint: false, destructiveHint: false, openWorld: false}
    input_schema:
      type: object
      properties:
        file_id: {type: string, description: "已上传序列文件的 file_id"}
        method: {type: string, enum: [NJ, UPGMA, ML, Bayesian]}
      required: [file_id, method]
    llm_result_fields: [task_id, status, message, success, error]
    ui_result_fields: [task_id, status, progress_url, result_url]
```

**分层工具发现（两阶段路由）** [调研B]：当工具数量 > 20 时，采用「类别→具体工具」的两阶段路由，降低 LLM 选择负担：

```python
# Stage 1: 工具类别选择
omichub_select_tool_category = {
    "name": "omichub_select_tool_category",
    "description": "选择工具类别",
    "input_schema": {
        "type": "object",
        "properties": {
            "category": {"type": "string",
                "enum": ["enrichment", "visualization", "sequence", "workflow"]}
        }
    }
}

# Stage 2: assemble_context 动态过滤，仅暴露选定类别的 tools
def filter_tools_by_category(tools: list, category: str) -> list:
    return [t for t in tools if t.get("category") == category]
```

设计理由：与 `tools_setting.yaml` 解耦；`invocation_mode` 明确执行策略；`llm_result_fields` / `ui_result_fields` 从协议层解决 4000 截断；**Tool Annotations 让 LLM 自主判断确认时机** [调研B]；**分层发现控制 context 长度** [调研B]；大数据入参优先 `upload://`。

#### 2.2.2 Tool Execution Bridge（工具执行桥）

> **更新**：补充 `is_error` 语义错误标记、cancellation 支持、progress 通知

新增 `src/omichub/application/services/tool_bridge_service.py`，职责：

1. 加载/热重载 `tools_schema.yaml`，按 `name` 查找 schema。
2. **JSON Schema 校验** LLM 参数；拒绝越界、缺必填、超大 `data` 字符串。
3. **身份**：始终带 `user_id`（来自 JWT），写路径限制在用户目录。
4. **文件引用**：解析 `upload://<file_id>`，校验归属后读入。
5. 按 `invocation_mode` 分发：
   - `backend_sync` / `backend_shim`：进程内调 service 或 shim，**禁止** HTTP 回环自调用。
   - `backend_async`：**只 enqueue 到 ARQ**，立即返回 `task_id`；**禁止 Bridge 内长轮询**。
   - `open_page`：返回前端 `route` + 预填参数。
6. **结果双通道**：`llm_payload`（仅摘要，≤3KB）回灌 LLM；`ui_payload`（完整图/表）走 SSE metadata。
7. **`is_error` 语义错误标记** [调研B]：失败时返回 `"is_error": true`，让 LLM 自主决定重试或解释。

```python
class ToolBridgeService:
    async def execute(self, user_id: str, tool_name: str, arguments: dict) -> dict:
        schema = self.registry.get(tool_name)
        if schema is None:
            return {"success": False, "is_error": True,
                    "error": f"未知工具: {tool_name}"}
        args = self._validate_and_resolve_refs(user_id, schema, arguments)
        if schema.requires_confirm and not arguments.get("_confirmed"):
            return {
                "success": True,
                "llm_payload": {"needs_confirm": True, "tool_name": tool_name,
                    "summary": "该操作会提交计算任务，请用户确认后再执行",
                    "preview_args": self._safe_preview(args)},
                "ui_payload": {"confirm_card": True, "tool_name": tool_name, "args": args},
            }
        try:
            if schema.invocation_mode == "backend_shim":
                raw = await self._run_shim(schema, user_id, args)
            elif schema.invocation_mode == "backend_sync":
                raw = await self._run_service_sync(schema, user_id, args)
            elif schema.invocation_mode == "backend_async":
                raw = await self._submit_async_only(schema, user_id, args)
            elif schema.invocation_mode == "open_page":
                raw = self._open_page_payload(schema, args)
            else:
                raw = {"success": False, "is_error": True,
                       "error": f"不支持的 mode: {schema.invocation_mode}"}
        except Exception as e:
            raw = {"success": False, "is_error": True, "error": str(e)}
        return {
            "success": bool(raw.get("success", True)),
            "is_error": raw.get("is_error", False),
            "llm_payload": self._pick(raw, schema.llm_result_fields),
            "ui_payload": self._pick(raw, schema.ui_result_fields),
        }
```

**Progress 通知与 Cancellation 支持** [调研B]：

```python
# ARQ Worker 中发布进度
async def arq_compute_phylo_tree(ctx, file_id: str, method: str) -> dict:
    job_id = ctx["job_id"]
    await ctx["redis"].publish(f"task:{job_id}:progress",
        json.dumps({"stage": "alignment", "progress": 0.2}))
    tree = await run_phylo_tool(file_id, method)
    return {"task_id": job_id, "tree": tree}

# SSE 端点透传进度: event: progress
data: {"task_id": "abc123", "stage": "tree_building", "progress": 0.6}
# Cancellation: POST /api/v1/tasks/{task_id}/cancel → await arq_redis.abort_job(task_id)
```

**与 chat_service 的衔接**：handler 返回值应保证 `result` 里给 LLM 的是 `llm_payload`；chat 层把 `ui_payload` 放进 SSE `tool_result` metadata（可约定 `result` 为 `{"llm":..., "ui":...}`）。

#### 2.2.3 纯前端工具策略（修订）

| 方式 | 说明 | 何时用 |
|------|------|--------|
| **A. 后端 Shim** | Python 实现核心计算 + 简化 Plotly JSON | 高频、参数少、适合对话内出图（volcano、manhattan） |
| **B. open_page fallback** | 不执行，返回 `/tools/xxx` + 参数说明 | 交互重、样式复杂、暂未 shim 的工具 |
| **C. 前端 Executor** | SSE 透传 tool_call → 浏览器跑 TS → POST 回灌 | **不作为主路径**（破坏后端闭环） |

**MVP 不做 100% 复刻前端样式**；shim 只保证：列识别、阈值分组、TopN 标注、可交互散点。完整样式仍引导用户打开工具页微调。

#### 2.2.4 挂载方式：优先 builtin MCP `omichub-tools`

**推荐（主路径）**：

1. 在 `presets.py` 增加 `omichub-tools` preset：`transport: builtin`，tools 列表由 `tools_schema.yaml` 生成，handlers 统一委托 `ToolBridgeService.execute`。
2. 在 `AgentService.assemble_context()` 中，**自动把 omichub-tools 并入** `mcp_servers` / `tools`（可配置开关，默认开），无需每个 Agent 手动勾选。
3. `stream_agent_chat` 继续走现有 `mcp_client.call_tool()`，核心闭环几乎不动。

**备选（调试/非 MCP）**：在 `assemble_context` 直接 append OpenAI tools；在 `chat_service.py:653-671` 分发顺序：`MCP → ToolBridge → web_search`。两者可并存。

#### 2.2.5 结果渲染（修订）

现有能力：`toolCalls` 卡 + **ECharts** `charts`。需要扩展：

| 类型 | 来源 | 前端行为 |
|------|------|----------|
| Plotly 图 | `ui_payload.plotly_figure` | `ChartData.type` 扩展为 `'echarts' \| 'plotly'` |
| 表格 | `table_data`（可截断行数） | Naive UI `NDataTable` 或折叠 JSON |
| 任务卡 | `task_id` + status/result URL | 展示进度入口，「去任务中心」链接 |
| 确认卡 | `needs_confirm` | 用户点确认后带 `_confirmed: true` 再调一次 |
| 下载 | `download_urls` / `result_ref` | 按钮下载 |
| open_page | `route` + hints | 一键跳转工具页 |

**禁止**把完整 Plotly JSON 放进回灌 LLM 的 `content`。

#### 2.2.6 异步任务队列选型：ARQ

> **更新**：新增章节，基于调研C的对比分析

**分层执行架构** [调研C]：

| 层级 | 技术 | 使用场景 |
|-----|------|---------|
| L1 即时（< 30s） | FastAPI 原生 asyncio | BLAST 查询、序列格式化 |
| L2 异步（30s ~ 10min） | ARQ + Redis | 系统发育树构建、富集分析 |
| L3 流程（> 10min） | Nextflow + K8s | RNA-seq 完整流程 |

**ARQ 替代 Celery 的理由** [调研C]：

| 维度 | Celery | ARQ | 结论 |
|------|--------|-----|------|
| Python async | 兼容但非原生 | **原生支持** | 与 FastAPI asyncio 生态完美兼容 |
| 延迟 | 中等 | **低 45%** | 对交互式对话场景影响显著 |
| 配置复杂度 | 陡峭 | **平缓** | 团队上手成本低 |
| 复杂工作流 | chain/chord/group | 不支持 | OmicHub L2 任务相对独立 |
| 监控工具 | Flower（成熟） | 无原生 | 需自建轻量监控 UI |

**ARQ 任务定义示例** [调研C]：

```python
from arq import create_pool
from arq.connections import RedisSettings

async def compute_phylo_tree(ctx, file_id: str, method: str = "iqtree") -> dict:
    task_id = ctx["job_id"]
    await ctx["redis"].publish(f"task:{task_id}:progress",
        json.dumps({"stage": "alignment", "progress": 0.2}))
    result = await run_phylo_tool(file_id, method)
    return {"task_id": task_id, "summary": f"树含 {len(result['sequences'])} 条序列",
            "plotly_data": result.get("plotly_json")}

class WorkerSettings:
    functions = [compute_phylo_tree]
    redis_settings = RedisSettings(host="localhost")
    max_jobs = 10; job_timeout = 3600; max_tries = 2
```

---

## 三、让 AI 助手「知道有哪些工具」

### 3.1 系统提示词注入

在 `assemble_context()` 组装 `system_prompt` 时追加自然语言清单（与 function tools 互补，降低漏调）：

```
你是 OmicHub 生信平台的 AI 助手。当前可调用平台工具（function 名以 omichub_ 开头）：
1. omichub_run_kegg_enrichment — KEGG 通路富集（物种 + 基因列表）
2. omichub_plot_volcano — 火山图（差异表达表，优先 upload://）
3. omichub_build_phylogenetic_tree — 提交建树任务（异步，需确认）
...
规则：
- 需要计算/出图时优先调用工具，不要只给操作说明。
- 大文件用 upload://file_id，不要把整表 CSV 塞进参数。
- 异步工具只负责提交；完成后引导用户根据 task_id / 任务中心查看。
- 标注 requires_confirm 或 destructiveHint 的工具须先说明影响并等待用户确认。
```

### 3.2 function schema 注入

将 `tools_schema.yaml` 的 `input_schema` 转为 OpenAI `tools[]`，经 omichub-tools MCP 或直接 append 到 `ctx.tools`。

### 3.3 体验增强（可选，Phase 2+）

- ToolsHub 卡片「问问 AI」→ 跳转 AIChat 预填提示词。
- 输入框 `/tool` 列出可用工具。
- 聊天附件自动映射为 `upload://` 供下一轮 tool 使用。

---

## 四、安全与权限

1. **身份传递**：Bridge / service 调用一律使用 JWT 解析的 `user_id`（不信任 LLM 传入的 user_id）。
2. **路径隔离**：结果只写用户目录；禁止 LLM 指定绝对路径。
3. **文件引用**：仅 `upload://` / 受控 chat-upload 路径；校验归属后再读。
4. **参数校验**：JSON Schema + 字符串长度/行数上限 + 枚举白名单。
5. **执行前确认**：`requires_confirm: true` 或 `destructiveHint: true` 的工具必须二次确认。
6. **配额与滥用**：单会话 `max_rounds=8` 已有；建议增加每用户工具调用速率限制。
7. **工具名隔离**：`omichub_` 前缀 + registry 唯一性校验。

---

## 五、分阶段实现建议（修订顺序）

> **更新**：明确各 Phase 产出物、验收标准、工期估算与风险缓解

### Phase 1：打通闭环（约 2 周）

**目标**：验证「发现 → 调用 → 摘要回灌 → 前端出图/表格」。

**交付物**：`tools_schema.yaml`（kegg + volcano）、`schema_loader.py`、`ToolBridgeService`、`omichub-tools` builtin preset、`volcano.py` shim、前端 Plotly 渲染、chat_service 双通道改造。

**最小可行验证清单（MVP 验收标准）**：

- [ ] 「对 TP53 BRCA1 EGFR MYC KRAS 做人类 KEGG 富集」→ 调用 enrichment → 聊天内出现通路表摘要 + 可交互 Plotly 图
- [ ] 「用这份差异表画火山图」+ 上传 CSV → 后端 shim 执行 → 出图 + LLM 能概括上下调数量
- [ ] 验证 `llm_payload` ≤ 3KB（不触发 4000 截断问题）
- [ ] 验证 `ui_payload.plotly_figure` 完整到达前端（不被截断）
- [ ] 工具 schema 热重载：修改 `tools_schema.yaml` 后 30 秒内生效

**明确不在本阶段做**：异步长轮询、全量前端工具 shim、ARQ 集成、前端 Executor、分层工具发现。

**工期**：2 周（后端 1.2 周 + 前端 0.8 周）
**风险缓解**：若火山 shim 超预期，Phase 1 只做 KEGG（零双实现）。

### Phase 2：覆盖与异步（约 3 周）

**目标**：扩展工具覆盖 + 异步任务提交 + ARQ 集成。

**交付物**：第二批 shim + `open_page` fallback、ARQ 集成 + `backend_async` 仅 submit、任务中心页面（SSE progress）、`requires_confirm` 确认卡、统一 `upload://` 解析、分层工具发现（> 15 个工具时启用）。

**工期**：3 周（后端 2 周 + 前端 1 周）
**风险缓解**：ARQ 生态不够成熟 → 保留 Celery 迁移路径；先用 Redis Stream 自建轻量监控。

### Phase 3：体验与外露（约 2 周）

**目标**：产品化体验 + 外部集成准备 + 知识化增强。

**交付物**：确认卡产品化 + 调用历史、速率限制与审计日志、`omichub-tools` 稳定 MCP 契约文档、分析结果知识化（自动关联文献）、可复现参数导出（BCO 预览）、Plotly.js 按需加载优化。

**工期**：2 周（后端 1.2 周 + 前端 0.8 周）
**风险缓解**：Plotly.js 按需加载若实现复杂，可延迟到后续版本。

---

## 六、需要新增/修改的文件

| 文件 | 动作 | 说明 |
|------|------|------|
| `tool_configs/tools_schema.yaml` | 新建 | LLM schema + mode + annotations + 字段白名单 |
| `src/omichub/tools/schema_loader.py` | 新建 | 加载/校验/热重载 |
| `src/omichub/application/services/tool_bridge_service.py` | 新建 | 校验、分发、摘要化、async 仅 enqueue |
| `src/omichub/tools/shims/volcano.py`（等） | 新建 | 轻量后端 shim |
| `src/omichub/infrastructure/mcp/presets.py` | 修改 | 注册 `omichub-tools` builtin，含 capability negotiation |
| `src/omichub/application/services/agent_service.py` | 修改 | 自动注入 omichub-tools，支持分层发现 |
| `src/omichub/application/services/chat_service.py` | 小改 | 双通道 result：LLM 摘要 + SSE ui_payload；is_error 标记 |
| `src/omichub/infrastructure/task_queue/arq_worker.py` | 新建 | ARQ Worker 配置 + 任务函数定义 |
| `src/omichub/api/...` 可选 `POST /tools/invoke` | 可选 | 调试 Bridge |
| `frontend/src/components/ai-chat/types.ts` | 修改 | `ChartData.type` 增加 `plotly` |
| `frontend/src/components/ai-chat/KimiMessageItem.vue` | 修改 | Plotly / 表格 / 任务卡 / 确认卡 / 进度通知 |
| `frontend/src/components/ai-chat/TaskProgressCard.vue` | 新建 | 任务进度卡片（SSE progress 事件渲染） |
| `frontend/src/views/BioTools/ToolsHubView.vue` | 可选 | 「问问 AI」 |

---

## 七、关键设计决策（修订）

> **更新**：补充业界依据标注

| 决策点 | 推荐方案 | 业界依据 |
|--------|---------|----------|
| 工具 schema 放哪 | `tools_schema.yaml` 独立文件 | Galaxy XML 解耦经验 [调研A] |
| 与 Agent 集成 | **优先 builtin MCP `omichub-tools`** | MCP 适配度 ★★★★★ [调研B] |
| 纯前端工具 | 高频 **轻量 shim** + 其余 **open_page** | Code Interpreter sandbox 模式 [调研D] |
| 异步工具 | **ARQ enqueue 仅 submit**，不在 Bridge/SSE 内长轮询 | 调研C 推荐方案 |
| 大结果 | **llm 摘要 + ui 完整载荷 / result_ref** | OpenAI Code Interpreter annotations [调研D] |
| 大数据入参 | **upload:// / 附件**，禁止大 CSV 进 args | Anthropic 文件引用模式 [调研D] |
| 工具命名 | **`omichub_` 前缀** | 业界工具前缀惯例 |
| 后端调用 | **进程内 service**，非 HTTP 自调用 | LangChain ToolNode 模式 [调研B] |
| 身份与权限 | 复用 JWT `user_id` + 用户目录 | Terra FISS-MCP 安全模型 [调研A] |
| 结果渲染 | 扩展 charts 支持 plotly + 任务/确认卡 | Plotly.js AI 生成成功率 85%+ [调研C] |
| 错误处理 | **`is_error` 语义标记** | Anthropic Tool Use [调研B] |
| 工具发现 | **两阶段路由（类别→工具）** | Claude Code 100+工具路由 [调研B] |
| 异步队列 | **ARQ 替代 Celery** | 原生 async、延迟低 45% [调研C] |

---

## 八、风险与规避

> **更新**：补充 ARQ 生态、Plotly.js 体积、LLM context 管理风险

| 风险 | 规避 |
|------|------|
| LLM 参数错误 | JSON Schema 校验 + `is_error` 语义标记回灌 [调研B] |
| tool_result 4000 截断导致图/表丢失 | 强制 `llm_result_fields`；完整数据走 `ui_payload` |
| 聊天侧仅 ECharts | Phase 1 同步做 Plotly 渲染，否则 shim 白做 |
| 前后端实现漂移 | shim 只覆盖核心路径；完整交互仍走工具页 |
| 异步任务拖死 SSE | ARQ 仅 enqueue；任务卡 + 任务中心 + progress 通知 [调研C] |
| LLM 刷重计算 | `requires_confirm` + 速率限制 + `max_rounds` |
| 工具名冲突 | `omichub_` 前缀 + 启动时唯一性检查 |
| Schema 维护成本 | 新增工具 PR checklist：卡片 yaml + schema yaml + shim |
| 用户数据泄露 | 文件归属校验；禁止绝对路径；日志不落敏感全量数据 |
| **ARQ 生态不够成熟** | 自建轻量任务监控 UI；保留 Celery 迁移路径（接口抽象隔离队列实现） [调研C] |
| **Plotly.js 体积大（~3MB）** | 按需 dynamic import；ECharts 保留作为大数据量降级方案 [调研C] |
| **工具数量膨胀后的 LLM context** | 两阶段路由控制单次暴露 ≤ 15 个；`openWorld` 标注过滤不相关工具 [调研B] |

---

## 九、与代码的关键锚点（实现时对照）

| 能力 | 位置 |
|------|------|
| Agent 工具闭环 | `chat_service.py` → `stream_agent_chat`（约 436–718 行） |
| 工具列表组装 | `agent_service.py` → `assemble_context`（约 309 行） |
| MCP 调用 / builtin handler | `infrastructure/mcp/client.py`、`presets.py` |
| tool_result 截断 | `chat_service.py` 约 686–688 行 `[:4000]` |
| 工具卡片注册 | `tool_configs/tools_setting.yaml`、`tools/registry/` |
| KEGG 同步实现 | `src/omichub/tools/enrichments/`（api/service/runner） |
| 建树异步 | `src/omichub/tools/phylogenetic_tree/` |
| 前端火山逻辑 | `frontend/src/utils/volcanoProcessor.ts` |
| 聊天图表类型 | `frontend/src/components/ai-chat/types.ts`（当前仅 echarts） |

---

## 十、结语

OmicHub 已具备 Agentic 基础设施（SSE、MCP builtin、多轮 tool 闭环）。联动工作的本质，是把工具箱从「前端卡片注册表」升级为 **「LLM 可消费的 schema + 进程内执行桥」**，并处理好 **结果体积、异步生命周期、双实现边界**。

> **更新**：基于业界调研的补充结论

**推荐实施主线**：

1. **builtin MCP `omichub-tools` + ToolBridge** — 复用现有 MCP 闭环 [调研B]
2. **先 KEGG（零双实现）→ 再 volcano 轻量 shim** — 最小验证路径
3. **摘要回灌 LLM，完整图/表给前端** — 分层结果策略 [调研C]
4. **异步只 enqueue，确认后再跑重任务** — ARQ 原生 async [调研C]
5. **两阶段工具发现 + Tool Annotations** — 为工具膨胀预留扩展性 [调研B]

按此路径推进，可在较少改动现有编排的前提下验证闭环，再逐步扩大工具覆盖面。业界趋势（MCP 标准化、ARQ 高性能异步、Plotly AI 友好）与 OmicHub 现有架构高度契合，窗口期有利。

---

## 十一、业界对标与 OmicHub 差异化定位

> **更新**：新增章节，基于 4 份调研的综合分析

### 11.1 主流平台 AI 集成做法对比

| 平台 | AI 集成方案 | 工具协议 | 异步策略 | 差异化不足 |
|------|-----------|----------|----------|-----------|
| **Galaxy** | MCP Server + Galactic Wizard + RNN 推荐 | Tool XML | Job Runner 插件化 | AI 功能实验性质强 [调研A] |
| **Terra** | FISS-MCP（Broad 自研） | WDL (GA4GH TRS) | Cromwell 异步 | 缺乏原生对话式 AI 助手 [调研A] |
| **Seqera** | Co-Scientist AI CLI | Nextflow DSL2 | Nextflow 原生异步 | CLI 形态为主，Web 集成浅 [调研A] |
| **NVIDIA BioNeMo** | Agent Toolkit + Nemotron | NIM Microservices | 容器化异步 | 闭源生态 + GPU 锁定 [调研D] |
| **BioNext-MCP** | MCP 插件 for Claude Desktop | Python 脚本 | 本地执行 | 单用户桌面端，非平台化 [调研D] |

### 11.2 OmicHub 的差异化机会

**差异化一：生信 Schema 自动生成**

- 从 Python/R 函数签名自动提取参数信息，生成 LLM function schema
- 内置生信参数类型库（organism codes、gene ID formats、p-value thresholds）
- 支持 `scanpy`、`Seurat`、`DESeq2`、`clusterProfiler` 等主流包的自动 wrapping

**差异化二：中文场景深度覆盖**

- 中文自然语言理解优化（物种名、基因名的中英文对照）
- 中国人群基因组数据库集成（如 ChinaMAP）
- **国内尚无集「自然语言交互 + 生信工具调用 + 智能报告生成」于一体的成熟产品** [调研D]

**差异化三：分析结果知识化**

- 不只是返回图表，而是返回**带解读的分析报告**
- 自动关联文献、通路数据库、临床注释
- 结果可追溯（BCO 标准集成）

**差异化四：开放生态 + 平台级集成深度**

| 维度 | OmicHub 定位 | 对比 |
|------|-------------|------|
| 架构 | Web 平台 + MCP builtin + Agentic 对话流 | BioNext-MCP 是桌面插件 |
| 集成深度 | 进程内 service 调用 + 双通道结果渲染 | Terra 是工作流级别 |
| 扩展性 | YAML schema + ARQ 异步 + 两阶段路由 | 比 NVIDIA 闭源更开放 |
| 部署 | 支持私有化 + 国产算力适配 | 比 BioNeMo 更灵活 |

### 11.3 竞争态势总结

```
                    平台化程度（高）
                          |
           Galaxy ───────┼─────── NVIDIA BioNeMo
                          |
    工具丰富度            │            OmicHub ★
    （低）────────────────┼────────────────（高）
                          |
           BioNext-MCP ──┼─────── Seqera
                          |
                    平台化程度（低）
```

OmicHub 的差异化定位：**国内首个平台级、对话式、深度生信集成的 AI 助手**，填补「通用生信 Web 平台 + 原生 AI 工具调用」的市场空白。

---

*文档结束*
