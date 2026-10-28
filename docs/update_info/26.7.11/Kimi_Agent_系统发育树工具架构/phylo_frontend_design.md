# OmicHub 系统发育树构建工具 — 前端设计方案

> 版本: v1.0 | 技术栈: Vue 3 + TypeScript + Naive UI + phylotree.js + Pinia

---

## 一、可视化库选型分析

### 1.1 候选库对比

| 维度 | **phylotree.js** | ECharts tree 系列 | phylocanvas.gl | PhyloJS |
|------|:---:|:---:|:---:|:---:|
| **定位** | 专业系统发育树库 | 通用树图库 | WebGL 大数树渲染 | 解析/工具库 |
| **底层技术** | D3.js (SVG) | Canvas/SVG | WebGL (Deck.gl) | 纯 JS |
| **Newick 解析** | 内置 | 不支持 | 内置 | 内置 (最佳) |
| **分支长度显示** | 完整支持 | 不支持 | 支持 | — |
| **Bootstrap 值** | 原生支持 | 不支持 | 需自定义 | — |
| **布局类型** | 矩形/径向/圆形 | 正交/径向 | 矩形/圆形/径向 | — |
| **节点交互** | 折叠/展开/重根/选择 | 折叠/展开 | 选择/高亮 | — |
| **缩放拖拽** | 原生支持 | roam 模式 | 原生支持 | — |
| **SVG 导出** | 原生支持 | 支持 | PNG 导出 | — |
| **TypeScript** | 有声明文件 | 完整支持 | 无 | 完整支持 |
| **包体积** | 238KB | 按需加载 | 53KB | 15KB |
| **大型树性能** | ~5000 tips | ~1000 tips | 100,000+ tips | — |
| **Vue 3 集成** | 需封装 | vue-echarts | 需封装 | 直接导入 |
| **生态活跃度** | 活跃 (2024-2025) | 非常活跃 | 中等 | 较新 (2024) |

### 1.2 各库详细分析

#### phylotree.js (推荐主库)

```
npm install phylotree
```

**核心优势：**
- **专为系统发育树设计**：基于 D3.js hierarchy layout 扩展，API 语义完全对应进化生物学概念（clade collapse、rerooting、ladderization）
- **丰富的交互能力**：缩放、拖拽、节点折叠/展开、重定根、阶梯化、多类别选择、brush 选择
- **专业功能内置**：支持 bootstrap 值显示、分支长度缩放、比例尺、tip 对齐、大小气泡
- **高度可定制**：通过 CSS 和 JavaScript callback 自定义样式，支持分支颜色渐变
- **格式支持广泛**：Newick（含 HyPhy/BEAST 扩展）、PhyloXML、NeXML
- **TypeScript 支持**：包含 TypeScript 声明文件（`phylotree`, `PhylotreeNode`, `RenderOptions`）
- **中间件设计**：selection_callback 和 traverse_and_compute 抽象便于与 Vue 响应式系统集成

**主要缺点：**
- 包体积较大（238KB，含 D3 依赖）
- 超过 5000 tips 时性能下降（SVG 渲染限制）
- Vue 3 集成需手动封装（非组件化设计）

**Vue 3 集成方式：**
```typescript
import { phylotree } from 'phylotree';
// 在组件 mounted 中实例化，通过 ref 访问 DOM 容器
// 利用 phylotree 的 selection_callback 与 Vue 响应式数据联动
```

#### ECharts tree 系列（不推荐）

