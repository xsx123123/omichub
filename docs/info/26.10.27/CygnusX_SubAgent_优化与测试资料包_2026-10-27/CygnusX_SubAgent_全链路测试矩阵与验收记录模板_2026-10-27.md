# CygnusX Sub-Agent Fan-out 全链路测试矩阵与验收记录模板

> 2026-10-27｜适用于当前仓库进行**先诊断、后修复、再回归**。此表不是已经通过的测试结果。  
> 核心原则：**服务端证据优先于模型口述；子任务层证据优先于工具层外推；父空间回读优先于子路径口述。**

## A. 测试准备与运行纪律

- 在隔离开发/预发环境测试，不使用真实科研数据或生产密钥；保存当前 commit、工作区修改、配置（脱敏）、运行时版本和工具配置摘要。
- 使用有效 `Agent Registry` 获得 canonical `agent_id`；不要假设前端显示的 `agent-code` 必定是 `code`。先确认 `shania` 当前是否可派生，避免用无权限目标造成测试无效。
- 单批允许数量与真正并发数量分别记录：历史 as-built 为 **4 / 3**；以当前加载的 runtime policy 为准。
- 指定两个独立模式：**普通 Chat Fan-out（常规受限工具）**、**已授权 Overdrive 工作台（可能有 sandbox/mount）**。禁止绕过能力预检后把它们的结果合并成“普通 Fan-out 可执行”。
- 需要执行的探针使用已有受控测试工具或 mock executor；若普通 Chat 没有执行器，预期判定是 `blocked`，而非自行给它升权。
- 每个案例记录：`test_id`、`source`、`run_id`、`turn_id`、`task_id`、`tool_call_id`、`config_hash`、`commit`、`expected`、`observed`、`result`、`evidence_ref`。不要把隐藏推理正文或明文秘钥写入日志。
- 对指标至少分离 `accepted_count`、`terminal_count`、`verified_success_count`、`published_artifact_count`。

## B. 具体测试矩阵（R01–R34）

