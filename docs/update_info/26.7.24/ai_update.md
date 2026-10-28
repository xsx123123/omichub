# OmicHub AI 助手交互体验优化方案

> **版本**：v1.0 | **日期**：2026-07-24
>
> **范围**：AI 对话（`/ai`）与 AI 工作台（`/studio`）的交互层优化，不涉及后端接口变更。
>
> **设计基线**：遵循 `ARCHITECTURE_DESIN/fontend.md` 设计令牌、动效、可访问性与组件库约定。

---

## 一、功能概览

| # | 功能 | 改动层级 | 涉及文件（主要） |
|---|------|----------|------------------|
| 1 | MCP 工具调用默认折叠 | 展示层 | `KimiMessageItem.vue`、新增 `McpToolCallCard.vue` |
| 2 | 暂停 AI 流式回复 | 交互 + 组合式函数 | `KimiChatInput.vue`、`useAgentChatStream.ts` |
| 3 | 审批弹窗底部抽屉 | 交互 + 组件 | `ApprovalCard.vue` → `ApprovalDrawer.vue` |
| 4 | AI 回复气泡宽度对齐 | 样式 | `KimiMessageItem.vue`、`KimiMessageList.vue` |
| 5 | 自动切换工作台模式 | 逻辑 | `KimiChatInput.vue` 或 `AgentWorkspace.vue` |
| 6 | 工作台自动折叠侧边栏 | 布局 | `DefaultLayout.vue` |

---

## 二、功能详述

### 2.1 MCP 工具调用默认折叠

**现状**：`update_plan`、`workspace_write` 等工具调用的参数和结果在 `KimiMessageItem.vue` 中以 `.tool-card` 完全展开，单次调用占据大量垂直空间。

**目标**：

```
┌─────────────────────────────────────────────┐
│ 🔧 update_plan              ✓ 成功   [▶]   │  ← 默认折叠
├─────────────────────────────────────────────┤
│ 🔧 workspace_write       ⏳ 等待批准  [▶]   │  ← 折叠，状态一目了然
└─────────────────────────────────────────────┘
```

**实现要点**：

- 新建 `frontend/src/components/ai-chat/McpToolCallCard.vue`，从 `KimiMessageItem.vue` 的 `.tool-card` 逻辑抽离。
- 内部维护 `collapsed = ref(true)`；折叠态单行展示：工具图标 + 工具名 + `NTag` 状态标签 + 旋转箭头。
- 展开态显示完整参数 JSON（`<pre>` + 语法高亮）+ 执行结果 + 操作按钮。
- 箭头动画：`transform: rotate(90deg)`，`transition: transform var(--motion-quick) ease-out`。
- 状态标签使用语义色：成功 `--arco-success`、失败 `--arco-danger`、等待批准 `--arco-warning`、运行中 `--arco-primary`。

**动效参数**：

| 属性 | 值 | 来源 |
|------|-----|------|
| 箭头旋转 | `140ms ease-out` | `--motion-quick` |
| 内容展开 | `220ms var(--motion-spring)` | `--motion-standard` |

---

### 2.2 暂停 AI 流式回复

**现状**：流式输出时用户无法中断，只能等待完成或刷新页面。`useAgentChatStream.ts` 通过 `fetch` + `ReadableStream` 接收 SSE。

**目标**：

```
流式输出中：              暂停后：
[⏸ 暂停生成]            [▶ 继续]  [↻ 重新生成]
```

**实现要点**：

- `useAgentChatStream.ts` 内部持有 `AbortController`；暂停时调用 `controller.abort()`，保留已追加的文本。
- `KimiChatInput.vue` 的发送按钮在 `isStreaming` 时切换为暂停按钮（`NButton` + 暂停图标）。
- 暂停后在消息底部追加状态行："已暂停"+ 两个操作按钮：
  - **继续**：若后端支持断点续传（`X-Stream-Offset`），从断点重连；否则等同重新生成。
  - **重新生成**：清空当前 AI 回复，以相同 `messages` 重新发起请求。
- 流式状态使用 `shallowRef` 存储文本，避免深层响应开销（遵循设计文档 §14.4）。

**状态映射**（遵循设计文档 §5.5 状态卡片协议）：

| 状态 | 按钮 | 文本提示 |
|------|------|----------|
| 流式中 | ⏸ 暂停 | — |
| 已暂停 | ▶ 继续 / ↻ 重新生成 | "生成已暂停" |
| 完成 | 发送（恢复） | — |

---

### 2.3 审批弹窗底部抽屉

**现状**：`ApprovalCard.vue` 将审批操作内嵌在对话流中，占用消息列表空间且视觉突兀。

**目标**：

```
┌─────────────────────────────────────────┐
│            （半透明遮罩）                 │
│                                         │
│  ┌─────────────────────────────────┐    │
│  │  🔒 操作审批                     │    │
│  │  workspace_write → /output/…    │    │
│  │  ┌───────────────────────────┐  │    │
│  │  │  文件内容预览（可滚动）     │  │    │
│  │  └───────────────────────────┘  │    │
│  │                                 │    │
│  │  [批准运行]  [编辑后运行]  拒绝  │    │
│  └─────────────────────────────────┘    │  ← 从底部滑入
└─────────────────────────────────────────┘
```

