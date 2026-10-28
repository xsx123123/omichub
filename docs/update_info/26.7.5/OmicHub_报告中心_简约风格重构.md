# OmicHub 报告中心简约风格重构方案

> **设计原则**: 少即是多 (Less is More)  
> **参考风格**: Linear / Vercel Dashboard / Notion  
> **核心变化**: 减少视觉噪音、增加留白、信息分层、hover 显操作

---

## 一、当前问题诊断

```
当前（复杂）:
+-------------------------------------------------------------+
| [图标] 标题  ●已完成 ★                                     |  ← 标题行拥挤
| 描述文字...                                                |  ← 描述占一行
| 🕐 -1天前  12个样本  耗时13分钟  vv2.2.0                   |  ← 元信息密集
| [🌐 html 2.72MB] [📄 pdf 1.5MB] [🖼️ png 871KB] [📊 csv 446KB]|  ← 文件标签杂乱
|                                                            |
| [预览] [下载] [任务] [★] [🗑️]                              |  ← 操作按钮常驻
+-------------------------------------------------------------+

目标（简约）:
+-------------------------------------------------------------+
|                                                            |
|  RNA-seq 差异表达分析报告 - 拟南芥盐胁迫处理                |  ← 纯标题，无状态badge
|  基于 RNAFlow 流程...                                       |  ← 描述灰色小字
|                                                            |
|  1天前 · 12样本 · 13分钟 · v2.2.0                          |  ← 极简元信息
|                                                            |
|  [预览] [下载] [任务] ...                                  |  ← hover 才显示
|                                                            |
+-------------------------------------------------------------+
```

---

## 二、简约版报告卡片设计

### 2.1 整体布局

```css
/* 报告卡片 - 简约版 */
.report-card-minimal {
  padding: 20px 24px;
  border-bottom: 1px solid #f5f5f5;  /* 细线分隔，替代卡片边框 */
  background: transparent;
  transition: background 0.15s ease;
  cursor: pointer;
  position: relative;
}

.report-card-minimal:hover {
  background: #fafafa;  /* 极淡的 hover 背景 */
}

.report-card-minimal:last-child {
  border-bottom: none;
}
```

### 2.2 标题区（极简）

```tsx
// 标题区 - 去掉状态 badge 和收藏星，纯文字
<div className="report-title-row">
  <h3 className="report-title-minimal">
    RNA-seq 差异表达分析报告 - 拟南芥盐胁迫处理
  </h3>
  {/* 状态用左侧竖线颜色表示，不在标题旁放 badge */}
</div>
```

```css
.report-title-minimal {
  font-size: 15px;
  font-weight: 500;
  color: #1a1a1a;
  margin: 0 0 4px;
  line-height: 1.5;
  /* 不截断，允许换行 */
  word-break: break-word;
}

/* 左侧状态指示线 - 极细 */
.report-card-minimal::before {
  content: '';
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 3px;
  height: 0;  /* 默认隐藏 */
  border-radius: 0 2px 2px 0;
  transition: height 0.2s ease;
}

.report-card-minimal:hover::before,
.report-card-minimal.completed::before {
  height: 60%;  /* hover 或已完成时显示 */
}

.report-card-minimal.completed::before { background: #00b42a; }
.report-card-minimal.generating::before { background: #ff7d00; }
.report-card-minimal.failed::before { background: #f53f3f; }
```

### 2.3 描述区（灰色小字）

```css
.report-desc-minimal {
  font-size: 13px;
  color: #999;  /* 更浅的灰色，降低存在感 */
  margin: 0 0 8px;
  line-height: 1.6;
  /* 最多两行 */
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
```

### 2.4 元信息区（极简，用 · 分隔）

```tsx
<div className="report-meta-minimal">
  <span>1天前</span>
  <span className="dot">·</span>
  <span>12 样本</span>
  <span className="dot">·</span>
  <span>13 分钟</span>
  <span className="dot">·</span>
  <span className="version">v2.2.0</span>

  {/* 生成中显示进度，但不占太多空间 */}
  {report.status === 'generating' && (
    <span className="generating-hint">
      <span className="dot">·</span>
      <Spin size="small" />
      <span>生成中</span>
    </span>
  )}
</div>
```

```css
.report-meta-minimal {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #bbb;  /* 更浅的灰色 */
}

.report-meta-minimal .dot {
  color: #ddd;
  font-size: 10px;
}

.report-meta-minimal .version {
  font-family: 'SF Mono', monospace;
  font-size: 11px;
  color: #ccc;
  background: #f5f5f5;
  padding: 1px 6px;
  border-radius: 4px;
}

.generating-hint {
  display: flex;
  align-items: center;
  gap: 4px;
  color: #ff7d00;
}
```

