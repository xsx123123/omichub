# CygnusX 子 Agent 执行可靠性、真实验收与产物闭环优化方案

> 版本：v1.0｜2026-10-27  
> 适用：普通聊天 `parallel_subagents`、Legacy/LangGraph、统一意图预分派；交叉核对超频 Wave / Celery Worker、AgentTeams、Goal，不擅自合并它们的授权边界。  
> 依据：用户提供的 `CygnusX_multi_agent_fanout.md` §9（2026-10-26 as-built 快照）、两张真实 UI 截图、用户最新并行对照与子 Agent 冒烟测试报告的**文字描述**。  
> 证据限制：本文件**没有检查在线仓库最新源码、真实运行日志或原始 `output/results/parallel_subagents_test_report.md`**；现有证据中，四个 sleep(5) 探针的并行/串行计时属于**工具层**证据，不能直接推广为完整子 Agent 子循环层的计时证据。所有建议路径与接口均须由实施 Agent 在当前仓库定位后确认。

---

## 0. 决策摘要：先解决什么、哪些不能误判

**总目标**：把“子 Agent 进程/模型返回了文字”改造为“任务经准入、在有权限的环境中真实执行、完成目标校验、生成并登记产物、把结构化结果返回父 Agent，前端显示与证据一致”。

当前问题按优先级排列：

| 紧急度 | 症状 | 确定性 | 首要动作 |
|---|---|---|---|
| P0 | 汇总 `4/4 ok`，代码子 Agent 实际未调用执行器/未生成文件 | 测试报告明确叙述 | 拆分 **运行正常**、**任务达成**、**产物可用** 三种判定；禁止用正常 LLM 回复作为业务成功 |
| P0 | B/C/D 只有状态无正文 | 报告明确叙述 | 逐层跟踪 ChildResult → llm_payload → parent → SSE，保留每个子任务的可审计结果引用 |
| P0 | `agent-code` 在该次派生中缺少执行器 | 单条子 Agent 正文明确 | 预检可用工具与权限，能力不足必须提前拒绝或降级，严禁静默标记成功 |
| P0 | 预期 4 个文件在父工作区全部 MISSING | 已执行父工作区检查；**不能证明子工作区未生成** | 分别排查“未生成 / 已生成未登记 / 已登记未发布 / 已发布未映射” |
| P0 | 5 子任务拒绝后，单轮 4 子任务亦被限制拒绝 | 上一轮真实工具反馈 | 校验在配额占用之前；校验失败不占已接纳分派配额；排查意图预分派是否已计数 |
| P1 | UI 同屏有“已完成、0/5、全执行中” | 截图明确 | 前端使用服务端状态机与事件序号派生视图，拒绝不创建运行中卡片 |
| P1 | 旧 schema `maxItems=5` 与运行时上限 4 漂移 | §4 旧规范与 §9 as-built 快照 | 统一后端 Policy、工具 schema 与模型提示（以当前源码为准） |
| P1 | 工具层并行已验证，但子循环层并行未直接验证 | 4× sleep(5)：并行 5.14s / 串行 20.23s | 子任务级记录真实服务端时间区间，控制变量对照 |

**短期安全策略**：普通 Fan-out 若无法提供已授权执行器/可回流产物，就只派预检确认可执行的只读任务；写文件、执行计算转到已有受控沙盒或 MAS/Goal/后台任务。**长期目标**不是永久禁止子 Agent 产物，而是接通明确授权的受控执行与可追溯交付。

### 0.1 三个不能混淆的“成功”

1. `execution_status=completed`：子 Agent 对话循环正常结束，并返回有效协议响应。
2. `outcome_status=succeeded`：具备**外部可验证的任务完成证据**；纯观点/开放问答只应标记 `answered_unverified` 或按明确质量标准完成，不能冒充工具执行成功。
3. `artifact_status=verified/published`：文件在子任务隔离目录真实存在，经校验/登记，并且可从父上下文访问；**未要求文件的只读任务可用 `not_required`**。

