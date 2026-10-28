# CC 提示词：基因表达矩阵 Explorer 工具实现

> 请在阅读本提示词的同时，参考《OmicHub 生信工具箱 · 前端工具设计规范》(tools_design.md) 和上面的 design.md 设计文档。火山图(VolcanoPlotView.vue + volcanoProcessor.ts)为首选样板代码，优先复用其模式。

---

## 任务概述

为 OmicHub 平台的「生信工具箱」新增一个**基因表达矩阵 Explorer**工具。用户上传基因表达矩阵后，平台使用 Plotly 动态可视化展示：PCA 降维散点图、样本基因表达 Boxplot、基因方差分布 Boxplot，三图以 Plotly subplots 纵向拼接为一图。

---

## Step 1: 创建处理器 (geneExpressionProcessor.ts)

路径：`frontend/src/utils/geneExpressionProcessor.ts`

这是一个**纯函数模块，不持有状态、不依赖 Vue**。所有数据处理、PCA计算、Plotly图表配置生成都在这里。

### 1.1 必须实现的函数

```typescript
// === 解析 ===
export function parseExpressionMatrix(text: string, delimiter: 'auto' | 'comma' | 'tab' = 'auto'): ExpressionMatrix
// - 自动/手动检测分隔符，解析CSV/TSV
// - 第一列为基因ID(gene_id列名)，后续列为样本表达值
// - 数值为空字符串或"NA"时视为NaN，提醒message.warning

export function parseGroupMapping(text: string): GroupMapping[]
// - 解析样本分组表，两列：sample, group

export function autoDetectDelimiter(text: string): string
// - 取前5行，统计逗号和制表符数量，多的那个为分隔符

// === 计算 ===
export function computePCA(matrix: ExpressionMatrix, nComponents = 2): PCAResult
// - 对转置后的矩阵(样本×基因)进行中心化
// - 计算协方差矩阵
// - 使用幂迭代法求前nComponents个特征值/特征向量
// - 返回投影坐标和方差贡献率
// 注意：这是原生JS实现，不引入外部数学库。样本量通常在10-200之间，完全够用。

export function computeGeneVariances(matrix: ExpressionMatrix): number[]
// - 计算每个基因跨样本的方差

export function applyLogTransform(matrix: ExpressionMatrix): ExpressionMatrix
// - 对表达值做 log2(x + 1) 变换，返回新矩阵

export function getSampleGroup(sample: string, groups: GroupMapping[]): string | undefined
// - 查找样本对应的分组

// === 图表配置生成 (核心) ===
export function buildExplorerFigure(
  processed: ProcessedData,
  config: ExplorerConfig,
  isDark: boolean
): { data: Plotly.Data[]; layout: Plotly.Layout; config: Plotly.Config }
// 这是最重要的函数。生成三图拼接的Plotly figure：
// - Subplots布局: 3行1列，使用 'domain' 或 subplot axis 方式拼接
// - Row1: PCA PC1 vs PC2 散点图。xaxis/yaxis 为 'x'/'y'
//   - 点按分组着色(无分组则统一色)
//   - 悬停显示样本名+PC坐标+方差贡献率
//   - 标题: "PCA: PC1 vs PC2"
// - Row2: 样本基因表达 Boxplot。xaxis2/yaxis2 绑定到 'x2'/'y2'
//   - 每个样本一个box，按分组着色
//   - 若 config.boxplotMode === 'top20'，只显示方差Top20的样本
//   - 标题: "Sample Expression Distribution"
// - Row3: 基因方差分布 Boxplot / Histogram。xaxis3/yaxis3 绑定到 'x3'/'y3'
//   - 展示基因方差的分布情况
//   - 标题: "Gene Variance Distribution"
// 
// Layout关键设置:
// - grid: { rows: 3, columns: 1, pattern: 'independent' }
// - 每个subplot高度比例约 0.33
// - 使用统一的color palette(Plotly内置的Set1/Set2/Set3等)
// - 根据isDark切换背景色/字体色
// - margin: { t: 40, r: 30, b: 40, l: 60 }

// === 辅助 ===
export function genSampleData(): { matrixText: string; groupText: string }
// - 生成20基因×8样本的模拟数据(Treatment vs Control)

export function getColorPalette(scheme: string, isDark: boolean): string[]
// - 返回Plotly内置配色数组
```

