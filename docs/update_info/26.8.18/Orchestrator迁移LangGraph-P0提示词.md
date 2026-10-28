# Orchestrator 迁移 LangGraph —— P0 实施提示词

> 来源：《协作室任务执行流程评估与优化文档》v1.2 §7（优化项 O11，独立工作流）。
> 依据文档：《agent引擎选型与优化建议.md》（2026-08-18）§4.4 / §5.2 / §5.3 / §7。
> 版本：v1.0（2026-08-18）

---

## 1. 背景与决策依据

- Orchestrator（`data/ai/orchestrator.yaml`）是 MAS 控制面核心：职责是把复合意图拆分为 DAG 计划并协调多 Agent 执行（fan-out、聚合、条件路由），且声明了 `requires_plan_confirmation: true`。
- 现状异常：它是全局 16 个 Agent 中**唯一既没有 engine 又没有 managed_prompt 的 Agent**，控制面反而跑在最弱的执行模型上。
- 评审结论：DAG 拆分 + 计划确认 + 多 Agent 协调天然是图结构问题，LangGraph 的 checkpoint / interrupt / 条件边是最匹配的现成能力；此为全局 P0。
- 边界约束：本次只动 Orchestrator；viz / code / skill-builder / shania 按分级结论另行处理，**禁止顺手一刀切迁移**；OverdriveRunService 按"先 B（仅替换 chat 循环）过渡"的既定路线，本次不做选项 A 的全量重构。

## 2. 提示词（可直接粘贴给编码 Agent）

```text
将 MAS Orchestrator 迁移到 LangGraph 引擎（或给出专用引擎的对比论证后实施）。
这是引擎层改造，不是重新设计 Orchestrator 的职责；禁止推倒重写现有编排逻辑，
禁止顺手迁移其他 Agent（viz/code/skill-builder/shania 不在本次范围）。

1. 先读代码验证（以下位置来自设计文档，行号可能漂移，以实际代码为准）：
   - data/ai/orchestrator.yaml（mas_orchestrator: true,
     requires_plan_confirmation: true，当前无 engine / managed_prompt）
   - data/ai/update/update_agent.md:620 附近的双引擎收敛 P0 决策记录
   - OverdriveRunService 的现有 chat 循环与 MAS path
   - 任一已在 LangGraph 组的 Agent 配置（如 data/ai/rnaseq.yaml）
     作为 engine 声明与图接线的参照样板
   - 《OmicHub多Agent调度优化方案》§3.1 的 DAG schema（task_id/
     depends_on/retry/timeout 字段），计划输出结构必须与之兼容

2. 图结构设计（最低要求四个节点）：
   - plan_generate：接收复合意图 → 输出 DAG 计划
     （结构兼容现有 DAG schema，含 depends_on/retry/timeout）；
   - plan_confirm：interrupt 节点——把计划推送用户确认，
     落实 requires_plan_confirmation: true；用户可确认/修改/取消，
     修改内容回写 state 后重新校验（环检测 + 依赖合法性）；
   - dispatch：按拓扑序 fan-out 派发各 work item，
     复用现有 Bridge 调度协议，不另造派发通道；
   - aggregate：收集各 Agent 产出并汇总。
3. 状态持久化：启用 checkpointer（生产环境用 DB 后端），
   每次状态迁移落 checkpoint——本项目的协作室故障恢复设计（O10）
   将复用这套持久化，禁止另建第二套状态存储；
   崩溃后可从最后一致 checkpoint 恢复，已确认的计划不重复确认。
4. 引擎声明与兼容：
   - orchestrator.yaml 补 engine 声明与 managed_prompt，
     对齐 LangGraph 组 Agent 的配置格式；
   - mas_orchestrator: true 的既有消费方（路由/注册/权限）保持可用；
   - OverdriveRunService 本次仅做"替换 chat 循环"的最小接入（B 方案），
     预留 Engine Interface 抽象点，不锁死底层——未来可换专用引擎。
5. 可观测：图执行全程 tracing（节点进入/退出、状态 diff、
   interrupt 触发与恢复），接入现有日志排查体系。
6. 灰度策略：保留旧执行路径一个版本作为 fallback，
   通过配置开关切换，打 deprecation 日志。

验收：
- 发送一个复合意图（需拆分为 2+ 并行/串行子任务），Orchestrator
  输出合法 DAG 计划并停在 plan_confirm 等待用户确认；
- 用户在确认点修改计划（删一个非必需分支），dispatch 按修改后
  计划执行；
- 执行中途重启服务，从最后 checkpoint 恢复，不重复已完成的派发；
- 配置开关可切回旧路径，旧路径行为不变；
- trace 日志可还原完整执行路径（含 interrupt 与恢复点）；
- 其他 15 个 Agent 行为回归不变。
```

## 3. 验收 Checklist

- [ ] DAG 计划输出与现有 schema 兼容（depends_on / retry / timeout）
- [ ] plan_confirm interrupt 落实 requires_plan_confirmation，修改可回写重校验
- [ ] checkpointer 持久化与协作室 O10 故障恢复共用一套，无第二套状态存储
- [ ] dispatch 复用现有 Bridge 协议，未另造派发通道
- [ ] OverdriveRunService 仅最小接入（B 方案），Engine Interface 预留可插拔
- [ ] 灰度开关可回退旧路径
- [ ] tracing 全程可查
- [ ] 其余 15 个 Agent 回归不变
