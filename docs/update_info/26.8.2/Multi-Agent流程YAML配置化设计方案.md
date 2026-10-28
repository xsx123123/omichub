# Multi-Agent 流程 YAML 配置化设计方案

> 目标：把《单细胞 Agent 与 AgentTeams 深度整合调查报告（v1.1）》中为 scrna 设计的"三段流程 + 只读审查 + 人工审批 + MAS DAG"架构**抽象为通用流程模板**，新增流程（RNA-seq、ATAC-seq、WGS 等）只需新增一个 YAML 文件 + 实现对应 executor，不改动编排、审批、状态机核心代码。
> 版本：v1.0（2026-08-02）

---

## 1. 设计原则

1. **一个流程 = 一个 YAML**：`data/ai/flows/{flow_id}.yaml`，流程的阶段划分、executor、审查 skill、审批 gate、DAG 边、交付物全部在文件里声明。
2. **共性的东西不下放**：重试策略、审批模板、资源档位、artifact 类型库收敛到 `_shared/`，流程 YAML 只引用、不重复定义——避免每个流程各写一套导致行为漂移。
3. **安全边界是硬约束，不是配置项**：流程 YAML **只能声明只读 review skill**；Worker 的 `forbidden_capabilities`（无 Shell/Docker/DB/写文件）仍由 team 声明文件控制，YAML 配置无法为任何流程开可写权限。配置层永远不能突破架构层的安全模型。
4. **YAML 是唯一的注册入口**：启动时由 Flow Registry 解析校验后，**派生注册**到现有三处机制——MAS executor 能力表、AgentTeams skill contracts、Bridge 流程白名单。不再三处手工同步（现状白名单漏配 scrna 的事故即源于此）。
5. **先迁移 scrna 验证设计，再接新流程**：scrna 是第一个 dogfood 对象；schema 设计以"scrna 能无损表达 + RNA-seq 能不改 schema 表达"为验收线。

---

## 2. 目录结构

```text
data/ai/flows/
├── _shared/
│   ├── policies.yaml          # 重试策略、审批模板、超时规则
│   ├── resources.yaml         # 资源档位（CPU/内存/队列/并发上限）
│   └── artifact_types.yaml    # 媒体类型、大小上限、保留策略
├── scrna.yaml                 # 流程定义（v1.1 报告内容的配置化表达）
├── rnaseq.yaml                # 示例：第二个流程
└── index.yaml                 # 流程清单与启用开关（可选，默认可扫目录）
```

---

## 3. 流程定义 Schema

### 3.1 完整结构（以 scrna.yaml 为例）

