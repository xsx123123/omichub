# OmicHub 云存储二进制下载 — 前后端连接与实时进度捕获方案

> **日期**：2025-06-27  
> **场景**：前端选择云服务商 → 后端调用对应二进制工具下载 → 前端实时显示进度  
> **二进制位置**：`/data/omichub/bin/`（ossutil / tosutil / obsutil）

---

## 一、整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                        前端 (Vue 3)                          │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────┐ │
│  │ 云商选择     │    │ 对象URI输入  │    │ 下载按钮         │ │
│  │ (下拉)      │ →  │ (文本框)    │ →  │ (带进度条)      │ │
│  └─────────────┘    └─────────────┘    └─────────────────┘ │
│         │                                              ▲     │
│         ▼                                              │     │
│  ┌─────────────────────────────────────────────────┐   │     │
│  │              实时进度面板                         │   │     │
│  │  ┌──────────────┐  ┌──────────────┐            │   │     │
│  │  │ 整体进度条    │  │ 当前文件进度  │  ←───────┘   │     │
│  │  │ [████████░░] │  │ [██████░░░░] │               │     │
│  │  │ 80% 8MB/s   │  │ 60% 5MB/s   │               │     │
│  │  └──────────────┘  └──────────────┘               │     │
│  │  下载速度: 8.5 MB/s                                │     │
│  │  已下载: 856 MB / 1.2 GB                           │     │
│  │  预计剩余: 45秒                                    │     │
│  │  当前文件: scanpy-2.1.0-py3-none-any.whl          │     │
│  └─────────────────────────────────────────────────┘         │
└─────────────────────────────────────────────────────────────┘
                            │ WebSocket (实时推送)
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                     后端 (FastAPI)                           │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────┐ │
│  │ API接收下载  │ →  │ Download    │ →  │ subprocess      │ │
│  │ 请求        │    │ Manager     │    │ (ossutil/etc)   │ │
│  └─────────────┘    └─────────────┘    └─────────────────┘ │
│                            │                                  │
│                            ▼ 解析stdout进度                    │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ WebSocket Manager ──→ 前端广播进度                        │ │
│  └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                   文件系统                                   │
│  /data/omichub/bin/                                        │
│    ├── ossutil              (阿里云工具)                     │
│    ├── tosutil              (火山引擎工具)                   │
│    └── obsutil              (华为云工具)                     │
│                                                              │
│  /data/downloads/          (下载目标目录)                     │
│    ├── {task_id}/                                         │
│    │   ├── scanpy-2.1.0.whl                               │
│    │   └── seurat-5.0.0.tar.gz                            │
│    └── ...                                                │
└─────────────────────────────────────────────────────────────┘
```

---

## 二、数据库设计

```sql
-- 云存储配置表（每个用户可配置多个云商）
CREATE TABLE cloud_storage_configs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    provider VARCHAR(20) NOT NULL,  -- aliyun / volcengine / huaweicloud
    name VARCHAR(100) NOT NULL,     -- 显示名称（如"阿里云华东1"）
    endpoint VARCHAR(255),          -- 自定义Endpoint（可选）
    access_key VARCHAR(255),        -- 加密存储
    secret_key VARCHAR(255),        -- 加密存储
    bucket VARCHAR(100),            -- 默认Bucket
    region VARCHAR(50),             -- 地域
    is_default BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 下载任务表
CREATE TABLE download_tasks (
    id SERIAL PRIMARY KEY,
    task_id VARCHAR(50) UNIQUE NOT NULL,  -- UUID
    user_id INTEGER NOT NULL REFERENCES users(id),
    
    -- 下载源
    provider VARCHAR(20) NOT NULL,   -- aliyun / volcengine / huaweicloud
    object_uri TEXT NOT NULL,        -- 对象URI（oss://bucket/path 或完整URL）
    destination_path TEXT NOT NULL,  -- 本地保存路径
    
    -- 状态
    status VARCHAR(20) DEFAULT 'pending',  -- pending/downloading/paused/completed/failed/cancelled
    
    -- 进度（实时更新）
    total_bytes BIGINT DEFAULT 0,     -- 总大小（字节）
    downloaded_bytes BIGINT DEFAULT 0,-- 已下载（字节）
    progress_percent INTEGER DEFAULT 0, -- 百分比 0-100
    speed_bytes_per_sec BIGINT DEFAULT 0, -- 速度（字节/秒）
    current_file TEXT,                -- 当前下载的文件名
    
    -- 统计
    file_count_total INTEGER DEFAULT 0,     -- 总文件数
    file_count_completed INTEGER DEFAULT 0, -- 已完成数
    
    -- 时间
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    estimated_end_at TIMESTAMPTZ,     -- 预计完成时间
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- 错误信息
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    
    -- 日志（JSONB存储详细进度日志）
    progress_log JSONB DEFAULT '[]'::jsonb
);

