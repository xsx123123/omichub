# Codex 执行提示词｜CygnusX RI09.5 正式项目综合科研报告 Phase 1–4

> **直接将本文完整内容复制给 Codex**；同时附上 `CygnusX_RI095_Project_Scientific_Report_Phase1-4_Implementation_2026-10-16.md` 和以下四份前序报告。  
> 任务目标是**在现有代码上实施并隔离验收**，不是再写一份空泛架构调查。不得把本轮新功能的代码完成夸大为真实运行验收。

## Role

你是一名维护 CygnusX BioOps 的 AI for Science 软件架构师、Python/FastAPI、Vue3、PostgreSQL/Celery、BioReport/Quarto 工程师和可复现计算研究专家。你的责任是在大量已完成的脏工作区成果基础上，**最小增量**实施正式项目综合报告，把已有科研事实与可验证科学结果组织成长期可追溯的交付产物。

## A. 必读资料与状态口径

1. **下一轮实施方案**：`CygnusX_RI095_Project_Scientific_Report_Phase1-4_Implementation_2026-10-16.md`（若附件不在仓库，先定位或在输入中读取）。
2. `cygnusx-project-delivery-runtime-acceptance.md`：RA01–RA15 的真实环境仍 BLOCKED；不要重复把 Mock 当真实 Worker。
3. `cygnusx-project-delivery-stabilization.md`：Project 鉴权重取、ready 下载时关系再核验、FileRecord 刷新、TSV 异常拒绝已存在。
4. `cygnusx-ri10-claim-provenance.md`：RI10 `deg.tsv` 数值单元格的只读 ClaimProvenance 已实现；不是通用科研发现或持久 Claim 数据库。
5. `cygnusx-project-scientific-summary-report.md`：14 章节原型、`summary-preview`、M0→Report→M1 的非循环方案。**正式 Report、PDF、Job、M1 仍为未实施**。
6. `cygnusx-project-delivery-ri06-ri09-implementation.md`、`reproducible-report-phase0/1/2-design.md`、活动架构文档；路径以仓库源码为准。

严格区分：`VERIFIED_CODE`、`PASS_ISOLATED`、`PASS_RUNTIME`、`PASS_E2E`、`BLOCKED`。任何使用 SQLite、假队列、jsdom、假执行器或临时 TSV 的成功，仅标隔离层。

## B. 先记录工作区，不覆盖并行任务

- 记录 branch/HEAD/git status/diff-stat、子仓 HEAD+dirty、相关 Feature Flags、已有 migrations/DB models、测试/类型检查范围。
- 在 `evidence/ri095-project-report-phase1-4/` 保存起点文件指纹、命令、测试、状态、阻断和结果；与现有证据目录约定一致。保护已有 Phase5、下载S3、Dataset、寻宝鼠、BioReport 其他修改。
- 禁止 `git reset --hard`、`git clean -fd`、`git stash`、`git checkout -- .`，不作全文件覆盖、无关批量格式化或隐藏修复。
- 不擅自 git commit/push、部署、运行生产迁移、真实下载、RNAFlow/DESeq2、历史复现或打开目前关闭的下载/分析/项目导出写门禁。

## C. 总体交付标准

最终实现一条在隔离环境可以验证的链：

```text
Project + 已冻结 ProjectDeliveryManifest M0
  → 用户选择可信 Claim（仅支持现有 deg.tsv 单元格场景）
  → 服务器核查并冻结 source snapshot/selection digest
  → 人类 JWT 明确创建 Project Summary Job
  → 固定输入受控渲染正式 HTML（PDF 条件具备时也渲染）
  → 实际 Report / FileRecord / SHA / 下载与版本
  → 用户明确创建新的 Manifest M1 + ProjectExportJob
  → M1 ZIP 包含真实已发布报告，离线核验
```

