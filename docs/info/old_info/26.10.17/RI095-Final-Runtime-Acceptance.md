# CygnusX BioOps · RI09.5 Authorized Runtime Closure & Full E2E Acceptance

**任务类型：** 真实运行验收、缺陷修复、端到端验证  
**目标：** 完成 RI09.5 尚未通过的 RC01、RC02 及项目交付链路验收  
**执行模式：** 在正式授权的隔离环境中实际执行，不以静态调查代替运行测试  
**最终交付：** `RI095-Authorized-Runtime-Acceptance-Results.md`

---

# 一、任务背景与当前状态

你是一名具备正式授权运行权限的高级 DevOps 工程师、数据库迁移审计工程师、后端架构师和 E2E 测试工程师。

请基于 CygnusX BioOps 当前源码和既有验收证据，完成尚未通过的真实运行验收。

首先阅读以下材料：

1. `RI095-Final-Runtime-Acceptance.md`
2. `cygnusx-ri095-runtime-e2e-investigation-2026-10-17.md`
3. `cygnusx-ri095-rc01-runtime-foundation-closure.md`
4. `cygnusx-ri095-rc02-pdf-browser-enablement.md`
5. `RI095-Runtime-E2E-Acceptance-Plan.md`
6. `RI095-Runtime-Validation-Agent-Prompt.md`
7. `deploy/acceptance/README.md`
8. `evidence/runtime-acceptance/artifact-index.json`

如果仓库中的文件路径与上述名称不一致，先根据实际仓库结构定位，不得假设文件不存在。

## 1.1 当前已知基线

最近一次最终验收记录：

- Run ID：`ri095-final-20261017-attempt1`
- 分支：`feat/research-agent-phase5`
- Git commit：`d9c92cf6ee1c1e8de902c2b897b93f60b4f00f33`
- 工作树包含既有未提交修改。
- Docker socket 探测返回 `operation not permitted`。
- 前端干净安装未完成：离线安装出现 `ENOTCACHED`，联网安装出现 DNS/registry 访问错误。
- 本轮未生成新的真实 PDF。
- 本轮未完成浏览器业务 E2E。
- 镜像 digest 在最终报告中为 `NOT_OBSERVED`。
- 旧数据库升级、已批准的任务 corpus、对象存储和完整 M0/M1/ZIP 验收仍存在前置条件。

此前的真实运行调查曾经完成部分 PostgreSQL、Celery、HTML、JWT、私有本地存储和 ZIP 验证，并发现过真实迁移缺陷。

**上述历史证据可以复用作为参考，但不能直接继承为本轮通过结果。**

## 1.2 本轮核心目标

完成以下工作：

1. 解决或明确当前执行环境的实际阻断。
2. 固化已有修复并验证源码状态。
3. 完成前端干净安装和真实构建。
4. 完成真实 PostgreSQL、Redis、FastAPI、Celery 运行验证。
5. 完成 HTML/PDF 报告生成与完整性验证。
6. 完成 FileRegistry、私有存储和 JWT 权限验证。
7. 完成 M0 → Report → M1 → ExportSelectionV2 → ZIP 交付验证。
8. 完成 Chromium 正常沙箱下的 Playwright 业务 E2E。
9. 补齐阶段级故障恢复与历史制品不变性验证。
10. 生成完整、可审计的最终验收报告。

不得仅输出新的调查文档或静态检查清单。

---

# 二、执行模式与安全约束

## 2.1 正式授权环境

在 Agent 实际执行命令的同一环境中确认：

- 当前操作系统与运行身份。
- Docker daemon 目标。
- Docker socket 访问能力。
- Compose 版本。
- 网络与依赖下载能力。
- 独立验收数据库、Redis 和存储是否可用。
- Chromium 沙箱运行条件。

在确认目标为经过批准的隔离环境后，可以直接执行非破坏性的验证、镜像构建、测试容器启动、数据库迁移、报告生成和 Playwright 测试。

对于已经明确授权的独立 disposable 资源，不必对每条常规测试命令重复请求确认。

涉及删除数据、修改共享资源、破坏性故障注入或变更安全策略的操作，必须先核实作用范围与授权。

