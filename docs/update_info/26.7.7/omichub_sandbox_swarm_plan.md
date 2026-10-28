# OmicHub 沙盒终端 Swarm 化改造方案

> **状态**: 规划阶段 | **目标**: 将单节点沙盒容器调度扩展为 Docker Swarm 多节点集群，实现核心服务与沙盒容器的物理隔离。

---

## 1. 改造动机

当前架构将 Web 服务、API 后端与沙盒容器部署在同一节点，存在以下瓶颈：

| 当前痛点 | 影响 |
|---------|------|
| 沙盒容器与核心服务争抢 CPU/内存/磁盘 I/O | 高峰期 API 响应延迟增加 |
| 单节点故障导致全平台不可用 | 无高可用能力 |
| 沙盒容器突破隔离后可直接访问本地核心服务 | 安全边界模糊 |
| 用户 workspace 绑定本地磁盘 | 无法横向扩展 Worker 节点 |

Swarm 化后，核心服务（Manager 节点）与沙盒容器（Worker 节点）实现**物理隔离**，同时具备水平扩展与高可用能力。

---

## 2. 目标架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Manager 节点（核心服务）                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐            │
│  │  Nginx   │  │ FastAPI  │  │  Redis   │  │ PostgreSQL│           │
│  │ (入口)   │  │ (API/WS) │  │ (Session)│  │ (持久化)  │           │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘            │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────┐      │
│  │  Docker Swarm Manager (调度决策 + Overlay 网络管理)       │      │
│  └─────────────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                           Overlay Network (加密)
                                    │
┌─────────────────────────────────────────────────────────────────────┐
│                      Worker 节点池（沙盒专用）                         │
│                                                                     │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐             │
│  │  Worker-01  │    │  Worker-02  │    │  Worker-N   │             │
│  │ ┌─────────┐ │    │ ┌─────────┐ │    │ ┌─────────┐ │             │
│  │ │ttyd容器 │ │    │ │ttyd容器 │ │    │ │ttyd容器 │ │             │
│  │ │(用户A)  │ │    │ │(用户B)  │ │    │ │(用户C)  │ │             │
│  │ └─────────┘ │    │ └─────────┘ │    │ └─────────┘ │             │
│  │ ┌─────────┐ │    │ ┌─────────┐ │    │ ┌─────────┐ │             │
│  │ │ttyd容器 │ │    │ │ttyd容器 │ │    │ │ttyd容器 │ │             │
│  │ │(用户D)  │ │    │ │(用户E)  │ │    │ │(用户F)  │ │             │
│  │ └─────────┘ │    │ └─────────┘ │    │ └─────────┘ │             │
│  └─────────────┘    └─────────────┘    └─────────────┘             │
│                                                                     │
│  共享挂载: /data/omichub/users (NFS / GlusterFS / CephFS)           │
│  安全策略: 无公网 IP、仅开放 Overlay 网络端口、AppArmor/Seccomp      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 3. 关键改造点

### 3.1 网络层：Overlay 加密网络

创建跨节点的加密 Overlay 网络，使 Manager 上的 API 可直接通过容器名解析并访问任意 Worker 上的 ttyd 容器。

```bash
# 在 Manager 节点执行
docker network create \
  --driver overlay \
  --attachable \
  --opt encrypted \
  --subnet 10.10.0.0/16 \
  omichub-sandbox-net
```

| 参数 | 说明 |
|------|------|
| `--driver overlay` | Swarm 跨节点覆盖网络 |
| `--attachable` | 允许独立容器（非 Swarm Service）加入网络，适配动态创建的 ttyd 会话容器 |
| `--opt encrypted` | VXLAN 加密，防止节点间流量被嗅探 |
| `--subnet` | 为 Overlay 网络划分子网，避免与宿主机网络冲突 |

### 3.2 存储层：共享文件系统

当前架构使用本地 `bind mount` 挂载用户 workspace，Swarm 多节点下必须改为共享存储，确保容器漂移到任意 Worker 时都能访问到同一套数据。

