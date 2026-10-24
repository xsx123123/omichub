# Changelog

本文件记录 CygnusX（OmicHub）所有显著变更。格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循语义化版本。历史提交信息见 `git log`（conventional commits）。

## [Unreleased]

### 2026-10-24 — 项目管理优化 WP1/WP2：项目身份统一与删除保留契约（审计 F01/F02/F03 修复）

> 分支：`fix/project-management-wp1-wp2`｜基线：`8411a452`
> 依据：`ARCHITECTURE_DESIGN/CygnusX_project_management_review.md`（审计快照 F01–F10）与配套优化方案 WP1/WP2。
> 本轮先以 21 个失败回归复现问题（旧行为下全部失败），再实施修复；修复后全部转绿。

#### Fixed

**F01 / P1 — 项目改名后运行目录分叉（已绑定项目的生产入口改用稳定 slug 落盘）**

- `application/services/agentteams_service.py` — `_prepare_case_run`：已通过 `project_id` 解析项目后，
  run 目录改为按 `project["slug"]`（稳定目录名）创建，不再用可变显示名 `project_name or project["name"]`
  重新推导目录；显示名仍随 Case ref 返回供展示，meta 新增 `project_slug` 字段。
- `application/services/studio_context_service.py` — `register_artifact_report`：会话已绑定项目
  （`session.project_id` 经 owner 校验可解析）时，产物登记的 run 目录按项目稳定 slug 落盘；
  未绑定的旧入口保持"标题即项目名"的兼容行为（标题为空/「新对话」仍报业务错误）。
- `application/services/chat_archive_service.py` — `ensure_chat_archive`：run 目录改用
  `_project_for_session` 返回的 `project.slug`（绑定→模型 slug；未绑定→由标题推导，与旧行为等价）。
- `application/services/project_archive_service.py` — `archive_overdrive_delivery`：Overdrive 交付归档
  的 run 目录改用 `project.slug`（DB 记录缺失的兜底 `ProjectInfo` 仍由显示名推导 slug，行为等价）。
- 不变量：已有项目 `slug` 不随改名变化；`project_id` 创建后不变；历史目录不迁移、不重绑证据；
  科研交付/报告/审计报告等本就按 slug 落盘的入口（`project_delivery_service` 等 4 处）不受影响。

**F02 / P1 — 会话默认项目绕过删除身份保护（统一身份预留入口）**

- `application/services/project_service.py` — 新增 `ProjectService.reserve_project_identity()`，
  作为显式创建 / 按名复用 / 会话默认项目三类路径的统一身份预留入口：
  - owner 行锁（`SELECT ... FOR UPDATE`）串行化同用户并发创建；
  - tombstone 检查：显式创建语义保持 `PROJECT_SLUG_RETAINED` 冲突；复用语义（默认项目/按名建单）
    在 slug 被已删除身份保留时分配新的可用 slug（`-2` 起，跳过存量与 tombstone），**不复活旧身份**；
  - 目录投影：创建即登记 `user_directories` 的 `projects/{slug}` 记录；
  - 仅 flush 不 commit，事务边界由调用方控制。
  - `create_project` / `get_or_create_project_by_name` 重构为该入口的薄封装
    （显式创建仍预建物理目录并 commit；按名复用删除了原先"撞 tombstone 即抛冲突"的行为，改为分配新身份）。
- `application/services/chat/session_management.py` — `_resolve_default_project_id` 重写：
  不再直接 `ProjectModel(...)` 裸建行（旧实现无 owner 锁、无 tombstone 检查、无目录投影），
  改调统一身份预留入口；仍保持"仅 flush、交给外层事务"的边界。

**F03 / P1 — 科研保留引用未完整转换为删除冲突（完整预检查 + FK 兜底）**

