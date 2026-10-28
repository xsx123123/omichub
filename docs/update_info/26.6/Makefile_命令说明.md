# Makefile 命令说明

本文档说明项目根目录 `Makefile` 中各个 `make` 命令的用途、依赖、常见使用流程和风险边界。

`Makefile` 主要承担四类工作：

- 本地开发：启动后端、Celery Worker、Celery Beat、Flower。
- 质量检查：运行测试、覆盖率、Ruff、Mypy。
- 数据库迁移：创建、执行、回滚、合并 Alembic 迁移。
- Docker 编排：启动、停止、重建主栈和独立 Worker 栈。

## 使用前提

在运行这些命令前，建议确认本机具备以下环境：

- `make`：执行本文件中的任务。
- `uv`：运行 Python 命令、测试、迁移和开发服务器。
- Docker 与 Docker Compose v2：运行 `docker compose ...` 相关命令。
- Node.js 与 npm：安装前端依赖、构建前端产物。
- 项目配置文件：例如 `.env`、数据库连接、Redis、外部服务密钥等。

常用入口：

```bash
make help
```

`make help` 会扫描 `Makefile` 中带有 `##` 注释的 target，并以列表形式展示可用命令。

## 命令总览

| 命令 | 用途 |
| --- | --- |
| `make help` | 显示所有带说明的 Makefile 命令 |
| `make dev` | 启动后端 FastAPI 开发服务器 |
| `make dev-worker` | 启动 Celery Worker |
| `make dev-beat` | 启动 Celery Beat 定时任务调度器 |
| `make dev-flower` | 启动 Flower 任务监控页面 |
| `make test` | 运行测试套件 |
| `make test-cov` | 运行测试并生成覆盖率报告 |
| `make lint` | 执行 Ruff 静态检查 |
| `make format` | 执行 Ruff 格式化和自动修复 |
| `make type-check` | 执行 Mypy 类型检查 |
| `make migrate` | 将数据库升级到最新 Alembic 版本 |
| `make migrate-new m="..."` | 基于模型变更生成新迁移 |
| `make migrate-rollback` | 回滚上一个数据库迁移 |
| `make migrate-merge` | 合并 Alembic 多分支并升级数据库 |
| `make docker-network` | 创建 Docker 外部网络 |
| `make docker-up` | 启动主栈 |
| `make docker-up-worker` | 启动独立 Worker 栈 |
| `make docker-up-all` | 启动主栈和 Worker 栈 |
| `make docker-down` | 停止主栈 |
| `make docker-down-worker` | 停止 Worker 栈 |
| `make docker-down-all` | 停止主栈和 Worker 栈 |
| `make docker-logs` | 查看主栈日志 |
| `make docker-logs-worker` | 查看 Worker 栈日志 |
| `make docker-clean` | 清理容器和孤儿容器，保留数据卷 |
| `make docker-purge` | 彻底清理容器、数据卷、网络、镜像和前端构建产物 |
| `make docker-start` | 清空后完整重建并启动全部服务 |
| `make frontend-install` | 安装前端依赖 |
| `make frontend-dev` | 启动前端开发服务器 |
| `make frontend-build` | 构建前端生产产物 |
| `make docker-reload` | 开发场景下重建前端并刷新 Docker 服务 |
| `make init-admin` | 初始化管理员账号 |
| `make init-cookies` | 初始化默认饼干定价策略 |
| `make check-alembic-heads` | 检测 Alembic 是否存在多分支 |
| `make check-migrations` | 静态检查 Alembic 迁移链完整性 |
| `make clean` | 清理 Python 缓存、测试缓存和覆盖率产物 |

## 本地开发命令

### `make dev`

启动后端开发服务器：

```bash
uv run uvicorn omichub.main:app --reload --host 0.0.0.0 --port 8000
```

适用场景：

- 本地调试后端 API。
- 需要热重载 Python 代码。
- 前端开发服务器通过 API 代理访问后端。

注意事项：

- 默认监听 `0.0.0.0:8000`。
- 依赖本地 Python 环境、数据库、Redis 和必要环境变量。
- 如果端口被占用，需要先停止已有服务或临时修改命令。

### `make dev-worker`

启动 Celery Worker：

```bash
uv run celery -A omichub.infrastructure.celery_app.celery worker --loglevel=info
```

适用场景：

- 本地处理异步任务。
- 调试下载、分析、后台处理等 Celery 任务。

注意事项：

- 需要 Redis 或当前配置中的 broker 可用。
- 如果只启动后端不启动 Worker，提交的后台任务可能会一直处于等待状态。

