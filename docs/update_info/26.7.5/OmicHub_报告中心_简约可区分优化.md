# OmicHub 报告中心简约风格 + 可区分性优化方案

> **文档版本**: v2.0
> **目标**: 在保持简约的前提下，恢复必要的视觉区分锚点
> **核心原则**: 简约不是去掉所有装饰，而是让每个元素都有信息价值

---

## 一、问题诊断

当前简约版的问题：

```
问题版（无法区分）:
+--------------------------------------------------+
| RNA-seq 差异表达分析报告 - 拟南芥盐胁迫处理      |  ← 全是黑色文字
| 基于 RNAFlow 流程...                             |
| 今天 · 12样本 · 13分钟 · v2.2.0                  |  ← 元信息无类型标识
| 🔵 report.html +3                                |
+--------------------------------------------------+
| ATAC-seq 染色质可及性分析报告 - 水稻根尖发育      |  ← 和上面完全一样风格
| ...                                              |
| 昨天 · 6样本 · 32分钟 · v0.0.5                   |
| 🔵 atac_report.html +1                           |
+--------------------------------------------------+
| RNA-seq 差异表达分析报告 - 生菜冷胁迫响应        |  ← 生成中？已完成？看不出
| ...                                              |
| 1天前 · 8样本 · - · v2.2.0 · 生成中              |  ← 只有文字提示
|                                                  |
+--------------------------------------------------+
```

**根本原因**: 去掉了图标、badge、状态色后，所有报告卡片变成了"纯文字列表"，大脑无法通过视觉快速分类。

---

## 二、优化方案：简约 + 可区分

### 2.1 视觉层次设计

```
优化版（可区分）:
+--------------------------------------------------+
| 🧬 RNA-seq 差异表达分析报告 - 拟南芥盐胁迫处理    |  ← 图标区分类型
|    基于 RNAFlow 流程...                           |  ← 描述缩进对齐
|    今天 · 12样本 · 13分钟 · v2.2.0 · RNA-seq      |  ← 类型标签
|    🔵 report.html +3                              |
+--------------------------------------------------+
| 🧪 ATAC-seq 染色质可及性分析报告 - 水稻根尖发育   |  ← 不同图标
|    ...                                            |
|    昨天 · 6样本 · 32分钟 · v0.0.5 · ATAC-seq      |
|    🔵 atac_report.html +1                         |
+--------------------------------------------------+
| 🧬 RNA-seq 差异表达分析报告 - 生菜冷胁迫响应      |  ← 标题橙色=生成中
|    ...                                            |
|    1天前 · 8样本 · - · v2.2.0 · RNA-seq · 生成中   |
|    ⏳ 报告生成中...                                |  ← 生成中提示
+--------------------------------------------------+
| 🧬 RNA-seq 差异表达分析报告 - 番茄果实成熟          |  ← 标题黑色=已完成
|    ...                                            |
|    2天前 · 9样本 · 28分钟 · v2.1.0 · RNA-seq       |
|    🔵 tomato_report.html +3                       |
+--------------------------------------------------+
| 🧪 ATAC-seq 分析报告 - 小麦抗旱品种比较            |  ← 标题红色=失败
|    ...                                            |     删除线
|    2天前 · 4样本 · 5分钟 · v0.0.5 · ATAC-seq       |
|    ⚠️ 生成失败                                     |
+--------------------------------------------------+
```

**区分维度**:
| 维度 | 视觉元素 | 作用 |
|------|----------|------|
| **流程类型** | 🧬/🧪 图标 + 类型标签 | 0.1秒识别分析类型 |
| **完成状态** | 标题颜色（黑/橙/红） | 一眼看出是否可用 |
| **左侧状态** | 3px 彩色竖线 | 列表扫视时的快速定位 |
| **收藏状态** | 竖线加粗 + 微光 | 重要报告突出 |
| **文件类型** | 彩色圆点 | 快速识别文件格式 |

---

## 三、详细实现

### 3.1 流程类型图标（恢复，但缩小）

```tsx
// ReportCardMinimal.tsx
<h3 className="report-title-minimal">
  <span className="flow-icon">{report.flowIcon}</span>
  <span className="title-text">{report.title}</span>
</h3>
```

