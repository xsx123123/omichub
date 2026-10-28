# OmicHub 界面美化文档 —— 火山方舟风格

> **设计参考**: 火山引擎 · 火山方舟控制台  
> **设计体系**: Arco Design（字节跳动企业级设计系统）  
> **技术栈**: React + TypeScript + Tailwind CSS + shadcn/ui + Recharts  
> **本文档用途**: 提交给 AI 编程助手（Kimi Code）执行美化开发

---

## 一、风格概述

### 1.1 火山方舟风格特征

火山引擎控制台（含火山方舟）60% 以上产品基于 **Arco Design** 搭建，核心视觉特征：

| 特征 | 说明 |
|------|------|
| **极简留白** | 大量留白，信息呼吸感强，不拥挤 |
| **浅色背景** | 页面背景 `#F2F3F8`（极浅蓝灰），卡片纯白 |
| **圆角卡片** | 12px 圆角，极淡阴影，边框极细 |
| **蓝色主题** | 主色 `#165DFF`（亮蓝），清新专业 |
| **药丸标签** | Tag 全圆角，浅色底+深色字 |
| **复合导航** | 顶部横向主导航 + 左侧功能边栏 |
| **底部用户区** | 左下角固定放置用户信息 |

### 1.2 与当前 OmicHub 的差异对照

| 元素 | 当前 OmicHub | 火山方舟风格 |
|------|-------------|-------------|
| 页面背景 | 纯白 `#FFFFFF` | 浅蓝灰 `#F2F3F8` |
| 卡片样式 | 简单边框 | 白底+淡阴影+12px圆角 |
| 导航方式 | 仅左侧图标栏 | 顶部横向 + 左侧功能栏 |
| 侧边栏 | 64px 纯图标 | 220px 图标+文字+高亮 |
| 用户信息 | 右上角 | **左下角** |
| 按钮风格 | 绿色主调 | 蓝色主调 `#165DFF` |
| 数据图表 | 无 | 柱状+折线组合图 |

---

## 二、全局设计规范

### 2.1 色彩体系（Arco Design 标准色）

#### 品牌色
```
Arco Primary:     #165DFF   (主按钮、链接、强调)
Arco Primary Light: #E8F3FF (激活背景、浅色点缀)
Arco Success:     #00B42A   (成功、完成、运行中)
Arco Success Light: #E8FFEA
Arco Warning:     #FF7D00   (警告、注意)
Arco Warning Light: #FFF7E8
Arco Danger:      #F53F3F   (错误、失败、删除)
Arco Danger Light:  #FFECE8
```

#### 中性色
```
页面背景:         #F2F3F8   (Neutral-bg)
卡片背景:         #FFFFFF   (Neutral-card)
边框色:           #E5E6EB   (Neutral-border)
主要文字:         #1D2129   (Neutral-text-1)
次要文字:         #4E5969   (Neutral-text-2)
辅助文字:         #86909C   (Neutral-text-3)
占位符文字:       #C9CDD4   (Neutral-text-4)
悬浮背景:         #F2F3F8   (Neutral-hover)
分割线:           #E5E6EB
```

#### 导航专用色
```
侧边栏背景:       #FFFFFF
侧边栏边框:       #E5E6EB
导航项默认文字:    #4E5969
导航项悬浮背景:    #F2F3F8
导航项激活背景:    #E8F3FF
导航项激活文字:    #165DFF
顶部导航背景:      #FFFFFF
顶部导航边框:      #E5E6EB
```

### 2.2 字体规范

```
Font Family: "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", 
             Roboto, "Noto Sans SC", "PingFang SC", "Microsoft YaHei", sans-serif

页面标题:     24px / font-weight: 600 / line-height: 32px  / color: #1D2129
模块标题:     18px / font-weight: 600 / line-height: 26px  / color: #1D2129
卡片标题:     16px / font-weight: 500 / line-height: 24px  / color: #1D2129
正文:         14px / font-weight: 400 / line-height: 22px  / color: #1D2129
辅助文字:     13px / font-weight: 400 / line-height: 20px  / color: #86909C
标签/徽章:    12px / font-weight: 500 / line-height: 18px
大数字:       32px / font-weight: 600 / line-height: 40px  / color: #1D2129 / tabular-nums
```

### 2.3 间距系统

```
页面内边距:        24px (p-6)
卡片内边距:        20px (p-5)
卡片间距:          16-20px (gap-4 / gap-5)
模块间距:          24px (mb-6)
元素间距:          12px (gap-3)
导航项高度:        40px
导航项内边距:      px-3 py-2
```

### 2.4 圆角与阴影

```
卡片圆角:          12px  (rounded-xl)
按钮圆角:          6px   (rounded-md)
输入框圆角:        6px   (rounded-md)
标签圆角:          9999px (rounded-full)
头像圆角:          50%   (rounded-full)

卡片阴影:          0 4px 16px rgba(29, 33, 41, 0.04)
卡片悬浮阴影:       0 8px 24px rgba(29, 33, 41, 0.08)
下拉菜单阴影:       0 4px 20px rgba(0, 0, 0, 0.08)
```

### 2.5 Tailwind 配置扩展

