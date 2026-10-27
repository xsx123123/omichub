# 欢迎语改造现状调查

调查日期：2026-10-26。架构入口：`ARCHITECTURE_DESIGN/README.md`、通知互动架构、Agent 执行框架、数据库架构；实施设计稿仅用于定义目标。

## 真实调用链

`DefaultLayout.vue` setup 注册 `useAdminWelcome()`，mount 时启动 role watch；同时 `loadCurrentUser()` 调用 `fetchUser()` 后消费 `consumeOnboarding()`。两条异步路径存在竞态，首次管理员也可能叠加 Toast。`OnboardingPopup.vue` 保持原样；新布局在完成 onboarding 判定后才调用 Toast。

`useAdminWelcome.ts` → `POST /api/v1/llm/generate-welcome`（RBAC AdminRequired）→ `WelcomeService.get_next_welcome()` → settings.welcome_yaml 读取和 welcome_state_yaml 游标写入。前后端兜底均含固定 root/晚上好。`main.py` lifespan 创建 `_seed_welcome` 后台任务，直接通过 `LiteLLMProvider` 调默认 provider 补池。旧 prompt 位于 `data/ai/prompts/welcome/admin_{system,user}.md`（prompt registry）；旧逻辑不属于 Agent Runtime。

Settings 默认路径为 `${storage_path}/cygnusx_data/welcome/{welcome,welcome_state}.yaml`，历史目录 `/data/omichub/omichub_data/welcome` 在当前宿主存在，uid:gid=1000:1000、755；`/data/cygnusx_data/welcome` 当前宿主不存在。用户报告的新目录 root:root 权限故障不能由此宿主路径直接证明，不伪造线上重现。此次不修改目录权限、不读写迁移旧文案。

## 可复用的真实契约

- `agent_loader.py` 读取 `data/CygnusX.yaml` 启用列表与 Agent YAML、prompt_file。公开 Agent 均带共享沙箱协议；内部 copywriter 应使用单独系统注册列表，避免被同步成可聊天/招募的公开助手，且不附加沙箱指令。
- `LangGraphRuntimeService(NodeDeps)` 是现有可注入依赖的 Agent 图执行器。最小内部适配器直接复用该图，tools/tool_executor/prepare_messages 均为空，不创建用户会话、不装配私有数据。模型来自 `AIProviderConfigService.get_active_default()`，推理由现有 provider_manager 执行；不是单独 SDK 调用。运行记录由新增表承载，图的 run_id 与持久化运行 ID 一致。
- Celery app 在 `infrastructure/celery_app/celery.py`，现有 Beat 时区 Asia/Shanghai；默认 analysis 队列有生产消费者。新任务路由该队列。通过分钟级轻量 tick 按 welcome_timezone 判断到期，避免更改全局时区。
- SQLAlchemy async Session、UUID users 主键、单字符串 admin/user 角色；非多租户欢迎文案，无私有数据。Alembic 当前 head=`project_lifecycle01`。新建 welcome batches/messages/runs/deliveries，独立可回滚迁移。
- 鉴权使用 JWT token_version + 实时 DB role/RBAC。首次会话由服务端签发的 token claim 保留，并在刷新 token 时继承，避免浏览器消费 onboarding 标志后重新领取。

## 兼容与边界

废止启动模型补池和 YAML 游标。旧 `/llm/generate-welcome` 作为管理员兼容入口调用新 DB 领取；新接口 `/welcome/claim`、`/welcome/impression` 和 `/admin/welcome/*`。DB 故障时静默不显示，登录独立；DB 可用但池为空时提供服务端短兜底并同样记录每日 reservation。ordinary/general 默认关闭，可配账号 allowlist。保留旧文件及旧路径 Settings 作为只读历史配置，不自动导入。

生产数据库、服务配置和 volume 不在开发测试中修改；真实测试使用独立隔离数据库，操作前记录配置/版本并备份测试 schema。上线迁移与发布步骤见 runbook，不能把测试结果写成生产已上线。
