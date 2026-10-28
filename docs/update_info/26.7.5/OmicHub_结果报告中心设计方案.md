# OmicHub 结果报告中心设计方案

> **文档版本**: v1.0
> **目标模块**: 结果报告中心（Report Center）
> **核心功能**: 统一查看、预览、下载分析生成的 HTML 报告
> **关联模块**: 分析中心、任务中心、数据管理

---

## 一、需求概述

用户在分析中心提交分析任务后，系统会生成 HTML 格式的分析报告。需要一个专门的模块来：

- 统一展示所有历史报告
- 支持在线预览 HTML 报告
- 支持下载报告（HTML / PDF）
- 按分析流程类型筛选
- 与任务状态关联

---

## 二、页面结构

```
+-------------------------------------------------------------+
|  OmicHub                                                    |
|  [侧边栏] 首页 | 仪表板 | 分析中心 | 任务中心 | 报告中心 | ... |
|                                                             |
|  +-------------------------------------------------------+ |
|  |  结果报告中心                              [?]       | |
|  |  查看和管理所有分析生成的报告                            | |
|  +-------------------------------------------------------+ |
|  |                                                        | |
|  |  [搜索报告...]    [全部流程 ▼]  [最近7天 ▼]  [刷新]   | |
|  |                                                        | |
|  |  +--------------------------------------------------+ | |
|  |  |  [图标] RNA-seq 差异表达分析    v2.2.0   已完成   | | |
|  |  |  生成时间: 2026-07-05 14:32 | 样本: 12 | 耗时: 45min | | |
|  |  |  [预览报告] [下载 HTML] [下载 PDF] [查看任务]      | | |
|  |  +--------------------------------------------------+ | |
|  |  |  [图标] ATAC-seq 染色质可及性分析  v0.0.5  已完成   | | |
|  |  |  生成时间: 2026-07-04 09:15 | 样本: 6  | 耗时: 32min | | |
|  |  |  [预览报告] [下载 HTML] [下载 PDF] [查看任务]      | | |
|  |  +--------------------------------------------------+ | |
|  |                                                        | |
|  +-------------------------------------------------------+ |
|                                                             |
+-------------------------------------------------------------+
```

---

## 三、路由与菜单配置

### 3.1 路由配置

```tsx
// src/router/index.tsx
const routes = [
  // ... 现有路由
  {
    path: "/reports",
    name: "ReportCenter",
    component: lazy(() => import("@/pages/ReportCenter")),
    meta: {
      title: "结果报告中心",
      icon: "FileText",
      requiresAuth: true,
    },
  },
  {
    path: "/reports/:reportId",
    name: "ReportPreview",
    component: lazy(() => import("@/pages/ReportCenter/Preview")),
    meta: {
      title: "报告预览",
      hideInMenu: true,
      requiresAuth: true,
    },
  },
];
```

### 3.2 侧边栏菜单

```yaml
# 在现有侧边栏配置中添加
menu:
  - name: "首页"
    icon: "Home"
    path: "/"
  - name: "仪表板"
    icon: "Dashboard"
    path: "/dashboard"
  - name: "分析中心"
    icon: "Flask"
    path: "/analysis"
  - name: "任务中心"
    icon: "Task"
    path: "/tasks"
  - name: "结果报告中心"  # 新增
    icon: "FileText"
    path: "/reports"
    badge: "report_count"
  - name: "数据管理"
    icon: "Database"
    path: "/data"
  - name: "AI 助手"
    icon: "MessageSquare"
    path: "/ai-assistant"
```

---

## 四、数据模型

### 4.1 报告数据结构

```typescript
// src/types/report.ts

export interface Report {
  id: string;
  taskId: string;
  flowId: string;
  flowName: string;
  flowVersion: string;
  flowIcon: string;

  title: string;
  description: string;

  status: ReportStatus;
  createdAt: string;
  completedAt?: string;

  sampleCount: number;
  duration: number;

  files: ReportFile[];
  tags: string[];

  isRead: boolean;
  isStarred: boolean;
}

export type ReportStatus =
  | "generating"
  | "completed"
  | "failed"
  | "expired";

export interface ReportFile {
  id: string;
  name: string;
  type: "html" | "pdf" | "png" | "zip" | "csv";
  size: number;
  url: string;
  isPrimary: boolean;
}

export interface ReportFilter {
  keyword?: string;
  flowId?: string;
  status?: ReportStatus;
  dateRange?: [string, string];
  isStarred?: boolean;
}
```