## 2.2 禁止事项

严禁：

- 访问或修改生产数据库。
- 读取或使用生产凭据、生产 JWT 或生产 `.env`。
- 将生产数据库配置继承到验收环境。
- 绕过 Docker socket 权限。
- 使用 `--no-sandbox` 绕过 Chromium 安全机制。
- 修改生产宿主的 AppArmor、seccomp 或其他安全策略以取得测试通过。
- 未经批准使用客户数据或对象存储。
- 使用虚构的科研执行结果冒充真实任务。
- 删除或覆盖历史 Manifest、ZIP、审计日志及已有验收证据。
- 使用 `docker compose down -v`、`docker volume prune` 或其他方式清除验收审计数据。
- 使用 `alembic stamp`、`downgrade`、数据库重置或重复创建表等手段掩盖迁移问题。
- 将静态检查、探针或历史运行结果冒充本轮真实运行通过。

## 2.3 执行环境受阻时

如果 Docker 仍然返回 `operation not permitted`：

1. 保存完整命令、退出码和错误日志。
2. 确认当前 Agent 是否运行在受限沙箱中。
3. 明确记录 Docker daemon 与权限探测结果。
4. 不得通过提权、切换未批准的 daemon 或修改宿主策略绕过阻断。
5. 继续执行与 Docker 无关且具备条件的前端锁文件审计、源码检查和离线构建准备。
6. 将必须依赖容器的 Gate 标记为 `BLOCKED`。
7. 输出需要管理员或环境负责人完成的最小授权操作。

如果依赖网络不可用，保留 DNS、registry、npm 和构建日志。不得将联网失败直接认定为源码缺陷，也不得把离线 dry-run 认定为完整安装成功。

---

# 三、阶段 RC00：环境准入与源码基线

这是本轮第一项必做任务。

## 3.1 环境检查清单

- [ ] 记录当前操作系统、内核、UID、GID、用户组。
- [ ] 记录 Docker context 和目标 daemon。
- [ ] 执行 `docker info`。
- [ ] 执行 `docker compose version`。
- [ ] 验证独立容器能够启动、执行简单命令并正常停止。
- [ ] 验证当前环境可以访问获准的 npm registry 或受控依赖镜像。
- [ ] 检查 PostgreSQL、Redis、私有卷和测试身份的实际可用性。
- [ ] 检查 Chromium、Playwright 和浏览器依赖版本。
- [ ] 确认不存在生产数据挂载或生产凭据继承。
- [ ] 记录所有检查结果与退出码。

Docker 准入测试必须在隔离资源中完成，不得仅根据宿主机其他终端的结果判断 Agent 已具备权限。

## 3.2 源码与工作树审计

检查：

- [ ] 当前分支与 Git commit。
- [ ] `git status`。
- [ ] 未提交修改。
- [ ] 未跟踪文件。
- [ ] 当前 migration 文件。
- [ ] `deploy/acceptance/` 下的验收实现。
- [ ] 前端依赖锁文件。
- [ ] 当前运行镜像及其真实 digest。

重点关注以下已有修复：

- `alembic/versions/c1d2e3f4b5a6_add_contract_digest_to_mcp_versions.py`
- `deploy/acceptance/compose.yml`
- `deploy/acceptance/control.py`
- `deploy/acceptance/runtime.py`
- `deploy/acceptance/checks.py`
- `deploy/acceptance/audit_migrations.py`
- `frontend/package-lock.json`

要求：

1. 区分既有修改与本轮新增修改。
2. 为修改前的工作树建立可恢复的快照或差异文件。
3. 保留无关的未提交修改。
4. 只对必要缺陷进行最小修复。
5. 未经授权，不得整体提交工作树。
6. 构建时必须记录真实源码状态；不能用 Git commit 代替未提交差异的记录。

**阶段验收：** 生成环境准入报告和源码基线报告。若 Docker 不可用，明确阻断范围，但继续执行可以独立完成的检查。

---

# 四、阶段 RC01：运行基础与数据库迁移

## 4.1 Alembic 迁移 DAG

重点核查：

