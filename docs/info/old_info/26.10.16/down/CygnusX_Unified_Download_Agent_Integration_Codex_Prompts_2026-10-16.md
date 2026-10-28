# CygnusX BioOps · 统一下载与多 Agent 工具化：Codex 全套实施提示词

**版本：2026-10-16 · 逐阶段执行版**  
**配套主文档：**`CygnusX_Unified_Download_Agent_Integration_Implementation_Plan_2026-10-16.md`  
**事实依据：** `cygnusx-platform-download-capability-and-agent-tool-readiness-audit-2026-10-16.md` 及其 E01–E50/H01–H05/I01–I05 证据索引（若已在当前仓库）。

> 使用方法：先把《实施方案》和审计报告交给 Codex，再复制最下方的 **Prompt 0（第一批 S0+S1）**。后续收到阶段验收报告后，依次用 Prompt 1–6。**不建议首次直接让 Codex 全做八阶段。**

## 0. 共享施工约束（以下每段提示词都自动继承）

```text
你是 CygnusX BioOps 现有下载服务与多 Agent 共享工具接入项目的资深 Python/Celery 数据工程师、科研资产架构师与安全验收负责人。

必须先阅读：
- 《CygnusX Unified Download & Agent Integration Implementation Plan》（当前附件，S0–S7）
- cygnusx-platform-download-capability-and-agent-tool-readiness-audit-2026-10-16.md
- 若存在 appendix-download-evidence-index.md、appendix-download-capability-matrix.yaml，读取对应证据
- 当前项目真实源码、配置、测试、ARCHITECTURE_DESIGN/CygnusX_download_architecture.md

所有历史审计结论只能作为定位线索，必须在当前 git HEAD + dirty 工作树下复核；如源码已改变，先说明差异。

共同硬约束：
1. 保护本来存在的未提交更改、子模块指针与用户文件。不得 git reset --hard、git clean、批量 checkout、强制覆盖、无权限的生产迁移、未经请求的 commit/push/release/deploy。
2. 不新增第二套下载器、第二套 FileRegistry、Dataset、Task、Gateway、MCP Server；优先复用 DownloadService、FileRegistry.register、DatasetImportService、AgentToolGateway、ToolConfirmationService、TaskService、现有 CLI 和 Worker。
3. 默认保持 WRITE_RUNTIME_ACCEPTED=False、worker_paths_verified=false 与当前 Agent 下载运行开关；不绕过源码门禁，不将人工 JWT 给 Node/LLM，不允许 user_confirmed=True 自批。
4. 所有外部下载、真实队列、Redis/PG、镜像构建/重启、网络测试与 Worker 故障注入都须事先确认在明确授权的隔离环境执行。授权不明时只运行本地无副作用测试，并标 BLOCKED。
5. 结果必须区分 VERIFIED_CODE、PASS_ISOLATED、PASS_RUNTIME、PASS_E2E、BLOCKED、FAIL、NOT_TESTED；不将 Mock/SQLite/jsdom 当真实生产验收。
6. 开发修改必须保持原人工下载 UI 入口可用，不丢原项目/用户隔离；真下载 Task 执行和科研 Dataset READY 严格分离。
7. 每个阶段交付：实际修改文件、原有文件保护、运行的测试命令及日志、API/DTO 变更、负例与已知阻断、Gate PASS/FAIL/BLOCKED、回滚方案。
8. 完成本阶段即停止。后续阶段除非用户本轮明确授权，不要自动继续；也不要因环境不足自行降低安全要求。
```

---

# Prompt 0（最推荐现在执行）· S0 + S1：真实下载文件登记修复

**完成意义：**优先修复这次审计中最高价值的断点，避免“测试替身给了 task_id，而真实 Worker 不给”的假阳性。

