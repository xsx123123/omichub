# OmicHub 生信工具箱 — 火山图绘制模块（Plotly 动态版）

> 版本：v1.0  
> 目标：在「生信工具箱」中新增「火山图绘制」工具，基于 Plotly.js 实现完全交互式动态火山图，功能对齐现有 R 脚本 `DrawVolcanoAddGene`，并超越静态图的交互体验。

---

## 一、模块定位

| 项目 | 说明 |
|------|------|
| **模块名称** | 火山图绘制 / Volcano Plot |
| **入口位置** | 左侧导航「生信工具箱」→ 新增卡片「火山图绘制」 |
| **技术栈** | React + Plotly.js (`react-plotly.js`) + Arco Design |
| **核心特性** | 交互式缩放、悬停基因详情、基因搜索高亮、动态阈值调整、PNG/SVG 导出 |

---

## 二、功能设计（对齐 R 脚本 + 增强）

### 2.1 数据输入

| 输入方式 | 说明 |
|----------|------|
| **文件上传** | 支持 `.csv` / `.tsv` / `.xlsx`，自动识别分隔符 |
| **列名映射** | 用户可手动指定 `padj` / `log2FoldChange` / `GENENAME` 对应列（如 R 脚本的 `padj_colname` 等） |
| **粘贴板** | 支持直接粘贴表格数据（小数据调试） |
| **示例数据** | 提供内置示例 DEG 数据，一键加载体验 |

### 2.2 参数配置面板（左侧或顶部折叠面板）

参考 R 脚本参数，全部支持实时调整并即时重绘：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `pvalCutoff` | 0.05 | 显著性阈值 |
| `LFCCutoff` | 1 | log2FoldChange 阈值 |
| `EXP_NAME` | `"Volcano"` | 实验名称，用于标题和轴标签 |
| `up_gene_color` | `#e41749` | 上调基因颜色 |
| `up_gene_tag_color` | `#7FFF00` | 上调标注基因高亮色 |
| `down_gene_color` | `#41b6e6` | 下调基因颜色 |
| `down_gene_tag_color` | `#16A085` | 下调标注基因高亮色 |
| `non_sig_color` | `#C7C7C7` | 非显著基因颜色 |
| `point_size` | 6 | 散点大小 |
| `alpha` | 0.6 | 非显著基因透明度 |
| `show_threshold_lines` | true | 是否显示阈值虚线 |
| `label_top_n` | 15 | 自动标注 Top N 显著基因（上下调各 N/2） |
| `custom_genes` | [] | 用户指定要高亮标注的基因列表（逗号分隔） |

### 2.3 智能数据处理逻辑（对齐 R 脚本）

```
1. 列名映射 → 标准化为 padj, log2FoldChange, GENENAME
2. 去除 NA 行
3. pvalue = 0 的处理 → 替换为 1e-324（JS 最小正值）
4. 计算 -log10(padj)
5. 分类标记：
   - Up: padj < pvalCutoff && log2FC > LFCCutoff
   - Down: padj < pvalCutoff && log2FC < -LFCCutoff
   - Non: 其他
6. 自动 Y 轴范围计算：
   - 若 max(y) > 300 → y_max = 250
   - 若 top1/top2 > 1.4 → y_max = (top1+top2)/2
   - 否则 y_max = max(y) * 1.1
7. X 轴范围：max(|log2FC|) * 1.2，若 > 7.5 则取 7.5
```

### 2.4 Plotly 交互特性

| 交互 | 实现 |
|------|------|
| **悬停提示** | 显示基因名、padj、log2FC、分组 |
| **框选缩放** | 鼠标框选区域自动放大 |
| **基因搜索** | 顶部搜索框输入基因名，Plotly 自动定位并高亮（脉冲动画） |
| **图例点击** | 点击图例可隐藏/显示特定分组 |
| **阈值拖拽** | 在图上直接拖拽虚线调整阈值（高级功能，可选） |
| **导出** | 工具栏支持 PNG / SVG / PDF 导出，以及数据下载 |

### 2.5 图表布局设计