```yaml
flow:
  id: scrna                      # 全局唯一，小写
  version: 1.1.0                 # 流程定义版本，变更即升版
  display_name: 单细胞转录组分析
  domain: scrna
  actor: agent-scrna             # AgentTeams identity（单 identity + 多 skill 模式）
  runtime_image: scrna           # 对应 deploy/runtime-images/scrna.Dockerfile
  bridge_workflow: scrna_seq     # 派生写入 Bridge 白名单的流程名
  trigger_hints:                 # 意图路由识别用（可选）
    - 单细胞
    - scRNA
    - cellranger

artifacts:                       # 本流程的 artifact 清单；类型规则引用 _shared
  - key: fastq_manifest
    type: json_manifest
  - key: raw_h5ad
    type: h5ad
    aliases: [input_h5ad]        # legacy 别名（对应调查报告 §5.4）
  - key: qc_filtered_h5ad
    type: h5ad
    aliases: [filtered_h5ad]
  - key: upstream_review
    type: review_report
  # ... 其余 artifact 同调查报告 §5.1–5.3

stages:
  - key: upstream
    title: 上游处理与样本 QC
    executors:
      - key: cellranger
        queue: scrna_upstream_highmem
        resource_profile: highmem_16c128g   # 引用 _shared/resources.yaml
        fan_out: per_sample                  # none | per_sample | per_group
        inputs: [fastq_manifest]
        outputs: [cellranger_outs, cellranger_metrics, sample_qc_report, raw_h5ad]
        retry_policy: infra_bounded          # 引用 _shared/policies.yaml
    review:                                  # 本阶段的只读审查（可选）
      skill: upstream-review
      inputs: [fastq_manifest, cellranger_metrics, sample_qc_report]
      output: upstream_review
    gate:                                    # 阶段出口的人工审批（可选）
      template: sample_inclusion
      required: true

  - key: integrate
    title: 下游整合、降维和聚类
    executors:
      - key: integrate_cluster
        queue: scrna_analysis_highmem
        resource_profile: highmem_32c256g
        inputs: [raw_h5ad, sample_inclusion_decision]
        outputs: [cell_qc_metrics, doublet_scores, qc_filtered_h5ad,
                  integration_diagnostics, integrated_h5ad,
                  cluster_markers, cluster_report, parameter_snapshot]
        retry_policy: infra_bounded
    review:
      skill: integration-review
      inputs: [cell_qc_metrics, integration_diagnostics, cluster_markers]
      output: integration_review
    gate:
      template: integration_approval
      required: true

  - key: advanced
    title: 注释验证与高级分析
    executors:
      - key: annotation_validate
        queue: scrna_analysis
        resource_profile: standard_8c32g
        inputs: [integrated_h5ad, cluster_markers]
        outputs: [annotation_evidence, annotation_validation_report, annotated_h5ad]
        retry_policy: infra_bounded
      - key: pseudobulk_de
        queue: scrna_analysis
        resource_profile: standard_8c32g
        inputs: [annotated_h5ad]
        outputs: [pseudobulk_counts, de_results, pathway_enrichment]
        retry_policy: infra_bounded
      - key: visualization
        queue: scrna_analysis
        resource_profile: standard_8c32g
        inputs: [annotated_h5ad, de_results]
        outputs: [visualization_bundle]
        retry_policy: infra_bounded
      - key: trajectory
        queue: scrna_analysis_highmem
        resource_profile: highmem_32c256g
        feature_flag: scrna_trajectory_enabled   # 默认关闭
        inputs: [annotated_h5ad]
        outputs: [trajectory_result]
        retry_policy: never
        admission:                               # 准入条件（可选）
          requires_approval: trajectory_root_direction
    review:
      skill: annotation-review
      inputs: [annotation_evidence, cluster_markers]
      output: annotation_review
    gate:
      template: annotation_revision
      required: true

edges:                             # DAG 依赖；delivery gate 是隐式汇聚节点
  - [upstream, integrate]
  - [integrate, advanced]

delivery:
  quality_gate: true               # 汇聚所有已启用末端分支（对应调查报告 §6.1 修正）
  outputs: [delivery_manifest, runbook]
```

### 3.2 共享策略库（`_shared/policies.yaml`）

```yaml
retry_policies:
  infra_bounded:                   # 调查报告 §9.3：基础设施失败限档内自动重试
    auto_retry_on: [oom, node_lost, queue_timeout]
    max_attempts: 2
    escalate: new_revision_requires_approval   # 升档/改参数 = 新 revision
  never:
    auto_retry_on: []

approval_templates:
  sample_inclusion:
    approvers: [project_owner]
    quorum: all                    # 多人 = 会签
    timeout_hours: 48
    on_timeout: remind_and_escalate
    never_auto_approve: true
    requires_reject_reason: true
  integration_approval:
    approvers: [project_owner]
    quorum: all
    timeout_hours: 48
    on_timeout: remind_and_escalate
    never_auto_approve: true
  annotation_revision:
    approvers: [project_owner]
    quorum: all
    timeout_hours: 48
    on_timeout: remind_and_escalate
    never_auto_approve: true
  trajectory_root_direction:
    approvers: [project_owner, domain_expert]
    quorum: all
    timeout_hours: 72
    on_timeout: remind_and_escalate
    never_auto_approve: true
```

资源档位（`_shared/resources.yaml`）定义 `standard_8c32g`、`highmem_16c128g`、`highmem_32c256g` 等命名的 CPU/内存/临时盘/单项目并发上限组合；artifact 类型库（`_shared/artifact_types.yaml`）定义 `h5ad`、`json_manifest`、`review_report`、`fastq`、`count_matrix` 等的媒体类型、大小上限与保留策略。

---

## 4. 加载、校验与派生注册

### 4.1 Flow Registry（新增，`src/omichub/application/services/flow_registry.py`）

启动时：

1. 扫描 `data/ai/flows/*.yaml`（跳过 `_shared/`）；
2. 用 Pydantic schema 校验每个文件（见 §4.2）；
3. 计算每个流程定义的 `flow_digest = sha256(规范化的 YAML)`，写入运行记录的 `parameter_set_digest` 同级字段，保证"跑的是哪版流程定义"可审计；
4. **派生注册**到三处现有机制：

