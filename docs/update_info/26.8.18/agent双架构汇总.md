# Agent 双架构汇总

> 本文档汇总 OmicHub 协作室中并行的两套 Agent 架构：
> - **架构 A：Agent 多智能体编排系统**（基于 LangGraph）— AI 层的智能体对话、意图路由与跨 Agent 协调
> - **架构 B：FlowFrame 流程流水线框架**（基于 Snakemake）— 计算层的批量生物信息学分析流水线
> 
> 两套架构通过 MCP Server、Bridge Service、API 层相互集成，形成完整的多模态生信分析平台。

---

## 目录

1. [架构概览：双轨并行](#1-架构概览双轨并行)
2. [架构 A：Agent 多智能体编排系统](#2-架构-aagent-多智能体编排系统)
3. [架构 B：FlowFrame 流程流水线框架](#3-架构-bflowframe-流程流水线框架)
4. [两套架构如何协作](#4-两套架构如何协作)
5. [关键文件索引](#5-关键文件索引)
6. [架构对比矩阵](#6-架构对比矩阵)

---

## 1. 架构概览：双轨并行

```
┌──────────────────────────────────────────────────────────────────┐
│                       用户界面 (Vue Frontend)                      │
│              协作室聊天 / AI工作台 / 分析中心 / 数据管理             │
└─────┬──────────────────────────┬─────────────────────────────────┘
      │                          │
┌─────▼──────────────┐  ┌───────▼────────────────────────────────┐
│  架构 A: Agent 编排   │  │           架构 B: FlowFrame            │
│  (AI 决策层)         │  │        (计算执行层)                    │
│                      │  │                                        │
│ • LangGraph Engine  │  │ • Snakemake DAG                        │
│ • LLM 推理规划       │  │ • 模块化规则链                          │
│ • Intent Routing     │  │ • 通用+组学专用分层                     │
│ • Agent Handoff      │  │ • Rust 工具链 (MD5/QC)                │
│ • MAS Orchestrator   │  │ • Conda/Docker 依赖管理               │
│ • Collaboration Room │  │ • HPC 集群调度                         │
└──────────────────────┘  └────────────────────────────────────────┘
      │                          │
      │  MCP Tool Call           │  API Gateway
      │  rnaflow_*               │  POST /api/v1/workflows
      ▼                          ▼
┌──────────────────────────────────────────────────────────────────┐
│                     基础设施层                                     │
│   Redis / Celery / PostgreSQL / Matrix / K8s / HPC Cluster       │
└──────────────────────────────────────────────────────────────────┘
```

### 核心分工

| 维度 | 架构 A — Agent 编排 | 架构 B — FlowFrame |
|------|---------------------|---------------------|
| **定位** | AI 决策层：理解用户需求 → 制定计划 → 调度资源 | 计算执行层：按既定 DAG 高效执行科学计算 |
| **引擎** | LangGraph (状态机 + LLM 节点) | Snakemake (DAG 构建器 + 规则引擎) |
| **智能程度** | 高 — LLM 可根据上下文动态调整策略 | 低 — YAML 定义的规则是确定的、可复现的 |
| **输出** | 计划、建议、解读、对话回复 | 定量矩阵、差异表、聚类结果、可视化图表 |
| **语言** | Python (FastAPI / LangGraph) | Snakefile (Python DSL) + R/Python/Bash 脚本 |
| **适用场景** | 需求澄清、方案设计、结果解读、异常处理 | 标准化的大批量数据分析 |

---

## 2. 架构 A：Agent 多智能体编排系统

### 2.1 设计哲学

让每个 Agent 专精一个领域，由 Manager (Orchestrator) 根据任务类型动态分配角色。Agent 之间可以通过 handoff 机制转介任务。

### 2.2 架构图

```
用户消息
    │
    ▼
┌─────────────────────────────────────────┐
│           Intent Router                  │
│  文本匹配 → Flow ID / Domain Registry    │
└────────────────┬────────────────────────┘
                 │
          ┌──────▼──────┐
          │Lead Planner  │ ← DOMAIN_HINTS 评分
          │ 选择         │   rnaseq→agent-rnaseq
          └──────┬──────┘
                 │
    ┌────────────▼─────────────┐
    │   Research Phase         │
    │   KB + Web + Model       │
    └────────────┬─────────────┘
                 │
    ┌────────────▼─────────────┐
    │   Plan Builder           │
    │   DAG 规划工作项          │
    └────────────┬─────────────┘
                 │
    ┌────────────▼─────────────┐
    │   Agent Teams Bridge     │
    │   Matrix Room 创建       │
    │   Work Item 分发         │
    └────────────┬─────────────┘
                 │
    ┌────────────▼─────────────┐
    │   Worker Execution       │
    │   agent-rnaseq / viz ... │
    │   可选调用 FlowFrame     │
    └──────────────────────────┘
```

### 2.3 Agent 注册表（共 15+ Agent）

来自 `data/ai/*.yaml` 配置文件和 `integrations/agentteams/teams/bioops-delivery.yaml`：

| Agent ID | Name | 领域 | Skill | 是否 Planning Eligible |
|----------|------|------|-------|----------------------|
| `agent-general` | 通用助手 | 全领域 | Requirements clarification, cross-domain synthesis | ✅ |
| `agent-rnaseq` | RNA-seq 分析师 | Bulk RNA-seq | rnaflow, deg, enrichments, wgcna, rmats | ✅ |
| `agent-viz` | 可视化助手 | 可视化 | visualization-review, figure-specification | ❌ |
| `agent-code` | 代码助手 | 编程/脚本 | code-review, reproducibility-advice | ❌ |
| `agent-data` | 数据管家 | 数据预检 | project-preflight, evidence-retrieval | ❌ |
| `agent-qc` | 质量审计员 | 质量控制 | quality-gate, artifact-inspect | ❌ |
| `agent-delivery` | 交付报告员 | 产物交付 | delivery-pack, runbook-capture | ❌ |
| `agent-scrna` | 单细胞分析师 | scRNA-seq | scrna-interpretation, cell-annotation-advice | ❌ |
| `agent-scrna-upstream` | 单细胞上游 | QC/Count | scrna-upstream-qc, cellranger-advice | ❌ |
| `agent-scrna-integration` | 单细胞整合 | Batch Correction | scrna-integration, batch-correction-advice | ❌ |
| `agent-scrna-advanced` | 单细胞高级 | Annotation/Trajectory | scrna-annotation, trajectory-and-communication | ❌ |
| `agent-atacseq` | ATAC-seq 分析师 | 染色质可及性 | atacseq-planning-advice, peak-interpretation | ❌ |
| `agent-cloud-ops` | 云运维专家 | 平台健康 | platform-health, incident-triage, rollback-plan | ❌ |
| `agent-mcp-builder` | MCP 构建师 | MCP Schema | mcp-schema-review, mcp-reproducibility | ❌ |
| `orchestrator` | 多智能体编排器 | MAS Orchestration | 无独立技能，协调者角色 | N/A (仅 Feature Flag 启用时) |

### 2.4 每个 Agent 的配置结构

以 `general.yaml` 为例 (`data/ai/general.yaml`)：

```yaml
# === 基本信息 ===
agent_id: agent-general
name: 通用助手
description: 覆盖日常问答与通用生信咨询的全能助手。
model: qwen3.7-plus              # 底层 LLM 模型
temperature: 0.7
max_tokens: 32768

# === Prompt & Skills ===
prompt_file: prompts/general.md
skill_ids: [atac-tools, blast, data-deliver, ..., wgcna]  # 24 个工具技能
mcp_ids: []                      # MCP Server 引用
tool_packs: [workspace, research, memory, handoff, subagents, agentteams_case, cloud_ops]

# === AgentTeams 运行时特性 ===
features:
  internal_case_role: agent-general
  agentteams:
    category: expert                   # expert | generalist | specialist
    recruitable: true                  # 可被 Manager 招募
    planner_eligible: true             # 可作为 Lead Planner
    execution_modes: [readonly_consultation, workspace_execution]
    max_parallel_work_items: 2         # 最大并行工作项数
    work_item_timeout_sec: 1800        # 单项超时
  engine: langgraph                    # ⭐ 执行引擎
  managed_prompt: true                 # 使用受控 Prompt 系统
  subagents_spawnable: true            # 可派生子 Agent

# === Persona ===
persona:
  archetype: "好奇而结构化的研究顾问"
  traits: [好奇, 结构化, 善于追问, 擅长综合]
  working_style: "先澄清目标...再连接信息"

# === Studio 配置 ===
studio:
  enabled: true
  default_mode: studio                 # 默认进入 AI 工作台
  runtime_profile: analysis-core
  required_capabilities: [python, r, bash]
```

### 2.5 LangGraph 引擎的关键字段

```yaml
engine: langgraph                    # 声明 LangGraph 作为运行时引擎
managed_prompt: true                 # 使用集中式 Prompt 管理
managed_profile: true                # 使用集中式 Profile 管理 (部分 Agent)
subagents_spawnable: true            # 支持 fan-out 派生子 Agent
mas_orchestrator: true               # 多智能体编排模式 (仅 orchestrator.yaml)
requires_plan_confirmation: true     # 需要人工确认计划 (仅 orchestrator.yaml)
```

### 2.6 Agent 间的协作方式

#### 方式一：Handoff (转介)

每个 Agent 定义 `handoff.allowed_targets`：

```yaml
# rnaseq.yaml
handoff:
  allowed_targets: [agent-viz, agent-code, agent-general, agent-atacseq]
  max_hops_per_session: 10

# general.yaml
handoff:
  allowed_targets: ["*"]  # 可转介给任何 Agent
```

#### 方式二：Parallel Sub-Agents

具有 `subagents_spawnable: true` 的 Agent 可以被 Manager 作为并行子 Agent 派生。

#### 方式三：AgentTeams Case (协作房间)

当任务需要多个 Agent 协同完成时，Manager 创建 Matrix Room，将各 Agent 招募为 Worker。

### 2.7 MAS Orchestrator — 超级协调者

**文件**: `data/ai/orchestrator.yaml`

```yaml
agent_id: agent-orchestrator
description: 将用户确认的复合分析意图转换为受限、可审计的 DAG 计划草稿。
features:
  mas_orchestrator: true           # 多智能体编排模式开关
  requires_plan_confirmation: true # 必须用户确认后执行
```

这是一个特殊 Agent，仅在 MAS Feature Flag 打开时使用。它不直接做分析，而是生成可审查的 DAG 计划。

---

## 3. 架构 B：FlowFrame 流程流水线框架

### 3.1 设计哲学

**共享骨架，分化分析** — 通用入口、配置、MD5 校验、QC、交付、报告为通用层；mapping/count/variant 为组学专用层。

### 3.2 Flow 家族成员

| 流程 | 组学场景 | 核心分析层 | 状态 | Flow 定义文件 |
|------|----------|------------|------|--------------|
| **RNAFlow** | Bulk RNA-seq | STAR → RSEM → DEG → variant → rMATS | 生产 | `flows/rnaseq.yaml` |
| **SCRNAFlow** | 单细胞 RNA | Cell Ranger / dnbc4tools → count matrix | 生产 | — |
| **BTCRFlow** | Bulk BCR/TCR | cutadapt → MiXCR → VDJtools diversity | 生产 | — |
| **ATACFlow** | 染色质可及性 | Bowtie2 → MACS2/3 peak → consensus → motif | 生产 | `flows/atacseq.yaml` |
| **WGSFlow** | 全基因组 | BWA → GATK → CNV/SV | 规划中 | — |
| **TreePlot** | 系统发育树 | IQ-TREE → ggtree 渲染 | 生产 | `flows/treeplot.yaml` |

### 3.3 标准目录结构（强制规范）

所有 Flow 仓库遵循统一目录树 (`Protocol/FlowFrame/flow-framework/references/flow_framework_spec.md §1.3`)：

```
<X>Flow/
├── snakefile                        # 入口（严格 8 步初始化序列）
├── config/
│   ├── config.yaml                  # 默认配置
│   ├── reference.yaml               # 参考基因组路径
│   ├── run_parameter.yaml           # 运行参数
│   └── cluster_config.yaml          # HPC 资源 profile
├── examples/
│   └── analysisyaml.example.yaml    # 项目级配置示例
├── schema/
│   └── config.schema.yaml           # JSON Schema 验证
├── rules/
│   ├── 01.common.smk                # 导入 + logger（无业务 rule）
│   ├── 02.file_convert_md5.smk      # FASTQ 标准化 + MD5 校验
│   ├── 03.short_read_qc.smk         # FastQC + MultiQC
│   ├── 04.*.smk ~ N-2.*.smk         # 组学专用层
│   ├── subrules/                    # 可选：可替换子规则
│   ├── N-1.deliver.smk              # 交付
│   ├── N.Report.smk                 # 报告
│   └── utils/
│       ├── common.py                # AnalysisTargets + DataDeliver
│       ├── datadeliver.py           # 模块目标收集器
│       ├── id_convert.py            # 样本表/对比表解析
│       ├── validate.py              # 配置验证
│       ├── reference_update.py      # 参考路径解析
│       └── resource_manager.py      # HPC 资源 profile
├── src/                             # Git submodule → JZ_Tools (Rust 工具)
├── report/                          # Git submodule → bioreport
├── envs/                            # Conda 环境 YAML
├── scripts/                         # 组学专用 R/Python 脚本
└── container_env/                   # Git submodule → Flowcontainer (可选)
```

### 3.4 Snakefile 8 步初始化序列（强制）

```python
from snakemake.utils import validate, min_version
min_version("9.9.0")

# Step 1: 导入框架工具
from rules.utils.id_convert import load_samples, load_contrasts
from rules.utils.validate import load_user_config, validate_genome_version
from rules.utils.reference_update import resolve_reference_paths
from rules.utils.resource_manager import rule_resource

# Step 2: 加载默认四件套
configfile: "config/config.yaml"
configfile: "config/reference.yaml"
configfile: "config/run_parameter.yaml"
configfile: "config/cluster_config.yaml"

# Step 3: 用户 analysisyaml 覆盖（最高优先级）
load_user_config(config, cmd_arg_name="analysisyaml")

# Step 4: 解析参考基因组路径
resolve_reference_paths(config, index_keys=[...])

# Step 5: Schema 验证
validate(config, "schema/config.schema.yaml")

# Step 6: 工作目录重定向
workdir: config["workflow"]

# Step 7: 加载样本表
SAMPLES = load_samples(config, required_columns=["sample", "sample_name", "group"])

# Step 8: 包含规则 + 动态目标
include: "rules/01.common.smk"
include: "rules/02.file_convert_md5.smk"
include: "rules/03.short_read_qc.smk"
# ... 组学专用规则 ...
include: "rules/N-1.deliver.smk"
include: "rules/N.Report.smk"

ALL_TARGETS = DataDeliver(config, SAMPLES, GROUPS, CONTRASTS)
rule all: input: ALL_TARGETS
```

### 3.5 通用层 vs 组学专用层（分层架构）

```
┌─────────────────────────────────────────────────────────────────┐
│                     通用层（所有 Flow 共享）                      │
│  01.common.smk       → Import + Logger 初始化                   │
│  02.file_convert_md5 → seq_preprocessor (Rust) + MD5 Verify     │
│  03.short_read_qc    → FastQC + MultiQC + FastQ Screen          │
│  N-1.deliver.smk     → 产物打包交付                              │
│  N.Report.smk        → HTML 交互式报告                           │
└────────────────────────┬────────────────────────────────────────┘
                         │ 从 04 开始分化
┌────────────────────────▼────────────────────────────────────────┐
│                     组学专用层                                    │
│                                                                 │
│  RNAFlow:                                                     │
│  04.Contamination → 05.fastp clean → 06.STAR mapping → 07.RSEM  │
│  → 08.GATK variant → 09.StringTie → 10.DEG → 11.rMATS → 12.Fusion
│                                                                 │
│  ATACFlow:                                                    │
│  04.Contamination → 05.fastp clean → 06.Bowtie2 → dedup → 07.MACS2
│  → HOMER annotation → consensus peaks → 09.ATAC QC → 10.DEG → 11.TOBIAS
│                                                                 │
│  TreePlot:                                                    │
│  plot stage → phylogenetic_tree executor (IQ-TREE + ggtree)     │
└─────────────────────────────────────────────────────────────────┘
```

### 3.6 目标生成系统（核心架构）

**文件**: `rules/utils/common.py`

```python
# 模块依赖图（每个流程自定义）
MODULE_DEPENDENCIES = {
    "mapping": ["qc_clean", "trimming"],
    "count": ["mapping"],
    "deg": ["count"],
}

# 模块收集器注册表
MODULE_COLLECTORS = {
    "qc_clean": datadeliver.qc_clean,
    "mapping": datadeliver.mapping,
    "deg": datadeliver.deg,
}

def AnalysisTargets(config, samples, groups, contrasts):
    """计算所有启用的分析模块的中间目标"""
    targets = [md5_json, md5_check]  # 固定门控目标
    enabled = _resolve_enabled_modules(config)
    for module in enabled:
        collector = MODULE_COLLECTORS[module]
        targets = collector(samples, targets, config, groups, contrasts)
    return targets

def DataDeliver(config, samples, groups, contrasts):
    """最终目标生成器"""
    targets = AnalysisTargets(...)
    if config.get("deliver"): targets.extend(delivery_outputs(config))
    if config.get("report"):  targets.extend(report_outputs(config))
    return targets
```

### 3.7 Rust 工具链

FlowFrame 在输入端使用两个 Rust 编写的性能工具（源码在 JZ_Tools submodule 中）：

| 工具 | 功能 | 实现语言 |
|------|------|---------|
| `seq_preprocessor` | FASTQ 标准化命名（零拷贝 symlink）+ MD5 审计 | Rust |
| `json_md5_verifier` | 多线程并行 MD5 校验（Rayon）+ 硬性门控 | Rust |

```text
raw_data_path (任意命名的原始 FASTQ)
    │
    ▼ seq_preprocessor
link_dir/{sample}/{sample}_R1.fq.gz  + raw_data_md5.json
    │
    ▼ json_md5_verifier (多线程 Rayon)
01.qc/md5_check.tsv  ← 硬性门控（失败则中止全流程）
    │
    ▼ 下游规则（依赖 md5_check.tsv 作为 input gate）
```

### 3.8 配置系统（六层优先级）

```
config/config.yaml          ← 最低 (仓库默认)
  ← config/reference.yaml   (参考基因组)
  ← config/run_parameter.yaml (运行参数)
  ← config/cluster_config.yaml (资源 profile)
  ← analysisyaml            ← 项目级 (用户覆盖)
  ← --config key=value      ← 命令行 (最终覆盖)
```

### 3.9 RNAFlow 典型分析步骤

```
02.file_convert_md5  → FASTQ 标准化 + MD5 校验 (Rust)
    ↓
03.short_read_qc     → FastQC + MultiQC + FastQ Screen (可选)
    ↓
04.Contamination     → 宿主污染检测
    ↓
05.fastp clean       → Adapter trimming + QC filtering
    ↓
06.STAR mapping      → 比对到参考基因组 (线程池: very_high_resource)
    ↓
07.RSEM count        → 基因/转录本定量
    ↓
08.GATK variant      → SNP/Indel 变异检测 (可选)
    ↓
09.StringTie         → 可变剪接检测 (可选)
    ↓
10.DEG/Enrichments   → DESeq2 差异分析 + GO/KEGG 富集
    ↓
11.rMATS             → 可变剪接定量 (可选)
    ↓
12.Fusion            → 融合基因检测 (可选)
    ↓
13.deliver           → 产物打包 (manifest + MD5 + log)
    ↓
14.Report            → HTML 交互式报告 (bioreport 容器)
```

### 3.10 TreePlot 分析步骤

```
plot stage (single stage, flow/treeplot.yaml)
    │
    ▼ phylogenetic_tree executor (workspace_execution)
    │
    ├─ 扫描 FASTA 序列
    ├─ Diamond/HMMER 同源检索
    ├─ MAFFT 多序列比对
    ├─ IQ-TREE 模型测试 + ML 建树 (ultrafast bootstrap)
    ├─ ggtree 可视化渲染
    └─ 产出: Newick/treefile + PDF + PNG
```

---

## 4. 两套架构如何协作

### 4.1 集成拓扑

```
用户在协作室发消息 → "帮我进行rna-seq分析"
    │
    ▼
┌──────────────────────────────────────────────┐
│              架构 A (Agent 编排)               │
│                                              │
│  1. Intent Router → rnaseq                   │
│  2. Lead Planner Selector → agent-rnaseq     │
│  3. Create AgentTeams Case                   │
│  4. Work Item: plan-01 → agent-rnaseq        │
│                                              │
│  agent-rnaseq 内部通过 MCP Tool 调用:          │
│  ├── check_workspace_data                    │
│  ├── rna_seq_prepare                         │
│  └── rna_seq_submit                          │
└──────────────────────┬───────────────────────┘
                       │ MCP Tool Call
                       ▼
┌──────────────────────────────────────────────┐
│              架构 B (FlowFrame)               │
│                                              │
│  RNAFlow/MCP Server (pipelines/RNAFlow/mcp/)  │
│  ├── list_supported_genomes_tool             │
│  ├── get_config_template_tool                │
│  ├── setup_complete_project_tool             │
│  ├── validate_config_tool                    │
│  └── run_rnaflow_tool                        ← Snakemake 执行
│                                              │
│  run_rnaflow_tool 内部:                       │
│    snakefile (snakefile)                      │
│      └─ Snakemake DAG → HPC Job Submission   │
│          └─ STAR/RSEM/DESeq2/ggtree ...       │
└──────────────────────────────────────────────┘
                       │
                       ▼
              产出结果回传给 agent-rnaseq
              → 解读结论 → 回复用户
```

### 4.2 协作模式总结

| 模式 | 触发条件 | 架构 A 做什么 | 架构 B 做什么 |
|------|---------|--------------|--------------|
| **纯咨询** | 无附件或纯问题 | LLM 解答原理/方案 | 不调用 |
| **方案设计** | 有附件但要求设计 | 制定分阶段方案、推荐工具 | 不调用 |
| **快速演示** | 用户要求示例数据演示 | 加载内置示例数据展示 | 可能触发最小 dry-run |
| **正式分析** | 用户明确要求实际分析 | 创建 Case → 提交 RNAFlow | 执行完整流水线 |
| **结果解读** | 分析完成后 | LLM 解读 DEG/富集结果 | 不调用 |
| **可视化** | 要求画图 | 分配 agent-viz → ggtree | 可能触发 TreePlot Flow |

### 4.3 桥接点详解

#### 桥接点 1: MCP Server

**文件**: `pipelines/RNAFlow/mcp/main.py`

RNAFlow 通过 FastMCP 暴露 20+ 工具函数给 Agent 调用。这些工具封装了底层的 Snakemake 流水线：

```python
@mcp.tool()
async def run_rnaflow_tool(
    config_path: str, cores: int = 20,
    dry_run: bool = False, user_confirmed: bool = False
) -> str:
    """Submit RNAFlow pipeline for execution"""
    return await run_rnaflow(config_path, cores, dry_run, ...)
```

Agent 通过 MCP 协议调用 `run_rnaflow_tool()`，等价于触发架构 B 的流水线。

#### 桥接点 2: Flow YAML 映射

**文件**: `data/ai/flows/rnaseq.yaml`, `data/ai/flows/treeplot.yaml`

每个 Flow 在 Agent 侧有一个轻量级的映射定义：

```yaml
# rnaseq.yaml (Agent 视角)
flow:
  id: rnaseq
  actor: agent-rnaseq
  bridge_workflow: rna_seq  ← 映射到具体 Pipeline
stages:
  - key: quantify
    executors:
      - key: rnaflow
  - key: differential
    executors:
      - key: deseq2
```

这是 Agent 层对 FlowFrame 的**抽象视图**——只暴露 2 个逻辑阶段，隐藏了内部的 14 个实际 Snakemake step。

#### 桥接点 3: Bridge Service

**文件**: `integrations/agentteams/bridge/omichub_agentteams_bridge/service.py`

Bridge 在 Agent 和 Pipeline 之间担任中介角色：

```python
# Bridge 硬编码的工作项创建
await self._ensure_work_item(case_id, work_item_id="quality-01",
    target="quality-auditor")      # 走 Agent 通道
await self._ensure_work_item(case_id, work_item_id="plan-01",
    target="agent-rnaseq")         # 触发 MCP → FlowFrame
```

#### 桥接点 4: Workflow Monitor 推送

**文件**: `Protocol/FlowFrame/flow-framework/references/flow_framework_spec.md §13.5`

FlowFrame 运行时可通过 `snakemake_logger_plugin_rich_loguru` 插件将进度推送到 OmicHub 平台，让架构 A 实时感知流水线状态：

```python
# FlowFrame monitor 推送
omichub_monitor_url: "https://omichub.example.edu/api/v1/workflow-monitor/events"
omichub_task_id: "rna_seq_abc123"
omichub_flow_id: "rna_seq"
```

### 4.4 何时用哪个架构

| 任务类型 | 推荐架构 | 原因 |
|---------|---------|------|
| "什么是 DESeq2？" | 架构 A | 概念解释，无需计算 |
| "这个 DEG 结果的生物学意义是什么？" | 架构 A | LLM 解读 + 知识库 |
| "给我画个火山图" | 架构 A → 架构 B | Agent-viz 生成代码 → ggtree/绘图 |
| "帮我分析这 20 个 sample 的差异表达" | 架构 A + B | 需启动 RNAFlow 流水线 |
| "帮我建一棵进化树" | 架构 A + B | 需 IQ-TREE 计算 |
| "检查数据质量" | 架构 A + B | 触发 RNAFlow QC 层 |
| "我的 pipeline 为什么跑失败了？" | 架构 A + B | Agent 解读日志 → 排查 FlowFrame |

---

## 5. 关键文件索引

### 架构 A 相关文件

| 文件 | 用途 |
|------|------|
| `data/ai/general.yaml` | 通用助手配置 |
| `data/ai/rnaseq.yaml` | RNA-seq 分析师配置 |
| `data/ai/viz.yaml` | 可视化助手配置 |
| `data/ai/code.yaml` | 代码助手配置 |
| `data/ai/scrna.yaml` | 单细胞分析师配置 |
| `data/ai/atacseq.yaml` | ATAC-seq 分析师配置 |
| `data/ai/orchestrator.yaml` | MAS Orchestrator 配置 |
| `data/ai/_overdrive_limits.yaml` | Overdrive 限制配置 |
| `data/ai/providers.yaml` | LLM Provider 配置 |
| `data/ai/router.yaml` | Agent 路由配置 |
| `data/ai/studio.yaml` | Studio 会话配置 |
| `data/ai/domains/omics.yaml` | 组学领域规则 |
| `data/ai/domains/phylo.yaml` | 系统发育领域规则 |
| `src/omichub/application/services/agentteams_room_response_service.py` | Manager 回复回路 |
| `src/omichub/application/services/agentteams_execution_intent.py` | 执行意图检测 |
| `src/omichub/application/services/agentteams_intent_router.py` | 意图路由 |
| `src/omichub/application/services/overdrive_planning_service.py` | Lead Planner 选择 + DAG |
| `src/omichub/application/services/agentteams_capability_registry.py` | Role → Agent 映射 |
| `src/omichub/api/v1/agentteams.py` | REST API 入口 |
| `integrations/agentteams/teams/bioops-delivery.yaml` | Worker 注册表 |

### 架构 B 相关文件

| 文件 | 用途 |
|------|------|
| `Protocol/FlowFrame/flow-framework/references/flow_framework_spec.md` | 框架规范 v2.0 (完整参考) |
| `Protocol/FlowFrame/flow-framework/SKILL.md` | SKILL 文档 |
| `Protocol/FlowFrame/flow-framework/assets/templates/snakefile` | Snakefile 模板 |
| `Protocol/FlowFrame/flow-framework/assets/templates/rules/01.common.smk` | 通用规则 01 |
| `Protocol/FlowFrame/flow-framework/assets/templates/rules/02.file_convert_md5.smk` | 通用规则 02 |
| `Protocol/FlowFrame/flow-framework/assets/templates/rules/03.short_read_qc.smk` | 通用规则 03 |
| `pipelines/RNAFlow/snakefile` | RNAFlow 入口 |
| `pipelines/RNAFlow/mcp/main.py` | RNAFlow MCP Server (20+ 工具) |
| `pipelines/RNAFlow/mcp/services/snakemake.py` | Snakemake 执行器 |
| `pipelines/RNAFlow/report/bioreport/` | 报告生成引擎 |
| `data/ai/flows/rnaseq.yaml` | RNAFlow Agent 侧映射 |
| `data/ai/flows/treeplot.yaml` | TreePlot Agent 侧映射 |

---

## 6. 架构对比矩阵

| 维度 | 架构 A: Agent 编排 | 架构 B: FlowFrame |
|------|-------------------|-------------------|
| **核心引擎** | LangGraph + LLM | Snakemake + Python DSL |
| **输入** | 自然语言消息 | FASTQ/FASTA + 配置文件 |
| **输出** | 对话回复 / 计划 / DAG | 定量矩阵 / DEG表 / 图表 |
| **决策方式** | LLM 推理 + domain rules | YAML 静态规则 |
| **可复现性** | ⚠️ LLM 随机性（temperature） | ✅ 确定性强复现 |
| **灵活性** | 🟢 高 — 可应对新场景 | 🔒 低 — 预定义的 rule |
| **扩展方式** | 新增 agent YAML / skill | 新增 rules/*.smk / envs |
| **硬件依赖** | GPU/LLM 调用次数 | CPU/内存/磁盘 |
| **执行时间** | 秒~分钟级 (对话响应) | 小时~天级 (大规模计算) |
| **错误处理** | LLM 重试 + prompt 迭代 | Snakemake retry + resume |
| **监控能力** | Agent status lines / trace | rich-loguru → OmicHub |
| **团队规模** | 15+ Agent 可并发 | 支持 HPC 集群分布式 |
| **主要用户** | 所有用户（对话交互） | 数据科学家/生物信息学家 |
| **配置驱动** | `data/ai/*.yaml` | `config/*.yaml` + `analysisyaml` |
| **Skill/Rule 体系** | Skill 包 (24+ 工具) | Snakemake Rule 链 (10-14 steps) |
| **持久化存储** | Redis (state) + DB (case) | 文件系统 (outputs/) |
| **认证/权限** | AgentTeams auth tokens | Platform API key + RBAC |

---

## 附录 A: Agent 完整配置清单

来自 `data/ai/*.yaml`（共 22 个 Agent 配置文件）：

| 文件名 | Agent ID | 是否有 engine: langgraph | 是否有 managed_prompt |
|--------|----------|------------------------|---------------------|
| general.yaml | agent-general | ✅ | ✅ |
| rnaseq.yaml | agent-rnaseq | ✅ | ✅ |
| viz.yaml | agent-viz | — | ✅ |
| code.yaml | agent-code | — | ✅ |
| scrna.yaml | agent-scrna | ✅ | — |
| scrna_upstream.yaml | agent-scrna-upstream | ✅ | — |
| scrna_integration.yaml | agent-scrna-integration | ✅ | — |
| scrna_advanced.yaml | agent-scrna-advanced | ✅ | — |
| atacseq.yaml | agent-atacseq | ✅ | ✅ |
| qc.yaml | agent-qc | ✅ | ✅ |
| delivery.yaml | agent-delivery | ✅ | ✅ |
| data.yaml | agent-data | ✅ | ✅ |
| cloud_ops.yaml | agent-cloud-ops | ✅ | ✅ |
| orchestrator.yaml | agent-orchestrator | — | — |
| mcp_builder.yaml | agent-mcp-builder | — | — |
| skill_builder.yaml | agent-skill-builder | — | ✅ |
| shania.yaml | agent-shania | — | — |
| provider_templates.yaml | (provider template) | — | — |
| providers.yaml | (LLM provider registry) | — | — |
| router.yaml | (router config) | — | — |
| studio.yaml | (studio config) | — | — |
| agent_ability.yaml | (ability registry) | — | — |

---

## 附录 B: FlowFamily 模块依赖对照表

来自 `Protocol/FlowFrame/flow-framework/references/flow_framework_spec.md §5.5`：

| 流程 | MODULE_DEPENDENCIES |
|------|---------------------|
| RNAFlow | `{"mapping":["qc_clean,trimming"], "count":["mapping"], "deg":["count"], "call_variant":["mapping"], "detect_novel_transcripts":["mapping"], "rmats":["mapping"], "gene_fusion":["mapping"]}` |
| SCRNAFlow | `{"count":["qc_clean"]}` |
| BTCRFlow | `{"mixcr":["qc_clean,trimming"], "vdj_analysis":["mixcr"]}` |
| ATACFlow | `{"mapping":["qc_clean,trimming"], "peak_calling":["mapping"], "motif_analysis":["peak_calling"], "consensus_peaks":["peak_calling"], "diff_peaks":["consensus_peaks"], "atac_qc":["mapping"]}` |
| WGSFlow | `{"mapping":["qc_clean,trimming"], "variant":["mapping"], "cnv":["mapping"], "sv":["mapping"]}` |