- `application/services/project_service.py` — `delete_project` 重写：
  - 预检查覆盖 **10 类**指向 `projects.id` 的 RESTRICT 引用：datasets、dataset_ingestions、
    research_plans、result_manifest_observations、download_execution_budgets、
    download_execution_admissions、project_export_jobs、project_export_requests、
    project_report_jobs、project_report_requests（登记于 `_RETAINED_REFERENCES` 常量，
    新增 project_id 外键时必须同步登记）；
  - **独立于功能开关**：旧实现仅在 `project_export_enabled=true` 时检查导出 Job 一项，
    现在任何开关状态下已存在的证据都会阻止物理删除；
  - 命中引用返回稳定 409：`code=PROJECT_HAS_RETAINED_REFERENCES`，`detail` 以中文列出
    各类保留引用计数（沿用现有 `{detail, code}` 错误模型，不引入平行格式；
    原导出专用码 `PROJECT_EVIDENCE_RETAINED` 随之退役，该码无前端/测试引用）；
  - 并发兜底：预检查与删除之间新增引用触发数据库 RESTRICT `IntegrityError` 时，
    先完整回滚（不留部分提交），再重新执行预检查并转换为同一业务冲突；
    仍无法识别的约束异常原样抛出，不吞掉其他数据库故障；
  - 删除成功路径不变：写 tombstone → 删项目行 → 删根目录索引 → commit，物理文件保留。

#### 回归测试（先失败后修复，共 21 个新增用例）

- 新增 `tests/unit/test_project_identity_wp1_wp2.py`（F01/F02/F03 回归，内存 SQLite + tmp_path 工厂）：
  - F01：AgentTeams Case 改名后 run 目录仍落原项目 slug；无显示名时同样按 slug 落盘。
  - F02：删除默认项目后新会话不复活旧 slug（分配 `-2` 新身份）；同用户复用、跨用户隔离、
    目录投影登记；`get_or_create_project_by_name` 撞 tombstone 时分配新身份。
  - F03：10 类保留引用逐一阻断（参数化，开关默认关闭状态）；干净项目删除写 tombstone
    且物理文件保留；预检查竞态由 FK 兜底（回滚后重新解释为 409，无部分提交）；
    跨用户删除返回 404。
- 扩展 `tests/unit/test_studio_context_service.py`（1 例）：绑定项目的 Studio 产物登记按 slug 落盘。
- 扩展 `tests/unit/test_project_archive_service.py`（1 例）：Overdrive 归档按 slug 落盘（显示名与 slug 显著不同）。

#### 存量测试适配（行为契约未变，测试替身补齐）

- `test_project_lifecycle.py` / `test_project_delivery.py`：fixture 建齐全部保留引用表
  （delete 预检查需要）；后者建表改 `checkfirst=True`。
- `test_project_report_selection.py`：4 处建表改 `checkfirst=True`（与 fixture 预建表共存）。
- `test_project_get_or_create.py`：fallback 用例改为断言统一身份预留的真实创建行为
  （原用例 mock 了 `create_project` 委托这一实现细节）。
- `test_session_project_binding.py`：默认项目用例补目录仓储替身；customer 用例补 `flush` mock。
- `test_studio_context_service.py`：`_FakeDb` 补 `refresh` 与 `DirectoryModel` 默认字段回填；
  `get` 路由补 `ProjectModel`。
- `test_agentteams_rooms.py`：`fake_get_project` 按真实契约补 `slug` 字段。

#### 验证记录

| 检查 | 命令 | 结果 |
| --- | --- | --- |
| 新增回归 | `uv run pytest tests/unit/test_project_identity_wp1_wp2.py …` | 修复前 21 失败（复现缺陷）→ 修复后全绿 |
| 单元全量 | `uv run pytest tests/unit -q -m "not quarantine"` | 4111 通过，7 失败——经干净基线 worktree 与 stash 双重核对均为存量失败（parallel_subagent / provider_retry[本地 .env 环境] / research_tool_pack / studio_approval / studio_manager / tool_error_codes×2），与本轮无关 |
| E2E | `uv run pytest tests/e2e -q -m "not quarantine"` | 5 通过，7 失败（langgraph 沙箱审批域）——stash 核对为存量失败 |
| Lint | `uv run ruff check <本轮改动文件>` | 0 错误（3 处 import 排序已自动修复）；仓库其余 265 个 ruff 存量错误未动 |
| 类型 | `uv run mypy <本轮 6 个 src 文件>` | 0 新增错误（53 对比基线 56，按错误文本去行号比对无差异；CI 不跑 mypy，本地补跑） |