```text
# CygnusX · S0 + S1 — Download FileRegistry / Dataset Reconciliation Contract Fix

请按所附实施方案的 S0、S1 工作包立即进行实际代码修复与测试。本轮只聚焦下载 Worker 文件登记 → Task/FileRecord → Dataset reconcile，不开始新增 Agent Catalog、不修改生产部署。

背景（2026-10-16 审计发现，必须先复核）：
- infrastructure/celery_app/tasks/download.py 的 _register_downloaded_files 走 DataFile(checksum="") 和 FileRepository.save；没有传真实 task_id，默认来源也不标 DOWNLOAD。
- DatasetImportService.reconcile 使用 FileRecordModel.task_id.in_(task_ids) 查询下载文件，因此真实关联可能断开。
- 现有 FileRegistry.register 已支持 task_id/source/checksum，GEO 归档服务已有复用范例。
- 隔离测试 I04 的 double 手写了 task_id/source，无法证明真实 Worker 登记链。

任务 A：施工前基线
1. 只读记录主仓 HEAD、branch、status --short、diff --stat、submodule status，标记本轮可修改与既有 dirty 文件。不要 reset/clean/stash。
2. 读取审计 E05/E15/E20/E21/E46/E47/I04，以及当前 FileRegistry.register、FileRepository、FileRecordModel、Worker _register_downloaded_files、DatasetImportService.reconcile 实际源码；先确认任务传参和数据库字段名称。
3. 查找现有针对 FileRegistry/下载 Worker/Dataset reconcile 的测试，避免创建重复测试框架。

任务 B：先写失败的跨层契约测试
1. 创建受控临时 user_root/work_dir、真实内容文件、真实（隔离数据库）Task ID / Owner。
2. 用真实 _register_downloaded_files 或其实际受控入口登记，随后调用真实 Dataset reconcile 查询 Task 产物；仅网络下载和 Queue 可以 stub。
3. 断言 FileRecord.task_id、source、实际 SHA-256、size、owner、路径归属，以及 DatasetAsset 引用。
4. 在修改实现前记录 red-test 结果；禁止 fixture 自己填 FileRecord.task_id/source/checksum 掩盖生产差异。

任务 C：最小修复
1. 优先让下载 Worker 调用现有 FileRegistry.register（或其共享后端方法），传真实 task_id、source=DOWNLOAD、实际计算的 SHA-256、size 和 owner。不要新增平行 FileRegistry；除非真有缺口且有评审证据，否则不要数据库迁移。
2. 工作目录/输出 manifest 中仅登记本次 Task 的产物，排除 .aria2、checkpoint、progress.key、日志等控制文件；拒绝 symlink/hardlink/特殊文件和目录逃逸。
3. 重复登记时保持安全幂等；已有未绑定或不同 Task 的同路径记录不得静默冒领；避免 used_storage 重复计费。
4. Task 非零退出但存在 partial 文件、成功退出但产物为空/缺失时，使用既有 Ingestion 对账语义明确报告，不将其提升为 Dataset READY。
5. 不删除历史孤儿文件；老记录补关联单独生成只读回填计划。
6. 不把下载完成状态直接当作原始表达矩阵的科学核验完成；保留 DatasetVersion 审核和 frozen Handoff。

任务 D：验收
至少实际运行实施方案 F01–F12；覆盖单文件、多文件、跨用户、控制文件、旧记录、冲突 hash、重试、异常、部分产物以及真实 Worker register → Dataset reconcile。
随后运行 DownloadService、DatasetImportService、FileRegistry、Task/owner 相关存量测试与必要静态类型/ruff/mypy。真实 Worker/PG/Redis 不可用时保持 BLOCKED，不得宣称运行级 PASS。

交付：
- docs/implementation/download-s0-baseline-and-red-test.md
- docs/implementation/download-s1-file-registry-dataset-bridge.md
- 按实际测试函数逐项列出 FAIL_BEFORE/PASS_AFTER 或仍 BLOCKED 的证据
- 明确回答：现有 FileRegistry 是否复用成功、真正的 task_id/source/SHA 从哪里写入、Dataset reconcile 是否不再依赖 double 手工赋值。
- 给出最小回滚（不删除任何用户下载数据）和 G1 结论。

不要开始 S2–S7；完成后停止等待下一步指令。
```

---

# Prompt 1 · S2：Worker 镜像来源、传输协议和版本契约

