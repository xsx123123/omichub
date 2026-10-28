# AgentTeams 非侵入式多 Agent 协作编排实施方案

> **文档状态**：实施中（Bridge、OmicHub 代理、AI 资源中心配置、协作中心与受控 Agent Gateway 代码已落地；真实 AgentTeams/HiClaw 控制面及 Gateway 对 OmicHub 专业 Agent 受控端点的联调待完成）
> **创建日期**：2026-07-30
> **适用目标**：以 AgentTeams 替换“谁来组织多个 Agent 协作”的外层控制面；不替换 OmicHub 的既有聊天、任务、流程、数据、权限与执行逻辑。
> **推荐落地方式**：AgentTeams 独立部署 + OmicHub Bridge（适配服务）+ OmicHub 既有 API/MCP 能力。

---

## 实施状态（2026-08-01）

已落地且已通过定向契约/类型验证的仓库内实现：

- 独立 `omichub-agentteams-bridge`：Case 状态机、Work Item 分派与回写、短期审批令牌、任务幂等、取消、质量门禁、审计 JSONL、指标与 `delivery_manifest.json`；每个 Worker 可通过仅返回自身待办的 `/v1/work-items/assigned` 收件箱发现任务，必须以身份绑定的原子 claim 领取后再执行，不能扫描所有 Case 或由多副本重复消费；Manager 对账只在观察到 OmicHub 任务成功后将 Case 推进为 `quality_running` 并幂等分派 Quality Auditor，质量结论通过后再分派 Delivery Reporter；预检通过后会保存 Bridge 自有的输入快照，审批提交只能使用与该快照完全一致的流程、样本表和分组对比；
- OmicHub 的受控 `/api/v1/agent-teams` 代理：浏览器不接触 Bridge 凭证，Case 读取按当前登录用户的 `requester_ref` 过滤，且不会得到内部预检输入快照或原始任务规格；新建 Case 时由后端以独立 Data Steward 身份分派并执行只读 `project-preflight`，样本表不通过则阻断、通过则进入 `approval_pending`；Case 所有者确认后只可命名任务，后端以独立审批机关签发短期令牌，并以 Workflow Operator 身份用已通过预检的快照提交任务，令牌与 Worker 凭证均不返回浏览器；
- `/agent-teams` 协作中心与 Case 详情页：展示真实 Case、Work Item、状态轨、审计时间线、任务/质量/manifest 证据与角色化下一步指引；状态接口会真实探测 Bridge 健康而非只检查配置，列表支持状态/项目筛选和游标分页，详情页仅在浏览器页面可见时每 20 秒增量轮询 Bridge 事件，并在执行阶段调用受控对账接口以生成下一角色待办；
- 聊天式 Case 发起与内嵌审批卡片：用户先在“协作对话”中填写目标、项目和样本上下文，整理为可审阅的 Case 草案后才创建并进入只读预检；预检通过后，详情页会展示执行者、固定输入、真实计算动作和审计范围，用户必须在提交弹窗中二次勾选，后端才会以审批机关与 Workflow Operator 身份提交任务；
- AI 资源中心的 `AgentTeams` 管理页：管理员可配置 Bridge 地址、超时和四个身份令牌，页面显示真实连通状态；令牌以加密形式持久化、读取时脱敏，保存/启用/切换地址均要求 TOTP 二次验证。运行时优先读取此数据库配置，尚未保存时才回退到服务端环境变量；
- 独立 `deploy/agentteams/` Compose、Bridge 环境模板、占位密钥/身份检查的 `preflight.py`、独立控制面默认拒绝网络策略和只读 `verify_control_plane.py` 部署验收门禁；
- `integrations/agentteams/demo/` 可重复演示驱动：默认只执行成功/阻断预检，完整工作流仅在显式 staging 审批开关和真实 demo 任务下执行。

2026-08-01 的本地验收已完成：Bridge 契约测试、Worker claim 适配器测试、OmicHub AgentTeams 代理/API Key scope/模块注册测试、独立控制面/Compose 覆盖测试和前端 AgentTeams 状态单测共 46 项通过；Bridge/Demo/部署预检 Ruff 检查与格式检查、前端 `vue-tsc --noEmit` 与生产构建，以及 Bridge 与 OmicHub 可选网络覆盖的 Compose 配置渲染均通过。生产模式和部署预检都会拒绝空值、`change-me-*` 和 `replace-with-*` 的 Bridge/Manager 凭证，防止模板值被误部署；Bridge 对请求与响应都设有 1 MiB 默认上限，宿主健康端口默认只绑定回环地址，并具备容器健康检查。

本轮新增的 AI 资源中心配置能力已通过前端 `vue-tsc --noEmit` 与生产构建、相关 Ruff 检查、`AgentTeamsBridgeSettingsService` 与 `AgentTeamsService` 的 14 项聚焦测试；Alembic 迁移已合并为唯一 head `q5r6s7t8u9v0`。这证明配置持久化、环境变量回退、凭证脱敏与启用校验可用，但不证明真实外部 Controller/Worker 或专业 Agent Gateway 已部署。

尚未宣称上线的内容：真实 AgentTeams/HiClaw Controller、Matrix、MinIO、Higress 资源尚需按目标版本官方 Schema 在独立环境部署，并注入生产凭证后做真实跨服务演示；受控 Gateway 已实现 `scientific-interpretation` REST 契约、专业 Agent/只读工具白名单、固定输出 Schema、成本护栏和 JSONL 审计，但 **尚未与 OmicHub 专业 Agent 的受控咨询端点完成真实联调**。当前闭环只调用确定性的预检/流程/任务 API。OmicHub 的 Celery、Snakemake、MAS DAG、ChatService 与领域数据保持不变。

本机开发环境已启动独立 Bridge，并通过 OmicHub 浏览器代理回读真实 Case：一条缺少样本表的预检进入 `preflight_blocked`，一条完整样本表预检进入 `approval_pending`；另已验证从 OmicHub 创建 API 自动分派 Data Steward 并完成完整样本表预检。对阻断 Case 调用受控提交 API 会明确返回拒绝，且未创建计算任务。所有这些验证均未提交计算任务。该验证只证明 OmicHub → Bridge 的 Case/预检/审批提交门禁链路已接通，不等同于真实 AgentTeams/HiClaw Controller、Matrix、MinIO 或 Higress 已部署，也不替代生产服务令牌、人工审批和真实 Worker 的联调验收。

---

## 1. 结论与边界

### 1.1 一句话结论

本方案不是把 OmicHub 迁移到 AgentTeams，也不是把 AgentTeams 接入后替换 Celery、Snakemake 或现有专业分析 Agent。

本方案只替换以下职责：

> **复杂企业任务到多个职能 Agent 的任务拆解、协作通信、共享上下文、状态汇总、审批协调与协作证据组织。**

AgentTeams 的 Manager/Team Leader 负责上述外层协作；OmicHub 继续是受控的多组学业务与计算执行平台。

### 1.1.1 最终目标链路与当前阶段

最终要交付的不是另一套替代 OmicHub 的专业 Agent，而是让 AgentTeams 成为外层协作控制面，**受控复用现有 OmicHub 专业 Agent**：

```text
聊天 / Case
  → AgentTeams Manager
  → 受控 Agent Gateway
  → 现有 OmicHub 专业 Agent
  → 结构化科学解读 / 建议 / 证据
  → 人工审批
  → Workflow Operator
  → OmicHub Flow / Task API
  → Celery / Snakemake / 产物与交付证据
```

其中“受控”有明确含义：

1. AgentTeams Manager 只能调用 Gateway 暴露的白名单专业能力，不能直接导入内部 Python 类、直连数据库或读取用户工作区；
2. 专业 Agent 被 AgentTeams 调用时默认只执行**解释、计划建议、结果解读和质控建议**，不自行提交任务、不自行扩展执行范围；
3. Gateway 返回固定 Schema 的结论、建议、证据引用和风险项，而不是将内部会话、工具调用记录或原始文件返回给 AgentTeams；
4. 涉及真实计算、取消、导出、共享或对外交付的动作，必须经过 Case 审批，再由 Workflow Operator 使用短期审批令牌调用确定性 OmicHub API；
5. 当前实现已完成“Case → 预检 → 人工审批 → Workflow Operator → OmicHub Flow / Task API”链路，**尚未实现“Manager → 受控 Agent Gateway → 现有专业 Agent”链路**。

### 1.2 保持不变的 OmicHub 能力

以下模块不做替换、不修改业务语义，也不迁移数据：

