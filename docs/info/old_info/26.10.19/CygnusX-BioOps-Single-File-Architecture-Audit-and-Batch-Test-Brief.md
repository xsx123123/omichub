# CygnusX BioOps 单文件架构审计与批量测试工作说明

版本：1.0｜编制日期：2026-10-18（Asia/Shanghai）  
用途：将本文件完整交给持有 CygnusX BioOps 仓库访问权限的 Codex 执行。  
工作范围：Architecture Discovery、Architecture Documentation、Architecture Validation、Test Strategy Design、Batch Test Planning。

> 本文件是工作指令，不是已经完成的仓库审计或测试结果。下述历史状态来自 2026-10-18 已有审计材料，必须在目标仓库重新核实。不得把本文件的编制视为 RC04 验收、测试执行或生产发布授权。

## 0. 给执行 Codex 的总指令

你是一名软件架构、Agent/MCP、受控执行、生物信息学工作流和自动化测试工程师。请基于真实源码、配置、数据契约与原始运行证据，完成本文件规定的五项工作，将调查、架构事实、验证结果、测试策略与批量执行计划全部汇入 `ARCHITECTURE_DESIGN` 下的**同一个 Markdown 主文件**。

首轮默认模式为 `READ_ONLY_DISCOVERY_AND_TEST_PLANNING`：允许读取仓库和已获授权的本地证据，允许更新指定主文件及写入本轮 evidence；“只读”指对业务源码、服务、数据库和安全配置只读。测试执行须通过本文准入规则，不因本工作说明而自动获得运行环境、外部服务或计算资源授权。

必须遵守：

1. Source Code First：源码与实际调用链优先于 README、设计稿和既往总结；源码也不能单独证明运行成功。
2. Evidence Driven：每个实现、集成、运行或 E2E 结论均有相应证据；摘要不替代原始断言。
3. Current Source Validation：历史 PASS 不等于当前 PASS；不同工作树、镜像或子模块版本的结果不得无条件继承。
4. Minimal Changes：本轮不修复业务代码、不大规模重构、不增加产品功能。修复建议写入同一主文件，待后续修复任务执行。
5. Fail Closed：目标环境、权限、费用或影响不明确时，不运行依赖该条件的测试；继续不受影响的调查。
6. Scientific Integrity：项目摘要报告生成成功，不等于真实 RNA-seq 分析、科学报告或独立复现通过。
7. Single Main File：所有人可读说明集中在一个主文件；测试原始日志和机器可读记录存 evidence。

## 1. 文件落点与单文件维护规则

先定位真正的仓库根与 `ARCHITECTURE_DESIGN/`，不要把当前聊天工作区误当平台仓库。找不到目标仓库或目录时，报告缺少的路径，不自行创建一个虚假的平台架构目录。

选择主文件的顺序：

- 若已有承担总体架构说明的主文件，复用该文件，并在开头记录其完整仓库相对路径。
- 若没有合适主文件，在确认目标仓库后创建 `ARCHITECTURE_DESIGN/ARCHITECTURE_DISCOVERY_REPORT.md`。
- 一旦选定，后续轮次均更新同一路径，不另建带日期、版本号或“final”后缀的平行报告。

保留其他既有文档和 ADR；不删除、不批量改写、不新增 README、TESTING 说明、模块独立报告或第二份总结。把旧文档清单、状态与主文件章节映射放进主文件。保留有价值的原设计，在对应章节区分“原设计”“当前事实”“差异”，不要无证据覆盖设计决策。

允许的本轮输出结构：

```text
ARCHITECTURE_DESIGN/
└── <唯一主文件>.md                      # 五部分及全部人可读结论

evidence/architecture-audit/<run-id>/    # 优先复用仓库既有 evidence 约定
├── baseline/                           # Git、源码清单、配置摘要
├── discovery/                          # 搜索、契约、调用关系原始记录
├── tests/<test-id>/<attempt-id>/        # 命令、日志、断言、截图、制品
├── test-catalog.json                    # 可选，机器可读测试目录
├── results.jsonl                        # 实际执行记录
├── artifact-index.json                 # 原始证据索引
└── checksums.sha256
```