**推荐方案：NFS（最小可用）**

```yaml
# docker-compose.sandbox.yml
volumes:
  workspace:
    driver: local
    driver_opts:
      type: nfs
      o: addr=nfs-server,rw,nolock,soft
      device: ":/data/omichub/users"
```

**进阶方案：GlusterFS / CephFS**
- 适合多节点高可用、无单点故障场景
- 运维复杂度较高，建议在集群规模扩大后引入

### 3.3 调度层：节点约束与标签

通过 Docker 节点标签，强制沙盒容器仅调度到专用 Worker 节点，防止沙盒容器占用 Manager 资源。

```bash
# 给 Worker 节点打标签
docker node update --label-add sandbox=true worker-01
docker node update --label-add sandbox=true worker-02
```

创建容器时增加约束：

```bash
docker run \
  --network omichub-sandbox-net \
  --constraint 'node.role == worker' \
  --constraint 'node.labels.sandbox == true' \
  ...
```

### 3.4 WebSocket 代理改造

当前架构中，后端通过 Docker SDK 在本地创建容器，然后直连 `ws://localhost:{ttyd_port}`。Swarm 化后，ttyd 容器可能运行在任意 Worker 节点，后端需通过 Overlay 网络内部 DNS 解析访问。

**改造前（单节点）**

```python
# 端口映射 + localhost 直连
container = client.containers.run(
    image="omichub/sandbox-terminal:latest",
    ports={"7681/tcp": allocated_port},  # 宿主机端口映射
    ...
)
ws_url = f"ws://localhost:{allocated_port}/ws"
```

**改造后（Swarm 多节点）**

```python
# 去掉端口映射，使用 Overlay 网络内部主机名
container = client.containers.run(
    image="omichub/sandbox-terminal:latest",
    network="omichub-sandbox-net",
    hostname=f"ttyd-{session_id}",  # Overlay 网络内可解析
    # 不再映射端口到宿主机
    ...
)
# 后端通过容器名直接访问，前端无感知
ws_url = f"ws://ttyd-{session_id}:7681/ws"
```

> **注意**：前端 WebSocket 仍然先连接到后端 API，由后端 API 代理转发到目标容器，因此前端无需感知底层网络变化。

### 3.5 端口分配简化

Swarm 化后，ttyd 不再需要暴露到宿主机的 `20000-30000` 端口范围，Overlay 网络内部可直接通过 `容器名:7681` 访问，彻底消除端口冲突问题。

| 维度 | 改造前 | 改造后 |
|------|--------|--------|
| 端口管理 | 后端动态分配宿主机端口，需维护端口池 | 无需宿主机端口映射 |
| 访问方式 | `ws://{WORKER_IP}:{port}/ws` | `ws://ttyd-{session_id}:7681/ws` |
| 网络暴露 | 宿主机端口暴露到外部 | 仅 Overlay 内部可达 |

---

## 4. 代码修改清单

| 模块 | 文件路径 | 当前逻辑 | 改造后 |
|------|---------|---------|--------|
| 容器管理 | `docker_manager.py` | 使用 Docker SDK 本地 `client.containers.run()` | 支持连接远程 Docker Daemon 或通过 Swarm Manager 调度 |
| 容器管理 | `docker_manager.py` | 端口映射 `-p {host_port}:7681` | 去掉端口映射，使用 Overlay 网络内部通信 |
| 容器管理 | `docker_manager.py` | `bind` 挂载本地路径 `/data/omichub/users/{uid}` | 改为 `volume` 挂载共享存储（NFS/GlusterFS） |
| 会话服务 | `terminal_service.py` | 返回 `ws_url` 包含宿主机 IP + 动态端口 | 返回容器主机名作为 WebSocket 代理目标 |
| WebSocket 代理 | `api/v1/terminal.py` | 代理到 `localhost:{port}` | 代理到 `ttyd-{session_id}:7681` |
| 配置文件 | `terminal_config.yaml` | 单节点配置（内存、CPU、端口范围） | 增加 `swarm.enabled`、`swarm.worker_labels`、`swarm.network_name`、`swarm.storage_driver` |