- [ ] revision 总数与当前仓库一致。
- [ ] base 唯一。
- [ ] head 唯一。
- [ ] 所有 branch、mergepoint 和 down_revision 关系正确。
- [ ] `h6i7j8k9l1m3` 创建 `mcp_versions`。
- [ ] `c1d2e3f4b5a6` 对 `mcp_versions` 的 ALTER 依赖 CREATE。
- [ ] 不存在循环依赖或重复迁移步骤。
- [ ] 离线迁移规划与实际执行顺序一致。

不能仅凭静态 DAG 正确就判定数据库迁移通过。

## 4.2 全新数据库升级

使用独立 disposable PostgreSQL。

- [ ] 记录 PostgreSQL 版本。
- [ ] 创建独立空数据库。
- [ ] 执行 `alembic upgrade head`。
- [ ] 保存完整迁移日志。
- [ ] 检查 `alembic current`。
- [ ] 检查实际表、索引、约束和触发器。
- [ ] 检查关键表的列定义与预期 schema。
- [ ] 检查 `mcp_versions` 已正确创建并添加目标字段。
- [ ] 检查迁移无重复执行、无遗留失败事务。
- [ ] 保存迁移前后状态及最终只读数据库快照。

此前空库迁移曾经通过，但本轮必须重新验证当前源码和镜像。

## 4.3 已有数据库升级兼容性

必须使用经过批准的脱敏历史数据库副本，包含可信的：

- schema 基线。
- `alembic_version`。
- 必要的历史数据。
- 报告及交付制品基线。
- 预期升级结果。

检查：

- [ ] 从历史版本执行升级。
- [ ] 检查历史表和数据是否保留。
- [ ] 检查约束、索引和触发器。
- [ ] 检查历史报告身份及关联。
- [ ] 检查 Manifest 和 ZIP 的原始字节不变。
- [ ] 保存升级前后 schema、版本、数据摘要和制品摘要。

如果缺少可信历史基线，必须标记：

`BLOCKED — LEGACY DATABASE BASELINE MISSING`

不得使用空库升级成功代替历史数据库兼容性验收。

## 4.4 Compose 与运行隔离

检查：

- [ ] 三处 `/tmp` tmpfs 使用正确的单一标量。
- [ ] 容器 UID/GID 符合预期。
- [ ] 容器仅连接独立 internal 网络。
- [ ] 不存在未经批准的宿主端口发布。
- [ ] 不存在 Docker socket 挂载。
- [ ] 不存在外部数据库地址继承。
- [ ] 不存在生产凭据继承。
- [ ] 私有存储使用专用命名卷。
- [ ] 验收配置默认关闭不必要的读写门禁。
- [ ] 八项既有错误配置拒绝回归继续通过。

实际启动后验证容器内 UID/GID、临时目录和私有存储目录的写入、fsync、回读与权限边界。

静态拒绝回归与真实容器权限测试分别记录。

---

# 五、阶段 RC01：前端确定性构建

实际前端 Dockerfile：

`deploy/docker/Dockerfile.frontend`

不得假设仓库存在 `frontend/Dockerfile`。

## 5.1 依赖安装

首先检查：

- [ ] `frontend/package.json`。
- [ ] `frontend/package-lock.json`。
- [ ] Node 与 npm 版本。
- [ ] registry 配置。
- [ ] DNS 解析。
- [ ] 依赖缓存。
- [ ] Sass optional dependency 锁树。
- [ ] 原始 `npm ci` 错误。

在干净临时目录或独立构建容器中执行真实：

`npm ci`

此前已观察到 `zrender@5.6.1` 的离线缓存缺失，以及 `registry.npmmirror.com` 的 DNS 访问失败。

本轮必须区分：

- 依赖锁文件错误。
- DNS/网络错误。
- registry 不可用。
- 缓存缺失。
- 实际代码构建错误。

不要通过不断修改 lockfile 掩盖网络故障。

如果依赖源不可用，保存真实失败证据，并在获得授权的受控依赖环境中继续。

## 5.2 前端构建

在 `npm ci` 完整通过后执行：

`npm run build`

检查：

