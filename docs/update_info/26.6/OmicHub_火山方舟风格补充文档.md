# OmicHub 火山方舟风格补充优化文档

> 本文档基于用户指定的"火山方舟（火山引擎）"UI风格偏好进行补充
> 参考截图：火山方舟控制台首页 + 应用实验室页面
> 
> **核心发现**：火山引擎控制台超过60%产品使用 **Arco Design**（字节跳动企业级设计系统）

---

## 一、火山方舟风格特征分析

### 1.1 色彩特征

| 元素 | 颜色值 | 说明 |
|------|--------|------|
| 页面背景 | `#F2F3F8` | 极浅的蓝灰色，比纯白柔和 |
| 卡片背景 | `#FFFFFF` | 纯白，与背景形成微妙层次 |
| 主要文字 | `#1D2129` | 接近纯黑，但略带暖色 |
| 次要文字 | `#4E5969` | 深灰色 |
| 辅助文字 | `#86909C` | 浅灰色 |
| 主题色 | `#165DFF` | 亮蓝色（Arco Design 默认主色） |
| 成功色 | `#00B42A` | 绿色 |
| 警告色 | `#FF7D00` | 橙色 |
| 危险色 | `#F53F3F` | 红色 |
| 边框色 | `#E5E6EB` | 极浅灰 |
| 悬浮背景 | `#F2F3F8` | 与页面背景同色 |

### 1.2 布局特征

- **极大留白**：卡片之间、模块之间有大量留白空间
- **圆角卡片**：卡片圆角约 `12px`，阴影极淡或无边框风格
- **左侧导航**：宽度约 `220px`，图标+文字，当前项蓝色背景高亮
- **顶部公告栏**：可关闭的横幅（Banner），带渐变色背景
- **两栏布局**：数据概览区域常采用左右分栏（如余额+图表）
- **步骤引导**：Step1 → Step2 的水平步骤条，箭头连接

### 1.3 组件特征

- **按钮**：圆角 `6px`，主按钮实心蓝色，次按钮灰色边框
- **标签 Tag**：药丸形状（`rounded-full`），浅色背景+深色文字
- **图表**：柱状图+折线图组合，双Y轴，蓝色主色调
- **卡片网格**：等宽卡片排列，顶部可带彩色渐变背景图
- **图标**：线性风格，`strokeWidth={1.5}`，简洁干净

---

## 二、与 Arco Design 的关系

### 2.1 核心发现

> **火山引擎控制台超过60%产品使用 Arco Design 组件库进行搭建** —— 字节跳动官方数据

这意味着火山方舟的UI风格本质上就是 **Arco Design 的默认主题风格**。

### 2.2 可选方案对比

| 方案 | 描述 | 优点 | 缺点 | 推荐度 |
|------|------|------|------|--------|
| **方案A：引入 Arco Design** | 直接安装 `@arco-design/web-react` | 100%还原火山引擎风格；组件丰富（60+） | 与现有 shadcn/ui 可能冲突；需重新配置主题；包体积增大 | ⭐⭐⭐ |
| **方案B：shadcn/ui + Tailwind 仿 Arco 风格** | 保持现有技术栈，通过 Tailwind 配置模仿 Arco 配色和风格 | 无兼容性问题；工程改动最小；保持 shadcn 生态优势 | 需手动调色调样式 | ⭐⭐⭐⭐⭐ |
| **方案C：混合方案** | 基础组件用 shadcn/ui，复杂组件（图表、步骤条）引入 Arco | 兼顾两者优势 | 维护复杂度增加 | ⭐⭐⭐⭐ |

### 2.3 推荐方案：方案B（详细说明）

**原因**：
1. 项目已基于 `shadcn/ui + Tailwind`，迁移成本高
2. shadcn/ui 的组件质量足够，只需调整视觉风格
3. Tailwind 的定制化能力完全可以复刻 Arco Design 的视觉效果
4. 避免引入两个 UI 库的样式冲突

---

## 三、具体实现方案

