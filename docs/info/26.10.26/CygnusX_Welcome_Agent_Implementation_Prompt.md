# CygnusX Welcome Agent｜开发执行提示词

你是 CygnusX BioOps 平台后端、前端、Agent 编排和部署工程师。

任务：将现有管理员欢迎 Toast 从失效的 welcome.yaml 文件池升级成
「基于平台现有 Agent Runtime 的每周离线批量欢迎语生成、验证、发布和分发系统」，
并允许经灰度后向普通用户展示。首次登录 OnboardingPopup 必须保持独立。

一、调查（必须首先执行且输出报告）
1. 检查 DefaultLayout.vue、useAdminWelcome.ts、OnboardingPopup.vue、authStore 的调用链。
2. 检查 welcome_service.py、welcome.yaml、admin_system.md、providers.yaml、llm.py。
3. 识别现有 Agent 注册/执行 API，现有模型路由、结构化输出、运行审计。
4. 识别现有 Celery/Beat 或项目统一任务调度方式，以及数据库 ORM/Alembic。
5. 只读核查旧欢迎池路径与新路径的 UID/权限问题；不得 chmod -R 777。
6. 输出 docs/welcome-agent/00-current-state.md，写明真实路径与兼容方案。

二、架构硬性要求
1. 真实调用现有 Agent Runtime 注册 welcome_copywriter Agent，不得仅在服务里单独调用 LLM SDK 冒充 Agent。
2. Agent 仅可使用经过批准的平台能力白名单；不读用户私有数据；不得执行 shell、任意检索或分析工作流。
3. 周日生成下一周候选，周一原子发布；所有批次进入 PostgreSQL，Agent run 可追溯。
4. 生产登录/Toast 接口绝不调用 LLM，旧 welcome.yaml 不再作为运行时主数据源。
5. 管理员与普通用户用不同 audience；普通用户首期默认关闭。
6. OnboardingPopup.vue 不改变，first_login 用户的首次会话不展示 Toast。
7. 保持原项目目录约定、RBAC、API Client、异常处理、日志、配置加载、迁移和测试框架。
8. 必须有 idempotency key、唯一约束、租约/短事务、防双发布、失败重试、降级和回滚。

三、实现顺序
F0：建立现状报告；
F1：创建 welcome_copywriter Prompt+Schema+质量校验，复用 Agent Runtime 并生成 24 条/受众；
F2：新增内容池和 delivery 表、Alembic 迁移，建立周期生成/审核/发布任务；
F3：实现认证 claim 和 impression，以及管理员审查/手工生成/撤回接口；
F4：前端将管理员 useAdminWelcome 替换为可扩展的 useWelcomeToast，维持 Onboarding 优先；
F5：补全测试、灰度开关、部署配置、观测与验收报告。

四、验收指标
- admin 和 general 各可成功生成至少 18 条合格内容，目标各 24 条；
- 每条可关联 agent_run_id、prompt_version、模型来源和验证记录；
- 登录产生 0 次 LLM 调用；
- 两设备同时登录每天至多显示一次（同一账号）；
- 下一周新内容可自动生成并原子发布；
- 多实例重复任务不造成双批次；
- LLM、Redis、数据库短时故障不会导致登录失败；
- 第一次登录仅显示 OnboardingPopup；
- 前端不再显示 OmicHub/root 旧文案；
- 完成所有相关单元、集成、前端回归测试。

五、工作边界
- 不要修改已有无关模块或进行大型重构。
- 不要擅自覆盖用户未提交变更。
- 所有新的路径必须按仓库真实布局命名。
- 不能臆造现成的 Agent API；发现契约不支持时先实现最小适配器并在报告中说明。
- 不能将示例 SQL/TypeScript 直接当作已经可运行的代码。
- 交付设计决策、实际改动清单、迁移与回滚步骤、可执行测试命令及完整结果。

请严格按 F0→F5 分阶段完成，并在每阶段生成可审查结果。
