# OmicHub Web/Worker 跨服务器分离部署测试文档

> **文档版本**: v1.0  
> **编写日期**: 2026-07-11  
> **适用代码版本**: `feature/festival-easter-egg` 合并后 (`main` 分支 `61ee5f2` 及之后)  
> **目标**: 验证 OmicHub 的 Web 服务栈与 Celery Worker 计算栈可分别部署在不同物理/虚拟机，并通过共享数据库、Redis、存储完成端到端分析任务。

---

## 1. 当前架构现状说明

### 1.1 已有编排文件

| 文件 | 用途 | 当前部署模式 |
|------|------|--------------|
| `deploy/docker/docker-compose.yml` | Web 主栈：nginx / web / beat / flower / db / cache | 单机全栈 |
| `deploy/docker/docker-compose.worker.yml` | 计算 Worker 栈：仅 Celery Worker | 单机与主栈通过外部网络 `omichub_net` 互通 |
| `deploy/docker/docker-compose.prod.yml` | 生产覆盖：关闭 Flower 公网端口、增加 workers 数量等 | 与 `docker-compose.yml` 叠加使用 |

### 1.2 服务间通信方式

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Web 主栈 (Server A)                            │
│  ┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐  ┌─────────┐  │
│  │  nginx  │────▶│   web   │────▶│   db    │     │  cache  │  │  beat   │  │
│  │  :8888  │     │  :8000  │     │ postgres│     │  redis  │  │ celery  │  │
│  └─────────┘     └────┬────┘     └─────────┘     └────┬────┘  └─────────┘  │
│                       │                                │                    │
│                       │ 提交/查询任务                   │ Celery broker      │
│                       │                                │ result backend     │
└───────────────────────┼────────────────────────────────┼────────────────────┘
                        │                                │
                        │                                │ (跨机需真实 IP/域名)
                        ▼                                ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            Worker 计算栈 (Server B)                         │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                         omichub-worker                             │    │
│  │  celery -A omichub.infrastructure.celery_app.celery worker -Q analysis│   │
│  │                                                                    │    │
│  │  挂载: /data/omichub (共享存储)                                     │    │
│  │  挂载: /home/zj/miniconda3 (宿主 conda)                             │    │
│  │  挂载: /home/zj/pipeline (Snakemake 流程代码)                       │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.3 关键依赖

| 依赖项 | Web 侧 | Worker 侧 | 跨机要求 |
|--------|--------|-----------|----------|
| PostgreSQL | web 读写任务元数据、用户信息 | worker 读写任务状态/日志 | Worker 必须能访问 DB |
| Redis | Celery broker/result backend | 消费/回写任务 | Worker 必须能访问 Redis |
| `/data/omichub` | 上传文件、结果文件、任务目录 | Snakemake 工作目录、日志 | 必须共享（NFS/并行文件系统） |
| 流程监控事件 | Web 接收 `/api/v1/workflow-monitor/events` | Snakemake logger plugin POST 事件 | Worker 必须能访问 Web 的 ingest URL |

### 1.4 为什么当前配置不能直接跨机

当前 `docker-compose.yml` 中声明了外部网络 `omichub_net`（`external: true`），`docker-compose.worker.yml` 也加入该网络。该网络**只在单台 Docker Host 上有效**，跨服务器后 Worker 无法加入 Web 服务器的 Docker 网络。

因此跨机部署需要：
1. 将 `POSTGRES_HOST` / `REDIS_HOST` 从 Docker 服务名 (`db` / `cache`) 改为真实可访问的 IP/域名。
2. 将 `WORKFLOW_MONITOR_INTERNAL_URL` 从 `http://web:8000/api/v1/workflow-monitor` 改为 Web 服务器的真实地址。
3. 用 NFS 等共享存储替代本地 bind mount，使两台服务器看到同一份 `/data/omichub`。
4. 调整防火墙，放行 DB、Redis、Web API 端口。

---

## 2. 测试目标

