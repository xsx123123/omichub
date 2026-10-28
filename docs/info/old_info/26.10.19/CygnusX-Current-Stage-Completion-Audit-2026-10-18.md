# CygnusX BioOps · 当前阶段完成度与证据审计工作单

> 版本：v1.0 ｜制定日期：2026-10-18  
> 执行对象：可访问 CygnusX/OmicHub 工作区的 Codex  
> **执行模式：AUDIT-ONLY（盘点、取证、归因、报告）；不是新一轮功能开发任务。**  
> 目标：回答“截至本次检查，**到底已经完成了哪些工作、哪些只是有代码、哪些有真实证据、距离可签收/论文案例/生产准入还差什么？**”  
> 当前文档是**审计指令与历史基线**，不是仓库现场核验结果。所有“当前状态”均由 Codex 实际检查后填写。

## 0. 交付目标（第一优先级）

本轮首先提交一份**有证据的现状清单**，而不是直接继续做新功能。覆盖两个层次：

1. **A. RI09.5 / RC04 收口状态**：已提交修复、镜像固化、门禁归零、浏览器完整 E2E、故障注入、证据一致性、外部 Gate、生产准入。
2. **B. CygnusX BioOps 平台能力全景**：数据发现/下载、Agent、受控分析、FlowFrame、BioReport、科研项目交付、跨模块贯通，以及真实科研可复现案例。

最后给出：

- **已经完成**：功能在当前代码中存在、通过明确测试或有可复核运行证据。
- **部分完成**：代码存在或部分场景通过，但关键场景、证据或集成未完成。
- **尚未开始/未找到**：有需求或文档，但仓库未见对应实现；注意不能把未搜索到直接断言为不存在。
- **无法判断/外部阻断**：权限不足、证据未提供、外部仓库不在当前工作区；准确写出缺什么。
- **下一步 5—10 项最小行动**：按依赖关系和影响优先级排序，不重新规划整个产品。

## 1. 必须先读的资料

### 1.1 本次审计的历史基线

按“最新正式结果 → 计划 → 旧报告”顺序阅读：

1. `RI095-Authorized-Runtime-Acceptance-Results.md`：Run ID `ri095-authorized-20261017-attempt1`，66 件证据；**是最近一轮有实际 Docker 运行记录的基线**。
2. `RI095-RC04-Release-Candidate-Evidence-Closure-Plan.md`：RC04-00～RC04-06 **计划与验收标准**，不是通过证明。
3. `RI095-RC04-Authorized-Agent-Execution-Prompt.md`：上一轮给授权 Agent 的执行要求。
4. `RI095-Final-Runtime-Acceptance.md`：留意 2026-10-18 顶部更新，不要把 10-17 旧 BLOCKED 当作最新结果。
5. `cygnusx-ri095-runtime-e2e-investigation-2026-10-17.md`、`cygnusx-ri095-rc01-runtime-foundation-closure.md`、`cygnusx-ri095-rc02-pdf-browser-enablement.md`。
6. `deploy/acceptance/README.md`、`evidence/runtime-acceptance/`、现有实施记录、设计文档、测试脚本与 CI。

**仓库内路径可能不同**。先定位同名文档；若找不到，写真实搜索路径和 `NOT_ACCESSIBLE/NOT_FOUND`，不能虚构文件已存在。

### 1.2 历史事实——仅作为待复核基线

以下均为**2026-10-17～18 授权 Agent 的报告主张**，不是本次审计自动通过状态：

