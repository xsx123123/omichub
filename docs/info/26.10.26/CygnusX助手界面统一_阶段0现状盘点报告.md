# CygnusX 助手界面统一 · 阶段 0 现状盘点报告

> 调研对象：星尘 AI（`/ai/:sessionId?`）与科研寻宝鼠（`/treasure-mouse`）。
> 调研方式：只读代码审查；未修改任何代码、样式、配置或注释。
> 证据约定：`文件:行号` 或 `文件#组件/函数`。找不到证据的结论明确写“未在代码中找到”。
> 本报告只描述现状与建议，不代表阶段 1 已开始。

---

## 0. 结论摘要

1. **两套界面没有共享任何聊天组件、聊天 store 或聊天 composable。** 星尘是 Vue 3 + naive-ui + scoped SCSS；寻宝鼠是“Vue 外壳 → Shadow DOM → React island”的跨运行时实现。共享的只有底层 HTTP 客户端、鉴权和少量周边 API，见 §1.3。
2. **统一改造的真正阻断点不是“样式不同”，而是运行时边界与数据模型不同。** 星尘的 `ChatMessage` 有 `modelName/tokens/timeline/toolCalls`，但没有顶层 `agent_id`；寻宝鼠的 `ResearchMessage` 有 `created_at` 但消息视图层不展示，也没有 tokens、model、feedback。见 §4。
3. **寻宝鼠的模型切换器目前是“有控件、无能力”。** 平台传入的是 `modelOptions: ['平台默认模型']` 与 `onSelectModel: () => {}`；后端 `ResearchSession.model_id` 存在但没有被传入 island。见 §2、§5。
4. **手册中若干“现状描述”与代码不一致，需以本报告为准：**
   - 星尘没有独立的“模型 badge”，模型名被当作助手身份名的回退显示。
   - STELLAR ROUTER 卡片不是百分比进度条，它展示意图与置信度；真正的进度条在 Overdrive / Fanout 卡片。
   - 寻宝鼠的数据集编号链接是**绿色**（`--color-helix`），不是橙色；正则只覆盖 GSE/GSM/GO/PMID，**不覆盖 SRR/PRJNA**。
   - 寻宝鼠的“意图规划/核验”步骤 chip 实际被过滤掉，只展示检索类工具。
   - 星尘的主强调色是蓝色，不是紫色；紫色主要用于渐变、动画和路由专家身份色。
   - 星尘普通助手消息没有“重新生成”按钮；只有错误/空内容态的消息操作栏有。
5. **阶段 1~2 应走“契约先行、双渲染器”路线**，而不是抽一个 Vue SFC 给两端复用。推荐目录与拆分顺序见 §6。

---

## 1. 组件树与实现位置

### 1.1 星尘 AI

**路由与外壳**

- 路由：`/ai/:sessionId?`，`meta.fullscreen: true`，见 `frontend/src/router/index.ts:133-138`。
- 布局：`frontend/src/layouts/DefaultLayout.vue:116-131` 对 `fullscreen` 只去掉内容 padding；顶部导航仍在，见 `DefaultLayout.vue:488-534`。
- 页面：`frontend/src/views/AIChatView.vue` → `AgentWorkspace.vue`。

```text
/ai/:sessionId?                         router/index.ts:133-138
└─ AIChatView.vue
   └─ AgentWorkspace.vue                agent-workspace/AgentWorkspace.vue:193-216
      ├─ AgentSidebar.vue               60px 图标栏：新建对话 / 历史会话
      │                                 AgentSidebar.vue:11-34、38-47
      ├─ AgentSandbox.vue               当前会话主容器
      │                                 AgentSandbox.vue:575-812
      │  ├─ StardustHero.vue            空会话 welcome（canvas 星尘 + 时段问候）
      │  │                              AgentSandbox.vue:641-645；StardustHero.vue:12-18、208-217
      │  ├─ KimiMessageList.vue         虚拟列表
      │  │                              AgentSandbox.vue:648-673
      │  │  └─ KimiMessageItem.vue      单条消息（2270 行）
      │  │     KimiMessageList.vue:348-369
      │  │     ├─ Markdown（markdown-it，linkify: true）
      │  │     │                          ai-chat/setup.ts:22
      │  │     ├─ RouteTransitionCard.vue           STELLAR ROUTER 路由卡
      │  │     ├─ OverdriveProgressCard.vue         超频进度卡（百分比）
      │  │     ├─ FanoutProgressCard.vue            并行子 Agent 进度卡
      │  │     ├─ TaskProgressCard.vue / PipelineTaskCard.vue
      │  │     ├─ ToolCallEntry.vue / StudioCellGroup.vue
      │  │     ├─ SkillInvocationCard.vue
      │  │     ├─ AskUserCard / PlanConfirmationCard / OverdriveApprovalCard
      │  │     ├─ MessageArtifactGallery / AgentTeamsCaseCard
      │  │     └─ MessageActionBar.vue / assistant-feedback-bar
      │  ├─ KimiChatInput.vue           输入 dock（2520 行）
      │  │                              AgentSandbox.vue:694-747
      │  │  ├─ MentionMenu.vue          @ 引用
      │  │  ├─ SlashCommandMenu.vue     / 快捷命令
      │  │  ├─ McpSelectionMenu.vue
      │  │  └─ toolbar：附件 / 工作区引用 / 联网 / 终端 / MCP / 深度思考 /
      │  │            运行时 / 进入工作台 / 队列
      │  │             KimiChatInput.vue:1505-1767
      │  └─ AgentCapabilityDrawer.vue   能力说明/编辑抽屉
      │                                 AgentSandbox.vue:810
      ├─ SessionHistoryDrawer.vue       历史会话抽屉
      │                                 AgentWorkspace.vue:216
      └─ AgentHub.vue                   无当前会话时的 Agent 选择页
                                        AgentWorkspace.vue:213
```

**状态与数据来源**

- 会话、消息、流式内容：`frontend/src/stores/agentHub.ts`。
- SSE：`frontend/src/composables/useAgentChatStream.ts`，请求 `POST /api/v1/chat/stream`（`useAgentChatStream.ts:609`）。
- 消息身份：`ChatMessage.modelName` 在 `agentHub.ts:2218-2228` 生成；`KimiMessageItem.vue:415-421` 优先使用 `senderAgent.name`，否则 `modelName`，最后 `agentName`。
- 历史消息的模型名恢复：`agentHub.ts:1707` 从 `metadata_json.model` 读取。

**过程可视化**

| 过程形态 | 组件 | 数据来源 |
|---|---|---|
| 路由更新卡（STELLAR ROUTER） | `RouteTransitionCard.vue:36-65` | `route` SSE 事件 → `message.routedAgent`；卡片展示 `transition.visible`、意图标签、置信度百分比（`RouteTransitionCard.vue:13-17、48-62`） |
| 超频协作进度（百分比） | `OverdriveProgressCard.vue` | `overdrive_progress` SSE 事件；`percentage()` 在 `OverdriveProgressCard.vue:149-159` |
| 并行子 Agent 进度 | `FanoutProgressCard.vue` | `subagents` SSE 事件；百分比在 `FanoutProgressCard.vue:13-17` |
| 工具调用 | `ToolCallEntry.vue` / `StudioCellGroup.vue` | `tool_call` / `tool_result`；`message.toolCalls` 与 `message.timeline` |
| 技能调用 | `SkillInvocationCard.vue` | `skill` SSE 事件；`duration_ms` 在 `SkillInvocationCard.vue:33-36` |
| 思考过程 | `KimiMessageItem.vue:1030-1040` | `message.thought` / `streamingThought`；`thinkingDuration` 字段在 `types.ts:184-185` |

> 注意：`RouteTransitionCard` 不是进度条；它只有置信度 `%` 文本。真正的百分比进度条在 Overdrive / Fanout 卡片。

