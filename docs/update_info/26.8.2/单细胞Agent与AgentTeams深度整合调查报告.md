# 单细胞 Agent 与 AgentTeams 深度整合调查报告

**调查日期：2026 年 8 月 2 日**  
**结论：可深度整合，建议采用“AgentTeams 协作与审批层 + OmicHub MAS 确定性执行层”的双层多智能体架构。**

---

## 1. 调查目标与范围

本报告评估以下三个拟拆分的单细胞 Agent 是否能够接入现有 AgentTeams 协作中心，并以 Multi-Agent 方式编排：

1. **上游处理与样本 QC Agent**：面向 FASTQ / Cell Ranger `outs`，执行 Cell Ranger、样本级 QC 和输入标准化；
2. **下游整合、降维、聚类 Agent**：面向表达矩阵或 `h5ad`，执行细胞 QC、批次诊断与校正、降维、聚类和初版 marker；
3. **注释验证与高级分析 Agent**：面向聚类结果，执行注释验证、pseudobulk 差异分析、可视化、可选轨迹/拟时序分析。

调查同时覆盖：现有 OmicHub 单细胞能力、MAS 编排与 artifact 契约、AgentTeams Bridge/Gateway 的权限模型、事件与状态衔接、安全边界、缺口、实施顺序及验收标准。

---

## 2. 执行摘要

### 2.1 可行性判断

| 维度 | 判断 | 说明 |
| --- | --- | --- |
| 三段式 Agent 拆分 | **推荐** | 输入/输出稳定、资源模型不同、可分别审批与重试。 |
| AgentTeams 作为协作平面 | **可行且推荐** | 已有 Case、Work Item、审批、证据、质量和交付状态机。 |
| MAS 作为执行平面 | **必须保留** | 已有 artifact DAG、节点状态机、幂等事件与受限 executor 模型。 |
| AgentTeams 直接运行 Cell Ranger / Docker | **不推荐，禁止** | 与现有“Worker 无数据库、Docker、Shell、数据卷权限”的隔离原则冲突。 |
| 三个 Agent 完全并行运行 | **不推荐** | 三段之间有严格 artifact 依赖；仅允许每一段内部受控并行。 |
| 当前代码可直接完成全链路 | **否** | 当前 MAS 只实现 `h5ad -> 基础 Scanpy QC`，需补上游、整合聚类和高级分析 executor。 |

### 2.2 推荐的职责划分

```text
用户 / OmicHub AI 页面
        │
        ▼
AgentTeams Case（协作、意见、证据、人工审批、交付）
        │  只交换逻辑引用、摘要、指标、审查结论
        ▼
OmicHub MAS Run（受控 DAG、artifact 契约、状态机、可重试执行）
        │
        ├─ 上游 Cell Ranger / 样本 QC executor
        ├─ Scanpy / Seurat 整合聚类 executor
        └─ 注释验证 / DE / 可视化 / 轨迹 executor
        │
        ▼
专用计算 Worker（RocketMQ 或 Celery 路由、容器/Apptainer、高资源队列）
```

核心原则：**AgentTeams 决定“是否做、为何做、如何审查”；MAS 决定“以什么已批准参数、在哪个受控运行环境执行”。**

---

## 3. 当前平台能力盘点

### 3.1 已有单细胞 Agent 与运行环境

现有 `agent-scrna` 已是单细胞领域专家，提示词覆盖 QC、归一化、HVG、批次校正、降维聚类、注释、差异、轨迹和通讯等建议；其 Studio runtime profile 是 `analysis-scrna`。

- Agent 定义：`data/ai/scrna.yaml`
- 单细胞工作流提示词：`data/ai/prompts/scrna.md`
- MAS 单细胞运行时镜像：`deploy/runtime-images/scrna.Dockerfile`
- Studio 单细胞镜像：`tool_configs/terminal/docker/Dockerfile.scrna`

运行时已包含或声明支持 Scanpy、AnnData、Leiden、igraph、Seurat；Studio 单细胞镜像另有 Harmony、Scrublet、scVelo。因此第二段和第三段的绝大多数 Python/R 分析依赖可在现有镜像基础上扩展。

### 3.2 现有 MAS 能力的实际边界

当前 MAS 能力清单只为 `agent-scrna` 注册了：

