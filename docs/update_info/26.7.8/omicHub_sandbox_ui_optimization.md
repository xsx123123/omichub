# OmicHub 云端沙盒终端页面 UI 优化方案

> 目标：将「云端沙盒终端」页面（图1）的视觉风格与交互体验，统一至「FASTQ 极速质控」页面（图2）的设计语言。

---

## 一、现状分析

### 1.1 当前页面问题（图1）

| 维度 | 现状问题 | 图2参考表现 |
|------|---------|------------|
| **布局结构** | 单列纵排，信息松散，右侧大量留白 | 左右分栏，左侧配置、右侧结果，紧凑高效 |
| **顶部导航** | 仅有图标 + 标题，无返回路径 | 「← 返回工具箱 + 页面标题」结构清晰 |
| **卡片质感** | 边框色浅、圆角小、阴影弱，卡片感不足 | 白色卡片 + 明显圆角 + 轻阴影，层级分明 |
| **滑块组件** | 轨道细、滑块小、刻度标签拥挤 | 轨道粗壮、节点清晰、标签间距舒适 |
| **视觉锚点** | 缺少大字号统计，页面无焦点 | 顶部三个统计卡片（保留率/Reads/GC）作为视觉重心 |
| **按钮** | 尺寸小、位置偏、无图标 | 宽幅蓝色按钮、带播放图标、有投影 |
| **配色** | 背景偏白，与内容边界不清 | 浅灰背景（#f5f6fa）衬托白色卡片 |

### 1.2 核心差距总结

当前页面最大的问题是**「纵列堆叠导致的信息密度过低」**和**「缺少视觉锚点导致的页面无焦点」**。图2通过左右分栏 + 顶部统计卡片，在第一眼就能让用户抓住核心信息，同时左侧配置面板与右侧结果区形成清晰的「输入-输出」心智模型。

---

## 二、优化目标

1. **布局重构**：由单列纵排改为「左配右览」双栏布局
2. **组件统一**：滑块、卡片、按钮、标签全部对齐图2组件规范
3. **视觉锚点**：增加顶部统计卡片，提供即时反馈
4. **配色对齐**：背景、主色、文字色统一至图2色板
5. **交互增强**：镜像选择支持点击切换，资源实时联动预览

---

## 三、详细改造方案

### 3.1 布局重构：左配右览双栏

```
┌─────────────────────────────────────────────────────────────┐
│  ← 返回工具箱    云端沙盒终端                                │
│  选择预装工具链的镜像，启动一个隔离、用完即毁的沙盒终端       │
├──────────────────────┬──────────────────────────────────────┤
│                      │                                      │
│  【选择分析环境】      │  ┌────────┬────────┬────────┐      │
│  ┌────────────────┐  │  │ 1.2 GB │ 12 个  │ 3 秒   │      │
│  │ 🔧 基础生信     │  │  │ 镜像大小│ 预装工具│ 预计启动│      │
│  │   [选中]        │  │  └────────┴────────┴────────┘      │
│  ├────────────────┤  │                                      │
│  │ 🧬 RNA-seq     │  │  【启动配置预览】                     │
│  │   [未选]        │  │  分析镜像    🔧 基础生信            │
│  ├────────────────┤  │  分配内存    512 MB                   │
│  │ 🧪 单细胞分析   │  │  分配 CPU    1 核                    │
│  │   [未选]        │  │  挂载目录    /data/...                │
│  └────────────────┘  │  网络模式    隔离（无出站）            │
│                      │  生命周期    用完即毁 🔴              │
│  【资源设置】         │                                      │
│  内存 [━━━━●━━━━]   │  [▶ 启动 基础生信]                   │
│  CPU  [━━━●━━━━━]   │                                      │
│                      │                                      │
└──────────────────────┴──────────────────────────────────────┘
```

**设计要点：**
- 左侧固定宽度 `380px`（可响应式），承载所有配置
- 右侧自适应，承载统计卡片 + 配置预览 + 启动按钮
- 两栏间距 `20px`，与图2左右面板间距一致

---

### 3.2 顶部导航栏改造

**现状：** 仅有图标 + "云端沙盒终端" 文字，无层级感。

**改造后：**