1. **基础连通性**: Web 服务器与 Worker 服务器之间 DB、Redis、HTTP API 可达。
2. **任务投递**: 用户在 Web 前端提交分析任务后，任务成功进入 Redis `analysis` 队列。
3. **任务消费**: Worker 服务器上的 Celery Worker 能拉取并执行 `analysis` 队列任务。
4. **状态同步**: Worker 执行过程中任务状态、日志实时写回 PostgreSQL，Web 前端可查看。
5. **流程监控**: Snakemake logger plugin 的事件能跨机写入 Web 的 workflow-monitor。
6. **存储一致**: 上传文件、Snakemake 工作目录、结果文件在双机共享存储上保持一致路径。
7. **故障恢复**: Worker 重启/断网恢复后，未完成任务或新任务可正常消费。
8. **水平扩展**: 可在 Worker 服务器上水平扩容 Worker 实例数。

---

## 3. 测试环境规划

### 3.1 服务器角色

| 角色 | 示例 IP | 最低配置建议 | 备注 |
|------|---------|--------------|------|
| Web 服务器 | `10.0.0.10` | 4C8G | 跑 nginx/web/beat/flower/db/cache |
| Worker 服务器 | `10.0.0.20` | 16C64G | 跑 Celery Worker，承载 Snakemake 计算 |
| NFS 服务器 | `10.0.0.30` | 2C4G + 大容量存储 | 可与 Web 服务器合并，生产建议独立 |

> 本次测试以**最小双机**为例：NFS 复用 Web 服务器 (`10.0.0.10`)，Worker 服务器 (`10.0.0.20`) 挂载其 `/data/omichub`。

### 3.2 软件要求

- Docker >= 24.0
- Docker Compose >= 2.20
- Git
- NFS 客户端 (`nfs-common`)
- 用户 `zj` 的 UID/GID 与 Web 服务器一致（默认 `1000:1000`）
- Worker 服务器已预装 `/home/zj/miniconda3` 及 Snakemake 环境、`/home/zj/pipeline` 流程代码

### 3.3 网络要求

| 源 | 目标 | 端口 | 用途 |
|----|------|------|------|
| Worker `10.0.0.20` | Web `10.0.0.10` | TCP 5432 | PostgreSQL |
| Worker `10.0.0.20` | Web `10.0.0.10` | TCP 6379 | Redis |
| Worker `10.0.0.20` | Web `10.0.0.10` | TCP 8000 | Workflow monitor ingest |
| Web `10.0.0.10` | Worker `10.0.0.20` | TCP 2049 | NFS（如 NFS 在 Web 侧） |
| 用户浏览器 | Web `10.0.0.10` | TCP 8888 | Nginx 入口 |
| 用户浏览器 | Web `10.0.0.10` | TCP 5555 | Flower 监控（可选，建议内网/VPN） |

---

## 4. 部署前改造

### 4.1 共享存储：NFS 配置

#### 4.1.1 在 Web/NFS 服务器 (`10.0.0.10`) 上导出

```bash
sudo apt-get update
sudo apt-get install -y nfs-kernel-server

# 创建目录并设置属主为容器运行用户（默认 1000:1000）
sudo mkdir -p /data/omichub
sudo chown -R 1000:1000 /data/omichub
sudo chmod 755 /data/omichub

# 配置导出
cat << 'EOF' | sudo tee /etc/exports
/data/omichub 10.0.0.20(rw,sync,no_subtree_check,no_root_squash)
EOF

sudo exportfs -ra
sudo systemctl restart nfs-kernel-server
sudo systemctl enable nfs-kernel-server
```

#### 4.1.2 在 Worker 服务器 (`10.0.0.20`) 上挂载

```bash
sudo apt-get update
sudo apt-get install -y nfs-common

sudo mkdir -p /data/omichub
sudo mount -t nfs 10.0.0.10:/data/omichub /data/omichub

# 验证
ls -la /data/omichub
df -h /data/omichub

# 开机自动挂载
echo "10.0.0.10:/data/omichub /data/omichub nfs defaults,_netdev 0 0" | sudo tee -a /etc/fstab
```

### 4.2 防火墙配置

#### 4.2.1 Web 服务器 (`10.0.0.10`)

```bash
# 允许 Worker 访问 DB / Redis / Web API
sudo ufw allow from 10.0.0.20 to any port 5432,6379,8000 proto tcp
# 允许 Worker 访问 NFS
sudo ufw allow from 10.0.0.20 to any port 2049 proto tcp
# Nginx 入口
sudo ufw allow 8888/tcp
# Flower（仅内网）
sudo ufw allow from 10.0.0.0/8 to any port 5555 proto tcp
```

#### 4.2.2 Worker 服务器 (`10.0.0.20`)

