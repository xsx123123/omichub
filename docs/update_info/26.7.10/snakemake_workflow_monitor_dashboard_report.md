# OmicHub Snakemake 流程监控面板可行性与实施报告

日期：2026-07-10

## 1. 结论

可以在当前 OmicHub 平台中添加原生监控面板，用于实时监测所有 Snakemake 分析流程的运行进度、规则执行、失败日志和错误告警。

推荐方案不是简单把 Grafana 页面嵌入 OmicHub，而是把你现有的 `snakemake-logger-plugin-rich-loguru` 作为 Snakemake 事件采集器，在 OmicHub 后端增加一层“流程监控摄取与聚合服务”，再由前端提供统一的“流程监控面板”。这样普通用户可以在平台内看自己的任务，管理员可以看全平台任务，Grafana/Loki 仍然保留为底层日志检索和排障工具。

当前平台已经具备大部分基础能力：

- 后端：FastAPI + SQLAlchemy + PostgreSQL + Redis + Celery。
- 任务系统：已有 `tasks` 表，包含 `status`、`progress`、`error_message`、`logs`。
- 实时推送：已有 Redis Pub/Sub 和 `/api/v1/tasks/{task_id}/ws` WebSocket。
- 执行体系：已有 Snakemake 执行器和 Celery Worker。
- 前端：已有任务中心、任务详情、进度条、实时日志页。

缺口主要有三点：

- 当前 Snakemake 执行器用 `process.communicate()` 等待流程结束后才回填 stdout/stderr，不是真正的运行中实时日志。
- 当前插件把事件推到 Loki，但 OmicHub 还没有接收、关联、聚合这些事件的服务。
- 插件事件需要稳定映射到 OmicHub 的 `task_id`，否则只能按 `project_name` 粗粒度查看。

## 2. 现状梳理

### 2.1 OmicHub 当前任务执行链路

当前分析任务链路如下：

1. 前端在分析中心提交任务。
2. `TaskService.submit()` 创建任务 ID、工作目录和流程配置文件。
3. 任务写入数据库，状态从 `pending` 进入 `queued`。
4. Celery 投递 `run_snakemake`。
5. Worker 调用 `LocalSnakemakeExecutor._execute()` 执行 Snakemake。
6. 执行完成后，Celery 将 stdout/stderr 的最后 200 行写入任务日志。
7. 状态变为 `success` 或 `failed`，失败时写入 `error_message`。
8. 前端任务详情页轮询 `/tasks/{task_id}`，并通过 `/tasks/{task_id}/ws` 接收日志推送。

关键代码位置：

- `src/omichub/application/services/task_service.py`
- `src/omichub/infrastructure/celery_app/tasks/analysis.py`
- `src/omichub/infrastructure/execution/local.py`
- `src/omichub/infrastructure/cache/pubsub.py`
- `src/omichub/api/v1/tasks.py`
- `frontend/src/views/TaskDetailView.vue`
- `frontend/src/views/TasksView.vue`

### 2.2 当前 Snakemake 执行器的实时性限制

`LocalSnakemakeExecutor` 现在使用：

```python
stdout, stderr = await process.communicate()
```

这意味着平台只有在 Snakemake 进程结束后才能拿到 stdout/stderr。虽然任务详情页已经有 WebSocket，但 Snakemake 运行中的逐行日志和进度不会实时进入该 WebSocket。

相比之下，`BinaryExecutor` 已经实现了逐行流式读取 stdout/stderr，并通过 `on_log`、`on_progress` 回调实时写库和推送。这说明 OmicHub 已经有适合实时执行器的架构模式，Snakemake 侧可以复用类似设计，或者直接接入你的 logger 插件事件流。

### 2.3 logger_plugin 当前能力

你写的插件位于：

`/home/zj/zj_code_libarary/jz_tools/src/logger_plugin`

插件包名：

`snakemake-logger-plugin-rich-loguru`

当前版本：

`0.2.1`

核心能力：