### 3.1 Tailwind 配置更新

```javascript
// tailwind.config.ts —— 添加火山方舟/Arco Design 色彩映射
import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      // ===== 火山方舟/Arco Design 色彩体系 =====
      colors: {
        // Arco 主色板
        arco: {
          primary: "#165DFF",
          "primary-light": "#E8F3FF",
          success: "#00B42A",
          "success-light": "#E8FFEA",
          warning: "#FF7D00",
          "warning-light": "#FFF7E8",
          danger: "#F53F3F",
          "danger-light": "#FFECE8",
        },
        // 中性色板
        neutral: {
          bg: "#F2F3F8",        // 页面背景
          card: "#FFFFFF",       // 卡片背景
          border: "#E5E6EB",   // 边框
          "text-1": "#1D2129", // 主要文字
          "text-2": "#4E5969", // 次要文字
          "text-3": "#86909C", // 辅助文字
          "text-4": "#C9CDD4", // 占位符
          hover: "#F2F3F8",    // 悬浮背景
        },
        // 侧边栏专用
        sidebar: {
          bg: "#FFFFFF",
          hover: "#F2F3F8",
          active: "#E8F3FF",
          "active-text": "#165DFF",
          border: "#E5E6EB",
        },
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        popover: {
          DEFAULT: "hsl(var(--popover))",
          foreground: "hsl(var(--popover-foreground))",
        },
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
      },
      // ===== 圆角系统 =====
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
        "arco-card": "12px",
        "arco-btn": "6px",
        "arco-tag": "9999px",
        "arco-input": "6px",
      },
      // ===== 阴影系统 =====
      boxShadow: {
        "arco-card": "0 4px 16px rgba(29, 33, 41, 0.04)",
        "arco-card-hover": "0 8px 24px rgba(29, 33, 41, 0.08)",
        "arco-dropdown": "0 4px 20px rgba(0, 0, 0, 0.08)",
      },
      // ===== 间距系统 =====
      spacing: {
        "page": "24px",
        "card": "20px",
        "section": "32px",
      },
      // ===== 字体系统 =====
      fontSize: {
        "arco-h1": ["24px", { lineHeight: "32px", fontWeight: "600" }],
        "arco-h2": ["18px", { lineHeight: "26px", fontWeight: "600" }],
        "arco-h3": ["16px", { lineHeight: "24px", fontWeight: "500" }],
        "arco-body": ["14px", { lineHeight: "22px", fontWeight: "400" }],
        "arco-caption": ["12px", { lineHeight: "20px", fontWeight: "400" }],
        "arco-metric": ["32px", { lineHeight: "40px", fontWeight: "600" }],
      },
      keyframes: {
        "accordion-down": {
          from: { height: "0" },
          to: { height: "var(--radix-accordion-content-height)" },
        },
        "accordion-up": {
          from: { height: "var(--radix-accordion-content-height)" },
          to: { height: "0" },
        },
      },
      animation: {
        "accordion-down": "accordion-down 0.2s ease-out",
        "accordion-up": "accordion-up 0.2s ease-out",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};

export default config;
```

### 3.2 CSS 变量更新

```css
/* globals.css —— 添加火山方舟风格的全局变量 */
@layer base {
  :root {
    --background: 0 0% 100%;
    --foreground: 220 13% 13%;
    --card: 0 0% 100%;
    --card-foreground: 220 13% 13%;
    --popover: 0 0% 100%;
    --popover-foreground: 220 13% 13%;
    --primary: 220 100% 55%;
    --primary-foreground: 0 0% 100%;
    --secondary: 220 14% 96%;
    --secondary-foreground: 220 13% 13%;
    --muted: 220 14% 96%;
    --muted-foreground: 215 14% 55%;
    --accent: 220 14% 96%;
    --accent-foreground: 220 13% 13%;
    --destructive: 0 84% 60%;
    --destructive-foreground: 0 0% 100%;
    --border: 220 13% 91%;
    --input: 220 13% 91%;
    --ring: 220 100% 55%;
    --radius: 0.75rem;

    /* 火山方舟自定义变量 */
    --arco-bg: #F2F3F8;
    --arco-card-bg: #FFFFFF;
    --arco-border: #E5E6EB;
    --arco-text-1: #1D2129;
    --arco-text-2: #4E5969;
    --arco-text-3: #86909C;
    --arco-primary: #165DFF;
    --arco-primary-light: #E8F3FF;
  }
}

@layer base {
  * {
    @apply border-border;
  }
  body {
    @apply bg-neutral-bg text-neutral-text-1 antialiased;
    font-family: "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, "Noto Sans SC", "PingFang SC", "Microsoft YaHei", sans-serif;
  }
}
```

