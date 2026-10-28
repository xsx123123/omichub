# 🌌 OmicHub AI助手「全状态生成态」视觉重塑方案 v2.0

> **版本**：v2.0  
> **针对模块**：AI助手聊天界面 - 回答生成中状态  
> **设计主题**：星尘流动 · 渐进浮现  
> **目标**：消灭空白卡片与廉价三圆点，让等待本身成为一种视觉享受；覆盖思考态、生成态、空状态、错误态全场景

---

## 一、问题全景诊断

| 场景 | 现状 | 痛点 |
|------|------|------|
| **思考中** | 灯泡+文字，可展开 | 展开后下方直接空白，无过渡 |
| **思考完→生成中** | 思考面板展开，下方空白 | 上下割裂，像"半截消息" |
| **纯生成中（无思考）** | 空白卡片+三圆点 | 焦虑感最强 |
| **无内容返回** | 空白或错误提示生硬 | 用户不知发生了什么 |
| **流式生成** | 文字突然出现 | 缺乏"书写感" |

---

## 二、五态设计体系

所有AI回复区域必须处于以下五种状态之一，**禁止出现第六种"裸空白"**：

```
┌─────────────────────────────────────────┐
│  State 1: 思考中（Thinking）            │
│  State 2: 思考完成+生成中（Streaming）  │
│  State 3: 纯生成中（Skeleton→Stream）  │
│  State 4: 生成完成（Completed）         │
│  State 5: 空内容/错误（Empty/Error）    │
└─────────────────────────────────────────┘
```

---

## 三、分态设计详解

### 3.1 State 1：思考中（Thinking）

**触发**：AI开始思考，尚未返回任何内容

**视觉结构**：

```
┌─────────────────────────────────────────┐
│ 🤖 qwen3.7-max          Tokens... 19:38│
├─────────────────────────────────────────┤
│ ┌─ 思考过程 ─────────────────────┐ ▼  │
│ │ 💡 正在分析用户意图...          │    │
│ │    · 识别关键词：减肥、武汉      │    │
│ │    · 关联知识库：营养学、本地美食 │    │
│ └────────────────────────────────────┘ │
│                                         │
│  ┌─────────────────────────────────┐   │
│  │ ░░  ████  ░░░░  ████  ░░░░   │   │  ← 骨架屏（下方必须紧跟）
│  │ ░░  ░░░░  ████  ░░░░  ████   │   │
│  │  星尘正在凝聚回答...            │   │
│  └─────────────────────────────────┘   │
│         ↑ 卡片呼吸微光边框               │
└─────────────────────────────────────────┘
```

**关键规则**：
- 思考面板展开时，**下方必须立即显示骨架屏**，禁止留白
- 思考面板样式优化：
  - 背景：`rgba(99, 102, 241, 0.04)`（极淡紫）
  - 边框：`1px solid rgba(99, 102, 241, 0.12)`
  - 圆角：`12px`
  - 左侧灯泡：渐变 SVG 图标（紫→蓝），不要默认emoji
  - 文字：`#4B5563`（深灰），`14px`
  - 展开箭头：旋转动画 `200ms ease`

**思考面板组件代码**：

```tsx
<div className="thinking-panel">
  <div className="thinking-header" onClick={toggle}>
    <div className="thinking-icon">
      <svg className="bulb-glow" /> {/* 渐变灯泡 */}
    </div>
    <span className="thinking-title">思考过程</span>
    <span className="thinking-status">分析中...</span>
    <ChevronIcon className={`arrow ${isOpen ? 'open' : ''}`} />
  </div>

  {isOpen && (
    <div className="thinking-content">
      {thinkingSteps.map((step, i) => (
        <div key={i} className="thinking-step">
          <span className="step-dot" />
          <span className="step-text">{step}</span>
        </div>
      ))}
    </div>
  )}
</div>
```

**思考面板 CSS**：