| 主题 | 历史报告所称结果 | 本次必须核实什么 |
|---|---|---|
| Docker / Compose | 独立 disposable 环境实际运行，PG14/Redis/API/Worker/浏览器隔离 | 当前 daemon、资源隔离、实际状态；不自动启动 |
| 前端构建 | 干净 `npm ci`、`npm run build` 通过，680 文件 SHA 对应 | lockfile/源码/镜像是否与当前 HEAD 对应 |
| 数据库 | 111 revision 的空库迁移；RA02 真 PG 断言；8 并发收敛单 Job | 新旧运行差异；RA02 早期 **12 项**与后期 **11 项**对账 |
| Celery | 注册、派发、幂等和 Beat reconcile 已实测 | 精准阶段故障注入是否后来补齐 |
| HTML/PDF | 真实中文 PDF 3 页、44,369 B；DB/磁盘/HTTP SHA 一致 | 当前 renderer、工具镜像、日志、制品是否仍可核查 |
| 交付链路 | M0→Report→M1→ExportSelectionV2→ZIP，ZIP 内含 HTML/PDF | 单轮 M0 不变与**跨历史版本不变**必须分开判断 |
| 浏览器 | 真 sandbox，1920/768/390 三视口，但 **31/34** | fresh/export existing-ready 断言是否补齐；不能自动改成 34/34 |
| 缺陷 D1—D4 | tmpfs、迁移顺序、PDF cwd/TMPDIR、空 request_key 均修复并重跑 | 源码修复是否 **已提交/可复现构建**、对应测试证据 |
| 证据/安全 | 一轮 66 件证据，镜像摘要、权限与 seccomp 有记录 | 索引 SHA、证据内容、真实配置与风险审查 |
| 外部 Gate | 旧库升级、历史 M0/ZIP 基线、独立 S3 Bucket 缺失 | 本轮有无正式授权资料；不能凭空补上 |
| 生产准入 | 仍建议关闭 | 现场只读确认，不修改生产环境 |

**特别说明**：授权轮的 `RC01=PARTIAL`，RC02 故障注入范围仍为 PARTIAL；虽报告称核心 `PASS_RUNTIME/PASS_E2E` 达成，仍不可将此推导为 `RC04-Core Accepted`、`RC04-Full Accepted` 或生产可发布。

## 2. 审计执行边界

- 默认 **AUDIT-ONLY**：允许读取仓库、Git 状态、源码、迁移、脚本、历史日志、现有报告和证据索引；允许运行不会修改业务状态的静态/只读检查。
- **不得**在本轮为赶进度而修改业务代码、依赖锁文件、迁移、数据库、验收门禁、生产配置、Docker daemon/宿主安全策略、已有历史报告或原始证据。
- **不得** `git commit/push/merge/tag`、`docker compose up/down`、`alembic upgrade/stamp`、删除卷或启动故障注入；真正需要复测时提出单独的经授权工作单。
- 允许**创建新的审计报告文件**（见第 9 节）。不要修改已有验收结论去“补绿”。
- 不将隐私凭据、JWT、API key、完整 `.env` 写入审计文档；配置类只输出经脱敏的字段名称、布尔值或摘要。
- 不直接访问生产数据库或生产对象存储；受控验收环境若可以读取状态，也优先通过已有只读证据核查。
- 发现安全门禁意外开放、生产秘密可能暴露、核心状态和证据冲突时，标记 `SECURITY_HOLD`，记录最小事实并立即停止涉及风险的后续检查。

## 3. 统一判定规则：禁止“有代码 = 已完成”

每一项功能**分别记录四个维度**：

| 维度 | 需要回答 | 证据例子 |
|---|---|---|
| `Implementation` 实现 | 当前源码真实存在吗？入口在哪里？ | 文件路径、符号、接口、组件及 commit |
| `Integration` 集成 | 真实业务入口连接了吗？是否绕过了 Mock/Stub？ | route→service→Worker、事件链、配置 |
| `Verification` 验证 | 有没有对应当前源码的测试/实际运行记录？ | 测试名、Run ID、exit code、日志、trace |
| `Evidence` 证据 | 是否可复核数据来源、产物、版本、SHA、权限？ | Manifest、FileRecord、SHA、镜像 digest |

各维度状态请使用：