### 2.5 文件列表（折叠或极简标签）

**方案 A：完全隐藏文件列表，hover 才展开**

```css
.report-files-minimal {
  max-height: 0;
  overflow: hidden;
  transition: max-height 0.2s ease, opacity 0.2s ease;
  opacity: 0;
}

.report-card-minimal:hover .report-files-minimal {
  max-height: 100px;
  opacity: 1;
  margin-top: 12px;
}
```

**方案 B：只显示主文件（HTML），其他折叠**

```tsx
<div className="report-files-minimal">
  <span className="primary-file">
    <span className="file-dot html" />  {/* 小圆点代替图标 */}
    differential_expression_report.html
  </span>
  <span className="more-files">+3</span>  {/* 其他文件数量 */}
</div>
```

```css
.report-files-minimal {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 12px;
}

.primary-file {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #4A6CF7;
  cursor: pointer;
}

.primary-file:hover {
  text-decoration: underline;
}

.file-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}

.file-dot.html { background: #4A6CF7; }
.file-dot.pdf { background: #f53f3f; }
.file-dot.png { background: #00b42a; }

.more-files {
  font-size: 11px;
  color: #ccc;
  background: #f5f5f5;
  padding: 2px 8px;
  border-radius: 10px;
}
```

### 2.6 操作按钮（hover 才显示，放在右侧）

```tsx
<div className="report-actions-minimal">
  <button className="action-btn-minimal" title="预览">
    <Eye size={14} />
  </button>
  <button className="action-btn-minimal" title="下载">
    <Download size={14} />
  </button>
  <button className="action-btn-minimal" title="任务">
    <ExternalLink size={14} />
  </button>
  <button className="action-btn-minimal" title="收藏">
    <Star size={14} />
  </button>
</div>
```

```css
.report-card-minimal {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.report-content {
  flex: 1;
  min-width: 0;
}

.report-actions-minimal {
  display: flex;
  gap: 4px;
  opacity: 0;
  transition: opacity 0.15s ease;
  padding-left: 16px;
}

.report-card-minimal:hover .report-actions-minimal {
  opacity: 1;
}

.action-btn-minimal {
  width: 28px;
  height: 28px;
  border-radius: 6px;
  border: none;
  background: transparent;
  color: #ccc;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s;
}

.action-btn-minimal:hover {
  background: #f0f0f0;
  color: #666;
}

/* 移动端始终显示操作按钮 */
@media (max-width: 768px) {
  .report-actions-minimal {
    opacity: 1;
  }
}
```

---

## 三、完整简约版卡片组件

```tsx
// src/pages/ReportCenter/components/ReportCardMinimal.tsx
import React from "react";
import { Eye, Download, ExternalLink, Star, Trash2 } from "lucide-react";
import { Report } from "@/types/report";
import { formatRelativeTime, formatDuration } from "@/utils/format";
import "./ReportCardMinimal.css";

interface Props {
  report: Report;
  onPreview: () => void;
  onDownload: () => void;
  onViewTask: () => void;
  onToggleStar: () => void;
  onDelete: () => void;
}

const ReportCardMinimal: React.FC<Props> = ({
  report,
  onPreview,
  onDownload,
  onViewTask,
  onToggleStar,
  onDelete,
}) => {
  const primaryFile = report.files.find(f => f.isPrimary);

  return (
    <div className={`report-card-minimal ${report.status}`}>
      <div className="report-content">
        {/* 标题 */}
        <h3 className="report-title-minimal">{report.title}</h3>

        {/* 描述 */}
        <p className="report-desc-minimal">{report.description}</p>

        {/* 元信息 */}
        <div className="report-meta-minimal">
          <span>{formatRelativeTime(report.createdAt)}</span>
          <span className="dot">·</span>
          <span>{report.sampleCount} 样本</span>
          <span className="dot">·</span>
          <span>{formatDuration(report.duration)}</span>
          <span className="dot">·</span>
          <span className="version">{report.flowVersion}</span>

          {report.status === 'generating' && (
            <span className="generating-hint">
              <span className="dot">·</span>
              <span>生成中</span>
            </span>
          )}
        </div>

        {/* 主文件（可选显示）*/}
        {primaryFile && report.status === 'completed' && (
          <div className="report-files-minimal">
            <span className="primary-file" onClick={onPreview}>
              <span className="file-dot html" />
              {primaryFile.name}
            </span>
            {report.files.length > 1 && (
              <span className="more-files">+{report.files.length - 1}</span>
            )}
          </div>
        )}
      </div>

      {/* 操作按钮 */}
      <div className="report-actions-minimal">
        {report.status === 'completed' && (
          <>
            <button className="action-btn-minimal" onClick={onPreview} title="预览">
              <Eye size={14} />
            </button>
            <button className="action-btn-minimal" onClick={onDownload} title="下载">
              <Download size={14} />
            </button>
          </>
        )}
        <button className="action-btn-minimal" onClick={onViewTask} title="查看任务">
          <ExternalLink size={14} />
        </button>
        <button 
          className={`action-btn-minimal ${report.isStarred ? 'starred' : ''}`}
          onClick={onToggleStar}
          title={report.isStarred ? "取消收藏" : "收藏"}
        >
          <Star size={14} fill={report.isStarred ? "#FFB800" : "none"} />
        </button>
        <button className="action-btn-minimal" onClick={onDelete} title="删除">
          <Trash2 size={14} />
        </button>
      </div>
    </div>
  );
};

export default ReportCardMinimal;
```