```css
.thinking-panel {
  background: rgba(99, 102, 241, 0.04);
  border: 1px solid rgba(99, 102, 241, 0.12);
  border-radius: 12px;
  margin-bottom: 12px;
  overflow: hidden;
}

.thinking-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  cursor: pointer;
  transition: background 0.2s;
}
.thinking-header:hover {
  background: rgba(99, 102, 241, 0.06);
}

.thinking-icon {
  width: 18px;
  height: 18px;
  color: #6366f1;
}

.thinking-title {
  font-size: 14px;
  font-weight: 500;
  color: #374151;
  flex: 1;
}

.thinking-status {
  font-size: 12px;
  color: #6366f1;
  background: rgba(99, 102, 241, 0.1);
  padding: 2px 10px;
  border-radius: 10px;
}

.thinking-content {
  padding: 0 14px 12px 42px;
  font-size: 13px;
  line-height: 1.8;
  color: #6b7280;
}

.thinking-step {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin-bottom: 4px;
}

.step-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: #a855f7;
  margin-top: 8px;
  flex-shrink: 0;
}

/* 展开箭头动画 */
.arrow {
  transition: transform 0.2s ease;
  color: #9ca3af;
}
.arrow.open {
  transform: rotate(180deg);
}
```

---

### 3.2 State 2：思考完成 + 正式生成中（Thinking Done + Streaming）

**触发**：思考内容已返回，正式回复开始流式生成

**视觉结构**：

```
┌─────────────────────────────────────────┐
│ 🤖 qwen3.7-max          Tokens... 19:38│
├─────────────────────────────────────────┤
│ ┌─ 思考过程 ─────────────────────┐ ▼  │
│ │ 💡 已深度思考（3步）            │    │
│ │    · 用户意图分析               │    │
│ │    · 知识库检索                 │    │
│ └────────────────────────────────────┘ │
│                                         │
│  武汉美食分析与减肥适配：                 │
│  - 热干面：碳水+脂肪... █               │  ← 流式文字+光标
│                                         │
└─────────────────────────────────────────┘
```

**关键规则**：
- 思考面板自动折叠（或保持用户手动展开的状态）
- 思考面板标题从"思考中..."变为"已深度思考"
- 思考面板背景色从动态脉冲变为静态淡紫
- 下方立即进入 State 3 的流式生成

---

### 3.3 State 3：纯生成中（Skeleton → Stream）

**触发**：无思考过程，直接开始生成回复

#### 阶段A：骨架屏（0~首个字符到达）

```css
.skeleton-container {
  padding: 8px 0;
}

.skeleton-line {
  height: 16px;
  border-radius: 8px;
  margin-bottom: 12px;
  /* 星尘主题流光 */
  background: linear-gradient(90deg, 
    rgba(99,102,241,0.06) 0%, 
    rgba(168,85,247,0.12) 20%, 
    rgba(59,130,246,0.12) 40%, 
    rgba(168,85,247,0.12) 60%, 
    rgba(99,102,241,0.06) 80%
  );
  background-size: 300% 100%;
  animation: stardust-flow 2s ease-in-out infinite;
}

@keyframes stardust-flow {
  0% { background-position: 300% 0; }
  100% { background-position: -300% 0; }
}
```

#### 阶段B：流式文字（首个字符到达后）

- 骨架屏 `opacity: 1→0`，`300ms` 渐隐
- 文字 `opacity: 0→1`，`200ms` 渐显
- 光标紧跟末尾

#### 阶段C：底部兜底（如果内容为空超过2秒）

显示一行小字：

> `🌌 星尘正在穿越神经网络，请稍候...`

```css
.waiting-hint {
  text-align: center;
  font-size: 13px;
  color: #9ca3af;
  margin-top: 16px;
  animation: gentle-pulse 2s ease-in-out infinite;
}
```

---

### 3.4 State 4：生成完成（Completed）

**触发**：流结束，内容完整

**过渡动画**：
- 光标消失：`opacity 1→0`，`200ms`
- 卡片呼吸停止：移除 `streaming-active` class
- Markdown 渲染：一次性高亮，不要逐行闪烁

---

### 3.5 State 5：空内容 / 错误（Empty / Error）