- **标题**：自动换行，如 `"RNA-seq log₂ fold change [EXP_NAME]\nVolcano Plot"`
- **X 轴**：`"log₂ fold change (EXP_NAME)"`
- **Y 轴**：`"-log₁₀(padj)"`
- **阈值线**：
  - 垂直线：`x = ±LFCCutoff`，黑色虚线，width=1
  - 水平线：`y = -log10(pvalCutoff)`，黑色虚线，width=1
- **散点分层**：Non-significant → Down → Up → 标注基因（Z 轴顺序确保标注在最上层）
- **标注基因**：使用 Plotly `annotations` 或 `scatter` text mode，带引线

---

## 三、UI 界面设计

### 3.1 整体布局（三栏响应式）

```
┌─────────────────────────────────────────────────────────────┐
│  顶部：面包屑 + 标题「火山图绘制」 + 示例数据按钮            │
├──────────┬─────────────────────────────────────┬──────────┤
│          │                                     │          │
│  左侧面板 │      中间：Plotly 火山图              │  右侧面板 │
│  参数配置 │      （占主要区域，可全屏）            │  基因列表 │
│  数据上传 │                                     │  统计信息 │
│          │                                     │          │
├──────────┴─────────────────────────────────────┴──────────┤
│  底部：数据预览表格（可折叠）                                │
└─────────────────────────────────────────────────────────────┘
```

- **桌面端**：左 280px（参数）+ 中自适应（图表）+ 右 260px（基因列表）
- **平板**：左侧面板可折叠为顶部工具栏
- **移动端**：参数面板变为底部抽屉，图表全屏

### 3.2 左侧面板 — 参数配置

使用 Arco Design `Collapse` 分组：

```
▶ 数据上传与列映射
  - 文件上传组件（Drag & Drop）
  - 列选择器：padj 列 / log2FC 列 / 基因名列
▶ 阈值与颜色
  - 数字输入：pvalCutoff, LFCCutoff
  - 颜色选择器：上调色、下调色、非显著色、标注色
▶ 标注设置
  - 开关：自动标注 Top N
  - 数字输入：Top N 数量
  - 文本域：自定义基因列表（逗号/换行分隔）
▶ 图表样式
  - 点大小滑块
  - 透明度滑块
  - 实验名称输入
```

每个参数修改后 **debounce 300ms** 自动触发重绘。

### 3.3 右侧面板 — 基因列表与统计

```
┌─────────────────┐
│  📊 统计概览      │
│  总基因: 15,842  │
│  上调: 342       │
│  下调: 298       │
│  非显著: 15,202  │
├─────────────────┤
│  🔍 基因搜索      │
│  [___________]   │
├─────────────────┤
│  ⭐ 显著基因列表  │
│  （按 padj 排序） │
│  • TP53  ↑ 4.2   │
│  • BRCA1 ↓ 3.8   │
│  ...             │
└─────────────────┘
```

- 点击基因列表项 → Plotly 高亮该点并居中
- 支持多选批量标注

### 3.4 图表区域工具栏

悬浮在图表右上角：

```
[📥 导出 PNG] [📥 导出 SVG] [🔍 重置视图] [⛶ 全屏]
```

---

## 四、技术实现方案

### 4.1 依赖

```json
{
  "react-plotly.js": "^2.6.0",
  "plotly.js": "^2.27.0",
  "papaparse": "^5.4.0",
  "xlsx": "^0.18.5"
}
```

### 4.2 核心数据结构

```typescript
interface VolcanoData {
  GENENAME: string;
  padj: number;
  log2FoldChange: number;
  log10_padj: number;
  group: 'up' | 'down' | 'non';
  isHighlighted?: boolean;  // 用户指定标注
  isTop?: boolean;          // Top N 自动标注
}

interface VolcanoConfig {
  pvalCutoff: number;
  lfcCutoff: number;
  expName: string;
  colors: {
    up: string;
    down: string;
    non: string;
    upTag: string;
    downTag: string;
  };
  pointSize: number;
  alpha: number;
  showThreshold: boolean;
  labelTopN: number;
  customGenes: string[];
}
```

### 4.3 数据处理 Pipeline（前端）