### `make dev-beat`

启动 Celery Beat：

```bash
uv run celery -A omichub.infrastructure.celery_app.celery beat --loglevel=info
```

适用场景：

- 本地调试定时任务。
- 验证周期任务是否按预期投递给 Worker。

注意事项：

- Beat 只负责调度任务，不负责真正执行任务。
- 一般需要同时运行 `make dev-worker`。

### `make dev-flower`

启动 Flower 监控服务：

```bash
uv run celery -A omichub.infrastructure.celery_app.celery flower --port=5555
```

适用场景：

- 查看 Celery Worker 状态。
- 查看任务执行历史、失败原因和队列情况。

默认端口：

- `5555`

## 测试与代码质量

### `make test`

运行完整测试：

```bash
uv run pytest tests/ -v
```

适用场景：

- 提交代码前验证后端测试。
- 修改服务层、API 层、任务逻辑后做回归检查。

### `make test-cov`

运行测试并生成覆盖率报告：

```bash
uv run pytest tests/ --cov=src/omichub --cov-report=term-missing --cov-report=html
```

产物：

- 终端覆盖率报告。
- `htmlcov/` HTML 覆盖率报告。

适用场景：

- 检查新增代码是否有测试覆盖。
- 做较大改动后评估测试盲区。

### `make lint`

执行 Ruff 静态检查：

```bash
uv run ruff check src/ tests/
```

适用场景：

- 检查代码风格和常见静态问题。
- 提交前快速发现明显错误。

### `make format`

执行格式化和自动修复：

```bash
uv run ruff format src/ tests/
uv run ruff check --fix src/ tests/
```

注意事项：

- 这个命令会修改文件。
- 建议在运行前确认工作区没有不希望被自动格式化的改动。

### `make type-check`

执行 Mypy 类型检查：

```bash
uv run mypy src/omichub/
```

适用场景：

- 修改核心服务、配置、schema、repository 后检查类型一致性。
- 在合并前发现接口签名或返回类型问题。

## 数据库迁移

### `make migrate`

执行数据库迁移到最新版本：

```bash
uv run alembic upgrade head
```

适用场景：

- 拉取新代码后同步数据库结构。
- 新增迁移文件后将数据库升级到最新状态。

### `make migrate-new m="migration name"`

创建新迁移：

```bash
uv run alembic revision --autogenerate -m "$(m)"
```

示例：

```bash
make migrate-new m="add cloud storage tables"
```

注意事项：

- `m` 参数必须提供，否则迁移名称为空。
- 自动生成后必须人工检查迁移内容，尤其是字段删除、索引变更、枚举变更和默认值。
- 生成迁移不等于执行迁移，仍需要运行 `make migrate`。

### `make migrate-rollback`

回滚上一个迁移：

```bash
uv run alembic downgrade -1
```

适用场景：

- 本地开发时撤回刚执行的迁移。
- 验证 downgrade 是否可用。

风险提示：

- 回滚可能删除字段、表或数据。
- 在共享数据库、生产数据库或有真实数据的环境中执行前必须先备份。

### `make migrate-merge`

合并 Alembic 多分支：

```bash
uv run alembic merge heads -m "auto-merge parallel branches"
uv run alembic upgrade head
```

适用场景：

- 多人并行开发后出现多个 Alembic head。
- `check-alembic-heads` 提示迁移树分叉。

注意事项：

- 合并前应确认多个 head 的迁移内容没有冲突。
- 合并后会继续执行 `alembic upgrade head`，数据库会被升级到最新版本。

### `make check-alembic-heads`

检测 Docker 主栈中的 Alembic 迁移是否存在多分支：

```bash
docker exec omichub-web alembic heads
```

行为：

- 等待 3 秒，给 `omichub-web` 容器启动时间。
- 在容器内执行 `alembic heads`。
- 如果检测到多个 `(head)`，输出修复命令。

适用场景：

- `docker-up` 或 `docker-up-all` 后自动检查迁移树。
- 登录、注册、接口调用出现数据库相关 500 错误时排查。

### `make check-migrations`

静态检查 Alembic 迁移链完整性：

```bash
uv run python scripts/check_migrations.py
```

适用场景：

- 不连接数据库，只检查迁移文件链路是否合理。
- 提交迁移文件前做本地校验。

## Docker 编排变量

`Makefile` 中定义了几个 Docker Compose 变量：

