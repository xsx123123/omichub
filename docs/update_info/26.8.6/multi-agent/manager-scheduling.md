# OmicHub Manager 多 Agent 调度机制

本文记录 2026 年 8 月 6 日当前超频协作模式的实际实现，重点回答：用户是否需要手动指定 Agent、Manager 如何选择专家、多个 Agent 如何通信，以及“同时调度”在运行时究竟是并行还是串行。

## 1. 用户是否需要设置 Agent

**不需要。** 用户只需要描述研究问题、数据模态、分组、样本量和已有输入。Manager 会根据内置能力边界自动分配任务。

系统目前有两层调度保障：

1. **Manager 模型调度**：Manager 根据候选 Agent 的 `category`、`default_role` 和 `capability_scope` 输出任务 DAG。
2. **后端默认调度**：如果 Manager 对明显的分析任务没有返回有效任务，后端会使用内置默认策略补充分工，避免复杂请求退化为 Manager 单独回答。

默认研究交付链为：

```text
通用助手：需求拆解、总体研究计划、数据契约
    ↓
领域专家：RNA-seq / 单细胞专项统计与生物学边界（存在匹配专家时）
    ↓
代码助手：代码结构、输入输出接口、沙盒执行和验证
    ↓
可视化助手：读取真实结果，完成图表与报告呈现
```

对于简单代码或绘图请求，默认策略只选择代码助手或可视化助手，不会强行启动整条研究链。

## 2. 为什么必须限定 Agent 能力

Manager 只有知道每个 Agent 的明确边界，才能稳定分工。仅提供 Agent 名称通常不够，会产生以下问题：

- 把统计设计交给只擅长绘图的 Agent；
- 让通用助手直接编写并执行完整分析代码；
- 多个 Agent 重复回答同一个问题；
- 下游 Agent 忽略上游方案，重新独立生成一份答案。

当前能力边界由两部分共同约束：

### 2.1 Manager 可见的调度能力

`src/omichub/application/services/chat_service.py` 会为候选 Agent 生成：

- `default_role`：该 Agent 在协作中的默认职责；
- `capability_scope`：Manager 可以分配给它的任务类型；
- `category` 和 `description`：用于补充领域判断。

### 2.2 Agent 运行时能力

`data/ai/*.yaml` 和对应 prompt 决定 Agent 实际可做什么：

- `prompt_file`：专业角色、输出规范和分析边界；
- `tool_packs`：可以看到和调用的工具；
- `skill_ids`：领域技能；
- `handoff.allowed_targets`：允许转交给哪些 Agent；
- `studio.required_capabilities`：代码或绘图执行环境；
- `features.subagents_spawnable`：是否允许被 Manager 派生为子 Agent。

因此，推荐新增专业 Agent 时同时维护 YAML 能力和 Manager 能力描述，而不是让用户在每次对话中手动配置。

## 3. Manager 一次性调度多个 Agent 的完整流程

### 3.1 收集候选 Agent

`ChatService._run_overdrive_turn()` 调用 `AgentService.list_agents(active_only=True)`，只保留：

- 非 Router Agent；
- `subagents_spawnable=true`；
- 已启用并绑定可用模型的 Agent。

随后生成候选目录并交给 Manager。

### 3.2 缺失信息预检

在真正分工前，系统检查数据模态、分组定义、样本量和输入类型。

如果缺少会改变分析路线的信息：

1. 暂停领域分析；
2. 由通用助手或 Manager 通过 `ask_request` 一次性提问；
3. 将原始请求写入会话 `sandbox_meta.overdrive_intake`；
4. 用户回答后，原始请求与补充信息合并，再重新进入调度。

### 3.3 Manager 输出任务 DAG

Manager 返回一行 JSON：

```json
{
  "speech": "先完成研究计划，再实现代码，最后设计可视化。",
  "questions": [],
  "assignments": [
    {
      "task_id": "research-plan",
      "agent_id": "agent-general",
      "task": "形成总体研究计划和数据契约",
      "depends_on": []
    },
    {
      "task_id": "code-design",
      "agent_id": "agent-code",
      "task": "基于研究计划设计代码",
      "depends_on": ["research-plan"]
    },
    {
      "task_id": "visualization-plan",
      "agent_id": "agent-viz",
      "task": "综合计划与代码设计可视化",
      "depends_on": ["research-plan", "code-design"]
    }
  ]
}
```

`task_id` 是逻辑任务标识，`depends_on` 表示数据依赖。

### 3.4 规范化与默认兜底

后端会依次执行：

1. 丢弃不存在、停用或任务为空的 Agent；
2. 修复重复 `task_id`；
3. 删除无效依赖和自依赖；
4. 对 General、Code、Visualization 强制补充默认依赖；
5. Manager 未分工时，按数据模态应用默认调度表。

因此，“一次性调度多个 Agent”指 Manager 一次生成完整 DAG，**不代表所有 Agent 同时运行**。

