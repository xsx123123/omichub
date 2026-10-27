# Welcome Agent 实现与验收报告

更新日期：2026-10-27。结论：F0–F5 的代码、迁移、接口、管理界面、运行手册和隔离演练已交付；**用户授权后已完成现有 Web/Worker/Beat 重启，最终接口及前端修复已生效**。当前管理员与普通用户各有 24 条 v1 活跃文案，普通用户展示仍关闭。默认模型最近返回 HTTP 402（余额不足）；首发人工内容批准和下一真实日历周切换仍无完成证据。全仓门禁尚未全绿，未提交或推送。

## 2026-10-27 运行切换与补充验收

- 用户回复“继续”后执行先前提出的协调重载。执行前重新备份并确认 Worker active/reserved 均为 0；停止唯一 Beat，再重启 Worker。Web 的 SIGHUP 滚动替换因现有 readiness 超时未完成，随后执行已授权的完整重启，恢复 Beat。未新建生产调度器、未修改生产时间或全局模型配置。
- 容器启动时间（UTC）：Worker `01:11:05Z`、Web `01:14:52Z`、Beat `01:15:21Z`。三个容器均 healthy；Web entrypoint 迁移检查及 schema drift 检查通过。连续 12 次原生 OpenAPI 采样均包含 `reservation_expires_at`；重启后真实 Beat/Worker 多次自动执行 `welcome.reconcile`，`published=0, enqueued=0`，未重复生成。
- 当前热挂载源码 HEAD 为 `b6ad48855660b79a9710fb33267b6cd5c068985d`，欢迎功能仍含未提交改动，以最新 source manifest 为准。`/health` 中 `git_sha=9313e6ab` 是既有镜像构建元数据，不能作为热挂载源码版本；本轮没有构建或发布新后端镜像。
- 通过登录页公开的 demo 账号正常调用原生登录和 `/auth/me`（均 200），普通用户 `/welcome/claim` 返回 204，确认展示开关仍关闭；未伪造 JWT、借用私有用户或消耗真实管理员领取额度。原生数据库仅核查既有 v1 活跃池；隔离 v3 候选没有灌入生产。
- 补齐实际编译应用的浏览器验证：原样 App、Vue Router、LoginView、DefaultLayout，连接独立 PG 和真实认证/欢迎 API；无关 GET 使用空 fixture，欢迎业务时钟明确模拟 2026-11-02。五项场景通过：管理员显示并回执、第二浏览器会话抑制、首次登录仅 onboarding、general 关闭不显示、general 开启显示并回执。两条合成账号 delivery 均为 shown/agent_pool，390px 与 1440px 截图及浏览器无错误记录已保存。
- 此演练发现登录成功 Message 在手机上遮挡欢迎标题。前端现等待已有 Message 和 modal 明确移除后再显示欢迎语，新增对应回归测试；欢迎专项 **7 passed**，全量前端 **100 files / 735 tests passed**，构建（含 `vue-tsc -b`）通过。全量测试日志仍含既有 jsdom navigation/resize-observer 输出，不将其描述为无警告。Nginx 返回的 index 与最终构建 SHA256 一致：`3ac14d1892ecacaea37317a351791cf12a45aae0c8961a688764ef64a6b77b8f`。
- 专用 PG 重新完整迁移后，欢迎单元/集成 **31 passed**，13 个欢迎源文件 strict typing 通过。原生 `/health`、接口版本与队列消费均已复核；本轮没有重新宣称后端全仓门禁全绿。
- 新私有备份：`/home/zj/.local/state/cygnusx/welcome-rollout-20261027T090810/`，目录 0700、文件 0600，含配置/源码/前端、容器信息、全库 schema 和四张欢迎表导出，归档清单已检查。含密钥的原始备份不写入公共 evidence。

本轮证据统一位于 `evidence/welcome-agent/rollout-2026-10-27/`。默认 `deepseek-v4-flash` 的既有健康探测返回 `402 Insufficient Balance`；已有 DB 欢迎分发不需要推理，但下一周生成需先恢复默认供应商。下一次自然生成为 **2026-11-01 03:00 Asia/Shanghai**，发布为 **2026-11-02 00:00**；尚未观察，不能用模拟周切换替代。

## 版本与范围