```javascript
// tailwind.config.js —— theme.extend 中添加
{
  colors: {
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
    neutral: {
      bg: "#F2F3F8",
      card: "#FFFFFF",
      border: "#E5E6EB",
      "text-1": "#1D2129",
      "text-2": "#4E5969",
      "text-3": "#86909C",
      "text-4": "#C9CDD4",
      hover: "#F2F3F8",
    },
  },
  borderRadius: {
    "arco-card": "12px",
    "arco-btn": "6px",
    "arco-tag": "9999px",
  },
  boxShadow: {
    "arco-card": "0 4px 16px rgba(29, 33, 41, 0.04)",
    "arco-card-hover": "0 8px 24px rgba(29, 33, 41, 0.08)",
    "arco-dropdown": "0 4px 20px rgba(0, 0, 0, 0.08)",
  },
  fontSize: {
    "arco-h1": ["24px", { lineHeight: "32px", fontWeight: "600" }],
    "arco-h2": ["18px", { lineHeight: "26px", fontWeight: "600" }],
    "arco-h3": ["16px", { lineHeight: "24px", fontWeight: "500" }],
    "arco-body": ["14px", { lineHeight: "22px", fontWeight: "400" }],
    "arco-caption": ["12px", { lineHeight: "20px", fontWeight: "400" }],
    "arco-metric": ["32px", { lineHeight: "40px", fontWeight: "600" }],
  },
}
```

---

## 三、导航体系设计（核心）

火山方舟采用 **顶部横向导航 + 左侧功能边栏** 的复合导航模式。OmicHub 按此模式设计。

### 3.1 整体导航架构

```
┌─────────────────────────────────────────────────────────────────┐
│  [≡] [🧬] OmicHub  │  控制台   分析流程中心   实验室知识库   文档   │  ← TopNav
├──────────┬──────────────────────────────────────────────────────┤
│          │                                                      │
│  首页    │                                                      │
│  ▲ 激活   │                   主内容区域                         │
│          │                                                      │
│  仪表板   │                                                      │
│          │                                                      │
│  分析中心 │                                                      │
│    ├ ... │                                                      │
│    ├ ... │                                                      │
│          │                                                      │
│  数据管理 │                                                      │
│          │                                                      │
│  任务中心 │                                                      │
│          │                                                      │
│ ─────────│                                                      │
│          │                                                      │
│  用量统计 │                                                      │
│  系统设置 →                                                     │
│ ─────────│                                                      │
│          │                                                      │
│  [👤]    │                                                      │
│  username│                                                      │
│  管理员   │                                                      │
│          │                                                      │
└──────────┴──────────────────────────────────────────────────────┘
   ↑Sidebar (220px)        ↑Main Content (剩余宽度)
```

### 3.2 顶部导航栏（TopNav）

#### 布局结构

```
┌────────────────────────────────────────────────────────────────────┐
│ [≡] [Logo] OmicHub  │  控制台   分析流程中心   实验室知识库   文档  │
│  (左)               │         (中 - 主导航)                    (右) │
└────────────────────────────────────────────────────────────────────┘
高度: 56px
背景: #FFFFFF
下边框: 1px solid #E5E6EB
```

#### 左侧区域

```
[汉堡菜单按钮] [Logo图标] │ [OmicHub 文字]
```

- **汉堡菜单按钮**: 32x32px, 灰色图标 `Menu` (lucide), 悬浮背景 `#F2F3F8`
- **Logo 图标**: OmicHub 的 DNA 双螺旋图标，36x36px
- **分隔线**: 1px 竖线 `#E5E6EB`，高 20px
- **产品名称**: "OmicHub"，16px / font-weight: 600 / color: #1D2129

#### 中间主导航

| 导航项 | 说明 | 链接目标 |
|--------|------|---------|
| **控制台** | Dashboard 首页 | `/dashboard` |
| **分析流程中心** | 全部分析流程列表 | `/analysis` |
| **实验室知识库** | 内部知识库（预留） | `/knowledge` |
| **文档** | 使用文档/API 文档 | `/docs` |

**样式规范**:
```
高度: 56px
内边距: px-4
文字: 14px / font-weight: 400 / color: #4E5969
激活态: color: #165DFF / font-weight: 500 / 底部 2px 蓝色指示线
悬浮态: color: #1D2129 / background: transparent
过渡: transition-colors duration-200
指示线: height 2px, background #165DFF, bottom 0, 宽度与文字等宽
```

**当前激活项底部指示线实现**:
```tsx
// 激活的导航项
<a className="
  relative 
  h-full 
  flex items-center 
  px-4 
  text-sm 
  font-medium 
  text-arco-primary
  transition-colors
">
  控制台
  {/* 底部蓝色指示线 */}
  <span className="
    absolute 
    bottom-0 
    left-4 
    right-4 
    h-0.5 
    bg-arco-primary 
    rounded-full
  " />
</a>
```

#### 右侧区域（可选）

```
[搜索框] [通知铃铛] [帮助?] [用户头像]
```

### 3.3 左侧边栏（Sidebar）

#### 整体规格

```
宽度: 220px
高度: 100vh (减去 TopNav 56px)
背景: #FFFFFF
右边框: 1px solid #E5E6EB
内边距: py-3 px-3
```

#### 导航分组结构

**第一组 —— 核心功能**:

| 导航项 | 图标 (lucide) | 链接 | 说明 |
|--------|--------------|------|------|
| 首页 | `Home` | `/home` | 星空主题 Landing Page |
| 仪表板 | `LayoutDashboard` | `/dashboard` | 数据概览 Dashboard |
| 分析中心 | `GitBranch` | `/analysis` | 展开子菜单 |
| ├ RNA-seq 分析 | `FlaskConical` | `/analysis/rna-seq` | 子项 |
| ├ ATAC-seq 分析 | `Dna` | `/analysis/atac-seq` | 子项 |
| ├ ChIP-seq 分析 | `Microscope` | `/analysis/chip-seq` | 子项 |
| ├ 单细胞分析 | `Grid3x3` | `/analysis/scrna` | 子项 |
| ├ 全基因组测序 | `Globe` | `/analysis/wgs` | 子项 |
| └ 宏基因组分析 | `Bug` | `/analysis/metagenome` | 子项 |
| 数据管理 | `Database` | `/data` | 样本/数据文件管理 |
| 任务中心 | `ClipboardList` | `/tasks` | 任务列表与状态 |

