# CygnusX BioOps｜当前开发完成度与真实验收状态审计

**版本**：v1.0 · 2026-10-18  
**文档性质**：交给 Codex 执行的“只读完成度核查 / Evidence-Based Progress Audit”工作说明  
**任务代号**：`CYGNUSX-CURRENT-STATUS-AUDIT-20261018`  
**核心目标**：核实 S0–S5、IAT-R1/R2、正在推进的 IAT-R3 与 G3-E2、S6/S7 各能力的**真实完成情况、阻断因素和下一步最短路径**。  
**边界**：本任务不实施新功能、不解除安全门禁、不执行真实下载、不做生产部署；只允许生成审计报告和必要的脱敏只读证据。

> **给 Codex 的执行指令**：完整阅读本文件后开始审计。不要根据阶段文档标题、README 声明、上一轮 PASS 或某个人的口头反馈，直接写“已完成”。逐项检查**当前工作树源码、实际调用链、原始测试日志、真实运行证据、权限门禁和未提交变更**。审计完成后生成 `docs/implementation/CygnusX_Current_Implementation_Status_Audit_2026-10-18.md`，并在证据可核查的范围内给出下一轮实施优先级。本任务为“检查”，**不是** IAT-R3、G3-E2 或 S6 的自动实施授权。

---

## 0. 审计目标与判断问题

请直接回答以下十个问题：

1. 到当前 HEAD + 未提交工作树为止，**哪些功能已经真正实现**，哪些仍然是设计、协议、接口、测试骨架或占位？
2. 哪些能力只有 `PASS_ISOLATED`？哪些确实有与当前代码版本一致的 `PASS_RUNTIME` 或 `PASS_E2E`？
3. 科研寻宝鼠、平台 AI Legacy/LangGraph 能否在各自**真实入口**中调用同一个 `AgentToolGateway`？工具的成功/失败语义是否正确？
4. GEO/SRA/ENA 发现、权威元数据、FileRecord、DatasetVersion、Download/Import Prepare 到底分别打通到哪一步？
5. S4 下载任务事务、幂等、Celery/Broker、恢复扫描、取消状态、文件注册和配额对账，还差哪些**真实故障注入**？
6. S3/G3 `TrustedExecutionAdapter` 是否已经从 `Protocol-only` 变成真实执行实现？九项可信 HTTP 运行测试是否真正执行且通过？
7. IAT-R3（平台 AI 完整轮次与科研寻宝鼠 React UI E2E）是否正在开发、是否已完成，真实证据是什么？
8. G3-E2（独立可信执行器、原子网络预算、磁盘硬配额、停止回执）是否正在开发、是否已完成，真实证据是什么？
9. FlowFrame 和 BioReport 的**平台对接与实际分析/报告交付**，相对目标链路还缺什么？
10. 目前是否已达到 S6 受控下载执行和 S7 真实科研闭环的门槛？如果没有，列出严格的阻断依赖。

最终必须给出：**已完成、部分完成、未完成、被阻断、现阶段开发中、证据不足**的列表，以及依赖排序后的 **P0/P1/P2 下一步任务**，不要空泛地写“继续优化”。

---

## 1. 审计范围与证据优先级

### 1.1 仓库与关联子仓

优先检查当前真实代码，不要假设文件路径永久不变：

- 主仓：FastAPI、AgentService、ToolBridge、MCPClient、AgentToolGateway、DownloadService、TaskService、DatasetService、FileRegistry、Celery、部署及验收材料。
- 科研寻宝鼠 `Treasure-Seeking_Mouse`：Node research runtime、`platform-tools.ts`、固定委托回调、React Presentation、DatasetCard、GEO 卡片、Grounding / ToolTrace、原生 UI 和测试。
- FlowFrame / FlowAgent：已有分析流程、专家审核/冻结、Handoff、计划提交与执行适配、可信 Gateway 委托情况。
- BioReport：已有报告生成、执行产物接线、科学解释/报告工作台的当前集成情况（若仓库不存在或版本不可访问则标注 `NOT_INSPECTABLE`，不得推测）。
- 仅以真实 Git 子模块和实际可访问的目录为准；没有挂载的仓库不能声称已审计其源码。

### 1.2 证据可信度顺序