```yaml
agent-scrna: [scanpy-qc, artifact-validate]
```

来源：`data/ai/mas/agent_capabilities.yaml`。

现有 `scanpy-qc` executor 的输入限定为 `/workspace/input` 下的 `.h5ad`，仅执行：

- `sc.pp.filter_cells(..., min_genes=...)`；
- `sc.pp.filter_genes(..., min_cells=...)`；
- 输出 `scrna_qc_filtered.h5ad` 和 `scrna_qc_metrics.json`。

实现位置：`src/omichub/infrastructure/mas/scanpy.py`、`src/omichub/infrastructure/celery_app/tasks/mas.py`。

当前 artifact schema 仅有：

- `scrna.input_h5ad`；
- `scrna.filtered_h5ad`；
- `scrna.qc_metrics`。

来源：`data/ai/mas/artifact_schemas.yaml`。

因此，当前平台能支撑“已有 h5ad 的最小 QC 节点”，**还不能直接支撑 FASTQ/Cell Ranger、跨样本整合聚类、注释验证或高级分析的可审计 DAG**。

### 3.3 现有 AgentTeams 基础

AgentTeams Bridge 已支持：

- Case 与 Work Item；
- Worker 领取、claim、完成工作项；
- 短时、范围受限的人类审批 token；
- 预检、任务提交、监控、取消、质量审查、交付证据；
- requester 隔离、幂等键、审计事件和 Case 状态机。

来源：`integrations/agentteams/bridge/`、`integrations/agentteams/skills/contracts.yaml`、`integrations/agentteams/teams/bioops-delivery.yaml`。

特别重要的是，现有 AgentTeams 团队已经声明：

```yaml
- identity: agent-scrna
  skills: [scrna-interpretation, cell-annotation-advice]
  forbidden_capabilities: [workflow_submit, workflow_cancel, database_access, shell, file_write]
```

这说明 `agent-scrna` 已经具备**协作身份与只读科学审查定位**，但还没有被授权直接执行工作流；这是正确的安全起点。

### 3.4 Gateway 的受控科学咨询能力

Agent Gateway 已定义固定的 `scientific-interpretation` 请求/响应协议，可调用：

- `interpretation`；
- `planning_advice`；
- `result_interpretation`；
- `qc_advice`。

Gateway 有调用次数、Token 用量、超时、审计及工具白名单限制，且明确不暴露原始会话、工具轨迹、文件、数据库、Shell 或工作流执行权限。

来源：`integrations/agentteams/gateway/omichub_agent_gateway/models.py`、`integrations/agentteams/gateway/omichub_agent_gateway/service.py`。

这非常适合承载三类单细胞 Agent 的“计划评审、QC 解释、注释审查、结果解释”工作项。

---

## 4. 推荐的 Multi-Agent 角色模型

### 4.1 不建议把三个角色做成三个自由执行 Agent

若三个 Agent 都可以任意访问工作区、Shell、Docker 和原始数据，会产生以下问题：

- 无法保证 Cell Ranger、QC、整合和轨迹参数可追溯；
- 上游产物可能被下游 Agent 覆盖或改写；
- 同一数据被多次提交，出现重复计算和费用膨胀；
- 生物学判断与确定性执行混杂，难以复现或审计；
- 违反 AgentTeams Worker 无 Shell、无 Docker、无数据卷访问的既有边界。

### 4.2 推荐：一个总控 + 三个领域协作角色 + 多个确定性 executor

| 层级 | 角色 | 主要职责 | 是否直接执行容器任务 |
| --- | --- | --- | --- |
| AgentTeams | `bioops-manager` / 单细胞总控 | 建立 Case、拆解 Work Item、汇总风险、发起审批、推动交付 | 否 |
| AgentTeams | `scrna-upstream-reviewer` | 评估 FASTQ/参考/chemistry、样本 QC 规则与纳入建议 | 否 |
| AgentTeams | `scrna-cluster-reviewer` | 评估过滤、整合、批次校正、聚类分辨率和 marker 证据 | 否 |
| AgentTeams | `scrna-advanced-reviewer` | 注释验证、比较设计、轨迹适用性、结果解释 | 否 |
| AgentTeams | `quality-auditor` | 审查 artifact 完整性、QC gate、审计记录 | 否 |
| MAS | `scrna-cellranger` executor | FASTQ 到每样本 Cell Ranger 结果 / 统一矩阵 | 是 |
| MAS | `scrna-qc-integrate-cluster` executor | 细胞 QC、doublet、整合、降维、聚类、marker | 是 |
| MAS | `scrna-advanced-analysis` executor | 注释证据表、pseudobulk DE、可视化、可选轨迹 | 是 |

