# 本地客户端接入 — Part 4 回填稿（确认问题 / 保留意见 / 行动顺序）

> 用途：直接粘贴回活文档《本地客户端加密接入：调查阶段实现计划》的 Part 4。
> 依据：`docs/info/26.10.29/CygnusX本地客户端加密接入_仓库现状调查报告.md`（只读调查，未改动任何代码）。
> 核对日期：2026-10-29。

## Part 4 报告核对结论与渐进集成方案

### 4.1 确认的问题

| # | 问题 | 证据（文件:行号） | 结论强度 |
|---|---|---|---|
| C1 | 无"首次连接"引导：服务器地址、CA、客户端证书、指纹均无分发/注册入口 | 全仓无 enrollment 模块；`api/v1/auth.py:265-323` 仅有 API Key | 代码确认，阻断 |
| C2 | 前端 API/WS 基址硬编码同源（`/api/v1`、`window.location.host`） | `frontend/src/api/client.ts:8`；`useSandboxWebSocket.ts:18-21`、`useTerminalWebSocket.ts:19-23`、`useWorkflowMonitorWebSocket.ts:13-16` | 代码确认，阻断 |
| C3 | 报告预览依赖 HttpOnly Cookie + 同源 iframe | `api/v1/reports.py:447-455`；`utils/reportPreviewSession.ts:7-16`；`ReportViewerView.vue:104-105`、`:276` | 代码确认，阻断（客户端） |
| C4 | `file://` 托管不可行：Vite 绝对路径 + history 路由 | `frontend/vite.config.ts:43-44`；`router/index.ts:495` | 代码确认，阻断 |
| C5 | EventSource 无法带 Authorization，任务进度 SSE 在非浏览器环境不可用 | `TaskProgressCard.vue:83-84`；`tasks.py:228-253` | 代码确认，阻断 |
| C6 | 无客户端工程、无证书生命周期（CA/签发/轮换/吊销） | 全仓无 Tauri/Electron；仅下载执行器有参考实现 `infrastructure/download/supervisor_server.py:344-346`、`supervisor_client.py:66-79` | 代码确认，阻断 |
| C7 | 客户端口无 mTLS，仅 TLS + 密码/JWT | `nginx.prod.conf` 无 `ssl_verify_client` | 代码确认，安全隐患 |
| C8 | uvicorn 未显式信任代理头 → HTTPS 下 `request.url.scheme` 仍为 `http`，预览 Cookie 的 `Secure` 恒为 false | `deploy/docker/Dockerfile:161`；`docker-compose.yml:117`；`docker-compose.prod.yml:23-26`；`reports.py:453` | 代码确认，安全隐患 |
| C9 | XFF 取最左值 + nginx 追加 → 可伪造 `127.0.0.1` 绕过限流/审计（可信网段默认含全部 RFC1918） | `middleware/rate_limit.py:35-43`、`:105-107`；`middleware/audit.py:33-38`；`nginx.prod.conf:92`；`core/config.py:671-678` | 代码确认，安全隐患 |
| C10 | 任务进度 SSE / MAS 房间 SSE 仅校验登录、不校验资源归属 | `api/v1/tasks.py:228-253`；`api/v1/mas_rooms.py:95-140` | 代码确认，安全隐患 |
| C11 | 生产仍公开 `/openapi.json`（只关 docs/redoc） | `main.py:444-451`；`middleware/auth.py:20` | 代码确认，安全隐患 |
| C12 | Phylo Redis / SearXNG 绑 `0.0.0.0` | `docker-compose.phylo.yml:45-46`；`docker-compose.searxng.yml:19-20` | 代码确认，安全隐患 |
| C13 | WebSocket token 走 query 参数 | `api/v1/sandbox.py:108-119`；`terminal.py:96-103` | 代码确认，安全隐患（中） |
| C14 | API Key 默认 `["*"]` 全权限 | `application/services/api_key_service.py:49`；`middleware/auth.py:75-79` | 代码确认，安全隐患 |
| C15 | AuthMiddleware 只解码不查库，吊销仅在 `CurrentUserId` 依赖生效 | `middleware/auth.py:153-173`；`api/deps.py:96-108` | 代码确认，安全隐患（低-中） |

### 4.2 核对后的判断修正（避免把"设计如此"当待办）

1. **不是缺口**：PostgreSQL/Redis/MinIO/Flower 绑 `127.0.0.1`、生产 `ports: []`；CORS 仅开发源；无 OAuth/SSO；Bearer 头而非 Cookie；`/tracks/` 限 RFC1918；`studio/internal/*` 自鉴权。这些不进待办。
2. **E 组浏览器依赖的归因**：真正的浏览器耦合只有两类——(a) 同源推导（基址/WS/Cookie 路径）；(b) 报告预览的同源 iframe + Cookie。`localStorage` 只用于 token 存储，属"可替换"而非"会断"。→ 客户端鉴权定为 **token-in-header**，不复用 Cookie。
3. **报告本身无缺格**：A–E 五组均已覆盖；仅"云 LB / 线上证书 / 房间可见性 / uvicorn 默认代理头"四处需外部信息，已列入保留意见。
4. **低成本止血点确认存在**：C8、C9、C11、C12 均为配置级修复（1-2 天），且 C8 同时修复 C6/Q6 的 `Secure` Cookie 问题，应前置到阶段 0。

