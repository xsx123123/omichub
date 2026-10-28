# AI 助手扩展：多 Agent 协作 × 工具绑定 × mem0 记忆（2026-07-23）

> 关联文档：`docs/26.7.22/ai_assistant_single_entry_architecture.md`（统一入口架构）、
> `docs/26.7.21/ai_assistant_review.md`（LangGraph 引擎）、
> `docs/26.7.21/mcp_ai_assistant_integration.md`（MCP 联动）。
> 本文基于当前 `feat/ai-assistant-framework` 分支的架构现状，规划三个方向的演进路径。

---

## 1. 多 Agent 协作：从单路由到编排

### 1.1 现状与 Gap

当前 router（`agent-router`）每条消息只选**一个**专家回答（`chat_service.py`
`_route_to_agent`，SSE `route` 事件 + 气泡路由徽标），本质是"单轮单专家路由"。
`agent-orchestrator`（MAS）的 YAML 已定义 DAG 计划 + 用户确认的雏形
（`features.mas_orchestrator: true`、`features.requires_plan_confirmation: true`），
但仍在 Feature Flag 后面，未真正展开。

### 1.2 目标场景：单细胞分析多专家接力

```
用户: "帮我分析这个 PBMC 数据集"
  → agent-scrna   : QC + 聚类 + 细胞注释（Studio 沙盒跑 Scanpy/Seurat）
  → agent-viz     : 出 UMAP / 小提琴图 / 差异基因热图
  → agent-rnaseq  : 通路富集 / 细胞通讯分析
  → agent-general : 汇总生物学解读
```

### 1.3 落地路径

#### 近期：LangGraph 子图编排（推荐先做）

在 LangGraph 里建一个 scRNA 分析状态图，QC → 聚类 → 注释 → 可视化是确定性节点，
每个节点调用对应专家的 prompt + 工具集，模型只做参数决策和结果解读。
文档 `26.7.22` §3 P3 已规划此方向。

```
┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐
│ QC 节点  │───▶│ 聚类节点 │───▶│ 注释节点 │───▶│ 可视化   │
│(确定性)  │    │(确定性)  │    │(LLM决策) │    │(确定性)  │
└─────────┘    └─────────┘    └─────────┘    └─────────┘
     │              │              │              │
  Scanpy API    Scanpy API    模型选 marker   matplotlib
  参数校验      分辨率搜索    基因 & 解读     出图 + 报告
```

- 每个节点可复用对应 Agent 的 `assemble_context()` 拿到 prompt + tools
- 中间产物（h5ad、图片路径、表格）通过 LangGraph State 传递
- 与现有 `features.engine: langgraph` 分流机制兼容（`chat_service.py:838`）

#### 中期：A2A 协议 + MAS Orchestrator

当 Agent 真正需要独立部署或对接外部 Agent 时，引入 Google A2A（Agent-to-Agent）协议：

| A2A 概念 | 映射到 OmicHub |
|---|---|
| Agent Card（能力描述 JSON） | 现有 `data/ai/*.yaml` 扩展为 `/.well-known/agent.json` |
| Task（任务委派 + 状态追踪） | orchestrator 生成的 DAG 子任务 |
| Artifact（中间产物交换） | h5ad 文件、图片、富集表格等 |
| Message / Part | 复用现有 SSE `data:` 行格式 |

- orchestrator 生成 DAG 计划 → 用户确认 → 每个子任务通过 A2A Task 委派
- 各 Agent 服务独立暴露 A2A 端点，支持跨框架（LangGraph / AutoGen / 自研）
- 适合多团队、多服务器、跨组织协作场景

#### 选型建议

| 维度 | LangGraph 子图 | A2A 协议 |
|---|---|---|
| 复杂度 | 低，进程内状态图 | 高，需 HTTP + JSON-RPC 层 |
| 适用规模 | 单服务内 3-5 个 Agent 协作 | 独立部署 / 跨组织 Agent |
| 中间产物传递 | State 字典，零拷贝 | Artifact URL，需文件服务 |
| 断线恢复 | LangGraph checkpointer | A2A Task 状态轮询 |
| 推荐阶段 | **现在** | Agent 独立化之后 |

