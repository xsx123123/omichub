# OmicHub 平台 Agent 能力优化方案：长期记忆与 A2A 多 Agent 协作

> 依据《OmicHub Agent 架构现状与扩展指南》（2026-07-26）编写。
> 前提共识：平台已实现真实的"工具增强型单 Agent + 模型路由"架构（ReAct/LangGraph、
> 四来源工具、白名单授权、审计），MAS 基础设施（Plan/Run/Node/Artifact/Approval/
> A2A Event/Celery 调度）已建成但默认关闭。
> 本文目标：补齐两大能力短板——**跨会话长期记忆** 与 **A2A 多 Agent 协作**，
> 并给出分阶段、可独立验收的实现方案。

### 文档关系与实施基线

本文是优化路线图；当前已实现的架构、真实运行链路、配置位置与已有边界以
[`ARCHITECTURE_DESIN/agent_architecture_and_extension_guide.md`](../../../ARCHITECTURE_DESIN/agent_architecture_and_extension_guide.md)
为准。实施时应先按该文档确认现有行为，再以本文定义新增能力的验收标准。

尤其要保持以下事实不被实现方案覆盖：

1. 当前默认链路是“router 一次分派 → 一个目标 Agent 执行”，不是多专家自动会诊；
2. Agent 的实际运行时模板来自数据库；`data/ai/*.yaml` 对已落库内置 Agent 默认只同步
   `features` 和 Studio 描述，不会自动覆盖提示词、模型或 MCP/Skill 绑定；
3. `features.engine: langgraph` 与手写 ReAct 循环并存，新控制类能力必须同时接入两条执行路径；
4. MAS 有 Run/Node/Artifact/A2A/Celery 调度基础设施，但默认关闭，且普通聊天不会自动创建 MAS Run。

### 实施状态（2026-07-26）

- **P1 长期记忆 MVP 已落地到代码**：新增 `agent_memories` 迁移与用户隔离服务、
  ToolBridge 记忆工具、聊天装配层的 L1/L2 召回、个人中心管理卡片及管理员只读查询接口。
- **上线前操作**：目标环境需执行 `alembic upgrade head` 创建记忆表；现有内置 Agent 在
  下次同步 features 后获得 `memory` 工具包，运行时还会补充通用记忆协议以兼容已落库提示词。
- **P2 Handoff 已落地到代码**：新增 `transfer_to_agent` ToolBridge 工具、Agent YAML 白名单与
  跳数限制、会话级交接事件审计、≤600 token 交接包、ReAct/LangGraph 双引擎上下文切换和前端
  SSE 转交卡片；默认 router 行为仍保持一次分派。
- **P3 MAS 产品化代码已就绪，默认灰度关闭**：已有计划预览/确认卡、Run 进度 SSE、节点失败重试、
  产物下载和 Artifact Schema 边校验。实际开放仍要求显式开启 `MAS_ENABLED=true`、部署 Celery
  调度链；该开关会自动将 `orchestrator` 纳入内置 Agent 同步，普通对话不会自动创建 MAS Run。
  除 RNA-seq 外，新增受限 `scanpy-qc` 单细胞节点（仅 `.h5ad`、禁网 Docker、过滤对象与 QC JSON
  产物）；对应单细胞镜像必须部署到 MAS Worker 后才可加入灰度模板。
- **P4 已提供默认关闭的增强实现**：语义向量重排复用 Provider embeddings、会话删除后的
  Celery 摘要记忆、可选 `update / coexist / discard` 冲突裁决，以及 router 驱动的 2~3
  专家并行会诊与主专家汇总均受独立开关保护；离线评估集仍按后续阶段推进。

---

## 第一部分：总体路线

### 1.1 为什么是这两个方向

| 现状短板 | 用户可感知的失败 | 对应方案 |
|---|---|---|
| 只有会话内持久化，无跨会话记忆 | "我上周说过我的数据是 10x V3 小鼠脑，这个会话又问我一遍" | Part 2 长期记忆 |
| router 单次分派后只有一个专家 | "单细胞质控做完想接着做富集分析，scrna 助手不会，让我自己重新开对话找 rnaseq" | Part 3 Agent Handoff |
| MAS 建成但无产品入口 | 复合任务（完整 RNA-seq 流程）无法自动拆解执行 | Part 4 MAS 产品化 |

### 1.2 分阶段路线（每阶段独立可验收、可灰度）