### 4.3 保留意见

| # | 项 | 为什么保留 | 解除条件 |
|---|---|---|---|
| R1 | 线上证书与 `server_name` | 仓库只有模板，`nginx.prod.conf:68` 写死 `localhost` | 运维提供生产证书/域名清单 |
| R2 | 云 LB / 安全组 | 代码不可见；若 LB 终结 TLS，则 mTLS 需改为 LB 侧客户端证书或 TCP 透传 | 提供网络拓扑 |
| R3 | `mas_rooms` 房间可见性语义 | 无成员校验，可能是"全员可见"的产品设计 | 产品确认；再决定补校验或文档化豁免 |
| R4 | `workflow_monitor` 公开摄取 | 启用时强制 token；关闭时路径公开但无写入 | 确认生产开关状态 |
| R5 | uvicorn 代理头默认信任范围 | 版本相关，未显式配置不可依赖 | 以实际镜像版本实测（`--proxy-headers --forwarded-allow-ips`） |
| R6 | 客户端形态/分发范围 | 决定是否必须做设备审批、吊销、更新签名 | 产品拍板（见 7.1） |

### 4.4 行动顺序

**原则：先止血（配置级）→ 再做 API 兼容层（不动协议）→ 再上 mTLS 引导（新增监听）→ 最后客户端 MVP。任何一步不依赖后一步。**

| 阶段 | 内容 | 入口文件 | 完成判据 |
|---|---|---|---|
| **阶段 0 止血（1-2 天）** | C8 代理头、C9 XFF、C10 SSE 归属、C11 OpenAPI、C12 端口 | `Dockerfile:161`、`docker-compose.yml:117`、`nginx.prod.conf:92`、`rate_limit.py:35-43`、`audit.py:33-38`、`tasks.py:228`、`mas_rooms.py:95`、`main.py:444-451`、`docker-compose.phylo.yml:45-46`、`docker-compose.searxng.yml:19-20` | HTTPS 下 scheme=https、Secure Cookie 生效；伪造 XFF 无效；他人资源 403/404；`/openapi.json` 非匿名可读；宿主不再监听 0.0.0.0:6379/8898；`make lint && make type-check && pytest tests/unit -m "not quarantine"` 全绿 |
| **阶段 1 API 兼容层（1-2 周）** | 基址收口（C2）、流式鉴权统一（C5/C13）、登录/2FA/refresh 适配、`GET /api/v1/client/bootstrap`、`devices` 表骨架 | `frontend/src/api/client.ts:8`、各 `use*WebSocket.ts`、`TaskProgressCard.vue:83`、`api/v1/auth.py`、新增 `api/v1/client.py`/`api/v1/devices.py` | Web 行为不变；客户端可完成完整登录 + SSE + WS；bootstrap 可返回 API 基址/CA/指纹/最低版本 |
| **阶段 2 mTLS 引导（2-3 周）** | 8443 独立监听 + `ssl_verify_client on` + CRL；ClientCert 中间件（指纹→设备表）；证书签发/轮换；443 回归 | `deploy/docker/nginx/`（新 server 块）、新增 `middleware/client_cert.py`、`alembic/versions/*devices*`、CA 脚本 | 无证书握手失败；吊销即时 403；审计含 `device_id/cert_fingerprint`；浏览器 443 零回归；参考实现对照 `download/supervisor_server.py:344-346` |
| **阶段 3 客户端 MVP（3-6 周）** | 壳与路由（C4）、钥匙串存 token（不复用 Cookie）、报告预览改造（C3）、文件能力、流与重连、更新与引导 | 新客户端仓库；`reportPreviewSession.ts` 客户端分支；`reports.py` 新增 Bearer 预览通道 | 无 `file://` 依赖；重启免登录；报告预览可用；弱网重连通过；新设备 5 分钟内完成接入 |

**阶段 0 之后必须先做决策**（阻塞阶段 1 的设计）：客户端形态（Tauri 优先）、分发范围（决定设备审批强度）、浏览器是否长期共存（决定 mTLS 用独立端口还是 optional）。

### 4.5 一句话结论

后端 API 复用度高（677 个端点、统一 `/api/v1`、Bearer 鉴权），真正的改造量集中在**引导/证书生命周期**与**前端同源耦合**；mTLS 应作为"设备准入"叠加在现有 JWT"用户身份"之上，独立 8443 监听是风险最低的落地形态。
