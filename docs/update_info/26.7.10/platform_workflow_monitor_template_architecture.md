# OmicHub 平台流程监控模板创建与前后端架构文档

日期：2026-07-10

## 1. 文档目标

本文档定义 OmicHub 平台内“流程监控面板”的模板创建方式、后端架构、前端架构、数据协议和落地步骤。

该监控面板面向两类使用者：

- 普通用户：实时查看自己提交的 Snakemake 分析任务进度、日志、错误和结果入口。
- 管理员：实时查看全平台任务运行状态、失败聚合、Worker 状态、近期错误趋势和异常任务。

本文档重点解决三个问题：

- 监控面板模板如何定义，如何扩展不同视图。
- 后端如何接收 Snakemake 插件事件、聚合数据并给前端提供 API/WebSocket。
- 前端如何按模板渲染监控页面，并保持实时更新。

## 2. 总体建议

建议把“流程监控面板”设计为模板驱动页面，而不是直接把所有图表和表格硬编码在一个 Vue 页面里。

原因：

- OmicHub 已经大量使用 YAML 作为流程、工具、站点内容配置来源。
- 监控视图会随着流程类型扩展，例如 RNA-seq、ATAC-seq、数据下载、未来单细胞等。
- 管理员视图和普通用户视图需要不同组件和权限。
- 后续可以扩展为后台可配置 dashboard。

第一期推荐使用源码管控 YAML 模板：

```text
tool_configs/workflow_monitor/templates/default.yaml
tool_configs/workflow_monitor/templates/admin.yaml
tool_configs/workflow_monitor/templates/user.yaml
```

第二期再支持数据库存储和管理员页面编辑。

## 3. 监控模板概念

一个监控模板描述：

- 页面标题和适用角色。
- 页面刷新策略。
- 数据源。
- Widget 列表。
- Widget 布局。
- 筛选项。
- 点击动作。
- 权限约束。

模板只描述“展示什么”和“如何布局”，不直接包含真实任务数据。

真实数据由后端 API 和 WebSocket 提供。

## 4. 模板文件目录

建议新增：

```text
tool_configs/workflow_monitor/
  README.md
  templates/
    default.yaml
    admin.yaml
    user.yaml
```

后端新增配置项：

```python
workflow_monitor_template_dir: str = "tool_configs/workflow_monitor/templates"
workflow_monitor_default_template: str = "default"
```

## 5. 模板 YAML 结构

### 5.1 顶层结构

```yaml
id: default
name: "流程监控总览"
version: "1.0.0"
description: "OmicHub 分析流程实时监控面板"
scope: user
refresh:
  mode: websocket
  fallback_interval_seconds: 5
permissions:
  roles: ["user", "admin"]
filters:
  - key: status
    label: "状态"
    type: select
    default: running
    options:
      - label: "全部"
        value: all
      - label: "运行中"
        value: running
      - label: "失败"
        value: failed
      - label: "已完成"
        value: success
  - key: flow_id
    label: "流程"
    type: flow_select
    default: all
  - key: keyword
    label: "搜索"
    type: search
    placeholder: "搜索任务名、Rule、错误信息"
layout:
  desktop:
    columns: 12
    row_height: 96
  mobile:
    columns: 1
widgets: []
```

### 5.2 Widget 通用字段

```yaml
- id: running_tasks
  type: metric
  title: "运行中任务"
  data_source: summary
  query:
    field: running_count
  layout:
    desktop: { x: 0, y: 0, w: 3, h: 1 }
    mobile: { x: 0, y: 0, w: 1, h: 1 }
  visible:
    roles: ["user", "admin"]
```

通用字段说明：

| 字段 | 说明 |
| --- | --- |
| `id` | Widget 唯一 ID |
| `type` | Widget 类型，如 `metric`、`task_table`、`event_stream` |
| `title` | 展示标题 |
| `data_source` | 对应后端数据源 |
| `query` | 数据字段或参数 |
| `layout` | 桌面和移动端布局 |
| `visible.roles` | 可见角色 |
| `actions` | 点击行为 |

## 6. 推荐内置 Widget 类型

### 6.1 metric

用于顶部指标卡。

示例：

