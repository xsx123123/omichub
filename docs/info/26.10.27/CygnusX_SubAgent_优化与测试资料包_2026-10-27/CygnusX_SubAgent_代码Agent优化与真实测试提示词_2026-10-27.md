# CygnusX 子 Agent 优化 + 真实测试：可直接交给代码 Agent 的主提示词

> 2026-10-27｜复制“主提示词”全文给有仓库访问权、能调用测试环境工具的代码 Agent。  
> 配套文件（若已复制到仓库/Agent 上下文中）：`CygnusX_multi_agent_fanout.md` 的 §9、`CygnusX_SubAgent_执行可靠性与产物闭环优化方案_2026-10-27.md`、`CygnusX_SubAgent_全链路测试矩阵与验收记录模板_2026-10-27.md`。若文件不可读，要求 Agent 以实际源码为准并明确缺少材料，不能假称已读取。

---

## 主提示词（完整可复制）

你现在是 **CygnusX Multi-Agent Runtime / Agent Execution Contract / Artifact Provenance 联合负责人**，具有 Python/FastAPI、异步并发、SQLAlchemy AsyncSession、Celery、Vue 3/SSE、Agent 工具治理、科研产物溯源的工程能力。

### 一、项目背景与必须尊重的事实

我要对现有 `parallel_subagents` 做一次从“能返回答案”到“真实完成并可验收科研工作”的系统性修复和测试。请在**当前仓库中先调查真实实现和当前配置，不要机械照搬旧设计稿**。

已知证据：

1. 工具层 4 个 `sleep(5)` 探针并行 5.14s、串行 20.23s，证明那次工具层调度真并行，但**尚未证明完整子 Agent 子循环真并行**。
2. 有一次协调层给出 `4/4 status=ok`，但 `agent-code` 明确表示派生环境没有 Python 执行器、没有 shell，只有只读 workspace 工具，因而未运行代码、未写文件。**`status=ok` 不是任务已完成的证据**。
3. 另三路子任务 B/C/D 仅看到了状态，正文结果没有被正确回传/暴露；必须定位丢失发生在 provider、runner、ChildResult、aggregator、父模型上下文还是 SSE/UI。
4. 父工作区检查四个目标文件均为 MISSING；这仅证明**父工作区不可访问**，不能排除文件已在子工作区生成但未发布。必须明确分离产生、验证、登记、发布、父回读。
5. 曾出现 5 任务因 `SUBAGENT_MAX_PARALLEL` 被拒，随后**同一轮**修成 4 任务又被“本轮已分派”拒绝。检查配额使用时机与统一意图预分派双占。
6. 最新架构快照（2026-10-26 §9）指出：单批上限 4、实际 `Semaphore` 并发 3、父消息一次 fan-out；普通子 Agent 与超频 `workspace_access=true` 可用工具不同；`shania` 当时未标记可派生；普通子任务 SSE UI 复用超频泳道，出现“已完成/0/5/全部执行中”矛盾。
7. 最新快照还有工具暴露开关缝隙、超频前后台 gate 分裂、`cached_tokens` 合并单测红灯、`1200s/24 轮` 与 web 长请求冲突等已知问题。请逐一确认当前是否仍存在。

**不要为了让测试通过而直接给普通子 Agent 任意 shell、Docker、数据库写权限，或绕过现有 HITL 审批、Case/Artifact/Evidence/Manifest、租户隔离、工作区限制。**

### 二、工作目标（按顺序完成）

**G0 审计当前仓库**：提交状态、分支、真实代码位置、配置和运行环境；绘制所有调用路径矩阵（Legacy / LangGraph / 统一意图 / 超频前台 / 超频 Celery / AgentTeams / Goal / MAS），生成真实 Agent capability matrix：可派生、有效工具、实际 sandbox 权限、写文件权限、工作区挂载状态。

**G1 解决假成功**：拆分子循环 `execution_status`、任务 `outcome_status`、产物 `artifact_status`。对执行/产物型任务，必须由 **服务端工具 receipt、断言、文件校验** 判定 `succeeded`，严禁由模型自报完成。对只读问答使用 `answered_unverified` 或满足明确定义的质量标准；不要一律绿色成功。

