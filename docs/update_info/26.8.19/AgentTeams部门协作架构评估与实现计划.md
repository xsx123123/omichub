# AgentTeams 部门协作架构评估与实现计划（2026-08）

> 配套评审稿：`agentteams_department_collaboration_architecture_2026-08.md`
> 本文档性质：评估 verdict + 设计细节补充 + 分阶段编码 Agent 提示词，可直接逐段粘贴给编码 Agent（kimi code / Claude Code / CODEX 等）执行。

> **当前进度（2026-08-18）**：Phase 1 已完成首轮实现；Phase 2 已增加 `resume/replan/branch/cancel` 决策接口和评估卡按钮，其中 `cancel`、`replan`、`branch` 已分别接入取消、重规划工作项和并行支线骨架；交接事件会触发 Manager 汇总回路。Work Item 已支持 `declared_inputs/declared_outputs` 写冲突串行化。安全点级别、恢复幂等、Case 参与者权限收敛和预算容量治理仍继续推进。

---

## Part 0. 评估结论（verdict）

**结论先行：方向对，可以进入实现。** 这份提案的四个核心决策都与 2025–2026 年业界多智能体编排的主流约定一致，且地基判断准确——现有系统（审计事件、Worker 进度投影、工作项取消、人工审批）确实覆盖了最难的部分，新增内容是协议层而非执行层重写。

逐项对照：

| 提案决策 | 业界对应约定 | 评价 |
| --- | --- | --- |
| Manager → 领域 Agent → Worker 三层 | 层级/supervisor 模式（CrewAI hierarchical process、LangGraph 嵌套子图、Magentic-One Orchestrator）是 >10 个 Agent 场景的公认自然形态 | ✅ 一致 |
| `@所有人` 不 fan-out，只生成 Manager 协调任务 | fan-out 仅适用于真正独立的分支；对同一问题无序群发是教科书级反模式 | ✅ 一致且少见地写对了 |
| 结构化 `room.agent_handoff` 而非自然语言交接 | OpenAI Agents SDK 显式 handoff、MetaGPT SOP 结构化产物（强制可验证产物而非聊天消息） | ✅ 一致 |
| 「停止—理解—决定」状态机 | LangGraph `interrupt()` / `Command(resume=...)` 的 HITL 范式：暂停、保存状态、人工决策、精确恢复 | ✅ 语义同构 |
| `branch_created` 新建并行支线 | LangGraph time-travel 的 checkpoint 分支语义 | ✅ 一致 |

**需要补强的是 8 个落地细节**（Part 2 逐条给出 spec），不改变架构方向，但缺了它们 Phase 2/3 会踩坑：

1. Mention 解析的歧义与优先级规则（提案只给了 happy path）。
2. `clarification_reply` 的超时与失效处理（澄清卡无人回答时工作项挂多久）。
3. 「安全停止点」需要三级可中断性分类，提案目前是一句原则。
4. 恢复/重派发的幂等语义（LangGraph 官方文档的头号坑：恢复时 interrupt 之前的代码会重跑）。
5. 产物契约与并发写入隔离的具体目录/锁规范（Phase 3 的前置）。
6. SSE 单流排序保证（交接事件与可见消息的先后关系）。
7. 失败降级路径（Manager/领域 Agent 超时、消息重复提交）。
8. 领域 Agent 直接回复时的工具白名单强制点（不能只靠提示词约束）。

**实施顺序建议**：在提案的 Phase 1 之前插入一个 Phase 0「只查不改的现状核验」——提案 §3.1 列了 7 项已有能力及代码位置，这些是后续所有提示词的锚点，必须先由编码 Agent 核实属实（文件路径、函数名、事件字段），核验结果同时校准 Phase 1–3 提示词中的锚点描述。

---

## Part 1. 与业界约定的对照依据（供向编码 Agent 复述）

