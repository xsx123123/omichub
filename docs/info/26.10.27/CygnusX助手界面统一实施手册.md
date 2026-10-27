# CygnusX 助手聊天界面统一实施手册

> 版本 v1.1 · 2026-10-26（v1.0 同日初版；v1.1 纳入阶段0报告核对结论，见文末 Part II）
> 适用范围：星尘 AI（主助手）、科研寻宝鼠（检索助手）及后续接入平台的所有 Agent 聊天界面
> 施工方式：本手册按阶段组织，每阶段一个 paste-ready 提示词块，按阶段投喂编码 Agent；每阶段独立可验、独立提交。验收权在用户手里，不接受编码 Agent 自报通过。
> 依据：2026-10-26 两界面截图实证 + 业界通行做法（Copilot Studio / ChatGPT GPTs / Claude Projects 均为"一套聊天组件 + 每 Agent 身份槽位定制"；多品牌设计系统共享原子组件、差异只走 token）+ 阶段0现状盘点报告（680 行，7 节）。

## 0. 结论与总原则

**要统一——但统一的是"骨架"，不是"皮肤"。**

- **统一（骨架层）**：消息气泡系统、消息元信息行（meta row）、过程可视化卡、实体高亮语义色、输入 dock 基础能力、反馈操作（赞/踩/复制）。
- **保留（皮肤层）**：每个 Agent 的名称、头像、主题色（accent token）、欢迎语、placeholder 文案、品牌按钮文案（如「下铲挖宝」）、领域免责声明（如 NCBI/NGDC 那句）。
- **主题色规则**：每 Agent 一个 accent token，只染固定槽位（见 §2.1），不许各页面自由用色。
- **技术路线（v1.1 修订）**：契约先行 + 双渲染器。阶段0报告实证寻宝鼠是「Vue 外壳 → Shadow DOM → React 19 island」，与星尘（Vue3 + naive-ui）零共享，共享 Vue SFC 路线不成立，详见 Part II。

技术栈前提：Vue3 + Pinia + 现有样式体系（星尘）；React 19 island（寻宝鼠聊天面）。所有改造锚定现有组件，先读代码再改，**禁止推倒重写，不改路由、不改功能逻辑**。

## 1. 现状问题清单（截图实证 + 阶段0报告校准）

### P1　过程可视化两套语言
- 现状：寻宝鼠＝绿色对勾步骤 chip + 每步耗时（意图规划 0ms → 跨库搜索 1165ms → GEO 1156ms → SRA 1707ms → 编号核验 1179ms）；星尘＝STELLAR ROUTER 路由卡（展示意图 + 置信度）。
- spec：抽统一 ProcessCard 组件，一个组件两种模式（steps / route），见 §2.3-3。
- 预期：用户在任何助手界面看到"AI 正在干什么"都是同一读法。

### P2　消息元信息行两套格式
- 现状：寻宝鼠内联在助手名后（`科研寻宝鼠 · 3次检索 · 4028ms`）；星尘是独立一行（`deepseek-v4-flash` badge + `通用助手` + `Tokens: 23131 ↑22955 ↓176` + `10/26 14:21`）。
- spec：统一 MessageMetaRow 组件，字段顺序固定，统计信息走 slot，见 §2.3-2。

### P3　实体高亮颜色没有语义规则
- 现状（v1.1 修正）：阶段0报告代码实证——寻宝鼠数据集编号链接为 `--color-helix` 绿（非截图判断的橙），且识别正则仅覆盖 GSE/GSM/GO/PMID，不含 SRR/PRJNA（placeholder 声称支持 SRR，属承诺未兑现，已列入 Part II 阶段0.5 止血包）；星尘文件 chip 紫色。颜色按助手各自定，全平台无语义规则。
- spec：落全局语义色板（数据集/文件/工具各占一色，不随 Agent accent 变化），见 §2.2。

### P4　输入区能力断层
- 现状：星尘有附件、@ 引用、/ 快捷命令、深度思考、进入工作台的完整工具条；寻宝鼠只有输入框 + 「下铲挖宝」单按钮。
- spec：ChatInputDock 基础槽位全助手一致；某槽位刻意不提供的，在 identity 配置里显式声明 disabled + 理由，不许静默缺失，见 §2.3-5。

### P5　反馈操作缺失（寻宝鼠）
- 现状：星尘消息有 👍👎📋；寻宝鼠没有。
- spec：FeedbackBar 全助手必备，埋点事件统一带 `agent_id + message_id`——评价数据是后续路由优化的原料，不能有的收、有的不收。（v1.1 补充：反馈 API 现状仅 {rating, comment} 无 agent_id，须在阶段1契约层先补。）