**触发**：模型返回空、API 异常、Agent 配置错误

**绝对禁止**：显示空白卡片或只有三个点然后停止

#### 空内容态

```
┌─────────────────────────────────────────┐
│ 🤖 qwen3.7-max          Tokens... 19:38│
├─────────────────────────────────────────┤
│                                         │
│     🌌                                  │
│     这片星域暂时没有回应                │
│                                         │
│     模型似乎返回了空内容，可能是：       │
│     · 当前问题超出了模型的知识边界       │
│     · 网络连接出现波动                   │
│                                         │
│     [🔄 重新生成]  [✏️ 换个问法]        │
│                                         │
└─────────────────────────────────────────┘
```

#### 错误态

```
┌─────────────────────────────────────────┐
│ 🤖 qwen3.7-max          Tokens... 19:38│
├─────────────────────────────────────────┤
│                                         │
│     💫                                  │
│     星尘信号受到了干扰                   │
│                                         │
│     错误代码：AGENT_CONFIG_ERROR          │
│     描述：当前 Agent 配置异常，无法调用工具 │
│                                         │
│     [🔄 重试]  [⚙️ 检查 Agent 配置]      │
│                                         │
└─────────────────────────────────────────┘
```

**空状态组件代码**：

```tsx
<div className="empty-state">
  <div className="empty-icon">🌌</div>
  <div className="empty-title">这片星域暂时没有回应</div>
  <div className="empty-desc">
    模型似乎返回了空内容，可能是：<br/>
    · 当前问题超出了模型的知识边界<br/>
    · 网络连接出现波动
  </div>
  <div className="empty-actions">
    <button className="btn-primary">🔄 重新生成</button>
    <button className="btn-secondary">✏️ 换个问法</button>
  </div>
</div>
```

```css
.empty-state {
  text-align: center;
  padding: 48px 24px;
  color: #6b7280;
}

.empty-icon {
  font-size: 48px;
  margin-bottom: 16px;
  opacity: 0.8;
}

.empty-title {
  font-size: 16px;
  font-weight: 600;
  color: #374151;
  margin-bottom: 8px;
}

.empty-desc {
  font-size: 13px;
  line-height: 1.8;
  color: #9ca3af;
  margin-bottom: 24px;
}

.empty-actions {
  display: flex;
  gap: 12px;
  justify-content: center;
}

.btn-primary {
  background: linear-gradient(135deg, #6366f1, #a855f7);
  color: white;
  border: none;
  padding: 8px 20px;
  border-radius: 10px;
  font-size: 13px;
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
}
.btn-primary:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(99, 102, 241, 0.3);
}
```

---

## 四、状态流转图

```
用户发送消息
    │
    ▼
┌─────────────────┐
│  创建 AI 卡片    │
│  进入生成态      │
└─────────────────┘
    │
    ├─ 有思考过程？────────────────┐
    │                              │
    ▼                              ▼
┌──────────────┐          ┌──────────────┐
│ State 1      │          │ State 3-A    │
│ 思考面板展开  │          │ 骨架屏流光   │
│ + 下方骨架屏 │          │              │
└──────────────┘          └──────────────┘
    │                              │
    │ 思考完成                      │ 收到首字符
    ▼                              ▼
┌──────────────┐          ┌──────────────┐
│ State 2      │          │ State 3-B    │
│ 思考面板折叠  │          │ 骨架屏渐隐   │
│ 或标记完成    │          │ 文字流式浮现 │
│ 下方流式生成  │          │ + 光标闪烁   │
└──────────────┘          └──────────────┘
    │                              │
    │                              │ 生成完成
    │                              ▼
    │                         ┌──────────────┐
    │                         │ State 4      │
    │                         │ 完成态       │
    │                         │ Markdown渲染 │
    │                         └──────────────┘
    │
    └─ 异常分支 ───────────────────────────┐
        │                                    │
        ▼                                    ▼
   ┌──────────────┐                 ┌──────────────┐
   │ State 5-A    │                 │ State 5-B    │
   │ 空内容       │                 │ 错误态       │
   │ 优雅空状态   │                 │ 错误提示+操作 │
   └──────────────┘                 └──────────────┘
```