| 派生目标 | 来源字段 | 替代的现状手工操作 |
| --- | --- | --- |
| MAS `agent_capabilities.yaml` + executor 路由 | `stages[].executors[]` | 手工注册 executor 枚举/Celery task 映射 |
| MAS `artifact_schemas.yaml` | `artifacts[]` + `_shared/artifact_types.yaml` | 手工维护 schema（含 legacy 别名） |
| AgentTeams `contracts.yaml` review skills | `stages[].review` | 手工声明 `scrna-*-review` 等 skill |
| Bridge 流程白名单 | `flow.bridge_workflow` | 手工改 `deploy/agentteams/bridge.env:7`（scrna 漏配的根因） |

派生注册是**生成/合并**而非覆盖：手工维护的既有条目保留，冲突时以 YAML 为准并输出 warning 日志。

### 4.2 校验规则（加载即失败，不进运行时）

- **schema 层**：必填字段、枚举值（`fan_out`、`quorum`）、类型；
- **引用完整性**：`resource_profile`、`retry_policy`、`gate.template` 必须存在于 `_shared/`；`inputs/outputs` 必须在本流程 `artifacts[]` 中声明；
- **DAG 合法性**：`edges` 无环；executor 的每个 input 要么是流程入口 artifact（首阶段输入），要么有上游 executor 产出；`delivery.quality_gate` 自动汇聚所有无出边的末端 executor；
- **安全护栏**：`review.boundary` 只能是 `read_only`；流程 YAML 出现任何可写能力声明（`shell`、`file_write`、`workflow_submit` 等）直接拒绝加载；
- **版本兼容**：`flow.version` 升级时，若删除/改名 artifact 而未在 `aliases` 中声明，校验失败——强制显式迁移。

### 4.3 运行时行为

- Case 创建时绑定 `flow_id + flow_version + flow_digest`；
- MAS Plan Validator 改为"对照流程定义校验"而非硬编码节点清单：节点是否在 stages 中、参数是否在 executor 声明的允许值内、gate 是否已满足；
- 状态机（Case ↔ Run 映射）保持流程无关，全部沿用调查报告 §6.2 的通用映射，**不进流程 YAML**——状态机是平台机制，不是流程差异点；
- 意图路由（此前优化建议的方案 A）用 `trigger_hints` 把用户输入匹配到 flow，命中后走该流程的 Case 确认卡。

---

## 5. 通用性验证：RNA-seq 流程示例

不改 schema、只写 YAML 即可表达第二个流程（骨架）：

```yaml
# data/ai/flows/rnaseq.yaml
flow:
  id: rnaseq
  version: 1.0.0
  display_name: bulk RNA-seq 差异分析
  domain: rnaseq
  actor: agent-rnaseq
  runtime_image: rnaseq
  bridge_workflow: rna_seq        # 已在 Bridge 白名单内
  trigger_hints: [RNA-seq, 转录组, 差异表达]

artifacts:
  - key: fastq_manifest
    type: json_manifest
  - key: quant_counts
    type: count_matrix
  - key: de_results
    type: de_table
  - key: upstream_review
    type: review_report
  - key: de_review
    type: review_report

stages:
  - key: quant
    title: 比对与定量
    executors:
      - key: star_salmon
        queue: rnaseq_highmem
        resource_profile: highmem_16c128g
        fan_out: per_sample
        inputs: [fastq_manifest]
        outputs: [quant_counts]
        retry_policy: infra_bounded
    review:
      skill: quant-review
      inputs: [fastq_manifest, quant_counts]
      output: upstream_review
    gate:
      template: sample_inclusion      # 直接复用共享审批模板
      required: true

  - key: de
    title: 差异分析与富集
    executors:
      - key: deseq2
        queue: rnaseq_analysis
        resource_profile: standard_8c32g
        inputs: [quant_counts]
        outputs: [de_results]
        retry_policy: infra_bounded
    review:
      skill: de-review
      inputs: [de_results]
      output: de_review
    gate:
      template: annotation_revision
      required: true

edges:
  - [quant, de]

delivery:
  quality_gate: true
  outputs: [delivery_manifest, runbook]
```

这个例子同时验证了：审批模板复用（`sample_inclusion` 跨流程通用）、两阶段 DAG（比 scrna 少一段）、无 feature flag 流程、以及白名单派生（`rna_seq` 自动确认在白名单内）。

---

## 6. 分阶段实施计划

### Phase A：Flow Schema + Registry + 校验器