- 初次验收 HEAD：`916cf1faccbbeb7414da137c65ff39de09b8eb66`；10 月 27 日热挂载版本见上节。欢迎功能为未提交工作区改动；工作区原有及并行产生的无关改动保留。最终文件校验见 `evidence/welcome-agent/source-manifest.json`，不能仅用 HEAD 代表这些新代码。
- 迁移：`welcome_pool01` → 父版本 `project_lifecycle01`，四张 welcome 表。完整迁移、downgrade 再 upgrade、全库 ORM/schema 对账均在隔离库通过。
- 测试 PG：`pgvector/pgvector:pg15`，image ID `sha256:4b4956e2ab1f0aec9779dfca20366a9963a3f24c34269c3a115dd838387f0734`，仓库 digest `sha256:47af0b65960b14f1c6945aa4ccae37836c632e9a6fe0eea9160936e616e5b2e9`。未构建或发布生产应用镜像。
- 产品新依赖：无；未修改 uv.lock/package-lock。旧 welcome 文件没有改权限、迁移或导入。

架构与实际文件清单见 `ARCHITECTURE_DESIGN/CygnusX_welcome_architecture.md` 和 `01-decisions-and-stages.md`。部署与备份、开关、运维、回滚命令见 `RUNBOOK.md`。

## 真实模型与质量

使用平台已配置的默认 `deepseek-v4-flash`，通过 `WelcomeAgentAdapter` → **现有 LangGraphRuntimeService** → 现有 provider_manager 执行。运行时无 tools/MCP/skills、无用户会话/私有数据/沙箱上下文。不是独立 SDK 伪装 Agent。仅向供应商传公开事实、批准的历史欢迎语与版本化写作方向。

最终 v3 候选（目标周 2026-11-02，revision=4，policy_version=v2）：

| 受众 | 合格数（目标 24、门槛 18） | 主题 | agent run ID | batch ID |
| --- | --- | --- | --- | --- |
| admin | 22 | 5 | `b8f33e5f-3620-4a01-aa05-ab96cee7b806` | `cb9ea536-3eb5-4f53-a66c-91a4dc18471f` |
| general | 19 | 5 | `64cb6fcf-122b-48ec-9065-8052687c28cb` | `b0edaa30-5a10-4f8b-8e63-06f7bdb1a069` |

Prompt 版本 v3，SHA256 `7e33abe06fe7ddd1b987e6e0e91b11ab45baed1a97e949b77b942af540cfeb54`。每条关联 run；每轮可查模型配置 ID、prompt/request hash、供应商重试用量、错误类别、token 与费用估算。

最终两批记录已知 token 54,657，按现有模型价格估算合计 0.0301518 元；只涵盖这两批，不含前轮调优实验，不是供应商账单承诺。超时或供应商未返回用量时明确标记 usage_complete=false，不把未知费用写成零。

实测发现初始 prompt 常机械复述平台事实、0.65 的相似度阈值漏掉中文近重复；最终收紧为 Jaccard 0.42/字符序列相似 0.8，并增加正文主题校验、NFKC 规范化及分轮写作方向。v1/v2 的历史试验审计保留在 evidence，**不是生产候选池**。最终池正文与元数据在 `live-generation-v3.json`，包括拒绝原因；旧品牌/伪造能力/富文本/不合规 JSON/近重复均有针对性测试。规则和开发抽查不能代替上线首发的人工批准。

## 验证结果

| 检查 | 命令/范围 | 结果 |
| --- | --- | --- |
| 欢迎业务单元与真实 PG 集成 | `WELCOME_TEST_DATABASE_URL=.../welcome_test uv run pytest tests/unit/test_welcome_agent.py tests/integration/test_welcome_pool.py -q` | 31 passed；覆盖真实图执行、坏 JSON、超时、无工具、租约抢占/旧 worker fencing、回执、频率、降级、DB 故障、事务失败、回滚与 RBAC，新增三项管理员并发变更回归 |
| 相关运行时/装配回归 | 同上并加入 `tests/unit/test_langgraph_runtime.py tests/unit/test_agent_loader_studio.py -m 'not quarantine'` | 92 passed，1 个既有 quarantine 排除 |
| Provider 重试回归 | `tests/unit/test_provider_retry_policy.py`，结合相关域共 112 用例 | 111 passed，1 个既有 embedding 失败；已用原始源码复现 |
| 欢迎代码 strict typing | `uv run mypy` 新增 welcome 服务/schema/API/tasks/models，共 13 文件 | 无错误 |
| 新增欢迎代码 lint | `uv run ruff check` 同域及新测试 | 通过 |
| 前端全量 | `cd frontend && npx vitest run` | 2026-10-27：100 files / 735 tests passed（包含用户并行增加的其他域测试） |
| 前端欢迎专项 | `npx vitest run src/composables/__tests__/welcome-toast.test.ts` | 7 passed；安全 VNode、会话防抖、账号隔离、onboarding、切号丢弃、modal/已有 Message 关闭事件 |
| 前端类型与构建 | `npx vue-tsc --noEmit`、`npm run build` | 通过；最终构建文件哈希见 source manifest |
| Alembic | `uv run python scripts/check_migrations.py`；独立 PG `upgrade head → downgrade project_lifecycle01 → upgrade head` | 通过，单 head |
| Schema | `DATABASE_URL=隔离库 uv run python scripts/check_schema_drift.py` | ORM 与数据库无漂移 |
| 配置加载/镜像契约 | 装配单测、`make validate-image-mapping`、`uv run python scripts/test_studio_agent_runtime.py` | 通过，公开 Agent 列表未混入内部 copywriter |
| Bridge | `cd integrations/agentteams/bridge && uv run pytest -q` | 190 passed，2 skipped |

