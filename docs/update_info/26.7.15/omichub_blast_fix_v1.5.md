# OmicHub BLAST 紧急修复与数据管理优化 v1.5

> 日期: 2026-07-15  
> 问题: 1) Graphic Summary 图例与标签重叠; 2) 数据库管理缺少数据清理功能; 3) 用户隔离需明确  
> 目标: 精准修复视觉问题 + 新增数据清理功能 + 强化用户隔离

---

## 一、Graphic Summary 视觉修复 (基于最新截图)

### 1.1 截图诊断

**现状问题:**
- `Chr1` 标签和 `Identity:` 图例**垂直重叠**
- 图例位置计算错误：`transform="translate(${padding.left}, ${svgHeight - 14})"` 和 Hit track 的 y 坐标冲突
- 单条结果时纵向空间浪费严重
- 标尺数字 `1` 和 `36` 太靠边，视觉不平衡

**修复目标:**
- 图例移到 SVG 底部独立区域，不与任何 Hit 标签重叠
- 单条结果时压缩纵向空间
- 标尺数字内移，增加 padding

### 1.2 修复后的 GraphicSummary 组件

```tsx
// src/components/Blast/BlastGraphicSummary.tsx
import React from "react";
import { Card, Tooltip } from "@arco-design/web-react";

interface HitData {
  hit_num: number;
  hit_id: string;
  hsps: Array<{
    query_from: number;
    query_to: number;
    identity_percent: number;
    evalue: number;
    bit_score: number;
  }>;
}

interface Props {
  queryLen: number;
  hits: HitData[];
}

const BlastGraphicSummary: React.FC<Props> = ({ queryLen, hits }) => {
  const svgWidth = 800;
  const padding = { left: 70, right: 50, top: 24, bottom: 28 };
  const barHeight = 16;
  const trackGap = 6;
  const trackHeight = barHeight + trackGap;
  const legendHeight = 20;

  // 计算高度：顶部padding + Query标尺 + 间距 + hits + 底部padding + 图例
  const contentHeight = 20 + 8 + hits.length * trackHeight;
  const svgHeight = padding.top + contentHeight + padding.bottom + legendHeight;

  const scale = (pos: number) =>
    padding.left + (pos / queryLen) * (svgWidth - padding.left - padding.right);

  const getColor = (identity: number) => {
    if (identity >= 90) return "#10b981";
    if (identity >= 70) return "#3b82f6";
    if (identity >= 40) return "#f59e0b";
    return "#ef4444";
  };

  // Query 标尺的 y 位置
  const rulerY = padding.top + 10;
  // 第一个 Hit 的 y 位置
  const firstHitY = rulerY + 18;

  return (
    <Card size="small" title="Graphic Summary" style={{ marginBottom: 12 }} bodyStyle={{ padding: "8px 16px 12px" }}>
      <svg width="100%" viewBox={`0 0 ${svgWidth} ${svgHeight}`} style={{ fontFamily: "monospace" }}>
        {/* Query 标尺标签 */}
        <text x={padding.left - 10} y={rulerY + 4} textAnchor="end" fill="#6b7280" fontSize={11} fontWeight={500}>
          Query
        </text>

        {/* 标尺线 */}
        <line
          x1={padding.left}
          y1={rulerY}
          x2={svgWidth - padding.right}
          y2={rulerY}
          stroke="#d1d5db"
          strokeWidth={2}
        />

        {/* 标尺刻度 */}
        <text x={padding.left} y={rulerY - 6} textAnchor="middle" fill="#9ca3af" fontSize={9}>1</text>
        <text x={svgWidth - padding.right} y={rulerY - 6} textAnchor="middle" fill="#9ca3af" fontSize={9}>
          {queryLen}
        </text>

        {/* Hit tracks */}
        {hits.map((hit, idx) => {
          const y = firstHitY + idx * trackHeight;
          return (
            <g key={hit.hit_num}>
              {/* Hit ID 标签 */}
              <text x={padding.left - 10} y={y + barHeight - 3} textAnchor="end" fill="#374151" fontSize={11}>
                {hit.hit_id}
              </text>

              {/* HSP bars */}
              {hit.hsps.map((hsp, hspIdx) => {
                const x = scale(hsp.query_from);
                const width = scale(hsp.query_to) - x;
                const color = getColor(hsp.identity_percent);

                return (
                  <Tooltip
                    key={hspIdx}
                    content={
                      <div style={{ fontSize: 12, lineHeight: 1.5 }}>
                        <div><strong>{hit.hit_id}</strong> HSP #{hspIdx + 1}</div>
                        <div>Query: {hsp.query_from}-{hsp.query_to}</div>
                        <div>Identity: {hsp.identity_percent.toFixed(1)}%</div>
                        <div>E: {hsp.evalue.toExponential(2)}</div>
                      </div>
                    }
                  >
                    <rect
                      x={x}
                      y={y}
                      width={Math.max(width, 3)}
                      height={barHeight}
                      rx={4}
                      fill={color}
                      opacity={0.9}
                      style={{ cursor: "pointer" }}
                    />
                  </Tooltip>
                );
              })}
            </g>
          );
        })}

        {/* 图例 - 固定在底部，不与任何元素重叠 */}
        <g transform={`translate(${padding.left}, ${svgHeight - 18})`}>
          <text x={0} y={0} fontSize={10} fill="#6b7280" fontWeight={500}>Identity:</text>
          {[
            { c: "#10b981", l: "≥90%" },
            { c: "#3b82f6", l: "≥70%" },
            { c: "#f59e0b", l: "≥40%" },
            { c: "#ef4444", l: "<40%" },
          ].map((item, i) => (
            <g key={i} transform={`translate(${55 + i * 60}, -8)`}>
              <rect width={12} height={12} rx={3} fill={item.c} />
              <text x={16} y={10} fontSize={10} fill="#6b7280">{item.l}</text>
            </g>
          ))}
        </g>
      </svg>
    </Card>
  );
};

export default BlastGraphicSummary;
```

