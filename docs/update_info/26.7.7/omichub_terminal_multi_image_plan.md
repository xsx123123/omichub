# OmicHub 沙盒终端多镜像选择功能实现计划

> **目标**: 在 `tools/terminal/` 下新增镜像配置文件，前端支持选择不同镜像启动沙盒终端，后端按所选镜像创建容器。  
> **阶段**: 先实现基础框架（单镜像可用），后续逐步扩展多镜像。  
> **日期**: 2026-07-08

---

## 1. 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│  前端 (Vue3 + Arco Design)                                       │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  TerminalView.vue / BioTools 页面                         │  │
│  │  ┌──────────────┐  ┌──────────────────┐                 │  │
│  │  │ 镜像选择卡片 │  │  xterm.js 终端   │                 │  │
│  │  │  (下拉/卡片) │  │  (WebSocket 代理) │                 │  │
│  │  └──────────────┘  └──────────────────┘                 │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼ POST /api/v1/terminal/sessions
┌─────────────────────────────────────────────────────────────────┐
│  后端 (FastAPI)                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  api/v1/terminal.py                                      │  │
│  │  POST /sessions -> TerminalService.create_session()      │  │
│  │  GET  /environments -> 返回镜像列表                      │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  application/services/terminal_service.py                │  │
│  │ 读取 terminal_images.yaml -> 选择镜像 -> 创建容器          │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  infrastructure/terminal/docker_manager.py               │  │
│  │  create_container(image=..., env_id=...)                │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  配置文件                                                        │
│  tools/terminal/terminal_images.yaml  <- 镜像定义                  │
│  tools/terminal/docker/                                          │
│    ├── Dockerfile.base      <- 基础镜像（当前默认）               │
│    ├── Dockerfile.rnaseq    <- RNAseq 环境（后续扩展）             │
│    └── Dockerfile.singlecell <- 单细胞（后续扩展）                │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. 配置文件设计

### 2.1 文件位置

```
tools/terminal/
├── terminal_images.yaml        # <- 新增：镜像配置文件
├── README.md
├── terminal_config.yaml        # 现有运行时配置
└── docker/
    ├── Dockerfile              # 现有基础镜像（可改名为 Dockerfile.base）
    ├── Dockerfile.rnaseq       # <- 后续扩展
    ├── Dockerfile.singlecell   # <- 后续扩展
    └── bashrc
```

### 2.2 配置格式（YAML）

```yaml
# tools/terminal/terminal_images.yaml
# 沙盒终端可用镜像定义
# 修改后需重新加载后端配置（或支持热重载）

version: "1.0"

# 镜像仓库前缀（可选，为空则使用完整镜像名）
registry_prefix: ""

# 默认镜像（用户未选择时）
default_image: "base"

# 镜像列表
images:
  - id: "base"
    name: "基础生信"
    description: "预装 samtools, bcftools, bedtools, fastqc, seqkit, python3, R"
    image: "omichub/sandbox-terminal:latest"
    tags: ["基础", "常用"]
    icon: "🔧"
    # 默认资源限制（可覆盖 terminal_config.yaml 的全局默认值）
    resources:
      memory_mb: 512
      cpu_cores: 1.0
    # 环境变量（注入到容器）
    env:
      - name: "OMICHUB_ENV"
        value: "base"
    # 是否启用
    enabled: true

  # === 以下为预留扩展，后续逐步实现 ===
  #
  # - id: "rnaseq"
  #   name: "RNAseq 分析"
  #   description: "DESeq2, edgeR, limma, STAR, HTSeq 差异表达全流程"
  #   image: "omichub/sandbox-rnaseq:latest"
  #   tags: ["转录组", "差异表达"]
  #   icon: "🧬"
  #   resources:
  #     memory_mb: 1024
  #     cpu_cores: 2.0
  #   env:
  #     - name: "OMICHUB_ENV"
  #       value: "rnaseq"
  #   enabled: false  # 先禁用，等镜像构建完成后再启用
  #
  # - id: "singlecell"
  #   name: "单细胞分析"
  #   description: "Seurat, Scanpy, Monocle3, 降维聚类轨迹分析"
  #   image: "omichub/sandbox-singlecell:latest"
  #   tags: ["单细胞", "轨迹分析"]
  #   icon: "🧠"
  #   resources:
  #     memory_mb: 2048
  #     cpu_cores: 2.0
  #   env:
  #     - name: "OMICHUB_ENV"
  #       value: "singlecell"
  #   enabled: false
```