```css
/* ReportCardMinimal.css */

/* ===== 卡片基础 ===== */
.report-card-minimal {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: 20px 24px;
  border-bottom: 1px solid #f5f5f5;
  background: transparent;
  transition: background 0.15s ease;
  cursor: pointer;
  position: relative;
}

.report-card-minimal:hover {
  background: #fafafa;
}

.report-card-minimal:last-child {
  border-bottom: none;
}

/* ===== 左侧状态线（极细，hover 显示）===== */
.report-card-minimal::before {
  content: '';
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 3px;
  height: 0;
  border-radius: 0 2px 2px 0;
  transition: height 0.2s ease;
}

.report-card-minimal:hover::before,
.report-card-minimal.completed::before {
  height: 50%;
}

.report-card-minimal.completed::before { background: #00b42a; }
.report-card-minimal.generating::before { background: #ff7d00; height: 50%; }
.report-card-minimal.failed::before { background: #f53f3f; height: 50%; }

/* ===== 内容区 ===== */
.report-content {
  flex: 1;
  min-width: 0;
  padding-right: 16px;
}

/* ===== 标题 ===== */
.report-title-minimal {
  font-size: 15px;
  font-weight: 500;
  color: #1a1a1a;
  margin: 0 0 4px;
  line-height: 1.5;
  word-break: break-word;
}

.report-card-minimal:hover .report-title-minimal {
  color: #4A6CF7;
}

/* ===== 描述 ===== */
.report-desc-minimal {
  font-size: 13px;
  color: #999;
  margin: 0 0 8px;
  line-height: 1.6;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* ===== 元信息 ===== */
.report-meta-minimal {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #bbb;
  flex-wrap: wrap;
}

.report-meta-minimal .dot {
  color: #e0e0e0;
  font-size: 10px;
}

.report-meta-minimal .version {
  font-family: 'SF Mono', 'Consolas', monospace;
  font-size: 11px;
  color: #ccc;
  background: #f5f5f5;
  padding: 1px 6px;
  border-radius: 4px;
}

.generating-hint {
  display: flex;
  align-items: center;
  gap: 4px;
  color: #ff7d00;
  font-size: 12px;
}

/* ===== 文件列表 ===== */
.report-files-minimal {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 10px;
}

.primary-file {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #4A6CF7;
  cursor: pointer;
  transition: opacity 0.15s;
}

.primary-file:hover {
  opacity: 0.8;
  text-decoration: underline;
}

.file-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
}

.file-dot.html { background: #4A6CF7; }
.file-dot.pdf { background: #f53f3f; }

.more-files {
  font-size: 11px;
  color: #ccc;
  background: #f5f5f5;
  padding: 2px 8px;
  border-radius: 10px;
}

/* ===== 操作按钮 ===== */
.report-actions-minimal {
  display: flex;
  gap: 2px;
  opacity: 0;
  transition: opacity 0.15s ease;
  flex-shrink: 0;
  padding-top: 2px;
}

.report-card-minimal:hover .report-actions-minimal {
  opacity: 1;
}

.action-btn-minimal {
  width: 28px;
  height: 28px;
  border-radius: 6px;
  border: none;
  background: transparent;
  color: #ccc;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s;
}

.action-btn-minimal:hover {
  background: #f0f0f0;
  color: #666;
}

.action-btn-minimal.starred {
  color: #FFB800;
}

/* 移动端始终显示操作按钮 */
@media (max-width: 768px) {
  .report-actions-minimal {
    opacity: 1;
  }

  .report-card-minimal {
    flex-direction: column;
  }

  .report-actions-minimal {
    padding-left: 0;
    padding-top: 12px;
    width: 100%;
    justify-content: flex-end;
  }
}
```

