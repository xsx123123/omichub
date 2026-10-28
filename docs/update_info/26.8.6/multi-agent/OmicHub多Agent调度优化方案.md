# OmicHub 多 Agent 调度优化方案

> 基于 2026-08-06 版《OmicHub Manager 多 Agent 调度机制》的优化设计。
> 目标：在保留现有"Manager 集中编排 + 拓扑波次执行"骨架的前提下，补齐产物共享、失败恢复、心跳监控、上下文预算四块短板，使调度模型与 AgentTeams 官方倡导的"可见、可干预、可恢复、低 token"协作模式对齐。

---

## 1. 设计原则

| 原则 | 含义 | 对应现状问题 |
| --- | --- | --- |
| 产物即文件 | 大产物落盘为文件，Agent 之间传引用不传全文 | 20,000 字 prompt 全量注入，token 成本高 |
| 状态可恢复 | 每个任务有状态机和进度日志，崩溃后可断点续跑 | 文档未定义失败/超时/恢复策略 |
| 最小强制依赖 | 兜底依赖只保下限，不消灭真实并行 | 强制默认依赖把多数请求变成全串行 |
| 过程可见可干预 | 运行中用户可插话、可降级、可终止 | 仅支持阶段前后的确认点 |
| 预算有上限 | 字数、轮次、并发、耗时均有可配置上限 | 上限写死、无追问轮次保护 |

---

## 2. 优化后的总体流程

```text
用户请求
   ↓
① 候选收集 + 缺失信息预检（带最大追问轮次）
   ↓
② Manager 输出任务 DAG（含数据契约字段）
   ↓
③ 规范化：契约校验 → 依赖最小化 → 拓扑排序 → 环检测
   ↓
④ 逐 Wave 执行（同 Wave 并行，信号量限流）
   │   每个任务：领取 → 心跳上报 → 产出落盘 → 进度日志 → 状态回写
   │   失败：按策略重试 / 跳过并级联标记 / 终止整链
   │   运行中：用户可插话干预（暂停、修改、终止）
   ↓
⑤ Manager 汇总（读共享空间索引 + 摘要，而非全文堆叠）
   ↓
⑥ 确认点：保存报告 / 数据就绪 → 受控执行阶段
```

与现状的差异集中在 ②（DAG schema 扩展）、③（依赖最小化）、④（状态机 + 共享空间 + 心跳）、⑤（汇总输入瘦身）。

---

## 3. 核心机制设计

### 3.1 任务 DAG Schema 扩展

Manager 输出的 assignment 增加契约与资源字段（全部可选，缺省时走默认）：

```json
{
  "task_id": "domain-analysis",
  "agent_id": "agent-scrna",
  "task": "完成单细胞聚类与注释方案",
  "depends_on": ["research-plan"],
  "accepts_inputs": ["count-matrix", "sample-metadata"],
  "produces_outputs": ["cluster-table", "annotation-report"],
  "retry": { "max_attempts": 2, "backoff_seconds": 30 },
  "timeout_seconds": 1800,
  "priority": "normal"
}
```

- `accepts_inputs` / `produces_outputs`：数据契约，供后端校验（见 3.3）；
- `retry` / `timeout_seconds`：失败策略与超时，缺省值由后端按任务类型配置；
- `priority`：同一 Wave 内的调度顺序提示。

### 3.2 任务状态机

每个任务实例在后端维护显式状态，替代当前"跑完才知道结果"的隐式流程：

```text
pending → ready（依赖全部 succeeded）→ running → succeeded
                                     ↘ failed ──(重试)──→ running
                                     ↘ skipped（上游失败级联 / 用户终止）
```

规则：

1. **级联跳过**：某任务最终失败（重试耗尽）时，其所有下游标记为 `skipped`，其余无依赖分支继续执行——不因一个分支失败拖垮整链；
2. **Manager 知情**：Wave 结束时把 `failed` / `skipped` 任务及其错误摘要反馈给 Manager，允许 Manager **就地补发一个修复任务**（最多 1 次补救轮）或带着缺口进入汇总；
3. **用户终止**：用户中途取消时，running 任务收到取消信号，未启动任务置 `skipped`，已完成的产物保留。

### 3.3 依赖最小化与契约校验

替换当前"对 General、Code、Visualization 强制补充默认依赖"的做法，改为两级：

**第一级：契约推导（主路径）**

- 后端用 `accepts_inputs` / `produces_outputs` 做自动连线：任务 B 需要的输入类型只有任务 A 产出，且 B 未声明依赖 A 时，自动补 `A → B`；
- 两个任务的输入输出契约无交集且 `depends_on` 互不涉及时，**禁止兜底逻辑把它们串起来**——这是释放真实并行的关键。

**第二级：类型兜底（仅在下述情况触发）**