### 2.3 配置加载方式

**方案 A：启动时加载（简单）**
- 后端启动时读取 `terminal_images.yaml`
- 存入内存（如 `app.state.terminal_images`）
- 修改后需重启后端

**方案 B：热重载（推荐，与现有 terminal_config.yaml 一致）**
- 复用现有的 `ConfigManager`（mtime 热重载）
- 监听 `terminal_images.yaml` 修改时间
- 修改后自动重新加载，无需重启

---

## 3. 后端改造计划

### 3.1 新增配置模型

```python
# src/omichub/application/schemas/terminal.py

from pydantic import BaseModel, Field
from typing import List, Optional, Dict

class TerminalImageResource(BaseModel):
    """镜像资源限制"""
    memory_mb: int = 512
    cpu_cores: float = 1.0

class TerminalImageEnv(BaseModel):
    """镜像环境变量"""
    name: str
    value: str

class TerminalImage(BaseModel):
    """单个镜像定义"""
    id: str = Field(..., description="镜像唯一标识")
    name: str = Field(..., description="显示名称")
    description: str = Field(..., description="描述")
    image: str = Field(..., description="Docker 镜像名")
    tags: List[str] = Field(default_factory=list)
    icon: str = Field(default="🔧", description="前端显示图标")
    resources: TerminalImageResource = Field(default_factory=TerminalImageResource)
    env: List[TerminalImageEnv] = Field(default_factory=list)
    enabled: bool = True

class TerminalImagesConfig(BaseModel):
    """镜像配置根模型"""
    version: str = "1.0"
    registry_prefix: Optional[str] = None
    default_image: str = "base"
    images: List[TerminalImage] = Field(default_factory=list)

    def get_image(self, image_id: str) -> Optional[TerminalImage]:
        """根据 ID 获取镜像配置"""
        for img in self.images:
            if img.id == image_id and img.enabled:
                return img
        return None

    def get_enabled_images(self) -> List[TerminalImage]:
        """获取所有启用的镜像"""
        return [img for img in self.images if img.enabled]

    def get_default_image(self) -> Optional[TerminalImage]:
        """获取默认镜像"""
        return self.get_image(self.default_image)
```

### 3.2 配置加载器扩展

```python
# src/omichub/tools/terminal/config.py
# 在现有 ConfigManager 基础上扩展

import yaml
from pathlib import Path
from typing import Optional
from omichub.application.schemas.terminal import TerminalImagesConfig, TerminalImage

class TerminalConfigManager:
    """终端配置管理器（支持热重载）"""

    def __init__(self, config_path: str, images_config_path: str):
        self.config_path = Path(config_path)
        self.images_config_path = Path(images_config_path)
        self._config = None
        self._images_config = None
        self._last_mtime = 0
        self._images_last_mtime = 0

    def _load_images_config(self) -> TerminalImagesConfig:
        """加载镜像配置"""
        if not self.images_config_path.exists():
            # 返回默认配置（仅基础镜像）
            return TerminalImagesConfig(
                images=[TerminalImage(
                    id="base",
                    name="基础生信",
                    description="预装常用生信工具",
                    image="omichub/sandbox-terminal:latest",
                    enabled=True
                )]
            )

        with open(self.images_config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return TerminalImagesConfig(**data)

    @property
    def images_config(self) -> TerminalImagesConfig:
        """获取镜像配置（自动热重载）"""
        current_mtime = self.images_config_path.stat().st_mtime
        if current_mtime != self._images_last_mtime or self._images_config is None:
            self._images_config = self._load_images_config()
            self._images_last_mtime = current_mtime
        return self._images_config
```

### 3.3 API 路由改造