建议 AgentTeams 侧初期仅保留一个 `agent-scrna` 身份，通过 `capability` 或 Work Item `skill_name` 划分上游/下游/高级三类审查任务；业务稳定后再拆成三个独立 AgentTeams identity。这样可控制身份、模型成本和审批面扩张。

---

## 5. 三段单细胞流程的建议边界

### 5.1 Agent A：上游处理与样本 QC

**输入**

- 原始 FASTQ；或 Cell Ranger `outs`；
- 样本表、10x chemistry、物种、参考版本；
- 可选：目标细胞数、预期细胞类型、文库/批次信息。

**确定性 executor**

- 每个样本运行 `cellranger count`；
- 对多库样本运行 `cellranger multi` 或合规的聚合策略；
- 解析 `metrics_summary.csv`、`web_summary.html`、barcode/UMI/gene 指标；
- 将 10x matrix / H5 标准化为原始 `h5ad`；
- 写入样本级 QC 汇总，不自动剔除样本。

**AgentTeams 审查任务**

- 检查 FASTQ、参考基因组、chemistry 与样本表一致性；
- 审阅每样本 reads、mapping、saturation、median genes、细胞数、ambient RNA / doublet 风险；
- 输出 `accept`、`manual_review` 或 `exclude_candidate` 建议；
- 若涉及样本剔除、参考切换或重跑参数，必须发起人类审批。

**必须新增 artifact**

```text
scrna.fastq_manifest
scrna.cellranger_outs
scrna.cellranger_metrics
scrna.sample_qc_report
scrna.raw_h5ad
scrna.sample_inclusion_decision
```

**资源要求**

- 队列：`scrna_upstream_highmem`；
- 参考索引版本固定并记录 checksum；
- 限制每节点的 CPU、内存、临时磁盘、最大 FASTQ 大小和并发样本数；
- Cell Ranger 二进制、参考和许可证由专用 Worker 管理，不进入 AgentTeams 容器。

### 5.2 Agent B：下游整合、降维和聚类

**输入**

- 经批准的 `scrna.raw_h5ad`；
- 样本/批次/分组 metadata；
- 上游 QC 的样本纳入决策。

**确定性 executor**

1. 细胞级 QC：UMI、genes、线粒体/核糖体比例、环境 RNA 相关指标；
2. doublet 检测与标记，而不是静默删除；
3. 归一化、HVG、回归项、PCA；
4. 批次诊断；按计划选择 Harmony、scVI 或 Seurat integration；
5. 邻接图、UMAP、Leiden；
6. cluster marker 表和版本化参数快照。

**AgentTeams 审查任务**

- 审查各样本过度过滤、批次是否仍主导 embedding、整合是否过度；
- 根据 marker 一致性提出分辨率候选，不把“cluster 数”直接视作“细胞类型数”；
- 对多个候选参数方案进行排序，要求用户批准最终方案后再作为正式产物发布。

**必须新增 artifact**

```text
scrna.cell_qc_metrics
scrna.doublet_scores
scrna.qc_filtered_h5ad
scrna.integration_diagnostics
scrna.integrated_h5ad
scrna.cluster_markers
scrna.cluster_report
```

### 5.3 Agent C：注释验证与高级分析

**输入**

- `scrna.integrated_h5ad`、cluster marker、样本分组；
- 初版细胞注释及参考数据库/marker 来源；
- 用户确认的比较组、时间点或轨迹生物学假设。

**确定性 executor**

- 对每个 cluster 生成 marker 证据、参考映射结果和置信度；
- 按细胞类型和生物学重复构建 pseudobulk，做 DE 与通路富集；
- 生成 UMAP、dot plot、heatmap、composition、DE、富集图；
- 只有满足轨迹准入条件时执行 PAGA / scVelo / Monocle3。

**AgentTeams 审查任务**

