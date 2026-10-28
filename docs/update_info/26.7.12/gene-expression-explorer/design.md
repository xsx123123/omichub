# OmicHub · 基因表达矩阵 Explorer 工具 · 设计与实现文档

> 功能：用户上传基因表达矩阵 → 平台自动生成 PCA 散点图、基因表达箱线图、样本方差箱线图，三图以 Plotly subplots 拼接展示，支持动态交互与导出。
>
> 参照文档：《OmicHub 生信工具箱 · 前端工具设计规范》(tools_design.md)
>
> 参考实现：火山图(`VolcanoPlotView.vue` + `volcanoProcessor.ts`) 为首选样板
>
> 版本: 2026-07-12

---

## 一、功能概述

| 功能点 | 说明 |
|--------|------|
| **数据输入** | 用户上传基因表达矩阵(CSV/TSV)，行为基因，列为样本，支持表头第一列为基因名 |
| **PCA 分析** | 对样本进行 PCA 降维，展示 PC1 vs PC2 散点图，悬停显示样本名与方差贡献率 |
| **基因表达分布** | 每个样本的基因表达量 boxplot，支持按分组着色 |
| **基因方差分布** | 每个基因的跨样本表达方差 boxplot，展示高变异/低变异基因分布 |
| **三图拼接** | 使用 Plotly subplots 将上述三图纵向拼接为一图，支持联动交互 |
| **分组着色** | 用户可上传/粘贴分组信息(可选)，样本按分组着色 |

---

## 二、数据格式

### 2.1 基因表达矩阵(必填)

```
gene_id,Sample_A,Sample_B,Sample_C,Sample_D
GENE001,12.5,8.3,15.2,9.1
GENE002,3.1,2.8,4.5,3.9
GENE003,0.0,1.2,0.5,2.1
...
```

- 第一列:基因 ID(gene_id)
- 后续列:样本表达值(TPM/FPKM/Count，数值型)
- 支持 CSV(逗号分隔)和 TSV(制表符分隔)，自动检测
- 表头必须有，基因名可为任意字符串

### 2.2 样本分组表(可选)

```
sample,group
Sample_A,Treatment
Sample_B,Treatment
Sample_C,Control
Sample_D,Control
```

- 两列：sample(样本名，须与表达矩阵列名一致)、group(分组标签)
- 上传后 PCA 散点与表达箱线图按分组着色

---

## 三、文件与目录组织

```
frontend/src/
├── views/BioTools/
│   └── GeneExpressionExplorerView.vue     # 工具主页面
├── utils/
│   └── geneExpressionProcessor.ts         # 数据解析、PCA计算、图表配置生成
├── router/index.ts                        # 新增 tools/gene-expression-explorer 路由
└── types/tools.ts                         # ToolItem 类型(不变)

tool_configs/
├── tools_setting.yaml                     # 追加 gene-expression-explorer 注册项
```

### 命名对照表

| 项目 | 值 |
|------|-----|
| key | `gene-expression-explorer` |
| 视图文件 | `GeneExpressionExplorerView.vue` |
| 处理器文件 | `geneExpressionProcessor.ts` |
| 路由 path | `tools/gene-expression-explorer` |
| 路由 name | `tools-gene-expression-explorer` |
| 根 class | `gene-expression-explorer-page` |
| 布局 class | `gene-expression-explorer-layout` |

---

## 四、注册表配置

### 4.1 tools_setting.yaml

```yaml
- key: "gene-expression-explorer"
  title: "基因表达矩阵 Explorer"
  description: "上传基因表达矩阵，一键生成 PCA 降维、样本表达分布与基因方差分析三图联动可视化"
  icon: "GridOutline"
  gradient: "linear-gradient(135deg, #722ED1 0%, #165DFF 100%)"
  route: "/tools/gene-expression-explorer"
  group: "visualization"
  enabled: true
  order: 50
  config_dir: ""
```

### 4.2 router/index.ts