### 1.2 核心算法提示 (PCA)

用幂迭代法求特征向量(样本量小，足够快)：

```typescript
function powerIteration(matrix: number[][], n: number): { eigenvalues: number[]; eigenvectors: number[][] } {
  // matrix 是 n_samples × n_samples 的协方差矩阵
  // 返回前 n 个特征值和对应的特征向量
  // 步骤：
  // 1. 随机初始化向量 b
  // 2. 迭代: b = A * b; b = b / ||b||
  // 3. 收敛后得到最大特征值对应的特征向量
  // 4. 用deflation求下一个
}
```

---

## Step 2: 创建视图 (GeneExpressionExplorerView.vue)

路径：`frontend/src/views/BioTools/GeneExpressionExplorerView.vue`

### 2.1 模板结构

```vue
<template>
  <div class="gene-expression-explorer-page">
    <!-- Toolbar -->
    <div class="page-toolbar">
      <NButton text @click="router.push('/tools')">
        <template #icon><NIcon :size="18"><ArrowBackOutline /></NIcon></template>
        返回工具箱
      </NButton>
      <h1 class="page-title">基因表达矩阵 Explorer</h1>
      <NButton size="small" quaternary @click="loadSample">
        <template #icon><NIcon><SparklesOutline /></NIcon></template>
        示例数据
      </NButton>
      <NButton size="small" type="primary" :loading="processing" @click="generatePlot">
        <template #icon><NIcon><BarChartOutline /></NIcon></template>
        生成图表
      </NButton>
    </div>

    <!-- 两栏布局 -->
    <div class="gene-expression-explorer-layout">
      <!-- 左：参数面板 -->
      <aside class="param-panel">
        <NCollapse :default-expanded-names="['data-input', 'chart-params']">
          <!-- 数据输入 -->
          <NCollapseItem title="数据输入" name="data-input">
            <NSpace vertical>
              <NUpload 
                :default-upload="false" 
                :max="1" 
                accept=".csv,.tsv,.txt"
                @change="handleMatrixUpload"
              >
                <NButton size="small">上传表达矩阵</NButton>
              </NUpload>
              
              <NSelect 
                v-model:value="delimiter" 
                :options="delimiterOptions" 
                size="small" 
                placeholder="分隔符"
              />
              
              <NUpload 
                :default-upload="false" 
                :max="1" 
                accept=".csv,.tsv"
                @change="handleGroupUpload"
              >
                <NButton size="small">上传分组表(可选)</NButton>
              </NUpload>
            </NSpace>
          </NCollapseItem>

          <!-- 图表参数 -->
          <NCollapseItem title="图表参数" name="chart-params">
            <NSpace vertical>
              <NFlex justify="space-between" align="center">
                <span>PCA点大小</span>
                <NInputNumber v-model:value="config.pointSize" :min="3" :max="30" :step="1" size="small" style="width: 100px" />
              </NFlex>
              <NFlex justify="space-between" align="center">
                <span>透明度</span>
                <NInputNumber v-model:value="config.pointOpacity" :min="0.1" :max="1" :step="0.1" size="small" style="width: 100px" />
              </NFlex>
              <NFlex justify="space-between" align="center">
                <span>箱线图</span>
                <NSelect v-model:value="config.boxplotMode" :options="boxplotOptions" size="small" style="width: 120px" />
              </NFlex>
              <NFlex justify="space-between" align="center">
                <span>配色</span>
                <NSelect v-model:value="config.colorScheme" :options="colorSchemeOptions" size="small" style="width: 120px" />
              </NFlex>
              <NFlex justify="space-between" align="center">
                <span>显示离群点</span>
                <NSwitch v-model:value="config.showOutliers" size="small" />
              </NFlex>
              <NFlex justify="space-between" align="center">
                <span>Log2变换</span>
                <NSwitch v-model:value="config.logTransform" size="small" />
              </NFlex>
            </NSpace>
          </NCollapseItem>

          <!-- 显示控制 -->
          <NCollapseItem title="显示控制" name="display-control">
            <NSpace vertical>
              <NFlex justify="space-between" align="center">
                <span>PCA图</span>
                <NSwitch v-model:value="config.showPCA" size="small" />
              </NFlex>
              <NFlex justify="space-between" align="center">
                <span>表达箱线图</span>
                <NSwitch v-model:value="config.showExpression" size="small" />
              </NFlex>
              <NFlex justify="space-between" align="center">
                <span>方差图</span>
                <NSwitch v-model:value="config.showVariance" size="small" />
              </NFlex>
              <NDivider style="margin: 8px 0" />
              <NFlex justify="space-between" align="center">
                <span>导出DPI</span>
                <NSelect v-model:value="exportDpi" :options="dpiOptions" size="small" style="width: 100px" />
              </NFlex>
              <NFlex gap="small">
                <NButton size="tiny" secondary @click="exportImage('png')">PNG</NButton>
                <NButton size="tiny" secondary @click="exportImage('svg')">SVG</NButton>
              </NFlex>
            </NSpace>
          </NCollapseItem>
        </NCollapse>
      </aside>

      <!-- 右：图表工作区 -->
      <main class="work-area">
        <div class="plot-card">
          <div v-if="!hasData" class="empty-state">
            <NEmpty description="请上传表达矩阵或加载示例数据">
              <template #icon><NIcon :size="48"><GridOutline /></NIcon></template>
            </NEmpty>
          </div>
          <NSpin v-else-if="processing" description="计算中..." />
          <div v-show="hasData && !processing" id="gene-expression-explorer-plot" class="plot-container" />
        </div>
      </main>
    </div>
  </div>
</template>
```

