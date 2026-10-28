# OmicHub 聊天界面重构方案 v2.0

> **参考原型**: 阿里云百炼(qwen) 聊天界面
> **适配目标**: OmicHub 浅色主题 + 完整消息元信息 + 顶部模型切换
> **核心原则**: 用户消息和 AI 消息信息结构对齐，样式区分但不割裂

---

## 一、参考图核心设计模式拆解

```
+-------------------------------------------------------------+
| [模型选择器: qwen3.7-max | 阿里云百炼 ▼]        [设置] [历史] |  ← 顶部全局栏
+-------------------------------------------------------------+
|                                                             |
|  [系统提示] 你好，我是默认助手...                            |
|                                                             |
|                                    ZJ  [头像]               |  ← 用户身份区(右上)
|                           Tokens: 12 | 06/17 19:42          |  ← 用户元信息(右上)
|                +-------------------------------+            |
|                | R 有 system.file() 这个函数吗 |            |  ← 用户消息气泡(右对齐)
|                +-------------------------------+            |
|                           [重试] [编辑] [复制] [删除]       |  ← 用户操作按钮(右下)
|                                                             |
|  [头像] qwen3.7-max | 阿里云百炼                            |  ← AI 身份区(左上)
|  06/17 19:42 | Tokens: 1595 ↑21 ↓1574                       |  ← AI 元信息(左上)
|  +--------------------------------------------------------+ |
|  | [💡 已深度思考 (用时 16.1 秒) >]                       | |  ← 思考过程折叠区
|  +--------------------------------------------------------+ |
|  |                                                        | |
|  |  是的，R 语言中确实有 system.file() 这个函数...        | |  ← AI 内容卡片
|  |                                                        | |
|  +--------------------------------------------------------+ |
|                                                             |
+-------------------------------------------------------------+
```

---

## 二、OmicHub 适配方案（浅色主题）

### 2.1 全局布局调整

```tsx
// ChatPage 整体结构
<div className="chat-page">
  {/* 顶部全局模型切换栏 */}
  <ChatTopBar>
    <Breadcrumb>
      <span>AI 助手</span>
      <span> / </span>
      <span>{currentAgent.name}</span>
    </Breadcrumb>
    
    <ModelSelector>
      <ModelIcon model={currentModel} />
      <span>{currentModel.name}</span>
      <span className="model-provider">| {currentModel.provider}</span>
      <ChevronDown size={14} />
    </ModelSelector>
    
    <TopBarActions>
      <Button icon={<Settings size={16} />} />
      <Button icon={<History size={16} />} />
    </TopBarActions>
  </ChatTopBar>
  
  {/* 消息列表区 */}
  <MessageList ref={scrollRef}>
    {messages.map(msg => (
      <MessageItem key={msg.id} message={msg} />
    ))}
  </MessageList>
  
  {/* 输入区 */}
  <ChatInput />
</div>
```

### 2.2 顶部模型切换栏（新增）

```css
/* ChatTopBar 样式 */
.chat-top-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 20px;
  border-bottom: 1px solid #f0f0f0;
  background: #ffffff;
  position: sticky;
  top: 0;
  z-index: 100;
}

.chat-top-bar .breadcrumb {
  font-size: 14px;
  color: #666;
}

.chat-top-bar .breadcrumb span:last-child {
  font-weight: 600;
  color: #1a1a1a;
}

/* 模型选择器 */
.model-selector {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 14px;
  border-radius: 20px;
  background: #f5f5f5;
  border: 1px solid #e8e8e8;
  cursor: pointer;
  transition: all 0.2s;
  font-size: 13px;
}

.model-selector:hover {
  background: #eeeeee;
  border-color: #d0d0d0;
}

.model-selector .model-icon {
  width: 20px;
  height: 20px;
  border-radius: 4px;
}

.model-selector .model-name {
  font-weight: 500;
  color: #1a1a1a;
}

.model-selector .model-provider {
  color: #999;
  font-size: 12px;
}

.model-selector .dropdown-arrow {
  color: #999;
  transition: transform 0.2s;
}

.model-selector.open .dropdown-arrow {
  transform: rotate(180deg);
}
```

### 2.3 消息项通用结构（信息对齐）