**核心问题：**
- **不支持分支长度**：ECharts tree 的 edge 不携带距离信息，而分支长度是系统发育树的核心要素
- **不支持 Newick 格式**：需自行编写转换器将 Newick 转为 ECharts tree data 格式
- **缺乏专业功能**：无 bootstrap 值显示、无重定根、无阶梯化、无比例尺
- Apache ECharts GitHub 上存在 [Feature Request #16555](https://github.com/apache/echarts/issues/16555) 请求支持系统发育树特性，但至今未实现

**结论**：ECharts tree 适用于通用层级数据展示（如组织架构图、文件目录），不适合系统发育树可视化。

#### phylocanvas.gl（大型树备选）

**核心优势：**
- **WebGL 渲染**：基于 Deck.gl，可处理 100,000+ tips 的超大型树
- 包体积适中（53KB，零依赖）

**主要缺点：**
- 定制化能力有限，不如 phylotree.js 灵活
- 缺少系统发育分析相关的专业 API
- TypeScript 支持不完善

**适用场景**：当用户需要可视化 5000+ tips 的超大型树时，作为 phylotree.js 的降级方案。

#### PhyloJS（辅助解析库）

**核心优势：**
- 仅 15KB，零依赖
- 完整的 TypeScript 支持
- 支持 Newick/Nexus/phyloXML/NeXML/PhyJSON 多种格式
- 支持网络、重定根、注释提取等操作

**适用场景**：作为 Newick 解析和树操作的辅助工具库，与 phylotree.js 配合使用。

### 1.3 最终推荐方案

| 场景 | 推荐库 | 理由 |
|------|--------|------|
| **主可视化引擎** | **phylotree.js** | 功能最全面、API 最专业、与 D3 生态完美融合 |
| **Newick 解析/预处理** | **phylotree.js 内置** | 无需额外依赖 |
| **超大型树 (>5000 tips)** | **phylocanvas.gl** | WebGL 渲染，GPU 加速 |
| **树统计计算** | **PhyloJS** (可选) | TypeScript 友好，零依赖 |

---

## 二、页面布局设计

### 2.1 整体布局

参照火山图工具的三栏紧凑布局规范：

```
┌─────────────────────────────────────────────────────────────┐
│ ← 返回工具箱   系统发育树构建                   ✨ 示例数据  │  ← toolbar
├──────────────┬──────────────────────────────┬───────────────┤
│  数据输入     │                              │   树统计信息   │
│   ▼          │   [phylotree.js 渲染区域]     │   序列 50     │
│  序列上传     │                              │   树高 2.34   │
│  Newick上传   │   ┌──────────────────────┐   │   分支 98     │
│  示例数据     │   │                      │   │   平均长度    │
│              │   │    矩形/径向树形图     │   │   Bootstrap   │
│  比对配置     │   │                      │   │               │
│   ▼          │   │  ○──○──A             │   │   节点搜索     │
│  工具选择     │   │  │  └──○──B          │   │   [______]    │
│  参数设置     │   │  └──○──C             │   │               │
│   (条件启用)  │   │                      │   │   序列列表     │
│              │   └──────────────────────┘   │   ┌───────────┐ │
│  树构建配置   │                              │   │ID|长度   │ │
│   ▼          │  [构建系统发育树] 导出 全屏    │   │Seq1|500 │ │
│  方法选择     │                              │   │Seq2|498 │ │
│  替代模型     │                              │   │...      │ │
│  Bootstrap   │                              │   └───────────┘ │
│              │                              │               │
│  可视化配置   │                              │               │
│   ▼          │                              │               │
│  布局选择     │                              │               │
│  分支样式     │                              │               │
│  标签开关     │                              │               │
│  颜色主题     │                              │               │
│              │                              │               │
│ [构建系统    │                              │               │
│  发育树]     │                              │               │
│              │                              │               │
└──────────────┴──────────────────────────────┴───────────────┘
   param-panel          work-area              side-panel
   (300px)              (1fr)                  (280px)
```

### 2.2 响应式策略

```css
/* 桌面三栏 */
.phylo-container {
  display: grid;
  grid-template-columns: 300px 1fr 280px;
  gap: 12px;
}

/* 平板/移动端单栏 */
@media (max-width: 1200px) {
  .phylo-container {
    grid-template-columns: 1fr;
  }
}
```

---

## 三、组件拆分策略

### 3.1 组件层级图

```
PhylogeneticTreeView.vue (页面级，状态编排)
├── PhyloToolbar.vue (工具栏：返回、标题、示例数据)
├── PhyloParamPanel.vue (左侧面板容器)
│   ├── DataInputSection.vue (数据输入折叠面板)
│   ├── AlignmentSection.vue (比对配置折叠面板)
│   ├── TreeBuildSection.vue (树构建配置折叠面板)
│   └── VizConfigSection.vue (可视化配置折叠面板)
├── PhyloWorkArea.vue (中间工作区)
│   ├── PhyloTreeRenderer.vue (phylotree.js 封装组件)
│   └── PhyloToolBar.vue (构建按钮、导出、全屏)
└── PhyloSidePanel.vue (右侧面板)
    ├── TreeStatistics.vue (树统计信息)
    ├── NodeSearch.vue (节点搜索)
    └── SequenceTable.vue (序列列表)

phyloProcessor.ts (纯函数工具模块)
```

### 3.2 拆分理由

| 组件 | 拆分理由 | 复用性 |
|------|---------|--------|
| `PhyloTreeRenderer.vue` | phylotree.js 的 Vue 封装，隔离 D3 DOM 操作 | 可在其他页面复用 |
| `PhyloParamPanel.vue` | 参数面板逻辑复杂，独立管理折叠状态 | 模式类似火山图参数面板 |
| `DataInputSection.vue` | 数据输入有独立的验证逻辑 | 模式可复用于其他工具 |
| `TreeStatistics.vue` | 统计计算独立，便于测试 | 通用统计展示组件 |
| `SequenceTable.vue` | 表格数据独立管理 | 通用序列列表组件 |

---

## 四、完整代码骨架

### 4.1 类型定义 (types/phylo.ts)

```typescript
/**
 * 系统发育树工具 — 类型定义
 */

/** 比对工具选项 */
export type AlignmentTool = 'mafft' | 'clustalo' | 'muscle' | 'prealigned';

/** 树构建方法 */
export type TreeMethod = 'nj' | 'upgma' | 'ml_iqtree' | 'ml_fasttree';

/** 替代模型 */
export type SubstitutionModel = 'JC69' | 'K2P' | 'HKY' | 'GTR' | 'GTR+G' | 'GTR+I+G';

/** 树布局类型 */
export type TreeLayout = 'rectangular' | 'circular' | 'radial';

/** 输入数据类型 */
export type InputType = 'fasta' | 'newick' | 'example';

/** 任务状态 */
export type TaskStatus = 'pending' | 'running' | 'success' | 'failed' | 'timeout';

/** 构建参数 */
export interface TreeBuildParams {
  alignmentTool: AlignmentTool;
  treeMethod: TreeMethod;
  substitutionModel: SubstitutionModel;
  bootstrap: number;
  advancedParams: string;
}

/** 可视化配置 */
export interface VizConfig {
  layout: TreeLayout;
  isRooted: boolean;
  showLabels: boolean;
  showBootstrap: boolean;
  showScaleBar: boolean;
  alignTips: boolean;
  branchWidth: number;
  fontSize: number;
}

/** 树统计信息 */
export interface TreeStatistics {
  sequenceCount: number;
  treeHeight: number;       // 最大分支长度
  totalBranches: number;
  avgBranchLength: number;
  minBootstrap: number;
  maxBootstrap: number;
  avgBootstrap: number;
}

/** 序列信息 */
export interface SequenceInfo {
  id: string;
  length: number;
  alignedLength: number;
  description?: string;
}

/** 节点数据 */
export interface TreeNode {
  id: string;
  name: string;
  branchLength: number;
  bootstrap?: number;
  isLeaf: boolean;
  children?: TreeNode[];
  parent?: TreeNode;
  depth?: number;
}

/** 任务响应 */
export interface TaskResponse {
  taskId: string;
  status: TaskStatus;
  progress?: number;
  message?: string;
  result?: {
    newick: string;
    fileId: string;
  };
  error?: string;
}
```

### 4.2 Pinia Store (stores/phyloStore.ts)

```typescript
import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import type {
  TreeBuildParams, VizConfig, TreeStatistics,
  SequenceInfo, TaskResponse, InputType
} from '@/types/phylo';

export const usePhyloStore = defineStore('phylo', () => {
  // === 状态 ===
  const inputType = ref<InputType | null>(null);
  const fileId = ref<string>('');
  const newickString = ref<string>('');
  const taskId = ref<string>('');
  const taskStatus = ref<TaskResponse['status']>('pending');
  const taskProgress = ref<number>(0);
  const taskError = ref<string>('');
  const isBuilding = ref<boolean>(false);
  const selectedNodeId = ref<string>('');

  const buildParams = ref<TreeBuildParams>({
    alignmentTool: 'mafft',
    treeMethod: 'nj',
    substitutionModel: 'K2P',
    bootstrap: 1000,
    advancedParams: ''
  });

  const vizConfig = ref<VizConfig>({
    layout: 'rectangular',
    isRooted: true,
    showLabels: true,
    showBootstrap: true,
    showScaleBar: true,
    alignTips: true,
    branchWidth: 1.5,
    fontSize: 12
  });

  const treeStatistics = ref<TreeStatistics>({
    sequenceCount: 0,
    treeHeight: 0,
    totalBranches: 0,
    avgBranchLength: 0,
    minBootstrap: 0,
    maxBootstrap: 0,
    avgBootstrap: 0
  });

  const sequences = ref<SequenceInfo[]>([]);

  // === 计算属性 ===
  const hasTree = computed(() => newickString.value.length > 0);
  const needsAlignment = computed(() => buildParams.value.alignmentTool !== 'prealigned');
  const isTaskRunning = computed(() => taskStatus.value === 'running');

  // === Actions ===
  function resetStore() {
    newickString.value = '';
    taskId.value = '';
    taskStatus.value = 'pending';
    taskProgress.value = 0;
    taskError.value = '';
    isBuilding.value = false;
    selectedNodeId.value = '';
    treeStatistics.value = {
      sequenceCount: 0, treeHeight: 0, totalBranches: 0,
      avgBranchLength: 0, minBootstrap: 0, maxBootstrap: 0, avgBootstrap: 0
    };
    sequences.value = [];
  }

  function setNewick(nwk: string) {
    newickString.value = nwk;
  }

  function updateTaskStatus(resp: TaskResponse) {
    taskStatus.value = resp.status;
    taskProgress.value = resp.progress ?? 0;
    if (resp.error) taskError.value = resp.error;
    if (resp.result?.newick) {
      newickString.value = resp.result.newick;
    }
  }

  return {
    inputType, fileId, newickString, taskId, taskStatus,
    taskProgress, taskError, isBuilding, selectedNodeId,
    buildParams, vizConfig, treeStatistics, sequences,
    hasTree, needsAlignment, isTaskRunning,
    resetStore, setNewick, updateTaskStatus
  };
});
```

### 4.3 API 接口层 (api/phylo.ts)

```typescript
import client from './client';
import type { TaskResponse, TreeBuildParams } from '@/types/phylo';

/**
 * 上传序列文件 (FASTA 格式)
 */
export function uploadSequenceFile(file: File) {
  const formData = new FormData();
  formData.append('file', file);
  return client.post<{ fileId: string; sequences: Array<{ id: string; length: number }> }>(
    '/api/phylo/upload',
    formData,
    { headers: { 'Content-Type': 'multipart/form-data' } }
  );
}

/**
 * 上传 Newick 文件 (已有树)
 */
export function uploadNewickFile(file: File) {
  const formData = new FormData();
  formData.append('file', file);
  return client.post<{ fileId: string; newick: string }>(
    '/api/phylo/upload-newick',
    formData,
    { headers: { 'Content-Type': 'multipart/form-data' } }
  );
}

/**
 * 提交树构建任务
 */
export function submitTreeBuild(fileId: string, params: TreeBuildParams) {
  return client.post<TaskResponse>('/api/phylo/build', {
    fileId,
    ...params
  });
}

/**
 * 查询任务状态
 */
export function getTaskStatus(taskId: string) {
  return client.get<TaskResponse>(`/api/phylo/task/${taskId}`);
}

/**
 * 取消任务
 */
export function cancelTask(taskId: string) {
  return client.post(`/api/phylo/task/${taskId}/cancel`);
}

/**
 * 获取示例数据
 */
export function getExampleData() {
  return client.get<{ fileId: string; newick: string; sequences: Array<{ id: string; length: number }> }>(
    '/api/phylo/example'
  );
}
```

### 4.4 核心处理器 (utils/phyloProcessor.ts)

```typescript
/**
 * phyloProcessor.ts — 系统发育树数据处理引擎
 * 职责：Newick 解析、统计计算、可视化配置生成、phylotree.js 封装
 */

import { phylotree, phylotree_node } from 'phylotree';
import type { TreeStatistics, SequenceInfo, VizConfig, TreeNode } from '@/types/phylo';

// ───────────────────────────────────────────────
// 1. Newick 解析与转换
// ───────────────────────────────────────────────

/**
 * 解析 Newick 字符串为 phylotree 实例
 */
export function parseNewick(newickStr: string): typeof phylotree.prototype {
  try {
    const tree = new phylotree(newickStr.trim());
    return tree;
  } catch (err) {
    throw new Error(`Newick 解析失败: ${err instanceof Error ? err.message : String(err)}`);
  }
}

/**
 * 将 phylotree 节点结构转为普通 JSON (用于 ECharts 等备用渲染)
 */
export function treeToJson(node: phylotree_node): TreeNode {
  const result: TreeNode = {
    id: node.name || `node_${Math.random().toString(36).slice(2, 8)}`,
    name: node.name || '',
    branchLength: node.attribute || 0,
    bootstrap: node.confidence || undefined,
    isLeaf: !node.children || node.children.length === 0,
    children: undefined
  };

  if (node.children && node.children.length > 0) {
    result.children = node.children.map((child: phylotree_node) => treeToJson(child));
  }

  return result;
}

// ───────────────────────────────────────────────
// 2. 树统计信息计算
// ───────────────────────────────────────────────

/**
 * 计算树的完整统计信息
 */
export function computeTreeStatistics(tree: typeof phylotree.prototype): TreeStatistics {
  let sequenceCount = 0;
  let totalBranches = 0;
  let totalBranchLength = 0;
  let treeHeight = 0;
  let bootstrapValues: number[] = [];

  tree.traverse_and_compute((node: phylotree_node) => {
    // 后序遍历
    const bl = node.attribute || 0;
    totalBranchLength += bl;
    totalBranches++;

    if (!node.children || node.children.length === 0) {
      sequenceCount++;
    }

    if (node.confidence !== undefined && node.confidence !== null) {
      bootstrapValues.push(node.confidence);
    }

    // 计算到根的距离
    const rootToTip = computeRootToTipDistance(node);
    if (rootToTip > treeHeight) {
      treeHeight = rootToTip;
    }
  });

  const avgBranchLength = totalBranches > 0 ? totalBranchLength / totalBranches : 0;

  return {
    sequenceCount,
    treeHeight: Math.round(treeHeight * 10000) / 10000,
    totalBranches,
    avgBranchLength: Math.round(avgBranchLength * 10000) / 10000,
    minBootstrap: bootstrapValues.length > 0 ? Math.min(...bootstrapValues) : 0,
    maxBootstrap: bootstrapValues.length > 0 ? Math.max(...bootstrapValues) : 0,
    avgBootstrap: bootstrapValues.length > 0
      ? Math.round((bootstrapValues.reduce((a, b) => a + b, 0) / bootstrapValues.length) * 100) / 100
      : 0
  };
}

/**
 * 计算节点到根的距离
 */
function computeRootToTipDistance(node: phylotree_node): number {
  let distance = 0;
  let current: phylotree_node | undefined = node;
  while (current) {
    distance += current.attribute || 0;
    current = current.parent;
  }
  return distance;
}

/**
 * 从 phylotree 提取序列列表
 */
export function extractSequences(tree: typeof phylotree.prototype): SequenceInfo[] {
  const sequences: SequenceInfo[] = [];

  tree.traverse_and_compute((node: phylotree_node) => {
    if (!node.children || node.children.length === 0) {
      sequences.push({
        id: node.name || 'unknown',
        length: node.data?.length || 0,
        alignedLength: node.data?.alignedLength || 0
      });
    }
  });

  return sequences;
}

// ───────────────────────────────────────────────
// 3. 可视化配置生成
// ───────────────────────────────────────────────

/**
 * 根据暗黑模式和用户配置生成 phylotree.js 渲染选项
 */
export function createRenderOptions(
  vizConfig: VizConfig,
  isDark: boolean
): Record<string, unknown> {
  const colors = getThemeColors(isDark);

  return {
    width: 800,
    height: 600,
    'align-tips': vizConfig.alignTips,
    'draw-size-bubbles': false,
    'left-right-spacing': 'fixed-step',
    'top-bottom-spacing': 'fixed-step',
    'left-offset': 10,
    'show-scale': vizConfig.showScaleBar,
    brush: true,
    zoom: true,
    collapsible: true,
    selectable: true,
    reroot: true,
    hide: true,
    'color-fill': colors.nodeFill,
    'color-stroke': colors.branchStroke,
    'color-text': colors.text,
    'color-bootstrap': colors.bootstrap,
    'font-size': vizConfig.fontSize,
    'branch-width': vizConfig.branchWidth,
    layout: vizConfig.layout === 'rectangular' ? 'linear'
      : vizConfig.layout === 'radial' ? 'radial'
      : 'circular',
    // 最大半径限制（径向/圆形布局）
    'max-radius': vizConfig.layout === 'radial' ? 768 : undefined
  };
}

/**
 * 主题配色方案
 */
interface ThemeColors {
  background: string;
  branchStroke: string;
  nodeFill: string;
  nodeStroke: string;
  text: string;
  bootstrap: string;
  highlight: string;
  selection: string;
}

export function getThemeColors(isDark: boolean): ThemeColors {
  return isDark ? {
    background: '#0d0d0d',
    branchStroke: '#a0a0a0',
    nodeFill: '#63e2b7',
    nodeStroke: '#63e2b7',
    text: '#e0e0e0',
    bootstrap: '#f0a020',
    highlight: '#18a058',
    selection: '#2080f0'
  } : {
    background: '#ffffff',
    branchStroke: '#555555',
    nodeFill: '#18a058',
    nodeStroke: '#18a058',
    text: '#333333',
    bootstrap: '#f0a020',
    highlight: '#18a058',
    selection: '#2080f0'
  };
}

// ───────────────────────────────────────────────
// 4. phylotree.js 封装
// ───────────────────────────────────────────────

/**
 * phylotree.js 渲染封装类
 * 隔离 D3 DOM 操作，提供 Vue 友好的 API
 */
export class PhyloTreeRenderer {
  private tree: typeof phylotree.prototype | null = null;
  private container: HTMLElement | null = null;
  private svg: SVGSVGElement | null = null;
  private options: Record<string, unknown> = {};
  private selectionCallback?: (selected: phylotree_node[]) => void;

  /**
   * 初始化渲染器
   */
  init(container: HTMLElement, options: Record<string, unknown> = {}) {
    this.container = container;
    this.options = options;
    this.clear();
  }

  /**
   * 加载并渲染 Newick 树
   */
  render(newickStr: string, options: Record<string, unknown> = {}) {
    if (!this.container) return;

    this.clear();
    this.options = { ...this.options, ...options };

    try {
      this.tree = new phylotree(newickStr.trim());

      // 设置选择回调
      if (this.selectionCallback) {
        this.tree.selection_callback(this.selectionCallback);
      }

      // 执行渲染
      this.tree.render({
        container: this.container,
        ...this.options
      });

      // 获取渲染后的 SVG
      this.svg = this.container.querySelector('svg');
    } catch (err) {
      console.error('树渲染失败:', err);
      throw err;
    }
  }

  /**
   * 更新渲染选项（不重新解析树）
   */
  updateOptions(options: Record<string, unknown>) {
    if (!this.tree || !this.container) return;
    this.options = { ...this.options, ...options };
    this.tree.render({
      container: this.container,
      ...this.options
    });
  }

  /**
   * 设置选择回调
   */
  onSelect(callback: (selected: phylotree_node[]) => void) {
    this.selectionCallback = callback;
    if (this.tree) {
      this.tree.selection_callback(callback);
    }
  }

  /**
   * 根据 ID 高亮节点
   */
  highlightNode(nodeId: string) {
    if (!this.tree) return;

    let target: phylotree_node | null = null;
    this.tree.traverse_and_compute((node: phylotree_node) => {
      if (node.name === nodeId) {
        target = node;
      }
    });

    if (target) {
      // phylotree.js 选择节点
      this.tree.modify_selection([target]);
    }
  }

  /**
   * 折叠/展开节点
   */
  toggleCollapse(nodeId: string) {
    if (!this.tree) return;

    this.tree.traverse_and_compute((node: phylotree_node) => {
      if (node.name === nodeId && node.children) {
        node.collapsed = !node.collapsed;
      }
    });

    this.refresh();
  }

  /**
   * 阶梯化树
   */
  ladderize() {
    if (!this.tree) return;
    this.tree.ladderize();
    this.refresh();
  }

  /**
   * 重定根到指定节点
   */
  reroot(nodeId: string) {
    if (!this.tree) return;

    this.tree.traverse_and_compute((node: phylotree_node) => {
      if (node.name === nodeId) {
        this.tree?.reroot(node);
      }
    });

    this.refresh();
  }

  /**
   * 导出 SVG 字符串
   */
  exportSVG(): string {
    if (!this.svg) return '';
    const serializer = new XMLSerializer();
    return serializer.serializeToString(this.svg);
  }

  /**
   * 导出 PNG DataURL
   */
  exportPNG(): Promise<string> {
    return new Promise((resolve, reject) => {
      if (!this.svg) {
        reject(new Error('没有可导出的 SVG'));
        return;
      }

      const svgStr = this.exportSVG();
      const blob = new Blob([svgStr], { type: 'image/svg+xml;charset=utf-8' });
      const url = URL.createObjectURL(blob);

      const img = new Image();
      img.onload = () => {
        const canvas = document.createElement('canvas');
        const rect = this.svg!.getBoundingClientRect();
        canvas.width = rect.width * 2;
        canvas.height = rect.height * 2;
        const ctx = canvas.getContext('2d')!;
        ctx.scale(2, 2);
        ctx.fillStyle = this.options['color-background'] as string || '#ffffff';
        ctx.fillRect(0, 0, rect.width, rect.height);
        ctx.drawImage(img, 0, 0, rect.width, rect.height);
        URL.revokeObjectURL(url);
        resolve(canvas.toDataURL('image/png'));
      };
      img.onerror = reject;
      img.src = url;
    });
  }

  /**
   * 导出 Newick 字符串
   */
  exportNewick(): string {
    if (!this.tree) return '';
    return this.tree.get_newick();
  }

  /**
   * 刷新渲染
   */
  private refresh() {
    if (!this.tree || !this.container) return;
    this.tree.render({
      container: this.container,
      ...this.options
    });
  }

  /**
   * 清除渲染
   */
  clear() {
    if (this.container) {
      this.container.innerHTML = '';
    }
    this.svg = null;
  }

  /**
   * 销毁实例
   */
  destroy() {
    this.clear();
    this.tree = null;
    this.container = null;
    this.selectionCallback = undefined;
  }
}

// ───────────────────────────────────────────────
// 5. 工具函数
// ───────────────────────────────────────────────

/**
 * 解析 FASTA 文件获取序列信息
 */
export function parseFastaInfo(content: string): SequenceInfo[] {
  const sequences: SequenceInfo[] = [];
  const lines = content.split('\n');
  let currentId = '';
  let currentSeq = '';

  for (const line of lines) {
    const trimmed = line.trim();
    if (trimmed.startsWith('>')) {
      if (currentId) {
        sequences.push({ id: currentId, length: currentSeq.length, alignedLength: currentSeq.length });
      }
      currentId = trimmed.slice(1).split(' ')[0];
      currentSeq = '';
    } else if (trimmed) {
      currentSeq += trimmed;
    }
  }

  if (currentId) {
    sequences.push({ id: currentId, length: currentSeq.length, alignedLength: currentSeq.length });
  }

  return sequences;
}

/**
 * 验证 Newick 格式基本语法
 */
export function validateNewick(nwk: string): { valid: boolean; error?: string } {
  const trimmed = nwk.trim();
  if (!trimmed) return { valid: false, error: 'Newick 字符串为空' };

  let parenCount = 0;
  for (const char of trimmed) {
    if (char === '(') parenCount++;
    if (char === ')') parenCount--;
    if (parenCount < 0) return { valid: false, error: '括号不匹配：多余的右括号' };
  }

  if (parenCount !== 0) return { valid: false, error: '括号不匹配' };
  if (!trimmed.endsWith(';')) return { valid: false, error: 'Newick 字符串应以分号结尾' };

  return { valid: true };
}

/**
 * 格式化 bootstrap 值为百分比显示文本
 */
export function formatBootstrap(value: number): string {
  if (value >= 1) return `${Math.round(value)}%`;
  if (value > 0) return `${Math.round(value * 100)}%`;
  return '-';
}
```

### 4.5 主页面 (views/PhylogeneticTreeView.vue)

```vue
<script setup lang="ts">
/**
 * PhylogeneticTreeView.vue — 系统发育树构建工具主页面
 * 三栏布局：左参数 / 中工作区 / 右辅助
 */

import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue';
import {
  NButton, NUpload, NSelect, NInputNumber, NInput,
  NRadioGroup, NRadioButton, NSwitch, NProgress,
  NEmpty, NDataTable, NStatistic, NCollapse, NCollapseItem,
  NCard, NTooltip, NIcon, NAlert, NSpace, NDivider,
  useMessage, useDialog
} from 'naive-ui';
import {
  ArrowBack, Sparkles, Build, Download, Expand,
  Search, InformationCircle, Leaf, StatsChart,
  List, Settings, Resize, ImageOutline, CodeDownload
} from '@vicons/ionicons5';
import { useRouter } from 'vue-router';
import { usePhyloStore } from '@/stores/phyloStore';
import { useThemeStore } from '@/stores/themeStore';
import {
  PhyloTreeRenderer, parseNewick, computeTreeStatistics,
  extractSequences, createRenderOptions, parseFastaInfo,
  validateNewick, getThemeColors
} from '@/utils/phyloProcessor';
import {
  uploadSequenceFile, uploadNewickFile, submitTreeBuild,
  getTaskStatus, getExampleData, cancelTask
} from '@/api/phylo';
import type { UploadFileInfo } from 'naive-ui';
import type { TreeStatistics, SequenceInfo } from '@/types/phylo';

// ─── 依赖注入 ───
const router = useRouter();
const message = useMessage();
const dialog = useDialog();
const store = usePhyloStore();
const themeStore = useThemeStore();

// ─── Refs ───
const treeContainerRef = ref<HTMLElement | null>(null);
const rendererRef = ref<PhyloTreeRenderer | null>(null);
const pollingTimer = ref<ReturnType<typeof setInterval> | null>(null);
const isFullscreen = ref(false);
const searchKeyword = ref('');
const showAdvanced = ref(false);

// ─── 计算属性 ───
const isDark = computed(() => themeStore.isDark);
const hasTree = computed(() => store.hasTree);
const isBuilding = computed(() => store.isBuilding);
const taskProgress = computed(() => store.taskProgress);

// ─── 比对工具选项 ───
const alignmentToolOptions = [
  { label: 'MAFFT (快速)', value: 'mafft' },
  { label: 'ClustalOmega', value: 'clustalo' },
  { label: 'MUSCLE', value: 'muscle' },
  { label: '已比对 (跳过)', value: 'prealigned' }
];

// ─── 构建方法选项 ───
const treeMethodOptions = [
  { label: '邻接法 (NJ)', value: 'nj' },
  { label: 'UPGMA', value: 'upgma' },
  { label: '最大似然 (IQ-TREE)', value: 'ml_iqtree' },
  { label: '最大似然 (FastTree)', value: 'ml_fasttree' }
];

// ─── 替代模型选项（动态）───
const modelOptions = computed(() => {
  const method = store.buildParams.treeMethod;
  if (method === 'nj' || method === 'upgma') {
    return [
      { label: 'JC69', value: 'JC69' },
      { label: 'K2P', value: 'K2P' },
      { label: 'HKY', value: 'HKY' },
      { label: 'GTR', value: 'GTR' }
    ];
  }
  return [
    { label: 'GTR', value: 'GTR' },
    { label: 'GTR+Γ', value: 'GTR+G' },
    { label: 'GTR+I+Γ', value: 'GTR+I+G' }
  ];
});

// ─── 布局选项 ───
const layoutOptions = [
  { label: '矩形', value: 'rectangular' },
  { label: '圆形', value: 'circular' },
  { label: '径向', value: 'radial' }
];

// ─── 序列表格列 ───
const sequenceColumns = [
  { title: '序列ID', key: 'id', ellipsis: { tooltip: true } },
  { title: '长度', key: 'length', width: 80 }
];

// ─── 统计卡片数据 ───
const statCards = computed(() => [
  { label: '序列数量', value: store.treeStatistics.sequenceCount, icon: Leaf },
  { label: '树高', value: store.treeStatistics.treeHeight.toFixed(4), icon: StatsChart },
  { label: '总分支', value: store.treeStatistics.totalBranches, icon: GitBranch },
  { label: '平均分支长', value: store.treeStatistics.avgBranchLength.toFixed(4), icon: StatsChart }
]);

// ───────────────────────────────────────────────
// 生命周期
// ───────────────────────────────────────────────

onMounted(() => {
  // 初始化渲染器
  if (treeContainerRef.value) {
    rendererRef.value = new PhyloTreeRenderer();
    rendererRef.value.init(treeContainerRef.value, {
      zoom: true,
      brush: true,
      collapsible: true,
      selectable: true,
      reroot: true
    });

    // 设置选择回调
    rendererRef.value.onSelect((selected) => {
      if (selected.length > 0) {
        store.selectedNodeId = selected[0].name || '';
      }
    });
  }
});

onUnmounted(() => {
  stopPolling();
  rendererRef.value?.destroy();
});

// ─── 监听树数据变化 ───
watch(() => store.newickString, (nwk) => {
  if (nwk && rendererRef.value) {
    renderTree(nwk);
  }
});

// ─── 监听可视化配置变化 ───
watch(() => store.vizConfig, () => {
  if (store.newickString && rendererRef.value) {
    updateTreeStyle();
  }
}, { deep: true });

// ─── 监听暗黑模式 ───
watch(isDark, () => {
  if (store.newickString && rendererRef.value) {
    updateTreeStyle();
  }
});

// ───────────────────────────────────────────────
// 树渲染
// ───────────────────────────────────────────────

function renderTree(newickStr: string) {
  if (!rendererRef.value || !treeContainerRef.value) return;

  try {
    const options = createRenderOptions(store.vizConfig, isDark.value);
    rendererRef.value.render(newickStr, options);

    // 计算统计信息
    const tree = parseNewick(newickStr);
    store.treeStatistics = computeTreeStatistics(tree);
    store.sequences = extractSequences(tree);

    message.success('树渲染完成');
  } catch (err) {
    message.error(`渲染失败: ${err instanceof Error ? err.message : '未知错误'}`);
  }
}

function updateTreeStyle() {
  if (!rendererRef.value) return;
  const options = createRenderOptions(store.vizConfig, isDark.value);
  rendererRef.value.updateOptions(options);
}

// ───────────────────────────────────────────────
// 文件上传处理
// ───────────────────────────────────────────────

async function handleSequenceUpload({ file }: { file: UploadFileInfo }) {
  if (!file.file) return;

  try {
    message.loading('正在上传序列文件...');
    const resp = await uploadSequenceFile(file.file);
    store.fileId = resp.data.fileId;
    store.inputType = 'fasta';
    store.sequences = resp.data.sequences.map((s) => ({
      id: s.id,
      length: s.length,
      alignedLength: s.length
    }));
    message.success(`成功上传 ${resp.data.sequences.length} 条序列`);
  } catch (err) {
    message.error('上传失败');
  }
}

async function handleNewickUpload({ file }: { file: UploadFileInfo }) {
  if (!file.file) return;

  try {
    const content = await file.file.text();
    const validation = validateNewick(content);
    if (!validation.valid) {
      message.error(`Newick 格式错误: ${validation.error}`);
      return;
    }

    message.loading('正在上传 Newick 文件...');
    const resp = await uploadNewickFile(file.file);
    store.fileId = resp.data.fileId;
    store.inputType = 'newick';
    store.setNewick(resp.data.newick);
    message.success('Newick 文件上传成功');
  } catch (err) {
    message.error('上传失败');
  }
}

// ───────────────────────────────────────────────
// 示例数据
// ───────────────────────────────────────────────

async function loadExampleData() {
  try {
    store.resetStore();
    message.loading('正在加载示例数据...');
    const resp = await getExampleData();
    store.fileId = resp.data.fileId;
    store.inputType = 'example';
    store.setNewick(resp.data.newick);
    store.sequences = resp.data.sequences.map((s) => ({
      id: s.id,
      length: s.length,
      alignedLength: s.length
    }));
    message.success('示例数据加载成功');
  } catch (err) {
    message.error('加载示例数据失败');
  }
}

// ───────────────────────────────────────────────
// 树构建
// ───────────────────────────────────────────────

async function buildTree() {
  if (!store.fileId) {
    message.warning('请先上传序列文件');
    return;
  }

  store.isBuilding = true;
  store.taskStatus = 'pending';
  store.taskProgress = 0;

  try {
    const resp = await submitTreeBuild(store.fileId, store.buildParams);
    store.taskId = resp.data.taskId;
    store.taskStatus = 'running';
    startPolling();
  } catch (err) {
    store.isBuilding = false;
    message.error('任务提交失败');
  }
}

// ───────────────────────────────────────────────
// 轮询
// ───────────────────────────────────────────────

function startPolling() {
  stopPolling();
  pollingTimer.value = setInterval(async () => {
    if (!store.taskId) return;

    try {
      const resp = await getTaskStatus(store.taskId);
      store.updateTaskStatus(resp.data);

      if (resp.data.status === 'success') {
        stopPolling();
        store.isBuilding = false;
        message.success('系统发育树构建完成');
        // 树会自动通过 watch(newickString) 渲染
      } else if (resp.data.status === 'failed') {
        stopPolling();
        store.isBuilding = false;
        message.error(`构建失败: ${resp.data.error || '未知错误'}`);
      }
    } catch {
      // 继续轮询
    }
  }, 2000);
}

function stopPolling() {
  if (pollingTimer.value) {
    clearInterval(pollingTimer.value);
    pollingTimer.value = null;
  }
}

// ───────────────────────────────────────────────
// 导出功能
// ───────────────────────────────────────────────

async function exportPNG() {
  if (!rendererRef.value) return;
  try {
    const dataUrl = await rendererRef.value.exportPNG();
    const link = document.createElement('a');
    link.href = dataUrl;
    link.download = 'phylogenetic_tree.png';
    link.click();
    message.success('PNG 导出成功');
  } catch {
    message.error('导出失败');
  }
}

function exportSVG() {
  if (!rendererRef.value) return;
  try {
    const svgStr = rendererRef.value.exportSVG();
    const blob = new Blob([svgStr], { type: 'image/svg+xml' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'phylogenetic_tree.svg';
    link.click();
    URL.revokeObjectURL(url);
    message.success('SVG 导出成功');
  } catch {
    message.error('导出失败');
  }
}

function exportNewick() {
  if (!rendererRef.value) return;
  const nwk = rendererRef.value.exportNewick();
  const blob = new Blob([nwk], { type: 'text/plain' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = 'tree.nwk';
  link.click();
  URL.revokeObjectURL(url);
  message.success('Newick 导出成功');
}

// ───────────────────────────────────────────────
// 全屏
// ───────────────────────────────────────────────

function toggleFullscreen() {
  const el = treeContainerRef.value;
  if (!el) return;

  if (!document.fullscreenElement) {
    el.requestFullscreen?.();
    isFullscreen.value = true;
  } else {
    document.exitFullscreen?.();
    isFullscreen.value = false;
  }
}

// ───────────────────────────────────────────────
// 节点搜索
// ───────────────────────────────────────────────

function handleSearch() {
  const keyword = searchKeyword.value.trim();
  if (!keyword || !rendererRef.value) return;
  rendererRef.value.highlightNode(keyword);
}

// ───────────────────────────────────────────────
// 返回工具箱
// ───────────────────────────────────────────────

function goBack() {
  dialog.warning({
    title: '确认返回',
    content: '返回工具箱将丢失当前数据，是否继续？',
    positiveText: '确认',
    negativeText: '取消',
    onPositiveClick: () => {
      store.resetStore();
      router.push('/tools');
    }
  });
}
</script>

<template>
  <div class="phylo-page">
    <!-- ═══════════════════════════════════════════ -->
    <!-- Toolbar                                   -->
    <!-- ═══════════════════════════════════════════ -->
    <div class="phylo-toolbar">
      <NButton quaternary circle @click="goBack">
        <template #icon>
          <NIcon><ArrowBack /></NIcon>
        </template>
      </NButton>
      <h2 class="phylo-title">系统发育树构建</h2>
      <NButton dashed size="small" @click="loadExampleData">
        <template #icon>
          <NIcon><Sparkles /></NIcon>
        </template>
        示例数据
      </NButton>
    </div>

    <!-- ═══════════════════════════════════════════ -->
    <!-- 三栏主布局                                 -->
    <!-- ═══════════════════════════════════════════ -->
    <div class="phylo-container">
      <!-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ -->
      <!-- 左侧面板：参数配置                        -->
      <!-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ -->
      <div class="param-panel">
        <!-- 数据输入 -->
        <NCollapse default-expanded-names="['data-input']">
          <NCollapseItem name="data-input" title="数据输入">
            <NSpace vertical>
              <NUpload
                accept=".fasta,.fa,.fna"
                :max="1"
                :custom-request="handleSequenceUpload"
              >
                <NButton block>
                  <template #icon><NIcon><CodeDownload /></NIcon></template>
                  上传 FASTA 序列
                </NButton>
              </NUpload>

              <NUpload
                accept=".nwk,.newick,.tre,.tree"
                :max="1"
                :custom-request="handleNewickUpload"
              >
                <NButton block secondary>
                  <template #icon><NIcon><List /></NIcon></template>
                  上传 Newick 文件
                </NButton>
              </NUpload>

              <NButton block dashed @click="loadExampleData">
                <template #icon><NIcon><Sparkles /></NIcon></template>
                加载示例数据
              </NButton>

              <!-- 已上传文件信息 -->
              <NAlert
                v-if="store.fileId"
                type="success"
                :show-icon="false"
                size="small"
              >
                已加载 {{ store.sequences.length }} 条序列
              </NAlert>
            </NSpace>
          </NCollapseItem>

          <!-- 比对配置 -->
          <NCollapseItem
            name="alignment"
            title="比对配置"
            :disabled="store.inputType === 'newick'"
          >
            <NSpace vertical>
              <div class="param-row">
                <label>比对工具</label>
                <NSelect
                  v-model:value="store.buildParams.alignmentTool"
                  :options="alignmentToolOptions"
                  size="small"
                />
              </div>

              <template v-if="store.buildParams.alignmentTool === 'mafft'">
                <div class="param-row">
                  <label>策略</label>
                  <NSelect
                    :value="'auto'"
                    :options="[
                      { label: '自动', value: 'auto' },
                      { label: 'L-INS-i (精确)', value: 'linsi' },
                      { label: 'FFT-NS-2 (快速)', value: 'fftns2' }
                    ]"
                    size="small"
                  />
                </div>
              </template>

              <template v-if="store.buildParams.alignmentTool === 'clustalo'">
                <div class="param-row">
                  <label>迭代次数</label>
                  <NInputNumber :value="1" :min="0" :max="5" size="small" />
                </div>
              </template>
            </NSpace>
          </NCollapseItem>

          <!-- 树构建配置 -->
          <NCollapseItem name="tree-build" title="树构建配置">
            <NSpace vertical>
              <div class="param-row">
                <label>构建方法</label>
                <NSelect
                  v-model:value="store.buildParams.treeMethod"
                  :options="treeMethodOptions"
                  size="small"
                />
              </div>

              <div class="param-row">
                <label>替代模型</label>
                <NSelect
                  v-model:value="store.buildParams.substitutionModel"
                  :options="modelOptions"
                  size="small"
                />
              </div>

              <div class="param-row">
                <label>Bootstrap 次数</label>
                <NInputNumber
                  v-model:value="store.buildParams.bootstrap"
                  :min="100"
                  :max="10000"
                  :step="100"
                  size="small"
                />
              </div>

              <div class="param-row">
                <NSwitch v-model:value="showAdvanced" size="small">
                  <template #checked>高级参数</template>
                  <template #unchecked>高级参数</template>
                </NSwitch>
              </div>

              <NInput
                v-if="showAdvanced"
                v-model:value="store.buildParams.advancedParams"
                type="textarea"
                placeholder="输入额外命令行参数..."
                :rows="3"
                size="small"
              />
            </NSpace>
          </NCollapseItem>

          <!-- 可视化配置 -->
          <NCollapseItem name="viz-config" title="可视化配置">
            <NSpace vertical>
              <div class="param-row">
                <label>布局</label>
                <NRadioGroup v-model:value="store.vizConfig.layout" size="small">
                  <NRadioButton value="rectangular">矩形</NRadioButton>
                  <NRadioButton value="circular">圆形</NRadioButton>
                  <NRadioButton value="radial">径向</NRadioButton>
                </NRadioGroup>
              </div>

              <div class="param-row">
                <label>有根树</label>
                <NSwitch v-model:value="store.vizConfig.isRooted" size="small" />
              </div>

              <div class="param-row">
                <label>显示标签</label>
                <NSwitch v-model:value="store.vizConfig.showLabels" size="small" />
              </div>

              <div class="param-row">
                <label>Bootstrap 值</label>
                <NSwitch v-model:value="store.vizConfig.showBootstrap" size="small" />
              </div>

              <div class="param-row">
                <label>比例尺</label>
                <NSwitch v-model:value="store.vizConfig.showScaleBar" size="small" />
              </div>

              <div class="param-row">
                <label>对齐末端</label>
                <NSwitch v-model:value="store.vizConfig.alignTips" size="small" />
              </div>

              <div class="param-row">
                <label>分支宽度</label>
                <NInputNumber
                  v-model:value="store.vizConfig.branchWidth"
                  :min="0.5"
                  :max="5"
                  :step="0.5"
                  size="small"
                />
              </div>

              <div class="param-row">
                <label>字体大小</label>
                <NInputNumber
                  v-model:value="store.vizConfig.fontSize"
                  :min="8"
                  :max="20"
                  :step="1"
                  size="small"
                />
              </div>
            </NSpace>
          </NCollapseItem>
        </NCollapse>

        <NDivider />

        <!-- 构建按钮 -->
        <NButton
          type="primary"
          block
          size="large"
          :loading="isBuilding"
          :disabled="!store.fileId || store.inputType === 'newick'"
          @click="buildTree"
        >
          <template #icon>
            <NIcon><Build /></NIcon>
          </template>
          {{ isBuilding ? '构建中...' : '构建系统发育树' }}
        </NButton>

        <NAlert
          v-if="store.inputType === 'newick'"
          type="info"
          size="small"
          :show-icon="false"
          style="margin-top: 8px"
        >
          已上传 Newick 文件，无需构建
        </NAlert>

        <!-- 进度条 -->
        <div v-if="isBuilding" class="progress-area">
          <NProgress
            type="line"
            :percentage="taskProgress"
            :indicator-placement="'inside'"
            processing
          />
          <div class="progress-text">正在构建系统发育树... {{ taskProgress }}%</div>
        </div>
      </div>

      <!-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ -->
      <!-- 中间工作区：树可视化                       -->
      <!-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ -->
      <div class="work-area">
        <!-- 工具条 -->
        <div class="work-toolbar">
          <NSpace>
            <NButton
              type="primary"
              :loading="isBuilding"
              :disabled="!store.fileId || store.inputType === 'newick'"
              @click="buildTree"
            >
              <template #icon><NIcon><Build /></NIcon></template>
              构建系统发育树
            </NButton>

            <NButton
              secondary
              :disabled="!hasTree"
              @click="exportPNG"
            >
              <template #icon><NIcon><ImageOutline /></NIcon></template>
              PNG
            </NButton>

            <NButton
              secondary
              :disabled="!hasTree"
              @click="exportSVG"
            >
              <template #icon><NIcon><CodeDownload /></NIcon></template>
              SVG
            </NButton>

            <NButton
              secondary
              :disabled="!hasTree"
              @click="exportNewick"
            >
              <template #icon><NIcon><List /></NIcon></template>
              Newick
            </NButton>

            <NButton
              quaternary
              circle
              :disabled="!hasTree"
              @click="toggleFullscreen"
            >
              <template #icon><NIcon><Expand /></NIcon></template>
            </NButton>
          </NSpace>
        </div>

        <!-- 树渲染区域 -->
        <div
          ref="treeContainerRef"
          class="tree-container"
          :class="{ 'dark-theme': isDark, 'light-theme': !isDark }"
        >
          <!-- 空状态 -->
          <NEmpty
            v-if="!hasTree"
            description="请上传序列文件或加载示例数据"
            class="tree-empty"
          >
            <template #extra>
              <NSpace>
                <NButton @click="loadExampleData">
                  <template #icon><NIcon><Sparkles /></NIcon></template>
                  加载示例数据
                </NButton>
              </NSpace>
            </template>
          </NEmpty>
        </div>

        <!-- 错误提示 -->
        <NAlert
          v-if="store.taskError"
          type="error"
          closable
          @close="store.taskError = ''"
        >
          {{ store.taskError }}
        </NAlert>
      </div>

      <!-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ -->
      <!-- 右侧面板：辅助信息                         -->
      <!-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ -->
      <div class="side-panel">
        <!-- 树统计信息 -->
        <NCard title="树统计" size="small" class="stat-card">
          <div class="stat-grid">
            <div class="stat-item">
              <div class="stat-label">序列数量</div>
              <div class="stat-value">{{ store.treeStatistics.sequenceCount }}</div>
            </div>
            <div class="stat-item">
              <div class="stat-label">树高</div>
              <div class="stat-value">{{ store.treeStatistics.treeHeight.toFixed(4) }}</div>
            </div>
            <div class="stat-item">
              <div class="stat-label">总分支</div>
              <div class="stat-value">{{ store.treeStatistics.totalBranches }}</div>
            </div>
            <div class="stat-item">
              <div class="stat-label">平均分支长</div>
              <div class="stat-value">{{ store.treeStatistics.avgBranchLength.toFixed(4) }}</div>
            </div>
          </div>

          <NDivider v-if="store.treeStatistics.maxBootstrap > 0" />

          <div v-if="store.treeStatistics.maxBootstrap > 0" class="stat-grid">
            <div class="stat-item">
              <div class="stat-label">Bootstrap 均值</div>
              <div class="stat-value">{{ store.treeStatistics.avgBootstrap }}%</div>
            </div>
            <div class="stat-item">
              <div class="stat-label">Bootstrap 范围</div>
              <div class="stat-value">
                {{ store.treeStatistics.minBootstrap }}-{{ store.treeStatistics.maxBootstrap }}%
              </div>
            </div>
          </div>
        </NCard>

        <!-- 节点搜索 -->
        <NCard title="节点搜索" size="small" class="search-card">
          <NInput
            v-model:value="searchKeyword"
            placeholder="输入节点 ID..."
            size="small"
            @keyup.enter="handleSearch"
          >
            <template #suffix>
              <NButton text size="tiny" @click="handleSearch">
                <NIcon><Search /></NIcon>
              </NButton>
            </template>
          </NInput>
        </NCard>

        <!-- 序列列表 -->
        <NCard title="序列列表" size="small" class="sequence-card">
          <NDataTable
            :columns="sequenceColumns"
            :data="store.sequences"
            :max-height="300"
            size="small"
            :pagination="{ pageSize: 10 }"
          />
        </NCard>

        <!-- 操作提示 -->
        <NAlert type="info" size="small" :show-icon="false">
          <template #header>
            <NIcon><InformationCircle /></NIcon> 操作提示
          </template>
          <ul class="tip-list">
            <li>鼠标滚轮缩放树形图</li>
            <li>拖拽平移视图</li>
            <li>点击节点折叠/展开子树</li>
            <li>右键点击节点可重定根</li>
            <li>框选多个分支</li>
          </ul>
        </NAlert>
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
// ───────────────────────────────────────────────
// 根容器
// ───────────────────────────────────────────────
.phylo-page {
  padding: 16px;
  width: 100%;
  box-sizing: border-box;
}

// ─── Toolbar ───
.phylo-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;

  .phylo-title {
    flex: 1;
    font-size: 18px;
    font-weight: 600;
    margin: 0;
    color: var(--n-text-color);
  }
}

// ─── 三栏布局 ───
.phylo-container {
  display: grid;
  grid-template-columns: 300px 1fr 280px;
  gap: 12px;
  align-items: start;
}

// ─── 左侧面板 ───
.param-panel {
  background: var(--n-card-color);
  border-radius: 12px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;

  :deep(.n-collapse .n-collapse-item) {
    margin-bottom: 4px;
  }

  .param-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    min-height: 32px;

    label {
      font-size: 13px;
      color: var(--n-text-color-2);
      white-space: nowrap;
    }

    .n-select,
    .n-input-number {
      width: 140px;
    }

    .n-radio-group {
      flex-shrink: 0;
    }
  }

  .progress-area {
    margin-top: 8px;

    .progress-text {
      font-size: 12px;
      color: var(--n-text-color-3);
      text-align: center;
      margin-top: 4px;
    }
  }
}

// ─── 中间工作区 ───
.work-area {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-height: 600px;

  .work-toolbar {
    background: var(--n-card-color);
    border-radius: 12px;
    padding: 8px 12px;
    display: flex;
    align-items: center;
  }

  .tree-container {
    flex: 1;
    background: var(--n-card-color);
    border-radius: 12px;
    padding: 12px;
    min-height: 500px;
    position: relative;
    overflow: hidden;

    // phylotree.js SVG 自适应
    :deep(svg) {
      width: 100%;
      height: 100%;
      min-height: 480px;
    }

    // 暗黑模式下的 SVG 样式
    &.dark-theme :deep(svg) {
      background: #0d0d0d;

      text {
        fill: #e0e0e0;
      }

      path.branch {
        stroke: #a0a0a0;
      }

      circle.node {
        fill: #63e2b7;
        stroke: #63e2b7;
      }

      .bootstrap-value {
        fill: #f0a020;
      }
    }

    &.light-theme :deep(svg) {
      background: #ffffff;

      text {
        fill: #333333;
      }

      path.branch {
        stroke: #555555;
      }

      circle.node {
        fill: #18a058;
        stroke: #18a058;
      }

      .bootstrap-value {
        fill: #f0a020;
      }
    }
  }

  .tree-empty {
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
  }
}

// ─── 右侧面板 ───
.side-panel {
  display: flex;
  flex-direction: column;
  gap: 10px;

  .stat-card {
    :deep(.n-card__content) {
      padding: 10px;
    }
  }

  .stat-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
  }

  .stat-item {
    text-align: center;
    padding: 6px;
    background: var(--n-action-color);
    border-radius: 8px;

    .stat-label {
      font-size: 11px;
      color: var(--n-text-color-3);
      margin-bottom: 2px;
    }

    .stat-value {
      font-size: 16px;
      font-weight: 600;
      color: var(--n-text-color);
    }
  }

  .search-card,
  .sequence-card {
    :deep(.n-card__content) {
      padding: 10px;
    }
  }

  .tip-list {
    margin: 0;
    padding-left: 16px;
    font-size: 12px;
    color: var(--n-text-color-2);

    li {
      margin-bottom: 4px;
    }
  }
}

// ─── 响应式 ───
@media (max-width: 1200px) {
  .phylo-container {
    grid-template-columns: 1fr;
  }

  .param-panel,
  .side-panel {
    order: unset;
  }
}

// ─── 全屏模式 ───
:fullscreen .tree-container {
  width: 100vw;
  height: 100vh;
  border-radius: 0;
}
</style>
```

### 4.6 树渲染器组件封装 (components/PhyloTreeRenderer.vue)

```vue
<script setup lang="ts">
/**
 * PhyloTreeRenderer.vue — phylotree.js 的 Vue 3 组件封装
 * 职责：将 D3/SVG 操作隔离在此组件内，对外暴露 Vue 友好的接口
 */

import { ref, onMounted, onUnmounted, watch } from 'vue';
import {
  PhyloTreeRenderer as PhyloRenderer,
  createRenderOptions,
  getThemeColors
} from '@/utils/phyloProcessor';
import type { VizConfig } from '@/types/phylo';
import type { phylotree_node } from 'phylotree';

// ─── Props ───
interface Props {
  newickString: string;
  vizConfig: VizConfig;
  isDark: boolean;
}

const props = defineProps<Props>();

// ─── Emits ───
const emit = defineEmits<{
  (e: 'select', nodes: phylotree_node[]): void;
  (e: 'rendered', stats: { nodeCount: number }): void;
  (e: 'error', error: Error): void;
}>();

// ─── Refs ───
const containerRef = ref<HTMLElement | null>(null);
const renderer = ref<PhyloRenderer | null>(null);

// ─── 生命周期 ───
onMounted(() => {
  if (containerRef.value) {
    renderer.value = new PhyloRenderer();
    renderer.value.init(containerRef.value);
    renderer.value.onSelect((nodes) => {
      emit('select', nodes);
    });

    // 如果已有数据，立即渲染
    if (props.newickString) {
      doRender();
    }
  }
});

onUnmounted(() => {
  renderer.value?.destroy();
});

// ─── 监听 ───
watch(() => props.newickString, (val) => {
  if (val) doRender();
});

watch(() => props.vizConfig, () => {
  doUpdate();
}, { deep: true });

watch(() => props.isDark, () => {
  doUpdate();
});

// ─── 渲染逻辑 ───
function doRender() {
  if (!renderer.value || !props.newickString) return;
  try {
    const options = createRenderOptions(props.vizConfig, props.isDark);
    renderer.value.render(props.newickString, options);
    emit('rendered', { nodeCount: 0 }); // 可通过 phylotree API 获取
  } catch (err) {
    emit('error', err instanceof Error ? err : new Error(String(err)));
  }
}

function doUpdate() {
  if (!renderer.value) return;
  const options = createRenderOptions(props.vizConfig, props.isDark);
  renderer.value.updateOptions(options);
}

// ─── 暴露方法 ───
defineExpose({
  exportPNG: () => renderer.value?.exportPNG(),
  exportSVG: () => renderer.value?.exportSVG(),
  exportNewick: () => renderer.value?.exportNewick(),
  highlightNode: (id: string) => renderer.value?.highlightNode(id),
  ladderize: () => renderer.value?.ladderize(),
  reroot: (id: string) => renderer.value?.reroot(id)
});
</script>

<template>
  <div
    ref="containerRef"
    class="phylo-renderer"
    :class="{ dark: isDark, light: !isDark }"
  />
</template>

<style scoped lang="scss">
.phylo-renderer {
  width: 100%;
  height: 100%;
  min-height: 400px;

  :deep(svg) {
    width: 100%;
    height: 100%;
  }

  &.dark :deep(svg) {
    background: #0d0d0d;
  }

  &.light :deep(svg) {
    background: #ffffff;
  }
}
</style>
```

---

## 五、暗黑模式适配方案

### 5.1 主题色映射

| 元素 | 亮色模式 | 暗黑模式 |
|------|---------|---------|
| SVG 背景 | `#ffffff` | `#0d0d0d` |
| 分支线条 | `#555555` | `#a0a0a0` |
| 节点填充 | `#18a058` | `#63e2b7` |
| 节点描边 | `#18a058` | `#63e2b7` |
| 标签文字 | `#333333` | `#e0e0e0` |
| Bootstrap 值 | `#f0a020` | `#f0a020` |
| 选中高亮 | `#2080f0` | `#2080f0` |
| 比例尺 | `#666666` | `#999999` |

### 5.2 动态切换实现

phylotree.js 的样式定制有两种方式：

1. **CSS 类切换**（推荐）：通过容器元素的 `dark`/`light` class 控制子 SVG 元素样式
2. **JavaScript callback**：通过 `createRenderOptions` 生成动态配置

在 `phyloProcessor.ts` 中，`createRenderOptions` 函数接收 `isDark` 参数，生成对应的配色配置。同时，Vue 组件通过 CSS 深度选择器 (`:deep`) 覆盖 SVG 内部样式。

### 5.3 监听与重渲染

```typescript
// 在 PhylogeneticTreeView.vue 中
watch(isDark, () => {
  if (store.newickString && rendererRef.value) {
    updateTreeStyle();  // 重新应用主题色
  }
});
```

---

## 六、与后端交互的数据流

### 6.1 数据流时序图

```
用户                    前端 (Vue)                  后端 (API)                Celery
 │                         │                           │                       │
 │── 选择 FASTA 文件 ─────>│                           │                       │
 │                         │── uploadSequenceFile() ──>│                       │
 │                         │                           │── 保存文件 ──────────>│
 │                         │<── file_id + sequences ───│                       │
 │<── 显示序列数量 ────────│                           │                       │
 │                         │                           │                       │
 │── 配置参数 ────────────>│                           │                       │
 │── 点击[构建] ──────────>│                           │                       │
 │                         │── submitTreeBuild() ─────>│                       │
 │                         │                           │── 提交 Celery 任务 ──>│
 │                         │<── task_id ───────────────│                       │
 │                         │                           │                       │
 │                         │◄──── 轮询 (每2s) ─────────│◄── 查询进度 ─────────│
 │<── 进度条更新 ─────────│                           │                       │
 │                         │                           │                       │
 │                         │◄──── 任务完成 ────────────│◄── 结果就绪 ─────────│
 │                         │                           │                       │
 │                         │── getResult() ───────────>│                       │
 │                         │<── Newick 字符串 ─────────│                       │
 │                         │                           │                       │
 │<── 渲染树形图 ─────────│                           │                       │
 │<── 显示统计信息 ───────│                           │                       │
```

### 6.2 轮询逻辑

```typescript
// 已集成在 PhylogeneticTreeView.vue 的 startPolling / stopPolling 函数中

const POLL_INTERVAL = 2000; // 2秒
const MAX_POLL_COUNT = 900; // 最多轮询30分钟

function startPolling() {
  let count = 0;
  stopPolling();

  pollingTimer.value = setInterval(async () => {
    count++;
    if (count > MAX_POLL_COUNT) {
      stopPolling();
      store.taskStatus = 'timeout';
      store.isBuilding = false;
      message.error('任务超时，请稍后重试');
      return;
    }

    const resp = await getTaskStatus(store.taskId);
    store.updateTaskStatus(resp.data);

    if (resp.data.status === 'success') {
      stopPolling();
      store.isBuilding = false;
      // watch(newickString) 会自动触发渲染
    } else if (resp.data.status === 'failed') {
      stopPolling();
      store.isBuilding = false;
    }
  }, POLL_INTERVAL);
}
```

### 6.3 错误处理策略

| 错误类型 | 处理方式 |
|---------|---------|
| 文件上传失败 | NAlert 显示错误信息 |
| Newick 格式错误 | 上传前前端验证，提示具体语法错误 |
| 任务提交失败 | NMessage 提示，保持参数不变 |
| 任务执行失败 | NAlert 显示后端返回的错误详情 |
| 任务超时 | 自动停止轮询，提示用户重试 |
| 渲染失败 | NMessage 提示，保留数据允许重新配置 |

---

## 七、路由与菜单配置

### 7.1 路由注册

```typescript
// router/index.ts
{
  path: '/tools/phylogenetic-tree',
  name: 'PhylogeneticTree',
  component: () => import('@/views/PhylogeneticTreeView.vue'),
  meta: {
    title: '系统发育树构建',
    icon: 'GitNetwork',  // ionicons5 图标名
    category: 'evolution',
    requiresAuth: true
  }
}
```

### 7.2 菜单项

```typescript
// 工具箱菜单配置
{
  key: 'phylogenetic-tree',
  label: '系统发育树构建',
  icon: renderIcon(GitNetwork),
  path: '/tools/phylogenetic-tree',
  description: '多序列比对与系统发育树构建可视化'
}
```

---

## 八、依赖安装清单

```bash
# 核心可视化库
npm install phylotree

# D3.js 类型声明 (phylotree 依赖)
npm install -D @types/d3

# 如需 PhyloJS 作为辅助解析库
npm install phylo
```

### package.json 依赖项

```json
{
  "dependencies": {
    "vue": "^3.4.0",
    "vue-router": "^4.2.0",
    "pinia": "^2.1.0",
    "naive-ui": "^2.38.0",
    "@vicons/ionicons5": "^0.12.0",
    "phylotree": "^1.4.0",
    "axios": "^1.6.0"
  },
  "devDependencies": {
    "typescript": "^5.3.0",
    "vite": "^5.0.0",
    "@vitejs/plugin-vue": "^5.0.0",
    "@types/d3": "^7.4.0",
    "sass": "^1.70.0"
  }
}
```

---

## 九、性能优化建议

### 9.1 大型树优化

| 策略 | 实现方式 |
|------|---------|
| 虚拟滚动 | 序列列表使用 NDataTable 内置虚拟滚动 |
| 延迟渲染 | 初始只渲染前 2 层节点，点击展开时渲染子树 |
| SVG 缓存 | phylotree.js 内部已优化，避免不必要的重绘 |
| 降级方案 | >5000 tips 时提示用户或切换至 phylocanvas.gl |

### 9.2 内存管理

- 组件卸载时调用 `renderer.destroy()` 释放 D3 事件监听
- 停止轮询避免内存泄漏
- 大文件上传使用分片上传

### 9.3 构建任务优化

- 后端使用 Celery 异步执行，前端轮询进度
- 支持任务取消（用户离开页面时）
- 构建结果缓存（相同参数直接返回缓存结果）

---

## 十、测试要点

| 测试项 | 内容 |
|--------|------|
| Newick 解析 | 各种格式变体（有/无分支长度、有/无 bootstrap、引号标签） |
| 文件上传 | FASTA 格式验证、大文件处理、非法文件提示 |
| 参数联动 | 构建方法改变时代联模型选项更新 |
| 暗黑模式 | 切换主题时 SVG 颜色正确更新 |
| 导出功能 | PNG/SVG/Newick 导出内容完整性 |
| 响应式 | 1200px 以下布局正确退化 |
| 轮询逻辑 | 任务成功/失败/超时各分支处理 |
| 内存泄漏 | 反复上传/渲染/卸载无内存增长 |

---

## 附录：phylotree.js 关键 API 速查

```typescript
import { phylotree } from 'phylotree';

// 1. 解析与创建
const tree = new phylotree(newickString);

// 2. 渲染
tree.render({
  container: '#tree-container',  // CSS 选择器或 DOM 元素
  width: 800,
  height: 600,
  zoom: true,                    // 启用缩放
  brush: true,                   // 启用框选
  collapsible: true,             // 可折叠节点
  selectable: true,              // 可选择分支
  reroot: true,                  // 可重定根
  'align-tips': true,            // 末端对齐
  'show-scale': true             // 显示比例尺
});

// 3. 遍历
tree.traverse_and_compute(callback, traversalType);
// traversalType: 'pre-order' | 'post-order'

// 4. 选择回调
tree.selection_callback((selectedNodes) => {
  console.log('选中节点:', selectedNodes);
});

// 5. 布局操作
tree.ladderize();           // 阶梯化
tree.reroot(node);          // 重定根
tree.update();              // 更新渲染

// 6. 导入/导出
const newick = tree.get_newick();  // 导出 Newick

// 7. 节点属性访问
node.name           // 节点名称
node.attribute      // 分支长度
node.confidence     // Bootstrap 值
node.children       // 子节点数组
node.parent         // 父节点
node.collapsed      // 是否折叠
```

---

> **文档版本**: v1.0
> **编写日期**: 2025
> **适配技术栈**: Vue 3.4 + TypeScript 5.3 + Naive UI 2.38 + phylotree.js 1.4