### 4.2 API 接口定义

```typescript
// src/api/report.ts

import request from "@/utils/request";

export const reportApi = {
  getReports: (params: ReportFilter & Pagination) =>
    request.get<PageResult<Report>>("/api/v1/reports", { params }),

  getReportDetail: (id: string) =>
    request.get<Report>(`/api/v1/reports/${id}`),

  previewReport: (id: string) =>
    request.get<string>(`/api/v1/reports/${id}/preview`),

  downloadReport: (reportId: string, fileId: string) =>
    request.get<Blob>(`/api/v1/reports/${reportId}/files/${fileId}/download`, {
      responseType: "blob",
    }),

  deleteReport: (id: string) =>
    request.delete(`/api/v1/reports/${id}`),

  toggleStar: (id: string, isStarred: boolean) =>
    request.patch(`/api/v1/reports/${id}/star`, { isStarred }),

  markAsRead: (id: string) =>
    request.patch(`/api/v1/reports/${id}/read`),
};
```

---

## 五、页面组件设计

### 5.1 报告列表页（ReportCenter）

```tsx
// src/pages/ReportCenter/index.tsx
import React, { useState, useEffect } from "react";
import {
  Input, Select, Button, Card, Badge, Empty, Spin,
  Dropdown, Tag, Tooltip, Pagination
} from "@arco-design/web-react";
import {
  Search, RefreshCw, FileText, Eye, Download,
  Star, Trash2, Clock, Filter, MoreHorizontal
} from "lucide-react";
import { useNavigate } from "react-router-dom";
import { reportApi } from "@/api/report";
import { Report, ReportStatus } from "@/types/report";
import ReportCard from "./components/ReportCard";
import ReportPreviewModal from "./components/ReportPreviewModal";
import "./index.css";

const ReportCenter: React.FC = () => {
  const navigate = useNavigate();
  const [reports, setReports] = useState<Report[]>([]);
  const [loading, setLoading] = useState(false);
  const [filter, setFilter] = useState({
    keyword: "",
    flowId: "",
    status: "",
    dateRange: "",
  });
  const [pagination, setPagination] = useState({
    current: 1,
    pageSize: 10,
    total: 0,
  });
  const [previewReport, setPreviewReport] = useState<Report | null>(null);

  const loadReports = async () => {
    setLoading(true);
    try {
      const res = await reportApi.getReports({
        ...filter,
        page: pagination.current,
        pageSize: pagination.pageSize,
      });
      setReports(res.data.list);
      setPagination(prev => ({ ...prev, total: res.data.total }));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadReports();
  }, [filter, pagination.current]);

  const flowOptions = [
    { label: "全部流程", value: "" },
    { label: "RNA-seq 差异表达分析", value: "rna_seq" },
    { label: "ATAC-seq 染色质可及性分析", value: "atac_seq" },
  ];

  const statusOptions = [
    { label: "全部状态", value: "" },
    { label: "已完成", value: "completed" },
    { label: "生成中", value: "generating" },
    { label: "失败", value: "failed" },
  ];

  const dateOptions = [
    { label: "全部时间", value: "" },
    { label: "最近7天", value: "7d" },
    { label: "最近30天", value: "30d" },
    { label: "最近90天", value: "90d" },
  ];

  return (
    <div className="report-center-page">
      <div className="page-header">
        <div>
          <h1 className="page-title">
            <FileText size={24} />
            结果报告中心
          </h1>
          <p className="page-subtitle">
            查看和管理所有分析生成的报告，支持在线预览和下载
          </p>
        </div>
      </div>

      <Card className="filter-card">
        <div className="filter-bar">
          <Input
            placeholder="搜索报告名称、流程、标签..."
            prefix={<Search size={16} />}
            value={filter.keyword}
            onChange={(v) => setFilter(prev => ({ ...prev, keyword: v }))}
            allowClear
            style={{ width: 280 }}
          />
          <Select
            placeholder="分析流程"
            options={flowOptions}
            value={filter.flowId}
            onChange={(v) => setFilter(prev => ({ ...prev, flowId: v }))}
            style={{ width: 200 }}
          />
          <Select
            placeholder="状态"
            options={statusOptions}
            value={filter.status}
            onChange={(v) => setFilter(prev => ({ ...prev, status: v }))}
            style={{ width: 140 }}
          />
          <Select
            placeholder="时间范围"
            options={dateOptions}
            value={filter.dateRange}
            onChange={(v) => setFilter(prev => ({ ...prev, dateRange: v }))}
            style={{ width: 140 }}
          />
          <Button
            icon={<RefreshCw size={16} />}
            onClick={loadReports}
          >
            刷新
          </Button>
        </div>
      </Card>

      <div className="stats-bar">
        <StatCard title="总报告数" value={pagination.total} icon="FileText" />
        <StatCard title="今日生成" value={0} icon="TrendingUp" />
        <StatCard title="生成中" value={0} icon="Clock" />
        <StatCard title="收藏" value={0} icon="Star" />
      </div>

      <Spin loading={loading} style={{ width: "100%" }}>
        {reports.length > 0 ? (
          <div className="report-list">
            {reports.map(report => (
              <ReportCard
                key={report.id}
                report={report}
                onPreview={() => setPreviewReport(report)}
                onDownload={(file) => handleDownload(report, file)}
                onDelete={() => handleDelete(report)}
                onToggleStar={() => handleToggleStar(report)}
                onViewTask={() => navigate(`/tasks/${report.taskId}`)}
              />
            ))}
          </div>
        ) : (
          <Empty
            icon={<FileText size={48} color="#ddd" />}
            description="暂无报告，前往分析中心提交任务生成报告"
          >
            <Button type="primary" onClick={() => navigate("/analysis")}>
              前往分析中心
            </Button>
          </Empty>
        )}
      </Spin>

      {reports.length > 0 && (
        <Pagination
          current={pagination.current}
          pageSize={pagination.pageSize}
          total={pagination.total}
          onChange={(page) => setPagination(prev => ({ ...prev, current: page }))}
          showTotal
          showJumper
        />
      )}

      {previewReport && (
        <ReportPreviewModal
          report={previewReport}
          onClose={() => setPreviewReport(null)}
        />
      )}
    </div>
  );
};

export default ReportCenter;
```