补充验证：新活跃池所有消息被禁用时会退回经过验证的 retired 池；没有可用旧池再走服务端静态兜底。不是直接跳过旧池。DB 不可用时返回无内容，以保留账号频率约束。

## Beat、浏览器和并发演练

使用专用 PG、专用 Redis broker/result backend、本次单独启动的真实 Celery Beat/Worker；业务时钟模拟 2026-11-02，Beat 调度本身按真实 wall clock 运行，未连接生产 broker。

- 2026-10-26 10:35:00（上海）Beat 自动投递 `welcome.reconcile`，任务 `2515dda9-58a0-4aa3-9162-35dc4d11073a` 在 Worker 成功：`published=2, enqueued=0`，原子切到最终两批。
- 10:36:00 下一次自动调度成功：`published=0, enqueued=0`。没有重复激活、没有模型调用。证据 `celery-beat.txt`、`celery-worker.txt`、`batch-state.json`。
- 10 月 26 日浏览器通过真实 `/auth/login`、`/auth/me`、签名 JWT、claim/impression API 和真实 PG，使用正式 Vue composable、Naive UI、原样 OnboardingPopup、欢迎管理组件；当时使用开发预览外壳。10 月 27 日已补齐实际编译应用及正式 DefaultLayout 的隔离浏览器演练，范围和限制见上节。
- admin/general 都显示 source=agent_pool 的最终真实文案；刷新、另一个浏览器会话当天不再显示；first_login 仅 onboarding，关闭/刷新后本会话仍无 Toast。390px 和 1440px、关闭按钮、文本节点及 aria-live 已检查。管理页可查看批次及 QA/run 元数据。浏览器期间 Redis 不可用，现有登录限流走原有降级，欢迎无 Redis 依赖。
- 独立合成账号的 200 次真实 HTTP claim、20 并发：1 次领取、199 次抑制、0 错误，回执成功。端到端 claim 延迟 P50≈478ms / P95≈669ms / P99≈835ms；是本机隔离环境数据，包含 JWT/DB，不是生产 SLO。

截图：`admin-desktop.png`、`admin-mobile.png`、`general-desktop.png`、`general-mobile.png`、`first-login.png`、`admin-review.png`；结果 `browser-results.json`、`load-test.json`。预览临时入口、进程和隔离容器在结束后清理，不作为新产品路由交付。

生产显示路径零 LLM 的证据同时包含模块依赖/源码检查、图 provider 调用计数在 claim/impression 后不增加的集成测试、无 provider 凭证的浏览器服务、真实 Worker 发布记录。认证 API 未增加欢迎生成依赖。

## 全仓门禁与存量失败

没有宣称全量全绿，也未违反 AGENTS.md 的提交前门禁要求替用户提交。

- `uv run pytest tests/unit tests/e2e -q -m 'not quarantine'`：快照 **4157 passed / 14 failed / 22 skipped / 63 deselected**。14 个失败均在 `git archive HEAD` 的原始源码副本中重现（定向复验 105 passed / 14 failed）。集中于既有 fan-out 用量合并、embedding 路由、MCP pack、Studio approval/mount、tool error contract 和 LangGraph sandbox approval；未改这些无关模块。
- 全量 ruff：基线 265、当前 265 条诊断；新增欢迎文件独立通过。
- 全量 mypy：基线 1011 errors / 213 files，当前 1007 errors / 211 files。忽略行号后比较，**新增诊断 0**；原始源码快照与 HEAD `916cf1fa` 的 src 完全相同。欢迎模块 strict 检查通过。
- 既有 quarantine 中 MCP 构建师用例断言 legacy-model，与当前配置不符；不算本功能通过，也未擅自修改。