1. **真实部署证据**：授权隔离环境、镜像/源码 digest、实际请求/任务 ID、PG/Redis/Broker/Worker 记录、浏览器截图、退出码、完整可复现命令。
2. **业务代码真实链路测试**：调用真实业务 Service / Runtime / Gateway 的隔离测试，准确注明 Mock 的外部边界。
3. **静态代码证据**：实现位置、函数/类、调用路径、注册表、配置与门禁。
4. **实施报告与架构文档**：只能作为线索；**不等同于当前运行验证**。
5. **README / 任务计划 / 注释 / 提示词**：只能表明设计意图，不能证明完成。

如证据冲突：优先复核原始事实，列出冲突与来源，**不要擅自选择乐观结果**。

### 1.3 统一状态模型（不要混用）

建议每个能力都独立填写这四个字段：

| 字段 | 允许值 | 规则 |
|---|---|---|
| `implementation` | `DESIGN_ONLY` / `INTERFACE_ONLY` / `CODE_PARTIAL` / `CODE_COMPLETE` / `NOT_IMPLEMENTED` / `UNKNOWN` | 基于当前源码。接口和 Mock 不等于执行实现。 |
| `verification` | `PASS_ISOLATED` / `PASS_RUNTIME` / `PASS_E2E` / `PARTIAL` / `NOT_TESTED` / `FAIL` / `BLOCKED` / `UNKNOWN` | 必须给出具体测试范围、证据及时间。 |
| `operability` | `ENABLED_AUTHORIZED` / `DISABLED_BY_GATE` / `ENV_BLOCKED` / `NOT_DEPLOYED` / `UNKNOWN` | “代码存在”不等于“当前可用”。 |
| `work_status` | `DONE` / `IN_PROGRESS` / `TODO` / `BLOCKED` / `UNVERIFIED` | 需检查当前工作树及待办；没有直接证据不得写正在开发。 |

**阶段级结论不能替代能力级结论**。例如 `S4=PASS_RUNTIME(partial)` 不意味着下载传输成功；`S5=PASS_RUNTIME(partial)` 不意味着 React 科研工作流 E2E 通过。

---

## 2. 本次审计的历史基线（仅为对照，不代表今天仍然成立）

以下来自 2026-10-17 的 `cygnusx-iat-r2-runtime-evidence-closure.md`；它是最新可见的阶段报告，Codex **必须复查当前代码及证据**，不得原样复制成今天的结论。

| 模块 | 截至 IAT-R2 报告记录的状态 | 审计重点 |
|---|---|---|
| 非生产集成验收环境 | PostgreSQL 14.23 / Redis 7.4.11 / 隔离 Compose / FastAPI / Celery / Chromium 部分实测 | 当前是否仍存在、源码/镜像是否对应当前变更 |
| S1 下载登记 | FileRegistry/Task/Owner/Source/SHA 对账已有隔离与 PG 运行证据 | 真实文件登记、失败回滚、Dataset reconcile 一致性 |
| S2 协议契约 | SRA/ENA/HTTP/HTTPS/FTP/OSS/TOS/OBS 能力描述，Cloud Drive 不实现 | 代码支持 ≠ Worker 二进制/执行认证 |
| S3 安全策略 | 参数重验、TransportAdmission、脱敏等部分代码已完成 | 运行时 egress/磁盘/取消硬约束仍缺 |
| S3-E1 / G3 | `TrustedExecutionAdapter` 在 IAT-R2 仍为 `Protocol-only`，九项 G3 测试 BLOCKED | 是否已新增可信实现及有效证据 |
| S4-A / S4-B0 | after_commit、可靠性恢复、幂等、唯一目录、取消事实保护已通过隔离回归 | 事务边界、竞争态、路径安全与历史兼容 |
| S4-B1 | 真实 PG/部分 Broker/Celery/文件可靠性已通过 | ACK 丢失、API 崩溃、长期 Worker 缺席、Beat 活性仍有缺口 |
| S5-A | 12 类 Capability Catalog，服务端状态、Scope/模块裁剪 | 当前 schema 与 tool registry 是否同步 |
| S5-B / S5-C1 | Node/平台 AI 共享 Gateway；Legacy/LangGraph 完整隔离轮次；错误传播修复 | 当前真实 runtime 装配、异常映射、撤权 |
| S5-C2 / IAT-R2 | Node `platformToolAdapter` → 实际 HTTP → Gateway → PG audit / Redis NX 已有真实证据 | 不得混同 Node 单工具调用与完整模型聊天/React 交互 |
| IAT-01 | `DELEGATION_REPLAY_BLOCKED`、`CONFIRMATION_RECORD_MISMATCH` 错误码修复，四项回归 | 当前代码、服务端返回和 ToolBridge 映射 |
| 平台 AI Legacy / LangGraph | IAT-R2 仍被空 `agent_templates`、无可用 Provider 配置阻断 | 是否已完成 IAT-R3 真实工具轮次 |
| 科研寻宝鼠 React 业务 E2E | IAT-R2 尚未具备已构建的 React 及业务测试资产 | 真实 GEO 卡、资产、Prepare、SSE/项目切换测试 |
| S6 / S7 | 不准入；尚无受控真实下载→FlowFrame→BioReport 证据闭环 | 检查新开发成果和各前置门禁 |