- **层级编排**：LangGraph 用父图调子图、CrewAI 用 manager agent 按能力委派、MetaGPT 用公司层级 + SOP 文档流转，三者共同点是「树内通信量随深度线性增长，而非全连接平方增长」。提案的三层结构（Manager/部门/Worker）正是该模式，且把「对外单一责任人」放在 Manager 符合 supervisor 惯例。
- **HITL 中断**：LangGraph 生产系统的标准形态是 `interrupt()`（暂停并保存完整状态）→ 人工输入 → `Command(resume=...)`（从断点精确恢复），配合持久化 checkpointer。提案的 `interruption_requested → interrupted → change_assessed → resume/replan/branch/cancel` 是该范式的多工作项推广，语义兼容。
- **关键教训（必须吸收）**：LangGraph 官方文档明确「节点恢复时 interrupt 之前的代码全部重跑」，因此**暂停点之前的副作用必须幂等（upsert/先查后建），副作用尽量放暂停点之后**。这条直接转化为 Part 2.4 的幂等规范。
- **反模式确认**：fan-out 模式仅在分支真正独立时成立；「对同一问题多个 Agent 各自作答」会产生互相矛盾的答案与竞态。提案对 `@所有人` 和多提及的处理（统一降级为 Manager 协调）是正确的。
- **supervisor 模式边界**：supervisor 委派的是互不重叠的子任务；同一部门内多个 Worker 若需共享中间数据，不能靠共享上下文，必须靠**显式产物契约**（A 的产物文件是 B 的声明输入）。这转化为 Part 2.5 的产物契约规范。

---

## Part 2. 需补充的设计细节（逐条 spec）

### 2.1 Mention 解析的歧义与优先级规则

提案只覆盖了单提及 happy path。补充机械解析规则（全部在进入模型前完成，不由 LLM 判断）：

| 场景 | 规则 |
| --- | --- |
| 同一消息含多个领域 Agent 提及 | 按提案降级为 `manager` 模式，且 `mentions` 数组保留全部对象供审计；Manager 协调消息中必须复述「用户点名了哪些部门」 |
| Agent 提及与文件提及同名（如 `@report`） | 优先级：精确 agent_id > 精确别名 > 文件名；冲突时在 `room.user_message` 写入 `mention_resolution_note`，前端在 chip 上显示解析结果，发送前用户可改 |
| 提及非当前 Case 参与者的 Agent | 不投递、不报错中断；生成 Manager 消息：「该部门尚未加入本 Case，是否由 Manager 评估后加入？」（走澄清卡而非静默丢弃） |
| 提及已离开团队的 Agent（Phase 3 团队变更后） | 别名目录按 Case 当前参与者快照解析；历史消息中的旧 mentions 只读展示，不可再投递 |
| 消息中间出现 `@`（非句首） | 与句首同等解析；chip 化后由前端保证 payload 准确，后端不依赖文本位置 |
| 纯 `@文件名` 无 Agent 提及 | `dispatch_mode = manager`（保持现状：文件引用不改变路由） |

容错别名（`@mamager` → `@Manager`）必须在 MentionResolver 的服务端别名表中实现，前端菜单只做提示，**禁止前后端各维护一份别名**。

### 2.2 `clarification_reply` 的优先级与超时

提案规定澄清回复「必须路由回原提问 Agent」，补充两条：

- **优先级**：`clarification_reply` 判定高于一切 `@` 规则。用户在回答澄清卡时即使写了 `@别的部门`，也只作为内容语义记录，不改变投递目标；在审计事件中写 `mention_overridden_by: clarification_reply`。
- **超时**：澄清卡挂起超过可配置时限（默认建议 72h）时，对应工作项转入 `awaiting_approval` 之外的显式 `stalled` 投影状态，Manager 主动在房间发一次跟进消息；超过第二个时限（默认 7 天）由 Manager 提议「按默认假设继续 / 冻结该支线 / 终止」，仍需人工决策，禁止自动继续真实计算。

### 2.3 「安全停止点」三级可中断性分类

把 §5.3 第 4 步落成每个工具在能力目录中的声明字段：

| 级别 | 含义 | 系统行为 | UI 文案 |
| --- | --- | --- | --- |
| `cooperative` | 工具内循环定期检查 cancellation_token（如分页下载、迭代分析） | 下发取消信号，等待确认事件，超时（默认 30s）后降级为 `queued` | 「正在停止…」 |
| `queued` | 只能在当前原子步骤边界停止（如单次比对、单次渲染） | 标记停止请求，步骤完成后不领取下一子任务 | 「将在当前步骤完成后停止」 |
| `external` | 外部不可中断流程（已提交的集群作业、远程队列） | 只登记停止意图 + 外部作业 ID，提供「是否同时撤销外部作业」的独立审批项 | 「外部作业仍在运行（ID: xxx），可选择撤销」 |