以上 evidence 文件按实际需要产生；未运行测试不制造运行日志。不得在 evidence 中藏入多套架构说明来规避单文件要求。新增测试脚本或修改既有执行器不在首轮范围内，可在主文件嵌入经核实的调用示例和后续实施建议。

## 2. 已有审计基线：仅供核对，不可直接沿用

先读取仓库中的以下材料，路径以实际搜索为准，缺失则记录，不编造内容：

- `CygnusX-Current-Stage-Completion-Report.md`
- `CygnusX-Feature-Evidence-Matrix.csv`
- `RI095-RC04-Completion-Gate-Matrix.md`
- `CygnusX-Next-Action-Backlog.md`
- `RI095-Authorized-Runtime-Acceptance-Results.md`
- `RI095-RC04-Release-Candidate-Evidence-Closure-Plan.md`
- 相关原始 Gate、RA/FI 定义、运行清单与 evidence。

2026-10-18 审计记录如下。它们是待重新核对的历史事实，不代表执行时现场：

| 项目 | 已有记录 | 本轮核查要求 |
|---|---|---|
| 仓库 | `/home/zj/zj_code_libarary/OmicHub`，分支 `main` | 路径仅为历史定位线索，以现场为准 |
| 审计时 HEAD | `d648f54d24affd2bd3787332a49a5f4c96494cef` | 重新读取 HEAD、工作树及子模块；历史记录有 22 条状态变更 |
| 最近完整 RI09.5 授权运行 | `ri095-authorized-20261017-attempt1` | 原始目录为 `evidence/runtime-acceptance/ri095-authorized-20261017-attempt1/` |
| 该运行源码基线 | `d9c92cf6ee1c1e8de902c2b897b93f60b4f00f33`，含未提交修复 | commit 本身不足以重现脏工作树；核对 source manifest、差异、子模块、镜像 digest |
| 后续 IAT/G3 | `iat-r3-20261018`、`g3-e2-20261018` | 隔离回归/源码及宿主预检不提升为当前全栈验收 |
| RC04 新运行 | 当时未发现新 Run ID | 搜索是否后来新增，不把计划文件算作执行证据 |
| RC04-Core | `PARTIAL / NOT ACCEPTED` | 当前源码、运行、安全和证据闭环尚未具备 |
| RC04-Full | `BLOCKED_EXTERNAL` | 旧库、历史制品、S3、异常 fixture 和 Gate 原文缺失 |
| 真实科研闭环 | `NOT_OBSERVED / BLOCKED` | 没有审定真实数据贯穿发现、下载、计算、报告及独立重放的案例 |
| Production-Ready | `NOT_APPROVED` | 是独立决策，不从 Core、Full 或 PDF 成功推导 |

必须专项核实以下缺口：

- **门禁**：历史 rollback flags 仍为 `ACCEPTANCE_READS=true`、`ACCEPTANCE_WRITES=true`、`ACCEPTANCE_PDF=true`；容器 `Exited (0)` 不等于持久门禁关闭。首轮读取实际配置和已授权的进程状态，记录差异；不自行改门禁。后续授权测试应核查关闭状态、有限开启范围与收尾恢复。
- **D1–D4**：历史报告涉及 tmpfs 标量、迁移依赖顺序、PDF `cwd/TMPDIR`、空 `request_key` UUID 兜底。原报告 D 编号映射须逐项核对，不依据历史摘要重排编号；未提交修复与当前镜像绑定尚未证明。
- **RA02**：早期 12 项，后期 11 项；遗漏 `RA02_12 legal update`，期望 SQLSTATE `00000`。`RA02_11 dup source` 不能替代合法更新正向断言。恢复计划须保留稳定 ID 并对账全部 12 项。
- **浏览器**：历史为 31/34；须对账 34 条具名断言，分别验证 fresh export 与 existing-ready，在 1920、768、390 三视口保留结果。API ready 不替代 UI ready；不能靠删断言或加等待掩盖竞态。
- **FI01–FI06**：没有精确阶段注入及恢复真实证据。目标涉及 validating、rendering、publishing、发布后 DB commit 前窗口、重复投递、撤权；具体 FI ID 映射以原始契约为准，找不到定义则阻断映射，不自行编号。
- **交付**：历史 HTML/PDF、FileRegistry、M0/M1、ExportSelectionV2、ZIP 校验器、JWT、跨 owner 拒绝和单轮 M0 字节不变已有限定范围的真实运行证据；当前源码未复跑，历史跨版本不变性未证明。
- **安全与索引**：seccomp 默认/自定义 profile 差分、实际容器作用域、capabilities、当前镜像关联仍需独立复核。历史索引声明 66 项、目录共 69 个文件，先解释计数口径，再逐项查 hash、大小、来源和断言语义。
- **外部条件**：批准脱敏旧库及 Alembic 版本、冻结历史 M0/ZIP corpus、独立测试 S3 Bucket/前缀与专用权限、存储异常可信 fixture、RA04–RA06 原文仍待补齐。不得用合成数据冒充历史基线。