- 检查 marker、参考图谱和组织/物种背景是否冲突；
- 输出高/中/低置信度注释及候选标签；
- 评估 DE 的独立重复、混杂因素与统计方法；
- 对轨迹根节点、方向、velocity 适用性提出风险说明；不允许“自动确定生物学结论”。

**必须新增 artifact**

```text
scrna.annotation_evidence
scrna.annotation_validation_report
scrna.annotated_h5ad
scrna.pseudobulk_counts
scrna.de_results
scrna.pathway_enrichment
scrna.visualization_bundle
scrna.trajectory_result
```

---

## 6. 推荐 DAG、AgentTeams Case 与 MAS Run 的映射

### 6.1 正式分析 DAG

```text
scrna-preflight
  └─ scrna-upstream-cellranger (按样本 fan-out)
       └─ scrna-sample-qc-gate
            └─ [人工审批：样本纳入、参考/参数变更]
                 └─ scrna-integrate-cluster
                      └─ scrna-cluster-review-gate
                           └─ [人工审批：正式整合/聚类版本]
                                └─ scrna-annotation-validation
                                     ├─ scrna-pseudobulk-de
                                     ├─ scrna-visualization
                                     └─ scrna-trajectory (可选、默认关闭)
                                          └─ scrna-delivery-quality-gate
```

### 6.2 Case 状态与 Run 状态对齐

现有 AgentTeams Case 已有：`received -> preflight_running -> approval_pending -> approved -> executing -> quality_running -> delivery_ready -> closed` 等状态；MAS Run 和 Node 也已有 `awaiting_approval`、`queued`、`running`、`waiting_approval`、`succeeded`、`failed` 等状态机。

建议建立**显式映射表**，不要让两个状态机互相覆盖：

| AgentTeams Case | MAS Run / Node | 含义 |
| --- | --- | --- |
| `preflight_running` | Run `draft` / 无执行节点 | 审查输入，尚未提交计算。 |
| `approval_pending` | Run `awaiting_approval` 或 Node `waiting_approval` | 等待样本纳入、参数、比较设计等人类决定。 |
| `executing` | Run `queued` / `running` | 已批准的 executor 在运行。 |
| `quality_running` | 下游 quality-gate Node | 审查完整性和生物学/统计质量。 |
| `quality_blocked` | Node `waiting_approval` 或新的 remediation plan | 有问题但不应自动重跑/自动改参数。 |
| `delivery_ready` | Run `succeeded` 或 `succeeded_with_warnings` | 结果、证据和 runbook 已齐全。 |

**权威性规则**：计算真相以 MAS Run/Artifact 为准；协作和审批真相以 AgentTeams Case 为准。二者只通过不可变事件关联，不共享数据库表。

### 6.3 关联键与事件幂等

每个执行计划至少携带：

```json
{
  "case_id": "agentteams-case-id",
  "mas_run_id": "uuid",
  "node_key": "scrna-integrate-cluster",
  "analysis_revision": 3,
  "input_manifest_digest": "sha256:...",
  "parameter_set_digest": "sha256:..."
}
```

必须使用以下幂等规则：

- AgentTeams Work Item：`case_id + work_item_id`；
- MAS Event：沿用既有 `dedupe_key` 与 `state_version`；
- 执行提交：`case_id + mas_run_id + node_key + analysis_revision`；
- RocketMQ/Celery 消息：同一 MAS node 的固定 task id，不依赖随机重复投递；
- AgentTeams 收到重复事件时只更新最后的单调状态，不再次发起审批或重跑。

---

## 7. 深度整合所需接口与契约扩展

### 7.1 AgentTeams Work Item 建议

建议新增以下 `skill_name`，这些均是“阅读逻辑 artifact 引用后给出结构化结论”的只读工作：

```yaml
scrna-upstream-review:
  actor: agent-scrna
  boundary: read_only
  input: [scrna.fastq_manifest, scrna.cellranger_metrics, scrna.sample_qc_report]
  output: [scrna.upstream_review]

scrna-integration-review:
  actor: agent-scrna
  boundary: read_only
  input: [scrna.cell_qc_metrics, scrna.integration_diagnostics, scrna.cluster_markers]
  output: [scrna.integration_review]

scrna-annotation-review:
  actor: agent-scrna
  boundary: read_only
  input: [scrna.annotation_evidence, scrna.cluster_markers]
  output: [scrna.annotation_review]

scrna-trajectory-review:
  actor: agent-scrna
  boundary: read_only
  input: [scrna.annotated_h5ad, scrna.trajectory_result]
  output: [scrna.trajectory_review]
```