---

## 四、统计卡片简约化

```css
/* 统计卡片 - 简约版 */
.stats-bar-minimal {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 0;  /* 去掉 gap，用边框分隔 */
  margin-bottom: 24px;
  border: 1px solid #f0f0f0;
  border-radius: 12px;
  overflow: hidden;
}

.stat-card-minimal {
  padding: 20px 24px;
  text-align: center;
  border-right: 1px solid #f5f5f5;
  transition: background 0.15s;
}

.stat-card-minimal:last-child {
  border-right: none;
}

.stat-card-minimal:hover {
  background: #fafafa;
}

.stat-value-minimal {
  font-size: 28px;
  font-weight: 600;
  color: #1a1a1a;
  line-height: 1;
  margin-bottom: 6px;
}

.stat-title-minimal {
  font-size: 13px;
  color: #bbb;
}

/* 不同统计项的颜色区分（仅数字） */
.stat-card-minimal:nth-child(1) .stat-value-minimal { color: #1a1a1a; }
.stat-card-minimal:nth-child(2) .stat-value-minimal { color: #00b42a; }
.stat-card-minimal:nth-child(3) .stat-value-minimal { color: #ff7d00; }
.stat-card-minimal:nth-child(4) .stat-value-minimal { color: #FFB800; }
```

---

## 五、筛选栏简约化

```css
/* 筛选栏 - 简约版 */
.filter-bar-minimal {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 0;
  border-bottom: 1px solid #f5f5f5;
  margin-bottom: 0;
}

/* 输入框简约 */
.filter-bar-minimal .arco-input {
  border: none;
  background: #f5f5f5;
  border-radius: 8px;
  padding: 8px 12px;
  font-size: 13px;
}

.filter-bar-minimal .arco-input:focus {
  background: #fff;
  box-shadow: 0 0 0 2px rgba(74, 108, 247, 0.1);
}

/* Select 简约 */
.filter-bar-minimal .arco-select {
  border: none;
  background: transparent;
}

.filter-bar-minimal .arco-select:hover {
  background: #f5f5f5;
}
```

---

## 六、整体页面效果

```
+-------------------------------------------------------------+
|  结果报告中心                                               |
|  查看和管理所有分析生成的报告                                |
|                                                             |
|  +------+ +------+ +------+ +------+                     |
|  |  5   | |  2   | |  1   | |  1   |                     |
|  | 总报告| | 今日 | | 生成中| | 收藏 |                     |
|  +------+ +------+ +------+ +------+                     |
|                                                             |
|  [搜索...]  [流程 ▼]  [状态 ▼]  [时间 ▼]  [刷新]          |
|  ────────────────────────────────────────────────────────  |
|                                                             |
|  |  RNA-seq 差异表达分析报告 - 拟南芥盐胁迫处理             |
|  |  基于 RNAFlow 流程...                                   |
|  |  1天前 · 12样本 · 13分钟 · v2.2.0    [👁] [⬇] [★]     |
|  ────────────────────────────────────────────────────────  |
|                                                             |
|  |  ATAC-seq 染色质可及性分析报告 - 水稻根尖发育          |
|  |  基于 ATACFlow 流程...                                  |
|  |  昨天 · 6样本 · 32分钟 · v0.0.5      [👁] [⬇] [★]     |
|  ────────────────────────────────────────────────────────  |
|                                                             |
|  |  RNA-seq 差异表达分析报告 - 生菜冷胁迫响应              |
|  |  基于 RNAFlow 流程...                                   |
|  |  1天前 · 8样本 · 生成中 · v2.2.0      [⏳] [★]         |
|  ────────────────────────────────────────────────────────  |
|                                                             |
+-------------------------------------------------------------+
```

---

## 七、修改清单

| 文件 | 修改内容 | 优先级 |
|------|----------|--------|
| ReportCardMinimal.tsx | 新建简约版卡片组件 | P0 |
| ReportCardMinimal.css | 新建简约版样式 | P0 |
| index.tsx | 替换 ReportCard 为 ReportCardMinimal | P0 |
| index.css | 统计卡片和筛选栏样式调整 | P1 |
| mockData.ts | 保持现有数据不变 | - |

---

*文档由 OmicHub 设计委员会（阿姨）编制*  
*"简约不是少，而是没有多余。" —— 迪特·拉姆斯*