**实体高亮**

- 数据集编号：**未在代码中找到** GSE/GSM/SRR/PRJNA 的专用正则或渲染组件。`ai-chat/setup.ts:22` 只开启了 markdown-it 的通用 `linkify`。
- 文件引用：
  - 用户消息附件 chip：`KimiMessageItem.vue:880-897`，样式 `KimiMessageItem.vue:1537-1549`。
  - 输入区工作区文件 chip：`.ref-file`，`KimiChatInput.vue:2185-2188`，颜色 `--arco-primary`。
  - @ 文件/技能/智能体：`MentionMenu.vue`，入口 `KimiChatInput.vue:1321-1356`。
- 工具引用：`ToolCallEntry` 在 `KimiMessageItem.vue:1090-1173`。

### 1.2 科研寻宝鼠

**路由与外壳**

- 路由：`/treasure-mouse`，`meta.fullscreen: true`，见 `frontend/src/router/index.ts:73-78`。
- 页面：`frontend/src/views/TreasureMouseView.vue` → `TreasureResearchWorkbench.vue`。
- 平台外壳与星尘相同，仍走 `DefaultLayout` 顶部导航；寻宝鼠自己的 header 在 island 内。

```text
/treasure-mouse                         router/index.ts:73-78
└─ TreasureMouseView.vue
   └─ TreasureResearchWorkbench.vue     消息/SSE/项目/会话编排
      │                                 TreasureResearchWorkbench.vue:337-339
      ├─ TreasureOriginalDisplay.vue    Vue → Shadow DOM 挂载器
      │  │                              TreasureOriginalDisplay.vue#mount
      │  │  ├─ loadTreasureIsland()     动态 import public/treasure-island/treasure-island.js
      │  │  ├─ syncAppearance()         从 documentElement 同步 theme/locale
      │  │  └─ view: TreasureIslandProps
      │  │      modelOptions: ['平台默认模型']、onSelectModel: () => {}
      │  │      TreasureOriginalDisplay.vue:35、39
      │  └─ Shadow DOM host              treasure-island/index.tsx:46
      │     └─ React island: FullPresentation.tsx
      │        │                        treasure-island/FullPresentation.tsx:71-121
      │        ├─ SessionSidebar / MobileDrawerHeader
      │        │                        FullPresentation.tsx:59-64、72-78
      │        ├─ header toolbar        刷新 / 排行榜 / 统计 / 关于 / 资产 /
      │        │                        能力 / 语言 / 桌宠 / 主题
      │        │                        FullPresentation.tsx:80-101
      │        ├─ EmptyState.tsx        welcome + 4 张任务卡 + 来源说明
      │        │                        FullPresentation.tsx:104；
      │        │                        EmptyState.tsx:29-71
      │        ├─ ChatMessage.tsx       单条消息
      │        │                        FullPresentation.tsx:105-108
      │        │  ├─ Markdown.tsx → IdLink.tsx
      │        │  │                     Markdown.tsx:3、17-40、102-124
      │        │  ├─ ToolTrace.tsx      步骤 chip 行
      │        │  │                     ChatMessage.tsx:150-152
      │        │  ├─ DatasetCardGrid / LiteratureCardPanel
      │        │  ├─ GroundingNotice / DownloadBoostCard
      │        │  └─ SuggestionBlock
      │        ├─ Composer.tsx          输入区
      │        │                        FullPresentation.tsx:65-69、112
      │        ├─ ResearchWorkflowPanel / PaperWorkspace
      │        │                        FullPresentation.tsx:114-115
      │        ├─ TreasureMouse / PetSettingsPanel
      │        │                        FullPresentation.tsx:116-117
      │        ├─ Leaderboard / UsageStatsDialog / AboutPresentation
      │        │                        FullPresentation.tsx:118-120
      │        └─ Dialogs 通过 presentation.portalContainer 进入 Shadow DOM
      └─ useResearchWorkflow / researchAgentApi / fetch SSE
```

**状态与数据来源**

- `messages`、`currentSession`、`sending`、`streamError`：`TreasureResearchWorkbench.vue:24-30`。
- 会话 API：`researchAgentApi`，`frontend/src/api/researchAgent.ts:84-118`。
- SSE：`POST /api/v1/research-agent/sessions/{id}/messages:stream`，`researchAgent.ts:120-122`；`Last-Event-ID` 断点续传，`TreasureResearchWorkbench.vue:109-133`。
- 事件落盘与视图映射：`frontend/src/components/research/adapters/researchPresentation.ts:73-90`。
- island 只接收展示数据与回调：`TreasureResearchWorkbench.vue:315-328`。

**过程可视化**

- 组件：`ToolTrace.tsx`。
- 每步 chip：图标（运行中 Loader / 完成 Check / 失败 X）+ 工具名 + `ms`，`ToolTrace.tsx:15-19、44-56`。
- 文献检索完成后按来源聚合：`ToolTrace.tsx:60-73`。
- 数据来源：`tool` SSE 事件 → `metadata_json.events.tools`（`researchPresentation.ts:85-86`）→ `researchMessageView` 生成 `toolLogs`（`researchPresentation.ts:75`）→ `ChatMessage` 渲染 `ToolTrace`（`ChatMessage.tsx:150-152`）。
- **过滤规则**：`grounding_check` 与 `intent_plan` 被排除在可见轨迹之外，见 `ChatMessage.tsx:96-98`。因此“意图规划/核验” chip 在当前代码中不会显示。

**实体高亮**

- 数据集编号：`frontend/src/lib/linkify.ts:13-18`，只匹配：
  - `GSE\d{3,7}`
  - `GSM\d{3,7}`
  - `GO:\d{7}`
  - `PMID:?\s?\d{6,9}`
- 渲染：`Markdown.tsx:102-124` 的 rehype 插件把文本节点切成 `<idlink>`，再由 `IdLink.tsx` 渲染浮层/复制/证据链。
- 链接颜色：`styles.css:497-513`，`color: var(--color-helix)`，即品牌绿；不是橙色。
- 文件引用：`ChatMessage.tsx:26-40` 的 `ChatUIMessage` 没有 attachments 字段；平台模式也没有把 `paperMode` / `paperAction` 传入 island（`TreasureResearchWorkbench.vue:315-328` 无 `paperMode`，`FullPresentation.tsx:65-69` 只透传 props）。因此当前平台模式没有通用附件/文件 chip。
- 工具引用：`ToolTrace` 的 chip 行。

### 1.3 两界面共享性结论

| 维度 | 星尘 AI | 科研寻宝鼠 | 是否共享 |
|---|---|---|---|
| 消息列表 | `KimiMessageList.vue` | React `FullPresentation` + `ChatMessage.tsx` | 否 |
| 消息项 | `KimiMessageItem.vue` | React `ChatMessage.tsx` | 否 |
| 输入区 | `KimiChatInput.vue` | React `Composer.tsx` | 否 |
| 聊天 store | `agentHub.ts` + `useAgentChatStream.ts` | `TreasureResearchWorkbench.vue` 局部 state + `useResearchWorkflow` | 否 |
| 样式 token | `tokens.css` / `chat-theme.css` / `global.css` | `styles.css`（Shadow DOM 内） | 否，两套 |
| Markdown | markdown-it（`setup.ts`） | react-markdown + rehype（`Markdown.tsx`） | 否 |
| 图标 | `@vicons/ionicons5` | `lucide-react` | 否 |
| UI 库 | naive-ui | Radix + Tailwind 4 | 否 |
| HTTP 客户端 | `api/client.ts` | `api/client.ts`（研究 API）+ 原生 `fetch`（SSE） | 部分 |
| 会话标题 | `chatApi.generateSessionTitle` | 复用 `chatApi.generateSessionTitle`（`researchAgent.ts:107-109`） | 是（周边 API） |