| ID | 等级 | 场景与输入 | 必须观察到的结果 | 证据类型 |
|---|---|---|---|---|
| R01 | P0 | 单次请求 **5** 个独立任务，当前上限 **4** | 参数拒绝；无子执行记录；没有 `run_started`；不消耗 accepted quota | 服务端准入事件、执行计数 |
| R02 | P0 | **同一个父 user turn 内** R01 被拒后改投合法 **4** 个 | 正式 accepted 并启动；不能再报“本轮已分派” | 同一 turn trace、状态变更 |
| R03 | P0 | 同轮第一次 accepted 后再提交另一组合法任务 | 返回 `TURN_LIMIT`/等价稳定错误；不得二次派生 | request key、run 计数 |
| R04 | P0 | 重放相同 key + 相同 payload | 取回原 run；子任务数和 tool receipts 不增加 | 幂等键、执行计数 |
| R05 | P0 | 相同 key + 不同 payload | 明确 conflict；不得静默重跑 | 接受记录、错误码 |
| R06 | P0 | 不在 spawnable 名单的 Agent（如历史快照 `shania`） | 预检拒绝目标；不执行；准确展示权限原因 | registry快照、事件 |
| R07 | P0 | tool schema `tasks.maxItems` 与 runtime 上限对照 | LLM 可见 schema、错误提示、运行时最大值一致 | schema dump、配置 hash |
| R08 | P0 | Fan-out 开关关闭 / YAML 工具包存在 | 该模式下 LLM 看不到不应暴露的工具；服务端仍拒绝绕过调用 | 有效工具清单 |
| R09 | P0 | Legacy、LangGraph 分别运行相同预检 | quota、错误、状态语义一致 | 两引擎 trace |
| R10 | P0 | 统一意图预分派 + LLM 尝试工具分派 | 同 turn 不双发、不双占；只有一次受理 | coordinator trace |
| R11 | P0 | 当前普通 code Agent 请求运行 Python/写文件但没有执行器 | preflight 识别工具缺失，`outcome=blocked`；不得 `succeeded` | effective tool list、结果信封 |
| R12 | P0 | 子循环 `completed`，文本回答“未执行” | `execution=completed` 可成立；`outcome` 必非 `succeeded` | 结果契约断言 |
| R13 | P0 | 子循环回答“我已经写好 png”，没有工具回执 | artifact `not_created`、验证失败；禁止伪造路径 | receipts、manifest |
| R14 | P0 | 三路有正文，一路返回错误/超时 | 每路都有 ChildResult，run 为 `partial`（按统一定义）；其他路结果保存 | ChildResult / 聚合 |
| R15 | P0 | 专门模拟 B/C/D 结果只剩 status | 检测出 `detail_ref` 缺失、阻断假成功并保留诊断错误 | 每层序列化 hash |
| R16 | P0 | 四路大正文总量超过模型上下文 | 父 LLM 每路有摘要 + ref；完整内容后端可取；`payload_truncated` 明示 | 结果详情读取 |
| R17 | P0 | 4 路子任务，semaphore=3，受控固定 5s 探针 | 至多 3 个同时 `running`，至少一段 `queued`；结束次序与 span 一致 | 子任务级 spans |
| R18 | P0 | 同样四路以单子任务串行 baseline 对照 | 可用同一 instrumented runner 计算并行与串行墙钟；不依赖 LLM 自报时间戳 | 服务端 monotonic spans |
| R19 | P0 | 一个子任务失败，另三个正常 | 失败不取消剩余；聚合清楚说明 3 完成/1 失败，并区分验证完成数 | 任务级事件 |
| R20 | P0 | 一路模型只输出数学可推断值，但未执行代码 | 不得产生 `tool_receipt` 或“已实测”标记 | 工具调度日志 |
| R21 | P0 | 已授权环境运行 `print('hello')`、记录 stdout | 真实执行器回执、实际 stdout、运行时版本；验证器确认 | execution receipt |
| R22 | P0 | 子 Agent 产生脚本与文本结果，隔离目录可读 | `produced` 由 `stat` + digest 证明，而不是 LLM 路径声明 | 子工作区 stat/hash |
| R23 | P0 | 子 Agent 产生 PNG 并通过文件验证 | 图像格式可解码、大小 > 0，manifest 关联 producer receipt | PNG 校验、hash |
| R24 | P0 | 产物已 produced，但父目录不存在 | 明确 `not_published`；不推断“子任务未生成” | 子 manifest + 父空间检查 |
| R25 | P0 | 产物发布到父上下文/文件中心 | 父以自己的访问权限重新打开，hash 一致；无路径逃逸 | published_ref、parent read |
| R26 | P0 | 产物重名/重试发布 | 不覆盖别人的文件；稳定幂等引用、同 hash 去重或版本化 | 发布记录 |
| R27 | P0 | 跨项目读别人的 Artifact、`../` 路径 | 拒绝并审计；不得以“为了测试”提权 | 授权/安全测试 |
| R28 | P1 | SSE `run_started` 丢失、重复、乱序 | 前端按 seq 去重，不出现幽灵卡片/状态回退；快照可恢复 | 客户端事件回放 |
| R29 | P1 | 模拟 5 任务拒绝 | UI“未启动”，无 5 张运行中卡；绝无 `0/5` 全绿 | 组件测试/截图 |
| R30 | P1 | 4/3 并发状态 UI | 3 运行 1 排队；完成后才更新；不显示错误 Wave 文案 | 组件测试/截图 |
| R31 | P1 | 一路 `blocked`、一路 `succeeded`、一路 `answered_unverified` | UI 三种状态不同；汇总“已完成”和“已验证成功”分开 | 前端状态快照 |
| R32 | P1 | 停止/超时/待审批/待补充问题 | 真正终止或暂停；不会持续转圈；不把暂停当成功 | 取消/暂停事件 |
| R33 | P1 | 超频前台 vs Celery worker 切换全局开关 | 策略统一或模式差异显式、可测试；无静默绕过 | 授权 policy trace |
| R34 | P0 | 全量非 quarantine 回归、cached_tokens 合并 | 不掩盖回归、不在未通过时宣称 ready；quarantine 单独列债务 | pytest 输出/CI |

## C. 专项并行探针（把“工具并行”提升为“子 Agent 并行”）

### C1. 变量控制

- 选择同一运行模式、相同 provider/mock、相同工具权限、同一批四个任务。
- 设置四个子 Agent 内部都必须调用**受控的** sleep(5) 测试工具（只用于测试，不对外开放任意 shell），不允许只让外层 `parallel_calls` 执行。
- 在 `SubAgentRunner` 的服务端记录 `queued_at`、`started_at`、`finished_at`，以及每路内部工具 receipt 的时间区间。
- 以子任务真实 `start/end` 的时间重叠和最大 active count 证明调度层并行；工具外层 5.14s vs 20.23s 仅作为**已有辅助证据**。
- 由于当前 `max_concurrent=3`，四任务固定 5s 的理想执行调度为两批，理论最小时间接近 10s + 开销；**不能把“4 路同时运行、5s 完成”当成现有配置的验收条件**。
- 复测时至少 3 次，汇报 mean、min/max、失败率、队列等待与 provider/tool 调用耗时。不同环境不要直接比较单次值。

### C2. 统一 trace 样例（示意、不是实测）

```json
{
  "run_id": "<run-id>",
  "source": "chat_fanout",
  "max_parallel": 4,
  "max_concurrent": 3,
  "tasks": [
    {"task_id": "<task-1>", "queue_ms": null, "start_ns": null, "end_ns": null, "status": "<status>"}
  ],
  "evidence_refs": ["<receipt-ref>"],
  "overlap_peak": null,
  "wall_ms": null
}
```

**跨进程规则**：不同进程的单调钟原点不能直接相减；需要统一 trace 机制/可信时间同步或在一个进程的 coordinator 以同一时钟记录调度观测。

## D. 最小真实执行与产物实验

