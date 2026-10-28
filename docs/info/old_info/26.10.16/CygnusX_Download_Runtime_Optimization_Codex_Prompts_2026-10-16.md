# CygnusX BioOps · 下载系统后续优化 Codex 提示词全集

**配套主文档：** `CygnusX_Download_Runtime_Optimization_Plan_2026-10-16.md`  
**当前工作区基线：** `download-completed-work-summary-2026-10-16.md`（S0/S1 已隔离通过、S2 部分、S3 部分完成，S4–S7 未完成）  
**目标：** 开展真正的**增量施工**；分阶段验收，不误称已生产可用。

## 0. 重要使用说明

**建议：现在仅复制「Prompt A · S3 Closure」给 Codex**；把此文件、优化方案和最新完成报告同时作为附件。完成、审阅 S3 报告后，再逐个发送 S4、S5、S6、S7。不要直接一次发送 A–E 要求全部实现，尤其不能跨过 G3 的强制运行依赖。

所有提示词均继承以下原则：

- 现有活动架构文档为 `ARCHITECTURE_DESIGN/CygnusX_download_architecture.md`；最新完成报告为当前事实起点，旧任务书只能作为施工计划。
- **不得重复开发已完成 S0/S1/S2**；只修本轮缺口并保留 Worker 已有 Task/source/SHA/FileRegistry/Dataset reconcile 契约。
- 当前实际工作树可能存在并行未提交修改，先只读审计 status/diff/HEAD/submodule，禁止 `reset --hard`、`clean`、随意 stash/checkout、覆盖文件或全仓格式化。
- 保留 `DOWNLOAD_TRANSPORT_RUNTIME_ACCEPTED=False` 及 Agent 既有写门禁，不用前端显示状态、Boolean `user_confirmed` 或改环境变量直接放行执行。
- 不新建第二套下载器、Celery/Task 引擎、FileRegistry、MCP Server、Agent Runtime 或审批系统。
- 可信身份来源于 JWT/已有可信 delegated context；Agent 不能指定 owner_id、project_id、服务器绝对路径、下载器任意命令、自行批准。
- 每一处实现必须明确 `PASS_ISOLATED` / `RUNTIME_BLOCKED` / `NOT_TESTED` / `FAIL`；Mock/SQLite/内存 Redis/伪 FTP/DOM 测试不能作为真实 Worker/PG/Redis/E2E 证据。
- 涉及真实下载、写 Task、启动 Worker、迁移数据库、修改生产开关、部署、提交或推送，必须另行获得用户授权；本轮没有隐式授权。
- 每个阶段输出：修改文件和函数、红绿测试、命令、证据路径、阻断原因、回滚建议、当前 Gate 结论，并在阶段结束后停止。

---

## Prompt A（**现在开始**）· S3 Closure：网络出站、硬预算、人工/Agent 边界

