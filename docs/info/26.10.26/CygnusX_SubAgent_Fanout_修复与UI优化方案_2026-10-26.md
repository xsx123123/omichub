# CygnusX Sub-Agent Fan-out 分派修复与交互优化方案

> 日期：2026-10-26  
> 依据：用户提供的两张实际运行截图与 `CygnusX_multi_agent_fanout.md` 中的 **§9 as-built（2026-10-26）**。  
> 范围：普通对话内 `parallel_subagents`、统一路由、Legacy/LangGraph、前端 SSE 状态投影与界面；同时核查其与超频/AgentTeams 复用组件的边界。  
> 证据等级：截图为用户侧现象；§9 为仓库/线上当日调查快照；**当前源码与最新运行日志尚未在本评审中直接读取**，以下根因判断须经 Agent 复查，严禁把推测写成已定位或已修复。

## 0. 结论

本次问题包括四个不同层面：

1. **派发准入与单轮额度生命周期**：5 任务被拒绝（`SUBAGENT_MAX_PARALLEL`），同轮重试 4 任务仍被单轮配额拒绝。初步怀疑准入校验之前已经计次，或统一意图预执行、主循环分派共享配额；必须打通 trace 才能判断。
2. **工具契约漂移**：历史 schema §4.3 将 `tasks.maxItems` 配置为 `5`，最新 §9.4 运行限制为 `4`；必须核对线上有效 schema，而非只看设计文件。
3. **目标与工具资格**：§9.1 表明 `shania` 未标记 `subagents_spawnable`；普通 Fan-out 并不自动授予所有沙盒/绘图工具，不能仅凭名称宣称 `agent-code`、`agent-viz` 可实际执行 Python/绘图。
4. **SSE / UI 投影错误与视觉混用**：截图同时出现“已完成”、`0/5`、满绿色进度条、五张“执行中”卡片；§9.1 指出普通 `subagents` 复用了超频泳道 UI，导致 `Wave`、`Manager 规划` 等不适合普通分派的文案暴露。

**推荐顺序：P0 准入/幂等/状态一致性 → P1 事件契约与可观测性 → P1 通用 TaskCard 与双业务容器 → P2 产物/审计/断线恢复。不要仅靠把上限从 4 调到 5 来掩盖问题。**

## 1. 事实、推测和核验点

| 项目 | 有据事实 | 待核查 |
| --- | --- | --- |
| 首次 5 个子任务 | 返回 `success=false`、`SUBAGENT_MAX_PARALLEL`、空 manifest | 拒绝之前是否生成 run、发送 `started` SSE、设置一次性计数器 |
| 第二次 4 个子任务 | 返回“本轮已执行过分派” | 计数器是在调用前递增、异常未回滚，还是意图路由先执行过 |
| 子任务执行 | 两次均未真实派出 Agent，未返回产物 | 是否留有孤儿 TaskCard/运行状态记录 |
| 并发 | §9 单批最多 4，实际并发上限 3 | 第四个任务是否显示 `queued` 而非 `running` |
| `shania` | §9.1 中未标记可派生 | 线上最新 DB 是否已更改、其真实 `agent_id` 是什么 |
| 运行时能力 | 常规子循环工具受 backend_sync / 特殊 workspace_access 授权约束 | code/viz 可用工具名单、执行容器和 artifact 公开协议 |
| 前端 | 画面有互相矛盾的聚合状态；§9 明确复用超频 UI | `started/aggregated` 之外是否有逐子事件、服务端事件与本地 store 如何合并 |

## 2. P0：修复“5 失败后 4 也被拒绝”

### 2.1 原则

- **validate 先于 reserve/commit**：参数数量、agent_id 规范化、spawnable、功能开关、上下文、目标工具可用性等校验完成后，才能正式占用每轮一次的 fan-out 准入额度。
- `rejected_before_dispatch` **不计已成功派发次数**。未创建子运行，不能向前端发 `started`。
- 真正 accepted/dispatch 后，只允许一个具有同一幂等键的执行实例；不能靠重复请求创建新 run。
- 对验证失败可以原轮修正重试，但需要单独的 **validation_attempt_budget**（例如最多 2 次），防止模型无限重试；拒绝绝不可伪装成功。
- **只读咨询**与“有工具的子任务”分开描述和授权。未经授权不能静默升级权限。
- 如果统一意图预执行和模型工具调用在同一 user turn 出现，应由同一个协作协调器做幂等/额度判定，不能出现双占或双派。