## 3. 第一部分：Architecture Discovery（架构调查）

### 3.1 固定可追溯现场

读取适用的仓库工作指引。记录时间和时区、仓库根、分支、完整 HEAD、dirty 状态、受跟踪差异与未跟踪源码清单、递归子模块 SHA/dirty 状态、锁文件摘要及现有部署配置路径。不 reset、clean、checkout 覆盖用户改动，不提交、不拉取子模块或依赖。

可先使用已确认存在的只读入口，例如 `git rev-parse HEAD`、`git status --short`、`git diff --stat`、`git submodule status --recursive` 和定向源码搜索。运行进程、镜像、数据库与对象存储信息仅通过已授权只读接口查看；不打印环境变量全集、令牌或完整连接串。

源码基线应包含实际工作树内容身份。若有脏改动，记录差异和相关文件 SHA；不能只写 HEAD。无法重建快照时明确标记 `UNFROZEN`，不得宣称候选发布源码已冻结。

### 3.2 盘点文档、入口与依赖

在主文件记录现有文档的 `CURRENT / PARTIALLY_CURRENT / OUTDATED / PROPOSED / UNKNOWN` 状态及依据。搜索真实服务入口、路由、模型、迁移、队列任务、适配器、策略、前端页面、测试和 CI。

核实 FastAPI、Vue3、PostgreSQL、pgvector、Redis、Celery、MinIO/S3、Docker、Snakemake、Slurm 等是否存在、接线、启用或运行。它们是调查候选，不是已确认技术栈。FlowFrame、RNAFlow、ATACFlow、Treasure-Seeking_Mouse、BioReport、Polariseq 及其他流程均按实际模块存在性记录。

区分源码依赖、运行依赖和数据/契约依赖，追踪调用方、被调用方、对象标识、权限传播与失败处理。找不到实现时记录搜索范围和断点，不由目录名称推断功能。

## 4. 第二部分：Architecture Documentation（单文件架构记录）

### 4.1 模块记录统一格式

每个模块在同一主文件内记录：设计目标；实际实现；真实源码路径与符号/行号及基线；入口和调用链；输入输出、必填字段与错误语义；数据模型和状态机；同步/异步依赖；身份、权限、预算和隔离边界；重试/取消/幂等/恢复；测试入口；原始证据与 Run ID；设计差异、未验证事项及下一步。

采用可检索事实 ID（如 `ARC-001`），将事实关联到源码、测试 ID 和 evidence。关键接口表至少列出生产者、消费者、契约位置、版本、授权上下文、输入/输出摘要与错误处理。

### 4.2 必须覆盖的整体框架