**G2 修复缺正文**：逐层检查 B/C/D 结果：provider → SubAgentRunner → ChildResult → aggregate → `llm_payload` → parent → SSE/UI；保存每路结果的结构化摘要与完整详情引用 `detail_ref`，包括失败原因、截断状态、工具回执。父总结可读每路短摘要，前端可按权限打开完整详情。不得静默丢失其他路的结果。

**G3 Capability Preflight**：每个子任务提交前声明依赖能力（如 `python.execute` / `artifact.write` / `research.retrieve`），结合用户、项目、Agent、source/mode 的 **实际装配工具** 计算可用能力。不满足则返回 `blocked/CAPABILITY_MISSING` 或以受控方式转交已授权执行工作台；不允许把“写一段代码作为建议”当成“真的运行代码”。普通/超频授权保持隔离。

**G4 Artifact 闭环**：复用现有 Case/Artifact/Evidence/Manifest 和 MinIO/PG 文件登记能力，按 `produced → verified → registered → published → parent_reopen_verified` 管理生命周期。每个子任务有隔离目录；真实检查文件字节数/类型/sha256、来源工具 receipt、发布权限；父 Agent 以自身权限重新打开发布引用，hash 相同才宣告交付。重试发布幂等，禁止跨项目/路径逃逸。

**G5 配额与幂等**：先无副作用完成请求 shape/count、registry canonical ID、spawnable、capability、权限校验，再以 CAS/唯一键或现有幂等机制占用**一次已接受 fan-out**。5 个任务被拒绝不扣 accepted quota，同一父 user turn 改成合法 4 任务能受理；一旦受理，第二个不同请求被拒；相同 request_key 重放返回原 run。统一意图预分派与 Legacy/LangGraph 共享一致的准入语义；修复 schema maxItems、提示词和 runtime 配置漂移。

**G6 SSE/UI**：以 `run_id/task_id/seq/source` 和严格状态机投影；拒绝不生成幽灵任务；4/3 配置中显示 3 running+1 queued；`completed`（子循环结束）与 `verified succeeded`（业务完成）分开展示；文件不可用不得出现“查看产物”假链接。普通聊天采用紧凑 Fan-out 卡片（不显示超频 Wave），超频保留自己的 Wave/Manager 壳层，TaskCard 可以共享。重复/乱序 SSE、断线重连和停止/超时有正确状态。

**G7 真实并行验证**：除了已有工具层 sleep 对照，还要在 `SubAgentRunner` 中采集服务端 trace spans，以同一环境下的可控 4 个子任务与 4 个单任务串行对照证明**子任务层**并行。现在实际并发 3，不应期待 4 个固定 5s 子任务全部在 5s 内结束；应验证峰值 active≤3、queued 时间及至少 2+ 任务重叠。不可只凭 LLM 自报时间戳。

**G8 可回归验收**：为以上功能新增自动化单测、集成测试、前端组件测试以及有授权的真实 smoke，执行配套矩阵 R01–R34；现有 `cached_tokens` 断言和 quarantine 积债如仍存在要独立跟踪，不能隐藏红灯并宣称上线。

### 三、明确的执行顺序（先事实后改造）

**Phase 0 只读调查**

1. 阅读用户提供的架构文档（重点 §9）和测试矩阵，随后读取当前仓库对应模块。`git status --short`，**尊重已有未提交文件**；不得无说明大规模重构。
2. 检索而非猜测当前实现：
   - `parallel_subagent_service.py`、`parallel_subagent_tool_service.py`
   - `chat_service.py` 中 Legacy、统一意图、超频前台、SSE 与配额
   - `chat/runtimes/langgraph_runtime.py`、`goal_adapters/fanout_adapter.py`
   - `infrastructure/celery_app/tasks/overdrive.py`、`agent_consultation_service.py`
   - `tool_configs/tools_schema.yaml`、`src/cygnusx/core/config.py`
   - `agent_service._filter_runtime_builtin_tools` / Agent Registry、工具包装配
   - `frontend/src/composables/useAgentChatStream.ts` 及现有协作组件
   - `tests/unit/test_parallel_subagent_service.py` 和相关 runtime/gate/overdrive 测试。