```tsx
// 顶部导航组件
<div className="page-header">
  <Button 
    type="secondary" 
    icon={<IconLeft />} 
    style={{ borderRadius: 8, width: 36, height: 36 }}
  />
  <div>
    <Typography.Text style={{ fontSize: 20, fontWeight: 600 }}>
      云端沙盒终端
    </Typography.Text>
    <Typography.Text type="secondary" style={{ fontSize: 13, marginTop: 4, display: 'block' }}>
      选择预装工具链的镜像，启动一个隔离、用完即毁的沙盒终端
    </Typography.Text>
  </div>
</div>
```

**样式规范：**
- 返回按钮：`36×36px`、圆角 `8px`、浅灰边框、hover 时背景变主色浅蓝
- 标题：`20px`、字重 `600`、色值 `#1f2937`
- 副标题：`13px`、色值 `#6b7280`、与标题间距 `4px`

---

### 3.3 镜像选择卡片改造

**现状：** 单选按钮 + 文字，选中态只有一个小蓝点，卡片感弱。

**改造后：** 卡片式单选，选中时有边框高亮 + 背景变化 + 投影。

```tsx
// 镜像选择项
<div className={
  `image-item ${selected ? 'active' : ''}`
}>
  <div className="image-radio">
    {selected && <div className="radio-dot" />}
  </div>
  <div className="image-info">
    <div className="image-name">🔧 基础生信</div>
    <div className="image-desc">
      预装 samtools、bcftools、bedtools、fastqc、seqkit、
      python3、numpy、pandas、biopython、pysam
    </div>
    <Tag size="small" style={{ marginTop: 8 }}>基础</Tag>
    <div className="image-res">默认资源：512 MB / 1 核</div>
  </div>
</div>
```

**样式规范：**

| 属性 | 未选中 | 选中 |
|------|--------|------|
| 边框 | `2px solid #e5e7eb` | `2px solid #2e5bff` |
| 背景 | `#ffffff` | `#f8faff` |
| 阴影 | 无 | `0 0 0 3px rgba(46,91,255,0.08)` |
| 圆角 | `10px` | `10px` |
| 内边距 | `16px` | `16px` |
| hover | 边框 `#c7d2fe`、背景 `#fafbff` | — |

**单选按钮样式：**
- 外圈：`18×18px`、圆角 `50%`、边框 `2px solid #d1d5db`
- 选中时：外圈变 `#2e5bff` 背景填充，内部白色圆点 `6×6px`

---

### 3.4 资源设置滑块改造

**现状：** 轨道细（约 `2px`）、滑块小、刻度标签拥挤在轨道下方。

**改造后：** 粗轨道 + 圆形滑块 + 清晰刻度。

```tsx
// 滑块组件（基于 Arco Slider 封装）
<Slider
  min={256}
  max={3840}
  step={512}
  value={memory}
  onChange={setMemory}
  showTicks
  formatTooltip={(v) => `${v} MB`}
  style={{
    trackHeight: 6,
    railColor: '#e5e7eb',
    trackColor: '#2e5bff',
    handleSize: 18,
    handleBorderColor: '#2e5bff',
    handleBoxShadow: '0 2px 6px rgba(46,91,255,0.25)',
  }}
/>
```

**样式规范：**

| 属性 | 值 |
|------|-----|
| 轨道高度 | `6px` |
| 轨道背景 | `#e5e7eb` |
| 填充色 | `#2e5bff` |
| 滑块尺寸 | `18×18px` |
| 滑块形状 | 圆形 |
| 滑块背景 | `#ffffff` |
| 滑块边框 | `2px solid #2e5bff` |
| 滑块投影 | `0 2px 6px rgba(46,91,255,0.25)` |
| 刻度标签 | `11px`、色值 `#6b7280`、上方 `5px` 竖线指示 |
| 当前值标签 | 背景 `#e8eeff`、文字 `#2e5bff`、圆角 `6px`、字重 `600` |

**刻度分布（内存）：**
`256M → 768M → 1280M → 1792M → 2304M → 2816M → 3328M → 3840M`

**刻度分布（CPU）：**
`0.5核 → 1核 → 1.5核 → 2核 → 2.5核 → 3核 → 3.5核 → 4核`

