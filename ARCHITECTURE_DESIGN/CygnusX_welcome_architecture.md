# CygnusX 欢迎语系统（as-built）

实现日期：2026-10-26，运行核验更新于 2026-10-27。现有 Web/Worker/Beat 已授权重启并确认加载最终接口及热挂载源码；现有两受众 v1 池各 24 条，general 仍关闭。代码、实际编译应用隔离演练及运行切换证据见 `docs/welcome-agent/WELCOME_ACCEPTANCE_REPORT.md`。默认模型最近返回 402，真实日历周切换及首发人工内容批准仍待验收；既有镜像的构建 SHA 不能代表热挂载工作区版本。

## 入口与边界

`DefaultLayout.loadCurrentUser()` 先消费现有 onboarding 协议，再调用 `useWelcomeToast`；首次会话写入账号级 sessionStorage 跳过标记。`OnboardingPopup.vue` 未改。服务端 access/refresh token 的 `onboarding_session` 签名位贯穿首次登录、2FA、首管设置与 token 刷新，claim 同样跳过该会话。旧 token 无此字段时按普通会话处理。

`POST /welcome/claim` 和 `/welcome/impression` 只访问 PostgreSQL，不导入生成适配器、读取文件或调用 Redis/模型。资格基于实时 users.role/status；general 默认关闭，可通过 Settings allowlist 灰度。数据库可用且池为空时提供后端短静态兜底，并照常记录频率；DB 不可用时返回无内容，不绕过频率控制。鉴权自身依赖数据库，DB 全面故障时不能承诺认证可用；欢迎模块不增加登录依赖。

旧 `/llm/generate-welcome` 保留管理员兼容路由，改为同一每日领取策略；`welcome_service.py` 只保留导入兼容别名。启动不再补写 YAML、不调用模型，仅后台将 reconcile 入队；原 welcome YAML/游标/路径配置保留归档，不自动导入旧品牌文案。

## 内部 Agent

- 注册：`data/CygnusX.yaml:agents.system_enabled` → `load_system_agent_configs()` → `data/ai/welcome_copywriter.yaml`。公开 agents.enabled 和 DB 助手同步不加载内部 Agent；不新增前台聊天入口或 Studio 能力。
- 执行：`WelcomeAgentAdapter` → 现有 `LangGraphRuntimeService(NodeDeps)` → 现有 provider_manager。默认模型来自 `AIProviderConfigService.get_active_default()`，不是新 SDK。
- 限权：tools、tool_executor、prepare_messages、MCP、skills 均为空；不装配用户记忆、知识、项目、会话、计费账户或沙箱。内部 prompt 不附加公开 Agent 的沙箱提示词。模型擅自输出工具调用时没有执行器，整次结果拒绝。
- 审计：NodeDeps.run_id 与 welcome_generation_runs.id 一致，execution_path=`welcome_system_langgraph`。每条消息引用 run；batch 保存 prompt 版本/SHA 和 QA；calls 保存每轮模型配置 ID、模型来源、请求哈希、prompt 哈希、provider attempt usage、估算费用、错误类别。provider 增加可选 usage 回调，默认调用行为不变；可计量空回复重试的额外消耗。超时/供应商未返回 usage 明确 `usage_complete=false`，不伪造零成本。
- Prompt 是受版本控制的内部系统任务配置，按版本文件加载并哈希；不是已发布到 DB 的公开助手 prompt。改公开助手仍须遵守管理端发布协议。

## 数据与并发

迁移 `welcome_pool01`，父版本 `project_lifecycle01`。四表 `welcome_batches/messages/generation_runs/deliveries` 全部注册 ORM metadata，UUID user FK。唯一约束覆盖 week/audience/locale/revision、生成幂等键、消息内容哈希、user/local_date，partial unique index 保证 audience/locale 只有一个 active。

生成先用短事务创建/领取 run，持有带期限的 lease_token；推理期间不保留事务。每轮审计与最终写入重新核验 lease_token，过期旧 worker 不可覆盖新结果。每次 run 最多三次租约尝试；每次尝试最多 ceil(target/8)+2 轮调用。失败不覆盖 active，重试按指数延迟由 reconcile 补偿；重试取得 run 行锁后重新读取 batch，确保等待锁期间发生的撤回不能被过期 ORM 状态覆盖；人工补生成显式使用新 revision，不修改已审批批次。

