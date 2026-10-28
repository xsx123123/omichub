# 2026-10-27 欢迎语运行切换证据

用户授权后重启现有 Web/Worker/Beat，保留当前两受众 v1 活跃池和 general=false。

- `before.json`、`drain-check.json`、`after.json`：重启前后状态、无活跃/预取任务、源代码与镜像版本边界。
- `web-after.json`、`native-*-welcome.txt`、`worker-statistics.json`：健康、12 次 OpenAPI 采样、原生 Beat/Worker 消费。
- `frontend-serving-final.json`：最终前端 index 哈希及 Message 协调代码已被 Nginx 提供；不使用较早的 `frontend-serving.json` 代表最终产物。
- `native-demo-check.json`、`catalogue-after.json`：公开 demo 正常登录/角色/claim=204 与数据库当前内容/开关；未消费真实管理员欢迎额度。
- `actual-layout-results.json`、`actual-layout-browser.txt`、`actual-layout-*.png`：实际编译应用（App/Router/LoginView/DefaultLayout），连接专用测试 PG 与认证/欢迎 API；业务日期模拟 2026-11-02，无关 GET 返回空 fixture。5 个场景通过，不将其称为生产全业务 E2E。
- `isolated-layout-deliveries.json`：合成账号的两个 agent_pool/shown 回执。
- `backend-tests.txt`、`backend-types.txt`、`frontend-tests.txt`、`frontend-full-tests.txt`、`frontend-build.txt`、`live-schema.txt`：31 个欢迎后端测试、13 文件 typing、7 个欢迎前端测试、全前端 735 个测试及构建/schema 检查。全前端日志含既有 jsdom navigation/resize-observer 输出。
- `provider-availability.json`：原生已有健康探测发现默认 DeepSeek 402；未为验收额外调用模型、改路由或充值。
- `cleanup-and-final-health.json`：结束时临时服务清理与生产容器健康复查。

原始备份含 env/容器敏感信息，仅保存于私有运维目录，未复制到此处。这里的测试账号和 delivery ID 均为隔离合成数据；不含 JWT。自然周生成/发布及首发人工内容批准尚未验收。完整解释见 `docs/welcome-agent/WELCOME_ACCEPTANCE_REPORT.md`。