### 2.2 Script 结构

```vue
<script setup lang="ts">
import { ref, reactive, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useMessage } from 'naive-ui'
import * as Plotly from 'plotly.js-dist-min'
import { useThemeStore } from '@/stores/theme'
import {
  type ExpressionMatrix, type GroupMapping, type ProcessedData,
  type ExplorerConfig, type PCAResult,
  DEFAULT_CONFIG,
  parseExpressionMatrix, parseGroupMapping, autoDetectDelimiter,
  computePCA, computeGeneVariances, applyLogTransform, getSampleGroup,
  buildExplorerFigure, genSampleData,
} from '@/utils/geneExpressionProcessor'

const EXPLORE_PLOT_ID = 'gene-expression-explorer-plot'
const router = useRouter()
const message = useMessage()
const themeStore = useThemeStore()
const isDark = computed(() => themeStore.isDark)

// === 状态 ===
const matrix = ref<ExpressionMatrix | null>(null)
const groups = ref<GroupMapping[]>([])
const processed = ref<ProcessedData | null>(null)
const config = reactive<ExplorerConfig>({ ...DEFAULT_CONFIG })
const delimiter = ref<'auto' | 'comma' | 'tab'>('auto')
const processing = ref(false)
const hasData = computed(() => matrix.value !== null)
const exportDpi = ref(300)

// === 选项数据 ===
const delimiterOptions = [
  { label: '自动检测', value: 'auto' },
  { label: '逗号', value: 'comma' },
  { label: '制表符', value: 'tab' },
]
const boxplotOptions = [
  { label: '全部样本', value: 'all' },
  { label: 'Top20方差', value: 'top20' },
]
const colorSchemeOptions = [
  { label: 'Set2', value: 'Set2' },
  { label: 'Set1', value: 'Set1' },
  { label: 'Set3', value: 'Set3' },
  { label: 'Pastel1', value: 'Pastel1' },
  { label: 'Dark24', value: 'Dark24' },
]
const dpiOptions = [
  { label: '300', value: 300 },
  { label: '600', value: 600 },
  { label: '1000', value: 1000 },
]

// === 文件上传处理 ===
function handleMatrixUpload({ file }: { file: UploadFileInfo }) {
  const reader = new FileReader()
  reader.onload = (e) => {
    const text = e.target?.result as string
    const d = delimiter.value === 'auto' ? autoDetectDelimiter(text) : delimiter.value
    try {
      matrix.value = parseExpressionMatrix(text, delimiter.value)
      message.success(`成功加载 ${matrix.value.geneIds.length} 个基因 × ${matrix.value.sampleNames.length} 个样本`)
      scheduleGenerate()
    } catch (err: any) {
      message.error('解析表达矩阵失败: ' + err.message)
    }
  }
  reader.readAsText(file.file as File)
}

function handleGroupUpload({ file }: { file: UploadFileInfo }) {
  const reader = new FileReader()
  reader.onload = (e) => {
    const text = e.target?.result as string
    try {
      groups.value = parseGroupMapping(text)
      message.success(`成功加载 ${groups.value.length} 个样本分组`)
      scheduleGenerate()
    } catch (err: any) {
      message.error('解析分组表失败: ' + err.message)
    }
  }
  reader.readAsText(file.file as File)
}

// === 核心流程 ===
async function generatePlot() {
  if (!matrix.value) {
    message.warning('请先上传表达矩阵')
    return
  }
  processing.value = true
  
  try {
    // 1. 数据预处理
    let workingMatrix = config.logTransform ? applyLogTransform(matrix.value) : matrix.value
    
    // 2. 计算
    const pca = computePCA(workingMatrix, 2)
    const geneVariances = computeGeneVariances(workingMatrix)
    
    processed.value = {
      matrix: workingMatrix,
      groups: groups.value,
      pca,
      geneVariances,
      sampleMedians: workingMatrix.sampleNames.map((_, i) => {
        const vals = workingMatrix.data.map(row => row[i]).filter(v => !isNaN(v))
        vals.sort((a, b) => a - b)
        return vals[Math.floor(vals.length / 2)]
      }),
    }
    
    // 3. 渲染
    await renderPlot()
  } catch (err: any) {
    message.error('计算失败: ' + err.message)
  } finally {
    processing.value = false
  }
}

async function renderPlot() {
  if (!processed.value) return
  const container = document.getElementById(EXPLORE_PLOT_ID)
  if (!container) return
  
  const figure = buildExplorerFigure(processed.value, config, isDark.value)
  await Plotly.react(container, figure.data, figure.layout, figure.config)
}

// === debounce ===
let debounceTimer: ReturnType<typeof setTimeout> | null = null
function scheduleGenerate() {
  if (debounceTimer) clearTimeout(debounceTimer)
  debounceTimer = setTimeout(generatePlot, 300)
}

// === 参数监听 ===
watch(() => [
  config.pointSize, config.pointOpacity, config.boxplotMode,
  config.colorScheme, config.showOutliers, config.logTransform,
  config.showPCA, config.showExpression, config.showVariance,
], scheduleGenerate, { deep: false })

watch(isDark, () => renderPlot())

// === 导出 ===
function exportImage(format: 'png' | 'svg') {
  const container = document.getElementById(EXPLORE_PLOT_ID)
  if (!container) return
  const scale = format === 'png' ? exportDpi.value / 96 : 1
  Plotly.downloadImage(container, {
    format,
    filename: `gene_expression_explorer_${formatTimestamp()}_${exportDpi.value}dpi`,
    scale,
  } as any)
}

function formatTimestamp(): string {
  const d = new Date()
  return `${d.getFullYear()}${String(d.getMonth()+1).padStart(2,'0')}${String(d.getDate()).padStart(2,'0')}_${String(d.getHours()).padStart(2,'0')}${String(d.getMinutes()).padStart(2,'0')}`
}

// === 示例数据 ===
function loadSample() {
  const { matrixText, groupText } = genSampleData()
  matrix.value = parseExpressionMatrix(matrixText, 'comma')
  groups.value = parseGroupMapping(groupText)
  delimiter.value = 'comma'
  message.info('已加载示例数据(20基因×8样本)')
  generatePlot()
}

// === 生命周期 ===
onMounted(() => loadSample())

onUnmounted(() => {
  if (debounceTimer) clearTimeout(debounceTimer)
  const el = document.getElementById(EXPLORE_PLOT_ID)
  if (el) Plotly.purge(el)
})
</script>
```