```typescript
function processVolcanoData(
  rawData: any[],
  colMap: { padj: string; lfc: string; gene: string },
  config: VolcanoConfig
): VolcanoData[] {
  // 1. 列映射
  // 2. 过滤 NA
  // 3. p=0 处理
  // 4. 计算 -log10(padj)
  // 5. 分组标记
  // 6. 排序
  // 7. 标记 Top N 和自定义基因
  // 8. 计算坐标轴范围
}
```

### 4.4 Plotly 配置核心代码结构

```typescript
const traces = [
  // Non-significant（底层，灰色）
  {
    x: nonData.map(d => d.log2FoldChange),
    y: nonData.map(d => d.log10_padj),
    mode: 'markers',
    type: 'scatter',
    name: `Non-significant (${nonData.length})`,
    marker: { color: config.colors.non, size: config.pointSize, opacity: config.alpha },
    hovertemplate: '<b>%{text}</b><br>log₂FC: %{x:.3f}<br>-log₁₀padj: %{y:.3f}<extra></extra>',
    text: nonData.map(d => d.GENENAME),
  },
  // Down-regulated
  { ... },
  // Up-regulated
  { ... },
  // 标注基因（最上层，带 text 标签）
  {
    mode: 'markers+text',
    textposition: 'top center',
    textfont: { size: 10, color: '#333' },
    // ...
  }
];

const layout = {
  title: { text: generateTitle(config.expName), font: { size: 16 } },
  xaxis: { 
    title: `log₂ fold change (${config.expName})`,
    range: [-xMax, xMax],
    zeroline: false 
  },
  yaxis: { 
    title: '-log₁₀(padj)', 
    range: [0, yMax],
    zeroline: false 
  },
  shapes: [
    // 阈值线：x = ±LFCCutoff, y = -log10(pvalCutoff)
    { type: 'line', x0: -lfc, x1: -lfc, y0: 0, y1: yMax, line: { dash: 'dash', width: 1, color: '#000' } },
    { type: 'line', x0: lfc, x1: lfc, y0: 0, y1: yMax, line: { dash: 'dash', width: 1, color: '#000' } },
    { type: 'line', x0: -xMax, x1: xMax, y0: -log10(pval), y1: -log10(pval), line: { dash: 'dash', width: 1, color: '#000' } },
  ],
  hovermode: 'closest',
  plot_bgcolor: '#fafafa',
  paper_bgcolor: '#fff',
  legend: { orientation: 'h', y: -0.15 },
};
```

---

## 五、与现有 R 脚本功能对照表

| R 脚本功能 | Plotly 实现 | 状态 |
|-----------|------------|------|
| 列名映射 | 下拉选择器手动映射 | ✅ |
| NA 去除 | 前端过滤 | ✅ |
| p=0 处理 | 替换为 Number.MIN_VALUE | ✅ |
| Up/Down/Non 分类 | 前端计算 + 图例分组 | ✅ |
| 自动 Y 轴范围 | 复刻 R 逻辑（极端值处理） | ✅ |
| 自动 X 轴范围 | 复刻 R 逻辑（上限 7.5） | ✅ |
| 标题自动换行 | 检测长度 > 30 字符插入 `\n` | ✅ |
| 阈值虚线 | Plotly `shapes` 实现 | ✅ |
| Top 15 基因标注 | 参数可调 + 自动排序 | ✅ |
| 自定义基因标注 | 搜索框 + 文本域输入 | ✅ |
| ggrepel 防重叠 | Plotly 自带 `textposition` + 可手动调整 | ⚠️ 近似 |
| 主题 minimal | 自定义 layout 样式 | ✅ |
| **新增：交互缩放** | Plotly 原生支持 | 🚀 增强 |
| **新增：悬停详情** | Plotly hovertemplate | 🚀 增强 |
| **新增：基因搜索定位** | 编程实现 | 🚀 增强 |
| **新增：PNG/SVG 导出** | Plotly 工具栏 | 🚀 增强 |

---

## 六、详细前端提示词（Prompt for CC / 前端开发）