| 模块 | 现有职责 | 本方案处理方式 |
|---|---|---|
| `ChatService` | 普通聊天、路由、Agent Handoff、SSE | 保持原样；后续由受控 Gateway 适配专业 Agent 调用，而非由 AgentTeams 直接侵入其运行时 |
| LangGraph runtime | 单 Agent ReAct、工具调用循环 | 保持原样；不由 AgentTeams 改写 |
| MAS DAG | 已批准分析计划的节点依赖、状态迁移、Celery 派发 | 继续作为分析任务执行编排层 |
| Celery | 异步任务与计算 Worker 调度 | 保持原样 |
| Snakemake / RNAFlow / ATACFlow | 真正的分析流程执行 | 保持原样 |
| Studio Sandbox | 受控代码、终端与分析环境 | 保持原样 |
| OmicHub 用户、项目、文件、报告、任务数据库 | 领域数据与权限事实来源 | 保持原样；不复制到 AgentTeams |
| 既有 Agent 配置 | RNA-seq、单细胞、可视化等专业能力 | 保持原样；通过受控 Gateway 作为 Manager 可请求的下游专业能力 |

现有接口边界可从以下位置确认：

- Agent 运行基线：`ARCHITECTURE_DESIN/agent_framework_final_baseline.md`
- 多 Agent 当前能力与限制：`ARCHITECTURE_DESIN/multi-agent.md`
- 任务 API：`src/omichub/api/v1/tasks.py`
- 流程 API：`src/omichub/api/v1/flows.py`
- MAS API：`src/omichub/api/v1/mas.py`
- AgentTeams 的协作控制面应位于 OmicHub 之外；不得绕过这些服务直接操作数据库或宿主机工作目录。

### 1.3 AgentTeams 接管的职责

| 协作职责 | 当前 OmicHub 入口 | 接入后由谁主责 |
|---|---|---|
| 接收复杂 BioOps/交付任务 | 聊天或业务页面 | AgentTeams Manager |
| 将任务分解为不同职能工作项 | `agent-orchestrator` / 人工 | AgentTeams Manager / Team Leader |
| 多角色间的协作消息和上下文 | Handoff、MAS context、聊天记录 | AgentTeams Team / Matrix Room |
| 选择哪个 Worker 负责哪一步 | 既有提示词或人工 | AgentTeams Manager |
| 高风险动作前的人机协调 | MAS approval / 前端确认 | AgentTeams 发起审批；OmicHub 保留执行前最终校验 |
| 多 Agent 协作 Trace、过程证据索引 | 现有日志分散在多个模块 | AgentTeams 协作轨迹 + Bridge 审计事件 |
| 真正执行分析、取消任务、生成报告 | OmicHub | **仍由 OmicHub** |

---

## 2. 为什么采用“旁路控制面”而不是直接替换

### 2.1 当前系统已有两类不同的“调度”

OmicHub 里“调度”至少有两层，不能混为一谈：

1. **协作调度（认知与决策层）**
   - 理解业务任务；
   - 分派数据核验、执行、质控、报告等角色；
   - 协调上下文与人工确认；
   - 汇总多个角色的中间结论。

2. **计算调度（确定性执行层）**
   - 按 DAG 依赖释放节点；
   - 提交 Celery；
   - 启动 Snakemake；
   - 管理重试、状态和产物。

AgentTeams 适合第一层；OmicHub 的 MAS、Celery 和 Snakemake 适合第二层。

### 2.2 直接替换的代价与风险

若让 AgentTeams 直接取代 MAS、Celery 或 TaskService，会产生以下问题：

- 需要重写当前任务状态机、幂等控制、任务归属与数据库投影；
- 需要迁移或重新验证流程参数校验、工作区路径隔离、工具策略；
- 容易让 Worker 获取数据库、Docker Socket 或主机目录的过高权限；
- 会破坏已经可运行的 OmicHub 前端任务页、日志页和报告页；
- 竞赛项目会同时承担“业务平台重构”和“多 Agent 基础设施”两类高风险工作。

因此本方案严格遵守：

```text
AgentTeams 负责“决定和协作”
OmicHub 负责“校验、执行、记录和交付”
```

---

## 3. 目标场景：BioOps 多组学分析交付闭环

### 3.1 推荐场景

**场景名称**：面向测序服务、育种研发或科研公共平台的多组学分析交付与运行治理。

典型输入是一个 RNA-seq 或 ATAC-seq 分析需求，其中可能存在：

- 样本表缺列、分组不完整、FASTQ 命名不一致；
- 物种、参考基因组、链特异性或比较组选择错误；
- 高计算成本任务需项目负责人确认；
- 流程执行失败，需区分数据、配置、资源与工具问题；
- QC 不达标，不能直接进入正式交付；
- 交付时需要保留参数、版本、日志、质量结论及审批记录。

### 3.2 必须跑通的演示闭环

```text
任务提交
  → 数据预检
  → 计划生成
  → 人工审批
  → OmicHub 提交工作流
  → 任务执行与状态回传
  → 质量门禁
  → 报告和审计包
  → 经验/Runbook 沉淀
```

至少准备两条可验证路径：

- **成功路径**：合法 RNA-seq 示例从预检到报告完成；
- **异常路径**：故意使用错误样本表、无效参数或低质控数据，触发阻断、说明原因，并展示修正后恢复执行。

---

## 4. 总体架构

### 4.1 逻辑架构

```text
┌───────────────────────────────────────────────────────────────┐
│ AgentTeams 控制面（新增、独立部署）                              │
│                                                               │
│  用户 / Element Room                                           │
│        │                                                      │
│        ▼                                                      │
│  BioOps Manager / Team Leader                                 │
│   ├── Data Steward Worker                                     │
│   ├── Workflow Operator Worker                                │
│   ├── Quality Auditor Worker                                  │
│   └── Delivery Reporter Worker                                │
│        │                                                      │
│        │ 仅调用受限 Skill                                      │
└────────┼──────────────────────────────────────────────────────┘
         │ HTTPS 或 MCP（服务账号、最小权限、可审计）
         ▼
┌─────────────────────────────┐   ┌─────────────────────────────┐
│ OmicHub Bridge               │   │ 受控 Agent Gateway（待实现） │
│（新增、无状态适配服务）        │   │ - 专业能力白名单与只读工具策略 │
│ - 身份映射与短期令牌           │   │ - 固定 Schema 结论/建议/证据  │
│ - 输入 Schema 校验与幂等键     │   │ - 超时与调用次数/token 护栏   │
│ - 任务状态归一化与轮询         │   │ - 审计事件 agent.consultation │
│ - 审批凭证校验                │   └────────────┼────────────────┘
│ - 审计事件写出                │                │ 只读白名单
└────────────┼────────────────┘                │（禁止提交/取消/写文件）
             │                                 ▼
             │                    ┌─────────────────────────────┐
             │                    │ OmicHub 专业 Agent（既有）    │
             │                    │ agent-rnaseq / agent-scrna / │
             │                    │ agent-viz ...                │
             │                    │（科学解读 / 建议 / 证据引用） │
             │                    └─────────────────────────────┘
             │ 仅通过既有 OmicHub HTTP API / 已授权 MCP
             ▼
┌───────────────────────────────────────────────────────────────┐
│ OmicHub（既有系统，不改变领域逻辑）                             │
│ FlowService → TaskService / MASService → Celery → Snakemake   │
│ 文件 / 项目 / 报告 / 日志 / Sandbox / RBAC                     │
└───────────────────────────────────────────────────────────────┘
```

### 4.2 网络与数据边界

| 区域 | 可访问资源 | 禁止事项 |
|---|---|---|
| AgentTeams Manager/Worker | AgentTeams 自身控制面、Bridge、协作房间 | 不可直连 OmicHub PostgreSQL、Redis、Docker Socket、`/data/omichub` |
| OmicHub Bridge | OmicHub API、审计后端、受控凭证 | 不可挂载 OmicHub 真实用户数据根目录；不可执行 Snakemake |
| 受控 Agent Gateway | OmicHub 专业 Agent 的只读白名单能力（科学解读/建议/证据引用）、ChatService 的受控调用入口 | 不可提交/取消任务、不可写用户工作区与文件、不可直连数据库、不可向 AgentTeams 返回原始会话/工具调用记录/原始文件 |
| OmicHub Worker | 现有工作区、流程、参考数据、Celery | 不接受来自 AgentTeams 的任意 shell 命令 |
| Matrix / 对象存储 | 小型任务说明、审计摘要、报告索引 | 不复制 FASTQ/BAM/参考基因组等大文件 |