**第二组 —— 系统与资源**（与第一组用分割线分隔）:

| 导航项 | 图标 (lucide) | 链接 |
|--------|--------------|------|
| 用量统计 | `BarChart3` | `/usage` |
| 系统设置 | `Settings` | `/settings` |
| 关于 OmicHub | `Info` | `/about` |

**第三组 —— 底部固定用户信息区**:

#### 导航项样式规范

**默认态**:
```tsx
<a className="
  flex items-center gap-3 
  px-3 py-2 
  rounded-lg 
  text-sm 
  text-neutral-text-2   // #4E5969
  hover:bg-neutral-hover // #F2F3F8
  transition-colors 
  cursor-pointer
">
  <Icon size={18} strokeWidth={1.5} />
  <span>导航文字</span>
</a>
```

**激活态（当前页面）**:
```tsx
<a className="
  flex items-center gap-3 
  px-3 py-2 
  rounded-lg 
  text-sm 
  font-medium
  bg-arco-primary-light   // #E8F3FF
  text-arco-primary       // #165DFF
  transition-colors 
  cursor-pointer
">
  <Icon size={18} strokeWidth={1.5} />
  <span>导航文字</span>
</a>
```

**可展开项（如"分析中心"）**:
```tsx
// 带展开箭头的导航项
<div className="
  flex items-center justify-between 
  px-3 py-2 
  rounded-lg 
  text-sm 
  text-neutral-text-2
  hover:bg-neutral-hover
  cursor-pointer
">
  <div className="flex items-center gap-3">
    <GitBranch size={18} strokeWidth={1.5} />
    <span>分析中心</span>
  </div>
  <ChevronRight 
    size={16} 
    className={cn(
      "text-neutral-text-3 transition-transform",
      expanded && "rotate-90"
    )} 
  />
</div>
```

#### 子菜单展开样式

```
分析中心                    >
├─ RNA-seq 分析            →  (缩进 32px, 字体 13px, 高度 36px)
├─ ATAC-seq 分析           →
├─ ChIP-seq 分析           →
├─ 单细胞分析               →
├─ 全基因组测序             →
└─ 宏基因组分析             →
```

```tsx
// 子菜单项
<div className="ml-6 pl-4 border-l border-neutral-border">
  <a className="
    flex items-center 
    py-2 
    text-[13px] 
    text-neutral-text-2
    hover:text-neutral-text-1
    transition-colors
  ">
    <FlaskConical size={16} strokeWidth={1.5} className="mr-2" />
    RNA-seq 分析
  </a>
</div>
```

#### 用户信息区（左下角固定）

```
┌──────────────────────┐
│  [头像]  username     │
│          管理员       │
│          ▼           │
└──────────────────────┘
点击展开:
┌──────────────────────┐
│  [头像]  username     │
│          管理员       │
│ ───────────────────  │
│  👤 个人中心          │
│  ⚙️ 账号设置          │
│  🌙 深色模式          │
│ ───────────────────  │
│  🚪 退出登录          │
└──────────────────────┘
```

**实现代码**:
```tsx
// 底部用户信息区 —— 固定在 Sidebar 底部
<div className="mt-auto pt-3 border-t border-neutral-border">
  <DropdownMenu>
    <DropdownMenuTrigger asChild>
      <button className="
        w-full 
        flex items-center gap-3 
        px-3 py-2.5 
        rounded-lg 
        hover:bg-neutral-hover
        transition-colors
        text-left
      ">
        {/* 用户头像 */}
        <Avatar className="w-8 h-8">
          <AvatarImage src={user.avatar} />
          <AvatarFallback className="bg-arco-primary-light text-arco-primary text-sm font-medium">
            {user.name?.charAt(0)?.toUpperCase()}
          </AvatarFallback>
        </Avatar>

        {/* 用户名和角色 */}
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-neutral-text-1 truncate">
            {user.name}
          </p>
          <p className="text-xs text-neutral-text-3">
            {user.role}
          </p>
        </div>

        {/* 下拉箭头 */}
        <ChevronUp size={14} className="text-neutral-text-3" />
      </button>
    </DropdownMenuTrigger>

    <DropdownMenuContent 
      align="start" 
      side="right"
      className="w-56"
    >
      <DropdownMenuLabel>
        <div className="flex items-center gap-3">
          <Avatar className="w-10 h-10">
            <AvatarFallback>{user.name?.charAt(0)}</AvatarFallback>
          </Avatar>
          <div>
            <p className="font-medium">{user.name}</p>
            <p className="text-xs text-muted-foreground">{user.email}</p>
          </div>
        </div>
      </DropdownMenuLabel>
      <DropdownMenuSeparator />
      <DropdownMenuItem>
        <User size={16} className="mr-2" /> 个人中心
      </DropdownMenuItem>
      <DropdownMenuItem>
        <Settings size={16} className="mr-2" /> 账号设置
      </DropdownMenuItem>
      <DropdownMenuItem>
        <Moon size={16} className="mr-2" /> 深色模式
      </DropdownMenuItem>
      <DropdownMenuSeparator />
      <DropdownMenuItem className="text-arco-danger">
        <LogOut size={16} className="mr-2" /> 退出登录
      </DropdownMenuItem>
    </DropdownMenuContent>
  </DropdownMenu>
</div>
```

**样式细节**:
- 头像: 32x32px, 圆形
- 默认头像: 使用用户名首字母，背景 `#E8F3FF`，文字 `#165DFF`
- 用户名: 14px / font-weight: 500 / color: #1D2129
- 角色: 12px / color: #86909C
- 展开菜单: 距左侧边栏右侧 8px，阴影 `0 4px 20px rgba(0,0,0,0.08)`

#### 侧边栏分割线

```tsx
// 组间分割线
<div className="my-3 mx-3 h-px bg-neutral-border" />
```

