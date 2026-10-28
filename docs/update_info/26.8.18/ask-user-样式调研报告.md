# AskUser 样式调研报告

## 概述

本文档调研了平台中 `ask_user` 澄清工具的当前实现样式，并与 Kimi 的询问样式进行对比分析。

---

## 一、Kimi 的 AskUser 样式（参考样式）

### 1.1 视觉特征

从参考截图 (`docs/info/26.8.18/image copy 4.png`) 观察，Kimi 的询问样式具有以下特点：

| 特征 | 描述 |
|------|------|
| **位置** | 悬浮于输入框上方，覆盖在聊天内容之上 |
| **动画** | 从输入框底部向上弹出（slide-up 动画） |
| **形态** | 独立的浮层卡片，不与消息气泡混排 |
| **视觉层级** | 高优先级，吸引用户注意力 |
| **交互焦点** | 用户必须在此卡片上完成选择/输入才能继续 |

### 1.2 交互流程

```
┌─────────────────────────────────────────┐
│  聊天消息区域                            │
│  (被浮层卡片部分遮挡)                    │
│                                         │
│  ┌───────────────────────────────────┐  │
│  │  问题文本                          │  │
│  │  ○ 选项 1                          │  │
│  │  ○ 选项 2 (推荐)                   │  │
│  │  ○ 选项 3                          │  │
│  │  ✎ 其他                            │  │
│  │                                    │  │
│  │              [跳过 Esc]  [发送 →]  │  │
│  └───────────────────────────────────┘  │
│                                         │
│  ┌───────────────────────────────────┐  │
│  │  输入框                            │  │
│  └───────────────────────────────────┘  │
─────────────────────────────────────────┘
```

### 1.3 核心优势

1. **视觉突出**：浮层设计让询问卡片成为视觉焦点
2. **动效引导**：从输入框弹出的动画暗示"这是输入框的延伸"
3. **交互清晰**：用户明确知道需要在此完成选择
4. **空间高效**：不占用消息流空间，聊天历史保持完整

---

## 二、平台当前 AskUser 实现

### 2.1 组件架构

```
frontend/src/components/ai-chat/
├── AskUserCard.vue      # 核心交互卡片组件
├── AskUserModal.vue     # 模态框包装器（Studio 场景使用）
── KimiMessageItem.vue  # 消息渲染组件（内嵌 AskUserCard）
```

### 2.2 当前样式特征

| 特征 | 描述 |
|------|------|
| **位置** | 嵌入在 AI 回复消息气泡内部 |
| **动画** | 无特殊动画，随消息流自然出现 |
| **形态** | 消息卡片的一部分，与正文内容混排 |
| **视觉层级** | 中等，与消息内容同级 |
| **交互焦点** | 用户可在卡片内操作，但非强制焦点 |

### 2.3 代码位置

**AskUserCard.vue** (`frontend/src/components/ai-chat/AskUserCard.vue`)

- 未回答状态：分页问题向导（选项点选 / "其他"自由输入 / 跳过 Esc / 下一步或提交）
- 已回答状态：折叠为工具卡片样式（"询问工具 | 已收集信息"），展开可回看问答

**渲染位置** (`KimiMessageItem.vue:1267`)

```vue
<!-- Studio ask_user 澄清卡片：分页交互收集 -->
<AskUserCard
  v-else-if="message.askRequest"
  :ask="message.askRequest"
  @submit="handleAskSubmit"
/>
```

### 2.4 样式细节

```scss
.ask-user-card {
  width: 100%;
  margin-top: 10px;
  padding: 14px 16px;
  background: var(--chat-ai-card, var(--neutral-card));
  border: 1px solid var(--chat-accent-border, ...);
  border-radius: 12px;
  box-shadow: var(--chat-shadow-sm, var(--shadow-card));
}
```

### 2.5 交互流程

```
┌─────────────────────────────────────────┐
│  AI 消息气泡                             │
│  ┌───────────────────────────────────┐  │
│  │  AI 回复正文内容...                │  │
│  │                                   │  │
│  │  ┌─────────────────────────────┐  │  │
│  │  │  问题文本                    │  │  │
│  │  │  ○ 选项 1                    │  │  │
│  │  │  ○ 选项 2                    │  │  │
│  │  │  ✎ 其他                      │  │  │
│  │  │          [跳过]  [下一步 →]  │  │  │
│  │  └─────────────────────────────┘  │  │
│  │                                   │  │
│  │  [点赞] [点踩] [复制]             │  │
│  └───────────────────────────────────┘  │
│                                         │
│  ┌───────────────────────────────────┐  │
│  │  输入框                            │  │
│  ───────────────────────────────────┘  │
└─────────────────────────────────────────┘
```

---

## 三、两种样式对比

### 3.1 视觉对比

| 维度 | Kimi 样式 | 平台当前样式 |
|------|-----------|--------------|
| 位置 | 输入框上方浮层 | AI 消息气泡内部 |
| 动画 | 从输入框底部弹出 | 无特殊动画 |
| 视觉层级 | 高（覆盖层） | 中（消息内容） |
| 空间占用 | 不占用消息流 | 占用消息流空间 |
| 焦点引导 | 强（必须交互） | 弱（可滚动跳过） |

### 3.2 交互对比

