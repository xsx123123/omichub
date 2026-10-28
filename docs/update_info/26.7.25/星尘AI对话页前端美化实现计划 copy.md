# 星尘 AI 对话页 · 前端样式美化实现计划

> 交付对象：编码 Agent（kimi code / Claude Code / CODEX 等）
> 任务性质：**在现有 AI 对话页基础上做视觉/样式优化**，不是重新设计，不改任何功能逻辑
> 生成日期：2026-07-25

---

## 一、背景与目标

星尘 AI 对话页（统一入口智能体页面）当前样式偏素：大面积纯白/浅灰、组件样式各自为政、输入框聚焦态为橙色描边，与 OmicHub 平台首页确立的"星尘"视觉基因（蓝紫渐变 + 星空元素 + 毛玻璃按钮 + 俏皮标志性文案）明显脱节。

**目标**：仅通过前端样式调整，让 AI 对话页与平台首页风格统一，提升质感与可读性。

**硬性约束**：

- 不改路由、不改功能逻辑、不改接口、不动无关组件
- 禁止推倒重写，必须先读现有代码再改
- 优先复用项目已有的 Arco Design 组件与设计变量
- 风格必须与平台首页保持一致（蓝紫渐变主色、星尘/宇宙视觉元素、标志性文案语气）

---

## 二、参考依据

### 2.1 平台首页视觉基调（风格锚点）

从 OmicHub 首页提取的品牌语言，作为本次美化的对齐标准：

| 元素 | 规格 |
|---|---|
| 品牌主渐变 | `linear-gradient(135deg, #2E5BFF 0%, #7B4DFF 100%)`（Hero Banner、通知条同款） |
| 强调蓝 | `#2E5BFF`（按钮、链接、激活态） |
| 毛玻璃按钮 | `background: rgba(255,255,255,0.12); backdrop-filter: blur(12px); border: 1px solid rgba(255,255,255,0.35)` |
| 卡片 | `#FFFFFF` 底、`border-radius: 12px`、`box-shadow: 0 2px 8px rgba(30,50,100,0.06)` |
| 图标色块 | 浅底色圆角方块 + 彩色图标（首页"快捷入口"卡片同款） |
| 文案语气 | 标志性俏皮文案，如"像收集星尘一样，一站式攒齐你的组学宝藏 ✨" |

### 2.2 arco-design-skill 的参考用法

项目样式体系基于 Arco Design，可要求编码 Agent 在执行时参考官方技能库
`https://github.com/arco-design/arco-design-skill/tree/main`：

- 该仓库提供 `@arco-design/web-react` 与 `@arco-design/web-vue` 两套技能文件，含 70+ 组件的 API 表、常见模式与最佳实践。
- **执行时按需加载对应参考文件**，不要全量照搬：
  - 顶栏/按钮 → `components/general/button.md`、`components/navigation/dropdown.md`
  - 模型信息标签 → `components/data-display/tag.md`
  - 思考过程折叠 → `components/data-display/collapse.md`
  - 输入区 → `components/data-entry/input.md`（Textarea 自适应高度用法）
  - 空状态/欢迎区 → `components/data-display/empty.md`、`components/data-display/card.md`
  - 主题变量与暗色 → `overview/theming.md`（CSS 变量定制方式）
- 若项目技术栈为 Vue 则用 `skills/arco-design-vue/` 目录，React 则用 `skills/arco-design/` 目录，以项目实际依赖为准。

---

## 三、现状问题清单（逐条转 spec）

> 每条 = 现状问题 → 具体修改 spec → 预期效果。所有数值为建议值，编码 Agent 可在 ±10% 内微调，但色值方向不得偏离品牌蓝紫系。

### 问题 1：页面整体苍白，无平台视觉基因

- **现状**：对话页背景为纯白/极浅灰，无任何星尘/宇宙元素，与首页 Hero 的蓝紫渐变星空氛围完全脱节。
- **修改 spec**：
  - 页面背景改为 `linear-gradient(180deg, #F4F6FF 0%, #FAFBFF 40%, #FFFFFF 100%)`；
  - 在对话区顶部叠加一层极淡装饰：2 个径向渐变光斑（`radial-gradient(circle, rgba(46,91,255,0.10) 0%, transparent 70%)` 与 `rgba(123,77,255,0.08)`），`opacity ≤ 0.6`，固定定位、`pointer-events: none`，不遮挡内容；
  - 可选：复用首页的二进制/星点纹理，透明度压到 `0.03~0.05` 作背景纹理。
- **预期效果**：页面有淡淡的蓝紫氛围但不喧宾夺主，正文区域对比度不受影响。

### 问题 2：顶栏按钮样式平、层级不清