```make
COMPOSE_MAIN   := docker compose -f deploy/docker/docker-compose.yml
COMPOSE_WORKER := docker compose -f deploy/docker/docker-compose.worker.yml
COMPOSE_ALL    := docker compose -f deploy/docker/docker-compose.yml -f deploy/docker/docker-compose.worker.yml
DOCKER_NETWORK := omichub_net
SANDBOX_NETWORK := omichub-sandbox-net
```

含义：

- `COMPOSE_MAIN`：主栈 Compose 文件，通常包含 web、db、redis、nginx、beat、flower。
- `COMPOSE_WORKER`：独立计算节点 Worker 栈。
- `COMPOSE_ALL`：主栈和 Worker 栈组合操作。
- `DOCKER_NETWORK`：主服务跨栈通信网络，名称为 `omichub_net`。
- `SANDBOX_NETWORK`：终端沙盒网络，名称为 `omichub-sandbox-net`。

## Docker 生命周期命令

### `make docker-network`

创建 Docker 外部网络：

```bash
docker network create omichub_net
docker network create omichub-sandbox-net
```

特点：

- 幂等执行。
- 如果网络已存在，不会中断后续流程。

### `make docker-up`

启动主栈：

```bash
make docker-network
docker compose -f deploy/docker/docker-compose.yml up -d
make check-alembic-heads
```

主栈通常包含：

- Web 后端。
- 数据库。
- Redis。
- Nginx。
- Celery Beat。
- Flower。

### `make docker-up-worker`

启动独立 Worker 栈：

```bash
make docker-network
docker compose -f deploy/docker/docker-compose.worker.yml up -d
```

适用场景：

- 单独扩展或重启计算节点。
- 主栈已经运行，只需要补充 Worker。

### `make docker-up-all`

启动主栈和 Worker 栈：

```bash
make docker-network
docker compose -f deploy/docker/docker-compose.yml up -d
docker compose -f deploy/docker/docker-compose.worker.yml up -d
make check-alembic-heads
```

适用场景：

- 本地或服务器上一键启动完整系统。
- 部署后恢复全部服务。

### `make docker-down`

停止主栈：

```bash
docker compose -f deploy/docker/docker-compose.yml down
```

说明：

- 停止并删除主栈容器和默认网络。
- 通常不会删除命名数据卷。

### `make docker-down-worker`

停止 Worker 栈：

```bash
docker compose -f deploy/docker/docker-compose.worker.yml down
```

### `make docker-down-all`

停止主栈和 Worker 栈：

```bash
docker compose \
  -f deploy/docker/docker-compose.yml \
  -f deploy/docker/docker-compose.worker.yml \
  down
```

### `make docker-logs`

查看主栈日志：

```bash
docker compose -f deploy/docker/docker-compose.yml logs -f
```

适用场景：

- 查看 Web、Nginx、数据库、Redis、Beat、Flower 等主栈日志。
- 排查接口错误、启动失败、数据库连接失败。

### `make docker-logs-worker`

查看 Worker 栈日志：

```bash
docker compose -f deploy/docker/docker-compose.worker.yml logs -f
```

适用场景：

- 排查任务未执行、任务失败、队列消费异常。

### `make docker-clean`

清理容器和孤儿容器：

```bash
docker compose \
  -f deploy/docker/docker-compose.yml \
  -f deploy/docker/docker-compose.worker.yml \
  down --remove-orphans
```

特点：

- 保留数据卷。
- 不删除镜像。
- 适合清理已经不用的旧容器。

### `make docker-purge`

彻底清理 Docker 环境和前端构建产物。

该命令会执行以下操作：

- 停止并删除主栈与 Worker 栈容器。
- 删除 Compose 命名数据卷。
- 强制删除指定的 OmicHub 容器。
- 删除名称匹配 `docker_` 的数据卷。
- 删除 `omichub_net` 网络。
- 删除本地构建镜像。
- 删除 `frontend/dist`。

风险提示：

- 这是危险命令。
- 会删除数据库等持久化数据卷。
- 会删除本地镜像和前端构建产物。
- 执行后通常只能通过重新构建和重新初始化恢复。

建议只在以下场景使用：

- 本地开发环境彻底重置。
- Docker 状态严重混乱，需要干净重建。
- 明确确认没有需要保留的数据。

### `make docker-start`

彻底重建并启动全部服务：

```bash
make docker-purge
cd frontend && npm run build
docker compose -f deploy/docker/docker-compose.yml build --no-cache
docker compose -f deploy/docker/docker-compose.worker.yml build --no-cache
make docker-network
docker compose -f deploy/docker/docker-compose.yml up -d
docker compose -f deploy/docker/docker-compose.worker.yml up -d
make check-alembic-heads
```