| 范围 | 必须回答的问题 |
|---|---|
| 平台与运行时 | 服务入口、前后端边界、PG/Redis/队列/Worker/存储职责；部署拓扑；实际配置与当前运行状态；调度与资源隔离 |
| Agent / MCP | Registry、Runtime、编排、工具发现、Tool Gateway、MCP、上下文/记忆和状态持久化；只读与写工具划分；工具授权；HITL；失败恢复；新增工具和 Agent 的治理及膨胀风险 |
| Trusted Execution | Plan → Expert Review → Approval → Version Lock → Admission → Budget Binding → Execution → Evidence 是否逐跳实现；审批是否绑定版本/输入/参数；执行前重验；旁路；重复扣费；撤权与在途任务 |
| 科研寻宝鼠 | 问题 → GEO/SRA/ENA/文献发现 → Grounding → DatasetCard → Project Asset；UI/BFF/Gateway/持久化是否接线；来源、许可和数据对象契约 |
| 下载中心 | Download Plan、审批、Admission、Polariseq/HTTP Supervisor、Worker、取消恢复、重复下载、大小/超时/配额、checksum 和资产登记；特别核查 HTTP Supervisor 生命周期断点 |
| FlowFrame / RNAFlow | 流程资产、专家审核、版本冻结、参数映射、输入校验、Snakemake/Docker/Slurm 调度与产物登记；workflow/input/parameter/container/output digest 之间的关联；其他流程仅按事实调查 |
| BioReport | RNAFlow 科学结果适配、结构化元数据、Quarto/HTML/PDF、记录持久化、科学解读证据与再生成；明确区分科学 BioReport 和 RI09.5 项目摘要/交付报告 |
| Evidence / 项目交付 | Case/Artifact/Evidence/Manifest/FileRegistry、ReportJob/ExportJob、StorageBackend、ExportSelectionV2、JWT；M0 → Report → M1 → ZIP → Verification 的来源、选择集、摘要、owner 隔离和历史不变性 |
| RI09.5 RC04 | RC04-00–06、RA02、34 项 UI、FI01–06、D1–D4、安全与索引复核、Full 外部 Gate；每项映射到原始验收契约 |

### 4.3 图与纵向切片

Mermaid 图直接嵌入主文件，不另存图文说明。至少表达系统/部署边界、模块依赖、Agent 受控执行时序、数据与 Evidence 生命周期。每条重要连线可追溯到代码或契约；在图例中区分已实现、仅设计、未验证/阻断。图中不得把未观测链路画成已运行通过。

必须单列三条切片，逐节点列出源码、契约、状态、最近可用证据和第一个断点：

1. **项目交付**：M0 → 项目摘要 HTML/PDF → FileRegistry → M1/V2 ZIP → JWT → 独立校验。
2. **真实科研**：Research Question → 寻宝鼠 → DatasetCard → 受控下载/校验 → FlowFrame 审核冻结 → RNAFlow 执行 → 科学结果 → BioReport → Evidence/Manifest → 独立重放。
3. **Agent 控制**：任务 → 编排/工具选择 → 专家批准 → Admission/预算 → Gateway/MCP/队列/Worker → 证据登记与恢复。

## 5. 第三部分：Architecture Validation（架构核验）

对模块边界、循环依赖、重复实现、共享状态、配置漂移、API/对象版本、跨 owner 隔离、权限旁路、审批失效、幂等与并发、状态机、异常恢复、可观测性和追溯连续性做基于证据的检查。

特别核查 Agent Runtime 与计算 Runtime 的边界，FlowFrame 审核规范与 RNAFlow 执行职责，平台调度、BioReport 报告、Evidence 审计是否重叠或断开；Dataset/Asset/FileRecord/Artifact 是否混用。

每个发现记录：`Finding ID / 影响范围 / 源码与证据 / 可观察触发条件 / 预期与实际 / 严重度 / 置信度 / 修复建议 / 回归测试 ID / 阻断依赖`。没有运行证据时标为静态风险或待验证，不写成已发生故障。不得只列通用最佳实践。

### 5.1 状态与证据判定

每项能力分别记录实现状态、集成状态、验证层级、版本匹配和阻断原因，避免一个 PASS 混淆所有维度。

| 维度/状态 | 判定边界 |
|---|---|
| `DESIGNED / IMPLEMENTED / INTEGRATED` | 分别需要设计依据、源码依据、真实接线依据；不自动证明运行成功 |
| `PASS_STATIC` | 仅静态检查满足明确断言 |
| `PASS_ISOLATED` | 隔离环境通过，明确 mock/fixture 与替代依赖 |
| `PASS_RUNTIME` | 指定真实运行环境中的具名断言通过 |
| `PASS_E2E` | 指定起终点真实链路通过，注明是否包含 UI、真实计算和外部服务 |
| `PASS_HISTORICAL` | 只对原运行版本和环境成立；保留原始验证层级 |
| `PARTIAL / FAIL / NOT_TESTED / NOT_OBSERVED` | 分别表示部分满足、实际断言失败、未执行、调查范围未发现证据 |
| `BLOCKED / BLOCKED_EXTERNAL` | 写清具体缺失条件、影响测试与解除条件 |