- `PASS_CURRENT`：当前源码/当前运行证据直接证明，证据完整。
- `PASS_HISTORICAL`：仅有较早 Run ID 的可信证据；未针对当前源码复跑。
- `PARTIAL`：实现或验证覆盖不完整。
- `IMPLEMENTED_UNVERIFIED`：代码存在，没找到有效运行证据。
- `PLANNED_ONLY`：仅方案/文档，未证实有实现。
- `FAIL`：实际执行发现明确违背断言的行为。
- `BLOCKED_ENV`：执行环境/权限阻断。
- `BLOCKED_EXTERNAL`：需要用户授权的历史旧库、corpus、S3 等外部材料。
- `NOT_FOUND`：按实际检索路径未发现，需写出检索范围；**不等于项目全局不存在**。
- `NOT_APPLICABLE`：不在本次模块范围，附理由。
- `SECURITY_HOLD`：安全前置阻断。

**单独保留运行 Gate 的原始 `PASS_STATIC / PASS_RUNTIME / PASS_E2E` 命名**，不能和审计维度中的 `PASS_CURRENT` 混为一谈。

每条结论最少必须有：`模块/能力、四维状态、实现路径、Run ID/证据路径、残留缺口、下一个动作`。没有证据写 `NOT_OBSERVED`，不能猜。

## 4. 审计工作流（按顺序）

### S0. 源码现场与审计基线（必做）

1. 记录真实仓库根目录、当前分支、`HEAD`、工作树 dirty/untracked 情况、remote（仅允许安全显示域名/仓库名）、代码/文档/证据目录位置。
2. 记录子模块/外部仓库依赖、是否可见及实际 commit；例如寻宝鼠、FlowFrame、Polariseq、BioReport 可能是**独立仓库或引入模块**，不能把它们默认为当前仓库代码。
3. 记录当前源码与 `d9c92cf6ee1c1e8de902c2b897b93f60b4f00f33` 的差异；区分 D1—D4 已提交、仅未提交、或被后续修改。
4. 按日期列出**10 月 18 日 RC04 计划之后新增的源码变更、测试和验收报告**；无法取得日期证据时标 `UNKNOWN`。
5. 扫描所有已存在的 `*acceptance*`、`*implementation*`、`*audit*`、`*test*`、CI 配置，标识最近一轮实际执行 Run ID。

建议只读命令（按仓库实际情况执行，勿打印 secrets）：

```bash
git rev-parse --show-toplevel
git branch --show-current
git rev-parse HEAD
git status --short
git log -12 --date=iso --pretty=format:'%h %ad %s'
git diff --stat
git ls-files --others --exclude-standard | head -100
find docs deploy evidence -maxdepth 5 -type f \( -iname '*rc04*' -o -iname '*acceptance*' -o -iname '*audit*' \) 2>/dev/null | sort
```

### S1. 事实与设计文档对账

- 扫描 README、架构 ADR、实施记录和最近一次真实验收报告，建立“**需求/承诺 → 代码入口 → 测试入口 → 证据 → 当前结论**”追踪链。
- **优先以当前源码和同版本的实际证据判断**；文档写“完成”但找不到对应入口/证据时标 `CLAIM_UNVERIFIED`，并解释为何不足。
- 同一需求如果在多份报告中结论不一致，按 Run ID、commit、运行环境和证据时间整理成时间线，不静默覆盖旧结论。
- 区分示例数据、synthetic fixtures、真实生产数据、获批准的脱敏历史 corpus；不得把示例数据包装成科研复现成功。

### S2. RC04-00～06 专项完成度（最高优先级）

逐行查源码、文档和证据；若找不到 RC04 新 Run ID，当前状态写**“计划已制定，现场执行未证实”**：

