# OmicHub 平台界面美化优化文档

> 本文档用于指导 AI 编程助手（Kimi Code）对 OmicHub 多组学分析平台进行全面的界面美化与交互优化。
> 
> **项目类型**: React + TypeScript + Tailwind CSS + shadcn/ui
> **目标**: 从现有的基础界面升级为专业级生物信息学平台风格

---

## 一、项目概述

### 1.1 平台简介

**OmicHub** 是华中农业大学园艺林学学院的多组学分析平台，支持：
- 多组学分析（RNA-seq / ATAC-seq / 单细胞）
- Snakemake 流程管理（可复现、可扩展、自动化）
- 私有化部署（数据不出内网，安全可控）

### 1.2 当前界面分析

平台目前包含两个主要页面：

| 页面 | 当前状态 | 主要问题 |
|------|---------|---------|
| **Dashboard 仪表板** | 基础布局，功能可用 | 信息密度低、空白过多、视觉层次弱、缺乏数据可视化 |
| **首页 Landing** | 星空主题背景，有品牌感 | 三个功能卡片样式基础、缺乏动效、与 Dashboard 风格断层 |
| **侧边栏导航** | 纯图标导航 | 图标风格不统一、缺少文字标签、当前页高亮弱 |

### 1.3 设计目标

- **专业性**: 符合科学数据平台的严谨美学
- **科技感**: 融入生命科学/基因组学的视觉元素（DNA、细胞、分子等）
- **一致性**: 首页与 Dashboard 风格统一，支持浅色/深色双主题
- **信息密度**: 在保持清晰的前提下，提升 Dashboard 的信息展示效率
- **交互体验**: 增加微动效、状态可视化、流程图等核心交互

---

## 二、全局设计规范

### 2.1 色彩体系

#### 品牌色（主色调 - 星空蓝紫系）

```
Brand Primary:    #4F6EF7  (主蓝色 - 按钮、链接、强调)
Brand Secondary:  #8B5CF6  (紫色 - 渐变、辅助强调)
Brand Accent:     #06D6A0  (青绿色 - 成功状态、运行中)
Brand Danger:     #EF476F  (粉红色 - 错误、失败)
Brand Warning:    #FFD166  (琥珀色 - 警告)
```

#### 背景色（浅色主题 - Dashboard 默认）

```
Bg Primary:       #F8FAFC   (页面主背景 - 极浅灰蓝)
Bg Secondary:     #FFFFFF   (卡片背景 - 纯白)
Bg Tertiary:      #F1F5F9   (次级背景 - 模块分区)
Bg Hover:         #E2E8F0   (悬停状态)
```

#### 背景色（深色主题 - 可选）

```
Bg Primary Dark:     #0F172A   (深蓝黑 - 页面主背景)
Bg Secondary Dark:   #1E293B   (卡片背景)
Bg Tertiary Dark:    #334155   (次级背景)
Bg Hover Dark:       #475569   (悬停状态)
```

#### 文字色

```
Text Primary:     #0F172A   (标题、重要文字)
Text Secondary:   #64748B   (次级文字、标签）
Text Muted:       #94A3B8   (辅助说明、占位符)
Text Inverse:     #FFFFFF   (深色背景上的文字)
```

#### 边框与分隔

```
Border Light:     #E2E8F0   (浅色边框)
Border Medium:    #CBD5E1   (中等边框)
Glow Primary:     rgba(79, 110, 247, 0.15)   (品牌色光晕)
Glow Accent:      rgba(6, 214, 160, 0.15)    (成功状态光晕)
```

### 2.2 字体规范

```
Font Family:  "Inter", "Noto Sans SC", -apple-system, sans-serif

H1 页面标题:   24px / font-semibold / tracking-tight  / text-primary
H2 模块标题:   18px / font-semibold / tracking-tight  / text-primary
H3 卡片标题:   15px / font-medium   / normal          / text-primary
Body 正文:     14px / font-normal   / normal          / text-primary
Caption 说明:  12px / font-normal   / normal          / text-muted
Metric 数值:   28px / font-bold     / tabular-nums    / text-primary
```

### 2.3 间距系统

```
页面内边距:     px-6 py-6 (24px)
卡片内边距:     p-5 (20px)
卡片间距:       gap-5 (20px)
模块间距:       mb-6 (24px)
元素间距:       gap-3 (12px)
紧凑间距:       gap-2 (8px)
```

### 2.4 圆角与阴影