**实现要点**：

- 新建 `frontend/src/components/ai-chat/ApprovalDrawer.vue`，使用 `NDrawer` + `placement="bottom"`。
- 通过 `v-model:show` 控制可见性（遵循设计文档 §5.6 弹窗约定）。
- 高度 `60vh`（移动端 `80vh`），圆角顶部 `border-radius: 16px 16px 0 0`。
- 遮罩 `rgba(0, 0, 0, 0.4)`，点击遮罩关闭（等同拒绝）。
- 内容区：操作类型标题 + 影响文件路径（`NTag`）+ 代码预览（`<pre>` 可滚动，最大高度 `30vh`）。
- 操作按钮：批准（`type="primary"`）、编辑后运行（`secondary`）、拒绝（`text`/`quaternary`）。
- 打开时焦点落在"批准运行"按钮；关闭后焦点返回触发消息。
- 异步审批期间按钮 `:loading` 防止重复提交。

**动效参数**：

| 属性 | 值 |
|------|-----|
| 抽屉滑入 | `300ms ease-out`（NDrawer 内置） |
| 抽屉滑出 | `200ms ease-in` |
| 遮罩淡入/淡出 | `200ms` |

> 注：`NDrawer` 自带动画，若需自定义时长可通过 `NDrawer` 的 `style` 或 CSS 覆盖 `--n-body-padding` 等变量。优先使用组件内置过渡。

---

### 2.4 AI 回复气泡宽度对齐

**现状**：AI 回复气泡 `max-width: 720px`，与底部输入框宽度不一致，宽屏下视觉不协调。

**目标**：AI 回复气泡最大宽度与输入框容器等宽，保持左右边距一致。

**实现要点**：

```css
/* KimiMessageList.vue 或对应样式 */
.ai-message-bubble {
  max-width: min(100% - 48px, var(--chat-content-max-width, 860px));
}
```

- 使用 CSS 变量 `--chat-content-max-width` 统一消息列表和输入框的最大宽度。
- 在消息列表容器和输入区容器上共享同一 `max-width` + `margin: 0 auto` 居中策略。
- Markdown 表格和代码块设置 `overflow-x: auto`，最小宽度 `320px`，避免被挤压。
- 用户消息保持右对齐，最大宽度可略窄（`70%`），与 AI 消息形成视觉区分。

---

### 2.5 自动切换工作台模式

**现状**：用户要求"生成一份分析报告"时，AI 在普通对话模式回复，未利用工作台的计划-执行-产物能力。

**目标**：检测用户意图后自动切换到工作台模式，使用 `update_plan` 制定计划并分步执行。

**实现要点**：

- 在消息发送前（`KimiChatInput.vue` 的 `handleSend` 或 `AgentWorkspace.vue`）进行意图匹配。
- 触发规则：动词（生成/创建/编写/制作/输出/分析）+ 名词（文档/模板/脚本/报告/文件/流程）。
- 匹配时：
  1. 自动切换右上角模式开关至"工作台模式"。
  2. 使用 `useMessage().info("已为您切换至工作台模式，便于跟踪任务进度")`。
  3. 后续请求携带 `mode: 'workbench'` 参数，后端使用 `update_plan` 工具。
- 不强制：用户可手动切回对话模式；不阻断发送流程。
- 关键词列表维护在 `frontend/src/config/` 下的常量文件中，便于后续扩展。

**触发词示例**：

| 动词 | 名词 |
|------|------|
| 生成、创建、编写、制作、输出、分析 | 文档、模板、脚本、报告、文件、流程、方案 |

---

### 2.6 AI 工作台自动折叠侧边栏

**现状**：进入 `/studio`（AI 工作台）后，`DefaultLayout.vue` 的 `NLayoutSider` 保持展开（~200px），工作台区域狭窄。

**目标**：

```
展开（~200px）：              折叠（60px）：
┌────────┬────────────┐     ┌──┬──────────────────┐
│ 🏠 首页 │            │     │🏠│                  │
│ 📊 仪表 │  AI 工作台  │     │📊│    AI 工作台      │
│ 🧪 分析 │  （狭窄）   │     │🧪│    （宽敞）       │
│ 💾 数据 │            │     │💾│                  │
└────────┴────────────┘     └──┴──────────────────┘
```

**实现要点**：

- `DefaultLayout.vue` 已使用 `NLayoutSider` 的 `collapsed` + `collapse-mode="width"` + `:collapsed-width="60"`。
- 新增路由监听：进入 `/studio` 或 `/ai` 时自动设置 `collapsed = true`；离开时恢复。
- 用户手动切换侧边栏时，写入 `localStorage('omichub:sidebar-locked')`，后续不再自动控制。
- 折叠态图标悬停使用 `NTooltip` 显示页面名称（`NLayoutSider` 的 `show-trigger` 或自定义 trigger）。
- 当前选中项保留左侧 3px 高亮色条（已有 `NMenu` 的 active 样式）。

