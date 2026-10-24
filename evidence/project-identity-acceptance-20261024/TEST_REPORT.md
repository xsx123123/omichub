# CygnusX 项目空间测试报告（F01/F02/F03 运行验收）

> 执行日期：2026-10-24｜执行人：编码 Agent（用户授权）
> 依据：`ARCHITECTURE_DESIGN/CygnusX_Project_Workspace_Test_Plan.md`
> 本报告为实际执行结果；历史单测数量不作为本轮结论。

## 基线

| 项 | 值 |
| --- | --- |
| HEAD / 分支 | `b3ed8c63` @ `fix/project-management-wp1-wp2`（含修复 `dc4893b0` + 本轮验收期修复，工作区另有 DEF-04 修复未提交，见"缺陷与修复"） |
| Python / PG | 3.11.14 / PostgreSQL 14.23（cygnusx-db 容器） |
| migration revision | `project_lifecycle01`（链头唯一，`make check-alembic-heads` 通过） |
| 存储根 | `/data/omichub`（HTTP 验收临时用户目录已清理） |
| 功能开关 | `project_export_enabled=False` 等科研开关全部默认关闭（HTTP H08 证明关闭态仍阻断） |
| 验收环境 | 宿主机直连开发栈：PG 127.0.0.1:5432、Redis 127.0.0.1:6379、进程内 ASGI 加载**当前工作区代码**（容器内 cygnusx-web 为 10-18 旧构建 `e78fd1ef`，不含本轮修复，未用于验收） |

## 用例结果

### A 层：本轮修复（SQLite 隔离回归 + 真实 PG + 真实 HTTP）

| 用例 | 状态 | 证据 |
| --- | --- | --- |
| ID-01 改名后四类入口稳定 slug（Case/Studio/会话归档/Overdrive） | PASS | 单测 `test_case_run_dir_keeps_stable_slug_after_rename`、`test_register_artifact_uses_bound_project_slug_not_title`、`test_ensure_chat_archive_uses_bound_project_slug`、`test_archive_overdrive_delivery_uses_slug_not_display_name`；HTTP H04/H14 |
| ID-02 project_id 不存在/已删除 | PASS（Overdrive 返回 None 不落盘；Case 404） | 源码路径 + 单测 `test_archive_overdrive_delivery_skips_without_project_id`（存量） |
| ID-03 跨用户 | PASS | HTTP H09（GET/PATCH/DELETE 全 404，不泄露引用计数） |
| ID-05 未绑定名称入口 | NOT_APPLICABLE（按方案留待 WP1 后续 API 契约扩展，本轮未改） | — |
| DEF-01..05 默认项目连续复用/删除后新身份/再次删除 | PASS | 单测 DEF 系列新增 5 例；HTTP H11/H12（真实会话入口：复用同 id；删除后新身份 slug=`默认项目-2`） |
| DEF-06..08 并发（默认解析/显式竞争/跨用户） | PASS | 真实 PG 临时库 PG-F/PG-G/PG-H |
| DEF-09 预留不提前 commit | PASS | `test_reserve_identity_does_not_commit_outer_transaction` |
| DEF-10 后缀 slug 跳过占用 | PASS | `test_default_project_skips_occupied_suffix_slug` |
| 默认项目改名后识别 | PASS（契约：按 slug 识别；改名复用，不另建） | `test_renamed_default_project_still_reused_by_slug` |
| DEL-R01..R10 十类引用阻断 | PASS | 参数化 10 例（开关默认关闭态）+ `test_delete_blocked_with_export_flag_enabled`（开启态） |
| DEL-01 干净删除 | PASS | 单测 + HTTP H07 |
| DEL-02 多类引用完整阻断信息 | PASS | `test_delete_blocked_reports_multiple_reference_types`（"数据集 1、科研计划 1"） |
| DEL-03 跨用户删除 | PASS | `test_delete_foreign_project_is_not_found` + HTTP H09 |
| DEL-04 重复删除 404、tombstone 唯一 | PASS | 单测 + HTTP H07 + PG-E |
| DEL-06 未识别异常保持原分类 | PASS | 单测（SQLite FK）+ 真实 PG PG-C（未登记表 FK → IntegrityError 原样抛出，回滚无部分提交） |
| DEL-07 中途失败无部分提交 | PASS | `test_delete_mid_operation_failure_no_partial_commit` |
| DEL-08 会话字符串引用现状 | 记录：chat_sessions.project_id 保留指向已删项目 id（F08 缺口，方案内后续） | HTTP H12 后会话仍持旧 id，新会话已归新默认项目 |
| DEL-R 并发引用写入（PG-DEL-01/02） | PASS | PG-B：owner+项目行锁下插入被阻塞；删除先提交后插入被 FK 拒绝；无悬空引用/部分提交 |
| PG-DEL-03 冲突后会话状态 | PASS | PG-D：同一 AsyncSession 冲突后新事务正常创建提交 |
| PG-DEL-04 并发删除 | PASS | PG-E：一胜一 404，tombstones=1 |
| HTTP 基本链路（H01..H14） | PASS | 未认证 401；创建 201；改名保留 slug；overview；空 PATCH 422；409+code+中文计数；list/count；sync-from-disk；物理目录稳定 |