```python
# src/omichub/api/v1/terminal.py

from fastapi import APIRouter, Depends, WebSocket
from omichub.application.schemas.terminal import (
    CreateSessionRequest, CreateSessionResponse,
    TerminalImage  # 新增
)
from omichub.application.services.terminal_service import TerminalService

router = APIRouter(prefix="/api/v1/terminal", tags=["terminal"])

# ========== 新增接口：获取可用镜像列表 ==========
@router.get("/environments", response_model=List[TerminalImage])
async def list_environments(
    service: TerminalService = Depends()
):
    """
    获取所有启用的沙盒环境（镜像）列表
    前端调用此接口渲染镜像选择面板
    """
    return service.get_enabled_images()

# ========== 改造接口：创建会话 ==========
@router.post("/sessions", response_model=CreateSessionResponse)
async def create_session(
    request: CreateSessionRequest,
    service: TerminalService = Depends()
):
    """
    创建沙盒终端会话
    request 中新增 image_id 字段，用于指定镜像
    """
    session = await service.create_session(
        user_id=request.user_id,
        image_id=request.image_id,  # 新增参数
        custom_resources=request.resources,
    )
    return session

# ========== WebSocket 代理（保持不变） ==========
@router.websocket("/sessions/{session_id}/ws")
async def terminal_websocket(
    websocket: WebSocket,
    session_id: str,
    service: TerminalService = Depends()
):
    """WebSocket 双向代理"""
    await service.proxy_websocket(websocket, session_id)
```

### 3.4 请求/响应模型更新

```python
# src/omichub/application/schemas/terminal.py

class CreateSessionRequest(BaseModel):
    """创建会话请求"""
    user_id: str
    image_id: Optional[str] = "base"  # 新增：镜像 ID，默认基础镜像
    resources: Optional[TerminalImageResource] = None  # 用户自定义资源

class CreateSessionResponse(BaseModel):
    """创建会话响应"""
    session_id: str
    ws_url: str
    image_id: str  # 新增：实际使用的镜像 ID
    image_name: str  # 新增：镜像显示名称
    expires_at: Optional[str] = None  # 超时时间
```

### 3.5 TerminalService 改造

```python
# src/omichub/application/services/terminal_service.py

class TerminalService:
    def __init__(self, config_manager: TerminalConfigManager):
        self.config = config_manager.config
        self.images_config = config_manager.images_config
        self.docker_manager = DockerManager(self.config, self.images_config)

    def get_enabled_images(self) -> List[TerminalImage]:
        """获取所有启用的镜像"""
        return self.images_config.get_enabled_images()

    async def create_session(
        self,
        user_id: str,
        image_id: Optional[str] = None,
        custom_resources: Optional[Dict] = None,
    ) -> CreateSessionResponse:
        """创建会话"""

        # 1. 确定镜像
        if not image_id:
            image_id = self.images_config.default_image

        image_config = self.images_config.get_image(image_id)
        if not image_config:
            raise ValueError(f"镜像不存在或未启用: {image_id}")

        # 2. 生成会话 ID
        session_id = generate_session_id()

        # 3. 合并资源限制（镜像默认 < 用户自定义 < 全局上限）
        resources = image_config.resources.dict()
        if custom_resources:
            resources.update({k: v for k, v in custom_resources.items() if v is not None})

        # 4. 创建容器
        container = self.docker_manager.create_container(
            session_id=session_id,
            user_id=user_id,
            image_config=image_config,  # 传入完整镜像配置
            custom_resources=resources,
        )

        # 5. 保存会话到数据库
        await self.save_session(session_id, user_id, image_id, container.id)

        # 6. 返回
        return CreateSessionResponse(
            session_id=session_id,
            ws_url=f"/api/v1/terminal/sessions/{session_id}/ws",
            image_id=image_config.id,
            image_name=image_config.name,
        )
```

### 3.6 DockerManager 改造