**关键修复点:**
1. `rulerY` 和 `firstHitY` 分开计算，确保不重叠
2. 图例 `transform` 使用 `svgHeight - 18`，固定在 SVG 最底部
3. `svgHeight` 计算包含 `legendHeight`，确保图例有独立空间
4. 单条结果时整体高度约 90px，不再浪费空间

---

## 二、BLAST 数据库管理 - 数据清理功能

### 2.1 需求

| 功能 | 说明 | 权限 |
|------|------|------|
| 清理 7 天前数据 | 删除所有 7 天前完成的 BLAST 任务及其结果文件 | 管理员 |
| 清理所有数据 | 删除所有 BLAST 任务及其结果文件（保留数据库索引） | 管理员 |
| 用户结果隔离 | 普通用户只能查看/下载/删除自己的任务结果 | 系统强制 |

### 2.2 后端 API 设计

```python
# backend/routes/blast_admin.py

from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
import os
import shutil

router = APIRouter(prefix="/api/blast/admin", tags=["BLAST Admin"])

@router.post("/cleanup/old")
async def cleanup_old_tasks(
    days: int = 7,
    current_user: User = Depends(require_admin),
    background_tasks: BackgroundTasks = None,
):
    """
    清理 N 天前完成的 BLAST 任务。
    只删除结果文件，保留数据库记录（标记为 cleaned）。
    """
    cutoff = datetime.utcnow() - timedelta(days=days)

    tasks = db.query(BlastTask).filter(
        BlastTask.status.in_(["completed", "failed"]),
        BlastTask.completed_at < cutoff,
        BlastTask.result_path.isnot(None)
    ).all()

    deleted_count = 0
    for task in tasks:
        # 删除结果文件
        if task.result_path and os.path.exists(task.result_path):
            try:
                os.remove(task.result_path)
                # 同时删除关联的 json/txt 文件
                for ext in [".json", ".txt"]:
                    alt_path = task.result_path.replace(".xml", ext)
                    if os.path.exists(alt_path):
                        os.remove(alt_path)
            except Exception as e:
                print(f"Failed to delete {task.result_path}: {e}")
                continue

        # 删除上传的查询序列文件
        if task.query_file_path and os.path.exists(task.query_file_path):
            try:
                os.remove(task.query_file_path)
            except:
                pass

        # 标记为已清理（保留元数据记录）
        task.result_path = None
        task.query_file_path = None
        task.result_size_kb = None
        task.status = "cleaned"
        deleted_count += 1

    db.commit()

    return {
        "message": f"已清理 {deleted_count} 个任务的结果文件",
        "cutoff_date": cutoff.isoformat(),
        "deleted_count": deleted_count,
    }


@router.post("/cleanup/all")
async def cleanup_all_tasks(
    confirm: bool = False,
    current_user: User = Depends(require_admin),
):
    """
    清理所有 BLAST 任务结果（保留数据库索引）。
    需要 confirm=true 确认。
    """
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="请设置 confirm=true 以确认清理所有数据。此操作不可恢复！"
        )

    tasks = db.query(BlastTask).filter(
        BlastTask.status.in_(["completed", "failed", "cleaned"])
    ).all()

    deleted_count = 0
    for task in tasks:
        if task.result_path and os.path.exists(task.result_path):
            try:
                os.remove(task.result_path)
                for ext in [".json", ".txt"]:
                    alt_path = task.result_path.replace(".xml", ext)
                    if os.path.exists(alt_path):
                        os.remove(alt_path)
            except:
                pass

        if task.query_file_path and os.path.exists(task.query_file_path):
            try:
                os.remove(task.query_file_path)
            except:
                pass

        task.result_path = None
        task.query_file_path = None
        task.result_size_kb = None
        task.status = "cleaned"
        deleted_count += 1

    db.commit()

    return {
        "message": f"已清理所有 {deleted_count} 个任务的结果文件",
        "deleted_count": deleted_count,
    }


@router.get("/storage-stats")
async def get_storage_stats(
    current_user: User = Depends(require_admin),
):
    """
    获取 BLAST 结果存储统计。
    """
    total_tasks = db.query(BlastTask).count()
    completed_tasks = db.query(BlastTask).filter(BlastTask.status == "completed").count()
    cleaned_tasks = db.query(BlastTask).filter(BlastTask.status == "cleaned").count()

    # 计算结果目录总大小
    result_dir = "/data/omichub/blast_results"
    total_size = 0
    if os.path.exists(result_dir):
        for dirpath, dirnames, filenames in os.walk(result_dir):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                total_size += os.path.getsize(fp)

    return {
        "total_tasks": total_tasks,
        "completed_tasks": completed_tasks,
        "cleaned_tasks": cleaned_tasks,
        "storage_mb": round(total_size / (1024 * 1024), 2),
        "result_dir": result_dir,
    }
```