```text
阶段一（P1，1~2 周）：长期记忆 MVP —— 记忆表 + 模型自主记忆工具 + 规则召回注入 + 用户管理入口
阶段二（P2，2~3 周）：Agent Handoff —— transfer_to_agent 工具 + 上下文交接包 + 前端转交可视化
阶段三（P3，2~3 周）：MAS 产品化灰度 —— 计划预览/确认 UI + 单场景灰度（RNA-seq 全流程）
阶段四（P4，按需）：记忆增强（向量召回、会话自动提炼）与多专家会诊（并行 + 汇总）
```

关键设计原则：

1. **复用而非重建**：A2A 协作直接长在现有 MAS 的 Event/outbox/Celery 设施上，不新造通信层；
2. **最小权限与可审计延续**：记忆写入、Agent 转交全部落审计，与现有工具治理对齐；
3. **用户可控**：记忆用户可见可删；协作过程（转交、计划）前端全程可见、可干预；
4. **默认收敛**：新能力先灰度，router 现有单次分派行为为默认回退路径。

---

## 第二部分（P1/P4）：长期记忆系统

### 2.1 记忆分层模型

| 层 | 范围 | 内容 | 生命周期 | 注入方式 |
|---|---|---|---|---|
| L0 会话记忆 | 单会话 | 消息历史、工具结果 | 会话级（已有） | 全量/压缩注入 |
| L1 用户画像 | 跨会话、全 Agent 共享 | 身份背景、偏好、常用数据类型、常用物种/参考基因组 | 长期，用户可删 | 常驻注入（≤300 tokens） |
| L2 项目/领域记忆 | 跨会话、按 Agent 或项目 | "某某项目用 GRCh38、样本分 4 组"、"scrna 数据已做完双细胞去除" | 长期，用户可删 | 按需召回注入 |
| L3 会话摘要 | 跨会话、按 Agent | 历史会话的压缩摘要 | 滚动归档 | 检索召回（P4） |

设计要点：**L1 常驻、L2/L3 按需**——延续平台 Skill 渐进披露的同一思想，避免记忆把系统提示撑爆。

### 2.2 数据模型

```sql
-- 记忆主表
CREATE TABLE agent_memories (
    id              UUID PRIMARY KEY,
    user_id         VARCHAR(36) NOT NULL,             -- 用户隔离，所有查询必带
    agent_id        VARCHAR(64) NULL,                 -- NULL = 用户级共享记忆；否则 Agent 专有
    scope           VARCHAR(16) NOT NULL,             -- profile | project | preference | summary
    content         TEXT NOT NULL,                    -- 一条记忆 = 一句自包含陈述
    keywords        JSONB NOT NULL DEFAULT '[]',       -- 规则召回用关键词（写入时由模型生成）
    embedding       VECTOR(1024) NULL,                -- P4 向量召回，MVP 可空
    source_session  VARCHAR(36) NULL,                 -- 来源会话（审计追溯）
    confidence      FLOAT NOT NULL DEFAULT 1.0,       -- 模型自述置信度
    use_count       INT NOT NULL DEFAULT 0,           -- 召回命中次数（淘汰依据）
    last_used_at    DATETIME NULL,
    status          VARCHAR(16) NOT NULL DEFAULT 'active',  -- active | archived
    created_at      DATETIME NOT NULL,
    updated_at      DATETIME NOT NULL,
    INDEX idx_user_agent (user_id, agent_id, status),
    INDEX idx_user_scope (user_id, scope, status)
);
```

约束：单用户记忆上限（如 500 条），超过时按 `use_count × recency` 淘汰到 archived；
`content` 单条 ≤200 字符，强制"一句自包含陈述"，防止模型把整段对话塞进来。

### 2.3 模型侧记忆工具（注册进 ToolBridge，走既有 schema/审计链路）

| 工具 | 入参要点 | 行为 |
|---|---|---|
| `save_memory` | content, scope, agent_id?, keywords[] | 写入前查重（同 user 下关键词重叠度高的已有记忆 → 转为 update）；返回记忆 id |
| `update_memory` | memory_id, content | 覆盖内容并记 updated_at；旧值进审计日志 |
| `forget_memory` | memory_id | 软删除（archived） |
| `search_memory` | query, scope?, limit≤5 | L2/L3 按需召回：MVP 用关键词 LIKE + use_count 排序；P4 换向量 |