-- 下载文件明细表
CREATE TABLE download_files (
    id SERIAL PRIMARY KEY,
    task_id VARCHAR(50) NOT NULL REFERENCES download_tasks(task_id),
    file_name VARCHAR(255) NOT NULL,
    object_key TEXT NOT NULL,        -- 云端的object key
    local_path TEXT NOT NULL,        -- 本地保存路径
    file_size BIGINT DEFAULT 0,
    downloaded_size BIGINT DEFAULT 0,
    status VARCHAR(20) DEFAULT 'pending', -- pending/downloading/completed/failed
    progress_percent INTEGER DEFAULT 0,
    speed_bytes_per_sec BIGINT DEFAULT 0,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 索引
CREATE INDEX idx_download_tasks_user ON download_tasks(user_id, created_at DESC);
CREATE INDEX idx_download_tasks_status ON download_tasks(status);
CREATE INDEX idx_download_files_task ON download_files(task_id);
```

---

## 三、后端完整代码

### 3.1 Pydantic DTO

```python
# app/schemas/download.py
from pydantic import BaseModel, Field, field_validator
from typing import Optional, Literal
from datetime import datetime

CloudProvider = Literal["aliyun", "volcengine", "huaweicloud"]

class DownloadCreateRequest(BaseModel):
    """创建下载任务请求"""
    provider: CloudProvider
    object_uri: str = Field(..., description="对象URI，如 oss://bucket/path/ 或完整URL")
    destination_dir: str = Field(default="/data/downloads", description="本地保存目录")
    recursive: bool = Field(default=False, description="是否递归下载目录")
    
    @field_validator('object_uri')
    @classmethod
    def validate_uri(cls, v: str) -> str:
        if not v.startswith(('oss://', 'tos://', 'obs://', 'http://', 'https://')):
            raise ValueError('URI必须以 oss:// / tos:// / obs:// / http(s):// 开头')
        return v

class DownloadTaskResponse(BaseModel):
    """下载任务响应"""
    task_id: str
    status: str
    provider: str
    object_uri: str
    destination_path: str
    total_bytes: int = 0
    downloaded_bytes: int = 0
    progress_percent: int = 0
    speed_bytes_per_sec: int = 0
    current_file: Optional[str] = None
    file_count_total: int = 0
    file_count_completed: int = 0
    started_at: Optional[datetime] = None
    estimated_end_at: Optional[datetime] = None
    error_message: Optional[str] = None
    created_at: datetime

class DownloadProgressEvent(BaseModel):
    """下载进度WebSocket事件"""
    type: str = "download.progress"  # download.progress / download.complete / download.error
    task_id: str
    progress_percent: int
    speed_bytes_per_sec: int
    downloaded_bytes: int
    total_bytes: int
    current_file: Optional[str] = None
    file_count_completed: int = 0
    file_count_total: int = 0
    estimated_seconds_remaining: Optional[int] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
```

### 3.2 下载服务（核心！）

```python
# app/services/download_service.py
"""
云存储下载服务 — 支持阿里云OSS/火山引擎TOS/华为云OBS
通过subprocess调用对应二进制工具，实时捕获进度
"""

import asyncio
import os
import re
import uuid
import json
from datetime import datetime, timedelta
from typing import Optional, Callable, AsyncIterable
from dataclasses import dataclass, field
from pathlib import Path
import shutil

from app.schemas.download import DownloadProgressEvent, CloudProvider


@dataclass
class DownloadConfig:
    """下载配置"""
    provider: CloudProvider
    object_uri: str
    destination_dir: str
    recursive: bool = False
    # 二进制工具路径
    bin_paths = {
        "aliyun": "/data/omichub/bin/ossutil",
        "volcengine": "/data/omichub/bin/tosutil",
        "huaweicloud": "/data/omichub/bin/obsutil",
    }


@dataclass
class DownloadState:
    """下载状态（内存中维护）"""
    task_id: str
    status: str = "pending"  # pending/downloading/paused/completed/failed/cancelled
    total_bytes: int = 0
    downloaded_bytes: int = 0
    speed_bps: int = 0
    current_file: str = ""
    file_count_total: int = 0
    file_count_completed: int = 0
    process: Optional[asyncio.subprocess.Process] = None
    progress_callbacks: list = field(default_factory=list)
    error_message: Optional[str] = None
    
    @property
    def progress_percent(self) -> int:
        if self.total_bytes <= 0:
            return 0 if self.status == "downloading" else 100
        return min(100, int(self.downloaded_bytes * 100 / self.total_bytes))
    
    @property
    def estimated_seconds_remaining(self) -> Optional[int]:
        if self.speed_bps <= 0 or self.total_bytes <= 0:
            return None
        remaining = self.total_bytes - self.downloaded_bytes
        return int(remaining / self.speed_bps)


class DownloadManager:
    """
    下载管理器 — 单例模式
    管理所有下载任务的生命周期
    """
    _instance = None
    _tasks: dict[str, DownloadState] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def create_task(self, config: DownloadConfig) -> DownloadState:
        """创建下载任务"""
        task_id = str(uuid.uuid4())[:8]
        
        # 校验二进制工具是否存在
        bin_path = config.bin_paths.get(config.provider)
        if not bin_path or not os.path.exists(bin_path):
            raise FileNotFoundError(
                f"{config.provider} 下载工具未找到: {bin_path}\n"
                f"请先执行: chmod +x {bin_path}"
            )
        
        # 创建目标目录
        dest = Path(config.destination_dir) / task_id
        dest.mkdir(parents=True, exist_ok=True)
        
        state = DownloadState(task_id=task_id)
        self._tasks[task_id] = state
        return state
    
    async def start_download(
        self,
        task_id: str,
        config: DownloadConfig,
        progress_callback: Optional[Callable[[DownloadProgressEvent], None]] = None
    ):
        """启动下载 — 核心方法"""
        state = self._tasks.get(task_id)
        if not state:
            raise ValueError(f"任务不存在: {task_id}")
        
        state.status = "downloading"
        state.started_at = datetime.utcnow()
        
        # 构建命令
        cmd = self._build_command(config, task_id)
        
        # 启动子进程
        state.process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=f"{config.destination_dir}/{task_id}"
        )
        
        # 注册回调
        if progress_callback:
            state.progress_callbacks.append(progress_callback)
        
        # 并发读取stdout和stderr
        await asyncio.gather(
            self._read_stdout(state, config.provider),
            self._read_stderr(state)
        )
        
        # 等待进程结束
        return_code = await state.process.wait()
        
        if return_code == 0:
            state.status = "completed"
            state.progress_percent = 100
        elif state.status != "cancelled":
            state.status = "failed"
            if not state.error_message:
                state.error_message = f"下载失败，退出码: {return_code}"
    
    def _build_command(self, config: DownloadConfig, task_id: str) -> list[str]:
        """根据云商构建对应的命令"""
        bin_path = config.bin_paths[config.provider]
        dest = f"{config.destination_dir}/{task_id}"
        
        if config.provider == "aliyun":
            # ossutil cp -r oss://bucket/path/ ./local/
            cmd = [
                bin_path,
                "cp",
                config.object_uri,
                dest,
                "--recursive" if config.recursive else "",
                "--update",           # 跳过已存在的文件
                "--force",            # 不提示确认
                "--jobs", "5",        # 并发数
                "--threshold", "102400",  # 分片阈值100KB
            ]
        
        elif config.provider == "volcengine":
            # tosutil cp -r tos://bucket/path/ ./local/
            cmd = [
                bin_path,
                "cp",
                config.object_uri,
                dest,
                "-r" if config.recursive else "",
                "-u",                 # 跳过已存在
                "-j", "5",            # 并发数
                "--checkpoint", f"{dest}/.checkpoint",  # 断点续传
            ]
        
        elif config.provider == "huaweicloud":
            # obsutil cp -r -f obs://bucket/path/ ./local/
            cmd = [
                bin_path,
                "cp",
                config.object_uri,
                dest,
                "-r" if config.recursive else "",
                "-f",                 # 强制覆盖
                "-u",                 # 只上传新文件
                "-j", "5",            # 并发数
                "-parallel", "5",     # 分段并发数
                "-partSize", "5",     # 分片大小MB
            ]
        
        else:
            raise ValueError(f"不支持的云商: {config.provider}")
        
        # 过滤空字符串
        return [c for c in cmd if c]
    
    async def _read_stdout(self, state: DownloadState, provider: CloudProvider):
        """读取stdout并解析进度 — 核心！"""
        if not state.process or not state.process.stdout:
            return
        
        # 不同云商的正则表达式
        patterns = {
            "aliyun": {
                # Succeeded: total num: 10, size: 1,024,000. OK num: 5(download 5 objects), Fail num: 0
                # Scanning... | Speed: 8.5MB/s, Downloading: file.txt 50%(512KB/1MB)
                "progress": re.compile(
                    r'Speed:\s*([\d.]+)([KMGT]?B)/s.*?Downloading:\s*(\S+)\s*(\d+)%\s*\(([\d.]+[KMGT]?B)/([\d.]+[KMGT]?B)\)'
                ),
                "summary": re.compile(
                    r'total num:\s*(\d+).*?OK num:\s*(\d+).*?Fail num:\s*(\d+)'
                ),
            },
            "volcengine": {
                # Progress: 50% (512MB/1GB) Speed: 8.5MB/s File: file.txt
                "progress": re.compile(
                    r'Progress:\s*(\d+)%\s*\(([\d.]+[KMGT]?B)/([\d.]+[KMGT]?B)\)\s*Speed:\s*([\d.]+)([KMGT]?B)/s\s*File:\s*(\S+)'
                ),
            },
            "huaweicloud": {
                # [=========================>        ] 75.00% 15MB/s file.txt 768MB/1GB
                "progress": re.compile(
                    r'([\d.]+)%\s*([\d.]+)([KMGT]?B)/s\s*(\S+)\s*([\d.]+[KMGT]?B)/([\d.]+[KMGT]?B)'
                ),
            }
        }
        
        pattern = patterns.get(provider, patterns["aliyun"])
        
        async for line in state.process.stdout:
            line_str = line.decode('utf-8', errors='replace').strip()
            if not line_str:
                continue
            
            # 解析进度
            if "progress" in pattern:
                match = pattern["progress"].search(line_str)
                if match:
                    self._update_progress_from_match(state, match, provider)
                    await self._notify_progress(state)
            
            # 解析汇总
            if "summary" in pattern:
                match = pattern["summary"].search(line_str)
                if match:
                    state.file_count_total = int(match.group(1))
                    state.file_count_completed = int(match.group(2))
    
    def _update_progress_from_match(
        self, state: DownloadState, match: re.Match, provider: CloudProvider
    ):
        """从正则匹配结果更新进度"""
        try:
            if provider == "aliyun":
                # Speed: 8.5MB/s, Downloading: file.txt 50%(512KB/1MB)
                speed_val = float(match.group(1))
                speed_unit = match.group(2)
                state.speed_bps = self._parse_size(f"{speed_val}{speed_unit}")
                state.current_file = match.group(3)
                state.progress_percent = int(match.group(4))
                downloaded = self._parse_size(match.group(5))
                total = self._parse_size(match.group(6))
                state.downloaded_bytes = downloaded
                state.total_bytes = total
            
            elif provider == "volcengine":
                # Progress: 50% (512MB/1GB) Speed: 8.5MB/s File: file.txt
                state.progress_percent = int(match.group(1))
                state.downloaded_bytes = self._parse_size(match.group(2))
                state.total_bytes = self._parse_size(match.group(3))
                speed_val = float(match.group(4))
                speed_unit = match.group(5)
                state.speed_bps = self._parse_size(f"{speed_val}{speed_unit}")
                state.current_file = match.group(6)
            
            elif provider == "huaweicloud":
                # 75.00% 15MB/s file.txt 768MB/1GB
                state.progress_percent = int(float(match.group(1)))
                speed_val = float(match.group(2))
                speed_unit = match.group(3)
                state.speed_bps = self._parse_size(f"{speed_val}{speed_unit}")
                state.current_file = match.group(4)
                state.downloaded_bytes = self._parse_size(match.group(5))
                state.total_bytes = self._parse_size(match.group(6))
        
        except (ValueError, IndexError) as e:
            print(f"进度解析错误: {e}")
    
    def _parse_size(self, size_str: str) -> int:
        """将人类可读的大小转为字节数"""
        size_str = size_str.strip().upper()
        units = {'B': 1, 'KB': 1024, 'MB': 1024**2, 'GB': 1024**3, 'TB': 1024**4}
        
        for unit, multiplier in units.items():
            if size_str.endswith(unit):
                return int(float(size_str[:-len(unit)]) * multiplier)
        
        return int(float(size_str))
    
    async def _read_stderr(self, state: DownloadState):
        """读取stderr（错误信息）"""
        if not state.process or not state.process.stderr:
            return
        
        async for line in state.process.stderr:
            line_str = line.decode('utf-8', errors='replace').strip()
            if line_str:
                # 有些云商把进度输出到stderr
                if '%' in line_str or 'Speed' in line_str:
                    # 可能是进度信息，尝试解析
                    pass
                elif 'Error' in line_str or 'error' in line_str:
                    state.error_message = line_str
    
    async def _notify_progress(self, state: DownloadState):
        """通知所有注册的回调"""
        event = DownloadProgressEvent(
            task_id=state.task_id,
            progress_percent=state.progress_percent,
            speed_bytes_per_sec=state.speed_bps,
            downloaded_bytes=state.downloaded_bytes,
            total_bytes=state.total_bytes,
            current_file=state.current_file,
            file_count_completed=state.file_count_completed,
            file_count_total=state.file_count_total,
            estimated_seconds_remaining=state.estimated_seconds_remaining
        )
        
        for callback in state.progress_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(event)
                else:
                    callback(event)
            except Exception as e:
                print(f"进度回调错误: {e}")
    
    async def cancel_download(self, task_id: str):
        """取消下载"""
        state = self._tasks.get(task_id)
        if not state or not state.process:
            return
        
        state.status = "cancelled"
        state.process.terminate()
        
        # 等待5秒后强制kill
        await asyncio.sleep(5)
        if state.process.returncode is None:
            state.process.kill()
    
    def get_task(self, task_id: str) -> Optional[DownloadState]:
        """获取任务状态"""
        return self._tasks.get(task_id)
    
    def list_tasks(self, user_id: int) -> list[DownloadState]:
        """列出用户的所有任务"""
        # TODO: 根据user_id过滤
        return list(self._tasks.values())