比较证据：`baseline-comparison.json`、`full-backend-summary.txt`、`baseline-failure-summary.txt`。完整命令输出在本次 evidence/临时日志，报告仅保留不含凭证的结果。

## 逐项完成审计与未决项

| 规范范围 | 当前证据 | 状态 |
| --- | --- | --- |
| P0 真实源码链路、Agent/调度/DB/目录核查 | 00-current-state + 真实源码/宿主 stat | 已完成源码调查；线上 root:root 故障与旧 Toast 尚未独立重现 |
| P1 两受众真实 Agent ≥18、结构化 QA、跨周去重、幂等、失败保池、可追溯用量 | v3 两批 + 单元/PG/图/供应商重试测试 | 隔离环境通过 |
| P2 周界、补偿、单 active、回滚、并发账号/设备、未见优先、预留恢复/重复回执、DB/Redis/Agent 故障 | PG 并发/故障测试 + 真 Beat/Worker + 真实登录/浏览器 | 隔离模拟通过；实际供应商已出现空回复并在预算内恢复 |
| P3 Onboarding 不变、general 默认关/可开、刷新/跨浏览器限次、安全文本、手机/读屏 | 原组件无改动 + composable 7 测试 + 实际 DefaultLayout 浏览器/API | 通过；general 仅测试环境临时开启 |
| P4 手动目标周生成→QA→真实自动投递发布→登录领取/回执 | v3、Beat/Worker、浏览器、压力记录 | 完成一次模拟周界演练；不是真实日历周切换 |
| F5 旧 YAML 运行链退役、配置/观测/回滚/运维/报告 | 新代码、架构文档、本报告与 RUNBOOK | 已交付 |
| 运行环境 welcome_pool01、两受众 v1 活跃池及最终修复协调重载 | 只读 DB 核查、重启记录、健康检查、12 次 OpenAPI 采样及原生 Beat/Worker | 已完成重载；既有数据保留，general 仍关闭 |
| 管理员灰度、首发人工批准、下一真实周切换 | 实际 DefaultLayout 隔离灰度通过；生产人工批准/真实周观察无证据 | **待人工质量验收与自然周观察** |
| 默认供应商可用性 | 原生既有健康探测：deepseek-v4-flash HTTP 402 Insufficient Balance | **待恢复；未擅自更换模型或触发付费重试** |
| 全仓提交门禁 | 存量失败仍在 | **未绿，未提交/推送** |

材料风险：reservation 过期恢复无法证明断网/浏览器崩溃场景下物理屏幕 exactly-once；规则并非完备语义安全证明；供应商不返回 usage 时成本未知；isolated mock-provider 测试不替代生产供应商 SLA。真实周观察最早对应下一次周日生成/周一发布，按 RUNBOOK 留下运行记录后才能关闭这部分验收。


## 2026-10-26 后续复查：并发撤回与实际运行版本（历史记录）

本轮重新核对当前状态后新增三项真实 PostgreSQL 回归。修复前均失败，分别证明：

1. 发布巡检读到 scheduled 后，管理员已撤回，巡检仍把它改回 validated。
2. 失败生成重试在等待 run 行锁期间发生撤回，过期 batch 快照把它重新生成并 scheduled。
3. 两管理员交错禁用/恢复，恢复值与过期 enabled=True 快照一致，ORM 没有发送 enabled 更新。

现已分别在发布资源锁/run 行锁内刷新状态，并按稳定 audience/locale 顺序处理批量发布；31 项欢迎单元/集成测试通过。新证据为 `race-before.txt`、`race-after.txt`、`race-lint.txt`、`race-mypy.txt`。

只读核查正在运行的 cygnusx-web（开始时间 2026-10-26T02:13:28Z）发现：其 `/app/src`、`/app/data` 热挂载工作区，实际 DB 已有 welcome_pool01；admin/general 各有一个本周 v1 active 池，均为 24 条，general 展示仍关闭。但运行进程的 OpenAPI claim_fields 缺少 `reservation_expires_at`；新前端会因此跳过 Toast。磁盘文件新旧不能代替进程加载版本的验证。证据 `runtime-before-reload.json`；没有伪造用户 JWT、消费真实账号额度或修改生产表。

当时已准备协调重载 Web/Worker/Beat 并发起授权请求；10 月 27 日用户回复后已执行，结果见本报告首节。10 月 26 日私有备份仍位于 `/home/zj/.local/state/cygnusx/welcome-rollout-20261026/`：配置/源码/前端、运行容器信息、全库 schema、四张 welcome 表 custom-format 数据导出；父目录 0700、敏感归档 0600，归档清单已验证可读取。相关数据只读导出，不改变用户现有记录。