| ID | 检查项 | 通过要求 | 不可混淆的风险 |
|---|---|---|---|
| RC04-00 | 验收门禁收口 | 私有持久化 `READS/WRITES/PDF=false` 且有效进程状态有现场证据；容器停止与卷保留 | 授权轮报告曾记录 flag 仍为 true；**旧 stop 日志不算现在状态** |
| RC04-01a | D1–D4 修复固化 | 当前源码有修复、相关 diff 清晰、必要测试通过 | 未提交 worktree ≠ RC frozen |
| RC04-01b | 确定性构建 | clean source、lock SHA、toolchain、frontend/dist、image full digest 对应 | 历史 dirty-build 不算新 RC |
| RC04-02a | 浏览器 34 项对账 | 34 条具名断言及 31/34 差项、旧→新映射 | API 30×200 ≠ UI 34/34 |
| RC04-02b | fresh export | 三视口 UI 真正从 fresh 状态创建、ready、ZIP SHA 下载 | 不能先用 API 种 ready 再冒充 fresh |
| RC04-02c | existing-ready | 同来源幂等创建同 Job，按钮/下载可用，不重复发布 | 不应等待必现的中间 status DOM |
| RC04-03 | FI01–FI06 故障注入 | validating/rendering/publishing、发布后 DB commit 前、重复投递/撤权真实失败和恢复证据 | 仅有 hook 代码不能算 FI 通过；生产不得可激活注入器 |
| RC04-04a | 数据交付与权限复核 | HTML/PDF/ZIP 三处 SHA、JWT、跨 owner、撤权、FileRegistry | 本轮新证据不能借用上轮 SHA 冒充 |
| RC04-04b | seccomp 安全审查 | 默认 profile vs 定制差分、容器作用域、cap_drop ALL、授权、风险意见 | sandbox 启动 ≠ seccomp 变更已审计 |
| RC04-04c | 证据索引复核 | 索引逐文件 SHA+大小+Run ID+脱敏+结论语义抽样 | 摘要一致 ≠ 断言真实通过 |
| RC04-05a | 旧库升级 | 批准脱敏旧库、schema/version/data、升级前后记录 | 空库迁移不得代替 |
| RC04-05b | 历史 M0/ZIP | 已冻结可信 corpus，多轮字节不变性 | 单次 M0 不变 ≠ 跨历史版本不变 |
| RC04-05c | S3 | 授权独立 Bucket/前缀/凭据、真实上传回读/撤权 | 本地 FileRegistry PASS ≠ S3 PASS |
| RC04-05d | 存储异常 | 漂移/丢失/symlink/配额等隔离 fixture 和真实结果 | 测试 fixture 不等于科研 corpus |
| RC04-05e | RA04–06 精确定义 | 找到原始 Gate 定义并建立逐项映射 | 不自行编造定义 |
| RC04-06 | 分级验收 | `RC04-Core`、`RC04-Full`、`Production-Ready` 独立判定 | Core Accepted ≠ Production-Ready |

**复核必答：** RA02 历史 12 条、本轮 11 条的差集是什么？是哪一条被删、合并、或遗漏？是否有等效新测试证据？

### S3. 平台功能全景盘点（代码与集成）

> 下表是**审计范围**，不是宣称这些能力已经实现。先定位真正属于当前仓库的模块；对于独立仓库只登记依赖指向与可访问性。每个条目都按“四维状态”填写。

