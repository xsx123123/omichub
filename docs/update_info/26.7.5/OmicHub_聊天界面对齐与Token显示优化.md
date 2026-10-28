# OmicHub 聊天界面对齐与 Token 显示优化方案

> **问题来源**: 用户反馈聊天界面输入框与消息内容未对齐，且缺少 Token 用量显示
> **参考原型**: 阿里云百炼(qwen) 聊天界面
> **修改范围**: 前端布局 + 消息元信息展示

---

## 一、问题诊断

### 1.1 当前问题

```
当前布局（问题示意）:
+-------------------------------------------------------------+
|  [AI消息] 你好！有什么我可以帮助你的吗？                     |
|                                                             |
|                                    [用户气泡] 哈哈哈        |  ← 用户消息右对齐
|                                                             |
|  [AI消息] 看来你今天心情不错呀！...                         |
|                                                             |
| +---------------------------------------------------------+ |
| | 向 代码助手 提问...                                      | |  ← 输入框占满宽度
| | [工具栏]                                    [发送]       | |  ← 和上面消息不对齐
| +---------------------------------------------------------+ |
+-------------------------------------------------------------+
```

### 1.2 参考图正确布局

```
阿里云百炼布局:
+-------------------------------------------------------------+
|  [AI消息] 你好，我是默认助手...                              |
|                                                             |
|                                    [用户气泡] R 有...       |  ← 右对齐，有边距
|                                    Tokens: 12 | 06/17 19:42 |  ← 元信息右对齐
|                                                             |
|  [AI消息] 是的，R 语言中确实有...                           |
|  Tokens: 1595 ↑21 ↓1574 | 06/17 19:42                       |  ← 元信息左对齐
|                                                             |
|                                    [输入框]                |  ← 输入框右侧边缘
|                                    和消息气泡右边缘对齐      |  ← 与上面消息对齐
+-------------------------------------------------------------+
```

---

## 二、修改方案

### 2.1 输入框宽度对齐

**核心思路**: 输入框不再占满整个底部宽度，而是和用户消息气泡的右边缘对齐，左侧留出和 AI 消息相同的边距。

#### 修改前 CSS

```css
/* 当前输入框 - 占满宽度 */
.chat-input-container {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  padding: 16px 24px;
  background: #fff;
  border-top: 1px solid #f0f0f0;
}

.chat-input-wrapper {
  width: 100%;
  max-width: none; /* 没有最大宽度限制 */
}
```

#### 修改后 CSS

```css
/* 修改后输入框 - 与消息内容对齐 */
.chat-input-container {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  padding: 16px 24px;
  background: #fff;
  border-top: 1px solid #f0f0f0;
  display: flex;
  justify-content: center; /* 居中容器 */
}

.chat-input-wrapper {
  width: 100%;
  max-width: calc(100% - 48px); /* 左右各留 24px 边距 */
  /* 或者更精确的对齐方式 */
  margin-left: 0;
  margin-right: auto;
}

/* 更好的方案：输入框和消息列表共用同一个内容区宽度 */
.chat-content-area {
  max-width: 900px; /* 或根据设计稿调整 */
  margin: 0 auto;
  padding: 0 24px;
  width: 100%;
}

.chat-input-container .chat-content-area {
  /* 输入框和内容区共用同一个宽度约束 */
  max-width: 900px;
  margin: 0 auto;
  width: 100%;
}
```

#### React 结构调整

```tsx
// 修改前
<div className="chat-page">
  <MessageList />
  <ChatInputContainer>  {/* 独立宽度 */}
    <ChatInput />
  </ChatInputContainer>
</div>

// 修改后
<div className="chat-page">
  {/* 消息列表和输入框共用同一个内容宽度约束 */}
  <div className="chat-content-area">
    <MessageList />
  </div>
  
  <ChatInputContainer>
    <div className="chat-content-area">  {/* 同样的宽度约束 */}
      <ChatInput />
    </div>
  </ChatInputContainer>
</div>
```

#### 对齐效果示意