```yaml
- id: failed_today
  type: metric
  title: "今日失败"
  data_source: summary
  query:
    field: failed_today
  style:
    tone: danger
    icon: AlertCircleOutline
```

### 6.2 task_table

用于展示运行中任务列表。

```yaml
- id: running_task_table
  type: task_table
  title: "运行中任务"
  data_source: tasks
  query:
    status: running
    limit: 50
  columns:
    - key: name
      label: "任务"
      width: 260
      action: open_task
    - key: flow_id
      label: "流程"
      width: 120
    - key: status
      label: "状态"
      width: 100
      renderer: status_badge
    - key: progress
      label: "进度"
      width: 180
      renderer: progress_bar
    - key: current_rule
      label: "当前 Rule"
      width: 180
    - key: last_event_at
      label: "最后事件"
      width: 160
      renderer: relative_time
  actions:
    row_click: open_task
```

### 6.3 event_stream

用于展示实时事件流。

```yaml
- id: realtime_events
  type: event_stream
  title: "实时事件"
  data_source: events
  query:
    levels: ["warning", "error", "critical", "info"]
    limit: 100
  options:
    auto_scroll: true
    compact: true
    group_by_task: false
```

### 6.4 error_list

用于展示近期失败和错误摘要。

```yaml
- id: recent_errors
  type: error_list
  title: "近期错误"
  data_source: errors
  query:
    limit: 20
  actions:
    item_click: open_task
```

### 6.5 rule_timeline

用于任务详情页展示 rule/job 事件时间线。

```yaml
- id: rule_timeline
  type: rule_timeline
  title: "Rule 执行时间线"
  data_source: task_events
  query:
    event_types: ["JobStarted", "JobFinished", "Error"]
```

### 6.6 worker_status

管理员专用，展示 Celery Worker 和队列状态。

```yaml
- id: worker_status
  type: worker_status
  title: "Worker 状态"
  data_source: workers
  visible:
    roles: ["admin"]
```

## 7. 默认模板示例

建议第一期内置 `default.yaml`：

```yaml
id: default
name: "流程监控总览"
version: "1.0.0"
scope: user
refresh:
  mode: websocket
  fallback_interval_seconds: 5
permissions:
  roles: ["user", "admin"]
filters:
  - key: status
    label: "状态"
    type: select
    default: running
    options:
      - { label: "全部", value: all }
      - { label: "运行中", value: running }
      - { label: "失败", value: failed }
      - { label: "已完成", value: success }
  - key: flow_id
    label: "流程"
    type: flow_select
    default: all
  - key: keyword
    label: "搜索"
    type: search
layout:
  desktop: { columns: 12, row_height: 96 }
  mobile: { columns: 1, row_height: 88 }
widgets:
  - id: running_count
    type: metric
    title: "运行中"
    data_source: summary
    query: { field: running_count }
    style: { tone: info, icon: PulseOutline }
    layout:
      desktop: { x: 0, y: 0, w: 3, h: 1 }
      mobile: { x: 0, y: 0, w: 1, h: 1 }

  - id: failed_today
    type: metric
    title: "今日失败"
    data_source: summary
    query: { field: failed_today }
    style: { tone: danger, icon: AlertCircleOutline }
    layout:
      desktop: { x: 3, y: 0, w: 3, h: 1 }
      mobile: { x: 0, y: 1, w: 1, h: 1 }

  - id: avg_progress
    type: metric
    title: "平均进度"
    data_source: summary
    query: { field: avg_running_progress }
    style: { tone: success, unit: percent }
    layout:
      desktop: { x: 6, y: 0, w: 3, h: 1 }
      mobile: { x: 0, y: 2, w: 1, h: 1 }

  - id: stale_tasks
    type: metric
    title: "疑似卡住"
    data_source: summary
    query: { field: stale_task_count }
    style: { tone: warning, icon: TimerOutline }
    layout:
      desktop: { x: 9, y: 0, w: 3, h: 1 }
      mobile: { x: 0, y: 3, w: 1, h: 1 }

  - id: running_tasks
    type: task_table
    title: "运行中任务"
    data_source: tasks
    query: { status: running, limit: 50 }
    layout:
      desktop: { x: 0, y: 1, w: 8, h: 5 }
      mobile: { x: 0, y: 4, w: 1, h: 5 }
    columns:
      - { key: name, label: "任务", action: open_task }
      - { key: flow_id, label: "流程" }
      - { key: status, label: "状态", renderer: status_badge }
      - { key: progress, label: "进度", renderer: progress_bar }
      - { key: current_rule, label: "当前 Rule" }
      - { key: last_event_at, label: "最后事件", renderer: relative_time }

  - id: realtime_events
    type: event_stream
    title: "实时事件"
    data_source: events
    query: { limit: 100 }
    options: { auto_scroll: true, compact: true }
    layout:
      desktop: { x: 8, y: 1, w: 4, h: 5 }
      mobile: { x: 0, y: 9, w: 1, h: 4 }

  - id: recent_errors
    type: error_list
    title: "近期错误"
    data_source: errors
    query: { limit: 20 }
    layout:
      desktop: { x: 0, y: 6, w: 12, h: 3 }
      mobile: { x: 0, y: 13, w: 1, h: 3 }
```