# 全局下载管理器
download_manager = DownloadManager()
```

### 3.3 WebSocket实时推送

```python
# app/websocket/download_ws.py
"""
下载进度WebSocket — 实时推送到前端
"""

import asyncio
import json
from datetime import datetime
from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict

from app.services.download_service import download_manager, DownloadProgressEvent

# 活跃的WebSocket连接 {task_id: [websocket1, websocket2, ...]}
active_connections: Dict[str, list[WebSocket]] = {}

async def register_download_websocket(websocket: WebSocket, task_id: str):
    """注册下载任务的WebSocket连接"""
    await websocket.accept()
    
    if task_id not in active_connections:
        active_connections[task_id] = []
    active_connections[task_id].append(websocket)
    
    try:
        # 持续接收前端消息（如取消指令）
        while True:
            data = await websocket.receive_json()
            
            if data.get("action") == "cancel":
                await download_manager.cancel_download(task_id)
            
    except WebSocketDisconnect:
        pass
    finally:
        # 清理连接
        if task_id in active_connections:
            active_connections[task_id].remove(websocket)
            if not active_connections[task_id]:
                del active_connections[task_id]

async def broadcast_progress(task_id: str, event: DownloadProgressEvent):
    """广播进度到所有连接的客户端"""
    if task_id not in active_connections:
        return
    
    message = {
        "type": "download.progress",
        "data": {
            "task_id": event.task_id,
            "progress_percent": event.progress_percent,
            "speed": format_speed(event.speed_bytes_per_sec),
            "downloaded": format_size(event.downloaded_bytes),
            "total": format_size(event.total_bytes),
            "current_file": event.current_file,
            "file_count": f"{event.file_count_completed}/{event.file_count_total}",
            "eta": format_eta(event.estimated_seconds_remaining),
            "timestamp": datetime.utcnow().isoformat()
        }
    }
    
    # 发送给所有连接的客户端
    disconnected = []
    for ws in active_connections[task_id]:
        try:
            await ws.send_json(message)
        except Exception:
            disconnected.append(ws)
    
    # 清理断开的连接
    for ws in disconnected:
        active_connections[task_id].remove(ws)