---

## 四、组件风格对照表

### 4.1 卡片（Card）

```tsx
// 火山方舟风格卡片
<div className="
  bg-white 
  rounded-xl           // 12px 圆角
  p-5                  // 20px 内边距
  shadow-arco-card     // 极淡阴影
  border border-neutral-border/50
  transition-all duration-300
  hover:shadow-arco-card-hover
  hover:-translate-y-0.5
">
  {/* 卡片内容 */}
</div>
```

### 4.2 按钮（Button）

```tsx
// 主按钮 —— 实心蓝色
<button className="
  px-4 py-2
  bg-arco-primary text-white
  rounded-md           // 6px 圆角
  text-sm font-medium
  hover:bg-blue-600
  active:bg-blue-700
  transition-colors
">
  提交分析
</button>

// 次按钮 —— 灰色边框
<button className="
  px-4 py-2
  bg-white text-neutral-text-1
  rounded-md
  text-sm font-medium
  border border-neutral-border
  hover:bg-neutral-hover
  active:bg-gray-100
  transition-colors
">
  取消
</button>

// 文字按钮
<button className="
  px-2 py-1
  text-arco-primary
  text-sm font-medium
  hover:text-blue-600
  hover:bg-arco-primary-light
  rounded-md
  transition-colors
">
  查看全部 →
</button>
```

### 4.3 标签（Tag）

```tsx
// 药丸标签 —— 火山方舟风格
<span className="
  inline-flex items-center
  px-2.5 py-0.5
  rounded-full           // 药丸形状
  text-xs font-medium
  bg-arco-primary/10    // 10% 主色背景
  text-arco-primary     // 主色文字
">
  RNA-seq
</span>

// 不同颜色的标签
const tagVariants = {
  blue:   "bg-blue-50 text-blue-600",
  green:  "bg-green-50 text-green-600",
  orange: "bg-orange-50 text-orange-600",
  red:    "bg-red-50 text-red-600",
  purple: "bg-purple-50 text-purple-600",
  gray:   "bg-gray-100 text-gray-600",
};
```

### 4.4 侧边栏导航（Sidebar）

```tsx
// 火山方舟风格侧边栏 —— 220px 宽度
<aside className="
  w-[220px] 
  h-screen 
  bg-sidebar-bg 
  border-r border-sidebar-border
  flex flex-col
">
  {/* Logo 区域 */}
  <div className="h-14 flex items-center px-4 border-b border-sidebar-border">
    <span className="text-lg font-semibold text-neutral-text-1">OmicHub</span>
  </div>

  {/* 导航项 */}
  <nav className="flex-1 py-3 px-3 space-y-1">
    {/* 普通项 */}
    <a className="
      flex items-center gap-3 
      px-3 py-2.5 
      rounded-lg
      text-sm text-neutral-text-2
      hover:bg-sidebar-hover
      transition-colors
    ">
      <Home size={18} strokeWidth={1.5} />
      <span>首页</span>
    </a>

    {/* 当前激活项 */}
    <a className="
      flex items-center gap-3 
      px-3 py-2.5 
      rounded-lg
      text-sm font-medium
      bg-sidebar-active
      text-sidebar-active-text
      transition-colors
    ">
      <LayoutDashboard size={18} strokeWidth={1.5} />
      <span>控制台</span>
    </a>
  </nav>
</aside>
```