行为：

- 先执行 `docker-purge`。
- 构建前端生产产物。
- 不使用缓存重新构建 Docker 镜像。
- 启动主栈和 Worker 栈。
- 检查 Alembic 多分支。

风险提示：

- 因为会先执行 `docker-purge`，所以也会删除数据卷。
- 不适合在有重要数据的环境中直接运行。

### `make docker-fix-permissions`

修复 `/data/omichub` 下由非 root 容器写入的运行目录权限：

```bash
make docker-fix-permissions
docker restart omichub-web omichub-worker omichub-beat
```

适用场景：

- 登录页提示“系统内部错误”，且 `docker logs omichub-web` 出现 `/app/logs/omichub.log` 权限错误。
- Worker 任务日志提示 `/data/omichub/logs/celery` 无法写入。
- 宿主目录由 root 创建后，非 root 的 web / worker 容器无法写入。

该目标不会删除数据，不会重建镜像，只调整日志、用户数据、上传、临时和 conda 运行目录的属主。

### `make docker-reload`

开发场景下刷新 Docker 服务：

```bash
make docker-network
make docker-runtime-dirs
docker ps -a --filter "name=omichub-" -q | xargs -r docker rm -f
docker build -t omichub/sandbox-terminal:latest tool_configs/terminal/docker/
cd frontend && npm run build
docker compose -f deploy/docker/docker-compose.yml up -d
docker compose -f deploy/docker/docker-compose.worker.yml up -d
make check-alembic-heads
```

适用场景：

- 前端代码更新后，需要重新构建 `frontend/dist` 并刷新 Docker 服务。
- 终端沙盒镜像有变化，需要重新构建镜像。
- 开发环境中需要快速重建容器，但不想执行 `docker-purge` 的完整清理。

注意事项：

- 会强制删除名称匹配 `omichub-` 的容器。
- 会重新构建终端沙盒镜像。
- 不会像 `docker-purge` 那样主动删除数据卷。

## 前端命令

### `make frontend-install`

安装前端依赖：

```bash
cd frontend && npm install
```

适用场景：

- 首次拉取项目后安装依赖。
- `package.json` 或 lock 文件变更后同步依赖。

### `make frontend-dev`

启动前端开发服务器：

```bash
cd frontend && npm run dev
```

适用场景：

- 调试 Vue 前端。
- 配合本地后端 `make dev` 联调。

### `make frontend-build`

构建前端生产版本：

```bash
cd frontend && npm run build
```

产物：

- `frontend/dist`

适用场景：

- Docker 主栈需要加载最新前端静态资源。
- 发布前验证前端可以生产构建。

## 初始化命令

### `make init-admin`

初始化管理员账号：

```bash
uv run python scripts/init_admin.py
```

适用场景：

- 首次部署后创建后台管理员。
- 本地重置数据库后重新建立管理员账号。

### `make init-cookies`

初始化默认饼干定价策略：

```bash
uv run python scripts/init_cookies.py
```

适用场景：

- 首次部署后写入默认积分或饼干策略。
- 重置数据库后恢复默认定价配置。

## 清理命令

### `make clean`

清理 Python 缓存和测试产物：

```bash
find . -type d -name __pycache__ -exec rm -rf {} +
find . -type f -name "*.pyc" -delete
rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov
```

会删除：

- `__pycache__` 目录。
- `.pyc` 文件。
- `.pytest_cache`
- `.mypy_cache`
- `.ruff_cache`
- `htmlcov`

适用场景：

- 清理本地缓存。
- 重新运行测试或类型检查前减少旧缓存影响。

## 常见工作流

### 本地前后端开发

首次安装前端依赖：

```bash
make frontend-install
```

启动后端：

```bash
make dev
```

另开终端启动前端：

```bash
make frontend-dev
```

如需异步任务能力，再启动 Worker：

```bash
make dev-worker
```

如需定时任务，再启动 Beat：

```bash
make dev-beat
```

如需查看 Celery 状态，再启动 Flower：

```bash
make dev-flower
```

### 本地完整 Docker 启动

```bash
make docker-up-all
```

启动后建议查看日志：

```bash
make docker-logs
make docker-logs-worker
```

如果提示 Alembic 多分支，按提示执行：

```bash
make migrate-merge
```

### 修改后端代码后的检查

```bash
make lint
make type-check
make test
```

如需覆盖率：

