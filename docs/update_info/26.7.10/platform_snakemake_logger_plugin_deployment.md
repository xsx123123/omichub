# OmicHub Snakemake Logger Plugin 部署接入说明

日期：2026-07-10

## 1. 插件来源与版本要求

OmicHub 当前流程监控依赖 Snakemake logger 插件：

- 远程仓库：`https://github.com/xsx123123/JZ_Tools`
- 安装子目录：`src/logger_plugin`
- Python 包名：`snakemake-logger-plugin-rich-loguru`
- Snakemake logger entrypoint：`rich_loguru`
- 最低版本：`>=0.2.1`

注意：插件必须安装在执行 `snakemake` 命令的同一个 Python 环境中。否则即使系统里能 import 插件，Snakemake CLI 仍可能找不到 logger entrypoint。

## 2. 平台部署改动

平台 Dockerfile 已在构建阶段从 GitHub 子目录安装插件：

```dockerfile
RUN /app/.venv/bin/python -m pip install --no-cache-dir "snakemake-logger-plugin-rich-loguru @ git+https://github.com/xsx123123/JZ_Tools.git@${SNAKEMAKE_LOGGER_PLUGIN_REF}#subdirectory=src/logger_plugin"
```

构建完成后会立即校验安装版本，低于 `0.2.1` 会让镜像构建失败。

worker 容器的 `PATH` 已调整为优先使用 `/app/.venv/bin/snakemake`，确保 Snakemake 与插件处于同一 venv：

```yaml
PATH=/app/.venv/bin:/home/zj/miniconda3/envs/snakemake/bin:/home/zj/miniconda3/bin:...
SNAKEMAKE_MONITOR_LOGGER=rich_loguru
```

宿主 conda 路径仍保留在 `PATH` 中，供 Snakemake `--use-conda` 创建和复用流程环境。

## 3. 构建参数

默认从仓库 `main` 分支安装插件。生产环境建议固定 tag 或 commit：

```bash
export SNAKEMAKE_LOGGER_PLUGIN_REF=v0.2.1
```

如果远程没有 tag，也可以使用 commit hash。

## 4. 必需环境变量

`.env` 中至少配置一个摄取 token：

```bash
WORKFLOW_MONITOR_INGEST_TOKEN=replace-with-long-random-token
```

worker 启动时会自动导出：

```bash
OMICHUB_WORKFLOW_MONITOR_TOKEN=${WORKFLOW_MONITOR_INGEST_TOKEN}
```

也可以直接配置：

```bash
OMICHUB_WORKFLOW_MONITOR_TOKEN=replace-with-long-random-token
```

平台后端会把 `OMICHUB_WORKFLOW_MONITOR_TOKEN` 作为 `WORKFLOW_MONITOR_INGEST_TOKEN` 的别名使用。生产环境启用流程监控时 token 为空会拒绝启动。

## 5. 任务运行时配置

任务提交时，平台会在任务工作目录生成 `monitor_config.yaml`：

```yaml
project_name: "<task_id>"
omichub_monitor_url: "http://web:8000/api/v1/workflow-monitor/events"
omichub_monitor_token: "${OMICHUB_WORKFLOW_MONITOR_TOKEN}"
omichub_task_id: "<task_id>"
omichub_flow_id: "<flow_id>"
omichub_user_id: "<user_id>"
omichub_monitor_sign_requests: true
omichub_monitor_signing_key: "${OMICHUB_WORKFLOW_MONITOR_TOKEN}"
omichub_monitor_encrypt_payload: false
omichub_monitor_tls_verify: true
```

真实 token 不写入任务目录，只通过 worker 环境变量由插件解析。

Snakemake 启动命令会自动追加：

```bash
--logger rich_loguru --config monitor_conf=/path/to/monitor_config.yaml
```

## 6. 安全说明

当前默认链路提供：

- Bearer token 鉴权：防止未授权客户端写入监控事件。
- HMAC-SHA256 签名：后端校验 `X-OmicHub-Signature`，防止请求内容被篡改，并限制 timestamp 时间偏差。

这不是传输加密。若 worker 到 web 不在可信 Docker 内网或内网链路上，生产环境应使用 HTTPS。若未来需要 HTTP 链路上也隐藏日志内容，需要同时启用插件的 AES-GCM payload 加密，并在后端增加 envelope 解密。

## 7. 重建与验证

依赖和 Dockerfile 已变化，必须重建镜像：

```bash
docker compose -f deploy/docker/docker-compose.yml build --build-arg SNAKEMAKE_LOGGER_PLUGIN_REF=${SNAKEMAKE_LOGGER_PLUGIN_REF:-main}
docker compose -f deploy/docker/docker-compose.worker.yml build --build-arg SNAKEMAKE_LOGGER_PLUGIN_REF=${SNAKEMAKE_LOGGER_PLUGIN_REF:-main}
```

验证 worker 内插件版本和 logger 名称：

```bash
docker exec omichub-worker python -c "from importlib.metadata import version; print(version('snakemake-logger-plugin-rich-loguru'))"
docker exec omichub-worker snakemake --help | grep -i logger
```

验证实际任务时，监控页面应能收到 `omichub.workflow_event.v1` 事件，并按 `task_id` 更新进度、当前 rule 和错误信息。