```markdown
# 🎯 任务：在 OmicHub「生信工具箱」中新增「火山图绘制」模块

## 背景
OmicHub 是一个生物信息学分析平台，当前「生信工具箱」已有 FASTQ 质控、Web 基因组浏览器、BLAST、组学绘图工坊、KEGG 富集分析等工具。现需新增「火山图绘制」工具，用于交互式展示 RNA-seq 等差异表达分析（DEG）结果。

## 技术约束
- 前端框架：React 18 + TypeScript
- UI 库：Arco Design（字节跳动）
- 图表库：Plotly.js（react-plotly.js）
- 状态管理：React Context 或 Zustand
- 路由：/tools/volcano-plot
- 必须支持暗黑模式（跟随平台主题）

## 一、页面路由与入口
1. 在「生信工具箱」页面新增卡片：
   - 图标：使用 `IconFire` 或自定义火山图标（🔥）
   - 标题：「火山图绘制」
   - 描述：「交互式差异表达火山图，支持动态阈值调整、基因搜索高亮、一键导出」
   - 点击跳转：/tools/volcano-plot

2. 面包屑导航：首页 > 生信工具箱 > 火山图绘制

## 二、整体布局（参考上文三栏设计）

### 左侧面板：参数配置（280px，可折叠）
使用 Arco Design `Form` + `Collapse` 实现以下分组：

**分组1：数据上传**
- Upload 组件：拖拽上传 `.csv/.tsv/.xlsx`，限制 50MB
- 上传后自动解析，展示前 5 行预览
- 三个 Select 组件：选择 padj 列 / log2FoldChange 列 / 基因名列（自动识别候选列）
- 「加载示例数据」按钮：内置 200 行模拟 DEG 数据

**分组2：阈值与颜色**
- InputNumber：pvalCutoff（0.001 ~ 1，步长 0.001，默认 0.05）
- InputNumber：LFCCutoff（0 ~ 5，步长 0.1，默认 1）
- 四个 ColorPicker：上调色(#e41749)、下调色(#41b6e6)、非显著色(#C7C7C7)、上调标注色(#7FFF00)、下调标注色(#16A085)
- Switch：显示阈值线（默认开启）

**分组3：标注设置**
- Switch：自动标注 Top N（默认开启）
- InputNumber：Top N 数量（1 ~ 100，默认 15）
- TextArea：自定义基因列表（逗号/换行/空格分隔，如 "TP53, BRCA1, EGFR"）
- 输入时实时校验基因名是否在数据集中，不存在的显示红色提示

**分组4：图表样式**
- Input：实验名称（默认 "Volcano"，用于标题和轴标签）
- Slider：点大小（2 ~ 15，默认 6）
- Slider：非显著点透明度（0.1 ~ 1，默认 0.6）

> 所有参数修改后 debounce 300ms 自动触发图表重绘，避免频繁渲染。

### 中间区域：Plotly 火山图
- 占据主要空间，最小高度 600px
- 图表上方悬浮工具栏（绝对定位，右上角）：
  - Button：导出 PNG
  - Button：导出 SVG
  - Button：重置视图
  - Button：全屏切换
- Plotly 配置要求：
  - `displayModeBar: true`（显示 Plotly 自带工具栏）
  - `responsive: true`
  - `hovermode: 'closest'`
  - 自定义 hovertemplate：显示基因名、log2FC、padj、分组
  - 散点按 Z 顺序分层：Non → Down → Up → Highlighted（确保标注点在最上层）
  - 阈值线使用 `shapes` 实现，黑色虚线，width=1
  - 标题自动换行：若 `expName + " Volcano Plot"` 长度 > 30 字符，插入换行符

### 右侧面板：基因列表与统计（260px，可折叠）
**统计卡片**：
- 总基因数 / 上调数 / 下调数 / 非显著数（使用 Arco `Statistic` 组件，上调红色、下调蓝色）

**基因搜索**：
- Input.Search：输入基因名，支持模糊搜索
- 搜索结果列表，点击后在图表中高亮该基因（脉冲动画 + 自动居中）
- 支持 Enter 键快速定位第一个结果

**显著基因列表**：
- 按 padj 升序排列，展示 Top 50
- 每行显示：基因名 + log2FC（带上下箭头）+ -log10(padj)
- 点击行 → 图表高亮
- 多选 Checkbox → 批量加入「自定义标注」

### 底部区域：数据预览表格
- 可折叠的 `Table` 组件
- 展示完整数据集，带分页（默认 50 条/页）
- 列：基因名、log2FC、padj、-log10(padj)、分组（带颜色标签）
- 支持按列排序

## 三、核心数据处理逻辑（必须严格实现）

在 `utils/volcanoProcessor.ts` 中实现：

```typescript
export function processVolcanoData(
  rawData: Record<string, any>[],
  colMap: { padj: string; lfc: string; gene: string },
  config: VolcanoConfig
) {
  // 1. 列名映射：将用户选择的列映射到标准字段
  // 2. 数据清洗：
  //    - 去除 padj/log2FC/GENENAME 任一为 NA/null/undefined 的行
  //    - padj <= 0 的替换为 Number.MIN_VALUE（约 5e-324）
  //    - 计算 log10_padj = -Math.log10(padj)
  // 3. 分组：
  //    - Up: padj < pvalCutoff && log2FC > LFCCutoff
  //    - Down: padj < pvalCutoff && log2FC < -LFCCutoff
  //    - Non: 其他
  // 4. 排序：按 padj 升序
  // 5. 自动标注 Top N：
  //    - 从 Up 组取前 labelTopN/2 个，从 Down 组取前 labelTopN/2 个
  //    - 标记 isTop = true
  // 6. 自定义标注：
  //    - 遍历 customGenes，若存在于数据集，标记 isHighlighted = true
  // 7. 坐标轴范围计算：
  //    - yMax: 若 max(log10_padj) > 300 → 250；
  //            若 top1/top2 > 1.4 → (top1+top2)/2；
  //            否则 → max * 1.1
  //    - xMax: max(abs(log2FC)) * 1.2，若 > 7.5 则取 7.5
  // 8. 返回：{ processedData, stats, axisRange }
}
```

## 四、Plotly 图表配置规范

在 `components/VolcanoPlot.tsx` 中实现：

```typescript
// 必须分 4 个 trace 绘制，确保图层顺序：
const traces = [
  {
    name: `Non-significant (${nonSig.length})`,
    x: nonSig.map(d => d.log2FoldChange),
    y: nonSig.map(d => d.log10_padj),
    mode: 'markers',
    type: 'scattergl', // 大数据量时使用 scattergl
    marker: { color: colors.non, size: pointSize, opacity: alpha },
    hovertemplate: '<b>%{text}</b><br>log₂FC: %{x:.3f}<br>-log₁₀padj: %{y:.3f}<br>Group: Non-significant<extra></extra>',
    text: nonSig.map(d => d.GENENAME),
  },
  // Down-regulated trace...
  // Up-regulated trace...
  // Highlighted genes trace（mode: 'markers+text'）...
];

