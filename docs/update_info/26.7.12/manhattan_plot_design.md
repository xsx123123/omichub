# OmicHub 工具箱 · 曼哈顿图(Manhattan Plot)设计文档

> 基于 Plotly.js + Naive UI 的动态交互式曼哈顿图工具，支持图-表联动选择。
> 参考规范: [tools_design.md](../tools_design.md) —— 火山图为首选样板
> 设计日期: 2026-07-12

---

## 一、功能概述

| 特性 | 说明 |
|------|------|
| **核心功能** | 将 GWAS / QTL 分析结果(P值 + 染色体位置)绘制为经典曼哈顿图 |
| **染色体智能识别** | 自动识别 Chr1-22/X/Y/MT 等常见染色体命名，支持自定义染色体列 |
| **双阈值线** | 可配置 suggestive line(建议线,默认 -log10(p)=5) 与 genome-wide line(全基因组线,默认 -log10(p)=8) |
| **图-表联动** | **核心交互**: Plotly 图中框选/点击点后，下方数据表格自动筛选并高亮对应行；表格中点击行，图上对应点高亮放大 |
| **信号点提取** | 一键筛选超出阈值线的显著 SNP，导出为表格/CSV |
| **大数据优化** | >5000 点自动启用 `scattergl`(WebGL)，流畅渲染数十万点 |
| **主题适配** | 亮/暗模式完整支持，图表配色自动切换 |

---

## 二、数据格式

### 2.1 输入文件格式

支持 **CSV / TSV / Excel**，必须包含以下列(列名自动检测，也可手动映射):

| 列 | 说明 | 示例值 | 自动检测关键词 |
|----|------|--------|--------------|
| **SNP** | 变异位点标识 | rs12345, Chr1_12345 | `snp`, `rsid`, `id`, `variant`, `marker` |
| **Chromosome** | 染色体编号 | 1, 2, ..., 22, X, Y | `chr`, `chrom`, `chromosome`, `scaffold` |
| **Position** | 染色体上的物理位置(bp) | 1234567 | `pos`, `position`, `bp`, `coord`, `posi` |
| **P-value** | 关联分析 P 值 | 1.23e-8 | `p`, `pval`, `pvalue`, `p-value`, `p_value` |

### 2.2 可选列

| 列 | 说明 | 自动检测关键词 |
|----|------|--------------|
| **Gene** | 邻近基因 | `gene`, `nearest_gene`, `gene_id` |
| **Effect** | 效应值/Beta | `beta`, `effect`, `b`, `or` |
| **MAF** | 次等位基因频率 | `maf`, `freq`, `eaf` |

### 2.3 示例数据(minimal)

```csv
SNP,Chromosome,Position,P-value
rs12124819,1,776546,0.5342
rs2977670,1,1118275,0.7921
rs143225591,1,1211293,0.1234
rs55727773,1,1479553,0.00000123
rs57570434,1,1505497,0.0456
```

### 2.4 数据加载流程

```
用户上传 CSV/TSV/粘贴数据
  → parseDelimited() 解析为原始行数据
  → autoDetectColumns() 自动匹配列名(支持手动覆盖)
  → validateData() 校验: P值范围(0,1], Position 为正整数, Chromosome 非空
  → 校验失败: message.error() 提示具体行号和错误类型
  → 校验通过: 进入绘图 Pipeline
```

---

## 三、页面布局

### 3.1 布局结构(三栏紧凑)

参考火山图 `VolcanoPlotView.vue` 的三栏布局:

```
┌─────────────────────────────────────────────────────────────────┐
│ [← 返回工具箱]  曼哈顿图绘制              [示例数据] [导出PNG]   │  ← Toolbar
├──────────┬──────────────────────────────────────┬───────────────┤
│          │                                      │               │
│  参数    │         曼哈顿图 (Plotly)             │   统计摘要    │
│  面板    │         -log10(p) vs Chromosome      │               │
│  280px   │         ┌──────────────────────┐     │  · 总SNP数    │
│          │         │  ◆  ◆ ◆  ◆  ◆◆ ◆   │     │  · 超出全基因 │
│ NCollapse│         │   ◆ ◆  ◆  ═══════   │     │    组线数量   │
│          │         │ ◆  ◆◆◆ ◆  threshold │     │  · 超出建议线 │
│ - 数据   │         │ ◆ ◆  ◆  ◆  ◆ ◆ ◆   │     │    数量       │
│ - 阈值   │         │   ◆ ◆  ◆  ◆  ◆ ◆   │     │  · 最高峰值   │
│ - 颜色   │         └──────────────────────┘     │    SNP        │
│ - 坐标轴 │                                      │  · 染色体分布 │
│ - 导出   │         [ 数据表格 (联动区域) ]       │    直方图     │
│          │         NDataTable + 筛选 + 分页     │               │
│          │                                      │               │
└──────────┴──────────────────────────────────────┴───────────────┘
```

### 3.2 布局 CSS

```css
.manhattan-page {
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
.manhattan-layout {
  display: grid;
  grid-template-columns: 280px 1fr 260px;
  gap: 16px;
  align-items: start;
}
.plot-card {
  position: relative;
  background: var(--neutral-card, #fff);
  border: 1px solid var(--neutral-border, #e5e6eb);
  border-radius: 12px;
  padding: 8px;
  min-height: 480px;
}
.plot-container {
  width: 100%;
  height: 480px;
}
.table-card {
  margin-top: 12px;
  background: var(--neutral-card, #fff);
  border: 1px solid var(--neutral-border, #e5e6eb);
  border-radius: 12px;
  padding: 8px;
  max-height: 360px;
  overflow-y: auto;
}
```

### 3.3 响应式

```css
@media (max-width: 1200px) {
  .manhattan-layout { grid-template-columns: 1fr; }
  .param-panel, .side-panel { max-height: none; }
}
@media (max-width: 768px) {
  .manhattan-page { padding: 12px; }
}
```

---

## 四、参数面板(NCollapse 折叠)

### 4.1 数据映射(Data)

```
┌─ 数据映射 ─────────────────────────┐
│ SNP 列      [下拉选择 ▼]           │
│ 染色体列     [下拉选择 ▼]           │
│ 位置列      [下拉选择 ▼]           │
│ P-value 列  [下拉选择 ▼]           │
│ (可选)基因列  [下拉选择 ▼]          │
│ (可选)效应列  [下拉选择 ▼]          │
└────────────────────────────────────┘
```

### 4.2 阈值设置(Thresholds)

```
┌─ 阈值线 ───────────────────────────┐
│ ☑ 显示建议线 (suggestive)          │
│    数值  [ 5.0   ]                 │
│    颜色  [■ #9467BD]               │
│                                    │
│ ☑ 显示全基因组线 (genome-wide)     │
│    数值  [ 8.0   ]                 │
│    颜色  [■ #E74C3C]               │
│                                    │
│ ─────────────────────────────────  │
│ 说明:                              │
│ · suggestive  = -log10(5e-6) ≈ 5.3 │
│ · genome-wide = -log10(5e-8) ≈ 7.3 │
└────────────────────────────────────┘
```

### 4.3 配色与样式(Style)