- **现状**："工作台模式""查看该智能体能力"两个按钮均为浅灰底 + 图标，视觉上与模型选择器平级，主次不明；返回箭头、标题区与首页头部语言不一致。
- **修改 spec**：
  - 顶栏容器改为毛玻璃：`background: rgba(255,255,255,0.72); backdrop-filter: blur(12px); border-bottom: 1px solid rgba(46,91,255,0.08)`，滚动时保持吸顶；
  - 主按钮（工作台模式）：品牌渐变底 `linear-gradient(135deg, #2E5BFF, #7B4DFF)`、白字、`border-radius: 8px`、hover 时 `opacity: 0.9` + `box-shadow: 0 4px 12px rgba(46,91,255,0.35)`；
  - 次按钮（查看该智能体能力）：ghost 样式，`border: 1px solid #D4DBF5`，hover 时边框/文字变为 `#2E5BFF`；
  - 模型选择器（qwen3.7-max）：浅灰底 `#F2F3F8` 胶囊、`border-radius: 16px`，hover 出下拉阴影 `0 4px 12px rgba(30,50,100,0.10)`。
- **预期效果**：顶栏层级清晰（主 CTA 一眼可见），与首页按钮语言一致。

### 问题 3：AI 回复卡片与表格样式生硬

- **现状**：AI 回复区为纯白卡片 + 默认细边框表格，模型信息行（模型名 / 代码助手标签 / Tokens / 时间戳）样式单薄，"思考过程"折叠条过于朴素。
- **修改 spec**：
  - 回复卡片：`border-radius: 12px`、`box-shadow: 0 2px 8px rgba(30,50,100,0.06)`、去掉生硬描边或改为 `1px solid rgba(46,91,255,0.06)`；
  - 模型信息行：模型名用 `#2E5BFF`、`font-weight: 600`；"代码助手"标签用 Arco `Tag`（浅色描边款，参考 arco-design-skill `tag.md`）；Tokens 与时间戳统一 `12px / #8A91A6`；
  - "思考过程"折叠条：浅蓝紫底 `#F4F6FF`、`border-radius: 8px`、展开箭头过渡 `200ms`；
  - Markdown 表格：表头底色 `#F4F6FF`、表头字 `font-weight: 600 / #3B4262`、行 hover `#F8F9FF`、行高 `48px`，单元格 padding `12px 16px`；表格圆角 `8px` 并裁掉溢出（`overflow: hidden`）。
- **预期效果**：回复内容层次清晰，表格与首页卡片语言统一。

### 问题 4：输入框聚焦态为橙色，与品牌色冲突；发送按钮状态不明

- **现状**：输入框聚焦时出现橙色/琥珀色描边光晕，"深度思考"开关也是琥珀色胶囊，与全站蓝紫主色打架；发送按钮为灰色箭头，启用/禁用状态区分度低。
- **修改 spec**：
  - 输入框聚焦态：描边 `1.5px solid #2E5BFF` + 外发光 `box-shadow: 0 0 0 3px rgba(46,91,255,0.12)`，过渡 `200ms`；
  - "深度思考"等开关类胶囊：选中态改为蓝紫系——`background: rgba(46,91,255,0.10); color: #2E5BFF; border: 1px solid rgba(46,91,255,0.35)`；未选中 `#8A91A6` 灰；
  - 发送按钮：启用态品牌渐变圆形按钮（直径 `32px`，白色 ↑ 图标，hover 加 `box-shadow: 0 4px 12px rgba(46,91,255,0.35)`）；禁用态 `#D4DBF5` 底 + 白图标，禁用手型；
  - 工具栏图标（灯泡/附件/联网/终端）：默认 `#8A91A6`，hover `#2E5BFF` + 浅底圆角气泡，激活态同"深度思考"选中样式。
- **预期效果**：输入区色彩全部回归品牌蓝紫系，按钮状态一眼可辨。

### 问题 5：对话区中部大面积空白，无引导

- **现状**：会话刚开始/内容较少时，对话区中部是大片空白，既浪费空间也没有引导作用。
- **修改 spec**：
  - 新增"欢迎/空状态"区块（仅在无消息时渲染，有消息后隐藏）：星尘 AI 大头像（`64px`）+ 欢迎语一句（沿用平台俏皮文案语气，如"我是星尘 AI，说出你的需求，我来帮你对接最合适的专家 ✨"）；
  - 下方 3~4 个快捷提问卡片：白底、`border-radius: 12px`、浅底圆角图标方块 + 两行文字（标题 + 灰色说明），与首页"快捷入口"卡片同一语言；hover 时 `translateY(-2px)` + 阴影加深，点击即填入输入框；
  - 快捷卡片内容从现有"智能体能力"文案中提炼（如：看看工作区文件 / 帮我做 KEGG 富集分析 / 画一个火山图 / RNA-seq 差异分析流程）。