```text
# CygnusX · S2 — Existing Worker Binary Provenance & Transport Contracts

前置检查：读取 S1 报告确认 G1 状态，复核当前 dirty baseline。若 G1 未过，仅能进行不依赖该 Gate 的协议静态修复，不得标记下载运行 READY。

本轮聚焦已存在 Worker / EBIDownload / aria2c / 云存储 CLI 的真实来源和协议适配；不重新开发下载器，不直接替换宿主或生产二进制。

1. 审计 deploy/docker/Dockerfile.worker、docker-compose、下载 tool YAML、DownloadRequest/source enum、_execute_download 及构造 CLI argv 的各分支。
2. 明确源码子模块 EBIDownload 1.4.0、宿主 EBIDownload 1.4.0、旁仓 Polariseq 1.4.3 与 Worker 运行镜像之间的差异；真实 Worker 无证据时留 UNKNOWN，不假定旁仓自动部署。
3. 修复人工 SRA 下载下拉的 Aspera 与 CLI（ftp/prefetch/aws/auto）不一致；不做虚假的 aspera→ftp 静默转换。检查 include/exclude 高级参数是否真的传到对应业务/CLI；没有实现就给明确不支持态。
4. 核对 HTTP/HTTPS、FTP（含目录）、FTPS、OSS/TOS/OBS、通用 s3/COS、云盘 share 链的 schema/执行事实；对不支持的选项返回稳定 reason code，不能继续用营销文案误导。
5. 明确 YAML/Settings/环境变量的优先级，特别是 binary path 与 Web/Worker STORAGE_PATH/WORKER_SHARED_DATA_DIR 的真实关系；输出可核验的版本/依赖/UID/挂载 Manifest。
6. 如需要修 Worker image 构建文件，采用有版本与 checksum 可审计的声明；**不要直接启动 Docker build 或改生产部署**，只做静态/isolated build（环境允许才运行）并记录证据。
7. 增加源/方法 DTO 表驱动测试、未知传输拒绝、CLI 参数兼容、版本/配置漂移负例，以及不打印任何密钥的 Manifest 验证。

验收 G2：每种来源的静态支持范围精确、UI 与 DTO/Worker 一致、镜像/二进制来源有可复验 Manifest；没有容器运行证据则实际下载仍 BLOCKED。

交付 docs/implementation/download-s2-worker-protocol-provenance.md、工具版本矩阵、证据、回滚、测试与仍未解决的 runtime Gates。完成后停止。
```

---

# Prompt 2 · S3：HTTP/FTP/云 URI 安全、硬预算和文件限制

```text
# CygnusX · S3 — Download Security, Network Policy & Hard Budget

基于 S0–S2 的验收结果，在当前既有 DownloadService/DownloadRequest/Worker 上做增量安全修复，不新增下载器、不擅自开启 Agent 执行。

审计已知问题（以实际代码重新确认）：
- direct_link DTO 仅过滤部分危险 scheme/显式内网 IP；没有完整的 DNS 绑定和重定向逐跳复核。
- FTP 递归目录由 ftplib 执行，缺限深/限数/限字节，数据连接网络策略未认证；ftps DTO 不接受。
- _validate_cloud_host 的 try/except ValueError 可能吞掉校验抛错，IPv6/无点数字裸 bucket 边界需修复。
- max_bytes 没进入 Worker 的有效硬停止链；REST links<=100 会被目录递归放大。
- 签名 URL 查询参数、object_uri 及 CLI stderr 可能存在敏感日志暴露。

任务：
1. 建立 Service 与 Worker 共享或等价的可信源/协议/地址策略；对 URI 做完整规范化、IP 类型/主机/端口/用户凭据/编码检查。
2. 每个网络跳转执行同样的目标限制；如果现有 aria2/wget/FTP 不能可信保证 Worker 出站约束，应采用经过验证的网络级限制/源白名单，并明确哪些协议仍不能开放 Agent；不能仅在 FastAPI 的 DTO 过滤。
3. FTP 目录最多深度、数量、总字节与超时由服务器明确限额；不能让 FTP 递归扩展后无限提交。
4. 在 Worker 执行或可信代理层实测硬字节限制和配额/目录占用；size 预估与实际字节分别记录；未知大小在预算上限内运行或拒绝。
5. 签名URL、HTTP query、object URI、认证信息必须脱敏保管和日志呈现；Node ToolTrace 与对话 history 不得回显密钥。
6. 下载/归档解压使用现有 Dataset 安全逻辑，拒绝路径逃逸与压缩炸弹；不得混入新解压器。
7. 添加不访问生产网络的受控 mock/loopback（如沙箱禁止 socket 则 fixture）负例：整数IP、IPv6、DNS重绑定、redirect到内网、FTP数据地址、恶意目录树、溢出预算、无法读取Content-Length、敏感URL日志。
8. 保留人工下载安全体验，绝不能通过打开网络出口、关闭安全校验或修改源码写门禁追求测试绿灯。

验收 G3：DTO、Service、Worker 的策略一致；不安全URL/重定向/FTP/超预算/路径/日志负例被拒绝；若运行层网络硬策略不可验证，Agent 任意 URL execute 继续 BLOCKED。

交付 docs/implementation/download-s3-network-budget-safety.md、技术约束/逐协议准入表、实际测试和运行缺口、最小回滚。完成后停止。
```