```
┌─ 配色与样式 ───────────────────────┐
│ 染色体配色方案 [经典 ▼]            │
│   · 经典(Chr1=#E74C3C, Chr2=#3498DB...)
│   · 柔和 pastel                    │
│   · 灰度 gray-scale                │
│   · 自定义                          │
│                                    │
│ 信号点颜色  [■ #FF4040]             │
│ (超过 genome-wide 线的点)           │
│                                    │
│ 点大小      [○●○○○] (1-8)         │
│ 点透明度    [○○●○○] (0.3-1.0)      │
│                                    │
│ 显示染色体标签   ☑                 │
│ 显示基因名(悬停) ☑                 │
└────────────────────────────────────┘
```

### 4.4 坐标轴(Axis)

```
┌─ 坐标轴 ───────────────────────────┐
│ Y轴最大値  [自动 ▼] / [ 输入 ]     │
│ Y轴标题    [-log10(P-value)]       │
│ X轴标题    [Chromosome]            │
│ 显示网格线  ☑                      │
└────────────────────────────────────┘
```

### 4.5 导出设置(Export)

```
┌─ 导出设置 ─────────────────────────┐
│ DPI        [1000 ▼] (300/600/1000) │
│ 导出格式   [PNG ▼]  (PNG/SVG)      │
│ 导出表格   [导出CSV ▼]             │
│   · 全部数据                        │
│   · 仅显著点(>genome-wide)          │
│   · 仅建议点(>suggestive)           │
└────────────────────────────────────┘
```

---

## 五、图-表联动设计(核心交互)

### 5.1 联动架构

```
┌─────────────┐      Plotly selected      ┌─────────────┐
│  Plotly 图   │ ────────────────────────→ │  Vue 状态    │
│             │      (box/lasso select)    │  selected   │
│             │                            │  PointIds   │
│             │ ←───────────────────────   │             │
│             │   hover highlight row      │             │
└─────────────┘                            └──────┬──────┘
                                                  │
                    NDataTable 行点击             │  筛选数据
                          │                       │
                          ▼                       ▼
                   ┌─────────────────────────────────┐
                   │        联动数据表格              │
                   │  · 显示 selected PointIds       │
                   │  · 点击行 → 图上点高亮           │
                   │  · 支持排序/筛选/分页            │
                   └─────────────────────────────────┘
```

### 5.2 交互细节

| 方向 | 触发 | 行为 |
|------|------|------|
| **图 → 表** | Plotly `plotly_selected` 事件(box select / lasso) | 表格自动筛选为选中点，选中行高亮 |
| **图 → 表** | Plotly `plotly_click` 事件(单击单点) | 表格滚动到该行并高亮，其他行置灰 |
| **图 → 表** | Plotly `plotly_hover` 事件 | 表格中对应行短暂高亮(预览效果) |
| **表 → 图** | 表格行点击 | Plotly 对应点放大(2x size) + 高亮颜色 + 添加 annotation |
| **表 → 图** | 表格行双击 | 图表自动 zoom 到该点所在染色体区域 |
| **清除选择** | 点击"清除选择"按钮 或 在图上空白处点击 | 表格恢复全部数据，点样式还原 |

### 5.3 Plotly 事件绑定

```typescript
// 在 onMounted / renderPlot 后绑定
Plotly.newPlot(container, data, layout, config).then(() => {
  // 框选 / lasso 选择
  container.on('plotly_selected', (event: any) => {
    const pointIds = event.points?.map((p: any) => p.customdata?.[0]) ?? []
    selectedSnpIds.value = new Set(pointIds)
  })

  // 单击单点
  container.on('plotly_click', (event: any) => {
    const snpId = event.points?.[0]?.customdata?.[0]
    if (snpId) {
      selectedSnpIds.value = new Set([snpId])
      scrollTableToRow(snpId)
    }
  })

  // Hover 预览
  container.on('plotly_hover', (event: any) => {
    const snpId = event.points?.[0]?.customdata?.[0]
    if (snpId) hoveredSnpId.value = snpId
  })
  container.on('plotly_unhover', () => {
    hoveredSnpId.value = null
  })
})
```

### 5.4 表格联动响应

```typescript
// computed: 根据 selectedSnpIds 筛选表格数据
const filteredTableData = computed(() => {
  if (selectedSnpIds.value.size === 0) return tableData.value
  return tableData.value.filter(row => selectedSnpIds.value.has(row.snpId))
})

// 表格行点击 → 图上高亮
function onTableRowClick(row: ManhattanRow) {
  selectedSnpIds.value = new Set([row.snpId])
  highlightPointOnPlot(row.snpId)
}

// 表格行双击 → zoom 到染色体区域
function onTableRowDblClick(row: ManhattanRow) {
  zoomToChromosome(row.chromosome)
}
```

---

## 六、图表配色方案

### 6.1 经典染色体配色(Classic)

交替使用高对比度色彩，确保相邻染色体可区分:

| 染色体 | 颜色 | Hex |
|--------|------|-----|
| Chr1 | 珊瑚红 | #E74C3C |
| Chr2 | 湖蓝 | #3498DB |
| Chr3 | 翠绿 | #2ECC71 |
| Chr4 | 琥珀 | #F39C12 |
| Chr5 | 紫罗兰 | #9B59B6 |
| Chr6 | 青柠 | #1ABC9C |
| Chr7 | 玫红 | #E91E63 |
| Chr8 | 天蓝 | #00BCD4 |
| Chr9 | 金橙 | #FF9800 |
| Chr10 | 靛蓝 | #673AB7 |
| Chr11+ | 循环使用上述颜色 | - |

### 6.2 柔和配色(Pastel)

| 染色体 | 颜色 | Hex |
|--------|------|-----|
| Chr1 | 浅粉 | #FF9AA2 |
| Chr2 | 薄荷 | #B5EAD7 |
| Chr3 | 淡紫 | #C7CEEA |
| Chr4 | 蜜桃 | #FFDAC1 |
| Chr5 | 淡黄 | #FFF5BA |

### 6.3 暗色模式适配

```typescript
function getPlotTheme(isDark: boolean) {
  return isDark ? {
    plot_bgcolor: '#1a1a2e',
    paper_bgcolor: '#1a1a2e',
    font: { color: '#E0E0E0' },
    gridcolor: '#33334d',
    zerolinecolor: '#444466',
  } : {
    plot_bgcolor: '#FAFBFC',
    paper_bgcolor: '#FAFBFC',
    font: { color: '#1d2129' },
    gridcolor: '#E5E6EB',
    zerolinecolor: '#C9CDD4',
  }
}
```

---

## 七、数据处理模块 `manhattanProcessor.ts`

### 7.1 类型定义

```typescript
export interface ManhattanConfig {
  suggestiveLine: number       // 建议线阈值,默认 5.0
  genomeWideLine: number       // 全基因组线阈值,默认 8.0
  showSuggestiveLine: boolean
  showGenomeWideLine: boolean
  colorScheme: 'classic' | 'pastel' | 'grayscale' | 'custom'
  signalColor: string          // 超阈值点颜色
  pointSize: number            // 1-8
  pointOpacity: number         // 0.3-1.0
  showChrLabels: boolean
  showGeneInHover: boolean
  yAxisMax: 'auto' | number
  yAxisTitle: string
  xAxisTitle: string
  showGrid: boolean
}

export interface ColMap {
  snp: string
  chromosome: string
  position: string
  pvalue: string
  gene?: string
  effect?: string
  maf?: string
}

export interface ManhattanRow {
  snpId: string
  chromosome: string | number
  position: number
  pvalue: number
  negLogP: number
  gene?: string
  effect?: number
  maf?: number
  isSignificant: boolean   // > genomeWideLine
  isSuggestive: boolean    // > suggestiveLine
}

export interface ProcessedResult {
  rows: ManhattanRow[]
  stats: ManhattanStats
  chromosomeOrder: (string | number)[]
}

export interface ManhattanStats {
  totalSnpCount: number
  genomeWideCount: number
  suggestiveCount: number
  maxNegLogP: number
  peakSnp: string
  chrDistribution: Record<string, number>
}

export interface PlotlyFigure {
  data: Plotly.Data[]
  layout: Partial<Plotly.Layout>
  config: Partial<Plotly.Config>
}
```