**代码思路**（基于现有 `DefaultLayout.vue`）：

```typescript
// DefaultLayout.vue <script setup lang="ts">
const route = useRoute()
const sidebarLocked = ref(localStorage.getItem('omichub:sidebar-locked'))

const autoCollapsePages = ['/studio', '/ai']

watch(
  () => route.path,
  (path) => {
    if (sidebarLocked.value !== null) return
    collapsed.value = autoCollapsePages.some((p) => path.startsWith(p))
  },
  { immediate: true },
)

function handleManualToggle() {
  collapsed.value = !collapsed.value
  sidebarLocked.value = String(collapsed.value)
  localStorage.setItem('omichub:sidebar-locked', sidebarLocked.value)
}
```

**动效参数**：

| 属性 | 值 | 来源 |
|------|-----|------|
| 宽度变化 | `200ms ease-in-out` | NLayoutSider 内置 |
| Tooltip 出现 | `140ms` | `--motion-quick` |

---

## 三、技术约束

| 约束 | 说明 |
|------|------|
| 框架 | Vue 3 + TypeScript + `<script setup lang="ts">` |
| 组件库 | Naive UI（NDrawer、NTag、NButton、NTooltip、NLayoutSider） |
| 样式 | 消费 `tokens.css` / `global.css` 语义变量，不硬编码色值 |
| 动效 | CSS transition 为主；仅动画 `transform` 和 `opacity`；遵循 `--motion-*` 令牌 |
| MCP 逻辑 | 保持现有 `useAgentChatStream` 的 tool_call 解析不变，只改展示层 |
| 可访问性 | 折叠卡片 `aria-expanded`；抽屉焦点管理；按钮 `aria-label`；`prefers-reduced-motion` 回退 |
| 移动端 | 审批抽屉 `80vh`；侧边栏默认折叠；气泡宽度 `100% - 32px` |

---

## 四、改动文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `components/ai-chat/McpToolCallCard.vue` | 新增 | 可折叠工具调用卡片 |
| `components/ai-chat/KimiMessageItem.vue` | 修改 | 替换内联 `.tool-card` 为 `McpToolCallCard` |
| `components/ai-chat/ApprovalDrawer.vue` | 新增 | 底部抽屉审批组件 |
| `components/ai-chat/KimiChatInput.vue` | 修改 | 暂停/继续/重新生成按钮 |
| `composables/useAgentChatStream.ts` | 修改 | 暴露 `abort()`、`isPaused` 状态 |
| `components/ai-chat/KimiMessageList.vue` | 修改 | 气泡宽度变量对齐 |
| `layouts/DefaultLayout.vue` | 修改 | 路由感知侧边栏自动折叠 |
| `config/aiIntents.ts` | 新增 | 工作台模式触发关键词常量 |
| `styles/global.css` | 修改 | 新增 `--chat-content-max-width` 变量 |

---

## 五、验收清单

- [ ] 工具调用卡片默认折叠，展开/收起动画流畅，`aria-expanded` 正确
- [ ] 流式输出可暂停、可继续/重新生成，暂停后已输出内容保留
- [ ] 审批操作触发底部抽屉，焦点管理正确，移动端高度 80vh
- [ ] AI 气泡宽度与输入框对齐，代码块/表格可横向滚动
- [ ] 意图匹配后自动切换工作台模式，有 toast 提示，可手动切回
- [ ] 进入 `/studio` 侧边栏自动折叠，离开恢复；手动锁定后不再自动控制
- [ ] 所有颜色使用语义令牌，深色模式正常
- [ ] `prefers-reduced-motion` 下动画安全回退
- [ ] `npm run type-check` 和 `npm run build` 通过

---

## 六、自测验证步骤

1. **MCP 折叠**：发送触发工具调用的消息 → 确认卡片默认折叠 → 点击展开 → 确认参数和结果完整 → 再次点击折叠。
2. **暂停回复**：发送长回复请求 → 流式中点击暂停 → 确认文本停止增长 → 点击继续/重新生成 → 确认行为正确。
3. **审批抽屉**：触发 `workspace_write` → 确认抽屉从底部滑入 → 预览内容 → 批准/拒绝 → 确认抽屉关闭、对话流更新。
4. **气泡宽度**：调整浏览器宽度 → 确认气泡与输入框等宽 → 发送含表格/代码块的消息 → 确认可横向滚动。
5. **工作台切换**：输入"生成一份分析报告" → 确认自动切换 + toast → 手动切回 → 确认不再强制。
6. **侧边栏折叠**：导航到 `/studio` → 确认侧边栏折叠 → 导航到首页 → 确认恢复 → 手动折叠并导航 → 确认偏好保持。
7. **深色模式 + 窄屏**：切换深色主题 → 重复以上步骤 → 切换至 375px 宽度 → 确认布局正常。