**必须复用**现有 ProjectDeliveryService、ReportService、FileRegistry、ReportSnapshot、ResearchClaimService、ClaimProvenance、Report/Delivery Job 可靠性模式、BioReportAdapter/Quarto、StoragePathFactory、Celery、AgentToolGateway 的只读能力。**不得新增第二套报告引擎、文件注册中心、Agent Runtime、MCP Server 或分析任务调度器**。

### 不可打破的事实边界

- `ReportModel.task_id` / `ReportGenerationJob.task_id` 当前是 Task-first 非空模型，**绝对禁止制造虚假的 Task**。先做兼容 ADR，再修改相关模型。
- 原 RI09.5 是只读 `render_project_summary_prototype` + `GET .../summary-preview`，不是正式项目科研报告。
- RI10 Claim 投影只核验由真实 `deg.tsv` 读取的有限数值；数值核验不证明机制、因果、QC、论文正确性或已完成复现。`claim_id` 不是新持久化科研结论实体。
- 旧 M0、旧 ProjectExportJob/ZIP、旧 ReportSnapshot 和 EvidenceManifest v1/v1.1 内容必须保持可读、摘要不变。
- BioReport 本地版本/源码 HEAD 不代表实际 Worker 的镜像 digest。缺正式运行验证时明确 `NOT_OBSERVED`。

## D. Step 0：快速现状检查，输出 D1 兼容决策

先检查所有实际 `ReportModel`、`ReportGenerationJob`、`ReportFile`、`ReportService`、旧 Task Report API、父子报告版本、Report Snapshot FK、Report.task_id 依赖、Report 下载/删除/项目权限、Celery Worker、`report_audit_renderer`、`BioReportAdapter`、项目 Export Job 与历史迁移。

给出两种方案和证据：

**方案 A（优先评估）**：在现有 Report/Job 中增加 `source_kind=task|project`，Task 源保留原约束，Project 源以 project_id、M0/job/digest 为主身份，增加互斥 CHECK、FK、唯一键、owner 范围和历史默认值。

**方案 B（仅当 A 迁移/Task-first 兼容性风险不可控）**：用最小 Project Report source/Job 身份适配原 ReportService、FileRegistry、渲染、存储、下载和版本语义，不复制原有引擎。

**必须生成 `docs/decisions/cygnusx-project-report-source-adr.md`，写清选型、受影响的真实调用点和隔离验证证据。** 仅在完成 ADR 后改动模型。允许生成版本化 Alembic 迁移代码并在**专用隔离测试库**验证；禁止生产迁移。若无法保证旧报表兼容，停止对应数据库变更并报告阻断，继续其他安全独立的契约/模板工作。

## E. Phase 1：正式项目报告身份和 Job

实现以下增量，不要把项目 ZIP 的 ExportJob 当项目 ReportJob：

1. 版本化 `ProjectReportSource` / `ProjectReportJob`（具体名称按现有 schema 决定），字段至少包含 owner/project、`source_manifest_job_id`、`source_manifest_digest`、`source_snapshot_digest`、格式、template/renderer/redaction/schema 版本、状态、请求键、产物身份及安全缺口。
2. 服务端从已完成、授权的**冻结 M0**确定项目和所有合法引用；**不能**根据目录、时间、项目名、Agent 文本猜测项目关系。
3. Create 由可信 JWT 人类操作触发，受现有项目模块权限和新报告准入约束。Prepare/Preview 无副作用，不暗中发起科学报告生成或项目 ZIP。
4. 使用现有持久队列模式：先提交 queued 意图再入队；投递不确定时原 Job 对账，不能盲目重发生成新 Job；Worker 互斥/超时/有限重试/中断恢复。
5. 最终 ready 必须绑定**真实 HTML（以及实际成功才有的 PDF）**、文件 SHA/size、FileRegistry/ReportFile、owner 授权、Report 版本；失败不产生伪造文件。
6. 所有 Task-first 旧接口及旧迁移/唯一键必须有兼容回归。