### 7.2 默认值

```typescript
export const DEFAULT_CONFIG: ManhattanConfig = {
  suggestiveLine: 5.0,
  genomeWideLine: 8.0,
  showSuggestiveLine: true,
  showGenomeWideLine: true,
  colorScheme: 'classic',
  signalColor: '#FF4040',
  pointSize: 4,
  pointOpacity: 0.8,
  showChrLabels: true,
  showGeneInHover: true,
  yAxisMax: 'auto',
  yAxisTitle: '-log₁₀(P-value)',
  xAxisTitle: 'Chromosome',
  showGrid: true,
}

export const CHROMOSOME_COLORS: Record<string, string[]> = {
  classic: [
    '#E74C3C', '#3498DB', '#2ECC71', '#F39C12', '#9B59B6',
    '#1ABC9C', '#E91E63', '#00BCD4', '#FF9800', '#673AB7',
  ],
  pastel: [
    '#FF9AA2', '#B5EAD7', '#C7CEEA', '#FFDAC1', '#FFF5BA',
    '#FFB7B2', '#E2F0CB', '#B5EAD7', '#C7CEEA', '#FF9AA2',
  ],
  grayscale: [
    '#333333', '#666666', '#999999', '#BBBBBB', '#555555',
    '#777777', '#444444', '#888888', '#AAAAAA', '#222222',
  ],
}

export const COLUMN_DETECTION_PATTERNS: Record<keyof ColMap, string[]> = {
  snp: ['snp', 'rsid', 'rs', 'id', 'variant', 'marker', 'snpid'],
  chromosome: ['chr', 'chrom', 'chromosome', 'scaffold', 'lg'],
  position: ['pos', 'position', 'bp', 'coord', 'posi', 'location'],
  pvalue: ['p', 'pval', 'pvalue', 'p-value', 'p_value', 'p.value', 'pv'],
  gene: ['gene', 'nearest_gene', 'gene_id', 'nearestgene'],
  effect: ['beta', 'effect', 'b', 'or', 'odds_ratio'],
  maf: ['maf', 'freq', 'eaf', 'frequency'],
}
```

### 7.3 核心函数

```typescript
/**
 * 自动检测列映射
 */
export function autoDetectColumns(headers: string[]): Partial<ColMap> {
  const colMap: Partial<ColMap> = {}
  const lowerHeaders = headers.map(h => h.toLowerCase().trim())

  for (const [field, patterns] of Object.entries(COLUMN_DETECTION_PATTERNS)) {
    for (let i = 0; i < lowerHeaders.length; i++) {
      const h = lowerHeaders[i]
      const match = patterns.some(p => h === p || h.includes(p))
      if (match) {
        colMap[field as keyof ColMap] = headers[i]
        break
      }
    }
  }
  return colMap
}

/**
 * 解析分隔符文本
 */
export function parseDelimited(text: string, filename: string): { headers: string[]; rows: Record<string, any>[] } {
  const delimiter = filename.endsWith('.tsv') || filename.endsWith('.txt') ? '\t' : ','
  const lines = text.trim().split('\n').filter(l => l.trim())
  if (lines.length < 2) throw new Error('文件至少需要包含表头和一行数据')

  const headers = lines[0].split(delimiter).map(h => h.trim().replace(/^"|"$/g, ''))
  const rows = lines.slice(1).map((line, idx) => {
    const values = line.split(delimiter).map(v => v.trim().replace(/^"|"$/g, ''))
    const row: Record<string, any> = {}
    headers.forEach((h, i) => { row[h] = values[i] })
    row._rowIndex = idx + 2  // 用于错误定位
    return row
  })
  return { headers, rows }
}

/**
 * 验证数据
 */
export function validateData(rows: Record<string, any>[], colMap: ColMap): string[] {
  const errors: string[] = []
  rows.forEach((row, i) => {
    const pval = parseFloat(row[colMap.pvalue])
    if (isNaN(pval) || pval <= 0 || pval > 1) {
      errors.push(`第 ${i + 2} 行: P-value "${row[colMap.pvalue]}" 无效(应在 0~1 之间)`)
    }
    const pos = parseInt(row[colMap.position])
    if (isNaN(pos) || pos < 0) {
      errors.push(`第 ${i + 2} 行: Position "${row[colMap.position]}" 无效(应为非负整数)`)
    }
  })
  return errors
}

/**
 * 处理数据 Pipeline
 */
export function processManhattanData(
  rawRows: Record<string, any>[],
  colMap: ColMap,
  config: ManhattanConfig,
): ProcessedResult {
  // 1. 转换为 ManhattanRow
  const rows: ManhattanRow[] = rawRows.map(row => {
    const pvalue = parseFloat(row[colMap.pvalue])
    const negLogP = -Math.log10(pvalue)
    return {
      snpId: String(row[colMap.snp] || ''),
      chromosome: normalizeChromosome(row[colMap.chromosome]),
      position: parseInt(row[colMap.position]) || 0,
      pvalue,
      negLogP,
      gene: colMap.gene ? row[colMap.gene] : undefined,
      effect: colMap.effect ? parseFloat(row[colMap.effect]) : undefined,
      maf: colMap.maf ? parseFloat(row[colMap.maf]) : undefined,
      isSignificant: negLogP >= config.genomeWideLine,
      isSuggestive: negLogP >= config.suggestiveLine && negLogP < config.genomeWideLine,
    }
  })

  // 2. 染色体排序(数字优先,然后 X/Y/MT)
  const chromosomeOrder = getChromosomeOrder([...new Set(rows.map(r => r.chromosome))])

  // 3. 计算统计信息
  const stats = computeStats(rows, config)

  return { rows, stats, chromosomeOrder }
}

/**
 * 标准化染色体名称
 */
function normalizeChromosome(chr: string): string | number {
  const cleaned = String(chr).toUpperCase().replace(/^CHR/, '').trim()
  const num = parseInt(cleaned)
  if (!isNaN(num)) return num
  return cleaned  // X, Y, MT, etc.
}

/**
 * 获取染色体排序顺序
 */
function getChromosomeOrder(chrs: (string | number)[]): (string | number)[] {
  const numeric = chrs.filter(c => typeof c === 'number').sort((a, b) => (a as number) - (b as number))
  const stringChrs = chrs.filter(c => typeof c === 'string')
  // X, Y, MT 的顺序
  const stringOrder = ['X', 'Y', 'MT', 'M']
  const sortedStrings = stringChrs.sort((a, b) => {
    const idxA = stringOrder.indexOf(a as string)
    const idxB = stringOrder.indexOf(b as string)
    if (idxA >= 0 && idxB >= 0) return idxA - idxB
    if (idxA >= 0) return -1
    if (idxB >= 0) return 1
    return String(a).localeCompare(String(b))
  })
  return [...numeric, ...sortedStrings]
}

/**
 * 计算统计信息
 */
function computeStats(rows: ManhattanRow[], config: ManhattanConfig): ManhattanStats {
  let genomeWideCount = 0
  let suggestiveCount = 0
  let maxNegLogP = 0
  let peakSnp = ''
  const chrDistribution: Record<string, number> = {}

  rows.forEach(row => {
    if (row.isSignificant) genomeWideCount++
    else if (row.isSuggestive) suggestiveCount++
    if (row.negLogP > maxNegLogP) {
      maxNegLogP = row.negLogP
      peakSnp = row.snpId
    }
    const chrKey = String(row.chromosome)
    chrDistribution[chrKey] = (chrDistribution[chrKey] || 0) + 1
  })

  return {
    totalSnpCount: rows.length,
    genomeWideCount,
    suggestiveCount,
    maxNegLogP,
    peakSnp,
    chrDistribution,
  }
}
```

