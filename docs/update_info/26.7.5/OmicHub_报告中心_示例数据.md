# OmicHub 报告中心示例数据与优化建议

## 一、示例数据文件

将以下代码保存到 `src/pages/ReportCenter/mockData.ts`：

```typescript
// src/pages/ReportCenter/mockData.ts
// 示例报告数据 - 用于前端开发和演示

import { Report } from "@/types/report";

export const mockReports: Report[] = [
  {
    id: "report_001",
    taskId: "task_20260705_001",
    flowId: "rna_seq",
    flowName: "RNA-seq 差异表达分析",
    flowVersion: "v2.2.0",
    flowIcon: "🧬",
    title: "RNA-seq 差异表达分析报告 - 拟南芥盐胁迫处理",
    description: "基于 RNAFlow 流程（STAR + RSEM + DESeq2）的标准 RNA-seq 差异表达分析。对比盐胁迫处理组与对照组，共鉴定出 1,247 个差异表达基因。",
    status: "completed",
    createdAt: "2026-07-05T14:32:00Z",
    completedAt: "2026-07-05T14:45:00Z",
    sampleCount: 12,
    duration: 780, // 13分钟
    files: [
      {
        id: "file_001",
        name: "differential_expression_report.html",
        type: "html",
        size: 2847563,
        url: "/reports/report_001/files/file_001",
        isPrimary: true,
      },
      {
        id: "file_002",
        name: "volcano_plot.pdf",
        type: "pdf",
        size: 1567800,
        url: "/reports/report_001/files/file_002",
        isPrimary: false,
      },
      {
        id: "file_003",
        name: "heatmap_top50.png",
        type: "png",
        size: 892300,
        url: "/reports/report_001/files/file_003",
        isPrimary: false,
      },
      {
        id: "file_004",
        name: "deseq2_results.csv",
        type: "csv",
        size: 456700,
        url: "/reports/report_001/files/file_004",
        isPrimary: false,
      },
    ],
    tags: ["rnaseq", "differential-expression", "arabidopsis"],
    isRead: true,
    isStarred: true,
  },
  {
    id: "report_002",
    taskId: "task_20260705_002",
    flowId: "atac_seq",
    flowName: "ATAC-seq 染色质可及性分析",
    flowVersion: "v0.0.5",
    flowIcon: "🧪",
    title: "ATAC-seq 染色质可及性分析报告 - 水稻根尖发育",
    description: "基于 ATACFlow 流程（Bowtie2/Chromap + MACS2 + TOBIAS）的染色质可及性分析。识别出 3,456 个开放染色质区域，发现 128 个转录因子结合位点。",
    status: "completed",
    createdAt: "2026-07-04T09:15:00Z",
    completedAt: "2026-07-04T09:47:00Z",
    sampleCount: 6,
    duration: 1920, // 32分钟
    files: [
      {
        id: "file_005",
        name: "atac_report.html",
        type: "html",
        size: 4218900,
        url: "/reports/report_002/files/file_005",
        isPrimary: true,
      },
      {
        id: "file_006",
        name: "peak_annotations.pdf",
        type: "pdf",
        size: 2345600,
        url: "/reports/report_002/files/file_006",
        isPrimary: false,
      },
    ],
    tags: ["atacseq", "chromatin-accessibility", "rice"],
    isRead: false,
    isStarred: false,
  },
  {
    id: "report_003",
    taskId: "task_20260705_003",
    flowId: "rna_seq",
    flowName: "RNA-seq 差异表达分析",
    flowVersion: "v2.2.0",
    flowIcon: "🧬",
    title: "RNA-seq 差异表达分析报告 - 生菜冷胁迫响应",
    description: "基于 RNAFlow 流程的标准 RNA-seq 分析。生菜在 4°C 冷胁迫处理 24h 后与对照组对比，鉴定出 892 个差异表达基因，涉及冷响应通路。",
    status: "generating",
    createdAt: "2026-07-05T16:20:00Z",
    completedAt: undefined,
    sampleCount: 8,
    duration: 0,
    files: [],
    tags: ["rnaseq", "cold-stress", "lettuce"],
    isRead: false,
    isStarred: false,
  },
  {
    id: "report_004",
    taskId: "task_20260703_001",
    flowId: "rna_seq",
    flowName: "RNA-seq 差异表达分析",
    flowVersion: "v2.1.0",
    flowIcon: "🧬",
    title: "RNA-seq 差异表达分析报告 - 番茄果实成熟",
    description: "番茄果实不同成熟阶段的转录组分析。比较绿熟期、破色期、红熟期三个阶段的基因表达差异，发现 2,156 个与果实成熟相关的差异表达基因。",
    status: "completed",
    createdAt: "2026-07-03T10:00:00Z",
    completedAt: "2026-07-03T10:28:00Z",
    sampleCount: 9,
    duration: 1680, // 28分钟
    files: [
      {
        id: "file_007",
        name: "tomato_ripening_report.html",
        type: "html",
        size: 3567200,
        url: "/reports/report_004/files/file_007",
        isPrimary: true,
      },
      {
        id: "file_008",
        name: "GO_enrichment.pdf",
        type: "pdf",
        size: 1890200,
        url: "/reports/report_004/files/file_008",
        isPrimary: false,
      },
      {
        id: "file_009",
        name: "KEGG_pathway.png",
        type: "png",
        size: 1245000,
        url: "/reports/report_004/files/file_009",
        isPrimary: false,
      },
      {
        id: "file_010",
        name: "results_archive.zip",
        type: "zip",
        size: 15678000,
        url: "/reports/report_004/files/file_010",
        isPrimary: false,
      },
    ],
    tags: ["rnaseq", "fruit-ripening", "tomato"],
    isRead: true,
    isStarred: false,
  },
  {
    id: "report_005",
    taskId: "task_20260702_001",
    flowId: "atac_seq",
    flowName: "ATAC-seq 染色质可及性分析",
    flowVersion: "v0.0.5",
    flowIcon: "🧪",
    title: "ATAC-seq 分析报告 - 小麦抗旱品种比较",
    description: "对比抗旱品种与敏感品种在干旱处理后的染色质开放区域变化，发现与抗旱相关的转录因子结合位点差异。",
    status: "failed",
    createdAt: "2026-07-02T08:30:00Z",
    completedAt: "2026-07-02T08:35:00Z",
    sampleCount: 4,
    duration: 300,
    files: [],
    tags: ["atacseq", "drought-stress", "wheat"],
    isRead: false,
    isStarred: false,
  },
];

// 统计概览数据
export const mockStats = {
  total: 5,
  today: 2,
  generating: 1,
  starred: 1,
};

```