```
卡片圆角:       rounded-xl  (12px)
按钮圆角:       rounded-lg  (8px)  或 rounded-full (药丸形)
输入框圆角:     rounded-lg  (8px)
徽标圆角:       rounded-full  (100%)

卡片阴影:       shadow-sm + border border-border-light
悬浮阴影:       shadow-lg + ring-2 ring-brand-primary/20
```

### 2.5 图标规范

- **统一使用 lucide-react 图标库**（shadcn/ui 默认）
- 侧边栏图标统一使用 **strokeWidth={1.5}**
- 功能图标使用 **strokeWidth={2}**
- 状态图标尺寸: 16px (sm), 20px (md), 24px (lg)
- 颜色跟随上下文：默认 Text Secondary，激活 Brand Primary，成功 Accent，危险 Danger

---

## 三、组件级设计规范

### 3.1 统计卡片（Dashboard Top Cards）

**当前问题**: 纯文字数字，无视觉层次感

**优化方案 - "Metric Card"**:

```
┌─────────────────────────────────┐
│  [Icon]  标签文字                  │  ← 12px Caption, Text Secondary
│                                  │
│  1,234                           │  ← 28px Metric, Text Primary
│  ━━━━━━━━━━━━━                   │  ← 底部迷你进度条或装饰线
│  ▲ 12.5%  较上周                │  ← 12px Caption, 正/负颜色
└─────────────────────────────────┘
   bg-white, rounded-xl, p-5, shadow-sm, border border-slate-200
```

**具体要求**:
- 每张卡片左上角有一个 **40x40px 的圆角图标容器**，背景色为品牌色的 10% 透明度
- 数值使用 `tabular-nums` 等宽数字，避免跳动
- 底部增加一条 **3px 高的彩色装饰线**（不同卡片不同颜色）
- 鼠标悬浮时：整体上浮 2px (`-translate-y-0.5`)，阴影增强 (`shadow-md`)，装饰线宽度展开动画 (`transition-all duration-300`)
- 卡片颜色分配：
  - 运行状态: 图标 #4F6EF7, 装饰线 #4F6EF7
  - 分析流程: 图标 #8B5CF6, 装饰线 #8B5CF6
  - 运行中任务: 图标 #06D6A0, 装饰线 #06D6A0
  - 数据样本: 图标 #F59E0B, 装饰线 #F59E0B

### 3.2 迷你趋势图（Sparkline）

在统计卡片下方或内部，增加一个高度 40px 的 SVG 迷你趋势图：

```typescript
// 在每张统计卡片中嵌入 Sparkline 组件
// 数据: 最近7天的数值数组
// 样式: 填充渐变 (品牌色 20% 透明度) + 描边 (品牌色)
// 动画: 从左到右绘制动画，duration 1000ms, ease-out
```

**SVG 规范**:
- 高度: 40px
- 宽度: 100% (响应式)
- 曲线类型: 贝塞尔平滑曲线 (非折线)
- 填充: `linearGradient` 从品牌色 20% 到 0%
- 描边: 2px，品牌色
- 无坐标轴、无标签，纯视觉装饰

### 3.3 快速开始卡片（Quick Start Cards）

**当前问题**: 三个按钮排成一行，样式普通

**优化方案 - "Action Card"**:

```
┌─────────────────────────────────┐
│  [大号图标]                       │  ← 48px 图标容器
│  提交分析任务                      │  ← 15px H3
│  上传样本并启动分析流程            │  ← 13px Body, Text Secondary
│  → 开始使用                       │  ← 14px 文字链接，Brand Primary
└─────────────────────────────────┘
```

**具体要求**:
- 三张卡片使用 **等宽网格布局** (`grid grid-cols-3 gap-5`)
- 每张卡片高度一致，内部垂直居中排列
- 图标容器: 56x56px, rounded-2xl, 背景色为对应品牌色的 10%
- 悬浮效果: `translateY(-2px)`, `shadow-lg`, 图标容器背景色加深到 20%
- 第一张卡片（提交分析任务）使用 **主按钮样式**（实心背景），其他使用 **次按钮样式**（边框），形成视觉层次

### 3.4 任务状态标签（Status Badge）

为最近任务列表设计统一的状态标签系统：