### 7.4 图表配置生成

```typescript
/**
 * 构建 Plotly 图表配置
 */
export function buildPlotlyFigure(
  result: ProcessedResult,
  config: ManhattanConfig,
  isDark: boolean,
  selectedSnpIds?: Set<string>,
  hoveredSnpId?: string | null,
): PlotlyFigure {
  const { rows, chromosomeOrder } = result
  const useGL = rows.length > 5000

  // 计算每个染色体的累积偏移(让染色体在X轴上连续排列)
  const { xPositions, chrBoundaries } = computeXPositions(rows, chromosomeOrder)

  // 为每行数据分配X坐标
  const rowsWithX = rows.map(row => ({
    ...row,
    x: xPositions.get(`${row.chromosome}_${row.snpId}`) || 0,
  }))

  // 按染色体分组创建 trace
  const colors = CHROMOSOME_COLORS[config.colorScheme] || CHROMOSOME_COLORS.classic
  const traces: Plotly.Data[] = []

  chromosomeOrder.forEach((chr, chrIdx) => {
    const chrRows = rowsWithX.filter(r => r.chromosome === chr)
    const color = colors[chrIdx % colors.length]

    // 普通点
    const normalRows = chrRows.filter(r => !r.isSignificant && !r.isSuggestive)
    if (normalRows.length > 0) {
      traces.push({
        type: useGL ? 'scattergl' : 'scatter',
        mode: 'markers',
        x: normalRows.map(r => r.x),
        y: normalRows.map(r => r.negLogP),
        customdata: normalRows.map(r => [r.snpId, r.chromosome, r.position, r.pvalue, r.gene]),
        marker: {
          color: color,
          size: config.pointSize,
          opacity: config.pointOpacity,
        },
        name: `Chr${chr}`,
        showlegend: false,
        hovertemplate: buildHoverTemplate(config),
      })
    }

    // 建议线点
    const suggestiveRows = chrRows.filter(r => r.isSuggestive)
    if (suggestiveRows.length > 0) {
      traces.push({
        type: useGL ? 'scattergl' : 'scatter',
        mode: 'markers',
        x: suggestiveRows.map(r => r.x),
        y: suggestiveRows.map(r => r.negLogP),
        customdata: suggestiveRows.map(r => [r.snpId, r.chromosome, r.position, r.pvalue, r.gene]),
        marker: {
          color: '#F39C12',
          size: config.pointSize + 2,
          opacity: 1.0,
          symbol: 'diamond',
        },
        name: `Suggestive (Chr${chr})`,
        showlegend: false,
        hovertemplate: buildHoverTemplate(config),
      })
    }

    // 全基因组显著点(信号点)
    const sigRows = chrRows.filter(r => r.isSignificant)
    if (sigRows.length > 0) {
      traces.push({
        type: useGL ? 'scattergl' : 'scatter',
        mode: 'markers',
        x: sigRows.map(r => r.x),
        y: sigRows.map(r => r.negLogP),
        customdata: sigRows.map(r => [r.snpId, r.chromosome, r.position, r.pvalue, r.gene]),
        marker: {
          color: config.signalColor,
          size: config.pointSize + 4,
          opacity: 1.0,
          symbol: 'star',
          line: { color: '#fff', width: 1 },
        },
        name: `Genome-wide (Chr${chr})`,
        showlegend: false,
        hovertemplate: buildHoverTemplate(config),
      })
    }
  })

  // 选中/高亮 trace(置顶)
  if (selectedSnpIds && selectedSnpIds.size > 0) {
    const selected = rowsWithX.filter(r => selectedSnpIds.has(r.snpId))
    if (selected.length > 0) {
      traces.push({
        type: 'scatter',
        mode: 'markers',
        x: selected.map(r => r.x),
        y: selected.map(r => r.negLogP),
        customdata: selected.map(r => [r.snpId]),
        marker: {
          color: '#00FF88',
          size: config.pointSize + 8,
          opacity: 1.0,
          symbol: 'circle',
          line: { color: '#fff', width: 2 },
        },
        name: 'Selected',
        showlegend: true,
        hovertemplate: '<b>%{customdata[0]}</b><br>SELECTED<extra></extra>',
      })
    }
  }

  // 阈值线
  const shapes: Partial<Plotly.Shape>[] = []
  const yMax = config.yAxisMax === 'auto'
    ? Math.ceil(result.stats.maxNegLogP * 1.1)
    : config.yAxisMax

  if (config.showSuggestiveLine) {
    shapes.push({
      type: 'line',
      x0: 0, x1: 1, xref: 'paper',
      y0: config.suggestiveLine, y1: config.suggestiveLine,
      line: { color: '#9467BD', width: 1, dash: 'dash' },
    })
  }
  if (config.showGenomeWideLine) {
    shapes.push({
      type: 'line',
      x0: 0, x1: 1, xref: 'paper',
      y0: config.genomeWideLine, y1: config.genomeWideLine,
      line: { color: '#E74C3C', width: 1.5, dash: 'dash' },
    })
  }

  // 注释(阈值线标注)
  const annotations: Partial<Plotly.Annotation>[] = []
  if (config.showSuggestiveLine) {
    annotations.push({
      x: 1, y: config.suggestiveLine,
      xref: 'paper',
      text: `Suggestive (p=1e-${config.suggestiveLine.toFixed(1)})`,
      showarrow: false,
      font: { size: 10, color: '#9467BD' },
      xanchor: 'right', yanchor: 'bottom',
    })
  }
  if (config.showGenomeWideLine) {
    annotations.push({
      x: 1, y: config.genomeWideLine,
      xref: 'paper',
      text: `Genome-wide (p=1e-${config.genomeWideLine.toFixed(1)})`,
      showarrow: false,
      font: { size: 10, color: '#E74C3C' },
      xanchor: 'right', yanchor: 'bottom',
    })
  }

  // 布局
  const theme = getPlotTheme(isDark)
  const layout: Partial<Plotly.Layout> = {
    ...theme,
    title: {
      text: 'Manhattan Plot',
      font: { size: 16 },
    },
    xaxis: {
      title: { text: config.xAxisTitle, font: { size: 13 } },
      tickmode: 'array',
      tickvals: chrBoundaries.map(b => b.mid),
      ticktext: chrBoundaries.map(b => String(b.chromosome)),
      showgrid: config.showGrid,
      gridcolor: isDark ? '#33334d' : '#E5E6EB',
      tickangle: 0,
    },
    yaxis: {
      title: { text: config.yAxisTitle, font: { size: 13 } },
      range: [0, yMax],
      showgrid: config.showGrid,
      gridcolor: isDark ? '#33334d' : '#E5E6EB',
    },
    shapes,
    annotations,
    hovermode: 'closest',
    showlegend: false,
    margin: { t: 40, r: 120, b: 60, l: 60 },
    dragmode: 'select',  // 默认框选模式
  }

  const plotConfig: Partial<Plotly.Config> = {
    displayModeBar: true,
    displaylogo: false,
    modeBarButtonsToRemove: ['toImage'],
    scrollZoom: true,
    responsive: true,
  }

  return { data: traces, layout, config: plotConfig }
}

/**
 * 计算每个 SNP 在X轴上的累积位置
 */
function computeXPositions(
  rows: ManhattanRow[],
  chromosomeOrder: (string | number)[],
): { xPositions: Map<string, number>; chrBoundaries: Array<{ chromosome: string | number; start: number; end: number; mid: number }> } {
  // 按染色体分组
  const chrGroups = new Map<string | number, ManhattanRow[]>()
  rows.forEach(row => {
    const key = row.chromosome
    if (!chrGroups.has(key)) chrGroups.set(key, [])
    chrGroups.get(key)!.push(row)
  })

  // 按位置排序
  chromosomeOrder.forEach(chr => {
    const group = chrGroups.get(chr)
    if (group) group.sort((a, b) => a.position - b.position)
  })

  // 计算累积X位置
  const xPositions = new Map<string, number>()
  const chrBoundaries: Array<{ chromosome: string | number; start: number; end: number; mid: number }> = []
  let currentX = 0
  const gap = 0.02  // 染色体间空隙(以最大位置的比例)

  chromosomeOrder.forEach(chr => {
    const group = chrGroups.get(chr)
    if (!group || group.length === 0) return

    const maxPos = group[group.length - 1].position
    const scale = 1e6  // 1 Mbp = 1 unit

    group.forEach(row => {
      const x = currentX + row.position / scale
      xPositions.set(`${chr}_${row.snpId}`, x)
    })

    const start = currentX
    const end = currentX + maxPos / scale
    chrBoundaries.push({
      chromosome: chr,
      start,
      end,
      mid: (start + end) / 2,
    })

    currentX = end + (maxPos / scale) * gap
  })

  return { xPositions, chrBoundaries }
}

/**
 * 构建 hover 模板
 */
function buildHoverTemplate(config: ManhattanConfig): string {
  let template = '<b>%{customdata[0]}</b><br>'
  template += 'Chr%{customdata[1]}: %{customdata[2]}<br>'
  template += 'P-value: %{customdata[3]:.2e}<br>'
  template += '-log₁₀(P): %{y:.2f}'
  if (config.showGeneInHover) {
    template += '<br>Gene: %{customdata[4]}'
  }
  template += '<extra></extra>'
  return template
}

/**
 * 生成示例数据
 */
export function genSampleData(): { headers: string[]; rows: Record<string, any>[] } {
  const headers = ['SNP', 'Chromosome', 'Position', 'P-value', 'Gene']
  const rows: Record<string, any>[] = []
  const chrCount = 12

  for (let chr = 1; chr <= chrCount; chr++) {
    const snpCount = 800 + Math.floor(Math.random() * 400)
    for (let i = 0; i < snpCount; i++) {
      const pos = Math.floor(Math.random() * 50000000) + 1
      // 大多数P值不显著，少数显著
      let pvalue: number
      const rand = Math.random()
      if (rand < 0.005) {
        // 全基因组显著 p < 1e-8
        pvalue = Math.pow(10, -(8 + Math.random() * 6))
      } else if (rand < 0.02) {
        // 建议显著 p < 1e-5
        pvalue = Math.pow(10, -(5 + Math.random() * 3))
      } else {
        // 不显著
        pvalue = Math.random() * 0.5 + 0.001
      }
      rows.push({
        SNP: `rs${1000000 + chr * 100000 + i}`,
        Chromosome: chr,
        Position: pos,
        'P-value': pvalue,
        Gene: `GENE_${chr}_${Math.floor(pos / 1000000)}`,
      })
    }
  }

  // 添加几个峰值SNP确保图好看
  rows.push({ SNP: 'rs_peak_001', Chromosome: 3, Position: 12345678, 'P-value': 2.3e-12, Gene: 'PEAK1' })
  rows.push({ SNP: 'rs_peak_002', Chromosome: 7, Position: 23456789, 'P-value': 5.1e-15, Gene: 'PEAK2' })
  rows.push({ SNP: 'rs_peak_003', Chromosome: 11, Position: 34567890, 'P-value': 1.2e-10, Gene: 'PEAK3' })
  rows.push({ SNP: 'rs_peak_004', Chromosome: 5, Position: 15000000, 'P-value': 8.7e-9, Gene: 'PEAK4' })

  return { headers, rows }
}
```