---

## 五、核心动画规范汇总

### 5.1 卡片呼吸动画

```css
.message-card.streaming-active {
  animation: card-breathe 3s ease-in-out infinite;
  border-color: rgba(99, 102, 241, 0.15);
}

@keyframes card-breathe {
  0%, 100% { box-shadow: 0 0 0 0 rgba(99, 102, 241, 0); }
  50% { box-shadow: 0 4px 24px -4px rgba(99, 102, 241, 0.12); }
}
```

### 5.2 骨架屏流光动画

```css
@keyframes stardust-flow {
  0% { background-position: 300% 0; }
  100% { background-position: -300% 0; }
}

.skeleton-line {
  height: 16px;
  border-radius: 8px;
  margin-bottom: 12px;
  background: linear-gradient(90deg, 
    rgba(99,102,241,0.06) 0%, 
    rgba(168,85,247,0.12) 20%, 
    rgba(59,130,246,0.12) 40%, 
    rgba(168,85,247,0.12) 60%, 
    rgba(99,102,241,0.06) 80%
  );
  background-size: 300% 100%;
  animation: stardust-flow 2s ease-in-out infinite;
}
```

### 5.3 光标闪烁动画

```css
@keyframes cursor-blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

.cursor-blink {
  display: inline-block;
  width: 2px;
  height: 1.2em;
  background: linear-gradient(180deg, #6366f1, #a855f7);
  margin-left: 2px;
  vertical-align: text-bottom;
  animation: cursor-blink 1.1s step-end infinite;
}
```

### 5.4 思考脉冲动画

```css
@keyframes pulse-ring {
  0%, 100% { transform: scale(1); opacity: 1; }
  50% { transform: scale(1.3); opacity: 0.6; }
}

.pulse-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: linear-gradient(135deg, #6366f1, #a855f7);
  animation: pulse-ring 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}
```

### 5.5 底部流光条动画

```css
@keyframes flow-move {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

.flow-bar {
  height: 2px;
  width: 60%;
  margin: 16px auto 0;
  border-radius: 2px;
  background: linear-gradient(90deg, transparent, #6366f1, #a855f7, transparent);
  background-size: 200% 100%;
  animation: flow-move 1.5s linear infinite;
}
```

---

## 六、完整组件代码示例（React + Tailwind）