```bash
# 允许 NFS 回连端口（可选，视内核版本可能不需要）
sudo ufw allow from 10.0.0.10 to any port 2049 proto tcp
# 允许出站访问 Web 服务器端口（通常默认允许）
```

### 4.3 环境变量改造

#### 4.3.1 复制并修改 `.env`

Web 服务器与 Worker 服务器使用同一份 `.env`，但部分变量需要显式覆盖真实 IP。

```bash
# 在代码根目录
cp .env .env.prod-cross-server
```

关键修改项（示例）：

```env
# ===== 应用 =====
APP_ENV=production
APP_SECRET_KEY=your-random-secret-key-here
JWT_SECRET_KEY=your-jwt-secret-key-here

# ===== 数据库 =====
# Web 侧：仍可用 db（Docker 服务名），Worker 侧必须改为 10.0.0.10
POSTGRES_HOST=10.0.0.10
POSTGRES_PORT=5432
POSTGRES_USER=omichub
POSTGRES_PASSWORD=your-strong-password
POSTGRES_DB=omichub

# ===== Redis =====
# Worker 侧必须改为 10.0.0.10
REDIS_HOST=10.0.0.10
REDIS_PORT=6379
REDIS_PASSWORD=your-strong-redis-password
REDIS_DB=0

# 显式指定 Celery broker/backend，避免自动组装时用到旧默认值
CELERY_BROKER_URL=redis://:your-strong-redis-password@10.0.0.10:6379/1
CELERY_RESULT_BACKEND=redis://:your-strong-redis-password@10.0.0.10:6379/2

# ===== 流程监控（关键） =====
WORKFLOW_MONITOR_INGEST_TOKEN=your-secure-random-token
OMICHUB_WORKFLOW_MONITOR_TOKEN=your-secure-random-token
# Worker 侧必须改为 Web 服务器真实地址
WORKFLOW_MONITOR_INTERNAL_URL=http://10.0.0.10:8000/api/v1/workflow-monitor

# ===== AI Provider 加密 =====
AI_PROVIDER_KEY_ENCRYPTION_KEY=your-fernet-key

# ===== 其他保持与现有 .env 一致 =====
AL_API_KEY=...
ARK_API_KEY=...
```

> 生产环境 `APP_ENV=production` 时，`src/omichub/core/config.py` 会强制校验 `APP_SECRET_KEY`、`JWT_SECRET_KEY`、`REDIS_PASSWORD`、`AI_PROVIDER_KEY_ENCRYPTION_KEY`、`WORKFLOW_MONITOR_INGEST_TOKEN` 非空且非默认值。

### 4.4 Docker Compose 改造

跨机部署时，直接使用原 `docker-compose.yml` 与 `docker-compose.worker.yml` 会有两个冲突点：
1. `omichub_net` 被声明为 `external: true`，Worker 侧无法加入 Web 侧的网络。
2. Worker 侧不再需要连接 `db` / `cache` 服务名，而是直接连 IP。

因此，建议创建一份跨机专用的覆盖文件。

#### 4.4.1 Web 服务器覆盖文件：`deploy/docker/docker-compose.cross-web.yml`

```yaml
# 跨机部署：Web 主栈覆盖
# 用法：docker compose -f docker-compose.yml -f docker-compose.cross-web.yml up -d
services:
  web:
    environment:
      - APP_ENV=production
      - APP_DEBUG=false
      - POSTGRES_HOST=db
      - REDIS_HOST=cache
      - SERVICE_NAME=web
      # Web 在本机仍可用服务名，但对外暴露 Workflow monitor 需用 0.0.0.0
    command: uvicorn omichub.main:app --host 0.0.0.0 --port 8000 --workers 4
    volumes:
      # 生产不挂载源码，使用镜像内代码
      - /data/omichub:/data/omichub
      - /data/omichub/logs/app:/app/logs
    ports:
      # 跨机场景 Worker 需要访问 8000 端口
      - "10.0.0.10:8000:8000"

  db:
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
    ports:
      # 仅允许 Worker 访问，绑定内网 IP
      - "10.0.0.10:5432:5432"

  cache:
    command: redis-server --requirepass ${REDIS_PASSWORD}
    ports:
      # 仅允许 Worker 访问，绑定内网 IP
      - "10.0.0.10:6379:6379"

  beat:
    environment:
      - POSTGRES_HOST=db
      - REDIS_HOST=cache

  flower:
    environment:
      - REDIS_HOST=cache
    ports:
      - "10.0.0.10:5555:5555"

# Web 栈不再使用外部 omichub_net，改为普通 bridge
networks:
  omichub_net:
    external: false
    driver: bridge
```