### 3.4 侧边栏折叠态

```
折叠宽度: 64px
只显示图标，隐藏文字
导航项: w-10 h-10, 居中图标, rounded-lg
悬浮显示 Tooltip（文字标签）
底部用户区只显示头像
```

```tsx
// 折叠态导航项
<a className="
  w-10 h-10 
  flex items-center justify-center 
  rounded-lg 
  text-neutral-text-2
  hover:bg-neutral-hover
  transition-colors
" title="首页">
  <Home size={20} strokeWidth={1.5} />
</a>

// 激活态
<a className="
  w-10 h-10 
  flex items-center justify-center 
  rounded-lg 
  bg-arco-primary-light
  text-arco-primary
  transition-colors
" title="首页">
  <Home size={20} strokeWidth={1.5} />
</a>
```

### 3.5 响应式适配

```
Desktop (≥1024px):  完整侧边栏 220px + TopNav
Tablet (768-1023px): 侧边栏折叠 64px + TopNav
Mobile (<768px):      侧边栏隐藏，汉堡菜单打开时全屏抽屉
```

---

## 四、Dashboard 控制台页面设计

### 4.1 整体布局

```
TopNav (56px)
├──────────────────────────────────────────────────────────────┐
│ Sidebar (220px) │  Main Content Area                          │
│                 │  px-6 py-6                                  │
│                 │                                             │
│                 │  ┌─────────────────────────────────────┐   │
│                 │  │  公告横幅 (可关闭)                    │   │
│                 │  └─────────────────────────────────────┘   │
│                 │                                             │
│                 │  快速开始                                   │
│                 │  Step1 → Step2 → Step3                      │
│                 │                                             │
│                 │  ┌─────────────┐ ┌──────────────────────┐  │
│                 │  │ 统计概览卡片  │ │  任务趋势图           │  │
│                 │  │             │ │  (柱状+折线组合图)     │  │
│                 │  │ 运行状态     │ │                      │  │
│                 │  │ 分析流程 6   │ │  日期选择器            │  │
│                 │  │ 运行任务 0   │ │                      │  │
│                 │  │ 数据样本 0   │ │  [Recharts 图表]      │  │
│                 │  └─────────────┘ └──────────────────────┘  │
│                 │                                             │
│                 │  ┌─────────────────────────────────────┐   │
│                 │  │ 最近任务                              │   │
│                 │  │ [表格 - 最多5条 + 查看全部链接]        │   │
│                 │  └─────────────────────────────────────┘   │
│                 │                                             │
│                 │  推荐分析流程                                │
│                 │  ┌────────┐ ┌────────┐ ┌────────┐         │
│                 │  │ RNA    │ │ ATAC   │ │ ChIP   │         │
│                 │  │ -seq   │ │ -seq   │ │ -seq   │         │
│                 │  └────────┘ └────────┘ └────────┘         │
│                 └─────────────────────────────────────────────┘
```

### 4.2 公告横幅（AnnouncementBanner）

```tsx
<div className="
  relative
  bg-gradient-to-r from-blue-500 to-indigo-500
  rounded-xl
  p-4 pr-12 mb-6
  text-white
">
  <div className="flex items-center gap-3">
    <div className="w-10 h-10 rounded-lg bg-white/20 flex items-center justify-center shrink-0">
      <Sparkles size={20} />
    </div>
    <div className="min-w-0">
      <h4 className="font-medium text-sm">单细胞分析模块即将上线</h4>
      <p className="text-xs text-white/80 truncate">
        全新支持 10x Genomics 数据，敬请期待
      </p>
    </div>
    <Button 
      variant="secondary" 
      size="sm" 
      className="ml-auto shrink-0 bg-white/20 text-white border-0 hover:bg-white/30"
    >
      立即查看
    </Button>
  </div>
  {/* 关闭按钮 */}
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

**说明**: 横幅可关闭，关闭状态存入 localStorage。支持多条公告轮播。

### 4.3 快速开始步骤引导（QuickStartSteps）

```
快速开始
Step1: 上传样本数据 ───→ Step2: 选择分析流程 ───→ Step3: 查看分析结果
[当前步骤高亮，已完成步骤蓝色，待完成步骤灰色]
```

```tsx
<div className="mb-6">
  <h2 className="text-lg font-semibold text-neutral-text-1 mb-4">快速开始</h2>
  <div className="flex items-center gap-2">
    {/* 已完成步骤 */}
    <StepItem number={1} title="上传样本数据" status="completed" />
    <StepArrow />
    {/* 当前步骤 */}
    <StepItem number={2} title="选择分析流程" status="current" />
    <StepArrow />
    {/* 待完成步骤 */}
    <StepItem number={3} title="查看分析结果" status="pending" />
  </div>
</div>

// StepItem 组件
function StepItem({ number, title, status }: { 
  number: number; 
  title: string; 
  status: 'completed' | 'current' | 'pending' 
}) {
  const styles = {
    completed: {
      circle: "bg-arco-primary text-white",
      text: "text-arco-primary font-medium",
    },
    current: {
      circle: "bg-arco-primary text-white ring-4 ring-arco-primary/20",
      text: "text-arco-primary font-medium",
    },
    pending: {
      circle: "bg-neutral-border text-neutral-text-3",
      text: "text-neutral-text-3",
    },
  };

  return (
    <div className="flex items-center gap-2">
      <span className={cn(
        "w-6 h-6 rounded-full flex items-center justify-center text-xs font-medium transition-all",
        styles[status].circle
      )}>
        {status === 'completed' ? <Check size={14} /> : number}
      </span>
      <span className={cn("text-sm", styles[status].text)}>{title}</span>
    </div>
  );
}