```python
# src/omichub/infrastructure/terminal/docker_manager.py

class DockerManager:
    def __init__(self, config, images_config):
        self.client = docker.from_env()
        self.config = config
        self.images_config = images_config

    def create_container(
        self,
        session_id: str,
        user_id: str,
        image_config: TerminalImage,  # 接收镜像配置
        custom_resources: Optional[Dict] = None,
    ):
        """创建容器"""

        # 1. 处理镜像名（支持 registry_prefix）
        image_name = image_config.image
        if self.images_config.registry_prefix:
            # 如果 image 不以 registry_prefix 开头，则添加前缀
            if not image_name.startswith(self.images_config.registry_prefix):
                image_name = f"{self.images_config.registry_prefix}/{image_name}"

        # 2. 拉取镜像（如果本地不存在）
        self._pull_image_if_needed(image_name)

        # 3. 准备环境变量
        env_vars = {}
        for env in image_config.env:
            env_vars[env.name] = env.value

        # 4. 准备挂载
        host_workspace = os.path.join(
            self.config.storage.workspace_base,
            user_id,
            "workspace"
        )
        os.makedirs(host_workspace, exist_ok=True)
        # 权限设置...

        # 5. 创建容器
        container = self.client.containers.run(
            image=image_name,
            name=f"ttyd-{session_id}",
            network=self.config.network.name,
            hostname=f"ttyd-{session_id}",

            volumes={
                host_workspace: {
                    "bind": "/home/omichub/workspace",
                    "mode": "rw",
                },
            },

            environment=env_vars,  # 注入镜像特定环境变量

            user="1000:1000",
            read_only=True,
            cap_drop=["ALL"],
            security_opt=["no-new-privileges:true"],

            mem_limit=f"{custom_resources.get('memory_mb', 512)}m",
            memswap_limit=f"{custom_resources.get('memory_mb', 512)}m",
            cpu_quota=int(custom_resources.get('cpu_cores', 1.0) * 100000),
            pids_limit=100,

            tmpfs={
                "/tmp": "rw,noexec,nosuid,size=100m",
                "/home/omichub/.cache": "rw,noexec,nosuid,size=50m",
            },

            auto_remove=True,
            detach=True,
            tty=True,
        )

        return container

    def _pull_image_if_needed(self, image_name: str):
        """如果本地没有镜像则拉取"""
        try:
            self.client.images.get(image_name)
        except docker.errors.ImageNotFound:
            logger.info(f"Pulling image: {image_name}")
            self.client.images.pull(image_name)
```

---

## 4. 前端改造计划

### 4.1 API 封装

```typescript
// frontend/src/api/terminal.ts

import axios from 'axios'

export interface TerminalImage {
  id: string
  name: string
  description: string
  image: string
  tags: string[]
  icon: string
  resources: {
    memory_mb: number
    cpu_cores: number
  }
  enabled: boolean
}

export interface CreateSessionRequest {
  user_id: string
  image_id?: string        // 新增
  resources?: {
    memory_mb?: number
    cpu_cores?: number
  }
}

export interface CreateSessionResponse {
  session_id: string
  ws_url: string
  image_id: string       // 新增
  image_name: string      // 新增
  expires_at?: string
}

// 获取可用镜像列表
export async function getEnvironments(): Promise<TerminalImage[]> {
  const res = await axios.get('/api/v1/terminal/environments')
  return res.data
}

// 创建会话（新增 image_id 参数）
export async function createSession(
  data: CreateSessionRequest
): Promise<CreateSessionResponse> {
  const res = await axios.post('/api/v1/terminal/sessions', data)
  return res.data
}
```

### 4.2 Pinia Store 扩展

```typescript
// frontend/src/stores/terminal.ts

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { getEnvironments, createSession, TerminalImage } from '@/api/terminal'

export const useTerminalStore = defineStore('terminal', () => {
  // 状态
  const environments = ref<TerminalImage[]>([])
  const selectedImage = ref<string>('base')  // 默认选中基础镜像
  const currentSession = ref<any>(null)
  const loading = ref(false)

  // 计算属性
  const enabledEnvironments = computed(() => 
    environments.value.filter(e => e.enabled)
  )

  const selectedImageConfig = computed(() =>
    environments.value.find(e => e.id === selectedImage.value)
  )

  // 获取镜像列表
  async function fetchEnvironments() {
    environments.value = await getEnvironments()
    // 如果默认镜像不在列表中，选择第一个启用的
    if (!environments.value.find(e => e.id === selectedImage.value)) {
      selectedImage.value = environments.value[0]?.id || 'base'
    }
  }

  // 创建会话
  async function launchSession(userId: string, customResources?: any) {
    loading.value = true
    try {
      const session = await createSession({
        user_id: userId,
        image_id: selectedImage.value,
        resources: customResources,
      })
      currentSession.value = session
      return session
    } finally {
      loading.value = false
    }
  }

  return {
    environments,
    selectedImage,
    currentSession,
    loading,
    enabledEnvironments,
    selectedImageConfig,
    fetchEnvironments,
    launchSession,
  }
})
```