---

## 5. 部署拓扑建议

### 5.1 最小可用集群（3 节点）

| 节点 | 角色 | 运行服务 | 标签 |
|------|------|---------|------|
| Node-1 | Manager | Nginx、FastAPI、PostgreSQL、Redis、Swarm Manager | — |
| Node-2 | Worker | 仅运行沙盒容器 | `sandbox=true` |
| Node-3 | Worker | 仅运行沙盒容器 | `sandbox=true` |
| NFS-Server | 存储 | 导出 `/data/omichub/users` | — |

### 5.2 扩展集群（N 节点）

- 增加 Manager 节点到 3 个，实现 Manager HA（Raft 共识）
- 横向增加 Worker 节点，自动负载均衡沙盒容器
- 存储层升级为 GlusterFS 或 CephFS，消除 NFS 单点

### 5.3 Worker 节点安全加固

```bash
# 仅允许 Overlay 子网流量 + SSH
ufw default deny incoming
ufw allow from 10.10.0.0/16
ufw allow 22/tcp
ufw enable

# 可选：Worker 节点仅保留内网 IP，无公网出口
# 所有对外流量通过 Manager 节点的 NAT/代理转发
```

---

## 6. 渐进式迁移路径

为避免一次性改造风险，建议分阶段实施：

### Phase 1：远程 Docker 验证（轻量过渡）

使用 Docker Context 将容器调度到远程 Worker，验证网络连通性与基本功能，不引入 Swarm 复杂度。

```bash
# 在 API 服务器添加远程 Docker 节点
docker context create worker-01 --docker "host=ssh://worker-01"
docker context use worker-01
```

```python
# docker_manager.py 中指定远程客户端
import docker
client = docker.DockerClient(base_url="ssh://worker-01")
```

**特点**：轻量、快速验证，但缺少自动调度、故障转移、服务发现。

### Phase 2：引入共享存储

在 Phase 1 基础上，将 NFS 挂载到所有 Worker 节点，解决 workspace 跨节点访问问题。此时仍使用 Docker Context，但已具备多节点数据一致性。

### Phase 3：完整 Swarm 化

- 初始化 Swarm 集群：`docker swarm init`
- 加入 Worker 节点：`docker swarm join --token ... manager-ip:2377`
- 创建 Overlay 网络：`docker network create ...`
- 改造 `docker_manager.py` 使用 Overlay 网络主机名通信
- 移除宿主机端口映射逻辑
- 上线并监控

---

## 7. 方案对比

| 维度 | 单节点 Docker | Docker Context（远程） | Docker Swarm（目标） |
|------|-------------|----------------------|-------------------|
| 隔离级别 | 逻辑隔离（namespace/cgroup） | 物理隔离（多节点） | 物理隔离（多节点） |
| 扩展性 | 垂直扩容（单机硬件上限） | 水平扩展（需手动选择节点） | 水平扩展（自动调度） |
| 高可用 | 单点故障 | 单点故障（Manager 仍单点） | Manager HA + Worker 冗余 |
| 服务发现 | 本地端口 + IP | 手动维护节点 IP | Overlay 网络内置 DNS |
| 存储 | 本地盘 | 需手动同步/NFS | 共享存储（NFS/GlusterFS） |
| 网络复杂度 | 低 | 中 | 中（Overlay 加密） |
| 运维成本 | 低 | 低 | 中 |
| 推荐阶段 | 当前 | Phase 1 过渡 | 长期目标 |

---

## 8. 待决策事项

- [ ] 共享存储选型：NFS（快速上线） vs GlusterFS（长期可靠）
- [ ] Worker 节点规格：CPU/内存配置，单节点最大并发容器数
- [ ] 会话亲和性：用户多次打开终端时，是否优先调度到同一 Worker（减少 NFS 缓存同步问题）
- [ ] 网络策略：是否启用 Overlay 网络加密（有性能开销，但提升安全性）
- [ ] 监控方案：Worker 节点资源监控、容器漂移告警、NFS 挂载状态检测