```tsx
// MessageItem 组件
const MessageItem = ({ message }) => {
  const isUser = message.role === "user";
  
  return (
    <div className={`message-item ${isUser ? "user" : "assistant"}`}>
      {/* 身份区 + 元信息 */}
      <div className="message-header">
        <div className="message-identity">
          <Avatar 
            src={isUser ? user.avatar : agent.icon}
            fallback={isUser ? user.name[0] : agent.name[0]}
            className={isUser ? "user-avatar" : "agent-avatar"}
          />
          <span className="message-name">
            {isUser ? user.name : agent.name}
          </span>
        </div>
        <div className="message-meta">
          <span className="tokens">Tokens: {message.tokens}</span>
          <span className="separator">|</span>
          <span className="timestamp">{formatTime(message.createdAt)}</span>
        </div>
      </div>
      
      {/* AI 专属：思考过程折叠区 */}
      {!isUser && message.thinking && (
        <ThinkingProcess 
          content={message.thinking}
          duration={message.thinkingDuration}
        />
      )}
      
      {/* 消息内容 */}
      <div className={`message-content ${isUser ? "bubble" : "card"}`}>
        <MarkdownRenderer content={message.content} />
      </div>
      
      {/* 操作按钮（hover 出现）*/}
      <div className="message-actions">
        {isUser ? (
          <>
            <ActionButton icon={<RefreshCw size={14} />} tooltip="重新发送" />
            <ActionButton icon={<Edit3 size={14} />} tooltip="编辑" />
            <ActionButton icon={<Copy size={14} />} tooltip="复制" />
            <ActionButton icon={<Trash2 size={14} />} tooltip="删除" />
          </>
        ) : (
          <>
            <ActionButton icon={<RefreshCw size={14} />} tooltip="重新生成" />
            <ActionButton icon={<Copy size={14} />} tooltip="复制" />
            <ActionButton icon={<Volume2 size={14} />} tooltip="朗读" />
            <ActionButton icon={<ThumbsUp size={14} />} tooltip="点赞" />
            <ActionButton icon={<ThumbsDown size={14} />} tooltip="点踩" />
          </>
        )}
      </div>
    </div>
  );
};
```

### 2.4 用户消息样式（右对齐气泡）

```css
/* 消息项基础 */
.message-item {
  padding: 20px 24px;
  transition: background 0.2s;
}

.message-item:hover {
  background: rgba(0, 0, 0, 0.01);
}

/* 用户消息布局：右对齐 */
.message-item.user {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
}

/* 用户消息头部（右对齐）*/
.message-item.user .message-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 6px;
  flex-direction: row-reverse; /* 头像在右，名称在左 */
}

.message-item.user .message-identity {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-direction: row-reverse;
}

.message-item.user .user-avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: linear-gradient(135deg, #FF9A9E, #FECFEF);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 12px;
  font-weight: 600;
}

.message-item.user .message-name {
  font-size: 13px;
  font-weight: 600;
  color: #1a1a1a;
}

.message-item.user .message-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 11px;
  color: #999;
}

.message-item.user .message-meta .separator {
  color: #ddd;
}

/* 用户消息气泡 */
.message-item.user .message-content.bubble {
  max-width: 80%;
  padding: 12px 16px;
  background: linear-gradient(135deg, #4A6CF7, #6B4B96);
  color: white;
  border-radius: 16px 16px 4px 16px; /* 左下角尖角 */
  font-size: 14px;
  line-height: 1.7;
  box-shadow: 0 2px 8px rgba(74, 108, 247, 0.2);
  word-break: break-word;
}

/* 用户消息操作按钮（右对齐）*/
.message-item.user .message-actions {
  display: flex;
  gap: 4px;
  margin-top: 8px;
  opacity: 0;
  transition: opacity 0.2s;
}

.message-item.user:hover .message-actions {
  opacity: 1;
}
```

### 2.5 AI 消息样式（左对齐卡片）

```css
/* AI 消息布局：左对齐 */
.message-item.assistant {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
}

/* AI 消息头部（左对齐）*/
.message-item.assistant .message-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 6px;
}

.message-item.assistant .message-identity {
  display: flex;
  align-items: center;
  gap: 8px;
}

.message-item.assistant .agent-avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: linear-gradient(135deg, #667eea, #764ba2);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 12px;
}

.message-item.assistant .message-name {
  font-size: 13px;
  font-weight: 600;
  color: #4A6CF7; /* 品牌蓝色 */
}

.message-item.assistant .message-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 11px;
  color: #999;
}

/* AI 消息内容卡片 */
.message-item.assistant .message-content.card {
  max-width: 90%;
  padding: 16px 20px;
  background: #ffffff;
  border: 1px solid #f0f0f0;
  border-radius: 12px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
  font-size: 14px;
  line-height: 1.8;
  color: #1a1a1a;
}

/* AI 消息操作按钮（左对齐）*/
.message-item.assistant .message-actions {
  display: flex;
  gap: 4px;
  margin-top: 8px;
  opacity: 0;
  transition: opacity 0.2s;
}

.message-item.assistant:hover .message-actions {
  opacity: 1;
}
```