**IAT-R2 历史汇总（须重新计算/对账）**：78 项，`PASS_RUNTIME=42`、`PASS_E2E=3`、`PASS_ISOLATED=3`、`BLOCKED=9`、`NOT_TESTED=21`。请重新从**当前版本测试矩阵和原始证据**按 Test ID 去重计数，并检查“聚合通过”和“完整原始场景通过”的一致性。

重要反例：IAT-R2 的 `PG-11` 中 raw SQL 可直接写入不受领域状态机约束的终态，而正常 Service/Repository 路径有防护；**不能据此声称数据库级不可绕过约束已实现**。

---

## 3. 第一步：冻结当前工作树事实

### 3.1 只读操作

从主仓根目录执行，记录完整输出（注意遮盖敏感配置）：

```bash
pwd
git rev-parse --show-toplevel
git rev-parse HEAD
git branch --show-current
git status --short
git diff --stat
git diff --name-status
git diff --cached --name-status
git submodule status --recursive
```

若子仓独立存在，进入子仓再分别读取 HEAD/branch/status，检查未提交修改。确认 `FlowFrame` / `Treasure-Seeking_Mouse` 子仓修改是否被主仓指针包含，**不能只靠父仓 HEAD 判断**。

### 3.2 实际代码定位

根据仓库实际布局，用 `rg --files`、`rg -n` 等只读命令定位，并把实际路径写入报告。下列关键词仅作搜索提示，不保证文件仍在旧位置：

```bash
rg -n 'TrustedExecutionAdapter|RuntimeAdmission|DOWNLOAD_TRANSPORT_RUNTIME_ACCEPTED|WRITE_RUNTIME_ACCEPTED' src deploy tests || true
rg -n 'describe_download_capabilities|DownloadCapabilities|capability_catalog|AgentToolGateway' src tests || true
rg -n 'dispatch_download|reconcile_download_tasks|after_commit|idempotency_key|recovery_attempts' src tests || true
rg -n 'platformToolAdapter|platform-tools|delegated/invoke|dataset.prepare_import' . --glob '!**/node_modules/**' --glob '!**/.git/**' || true
```

别把报告中的提议路径当作真实源码路径；源码缺失要写 `NOT_FOUND`。

### 3.3 构建/测试版本一致性

必须记录：

- 当前 HEAD、dirty tracked 文件数、untracked 文件数、子仓 commit/dirty 状态。
- 最新 IAT-R2 与当前 HEAD 的差异、运行镜像源码 digest 是否包含未提交增量。
- 若 IAT-R3 或 G3-E2 已有新分支、新实施报告或未提交源码，定位并核对其真正修改了哪些文件。
- 不要自动 `git clean/reset/checkout`、`git submodule update --force`、`git add/commit/push`。

---

## 4. 第二步：按模块逐项核验“完成度”

每个模块均填写：**已有代码 / 实际调用入口 / 测试与证据 / 当前阻断 / 完成状态 / 下一动作**。

### A. 科研数据发现与证据（DISCOVERY）

- [ ] GEO Series / Sample（GSE/GSM）解析是否真实支持；是否保留来源与分组结构。
- [ ] SRA/ENA accession、filereport、候选文件、源证据和不完整标志是否正确。
- [ ] 文献查询与数据集关联是否真实由科研寻宝鼠工具提供，是否能定位来源。
- [ ] 未解析 GSE/GSM 是否被正确阻止直接送入 SRR 下载器。
- [ ] 外部真实 GEO/SRA/ENA **元数据**访问是否有授权测试证据；不得用本地替身宣称已完成。
- [ ] `dataset.discover` / `DatasetCard` / `GroundingNotice` 是否使用同一可信结果，而非前端伪造。

### B. Download Capability Catalog / Agent Gateway