## 8. 后端架构

### 8.1 新增后端文件

建议新增：

```text
src/omichub/api/v1/workflow_monitor.py
src/omichub/application/schemas/workflow_monitor.py
src/omichub/application/services/workflow_monitor_service.py
src/omichub/application/services/workflow_monitor_template_service.py
src/omichub/infrastructure/cache/workflow_monitor_pubsub.py
src/omichub/infrastructure/yaml/workflow_monitor_template_loader.py
```

第二期可新增：

```text
src/omichub/infrastructure/database/models/workflow_monitor.py
src/omichub/infrastructure/database/repositories/workflow_monitor_repository.py
alembic/versions/<revision>_add_workflow_monitor_events.py
```

### 8.2 后端分层职责

#### API 层

文件：

`src/omichub/api/v1/workflow_monitor.py`

职责：

- 暴露模板、总览、任务摘要、事件查询、WebSocket 和摄取端点。
- 做用户鉴权和角色判断。
- 不写复杂业务逻辑。

#### Schema 层

文件：

`src/omichub/application/schemas/workflow_monitor.py`

职责：

- 定义模板 DTO。
- 定义事件 DTO。
- 定义任务快照 DTO。
- 定义总览 DTO。

#### Service 层

文件：

`workflow_monitor_service.py`

职责：

- 解析插件事件。
- 更新 Redis 实时摘要。
- 更新 `tasks.progress` 和 `tasks.error_message`。
- 发布 WebSocket 事件。
- 查询任务快照和错误聚合。

文件：

`workflow_monitor_template_service.py`

职责：

- 加载模板。
- 校验模板结构。
- 按用户角色过滤 widget。
- 合并默认筛选项。

#### Infrastructure 层

文件：

`workflow_monitor_pubsub.py`

职责：

- 管理 Redis channel。
- 发布全局事件、用户事件、任务事件。

文件：

`workflow_monitor_template_loader.py`

职责：

- 从 YAML 读取模板。
- mtime 热重载。
- 缓存模板。

## 9. 后端 API 设计

### 9.1 模板接口

```text
GET /api/v1/workflow-monitor/templates
```

返回当前用户可用模板列表。

```json
{
  "items": [
    {
      "id": "default",
      "name": "流程监控总览",
      "version": "1.0.0",
      "scope": "user"
    }
  ],
  "total": 1
}
```

```text
GET /api/v1/workflow-monitor/templates/{template_id}
```

返回模板详情。后端需要按用户角色过滤不可见 widget。

```text
POST /api/v1/workflow-monitor/templates/reload
```

管理员接口，重新加载 YAML 模板。

### 9.2 总览接口

```text
GET /api/v1/workflow-monitor/overview
```

参数：

```text
template_id=default
status=running
flow_id=all
keyword=
time_range=24h
```

返回：

```json
{
  "summary": {
    "running_count": 3,
    "failed_today": 1,
    "avg_running_progress": 52.7,
    "stale_task_count": 0,
    "warning_count_10m": 4,
    "error_count_10m": 1
  },
  "tasks": [
    {
      "id": "task-id",
      "name": "RNA-seq 差异分析",
      "flow_id": "rna_seq",
      "status": "running",
      "progress": 0.527,
      "progress_percent": 52.7,
      "progress_details": "31/59",
      "current_rule": "star_align",
      "current_job_id": 31,
      "last_event_at": "2026-07-10T12:00:00+08:00",
      "last_error": ""
    }
  ],
  "events": [],
  "errors": []
}
```