### 2.6 思考过程折叠区（AI 专属）

```tsx
const ThinkingProcess = ({ content, duration }) => {
  const [expanded, setExpanded] = useState(false);
  
  return (
    <div className="thinking-process">
      <div 
        className="thinking-header"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="thinking-icon">💡</div>
        <span className="thinking-title">
          {expanded ? "思考过程" : `已深度思考（用时 ${duration} 秒）`}
        </span>
        <ChevronRight 
          size={16}
          className={`thinking-arrow ${expanded ? "expanded" : ""}`}
        />
      </div>
      {expanded && (
        <div className="thinking-content">
          <pre>{content}</pre>
        </div>
      )}
    </div>
  );
};
```

```css
.thinking-process {
  width: 90%;
  margin-bottom: 8px;
}

.thinking-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  background: #f8f9ff;
  border: 1px solid #e8ecff;
  border-radius: 10px;
  cursor: pointer;
  transition: background 0.2s;
  font-size: 13px;
  color: #4A6CF7;
}

.thinking-header:hover {
  background: #f0f3ff;
}

.thinking-icon {
  font-size: 16px;
}

.thinking-title {
  flex: 1;
  font-weight: 500;
}

.thinking-arrow {
  transition: transform 0.2s;
  color: #999;
}

.thinking-arrow.expanded {
  transform: rotate(90deg);
}

.thinking-content {
  padding: 12px 16px;
  background: #fafbff;
  border: 1px solid #e8ecff;
  border-top: none;
  border-radius: 0 0 10px 10px;
  font-size: 13px;
  color: #666;
  line-height: 1.7;
  max-height: 300px;
  overflow-y: auto;
}

.thinking-content pre {
  white-space: pre-wrap;
  word-break: break-word;
  margin: 0;
  font-family: inherit;
}
```

### 2.7 操作按钮组件

```tsx
const ActionButton = ({ icon, tooltip, onClick }) => (
  <button 
    className="action-btn"
    onClick={onClick}
    title={tooltip}
  >
    {icon}
  </button>
);
```

```css
.action-btn {
  width: 28px;
  height: 28px;
  border-radius: 6px;
  border: none;
  background: transparent;
  color: #bbb;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}

.action-btn:hover {
  background: #f0f0f0;
  color: #666;
}

.message-item.user .action-btn:hover {
  background: rgba(255, 255, 255, 0.2);
  color: white;
}
```

---

## 三、数据模型扩展

每条消息需要新增字段：

```typescript
interface Message {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  
  // 新增字段
  tokens: {
    input: number;   // 输入 token 数
    output: number;  // 输出 token 数
    total: number;   // 总 token 数
  };
  createdAt: string;  // ISO 时间戳
  
  // AI 专属
  thinking?: string;           // 思考过程内容
  thinkingDuration?: number;    // 思考用时（秒）
  model?: string;              // 实际使用的模型
  
  // 用户专属
  edited?: boolean;            // 是否被编辑过
  editHistory?: string[];      // 编辑历史
}
```

---

## 四、与现有代码的对比修改点

| 修改项 | 修改前 | 修改后 |
|--------|--------|--------|
| **模型切换位置** | 聊天头部小标签 | 顶部全局模型选择器（下拉）|
| **用户消息样式** | 蓝色气泡，无头像 | 渐变紫气泡，有头像+用户名+时间+Tokens |
| **AI 消息样式** | 白色卡片，有头像 | 白色卡片，有头像+模型名+时间+Tokens+思考折叠 |
| **操作按钮** | 仅在 AI 消息下方 | 用户和 AI 消息都有，hover 出现 |
| **消息元信息** | 几乎无 | 完整的 Tokens、时间戳、模型标识 |
| **思考过程** | 无 | AI 消息可折叠展示思考过程（预留）|

---

## 五、实施建议

1. **先改布局**：把模型切换从聊天头部移到顶部全局栏，这是结构性改动
2. **再改消息组件**：统一 MessageItem 组件，支持两种布局模式（user/assistant）
3. **后端配合**：需要后端返回 `tokens`、`createdAt`、`model` 等字段
4. **思考过程**：可以先做 UI 占位，等 Agent 架构上线后填充真实数据

---

*文档由 OmicHub 设计委员会（阿姨）编制*