**文件原则**：AgentTeams 只传递 `project_id`、`file_id`、任务 ID、产物 ID、manifest、摘要和签名 URL；真实组学文件始终驻留 OmicHub。

---

## 5. 角色与 Agent Identity 清单

### 5.1 最小可参赛 Team（4 个 Worker + 1 个 Manager）

| Identity | 类型 | 职责 | 可调用 Skill | 禁止权限 | 主要输出 |
|---|---|---|---|---|---|
| `bioops-manager` | Manager / Team Leader | 解析需求、拆解工作项、派发、汇总、审批协调 | `task-intake`, `approval-request`, `case-closeout` | 不提交计算任务、不读原始大文件 | `case_plan.json` |
| `data-steward` | Worker | 样本、元数据、流程参数的预检 | `project-preflight`, `evidence-retrieval` | 不执行流程、不修改用户文件 | `preflight_report.json` |
| `workflow-operator` | Worker | 准备、提交、监控、取消既有 OmicHub 工作流 | `workflow-submit`, `workflow-monitor`, `workflow-cancel` | 不绕过审批、不改流程 YAML | `execution_receipt.json` |
| `quality-auditor` | Worker | QC/产物完整性/运行状态验证 | `quality-gate`, `artifact-inspect` | 不提交任务、不删除产物 | `quality_decision.json` |
| `delivery-reporter` | Worker | 汇总执行证据、生成交付与复盘草稿 | `delivery-pack`, `runbook-capture` | 不执行高风险动作 | `delivery_manifest.json` |

### 5.2 不和现有 OmicHub Agent 重名或抢职责

现有 `agent-rnaseq`、`agent-scrna`、`agent-viz` 等是面向用户的专业分析角色；本方案新增的 Worker 是企业交付场景的操作角色。

两者关系如下：

```text
AgentTeams Workflow Operator
   └─ Bridge 调用 OmicHub 的确定性流程 API

AgentTeams Manager
   └─ 受控 Agent Gateway
       └─ 现有 OmicHub 专业 Agent（agent-rnaseq / agent-scrna / agent-viz ...）
           └─ 结构化科学解读、建议与证据引用
```

当前阶段已完成第二条链路的 Gateway 侧代码实现：只读 `scientific-interpretation` Skill 允许 Manager 请求专业摘要，同时禁止专业 Agent 自行提交任务、修改样本表、写入用户文件或再次编排同一 Case。Gateway 对 OmicHub 专业 Agent 受控咨询端点的真实联调仍待完成；在此之前不得将该链路宣称为已部署或已上线。这样既复用现有知识与会话能力，又避免两个编排器对同一任务独立拆解。

---

## 6. 协作状态、上下文与消息协议

### 6.1 Case 是跨系统关联根

每一个 AgentTeams 协作任务创建一个 `case_id`。它不是 OmicHub 的任务 ID，也不替代 `MASRun.id`；它只负责关联多个系统的证据。

```json
{
  "case_id": "bioops_20260730_001",
  "requester": {"omic_user_id": "<uuid>", "display_name": "researcher-a"},
  "project_ref": {"project_id": "<uuid>", "workspace_id": "<uuid>"},
  "intent": "bulk_rnaseq_delivery",
  "status": "preflight_pending",
  "correlation": {
    "agentteams_team_id": "bioops-delivery",
    "matrix_room_id": "!room:example.org",
    "omic_task_ids": [],
    "mas_run_ids": []
  },
  "created_at": "2026-07-30T10:00:00Z"
}
```

### 6.2 共享状态只放事实，不放长 Prompt

共享状态分为四类：

| 类型 | 示例 | 存储建议 | 规则 |
|---|---|---|---|
| 任务事实 | `flow_id`、样本数、任务状态 | Bridge 状态库或 AgentTeams 状态 | 可结构化更新 |
| 决策证据 | 预检错误、QC 阈值、日志片段 | OmicHub 产物/Bridge 审计索引 | 必须带来源 |
| 协作结论 | “阻断，需补 comparison” | Matrix/AgentTeams 消息 + 状态摘要 | 必须带角色与时间 |
| 大文件引用 | FASTQ、BAM、报告 HTML | OmicHub 文件 ID 或下载链接 | 禁止在协作房间复制 |

不可将数据库连接串、API Key、JWT、用户隐私原始数据、完整 FASTQ/BAM 内容写入 Matrix 房间或 Worker prompt。

### 6.3 Worker 输入输出包络

所有 Worker 使用同一输入输出包络，避免自由文本造成状态漂移。

```json
{
  "schema_version": "1.0",
  "case_id": "bioops_20260730_001",
  "work_item_id": "preflight-01",
  "parent_work_item_id": null,
  "actor": "bioops-manager",
  "target": "data-steward",
  "objective": "校验 RNA-seq 项目是否满足提交条件",
  "context_refs": [
    {"kind": "project", "id": "<uuid>"},
    {"kind": "flow", "id": "rna_seq"},
    {"kind": "file", "id": "<uuid>"}
  ],
  "constraints": {
    "read_only": true,
    "approval_required": false,
    "deadline_seconds": 300
  }
}
```

Worker 输出：

```json
{
  "schema_version": "1.0",
  "case_id": "bioops_20260730_001",
  "work_item_id": "preflight-01",
  "status": "blocked",
  "summary": "样本表缺少 comparison 所需的 group 信息。",
  "findings": [
    {
      "code": "MISSING_GROUP",
      "severity": "error",
      "message": "样本 S03 未设置 group",
      "evidence_refs": [{"kind": "file", "id": "<uuid>", "location": "row:4"}]
    }
  ],
  "next_actions": ["request_user_correction"],
  "artifacts": [
    {"kind": "preflight_report", "uri": "omic://artifacts/<id>", "sha256": "..."}
  ],
  "produced_by": "data-steward",
  "produced_at": "2026-07-30T10:03:00Z"
}
```

---

## 7. Skill 设计与 OmicHub Bridge 契约

### 7.1 Skill 分层原则

- **Skill 是可复用业务能力**：例如“执行前预检”“提交工作流”“质量门禁”。
- **Bridge 工具是稳定连接能力**：例如 `GET /flows/{id}`、`POST /tasks`。
- **Agent 是判断何时调用 Skill、如何处理失败和如何与其他角色协作的主体**。
- 不将一次性的自然语言步骤错误命名为 Skill。

### 7.2 核心 Skill 清单

| Skill | 输入 | 输出 | 调用条件 | 失败处理 | 安全边界 |
|---|---|---|---|---|---|
| `project-preflight` | 项目/文件/流程引用 | 预检报告、阻断项、建议 | 收到新分析需求 | 返回 `blocked`，不提交任务 | 只读 |
| `workflow-submit` | 已通过预检的执行规格、审批凭证 | OmicHub task ID、执行回执 | 预检通过且审批通过 | 幂等重试；参数错误转回预检 | 仅允许白名单 flow |
| `workflow-monitor` | task ID | 统一状态、进度、关键日志 | 任务非终态 | 超时告警；不自动扩大资源 | 只读 |
| `workflow-cancel` | task ID、原因、审批凭证 | 取消回执 | 高风险/异常或人工终止 | 幂等；保存取消原因 | 仅特定角色 |
| `quality-gate` | task ID、产物引用、规则版本 | 通过/警告/阻断、证据 | 任务完成或关键阶段结束 | 规则缺失则 `manual_review` | 只读 |
| `delivery-pack` | case、任务与质量结论 | manifest、报告索引、复盘草稿 | 质量通过或人工豁免 | 缺产物时阻断交付 | 只写证据包 |
| `scientific-interpretation`（Gateway 代码已实现，专业端点联调待完成） | Case 摘要、问题、已授权任务/产物引用、目标专业角色 | 固定 Schema 的结论、建议、证据引用、风险项 | Manager 需要专业规划、结果解释或 QC 建议 | 返回 `manual_review`，不降级为自动执行 | Gateway 白名单、只读、无任务提交权限；单次调用超时 + 每 Case 调用次数与 token 成本上限 |
| `runbook-capture` | 异常/恢复结果 | 去标识化经验条目 | case 关闭 | 审核后发布 | 禁止写密钥/PII |

### 7.3 Bridge 的最小 API

Bridge 是新服务；首期实现 REST 即可。若后续用 MCP，只把下表中的操作封装成同名 Tool，不修改 Skill 语义。

