# OmicHub AI界面功能优化计划

> **文档版本**：v1.0  
> **日期**：2025-06-26  
> **问题定位**：AI界面已按Kimi风格实现UI，但存在关键功能缺陷导致无法使用

---

## 一、当前问题诊断（基于截图分析）

### 截图1：当前AI聊天界面状态

```
已实现的：
✅ 深色主题 + 左侧边栏布局
✅ 底部居中输入框 + "/"提示
✅ Agent按钮、插件按钮、模型选择下拉
✅ 发送消息"hi"成功显示在用户消息区
✅ 左侧功能菜单（插件/分析流程/项目数据/深度研究/代码沙盒/Agent模式）
✅ 历史会话（今天/hi）
✅ 用户信息（root/Admin）

未实现的/有问题的：
❌ AI回复只有头像+名字"OmicHub AI"，没有实际内容
❌ 底部有白色空隙，聊天区域没有铺满视口（100vh）
❌ 流式输出效果（打字机效果）
❌ 代码块/图表/MCP结果渲染
```

### 截图2：模型配置状态

```
当前配置：
- 名称：kimi
- Provider：OpenAI兼容
- 模型：qwen3.7-max
- Base URL：https://llm-i1uekbihz77q045m.cn-beijing.maas.aliyuncs.com/co（阿里云MaaS）
- API Key：⚠️ 留空！（这是最大问题）
- Temperature：0.7
- Max Tokens：2048
- Top P：1
- Timeout：120
- 启用：开启
```

### 问题根因分析

| # | 问题 | 根因 | 严重度 |
|---|------|------|--------|
| 1 | **AI不回复** | API Key为空，后端调用LLM时认证失败 | 🔴 致命 |
| 2 | **回复内容为空** | 后端错误处理不完善，API报错时前端只显示AI名称没有错误信息 | 🔴 致命 |
| 3 | **底部白色空隙** | CSS高度计算问题，主聊天区域没有设置`height: 100vh`或`flex: 1` | 🟠 严重 |
| 4 | **模型选择不联动** | 输入框显示"K2.6快速"是写死的，没有从模型配置读取 | 🟠 严重 |
| 5 | **无错误提示** | API调用失败时前端没有展示错误信息（如"API Key未配置"） | 🟡 中等 |

---

## 二、优化计划（分4个阶段）

### 🔴 阶段一：紧急修复（1-2小时）— 让AI能用

#### 1.1 修复底部白色空隙（CSS问题）

**问题**：聊天区域没有铺满视口高度，底部有白色空隙。

**修复**：修改布局CSS，确保主聊天区域占满整个视口。

```css
/* src/views/AIAssistantView.vue 或 KimiLayout.vue */
.ai-chat-layout {
  display: flex;
  height: 100vh;           /* 关键：占满整个视口 */
  width: 100vw;
  overflow: hidden;        /* 防止整体滚动 */
  background: var(--chat-bg, #000000);
}

.chat-main-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  height: 100vh;           /* 关键 */
  overflow: hidden;
}

/* 消息列表区域 */
.message-list-container {
  flex: 1;                 /* 关键：占满剩余空间 */
  overflow-y: auto;        /* 内部滚动 */
  min-height: 0;           /* 关键：flex子元素需要 */
}

/* 输入框固定在底部 */
.chat-input-wrapper {
  flex-shrink: 0;          /* 不压缩 */
  padding: 16px 20px;
  background: var(--chat-surface, #1a1a1a);
  border-top: 1px solid var(--chat-border, #333);
}
```

```vue
<!-- 确保根元素占满 -->
<template>
  <div class="ai-chat-layout">
    <!-- 左侧边栏 -->
    <KimiSidebar class="sidebar" />
    
    <!-- 主聊天区域 -->
    <div class="chat-main-area">
      <!-- 顶部标题栏 -->
      <ChatHeader v-if="currentSession" />
      
      <!-- 消息列表 - flex:1 占满中间 -->
      <div class="message-list-container">
        <KimiEmptyState v-if="!currentSession" />
        <KimiMessageList v-else />
      </div>
      
      <!-- 底部输入框 -->
      <div class="chat-input-wrapper">
        <KimiChatInput />
      </div>
    </div>
  </div>
</template>
```

#### 1.2 修复AI不回复问题（后端API调用）