### 5.2 报告卡片组件（ReportCard）

```tsx
// src/pages/ReportCenter/components/ReportCard.tsx
import React from "react";
import { Card, Badge, Button, Tag, Tooltip, Progress } from "@arco-design/web-react";
import {
  Eye, Download, Star, Trash2, ExternalLink,
  Clock, Database, CheckCircle, AlertCircle
} from "lucide-react";
import { Report, ReportFile } from "@/types/report";
import { formatBytes, formatDuration, formatDateTime } from "@/utils/format";
import "./ReportCard.css";

interface ReportCardProps {
  report: Report;
  onPreview: () => void;
  onDownload: (file: ReportFile) => void;
  onDelete: () => void;
  onToggleStar: () => void;
  onViewTask: () => void;
}

const ReportCard: React.FC<ReportCardProps> = ({
  report,
  onPreview,
  onDownload,
  onDelete,
  onToggleStar,
  onViewTask,
}) => {
  const statusConfig = {
    generating: { color: "orange", icon: <Clock size={14} />, text: "生成中" },
    completed: { color: "green", icon: <CheckCircle size={14} />, text: "已完成" },
    failed: { color: "red", icon: <AlertCircle size={14} />, text: "失败" },
    expired: { color: "gray", icon: <Clock size={14} />, text: "已过期" },
  };

  const status = statusConfig[report.status];
  const primaryFile = report.files.find(f => f.isPrimary) || report.files[0];

  return (
    <Card className={`report-card ${report.status}`}>
      <div className="report-card-content">
        <div className="report-icon">
          <span className="flow-emoji">{report.flowIcon}</span>
          {report.status === "generating" && (
            <Progress
              type="circle"
              size="small"
              percent={report.progress || 0}
              status="active"
            />
          )}
        </div>

        <div className="report-info">
          <div className="report-header">
            <h3 className="report-title">{report.title}</h3>
            <Badge status={status.color} text={status.text} />
            {report.isStarred && <Star size={16} className="star-icon" fill="#FFB800" color="#FFB800" />}
          </div>

          <p className="report-desc">{report.description}</p>

          <div className="report-meta">
            <span className="meta-item">
              <Clock size={12} />
              {formatDateTime(report.createdAt)}
            </span>
            <span className="meta-item">
              <Database size={12} />
              {report.sampleCount} 个样本
            </span>
            <span className="meta-item">
              <Clock size={12} />
              耗时 {formatDuration(report.duration)}
            </span>
            {report.flowVersion && (
              <Tag size="small" color="arcoblue">
                v{report.flowVersion}
              </Tag>
            )}
          </div>

          <div className="report-files">
            {report.files.map(file => (
              <Tag
                key={file.id}
                size="small"
                color={file.type === "html" ? "arcoblue" : "gray"}
                className="file-tag"
              >
                {file.name} ({formatBytes(file.size)})
              </Tag>
            ))}
          </div>
        </div>

        <div className="report-actions">
          {report.status === "completed" && (
            <>
              <Tooltip content="预览报告">
                <Button
                  type="primary"
                  icon={<Eye size={16} />}
                  onClick={onPreview}
                >
                  预览
                </Button>
              </Tooltip>

              <Tooltip content="下载 HTML">
                <Button
                  icon={<Download size={16} />}
                  onClick={() => onDownload(primaryFile)}
                >
                  下载
                </Button>
              </Tooltip>
            </>
          )}

          <Tooltip content="查看关联任务">
            <Button
              icon={<ExternalLink size={16} />}
              onClick={onViewTask}
            >
              任务
            </Button>
          </Tooltip>

          <Tooltip content={report.isStarred ? "取消收藏" : "收藏"}>
            <Button
              icon={
                <Star
                  size={16}
                  fill={report.isStarred ? "#FFB800" : "none"}
                  color={report.isStarred ? "#FFB800" : "#999"}
                />
              }
              onClick={onToggleStar}
            />
          </Tooltip>

          <Tooltip content="删除">
            <Button
              icon={<Trash2 size={16} />}
              status="danger"
              onClick={onDelete}
            />
          </Tooltip>
        </div>
      </div>
    </Card>
  );
};

export default ReportCard;
```