### 2.3 Style

```vue
<style scoped>
.gene-expression-explorer-page {
  padding: 16px;
  min-height: 100%;
}
.page-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
}
.page-title {
  font-size: 20px;
  font-weight: 600;
  color: var(--neutral-text-1, #1d2129);
  margin: 0;
  flex: 1;
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
.work-area {
  min-width: 0;
}
.plot-card {
  position: relative;
  background: var(--neutral-card, #fff);
  border: 1px solid var(--neutral-border, #e5e6eb);
  border-radius: 12px;
  padding: 8px;
  min-height: 720px;
}
.plot-container {
  width: 100%;
  height: 780px;
}
.empty-state {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 540px;
}

@media (max-width: 1200px) {
  .gene-expression-explorer-layout {
    grid-template-columns: 1fr;
  }
  .param-panel {
    max-height: none;
  }
}
</style>
```

---

## Step 3: 注册工具

### 3.1 tool_configs/tools_setting.yaml

在 `tools` 列表中追加(保持 order 递增)：

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

### 3.2 router/index.ts

在 `DefaultLayout` 的 children 中追加：

```ts
{
  path: 'tools/gene-expression-explorer',
  name: 'tools-gene-expression-explorer',
  component: () => import('@/views/BioTools/GeneExpressionExplorerView.vue'),
  meta: { title: '基因表达矩阵 Explorer', requiresAuth: true },
}
```