**问题根因链**：
```
用户输入"hi" 
→ 前端发送WebSocket/HTTP请求到后端
→ 后端调用LLM API
→ API Key为空 → 阿里云返回401 Unauthorized
→ 后端错误处理不完善 → 返回空内容或报错
→ 前端只渲染了"OmicHub AI"标题，没有处理错误/空内容
```

**修复方案**：

**A. 后端修复（FastAPI）**：

```python
# app/services/llm_service.py
import httpx
from fastapi import HTTPException

class LLMService:
    def __init__(self):
        self.config = self._load_active_config()
    
    def _load_active_config(self):
        """从数据库加载启用的模型配置"""
        # 查询ai_model_configs表，找到is_default=True或is_active=True的记录
        config = db.query(AIModelConfig).filter(
            AIModelConfig.is_active == True
        ).order_by(AIModelConfig.is_default.desc()).first()
        
        if not config:
            raise HTTPException(status_code=500, detail="没有可用的AI模型配置")
        
        # ⚠️ 关键检查：API Key不能为空
        if not config.api_key:
            raise HTTPException(
                status_code=500, 
                detail=f"模型 '{config.name}' 的API Key未配置，请在系统管理 > AI模型配置中设置"
            )
        
        return config
    
    async def chat(self, messages: list, stream: bool = True):
        """调用LLM API"""
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",  # 使用配置的API Key
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.config.model,           # 使用配置的模型名
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "top_p": self.config.top_p,
            "stream": stream
        }
        
        try:
            async with httpx.AsyncClient(timeout=self.config.timeout) as client:
                if stream:
                    # 流式输出
                    async with client.stream(
                        "POST", 
                        f"{self.config.base_url}/chat/completions",
                        headers=headers,
                        json=payload
                    ) as response:
                        if response.status_code == 401:
                            yield {"error": "API Key无效或已过期，请检查AI模型配置"}
                            return
                        elif response.status_code != 200:
                            body = await response.aread()
                            yield {"error": f"LLM API错误 (HTTP {response.status_code}): {body.decode()[:200]}"}
                            return
                        
                        async for line in response.aiter_lines():
                            if line.startswith("data: "):
                                data = line[6:]
                                if data == "[DONE]":
                                    break
                                # 解析SSE数据并yield
                                yield self._parse_sse_chunk(data)
                else:
                    # 非流式
                    response = await client.post(
                        f"{self.config.base_url}/chat/completions",
                        headers=headers,
                        json=payload
                    )
                    yield self._parse_response(response.json())
                    
        except httpx.TimeoutException:
            yield {"error": f"LLM API请求超时（{self.config.timeout}秒），请检查网络或增加Timeout设置"}
        except httpx.ConnectError:
            yield {"error": f"无法连接到LLM API ({self.config.base_url})，请检查Base URL是否正确"}
        except Exception as e:
            yield {"error": f"调用LLM时发生错误: {str(e)}"}
```

**B. API Key存储安全方案**：

```python
# app/models/ai_config.py
from sqlalchemy import Column, Integer, String, Float, Boolean, Text
from cryptography.fernet import Fernet
import os

# 使用环境变量或Docker Secrets作为加密密钥
ENCRYPTION_KEY = os.environ.get("AI_CONFIG_ENCRYPTION_KEY") or Fernet.generate_key()
fernet = Fernet(ENCRYPTION_KEY)

class AIModelConfig(Base):
    __tablename__ = "ai_model_configs"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)           # 显示名称（如"kimi"）
    provider = Column(String(50), nullable=False)         # openai_compatible / anthropic / azure
    model = Column(String(100), nullable=False)           # qwen3.7-max / gpt-4 / kimi-k2
    base_url = Column(Text, nullable=False)               # API端点URL
    _api_key = Column("api_key", Text, nullable=True)     # 加密存储的API Key
    temperature = Column(Float, default=0.7)
    max_tokens = Column(Integer, default=2048)
    top_p = Column(Float, default=1.0)
    timeout = Column(Integer, default=120)                # 秒
    is_active = Column(Boolean, default=True)
    is_default = Column(Boolean, default=False)           # 默认使用的模型
    created_at = Column(DateTime, default=datetime.utcnow)
    
    @property
    def api_key(self):
        """解密API Key"""
        if self._api_key:
            return fernet.decrypt(self._api_key.encode()).decode()
        return None
    
    @api_key.setter
    def api_key(self, value):
        """加密存储API Key"""
        if value:
            self._api_key = fernet.encrypt(value.encode()).decode()
        else:
            self._api_key = None
```