```
+-------------------------------------------------------------+
|                                                             |
|  +-----------------------------------------------------+   |
|  |  [AI消息] 你好！有什么我可以帮助你的吗？              |   |  ← 左对齐
|  +-----------------------------------------------------+   |
|                                                             |
|  +-----------------------------------------------------+   |
|  |                                    [用户气泡] 哈哈哈 |   |  ← 右对齐
|  +-----------------------------------------------------+   |
|                                                             |
|  +-----------------------------------------------------+   |
|  |  [AI消息] 看来你今天心情不错呀！...                  |   |
|  +-----------------------------------------------------+   |
|                                                             |
|  +-----------------------------------------------------+   |
|  |  [输入框] 向 代码助手 提问...                        |   |  ← 和消息对齐
|  +-----------------------------------------------------+   |
|                                                             |
+-------------------------------------------------------------+
```

### 2.2 Token 用量显示

#### 显示位置

参考阿里云百炼，Token 信息放在每条消息的**元信息行**中，和用户名、时间戳同一行。

```tsx
// AI 消息元信息（左对齐）
<div className="message-meta ai">
  <span className="model-name">{message.model}</span>
  <span className="separator">|</span>
  <span className="timestamp">{formatTime(message.createdAt)}</span>
  <span className="separator">|</span>
  <span className="tokens">
    Tokens: {message.tokens.total}
    <span className="token-detail">
      ↑{message.tokens.input} ↓{message.tokens.output}
    </span>
  </span>
</div>

// 用户消息元信息（右对齐）
<div className="message-meta user">
  <span className="username">{user.name}</span>
  <span className="separator">|</span>
  <span className="timestamp">{formatTime(message.createdAt)}</span>
  <span className="separator">|</span>
  <span className="tokens">
    Tokens: {message.tokens.total}
  </span>
</div>
```

#### CSS 样式

```css
/* 消息元信息基础 */
.message-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #999;
  margin-bottom: 6px;
}

/* AI 消息元信息 - 左对齐 */
.message-meta.ai {
  justify-content: flex-start;
  padding-left: 36px; /* 和头像对齐 */
}

.message-meta.ai .model-name {
  font-weight: 500;
  color: #4A6CF7;
}

/* 用户消息元信息 - 右对齐 */
.message-meta.user {
  justify-content: flex-end;
  padding-right: 36px; /* 和头像对齐 */
}

.message-meta.user .username {
  font-weight: 500;
  color: #1a1a1a;
}

/* 分隔符 */
.message-meta .separator {
  color: #ddd;
  font-size: 10px;
}

/* Token 信息 */
.message-meta .tokens {
  display: flex;
  align-items: center;
  gap: 4px;
}

.message-meta .token-detail {
  color: #bbb;
  font-size: 11px;
}

/* Token 箭头图标（可选）*/
.message-meta .token-detail .arrow-up {
  color: #52c41a; /* 绿色 - 输入 */
}

.message-meta .token-detail .arrow-down {
  color: #1890ff; /* 蓝色 - 输出 */
}
```

#### 数据模型

```typescript
interface Message {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  
  // Token 用量（新增）
  tokens: {
    input: number;    // 输入 token 数（用户消息时为用户输入，AI 消息时为上下文+提示词）
    output: number;   // 输出 token 数（仅 AI 消息有）
    total: number;    // 总 token 数 = input + output
  };
  
  createdAt: string;
  model?: string;     // 实际使用的模型标识
}

// 后端返回示例
const messageResponse = {
  id: "msg_xxx",
  role: "assistant",
  content: "你好！有什么我可以帮助你的吗？",
  tokens: {
    input: 21,       // 上下文 + 系统提示 + 用户输入
    output: 1574,    // AI 生成的回复
    total: 1595
  },
  createdAt: "2026-07-05T16:45:00Z",
  model: "qwen3.7-plus"
};
```

---

## 三、完整消息组件代码