- [ ] 12 类能力是否仍存在；`Cloud Drive` 是否明确为 `NOT_IMPLEMENTED`。
- [ ] `CODE_AVAILABLE`、`CONFIGURED`、`RUNTIME_VERIFIED`、`EXECUTION_BLOCKED` 是否分离。
- [ ] `downloads.describe_capabilities`、`dataset.discover`、`dataset.list_project_assets`、`dataset.inspect`、`dataset.list_files`、`tasks.get_status` Schema 是否与实际注册一致。
- [ ] Tools Registry / `ToolCapability.agents` / builtin MCP / Node Callback 是否调用同一 Gateway，不平行实现 DownloadService。
- [ ] `agent_kind`、user/session/project、模块和 scope 是否在 invoke **重新验证**，有限委托是否只可缩权。
- [ ] 错误码：防重放 `DELEGATION_REPLAY_BLOCKED`、审批记录不匹配 `CONFIRMATION_RECORD_MISMATCH`；HTTP 409、MCP/ToolBridge 不能假成功/不受控重试。
- [ ] 模型参数是否无法设置 caller、runtime_verified、owner、project、scope、approval 或工具地址。

### C. 科研寻宝鼠独立 Node / React / Vue 接入（IAT-R3 的一部分）

- [ ] `platformToolAdapter` 真实 Node → HTTP → FastAPI → Gateway → PG Audit / Redis NX 是否与 IAT-R2 一致。
- [ ] 是否实现并验证**完整用户聊天轮次**：输入 → Node Agent 决策 → 固定 callback → Tool Result → 聊天回复。
- [ ] React Presentation 是否实际构建/启动，是否保留 Composer、DatasetCard、LiteratureCard、ToolTrace、Grounding、Next Shovel、SessionSidebar、主题/双语。
- [ ] React/Vue Typed Adapter 与平台鉴权是否一致，当前项目/会话/迟到响应是否隔离。
- [ ] GEO DatasetCard → 来源证据 → 文件候选 → 项目已有资产 → DatasetVersion/FileRecord → Import Prepare → 待审批真实 Chromium E2E 是否通过。
- [ ] browser 登录页 200、未授权 401、顺序导航正常不可冒充上述科研业务 E2E。
- [ ] pnpm/Vite/真实 Node web-chat 服务、测试 Dataset seed、浏览器截图是否齐全；是否访问了生产 Treasure Mouse 栈（若有则列为异常）。

### D. 平台 AI Legacy / LangGraph（IAT-R3 的一部分）

- [ ] 合法的 `agent_templates` / Provider 测试配置是否存在且属于隔离环境；是否使用受控 Provider 或确定性可审查 Provider（不得伪称第三方模型真实调用）。
- [ ] Legacy：AgentService → ChatService → MCPClient → ToolBridge → Gateway → 结果回灌 → 最终回复 **真实服务**运行记录。
- [ ] LangGraph：同上完整图执行工具轮次；不以 Schema 装配或直接 Gateway 调用替代。
- [ ] 工具失败 / 禁止访问 / 过期委托的 `success` / `is_error` / SSE 终态正确。
- [ ] ToolBridge 通用上下文可信派生、有限 scope 不扩张、撤权/项目切换/历史恢复是否继续通过。
- [ ] 两套 Runtime 的执行模型和结果消费路径是否共享同一业务契约。

### E. 下载预案、人工审批与科研资产

- [ ] `downloads.prepare` / `dataset.prepare_import` 职责是否独立，不嵌套生成双审批。
- [ ] GEO 候选数据经授权选择之后，合法 ImportProposal 是否**真实持久化**；仅空 accession 校验失败不足以证明功能完成。
- [ ] 人工确认：签名/JWT、TTL、nonce、审批记录、权限重验、多并发单消费是否有真实 Redis/PG 证据。
- [ ] Prepare 是否不会直接产生真实 Download Task；批准是否与最终执行记录分离。
- [ ] DatasetVersion、FileRecord、SHA/size、Task、owner/project、Ingestion、Manifest/Handoff 的关联能否实际查询。
- [ ] processed/raw 模式对 count matrix 原始计数的科学约束是否保留，不使用 TPM/FPKM 冒充 counts。

### F. S4 下载任务可靠性（含 S4-B1/IAT-R2）