### B 层：相邻回归

| 范围 | 结果 |
| --- | --- |
| 文件/上传/团队 ACL/工作区归档/路径工厂/存储后端/项目概览/项目归档（11 个测试文件） | 121 passed |
| 全套单测 `pytest tests/unit -m "not quarantine"` | 4122 passed / 7 failed——7 个与本轮无关的存量失败（parallel_subagent / provider_retry[宿主 .env 环境] / research_tool_pack / studio_approval / studio_manager / tool_error_codes×2，上一工作包已用基线 worktree + stash 双重核对） |
| `make check-migrations` / `make check-alembic-heads` | 通过（无迁移变更） |
| ruff（本轮新增/修改文件） | All checks passed |

### C 层：后续工作包

FUT-01..13（F04 持久打包、F05 页面操作、F06 分页、F07 排序扫描、F08 侧入口矩阵、F09 能力、F10 指标）——**NOT_RUN**，属后续工作包验收，不影响本轮放行结论。

## 汇总

- PASS：A 层 SQLite 30 + 真实 PG 8 + 真实 HTTP 14；B 层 121 + 全套 4122
- FAIL：0（本轮范围）
- BLOCKED：0
- NOT_APPLICABLE：ID-05（未绑定名称入口保持兼容，方案既定后续）
- NOT_RUN：C 层 FUT 系列（后续工作包）
- PostgreSQL 并发：**已完成**（临时库 `cygnusx_identity_verify_*` 验后销毁）
- 真实 HTTP：**已完成**（ASGI + 真实 PG/Redis/JWT/审计/限流中间件全链）
- Worker/浏览器：未执行（本轮改动不触达 Worker；页面无改动）

## 一致性结论

- 项目 UUID/slug 与运行路径：改名后四个已绑定入口全部落原 slug 目录；物理目录 `projects/Original` 保留、无 `Renamed_Project` 目录。
- 默认项目连续及并发复用：真实会话入口连续创建复用同一身份；删除后新会话获得 `默认项目-2` 新身份，旧 tombstone 保留；并发解析收敛单行。
- 引用保护与事务回滚：十类引用 + 开关两态阻断；并发窗口由行锁 + FK 兜底，无悬空引用、无部分提交；未识别异常保持 IntegrityError 分类。
- 历史文件和证据：删除仅移除 DB 行与根目录索引，物理文件保留（H07/单测）。

## 缺陷与修复（验收过程中发现）

1. **DEF-04 真实缺陷（已修复，待提交）**：`reserve_project_identity` 复用语义只按基名 slug 查找——默认项目被删、替代身份（`-2`）建立后，再次解析会继续分配 `-3/-4`（每个后续会话一个新项目）。修复：slug 未命中且复用语义时按显示名回退识别既有替代身份（与统一前默认路径的名称优先语义一致）。回归：`test_default_project_replacement_stable_across_sessions`（修复前失败）；HTTP H11/H12 在修复后代码上通过。
2. 测试脚本自身 4 处断言/工具 bug（H08 tombstone 计数范围、H10 count 响应结构、cleanup UserModel 删除、导入排序），均为脚本修正，非产品缺陷。

## 未解决问题

- 已识别但超出本轮：F04–F10、未绑定名称入口契约扩展、DEL-08 字符串引用矩阵。
- 验收期未提交变更：`project_service.py`（DEF-04 修复）+ 测试/脚本/文档——见"放行结论"。

## 放行结论

- **代码与隔离回归：通过。**
- **真实运行验收：通过**（真实 PG 并发 + 真实 HTTP 全链；容器 web 服务未含本轮修复，部署前置条件见下）。
- 上线前置条件：合并 `fix/project-management-wp1-wp2` 并重建/重启 cygnusx-web（当前容器为 `e78fd1ef` 旧构建）；无数据库迁移。

## 证据文件

- `pg_verify.log`：真实 PG 8 用例原始输出（临时库验后销毁）
- `http_verify.log`：真实 HTTP 14 用例原始输出
- 复现命令见 `scripts/poc/verify_project_identity_pg.py` / `verify_project_identity_http.py` 头部注释