### 4.3 前端组件：镜像选择器（下拉方案 - 快速实现）

```vue
<!-- frontend/src/components/terminal/ImageSelector.vue -->
<template>
  <div class="image-selector">
    <a-select
      v-model="store.selectedImage"
      :loading="store.loading"
      :style="{ width: '280px' }"
      @change="onImageChange"
    >
      <a-option
        v-for="env in store.enabledEnvironments"
        :key="env.id"
        :value="env.id"
      >
        <span class="env-option">
          <span class="env-icon">{{ env.icon }}</span>
          <span class="env-name">{{ env.name }}</span>
          <span class="env-tag" v-if="env.tags.length">{{ env.tags[0] }}</span>
        </span>
      </a-option>
    </a-select>

    <!-- 镜像描述提示 -->
    <a-tooltip :content="selectedDesc" position="bottom">
      <icon-info-circle class="info-icon" />
    </a-tooltip>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useTerminalStore } from '@/stores/terminal'

const store = useTerminalStore()

const selectedDesc = computed(() => {
  const env = store.selectedImageConfig
  return env ? env.description : ''
})

function onImageChange(value: string) {
  store.selectedImage = value
}
</script>

<style scoped>
.image-selector {
  display: flex;
  align-items: center;
  gap: 8px;
}
.env-option {
  display: flex;
  align-items: center;
  gap: 6px;
}
.env-icon {
  font-size: 16px;
}
.env-name {
  font-weight: 500;
}
.env-tag {
  font-size: 11px;
  color: var(--color-text-3);
  background: var(--color-fill-2);
  padding: 0 6px;
  border-radius: 4px;
}
.info-icon {
  color: var(--color-text-3);
  cursor: pointer;
}
</style>
</template>
```

### 4.4 终端页面集成

```vue
<!-- frontend/src/views/BioTools/TerminalView.vue -->
<template>
  <div class="terminal-page">
    <!-- 顶部工具栏 -->
    <div class="terminal-toolbar">
      <div class="toolbar-left">
        <h3>云端沙盒终端</h3>
        <!-- 新增：镜像选择器 -->
        <ImageSelector v-if="!isRunning" />
      </div>
      <div class="toolbar-right">
        <a-button
          v-if="!isRunning"
          type="primary"
          :loading="store.loading"
          @click="startSession"
        >
          <icon-play /> 启动终端
        </a-button>
        <a-button
          v-else
          status="danger"
          @click="stopSession"
        >
          <icon-poweroff /> 销毁会话
        </a-button>
      </div>
    </div>

    <!-- 镜像信息展示（会话运行时） -->
    <div v-if="isRunning && currentImage" class="session-info">
      <a-tag color="arcoblue">
        <template #icon><icon-apps /></template>
        {{ currentImage.name }}
      </a-tag>
      <span class="session-id">会话: {{ store.currentSession?.session_id }}</span>
    </div>

    <!-- 终端区域 -->
    <div class="terminal-container" v-show="isRunning">
      <XTerminal :session-id="store.currentSession?.session_id" />
    </div>

    <!-- 空状态 -->
    <div v-if="!isRunning" class="empty-state">
      <icon-terminal class="empty-icon" />
      <p>选择分析环境后点击「启动终端」</p>
      <p class="empty-desc">预装工具链，退出即销毁，数据保留在工作目录</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useTerminalStore } from '@/stores/terminal'
import ImageSelector from '@/components/terminal/ImageSelector.vue'
import XTerminal from '@/components/terminal/XTerminal.vue'

const store = useTerminalStore()
const isRunning = ref(false)

const currentImage = computed(() =>
  store.environments.find(e => e.id === store.currentSession?.image_id)
)

onMounted(() => {
  // 页面加载时获取镜像列表
  store.fetchEnvironments()
})

async function startSession() {
  const session = await store.launchSession('current-user-id')
  if (session) {
    isRunning.value = true
  }
}

async function stopSession() {
  // 调用销毁 API...
  isRunning.value = false
  store.currentSession = null
}
</script>
```

---

## 5. 文件修改清单