**禁止**任何工具静默归为 `external`——能力目录中每个工具必须显式声明级别，未声明的工具默认 `queued` 并在审计中记警告。

`work_item.interrupted` 事件的快照 schema（提案未定义）：

```json
{
  "event_type": "work_item.interrupted",
  "work_item_id": "scrna-comparison-01",
  "stop_level": "cooperative",
  "completed_steps": ["load_matrix", "normalize"],
  "pending_steps": ["integrate", "deg"],
  "reusable_artifacts": [
    {"path": "output/case_x/scrna-comparison-01/normalized.h5ad", "step": "normalize", "content_hash": "sha256:..."}
  ],
  "resume_hint": "normalize 产物参数与变更后配置兼容，可复用",
  "external_jobs": []
}
```

`resume_hint` 由领域 Agent 在评估时填写，快照本身只记事实；两者分开写，避免把判断混进证据。

### 2.4 恢复与重派发的幂等语义

吸收 LangGraph「恢复时暂停点之前代码重跑」的教训，定三条硬规则：

1. **所有恢复路径（resume/replan/branch）写入侧一律 upsert**：按 `work_item_id + step_name` 定位既有记录，禁止 insert-only。
2. **事件去重**：`causation_event_id` 唯一约束——同一因果事件触发的下游事件重复到达时直接丢弃；用户消息重复提交（双击/重试）按 `client_message_id` 去重，幂等返回第一次的 message id。
3. **副作用后置**：审批、真实计算派发、外部提交一律放在状态机「决策已确认」节点之后；决策确认节点本身只写事件，不调外部系统。

### 2.5 产物契约与并发写入隔离（Phase 3 前置，但规范要在 Phase 1 就定）

- **目录约定**：`output/{case_id}/{work_item_id}/`，Worker 只允许写自己的目录；跨 Worker 复用一律只读引用。
- **产物声明**：每个 work item 在创建时声明 `declared_inputs`（路径列表，只读）与 `declared_outputs`（路径列表，独占写）；派发前由编排层做**冲突检查**：任一 work item 的 `declared_outputs` 与另一并行 work item 的 `declared_inputs/outputs` 相交即拒绝并行，降级为串行 wave 并在审计中记录原因。
- **内容寻址**：产物清单带 `content_hash`，重规划时据此判断「参数变了但产物可复用」，避免凭文件名猜测。
- 同部门 Worker 需要共享中间数据时，只允许「A 声明输出 → B 声明输入」的显式依赖边，禁止共享可写上下文（对应 supervisor 模式的边界条件）。

### 2.6 SSE 单流排序与重建保证

- 每个 Case 一个全局单调递增 `seq`（持久化，非内存计数器）；所有 room/work_item 事件携带。前端只按 `seq` 排序投影，不按到达时间。
- 排序不变量：`room.agent_handoff` 的 `seq` 必须小于 Manager 对应汇总 `room.agent_message` 的 `seq`；`work_item.interruption_requested` 必须小于该工作项此后一切状态事件。后端在写事件时强制（同事务取 seq）。
- 历史重载 = 按 `seq` 重放，前端不得用本地状态修补缺失事件；检测到 seq 空洞时整段重拉而不是猜测。

### 2.7 失败降级路径

| 故障 | 行为 |
| --- | --- |
| 被点名领域 Agent 超时/报错 | 30s（可配）无 `room.agent_message` 则 Manager 接管发降级消息：「单细胞部门暂时无法响应，已记录，稍后重试或由我转达」，审计记 `room.agent_timeout`；**不得静默丢失** |
| Manager 自身不可用 | 房间入口拒绝新消息并明确提示（不排队假接收），进行中的 Worker 不受影响 |
| Celery 任务重复投递 | 靠 2.4 的去重规则吸收 |
| 中断请求时工作项刚好完成 | 竞态以事件 seq 定胜负：完成事件在前则中断请求转为「针对结果的变更评估」，不再冻结；评估照常给出，用户仍可选择回滚式重规划 |

### 2.8 领域 Agent 直接回复的权限强制

「不能绕过审批和 Case 约束」不能只写在系统提示词里：

- `DomainAgentRoomResponseService` 构造时按能力目录注入**该 Agent 的工具白名单**，模型根本拿不到白名单外工具的 schema（不是「提示它别用」）。
- 直接回复中产生真实计算意图时，服务层统一走既有审批卡生成函数（与 Manager 路径同一个入口），杜绝两套审批逻辑漂移。
- `自主模式` 标记在服务层做拦截判断，提示词层面只做行为引导。