- [ ] 安装命令退出码为 0。
- [ ] 构建命令退出码为 0。
- [ ] 构建不存在未处理错误。
- [ ] dist 为本轮当前源码生成。
- [ ] 记录 Node/npm 版本。
- [ ] 记录 package-lock SHA-256。
- [ ] 记录 dist 文件清单和逐文件 SHA-256。
- [ ] 记录 Docker 镜像 digest。
- [ ] 验证实际部署镜像中的前端文件与本轮构建产物一致。

禁止使用来源不明的旧 `dist` 替代当前源码构建。

**阶段验收：** 只有真实 `npm ci` 与 `npm run build` 成功，才允许将前端构建标记为 `PASS_RUNTIME`。

---

# 六、阶段 RC01：PostgreSQL、API 与 Celery

## 6.1 数据库约束 RA02

使用真实 PostgreSQL，而不是 SQLite 或 jsdom。

至少重新执行此前的 12 项断言：

- [ ] `report_files` XOR 双 NULL，预期 SQLSTATE `23514`。
- [ ] `report_files` XOR 双非空，预期 `23514`。
- [ ] 外键指向不存在的 `file_record`，预期 `23503`。
- [ ] XOR 恰好一项，预期合法。
- [ ] 修改冻结的 export manifest，预期 `P0001`。
- [ ] 修改冻结的 report identity，预期 `P0001`。
- [ ] `status=ready` 但缺少 HTML 字段，预期 `23514`。
- [ ] export 状态越出枚举，预期 `23514`。
- [ ] report 状态越出枚举，预期 `23514`。
- [ ] `attempt_count < 0`，预期 `23514`。
- [ ] 重复 `(user, project, source_digest)`，预期 `23505`。
- [ ] 合法更新成功。

逐项保存实际 SQL、实际 SQLSTATE、预期结果和数据库版本。

## 6.2 并发与幂等 RA03

使用真实 FastAPI、JWT 和 PostgreSQL。

- [ ] 8 个并发请求提交同一来源 Manifest。
- [ ] 请求具有不同 `request_key`。
- [ ] 验证 Job ID 收敛行为。
- [ ] 验证唯一约束与幂等逻辑。
- [ ] 验证 `attempt_count`。
- [ ] 验证不存在重复发布。
- [ ] 验证 advisory lock 获取、释放和重入。
- [ ] 验证项目停用或删除后的保留语义。
- [ ] 验证不同来源版本的行为。

需要已批准的历史任务 corpus 才能验证的场景，缺少前置数据时单独标记 `BLOCKED`。

## 6.3 Celery RA04–RA06

先阅读仓库中真实的任务注册、调度器和执行入口。

不得自行编造原始 RA04、RA05、RA06 的定义。

- [ ] 确认 Redis Broker 与 Backend 的独立配置。
- [ ] 确认队列为 `ri095_acceptance`。
- [ ] 检查 Worker 任务注册表。
- [ ] 检查 Beat 调度任务。
- [ ] 执行真实 `send_task` 到 Worker 的派发往返。
- [ ] 记录 task ID、received、started、finished。
- [ ] 验证写门禁关闭时 fail-closed。
- [ ] 验证重复投递的幂等性。
- [ ] 验证 reconcile 对陈旧任务的恢复。
- [ ] 验证任务重试与错误状态。
- [ ] 验证 advisory lock 释放。
- [ ] 实施 validating、rendering、publishing 阶段的可控故障注入。
- [ ] 验证发布成功、状态提交失败等边界情况。

故障注入必须使用经过审查的测试专用机制，不得随机杀进程代替精确故障场景。

如果阶段级故障注入器不存在，优先在隔离测试层实现最小、可复核的注入机制，并确保不会进入生产执行路径。

如果原始 Gate 定义缺失，明确记录定义缺口，不得自行重新分配编号。

---

# 七、阶段 RC02：HTML 与 PDF 真实运行

## 7.1 确认实际调用链

当前已知项目科学报告 PDF 路径：

`BioReportAdapter → report_audit_pdf_renderer → Pandoc → Typst`

此路径将冻结的 HTML 转换为 PDF，不重新执行科研分析。