#### 4.4.2 Worker 服务器覆盖文件：`deploy/docker/docker-compose.cross-worker.yml`

```yaml
# 跨机部署：Worker 计算栈覆盖
# 用法：docker compose -f docker-compose.worker.yml -f docker-compose.cross-worker.yml up -d
services:
  worker:
    environment:
      - APP_ENV=production
      - POSTGRES_HOST=10.0.0.10
      - REDIS_HOST=10.0.0.10
      - CELERY_BROKER_URL=redis://:${REDIS_PASSWORD}@10.0.0.10:6379/1
      - CELERY_RESULT_BACKEND=redis://:${REDIS_PASSWORD}@10.0.0.10:6379/2
      - SERVICE_NAME=worker
      - OMICHUB_LOG_DIR=/app/logs
      - OMICHUB_CELERY_LOG_DIR=/data/omichub/logs/celery/tasks
      - OMICHUB_WORKFLOW_MONITOR_TOKEN=${OMICHUB_WORKFLOW_MONITOR_TOKEN:-${WORKFLOW_MONITOR_INGEST_TOKEN}}
      - WORKFLOW_MONITOR_INTERNAL_URL=http://10.0.0.10:8000/api/v1/workflow-monitor
    # 移除对 omichub_net 的依赖，Worker 侧独立 bridge
    networks:
      - default

# 覆盖原文件中的 external network，使用本机默认 bridge
networks:
  omichub_net:
    external: false
    driver: bridge
```

> 注意：Worker 镜像构建需要源码上下文，建议在两台服务器上使用同一 Git commit 构建，或在一台构建后推送到私有镜像仓库，另一台拉取。

### 4.5 镜像同步方案（推荐）

#### 方案 A：私有镜像仓库（推荐）

```bash
# 在 Web 服务器构建并推送
docker compose -f deploy/docker/docker-compose.yml build
docker tag omichub-web:latest registry.internal/omichub/web:v1.0.0
docker tag omichub-worker:latest registry.internal/omichub/worker:v1.0.0
docker push registry.internal/omichub/web:v1.0.0
docker push registry.internal/omichub/worker:v1.0.0

# 在 Worker 服务器拉取
docker pull registry.internal/omichub/worker:v1.0.0
```

#### 方案 B：docker save / load

```bash
# Web 服务器
docker save omichub-web:latest omichub-worker:latest | gzip > omichub-images.tar.gz
scp omichub-images.tar.gz 10.0.0.20:/tmp/

# Worker 服务器
ssh 10.0.0.20 'gunzip -c /tmp/omichub-images.tar.gz | docker load'
```

---

## 5. 详细部署步骤

### 5.1 Web 服务器部署 (`10.0.0.10`)

```bash
# 1. 克隆代码（与 Worker 同 commit）
git clone <repo> /opt/omichub
cd /opt/omichub
git checkout main

# 2. 准备环境变量
cp .env.prod-cross-server .env

# 3. 创建运行目录
make docker-network
make docker-runtime-dirs

# 4. 构建前端
cd frontend && npm install && npm run build && cd ..

# 5. 构建镜像
docker compose -f deploy/docker/docker-compose.yml build

# 6. 启动 Web 主栈（跨机覆盖）
docker compose \
  -f deploy/docker/docker-compose.yml \
  -f deploy/docker/docker-compose.cross-web.yml \
  up -d

# 7. 等待迁移完成并检查健康
docker logs -f omichub-web
# 看到 "Application startup complete" 后 Ctrl+C

# 8. 初始化管理员（首次）
docker exec -it omichub-web python scripts/init_admin.py
```

### 5.2 Worker 服务器部署 (`10.0.0.20`)