| 维度 | Kimi 样式 | 平台当前样式 |
|------|-----------|--------------|
| 用户感知 | "需要我回答这个问题" | "AI 提供了一个可选的交互卡片" |
| 操作路径 | 直接在浮层上选择 | 需要在消息流中找到卡片 |
| 完成感 | 明确（关闭浮层即完成） | 模糊（卡片折叠即完成） |
| 历史回看 | 浮层关闭后不可见 | 卡片保留在消息历史中 |

### 3.3 技术实现对比

| 维度 | Kimi 样式（推测） | 平台当前样式 |
|------|-------------------|--------------|
| DOM 位置 | 输入框容器的子元素 | 消息列表的子元素 |
| 定位方式 | `position: absolute` 或 `fixed` | 文档流内正常布局 |
| 动画实现 | CSS transition/animation | 无 |
| 状态管理 | 全局/输入框级状态 | 消息级状态 (`message.askRequest`) |

---

## 四、平台 AskUser 数据结构

### 4.1 类型定义

```typescript
// 单个问题
interface AskQuestion {
  question: string
  options?: string[]  // 可点选的互斥选项
}

// 澄清请求
interface AskRequest {
  kind?: 'questions' | 'plan_confirmation'
  questions: AskQuestion[]
  planConfirmation?: PlanConfirmation  // kind=plan_confirmation 时存在
  answers?: string[]  // 用户按问题顺序给出的答案
  answered?: boolean  // 是否已回答
}
```

### 4.2 消息集成

```typescript
interface ChatMessage {
  // ... 其他字段
  askRequest?: AskRequest  // Studio ask_user 澄清卡片（AI 消息专属）
}
```

---

## 五、当前实现的优点

1. **历史可追溯**：询问卡片保留在消息历史中，用户可随时回看
2. **折叠展示**：已回答的问题折叠为摘要，不占用过多空间
3. **分页支持**：支持多问题分页收集，避免单次信息过载
4. **灵活输入**：支持选项点选和"其他"自由输入两种模式
5. **键盘友好**：支持 Esc 跳过、方向键导航

---

## 六、改进建议

### 6.1 方案 A：采用 Kimi 浮层样式

**优点**：
- 视觉更突出，用户感知更强
- 动效引导更自然
- 不占用消息流空间

**缺点**：
- 需要重构 DOM 结构（从消息内移到输入框容器）
- 历史回看需要额外处理（浮层关闭后如何查看）
- 多问题分页时浮层高度管理复杂

**实现要点**：
```vue
<!-- 在输入框容器中添加浮层 -->
<div class="chat-input-container">
  <AskUserFloatingCard
    v-if="pendingAsk"
    :ask="pendingAsk"
    @submit="handleAskSubmit"
  />
  <ChatInput />
</div>
```

### 6.2 方案 B：混合样式（推荐）

保留当前消息内嵌样式，但增加以下改进：

1. **添加出现动画**：卡片出现时添加 slide-up 动画
2. **高亮边框**：未回答时添加脉冲边框动画
3. **自动滚动**：卡片出现时自动滚动到可视区域
4. **输入框联动**：卡片出现时输入框显示提示文字

**实现要点**：
```scss
.ask-user-card {
  animation: ask-card-slide-up 0.3s ease-out;
  
  &:not(.answered) {
    border-color: var(--chat-accent);
    box-shadow: 0 0 0 2px var(--chat-accent-light);
    animation: ask-card-pulse 2s ease-in-out infinite;
  }
}

@keyframes ask-card-slide-up {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
```

### 6.3 方案 C：保持现状

当前样式已经功能完整，如果用户没有强烈反馈，可以保持现状。

---

## 七、相关文件清单

| 文件 | 用途 |
|------|------|
| `frontend/src/components/ai-chat/AskUserCard.vue` | 核心交互卡片组件 |
| `frontend/src/components/ai-chat/AskUserModal.vue` | 模态框包装器 |
| `frontend/src/components/ai-chat/KimiMessageItem.vue` | 消息渲染（内嵌 AskUserCard） |
| `frontend/src/components/ai-chat/types.ts` | 类型定义（AskRequest, AskQuestion） |
| `frontend/src/views/StudioView.vue` | Studio 场景使用 AskUserModal |
| `frontend/src/stores/agentHub.ts` | 状态管理（answerAskRequest） |
| `frontend/src/composables/useAgentChatStream.ts` | 流式处理中解析 ask_user |

---

## 八、总结

| 项目 | 结论 |
|------|------|
| 当前样式 | 消息内嵌卡片，功能完整但视觉优先级较低 |
| Kimi 样式 | 输入框上方浮层，视觉突出且有动效引导 |
| 推荐方案 | 方案 B（混合样式）：保留当前架构，增加动画和高亮 |
| 优先级 | 中（功能已可用，样式优化为锦上添花） |

---

## 附录：AskUserCard 组件功能清单

### 未回答状态
- [x] 分页问题展示（‹ 1/1 ›）
- [x] 选项点选（含"推荐"标注排序）
- [x] "其他"自由输入
- [x] 跳过当前题（Esc 快捷键）
- [x] 下一步/提交按钮
- [x] 键盘导航支持

### 已回答状态
- [x] 折叠为工具卡片样式
- [x] 显示"询问工具 | 已收集信息"
- [x] 点击展开回看问答
- [x] 限高 220px 内部滚动