```text
# CygnusX BioOps · Unified Download Runtime S3 Closure

Role: 资深 Python 后端 / 下载运行时 / 应用安全 / 科研平台架构工程师。

请完整阅读以下文件，并在当前真实源码与工作树中复核：
1. CygnusX_Download_Runtime_Optimization_Plan_2026-10-16.md
2. download-completed-work-summary-2026-10-16.md
3. docs/implementation/download-s3-network-budget-safety.md
4. ARCHITECTURE_DESIGN/CygnusX_download_architecture.md
5. docs/adr/download-transport-and-asset-registration.md
6. docs/contracts/cygnusx-download-runtime-manifest-v1.md

本轮唯一主要目标：完成 S3 未完成的网络安全、实时传输硬预算、敏感信息完整边界和人工下载兼容设计与代码修复。**不得启动 S4–S7 的依赖实施。**

步骤 0：保护历史成果
- 记录 git status --short、各子模块 HEAD/dirty、当前相关源码 diff、此前 G1/G2/G3 的证据；确认已有 S3 修复不被覆盖。
- 特别保留下载 Worker 通过 FileRegistry.register 写 task_id、source、SHA-256、大小、配额和 Dataset reconcile 的 S1 行为。
- 定位 download.py、outputs/provenance/policy、download_security.py、download_contract.py、DownloadService、DTO、BinaryExecutor、ToolConfirmation、MCP、DownloadsView 的实际调用关系。

步骤 1：网络与协议
- 把来源 URL 的准入规则集中到现有安全模块中，保证 DTO/Service/Worker 对旧 Task 和内部调用一致校验。
- 覆盖 Unicode/IDNA、IPv4/IPv6、非标准数字地址、DNS CNAME/多结果、port、localhost、metadata IP、私网/回环、HTTP_PROXY 及外部代理。
- 证明实际网络连接使用经过安全验证的目标，而不仅是预解析检查；每次 redirect 后重新准入。
- 如 aria2c/底层 HTTP 工具无法安全绑定实际连接地址，采用可信隔离 egress policy/受控网络代理；当下环境不能真实证明该策略时，明确 protocol=BLOCKED、保留执行关闭。
- 对 FTP 控制连接/主动被动模式/PASV数据连接进行实际策略适用性设计，递归目录有深度、条目和总量限制；不能确保出站绑定时不允许 Agent FTP execute。
- 保持 FTPS、Aspera、泛 s3://、云盘等未支持场景为 UNSUPPORTED；不靠 fallback 绕过。

步骤 2：实际传输预算
- 为每种已有传输后端调查并实现可证明的运行时大小/总任务字节/超时/磁盘预算；准备预案阶段的配额检查和下载后的扫描上限都不能代替真实硬停止。
- 若某 CLI 不能通过受控网关或 OS/容器层确保硬字节限制，明确标记该执行协议 BLOCKED，而不是在配置文件里增加一个未生效的 max_bytes。
- 测试 Content-Length 缺失/撒谎、chunked、多文件累积、FTP目录膨胀、磁盘不足、Worker异常和部分文件回滚/对账。
- 如原子磁盘配额预留与 S4 事务提交强相关，请先记录设计与阻断，不为完成 S3 草率新增平行事务框架。

步骤 3：凭据与对话历史
- 复核 Task.parameters、CLI stderr/stdout、Worker logger、API Pydantic error、MCP error/ToolTrace、Node callback、React/Vue 消息投影和历史序列化。
- 设计执行凭据与用户/模型可见脱敏投影的隔离；不能用删除所有 query 字段破坏合法功能或审批参数哈希。
- 对无法安全执行的签名 URL 明确返回稳定错误，不把签名内容带入模型。

步骤 4：人工/Agent 安全准入
- 当前 DOWNLOAD_TRANSPORT_RUNTIME_ACCEPTED=False 同时阻断人工与 Agent。提出并落地必要的最小策略分层，使将来能按 protocol × caller_kind × identity × certification 作差异判断。
- 在当前运行门禁未通过时**两者都继续阻断 execute**；只允许安全只读或 Prepare。
- 人工 JWT 与 Node/MCP 委托不共享审批能力；模型不允许提供 user_confirmed=true 直接通过。

步骤 5：验证
- 先添加失败边界测试，再做最小修复。
- 至少完成主方案 I01–I08/G3-01–G3-10 的可运行部分，必要时加隔离 test fixtures，但不能将 mock 结果说成网络隔离已认证。
- 重新跑 S1 登记和 Dataset reconcile 的真实函数级回归；记录曾存在的 quarantine 和全仓存量问题。
- 若 Docker socket 或 aria2c/Worker 不可用，标注 BLOCKED，并输出在受控非生产环境复测的精确命令/配置要求，不能更改总门禁冒充通过。

交付 docs/implementation/download-s3-closure-implementation.md：
- 当前工作树与已完成 S3 的保留矩阵；
- network/FTP/redirect/port/dns/egress 真实策略及未支持点；
- 下载硬预算实施范围与按协议的阻断；
- 人工与 Agent 的安全门禁；
- 工具和对话凭据泄漏负例；
- 测试命令及真实结果、修改文件、Gate G3（CODE_COMPLETE/RUNTIME_BLOCKED 或 PASS_WITH_EVIDENCE）;
- 回滚策略与 S4 准入结论。

不得擅自提交、推送、部署或执行真实下载。完成本轮后停止。
```