---

## 八、Vue 视图 `ManhattanPlotView.vue`

### 8.1 完整代码框架

```vue
<template>
  <div class="manhattan-page">
    <!-- Toolbar -->
    <div class="page-toolbar">
      <NButton text @click="router.push('/tools')">
        <template #icon><NIcon :size="18"><ArrowBackOutline /></NIcon></template>
        返回工具箱
      </NButton>
      <h1 class="page-title">曼哈顿图绘制</h1>
      <NButton size="small" quaternary @click="loadSample">
        <template #icon><NIcon><SparklesOutline /></NIcon></template>
        示例数据
      </NButton>
      <NButton size="small" secondary @click="exportTableData">
        <template #icon><NIcon><DownloadOutline /></NIcon></template>
        导出表格
      </NButton>
      <NButtonGroup>
        <NButton size="tiny" secondary @click="exportImage('png')">PNG</NButton>
        <NButton size="tiny" secondary @click="exportImage('svg')">SVG</NButton>
      </NButtonGroup>
    </div>

    <!-- 主体 -->
    <div class="manhattan-layout">
      <!-- 左侧参数面板 -->
      <aside class="param-panel">
        <NCollapse :default-expanded-names="['data', 'thresholds', 'style']" arrow-placement="left">
          <!-- 数据映射 -->
          <NCollapseItem title="数据映射" name="data">
            <div class="param-row">
              <span class="param-label">SNP 列</span>
              <NSelect v-model:value="colMap.snp" :options="headerOptions" size="small" />
            </div>
            <div class="param-row">
              <span class="param-label">染色体列</span>
              <NSelect v-model:value="colMap.chromosome" :options="headerOptions" size="small" />
            </div>
            <div class="param-row">
              <span class="param-label">位置列</span>
              <NSelect v-model:value="colMap.position" :options="headerOptions" size="small" />
            </div>
            <div class="param-row">
              <span class="param-label">P-value 列</span>
              <NSelect v-model:value="colMap.pvalue" :options="headerOptions" size="small" />
            </div>
            <div class="param-row">
              <span class="param-label">基因列(可选)</span>
              <NSelect v-model:value="colMap.gene" :options="headerOptions" size="small" clearable />
            </div>
          </NCollapseItem>

          <!-- 阈值设置 -->
          <NCollapseItem title="阈值线" name="thresholds">
            <div class="param-row">
              <NSwitch v-model:value="config.showSuggestiveLine" size="small" />
              <span class="param-label-inline">显示建议线</span>
              <NInputNumber v-model:value="config.suggestiveLine" :show-button="false" size="small" class="param-input-sm" />
            </div>
            <div class="param-row">
              <NSwitch v-model:value="config.showGenomeWideLine" size="small" />
              <span class="param-label-inline">显示全基因组线</span>
              <NInputNumber v-model:value="config.genomeWideLine" :show-button="false" size="small" class="param-input-sm" />
            </div>
          </NCollapseItem>

          <!-- 配色样式 -->
          <NCollapseItem title="配色与样式" name="style">
            <div class="param-row">
              <span class="param-label">配色方案</span>
              <NSelect v-model:value="config.colorScheme" :options="colorSchemeOptions" size="small" />
            </div>
            <div class="param-row">
              <span class="param-label">信号点颜色</span>
              <NColorPicker v-model:value="config.signalColor" :show-alpha="false" size="small" />
            </div>
            <div class="param-row">
              <span class="param-label">点大小</span>
              <NSlider v-model:value="config.pointSize" :min="1" :max="8" :step="1" />
            </div>
            <div class="param-row">
              <span class="param-label">点透明度</span>
              <NSlider v-model:value="config.pointOpacity" :min="0.3" :max="1.0" :step="0.1" />
            </div>
          </NCollapseItem>

          <!-- 坐标轴 -->
          <NCollapseItem title="坐标轴" name="axis">
            <div class="param-row">
              <span class="param-label">Y轴最大値</span>
              <NRadioGroup v-model:value="yAxisMaxMode" size="small">
                <NRadioButton value="auto">自动</NRadioButton>
                <NRadioButton value="manual">自定义</NRadioButton>
              </NRadioGroup>
              <NInputNumber v-if="yAxisMaxMode === 'manual'" v-model:value="manualYMax" :show-button="false" size="small" class="param-input-sm" />
            </div>
          </NCollapseItem>

          <!-- 导出 -->
          <NCollapseItem title="导出" name="export">
            <div class="param-row">
              <span class="param-label">DPI</span>
              <NSelect v-model:value="exportDpi" :options="[{label:'300',value:300},{label:'600',value:600},{label:'1000',value:1000}]" size="small" />
            </div>
          </NCollapseItem>
        </NCollapse>

        <!-- 生成按钮 -->
        <div class="action-area">
          <NButton size="small" type="primary" :loading="plotting" block @click="generatePlot">
            <template #icon><NIcon><BarChartOutline /></NIcon></template>
            生成图表
          </NButton>
          <NButton v-if="selectedSnpIds.size > 0" size="small" text block @click="clearSelection">
            清除选择 ({{ selectedSnpIds.size }} 个)
          </NButton>
        </div>
      </aside>

      <!-- 中间工作区 -->
      <main class="work-area">
        <!-- 图表 -->
        <div class="plot-card">
          <div v-if="!processed" class="empty-state">
            <NEmpty description="请上传数据或加载示例" />
          </div>
          <NSpin v-else :show="plotting">
            <div id="manhattan-plot-container" class="plot-container" />
          </NSpin>
        </div>

        <!-- 数据表格(图-表联动) -->
        <div class="table-card">
          <div class="table-header">
            <span class="table-title">
              SNP 明细
              <NTag v-if="selectedSnpIds.size > 0" size="small" type="info">
                已选 {{ selectedSnpIds.size }} 个
              </NTag>
            </span>
            <div class="table-actions">
              <NButton v-if="selectedSnpIds.size > 0" size="tiny" text @click="showAllData">
                显示全部
              </NButton>
              <NButton v-if="selectedSnpIds.size > 0" size="tiny" text @click="showSelectedOnly">
                仅选中
              </NButton>
            </div>
          </div>
          <NDataTable
            :columns="tableColumns"
            :data="filteredTableData"
            :pagination="{ pageSize: 10 }"
            size="small"
            :row-class-name="getRowClassName"
            :scroll-x="700"
            @update:checked-row-keys="onTableSelectionChange"
            @row-click="onTableRowClick"
          />
        </div>
      </main>

      <!-- 右侧统计面板 -->
      <aside class="side-panel">
        <div class="stat-card">
          <div class="stat-title">统计摘要</div>
          <div class="stat-grid">
            <NStatistic label="总 SNP 数" :value="stats?.totalSnpCount || 0" />
            <NStatistic label="全基因组显著" :value="stats?.genomeWideCount || 0">
              <template #suffix>
                <NTag v-if="stats" size="tiny" :type="stats.genomeWideCount > 0 ? 'error' : 'default'">
                  {{ stats.totalSnpCount > 0 ? ((stats.genomeWideCount / stats.totalSnpCount) * 100).toFixed(2) : 0 }}%
                </NTag>
              </template>
            </NStatistic>
            <NStatistic label="建议显著" :value="stats?.suggestiveCount || 0" />
            <NStatistic label="最高峰值">
              <template #default>
                <span v-if="stats" class="peak-value">{{ stats.maxNegLogP.toFixed(2) }}</span>
              </template>
            </NStatistic>
          </div>
          <NDivider />
          <div class="stat-title">峰值 SNP</div>
          <NTag v-if="stats?.peakSnp" size="small" type="error">{{ stats.peakSnp }}</NTag>
        </div>

        <!-- 染色体分布柱状图 -->
        <div class="stat-card">
          <div class="stat-title">染色体分布</div>
          <div ref="chrDistChart" class="mini-chart" />
        </div>
      </aside>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useMessage } from 'naive-ui'
import { NButton, NButtonGroup, NSelect, NInputNumber, NSwitch, NSlider, NColorPicker,
         NRadioGroup, NRadioButton, NCollapse, NCollapseItem, NDataTable, NTag, NDivider,
         NStatistic, NEmpty, NSpin, NIcon } from 'naive-ui'
import { ArrowBackOutline, SparklesOutline, BarChartOutline, DownloadOutline } from '@vicons/ionicons5'
import * as Plotly from 'plotly.js-dist-min'
import { useThemeStore } from '@/stores/theme'
import type { DataTableColumns } from 'naive-ui'
import type { ManhattanConfig, ColMap, ManhattanRow, ManhattanStats, ProcessedResult, PlotlyFigure } from '@/utils/manhattanProcessor'
import {
  DEFAULT_CONFIG,
  autoDetectColumns,
  parseDelimited,
  validateData,
  processManhattanData,
  buildPlotlyFigure,
  genSampleData,
} from '@/utils/manhattanProcessor'

const router = useRouter()
const message = useMessage()
const themeStore = useThemeStore()
const isDark = computed(() => themeStore.isDark)

// === 状态 ===
const config = ref<ManhattanConfig>({ ...DEFAULT_CONFIG })
const colMap = ref<Partial<ColMap>>({})
const headers = ref<string[]>([])
const rawRows = ref<Record<string, any>[]>([])
const processed = ref<ProcessedResult | null>(null)
const stats = computed(() => processed.value?.stats || null)
const plotting = ref(false)
const selectedSnpIds = ref<Set<string>>(new Set())
const hoveredSnpId = ref<string | null>(null)
const tableMode = ref<'all' | 'selected'>('all')

const yAxisMaxMode = ref<'auto' | 'manual'>('auto')
const manualYMax = ref(15)
const exportDpi = ref(1000)

// === 列选项 ===
const headerOptions = computed(() => headers.value.map(h => ({ label: h, value: h })))
const colorSchemeOptions = [
  { label: '经典', value: 'classic' },
  { label: '柔和', value: 'pastel' },
  { label: '灰度', value: 'grayscale' },
]

// === 表格 ===
const tableColumns = computed<DataTableColumns<ManhattanRow>>(() => [
  { type: 'selection', multiple: false },
  { title: 'SNP', key: 'snpId', width: 120, sorter: 'default', fixed: 'left' },
  { title: 'Chr', key: 'chromosome', width: 60, sorter: (a, b) => Number(a.chromosome) - Number(b.chromosome) },
  { title: 'Position', key: 'position', width: 110, sorter: 'default', render: (row) => row.position.toLocaleString() },
  { title: 'P-value', key: 'pvalue', width: 100, sorter: 'default', render: (row) => row.pvalue.toExponential(2) },
  { title: '-log₁₀(P)', key: 'negLogP', width: 90, sorter: 'default', render: (row) => row.negLogP.toFixed(2) },
  { title: 'Gene', key: 'gene', width: 100 },
  { title: 'Status', key: 'status', width: 100, render: (row) => {
    if (row.isSignificant) return h(NTag, { size: 'tiny', type: 'error' }, () => 'Genome-wide')
    if (row.isSuggestive) return h(NTag, { size: 'tiny', type: 'warning' }, () => 'Suggestive')
    return h(NTag, { size: 'tiny' }, () => 'NS')
  }},
])

// 筛选后的表格数据
const filteredTableData = computed(() => {
  const rows = processed.value?.rows || []
  if (tableMode.value === 'selected' && selectedSnpIds.value.size > 0) {
    return rows.filter(r => selectedSnpIds.value.has(r.snpId))
  }
  return rows
})

function getRowClassName(row: ManhattanRow) {
  if (selectedSnpIds.value.has(row.snpId)) return 'row-selected'
  if (hoveredSnpId.value === row.snpId) return 'row-hovered'
  return ''
}

function onTableRowClick(row: ManhattanRow) {
  selectedSnpIds.value = new Set([row.snpId])
  renderPlot()
}

function onTableSelectionChange(keys: (string | number)[]) {
  selectedSnpIds.value = new Set(keys as string[])
  renderPlot()
}

function showAllData() { tableMode.value = 'all' }
function showSelectedOnly() { tableMode.value = 'selected' }

// === Plotly ===
const PLOT_DIV_ID = 'manhattan-plot-container'

async function renderPlot() {
  if (!processed.value) return
  plotting.value = true

  try {
    const container = document.getElementById(PLOT_DIV_ID)
    if (!container) return

    const yMax = yAxisMaxMode.value === 'manual' ? manualYMax.value : 'auto' as const
    const currentConfig = { ...config.value, yAxisMax: yMax }

    const figure = buildPlotlyFigure(
      processed.value,
      currentConfig,
      isDark.value,
      selectedSnpIds.value,
      hoveredSnpId.value,
    )

    await Plotly.react(container, figure.data, figure.layout, figure.config)

    // 绑定事件(仅在首次渲染时)
    if (!container.hasAttribute('data-events-bound')) {
      bindPlotEvents(container)
      container.setAttribute('data-events-bound', 'true')
    }
  } finally {
    plotting.value = false
  }
}

function bindPlotEvents(container: HTMLElement) {
  // 框选 / lasso 选择
  container.on('plotly_selected', (event: any) => {
    const pointIds = event.points?.map((p: any) => p.customdata?.[0]) ?? []
    selectedSnpIds.value = new Set(pointIds)
  })

  // 单击单点
  container.on('plotly_click', (event: any) => {
    const snpId = event.points?.[0]?.customdata?.[0]
    if (snpId) selectedSnpIds.value = new Set([snpId])
  })

  // Hover
  container.on('plotly_hover', (event: any) => {
    hoveredSnpId.value = event.points?.[0]?.customdata?.[0] || null
  })
  container.on('plotly_unhover', () => {
    hoveredSnpId.value = null
  })

  // 双击空白处清除选择
  container.on('plotly_doubleclick', () => {
    selectedSnpIds.value = new Set()
  })
}

function clearSelection() {
  selectedSnpIds.value = new Set()
  renderPlot()
}

function generatePlot() {
  updatePipeline()
}

// === 数据加载 ===
function loadSample() {
  const sample = genSampleData()
  headers.value = sample.headers
  rawRows.value = sample.rows
  colMap.value = autoDetectColumns(sample.headers) as ColMap
  updatePipeline()
  message.success('已加载示例数据')
}

async function updatePipeline() {
  if (!colMap.value.snp || !colMap.value.chromosome || !colMap.value.position || !colMap.value.pvalue) {
    return
  }

  const fullColMap = colMap.value as ColMap
  const errors = validateData(rawRows.value, fullColMap)
  if (errors.length > 0) {
    message.error(`数据校验失败: ${errors.slice(0, 3).join('; ')}${errors.length > 3 ? ` 等${errors.length}处错误` : ''}`)
    return
  }

  processed.value = processManhattanData(rawRows.value, fullColMap, config.value)
  await renderPlot()
}

// === 导出 ===
function exportImage(format: 'png' | 'svg') {
  const container = document.getElementById(PLOT_DIV_ID)
  if (!container) return

  const rect = container.getBoundingClientRect()
  const timestamp = new Date().toISOString().slice(0, 19).replace(/[:T]/g, '')
  const baseName = 'manhattan'

  if (format === 'svg') {
    Plotly.downloadImage(container, {
      format: 'svg',
      filename: `${baseName}_${timestamp}`,
      width: Math.round(rect.width),
      height: Math.round(rect.height),
    } as any)
  } else {
    const dpi = exportDpi.value
    const scale = dpi / 96
    Plotly.downloadImage(container, {
      format: 'png',
      filename: `${baseName}_${timestamp}_${dpi}dpi`,
      width: Math.round(rect.width),
      height: Math.round(rect.height),
      scale,
    } as any)
  }
}

function exportTableData() {
  if (!processed.value) return
  const rows = tableMode.value === 'selected'
    ? processed.value.rows.filter(r => selectedSnpIds.value.has(r.snpId))
    : processed.value.rows

  const csv = [
    'SNP,Chromosome,Position,P-value,-log10(P),Gene,Is_Significant,Is_Suggestive',
    ...rows.map(r => `${r.snpId},${r.chromosome},${r.position},${r.pvalue},${r.negLogP},${r.gene || ''},${r.isSignificant},${r.isSuggestive}`)
  ].join('\n')

  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
  const link = document.createElement('a')
  link.href = URL.createObjectURL(blob)
  link.download = `manhattan_data_${new Date().toISOString().slice(0, 10)}.csv`
  link.click()
}

// === 生命周期 ===
let debounceTimer: ReturnType<typeof setTimeout> | null = null

function schedulePipeline() {
  if (debounceTimer) clearTimeout(debounceTimer)
  debounceTimer = setTimeout(updatePipeline, 300)
}

// 监听参数变化自动更新
watch(() => [
  config.value.suggestiveLine,
  config.value.genomeWideLine,
  config.value.showSuggestiveLine,
  config.value.showGenomeWideLine,
  config.value.colorScheme,
  config.value.signalColor,
  config.value.pointSize,
  config.value.pointOpacity,
  config.value.showChrLabels,
  config.value.showGeneInHover,
  config.value.showGrid,
], schedulePipeline, { deep: false })

watch(isDark, () => renderPlot())

onMounted(() => {
  loadSample()
})

onUnmounted(() => {
  if (debounceTimer) clearTimeout(debounceTimer)
  const el = document.getElementById(PLOT_DIV_ID)
  if (el) Plotly.purge(el)
})
</script>

<style scoped>
.manhattan-page {
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
.manhattan-layout {
  display: grid;
  grid-template-columns: 280px 1fr 260px;
  gap: 16px;
  align-items: start;
}

/* 参数面板 */
.param-panel {
  background: var(--neutral-card, #fff);
  border: 1px solid var(--neutral-border, #e5e6eb);
  border-radius: 12px;
  padding: 12px;
  max-height: calc(100vh - 120px);
  overflow-y: auto;
}
.param-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}
.param-label {
  font-size: 12px;
  color: var(--neutral-text-2, #4e5969);
  min-width: 60px;
  flex-shrink: 0;
}
.param-label-inline {
  font-size: 12px;
  color: var(--neutral-text-2, #4e5969);
  flex: 1;
}
.param-input-sm {
  width: 70px;
}
.action-area {
  margin-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

/* 图表区域 */
.plot-card {
  position: relative;
  background: var(--neutral-card, #fff);
  border: 1px solid var(--neutral-border, #e5e6eb);
  border-radius: 12px;
  padding: 8px;
  min-height: 480px;
}
.plot-container {
  width: 100%;
  height: 480px;
}
.empty-state {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 480px;
}

/* 表格 */
.table-card {
  margin-top: 12px;
  background: var(--neutral-card, #fff);
  border: 1px solid var(--neutral-border, #e5e6eb);
  border-radius: 12px;
  padding: 8px;
  max-height: 360px;
  overflow-y: auto;
}
.table-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
  padding: 0 4px;
}
.table-title {
  font-size: 13px;
  font-weight: 500;
  color: var(--neutral-text-1, #1d2129);
  display: flex;
  align-items: center;
  gap: 8px;
}
.table-actions {
  display: flex;
  gap: 4px;
}

/* 统计面板 */
.side-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.stat-card {
  background: var(--neutral-card, #fff);
  border: 1px solid var(--neutral-border, #e5e6eb);
  border-radius: 12px;
  padding: 12px;
}
.stat-title {
  font-size: 13px;
  font-weight: 500;
  color: var(--neutral-text-1, #1d2129);
  margin-bottom: 8px;
}
.stat-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}
.peak-value {
  font-size: 18px;
  font-weight: 600;
  color: var(--arco-primary, #165DFF);
}
.mini-chart {
  width: 100%;
  height: 160px;
}

/* 表格行样式 */
:deep(.row-selected) {
  background-color: var(--arco-primary-light, rgba(22, 93, 255, 0.1)) !important;
}
:deep(.row-hovered) {
  background-color: var(--neutral-bg, rgba(0, 0, 0, 0.04)) !important;
}

/* 响应式 */
@media (max-width: 1200px) {
  .manhattan-layout { grid-template-columns: 1fr; }
  .param-panel, .side-panel { max-height: none; }
}
@media (max-width: 768px) {
  .manhattan-page { padding: 12px; }
}
</style>
```

