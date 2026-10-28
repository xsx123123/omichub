# Agent 引擎选型与优化建议

> 本文档梳理当前 15+ Agent 的引擎实现状态，提出 LangGraph vs 直接 LLM 调用的选型标准及优化方向。  
> 最后更新: 2026-08-18

---

## 目录

1. [现状盘点](#1-现状盘点)
2. [为什么需要双引擎？](#2-为什么需要双引擎)
3. [选型决策矩阵](#3-选型决策矩阵)
4. [四个非 LangGraph Agent 的分析](#4-四个非-langgraph-agent-的分析)
5. [优化建议](#5-优化建议)
6. [迁移风险评估](#6-迁移风险评估)
7. [目标状态路线图](#7-目标状态路线图)

---

## 1. 现状盘点

### 1.1 引擎分布总览

| 引擎类型 | 数量 | 占比 |
|---------|------|------|
| **LangGraph** | 11 个 | ~73% |
| **非 LangGraph** (managed_prompt / direct) | 4 个 | ~27% |

### 1.2 LangGraph 组（11 个）

| Agent | 领域 | managed_prompt | subagents_spawnable | planner_eligible |
|-------|------|----------------|---------------------|------------------|
| agent-general | 全领域通用 | ✅ | ✅ | ✅ |
| agent-rnaseq | Bulk RNA-seq | ✅ | ✅ | ✅ |
| agent-scrna | scRNA-seq | — | ✅ | ❌ |
| agent-scrna-upstream | 单细胞上游 QC/Count | — | — | ❌ |
| agent-scrna-integration | 单细胞整合/批校正 | — | — | ❌ |
| agent-scrna-advanced | 单细胞高级注释/轨迹 | — | — | ❌ |
| agent-atacseq | ATAC-seq | ✅ | — | ❌ |
| agent-qc | 质量控制 | ✅ | — | ❌ |
| agent-data | 数据管家/预检 | ✅ | — | ❌ |
| agent-delivery | 交付报告员 | ✅ | — | ❌ |
| agent-cloud-ops | 云运维专家 | ✅ | — | ❌ |

### 1.3 非 LangGraph 组（4 个）

| Agent | 文件 | managed_prompt | engine | 说明 |
|-------|------|----------------|--------|------|
| **agent-viz** | viz.yaml | ✅ | ❌ | 可视化助手 |
| **agent-code** | code.yaml | ✅ | ❌ | 代码助手 |
| **agent-skill-builder** | skill_builder.yaml | ✅ | ❌ | Skill 构建师 |
| **agent-orchestrator** | orchestrator.yaml | ❌ | ❌ | MAS Orchestrator |
| **agent-shania** | shania.yaml | ❌ | ❌ | Shania 助手 |

> ⚠️ **注意**: `providers.yaml`, `router.yaml`, `studio.yaml`, `agent_ability.yaml`, `provider_templates.yaml` 这些不是 Agent 配置，而是基础设施组件，不涉及引擎选择。

### 1.4 相关设计上下文

来自 `data/ai/update/update_agent.md:620`:

```
明确双引擎收敛路径：
当前部分 Agent 声明 engine: langgraph
P0 决策 —— OverdriveRunService 是作为唯一权威编排器包装两种引擎，
还是仅替换 chat 循环。
```

这表明系统已经意识到双引擎并存是个待解决的设计问题。

---

## 2. 为什么需要双引擎？

### 2.1 核心区别

| 维度 | LangGraph | Direct LLM + Prompt |
|------|-----------|---------------------|
| **执行模型** | 图结构状态机，节点间可条件跳转 | 线性调用，一次 request → response |
| **状态管理** | 自动 checkpoint，支持中断/恢复/手动审批(HITL) | 无内置状态，依赖外部存储 |
| **控制流** | if-else / 循环 / 分支在图结构中声明式定义 | 需要 LLM "思考"后自行决定下一步 |
| **调试性** | 可在任何节点暂停、查看中间态、注入干预 | 黑盒，只有最终输出 |
| **确定性** | 图结构本身约束了可能的执行路径 | LLM 可能走任意路径 |
| **延迟** | 每次边遍历都需要一次 LLM call，有累积延迟 | 单次 LLM call，延迟最低 |
| **适用复杂度** | 多步、带校验、需回退的复杂流程 | 简单问答、单次判断任务 |
| **资源消耗** | 高（多次 LLM call + 状态持久化） | 低（一次 LLM call） |

### 2.2 LangGraph 的核心能力清单

当需要以下任一能力时，**应该使用 LangGraph**：

| 需求 | 是否必需 LangGraph |
|------|-------------------|
| 多轮工具调用（如查询→分析→再查询） | ✅ |
| 人工审批门控（HITL / approval gate） | ✅ |
| 状态中断后恢复（如用户中途修改要求） | ✅ |
| 循环重试（如验证失败后自动修复并重试） | ✅ |
| 分支决策（根据结果选不同子流程） | ✅ |
| 子图嵌套/并行 fan-out | ✅ |
| 中间步骤审计追踪 | ✅ |
| 单次简单回答/分类 | ❌ |
| 简单的内容生成（写文案/画图指令） | ❌ |
| 一次性 API 调用 | ❌ |

---

## 3. 选型决策矩阵

### 3.1 决策流程图

```
新 Agent / 现有 Agent 是否评估？
    │
    ├─ Q1: 是否需要超过 1 次 LLM call 完成任务？
    │   └─ YES → 需要 LangGraph
    │   └─ NO ↓
    │
    ├─ Q2: 是否需要人工干预/审批点？
    │   └─ YES → 需要 LangGraph (checkpoint + interrupt)
    │   └─ NO ↓
    │
    ├─ Q3: 是否需要工具调用的条件分支？
    │   └─ YES → 需要 LangGraph (条件边)
    │   └─ NO ↓
    │
    ├─ Q4: 是否需要循环/重试机制？
    │   └─ YES → 需要 LangGraph (循环边)
    │   └─ NO ↓
    │
    └─ → 直接 LLM + managed_prompt 即可
```

### 3.2 简化版检查表

| 场景特征 | 推荐引擎 | 理由 |
|---------|---------|------|
| Agent 需要连续做 2+ 步推理或工具调用 | LangGraph | 避免 LLM "幻觉"导致步骤跳跃 |
| Agent 是 Lead Planner (planner_eligible: true) | LangGraph | 规划过程需要结构化输出+校验 |
| Agent 涉及计算/写入操作 (代价高) | LangGraph | 需要确认门控防止误操作 |
| Agent 只做咨询/解读/对话 | 看复杂度 | 简单→direct, 复杂→LangGraph |
| Agent 只需要一次 prompt 模板渲染 | Direct | 没必要引入图结构 |
| Agent 是编排者(Orchestrator) | 特殊 | 自有专用协议 |

---

## 4. 四个非 LangGraph Agent 的分析

### 4.1 agent-viz (可视化助手)

**文件**: `data/ai/viz.yaml`

**当前能力**:
- skill_ids: `r-plot-library`, `dotplot`
- tool_packs: `workspace, visualization, handoff, agentteams_case`
- managed_prompt: ✅
- planner_eligible: ❌

**是否需要 LangGraph? 存疑。**

#### 不需要的理由:
- 绘图本质上是：接收数据 → 选择图表类型 → 生成 R/Python 代码 → 执行 → 返回图片
- 这是一个相对线性的流程，不太需要复杂的条件分支或循环
- 如果出错（如代码语法错误），让 LLM 自行修复比定义显式 retry 节点更灵活

#### 可能需要 LangGraph 的理由:
- 实际场景中用户经常说 "换个颜色"/"加个标题"/"改成柱状图"——这是**迭代对话**，需要维护状态
- AgentTeams Case 模式下可能需要 approval gate（正式交付前确认）
- 如果同时调用多个工具（数据库查询 + 绘图），可能需要 Fan-out

**结论**: 如果只是 AI 工作台内的普通对话，Direct 足够；如果要进入 **AgentTeams Case** 模式并支持多人审批流水线，应升级为 LangGraph。

---

### 4.2 agent-code (代码助手)

**文件**: `data/ai/code.yaml`

**当前能力**:
- skill_ids: `code-review`, `reproducibility-advice` 等
- tool_packs: `workspace, research, memory, handoff, subagents, agentteams_case`
- managed_prompt: ✅

**是否需要 LangGraph? 大概率不需要。**

#### 理由:
- 代码助手的任务通常是：阅读需求 → 写代码 → 用户反馈 → 修改
- 这本身就是自然的对话循环，不需要显式的图结构来约束
- `subagents_spawnable: true` 意味着它可以在需要时派生子 Agent，这种动态能力用 LangGraph 反而更难表达
- 代码生成的质量主要由 prompt 质量和模型能力决定，不是执行模型决定的

**结论**: 维持当前方案是合理的。如果需要更严格的代码安全审查门禁，可以考虑添加一个 LangGraph "review node"。

---

### 4.3 agent-skill-builder (Skill 构建师)

**文件**: `data/ai/skill_builder.yaml`

**当前能力**:
- managed_prompt: ✅
- engine: ❌

**是否需要 LangGraph? 可能需要。**

#### 理由:
- 创建 Skill 涉及：需求分析 → 编写 Prompt → 定义 Tool 列表 → 测试验证 → 迭代修正
- 这是一个典型的"生成-验证-修改"循环，适合 LangGraph 的循环边
- 产出物需要满足严格的结构规范（JSON Schema），可以用 checkpoint 保存中间版本

**结论**: 如果 Skill 创建流程已经比较复杂且需要版本管理，建议升级到 LangGraph。否则可以保持简单。

---

### 4.4 agent-orchestrator (MAS Orchestrator)

**文件**: `data/ai/orchestrator.yaml`

**当前能力**:
- mas_orchestrator: true
- requires_plan_confirmation: true
- engine: ❌
- managed_prompt: ❌

**是否需要 LangGraph? 这正是 LangGraph 最擅长的场景。**

#### 理由:
- Orchestrator 的职责是**将复合意图拆分为 DAG 计划**，这本质上是一个图结构问题
- 需要 `requires_plan_confirmation` —— LangGraph 的 checkpoint/interrupt 天然支持
- Orchestrator 需要协调多个 Agent，涉及 fan-out、聚合、条件路由
- 它的输入（用户需求）和输出（DAG 计划）之间有多个中间推理步骤

**⚡ 建议优先级: 最高**
- Orchestrator 是整个系统的控制面核心
- 它应该拥有最严谨的状态管理
- 但当前它是唯一一个没有 engine、没有 managed_prompt 的 Agent

**可能的解决方案**: 
- 要么给 Orchestrator 加上 `engine: langgraph`
- 要么为它开发专用的执行引擎（OverdriveRunService 中的 MAS path）
- 无论哪种，都需要从"默认直接 LLM"切换到结构化编排

---

### 4.5 agent-shania (Shania 助手)

**文件**: `data/ai/shania.yaml`

**当前能力**:
- engine: ❌
- managed_prompt: ❌

**是否需要 LangGraph?**

这需要知道 shania 具体做什么。从命名推测可能是：
- 一个特定的业务助手（可能是某个团队/项目名）
- 或者是一个实验性的 Agent

**结论**: 需要进一步了解其职责后才能判断。

---

## 5. 优化建议

### 5.1 分级策略

不建议"一刀切"地全部迁移到 LangGraph 或全部移除 LangGraph。应该按**任务复杂度分级**：

```
Level 0: Direct LLM + Prompt (无状态)
  ├── 纯文本问答
  ├── 简单分类/判断
  └── 单次内容生成

Level 1: LangGraph Simple (单图)
  ├── 标准分析流程 (RNA-seq, ATAC-seq)
  ├── 数据预处理管道
  └── 带审批的正式任务

Level 2: LangGraph Multi-Agent (多图嵌套)
  ├── MAS Orchestrator
  ├── 跨域综合任务
  └── 复杂 Case 编排

Level 3: Custom Engine (专用)
  ├── MAS Orchestrator (如果标准 LangGraph 不够)
  └── 其他特殊场景
```

### 5.2 优先调整清单

| 优先级 | Agent | 动作 | 预期收益 |
|-------|-------|------|---------|
| **P0** | orchestrator | 升级为 LangGraph 或专用引擎 | 控制面可靠性大幅提升 |
| **P1** | viz | 在 Case 模式下升级到 LangGraph | 支持审批流程和状态恢复 |
| **P2** | skill-builder | 视复杂度决定是否升级 | 提升 Skill 创建质量 |
| **P2** | shania | 调查职责后决策 | 确保不会遗漏关键需求 |
| P3 | code | 观察是否需要 | 通常不需要 |
| P4 | 所有 LangGraph Agents | 审查是否可以简化为 Level 0/1 | 减少不必要的复杂度 |

### 5.3 OverdriveRunService 的统一设计建议

来自 `data/ai/update/update_agent.md` 提到的 P0 决策点：

```
OverdriveRunService 的定位选择：

选项 A: 唯一权威编排器包装两种引擎
  优点:
  - 统一的错误处理、监控、重试策略
  - 简化的配置体系
  - 便于后续替换底层实现
  
  缺点:
  - OverdriveRunService 本身会变得复杂
  - 两层抽象增加调试难度

选项 B: 仅替换 chat 循环
  优点:
  - 改动最小，风险最低
  - LangGraph agents 保持不变
  - 非 LangGraph agents 也保持不变
  
  缺点:
  - 双引擎差异仍在
  - 长期仍需解决统一性问题
```

**推荐: 先选 B 过渡，再逐步收敛到 A。**

---

## 6. 迁移风险评估

### 6.1 从 LangGraph 移到 Direct 的风险

| 风险 | 严重程度 | 影响范围 |
|------|---------|---------|
| 丢失 checkpoint/recovery | 🔴 高 | RNASEQ/ATACSEQ 等耗时长的任务中断后无法恢复 |
| 丢失 HITL 支持 | 🟡 中 | 正式分析提交时缺少确认环节 |
| 丢失中间态审计 | 🟡 中 | 合规性和 debug 困难 |
| 控制流不确定性增加 | 🔴 高 | LLM 可能在多步任务中跳过必要环节 |

**结论: LangGraph 组的 Agent 不要轻易降级。**

### 6.2 从 Direct 迁移到 LangGraph 的风险

| 风险 | 严重程度 | 影响范围 |
|------|---------|---------|
| 延迟增加 (每次边 traversal = 1 LLM call) | 🟡 中 | Viz/Code 可能变得更慢 |
| 运维复杂度增加 | 🟢 低 | 需要管理 graph state, checkpoints |
| 过度工程化 | 🟡 中 | 简单任务不值得图结构 |
| 迁移期间回归 bug | 🟡 中 | 需要充分测试 |

**结论: Direct 组迁移需谨慎评估收益成本比。**

---

## 7. 目标状态路线图

### Phase 1: 现状固化 (现在 - 2周)
- [ ] 确定 `overdrive_limits.yaml` 中 per-agent 的 engine override 字段格式
- [ ] 补全 `shania.yaml` 的缺失文档
- [ ] 为所有 15+ agents 补充 engine 字段的 rationale 注释
- [ ] 记录当前哪些 tasks 因为用了非 LangGraph 引擎而存在已知问题

### Phase 2: 控制面升级 (2 - 4周)
- [ ] Orchestrator 迁移到 LangGraph（或确认专用引擎方案）
- [ ] 验证 Orchestrator 的 `mas_orchestrator: true` 功能是否正常工作
- [ ] OverdriveRunService 选择 B 方案（替换 chat 循环）
- [ ] 建立统一的 tracing/metrics 覆盖两种引擎

### Phase 3: 工作负载优化 (4 - 8周)
- [ ] Viz 在 AgentTeams Case 模式下升级到 LangGraph
- [ ] 审查所有 11 个 LangGraph agents，降级过于简单的为 Level 0/1
- [ ] Skill-builder 视实际情况决定是否升级
- [ ] 完成 P0/P1 对齐项

### Phase 4: 统一收敛 (8周+)
- [ ] OverdriveRunService 成为唯一编排入口（无论底层是 LangGraph 还是 Direct）
- [ ] 暴露标准化的 Engine Interface，未来可以自由替换
- [ ] 完善的 metrics dashboard 监控各 Agent 的执行效率

---

## 附录: 完整对照表

| # | Agent ID | File | Engine | Managed Prompt | SubAgents Spawnable | Planning Eligible | Suggested Tier | Recommended Action |
|---|----------|------|--------|---------------|--------------------|-------------------|---------------|-------------------|
| 1 | agent-general | general.yaml | ✅ LangGraph | ✅ | ✅ | ✅ | Level 2 | 维持 |
| 2 | agent-rnaseq | rnaseq.yaml | ✅ LangGraph | ✅ | ✅ | ✅ | Level 1 | 维持 |
| 3 | agent-viz | viz.yaml | ❌ | ✅ | ✅ | ❌ | Level 1→2 | Case 模式升级 LangGraph |
| 4 | agent-code | code.yaml | ❌ | ✅ | — | ❌ | Level 0 | 维持，观察 |
| 5 | agent-scrna | scrna.yaml | ✅ LangGraph | — | ✅ | ❌ | Level 1 | 维持 |
| 6 | agent-scrna-upstream | scrna_upstream.yaml | ✅ LangGraph | — | — | ❌ | Level 1 | 维持 |
| 7 | agent-scrna-integration | scrna_integration.yaml | ✅ LangGraph | — | — | ❌ | Level 1 | 维持 |
| 8 | agent-scrna-advanced | scrna_advanced.yaml | ✅ LangGraph | — | — | ❌ | Level 1 | 维持 |
| 9 | agent-atacseq | atacseq.yaml | ✅ LangGraph | ✅ | — | ❌ | Level 1 | 维持 |
| 10 | agent-qc | qc.yaml | ✅ LangGraph | ✅ | — | ❌ | Level 1 | 维持 |
| 11 | agent-data | data.yaml | ✅ LangGraph | ✅ | — | ❌ | Level 1 | 维持 |
| 12 | agent-delivery | delivery.yaml | ✅ LangGraph | ✅ | — | ❌ | Level 1 | 维持 |
| 13 | agent-cloud-ops | cloud_ops.yaml | ✅ LangGraph | ✅ | — | ❌ | Level 1 | 维持 |
| 14 | orchestrator | orchestrator.yaml | ❌ | ❌ | — | N/A | **Level 3** | **⭐ P0 迁移** |
| 15 | skill-builder | skill_builder.yaml | ❌ | ✅ | — | ❌ | Level 0→1 | 视复杂度决定 |
| 16 | shania | shania.yaml | ❌ | ❌ | — | ? | TBD | 调查职责 |
