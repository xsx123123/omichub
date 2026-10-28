# Delivery Agent 架构与提示词详细梳理

## 一、概述

Delivery Agent（交付报告员）是 OmicHub BioOps 多智能体协作系统中的**最终交付环节专家**，负责汇总经过质量门确认的 Artifact、运行信息和风险，形成可复核的交付包。

---

## 二、核心配置文件

### 2.1 Agent 身份配置 (`data/ai/delivery.yaml`)

```yaml
agent_id: agent-delivery
name: 交付报告员
description: 面向已验证分析产物的交付清单、运行说明与证据汇总专家。
avatar: "📦"
color: "#2563eb"
category: analysis
model: deepseek-v4-flash          # 低成本模型（结构化汇总任务）
prompt_file: prompts/delivery.md
welcome_message: "你好！我是交付报告员。请提供已验证的产物、质量结论和运行信息；我会整理可复核的交付清单与风险说明。"
temperature: 0.2                   # 低温度，确保输出确定性
max_tokens: 32768
mcp_ids: []                        # 无 MCP 服务
skill_ids:
  - md5                            # 文件完整性校验
```

### 2.2 AgentTeams 协作配置

```yaml
features:
  agentteams:
    category: expert
    recruitable: true              # 可被 Manager 招募
    planner_eligible: false        # 不参与计划制定
    execution_modes: [readonly_consultation, workspace_execution]
    max_parallel_work_items: 2
    case_mode_excluded_tool_packs: [subagents]
    handoff_in_case_mode: false
    work_item_timeout_sec: 1800    # 30 分钟超时
```

### 2.3 Persona 人格配置

```yaml
persona:
  archetype: "耐心而结果导向的交付管理员"
  traits: [条理清晰, 耐心, 结果导向, 重视可复现]
  working_style: "逐项对齐交付清单、文件路径、版本、质量结论和复现说明"
  communication_style: "按交付物、使用方法和已知风险组织说明，让接收者可以直接核验"
  challenge_style: "发现产物未验证、路径不稳定或复现信息缺失时拒绝包装成已完成交付"
  status_lines:
    recruited: ["已加入并准备整理交付物"]
    queued: ["正在核对交付清单"]
    running: ["正在汇总产物与复现说明"]
    reviewing: ["正在复查路径、版本与质量结论"]
    succeeded: ["交付包已整理完成"]
    failed: ["交付整理遇到阻断，正在记录缺口"]
    awaiting_input: ["正在等待必要的交付确认"]
```

### 2.4 能力与输入输出

```yaml
capability_scope: [交付清单, 证据汇总, 运行说明, 结果风险说明]
capability_tags: [delivery-manifest, evidence-pack, runbook-capture, artifact-validation]
accepts_inputs: [artifact-reference, quality-decision, evidence-reference, analysis-parameters]
produces_outputs: [delivery-manifest, delivery-summary, runbook, risk-summary]
default_stage: delivery-pack
```

### 2.5 工具包配置

```yaml
tool_packs: [workspace, research, memory, handoff, agentteams_case]
```

| 工具包 | 用途 |
|--------|------|
| `workspace` | 查看、搜索工作区文件（只读） |
| `research` | 联网证据检索 + KEGG 富集分析 |
| `memory` | 跨会话长期记忆 |
| `handoff` | 向其他 Agent 交接上下文 |
| `agentteams_case` | 协作 Case 相关工具 |

### 2.6 转交配置

```yaml
handoff:
  allowed_targets: [agent-general, agent-qc, agent-viz, agent-code]
  max_hops_per_session: 10
```

### 2.7 Studio 工作台配置

```yaml
studio:
  enabled: true
  runtime_profile: analysis-core
  required_capabilities: [tabular]
```

---

## 三、系统提示词 (`data/ai/prompts/delivery.md`)

### 3.1 完整提示词内容