### 5.3 报告预览弹窗（ReportPreviewModal）

```tsx
// src/pages/ReportCenter/components/ReportPreviewModal.tsx
import React, { useState, useEffect } from "react";
import { Modal, Spin, Button } from "@arco-design/web-react";
import { X, Download, ExternalLink, Maximize2 } from "lucide-react";
import { reportApi } from "@/api/report";
import { Report } from "@/types/report";
import "./ReportPreviewModal.css";

interface ReportPreviewModalProps {
  report: Report;
  onClose: () => void;
  onOpenInNewTab?: () => void;
}

const ReportPreviewModal: React.FC<ReportPreviewModalProps> = ({
  report,
  onClose,
  onOpenInNewTab,
}) => {
  const [htmlContent, setHtmlContent] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [isFullscreen, setIsFullscreen] = useState(false);

  useEffect(() => {
    loadPreview();
  }, [report.id]);

  const loadPreview = async () => {
    setLoading(true);
    try {
      const res = await reportApi.previewReport(report.id);
      setHtmlContent(res.data);
    } catch (error) {
      setHtmlContent("<p>报告加载失败，请尝试下载查看</p>");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal
      title={
        <div className="preview-modal-header">
          <span>{report.title}</span>
          <div className="preview-actions">
            <Button
              icon={<Download size={16} />}
              onClick={() => handleDownload(report)}
            >
              下载
            </Button>
            <Button
              icon={<ExternalLink size={16} />}
              onClick={onOpenInNewTab}
            >
              新窗口打开
            </Button>
            <Button
              icon={<Maximize2 size={16} />}
              onClick={() => setIsFullscreen(!isFullscreen)}
            >
              {isFullscreen ? "退出全屏" : "全屏"}
            </Button>
            <Button
              icon={<X size={16} />}
              onClick={onClose}
            />
          </div>
        </div>
      }
      visible={true}
      onCancel={onClose}
      footer={null}
      width={isFullscreen ? "100%" : "90%"}
      style={{
        maxWidth: isFullscreen ? "100%" : "1200px",
        top: isFullscreen ? 0 : "5vh",
      }}
      wrapClassName={isFullscreen ? "fullscreen-modal" : ""}
    >
      <Spin loading={loading} style={{ width: "100%", minHeight: 400 }}>
        <div className="preview-container">
          <iframe
            srcDoc={htmlContent}
            title={report.title}
            className="preview-iframe"
            sandbox="allow-scripts allow-same-origin"
          />
        </div>
      </Spin>
    </Modal>
  );
};

export default ReportPreviewModal;
```