- [ ] 数据库外层 commit 后投递、savepoint/rollback 不投递。
- [ ] Broker 发布失败与请求重试使用同一 Task；API 崩溃 / ACK 丢失风险有何证据。
- [ ] `request_key`/摘要/owner/project 幂等、终态新显式键重试、别名数量上限。
- [ ] 真正的专属 Worker 是否注册 `run_download`/`reconcile_downloads`、订阅隔离队列、带正确 `SERVICE_NAME=worker`。
- [ ] 真实 Broker 重复投递、Worker 原子 queued→running、恢复扫描，以及失败/恢复日志是否存在。
- [ ] Beat 长时间故障、API 进程死亡、丢 ACK、长时间 Worker 缺席、两个扫描器与公平性，哪些仍 NOT_TESTED。
- [ ] `CANCELLED` 是否仅为业务接受取消；有无 `process_tree_stopped` 和 `egress_revoked` 的真正监督器回执。
- [ ] 任务专属目录、`O_NOFOLLOW`、marker（只作归属线索）、FileRegistry 登记与失败回滚是否正确。
- [ ] 特别检查 `PG-11`：业务层 `TaskRepository/Service` 状态防护与任意 raw SQL 写入的区别，不允许宣称 DB 层完全不可绕过。
- [ ] 真实外部下载未开放前，不把 fail-closed Celery 任务当作下载成功。

### G. S3/G3 Trusted Download Execution（含可能新增的 G3-E2 工作）

**逐项审查，任何一项只有设计或接口都不能称实现完成：**

- [ ] G3-01：OS Supervisor 真正运行在可信控制平面；普通 Worker/下载 CLI 无 root、Docker socket、DB/Broker secret、NET_ADMIN/NET_RAW。
- [ ] G3-02：单 Task cgroup v2 + network/mount scope **启动前生效**，下载 CLI 与所有后代处于同一限制范围。
- [ ] G3-03：默认拒绝 IPv4/IPv6，唯一出口；DNS/真实连接绑定、重定向逐跳验证；无直连绕过。
- [ ] G3-04：实际 RX 字节硬上界，同步阻止超量，覆盖并发连接、未知 Content-Length、Range、重试/失败流量；测量点和超调上界有证据。
- [ ] G3-05：每 Task 文件系统**块和 inode**硬配额，覆盖 output/HOME/TMP/cache/checkpoint；tmpfs/额外可写挂载有明确限制。
- [ ] G3-06：取消后可信出口撤销 + 全进程树停止 + scope 为空；进程残留绝不谎报已清理。
- [ ] G3-07：Worker SIGKILL / Supervisor 重启 / 断连后的租约与安全回收，不依赖 Worker finally。
- [ ] G3-08：经认证只允许受控 HTTP 小文件，Task/CLI hash、scope、quota、实际 FileRegistry/SHA 对账齐全。
- [ ] G3-09：9 项真实 HTTP 测试使用非 Mock `trusted_http_driver` 执行且无 skip，不把 fixture 存在算通过。

特别强调：**HTTP 认证不代表 HTTPS、FTP、SRA、ENA、EBIDownload、OSS/TOS/OBS 已认证**。RuntimeAdmission 必须绑定实际环境、工具 digest、协议、预算与 caller 通道。人工与 Agent 执行准入分别判断。

### H. FlowFrame / FlowAgent 接入

- [ ] FlowFrame 是否存在**专家审核 / 版本冻结 / 受控执行**的真实代码路径，而不仅 README 声明。
- [ ] `DatasetVersion / Manifest → FlowFrame` Handoff 是否真实写入并由原执行服务消费。
- [ ] RNAFlow / CountsDEGFlow 等目标流程是否在测试运行环境实际执行成功；数据格式/科学输入校验是否通过。
- [ ] FlowAgent 是否已加入统一可信 Gateway 委托体系，还是仅凭 API Key 访问计划接口；不要混淆规划权限与下载授权。
- [ ] 真实结果、参数、环境、工具版本、输入输出指纹是否进入统一 provenance 链。

### I. BioReport / 结果交付与科学证据

- [ ] BioReport 能否从真实受控分析结果生成报告；是否存在可复现的运行日志/产物。
- [ ] HTML/PDF 是否真实渲染并可经授权访问；引用的 DatasetVersion/ExecutionManifest 是否可追溯。
- [ ] Scientific summary/interpretation 若为新增 Agent：必须区分已完成实现、Mock / 静态展示与真实研究数据验证。
- [ ] 当前 `Research Question → GEO/ENA → Approval → Download → Dataset → FlowFrame → BioReport` 是否已做一次真实完整 E2E；没有则写 `NOT_YET_END_TO_END`。

### J. S6 / S7 最终准入

必须逐项核实以下独立条件：