上述三者不等价。`LLM 说“完成了”` 不构成验证；正常工具信封 `success=true` 也不构成业务成功。

---

## 1. 实际架构基线与核查顺序

### 1.1 已记录的现状（以 §9 为准，不把旧 §4–8 设计视为在线代码）

- `subagent_max_parallel=4` 为单批限制，`subagent_max_concurrent=3` 是真正的 semaphore 同时运行上限；同一父消息限一次**已接受**的 fan-out（需修准入语义）。
- 普通 Legacy 调用：`src/cygnusx/application/services/chat_service.py`；LangGraph：`src/cygnusx/application/services/chat/runtimes/langgraph_runtime.py`；统一路由有独立的预执行 fan-out 入口。
- 核心子循环：`src/cygnusx/application/services/parallel_subagent_service.py`、薄壳 `parallel_subagent_tool_service.py`；工具注册 `tool_configs/tools_schema.yaml`；配置 `src/cygnusx/core/config.py`。
- §9 的可派生名单有 `code/data/qc/viz` 等 **registry 名称**；`shania` 未标记 spawnable。注意前端展示的 `agent-code` 与内部 `code` **不能不核实就等同**，从数据库/registry 获取 canonical ID。
- 子循环有独占 AsyncSession、防递归、控制工具剥离、审批转换、隔离工作目录、token usage 合并与部分审计；`safe_only`、普通聊天、超频 `workspace_access=true` 的工具域不同。
- 超频 `workspace_access=true` 才会追加工作台工具并注册 workdir mount；不能由“agent-code”这个名字推断普通 fan-out 可用 `sandbox_execute`。
- 线上记录 `SUBAGENT_CHILD_TIMEOUT_SECONDS=1200`、`SUBAGENT_MAX_ROUNDS_PER_CHILD=24`，与代码默认 180s / 6 轮不同；web 长请求需另行治理。
- 已知门禁问题包括 `cached_tokens` 单测断言失败、工具关闭后仍暴露、多前后台开关语义不一致以及 quarantine 测试积债。

### 1.2 先保全环境，再调查

1. `git status --short`、当前 commit、分支、相关服务版本、环境开关（**只记录布尔值或脱敏值**）；不覆盖用户未提交的修改。
2. 读取当前线上/本地的真实代码、registry、有效工具 schema、配置加载优先级；把 §9 视作**历史基线**，发现漂移必须单列。
3. 从服务端获取一次真实 `run_id / turn_id / task_id / tool_call_id / source` 轨迹；不能凭前端截图推断 Python 执行链路。
4. 检查后台实际持久化的执行记录、manifest、文件系统或 MinIO/PG 存储引用；缺少这些即明确报告“缺证据”。
5. 在隔离测试环境使用无真实科研数据的最小 smoke fixture；不得为了通过冒烟临时给普通用户加 shell / Docker / DB 写权限。

### 1.3 入口矩阵必须分别审查

| 入口 | 核心问题 | 预期边界 |
|---|---|---|
| 普通 Legacy `parallel_subagents` | 限额是否过早扣、错误信封是否变假成功 | 会话级准入 + 受限工具 |
| 普通 LangGraph | 是否与 Legacy 同规则、重复工具调用是否幂等 | 同语义，不同引擎一致 |
| 统一意图 `fanout` | 预分派与 LLM tool-call 是否双占额度 | 同一 turn 使用同一 coordinator/幂等键 |
| 超频前台 Wave | gate 是否与后台授权不一致 | 明确 mode 与 source |
| 超频后台 Celery | `runtime_authorized=True` 语义，workspace 额外工具和挂载 | 单独的高权限执行策略及审计 |
| AgentTeams 会诊 | `safe_only` 和 spawnable 豁免边界 | 不借咨询路径获得执行权限 |
| Goal Fan-out | 幂等持久单元与关闭门禁 | 保留 Goal 原有恢复机制 |
| MAS DAG | 长时管道、审批、完整 provenance | 不替代为 Web 请求中的超长 fan-out |