### P6　壳层共享控件位置语言不一致
- 现状：寻宝鼠顶栏右侧＝全局只读/项目数据资产/刷新下载能力/EN/主题；星尘＝余额/通知 99+/帮助。工具页与主助手壳可以不同，但共享控件（语言、主题、帮助）的位置顺序要一致。

## 2. 统一设计规范

### 2.1 Agent 身份配置（皮肤层）

每个 Agent 一份 identity 配置，界面从配置读皮肤：

```ts
interface AgentIdentity {
  agentId: string
  name: string          // 星尘 AI / 科研寻宝鼠
  avatar: string
  accent: string        // 主色 hex：星尘 = #4C6FFF（--brand-primary，v1.2 拍板，同时收敛 #2E5BFF 双蓝；紫色仅留装饰渐变）；寻宝鼠 = 现状绿 #218747（--primary）
  greeting: string      // 欢迎语
  placeholder: string   // 输入框 placeholder
  sendLabel?: string    // 品牌发送文案，如「下铲挖宝」；缺省为发送图标
  disclaimer?: string   // 页脚免责声明
  disabledSlots?: string[]  // 刻意不提供的 dock 槽位 + 注释理由
}
```

accent 通过 CSS 变量注入聊天容器根节点：

```css
--agent-accent         /* 现状色值登记 */
--agent-accent-soft    /* accent 10% 透明度，派生，不手写 */
--agent-accent-contrast /* accent 上的文字色，默认白 */
```

**accent 只染五个固定槽位**：①头像底色　②用户气泡背景　③发送/主 CTA 按钮　④步骤完成态对勾　⑤正文小标题强调色。其余一律中性色或语义色。accent 上白字对比度须 ≥ 4.5:1，不满足时加深 accent，不改字色。

### 2.2 语义色板（全局固定，不随 Agent 变化）

| 语义 | 用途 | 色值 | 说明 |
|---|---|---|---|
| `--sem-dataset` | GSE/GSM/SRR/PRJNA/ERX 等数据集编号 | 沿用代码实证现状 `--color-helix` 绿（hover 加深一档） | v1.1 修正：截图误判为橙；与寻宝鼠 accent 同色可接受（染色槽位不同：链接下划线 vs 填充按钮） |
| `--sem-file` | 工作区文件引用 chip | `#4F7FF2`（蓝，12px 圆角 chip + 前置图标） | 星尘现状紫 chip 改成语义蓝 |
| `--sem-tool` | @引用的工具/技能 chip | `#0E9F8A`（青） | 新增 |
| 普通外链 | 正文超链接 | 跟随 `--agent-accent` | — |

### 2.3 统一组件清单（AgentChat 组件族，v1.1 起为契约层 + 双渲染器）

1. **AgentChatShell**：消息列 + 输入 dock 的布局容器。工具页壳与主助手壳可不同，但消息区与输入区结构一致。
2. **MessageMetaRow**：`小头像 + Agent名 + 模型badge + Tokens ↑in/↓out + 统计slot + 时间戳`。星尘的 Tokens 数据与寻宝鼠的「3次检索·4028ms」都作为统计 slot 内容填入。（v1.1 修正：星尘现状无独立模型 badge，模型名是助手身份名的回退——契约层补独立 modelName 字段，见 Part II 阶段1。）
3. **ProcessCard**：`props { mode: 'none' | 'steps' | 'progress', steps: [{id, label, status, durationMs}], progress: {completed, total, phase?, percent?} }`（v1.2 修正：采用阶段0报告 §6.4 的 ViewModel——process 只分 none/steps/progress；路由卡的"谁接手 + 意图 + 置信度"归 `identity.routedAgent` 表达，做成与 ProcessCard 同族外观的独立通知卡，不占 process 模式）。寻宝鼠检索链路用 steps 模式（对勾 + 耗时 chip，对勾染 accent）；星尘 Overdrive/Fanout 用 progress 模式。卡片统一：圆角 12px、1px 边框、标题行左图标右状态。
4. **EntityChip**：`type ∈ dataset | file | tool`，按 §2.2 语义色板渲染；GSE/GSM/SRR 一律走 dataset，工作区文件走 file。
5. **ChatInputDock**：基础槽位全助手一致（附件、@、/、深度思考、进入工作台、发送）；Enter 发送、Shift+Enter 换行全平台一致；agent-specific 动作走扩展插槽，品牌文案走 `sendLabel`。
6. **FeedbackBar**：👍👎📋 全助手必备；埋点事件统一 `agent_id + message_id + action`。