| S6 真实受控下载执行准入项 | 审计问题 |
|---|---|
| S4 可靠性 | 真实 PG + Broker + 原 Worker 执行可靠性是否满足本阶段所需范围？未覆盖的故障窗口是否有可接受风险说明？ |
| S5 Agent | Node/Legacy/LangGraph 真实授权调用，人工确认与回执是否达标？ |
| G3 可信执行 | 真实执行 Supervisor、出口/硬预算/quota、九项非 Mock 测试是否达标？ |
| 审批与业务关联 | 人工审批、nonce、scope、预算是否绑定到**同一 Task/Proposal**，防重放和撤权是否生效？ |
| 逐项运行准入 | 服务端按环境/协议/工具 hash/caller（human/agent）认证，默认拒绝并可撤销？ |

**任一硬门槛缺失，S6 `NOT_READY`**；S7 真实科研 E2E 也不得声称通过。只读发现和 Prepare 可按独立门禁验收，不必等 G3 才展示。

---

## 5. 第三步：核对 IAT-R3、G3-E2 等正在开展的工作

请主动搜索最近新增/修改的实施报告、代码、测试、证据目录、分支（仅本地只读）、TODO；特别关注：

- `IAT-R3`、`Agent Runtime & Research UI`、`React Presentation`、`agent_templates`、`provider`、`Chromium`、`GEO DatasetCard`、`Import Prepare`。
- `G3-E2`、`TrustedExecutionAdapter`、`Supervisor`、`cgroup`、`network budget`、`project quota`、`trusted_http_driver`。
- `S4` 剩余故障注入、Celery Broker ACK 丢失、Worker 长期缺席与恢复机制。

**每个工作包要回答：**

1. 是否找到当前真实变更？路径与 Git diff/hunk 是什么？
2. 代码是否已连接原业务入口，还是只新增未调用模块？
3. 测试是否在当前代码、当前环境实际运行？有无 skip、fail、timeout？
4. 是否有运行认证所需的环境身份、源码版本、真实资源计量及业务关联证据？
5. 是否已提交或仍在共享 dirty worktree？子仓指针是否一致？
6. 后续还缺哪些可直接执行的工作？

如果目前看不到 IAT-R3/G3-E2 的代码/报告，写 `NO_CURRENT_EVIDENCE`，**不能从此前给 Codex 的提示词推断已经实现**。

---

## 6. 第四步：核验运行证据与验收矩阵

### 6.1 优先查验这些历史文件是否在仓库中

- `cygnusx-iat-r2-runtime-evidence-closure.md`（或仓库对应 docs 位置）
- `acceptance-report.md`
- `CygnusX_Integration_Test_Matrix_2026-10-17.csv`（含更新版本，选择当前有效路径）
- `evidence/iat-20261017/13-iat-r2/`
- `evidence/iat-20261017/05-s4-postgres/`
- `evidence/iat-20261017/07-s4-files/`
- `evidence/iat-20261017/08-s5-agent/`
- `evidence/iat-20261017/09-s5-browser/`
- `evidence/iat-20261017/10-g3-security/`

路径可能与附件不同，应先定位，不要凭文档猜测存在。无法访问原始日志时，标记 `EVIDENCE_NOT_ACCESSIBLE`，不要沿用 PASS_RUNTIME 作为已独立核实结论。

### 6.2 按 Test ID 做一致性检查

- Test ID 唯一，合计必须等于矩阵实际行数；不能重复计入同一测试。
- 从 CSV 实际状态字段重新计算数量；检查 `PASS_RUNTIME + PASS_E2E + PASS_ISOLATED + BLOCKED + NOT_TESTED (+新增状态)` 之和。
- 每项 PASS 必须能定位到一次与其原始场景一致的运行证据；`exit 0` + `skipped` 不算 PASS。
- 一个 Test ID 仅完成子断言，写 `PARTIAL`，另列子场景和未验部分；不要强行填完整 PASS。
- 错误状态如 `Celery succeeded: {'status': 'failed'}` 是**任务执行过程成功结束但业务下载失败**，不得记作科学文件传输通过。
- Chromium 登录页 200 不等于 React 科研工作台通过。
- Node `platformToolAdapter` 真实 HTTP 工具调用不等于模型对话全轮次和用户 UI E2E。
- Broker/PG 实测证据不等于可信 OS Supervisor 与硬 quota。
- 旧日志的源码 SHA/dirty diff 与新代码不一致时标记 `STALE_EVIDENCE`。