```tsx
import React from "react";
import { format } from "date-fns";
import { ArrowUp, ArrowDown } from "lucide-react";
import "./MessageItem.css";

interface TokenInfo {
  input: number;
  output: number;
  total: number;
}

interface Message {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  tokens: TokenInfo;
  createdAt: string;
  model?: string;
}

interface MessageItemProps {
  message: Message;
  user?: { name: string; avatar?: string };
  agent?: { name: string; icon: string };
}

const MessageItem: React.FC<MessageItemProps> = ({ message, user, agent }) => {
  const isUser = message.role === "user";
  
  const formatTime = (date: string) => {
    return format(new Date(date), "MM/dd HH:mm");
  };
  
  return (
    <div className={`message-item ${isUser ? "user" : "assistant"}`}>
      {/* 元信息行 */}
      <div className={`message-meta ${isUser ? "user" : "ai"}`}>
        {isUser ? (
          <>
            <span className="username">{user?.name || "我"}</span>
            <span className="separator">|</span>
            <span className="timestamp">{formatTime(message.createdAt)}</span>
            <span className="separator">|</span>
            <span className="tokens">
              Tokens: {message.tokens.total}
            </span>
          </>
        ) : (
          <>
            <span className="model-name">{message.model || agent?.name}</span>
            <span className="separator">|</span>
            <span className="timestamp">{formatTime(message.createdAt)}</span>
            <span className="separator">|</span>
            <span className="tokens">
              Tokens: {message.tokens.total}
              <span className="token-detail">
                <ArrowUp size={10} className="arrow-up" />
                {message.tokens.input}
                <ArrowDown size={10} className="arrow-down" />
                {message.tokens.output}
              </span>
            </span>
          </>
        )}
      </div>
      
      {/* 消息内容 */}
      <div className="message-body">
        <div className="avatar">
          {isUser ? (
            <div className="user-avatar">
              {user?.avatar ? (
                <img src={user.avatar} alt={user.name} />
              ) : (
                <span>{(user?.name || "我")[0]}</span>
              )}
            </div>
          ) : (
            <div className="agent-avatar">
              <span>{agent?.icon}</span>
            </div>
          )}
        </div>
        
        <div className={`message-content ${isUser ? "bubble" : "card"}`}>
          <MarkdownRenderer content={message.content} />
        </div>
      </div>
    </div>
  );
};

export default MessageItem;
```

```css
/* MessageItem.css */
.message-item {
  padding: 16px 0;
  transition: background 0.2s;
}

.message-item:hover {
  background: rgba(0, 0, 0, 0.005);
}

/* ===== 元信息行 ===== */
.message-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  margin-bottom: 6px;
}

.message-meta.ai {
  justify-content: flex-start;
  padding-left: 4px;
}

.message-meta.user {
  justify-content: flex-end;
  padding-right: 4px;
}

.message-meta .username {
  font-weight: 500;
  color: #1a1a1a;
}

.message-meta .model-name {
  font-weight: 500;
  color: #4A6CF7;
}

.message-meta .separator {
  color: #ddd;
  font-size: 10px;
}

.message-meta .timestamp {
  color: #999;
}

.message-meta .tokens {
  display: flex;
  align-items: center;
  gap: 4px;
  color: #999;
}

.message-meta .token-detail {
  display: flex;
  align-items: center;
  gap: 2px;
  margin-left: 4px;
  font-size: 11px;
  color: #bbb;
}

.message-meta .arrow-up {
  color: #52c41a;
}

.message-meta .arrow-down {
  color: #1890ff;
}

/* ===== 消息主体 ===== */
.message-body {
  display: flex;
  gap: 12px;
  align-items: flex-start;
}

.message-item.user .message-body {
  flex-direction: row-reverse;
}

/* 头像 */
.avatar {
  flex-shrink: 0;
}

.user-avatar,
.agent-avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 600;
}

.user-avatar {
  background: linear-gradient(135deg, #FF9A9E, #FECFEF);
  color: white;
}

.agent-avatar {
  background: linear-gradient(135deg, #667eea, #764ba2);
  color: white;
}

.user-avatar img {
  width: 100%;
  height: 100%;
  border-radius: 50%;
  object-fit: cover;
}

/* 消息内容 */
.message-content {
  max-width: 80%;
  word-break: break-word;
}

.message-content.bubble {
  padding: 12px 16px;
  background: linear-gradient(135deg, #4A6CF7, #6B4B96);
  color: white;
  border-radius: 16px 16px 4px 16px;
  font-size: 14px;
  line-height: 1.7;
  box-shadow: 0 2px 8px rgba(74, 108, 247, 0.2);
}

.message-content.card {
  padding: 16px 20px;
  background: #ffffff;
  border: 1px solid #f0f0f0;
  border-radius: 12px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
  font-size: 14px;
  line-height: 1.8;
  color: #1a1a1a;
}
```