## 3. 分阶段实施与提示词

> **v1.1 修订（2026-10-26 阶段0报告核对后）**：实施路线已改为「阶段0.5 止血包 → 阶段1 契约先行 → 双渲染器按 FeedbackBar → MetaRow → EntityChip → ProcessCard → InputDock → MessageShell 顺序施工」，见文末 Part II；下方 v1.0 的阶段 1~4 划分保留作背景，实施以 Part II 为准。

阶段 0 只查不改做现状盘点（已完成，报告 680 行/7 节齐全，核对结论见 Part II）。

### 阶段 0　现状组件盘点（只查不改，已完成）

```text
你是一名资深前端架构师，任务是对 CygnusX 平台的两个 AI 助手聊天界面做一次统一改造前的现状审查。
本次只做代码级调研与评估，禁止修改任何代码（包括样式、配置、注释）；先读代码再下结论，
所有结论必须标注对应文件路径与关键代码位置（文件:行号 或 文件#组件名/函数名），
找不到证据的结论一律写"未在代码中找到"，禁止按界面表现脑补实现。

## 审查背景

平台内现有两个 AI 助手界面：
- 星尘 AI：主助手（完整工作台壳：左侧图标栏 + 顶部导航；消息带 STELLAR ROUTER 路由卡、
  模型 badge、Tokens 统计、赞/踩/复制；输入区有附件、@ 引用、/ 快捷命令、深度思考、进入工作台）。
- 科研寻宝鼠：检索助手（工具页壳；消息带绿色对勾步骤 chip + 每步耗时；GSE 编号橙色链接；
  输入区只有输入框 + 「下铲挖宝」按钮；页脚有 NCBI/NGDC 免责声明）。

后续计划：统一两界面的聊天骨架（消息气泡、meta 行、过程卡、实体 chip、输入 dock、反馈条），
保留每 Agent 的名称/头像/主题色/欢迎语/placeholder/品牌文案/免责声明（皮肤层）。
本次审查为统一改造提供现状基线。

## 审查任务

### A. 组件树与实现位置
1. 两个界面各自的路由入口、页面组件、消息列表/消息项渲染组件、输入区组件的完整组件树
   （文字树即可，标注文件路径）。
2. 过程可视化的实现位置：寻宝鼠的步骤 chip 行（意图规划/跨库搜索/GEO/SRA/核验 + 每步耗时）、
   星尘的 STELLAR ROUTER 路由卡 + 进度条——分别是哪个组件、数据从哪来。
3. 实体高亮的实现位置：GSE/GSM/SRR 编号的识别与渲染（正则？后端标注？）、
   工作区文件 chip 的渲染组件。
4. 两界面是否已共享任何聊天相关组件 / composable / store，还是完全两套实现。

### B. 样式体系与主题色现状
1. 是否已有 CSS 变量 / design token / 主题配置文件；有则列出文件与变量清单。
2. 两界面主题色（星尘紫、寻宝鼠绿）分别硬编码在哪些文件哪些选择器里，统计出现次数。
3. scoped 样式重复度：两界面消息气泡、输入框、卡片是否有重复定义的同名/同义类。
4. 暗色模式的实现方式（如有）。

### C. 能力矩阵
输出「能力 × 两助手」矩阵，每格填：已实现（代码位置）/ 部分实现 / 未实现 / 刻意不提供（须注明依据）。
能力行至少包括：消息气泡、助手头像与名称展示、meta 行各字段（模型 badge / Tokens 统计 / 耗时 /
时间戳 / 检索次数）、过程卡（步骤模式 / 进度模式）、实体高亮（数据集编号 / 文件引用 / 工具引用）、
输入区槽位（附件 / @ / / 快捷命令 / 深度思考 / 进入工作台 / 语音）、发送行为（Enter 发送 /
Shift+Enter 换行）、赞 / 踩 / 复制、消息重新生成、页脚免责声明、模型切换器、助手能力说明入口。

### D. 数据流与埋点
1. 消息数据结构：字段清单（是否已带 agent_id / 模型名 / token 用量 / 过程步骤 / 耗时）、
   SSE 事件类型清单。
2. 赞/踩/复制是否已有埋点事件，事件协议是什么（字段、上报路径）。
3. Agent 身份相关信息（名称/头像/主题色/欢迎语/placeholder/免责声明）目前是写死在组件里，
   还是已有配置化入口。

### E. 复用障碍与风险
1. 抽共享组件（MessageMetaRow / ProcessCard / EntityChip / ChatInputDock / FeedbackBar）
   会踩到的坑：样式耦合、props 硬编码、store 耦合、同名类冲突、第三方组件库定制点。
2. 按严重度分级：阻断统一改造 / 体验不一致 / 技术债。
3. 低成本止血点：不依赖组件抽取、只差一次调用/登记就能先统一的点（如色值直接换变量）。

## 交付格式
1. 组件树（两界面各一，带文件路径）
2. 「能力 × 两助手」矩阵表（每格标注代码位置）
3. 样式现状清单（token 有无 + 硬编码色值清单及位置）
4. 消息数据结构与 SSE 事件清单
5. 分级风险清单（每条带代码证据）
6. 演进建议：组件抽取的推荐目录位置与拆分顺序，给出判断和理由
7. 不做任何代码修改，只输出上述报告
```