# 辅助函数
def format_speed(bps: int) -> str:
    """格式化速度"""
    if bps >= 1024**3:
        return f"{bps / 1024**3:.1f} GB/s"
    elif bps >= 1024**2:
        return f"{bps / 1024**2:.1f} MB/s"
    elif bps >= 1024:
        return f"{bps / 1024:.1f} KB/s"
    return f"{bps} B/s"

def format_size(bytes_val: int) -> str:
    """格式化大小"""
    if bytes_val >= 1024**4:
        return f"{bytes_val / 1024**4:.1f} TB"
    elif bytes_val >= 1024**3:
        return f"{bytes_val / 1024**3:.1f} GB"
    elif bytes_val >= 1024**2:
        return f"{bytes_val / 1024**2:.1f} MB"
    elif bytes_val >= 1024:
        return f"{bytes_val / 1024:.1f} KB"
    return f"{bytes_val} B"

def format_eta(seconds: int | None) -> str:
    """格式化预计时间"""
    if seconds is None:
        return "计算中..."
    if seconds < 60:
        return f"{seconds}秒"
    elif seconds < 3600:
        return f"{seconds // 60}分{seconds % 60}秒"
    return f"{seconds // 3600}时{(seconds % 3600) // 60}分"
```

### 3.4 FastAPI路由

```python
# app/api/v1/download.py
"""
下载管理API + WebSocket
"""