```ts
{
  path: 'tools/gene-expression-explorer',
  name: 'tools-gene-expression-explorer',
  component: () => import('@/views/BioTools/GeneExpressionExplorerView.vue'),
  meta: { title: '基因表达矩阵 Explorer', requiresAuth: true },
}
```

### 4.3 ToolsHubView.vue ICON_MAP

```ts
import { GridOutline } from '@vicons/ionicons5'

const ICON_MAP: Record<string, Component> = {
  // ... 已有图标
  GridOutline, // ← 基因表达矩阵 Explorer
}
```

---

## 五、页面布局

### 5.1 布局模式

采用**两栏布局**（左参数 + 右工作区），无右侧辅助面板。

```
┌──────────────────────────────────────────────────────────────┐
│  ← 返回工具箱    基因表达矩阵 Explorer    [示例数据] [生成图表] │  ← toolbar
├──────────────┬───────────────────────────────────────────────┤
│              │                                                │
│   参数面板    │           Plotly 图表工作区                      │
│   280px      │           (三图 subplots 拼接)                  │
│              │                                                │
│  ┌────────┐  │           ┌─────────────────────────────┐     │
│  │数据输入 │  │           │    PCA 散点图 (PC1 vs PC2)  │     │
│  │分组设置 │  │           ├─────────────────────────────┤     │
│  │图表参数 │  │           │    样本基因表达 Boxplot      │     │
│  │显示控制 │  │           ├─────────────────────────────┤     │
│  └────────┘  │           │    基因方差分布 Boxplot      │     │
│              │           └─────────────────────────────┘     │
└──────────────┴───────────────────────────────────────────────┘
```

### 5.2 CSS 骨架

```css
.gene-expression-explorer-page {
  padding: 16px;
  min-height: 100%;
}
.gene-expression-explorer-layout {
  display: grid;
  grid-template-columns: 300px 1fr;
  gap: 16px;
  align-items: start;
}
.param-panel {
  background: var(--neutral-card, #fff);
  border: 1px solid var(--neutral-border, #e5e6eb);
  border-radius: 12px;
  padding: 12px;
  max-height: calc(100vh - 120px);
  overflow-y: auto;
}
.plot-card {
  position: relative;
  background: var(--neutral-card, #fff);
  border: 1px solid var(--neutral-border, #e5e6eb);
  border-radius: 12px;
  padding: 8px;
  min-height: 720px;  /* 三图拼接，需要更大高度 */
}
.plot-container {
  width: 100%;
  height: 780px;
}
```

### 5.3 响应式

```css
@media (max-width: 1200px) {
  .gene-expression-explorer-layout { grid-template-columns: 1fr; }
  .param-panel { max-height: none; }
}
```

---

## 六、参数面板设计

使用 `NCollapse` 分组折叠，默认展开「数据输入」。

### 6.1 数据输入 (NCollapseItem)

| 参数 | 组件 | 默认值 | 说明 |
|------|------|--------|------|
| 表达矩阵文件 | `NUpload` | — | `accept: '.csv,.tsv,.txt'`, `:max="1"`, `:default-upload="false"` |
| 分隔符 | `NSelect` | `'auto'` | options: `auto`(自动检测), `comma`(逗号), `tab`(制表符) |
| 分组文件 | `NUpload` | — | 可选，`accept: '.csv,.tsv'`, `:max="1"` |
| 示例数据 | `NButton` (text) | — | 点击加载内置示例数据 |

### 6.2 图表参数 (NCollapseItem)

| 参数 | 组件 | 默认值 | 说明 |
|------|------|--------|------|
| PCA 点大小 | `NInputNumber` | 10 | 范围 3-30 |
| PCA 透明度 | `NInputNumber` | 0.7 | 范围 0.1-1.0, step 0.1 |
| 箱线图展示 | `NSelect` | `'all'` | `'all'`全部样本、`'top20'`方差Top20样本 |
| 调色方案 | `NSelect` | `'Set2'` | Plotly 内置配色: Set1/Set2/Set3/Pastel1/Dark24 |
| 显示离群点 | `NSwitch` | `true` | boxplot 是否显示 outlier 点 |
| 对数变换 | `NSwitch` | `false` | 对表达值做 log2(x+1) 变换 |