---

## Part 3. 运行时角色提示词草案（供编码 Agent 直接采用）

以下五段是**运行时 system prompt / 结构化输出提示词**草案，编码 Agent 实现服务时直接落位；`{{...}}` 为模板变量。

### 3.1 Manager 房间响应提示词（`manager` / `broadcast` 模式）

```text
你是 {{manager_display_name}}，生物信息协作室的客户经理（Manager）。用户是甲方，
领域 Agent（{{participant_agent_list}}）是各部门负责人，Worker 是部门下的执行员工。

你的职责：
1. 澄清目标、控制范围/预算/审批、整合对外交付。
2. 不替代领域 Agent 做专业判断；专业问题转述给对应部门，并说明「已请 XX 部门评估」。
3. 收到 @所有人（broadcast）时：先解释涉及哪些部门、各自的职责与预计顺序，
   然后生成受控派发计划（串行/并行及理由），绝不直接 fan-out。
4. 收到领域 Agent 交接（room.agent_handoff）后：面向甲方汇总结果、风险、
   产物清单与下一步建议；需要真实计算的下一步必须生成审批卡，不得口头放行。

硬约束：
- 所有事实（文件路径、数值、任务状态）只能引用事件与产物中的内容，禁止编造。
- 你不能批准真实计算；只能发起审批请求。
- 一条回复聚焦一个主题；涉及多部门时分节并标注部门名。
```

### 3.2 领域 Agent 直接答复提示词（`direct` 模式，无运行中任务）

```text
你是 {{agent_display_name}}（{{agent_id}}），本 Case 中「{{domain_name}}」部门的负责人。
用户刚才直接点名你：「{{user_message}}」。

你的职责：
1. 以部门负责人身份直接回答专业问题，口吻专业、面向甲方可懂。
2. 如果问题超出你的领域，说明边界并建议由 {{manager_display_name}} 协调对应部门。
3. 如果回答需要真实计算/写入/参数变更：不要执行，输出「需要做的事 + 预计影响」，
   由系统生成审批卡。
4. 回答末尾如有后续动作，给出明确建议（新增任务 / 等待用户确认 / 无需动作）。

硬约束：
- 你可用的工具仅限：{{tool_whitelist}}。其余工具对你不可见也不可用。
- 不得代表 Manager 承诺范围、预算、排期。
- 不得评论其他部门的中间结果，除非该结果已作为正式交接/产物进入本 Case 证据。
```

### 3.3 变更评估提示词（`direct` 模式，有运行中任务 → `room.change_assessment`）

```text
你是 {{agent_display_name}}，正在执行工作项 {{affected_work_items}}。
用户发来变更消息：「{{user_message}}」。系统已冻结你名下受影响的工作项。

你处于只读评估上下文：可以读取当前进度、已有产物清单（含 content_hash）、
依赖图和用户消息；禁止执行任何写操作或真实计算。

请输出严格符合以下 JSON Schema 的评估（不要输出任何额外文字）：

{
  "understood_change": "用一句话复述你理解的用户意图",
  "affected_work_items": [{"work_item_id": "...", "impact": "obsolete|partially_reusable|unaffected", "reason": "..."}],
  "reusable_artifacts": [{"path": "...", "content_hash": "...", "why_reusable": "..."}],
  "invalidated_artifacts": [{"path": "...", "why": "..."}],
  "recommended_action": "resume|replan|branch|cancel",
  "recommendation_reason": "...",
  "requires_approval": true,
  "estimated_new_cost": {"compute": "...", "time": "...", "caveats": "..."},
  "user_facing_summary": "给甲方看的一段话：影响是什么、建议怎么做、为什么"
}

判断规则：
- 上游产物参数与变更后配置兼容 → partially_reusable，优先复用而不是重跑。
- 拿不准兼容性 → 标 requires_approval=true 并在 caveats 说明不确定性，禁止猜测放行。
- 用户意图模糊 → recommended_action=branch 的优先级高于 replan（保留原结果，并行试错）。
```

### 3.4 交接生成提示词（完成 → `room.agent_handoff`）

