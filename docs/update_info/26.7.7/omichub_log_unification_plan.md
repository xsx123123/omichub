# OmicHub 平台日志统一管理改造计划

> 目标：将目前碎片化的日志体系统一归集到 `/data/omichub_data/logs/` 目录，实现「统一落盘 + 分级聚合」，同时保留现有 WebSocket 实时流能力。

---

## 目录

- [一、现状诊断](#一现状诊断)
- [二、目标目录结构](#二目标目录结构)
- [三、分步实施计划](#三分步实施计划)
  - [Phase 1：基础设施打通（挂载与权限）](#phase-1基础设施打通挂载与权限)
  - [Phase 2：应用日志统一改造（loguru）](#phase-2应用日志统一改造loguru)
  - [Phase 3：Nginx 日志标准化](#phase-3nginx-日志标准化)
  - [Phase 4：Celery 任务日志双写](#phase-4celery-任务日志双写)
  - [Phase 5：Snakemake 日志统一路由](#phase-5snakemake-日志统一路由)
  - [Phase 6：审计日志实现](#phase-6审计日志实现)
  - [Phase 7：日志聚合与监控（Loki）](#phase-7日志聚合与监控loki)
- [四、实施优先级与里程碑](#四实施优先级与里程碑)
- [五、立即执行的 Checklist](#五立即执行的-checklist)
- [六、附录：配置参考](#六附录配置参考)

---

## 一、现状诊断

| 日志类型 | 当前去向 | 是否持久 | 问题 |
|----------|----------|----------|------|
| 应用服务日志（web/beat/worker） | stdout / 容器内 `logs/omichub.log` | 不持久 | `docker-compose.prod.yml` 未挂载 `/app/logs`，容器重建即丢失 |
| Nginx 访问/错误日志 | 容器内 `/var/log/nginx/` | 不持久 | 同样未挂载到宿主机，重启即丢失 |
| 任务实时日志 | Redis Pub/Sub -> WebSocket -> PostgreSQL | 已持久化 | 目前唯一跨容器重启保留的日志，但文本排查不便 |
| Snakemake 流程日志 | 本地 stdout / 可选 Loki | 视配置 | 需手动配置 `loki_url` 和 `project_name` |
| 审计日志 | 未实现（todo.md 待办） | 未实现 | 中间件 + 数据表均未落地 |

> 设计文档（`report/04_可优化点与建议.md`、`todo.md`）已明确记录待办：「结构化日志 + Loki 聚合」和「监控告警体系」尚未完成。

---

## 二、目标目录结构

在宿主机统一规划如下，容器内通过 bind mount 映射：

```
/data/omichub_data/logs/
├── app/                          # 应用服务日志（web / beat / worker）
│   ├── omichub.log               # 主应用日志（loguru 轮转）
│   ├── omichub.json.log          # 结构化 JSON 日志，供 Loki 抓取
│   └── error.log                 # ERROR 级别以上单独抽离
├── nginx/
│   ├── access.log                # Nginx 访问日志
│   └── error.log                 # Nginx 错误日志
├── celery/                       # Celery 任务执行日志（DB 之外的文本备份）
│   └── tasks/
│       └── {task_id}.log
├── snakemake/                    # 生物信息流程日志
│   └── {project_name}/
│       └── {timestamp}/
├── audit/                        # 审计日志（待实现）
│   └── audit.log
└── loki/                         # 后续接入 Grafana Loki 的本地数据
```

---

## 三、分步实施计划

### Phase 1：基础设施打通（挂载与权限）

**目标**：让日志先能写到宿主机目录，解决「容器重建即丢」的问题。

#### 1.1 宿主机创建目录并设权限

```bash
sudo mkdir -p /data/omichub_data/logs/{app,nginx,celery,snakemake,audit}
sudo chown -R 1000:1000 /data/omichub_data/logs
sudo chmod -R 755 /data/omichub_data/logs
```

> 注意：确保容器内运行用户的 UID/GID 与宿主机一致（如 `user: "1000:1000"`），避免权限拒绝。

#### 1.2 `docker-compose.prod.yml` 挂载配置

```yaml
services:
  web:
    user: "1000:1000"
    volumes:
      - /data/omichub_data/logs/app:/app/logs
    environment:
      - SERVICE_NAME=web

  beat:
    user: "1000:1000"
    volumes:
      - /data/omichub_data/logs/app:/app/logs
    environment:
      - SERVICE_NAME=beat

  worker:
    user: "1000:1000"
    volumes:
      - /data/omichub_data/logs/app:/app/logs
      - /data/omichub_data/logs/snakemake:/logs
    environment:
      - SERVICE_NAME=worker

  nginx:
    volumes:
      - /data/omichub_data/logs/nginx:/var/log/nginx
```

#### 1.3 验证

```bash
docker compose -f docker-compose.prod.yml down
docker compose -f docker-compose.prod.yml up -d
# 检查宿主机目录是否生成日志文件
ls -la /data/omichub_data/logs/app/
ls -la /data/omichub_data/logs/nginx/
```

---

### Phase 2：应用日志统一改造（loguru）

**目标**：让 web / beat / worker 的日志统一格式、统一路径、支持结构化 JSON。

#### 2.1 改造 `src/omichub/core/logging.py`

```python
import sys
import os
from loguru import logger

LOG_DIR = "/app/logs"
os.makedirs(LOG_DIR, exist_ok=True)

SERVICE_NAME = os.getenv("SERVICE_NAME", "app")


def setup_logging():
    # 移除默认 handler
    logger.remove()

    # 1. stdout（开发环境保留，可读性优先）
    logger.add(
        sys.stdout,
        level="INFO",
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
               "<level>{level: <8}</level> | "
               "<cyan>{extra[service]}</cyan> | "
               "{message}",
    )

    # 2. 主日志文件（轮转，50MB / 保留30天 / zip压缩）
    logger.add(
        f"{LOG_DIR}/omichub.log",
        rotation="50 MB",
        retention="30 days",
        compression="zip",
        level="INFO",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {extra[service]} | {message}",
        enqueue=True,           # 多进程安全
        backtrace=True,
        diagnose=True,
    )

    # 3. JSON 结构化日志（供 Loki / Promtail 抓取）
    logger.add(
        f"{LOG_DIR}/omichub.json.log",
        rotation="50 MB",
        retention="30 days",
        compression="zip",
        level="INFO",
        serialize=True,         # 输出 JSON
        enqueue=True,
    )

    # 4. ERROR 级别单独抽离（快速定位故障）
    logger.add(
        f"{LOG_DIR}/error.log",
        rotation="50 MB",
        retention="30 days",
        compression="zip",
        level="ERROR",
        enqueue=True,
        backtrace=True,
        diagnose=True,
    )

    # 绑定服务名到上下文
    logger = logger.bind(service=SERVICE_NAME)
    return logger


# 全局初始化
logger = setup_logging()
```

#### 2.2 使用方式

```python
from omichub.core.logging import logger

logger.info("Pipeline started")
logger.error("BLAST database not found")
```

#### 2.3 环境变量控制（可选）

| 环境变量 | 说明 | 默认值 |
|----------|------|--------|
| `SERVICE_NAME` | 服务标识（web/beat/worker） | `app` |
| `OMICHUB_LOG_LEVEL` | 日志级别 | `INFO` |
| `OMICHUB_LOG_FORMAT` | 输出格式（text/json） | `text` |

---

### Phase 3：Nginx 日志标准化

**目标**：Nginx 日志落到统一目录，并开启结构化格式方便后续解析。

#### 3.1 `nginx.prod.conf` 配置

```nginx
# 定义结构化 JSON 格式，方便后续接入 Loki
log_format omichub_json escape=json '{'
    '"timestamp":"$time_iso8601",'
    '"service":"nginx",'
    '"remote_addr":"$remote_addr",'
    '"request_id":"$http_x_request_id",'
    '"method":"$request_method",'
    '"uri":"$uri",'
    '"status":$status,'
    '"bytes":$body_bytes_sent,'
    '"request_time":$request_time,'
    '"upstream_time":"$upstream_response_time",'
    '"referer":"$http_referer",'
    '"user_agent":"$http_user_agent"'
'}';

server {
    access_log /var/log/nginx/access.log omichub_json;
    error_log /var/log/nginx/error.log warn;

    # ... 其他配置
}
```

> 由于 `docker-compose.prod.yml` 已将 `/var/log/nginx` 挂载到宿主机，日志会自动持久化。

---

### Phase 4：Celery 任务日志双写

**目标**：任务日志既保留现有的 WebSocket 实时流 + DB 持久化，**同时**写入文本文件，方便在宿主机上 `tail -f` 排查。

#### 4.1 任务日志模块

```python
import os
from loguru import logger
from celery import Task

TASK_LOG_DIR = "/app/logs/celery/tasks"
os.makedirs(TASK_LOG_DIR, exist_ok=True)


class LoggedTask(Task):
    '''Celery Task base: auto-create per-task log file'''

    def __call__(self, *args, **kwargs):
        task_id = self.request.id or "no-id"
        sink_path = f"{TASK_LOG_DIR}/{task_id}.log"

        # 动态添加文件 sink
        handler_id = logger.add(
            sink_path,
            level="INFO",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}",
            enqueue=True,
        )

        try:
            logger.info(f"Task {task_id} started")
            return self.run(*args, **kwargs)
        finally:
            logger.info(f"Task {task_id} finished")
            logger.remove(handler_id)


# 使用方式
@app.task(base=LoggedTask, bind=True)
def run_pipeline(self, project_id):
    logger.info(f"Running pipeline for project {project_id}")
    # ... 业务逻辑
```

#### 4.2 日志清理策略

```bash
# 定期清理超过 7 天的任务日志（加入 crontab）
find /data/omichub_data/logs/celery/tasks -type f -mtime +7 -delete
```

---

### Phase 5：Snakemake 日志统一路由

**目标**：让生物信息流程的日志进入 `/data/omichub_data/logs/snakemake/`。

#### 5.1 调用端配置

```python
import os
from datetime import datetime

project_name = "rnaseq_proj_01"  # 从任务参数获取
log_dir = f"/logs/snakemake/{project_name}/{datetime.now().strftime('%Y%m%d_%H%M%S')}"
os.makedirs(log_dir, exist_ok=True)

# 通过环境变量传给 Snakemake 流程
os.environ["SNAKEMAKE_LOG_DIR"] = log_dir

# 启动 Snakemake
# snakemake --config log_dir=$SNAKEMAKE_LOG_DIR ...
```

#### 5.2 Snakemake 流程内读取

```python
# Snakefile
import os
from loguru import logger

log_dir = config.get("log_dir", "/tmp")
logger.add(f"{log_dir}/snakemake.log", rotation="10 MB", enqueue=True)

logger.info("Snakemake workflow started")
```

---

### Phase 6：审计日志实现

**目标**：填补 `todo.md` 中「审计日志表 + 中间件」的空白，同时写一份文本备份到统一目录。

#### 6.1 数据模型（PostgreSQL）

```python
from sqlalchemy import Column, String, DateTime, JSON, Integer
from sqlalchemy.sql import func

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    user_id = Column(String(64), nullable=False, index=True)
    action = Column(String(64), nullable=False)      # LOGIN, LOGOUT, DATA_EXPORT, PIPELINE_RUN, PERMISSION_CHANGE
    resource = Column(String(256), nullable=False)   # 被操作的资源标识
    details = Column(JSON, default={})               # 详细参数
    ip_address = Column(String(64))
    user_agent = Column(String(512))
    result = Column(String(16), nullable=False)      # SUCCESS / FAILURE
```

#### 6.2 中间件（FastAPI 示例）

```python
from fastapi import Request
from omichub.core.logging import logger
import time

async def audit_middleware(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration = time.time() - start

    # 只记录敏感操作
    sensitive_paths = ["/api/v1/auth", "/api/v1/admin", "/api/v1/pipelines/run", "/api/v1/data/export"]
    if any(request.url.path.startswith(p) for p in sensitive_paths):
        audit_entry = {
            "timestamp": datetime.now().isoformat(),
            "user_id": request.state.user_id if hasattr(request.state, "user_id") else "anonymous",
            "action": f"{request.method}_{request.url.path}",
            "resource": str(request.url),
            "details": {"duration_ms": round(duration * 1000, 2)},
            "ip_address": request.client.host,
            "user_agent": request.headers.get("user-agent", ""),
            "result": "SUCCESS" if response.status_code < 400 else "FAILURE",
        }

        # 双写：DB + 文件
        await save_audit_log_to_db(audit_entry)
        logger.bind(service="audit").info(f"AUDIT: {audit_entry}")

    return response
```

#### 6.3 文本备份路径

```
/data/omichub_data/logs/audit/audit.log
```

---

### Phase 7：日志聚合与监控（Loki）

**目标**：当文本日志统一后，平滑接入 Loki，实现跨服务全文检索。

#### 7.1 `docker-compose.monitoring.yml`（可选）

```yaml
services:
  loki:
    image: grafana/loki:2.9.0
    ports:
      - "3100:3100"
    volumes:
      - /data/omichub_data/logs/loki:/loki
      - ./loki-config.yml:/etc/loki/local-config.yaml
    command: -config.file=/etc/loki/local-config.yaml

  promtail:
    image: grafana/promtail:2.9.0
    volumes:
      - /data/omichub_data/logs:/logs:ro
      - ./promtail-config.yml:/etc/promtail/config.yml
    command: -config.file=/etc/promtail/config.yml
```

#### 7.2 `promtail-config.yml`

```yaml
server:
  http_listen_port: 9080
  grpc_listen_port: 0

positions:
  filename: /tmp/positions.yaml

clients:
  - url: http://loki:3100/loki/api/v1/push

scrape_configs:
  - job_name: omichub-app
    static_configs:
      - targets:
          - localhost
        labels:
          job: omichub-app
          service: app
          __path__: /logs/app/*.log

  - job_name: omichub-nginx
    static_configs:
      - targets:
          - localhost
        labels:
          job: omichub-nginx
          service: nginx
          __path__: /logs/nginx/*.log

  - job_name: omichub-audit
    static_configs:
      - targets:
          - localhost
        labels:
          job: omichub-audit
          service: audit
          __path__: /logs/audit/*.log
```

#### 7.3 Grafana 查询示例

```logql
# 查询所有 ERROR 级别日志
{service="app"} |= "ERROR"

# 查询特定用户的审计记录
{service="audit"} | json | user_id="user_123"

# 查询 Nginx 5xx 错误
{service="nginx"} | json | status>=500
```

---

## 四、实施优先级与里程碑

| 里程碑 | 内容 | 预计工时 | 优先级 |
|--------|------|----------|--------|
| **M1** | Phase 1 + Phase 2：挂载目录 + 应用日志统一改造 | 2-3h | P0 |
| **M2** | Phase 3：Nginx 日志挂载 + 结构化 | 1h | P0 |
| **M3** | Phase 4：Celery 任务日志双写 | 2h | P1 |
| **M4** | Phase 5：Snakemake 日志统一路由 | 1h | P1 |
| **M5** | Phase 6：审计日志表 + 中间件 + 文本备份 | 4-6h | P2 |
| **M6** | Phase 7：Loki + Promtail + Grafana 面板 | 3-4h | P3（可延后） |

---

## 五、立即执行的 Checklist

按顺序执行，今晚即可打通 P0：

- [ ] 宿主机创建目录：`mkdir -p /data/omichub_data/logs/{app,nginx,celery,snakemake,audit}`
- [ ] 设置权限：`chown -R 1000:1000 /data/omichub_data/logs`
- [ ] 修改 `docker-compose.prod.yml`，给 web/beat/worker/nginx 加上 `volumes` 挂载
- [ ] 给各服务容器环境变量加上 `SERVICE_NAME=web/beat/worker`
- [ ] 改造 `src/omichub/core/logging.py`，统一 sink 到 `/app/logs/`，开启 `enqueue=True`
- [ ] 重启生产环境，验证日志出现在 `/data/omichub_data/logs/` 下
- [ ] 确认 loguru 的 `rotation="50 MB"` 正常工作（或配置系统 `logrotate`）
- [ ] 测试容器重建后日志是否保留

---

## 六、附录：配置参考

### A. 宿主机目录创建脚本

```bash
#!/bin/bash
set -e

LOG_BASE="/data/omichub_data/logs"

mkdir -p ${LOG_BASE}/{app,nginx,celery,snakemake,audit}

# 假设容器以 UID 1000 运行
chown -R 1000:1000 ${LOG_BASE}
chmod -R 755 ${LOG_BASE}

echo "日志目录已创建并授权"
tree ${LOG_BASE}
```

### B. 系统 logrotate 配置（备用）

如果不用 loguru 内置轮转，可在宿主机配置：

```bash
# /etc/logrotate.d/omichub
/data/omichub_data/logs/app/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 0644 1000 1000
}
```

### C. 快速排查命令

```bash
# 实时跟踪应用日志
tail -f /data/omichub_data/logs/app/omichub.log

# 只看 ERROR
tail -f /data/omichub_data/logs/app/error.log

# 按任务查 Celery 日志
cat /data/omichub_data/logs/celery/tasks/{task_id}.log

# 统计今日 ERROR 数量
grep "ERROR" /data/omichub_data/logs/app/omichub.log | wc -l

# 审计日志快速检索
grep "user_123" /data/omichub_data/logs/audit/audit.log
```

---

> 文档版本：v1.0  
> 创建日期：2026-07-07  
> 关联文档：`report/04_可优化点与建议.md`、`todo.md`