---

## 2. 「能力 × 两助手」矩阵

状态说明：

- **已实现**：有明确代码路径并接入当前平台。
- **部分实现**：有控件/字段/组件，但缺少一端数据或未接入平台。
- **未实现**：未找到代码路径。
- **刻意精简\***：根据组件能力面和产品定位判断为有意不做；但**代码中未找到显式 `disabledSlots` 声明**，阶段 2 需要显式化，避免被误判为缺陷。

| # | 能力 | 星尘 AI | 科研寻宝鼠 |
|---|---|---|---|
| 1 | 消息气泡 | 已实现：用户右对齐 `KimiMessageItem.vue:1518-1530`；助手卡片 `:2220-2225` | 已实现：用户右对齐绿色气泡 `ChatMessage.tsx:123`；助手卡片 `:154` |
| 2 | 助手头像与名称 | 部分实现：Lottie/emoji + 名称 `KimiMessageItem.vue:912-951`；默认头像 `🤖`、默认色 `#4f8ef7` 来自 `KimiMessageList.vue:34-39`，`AgentSandbox` 未传 agent 身份 | 已实现（固定品牌）：BrandMark + `brand.name`，`ChatMessage.tsx:137-143`；无每 Agent 身份 |
| 3 | 用户头像与名称 | 已实现：名称 + `UserAvatar`，`KimiMessageItem.vue:861-875` | 部分实现：只有 User 图标，无名称，`ChatMessage.tsx:126-128` |
| 4 | meta：模型 badge | 部分实现：没有独立 badge；模型名作为助手身份名回退，`KimiMessageItem.vue:415-421` + `agentHub.ts:2218-2228` | 未实现：消息视图无 model 字段，`ChatMessage.tsx:26-40` |
| 5 | meta：Tokens 统计 | 已实现：`Tokens: total ↑in ↓out`，`KimiMessageItem.vue:404-413`；助手 header `:947-951` | 未实现：`ResearchMessage` 无 tokens，`researchAgent.ts:72-82` |
| 6 | meta：耗时 | 部分实现：思考耗时 `thinkingDuration`（`types.ts:184-185`）；技能耗时 `duration_ms`（`SkillInvocationCard.vue:33-36`）；通用工具无耗时字段 | 已实现（工具级）：每步 `ms`，`ToolTrace.tsx:54-56`；meta 行还有总检索耗时 `ChatMessage.tsx:144-147` |
| 7 | meta：时间戳 | 已实现：`MM/DD HH:mm`，`KimiMessageItem.vue:386-390`；用户/助手都显示 | 未实现：`ChatUIMessage` 无 `createdAt`，`ChatMessage.tsx:26-40`；`researchMessageView` 也未映射 |
| 8 | meta：检索次数 | 未实现：没有消息级“检索 n 次”字段/展示；只有工具卡与来源卡 | 已实现：`{n} 次检索 · {ms}ms`，`ChatMessage.tsx:142-148` |
| 9 | 过程卡：步骤模式 | 部分实现：工具卡/技能卡是步骤列表，但没有“每步耗时”统一行；`ToolCallEntry.vue`、`SkillInvocationCard.vue` | 已实现：`ToolTrace` chip 行 + 每步 `ms`，`ToolTrace.tsx:21-79` |
| 10 | 过程卡：进度模式 | 已实现：Overdrive 百分比 `OverdriveProgressCard.vue:149-159`；Fanout 百分比 `FanoutProgressCard.vue:13-17`；路由卡只有置信度 `RouteTransitionCard.vue:48-62` | 未实现：无百分比进度卡；只有步骤 chip |
| 11 | 实体高亮：数据集编号 | 未实现：未找到 GSE/GSM/SRR/PRJNA 正则；仅 markdown-it `linkify: true`（`setup.ts:22`） | 部分实现：GSE/GSM/GO/PMID，`linkify.ts:13-18`；**不含 SRR/PRJNA**，尽管 placeholder 提到 SRR（`zh.ts:155-156`） |
| 12 | 实体高亮：文件引用 | 已实现：用户附件 chip `KimiMessageItem.vue:880-897`；输入区 `.ref-file` `KimiChatInput.vue:2185-2188`；@ 文件 `MentionMenu.vue` | 未实现/未接线：`Composer` 有 `paperMode` PDF 附件（`Composer.tsx:106-119`），但平台未传 `paperMode/onPaperAction`（`TreasureResearchWorkbench.vue:315-328`）；消息视图无 attachments |
| 13 | 实体高亮：工具引用 | 已实现：`ToolCallEntry`/`StudioCellGroup`，`KimiMessageItem.vue:1090-1173` | 已实现：`ToolTrace` chip，`ChatMessage.tsx:150-152` |
| 14 | 输入区：附件 | 已实现：附件按钮，`KimiChatInput.vue:1507-1514`；支持粘贴/拖入 | 未接线：`Composer` 仅 `paperMode` 下显示 PDF 按钮（`Composer.tsx:106-119`）；平台模式未启用 |
| 15 | 输入区：@ 引用 | 已实现：`MentionMenu.vue`，入口 `KimiChatInput.vue:1321-1356`；文件/技能/智能体 | 刻意精简\*：`Composer` 无 @ 控件（`Composer.tsx:85-176`）；依据：检索助手输入面仅文本/模型/发送 |
| 16 | 输入区：/ 快捷命令 | 已实现：`SlashCommandMenu.vue`，入口 `KimiChatInput.vue:1321-1356`；触发 `:617-637` | 刻意精简\*：`Composer` 无 / 控件；无显式声明 |
| 17 | 输入区：深度思考 | 已实现：`toolbar.deepThinking`，`KimiChatInput.vue:1574-1588`；状态在 `chatStore.deepThinking` | 刻意精简\*：`Composer` 无此槽位；无显式声明 |
| 18 | 输入区：进入工作台 | 已实现：`toolbar.workbench`，`KimiChatInput.vue:1655-1671`；`AgentSandbox` 传 `show-workbench-control` `:701` | 刻意精简\*：`Composer` 无此槽位；无显式声明 |
| 19 | 输入区：语音 | 未实现：`frontend/src/components/ai-chat` 未找到麦克风/录音控件 | 未实现：`Composer` 未找到语音控件 |
| 20 | 发送行为：Enter / Shift+Enter | 已实现：Enter 发送、Shift+Enter 换行、IME 防护，`KimiChatInput.vue:542-613` | 已实现：`Composer.tsx:136-142`；IME composition 处理 `:106-134` |
| 21 | 流式期间继续发送/队列 | 已实现：`AgentSandbox` 传 `:queued-items` 与 `@remove-queued`，`AgentSandbox.vue:694-709`；`KimiChatInput` 队列 UI | 未接线：`Composer` 预留 `onQueue`（`Composer.tsx:39-40、74-80`），但 `FullPresentation` 未传，流式中按 Enter 直接返回（`Composer.tsx:73-80`） |
| 22 | 赞 / 踩 / 复制 | 已实现：助手 feedback bar 👍👎📋，`KimiMessageItem.vue:1281-1315`；用户操作栏复制/编辑/删除/重发 `MessageActionBar.vue:112-152` | 部分实现：只有复制问答，`ChatMessage.tsx:119-121、191-204`；没有赞/踩 |
| 23 | 消息重新生成 | 部分实现：用户消息有“重新发送”（`MessageActionBar.vue:112-121`）；助手**普通完成态没有重新生成**，只有错误/空内容态的操作栏有（`KimiMessageItem.vue:1318-1329`；`MessageActionBar.vue:179-194`） | 已实现：完成且非流式的助手消息有“重新挖一次”，`ChatMessage.tsx:191-204`；父层 `TreasureResearchWorkbench.vue:306-310` 取上一条用户消息重发 |
| 24 | 页脚免责声明 | 未实现：未找到通用免责声明；只有暂停提示 `KimiChatInput.vue:1764-1766` | 已实现：`composer.disclaimer`，`Composer.tsx:172`；文案 `zh.ts:160-161` |
| 25 | 模型切换器 | 已实现：`AgentSandbox.vue:606-625` 的 `n-select`；`handleModelSwitch` `:390-399` | 部分实现/未接线：`Composer` 有原生 `<select>`（`Composer.tsx:160-170`），但平台只给 `['平台默认模型']` 且 `onSelectModel: () => {}`（`TreasureOriginalDisplay.vue:35、39`） |
| 26 | 助手能力说明入口 | 已实现：`AgentCapabilityDrawer.vue`，`AgentSandbox.vue:626-634、810`；展示/编辑模型、MCP、Skill | 部分实现：header “刷新下载能力与权限”触发 `capabilities.refresh`（`FullPresentation.tsx:96`；`TreasureResearchWorkbench.vue:311-313`）；`AboutPresentation` 是项目介绍（`archive/island/src/island/AboutPresentation.tsx:32-53、68-70`），不是 Agent 能力档案 |
| 27 | 会话侧栏 | 已实现：60px 图标栏 + 历史抽屉，`AgentSidebar.vue:11-34`；`SessionHistoryDrawer` | 已实现：56px 图标栏 + 270px 展开栏，`FullPresentation.tsx:72-78` |
| 28 | 主题 / 语言 | 主题：用户菜单切换，`DefaultLayout.vue:421-438`；语言：聊天壳未找到切换入口 | 主题：header 切换，`FullPresentation.tsx:98-99`；语言：`LanguageToggle`，`FullPresentation.tsx:97` |