**C. 前端修复（错误展示）**：

```vue
<!-- KimiMessageItem.vue -->
<template>
  <div class="message-item" :class="{ 'user': isUser, 'ai': !isUser }">
    <!-- AI头像和名称 -->
    <div v-if="!isUser" class="ai-header">
      <img src="/logo.png" class="ai-avatar" />
      <span class="ai-name">OmicHub AI</span>
    </div>
    
    <!-- 消息内容 -->
    <div class="message-content">
      <!-- ❌ 当前可能只渲染了这个div但没有内容 -->
      
      <!-- ✅ 修复：支持多种内容类型 -->
      
      <!-- 1. 错误消息（红色提示） -->
      <n-alert v-if="message.type === 'error'" type="error" :bordered="false">
        <template #header>
          <n-icon><AlertCircle /></n-icon> 出错了
        </template>
        {{ message.content }}
        <n-button text type="error" size="small" @click="retry">
          重试
        </n-button>
      </n-alert>
      
      <!-- 2. 加载中状态 -->
      <div v-else-if="message.isLoading" class="typing-indicator">
        <span class="dot"></span>
        <span class="dot"></span>
        <span class="dot"></span>
      </div>
      
      <!-- 3. 正常Markdown内容 -->
      <div v-else class="markdown-body" v-html="renderedMarkdown" />
    </div>
  </div>
</template>
```

#### 1.3 修复模型选择联动

**当前问题**：输入框右下角显示"K2.6快速"是写死的字符串。

**修复方案**：

```vue
<!-- KimiChatInput.vue -->
<template>
  <div class="chat-input-container">
    <n-input
      v-model:value="inputText"
      type="textarea"
      :placeholder="'输入 \"/\" 唤起插件和技能...'"
      :autosize="{ minRows: 1, maxRows: 8 }"
      @keydown="handleKeydown"
    />
    
    <!-- 底部工具栏 -->
    <div class="input-toolbar">
      <div class="toolbar-left">
        <n-button text size="small">
          <template #icon><n-icon><AddOutline /></n-icon></template>
        </n-button>
        
        <n-button 
          :type="isAgentMode ? 'primary' : 'default'" 
          size="small"
          @click="toggleAgent"
        >
          <template #icon><n-icon><SparklesOutline /></n-icon></template>
          Agent
        </n-button>
        
        <n-button text size="small">
          <template #icon><n-icon><ExtensionOutline /></n-icon></template>
          插件
        </n-button>
      </div>
      
      <div class="toolbar-right">
        <!-- ✅ 修复：从store读取模型列表，动态显示当前模型 -->
        <n-dropdown 
          :options="modelOptions" 
          @select="handleModelChange"
          trigger="click"
        >
          <n-button text size="small">
            {{ currentModel?.name || '选择模型' }}
            <template #icon><n-icon><ChevronDownOutline /></n/icon></template>
          </n-button>
        </n-dropdown>
        
        <n-button 
          circle 
          type="primary" 
          :disabled="!inputText.trim() || isLoading"
          @click="sendMessage"
        >
          <template #icon><n-icon><SendOutline /></n/icon></template>
        </n-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useChatStore } from '@/stores/chat'
import { useModelStore } from '@/stores/model'  // ✅ 新增

const chatStore = useChatStore()
const modelStore = useModelStore()  // ✅ 管理模型配置

// ✅ 从modelStore读取当前模型
const currentModel = computed(() => modelStore.currentModel)

// ✅ 下拉选项从后端动态获取
const modelOptions = computed(() => {
  return modelStore.models.map(m => ({
    label: `${m.name} (${m.model})`,
    key: m.id,
    disabled: !m.is_active
  }))
})

const handleModelChange = (modelId: number) => {
  modelStore.switchModel(modelId)
}
</script>
```