---

## 2. P0：重构子任务结果契约，杜绝“4/4 假成功”

### 2.1 建议的结果状态（兼容迁移，不直接破坏旧 `status` 字段）

**运行生命周期** `run_status`：`validating | rejected | accepted | running | aggregating | completed | cancelled`；另定义 `outcome_status`。

**子循环生命周期** `execution_status`：`queued | running | completed | error | timed_out | cancelled | awaiting_input | approval_pending`。

**业务结果** `outcome_status`：`succeeded | partial | blocked | failed | answered_unverified | not_evaluated`。其中 `blocked` 用于缺权限/缺工具/缺输入；`answered_unverified` 用于没有客观工具验收的内容型回答。

**产物结果** `artifact_status`：`not_required | not_created | produced | verified | published | publish_failed`。

注意：可异步等待审批/补充问题的任务 `awaiting_input/approval_pending` 是**暂停态**，不是已经成功的终态；需要定义由哪个工作流负责恢复。`run_status=completed` 只代表流程结束，不等价于 `outcome_status=succeeded`。

### 2.2 参考结构化 ChildResult v2

```json
{
  "schema_version": 2,
  "run_id": "opaque-run-id",
  "task_id": "opaque-task-id",
  "agent_id": "code",
  "display_name": "代码助手",
  "execution_status": "completed",
  "outcome_status": "blocked",
  "reason_code": "CAPABILITY_MISSING",
  "reason": "当前执行上下文未授权代码执行器",
  "capabilities_required": ["python.execute", "artifact.write"],
  "capabilities_granted": ["workspace.list", "workspace.read"],
  "answer_summary": "未执行：当前无可用的 Python 执行工具",
  "detail_ref": "opaque-result-record-id",
  "tool_receipts": [],
  "artifacts": [],
  "artifact_status": "not_created",
  "validation": {
    "verified": false,
    "checks": [
      {"id": "stdout_hello", "status": "not_run"},
      {"id": "file_exists", "status": "not_run"}
    ]
  },
  "timing": {
    "queued_at": null,
    "started_at": null,
    "finished_at": null,
    "elapsed_ms": null
  },
  "usage": {"input_tokens": 0, "output_tokens": 0, "cached_tokens": 0}
}
```

> 仅为**字段示例**，不是实际输出。时间、token 和工具回执一律由服务端产生；不要凭 LLM 回答生成。能不回传敏感工具参数/工作区绝对路径的字段必须脱敏。对未受理任务不产生 child 执行记录。

### 2.3 最终成功的判定器（不要让 LLM 自评）

```python
# 参考伪代码：先基于任务契约，再基于真实执行回执判定

def evaluate_outcome(task_contract, child_execution, tool_receipts, artifact_manifest):
    if child_execution.terminal_error:
        return "failed"
    if child_execution.missing_capability:
        return "blocked"
    if task_contract.requires_execution:
        if not has_successful_execution_receipt(tool_receipts):
            return "blocked"
    if task_contract.requires_artifacts:
        if not all_required_artifacts_verified(task_contract, artifact_manifest):
            return "partial" if has_some_verified_outputs(artifact_manifest) else "failed"
    if task_contract.requires_assertions:
        if not assertions_pass(task_contract, tool_receipts, artifact_manifest):
            return "failed"
    if task_contract.freeform_answer_without_objective_verifier:
        return "answered_unverified"
    return "succeeded"
```

必须单独输出：

- `accepted_count`：被服务端接纳的子任务数；校验拒绝不计入。
- `terminal_count`：结束执行（成功、失败、超时、取消）的子任务数；暂停态不计入。
- `verified_success_count`：目标验收真正通过的子任务数。
- `published_artifact_count`：已发布并可由父工作区访问的产物数。