- **预期效果**：空状态有品牌感和引导性，用户知道能问什么。

### 问题 6：细节统一性

- **现状**：滚动条为浏览器默认样式；"回到底部"悬浮按钮样式孤立；用户气泡与 AI 卡片间距偏挤。
- **修改 spec**：
  - 对话区滚动条：宽 `6px`、滑块 `rgba(46,91,255,0.20)`、hover `0.35`，轨道透明；
  - "回到底部"按钮：白底圆形 `36px`、`box-shadow: 0 2px 8px rgba(30,50,100,0.12)`、图标 `#2E5BFF`；
  - 消息间距：用户气泡与 AI 卡片之间 `margin: 24px 0`，卡片内段落行高 `1.75`；
  - 页面底部免责声明（"以上星尘由硅基网络演算……"）保持 `12px / #B0B6C9` 居中。
- **预期效果**：细节不跳戏，整体完成度提升。

---

## 四、设计变量（建议沉淀为 CSS 变量）

```css
:root {
  --brand-gradient: linear-gradient(135deg, #2E5BFF 0%, #7B4DFF 100%);
  --brand-blue: #2E5BFF;
  --brand-purple: #7B4DFF;
  --brand-bg-soft: #F4F6FF;
  --brand-border-soft: rgba(46, 91, 255, 0.08);
  --brand-glow: rgba(46, 91, 255, 0.35);
  --text-primary: #1D2433;
  --text-secondary: #8A91A6;
  --card-shadow: 0 2px 8px rgba(30, 50, 100, 0.06);
  --card-radius: 12px;
}
```

若项目已通过 Arco 的 `ConfigProvider` / 主题变量管理主色（参考 arco-design-skill `overview/theming.md`），优先在主题层统一主色为 `#2E5BFF`，避免散写。

---

## 五、分阶段实现计划

| 阶段 | 范围 | 对应问题 | 独立可验 |
|---|---|---|---|
| 阶段一 | 全局基调 + 顶栏 | 问题 1、2 | 打开页面即有品牌氛围，顶栏层级清晰 |
| 阶段二 | 消息区（气泡/回复卡片/表格/折叠条） | 问题 3、6 | 发一条含表格的消息即可对照验收 |
| 阶段三 | 输入区 + 空状态引导 | 问题 4、5 | 聚焦输入框、切换深度思考、空会话页逐项检查 |

每阶段改完单独提交/截图确认，再进下一阶段。

---

## 六、给编码 Agent 的提示词（按阶段整段复制）

### 阶段一提示词：全局基调 + 顶栏

```text
你是一名资深前端工程师。项目使用 Arco Design 组件库（先确认是 @arco-design/web-react
还是 @arco-design/web-vue）。组件 API 与最佳实践可参考官方技能库
https://github.com/arco-design/arco-design-skill/tree/main 中对应目录
（React 用 skills/arco-design/，Vue 用 skills/arco-design-vue/），按需查阅
button.md、dropdown.md、overview/theming.md，不要全量引入。

任务：在现有"星尘 AI"对话页（统一入口智能体聊天页）基础上做视觉优化。先阅读该页面
组件与样式文件，理解当前实现后再修改。禁止推倒重写，禁止改路由、功能逻辑、接口和
无关组件。

本阶段只做两件事：

1. 页面背景基调：
   - 页面背景改为 linear-gradient(180deg, #F4F6FF 0%, #FAFBFF 40%, #FFFFFF 100%)
   - 对话区顶部叠加 2 个固定定位的装饰光斑：radial-gradient(circle,
     rgba(46,91,255,0.10) 0%, transparent 70%) 和 rgba(123,77,255,0.08) 各一个，
     pointer-events: none，不遮挡任何内容与交互
2. 顶栏：
   - 容器改毛玻璃：background: rgba(255,255,255,0.72); backdrop-filter: blur(12px);
     border-bottom: 1px solid rgba(46,91,255,0.08)；滚动吸顶
   - "工作台模式"主按钮：linear-gradient(135deg, #2E5BFF, #7B4DFF) 底、白字、
     border-radius: 8px，hover 加 box-shadow: 0 4px 12px rgba(46,91,255,0.35)
   - "查看该智能体能力"次按钮：ghost 样式，border: 1px solid #D4DBF5，hover 时
     边框与文字变 #2E5BFF
   - 模型选择器胶囊：背景 #F2F3F8、border-radius: 16px

建议把品牌色沉淀为 CSS 变量（--brand-gradient、--brand-blue: #2E5BFF 等），
若项目已用 Arco ConfigProvider 管理主题，优先在主题层把主色统一为 #2E5BFF。

验收：页面出现淡蓝紫氛围但正文可读性不受影响；顶栏主次分明；所有按钮功能行为
与改前完全一致。完成后列出修改的文件与关键属性改动。
```