```typescript
// stores/model.ts — 新增模型管理Store
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { useRequest } from '@/composables/useRequest'

export const useModelStore = defineStore('model', () => {
  const models = ref<ModelConfig[]>([])
  const currentModelId = ref<number | null>(null)
  const loading = ref(false)
  
  const { get } = useRequest()
  
  // 获取所有模型配置
  const fetchModels = async () => {
    loading.value = true
    try {
      const res = await get('/api/v1/ai/models')
      models.value = res.data
      
      // 自动选择默认模型
      const defaultModel = models.value.find(m => m.is_default && m.is_active)
      if (defaultModel && !currentModelId.value) {
        currentModelId.value = defaultModel.id
      }
    } finally {
      loading.value = false
    }
  }
  
  // 当前选中的模型
  const currentModel = computed(() => {
    return models.value.find(m => m.id === currentModelId.value)
  })
  
  // 切换模型
  const switchModel = (modelId: number) => {
    currentModelId.value = modelId
    // 保存到localStorage，下次打开保持选择
    localStorage.setItem('omic_selected_model', String(modelId))
  }
  
  // 初始化时恢复选择
  const init = () => {
    const saved = localStorage.getItem('omic_selected_model')
    if (saved) {
      currentModelId.value = Number(saved)
    }
    fetchModels()
  }
  
  return {
    models,
    currentModel,
    currentModelId,
    loading,
    fetchModels,
    switchModel,
    init
  }
})
```

#### 1.4 添加WebSocket流式输出

```typescript
// composables/useChatStream.ts
import { ref } from 'vue'

export function useChatStream() {
  const isLoading = ref(false)
  const isStreaming = ref(false)
  const error = ref<string | null>(null)
  
  let ws: WebSocket | null = null
  
  const connect = (sessionId: string) => {
    const token = localStorage.getItem('token')
    ws = new WebSocket(
      `wss://${window.location.host}/ws/v1/chat/${sessionId}?token=${token}`
    )
    
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data)
      
      switch (data.type) {
        case 'chat.message_chunk':
          // 追加到当前AI消息
          appendToLastMessage(data.payload.delta)
          break
        case 'chat.message_complete':
          isStreaming.value = false
          isLoading.value = false
          break
        case 'chat.error':
          error.value = data.payload.message
          isStreaming.value = false
          isLoading.value = false
          // 显示错误消息
          showErrorMessage(data.payload.message)
          break
      }
    }
    
    ws.onerror = () => {
      error.value = 'WebSocket连接失败，请刷新页面重试'
      isLoading.value = false
    }
  }
  
  const sendMessage = (content: string, modelId: number) => {
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      error.value = '连接已断开，请刷新页面'
      return
    }
    
    isLoading.value = true
    isStreaming.value = true
    error.value = null
    
    ws.send(JSON.stringify({
      type: 'chat.send_message',
      payload: {
        content,
        model_id: modelId  // ✅ 传递当前选择的模型ID
      }
    }))
  }
  
  return {
    isLoading,
    isStreaming,
    error,
    connect,
    sendMessage
  }
}
```

---

### 🟠 阶段二：功能完善（2-4小时）

#### 2.1 消息Markdown渲染

```bash
npm install markdown-it highlight.js @types/markdown-it
```

```typescript
// composables/useMarkdown.ts
import MarkdownIt from 'markdown-it'
import hljs from 'highlight.js'
import 'highlight.js/styles/github-dark.css'  // 暗黑主题代码高亮

const md = new MarkdownIt({
  html: false,        // 安全：不渲染HTML
  breaks: true,       // 换行转为<br>
  linkify: true,      // 自动链接
  highlight: (code, lang) => {
    if (lang && hljs.getLanguage(lang)) {
      return hljs.highlight(code, { language: lang }).value
    }
    return hljs.highlightAuto(code).value
  }
})

// 安全：禁用危险标签
md.disable(['image'])  // 如果需要图片可以自定义处理

export const useMarkdown = () => {
  const render = (content: string): string => {
    return md.render(content)
  }
  return { render }
}
```

#### 2.2 代码块复制功能

```vue
<!-- 代码块渲染组件 -->
<template>
  <div class="code-block">
    <div class="code-header">
      <span class="code-lang">{{ language }}</span>
      <n-button text size="tiny" @click="copyCode">
        <template #icon><n-icon><CopyOutline /></n/icon></template>
        {{ copied ? '已复制' : '复制' }}
      </n-button>
    </div>
    <pre><code v-html="highlightedCode"></code></pre>
  </div>