---

## 9. 相关文档

- [云端沙盒终端原始文档](./README.md)
- [Docker Swarm 官方文档](https://docs.docker.com/engine/swarm/)
- [Overlay 网络加密说明](https://docs.docker.com/network/overlay/#encrypt-traffic-on-an-overlay-network)

---

## 10. 待办事项（TODO）—— 基于当前架构的 Swarm 落地步骤

以下任务按依赖顺序排列，可直接作为迭代开发看板使用。前 4 项为**阻塞项**，完成后即可进入 Phase 1 验证；后续项可分批实施。

### Phase 0：前置准备（一次性）

| # | 任务 | 负责人 | 验收标准 |
|---|------|--------|----------|
| 0.1 | 在所有目标节点安装 Docker 并启用 Swarm 模式 | 运维 | `docker node ls` 能看到 Manager + Worker |
| 0.2 | 为 Worker 节点打标签 | 运维 | `docker node inspect worker-01` 可见 `sandbox=true` |
| 0.3 | 创建加密 Overlay 网络 | 运维 | `docker network ls` 可见 `omichub-sandbox-net`，`docker network inspect` 显示 `encrypted=true` |
| 0.4 | 部署 NFS/GlusterFS 并导出 `/data/omichub/users` | 运维 | 所有 Worker 可挂载并读写同一目录 |
| 0.5 | 配置 Worker 节点防火墙（仅允许 Overlay 子网 + SSH） | 运维 | `ufw status` 显示默认 deny，且 Worker 无公网暴露 |

### Phase 1：Docker Manager 远程化（最小过渡）

| # | 任务 | 涉及文件 | 验收标准 |
|---|------|----------|----------|
| 1.1 | 在 `TerminalDockerManager` 中支持可配置的 Docker Client base_url | `docker_manager.py` | 能通过环境变量 `DOCKER_HOST=ssh://worker-01` 或配置项 `docker.host` 连接远程 Daemon |
| 1.2 | 保留本地 `docker.from_env()` 作为 fallback | `docker_manager.py` | 未配置远程地址时，现有开发环境行为不变 |
| 1.3 | 验证远程创建容器后，`omichub-web` 仍能通过 Overlay 网络解析 `omichub-term-{uid[:8]}-{session_id}` | `terminal.py` | WebSocket 代理成功连到远程容器 |
| 1.4 | 更新 `tools/terminal/README.md` 中架构图，补充“远程 Docker Context”模式 | `README.md` | 文档与代码一致 |

### Phase 2：网络与端口改造（Swarm 原生通信）

| # | 任务 | 涉及文件 | 验收标准 |
|---|------|----------|----------|
| 2.1 | 移除 `docker_manager.py` 中的宿主机端口映射 `ports={"7681/tcp": port}` | `docker_manager.py` | 容器不再占用 20000-30000 宿主机端口 |
| 2.2 | 删除 `_allocate_port` / `_release_port` 端口池逻辑 | `docker_manager.py` | 代码中无端口范围配置依赖 |
| 2.3 | 将容器 hostname 从固定 `sandbox` 改为唯一标识 `ttyd-{session_id}`，并接入 Overlay 网络 | `docker_manager.py` | `docker inspect` 可见 `Hostname=ttyd-term_xxx`，且同网络内可解析 |
| 2.4 | 更新 `terminal.py` 的 WebSocket 代理目标：统一使用 `ws://ttyd-{session_id}:7681/ws` | `terminal.py` | 去掉 `/.dockerenv` 分支判断，本地开发也走 Overlay 网络（开发机加入 Swarm 或保留 override） |
| 2.5 | 同步更新 `terminal_service.py` 返回给前端的 `ws_url`：可返回空或保留兼容字段 | `terminal_service.py` | 前端不依赖 `ws_url` 中的端口信息 |

### Phase 3：存储层改造（共享文件系统）

| # | 任务 | 涉及文件 | 验收标准 |
|---|------|----------|----------|
| 3.1 | 将 `volumes={workspace_host: ...}` 的 bind mount 改为 named volume（NFS 驱动） | `docker_manager.py` | 容器无论调度到哪个 Worker，都能访问同一 workspace |
| 3.2 | 在 `terminal_config.yaml` 中新增 `swarm.storage_driver` / `swarm.storage_opts` 配置 | `terminal_config.yaml` | 不重启后端即可热切换存储驱动 |
| 3.3 | 验证容器漂移到另一 Worker 后，历史文件、conda env、git 仓库均保留 | 集成测试 | 用户无感知 |

### Phase 4：调度约束与资源隔离

| # | 任务 | 涉及文件 | 验收标准 |
|---|------|----------|----------|
| 4.1 | 在 `client.containers.run()` 中增加 Swarm 约束 | `docker_manager.py` | 容器只调度到 `node.labels.sandbox == true` 的 Worker |
| 4.2 | 限制单 Worker 最大并发容器数（通过 Swarm resource reservation 或后端配额） | `terminal_service.py` / `docker_manager.py` | 超载时优雅排队或拒绝 |
| 4.3 | 为沙盒容器配置 CPU/Memory reservation，避免 Worker 被耗尽 | `docker_manager.py` | `docker inspect` 可见 `Resources.Reservations` |

### Phase 5：配置与部署编排

| # | 任务 | 涉及文件 | 验收标准 |
|---|------|----------|----------|
| 5.1 | 在 `terminal_config.yaml` 中新增 `swarm` 配置段 | `terminal_config.yaml` | 包含 `enabled`、`network_name`、`worker_labels`、`storage_driver`、`remote_host` |
| 5.2 | 拆分 `deploy/docker/docker-compose.yml`：核心服务与沙盒 Worker 分离 | `docker-compose.yml` / 新增 `docker-compose.sandbox-worker.yml` | Manager 栈不运行沙盒容器，Worker 栈不运行 API/DB |
| 5.3 | 更新 `Makefile` 的 `docker-network` 目标，自动创建 Swarm Overlay 网络 | `Makefile` | `make docker-network` 幂等创建加密 Overlay 网络 |
| 5.4 | 更新 `entrypoint.sh`，在 Worker 节点跳过 Alembic 等 Manager 专属初始化 | `entrypoint.sh` | Worker 容器启动不报错 |

### Phase 6：安全与可观测性

| # | 任务 | 涉及文件 | 验收标准 |
|---|------|----------|----------|
| 6.1 | Worker 节点禁止公网访问，仅通过 Manager NAT/代理出站 | 运维脚本 | 安全扫描通过 |
| 6.2 | 添加 Worker 节点资源监控（CPU / 内存 / 容器数 / NFS 挂载状态） | 新增监控配置 | Grafana/Prometheus 或现有日志告警可用 |
| 6.3 | 添加沙盒容器漂移告警：容器在 Worker 间迁移时触发通知 | 监控 | 告警通道打通 |
| 6.4 | 使用 Docker Secrets 管理 SSH 私钥或 TLS 证书（如使用远程 Docker TLS） | 部署脚本 | 密钥不落盘 |

### Phase 7：迁移与验证

| # | 任务 | 验收标准 |
|---|------|----------|
| 7.1 | 在测试环境按新 compose 部署 3 节点集群（1 Manager + 2 Worker + NFS） | 功能测试通过 |
| 7.2 | 验证用户可在不同 Worker 上同时打开多个终端 | 会话列表正常，WebSocket 连通 |
| 7.3 | 验证容器漂移后用户 workspace 数据一致性 | 文件修改在迁移后可见 |
| 7.4 | 压测：模拟 N 并发会话，观察 Manager API 响应延迟与 Worker 资源使用 | 达到预期吞吐 |
| 7.5 | 编写迁移手册：从单节点升级到 Swarm 的零停机步骤 | 文档归档 |

---

> 最后更新：2026-07-07