---

## 3. 样式现状清单

### 3.1 Token 体系

| 文件 | 规模/职责 | 关键 token |
|---|---|---|
| `frontend/src/styles/tokens.css` | 138 行；全局品牌 + 表面体系 | `--stardust-blue #2E5BFF`、`--stardust-purple #7B4DFF`、`--stardust-gradient`（`:2-7`）；`--brand-primary #4C6FFF`（`:11`）；`--surface-*`、`--text-*`、`--border-*`、`--radius-*`（`:22-44`）；暗色覆盖 `:root[data-theme="dark"]`（`:69-110`） |
| `frontend/src/styles/chat-theme.css` | 105 个 `--chat-*` 定义；聊天语义层 | `--chat-accent: var(--arco-primary)`（暗色 `:25`、亮色 `:119`）；`--chat-user-bubble`（暗色 `:30`、亮色 `:123`）；`--chat-*` 映射到 `--surface-*` / `--text-*` / `--border-*` |
| `frontend/src/styles/global.css` | 平台基础变量/字号/间距 | `--arco-primary: var(--brand-primary)`（`:20`）；暗色 `:106-118`；`--chat-content-max-width: 1040px`（`:92`）；字号刻度 `:94-102` |
| `pipelines/Treasure-Seeking_Mouse/src/styles.css` | Shadow DOM 内的独立主题 | Tailwind 4 `@theme inline`（`:13-60`）；亮色 token `:62-126`；暗色 `.dark` `:129-172`；品牌绿 `--primary: #218747`（`:90`）、`--helix: var(--primary)`（`:105`）、探矿金 `--gold: #D97706`（`:114`） |
| `frontend/treasure-island/index.tsx` | Shadow DOM 样式注入 | `styles.css?inline`（`:13`）；`@font-face` 提升到 document（`:24`）；`:root` 改写为 `.treasure-island-root`（`:25-26`）；`attachShadow({ mode: 'open' })`（`:46`）；`theme.className` 加 `.dark`（`:69`） |

**结论：token 是“两套完整体系”，不是一套共享体系。** 星尘有 `--stardust-*`、`--brand-*`、`--arco-*`、`--chat-*` 四层；寻宝鼠有 `--background/--primary/--helix/--gold/--pet-*` 另一套，并在 Shadow DOM 内重新定义。CSS 变量虽然能穿透 shadow boundary，但 island 根节点自己覆盖了同名/近义变量，所以不能指望宿主 token 自动统一。

### 3.2 品牌色与硬编码色值

**星尘 AI**

| 颜色 | 位置 | 用途 |
|---|---|---|
| `#2E5BFF` `--stardust-blue` | `tokens.css:2` | AI 名称、能力按钮 hover、canvas 亮色主星 |
| `#7B4DFF` `--stardust-purple` | `tokens.css:3` | 渐变、canvas 紫星 |
| `#4C6FFF` `--brand-primary` | `tokens.css:11` | 主按钮、`--arco-primary`、`--chat-accent` |
| `#8e6cf0` | `data/ai/router.yaml:6` | 星尘 AI 的路由专家身份色；前端消息身份未消费 |
| `#4f8ef7` | `KimiMessageList.vue:39`；`KimiMessageItem.vue:1377、1382、1420、1425` | 默认 agent 色 / `--chat-accent` 回退值 |
| `rgba(79, 142, 247, ...)` | `KimiMessageItem.vue:1378、1383、1441` | feedback hover / 路由徽标背景 |
| `rgba(255,255,255,...)` | `KimiMessageItem.vue:1542-1548` | 用户附件 chip（写死白色透明，未走 token） |
| `#38BDF8` / `#FFFFFF` / `#8FA3FF` | `StardustHero.vue:106-109` | canvas 星尘调色板 |
| `#B9C6FF` / `#7B4DFF` | `StardustHero.vue:200` | canvas 连线/星尘绘制 |
| `#fff` / `rgba(76,111,255,.24)` | `AgentSidebar.vue:86-91` | 新建对话按钮前景与 hover 阴影 |
| `#d4dbf5` / `rgba(118,145,255,.35)` | `AgentSandbox.vue:892、1205` | 能力按钮边框 |

**科研寻宝鼠**

| 颜色 | 位置 | 用途 |
|---|---|---|
| `#218747` `--primary` | `styles.css:90` | 品牌绿主行动色 |
| `--helix: var(--primary)` | `styles.css:105` | 链接、完成图标、品牌强调 |
| `#E8F7EC` `--helix-soft` | `styles.css:106` | 品牌绿浅底 |
| `#D97706` / `#B45309` / `#FEF3C7` | `styles.css:114-116` | 探矿金 / 重点词 / 金块 |
| `oklch(...)` 暗色 | `styles.css:135-171` | 夜探矿洞色板，全部走 oklch |
| `--color-helix` | `styles.css:497-513` | `.id-link` 数据集编号链接，**绿色** |

**硬编码统计（正则 `#[0-9a-fA-F]{3,8}`，含 legacy/测试/资产文件）**

| 范围 | 命中数 | 主要文件 |
|---|---|---|
| `frontend/src/components/ai-chat` | 265 处 / 34 文件 | `KimiMessageItem.vue` 62、`SkillInvocationCard.vue` 17、`ChatCodeCard.vue` 15、`ApprovalCard.vue` 20、`OverdriveProgressCard.vue` 14、`TaskProgressCard.vue` 14、`MessageArtifactGallery.vue` 12、`PendingApprovalBar.vue` 11 |
| `frontend/src/components/agent-workspace` | 44 处 / 7 文件 | `AgentSandbox.vue` 25、`StardustHero.vue` 5、`AgentCapabilityDrawer.vue` 4、`AgentSidebar.vue` 4 |
| `pipelines/Treasure-Seeking_Mouse/src` | 57 处 / 7 文件 | `styles.css` 44、品牌 SVG 资产 11、`treasureBurst.ts` 1、`chart.tsx` 1 |