只有相关源码、工作树、子模块、构建/镜像、环境和测试断言匹配，才可在验证结果上标注 `CURRENT`。无法判定匹配时标 `UNKNOWN` 或 `MISMATCH`。子断言成功不自动提升父 Gate；计划、hook、API mock、SQLite 测试或文件数量不能替代 PG/Worker/UI/阶段故障的指定真实验收。

Core、Full、真实科研复现、Production-Ready 分开判定。验收定义缺失时记录未知，不擅自缩减范围后宣布 Accepted。

## 6. 第四部分：Test Strategy Design（分层测试策略）

### 6.1 发现真实测试入口

先检查 Makefile、pyproject/pytest、package.json scripts、Playwright、Compose、验收目录、CI 与现有执行器，读取其副作用、fixture、数据库目标和自动启动行为。只列出核实存在的命令及工作目录。未核实命令标 `UNVERIFIED_COMMAND`，不得放进可直接执行批次。

测试矩阵全部写入主文件；可将同内容的机器可读目录存 evidence，不另建测试说明文件。

| 层级 | 范围 | 主要前提及证据 |
|---|---|---|
| T01 Static | 导入/类型/配置/契约/依赖检查 | 防止安装与构建隐式副作用；保留检查输出 |
| T02 Unit | 纯函数、组件、状态逻辑 | 隔离 fixture、无真实写资源；记录 mock 边界 |
| T03 Contract | API、DatasetCard、审批、Manifest、工具契约 | 字段/版本/错误/owner 上下文断言 |
| T04 Integration | PG/Redis/Broker/Worker/存储适配 | 独立测试实例与 namespace；不能用 SQLite 替代 PG 约束 |
| T05 Runtime | 真实服务、队列、报告/导出任务 | 源码与镜像绑定；Job 状态和后台证据 |
| T06 Browser E2E | 登录、项目、预览、fresh/existing-ready、下载 | 三视口、34 项对账、截图/trace/console/network |
| T07 Scientific Workflow | 小型公开或获授权 RNA-seq 真实计算 | 数据来源、样本/设计、参考与版本、预算、科学验收 |
| T08 Fault Injection | FI01–06 与恢复、撤权和重复投递 | 精确注入点、一次性环境、恢复和副作用断言 |
| T09 Provenance | Manifest/Registry/ZIP/JWT/owner/历史不变性 | DB/磁盘/HTTP 摘要对账与独立验证 |
| T10 Reproducibility | 干净环境重建、科学重放、历史兼容 | 冻结输入/软件/参数；区分字节一致和数值容差 |

### 6.2 每个测试必填字段

`Test ID、能力/事实 ID、层级、源码/测试路径、具名断言、命令与 cwd、依赖、环境标识、fixture 与输入摘要、预期输出、证据要求、权限与副作用、CPU/内存/磁盘/网络/费用、超时、并发组、重试规则、清理/恢复、当前状态、Run ID、阻断项`。

时长/费用无实测时只给估算区间、假设和不确定性。注明命令退出码与业务断言是否同时成功；零退出码不自动等于 PASS。

### 6.3 关键验收设计

- RA02：12 个稳定 ID 逐项期望/实际 SQLSTATE，显式包含合法更新；用例间隔离、事务与清理可核验。
- UI：fresh 必须从无对应导出 Job 的明确状态由 UI 创建；existing-ready 单独准备已有 ready Job，证明复用、不重复发布、按钮与下载可用。比较 ZIP SHA、Job/文件数量与幂等键，保留三视口结果。
- FI：读取原始 ID 定义后建立“注入点 → 故障可见性 → 持久状态 → 重试/对账 → 最终恢复 → 无重复/幽灵文件 → 历史制品不变”证据链。普通 kill 或普通失败不自动满足阶段注入。
- Trusted Execution：参数/流程/输入变化导致审批失效；未批、过期、撤权、预算不足和旁路均有拒绝断言；执行前复查、重复请求预算和在途撤权语义依契约核实。
- 科学分析：固定 accession、样本分组、输入摘要、参考基因组/注释、workflow/容器/软件版本与参数；核对 QC、比对/定量、DEG/富集等实际流程支持的结果。不得虚构科学阈值；先依据方法和基准约定容差，再执行独立重放。合成 fixture 不替代真实案例。
- 交付与安全：验证选择集、报告来源、JWT 过期/跨 owner、索引 hash/大小及语义、seccomp 差分与实际运行约束。安全检查不得通过关闭 sandbox 或放宽生产配置取得 PASS。