---

# Prompt 3 · S4：任务事务、幂等、唯一目录、取消与恢复

```text
# CygnusX · S4 — Download Task Consistency & Recovery

读 S0–S3 和当前下载/Task/dispatcher/Worker/Storage 源码，先确认旧任务和人工下载 UI 的兼容约束。

本轮重点修复：
1. DownloadService.enqueue_task 在外层 API DB 最终提交前发生的竞态，选择并实施仓库可复用的可靠提交方案（已有 outbox 优先；没有则事务提交后投递+失败对账机制）。不要宣称 exactly-once；保证逻辑幂等和可恢复。
2. Task work_dir 变成唯一受控任务目录，避免以 accession/首链接生成同名目录碰撞；保持 owner storage root 安全。
3. 对稳定 request_key/source snapshot 与 normalized_params 做幂等，跨入口检查已有 FileRecord/进行中 Task；不能让两用户共用任意一个私有资产。
4. 下载开始前可信配额预留、运行硬预算、最终实际 size 对账和失败时安全释放；注意并发资源竞争。
5. 任务失败、Worker 被杀、队列投递歧义、文件已写但注册失败时保留 RECONCILIATION_REQUIRED/PARTIAL 语义，按已有 Task Enum 设计投影，避免破坏客户端。
6. 真实取消需发到下载 Worker/受控子进程组，而不是只把 Task 状态变 cancelled；聊天 cancel 与持久下载 Task cancel 严格分离。
7. 重试不得无条件重新发起网络下载，需先对账 Task、checksum、源、预算、已存在文件；不清理未知部分文件。
8. 加强下载 UI 的实际任务列表/status/progress 查询，避免 direct_link 被误标 SRA 或返回虚构速度。

测试至少包括：延迟 DB commit 与 Worker 提前读取、Broker enqueue 失败、重复提交/队列重复、并发两个用户同名链接、Worker crash/取消部分文件、相同路径不同 SHA、重试前 source 变化、配额回收与人工 Task 查询。

验收 G4：不丢真实 Task，不重复创建可计费副作用，有明确人工对账 runbook；真实 Redis/PG/Worker 未验时只能 PASS_ISOLATED，不能开放 Agent write。

交付 docs/implementation/download-s4-task-idempotency-recovery.md、状态机、任务对账操作手册、测试/回滚。完成后停止。
```

---

# Prompt 4 · S5：统一下载能力目录（共享 Gateway，暂不开放执行）

```text
# CygnusX · S5 — Shared Download Capability Catalog

首先读取 2026-10-16 审计 §7–8/§12 及 S0–S4 报告；确认业务 Service/安全门禁未被重复实现。

目标是在既有 ToolCapability、AgentToolGateway.describe_capabilities、现有 schemas 与 MCP ToolBridge 上扩展一个按“来源×协议×角色×权限×运行认证”的 Download Capability Catalog。不是创建第二个 MCP Server 或独立 Agent Runtime。

执行：
1. 盘点当前 catalog 的 schema_version/scope/side_effect/input_schema/approval/idempotency/agents/runtime_status 等字段；优先复用，最小扩展。
2. 对 D01–D16 逐项映射为 supported/partial/unsupported 与 runtime unknown/blocked/pass，并给出 reason_code；不要把旧 downloads 的 unsupported processed_matrix 当作全平台 Dataset processed prepare 不支持。
3. 增加或投影只读能力列表、GEO/ENA source resolver、owner project FileRecord 查询、Task 状态查询、Dataset 受控 Prepare 的真实可用性。新名字以已有工具目录为准，不重复注册同义功能。
4. 严格检查 user/project/session/modules/agent_kind/limited delegation scopes。FlowAgent 尚无可信下载身份上下文时只报告 NOT_INTEGRATED；不要默认授予全工具。
5. 对 agent-visible catalog 只提供无需保密的协议、来源、预算、原因和状态；容器绝对路径、镜像完整 digest、凭据只能出现在可信审计/运维记录，不能暴露给 LLM。
6. Catalog 只读返回并不代表 Gateway invoke 自动通过；服务端最终授权/门禁需重新检查，状态变更实时可见或有失效机制。
7. 云盘仍 STUB，FTPS/通用S3/COS不因统一工具列表而自动接入；未认证 HTTP/FTP 下载执行不暴露。

验收：capability 列表真实、不同 Agent/Owner/project 权限切片准确；feature flag关闭或Worker未验状态表现一致；schema与handler、测试 fixture 完整，未自动开启任意写工具。

交付 docs/contracts/cygnusx-download-capability-catalog-v1.md、docs/implementation/download-s5-agent-catalog.md，Catalog兼容说明与G5测试。完成后停止。
```