建议把现有 `scrna-interpretation` 扩展为上述多个细分 skill，而非让单一自由文本任务承担所有决策。

### 7.2 Gateway 咨询响应的结构化字段

现有科学咨询响应已有 `conclusion`、`recommendations`、`evidence_refs`、`risks`，建议在单细胞场景增加受控的 `structured_findings`，例如：

```json
{
  "decision": "approve | manual_review | block",
  "confidence": "high | medium | low",
  "parameter_recommendations": {
    "min_genes": {"value": 300, "rationale": "..."},
    "integration_method": {"value": "harmony", "rationale": "..."}
  },
  "sample_flags": [
    {"sample_id": "S03", "severity": "warning", "reason": "..."}
  ],
  "annotation_flags": [
    {"cluster": "7", "severity": "manual_review", "reason": "..."}
  ]
}
```

该字段必须经 Pydantic schema 校验；不能直接被 executor 当作 Shell 参数。只有经过 MAS Plan Validator、策略校验和必要的用户审批后，才能写入新的计划 revision。

### 7.3 MAS executor、能力和策略扩展

需要新增 executor 枚举/路由、对应 Celery/RocketMQ task、artifact schema、tool policy 和专用镜像。建议初始命名：

| executor | 目标队列 | 主要输出 |
| --- | --- | --- |
| `scrna-cellranger` | `scrna_upstream_highmem` | Cell Ranger `outs`、metrics、raw h5ad |
| `scrna-sample-qc-gate` | `analysis` | QC gate 决策、证据报告 |
| `scrna-integrate-cluster` | `scrna_analysis_highmem` | integrated h5ad、marker、诊断图 |
| `scrna-annotation-validate` | `scrna_analysis` | 注释证据与置信度报告 |
| `scrna-pseudobulk-de` | `scrna_analysis` | DE/富集结果 |
| `scrna-trajectory` | `scrna_analysis_highmem` | trajectory artifact |

现有 `scanpy-qc` 可重构为 `scrna-qc-filter`，保留其现有输入/输出以保证向后兼容。

### 7.4 API 边界

建议新建 OmicHub 服务端内部 API，由 Bridge/Gateway 通过 Manager 身份调用：

```text
POST /api/v1/agentteams/cases/{case_id}/mas-runs
GET  /api/v1/agentteams/cases/{case_id}/mas-runs/{run_id}
GET  /api/v1/agentteams/cases/{case_id}/artifacts
POST /api/v1/agentteams/cases/{case_id}/reviews
POST /api/v1/agentteams/cases/{case_id}/approval-requests
```

边界要求：

- 请求只接收 `omic://...` 或 MAS Artifact ID，不接收宿主文件路径；
- Bridge 不得获得 PostgreSQL、Redis、Docker socket、共享存储挂载或 shell 权限；
- 单细胞图片/表格可使用经授权的短时 artifact URL 或逻辑摘要；
- 原始 FASTQ、完整表达矩阵、患者/样本标识信息默认不跨出 OmicHub。

---

## 8. 人工审批与科学风险控制

以下操作必须进入审批卡，不能由 Agent 自动决定：

| 决策 | 风险 | 审批人 |
| --- | --- | --- |
| Cell Ranger 参考/chemistry/feature reference 选择 | 原始量化不可逆且代价高 | 项目负责人或平台管理员 |
| 样本整批剔除 | 影响统计功效和研究结论 | 项目负责人 |
| 高比例细胞过滤策略 | 可能选择性去除真实细胞状态 | 项目负责人 + 质量审查 |
| Harmony/scVI/Seurat 整合方案 | 可能过校正、抹平生物学差异 | 项目负责人 |
| 正式聚类分辨率/annotation revision | 影响后续 DE 与结论 | 项目负责人 |
| DE 比较组和协变量 | 直接影响统计结论 | 项目负责人 |
| 拟时序根节点、方向、velocity 使用 | 容易产生过度解释 | 项目负责人 + 领域专家 |

