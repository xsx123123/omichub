# OmicHub AI 聊天窗口 Kimi 风格改造方案

> 文档版本：v1.0 | 作者：前端 UI/UX 设计团队 | 日期：2025-01-15

---

## 目录

1. [设计方案文档](#1-设计方案文档)
   - 1.1 [布局对比分析](#11-布局对比分析)
   - 1.2 [新布局设计](#12-新布局设计)
2. [第三方包推荐](#2-第三方包推荐)
3. [完整的 Vue3 组件代码](#3-完整的-vue3-组件代码)
   - 3.1 [KimiLayout.vue](#31-kimilayoutvue)
   - 3.2 [KimiChatInput.vue](#32-kimichatinputvue)
   - 3.3 [KimiEmptyState.vue](#33-kimiemptystatevue)
   - 3.4 [KimiMessageList.vue](#34-kimimessagelistvue)
   - 3.5 [KimiMessageItem.vue](#35-kimimessageitemvue)
   - 3.6 [KimiSidebar.vue](#36-kimisidebarvue)
   - 3.7 [SlashCommandMenu.vue](#37-slashcommandmenuvue)
4. [样式设计 CSS/CSS 变量](#4-样式设计-csscss-变量)
5. [动画设计](#5-动画设计)
6. [Pinia Store 更新](#6-pinia-store-更新)
7. [改造步骤迁移计划](#7-改造步骤迁移计划)

---

## 1. 设计方案文档

### 1.1 布局对比分析

#### 当前 OmicHub AI 助手界面问题诊断

| 维度 | 当前设计 | Kimi 目标风格 | 问题严重程度 |
|------|----------|--------------|-------------|
| **主题色** | 浅色主题（白/灰） | 深色沉浸式（纯黑） | 高 |
| **背景** | 浅灰 #f5f5f5 | 纯黑 #000000 | 高 |
| **左侧边栏** | 系统导航（分析中心/数据管理等） | 聊天专用（新建会话/功能菜单/历史会话） | 高 |
| **对话列表面板** | 窄面板，仅显示"新对话"x2，内容空洞 | 集成在左侧边栏，带历史会话预览 | 中 |
| **主区域空状态** | 大面积空白，只有顶部输入框 | 中央大 Logo + 底部居中输入框 + 快捷卡片 | 高 |
| **输入框位置** | 顶部（不符合现代 AI 习惯） | 底部居中（符合 ChatGPT/Kimi/Claude 习惯） | 高 |
| **品牌展示** | 仅左上角小 Logo | 中央大字 Logo（KIMI 风格） | 中 |
| **快捷入口** | 无 | 2x3 网格快捷提示卡片 | 中 |
| **输入框样式** | 细长单行输入 | 大圆角文本域，自适应高度 | 高 |
| **底部工具栏** | 无 | +附件/Agent/模型选择/发送按钮 | 高 |
| **Slash 命令** | 无 | 输入"/"唤起快捷菜单 | 中 |
| **消息展示** | 传统对话模式 | 用户气泡右对齐 + AI 卡片左对齐全宽 | 高 |
| **AI 消息内部** | 纯文本 | Markdown + 代码高亮 + 图表 + 思考过程 | 高 |
| **用户头像区** | 左下角简单头像+名字 | 左下角头像+名字+等级标签 | 低 |
| **动画效果** | 无 | Logo 呼吸/消息滑入/输入框展开 | 中 |

#### 详细问题分析

**问题 1：空间利用率极低**
当前界面左侧有一个独立的"对话"列表面板，宽度约 200px，但只显示了两个"新对话"条目，大量空间被浪费。右侧主区域（约 70% 宽度）完全空白，只有一个输入框在顶部。这种布局让用户感觉"没什么内容"。

**问题 2：不符合 AI 产品交互习惯**
现代 AI 聊天产品（ChatGPT、Claude、Kimi、文心一言）的输入框都在底部，因为：
- 对话内容自然从上到下流式展示
- 底部输入更符合"对话"的心理模型
- 用户视线从消息内容自然下移到底部输入

当前 Omichub 的输入框在顶部，用户在输入后需要向上看才能看到回复，违反自然阅读流。

**问题 3：缺乏品牌沉浸感**
Kimi 的纯黑背景+中央大 Logo 设计创造了强烈的品牌认知和沉浸感。用户一进入页面就知道"这是 Kimi"。当前 Omichub 的浅色界面缺乏这种品牌冲击力。

**问题 4：功能入口分散**
当前没有统一的功能入口，插件、Agent、模型选择等功能缺乏直观的操作界面。

---

### 1.2 新布局设计

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  OmicHub 顶部导航栏（保持原有）                                               │
├──────────────┬──────────────────────────────────────────────────────────────┤
│              │                                                              │
│  ┌────────┐  │                    【空状态】                                │
│  │+ 新建会话│  │                                                              │
│  │  ⌘K    │  │              ┌─────────────────────────┐                     │
│  └────────┘  │              │                         │                     │
│              │              │      OMIC HUB           │   ← 大Logo           │
│  ──────────  │              │                         │                     │
│   功能菜单    │              └─────────────────────────┘                     │
│              │                                                              │
│  📎 插件      │        ┌─────────────────────────────────────┐               │
│  📊 分析流程  │        │ 🔬 帮我分析RNA-seq差异表达基因       │               │
│  📁 项目数据  │        │ 📊 绘制UMAP降维可视化图              │  ← 快捷卡片    │
│  🔬 深度研究  │        │ 🧬 查询GO富集分析结果               │    2x3网格     │
│  💻 代码沙盒  │        │ 📁 列出我最近的分析任务              │               │
│  🤖 Agent模式│        │ 💻 打开代码沙盒写Python              │               │
│              │        │ 📎 使用插件搜索PubMed文献            │               │
│  ──────────  │        └─────────────────────────────────────┘               │
│   历史会话    │                                                              │
│              │  ┌───────────────────────────────────────────────────────┐   │
│  📂 今天      │  │  输入 "/" 唤起插件和技能...                            │   │
│   会话1      │  │                                                       │   │
│   会话2      │  │  [+]  [🤖 Agent]  [📎 插件]  [模型 ▼]           [→]  │   │ ←输入框
│              │  └───────────────────────────────────────────────────────┘   │
│  📂 昨天      │                                                              │
│   会话3      │                                                              │
│              │                                                              │
│  📂 更早      │                                                              │
│              │                                                              │
│  ──────────  │                                                              │
│  👤 root     │                                                              │
│  🏷️ 管理员   │                                                              │
│              │                                                              │
└──────────────┴──────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│  OmicHub 顶部导航栏（保持原有）                                               │
├──────────────┬──────────────────────────────────────────────────────────────┤
│              │  会话标题（可编辑）                    [分享] [设置]          │
│  左侧边栏    ├──────────────────────────────────────────────────────────────┤
│  （同上）    │                                                              │
│              │  ┌───────────────────────────────────────────────────────┐   │
│              │  │ 👤 用户消息内容                                        │   │
│              │  │                                                        │   │
│              │  └───────────────────────────────────────────────────────┘   │
│              │                                                              │
│              │  🤖 AI头像  AI消息卡片                                      │
│              │  ┌───────────────────────────────────────────────────────┐   │
│              │  │  思考过程...（可折叠）                                  │   │
│              │  │  ┌──────────────┐                                      │   │
│              │  │  │  ```python    │  [📋复制]                            │   │
│              │  │  │  print("hi")  │                                      │   │
│              │  │  │  ```          │                                      │   │
│              │  │  └──────────────┘                                      │   │
│              │  │  ┌─────────────────────────────────────┐               │   │
│              │  │  │ 📊 图表渲染区域（ECharts）            │               │   │
│              │  │  └─────────────────────────────────────┘               │   │
│              │  │  [👍] [👎]                                             │   │
│              │  └───────────────────────────────────────────────────────┘   │
│              │                                                              │
│              │  ┌───────────────────────────────────────────────────────┐   │
│              │  │  输入 "/" 唤起插件和技能...                            │   │
│              │  │                                                       │   │
│              │  │  [+]  [🤖 Agent]  [📎 插件]  [模型 ▼]           [→]  │   │
│              │  └───────────────────────────────────────────────────────┘   │
│              │                                                              │
└──────────────┴──────────────────────────────────────────────────────────────┘
```

---

## 2. 第三方包推荐

| 功能 | 推荐包名 | 版本 | 用途 | 安装命令 |
|------|----------|------|------|----------|
| Markdown 渲染 | `markdown-it` | ^14.0.0 | AI 消息支持 Markdown 语法 | `npm i markdown-it @types/markdown-it` |
| Markdown Vue 组件 | `vue-markdown-render` | ^2.2.1 | Vue 组件形式使用 markdown-it | `npm i vue-markdown-render` |
| 代码高亮 | `highlight.js` | ^11.9.0 | 代码块语法高亮，支持 180+ 语言 | `npm i highlight.js` |
| 代码复制 | `vue3-copy-to-clipboard` | ^1.0.2 | 代码块一键复制功能 | `npm i vue3-copy-to-clipboard` |
| 自动调整高度 | `@vueuse/core` | ^10.7.0 | useTextareaAutosize 输入框自适应 | `npm i @vueuse/core` |
| 快捷键 | `@vueuse/core` | ^10.7.0 | useMagicKeys 支持 ⌘+K 等快捷键 | `npm i @vueuse/core` |
| 动画 | `@vueuse/motion` | ^2.2.0 | 消息入场动画、Logo 动画 | `npm i @vueuse/motion` |
| 虚拟滚动 | `vue-virtual-scroller` | ^2.0.0-beta.8 | 长消息列表虚拟滚动优化 | `npm i vue-virtual-scroller@next` |
| 图标库 | `@vicons/ionicons5` | ^0.12.0 | 功能菜单图标（close/add/chevron） | `npm i @vicons/ionicons5` |
| 图标库扩展 | `@vicons/carbon` | ^0.12.0 | 更多专业图标（code/send/analytics） | `npm i @vicons/carbon` |
| Naive UI 内置 | `naive-ui` | ^2.37.0 | 主题、按钮、下拉菜单、对话框等 | （已有） |
| 日期处理 | `date-fns` | ^3.0.0 | 历史会话日期分组（今天/昨天/更早） | `npm i date-fns` |
| 图表渲染 | `echarts` | ^5.4.0 | AI 消息中的图表内联渲染 | `npm i echarts vue-echarts` |

### 依赖安装命令汇总

```bash
# 核心依赖
npm i markdown-it @types/markdown-it highlight.js vue3-copy-to-clipboard

# VueUse 全家桶
npm i @vueuse/core @vueuse/motion

# 虚拟滚动
npm i vue-virtual-scroller@next

# 图标库
npm i @vicons/ionicons5 @vicons/carbon

# 工具库
npm i date-fns echarts vue-echarts
```

### 在 main.ts 中注册

```typescript
import { createApp } from 'vue'
import App from './App.vue'
import naive from 'naive-ui'
import 'highlight.js/styles/github-dark.css'  // 代码高亮主题
import 'vue-virtual-scroller/dist/vue-virtual-scroller.css'  // 虚拟滚动样式

const app = createApp(App)
app.use(naive)
app.mount('#app')
```

---

## 3. 完整的 Vue3 组件代码

### 3.1 KimiLayout.vue — 新布局框架

```vue
<template>
  <div class="kimi-layout" :data-theme="theme">
    <!-- 左侧边栏 -->
    <KimiSidebar
      :sessions="sessions"
      :current-session-id="currentSessionId"
      :user-info="userInfo"
      :collapsed="sidebarCollapsed"
      @new-session="handleNewSession"
      @select-session="handleSelectSession"
      @delete-session="handleDeleteSession"
      @toggle-collapse="sidebarCollapsed = !sidebarCollapsed"
      @navigate="handleNavigate"
    />

    <!-- 主聊天区域 -->
    <main class="kimi-main" :class="{ 'sidebar-collapsed': sidebarCollapsed }">
      <!-- 空状态 -->
      <KimiEmptyState
        v-if="!currentSession || currentSession.messages.length === 0"
        :logo-text="'OMIC HUB'"
        :quick-prompts="quickPrompts"
        @send-prompt="handleSendPrompt"
        @upload-file="handleUploadFile"
      />

      <!-- 对话状态 -->
      <template v-else>
        <!-- 会话头部 -->
        <div class="session-header">
          <n-input
            v-model:value="currentSession.title"
            class="session-title-input"
            placeholder="会话标题"
            @blur="handleUpdateTitle"
          >
            <template #prefix>
              <n-icon><EditOutline /></n-icon>
            </template>
          </n-input>
          <div class="session-actions">
            <n-button text class="action-btn" @click="handleShare">
              <template #icon>
                <n-icon><ShareOutline /></n-icon>
              </template>
              分享
            </n-button>
            <n-button text class="action-btn" @click="showSettings = true">
              <template #icon>
                <n-icon><SettingsOutline /></n-icon>
              </template>
              设置
            </n-button>
          </div>
        </div>

        <!-- 消息列表 -->
        <KimiMessageList
          :messages="currentSession.messages"
          :is-typing="isTyping"
          :streaming-content="streamingContent"
          :streaming-thought="streamingThought"
          @feedback="handleFeedback"
          @copy-message="handleCopyMessage"
          @retry="handleRetry"
        />

        <!-- 底部输入框区域 -->
        <div class="input-area-wrapper">
          <KimiChatInput
            v-model="inputMessage"
            :placeholder="'输入 \"/\" 唤起插件和技能...'"
            :agent-mode="agentMode"
            :selected-model="selectedModel"
            :models="availableModels"
            :plugins="availablePlugins"
            :disabled="isTyping"
            @send="handleSend"
            @toggle-agent="agentMode = !agentMode"
            @select-model="handleSelectModel"
            @select-plugin="handleSelectPlugin"
            @upload-file="handleUploadFile"
          />
        </div>
      </template>
    </main>

    <!-- 设置弹窗 -->
    <n-modal v-model:show="showSettings" title="会话设置" preset="card" class="settings-modal">
      <SessionSettings :session="currentSession" />
    </n-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useMagicKeys, whenever } from '@vueuse/core'
import { NButton, NIcon, NInput, NModal, useMessage } from 'naive-ui'
import {
  ShareOutline,
  SettingsOutline,
  EditOutline
} from '@vicons/ionicons5'
import KimiSidebar from './KimiSidebar.vue'
import KimiEmptyState from './KimiEmptyState.vue'
import KimiMessageList from './KimiMessageList.vue'
import KimiChatInput from './KimiChatInput.vue'
import SessionSettings from './SessionSettings.vue'
import type { ChatSession, ChatMessage, UserInfo, QuickPrompt, ModelOption, PluginOption } from './types'

// ===== Props =====
interface Props {
  theme?: 'dark' | 'light'
}
const props = withDefaults(defineProps<Props>(), {
  theme: 'dark'
})

// ===== Emits =====
const emit = defineEmits<{
  send: [content: string, options: SendOptions]
  newSession: []
  selectSession: [sessionId: string]
  deleteSession: [sessionId: string]
  updateTitle: [sessionId: string, title: string]
  share: [sessionId: string]
  navigate: [path: string]
}>()

interface SendOptions {
  agentMode: boolean
  model: string
  plugins: string[]
  attachments?: File[]
}

// ===== State =====
const theme = ref(props.theme)
const sidebarCollapsed = ref(false)
const inputMessage = ref('')
const agentMode = ref(false)
const selectedModel = ref('kimi-k2')
const isTyping = ref(false)
const streamingContent = ref('')
const streamingThought = ref('')
const showSettings = ref(false)
const message = useMessage()

// ===== 快捷键 =====
const { Meta_K, Ctrl_K, Escape } = useMagicKeys()

// ⌘+K / Ctrl+K 新建会话
whenever(Meta_K, () => {
  handleNewSession()
})
whenever(Ctrl_K, () => {
  handleNewSession()
})

// ===== Mock 数据（实际从 Pinia Store 获取）=====
const userInfo = ref<UserInfo>({
  id: '1',
  name: 'root',
  avatar: '',
  role: '管理员',
  roleTag: 'Admin'
})

const sessions = ref<ChatSession[]>([
  {
    id: '1',
    title: 'RNA-seq 差异表达分析',
    messages: [],
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
    model: 'kimi-k2'
  },
  {
    id: '2',
    title: 'GO 富集分析结果解读',
    messages: [],
    createdAt: new Date(Date.now() - 86400000).toISOString(),
    updatedAt: new Date(Date.now() - 86400000).toISOString(),
    model: 'qwen-plus'
  }
])

const currentSessionId = ref<string>('')

const currentSession = computed<ChatSession | undefined>(() => {
  return sessions.value.find(s => s.id === currentSessionId.value)
})

const availableModels = ref<ModelOption[]>([
  { id: 'kimi-k2', name: 'K2.6 快速', description: 'Kimi 最新模型', provider: 'kimi' },
  { id: 'qwen-plus', name: 'Qwen3 Plus', description: '通义千强模型', provider: 'aliyun' },
  { id: 'qwen-max', name: 'Qwen3 Max', description: '通义千问最强', provider: 'aliyun' },
  { id: 'deepseek-chat', name: 'DeepSeek-V3', description: '深度求索', provider: 'deepseek' },
  { id: 'gpt-4o', name: 'GPT-4o', description: 'OpenAI', provider: 'openai' }
])

const availablePlugins = ref<PluginOption[]>([
  { id: 'pubmed', name: 'PubMed 搜索', description: '搜索生物医学文献', icon: '🔬' },
  { id: 'kegg', name: 'KEGG 通路', description: '查询通路信息', icon: '🧬' },
  { id: 'go', name: 'GO 富集', description: '基因功能富集分析', icon: '📊' },
  { id: 'code', name: '代码执行', description: '执行 Python/R 代码', icon: '💻' },
  { id: 'chart', name: '图表生成', description: '生成数据可视化图表', icon: '📈' }
])

const quickPrompts = ref<QuickPrompt[]>([
  { icon: '🔬', text: '帮我分析 RNA-seq 差异表达基因', category: 'analysis' },
  { icon: '📊', text: '绘制 UMAP 降维可视化图', category: 'visualization' },
  { icon: '🧬', text: '查询 GO 富集分析结果', category: 'analysis' },
  { icon: '📁', text: '列出我最近的分析任务', category: 'task' },
  { icon: '💻', text: '打开代码沙盒写 Python', category: 'code' },
  { icon: '📎', text: '使用插件搜索 PubMed 文献', category: 'search' }
])

// ===== Methods =====
function handleNewSession() {
  const newSession: ChatSession = {
    id: Date.now().toString(),
    title: '新对话',
    messages: [],
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
    model: selectedModel.value
  }
  sessions.value.unshift(newSession)
  currentSessionId.value = newSession.id
  emit('newSession')
}

function handleSelectSession(sessionId: string) {
  currentSessionId.value = sessionId
  emit('selectSession', sessionId)
}

function handleDeleteSession(sessionId: string) {
  const idx = sessions.value.findIndex(s => s.id === sessionId)
  if (idx > -1) {
    sessions.value.splice(idx, 1)
    if (currentSessionId.value === sessionId) {
      currentSessionId.value = sessions.value[0]?.id || ''
    }
  }
  emit('deleteSession', sessionId)
}

function handleSendPrompt(prompt: string) {
  if (!currentSession.value) {
    handleNewSession()
  }
  handleSend(prompt, { agentMode: agentMode.value, model: selectedModel.value, plugins: [] })
}

function handleSend(content: string, options: SendOptions) {
  if (!content.trim() || isTyping.value) return

  // 添加用户消息
  const userMessage: ChatMessage = {
    id: Date.now().toString(),
    role: 'user',
    content,
    createdAt: new Date().toISOString()
  }

  if (currentSession.value) {
    currentSession.value.messages.push(userMessage)
    currentSession.value.updatedAt = new Date().toISOString()
  }

  // 清空输入
  inputMessage.value = ''

  // 触发发送事件
  emit('send', content, options)

  // 模拟 AI 回复（实际应通过 SSE/WebSocket）
  simulateAIResponse()
}

function simulateAIResponse() {
  isTyping.value = true
  streamingContent.value = ''
  streamingThought.value = ''

  const fullContent = '这是一个模拟的 AI 回复。在实际实现中，这里会通过 SSE 或 WebSocket 接收流式响应内容。\n\n```python\n# 示例代码\nimport pandas as pd\nimport numpy as np\n\ndf = pd.read_csv("expression.csv")\nprint(df.head())\n```\n\n我可以帮您：\n1. 分析 RNA-seq 数据\n2. 绘制可视化图表\n3. 执行 GO/KEGG 富集分析\n4. 搜索 PubMed 文献'

  let index = 0
  const interval = setInterval(() => {
    if (index < fullContent.length) {
      streamingContent.value += fullContent[index]
      index++
    } else {
      clearInterval(interval)
      isTyping.value = false

      // 添加完整 AI 消息
      const aiMessage: ChatMessage = {
        id: Date.now().toString(),
        role: 'assistant',
        content: streamingContent.value,
        thought: streamingThought.value || undefined,
        createdAt: new Date().toISOString()
      }

      if (currentSession.value) {
        currentSession.value.messages.push(aiMessage)
      }

      streamingContent.value = ''
      streamingThought.value = ''
    }
  }, 30)
}

function handleSelectModel(modelId: string) {
  selectedModel.value = modelId
  if (currentSession.value) {
    currentSession.value.model = modelId
  }
}

function handleSelectPlugin(pluginId: string) {
  message.info(`已选择插件: ${pluginId}`)
}

function handleUploadFile(file: File) {
  message.info(`上传文件: ${file.name}`)
}

function handleUpdateTitle() {
  if (currentSession.value) {
    emit('updateTitle', currentSession.value.id, currentSession.value.title)
  }
}

function handleShare() {
  if (currentSession.value) {
    emit('share', currentSession.value.id)
  }
}

function handleNavigate(path: string) {
  emit('navigate', path)
}

function handleFeedback(messageId: string, type: 'like' | 'dislike') {
  message.success(type === 'like' ? '感谢您的反馈！' : '我们会继续改进')
}

function handleCopyMessage(content: string) {
  navigator.clipboard.writeText(content)
  message.success('已复制到剪贴板')
}

function handleRetry(messageId: string) {
  message.info('重新生成中...')
}

// ===== Lifecycle =====
onMounted(() => {
  // 默认选中第一个会话或新建
  if (sessions.value.length > 0 && !currentSessionId.value) {
    currentSessionId.value = sessions.value[0].id
  }
})
</script>

<style scoped lang="scss">
.kimi-layout {
  display: flex;
  width: 100vw;
  height: 100vh;
  background: var(--chat-bg);
  color: var(--chat-text-primary);
  overflow: hidden;

  .kimi-main {
    flex: 1;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    transition: margin-left 0.3s ease;

    &.sidebar-collapsed {
      // 侧边栏折叠时的样式
    }
  }

  .session-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 24px;
    border-bottom: 1px solid var(--chat-border);
    background: var(--chat-surface);

    .session-title-input {
      max-width: 400px;
      background: transparent;

      :deep(.n-input__input-el) {
        color: var(--chat-text-primary);
        font-size: 16px;
        font-weight: 500;
      }
    }

    .session-actions {
      display: flex;
      gap: 8px;

      .action-btn {
        color: var(--chat-text-secondary);

        &:hover {
          color: var(--chat-text-primary);
        }
      }
    }
  }

  .input-area-wrapper {
    padding: 16px 24px 24px;
    background: linear-gradient(to top, var(--chat-bg) 80%, transparent);
  }
}
</style>
```

### 3.2 KimiChatInput.vue — 底部输入框（核心组件）

```vue
<template>
  <div class="kimi-chat-input" :class="{ focused: isFocused, disabled }">
    <!-- 文本域 -->
    <div class="input-wrapper">
      <textarea
        ref="textareaRef"
        v-model="localValue"
        class="chat-textarea"
        :placeholder="placeholder"
        :disabled="disabled"
        rows="1"
        @focus="isFocused = true"
        @blur="handleBlur"
        @keydown="handleKeydown"
        @input="handleInput"
      />
    </div>

    <!-- Slash 命令菜单 -->
    <SlashCommandMenu
      v-if="showSlashMenu"
      :query="slashQuery"
      :position="slashMenuPosition"
      @select="handleSlashSelect"
      @close="showSlashMenu = false"
    />

    <!-- 底部工具栏 -->
    <div class="input-toolbar">
      <!-- 左侧工具 -->
      <div class="toolbar-left">
        <!-- 附件上传按钮 -->
        <n-tooltip trigger="hover">
          <template #trigger>
            <n-button text class="toolbar-btn" @click="triggerFileUpload">
              <template #icon>
                <n-icon size="18"><AddOutline /></n-icon>
              </template>
            </n-button>
          </template>
          上传文件
        </n-tooltip>
        <input
          ref="fileInputRef"
          type="file"
          multiple
          style="display: none"
          @change="handleFileChange"
        />

        <!-- Agent 模式开关 -->
        <n-tooltip trigger="hover">
          <template #trigger>
            <n-button
              text
              class="toolbar-btn agent-btn"
              :class="{ active: agentMode }"
              @click="$emit('toggleAgent')"
            >
              <template #icon>
                <n-icon size="16"><BotOutline /></n-icon>
              </template>
              <span class="btn-label">Agent</span>
            </n-button>
          </template>
          {{ agentMode ? '关闭' : '开启' }} Agent 模式
        </n-tooltip>

        <!-- 插件选择 -->
        <n-dropdown
          :options="pluginOptions"
          trigger="click"
          @select="handlePluginSelect"
        >
          <n-tooltip trigger="hover">
            <template #trigger>
              <n-button text class="toolbar-btn">
                <template #icon>
                  <n-icon size="16"><ExtensionPuzzleOutline /></n-icon>
                </template>
                <span class="btn-label">插件</span>
              </n-button>
            </template>
            选择插件
          </n-tooltip>
        </n-dropdown>
      </div>

      <!-- 右侧工具 -->
      <div class="toolbar-right">
        <!-- 模型选择 -->
        <n-dropdown
          :options="modelDropdownOptions"
          trigger="click"
          @select="handleModelSelect"
        >
          <n-button text class="toolbar-btn model-btn">
            <span class="model-name">{{ selectedModelName }}</span>
            <n-icon size="14"><ChevronDownOutline /></n-icon>
          </n-button>
        </n-dropdown>

        <!-- 发送按钮 -->
        <n-button
          circle
          class="send-btn"
          :class="{ active: canSend }"
          :disabled="!canSend || disabled"
          @click="handleSend"
        >
          <template #icon>
            <n-icon size="18"><ArrowUpOutline /></n-icon>
          </template>
        </n-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue'
import { useTextareaAutosize } from '@vueuse/core'
import { NButton, NIcon, NTooltip, NDropdown } from 'naive-ui'
import {
  AddOutline,
  ArrowUpOutline,
  ChevronDownOutline,
  ExtensionPuzzleOutline
} from '@vicons/ionicons5'
import { BotOutline } from '@vicons/carbon'
import SlashCommandMenu from './SlashCommandMenu.vue'
import type { ModelOption, PluginOption } from './types'

// ===== Props =====
interface Props {
  modelValue: string
  placeholder?: string
  agentMode?: boolean
  selectedModel?: string
  models?: ModelOption[]
  plugins?: PluginOption[]
  disabled?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  modelValue: '',
  placeholder: '输入 "/" 唤起插件和技能...',
  agentMode: false,
  selectedModel: 'kimi-k2',
  models: () => [],
  plugins: () => [],
  disabled: false
})

// ===== Emits =====
const emit = defineEmits<{
  'update:modelValue': [value: string]
  send: [content: string]
  toggleAgent: []
  selectModel: [modelId: string]
  selectPlugin: [pluginId: string]
  uploadFile: [file: File]
}>()

// ===== Refs =====
const textareaRef = ref<HTMLTextAreaElement>()
const fileInputRef = ref<HTMLInputElement>()
const isFocused = ref(false)
const showSlashMenu = ref(false)
const slashQuery = ref('')
const slashMenuPosition = ref({ top: 0, left: 0 })

// ===== 自动调整高度 =====
const { textarea, input: localValue } = useTextareaAutosize({
  element: textareaRef,
  styleProp: 'minHeight',
  styleTarget: textareaRef,
  input: () => props.modelValue
})

// 同步 v-model
watch(localValue, (val) => {
  emit('update:modelValue', val)
})

watch(() => props.modelValue, (val) => {
  if (val !== localValue.value) {
    localValue.value = val
  }
})

// ===== Computed =====
const canSend = computed(() => localValue.value.trim().length > 0)

const selectedModelName = computed(() => {
  const model = props.models.find(m => m.id === props.selectedModel)
  return model?.name || '选择模型'
})

const modelDropdownOptions = computed(() => {
  return props.models.map(m => ({
    key: m.id,
    label: `${m.name} - ${m.description}`,
    disabled: m.id === props.selectedModel
  }))
})

const pluginOptions = computed(() => {
  return props.plugins.map(p => ({
    key: p.id,
    label: `${p.icon} ${p.name} - ${p.description}`
  }))
})

// ===== Methods =====
function handleKeydown(e: KeyboardEvent) {
  // Enter 发送（不按住 Shift）
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    if (canSend.value && !props.disabled) {
      handleSend()
    }
  }

  // Shift+Enter 换行（默认行为）
  if (e.key === 'Enter' && e.shiftKey) {
    // 允许默认换行行为
  }

  // Escape 关闭 Slash 菜单
  if (e.key === 'Escape') {
    showSlashMenu.value = false
  }

  // 监听 "/" 键唤起菜单
  if (e.key === '/' && localValue.value === '') {
    nextTick(() => {
      showSlashMenu.value = true
      slashQuery.value = ''
      updateSlashMenuPosition()
    })
  }
}

function handleInput() {
  // 检测 Slash 命令
  const text = localValue.value
  const lastLine = text.split('\n').pop() || ''

  if (lastLine.startsWith('/')) {
    showSlashMenu.value = true
    slashQuery.value = lastLine.slice(1)
    updateSlashMenuPosition()
  } else {
    showSlashMenu.value = false
  }
}

function updateSlashMenuPosition() {
  if (!textareaRef.value) return
  const rect = textareaRef.value.getBoundingClientRect()
  slashMenuPosition.value = {
    top: rect.top - 220,
    left: rect.left + 20
  }
}

function handleSlashSelect(command: string) {
  const text = localValue.value
  const lines = text.split('\n')
  lines[lines.length - 1] = command + ' '
  localValue.value = lines.join('\n')
  showSlashMenu.value = false
  nextTick(() => textareaRef.value?.focus())
}

function handleSend() {
  const content = localValue.value.trim()
  if (!content || props.disabled) return
  emit('send', content)
  localValue.value = ''
  nextTick(() => {
    if (textareaRef.value) {
      textareaRef.value.style.height = 'auto'
    }
  })
}

function handleBlur() {
  // 延迟关闭，避免点击菜单时先触发 blur
  setTimeout(() => {
    isFocused.value = false
    showSlashMenu.value = false
  }, 200)
}

function triggerFileUpload() {
  fileInputRef.value?.click()
}

function handleFileChange(e: Event) {
  const target = e.target as HTMLInputElement
  const files = target.files
  if (files && files.length > 0) {
    emit('uploadFile', files[0])
    target.value = '' // 重置
  }
}

function handleModelSelect(modelId: string) {
  emit('selectModel', modelId)
}

function handlePluginSelect(pluginId: string) {
  emit('selectPlugin', pluginId)
}
</script>

<style scoped lang="scss">
.kimi-chat-input {
  background: var(--chat-input-bg);
  border: 1px solid var(--chat-input-border);
  border-radius: 20px;
  padding: 12px 16px;
  transition: all 0.3s ease;

  &.focused {
    border-color: var(--chat-accent);
    box-shadow: 0 0 0 2px rgba(79, 142, 247, 0.15);
  }

  &.disabled {
    opacity: 0.6;
    pointer-events: none;
  }

  .input-wrapper {
    margin-bottom: 8px;
  }

  .chat-textarea {
    width: 100%;
    min-height: 24px;
    max-height: 200px;
    background: transparent;
    border: none;
    outline: none;
    color: var(--chat-text-primary);
    font-size: 15px;
    line-height: 1.6;
    resize: none;
    font-family: inherit;

    &::placeholder {
      color: var(--chat-text-muted);
    }

    &::-webkit-scrollbar {
      width: 4px;
    }

    &::-webkit-scrollbar-thumb {
      background: var(--chat-border);
      border-radius: 2px;
    }
  }

  .input-toolbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    border-top: 1px solid var(--chat-border);
    padding-top: 8px;

    .toolbar-left,
    .toolbar-right {
      display: flex;
      align-items: center;
      gap: 4px;
    }

    .toolbar-btn {
      color: var(--chat-text-secondary);
      padding: 4px 8px;
      border-radius: 8px;
      transition: all 0.2s ease;

      &:hover {
        color: var(--chat-text-primary);
        background: var(--chat-surface-hover);
      }

      &.agent-btn.active {
        color: var(--chat-accent);
        background: rgba(79, 142, 247, 0.1);
      }

      .btn-label {
        margin-left: 4px;
        font-size: 13px;
      }

      &.model-btn {
        .model-name {
          margin-right: 4px;
          font-size: 13px;
        }
      }
    }

    .send-btn {
      width: 32px;
      height: 32px;
      color: var(--chat-text-muted);
      background: var(--chat-surface);
      transition: all 0.2s ease;

      &:hover,
      &.active {
        color: #fff;
        background: var(--chat-accent);
      }

      &:disabled {
        opacity: 0.4;
      }
    }
  }
}
</style>
```

### 3.3 KimiEmptyState.vue — 空状态页面

```vue
<template>
  <div class="kimi-empty-state">
    <!-- 中央内容区 -->
    <div class="empty-content" v-motion="logoMotion">
      <!-- Logo -->
      <div class="logo-container">
        <h1 class="main-logo">{{ logoText }}</h1>
        <div class="logo-subtitle">AI 智能助手</div>
      </div>

      <!-- 快捷提示卡片 -->
      <div class="quick-prompts">
        <div
          v-for="(prompt, index) in quickPrompts"
          :key="index"
          v-motion="cardMotion(index)"
          class="prompt-card"
          @click="handlePromptClick(prompt)"
        >
          <span class="prompt-icon">{{ prompt.icon }}</span>
          <span class="prompt-text">{{ prompt.text }}</span>
        </div>
      </div>
    </div>

    <!-- 底部输入框 -->
    <div v-motion="inputMotion" class="empty-input-wrapper">
      <KimiChatInput
        v-model="inputValue"
        :placeholder="'输入 \"/\" 唤起插件和技能...'"
        @send="handleSend"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useMotion } from '@vueuse/motion'
import KimiChatInput from './KimiChatInput.vue'
import type { QuickPrompt } from './types'

// ===== Props =====
interface Props {
  logoText?: string
  quickPrompts?: QuickPrompt[]
}

const props = withDefaults(defineProps<Props>(), {
  logoText: 'OMIC HUB',
  quickPrompts: () => []
})

// ===== Emits =====
const emit = defineEmits<{
  sendPrompt: [prompt: string]
  uploadFile: [file: File]
}>()

// ===== State =====
const inputValue = ref('')

// ===== Motion 动画配置 =====
const logoMotion = {
  initial: { opacity: 0, y: 30, scale: 0.95 },
  enter: {
    opacity: 1,
    y: 0,
    scale: 1,
    transition: { duration: 600, ease: 'easeOut' }
  }
}

const cardMotion = (index: number) => ({
  initial: { opacity: 0, y: 20 },
  enter: {
    opacity: 1,
    y: 0,
    transition: {
      duration: 400,
      delay: 300 + index * 80,
      ease: 'easeOut'
    }
  }
})

const inputMotion = {
  initial: { opacity: 0, y: 20 },
  enter: {
    opacity: 1,
    y: 0,
    transition: { duration: 500, delay: 800, ease: 'easeOut' }
  }
}

// ===== Methods =====
function handlePromptClick(prompt: QuickPrompt) {
  emit('sendPrompt', prompt.text)
}

function handleSend(content: string) {
  emit('sendPrompt', content)
}
</script>

<style scoped lang="scss">
.kimi-empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  flex: 1;
  padding: 40px 24px;
  position: relative;
  overflow-y: auto;

  .empty-content {
    display: flex;
    flex-direction: column;
    align-items: center;
    margin-bottom: 48px;
  }

  .logo-container {
    text-align: center;
    margin-bottom: 48px;

    .main-logo {
      font-size: 72px;
      font-weight: 800;
      letter-spacing: 12px;
      color: var(--chat-text-primary);
      margin: 0;
      animation: logoBreath 4s ease-in-out infinite;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    }

    .logo-subtitle {
      font-size: 16px;
      color: var(--chat-text-secondary);
      margin-top: 8px;
      letter-spacing: 4px;
    }
  }

  .quick-prompts {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 12px;
    max-width: 720px;
    width: 100%;

    @media (max-width: 768px) {
      grid-template-columns: repeat(2, 1fr);
    }

    @media (max-width: 480px) {
      grid-template-columns: 1fr;
    }
  }

  .prompt-card {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 14px 16px;
    background: var(--chat-surface);
    border: 1px solid var(--chat-border);
    border-radius: 12px;
    cursor: pointer;
    transition: all 0.25s ease;

    &:hover {
      background: var(--chat-surface-hover);
      border-color: var(--chat-accent);
      transform: translateY(-2px);
      box-shadow: 0 4px 20px rgba(79, 142, 247, 0.1);
    }

    .prompt-icon {
      font-size: 20px;
      flex-shrink: 0;
    }

    .prompt-text {
      font-size: 14px;
      color: var(--chat-text-secondary);
      line-height: 1.4;
    }
  }

  .empty-input-wrapper {
    width: 100%;
    max-width: 760px;
    position: sticky;
    bottom: 0;
  }
}

// Logo 呼吸动画
@keyframes logoBreath {
  0%, 100% {
    opacity: 1;
    text-shadow: 0 0 40px rgba(79, 142, 247, 0.15);
  }
  50% {
    opacity: 0.85;
    text-shadow: 0 0 60px rgba(79, 142, 247, 0.25);
  }
}
</style>
```

### 3.4 KimiMessageList.vue — 消息列表

```vue
<template>
  <div ref="listRef" class="kimi-message-list">
    <!-- 使用虚拟滚动优化长列表 -->
    <RecycleScroller
      v-if="messages.length > 20"
      class="message-scroller"
      :items="messagesWithIndex"
      :item-size="80"
      key-field="id"
      v-slot="{ item }"
    >
      <KimiMessageItem
        :message="item"
        :is-streaming="item.id === streamingMessageId"
        :streaming-content="streamingContent"
        :streaming-thought="streamingThought"
        @feedback="$emit('feedback', $event)"
        @copy-message="$emit('copyMessage', $event)"
        @retry="$emit('retry', $event)"
      />
    </RecycleScroller>

    <!-- 普通滚动（消息较少时） -->
    <div v-else class="message-container">
      <transition-group name="message-slide">
        <KimiMessageItem
          v-for="message in messages"
          :key="message.id"
          :message="message"
          :is-streaming="message.id === streamingMessageId"
          :streaming-content="streamingContent"
          :streaming-thought="streamingThought"
          @feedback="$emit('feedback', $event)"
          @copy-message="$emit('copyMessage', $event)"
          @retry="$emit('retry', $event)"
        />
      </transition-group>

      <!-- 正在输入指示器 -->
      <div v-if="isTyping && !streamingContent" class="typing-indicator">
        <div class="typing-dot" />
        <div class="typing-dot" />
        <div class="typing-dot" />
      </div>
    </div>

    <!-- 滚动到底部按钮 -->
    <transition name="fade">
      <n-button
        v-if="showScrollToBottom"
        circle
        class="scroll-to-bottom"
        @click="scrollToBottom"
      >
        <template #icon>
          <n-icon><ChevronDownOutline /></n-icon>
        </template>
      </n-button>
    </transition>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { NButton, NIcon } from 'naive-ui'
import { ChevronDownOutline } from '@vicons/ionicons5'
import { RecycleScroller } from 'vue-virtual-scroller'
import KimiMessageItem from './KimiMessageItem.vue'
import type { ChatMessage } from './types'

// ===== Props =====
interface Props {
  messages: ChatMessage[]
  isTyping?: boolean
  streamingContent?: string
  streamingThought?: string
}

const props = withDefaults(defineProps<Props>(), {
  isTyping: false,
  streamingContent: '',
  streamingThought: ''
})

// ===== Emits =====
const emit = defineEmits<{
  feedback: [messageId: string, type: 'like' | 'dislike']
  copyMessage: [content: string]
  retry: [messageId: string]
}>()

// ===== Refs =====
const listRef = ref<HTMLDivElement>()
const showScrollToBottom = ref(false)

// ===== Computed =====
const messagesWithIndex = computed(() => {
  return props.messages.map((m, i) => ({ ...m, index: i }))
})

const streamingMessageId = computed(() => {
  // 最后一条 AI 消息正在流式输出
  const lastMsg = props.messages[props.messages.length - 1]
  if (lastMsg?.role === 'assistant' && props.isTyping) {
    return lastMsg.id
  }
  return ''
})

// ===== Methods =====
function scrollToBottom() {
  if (listRef.value) {
    listRef.value.scrollTop = listRef.value.scrollHeight
  }
}

function handleScroll() {
  if (!listRef.value) return
  const { scrollTop, scrollHeight, clientHeight } = listRef.value
  showScrollToBottom.value = scrollHeight - scrollTop - clientHeight > 100
}

// 自动滚动到底部
watch(() => props.messages.length, () => {
  nextTick(() => {
    if (!showScrollToBottom.value) {
      scrollToBottom()
    }
  })
})

watch(() => props.streamingContent, () => {
  nextTick(() => {
    if (!showScrollToBottom.value) {
      scrollToBottom()
    }
  })
})

// ===== Lifecycle =====
onMounted(() => {
  listRef.value?.addEventListener('scroll', handleScroll)
  scrollToBottom()
})

onUnmounted(() => {
  listRef.value?.removeEventListener('scroll', handleScroll)
})
</script>

<style scoped lang="scss">
.kimi-message-list {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 16px 0;
  position: relative;

  .message-scroller,
  .message-container {
    padding: 0 24px;
    max-width: 900px;
    margin: 0 auto;
  }

  .typing-indicator {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 16px 20px;
    margin-left: 48px;

    .typing-dot {
      width: 8px;
      height: 8px;
      background: var(--chat-text-muted);
      border-radius: 50%;
      animation: typingBounce 1.4s ease-in-out infinite;

      &:nth-child(2) {
        animation-delay: 0.2s;
      }

      &:nth-child(3) {
        animation-delay: 0.4s;
      }
    }
  }

  .scroll-to-bottom {
    position: absolute;
    bottom: 20px;
    right: 40px;
    background: var(--chat-surface);
    border: 1px solid var(--chat-border);
    color: var(--chat-text-secondary);

    &:hover {
      background: var(--chat-surface-hover);
      color: var(--chat-text-primary);
    }
  }
}

// 消息滑入动画
.message-slide-enter-active,
.message-slide-leave-active {
  transition: all 0.3s ease;
}

.message-slide-enter-from {
  opacity: 0;
  transform: translateY(20px);
}

.message-slide-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}

// 淡入淡出
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

// 打字指示器动画
@keyframes typingBounce {
  0%, 60%, 100% {
    transform: translateY(0);
  }
  30% {
    transform: translateY(-6px);
  }
}
</style>
```

### 3.5 KimiMessageItem.vue — 单条消息

```vue
<template>
  <div class="kimi-message-item" :class="message.role">
    <!-- 用户消息 -->
    <template v-if="message.role === 'user'">
      <div class="user-message-wrapper">
        <div class="user-bubble">
          <div class="message-content">{{ message.content }}</div>
          <!-- 附件展示 -->
          <div v-if="message.attachments?.length" class="attachments">
            <div
              v-for="(file, idx) in message.attachments"
              :key="idx"
              class="attachment-tag"
            >
              <n-icon size="14"><DocumentOutline /></n-icon>
              <span>{{ file.name }}</span>
            </div>
          </div>
        </div>
        <div class="user-avatar">
          <n-avatar
            round
            size="small"
            :src="userAvatar"
            fallback-src="https://api.dicebear.com/7.x/avataaars/svg?seed=user"
          />
        </div>
      </div>
    </template>

    <!-- AI 消息 -->
    <template v-else-if="message.role === 'assistant'">
      <div class="ai-message-wrapper">
        <!-- AI 头像 -->
        <div class="ai-avatar">
          <n-avatar
            round
            size="small"
            :style="{ background: 'var(--chat-accent)' }"
          >
            <n-icon size="16"><SparklesOutline /></n-icon>
          </n-avatar>
        </div>

        <div class="ai-content">
          <!-- AI 名称 -->
          <div class="ai-name">OmicHub AI</div>

          <!-- 思考过程（可折叠） -->
          <div v-if="thoughtContent" class="thought-section">
            <div class="thought-toggle" @click="showThought = !showThought">
              <n-icon size="14" class="toggle-icon" :class="{ expanded: showThought }">
                <ChevronForwardOutline />
              </n-icon>
              <span class="thought-label">思考过程</span>
              <n-tag size="small" :bordered="false" type="info" class="thought-status">
                {{ isStreaming ? '思考中...' : '已完成' }}
              </n-tag>
            </div>
            <n-collapse-transition>
              <div v-show="showThought" class="thought-content">
                <pre>{{ thoughtContent }}</pre>
              </div>
            </n-collapse-transition>
          </div>

          <!-- 消息内容（Markdown 渲染） -->
          <div class="message-body markdown-body" v-html="renderedContent" />

          <!-- 工具调用结果 -->
          <div v-if="message.toolCalls?.length" class="tool-results">
            <div
              v-for="(tool, idx) in message.toolCalls"
              :key="idx"
              class="tool-card"
            >
              <div class="tool-header">
                <n-icon size="16"><BuildOutline /></n-icon>
                <span>{{ tool.name }}</span>
              </div>
              <div class="tool-content">
                <pre>{{ JSON.stringify(tool.result, null, 2) }}</pre>
              </div>
            </div>
          </div>

          <!-- 图表渲染 -->
          <div v-if="message.charts?.length" class="chart-results">
            <div
              v-for="(chart, idx) in message.charts"
              :key="idx"
              class="chart-container"
            >
              <v-chart :option="chart.option" autoresize style="height: 300px" />
            </div>
          </div>

          <!-- 消息操作栏 -->
          <div class="message-actions">
            <n-button text size="tiny" class="action-btn" @click="handleCopy">
              <template #icon><n-icon size="14"><CopyOutline /></n-icon></template>
              复制
            </n-button>
            <n-button text size="tiny" class="action-btn" @click="handleRetry">
              <template #icon><n-icon size="14"><RefreshOutline /></n-icon></template>
              重试
            </n-button>
            <n-button text size="tiny" class="action-btn" @click="handleFeedback('like')">
              <template #icon><n-icon size="14"><ThumbsUpOutline /></n-icon></template>
            </n-button>
            <n-button text size="tiny" class="action-btn" @click="handleFeedback('dislike')">
              <template #icon><n-icon size="14"><ThumbsDownOutline /></n-icon></template>
            </n-button>
          </div>
        </div>
      </div>
    </template>

    <!-- 系统消息 -->
    <template v-else-if="message.role === 'system'">
      <div class="system-message">
        <span>{{ message.content }}</span>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import {
  NAvatar, NButton, NIcon, NTag, NCollapseTransition
} from 'naive-ui'
import {
  SparklesOutline,
  ChevronForwardOutline,
  CopyOutline,
  RefreshOutline,
  ThumbsUpOutline,
  ThumbsDownOutline,
  DocumentOutline,
  BuildOutline
} from '@vicons/ionicons5'
import MarkdownIt from 'markdown-it'
import hljs from 'highlight.js'
import type { ChatMessage } from './types'

// ===== Props =====
interface Props {
  message: ChatMessage
  isStreaming?: boolean
  streamingContent?: string
  streamingThought?: string
  userAvatar?: string
}

const props = withDefaults(defineProps<Props>(), {
  isStreaming: false,
  streamingContent: '',
  streamingThought: ''
})

// ===== Emits =====
const emit = defineEmits<{
  feedback: [messageId: string, type: 'like' | 'dislike']
  copyMessage: [content: string]
  retry: [messageId: string]
}>()

// ===== State =====
const showThought = ref(false)

// ===== Markdown 渲染器 =====
const md = new MarkdownIt({
  html: false,
  linkify: true,
  typographer: true,
  highlight: (str: string, lang: string): string => {
    if (lang && hljs.getLanguage(lang)) {
      try {
        const highlighted = hljs.highlight(str, { language: lang }).value
        return `<pre class="hljs"><div class="code-header"><span class="code-lang">${lang}</span><button class="copy-btn" data-code="${encodeURIComponent(str)}">复制</button></div><code class="hljs language-${lang}">${highlighted}</code></pre>`
      } catch (__) { /* empty */ }
    }
    return `<pre class="hljs"><div class="code-header"><span class="code-lang">text</span><button class="copy-btn" data-code="${encodeURIComponent(str)}">复制</button></div><code>${md.utils.escapeHtml(str)}</code></pre>`
  }
})

// ===== Computed =====
const thoughtContent = computed(() => {
  if (props.isStreaming) {
    return props.streamingThought
  }
  return props.message.thought || ''
})

const renderedContent = computed(() => {
  const content = props.isStreaming
    ? props.streamingContent
    : props.message.content

  if (!content) return ''

  // 添加代码块复制按钮的事件监听
  nextTick(() => {
    document.querySelectorAll('.copy-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const code = decodeURIComponent((e.target as HTMLElement).dataset.code || '')
        navigator.clipboard.writeText(code)
        ;(e.target as HTMLElement).textContent = '已复制!'
        setTimeout(() => {
          ;(e.target as HTMLElement).textContent = '复制'
        }, 1500)
      })
    })
  })

  return md.render(content)
})

// ===== Methods =====
function handleCopy() {
  const content = props.message.content
  navigator.clipboard.writeText(content)
  emit('copyMessage', content)
}

function handleRetry() {
  emit('retry', props.message.id)
}

function handleFeedback(type: 'like' | 'dislike') {
  emit('feedback', props.message.id, type)
}

// 辅助函数
function nextTick(fn: () => void) {
  setTimeout(fn, 0)
}
</script>

<style scoped lang="scss">
.kimi-message-item {
  margin-bottom: 24px;

  // 用户消息样式
  &.user {
    .user-message-wrapper {
      display: flex;
      justify-content: flex-end;
      align-items: flex-start;
      gap: 12px;

      .user-bubble {
        max-width: 80%;
        padding: 12px 18px;
        background: var(--chat-user-bubble);
        border-radius: 18px 18px 4px 18px;
        color: var(--chat-text-primary);
        font-size: 15px;
        line-height: 1.6;

        .message-content {
          white-space: pre-wrap;
          word-break: break-word;
        }

        .attachments {
          margin-top: 8px;
          display: flex;
          flex-wrap: wrap;
          gap: 6px;

          .attachment-tag {
            display: inline-flex;
            align-items: center;
            gap: 4px;
            padding: 4px 10px;
            background: rgba(79, 142, 247, 0.1);
            border-radius: 6px;
            font-size: 12px;
            color: var(--chat-accent);
          }
        }
      }

      .user-avatar {
        flex-shrink: 0;
      }
    }
  }

  // AI 消息样式
  &.assistant {
    .ai-message-wrapper {
      display: flex;
      align-items: flex-start;
      gap: 12px;

      .ai-avatar {
        flex-shrink: 0;
        margin-top: 4px;
      }

      .ai-content {
        flex: 1;
        max-width: calc(100% - 60px);

        .ai-name {
          font-size: 13px;
          font-weight: 500;
          color: var(--chat-accent);
          margin-bottom: 6px;
        }

        // 思考过程
        .thought-section {
          margin-bottom: 10px;
          background: rgba(79, 142, 247, 0.05);
          border: 1px solid rgba(79, 142, 247, 0.15);
          border-radius: 8px;
          overflow: hidden;

          .thought-toggle {
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 8px 12px;
            cursor: pointer;
            user-select: none;
            transition: background 0.2s;

            &:hover {
              background: rgba(79, 142, 247, 0.08);
            }

            .toggle-icon {
              transition: transform 0.2s ease;

              &.expanded {
                transform: rotate(90deg);
              }
            }

            .thought-label {
              font-size: 13px;
              color: var(--chat-text-secondary);
            }

            .thought-status {
              margin-left: auto;
            }
          }

          .thought-content {
            padding: 10px 12px;
            border-top: 1px solid rgba(79, 142, 247, 0.1);

            pre {
              margin: 0;
              font-size: 13px;
              color: var(--chat-text-secondary);
              white-space: pre-wrap;
              word-break: break-word;
              font-family: 'Courier New', monospace;
              line-height: 1.5;
            }
          }
        }

        // 消息内容
        .message-body {
          font-size: 15px;
          line-height: 1.7;
          color: var(--chat-text-primary);

          :deep(p) {
            margin: 0 0 12px;

            &:last-child {
              margin-bottom: 0;
            }
          }

          :deep(ul, ol) {
            margin: 8px 0;
            padding-left: 24px;
          }

          :deep(li) {
            margin: 4px 0;
          }

          :deep(code:not(.hljs)) {
            background: rgba(79, 142, 247, 0.1);
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 13px;
            color: var(--chat-accent);
          }

          :deep(pre.hljs) {
            background: #0d1117;
            border-radius: 10px;
            padding: 0;
            margin: 12px 0;
            overflow: hidden;

            .code-header {
              display: flex;
              justify-content: space-between;
              align-items: center;
              padding: 8px 16px;
              background: #161b22;
              border-bottom: 1px solid #30363d;

              .code-lang {
                font-size: 12px;
                color: var(--chat-text-muted);
                text-transform: uppercase;
              }

              .copy-btn {
                background: transparent;
                border: 1px solid var(--chat-border);
                color: var(--chat-text-secondary);
                padding: 2px 10px;
                border-radius: 4px;
                font-size: 12px;
                cursor: pointer;
                transition: all 0.2s;

                &:hover {
                  background: var(--chat-surface-hover);
                  color: var(--chat-text-primary);
                }
              }
            }

            code {
              display: block;
              padding: 16px;
              overflow-x: auto;
              font-size: 13px;
              line-height: 1.5;
            }
          }

          :deep(blockquote) {
            border-left: 3px solid var(--chat-accent);
            margin: 12px 0;
            padding: 8px 16px;
            background: rgba(79, 142, 247, 0.05);
            border-radius: 0 8px 8px 0;

            p {
              margin: 0;
            }
          }

          :deep(table) {
            width: 100%;
            border-collapse: collapse;
            margin: 12px 0;

            th, td {
              padding: 8px 12px;
              border: 1px solid var(--chat-border);
              text-align: left;
            }

            th {
              background: var(--chat-surface);
              font-weight: 500;
            }
          }

          :deep(a) {
            color: var(--chat-accent);
            text-decoration: none;

            &:hover {
              text-decoration: underline;
            }
          }
        }

        // 工具调用结果
        .tool-results {
          margin-top: 12px;

          .tool-card {
            background: var(--chat-surface);
            border: 1px solid var(--chat-border);
            border-radius: 10px;
            overflow: hidden;
            margin-bottom: 8px;

            .tool-header {
              display: flex;
              align-items: center;
              gap: 8px;
              padding: 10px 14px;
              background: var(--chat-surface-hover);
              font-size: 13px;
              font-weight: 500;
              color: var(--chat-text-primary);
            }

            .tool-content {
              padding: 12px 14px;

              pre {
                margin: 0;
                font-size: 12px;
                color: var(--chat-text-secondary);
                white-space: pre-wrap;
                word-break: break-word;
                max-height: 300px;
                overflow-y: auto;
              }
            }
          }
        }

        // 图表结果
        .chart-results {
          margin-top: 12px;

          .chart-container {
            background: var(--chat-surface);
            border: 1px solid var(--chat-border);
            border-radius: 10px;
            padding: 16px;
          }
        }

        // 消息操作栏
        .message-actions {
          display: flex;
          gap: 4px;
          margin-top: 10px;
          opacity: 0;
          transition: opacity 0.2s ease;

          .action-btn {
            color: var(--chat-text-muted);
            padding: 4px 8px;

            &:hover {
              color: var(--chat-text-secondary);
              background: var(--chat-surface-hover);
            }
          }
        }

        &:hover .message-actions {
          opacity: 1;
        }
      }
    }
  }

  // 系统消息样式
  &.system {
    .system-message {
      text-align: center;
      padding: 8px 0;
      font-size: 13px;
      color: var(--chat-text-muted);
    }
  }
}
</style>
```

### 3.6 KimiSidebar.vue — 左侧边栏

```vue
<template>
  <aside class="kimi-sidebar" :class="{ collapsed }">
    <!-- 顶部 Logo 区域 -->
    <div class="sidebar-header">
      <div v-if="!collapsed" class="sidebar-logo">
        <img src="/logo.svg" alt="OmicHub" class="logo-img" />
        <span class="logo-text">AI 助手</span>
      </div>
      <n-button text class="collapse-btn" @click="$emit('toggleCollapse')">
        <template #icon>
          <n-icon size="18"><MenuOutline /></n-icon>
        </template>
      </n-button>
    </div>

    <!-- 新建会话按钮 -->
    <div class="new-session-area">
      <n-button
        type="primary"
        class="new-session-btn"
        :class="{ collapsed }"
        @click="$emit('newSession')"
      >
        <template #icon>
          <n-icon><AddOutline /></n-icon>
        </template>
        <span v-if="!collapsed" class="btn-text">新建会话</span>
        <span v-if="!collapsed" class="shortcut">⌘K</span>
      </n-button>
    </div>

    <!-- 功能菜单区 -->
    <div class="function-menu">
      <div v-if="!collapsed" class="menu-section-title">功能</div>
      <div class="menu-items">
        <div
          v-for="item in functionMenus"
          :key="item.key"
          class="menu-item"
          :class="{ active: activeMenu === item.key }"
          @click="handleMenuClick(item)"
        >
          <n-icon size="18" class="menu-icon">
            <component :is="item.icon" />
          </n-icon>
          <span v-if="!collapsed" class="menu-label">{{ item.label }}</span>
          <n-tag
            v-if="!collapsed && item.badge"
            size="small"
            :bordered="false"
            type="info"
            class="menu-badge"
          >
            {{ item.badge }}
          </n-tag>
        </div>
      </div>
    </div>

    <!-- 历史会话区 -->
    <div v-if="!collapsed" class="history-section">
      <div class="menu-section-title">
        <span>历史会话</span>
        <n-button text size="tiny" class="clear-btn" @click="handleClearHistory">
          <template #icon><n-icon size="14"><TrashOutline /></n-icon></template>
        </n-button>
      </div>

      <!-- 今天 -->
      <div v-if="todaySessions.length" class="session-group">
        <div class="group-label">今天</div>
        <div
          v-for="session in todaySessions"
          :key="session.id"
          class="session-item"
          :class="{ active: currentSessionId === session.id }"
          @click="$emit('selectSession', session.id)"
        >
          <n-icon size="14" class="session-icon"><ChatbubbleOutline /></n-icon>
          <span class="session-title">{{ session.title }}</span>
          <n-button
            text
            size="tiny"
            class="delete-btn"
            @click.stop="$emit('deleteSession', session.id)"
          >
            <template #icon><n-icon size="12"><CloseOutline /></n-icon></template>
          </n-button>
        </div>
      </div>

      <!-- 昨天 -->
      <div v-if="yesterdaySessions.length" class="session-group">
        <div class="group-label">昨天</div>
        <div
          v-for="session in yesterdaySessions"
          :key="session.id"
          class="session-item"
          :class="{ active: currentSessionId === session.id }"
          @click="$emit('selectSession', session.id)"
        >
          <n-icon size="14" class="session-icon"><ChatbubbleOutline /></n-icon>
          <span class="session-title">{{ session.title }}</span>
          <n-button
            text
            size="tiny"
            class="delete-btn"
            @click.stop="$emit('deleteSession', session.id)"
          >
            <template #icon><n-icon size="12"><CloseOutline /></n-icon></template>
          </n-button>
        </div>
      </div>

      <!-- 更早 -->
      <div v-if="olderSessions.length" class="session-group">
        <div class="group-label">更早</div>
        <div
          v-for="session in olderSessions"
          :key="session.id"
          class="session-item"
          :class="{ active: currentSessionId === session.id }"
          @click="$emit('selectSession', session.id)"
        >
          <n-icon size="14" class="session-icon"><ChatbubbleOutline /></n-icon>
          <span class="session-title">{{ session.title }}</span>
          <n-button
            text
            size="tiny"
            class="delete-btn"
            @click.stop="$emit('deleteSession', session.id)"
          >
            <template #icon><n-icon size="12"><CloseOutline /></n-icon></template>
          </n-button>
        </div>
      </div>

      <!-- 空状态 -->
      <div v-if="!sessions.length" class="history-empty">
        暂无历史会话
      </div>
    </div>

    <!-- 底部用户信息 -->
    <div class="user-info" :class="{ collapsed }">
      <n-avatar
        round
        size="small"
        :src="userInfo.avatar"
        :fallback-src="`https://api.dicebear.com/7.x/initials/svg?seed=${userInfo.name}`"
      />
      <div v-if="!collapsed" class="user-meta">
        <div class="user-name">{{ userInfo.name }}</div>
        <n-tag size="small" :bordered="false" type="success" class="role-tag">
          {{ userInfo.roleTag || userInfo.role }}
        </n-tag>
      </div>
      <n-button v-if="!collapsed" text class="user-menu-btn">
        <template #icon><n-icon size="14"><ChevronDownOutline /></n-icon></template>
      </n-button>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { NButton, NIcon, NAvatar, NTag } from 'naive-ui'
import {
  AddOutline,
  CloseOutline,
  ChatbubbleOutline,
  TrashOutline,
  ChevronDownOutline,
  MenuOutline
} from '@vicons/ionicons5'
import {
  ExtensionPuzzleOutline,
  AnalyticsOutline,
  FolderOutline,
  SearchOutline,
  CodeOutline,
  BotOutline
} from '@vicons/carbon'
import { isToday, isYesterday, parseISO } from 'date-fns'
import type { ChatSession, UserInfo } from './types'

// ===== Props =====
interface Props {
  sessions?: ChatSession[]
  currentSessionId?: string
  userInfo?: UserInfo
  collapsed?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  sessions: () => [],
  currentSessionId: '',
  collapsed: false
})

// ===== Emits =====
const emit = defineEmits<{
  newSession: []
  selectSession: [sessionId: string]
  deleteSession: [sessionId: string]
  toggleCollapse: []
  navigate: [path: string]
}>()

// ===== State =====
const activeMenu = ref('')

// ===== 功能菜单配置 =====
const functionMenus = [
  { key: 'plugin', label: '插件', icon: ExtensionPuzzleOutline, path: '/plugins' },
  { key: 'analysis', label: '分析流程', icon: AnalyticsOutline, path: '/analysis' },
  { key: 'data', label: '项目数据', icon: FolderOutline, path: '/data' },
  { key: 'research', label: '深度研究', icon: SearchOutline, path: '/research' },
  { key: 'code', label: '代码沙盒', icon: CodeOutline, path: '/code-sandbox' },
  { key: 'agent', label: 'Agent 模式', icon: BotOutline, path: '/agent', badge: 'New' }
]

// ===== 会话分组 =====
const todaySessions = computed(() => {
  return props.sessions.filter(s => {
    try { return isToday(parseISO(s.updatedAt)) } catch { return false }
  })
})

const yesterdaySessions = computed(() => {
  return props.sessions.filter(s => {
    try { return isYesterday(parseISO(s.updatedAt)) } catch { return false }
  })
})

const olderSessions = computed(() => {
  return props.sessions.filter(s => {
    try {
      const d = parseISO(s.updatedAt)
      return !isToday(d) && !isYesterday(d)
    } catch { return false }
  })
})

// ===== Methods =====
function handleMenuClick(item: typeof functionMenus[0]) {
  activeMenu.value = item.key
  emit('navigate', item.path)
}

function handleClearHistory() {
  // 清空历史会话逻辑
}
</script>

<style scoped lang="scss">
.kimi-sidebar {
  width: var(--chat-sidebar-width);
  min-width: var(--chat-sidebar-width);
  height: 100%;
  background: var(--chat-sidebar-bg);
  border-right: 1px solid var(--chat-border);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  transition: width 0.3s ease, min-width 0.3s ease;

  &.collapsed {
    width: 60px;
    min-width: 60px;
  }

  .sidebar-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 16px;
    border-bottom: 1px solid var(--chat-border);

    .sidebar-logo {
      display: flex;
      align-items: center;
      gap: 10px;

      .logo-img {
        width: 28px;
        height: 28px;
      }

      .logo-text {
        font-size: 15px;
        font-weight: 600;
        color: var(--chat-text-primary);
      }
    }

    .collapse-btn {
      color: var(--chat-text-secondary);

      &:hover {
        color: var(--chat-text-primary);
      }
    }
  }

  .new-session-area {
    padding: 12px 16px;

    .new-session-btn {
      width: 100%;
      height: 40px;
      border-radius: 10px;
      font-size: 14px;
      background: var(--chat-accent);
      color: #fff;
      transition: all 0.2s ease;

      &:hover {
        background: var(--chat-accent-hover);
      }

      &.collapsed {
        width: 36px;
        height: 36px;
        padding: 0;
        border-radius: 8px;
      }

      .btn-text {
        flex: 1;
        text-align: left;
      }

      .shortcut {
        font-size: 11px;
        opacity: 0.6;
        margin-left: 4px;
      }
    }
  }

  .function-menu {
    padding: 0 12px;
    margin-bottom: 16px;

    .menu-section-title {
      padding: 8px 16px;
      font-size: 11px;
      color: var(--chat-text-muted);
      text-transform: uppercase;
      letter-spacing: 1px;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }

    .menu-items {
      display: flex;
      flex-direction: column;
      gap: 2px;
    }

    .menu-item {
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 9px 14px;
      border-radius: 8px;
      cursor: pointer;
      transition: all 0.2s ease;
      color: var(--chat-text-secondary);
      position: relative;

      &:hover {
        background: var(--chat-surface-hover);
        color: var(--chat-text-primary);
      }

      &.active {
        background: rgba(79, 142, 247, 0.1);
        color: var(--chat-accent);
      }

      .menu-icon {
        flex-shrink: 0;
      }

      .menu-label {
        flex: 1;
        font-size: 14px;
      }

      .menu-badge {
        font-size: 10px;
        height: 18px;
        line-height: 16px;
      }
    }
  }

  .history-section {
    flex: 1;
    overflow-y: auto;
    padding: 0 12px;

    .menu-section-title {
      padding: 8px 16px;
      font-size: 11px;
      color: var(--chat-text-muted);
      text-transform: uppercase;
      letter-spacing: 1px;
      display: flex;
      align-items: center;
      justify-content: space-between;

      .clear-btn {
        color: var(--chat-text-muted);
        opacity: 0;
        transition: opacity 0.2s;

        &:hover {
          color: #ff4d4f;
        }
      }

      &:hover .clear-btn {
        opacity: 1;
      }
    }

    .session-group {
      margin-bottom: 12px;

      .group-label {
        padding: 4px 16px;
        font-size: 11px;
        color: var(--chat-text-muted);
      }
    }

    .session-item {
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 8px 14px;
      border-radius: 8px;
      cursor: pointer;
      transition: all 0.2s ease;
      color: var(--chat-text-secondary);
      position: relative;

      &:hover {
        background: var(--chat-surface-hover);
        color: var(--chat-text-primary);

        .delete-btn {
          opacity: 1;
        }
      }

      &.active {
        background: rgba(79, 142, 247, 0.1);
        color: var(--chat-accent);
      }

      .session-icon {
        flex-shrink: 0;
        opacity: 0.5;
      }

      .session-title {
        flex: 1;
        font-size: 13px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }

      .delete-btn {
        opacity: 0;
        color: var(--chat-text-muted);
        transition: opacity 0.2s;

        &:hover {
          color: #ff4d4f;
        }
      }
    }

    .history-empty {
      padding: 24px;
      text-align: center;
      font-size: 13px;
      color: var(--chat-text-muted);
    }
  }

  .user-info {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 12px 16px;
    border-top: 1px solid var(--chat-border);
    margin-top: auto;

    &.collapsed {
      justify-content: center;
      padding: 12px 8px;
    }

    .user-meta {
      flex: 1;
      min-width: 0;

      .user-name {
        font-size: 13px;
        font-weight: 500;
        color: var(--chat-text-primary);
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }

      .role-tag {
        margin-top: 2px;
        font-size: 10px;
        height: 18px;
        line-height: 16px;
      }
    }

    .user-menu-btn {
      color: var(--chat-text-muted);
      flex-shrink: 0;

      &:hover {
        color: var(--chat-text-primary);
      }
    }
  }
}
</style>
```

### 3.7 SlashCommandMenu.vue — "/" 快捷菜单

```vue
<template>
  <div
    ref="menuRef"
    class="slash-command-menu"
    :style="{ top: position.top + 'px', left: position.left + 'px' }"
  >
    <!-- 搜索框 -->
    <div class="menu-search">
      <n-icon size="16" class="search-icon"><SearchOutline /></n-icon>
      <input
        ref="searchRef"
        v-model="searchQuery"
        class="search-input"
        placeholder="搜索命令..."
        @keydown="handleMenuKeydown"
      />
    </div>

    <!-- 命令列表 -->
    <div class="command-list" ref="listRef">
      <div
        v-for="(command, index) in filteredCommands"
        :key="command.id"
        class="command-item"
        :class="{ active: selectedIndex === index, category: command.isCategory }"
        @click="handleSelect(command)"
        @mouseenter="selectedIndex = index"
      >
        <template v-if="command.isCategory">
          <span class="category-label">{{ command.name }}</span>
        </template>
        <template v-else>
          <div class="command-icon">
            <n-icon size="18"><component :is="command.icon" /></n-icon>
          </div>
          <div class="command-info">
            <div class="command-name">{{ command.name }}</div>
            <div class="command-desc">{{ command.description }}</div>
          </div>
          <div class="command-shortcut">{{ command.shortcut || command.id }}</div>
        </template>
      </div>

      <!-- 空状态 -->
      <div v-if="filteredCommands.length === 0" class="menu-empty">
        未找到匹配的命令
      </div>
    </div>

    <!-- 底部提示 -->
    <div class="menu-footer">
      <div class="footer-hint">
        <kbd>↑</kbd><kbd>↓</kbd> 导航
      </div>
      <div class="footer-hint">
        <kbd>Enter</kbd> 选择
      </div>
      <div class="footer-hint">
        <kbd>Esc</kbd> 关闭
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick } from 'vue'
import { NIcon } from 'naive-ui'
import { SearchOutline } from '@vicons/ionicons5'
import {
  AnalyticsOutline,
  FolderOutline,
  CodeOutline,
  SearchOutline as CarbonSearchOutline,
  ExtensionPuzzleOutline,
  BotOutline,
  ChartLineOutline,
  DataTableOutline,
  DocumentOutline,
  HelpOutline
} from '@vicons/carbon'

// ===== Props =====
interface Props {
  query?: string
  position: { top: number; left: number }
}

const props = withDefaults(defineProps<Props>(), {
  query: ''
})

// ===== Emits =====
const emit = defineEmits<{
  select: [command: string]
  close: []
}>()

// ===== Refs =====
const menuRef = ref<HTMLDivElement>()
const searchRef = ref<HTMLInputElement>()
const listRef = ref<HTMLDivElement>()
const searchQuery = ref(props.query)
const selectedIndex = ref(0)

// ===== 命令定义 =====
interface Command {
  id: string
  name: string
  description: string
  icon: any
  shortcut?: string
  isCategory?: boolean
}

const commands: Command[] = [
  { id: 'category-analysis', name: '分析', isCategory: true },
  { id: '/analysis', name: '分析流程', description: '启动生物信息分析流程', icon: AnalyticsOutline, shortcut: '/analysis' },
  { id: '/rna', name: 'RNA-seq 分析', description: '差异表达基因分析', icon: DataTableOutline, shortcut: '/rna' },
  { id: '/go', name: 'GO 富集分析', description: '基因功能富集分析', icon: ChartLineOutline, shortcut: '/go' },
  { id: '/kegg', name: 'KEGG 通路分析', description: '代谢通路富集分析', icon: ChartLineOutline, shortcut: '/kegg' },

  { id: 'category-data', name: '数据', isCategory: true },
  { id: '/data', name: '查询项目数据', description: '查看您的实验数据', icon: FolderOutline, shortcut: '/data' },
  { id: '/task', name: '查看分析任务', description: '查看正在运行的任务', icon: DocumentOutline, shortcut: '/task' },

  { id: 'category-tools', name: '工具', isCategory: true },
  { id: '/code', name: '代码执行', description: '在沙盒中执行 Python/R 代码', icon: CodeOutline, shortcut: '/code' },
  { id: '/search', name: '文献搜索', description: '搜索 PubMed 等数据库', icon: CarbonSearchOutline, shortcut: '/search' },
  { id: '/plugin', name: '插件市场', description: '浏览可用插件', icon: ExtensionPuzzleOutline, shortcut: '/plugin' },
  { id: '/agent', name: 'Agent 模式', description: '切换到 Agent 自主模式', icon: BotOutline, shortcut: '/agent' },

  { id: 'category-help', name: '帮助', isCategory: true },
  { id: '/help', name: '使用帮助', description: '查看 AI 助手使用指南', icon: HelpOutline, shortcut: '/help' }
]

// ===== Computed =====
const filteredCommands = computed(() => {
  const q = searchQuery.value.toLowerCase().trim()
  if (!q) return commands

  const filtered = commands.filter(cmd => {
    if (cmd.isCategory) return false
    return cmd.name.toLowerCase().includes(q) ||
           cmd.description.toLowerCase().includes(q) ||
           cmd.id.toLowerCase().includes(q)
  })

  // 按类别分组
  const result: Command[] = []
  let lastCategory = ''
  for (const cmd of commands) {
    if (cmd.isCategory) {
      lastCategory = cmd.name
      const hasChildren = filtered.some(f => {
        const idx = commands.indexOf(f)
        // 找到 f 前面的 category
        for (let i = idx - 1; i >= 0; i--) {
          if (commands[i].isCategory) return commands[i].name === lastCategory
        }
        return false
      })
      if (hasChildren) result.push(cmd)
    } else if (filtered.includes(cmd)) {
      result.push(cmd)
    }
  }

  return result
})

// ===== Methods =====
function handleMenuKeydown(e: KeyboardEvent) {
  const items = filteredCommands.value.filter(c => !c.isCategory)
  const itemCount = items.length

  switch (e.key) {
    case 'ArrowDown':
      e.preventDefault()
      selectedIndex.value = (selectedIndex.value + 1) % itemCount
      scrollToSelected()
      break
    case 'ArrowUp':
      e.preventDefault()
      selectedIndex.value = (selectedIndex.value - 1 + itemCount) % itemCount
      scrollToSelected()
      break
    case 'Enter':
      e.preventDefault()
      const selected = items[selectedIndex.value]
      if (selected) handleSelect(selected)
      break
    case 'Escape':
      e.preventDefault()
      emit('close')
      break
  }
}

function handleSelect(command: Command) {
  if (command.isCategory) return
  emit('select', command.id)
}

function scrollToSelected() {
  nextTick(() => {
    const activeEl = listRef.value?.querySelector('.command-item.active')
    if (activeEl) {
      activeEl.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
    }
  })
}

// ===== Lifecycle =====
onMounted(() => {
  nextTick(() => {
    searchRef.value?.focus()
    selectedIndex.value = 0
  })
})
</script>

<style scoped lang="scss">
.slash-command-menu {
  position: fixed;
  z-index: 1000;
  width: 360px;
  background: var(--chat-surface);
  border: 1px solid var(--chat-border);
  border-radius: 12px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
  overflow: hidden;
  animation: menuPopup 0.2s ease-out;

  .menu-search {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 14px;
    border-bottom: 1px solid var(--chat-border);

    .search-icon {
      color: var(--chat-text-muted);
      flex-shrink: 0;
    }

    .search-input {
      flex: 1;
      background: transparent;
      border: none;
      outline: none;
      color: var(--chat-text-primary);
      font-size: 14px;

      &::placeholder {
        color: var(--chat-text-muted);
      }
    }
  }

  .command-list {
    max-height: 320px;
    overflow-y: auto;
    padding: 4px;

    .command-item {
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 8px 12px;
      border-radius: 8px;
      cursor: pointer;
      transition: all 0.15s ease;
      color: var(--chat-text-primary);

      &:hover,
      &.active {
        background: var(--chat-surface-hover);
      }

      &.category {
        padding: 6px 12px;
        cursor: default;
        pointer-events: none;

        &:hover {
          background: transparent;
        }

        .category-label {
          font-size: 11px;
          color: var(--chat-text-muted);
          text-transform: uppercase;
          letter-spacing: 1px;
          font-weight: 500;
        }
      }

      .command-icon {
        width: 32px;
        height: 32px;
        display: flex;
        align-items: center;
        justify-content: center;
        background: rgba(79, 142, 247, 0.1);
        border-radius: 8px;
        color: var(--chat-accent);
        flex-shrink: 0;
      }

      .command-info {
        flex: 1;
        min-width: 0;

        .command-name {
          font-size: 14px;
          font-weight: 500;
        }

        .command-desc {
          font-size: 12px;
          color: var(--chat-text-muted);
          margin-top: 1px;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }
      }

      .command-shortcut {
        font-size: 12px;
        color: var(--chat-text-muted);
        font-family: 'Courier New', monospace;
        flex-shrink: 0;
      }
    }

    .menu-empty {
      padding: 24px;
      text-align: center;
      font-size: 13px;
      color: var(--chat-text-muted);
    }
  }

  .menu-footer {
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 8px 14px;
    border-top: 1px solid var(--chat-border);
    background: rgba(0, 0, 0, 0.2);

    .footer-hint {
      display: flex;
      align-items: center;
      gap: 4px;
      font-size: 11px;
      color: var(--chat-text-muted);

      kbd {
        display: inline-block;
        padding: 2px 6px;
        background: var(--chat-surface-hover);
        border: 1px solid var(--chat-border);
        border-radius: 4px;
        font-size: 10px;
        font-family: monospace;
      }
    }
  }
}

// 菜单弹出动画
@keyframes menuPopup {
  from {
    opacity: 0;
    transform: translateY(8px) scale(0.96);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}
</style>
```

---

## 4. 样式设计（CSS/CSS 变量）

创建文件 `src/styles/chat-theme.css`：

```css
/* ============================================================
   OmicHub AI Chat - Kimi 风格主题变量
   ============================================================ */

/* 暗黑模式变量（Kimi 风格） */
:root[data-theme="dark"] {
  /* 基础背景 */
  --chat-bg: #000000;
  --chat-surface: #1a1a1a;
  --chat-surface-hover: #2a2a2a;
  --chat-sidebar-bg: #000000;

  /* 边框 */
  --chat-border: #333333;
  --chat-border-light: #444444;

  /* 文字 */
  --chat-text-primary: #ffffff;
  --chat-text-secondary: #888888;
  --chat-text-muted: #555555;

  /* 强调色 */
  --chat-accent: #4f8ef7;
  --chat-accent-hover: #3a7de4;
  --chat-accent-light: rgba(79, 142, 247, 0.1);

  /* 消息 */
  --chat-user-bubble: #2a2a2a;
  --chat-ai-card: #111111;

  /* 输入框 */
  --chat-input-bg: #1a1a1a;
  --chat-input-border: #333333;

  /* 状态色 */
  --chat-success: #52c41a;
  --chat-warning: #faad14;
  --chat-error: #ff4d4f;
  --chat-info: #4f8ef7;

  /* 尺寸 */
  --chat-sidebar-width: 260px;
  --chat-logo-size: 120px;
  --chat-max-content-width: 900px;

  /* 阴影 */
  --chat-shadow-sm: 0 2px 8px rgba(0, 0, 0, 0.3);
  --chat-shadow-md: 0 4px 20px rgba(0, 0, 0, 0.4);
  --chat-shadow-lg: 0 8px 32px rgba(0, 0, 0, 0.5);
  --chat-shadow-glow: 0 0 40px rgba(79, 142, 247, 0.15);

  /* 圆角 */
  --chat-radius-sm: 6px;
  --chat-radius-md: 10px;
  --chat-radius-lg: 16px;
  --chat-radius-xl: 20px;

  /* 过渡 */
  --chat-transition-fast: 0.15s ease;
  --chat-transition-normal: 0.25s ease;
  --chat-transition-slow: 0.4s ease;
}

/* 浅色模式变量 */
:root[data-theme="light"] {
  --chat-bg: #f5f5f5;
  --chat-surface: #ffffff;
  --chat-surface-hover: #f0f0f0;
  --chat-sidebar-bg: #ffffff;

  --chat-border: #e0e0e0;
  --chat-border-light: #d0d0d0;

  --chat-text-primary: #1a1a1a;
  --chat-text-secondary: #666666;
  --chat-text-muted: #999999;

  --chat-accent: #2563eb;
  --chat-accent-hover: #1d4ed8;
  --chat-accent-light: rgba(37, 99, 235, 0.1);

  --chat-user-bubble: #2563eb;
  --chat-ai-card: #ffffff;

  --chat-input-bg: #ffffff;
  --chat-input-border: #e0e0e0;

  --chat-success: #52c41a;
  --chat-warning: #faad14;
  --chat-error: #ff4d4f;
  --chat-info: #2563eb;

  --chat-sidebar-width: 260px;
  --chat-logo-size: 120px;
  --chat-max-content-width: 900px;

  --chat-shadow-sm: 0 2px 8px rgba(0, 0, 0, 0.06);
  --chat-shadow-md: 0 4px 20px rgba(0, 0, 0, 0.08);
  --chat-shadow-lg: 0 8px 32px rgba(0, 0, 0, 0.1);
  --chat-shadow-glow: 0 0 40px rgba(37, 99, 235, 0.1);

  --chat-radius-sm: 6px;
  --chat-radius-md: 10px;
  --chat-radius-lg: 16px;
  --chat-radius-xl: 20px;

  --chat-transition-fast: 0.15s ease;
  --chat-transition-normal: 0.25s ease;
  --chat-transition-slow: 0.4s ease;
}

/* ============================================================
   全局滚动条样式
   ============================================================ */

.kimi-layout ::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}

.kimi-layout ::-webkit-scrollbar-track {
  background: transparent;
}

.kimi-layout ::-webkit-scrollbar-thumb {
  background: var(--chat-border);
  border-radius: 3px;
}

.kimi-layout ::-webkit-scrollbar-thumb:hover {
  background: var(--chat-text-muted);
}

/* ============================================================
   代码高亮主题覆盖
   ============================================================ */

.kimi-message-item .hljs {
  background: #0d1117 !important;
  color: #c9d1d9;
}

.kimi-message-item .hljs-keyword {
  color: #ff7b72;
}

.kimi-message-item .hljs-string {
  color: #a5d6ff;
}

.kimi-message-item .hljs-number {
  color: #79c0ff;
}

.kimi-message-item .hljs-function {
  color: #d2a8ff;
}

.kimi-message-item .hljs-comment {
  color: #8b949e;
}

/* ============================================================
   响应式适配
   ============================================================ */

@media (max-width: 768px) {
  :root {
    --chat-sidebar-width: 0px;
  }

  .kimi-sidebar {
    position: fixed;
    left: 0;
    top: 0;
    bottom: 0;
    z-index: 100;
    transform: translateX(-100%);
    transition: transform 0.3s ease;
  }

  .kimi-sidebar.open {
    transform: translateX(0);
  }

  .kimi-empty-state .main-logo {
    font-size: 42px !important;
    letter-spacing: 6px !important;
  }

  .quick-prompts {
    grid-template-columns: 1fr !important;
  }
}

/* ============================================================
   全局动画关键帧
   ============================================================ */

@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes scaleIn {
  from {
    opacity: 0;
    transform: scale(0.95);
  }
  to {
    opacity: 1;
    transform: scale(1);
  }
}

@keyframes slideInRight {
  from {
    opacity: 0;
    transform: translateX(20px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

@keyframes slideInLeft {
  from {
    opacity: 0;
    transform: translateX(-20px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

@keyframes shimmer {
  0% { background-position: -200% 0; }
  100% { background-position: 200% 0; }
}

/* 骨架屏加载动画 */
.skeleton-loading {
  background: linear-gradient(
    90deg,
    var(--chat-surface) 25%,
    var(--chat-surface-hover) 50%,
    var(--chat-surface) 75%
  );
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
}
```

---

## 5. 动画设计

### 5.1 动画清单

| 动画名称 | 触发条件 | 动画描述 | 持续时间 | 缓动函数 |
|----------|----------|----------|----------|----------|
| Logo 呼吸 | 空状态页面加载 | Logo 透明度+阴影脉动 | 4s | ease-in-out |
| 消息滑入 | 新消息添加到列表 | 从下方 20px 滑入+淡入 | 0.3s | ease-out |
| 输入框 Focus | 点击输入框 | 边框变亮+外发光 | 0.3s | ease |
| Slash 菜单弹出 | 输入 "/" | 缩放+淡入 | 0.2s | ease-out |
| 思考展开 | 点击思考区域 | 高度展开 | 0.25s | ease |
| 快捷卡片 Hover | 鼠标悬停 | 上浮+阴影+边框变色 | 0.25s | ease |
| 侧边栏折叠 | 点击折叠按钮 | 宽度渐变 | 0.3s | ease |
| 发送按钮激活 | 输入内容时 | 颜色渐变+缩放 | 0.2s | ease |
| 打字指示器 | AI 正在输入 | 三个点弹跳 | 1.4s | ease-in-out |
| Logo 入场 | 空状态加载 | 淡入+上移+缩放 | 0.6s | ease-out |
| 快捷卡片入场 | 空状态加载 | 依次淡入+上移 | 0.4s | ease-out |
| 输入框入场 | 空状态加载 | 淡入+上移 | 0.5s | ease-out |

### 5.2 关键动画代码

```scss
// Logo 呼吸动画（已在 KimiEmptyState.vue 中定义）
@keyframes logoBreath {
  0%, 100% {
    opacity: 1;
    text-shadow: 0 0 40px rgba(79, 142, 247, 0.15);
  }
  50% {
    opacity: 0.85;
    text-shadow: 0 0 60px rgba(79, 142, 247, 0.25);
  }
}

// 消息滑入动画（已在 KimiMessageList.vue 中定义）
.message-slide-enter-active {
  transition: all 0.3s ease;
}
.message-slide-enter-from {
  opacity: 0;
  transform: translateY(20px);
}

// Slash 菜单弹出动画（已在 SlashCommandMenu.vue 中定义）
@keyframes menuPopup {
  from {
    opacity: 0;
    transform: translateY(8px) scale(0.96);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

// 打字指示器动画（已在 KimiMessageList.vue 中定义）
@keyframes typingBounce {
  0%, 60%, 100% { transform: translateY(0); }
  30% { transform: translateY(-6px); }
}
```

---

## 6. Pinia Store 更新

创建文件 `src/stores/chat.ts`：

```typescript
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { isToday, isYesterday, parseISO } from 'date-fns'
import type { ChatSession, ChatMessage, UserInfo, ModelOption } from '@/components/ai-chat/types'

export const useChatStore = defineStore('chat', () => {
  // ========== State ==========
  const sessions = ref<ChatSession[]>([])
  const currentSessionId = ref<string>('')
  const isTyping = ref(false)
  const streamingContent = ref('')
  const streamingThought = ref('')
  const theme = ref<'dark' | 'light'>('dark')
  const sidebarCollapsed = ref(false)
  const agentMode = ref(false)
  const selectedModel = ref('kimi-k2')

  const currentUser = ref<UserInfo>({
    id: '',
    name: '',
    avatar: '',
    role: '',
    roleTag: ''
  })

  // ========== Getters ==========
  const currentSession = computed<ChatSession | undefined>(() => {
    return sessions.value.find(s => s.id === currentSessionId.value)
  })

  const todaySessions = computed(() => {
    return sessions.value.filter(s => {
      try { return isToday(parseISO(s.updatedAt)) } catch { return false }
    })
  })

  const yesterdaySessions = computed(() => {
    return sessions.value.filter(s => {
      try { return isYesterday(parseISO(s.updatedAt)) } catch { return false }
    })
  })

  const olderSessions = computed(() => {
    return sessions.value.filter(s => {
      try {
        const d = parseISO(s.updatedAt)
        return !isToday(d) && !isYesterday(d)
      } catch { return false }
    })
  })

  const messageCount = computed(() => {
    return currentSession.value?.messages.length || 0
  })

  // ========== Actions ==========

  // 会话管理
  function createSession(title?: string): ChatSession {
    const session: ChatSession = {
      id: `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      title: title || '新对话',
      messages: [],
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      model: selectedModel.value
    }
    sessions.value.unshift(session)
    currentSessionId.value = session.id
    saveToLocalStorage()
    return session
  }

  function selectSession(sessionId: string) {
    currentSessionId.value = sessionId
  }

  function deleteSession(sessionId: string) {
    const idx = sessions.value.findIndex(s => s.id === sessionId)
    if (idx > -1) {
      sessions.value.splice(idx, 1)
      if (currentSessionId.value === sessionId) {
        currentSessionId.value = sessions.value[0]?.id || ''
      }
      saveToLocalStorage()
    }
  }

  function updateSessionTitle(sessionId: string, title: string) {
    const session = sessions.value.find(s => s.id === sessionId)
    if (session) {
      session.title = title
      session.updatedAt = new Date().toISOString()
      saveToLocalStorage()
    }
  }

  // 消息 CRUD
  function addMessage(sessionId: string, message: ChatMessage) {
    const session = sessions.value.find(s => s.id === sessionId)
    if (session) {
      session.messages.push(message)
      session.updatedAt = new Date().toISOString()

      // 自动更新标题（第一条用户消息后）
      if (session.messages.length === 1 && message.role === 'user') {
        const autoTitle = message.content.slice(0, 30) + (message.content.length > 30 ? '...' : '')
        session.title = autoTitle
      }

      saveToLocalStorage()
    }
  }

  function updateMessage(sessionId: string, messageId: string, updates: Partial<ChatMessage>) {
    const session = sessions.value.find(s => s.id === sessionId)
    if (session) {
      const message = session.messages.find(m => m.id === messageId)
      if (message) {
        Object.assign(message, updates)
        saveToLocalStorage()
      }
    }
  }

  function deleteMessage(sessionId: string, messageId: string) {
    const session = sessions.value.find(s => s.id === sessionId)
    if (session) {
      const idx = session.messages.findIndex(m => m.id === messageId)
      if (idx > -1) {
        session.messages.splice(idx, 1)
        saveToLocalStorage()
      }
    }
  }

  function clearMessages(sessionId: string) {
    const session = sessions.value.find(s => s.id === sessionId)
    if (session) {
      session.messages = []
      session.updatedAt = new Date().toISOString()
      saveToLocalStorage()
    }
  }

  // 流式输出控制
  function startStreaming() {
    isTyping.value = true
    streamingContent.value = ''
    streamingThought.value = ''
  }

  function appendStreamContent(content: string) {
    streamingContent.value += content
  }

  function appendStreamThought(thought: string) {
    streamingThought.value += thought
  }

  function finishStreaming() {
    isTyping.value = false
    streamingContent.value = ''
    streamingThought.value = ''
  }

  // 设置
  function setTheme(newTheme: 'dark' | 'light') {
    theme.value = newTheme
    document.documentElement.setAttribute('data-theme', newTheme)
    localStorage.setItem('chat-theme', newTheme)
  }

  function toggleTheme() {
    setTheme(theme.value === 'dark' ? 'light' : 'dark')
  }

  function selectModel(modelId: string) {
    selectedModel.value = modelId
    if (currentSession.value) {
      currentSession.value.model = modelId
    }
  }

  // 持久化
  function saveToLocalStorage() {
    try {
      localStorage.setItem('chat-sessions', JSON.stringify(sessions.value))
    } catch (e) {
      console.warn('Failed to save sessions:', e)
    }
  }

  function loadFromLocalStorage() {
    try {
      const saved = localStorage.getItem('chat-sessions')
      if (saved) {
        sessions.value = JSON.parse(saved)
      }
      const savedTheme = localStorage.getItem('chat-theme')
      if (savedTheme) {
        theme.value = savedTheme as 'dark' | 'light'
        document.documentElement.setAttribute('data-theme', theme.value)
      }
    } catch (e) {
      console.warn('Failed to load sessions:', e)
    }
  }

  // 初始化
  function initStore(user: UserInfo) {
    currentUser.value = user
    loadFromLocalStorage()
    if (!sessions.value.length) {
      createSession()
    } else if (!currentSessionId.value) {
      currentSessionId.value = sessions.value[0].id
    }
  }

  return {
    // State
    sessions,
    currentSessionId,
    isTyping,
    streamingContent,
    streamingThought,
    theme,
    sidebarCollapsed,
    agentMode,
    selectedModel,
    currentUser,

    // Getters
    currentSession,
    todaySessions,
    yesterdaySessions,
    olderSessions,
    messageCount,

    // Actions
    createSession,
    selectSession,
    deleteSession,
    updateSessionTitle,
    addMessage,
    updateMessage,
    deleteMessage,
    clearMessages,
    startStreaming,
    appendStreamContent,
    appendStreamThought,
    finishStreaming,
    setTheme,
    toggleTheme,
    selectModel,
    initStore,
    saveToLocalStorage,
    loadFromLocalStorage
  }
})
```

### 类型定义文件 `src/components/ai-chat/types.ts`：

```typescript
// ===== 聊天消息 =====
export interface ChatMessage {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  thought?: string
  toolCalls?: ToolCall[]
  charts?: ChartData[]
  attachments?: FileAttachment[]
  feedback?: 'like' | 'dislike'
  createdAt: string
}

// ===== 工具调用 =====
export interface ToolCall {
  id: string
  name: string
  arguments: Record<string, any>
  result?: any
  status: 'pending' | 'running' | 'success' | 'error'
}

// ===== 图表数据 =====
export interface ChartData {
  id: string
  type: 'echarts'
  option: any
}

// ===== 文件附件 =====
export interface FileAttachment {
  name: string
  size: number
  type: string
  url?: string
}

// ===== 会话 =====
export interface ChatSession {
  id: string
  title: string
  messages: ChatMessage[]
  createdAt: string
  updatedAt: string
  model: string
  shared?: boolean
  settings?: SessionSettings
}

// ===== 会话设置 =====
export interface SessionSettings {
  temperature?: number
  maxTokens?: number
  topP?: number
  systemPrompt?: string
}

// ===== 用户信息 =====
export interface UserInfo {
  id: string
  name: string
  avatar: string
  role: string
  roleTag?: string
}

// ===== 快捷提示 =====
export interface QuickPrompt {
  icon: string
  text: string
  category: string
}

// ===== 模型选项 =====
export interface ModelOption {
  id: string
  name: string
  description: string
  provider: string
}

// ===== 插件选项 =====
export interface PluginOption {
  id: string
  name: string
  description: string
  icon: string
}

// ===== Slash 命令 =====
export interface SlashCommand {
  id: string
  name: string
  description: string
  icon: string
  category: string
  shortcut?: string
}
```

---

## 7. 改造步骤迁移计划

### 步骤 1：安装第三方依赖包（5 分钟）

```bash
# 核心依赖
cd /path/to/omic-hub-frontend
npm install markdown-it @types/markdown-it highlight.js vue3-copy-to-clipboard

# VueUse 全家桶（核心功能库）
npm install @vueuse/core @vueuse/motion

# 虚拟滚动
npm install vue-virtual-scroller@next

# 图标库
npm install @vicons/ionicons5 @vicons/carbon

# 工具库
npm install date-fns echarts vue-echarts
```

### 步骤 2：创建 CSS 主题文件（5 分钟）

1. 创建 `src/styles/chat-theme.css`
2. 将上述 CSS 变量代码复制到该文件
3. 在 `main.ts` 中引入：`import './styles/chat-theme.css'`
4. 在 `main.ts` 中设置默认主题：`document.documentElement.setAttribute('data-theme', 'dark')`

### 步骤 3：创建类型定义文件（3 分钟）

1. 创建 `src/components/ai-chat/types.ts`
2. 将所有类型定义复制到该文件

### 步骤 4：创建 Pinia Store（5 分钟）

1. 创建 `src/stores/chat.ts`
2. 将 Store 代码复制到该文件
3. 在需要的地方引入并使用

### 步骤 5：创建新布局组件（按顺序）（30 分钟）

按以下顺序创建组件（因为有依赖关系）：

| 顺序 | 组件 | 文件路径 | 依赖 |
|------|------|----------|------|
| 1 | SlashCommandMenu | `src/components/ai-chat/SlashCommandMenu.vue` | 无 |
| 2 | KimiChatInput | `src/components/ai-chat/KimiChatInput.vue` | SlashCommandMenu |
| 3 | KimiMessageItem | `src/components/ai-chat/KimiMessageItem.vue` | 无 |
| 4 | KimiMessageList | `src/components/ai-chat/KimiMessageList.vue` | KimiMessageItem |
| 5 | KimiEmptyState | `src/components/ai-chat/KimiEmptyState.vue` | KimiChatInput |
| 6 | KimiSidebar | `src/components/ai-chat/KimiSidebar.vue` | 无 |
| 7 | KimiLayout | `src/components/ai-chat/KimiLayout.vue` | 以上全部 |

### 步骤 6：替换当前 AI 助手页面（10 分钟）

1. 找到当前的 AI 助手页面组件（可能在 `src/views/AIAssistant.vue` 或类似路径）
2. 备份原有代码
3. 替换为新的 KimiLayout 组件引用：

```vue
<template>
  <KimiLayout
    theme="dark"
    @send="handleSend"
    @new-session="handleNewSession"
    @navigate="handleNavigate"
  />
</template>

<script setup lang="ts">
import KimiLayout from '@/components/ai-chat/KimiLayout.vue'
import { useChatStore } from '@/stores/chat'

const chatStore = useChatStore()

function handleSend(content: string, options: any) {
  // 调用后端 API 发送消息
  // 使用 SSE 接收流式响应
}

function handleNewSession() {
  chatStore.createSession()
}

function handleNavigate(path: string) {
  // 处理导航
}
</script>
```

### 步骤 7：接入后端 API（15 分钟）

```typescript
// src/api/chat.ts
import { useChatStore } from '@/stores/chat'

export async function sendChatMessage(content: string, options: SendOptions) {
  const chatStore = useChatStore()
  const session = chatStore.currentSession
  if (!session) return

  // 添加用户消息
  const userMessage: ChatMessage = {
    id: `msg_${Date.now()}`,
    role: 'user',
    content,
    createdAt: new Date().toISOString()
  }
  chatStore.addMessage(session.id, userMessage)

  // 创建 AI 消息占位
  const aiMessageId = `msg_${Date.now()}_ai`
  chatStore.addMessage(session.id, {
    id: aiMessageId,
    role: 'assistant',
    content: '',
    createdAt: new Date().toISOString()
  })

  // 开始流式输出
  chatStore.startStreaming()

  // SSE 请求
  const response = await fetch('/api/v1/chat/completions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      session_id: session.id,
      message: content,
      model: options.model,
      agent_mode: options.agentMode,
      plugins: options.plugins
    })
  })

  // 读取 SSE 流
  const reader = response.body?.getReader()
  const decoder = new TextDecoder()

  if (!reader) {
    chatStore.finishStreaming()
    return
  }

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      const chunk = decoder.decode(value)
      const lines = chunk.split('\n')

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = line.slice(6)
          if (data === '[DONE]') continue

          try {
            const parsed = JSON.parse(data)
            const delta = parsed.choices?.[0]?.delta

            if (delta?.reasoning_content) {
              chatStore.appendStreamThought(delta.reasoning_content)
            }
            if (delta?.content) {
              chatStore.appendStreamContent(delta.content)
            }
          } catch (e) {
            // 忽略解析错误
          }
        }
      }
    }
  } finally {
    // 更新最终消息内容
    chatStore.updateMessage(session.id, aiMessageId, {
      content: chatStore.streamingContent,
      thought: chatStore.streamingThought || undefined
    })
    chatStore.finishStreaming()
  }
}
```

### 步骤 8：测试和调优（20 分钟）

检查清单：

- [ ] 深色主题正确渲染
- [ ] 浅色主题切换正常
- [ ] 新建会话按钮工作
- [ ] ⌘+K 快捷键工作
- [ ] 历史会话显示和分组
- [ ] 会话切换正常
- [ ] 空状态 Logo 和快捷卡片显示
- [ ] 快捷卡片点击发送消息
- [ ] 输入框自适应高度
- [ ] Enter 发送 / Shift+Enter 换行
- [ ] "/" 唤起 Slash 菜单
- [ ] Slash 菜单键盘导航
- [ ] 用户消息右对齐气泡
- [ ] AI 消息左对齐卡片
- [ ] Markdown 渲染正常
- [ ] 代码块语法高亮
- [ ] 代码块复制按钮
- [ ] 思考过程折叠/展开
- [ ] 消息入场动画
- [ ] 流式输出效果
- [ ] 底部工具栏（Agent/模型/插件）
- [ ] 模型选择下拉
- [ ] 响应式适配（移动端）
- [ ] Pinia Store 持久化

### 迁移计划时间估算

| 步骤 | 任务 | 预估时间 |
|------|------|----------|
| 1 | 安装依赖 | 5 分钟 |
| 2 | CSS 主题文件 | 5 分钟 |
| 3 | 类型定义 | 3 分钟 |
| 4 | Pinia Store | 5 分钟 |
| 5 | 7 个 Vue 组件 | 30 分钟 |
| 6 | 替换页面 | 10 分钟 |
| 7 | API 接入 | 15 分钟 |
| 8 | 测试调优 | 20 分钟 |
| **总计** | | **约 1.5 小时** |

---

## 附录：与 OmicHub 现有系统的集成点

### A. 与现有左侧导航的兼容

OmicHub 已有左侧系统导航栏（分析中心/数据管理/任务中心/AI 助手/代码沙盒/用量统计/系统设置）。新设计将 AI 助手的左侧改为**聊天专用边栏**，系统导航通过以下方式兼容：

1. **方案推荐**：保留原有系统导航作为一级导航，AI 助手页面内使用新的 KimiSidebar 作为二级导航
2. **面包屑导航**：在 AI 助手页面顶部显示 "OmicHub > AI 助手 > 当前会话标题"
3. **统一入口**：在 KimiSidebar 底部用户信息上方添加"返回系统"按钮

### B. 与现有 AI 模型配置的对接

从截图 2 可以看到，OmicHub 已有 AI 模型配置页面（Provider 配置表），支持 kimi/qwen 等模型。新设计中的模型选择下拉直接读取该配置：

```typescript
// 从现有 API 获取模型列表
const { data: models } = useQuery({
  queryKey: ['ai-models'],
  queryFn: fetchAIModels  // 复用现有 API
})
```

### C. 与现有用户系统的对接

底部用户信息从现有用户系统获取：

```typescript
// 从现有 auth store 获取
const authStore = useAuthStore()
const userInfo = computed(() => ({
  id: authStore.user.id,
  name: authStore.user.username,
  avatar: authStore.user.avatar,
  role: authStore.user.role,
  roleTag: authStore.user.roleTag
}))
```

---

> **文档结束**。本方案提供了从设计分析到完整代码实现的全链路指导，所有 Vue 组件均采用 `<script setup>` + TypeScript 编写，可直接集成到 OmicHub 的 Vue 3 + Vite 项目中。
