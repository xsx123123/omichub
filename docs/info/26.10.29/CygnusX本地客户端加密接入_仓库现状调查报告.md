# CygnusX 本地客户端加密接入 — 阶段 0 仓库现状调查报告

> 版本：v1.0（2026-10-29）
> 调查方式：**只读代码核查，未修改任何业务代码**；每条结论标注代码位置（文件:行号 或 文件#函数名）
> 调查基线：分支 `feat/report-center-ai-linkage`，提交 `b7482e6f`
> 调查目标：摸清后端现状，评估「本地客户端 + 应用层 TLS/mTLS」的接入改造量与风险点
> 配套：`docs/info/26.10.29/本地客户端接入_Part4回填稿_确认问题与行动顺序.md`（可直接回填活文档 Part 4）

---

## 0. 结论先行（TL;DR）

1. **API 层高度可复用，不需要为本地客户端另建一套接口。** 后端是单一 FastAPI 应用，全部业务挂在统一前缀 `/api/v1` 下，共约 **677 个路由装饰器**（含 admin/tools），鉴权以 `Authorization: Bearer <JWT>` 为主，天然适合非浏览器客户端。证据：`src/cygnusx/main.py:552`、`src/cygnusx/api/v1/router.py:75-184`、`src/cygnusx/middleware/auth.py:153-173`。
2. **真正的阻断项不是密码学，而是三类工程适配：**
   - **引导信息分发缺失**：服务器地址、私有 CA、客户端证书、证书指纹目前没有任何分发/注册机制（§D3）。
   - **前端同源硬编码**：API 基址、WebSocket 主机、静态资源路径全部依赖同源部署（§E3-E5）。
   - **浏览器专有链路**：报告预览依赖 HttpOnly Cookie + 同源 iframe；`file://` 托管不可行（§E4、§E9）。
3. **mTLS 应定位为「设备/网络准入层」，不能替代用户 JWT。** 现有用户身份是 JWT（30 分钟 access + 7 天 refresh，带 `token_version` 吊销），mTLS 提供的是"这台设备是否被允许建立连接"的第二道门。二者叠加才是完整的应用层身份体系。
4. **建议 mTLS 走独立监听（如 8443），浏览器继续走 443。** 避免在浏览器端口强制客户端证书导致 Web 端不可用；nginx 用 `ssl_verify_client optional` + `$ssl_client_verify`/`$ssl_client_fingerprint` 透传给后端，由中间件完成"证书指纹 → 设备/用户"映射。
5. **仓库内已有可复用的 mTLS 参考实现**：下载执行 Supervisor 控制链路（CA + 客户端证书 + `CERT_REQUIRED` + 证书 SHA-256 映射调用方），可直接借鉴其证书校验与身份映射模式（§C8）。
6. **先做 6 项低成本止血再谈 mTLS**：代理头信任、XFF 防伪造、SSE 资源归属校验、OpenAPI 收敛、非必要端口回收、报告预览 Cookie 的 Secure 判定（§4.1）。

---

## 1. 调查范围与方法

| 项 | 说明 |
|---|---|
| 代码范围 | `src/cygnusx/`（api/middleware/core/config/infrastructure）、`frontend/src/`、`deploy/docker/`、根目录 `.env.example`、`Makefile`、`pyproject.toml` |
| 方法 | 静态代码阅读 + 关键符号 grep + 路由装饰器计数；未启动服务、未连接真实数据库 |
| 基线 | 分支 `feat/report-center-ai-linkage`，提交 `b7482e6f` |
| 未覆盖 | 生产环境实际证书、云安全组/防火墙规则、线上 nginx 版本差异（属运维面，代码内只能看到配置模板） |
| 标注约定 | 「设计如此」= 刻意为之，不应转成待办；「缺口」= 与本地客户端目标冲突或存在安全风险 |

---

## 2. 「关注点 × 现状」矩阵

### 2.1 A 组：后端 API 形态

| # | 关注点 | 现状 | 评级 | 代码位置 |
|---|---|---|---|---|
| A1 | 技术栈 | Python 3.11 + FastAPI + SQLAlchemy(asyncpg) + Pydantic v2；uvicorn 启动 | 可复用 | `pyproject.toml:15`；`src/cygnusx/main.py:440-451` |
| A2 | 应用入口 | `create_app()` 工厂 + 模块级 `app = create_app()`；lifespan 内做 DB/沙盒/Agent/知识库初始化 | 可复用 | `src/cygnusx/main.py:440-583` |
| A3 | 进程形态 | 单体 Web（4 workers）+ 独立 Celery worker/beat/flower + RocketMQ worker；长任务 >600s 走 Celery | 设计如此 | `deploy/docker/docker-compose.yml:117`；`deploy/docker/docker-compose.prod.yml:24`；`Makefile:7` |
| A4 | API 版本 | 统一 `/api/v1` 前缀；OpenAPI 版本号来自 `settings.app_version` | 可复用 | `src/cygnusx/main.py:552`；`main.py:447` |
| A5 | 路由注册 | 单一聚合点 `api_router`，按域 `include_router`；工具路由自动发现 | 可复用 | `src/cygnusx/api/v1/router.py:75-184`；`router.py:172-174` |
| A6 | 接口规模 | 约 **677** 个路由装饰器（grep 统计，含 admin 与 tools）；REST 为主 | — | `grep -r "@router.(get|post|put|patch|delete|websocket\|api_route)"` |
| A7 | 协议分布 | **REST + SSE + WebSocket + NDJSON 混合**；SSE/WS 清单见 §2.2 | 需适配 | 见 A8/A9 |
| A8 | SSE 端点 | 聊天、Studio run、报告 Copilot、Research Agent、Goals、MAS、AgentTeams、任务进度、BLAST | 可复用 | `api/v1/chat.py:596`、`:336`、`:726`；`studio.py:1269`；`reports.py:177`；`research_agent.py:97`；`goals.py:128`；`mas.py:81`；`mas_rooms.py:95`；`tasks.py:228`；`tools/blast/api.py:88`；`agentteams.py:1147`、`:1327` |
| A9 | WebSocket 端点 | AI、Cookie、流程监控、任务、沙盒、终端、Studio 终端；**AuthMiddleware 对 WS 一律放行，端点内自鉴权** | 需适配 | `api/v1/ai.py:133`；`cookies.py:80`；`workflow_monitor.py:212`、`:237`；`tasks.py:188`；`sandbox.py:108`；`terminal.py:96`；`studio.py:1176`；`middleware/auth.py:117-119` |
| A10 | 前端调用层 | 单例 axios，`baseURL '/api/v1'`；请求拦截器注入 Bearer；响应拦截器 401 自动刷新并重放 | 可复用 | `frontend/src/api/client.ts:7-13`、`:46-55`、`:84-114` |
| A11 | 前端基址配置 | **硬编码相对路径 `/api/v1`**；dev 由 Vite 代理到 `:8888`（nginx） | **缺口** | `frontend/src/api/client.ts:8`；`frontend/vite.config.ts:21-28` |
| A12 | SSE 鉴权 | 多数走全局 Bearer；WebSocket 用 `?token=<JWT>` 查询参数；Studio 内部 exec 用控制令牌 | 需适配 | `sandbox.py:108-119`；`studio.py:269-277`；`middleware/auth.py:36-52` |
| A13 | 心跳/保活 | 聊天 15s 心跳；报告/Goals/MAS 房间/ BLAST 有周期注释；AgentTeams 用 60s 有界流+前端重连 | 可复用 | `chat.py:54-56`、`:657-659`；`reports.py:246-248`；`goals.py:151-158`；`mas_rooms.py:123-124`；`tools/blast/api.py:106-108` |
| A14 | 断线重连 | 聊天主流式**无自动重连**；AgentHub/MAS 房间有重连逻辑；AgentTeams 结束即重连 | 需适配 | `frontend/src/composables/useChatStream.ts:51-55`、`:83`；`stores/agentHub.ts:800-802`；`stores/masRoom.ts:314-320` |
| A15 | EventSource 例外 | 任务进度卡用浏览器 `EventSource`，**无法携带 Authorization**，默认会 401 | **缺口（已知）** | `frontend/src/components/ai-chat/TaskProgressCard.vue:83-84` |
| A16 | 反向代理 SSE | nginx `/api/` 未显式 `proxy_buffering off`，依赖后端 `X-Accel-Buffering: no`；`proxy_read_timeout 86400` | 可复用 | `deploy/docker/nginx/nginx.prod.conf:86-97`；`tasks.py:256`；`chat.py:711` |