- Manager 完全没有返回有效分工，或契约字段全部缺失时，才退回现有的默认调度表（通用 → 领域 → 代码 → 可视化）；
- 兜底触发时必须向前端发送一条 `schedule_fallback` 事件，进度 Dock 显示"已使用默认分工"，避免用户误以为"超频 = 并行"而实际走了串行。

**校验失败处理**：若契约无法满足（如某输入类型没有任何上游产出），不要强行执行——退回预检环节向用户确认数据来源，或由 Manager 重新分工。

### 3.4 共享产物空间与引用传递

替代 20,000 字全文注入，按任务建立共享目录：

```text
output/overdrive/<session_id>/
├── manifest.json                 # 任务索引：task_id、状态、产物清单、摘要
├── tasks/
│   ├── research-plan/
│   │   ├── result.md             # 完整正式产物（原 final_answer 全文）
│   │   ├── summary.md            # ≤1,500 字摘要（由产出方顺带生成）
│   │   └── progress.log          # 追加式进度日志（见 3.6）
│   └── code-design/ ...
└── final/                        # 汇总报告与交付物
```

下游任务的 prompt 注入改为**三层结构**：

```text
## 上游产物摘要（必读）
【research-plan】<summary.md 内容>
【code-design】<summary.md 内容>

## 上游产物位置（按需读取）
- research-plan 完整产物: output/overdrive/<sid>/tasks/research-plan/result.md
- 产物清单与状态: output/overdrive/<sid>/manifest.json

必须基于上游产物继续工作；需要细节时用读文件工具获取，不得忽略依赖重新独立回答。
```

收益：

- 默认注入量从 ≤20,000 字降到 ≤3,000 字（N 个摘要），长链路的 token 消耗近似从 O(n×L) 降到 O(n×s)；
- 产物落盘天然支持断点恢复（3.6）和报告索引（`output/README.md` 可直接引用 manifest）;
- `summary.md` 同时是前端折叠卡片的默认展示内容，一处生成两处复用。

`manifest.json` 由后端在每次状态变更后原子重写（先写临时文件再 rename），它是 Manager 汇总和前端进度 Dock 的唯一事实来源。

### 3.5 波次执行器改造

`_overdrive_assignment_waves()` 与 `ParallelSubAgentService` 的改动点：

1. **执行前**：按 3.3 重算依赖 → 拓扑排序 → 环检测。检测到环时仍降级为单任务串行，但额外推送 `schedule_warning` SSE 事件说明哪个环被拆开；
2. **执行中**：每个子任务包装状态机钩子——开始前写 `running` + 时间戳到 manifest，结束后写终态；`asyncio.gather()` 使用 `return_exceptions=True`，单个任务异常不再中断同 Wave 其他任务；
3. **信号量之外加总量护栏**：单会话超频任务总数上限（建议 12）、单 Wave 并行上限（建议 4）、整链墙钟超时（建议 45 分钟），超限即向用户说明并降级；
4. **Wave 间检查点**：每个 Wave 结束后检查是否有用户插话/取消请求（见 3.7）。

### 3.6 失败恢复与断点续跑

利用共享空间实现两层恢复：

**层一：进程内重试**
按任务 `retry` 配置重试，指数退避；仅对工具超时、模型 5xx 等瞬时错误重试，对"输入数据缺失/格式错误"类确定性失败直接置 `failed`（重试无意义）。

**层二：会话级断点恢复**

- 每个任务运行中向 `progress.log` 追加里程碑（开始、工具调用完成、产出落盘）;
- 服务重启或会话恢复时，后端读取 `manifest.json`：`succeeded` 任务直接复用产物，`running` 任务回退为 `ready` 重跑（幂等要求：产物写入用"临时文件 + rename"，半成品不可见）;
- 用户侧表现为"继续上次的研究"而非整轮重来。

进度日志同时服务排障：任务失败时把日志尾部 50 行附进错误摘要给 Manager。

### 3.7 心跳与运行中干预

**心跳**：子 Agent 复用现有 `worker_reasoning_delta` / `worker_text_delta` / `worker_tool_call` 事件作为活跃信号；后端为每个 running 任务记"最后事件时间"，静默超过阈值（建议 120 秒）推送 `worker_stalled` 事件，超过任务 `timeout_seconds` 判定超时失败。进度 Dock 对 stalled 任务显示黄色警示，无需新增底层通道。

**运行中干预**（对齐 AgentTeams "jump in anytime" 的轻量版）：

- 进度 Dock 增加三个操作：**暂停当前 Wave 后的调度**、**跳过指定 pending 任务**、**终止整链**；
- Wave 间检查点消费这些指令；running 任务不支持硬中断时，先标记"完成后不调度后续"，再异步取消；
- 用户在运行中发送的插话，作为 `user_directive` 注入下一个 Wave 的任务指令（不动正在运行的任务，避免上下文污染）。

### 3.8 上下文与预算配置化

把写死的限制收拢为一份配置（可 per-agent 覆盖）：