### 3.5 拓扑波次执行

`_overdrive_assignment_waves()` 对 DAG 进行拓扑拆分：

```text
Wave 1: research-plan
Wave 2: domain-analysis
Wave 3: code-design
Wave 4: visualization-plan
```

- 同一 Wave 内没有相互依赖的任务可以并行；
- 下一 Wave 必须等待依赖任务完成；
- 检测到循环依赖时，系统按原顺序拆为单任务安全执行，避免死锁。

每个 Wave 调用一次 `ParallelSubAgentToolService.run_parallel_subagents()`。其底层 `ParallelSubAgentService` 使用 `asyncio.gather()` 执行本 Wave 的独立任务，并通过信号量限制并发量。

### 3.6 Agent 之间如何通信

Agent 不是直接互相发送聊天消息，而是通过 Manager 编排的**结构化上游产物**通信。

每个任务完成后返回：

- `answer`：正式阶段结论；
- `thought`：独立的模型 reasoning，仅用于思考面板，不进入正式结论；
- `packet.final_answer`：可供 Manager 和下游任务使用的稳定结论；
- `approval_requests` / `questions`：需要用户确认或补充的信息；
- `workdir`：隔离子任务产物目录。

后端把依赖任务的 `final_answer` 注入下游任务：

```text
## 已完成的上游产物
【research-plan】
...

【code-design】
...

必须基于这些上游产物继续工作；不得忽略依赖后重新独立回答原问题。
```

当前阶段结论上限为 8,000 字，依赖任务指令上限为 20,000 字，可覆盖长研究计划和代码设计，避免此前 1,200 字截断造成的信息丢失。

### 3.7 流式事件与前端显示

子 Agent 运行时产生：

- `worker_started`：任务开始；
- `worker_reasoning_delta`：思考增量；
- `worker_text_delta`：正式正文增量；
- `worker_tool_call`：工具调用；
- `worker_finished`：任务结束。

ChatService 将它们转换为 SSE：

- reasoning 写入消息 `thought`，显示在独立“思考过程”面板；
- text 写入消息 `content`，显示为正式专家产物；
- progress 更新固定在输入框上方的超频进度 Dock；
- 专家正式产物完成后默认折叠，避免长内容占满页面。

### 3.8 Manager 汇总

全部有效任务完成后，Manager 接收各 Agent 的正式结论，不接收 reasoning，并输出一份综合报告。报告必须覆盖：

- 研究目标与假设；
- 数据与设计前提；
- 分阶段分析路线；
- 代码和工具实现；
- 可视化与交付物；
- 风险与质量控制；
- 下一步执行条件。

禁止使用“专家结论已分别展示”作为最终回复。

## 4. 报告保存和数据执行

研究计划汇总完成后，Manager 固定询问：

1. 是否保存报告到工作目录；
2. 数据是否已经准备好。

用户确认保存后：

- 报告写入 `output/results/overdrive-report-<时间>.md`；
- `output/README.md` 增加报告索引。

用户确认数据就绪后：

1. 代码助手获得当前父会话工作区的受控读写和沙盒执行能力；
2. 先核验真实文件、列名、样本和分组；
3. 脚本写入 `scripts/`，结果写入 `output/results/`；
4. 可视化助手等待代码阶段完成，再读取真实结果并输出 `output/figures/`；
5. 数据缺失或格式不正确时停止执行并报告具体问题，禁止伪造结果或图表。

## 5. 当前关键实现位置

| 功能 | 文件 |
| --- | --- |
| Manager prompt、默认调度、DAG、汇总和后续确认 | `src/omichub/application/services/chat_service.py` |
| 子 Agent 并发、工具过滤、reasoning/answer 分离 | `src/omichub/application/services/parallel_subagent_service.py` |
| SSE 事件解析 | `frontend/src/composables/useAgentChatStream.ts` |
| 房间发言和历史消息状态 | `frontend/src/stores/agentHub.ts` |
| 固定进度 Dock | `frontend/src/components/ai-chat/OverdriveProgressCard.vue` |
| 专家产物折叠和思考面板 | `frontend/src/components/ai-chat/KimiMessageItem.vue` |
| 聊天页底部布局 | `frontend/src/components/agent-workspace/AgentSandbox.vue` |

## 6. 后续扩展建议

新增 Agent 时建议提供机器可读的能力字段，而不是只写自然语言描述：

```yaml
features:
  subagents_spawnable: true
  capability_tags: [bulk-rnaseq, deg, enrichment]
  accepts_inputs: [count-matrix, sample-metadata]
  produces_outputs: [deg-table, pathway-table, analysis-report]
  default_stage: domain-analysis
```

Manager 可以进一步使用 `accepts_inputs` 和 `produces_outputs` 自动校验数据契约，减少错误分工，并允许多个真正独立的领域任务在同一 Wave 并行执行。