候选业务 API（先与当前路由核对，不强行重复建）：
- `POST /projects/{id}/scientific-summary/prepare`（只读选择/费用/缺口/digest）
- `POST /projects/{id}/scientific-summary`（JWT 确认 digest+request_key，独立 Job）
- `GET /projects/{id}/scientific-summary/{job}`（当前身份状态）
- `GET /projects/{id}/scientific-summary/{job}/preview`（只读）
- `GET /projects/{id}/scientific-summary/{job}/download?format=html|pdf`（只下载真实已登记产物）

不得悄悄将现有 `GET /projects/{id}/exports/{job}/summary-preview` 从只读变成创建操作；继续标记原型 `X-Report-Status=prototype`，不要把原型登记成科学报告。

## F. Phase 2：选定的已核验 Claim 证据冻结

基于原 RI10 `ResearchClaimService` 与 `ClaimProvenance`，实现**已明确选择、已服务端验证、绑定到 M0 的 Claim Selection**：

1. 用户只提供受限的 `task_id`、`report_id`（可选）、`file_record_id`、`feature_id/gene_id`、`column`。额外自报 `value/sha/owner/project/verified` 字段拒绝。
2. 验证用户当前 owner+project 权限、Task/Version/Report/Observation/文件关系，以及**该资源属于 M0 的选择范围**。
3. 实际读取原受管 `deg.tsv` 的合法行列；复用原 SHA、FD/O_NOFOLLOW、唯一 gene、列名、NA/有限数值、实际 Observation 校验。不能接受 LLM 自己生成的值。
4. 冻结服务端真实值、`file_sha256`、Report版本、Task、Version、Observation、已保存 ExecutionDefinition/binding 证据（仅可得的），缺失来源清晰标注。Claim selection 有独立规范化 digest 和版本。
5. Prepare 返回摘要/缺口；Create 必须再核源范围/当前字节/当前权限。不一致 409 `DRIFT`，不得自动用最新版本替换旧值。
6. 首版 `SUPPORTED_CLAIM` 仅允许由服务器组合的 `feature.column = value` 有限数值陈述；AI 文本默认不进入验证性结论区。普通项目即使没有 verified Claim，也能诚实生成项目事实报告。
7. 首选冻结到原 Project Report Job/source snapshot 的不可变数据字段；没有索引/长期保存必要，不新建独立通用 Claim 数据库。旧 ReportSnapshot 与旧 Claim 源 schema 不动。

要求测试：跨owner/跨project、Task不属于M0、旧Report版本、来源SHA漂移、重复feature、缺列、NA、非有限值、格式错误、Fake claimed verified、相同选择hash稳定、冻结结果不可静默替换、敏感字段不得出现于投影。

## G. Phase 3：正式项目 HTML/PDF + 受控发布

在已有原型的**14 章结构**基础上，优先复用 BioReport/Quarto single 布局、主题、可信 Pandoc/Typst 工具与存储/报告服务。实际实现前检查本地 BioReport CLI、模板、Worker 渲染器版本和当前代码；项目跨 Task 模板不得直接复制 RNA 统计报告模板。

- **正式模板是版本化项目模板**，输入仅 M0+冻结的 Claim/元数据/缺口、明确受权的小文件，不进行统计重新计算、跨组学聚合或额外网络检索；AI 自动生成默认禁用。
- 严禁 Agent/user 传入任意模板路径、Quarto YAML、shell、脚本、绝对路径、服务端令牌、云凭据或未授权 PDF 资源。
- 每章缺失事实显式标 `NOT_RECORDED`/`NOT_OBSERVED`/`NOT_RUN`，不得根据当前 Flow Catalog 或目录生成历史环境。
- 受控 HTML：CSP、转义、离线可读、明确“有限科研证据核验而非科学结论保证”；项目内 sandbox 预览；不用危险 iframe 权限组合。
- PDF 必须来自相同冻结源；PDF 失败只记 partial，保留有效 HTML，不创建空 PDF、不重新运行分析。没有可信 Quarto/Pandoc/Typst 时允许完成 HTML 隔离原型，但正式渲染运行 Gate BLOCKED。
- 报告独立于 Project ZIP；Report 发布成功后由用户决定是否纳入新的导出范围。
- FileRegistry、ReportFile、Report 权限、SHA、版本和原子发布必须复用；读出后再次确认当前用户、Project、文件和 SHA。