- 作为 Snakemake logger plugin 接入。
- 使用 Rich 优化终端输出。
- 使用 Loguru 保存本地日志。
- 将结构化日志异步推送到 Grafana Loki。
- 自动解析 Snakemake 事件字段：
  - `Snakemake_Rule`
  - `Snakemake_JobId`
  - `Event_Type`
  - `Shell_Command`
  - `progress_percent`
  - `progress_details`
- 自动识别 `Job stats` 和 `Finished jobid` 来计算流程进度。
- 支持 `project_name` 隔离项目。
- 支持钉钉、飞书 Webhook 完成/失败通知。
- 使用 Queue + Worker Thread 异步推送，避免阻塞 Snakemake 主进程。

插件当前推送的是 Loki push payload，结构大致为：

```json
{
  "streams": [
    {
      "stream": {
        "project_id": "project_name",
        "job": "snakemake",
        "level": "INFO"
      },
      "values": [
        [
          "timestamp_ns",
          "{\"msg\":\"...\",\"progress_percent\":42.5,\"progress_details\":\"17/40 ...\"}"
        ]
      ]
    }
  ]
}
```

这个 payload 已经足够支撑 OmicHub 原生监控面板。

## 3. 推荐总体架构

推荐采用“插件采集 + OmicHub 摄取 + Redis 实时推送 + PostgreSQL 持久摘要 + 前端监控面板”的架构。

### 3.1 数据流

```text
Snakemake
  |
  | --logger rich_loguru
  v
logger_plugin
  |
  | Loki-compatible HTTP push
  v
OmicHub FastAPI 摄取端点
  |
  | 解析 task_id / rule / jobid / progress / error
  v
Redis Hash / Stream / PubSub
  |
  | WebSocket
  v
前端流程监控面板

同时：

OmicHub 摄取端点
  |
  | 摘要写入
  v
PostgreSQL tasks / workflow_monitor_events
```

### 3.2 为什么不只用 Grafana

Grafana/Loki 适合管理员排障和日志查询，但不适合作为 OmicHub 用户级监控的唯一入口：

- 用户权限难以和 OmicHub 账号、任务归属完全打通。
- 普通用户不应暴露 Loki 查询能力。
- OmicHub 任务详情、报告、数据路径、饼干计费等上下文都在平台内。
- 前端任务中心已经有任务视图，只缺实时事件源。

因此建议：

- Loki/Grafana 保留：用于管理员深度排障、日志检索、性能分析。
- OmicHub 原生面板新增：用于用户和管理员日常监控。

## 4. 插件与 OmicHub 的对接方式

### 4.1 最小插件改造方案

最小成本方案是让 OmicHub 实现 Loki Push API 兼容端点。

插件当前逻辑是：

- 如果 `loki_url` 不是以 `/loki/api/v1/push` 结尾，就自动拼接 `/loki/api/v1/push`。

因此 OmicHub 可以新增：

```text
POST /api/v1/workflow-monitor/loki/api/v1/push
```

Worker 中配置：

```yaml
loki_url: "http://web:8000/api/v1/workflow-monitor"
project_name: "<task_id>"
```

插件实际会推送到：

```text
http://web:8000/api/v1/workflow-monitor/loki/api/v1/push
```

这种方式可以不改插件主逻辑，OmicHub 后端接收 Loki payload 后自行解析。

### 4.2 更稳妥的长期方案

长期建议给插件增加第二个 sink：

```yaml
omichub_monitor_url: "http://web:8000/api/v1/workflow-monitor/events"
omichub_monitor_token: "${OMICHUB_WORKFLOW_MONITOR_TOKEN}"
task_id: "<task_id>"
flow_id: "<flow_id>"
user_id: "<user_id>"
```

插件同时支持：

- `loki_url`：继续推 Loki。
- `omichub_monitor_url`：推 OmicHub 原生事件。

这样 payload 可以直接使用业务字段，不必兼容 Loki 的 streams/values 结构，后端解析也更简单。

### 4.3 当前优先建议