### 2.2 B 组：鉴权与身份体系

| # | 关注点 | 现状 | 评级 | 代码位置 |
|---|---|---|---|---|
| B1 | 认证方案 | **JWT（HS256）为主 + API Key 辅助**；无 OAuth/SSO/OIDC；无 Session-Cookie 登录态 | 可复用 | `core/config.py:196-199`；`core/security.py:61-117` |
| B2 | 登录 | OAuth2 Password 表单（`application/x-www-form-urlencoded`），非 JSON；支持 2FA 挑战态 | 需适配 | `api/v1/auth.py:48-79` |
| B3 | 令牌签发 | access 30 分钟、refresh 7 天；均含 `sub`、`exp`、`type`、`token_version` | 可复用 | `core/security.py:61-106`；`api/v1/auth.py:73-79` |
| B4 | 令牌校验 | 中间件只解码签名/过期；**业务依赖 `CurrentUserId` 再查库校验用户状态与 `token_version`** | 可复用 | `middleware/auth.py:161-171`；`api/deps.py:96-108` |
| B5 | 刷新 | `/api/v1/auth/refresh`；校验 `type=refresh`、用户状态、`token_version`，轮换双令牌 | 可复用 | `api/v1/auth.py:181-193`；`services/auth_service.py:198-225` |
| B6 | 吊销 | 改密/管理员踢下线通过 `users.token_version += 1` 使旧令牌失效（刷新与业务依赖双点校验） | 可复用 | `api/deps.py:100-101`；`services/auth_service.py:215` |
| B7 | API Key | SHA-256 落库、明文仅返回一次、支持 scopes；`X-API-Key` 头；无 scope 限制（`["*"]`）时可访问全部路由 | 可复用 | `middleware/auth.py:125-151`；`services/api_key_service.py:19-49`；`api/v1/auth.py:265-323` |
| B8 | API Key 管理 | 登录后可创建/列出/吊销自己的 Key；**尚无"设备证书/设备注册"概念** | 缺口（mTLS 前置） | `api/v1/auth.py:265-323` |
| B9 | 用户模型 | 单库多用户；`role` 仅 admin/user；`workspace_id`、`lab_group`、`disabled_modules`；**无 tenant_id** | 设计如此 | `infrastructure/database/models/user.py:14-53` |
| B10 | 资源边界 | 由各 Service 按 `current_user_id` 过滤；无统一租户隔离层 | 需逐接口核对 | `api/deps.py:50-90`；各 `application/services/*` |
| B11 | RBAC | `require_roles` / `require_admin` 实时查库；管理端路由挂依赖 | 可复用 | `middleware/rbac.py:18-56` |
| B12 | 模块授权 | `ModuleGateMiddleware` 读 `data/MODULE_LOCKED.yaml`，按用户 `disabled_modules` 返回 403 `MODULE_LOCKED` | 可复用 | `middleware/module_gate.py:44-101` |
| B13 | CORS | `CORSMiddleware`，默认 origins `http://localhost:5173`、`:3000`，`allow_credentials=True` | 设计如此（对原生客户端无影响） | `main.py:453-460`；`core/config.py:202` |
| B14 | CSRF | 无 CSRF token 中间件；认证靠 Authorization 头，天然免 CSRF；仅报告预览用 Cookie 且 `SameSite=strict` | 设计如此 | `api/v1/reports.py:447-455` |
| B15 | 密钥配置 | `Settings` 读 `.env`；Fernet 加密 AI Provider Key；生产强制校验默认密钥/Redis 密码/Bridge 凭证 | 可复用 | `core/config.py:864-900`；`core/security.py:13-44` |
| B16 | 硬编码扫描 | 未发现 `sk-*`/`AKIA*`/私钥块；仅保留 `change-me-in-production` 默认值（生产被拒绝启动） | 通过 | 全仓 grep；`core/config.py:874-876` |
| B17 | 审计 | 写操作落 `audit_logs`（user_id/method/path/resource/status/ip/ua），DB 异常不阻断主请求 | 可复用，需扩展设备维度 | `middleware/audit.py:22-90` |
| B18 | 限流 | 每 IP 滑动窗口 100/60s；RFC1918/回环默认**跳过限流**；`X-Forwarded-For` 取**最左值** | **有缺口** | `core/config.py:664-678`；`middleware/rate_limit.py:35-43`、`:101-107` |
| B19 | 公开路径 | `/health`、`/openapi.json`、登录/注册/刷新、站点配置、工作流监控摄取 | **需收敛** | `middleware/auth.py:17-34`；`main.py:444-451` |