```tsx
import React, { useState, useEffect } from 'react';
import './StreamingMessage.css';

interface StreamingMessageProps {
  modelName: string;
  isThinking: boolean;
  thinkingSteps?: string[];
  content: string;
  isStreaming: boolean;
  tokens: { input: number; output: number };
  timestamp: string;
  error?: { code: string; message: string } | null;
}

export const StreamingMessage: React.FC<StreamingMessageProps> = ({
  modelName,
  isThinking,
  thinkingSteps,
  content,
  isStreaming,
  tokens,
  timestamp,
  error,
}) => {
  const [showSkeleton, setShowSkeleton] = useState(true);
  const [isThinkingOpen, setIsThinkingOpen] = useState(true);

  // 收到第一个字符后，骨架屏渐隐
  useEffect(() => {
    if (content.length > 0) {
      const timer = setTimeout(() => setShowSkeleton(false), 300);
      return () => clearTimeout(timer);
    }
  }, [content]);

  // 思考完成后自动折叠
  useEffect(() => {
    if (!isThinking && thinkingSteps && thinkingSteps.length > 0) {
      const timer = setTimeout(() => setIsThinkingOpen(false), 500);
      return () => clearTimeout(timer);
    }
  }, [isThinking, thinkingSteps]);

  // 错误态
  if (error) {
    return (
      <div className="message-card">
        <div className="message-header">
          <div className="model-info">
            <span className="model-avatar">🌌</span>
            <span className="model-name">{modelName}</span>
          </div>
          <div className="meta-info">
            <span className="tokens">Tokens: {tokens.input} ↑{tokens.output} ↓0</span>
            <span className="timestamp">{timestamp}</span>
          </div>
        </div>
        <div className="empty-state error">
          <div className="empty-icon">💫</div>
          <div className="empty-title">星尘信号受到了干扰</div>
          <div className="empty-desc">
            错误代码：{error.code}<br/>
            描述：{error.message}
          </div>
          <div className="empty-actions">
            <button className="btn-primary">🔄 重试</button>
            <button className="btn-secondary">⚙️ 检查 Agent 配置</button>
          </div>
        </div>
      </div>
    );
  }

  // 空内容态（非流式且无内容）
  if (!isStreaming && !isThinking && content.length === 0) {
    return (
      <div className="message-card">
        <div className="message-header">
          <div className="model-info">
            <span className="model-avatar">🌌</span>
            <span className="model-name">{modelName}</span>
          </div>
          <div className="meta-info">
            <span className="tokens">Tokens: {tokens.input} ↑{tokens.output} ↓0</span>
            <span className="timestamp">{timestamp}</span>
          </div>
        </div>
        <div className="empty-state">
          <div className="empty-icon">🌌</div>
          <div className="empty-title">这片星域暂时没有回应</div>
          <div className="empty-desc">
            模型似乎返回了空内容，可能是：<br/>
            · 当前问题超出了模型的知识边界<br/>
            · 网络连接出现波动
          </div>
          <div className="empty-actions">
            <button className="btn-primary">🔄 重新生成</button>
            <button className="btn-secondary">✏️ 换个问法</button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={`message-card ${isStreaming ? 'streaming-active' : ''}`}>
      {/* 头部 */}
      <div className="message-header">
        <div className="model-info">
          <span className="model-avatar">🌌</span>
          <span className="model-name">{modelName}</span>
        </div>
        <div className="meta-info">
          <span className="tokens">Tokens: {tokens.input} ↑{tokens.output} ↓0</span>
          <span className="timestamp">{timestamp}</span>
        </div>
      </div>

      {/* 思考过程 */}
      {(isThinking || (thinkingSteps && thinkingSteps.length > 0)) && (
        <div className="thinking-panel">
          <div 
            className="thinking-header" 
            onClick={() => setIsThinkingOpen(!isThinkingOpen)}
          >
            <div className="thinking-icon">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
                <path d="M12 2C8.13 2 5 5.13 5 9c0 2.38 1.19 4.47 3 5.74V17c0 .55.45 1 1 1h6c.55 0 1-.45 1-1v-2.26c1.81-1.27 3-3.36 3-5.74 0-3.87-3.13-7-7-7z" 
                  fill="url(#bulbGradient)"/>
                <defs>
                  <linearGradient id="bulbGradient" x1="5" y1="2" x2="19" y2="18">
                    <stop offset="0%" stopColor="#6366f1"/>
                    <stop offset="100%" stopColor="#a855f7"/>
                  </linearGradient>
                </defs>
              </svg>
            </div>
            <span className="thinking-title">思考过程</span>
            <span className={`thinking-status ${isThinking ? 'active' : ''}`}>
              {isThinking ? '分析中...' : `已深度思考（${thinkingSteps?.length || 0}步）`}
            </span>
            <svg 
              className={`arrow ${isThinkingOpen ? 'open' : ''}`} 
              width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
            >
              <path d="M6 9l6 6 6-6" strokeWidth="2" strokeLinecap="round"/>
            </svg>
          </div>

          {isThinkingOpen && thinkingSteps && (
            <div className="thinking-content">
              {thinkingSteps.map((step, i) => (
                <div key={i} className="thinking-step">
                  <span className="step-dot" />
                  <span className="step-text">{step}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* 内容区 */}
      <div className="content-area">
        {/* 骨架屏：无内容且生成中 */}
        {showSkeleton && isStreaming && content.length === 0 && (
          <div className="skeleton-container">
            <div className="skeleton-line" style={{ width: '90%' }} />
            <div className="skeleton-line" style={{ width: '75%' }} />
            <div className="skeleton-line" style={{ width: '60%' }} />
            <div className="skeleton-line" style={{ width: '85%' }} />
            <div className="skeleton-paragraph" />
            <div className="waiting-hint">🌌 星尘正在穿越神经网络，请稍候...</div>
          </div>
        )}

        {/* 流式内容 */}
        {content.length > 0 && (
          <div className="stream-text">
            <span className="rendered">{content}</span>
            {isStreaming && <span className="cursor" />}
          </div>
        )}

        {/* 底部流光条：生成中且内容为空时的兜底 */}
        {isStreaming && content.length === 0 && !showSkeleton && (
          <div className="flow-bar" />
        )}
      </div>
    </div>
  );
};
```