要求回归：同一旧快照生成的原执行证据 HTML 字节与改动前一致，除非另行明确版本迁移并附差异证据。

## H. Phase 4：M0→Project Report→M1 ZIP（禁止摘要环）

- 现有 M0 必须保持完全不变。正式项目报告自己的 source 仅引用 M0 digest + 冻结 Claim selection digest，不得引用包含自身的最终 M1 digest。
- 经授权确认后创建**新的** Export 选择和 M1 Manifest，引用已发布 Project Report ID、HTML/PDF 的 FileRecord ID、SHA、size，以及 M0 digest。不得原地修改旧 ExportJob。
- M1 ZIP 仅包含实际存在、经过授权和校验的文件。若 PDF 不存在必须 partial / excluded 或 missing，不能伪造 PDF。ZIP SHA 必须由包外已授权元数据提供。
- 复用现有 ProjectDeliveryService、ProjectExportJob、ZIP 校验、幂等/锁、文件预算、JWT 下载；新增字段遵守旧 ProjectManifest v1 的摘要版本兼容。需要升级 Schema 时显式 v2，不暗改 v1 摘要定义。
- 仍执行 500 文件/16 MiB 每文件/64 MiB payload/80 MiB ZIP 或当前真实配置的限制，超出明确拒绝。FTP/原始 FASTQ/BAM 不自动带入。
- 将 TaskService/DownloadService/BioReport科学分析执行入口替换成抛异常的测试钩子，仍应能完成项目 ZIP 收集；**导出不隐式触发科研计算**。

## I. 前端融合与交互

保留 `ProjectDetailView.vue` / `ProjectResearchDelivery.vue` 的现有布局，沿用 RI09.5 原型入口，添加清楚的正式报告流程：

```text
已有项目导出 M0 → 选择需要引用的 DEG 证据单元
→ 查看已验证/未验证/缺失项 → 确认生成正式项目报告
→ 查看真实持久 Job 状态 → 预览/下载 HTML 与实际 PDF
→ （可选）新建项目导出 M1 → 下载并离线核验 ZIP
```

- 原型显著标明 prototype，不与正式报告混淆；无 Claim 时不伪造“Key Findings”。
- 用户选择发生变化后旧 Prepare digest 失效；切换 Project、Report 版本、logout 时中止请求、清掉旧身份的数据；慢响应不得污染新项目。
- 真实 status，不显示假百分比；区分未启用、无权限、无记录、缺证据、partial、渲染失败、PDF 缺失。
- HTML 预览 CSP/sandbox、键盘/窄屏交互测试；jsdom 能证明的只标 isolated。若实际 Chromium 不可用则 BR 环境保持 BLOCKED。

## J. 必须运行的质量与验收

优先复用实施方案的 D01–D04、C01–C08、R01–R07、E01–E06、BR01–BR02 与现有 RA01–RA15，不把相同场景复制为无意义的新测试数量。

### 代码与隔离验收

- 真实 SQLite 模型/迁移与 API/Service/文件运行，报告从 JWT 身份重构 owner/project，当前路径/权限拒绝非法对象；不使用只有 Mock Controller 的纯 happy path。
- claim 引用必须 M0 范围限定、真实临时 TSV 文件字节和 SHA、源漂移与失败测试。
- 旧 Report/ReportGenerationJob 非空/unique、`get_by_task_id`、旧 report_kind 与 PDF/ReportSnapshot/ZIP 兼容；v1 冻结 digest 不变。
- 真实报告 HTML 文件发布、回读 SHA、FileRecord/ReportFile/状态一致；失败时不显示 ready；同 selection request_key 的并发隔离去重。
- M0、已生成 HTML/PDF、M1 新 ZIP 的摘要正确无环、scope/权限变化 fail-closed；ZIP 同 existing independent verifier 通过。
- 旧审计 HTML 相同快照字节一致；前端相关测试、typecheck/build；有界 Ruff/mypy 检查，无新增同范围诊断。全仓遗留错误如实列出，不强行清零。

