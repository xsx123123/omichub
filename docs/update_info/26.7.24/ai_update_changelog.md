# OmicHub AI 助手交互体验优化 — 实施记录

> **日期**：2026-07-24 ~ 2026-07-25
>
> **分支**：`feat/ai-assistant-ux-optimization`
>
> **基线文档**：[ai_update.md](./ai_update.md)（优化方案 v1.0）、`ARCHITECTURE_DESIN/fontend.md`（前端设计规范）
>
> **验证状态**：`vue-tsc --noEmit` ✅ | `vite build` ✅

---

## 一、变更文件清单

| 文件 | 操作 | 对应功能 |
|------|------|----------|
| `frontend/src/components/ai-chat/McpToolCallCard.vue` | **新增** | 2.1 MCP 工具调用折叠 |
| `frontend/src/components/ai-chat/ApprovalDrawer.vue` | **新增** | 2.3 审批底部抽屉 |
| `frontend/src/config/aiIntents.ts` | **新增** | 2.5 工作台意图匹配 |
| `frontend/src/components/ai-chat/KimiMessageItem.vue` | 修改 | 2.1 / 2.4 |
| `frontend/src/components/ai-chat/KimiMessageList.vue` | 修改 | 2.4 |
| `frontend/src/components/ai-chat/KimiChatInput.vue` | 修改 | 2.2 / 2.5 |
| `frontend/src/composables/useAgentChatStream.ts` | 修改 | 2.2 |
| `frontend/src/stores/agentHub.ts` | 修改 | 2.2 |
| `frontend/src/layouts/DefaultLayout.vue` | 修改 | 2.6 |
| `frontend/src/styles/global.css` | 修改 | 2.4 |

---

## 二、功能实施详情

### 2.1 MCP 工具调用默认折叠

**方案**：将 `KimiMessageItem.vue` 中内联的 `.tool-card` 逻辑（参数展示、结果展示、确认卡、跳转卡、任务进度卡）整体抽为独立组件 `McpToolCallCard.vue`。

**实现要点**：

- `collapsed = ref(true)` 默认折叠，折叠态单行展示：`BuildOutline` 图标 + 工具名 + `NTag`（MCP 服务器）+ 状态标签 + `ChevronForwardOutline` 旋转箭头。
- 状态标签语义色映射：

  | 状态 | NTag type | 文案 |
  |------|-----------|------|
  | `success` | `success` | 成功 |
  | `error` | `error` | 失败 |
  | `awaiting_approval` | `warning` | 等待批准 |
  | `running` | `info` | 执行中 |
  | `pending` | `default` | 等待中 |

- 展开态保留原有完整参数 JSON（`<pre>` 格式化）+ 结果 + 二次确认卡 + open_page 引导卡 + PipelineTaskCard / TaskProgressCard。
- 箭头动画：`transform: rotate(90deg)`，`transition: transform var(--motion-quick) ease-out`（140ms）。
- 可访问性：标题行 `role="button"` + `tabindex="0"` + `:aria-expanded`，支持 `Enter` / `Space` 键盘切换。
- `prefers-reduced-motion: reduce` 下移除箭头旋转和展开过渡动画。

**KimiMessageItem.vue 变更**：

- 新增 `import McpToolCallCard`，模板中 `<div v-else class="tool-card">` 整块替换为 `<McpToolCallCard v-else :tool="tool" @confirm-tool @open-tool-page @generate-visualization @adjust-parameters />`。
- 移除不再使用的 `BuildOutline` 图标导入。
- 移除已迁移至 McpToolCallCard 的 CSS：`.tool-card`、`.tool-header`、`.server-tag`、`.status-tag`、`.tool-section-title`、`.tool-args pre`、`.tool-content pre`、`.confirm-card` 系列、`.open-page-card` 系列。
- `ApprovalCard`、`StudioCodeCard`、`MasPlanPreviewCard`、`artifact_register` 等特殊卡片的渲染分支不变。

---

### 2.2 暂停 AI 流式回复