| Bridge 路由 | 方法 | 作用 | 映射的既有 OmicHub 能力 |
|---|---|---|---|
| `/v1/flows` | `GET` | 获取可用流程及参数 Schema | `GET /api/v1/flows`、`GET /api/v1/flows/{flow_id}/schema` |
| `/v1/projects/{id}/preflight` | `POST` | 读取项目元数据并执行预检 | 文件/项目 API + 纯 Bridge 校验 |
| `/v1/tasks` | `POST` | 带审批凭证提交任务 | `POST /api/v1/tasks` |
| `/v1/tasks/{id}` | `GET` | 获取任务状态 | `GET /api/v1/tasks/{id}` |
| `/v1/tasks/{id}/events` | `GET` | 标准化轮询或 SSE 事件 | `GET /api/v1/tasks/{id}`、日志/WS |
| `/v1/tasks/{id}/cancel` | `POST` | 取消任务 | `POST /api/v1/tasks/{id}/cancel` |
| `/v1/tasks/{id}/artifacts` | `GET` | 获取受限产物逻辑引用 | 从既有 `GET /api/v1/tasks/{id}` 的成功状态推导 `omic://tasks/{id}/result`；不暴露宿主路径、不列目录 |
| `/v1/tasks/{id}/quality-gate` | `POST` | 调用既有/新增质量规则 | 既有产物 + 规则实现 |
| `/v1/cases/{case_id}/evidence` | `POST` | 写入 Bridge 审计索引 | **新增，Bridge 自身存储** |

### 7.4 `workflow-submit` 请求契约

```json
{
  "case_id": "bioops_20260730_001",
  "idempotency_key": "case-001-submit-rna-v1",
  "approval_token": "opaque-short-lived-token",
  "task": {
    "flow_id": "rna_seq",
    "name": "salt-stress-rna-seq-v1",
    "parameters": {"Genome_Version": "ITAG4.1"},
    "sample_sheet": [{"sample": "S01", "group": "control"}],
    "comparisons": [{"control": "control", "treatment": "salt"}],
    "execution_mode": "local"
  }
}
```

Bridge 必须：

1. 检查调用者角色是否为 `workflow-operator`；
2. 验证 `approval_token` 对应相同 `case_id`、相同 flow 和未过期；
3. 检查 `idempotency_key` 是否已提交过；
4. 将请求转换为既有 `TaskSubmitRequest`；
5. 使用映射后的 OmicHub 用户身份调用 `POST /api/v1/tasks`；
6. 将 OmicHub `task_id` 与 `case_id` 写入 Bridge 审计索引；
7. 返回稳定的结构化回执。

OmicHub 现有任务提交 DTO 为 `TaskSubmitRequest`，字段包括 `flow_id`、`name`、`parameters`、`sample_sheet`、`comparisons` 和 `execution_mode`；Bridge 不自行发明第二套任务语义。

---

## 8. 状态机、审批与回滚

### 8.1 Case 状态机

```text
received
  → preflight_running
  → preflight_blocked ──→ waiting_for_correction ──┐
  │                                                │
  └→ approval_pending → approved → executing → quality_running
                                      │                 │
                                      │                 ├→ delivery_ready → closed
                                      │                 └→ quality_blocked → remediation_pending
                                      │                                      │
                                      └→ execution_failed ───────────────────┘

任一非终态 → cancelled
```

AgentTeams 维护协作 Case 状态；OmicHub 维护真实任务状态。二者通过 `case_id ↔ task_id` 关联，不相互覆盖。

### 8.2 高风险动作清单

| 动作 | 是否自动允许 | 需要谁审批 | 回滚/补救 |
|---|---:|---|---|
| 读取流程 Schema、任务状态、日志 | 是 | 无 | 不适用 |
| 执行预检 | 是 | 无 | 不适用 |
| 提交正式计算任务 | 否 | 项目负责人/用户 | 提交后可取消未结束任务 |
| 重新提交同一任务 | 否 | 用户或预设策略 | 使用新 idempotency key，保留旧任务证据 |
| 取消正在运行任务 | 否 | 用户；严重资源风险可由管理员 | OmicHub `cancel_task`，保留日志 |
| 删除文件/报告 | 否 | 仅 OmicHub 原有权限机制 | 不允许 AgentTeams Worker 直接调用 |
| 发布 Runbook/知识条目 | 否 | 管理员或责任人审核 | 版本化撤回 |

### 8.3 双重保护

审批不能只依赖 AgentTeams 文本消息，必须至少具备两层保护：

1. AgentTeams/Matrix 中显示清晰的审批卡：任务、成本/影响、参数摘要、有效期；
2. Bridge 只接受带 `case_id`、动作范围、有效期、签名的短期 `approval_token`；
3. Bridge 在调用 OmicHub 前再次校验；
4. OmicHub 继续按已有用户身份、RBAC 和任务校验执行。

如果审批链失效，Bridge 必须返回 `approval_required`，不能降级为自动提交。

---

## 9. 可观测、审计与证据包

### 9.1 Trace 关联字段

所有 AgentTeams、Bridge 与 OmicHub 事件至少带：

```text
case_id
work_item_id
agentteams_team_id
matrix_room_id（如有）
omic_user_id（最小化/脱敏）
omic_task_id（如有）
mas_run_id（如有）
agent_identity
skill_name + skill_version
bridge_operation
approval_id（如有）
trace_id / parent_span_id（如可用）
```

### 9.2 事件类型

| 事件 | 产生方 | 必备证据 |
|---|---|---|
| `case.created` | Manager | 原始需求摘要、发起者、边界 |
| `work_item.assigned` | Manager | 角色、目标、上下文引用 |
| `skill.started/finished/failed` | Worker/Bridge | 输入摘要、输出摘要、耗时、错误码 |
| `approval.requested/resolved` | Manager/Bridge | 风险说明、审批人、决定、有效期 |
| `omic_task.submitted/status_changed/cancelled` | Bridge | task ID、状态、关键日志引用 |
| `quality.decision` | Quality Auditor | 规则版本、结论、证据引用 |
| `agent.consultation` | 受控 Agent Gateway | 目标专业角色、问题摘要、结论 Schema 版本、耗时与 token 成本、证据引用 |
| `case.closed` | Delivery Reporter | 交付 manifest、复盘引用 |

### 9.3 证据包内容

每个关闭的 Case 生成一个 `delivery_manifest.json`，至少包含：

- Case 和任务的关联 ID；
- Agent Identity 清单和 Skill 版本；
- 输入数据引用及权限摘要；
- 流程版本、参数、运行模式；
- 审批/取消/重试记录；
- OmicHub 任务最终状态、日志摘要和产物哈希；
- QC/质量门禁结论与规则版本；
- 异常分支与恢复处理；
- Runbook 草稿或经验条目引用。

现有 OmicHub 任务日志、工作流日志及产物继续是计算执行的权威证据；Bridge 只补充“谁在何时做了什么协作/调用”的跨系统索引。

---

## 10. 部署方案

### 10.1 Compose 拆分原则

不要将 AgentTeams 基础设施混入 OmicHub 主 Compose 文件。建议新增独立编排：

```text
deploy/agentteams/
├── docker-compose.agentteams.yml
├── .env.agentteams.example
├── bridge.env.example
└── README.md
```

它与现有 `deploy/docker/docker-compose.yml` 并列运行，仅通过专用内网/网关访问 Bridge。

### 10.2 最小服务集

| 服务 | 归属 | 说明 |
|---|---|---|
| AgentTeams Controller / Manager / Worker | AgentTeams | 协作控制面与角色执行 |
| Matrix / Element | AgentTeams | 协作通信与人工审批展示 |
| MinIO | AgentTeams | 小型共享文档、不可存组学大文件 |
| Higress（可选但推荐） | AgentTeams 侧 | 模型、MCP/Bridge 统一鉴权、路由、限流与观测 |
| `omichub-agentteams-bridge` | 新增 | 与 OmicHub API 的唯一集成点 |
| OmicHub 主栈和 Worker 栈 | 既有 | 不改变 |

### 10.3 凭证和鉴权

- 每个 Worker 使用不同的 Bridge service identity；不得共享 OmicHub 管理员 JWT。
- Bridge 通过短期 OAuth/JWT 或签名请求映射到受限 OmicHub 用户/服务账户。
- Bridge 仅允许固定的 HTTP 方法、路径、flow ID 和参数 Schema；所有请求都设置超时与速率上限。
- 密钥存放在 AgentTeams/网关密钥管理中，不写入 Team、Worker、Skill 或 Matrix 消息配置。
- 比赛 Demo 可以使用单个“演示用户 + 演示项目”，但仍必须展示角色最小权限与动作白名单。