### 2.3 前端数据库管理页面

```tsx
// src/pages/Admin/BlastDatabaseAdminPage.tsx
import React, { useState } from "react";
import {
  Card, Table, Button, Modal, Message, Space, Statistic,
  Descriptions, Popconfirm, Divider
} from "@arco-design/web-react";
import { IconDelete, IconRefresh, IconPlus, IconClear } from "@arco-design/web-react/icon";

const BlastDatabaseAdminPage: React.FC = () => {
  const [stats, setStats] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  // 获取存储统计
  const fetchStats = async () => {
    const res = await fetch("/api/blast/admin/storage-stats");
    const data = await res.json();
    setStats(data);
  };

  // 清理 7 天前数据
  const handleCleanupOld = async () => {
    Modal.confirm({
      title: "确认清理 7 天前的数据？",
      content: "这将删除 7 天前完成的 BLAST 任务的结果文件，保留数据库记录。此操作不可恢复。",
      onOk: async () => {
        setLoading(true);
        try {
          const res = await fetch("/api/blast/admin/cleanup/old?days=7", { method: "POST" });
          const data = await res.json();
          Message.success(data.message);
          fetchStats();
        } catch (e) {
          Message.error("清理失败");
        } finally {
          setLoading(false);
        }
      },
    });
  };

  // 清理所有数据
  const handleCleanupAll = async () => {
    Modal.confirm({
      title: "⚠️ 确认清理所有数据？",
      content: "这将删除所有 BLAST 任务的结果文件，保留数据库索引和元数据记录。此操作不可恢复！",
      okButtonProps: { status: "danger" },
      onOk: async () => {
        setLoading(true);
        try {
          const res = await fetch("/api/blast/admin/cleanup/all?confirm=true", { method: "POST" });
          const data = await res.json();
          Message.success(data.message);
          fetchStats();
        } catch (e) {
          Message.error("清理失败");
        } finally {
          setLoading(false);
        }
      },
    });
  };

  return (
    <div style={{ padding: 24 }}>
      <Card title="BLAST 数据库管理" style={{ marginBottom: 16 }}>
        {/* 存储统计 */}
        <div style={{ marginBottom: 16 }}>
          <h3 style={{ fontSize: 14, marginBottom: 12 }}>存储统计</h3>
          <Space size="large">
            <Statistic title="总任务数" value={stats?.total_tasks || 0} />
            <Statistic title="已完成" value={stats?.completed_tasks || 0} />
            <Statistic title="已清理" value={stats?.cleaned_tasks || 0} />
            <Statistic title="存储占用" value={`${stats?.storage_mb || 0} MB`} />
          </Space>
        </div>

        <Divider />

        {/* 数据清理操作 */}
        <div style={{ marginBottom: 16 }}>
          <h3 style={{ fontSize: 14, marginBottom: 12 }}>数据清理</h3>
          <Space>
            <Popconfirm
              title="清理 7 天前的数据"
              content="删除 7 天前完成的任务结果文件，保留记录。"
              onOk={handleCleanupOld}
            >
              <Button type="primary" status="warning" icon={<IconClear />} loading={loading}>
                清理 7 天前数据
              </Button>
            </Popconfirm>

            <Popconfirm
              title="⚠️ 清理所有数据"
              content="删除所有任务结果文件，保留数据库索引。不可恢复！"
              onOk={handleCleanupAll}
            >
              <Button type="primary" status="danger" icon={<IconDelete />} loading={loading}>
                清理所有数据
              </Button>
            </Popconfirm>
          </Space>
        </div>

        <Divider />

        {/* 数据库列表 */}
        <div>
          <h3 style={{ fontSize: 14, marginBottom: 12 }}>数据库列表</h3>
          <Table
            columns={[
              { title: "ID", dataIndex: "id", width: 80 },
              { title: "名称", dataIndex: "name" },
              { title: "标识", dataIndex: "db_key", width: 100 },
              { title: "类型", dataIndex: "db_type", width: 80 },
              { title: "状态", dataIndex: "build_status", width: 100 },
              { title: "序列数", dataIndex: "sequence_count", width: 80 },
              { title: "大小 (MB)", dataIndex: "file_size_mb", width: 100 },
              { title: "公开", dataIndex: "is_public", width: 80 },
              { title: "操作", render: (_, record) => (
                <Space>
                  <Button size="small" icon={<IconRefresh />}>重建</Button>
                  <Button size="small" status="danger" icon={<IconDelete />}>删除</Button>
                </Space>
              )},
            ]}
            data={[]}
          />
        </div>
      </Card>
    </div>
  );
};

export default BlastDatabaseAdminPage;
```