```yaml
# data/ai/_overdrive_limits.yaml
summary_chars: 1500          # 摘要注入上限
upstream_context_chars: 8000 # 注入下游的总上下文上限（摘要+索引）
task_instruction_chars: 20000
max_tasks_per_session: 12
max_parallel_per_wave: 4
chain_wall_timeout_minutes: 45
stall_threshold_seconds: 120
max_intake_rounds: 3         # 缺失信息最大追问轮次
max_repair_rounds: 1         # Manager 失败补救轮次
```

预检追问超过 `max_intake_rounds` 时，Manager 必须基于已有信息给出带假设的保守方案，并在报告中显式列出假设，而不是无限追问。

---

## 4. 与现有代码的改动映射

| 改动 | 文件 | 要点 |
| --- | --- | --- |
| DAG schema 扩展、契约校验、依赖最小化 | `src/omichub/application/services/chat_service.py` | 规范化阶段重写；兜底触发时发 `schedule_fallback` 事件 |
| 任务状态机、重试、级联跳过、心跳检测 | `src/omichub/application/services/parallel_subagent_service.py` | `gather(return_exceptions=True)`；状态钩子写 manifest |
| 共享空间与摘要生成 | `parallel_subagent_service.py` + 各 agent prompt | prompt 增加"产出 ≤1,500 字摘要"要求；产物落盘改原子写 |
| 汇总输入瘦身 | `chat_service.py` | Manager 汇总读 manifest + 摘要，七小节结构不变 |
| 预算配置加载 | `chat_service.py` | 读取 `_overdrive_limits.yaml`，支持 per-agent 覆盖 |
| 新 SSE 事件：`schedule_fallback` / `schedule_warning` / `worker_stalled` / 干预指令 | `frontend/src/composables/useAgentChatStream.ts`、`frontend/src/stores/agentHub.ts` | 事件解析与房间状态扩展 |
| 进度 Dock：fallback 标识、stalled 警示、干预按钮、并行/串行标识 | `frontend/src/components/ai-chat/OverdriveProgressCard.vue` | 数据源切换为 manifest 推送 |
| 专家卡片默认展示摘要 | `frontend/src/components/ai-chat/KimiMessageItem.vue` | 折叠态显示 summary.md，展开显示全文 |

---

## 5. 分阶段落地计划

**P0（恢复与止血，1 个迭代）**

- 任务状态机 + `gather(return_exceptions=True)` + 级联跳过；
- manifest.json 与产物原子写；
- 超时与 stalled 检测；
- `max_intake_rounds` 防追问循环。

**P1（成本与并行，1 个迭代）**

- 共享产物空间 + 摘要注入，下线全文注入；
- `accepts_inputs` / `produces_outputs` 契约推导依赖，强制默认依赖降级为纯兜底 + `schedule_fallback` 事件；
- 预算配置化。

**P2（体验与干预，1 个迭代）**

- 断点续跑（会话恢复时复用已完成产物）;
- 运行中干预（暂停/跳过/终止 + 插话注入下一 Wave）;
- 进度 Dock 区分并行/串行 Wave、stalled 警示、失败任务错误摘要展示。

---

## 6. 新增 Agent YAML 约定（最终版）

```yaml
features:
  subagents_spawnable: true
  capability_tags: [scrna, clustering, annotation]
  accepts_inputs: [count-matrix, sample-metadata]
  produces_outputs: [cluster-table, annotation-report]
  default_stage: domain-analysis
  retry: { max_attempts: 2, backoff_seconds: 30 }
  timeout_seconds: 1800
  limits:                       # 可选，覆盖全局预算
    summary_chars: 2000
```

新增 Agent 的注册 checklist：

1. YAML 能力字段齐全（tags / inputs / outputs / stage）;
2. prompt 中包含"产出正式结论 + ≤1,500 字摘要"的输出规范；
3. Manager 可见的 `default_role` / `capability_scope` 与 YAML 一致；
4. 产物写入遵循"临时文件 + rename"的幂等约定。

---

## 7. 验收清单

- [ ] 构造一个上游任务必失败的请求：下游被标记 `skipped`，无依赖分支正常完成，Manager 汇总中说明缺口；
- [ ] 构造双模态请求（bulk + 单细胞）：两个领域任务出现在同一 Wave 且真实并行，Dock 显示并行标识；
- [ ] 杀掉 running 中的服务再恢复：已完成任务不重跑，running 任务从断点重跑；
- [ ] 全链路统计 token 消耗：相比全文注入版本，5 任务链路的调度注入 token 下降 ≥60%；
- [ ] 触发兜底分工时前端出现"已使用默认分工"标识；
- [ ] 追问 3 轮仍缺信息时，输出带显式假设的保守方案而非继续追问；
- [ ] 运行中点击"终止"：running 任务收到取消、pending 任务置 `skipped`，已有产物保留且可查看。