### 10.4 大文件与网络策略

- 不通过 Matrix/MinIO 传 FASTQ、BAM、reference、完整 workflow 目录；
- Worker 只持有 OmicHub 的文件引用；
- Bridge 最大请求体和返回体均应设限；长日志用分页或摘要；
- Bridge 到 OmicHub 使用内网 TLS、服务发现或固定网关地址；
- AgentTeams Worker 默认无出网权限，只有确有必要的检索 Worker 单独放行。

### 10.5 部署前置检查与演示顺序

在独立环境部署前，先对实际受管环境文件执行 `python3 deploy/agentteams/preflight.py --bridge-env <bridge.env> --omichub-env <.env>`。该检查必须通过后才能启动 Bridge；Bridge 启动后再以 `--check-health --bridge-url <url>` 做只读健康探测。随后按 `integrations/agentteams/demo/README.md` 先运行不提交计算的预检成功/阻断路径，最后才在 staging 中以显式 `--allow-automated-demo-approval` 和真实 demo 任务运行完整闭环。生产演示不得将该 staging 自动审批开关替代真实人工审批卡。

---

## 11. 前端实施方案：Agent 协作中心

### 11.1 页面定位与命名

新增一级业务页面名称：**Agent 协作中心**。

它是面向用户、项目负责人和交付人员的 Case 协作工作台，用于发起、观察、审批和复核一个真实多 Agent 协作闭环；它不是普通问答页面、不是既有 AI 助手的第二套皮肤，也不是 OmicHub 任务中心的替代品。

页面只负责展示和操作 AgentTeams 的协作控制面及 Bridge 的 Case 资源：

```text
AI 助手（/ai）
  └─ 单 Agent 对话、路由、专业咨询、轻量 Handoff

AI 工作台（/studio/:sessionId）
  └─ 单个 Studio 会话中的文件、代码、终端和产物协作

Agent 协作中心（/agent-teams）【新增】
  └─ 多 Agent Case：任务拆解、角色协作、审批、跨系统执行证据

任务中心（/tasks）
  └─ OmicHub 真实计算任务、日志、进度和结果
```

前端不是“多头像聊天 UI”。页面上每一条角色状态、Skill 调用、审批与任务进度都必须由 AgentTeams/Bridge/OmicHub 的真实状态驱动；在后端尚未接通前只能以明确标记的 Mock/演示数据呈现，不能伪装成已执行任务。

### 11.2 现有前端基线与复用决策

本节的实现必须遵循：

- 前端设计规范：`ARCHITECTURE_DESIN/fontend.md`；
- 设计令牌：`frontend/src/styles/tokens.css`、`frontend/src/styles/global.css`；
- 主导航和移动端框架：`frontend/src/layouts/DefaultLayout.vue`；
- 既有 AI 助手工作区：`frontend/src/views/AIChatView.vue`、`frontend/src/components/agent-workspace/AgentWorkspace.vue`；
- 既有 AI 工作台：`frontend/src/views/StudioView.vue`；
- 审批、MAS 进度、任务进度呈现模式：`frontend/src/components/ai-chat/ApprovalCard.vue`、`frontend/src/components/ai-chat/MasRunProgressCard.vue`、`frontend/src/components/ai-chat/TaskProgressCard.vue`。

复用与避免复用的原则如下：

| 现有模式 | 是否复用 | 在协作中心中的用途 |
|---|---:|---|
| `PageHeader` 与 `.page-container` | 是 | 标准工作台页头、操作区、全宽内容区 |
| Naive UI `NCard`/`NButton`/`NTag`/`NDrawer`/`NDataTable` | 是 | 一致的业务卡片、操作、状态与移动端抽屉 |
| `ApprovalCard` 的信息结构 | 是，重构为独立域组件 | 显示真实审批原因、影响、有效期和决定 |
| `MasRunProgressCard`/`TaskProgressCard` 的进度语义 | 是，重构为独立域组件 | 展示 OmicHub task / MAS Run 关联状态 |
| `AgentWorkspace` 的沉浸式双栏聊天壳 | 否 | 协作中心不是常驻聊天页，不复制其会话侧栏与输入框 |
| `StudioView` 的三栏可调整面板思路 | 选择性复用 | Case 详情可在宽屏采用可折叠证据侧栏，但不引入终端/编辑器面板 |
| `AgentHub` 的 Agent 卡片视觉 | 是，取其身份卡模式 | 用于角色目录与执行状态，不作为聊天入口 |

**组件库选择**：页面以 Naive UI 为主，原因是现有任务、审批、抽屉、表格和布局模式已使用 Naive UI；不在此页面混用 Arco 的同类交互控件。图标继续使用 `@vicons/ionicons5`，所有纯图标按钮必须有 `NTooltip` 和 `aria-label`。

### 11.3 路由、导航与权限

#### 路由设计

新增以下懒加载路由，不使用 `fullscreen: true`：

```ts
{
  path: 'agent-teams',
  name: 'agent-teams',
  component: () => import('@/views/AgentTeamsView.vue'),
  meta: { title: 'Agent 协作中心', requiresAuth: true },
},
{
  path: 'agent-teams/cases/:caseId',
  name: 'agent-teams-case',
  component: () => import('@/views/AgentTeamsCaseView.vue'),
  meta: { title: '协作案例', requiresAuth: true },
},
```

设计选择：

- `/agent-teams` 是 Case 列表与总览页；
- `/agent-teams/cases/:caseId` 是可深链接、可审计、可在浏览器前进/后退中恢复的详情页；
- 不将当前 Case 仅保存在抽屉或 Pinia 内存中；Case ID 必须反映在 URL；
- AgentTeams 不接通或用户无权限时仍可访问列表页面，但显示明确的空态/未开通态，不能显示错误的“系统正常运行”。

#### 导航位置

在 `frontend/src/layouts/DefaultLayout.vue` 的 AI/工作台邻近位置增加一级导航项：

```text
星尘 AI
Agent 协作中心
```

推荐图标：`GitNetworkOutline`、`PeopleOutline` 或 `LayersOutline` 中选择一个当前图标库已提供的图标；最终只保留一个，不用“多个 Agent 头像”作为导航图标。

首页快捷入口在 `frontend/src/config/homeQuickEntries.ts` 增加：

```ts
{
  key: 'agent-teams',
  title: 'Agent 协作中心',
  desc: '发起并追踪多 Agent 协作案例',
  to: '/agent-teams',
  icon: 'GitNetworkOutline',
  icon_bg: 'violet',
}
```

若模块权限系统启用，增加独立模块键 `agent_teams`；前端仅用于菜单隐藏/锁定提示，后端和 Bridge 才是实际权限边界。页面不得只根据前端角色决定是否允许审批、提交或取消任务。

### 11.4 页面信息架构

#### A. Case 总览页：`/agent-teams`

采用标准 `.page-container`，不设置 ad-hoc `max-width`。页面从上至下分为四个区域：

```text
┌─────────────────────────────────────────────────────────────┐
│ PageHeader                                                    │
│ Agent 协作中心                   [刷新] [新建协作 Case]         │
│ 将复杂多组学交付拆解为可追踪、可审批、可验证的协作闭环             │
├─────────────────────────────────────────────────────────────┤
│ 状态概览：进行中 / 待审批 / 被阻断 / 本周已交付                  │
├─────────────────────────────────────────────────────────────┤
│ 筛选栏：状态｜项目｜流程｜时间｜我的待办                         │
├─────────────────────────────────────────────────────────────┤
│ Case 列表                                                      │
│  Case 名称 / 当前阶段 / 角色进度 / 关联任务 / 风险或阻断 / 更新时间 │
└─────────────────────────────────────────────────────────────┘
```

**状态概览卡**：4 张轻量卡片。每张卡包含数值、文本标签、辅助说明及可点击筛选；不能只用颜色圆点表达状态。卡片可使用共享 `.card-hover`，点击后应保留筛选条件并更新 URL query，例如 `?status=approval_pending`。

**Case 列表桌面端**：优先 `NDataTable`，因为 Case 有状态、时间、任务、审批等需要快速扫描的字段。推荐列：

| 列 | 内容 | 交互 |
|---|---|---|
| Case | 名称、Case ID、目标流程 | 点击进入详情 |
| 当前阶段 | 预检 / 待审批 / 执行 / 质控 / 交付 / 阻断 | `NTag` + 文本 |
| 协作进度 | `3/5` 角色完成、简短 progress bar | 点击定位到详情协作视图 |
| 关联执行 | OmicHub task ID / MAS Run ID | 跳转既有任务或 MAS 页面 |
| 风险与待办 | 待审批、阻断原因、失败次数 | 高优先级在文案前显示语义图标 |
| 最近更新 | 相对时间 + 绝对时间 Tooltip | 支持排序 |