第一期建议走 Loki-compatible endpoint，因为它对现有插件侵入最小。

第二期再给插件补充 `omichub_monitor_url` 原生推送能力。

## 5. task_id 关联设计

监控面板能否准确工作，关键在于每条 Snakemake 事件必须能关联到 OmicHub 的 `task_id`。

### 5.1 推荐做法

平台提交任务时自动生成监控配置，禁止普通用户手动决定最终推送地址。

推荐写入每个任务工作目录：

```yaml
loki_url: "http://web:8000/api/v1/workflow-monitor"
project_name: "<task_id>"
omichub_task_id: "<task_id>"
omichub_flow_id: "<flow_id>"
omichub_user_id: "<user_id>"
```

第一期插件只读取 `loki_url` 和 `project_name` 也够用，因为 `project_name` 可以直接等于 `task_id`。

第二期插件支持 `omichub_task_id` 后，可以把 `task_id` 写入 Loki JSON 内容和 label。

### 5.2 不建议直接使用用户填写的 loki_url

当前 RNA-seq 和 ATAC-seq 表单的高级参数中有 `loki_url`。生产环境不建议把这个字段作为最终监控推送地址直接交给用户控制，原因是：

- Worker 能访问内网服务，用户可控 URL 存在 SSRF 风险。
- 监控数据入口应该由平台统一管理。
- 错误 URL 会导致监控丢失。

建议策略：

- UI 中可以保留“自定义外部 Loki”作为管理员能力。
- 普通用户提交任务时，平台强制注入内部 OmicHub 监控地址。
- 如需同时推外部 Loki，由后端安全白名单控制。

## 6. 后端实施方案

### 6.1 新增模块

建议新增：

```text
src/omichub/api/v1/workflow_monitor.py
src/omichub/application/schemas/workflow_monitor.py
src/omichub/application/services/workflow_monitor_service.py
src/omichub/infrastructure/cache/workflow_monitor_pubsub.py
```

可选新增：

```text
src/omichub/infrastructure/database/models/workflow_monitor.py
src/omichub/infrastructure/database/repositories/workflow_monitor_repository.py
```

### 6.2 API 设计

建议接口：

```text
POST /api/v1/workflow-monitor/loki/api/v1/push
```

用途：

- 接收插件发送的 Loki push payload。
- 由 Worker 内网调用。
- 使用共享 token 鉴权。

```text
GET /api/v1/workflow-monitor/overview
```

用途：

- 获取监控总览。
- 普通用户只返回自己的任务。
- 管理员可查看全平台。

查询参数：

```text
status=running|failed|success|all
flow_id=rna_seq
user_id=<uuid>  # 仅管理员
keyword=<task name / flow / rule / error>
```

```text
GET /api/v1/workflow-monitor/tasks/{task_id}/events
```

用途：

- 获取某个任务的最近事件。
- 支持分页或 `since`。

```text
GET /api/v1/workflow-monitor/tasks/{task_id}/summary
```

用途：

- 获取任务实时摘要。
- 包含当前 rule、完成 job 数、总 job 数、最近错误、最后事件时间。

```text
WS /api/v1/workflow-monitor/ws
```

用途：

- 管理员全局监控。
- 普通用户只推送本人任务事件。

```text
WS /api/v1/workflow-monitor/tasks/{task_id}/ws
```

用途：

- 单任务监控详情页。
- 可以复用现有 `/tasks/{task_id}/ws`，也可以新增专门的结构化事件通道。

### 6.3 事件 DTO

建议 OmicHub 内部标准事件格式：

```json
{
  "task_id": "uuid",
  "flow_id": "rna_seq",
  "user_id": "uuid",
  "project_name": "uuid-or-readable-name",
  "timestamp": "2026-07-10T12:00:00+08:00",
  "level": "info",
  "message": "Finished jobid: 12 (Rule: trim_fastq)",
  "source": "snakemake",
  "rule": "trim_fastq",
  "job_id": 12,
  "event_type": "JobFinished",
  "shell_command": null,
  "progress_percent": 42.5,
  "progress_details": "17/40",
  "raw": {}
}
```