```css
/* ReportPreviewModal.css */
.preview-modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
}

.preview-actions {
  display: flex;
  gap: 8px;
}

.preview-container {
  width: 100%;
  height: 70vh;
  border-radius: 8px;
  overflow: hidden;
  background: #fff;
}

.preview-iframe {
  width: 100%;
  height: 100%;
  border: none;
}

.fullscreen-modal .arco-modal {
  width: 100% !important;
  max-width: 100% !important;
  height: 100vh !important;
  margin: 0 !important;
  top: 0 !important;
  border-radius: 0 !important;
}

.fullscreen-modal .preview-container {
  height: calc(100vh - 120px);
}
```

---

## 六、CSS 样式

```css
/* ReportCenter/index.css */
.report-center-page {
  padding: 24px;
  max-width: 1200px;
  margin: 0 auto;
}

.page-header {
  margin-bottom: 24px;
}

.page-title {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 24px;
  font-weight: 600;
  color: #1a1a1a;
  margin: 0 0 8px;
}

.page-subtitle {
  font-size: 14px;
  color: #666;
  margin: 0;
}

/* 筛选栏 */
.filter-card {
  margin-bottom: 20px;
}

.filter-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

/* 统计概览 */
.stats-bar {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 24px;
}

/* 报告列表 */
.report-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin-bottom: 24px;
}

/* ReportCard.css */
.report-card {
  transition: all 0.2s;
}

.report-card:hover {
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.08);
  transform: translateY(-2px);
}

.report-card.generating {
  border-left: 3px solid #ff7d00;
}

.report-card.completed {
  border-left: 3px solid #00b42a;
}

.report-card.failed {
  border-left: 3px solid #f53f3f;
}

.report-card-content {
  display: flex;
  gap: 16px;
  align-items: flex-start;
}

.report-icon {
  width: 48px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.flow-emoji {
  font-size: 32px;
}

.report-info {
  flex: 1;
  min-width: 0;
}

.report-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
}

.report-title {
  font-size: 16px;
  font-weight: 600;
  color: #1a1a1a;
  margin: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.star-icon {
  flex-shrink: 0;
}

.report-desc {
  font-size: 13px;
  color: #666;
  margin: 0 0 12px;
  line-height: 1.6;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.report-meta {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}

.meta-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: #999;
}

.report-files {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.file-tag {
  cursor: pointer;
}

.report-actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
  align-items: flex-start;
}
```

---

## 七、与现有模块的集成

### 7.1 分析中心 -> 报告中心

在分析中心的"三步开始你的分析"第三步"查看分析结果"卡片，点击后跳转到报告中心并自动筛选该任务的报告。

```tsx
<Button
  type="primary"
  icon={<FileText size={16} />}
  onClick={() => navigate(`/reports?taskId=${taskId}`)}
>
  查看报告
</Button>
```

### 7.2 任务中心 -> 报告中心

任务完成后，在任务列表中显示"查看报告"按钮。

```tsx
{task.status === "completed" && task.reportId && (
  <Button
    type="primary"
    size="small"
    icon={<Eye size={14} />}
    onClick={() => navigate(`/reports/${task.reportId}`)}
  >
    查看报告
  </Button>
)}
```

### 7.3 报告中心 -> 任务中心

报告卡片中的"查看任务"按钮跳转到关联任务详情。

---

## 八、后端配合需求