### 2.2 参考准入伪代码（必须结合实际框架实现）

```python
async def dispatch_fanout(request, ctx):
    # 1. 仅做预检，无 quota 副作用、无 started SSE
    policy = resolve_effective_policy(ctx)
    validated = validate_all(
        request, max_tasks=policy.max_parallel,
        spawnable_agents=policy.spawnable_targets,
        tool_permissions=policy.target_capabilities,
    )
    if not validated.ok:
        return rejected(code=validated.code, reason=validated.reason,
                        dispatched_count=0, can_retry_this_turn=True)

    # 2. CAS / 唯一键事务：按 user_turn + tool_call_id / request_key 区分并防重
    reservation = await coordinator.accept_once(
        turn_id=ctx.turn_id, request_key=ctx.request_key,
        payload_digest=validated.digest,
    )
    if reservation.already_same_request:
        return await coordinator.get_existing_run(reservation.run_id)
    if reservation.conflict:
        return rejected(code="SUBAGENT_TURN_LIMIT", can_retry_this_turn=False)

    # 3. 接受分派后才出现 run_started/child_queued；失败须有终态记录
    await emit_run_started(reservation.run_id, validated.tasks)
    return await execute_children_with_semaphore(reservation.run_id, validated)
```

**关键语义**：`accepted` 后如 worker/提供方失败，则标记 `failed` / `partial`；不要因为失败就偷偷释放额度而形成重复副作用。仅校验拒绝、完全未接纳执行时才允许同轮修正；服务器崩溃等竞态通过幂等记录与恢复协调处理。

### 2.3 配置统一

- 核对 `tool_configs/tools_schema.yaml`、有效 OpenAI tool schema、`core/config.py`、管理端/环境变量和 system prompt，保证显示最大值统一为 `4`，或由统一 Policy/Registry 派生；实际限制始终以服务端为准。
- 校验 `agent_id` 用实际 Agent Registry 主键；`agent-code` 等**显示名**不能想当然地视为数据库主键。错误信息返回允许的规范 ID / 能力摘要，避免暴露敏感配置。
- 复查 §9.2 `agent_service._filter_runtime_builtin_tools` 开关关闭后不隐藏工具的缝隙。
- 检查统一意图路由 fanout、Legacy、LangGraph、Goal、超频前后台所有入口；不同入口可有不同授权策略，但必须明确且稳定，不得无声绕过。

## 3. P0：建立统一执行状态机

### 3.1 两层状态，不再靠“绿色进度条”猜结果

**运行级** `FanoutRun`：`validating → accepted → running → aggregating → succeeded | partial | failed | cancelled`；预检拒绝单独记录 `rejected`，绝不经过 `running`。

**子任务级** `SubagentTask`：`queued → running → succeeded | failed | timed_out | cancelled | awaiting_input | approval_pending`。其中待用户输入、待审批属于**非终态暂停**，应明确显示阻塞，不可计入成功或失败；是否允许恢复由当前任务编排机制定义。

- `completed_count = succeeded + failed + timed_out + cancelled`（明确这是**终态数**，并另显示成功数）；`total_count = 实际 accepted tasks`。
- 成功度/完成度分开：例如“已结束 3/4 · 成功 2 · 失败 1”，不能把 `failed` 算成成功。
- 仅所有子任务均为终态且聚合落定后，运行才是 `succeeded/partial/failed/cancelled`。`0/5` 时不得显示“已完成”。
- `max_concurrent=3` 且提交 4 个时，默认 **3 running + 1 queued**，不是 4 running。
- 当前仅有截图与 §9，需先核实是否缺少 `child_started/child_done` 事件；若没有应补齐。

### 3.2 SSE 统一事件信封建议

```json
{
  "type": "subagents",
  "schema_version": 2,
  "source": "chat_fanout",
  "run_id": "opaque-id",
  "turn_id": "opaque-id",
  "seq": 12,
  "phase": "child_started",
  "timestamp": "2026-10-26T10:00:00Z",
  "payload": {
    "task_id": "opaque-task-id",
    "agent_id": "canonical-agent-id",
    "display_name": "代码分析助手",
    "status": "running"
  }
}
```