```bash
# 1. 挂载 NFS（如 4.1.2 所示）

# 2. 克隆代码（与 Web 同 commit）
git clone <repo> /opt/omichub
cd /opt/omichub
git checkout main

# 3. 准备环境变量（与 Web 同一份 .env）
cp .env.prod-cross-server .env

# 4. 拉取或构建 Worker 镜像
# 若使用私有仓库：
docker pull registry.internal/omichub/worker:v1.0.0
# 或本地构建：
# docker compose -f deploy/docker/docker-compose.worker.yml build

# 5. 准备 Worker 运行目录
make docker-runtime-dirs

# 6. 启动 Worker 栈（跨机覆盖）
docker compose \
  -f deploy/docker/docker-compose.worker.yml \
  -f deploy/docker/docker-compose.cross-worker.yml \
  up -d

# 7. 查看 Worker 日志
docker logs -f omichub-worker
```

### 5.3 验证基础服务

#### 5.3.1 Web 健康检查

```bash
# 从任意机器
curl http://10.0.0.10:8000/health
# 预期: {"status":"ok"}

curl http://10.0.0.10:8888/health
# 预期: {"status":"ok"}
```

#### 5.3.2 Worker 到 DB/Redis 连通性

```bash
# 在 Worker 服务器进入 worker 容器
docker exec -it omichub-worker /bin/sh

# 测试 Redis
redis-cli -h 10.0.0.10 -p 6379 -a ${REDIS_PASSWORD} ping
# 预期: PONG

# 测试 PostgreSQL
psql postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@10.0.0.10:5432/${POSTGRES_DB} -c "SELECT 1;"
# 预期: 1

# 测试 Workflow monitor ingest
curl -X POST http://10.0.0.10:8000/api/v1/workflow-monitor/events \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${OMICHUB_WORKFLOW_MONITOR_TOKEN}" \
  -d '{"type":"ping","task_id":"test"}'
# 预期: 200 OK 或 202 Accepted
```

#### 5.3.3 Celery Worker 注册检查

```bash
# 在 Web 服务器或 Worker 服务器
docker exec omichub-web celery -A omichub.infrastructure.celery_app.celery inspect ping
# 预期: 至少一个 worker 回复 pong

docker exec omichub-web celery -A omichub.infrastructure.celery_app.celery inspect registered
# 预期: 包含 omichub.infrastructure.celery_app.tasks.analysis.run_snakemake

docker exec omichub-web celery -A omichub.infrastructure.celery_app.celery inspect active_queues
# 预期: Worker 消费 analysis 队列
```

---

## 6. 功能测试用例

### 测试 1：Web 前端访问与登录

| 步骤 | 操作 | 预期结果 |
|------|------|----------|
| 1.1 | 浏览器访问 `http://10.0.0.10:8888` | 页面加载正常，无 502/504 |
| 1.2 | 使用 init_admin 创建的账号登录 | 登录成功，跳转工作台 |
| 1.3 | 访问「任务中心」| 页面正常加载，无报错 |
| 1.4 | 访问「实验室知识库」| 文档列表正常显示 |

### 测试 2：任务提交与 Worker 消费

| 步骤 | 操作 | 预期结果 |
|------|------|----------|
| 2.1 | 在工作台选择 RNA-seq / ATAC-seq 流程，提交一个测试任务 | Web 返回任务 ID，状态为 `PENDING` |
| 2.2 | 在 Worker 服务器查看日志 `docker logs -f omichub-worker` | 出现 `Received task` 并开始执行 |
| 2.3 | 在 Web 前端刷新任务详情 | 状态变为 `RUNNING`，日志实时滚动 |
| 2.4 | 等待任务完成 | 状态变为 `SUCCESS` 或 `FAILED` |
| 2.5 | 检查 `/data/omichub/users/{uid}/results/{flow_id}/{task_id}/` | 在 Web 与 Worker 服务器上目录内容一致 |

### 测试 3：流程监控 (Workflow Monitor) 事件

| 步骤 | 操作 | 预期结果 |
|------|------|----------|
| 3.1 | 提交一个分析任务 | 任务进入 RUNNING |
| 3.2 | 打开浏览器 DevTools 或访问 `http://10.0.0.10:8888/api/v1/workflow-monitor/tasks/{task_id}/events` | 能看到 snakemake 事件流 |
| 3.3 | 在 Worker 容器内检查日志 | 无 `ConnectionError` 到 `10.0.0.10:8000` |
| 3.4 | 检查 Web 日志 `docker logs omichub-web` | 无 workflow-monitor 认证失败 401 |

### 测试 4：文件上传与共享存储一致性