```markdown
# OmicHub 交付报告员系统提示词

## 角色与职责边界

你负责汇总经过质量门确认的 Artifact、运行信息和风险，形成可复核交付包；不得伪造、修改或绕过质量结论。

## 对话与执行模式

先核对交付范围和质量状态，再组织交付内容、缺口与风险；不将未验证产物纳入正式交付。

## 输入确认

确认交付对象、项目、质量门结论、Artifact 与任务引用、报告格式、版本和发布时间要求。

## 知识检索与证据规则

只汇总已确认的 Artifact、任务、日志、审计结论与明确的风险信息，所有交付声明应可回溯。

## 方法论与专业决策

依据质量门、版本一致性、完整性和可复现性组织交付，不自行重解释领域结果或放宽验收标准。

## 工具、Skill 与工作区协议

使用授权的只读检索、引用和交付编排工具；不得越权创建、移动、删除或伪造文件。

## 执行确认与安全边界

任何发布、外发、写入或覆盖交付物的动作须按平台权限与明确确认执行；未通过质量门时停止交付。

## 输出与交付规范

输出交付清单、版本、质量状态、证据引用、已知风险、缺失项和接收方可执行的复现说明。

## 失败、降级与诚实约束

引用失效、质量未确认或材料不完整时如实报告并返回补齐路径，不以摘要掩盖缺口。

## 转介、交接与协作

将质量阻塞项返回质控或执行 Agent；向接收方交接完整引用、版本和风险，不重复生成上游产物。

## 领域补充规范

你是 OmicHub BioOps 工作组的交付报告员，负责 `delivery-pack`。你只汇总已经过质量门确认的
Artifact、任务引用、运行信息和风险；不得生成、移动、删除或伪造文件，也不得绕过质量结论。

## 交付规则

1. 先建立交付清单：产物引用、用途、生成来源、可用性状态和复现信息。
2. 只有当质量结论允许继续时才建议交付；缺少关键 Artifact、质量状态、版本或复现步骤时必须明确
   阻断并列出缺口。
3. 可对已授权文件使用只读工作区和 `md5` Skill 核对存在性/完整性；未读取的内容必须标记"未验证"。
4. 风险披露必须包含限制、未验证假设、失败/重跑条件以及接收者下一步。
5. 不暴露宿主机路径、凭据或原始敏感数据；只输出受控 Artifact 引用与逻辑下载路径。

## AgentTeams 会诊格式

`delivery-pack` 会诊返回 JSON 信封，结论包括交付摘要、可下载/可复现产物、运行说明、风险和
证据引用。若信息不足，`conclusion` 首行写 `BLOCKED` 并给出最小补充清单。
```

### 3.2 提示词结构分析

| 章节 | 核心约束 |
|------|----------|
| 角色与职责边界 | 只汇总，不伪造/修改/绕过质量结论 |
| 对话与执行模式 | 先核对范围和质量，再组织内容 |
| 输入确认 | 确认交付对象、项目、质量门结论等 |
| 知识检索与证据规则 | 只汇总已确认的信息，所有声明可回溯 |
| 方法论与专业决策 | 依据质量门、版本一致性、完整性组织交付 |
| 工具、Skill 与工作区协议 | 只读检索，不得越权创建/移动/删除/伪造 |
| 执行确认与安全边界 | 按权限执行，未通过质量门时停止交付 |
| 输出与交付规范 | 输出清单、版本、质量状态、证据、风险、复现说明 |
| 失败、降级与诚实约束 | 如实报告缺口，不以摘要掩盖 |
| 转介、交接与协作 | 阻塞项返回质控，不重复生成上游产物 |
| 领域补充规范 | 明确 `delivery-pack` 职责边界 |
| 交付规则 | 5 条具体规则（清单建立、质量门阻断、完整性核对、风险披露、安全边界） |
| AgentTeams 会诊格式 | JSON 信封格式，信息不足时 `BLOCKED` |

---

## 四、运行时架构

### 4.1 角色标识映射

```python
# agentteams_capability_registry.py
_ROLE_ALIASES = {
    "data-steward": "agent-data",
    "quality-auditor": "agent-qc",
    "delivery-reporter": "agent-delivery",  # ← Delivery Agent 别名
}
```

### 4.2 能力注册

```python
# 固定能力映射
fixed = {
    "delivery-reporter": "delivery-pack",
    "agent-delivery": "delivery-pack",
}
```

### 4.3 Agent 加载流程

```
OmicHub.yaml (agents.enabled: [..., delivery, ...])
    ↓
agent_loader.py: load_agent_configs()
    ↓
加载 data/ai/delivery.yaml
    ↓
读取 prompts/delivery.md
    ↓
追加 shared/sandbox_protocol.md（共享沙盒协议）
    ↓
应用 tool_packs（workspace, research, memory, handoff, agentteams_case）
    ↓
注册到数据库
```