---

## 三、用户结果隔离设计

### 3.1 隔离原则

| 层面 | 隔离措施 | 实现方式 |
|------|----------|----------|
| **文件系统** | 用户结果文件按 user_id 分目录 | `/data/omichub/blast_results/{user_id}/` |
| **数据库** | 用户只能查询自己的任务记录 | `WHERE user_id = current_user.id` |
| **API 权限** | 用户无法访问他人任务 | 路由层校验 `task.user_id == current_user.id` |
| **下载认证** | 下载链接必须携带有效 Token | `Authorization: Bearer` + Cookie fallback |
| **管理员例外** | 管理员可查看所有任务 | `require_admin` 装饰器 |

### 3.2 文件目录结构

```
/data/omichub/
├── blast_db/                    # 数据库索引（全局共享，只读）
│   ├── tra10/
│   │   ├── source.fasta
│   │   ├── tra10.nhr
│   │   ├── tra10.nin
│   │   └── tra10.nsq
│   └── test/
│       └── ...
├── blast_uploads/               # 用户上传的查询序列（按用户隔离）
│   ├── user_1/
│   │   ├── task_xxx_query.fasta
│   │   └── task_yyy_query.fasta
│   ├── user_2/
│   │   └── ...
│   └── admin/
│       └── ...
└── blast_results/               # 任务结果文件（按用户隔离）
    ├── user_1/
    │   ├── task_xxx.xml
    │   ├── task_xxx.json
    │   └── task_xxx.txt
    ├── user_2/
    │   └── ...
    └── admin/
        └── ...
```

### 3.3 后端权限校验（所有路由必须实现）