```css
.flow-icon {
  font-size: 16px;
  margin-right: 8px;
  opacity: 0.85;
  filter: grayscale(0.15); /* 轻微降饱和，不抢眼 */
  display: inline-block;
  vertical-align: middle;
  transition: transform 0.2s ease;
}

.report-card-minimal:hover .flow-icon {
  transform: scale(1.1);
  filter: grayscale(0); /* hover 恢复鲜艳 */
}
```

### 3.2 标题颜色区分状态（替代 badge）

```css
/* 已完成 - 正常黑色 */
.report-card-minimal.completed .report-title-minimal .title-text {
  color: #1a1a1a;
}

/* 生成中 - 橙色，表示进行中 */
.report-card-minimal.generating .report-title-minimal .title-text {
  color: #ff7d00;
}

/* 失败 - 红色，表示不可用 */
.report-card-minimal.failed .report-title-minimal .title-text {
  color: #f53f3f;
  text-decoration: line-through;
  opacity: 0.7;
}

/* 已过期 - 灰色 */
.report-card-minimal.expired .report-title-minimal .title-text {
  color: #999;
}
```

### 3.3 流程类型标签（小药丸，淡背景）

```tsx
// 添加到元信息行末尾
<div className="report-meta-minimal">
  <span>今天</span>
  <span className="dot">·</span>
  <span>12 样本</span>
  <span className="dot">·</span>
  <span>13 分钟</span>
  <span className="dot">·</span>
  <span className="version">v2.2.0</span>
  <span className="dot">·</span>
  <span className="flow-tag">{report.flowName.split(' ')[0]}</span>
  {report.status === 'generating' && (
    <>
      <span className="dot">·</span>
      <span className="status-tag generating">生成中</span>
    </>
  )}
  {report.status === 'failed' && (
    <>
      <span className="dot">·</span>
      <span className="status-tag failed">失败</span>
    </>
  )}
</div>
```

```css
.flow-tag {
  font-size: 11px;
  color: #888;
  background: #f0f0f0;
  padding: 2px 8px;
  border-radius: 10px;
  font-weight: 500;
  letter-spacing: 0.3px;
}

.status-tag {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 10px;
  font-weight: 500;
}

.status-tag.generating {
  color: #ff7d00;
  background: #fff7e6;
}

.status-tag.failed {
  color: #f53f3f;
  background: #fff2f0;
}
```

### 3.4 左侧状态线强化

```css
.report-card-minimal::before {
  content: '';
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 3px;
  height: 0;
  border-radius: 0 2px 2px 0;
  transition: all 0.25s cubic-bezier(0.34, 1.56, 0.64, 1);
}

/* 已完成 - 绿色 */
.report-card-minimal.completed::before {
  background: #00b42a;
  height: 60%;
}

/* 生成中 - 橙色 + 脉冲 */
.report-card-minimal.generating::before {
  background: #ff7d00;
  height: 60%;
  animation: pulse-line 2s ease-in-out infinite;
}

/* 失败 - 红色 */
.report-card-minimal.failed::before {
  background: #f53f3f;
  height: 60%;
}

/* 已收藏 - 加粗 + 微光 */
.report-card-minimal.is-starred::before {
  width: 4px;
  height: 70%;
  box-shadow: 0 0 8px rgba(0, 178, 42, 0.25);
}

@keyframes pulse-line {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.35; }
}
```

### 3.5 文件区用颜色区分类型

```tsx
const fileColorMap = {
  html: '#4A6CF7',   // 蓝色
  pdf: '#f53f3f',    // 红色
  png: '#00b42a',    // 绿色
  csv: '#722ed1',    // 紫色
  zip: '#86909c',    // 灰色
};

<span className="primary-file" onClick={onPreview}>
  <span 
    className="file-dot" 
    style={{ background: fileColorMap[primaryFile.type] }}
  />
  {primaryFile.name}
</span>
```

```css
.file-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  flex-shrink: 0;
  transition: transform 0.2s ease;
}

.primary-file:hover .file-dot {
  transform: scale(1.3);
}
```

### 3.6 生成中/失败状态的特殊提示