---

## 五、在协作流程中的位置

### 5.1 Case 状态机中的 Delivery

```
queued → received → preflight_running → preflight_blocked/approval_pending
    → approved → executing → execution_failed/quality_running
    → quality_blocked/remediation_pending → delivery_ready ← 交付就绪
```

### 5.2 交付触发条件

```python
# case_room_projector.py
"delivery_ready": "质量门已通过，交付文件已经可以核验和下载。"
```

### 5.3 Bridge 服务中的交付工作项

```python
# service.py - reconcile_case 方法
if not self._quality_gate_required(case):
    case = await self._cases.transition(case_id, "delivery_ready")
    await self._ensure_work_item(
        case,
        WorkItemRecord(
            work_item_id="delivery-01",
            parent_work_item_id=quality_dependency,
            target="delivery-reporter",           # ← 交付报告员
            objective="汇总任务产物、解读结论与限制，形成可追溯交付包。",
            skill_name="delivery-pack",
            context_refs=[...],
            read_only=True,
        ),
    )
```

---

## 六、Worker 运行时 (`integrations/agentteams/worker/delivery_runner.py`)

### 6.1 配置加载

```python
@dataclass(frozen=True)
class DeliveryWorkerConfig:
    bridge_url: str
    token: str
    poll_seconds: float

def load_config(environ: dict[str, str] | None = None) -> DeliveryWorkerConfig:
    # 环境变量:
    # - AGENTTEAMS_BRIDGE_BASE_URL
    # - AGENTTEAMS_BRIDGE_TOKEN
    # - AGENTTEAMS_WORKER_IDENTITY (必须为 "delivery-reporter")
    # - AGENTTEAMS_WORKER_POLL_SECONDS (默认 5)
```

### 6.2 执行流程

```
┌─────────────────────────────────────────────────────────────┐
│  delivery_runner.py 主循环                                    │
─────────────────────────────────────────────────────────────┤
│  1. claim_next(dry_run=True)  → 预览是否有待处理工作项         │
│  2. claim_next()              → 正式认领工作项                │
│  3. heartbeat_work_item()     → 发送心跳                      │
│  4. execute_readonly_work_item() → 调用 agent-delivery 会诊   │
│     - agent_id: "agent-delivery"                             │
│     - capability: "delivery-pack"                            │
│     - question: "汇总交付清单、产物引用、运行说明、已知风险和复现步骤。不得遗漏风险披露。" │
│  5. 检查质量结论 (passed/warning/manual_review)               │
│  6. close_case()              → 关闭 Case，生成 manifest      │
└─────────────────────────────────────────────────────────────┘
```

### 6.3 关键逻辑

```python
def run_once(config: DeliveryWorkerConfig) -> dict[str, Any]:
    identity = "delivery-reporter"
    
    # 1. 预览
    preview = claim_next(config.bridge_url, identity, config.token, dry_run=True)
    if preview.get("assignment") is None:
        return {"action": "idle", "identity": identity}
    
    # 2. 认领
    claimed = claim_next(config.bridge_url, identity, config.token)
    assignment = claimed.get("assignment")
    if assignment is None:
        return {"action": "claim_raced", "identity": identity}
    
    # 3. 获取 task_id
    task_id = _task_id(assignment)
    trace_id = uuid.uuid4().hex
    
    # 4. 心跳
    heartbeat_work_item(config.bridge_url, identity, config.token, assignment,
                       summary="agent-delivery consultation started.", trace_id=trace_id)
    
    # 5. 执行只读会诊
    evidence_refs = [f"task:{task_id}"] if task_id else []
    result = execute_readonly_work_item(
        config.bridge_url, identity, config.token, assignment,
        agent_id="agent-delivery",
        capability="delivery-pack",
        question="汇总交付清单、产物引用、运行说明、已知风险和复现步骤。不得遗漏风险披露。",
        evidence_refs=evidence_refs,
        trace_id=trace_id,
    )
    
    # 6. 检查质量结论
    quality_decision = str(assignment.get("quality_decision") or "").strip().lower()
    if quality_decision not in {"passed", "warning", "manual_review"}:
        return {"action": "manual_review", "reason": "missing_or_invalid_quality_decision"}
    
    # 7. 关闭 Case
    closed = close_case(config.bridge_url, identity, config.token, assignment,
                       quality_decision=quality_decision, remediation_summary=summary)
    
    return {"action": "closed", "case_id": ..., "manifest_uri": ...}
```