### Prompt A 验收建议

至少应看到：Worker 的安全规则无法被旧 queued Task 绕过；真实网络 egress 与限额未被验证的协议保持 BLOCKED；响应/持久日志/ToolTrace 的安全边界清楚；人工与 Agent 的权限设计存在，但均不绕开同一个尚未解除的 transport runtime Gate；S1 文件登记相关测试未回归。

---

## Prompt B · S4：下载任务调度一致性、幂等、取消与恢复

**发送条件：** G3 已达到项目允许进入 S4 的 Gate（或用户明确授权只做隔离 S4 代码而不声称运行通过）。

```text
# CygnusX BioOps · S4 Download Task Consistency and Recovery

请阅读最新 S3 Closure 实施报告、优化方案第4章、原 S0/S1/S2/下载源代码。首先保护 dirty 工作树并复核已完成的安全门禁。

本阶段只修复既有 DownloadService/Task/Celery/Worker 的提交一致性、全局幂等、唯一下载目录、可靠取消和对账，不添加新 Task 引擎或独立下载系统。

A. 提交时序：复现 enqueue 先于 DB commit 的窗口。验证 Worker 看不见尚未提交 Task；复用现有持久 Ledger/after_commit/dispatcher，如仍缺可靠恢复才评估最小 Transactional Outbox。对不确定是否已投递的情况保留 RECONCILIATION_REQUIRED，不因 HTTP 重试产生第二 Task。

B. 幂等：为 manual REST、通用 download prepare、科研 dataset import 的调用明确 request key 与参数哈希范围。保持原 DatasetImportService request_key 的兼容性，处理同一个意图重复提交、并发、参数变化和跨用户同 URL 不得复用权限。

C. 独占目录与配额：每 Task 独立受控工作目录；禁止沿用第一个链接文件名导致重叠。预留/结算/释放配额的事务边界与真实 used_storage 无重复扣费；历史路径保持只读兼容，不自动迁移或删除用户数据。

D. 取消与恢复：区分 DB cancelled 与下载进程真正停止。只终止由 Task 拥有的子进程组；Worker kill、broker重投、下载器断点、部分文件、登记失败均具有可重建状态；不得盲目删除部分文件或自动重下载。

E. 资产：保持既有 FileRegistry.register + task_id/source/SHA/idempotency；真实登记函数和 Dataset reconcile 必须联测，禁止 double 人工写关联字段。

要求先红测再最小修复，覆盖两进程同 request_key、数据库提交竞态、配额争用、Worker crash、取消中的子进程、任务状态对账、跨用户文件归属和历史记录。

如果缺真实 PostgreSQL/Redis/Broker/Worker 环境，只能标 PASS_ISOLATED / RUNTIME_BLOCKED。保留关闭的执行门禁。

交付 docs/implementation/download-s4-consistency-recovery-implementation.md，包含 G4 判定、关键事务时序图、DB/queue故障矩阵、幂等约束、测试证据、回滚策略。完成后停止，不进入 S5。
```

---

## Prompt C · S5：统一 Download Capability Catalog（不开放执行）

**发送条件：** G4 已满足需要的依赖验收；若仍有真实运行阻断，只允许安全的 Catalog 静态投影与测试，并保留阻断。