发布使用 audience/locale PostgreSQL 事务咨询锁；同一事务 retire 旧池、flush、activate 新池。scheduled 到期即可补发布，不依赖任务准点到达。若禁用消息后不达门槛，批次退回 validated 等人工复核，其余 audience 继续发布。巡检按 audience/locale 的稳定顺序加锁，并在锁内重新读取候选状态；已撤回/已被其他发布者处理的候选直接跳过。撤回设 withdrawn 并封住生成 run；回滚仅允许经验证的 retired 池，保存操作者和说明。

领取使用 user/local_date 咨询锁 + 行锁 + 唯一约束。未到期 reservation 的竞争请求返回 204，避免多个标签页同时显示同一 reservation（比返回同一内容更严格）。5 分钟未回执可重新领取，旋转 delivery ID 拒绝旧回执。impression 检查所有者/期限，重复回执不重复记数。仍无法在浏览器崩溃或长断网且无回执时证明“物理屏幕 exactly once”；承诺的是每日账本唯一、正常回执后不再分发和有限的预留恢复窗口。

当前池 → 最近一周经验证旧池（week_start 至多落后一周，即上期结束后最多延用七天）→ 服务端兜底；优先排除用户最近 30 日 shown 的 message。撤回池和禁用单条不再被新领取选择。无 Redis 游标或跨副本文件一致性依赖。

## 调度与配置

现有 Celery app/唯一 Beat 增加分钟级 `welcome.reconcile`，`welcome.*` 明确路由生产已消费的 analysis 队列。tick 在 `welcome_timezone` 计算日/周界；不修改全局 Beat 时区。周日配置时刻（默认 03:00）开始补下一周，周一到期原子发布；当前周缺失/超时租约也由 tick 修复。这覆盖每日 03:30 巡检及错过触发时的恢复，不增加第二套 scheduler。

配置唯一来源为 Settings 的 WELCOME_*；Agent YAML 声明身份/prompt/能力和输出上限，实际输出预算取配置上限与 Agent 上限的较小值。general 默认 false；`welcome_enabled=false` 同时关闭新领取、调度与生成。已发 reservation 的回执仍可确认。

## 内容质量与前端

中文首期仅 zh-CN。严格 JSON/Pydantic extra=forbid，14–48 字，最多一个 Emoji，拒绝旧品牌/root、控制字符、富文本、链接、隐私/诊疗/夸大能力和时间表述。保守策略拒绝具体能力宣传，而非借欢迎语推广功能。最近八周批准文案参与哈希与近似去重；Jaccard>=0.42 或字符序列相似>=0.8 拒绝（由真实中文近重复样本校准）。topic 同时做正文关键词校验，防止仅贴四个标签；至少 18 条且覆盖四个主题才可 scheduled。v3 prompt 强调句式和意涵差异，按轮次使用 YAML 中批准的公开写作方向，不要求每句重述平台事实。规则不等于完备的语义/敏感内容证明，首发仍需人工抽查。

前端安全文本 VNode + role=status/aria-live；通知五秒自动关闭、可关闭和悬停暂停，宽度适配小屏。若有 modal/approval 或已有登录成功/错误 Message，以 MutationObserver 等待明确移除事件，避免手机上叠加遮挡，不通过 sleep 猜测。超过 reservation 有效期不再显示。sessionStorage 只防 UI 重复，服务端负责跨设备频率。

管理入口：通知公告管理 → 欢迎语。支持生成、revision 补生成、刷新状态、逐条禁用/恢复、批次发布/撤回/回滚及 QA/run/token 元数据查看；所有 `/admin/welcome/*` 使用统一 AdminRequired。单条禁用/恢复在发布资源锁内刷新 message/batch 后执行，避免显式恢复与旧 enabled 快照相同而被 ORM 忽略。发布、撤回、回滚、禁用均留操作者/审核说明，平台 Audit 中间件照常记录请求。

监控通过现有 OTel meter：generation_runs、valid_messages、claim_latency、fallback、impressions、llm_tokens、pool_age（无 user 标签）。active 池过期仍由 reconcile 上报年龄，便于识别长期失败。