### 3.3 ToolsHubView.vue

在 `ICON_MAP` 中导入并注册 `GridOutline`：

```ts
import { GridOutline } from '@vicons/ionicons5'

const ICON_MAP: Record<string, Component> = {
  // ... existing icons
  GridOutline,
}
```

---

## Step 4: 关键实现注意事项

### 4.1 Plotly Subplots 拼接方式

使用 `Plotly` 的 `make_subplots` 等效方式，在 layout 中定义 grid：

```typescript
layout: {
  grid: { rows: 3, columns: 1, pattern: 'independent' },
  // Row1: PCA → xaxis/yaxis (默认)
  // Row2: Expression Boxplot → xaxis2/yaxis2
  // Row3: Variance → xaxis3/yaxis3
  xaxis2: { anchor: 'y2', title: 'Sample' },
  yaxis2: { anchor: 'x2', title: 'Expression Value' },
  xaxis3: { anchor: 'y3', title: 'Gene Rank' },
  yaxis3: { anchor: 'x3', title: 'Variance' },
}
```

每个 trace 通过 `xaxis: 'x2', yaxis: 'y2'` 等属性绑定到对应 subplot。

### 4.2 PCA 算法

必须在 JS 中原生实现，不引入 numeric.js 等外部依赖。样本量通常 < 200，幂迭代法足够：

```typescript
function matMul(a: number[][], b: number[][]): number[][]
function transpose(a: number[][]): number[][]
function normalize(v: number[]): number[]
function dotProduct(a: number[], b: number[]): number
function powerIteration(A: number[][], nComp: number): { values: number[]; vectors: number[][] }
```

### 4.3 Boxplot 数据格式

Plotly boxplot 可以直接接收 y 值数组：

```typescript
// 样本表达箱线图
type: 'box',
y: [/* 某个样本的所有基因表达值 */],
name: 'Sample_A',
xaxis: 'x2',
yaxis: 'y2',
```

### 4.4 分组着色

如果有分组信息，PCA 散点和表达箱线图都按分组着色：

```typescript
// 获取每个样本的颜色
const sampleColors = samples.map(s => {
  const g = getSampleGroup(s, groups)
  return g ? colorMap[g] : '#999'
})
```

---

## Step 5: 验证清单

完成后请逐项确认：

- [ ] `geneExpressionProcessor.ts` 所有函数导出正确，TypeScript 类型完整
- [ ] `GeneExpressionExplorerView.vue` 编译无错误，所有 Naive UI 组件正确导入
- [ ] 进入页面自动加载示例数据，三图正确渲染
- [ ] 上传新文件后自动解析并重新生成图表
- [ ] 参数调整(点大小/透明度/配色)有 300ms debounce 自动更新
- [ ] 三个显示控制开关(PCA/表达/方差)能正确显示/隐藏对应 subplot
- [ ] 暗黑模式切换图表背景色正确变化
- [ ] PNG/SVG 导出正常工作，文件名含时间戳
- [ ] `vue-tsc` 严格类型检查通过
- [ ] 构建后 `docker restart omichub-nginx` 能正常访问

---

## 参考文件

| 文件 | 路径 | 作用 |
|------|------|------|
| 设计规范 | `tools_design.md` | 布局/样式/交互的通用规范 |
| 设计文档 | `design.md` | 本工具的详细设计说明 |
| 首选样板 | `VolcanoPlotView.vue` + `volcanoProcessor.ts` | 三栏布局、Plotly暗黑模式、导出 |
| 分组参考 | `KeggEnrichmentView.vue` | 两栏布局(参数+结果) |