### 4.5 公告横幅（Banner）

```tsx
// 火山方舟风格公告横幅 —— 可关闭
<div className="
  relative
  bg-gradient-to-r from-indigo-500 to-purple-500
  rounded-xl
  p-4 pr-12
  text-white
  mb-6
">
  <div className="flex items-center gap-3">
    <div className="w-10 h-10 rounded-lg bg-white/20 flex items-center justify-center">
      <Sparkles size={20} />
    </div>
    <div>
      <h4 className="font-medium text-sm">单细胞分析模块即将上线</h4>
      <p className="text-xs text-white/80">全新支持 10x Genomics 数据，敬请期待</p>
    </div>
  </div>
  <button className="
    absolute right-3 top-1/2 -translate-y-1/2
    w-6 h-6 rounded-full
    bg-white/20 hover:bg-white/30
    flex items-center justify-center
    transition-colors
  ">
    <X size={14} />
  </button>
</div>
```

### 4.6 步骤引导（Steps）

```tsx
// 火山方舟风格步骤条 —— Step1 → Step2 → Step3
<div className="flex items-center gap-2 mb-6">
  {/* 已完成步骤 */}
  <div className="flex items-center gap-2">
    <span className="
      w-6 h-6 rounded-full 
      bg-arco-primary text-white 
      flex items-center justify-center 
      text-xs font-medium
    ">1</span>
    <span className="text-sm text-arco-primary font-medium">快速接入</span>
  </div>

  {/* 连接箭头 */}
  <ChevronRight size={16} className="text-neutral-text-4 mx-1" />

  {/* 当前步骤 */}
  <div className="flex items-center gap-2">
    <span className="
      w-6 h-6 rounded-full 
      bg-arco-primary text-white 
      flex items-center justify-center 
      text-xs font-medium
    ">2</span>
    <span className="text-sm text-arco-primary font-medium">Token 计算与用量</span>
  </div>

  {/* 连接箭头 */}
  <ChevronRight size={16} className="text-neutral-text-4 mx-1" />

  {/* 待完成步骤 */}
  <div className="flex items-center gap-2">
    <span className="
      w-6 h-6 rounded-full 
      bg-neutral-border text-neutral-text-3 
      flex items-center justify-center 
      text-xs font-medium
    ">3</span>
    <span className="text-sm text-neutral-text-3">数据分析</span>
  </div>
</div>
```

---

## 五、分析流程展示方案（基于应用实验室风格）

### 5.1 设计目标

将火山方舟"应用实验室"的卡片网格布局应用于 OmicHub 的分析流程展示：
- 大图卡片展示推荐/热门分析流程
- 小卡片网格展示所有可用分析流程
- 每个卡片包含：图标、名称、描述、标签

### 5.2 布局结构

```
┌──────────────────────────────────────────────────────────────┐
│  Header Bar                                                   │
├──────────┬───────────────────────────────────────────────────┤
│          │  分析流程中心                                       │
│          │  选择适合您研究需求的分析流程，快速启动多组学分析      │
│          │                                                   │
│ Sidebar  │  [🔥 推荐流程]                                    │
│          │  ┌─────────────────────────────────────┐          │
│          │  │ [大图卡片 - 带彩色渐变背景]            │          │
│          │  │  RNA-seq 差异表达分析                  │          │
│          │  │  适用于基因表达定量与差异分析...         │          │
│          │  │  [热门] [转录组] [Doubao]             │          │
│          │  └─────────────────────────────────────┘          │
│          │                                                   │
│          │  [📋 全部流程]                                    │
│          │  ┌──────────┐ ┌──────────┐ ┌──────────┐         │
│          │  │ 🧬 ATAC  │ │ 🧬 ChIP  │ │ 🧬 单细胞 │         │
│          │  │ seq      │ │ seq      │ │  RNA    │         │
│          │  │ 染色质可 │ │ 蛋白-DNA │ │ 细胞聚类 │         │
│          │  │ 及性分析 │ │ 互作分析 │ │ 与注释   │         │
│          │  │ [表观遗传]│ │ [表观遗传]│ │ [单细胞] │         │
│          │  └──────────┘ └──────────┘ └──────────┘         │
│          │  ┌──────────┐ ┌──────────┐ ┌──────────┐         │
│          │  │ 🧬 WGS   │ │ 🧬 WGBS  │ │ 🧬 宏基因 │         │
│          │  │ 全基因组 │ │ 全基因组 │ │ 组分析   │         │
│          │  │ 测序分析 │ │ 甲基化   │ │ 菌群分析 │         │
│          │  │ [基因组] │ │ [表观遗传]│ │ [微生物] │         │
│          │  └──────────┘ └──────────┘ └──────────┘         │
│          └───────────────────────────────────────────────────┘
```