```text
# CygnusX BioOps · S5 Shared Download Capability Catalog

请基于已完成的 S1–S4 成果和当前 AgentToolGateway / ToolCapability / MCPClient/ToolBridge / DatasetImportService 源码，扩展现有平台的统一下载能力目录。严禁新建独立 Download Gateway、AgentRuntime、MCP Server 或平行 Schema 注册表。

实现目标：目录必须按 source_family、protocol/backend、operation(READ/PREPARE/EXECUTE)、agent_kind、module/project/owner scopes、runtime certification 计算当前可信能力集；实现状态、部署认证状态与 Agent 当前可用状态分别表达。

明确支持范围：GEO GSE/GSM必须先解析；SRR/ENA文件采用权威解析和当前 CLI 契约；HTTP/HTTPS与匿名FTP独立Gate；OSS/TOS/OBS逐provider校验；FTPS、Aspera、通用S3/COS、云盘保持 UNSUPPORTED/UI_ONLY。不要仅因 frontend tab 存在就将其注册为可执行能力。

首批能力只读/Prepare：download.list_capabilities、可信 download.resolve_source、dataset.inspect/list_project_assets、dataset.prepare_import、受控 downloads.prepare、tasks.get_status；调用实际工具名优先与当前仓库同义实现对齐。不允许 Agent 直接获得自己批准自己的操作。

区分 dataset.prepare_import（科研来源/样本/预算+一次确认）与 generic downloads.prepare（受控普通文件）。不得嵌套重复确认；必要时基于现有确认/Task模型补跨入口幂等契约。

只读 Catalog 不公开系统绝对路径、二进制 hash 的敏感部署细节、Token、原始签名 URL。生产未认证的 execute 保持 BLOCKED，不能在 Tool 描述中暗示已可下载。

补齐 DTO/Schema 静态 parity、Gateway 枚举过滤、不同用户/项目与 Agent scopes、动态工具注入、已存在 FileRecord 优先复用等测试。

交付 docs/implementation/download-s5-capability-catalog-implementation.md：代码位置、Catalog Schema、实际运行状态来源、工具权限矩阵、旧工具兼容、G5 结果和可逆回滚。完成后停止。
```

---

## Prompt D · S6：科研寻宝鼠、平台 AI、FlowAgent 共享工具

```text
# CygnusX BioOps · S6 Multi-Agent Controlled Download Tools

请基于真实 S5 Capability Catalog 与当前 Agent Gateway，开展多 Agent 工具接入。不得重复开发下载器、Dataset、审批系统和Task。

1. 科研寻宝鼠：保留 React Island 原版 DatasetCard/ToolTrace/Grounding/Next Shovel 和 Node 研究内核。React 只发 typed actions，Vue/FastAPI BFF 建立可信 owner/project/session；Node 继续固定受限 delegated callback，不开放任意 MCP server URL。GEO accession 经 GeoMetadataAdapter 解析权威 Run/附件，再生成一次受控 ImportProposal。
2. 平台 AI：通过 MCPClient/ToolBridge 使用与寻宝鼠一致的 Gateway capability schema、业务 Service 和审批；修复现有动态工具注入/fixture 缺口，不能只用静态 schema parity 代替运行验证。
3. FlowAgent：先审查已有身份、Project Context、plan API，再实现最小 scope adapter（资产查询/来源检查/必要的prepare）。如无法建立可信项目与用户委托，就标 BLOCKED，不自行推断 owner/project。
4. 人工下载：原 DownloadsView 四个入口、真实 owner Task 查询和独立权限继续保留；云盘仍为未接入状态；S7 之前任何 protocol execute 不提前解禁。
5. 审批/持久化：JWT-only 人类 approve/reject、参数 hash/TTL/Redis CAS/一次性消费，下载和分析批准独立；模型不得使用 user_confirmed=true 或伪造 confirmation_id 自批；所有 Task/Asset/Report ID来自真实记录。
6. UI：统一 Proposal/Task/Artifact 投影，刷新和会话/项目切换重新 owner-scoped 恢复，ToolTrace 搜索完成不可误当真实下载成功。无真实 Task 不显示进度百分比。

验证双 Agent 的同源业务 Service 调用、工具目录 scope 差异、user/project伪造负例、过期/重放、project切换、会话历史/脱敏、已有文件免重下。真实 Node callback、Redis 双进程、PG与双用户E2E若未验收必须继续 BLOCKED。

交付 docs/implementation/download-s6-multi-agent-integration.md，列每个 Agent 当前 READ/PREPARE/EXECUTE 能力及 G6 证据、未连通项和回滚策略。完成后停止。
```

