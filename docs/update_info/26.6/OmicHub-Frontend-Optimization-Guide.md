# OmicHub 前端风格优化实施指南

> 生成日期：2026-07-04
> 目标：从"调查诊断"到"可执行方案"，提供具体代码与实施步骤
> 适用对象：OmicHub 全站前端代码

---

## 目录

1. [核心结论与策略](#一核心结论与策略)
2. [P0 紧急修复（本周内）](#二p0-紧急修复本周内)
3. [P1 规范建立（1-2 周）](#三p1-规范建立1-2-周)
4. [P2 视觉提升（2-3 周）](#四p2-视觉提升2-3-周)
5. [P3 锦上添花（按需）](#五p3-锦上添花按需)
6. [具体组件改造示例](#六具体组件改造示例)
7. [推荐引入的开源库](#七推荐引入的开源库)
8. [实施路线图与检查清单](#八实施路线图与检查清单)
9. [附录：设计令牌速查表](#九附录设计令牌速查表)

---

## 一、核心结论与策略

### 1.1 诊断结论

你的平台已经建立了**非常健康的三层主题架构**：

| 层级 | 状态 | 评价 |
|------|------|------|
| Layer 1: CSS 变量（global.css） | 完善 | 设计令牌覆盖颜色/阴影/圆角/字体，亮暗双色齐全 |
| Layer 2: Naive UI ThemeOverrides | 良好 | App.vue 中集中配置，与 CSS 变量对齐 |
| Layer 3: Chat 主题（chat-theme.css） | 基本良好 | 深色模式已桥接，浅色模式主色需对齐 |

**统一性评分：7/10** — 架构没问题，是执行走样了。

### 1.2 根本问题

> **不是架构问题，而是执行一致性问题。**

- 三套样式范式并存：CSS 变量（主流，~90 个文件）+ Tailwind（~5 个文件）+ 内联样式（~3 个文件）
- 设计令牌已定义，但组件中大量硬编码值使其形同虚设
- Tailwind 默认色板（gray-500、blue-600）与 Arco 色板视觉不一致，且深色模式下无法响应

### 1.3 核心策略

> **先统一，再美化。做减法，克制用色。**

**具体执行策略：**
- **新代码不犯错** — 新写的页面/组件严格遵循设计令牌
- **旧代码顺手修** — 遇到 bug 或需改动时顺手修复，不专门抽时间全面重构
- **先做 P0（颜色/圆角统一）**，P1/P2 在开发新功能时顺带推进

---

## 二、P0 紧急修复（本周内）

### 2.1 修复 Tailwind 颜色体系分裂

**问题**：`DownloadsView.vue`、`TaskTable.vue`、`DeleteConfirmModal.vue`、`OnboardingPopup.vue` 等使用 Tailwind 默认色板（`bg-gray-100`、`text-blue-600`、`bg-red-50` 等），与 Arco 色板视觉不一致，且**深色模式下会露馅**。

**解决方案**：在 `tailwind.config.js` 中扩展自定义颜色，映射到 CSS 变量。

**步骤 1：修改 `tailwind.config.js`**

```javascript
// tailwind.config.js
/** @type {import('tailwindcss').Config} */
export default {
  // ... 其他配置
  theme: {
    extend: {
      // 将 Tailwind 默认色板替换为平台设计令牌
      colors: {
        // 主色
        primary: {
          DEFAULT: 'var(--arco-primary)',
          50: 'var(--arco-primary-50, rgba(22,93,255,0.05))',
          100: 'var(--arco-primary-100, rgba(22,93,255,0.1))',
          200: 'var(--arco-primary-200, rgba(22,93,255,0.2))',
        },
        // 语义色
        success: 'var(--arco-success)',
        warning: 'var(--arco-warning)',
        danger: 'var(--arco-danger)',
        // 中性色
        neutral: {
          bg: 'var(--neutral-bg)',
          card: 'var(--neutral-card)',
          border: 'var(--neutral-border, #E5E6EB)',
        },
        // 文字色（通过 opacity 控制层级）
        text: {
          primary: 'var(--neutral-text-1)',
          secondary: 'var(--neutral-text-2, #4E5969)',
          tertiary: 'var(--neutral-text-3, #86909C)',
        },
      },
      // 圆角统一
      borderRadius: {
        sm: 'var(--radius-sm)',   // 8px
        md: 'var(--radius-md)',   // 12px
        lg: 'var(--radius-lg)',   // 16px
      },
      // 阴影统一
      boxShadow: {
        card: 'var(--shadow-card)',
        'card-hover': 'var(--shadow-card-hover)',
        dropdown: 'var(--shadow-dropdown)',
        soft: 'var(--shadow-soft)',
      },
    },
  },
}
```

**步骤 2：逐步替换现有 Tailwind 类名**

| 旧写法（Tailwind 默认） | 新写法（设计令牌） | 说明 |
|----------------------|------------------|------|
| `bg-gray-100` | `bg-neutral-bg` | 背景色 |
| `bg-white` | `bg-neutral-card` | 卡片背景 |
| `text-blue-600` | `text-primary` | 主色文字 |
| `text-gray-500` | `text-text-secondary` | 次要文字 |
| `text-gray-400` | `text-text-tertiary` | 辅助文字 |
| `bg-red-50` | `bg-danger/5` | 危险色背景（用 opacity） |
| `text-red-500` | `text-danger` | 危险色文字 |
| `bg-green-50` | `bg-success/5` | 成功色背景 |
| `border-gray-200` | `border-neutral-border` | 边框色 |
| `rounded-lg` | `rounded-lg` | 保持不变（已映射到 16px） |
| `shadow-md` | `shadow-card` | 卡片阴影 |

**步骤 3：具体组件改造示例**

以 `TaskTable.vue` 为例：

```vue
<!-- 改造前 -->
<div class="bg-gray-100 text-gray-500 rounded-lg shadow-md p-4">
  <span class="text-blue-600 font-medium">运行中</span>
</div>

<!-- 改造后 -->
<div class="bg-neutral-bg text-text-secondary rounded-lg shadow-card p-4">
  <span class="text-primary font-medium">运行中</span>
</div>
```

### 2.2 统一圆角硬编码

**问题**：全项目有 8+ 种不同的 `border-radius` 硬编码值：3px/4px/6px/8px/10px/12px/14px/16px。

**解决方案**：收敛到设计令牌的 3 档。

**映射表：**

| 当前硬编码值 | 应替换为 | 说明 |
|-------------|---------|------|
| `3px` / `4px` / `6px` | `var(--radius-sm)` (8px) | 小元素（标签、徽章） |
| `8px` / `10px` | `var(--radius-sm)` (8px) | 按钮、输入框 |
| `12px` / `14px` | `var(--radius-md)` (12px) | 中等卡片 |
| `16px` | `var(--radius-lg)` (16px) | 大卡片、弹窗 |

**需要修改的文件清单**：

```bash
# 搜索所有硬编码 border-radius（排除 node_modules 和 design tokens 定义文件）
grep -r "border-radius:" src/ --include="*.vue" --include="*.css" --include="*.scss" | \
  grep -v "var(--radius" | \
  grep -v "global.css" | \
  grep -v "chat-theme.css"

# 搜索硬编码的 rounded- 类（Tailwind 中未使用变量的）
grep -r "rounded-\[" src/ --include="*.vue" --include="*.css"
```

**特别注意**：Naive UI 的 `GlobalThemeOverrides` 中 `borderRadius: 6px` 与全局 `--radius-sm: 8px` 不一致，需要对齐。

```javascript
// App.vue 中的 GlobalThemeOverrides
const themeOverrides = {
  common: {
    // 从 6px 对齐到 8px
    borderRadius: '8px',
    // 其他覆盖...
  }
}
```

### 2.3 统一阴影硬编码

**问题**：多个组件自定义阴影值，未使用 `--shadow-*` 变量。

**解决方案**：统一引用设计令牌。

**阴影使用规范：**

| 场景 | 应使用的变量 | 值 |
|------|-------------|-----|
| 普通卡片 | `var(--shadow-card)` | `0 4px 16px rgba(29,33,41,0.04)` |
| 卡片悬停 | `var(--shadow-card-hover)` | `0 8px 24px rgba(29,33,41,0.08)` |
| 下拉菜单/弹窗 | `var(--shadow-dropdown)` | `0 4px 20px rgba(0,0,0,0.08)` |
| 柔和阴影 | `var(--shadow-soft)` | `0 4px 12px rgba(0,0,0,0.05)` |

**搜索需要修改的代码：**

```bash
grep -r "box-shadow:" src/ --include="*.vue" --include="*.css" --include="*.scss" | \
  grep -v "var(--shadow"
```

### 2.4 修复 Chat 浅色模式主色

**问题**：`chat-theme.css` 中 `--chat-accent: #2563eb`（Tailwind blue-600）与平台主色 `--arco-primary: #165DFF` 不同。

**解决方案**：在 `global.css` 中添加浅色模式的 chat 变量桥接。

```css
/* global.css */

/* 浅色模式 Chat 变量桥接 */
:root[data-theme="light"] {
  /* 已有变量... */

  /* Chat 子系统变量桥接 */
  --chat-accent: var(--arco-primary);
  --chat-accent-light: var(--arco-primary-100, rgba(22,93,255,0.1));
  --chat-bg: var(--neutral-card);
  --chat-bg-secondary: var(--neutral-bg);
  --chat-border: var(--neutral-border, #E5E6EB);
  --chat-text-primary: var(--neutral-text-1);
  --chat-text-secondary: var(--neutral-text-2, #4E5969);
}

/* 深色模式 Chat 变量桥接 */
:root[data-theme="dark"] {
  /* 已有变量... */

  /* Chat 子系统变量桥接 */
  --chat-accent: var(--arco-primary);
  --chat-accent-light: var(--arco-primary-200, rgba(22,93,255,0.2));
  --chat-bg: var(--neutral-card);
  --chat-bg-secondary: var(--neutral-bg);
  --chat-border: var(--neutral-border, #333);
  --chat-text-primary: var(--neutral-text-1);
  --chat-text-secondary: var(--neutral-text-2, #86909C);
}
```

然后修改 `chat-theme.css`，移除硬编码的 `--chat-accent`：

```css
/* chat-theme.css - 改造前 */
--chat-accent: #2563eb;

/* chat-theme.css - 改造后 */
/* 移除这一行，改为从 global.css 继承 */
```

---

## 三、P1 规范建立（1-2 周）

### 3.1 清理遗留组件

**问题**：`HeaderComponent.vue` 仍使用硬编码颜色（`#1890ff`、`#e8e8e8`、`white`），完全脱离设计系统。

**行动方案**：

1. 首先确认该组件是否仍在使用：
   ```bash
   grep -r "HeaderComponent" src/ --include="*.vue" --include="*.ts"
   ```

2. **如果不再使用**：直接删除文件
   ```bash
   git rm src/components/HeaderComponent.vue
   ```

3. **如果仍在使用**：迁移到 CSS 变量

```vue
<!-- HeaderComponent.vue 改造示例 -->
<template>
  <!-- 改造前 -->
  <header style="background: #1890ff; border-bottom: 1px solid #e8e8e8;">
    <span style="color: white;">OmicHub</span>
  </header>

  <!-- 改造后 -->
  <header class="header-component">
    <span class="header-title">OmicHub</span>
  </header>
</template>

<style scoped>
.header-component {
  background: var(--arco-primary);
  border-bottom: 1px solid var(--neutral-border);
}
.header-title {
  color: var(--neutral-card); /* 或 var(--neutral-text-1) 视对比度而定 */
}
</style>
```

### 3.2 建立响应式断点规范

**问题**：当前有 8+ 种不同的断点值（400px/480px/640px/720px/768px/820px/900px/1024px/1100px）。

**解决方案**：定义标准断点并写入 `tailwind.config.js`。

```javascript
// tailwind.config.js
module.exports = {
  theme: {
    screens: {
      'xs': '480px',    // 小屏手机
      'sm': '640px',    // 大屏手机
      'md': '768px',    // 平板
      'lg': '1024px',   // 小桌面
      'xl': '1280px',   // 大桌面
      '2xl': '1536px',  // 超大屏
    },
  },
}
```

**媒体查询使用规范**：

| 场景 | 写法 | 说明 |
|------|------|------|
| Vue template | `<div class="md:flex">` | 优先用 Tailwind 响应式类 |
| CSS 中 | `@media (min-width: 768px)` | 用具体 px 值时参考断点表 |
| 特殊场景 | `@media (max-width: 767px)` | 移动端优先时用 max-width |

**逐步替换现有媒体查询**：

```bash
# 搜索所有媒体查询中的硬编码值
grep -r "@media" src/ --include="*.vue" --include="*.css" --include="*.scss" | \
  grep -E "[0-9]+px"
```

### 3.3 建立 Type Scale（字体层级）

**问题**：页面标题 20px/24px/28px 不统一，卡片标题 15px-16px 浮动，正文 13px-14px 浮动。

**解决方案**：建立平台统一的 Type Scale。

**在 `global.css` 中添加字体变量：**

```css
:root {
  /* 已有变量... */

  /* === Type Scale === */
  /* Display - 登录页/欢迎页大标题 */
  --font-display-size: 28px;
  --font-display-height: 36px;
  --font-display-weight: 600;
  --font-display-spacing: -0.02em;

  /* Page Title - 页面标题 */
  --font-page-title-size: 24px;
  --font-page-title-height: 32px;
  --font-page-title-weight: 600;
  --font-page-title-spacing: -0.02em;

  /* Section Title - 区块标题 */
  --font-section-size: 18px;
  --font-section-height: 28px;
  --font-section-weight: 600;
  --font-section-spacing: -0.01em;

  /* Card Title - 卡片标题 */
  --font-card-title-size: 16px;
  --font-card-title-height: 24px;
  --font-card-title-weight: 500;

  /* Body - 正文 */
  --font-body-size: 14px;
  --font-body-height: 22px;
  --font-body-weight: 400;

  /* Small - 辅助文字 */
  --font-small-size: 13px;
  --font-small-height: 20px;
  --font-small-weight: 400;

  /* Caption - 标签/徽章 */
  --font-caption-size: 12px;
  --font-caption-height: 18px;
  --font-caption-weight: 400;

  /* Micro - 极小说明文字 */
  --font-micro-size: 11px;
  --font-micro-height: 16px;
  --font-micro-weight: 400;
}
```

**提供工具类（在 `global.css` 中）：**

```css
/* Type Scale 工具类 */
.font-display {
  font-size: var(--font-display-size);
  line-height: var(--font-display-height);
  font-weight: var(--font-display-weight);
  letter-spacing: var(--font-display-spacing);
}

.font-page-title {
  font-size: var(--font-page-title-size);
  line-height: var(--font-page-title-height);
  font-weight: var(--font-page-title-weight);
  letter-spacing: var(--font-page-title-spacing);
}

.font-section {
  font-size: var(--font-section-size);
  line-height: var(--font-section-height);
  font-weight: var(--font-section-weight);
  letter-spacing: var(--font-section-spacing);
}

.font-card-title {
  font-size: var(--font-card-title-size);
  line-height: var(--font-card-title-height);
  font-weight: var(--font-card-title-weight);
}

.font-body {
  font-size: var(--font-body-size);
  line-height: var(--font-body-height);
  font-weight: var(--font-body-weight);
}

.font-small {
  font-size: var(--font-small-size);
  line-height: var(--font-small-height);
  font-weight: var(--font-small-weight);
}

.font-caption {
  font-size: var(--font-caption-size);
  line-height: var(--font-caption-height);
  font-weight: var(--font-caption-weight);
}

.font-micro {
  font-size: var(--font-micro-size);
  line-height: var(--font-micro-height);
  font-weight: var(--font-micro-weight);
}
```

**使用示例：**

```vue
<template>
  <!-- 页面标题 -->
  <h1 class="font-page-title text-text-primary">数据管理</h1>

  <!-- 区块标题 -->
  <h2 class="font-section text-text-primary">样本列表</h2>

  <!-- 卡片标题 -->
  <h3 class="font-card-title text-text-primary">运行参数</h3>

  <!-- 正文 -->
  <p class="font-body text-text-secondary">这是一段说明文字...</p>

  <!-- 辅助文字 -->
  <span class="font-small text-text-tertiary">最后更新：2024-01-01</span>

  <!-- 标签 -->
  <span class="font-caption text-text-tertiary">NEW</span>
</template>
```

### 3.4 统一交互反馈

**问题**：卡片悬停效果不统一，按钮点击反馈不一致。

**解决方案**：统一交互规范。

**卡片悬停效果（改造 `global.css`）：**

```css
/* 统一卡片悬停 - 推荐 translateY(-4px) */
.card-hover {
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}
.card-hover:hover {
  transform: translateY(-4px);
  box-shadow: var(--shadow-card-hover);
}

/* 替代方案：更克制的 2px 上浮 */
.card-hover-subtle {
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}
.card-hover-subtle:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-card-hover);
}
```

> **建议**：统一用 `-4px`，`8px` 太浮夸不够简约，`2px` 感知不明显。

**按钮点击反馈：**

```css
/* 按钮点击缩放 */
.btn-press {
  transition: transform 0.1s ease;
}
.btn-press:active {
  transform: scale(0.97);
}
```

**所有可点击元素统一 hover/active：**

```css
/* 链接/文字按钮悬停 */
.link-hover {
  transition: color 0.15s ease;
}
.link-hover:hover {
  color: var(--arco-primary);
}

/* 统一焦点环（accessibility） */
.focus-ring:focus-visible {
  outline: 2px solid var(--arco-primary);
  outline-offset: 2px;
}
```

### 3.5 SCSS 使用规范

**问题**：6 个文件使用 `lang="scss"` 但未实际使用 SCSS 特性。

**解决方案**：制定使用规范。

**SCSS 使用原则：**

```
能用普通 CSS 解决的，不用 SCSS。
只在以下场景使用 SCSS：
1. 需要嵌套规则（&:hover, &__element）
2. 需要使用变量计算
3. 需要使用 mixin
4. 需要使用 @for/@each 循环
```

**具体建议：**

对于当前 6 个使用 SCSS 的文件（`AgentCard`、`AgentHub`、`AgentWorkspace`、`KimiMessageItem` 等）：

1. **检查是否实际使用了 SCSS 特性**：
   ```bash
   grep -l "lang=\"scss\"" src/ -r --include="*.vue"
   ```

2. **如果只用了普通 CSS**：去掉 `lang="scss"`，降低编译开销

3. **如果用了嵌套/变量**：保留，并制定规范

**SCSS 使用规范示例：**

```scss
<!-- AgentCard.vue -->
<style scoped lang="scss">
.agent-card {
  // 嵌套规则 - 合理使用 SCSS
  &__header {
    padding: 16px;

    &:hover {
      background: var(--neutral-bg);
    }
  }

  &__title {
    font-size: var(--font-card-title-size);
    font-weight: 500;
  }

  // & 父选择器引用
  &.is-active {
    border-color: var(--arco-primary);
  }
}
</style>
```

---

## 四、P2 视觉提升（2-3 周）

### 4.1 增加留白（Whitespace）

**现状**：卡片 padding 多为 `20px`，页面 padding `24px`，间距较紧凑。

**优化方案：**

| 元素 | 当前值 | 建议值 | 变化 |
|------|--------|--------|------|
| 卡片 padding | `20px` | `24px` | +4px |
| 大卡片 padding | `24px` | `28px` | +4px |
| 页面级 padding | `24px` | `32px` | +8px |
| 卡片间 gap | `16px` | `20px` | +4px |
| 区块间 gap | `24px` | `32px` | +8px |

**在 `global.css` 中定义间距变量：**

```css
:root {
  /* 间距体系 */
  --space-xs: 4px;
  --space-sm: 8px;
  --space-md: 12px;
  --space-lg: 16px;
  --space-xl: 20px;
  --space-2xl: 24px;
  --space-3xl: 32px;
  --space-4xl: 40px;
  --space-5xl: 48px;

  /* 卡片/页面专用间距 */
  --card-padding: 24px;
  --card-gap: 20px;
  --page-padding: 32px;
  --section-gap: 32px;
}
```

**布局容器更新：**

```css
/* 页面容器 */
.page-container {
  padding: var(--page-padding);
  max-width: 1440px;
  margin: 0 auto;
}

/* 卡片网格 */
.card-grid {
  display: grid;
  gap: var(--card-gap);
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
}

/* 卡片内边距 */
.arco-card {
  padding: var(--card-padding);
}
```

### 4.2 降低视觉噪音

**现状**：部分页面信息密度过高，装饰性元素过多。

**优化方案：**

**1. 减少同时出现的动画元素**

```css
/* 装饰性动画只在首屏/核心区域出现 */
.hero-section .gradient-bg {
  animation: gradientShift 8s ease infinite;
}

/* 其他区域移除或简化动画 */
.content-section .gradient-bg {
  animation: none; /* 或简化 */
}
```

**2. 渐变文字仅用于核心 CTA**

```css
/* 渐变文字限制使用 */
.gradient-text {
  background: linear-gradient(135deg, var(--arco-primary), #00B42A);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

/* 仅在以下场景使用：
   - 欢迎页/登录页大标题
   - 核心 CTA 按钮文字
   - 空状态引导文字
   不在以下场景使用：
   - 普通卡片标题
   - 正文内容
   - 导航栏
*/
```

**3. 降低阴影强度**

```css
:root {
  /* 当前 */
  --shadow-card: 0 4px 16px rgba(29,33,41,0.04);
  /* 建议 */
  --shadow-card: 0 4px 16px rgba(29,33,41,0.03);

  /* 当前 */
  --shadow-card-hover: 0 8px 24px rgba(29,33,41,0.08);
  /* 建议 */
  --shadow-card-hover: 0 8px 24px rgba(29,33,41,0.06);
}
```

**4. 降低边框透明度**

```css
:root[data-theme="light"] {
  /* 当前 */
  --neutral-border: rgba(229,230,235,0.5);
  /* 建议 */
  --neutral-border: rgba(229,230,235,0.3);
}

:root[data-theme="dark"] {
  /* 暗色模式使用白色透明 */
  --neutral-border: rgba(255,255,255,0.06);
}
```

### 4.3 强化排版层次

**优化方案：**

**1. 标题统一增加 letter-spacing 和 font-weight**

```css
/* 已在 Type Scale 中定义，这里强调使用 */
.font-page-title,
.font-section {
  font-weight: 600;
  letter-spacing: -0.02em;
}

/* 数字/统计数据强化 */
.stat-number {
  font-size: 32px;
  font-weight: 700;
  letter-spacing: -0.03em;
  color: var(--neutral-text-1);
  /* 可选：等宽字体 */
  font-variant-numeric: tabular-nums;
}
```

**2. 次要信息拉开层次**

```vue
<!-- 改造前 -->
<div>
  <span class="text-text-secondary">样本数量</span>
  <span class="text-text-secondary">1,234</span>
</div>

<!-- 改造后 -->
<div>
  <span class="font-caption text-text-tertiary">样本数量</span>
  <span class="stat-number text-text-primary">1,234</span>
</div>
```

### 4.4 深色模式精致化

**优化方案：**

**1. 暗色模式阴影微调**

```css
:root[data-theme="dark"] {
  /* 当前阴影偏重，微调 */
  --shadow-card: 0 4px 16px rgba(0,0,0,0.20);
  --shadow-card-hover: 0 8px 24px rgba(0,0,0,0.28);
  --shadow-dropdown: 0 4px 20px rgba(0,0,0,0.30);
}
```

**2. 暗色模式边框使用半透明白色**

```css
:root[data-theme="dark"] {
  /* 替代固定的 #333 */
  --neutral-border: rgba(255,255,255,0.06);
}
```

**3. 暗色模式文字对比度检查**

```bash
# 使用 axe-core 或 Lighthouse 检查对比度
# 确保所有文字满足 WCAG AA 标准（4.5:1）
```

---

## 五、P3 锦上添花（按需）

### 5.1 Tailwind Preflight 策略（无需改动）

当前 Tailwind preflight 已关闭以避免与 Naive UI 冲突，这是合理策略。

**建议**：将 Tailwind 主要用于布局工具（flex/grid/gap/space），颜色/阴影走 CSS 变量，减少冲突面。

### 5.2 动画性能优化

**`gradientShift` 动画优化：**

```css
/* 改造前 - 可能触发重绘 */
@keyframes gradientShift {
  0% { background-position: 0% 50%; }
  50% { background-position: 100% 50%; }
  100% { background-position: 0% 50%; }
}

.gradient-bg {
  background-size: 200% 200%;
  animation: gradientShift 8s ease infinite;
}

/* 改造后 - 使用 will-change 提示 */
.gradient-bg {
  background-size: 200% 200%;
  animation: gradientShift 8s ease infinite;
  will-change: background-position; /* 提示浏览器优化 */
}

/* 或改用 CSS @property（更现代的方式） */
@property --gradient-angle {
  syntax: '<angle>';
  initial-value: 0deg;
  inherits: false;
}

@keyframes gradientRotate {
  to { --gradient-angle: 360deg; }
}

.gradient-bg-modern {
  background: conic-gradient(from var(--gradient-angle), var(--arco-primary), #00B42A, var(--arco-primary));
  animation: gradientRotate 8s linear infinite;
}
```

### 5.3 Naive UI 组件样式深度定制

如需进一步统一 Naive UI 组件与平台风格：

```javascript
// App.vue - GlobalThemeOverrides 完整配置参考
const themeOverrides = {
  common: {
    primaryColor: 'var(--arco-primary)',
    primaryColorHover: 'var(--arco-primary-hover, #3B82F6)',
    primaryColorPressed: 'var(--arco-primary-pressed, #0E42D2)',
    primaryColorSuppl: 'var(--arco-primary)',
    successColor: 'var(--arco-success)',
    warningColor: 'var(--arco-warning)',
    errorColor: 'var(--arco-danger)',
    borderRadius: '8px',
    fontSize: '14px',
    fontSizeMedium: '14px',
    fontSizeLarge: '16px',
    heightMedium: '36px',
    heightLarge: '40px',
  },
  Button: {
    borderRadius: '8px',
    fontWeight: '500',
  },
  Card: {
    borderRadius: '12px',
    paddingMedium: '24px',
    paddingLarge: '28px',
  },
  Input: {
    borderRadius: '8px',
    heightMedium: '36px',
  },
  // ... 其他组件
}
```

---

## 六、具体组件改造示例

### 6.1 DownloadsView.vue 改造

**改造前：**

```vue
<template>
  <div class="bg-gray-100 min-h-screen p-6">
    <div class="bg-white rounded-lg shadow-md p-5">
      <h2 class="text-xl font-semibold text-gray-800 mb-4">公共数据下载</h2>
      <div class="text-blue-600 cursor-pointer hover:underline">高级选项</div>
      <div class="bg-red-50 text-red-500 p-3 rounded mt-2">错误提示</div>
    </div>
  </div>
</template>
```

**改造后：**

```vue
<template>
  <div class="bg-neutral-bg min-h-screen" style="padding: var(--page-padding)">
    <div class="bg-neutral-card rounded-lg shadow-card" style="padding: var(--card-padding)">
      <h2 class="font-page-title text-text-primary" style="margin-bottom: var(--space-lg)">
        公共数据下载
      </h2>
      <div class="text-primary cursor-pointer link-hover font-small">高级选项</div>
      <div class="bg-danger/5 text-danger p-3 rounded mt-2 font-small">错误提示</div>
    </div>
  </div>
</template>

<style scoped>
/* 如需自定义，使用 CSS 变量 */
.downloads-page {
  background: var(--neutral-bg);
  min-height: 100vh;
  padding: var(--page-padding);
}
</style>
```

### 6.2 TaskTable.vue 改造

**改造前：**

```vue
<template>
  <div class="overflow-x-auto">
    <table class="w-full text-sm">
      <thead class="bg-gray-50">
        <tr>
          <th class="px-4 py-3 text-left text-gray-500">任务名</th>
          <th class="px-4 py-3 text-left text-gray-500">状态</th>
        </tr>
      </thead>
      <tbody>
        <tr class="border-b border-gray-100">
          <td class="px-4 py-3 text-blue-600">基因组分析</td>
          <td class="px-4 py-3">
            <span class="bg-green-50 text-green-600 px-2 py-1 rounded">运行中</span>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
```

**改造后：**

```vue
<template>
  <div class="overflow-x-auto">
    <table class="w-full font-body">
      <thead class="bg-neutral-bg">
        <tr>
          <th class="px-4 py-3 text-left font-caption text-text-tertiary">任务名</th>
          <th class="px-4 py-3 text-left font-caption text-text-tertiary">状态</th>
        </tr>
      </thead>
      <tbody>
        <tr class="border-b" style="border-color: var(--neutral-border)">
          <td class="px-4 py-3 text-primary font-medium">基因组分析</td>
          <td class="px-4 py-3">
            <span class="bg-success/5 text-success px-2 py-1 rounded font-caption">运行中</span>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
/* 如需更精细控制 */
table th {
  font-weight: 500;
}
table td {
  color: var(--neutral-text-1);
}
</style>
```

### 6.3 DeleteConfirmModal.vue 改造

**改造前：**

```vue
<template>
  <div class="bg-white rounded-xl shadow-lg p-6 max-w-md">
    <div class="text-red-500 mb-4">
      <icon-warning />
    </div>
    <h3 class="text-lg font-semibold text-gray-900 mb-2">确认删除</h3>
    <p class="text-gray-500 mb-6">删除后无法恢复，是否继续？</p>
    <div class="flex gap-3">
      <button class="flex-1 bg-gray-100 text-gray-700 py-2 rounded-lg">取消</button>
      <button class="flex-1 bg-red-500 text-white py-2 rounded-lg">删除</button>
    </div>
  </div>
</template>
```

**改造后：**

```vue
<template>
  <div class="bg-neutral-card rounded-lg shadow-dropdown max-w-md" style="padding: var(--card-padding)">
    <div class="text-danger mb-4">
      <icon-warning />
    </div>
    <h3 class="font-section text-text-primary mb-2">确认删除</h3>
    <p class="font-body text-text-secondary mb-6">删除后无法恢复，是否继续？</p>
    <div class="flex gap-3">
      <button class="flex-1 py-2 rounded-lg btn-press" style="background: var(--neutral-bg); color: var(--neutral-text-1)">
        取消
      </button>
      <button class="flex-1 py-2 rounded-lg btn-press" style="background: var(--arco-danger); color: white">
        删除
      </button>
    </div>
  </div>
</template>

<style scoped>
button {
  font-size: var(--font-body-size);
  font-weight: 500;
  transition: opacity 0.15s ease;
}
button:hover {
  opacity: 0.9;
}
</style>
```

---

## 七、推荐引入的开源库

### 7.1 高优先级引入

#### AutoAnimate — 零配置列表动画

```bash
npm install @formkit/auto-animate
```

**使用方式（极简）：**

```vue
<script setup>
import { vAutoAnimate } from '@formkit/auto-animate'

const items = ref([...])
</script>

<template>
  <!-- 加一行指令，列表自动获得流畅增删动画 -->
  <ul v-auto-animate>
    <li v-for="item in items" :key="item.id">
      {{ item.name }}
    </li>
  </ul>
</template>
```

**适用场景：**
- 任务列表增删
- 文件列表变化
- 消息列表新消息插入
- 卡片网格筛选/排序

**为什么推荐**：一个指令解决所有列表动画，与"简约大气"的微交互理念完美契合。

### 7.2 中优先级引入

#### Lucide Icons — 更现代的图标

```bash
npm install lucide-vue-next
```

**使用方式：**

```vue
<script setup>
import { FolderOpen, Dna, Settings, Download } from 'lucide-vue-next'
</script>

<template>
  <FolderOpen :size="20" />
  <Dna :size="20" stroke-width="1.5" />
</template>
```

**迁移策略**：
- 新页面优先使用 Lucide
- 旧页面逐步替换（不需要一次性全改）
- 建立图标映射表：

| Ionicons5 | Lucide | 说明 |
|-----------|--------|------|
| `folder-open-outline` | `FolderOpen` | 文件夹 |
| `settings-outline` | `Settings` | 设置 |
| `download-outline` | `Download` | 下载 |
| `trash-outline` | `Trash2` | 删除 |
| `add-circle-outline` | `PlusCircle` | 添加 |
| `alert-circle-outline` | `AlertCircle` | 警告 |

### 7.3 低优先级引入

#### Fontsource — 自托管 Inter 字体

```bash
npm install @fontsource/inter
```

**使用方式：**

```javascript
// main.js
import '@fontsource/inter/400.css'
import '@fontsource/inter/500.css'
import '@fontsource/inter/600.css'
import '@fontsource/inter/700.css'
```

**好处**：避免 Google Fonts 依赖，离线可用，加载更快。

#### PrimeVue（按需引入）

如需补充 Naive UI 未覆盖的组件：

```bash
npm install primevue
```

```javascript
// main.js
import OverlayPanel from 'primevue/overlaypanel'
import Timeline from 'primevue/timeline'
import Splitter from 'primevue/splitter'

app.component('OverlayPanel', OverlayPanel)
```

---

## 八、实施路线图与检查清单

### Phase 1：统一基础（本周内）

目标：解决最影响一致性的颜色/圆角/阴影问题。

- [ ] **Day 1**：修改 `tailwind.config.js`，添加设计令牌映射
- [ ] **Day 1**：修复 Chat 浅色模式主色（`global.css` 桥接）
- [ ] **Day 2-3**：改造 `DownloadsView.vue`（Tailwind → CSS 变量）
- [ ] **Day 2-3**：改造 `TaskTable.vue`（Tailwind → CSS 变量）
- [ ] **Day 2-3**：改造 `DeleteConfirmModal.vue`（Tailwind → CSS 变量）
- [ ] **Day 4**：统一圆角硬编码（搜索替换为 `var(--radius-*)`）
- [ ] **Day 4-5**：统一阴影硬编码（搜索替换为 `var(--shadow-*)`）
- [ ] **Day 5**：对齐 Naive UI borderRadius（6px → 8px）
- [ ] **Day 5-7**：处理其他 Tailwind 组件（`OnboardingPopup.vue` 等）

**Phase 1 完成标准：**
- 所有 Tailwind 组件使用设计令牌颜色
- 无 Tailwind 默认色板（gray/blue/red/green）残留
- 圆角只有 3 种（8px/12px/16px）
- Chat 浅色模式主色与平台一致

### Phase 2：规范建立（第 2 周）

目标：建立可复用的规范体系。

- [ ] 在 `global.css` 中添加 Type Scale 变量和工具类
- [ ] 在 `tailwind.config.js` 中添加标准断点
- [ ] 统一卡片悬停效果（`-4px` + 阴影升级）
- [ ] 统一按钮点击反馈（`scale(0.97)`）
- [ ] 清理/迁移 `HeaderComponent.vue`
- [ ] 制定 SCSS 使用规范

**Phase 2 完成标准：**
- 有完整的 Type Scale 可用
- 有标准断点规范
- 交互反馈统一

### Phase 3：视觉提升（第 3-4 周）

目标：提升"大气"感。

- [ ] 增加留白（卡片 padding 20px→24px，页面间距 24px→32px）
- [ ] 降低视觉噪音（减少装饰性动画、降低阴影/边框强度）
- [ ] 强化排版层次（letter-spacing、font-weight 对比）
- [ ] 深色模式微调（边框透明度、阴影参数）

**Phase 3 完成标准：**
- 整体留白增加 20%+
- 无多余装饰性动画
- 排版层次清晰

### Phase 4：库升级（第 5 周起，按需）

- [ ] 引入 AutoAnimate（`@formkit/auto-animate`）
- [ ] 新页面使用 Lucide 图标
- [ ] 评估 PrimeVue 补充组件
- [ ] 使用 Fontsource 自托管 Inter 字体

### 持续进行

- [ ] 新页面/组件严格遵循设计令牌
- [ ] 旧页面遇到 bug 时顺手修复
- [ ] 定期运行统一性检查脚本

**统一性检查脚本：**

```bash
#!/bin/bash
# check-consistency.sh

echo "=== OmicHub 前端一致性检查 ==="
echo ""

echo "1. 检查 Tailwind 默认色板残留..."
grep -rn "bg-gray-\|text-gray-\|text-blue-\|bg-blue-\|text-red-\|bg-red-\|text-green-\|bg-green-" \
  src/ --include="*.vue" | grep -v "node_modules" | head -20

echo ""
echo "2. 检查圆角硬编码..."
grep -rn "border-radius:\s*[0-9]" \
  src/ --include="*.vue" --include="*.css" | \
  grep -v "var(--radius" | grep -v "global.css" | head -20

echo ""
echo "3. 检查阴影硬编码..."
grep -rn "box-shadow:" \
  src/ --include="*.vue" --include="*.css" | \
  grep -v "var(--shadow" | head -20

echo ""
echo "4. 检查颜色硬编码（#rrggbb 格式）..."
grep -rn "#[0-9A-Fa-f]\{6\}" \
  src/ --include="*.vue" --include="*.css" | \
  grep -v "global.css" | grep -v "chat-theme.css" | head -20

echo ""
echo "检查完成！"
```

---

## 九、附录：设计令牌速查表

### 颜色

| 变量 | 亮色 | 暗色 | 用途 |
|------|------|------|------|
| `--arco-primary` | `#165DFF` | `#3B82F6` | 主色 |
| `--arco-success` | `#00B42A` | `#22C55E` | 成功 |
| `--arco-warning` | `#FF7D00` | `#F59E0B` | 警告 |
| `--arco-danger` | `#F53F3F` | `#EF4444` | 危险 |
| `--neutral-bg` | `#F2F3F8` | `#0B0F19` | 页面背景 |
| `--neutral-card` | `#FFFFFF` | `#151A25` | 卡片背景 |
| `--neutral-border` | `rgba(229,230,235,0.3)` | `rgba(255,255,255,0.06)` | 边框 |
| `--neutral-text-1` | `#1D2129` | `#F2F3F8` | 主文字 |
| `--neutral-text-2` | `#4E5969` | `#C9CDD4` | 次要文字 |
| `--neutral-text-3` | `#86909C` | `#6B7785` | 辅助文字 |

### 阴影

| 变量 | 值（亮色） |
|------|-----------|
| `--shadow-card` | `0 4px 16px rgba(29,33,41,0.03)` |
| `--shadow-card-hover` | `0 8px 24px rgba(29,33,41,0.06)` |
| `--shadow-dropdown` | `0 4px 20px rgba(0,0,0,0.08)` |
| `--shadow-soft` | `0 4px 12px rgba(0,0,0,0.05)` |

### 圆角

| 变量 | 值 | 用途 |
|------|-----|------|
| `--radius-sm` | `8px` | 按钮、输入框、小元素 |
| `--radius-md` | `12px` | 中等卡片 |
| `--radius-lg` | `16px` | 大卡片、弹窗 |

### 间距

| 变量 | 值 |
|------|-----|
| `--card-padding` | `24px` |
| `--card-gap` | `20px` |
| `--page-padding` | `32px` |
| `--section-gap` | `32px` |

### 字体

| 层级 | 变量 | 大小 | 行高 | 字重 |
|------|------|------|------|------|
| Display | `--font-display-*` | 28px | 36px | 600 |
| Page Title | `--font-page-title-*` | 24px | 32px | 600 |
| Section | `--font-section-*` | 18px | 28px | 600 |
| Card Title | `--font-card-title-*` | 16px | 24px | 500 |
| Body | `--font-body-*` | 14px | 22px | 400 |
| Small | `--font-small-*` | 13px | 20px | 400 |
| Caption | `--font-caption-*` | 12px | 18px | 400 |
| Micro | `--font-micro-*` | 11px | 16px | 400 |

### Tailwind 映射速查

| 想表达的意思 | Tailwind 类 |
|-------------|------------|
| 主色文字 | `text-primary` |
| 成功色文字 | `text-success` |
| 危险色文字 | `text-danger` |
| 警告色文字 | `text-warning` |
| 背景色 | `bg-neutral-bg` |
| 卡片背景 | `bg-neutral-card` |
| 主文字 | `text-text-primary` |
| 次要文字 | `text-text-secondary` |
| 辅助文字 | `text-text-tertiary` |
| 边框色 | `border-neutral-border` |
| 小圆角 | `rounded-sm` (8px) |
| 中圆角 | `rounded-md` (12px) |
| 大圆角 | `rounded-lg` (16px) |
| 卡片阴影 | `shadow-card` |
| 柔和阴影 | `shadow-soft` |

---

## 结语

> **核心原则：先统一，再美化。新代码不犯错，旧代码顺手修。**

你的平台架构已经非常健康，不需要大重构。重点是：

1. **让设计令牌真正落地** — 把硬编码的颜色、圆角、阴影清理干净
2. **建立规范** — Type Scale、断点、交互反馈统一
3. **做减法** — 增加留白，降低视觉噪音，克制用色
4. **微动效优先** — AutoAnimate 一个指令解决列表动画，简洁优雅

按照这个路线走，暑假结束完整上线时，平台的一致性和视觉品质都会有质的提升。不需要追求完美，追求"每次提交都比之前好一点"就够了。

---

*文档版本：v1.0*
*生成日期：2026-07-04*
*适用平台：OmicHub 前端全站*