```text
你是 {{agent_display_name}}。你负责的以下工作项已全部完成或阶段性完成：
{{completed_work_items}}。

生成给 {{manager_display_name}} 的结构化交接，严格符合 Schema：
{
  "summary": "一段面向非本领域专业读者也能看懂的结果摘要",
  "key_findings": ["..."],
  "risks": ["..."],
  "artifact_refs": [{"path": "...", "kind": "table|figure|report|data", "description": "..."}],
  "recommended_next_action": "request_user_review|propose_next_phase|await_other_department|none",
  "handoff_to": "bioops-manager"
}

硬约束：
- artifact_refs 只能列真实存在且已登记的产物；每个产物必须来自工作项的 declared_outputs。
- risks 不许为空数组敷衍：没有风险就写 ["未发现显著风险；常规注意事项：..."]。
- 不在交接中向用户直接喊话；对外沟通由 Manager 负责。
```

### 3.5 广播协调提示词（`@所有人` → Manager 协调）

```text
用户发送了 @所有人：「{{user_message}}」。
当前 Case 参与部门：{{participant_agents_with_status}}。

输出两部分：
1. 一段对用户可见的协调说明：这条消息涉及哪些部门、为什么、各自将做什么。
2. 一个派发计划 JSON：
{
  "waves": [
    {"parallel": true, "tasks": [{"agent_id": "...", "instruction": "...", "expected_output": "message|assessment|work_items"}]}
  ],
  "skip": [{"agent_id": "...", "reason": "与该部门职责无关，不打扰"}]
}

规则：默认宁少勿多——与该消息无关的部门放入 skip 并说明理由；
同一 wave 内的任务必须互不依赖；依赖关系跨 wave 表达。
```

---

## Part 4. 分阶段实施计划与编码 Agent 提示词

### Phase 0：现状核验（只查不改）

目的：核实评审稿 §3.1 列出的 7 项已有能力属实，产出后续所有提示词的锚点事实表。

```text
【任务性质】只做代码级调研与评估，禁止修改任何代码、配置、数据库。
先读代码再下结论；所有结论必须标注文件路径与关键代码位置（文件:行号/函数名）。

【背景】我们要在现有 AgentTeams 协作室上实施「部门协作架构」升级。
实施前需要核实以下地基能力是否真实存在、接口形态如何：

请逐项核实并给出证据：
1. 房间消息审计：src/omichub/application/services/agentteams_service.py 中
   用户消息是否以 room.user_message 事件持久化？事件 payload 现有字段清单是什么？
   SSE 历史重载的事件接口与分页参数是什么？
2. 路由决策：src/omichub/application/services/agentteams_route_decision.py 的
   输入/输出结构？Router 如何选择 Flow 与 lead planner？置信度阈值在哪定义？
3. Manager/领域流程交接：agentteams_room_response_service.py 中
   「正式规划启动后停止 Manager 泛化追问」的具体实现位置与触发条件。
4. Worker 进度投影：frontend/src/utils/agentTeamsRoom.ts 如何把
   work item / Skill / 工具调用 / 产物投影成卡片？事件类型到卡片的映射表在哪？
5. 工作项取消：integrations/agentteams/bridge/omichub_agentteams_bridge/service.py
   中取消非终态 work item 的入口、级联跳过下游依赖的实现、以及终态集合定义。
6. 人工审批：审批卡事件的类型、状态机、以及「旧自动确认标记只清理不放行」的位置。
7. 能力目录：Agent 名称/别名/agent_id/工具白名单当前来自哪里？
   是否已有运行时目录服务，还是散落在配置/提示词中？

【交付格式】
A. 能力核验矩阵：能力 × 是否存在（✅/⚠️部分/❌）× 证据位置 × 备注。
B. 关键数据结构清单：room.user_message、审批卡、work item 事件的现有字段。
C. 与上述描述不符之处的差异清单（这将直接修改我们的实施提示词）。
D. 你认为实施「提及解析与定向投递」最小改动的切入点和理由。
```

### Phase 1：可见但不改变执行（低风险）

目标：前端 `@` 菜单 + 审计字段扩展 + 定向只读答复 + 交接投影。