### 9.3 单任务摘要

```text
GET /api/v1/workflow-monitor/tasks/{task_id}/summary
```

返回：

```json
{
  "task_id": "task-id",
  "flow_id": "rna_seq",
  "status": "running",
  "progress": 0.527,
  "progress_percent": 52.7,
  "progress_details": "31/59",
  "current_rule": "star_align",
  "current_job_id": 31,
  "finished_jobs": 31,
  "total_jobs": 59,
  "last_event_at": "2026-07-10T12:00:00+08:00",
  "last_error": null
}
```

### 9.4 事件查询

```text
GET /api/v1/workflow-monitor/tasks/{task_id}/events
```

参数：

```text
level=warning,error
limit=200
cursor=<cursor>
```

### 9.5 WebSocket

全局监控：

```text
WS /api/v1/workflow-monitor/ws?token=<JWT>&template_id=default
```

单任务监控：

```text
WS /api/v1/workflow-monitor/tasks/{task_id}/ws?token=<JWT>
```

消息格式：

```json
{
  "type": "event",
  "event": {
    "task_id": "task-id",
    "level": "info",
    "message": "Finished jobid: 12 (Rule: trim_fastq)",
    "snakemake": {
      "rule": "trim_fastq",
      "job_id": 12,
      "event_type": "JobFinished",
      "progress_percent": 42.5,
      "progress_details": "17/40"
    }
  }
}
```

任务快照更新：

```json
{
  "type": "task_snapshot",
  "task": {
    "id": "task-id",
    "status": "running",
    "progress": 0.425,
    "current_rule": "trim_fastq",
    "last_event_at": "2026-07-10T12:00:00+08:00"
  }
}
```

### 9.6 插件摄取接口

第一期 Loki-compatible：

```text
POST /api/v1/workflow-monitor/loki/api/v1/push
```

第二期原生：

```text
POST /api/v1/workflow-monitor/events
```

生产环境建议原生接口使用：

```text
Authorization: Bearer <WORKFLOW_MONITOR_INGEST_TOKEN>
X-OmicHub-Timestamp: ...
X-OmicHub-Nonce: ...
X-OmicHub-Signature: ...
```

## 10. Redis 数据结构

### 10.1 任务摘要

```text
workflow_monitor:task:{task_id}:summary
```

类型：Hash 或 JSON String。

字段：

```json
{
  "task_id": "task-id",
  "flow_id": "rna_seq",
  "user_id": "user-id",
  "status": "running",
  "progress": 0.42,
  "progress_percent": 42.0,
  "progress_details": "17/40",
  "current_rule": "trim_fastq",
  "current_job_id": 17,
  "last_event_at": "...",
  "last_error": ""
}
```

TTL：

```text
24h 到 7d
```

### 10.2 最近事件

```text
workflow_monitor:task:{task_id}:events
```

类型：List 或 Stream。

第一期可用 List：

- `LPUSH`
- `LTRIM 0 999`
- `EXPIRE`

第二期建议 Stream：

- `XADD`
- `XREAD`
- `XTRIM MAXLEN`

### 10.3 全局运行中任务集合

```text
workflow_monitor:running_tasks
```

类型：Set 或 Sorted Set。

建议 Sorted Set：

- member：task_id
- score：last_event_timestamp

可用于判断 stale task。

### 10.4 Pub/Sub Channel

```text
workflow_monitor:global
workflow_monitor:user:{user_id}
workflow_monitor:task:{task_id}
```

## 11. PostgreSQL 数据模型

第一期可以不新增表，优先复用：

- `tasks.progress`
- `tasks.logs`
- `tasks.error_message`

第二期新增：

```text
workflow_monitor_events
workflow_monitor_templates
```

### 11.1 workflow_monitor_events

字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | UUID | 主键 |
| task_id | UUID | 任务 ID |
| flow_id | String | 流程 ID |
| user_id | UUID | 用户 ID |
| timestamp | DateTime | 事件时间 |
| level | String | 日志等级 |
| rule | String | Snakemake rule |
| job_id | Integer | jobid |
| event_type | String | 事件类型 |
| message | Text | 消息 |
| progress_percent | Float | 0 到 100 |
| progress_details | String | 例如 17/40 |
| raw | JSONB | 原始 payload |