### 6.3 显示控制 (NCollapseItem)

| 参数 | 组件 | 默认值 | 说明 |
|------|------|--------|------|
| 显示 PCA | `NSwitch` | `true` | 切换 PCA subplot 显示 |
| 显示表达箱线图 | `NSwitch` | `true` | 切换表达分布 subplot |
| 显示方差箱线图 | `NSwitch` | `true` | 切换方差分布 subplot |
| 导出 DPI | `NSelect` | `300` | options: 300, 600, 1000 |
| 导出格式 | `NButtonGroup` | — | PNG / SVG 导出按钮 |

---

## 七、处理器模块 (geneExpressionProcessor.ts)

### 7.1 类型定义

```typescript
// ===== 类型 =====
export interface ExpressionMatrix {
  geneIds: string[]          // 基因名列表
  sampleNames: string[]      // 样本名列
  data: number[][]           // 二维数值矩阵 [geneIdx][sampleIdx]
}

export interface GroupMapping {
  sample: string
  group: string
}

export interface PCAResult {
  scores: number[][]         // 样本得分 [sampleIdx][PC]
  explainedVariance: number[] // 各主成分方差贡献率
  pc1: number[]              // PC1 坐标
  pc2: number[]              // PC2 坐标
}

export interface ProcessedData {
  matrix: ExpressionMatrix
  groups: GroupMapping[]
  pca: PCAResult
  geneVariances: number[]    // 每个基因的跨样本方差
  sampleMedians: number[]    // 每个样本的中位数表达
}

export interface ExplorerConfig {
  pointSize: number
  pointOpacity: number
  boxplotMode: 'all' | 'top20'
  colorScheme: string
  showOutliers: boolean
  logTransform: boolean
  showPCA: boolean
  showExpression: boolean
  showVariance: boolean
}

export const DEFAULT_CONFIG: ExplorerConfig = {
  pointSize: 10,
  pointOpacity: 0.7,
  boxplotMode: 'all',
  colorScheme: 'Set2',
  showOutliers: true,
  logTransform: false,
  showPCA: true,
  showExpression: true,
  showVariance: true,
}
```

### 7.2 纯函数接口

```typescript
// ===== 解析 =====
export function parseExpressionMatrix(text: string, delimiter?: 'auto' | 'comma' | 'tab'): ExpressionMatrix
export function parseGroupMapping(text: string): GroupMapping[]
export function autoDetectDelimiter(text: string): string

// ===== 计算 =====
export function computePCA(matrix: ExpressionMatrix, nComponents?: number): PCAResult
export function computeGeneVariances(matrix: ExpressionMatrix): number[]
export function applyLogTransform(matrix: ExpressionMatrix): ExpressionMatrix
export function getSampleGroup(sample: string, groups: GroupMapping[]): string

// ===== 图表配置生成 =====
export function buildExplorerFigure(
  processed: ProcessedData,
  config: ExplorerConfig,
  isDark: boolean
): Plotly.Figure

// ===== 辅助 =====
export function genSampleData(): { matrix: string; groups: string }
export function formatVariance(n: number): string
```

### 7.3 PCA 计算算法

使用简单的协方差矩阵特征值分解(JavaScript 原生实现，不依赖外部库)：

```
1. 输入矩阵 X: n_genes × n_samples
2. 中心化: 每行减去该行均值
3. 计算协方差矩阵: C = X_centered^T · X_centered / (n_genes - 1)
4. 对 C 做特征值分解，取前2大特征值对应的特征向量
5. 投影: scores = X_centered · eigenvectors
6. 计算 explained variance ratio
```

> 注：样本量通常不大(几十到几百)，JS 原生计算足够快。若后续样本量大可考虑引入 numeric.js。

### 7.4 Plotly Subplots 布局