### 阶段 1~4（v1.0 版本，保留作背景，实施以 Part II 为准）

v1.0 阶段1（token 层）、阶段2（共享组件抽取）、阶段3（输入 dock 对齐 + 壳层归位）、阶段4（双路回归）的提示词块已被 Part II 的阶段0.5/阶段1 替代；组件抽取的验收要点已并入 Part II 行动顺序。v1.0 原文要点：抽组件以 `agent-chat-` 类名前缀隔离 scoped 样式冲突；「下铲挖宝」保留为 sendLabel；壳层共享控件（语言/主题/帮助）同顺序归位；回归须构造含 GSE 编号、文件引用、steps/route 两种过程卡、@工具引用的测试消息并双端截图。

## 4. 验收 checklist（用户手测对照表）

| # | 操作 | 期望现象 | 不通过处理 | 谁测 |
|---|---|---|---|---|
| 1 | 两助手各发一条消息 | meta 行位置与字段顺序完全一致，仅 accent 色不同 | 截图对比，找编码 Agent 修 | 用户 |
| 2 | 寻宝鼠检索一次 | 过程卡为统一卡片样式 steps 模式，每步耗时保留 | 查 ProcessCard 是否两处同一契约 | 用户 |
| 3 | 星尘触发路由 | 过程卡 route 模式（意图+置信度），与 steps 模式明显同族 | 同上 | 用户 |
| 4 | 消息同时含数据集编号与文件引用 | 数据集 helix 绿、文件 `#4F7FF2` 蓝，两界面一致；SRR/PRJNA 也能高亮 | 查硬编码色覆盖语义变量、正则覆盖范围 | 用户 |
| 5 | 寻宝鼠回复消息 | 出现 👍👎📋，点击产生带 agent_id 的埋点事件 | 查 FeedbackBar 挂载与反馈 API 契约 | 用户+Agent |
| 6 | 对比两助手输入区 | 基础槽位一致；「下铲挖宝」文案保留；刻意缺失槽位有 disabledSlots 声明 | 查 identity 配置 | 用户 |
| 7 | 切换 Agent | 仅五槽位变色，其余像素不变 | 查 accent 染色范围外溢 | 用户 |
| 8 | 暗色模式/窄屏各过一遍 | 无对比度崩坏、无布局错位；--chat-bg-soft 已定义 | 截图找编码 Agent 修 | 用户 |

## 5. 风险与回退

- **运行时边界（v1.1 升为第一风险）**：寻宝鼠聊天面在 open Shadow DOM + React 19 island 内，与星尘 Vue 世界零共享——一切"共享组件"都按契约层 + 双渲染器理解，不存在跨栈复用组件文件。
- **样式耦合**：两界面 scoped 样式可能有同名类——抽组件用 `agent-chat-` 前缀隔离；阶段0 报告已列出冲突点，施工前先核对。
- **刻意缺失 ≠ 缺口**：某槽位某助手确实不该有的，走 `disabledSlots` 显式声明，不当作 bug 修。
- **双端回归纪律**：契约或渲染器任何改动，两个界面必须同时回归，不接受只验一边。
- **回退**：每阶段独立提交，单阶段出问题单独 revert，不影响其他阶段；施工前务必先处理工作区既有未提交改动（见 Part II §1）。

---

## Part II　阶段0报告核对结论与修订实施路线（v1.1，2026-10-26）

### 1. 报告完整性核对