### 8.1 新增接口

| 接口 | 方法 | 说明 |
|------|------|------|
| /api/v1/reports | GET | 获取报告列表（支持筛选、分页） |
| /api/v1/reports/:id | GET | 获取报告详情 |
| /api/v1/reports/:id/preview | GET | 获取报告 HTML 内容（用于 iframe 预览） |
| /api/v1/reports/:id/files/:fileId/download | GET | 下载报告文件 |
| /api/v1/reports/:id | DELETE | 删除报告（仅删除记录，文件由存储服务处理） |
| /api/v1/reports/:id/star | PATCH | 收藏/取消收藏 |
| /api/v1/reports/:id/read | PATCH | 标记已读 |

### 8.2 数据表设计

```sql
CREATE TABLE reports (
  id VARCHAR(36) PRIMARY KEY,
  task_id VARCHAR(36) NOT NULL,
  flow_id VARCHAR(50) NOT NULL,
  flow_name VARCHAR(100) NOT NULL,
  flow_version VARCHAR(20),
  flow_icon VARCHAR(50),
  title VARCHAR(200) NOT NULL,
  description TEXT,
  status ENUM('generating', 'completed', 'failed', 'expired') DEFAULT 'generating',
  sample_count INT DEFAULT 0,
  duration INT DEFAULT 0,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  completed_at TIMESTAMP NULL,
  is_read TINYINT(1) DEFAULT 0,
  is_starred TINYINT(1) DEFAULT 0,
  INDEX idx_task_id (task_id),
  INDEX idx_flow_id (flow_id),
  INDEX idx_status (status),
  INDEX idx_created_at (created_at)
);

CREATE TABLE report_files (
  id VARCHAR(36) PRIMARY KEY,
  report_id VARCHAR(36) NOT NULL,
  name VARCHAR(200) NOT NULL,
  type ENUM('html', 'pdf', 'png', 'zip', 'csv') NOT NULL,
  size BIGINT DEFAULT 0,
  url VARCHAR(500) NOT NULL,
  is_primary TINYINT(1) DEFAULT 0,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (report_id) REFERENCES reports(id) ON DELETE CASCADE
);
```

---

## 九、文件结构

```
src/
├── pages/
│   └── ReportCenter/
│       ├── index.tsx                    # 报告列表页
│       ├── index.css                    # 列表页样式
│       ├── Preview.tsx                  # 报告预览页（独立路由）
│       ├── Preview.css                  # 预览页样式
│       └── components/
│           ├── ReportCard.tsx           # 报告卡片
│           ├── ReportCard.css           # 卡片样式
│           ├── ReportPreviewModal.tsx   # 预览弹窗
│           ├── ReportPreviewModal.css   # 弹窗样式
│           ├── StatCard.tsx             # 统计卡片
│           └── EmptyState.tsx           # 空状态
├── api/
│   └── report.ts                        # 报告 API
├── types/
│   └── report.ts                        # 报告类型定义
└── utils/
    └── format.ts                        # 格式化工具（bytes、duration、datetime）
```

---

## 十、实施建议

### 10.1 优先级

| 优先级 | 功能 | 说明 |
|--------|------|------|
| P0 | 报告列表页 | 基础展示、筛选、分页 |
| P0 | 报告预览 | iframe 加载 HTML 报告 |
| P0 | 报告下载 | 下载 HTML/PDF 文件 |
| P1 | 与任务中心联动 | 任务完成后自动生成报告记录 |
| P1 | 收藏功能 | 收藏常用报告 |
| P2 | 统计概览 | 顶部数据卡片 |
| P2 | 全屏预览 | 报告全屏查看模式 |

### 10.2 注意事项

1. HTML 报告安全性：iframe 使用 sandbox="allow-scripts allow-same-origin"，防止恶意脚本
2. 大报告加载：超过 10MB 的 HTML 报告建议先下载再查看，避免浏览器卡顿
3. 报告过期策略：设置报告保留期限（如 90 天），过期后自动清理文件但保留记录
4. 存储优化：HTML 报告可压缩存储，预览时解压

---

*文档由 OmicHub 技术委员会（阿姨）编制*
*"分析只是开始，报告才是交付。"*