### 11.2 workflow_monitor_templates

第二期支持后台编辑时使用。

字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | String | 模板 ID |
| name | String | 模板名 |
| version | String | 版本 |
| scope | String | user/admin |
| content | JSONB | 模板内容 |
| enabled | Boolean | 是否启用 |
| created_at | DateTime | 创建时间 |
| updated_at | DateTime | 更新时间 |

## 12. 前端架构

### 12.1 新增前端文件

建议新增：

```text
frontend/src/api/workflowMonitor.ts
frontend/src/types/workflowMonitor.ts
frontend/src/stores/workflowMonitor.ts
frontend/src/composables/useWorkflowMonitorWebSocket.ts
frontend/src/views/WorkflowMonitorView.vue
frontend/src/components/workflow-monitor/MonitorFilterBar.vue
frontend/src/components/workflow-monitor/MonitorWidgetRenderer.vue
frontend/src/components/workflow-monitor/widgets/MetricWidget.vue
frontend/src/components/workflow-monitor/widgets/TaskTableWidget.vue
frontend/src/components/workflow-monitor/widgets/EventStreamWidget.vue
frontend/src/components/workflow-monitor/widgets/ErrorListWidget.vue
frontend/src/components/workflow-monitor/widgets/RuleTimelineWidget.vue
frontend/src/components/workflow-monitor/widgets/WorkerStatusWidget.vue
```

### 12.2 路由

新增：

```ts
{
  path: 'workflow-monitor',
  name: 'workflow-monitor',
  component: () => import('@/views/WorkflowMonitorView.vue'),
  meta: { title: '流程监控', requiresAuth: true }
}
```

导航建议放在“任务中心”附近：

```ts
{ key: 'workflow-monitor', label: '流程监控', to: '/workflow-monitor', icon: PulseOutline }
```

### 12.3 类型定义

`frontend/src/types/workflowMonitor.ts`：

```ts
export interface MonitorTemplate {
  id: string
  name: string
  version: string
  scope: 'user' | 'admin'
  filters: MonitorFilter[]
  layout: MonitorLayoutConfig
  widgets: MonitorWidget[]
}

export interface MonitorWidget {
  id: string
  type: 'metric' | 'task_table' | 'event_stream' | 'error_list' | 'rule_timeline' | 'worker_status'
  title: string
  data_source: string
  query?: Record<string, unknown>
  layout: Record<string, MonitorWidgetLayout>
  columns?: MonitorTableColumn[]
  options?: Record<string, unknown>
  visible?: { roles?: string[] }
}

export interface WorkflowTaskSnapshot {
  id: string
  name: string
  flow_id: string
  user_id: string
  username?: string
  status: string
  progress: number
  progress_percent: number
  progress_details?: string
  current_rule?: string
  current_job_id?: number
  last_event_at?: string
  last_error?: string
}

export interface WorkflowEvent {
  task_id: string
  flow_id?: string
  level: 'debug' | 'info' | 'warning' | 'error' | 'critical'
  message: string
  timestamp: string
  snakemake?: {
    rule?: string
    job_id?: number
    event_type?: string
    progress_percent?: number
    progress_details?: string
    shell_command?: string
  }
}
```

### 12.4 Store 设计

`useWorkflowMonitorStore` 状态：

```ts
const template = ref<MonitorTemplate | null>(null)
const summary = ref<WorkflowMonitorSummary | null>(null)
const tasks = ref<WorkflowTaskSnapshot[]>([])
const events = ref<WorkflowEvent[]>([])
const errors = ref<WorkflowEvent[]>([])
const filters = reactive<Record<string, unknown>>({})
const connected = ref(false)
const loading = ref(false)
```

核心方法：

```ts
async function fetchTemplate(templateId = 'default') {}
async function fetchOverview() {}
function applyEvent(event: WorkflowEvent) {}
function applyTaskSnapshot(task: WorkflowTaskSnapshot) {}
function setFilter(key: string, value: unknown) {}
function resetFilters() {}
```

### 12.5 WebSocket composable

`useWorkflowMonitorWebSocket.ts`：