const layout = {
  title: {
    text: title.length > 30 ? title.slice(0, 30) + '\n' + title.slice(30) : title,
    font: { size: 16, color: isDark ? '#fff' : '#333' }
  },
  xaxis: {
    title: `log₂ fold change (${expName})`,
    range: [-xMax, xMax],
    zeroline: false,
    gridcolor: isDark ? '#333' : '#eee',
    color: isDark ? '#fff' : '#333',
  },
  yaxis: {
    title: '-log₁₀(padj)',
    range: [0, yMax],
    zeroline: false,
    gridcolor: isDark ? '#333' : '#eee',
    color: isDark ? '#fff' : '#333',
  },
  shapes: showThreshold ? [
    { type: 'line', x0: -lfc, x1: -lfc, y0: 0, y1: yMax, line: { dash: 'dash', width: 1, color: '#000' } },
    { type: 'line', x0: lfc, x1: lfc, y0: 0, y1: yMax, line: { dash: 'dash', width: 1, color: '#000' } },
    { type: 'line', x0: -xMax, x1: xMax, y0: -Math.log10(pvalCutoff), y1: -Math.log10(pvalCutoff), line: { dash: 'dash', width: 1, color: '#000' } },
  ] : [],
  plot_bgcolor: isDark ? '#1a1a1a' : '#fafafa',
  paper_bgcolor: isDark ? '#141414' : '#fff',
  font: { color: isDark ? '#fff' : '#333' },
  legend: { orientation: 'h', y: -0.15, x: 0.5, xanchor: 'center' },
  hovermode: 'closest',
  margin: { t: 60, r: 40, b: 80, l: 60 },
};
```

## 五、暗黑模式适配

- 监听平台主题切换（通过 Context 或 CSS 变量）
- Plotly 图表：
  - 背景色：`plot_bgcolor` / `paper_bgcolor` 随主题切换
  - 文字颜色：轴标题、刻度、图例随主题切换
  - 网格线：`gridcolor` 使用 `#333`（暗）/ `#eee`（亮）