不要无依据地增加 Quarto 或 LaTeX 作为必需依赖。

## 7.2 Worker 镜像

在受控 Worker 镜像中安装并固定实际需要的：

- Pandoc。
- Typst。
- Droid Sans Fallback 或经验证的中文字体。
- 字体检查工具。
- 其他 renderer 实际依赖。

记录：

- [ ] 源码 commit 与工作树差异。
- [ ] Worker 镜像 digest。
- [ ] Pandoc 版本。
- [ ] Typst 版本。
- [ ] 字体列表及字体文件摘要。
- [ ] 模板版本。
- [ ] renderer 版本。
- [ ] 镜像构建日志。

不得使用宿主机的工具版本冒充 Worker 内版本。

## 7.3 HTML 生成

- [ ] 通过真实业务入口创建报告 Job。
- [ ] Worker 实际消费任务。
- [ ] 生成真实 HTML。
- [ ] 检查报告内容与 provenance 标签。
- [ ] 检查数据库 FileRecord。
- [ ] 检查磁盘文件。
- [ ] 记录 HTML SHA-256。
- [ ] 通过真实 HTTP/JWT 下载。
- [ ] 比较数据库、磁盘和下载三处 SHA-256。

## 7.4 PDF 生成

- [ ] 使用已冻结 HTML 真实生成 PDF。
- [ ] 验证 PDF 可解析。
- [ ] 检查中文字体。
- [ ] 检查分页与文本溢出。
- [ ] 检查 PDF 页面数与内容。
- [ ] 记录 PDF SHA-256。
- [ ] 检查 FileRecord、磁盘和 JWT 下载摘要一致。
- [ ] 验证失败时 HTML 仍保留。
- [ ] 验证 PDF 失败不会错误标记为成功。
- [ ] 验证失败后的 Job 状态和重试恢复。

HTML 成功不能替代 PDF 成功。

如果 PDF 渲染器失败，保留原始错误和失败产物；修复后重跑相同场景，并保留两轮证据。

---

# 八、阶段 RC02：Chromium 与 Playwright 浏览器环境

历史问题是 Chromium 报告：

`No usable sandbox`

涉及宿主 AppArmor 与非特权 user namespace 限制。

本轮必须在支持正常 Chromium sandbox 的隔离 Runner 上执行。

## 8.1 浏览器准入

- [ ] 核实 Runner 的授权与隔离属性。
- [ ] 核实 AppArmor/user namespace 条件。
- [ ] 核实 seccomp 与 Chromium sandbox。
- [ ] 核实 Playwright npm 包版本。
- [ ] 核实 Chromium 浏览器版本。
- [ ] 完成真实浏览器启动。
- [ ] 保留启动日志。

禁止使用 `--no-sandbox`。

如果没有合规 Runner，记录准确阻断条件，不得伪造浏览器通过结果。

## 8.2 完整业务 Playwright E2E

必须运行真正的业务测试，而不只是首页启动探针。

依次验证：

- [ ] 用户登录。
- [ ] 项目列表。
- [ ] ProjectDetail 页面。
- [ ] Claim 操作。
- [ ] 创建科学报告 Job。
- [ ] Job 状态更新。
- [ ] HTML 报告展示。
- [ ] PDF 生成与下载。
- [ ] Manifest 更新。
- [ ] ExportSelectionV2。
- [ ] ZIP 导出。
- [ ] ZIP 验证。
- [ ] JWT 下载权限。
- [ ] 撤权后再次下载应被拒绝。
- [ ] 页面刷新后的状态恢复。
- [ ] 离页后重新进入。
- [ ] 失败重试。
- [ ] 键盘操作。
- [ ] 窄屏布局与交互。

至少验证三个视口：

- Desktop：1920px。
- Tablet：768px。
- Mobile：390px。

保存：

- Playwright trace。
- 截图。
- Console 日志。
- 网络请求日志。
- HTTP 状态。
- 下载文件与 SHA-256。
- 测试用例及退出码。
- 失败场景的复现步骤。

首页探针通过不代表业务 E2E 通过。

---

# 九、阶段 RC03：FileRegistry、JWT 与存储

## 9.1 私有本地存储