---

## 九、注册配置

### 9.1 `tools_setting.yaml` 追加

```yaml
- key: "manhattan"
  title: "曼哈顿图绘制"
  description: "GWAS / QTL 关联分析结果的可视化，支持染色体级交互式曼哈顿图与图-表联动"
  icon: "BarChartOutline"
  gradient: "linear-gradient(135deg, #E74C3C 0%, #9B59B6 50%, #3498DB 100%)"
  route: "/tools/manhattan"
  group: "visualization"
  enabled: true
  order: 50
  config_dir: ""
```

> `order: 50` 排在火山图(45)之后，确保可视化组内顺序合理。

### 9.2 `router/index.ts` 追加

```typescript
{
  path: 'tools/manhattan',
  name: 'tools-manhattan',
  component: () => import('@/views/BioTools/ManhattanPlotView.vue'),
  meta: { title: '曼哈顿图绘制', requiresAuth: true },
},
```

### 9.3 `ToolsHubView.vue` 图标登记

```typescript
import { BarChartOutline /* 已在 ICON_MAP 中,无需新增 */ } from '@vicons/ionicons5'
```

`BarChartOutline` 已在现有 `ICON_MAP` 中登记，无需重复添加。

---

## 十、文件清单

| 文件 | 路径 | 说明 |
|------|------|------|
| 视图 | `frontend/src/views/BioTools/ManhattanPlotView.vue` | 页面组件 |
| 处理器 | `frontend/src/utils/manhattanProcessor.ts` | 数据处理 + Plotly 配置生成 |
| 注册 | `tool_configs/tools_setting.yaml` | 工具卡片注册 |
| 路由 | `frontend/src/router/index.ts` | 子路由注册 |