#### 2026-10-24 运行验收补记（同日第二轮）

按 `ARCHITECTURE_DESIGN/CygnusX_Project_Workspace_Test_Plan.md` 完成运行验收，报告见
`evidence/project-identity-acceptance-20261024/TEST_REPORT.md`：

- **Fixed**：验收 DEF-04 发现真实缺陷——默认项目被删、替代身份（`默认项目-2`）建立后，
  再次解析会继续分配 `-3/-4`（每个后续会话各建一个新项目）。`reserve_project_identity`
  复用语义补按显示名回退识别既有替代身份（与统一前默认路径名称优先语义一致）。
- **真实 PostgreSQL 并发验收 8/8 PASS**（`scripts/poc/verify_project_identity_pg.py`，
  一次性临时库验后销毁）：owner/项目行锁串行化（并发插入被阻塞、删除先提交则插入被
  FK 拒绝、无悬空引用）、未登记引用表 FK 异常保持原分类、冲突后会话可复用、并发删除
  tombstone 唯一、并发默认解析/显式竞争/跨用户同名收敛。
- **真实 HTTP 验收 14/14 PASS**（`scripts/poc/verify_project_identity_http.py`，进程内
  ASGI + 真实 PG/Redis/JWT/审计/限流）：创建→改名（slug 不变）→overview→删除全链、
  409 `PROJECT_HAS_RETAINED_REFERENCES` 错误结构、跨用户 404 不泄露引用计数、真实会话
  入口默认项目复用、删除默认项目后新身份 `默认项目-2`、物理目录稳定。
- 单测新增 12 例（A 层补充：DEF-04/05/09/10、DEL-02/04/06/07、开关开启态、会话归档
  slug），全套 4122 passed（7 个与本轮无关的存量失败不变）；B 层相邻回归 121 passed。
- 上线前置：合并本分支后需重建/重启 cygnusx-web（容器当前为 10-18 旧构建 `e78fd1ef`）。

#### 未验证与已知边界（如实列出）

- **真实 PostgreSQL 并发未验收**：owner 行锁并发建项目、RESTRICT 兜底的真实 PG 行为、
  真实 HTTP 409 结构均需集成环境验证；SQLite 回归不证明 PG 锁语义。
- **未绑定项目的旧名称入口保持现状**：`TaskService._make_work_dir` 与 6 个生信工具
  （blast/deg/gsea/synteny/enrichments/phylogenetic_tree）以任务/项目名直接落盘、
  无 `project_id` 参数——按优化方案属"未绑定旧名称入口"，需 API 契约扩展（schema + 前端），
  留待 WP1 后续；本轮已绑定路径全部收敛。
- 会话/协作室的字符串 `project_id` 关联、子目录索引解绑（审计 F08）未在本轮范围。
- 项目完成后的进程内打包（F04）、会话分页（F06）、运行排序扫描（F07）等见审计快照，未动。

#### 迁移与回退

- **无数据库迁移**：未改任何 ORM 模型/表结构，`make check-migrations` 不受影响。
- 部署前提：无。回退即还原本提交；tombstone/唯一约束等数据不变量由数据库既有约束保证，
  回退不破坏已产生的 `-2` 后缀 slug 身份（仅表示后续创建回到旧的冲突语义）。

## [历史版本]

2026-10-24 之前的变更未在本文件追溯，请查阅 `git log` 与 `ARCHITECTURE_DESIGN/` 各 as-built 文档。