## 7. 第五部分：Batch Test Planning（批量测试计划与流程）

### 7.1 准入模式

| 模式 | 允许行为 | 必要条件 |
|---|---|---|
| A 首轮调查/计划（默认） | 只读取证、主文件更新、evidence 存档、生成执行预览 | 正确仓库与可读范围；不启动测试服务、不执行迁移/下载/计算 |
| B 已授权隔离测试 | 已审查的本地静态/单元/契约测试 | 现有授权覆盖；确认无生产访问、外部付费、隐式安装/服务启动；输出仅落允许测试目录 |
| C 已授权真实运行 | PG/Redis/Worker、UI、PDF、下载、科学计算、FI、S3/旧库测试 | 明确目标环境、权限、预算、隔离/恢复/清理责任和临时门禁范围；现有授权可复用，缺什么只补什么 |

生成清单或 dry-run 不等于执行；dry-run 入口也需先审查副作用。首轮完成 A 后，若现有授权已满足 B/C，可继续对应测试；否则将可审阅的准确批次、资源和待授权项写入主文件，等待缺失条件，不以时间经过当作授权。

涉及生产数据库迁移、生产门禁变更、生产凭据、全局安全策略、删除共享数据或发布的动作不在本工作说明授权范围。不要为调查读取生产秘密。获授权测试仅对专用可丢弃资源操作，不停止或清理归属不明的服务。

### 7.2 批量执行顺序

1. **B00 基线与预检**：确认源码内容身份、原始 Gate、实际测试入口、隔离项目名/端口/卷/数据库/队列/Bucket 前缀，核实当前门禁和进程。预检不通过则阻断依赖批次。
2. **B01 快速隔离批次**：T01–T03，筛查接口、状态与测试自身问题；只在准入后执行。
3. **B02 集成批次**：T04 与必要 T05，先数据库迁移/约束、权限、队列与存储接线，再报告/导出。RA02 必须完整对账。
4. **B03 RC04 正常链**：当前基线构建/镜像一致性核验、HTML/PDF、Manifest/Registry/ZIP/JWT，再 T06 的 fresh 与 existing-ready；RC04 构建动作也需纳入资源及网络授权。
5. **B04 RC04 异常与证据**：FI01–06、恢复/幂等/撤权，T09、安全与索引复核；Full 外部测试分成独立依赖批次，不影响无关调查。
6. **B05 真实 RNA-seq 纵向案例**：以稳定工程基线和已满足的科学执行前提为准，先做小规模先导，再跑完整真实切片及 T10 独立重放。Core 未满足时可继续设计，不把科研运行扩张混入 Core 修复。
7. **B06 收尾与结论**：核查任务结束、临时门禁恢复、资源清理、残留队列/卷/制品归属和证据完整性，回写同一主文件。

每批次列出准确 Test ID、前置批次、命令与 cwd、环境、资源上限、允许并发、时限、证据路径、停止条件和清理方式。未获授权的批次停留在计划状态。

### 7.3 并行、重试与停止

- 仅无共享写状态的测试可并行；共享 DB/schema、队列、Job 幂等键、Bucket 前缀或固定端口时串行或使用明确隔离空间。并发上限来自实际资源预算。
- 超时、队列积压、预算/磁盘达到上限即停止相关批次。发现误连生产、跨 owner 泄露、审批旁路、不可逆破坏、沙箱失效或制品被意外修改时，停止所有共享该风险的测试，保存现场并按已授权恢复方案处理。
- 缺外部条件时标 BLOCKED，不伪造 fixture 冒充旧库或历史制品；普通单项失败可继续不依赖它的安全批次。
- 自动重试仅针对明确可恢复的瞬时故障，保留首次失败和每次尝试。断言失败不靠反复运行“刷绿”；重跑通过仍记录 flaky 或恢复原因。
- 本轮不修改业务代码；若后续授权修复导致源码变化，建立新基线和新运行关联，重跑受影响用例及约定发布 Gate，不混合版本拼装一个“全部通过”。

## 8. 原始证据与运行记录规范