---

## 十一、上线检查清单

- [x] `tools_setting.yaml` 已注册，`key=manhattan`，`group=visualization`，`order=50`
- [x] `router/index.ts` 已加 `tools/manhattan` 子路由，`name=tools-manhattan`
- [x] 图标 `BarChartOutline` 已确认在 `ICON_MAP` 中
- [x] 视图 `ManhattanPlotView.vue`，根 class `manhattan-page`，布局 class `manhattan-layout`
- [x] 处理器 `manhattanProcessor.ts`，纯函数模块，无 Vue 依赖
- [x] 三栏布局: `280px 1fr 260px`，gap 16px
- [x] 图表容器高度 480px，Plotly margin `{t:40, r:120, b:60, l:60}`
- [x] 图-表联动: `plotly_selected` → 表格筛选，表格行点击 → 图上高亮
- [x] 大数据优化: >5000 点自动 `scattergl`
- [x] 响应式: `@media (max-width: 1200px)` 退化为单栏
- [x] 暗色模式: 监听 `isDark` 重渲染，独立暗色配色
- [x] `onMounted` 加载示例数据
- [x] 参数变化 300ms debounce 自动更新
- [x] `type="primary"` 主操作按钮「生成图表」
- [x] `onUnmounted` 清理定时器 + `Plotly.purge`
- [x] 导出 PNG(300/600/1000 DPI) + SVG + CSV