父 Agent 禁止说“4/4 成功”，除非四路都满足各自 contract 的验证标准。若四路都完成回复但无产物，示例表述：“4 个子循环已返回，已验证完成 0 个；其余受阻或待验证”。

### 2.4 B/C/D 正文丢失：全链路定位

通过相同 `run_id/task_id` 比较以下层次的**存在性、长度、摘要 hash**（不直接打印敏感全文）：

`Provider response → SubAgentRunner → ChildResult → result serialization → ParallelSubAgentService aggregate → tool llm_payload → 父 Agent 模型上下文 → Chat SSE → 前端记录详情`

检查点：

1. B/C/D 是否真的生成 `answer`？是否只有 status 事件？
2. 是否受单子 `answer` 截断、父 `llm_payload` 字符上限、上下文窗口限制或结果序列化丢字段影响？
3. 是否出现 `answer=null`、`detail_ref` 缺失、JSON 不兼容或 tool message 被覆盖？
4. 结果是否有记录但只回给父 Agent 一路？若是，父 `summary` 必须引用所有 child 结果索引与 counts。
5. 大正文**单独持久化**为可授权读取的 `detail_ref`；父 LLM 接收每路短摘要和引用，前端抽屉查看完整内容，避免把上万字符全部塞进上下文。
6. 标注 `payload_truncated=true` 和 `dropped_fields`；不得静默截断后仍称验收通过。

---

## 3. P0：Capability Preflight 与有权限的执行器

### 3.1 用“任务能力”而不是 Agent 名称做准入

新增可测试的 capability contract；具体绑定必须由当前工具 registry 动态求值：

| Capability | 意义 | 典型工具类别 | 缺失时 |
|---|---|---|---|
| `research.retrieve` | 搜索知识库或网络，按权限 | `knowledge_search`、`web_search` | 阻断依赖检索的任务或标明不可检索 |
| `workspace.read` | 枚举/读取项目文件 | read/list/search 类 | 提示缺工作区权限 |
| `python.execute` | 真正启动可控 Python | 授权 sandbox 计算工具 | 代码运行任务预检失败 |
| `artifact.write` | 在隔离子空间写入文件 | 受控执行沙盒或输出 API | 文件生成任务预检失败 |
| `artifact.publish` | 验证并向父空间发布 | 登记/发布服务 | 不能宣称“文件已交付” |
| `approval.request` | 向父工作流上交需人工审批的动作 | 结构化审批包 | 不自行执行破坏性操作 |

Preflight 的输入至少应包含 `user_id`、`tenant/project`、`source`、`runner_mode`、`agent_id`、`task_contract` 和有效工具名单。模型声称的 capability 不能作为权限依据；必须走服务端许可求交集。

### 3.2 工具授权矩阵要可输出、可复现

先产生一个真实 `subagent_capability_matrix.md`，列出 **每个可派生 Agent** 在如下模式的 `实际有效工具`、`被剥离工具及原因`、`能否用沙盒`、`产物写权限`：

- 普通聊天 Fan-out / `safe_only` / 超频前台 / 超频后台 `workspace_access=true` / Goal / AgentTeams。
- 权限与 runtime 的依据必须是当前装配后的 tool list，而不只是 YAML 声明；敏感 tool 名单的展示仅限内部审计。
- 不能为跑通普通 smoke 而修改 `safe_only`、去除确认、开启无限 shell 或解除 workspace mount 隔离。

### 3.3 子 Agent 受控执行能力的演进路径

**路径 A（本轮可验收）**：普通 Fan-out 默认保持保守权限；若任务需要执行/写文件且无授权工具，preflight 立即 `blocked`，提供合法的替代执行模式。此时系统在安全边界上是合格的，业务执行能力仍不达标。