职责：

- 读取 JWT。
- 连接 `/api/v1/workflow-monitor/ws`。
- 自动处理重连。
- 接收 `event`、`task_snapshot`、`summary`。
- 页面卸载时关闭连接。

重连策略：

- 首次断开 1 秒后重连。
- 后续指数退避，最大 30 秒。
- token 不存在或 1008 关闭时不重连。

## 13. 前端渲染流程

`WorkflowMonitorView.vue` 页面加载：

1. 读取路由 query 中的 `template_id`，默认 `default`。
2. 调用 `fetchTemplate(template_id)`。
3. 根据模板初始化 filters。
4. 调用 `fetchOverview()` 获取首屏数据。
5. 打开 WebSocket。
6. `MonitorWidgetRenderer` 按模板 widgets 渲染对应组件。
7. WebSocket 推送更新 store，Widget 自动响应。

数据流：

```text
WorkflowMonitorView
  -> useWorkflowMonitorStore
    -> workflowMonitorApi.getTemplate()
    -> workflowMonitorApi.getOverview()
    -> useWorkflowMonitorWebSocket()
  -> MonitorWidgetRenderer
    -> MetricWidget / TaskTableWidget / EventStreamWidget / ErrorListWidget
```

## 14. Widget Renderer 设计

`MonitorWidgetRenderer.vue` 根据 `widget.type` 分发：

```ts
const widgetMap = {
  metric: MetricWidget,
  task_table: TaskTableWidget,
  event_stream: EventStreamWidget,
  error_list: ErrorListWidget,
  rule_timeline: RuleTimelineWidget,
  worker_status: WorkerStatusWidget,
}
```

每个 Widget 接收：

```ts
defineProps<{
  widget: MonitorWidget
  data: unknown
  loading?: boolean
}>()
```

不建议每个 Widget 自己发请求。第一期统一由页面和 store 拉取数据，减少并发请求和状态混乱。

## 15. 权限设计

### 15.1 模板权限

后端按角色过滤模板：

- 普通用户：只能使用 `scope=user` 或 roles 包含 `user` 的模板。
- 管理员：可使用全部模板。

### 15.2 数据权限

后端所有查询必须加权限过滤：

- 普通用户只能查询 `tasks.user_id = current_user.id`。
- 管理员可以查询全平台。

WebSocket 同理：

- 普通用户订阅 `workflow_monitor:user:{user_id}`。
- 管理员可订阅 `workflow_monitor:global`。

### 15.3 摄取权限

插件摄取接口不使用用户 JWT。

建议使用：

```text
WORKFLOW_MONITOR_INGEST_TOKEN
```

原生事件接口必须校验 token。Loki-compatible 第一阶段如果暂时没有 token，也必须限定内网访问。

## 16. 监控模板校验规则

后端加载 YAML 时必须校验：

- `id` 只能包含字母、数字、下划线、短横线。
- `widgets[].id` 在模板内唯一。
- `widgets[].type` 必须属于白名单。
- `widgets[].data_source` 必须属于白名单。
- `layout.desktop.w/h` 必须为正数。
- `visible.roles` 只能包含 `user`、`admin`。
- `actions` 只能使用后端和前端明确支持的动作。

白名单建议：

```python
WIDGET_TYPES = {
    "metric",
    "task_table",
    "event_stream",
    "error_list",
    "rule_timeline",
    "worker_status",
}

DATA_SOURCES = {
    "summary",
    "tasks",
    "events",
    "errors",
    "task_events",
    "workers",
}

ACTIONS = {
    "open_task",
    "open_report",
    "open_logs",
}
```

## 17. 前端 UI 规范

流程监控是生产工具页面，不做营销式布局。

建议：

- 顶部为紧凑指标条。
- 中间为任务表格和事件流并排。
- 下方为错误聚合。
- 移动端按指标、任务、事件、错误纵向堆叠。
- 长日志必须截断并提供 tooltip 或展开。
- Rule 名、路径、shell command 必须允许复制。
- 错误等级使用稳定颜色：
  - info：蓝/灰。
  - warning：黄。
  - error/critical：红。
  - success：绿。

## 18. 与现有任务中心的关系

新增页面不替代任务中心：