**关键判断：手册所称“星尘紫”不是当前主强调色。** 主强调色是蓝色 `--brand-primary #4C6FFF` → `--chat-accent`；`--stardust-blue #2E5BFF` 又单独用于 AI 名称；紫色 `--stardust-purple #7B4DFF` 主要出现在渐变和 canvas；路由专家色是 `#8e6cf0`。统一 token 前必须先决定“星尘身份主色”到底是哪一个，否则会把现有三色混用固化。

### 3.3 scoped 样式重复度与潜在冲突

当前寻宝鼠样式在 Shadow DOM 内，**不会与星尘全局样式直接冲突**；但阶段 2 若把两端放进同一棵 Vue 树/同一作用域，下列同名或同义类会冲突：

| 语义 | 星尘 | 寻宝鼠 | 冲突点 |
|---|---|---|---|
| 消息头 | `.message-header` / `.message-identity` / `.message-name`，`KimiMessageItem.vue:1389-1421` | Tailwind `flex items-baseline`，`ChatMessage.tsx:142-149` | 同名 `.message-header`、`.message-name` 语义不同 |
| 用户气泡 | `.message-content.user-bubble`，`KimiMessageItem.vue:1518-1530` | `rounded-xl rounded-br-sm bg-primary`，`ChatMessage.tsx:123` | `.message-content` 同名，圆角/最大宽度/颜色不同 |
| 助手卡片 | `.message-content.ai-card`，`KimiMessageItem.vue:2220-2225` | `rounded-xl rounded-tl-sm border border-border bg-card`，`ChatMessage.tsx:154` | `.message-content` 同名 |
| 附件 chip | `.attachments` / `.attachment-tag`，`KimiMessageItem.vue:1531-1549` | 无 | `.attachment-*` 若共享会与寻宝鼠未来附件冲突 |
| 输入区 | `.ai-composer` / `.input-toolbar` / `.composer-input`，`KimiChatInput.vue:1505-1767` | `.composer` / `.composer-input` / `.composer-model`，`Composer.tsx:85-176` | `.composer`、`.composer-input` 同名 |
| welcome | StardustHero 自有 scoped，`StardustHero.vue:208-217` | `.welcome-workspace` / `.welcome-content` / `.welcome-heading`，`EmptyState.tsx:30-41` | `.welcome-*` 命名空间重叠 |
| 过程 chip | 无同名 `.tool-trace`；工具卡为 `.tool-results` / `.timeline-tool-entry`，`KimiMessageItem.vue:1144-1173、2166-2169` | `.tool-trace` 由 Tailwind 内联类构成，`ToolTrace.tsx:44-78` | 语义重复，类名不同 |
| 侧栏 | `.agent-sidebar`，`AgentSidebar.vue:38-47` | `.treasure-app` 内 `aside`，`FullPresentation.tsx:72-77` | 宽度 60px vs 56px |

**建议：** 阶段 2 抽出的类统一加 `agent-chat-` 前缀（手册要求），并避免直接复用 `.message-*` / `.composer*` / `.welcome-*`。

### 3.4 暗色模式实现

- **星尘**：`tokens.css:69-110` 用 `:root[data-theme="dark"]` 覆盖全局变量；`chat-theme.css:8-79` 再覆盖聊天语义变量；主题切换在用户菜单 `DefaultLayout.vue:421-438`。组件大多走 `--chat-*`，但仍有写死 `rgba`/`#4f8ef7` 回退。
- **寻宝鼠**：`styles.css:129-172` 用 `.dark` 覆盖 island 根上的变量；`index.tsx:69` 根据 `props.context.theme` 给 `.treasure-island-root` 加 `.dark`；`TreasureOriginalDisplay.vue#syncAppearance` 用 `MutationObserver` 监听 `documentElement` 的 `class/data-theme/lang`。
- **结论**：两套暗色模式互不感知。统一 token 时不能只改星尘的 `:root[data-theme=dark]`，还必须给 island 根提供同名映射或让 island 消费宿主变量。

---

## 4. 消息数据结构与 SSE 事件清单

### 4.1 星尘 `ChatMessage`

定义：`frontend/src/components/ai-chat/types.ts:171-242`。

| 字段 | 存在 | 说明/位置 |
|---|---|---|
| `id` / `backendMessageId` | 是 | `types.ts:172-174` |
| `role` / `content` | 是 | `types.ts:181-182` |
| `agent_id`（顶层） | **否** | 未在 `ChatMessage` 顶层找到；身份在 `senderAgent.id`（`:203-210`）或 `routedAgent.agentId`（`:35-52`） |
| `senderAgent` | 是 | `{ id, name, avatar?, color?, role?, round? }`，`types.ts:203-210` |
| `routedAgent` | 是 | `RoutedAgentInfo`，`types.ts:35-52` |
| `modelName` | 是 | `types.ts:186-187` |
| `tokens` | 是 | `TokenInfo { input, output, total, cached, cachedOutput }`，`types.ts:6-14` |
| `thinkingDuration` | 是 | 秒，`types.ts:184-185` |
| `timeline` | 是 | `TimelineSegment[]`，`types.ts:189-191、252-261` |
| `toolCalls` | 是 | `ToolCall[]`，`types.ts:291-318`；**没有 `durationMs` 字段** |
| `skillInvocations` | 是 | `SkillInvocationCard[]`，含 `duration_ms`，`types.ts:264-282` |
| `createdAt` | 是 | `types.ts:241` |
| `feedback` | 是 | `'like' \| 'dislike'`，`types.ts:225` |
| `status` / `error` / `finishReason` | 是 | `types.ts:233-240` |
| `suggestions` / `attachments` / `charts` / `webSources` / `knowledgeSources` | 是 | `types.ts:194-236` |
| 过程步骤（统一数组） | 否 | 没有 `processSteps[]`；过程由 `timeline` + `toolCalls` + `routedAgent` + `overdriveProgress` + `fanoutProgress` 分散表达 |

### 4.2 寻宝鼠 `ResearchMessage` / `ChatUIMessage`

API 类型：`frontend/src/api/researchAgent.ts:72-82`。

| 字段 | 存在 | 说明/位置 |
|---|---|---|
| `message_id` | 是 | `researchAgent.ts:73` |
| `role` / `content` / `status` | 是 | `researchAgent.ts:74-76` |
| `metadata_json.proposals` | 是 | `researchAgent.ts:78` |
| `metadata_json.events.cards` | 是 | `researchAgent.ts:79` |
| `metadata_json.events.tools` | 是 | 工具事件快照，含 `name/label/status/ms` |
| `metadata_json.events.grounding` | 是 | `researchAgent.ts:79` |
| `metadata_json.events.polariseq` | 是 | `researchAgent.ts:79` |
| `metadata_json.events.error` | 是 | `researchAgent.ts:79` |
| `created_at` | 是 | `researchAgent.ts:81`；但 `researchMessageView` 未映射到 `ChatUIMessage` |
| `agent_id` | **否** | 未在 `ResearchMessage` 找到 |
| `modelName` / `tokens` | **否** | 未在 `ResearchMessage` 找到 |
| `feedback` | **否** | 未在 `ResearchMessage` 找到 |
| 消息级耗时 | **否** | 只有工具级 `ms`，没有整轮耗时 |

视图层 `ChatUIMessage`：`pipelines/Treasure-Seeking_Mouse/src/components/chat/ChatMessage.tsx:26-40`。

| 字段 | 存在 | 说明 |
|---|---|---|
| `id` / `role` / `content` | 是 | `ChatMessage.tsx:27-29` |
| `cards` / `toolLogs` / `boost` / `grounding` | 是 | `ChatMessage.tsx:30-35` |
| `completion` / `streaming` / `liveTools` / `error` | 是 | `ChatMessage.tsx:36-39` |
| `createdAt` / `tokens` / `modelName` / `feedback` / `attachments` | **否** | 未在 `ChatUIMessage` 找到 |