### 5.1 新增文件

| 文件路径 | 作用 | 优先级 |
|---------|------|--------|
| `tools/terminal/terminal_images.yaml` | 镜像配置文件 | 高 |
| `src/omichub/application/schemas/terminal.py` | 新增镜像相关 Pydantic 模型 | 高 |
| `frontend/src/components/terminal/ImageSelector.vue` | 镜像选择下拉组件 | 高 |
| `frontend/src/api/terminal.ts` | 新增 `getEnvironments` 接口 | 高 |
| `frontend/src/stores/terminal.ts` | 扩展 Pinia store | 高 |
| `frontend/src/components/terminal/ImageCardSelector.vue` | 卡片选择器（后续迭代） | 中 |

### 5.2 修改文件

| 文件路径 | 修改内容 | 优先级 |
|---------|---------|--------|
| `src/omichub/tools/terminal/config.py` | 扩展 ConfigManager，支持加载 `terminal_images.yaml` | 高 |
| `src/omichub/api/v1/terminal.py` | 新增 `GET /environments` 接口；改造 `POST /sessions` | 高 |
| `src/omichub/application/services/terminal_service.py` | `create_session` 接收 `image_id` 参数 | 高 |
| `src/omichub/infrastructure/terminal/docker_manager.py` | `create_container` 接收 `image_config` 参数 | 高 |
| `frontend/src/views/BioTools/TerminalView.vue` | 集成 ImageSelector，显示镜像信息 | 高 |
| `frontend/src/components/terminal/XTerminal.vue` | 无改动（保持现有 WebSocket 逻辑） | 低 |

### 5.3 可选重命名

| 原文件 | 建议新名 | 原因 |
|--------|---------|------|
| `tools/terminal/docker/Dockerfile` | `Dockerfile.base` | 明确标识为基础镜像，与后续 `Dockerfile.rnaseq` 等区分 |

---

## 6. 实施步骤（推荐顺序）

### Phase 1：配置文件 + 后端读取（1 天）

1. 创建 `tools/terminal/terminal_images.yaml`，定义基础镜像
2. 扩展 `config.py` 的 `ConfigManager`，支持读取镜像配置
3. 新增 `schemas/terminal.py` 中的镜像模型
4. 修改 `terminal_service.py` 和 `docker_manager.py`，支持按镜像配置创建容器
5. 新增 `GET /environments` 和改造 `POST /sessions` 接口
6. 本地测试：通过 API 直接调用，确认能按指定镜像启动容器

### Phase 2：前端选择器（0.5 天）

1. 前端 API 层新增 `getEnvironments`
2. 扩展 Pinia store
3. 实现 `ImageSelector.vue`（下拉选择器）
4. 在 `TerminalView.vue` 中集成，页面加载时获取镜像列表
5. 联调测试：前端选择镜像 -> 后端创建对应容器 -> 终端正常连接

### Phase 3：体验优化（后续迭代）

1. 实现 `ImageCardSelector.vue` 卡片选择器，替换下拉框
2. 添加资源自定义滑块（内存/CPU）
3. 添加镜像搜索/过滤功能
4. 镜像构建流水线（CI/CD 自动构建 `Dockerfile.rnaseq` 等）

---

## 7. 当前阶段最小可用配置

```yaml
# tools/terminal/terminal_images.yaml
# 当前只启用一个基础镜像，后续逐步扩展

version: "1.0"
registry_prefix: ""
default_image: "base"

images:
  - id: "base"
    name: "基础生信"
    description: "samtools, bcftools, bedtools, fastqc, seqkit, python3, R, zsh"
    image: "omichub/sandbox-terminal:latest"
    tags: ["基础"]
    icon: "🔧"
    resources:
      memory_mb: 512
      cpu_cores: 1.0
    env:
      - name: "OMICHUB_ENV"
        value: "base"
      - name: "TERM"
        value: "xterm-256color"
    enabled: true
```

> 即使当前只有一个镜像，完成这套框架后，后续新增镜像只需：
> 1. 写 `Dockerfile.xxx` 构建镜像
> 2. 在 `terminal_images.yaml` 中增加一条配置
> 3. 前端自动显示新选项（因为列表是后端动态返回的）

---

*计划生成时间: 2026-07-08*