| 步骤 | 操作 | 预期结果 |
|------|------|----------|
| 4.1 | 在 Web 前端上传一个样本文件（如 FASTQ） | 上传成功，进度条完成 |
| 4.2 | 在 Web 服务器检查 `/data/omichub/uploads/{user_id}/` | 文件存在且大小正确 |
| 4.3 | 在 Worker 服务器检查同一路径 | 文件存在且大小与 Web 侧一致 |
| 4.4 | 提交任务引用该文件 | 任务能正常读取文件 |

### 测试 5：任务失败与重试

| 步骤 | 操作 | 预期结果 |
|------|------|----------|
| 5.1 | 提交一个配置错误的任务（如错误的样本路径） | Worker 执行失败 |
| 5.2 | 在 Web 前端查看失败原因 | 能看到 stderr 摘要 |
| 5.3 | 修正配置后重新提交 | 新任务被 Worker 正常消费 |

### 测试 6：Worker 水平扩展

```bash
# 在 Worker 服务器
docker compose \
  -f deploy/docker/docker-compose.worker.yml \
  -f deploy/docker/docker-compose.cross-worker.yml \
  up -d --scale worker=3

# 验证
docker exec omichub-web celery -A omichub.infrastructure.celery_app.celery inspect ping
# 预期: 3 个 worker 实例回复
```

| 步骤 | 操作 | 预期结果 |
|------|------|----------|
| 6.1 | 扩容到 3 个 Worker | `inspect ping` 返回 3 个节点 |
| 6.2 | 并发提交 3 个任务 | 任务被分发到不同 Worker 并行执行 |
| 6.3 | 缩容回 1 个 Worker | 无任务丢失，运行中的任务继续执行 |

### 测试 7：Beat 定时任务

| 步骤 | 操作 | 预期结果 |
|------|------|----------|
| 7.1 | 确认 `omichub-beat` 容器在 Web 服务器运行 | `docker ps` 显示健康 |
| 7.2 | 等待 5 分钟 | `sandbox-recycle-expired` 任务触发 |
| 7.3 | 检查 beat 日志 | 定时任务正常调度，无 Redis 连接错误 |

### 测试 8：Flower 监控跨机 Worker

| 步骤 | 操作 | 预期结果 |
|------|------|----------|
| 8.1 | 浏览器访问 `http://10.0.0.10:5555`（需内网） | Flower 登录页正常 |
| 8.2 | 登录后查看 Workers 标签页 | 能看到 Worker 服务器上的 worker 节点 |
| 8.3 | 提交任务后查看 Tasks | 任务状态、队列长度实时更新 |

---

## 7. 性能与稳定性测试

### 7.1 并发任务压力测试

```bash
# 在 Web 服务器使用脚本连续提交 N 个任务
for i in $(seq 1 10); do
  curl -X POST http://10.0.0.10:8888/api/v1/tasks \
    -H "Authorization: Bearer <user_token>" \
    -H "Content-Type: application/json" \
    -d '{
      "flow_id": "rna_seq",
      "name": "concurrent-test-'$i'",
      "samples": [...]
    }'
done
```

| 指标 | 目标 |
|------|------|
| 10 个任务全部进入 RUNNING | 无队列积压 |
| Worker CPU/内存 | 不超过宿主机 80% |
| Web API 响应时间 | 提交接口 < 500ms |
| 任务完成时间 | 与单机部署差距 < 10%（网络开销） |

### 7.2 网络抖动测试

| 场景 | 操作 | 预期结果 |
|------|------|----------|
| Worker 与 Redis 断开 30 秒 | 在 Worker 侧断网 | Worker 重连后恢复消费，无任务丢失 |
| Worker 与 DB 断开 30 秒 | 在 Worker 侧断网 | 任务执行中无法更新状态，恢复后状态同步 |
| NFS 短暂不可达 | umount/mount | Snakemake 可能失败，新任务恢复后正常 |

### 7.3 Worker 重启测试

```bash
# Worker 服务器
docker restart omichub-worker

# 同时提交新任务
# 预期：重启完成后 Worker 重新注册并消费队列中未执行的任务
```

---

## 8. 故障演练

### 8.1 Worker 服务器宕机