---

# Prompt 5 · S6：寻宝鼠、平台 AI、FlowAgent 的工具投影与预案

```text
# CygnusX · S6 — Multi-Agent Download Tools & Dataset Prepare

本阶段只有在现有读/预案安全基础通过相应 Gate 后进行受控增量；必须保持 WRITE_RUNTIME_ACCEPTED=False 等源码门禁。

目标：同一 download/dataset/Task 业务服务可由多个 Agent 通过各自可信适配调用；不是统一为同一种网络协议，也不是给各 Agent 相同全权限。

任务：
1. 科研寻宝鼠：保留旧 React Island FullPresentation、DatasetCard/Grounding/NextShovel；Node 固定委托 callback→AgentToolGateway；React只触发typed意图，Vue/BFF解析可信Project/session。为GEO/supplementary增加受控source inspect、Dataset import prepare与任务状态；不让模型自己挑任意服务器URL/执行路径。
2. 平台 AI：核查 MCPClient/ToolBridge 现有 dynamic tool catalog 到Gateway的运行一致性；修复审计指出的 isolated fixture 缺 legacy_pipeline_tools 问题，不用 skip 掩盖；测试该工具真实进入允许的schema/handler。
3. 外部 MCP：核查 legacy wrapper cygnusx_submit_download 与真实后端source/method支持；纠正声明可GSE/GSM/Aspera/raw_data的失真；拒绝user_confirmed布尔自批，复用JWT-only confirmation。
4. FlowAgent：调查现在只有Snakemake plan的事实；如无可信 user/project delegated context，先产出适配设计、标NOT_INTEGRATED。可以仅实现经批准的 read/inspect/prepare adapter，绝不借共享API Key冒充最终用户或自动执行。
5. ImportProposal是科研来源/样本/预算权威；downloads.prepare给普通受控来源使用；不让import嵌套再次prepare或双审批；跨入口重复提交提出明确已存在资产/源快照复用策略。
6. 对话中展示的ToolInvocation/Proposal/Task/Report引用必须来自服务器持久记录。无已完成真实Task不能显示下载成功/进度；未通过运行认证时明确BLOCKED原因。
7. 动作恢复：项目切换、刷新、跨用户、确认过期、nonce重放、后台任务继续运行与取消对话分开。

测试：两Agent同一Gateway/Service/Schema；用户A项目A不能读B项目；未授权Agent不见execute；Node不能看到人类JWT；prepare不产生Task；确认需要真人JWT；已存在真实Task只读恢复；动态MCP工具注入本地隔离通过，真实Transport继续独立Gate。

验收 G6：只读/prepare/status完整实现且有相关隔离测试；FlowAgent状态诚实，不能声称所有Agent已上线；后台写门禁继续关闭。

交付 docs/implementation/download-s6-multi-agent-tool-integration.md、权限矩阵、Tool Catalog/API diff、React UI回归/测试日志/回滚。完成后停止。
```

---

# Prompt 6 · S7：隔离真实 Worker 与科研 E2E 发布验收