## 二、使用方式

在 `ReportCenter/index.tsx` 中引入示例数据：

```tsx
import { mockReports, mockStats } from './mockData';

// 在 loadReports 函数中使用（开发阶段）
const loadReports = async () => {
  setLoading(true);
  try {
    // 开发阶段使用 mock 数据
    setReports(mockReports);
    setPagination(prev => ({ ...prev, total: mockStats.total }));
    
    // 生产环境使用真实 API
    // const res = await reportApi.getReports({...});
  } finally {
    setLoading(false);
  }
};
```



## 三、当前实现优化建议

### 3.1 统计卡片优化

当前统计卡片是静态的 0，需要连接真实数据或 mock 数据：

```tsx
// 统计卡片组件优化
const StatCard = ({ title, value, icon, color }) => (
  <Card className="stat-card">
    <div className="stat-card-content">
      <div className={`stat-icon ${color}`}>
        {icon}
      </div>
      <div className="stat-info">
        <div className="stat-value">{value}</div>
        <div className="stat-title">{title}</div>
      </div>
    </div>
  </Card>
);
```

```css
.stat-card {
  transition: all 0.2s;
}

.stat-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
}

.stat-card-content {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 8px;
}

.stat-icon {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
}

.stat-icon.blue {
  background: linear-gradient(135deg, #e8f0ff, #d6e4ff);
  color: #4A6CF7;
}

.stat-icon.green {
  background: linear-gradient(135deg, #e6ffed, #c6f6d5);
  color: #00b42a;
}

.stat-icon.orange {
  background: linear-gradient(135deg, #fff7e6, #ffe4ba);
  color: #ff7d00;
}

.stat-icon.purple {
  background: linear-gradient(135deg, #f3e8ff, #e9d5ff);
  color: #722ed1;
}

.stat-value {
  font-size: 28px;
  font-weight: 700;
  color: #1a1a1a;
  line-height: 1;
}

.stat-title {
  font-size: 13px;
  color: #999;
  margin-top: 4px;
}
```

### 3.2 筛选栏交互优化

当前筛选栏的 Select 组件需要添加清空功能和更好的视觉反馈：