**方案**：在 `useAgentChatStream` 组合式函数中新增暂停语义，通过 `KimiChatInput` 的按钮状态切换暴露给用户。

**useAgentChatStream.ts 变更**：

```typescript
// 新增状态
const isPaused = ref(false)

// streamChat 入口重置暂停态
isPaused.value = false

// 新增方法
function pauseStream(): void {
  abortController.value?.abort()
  isStreaming.value = false
  isPaused.value = true        // 标记暂停，保留已输出文本
}

function resetPause(): void {
  isPaused.value = false
}

// abortStream 同步重置暂停态
function abortStream(): void {
  abortController.value?.abort()
  isStreaming.value = false
  isPaused.value = false
}

return { isStreaming, isPaused, streamChat, abortStream, pauseStream, resetPause }
```

**agentHub.ts 变更**：

- 解构新增 `isPaused, pauseStream, resetPause`。
- 新增 `pauseStreaming()` 方法：调用 `pauseStream()`，将当前 AI 消息的 `content` 保留为 `streamingContent`，状态维持 `streaming`。
- `return` 导出新增 `isPaused`、`pauseStreaming`。

**KimiChatInput.vue 变更**：

- 新增 Props：`isStreaming?: boolean`、`isPaused?: boolean`。
- 新增 Emits：`pause`、`resume`、`regenerate`。
- 发送按钮区域三态切换：

  | 状态 | 按钮 | 样式 |
  |------|------|------|
  | 流式中 (`isStreaming`) | ⏸ 暂停（`PauseOutline`） | 橙色底 + 脉冲动画 `pause-pulse 1.6s` |
  | 已暂停 (`isPaused`) | ▶ 继续（`PlayOutline`）+ ↻ 重新生成（`RefreshOutline`） | 继续=绿色底，重新生成=默认底 |
  | 默认 | ↑ 发送（`ArrowUpOutline`） | 品牌渐变底 |

- 底部提示行：暂停时显示橙色 `生成已暂停`，否则显示 `siteConfigStore.aiInputHint`。
- `prefers-reduced-motion` 下移除暂停按钮脉冲动画。

**父组件接入方式**（AIChatView / StudioView 需配合）：

```vue
<KimiChatInput
  :is-streaming="agentHubStore.isStreaming"
  :is-paused="agentHubStore.isPaused"
  @pause="agentHubStore.pauseStreaming()"
  @resume="agentHubStore.sendMessage(lastUserContent)"
  @regenerate="handleRegenerate"
/>
```

---

### 2.3 审批弹窗底部抽屉

**方案**：新建 `ApprovalDrawer.vue`，使用 `NDrawer placement="bottom"` 替代对话流内嵌的审批交互，提供更宽敞的预览空间。

**实现要点**：

- `v-model:show` 控制可见性（遵循设计文档 §5.6 弹窗约定）。
- 高度：桌面端 `60vh`，移动端 `@media (max-width: 768px)` 覆盖为 `80vh`。
- 圆角顶部：`:deep(.n-drawer) { border-radius: 16px 16px 0 0 }`。
- 遮罩点击关闭（`mask-closable`），等同拒绝。
- 内容区结构：
  1. 标题栏：`ShieldCheckmarkOutline` 图标 + 操作类型 + 状态 `NTag`。
  2. 风险提示（`approval.risk_hint`）。
  3. 影响文件路径（`NTag` 标签 + 语言标签）。
  4. 代码/内容预览（`<pre>` 等宽字体，`max-height: 30vh`，可滚动）。
- 操作按钮：批准运行（`type="primary"`）、编辑后运行（`secondary`）、拒绝（`quaternary type="error"`）。
- 焦点管理：`watch(show)` 打开时 `nextTick(() => approveBtnRef.value?.focus())`。
- 异步审批期间 `:loading="submitting"` 防重复提交。
- 调用 `agentHubStore.approveToolCall()` / `rejectToolCall()`，成功/失败均有 `useMessage()` 反馈。