```text
【任务性质】在现有 AgentTeams 协作室基础上增量修改，禁止重构无关模块；
先阅读 Phase 0 核验报告与相关代码再动手。技术栈：后端 FastAPI + Celery，
前端 Vue3 + 既有 agentTeamsRoom.ts 事件投影体系。

【实现内容】
1. 新增 AgentTeamsMentionResolver（应用服务层）：
   - 基于运行时能力目录 + Case 当前参与者解析 @ 提及，输出标准 mentions 数组；
   - 解析优先级与歧义规则按设计文档 Part 2.1 表逐条实现；
   - 别名表（含 @mamager→@Manager）只在服务端维护一份；
   - 纯文本降级：前端 chip 不可用时仍能从 content 文本解析。
2. room.user_message 事件 payload 增加 mentions、target_agent_id、dispatch_mode、
   client_message_id（幂等去重键）；dispatch_mode 四值：
   manager / direct / broadcast / clarification_reply，判定优先级按 Part 2.2。
3. 新增 AgentTeamsRoomDispatchService + DomainAgentRoomResponseService：
   - direct 模式且目标 Agent 无运行中 work item → 生成只读领域答复
     （运行时提示词用 Part 3.2，工具白名单按 Part 2.8 在构造时注入）；
   - direct 模式且有运行中 work item → 本阶段只回「已收到，变更评估将在
     Phase 2 提供」并记录意图，不冻结（冻结是 Phase 2 内容）；
   - 超时降级按 Part 2.7：30s 无响应由 Manager 发降级消息并记 room.agent_timeout。
4. 新增 AgentTeamsHandoffService：统一写 room.agent_handoff（Schema 按 Part 3.4），
   先在「工作项全部完成」这一既有钩子上接入；Manager 收到交接后生成汇总
   room.agent_message（提示词 Part 3.1 第 4 条）。
5. 前端：
   - @ 菜单分组（项目成员/群组/工作区文件），三类不同图标、payload、说明文案；
     数据来自新的 Case 参与者接口，禁止前端静态列表；
   - 发送前保留可编辑提及 chip；
   - room.agent_message 显示真实 Agent 身份与部门徽标；
   - room.agent_handoff 渲染为轻量交接卡（样式区别于用户消息）；
   - 历史重载后提及 chip 与交接卡完整恢复。

【一致性约束】
- 不改现有 RoomResponseService 的 manager 默认回路；无提及消息行为与现状完全一致。
- 事件全部带 case_id/actor/recorded_at/correlation_id/causation_event_id/seq（Part 2.6）。

【验收】
- @单细胞助手 只由 agent-scrna 回答，Manager 不抢答；无提及时行为与改版前一致；
- @mamager 容错生效；@非参与部门 触发澄清卡而非静默丢弃；
- 双击发送/网络重试不产生重复消息（client_message_id 去重）；
- 刷新/切换房间后 mentions、答复、交接卡完整恢复；
- room.agent_handoff 的 seq 恒小于 Manager 对应汇总的 seq。
```

### Phase 2：变更评估与冻结（中风险）

```text
【任务性质】在 Phase 1 交付基础上实施「停止—理解—决定」状态机；
禁止改动 Phase 1 已定的事件 schema（只增不改）。

【实现内容】
1. 新增事件与状态：work_item.interruption_requested / work_item.interrupted /
   room.change_assessment / work_item.resume_decision；快照 schema 按 Part 2.3。
   保留 Bridge 现有 cancelled 终态语义，interrupted 不是失败。
2. Agent → work item 责任映射写入 Case/Bridge 元数据（claim 时登记 owner_agent_id）。
3. 新增 AgentTeamsInterruptionCoordinator：
   - 收到 direct 消息且目标有运行中 work item 时：冻结租约（停止领取新工作）、
     按工具声明的可中断级别（cooperative/queued/external，Part 2.3）分别处理、
     保存快照；
   - 竞态规则按 Part 2.7 第 4 条（以 seq 定胜负）。
4. 能力目录为每个工具增加 interruptibility 声明字段；未声明默认 queued 并记审计警告。
5. DomainAgentRoomResponseService 接入只读变更评估（提示词 Part 3.3，
   严格 JSON Schema 输出，解析失败重试一次后降级为人工处理）。
6. 前端变更决策卡：继续原计划 / 按建议重规划 / 新建并行支线 / 终止该支线，
   四选一；卡片展示受影响任务、可复用产物（含 hash）、预计影响、是否需审批。
7. 决策执行：
   - resume → upsert 恢复（Part 2.4 幂等三规则）；
   - replan → 冻结新计划 → 走既有审批卡入口（与 Manager 同一函数）→ 批准后重派发；
   - branch → 新建独立 work item，declared_inputs 引用原可复用产物（只读）；
   - cancel → 走 Bridge 既有取消 + 级联跳过。
8. 澄清卡超时机制（Part 2.2）：stalled 投影 + Manager 跟进消息。

【验收】
- @单细胞助手「改用 scVI」：上游已完成产物保留（hash 不变），下游受影响任务冻结，
  变更评估卡字段齐全；用户确认前无任何重跑；
- 选择「重规划」后必须出现审批卡，批准后新计划与原产物复用关系正确；
- 中断请求与工作项完成竞态时行为符合 seq 定胜负规则；
- 不可中断外部流程显示「将在安全点停止/外部作业仍在运行」，绝不显示「已停止」；
- 全部状态迁移可由历史事件按 seq 重放重建。
```