### 6.3 是否允许执行新测试

本任务默认**只读审计**。可使用 `git`、`rg`、`cat`、`stat`、`sha256sum` 及无副作用的配置检查。已有测试日志可解析。

- 仅在当前权限和资源边界已明确，且测试确定不触碰生产、不做网络下载、不进行数据库写入/故障注入的条件下，允许运行少量**纯隔离**测试验证静态判断，并完整记录命令。
- 不要因为测试环境已存在就自动重启容器、修改 `acceptance.env`、刷新凭据、迁移数据库或操作持久任务。
- PG/Redis/Worker/Chromium 运行时补测需要单独的明确非生产授权；本轮以**既有证据复核**为主，不代替后续实施任务。

---

## 7. 第五步：输出风险与优先级

按“是否阻断最终科研闭环”“能否在当前环境直接收尾”“是否存在权限或安全漏洞”“工程工作量/依赖”排序，不按文档阶段编号简单排序。

审计至少评估这些候选，**仅在源码确实支持时才判为缺陷或完成项**：

### P0 候选

1. IAT-R3 Legacy/LangGraph 完整真实 Runtime（受控合法 Agent Template/测试 Provider）。
2. 科研寻宝鼠 React 真实构建、固定回调、GEO DatasetCard → Dataset/Prepare 浏览器工作流。
3. G3-E2 实际可信 OS 执行器、egress/RX hard budget、磁盘 block/inode quota、停止回执、HTTP 九项验收。
4. S4 剩余与真实执行准入有关的提交/ACK 丢失、进程死亡及持久恢复关键场景。
5. 端到端审批→Task→FileRecord→Dataset→FlowFrame→BioReport 的真实证据链。

### P1 候选

- `ConflictError` / ToolBridge 业务码的完整映射与用户可理解错误语义。
- PG 并发幂等冲突对外行为：是否将可恢复的 `IntegrityError` 正确转化为重读同 Task/明确冲突。
- Agent 模型上下文紧凑目录，避免截断 `runtime_status` 等安全字段。
- 工作区/子仓 Git 变更归属审查；逐阶段可复现 commit/dirty manifest。
- 真实部署配置一致性：`SERVICE_NAME=worker`、Worker 注册、专用队列与镜像 digest。

### P2 候选

- 长期幂等查询性能、恢复阈值与日志关联观测。
- 后续 HTTPS、FTP、EBIDownload、云后端分协议认证。
- 未来 FlowAgent 下载工具最小可信委托及其他垂直科研 Agent 扩展。

每个问题输出：优先级、阻断模块、真实证据、具体建议、预期改动位置、验收标准、是否需要授权主机。

---

## 8. 必须生成的审计报告结构

请输出一个完整、可读、可用于下一轮分工的 Markdown：

**目标路径**：`docs/implementation/CygnusX_Current_Implementation_Status_Audit_2026-10-18.md`

```text
# CygnusX BioOps · 当前开发状态与完成度审计

1. 审计范围、时间、目标与权限限制
2. 代码基线（HEAD/branch/dirty/submodule/build digest）
3. 执行摘要（当前达成了什么、还差什么）
4. 按能力完成度矩阵
5. S0–S3/G3：下载协议、安全边界及执行设施
6. S4：Task/Broker/Celery/FileRegistry 可靠性
7. S5：Catalog、Gateway、Node、Legacy/LangGraph
8. IAT-R3：真实 Agent/React 科研 UI 的当前完成度
9. G3-E2：可信执行 Supervisor 与九项 HTTP 测试完成度
10. GEO/ENA → Prepare → Dataset → FlowFrame → BioReport 科研链路
11. 测试证据复核（矩阵计数、源码版本、日志、skip、partial）
12. 当前安全门禁与发布能力分级
13. 当前阻断（代码缺口 / 环境依赖 / 缺数据 / 缺授权 / 缺测试）
14. 本轮新发现风险与回归问题
15. P0/P1/P2 下一步实施清单（带依赖与验收标准）
16. S6/S7 Go/No-Go 结论
17. 附录：证据索引、实际命令、未能访问的文件
```

### 8.1 完成度矩阵（至少覆盖以下行）