### 5.3 推荐流程大图卡片

```tsx
// 大图卡片 —— 带彩色渐变背景
<div className="
  relative 
  overflow-hidden 
  rounded-2xl 
  p-6 
  min-h-[180px]
  bg-gradient-to-br from-blue-500 via-indigo-500 to-purple-600
  text-white
  cursor-pointer
  group
  transition-all duration-300
  hover:shadow-lg hover:scale-[1.01]
">
  {/* 装饰性背景图案 */}
  <div className="absolute top-0 right-0 w-40 h-40 opacity-20">
    <Dna size={160} className="rotate-12" />
  </div>

  {/* 标签 */}
  <div className="flex gap-2 mb-4">
    <span className="px-2 py-0.5 rounded-full bg-white/20 text-xs font-medium">
      热门
    </span>
    <span className="px-2 py-0.5 rounded-full bg-white/20 text-xs font-medium">
      转录组
    </span>
  </div>

  {/* 内容 */}
  <h3 className="text-xl font-semibold mb-2 relative z-10">RNA-seq 差异表达分析</h3>
  <p className="text-sm text-white/80 mb-4 relative z-10 max-w-md">
    适用于基因表达定量与差异分析，支持 DESeq2、edgeR 等多种算法...
  </p>

  {/* 底部信息 */}
  <div className="flex items-center gap-4 text-xs text-white/70 relative z-10">
    <span className="flex items-center gap-1">
      <Users size={14} /> 1,234 次使用
    </span>
    <span className="flex items-center gap-1">
      <Star size={14} /> 4.9 评分
    </span>
  </div>
</div>
```

### 5.4 分析流程小卡片

```tsx
// 小卡片 —— 标准分析流程卡片
<div className="
  bg-white 
  rounded-xl 
  p-5 
  border border-neutral-border/60
  cursor-pointer
  group
  transition-all duration-300
  hover:shadow-arco-card-hover
  hover:-translate-y-1
  hover:border-arco-primary/30
">
  {/* 图标 */}
  <div className="
    w-12 h-12 rounded-xl 
    bg-blue-50 
    flex items-center justify-center 
    mb-4
    group-hover:bg-blue-100
    transition-colors
  ">
    <FlaskConical size={24} className="text-arco-primary" />
  </div>

  {/* 标题 */}
  <h4 className="text-base font-medium text-neutral-text-1 mb-1">
    ATAC-seq 分析
  </h4>

  {/* 描述 */}
  <p className="text-sm text-neutral-text-3 mb-4 line-clamp-2">
    染色质可及性分析，用于研究染色质开放区域
  </p>

  {/* 标签 */}
  <div className="flex flex-wrap gap-1.5">
    <span className="px-2 py-0.5 rounded-full bg-blue-50 text-blue-600 text-xs">
      表观遗传
    </span>
    <span className="px-2 py-0.5 rounded-full bg-green-50 text-green-600 text-xs">
      自动化
    </span>
  </div>
</div>
```

### 5.5 不同分析流程的图标映射