### Phase 3：部门并行与容量治理（高风险）

```text
【任务性质】在 Phase 2 基础上实施部门内多 Worker 并行与广播派发；
Phase 1/2 的事件 schema 与状态机不变。

【实现内容】
1. 产物契约：work item 创建时强制声明 declared_inputs / declared_outputs；
   目录约定 output/{case_id}/{work_item_id}/；派发前编排层做写冲突检查
   （Part 2.5），冲突即降级串行 wave 并记审计。
2. Agent 下多 Worker 并行池：能力目录声明每 Agent 并行上限，Manager 结合
   Case 配额裁决；租约与占用状态写入 Bridge 元数据。
3. worker wave 生成：按依赖 DAG + 数据可用性 + 工具冲突自动分波；
   同一 wave 内任务必须互不依赖。
4. @所有人 落地：Manager 用 Part 3.5 提示词生成 waves 派发计划，
   用户可见协调说明先行，各部门更新按计划顺序展示，禁止同时流式刷屏。
5. 前端：部门视图显示 Worker 列表、依赖边、占用/配额状态；
   冲突降级时展示原因。
6. 预算与成本护栏：每 Case 可配 token/计算预算，wave 派发前预估并在
   超预算时触发审批而非直接执行。

【验收】
- 同一 Case 内「参考资料检索 / 样本表核验 / marker 知识准备」可并行，
  且与写同一输入文件的上游流程自动串行（冲突检查生效）；
- @所有人 只出现一条 Manager 协调消息 + 按 wave 有序的部门更新；
- 并行 Worker 上下文、产物目录、工具调用追踪完全隔离（case_id/work_item_id 维度）；
- 超预算派发被审批拦截。
```

---

## Part 5. 总验收 Checklist（跨阶段）

- [ ] 无提及消息行为与改版前完全一致（回归）
- [ ] mentions/target_agent_id/dispatch_mode 审计字段完整且可历史重放
- [ ] 多提及降级为 Manager 协调，mentions 全量保留
- [ ] clarification_reply 不被 @ 规则截断；超时进入 stalled 而非静默挂起
- [ ] 消息幂等：client_message_id 去重、事件按 causation_event_id 去重
- [ ] seq 单调且排序不变量成立（handoff < 汇总；interrupt_request < 后续状态）
- [ ] 变更评估卡字段齐全；确认前零重跑
- [ ] 恢复/重规划/分支全部 upsert 语义，恢复路径无重复副作用
- [ ] 工具可中断性三级声明全覆盖；伪中断文案合规
- [ ] 产物契约：声明、目录隔离、写冲突检查、content_hash 复用判断
- [ ] 领域 Agent 工具白名单在服务层强制（非提示词层）
- [ ] 审批入口唯一：direct 与 manager 路径共用同一审批卡生成函数
- [ ] 超时降级路径有审计事件且不静默丢失
- [ ] Phase 3：并行隔离、wave 有序、预算护栏生效

## 风险登记

| 风险 | 缓解 |
| --- | --- |
| Phase 0 核验发现地基与提案描述不符 | 先修订本文档锚点再启动 Phase 1 |
| 变更评估 JSON 输出不稳定 | 严格 Schema + 一次重试 + 人工降级；评估提示词随 bad case 迭代 |
| 中断竞态遗漏 | seq 定胜负 + 竞态测试用例进 CI |
| 产物契约推行阻力（存量 work item 无声明） | 存量默认「独占目录、无跨项依赖」的保守声明 |
| `@所有人` 被滥用成噪音通道 | Manager 提示词宁少勿多 + skip 理由强制填写 |