建议将 AgentTeams 返回值限制为“建议 + 证据 + 风险”，而不是“直接改参数 + 自动重跑”。MAS 的 `waiting_approval` 状态机已经适合承载此流程。

---

## 9. 安全、数据治理与运行成本

### 9.1 数据隔离

- AgentTeams 仅使用逻辑 project/task/artifact 引用；
- Bridge 的 Case 读取继续按 `requester_ref` 隔离；
- 每个 MAS Run 只可读其 `/workspace/input` 和已声明 artifact，输出写入 `/workspace/results`；
- 禁止把原始 FASTQ、原始 count matrix、完整 `h5ad` 直接嵌入 Work Item 或 LLM prompt；
- 向 Gateway 提供的内容应是 QC 指标、marker 前 N 条、聚合图摘要、经过脱敏的 metadata。

### 9.2 执行安全

- Cell Ranger Worker：只读参考、只读输入、专属写入目录、无公网或经受控下载入口；
- Scanpy/Seurat Worker：容器网络默认关闭；
- Cell Ranger、scVI 和大规模 h5ad 在专用资源队列运行；
- 不允许 AgentTeams 角色以“诊断”为由进入 shell 或 Docker；
- 模型输出只能作为 Plan Draft / Review，不可拼接进命令行。

### 9.3 成本与并发

- Cell Ranger 以样本为粒度 fan-out，但需按项目设置最大并发数；
- `h5ad` 整合、scVI、velocity 需要内存门槛和 cell 数上限；
- Gateway 沿用每 Case 调用次数、Token 上限、超时与审计；
- 同一 revision 的同一 node 应复用计算结果，不因多次 Agent 讨论重复运行。

---

## 10. 分阶段实施计划

### Phase 0：设计与契约（建议先完成）

1. 确认输入范围：仅 10x 3'，还是同时覆盖 5'、VDJ、Feature Barcode、多组学；
2. 确定 Cell Ranger 版本、许可证处理、参考来源、checksum 和升级策略；
3. 定义所有 `scrna.*` artifact schema、媒体类型、最大大小和保留策略；
4. 在 AgentTeams contracts 中增加四类单细胞 review skill；
5. 为三类科学审查建立固定 JSON 输出 schema；
6. 明确审批矩阵和审计字段。

**验收**：一份无执行权限的模拟 Case 能走完 preflight、review、approval 和 delivery 状态。

### Phase 1：上游 Cell Ranger 与样本 QC

1. 新增 `scrna-cellranger` executor 与高资源 Worker；
2. 新增 FASTQ manifest 校验、参考 registry、sample sheet 校验；
3. 解析 Cell Ranger metrics，生成标准化 QC artifact 和 raw h5ad；
4. 接入 `scrna-upstream-review` Work Item；
5. 设计“纳入/复查/排除候选”审批卡。

**验收**：两个样本的 FASTQ 能并行 `count`，汇总后不经审批不能进入整合节点；重投同一 node 不重复执行。

### Phase 2：整合、降维、聚类

1. 将现有 `scanpy-qc` 保留为兼容节点；
2. 新增 `scrna-integrate-cluster` executor；
3. 生成 QC、doublet、integration diagnostics、UMAP、marker 和 integrated h5ad；
4. 新增 `scrna-integration-review` 与聚类方案审批；
5. 为大规模数据设队列、资源 profile、参数限额和失败恢复。

**验收**：多样本数据能够完成两种候选整合方案的受控比较，并只有批准的 revision 标记为正式结果。

### Phase 3：注释验证与高级分析

1. 新增 marker/reference evidence schema；
2. 增加 annotation validation executor 与 AgentTeams review；
3. 先实现按细胞类型的 pseudobulk DE、富集和标准图表；
4. 轨迹作为 feature flag，必须经过“数据适用性 + 根节点”双审批；
5. 将结果打包为完整交付 manifest 与 runbook。

**验收**：每个 annotation 都有证据与置信度；DE 明确细胞类型、比较组、样本重复和协变量；未满足准入条件时轨迹节点自动阻断并要求人工复核。

### Phase 4：生产化与可观测性