**与 ApprovalCard 的关系**：`ApprovalCard.vue` 保留不删除，`KimiMessageItem` 中 `tool.approval` 仍渲染 `ApprovalCard`（对话流内终态徽标）。`ApprovalDrawer` 作为增强交互层，由父组件（如 StudioView）在收到 `approval_request` 事件时按需打开，两者可共存。

---

### 2.4 AI 回复气泡宽度对齐

**方案**：新增全局 CSS 变量 `--chat-content-max-width`，统一消息列表和输入框的最大宽度。

**global.css 变更**：

```css
:root {
  /* ===== AI 对话内容宽度（消息列表与输入框共享）===== */
  --chat-content-max-width: 860px;
}
```

**KimiMessageList.vue 变更**：

```css
/* 之前 */
max-width: 900px;

/* 之后 */
max-width: var(--chat-content-max-width, 860px);
```

**KimiMessageItem.vue 变更**：

- AI 气泡：`max-width: 90%` → `max-width: min(100% - 48px, var(--chat-content-max-width, 860px))`，宽屏下与输入框等宽，窄屏保留 48px 左右边距。
- 用户气泡：`max-width: 80%` → `max-width: 70%`，与 AI 消息形成视觉区分。
- 新增 Markdown 表格/代码块横向滚动：

```css
.kimi-message-item.assistant :deep(.markdown-body table),
.kimi-message-item.assistant :deep(.markdown-body pre) {
  overflow-x: auto;
  min-width: 320px;
  max-width: 100%;
}
```

---

### 2.5 自动切换工作台模式

**方案**：新建 `frontend/src/config/aiIntents.ts` 集中维护触发关键词，在 `KimiChatInput.handleSend()` 中进行意图匹配。

**aiIntents.ts 内容**：

```typescript
export const WORKBENCH_VERBS = [
  '生成', '创建', '编写', '制作', '输出', '分析',
  '构建', '撰写', '设计', '整理',
]

export const WORKBENCH_NOUNS = [
  '文档', '模板', '脚本', '报告', '文件', '流程',
  '方案', '计划', '图表', '代码', '笔记', '总结',
]

export function matchWorkbenchIntent(text: string): boolean {
  const hasVerb = WORKBENCH_VERBS.some((v) => text.includes(v))
  const hasNoun = WORKBENCH_NOUNS.some((n) => text.includes(n))
  return hasVerb && hasNoun
}
```

**KimiChatInput.vue 变更**：

- `handleSend()` 中调用 `matchWorkbenchIntent(content)`。
- 命中时：`message.info('已为您切换至工作台模式，便于跟踪任务进度')`。
- `emit('send', content, { ..., workbenchIntent })` 将意图标记透传给父组件。
- 不强制、不阻断：用户可手动切回对话模式。

**父组件接入方式**（AIChatView 需配合）：

```typescript
function handleSend(content: string, options: SendOptions) {
  if (options.workbenchIntent) {
    // 切换到工作台模式（如路由跳转 /studio 或设置 mode: 'workbench'）
  }
  agentHubStore.sendMessage(content, options)
}
```

---

### 2.6 AI 工作台自动折叠侧边栏

**方案**：在 `DefaultLayout.vue` 现有路由驱动折叠逻辑基础上，扩展支持 `/studio` 和 `/ai` 路径自动折叠，并通过 `localStorage` 实现手动锁定。

**DefaultLayout.vue 变更**：

```typescript
// 新增状态
const sidebarLocked = ref<string | null>(localStorage.getItem('omichub:sidebar-locked'))
const autoCollapsePages = ['/studio', '/ai']
```

路由监听扩展（与现有 `autoCollapseSidebar` meta 合并）：

```typescript
watch(
  () => route.fullPath,
  () => {
    const metaCollapse = route.meta.autoCollapseSidebar === true
    const aiPageCollapse = sidebarLocked.value === null
      && autoCollapsePages.some((p) => route.path.startsWith(p))
    const autoCollapse = metaCollapse || aiPageCollapse
    // ... 进入折叠 / 离开恢复逻辑不变
  },
)
```