| 领域 | 必查能力与关键问题 | 实现/证据线索（需验证） |
|---|---|---|
| P01 平台基础 | FastAPI、前端、PostgreSQL、Redis、Celery、MinIO/本地存储、配置隔离、鉴权 RBAC | 应用入口、router、models/migrations、compose、运行日志 |
| P02 项目上下文 | Project、Owner、Claim、Task、Case、Artifact、Evidence、Manifest、FileRegistry 身份和状态关联 | ORM schema、service、API、UI、权限测试 |
| P03 Agent 框架 | Agent 目录/注册表、编排、ReAct/LangGraph、工具选择、上下文、超时/幂等、人工确认、受控执行 | `agent*`、runtime、tool registry、审批状态与测试 |
| P04 科研寻宝鼠 | 自然语言 GEO/SRA 数据发现、文献/数据证据、Grounding、DatasetCard、Next Shovel、SSE、项目上下文/历史 | 内嵌模块/外部仓库引用、BFF API、前端入口、集成测试 |
| P05 下载中心 | GEO/ENA/SRA/SRR/直链、Polariseq 协同、下载预案、授权/白名单/校验/重试/幂等/资产登记 | download API、workers、capabilities、S1–S5/R1–R4 证据 |
| P06 FlowFrame | 版本化流程、参数 schema、专家审核/版本冻结、FlowAgent、输入校验、流程追溯 | 具体包、git pin、审批记录、流程定义、集成适配 |
| P07 标准分析中心 | RNAFlow/ATACFlow/DNAFlow 等安装与真实执行、Docker/Snakemake/Slurm、作业管理、恢复、资源隔离 | executor、workflow registry、任务日志、输出 artifact |
| P08 高级分析 | AI 生成灵活 Python/R、专家审核、执行限制、产物记录、方法学解释和证据链 | sandbox/approval/hitl、代码与日志，不推断运行成功 |
| P09 BioReport | 科学 Quarto 报告、HTML/PDF、数据库持久化、Interpretation Agent、报告工作台与服务适配 | 分清 BioReport 外部科学报告与项目 summary PDF renderer |
| P10 科研项目交付 | M0/Report/M1/ExportSelectionV2/ZIP、JWT/owner、SHA、不变性、rollback | RI09.5 权威报告与当前 service/tests |
| P11 前端集成体验 | 登录、科研发现→下载→分析→报告、项目恢复、导航、响应式、错误恢复 | routes、components、Playwright E2E、真实页面 |
| P12 数据治理 | 数据源/授权、checksum、血缘/manifest、私有/对象存储、quota、保留/删除、敏感信息 | metadata、storage backend、audit logs、风险审查 |
| P13 部署交付 | compose、镜像、环境隔离、版本 pin、CI、Secrets、监控、告警、备份与恢复 | Dockerfiles、CI、运维手册、运行验收 |
| P14 科研复现案例 | 获授权真实 RNA-seq 数据→下载→FlowFrame 执行→BioReport→证据回放，结果及环境复现 | 至少一个真实任务样本与可重算证据；**不能用 RI09.5 项目摘要 PDF 替代** |
| P15 对外交付/开源 | README、Licenses、部署文档、API 文档、演示数据、版本发布、BP/论文声明匹配 | 当前 docs、tag、release、开源仓库权限 |

**输出要求：** 为每个领域选至少一个真实可运行的“纵向切片”（UI 或 API → domain service → worker/tool → artifact/DB → report/manifest），列出第一个断点在哪里。不要把模块计数、Agent 数量、流程数直接当作通过度。

### S4. 端到端纵向切片（必须区分三条）

**Slice A — RI09.5 项目交付（历史已有较强证据）：**

`Project/Claim → Scientific Summary Job → HTML + PDF → FileRegistry → M1 → ExportSelectionV2 → ZIP → JWT Download → Browser`。

审计路径与最近 Run ID，一并列出 `evidence_status=partial` 的具体未关闭事项。

**Slice B — 真实科研分析（论文/平台愿景最关键）：**

`研究问题/数据发现 → 数据集筛选与 provenance → 获取/校验 → 项目资产 → FlowFrame 审核版本 → 受控执行 → 多组学结果 → BioReport 科学报告 → Evidence/Manifest → 可重算交付`。

要找出**有真实数据和可信任务 Run ID 的最长连续通过片段**。若只完成前端或某个 API、没有真的分析任务，不得写“End-to-End Complete”。

**Slice C — Agent 发起受控流程：**

`用户自然语言需求 → Agent 研究/规划 → 工具能力预检 → 专家审核 → 版本锁定 → 队列/执行 → 证据注册 → 交付/解释`。

必须区分：Agent 生成代码、Agent 自动调用工具、专家批准后真实执行三种完全不同的能力和 Gate。

**对三条切片分别记录**：入口、最后实际通过节点、首个缺口、依赖条件、源文件、测试证据、是否能在独立环境复跑。

### S5. 测试覆盖、质量与风险