| 状态 | 背景色 | 文字色 | 图标 | 动画 |
|------|--------|--------|------|------|
| 运行中 | #06D6A0/15 | #059669 | Loader2 (旋转) | 图标无限旋转 1s linear |
| 排队中 | #F59E0B/15 | #D97706 | Clock | 图标左右微摆 2s ease-in-out |
| 已完成 | #4F6EF7/15 | #4F6EF7 | CheckCircle2 | 无 |
| 失败 | #EF476F/15 | #DC2626 | XCircle | 无 |
| 待审核 | #8B5CF6/15 | #7C3AED | AlertCircle | 无 |

**样式规范**:
```
inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium
```

### 3.5 最近任务表格（Recent Tasks Table）

**当前问题**: 空状态只有一个烧瓶图标，有数据时展示方式未知

**优化方案**:

**空状态（Empty State）**:
```
┌─────────────────────────────────────────────────┐
│                                                  │
│        [大号烧瓶图标 + 微弱动画]                  │  ← 64px, 颜色 #CBD5E1
│                                                  │
│        暂无运行中的任务                           │  ← 16px, Text Primary
│        点击上方"提交分析任务"开始您的第一次分析    │  ← 14px, Text Secondary
│                                                  │
│        [提交分析任务] 按钮                        │  ← Primary Button
│                                                  │
└─────────────────────────────────────────────────┘
```

**有数据状态**:
```
表头: 任务名称 | 分析流程 | 提交时间 | 状态 | 进度 | 操作
行样式: hover:bg-slate-50, transition-colors

进度列: 使用 Progress 组件 (shadcn/ui 内置)
  - 高度: 6px
  - 背景: #E2E8F0
  - 填充: 渐变色 (Brand Primary → Brand Secondary)
  - 动画: 进度变化时宽度过渡 500ms ease-out

操作列: 三个图标按钮 (查看日志、重新运行、删除)
  - 尺寸: 32x32px
  - 样式: ghost variant, rounded-lg
  - 悬浮: bg-slate-100 + 图标颜色变深
```

### 3.6 分析流程可视化组件（Pipeline Visualizer）【核心功能】

**这是平台的差异化功能，优先级最高**

**设计目标**: 将 Snakemake 分析流程以可视化的节点流图展示

**组件结构**:
```
┌─────────────────────────────────────────────────────────┐
│  分析流程名称                    [收起/展开] [查看详情]   │
├─────────────────────────────────────────────────────────┤
│                                                          │
│   ┌────────┐      ┌────────┐      ┌────────┐            │
│   │ QC质控  │─────→│ 序列比对 │─────→│ 表达定量 │───→ ...│
│   │  ✅    │      │  🔄    │      │  ⏳    │            │
│   │2m 30s  │      │ 运行中  │      │ 等待   │            │
│   └────────┘      └────────┘      └────────┘            │
│      2 GB           8 GB            4 GB                 │
│                                                          │
│   图例: ✅ 已完成  🔄 运行中  ⏳ 等待  ❌ 失败           │
└─────────────────────────────────────────────────────────┘
```

**节点设计**:
```css
/* 节点卡片 */
.pipeline-node {
  width: 140px;
  padding: 16px;
  border-radius: 12px;
  background: white;
  border: 2px solid;
  text-align: center;
  transition: all 300ms ease;
}

/* 状态变体 */
.node-completed { border-color: #06D6A0; box-shadow: 0 0 12px rgba(6, 214, 160, 0.2); }
.node-running   { border-color: #4F6EF7; box-shadow: 0 0 16px rgba(79, 110, 247, 0.3); }
.node-pending   { border-color: #CBD5E1; opacity: 0.7; }
.node-failed    { border-color: #EF476F; box-shadow: 0 0 12px rgba(239, 71, 111, 0.2); }
```

