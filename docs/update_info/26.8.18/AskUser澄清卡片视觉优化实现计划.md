# AskUser 澄清卡片视觉优化实现计划

> 版本：v1.0（2026-08-18）
> 前置文档：《ask-user-样式调研报告》（平台内嵌卡片 vs Kimi 浮层样式对比）
> 本文档 = 评估结论 + 定稿方案 + 可直接粘贴给编码 Agent 的提示词 + 验收清单

---

## 一、背景与评估结论

### 1.1 背景

调研报告对比了 Kimi 的 ask_user 浮层样式（输入框上方弹出、slide-up 动画、强制焦点）与平台当前实现（AI 消息气泡内嵌卡片、无动画、视觉层级中等），并给出三个方案：

- 方案 A：切换为 Kimi 式浮层
- 方案 B（报告推荐）：保留消息内嵌，增加动画与高亮引导
- 方案 C：保持现状

### 1.2 评估 Verdict：方案 B 方向正确，采纳

**业界约定查证**："结构化澄清 UI" 是主流共识，但落地形态分两派：

| 流派 | 代表产品 | 形态 |
|------|----------|------|
| 浮层/对话框派 | Kimi、Cursor 2.1 Plan Mode | 输入框上方浮层或专用交互对话框，选项点选 + 文本输入 + 可逐题跳过 |
| 消息流内嵌派 | ChatGPT、Claude、Perplexity | 追问/建议以消息流内的 chips、卡片呈现 |

两派都成立。对平台选择方案 B 的三条依据：

1. **设计共识反对遮挡式浮层**：浮层/模态锁死聊天、遮挡正文被列为 AI 聊天界面反模式，交互元素应贴近其上下文。参考截图本身即实证——浮层遮住了正文"三重依据"的第 1 条。平台场景中 ask_user 常跟在长评审结论/长分析之后，遮挡代价更高。
2. **多问题分页 + 历史回看是硬需求**：浮层需额外解决高度管理与回看入口；内嵌卡片天然免费拥有这两个能力（已回答折叠为"询问工具 | 已收集信息"）。
3. **方案 A 的隐性成本（调研报告遗漏，补充）**：
   - 浮层会遮挡正在流式生成的正文；
   - 平台已有 AskUserModal（Studio 场景）一套浮层实现，消息流再切浮层 = 双套 DOM 结构长期维护。

### 1.3 目标

不改 DOM 架构、不改交互逻辑、不改数据结构，只通过动画、高亮、滚动策略与视觉细节，把内嵌卡片的"注意力引导"提升到浮层级别。

---

## 二、问题清单与优化 Spec

### 问题 1：入场动画与高亮缺失（含调研报告示例代码的 CSS bug）

调研报告方案 B 的示例代码**直接照抄会翻车**：

```scss
.ask-user-card {
  animation: ask-card-slide-up 0.3s ease-out;        /* 基类 */
  &:not(.answered) {
    animation: ask-card-pulse 2s ease-in-out infinite; /* 特异性更高，把 slide-up 整个覆盖 */
  }
}
```

未回答状态下 `animation` 简写后声明者胜，**入场动画根本不会播放**；且无限脉冲是注意力反模式。

**定稿 Spec**：

- 未回答状态：入场动画 opacity 0→1、translateY(10px)→0，0.3s ease-out；
- 静态高亮：`border-color: var(--chat-accent)` + `box-shadow: 0 0 0 2px color-mix(in srgb, var(--chat-accent) 25%, transparent)`；
- 呼吸脉冲**只播 2 次后静止**（延迟 0.3s 等入场播完），禁止 infinite；
- 多条动画必须在**同一个 animation 简写里逗号分隔**声明，不得分散到不同选择器；
- `prefers-reduced-motion: reduce` 时取消全部动画，仅保留静态高亮。

### 问题 2：自动滚动不得打扰阅读

无条件 `scrollIntoView` 会粗暴打断正在阅读上方内容的用户（AI 聊天界面高频 UX 错误）。

**定稿 Spec**：

- 仅当消息列表滚动位置距底部 **< 100px** 时才自动滚动使卡片可见；
- 否则在输入框上方显示轻量 pill「有 N 个待回答的问题 ↓」，点击平滑滚动到卡片；卡片进入视口或已回答后 pill 消失；
- pill 样式：毛玻璃 `rgba(255,255,255,0.08)` + `backdrop-filter: blur(12px)` + 1px 高亮边框（深色模式用对应 `--chat-*` 变量）。