---

## 七、与其他 Agent 的关系

### 7.1 上游 Agent

| Agent | 关系 |
|-------|------|
| `agent-qc` | 质量门结论是交付的前提条件 |
| `agent-data` | 数据预检和 Artifact 引用核验 |
| `workflow-operator` | 执行工作流，生成产物 |

### 7.2 可转交目标

```yaml
handoff:
  allowed_targets: [agent-general, agent-qc, agent-viz, agent-code]
```

| 目标 Agent | 转交场景 |
|------------|----------|
| `agent-general` | 需要通用澄清或平台协调 |
| `agent-qc` | 发现产物未验证，需要重新质控 |
| `agent-viz` | 缺少图表，需要可视化专家补齐 |
| `agent-code` | 缺少复现脚本，需要代码专家补齐 |

### 7.3 在 AgentTeams 团队中的位置

```yaml
# bioops-delivery.yaml
workers:
  - identity: agent-delivery
    skills: [delivery-pack, runbook-capture]
    bridge_identity_env: AGENTTEAMS_AGENT_DELIVERY_TOKEN
    work_inbox: "GET /v1/work-items/assigned"
    forbidden_capabilities: [workflow_submit, workflow_cancel, shell]
```

---

## 八、共享沙盒协议（追加到提示词）

所有 Agent 加载时都会追加 `data/ai/prompts/shared/sandbox_protocol.md`，其中与交付相关的约束：

```markdown
### 沙盒目录使用规范

- `input/`（只读）：用户上传的原始数据。不得修改、覆盖、删除或重命名。
- `ref/`（只读）：参考基因组、注释文件和公共数据库。
- `scripts/`：生成的脚本与代码。
- `output/results/`：结果表格与数据文件。
- `output/figures/`：图表。
- `output/logs/`：运行日志。
- `output/tmp/`：中间文件。

**交付时输出每个产物的实际路径和一句话说明**；每个分析在 `output/results/` 写 
`<project>_summary.md`，会话结束在 `output/README.md` 汇总分析与产物。
```

---

## 九、Overdrive 超频协作中的交付

### 9.1 DeliveryAssembler

```python
# overdrive_execution_service.py
class DeliveryAssembler:
    async def write(self, run: OverdriveRunModel) -> dict[str, Any]:
        # 生成 final-report.md
        root = overdrive_run_root(run.session_id, run.run_id) / "delivery"
        path_rel = f"{root_rel}/final-report.md"
        return {"path": relative, "official_artifacts": official, "content": content}
    
    async def write_readme(self, run, delivery, *, manager_summary=""):
        # 生成 README.md：交付清单、下载方式与 Manager 总结
        path_rel = f"{root_rel}/README.md"
        return {"path": relative, "content": content}
```

### 9.2 交付目录结构

```
<session_id>/<run_id>/delivery/
├── final-report.md    # 最终报告
└── README.md          # 项目 README（交付清单 + 下载方式）
```

### 9.3 规划型交付（planning_only）

```python
# overdrive_run_service.py
async def _write_planning_only_delivery(self, run, plan):
    # planning_only run 不经过执行期，确认计划即完成
    # 生成 delivery/README.md 作为可下载交付物
    readme_relative = f"{relative_root}/delivery/README.md"
```

---

## 十、质量门与交付的关系

### 10.1 FlowRegistry 中的交付定义

```python
# flow_registry.py
class DeliveryDefinition(_StrictModel):
    quality_gate: bool = True           # 是否需要质量门
    outputs: list[str] = []             # 交付产物列表
    thresholds: dict[str, float] = {}   # 质量阈值
```

### 10.2 质量门决策

```python
# agentteams_quality_gate_service.py
def evaluate(self, flow_id: str, metrics: dict[str, Any]) -> dict[str, Any]:
    thresholds = registered.definition.delivery.thresholds
    # 检查 mapping_rate, q30, duplicate_rate 等指标
```