1. 定义 Pydantic schema（流程、阶段、executor、review、gate、edges）；
2. 实现 Flow Registry 的扫描、校验、digest 计算；
3. 把 scrna v1.1 报告内容完整转写为 `flows/scrna.yaml`，**校验器全绿**作为验收。

**验收**：scrna YAML 加载通过；故意制造 6 类错误（环、未声明 artifact、可写能力、坏引用、缺 gate 模板、artifact 改名无别名）全部在加载期被拦截。

### Phase B：派生注册 + Plan Validator 改造

1. 实现到 MAS 能力表 / artifact schema / AgentTeams contracts / Bridge 白名单的四处派生注册；
2. MAS Plan Validator 从硬编码节点清单改为对照流程定义校验；
3. 回归：既有 rna_seq 硬编码路径与 YAML 派生路径行为一致。

**验收**：scrna Case 经 YAML 定义走通 preflight → review → approval → delivery（可先无真实 executor，用 mock）；`bridge.env` 不再手工维护流程清单。

### Phase C：RNA-seq 迁移（通用性验证）

1. 按 §5 编写 `flows/rnaseq.yaml`；
2. 只实现/适配 executor，编排与审批零代码改动；
3. 跑通一个真实 RNA-seq Case。

**验收**：新增流程的总改动 = 1 个 YAML + executor 实现，核心服务代码零变更。

### Phase D：管理面与更多流程

1. 管理后台流程清单页：展示已加载流程、版本、digest、校验状态；
2. ATAC-seq / WGS 等按同样方式接入；
3. （可选）YAML 的可视化 DAG 预览与编辑。

---

## 7. 可直接粘贴给编码 Agent 的提示词

```text
在现有 OmicHub MAS + AgentTeams 架构上实现"流程 YAML 配置化"，禁止改动 Worker 权限模型、
Case/Run 状态机和既有 4 条多 Agent 协作路径的内部实现，只在上方加流程定义层。

背景：当前每个分析流程（scrna、rnaseq）的 DAG、executor、review skill、审批点、artifact
schema 分散硬编码在 mas 配置、contracts.yaml 和 bridge.env 中，新增流程要改多处且已经出
过 scrna 白名单漏配事故。目标：一个流程 = data/ai/flows/{flow_id}.yaml 一个文件。

具体要求：
1. 新建 src/omichub/application/services/flow_registry.py：启动时扫描 data/ai/flows/
   （跳过 _shared/），用 Pydantic 校验并计算每个流程的 sha256 digest。schema 与校验规则
   按设计文档 §3、§4.2 实现，特别包括：edges 无环、inputs/outputs 引用已声明 artifact、
   review.boundary 仅允许 read_only、出现可写能力声明直接拒绝加载。
2. 实现派生注册（§4.1 表格）：从 YAML 生成/合并 MAS agent_capabilities、artifact_schemas
   （含 aliases）、AgentTeams review skill contracts、Bridge 流程白名单；手工既有条目保留，
   冲突以 YAML 为准并打 warning。
3. MAS Plan Validator 从硬编码节点清单改为对照流程定义校验。
4. 把 scrna 流程按设计文档 §3.1 转写为 flows/scrna.yaml 作为首个迁移对象；按 §5 编写
   flows/rnaseq.yaml 骨架验证 schema 通用性。
5. _shared/ 下落地 policies.yaml（retry/approval 模板）、resources.yaml（资源档位）、
   artifact_types.yaml（类型库），内容按设计文档 §3.2。
6. 测试：6 类非法 YAML（环、未声明 artifact、可写能力、坏模板引用、缺 gate 模板、
   artifact 改名无别名）必须在加载期报错；scrna/rnaseq 两个 YAML 加载全绿。

完成后请说明：派生注册与手工既有配置的合并策略、digest 在运行记录中的落点。
```

---

## 8. 风险与边界

| 风险 | 缓解 |
| --- | --- |
| YAML 表达能力不足，特殊流程塞不进 schema | schema 保留 `extensions` 透传字段；连续两个流程需要同一扩展时再升格为一等字段 |
| 配置即代码，错误配置直接炸启动 | 加载期全量校验 + 单流程失败不影响其他流程加载（隔离降级）+ digest 审计 |
| 流程 YAML 被当作提权通道 | 安全护栏硬编码在校验器里（可写能力一律拒载），不进配置 |
| 共享模板被改影响所有流程 | `_shared/` 变更要求单独评审 + 所有引用流程的回归测试 |
| 状态机被塞进流程配置导致分裂 | 明确纪律：Case/Run 状态机是平台机制，流程 YAML 不承载 |