```tsx
{report.status === 'generating' && (
  <div className="status-hint generating">
    <Spin size="small" />
    <span>报告生成中，请稍候...</span>
  </div>
)}

{report.status === 'failed' && (
  <div className="status-hint failed">
    <AlertTriangle size={14} />
    <span>生成失败，请查看任务日志</span>
  </div>
)}
```

```css
.status-hint {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 10px;
  font-size: 12px;
  padding: 8px 12px;
  border-radius: 8px;
  width: fit-content;
}

.status-hint.generating {
  color: #ff7d00;
  background: #fff7e6;
}

.status-hint.failed {
  color: #f53f3f;
  background: #fff2f0;
}
```

---

## 四、完整卡片组件代码

```tsx
// src/pages/ReportCenter/components/ReportCardMinimal.tsx
import React from "react";
import { Eye, Download, ExternalLink, Star, Trash2, AlertTriangle } from "lucide-react";
import { Spin } from "@arco-design/web-react";
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

const fileColorMap: Record<string, string> = {
  html: '#4A6CF7',
  pdf: '#f53f3f',
  png: '#00b42a',
  csv: '#722ed1',
  zip: '#86909c',
};

const ReportCardMinimal: React.FC<Props> = ({
  report, onPreview, onDownload, onViewTask, onToggleStar, onDelete,
}) => {
  const primaryFile = report.files.find(f => f.isPrimary);
  const flowShortName = report.flowName.split(' ')[0]; // "RNA-seq" / "ATAC-seq"

  return (
    <div className={`report-card-minimal ${report.status} ${report.isStarred ? 'is-starred' : ''}`}>
      <div className="report-content">
        {/* 标题 */}
        <h3 className="report-title-minimal">
          <span className="flow-icon">{report.flowIcon}</span>
          <span className="title-text">{report.title}</span>
        </h3>

        {/* 描述 */}
        <p className="report-desc-minimal">{report.description}</p>

        {/* 元信息 */}
        <div className="report-meta-minimal">
          <span>{formatRelativeTime(report.createdAt)}</span>
          <span className="dot">·</span>
          <span>{report.sampleCount} 样本</span>
          <span className="dot">·</span>
          <span>{report.duration > 0 ? formatDuration(report.duration) : '-'}</span>
          <span className="dot">·</span>
          <span className="version">{report.flowVersion}</span>
          <span className="dot">·</span>
          <span className="flow-tag">{flowShortName}</span>
          {report.status === 'generating' && (
            <>
              <span className="dot">·</span>
              <span className="status-tag generating">生成中</span>
            </>
          )}
          {report.status === 'failed' && (
            <>
              <span className="dot">·</span>
              <span className="status-tag failed">失败</span>
            </>
          )}
        </div>

        {/* 主文件 */}
        {primaryFile && report.status === 'completed' && (
          <div className="report-files-minimal">
            <span className="primary-file" onClick={onPreview}>
              <span 
                className="file-dot" 
                style={{ background: fileColorMap[primaryFile.type] || '#999' }}
              />
              {primaryFile.name}
            </span>
            {report.files.length > 1 && (
              <span className="more-files">+{report.files.length - 1}</span>
            )}
          </div>
        )}

        {/* 状态提示 */}
        {report.status === 'generating' && (
          <div className="status-hint generating">
            <Spin size="small" />
            <span>报告生成中，请稍候...</span>
          </div>
        )}
        {report.status === 'failed' && (
          <div className="status-hint failed">
            <AlertTriangle size={14} />
            <span>生成失败，请查看任务日志</span>
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

/* ===== 左侧状态线 ===== */
.report-card-minimal::before {
  content: '';
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 3px;
  height: 0;
  border-radius: 0 2px 2px 0;
  transition: all 0.25s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.report-card-minimal.completed::before {
  background: #00b42a;
  height: 60%;
}

.report-card-minimal.generating::before {
  background: #ff7d00;
  height: 60%;
  animation: pulse-line 2s ease-in-out infinite;
}

.report-card-minimal.failed::before {
  background: #f53f3f;
  height: 60%;
}

.report-card-minimal.is-starred::before {
  width: 4px;
  height: 70%;
  box-shadow: 0 0 8px rgba(0, 178, 42, 0.25);
}

@keyframes pulse-line {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.35; }
}

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
  margin: 0 0 4px;
  line-height: 1.5;
  word-break: break-word;
  display: flex;
  align-items: center;
}

.flow-icon {
  font-size: 16px;
  margin-right: 8px;
  opacity: 0.85;
  filter: grayscale(0.15);
  display: inline-block;
  vertical-align: middle;
  transition: all 0.2s ease;
  flex-shrink: 0;
}

.report-card-minimal:hover .flow-icon {
  transform: scale(1.1);
  filter: grayscale(0);
}

/* 标题颜色按状态区分 */
.report-card-minimal.completed .title-text {
  color: #1a1a1a;
}

.report-card-minimal.generating .title-text {
  color: #ff7d00;
}

.report-card-minimal.failed .title-text {
  color: #f53f3f;
  text-decoration: line-through;
  opacity: 0.7;
}

.report-card-minimal.expired .title-text {
  color: #999;
}

/* ===== 描述 ===== */
.report-desc-minimal {
  font-size: 13px;
  color: #999;
  margin: 0 0 8px 24px; /* 缩进对齐标题 */
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
  margin-left: 24px; /* 缩进对齐 */
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

.flow-tag {
  font-size: 11px;
  color: #888;
  background: #f0f0f0;
  padding: 2px 8px;
  border-radius: 10px;
  font-weight: 500;
  letter-spacing: 0.3px;
}

.status-tag {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 10px;
  font-weight: 500;
}

.status-tag.generating {
  color: #ff7d00;
  background: #fff7e6;
}

.status-tag.failed {
  color: #f53f3f;
  background: #fff2f0;
}

/* ===== 文件列表 ===== */
.report-files-minimal {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 10px;
  margin-left: 24px; /* 缩进对齐 */
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
  width: 7px;
  height: 7px;
  border-radius: 50%;
  flex-shrink: 0;
  transition: transform 0.2s ease;
}

.primary-file:hover .file-dot {
  transform: scale(1.3);
}

.more-files {
  font-size: 11px;
  color: #ccc;
  background: #f5f5f5;
  padding: 2px 8px;
  border-radius: 10px;
}

/* ===== 状态提示 ===== */
.status-hint {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 10px;
  margin-left: 24px;
  font-size: 12px;
  padding: 8px 12px;
  border-radius: 8px;
  width: fit-content;
}

.status-hint.generating {
  color: #ff7d00;
  background: #fff7e6;
}

.status-hint.failed {
  color: #f53f3f;
  background: #fff2f0;
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
    padding-left: 24px;
    padding-top: 12px;
    width: 100%;
    justify-content: flex-start;
  }
}
```