### 4.3 SSE endpoint 与事件

**星尘 AI**

- Endpoint：`POST /api/v1/chat/stream`，`frontend/src/composables/useAgentChatStream.ts:609`。
- 事件分支：`useAgentChatStream.ts:718-1172`。
- 事件类型（按 switch 分组）：

| 分组 | 事件 |
|---|---|
| Agent 轮次 | `agent_turn_started`、`agent_context_reinjected`、`agent_turn_continued`、`agent_final_result`、`agent_turn_failed`、`agent_loop_guard_triggered` |
| 文本/推理 | `text`、`content`、`message`、`delta`、`reasoning` |
| 工具/技能 | `tool_call`、`tool_result`、`tool_output`、`skill`、`web_search_results` |
| 模式/工作台 | `mode_changed`、`studio_promoted` |
| 协作室/超频 | `room_speech`、`room_speech_delta`、`overdrive_progress`、`overdrive_approval_request`、`subagents` |
| 调度/可靠性 | `schedule_fallback`、`schedule_warning`、`worker_stalled`、`loop_guard_triggered`、`round_limit`、`context_compressed` |
| 路由/专家 | `route`、`handoff`、`consultation`、`collaboration_route` |
| 审批/澄清 | `approval_request`、`approval_resolved`、`ask_request`、`plan` |
| 协作 Case | `agentteams_case` |
| 终态 | `error`、`done` |

**科研寻宝鼠**

- Endpoint：`POST /api/v1/research-agent/sessions/{sessionId}/messages:stream`，`frontend/src/api/researchAgent.ts:120-122`。
- 官方能力清单：`src/cygnusx/application/schemas/research_agent.py:66`：

```text
delta, tool, cards, polariseq, grounding, end, error, cancel
```

- 前端还处理/观察到：
  - `platform_tool`：`TreasureResearchWorkbench.vue:125`（仅用于标记，不在官方清单）。
  - `interrupted`：`researchPresentation.ts:77、114` 作为终态错误文案；后端在异常收尾时持久化，见 `research_treasure_service.py:740-742`。
- 断点续传：`Last-Event-ID`，`TreasureResearchWorkbench.vue:109-133`；解析器 `researchPresentation.ts:93-129`。
- 事件持久化：`research_treasure_service.py:614-631`；终态快照 `:626-631`。
- **没有 `thought` / `status` 事件**：官方清单未列，`applyResearchEvent` 也未处理；寻宝鼠的消息思考态只靠`streaming` + 空内容文案（`ChatMessage.tsx:165-167`）。

### 4.4 赞/踩/复制与埋点

- 星尘反馈 API：`PUT /api/v1/chat/sessions/{sessionId}/messages/{messageId}/feedback`，body `{ rating, comment }`，`frontend/src/api/chat.ts:201-216`。
- 星尘 store：`submitMessageFeedback` 做乐观更新/失败回滚，`agentHub.ts:2033-2055`。
- **反馈协议没有 `agent_id`**：`chat.ts:209` 只发 `rating/comment`；前端也没有在 feedback 中附带 agent 身份。
- **未在代码中找到独立埋点事件**：复制、点赞、点踩均只触发本地 UI/父组件事件或上述 REST 调用，没有 analytics/telemetry 事件上报字段。
- 寻宝鼠：没有赞/踩；复制为本地 `copyText`（`ChatMessage.tsx:63-73、119-121、191-197`），没有反馈 API。

### 4.5 Agent 身份配置现状

- 后端 YAML 已有身份字段：`data/ai/router.yaml:2-6`（`name: 星尘 AI`、`avatar: "🧭"`、`color: "#8e6cf0"`）、`:13`（`welcome_message`）。
- 前端类型也有 `AgentTemplate.avatar/color`：`frontend/src/types/agent.ts:121-128`。
- **但星尘消息项没有消费这些字段**：
  - `KimiMessageList` 的 `agentAvatar/agentColor` 默认值是 `🤖` / `#4f8ef7`（`KimiMessageList.vue:34-39`）。
  - `AgentSandbox` 只向 `KimiMessageList` 传了 `:model-name`（`AgentSandbox.vue:648-660`），没有传 `agent-name/avatar/color`。
  - `KimiMessageItem` 的身份名优先 `senderAgent.name` → `modelName` → `agentName`（`:415-421`）；头像/颜色优先 `senderAgent` → props 默认（`:420-421`）。
  - 欢迎语 `welcome_message` 未被 `StardustHero` 消费；首页是按时段硬编码问候（`StardustHero.vue:12-18、208-217`）。
  - placeholder 硬编码在 `AgentSandbox.vue:386-388` 与 `KimiChatInput.vue:119`。
- 寻宝鼠：品牌名/欢迎语/placeholder/免责声明都在 i18n 字典，`zh.ts:69-71、110-119、155-161`；没有 Agent 身份配置入口。

---

## 5. 分级风险清单

### 5.1 阻断统一改造

**B1. 两套运行时 + Shadow DOM + 独立构建边界**

- 星尘是 Vue/naive-ui；寻宝鼠是 React/Tailwind/Radix，挂在 open Shadow DOM（`treasure-island/index.tsx:46`）。
- island 样式由 `styles.css?inline` 注入，`:root` 被改写为 `.treasure-island-root`（`index.tsx:24-26`），`theme` 通过 class 切换（`:69`）。
- `npm run predev/prebuild` 会先构建 island（`frontend/package.json:12-13`）；构建脚本从子模块 `pipelines/Treasure-Seeking_Mouse` 取 `src/shared/archive`，只覆盖父仓的 `FullPresentation.tsx` / `index.tsx`（`frontend/scripts/build-treasure-island.mjs:1-70`）。
- 影响：**不能把星尘的 Vue 组件直接给寻宝鼠用**；也不能在父仓随意改 React 聊天组件（README 明确“共享样式和组件必须在子仓修改”，`frontend/treasure-island/README.md:9-17`）。阶段 2 必须先决定 React 共享组件的归属和 overlay 策略。

**B2. 数据模型无法支撑统一的 meta / 反馈 / 埋点**

- 星尘缺顶层 `agent_id`；`ToolCall` 无 `durationMs`（`types.ts:291-318`）。
- 寻宝鼠缺 `tokens`、`modelName`、消息级 `createdAt` 视图映射、`feedback`、`agent_id`（`researchAgent.ts:72-82`；`ChatMessage.tsx:26-40`）。
- 反馈 API 无 `agent_id`（`chat.ts:201-216`）。
- 影响：统一 `MessageMetaRow` 和 `FeedbackBar` 前，必须先补数据契约；只做视觉抽取会出现大量 `undefined` 或假字段。

**B3. 星尘消息/输入组件与 store 深度耦合，寻宝鼠组件是纯展示**

- `KimiMessageItem` 直接 import `useAgentHubStore`、`apiClient`、`chatApi`、`usePyodide`（`KimiMessageItem.vue:16-40`），并在组件内处理反馈、工具确认、证据链等。
- `KimiChatInput` 直接使用 `chat/agentHub/auth/modules/goalRuntime` 五个 store（`KimiChatInput.vue:54-63`），并直接调 `apiClient`/`agentTeamsApi`。
- 寻宝鼠 `ChatMessage` 以 props + 局部 UI 状态为主，只有 `evidenceBus` 一个薄通道（`ChatMessage.tsx:1-24、90-113`）。
- 影响：抽取星尘组件不是“搬模板”，必须先做 props/events 解耦；否则共享组件会反向依赖星尘 store。

**B4. 寻宝鼠模型切换器未接线**