- [ ] 真实文件原子发布。
- [ ] 文件回读。
- [ ] FileRecord 与 ReportFile 关联。
- [ ] owner 归属。
- [ ] 磁盘、数据库与下载摘要一致。
- [ ] 权限校验。
- [ ] 生命周期管理。
- [ ] 配额边界。
- [ ] 文件丢失检测。
- [ ] 文件漂移检测。
- [ ] 符号链接安全。
- [ ] 撤权后的访问拒绝。
- [ ] 失败恢复。
- [ ] 保留历史制品。

存储漂移、丢失和旧文件不可变性测试必须使用可信基线，不得虚构预期 SHA。

## 9.2 JWT 与权限隔离

使用独立测试身份。

- [ ] 真实注册与登录。
- [ ] JWT 访问 `/auth/me`。
- [ ] JWT 创建 API key。
- [ ] API key 访问 JWT 专用路径应被拒绝。
- [ ] 无认证访问应被拒绝。
- [ ] 跨 owner 读取项目应被拒绝。
- [ ] 跨 owner 下载报告应被拒绝。
- [ ] 用户列表不泄露其他用户资源。
- [ ] 停用用户后旧 JWT 不再有效。
- [ ] 撤权后重新下载应被拒绝。
- [ ] 错误响应不泄露文件内容或敏感信息。

状态码以仓库实际认证契约为准，不得假设所有拒绝都必须返回 403。

## 9.3 对象存储

与本地存储分开验收。

必须先获得授权的独立测试 Bucket、凭据和专用前缀。

- [ ] 配置独立 S3 backend。
- [ ] 上传。
- [ ] 回读。
- [ ] SHA-256 校验。
- [ ] 权限隔离。
- [ ] 失败重试。
- [ ] 删除与生命周期边界。
- [ ] 撤权。
- [ ] 存储对象漂移与丢失验证。

没有授权 Bucket 时，将对象存储 Gate 标记为 `BLOCKED`，不能使用本地存储结果替代。

---

# 十、阶段 RC03：M0 → Report → M1 → V2 → ZIP 完整交付链路

这是本轮最重要的业务验收之一。

必须使用经过批准的真实完成任务 corpus，包含必要的历史 Manifest、任务状态和可信文件摘要。

不得伪造科研执行结果或自行制造可信历史基线。

## 10.1 输入与前置条件

- [ ] 确认 corpus 来源。
- [ ] 确认 owner 与访问授权。
- [ ] 确认任务状态为已完成。
- [ ] 确认原始 Manifest M0。
- [ ] 确认历史 ZIP 基线。
- [ ] 确认 HTML/PDF 与原任务的真实关联。
- [ ] 保存所有输入文件 SHA-256。

缺少历史基线时，保留不依赖该基线的其他测试，但将历史制品不变性验证标记为 `BLOCKED`。

## 10.2 端到端执行

执行以下真实链路：

`Completed Scientific Task → Source Manifest M0 → Report Job → HTML/PDF Artifact → Updated Manifest M1 → ExportSelectionV2 → Project Delivery ZIP → Verification → JWT Download`

逐项检查：

- [ ] M0 内容与原始字节不变。
- [ ] Report Job 与来源任务关联正确。
- [ ] HTML/PDF 与 FileRecord 关联正确。
- [ ] M1 引用正确的来源和报告。
- [ ] 版本变化有明确证据。
- [ ] ExportSelectionV2 显式选择来源 Manifest 与报告。
- [ ] ZIP 成员符合选择范围。
- [ ] ZIP 内包含预期的报告文件。
- [ ] ZIP 内 Manifest 与实际成员一致。
- [ ] 校验文件正确。
- [ ] 仓库提供的 ZIP 验证器实际通过。
- [ ] ZIP SHA 与数据库及下载文件一致。
- [ ] JWT 下载成功。
- [ ] 跨 owner 下载失败。
- [ ] 历史 ZIP 的原始字节不变。
- [ ] 多次导出不会修改冻结的历史制品。

特别检查：此前默认 `ExportSelection` 生成的 evidence ZIP 不包含项目科学报告。