- Arco Design 组件自动跟随主题，无需额外处理

## 六、性能优化要求

1. 数据量 > 5000 行时，Plotly trace 使用 `type: 'scattergl'`（WebGL 渲染）
2. 参数变化使用 `debounce(300ms)` 触发重绘
3. 大数据集（> 10000 行）时：
   - 非显著点采样显示（每 10 个取 1 个，或按密度采样）
   - 显著点全部保留
   - 添加提示：「数据量较大，已采样显示，导出时使用完整数据」
4. 使用 `useMemo` 缓存 processedData，避免重复计算
5. Plotly 图表使用 `useRef` 获取实例，通过 `react-plotly.js` 的 `onUpdate` 控制重绘范围

## 七、错误处理

| 场景 | 处理方式 |
|------|----------|
| 文件格式错误 | Upload 组件显示红色错误提示，支持重新上传 |
| 列名映射失败 | 自动识别失败时，Select 显示「未识别」，用户手动选择后方可绘图 |
| 无显著基因 | 图表正常显示，右侧面板统计为 0，给出友好提示 |
| 自定义基因不存在 | TextArea 中不存在的基因名标红，Tooltip 提示「未在数据集中找到」 |
| 全为 NA | 弹出 Notification：「数据集中无有效数值，请检查列映射」 |

## 八、文件结构建议

```
src/
  pages/
    VolcanoPlot/
      index.tsx                 # 主页面，三栏布局
      components/
        ConfigPanel.tsx         # 左侧参数配置
        PlotArea.tsx            # 中间 Plotly 图表
        GenePanel.tsx           # 右侧基因列表
        DataPreview.tsx         # 底部数据预览
        ExportToolbar.tsx       # 图表悬浮工具栏
      utils/
        volcanoProcessor.ts     # 核心数据处理
        fileParser.ts           # CSV/TSV/XLSX 解析
        plotlyConfig.ts         # Plotly layout 配置生成
      hooks/
        useVolcanoData.ts       # 数据处理的自定义 hook
        useDebounce.ts          # debounce hook
      types/
        volcano.ts              # TypeScript 类型定义
      data/
        sampleData.ts           # 示例 DEG 数据
```

## 九、验收标准

- [ ] 上传 CSV 后 3 秒内完成解析并渲染图表
- [ ] 修改任意参数后 300ms 内图表更新
- [ ] 暗黑模式下图表文字/背景/网格线正确切换
- [ ] 导出 PNG/SVG 分辨率清晰，包含完整图例
- [ ] 自定义基因标注支持 50+ 基因同时标注不卡顿
- [ ] 移动端布局自适应，参数面板可正常折叠
- [ ] 示例数据一键加载后可直接体验全部功能
```

---

## 七、实施优先级建议

| 阶段 | 内容 | 预计工时 |
|------|------|----------|
| **Phase 1** | 基础布局 + 数据上传 + 列映射 + 基础 Plotly 渲染 | 2 天 |
| **Phase 2** | 参数面板（阈值、颜色、样式）+ 实时联动 | 1.5 天 |
| **Phase 3** | 基因搜索 + 标注系统 + 右侧基因面板 | 1.5 天 |
| **Phase 4** | 导出功能 + 暗黑模式 + 性能优化 | 1 天 |
| **Phase 5** | 示例数据 + 错误处理 + 移动端适配 | 1 天 |

**总计：约 7 个工作日**

---

*文档生成时间：2026-07-06*  
*版本：v1.0*  
*状态：待开发*
