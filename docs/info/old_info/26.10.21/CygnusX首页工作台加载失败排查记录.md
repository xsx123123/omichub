# CygnusX 首页工作台加载失败排查记录

时间：2026-10-21 16:00～16:05（Asia/Shanghai）。

## 现象与直接原因

首页“最近项目 / 运行任务 / 最近报告”同时显示暂时无法加载。实际请求 `/api/v1/projects`、`/api/v1/tasks?status=running&limit=5`、`/api/v1/reports?page=1&page_size=5` 均返回 **502**，健康检查也为 502。

`cygnusx-web` 的 Uvicorn 子进程在导入应用路由时，经 `core/logging.py:setup_logging()` 初始化 JSON 文件 sink，抛出：

```text
PermissionError: [Errno 13] Permission denied: '/app/logs/cygnusx.json.log'
```

该路径实际挂载自 `/data/omichub/logs/app/cygnusx.json.log`：文件属主 **0:0（root）**、权限 **644**，Web 配置及实际进程均以 **1000:1000** 运行，因此不能追加写入。Web 容器虽处于 running，但子进程反复启动失败、健康检查 unhealthy；Nginx 静态页面可访问，API upstream 不可用，导致三个卡片同时报错。Beat 也因同一个日志文件的权限错误反复重启。

首页加载逻辑按接口失败如实展示错误，没有本次样式改动造成请求损坏的证据。**尚未确定哪个进程创建或改变了旧文件的属主**，不能据此归咎于某次发布、轮转或其他操作。

## 已执行的恢复

保留非 root 运行方式，不更改容器用户或放宽日志权限。由于当前宿主用户无免密 chown 权限，利用其对日志父目录的正常管理权限，将旧 JSON 日志按轮转方式完整保留为：

```text
/data/omichub/logs/app/cygnusx.json.permission-backup-20261021T080305Z.log
```

随后由 UID 1000 重新创建原路径，属主恢复为 **1000:1000**、权限仍为 **644**。未删除旧日志、未修改业务数据、未修改源代码。Uvicorn 子进程自动重试、Beat 自动重启后恢复，无需手动重建或重启服务。

后续运维应以服务用户运行诊断脚本，避免在共享日志目录重新创建 root 属主文件。仓库已有 `make docker-fix-permissions` 与 `make docker-runtime-dirs` 维护入口；使用时应核实 `DATA_ROOT`、`PUID`、`PGID` 与实际部署一致。本轮仅处理已确认异常的单个日志文件。

## 实际恢复验证

本轮使用运行中的 Nginx/Web/数据库验证，**未 mock 项目、任务或报告 API**。

| 检查 | 结果 |
| --- | --- |
| Web / Beat Docker 健康检查 | 均为 healthy |
| `/health` | 200 |
| 登录态 `GET /api/v1/projects` | 200，30 项 |
| 登录态 `GET /api/v1/tasks?status=running&limit=5` | 200，5 项 |
| 登录态 `GET /api/v1/tasks?status=queued&limit=5` | 200，5 项 |
| 登录态 `GET /api/v1/reports?page=1&page_size=5` | 200，5 项 |
| 实际首页浏览器渲染 | 最近项目 3 条、运行/排队任务 5 条、最近报告 3 条；无加载失败卡片 |
| 点击首页“刷新” | 四个数据请求再次全部 200，无加载失败卡片 |
| 浏览器 pageerror | 0 |
| 日志文件恢复后复查 | 属主 1000:1000，权限 644，可写 |

诊断认证使用服务端签发的 5 分钟临时令牌，仅保留于内存，不写文件、不打印；浏览器测试仅阻止与故障无关的欢迎词 LLM 请求，避免额外推理调用。

本地证据位于 `evidence/home-visual-20261021/`：

- `api-outage-log-permission-repair.json`：权限修复前后与备份位置。
- `api-outage-live-verification.json`：实际接口及浏览器结果。
- `workbench-live-recovered.png`：恢复后的工作台截图。

本次无需新增测试或重跑构建，因为没有修改项目源码或依赖；通过实际故障链路及恢复行为验证修复效果。