**路径 B（明确授权后实现）**：从已有沙盒工具/工作台策略中复用最小权限执行能力，限定受信用户、项目/工作区、CPU/内存/耗时、镜像/网络、输出目录、审批与审计；为每个子 Agent 生成独立 workspace mount。不要把父 Agent 的绝对路径或令牌复制给子 LLM。

**路径 C（长任务）**：高耗时 RNAFlow/ATACFlow/多样本流水线移交 MAS/Goal/Celery 受控持久执行，Fan-out 仅做计划、准备、监督和结果综合。

---

## 4. P0–P1：Artifact 真实生成、登记、发布与父工作区回读

### 4.1 四个必须分开的阶段

1. **Produced**：子运行沙盒中真实 `stat` 可找到文件，已由授权工具写出。
2. **Verified**：文件符合类型/大小/格式/哈希/业务断言；图件可实际解码，脚本输出和 stdout 匹配。
3. **Registered**：记录 `artifact_id`、子任务/执行回执、哈希、环境、参数与产物来源，关联已有 Case/Artifact/Evidence/Manifest 能力。
4. **Published**：通过受控的映射/复制/引用把文件提供给父 Agent 的工作区或文件中心，`parent_reopen_check=passed` 后方可算交付成功。

父空间缺文件只能证明该位置不可见，不能证明 `Produced=false`。诊断时必须检查每一层及失败原因。

### 4.2 建议 ArtifactManifest v1（示例）

```json
{
  "schema_version": 1,
  "run_id": "opaque-run",
  "task_id": "opaque-task",
  "entries": [{
    "artifact_id": "opaque-artifact-id",
    "logical_name": "hello_smoke_script",
    "child_relative_path": "scripts/hello_smoke.py",
    "mime_type": "text/x-python",
    "byte_size": null,
    "sha256": null,
    "producer_receipt_id": "opaque-tool-receipt",
    "lifecycle": "produced",
    "published_ref": null,
    "parent_reopen_check": "not_run"
  }]
}
```

`null` 值用于表示未观测到，**不代表 0 字节或校验通过**。字段在有真实证据时由服务端填写。禁止在模型文本里宣称某路径存在就创建 manifest。输出文件重名时必须按 `run_id/task_id` 命名空间或明确的冲突策略，不覆盖已有文件。

### 4.3 建议执行路径

```text
parent context / project
  └─ subagent run_id
      ├─ task_01/       # 独立挂载，最小写权限
      │   ├─ scripts/hello_smoke.py
      │   └─ output/results/hello_stdout.txt
      ├─ task_02/
      │   └─ output/figures/hello_scatter.png
      ├─ manifests/
      │   └─ artifacts.json
      └─ evidence/
          └─ tool_receipts.jsonl

# 发布动作完成后：
parent output/subagents/<run_id>/<task_id>/<artifact_name>
```

后端发布到父空间时优先复用已有 Artifact/MinIO 映射与权限服务；上述路径是**逻辑布局示例**，不得假设平台已有完全相同目录或下载 API。成功交付的判据是**父 Agent 能以其自己的凭据读取已发布引用，且 hash 一致**。

### 4.4 事务、幂等与故障恢复

- `artifact_id` / content hash 用来去重；发布接口以 `run_id + task_id + logical_name + digest` 形成幂等键。
- 产物记录与对象存储写入可能不是单事务；使用 `pending → available/failed` 状态与补偿/巡检，不出现“数据库说有，但文件丢失”假成功。
- 子任务失败前已验证的其他子任务产物继续保留；父任务是 `partial`，不能全局清空。
- 权限与隔离必须维护：禁止 `../` 路径逃逸、跨项目读取、链接逃逸、直接公开容器绝对路径、未审计外部 shell。
- 取消/超时后子进程与挂载清理、临时产物保留策略明确；父空间不得引用尚未发布的临时路径。

---

## 5. P0：Fan-out 准入、额度与双路径触发