```python
# backend/routes/blast.py

@router.get("/results/{task_id}")
async def get_blast_results(
    task_id: str,
    format: Literal["json", "xml", "text", "summary"] = "json",
    current_user: User = Depends(get_current_user),
):
    task = db.query(BlastTask).filter(BlastTask.task_id == task_id).first()

    # ===== 核心隔离校验 =====
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    # 普通用户只能访问自己的任务
    if task.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="无权访问此任务")

    # ... 后续逻辑


@router.get("/tasks")
async def list_user_tasks(
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(get_current_user),
):
    """用户只能查看自己的任务列表"""
    query = db.query(BlastTask).filter(BlastTask.user_id == current_user.id)

    if status:
        query = query.filter(BlastTask.status == status)

    total = query.count()
    tasks = query.order_by(BlastTask.submitted_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "tasks": tasks,
    }


@router.post("/tasks/{task_id}/cancel")
async def cancel_blast_task(
    task_id: str,
    current_user: User = Depends(get_current_user),
):
    """用户只能取消自己的任务"""
    task = db.query(BlastTask).filter(BlastTask.task_id == task_id).first()

    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    if task.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="无权取消此任务")

    if task.status not in ["queued", "running"]:
        raise HTTPException(status_code=400, detail=f"任务状态为 {task.status}，无法取消")

    # 撤销 Celery 任务
    celery.control.revoke(task_id, terminate=True)
    task.status = "cancelled"
    db.commit()

    return {"message": "任务已取消"}
```

### 3.4 Celery 任务中的文件路径隔离

```python
# backend/tasks/blast_search.py

@shared_task(bind=True, queue="blast_search")
def blast_search_task(self, task_id: str):
    db = SessionLocal()
    try:
        task = db.query(BlastTask).filter(BlastTask.task_id == task_id).first()

        # 用户隔离目录
        user_id = task.user_id
        upload_dir = f"/data/omichub/blast_uploads/user_{user_id}"
        result_dir = f"/data/omichub/blast_results/user_{user_id}"

        os.makedirs(upload_dir, exist_ok=True)
        os.makedirs(result_dir, exist_ok=True)

        query_file = f"{upload_dir}/{task_id}_query.fasta"
        result_xml = f"{result_dir}/{task_id}.xml"
        result_json = f"{result_dir}/{task_id}.json"

        # ... 执行 BLAST

        # 更新结果路径
        task.result_path = result_xml
        db.commit()

    finally:
        db.close()
```

### 3.5 数据清理时的隔离

```python
# 清理时按用户目录删除，确保不越界

def cleanup_user_results(user_id: int):
    """清理指定用户的结果文件"""
    user_result_dir = f"/data/omichub/blast_results/user_{user_id}"
    user_upload_dir = f"/data/omichub/blast_uploads/user_{user_id}"

    if os.path.exists(user_result_dir):
        shutil.rmtree(user_result_dir)
        os.makedirs(user_result_dir, exist_ok=True)

    if os.path.exists(user_upload_dir):
        shutil.rmtree(user_upload_dir)
        os.makedirs(user_upload_dir, exist_ok=True)
```

---

## 四、修改文件清单

| 文件 | 修改内容 |
|------|----------|
| `src/components/Blast/BlastGraphicSummary.tsx` | 修复图例与标签重叠，压缩单条结果空间 |
| `backend/routes/blast_admin.py` | 新增 `cleanup/old`、`cleanup/all`、`storage-stats` 接口 |
| `src/pages/Admin/BlastDatabaseAdminPage.tsx` | 新增存储统计面板、数据清理按钮 |
| `backend/routes/blast.py` | 所有路由增加 `user_id` 隔离校验 |
| `backend/tasks/blast_search.py` | 文件路径按 `user_{id}` 分目录 |
| `backend/models/blast.py` | 可选：增加 `cleaned` 状态到 `status` 枚举 |

---

## 五、验收标准

### 5.1 视觉修复
- [ ] Graphic Summary 中 `Chr1` 标签和图例不重叠
- [ ] 单条结果时 Graphic Summary 高度不超过 120px
- [ ] 图例显示在 SVG 底部独立区域
- [ ] 标尺数字 `1` 和 `36` 视觉平衡

### 5.2 数据清理
- [ ] 管理员可在数据库管理页面查看存储统计
- [ ] 点击"清理 7 天前数据"弹出确认框，确认后删除旧结果文件
- [ ] 点击"清理所有数据"弹出危险确认框，确认后删除所有结果文件
- [ ] 清理后保留数据库记录（状态变为 `cleaned`）
- [ ] 清理操作只影响结果文件，不影响数据库索引

### 5.3 用户隔离
- [ ] 用户 A 无法通过 API 访问用户 B 的任务结果
- [ ] 用户 A 的任务文件存储在 `user_{A_id}` 目录下
- [ ] 下载链接携带 Token 校验，防止未授权访问
- [ ] 管理员可以访问所有用户的任务
- [ ] 任务列表只返回当前用户的任务