### 10.3 质量门跳过时的交付

```python
# service.py
if not self._quality_gate_required(case):
    case = await self._cases.transition(case_id, "delivery_ready")
    # 直接创建交付工作项，跳过质控
```

---

## 十一、前端展示

### 11.1 Case 状态投影

```python
# case_room_projector.py
"delivery_ready": "质量门已通过，交付文件已经可以核验和下载。"
```

### 11.2 交付就绪事件

```python
# overdrive_run_service.py
if event_type == "manager_delivery_ready":
    return {
        "type": "room_speech",
        "content": str(payload.get("content") or "本轮协作交付已就绪。"),
        "delivery_path": payload.get("delivery_path"),
        "sender": {"agent_id": "agent-orchestrator", "name": "超频 Manager", "role": "manager"},
    }
```

---

## 十二、优化建议

### 12.1 提示词优化方向

| 当前问题 | 优化建议 |
|----------|----------|
| 提示词较通用，缺少具体输出格式示例 | 添加 JSON 输出模板和示例 |
| 风险披露规则较抽象 | 提供风险分类模板（高/中/低） |
| 缺少交付物清单的具体字段定义 | 定义标准交付物 Schema |
| 未明确多产物时的优先级排序 | 添加产物优先级规则 |

### 12.2 架构优化方向

| 当前问题 | 优化建议 |
|----------|----------|
| 交付 Agent 只读，无法生成缺失文档 | 考虑授予有限的文件创建权限 |
| 质量门跳过时直接交付，缺少人工确认 | 添加可选的人工确认环节 |
| 交付物格式不统一 | 定义标准交付物模板 |
| 缺少交付物版本管理 | 添加版本追踪机制 |

### 12.3 Worker 优化方向

| 当前问题 | 优化建议 |
|----------|----------|
| 轮询间隔固定（5 秒） | 支持动态调整轮询间隔 |
| 缺少重试机制 | 添加指数退避重试 |
| 错误处理较简单 | 添加详细的错误分类和恢复策略 |

---

## 十三、相关文件清单

| 文件 | 用途 |
|------|------|
| `data/ai/delivery.yaml` | Agent 身份和协作配置 |
| `data/ai/prompts/delivery.md` | 系统提示词 |
| `data/ai/prompts/shared/sandbox_protocol.md` | 共享沙盒协议（自动追加） |
| `data/ai/agent_ability.yaml` | Agent 能力目录 |
| `data/OmicHub.yaml` | 启用配置 |
| `integrations/agentteams/teams/bioops-delivery.yaml` | AgentTeams 团队配置 |
| `integrations/agentteams/worker/delivery_runner.py` | Worker 运行时 |
| `integrations/agentteams/worker/claim_next.py` | 工作项认领 |
| `integrations/agentteams/bridge/omichub_agentteams_bridge/service.py` | Bridge 服务 |
| `src/omichub/application/services/agentteams_capability_registry.py` | 能力注册 |
| `src/omichub/application/services/case_room_projector.py` | Case 状态投影 |
| `src/omichub/application/services/overdrive_execution_service.py` | 超频执行服务 |
| `src/omichub/application/services/overdrive_run_service.py` | 超频运行服务 |
| `src/omichub/application/services/flow_registry.py` | 流程注册 |
| `src/omichub/infrastructure/config/agent_loader.py` | Agent 加载器 |
| `data/ai/tools/workspace.yaml` | 工作区工具包 |
| `data/ai/tools/research.yaml` | 研究工具包 |
| `data/ai/tools/memory.yaml` | 记忆工具包 |
| `data/ai/tools/handoff.yaml` | 转交工具包 |
| `data/ai/tools/agentteams_case.yaml` | 协作 Case 工具包 |

---

## 十四、总结

Delivery Agent 是 OmicHub 多智能体协作系统的**质量守门人**和**交付整理者**，核心职责是：

1. **只汇总，不生成**：只整理已验证的产物，不伪造或绕过质量结论
2. **质量门依赖**：交付前必须通过质量门（或明确跳过）
3. **风险透明**：如实报告缺口和风险，不以摘要掩盖
4. **可复现**：所有交付声明可回溯，提供复现说明

当前架构清晰，提示词约束明确，但在输出格式标准化、交付物模板、错误恢复等方面有优化空间。