### 5.1 只在 **accepted** 时消耗父轮分派配额

正确顺序：

`validate shape/count → resolve canonical agents → spawnable → capability preflight → auth/context policy → atomic reserve accepted slot → emit run_started → queue/run → aggregate → terminalize`

- 参数 5 个超过上限 4：拒绝、**无子任务启动**、`accepted_count=0`，不占“成功受理的一次 fan-out”。
- 之后同一模型 user-turn 改成合法 4 个：在 validation retry budget 内允许一次受理；这项必须在单次父模型工具循环的测试中复现，不能用跨 user turn 的两个聊天消息替代。
- 单轮已经受理一次，再提交**不同**任务集合：拒绝 `SUBAGENT_TURN_LIMIT`。
- 同一 request_key 完全相同的超时重放：返回原 run/result，不执行第二次；**相同 key 不同 payload** 返回冲突错误。
- 统一意图路由预分派与 Legacy/LangGraph 的主动工具调用要共享同一个 coordinator，统一 `turn_id` 和 request key，避免重复占用。

### 5.2 并发控制与任务状态

`max_parallel=4` 代表单批容量，而 `max_concurrent=3` 代表同时运行上限；四路任务应有可观察的 `3 running + 1 queued`，释放 semaphore 后 queued 才能 running。其原本超过 5 的旧工具 schema 与运行时限制必须统一，不仅改提示词。

**不要用** `4/4 status=ok`、`墙钟<串行总和` 或用户可见的动画作为并行验收依据。记录真正的子任务 `start_monotonic_ns/end_monotonic_ns`（同进程内比较），或者统一时钟基准的服务端 trace spans；如跨进程，不能直接比较不同进程的 monotonic 值。

### 5.3 配额正确性参考伪代码

```python
async def accept_fanout(request, context):
    policy = resolve_runtime_policy(context)
    result = validate_fanout(request, policy)   # 无副作用
    if not result.ok:
        return rejected(result.code, accepted=False, can_retry=True)

    # 只允许真正 accepted 的调度占用一次；持久 CAS/唯一约束
    acceptance = await coordinator.accept_once(
        turn_id=context.turn_id,
        request_key=context.request_key,
        canonical_digest=result.digest,
    )
    if acceptance.same_request:
        return await coordinator.get_existing_result(acceptance.run_id)
    if acceptance.conflict:
        return rejected("SUBAGENT_TURN_LIMIT", accepted=False)

    await persist_accepted_run(acceptance.run_id, result.tasks)
    await emit("run_started", acceptance.run_id)
    return await run_children(acceptance.run_id, result.tasks)
```

需要处理 `accept_once` 和 `persist_accepted_run` 之间 crash 的恢复/补偿；不能出现已经占名额但数据库没有 run 的幽灵记录。

---

## 6. P1：SSE / 前端状态投影与简洁 UI

### 6.1 SSE v2（建议兼容原始 `subagents` chunk）

事件字段：`schema_version`、`source`、`turn_id`、`run_id`、`task_id?`、`seq`、`occurred_at`、`phase`、`payload`；版本升级需保留旧字段映射或显式迁移。

建议阶段：

`validation_rejected` / `run_accepted` / `child_queued` / `child_started` / `child_progress` / `child_completed` / `child_blocked` / `child_timed_out` / `child_approval_pending` / `child_awaiting_input` / `artifact_verified` / `artifact_published` / `run_aggregating` / `run_completed` / `run_cancelled` / `heartbeat`。

前端只信服务端状态而不自行“模拟成功”。重复/乱序事件按 `run_id+seq` 去重；断线后通过**授权的 snapshot/replay 路径**恢复（具体路由以现有代码为准）；取消必须透传到子执行器，不只是隐藏卡片。

### 6.2 单个 task UI 提供三层信息

**第一层（默认）**：角色名、简短任务、排队/运行/已结束、`验收通过/受阻/未验证`、执行时长。