### 6.4 数据持久化策略

不建议把所有 Snakemake 高频事件都完整写入 `tasks.logs`，原因是：

- `tasks.logs` 是 JSON 字段，适合保存最近日志摘要，不适合无限增长的事件流。
- 高频日志会放大数据库写入压力。
- 结构化查询不方便。

建议分层：

#### Redis

用于实时状态：

```text
workflow_monitor:task:{task_id}:summary
workflow_monitor:task:{task_id}:events
workflow_monitor:global
```

内容：

- 最新进度。
- 最新 rule/job。
- 最近 200 到 1000 条事件。
- 全局运行中任务集合。

#### PostgreSQL

第一期可以只更新 `tasks.progress`、`tasks.error_message`、`tasks.logs` 的最近摘要。

第二期新增表：

```text
workflow_monitor_events
```

字段建议：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | UUID | 主键 |
| task_id | UUID | 关联 tasks.id |
| flow_id | String | 流程 ID |
| user_id | UUID | 任务归属 |
| project_name | String | 插件项目名 |
| timestamp | DateTime | 事件时间 |
| level | String | info/warning/error/critical |
| rule | String | Snakemake rule |
| job_id | Integer | Snakemake job id |
| event_type | String | JobStarted/JobFinished/ShellCommand/Error |
| message | Text | 清洗后的消息 |
| progress_percent | Float | 0 到 100 |
| progress_details | String | 例如 17/40 |
| shell_command | Text | 可选 |
| raw | JSONB | 原始字段 |

索引建议：

```text
idx_workflow_events_task_time(task_id, timestamp desc)
idx_workflow_events_flow_time(flow_id, timestamp desc)
idx_workflow_events_level_time(level, timestamp desc)
idx_workflow_events_rule(rule)
```

#### tasks 表摘要字段

可以后续扩展：

```text
last_rule
last_job_id
last_monitor_at
progress_detail
monitor_source
```

如果不想改 `tasks` 表，第一期也可以把这些摘要存在 Redis。

### 6.5 进度同步策略

插件推来的 `progress_percent` 是 0 到 100，而 OmicHub `tasks.progress` 是 0 到 1。

摄取时转换：

```text
task.progress = progress_percent / 100
```

状态推断建议：

- 收到第一条有效事件：若任务是 `queued`，推进到 `running`。
- `progress_percent >= 100` 且出现 `Complete log(s):`：可标记为候选完成，但最终状态仍以 Celery 进程 returncode 为准。
- 收到 `ERROR`、`CRITICAL`、`WorkflowError`：更新 `error_message` 摘要，但不要立即把任务标记为 `failed`，除非 Celery 确认 returncode 非 0。

原因：

- Snakemake 运行中可能输出 warning/error 风格信息，但最终仍成功。
- Celery 是流程生命周期的权威来源。
- logger 插件是观测信号，不应单独决定最终任务状态。

### 6.6 WebSocket 推送

摄取端收到事件后发布 Redis Pub/Sub：

```text
workflow_monitor:global
workflow_monitor:user:{user_id}
workflow_monitor:task:{task_id}
task_logs:{task_id}
```

其中 `task_logs:{task_id}` 可以继续给现有任务详情页使用，保证不改前端也能看到日志。

前端监控面板使用：

```text
WS /api/v1/workflow-monitor/ws
```

任务详情页可以继续使用：

```text
WS /api/v1/tasks/{task_id}/ws
```

也可以新增结构化 tab 使用：

```text
WS /api/v1/workflow-monitor/tasks/{task_id}/ws
```

### 6.7 鉴权

摄取端点不能使用普通用户 JWT，因为它由 Worker/插件调用。

建议新增环境变量：

```text
WORKFLOW_MONITOR_INGEST_TOKEN=<random-long-secret>
WORKFLOW_MONITOR_ENABLED=true
```