**连接线设计**:
- 使用 SVG 绘制贝塞尔曲线连接节点
- 已完成路径: 渐变色描边 (#06D6A0 → #4F6EF7)，2px，带流动动画 (stroke-dasharray 虚线流动)
- 待执行路径: #CBD5E1，1px，虚线

**悬浮交互**:
- 悬浮节点时：节点放大 1.05 倍，显示工具提示（Tooltip）包含详细信息（运行时间、内存使用、输入/输出文件大小）
- 点击节点：展开下方抽屉（Drawer）显示完整日志

---

## 四、页面级优化方案

### 4.1 Dashboard 仪表板页（全面重设计）

**新布局结构**:

```
┌──────────────────────────────────────────────────────────────┐
│  Header Bar (现有 - 保持)                                     │
├──────────┬───────────────────────────────────────────────────┤
│          │  页面标题 + 实时时钟/系统状态                      │
│          │  "Dashboard" + "系统运行正常 ● 3个节点在线"        │
│          ├───────────────────────────────────────────────────┤
│          │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐│
│          │  │ 运行状态  │ │ 分析流程  │ │ 运行任务  │ │ 数据样本││  ← Metric Cards
│          │  │          │ │          │ │          │ │        ││
│          │  │ Sparkline│ │ Sparkline│ │ Sparkline│ │Sparkl. ││
│          │  └──────────┘ └──────────┘ └──────────┘ └────────┘│
│          ├───────────────────────────────────────────────────┤
│          │  快速开始                                        │
│          │  ┌──────────────┐┌──────────────┐┌──────────────┐│
│          │  │  🚀 提交任务  ││  📤 上传数据  ││  📋 浏览流程  ││  ← Action Cards
│          │  └──────────────┘└──────────────┘└──────────────┘│
│          ├───────────────────────────────────────────────────┤
│          │  进行中的流程 (Pipeline Visualizer)               │
│          │  ┌──────────────────────────────────────────┐     │
│          │  │  [流程可视化图 或 空状态]                  │     │
│          │  └──────────────────────────────────────────┘     │
│          ├───────────────────────────────────────────────────┤
│ Sidebar  │  最近任务                                          │
│          │  ┌──────────────────────────────────────────┐     │
│          │  │  [任务表格 - 最多显示5条 + 查看全部链接]   │     │
│          │  └──────────────────────────────────────────┘     │
│          ├───────────────────────────────────────────────────┤
│          │  系统资源监控 (新增)                               │
│          │  ┌──────────────┐ ┌──────────────┐               │
│          │  │ CPU 使用率    │ │ 内存使用      │               │
│          │  │ [环形图]      │ │ [环形图]      │               │
│          │  └──────────────┘ └──────────────┘               │
│          └───────────────────────────────────────────────────┘
```

**模块优先级（从上到下）**:
1. **统计概览行** (必做) - 4 张 Metric Cards
2. **快速开始** (必做) - 3 张 Action Cards
3. **进行中的流程** (高优) - Pipeline Visualizer
4. **最近任务** (必做) - 表格或卡片列表
5. **系统资源监控** (中优) - CPU/内存/存储环形图

### 4.2 首页 Landing Page（优化升级）

**保持现有星空背景主题，进行精细化调整**:

#### Hero 区域
- **标题**: "We are made of star-stuff" - 字体加大到 40px，增加微弱发光效果 (`text-shadow: 0 0 40px rgba(79, 110, 247, 0.3)`)
- **副标题**: "我们由星尘构成" - 保持现有风格
- **星球动画**: 增加缓慢的自转动画或脉冲光晕动画 (CSS animation, 8s infinite)

#### 哲思文字卡片
- 背景: `rgba(15, 23, 42, 0.7)` + `backdrop-blur-lg`
- 边框: 1px solid `rgba(255, 255, 255, 0.1)`
- 左侧增加一条 3px 宽的渐变装饰线 (`linear-gradient(to bottom, #4F6EF7, #8B5CF6)`)

#### 功能卡片区域（重点优化）

```
┌─────────────────────────────────────────────────────────────┐
│                                                              │
│  ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐│
│  │  🧬              │ │  ⚡              │ │  🔒              ││
│  │  多组学分析       │ │  Snakemake 流程   │ │  私有化部署       ││
│  │                  │ │                  │ │                  ││
│  │  RNA-seq /       │ │  可复现、可扩展、  │ │  数据不出内网     ││
│  │  ATAC-seq /      │ │  自动化           │ │  安全可控        ││
│  │  单细胞          │ │                  │ │                  ││
│  │                  │ │  [了解更多 →]     │ │  [了解更多 →]     ││
│  └──────────────────┘ └──────────────────┘ └──────────────────┘│
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

**卡片样式规范**:
```css
.feature-card {
  background: rgba(30, 41, 59, 0.6);
  backdrop-filter: blur(16px);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 20px;
  padding: 32px;
  transition: all 400ms cubic-bezier(0.4, 0, 0.2, 1);
}

.feature-card:hover {
  transform: translateY(-8px);
  border-color: rgba(79, 110, 247, 0.3);
  box-shadow: 
    0 20px 40px rgba(0, 0, 0, 0.3),
    0 0 60px rgba(79, 110, 247, 0.1);
}
```

**图标设计**:
- 使用 **渐变背景图标容器**: `linear-gradient(135deg, #4F6EF7, #8B5CF6)`
- 尺寸: 56x56px, rounded-2xl
- 图标颜色: 白色
- 悬浮时图标容器增加脉冲光环动画

**底部 Footer**:
- "OmicHub · 华中农业大学园艺林学学院 · 多组学分析平台"
- 增加一个微妙的顶部边框分隔线 (`border-top: 1px solid rgba(255,255,255,0.1)`)

### 4.3 侧边栏导航（Sidebar）优化

**当前问题**: 纯图标，无文字，当前高亮弱

**优化方案**:

```
展开状态 (默认宽 200px):
┌──────────────┐
│ 🧬 OmicHub   │  ← Logo + 文字
├──────────────┤
│ 🏠 首页      │  ← 图标 + 文字标签
│ 📊 仪表板    │  ← 当前页: 蓝色背景高亮
│ 📋 分析流程  │
│ 📤 数据管理  │
│ 🔔 任务中心  │
├──────────────┤
│ ⚙️ 系统设置  │
│ 👤 个人中心  │
│ ❓ 帮助文档  │
└──────────────┘

折叠状态 (宽 64px):
┌──────┐
│  🧬   │
├──────┤
│  🏠   │  ← 仅图标，悬停显示 Tooltip
│  📊   │
│  📋   │
└──────┘
```

**样式规范**:
- 背景: 与主页面背景色一致（浅色模式 `#F8FAFC`，深色模式 `#0F172A`）
- 右边框: `border-right: 1px solid #E2E8F0`
- 导航项高度: 40px
- 内边距: `px-3 py-2`
- 圆角: `rounded-lg`
- **当前页高亮**: 
  - 背景: `bg-brand-primary/10`
  - 文字: `text-brand-primary`
  - 左侧 3px 蓝色指示条 (`border-l-3 border-brand-primary`)
- **悬浮效果**: `bg-slate-100` (浅色) / `bg-slate-800` (深色)
- **展开/折叠切换**: 底部有一个箭头按钮，带动画旋转 (`rotate-180`)

**图标映射**:
| 导航项 | 图标 (lucide-react) |
|--------|-------------------|
| 首页 | Home |
| 仪表板 | LayoutDashboard |
| 分析流程 | GitBranch |
| 数据管理 | Database |
| 任务中心 | ClipboardList |
| 系统设置 | Settings |
| 个人中心 | User |
| 帮助文档 | HelpCircle |

---

## 五、交互动效规范

### 5.1 全局过渡

```css
/* 所有交互元素统一过渡 */
.interactive {
  transition: all 200ms cubic-bezier(0.4, 0, 0.2, 1);
}
```

### 5.2 页面加载动画

- Dashboard: 统计卡片依次淡入上飘 (`stagger delay: 100ms`)
- 首页: 星空背景渐显，标题打字机效果或淡入

### 5.3 悬浮动效

| 元素 | 悬浮效果 | 时长 |
|------|---------|------|
| 卡片 | translateY(-2px) + shadow 增强 | 300ms |
| 按钮 | 亮度提升 / 背景色加深 | 150ms |
| 表格行 | 背景色变化 | 150ms |
| 图标按钮 | 缩放 1.05 + 背景出现 | 200ms |
| 导航项 | 背景色变化 + 文字颜色变化 | 150ms |

### 5.4 状态变化动画

- **任务状态变更**: 标签颜色渐变过渡 (500ms)
- **进度条更新**: 宽度变化动画 (500ms ease-out)
- **Pipeline 节点完成**: 边框颜色从蓝变绿，伴随微弱闪烁效果
- **数据加载**: Skeleton 骨架屏动画 (shadcn/ui 内置)

### 5.5 特殊效果

- **星空背景粒子**: 在首页背景增加少量微弱闪烁的白点（纯 CSS 动画，每个点随机延迟，模拟星星闪烁）
- **运行中状态脉冲**: 运行中的任务/节点有一个微弱的脉冲光环 (`animate-pulse` 或自定义 ring 动画)

---

## 六、新增推荐组件（从 shadcn/ui 引入）

以下 shadcn/ui 组件建议安装使用：

```bash
npx shadcn add tooltip
npx shadcn add progress
npx shadcn add badge
npx shadcn add skeleton
npx shadcn add drawer
npx shadcn add separator
npx shadcn add switch        # 用于深色/浅色主题切换
npx shadcn add dropdown-menu # 用于用户菜单
```

---

## 七、技术实现要点

### 7.1 主题切换实现

```typescript
// 使用 React Context + localStorage
// 监听系统偏好: window.matchMedia('(prefers-color-scheme: dark)')
// 在 html 元素上切换 class: 'dark' / 'light'
// Tailwind: darkMode: 'class' in tailwind.config.js
```

### 7.2 数据可视化库选择

| 图表类型 | 推荐库 |
|---------|--------|
| 迷你趋势图 (Sparkline) | 手写 SVG 或 ECharts |
| 环形图 (资源监控) | ECharts 或 Chart.js |
| 流程可视化图 | ReactFlow (@xyflow/react) |
| 科学结果图表 (火山图/热图) | Plotly.js |

**安装**:
```bash
npm install @xyflow/react echarts
```

### 7.3 响应式断点

```
Mobile:  < 768px   (单列布局，侧边栏折叠为抽屉)
Tablet:  768px+   (双列布局)
Desktop: 1024px+  (完整布局)
Wide:    1440px+  (最大内容宽度 1440px，居中)
```

---

## 八、参考资源

### 8.1 参考平台截图（已收集）

以下平台截图保存在项目 `/reference_images/` 目录下，可供 Kimi Code 参考：

| 文件名 | 说明 |
|--------|------|
| `ref_genome_dashboard.jpg` | 基因组数据 Dashboard - 深色主题、数据密集展示风格 |
| `ref_scientific_dashboard.jpg` | 科学数据 Dashboard - 卡片式布局参考 |
| `ref_rna_seq_platform.png` | RNA-seq 分析平台 - 左侧面板+右侧图表布局 |
| `ref_qgen_dashboard.png` | Qgen 基因分析平台 - 深色主题、分子可视化 |
| `ref_latch_admin.png` | Latch Bio Admin - 现代 Dashboard 表格布局 |

### 8.2 设计参考链接

- **Galaxy Project**: https://usegalaxy.org - 生物信息学工作流平台鼻祖
- **GenePattern**: https://cloud.genepattern.org - Broad Institute 分析平台
- **Latch Bio**: https://latch.bio - 现代生物信息云平台
- **shadcn/ui**: https://ui.shadcn.com - UI 组件库文档
- **ReactFlow**: https://reactflow.dev - 流程图可视化库

---

## 九、实施优先级

### Phase 1: 基础美化（立即实施）
- [x] 全局色彩/字体/间距规范落地
- [x] 统计卡片 Metric Card 组件
- [x] 快速开始 Action Card 组件
- [x] 侧边栏导航优化（图标+文字+高亮）
- [x] 任务状态标签 Badge 组件
- [x] 最近任务表格样式优化
- [x] 空状态 Empty State 优化

### Phase 2: 数据可视化（第2轮）
- [x] 统计卡片迷你趋势图 Sparkline
- [x] 系统资源监控环形图
- [x] 最近任务表格进度条

### Phase 3: 核心功能（第3轮）
- [x] 分析流程可视化 Pipeline Visualizer（ReactFlow）
- [x] 流程节点悬浮详情抽屉

### Phase 4: 体验升级（第4轮）
- [x] 深色/浅色主题切换
- [x] 首页星空背景动效优化
- [x] 功能卡片悬浮动效
- [x] 页面加载动画

---

## 十、附录：Tailwind 配置扩展

```javascript
// tailwind.config.js 需要添加的扩展
module.exports = {
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        brand: {
          primary: '#4F6EF7',
          secondary: '#8B5CF6',
          accent: '#06D6A0',
          danger: '#EF476F',
          warning: '#FFD166',
        },
      },
      fontFamily: {
        sans: ['Inter', 'Noto Sans SC', 'system-ui', 'sans-serif'],
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'float': 'float 6s ease-in-out infinite',
        'glow': 'glow 2s ease-in-out infinite alternate',
      },
      keyframes: {
        float: {
          '0%, 100%': { transform: 'translateY(0)' },
          '50%': { transform: 'translateY(-10px)' },
        },
        glow: {
          '0%': { boxShadow: '0 0 20px rgba(79, 110, 247, 0.2)' },
          '100%': { boxShadow: '0 0 40px rgba(79, 110, 247, 0.4)' },
        },
      },
    },
  },
}
```

---

> **文档版本**: v1.0
> **编写日期**: 2026-06-25
> **目标读者**: Kimi Code / AI 编程助手
> **建议**: 按 Phase 1 → Phase 2 → Phase 3 → Phase 4 的顺序逐步实施，每轮完成后进行效果确认。