建议事件类型：

`validation_rejected`（无任务启动）/ `run_started` / `child_queued` / `child_started` / `child_progress`（限频）/ `child_succeeded` / `child_failed` / `child_timed_out` / `child_blocked` / `aggregating` / `run_completed` / `run_cancelled` / `heartbeat`。

要求：

- 不同来源统一 `run_id`、`task_id`、`seq`，`source` 明确 `chat_fanout | overdrive | agentteams | goal`。
- 前端按 run_id/task_id 聚合，`seq` 严格去重/防倒退；重连后以服务端快照恢复，不能拿上一轮缓存冒充本轮。
- 后端拒绝时必须发拒绝事件或让前端确认请求被拒，清除任何“乐观启动”的卡片；**禁止在准入成功前生成“执行中”**。
- 保留原工具响应字段兼容旧前端，升级客户端以 v2 状态为准；添加版本契约测试。
- 高耗时子工具期间提供心跳或阶段性进度；停止按钮应穿透父 run 到子任务取消令牌，不得只是停动画。
- 不要将内部 token、推理链、密钥、私有路径直接展示给前端。

## 4. P1：UI 信息架构——从“超频大面板”改为嵌入式协作卡片

### 4.1 普通对话展示（推荐）

```text
┌─────────────────────────────────────────────────────────────────────┐
│  ◉ 并行协作                        正在执行 · 1/4           [展开/收起] │
│  4 个独立任务 · 实际并行 3 个             ▰ ▱ ▱ ▱                       │
│                                                                     │
│  [代码分析助手       运行中]       [可视化助手        等待中]          │
│   Python 连通性测试               生成示例散点图                      │
│   当前：执行工具…                 等待执行资源                       │
│                                                                     │
│  [质量审计助手       已完成]       [数据分析助手        已完成]        │
│   FASTQ QC 预检建议               数据字段契约                       │
│   查看摘要  [查看结果]            查看摘要  [查看结果]               │
│                                                                     │
│  任务完成后将由主助手汇总结论                           [查看执行详情] │
└─────────────────────────────────────────────────────────────────────┘
```

**视觉准则**：

- 默认是一行摘要 + 极薄分段进度 + 可折叠内容，**不要压占整个聊天正文高度**。
- 桌面端两列 TaskCard、窄屏单列；每卡以“**角色名称、真实状态、单行任务、最近一步、查看产物**”为最小单位。
- 保留简洁蓝色（进行中）、绿色（成功）、琥珀（等待/部分）、红色（失败）、灰色（排队/取消）。**统一边框和浅底，不使用大面积浅蓝底铺满 5 卡**。
- 普通 Fan-out 不显示 `Wave 1/1` 与 `Manager 规划 / 专家协作 / 结论交付` 三条进度。高级超频模式才显示 Wave、Manager 和多阶段复核。
- 进度条只表示一个确切指标：任务终态数/接受任务数。等待中的任务不显示执行中；成功率可另用小文字表示。
- 默认折叠已完成任务摘要，展开后才出现 token/耗时/工具记录/产物信息；长 task 和 reasoning 不直接铺开。
- **成功、失败、未启动**必须视觉分开：拒绝分派只显示“未启动 · 最多 4 个任务；本次提交 5 个”，没有子卡片与绿色完成进度。
- 把截图中的“AI 正在回复，消息将排队等待”保留在**输入区域的排队提示**，不要混入多 Agent 卡片状态。

### 4.2 推荐组件与数据分层（Vue 3）

```text
AgentCollaborationContainer.vue     # 判断 source，选择普通/超频壳层
 ├─ FanoutCompactPanel.vue          # 普通聊天；简洁摘要与 task 网格
 │   ├─ FanoutProgress.vue          # run 状态 + 分段进度
 │   ├─ SubagentTaskCard.vue        # 统一任务卡，普通/超频可复用
 │   └─ SubagentResultDrawer.vue    # 执行摘要/工具记录/产物
 ├─ OverdriveWavePanel.vue          # 超频：Manager、Wave、交叉复核
 │   └─ SubagentTaskCard.vue        # 只复用任务级卡片
 └─ CollaborationEventAdapter.ts    # SSE -> normalized run/task state
```