3. 生成**当前数据流与状态图**（mermaid），列真实路径+函数+行号；对 §9 快照与当前代码差异逐条标注，不要把历史行号当真。
4. 提供每个 Agent 在不同模式下实际可用的工具能力表；说明 `agent-code` vs `code` 等 UI ID 的映射。
5. 复现最小问题并保存脱敏证据。遇到运行环境不可用时仅做静态/单测检查并报告 blocker，不能编造 smoke 已通过。

**Phase 1 P0 修复**

6. 定义 versioned `TaskContract/ChildResult/ArtifactManifest` DTO，尽量保持旧 tool response 兼容；若需要数据库迁移先设计迁移/回滚与持久化策略。
7. 在运行层加入可测的 outcome evaluator，不靠 LLM 自评；每个子任务都能拿到摘要、详情引用、工具 receipts 和验证断言。
8. 加 capability preflight 与合法降级；严格保留子循环独占 AsyncSession、防递归、防会话控制、审批升级、工作区隔离。
9. 重构准入/配额时机并覆盖验证失败后同轮合法重试、双路由幂等、请求重放与取消异常的并发竞态。
10. 先执行 P0 聚焦测试，**未通过不要继续宣称 P1 已完成**，可继续修复但明确当前关卡状态。

**Phase 2 产物闭环与授权执行**

11. 只在真正授权的工作台/沙盒中对 code/viz 测试 Python、stdout、脚本、PNG；普通无执行器环境必须返回 `blocked`。如果现有基础设施支持，复用最小权限执行接口；不新增任意 shell 后门。
12. 增加产物 manifest 的真实文件存在/解码/sha256/权限校验、发布与父回读。测试重复发布、异常中断、跨工作区拒绝。

**Phase 3 SSE + UI**

13. 建立 normalize reducer/store 与事件序号一致性；普通 Fan-out 使用小型协作面板；任务卡显示运行状态、结果验证状态、产物状态；长详情按需抽屉展示。
14. 编写 UI 单测 + 组件截图对照。重点测试 5 拒绝后**不生成任务卡**、4/3 queued、blocked 与 partial、SSE 乱序/重连、取消传播。

**Phase 4 系统测试/上线审查**

15. 逐项运行 R01–R34；至少一次真实普通 Fan-out 只读任务、一次有授权工作台代码/绘图任务、一次子任务级并行对照；记录所有失败和缺证据项。
16. 运行原有单元门禁 `pytest tests/unit -m 'not quarantine'`（实际项目测试命令以仓库说明为准），执行受影响模块集成测试、前端构建与关键 E2E；不要悄悄 `skip` 原先会失败的测试。
17. 完成必要的部署/服务重建后的真实冒烟，保留版本、日志和 UI 截图；给出可操作回滚方法。

### 四、不可接受的行为（必须当作验收失败）

- 子 Agent 说“无法执行”但父汇总 `4/4 成功`。
- 用 `sum(range(1,101))=5050` 等常识结果冒充真实 Python stdout。
- 前端/后端用 `LLM response received` 自动映射 `task succeeded`。
- B/C/D 正文丢失但聚合报告不报告这一缺口。
- 子 Agent 只在隔离目录产出，父工作区无可访问引用，却写“已交付文件”。
- 把外层 `parallel_calls` 结果当作完整子 Agent 子循环并行实测。
- `4/3` 并发时 UI 展示四个 running 或拒绝分派时 `0/5 已完成`。
- 使用已禁用的 `safe_only`/审批绕过、未经授权给普通 Agent shell、未做目录隔离。
- 修一个子 Agent 入口时破坏超频、AgentTeams、Goal 或 MAS 行为。
- 只写建议、没有实际代码 diff / 实际测试，却宣称“已修复”。

### 五、交付文件与结果格式（请实际保存到仓库现有 docs 规范下）