三图纵向拼接：`subplots: [[{}], [{}], [{}]]`，即 3 行 1 列。

```
Row 1 (0.35): PCA Scatter PC1 vs PC2
Row 2 (0.35): Sample Expression Boxplot  
Row 3 (0.30): Gene Variance Boxplot
```

共享 x 轴标签优化：PCA 图为样本坐标轴，箱线图为样本名/基因名。

---

## 八、视图交互流程

### 8.1 数据流

```
用户上传表达矩阵 ──→ parseExpressionMatrix() ──→ matrix (reactive)
用户上传分组表    ──→ parseGroupMapping()    ──→ groups (reactive)
                                                        │
                                                        ▼
用户点击「生成图表」──→ computePCA() + computeGeneVariances()
                                                        │
                                                        ▼
                                            buildExplorerFigure()
                                                        │
                                                        ▼
                                              Plotly.react(container, figure)
```

### 8.2 生命周期

```typescript
onMounted(() => {
  loadSample()  // 自动载入示例数据并渲染
})

onUnmounted(() => {
  if (debounceTimer) clearTimeout(debounceTimer)
  const el = document.getElementById(EXPLORE_PLOT_ID)
  if (el) Plotly.purge(el)
})
```

### 8.3 自动更新

参数变化 300ms debounce 触发重渲染：

```typescript
watch(() => [
  config.pointSize, config.pointOpacity, config.boxplotMode,
  config.colorScheme, config.showOutliers, config.logTransform,
  config.showPCA, config.showExpression, config.showVariance
], scheduleRender, { deep: false })
```

---

## 九、示例数据

内置 20 个基因 × 8 个样本(4 Treatment + 4 Control)的模拟数据：

```
gene_id,Treat_1,Treat_2,Treat_3,Treat_4,Ctrl_1,Ctrl_2,Ctrl_3,Ctrl_4
GENE001,15.2,14.8,16.1,15.5,5.3,4.9,5.8,5.1
GENE002,2.1,2.5,1.9,2.3,8.7,9.1,8.5,8.9
...
```

分组数据：
```
sample,group
Treat_1,Treatment
Treat_2,Treatment
...
Ctrl_1,Control
...
```

---

## 十、暗黑模式适配

```typescript
const themeStore = useThemeStore()
const isDark = computed(() => themeStore.isDark)
watch(isDark, () => renderPlot())

// buildExplorerFigure 内部根据 isDark 选择：
const darkPalette = {
  paper_bgcolor: '#1a1a2e',
  plot_bgcolor: '#16162a',
  font: { color: '#e0e0e0' },
  gridcolor: '#2a2a4a',
}
const lightPalette = {
  paper_bgcolor: '#ffffff',
  plot_bgcolor: '#fafafa',
  font: { color: '#1d2129' },
  gridcolor: '#e5e6eb',
}
```

---

## 十一、上线 Checklist

- [ ] `tools_setting.yaml` 已注册，`key`/`route`/`icon`/`group`/`order` 正确
- [ ] `router/index.ts` 已加 `tools/gene-expression-explorer` 子路由
- [ ] `GridOutline` 已在 `ToolsHubView.vue` 的 `ICON_MAP` 登记
- [ ] 视图 `GeneExpressionExplorerView.vue`，根 class `gene-expression-explorer-page`
- [ ] 处理器 `geneExpressionProcessor.ts`，纯函数无 Vue 依赖
- [ ] 两栏布局 `grid-template-columns: 300px 1fr`
- [ ] 所有颜色走 CSS 变量，无硬编码
- [ ] 暗黑模式：图表监听 `isDark` 重渲染
- [ ] `onMounted` 载入示例数据
- [ ] 参数变化 300ms debounce
- [ ] 有 `type="primary"` 的「生成图表」按钮
- [ ] `onUnmounted` 清理定时器与 Plotly
- [ ] `npm run build` 通过 (`vue-tsc` 严格检查)
- [ ] 构建后 `docker restart omichub-nginx`