// 步骤间箭头
function StepArrow() {
  return <ChevronRight size={16} className="text-neutral-text-4 mx-1" />;
}
```

### 4.4 统计概览卡片（MetricCard）

左侧卡片布局（参照火山方舟"账户余额"卡片）:

```
┌──────────────────────────────┐
│ 运行状态          [图标按钮]  │
│                              │
│ 检测中...                     │
│                              │
│ ──────────────────────────── │
│ 分析流程          6          │
│ 运行任务          0          │
│ 数据样本          0          │
└──────────────────────────────┘
```

```tsx
// 统计概览卡片
<div className="bg-white rounded-xl p-5 shadow-arco-card">
  {/* 头部 */}
  <div className="flex items-center justify-between mb-6">
    <span className="text-sm text-neutral-text-2">运行状态</span>
    <Button variant="ghost" size="icon" className="w-8 h-8">
      <RefreshCw size={16} className="text-neutral-text-3" />
    </Button>
  </div>

  {/* 主状态 */}
  <div className="mb-6">
    <div className="flex items-center gap-2">
      <span className="relative flex h-3 w-3">
        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-arco-success opacity-75" />
        <span className="relative inline-flex rounded-full h-3 w-3 bg-arco-success" />
      </span>
      <span className="text-arco-metric text-neutral-text-1">检测中...</span>
    </div>
  </div>

  {/* 分割线 */}
  <div className="h-px bg-neutral-border mb-4" />

  {/* 子项列表 */}
  <div className="space-y-3">
    <div className="flex items-center justify-between">
      <span className="text-sm text-neutral-text-3">分析流程</span>
      <span className="text-sm font-medium text-neutral-text-1">6</span>
    </div>
    <div className="flex items-center justify-between">
      <span className="text-sm text-neutral-text-3">运行任务</span>
      <span className="text-sm font-medium text-neutral-text-1">0</span>
    </div>
    <div className="flex items-center justify-between">
      <span className="text-sm text-neutral-text-3">数据样本</span>
      <span className="text-sm font-medium text-neutral-text-1">0</span>
    </div>
  </div>