### 2.3 C 组：传输安全现状

| # | 关注点 | 现状 | 评级 | 代码位置 |
|---|---|---|---|---|
| C1 | TLS 终结点 | **nginx 终结**：生产 `listen 443 ssl`，HTTP 80 跳转；应用进程内**无 TLS** | 可复用 | `deploy/docker/nginx/nginx.prod.conf:59-80` |
| C2 | 证书来源 | 宿主机 `/etc/ssl/certs` 只读挂载；证书路径硬编码 `ssl-cert.pem/key`；**仓库无生成/续期脚本**，无 certbot/Caddy/Traefik | 运维缺口 | `deploy/docker/docker-compose.prod.yml:12`；`nginx.prod.conf:77-78` |
| C3 | TLS 版本 | TLS 1.2/1.3；`HIGH:!aNULL:!MD5`；HSTS 1 年 | 可复用 | `nginx.prod.conf:75`、`:79-80` |
| C4 | server_name | `server_name localhost`；按域名/IP 访问需替换证书与 server_name | 需配置 | `nginx.prod.conf:68` |
| C5 | mTLS（面向客户端） | **完全不存在**：nginx 无 `ssl_client_certificate`/`ssl_verify_client`；无私有 CA 材料 | **缺口（主线）** | 全仓 grep 无命中（除下述 C8） |
| C6 | 后端监听 | uvicorn 全部 `--host 0.0.0.0 --port 8000`，仅在容器网络内；宿主 web 端口默认 `127.0.0.1:8000` | 设计如此 | `Dockerfile:161`；`docker-compose.yml:117`、`:120`；`docker-compose.prod.yml:24` |
| C7 | 宿主端口暴露 | nginx `0.0.0.0:8888`；PG/Redis/MinIO/Flower/RocketMQ **默认 127.0.0.1**；生产 PG/Redis/Flower `ports: []` | 设计如此（单机默认安全） | `docker-compose.yml:20`、`:266`、`:296`、`:317`、`:342-343`、`:398`、`:415-417`；`docker-compose.prod.yml:44-54` |
| C8 | 非 HTTP 暴露口 | **Phylo Redis `6379:6379` 绑 0.0.0.0**；SearXNG `8898:8080` 绑 0.0.0.0（生产 override 未覆盖） | **安全隐患** | `deploy/docker/docker-compose.phylo.yml:45-46`；`deploy/docker/docker-compose.searxng.yml:19-20` |
| C9 | 现有 mTLS 参考实现 | 下载执行 Supervisor：客户端 CA+cert+key，强制 `https`；服务端强制 `CERT_REQUIRED` + `TLS>=1.2`，按证书 SHA-256 映射调用方 | **可复用范式** | `infrastructure/download/supervisor_client.py:66-100`；`supervisor_server.py:344-346`、`:384-395`；`core/config.py:49-51`；`.env.example:218-224` |
| C10 | 代理头 | nginx 设置 `X-Forwarded-For/$proxy_add_x_forwarded_for`、`X-Real-IP`、`X-Forwarded-Proto`；uvicorn 命令**未显式** `--proxy-headers/--forwarded-allow-ips` | **有缺口** | `nginx.prod.conf:90-93`；`docker-compose.yml:117`；`Dockerfile:161` |
| C11 | 内网假设 | `/tracks/` 仅放行 RFC1918；文档明确 DB/Redis/8000/5555 不对外 | 设计如此 | `nginx.prod.conf:142-157`；`docs/分析中心_Celery_Snakemake_跨服务器部署实施方案.md:98`、`:164-171` |
| C12 | SSE 代理缓冲 | 无 `proxy_buffering off`；依赖 `X-Accel-Buffering: no`（nginx 识别，其他反代不一定） | 可复用（有隐含前提） | `nginx.prod.conf:86-97`；`chat.py:711` 等 |

### 2.4 D 组：部署与配置形态

| # | 关注点 | 现状 | 评级 | 代码位置 |
|---|---|---|---|---|
| D1 | 部署方式 | Docker Compose（主栈 + prod/worker/cross-web/cross-worker/pgvector/phylo/searxng）；无 K8s 实际编排（仅规划文档） | 设计如此 | `deploy/docker/docker-compose*.yml`；`docs/report/07_K8s大规模部署方案.md`（规划） |
| D2 | 配置层 | 统一 `Settings`（pydantic-settings，读 `.env`）+ `data/CygnusX.yaml` 注册中心 + 各域 YAML | 可复用 | `core/config.py:40-900`；`.env.example`；`data/CygnusX.yaml` |
| D3 | 引导信息分发 | **不存在**：无服务器地址/CA/证书指纹/设备注册的分发或发现机制；登录后才可创建 API Key | **缺口（阻断）** | `api/v1/auth.py:265-323`；全仓无 bootstrap/enrollment 模块 |
| D4 | 公开配置面 | 未登录可读 `/api/v1/site-settings`、`/api/v1/platform/config`（站点文案/注册开关），不含连接引导 | 可复用（可扩展） | `api/v1/site_settings.py:34`；`api/v1/platform_config.py:12` |
| D5 | 版本/健康 | `/health` 返回 version/git_sha/build_time，可用于客户端兼容性握手 | 可复用 | `main.py:571-578` |
| D6 | 客户端工程 | **仓库内无 Tauri/Electron/CLI 客户端工程**；仅 MCP Server 与 `scripts/` 运维 CLI | 缺口（新建） | 全仓 grep 无 Tauri/Electron 配置 |
| D7 | 配置开关散落 | 主体集中；但 nginx 证书路径、`/tracks/` 白名单、CORS 默认值为硬编码/环境变量混合 | 需收敛 | `nginx.prod.conf:77-78`、`:153-156`；`core/config.py:202` |

### 2.5 E 组：客户端接入就绪度