### D1. 代码执行（仅在已授权沙盒）

真实执行以下内容并保存可核验的 stdout：

```python
import platform
print("hello")
print("python=" + platform.python_version())
```

要求：执行器真实返回 stdout/exit_code；脚本真实写入隔离目录；生成的 `.py` 有 sha256；发布到父空间后再次读取，并核对 hash。若缺 `python.execute/artifact.write`，正确结果是 `blocked / CAPABILITY_MISSING`，不是写出代码示例冒充执行。

### D2. 绘图（仅在已授权沙盒）

用已安装的 matplotlib / ggplot2 画 5 个点 `y=x` 的图，保存 PNG；记录绘图库和运行时实际版本、文件大小、sha256、实际可解码验证结果、父空间发布引用。没有包或没有执行器时报告能力/环境不足，不伪造图像路径。

### D3. 只读咨询与检索

使用可派生、具备检索能力的 agent，各自完成不依赖 workspace 写入的独立问题：数据入库字段契约、FASTQ QC 判读、RNA-seq 可复现元数据。输出**正文 + 摘要 + 来源/不确定性**；这些任务可以验收“答案已返回且字段符合规范”，但没有来源核验时不可宣称事实可靠已完全验证。

### D4. 产物证据矩阵（必须逐个填）

| 任务 | required | produced? | verified? | registered? | published? | parent_read? | observed evidence |
|---|---|---|---|---|---|---|---|
| code stdout | 是 | 待测 | 待测 | 待测 | 待测 | 待测 | `receipt_id`/stdout |
| code script | 是 | 待测 | 待测 | 待测 | 待测 | 待测 | sha256/stat |
| viz PNG | 是 | 待测 | 待测 | 待测 | 待测 | 待测 | decode/hash |
| data contract | 否（正文） | 不适用 | 答案验收 | 不适用 | 详情 ref | 可打开详情 | answer/ref |

## E. 运行顺序建议：不要一次测试所有复杂情况

**Gate 0（只读诊断）**：R01、R06、R07、R08、R11、R15 —— 确认配置、现有能力与假成功发生点。

**Gate 1（基础契约单元/集成）**：R01–R16、R20 —— 没有错误消费名额，没有假成功，B/C/D 可回溯。

**Gate 2（子循环并行和失败隔离）**：R17–R19 —— 子任务级 spans 证明并发和真实 queue。

**Gate 3（安全执行/产物）**：R21–R27 —— 只在授权 workspace 测试脚本/PNG/发布。

**Gate 4（界面/生命周期）**：R28–R33 —— UI、重连、取消、超频模式语义。

**Gate 5（CI / 部署）**：R34 + 门禁 + 重建容器后端到端重测；不通过前面 gate，不声称“生产可用”。

## F. 测试命令建议（先检查当前仓库再执行）

```bash
# 当前仓库根目录执行，先确认路径和项目自身说明：
git rev-parse --short HEAD
git status --short

# 聚焦已有子 Agent 单测（路径来自 2026-10-26 文档；若已改名需查找）
pytest tests/unit/test_parallel_subagent_service.py -q

# 门禁（可能含历史失败，须如实记录）
pytest tests/unit -m "not quarantine" -q
```

运行 R01–R33 时应由实施 Agent 在仓库新增相应**自动化单测、集成测试和 UI 组件测试**；本文不虚构当前已存在的 CLI 命令或 API URL。真实 E2E 需通过平台现有的授权 Chat/Overdrive 入口触发，采集 trace/manifest/screenshots。

## G. 验收记录模板（复制，每个 test 一条）

```markdown
### Rxx — <测试名称>
- commit / env / mode：
- 日期 / operator：
- 配置快照 hash：
- 输入 / 前置条件：
- 预期：
- 观察：
- 运行 run_id / turn_id / task_id：
- 服务器证据：
- 子循环工具回执证据：
- Artifact manifest / parent reopen：
- UI 截图 / 状态快照：
- 判定：PASS / FAIL / BLOCKED / NOT_RUN
- 缺陷编号：
- 修复提交（若有）：
```

### 最终总报告结构

```markdown
# CygnusX 子 Agent 真实验收报告
## 1. 运行基线和限制
## 2. 执行摘要（PASS / FAIL / BLOCKED / NOT_RUN 计数）
## 3. 最关键的 3 个问题及修复证据
## 4. 子任务级并行跨度与基线对照
## 5. 工具能力矩阵和最小权限检查
## 6. 四路 ChildResult / 正文留痕完整率
## 7. Artifact 生成→登记→发布→父回读验收
## 8. UI 状态与 SSE 一致性
## 9. 34 项测试矩阵逐项结果与 evidence refs
## 10. 未修复问题、风险、回滚和上线判定
```

**验收红线**：只要仍出现“未执行代码却认定成功”“产物没有父空间可用证据却宣称交付”“子任务 B/C/D 无法查询内容还声称 4/4 完成”，本轮只能判为**未通过端到端验收**，即使调度并行性已经通过。