插件配置中携带 token。若第一期不改插件，可通过 URL query 或内部网络隔离临时解决，但生产建议尽快改插件支持 Header：

```text
Authorization: Bearer <token>
```

如果走 Loki-compatible endpoint 且插件暂不支持 header，可以采用：

```yaml
loki_url: "http://web:8000/api/v1/workflow-monitor?token=<secret>"
```

但这种方式会因为插件简单拼接路径而变得不稳定。更推荐插件增加 `headers` 或 `omichub_monitor_token`。

## 7. Snakemake 执行器改造点

### 7.1 必须显式启用 logger 插件

当前 `LocalSnakemakeExecutor` 命令中没有 logger 参数：

```text
snakemake -s <snakefile> --cores <n> ...
```

需要增加：

```text
--logger rich_loguru
```

或：

```text
--logger rich_loguru
```

注意：插件 README 使用 `rich-loguru`，但 `pyproject.toml` entry point 是 `rich_loguru`。当前平台统一使用 `rich_loguru`，该名称来自插件 pyproject.toml 的 snakemake.loggers entry point。

建议新增配置：

```python
snakemake_logger: str = "rich_loguru"
snakemake_monitor_enabled: bool = True
```

执行器中按开关追加：

```python
if self.settings.snakemake_monitor_enabled:
    cmd.extend(["--logger", self.settings.snakemake_logger])
```

### 7.2 监控配置注入

推荐在 `TaskService.submit()` 创建任务时生成：

```text
{work_dir}/monitor_config.yaml
```

内容：

```yaml
loki_url: "http://web:8000/api/v1/workflow-monitor"
project_name: "<task_id>"
omichub_task_id: "<task_id>"
omichub_flow_id: "<flow_id>"
omichub_user_id: "<user_id>"
```

然后执行 Snakemake 时追加：

```text
--config monitor_conf={work_dir}/monitor_config.yaml
```

当前插件会手动解析 CLI 中的 `--config monitor_conf=...`，这是比把监控字段混入分析配置更稳妥的方式。

原因：

- 不污染 RNAFlow/ATACFlow 原始 analysis YAML。
- 避免底层流程对未知字段敏感。
- 每个任务都有稳定独立的监控配置。

### 7.3 本地日志目录修正

当前代码默认：

```python
SNAKEMAKE_LOG_ROOT = /logs/snakemake
```

Worker compose 当前挂载：

```text
/data/omichub/logs/snakemake:/logs
```

这会让实际日志进入：

```text
/logs/snakemake
```

对应宿主：

```text
/data/omichub/logs/snakemake/snakemake
```

建议二选一修正：

方案 A：

```yaml
- /data/omichub/logs/snakemake:/logs/snakemake
```

方案 B：

```yaml
- OMICHUB_SNAKEMAKE_LOG_DIR=/logs
```

更推荐方案 A，使注释、代码默认值和挂载路径一致。

### 7.4 插件可靠性补强

当前插件使用 daemon worker thread 推送 Loki，进程退出时可能存在队列尚未 flush 完的风险。

建议插件增加：

- `close()` 或 `stop()` 方法。
- `atexit` flush。
- 在 Snakemake 完成事件后 `queue.join()` 等待短暂收尾。
- 推送失败计数和本地 fallback 文件。

这不是第一期必须项，但生产环境建议补。

## 8. 前端监控面板设计

### 8.1 路由与导航

建议新增路由：

```text
/workflow-monitor
```

导航位置：

- 主导航中放在“任务中心”附近。
- 名称：`流程监控`
- 图标：建议使用图表、脉冲、终端类图标。

也可以把它作为任务中心的一个 tab：

```text
/tasks?view=monitor
```

考虑到全局监控和任务列表功能不同，推荐独立页面。

### 8.2 页面结构

监控面板建议分为 5 个区域：

#### 顶部指标栏

展示：

- 运行中任务数。
- 今日完成任务数。
- 今日失败任务数。
- 平均进度。
- 最近 10 分钟错误数。
- 最久运行任务。

#### 筛选栏