每轮使用不覆盖旧目录的 Run ID，例如 `arch-audit-YYYYMMDDTHHMMSS+0800-<source-id>`。执行前保存基线，执行后检查源码漂移。已生成旧证据只读保留；脱敏副本标记派生关系，不覆盖原件。

每个测试记录以下结构（示例为模板，非结果）：

```json
{
  "run_id": "<实际运行标识>",
  "test_id": "<稳定测试ID>",
  "attempt_id": "<本次尝试>",
  "source": {"commit": "<完整SHA>", "dirty": true, "snapshot_digest": "<工作树摘要>", "submodules": {}},
  "environment_id": "<专用环境>",
  "image_digests": [],
  "command": "<经脱敏的实际命令>",
  "cwd": "<仓库内工作目录>",
  "started_at": "<带时区时间>",
  "ended_at": "<带时区时间>",
  "exit_code": null,
  "assertions": [],
  "status": "NOT_TESTED",
  "validation_level": null,
  "baseline_match": "UNKNOWN",
  "evidence_paths": [],
  "blocker": null,
  "cleanup_status": "NOT_STARTED"
}
```

`artifact-index.json` 至少列出相对路径、字节数、SHA-256、Run/Test/Attempt ID、产生步骤、证据用途与脱敏状态。证据包括必要的 stdout/stderr、逐项断言、服务/Worker 日志、DB 查询结果、HTTP 状态与内容摘要、截图/trace、输入/参数/环境清单及清理验证。

不保存可复用密码、令牌、JWT 完整值、预签名 URL 或敏感个人数据。用不可复用标识及脱敏字段建立关联。主文件链接 evidence 相对路径，并明确“hash 一致”与“业务断言成立”是两种检查。

## 9. 同一 Markdown 主文件的最终章节要求

最终主文件必须同时包含以下内容，可复用已有章节顺序，但不得拆成多个文档：

1. 摘要、范围、模式、限制、审计时间和唯一主文件路径。
2. 当前源码/子模块/构建/运行基线及历史基线对照。
3. 既有架构文档清单、状态和章节映射。
4. 系统整体架构、部署图、模块/契约/依赖矩阵。
5. Agent/MCP、Trusted Execution、寻宝鼠、下载、FlowFrame/RNAFlow、BioReport、Evidence 的逐模块事实。
6. 三条纵向切片、最长真实连续链及首个断点。
7. 架构核验发现、风险、证据与建议。
8. RI09.5 RC04 Gate 对账，含原始定义来源、当前/历史状态与解除条件。
9. 分层测试策略、完整测试矩阵和具体命令。
10. 批量执行顺序、准入、并发/资源、停止/恢复与清理操作。
11. 实际运行结果与原始 evidence 索引；未执行明确标记，不用计划代替结果。
12. 外部阻断项、待补输入与下一轮优先事项。
13. 更新记录：日期、Run ID、源码基线、结论变化及对应证据。

优先级默认：P0 当前基线/门禁事实、RC04-Core 缺口与证据；P1 首个真实 RNA-seq 科研闭环；Full 外部条件单列管理。不要因平台模块多而继续横向增加功能。

## 10. 完成检查与最终回复

完成前检查：

- 是否只新增或更新了一个架构 Markdown 主文件；其他既有文档是否保留？
- 五部分是否全部在主文件中，图、矩阵、Runbook 是否可直接使用？
- 所有源码路径、测试命令、契约与证据链接是否存在；缺失项是否如实标记？
- 是否完整保留历史 PASS 的版本/层级限制，没有继承成当前 PASS？
- RA02 12/11、浏览器 31/34、fresh/existing-ready、FI01–06、门禁、安全及索引差异是否逐项对账？
- 是否区分了科学 BioReport 与项目摘要，以及 Core、Full、真实科研复现、生产就绪？
- 是否明确列出当前能执行、尚需授权、缺环境/数据、缺原始定义的批次？
- 实际执行是否全部有原始证据与清理状态，失败和未执行是否保留？

最后在聊天中只给简洁交付摘要：唯一主文件路径、evidence 根目录、已执行/未执行范围、当前四类验收结论、最关键阻断项和下一批可执行工作。不要再创建额外总结报告。

**没有读取仓库就不声称已调查；没有运行就不声称已测试；没有当前匹配证据就不声称当前通过；没有完整 Gate 就不声称 Accepted。**