**第二层（展开）**：工具调用数、摘要、缺失能力、产物缩略图/已发布文件、重试信息。

**第三层（审计抽屉）**：完整答复（适当裁剪/权限控制）、工具 receipts、日志链接、artifact provenance、失败栈摘要（脱敏）。

普通 Fan-out 用紧凑卡片（桌面 2 列、移动 1 列），不沿用超频 `Wave 1/1` 和 `Manager → 专家 → 结论` 大面板；超频保留 Wave 容器，但底层共享 TaskCard。

### 6.3 前端绝对禁止的组合

- `run rejected` 却渲染子任务“运行中”。
- `terminal_count=0` 却显示绿色满进度 / “全部完成”。
- `3 active+1 queued` 却显示四张“运行中”。
- `outcome_status=blocked` 却用绿色“任务成功”。
- `artifact_status=not_created/publish_failed` 却出现可下载链接。

### 6.4 Vue3 候选拆分

```text
CollaborationContainer.vue
 ├─ FanoutCompactPanel.vue
 │   ├─ FanoutStatusLine.vue
 │   ├─ SubagentTaskCard.vue
 │   └─ SubagentResultDrawer.vue
 └─ OverdriveWavePanel.vue
     └─ SubagentTaskCard.vue

useAgentChatStream.ts  → collaborationEventAdapter.ts → normalizedStore
```

上面的名称是**建议**，应根据仓库现有组件做最小增量改造；不要重复创建与现有同职责组件。

---

## 7. P1：超时、重试、计费和审计

- `1200s/24` 适用于部分长场景，但在普通 Web SSE 中可能显著阻塞；按 `source/mode` 拆分短任务预算和异步后台任务预算，不改变长任务已有 SLA 前先核查。
- 每个子任务使用 `queued_at/started_at/finished_at`，工具级 traces 包含 provider/tool queue delay、LLM 时间、沙盒执行时间、artifact publish 时间。
- 失败分类：`VALIDATION_REJECTED`、`CAPABILITY_MISSING`、`PROVIDER_RATE_LIMIT`、`TOOL_TIMEOUT`、`EXECUTION_FAILED`、`RESULT_NOT_VERIFIED`、`ARTIFACT_NOT_PUBLISHED` 等。
- 重试只对明确瞬态错误（429/5xx/可重试断网），有副作用任务必须先核对 receipts / 幂等键；禁止“再试一次”生成重复文件或重复扣费。
- 汇总每个子任务 `input_tokens/output_tokens/cached_tokens`，父子聚合正确；先修文档 §9.6 所提 `cached_tokens` 回归测试，quarantine 不应掩盖相关故障。
- 审计不记录明文 API key、长 prompt、敏感样本数据、令牌、原始绝对工作区路径。必要时 hash/引用替代。

---

## 8. 分阶段实施工作包（每阶段明确退出条件）

### WP0 — 调查取证（只读）

- 读取有效配置、tool schema、Registry、所有 8 类调用入口。
- 重现：5→4 同轮重试；`shania` 非 spawnable；code 缺执行器；B/C/D 正文缺失；父空间四个路径 MISSING。
- 输出文件：`docs/subagents/audit_current.md`、`docs/subagents/capability_matrix.md`、`docs/subagents/evidence_index.md`（路径可依仓库规范调整）。
- 退出条件：每一条问题都有可验证事实、代码行号、run/trace ID 和原始/脱敏证据，不用猜测写结论。

### WP1 — 结果与准入 P0 修复

- 新增 versioned ChildResult 与 task contract，分离 execution/outcome/artifact；保留旧字段兼容。
- 准入先验证后占配额，统一意图预分派与双引擎幂等；capability preflight 缺失则 blocked，不伪装成功。
- 父 Agent 只接收**真实** counts、每路短摘要和 detail_ref；子结果长内容保留后台存储。
- 退出条件：测试 R01–R12 全绿，`4/4 ok` 不再覆盖目标失败。