筛选：

- 状态：全部、运行中、失败、完成。
- 流程：RNA-seq、ATAC-seq 等。
- 用户：管理员可见。
- 关键词：任务名、rule、错误信息。
- 时间范围：最近 1 小时、6 小时、24 小时、7 天。

#### 运行中任务表

字段：

- 任务名称。
- 流程。
- 用户。
- 状态。
- 总进度。
- 当前 rule。
- 完成 job 数。
- 最近事件时间。
- 最近错误摘要。
- 操作：查看详情、查看报告、查看日志。

#### 实时事件流

展示最近事件：

- 时间。
- 任务。
- Rule。
- Job ID。
- Level。
- Message。

支持只看 warning/error。

#### 错误聚合面板

展示：

- 近期失败任务。
- 高频错误消息。
- 失败 rule 排名。
- 一键跳转任务详情。

### 8.3 任务详情增强

在 `TaskDetailView.vue` 中新增 tab：

```text
Snakemake 事件
```

内容：

- 当前 rule。
- 当前进度。
- job 完成列表。
- rule 级别 timeline。
- shell command 折叠展示。
- warning/error 快速过滤。

原有“实时日志”保留，新增结构化视图不替代纯日志。

### 8.4 前端状态管理

建议新增：

```text
frontend/src/stores/workflowMonitor.ts
frontend/src/composables/useWorkflowMonitorWebSocket.ts
frontend/src/api/workflowMonitor.ts
frontend/src/views/WorkflowMonitorView.vue
```

WebSocket 事件类型：

```ts
type WorkflowMonitorEvent =
  | { type: 'task_snapshot'; task: WorkflowTaskSnapshot }
  | { type: 'event'; event: WorkflowEvent }
  | { type: 'summary'; summary: WorkflowMonitorSummary }
  | { type: 'error'; detail: string }
  | { type: 'pong' }
```

### 8.5 UI 风格

该页面属于运维和分析生产工具，应保持密度高、信息清楚、少装饰。

建议：

- 使用表格、状态徽标、细进度条、事件列表。
- 颜色克制：蓝色表示运行中，绿色完成，红色失败，黄色告警。
- 不做营销式大卡片和大 hero。
- 重点保证长日志、长路径、长 rule 名不会撑破布局。

## 9. 权限模型

### 9.1 普通用户

只能查看：

- 自己提交的任务。
- 自己任务的实时事件。
- 自己任务的错误日志。

### 9.2 管理员

可以查看：

- 全平台任务。
- 所有用户的运行中任务。
- 全局错误聚合。
- Worker 节点和队列健康状态。
- 可选：外部 Loki/Grafana 跳转链接。

### 9.3 摄取端点

只允许：

- 内网 Worker 调用。
- 携带共享 token。
- 可选限制来源网段。

不能允许前端用户直接调用摄取端点。

## 10. 部署与环境配置

### 10.1 Worker 环境

需要确认 Snakemake 环境中安装插件：

```bash
pip install -e /home/zj/zj_code_libarary/jz_tools/src/logger_plugin
```

或打包后安装：

```bash
pip install snakemake-logger-plugin-rich-loguru
```

由于 Worker 当前优先使用宿主 conda：

```text
/home/zj/miniconda3/envs/snakemake/bin
```

插件必须安装到这个环境里，而不是 OmicHub Web 镜像的 `.venv` 中。

### 10.2 网络

Worker 和 Web 已经通过 `omichub_net` 互通。Worker 可以访问：

```text
http://web:8000
```

监控推送地址建议使用：

```text
http://web:8000/api/v1/workflow-monitor
```

不要通过公网 nginx 地址回环访问，内网服务名更稳定。

### 10.3 新增环境变量

建议：

```text
WORKFLOW_MONITOR_ENABLED=true
WORKFLOW_MONITOR_INGEST_TOKEN=<long-random-secret>
WORKFLOW_MONITOR_INTERNAL_URL=http://web:8000/api/v1/workflow-monitor
WORKFLOW_MONITOR_EVENT_TTL_SECONDS=86400
WORKFLOW_MONITOR_RECENT_EVENT_LIMIT=1000
SNAKEMAKE_MONITOR_ENABLED=true
SNAKEMAKE_LOGGER=rich_loguru
```