**移动端**：在 `max-width: 768px` 时切换成 Case 卡片列表，不强行压缩表格。每张卡显示名称、阶段、当前责任角色、更新时间和一个“查看协作”主操作。

#### B. Case 详情页：`/agent-teams/cases/:caseId`

详情页是比赛 Demo 的主展示页。宽屏使用“三段式工作台”，但每段都有可读标题、空态、加载态和错误态：

```text
┌────────────────────────────────────────────────────────────────────┐
│ 返回协作中心 / Case 名称 / 状态 Tag                 [刷新] [更多]  │
│ Project · RNA-seq · case_id · 最近更新时间                         │
├──────────────┬────────────────────────────────────┬────────────────┤
│ 协作概览       │ 协作时间线 / 工作项主视图              │ 执行证据       │
│ 角色和阶段     │ Manager 分派 → Worker 输出 → 审批 → 验证 │ 任务/产物/审批 │
│ 200–264 px    │ 自适应主列                              │ 300–360 px    │
└──────────────┴────────────────────────────────────┴────────────────┘
```

1. **左列：协作概览（固定语义，不是聊天联系人列表）**
   - Case 阶段轨：接收、预检、审批、执行、质量、交付；
   - Agent Identity 列表：Manager 与各 Worker 的运行状态、当前工作项、最后更新时间；
   - 可点击角色过滤主视图事件；
   - 使用 `aria-current` 或 `aria-pressed` 说明当前筛选角色。

2. **中列：协作主视图（默认）**
   - 顶部为当前阶段与“下一步为什么发生”的结构化摘要；
   - 下方按时间顺序显示协作事件，不伪装成人类即时聊天气泡；
   - 每条事件是 `ActivityEventCard`：角色、动作、Skill、结果、耗时、证据链接、展开后的输入/输出摘要；
   - 同一工作项的事件以细线和 work item ID 聚合；
   - 提供“全部 / 决策 / 工具调用 / 审批 / 异常”筛选；使用 `.omichub-segmented-toggle`，并设置 `aria-pressed`；
   - 默认仅展示安全摘要；原始日志、参数和工具响应在展开后显示，且敏感字段经过后端脱敏。

3. **右列：执行证据（可折叠）**
   - `OmicHubTaskPanel`：任务 ID、状态、进度、跳转任务详情、最新关键日志；
   - `ApprovalPanel`：待审批卡或历史审批列表；
   - `ArtifactEvidencePanel`：预检报告、质量结论、交付 manifest、报告链接、hash；
   - `CaseTracePanel`：Trace ID、Skill 数量、失败重试次数、累计耗时等可观测摘要；
   - 在窄屏收进 `NDrawer`，由“证据与任务”按钮打开，不覆盖中间协作主视图的当前阅读位置。

#### C. 新建 Case：右侧抽屉，不另建空白大页面

使用 `NDrawer` + `NForm` 做两步表单，原因是创建 Case 是低频、短流程，完成后应回到详情页而非停留在配置页。

```text
步骤 1：选择项目与目标
- 项目 / 工作区
- 场景模板（RNA-seq 交付、ATAC-seq 交付）
- 流程
- 业务目标与交付说明

步骤 2：执行边界
- 样本表或文件引用
- 参考基因组 / 关键参数
- 是否要求人工审批
- 参与角色（默认 Team 模板，只读展示；高级模式可调整）
```

提交前显示“将创建协作 Case，不会立即提交计算任务”；只有 Manager 完成预检并进入审批流程后，Workflow Operator 才可通过 Bridge 提交 OmicHub task。

### 11.5 组件、目录与状态管理

建议新增目录，不侵入 `ai-chat` 与 `agent-workspace` 目录：

```text
frontend/src/
├── views/
│   ├── AgentTeamsView.vue
│   └── AgentTeamsCaseView.vue
├── components/agent-teams/
│   ├── AgentTeamsCaseTable.vue
│   ├── AgentTeamsCaseCard.vue
│   ├── AgentTeamsCaseCreateDrawer.vue
│   ├── CaseStageRail.vue
│   ├── AgentIdentityList.vue
│   ├── AgentIdentityRow.vue
│   ├── CollaborationTimeline.vue
│   ├── ActivityEventCard.vue
│   ├── WorkItemGroup.vue
│   ├── ApprovalPanel.vue
│   ├── OmicHubTaskPanel.vue
│   ├── ArtifactEvidencePanel.vue
│   ├── CaseTracePanel.vue
│   ├── AgentTeamsEmptyState.vue
│   └── agentTeamsStatus.ts
├── api/
│   └── agentTeams.ts
├── stores/
│   └── agentTeams.ts
└── types/
    └── agentTeams.ts
```

职责边界：

| 模块 | 责任 | 不负责 |
|---|---|---|
| `AgentTeamsView` | Case 总览、筛选 query 同步、新建抽屉 | 不维护详情事件缓存 |
| `AgentTeamsCaseView` | 加载 Case、组合三栏、保持路由状态 | 不自行拼接后端状态 |
| `agentTeams.ts` API | 调用 `/api/v1/agent-teams/*`，归一化错误 | 不含 UI 状态 |
| Pinia `agentTeams` Store | 当前 Case、列表缓存、局部刷新、实时事件游标 | 不存 JWT/密钥/完整工具响应 |
| `agentTeamsStatus.ts` | Case/Worker/任务状态到文本、Tag 类型、图标的单一映射 | 不擅自推断后端状态 |
| `ActivityEventCard` | 渲染已脱敏的活动事件 | 不承担审批请求或任务提交逻辑 |

建议的前端类型（需与 Bridge/OpenAPI 契约同步生成或手写维护）：

```ts
export type CaseStatus =
  | 'received'
  | 'preflight_running'
  | 'preflight_blocked'
  | 'approval_pending'
  | 'executing'
  | 'quality_running'
  | 'quality_blocked'
  | 'delivery_ready'
  | 'closed'
  | 'execution_failed'
  | 'cancelled'

export interface AgentTeamsCaseSummary {
  id: string
  title: string
  status: CaseStatus
  flowId?: string
  projectName: string
  teamName: string
  activeAgentCount: number
  completedAgentCount: number
  taskIds: string[]
  pendingApprovalCount: number
  updatedAt: string
}

export interface CollaborationEvent {
  id: string
  caseId: string
  workItemId?: string
  occurredAt: string
  agent: { id: string; name: string; role: 'manager' | 'worker' }
  category: 'decision' | 'skill' | 'approval' | 'task' | 'quality' | 'error'
  title: string
  summary: string
  status: 'running' | 'succeeded' | 'blocked' | 'failed' | 'waiting'
  skill?: { name: string; version: string; durationMs?: number }
  evidenceRefs: Array<{ kind: string; id: string; label: string; href?: string }>
}
```

### 11.6 API、刷新与实时状态策略

Agent 协作中心的接口由后续新增的 OmicHub Bridge/后端代理提供；前端不直接请求 AgentTeams Controller、Matrix、MinIO 或 OmicHub 数据库。

推荐页面接口：

| UI 需求 | 前端调用 | 说明 |
|---|---|---|
| Case 列表 | `GET /api/v1/agent-teams/cases` | 已实现 `status`、`project_id`、`cursor`、`limit`；当前登录用户固定为 `mine` |
| Case 详情 | `GET /api/v1/agent-teams/cases/{caseId}` | 返回阶段、角色、任务/审批/产物引用 |
| 协作事件 | `GET /api/v1/agent-teams/cases/{caseId}/events` | 已实现 `cursor`、`limit` 游标增量读取，默认只取安全摘要 |
| 创建 Case | `POST /api/v1/agent-teams/cases` | 只创建 Case，不立即提交计算 |
| 审批决定 | `POST /api/v1/agent-teams/cases/{caseId}/approvals/{approvalId}/resolve` | 后端再次校验审批人和动作范围 |
| 取消协作 | `POST /api/v1/agent-teams/cases/{caseId}/cancel` | 仅在允许状态和有权限时显示 |
| 实时更新 | 未接入 SSE | 当前详情页在页面可见时每 20 秒以事件游标局部轮询；不伪造实时连接状态 |

**实时策略**：