### 真实运行独立门禁

实际 PostgreSQL/Celery/broker/存储/浏览器、真实项目样本、BioReport/Quarto版本与授权不存在时：标 **BLOCKED**，不要连生产/默认数据库，不启动真实 Job，不改 flag。后续必须有真实 PG migrations/约束/并发/强杀恢复，受控 HTML/PDF 真实引擎、真实JWT下载、实际Chromium 1920/768/390 及 ZIP 本地SHA 验收。

## K. 输出文件与可审阅结果

实际源码、测试、迁移（如方案需要）之外，生成：

1. `docs/decisions/cygnusx-project-report-source-adr.md`。
2. `docs/contracts/cygnusx-project-report-source-v1.md` + `.schema.json`。
3. `docs/contracts/cygnusx-project-verified-claim-selection-v1.md` + `.schema.json`。
4. `docs/implementation/cygnusx-ri095-project-scientific-report-phase1-4.md`：逐阶段 as-built，明确哪些代码真正已实施、哪些仅设计、缺什么 Gate。
5. `docs/audits/cygnusx-ri095-real-runtime-gates.md`：真实环境准入缺项、验证命令和授权前停止点。
6. `evidence/ri095-project-report-phase1-4/`：baseline、每个测试日志与退出码、JUnit、schema/checks、质量前后对照、安全反例、源码指纹（不含凭据）。

实施报告最终输出**完成/阻断矩阵**（G0、P1、P2、P3、P4、RA），禁止将设计或 isolated 报告成已发布 Project Scientific Report。特别说明模型迁移的兼容性、报告/Job/Manifest 不能原地改写、关闭新入口的回滚方案、所有旧科研记录和文件保留策略。

## L. 执行次序与自动停止点

1. 读全资料，记录 Dirty Baseline，最小现状核对；**不要重复全仓大调查**。
2. **先完成 D1 Report source ADR**。如果现有模型兼容无法保证，报告 D1 BLOCKED，**不要贸然破坏 ReportModel**；仍可以继续 Claim Selection 和模板等独立部分。
3. 实现 P1 身份+Job 的安全最小增量，运行相关隔离迁移、旧报告回归。
4. 实现 P2 冻结 Claim 选择，完成 SHA/版本/漂移/项目关联负例测试。
5. 实现 P3 正式 HTML；有可信渲染/环境再实现并验证 PDF，暂缺时 PDF 状态准确 BLOCKED，不伪造。
6. 实现 P4 新 M1/新版 ZIP，必须在真实报告文件已经落地且允许版本化交付时才声明完成；否则做可隔离的契约/测试，标 blocker。
7. 将组件融入已有项目详情，避免第二个项目管理/报告中心；运行回归、类型/构建、安全测试。
8. 输出 ADR、Schema、as-built、测试/阻断/回滚和下一轮 RI05 准入清单；**完成即停**。

**最高停止条件**：没有授权的生产/共享资源不得探测或写入；任何受信报告 Job 不能在不安全 source 模型、身份/版本混淆、未批准真实组件或涉及越权时强行推进。不能为了页面演示解除已有 write gate。不得自动上传/提交、部署或发起科研计算。

## 最终验收宣言

> 本轮是否成功，不以新增表/接口数量评判，而以**项目范围可冻结、结论数字有真实 SHA/Task/Observation 依据、报告具有真实身份和字节文件、M0/M1 不混淆且 ZIP 可独立验证**为准；任何缺失生产/真实科研证据仍如实 BLOCKED。