</div>
```

### 4.5 趋势图卡片（TrendChartCard）

右侧卡片，参照火山方舟"调用总量"图表：

```
┌──────────────────────────────────────────────────┐
│ 任务提交趋势                         [日期选择器]  │
│                                                  │
│  40万 ──                                  200    │
│  30万 ──    ████                         150    │
│  20万 ──    ████   ██████                100    │
│  10万 ──██  ████   ██████   ██            50    │
│    0 ─────────────────────────────────────── 0   │
│      06/12  06/14  06/16  06/18  06/20  06/22   │
│                                                  │
│  ● 分析任务数    ─── 样本数量                     │
└──────────────────────────────────────────────────┘
```

```tsx
// 使用 Recharts 实现
import { ComposedChart, Bar, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';

const data = [
  { date: '06/12', tasks: 5,   samples: 10 },
  { date: '06/14', tasks: 15,  samples: 35 },
  { date: '06/16', tasks: 40,  samples: 180 },
  { date: '06/18', tasks: 25,  samples: 120 },
  { date: '06/20', tasks: 8,   samples: 40 },
  { date: '06/22', tasks: 2,   samples: 15 },
  { date: '06/24', tasks: 0,   samples: 5 },
];

<div className="bg-white rounded-xl p-5 shadow-arco-card">
  {/* 头部 */}
  <div className="flex items-center justify-between mb-4">
    <span className="text-sm text-neutral-text-2">任务提交趋势</span>
    <Button variant="outline" size="sm" className="text-xs h-8">
      <Calendar size={14} className="mr-1" />
      2026-06-12 - 2026-06-25
    </Button>
  </div>

  {/* 单位标注 */}
  <div className="flex items-center justify-between mb-2">
    <span className="text-xs text-neutral-text-3">单位：任务数</span>
    <span className="text-xs text-neutral-text-3">单位：样本数</span>
  </div>

  {/* 图表 */}
  <ResponsiveContainer width="100%" height={240}>
    <ComposedChart data={data}>
      <CartesianGrid strokeDasharray="3 3" stroke="#E5E6EB" vertical={false} />
      <XAxis 
        dataKey="date" 
        tick={{ fill: '#86909C', fontSize: 12 }}
        axisLine={{ stroke: '#E5E6EB' }}
        tickLine={false}
      />
      <YAxis 
        yAxisId="left"
        tick={{ fill: '#86909C', fontSize: 12 }}
        axisLine={false}
        tickLine={false}
      />
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
      <Legend wrapperStyle={{ paddingTop: '16px', fontSize: '12px' }} />
      <Bar 
        yAxisId="left"
        dataKey="tasks" 
        name="分析任务数" 
        fill="#165DFF" 
        radius={[4, 4, 0, 0]}
        maxBarSize={32}
      />
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
</div>
```

### 4.6 最近任务表格（RecentTasksTable）

```tsx
<div className="bg-white rounded-xl p-5 shadow-arco-card">
  {/* 头部 */}
  <div className="flex items-center justify-between mb-4">
    <h3 className="text-base font-medium text-neutral-text-1">最近任务</h3>
    <Button variant="ghost" size="sm" className="text-arco-primary text-sm">
      查看全部 →
    </Button>
  </div>

  {/* 表格 */}
  <div className="overflow-x-auto">
    <table className="w-full">
      <thead>
        <tr className="border-b border-neutral-border">
          <th className="text-left py-3 px-4 text-xs font-medium text-neutral-text-3">任务名称</th>
          <th className="text-left py-3 px-4 text-xs font-medium text-neutral-text-3">分析流程</th>
          <th className="text-left py-3 px-4 text-xs font-medium text-neutral-text-3">提交时间</th>
          <th className="text-left py-3 px-4 text-xs font-medium text-neutral-text-3">状态</th>
          <th className="text-left py-3 px-4 text-xs font-medium text-neutral-text-3">操作</th>
        </tr>
      </thead>
      <tbody>
        {tasks.length === 0 ? (
          <tr>
            <td colSpan={5} className="py-16 text-center">
              <div className="flex flex-col items-center">
                <FlaskConical size={48} className="text-neutral-text-4 mb-3" />
                <p className="text-sm text-neutral-text-2 mb-1">暂无任务</p>
                <p className="text-xs text-neutral-text-3 mb-4">
                  点击上方按钮提交您的第一个分析任务
                </p>
                <Button size="sm" className="bg-arco-primary text-white hover:bg-blue-600">
                  <Rocket size={14} className="mr-1" />
                  提交分析任务
                </Button>
              </div>
            </td>
          </tr>
        ) : (
          tasks.map((task) => (
            <tr 
              key={task.id} 
              className="border-b border-neutral-border/50 hover:bg-neutral-hover transition-colors"
            >
              <td className="py-3 px-4 text-sm text-neutral-text-1">{task.name}</td>
              <td className="py-3 px-4">
                <Tag color="blue">{task.pipeline}</Tag>
              </td>
              <td className="py-3 px-4 text-sm text-neutral-text-3">{task.submittedAt}</td>
              <td className="py-3 px-4">
                <StatusBadge status={task.status} />
              </td>
              <td className="py-3 px-4">
                <div className="flex items-center gap-1">
                  <IconButton icon={<Eye size={16} />} tooltip="查看" />
                  <IconButton icon={<RotateCcw size={16} />} tooltip="重新运行" />
                  <IconButton icon={<Trash2 size={16} />} tooltip="删除" danger />
                </div>
              </td>
            </tr>
          ))
        )}
      </tbody>
    </table>
  </div>
</div>
```

### 4.7 状态标签（StatusBadge）

| 状态 | 样式 |
|------|------|
| 运行中 | bg-#E8F3FF text-#165DFF + 旋转 Loader 图标 |
| 排队中 | bg-#FFF7E8 text-#FF7D00 + Clock 图标 |
| 已完成 | bg-#E8FFEA text-#00B42A + CheckCircle 图标 |
| 失败 | bg-#FFECE8 text-#F53F3F + XCircle 图标 |

```tsx
function StatusBadge({ status }: { status: string }) {
  const config = {
    running:  { bg: "bg-[#E8F3FF]", text: "text-[#165DFF]", icon: Loader2, label: "运行中" },
    queued:   { bg: "bg-[#FFF7E8]", text: "text-[#FF7D00]", icon: Clock, label: "排队中" },
    completed:{ bg: "bg-[#E8FFEA]", text: "text-[#00B42A]", icon: CheckCircle2, label: "已完成" },
    failed:   { bg: "bg-[#FFECE8]", text: "text-[#F53F3F]", icon: XCircle, label: "失败" },
  };

  const c = config[status] || config.queued;
  const Icon = c.icon;

  return (
    <span className={cn(
      "inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium",
      c.bg, c.text
    )}>
      <Icon size={12} className={status === 'running' ? 'animate-spin' : ''} />
      {c.label}
    </span>
  );
}
```

---

## 五、分析流程中心页面设计

### 5.1 布局（参照火山方舟"应用实验室"）

```
┌──────────────────────────────────────────────────────────────┐
│  TopNav: 控制台   分析流程中心(激活)   实验室知识库   文档    │
├──────────┬───────────────────────────────────────────────────┤
│          │  分析流程中心                                      │
│ Sidebar  │  选择适合您研究需求的分析流程，快速启动多组学分析     │
│          │  [Github 开源代码] [开发者文档]                     │
│          │                                                   │
│          │  🔥 推荐流程                                       │
│          │  ┌──────────────────────────────────────────┐    │
│          │  │ [大图卡片 - 渐变色背景]                    │    │
│          │  │  RNA-seq 差异表达分析                      │    │
│          │  │  适用于基因表达定量与差异分析...              │    │
│          │  │  [热门] [转录组] [1,234次使用] [4.9★]      │    │
│          │  └──────────────────────────────────────────┘    │
│          │                                                   │
│          │  📋 全部流程                                      │
│          │  ┌──────────┐ ┌──────────┐ ┌──────────┐          │
│          │  │ 🧬 ATAC  │ │ 🧬 ChIP  │ │ 🧬 单细胞 │          │
│          │  │ seq      │ │ seq      │ │  RNA    │          │
│          │  │ 染色质可 │ │ 蛋白-DNA │ │ 细胞聚类 │          │
│          │  │ 及性分析 │ │ 互作分析 │ │ 与注释   │          │
│          │  │ [表观遗传]│ │ [表观遗传]│ │ [单细胞] │          │
│          │  └──────────┘ └──────────┘ └──────────┘          │
│          │  ┌──────────┐ ┌──────────┐ ┌──────────┐          │
│          │  │ 🧬 WGS   │ │ 🧬 WGBS  │ │ 🧬 宏基因 │          │
│          │  │ 全基因组 │ │ 全基因组 │ │ 组分析   │          │
│          │  │ 测序分析 │ │ 甲基化   │ │ 菌群分析 │          │
│          │  │ [基因组] │ │ [表观遗传]│ │ [微生物] │          │
│          │  └──────────┘ └──────────┘ └──────────┘          │
└──────────┴───────────────────────────────────────────────────┘
```

### 5.2 推荐流程大图卡片

```tsx
<div className="
  relative overflow-hidden 
  rounded-2xl p-6 min-h-[200px]
  bg-gradient-to-br from-blue-500 via-indigo-500 to-purple-600
  text-white cursor-pointer group
  transition-all duration-300
  hover:shadow-lg hover:scale-[1.01]
">
  {/* 装饰性 DNA 背景 */}
  <div className="absolute top-0 right-0 w-48 h-48 opacity-10">
    <Dna size={192} className="rotate-12" />
  </div>

  {/* 标签 */}
  <div className="flex gap-2 mb-4 relative z-10">
    <span className="px-2 py-0.5 rounded-full bg-white/20 text-xs font-medium">
      🔥 热门
    </span>
    <span className="px-2 py-0.5 rounded-full bg-white/20 text-xs font-medium">
      转录组
    </span>
  </div>

  {/* 内容 */}
  <h3 className="text-xl font-semibold mb-2 relative z-10">RNA-seq 差异表达分析</h3>
  <p className="text-sm text-white/80 mb-4 relative z-10 max-w-lg">
    适用于基因表达定量与差异分析，支持 DESeq2、edgeR 等多种算法，
    提供完整的质控、比对、定量和差异分析流程。
  </p>

  {/* 底部统计 */}
  <div className="flex items-center gap-6 text-xs text-white/70 relative z-10">
    <span className="flex items-center gap-1">
      <Users size={14} /> 1,234 次使用
    </span>
    <span className="flex items-center gap-1">
      <Star size={14} /> 4.9 评分
    </span>
    <span className="flex items-center gap-1">
      <Clock size={14} /> 约 2 小时
    </span>
  </div>
</div>
```

### 5.3 分析流程小卡片

```tsx
<div className="
  bg-white rounded-xl p-5 
  border border-neutral-border/60
  cursor-pointer group
  transition-all duration-300
  hover:shadow-arco-card-hover hover:-translate-y-1 hover:border-arco-primary/30
">
  {/* 图标 */}
  <div className="
    w-12 h-12 rounded-xl 
    bg-blue-50 flex items-center justify-center mb-4
    group-hover:bg-blue-100 transition-colors
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
    <Tag color="blue">表观遗传</Tag>
    <Tag color="green">自动化</Tag>
  </div>
</div>
```

### 5.4 分析流程图标映射

| 分析流程 | lucide 图标 | 图标容器背景 |
|---------|------------|------------|
| RNA-seq 差异表达 | `FlaskConical` | blue-50 → blue-100 |
| ATAC-seq 分析 | `Dna` | purple-50 → purple-100 |
| ChIP-seq 分析 | `Microscope` | indigo-50 → indigo-100 |
| 单细胞 RNA 分析 | `Grid3x3` | green-50 → green-100 |
| 全基因组测序 | `Globe` | cyan-50 → cyan-100 |
| 全基因组甲基化 | `BookOpen` | amber-50 → amber-100 |
| 宏基因组分析 | `Bug` | orange-50 → orange-100 |
| 代谢组分析 | `Beaker` | rose-50 → rose-100 |

---

## 六、组件公共样式规范

### 6.1 按钮（Button）

```tsx
// 主按钮 —— 实心蓝色
<button className="
  px-4 py-2 h-9
  bg-arco-primary text-white
  rounded-md text-sm font-medium
  hover:bg-[#306FFF]
  active:bg-[#114FD9]
  transition-colors
">
  提交分析
</button>

// 次按钮 —— 灰色边框
<button className="
  px-4 py-2 h-9
  bg-white text-neutral-text-1
  rounded-md text-sm font-medium
  border border-neutral-border
  hover:bg-neutral-hover
  active:bg-[#E5E6EB]
  transition-colors
">
  取消
</button>

// 文字按钮
<button className="
  px-2 py-1 h-8
  text-arco-primary
  text-sm font-medium
  hover:bg-arco-primary-light
  rounded-md
  transition-colors
">
  查看全部 →
</button>

// 图标按钮
<button className="
  w-8 h-8
  flex items-center justify-center
  rounded-lg
  text-neutral-text-2
  hover:bg-neutral-hover hover:text-neutral-text-1
  transition-colors
">
  <Settings size={16} />
</button>
```

### 6.2 标签（Tag）

```tsx
const tagColors = {
  blue:   { bg: "bg-blue-50",   text: "text-blue-600" },
  green:  { bg: "bg-green-50",  text: "text-green-600" },
  orange: { bg: "bg-orange-50", text: "text-orange-600" },
  red:    { bg: "bg-red-50",    text: "text-red-600" },
  purple: { bg: "bg-purple-50", text: "text-purple-600" },
  gray:   { bg: "bg-gray-100",  text: "text-gray-600" },
};

<span className="
  inline-flex items-center
  px-2 py-0.5
  rounded-full
  text-xs font-medium
  bg-blue-50 text-blue-600
">
  RNA-seq
</span>
```

### 6.3 卡片（Card）

```tsx
<div className="
  bg-white 
  rounded-xl           // 12px
  p-5                  // 20px 内边距
  shadow-arco-card     // 0 4px 16px rgba(29, 33, 41, 0.04)
  border border-neutral-border/50
  transition-all duration-300
  hover:shadow-arco-card-hover
  hover:-translate-y-0.5
">
  {/* 卡片内容 */}
</div>
```

### 6.4 输入框（Input）

```tsx
<input className="
  h-9 px-3
  bg-white
  border border-neutral-border
  rounded-md
  text-sm text-neutral-text-1
  placeholder:text-neutral-text-4
  focus:outline-none focus:border-arco-primary focus:ring-2 focus:ring-arco-primary/20
  transition-all
" placeholder="搜索分析流程..." />
```

### 6.5 空状态（EmptyState）

```tsx
<div className="flex flex-col items-center py-16">
  <FlaskConical size={64} className="text-neutral-text-4 mb-4" />
  <p className="text-base text-neutral-text-2 mb-1">暂无任务</p>
  <p className="text-sm text-neutral-text-3 mb-6">
    点击上方"提交分析任务"开始您的第一次分析
  </p>
  <Button className="bg-arco-primary text-white hover:bg-[#306FFF]">
    <Rocket size={16} className="mr-2" />
    提交分析任务
  </Button>
</div>
```

---

## 七、交互动效规范

### 7.1 全局过渡

```css
/* 所有交互元素 */
.interactive {
  transition: all 200ms cubic-bezier(0.4, 0, 0.2, 1);
}
```

### 7.2 各元素动效

| 元素 | 触发 | 效果 | 时长 |
|------|------|------|------|
| 卡片 | 悬浮 | translateY(-2px) + 阴影增强 | 300ms |
| 按钮 | 悬浮 | 背景色加深 | 150ms |
| 按钮 | 点击 | scale(0.98) | 100ms |
| 表格行 | 悬浮 | 背景变 #F2F3F8 | 150ms |
| 导航项 | 悬浮 | 背景变 #F2F3F8 | 150ms |
| 导航项 | 激活 | 背景变 #E8F3FF + 文字变 #165DFF | 150ms |
| 图标按钮 | 悬浮 | 背景出现 + 图标色加深 | 200ms |
| 侧边栏折叠 | 切换 | 宽度 220px → 64px 过渡 | 300ms |
| 页面加载 | 进入 | 内容淡入 + 轻微上移 | 400ms |

### 7.3 状态动画

- **运行中状态**: 绿色圆点脉冲动画 (`animate-ping` + `animate-pulse`)
- **加载中**: Skeleton 骨架屏 shimmer 动画
- **任务状态变更**: 标签颜色渐变过渡 (300ms)
- **进度条**: 宽度变化 500ms ease-out

---

## 八、依赖安装清单

```bash
# 图表库（双 Y 轴组合图）
npm install recharts

# 图标库（shadcn 默认使用）
npm install lucide-react

# 类名合并工具（shadcn 已包含）
# npm install clsx tailwind-merge

# shadcn 组件按需安装
npx shadcn add dropdown-menu
npx shadcn add avatar
npx shadcn add badge
npx shadcn add button
npx shadcn add table
npx shadcn add tooltip
```

---

## 九、文件结构规划

```
src/
├── components/
│   ├── ui/                    # shadcn/ui 组件
│   ├── layout/
│   │   ├── TopNav.tsx         # 顶部导航栏
│   │   ├── Sidebar.tsx        # 左侧边栏（含用户信息）
│   │   └── AppLayout.tsx      # 整体布局组合
│   ├── dashboard/
│   │   ├── AnnouncementBanner.tsx   # 公告横幅
│   │   ├── QuickStartSteps.tsx      # 快速开始步骤
│   │   ├── MetricCard.tsx           # 统计概览卡片
│   │   ├── TrendChartCard.tsx       # 趋势图卡片
│   │   ├── RecentTasksTable.tsx     # 最近任务表格
│   │   └── StatusBadge.tsx          # 状态标签
│   ├── analysis/
│   │   ├── FeaturedFlowCard.tsx     # 推荐流程大图卡片
│   │   ├── AnalysisFlowCard.tsx     # 分析流程小卡片
│   │   └── AnalysisFlowGrid.tsx     # 流程网格布局
│   └── common/
│       ├── Tag.tsx              # 药丸标签
│       ├── IconButton.tsx       # 图标按钮
│       └── EmptyState.tsx       # 空状态
├── pages/
│   ├── Dashboard.tsx            # 控制台页面
│   ├── AnalysisCenter.tsx       # 分析流程中心
│   └── Home.tsx                 # 首页（星空主题保留）
├── hooks/
│   └── useSidebar.ts            # 侧边栏状态管理
├── lib/
│   └── utils.ts                 # 工具函数
├── App.tsx
└── main.tsx
```

---

## 十、与首页（星空主题）的衔接

首页保持现有的**深色星空主题**作为品牌 Landing Page。从首页进入控制台（Dashboard）时：

1. 点击首页的"立即体验"或"进入控制台"按钮
2. 路由跳转到 `/dashboard`
3. 页面切换为**浅色火山方舟风格**
4. 顶部导航栏始终可见，作为两个主题间的视觉锚点

**建议过渡效果**: 页面切换时使用淡入淡出动画（React Router 的 transition），减少主题切换的割裂感。

---

## 十一、实施优先级

### Phase 1: 导航体系（最高优先级）
- [x] TopNav 顶部导航栏组件
- [x] Sidebar 左侧边栏组件（含展开/折叠）
- [x] 底部用户信息区（左下角 DropdownMenu）
- [x] 导航路由配置
- [x] 当前页面高亮逻辑

### Phase 2: Dashboard 控制台
- [x] 公告横幅
- [x] 快速开始步骤引导
- [x] 统计概览卡片（左侧）
- [x] 趋势图卡片（右侧，Recharts 组合图）
- [x] 最近任务表格
- [x] 空状态优化

### Phase 3: 分析流程中心
- [x] 推荐流程大图卡片
- [x] 分析流程网格布局
- [x] 分析流程小卡片

### Phase 4: 交互优化
- [x] 页面加载动画
- [x] 悬浮动效统一
- [x] 侧边栏折叠/展开动画

---

## 十二、相关资源

| 资源 | 链接 |
|------|------|
| **Arco Design** | https://arco.design |
| **shadcn/ui** | https://ui.shadcn.com/docs |
| **Recharts** | https://recharts.org/en-US |
| **lucide-react** | https://lucide.dev/icons |
| **火山方舟控制台** | https://console.volcengine.com/ark |

---

> **文档版本**: v1.0  
> **编写日期**: 2026-06-25  
> **风格参考**: 火山引擎 · 火山方舟控制台  
> **设计体系**: Arco Design（字节跳动）  
> **交付对象**: Kimi Code / AI 编程助手