from fastapi import APIRouter, Depends, HTTPException, WebSocket
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.auth import get_current_user, User
from app.schemas.download import (
    DownloadCreateRequest, DownloadTaskResponse, DownloadProgressEvent
)
from app.services.download_service import (
    download_manager, DownloadConfig, DownloadState
)
from app.websocket.download_ws import (
    register_download_websocket, broadcast_progress
)

router = APIRouter(prefix="/downloads", tags=["Downloads"])

# ========== REST API ==========

@router.post("/tasks", response_model=DownloadTaskResponse)
async def create_download_task(
    request: DownloadCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """创建下载任务"""
    config = DownloadConfig(
        provider=request.provider,
        object_uri=request.object_uri,
        destination_dir=request.destination_dir,
        recursive=request.recursive
    )
    
    state = download_manager.create_task(config)
    
    # TODO: 保存到数据库
    
    return DownloadTaskResponse(
        task_id=state.task_id,
        status=state.status,
        provider=request.provider,
        object_uri=request.object_uri,
        destination_path=f"{request.destination_dir}/{state.task_id}",
        created_at=datetime.utcnow()
    )

@router.post("/tasks/{task_id}/start")
async def start_download(
    task_id: str,
    current_user: User = Depends(get_current_user)
):
    """启动下载任务"""
    # TODO: 从数据库恢复配置
    config = DownloadConfig(...)  # 从数据库读取
    
    # 启动下载（在后台运行）
    asyncio.create_task(
        download_manager.start_download(
            task_id=task_id,
            config=config,
            progress_callback=lambda e: broadcast_progress(task_id, e)
        )
    )
    
    return {"message": "下载已启动", "task_id": task_id}

@router.get("/tasks/{task_id}", response_model=DownloadTaskResponse)
def get_task_status(
    task_id: str,
    current_user: User = Depends(get_current_user)
):
    """获取任务状态"""
    state = download_manager.get_task(task_id)
    if not state:
        raise HTTPException(404, "任务不存在")
    
    return _state_to_response(state)

@router.post("/tasks/{task_id}/cancel")
async def cancel_download(
    task_id: str,
    current_user: User = Depends(get_current_user)
):
    """取消下载"""
    await download_manager.cancel_download(task_id)
    return {"message": "下载已取消", "task_id": task_id}

@router.get("/tasks", response_model=list[DownloadTaskResponse])
def list_tasks(
    current_user: User = Depends(get_current_user)
):
    """列出所有下载任务"""
    states = download_manager.list_tasks(current_user.id)
    return [_state_to_response(s) for s in states]

# ========== WebSocket ==========

@router.websocket("/ws/{task_id}")
async def download_websocket(websocket: WebSocket, task_id: str):
    """下载进度WebSocket — 前端连接此接口接收实时进度"""
    await register_download_websocket(websocket, task_id)

# 辅助函数
def _state_to_response(state: DownloadState) -> DownloadTaskResponse:
    return DownloadTaskResponse(
        task_id=state.task_id,
        status=state.status,
        provider="",  # TODO: 从数据库读取
        object_uri="",
        destination_path="",
        total_bytes=state.total_bytes,
        downloaded_bytes=state.downloaded_bytes,
        progress_percent=state.progress_percent,
        speed_bytes_per_sec=state.speed_bps,
        current_file=state.current_file,
        file_count_total=state.file_count_total,
        file_count_completed=state.file_count_completed,
        started_at=getattr(state, 'started_at', None),
        estimated_end_at=(
            datetime.utcnow() + timedelta(seconds=state.estimated_seconds_remaining or 0)
            if state.estimated_seconds_remaining else None
        ),
        created_at=datetime.utcnow()
    )
```

---

## 四、前端完整代码

### 4.1 下载管理 Composable

```typescript
// composables/useDownloadManager.ts
/**
 * 下载管理 Composable — 管理云存储下载的全生命周期
 * 支持阿里云OSS/火山引擎TOS/华为云OBS
 */

import { ref, computed, reactive } from 'vue'

export interface DownloadTask {
  taskId: string
  status: 'pending' | 'downloading' | 'paused' | 'completed' | 'failed' | 'cancelled'
  provider: string
  objectUri: string
  destinationPath: string
  progressPercent: number
  speedBps: number
  downloadedBytes: number
  totalBytes: number
  currentFile: string
  fileCountTotal: number
  fileCountCompleted: number
  speed: string        // 格式化后的速度（如 "8.5 MB/s"）
  downloaded: string   // 格式化后的大小（如 "856 MB"）
  total: string        // 格式化后的大小
  eta: string          // 预计剩余时间（如 "45秒"）
  errorMessage?: string
}

export function useDownloadManager() {
  // State
  const tasks = reactive<Record<string, DownloadTask>>({})
  const activeTaskId = ref<string | null>(null)
  const wsConnections = reactive<Record<string, WebSocket>>({})
  
  // Getters
  const activeTask = computed(() => {
    return activeTaskId.value ? tasks[activeTaskId.value] : null
  })
  
  const isDownloading = computed(() => {
    return activeTask.value?.status === 'downloading'
  })
  
  // ========== 创建下载任务 ==========
  async function createTask(params: {
    provider: string
    objectUri: string
    destinationDir?: string
    recursive?: boolean
  }): Promise<string> {
    const response = await fetch('/api/v1/downloads/tasks', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${localStorage.getItem('token')}`
      },
      body: JSON.stringify({
        provider: params.provider,
        object_uri: params.objectUri,
        destination_dir: params.destinationDir || '/data/downloads',
        recursive: params.recursive || false
      })
    })
    
    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || '创建下载任务失败')
    }
    
    const data = await response.json()
    
    // 初始化任务状态
    tasks[data.task_id] = reactive<DownloadTask>({
      taskId: data.task_id,
      status: 'pending',
      provider: params.provider,
      objectUri: params.objectUri,
      destinationPath: data.destination_path,
      progressPercent: 0,
      speedBps: 0,
      downloadedBytes: 0,
      totalBytes: 0,
      currentFile: '',
      fileCountTotal: 0,
      fileCountCompleted: 0,
      speed: '0 B/s',
      downloaded: '0 B',
      total: '0 B',
      eta: '计算中...'
    })
    
    return data.task_id
  }
  
  // ========== 启动下载 + WebSocket连接 ==========
  async function startDownload(taskId: string) {
    const task = tasks[taskId]
    if (!task) throw new Error('任务不存在')
    
    activeTaskId.value = taskId
    
    // 1. 先调用REST API启动下载
    const response = await fetch(`/api/v1/downloads/tasks/${taskId}/start`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
    })
    
    if (!response.ok) {
      throw new Error('启动下载失败')
    }
    
    // 2. 建立WebSocket连接接收实时进度
    connectWebSocket(taskId)
  }
  
  // ========== WebSocket连接 ==========
  function connectWebSocket(taskId: string) {
    const token = localStorage.getItem('token')
    const ws = new WebSocket(
      `wss://${window.location.host}/api/v1/downloads/ws/${taskId}?token=${token}`
    )
    
    ws.onopen = () => {
      console.log(`[下载 ${taskId}] WebSocket已连接`)
      wsConnections[taskId] = ws
    }
    
    ws.onmessage = (event) => {
      const message = JSON.parse(event.data)
      
      if (message.type === 'download.progress') {
        updateTaskProgress(taskId, message.data)
      } else if (message.type === 'download.complete') {
        tasks[taskId].status = 'completed'
        tasks[taskId].progressPercent = 100
        closeWebSocket(taskId)
      } else if (message.type === 'download.error') {
        tasks[taskId].status = 'failed'
        tasks[taskId].errorMessage = message.data.error
        closeWebSocket(taskId)
      }
    }
    
    ws.onerror = (error) => {
      console.error(`[下载 ${taskId}] WebSocket错误:`, error)
    }
    
    ws.onclose = () => {
      console.log(`[下载 ${taskId}] WebSocket已关闭`)
      delete wsConnections[taskId]
    }
  }
  
  // ========== 更新进度 ==========
  function updateTaskProgress(taskId: string, data: any) {
    const task = tasks[taskId]
    if (!task) return
    
    task.status = 'downloading'
    task.progressPercent = data.progress_percent
    task.speed = data.speed
    task.downloaded = data.downloaded
    task.total = data.total
    task.currentFile = data.current_file
    task.fileCountCompleted = parseInt(data.file_count.split('/')[0])
    task.fileCountTotal = parseInt(data.file_count.split('/')[1])
    task.eta = data.eta
  }
  
  // ========== 取消下载 ==========
  async function cancelDownload(taskId: string) {
    // 通过WebSocket发送取消指令
    const ws = wsConnections[taskId]
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ action: 'cancel' }))
    }
    
    // 同时调用REST API
    await fetch(`/api/v1/downloads/tasks/${taskId}/cancel`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
    })
    
    tasks[taskId].status = 'cancelled'
    closeWebSocket(taskId)
  }
  
  // ========== 清理 ==========
  function closeWebSocket(taskId: string) {
    const ws = wsConnections[taskId]
    if (ws) {
      ws.close()
      delete wsConnections[taskId]
    }
  }
  
  function disconnectAll() {
    Object.keys(wsConnections).forEach(taskId => closeWebSocket(taskId))
  }
  
  return {
    tasks,
    activeTask,
    activeTaskId,
    isDownloading,
    createTask,
    startDownload,
    cancelDownload,
    disconnectAll
  }
}
```

### 4.2 下载进度组件（Vue 3）

```vue
<!-- components/DownloadProgressPanel.vue -->
<template>
  <div class="download-progress-panel" v-if="activeTask">
    <!-- 头部信息 -->
    <div class="panel-header">
      <div class="title-row">
        <n-tag :type="statusTagType" size="small">{{ statusText }}</n-tag>
        <span class="file-count" v-if="activeTask.fileCountTotal > 1">
          文件 {{ activeTask.fileCountCompleted }}/{{ activeTask.fileCountTotal }}
        </span>
      </div>
      <n-button 
        v-if="isDownloading" 
        text 
        type="error" 
        size="small"
        @click="$emit('cancel', activeTask.taskId)"
      >
        <template #icon><n-icon><CloseOutline /></n-icon></template>
        取消
      </n-button>
    </div>
    
    <!-- 整体进度条 -->
    <div class="overall-progress">
      <div class="progress-info">
        <span class="percent">{{ activeTask.progressPercent }}%</span>
        <span class="size">{{ activeTask.downloaded }} / {{ activeTask.total }}</span>
      </div>
      <n-progress
        :percentage="activeTask.progressPercent"
        :show-indicator="false"
        :height="12"
        :border-radius="6"
        :color="progressColor"
        :track-color="isDark ? '#2a2a3c' : '#e8e8e8'"
        type="line"
        class="main-progress"
      />
    </div>
    
    <!-- 详细信息 -->
    <div class="detail-info">
      <div class="info-item">
        <n-icon><SpeedometerOutline /></n-icon>
        <span>速度: <strong>{{ activeTask.speed }}</strong></span>
      </div>
      <div class="info-item">
        <n-icon><TimeOutline /></n-icon>
        <span>剩余: <strong>{{ activeTask.eta }}</strong></span>
      </div>
    </div>
    
    <!-- 当前文件 -->
    <div class="current-file" v-if="activeTask.currentFile">
      <n-icon><DocumentOutline /></n-icon>
      <span class="filename" :title="activeTask.currentFile">
        {{ activeTask.currentFile }}
      </span>
    </div>
    
    <!-- 错误信息 -->
    <n-alert 
      v-if="activeTask.errorMessage" 
      type="error" 
      :show-icon="false"
      class="error-alert"
    >
      {{ activeTask.errorMessage }}
    </n-alert>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { CloseOutline, SpeedometerOutline, TimeOutline, DocumentOutline } from '@vicons/ionicons5'