工具在 `tool_configs/tools_schema.yaml` 注册，`invocation_mode: sync`，权限标注
`user_scoped: true`；授权通过工具包：`data/ai/tools/memory.yaml`，默认只给
`agent-general`、`agent-scrna`、`agent-rnaseq`、`shania` 等长期陪伴型 Agent，
一次性任务型工具 Agent 不给。

实现时需补充一个明确的数据库发布动作：对已落库 Agent，仅编辑 `tool_packs` 不会自动把
新的工具绑定写入 `mcp_ids` / `skill_ids`。记忆工具若通过内置 ToolBridge 暴露，可由
`features.tool_packs` 白名单生效；若使用 Skill 或外部 MCP，则还需通过管理端/API 保存绑定，
或先实现“从 YAML 发布”动作。

### 2.4 召回与注入

```text
`ChatService.stream_agent_chat()` 已掌握 `user_id` 与用户消息；记忆召回应在这里或其调用的
会话级上下文装配方法中新增，**不能只在当前签名为 `assemble_context(agent_id)` 的
`AgentService.assemble_context()` 内实现**，否则缺少用户隔离和当前 query。推荐链路：

```text
ChatService.stream_agent_chat(user_id, agent_id, messages)
  ├── AgentService.assemble_context(agent_id)  # Agent 静态模板、工具和能力
  └── MemoryService.build_prompt_context(user_id, agent_id, user_text)
```

随后追加：

```text
  ├── L1 常驻块：取 user_id 下 scope=profile/preference 的 active 记忆（≤10 条）
  │     渲染为系统提示尾部固定块：
  │       "## 用户记忆（跨会话，可能过时，与当前对话冲突时以对话为准）
  │        - 用户主要做肿瘤单细胞数据，常用 GRCh38 与 mm10
  │        - 偏好结果输出为中文表格 ..."
  ├── L2 触发召回：用户消息命中记忆 keywords（LIKE 匹配 ≥1 个）→ 取 top 5 注入
  └── search_memory 工具暴露给模型，供其主动深查
```

注入预算：L1+L2 合计 ≤800 tokens；`use_count`/`last_used_at` 在被注入时更新。

### 2.5 写入时机与质量控制

1. **模型自主写入（主路径）**：在 Agent 提示词中加入记忆协议（见 2.7），模型在
   对话中识别出"跨会话有价值的事实"时调 `save_memory`；
2. **会话结束自动提炼（P4）**：Celery 任务对结束会话跑 summarizer，产出
   scope=summary 记忆，置信度标 0.7（低于用户自述的 1.0）；
3. **冲突合并（P1 MVP）**：save 时在同一用户、同一 Agent 范围、同一 scope 下发现关键词重叠，
   以最新自包含陈述覆盖旧值；管理员和用户均可追溯与删除。后续 P4 再接入轻量 LLM 裁决
   （更新 / 并存 / 丢弃），避免在写入热路径增加模型依赖。

### 2.6 用户管理入口（隐私与信任刚需）

- 前端"个人中心 → 我的记忆"：列表展示（scope 徽标、内容、来源 Agent、使用时间），
  支持单条删除、一键清空、按 Agent 过滤；
- 管理端：只读审计视图（谁、何时、哪个 Agent 写了什么）；
- 策略：禁止写入密钥/密码/原始数据内容——`save_memory` 服务端做正则拦截
  （token/key/password 模式 + 长度异常拒绝），并在工具描述中明确禁令。

### 2.7 Agent 提示词记忆协议（追加到各 Agent prompt_file）

```text
## 长期记忆协议
你拥有跨会话记忆能力，遵循以下规则：
1. 当用户透露跨会话有价值的信息时（研究领域、常用数据类型、物种与参考基因组、
   分析偏好、项目进展、明确说"记住"的内容），调用 save_memory 保存，
   content 必须是一句自包含陈述（≤200 字符），不要保存本次对话的临时细节。
2. 系统提示中"用户记忆"块是历史记忆，可能过时；与当前对话冲突时以对话为准，
   并用 update_memory 修正。