- `TreasureOriginalDisplay.vue:35`：`modelOptions: ['平台默认模型']`；`:39`：`onSelectModel: () => {}`。
- `TreasureResearchWorkbench.vue:315-328` 没有把 `currentSession.model_id` 或平台模型列表传给 island。
- 影响：统一“模型切换器”时，寻宝鼠只能显示假选项；阶段 2 要么补数据，要么显式 `disabledSlots: ['modelSwitcher']`。

### 5.2 体验不一致

**E1. meta 行字段严重不对称**

- 星尘：Tokens + 时间（`KimiMessageItem.vue:861-875、947-951`）。
- 寻宝鼠：品牌 + 检索次数/耗时（`ChatMessage.tsx:142-148`）。
- 结果：同一个“meta 行”组件在两端没有共同字段，必须做归一化。

**E2. 反馈 / 重新生成 / 复制不对等**

- 星尘：助手有赞/踩/复制（`KimiMessageItem.vue:1281-1315`）；普通完成态没有重新生成；错误/空态才有（`:1318-1329`）。
- 寻宝鼠：有复制/重新生成（`ChatMessage.tsx:191-204`）；没有赞/踩。
- 复制模式也不同：星尘支持纯文本/Markdown/引用（`MessageActionBar.vue:157-177`）；寻宝鼠只复制正文（`ChatMessage.tsx:194-195`）。

**E3. 实体高亮与手册描述不一致**

- 寻宝鼠链接是绿色（`styles.css:497-513`），不是橙色。
- 正则仅 GSE/GSM/GO/PMID（`linkify.ts:13-18`），**不含 SRR/PRJNA**，但 placeholder 明示支持 SRR（`zh.ts:155-156`）。
- “意图规划/核验” chip 被 `ChatMessage.tsx:96-98` 过滤，不会显示。
- 星尘没有数据集编号高亮；只有通用 URL linkify（`setup.ts:22`）。

**E4. 身份与品牌皮肤硬编码**

- 星尘助手头像/名称回退到 `🤖` / `modelName`（`KimiMessageList.vue:34-39`；`KimiMessageItem.vue:415-421`），`router.yaml` 的 `avatar/color/welcome_message` 未贯通。
- 寻宝鼠固定 BrandMark + `brand.name`（`ChatMessage.tsx:137-143`），没有每 Agent 身份。
- 星尘没有页脚免责声明；寻宝鼠有（`Composer.tsx:172`；`zh.ts:160-161`）。

**E5. 外壳、导航顺序、主题/语言不一致**

- 平台顶部导航：账户余额 → 通知 → 帮助（`DefaultLayout.vue:488-534`）；主题在用户菜单（`:421-438`）。
- 星尘：60px 图标栏（`AgentSidebar.vue:38-47`）+ 会话 header（模型、能力、token）（`AgentSandbox.vue:575-636`）。
- 寻宝鼠：56px 图标栏 + 270px 展开栏（`FullPresentation.tsx:72-78`）+ 自有 header（刷新/排行榜/统计/关于/资产/能力/语言/桌宠/主题）（`:80-101`）。
- 语言切换只在寻宝鼠 header（`FullPresentation.tsx:97`）；星尘聊天壳未找到切换入口。

**E6. 流式期间的发送行为不一致**

- 星尘有消息队列（`AgentSandbox.vue:694-709`）。
- 寻宝鼠 `Composer` 预留 `onQueue`，但平台未传；流式中按 Enter 直接返回（`Composer.tsx:73-80`）。

### 5.3 技术债

**T1. 组件体量与硬编码色值**

- `KimiMessageItem.vue` 2270 行、`KimiChatInput.vue` 2520 行、`AgentSandbox.vue` 1206 行。
- `ai-chat` 目录 265 处 hex（含 legacy/测试），`agent-workspace` 44 处，寻宝鼠 `styles.css` 44 处。详见 §3.2。
- 结果：任何视觉统一都会同时触碰大量样式和逻辑，回归面大。

**T2. token 重复与死回退**

- `--chat-bg-soft` 只在 `KimiMessageItem.vue:1441` 被使用，但在 `chat-theme.css` 中未找到定义，实际永远走 fallback `rgba(127,127,127,0.08)`。
- 多处 `var(--chat-accent, #4f8ef7)`、`var(--text-tertiary, #9aa3b2)` 等回退值把旧色板固化在组件里（`KimiMessageItem.vue:1369、1377、1382、1420、1425、1442`）。
- `--stardust-blue` 与 `--brand-primary` 两个蓝色并存（`tokens.css:2、11`），语义边界不清。

**T3. 默认 props / 配置未贯通**

- `KimiMessageList` 的 `agentAvatar/agentColor` 默认值未被 `AgentSandbox` 覆盖（`KimiMessageList.vue:34-39`；`AgentSandbox.vue:648-660`）。
- `router.yaml` 的 `avatar/color/welcome_message` 未在前端消费（`router.yaml:2-13`）。
- 结果：Agent 身份“有配置但没生效”，统一皮肤时容易误以为已配置化。

**T4. 刻意缺失没有显式声明**

- 寻宝鼠缺少 @、/、深度思考、工作台、语音、通用附件；从 `Composer.tsx` 能力面看像是刻意精简，但代码中没有 `disabledSlots` 或等价声明。
- 结果：阶段 2 无法区分“刻意不提供”和“漏做”；手册也明确要求用 `disabledSlots` 显式声明（手册 §约束）。

**T5. SSE 消费与事件映射双份维护**

- 星尘：`useAgentChatStream.ts:718-1172` 的大 switch。
- 寻宝鼠：`researchPresentation.ts:81-90` 的增量映射 + `consumeResearchStream`（`:93-129`）。
- 结果：统一过程卡时不能假设事件字段一致；需要各自 adapter 产出统一 ViewModel。

### 5.4 低成本止血点（不依赖组件抽取）

| 止血点 | 改动量 | 价值 |
|---|---|---|
| `AgentSandbox` 向 `KimiMessageList` 透传 `agent-name/avatar/color`（`AgentSandbox.vue:648-660`） | 1 处模板 + 1 处 props | 立即让星尘消息身份不再回退到 `🤖`/`#4f8ef7` |
| 寻宝鼠把 `currentSession.model_id` + 平台模型列表传入 island（`TreasureResearchWorkbench.vue:315-328`） | 1 个 computed + island props | 让模型选择器从“假控件”变真，或显式置灰 |
| 反馈 API 增加 `agent_id`（`chat.ts:201-216`） | 前后端各 1 处 | 为统一 FeedbackBar 埋点打基础 |
| 寻宝鼠补 `SRR/PRJNA/ENA` 正则（`linkify.ts:13-18`） | 1 个规则表 | 消除 placeholder 与行为不一致 |
| 统一 `.id-link` 颜色到 `--chat-accent` 或身份 token（`styles.css:497-513`） | 1 个变量映射 | 阶段 1 的 token 统一先落地 |
| 星尘把 `#4f8ef7` 回退改为 `var(--chat-accent)` / 身份 token（`KimiMessageItem.vue:1377、1382、1420、1425`） | 少量替换 | 去掉第二套蓝色 |
| 给 `--chat-bg-soft` 补定义或删除 fallback（`KimiMessageItem.vue:1441`） | 1 处 | 去掉死回退 |
| 给寻宝鼠补 `disabledSlots` 声明（@、/、deepThinking、workbench、voice、genericAttachment） | 1 个契约对象 | 把“刻意精简”从推断变成事实 |

---

## 6. 演进建议

### 6.1 判断：不要抽一个共享 SFC

两界面的差异是**运行时 + 组件库 + 数据源**三重差异，不是同一框架内的样式分叉。抽一个 Vue SFC 无法被 React island 消费；抽一个 React 组件又无法被星尘的 naive-ui 生态直接复用。可行的路线是：

> **契约先行 + 双渲染器**：统一设计 token、消息 ViewModel、能力插槽和交互语义；Vue 与 React 各自实现同一份规格，逐条对齐，而不是复制代码。

