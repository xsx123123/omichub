# 01-Prompt｜直接交给 Codex：P0-A Trusted Admission & Budget Binding

复制以下完整提示词（请在仓库根目录、与其他工作包文件隔离的工作树执行）：

---

你是 CygnusX BioOps 的**资深 Python / FastAPI / SQLAlchemy / PostgreSQL / 分布式事务与权限安全工程师**。本轮任务名 **P0-A：Trusted Admission & Budget Binding**。先阅读 `01_P0A_Implementation.md` 与 `00_Overall_Roadmap.md`（如未放入仓库，先让操作者提供），以及当前仓库中权威的架构文档、`CygnusX_Current_Implementation_Status_Audit_2026-10-18.md`。**不要据旧报告假定代码没有变化。**

## 不可变边界

- 只复用 `DatasetImportService`、`ToolConfirmationService`、`DownloadService`、`TaskService`、原 `Task`/PG、`FileRegistry`、Celery 和当前 dirty 的 `download_execution` Model/Repository/迁移。
- **不要**创建第二套 Approval/Task/Quota/Queue/Gateway；不要把 `caller_already_verified`、模型参数或 HTTP header 当成人工审批事实。
- `DOWNLOAD_TRANSPORT_RUNTIME_ACCEPTED=False`、`WRITE_RUNTIME_ACCEPTED=False`、Agent 写开关保持关闭；不要启动下载或 Supervisor。工作树和子仓未提交修改不能覆盖；不得自动 commit/push。
- 若无独立授权 PG，只完成源码、迁移静态审查与隔离测试，并将真实 PG 明确记为 `RUNTIME_BLOCKED`。不许连接默认业务数据库。

## P0-A0：开工前只读调查（必须先做）

1. 记录主仓 HEAD/branch/dirty，所有子仓及 nested report 的 gitlink、HEAD、dirty，保留 tracked diff 和 untracked 清单；定位审计中的 `dwnadmission01`、`models/download_execution.py`、`repositories/download_execution_admission.py` 当前代码。把新增和已有字段列出差异表。
2. 画真实调用链：`Prepare → Human decide → persisted approval/ingestion → Task → admission → budget → existing Worker`；逐函数标明 Session/transaction owner、锁、权限来源。
3. 查 `DownloadService.submit` 的 idempotency/after_commit/Task WorkDir、`ToolConfirmationService` nonce、现有 `Admission` resolver 和可撤销状态；列出旧代码不能证明的事实。
4. 写 `evidence/p0a/baseline/` 快照，不执行数据库写。

## P0-A1：持久审批与同 Task 绑定

- 在原确认和 ingestion 流程中持久化/关联不可变审批快照：actor/time/JWT来源哈希、owner/project、ingestion/proposal、source/request digest、scope、expires/revokes 与版本；禁止保存明文 token。
- `issue_processed_http_admission` 或等效服务入口必须使用受信数据库连接**重新查询和验证**审批、原 Task、owner/project、参数、request digest 和当前状态；禁止由调用方 `approved=True` 直接放行。
- 同一 `ingestion + approval + attempt/epoch` 只绑定原业务允许的一项 Task；相同幂等请求按原 S4 语义复用，不重复创建活跃 Task。raw 多 Task 若未共享预算实现完备则强制拒绝，不偷偷拆分上限。
- Admission 绑定 caller（human/agent 仅可信身份来源）、固定环境 ID、签名工具/镜像 digest、协议 HTTP 候选、policy digest、有效期，拒绝错绑/跨用户/跨项目/过期/重放。

## P0-A2：预算状态机与迁移

- 以最少新增字段/表实现共享持久预算 reservation，支持原子保留、Claim CAS、attempt/epoch fencing、撤销、未知结果保持额度、可信报告后结算；不以最终文件 size 充当网络 RX，也不自行伪造 G3 计数。
- 若已存在等价记录，复用并补齐索引/check，避免双账。并发时 `SUM(reservation) <= parent_limit` 为强约束；仅单 Task processed HTTP 作为第一里程碑，raw 多 Task 必须独立标明支持范围。
- 检查所有字节类型在 PostgreSQL 真实映射是否为 32-bit Integer。若业务最大预算会超过上限，采用 BigInteger/SQL 约束与有序迁移；或明确并强制拒绝超界请求。不能在 SQLite 小整数测试后宣布解决。
- 已运行 Admission 的取消：标记撤销需求而非宣称 OS 已停止，直到 G3 的可信 scope/egress 关闭回执，否则 `RECONCILIATION_REQUIRED`、保留未定预算。

## P0-A3：测试优先于宣称通过

新增或适配 `tests/unit/test_download_execution_admission.py` 及最小专项测试：

1. 未批准、无效 actor/project/scope、旧 approval、请求/来源/工具/环境 digest 篡改全部拒绝。
2. 同 Task 并发双签发/双 Claim、Redis 重放、PG 唯一约束、锁等待与 deadlock。
3. parent budget 由多个 Task 并发争抢时严格不超额。
4. Transaction rollback/savepoint/commit failure，不留可执行孤儿 Admission、不提前 enqueue。
5. >=2GiB 边界、负数/0/溢出、网络与盘/inode 单位分离。
6. 取消前、claim 后、Worker 失联与重复 epoch，绝不凭没有回执释放完整余额。
7. 旧 S4 幂等/取消/FileRegistry 等回归不能退化。

离线阶段先 red→green，要求 Ruff、针对性 mypy/迁移链。获明确授权的非生产 PG 后执行真实**双连接、事务屏障、锁与并发**测试；保存服务端版本/SQL/exit/Task 行/余额/错误码。不使用 SQLite 替代 PG PASS。

## P0-A4：交付与停机条件

生成 `docs/implementation/cygnusx-p0a-trusted-admission-budget-binding.md`，应含：

- 当前与修改后架构图、数据模型/状态机、具体代码 diff 清单；
- 审批→Task→Admission→Budget→attempt/epoch 的真实 ID 对账；
- DB 迁移及回退、旧 Task/旧数据兼容；
- 测试清单 `PA-01..PA-14` 与 PASS_ISOLATED/PASS_RUNTIME/BLOCKED 分层，完整日志与命令；
- 真实 PG 并发/撤销/额度结果；未运行就 NOT_TESTED；
- 与 G3 Supervisor 的 DTO/安全契约、尚待 G3 提供的 OS 事实；
- 保留原门禁的运行/源码证明；
- 有风险的文件、代码源 SHA、证据索引、回滚方案、最终 Go/No-Go。

**发现数据库结构冲突、真实审批来源不可追溯、事务难以可靠绑定、未经授权的数据库/网络/容器运行需求，立即停止危险步骤并汇报。** 不自动转入 G3、不开放人工或 Agent 下载、不提交/推送。完成本工作包后停止。