```text
# CygnusX · S7 — Isolated Runtime Closure / Release Gate Validation

本阶段属于独立运行验收任务，不是继续增加组件。执行前必须得到明确的非生产隔离环境授权、用户/项目、文件前缀、网络目的地、资源预算、备份策略；若未授权，仅输出可执行 runbook，不真实下载或改变部署。

按 DL-RG01–DL-RG15 逐项验收：
1. 源码、子仓、镜像 digest 与 Worker 内 EBIDownload/aria2/OSS/TOS/OBS版本/哈希/UID/挂载一致。
2. 真实 PostgreSQL 迁移/owner/并发事务；Redis 双进程 nonce/CAS/TTL/replay；实际 Celery broker 调度、任务提交与回滚/对账。
3. HTTP/HTTPS小文件、FTP控制/数据连接、SRA小Run、GEO小supplementary、OSS/TOS/OBS按来源分别通过实际bytes/checksum/源安全/预算；云盘/FTPS如未实现明确UNSUPPORTED。
4. 验证真实Task ID→FileRecord.task_id/source/SHA→DatasetAsset→DatasetVersion→Frozen Handoff；缺用户/项目权限和校验不应提升READY。
5. 双用户/双项目 REST/Node delegated Gateway/MCP scopes、撤权、令牌重放、异常网络重定向与预算安全负例。
6. Worker kill/断网/取消、重复消息、partial文件、登记失败与恢复，确认真实进程/文件/DB和配额一致。
7. 两个Agent以真实可授权方式复用同一业务Gateway；Node/MCP适配协议允许不同，但必须共享真实Service和安全规则。
8. 用户明确授权且对应Gate已通过时，用合法的小型GEO raw counts / SRA FASTQ案例从来源、下载、FileRecord、DatasetVersion到FlowFrame Task、Result Manifest与Scientific BioReport/Execution Evidence Report，留下全部真实ID/hash。无法完成则报告阻断，不造成功结果。

所有Gate逐项标PASS_RUNTIME/PASS_E2E/FAIL/BLOCKED，记录环境版本与安全回退计划；只允许按具体协议/Agent/权限发布具备证据的能力。不能通过改一个flag一次性开放所有工具。

交付 docs/audits/download-s7-runtime-release-gates.md、环境Manifest、日志/任务与文件校验索引、运维对账runbook、READY/PREPARE_ONLY/BLOCKED按能力结论；没有生产发布授权不得部署。完成后停止。
```

---

# Prompt 7（可选）· 总控多阶段 Codex 任务（不推荐首次整批运行）

```text
请基于附件《CygnusX 统一下载与多 Agent 工具化实施方案》和 2026-10-16 审计，依次完成 S0–S7。先冻结现有脏工作树并重定位源码，务必修复实际 Worker FileRegistry task_id/source/SHA → Dataset reconcile 断点，再处理 Worker版本/协议、网络安全与硬预算、提交事务与故障恢复，最后扩展现有 Gateway Download Capability Catalog 和各 Agent 的只读/Prepare/状态工具。

严格分 Gate：S0/G0 → S1/G1 → S2/G2 → S3/G3 → S4/G4 → S5/G5 → S6/G6 → S7/Release。

关键要求：
- **先修生产登记函数，不用替身手填 task_id**；真实 Worker登记与Dataset reconcile合同测试通过。
- 保留人工下载 UI、GEO Adapter、下载 CLI、FileRegistry、DownloadService、TaskService、DatasetImportService、ToolConfirmationService；禁止新建一套下载引擎/工具网关/文件表。
- 保持真实写入安全门禁关闭，Node/LLM不能自证审批；不通过运行Gate不得 execute。
- 所有阶段报告包括具体变更、测试命令、证据、未通过项和回滚；如果任一依赖Gate失败则停止下一依赖阶段。
- 不擅自安装/启动生产服务、不访问真实私密数据、不中断已有任务、不重置已有dirty工作树、不提交/推送/部署。

建议本轮先完成 S0+S1 并等待我审阅，不要因为“总控”文字直接执行尚未授权的后续真实网络与Worker测试。
```

---

## 如何使用

**当前立即执行：**上传两份 Markdown 和调查报告，发送 **Prompt 0**。Codex 输出 S0+S1 报告后，核实真实代码路径是否修复、跨层测试是否没有手动补 `task_id`，再执行 Prompt 1。

后续 Prompt 1–5 属于代码增量开发与隔离验证；Prompt 6 是需要独立环境授权的运行验收。任何阶段都不得仅因本地 build/test 通过而宣布下载与科研分析真正可执行。

**最终检查点：下载传输引擎不重建；文件与任务真实关联；Agent 仅复用已验证且得到授权的能力。**