---

## 2. 给不同 Agent 添加工具（Tools）

### 2.1 当前机制

工具绑定在 `agent_service.py:assemble_context()` 中完成：

```
Agent YAML mcp_ids[] → 查 mcp_servers 表 → 拿每个 server 的 tools[]
                     → 转 OpenAI function-calling schema → 注入 LLM 请求
```

### 2.2 三种绑定方式

#### 方式一：绑定已有 MCP Server（推荐）

在 Agent YAML 的 `mcp_ids` 里加对应 server 的 UUID：

```yaml
# data/ai/scrna.yaml
mcp_ids:
  - "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"  # mcp_servers 表中某个 server 的 ID
```

`assemble_context` 会自动查库、拉工具列表、转 schema。

#### 方式二：默认注入（零配置）

`mcp_ids` 为空时，`agent_service.py:113-114` 自动注入两个 builtin preset：

- `omichub-tools`：平台内置分析工具（schema_loader 注册）
- `omichub-platform`：平台管理能力（任务查询、文件管理等）

当前所有 Agent YAML 的 `mcp_ids: []` 均走此默认路径。

#### 方式三：Skill 注入 prompt 级能力

`skill_ids` 绑定的技能通过 `_build_skills_prompt()` 拼进 system_prompt 后缀，
适合给 Agent 加领域知识 / 工作流指引（非 function-calling 工具）。

### 2.3 新增自定义工具流程

```
1. 实现 MCP Server（stdio / sse 外部进程，或 builtin preset）
2. 在 mcp_servers 表注册（name, transport, tools[]）
   - tools[] 每项：tool_name, description, input_schema (JSON Schema)
3. 在目标 Agent YAML 的 mcp_ids 里引用该 server UUID
4. ensure_builtin_agents 同步后生效（或管理员手动绑定）
```

### 2.4 未来扩展：运行时动态工具

当前不支持根据上下文（如用户上传文件类型）临时加载工具。
如需实现，在 `assemble_context` 里加一层条件逻辑：

```python
# 伪代码：根据会话附件类型动态追加工具
if has_h5ad_attachment(messages):
    extra_tools = await load_scanpy_tools()
    tools.extend(extra_tools)
```

---

## 3. mem0 记忆集成

### 3.1 现状

当前上下文管理是基础的会话消息历史（`chat_messages` 表），无长期记忆、
无跨会话记忆、无摘要压缩。长会话会 token 爆炸，切换 Agent 后丢失上下文。

### 3.2 三层记忆架构

```
┌─────────────────────────────────────────────────────┐
│ 层级 3：跨 Agent 共享记忆                            │
│   所有 Agent 共享 user_id 的 mem0 空间               │
│   router 路由时把记忆传给目标专家                     │
│   按 agent_id metadata 过滤领域相关记忆              │
├─────────────────────────────────────────────────────┤
│ 层级 2：会话级摘要记忆                               │
│   长会话（>20 轮）自动摘要压缩早期消息                │
│   避免 token 爆炸，保留关键决策和中间结果             │
├─────────────────────────────────────────────────────┤
│ 层级 1：用户级长期记忆（最实用，推荐先做）            │
│   每轮对话后提取记忆 → 下一轮检索注入 system_prompt   │
│   跨会话持久化，用户偏好 / 历史分析结论 / 常用参数    │
└─────────────────────────────────────────────────────┘
```

### 3.3 层级 1 实现方案（推荐先做）

在 `chat_service.stream_agent_chat` 的 `assemble_context` 之后、LLM 调用之前
加两个 hook：