不能把默认导出模式通过当成 `ExportSelectionV2` 完整通过。

必须使用真实 `ExportSelectionV2` 入口验证 HTML/PDF 与 Manifest 的关联。

---

# 十一、阶段 RC03：故障恢复与可靠性

使用专门的隔离测试资源和经过审查的故障注入机制。

不得对生产服务进行故障注入。

检查：

- [ ] Job 重复投递。
- [ ] Worker 任务失败。
- [ ] Worker 在受控阶段中断。
- [ ] validating 阶段故障。
- [ ] rendering 阶段故障。
- [ ] publishing 阶段故障。
- [ ] 发布成功但状态提交失败。
- [ ] Beat reconcile。
- [ ] 孤立文件检测。
- [ ] 存储文件丢失。
- [ ] 存储内容漂移。
- [ ] 数据库与存储状态不一致。
- [ ] 权限撤销后的重试。
- [ ] ZIP 验证失败。
- [ ] PDF 失败但 HTML 保留。
- [ ] 恢复后不会重复发布。
- [ ] `attempt_count` 与实际执行次数一致。
- [ ] 冻结的旧 Manifest/ZIP 未发生变化。

每种场景必须记录：

1. 注入前状态。
2. 注入动作。
3. 实际错误。
4. 数据库状态。
5. 文件状态。
6. 恢复动作。
7. 恢复后的状态。
8. SHA-256 与证据路径。

不得用随机 `kill` 代替阶段级可复核故障注入。

如果测试执行器缺少必要场景，应实现最小、测试专用、不会进入生产路径的注入机制，并单独审查该实现。

---

# 十二、证据管理与运行记录

每轮测试生成唯一 Run ID。

建议命名：

`ri095-authorized-YYYYMMDD-attemptN`

证据目录：

`evidence/runtime-acceptance/<RUN_ID>/`

至少保存：

- `environment.json`
- `source-status.txt`
- `source-hashes.json`
- `execution.json`
- `image-digests.txt`
- `migration-results/`
- `frontend-build/`
- `database/`
- `celery/`
- `report-html/`
- `report-pdf/`
- `storage/`
- `auth/`
- `delivery-chain/`
- `browser/`
- `fault-injection/`
- `rollback/`
- `artifact-index.json`
- `results.md`

每项证据记录：

- Run ID。
- Git commit。
- 工作树差异摘要。
- 实际镜像 digest。
- 执行时间。
- 命令。
- 退出码。
- 预期结果。
- 实际结果。
- Gate 状态。
- 证据路径。
- SHA-256。
- 失败原因。

不要将密码、JWT、API key 或其他敏感凭据原文写入仓库证据。

证据索引的 SHA-256 仅证明文件完整性，不代表其中的断言已经通过验证。

---

# 十三、Gate 状态与验收标准

使用以下状态：

- `PASS_STATIC`
- `PASS_RUNTIME`
- `PASS_E2E`
- `PARTIAL`
- `FAIL`
- `BLOCKED`

## 13.1 PASS_STATIC

只表示静态检查、配置检查、代码检查或离线规划通过。

不得将其视为真实运行通过。

## 13.2 PASS_RUNTIME

必须具备真实运行环境和可复核证据。

至少证明相应服务、数据库、任务、文件和权限行为在真实执行中符合预期。

## 13.3 PASS_E2E

必须完成真实业务入口到最终交付物的端到端执行。

需要包含实际浏览器交互、任务执行、报告生成、Manifest 关联、ZIP 验证和授权下载等适用场景。

## 13.4 PARTIAL

表示部分场景通过，但仍存在必需的未完成测试或已知缺口。

## 13.5 FAIL

表示实际执行发现缺陷，或实际结果违反明确的验收断言。

必须记录复现步骤、根因、最小修复和重跑证据。

## 13.6 BLOCKED

表示由于环境、授权、可信数据、工具链或其他前置条件缺失，无法完成所需验证。

必须写清楚解除条件。

**同一个 Gate 只要仍有必需场景未完成，就不得标记为整体通过。**

不得把某个子场景通过扩大解释为完整验收成功。

---

# 十四、最终检查清单