手动切换锁定：

```typescript
function toggleCollapsed() {
  collapsed.value = !collapsed.value
  // ... 原有逻辑
  // 手动操作后锁定，不再自动折叠
  sidebarLocked.value = String(collapsed.value)
  localStorage.setItem('omichub:sidebar-locked', sidebarLocked.value)
}
```

**行为矩阵**：

| 场景 | 侧边栏行为 |
|------|-----------|
| 进入 `/studio` 或 `/ai`（未锁定） | 自动折叠至 64px |
| 离开 `/studio` 或 `/ai`（未锁定） | 恢复用户上次手动状态 |
| 用户手动点击汉堡按钮 | 切换折叠 + 写入 `localStorage` 锁定 |
| 锁定后进入 `/studio` 或 `/ai` | 不再自动控制，保持用户偏好 |
| 窗口 < 1024px（平板） | 原有逻辑不变，始终折叠 |
| 窗口 < 768px（移动端） | 原有逻辑不变，使用抽屉 |

---

## 三、设计规范遵循情况

| 规范要求 | 落实情况 |
|----------|----------|
| 语义色彩令牌（`--arco-*`、`--neutral-*`） | ✅ 所有新增颜色使用语义变量，无硬编码浅色值 |
| 动效令牌（`--motion-quick`、`--motion-standard`、`--motion-spring`） | ✅ 箭头旋转 140ms、展开 220ms spring |
| 仅动画 `transform` 和 `opacity` | ✅ 箭头旋转用 transform，展开用 opacity |
| `prefers-reduced-motion` 回退 | ✅ McpToolCallCard、KimiChatInput 均添加 |
| 可访问性（`aria-expanded`、焦点管理、`aria-label`） | ✅ 折叠卡片 `aria-expanded`，抽屉焦点落在批准按钮 |
| 弹窗 `v-model:show` 管理 | ✅ ApprovalDrawer 使用 `v-model:show` |
| `useMessage()` 反馈 | ✅ 审批成功/失败、工作台切换均有 toast |
| Naive UI 组件（NDrawer、NTag、NButton、NTooltip） | ✅ 全部使用 Naive UI |
| `<script setup lang="ts">` + Composition API | ✅ 所有新增/修改文件 |
| 深色模式兼容 | ✅ 使用 CSS 变量，深色模式自动适配 |

---

## 四、待配合事项

以下功能已在组件层面完成，但需要父组件（视图层）配合接入：

| 功能 | 需要配合的视图 | 接入方式 |
|------|---------------|----------|
| 暂停/继续/重新生成 | `AIChatView.vue`、`StudioView.vue` | 传递 `:is-streaming`、`:is-paused` props，处理 `@pause`、`@resume`、`@regenerate` 事件 |
| 审批底部抽屉 | `StudioView.vue` | 在 `onApprovalRequest` 回调中设置 `ApprovalDrawer` 的 `show` 和 `tool` |
| 工作台模式切换 | `AIChatView.vue` | 在 `@send` 回调中检查 `options.workbenchIntent`，执行模式切换或路由跳转 |

---

## 五、验收清单

- [x] 工具调用卡片默认折叠，展开/收起动画流畅，`aria-expanded` 正确
- [x] 流式输出可暂停，暂停后已输出内容保留，显示继续/重新生成按钮
- [x] 审批底部抽屉组件就绪，焦点管理正确，移动端高度 80vh
- [x] AI 气泡宽度与输入框对齐（`--chat-content-max-width: 860px`），代码块/表格可横向滚动
- [x] 意图匹配后 toast 提示，`workbenchIntent` 标记透传
- [x] 进入 `/studio`、`/ai` 侧边栏自动折叠，离开恢复；手动锁定后不再自动控制
- [x] 所有颜色使用语义令牌
- [x] `prefers-reduced-motion` 下动画安全回退
- [x] `vue-tsc --noEmit` 通过
- [x] `vite build` 通过