3. 用户要求忘记某事时调用 forget_memory，并在回复中确认。
4. 禁止保存：任何密钥、密码、Token、原始数据内容、他人隐私信息。
5. 不要在每次回复中提及你记住了什么，除非用户主动问。
```

### 2.8 记忆系统验收标准

- [ ] 会话 A 中告知"我的单细胞数据是 10x V3 小鼠脑"，新开会话 B 问"帮我设计质控流程"，模型直接基于该背景回答且不再次追问
- [ ] 同一事实更新（GRCh37→GRCh38）后，旧记忆被替换而非并存冲突
- [ ] 用户在"我的记忆"中可看到该条记忆并可删除，删除后新会话不再注入
- [ ] save_memory 写入密钥模式内容被服务端拒绝并留审计
- [ ] 注入预算生效：L1+L2 注入不超过 800 tokens（装配层有截断日志）
- [ ] 未授权 Agent 的工具列表中不出现记忆工具

---

## 第三部分（P2）：Agent Handoff —— 轻量 A2A 协作

### 3.1 定位：router 与 MAS 之间的中间态

```text
现状：router 一次分派 → 单专家跑到底
Handoff：专家 A 在会话中判断"下一步超出我的领域" → 主动转交专家 B，
          B 带着结构化的交接上下文继续，全程在同一会话内对用户透明
MAS（P3）：复合任务预先拆解为 DAG，多节点调度执行
```

Handoff 解决 80% 的"一个问题跨两个领域"场景，成本是 MAS 的 1/5，且失败模式
简单可控（转错专家 ≈ router 选错，可再转回）。

### 3.2 转交流程

```text
用户：帮我做单细胞质控，然后做差异表达和富集分析
  │
  ▼
agent-scrna（ReAct 循环中）
  │  完成质控，产出 artifact（质控报告路径/摘要）
  │  判断：差异表达+富集属 RNA-seq/功能分析领域
  ▼
调用 transfer_to_agent({
      target_agent: "agent-rnaseq",
      reason: "质控完成，需进行差异表达与富集分析",
      handoff_summary: "已完成：10x V3 小鼠脑数据质控，过滤后 8500 细胞，
                        双细胞率 3.2%，报告在 workspace/qc/report.html",
      artifacts: ["workspace/qc/report.html", "workspace/qc/filtered.h5ad"],
      user_intent: "差异表达 + 富集分析",
      constraints: ["使用 GRCh38 注释", "样本分 4 组"]
})
  │
  ▼
ChatService 处理转交：
  ├── 校验 target_agent 存在、enabled、且在当前 Agent 的转交白名单内
  ├── 写入会话事件（type: handoff，含 from/to/reason，审计 + 前端渲染）
  ├── 重新 assemble_context(agent-rnaseq)
  ├── 构造交接消息注入新专家上下文（见 3.3 handoff packet）
  └── 继续 ReAct 循环（转交计 1 轮，单次会话最多 3 次转交防死循环）
```

### 3.3 Handoff Packet（交接上下文结构）

```text
## 会话交接（来自 agent-scrna）
- 转交原因：质控完成，需进行差异表达与富集分析
- 用户原始诉求：{user_intent}
- 已完成工作摘要：{handoff_summary}
- 相关产物（位于用户 workspace）：{artifacts[]}
- 约束与背景：{constraints[]}
请在此基础上继续，不要重复已完成的工作；如需更多细节，
可读取上述产物文件或向用户确认。
```

预算：packet ≤600 tokens；**完整消息历史不跟随转交**（新专家只看 packet +
系统注入的公共上下文），这是控制上下文膨胀的关键决策。

### 3.4 转交白名单与防环

```yaml
# data/ai/scrna.yaml 追加
handoff:
  allowed_targets: [agent-rnaseq, agent-viz, agent-code, agent-general]
  max_hops_per_session: 3