- 罗列当前 repo 可发现的单元/契约/集成/运行 E2E/浏览器/故障注入测试套件，注明实际最近运行日期与 commit。没有运行记录不能记通过。
- 审核 CI/CD 哪些检查真正会阻止回归（代码 lint、迁移拓扑、npm ci、前端 build、API/DB 契约、artifact 校验、浏览器 smoke/业务 E2E）。
- 识别 TODO、FIXME、stub/mock、临时断言、占位报告表、功能 flag、hardcoded demo、权限绕过与关键技术债，**仅列能够定位文件的项**。
- 专项核对：D1–D4 回归、RA02 12/11、`31/34`、FI01–FI06、seccomp diff、`evidence_status=partial`、历史数据库/S3/corpus 外部 Gate。
- 发现已存在 `SECURITY_HOLD` 或新 P0 风险，必须置顶，不得用总完成率掩盖。

## 5. 完成度计算口径（可选，但必须可复核）

不要凭感觉输出“平台完成 90%”。若报告完成率，采用**预先列明的分母**：

1. **RC04 关键 Gate 完成数**：`通过 Gate 数 / 有明确验收契约的必需 Gate 总数`；外部依赖另列，不从总体静默排除。
2. **平台能力实现覆盖**：`当前仓库可证实已实现的能力数 / 当前审计列明的能力数`，不计外部不可见仓库为通过。
3. **集成/真实运行覆盖**：独立统计有完整纵向集成路径与真实 Run ID 的能力数。
4. **科研复现完成度**：必须按真实科学案例证据链列项，不用工程代码数量折算。

允许不报百分比；优先用 `Verified / Partial / Unverified / Blocked` 计数和原始明细。

## 6. 输出中的“里程碑地图”

至少给出三层结论，避免一个“完成”覆盖不同范围：

| 层级 | 何时可称完成 | 审计应输出 |
|---|---|---|
| M1. `RC04-Core Accepted` | 固定源码/镜像、门禁归零、完整 E2E、故障恢复、证据核验和关键安全审查通过 | `ACCEPTED / PARTIAL / FAIL / BLOCKED` + Gate 证据 |
| M2. `RC04-Full Accepted` | M1 + 历史旧库升级、历史制品不变、S3 和全部约定 Gate 通过 | `ACCEPTED / BLOCKED_EXTERNAL / PARTIAL` |
| M3. `Reproducible Scientific Workflow Demonstrated` | 有至少一个真实科研流程从真实数据到可复现结果的完整证据 | 案例 ID、流程版本、输入/环境/参数/结果、独立复现记录 |
| M4. `Production-Ready` | 完整验收 + 独立安全、备份恢复、运维、数据治理、发布审批 | 仅给 readiness 建议，不自行开生产 Gate |

要明确：M1 与 M2 是 **RI09.5 项目交付运行时**的工程验收，M3 才进一步支撑 CygnusX 的 AI for Science 框架愿景。

## 7. 风险与下一步排序规则

对每项未完成内容记录：

- `Severity`：P0/P1/P2（P0=安全/证据失真/核心门禁/阻断核心链路）。
- `Type`：代码缺陷、测试缺口、环境阻断、外部授权、设计未定、证据缺失、待集成。
- `Dependency`：谁/什么前置材料必须先到位。
- `Action`：**最小可执行任务**（文件或接口范围 + 验收测试 + 输出证据）。
- `Owner`：可建议角色，但不知道责任人时写 `UNASSIGNED`，不要编造姓名。
- `Can Agent Do Now`：YES/NO/AFTER_AUTHORIZATION。

最终推荐 **不超过 10 项**下一步任务，分成：

- `Now`：可在当前授权内立即做、无需新产品功能。
- `Needs Input`：需批准旧库、历史 corpus、S3、原 Gate 文本等。
- `Next Milestone`：完成 RC04 后以真实 RNAFlow/FlowFrame 案例贯通科研复现。

## 8. 严格审计规则与停止条件

1. 无法找到必要资料时**说明检索范围和缺失证据**，不要生成假路径。
2. 先读代码、后推断状态；引用准确文件路径、符号及尽可能精确的行范围。
3. 旧报告里的 PASS 只标 `PASS_HISTORICAL`，除非能关联到当前源码的运行证据。
4. 业务运行日志、Playwright trace、产物 SHA、Git commit 和镜像 digest 必须互相对应；无法对应就写 `UNLINKED`。
5. 未授权的外部仓库不主动 clone，不假定 FlowFrame/BioReport/Polariseq 仓库已经被集成。
6. **审计不能顺带修改和修复问题**。将具体修复整理成下一轮 Codex 工作单。
7. 不得进行生产操作，不得输出密钥，不得自行将 production flags 改成 true。
8. 任何“已完成”结论必须附至少一条**可定位、可复核的证据链**；仅 README 主张不够。