---

## 五、视觉对比总结

| 元素 | 复杂版 | 简约版 v1 | 简约版 v2（本方案） |
|------|--------|-----------|---------------------|
| 流程图标 | 🧬 32px | ❌ 去掉 | 🧬 16px，hover 放大 |
| 状态 badge | ●已完成 | ❌ 去掉 | 标题颜色区分 |
| 收藏星 | ★ 标题旁 | ❌ 去掉 | 左侧线加粗 |
| 描述 | 正常黑色 | 灰色 | 灰色 + 缩进对齐 |
| 元信息 | 标签式 | · 分隔 | · 分隔 + 类型标签 |
| 文件列表 | 多图标标签 | 主文件 + 数量 | 彩色圆点 + 文件名 |
| 操作按钮 | 常驻 | hover 显示 | hover 显示 |
| 生成中提示 | 进度条 | 文字 | 橙色提示条 + 脉冲线 |
| 失败提示 | 红色badge | 文字 | 红色提示条 + 删除线 |

---

## 六、修改清单

| 文件 | 修改内容 | 优先级 |
|------|----------|--------|
| ReportCardMinimal.tsx | 恢复 flowIcon、添加状态标签、添加状态提示 | P0 |
| ReportCardMinimal.css | 标题颜色区分状态、左侧脉冲线、文件彩色圆点 | P0 |
| index.css | 统计卡片保持简约 | P1 |

---

*文档由 OmicHub 技术委员会（阿姨）编制*
*"简约是保留必要，去掉多余。可区分是保留必要的信息锚点。"*