```tsx
// 筛选栏优化
<div className="filter-bar">
  <Input.Search
    placeholder="搜索报告名称、流程、标签..."
    allowClear
    style={{ width: 280 }}
    onSearch={(value) => setFilter(prev => ({ ...prev, keyword: value }))}
  />

  <Select
    placeholder="分析流程"
    allowClear
    options={flowOptions}
    value={filter.flowId || undefined}
    onChange={(v) => setFilter(prev => ({ ...prev, flowId: v }))}
    style={{ width: 200 }}
    prefix={<Filter size={14} />}
  />

  <Select
    placeholder="状态"
    allowClear
    options={statusOptions}
    value={filter.status || undefined}
    onChange={(v) => setFilter(prev => ({ ...prev, status: v }))}
    style={{ width: 140 }}
  />

  <Select
    placeholder="时间范围"
    allowClear
    options={dateOptions}
    value={filter.dateRange || undefined}
    onChange={(v) => setFilter(prev => ({ ...prev, dateRange: v }))}
    style={{ width: 140 }}
  />

  <Button
    type="secondary"
    icon={<RefreshCw size={16} />}
    onClick={loadReports}
  >
    刷新
  </Button>
</div>
```

### 3.3 报告卡片状态颜色优化

当前卡片左侧状态线颜色需要更明显的区分：

```css
/* 状态颜色增强 */
.report-card {
  position: relative;
  overflow: hidden;
}

.report-card::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 4px;
  border-radius: 2px 0 0 2px;
}

.report-card.completed::before {
  background: linear-gradient(180deg, #00b42a, #00c853);
}

.report-card.generating::before {
  background: linear-gradient(180deg, #ff7d00, #ff9800);
  animation: pulse 2s infinite;
}

.report-card.failed::before {
  background: linear-gradient(180deg, #f53f3f, #ff4d4f);
}

.report-card.expired::before {
  background: linear-gradient(180deg, #86909c, #a1a7b3);
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}
```

### 3.4 生成中报告的特殊展示

对于生成中的报告，需要显示进度和取消按钮：

```tsx
// 生成中报告卡片
{report.status === "generating" && (
  <div className="generating-indicator">
    <Spin size="small" />
    <span>报告生成中...</span>
    <Progress 
      percent={report.progress || 0} 
      size="small" 
      style={{ width: 120 }}
    />
    <Button size="mini" status="danger">
      取消
    </Button>
  </div>
)}
```

```css
.generating-indicator {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  background: #fff7e6;
  border-radius: 8px;
  margin-top: 12px;
}

.generating-indicator span {
  color: #ff7d00;
  font-size: 13px;
}
```

### 3.5 空状态优化

当前空状态已经不错，但可以增加更多引导：

```tsx
<Empty
  icon={<FileText size={64} color="#d9d9d9" />}
  description={
    <div className="empty-description">
      <p className="empty-title">暂无报告</p>
      <p className="empty-subtitle">
        前往分析中心提交任务，生成你的第一份分析报告
      </p>
      <div className="empty-tips">
        <p>支持的报告类型：</p>
        <div className="tip-tags">
          <Tag size="small">RNA-seq 差异表达</Tag>
          <Tag size="small">ATAC-seq 染色质可及性</Tag>
          <Tag size="small">ChIP-seq 峰值分析</Tag>
          <Tag size="small">WGBS 甲基化分析</Tag>
        </div>
      </div>
    </div>
  }
>
  <Button type="primary" size="large" onClick={() => navigate("/analysis")}>
    <Flask size={18} />
    前往分析中心
  </Button>
</Empty>
```

```css
.empty-description {
  text-align: center;
}

.empty-title {
  font-size: 18px;
  font-weight: 600;
  color: #1a1a1a;
  margin-bottom: 8px;
}

.empty-subtitle {
  font-size: 14px;
  color: #666;
  margin-bottom: 20px;
}

.empty-tips {
  background: #f8f9fa;
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 24px;
}

.empty-tips p {
  font-size: 13px;
  color: #999;
  margin-bottom: 8px;
}

.tip-tags {
  display: flex;
  gap: 8px;
  justify-content: center;
  flex-wrap: wrap;
}
```

### 3.6 报告卡片文件列表优化

文件标签增加点击下载和图标：

```tsx
// 文件标签组件
const FileTag = ({ file }) => {
  const fileIconMap = {
    html: <Globe size={12} />,
    pdf: <FileText size={12} />,
    png: <Image size={12} />,
    csv: <Table size={12} />,
    zip: <Archive size={12} />,
  };

  return (
    <Tag
      size="small"
      color={file.type === "html" ? "arcoblue" : "gray"}
      className="file-tag"
      onClick={() => handleDownload(file)}
    >
      <span className="file-tag-content">
        {fileIconMap[file.type]}
        <span>{file.name}</span>
        <span className="file-size">({formatBytes(file.size)})</span>
      </span>
    </Tag>
  );
};
```