## 9. 必须生成的交付物（仅新增文档）

建议放在当前仓库 `docs/audits/`；若已有固定 docs conventions，沿用实际目录：

1. **`CygnusX-Current-Stage-Completion-Report.md`**：执行摘要、代码/集成/验证全景、里程碑判断、风险与下一步。要求先给“一页速览”，再给证据。
2. **`CygnusX-Feature-Evidence-Matrix.csv`**：按下表字段做逐能力审计，至少涵盖 P01–P15 和 RC04 全项。
3. **`RI095-RC04-Completion-Gate-Matrix.md`**：RC04-00～06 的逐 Gate 证据与状态、RA02 12/11 差集、E2E 31/34、FI01–06。
4. **`CygnusX-Next-Action-Backlog.md`**：不超过 10 项，含优先级、阻断、最小验收测试、是否可由 Codex 立即执行。

CSV 建议字段：

```csv
area_id,capability,implementation_status,integration_status,verification_status,evidence_status,current_gate,code_path,test_path,run_id,evidence_path,commit_or_digest,gap,next_action,owner_or_input
```

审计报告**必须先回答**以下 12 个问题：

1. 当前 HEAD、工作树状态、最近一次完整运行 Run ID 分别是什么？
2. RC04 有无新实施/运行报告？是实际执行还是仅有计划？
3. D1–D4 是否都固化进可复现源码？
4. `READS/WRITES/PDF` 持久化门禁是否真实关闭，并确认运行进程有效状态？
5. 浏览器 `31/34` 到底补齐了没有？fresh/existing-ready 三视口各自结果是什么？
6. RA02 的 12/11 项差异是否查清？
7. FI01–FI06 是否有真实的精准注入与恢复证据？
8. 当前核心 HTML/PDF/ZIP、JWT、FileRegistry/Manifest 是否有同版本真实证据？
9. seccomp 调整经何种审查，是否仍有权限扩大风险？
10. 旧库升级、历史 M0/ZIP、S3/存储异常的授权与证据状况是什么？
11. 科研寻宝鼠→数据资产→FlowFrame→分析执行→BioReport→Evidence 的**最长连续真实通过片段**到哪里？
12. 当前可以接受 `RC04-Core`、`RC04-Full`、`Production-Ready`、`Scientific Workflow Demonstrated` 中的哪一项，分别为什么？

### 最终报告建议摘要格式

```markdown
# 当前完成度总览（截至实际检查日期）

- Repo/HEAD/dirty：...
- 最近真实 Run ID：...
- RC04-Core：ACCEPTED / PARTIAL / ... （证据）
- RC04-Full：ACCEPTED / BLOCKED_EXTERNAL / ... （证据）
- Production-Ready：NOT_APPROVED / ... （证据）
- 科研工作流真实复现：VERIFIED / PARTIAL / NOT_OBSERVED （证据）

## 目前明确完成的能力（逐项引用证据）
...
## 仅有实现、尚无运行证据的能力
...
## 有真实运行证据但未完全闭环的能力
...
## 仍需外部授权/材料的 Gate
...
## RC04 的实际最新状态及与授权轮的差异
...
## 下阶段不超过 10 项最小任务
...
## 结论可信度和缺失信息
...
```

## 10. Codex 退出条件

**只有在生成上述 4 个实际审计文件、给出每条关键结论的源码/测试/证据路径、说明无法访问的范围，并明确区分“计划/代码/运行/完整 E2E/科研复现”后，才可以声明本轮盘点完成。**

审计完成后停止，不继续自行开发 RC04 或其他功能。等待负责人选择下一批任务。