- `useAgentChatStream.ts` 只解析/派发事件，不直接决定“超频完成”；业务状态推导放入 normalized store/reducer。
- 组件使用只读计算属性 `isTerminal`/`finishedCount`/`successCount`，禁止分别维护相互独立的 `isCompleted` 和卡片 status。
- 使用 CSS variables 对齐现有平台设计 token；推荐 10–12px 圆角、1px 中性边线、轻微背景对比、少量阴影、行距 1.5；支持暗色主题、键盘操作、屏幕阅读器的状态播报。
- `task_id` 作为 v-for key，避免旧任务视觉复用；展开折叠状态可独立于执行状态。

### 4.3 推荐 UI 文案映射

| 后端真实状态 | 用户看到的文案 | 颜色 | 是否显示任务卡 |
| --- | --- | --- | --- |
| `validation_rejected` | 未启动 · 参数不符合要求 | 中性 / 红色提示 | 不显示虚假任务卡 |
| `queued` | 等待执行 | 中性灰 | 是 |
| `running` | 正在执行 | 蓝 | 是 |
| `awaiting_input` | 等待补充信息 | 琥珀 | 是 |
| `approval_pending` | 等待审批 | 琥珀 | 是 |
| `succeeded` | 已完成 | 绿 | 是 |
| `failed/timed_out` | 执行失败 / 超时 | 红 | 是 |
| `partial`（run） | 部分完成 | 琥珀 | 是 |
| `cancelled` | 已取消 | 灰 | 视归档策略保留 |

## 5. P1：运行能力和交付保障

### 5.1 不要拿“咨询 Agent”测试“可执行工具 Agent”

- 使用 `list_agents` / Agent Registry（实际接口以仓库为准）拿到可派生 **canonical ID**、`spawnable`、工具清单与 scope；避免手写 `agent-code`、`agent-viz` 误用显示名。
- 对 `shania`：当前快照不可派生。若要做 UI 文案咨询，由主助手直接回答或使用合规咨询路径；**不能为了通过冒烟测试直接放开 `spawnable`**。
- 对 `code`/`viz`：先核验普通 Fan-out 是否有沙盒、文件写入和绘图工具。§9 说明超频 `workspace_access=true` 会有额外工作台工具，这并不意味着普通 Fan-out 也有；不得虚构 hello stdout 或图片路径。
- 第一次端到端验证建议：**2 个已授权且均为只读任务的 Agent**，验证稳定后再扩展到 `4`（含 `3 active + 1 queued`），最后才验证代码/可视化产物。

### 5.2 超时与同步 HTTP 请求

- §9 线上 `SUBAGENT_CHILD_TIMEOUT_SECONDS=1200`、`SUBAGENT_MAX_ROUNDS_PER_CHILD=24`，已超平台“web 进程长任务转 Celery”的既有约定。应将短对话 fan-out 的同步预算与长任务执行预算拆开。
- 方案 A：短会话任务保留 SSE 直连，但设置合理总时间上限、心跳、取消和超时终态。
- 方案 B：长耗时或写产物任务经 Goal/Celery/MAS 等持久执行承载，REST/SSE 拉取进度；不要把 20 分钟子循环留在单个 Web 请求里。
- 故障分类应区分 `validation_error` / `provider_429` / `tool_unavailable` / `timeout` / `cancelled`，只对明确可重试的瞬态错误执行退避，不重复执行已产生副作用的步骤。

### 5.3 产物

- 产物必须来自真实已生成/登记的 Artifact，至少提供：`artifact_id`、`task_id`、`mime_type`、可用性、校验/存储映射；对外通过授权下载/预览端点暴露，**不能把任意 sandbox 相对路径直接当公网链接**。
- 展开任务详情展示真实 stdout、脚本版本、图像缩略图（如有）、执行摘要、审计轨迹；没执行就显示“未执行 + 原因”。
- 和 Case/Artifact/Evidence/Manifest 现有追溯结构兼容，不另建平行的不可复现文件资产系统。