交付格式通过：7 节齐全、能力矩阵 28 行、结论均带代码位置（treasure-island/index.tsx:46、AgentSandbox.vue:648-673、types.ts:171-242、researchAgent.ts:72-82、chat.ts:201-216 等）、合规声明明确（只新增报告，未改任何代码）。

⚠️ **前置家务事**：报告注明工作区在审查前已有未提交改动（frontend/src/**、src/cygnusx/**）。施工前必须先 commit 或 stash 这些改动，保证每个阶段可干净 revert——改动混在一起时，"单阶段回退"是空话。

### 2. 推翻 v1.0 旧判断的修正记录

| # | v1.0 旧判断 | 代码证据 | v1.1 新结论 |
|---|---|---|---|
| 1 | 两界面可抽共享 Vue SFC | 寻宝鼠＝Vue 外壳 → open Shadow DOM → React 19 island，零共享（treasure-island/index.tsx:46，AgentSandbox.vue:648-673） | 路线改为**契约先行 + 双渲染器**：抽 frontend/src/components/agent-chat/ 契约层，Vue 渲染器服务星尘、React 渲染器服务寻宝鼠 island |
| 2 | 寻宝鼠 GSE 链接为橙色 | 实为 `--color-helix` 绿 | 语义色板数据集色沿用 helix 绿（§2.2 已就地修正） |
| 3 | 星尘路由卡是百分比进度条 | 路由卡展示意图 + 置信度（「通用问答 0%」是置信度） | ProcessCard 第二模式改为 route（intent + confidence）（§2.3 已就地修正） |
| 4 | 星尘有独立模型 badge | 模型名是助手身份名的回退 | 契约补独立 modelName 字段（阶段1） |
| 5 | SRR 编号已支持 | 正则仅覆盖 GSE/GSM/GO/PMID | placeholder 承诺未兑现：扩正则 SRR/PRJNA/ERX（阶段0.5） |
| 6 | 未发现假控件 | onSelectModel: () => {}（TreasureOriginalDisplay.vue:39） | 寻宝鼠模型切换器是假控件：先下线留 TODO（阶段0.5），统一改造时再接真 |
| 7 | 未发现重新生成不对称 | 星尘仅错误/空态有重新生成 | 统一为完成态也可重新生成（阶段2 MetaRow 施工时落地） |
| 8 | 未发现 chip 过滤 | intent_plan / grounding_check chip 被过滤 | 核实是否刻意：刻意→注释声明；非刻意→恢复显示（阶段0.5 核实项） |

### 3. 确认的问题（方向被证实，根因更深）

P1/P2/P4/P5 方向全部证实，但阻断点不在组件层：

- **零共享**：星尘 Vue3 + naive-ui + scoped SCSS vs 寻宝鼠 React 19 island，聊天组件、store、composable 均无复用；
- **数据模型缺口**：星尘缺顶层 agent_id、ToolCall.durationMs；寻宝鼠缺 tokens / modelName / 消息级 createdAt 视图映射 / feedback / agent_id；反馈 API 仅 {rating, comment} 无 agent_id——**契约不补，组件抽了也白抽**；
- **样式债量化**：ai-chat 265 处 hex、agent-workspace 44 处、寻宝鼠 styles.css 44 处；--chat-bg-soft 被使用但未定义；--stardust-blue 与 --brand-primary 双蓝并存。

### 4. 保留意见

双渲染器＝每个组件改两遍，这是为零共享现状付的税，今天没有更便宜的方案。记入**长期决策点**：后续 Agent 变多或寻宝鼠迭代变重时，评估将寻宝鼠聊天面从 React island 收敛回 Vue（另案，不阻塞本计划）。组件抽取目录采用报告建议 `frontend/src/components/agent-chat/`。

### 5. 行动顺序 v1.1

1. 前置：commit/stash 工作区既有未提交改动；
2. **阶段0.5 止血包**（不动架构，半天级）；
3. **阶段1 契约先行**（数据模型补齐 + AgentIdentity 契约 + token 层；本阶段视觉零变化，只立地基）；
4. **阶段2 起双渲染器施工**：FeedbackBar → MetaRow → EntityChip → ProcessCard → InputDock → MessageShell，每步双端截图回归；
5. 决策点（默认按推荐，可推翻）：数据集语义色＝helix 绿；完成态也有重新生成；寻宝鼠的 @、/、深度思考、工作台、队列、附件走 disabledSlots 显式声明。**v1.2 已拍板**：星尘 accent＝#4C6FFF 品牌蓝；React 渲染器＝父仓 overlay（扩 build-treasure-island.mjs 的 overlay 列表 + 同步更新 frontend/treasure-island/README.md 边界说明）；星尘补平台级通用免责声明。

### 阶段0.5 提示词（止血包）

> **⚠️ 本节 4 条原版已作废，以 §6.4 的 v1.2 修订版（5 条）为准**——修订点：新增第 5 条星尘身份透传；第 3 条模型切换器改为"有 API 则接真、无 API 才下线"。

### 阶段1 提示词（契约先行，替代 v1.0 阶段1）

```text
在阶段0.5基础上施工，禁止推倒重写，不改路由。本阶段只立契约，不做视觉统一：

1. 消息数据契约补齐（向后兼容，新增字段可选）：
   - 星尘侧：消息顶层补 agent_id；ToolCall 补 durationMs（types.ts:171-242、291-318 附近）；
   - 寻宝鼠侧：补 tokens、modelName、消息级 createdAt 的视图映射（researchAgent.ts:72-82，ChatMessage.tsx:26-40）；
   - 反馈 API：{rating, comment} 扩为 {rating, comment, agent_id, message_id}（chat.ts:201-216），旧调用兼容。
2. 新建 AgentIdentity 契约（字段：agentId/name/avatar/accent/greeting/placeholder/sendLabel/disclaimer/disabledSlots），星尘与寻宝鼠各一份；accent 按 v1.2 拍板值登记：星尘 #4C6FFF（--brand-primary，收敛 #2E5BFF；紫色仅留装饰渐变不占槽位），寻宝鼠 #218747（--primary）；两界面改为从契约读取上述身份字段。星尘 disclaimer 补平台级通用文案（"AI 生成内容仅供参考"类），与寻宝鼠领域免责渲染在同一页脚位置。
3. token 层：--agent-accent / --agent-accent-soft / --agent-accent-contrast 三件套（只染五槽位：头像底色、用户气泡、发送/CTA、步骤完成态对勾、正文小标题）；语义色板三变量（--sem-dataset 取 helix 绿、--sem-file、--sem-tool）；合并 --stardust-blue 与 --brand-primary 双蓝为一处定义。
4. 自验：契约改动后两界面视觉零变化（本阶段不做换色），附双端截图；新增字段附类型定义位置清单。
```

阶段2 起各组件的双渲染器提示词，在阶段1 验收通过后按契约产物逐阶段下发（届时组件 props 以落定的契约为准刷新）。

---

## Part II 附录 A　逐阶段操作手册（2026-10-26）

每阶段三步：**前置 → 投喂 → 验收**。提示词原文在 Part II 对应小节，本附录给操作与验收对照。

### ① 前置：清理工作区（用户自己执行，~2 分钟）

```bash
git status                                    # 先看有哪些未提交改动
git add -A && git commit -m "chore: 统一改造前 WIP 存档（2026-10-26）"
# 不想提交就用 stash（但 stash 容易被后续操作冲掉，推荐 commit）：
# git stash push -m "pre-unification-wip"
```

之后每个阶段施工完都要求编码 Agent 单独 commit，commit message 带阶段号（如 `feat(agent-chat): 阶段0.5 止血包`），保证单阶段可 revert。

### ② 阶段0.5 止血包：投喂 §6.4 v1.2 修订版提示词（5 条）后

| # | 验收操作 | 期望现象 | 不通过处理 |
|---|---|---|---|
| 1 | `git diff --stat` 看改动范围 | 只动四件事相关文件，无顺手"优化" | 有多余改动 → 打回，要求 revert 多余部分 |
| 2 | DevTools 查 `--chat-bg-soft` | 变量有定义值，两界面背景渲染无异常 | 未定义或背景错乱 → 打回 |
| 3 | 寻宝鼠发一条含 SRR/PRJNA 编号的消息 | 编号高亮为 helix 绿链接 | 不高亮 → 查正则改动位置 |
| 4 | 看寻宝鼠模型切换器 | 有更新 API → 切换真实生效；无 API → 控件消失且代码留 TODO | 仍是假控件 → 打回 |
| 5 | 触发一次检索 | intent_plan / grounding_check chip 按核实结论处理（刻意→有注释；非刻意→恢复显示） | 既无注释也无显示 → 打回 |
| 6 | 星尘发一条消息 | 助手身份显示 router.yaml 配置的名称/头像（🧭 星尘 AI），不再回退 🤖 | 仍 🤖 → 查 AgentSandbox 透传 |

四条全过 → 让编码 Agent commit → 进入阶段1；任何一条不过 → 打回重修，不进入下一阶段。

### ③ 阶段1 契约先行：投喂 Part II 阶段1 提示词后

| # | 验收操作 | 期望现象 | 不通过处理 |
|---|---|---|---|
| 1 | 两界面各发一条消息并截图，与施工前截图对比 | **视觉零变化**（本阶段只立地基，不做换色） | 有色差/错位 → 定位是哪个变量/组件引起，打回 |
| 2 | 查 AgentIdentity 契约文件 | 星尘、寻宝鼠各一份；字段齐（agentId/name/avatar/accent/greeting/placeholder/sendLabel/disclaimer/disabledSlots）；accent 为现状色值 | 缺字段/配色是新值 → 打回 |
| 3 | 查类型定义清单 | 星尘消息顶层有 agent_id、ToolCall 有 durationMs；寻宝鼠侧 tokens/modelName/createdAt 视图映射已补；反馈 API 扩为 {rating, comment, agent_id, message_id} 且旧调用兼容 | 缺字段 → 打回 |
| 4 | 实际发一条消息并点 👍 | 埋点事件带 agent_id + message_id | 缺字段 → 打回 |
| 5 | 查双蓝合并 | --stardust-blue 与 --brand-primary 合并为一处定义，引用全改 | 仍两处定义 → 打回 |

验收权在你手里，不接受编码 Agent 自报通过；拿回结果贴回来给我核对后再进阶段2。

---

## Part II §6　报告全文核对补记（v1.2，2026-10-26）

### 6.1 全文核对结论

报告全文 680 行通读完毕，**通过**：七节交付物齐全、28 行能力矩阵每格带代码位置且无缺格串行、"刻意精简\*"标注诚实（明说代码中无显式声明、是依据组件能力面推断）、§5.4 低成本止血表 8 条、§6.5 四条"不建议做法"、§6.6 验收纪律均直接可用。

### 6.2 全文新增修正记录（相对 v1.1）

| # | 旧判断 | 报告证据 | v1.2 新结论 |
|---|---|---|---|
| 9 | 星尘 accent 取"现状紫" | §3.2：主强调色是蓝（--brand-primary #4C6FFF → --chat-accent）；#2E5BFF 用于 AI 名称、#7B4DFF 用于渐变装饰、#8e6cf0 为 router.yaml 身份色但前端未消费；四色并存 | accent 拍板 **#4C6FFF**；收敛 #2E5BFF 双蓝；紫色仅留装饰渐变不占槽位；#8e6cf0 留作路由身份色域 |
| 10 | v1.1 把路由卡并入 ProcessCard.route 模式 | §6.4 ViewModel：process 仅 none/steps/progress；路由信息归 identity.routedAgent | 采用报告契约：路由卡做成与 ProcessCard 同族外观的独立通知卡，不占 process 模式（§2.3-3 已就地修正） |
| 11 | 未考虑 React 渲染器归属 | §6.2 + B1：island 从子仓 pipelines/Treasure-Seeking_Mouse 构建，README 规定"共享组件必须在子仓修改" | 拍板**方案 A 父仓 overlay**：扩 build-treasure-island.mjs overlay 列表，同步更新 frontend/treasure-island/README.md:9-17 边界说明 |
| 12 | 未评估星尘组件与 store 耦合度 | B3：KimiMessageItem 直接 import useAgentHubStore/apiClient/chatApi/usePyodide；KimiChatInput 用五个 store | 佐证 §6.3 排序：纯 props 的 FeedbackBar 最先做；抽取星尘组件前必须先做 props/events 解耦；输入区放最后 |
| 13 | 星尘无免责声明未处理 | §2 矩阵 #24、§6.4 disabledSlots 建议 | 拍板**补平台级通用免责声明**，与寻宝鼠领域免责同一页脚位置 |

### 6.3 三项拍板结果（2026-10-26，用户授权按推荐执行）

1. 星尘 accent＝**#4C6FFF 品牌蓝**；
2. React 渲染器＝**父仓 overlay**（frontend/treasure-island/agent-chat/）；
3. 星尘**补**平台级通用免责声明。

### 6.4 阶段0.5 修订版提示词（4 条 → 5 条，替代 Part II §5 原版）

```text
在现有代码基础上修改，禁止动组件结构与路由。本次只做五件止血事项：

1. 定义 --chat-bg-soft：该变量只在 KimiMessageItem.vue:1441 被使用但未定义（永远走 fallback rgba(127,127,127,0.08)），在 chat-theme.css 补定义（亮暗两态取值与同族 --chat-bg 协调），附定义前后对比截图。
2. 寻宝鼠编号正则扩展：linkify.ts:13-18 现状仅覆盖 GSE/GSM/GO/PMID，扩到 SRR/PRJNA/ERX，与 placeholder「GSE / GSM / SRR 编号」的承诺对齐（zh.ts:155-156），补对应用例截图或单测。
3. 寻宝鼠模型切换器假控件（modelOptions: ['平台默认模型']、onSelectModel: () => {}，TreasureOriginalDisplay.vue:35、39）：先查后端是否有更新 session.model_id 的接口——有则把 currentSession.model_id + 平台模型列表 + 选择回调接进 island（TreasureResearchWorkbench.vue:315-328），让假控件变真（首选，兑现承诺）；没有则下线隐藏，留 TODO 注释指向统一改造。
4. 核实 intent_plan / grounding_check chip 被过滤（ChatMessage.tsx:96-98）是否刻意：刻意→在过滤处注释声明理由；非刻意→恢复显示。
5. 星尘消息身份透传：AgentSandbox 向 KimiMessageList 传 agent-name/avatar/color（AgentSandbox.vue:648-660；默认值 🤖/#4f8ef7 在 KimiMessageList.vue:34-39），数据源用 router.yaml:2-6 的 name/avatar/color，让消息身份不再回退到 🤖。

验收：五项各自附证据（截图/测试/代码位置）；不得顺手做其他"优化"；#4f8ef7 等死回退的统一清理不在本期范围（归阶段1 token 层）。
```

阶段0.5 验收对照表相应加第 6 行：发条消息看星尘助手身份显示为 router.yaml 配置的名称/头像（不再是 🤖 回退）。

---

## 附录 B　改造后界面目标形态（施工靶子）

一句话原则：**切换助手时，只有颜色、头像、名字、文案在变；消息怎么读、过程怎么看、按钮在哪、Enter 干嘛——肌肉记忆全部通用。**

**星尘 AI（accent #4C6FFF）**

```text
┌──────────────────────────────────────────────────────────┐
│ 🧭 星尘 AI · deepseek-v4-flash · Tokens ↑23.0K ↓176 · 10/26 14:21 │ ← 统一meta行：头像来自router.yaml，模型名是独立字段
│ ┌──────────────────────────────────────────────────────┐ │
│ │ ⤳ 星尘 AI → 通用助手        意图：通用问答 · 置信度 87% │ │ ← 路由通知卡：与过程卡同族外观（12px圆角、1px边框、左图标右状态）
│ └──────────────────────────────────────────────────────┘ │
│ 正文……GSE20403（helix绿链接） [📄 文件]（蓝chip） [🔧 工具]（青chip）│ ← 语义色全平台统一；星尘第一次获得数据集高亮
│ 👍  👎  📋  ⟳重新生成                                      │ ← 完成态也有重新生成；赞踩埋点带agent_id
└──────────────────────────────────────────────────────────┘
 输入区能力不变；页脚新增平台级"AI 生成内容仅供参考"
 紫色只留在 StardustHero 装饰渐变，不占 accent 槽位
```

**科研寻宝鼠（accent #218747，个性全保留）**

```text
┌──────────────────────────────────────────────────────────┐
│ 🐭 科研寻宝鼠 · 平台默认模型 · Tokens ↑1.2K ↓856 · 3次检索 · 4028ms · 14:21 │ ← 同一meta行组件：补上模型/Tokens/时间戳
│ ┌──────────────────────────────────────────────────────┐ │
│ │ ✓意图规划 0ms  ✓跨库搜索 1165ms  ✓GEO 1156ms  ✓SRA 1707ms │ │ ← 统一ProcessCard steps模式：外观与星尘同族，对勾染绿
│ └──────────────────────────────────────────────────────┘ │
│ ……GSE330435、SRR123456、PRJNA800001（全部可点，helix绿）      │ ← SRR/PRJNA 承诺兑现
│ 👍  👎  📋  ⟳重新挖一次                                    │ ← 新增赞踩；复制、重新挖保留
└──────────────────────────────────────────────────────────┘
 [描述你的研究问题，或粘贴 GSE / GSM / SRR 编号……]  [⛏ 下铲挖宝]  ← 品牌文案全保留
 页脚：数据来自公共组学与文献库，请以 NCBI / NGDC 原始记录为准
 @、/、深度思考等走 disabledSlots 显式声明"刻意不做"，不再是"漏做"
```