```python
from mem0 import Memory

# ── 初始化（应用启动时单例） ──
mem0_config = {
    "llm": {
        "provider": "openai",
        "config": {
            "model": "qwen3.7-max",
            "api_key": settings.OPENAI_API_KEY,
            "base_url": settings.OPENAI_BASE_URL,  # 复用 ProviderManager 配置
        },
    },
    "vector_store": {
        "provider": "qdrant",
        "config": {"host": "localhost", "port": 6333},
    },
}
memory = Memory.from_config(mem0_config)

# ── Hook 1：调用前检索（注入 system_prompt） ──
relevant = memory.search(query=user_message, user_id=user_id, limit=5)
if relevant:
    memory_block = "\n".join(r["memory"] for r in relevant)
    system_prompt = f"{system_prompt}\n\n## 用户历史记忆\n{memory_block}"

# ── Hook 2：调用后提取（异步，不阻塞 SSE） ──
memory.add(
    messages=[
        {"role": "user", "content": user_message},
        {"role": "assistant", "content": assistant_reply},
    ],
    user_id=user_id,
    metadata={"agent_id": agent_id, "session_id": session_id},
)
```

### 3.4 层级 2：会话级摘要

```python
# 在消息组装环节，当历史消息 > 20 轮时触发
if len(history_messages) > 20:
    early = history_messages[:-10]   # 早期消息
    recent = history_messages[-10:]  # 最近 10 轮保留原文
    summary = await llm_summarize(early)  # LLM 摘要
    history_messages = [
        {"role": "system", "content": f"## 早期对话摘要\n{summary}"},
        *recent,
    ]
```

### 3.5 层级 3：跨 Agent 共享

```python
# 所有 Agent 共享同一个 user_id 的 mem0 空间
# router 路由时把记忆一起传给目标专家
relevant = memory.search(
    query=user_message,
    user_id=user_id,
    limit=5,
    # 可选：按 agent_id 过滤，让 scrna 专家只看分析相关记忆
    # filters={"agent_id": "agent-scrna"},
)
```

### 3.6 落地建议

| 步骤 | 内容 | 改动范围 |
|---|---|---|
| 1 | `pip install mem0ai`，Docker 起 Qdrant | 依赖 + 部署 |
| 2 | 在 `core/config.py` 加 mem0 配置项（Qdrant 地址、embedding 模型） | 配置 |
| 3 | 新建 `infrastructure/memory/mem0_client.py`，封装 Memory 单例 | 基础设施 |
| 4 | `chat_service.stream_agent_chat` 加 search / add 两个 hook | 应用服务 |
| 5 | 层级 2 摘要压缩（可选，长会话场景） | 应用服务 |
| 6 | 层级 3 跨 Agent 共享 + metadata 过滤（可选） | 应用服务 |

- mem0 的 LLM 配置复用 `ProviderManager` 里已有的模型（qwen3.7-max）
- 向量库先用 Qdrant（`docker run -p 6333:6333 qdrant/qdrant`），
  MVP 阶段可用 mem0 内置 SQLite + 本地 embedding
- 记忆提取（Hook 2）建议异步执行（`asyncio.create_task`），不阻塞 SSE 流

---

## 4. 优先级总览

| 优先级 | 事项 | 依赖 | 预估工作量 |
|---|---|---|---|
| **P0** | mem0 层级 1（用户级长期记忆） | Qdrant 部署 | 1-2 天 |
| **P1** | LangGraph scRNA 子图编排 | LangGraph 引擎已就绪 | 3-5 天 |
| **P1** | 自定义 MCP 工具绑定文档化 | 无 | 0.5 天 |
| **P2** | 会话级摘要压缩（层级 2） | mem0 层级 1 | 1 天 |
| **P2** | 运行时动态工具加载 | assemble_context 改造 | 1-2 天 |
| **P3** | A2A 协议 + MAS Orchestrator 落地 | Agent 独立部署 | 1-2 周 |
| **P3** | 跨 Agent 共享记忆（层级 3） | mem0 层级 1 + router 改造 | 1 天 |