### 10.4 Nginx

如果前端通过 `/api/v1/workflow-monitor/ws` 连接 WebSocket，现有 `/api/` 代理已支持 WebSocket Upgrade。

如果摄取端点仅给 Worker 内网调用，不需要暴露到 nginx。

生产上可以在 nginx 禁止外部访问摄取路径：

```text
/api/v1/workflow-monitor/loki/api/v1/push
```

只允许 Web 容器内部或 Worker 访问更安全。

## 11. 与现有任务中心的关系

不建议替代任务中心。

推荐关系：

- 任务中心：任务生命周期管理，适合查看历史、删除、报告跳转。
- 流程监控：运行中监控和错误聚合，适合实时观察。
- 任务详情：单任务深度信息，适合排查某一个任务。

新增监控面板后，任务中心仍然保留当前功能，只是进度数据会更实时。

## 12. 分阶段实施计划

### 阶段 1：最小可用监控

目标：平台内能实时看到运行中的 Snakemake 任务进度和错误。

后端：

- 新增 workflow monitor API。
- 实现 Loki-compatible ingest endpoint。
- 将插件事件解析为内部事件。
- 更新 `tasks.progress`。
- 将事件发布到 Redis Pub/Sub。
- 将核心事件追加到 `task_logs:{task_id}`，复用现有任务详情日志 WebSocket。

执行器：

- Snakemake 命令增加 `--logger rich_loguru` 或实际可用的 logger 名称。
- 每个任务生成 `monitor_config.yaml`。
- 执行命令追加 `--config monitor_conf=<path>`。

前端：

- 任务详情页实时日志能看到插件推来的事件。
- 任务列表进度通过原有轮询更新。

验收标准：

- 提交 RNA-seq/ATAC-seq 任务后，任务运行中进度不再一直停在 0。
- Snakemake `Finished jobid` 能实时进入任务详情日志。
- 失败任务能在任务详情中实时看到错误摘要。

### 阶段 2：原生流程监控面板

目标：新增 `/workflow-monitor` 页面。

后端：

- 增加 overview/summary/events API。
- 增加全局 WebSocket。
- 增加 Redis 中的任务摘要缓存。

前端：

- 新增 `WorkflowMonitorView.vue`。
- 新增全局运行中任务表。
- 新增实时事件流。
- 新增错误聚合面板。

验收标准：

- 管理员能看到全平台运行中任务。
- 普通用户只能看到自己的任务。
- 页面无需手动刷新即可更新进度和错误。

### 阶段 3：结构化事件持久化与告警

目标：支持历史追踪、规则级失败统计和可靠告警。

后端：

- 新增 `workflow_monitor_events` 表。
- 增加事件查询分页。
- 增加失败 rule 统计。
- 增加任务超时、长时间无事件告警。

插件：

- 增加 `omichub_monitor_url` 原生事件推送。
- 增加 token/header 支持。
- 增加退出 flush。

前端：

- 任务详情新增 Snakemake 结构化事件 tab。
- 增加 rule timeline。
- 增加 shell command 折叠展示。

验收标准：

- 可查询任意任务历史 rule/job 事件。
- 可统计最近一周失败最多的 rule。
- 插件推送失败不会影响 Snakemake 主流程。

## 13. 风险与应对

### 13.1 插件事件丢失

风险：

- 插件使用后台 daemon thread，进程退出时可能尚未发送完所有队列事件。

应对：

- 插件增加退出 flush。
- OmicHub 仍以 Celery returncode 作为最终状态权威。
- 本地 stdout/stderr 落盘保底。

### 13.2 任务关联错误

风险：

- `project_name` 如果使用用户项目名，可能重复。

应对：

- 强制 `project_name = task_id`。
- 显示名称可以另存为 `display_project_name`。

