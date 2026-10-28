# OmicHub 云端沙盒终端（Web Terminal）实现文档

> **版本**: v1.0  
> **状态**: 设计阶段  
> **目标**: 在 OmicHub 生信工具箱中集成即用即毁的隔离容器终端，支持用户挂载个人工作目录进行命令行操作，同时确保零 root 权限、零持久化污染。

---

## 目录

1. [项目概述](#1-项目概述)
2. [架构设计](#2-架构设计)
3. [安全策略详解](#3-安全策略详解)
4. [后端实现](#4-后端实现)
5. [前端实现](#5-前端实现)
6. [Docker 镜像构建](#6-docker-镜像构建)
7. [YAML 配置规范](#7-yaml-配置规范)
8. [部署与运维](#8-部署与运维)
9. [风险矩阵与应对](#9-风险矩阵与应对)
10. [迭代路线图](#10-迭代路线图)

---

## 1. 项目概述

### 1.1 背景与动机

OmicHub 作为一站式生信分析平台，目前提供了丰富的 GUI 工具（FASTQ 质控、BLAST、火山图、KEGG 富集等）。然而，部分高阶用户和复杂流程需要：

- 直接调用命令行工具（如 `samtools`、`bedtools`、`bcftools`）进行自定义参数分析
- 在隔离环境中调试 Pipeline 脚本
- 快速查看、预处理上传的数据文件
- 执行平台尚未 GUI 化的生信软件

**云端沙盒终端** 的引入，在不破坏平台安全边界的前提下，赋予用户受控的命令行自由度。

### 1.2 核心设计原则

| 原则 | 说明 |
|------|------|
| **即用即毁** | 容器退出后自动销毁，不留任何进程、文件系统残留 |
| **零 Root** | 全程使用 Rootless Docker，容器内外均以非特权用户运行 |
| **目录隔离** | 仅挂载用户个人工作目录，禁止访问宿主机系统路径及其他用户数据 |
| **资源受限** | 内存、CPU、进程数、磁盘均有硬上限，防止单用户耗尽资源 |
| **配置驱动** | 所有参数通过 YAML 文件管理，与 OmicHub 现有架构保持一致 |

### 1.3 术语表

| 术语 | 定义 |
|------|------|
| **Session** | 一次终端会话，对应一个运行中的 Docker 容器实例 |
| **Sandbox** | 隔离容器环境，包含预装的生信工具链和受限资源 |
| **Workspace** | 用户持久化目录，挂载到容器内，会话结束后数据保留 |
| **Tmpfs** | 内存文件系统，用于容器内部临时写入，随容器销毁 |
| **Rootless Docker** | 以普通用户身份运行 Docker Daemon，无需 root 权限 |

---

## 2. 架构设计

### 2.1 整体架构图

```
+-------------------------------------------------------------+
|                        用户浏览器                            |
|  +------------------------------------------------------+  |
|  |  OmicHub 前端 (React + Arco Design + xterm.js)       |  |
|  |  - 终端页面 / 浮动面板 / 全屏模式                      |  |
|  |  - WebSocket 连接管理                                 |  |
|  +------------------+-------------------------------+     |  |
+----------------------|-------------------------------------+
                       | HTTPS / WSS
                       v
+-------------------------------------------------------------+
|                     Nginx 反向代理                           |
|  - 路由: /api/terminal/* -> OmicHub Backend                |
|  - 路由: /ws/terminal/*  -> WebSocket 代理                 |
|  - JWT 鉴权校验                                            |
+----------------------+--------------------------------------+
                       |
                       v
+-------------------------------------------------------------+
|                  OmicHub Backend (Python/FastAPI)            |
|  +--------------+  +--------------+  +------------------+  |
|  |  Terminal    |  |  Docker      |  |  Session         |  |
|  |  API Router  |  |  Manager     |  |  Monitor         |  |
|  |  - 创建会话  |  |  - 容器生命周期|  |  - 空闲检测      |  |
|  |  - 查询状态  |  |  - 资源配额   |  |  - 自动销毁      |  |
|  |  - 销毁会话  |  |  - 端口分配   |  |  - 日志审计      |  |
|  +--------------+  +--------------+  +------------------+  |
+----------------------+--------------------------------------+
                       | Unix Socket / REST
                       v
+-------------------------------------------------------------+
|              Rootless Docker Daemon (per user)               |
|  - Socket: /run/user/<UID>/docker.sock                     |
|  - 用户级命名空间隔离                                        |
+----------------------+--------------------------------------+
                       |
           +-----------+-----------+
           v                       v
+------------------+    +------------------+
|  Sandbox Container|    |  Sandbox Container|
|  (User A)         |    |  (User B)         |
|  - ttyd @ :7681   |    |  - ttyd @ :7682   |
|  - 挂载 workspace |    |  - 挂载 workspace |
|  - 资源限制 512m  |    |  - 资源限制 512m  |
+------------------+    +------------------+
```

### 2.2 数据流

```
1. 用户点击启动沙盒终端
   -> 前端 POST /api/terminal/sessions
   -> 后端验证 JWT + 检查用户配额
   -> Docker Manager 启动容器（rootless 模式）
   -> 返回 {session_id, ws_url, expires_at}

2. 前端 xterm.js 连接 ws_url
   -> Nginx 代理 WebSocket -> 容器内 ttyd
   -> 用户获得交互式 bash

3. 用户输入命令
   -> 命令在容器内执行
   -> 文件操作仅影响挂载的 workspace 和 tmpfs
   -> 标准输出通过 WebSocket 实时返回前端

4. 会话结束（用户主动关闭 / 超时 / 断开）
   -> Session Monitor 触发销毁
   -> Docker Manager 执行 docker stop + --rm
   -> 容器彻底消失，workspace 数据保留在宿主机
```

---

## 3. 安全策略详解

### 3.1 Rootless Docker 部署

OmicHub 服务器上为每个用户启用独立的 rootless Docker 环境：

```bash
# 以 omichub 用户身份安装 rootless docker
$ dockerd-rootless-setuptool.sh install

# 验证：docker daemon 以普通用户运行
$ ps aux | grep dockerd
omichub   1234  0.1  1.2  123456  7890 ?  Ssl  10:00  0:02 dockerd --rootless

# 验证 socket 位置
$ ls -la /run/user/$(id - u)/docker.sock
srw-rw---- 1 omichub omichub 0 Jul  7 10:00 /run/user/1001/docker.sock
```

**安全收益**：
- 容器逃逸后，攻击者仅获得 `omichub` 用户权限，无法触及 root
- Docker socket 位于用户命名空间内，天然隔离多租户

### 3.2 容器运行时安全参数

```bash
docker run \
  --rm \                                    # 退出即销毁
  --read-only \                             # 根文件系统只读
  --tmpfs /tmp:rw,noexec,nosuid,size=100m \ # 临时可写区，禁止执行，限制大小
  --tmpfs /home/omichub/.cache:rw,noexec,nosuid,size=50m \
  --cap-drop ALL \                          # 丢弃所有 Linux capabilities
  --security-opt no-new-privileges=true \   # 禁止进程提升权限
  --security-opt seccomp=omichub-terminal.json \ # 自定义 seccomp 策略
  --memory 512m \                           # 内存硬限制
  --memory-swap 512m \                      # 禁止 swap（防止 OOM 绕过）
  --cpus 1.0 \                              # CPU 限制
  --pids-limit 100 \                        # 进程数限制（防 fork bomb）
  --user 1000:1000 \                        # 容器内以非 root 运行
  --network omichub-sandbox-net \           # 隔离桥接网络
  --hostname sandbox \                      # 统一 hostname，避免信息泄露
  -v /data/omichub/users/<user_id>/workspace:/home/omichub/workspace:rw \
  -v /data/omichub/users/<user_id>/tmp:/home/omichub/tmp:rw \
  omichub/sandbox-terminal:latest
```

### 3.3 目录挂载白名单

| 宿主机路径 | 容器内路径 | 权限 | 持久化 | 说明 |
|-----------|-----------|------|--------|------|
| `/data/omichub/users/{uid}/workspace` | `/home/omichub/workspace` | `rw` | 是 | 用户工作区，数据保留 |
| `/data/omichub/users/{uid}/tmp` | `/home/omichub/tmp` | `rw` | 定期清理 | 临时计算区 |
| - | `/tmp` | `rw,noexec` | 否 | 容器内部 tmpfs，随容器销毁 |
| - | `/home/omichub/.cache` | `rw,noexec` | 否 | 工具缓存 tmpfs |

**禁止挂载项**（硬编码黑名单）：
- `/var/run/docker.sock`
- `/` 或 `/etc` 或 `/usr`
- 其他用户的 `/data/omichub/users/*`
- 宿主机环境变量文件（`.env`, `.bashrc` 等）

### 3.4 网络安全

```bash
# 创建隔离桥接网络
docker network create \
  --driver bridge \
  --subnet 172.28.0.0/16 \
  --gateway 172.28.0.1 \
  --opt com.docker.network.bridge.name=omichub-sandbox \
  omichub-sandbox-net

# 可选：限制出站连接（通过 iptables 或 docker network 内部 DNS 白名单）
# 仅允许访问 NCBI、Ensembl、KEGG 等生信常用域名
```

---

## 4. 后端实现

### 4.1 技术栈

- **框架**: FastAPI (Python 3.10+)
- **Docker SDK**: `docker-py` (连接 rootless socket)
- **WebSocket 代理**: 纯 Nginx 代理，后端不持有 WebSocket 连接
- **任务调度**: `APScheduler` 或 `asyncio` 原生定时器（空闲检测）
- **数据存储**: Redis（会话状态缓存）+ PostgreSQL（审计日志持久化）

### 4.2 核心模块结构

```
omic_hub/
  backend/
    api/
      v1/
        terminal.py          # FastAPI Router
    services/
      docker_manager.py        # 容器生命周期管理
      session_monitor.py       # 会话监控与自动销毁
      port_allocator.py        # 动态端口分配
    models/
      terminal.py              # Pydantic 数据模型
    schemas/
      terminal.yaml            # 运行时配置（与 general.yaml 合并）
    utils/
      security_validator.py    # 挂载路径校验、命令审计
```

### 4.3 API 接口设计

#### 4.3.1 创建会话

```http
POST /api/v1/terminal/sessions
Authorization: Bearer <JWT>
Content-Type: application/json

{
  "image_tag": "latest",           // 可选，默认 latest
  "resources": {                   // 可选，覆盖默认配置
    "memory_mb": 1024,
    "cpu_cores": 2.0
  },
  "env_vars": {                    // 可选，注入环境变量
    "REF_GENOME": "/home/omichub/workspace/ref.fa"
  }
}
```

**响应**:
```json
{
  "session_id": "term_2v8x9k3m",
  "status": "running",
  "ws_url": "wss://omichub.example.com/ws/terminal/term_2v8x9k3m",
  "container_id": "a1b2c3d4e5f6",
  "expires_at": "2026-07-07T17:13:00Z",
  "resources": {
    "memory_mb": 512,
    "cpu_cores": 1.0,
    "pid_limit": 100
  },
  "mounted_volumes": [
    {
      "host": "/data/omichub/users/42/workspace",
      "container": "/home/omichub/workspace",
      "mode": "rw"
    }
  ]
}
```

#### 4.3.2 查询会话状态

```http
GET /api/v1/terminal/sessions/{session_id}
Authorization: Bearer <JWT>
```

**响应**:
```json
{
  "session_id": "term_2v8x9k3m",
  "status": "running",              // running | idle | stopping | stopped
  "container_id": "a1b2c3d4e5f6",
  "created_at": "2026-07-07T16:43:00Z",
  "last_activity_at": "2026-07-07T16:50:23Z",
  "idle_seconds": 120,
  "expires_at": "2026-07-07T17:13:00Z",
  "resource_usage": {
    "memory_mb": 128,
    "cpu_percent": 5.2
  }
}
```

#### 4.3.3 销毁会话

```http
DELETE /api/v1/terminal/sessions/{session_id}
Authorization: Bearer <JWT>
```

**响应**:
```json
{
  "session_id": "term_2v8x9k3m",
  "status": "stopped",
  "destroyed_at": "2026-07-07T16:55:00Z",
  "reason": "user_request"          // user_request | idle_timeout | resource_limit | system_shutdown
}
```

#### 4.3.4 列出用户活跃会话

```http
GET /api/v1/terminal/sessions
Authorization: Bearer <JWT>
```

### 4.4 Docker Manager 核心代码

```python
# backend/services/docker_manager.py

import docker
import random
import string
from pathlib import Path
from typing import Optional, Dict, List
from pydantic import BaseModel, Field
from datetime import datetime, timedelta


class ResourceQuota(BaseModel):
    memory_mb: int = Field(default=512, ge=256, le=4096)
    cpu_cores: float = Field(default=1.0, ge=0.5, le=4.0)
    pid_limit: int = Field(default=100, ge=50, le=500)
    tmpfs_size_mb: int = Field(default=100, ge=50, le=500)


class VolumeMount(BaseModel):
    host_path: str
    container_path: str
    mode: str = "rw"


class TerminalSession(BaseModel):
    session_id: str
    user_id: str
    container_id: Optional[str] = None
    host_port: Optional[int] = None
    status: str = "pending"  # pending, running, stopping, stopped
    created_at: str
    last_activity_at: str
    expires_at: str
    resources: ResourceQuota
    mounts: List[VolumeMount]
    ws_url: Optional[str] = None


class DockerManager:
    """
    Rootless Docker 容器管理器
    每个用户拥有独立的 Docker client（通过 /run/user/<UID>/docker.sock）
    """
    
    def __init__(self, config: dict):
        self.config = config
        self.base_port = config.get("terminal", {}).get("base_port", 20000)
        self.max_port = config.get("terminal", {}).get("max_port", 30000)
        self.allocated_ports: set = set()
        
    def _get_client(self, user_id: str) -> docker.DockerClient:
        """获取指定用户的 rootless Docker client"""
        # 实际部署中，通过用户 UID 映射 socket 路径
        # 这里简化处理，假设所有用户共享一个受限的 rootless daemon
        socket_path = f"/run/user/1000/docker.sock"  # 生产环境需动态获取 UID
        return docker.DockerClient(base_url=f"unix://{socket_path}")
    
    def _generate_session_id(self) -> str:
        """生成会话 ID: term_<8位随机>"""
        return "term_" + "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
    
    def _allocate_port(self) -> int:
        """分配随机高位端口"""
        while True:
            port = random.randint(self.base_port, self.max_port)
            if port not in self.allocated_ports:
                self.allocated_ports.add(port)
                return port
    
    def _validate_mount(self, mount: VolumeMount, user_id: str) -> bool:
        """校验挂载路径是否合法"""
        allowed_prefixes = [
            f"/data/omichub/users/{user_id}/",
        ]
        forbidden_patterns = [
            "/var/run/docker.sock",
            "/etc/",
            "/usr/",
            "/root/",
            "/proc/",
            "/sys/",
        ]
        
        host_path = Path(mount.host_path).resolve()
        
        # 检查是否在白名单内
        if not any(str(host_path).startswith(p) for p in allowed_prefixes):
            return False
        
        # 检查是否在黑名单内
        if any(str(host_path).startswith(f) for f in forbidden_patterns):
            return False
        
        return True
    
    def create_session(
        self, 
        user_id: str, 
        resources: Optional[ResourceQuota] = None,
        env_vars: Optional[Dict[str, str]] = None
    ) -> TerminalSession:
        """创建新的沙盒终端会话"""
        
        client = self._get_client(user_id)
        session_id = self._generate_session_id()
        port = self._allocate_port()
        
        # 使用默认或自定义资源配额
        quota = resources or ResourceQuota()
        
        # 构建挂载列表
        workspace_path = f"/data/omichub/users/{user_id}/workspace"
        tmp_path = f"/data/omichub/users/{user_id}/tmp"
        
        mounts = [
            VolumeMount(
                host_path=workspace_path,
                container_path="/home/omichub/workspace",
                mode="rw"
            ),
            VolumeMount(
                host_path=tmp_path,
                container_path="/home/omichub/tmp",
                mode="rw"
            ),
        ]
        
        # 校验所有挂载
        for mount in mounts:
            if not self._validate_mount(mount, user_id):
                raise ValueError(f"非法挂载路径: {mount.host_path}")
        
        # 构建 Docker 运行参数
        volumes = {}
        for mount in mounts:
            volumes[mount.host_path] = {
                "bind": mount.container_path,
                "mode": mount.mode
            }
        
        environment = {
            "USER_ID": user_id,
            "SESSION_ID": session_id,
            "HOME": "/home/omichub",
            "PS1": "\\u@omichub-sandbox:\\w\\$ ",
        }
        if env_vars:
            environment.update(env_vars)
        
        try:
            container = client.containers.run(
                image=self.config["terminal"]["image"],
                detach=True,
                auto_remove=True,  # --rm
                read_only=True,    # --read-only
                mem_limit=f"{quota.memory_mb}m",
                memswap_limit=f"{quota.memory_mb}m",  # 禁止 swap
                cpu_quota=int(quota.cpu_cores * 100000),
                cpu_period=100000,
                pids_limit=quota.pid_limit,
                cap_drop=["ALL"],
                security_opt=["no-new-privileges:true"],
                tmpfs={
                    "/tmp": f"rw,noexec,nosuid,size={quota.tmpfs_size_mb}m",
                    "/home/omichub/.cache": "rw,noexec,nosuid,size=50m",
                },
                volumes=volumes,
                ports={"7681/tcp": port},
                network="omichub-sandbox-net",
                hostname="sandbox",
                user="1000:1000",
                environment=environment,
                working_dir="/home/omichub/workspace",
                name=f"omichub-terminal-{user_id}-{session_id}",
                labels={
                    "app": "omichub-terminal",
                    "user_id": user_id,
                    "session_id": session_id,
                },
                # 健康检查：ttyd 进程存活检测
                healthcheck={
                    "test": ["CMD", "wget", "--quiet", "--tries=1", "--spider", "http://localhost:7681"],
                    "interval": 30000000000,  # 30s (nanoseconds)
                    "timeout": 10000000000,  # 10s
                    "retries": 3,
                },
            )
            
            session = TerminalSession(
                session_id=session_id,
                user_id=user_id,
                container_id=container.id,
                host_port=port,
                status="running",
                created_at=datetime.utcnow().isoformat() + "Z",
                last_activity_at=datetime.utcnow().isoformat() + "Z",
                expires_at=(datetime.utcnow() + timedelta(minutes=30)).isoformat() + "Z",
                resources=quota,
                mounts=mounts,
                ws_url=f"wss://{self.config['domain']}/ws/terminal/{session_id}",
            )
            
            return session
            
        except docker.errors.APIError as e:
            self.allocated_ports.discard(port)
            raise RuntimeError(f"容器启动失败: {e.explanation}")
    
    def destroy_session(self, user_id: str, session_id: str, reason: str = "user_request") -> dict:
        """销毁指定会话"""
        client = self._get_client(user_id)
        
        try:
            container = client.containers.get(f"omichub-terminal-{user_id}-{session_id}")
            container.stop(timeout=5)
            # --rm 会自动删除容器，无需手动 remove
            
            # 释放端口
            # 实际应从会话记录中读取 host_port
            
            return {
                "session_id": session_id,
                "status": "stopped",
                "destroyed_at": datetime.utcnow().isoformat() + "Z",
                "reason": reason,
            }
        except docker.errors.NotFound:
            return {
                "session_id": session_id,
                "status": "stopped",
                "destroyed_at": datetime.utcnow().isoformat() + "Z",
                "reason": "already_stopped",
            }
    
    def list_user_sessions(self, user_id: str) -> List[TerminalSession]:
        """列出用户所有活跃会话"""
        client = self._get_client(user_id)
        containers = client.containers.list(
            filters={
                "label": f"app=omichub-terminal",
                "label": f"user_id={user_id}",
            }
        )
        # 转换为 TerminalSession 对象列表
        return []
    
    def get_session_stats(self, user_id: str, session_id: str) -> dict:
        """获取容器资源使用统计"""
        client = self._get_client(user_id)
        container = client.containers.get(f"omichub-terminal-{user_id}-{session_id}")
        stats = container.stats(stream=False)
        
        memory_usage = stats["memory_stats"]["usage"] / (1024 * 1024)  # MB
        cpu_delta = stats["cpu_stats"]["cpu_usage"]["total_usage"] - stats["precpu_stats"]["cpu_usage"]["total_usage"]
        system_delta = stats["cpu_stats"]["system_cpu_usage"] - stats["precpu_stats"]["system_cpu_usage"]
        cpu_percent = (cpu_delta / system_delta) * 100.0 if system_delta > 0 else 0.0
        
        return {
            "memory_mb": round(memory_usage, 2),
            "cpu_percent": round(cpu_percent, 2),
            "pids": len(stats["pids_stats"].get("current", [])),
        }
```

### 4.5 Session Monitor 空闲检测

```python
# backend/services/session_monitor.py

import asyncio
from datetime import datetime, timedelta
from typing import Dict
import redis.asyncio as redis


class SessionMonitor:
    """
    会话监控器：跟踪终端活动，自动销毁空闲会话
    使用 Redis 存储会话心跳，支持多后端实例部署
    """
    
    def __init__(self, redis_client: redis.Redis, docker_manager):
        self.redis = redis_client
        self.docker = docker_manager
        self.idle_timeout = 1800  # 30 分钟
        self.disconnect_timeout = 300  # 断连 5 分钟后销毁
        self.check_interval = 60  # 每 60 秒检查一次
        
    async def heartbeat(self, session_id: str, user_id: str):
        """更新会话心跳时间"""
        key = f"terminal:heartbeat:{session_id}"
        await self.redis.setex(key, self.idle_timeout + 300, user_id)
    
    async def mark_disconnect(self, session_id: str, user_id: str):
        """标记会话 WebSocket 断开"""
        key = f"terminal:disconnect:{session_id}"
        await self.redis.setex(key, self.disconnect_timeout, user_id)
    
    async def remove_disconnect(self, session_id: str):
        """WebSocket 重连时移除断开标记"""
        await self.redis.delete(f"terminal:disconnect:{session_id}")
    
    async def run(self):
        """主循环：定期检查并销毁超时会话"""
        while True:
            await asyncio.sleep(self.check_interval)
            await self._check_idle_sessions()
            await self._check_disconnected_sessions()
    
    async def _check_idle_sessions(self):
        """检查空闲超时会话"""
        # 扫描所有心跳 key
        async for key in self.redis.scan_iter(match="terminal:heartbeat:*"):
            session_id = key.decode().split(":")[-1]
            ttl = await self.redis.ttl(key)
            
            # TTL 接近过期 = 长时间无心跳
            if ttl < 300:
                user_id = await self.redis.get(key)
                if user_id:
                    user_id = user_id.decode()
                    await self._destroy_session(user_id, session_id, "idle_timeout")
    
    async def _check_disconnected_sessions(self):
        """检查断连超时会话"""
        async for key in self.redis.scan_iter(match="terminal:disconnect:*"):
            session_id = key.decode().split(":")[-1]
            ttl = await self.redis.ttl(key)
            
            if ttl < 60:  # 即将过期
                user_id = await self.redis.get(key)
                if user_id:
                    user_id = user_id.decode()
                    await self._destroy_session(user_id, session_id, "disconnect_timeout")
    
    async def _destroy_session(self, user_id: str, session_id: str, reason: str):
        """执行销毁并清理 Redis"""
        try:
            result = self.docker.destroy_session(user_id, session_id, reason)
            await self.redis.delete(f"terminal:heartbeat:{session_id}")
            await self.redis.delete(f"terminal:disconnect:{session_id}")
            await self.redis.delete(f"terminal:session:{session_id}")
            
            # 记录审计日志
            await self.redis.lpush(
                f"terminal:audit:{user_id}",
                f"{datetime.utcnow().isoformat()} | {session_id} | {reason}"
            )
        except Exception as e:
            # 记录错误，但不中断监控循环
            print(f"销毁会话失败 {session_id}: {e}")
```

### 4.6 Nginx WebSocket 代理配置

```nginx
# /etc/nginx/conf.d/terminal.conf

upstream terminal_backend {
    least_conn;
    # 后端 FastAPI 实例
    server 127.0.0.1:8000;
}

# WebSocket 代理：将 /ws/terminal/<session_id> 转发到对应容器端口
location ~ ^/ws/terminal/(?P<session_id>term_[a-z0-9]+)$ {
    # JWT 鉴权（共享 OmicHub 统一鉴权）
    auth_request /api/v1/auth/verify;
    auth_request_set $auth_user $upstream_http_x_user_id;
    
    # 验证 session_id 属于当前用户
    # 可通过 auth_request 子请求或 Lua 脚本实现
    
    proxy_pass http://127.0.0.1:$terminal_port;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    
    # WebSocket 超时设置
    proxy_read_timeout 86400s;
    proxy_send_timeout 86400s;
    
    # 关键：连接断开时通知后端
    proxy_set_header X-Session-ID $session_id;
}

# 辅助：通过后端 API 查询 session_id 对应的端口
location /_internal/terminal_port {
    internal;
    proxy_pass http://terminal_backend/api/v1/terminal/sessions/$session_id/port;
    proxy_set_header Host $host;
}
```

> **注意**: 生产环境中建议用 **OpenResty + Lua** 或 **Nginx Plus** 动态解析 session_id -> port 映射，
> 避免静态配置。也可简化方案：后端启动容器时注册到 Consul/Etcd，Nginx 通过 DNS 服务发现。

---

## 5. 前端实现

### 5.1 技术栈

- **终端组件**: `xterm.js` (v5.x) + `xterm-addon-fit` + `xterm-addon-web-links`
- **UI 框架**: React 18 + Arco Design (与 OmicHub 现有设计一致)
- **WebSocket**: 原生 WebSocket API，支持自动重连
- **状态管理**: Zustand 或 React Context (轻量级)

### 5.2 组件结构

```
frontend/src/
  pages/
    Terminal/
      index.tsx                    # 终端页面（全屏/弹窗模式）
      components/
        TerminalCard.tsx         # 生信工具箱中的入口卡片
        XTerminal.tsx            # xterm.js 封装组件
        TerminalToolbar.tsx      # 工具栏（复制、粘贴、全屏、销毁）
        SessionInfo.tsx          # 会话信息面板（资源、剩余时间）
        FileExplorer.tsx         # 侧边文件浏览器（workspace 内容）
      hooks/
        useTerminalSession.ts    # 会话管理 Hook
        useWebSocket.ts          # WebSocket 连接管理
        useContainerStats.ts     # 轮询资源使用率
```

### 5.3 核心组件代码

#### 5.3.1 XTerminal 组件

```tsx
// frontend/src/pages/Terminal/components/XTerminal.tsx

import React, { useEffect, useRef, useCallback } from 'react';
import { Terminal } from 'xterm';
import { FitAddon } from 'xterm-addon-fit';
import { WebLinksAddon } from 'xterm-addon-web-links';
import 'xterm/css/xterm.css';

interface XTerminalProps {
  wsUrl: string;
  onData?: (data: string) => void;
  onConnectionChange?: (connected: boolean) => void;
}

const XTerminal: React.FC<XTerminalProps> = ({ wsUrl, onData, onConnectionChange }) => {
  const terminalRef = useRef<HTMLDivElement>(null);
  const termRef = useRef<Terminal | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const fitAddonRef = useRef<FitAddon | null>(null);
  const reconnectTimerRef = useRef<NodeJS.Timeout | null>(null);
  const heartbeatTimerRef = useRef<NodeJS.Timeout | null>(null);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      onConnectionChange?.(true);
      fitAddonRef.current?.fit();
      
      // 启动心跳
      heartbeatTimerRef.current = setInterval(() => {
        ws.send(JSON.stringify({ type: 'heartbeat' }));
      }, 30000);
    };

    ws.onmessage = (event) => {
      const data = event.data;
      if (typeof data === 'string') {
        // ttyd 直接发送 ANSI 数据
        termRef.current?.write(data);
      }
    };

    ws.onclose = () => {
      onConnectionChange?.(false);
      if (heartbeatTimerRef.current) {
        clearInterval(heartbeatTimerRef.current);
      }
      
      // 自动重连（最多 5 次）
      let attempts = 0;
      const tryReconnect = () => {
        if (attempts < 5) {
          attempts++;
          reconnectTimerRef.current = setTimeout(() => {
            termRef.current?.write('\r\n[断开连接，尝试重连...]\r\n');
            connect();
          }, 3000);
        } else {
          termRef.current?.write('\r\n[连接已断开，请刷新页面重试]\r\n');
        }
      };
      tryReconnect();
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      ws.close();
    };
  }, [wsUrl, onConnectionChange]);

  useEffect(() => {
    // 初始化 xterm
    const term = new Terminal({
      fontFamily: 'JetBrains Mono, Fira Code, monospace',
      fontSize: 14,
      theme: {
        background: '#1e1e1e',
        foreground: '#d4d4d4',
        cursor: '#d4d4d4',
        selectionBackground: '#264f78',
        black: '#000000',
        red: '#cd3131',
        green: '#0dbc79',
        yellow: '#e5e510',
        blue: '#2472c8',
        magenta: '#bc3fbc',
        cyan: '#11a8cd',
        white: '#e5e5e5',
      },
      cursorBlink: true,
      cursorStyle: 'block',
      scrollback: 10000,
      allowTransparency: false,
      macOptionIsMeta: true,  // macOS Option 键作为 Meta
    });

    const fitAddon = new FitAddon();
    const webLinksAddon = new WebLinksAddon();
    
    term.loadAddon(fitAddon);
    term.loadAddon(webLinksAddon);
    
    if (terminalRef.current) {
      term.open(terminalRef.current);
      fitAddon.fit();
    }

    termRef.current = term;
    fitAddonRef.current = fitAddon;

    // 用户输入转发到 WebSocket
    term.onData((data) => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(data);
      }
      onData?.(data);
    });

    // 窗口大小调整
    const handleResize = () => {
      fitAddon.fit();
      const { cols, rows } = term;
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({
          type: 'resize',
          cols,
          rows,
        }));
      }
    };
    window.addEventListener('resize', handleResize);

    // 建立连接
    connect();

    return () => {
      window.removeEventListener('resize', handleResize);
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
      if (heartbeatTimerRef.current) clearInterval(heartbeatTimerRef.current);
      wsRef.current?.close();
      term.dispose();
    };
  }, [connect, onData]);

  return (
    <div 
      ref={terminalRef} 
      style={{ 
        width: '100%', 
        height: '100%', 
        backgroundColor: '#1e1e1e',
        borderRadius: '4px',
        padding: '8px',
      }} 
    />
  );
};

export default XTerminal;
```

#### 5.3.2 TerminalCard（生信工具箱入口）

```tsx
// frontend/src/pages/Terminal/components/TerminalCard.tsx

import React, { useState } from 'react';
import { Card, Button, Modal, Message, Spin } from '@arco-design/web-react';
import { IconTerminal, IconFullscreen, IconDelete } from '@arco-design/web-react/icon';
import XTerminal from './XTerminal';
import { useTerminalSession } from '../hooks/useTerminalSession';

const TerminalCard: React.FC = () => {
  const [visible, setVisible] = useState(false);
  const [fullScreen, setFullScreen] = useState(false);
  const { session, loading, createSession, destroySession } = useTerminalSession();

  const handleOpen = async () => {
    try {
      await createSession();
      setVisible(true);
    } catch (error) {
      Message.error('启动沙盒终端失败，请稍后重试');
    }
  };

  const handleClose = async () => {
    if (session) {
      await destroySession(session.session_id);
      Message.success('沙盒终端已销毁');
    }
    setVisible(false);
    setFullScreen(false);
  };

  return (
    <>
      <Card
        className="tool-card"
        hoverable
        onClick={handleOpen}
        style={{ cursor: "pointer" }}
      >
        <div className="tool-card-content">
          <div className="tool-icon" style={{ background: "linear-gradient(135deg, #1e1e1e 0%, #333 100%)" }}>
            <IconTerminal style={{ fontSize: 32, color: "#0dbc79" }} />
          </div>
          <div className="tool-info">
            <h3>云端沙盒终端</h3>
            <p>隔离容器环境，预装常用生信工具，退出即销毁，数据仅保留在工作目录</p>
          </div>
          <IconFullscreen style={{ fontSize: 20, color: "#86909c" }} />
        </div>
      </Card>

      <Modal
        title={
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <IconTerminal style={{ color: "#0dbc79" }} />
            <span>沙盒终端 {session?.session_id}</span>
            {session && (
              <span style={{ fontSize: 12, color: "#86909c", marginLeft: "auto" }}>
                剩余时间: {session.remaining_minutes}分钟
              </span>
            )}
          </div>
        }
        visible={visible}
        onCancel={handleClose}
        footer={
          <div style={{ display: "flex", justifyContent: "space-between" }}>
            <Button type="secondary" onClick={() => setFullScreen(!fullScreen)}>
              {fullScreen ? '退出全屏' : '全屏模式'}
            </Button>
            <Button type="primary" status="danger" onClick={handleClose} icon={<IconDelete />}>
              销毁会话
            </Button>
          </div>
        }
        style={{ width: fullScreen ? "100vw" : 900 }}
        bodyStyle={{ 
          height: fullScreen ? "calc(100vh - 120px)" : 500,
          padding: 0,
          background: '#1e1e1e',
        }}
        wrapClassName={fullScreen ? "terminal-fullscreen" : ""}
        escToExit={false}  // 禁用 ESC 关闭，避免与 vim 冲突
      >
        {loading ? (
          <div style={{ display: "flex", justifyContent: "center", alignItems: "center", height: "100%" }}>
            <Spin size={40} tip="正在启动隔离容器..." />
          </div>
        ) : session?.ws_url ? (
          <XTerminal 
            wsUrl={session.ws_url} 
            onConnectionChange={(connected) => {
              if (!connected) {
                Message.warning('终端连接已断开');
              }
            }}
          />
        ) : (
          <div style={{ color: "#fff", padding: 20 }}>会话初始化失败</div>
        )}
      </Modal>
    </>
  );
};

export default TerminalCard;
```

#### 5.3.3 useTerminalSession Hook

```tsx
// frontend/src/pages/Terminal/hooks/useTerminalSession.ts

import { useState, useCallback, useRef, useEffect } from 'react';
import { request } from '@/utils/request';  // OmicHub 统一请求封装

interface SessionInfo {
  session_id: string;
  ws_url: string;
  status: string;
  expires_at: string;
  remaining_minutes: number;
  resources: {
    memory_mb: number;
    cpu_cores: number;
  };
}

export const useTerminalSession = () => {
  const [session, setSession] = useState<SessionInfo | null>(null);
  const [loading, setLoading] = useState(false);
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  const createSession = useCallback(async () => {
    setLoading(true);
    try {
      const res = await request.post('/api/v1/terminal/sessions', {
        resources: {
          memory_mb: 512,
          cpu_cores: 1.0,
        },
      });
      setSession(res.data);
      
      // 启动倒计时
      if (timerRef.current) clearInterval(timerRef.current);
      timerRef.current = setInterval(() => {
        setSession((prev) => {
          if (!prev) return null;
          const remaining = Math.max(0, 
            Math.floor((new Date(prev.expires_at).getTime() - Date.now()) / 60000)
          );
          return { ...prev, remaining_minutes: remaining };
        });
      }, 60000);
      
    } finally {
      setLoading(false);
    }
  }, []);

  const destroySession = useCallback(async (sessionId: string) => {
    await request.delete(`/api/v1/terminal/sessions/${sessionId}`);
    if (timerRef.current) clearInterval(timerRef.current);
    setSession(null);
  }, []);

  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, []);

  return { session, loading, createSession, destroySession };
};
```

---

## 6. Docker 镜像构建

### 6.1 Dockerfile

```dockerfile
# images/sandbox-terminal/Dockerfile

FROM ubuntu:22.04

LABEL maintainer="OmicHub Team"
LABEL description="Rootless sandbox terminal for OmicHub"

# 避免交互式配置提示
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Asia/Shanghai

# 创建非 root 用户（UID 1000 必须与宿主机映射一致）
RUN groupadd -r -g 1000 omichub && \
    useradd -r -u 1000 -g omichub -d /home/omichub -s /bin/bash omichub && \
    mkdir -p /home/omichub/workspace /home/omichub/tmp && \
    chown -R omichub:omichub /home/omichub

# 安装基础工具 + 生信工具链
RUN apt-get update && apt-get install -y --no-install-recommends \
    # 基础工具
    wget curl ca-certificates gnupg2 \
    htop vim nano less tree \
    bash-completion man-db \
    # 构建依赖
    build-essential cmake \
    # Python 环境
    python3 python3-pip python3-venv \
    # R 环境
    r-base r-base-dev \
    # 常用生信工具
    samtools bcftools bedtools \
    bwa bowtie2 hisat2 \
    fastqc multiqc \
    # 序列处理
    seqkit \
    # 其他实用工具
    jq csvkit \
    # ttyd 依赖
    libwebsockets-dev libjson-c-dev \
    && rm -rf /var/lib/apt/lists/*

# 安装 ttyd（Web 终端）
# 方式1：从 release 下载预编译二进制（推荐，更轻量）
RUN wget -qO /usr/local/bin/ttyd \
    https://github.com/tsl0922/ttyd/releases/download/1.7.4/ttyd.x86_64 && \
    chmod +x /usr/local/bin/ttyd

# 安装常用 Python 包
RUN pip3 install --no-cache-dir \
    numpy pandas scipy matplotlib seaborn \
    biopython pysam pybedtools

# 安装常用 R 包
RUN R -e "install.packages(c('tidyverse', 'ggplot2', 'dplyr', 'data.table'), repos='https://cloud.r-project.org/')"

# 配置 bash 环境
COPY bashrc /home/omichub/.bashrc
RUN chown omichub:omichub /home/omichub/.bashrc

# 创建欢迎信息
RUN echo 'echo "欢迎来到 OmicHub 沙盒终端！"' >> /home/omichub/.bashrc && \
    echo 'echo "工作目录: /home/omichub/workspace"' >> /home/omichub/.bashrc && \
    echo 'echo "临时目录: /home/omichub/tmp (容器销毁后清空)"' >> /home/omichub/.bashrc && \
    echo 'echo "预装工具: samtools, bcftools, bedtools, bwa, python3, R"' >> /home/omichub/.bashrc && \
    echo 'echo ""' >> /home/omichub/.bashrc

# 切换非 root 用户
USER omichub
WORKDIR /home/omichub/workspace

# 暴露 ttyd 端口
EXPOSE 7681

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost:7681 || exit 1

# 启动 ttyd，绑定到所有接口
CMD ["ttyd", "-p", "7681", "-W", "-t", "fontSize=14", "-t", "fontFamily=JetBrains Mono", "bash"]
```

### 6.2 构建与推送

```bash
# 构建镜像
cd images/sandbox-terminal
docker build -t omichub/sandbox-terminal:latest -t omichub/sandbox-terminal:v1.0.0 .

# 测试运行（本地验证）
docker run --rm -it \
  --read-only \
  --tmpfs /tmp:rw,noexec,nosuid,size=100m \
  -p 7681:7681 \
  -v $(pwd)/test-workspace:/home/omichub/workspace:rw \
  omichub/sandbox-terminal:latest

# 推送至私有仓库（如 Harbor）
docker tag omichub/sandbox-terminal:latest harbor.omichub.local/omic/sandbox-terminal:latest
docker push harbor.omichub.local/omic/sandbox-terminal:latest
```

### 6.3 镜像版本策略

| 标签 | 说明 | 更新频率 |
|------|------|---------|
| `latest` | 最新稳定版，YAML 默认引用 | 每月 |
| `v1.0.0` | 固定版本，生产环境锁定 | 按发布 |
| `dev` | 开发测试版 | 每日 CI/CD |

---

## 7. YAML 配置规范

在 OmicHub 现有 `general.yaml` 中新增 `terminal` 段落，或通过独立 `terminal.yaml` 管理。

```yaml
# config/terminal.yaml

terminal:
  # 功能开关
  enabled: true
  
  # 容器镜像配置
  image:
    registry: "harbor.omichub.local/omic"
    name: "sandbox-terminal"
    tag: "latest"
    pull_policy: "IfNotPresent"  # Always | IfNotPresent | Never
  
  # 默认资源配额（用户可在前端申请覆盖，但受 max 限制）
  default_resources:
    memory_mb: 512
    cpu_cores: 1.0
    pid_limit: 100
    tmpfs_size_mb: 100
  
  # 资源上限（硬限制，防止滥用）
  max_resources:
    memory_mb: 4096
    cpu_cores: 4.0
    pid_limit: 500
    tmpfs_size_mb: 500
  
  # 端口分配范围
  port_range:
    base: 20000
    max: 30000
  
  # 会话生命周期
  lifecycle:
    idle_timeout: 1800        # 30分钟无操作自动销毁（秒）
    disconnect_timeout: 300   # WebSocket 断连后 5 分钟销毁（秒）
    max_session_duration: 7200  # 单次会话最长 2 小时（秒）
    max_sessions_per_user: 2    # 每个用户同时最多 2 个活跃会话
  
  # 安全策略
  security:
    read_only_root: true
    cap_drop_all: true
    no_new_privileges: true
    seccomp_profile: "omichub-terminal.json"  # 自定义 seccomp 文件路径
    apparmor_profile: "docker-omic-terminal"  # AppArmor 配置（可选）
    
    # 挂载路径白名单（正则）
    allowed_mount_patterns:
      - "^/data/omichub/users/[0-9]+/workspace$"
      - "^/data/omichub/users/[0-9]+/tmp$"
    
    # 挂载路径黑名单（正则）
    forbidden_mount_patterns:
      - ".*docker\.sock.*"
      - "^/etc/.*"
      - "^/usr/.*"
      - "^/root/.*"
      - "^/proc/.*"
      - "^/sys/.*"
  
  # 网络配置
  network:
    mode: "bridge"            # bridge | none | custom
    custom_network: "omichub-sandbox-net"
    # 出站限制（可选，需配合 iptables / DNS 白名单）
    outbound_allowed_domains:
      - "ncbi.nlm.nih.gov"
      - "ensembl.org"
      - "kegg.jp"
      - "github.com"
  
  # 存储配置
  storage:
    workspace_base: "/data/omichub/users/{user_id}/workspace"
    tmp_base: "/data/omichub/users/{user_id}/tmp"
    tmp_cleanup_interval: 3600  # 每小时清理一次 tmp 目录
    tmp_max_age: 86400          # tmp 文件保留 24 小时
  
  # 审计与日志
  audit:
    enabled: true
    log_level: "INFO"           # DEBUG | INFO | WARNING | ERROR
    retention_days: 30
    log_commands: false         # 是否记录用户输入的命令（隐私敏感，默认关闭）
    log_commands_patterns:      # 若开启，仅记录匹配以下模式的命令
      - "^rm .*"
      - "^sudo .*"
      - "^curl .*"
  
  # 前端配置（透传给前端）
  frontend:
    theme: "dark"               # dark | light
    font_family: "JetBrains Mono, Fira Code, monospace"
    font_size: 14
    scrollback: 10000
    enable_web_links: true      # 自动识别并高亮 URL
    enable_copy_on_select: true # 选中即复制
```

---

## 8. 部署与运维

### 8.1 服务器环境准备

```bash
# 1. 安装 Rootless Docker
# 参考: https://docs.docker.com/engine/security/rootless/

# 创建 omichub 服务用户
sudo useradd -m -s /bin/bash -u 1000 omichub
sudo loginctl enable-linger omichub  # 允许用户后台运行服务

# 切换到 omichub 用户安装 rootless docker
sudo -u omichub -i
curl -fsSL https://get.docker.com/rootless | sh

# 配置环境变量（添加到 ~/.bashrc）
echo 'export PATH=/home/omichub/bin:$PATH' >> ~/.bashrc
echo 'export DOCKER_HOST=unix:///run/user/1000/docker.sock' >> ~/.bashrc
source ~/.bashrc

# 验证
docker info | grep "rootless"
# 应输出:  rootless: true

# 2. 创建隔离网络
docker network create \
  --driver bridge \
  --subnet 172.28.0.0/16 \
  --gateway 172.28.0.1 \
  omichub-sandbox-net

# 3. 创建工作目录结构
sudo mkdir -p /data/omichub/users
sudo chown -R omichub:omichub /data/omichub

# 4. 限制用户磁盘配额（可选，使用 xfs quota 或 LVM）
# xfs_quota -x -c 'limit bsoft=10G bhard=20G omichub' /data
```

### 8.2 后端服务部署

```ini
; /etc/systemd/system/omichub-backend.service

[Unit]
Description=OmicHub Backend API
After=network.target redis.service postgresql.service

[Service]
Type=simple
User=omichub
Group=omichub
WorkingDirectory=/opt/omichub/backend
Environment="PATH=/home/omichub/bin:/usr/local/bin:/usr/bin:/bin"
Environment="DOCKER_HOST=unix:///run/user/1000/docker.sock"
Environment="OMICHUB_CONFIG=/opt/omichub/config/terminal.yaml"
ExecStart=/opt/omichub/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### 8.3 监控与告警

```yaml
# prometheus/rules/terminal.yml

groups:
  - name: omichub_terminal
    rules:
      - alert: TerminalHighMemoryUsage
        expr: |
          container_memory_usage_bytes{name=~"omichub-terminal-.*"} 
          / container_spec_memory_limit_bytes > 0.9
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "沙盒终端内存使用率超过 90%"
          
      - alert: TerminalIdleLongTime
        expr: |
          time() - omichub_terminal_last_activity_timestamp > 3600
        for: 5m
        labels:
          severity: info
        annotations:
          summary: "沙盒终端会话空闲超过 1 小时"
          
      - alert: TerminalContainerEscape
        expr: |
          rate(container_cpu_system_seconds_total{name=~"omichub-terminal-.*"}[5m]) > 0.5
        labels:
          severity: critical
        annotations:
          summary: "沙盒终端异常系统 CPU 使用，疑似逃逸行为"
```

### 8.4 日常运维命令

```bash
# 查看所有活跃终端会话
docker ps --filter "label=app=omichub-terminal" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# 查看特定用户会话
docker ps --filter "label=user_id=42" --filter "label=app=omichub-terminal"

# 强制销毁异常会话
docker stop omichub-terminal-42-term_xxxxxx

# 清理孤儿网络/卷
docker network prune -f
docker volume prune -f

# 查看会话审计日志
redis-cli lrange "terminal:audit:42" 0 -1
```

---

## 9. 风险矩阵与应对

| 风险项 | 概率 | 影响 | 应对策略 | 状态 |
|--------|------|------|---------|------|
| **容器逃逸** | 低 | 高 | Rootless Docker + 非 root 用户 + capability 全丢 + seccomp | 已设计 |
| **资源耗尽 (DoS)** | 中 | 中 | 内存/CPU/PID/磁盘硬限制 + 单用户会话数限制 | 已设计 |
| **敏感数据泄露** | 低 | 高 | 仅挂载用户目录 + 禁止系统路径 + 只读根文件系统 | 已设计 |
| **恶意网络行为** | 中 | 中 | 隔离桥接网络 + 可选出站域名白名单 | 可选增强 |
| **会话劫持** | 低 | 高 | JWT 鉴权 + WebSocket URL 含随机 session_id + HTTPS/WSS | 已设计 |
| **命令注入** | 低 | 中 | 容器内非 root + 只读文件系统 + 命令审计（可选） | 已设计 |
| **镜像漏洞** | 中 | 中 | 定期扫描基础镜像 + 最小化安装 + 及时更新 | 持续运维 |
| **持久化攻击** | 低 | 高 | 只读根文件系统 + tmpfs 限制 + 定期清理 tmp | 已设计 |

---

## 10. 迭代路线图

### Phase 1 - MVP（2 周）
- [ ] 基础 rootless Docker 容器启动/销毁 API
- [ ] ttyd + xterm.js 最小可用终端
- [ ] 仅挂载 workspace，只读根文件系统
- [ ] 30 分钟空闲超时销毁
- [ ] 前端生信工具箱新增终端卡片

### Phase 2 - 增强安全与体验（2 周）
- [ ] 资源配额动态调整（内存/CPU/PID 限制）
- [ ] WebSocket 断连自动重连 + 心跳机制
- [ ] 全屏/分屏模式支持
- [ ] 容器内预装常用生信工具链（samtools, bedtools, python, R）
- [ ] 命令历史缓存（前端本地存储）

### Phase 3 - 生态集成（3 周）
- [ ] 侧边文件浏览器（与 OmicHub 文件管理联动）
- [ ] 拖拽上传文件到 workspace
- [ ] 终端内直接提交任务到 OmicHub 任务中心
- [ ] 多会话标签页（类似 iTerm2）
- [ ] 自定义环境变量和启动脚本

### Phase 4 - 高级功能（远期）
- [ ] GPU 沙盒支持（CUDA 容器）
- [ ] 自定义 Docker 镜像选择（用户上传 Dockerfile）
- [ ] 协作模式（多用户共享同一个只读终端视图）
- [ ] 终端录屏与回放（用于教学、故障排查）

---

## 附录

### A. 自定义 Seccomp 策略示例

```json
{
  "defaultAction": "SCMP_ACT_ERRNO",
  "architectures": ["SCMP_ARCH_X86_64", "SCMP_ARCH_X86"],
  "syscalls": [
    {
      "names": [
        "accept", "accept4", "access", "adjtimex", "alarm", "bind",
        "brk", "capget", "capset", "chdir", "chmod", "chown", "clock_getres",
        "clock_gettime", "clock_nanosleep", "clone", "close", "connect",
        "copy_file_range", "creat", "dup", "dup2", "dup3", "epoll_create",
        "epoll_create1", "epoll_ctl", "epoll_ctl_old", "epoll_pwait",
        "epoll_wait", "epoll_wait_old", "eventfd", "eventfd2", "execve",
        "execveat", "exit", "exit_group", "faccessat", "fadvise64",
        "fadvise64_64", "fallocate", "fanotify_mark", "fchdir", "fchmod",
        "fchmodat", "fchown", "fchownat", "fcntl", "fdatasync", "fgetxattr",
        "flistxattr", "flock", "fork", "fremovexattr", "fsetxattr", "fstat",
        "fstat64", "fstatat64", "fstatfs", "fstatfs64", "fsync", "ftruncate",
        "ftruncate64", "futex", "getcpu", "getcwd", "getdents", "getdents64",
        "getegid", "getegid32", "geteuid", "geteuid32", "getgid", "getgid32",
        "getgroups", "getgroups32", "getitimer", "getpeername", "getpgid",
        "getpgrp", "getpid", "getppid", "getpriority", "getrandom", "getresgid",
        "getresgid32", "getresuid", "getresuid32", "getrlimit", "get_robust_list",
        "getrusage", "getsid", "getsockname", "getsockopt", "get_thread_area",
        "gettid", "gettimeofday", "getuid", "getuid32", "getxattr", "ioctl",
        "io_cancel", "io_destroy", "io_getevents", "io_pgetevents", "ioprio_get",
        "ioprio_set", "io_setup", "io_submit", "io_uring_enter", "io_uring_register",
        "io_uring_setup", "kill", "lchown", "lgetxattr", "link", "linkat",
        "listen", "listxattr", "llistxattr", "lremovexattr", "lseek", "lsetxattr",
        "lstat", "lstat64", "madvise", "memfd_create", "mincore", "mkdir",
        "mkdirat", "mknod", "mknodat", "mlock", "mlock2", "mlockall", "mmap",
        "mmap2", "mprotect", "mq_getsetattr", "mq_notify", "mq_open", "mq_timedreceive",
        "mq_timedsend", "mq_unlink", "mremap", "msgctl", "msgget", "msgrcv",
        "msgsnd", "msync", "munlock", "munlockall", "munmap", "nanosleep",
        "newfstatat", "open", "openat", "openat2", "pause", "pidfd_open",
        "pidfd_send_signal", "pipe", "pipe2", "poll", "ppoll", "prctl", "pread64",
        "preadv", "preadv2", "prlimit64", "pselect6", "pwrite64", "pwritev",
        "pwritev2", "read", "readahead", "readdir", "readlink", "readlinkat",
        "readv", "recv", "recvfrom", "recvmmsg", "recvmsg", "remap_file_pages",
        "removexattr", "rename", "renameat", "renameat2", "restart_syscall",
        "rmdir", "rseq", "rt_sigaction", "rt_sigpending", "rt_sigprocmask",
        "rt_sigqueueinfo", "rt_sigreturn", "rt_sigsuspend", "rt_sigtimedwait",
        "rt_tgsigqueueinfo", "sched_getaffinity", "sched_getattr", "sched_getparam",
        "sched_get_priority_max", "sched_get_priority_min", "sched_getscheduler",
        "sched_rr_get_interval", "sched_setaffinity", "sched_setattr",
        "sched_setparam", "sched_setscheduler", "sched_yield", "seccomp",
        "select", "semctl", "semget", "semop", "semtimedop", "send", "sendfile",
        "sendfile64", "sendmmsg", "sendmsg", "sendto", "setfsgid", "setfsgid32",
        "setfsuid", "setfsuid32", "setgid", "setgid32", "setgroups", "setgroups32",
        "setitimer", "setpgid", "setpriority", "setregid", "setregid32",
        "setresgid", "setresgid32", "setresuid", "setresuid32", "setreuid",
        "setreuid32", "setrlimit", "set_robust_list", "setsid", "setsockopt",
        "set_thread_area", "set_tid_address", "setuid", "setuid32", "setxattr",
        "shmat", "shmctl", "shmdt", "shmget", "shutdown", "sigaltstack", "signalfd",
        "signalfd4", "socket", "socketcall", "socketpair", "splice", "stat",
        "stat64", "statfs", "statfs64", "statx", "symlink", "symlinkat", "sync",
        "sync_file_range", "syncfs", "sysinfo", "tee", "tgkill", "time", "timer_create",
        "timer_delete", "timer_getoverrun", "timer_gettime", "timer_settime",
        "timerfd_create", "timerfd_gettime", "timerfd_settime", "times", "tkill",
        "truncate", "truncate64", "ugetrlimit", "umask", "uname", "unlink",
        "unlinkat", "utime", "utimensat", "utimes", "vfork", "wait4", "waitid",
        "waitpid", "write", "writev"
      ],
      "action": "SCMP_ACT_ALLOW"
    },
    {
      "names": ["personality"],
      "action": "SCMP_ACT_ALLOW",
      "args": [
        {
          "index": 0,
          "value": 0,
          "op": "SCMP_CMP_EQ"
        },
        {
          "index": 0,
          "value": 8,
          "op": "SCMP_CMP_EQ"
        },
        {
          "index": 0,
          "value": 131072,
          "op": "SCMP_CMP_EQ"
        },
        {
          "index": 0,
          "value": 131073,
          "op": "SCMP_CMP_EQ"
        },
        {
          "index": 0,
          "value": 4294967295,
          "op": "SCMP_CMP_EQ"
        }
      ]
    }
  ]
}
```

### B. 快速验证清单

部署完成后，按以下清单验证功能：

- [ ] 用户 A 启动终端，确认容器以 UID 1000 运行
- [ ] 在容器内执行 `whoami` -> 输出 `omichub`
- [ ] 在容器内执行 `touch /etc/test` -> 权限拒绝（只读根文件系统）
- [ ] 在容器内执行 `touch /home/omichub/workspace/test.txt` -> 成功，且宿主机对应目录出现文件
- [ ] 在容器内执行 `cat /proc/self/status | grep Cap` -> 所有 Cap 为 0
- [ ] 空闲 30 分钟后，容器自动销毁
- [ ] 用户 A 无法通过任何路径访问用户 B 的 workspace
- [ ] WebSocket 连接使用 wss://（TLS 加密）
- [ ] 容器内 `curl https://ncbi.nlm.nih.gov` -> 成功（若启用出站白名单）
- [ ] 容器内 `curl https://evil.com` -> 失败（若启用出站白名单）

---

*文档结束。如有疑问或需调整实现细节，请随时联系开发团队。*