---

### 3.5 新增：顶部统计卡片

这是图2最核心的视觉特征，当前页面完全缺失。需要在右侧顶部增加 3 个统计卡片。

```tsx
// 统计卡片
<Grid.Row gutter={16}>
  <Grid.Col span={8}>
    <Card className="stat-card">
      <div className="stat-label">镜像大小</div>
      <div className="stat-value">
        1.2<span className="stat-unit">GB</span>
      </div>
    </Card>
  </Grid.Col>
  <Grid.Col span={8}>
    <Card className="stat-card">
      <div className="stat-label">预装工具</div>
      <div className="stat-value">
        12<span className="stat-unit">个</span>
      </div>
    </Card>
  </Grid.Col>
  <Grid.Col span={8}>
    <Card className="stat-card">
      <div className="stat-label">预计启动</div>
      <div className="stat-value">
        3<span className="stat-unit">秒</span>
      </div>
    </Card>
  </Grid.Col>
</Grid.Row>
```

**样式规范：**

| 属性 | 值 |
|------|-----|
| 卡片背景 | `#ffffff` |
| 边框 | `1px solid #e5e7eb` |
| 圆角 | `12px` |
| 内边距 | `20px` |
| 标签文字 | `12px`、色值 `#6b7280`、下边距 `8px` |
| 数值文字 | `24px`、字重 `700`、色值 `#1f2937` |
| 单位文字 | `14px`、字重 `500`、色值 `#6b7280`、左边距 `2px` |

---

### 3.6 配置预览面板改造

**现状：** 无预览区，用户无法确认配置后再启动。

**改造后：** 增加「启动配置预览」面板，列出所有关键配置项，底部放置启动按钮。

```tsx
<Card className="preview-panel">
  <div className="preview-title">
    <IconFile style={{ marginRight: 8 }} />
    启动配置预览
  </div>
  <div className="preview-row">
    <span className="preview-key">分析镜像</span>
    <span className="preview-val">🔧 基础生信</span>
  </div>
  <div className="preview-row">
    <span className="preview-key">分配内存</span>
    <span className="preview-val">512 MB</span>
  </div>
  <div className="preview-row">
    <span className="preview-key">分配 CPU</span>
    <span className="preview-val">1 核</span>
  </div>
  <div className="preview-row">
    <span className="preview-key">挂载目录</span>
    <span className="preview-val">/data/omichub/users/...</span>
  </div>
  <div className="preview-row">
    <span className="preview-key">网络模式</span>
    <span className="preview-val">隔离（无出站）</span>
  </div>
  <div className="preview-row">
    <span className="preview-key">生命周期</span>
    <span className="preview-val" style={{ color: '#dc2626' }}>
      用完即毁
    </span>
  </div>

  <Button 
    type="primary" 
    size="large"
    long
    icon={<IconPlayArrow />}
    style={{
      marginTop: 20,
      borderRadius: 10,
      height: 48,
      fontSize: 15,
      fontWeight: 600,
      boxShadow: '0 4px 12px rgba(46,91,255,0.25)',
    }}
  >
    启动 基础生信
  </Button>
</Card>
```

**样式规范：**

| 属性 | 值 |
|------|-----|
| 面板背景 | `#ffffff` |
| 边框 | `1px solid #e5e7eb` |
| 圆角 | `12px` |
| 内边距 | `24px` |
| 标题 | `15px`、字重 `600`、图标 `18px`、右边距 `8px` |
| 行高 | `flex` 两端对齐、内边距 `12px 0`、底边框 `1px solid #f3f4f6` |
| key 色 | `#6b7280` |
| val 色 | `#1f2937`、字重 `600` |
| 启动按钮 | 主蓝色、通栏、高 `48px`、圆角 `10px`、投影 |

---

### 3.7 配色方案统一

全局色板对齐图2：