- 任务中心：任务管理、历史任务、报告入口、删除任务。
- 流程监控：实时运行态、错误聚合、全局态势。
- 任务详情：单任务日志、DAG、结构化事件、结果路径。

建议任务中心增加一个入口：

```text
查看实时监控
```

点击跳到：

```text
/workflow-monitor?task_id=<task_id>
```

或任务详情页新增 tab：

```text
结构化事件
```

## 19. 分阶段实施

### 阶段 1：模板静态加载 + 监控总览

后端：

- 新增模板 YAML 目录。
- 新增模板 loader。
- 新增 `/workflow-monitor/templates/{id}`。
- 新增 `/workflow-monitor/overview`。

前端：

- 新增 `/workflow-monitor` 页面。
- 新增 template-driven renderer。
- 使用轮询获取 overview。

验收：

- 能按 `default.yaml` 渲染页面。
- 普通用户只看到自己的任务。
- 管理员可看到全平台任务。

### 阶段 2：WebSocket 实时更新

后端：

- 新增 workflow monitor Pub/Sub。
- 新增 `/workflow-monitor/ws`。
- 摄取端发布事件。

前端：

- 新增 WebSocket composable。
- store 根据事件更新任务表和事件流。

验收：

- Snakemake 运行时页面无需刷新即可更新进度。
- 事件流实时追加。
- 断线后能自动重连。

### 阶段 3：结构化事件持久化

后端：

- 新增 `workflow_monitor_events` 表。
- 新增事件分页查询。
- 新增错误聚合统计。

前端：

- 任务详情新增 Rule timeline。
- 错误聚合支持按 rule、flow、用户过滤。

验收：

- 历史任务也能查看结构化事件。
- 能统计失败最多的 rule。

### 阶段 4：模板后台管理

后端：

- 新增模板 DB 表。
- 新增管理员模板 CRUD。

前端：

- 新增监控模板管理页。
- 支持拖拽布局或表单编辑。

验收：

- 管理员无需改 YAML 即可新增或调整监控页面。

## 20. 推荐开发任务清单

后端任务：

1. 新增 workflow monitor schema。
2. 新增 YAML template loader。
3. 新增 template service。
4. 新增 monitor service。
5. 新增 Redis pubsub 工具。
6. 新增 API router 并注册到 `api/v1/router.py`。
7. 新增 overview 查询。
8. 新增 WebSocket。
9. 新增插件事件摄取与 task progress 同步。

前端任务：

1. 新增 workflow monitor 类型定义。
2. 新增 workflow monitor API。
3. 新增 workflow monitor store。
4. 新增 WebSocket composable。
5. 新增 WorkflowMonitorView。
6. 新增 FilterBar。
7. 新增 WidgetRenderer。
8. 新增 metric/task table/event stream/error list widgets。
9. 新增路由和导航入口。

配置任务：

1. 新增 `tool_configs/workflow_monitor/templates/default.yaml`。
2. 新增 `admin.yaml`。
3. 新增 `user.yaml`。
4. 新增 `.env` 中 workflow monitor 配置。

## 21. 验收标准

第一期完成后应满足：

- `/workflow-monitor` 可以打开并按模板渲染。
- 模板来自 YAML，而不是硬编码。
- 普通用户只能看到自己的任务。
- 管理员可以看到全平台任务。
- 运行中任务的进度、当前 rule、最后事件时间可见。
- 事件流能实时追加 Snakemake 插件推送事件。
- 失败任务能显示错误摘要并跳转任务详情。
- 关闭 WebSocket 后页面能退化到 5 秒轮询。
- 模板 YAML 修改后可通过 reload 接口热加载。

## 22. 最终建议

建议先实现 YAML 模板驱动的 `/workflow-monitor` 页面，不要一开始就做可视化模板编辑器。

推荐最小落地路径：

1. 新增 `default.yaml` 模板。
2. 后端实现模板加载和 overview API。
3. 前端实现 WidgetRenderer 和 4 个核心 Widget：metric、task_table、event_stream、error_list。
4. 摄取 Snakemake 插件事件后写 Redis，并通过 WebSocket 推给页面。
5. 页面稳定后，再扩展 rule_timeline、worker_status 和模板后台管理。

这样既能快速把流程实时监控跑起来，又保留后续扩展空间。