在不覆盖用户已有文件的前提下，创建或更新（目录可根据仓库惯例调整）：

```text
docs/subagents/
  01_current_runtime_audit.md           # 真实调用方矩阵、配置、漏洞、根因证据
  02_capability_matrix.md               # agent × mode × effective tools × artifacts
  03_execution_result_contract.md       # 状态字段/结果/向后兼容/状态机
  04_artifact_delivery_contract.md       # 产物校验、发布、父回读、权限
  05_test_execution_report.md           # R01–R34 实测结果/失败证据/指标
  06_deployment_and_rollback.md         # 灰度、开关、迁移、回滚和上线检查
  evidence/                            # 脱敏 traces/receipts/manifest/截图引用
```

优先复用现有目录和接口；如果已有同职责文档，应更新而非重复造一份。

最终对我的回答按以下结构，**不要泛泛而谈**：

1. **最终结论**：普通 Fan-out 是否可稳定纯问答、是否可实际执行、是否可交付产物（分别 PASS/FAIL/BLOCKED/NOT_RUN）。
2. **改变了什么**：文件列表、关键 diff、配置变更、迁移、权限变化（如果没有就写无）。
3. **最重要的根因**：每项给代码函数/位置、真实复现实验与证据 ID。
4. **结果真实性**：`accepted/terminal/verified_success/published_artifacts` 各自的统计和每路任务完成证据。
5. **子任务级并行证据**：服务端 spans、实际 active 峰值、serial baseline、重复次数、说明与已有工具层 sleep 数据的边界。
6. **Artifact 证据**：真实 stdout / 文件 stat / hash / manifest / parent reopen 的结果；未实现环节明确标红。
7. **R01–R34 汇总**：PASS/FAIL/BLOCKED/NOT_RUN，列证据路径，不能用一个“整体成功”代替。
8. **遗留问题与上线裁决**：安全回归、性能、负载、断线、CI、灰度和回滚。

开始时先按 Phase 0 获取事实，输出真实检查清单和诊断证据；能直接修复的按阶段实施并同步执行测试。每个阶段结束更新文档。**不要询问我已明确给出的配置或问题，不要声称没有执行的测试已通过。**

---

## 附：只想先做一次“无改动诊断”的短提示词

> 可先用以下文字做首轮诊断，确认基线后再执行主提示词。

请以当前 CygnusX 仓库为准，只读调查 `parallel_subagents` 的 5 大问题：① 子 Agent `status=ok` 但真实任务未完成；② 普通 code/viz 派生没有执行/写文件工具；③ B/C/D 仅状态而无完整正文；④ 子沙盒文件不回流父工作区；⑤ 5 任务拒绝后同轮 4 任务仍被配额拒绝。逐一检查 Legacy/LangGraph/统一路由、超频前后台、`parallel_subagent_service.py`、Agent Registry/工具装配、SSE/UI。输出真实函数路径、有效工具列表、现有准入顺序、结果信封、manifest 机制、最小复现步骤、证据缺口和 P0/P1 修复优先级；**不要改任何代码、不要给 Agent 提权、不要运行会改变生产状态的命令；无真实数据不要宣称成功**。

## 附：修复后专用冒烟提示词（需要已完成 P0）

请在已授权测试环境执行 CygnusX `parallel_subagents` 真实 E2E 冒烟，依照 R01–R34 测试矩阵做 Gate 0→5：先验证 5→4 同轮重试及幂等；然后四路独立短答和每路 ChildResult/detail_ref；再执行子任务级带固定 sleep 的 serial/parallel 对照；最后只在有执行器权限的工作台中运行 Python `print('hello')`、生成 `.py`、保存 matplotlib 五点散点 PNG、产物 sha256/manifest/发布/父空间重读。记录真实 run_id、工具 receipts、SSE、截图、失败率和权限。普通无执行器模式应正确 blocked，不要为过测试提权；B/C/D 缺正文、父工作区无可访问产物或 `4/4` 假成功均判 FAIL。输出逐项证据，不用总状态替代细节。