| ID | 子系统 / 能力 | 当前源码证据 | 隔离验证 | 真实运行 | 浏览器 E2E | 阻断 | 实施状态 | 下一步 |
|---|---|---|---|---|---|---|---|---|
| D01 | GEO/SRA/ENA 权威来源解析 | | | | | | | |
| D02 | 12 类下载 Capability Catalog | | | | | | | |
| D03 | AgentToolGateway 与委托鉴权 | | | | | | | |
| D04 | Node 平台工具真实 HTTP 调用 | | | | | | | |
| D05 | 科研寻宝鼠 React/Vue 业务 E2E | | | | | | | |
| D06 | 平台 AI Legacy 完整工具轮次 | | | | | | | |
| D07 | 平台 AI LangGraph 完整工具轮次 | | | | | | | |
| D08 | Download/Import Prepare 与人工确认 | | | | | | | |
| D09 | PostgreSQL 幂等/事务一致性 | | | | | | | |
| D10 | Broker/Celery Worker/Beat 恢复 | | | | | | | |
| D11 | FileRegistry/Task/Dataset 资产关联 | | | | | | | |
| D12 | S3/G3 TrustedExecutionAdapter 实体 | | | | | | | |
| D13 | 网络原子 RX 硬预算和受控出口 | | | | | | | |
| D14 | Task FS block/inode 硬配额 | | | | | | | |
| D15 | Worker 死亡/取消后的可信停止 | | | | | | | |
| D16 | HTTP G3 九项真实安全验收 | | | | | | | |
| D17 | FlowFrame 冻结 Handoff / 受控计算 | | | | | | | |
| D18 | BioReport + Provenance 结果交付 | | | | | | | |
| D19 | S6 Human/Agent 执行认证准入 | | | | | | | |
| D20 | S7 科研闭环全链路 E2E | | | | | | | |

对**每行**附最少一条源码定位和一条相关测试/运行证据，若不存在请显式写 `NONE / NOT_FOUND / NOT_TESTED`。切勿留下默认空白让读者误解为通过。

### 8.2 三个必须回答的总结

**(A) 现阶段真正已经完成了哪些？**
按“CODE_COMPLETE+已验证”“CODE_COMPLETE+待运行”“接口/设计”“未实现”分类。

**(B) 距最终目标还有哪些明确缺口？**
只列阻断闭环的真实事项，并注明直接依赖与能否并行。

**(C) 下一轮让 Codex 先做哪 3 件事？**
输出具体路径、实施范围、DoD、预计风险，不凭主观完成百分比。

---

## 9. 最终安全与变更约束

- 默认只读：**不得修改生产源码、部署配置、安全开关、数据库、队列、用户文件或既有报告**。唯一允许的新产物为审计报告及必要的脱敏只读证据。
- 禁止真实下载、任何 Agent 自动执行、擅自网络扫描、权限提升、生产容器启停、`docker compose down -v`、数据库 DROP/TRUNCATE/FLUSH。
- 禁止将 `DOWNLOAD_TRANSPORT_RUNTIME_ACCEPTED=False`、`WRITE_RUNTIME_ACCEPTED=False` 翻为 true；不改变人类审批模型。
- 不提交/推送、不整理脏工作树、不删除或重置 Git 子模块；需要可供部署的 commit 建议只列出审查清单。
- 已通过的阶段成果不能因为新阶段阻断而被全部否定；反之也不能将局部 `PASS_RUNTIME` 推广为整个阶段完成。
- 若源码、原始证据或运行权限不足，写明确的 `EVIDENCE_NOT_ACCESSIBLE` / `RUNTIME_NOT_AUTHORIZED`，不得编造测试。
- 本任务完成后**停止**，只交付审计结果，不自行开始 IAT-R3、G3-E2、S6 或 S7 代码修改。

---

## 10. 可直接复制给 Codex 的极简启动指令

> 阅读并执行 `CygnusX_Current_Implementation_Status_Audit_Codex_2026-10-18.md`。这是一次**只读完成度审计**，不是实施任务。以当前 HEAD+dirty 工作树、子仓、真实源码、测试与 `evidence/iat-20261017/` 以及最新 IAT-R3/G3-E2 增量为准，逐项检查 D01–D20，重点识别“已实现/仅接口/隔离通过/真实通过/浏览器通过/阻断/正在开发”之间的差异。输出 `docs/implementation/CygnusX_Current_Implementation_Status_Audit_2026-10-18.md`，包含真实完成情况、证据索引、风险、P0/P1/P2 任务和 S6/S7 Go/No-Go。不得修改业务代码、生产环境和安全门禁，不得将历史报告直接写成当前结论。完成即停止。

**验收原则：能由证据证明的才写完成；没有证据的显式标注，不靠感觉估算进度。**