**配套 CSS（StreamingMessage.css）**：

```css
/* 卡片基础 */
.message-card {
  background: #ffffff;
  border-radius: 16px;
  border: 1px solid rgba(99, 102, 241, 0.08);
  padding: 16px 20px;
  margin: 12px 0;
  transition: all 0.3s ease;
}

/* 生成中呼吸效果 */
.message-card.streaming-active {
  animation: card-breathe 3s ease-in-out infinite;
  border-color: rgba(99, 102, 241, 0.15);
}

@keyframes card-breathe {
  0%, 100% { box-shadow: 0 0 0 0 rgba(99, 102, 241, 0); }
  50% { box-shadow: 0 4px 24px -4px rgba(99, 102, 241, 0.12); }
}

/* 头部 */
.message-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  font-size: 13px;
}
.model-info {
  display: flex;
  align-items: center;
  gap: 8px;
}
.model-avatar {
  font-size: 16px;
}
.model-name {
  font-weight: 600;
  color: #1f2937;
}
.meta-info {
  color: #9ca3af;
  font-size: 12px;
  display: flex;
  gap: 12px;
}

/* 思考面板 */
.thinking-panel {
  background: rgba(99, 102, 241, 0.04);
  border: 1px solid rgba(99, 102, 241, 0.12);
  border-radius: 12px;
  margin-bottom: 12px;
  overflow: hidden;
}

.thinking-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  cursor: pointer;
  transition: background 0.2s;
}
.thinking-header:hover {
  background: rgba(99, 102, 241, 0.06);
}

.thinking-icon {
  width: 18px;
  height: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.thinking-title {
  font-size: 14px;
  font-weight: 500;
  color: #374151;
  flex: 1;
}

.thinking-status {
  font-size: 12px;
  color: #6366f1;
  background: rgba(99, 102, 241, 0.1);
  padding: 2px 10px;
  border-radius: 10px;
  transition: all 0.3s ease;
}
.thinking-status.active {
  animation: gentle-pulse 2s ease-in-out infinite;
}

.thinking-content {
  padding: 0 14px 12px 42px;
  font-size: 13px;
  line-height: 1.8;
  color: #6b7280;
}

.thinking-step {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin-bottom: 4px;
}

.step-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: #a855f7;
  margin-top: 8px;
  flex-shrink: 0;
}

/* 展开箭头动画 */
.arrow {
  transition: transform 0.2s ease;
  color: #9ca3af;
}
.arrow.open {
  transform: rotate(180deg);
}

/* 骨架屏 */
.skeleton-container {
  margin: 8px 0;
}

.skeleton-line {
  height: 16px;
  border-radius: 8px;
  margin-bottom: 12px;
  background: linear-gradient(90deg, 
    rgba(99,102,241,0.06) 0%, 
    rgba(168,85,247,0.12) 20%, 
    rgba(59,130,246,0.12) 40%, 
    rgba(168,85,247,0.12) 60%, 
    rgba(99,102,241,0.06) 80%
  );
  background-size: 300% 100%;
  animation: stardust-flow 2s ease-in-out infinite;
}

.skeleton-paragraph {
  height: 80px;
  border-radius: 8px;
  background: linear-gradient(90deg, 
    rgba(99,102,241,0.06) 0%, 
    rgba(168,85,247,0.12) 20%, 
    rgba(59,130,246,0.12) 40%, 
    rgba(168,85,247,0.12) 60%, 
    rgba(99,102,241,0.06) 80%
  );
  background-size: 300% 100%;
  animation: stardust-flow 2s ease-in-out infinite;
}

@keyframes stardust-flow {
  0% { background-position: 300% 0; }
  100% { background-position: -300% 0; }
}

/* 等待提示 */
.waiting-hint {
  text-align: center;
  font-size: 13px;
  color: #9ca3af;
  margin-top: 16px;
  animation: gentle-pulse 2s ease-in-out infinite;
}

@keyframes gentle-pulse {
  0%, 100% { opacity: 0.6; }
  50% { opacity: 1; }
}

/* 流式文字 */
.stream-text {
  font-size: 15px;
  line-height: 1.7;
  color: #374151;
}

.cursor {
  display: inline-block;
  width: 2px;
  height: 1.2em;
  background: linear-gradient(180deg, #6366f1, #a855f7);
  margin-left: 2px;
  vertical-align: text-bottom;
  animation: cursor-blink 1.1s step-end infinite;
}

@keyframes cursor-blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

/* 底部流光条 */
.flow-bar {
  height: 2px;
  width: 60%;
  margin: 16px auto 0;
  border-radius: 2px;
  background: linear-gradient(90deg, transparent, #6366f1, #a855f7, transparent);
  background-size: 200% 100%;
  animation: flow-move 1.5s linear infinite;
}

@keyframes flow-move {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

/* 空状态 */
.empty-state {
  text-align: center;
  padding: 48px 24px;
  color: #6b7280;
}
.empty-state.error .empty-icon {
  color: #f59e0b;
}

.empty-icon {
  font-size: 48px;
  margin-bottom: 16px;
  opacity: 0.8;
}

.empty-title {
  font-size: 16px;
  font-weight: 600;
  color: #374151;
  margin-bottom: 8px;
}

.empty-desc {
  font-size: 13px;
  line-height: 1.8;
  color: #9ca3af;
  margin-bottom: 24px;
}

.empty-actions {
  display: flex;
  gap: 12px;
  justify-content: center;
}

.btn-primary {
  background: linear-gradient(135deg, #6366f1, #a855f7);
  color: white;
  border: none;
  padding: 8px 20px;
  border-radius: 10px;
  font-size: 13px;
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
}
.btn-primary:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(99, 102, 241, 0.3);
}

.btn-secondary {
  background: transparent;
  color: #6b7280;
  border: 1px solid #e5e7eb;
  padding: 8px 20px;
  border-radius: 10px;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
}
.btn-secondary:hover {
  background: #f9fafb;
  border-color: #d1d5db;
}
```