1. Case 详情加载后建立 SSE；
2. 收到事件只局部更新受影响的 Case、工作项、审批或任务卡，不能刷新整个路由；
3. SSE 断开后显示“实时连接已断开，正在重连”，并以指数退避方式重连；
4. 连续失败后降级为 15–30 秒轮询，同时保留可见的“降级刷新中”状态；
5. 离开详情页、切换 Case 或组件卸载时关闭连接；
6. 刷新按钮仅刷新当前列表或当前 Case，禁止 `window.location.reload()`。

这与现有 `frontend/src/api/client.ts` 的 JWT 拦截器、错误处理和模块锁定机制保持一致。

### 11.7 视觉与交互样式规范

#### 页面材质与布局

- 背景、文字、边框、阴影全部消费现有语义 CSS 变量；不在组件内硬编码白色、灰色、紫色或阴影数值。
- 页面根使用标准 `.page-container`，保留工作台所需的全宽空间；普通页面不可自行增加 `max-width`。
- 页面卡片使用实体卡片材质与清晰边框；不在协作时间线上叠加多层玻璃和重阴影。
- 只在顶部 Case 摘要或“待审批”提醒条使用非常轻的品牌渐变；主操作按钮在渐变背景上使用规范的高对比样式。
- 宽屏布局建议：左列 `minmax(200px, 264px)`、主列 `minmax(0, 1fr)`、右列 `minmax(300px, 360px)`；任一侧栏可折叠，但主列不得低于可读宽度。

#### 状态语义

状态必须是“图标 + 文本 + 色彩”的组合，不能仅使用色点：

| 状态 | 文案 | 视觉语义 | 额外信息 |
|---|---|---|---|
| `running` | 进行中 | primary/info | 显示进度或当前角色 |
| `waiting` | 等待审批/输入 | warning | 明确显示等待对象与截止时间 |
| `succeeded` | 已完成/已通过 | success | 显示完成时间 |
| `blocked` | 已阻断 | warning 或 error，取决于是否需人工处理 | 显示首要阻断原因 |
| `failed` | 执行失败 | error | 显示错误分类与重试/查看证据操作 |
| `cancelled` | 已取消 | default | 显示取消人和原因 |

Case 卡、角色行和事件卡如果可点击，使用共享 `.omichub-selectable-card`：

- 选中态保留连续 outline 与左侧状态 rail；
- 用 `aria-selected` 或 `aria-pressed` 暴露选择状态；
- 键盘 `Enter`/`Space` 可打开详情或切换筛选；
- hover 仅提升边框/阴影，不通过位移制造不稳定感。

#### 协作时间线

- 时间线按事件真实发生顺序展示；并行 Worker 事件允许同一时间段交错，但必须保留 `work_item_id` 分组；
- Manager 的“任务分派/汇总”使用中性主色；Worker 的结果以角色 icon + 状态 Tag 区分，不为每个角色设置不可访问的专属颜色；
- 工具调用事件默认折叠参数，仅展示 Skill 名称、耗时、成功/失败和证据；
- 错误事件必须提供“查看证据”“重试状态/等待人工处理”等明确后续动作，不只显示红色文本；
- 审批事件使用与现有 `ApprovalCard` 一致的层次：风险说明、动作、影响、有效期、批准/拒绝按钮、已完成的审批记录；
- 不让 Agent 输出的长 Markdown 占满时间线。超过 4 行的说明折叠，展开后仍保留最大高度和滚动区域。

#### 动效、可访问性和响应式

- 普通状态变化使用 `120–200ms` opacity/border/background 过渡；不使用自动播放的复杂节点连线动画；
- 正在运行的事件可使用低频、非闪烁 loading indicator；`prefers-reduced-motion` 下静态呈现；
- `prefers-reduced-transparency` 时移除 banner/抽屉的 backdrop blur，保持实色背景；
- 对比度、焦点和高对比主题沿用 `tokens.css`/`global.css`；
- `< 1280px`：右侧证据栏折叠为可打开抽屉；
- `< 1024px`：左侧协作概览改为顶部可横向滚动的阶段/角色条；
- `< 768px`：详情页单列，Case 列表改卡片，主操作至少 44px 点击区域；
- 审批弹层初始焦点放在标题或风险摘要；拒绝/取消等破坏性操作必须二次确认并说明影响。

### 11.8 页面状态与异常分支

每个页面和核心面板必须覆盖以下状态：

| 状态 | 总览页 | 详情页 |
|---|---|---|
| 首次加载 | 结构化 Skeleton，不显示伪数据 | 三栏各自 Skeleton，保留页头 |
| 空态 | 说明何时该创建协作 Case + 主操作 | Case 无协作事件时说明等待原因 |
| AgentTeams 未接通 | 解释集成尚未启用，隐藏新建按钮或提供管理员联系入口 | 不显示“任务失败”，展示集成不可用状态 |
| 无权限 | 保留路由页壳，显示模块/Case 权限说明 | 不泄露 Case 名称、任务 ID、产物路径 |
| 网络错误 | 局部错误卡 + 重试，保留已有列表 | 中列错误卡；右栏不清空已加载证据 |
| SSE 重连 | 列表可继续操作 | 显示连接状态，不阻断人工审批按钮的真实可用性判断 |
| Case 被其他用户更新 | 局部合并、toast 提示 | 依据服务端版本号刷新冲突区域 |
| 审批已过期/被处理 | 更新卡片并禁用旧按钮 | 显示决定者、时间与后续状态 |

### 11.9 前端验收与演示脚本

实现完成后，演示应按以下顺序进行：

1. 打开 `/agent-teams`，筛选“待审批”并查看 Case 状态、角色完成度和关联任务；
2. 创建一个 RNA-seq 交付 Case，确认 UI 明示“尚未提交计算任务”；
3. 进入 `/agent-teams/cases/:caseId`，查看 Manager 分派给 Data Steward 的预检工作项；
4. 展示预检通过后生成的审批卡；批准后由 Workflow Operator 提交 OmicHub 任务；
5. 在右侧证据栏看到真实 task ID、进度和跳转链接；
6. 展示 Quality Auditor 的质量结论与 Delivery Reporter 的 manifest；
7. 再演示一个预检阻断或任务失败 Case，确认时间线、原因、证据和恢复动作均可见；
8. 在窄屏宽度、键盘导航、深色主题和 reduced-motion 下完成一次关键路径检查。

前端交付前至少执行：

```bash
npm --prefix frontend run type-check
npm --prefix frontend run build
```

为状态映射、SSE 事件归一化、审批按钮权限和 Case 路由恢复增加针对性 Vitest 测试。若未接入真实 AgentTeams 服务，测试 fixture 必须明确标注为演示数据。

---

## 12. 分阶段实施计划

### Phase 0：初赛材料（2–4 人日）

目标：完成可审查方案，不要求运行代码。

- 完成本文件中的职责边界、架构图、Identity 清单和 Skill 清单；
- 选定一个 RNA-seq 示例与一个异常样例；
- 画出成功与失败两个时序图；
- 写明 AgentTeams Manager/Worker 与 OmicHub API 的映射；
- 明确开源目录、部署边界与敏感数据处理方式。

**验收**：评审可判断至少 3 个角色如何协作、如何调用工具、怎样审批、怎样验证并保留证据。

### Phase 1：旁路 POC（5–7 人日）

目标：最小成功闭环。

- 独立部署 AgentTeams；
- 新建 `omichub-agentteams-bridge`；
- 先实现 `list_flows`、`preflight`、`submit_task`、`get_task`、`cancel_task`；
- 配置 Manager、Data Steward、Workflow Operator、Quality Auditor；
- 接通一个 RNA-seq 演示任务；
- 保留 `case_id ↔ task_id` 审计表或 JSONL 日志。

**验收**：AgentTeams Manager 能协调至少 3 个角色，Worker 通过 Bridge 成功提交一个 OmicHub 任务，并可在协作房间看到状态回传。

### Phase 2：复赛可验证 Demo（8–12 人日）

目标：满足赛事“可运行、可验证、可审计”。

- 添加审批卡与 Bridge 审批令牌；
- 添加幂等、重试、超时、取消和失败分类；
- 接入质量门禁与报告 manifest；
- 可选增强：落地受控 Agent Gateway 与 `scientific-interpretation` Skill，在 1–2 个知识密集型 Case（如新物种基因组选择、比较组设计复核）上演示「Manager → Gateway → 专业 Agent → 结构化建议 → 人工审批」链路；
- 至少演示成功、预检阻断、执行失败或 QC 阻断三种路径中的两种；
- 输出 Trace/Log/Metrics 中至少两类数据；
- 添加一键部署、示例输入输出和 API/Skill 契约测试。