```css
:root {
  --bg: #f5f6fa;              /* 页面背景 */
  --card-bg: #ffffff;          /* 卡片背景 */
  --primary: #2e5bff;          /* 主蓝色（按钮、选中、填充） */
  --primary-light: #e8eeff;      /* 主色浅蓝（hover、标签背景） */
  --text-main: #1f2937;        /* 主文字 */
  --text-sub: #6b7280;         /* 次要文字 */
  --border: #e5e7eb;           /* 边框 */
  --radius: 12px;              /* 卡片圆角 */
  --shadow: 0 1px 3px rgba(0,0,0,0.05), 0 1px 2px rgba(0,0,0,0.03);
  --shadow-hover: 0 4px 12px rgba(0,0,0,0.08);
  --shadow-btn: 0 4px 12px rgba(46,91,255,0.25);
}
```

---

### 3.8 交互增强

| 交互点 | 当前行为 | 优化后行为 |
|--------|---------|-----------|
| 镜像选择 | 点击单选按钮 | 点击整个卡片区域均可选中，hover 有视觉反馈 |
| 资源调整 | 仅滑块拖动 | 滑块拖动时，右侧预览面板实时联动更新 |
| 启动按钮 | 固定文字 | 动态跟随选中镜像名称，如「启动 基础生信」→「启动 RNA-seq 分析」 |
| 卡片 hover | 无 | 轻微上浮 + 阴影加深，提示可点击 |

---

## 四、响应式适配

```css
@media (max-width: 900px) {
  .main-layout {
    grid-template-columns: 1fr;  /* 单列堆叠 */
  }
  .preview-grid {
    grid-template-columns: 1fr;  /* 统计卡片纵向排列 */
  }
  .left-column {
    order: 2;  /* 配置面板放下面 */
  }
  .right-column {
    order: 1;  /* 预览面板放上面 */
  }
}
```

---

## 五、文件结构与代码组织建议

```
src/
├── pages/
│   └── SandboxTerminal/
│       ├── index.tsx              # 页面入口
│       ├── components/
│       │   ├── PageHeader.tsx     # 顶部导航
│       │   ├── ImageSelector.tsx  # 镜像选择卡片组
│       │   ├── ResourceSlider.tsx # 资源滑块（内存/CPU）
│       │   ├── StatCards.tsx      # 顶部统计卡片
│       │   ├── PreviewPanel.tsx   # 配置预览面板
│       │   └── LaunchButton.tsx   # 启动按钮
│       ├── hooks/
│       │   └── useSandboxConfig.ts # 配置状态管理
│       └── style.module.less      # 页面级样式
```

---

## 六、实施优先级

| 优先级 | 改造项 | 预估工时 | 影响 |
|--------|--------|---------|------|
| P0 | 布局重构（左右分栏） | 2h | ★★★★★ |
| P0 | 配色统一（背景+卡片） | 30min | ★★★★★ |
| P0 | 顶部统计卡片 | 1h | ★★★★★ |
| P1 | 镜像选择卡片化 | 1.5h | ★★★★☆ |
| P1 | 滑块组件美化 | 1h | ★★★★☆ |
| P1 | 配置预览面板 | 1h | ★★★★☆ |
| P2 | 按钮改造 + 动态文案 | 30min | ★★★☆☆ |
| P2 | 响应式适配 | 1h | ★★★☆☆ |
| P3 | 交互动效（hover、联动） | 1h | ★★☆☆☆ |

**建议分两次迭代：**
- **第一轮（P0+P1）**：布局 + 卡片 + 滑块 + 统计，完成视觉统一
- **第二轮（P2+P3）**：按钮 + 响应式 + 动效，打磨细节

---

## 七、验收标准

- [ ] 页面背景为 `#f5f6fa`，卡片为白色圆角
- [ ] 顶部有「返回」按钮 + 标题 + 副标题
- [ ] 左右分栏布局，左侧配置、右侧预览
- [ ] 右侧顶部有 3 个统计卡片，大字号显示
- [ ] 镜像选择为卡片式单选，选中态有明显边框高亮
- [ ] 滑块轨道 `6px`、圆形滑块、刻度清晰
- [ ] 启动按钮宽幅、蓝色、带播放图标、有投影
- [ ] 配置预览面板列出所有关键信息
- [ ] 镜像切换时，按钮文案和预览面板实时联动
- [ ] 在 `900px` 以下屏幕自动切换为单列布局

---

*文档生成时间：2026-07-08*
*设计参考：OmicHub FASTQ 极速质控页面*