| # | 关注点 | 现状 | 评级 | 代码位置 |
|---|---|---|---|---|
| E1 | 客户端必需 API | 登录/刷新/me/api-keys、users、projects、files、tasks/runs/flows、chat、reports、notifications、sandbox/studio/terminal | 可直接复用 | `router.py:80-170`；`auth.py:48-193` |
| E2 | 仅 Web 内部 API | `studio/internal/*`、`agent-teams/consultations|introspection`、`workflow-monitor` 摄取、downloads supervisor、admin/* | 客户端不应依赖 | `middleware/auth.py:36-52`；`router.py:106-147` |
| E3 | 浏览器存储 | token 存 `localStorage`（access/refresh），WS/SSE 亦从 localStorage 取 token | 需适配（改用系统钥匙串） | `client.ts:48`、`:59-69`；`stores/auth.ts:22-46`；`useAIWebSocket.ts:29` |
| E4 | Cookie 依赖 | 报告预览：`cygnusx_report_session` HttpOnly + `cygnusx_report_context`；同源 iframe 加载 `preview-content` | **阻断（桌面壳）** | `api/v1/reports.py:447-455`；`frontend/src/utils/reportPreviewSession.ts:7-16`；`views/ReportViewerView.vue:104-105`、`:276` |
| E5 | OAuth 跳转 | 无 OAuth/SSO；登录仅账号密码 + 可选 TOTP | 简化客户端 | `views/LoginView.vue:213-224`；全仓无 OIDC 回调 |
| E6 | 同源相对 URL | REST 用 `/api/v1`；WS 用 `window.location.host` 拼 `ws(s)://`；多个 fetch 用相对路径 | **阻断** | `client.ts:8`；`useSandboxWebSocket.ts:18-21`；`useTerminalWebSocket.ts:19-23`；`useWorkflowMonitorWebSocket.ts:13-16`；`api/goals.ts:109-111` |
| E7 | EventSource | 任务进度卡使用 `EventSource`，无法带 Authorization，默认 401 | **缺口（Web 已存在）** | `TaskProgressCard.vue:83-84` |
| E8 | 上传/下载 | 分块上传 + 预签名上传（FormData）；下载以 Blob + `a[download]` 为主（约 40 处）；打印用 object URL iframe | 需适配 | `composables/useChunkUpload.ts:124`、`:184-197`；`usePresignedUpload.ts:84`、`:104`；`views/FilesView.vue:376-378`；`utils/blobPrint.ts:5-20` |
| E9 | 前端托管 | Vite 未设 `base`，产物绝对路径；`createWebHistory()`；nginx SPA fallback | **阻断 file://** | `frontend/vite.config.ts:43-44`；`src/router/index.ts:495`；`nginx.prod.conf:165-169` |
| E10 | 跨域 iframe 交互 | JBrowse 访问 `contentDocument`、报告预览校验 `event.origin==='null'` | 需适配 | `views/BioTools/JBrowseViewer.vue:312-323`、`:535`；`ReportViewerView.vue:121` |
| E11 | Service Worker/PWA | 无 SW、无 manifest、无 IndexedDB 实际调用 | 无影响 | 全仓检索 |
| E12 | mTLS 改造点 | 见 §2.6 工作量分级 | 小/中/大 | — |

### 2.6 E 组补充：mTLS 改造工作量分级

| 级别 | 改造项 | 具体位置 | 说明 |
|---|---|---|---|
| **小（配置级）** | nginx 增加独立 mTLS 监听 + `ssl_client_certificate`/`ssl_verify_client optional` | `deploy/docker/nginx/nginx.prod.conf` | 浏览器口不动；8443 口强制或可选客户端证书 |
| **小** | 透传 `$ssl_client_verify` / `$ssl_client_fingerprint` / `$ssl_client_s_dn` | 同上 `location /api/` | 后端据此做设备身份判定 |
| **小** | uvicorn 显式 `--proxy-headers --forwarded-allow-ips=<nginx 网段>` | `Dockerfile:161`、`docker-compose.yml:117`、`docker-compose.prod.yml:24` | 修正 scheme/客户端 IP |
| **中（新增中间件）** | 设备证书指纹 → 设备/用户映射中间件；审计写入设备 ID | 新增 `middleware/client_cert.py`；`middleware/audit.py` 扩展 | 证书仅证明"设备"，用户仍由 JWT 证明 |
| **中** | 设备注册/吊销 API + 数据表 | 新增 `api/v1/devices.py` + Alembic 迁移 | 与现有 `token_version` 吊销模型并列 |
| **中** | WebSocket 通道校验客户端证书 | `middleware/auth.py:117-119` 之前或端点内 | TLS 层已完成 mTLS，WS 复用同一连接 |
| **大（架构/产品）** | 客户端工程、证书分发/轮换、系统钥匙串、自动更新、离线策略 | 全新目录（如 `client/`） | 与后端解耦，独立交付 |
| **大** | 报告预览去 Cookie 化（桌面壳） | `reports.py` + `ReportViewerView.vue` | 改为 Bearer/token-in-header 的预览通道，或客户端内置同源代理 |

---

## 3. 请求流转链路（文字版）

### 3.1 浏览器现状（生产）

```
浏览器
  │  HTTPS 443（同源，静态资源 + API）
  ▼
nginx（TLS 终结、限流 10r/s、HSTS、/tracks 内网白名单）
  │  proxy_pass http://web:8000（HTTP，容器网络）
  │  X-Forwarded-For / X-Real-IP / X-Forwarded-Proto
  ▼
uvicorn（4 workers，无进程内 TLS）
  │  TraceContext → RateLimit → Audit → CookieRequired → Auth → ModuleGate → CORS
  ▼
AuthMiddleware：Bearer 解码 → request.state.user_id（不查库）
  ▼
路由（/api/v1/*）→ CurrentUserId 依赖（查库校验 status + token_version）
  ▼
application/services（150+ 用例）
  ▼
PostgreSQL / Redis / MinIO / Celery（长任务 reconcile-only）
```

关键实现位置：
- TLS 终结与转发：`deploy/docker/nginx/nginx.prod.conf:66-97`
- 中间件注册顺序：`src/cygnusx/main.py:453-491`（后注册=更外层）
- JWT 解码：`src/cygnusx/middleware/auth.py:153-173`
- 用户状态/版本复核：`src/cygnusx/api/deps.py:96-108`
- 业务与存储：`src/cygnusx/application/services/`、`src/cygnusx/infrastructure/database/`

### 3.2 本地客户端目标态（建议）

```
本地客户端（Tauri/Electron）
  │  HTTPS 8443（mTLS：客户端证书 + 服务端证书校验）
  ▼
nginx mTLS listener（ssl_verify_client optional/on + CRL）
  │  X-Client-Verify / X-Client-Fingerprint / X-Client-Subject
  ▼
uvicorn
  │  RateLimit（修正后的真实 IP）→ Audit（含设备指纹）
  │  ClientCertMiddleware（证书 → 设备注册表校验；吊销即拒）
  ▼
AuthMiddleware（Bearer JWT，用户身份）
  ▼
同一套 /api/v1 业务路由（零改动复用）
```

要点：
- **双身份**：mTLS = 设备准入；JWT = 用户身份。任一缺失都不放行受保护业务。
- **浏览器共存**：443 口保持现状；8443 口专供客户端，或 443 口 `ssl_verify_client optional` 并在后端按 UA/证书双模式判定。推荐前者，隔离清晰、回滚容易。
- **WebSocket/SSE**：TLS 连接层已含客户端证书，无需在 URL 里再传证书；但 JWT 仍需按现有方式携带（WS 建议改为 `Sec-WebSocket-Protocol` 或首帧鉴权，避免 query token 落日志）。

### 3.3 SSE / WebSocket 链路

| 链路 | 握手/鉴权 | 心跳 | 断线重连 | 位置 |
|---|---|---|---|---|
| 聊天 SSE | `POST /api/v1/chat/stream` + Bearer | 15s `: heartbeat` | 前端无自动重连 | `chat.py:596`、`:54-56`、`:657-659`；`useChatStream.ts:51-55` |
| 报告 Copilot SSE | `POST /reports/{id}/copilot/stream` + Bearer + 报告绑定 | 周期注释 | 复用 AgentChat 重试 | `reports.py:177`、`:246-248` |
| Studio run SSE | `POST /studio/sessions/{id}/run` + Bearer | 无显式 | 前端按流处理 | `studio.py:1269` |
| Studio 内部 exec | `X-CygnusX-Studio-Control-Token` | — | — | `studio.py:269-290`；`auth.py:38-43` |
| 沙盒 WS | `?token=<JWT>` + 用户活性校验 | 前端/后端协议内 | 前端重连 | `sandbox.py:108-119`；`useSandboxWebSocket.ts:18-21` |
| 终端 WS | `?token=<JWT>` | 前端 30s ping | 前端重连 | `terminal.py:96-103`、`:157-160`；`useTerminalWebSocket.ts:43-47` |
| AgentTeams SSE | Bearer + room/case 归属（房间流有校验） | 60s 有界流 | 结束立即重连 | `agentteams.py:1147`、`:1327`；`AgentTeamsRoomView.vue:1499-1509` |
| MAS 房间 SSE | Bearer（**未见房间成员校验**） | 1s 轮询 + heartbeat | 前端重连 | `mas_rooms.py:95-140`；`stores/masRoom.ts:314-320` |
| 任务进度 SSE | Bearer（**未见任务归属校验**） | 无显式 | EventSource 默认 | `tasks.py:228-253`；`TaskProgressCard.vue:83-84` |

### 3.4 异步任务链路（客户端必须理解）

- 提交：`POST /api/v1/tasks` → `TaskService.submit` 九步链 → Celery/RocketMQ。
- 进度：SSE `/tasks/{id}/progress` 或 WS `/tasks/{id}/ws`；状态落 Redis Pub/Sub。
- 长任务 >600s：Web 进程不直接执行，Celery reconcile-only（`AGENTS.md` §3）。
- 客户端影响：需要实现"提交 → 订阅进度 → 断线补偿（重连后拉状态）"的状态机，不能只依赖单次 SSE。

---

## 4. 风险与缺口清单

### 4.1 低成本止血点（先做，1-2 天量级）

| # | 问题 | 证据 | 建议 |
|---|---|---|---|
| Q1 | uvicorn 未显式信任 nginx 代理头，`request.url.scheme` 在 HTTPS 下仍为 `http` | `Dockerfile:161`；`docker-compose.yml:117`；`nginx.prod.conf:93`；`reports.py:453` | 加 `--proxy-headers --forwarded-allow-ips=<nginx 容器网段>`；验证 `request.url.scheme == https` |
| Q2 | `X-Forwarded-For` 取最左值 + nginx 追加而非覆盖 → 客户端可伪造 `127.0.0.1` 绕过限流/审计 | `rate_limit.py:35-43`、`:105-107`；`audit.py:33-38`；`nginx.prod.conf:92` | nginx 改为 `proxy_set_header X-Forwarded-For $remote_addr`；后端仅在可信代理来源时采信 XFF |
| Q3 | 任务进度 SSE / MAS 房间 SSE 缺少资源归属校验 | `tasks.py:228-253`；`mas_rooms.py:95-140` | 增加 task/room 归属或成员校验；若"房间全员可见"是产品设计，写入文档并显式豁免 |
| Q4 | `/openapi.json` 生产仍公开（只关了 docs/redoc） | `main.py:444-451`；`middleware/auth.py:20` | 生产设 `openapi_url=None` 或纳入管理员鉴权 |
| Q5 | Phylo Redis / SearXNG 绑定 0.0.0.0 | `docker-compose.phylo.yml:45-46`；`docker-compose.searxng.yml:19-20` | 改为 `127.0.0.1:port` 或 `ports: []` + 内部网络 |
| Q6 | 报告预览 Cookie 的 `Secure` 依赖错误的 scheme 判定 | `reports.py:453`；Q1 | 修正代理头后自动修复；或在生产强制 `secure=True` |

### 4.2 阻断客户端接入（P0）

| # | 阻断项 | 证据 | 影响 |
|---|---|---|---|
| P0-1 | **无引导信息分发机制**：服务器地址、CA、客户端证书、指纹均无下发/注册入口 | `api/v1/auth.py:265-323`；全仓无 enrollment 模块 | 客户端无法安全地"第一次连上服务器" |
| P0-2 | **前端 API/WS 基址硬编码同源** | `client.ts:8`；`useSandboxWebSocket.ts:18-21` 等 | 桌面壳无法指向远端服务器，除非注入本地反向代理 |
| P0-3 | **报告预览依赖 HttpOnly Cookie + 同源 iframe** | `reports.py:447-455`；`reportPreviewSession.ts:7-16`；`ReportViewerView.vue:276` | 桌面 WebView 自定义协议下 Cookie/同源判定失效，报告预览不可用 |
| P0-4 | **`file://` 托管不可行**：Vite 绝对路径 + history 路由 | `vite.config.ts:43-44`；`router/index.ts:495` | 必须用自定义协议或本地静态服务器 + `base:'./'` + hash 路由 |
| P0-5 | **EventSource 无 Authorization** | `TaskProgressCard.vue:83-84` | 任务进度在客户端（以及当前 Web 的该组件）不可用；需改 fetch 流或后端支持 query token |
| P0-6 | **无客户端工程与证书生命周期** | 全仓无 Tauri/Electron；无 CA/CRL 管理 | 需新建客户端仓库与签发/轮换/吊销流程 |

### 4.3 安全隐患（P1）

| # | 风险 | 证据 | 说明 |
|---|---|---|---|
| P1-1 | 客户端口无 mTLS：当前只有 TLS + 密码/JWT | `nginx.prod.conf` 无 `ssl_verify_client` | 任何拿到账号密码的人可在任意设备登录；无设备准入 |
| P1-2 | WebSocket token 走 query | `sandbox.py:108-119`；`terminal.py:96-103` | nginx 访问日志用 `$uri` 不含 query，但上游/代理/浏览器历史可能记录；建议改协议头或首帧 |
| P1-3 | 限流可被 XFF 伪造绕过 | 见 Q2 | 公开部署下可被用于暴力破解/资源耗尽 |
| P1-4 | 默认信任全部 RFC1918 跳过限流 | `config.py:671-678` | 校园网/内网客户端天然无限流；对公开分发场景需重审 |
| P1-5 | 生产证书手工挂载、无自动续期、`server_name localhost` | `docker-compose.prod.yml:12`；`nginx.prod.conf:68`、`:77-78` | 到期即全站不可用；域名访问易证书不匹配 |
| P1-6 | 非必要端口 0.0.0.0 | 见 Q5 | Phylo Redis 无密码暴露风险高 |
| P1-7 | API Key 默认 `["*"]` 全权限 | `api_key_service.py:49`；`middleware/auth.py:75-79` | 客户端若用 API Key 代替登录，须强制最小 scope |
| P1-8 | 认证中间件只解码不查库，吊销依赖业务依赖 | `middleware/auth.py:161-171`；`deps.py:96-108` | 未挂 `CurrentUserId` 的端点可能接受已吊销 token；建议统一收敛 |

### 4.4 体验降级（P2）

| # | 问题 | 证据 | 影响 |
|---|---|---|---|
| P2-1 | 聊天 SSE 无自动重连 | `useChatStream.ts:51-55`、`:83` | 客户端需自建重连/补偿 |
| P2-2 | 登录后固定回 `/`，未消费 `redirect` | `client.ts:77-79`；`LoginView.vue:213-224` | 桌面壳需自行处理登录后导航 |
| P2-3 | 上传/下载强依赖浏览器能力 | `useChunkUpload.ts:124`；`FilesView.vue:376-378`；`blobPrint.ts:5-20` | 客户端需替换为系统文件对话框/流式落盘 |
| P2-4 | 多个 iframe/跨文档交互 | `JBrowseViewer.vue:312-323`；`ReportViewerView.vue:121` | 桌面 WebView 安全模型不同，需逐项回归 |
| P2-5 | 反向代理依赖 `X-Accel-Buffering` | `chat.py:711` 等 | 若客户端前置自建代理，需同样处理或关闭缓冲 |
| P2-6 | 2FA 为交互式 TOTP | `api/v1/auth.py:132-155` | 客户端需实现挑战态 UI 与重试/限流提示 |

### 4.5 「设计如此」清单（不要转成待办）

| 项 | 原因 |
|---|---|
| PostgreSQL/Redis/MinIO/Flower 默认绑 `127.0.0.1`，生产 `ports: []` | 单机安全默认，刻意不对外 |
| CORS 只允许 localhost 开发源 | 浏览器同源部署；原生客户端不受 CORS 约束 |
| 无 OAuth/SSO | 当前产品定位为私有化部署，账号密码 + 2FA 足够；客户端反而更简单 |
| Bearer 头认证而非 Cookie | 对非浏览器客户端最友好；也天然免 CSRF |
| `/tracks/` 仅 RFC1918 | JBrowse 大文件直读的临时方案，已在注释中标明公网/多租户需改鉴权代理 |
| `studio/internal/*`、`agent-teams/introspection` 自鉴权 | 内部服务间调用，不应暴露给客户端 |
| 长任务 >600s 走 Celery | 架构约束，客户端只需轮询/订阅状态 |

---

## 5. 演进建议：mTLS 主线 vs 叠加 WireGuard/Tailscale

### 5.1 判断

**主线采用「应用层 mTLS（独立监听）+ 现有 JWT」；WireGuard/Tailscale 作为可选叠加层，不作为产品前提。**

理由：
1. **复用度最高**：客户端直连现有 `/api/v1`，677 个端点零改动；mTLS 只发生在 TLS 层与一个轻量中间件。
2. **身份分层清晰**：证书证明设备，JWT 证明用户；审计可同时记录 `device_fingerprint + user_id`，满足"谁、用哪台设备、做了什么"。
3. **可控的吊销粒度**：设备证书可单独吊销（CRL/短周期证书），不影响用户其他设备；比共享 API Key 或 SSH 密钥更细。
4. **浏览器共存成本低**：独立 8443 口或 `ssl_verify_client optional`，Web 端零感知。
5. **WireGuard/Tailscale 的定位**：适合运维/内网加固（例如把 8443 只暴露在组网内），但每台终端要装组网客户端、信任边界含第三方控制面；对"公开分发的桌面客户端"是额外负担，且不能替代应用层用户鉴权。

### 5.2 两种 mTLS 落地形态对比

| 形态 | 做法 | 优点 | 代价 | 适用 |
|---|---|---|---|---|
| **A. 独立 mTLS 监听（推荐）** | nginx 新增 `listen 8443 ssl` + `ssl_verify_client on`，443 保持浏览器现状 | 隔离彻底、回滚容易、浏览器零风险 | 客户端需固定 8443；多一个端口要放行 | 本地客户端产品化 |
| **B. 同端口 optional** | 443 加 `ssl_verify_client optional`，后端按 `$ssl_client_verify` 分流 | 单端口、客户端/浏览器同入口 | 需处理 495/496 错误页；后端判定分支增多；浏览器误配风险 | 过渡期/小范围 |
| **C. 应用层自签 mTLS** | FastAPI/uvicorn 直接加载 CA 与证书 | 少一层代理 | uvicorn 证书热更新/CRL 弱；与现有 nginx 架构重复 | 不推荐 |

### 5.3 mTLS 威胁模型（说清楚"解决什么/不解决什么"）

| 威胁 | mTLS 是否解决 | 说明 |
|---|---|---|
| 未授权设备连接 API | ✅ | 无合法证书在 TLS 握手即被拒 |
| 账号密码泄露后的异地登录 | ⚠️ 部分 | 攻击者若无设备证书仍被拒；但若同时窃取证书则失效，需配合设备绑定/风控 |
| 用户越权访问他人数据 | ❌ | 仍由 JWT + Service 层资源校验负责（见 Q3） |
| 传输窃听/篡改 | ✅（TLS 已具备） | mTLS 在此基础上增加客户端身份 |
| 服务端被冒充 | ✅ | 客户端校验服务端证书 + 可选指纹固定（pinning） |
| 内部人员/运维滥用 | ⚠️ | 需审计 + 最小权限 + 证书吊销流程 |

### 5.4 证书与引导设计要点

1. **私有 CA**：离线根 CA + 在线中间 CA；中间 CA 签设备证书（短周期，如 90 天）。
2. **注册流程**：用户登录（JWT）→ 调用 `POST /api/v1/devices/enroll`（需 2FA/管理员审批可选）→ 服务端签发设备证书 → 客户端写入系统钥匙串。
3. **绑定关系**：`device_id ↔ user_id ↔ cert_fingerprint ↔ status(active/revoked)`；吊销即时写入 CRL/DB，中间件每次校验状态。
4. **引导信息**：`GET /api/v1/client/bootstrap`（公开但限流）返回 `{api_base, mtls_host, mtls_port, ca_pem, ca_fingerprint, min_client_version}`；CA 指纹用于首次信任建立（TOFU + 人工核对）。
5. **证书轮换**：到期前 30 天自动续签（仍走 JWT 鉴权 + 设备私钥证明）；吊销列表缓存 Redis，TTL 短。
6. **审计**：`audit_logs` 增加 `device_id`、`cert_fingerprint`、`client_version` 字段。

---

## 6. 分阶段实施手册（API 兼容层 → mTLS 引导 → 客户端 MVP）

### 阶段 0：止血与基线（1-2 天）

| 任务 | 文件 | 验收 |
|---|---|---|
| 修代理头信任 | `Dockerfile:161`、`docker-compose.yml:117`、`docker-compose.prod.yml:24` | HTTPS 请求下 `request.url.scheme == "https"`；预览 Cookie 带 `Secure` |
| 修 XFF 伪造 | `nginx.prod.conf:92`、`rate_limit.py:35-43`、`audit.py:33-38` | 伪造 `X-Forwarded-For` 不再绕过限流；审计 IP 为真实来源 |
| SSE 归属校验 | `tasks.py:228`、`mas_rooms.py:95` | 他人 task/room 返回 403/404 |
| OpenAPI 收敛 | `main.py:444-451` | 生产 `/openapi.json` 不可匿名访问 |
| 端口回收 | `docker-compose.phylo.yml:45-46`、`docker-compose.searxng.yml:19-20` | 宿主不再监听 0.0.0.0:6379/8898 |
| 回归 | `make lint && make type-check && uv run pytest tests/unit -q -m "not quarantine"` | 全绿 |

### 阶段 1：API 兼容层（1-2 周）

| 任务 | 说明 | 验收 |
|---|---|---|
| 统一基址配置 | 前端所有相对 URL 收口到 `apiBaseUrl`/`wsBaseUrl` 配置（env/运行时注入） | Web 行为不变；客户端可指向远端 |
| 流式鉴权统一 | SSE 全部支持 `Authorization` 头（fetch 流）；WS 支持 `Sec-WebSocket-Protocol` 或首帧 token，保留 query 兼容 | 客户端无需把 token 放 URL |
| 登录/刷新适配 | 明确 `application/x-www-form-urlencoded` 登录；2FA 挑战态；refresh 轮换 | 客户端可完成完整登录链路 |
| 引导端点 | 新增 `GET /api/v1/client/bootstrap`（公开/限流） | 返回 API 基址、mTLS 端点、CA、指纹、最低版本 |
| 设备注册骨架 | `devices` 表 + `POST/GET/DELETE /api/v1/devices` | 登录后可登记/吊销设备（先不签证书） |

### 阶段 2：mTLS 引导（2-3 周）

| 任务 | 说明 | 验收 |
|---|---|---|
| nginx mTLS 监听 | 8443 + `ssl_verify_client on` + CRL + 透传指纹头 | 无证书握手失败；有证书可进入 `/api/` |
| ClientCert 中间件 | 校验 `X-Client-Fingerprint` 与设备表状态；注入 `request.state.device_id` | 吊销设备立即 403；审计含设备维度 |
| 证书签发/轮换 | CA 脚本（离线根 + 在线中间）、`enroll`/`renew` 端点、私钥仅客户端持有 | 完整生命周期演练通过 |
| 浏览器隔离验证 | 443 口回归全部 Web 功能 | Web 无回归 |

### 阶段 3：客户端 MVP（3-6 周）

| 任务 | 说明 | 验收 |
|---|---|---|
| 壳与路由 | Tauri/Electron 自定义协议或本地静态服务；`base:'./'` + hash 路由 | 无 `file://` 依赖 |
| 令牌存储 | 系统钥匙串（Keychain/Credential Manager/libsecret），不落 localStorage | 重启后免登录、登出清理 |
| 报告预览 | 客户端本地代理同源化，或后端新增 Bearer 预览通道 | 报告预览可用 |
| 文件能力 | 系统文件对话框、分块/预签名上传、下载落盘 | 上传/下载/打印回归 |
| 流与重连 | 统一 SSE/WS 客户端，指数退避 + 断线补偿 | 弱网演练通过 |
| 更新与引导 | 首次引导（服务器地址/CA 指纹核对）、自动更新、版本握手 | 新设备 5 分钟内可完成接入 |

---

## 7. 待确认决策与保留意见

### 7.1 需要产品/运维确认

1. **客户端形态**：桌面 GUI（Tauri 推荐，体积小、系统 WebView）/ Electron / CLI？决定打包、钥匙串、自动更新方案。
2. **分发范围**：只给自己用 / 小范围分发 / 未来公开？决定是否必须做设备注册审批、证书吊销、自动更新签名。
3. **浏览器是否长期共存**：若是，必须采用独立 mTLS 端口或 optional 模式（§5.2）。
4. **证书生命周期归属**：谁运维私有 CA？是否接受"根 CA 离线保管"的运维成本？
5. **内网/组网叠加**：是否已有 WireGuard/Tailscale 基础设施？若有，可先以组网限制 8443 暴露面，再上 mTLS。

### 7.2 保留意见（调查中无法 100% 确认）

| 项 | 说明 |
|---|---|
| 线上实际证书与 server_name | 仓库只有模板；生产是否已替换为正式域名证书需运维确认 |
| 云 LB/安全组 | 代码内看不到；若前置云 LB 终结 TLS，则 nginx mTLS 方案需改为 LB 侧客户端证书或 TCP 透传 |
| `mas_rooms` 房间可见性语义 | 当前代码无成员校验；需产品确认"房间是否全员可见"，再决定是补校验还是文档化豁免 |
| `workflow_monitor` 公开摄取 | 生产校验器在 `workflow_monitor_enabled` 时强制 token；若关闭监控则路径仍公开但无数据写入，风险可接受 |
| uvicorn 代理头默认行为 | 未显式配置；不同版本默认信任范围不同，需以实际镜像版本实测确认（本报告按"未显式配置=不可依赖"处理） |

---

## 8. 证据索引（按主题）

**入口与路由**
- `src/cygnusx/main.py:440-583`（应用工厂/中间件/路由/健康检查）
- `src/cygnusx/api/v1/router.py:75-184`（路由聚合）
- `deploy/docker/Dockerfile:161`、`deploy/docker/docker-compose.yml:117`、`deploy/docker/docker-compose.prod.yml:24`、`Makefile:7`（uvicorn 启动）

**鉴权与身份**
- `src/cygnusx/core/security.py:61-117`（JWT 签发/解码）
- `src/cygnusx/core/config.py:196-202`（JWT/CORS 配置）
- `src/cygnusx/middleware/auth.py:17-173`（公开路径/API Key/Bearer/WS 放行）
- `src/cygnusx/api/deps.py:50-108`（CurrentUserId 与 token_version 校验）
- `src/cygnusx/api/v1/auth.py:48-193`、`:265-323`（登录/刷新/API Key）
- `src/cygnusx/application/services/auth_service.py:132-225`（登录/刷新实现）
- `src/cygnusx/application/services/api_key_service.py:19-102`（API Key 哈希与 scope）
- `src/cygnusx/infrastructure/database/models/user.py:14-53`（用户模型）
- `src/cygnusx/middleware/rbac.py:18-56`、`module_gate.py:44-101`（RBAC/模块门）

**传输与部署**
- `deploy/docker/nginx/nginx.prod.conf:59-97`、`:142-169`（TLS/代理/内网白名单/SPA）
- `deploy/docker/docker-compose.prod.yml:7-54`（443/证书挂载/生产端口关闭）
- `deploy/docker/docker-compose.yml:20`、`:120`、`:266`、`:296`、`:317`、`:342-343`、`:398`、`:415-417`（端口绑定）
- `deploy/docker/docker-compose.phylo.yml:45-46`、`docker-compose.searxng.yml:19-20`（0.0.0.0 暴露）
- `src/cygnusx/infrastructure/download/supervisor_server.py:344-395`、`supervisor_client.py:66-100`（现有 mTLS 范式）
- `src/cygnusx/core/config.py:49-51`、`.env.example:218-224`（mTLS 配置项）

**前端适配面**
- `frontend/src/api/client.ts:7-13`、`:46-71`、`:84-114`（axios/令牌/刷新）
- `frontend/vite.config.ts:21-28`、`:43-44`（代理/构建 base）
- `frontend/src/router/index.ts:495`（history 路由）
- `frontend/src/utils/reportPreviewSession.ts:7-16`、`views/ReportViewerView.vue:104-105`、`:276`（预览 Cookie/iframe）
- `frontend/src/composables/useSandboxWebSocket.ts:18-21`、`useTerminalWebSocket.ts:19-23`、`useWorkflowMonitorWebSocket.ts:13-16`（WS 相对主机）
- `frontend/src/components/ai-chat/TaskProgressCard.vue:83-84`（EventSource 无鉴权）
- `frontend/src/views/LoginView.vue:213-224`（登录后固定跳转）

**风险控制**
- `src/cygnusx/middleware/rate_limit.py:35-43`、`:101-107`（XFF/可信网段）
- `src/cygnusx/middleware/audit.py:33-38`、`:70-90`（审计 IP/写入）
- `src/cygnusx/api/v1/reports.py:447-455`（预览 Cookie）
- `src/cygnusx/api/v1/tasks.py:228-253`、`api/v1/mas_rooms.py:95-140`（SSE 归属）

---

## 9. 附：路由域分布（约 677 个装饰器，Top 域）

| 域 | 装饰器数 | 代表文件 |
|---|---|---|
| AgentTeams | 49 | `api/v1/agentteams.py` |
| Studio | 41 | `api/v1/studio.py` |
| Chat | 38 | `api/v1/chat.py` |
| Files | 26 | `api/v1/files.py` |
| Datasets | 25 | `api/v1/datasets.py` |
| BLAST | 23 | `tools/blast/api.py` |
| Admin Skills | 23 | `api/v1/admin/skills.py` |
| Reports | 18 | `api/v1/reports.py` |
| Docs | 17 | `api/v1/docs.py` |
| Research Delivery | 16 | `api/v1/research_delivery.py` |
| Users | 15 | `api/v1/users.py` |
| MCP / MCP Builder | 15 / 15 | `api/v1/mcp.py`、`mcp_builder.py` |
| Auth | 14 | `api/v1/auth.py` |
| MAS | 13 | `api/v1/mas.py` |
| AI | 13 | `api/v1/ai.py` |

> 计数为静态 grep 结果，含条件注册与 WebSocket 装饰器，用于量级评估，不作为精确契约数。

---

**报告结束。本调查未修改任何业务代码。**