## 6. P2：自动化验收矩阵

| 编号 | 场景 | 必须达到 |
| --- | --- | --- |
| T01 | 单轮提交 5 个（上限 4） | 返回校验拒绝；0 子运行；0 `run_started`；不消耗已接受配额 |
| T02 | 紧接着同轮改成合法 4 个 | 正式 accepted，至少一个子任务真实 started；不是“本轮已分派” |
| T03 | 一个目标非 spawnable | 清楚返回目标无权限；0 子运行；不伪造任务卡 |
| T04 | 已 accepted 后再次不同请求 | 受控拒绝单轮第二个不同 fan-out |
| T05 | 同一 tool_call_id / request_key 重放 | 返回同一 run，不二次执行、不重复写文件 |
| T06 | `max_parallel=4,max_concurrent=3` | 三个 running、一个 queued；资源释放才开始第四个 |
| T07 | 单个子任务失败、其余成功 | run `partial`，成功产物仍可用；前端显示正确计数 |
| T08 | 全部校验失败 | UI `未启动`，无“已完成/0/5/执行中”的矛盾组合 |
| T09 | SSE 重复/乱序/断线重连 | 状态不倒退，不重复卡片，快照恢复一致 |
| T10 | Legacy / LangGraph / 统一路由 | 相同准入与幂等语义，明确是否预分派 |
| T11 | 超频前台与 Celery 后台 | 关闭/开启开关的授权策略一致或文档明确分离 |
| T12 | 功能开关关闭 | 不应仍向 LLM 暴露工具并浪费一次调用 |
| T13 | 正确的可执行沙盒 Agent | 真实 stdout/文件/图片，产物可预览且通过权限检查 |
| T14 | 只读 Agent 无沙盒工具 | 明确拒绝或降级为只读，不伪造执行成功 |
| T15 | 高耗时/取消/审批请求 | 有可观察终态或暂停状态，无永久运行中 |
| T16 | CI 回归 | 修 `cached_tokens` 断言，跑非 quarantine 全套；quarantine 单独核验 |

观察指标：`fanout_validation_rejected_total`、`fanout_accepted_total`、`fanout_started_total`、`fanout_completed_total`、`fanout_quota_conflict_total`、`fanout_orphaned_ui_runs_total`、`fanout_duration_seconds`、子任务状态/工具失败/产物登记情况。所有日志带 `turn_id/run_id/tool_call_id/task_id/source`，严格去敏。

## 7. 实施工作包及建议改动位置

### WP0 — 诊断（不改业务代码）

1. 沿 `chat_service.py` Legacy + LangGraph + `unified_intent_router` 找到配额置位、调用入口、异常处理、started SSE 的实际先后顺序。
2. 追 `ParallelSubAgentService.run` 参数校验、授权、semaphore、child 生命周期、返回信封；检查 schema 5/运行 4。
3. 确认 `shania`、`code`、`viz` 等 registry 真实 ID/可派生标志/工具授权。
4. 追 `useAgentChatStream.ts` 和泳道状态组件的创建、SSE 聚合、complete 推导与清理。
5. 输出**实际代码路径+函数+行号+事件轨迹**，重现 5→4 序列。

### WP1 — P0 后端修复

对准入、单轮配额、校验拒绝、统一幂等与错误码做修复；统一配置和 tool schema；不能破坏现有 C1–C7 隔离安全规则。增加 T01–T06、T10、T12 单测/集成测试。

### WP2 — P0 前端状态修复

引入明确 run/task 状态机和事件 reducer；修 0/5 + 完成、5 个 rejected 仍执行中、不同 run 串状态、SSE 断线重连。先改对，再改美观。

### WP3 — P1 UI 改造

按 §4 实现 CompactPanel、TaskCard、DetailDrawer 与 OverdriveWavePanel 两个容器。复用任务卡但隔离 `source` 业务文案，保留现有聊天布局和设计系统；展示真实结果与产物。

### WP4 — P1/P2 真运行验收与可观测性

完成 T07–T16，生成 Playwright 截图（桌面、手机、暗色模式）和后端 run/trace 证据；修复已有 cached_tokens 红测试以及相关 quarantine 欠账；提供前后对比图和变更文档。