```

- 只允许显式声明的转交边，避免任意跳转；
- 服务端记录转交链（A→B→C），出现回边（B→A）时要求 reason 必须引用新信息，
  且受 max_hops 硬限制；
- 转交失败（目标不存在/未启用/超限）→ 工具返回结构化错误，模型改为告知用户
  "建议新开 xx 助手会话"，保持现有体验兜底。

### 3.5 前端转交可视化

- 消息流中插入转交卡片：`🔀 单细胞分析师 → RNA-seq 分析师｜质控完成，转交进行差异表达与富集分析`，12px 灰色、可展开查看交接摘要；
- 会话标题区的当前 Agent 标识随转交更新，历史消息仍归属原发言 Agent（头像/名称不变）；
- SSE 新增事件类型 `handoff`，字段与 3.2 会话事件一致，前端无需轮询。

### 3.6 Router 升级（配合 Handoff）

router 提示词中补充：当问题明显横跨 ≥2 个领域时，选择**第一阶段**最合适的专家，
并在决策 JSON 中标注 `"expect_handoff": true`——仅用于审计与评估统计，不改变
执行行为。路由评估集同步补充多领域样本。

### 3.7 Handoff 验收标准

- [ ] "单细胞质控→差异表达"复合请求在同一会话内完成转交，scrna 不越权做富集分析
- [ ] rnaseq 收到的上下文包含 handoff packet 且不包含 scrna 的完整消息历史
- [ ] 转交卡片在消息流正确渲染，前后消息 Agent 归属正确
- [ ] 非白名单目标转交被拒绝并有结构化错误；连续转交 3 次后第 4 次被拒绝
- [ ] 转交全链路审计可查（谁转谁、何时、reason、artifacts）
- [ ] 单领域请求行为与现状完全一致（无转交发生）

---

## 第四部分（P3）：MAS 产品化 —— 受控 DAG 协作

### 4.1 现状盘点（已有/缺失）

| 层 | 已有（复用） | 缺失（本阶段补） |
|---|---|---|
| 计划 | `mas_plan_preview`、`MASPlanValidator`、`agent_capabilities.yaml` | 面向用户的话题识别：何时该建议升级为 MAS Run |
| 执行 | Run/Node/Artifact/Approval 持久化、Celery 调度、fake/RNAFlow/火山图/quality-gate 执行器 | 更多执行器（scrna 流程、GATK 流程） |
| 通信 | A2A outbox / Redis Stream / 进度事件 | 节点间结构化产物契约（Artifact schema 注册表） |
| 前端 | 无 | **计划预览/确认 UI、Run 进度视图、节点产物下载** |
| 入口 | orchestrator 未启用 | 灰度策略：单场景开放 |

结论：产品化 80% 的工作在**前端与灰度策略**，不在引擎。

### 4.2 计划确认 UI（核心交付物）

```text
用户：帮我跑完整的 RNA-seq 差异分析（数据在 raw_data/rnaseq/）
  │
  ▼
agent-orchestrator 调 mas_plan_preview → 计划草稿
  │
  ▼
前端渲染计划卡片（非消息文本，结构化 UI）：
┌─ 分析计划（草稿，待你确认）────────────────┐
│ ① 质控 fastqc        agent-code   ~2min    │
│ ② 比对 hisat2        agent-rnaseq ~15min   │  ← 依赖 ①
│ ③ 定量 featureCounts agent-rnaseq ~5min    │  ← 依赖 ②
│ ④ 差异分析 DESeq2    agent-rnaseq ~3min    │  ← 依赖 ③
│ ⑤ 火山图+富集        agent-viz    ~3min    │  ← 依赖 ④
│                                            │
│ 预计资源：4 核 / 8GB × ~30min              │
│ [✏️ 调整计划]  [✅ 确认执行]  [取消]        │
└────────────────────────────────────────────┘
  │ 确认 → Run 状态 awaiting_approval → queued（走现有审批流）
  ▼
Run 进度视图：DAG 节点状态实时刷新（queued/running/done/failed），
  节点可展开看日志摘要与产物下载链接；失败节点支持"重试该节点"。
```

### 4.3 节点产物契约（Artifact Schema 注册表）

当前节点间产物传递靠约定，产品化前必须注册化：

```yaml
# data/ai/mas/artifact_schemas.yaml
- type: rnaseq.count_matrix
  producer: featurecounts_node
  schema: { format: tsv, rows: genes, cols: samples, requires: [sample_group_file] }
- type: qc.report
  producer: fastqc_node
  schema: { format: html, multi: true }