| 分析流程 | lucide-react 图标 | 图标背景色 |
|---------|-------------------|-----------|
| RNA-seq | FlaskConical | blue-50 / blue-100 |
| ATAC-seq | Dna | purple-50 / purple-100 |
| ChIP-seq | Microscope | indigo-50 / indigo-100 |
| scRNA-seq | Cell (或 Grid3x3) | green-50 / green-100 |
| WGS | Globe | cyan-50 / cyan-100 |
| WGBS | BookOpen | amber-50 / amber-100 |
| 宏基因组 | Bug | orange-50 / orange-100 |
| 代谢组 | Beaker | rose-50 / rose-100 |
| 蛋白质组 | Protein (或 Layers) | teal-50 / teal-100 |

---

## 六、图表组件方案

### 6.1 推荐图表库

火山方舟使用的图表风格（柱状图+折线图组合、双Y轴）推荐使用：

| 库 | 推荐度 | 说明 |
|----|--------|------|
| **ECharts** | ⭐⭐⭐⭐⭐ | 功能最全面；双Y轴天然支持；Arco Design 官方推荐的图表方案（VisActor 团队与 Arco 同源） |
| **VisActor / VChart** | ⭐⭐⭐⭐⭐ | 字节跳动开源可视化方案，与 Arco Design 完全同源，风格完美匹配 |
| **Recharts** | ⭐⭐⭐⭐ | React 原生；API 友好；需额外配置双Y轴 |
| **AntV G2Plot** | ⭐⭐⭐⭐ | 阿里出品；自动适配多种图表类型 |  

**首选推荐：VChart（@visactor/react-vchart）**

原因：
1. 字节跳动 VisActor 团队出品，与火山引擎/Arco Design 同源
2. 风格默认就是字节跳动设计规范
3. 支持 React 组件化调用
4. 双Y轴图表开箱即用

**安装**：
```bash
npm install @visactor/react-vchart
```

### 6.2 调用量趋势图实现

```tsx
import { BarChart, LineChart, Bar, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, ComposedChart } from 'recharts';
// 或使用 VChart

// 示例数据
const data = [
  { date: '06/12', tasks: 5,   samples: 10 },
  { date: '06/14', tasks: 15,  samples: 35 },
  { date: '06/16', tasks: 40,  samples: 180 },
  { date: '06/18', tasks: 25,  samples: 120 },
  { date: '06/20', tasks: 8,   samples: 40 },
  { date: '06/22', tasks: 2,   samples: 15 },
  { date: '06/24', tasks: 0,   samples: 5 },
];

// Recharts 组合图（柱状图+折线图）
<ResponsiveContainer width="100%" height={280}>
  <ComposedChart data={data}>
    <CartesianGrid strokeDasharray="3 3" stroke="#E5E6EB" vertical={false} />
    <XAxis 
      dataKey="date" 
      tick={{ fill: '#86909C', fontSize: 12 }}
      axisLine={{ stroke: '#E5E6EB' }}
      tickLine={false}
    />
    {/* 左Y轴 - 任务数 */}
    <YAxis 
      yAxisId="left"
      tick={{ fill: '#86909C', fontSize: 12 }}
      axisLine={false}
      tickLine={false}
    />
    {/* 右Y轴 - 样本数 */}
    <YAxis 
      yAxisId="right" 
      orientation="right"
      tick={{ fill: '#86909C', fontSize: 12 }}
      axisLine={false}
      tickLine={false}
    />
    <Tooltip 
      contentStyle={{ 
        borderRadius: '8px', 
        border: '1px solid #E5E6EB',
        boxShadow: '0 4px 20px rgba(0,0,0,0.08)'
      }}
    />
    <Legend 
      wrapperStyle={{ paddingTop: '16px' }}
    />
    {/* 柱状图 - 任务数 */}
    <Bar 
      yAxisId="left"
      dataKey="tasks" 
      name="分析任务数" 
      fill="#165DFF" 
      radius={[4, 4, 0, 0]}
      maxBarSize={32}
    />
    {/* 折线图 - 样本数 */}
    <Line 
      yAxisId="right"
      type="monotone" 
      dataKey="samples" 
      name="样本数量" 
      stroke="#FF7D00" 
      strokeWidth={2}
      dot={{ fill: '#FF7D00', strokeWidth: 0, r: 4 }}
      activeDot={{ r: 6, fill: '#FF7D00' }}
    />
  </ComposedChart>
</ResponsiveContainer>
```