## 8. 可直接交给仓库代码 Agent 的执行提示词

> 任务：对 CygnusX 对话内 `parallel_subagents` 进行 **P0 分派配额/状态一致性修复 + P1 UI 紧凑化重构**。以仓库真实代码为准，不得仅改 prompt、CSS 或调大并发上限来掩盖问题。
>
> 输入：阅读 `CygnusX_multi_agent_fanout.md` §9（2026-10-26 as-built）与本文；两张复现截图表明 UI 同时显示“已完成”“0/5”“执行中”，实际 `parallel_subagents` 先因 5>4 被拒，随后缩到 4 仍被单轮配额拒绝，均无真实子 Agent/产物。
>
> **第一阶段：只读调查。** 核对有效 tool schema 的 maxItems、runtime max_parallel=4、max_concurrent=3、每轮 1 次护栏；明确 quota 消耗与校验、SSE started 的时序；排除意图路由预执行造成的双计；核对 canonical agent_id、spawnable、code/viz 沙盒与 artifact 权限；检查 Legacy、LangGraph、超频前后端和 `useAgentChatStream.ts`。请输出准确文件/函数/行号、事实/假设区分、最小复现步骤与修复补丁清单。
>
> **第二阶段：修复后端。** 校验拒绝不得占 accepted 配额、不得创建执行中卡片；同轮 5→4 修正应允许，已成功 accepted 的第二个不同 fan-out 必须拒绝；同一请求重放必须幂等；对不具 spawnable 权限的 Agent 明确失败；运行配置、工具 schema、LLM 提示词上限一致；保留 C1–C7 安全边界。不要扩大 `shania` 权限来通过冒烟。
>
> **第三阶段：修复事件契约与前端 UI。** 运行/子任务分层状态机；补齐真实 child started/done/failed、queued、heartbeat/终态事件；run_id/task_id/seq 去重；前端拒绝后呈现“未启动”，不可出现“已完成 0/5”；普通 chat Fan-out 改为紧凑的两列 Subagent TaskCard，桌面两列、移动单列；普通模式不显示超频的 Wave/Manager 阶段；超频继续保留自己的阶段容器。轻量蓝灰配色、小面积状态色、少进度条、提供折叠结果/真实产物预览。
>
> **第四阶段：测试与部署验收。** 优先执行 T01–T16，先让门禁变绿；至少真实完成一次 2 个只读 Agent 的 fan-out、一次 4 Agent（3 跑 1 排队），再做支持工具的 Python/图片真实产物测试。对所有没有执行的任务明确返回原因。确认实际服务重建、运行时冒烟、SSE/REST 同步、Playwright 截图、错误码和 trace、CI 结果，生成 `FANOUT_FIX_REPORT.md` 与 `FANOUT_UI_ACCEPTANCE.md`。不得声称未运行的测试通过，不得捏造 Agent stdout 或图像文件。
>
> **约束：** 尊重仓库已存在的 agent-workspace 组件与设计系统；保留最小增量与向后兼容；只更改本工作包必要文件，不触碰与本任务无关的用户修改；任何权限拓展、Celery/MAS 迁移或 schema 破坏性变更需列入单独变更项和回滚方案。

## 9. 本次不建议做的事

- 不要把 `SUBAGENT_MAX_PARALLEL` 简单改为 `5` 当作修复：这只能避开首次报错，修不了已完成 0/5、quota 消耗、spawnable 权限和工具缺失。
- 不要为视觉效果伪造进度百分比、随机执行步骤、计时器或者产物。无法从真实事件得到的数据就不要展示。
- 不要把 AgentTeams/超频工作台工具在普通 Fan-out 全量授予；需要工作区权限应遵守审批和隔离原则。
- 不要因为架构文档历史 §4 写着 `maxItems=5` 就忽略最新 §9；现时实际代码、DB、有效配置、运行日志是最终证据。

---

**可验收的最终体验**：用户提交合法 4 任务→3 任务真正运行、1 任务排队→逐卡真实更新→4 子任务终态→主 Agent 汇总→对每个 Agent 的实际结果与已登记产物可追踪。提交 5 任务或不允许的 Agent→明确预检拒绝、无虚假运行卡片→仍可在同轮合法修正一次。