**验收**：评审可重复运行 Demo，检查工具调用、审批、任务状态、质量结论和最终证据包。

### Phase 3：生产加固（后续，20+ 人日）

- 用户身份联合与细粒度数据权限；
- 真实审计存储、告警和长周期保留；
- 多租户隔离、密钥轮换、限流、配额；
- 事件驱动状态回传代替短轮询；
- Runbook 审核、版本发布与回滚；
- 容灾、备份、升级与安全评审。

---

## 13. 开发任务拆分与预估

| 工作包 | 文件/模块归属 | 规模 | 说明 |
|---|---|---:|---|
| AgentTeams 独立部署 | `deploy/agentteams/` | 1–2 人日 | 不改 OmicHub Compose |
| Bridge 骨架与认证 | `integrations/agentteams/bridge/` | 2–3 人日 | 无状态服务、身份映射、审计 |
| Task/Flow 适配器 | Bridge | 2 人日 | 调用既有 `/flows`、`/tasks` |
| Identity、Team、Worker 配置 | `integrations/agentteams/teams/` | 1–2 人日 | 4 Worker + Manager |
| Skill 契约与执行器 | `integrations/agentteams/skills/` | 2–3 人日 | 预检、提交、监控、质量门禁 |
| 受控 Agent Gateway 与 `scientific-interpretation` | `integrations/agentteams/gateway/`（新增） | 3–5 人日 | 白名单适配、固定 Schema 结论、成本护栏、`agent.consultation` 审计事件 |
| 审批与回滚 | Bridge + AgentTeams | 2–3 人日 | 短期令牌、状态变化 |
| 证据包与观测 | Bridge + Demo | 2–4 人日 | case trace、manifest、指标 |
| 自动化测试与演示脚本 | `integrations/agentteams/bridge/tests/`、`integrations/agentteams/demo/` | 2–3 人日 | 契约、冒烟、异常路径 |

估算：

- **最小 POC**：10–15 人日；
- **复赛质量 Demo**：18–28 人日；
- **可选 Agent Gateway 增强**：3–5 人日（叠加在复赛 Demo 上）；
- **真正生产化**：40–60 人日，且需平台安全/运维投入。

---

## 14. 不应做的事

1. 不重写 `ChatService` 或 LangGraph runtime 来“兼容” AgentTeams；
2. 不让 AgentTeams 直接调用 `TaskService` Python 类或直连 OmicHub 数据库；
3. 不把 Celery、MAS DAG 或 Snakemake 的计算调度迁走；
4. 不把 FASTQ/BAM/参考基因组复制到 Matrix/MinIO；
5. 不让任意 Worker 执行 shell、Docker 或数据库 SQL；
6. 不依赖尚未稳定的 OmicHub 子 Agent fan-out 作为比赛闭环的关键路径；
7. 不在文档或 PPT 中把“计划中的 Bridge/审批/可观测能力”描述为已经上线。
8. 不让 AgentTeams Manager 直接调用 `ChatService` 内部实现、Agent Python 类或专业 Agent 的任意工具；必须经受控 Agent Gateway 暴露白名单 Skill。
9. 不让被 Gateway 调用的专业 Agent 在同一 Case 中自行提交、取消或重规划计算任务；这些动作始终由人工审批后的 Workflow Operator 执行。

---

## 15. 验收清单

### 15.1 架构验收

- [x] **代码/配置证据**：AgentTeams Bridge 仅调用受控 OmicHub HTTP API，未导入 `TaskService`、未连接 OmicHub DB；计算仍在 OmicHub 任务 API、Celery 与流程层；
- [x] **代码/配置证据**：提供独立 `deploy/agentteams/`、独立网络与 Bridge 持久卷，不修改 OmicHub 主 Compose；
- [x] **代码/配置证据**：Team 身份和 Compose 约束禁止 Worker 获取 OmicHub DB、Redis、Docker Socket、宿主数据卷；
- [ ] **部署验收待执行**：在真实独立 AgentTeams/HiClaw 环境应用 `deploy/agentteams/kubernetes/network-policy.default-deny.yaml`，运行 `deploy/agentteams/verify_control_plane.py` 并验证版本对应的网关白名单。

### 15.2 协作验收

- [x] **契约证据**：同一 Case 可由 Manager 分派 `data-steward`、`workflow-operator`、`quality-auditor` 与 `delivery-reporter` Work Item，且仅目标 Worker 可读取关联 Case/任务并回写；观察到 OmicHub 任务成功后才幂等分派 Quality Auditor，质量结论通过后才幂等分派 Delivery Reporter；
- [x] **界面/审计证据**：协作中心展示 Work Item、上下文引用、状态轨和按 `work_item_id` 关联的审计时间线；Case 列表支持状态/项目筛选及游标分页，详情页使用可见页面的增量事件轮询；
- [x] **契约证据**：Skill 合约、输入/输出、失败处理与最小权限边界已在 `integrations/agentteams/skills/contracts.yaml` 和 Bridge 路由中实现；
- [x] **契约证据**：相同 `idempotency_key` 的重复提交只创建一次 OmicHub task；
- [x] **代理/运行证据**：用户创建 Case 后，OmicHub 后端以独立 Data Steward 身份自动分派并执行只读预检；预检通过的 Case 才显示人工确认入口，确认后的审批令牌和 Workflow Operator 凭证均只保留在服务端；Bridge 保存的预检输入快照不会返回浏览器，后续提交若改变流程、样本表或分组对比会被拒绝；
- [x] **界面/配置证据**：协作对话可整理并创建真实 Case，Case 详情以审批卡片展示执行范围并要求二次确认；AI 资源中心可由管理员以 TOTP 配置 Bridge，令牌加密保存且读取脱敏；
- [x] **Gateway 代码与定向契约验证完成（2026-08-01）**：已实现 `scientific-interpretation` Skill 与独立受控 Agent Gateway；覆盖白名单、只读工具拦截、固定 Schema、超时/次数/token 护栏及 `agent.consultation` JSONL 审计的定向测试。
- [ ] **Gateway 端到端验收待执行**：在真实受控咨询端点与 AgentTeams Manager 环境中，按白名单调用现有 `agent-rnaseq`、`agent-scrna`、`agent-viz` 等专业 Agent，并验证其只返回结构化解读/建议/证据，不能提交或取消任务；
- [ ] **部署验收待执行**：以真实 AgentTeams Worker/Matrix 房间运行上述三角色演示。

### 15.3 安全与证据验收

- [x] **契约证据**：正式任务提交和取消均校验带 `case_id`、动作范围、有效期和签名的审批令牌；
- [x] **契约证据**：Case、Work Item、Skill、任务提交/取消和质量决策均以 `case_id` 及审计事件关联；
- [x] **观测证据**：Bridge 输出 JSONL 审计事件与受限 `/v1/metrics` 指标；
- [x] **契约证据**：关闭 Case 生成包含任务参数、OmicHub 快照、审批事件、质量结论和 Runbook 引用的 manifest；
- [x] **契约证据**：预检/质量阻断、修复后重试和取消路径均有定向测试及可展示事件；
- [x] **运行证据**：已对 `preflight_blocked` Case 发起受认证提交请求，得到拒绝且未创建 OmicHub task；Bridge 的受限 OmicHub API Key 可读取流程，但访问非授权用户接口返回 `403`；
- [ ] **部署验收待执行**：使用真实任务、真实审批人与真实 Worker 执行可重复 Demo。

---

## 16. 参考依据

### OmicHub 当前实现（仓库内）

- `ARCHITECTURE_DESIN/agent_framework_final_baseline.md`
- `ARCHITECTURE_DESIN/multi-agent.md`
- `src/omichub/api/v1/router.py`
- `src/omichub/api/v1/tasks.py`
- `src/omichub/api/v1/flows.py`
- `src/omichub/api/v1/mas.py`
- `src/omichub/application/schemas/task.py`
- `src/omichub/application/schemas/mas.py`
- `data/ai/mas/artifact_schemas.yaml`
- `data/ai/mas/tool_policies.yaml`

### AgentTeams 选型依据（外部）

- AgentTeams/HiClaw 官方仓库与部署文档：Manager/Worker 容器协作、Matrix 协作层、MinIO 文件协作与网关治理能力。
- 实施时应以目标部署版本的官方文档和 API/配置 Schema 为准；不要根据本文中的概念图直接假设具体 CRD、CLI 或配置字段名称。