```

`MASPlanValidator` 校验升级：除了能力校验，增加**边校验**——节点 B 声明消费的
artifact type 必须有上游节点产出，类型不匹配在计划预览阶段就报错，而不是运行时失败。

### 4.4 灰度策略

1. **入口收敛**：MAS Run 不开放自由触发，只在 orchestrator 识别到匹配
   `agent_capabilities.yaml` 中已注册流程模板的请求时，主动建议"这是一个复合任务，
   可以为你生成多步分析计划"；
2. **首批只放 1~2 个模板**：RNA-seq 全流程（hisat2→featureCounts→DESeq2→火山图）、
   单细胞标准流程（质控→聚类→注释→marker 图）；模板即已验证的执行器组合；
3. **双闸门**：计划确认（用户）+ quality-gate 节点（自动，已有执行器）；
4. **回退**：计划生成失败/执行失败 → 无缝退回单 Agent 对话继续，Run 状态
   与原因可见。

### 4.5 MAS 产品化验收标准

- [ ] 匹配模板的复合请求触发计划建议卡片，确认后 Run 进入调度，5 节点 DAG 状态实时可见
- [ ] 边校验生效：构造一个产物类型不匹配的计划，在预览阶段即被拒绝并指出具体边
- [ ] 某节点失败后可单独重试该节点，下游节点按依赖等待
- [ ] 每个节点产物可在前端下载，路径隔离在用户 workspace
- [ ] 未匹配模板的普通对话不触发任何 MAS 行为
- [ ] 审批、调度、节点事件的审计链完整

---

## 第五部分（P4，按需）：增强项

1. **记忆向量召回**：keywords 规则召回换 embedding 检索（复用平台现有向量设施），
   会话结束自动提炼摘要记忆（Celery 任务 + summarizer prompt）；
2. **多专家会诊（Fan-out）**：router 广播给 2~3 个专家并行回答 + 汇总 Agent 整合
   （仅建议类问题开放，如"这个数据该用哪种分析方法"）；产物仍走 A2A outbox，
   不新造通道；
3. **Agent 评估体系**：路由/转交准确率、工具命中率、记忆写入质量抽检，
   回归测试集纳入 CI。

---

## 第六部分：给编码 Agent 的实施提示词（分阶段）

### 6.1 阶段一提示词：长期记忆 MVP

```text
你是一名资深全栈工程师。项目为 OmicHub 多助手平台（FastAPI + SQLAlchemy 异步 +
Vue3；Agent 架构见 data/ai/ 与 src/omichub/application/services/agent_service.py）。
先阅读 agent_service.py 的 assemble_context、tool_configs/tools_schema.yaml、
ToolBridgeService 与现有工具注册流程，理解工具 schema 注册与审计链路后再动手。

任务：实现长期记忆系统 MVP（设计见方案文档第二部分，含建表 SQL、工具定义、
召回注入逻辑、记忆协议提示词）。
1. Alembic 迁移创建 agent_memories 表（字段/索引/约束按文档 2.2）。
2. tools_schema.yaml 注册 save_memory/update_memory/forget_memory/search_memory
   四个工具（user_scoped、sync），ToolBridgeService 实现执行逻辑：写入查重转
   update、密钥模式正则拦截、单用户 500 条上限淘汰。
3. 新建 data/ai/tools/memory.yaml 工具包，仅授权给 general/scrna/rnaseq/shania。
4. assemble_context 注入 L1 常驻记忆块（≤10 条，渲染格式按文档 2.4）+
   L2 关键词触发召回（top5），L1+L2 合计 ≤800 tokens，截断记日志；
   命中时更新 use_count/last_used_at。
5. 四个 Agent 的 prompt_file 追加记忆协议（文档 2.7 原文），并通过管理端
   API 发布到数据库（PUT /api/v1/admin/agents/{id}）。
6. 前端个人中心加"我的记忆"页：列表/删除/清空/按 Agent 过滤。

## 验收
- 按文档 2.8 逐条验收，重点：跨会话记忆生效、冲突更新不并存、密钥写入被拒、
  删除后不再注入、未授权 Agent 无记忆工具。
```

### 6.2 阶段二提示词：Agent Handoff

```text
你是一名资深全栈工程师。项目为 OmicHub 多助手平台。先阅读 chat_service.py 的
stream_agent_chat 与路由逻辑、agent YAML 加载（agent_loader.py）、SSE 事件流，
理解 ReAct 循环与工具执行链路后再动手。

任务：实现 Agent Handoff 轻量协作（设计见方案文档第三部分，含转交流程图、
handoff packet 结构、白名单与防环策略）。
1. tools_schema.yaml 注册 transfer_to_agent（入参 target_agent/reason/
   handoff_summary/artifacts/user_intent/constraints）。它是**控制流工具**，工具结果不直接回灌
   当前循环，而是由 ChatService 接管执行转交；同时要为手写 ReAct 和
   `LangGraphRuntimeService` 的 `tool_executor` 增加同一份 handoff 信号协议，不能只改其中一条。