---

## 四、输入框对齐修改

### 4.1 布局结构调整

```tsx
// ChatPage.tsx
const ChatPage = () => {
  return (
    <div className="chat-page">
      {/* 顶部栏 */}
      <ChatHeader />
      
      {/* 消息列表 - 共用内容区宽度 */}
      <div className="chat-scroll-area">
        <div className="chat-content-wrapper">
          <MessageList />
        </div>
      </div>
      
      {/* 输入框 - 同样的内容区宽度 */}
      <div className="chat-input-area">
        <div className="chat-content-wrapper">
          <ChatInput />
        </div>
      </div>
    </div>
  );
};
```

### 4.2 CSS 样式

```css
/* ChatPage.css */
.chat-page {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: #f5f5f5;
}

/* 共用内容宽度约束 */
.chat-content-wrapper {
  max-width: 900px; /* 根据设计稿调整 */
  margin: 0 auto;
  width: 100%;
  padding: 0 24px;
  box-sizing: border-box;
}

/* 消息列表区域 */
.chat-scroll-area {
  flex: 1;
  overflow-y: auto;
  padding: 20px 0;
}

/* 输入框区域 */
.chat-input-area {
  padding: 16px 0;
  background: #fff;
  border-top: 1px solid #f0f0f0;
  /* 关键：输入框和消息列表使用同样的 .chat-content-wrapper 宽度 */
}

/* 输入框样式 */
.chat-input {
  width: 100%;
  border: 1px solid #e0e0e0;
  border-radius: 16px;
  padding: 12px 16px;
  font-size: 14px;
  outline: none;
  transition: border-color 0.2s, box-shadow 0.2s;
  resize: none;
  min-height: 48px;
  max-height: 200px;
}

.chat-input:focus {
  border-color: #4A6CF7;
  box-shadow: 0 0 0 3px rgba(74, 108, 247, 0.1);
}
```

---

## 五、后端接口修改

后端需要在返回消息时带上 token 用量信息。

```typescript
// API 响应格式
interface ChatResponse {
  message: {
    id: string;
    role: "assistant";
    content: string;
    tokens: {
      input: number;
      output: number;
      total: number;
    };
    createdAt: string;
    model: string;
  };
}

// 如果后端暂不支持 token 统计，前端可以先用占位数据
const placeholderTokens = {
  input: 0,
  output: 0,
  total: 0,
};
```

---

## 六、修改清单

| 修改项 | 文件 | 说明 |
|--------|------|------|
| 输入框对齐 | ChatPage.css | 添加 `.chat-content-wrapper` 共用宽度约束 |
| 输入框对齐 | ChatPage.tsx | 消息列表和输入框包裹在同一个宽度容器内 |
| Token 显示 | MessageItem.tsx | 新增元信息行，显示用户名/模型名 + 时间 + Tokens |
| Token 显示 | MessageItem.css | 新增 `.message-meta` 样式，区分 user/ai 对齐方式 |
| 数据模型 | types/message.ts | 消息类型增加 `tokens` 字段 |
| 后端接口 | chat API | 返回消息时包含 `tokens` 用量 |

---

*文档由 OmicHub 设计委员会（阿姨）编制*