### 阶段二提示词：消息区

```text
继续在"星尘 AI"对话页上做样式优化（沿用阶段一建立的品牌变量 #2E5BFF / #7B4DFF /
--brand-gradient）。先读现有消息区组件代码再改，禁止重写、禁止动消息渲染与流式
逻辑。表格与标签的组件用法可参考 https://github.com/arco-design/arco-design-skill
中的 components/data-display/tag.md 与 collapse.md。

本阶段修改：

1. AI 回复卡片：border-radius: 12px；box-shadow: 0 2px 8px rgba(30,50,100,0.06)；
   描边改为 1px solid rgba(46,91,255,0.06) 或去掉
2. 模型信息行：模型名 #2E5BFF、font-weight: 600；"代码助手"用浅色描边 Tag；
   Tokens 与时间戳统一 12px / #8A91A6
3. "思考过程"折叠条：底色 #F4F6FF、border-radius: 8px、箭头过渡 200ms
4. Markdown 表格：表头底色 #F4F6FF、表头字 font-weight: 600 / #3B4262；
   行 hover #F8F9FF；行高 48px；单元格 padding 12px 16px；表格容器
   border-radius: 8px + overflow: hidden
5. 消息节奏：用户气泡与 AI 卡片间距 margin 24px 0；正文行高 1.75
6. 对话区滚动条：宽 6px、滑块 rgba(46,91,255,0.20)、hover 0.35、轨道透明；
   "回到底部"悬浮按钮：白底圆形 36px、box-shadow 0 2px 8px rgba(30,50,100,0.12)、
   图标 #2E5BFF

验收：发送一条会触发表格回复的消息（或构造 mock），对照上述数值逐项检查；
消息流式渲染、复制、折叠等功能行为与改前一致。
```

### 阶段三提示词：输入区 + 空状态

```text
继续在"星尘 AI"对话页上做样式优化（沿用品牌变量）。先读输入区组件代码再改，
禁止改动发送、附件、联网、深度思考等任何功能逻辑。Input/Textarea 与 Empty、Card
的用法可参考 https://github.com/arco-design/arco-design-skill 中的
components/data-entry/input.md、components/data-display/empty.md、card.md。

本阶段修改：

1. 输入框聚焦态：border 1.5px solid #2E5BFF + box-shadow 0 0 0 3px
   rgba(46,91,255,0.12)，过渡 200ms（替换掉现有橙色聚焦样式）
2. "深度思考"等开关胶囊：选中态 background rgba(46,91,255,0.10)、color #2E5BFF、
   border 1px solid rgba(46,91,255,0.35)；未选中 #8A91A6
3. 发送按钮：启用态品牌渐变圆形（32px，白色 ↑ 图标，hover 加
   box-shadow 0 4px 12px rgba(46,91,255,0.35)）；禁用态 #D4DBF5 底
4. 工具栏图标（灯泡/附件/联网/终端）：默认 #8A91A6，hover #2E5BFF + 浅底气泡
5. 空状态欢迎区（仅在无消息时渲染，有消息后隐藏）：
   - 星尘 AI 大头像 64px + 一句欢迎语（沿用平台俏皮文案语气）
   - 下方 3~4 个快捷提问卡片：白底、border-radius 12px、浅底圆角图标方块 +
     标题/说明两行文字，与平台首页"快捷入口"卡片同一语言；hover 上浮 2px +
     阴影加深；点击把问题填入输入框（不自动发送）
   - 快捷问题从现有智能体能力文案提炼

验收：输入区不再出现橙色；开关与发送按钮状态一眼可辨；空会话页有欢迎引导；
填入快捷问题、发送、附件等功能全部正常；桌面与移动宽度下无布局破损。
```

---

## 七、总验收 Checklist

- [ ] 全页面无橙色残留，主色统一为 `#2E5BFF → #7B4DFF` 蓝紫系
- [ ] 正文与背景对比度 ≥ 4.5:1（WCAG AA）
- [ ] 顶栏、按钮、卡片、表格与平台首页视觉语言一致
- [ ] 空状态有欢迎区与快捷提问卡片；有消息后自动隐藏
- [ ] 发送、流式回复、思考过程折叠、表格渲染、附件、深度思考、模型切换功能与改前完全一致
- [ ] 动画/过渡均在 200~400ms，无干扰阅读的循环动效
- [ ] 桌面与移动两种宽度下无横向滚动、无布局破损
- [ ] 未新增依赖（如确有必要，已在提交说明中给出理由）