### 13.3 高频日志压垮数据库

风险：

- Snakemake 大流程日志很多，全部写 PostgreSQL 会放大压力。

应对：

- Redis 保存实时窗口。
- PostgreSQL 只保存结构化关键事件或采样事件。
- `tasks.logs` 只保留最近 N 条摘要。

### 13.4 用户可控推送地址

风险：

- 用户填写 `loki_url` 可能造成内网探测。

应对：

- 由后端强制注入内部地址。
- 自定义外部 Loki 只允许管理员设置。
- 对 URL 做白名单校验。

### 13.5 多进程 WebSocket 状态

风险：

- Web 容器使用多个 uvicorn worker，内存状态不共享。

应对：

- 所有实时事件通过 Redis Pub/Sub/Stream 传递。
- 不依赖单进程内存。

### 13.6 Snakemake logger 名称不一致

风险：

- README 中使用 `rich-loguru`，entry point 是 `rich_loguru`。

应对：

- 在生产 Snakemake 环境中执行最小 Snakefile 验证。
- 将可用名称写入 `.env` 配置，不硬编码。

## 14. 建议任务拆分

### 后端任务

1. 新增 workflow monitor schema/service/router。
2. 新增 Loki-compatible ingest endpoint。
3. 新增 Redis workflow monitor pubsub 工具。
4. 在 `api/v1/router.py` 注册新路由。
5. 在 `TaskService.submit()` 生成 `monitor_config.yaml`。
6. 在 `LocalSnakemakeExecutor` 增加 logger 和 monitor config 参数。
7. 摄取事件后更新 `tasks.progress` 和 `task_logs:{task_id}`。
8. 增加权限校验和 ingest token。

### 前端任务

1. 新增 workflow monitor API client。
2. 新增 workflow monitor WebSocket composable。
3. 新增 workflow monitor store。
4. 新增 `/workflow-monitor` 页面。
5. 任务详情页增加结构化事件 tab。
6. 侧边栏新增“流程监控”入口。

### 插件任务

1. 验证 logger 名称。
2. 增加 `omichub_monitor_url` 可选配置。
3. 增加 `omichub_monitor_token`。
4. 增加进程退出 flush。
5. 将 `task_id`、`flow_id`、`user_id` 写入 payload。

### 部署任务

1. 在 Snakemake conda 环境安装插件。
2. 增加 `WORKFLOW_MONITOR_*` 环境变量。
3. 修正 Snakemake 日志目录挂载。
4. 可选部署 Loki/Grafana 作为管理员排障面板。

## 15. 推荐优先级

最高优先级：

1. 确认插件在 Worker 的 Snakemake 环境中可用。
2. 执行器启用 logger 插件。
3. 自动注入 `task_id` 级监控配置。
4. OmicHub 后端接收插件事件。
5. 将插件事件同步到现有任务详情 WebSocket。

中优先级：

1. 新增流程监控独立页面。
2. Redis 实时摘要缓存。
3. 管理员全局视图。

低优先级：

1. 完整历史事件表。
2. Rule timeline。
3. 失败规则统计。
4. Grafana 深度跳转。

## 16. 最终建议

建议立即启动第一期改造。第一期改造量不大，但收益很明显：现有 Snakemake 任务可以从“结束后回填日志”升级为“运行中实时进度和错误可见”。

最稳妥的路径是：

1. OmicHub 新增 Loki-compatible 摄取端点。
2. Worker 运行 Snakemake 时启用 `rich_loguru` logger。
3. 每个任务生成独立 `monitor_config.yaml`，并用 `project_name = task_id` 做强关联。
4. 摄取服务把 `progress_percent` 写回 `tasks.progress`，把事件发布到 Redis。
5. 前端先复用现有任务详情页，确认链路稳定后再做独立流程监控面板。

这样可以最大化复用你已经写好的插件和 OmicHub 已有任务体系，同时把后续的全平台监控、规则级错误统计和告警能力自然扩展出来。