```css
.file-tag {
  cursor: pointer;
  transition: all 0.2s;
}

.file-tag:hover {
  transform: translateY(-1px);
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.08);
}

.file-tag-content {
  display: flex;
  align-items: center;
  gap: 4px;
}

.file-size {
  font-size: 11px;
  color: #bbb;
}
```

### 3.7 批量操作功能

增加批量选择和操作功能：

```tsx
// 批量操作栏
<div className="batch-actions-bar">
  <Checkbox
    checked={selectedReports.length === reports.length}
    indeterminate={selectedReports.length > 0 && selectedReports.length < reports.length}
    onChange={(checked) => handleSelectAll(checked)}
  >
    全选 ({selectedReports.length}/{reports.length})
  </Checkbox>

  {selectedReports.length > 0 && (
    <div className="batch-buttons">
      <Button icon={<Download size={16} />}>批量下载</Button>
      <Button icon={<Star size={16} />}>批量收藏</Button>
      <Button status="danger" icon={<Trash2 size={16} />}>批量删除</Button>
    </div>
  )}
</div>
```

### 3.8 报告卡片 hover 效果增强

```css
.report-card {
  transition: all 0.25s cubic-bezier(0.34, 1.56, 0.64, 1);
  cursor: pointer;
}

.report-card:hover {
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.08);
  transform: translateY(-3px);
}

.report-card:hover .report-title {
  color: #4A6CF7;
}

/* 操作按钮默认隐藏，hover 显示 */
.report-actions {
  opacity: 0;
  transition: opacity 0.2s;
}

.report-card:hover .report-actions {
  opacity: 1;
}

/* 移动端始终显示操作按钮 */
@media (max-width: 768px) {
  .report-actions {
    opacity: 1;
  }
}
```

### 3.9 时间显示优化

使用相对时间（今天、昨天、3天前）+ 绝对时间tooltip：

```tsx
const formatRelativeTime = (date: string) => {
  const now = new Date();
  const target = new Date(date);
  const diff = now.getTime() - target.getTime();
  const days = Math.floor(diff / (1000 * 60 * 60 * 24));

  if (days === 0) return "今天";
  if (days === 1) return "昨天";
  if (days < 7) return `${days}天前`;
  if (days < 30) return `${Math.floor(days / 7)}周前`;
  return formatDateTime(date);
};

// 使用
<Tooltip content={formatDateTime(report.createdAt)}>
  <span>{formatRelativeTime(report.createdAt)}</span>
</Tooltip>
```

### 3.10 响应式布局优化

```css
/* 统计卡片响应式 */
.stats-bar {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}

@media (max-width: 1024px) {
  .stats-bar {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 640px) {
  .stats-bar {
    grid-template-columns: 1fr;
  }
}

/* 筛选栏响应式 */
.filter-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

@media (max-width: 768px) {
  .filter-bar > * {
    width: 100% !important;
  }
}

/* 报告卡片响应式 */
.report-card-content {
  display: flex;
  gap: 16px;
  align-items: flex-start;
}

@media (max-width: 768px) {
  .report-card-content {
    flex-direction: column;
  }

  .report-actions {
    width: 100%;
    justify-content: flex-end;
  }
}
```

## 四、完整优化清单

| 优先级 | 优化项 | 说明 | 文件 |
|--------|--------|------|------|
| P0 | 连接 mock 数据 | 让页面有真实内容展示 | mockData.ts |
| P0 | 统计卡片数据绑定 | 显示真实统计数字 | index.tsx |
| P1 | 状态颜色增强 | 左侧状态线 + 动画 | ReportCard.css |
| P1 | 生成中报告展示 | 进度条 + 取消按钮 | ReportCard.tsx |
| P1 | 文件标签图标 | 不同文件类型不同图标 | ReportCard.tsx |
| P1 | 相对时间显示 | 今天/昨天/3天前 | format.ts |
| P2 | 批量操作 | 多选 + 批量下载/删除 | index.tsx |
| P2 | 响应式布局 | 移动端适配 | *.css |
| P2 | 空状态增强 | 增加引导提示 | index.tsx |
| P2 | hover 效果 | 卡片悬浮动画 | ReportCard.css |
| P3 | 报告收藏 | 收藏功能交互 | ReportCard.tsx |
| P3 | 报告分享 | 生成分享链接 | index.tsx |

---

*文档由 OmicHub 技术委员会（阿姨）编制*