</template>
```

#### 2.3 打字机效果（流式输出视觉优化）

```css
/* 流式输出的光标闪烁 */
.streaming-cursor::after {
  content: '|';
  animation: blink 1s step-end infinite;
  color: var(--chat-accent);
}

@keyframes blink {
  50% { opacity: 0; }
}

/* 消息入场动画 */
@keyframes messageSlideIn {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.message-item {
  animation: messageSlideIn 0.3s ease-out;
}
```

#### 2.4 停止生成按钮

```vue
<!-- 流式输出时显示停止按钮 -->
<n-button 
  v-if="isStreaming" 
  size="small" 
  type="error" 
  ghost
  @click="stopGeneration"
>
  <template #icon><n-icon><StopOutline /></n/icon></template>
  停止生成
</n-button>
```

---

### 🟡 阶段三：联动优化（2-3小时）

#### 3.1 AI模型配置 ↔ 聊天界面完全联动

```
系统管理 > AI模型配置
├── 新增/编辑模型
│   ├── 名称（显示在dropdown中）
│   ├── Provider（OpenAI兼容/Anthropic/Azure）
│   ├── 模型ID（qwen3.7-max/gpt-4等）
│   ├── Base URL
│   ├── API Key（加密存储）
│   ├── 参数（Temperature/Max Tokens/Top P/Timeout）
│   └── 设为默认
│
└── 聊天界面
    ├── 模型下拉读取所有active模型
    ├── 显示名称 + 模型ID
    ├── 默认选中is_default的模型
    ├── 切换模型后后续对话使用新模型
    └── 如果只有1个模型，隐藏dropdown
```

#### 3.2 聊天 ↔ 代码沙盒联动

```
AI回复中的代码块
├── 点击"在沙盒中运行"按钮
├── 打开代码沙盒页面
├── 自动将代码填入编辑器
└── 自动执行并显示结果
```

#### 3.3 聊天 ↔ 分析流程联动

```
用户："帮我做一个RNA-seq分析"
AI：识别意图 → 调用 MCP workflow tool
├── 返回参数确认卡片（样本/流程/参数）
├── 用户点击"确认提交"
├── 调用POST /api/v1/tasks
└── 返回任务ID，可点击跳转到任务详情
```

#### 3.4 聊天 ↔ 项目数据联动

```
AI助手上下文
├── 自动感知当前选中的项目
├── 可以查询项目下的样本列表
├── 可以引用项目数据作为分析输入
└── 可以读取项目历史任务结果
```

---

### 🟢 阶段四：体验优化（持续）

#### 4.1 快捷提示卡片（空状态）

```vue
<!-- KimiEmptyState.vue -->
<div class="quick-prompts-grid">
  <n-card 
    v-for="prompt in quickPrompts" 
    :key="prompt.id"
    hoverable
    class="prompt-card"
    @click="selectPrompt(prompt.text)"
  >
    <div class="prompt-icon">{{ prompt.icon }}</div>
    <div class="prompt-text">{{ prompt.text }}</div>
  </n-card>
</div>

<script setup>
const quickPrompts = [
  { id: 1, icon: '🔬', text: '帮我分析RNA-seq差异表达基因' },
  { id: 2, icon: '📊', text: '绘制UMAP降维可视化图' },
  { id: 3, icon: '🧬', text: '查询GO富集分析结果' },
  { id: 4, icon: '📁', text: '列出我最近的分析任务' },
  { id: 5, icon: '💻', text: '打开代码沙盒写Python脚本' },
  { id: 6, icon: '📎', text: '使用插件搜索PubMed文献' }
]
</script>

<style scoped>
.quick-prompts-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
  max-width: 600px;
  margin: 0 auto;
}
.prompt-card {
  cursor: pointer;
  transition: all 0.2s;
}
.prompt-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0,0,0,0.15);
}
</style>
```

#### 4.2 消息反馈（👍/👎）

```vue
<div class="message-actions">
  <n-button text size="tiny" @click="feedback('up')">
    <n-icon><ThumbsUpOutline /></n-icon>
  </n-button>
  <n-button text size="tiny" @click="feedback('down')">
    <n-icon><ThumbsDownOutline /></n-icon>
  </n-button>
  <n-button text size="tiny" @click="copyMessage">
    <n-icon><CopyOutline /></n-icon>
  </n-button>