---

## Prompt E · S7：独立真实运行与科研 E2E 发布验收

**该 Prompt 只在用户提供已授权的隔离 Worker/数据库/网络/预算并明确允许实际测试后运行。**

```text
# CygnusX BioOps · S7 Isolated Runtime + Scientific E2E Validation

本轮只有明确授权的非生产隔离环境允许执行真实小文件下载、DB迁移演练、Worker测试和科学Flow；不得用生产账户、生产对象存储或真实用户资产作为演示靶点。

先复核来源清单：主仓与 EBIDownload 子仓SHA/dirty、Docker build provenance、镜像 digest、容器内 EBIDownload/aria2c/OSS/TOS/OBS版本/hash/help、运行UID、mount及 egress；scripts/inspect_download_runtime.py 的 SOURCE_ONLY 不是运行认证。

依次验证：
A. PostgreSQL 实际 schema/唯一约束/两连接并发/回滚；真实 Redis 两进程 CAS/TTL/nonce/replay/故障fail-closed；Celery/Broker commit可见性、幂等、任务终态与进程取消。
B. HTTPS与HTTP使用自控小文件服务分别验收真实网络目标和重定向安全、任务硬预算、实际FileRecord hash及source，不能用HTTP测试替代FTP。
C. 匿名FTP使用自控FTP服务验证控制/数据通道和目录上限；未认证FTP只能保持BLOCKED。SRA/ENA/GEO使用合法公开小样本、真实metadata和转换程序；OSS/TOS/OBS每种独立凭据及临时测试桶验收。FTPS/云盘保持UNSUPPORTED。
D. 真 Task→FileRegistry→DatasetAsset→DatasetVersion/Handoff 的所有关联、实际SHA、源文件身份、Worker路径可用性；两个授权用户×两个项目×寻宝鼠/平台AI的真实权限负例和模型不能自批测试。
E. 用真实来源证据完整的小型GEO raw counts先验证CountsDEGFlow、Result Manifest、BioReport与执行证据，再在资源允许时测小型SRA FASTQ→RNAFlow。所有报告/Task ID都从真实服务读取，结果不齐不得宣称科研闭环通过。
F. 人工下载和React Island的真实浏览器交互、失败状态、刷新恢复、任务与报告入口。

逐协议、逐Agent、逐operation输出运行Gate报告和已获证据。原则上恢复具体已验收能力由单独发布决策批准，测试完成不得自动改生产功能开关。

交付 docs/implementation/download-s7-runtime-scientific-e2e-validation.md 和脱敏证据索引，区分 READ_ONLY_READY、PREPARE_READY、MANUAL_EXECUTE_READY、AGENT_EXECUTE_READY、DATASET_HANDOFF_READY、ANALYSIS_DELIVERY_READY、VISUAL_RELEASE_READY。没有证据即 BLOCKED/NOT_TESTED。完成后停止。
```

---

## Prompt F · 后续 Codex 阶段交接质量审查（可选）

```text
请审查上一阶段交付报告与 git diff，先只读核对：是否重复实现了现有组件、是否回退 S1 文件登记契约、是否有隐式解除 DOWNLOAD_TRANSPORT_RUNTIME_ACCEPTED 或 Agent 写门禁、是否使用 Mock 冒充真实 Worker/PG/Redis、是否绕过 Gateway/人工审批、是否把成功下载误写 Dataset READY。列出阻断缺陷、最小修复与可重跑测试；未经允许不启动后续阶段、不提交部署。
```

## 一次性开工建议

**这次真正要执行的是 Prompt A**。给 Codex 附上两份本轮文件与最新成果总结，然后让它在 S3 闭合后输出明确 G3 结论。S4、S5、S6、S7 不应在没有 Gate 证据时被一次性自动串行启动。第一轮交付后，可以将 `download-s3-closure-implementation.md` 再发回来做代码边界审查，再决定进入下一阶段。