这与手册“禁止复制分叉”不冲突：共享的是**契约与测试**，不是同一份源码。

### 6.2 推荐目录

| 层 | 推荐位置 | 内容 |
|---|---|---|
| Token 契约 | `frontend/src/styles/agent-chat-tokens.css` | `--agent-chat-identity-*`、`--agent-chat-bubble-*`、`--agent-chat-meta-*`、`--agent-chat-process-*`、`--agent-chat-feedback-*`；星尘与 island 各自把现有 token 映射到这一层 |
| ViewModel 契约 | `frontend/src/components/agent-chat/contract.ts` | `AgentChatMessageView`、`AgentChatIdentity`、`AgentChatMeta`、`AgentChatProcess`、`AgentChatSlots`、`AgentChatActions` |
| 星尘适配器 | `frontend/src/components/agent-chat/adapters/agentHub.ts` | `ChatMessage` → `AgentChatMessageView` |
| 寻宝鼠适配器 | `frontend/src/components/agent-chat/adapters/research.ts` | `ResearchMessage`/`ChatUIMessage` → `AgentChatMessageView` |
| Vue 共享组件 | `frontend/src/components/agent-chat/` | `AgentChatMetaRow.vue`、`AgentChatFeedbackBar.vue`、`AgentChatEntityChip.vue`、`AgentChatProcessCard.vue`、`AgentChatInputDock.vue`、`AgentChatMessageShell.vue` |
| React 共享组件 | 方案 A：`frontend/treasure-island/agent-chat/`（父仓 overlay）；方案 B：`pipelines/Treasure-Seeking_Mouse/src/components/chat/agent-chat/`（子仓） | 与 Vue 组件同名同 props 的 React 实现；方案 A 需要扩展 `build-treasure-island.mjs` 的 overlay 列表，方案 B 需要子仓提交 + 父仓指针 |
| 测试 | `frontend/src/components/agent-chat/__tests__/` + island 侧同构测试 | adapter 单测、消息类型快照、视觉回归清单 |

**归属建议：** 如果目标是“平台统一、父仓可独立迭代”，选方案 A（父仓 overlay）；如果目标是“保持寻宝鼠子仓可独立发行”，选方案 B（子仓实现）。两条路都必须让 `frontend/treasure-island/README.md:9-17` 的边界说明同步更新，否则下一位维护者仍会按“共享组件必须改子仓”执行。

### 6.3 拆分顺序（从低耦合到高耦合）

| 顺序 | 组件 | 为什么先/后 | 关键依赖 |
|---|---|---|---|
| 0 | Token 契约 + ViewModel 契约 | 不改变视觉，先让两端有共同语言 | §3、§4 |
| 1 | `AgentChatFeedbackBar` | 纯 props/events，最容易对齐；同时把 `agent_id + message_id + action` 埋点补上 | 反馈 API、`feedback` 字段 |
| 2 | `AgentChatMetaRow` | 纯格式化；先补字段再统一展示 | tokens、时间、model、searchCount、duration |
| 3 | `AgentChatEntityChip` | 纯文本/正则/链接；可独立于消息壳 | `linkify` 规则表、`IdLink` |
| 4 | `AgentChatProcessCard` | 需要 steps/progress 两种 adapter；先把两侧事件归一到 `ProcessStep[]` | `toolCalls`、`toolLogs`、`overdriveProgress`、`fanoutProgress` |
| 5 | `AgentChatInputDock` | 最重：附件、@、/、深度思考、工作台、队列、模型；必须用 `disabledSlots` | `KimiChatInput` 的 store 解耦、`Composer` 的能力声明 |
| 6 | `AgentChatMessageShell` | 最后：包住现有消息渲染，承接气泡/头部/操作栏；回归面最大 | 1~5 全部稳定后 |

**理由：** 1~3 是纯展示，失败可快速回滚；4 需要数据归一；5 涉及 store 与平台能力；6 会碰流式/虚拟列表/滚动吸附，必须最后做。

### 6.4 统一 ViewModel 与 `disabledSlots`

建议契约（示意）：

```ts
export interface AgentChatMessageView {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  identity: {
    agentId?: string
    name: string
    avatar?: string
    color?: string
    modelName?: string
  }
  meta: {
    tokens?: { input?: number; output?: number; total?: number; cached?: number }
    durationMs?: number
    createdAt?: string
    searchCount?: number
  }
  process: {
    mode: 'none' | 'steps' | 'progress'
    steps?: Array<{ id: string; label: string; status: 'running' | 'done' | 'error'; durationMs?: number }>
    progress?: { completed: number; total: number; phase?: string; percent?: number }
  }
  entities: {
    accessions?: Array<{ id: string; kind: string; url: string }>
    files?: Array<{ name: string; kind?: string; url?: string }>
    tools?: Array<{ name: string; label?: string; status?: string }>
  }
  actions: {
    feedback?: 'like' | 'dislike'
    regenerate?: boolean
    copyModes?: Array<'plain' | 'markdown' | 'citation'>
  }
  slots: AgentChatSlots
}
```

`disabledSlots` 建议：

```ts
// 寻宝鼠
{
  mention: false,
  slash: false,
  deepThinking: false,
  workbench: false,
  voice: false,
  genericAttachment: false,
  disclaimer: true,     // 有品牌免责声明
}
// 星尘
{
  mention: true,
  slash: true,
  deepThinking: true,
  workbench: true,
  voice: false,         // 未实现
  genericAttachment: true,
  disclaimer: false,    // 未实现，是否补产品决定
}
```

> 注意：上表的 `false` 表示“该槽位不提供”，需要在阶段 2 以显式配置落地；本报告只是建议，不是现状。现状是两端都没有 `disabledSlots`。

### 6.5 不建议的做法

1. **不要把 React island 嵌进星尘的 Vue 消息列表**：会引入第二套 Shadow DOM、两套 i18n、两套主题，且滚动/虚拟列表不可控。
2. **不要为了共享而把寻宝鼠整体迁移到 Vue**：违反手册“禁止推倒重写”，且会破坏子仓独立发行。
3. **不要复制 `KimiMessageItem` 到 React 或复制 `ChatMessage` 到 Vue**：手册明确禁止复制分叉；应共享 ViewModel 和测试，各自渲染。
4. **不要先做输入区**：`KimiChatInput` 的 store 耦合和寻宝鼠的能力差异会把统一拖入长尾。

### 6.6 验收建议

- 每个消息类型（纯文本、工具调用、路由卡、超频进度、文献卡、错误、空内容、用户附件）在两端各留一张 golden 截图/结构快照。
- adapter 单测覆盖：星尘 `ChatMessage` → ViewModel、寻宝鼠 `ResearchMessage` → ViewModel、缺字段降级。
- SSE 不改：阶段 2 只做展示层，保持 `/chat/stream` 与 `messages:stream` 的事件契约不变。
- 类名前缀：所有抽取组件/样式使用 `agent-chat-`，避免 §3.3 的 `.message-*` / `.composer*` / `.welcome-*` 冲突。
- 逐条消息目检：暗色、窄屏、IME、流式追加、断流恢复、长消息滚动。

---

## 7. 本次未修改代码

- 未修改任何 `.vue` / `.ts` / `.tsx` / `.css` / `.scss` / `.yaml` / `.json` 文件。
- 未修改 `pipelines/Treasure-Seeking_Mouse` 子模块，未改动父仓子模块指针。
- 唯一新增文件为本报告：`docs/info/26.10.26/CygnusX助手界面统一_阶段0现状盘点报告.md`。
- 下一步应先把本报告交给产品/前端核对，确认 §0 的差异项与 §6 的目录归属，再进入阶段 1；在核对前不开始任何代码改造。