```bash
make test-cov
```

### 修改前端代码后刷新 Docker 环境

```bash
make frontend-build
make docker-reload
```

说明：

- `frontend-build` 单独验证前端构建。
- `docker-reload` 会重新构建前端并刷新 Docker 服务，因此在确定只使用 `docker-reload` 时，前一个命令可以省略。

### 创建并执行数据库迁移

生成迁移：

```bash
make migrate-new m="describe schema change"
```

检查生成文件后执行迁移：

```bash
make migrate
```

建议随后运行：

```bash
make check-migrations
make test
```

### 修复 Alembic 多分支

先确认当前状态：

```bash
make check-alembic-heads
```

如果确认多个 head 可以合并：

```bash
make migrate-merge
```

合并后建议检查迁移链：

```bash
make check-migrations
```

### 彻底重置本地 Docker 环境

仅在确认可以删除本地数据时执行：

```bash
make docker-start
```

该命令会先执行 `docker-purge`，因此会删除数据库卷、镜像和前端构建产物。

## 风险命令对比

| 命令 | 是否删除容器 | 是否删除数据卷 | 是否删除镜像 | 是否删除前端产物 | 推荐场景 |
| --- | --- | --- | --- | --- | --- |
| `make docker-down` | 是 | 否 | 否 | 否 | 停主栈 |
| `make docker-down-worker` | 是 | 否 | 否 | 否 | 停 Worker 栈 |
| `make docker-down-all` | 是 | 否 | 否 | 否 | 停完整系统 |
| `make docker-clean` | 是 | 否 | 否 | 否 | 清理容器和孤儿容器 |
| `make docker-reload` | 是，强制删除 `omichub-` 容器 | 否 | 不主动删除 | 会重新构建前端 | 开发刷新服务 |
| `make docker-purge` | 是 | 是 | 是 | 是 | 彻底重置 |
| `make docker-start` | 是 | 是 | 是 | 是 | 干净重建完整环境 |

## 常见问题

### `make help` 没显示新命令

`make help` 只显示带 `##` 注释的 target。

新增命令时建议写成：

```make
target-name: ## 命令说明
	command
```

### `make migrate-new` 生成了异常迁移

Alembic 自动生成迁移并不总是准确，尤其是以下情况：

- 字段重命名可能被识别为删除旧字段并新增字段。
- 枚举、默认值、索引、约束变化可能需要人工调整。
- 多个开发分支同时改迁移时可能产生多个 head。

处理方式：

- 人工检查 `alembic/versions/` 中的新迁移文件。
- 确认 upgrade 和 downgrade 都符合预期。
- 必要时手写迁移逻辑。

### Docker 启动后接口报数据库错误

优先检查迁移状态：

```bash
make check-alembic-heads
```

如果存在多个 head：

```bash
make migrate-merge
```

如果只是数据库未升级：

```bash
make migrate
```

### 前端改动没有在 Docker 环境生效

前端生产环境依赖 `frontend/dist`。

可以执行：

```bash
make docker-reload
```

或至少先构建前端：

```bash
make frontend-build
```

### Worker 没有消费任务

检查顺序：

1. 确认 Worker 是否启动：`make docker-logs-worker` 或 `make dev-worker`。
2. 确认 Redis 或 broker 是否可用。
3. 确认任务是否被正确投递。
4. 确认 Worker 所在环境是否有任务依赖的文件、工具和环境变量。

### `docker network create` 报网络已存在

`docker-network` 已经做了容错处理，网络存在时不会中断：

```make
docker network create $(DOCKER_NETWORK) 2>/dev/null || true
```

如果网络配置本身有问题，可以手动检查：

```bash
docker network ls
docker network inspect omichub_net
docker network inspect omichub-sandbox-net
```

## 维护建议

新增或修改 Makefile 命令时，建议遵守以下约定：

- 每个可公开使用的 target 都写 `##` 注释，保证 `make help` 可见。
- 新增 target 后同步更新 `.PHONY`，避免同名文件影响执行。
- 危险命令在名称和说明中明确标注风险。
- Docker 相关命令保持主栈、Worker 栈和全量栈三类入口清晰。
- 数据库迁移命令保持可回滚、可检查、可合并的闭环。
- 文档中的命令示例应与 `Makefile` 保持同步。

当前 `Makefile` 顶部 `.PHONY` 列表没有覆盖所有已定义 target，例如前端命令、部分开发命令和迁移检查命令。命令仍可执行，但后续维护时建议补齐，降低同名文件造成误判的风险。