---

## 十二、图-表联动时序图

```
用户                          Plotly                          Vue State                     Table
 │                              │                                │                           │
 │  框选多个点                  │                                │                           │
 │ ──────────────────────────> │                                │                           │
 │                              │ plotly_selected event          │                           │
 │                              │ ──────────────────────────>  │                           │
 │                              │                                │ selectedSnpIds = {...}    │
 │                              │                                │                           │
 │                              │                                │ filteredTableData 更新    │
 │                              │                                │ ────────────────────────> │
 │                              │                                │                           │ 仅显示选中行
 │                              │                                │                           │
 │  点击表格某行                │                                │                           │
 │ ──────────────────────────> │                                │                           │
 │                              │                                │ onTableRowClick           │
 │                              │                                │ selectedSnpIds = {snp1}   │
 │                              │                                │                           │
 │                              │ Plotly.react() 重渲染          │                           │
 │                              │ 选中点高亮(绿色+放大)           │                           │
 │                              │ <──────────────────────────  │                           │
 │                              │                                │                           │
 │  双击表格行                  │                                │                           │
 │ ──────────────────────────> │                                │                           │
 │                              │                                │ zoomToChromosome()        │
 │                              │ layout.xaxis.range 更新        │                           │
 │                              │ <──────────────────────────  │                           │
 │  图表自动 zoom 到该染色体     │                                │                           │
 │                              │                                │                           │
 │  点击"显示全部"              │                                │                           │
 │ ──────────────────────────> │                                │                           │
 │                              │                                │ tableMode = 'all'         │
 │                              │                                │ selectedSnpIds = {}       │
 │                              │ Plotly.react() 还原            │                           │
 │  所有点恢复默认样式           │ <──────────────────────────  │                           │
 │                              │                                │                           │
```

---

*设计完成。本规范由 tools_design.md 衍生，所有布局/命名/交互约定与母规范保持一致。*