1. Bridge Case Store 从文件实现迁移到持久化数据库；
2. 建立 Case/MAS Run/Task/Artifact 的可视化关联页；
3. 增加队列延迟、Cell Ranger 成功率、GPU/内存、artifact 大小、Gateway 成本监控；
4. 对参考版本升级、模型升级、pipeline revision 做回归测试；
5. 编写撤销、重跑、数据保留和灾备 runbook。

---

## 11. 关键风险与缓解措施

| 风险 | 表现 | 缓解 |
| --- | --- | --- |
| 上游原始数据量巨大 | FASTQ / reference / BAM 占满共享盘 | 预估磁盘、配额、TTL、按样本并发上限、分层存储。 |
| 参考版本漂移 | 不同项目不可比 | Reference registry + checksum + Cell Ranger version 固化。 |
| 过度整合 | 批次校正抹去真实生物学差异 | 必须输出整合前后诊断并人工批准。 |
| 伪重复 DE | 细胞当独立重复导致显著性虚高 | 有生物学重复时默认 pseudobulk。 |
| 轨迹过度解释 | UMAP 连续性被误解为时间 | 默认关闭，需准入条件和根节点审批。 |
| Agent 幻觉驱动执行 | 自由文本变成命令或参数 | 强制结构化 schema、Plan Validator、审批和允许值白名单。 |
| AgentTeams/MAS 双状态冲突 | Case 显示完成但 MAS 失败 | 以 MAS artifact 为计算真相，以 Case 为协作真相；通过幂等事件同步。 |
| 重复消息 | RocketMQ/Celery 重投导致重复计算 | 固定 idempotency key、node revision、artifact digest 和状态版本。 |

---

## 12. 最终建议

1. **采纳三段式单细胞 Agent 拆分。** 它符合单细胞方法学的自然阶段，也符合现有 MAS artifact DAG 和 AgentTeams Work Item 模型。
2. **不要把 AgentTeams 变成计算平台。** AgentTeams 应深度参与 Case 编排、领域审查、质量决策、人工审批和交付，不直接持有 Docker/Shell/数据卷权限。
3. **将现有 `agent-scrna` 先升级为“单细胞科学审查 Agent”。** 用 capability/skill 区分 upstream、integration、annotation、trajectory review；后续再按成本和治理需求拆成三个 identity。
4. **MAS 是唯一的工作流执行权威。** 上游 Cell Ranger、下游 Scanpy/Seurat、高级分析全部以明确 executor、artifact contract、资源队列和状态机执行。
5. **先做上游标准化和中游整合，再做高级分析。** 没有稳定 `raw_h5ad -> integrated_h5ad` 契约时，不应先上线注释验证或拟时序。
6. **将轨迹列为可选、高风险功能。** 不应作为默认“高级分析套餐”自动运行。

总体判断：**可以与 AgentTeams 深度整合，并作为 Multi-Agent 调度；推荐的深度是“协作、审查、审批、证据与交付深度整合”，而不是“让协作 Agent 获得原始数据和计算环境的直接执行权限”。**

---

## 13. 调查证据索引

- 单细胞 Agent 与提示词：`data/ai/scrna.yaml`、`data/ai/prompts/scrna.md`
- 单细胞 MAS 执行器：`src/omichub/infrastructure/mas/scanpy.py`、`src/omichub/infrastructure/celery_app/tasks/mas.py`
- MAS 能力、artifact 和策略：`data/ai/mas/agent_capabilities.yaml`、`data/ai/mas/artifact_schemas.yaml`、`data/ai/mas/tool_policies.yaml`
- MAS 调度与校验：`src/omichub/application/services/mas_scheduler_service.py`、`src/omichub/application/services/mas_plan_validator.py`、`src/omichub/domain/mas/models.py`
- 单细胞运行时：`deploy/runtime-images/scrna.Dockerfile`、`tool_configs/terminal/docker/Dockerfile.scrna`
- AgentTeams 团队边界：`integrations/agentteams/teams/bioops-delivery.yaml`
- AgentTeams Bridge 与技能契约：`integrations/agentteams/README.md`、`integrations/agentteams/skills/contracts.yaml`、`integrations/agentteams/bridge/`
- 受控科学咨询 Gateway：`integrations/agentteams/gateway/`
- OmicHub Case 代理与观察器：`src/omichub/application/services/agentteams_case_tool_service.py`、`src/omichub/application/services/agentteams_case_watch_service.py`