</div>
```

#### 4.3 会话管理

```
左侧历史会话
├── 今天
│   ├── hi (3条消息)
│   └── RNA-seq分析讨论 (12条消息)
├── 昨天
│   └── ATAC-seq数据质控 (8条消息)
├── 更早
│   └── 单细胞聚类参数优化 (25条消息)
```

---

## 三、后端API接口清单

### 3.1 模型配置管理（已有但需要完善）

```
GET    /api/v1/ai/models              # 获取所有模型配置（前端dropdown用）
GET    /api/v1/ai/models/{id}         # 获取单个模型配置
POST   /api/v1/ai/models              # 新增模型配置（管理员）
PUT    /api/v1/ai/models/{id}         # 更新模型配置（管理员）
DELETE /api/v1/ai/models/{id}         # 删除模型配置（管理员）
PUT    /api/v1/ai/models/{id}/default # 设为默认模型（管理员）
POST   /api/v1/ai/models/{id}/test    # 测试连接（管理员）
```

### 3.2 聊天接口（WebSocket + REST）

```
# WebSocket
WS     /ws/v1/chat/{session_id}       # 聊天WebSocket（流式输出）
  → 发送: { type: "chat.send_message", payload: { content, model_id } }
  ← 接收: { type: "chat.message_chunk", payload: { delta } }
  ← 接收: { type: "chat.message_complete" }
  ← 接收: { type: "chat.error", payload: { message } }
  ← 接收: { type: "chat.tool_call", payload: { tool_name, arguments } }

# REST（备用）
POST   /api/v1/chat/sessions          # 创建新会话
GET    /api/v1/chat/sessions          # 获取会话列表
GET    /api/v1/chat/sessions/{id}     # 获取会话详情
DELETE /api/v1/chat/sessions/{id}     # 删除会话
GET    /api/v1/chat/sessions/{id}/messages  # 获取消息历史
POST   /api/v1/chat/feedback          # 消息反馈（👍/👎）
```

---

## 四、快速验证清单

修复完成后，按以下清单验证：

| # | 验证项 | 期望结果 | 状态 |
|---|--------|----------|------|
| 1 | 打开AI助手页面 | 界面铺满全屏，无白色空隙 | ⬜ |
| 2 | 不输入任何内容 | 显示中央Logo + 快捷提示卡片 | ⬜ |
| 3 | 输入"hi"发送 | AI有实际文字回复（不是空的） | ⬜ |
| 4 | 查看AI回复内容 | 回复是合理的自然语言（非错误信息） | ⬜ |
| 5 | API Key为空时发送 | 前端显示友好错误"API Key未配置" | ⬜ |
| 6 | 模型选择下拉 | 显示配置的所有模型名称 | ⬜ |
| 7 | 切换模型 | 后续对话使用新模型 | ⬜ |
| 8 | AI回复包含代码 | 代码块有语法高亮 + 复制按钮 | ⬜ |
| 9 | 长消息测试 | 虚拟滚动正常工作 | ⬜ |
| 10 | 连续对话 | 上下文连贯，AI记得之前的内容 | ⬜ |
| 11 | 停止生成按钮 | 流式输出时可点击停止 | ⬜ |
| 12 | 新建会话(⌘+K) | 清空当前对话，开始新会话 | ⬜ |
| 13 | 历史会话显示 | 左侧显示历史会话列表 | ⬜ |
| 14 | 暗黑/浅色切换 | 主题正常切换 | ⬜ |

---

## 五、紧急修复优先级（今天必须完成）

| 优先级 | 修复项 | 预估时间 | 影响 |
|--------|--------|----------|------|
| **P0** | 填充API Key（后端或配置） | 10分钟 | AI能用 |
| **P0** | 修复底部白色空隙（CSS） | 15分钟 | 界面美观 |
| **P0** | 添加错误处理和展示 | 30分钟 | 知道为什么失败 |
| **P0** | 修复模型选择联动 | 30分钟 | 选择正确的模型 |
| **P1** | Markdown渲染 + 代码高亮 | 1小时 | 可读性 |
| **P1** | WebSocket流式输出 | 1小时 | 实时体验 |
| **P2** | 打字机效果 | 30分钟 | 视觉体验 |
| **P2** | 快捷提示卡片 | 30分钟 | 引导用户 |