---

## 七、给 CC 的修改提示词（直接复制）

```markdown
## 任务：AI助手聊天界面「全状态生成态」视觉重塑

### 禁止事项（零容忍）
1. 禁止任何时刻出现纯白色空白消息体
2. 禁止三个灰色圆点loading动画
3. 禁止思考面板展开后下方直接留白
4. 禁止空内容时只显示"系统内部错误"生硬的文字

### 必须实现

#### 1. 思考过程面板（Thinking Panel）优化
- 背景改为 `rgba(99, 102, 241, 0.04)`，边框 `rgba(99, 102, 241, 0.12)`
- 标题左侧灯泡改为渐变紫蓝 SVG 图标（不要默认emoji，用SVG可控制颜色）
- 展开时下方**必须紧跟骨架屏**，不能有空隙
- 思考中状态标签：`分析中...` 小标签，背景淡紫，圆角 pill
- 思考完成：标签变为 `已深度思考` + 步数
- 展开箭头添加旋转动画 `200ms ease`

#### 2. 骨架屏（Skeleton Screen）
- 4条流光脉冲线 + 1个段落块
- 配色：星尘紫蓝渐变流光，禁止纯灰色
- 动画：`stardust-flow 2s ease-in-out infinite`
- 每条线高度 `16px`，圆角 `8px`，间距 `12px`
- 宽度分别为 `90%, 75%, 60%, 85%`

#### 3. 流式生成（Streaming）
- 收到首个字符时，骨架屏 `300ms opacity` 渐隐
- 文字逐字浮现，末尾带渐变光标 `▍`（U+258D）
- 光标颜色：`linear-gradient(180deg, #6366F1, #A855F7)`
- 光标动画：`cursor-blink 1.1s step-end infinite`
- 生成完成时光标消失，卡片呼吸停止

#### 4. 卡片呼吸效果（生成中）
- 外发光：`box-shadow` 周期变化，3s ease-in-out infinite
- 边框颜色：从 `rgba(99,102,241,0.08)` 到 `0.25` 呼吸
- 生成完成后立即停止动画

#### 5. 空内容兜底（Empty State）
- 空内容时显示：🌌 图标 + "这片星域暂时没有回应"
- 说明文字：列出可能原因（知识边界/网络波动）
- 操作按钮：`重新生成`（主按钮，紫蓝渐变）、`换个问法`（次按钮）
- 错误态：显示错误代码 + 友好描述 + 重试/检查配置按钮

#### 6. 超长等待提示
- 如果骨架屏展示超过 2 秒仍未收到首字符：
- 在骨架屏下方显示：`🌌 星尘正在穿越神经网络，请稍候...`
- 字体 `13px`，灰色， gentle-pulse 动画

### 状态机要求
- 实现完整的五态流转：Thinking → Thinking+Streaming → Skeleton→Stream → Completed → Empty/Error
- 任何状态切换必须有过渡动画（opacity/transform），禁止闪切
- 思考面板与骨架屏/流式内容必须在同一个消息卡片内，禁止分离

### 文件范围
- 修改 AI 消息渲染组件（StreamingMessage / ChatMessage）
- 新增 ThinkingPanel 组件
- 新增 EmptyState 组件
- 新增/修改 CSS 动画文件

### 验收清单
- [ ] 思考面板展开后下方无留白，直接是骨架屏
- [ ] 骨架屏为紫蓝流光，不是纯灰
- [ ] 无三圆点动画残留
- [ ] 空内容时显示优雅空状态，不是空白
- [ ] 光标只在生成中时闪烁，完成后消失
- [ ] 卡片呼吸效果流畅，60fps
- [ ] 所有过渡动画自然，无卡顿
```

---

## 八、快速对照：改前 vs 改后

| 场景 | 改前 | 改后 |
|------|------|------|
| 思考中 | 灯泡+文字，下方空白 | 思考面板+脉冲骨架屏，星尘流光 |
| 思考完生成中 | 展开面板+空白+三圆点 | 折叠面板+流式文字+紫色光标 |
| 纯生成中 | 空白卡片+三圆点 | 呼吸卡片+流光骨架→逐字浮现 |
| 空内容 | 空白或"系统错误" | 🌌 优雅空状态+操作按钮 |
| 整体质感 | 廉价、焦虑 | 科技感、沉浸、星尘主题统一 |

---

## 九、效果描述

改完之后的效果大概是：

> 用户发完消息，右侧立刻出现用户气泡。左侧瞬间出现一张**边缘泛着微弱紫光的白色卡片**，卡片内部不是空白，而是**几条流光在缓缓流动**，像星尘在汇聚。  
> 如果模型在思考，上方展开一个淡紫色的思考面板，下方紧跟流光骨架屏。思考完成后面板自动折叠，第一个字"基"突然出现，后面跟着一个**紫色的小竖线在轻轻闪烁**。随着token不断到来，文字像打字机一样逐字延伸，竖线始终紧跟末尾。  
> 当生成结束，竖线消失，卡片边缘的微光也渐渐平息，Markdown格式瞬间渲染完成，一切归于宁静。  
> 如果模型返回空内容，卡片内不是死白，而是出现一颗🌌图标和温柔的文字："这片星域暂时没有回应"，配上两个操作按钮。  
>
> 这种"从星尘中凝结出文字"的感觉，才配得上平台的气质 🌠

---

*文档版本：v2.0*  
*生成日期：2026-07-05*  
*主题：星尘流动 · 渐进浮现*