### WP2 — Artifact 闭环

- 依据现有 Case/Artifact/Evidence/Manifest 接口做产生、校验、登记、发布、父回读五步。
- 在真正被授权的沙盒模式中完成 Python stdout + 文件 + PNG 的端到端验证；普通无工具模式应正确 blocked。
- 退出条件：工具证据真实、manifest 带 hash，父空间重新读取同一 hash，跨项目越权检查拒绝。

### WP3 — UI 与 SSE

- 引入状态机/事件版本；普通/超频壳层分离、TaskCard 复用，细粒度任务状态与产物证据展示。
- 退出条件：拒绝/运行/阻塞/部分完成/超时/断线重连一致；截图中不再出现错配。

### WP4 — 生产灰度与回归

- 先开发/预发环境纯问答，再 `code/viz` 授权工作台，再稳定后按白名单逐步扩大。
- 灰度随时可关闭，不污染其他入口；`pytest tests/unit -m 'not quarantine'` 与相关集成/E2E 全绿。原有失败如尚未修复须显式作为门禁阻断，不能擅自 skip。
- 输出最终修复报告：变更文件、提交 hash、测试命令、通过/失败表、性能、权限复核、回滚方法。

---

## 9. 通过标准：在“可观测性、真实性、并行、交付”四个维度分别打勾

| 维度 | 必要条件 | 不通过示例 |
|---|---|---|
| 调度 | 服务端 started/finished spans 证明重叠；4 任务/3 并发状态正确 | 只看工具层 sleep 探针；只看所有工具返回 ok |
| 完成真实性 | 任务 contract 断言由真实工具 receipts / 验收器验证 | LLM 自称完成、没 stdout 却记成功 |
| 结果回灌 | 四路 ChildResult 均可按 ref 读取，不因内容长而静默消失 | B/C/D 只有 status 且查不到正文 |
| 产物 | 子沙盒存在 → 校验 hash → 登记 → 发布 → 父回读 hash 一致 | 仅返回一个猜测路径或父目录 MISSING |
| 权限 | 普通/超频/AgentTeams 每个 mode 的有效工具域受控 | 为了过测试擅自给普通 Agent shell |
| UI | 拒绝无幽灵任务，阻塞/失败/未验证不变绿色成功 | 0/5 却显示全部完成 |
| 恢复 | 重放、乱序、重连、取消、超时有正确状态与证据 | 用户停止后子执行器继续跑 |

---

## 10. 建议代码检查索引（不是断言当前行号仍有效）

| 内容 | 优先检查处 |
|---|---|
| runtime / child outputs / semaphore / preflight | `src/cygnusx/application/services/parallel_subagent_service.py` |
| adapter / tool call result | `src/cygnusx/application/services/parallel_subagent_tool_service.py` |
| Legacy / 意图预分派 / 超频前台 / SSE | `src/cygnusx/application/services/chat_service.py` |
| LangGraph | `src/cygnusx/application/services/chat/runtimes/langgraph_runtime.py` |
| 数据模型 / 配额 / defaults | `src/cygnusx/core/config.py` |
| tool definitions / maxItems | `tool_configs/tools_schema.yaml` |
| Agent 工具装配与暴露 | AgentService、tool pack loader / `agent_service._filter_runtime_builtin_tools` |
| 工作台权限/挂载 | `src/cygnusx/infrastructure/celery_app/tasks/overdrive.py` 和实际沙盒挂载代码 |
| 前端事件 | `frontend/src/composables/useAgentChatStream.ts` |
| 测试基线 | `tests/unit/test_parallel_subagent_service.py`、`tests/unit/...` / `tests` 下相关测试 |

**规则**：修复前先找到并阅读当前函数实现与回归测试；若源文件重命名，按实际仓库搜索。绝不按历史文档的行号盲改。