| 步骤 | 操作 | 预期结果 |
|------|------|----------|
| 1 | 停止 Worker 容器 | `celery inspect ping` 无 Worker 响应 |
| 2 | 提交新任务 | 任务在 Redis `analysis` 队列中排队 |
| 3 | 恢复 Worker 容器 | Worker 自动拉取并执行队列中任务 |

### 8.2 Redis 不可用

| 步骤 | 操作 | 预期结果 |
|------|------|----------|
| 1 | 停止 cache 容器 | Web 提交任务时可能降级或报错 |
| 2 | 恢复 cache 容器 | Worker 重连，新任务正常消费 |

### 8.3 PostgreSQL 不可用

| 步骤 | 操作 | 预期结果 |
|------|------|----------|
| 1 | 停止 db 容器 | Web 健康检查失败，Worker 任务无法更新状态 |
| 2 | 恢复 db 容器 | 服务恢复，后续任务正常 |

### 8.4 NFS 共享存储断开

| 步骤 | 操作 | 预期结果 |
|------|------|----------|
| 1 | 在 Worker 侧 umount NFS | 正在运行的 Snakemake 任务因找不到目录失败 |
| 2 | remount NFS | 新任务可正常读写共享目录 |
| 3 | 检查任务结果一致性 | 失败任务保留在 DB，成功任务结果可见 |

---

## 9. 回滚方案

若跨机部署测试失败，可快速回滚到单机部署：

```bash
# 1. Worker 服务器停止并清理
cd /opt/omichub
docker compose \
  -f deploy/docker/docker-compose.worker.yml \
  -f deploy/docker/docker-compose.cross-worker.yml \
  down

# 2. Web 服务器停止跨机覆盖，恢复单机
docker compose \
  -f deploy/docker/docker-compose.yml \
  -f deploy/docker/docker-compose.cross-web.yml \
  down

# 恢复单机启动
docker compose -f deploy/docker/docker-compose.yml up -d
docker compose -f deploy/docker/docker-compose.worker.yml up -d

# 3. 恢复环境变量（如需要）
cp .env .env.prod-cross-server.bak
cp .env.single-server .env
```

---

## 10. 验收清单

| 检查项 | 状态 | 备注 |
|--------|------|------|
| Web 服务器 `docker ps` 全部健康 | ⬜ | |
| Worker 服务器 `docker ps` 全部健康 | ⬜ | |
| Worker 能 ping 通 Web 的 5432/6379/8000 | ⬜ | |
| NFS 在双机挂载且内容一致 | ⬜ | |
| 用户可登录 Web 前端 | ⬜ | |
| 可成功提交并执行至少一个分析任务 | ⬜ | |
| 任务状态、日志在前端实时更新 | ⬜ | |
| Workflow monitor 事件正常到达 Web | ⬜ | |
| Flower 能看到 Worker 节点 | ⬜ | |
| Worker 扩容/缩容无任务丢失 | ⬜ | |
| Worker 重启后恢复消费 | ⬜ | |
| 生产密钥已替换默认值 | ⬜ | |
| 防火墙仅开放必要端口 | ⬜ | |

---

## 11. 常见问题排查

### 11.1 Worker 无法连接 Redis

**现象**: Worker 日志反复出现 `ConnectionError: Error connecting to cache:6379` 或 `10.0.0.10:6379`。

**排查**:
```bash
# 在 Worker 容器内
docker exec -it omichub-worker /bin/sh
redis-cli -h 10.0.0.10 -p 6379 -a <password> ping

# 在 Web 服务器检查 Redis 监听
sudo ss -tlnp | grep 6379
# 应显示 10.0.0.10:6379，而不是 127.0.0.1:6379
```

**解决**: 确认 `docker-compose.cross-web.yml` 中 cache 端口绑定到 `10.0.0.10:6379`，防火墙放行。

### 11.2 Worker 无法连接 PostgreSQL

**现象**: `psycopg2.OperationalError: could not connect to server: Connection refused`。

**排查**:
```bash
# Web 服务器检查
docker exec omichub-db pg_isready -U omichub
sudo ss -tlnp | grep 5432
```

**解决**: 生产环境 `config.py` 会强制校验密钥；同时确认 `.env` 中 `POSTGRES_HOST=10.0.0.10`。

### 11.3 任务提交后 Worker 不消费

**现象**: 任务一直 `PENDING`，Flower 中 `analysis` 队列有积压但 Worker 数为空。