### 问题 3：输入框联动不要用 placeholder

placeholder 在输入框聚焦后不可见，且会污染原有占位文案逻辑。

**定稿 Spec**：输入框容器顶部加常驻细条提示「AI 正在等待你的回答」，仅当存在未回答 askRequest 时显示，回答/跳过后消失；字号 12px，低对比次要色，与 pill 同视觉体系。

### 问题 4：借鉴主流产品的低成本视觉细节（调研报告未提）

从 Kimi 截图可直接搬进现有 AskUserCard 的细节：

- 未选中选项左侧加**序号徽标**：20×20px、圆角 6px、1px 边框、序号 12px；
- 选中项**整行高亮**：背景 `color-mix(in srgb, var(--chat-accent) 12%, transparent)`，序号位变 ✓ 图标，行边框 accent 色；
- 「跳过」按钮右侧加 **Esc 徽标**、「提交/下一步」加 **↵ 徽标**（kbd 样式：11px、圆角 4px、半透明底）；
- 分页器（‹ 1/1 ›）保持标题行右侧，不换行。

---

## 三、分阶段实现

| 阶段 | 内容 | 风险 | 独立可验 |
|------|------|------|----------|
| 阶段 1 | 问题 1：动画修复 + 静态高亮（纯 CSS/SCSS） | 极低 | 卡片出现播动画、脉冲 2 次后静止 |
| 阶段 2 | 问题 2 + 3：滚动阈值、待回答 pill、输入框提示条（轻量 JS/状态） | 低 | 阅读位置不跳转、底部自动滚、提示显隐正确 |
| 阶段 3 | 问题 4：序号徽标、选中态、快捷键徽标、分页器位置 | 极低 | 逐条对照 spec 截图确认 |

阶段 1 无依赖可先行；阶段 3 与阶段 1 可并行；阶段 2 涉及滚动容器状态，建议在阶段 1 合入后进行。

---

## 四、编码 Agent 提示词（整段复制）