2. ChatService 转交处理：白名单校验（agent YAML 新增 handoff.allowed_targets/
   max_hops_per_session）、写会话事件（type: handoff）、重新 assemble_context、
   注入 handoff packet（≤600 tokens，完整历史不跟随）、继续 ReAct；
   回边与 hop 数限制按文档 3.4。
3. SSE 新增 handoff 事件；前端消息流渲染转交卡片（可展开摘要）、当前 Agent
   标识随转交更新、历史消息归属不变。
4. 为 scrna/rnaseq/viz/code/general 的 YAML 配置转交白名单；router 提示词
   补充 expect_handoff 标注（文档 3.6）。

## 验收
- 按文档 3.7 逐条验收，重点：同会话复合请求自动转交、packet 不含完整历史、
  非白名单拒绝、3 hop 硬限制、审计链完整、单领域请求零行为变化。
```

### 6.3 阶段三提示词：MAS 产品化灰度

```text
你是一名资深全栈工程师。项目为 OmicHub 多助手平台。先阅读 mas_service.py、
mas_scheduler_service.py、data/ai/mas/agent_capabilities.yaml、orchestrator.yaml，
理解 Plan/Run/Node/Artifact/Approval 与 Celery 调度现状后再动手。

任务：MAS 产品化灰度（设计见方案文档第四部分，含计划确认 UI 结构、Artifact
Schema 注册表、灰度策略）。
1. 新建 data/ai/mas/artifact_schemas.yaml；MASPlanValidator 增加边校验
   （下游消费的 artifact type 必须有上游产出），预览阶段报错并指出具体边。
2. 后端：先将 `agent-orchestrator` 通过受控开关纳入可用入口，并确认
   `MAS_ENABLED=true`、Celery Beat 的 outbox 发布/消费任务和目标执行器均已部署；随后让
   orchestrator 匹配流程模板时输出计划建议（结构化 SSE 事件，
   非纯文本）；Run/Node 进度 API 供前端轮询或 SSE 订阅；节点重试端点。
3. 前端：计划确认卡片（节点列表/依赖/资源预估/调整-确认-取消）、Run 进度
   视图（DAG 状态实时刷新、节点日志摘要、产物下载、失败重试）。
4. 灰度：仅 RNA-seq 全流程与单细胞标准流程两个模板开放；普通对话零影响；
   失败回退单 Agent 对话。

## 验收
- 按文档 4.5 逐条验收，重点：边校验预览期拦截、失败节点单独重试、
  产物用户隔离、非模板请求零触发。
```

---

## 第七部分：风险与回退

| 风险 | 应对 |
|---|---|
| 记忆污染（模型写入错误/低质记忆） | 写入置信度 + 用户可见可删 + 冲突合并裁决 + 抽检评估（P4 纳入评估体系） |
| 记忆泄露隐私 | user_id 强隔离贯穿所有查询；管理端只读审计；密钥正则拦截；用户一键清空 |
| Handoff 死循环/乱跳 | 白名单 + max_hops=3 硬限制 + 回边需新信息；失败兜底回单 Agent 话术 |
| 转交后上下文丢失关键信息 | packet 模板强制四要素（意图/摘要/产物/约束）；评估集覆盖复合任务回归 |
| MAS 计划质量不稳定 | 模板化灰度（只允许已验证执行器组合），不做自由规划；双闸门 |
| 注入膨胀推高 token 成本 | 记忆 ≤800 tokens、packet ≤600 tokens 硬预算，装配层截断+日志监控 |
| 各阶段相互阻塞 | 三阶段完全解耦：记忆不依赖 Handoff，Handoff 不依赖 MAS（通信层复用但接口独立），任一阶段上线其余可照旧 |

## 第八部分：实施顺序与工作量预估

| 阶段 | 内容 | 工作量 | 前置 |
|---|---|---|---|
| P1 | 长期记忆 MVP | 后端 3~4 天 + 前端 1 天 | 无 |
| P2 | Agent Handoff | 后端 3~5 天 + 前端 1~2 天 | 无（与 P1 可并行） |
| P3 | MAS 产品化灰度 | 前端 4~5 天 + 后端 2~3 天 | 建议 P2 稳定后 |
| P4 | 向量召回/会诊/评估 | 按需 | P1/P2 上线后 |

推荐排期：P1 与 P2 并行启动（不同模块无冲突），P3 在 P2 灰度稳定一周后启动。