最终报告必须逐项给出状态、实际证据和缺失条件。

## RC00：准入与源码

- [ ] Agent 自身 Docker 权限已核实。
- [ ] 隔离环境已真实启动验证。
- [ ] 源码 commit 与工作树差异已记录。
- [ ] 真实镜像 digest 已记录。
- [ ] 测试资源授权已核实。

## RC01：运行基础

- [ ] Alembic DAG 检查通过。
- [ ] 空库迁移真实通过。
- [ ] 历史数据库升级真实通过，或明确 BLOCKED。
- [ ] PostgreSQL 约束测试通过。
- [ ] Compose 隔离检查通过。
- [ ] UID/GID 与私有卷真实检查通过。
- [ ] 前端真实 `npm ci` 通过。
- [ ] 前端真实 `npm run build` 通过。
- [ ] 当前部署前端与源码构建产物一致。
- [ ] Celery 任务注册、派发与重复投递验证通过。
- [ ] 阶段级故障恢复已验证，或明确 BLOCKED。

## RC02：报告与浏览器

- [ ] HTML 真实生成。
- [ ] HTML 数据库、磁盘和下载 SHA 一致。
- [ ] Pandoc/Typst/字体版本已固定。
- [ ] 中文 PDF 真实生成。
- [ ] PDF 解析、字体、分页检查通过。
- [ ] PDF 数据库、磁盘和下载 SHA 一致。
- [ ] PDF 失败时 HTML 保留且状态可恢复。
- [ ] Chromium 正常 sandbox 启动。
- [ ] Playwright 与 Chromium 版本匹配。
- [ ] 真实业务 E2E 完成。
- [ ] 1920/768/390 三种视口验证完成。

## RC03：科研交付

- [ ] FileRegistry 与本地存储验证通过。
- [ ] JWT 与跨 owner 权限验证通过。
- [ ] 撤权后访问被正确拒绝。
- [ ] 对象存储验证通过，或明确 BLOCKED。
- [ ] 已批准的真实任务 corpus 可用。
- [ ] M0 与历史 ZIP 基线已核实。
- [ ] Report 与 HTML/PDF 关联正确。
- [ ] M1 版本更新正确。
- [ ] ExportSelectionV2 真实执行。
- [ ] ZIP 包含预期报告与证据。
- [ ] ZIP 验证器通过。
- [ ] ZIP 下载 SHA 与数据库一致。
- [ ] 历史 Manifest 与 ZIP 原始字节不变。
- [ ] 完整故障恢复证据已保留。

---

# 十五、最终交付文档

输出：

`RI095-Authorized-Runtime-Acceptance-Results.md`

必须包含：

1. 执行摘要。
2. Run ID、Git commit 与源码状态。
3. 实际执行环境和授权边界。
4. 每项 Gate 的执行结果。
5. 真实执行命令与退出码。
6. 数据库迁移与约束验证。
7. 前端确定性构建。
8. HTML/PDF 渲染验证。
9. Celery 与阶段级故障恢复。
10. FileRegistry、存储与 JWT 验证。
11. M0/M1/V2/ZIP 交付链路。
12. Browser E2E 与三种视口结果。
13. 修复文件与最小 diff。
14. 证据目录及 SHA-256 索引。
15. 未解决问题与解除条件。
16. 回滚与资源清理记录。
17. 生产准入建议。

报告末尾必须明确回答：

- RC01 是否完整通过？
- RC02 是否完整通过？
- 完整 `PASS_RUNTIME` 是否达成？
- 完整 `PASS_E2E` 是否达成？
- 哪些 Gate 仍为 `PARTIAL`、`FAIL` 或 `BLOCKED`？
- 是否具备进入依赖上述验收结论的下一阶段的条件？

## 最终执行原则

真实执行优先于静态调查。

最小修复优先于大规模重构。

历史证据可复用，但不得自动继承通过状态。

缺少授权或可信基线时必须如实阻断。

所有修复必须经过相关回归测试。

不得为了得到 PASS 修改安全门禁。

**最终目标不是让报告显示全部通过，而是获得真实、可复现、可审计的科研项目交付运行证据。**