---

## 七、Dashboard 页面重构方案（火山方舟风格）

### 7.1 新布局

```tsx
// Dashboard 页面 —— 火山方舟风格
<div className="min-h-screen bg-neutral-bg">
  {/* 左侧边栏 */}
  <Sidebar />

  {/* 主内容区 */}
  <main className="ml-[220px] p-6">
    {/* 顶部 Header */}
    <header className="mb-6">
      <h1 className="text-arco-h1 text-neutral-text-1">控制台</h1>
    </header>

    {/* 公告横幅 */}
    <AnnouncementBanner />

    {/* 快速开始 - 步骤引导 */}
    <section className="mb-6">
      <h2 className="text-arco-h2 text-neutral-text-1 mb-4">快速开始</h2>
      <QuickStartSteps />
    </section>

    {/* 数据概览 - 左右分栏 */}
    <section className="grid grid-cols-2 gap-5 mb-6">
      {/* 左侧 - 账户概览卡片 */}
      <div className="bg-white rounded-xl p-5 shadow-arco-card">
        <div className="flex items-center justify-between mb-4">
          <span className="text-sm text-neutral-text-2">运行中任务</span>
          <Button variant="outline" size="sm">查看全部</Button>
        </div>
        <div className="text-arco-metric text-neutral-text-1">6</div>
        <div className="mt-4 pt-4 border-t border-neutral-border">
          <div className="flex justify-between text-sm">
            <span className="text-neutral-text-3">分析流程</span>
            <span className="text-neutral-text-1 font-medium">12</span>
          </div>
        </div>
      </div>

      {/* 右侧 - 趋势图 */}
      <div className="bg-white rounded-xl p-5 shadow-arco-card">
        <div className="flex items-center justify-between mb-4">
          <span className="text-sm text-neutral-text-2">任务提交趋势</span>
          <DateRangePicker />
        </div>
        <TrendChart />
      </div>
    </section>

    {/* 最近任务 */}
    <section className="bg-white rounded-xl p-5 shadow-arco-card">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-arco-h3 text-neutral-text-1">最近任务</h2>
        <Button variant="ghost" className="text-arco-primary">查看全部 →</Button>
      </div>
      <RecentTasksTable />
    </section>
  </main>
</div>
```

---

## 八、与主文档的整合建议

本文档是对 `OmicHub_美化优化文档.md` 的**风格方向补充**，而非替代。建议将两者结合使用：

1. **色彩体系**：以本文档的火山方舟/Arco Design 色值为准
2. **布局结构**：参考本文档的 Dashboard 布局（公告栏→步骤引导→左右分栏→表格）
3. **分析流程展示**：以本文档第5节的应用实验室卡片网格方案为准
4. **组件动效**：参考主文档的交互动效规范
5. **实施优先级**：保持主文档的 Phase 1→4 节奏

---

## 九、相关资源链接

| 资源 | 链接 |
|------|------|
| **Arco Design React** | https://arco.design/react/docs/start |
| **Semi Design** | https://semi.design |
| **VisActor / VChart** | https://www.visactor.io/vchart |
| **火山方舟控制台** | https://console.volcengine.com/ark |
| **Recharts** | https://recharts.org |
| **ECharts React** | https://echarts.apache.org/handbook/basics/release-note/v5-upgrade-guide/ |

---

> **文档版本**: v1.0
> **编写日期**: 2026-06-25
> **风格参考**: 火山方舟（火山引擎）控制台
> **设计体系**: Arco Design（字节跳动）
> **关联文档**: OmicHub_美化优化文档.md（主文档）