**排查**:
```bash
docker exec omichub-web celery -A omichub.infrastructure.celery_app.celery inspect active_queues
docker exec omichub-web celery -A omichub.infrastructure.celery_app.celery inspect ping
```

**可能原因**:
- Worker 命令缺少 `-Q analysis`（当前 `docker-compose.worker.yml` 已配置，检查是否被覆盖丢失）。
- Worker 连接到了错误的 Redis 库（broker/db 编号）。
- `task_default_queue` 被覆盖为 `celery`（检查环境变量）。

### 11.4 Workflow monitor 无事件

**现象**: 任务在 RUNNING，但 workflow-monitor 事件列表为空。

**排查**:
```bash
# Worker 容器内检查 monitor_config.yaml
cat /data/omichub/users/{uid}/results/{flow_id}/{task_id}/monitor_config.yaml
# 应显示 omichub_monitor_url: http://10.0.0.10:8000/api/v1/workflow-monitor/events

# 测试 ingest
curl -X POST http://10.0.0.10:8000/api/v1/workflow-monitor/events \
  -H "Authorization: Bearer <token>" \
  -d '{"type":"test"}'
```

**解决**: 确认 Worker 环境变量 `WORKFLOW_MONITOR_INTERNAL_URL=http://10.0.0.10:8000/api/v1/workflow-monitor`。

### 11.5 NFS 文件权限错误

**现象**: Worker 中 Snakemake 报错 `Permission denied`。

**排查**:
```bash
# 在 Worker 服务器
ls -la /data/omichub
id  # 确认当前 UID 为 1000

# 在 Web/NFS 服务器
ls -la /data/omichub
```

**解决**: 确保 NFS 导出选项包含 `no_root_squash` 且 UID/GID 一致；必要时在 Worker 服务器创建相同 UID 用户。

### 11.6 Worker 启动报 conda 路径错误

**现象**: `snakemake: command not found` 或 `--use-conda` 找不到环境。

**排查**:
```bash
docker exec -it omichub-worker /bin/sh
which snakemake
ls /home/zj/miniconda3/envs/snakemake/bin/snakemake
ls /data/omichub/.conda_envs
```

**解决**: 确认 Worker 服务器已预装 `/home/zj/miniconda3`，且 `docker-compose.worker.yml` 正确挂载；确认 `PATH` 环境变量包含 snakemake 路径。

---

## 12. 后续生产化建议

1. **数据库与 Redis 独立**: 测试阶段可放在 Web 服务器，生产建议单独部署或使用云托管 RDS / Redis。
2. **镜像仓库**: 建立内部 Harbor/ACR，避免 `docker save/load` 手动同步。
3. **配置管理**: 将 `.env` 拆分为 Web/Worker/Shared 三份，用 Ansible/Helm 管理，避免 IP 硬编码。
4. **日志聚合**: Worker 日志统一收集到 Loki / ELK，便于跨机排障。
5. **监控告警**: 为 DB、Redis、NFS、Worker 队列长度设置 Prometheus 告警。
6. **CI/CD**: 构建镜像 → 推仓库 → 双机滚动更新，实现自动化。

---

## 13. 附录：一键检查脚本

可在 Worker 服务器保存为 `check_worker_env.sh`：

```bash
#!/bin/bash
set -e
WEB_IP="10.0.0.10"
REDIS_PASSWORD="${REDIS_PASSWORD}"
POSTGRES_USER="${POSTGRES_USER:-omichub}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD}"
POSTGRES_DB="${POSTGRES_DB:-omichub}"

echo "=== Worker 环境连通性检查 ==="
echo "[1/5] 检查 NFS 挂载"
df -h /data/omichub

echo "[2/5] 检查 Redis"
redis-cli -h $WEB_IP -p 6379 -a "$REDIS_PASSWORD" ping

echo "[3/5] 检查 PostgreSQL"
PGPASSWORD=$POSTGRES_PASSWORD psql -h $WEB_IP -U $POSTGRES_USER -d $POSTGRES_DB -c "SELECT 1;"

echo "[4/5] 检查 Web API"
curl -sf http://$WEB_IP:8000/health

echo "[5/5] 检查 Celery Worker 注册"
docker exec omichub-worker celery -A omichub.infrastructure.celery_app.celery inspect ping

echo "=== 全部通过 ==="
```

---

**文档结束**