```text
你是一名资深前端工程师。项目使用 Vue3 + Pinia + SCSS 变量体系（--chat-* / --neutral-* / --shadow-*）。

任务：在现有 AI 对话的 ask_user 澄清卡片基础上做视觉引导优化。先阅读现有代码：
- frontend/src/components/ai-chat/AskUserCard.vue（核心交互卡片）
- frontend/src/components/ai-chat/KimiMessageItem.vue（渲染位置，约 1267 行内嵌 AskUserCard）
- frontend/src/components/ai-chat/AskUserModal.vue（Studio 场景模态包装器，本次不动）
理解当前实现后再修改。禁止推倒重写，禁止改动组件 props/事件接口、消息数据结构
（AskRequest/AskQuestion）、路由与无关组件。本次只改视觉与轻量提示，不改交互流程
（选项点选/其他输入/Esc 跳过/分页/提交/折叠回看逻辑全部保持不变）。

## 需要修改的问题（逐条执行）

1. [入场动画与高亮提示缺失]：当前卡片随消息流静默出现，视觉优先级低。
   - 未回答状态加入场动画：opacity 0→1、translateY(10px)→0，0.3s ease-out。
   - 未回答状态加静态高亮：border-color: var(--chat-accent)；
     box-shadow: 0 0 0 2px color-mix(in srgb, var(--chat-accent) 25%, transparent)。
   - 高亮呼吸脉冲仅播放 2 次后静止：pulse 延迟 0.3s（等入场播完），周期 2.4s，
     iteration-count 为 2，禁止 infinite。
   - 关键约束：同一元素的多条动画必须在同一个 animation 简写里逗号分隔声明；
     分散到基类与 :not(.answered) 两个选择器会互相覆盖，导致入场动画失效。
   - 全部动画遵守 prefers-reduced-motion：开启时取消动画，仅保留静态高亮边框。

2. [出现时不打扰阅读]：卡片出现时不要无条件 scrollIntoView。
   - 仅当消息列表滚动位置距底部 < 100px 时才自动滚动使卡片可见。
   - 否则在输入框上方显示轻量 pill：「有 N 个待回答的问题 ↓」，点击平滑滚动到卡片；
     pill 在卡片进入视口或已回答后消失。
   - pill 样式：毛玻璃 background: rgba(255,255,255,0.08);
     backdrop-filter: blur(12px); 1px 高亮边框；深色模式用对应 --chat-* 变量。

3. [输入框联动提示]：不要改输入框 placeholder。在输入框容器顶部加常驻细条提示
   「AI 正在等待你的回答」，仅当存在未回答 askRequest 时显示，回答/跳过后消失；
   字号 12px，低对比次要色，与 pill 同视觉体系。

4. [选项视觉细节]：
   - 未选中选项左侧加序号徽标：20×20px、圆角 6px、1px 边框、序号 12px。
   - 选中项整行高亮：背景 color-mix(in srgb, var(--chat-accent) 12%, transparent)；
     左侧序号位变为 ✓ 图标；行边框 accent 色。
   - 「跳过」按钮右侧加 Esc 徽标、「提交/下一步」按钮加 ↵ 徽标（kbd 样式：11px、
     圆角 4px、半透明底）。
   - 分页器（‹ 1/1 ›）保持在标题行右侧，不换行。

## 全局约束

- 颜色一律使用现有 CSS 变量（--chat-accent、--chat-ai-card、--chat-shadow-sm 等），
  深色/浅色两套主题都要验证，文字对比度不低于 WCAG AA（4.5:1）。
- 动画只用 transform / opacity / box-shadow，入场 ≤ 300ms，脉冲周期 2.4s。
- 已回答状态的折叠卡片样式（"询问工具 | 已收集信息"）保持不变。
- AskUserModal（Studio 场景）本次不改，且不得引入会破坏它的全局样式覆盖。

## 验收标准（逐条自检）

- [ ] 未回答卡片出现时播放入场动画 + 脉冲恰好 2 次后静止在静态高亮态
- [ ] 开启系统"减少动态效果"后无任何动画，仅静态高亮
- [ ] 用户在上方阅读时不自动跳转、出现待回答 pill；在底部时自动滚到卡片
- [ ] 输入框上方提示条随未回答/已回答正确显隐，placeholder 未被改动
- [ ] 选项序号徽标、选中 ✓ 整行高亮、按钮快捷键徽标、分页器位置符合 spec
- [ ] 深浅两套主题下对比度正常
- [ ] 交互行为与改前完全一致：点选/其他输入/Esc 跳过/分页/提交/折叠回看
- [ ] AskUserModal 在 Studio 场景无样式回归

完成后简述：每个问题对应的修改文件与关键属性改动。
```

---

## 五、总验收 Checklist

- [ ] 阶段 1：动画与高亮按 spec 落地，无 CSS 覆盖 bug
- [ ] 阶段 2：滚动阈值 100px 生效，pill 与提示条显隐逻辑正确
- [ ] 阶段 3：四处视觉细节逐条对照确认
- [ ] 深浅双主题回归
- [ ] prefers-reduced-motion 回归
- [ ] 交互行为零回归（点选/其他/跳过/分页/提交/折叠）
- [ ] AskUserModal（Studio）零回归

---

## 六、风险与回退

| 风险 | 说明 | 回退 |
|------|------|------|
| 动画覆盖 | 多条 animation 分散声明互相覆盖（本次已踩过的坑） | 合并为单条简写；实在不行只保留静态高亮 |
| 滚动阈值误伤 | 长消息流中 100px 阈值在部分分辨率下偏紧 | 调整为按视口高度比例（如 15%） |
| pill 与现有输入框上方元素打架 | 输入框容器顶部可能已有其他提示组件 | pill 改为消息列表右下角浮动按钮 |
| 全部回退 | 任何阶段出问题 | 该阶段改动均为独立提交，单独 revert 即可；卡片基础功能不依赖任何新样式 |

---

## 七、相关文件清单

| 文件 | 本次是否改动 | 用途 |
|------|--------------|------|
| `frontend/src/components/ai-chat/AskUserCard.vue` | ✅ 主战场 | 核心交互卡片 |
| `frontend/src/components/ai-chat/KimiMessageItem.vue` | ✅ 少量 | 卡片渲染、滚动容器上下文 |
| `frontend/src/components/ai-chat/AskUserModal.vue` | ❌ 不动 | Studio 场景模态包装器 |
| `frontend/src/components/ai-chat/types.ts` | ❌ 不动 | AskRequest/AskQuestion 类型 |
| 输入框容器组件 | ✅ 少量 | 待回答 pill 与提示条挂载点 |