import type { DownloadTask } from '@/composables/useDownloadManager'

const props = defineProps<{
  activeTask: DownloadTask | null
  isDownloading: boolean
  isDark?: boolean
}>()

const emit = defineEmits<{
  cancel: [taskId: string]
}>()

const statusTagType = computed(() => {
  const map: Record<string, string> = {
    'pending': 'default',
    'downloading': 'primary',
    'paused': 'warning',
    'completed': 'success',
    'failed': 'error',
    'cancelled': 'error'
  }
  return map[props.activeTask?.status || 'pending'] as any
})

const statusText = computed(() => {
  const map: Record<string, string> = {
    'pending': '等待中',
    'downloading': '下载中',
    'paused': '已暂停',
    'completed': '已完成',
    'failed': '失败',
    'cancelled': '已取消'
  }
  return map[props.activeTask?.status || 'pending']
})

const progressColor = computed(() => {
  if (props.activeTask?.status === 'failed') return '#ff4d4f'
  if (props.activeTask?.status === 'completed') return '#52c41a'
  return '#4f8ef7'
})
</script>

<style scoped>
.download-progress-panel {
  background: var(--card-bg, #1a1a2e);
  border: 1px solid var(--border-color, #2a2a3c);
  border-radius: 12px;
  padding: 16px;
  min-width: 360px;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.title-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.file-count {
  font-size: 12px;
  color: #888;
}

.overall-progress {
  margin-bottom: 12px;
}

.progress-info {
  display: flex;
  justify-content: space-between;
  margin-bottom: 6px;
}

.percent {
  font-size: 18px;
  font-weight: 600;
  color: #4f8ef7;
}

.size {
  font-size: 13px;
  color: #888;
}

.main-progress {
  margin: 0;
}

:deep(.main-progress .n-progress-graph-line-fill) {
  transition: width 0.3s ease;
}

.detail-info {
  display: flex;
  gap: 20px;
  margin-bottom: 10px;
}

.info-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #aaa;
}

.info-item strong {
  color: #e0e0e0;
}

.current-file {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 10px;
  background: rgba(255,255,255,0.03);
  border-radius: 6px;
  font-size: 12px;
  color: #888;
}

.filename {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}

.error-alert {
  margin-top: 10px;
}
</style>
```

### 4.3 下载表单组件

```vue
<!-- components/CloudDownloadForm.vue -->
<template>
  <div class="cloud-download-form">
    <n-form
      ref="formRef"
      :model="form"
      :rules="rules"
      label-placement="left"
      label-width="100"
    >
      <!-- 云服务商选择 -->
      <n-form-item label="云服务商" path="provider">
        <n-select
          v-model:value="form.provider"
          :options="providerOptions"
          placeholder="选择云服务商"
          @update:value="onProviderChange"
        />
      </n-form-item>
      
      <!-- 对象URI -->
      <n-form-item label="对象URI" path="objectUri">
        <n-input
          v-model:value="form.objectUri"
          type="textarea"
          :rows="2"
          placeholder="如: oss://mybucket/data/tools/"
        />
        <template #feedback>
          <span class="uri-hint">
            {{ providerHint }}
          </span>
        </template>
      </n-form-item>
      
      <!-- 目标目录 -->
      <n-form-item label="保存到" path="destinationDir">
        <n-input
          v-model:value="form.destinationDir"
          placeholder="/data/downloads"
        />
      </n-form-item>
      
      <!-- 递归下载 -->
      <n-form-item label=" ">
        <n-checkbox v-model:checked="form.recursive">
          递归下载目录下所有文件
        </n-checkbox>
      </n-form-item>
      
      <!-- 提交按钮 -->
      <n-form-item label=" ">
        <n-button
          type="primary"
          size="large"
          :loading="submitting"
          :disabled="!form.provider || !form.objectUri"
          @click="handleSubmit"
        >
          <template #icon><n-icon><DownloadOutline /></n-icon></template>
          开始下载
        </n-button>
      </n-form-item>
    </n-form>
    
    <!-- 下载进度面板 -->
    <DownloadProgressPanel
      v-if="downloadManager.activeTask"
      :active-task="downloadManager.activeTask"
      :is-downloading="downloadManager.isDownloading"
      :is-dark="true"
      @cancel="downloadManager.cancelDownload"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, reactive } from 'vue'
import { DownloadOutline } from '@vicons/ionicons5'
import { useDownloadManager } from '@/composables/useDownloadManager'
import DownloadProgressPanel from './DownloadProgressPanel.vue'

const downloadManager = useDownloadManager()

const formRef = ref()
const submitting = ref(false)

const form = reactive({
  provider: null as string | null,
  objectUri: '',
  destinationDir: '/data/downloads',
  recursive: true
})

const providerOptions = [
  { label: '阿里云 OSS', value: 'aliyun' },
  { label: '火山引擎 TOS', value: 'volcengine' },
  { label: '华为云 OBS', value: 'huaweicloud' }
]

const providerHint = computed(() => {
  const hints: Record<string, string> = {
    'aliyun': '格式: oss://bucket-name/path/to/file/',
    'volcengine': '格式: tos://bucket-name/path/to/file/',
    'huaweicloud': '格式: obs://bucket-name/path/to/file/'
  }
  return hints[form.provider || ''] || '请先选择云服务商'
})

const rules = {
  provider: { required: true, message: '请选择云服务商', trigger: 'change' },
  objectUri: { 
    required: true, 
    message: '请输入对象URI',
    trigger: 'blur'
  }
}

function onProviderChange(value: string) {
  // 自动更新URI前缀
  const prefixes: Record<string, string> = {
    'aliyun': 'oss://',
    'volcengine': 'tos://',
    'huaweicloud': 'obs://'
  }
  if (!form.objectUri) {
    form.objectUri = prefixes[value] || ''
  }
}

async function handleSubmit() {
  try {
    await formRef.value?.validate()
    
    submitting.value = true
    
    // 1. 创建任务
    const taskId = await downloadManager.createTask({
      provider: form.provider!,
      objectUri: form.objectUri,
      destinationDir: form.destinationDir,
      recursive: form.recursive
    })
    
    // 2. 启动下载
    await downloadManager.startDownload(taskId)
    
  } catch (error: any) {
    window.$message?.error(error.message || '提交失败')
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.cloud-download-form {
  max-width: 600px;
}

.uri-hint {
  font-size: 12px;
  color: #888;
}
</style>
```

---

## 五、二进制工具安装检查脚本

```bash
#!/bin/bash
# /data/omichub/bin/check-tools.sh
# 检查三个云存储工具是否就绪

echo "=== OmicHub 云存储工具检查 ==="
echo ""

BIN_DIR="/data/omichub/bin"
TOOLS=("ossutil" "tosutil" "obsutil")
PROVIDERS=("阿里云 OSS" "火山引擎 TOS" "华为云 OBS")

all_ready=true

for i in "${!TOOLS[@]}"; do
    tool="${TOOLS[$i]}"
    provider="${PROVIDERS[$i]}"
    path="${BIN_DIR}/${tool}"
    
    echo -n "[${provider}] ${tool} ... "
    
    if [ ! -f "$path" ]; then
        echo "❌ 不存在 (${path})"
        all_ready=false
    elif [ ! -x "$path" ]; then
        echo "⚠️  没有执行权限，正在修复..."
        chmod +x "$path"
        echo "✅ 已修复"
    else
        # 测试版本
        version=$($path --version 2>&1 | head -1 || echo "unknown")
        echo "✅ 就绪 (${version})"
    fi
done

echo ""
if $all_ready; then
    echo "所有工具已就绪！"
else
    echo "部分工具缺失，请下载并放置到 ${BIN_DIR}/"
    exit 1
fi
```

---

## 六、文件清单

### 后端新增文件（6个）
```
app/
├── schemas/
│   └── download.py              # Pydantic DTO
├── services/
│   └── download_service.py      # 下载管理器（核心）
├── api/v1/
│   └── download.py              # FastAPI路由
├── websocket/
│   └── download_ws.py           # WebSocket推送
└── database/migrations/
    └── V010__add_download_tasks.py  # 数据库迁移
```

### 前端新增文件（3个）
```
src/
├── composables/
│   └── useDownloadManager.ts    # 下载管理Composable
└── components/
    ├── DownloadProgressPanel.vue  # 进度面板
    └── CloudDownloadForm.vue      # 下载表单
```

---

## 七、API接口清单

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/v1/downloads/tasks` | 创建下载任务 |
| `POST` | `/api/v1/downloads/tasks/{task_id}/start` | 启动下载 |
| `GET` | `/api/v1/downloads/tasks/{task_id}` | 获取任务状态 |
| `POST` | `/api/v1/downloads/tasks/{task_id}/cancel` | 取消下载 |
| `GET` | `/api/v1/downloads/tasks` | 列出所有任务 |
| `WS` | `/api/v1/downloads/ws/{task_id}` | **WebSocket实时进度** |
