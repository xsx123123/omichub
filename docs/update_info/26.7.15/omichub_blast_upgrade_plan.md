# OmicHub BLAST 模块升级计划

> 版本: v1.0  
> 日期: 2026-07-15  
> 负责人: 用户  
> 执行助手: CC (Claude Code)  
> 目标: 将现有 BLAST 基础表单升级为完整的生产级序列检索工具

---

## 一、现状诊断 (Current State)

### 1.1 已有实现

| 组件 | 状态 | 说明 |
|------|------|------|
| 查询表单 | ✅ 基础版 | 左侧卡片式布局，支持序列输入、数据库选择、E-value、最大匹配数、比对算法、Word Size/Gap Open/Gap Extend 等参数 |
| 结果展示 | ⚠️ 缺失 | 右侧大片空白，无结果可视化、无历史任务、无序列实时分析 |
| 后端 API | ⚠️ 待确认 | 表单提交逻辑存在，但异步任务调度、结果解析、状态追踪需完善 |
| 数据库管理 | ❌ 未实现 | 管理员无法通过网页上传 FASTA 并构建 BLAST 索引 |
| 任务中心 | ❌ 未实现 | 无任务历史列表、无进度追踪、无取消功能 |
| 结果导出 | ❌ 未实现 | 不支持 XML/JSON/Text 多格式下载 |

### 1.2 核心痛点

1. **右侧空间浪费**：当前页面右侧约 70% 区域为空白，用户首次进入缺乏引导
2. **无即时反馈**：输入序列后无法实时查看序列统计（长度、GC 含量、类型推断）
3. **无任务上下文**：提交后无法在当前页面追踪任务状态，需跳转至其他模块
4. **无历史连续性**：用户无法快速复用或查看最近的查询记录
5. **管理员运维困难**：新增 BLAST 数据库需手动 SSH 执行 `makeblastdb`，无审计日志

---

## 二、升级目标 (Target State)

### 2.1 用户体验目标

- **输入即分析**：输入 FASTA 序列后 200ms 内展示序列统计与算法推荐
- **右侧信息面板**：常驻显示序列分析、最近任务、参数说明三层信息
- **任务全生命周期**：提交 → 排队 → 运行 → 完成 → 结果查看，全程可追踪
- **一键复用**：历史任务支持"重新运行"，自动填充上次参数
- **多格式导出**：支持 XML (outfmt 5)、JSON (结构化)、Text (outfmt 0) 三种格式

### 2.2 系统架构目标

- **异步任务调度**：Celery + Redis 处理 BLAST 查询与数据库构建
- **Docker 沙盒隔离**：所有 BLAST 计算在 `ncbi/blast` 容器内执行
- **数据库元数据管理**：PostgreSQL 记录所有数据库、任务、结果元信息
- **管理员零运维**：网页端完成 FASTA 上传 → 自动建索引 → 状态监控
- **高并发支持**：查询任务与建库任务分队列，避免资源争抢

---

## 三、升级路线图 (Roadmap)

```
Phase 1 (第 1-2 天): 前端体验升级 — 右侧信息面板 + 序列实时分析
Phase 2 (第 3-4 天): 后端任务系统 — Celery 异步调度 + 任务状态追踪
Phase 3 (第 5-6 天): 结果可视化 — 比对表格 + 自定义可视化组件 + 多格式导出
Phase 4 (第 7-8 天): 管理员数据库管理 — 上传 FASTA + 自动 makeblastdb + 版本控制
Phase 5 (第 9-10 天): 集成测试 + 性能优化 + 文档收尾
```

### 3.1 执行进度（2026-07-15）

已落地：

- 用户端双栏检索页、序列实时统计、算法推荐、参数说明和最近 5 条任务。
- BLAST 任务中心：分页、状态筛选、任务 ID/查询名称搜索、结果查看和参数复用。
- 结果表格排序、命中详情展开，以及 XML、JSON、Text 三格式下载。
- PostgreSQL 元数据模型与 Alembic 迁移、Celery 查询/建库专用队列、状态轮询和任务取消。
- 管理员 FASTA 上传、上传进度、构建状态/日志、重新构建、软删除和受约束的硬删除。
- 任务所有权隔离、管理员 RBAC、FASTA 大小/格式校验、查询长度与参数边界校验。
- 建库使用临时索引前缀并在校验成功后原子替换，避免重建期间暴露半成品索引。
- 19 个 BLAST 核心单元测试；前端类型检查和生产构建已通过。

架构决策：

- 生产默认在专用 OmicHub Worker 容器内直接运行 `ncbi-blast+`，避免向 Worker 挂载宿主机 Docker Socket。配置仍保留 `execution.use_docker`，需要二次容器隔离的部署可显式开启。
- PostgreSQL 为运行时权威，`tool_configs/blast/blast_db.yaml` 作为可审计、可迁移的声明式副本。

仍需在部署环境完成：

- Redis/Celery/PostgreSQL + 真实 BLAST 数据库端到端查询与取消验证。
- 50 并发压力测试、1000 hits 页面性能测试和多浏览器/多分辨率人工验收。
- SSE/WebSocket 实时推送、Redis 查询结果缓存、大文件分片上传和数据库版本回滚属于后续 P2 优化。

---

## 四、Phase 1: 前端体验升级 (右侧信息面板)

### 4.1 任务清单

| # | 任务 | 优先级 | 预估工时 | 交付物 |
|---|------|--------|----------|--------|
| 1.1 | 创建 `BlastRightPanel` 组件 | P0 | 2h | `src/pages/Blast/BlastRightPanel.tsx` |
| 1.2 | 序列实时分析模块 | P0 | 3h | 序列长度、GC 含量、类型推断、算法推荐 |
| 1.3 | 最近任务列表模块 | P1 | 2h | 展示最近 5 条任务，支持点击跳转 |
| 1.4 | 参数说明常驻模块 | P1 | 1h | E-value、Word Size 等参数解释 |
| 1.5 | 主页面布局调整 | P0 | 1h | 左侧 Col 9 → 右侧 Col 15 分栏 |
| 1.6 | 响应式适配 | P2 | 2h | 移动端折叠右侧面板 |

### 4.2 技术实现细节

#### 4.2.1 序列实时分析算法

```typescript
// utils/sequenceAnalysis.ts

export interface SequenceStats {
  length: number;
  gcContent: number;
  type: 'nucl' | 'prot' | 'unknown';
  recommendedProgram: string;
  header?: string;
  atContent: number;
  nContent: number;
}

/**
 * 检测序列类型
 * 规则：
 * 1. 长度 < 20 且无法判断 → unknown
 * 2. 仅含 ATCGU + 简并碱基 → nucl
 * 3. 仅含标准氨基酸 → prot
 * 4. 混合或含非法字符 → unknown
 */
export function detectSequenceType(seq: string): 'nucl' | 'prot' | 'unknown' {
  const clean = seq.replace(/\s/g, '').toUpperCase();
  if (clean.length < 20) return 'unknown';

  const nuclPattern = /^[ATCGUNRYMKSWHBVD]+$/;
  const protPattern = /^[ACDEFGHIKLMNPQRSTVWY]+$/;

  if (nuclPattern.test(clean)) return 'nucl';
  if (protPattern.test(clean)) return 'prot';
  return 'unknown';
}

/**
 * 计算 GC 含量
 */
export function calculateGCContent(seq: string): number {
  const clean = seq.replace(/\s/g, '').toUpperCase();
  const valid = clean.replace(/[^ATCGU]/g, '');
  if (valid.length === 0) return 0;
  const gc = (valid.match(/[GC]/g) || []).length;
  return (gc / valid.length) * 100;
}

/**
 * 自动推荐比对算法
 * queryType: 查询序列类型
 * dbType: 数据库类型 (从已选数据库获取)
 */
export function recommendProgram(
  queryType: 'nucl' | 'prot',
  dbType: 'nucl' | 'prot'
): string {
  const map: Record<string, string> = {
    'nucl-nucl': 'blastn',
    'prot-prot': 'blastp',
    'nucl-prot': 'blastx',
    'prot-nucl': 'tblastn',
  };
  return map[`${queryType}-${dbType}`] || 'blastn';
}

/**
 * 提取 FASTA Header
 */
export function extractFastaHeader(seq: string): string | undefined {
  const match = seq.match(/^>(.+)/m);
  return match ? match[1].trim() : undefined;
}
```

#### 4.2.2 右侧面板组件结构

```
BlastRightPanel
├── SequenceAnalysisCard      // 序列实时分析 (顶部)
│   ├── Statistic: 序列长度
│   ├── Statistic: GC 含量
│   ├── Tag: 推断类型
│   └── RecommendationBox: 推荐算法 + 说明
├── RecentTasksCard           // 最近任务 (中部)
│   ├── List: 最近 5 条任务
│   └── Button: 查看全部 → 跳转任务中心
└── ParameterHelpCard         // 参数说明 (底部)
    ├── Descriptions: E-value, Word Size 等
    └── Divider + 算法选择指南
```

#### 4.2.3 页面布局调整

```tsx
// BlastQueryPage.tsx 布局修改
<Row gutter={24}>
  {/* 左侧：查询表单 */}
  <Col xs={24} md={24} lg={9} xl={8}>
    <BlastQueryForm />
  </Col>

  {/* 右侧：信息面板 */}
  <Col xs={24} md={24} lg={15} xl={16}>
    <BlastRightPanel
      sequenceStats={sequenceStats}
      recentTasks={recentTasks}
      loadingTasks={loadingTasks}
    />
  </Col>
</Row>
```

### 4.3 验收标准

- [ ] 输入有效 FASTA 后，右侧 200ms 内显示序列长度、GC 含量、类型标签
- [ ] 选择数据库后，自动推荐算法并高亮显示推荐原因
- [ ] 最近任务列表展示最近 5 条，含状态标签、数据库名、提交时间
- [ ] 点击历史任务可跳转至结果详情页
- [ ] 参数说明卡片常驻，帮助新用户理解各参数含义
- [ ] 页面在 1920x1080、1440x900、1366x768 分辨率下无横向滚动条

---

## 五、Phase 2: 后端任务系统 (Celery 异步调度)

### 5.1 任务清单

| # | 任务 | 优先级 | 预估工时 | 交付物 |
|---|------|--------|----------|--------|
| 2.1 | 数据库表设计 | P0 | 2h | `blast_databases` + `blast_tasks` 表 |
| 2.2 | 数据库模型 (SQLAlchemy) | P0 | 2h | `models/blast.py` |
| 2.3 | API 路由实现 | P0 | 4h | `routes/blast.py` (用户端 + 管理员端) |
| 2.4 | Celery 任务配置 | P0 | 2h | `celery_config.py` + 队列路由 |
| 2.5 | BLAST 查询任务 | P0 | 4h | `tasks/blast_search.py` |
| 2.6 | 任务状态查询 API | P1 | 2h | `GET /api/blast/tasks/{task_id}` |
| 2.7 | 任务取消 API | P1 | 1h | `POST /api/blast/tasks/{task_id}/cancel` |
| 2.8 | 用户任务历史 API | P1 | 2h | `GET /api/blast/tasks` (分页) |
| 2.9 | 结果文件解析 | P1 | 3h | XML 解析 → JSON 结构化 |
| 2.10 | WebSocket / SSE 通知 | P2 | 3h | 任务完成实时推送 |

### 5.2 数据库设计

#### 5.2.1 blast_databases 表

```sql
CREATE TABLE blast_databases (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(128) NOT NULL,        -- 显示名称
    db_key          VARCHAR(64) NOT NULL UNIQUE,  -- 目录标识
    db_type         VARCHAR(16) NOT NULL CHECK (db_type IN ('nucl', 'prot')),
    source_species  VARCHAR(128),
    source_version  VARCHAR(64),
    file_path       VARCHAR(512) NOT NULL,        -- 绝对路径
    file_size_mb    FLOAT,
    sequence_count  INTEGER,
    build_status    VARCHAR(32) DEFAULT 'pending'
                    CHECK (build_status IN ('pending', 'building', 'ready', 'failed', 'deprecated')),
    is_public       BOOLEAN DEFAULT TRUE,
    created_by      INTEGER REFERENCES users(id),
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW(),
    build_log       TEXT
);

CREATE INDEX idx_blast_db_status ON blast_databases(build_status);
CREATE INDEX idx_blast_db_type ON blast_databases(db_type);
```

#### 5.2.2 blast_tasks 表

```sql
CREATE TABLE blast_tasks (
    id              SERIAL PRIMARY KEY,
    task_id         VARCHAR(64) NOT NULL UNIQUE,    -- Celery UUID
    user_id         INTEGER NOT NULL REFERENCES users(id),
    db_id           INTEGER NOT NULL REFERENCES blast_databases(id),

    -- 查询参数
    program         VARCHAR(16) NOT NULL,
    query_title     VARCHAR(256),
    query_sequence  TEXT NOT NULL,
    query_file_path VARCHAR(512),
    evalue          FLOAT DEFAULT 0.00001,
    max_target_seqs INTEGER DEFAULT 10,
    word_size       INTEGER,
    gapopen         INTEGER,
    gapextend       INTEGER,

    -- 任务状态
    status          VARCHAR(32) DEFAULT 'queued'
                    CHECK (status IN ('queued', 'running', 'completed', 'failed', 'cancelled')),
    progress        INTEGER DEFAULT 0,            -- 0-100

    -- 结果信息
    result_format   VARCHAR(16) DEFAULT 'xml',
    result_path     VARCHAR(512),
    result_size_kb  INTEGER,
    hit_count       INTEGER,
    top_hit_identity FLOAT,
    top_hit_evalue   FLOAT,

    -- 时间戳
    submitted_at    TIMESTAMP DEFAULT NOW(),
    started_at      TIMESTAMP,
    completed_at    TIMESTAMP,

    -- 错误信息
    error_message   TEXT
);

CREATE INDEX idx_blast_task_user ON blast_tasks(user_id);
CREATE INDEX idx_blast_task_status ON blast_tasks(status);
CREATE INDEX idx_blast_task_submitted ON blast_tasks(submitted_at DESC);
```

### 5.3 Celery 任务实现

#### 5.3.1 配置

```python
# celery_config.py
from celery import Celery

app = Celery('omichub_blast')
app.conf.update(
    broker_url='redis://redis:6379/1',
    result_backend='redis://redis:6379/2',
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Asia/Shanghai',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,          # 硬超时 1h
    task_soft_time_limit=3000,     # 软超时 50min
    worker_prefetch_multiplier=1,
    task_routes={
        'tasks.blast_search': {'queue': 'blast_search'},
        'tasks.blast_db_build': {'queue': 'blast_db_build'},
    },
)
```

#### 5.3.2 BLAST 查询任务

```python
# tasks/blast_search.py
import subprocess
import os
import xml.etree.ElementTree as ET
from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from datetime import datetime
from app.database import SessionLocal
from app.models import BlastTask, BlastDatabase

@shared_task(bind=True, queue='blast_search', max_retries=2)
def blast_search_task(self, task_id: str):
    db = SessionLocal()
    try:
        task = db.query(BlastTask).filter(BlastTask.task_id == task_id).first()
        if not task:
            raise ValueError(f"Task {task_id} not found")

        task.status = 'running'
        task.started_at = datetime.utcnow()
        db.commit()

        # 构建路径
        result_dir = f"/data/omichub/blast_results/{task.user_id}"
        os.makedirs(result_dir, exist_ok=True)
        xml_path = f"{result_dir}/{task_id}.xml"
        json_path = f"{result_dir}/{task_id}.json"

        blast_db = db.query(BlastDatabase).filter(BlastDatabase.id == task.db_id).first()

        # 构建 Docker 命令
        cmd = [
            'docker', 'run', '--rm',
            '-v', f'/data/omichub/blast_db:/blast_db:ro',
            '-v', f'/data/omichub/blast_uploads:/uploads:ro',
            '-v', f'{result_dir}:/results',
            'ncbi/blast:latest',
            task.program,
            '-query', f'/uploads/{task.user_id}/{task_id}_query.fasta',
            '-db', f'/blast_db/{blast_db.db_key}',
            '-evalue', str(task.evalue),
            '-max_target_seqs', str(task.max_target_seqs),
            '-outfmt', '5',
            '-out', f'/results/{task_id}.xml',
            '-num_threads', '4'
        ]

        if task.word_size:
            cmd.extend(['-word_size', str(task.word_size)])
        if task.gapopen:
            cmd.extend(['-gapopen', str(task.gapopen)])
        if task.gapextend:
            cmd.extend(['-gapextend', str(task.gapextend)])

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=3000)

        if result.returncode != 0:
            raise RuntimeError(f"BLAST failed: {result.stderr}")

        # 解析结果
        stats = parse_blast_xml(xml_path)
        convert_xml_to_json(xml_path, json_path)

        task.status = 'completed'
        task.completed_at = datetime.utcnow()
        task.result_path = xml_path
        task.result_size_kb = os.path.getsize(xml_path) // 1024
        task.hit_count = stats['hit_count']
        task.top_hit_identity = stats.get('top_identity')
        task.top_hit_evalue = stats.get('top_evalue')
        db.commit()

        # 发送通知
        notify_user_task_complete.delay(task.user_id, task_id)

        return {"task_id": task_id, "status": "completed", "hits": stats['hit_count']}

    except SoftTimeLimitExceeded:
        task.status = 'failed'
        task.error_message = 'Task exceeded time limit (50 minutes)'
        db.commit()
        raise
    except Exception as e:
        task.status = 'failed'
        task.error_message = str(e)
        db.commit()
        if self.request.retries < 2:
            raise self.retry(exc=e, countdown=60)
        raise
    finally:
        db.close()


def parse_blast_xml(xml_path: str) -> dict:
    tree = ET.parse(xml_path)
    root = tree.getroot()
    hits = root.findall('.//Hit')
    stats = {'hit_count': len(hits), 'top_identity': None, 'top_evalue': None}

    if hits:
        hsp = hits[0].find('.//Hsp')
        if hsp is not None:
            identity = hsp.find('Hsp_identity')
            align_len = hsp.find('Hsp_align-len')
            if identity is not None and align_len is not None:
                stats['top_identity'] = float(identity.text) / float(align_len.text) * 100
            evalue = hsp.find('Hsp_evalue')
            if evalue is not None:
                stats['top_evalue'] = float(evalue.text)

    return stats
```

### 5.4 API 路由

```python
# routes/blast.py
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Optional, Literal

router = APIRouter(prefix="/api/blast", tags=["BLAST"])

class BlastSubmitRequest(BaseModel):
    db_id: int
    query_sequence: Optional[str] = None
    query_title: Optional[str] = "Untitled Query"
    program: Literal["blastn", "blastp", "blastx", "tblastn", "tblastx"] = "blastn"
    evalue: float = 0.00001
    max_target_seqs: int = Field(10, ge=1, le=100)
    word_size: Optional[int] = None
    gapopen: Optional[int] = None
    gapextend: Optional[int] = None

@router.get("/databases")
async def list_databases(db_type: Optional[str] = None, current_user=Depends(get_current_user)):
    pass

@router.post("/submit")
async def submit_task(request: BlastSubmitRequest, current_user=Depends(get_current_user)):
    pass

@router.get("/tasks/{task_id}")
async def get_task_status(task_id: str, current_user=Depends(get_current_user)):
    pass

@router.get("/results/{task_id}")
async def get_results(task_id: str, format: Literal["json", "xml", "text", "summary"] = "json"):
    pass

@router.post("/tasks/{task_id}/cancel")
async def cancel_task(task_id: str, current_user=Depends(get_current_user)):
    pass

@router.get("/tasks")
async def list_tasks(status: Optional[str] = None, page: int = 1, page_size: int = 20):
    pass

# 管理员端
@router.post("/admin/databases")
async def create_database(name: str, db_key: str, db_type: str, fasta_file: UploadFile = File(...)):
    pass

@router.get("/admin/databases/{db_id}/build-status")
async def get_build_status(db_id: int):
    pass

@router.post("/admin/databases/{db_id}/rebuild")
async def rebuild_database(db_id: int):
    pass

@router.delete("/admin/databases/{db_id}")
async def delete_database(db_id: int, hard_delete: bool = False):
    pass
```

### 5.5 验收标准

- [ ] `POST /api/blast/submit` 返回 task_id，任务状态进入 `queued`
- [ ] Celery Worker 消费任务后，状态变为 `running`，数据库 `started_at` 有值
- [ ] 任务完成后，状态为 `completed`，`result_path` 指向有效 XML 文件
- [ ] 任务失败时，状态为 `failed`，`error_message` 包含具体错误
- [ ] `GET /api/blast/tasks/{task_id}` 返回完整任务信息，包括进度和结果摘要
- [ ] `POST /api/blast/tasks/{task_id}/cancel` 可成功撤销 queued 或 running 任务
- [ ] 并发提交 10 个任务，Celery 队列正常处理，无任务丢失

---

## 六、Phase 3: 结果可视化与导出

### 6.1 任务清单

| # | 任务 | 优先级 | 预估工时 | 交付物 |
|---|------|--------|----------|--------|
| 3.1 | XML 解析为结构化 JSON | P0 | 3h | `utils/blast_xml_parser.py` |
| 3.2 | 比对结果表格组件 | P0 | 3h | `BlastResultTable.tsx` |
| 3.3 | 比对条可视化组件 | P1 | 4h | `BlastAlignmentViewer.tsx` |
| 3.4 | 多格式导出功能 | P1 | 2h | XML/JSON/Text 下载按钮 |
| 3.5 | 结果详情页 | P0 | 3h | `BlastResultPage.tsx` |
| 3.6 | 任务中心页面 | P1 | 3h | `BlastTaskHistoryPage.tsx` |

### 6.2 结果解析数据结构

```typescript
// types/blast.ts

interface BlastHit {
  query_id: string;
  subject_id: string;
  subject_title: string;
  subject_length: number;
  identity: number;          // 百分比
  identity_count: number;    // 匹配碱基数
  align_length: number;
  mismatches: number;
  gaps: number;
  evalue: number;
  bit_score: number;
  query_range: [number, number];
  subject_range: [number, number];
  query_seq: string;
  subject_seq: string;
  midline: string;           // 匹配标记线
}

interface BlastResult {
  task_id: string;
  query_title: string;
  database_name: string;
  program: string;
  query_length: number;
  hit_count: number;
  hits: BlastHit[];
  parameters: {
    evalue: number;
    max_target_seqs: number;
    word_size?: number;
  };
}
```

### 6.3 比对条可视化

```tsx
// 比对条颜色编码
const identityColors = [
  { min: 0, max: 40, color: '#ef4444' },    // 红色: 低相似
  { min: 40, max: 70, color: '#f59e0b' },   // 橙色: 中等
  { min: 70, max: 90, color: '#3b82f6' },   // 蓝色: 较高
  { min: 90, max: 100, color: '#10b981' },  // 绿色: 高相似
];
```

### 6.4 验收标准

- [ ] 结果页加载 < 2s (1000 hits 以内)
- [ ] 表格支持按 E-value、Identity、Bit Score 排序
- [ ] 点击表格行展开比对详情（序列对齐 + 匹配条）
- [ ] 支持 XML、JSON、Text 三种格式下载
- [ ] 任务中心支持分页、按状态筛选、搜索任务 ID
- [ ] 历史任务支持"重新运行"，自动填充参数

---

## 七、Phase 4: 管理员数据库管理

### 7.1 任务清单

| # | 任务 | 优先级 | 预估工时 | 交付物 |
|---|------|--------|----------|--------|
| 4.1 | 数据库管理页面 | P0 | 3h | `BlastDatabaseAdminPage.tsx` |
| 4.2 | FASTA 上传组件 | P0 | 2h | 支持拖拽上传、进度条、格式校验 |
| 4.3 | makeblastdb Celery 任务 | P0 | 3h | `tasks/blast_db_build.py` |
| 4.4 | 构建状态实时推送 | P1 | 2h | SSE / 轮询显示进度 |
| 4.5 | 数据库版本管理 | P2 | 3h | 支持多版本共存与回滚 |
| 4.6 | 数据库删除/重建 | P1 | 2h | 软删除 + 硬删除选项 |

### 7.2 makeblastdb 任务

```python
# tasks/blast_db_build.py
@shared_task(bind=True, queue='blast_db_build', max_retries=1)
def blast_db_build_task(self, db_id: int):
    db = SessionLocal()
    try:
        blast_db = db.query(BlastDatabase).filter(BlastDatabase.id == db_id).first()
        blast_db.build_status = 'building'
        db.commit()

        db_dir = f"/data/omichub/blast_db/{blast_db.db_key}"
        source_fasta = f"{db_dir}/source.fasta"

        cmd = [
            'docker', 'run', '--rm',
            '-v', f'{db_dir}:/work',
            'ncbi/blast:latest',
            'makeblastdb',
            '-in', '/work/source.fasta',
            '-dbtype', blast_db.db_type,
            '-out', f'/work/{blast_db.db_key}',
            '-parse_seqids',
            '-hash_index'
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)

        if result.returncode != 0:
            blast_db.build_status = 'failed'
            blast_db.build_log = result.stderr
            db.commit()
            raise RuntimeError(f"makeblastdb failed: {result.stderr}")

        # 验证索引文件
        expected = [
            f"{db_dir}/{blast_db.db_key}.nhr",
            f"{db_dir}/{blast_db.db_key}.nin",
            f"{db_dir}/{blast_db.db_key}.nsq"
        ] if blast_db.db_type == 'nucl' else [
            f"{db_dir}/{blast_db.db_key}.phr",
            f"{db_dir}/{blast_db.db_key}.pin",
            f"{db_dir}/{blast_db.db_key}.psq"
        ]

        for f in expected:
            if not os.path.exists(f):
                raise FileNotFoundError(f"Missing index file: {f}")

        blast_db.build_status = 'ready'
        blast_db.sequence_count = count_fasta_sequences(source_fasta)
        blast_db.file_size_mb = sum(os.path.getsize(f) for f in expected) / (1024 * 1024)
        blast_db.build_log = result.stdout + "\n" + result.stderr
        db.commit()

        return {"db_id": db_id, "status": "ready"}

    except Exception as e:
        blast_db.build_status = 'failed'
        blast_db.build_log = str(e)
        db.commit()
        raise
    finally:
        db.close()
```

### 7.3 验收标准

- [ ] 管理员可上传 FASTA 文件，系统自动投递 makeblastdb 任务
- [ ] 构建过程中页面显示实时进度（日志流或进度条）
- [ ] 构建完成后数据库自动出现在用户可选列表中
- [ ] 构建失败时保留日志，管理员可查看具体错误
- [ ] 支持重新构建已有数据库（原子替换，不影响正在运行的查询）
- [ ] 支持软删除（标记 deprecated）和硬删除（清理文件）

---

## 八、Phase 5: 集成测试与性能优化

### 8.1 测试清单

| # | 测试项 | 方法 | 通过标准 |
|---|--------|------|----------|
| 8.1 | 单元测试：序列分析算法 | pytest | 100 条测试序列，类型推断准确率 > 98% |
| 8.2 | 单元测试：XML 解析 | pytest | 解析 10 个真实 BLAST XML，无异常 |
| 8.3 | 集成测试：完整查询流程 | pytest + Celery | 提交 → 完成 → 结果查看，端到端 < 5min |
| 8.4 | 压力测试：并发查询 | locust | 50 并发用户，平均响应 < 3s，无任务丢失 |
| 8.5 | 安全测试：权限隔离 | 手动 | 普通用户无法访问 admin 接口，无法查看他人任务 |
| 8.6 | 兼容性测试：多浏览器 | 手动 | Chrome/Firefox/Edge/Safari 最新两版本正常 |

### 8.2 性能优化项

| 优化点 | 方案 | 预期收益 |
|--------|------|----------|
| 查询结果缓存 | Redis 缓存 24h | 重复查询直接返回，减少计算 |
| 大文件分片上传 | 前端分片 + 后端合并 | 支持 > 2GB FASTA 上传 |
| 结果文件压缩 | gzip 存储 XML | 减少 70% 存储空间 |
| 数据库预热 | 启动时加载常用数据库 | 首次查询提速 30% |
| 前端虚拟滚动 | 结果表格 > 1000 行时 | 页面不卡顿 |

---

## 九、部署检查清单

- [ ] 服务器 Docker 已安装，Celery Worker 有权限调用 `docker run`
- [ ] `/data/omichub/blast_db` 目录已创建，权限 755
- [ ] `/data/omichub/blast_uploads` 目录已创建，权限 755
- [ ] `/data/omichub/blast_results` 目录已创建，权限 755
- [ ] `ncbi/blast:latest` 镜像已拉取
- [ ] Redis 服务正常运行，DB 1 和 DB 2 可用
- [ ] PostgreSQL 表已迁移（`blast_databases`、`blast_tasks`）
- [ ] Celery Worker 已启动并监听 `blast_search` 和 `blast_db_build` 队列
- [ ] Nginx 上传大小限制已调整（`client_max_body_size 2G`）
- [ ] 日志收集已配置（Loki / ELK）
- [ ] 监控告警已配置（Prometheus + Grafana / 任务失败通知）

---

## 十、风险与应对

| 风险 | 影响 | 概率 | 应对方案 |
|------|------|------|----------|
| makeblastdb 内存不足 | 建库失败 | 中 | 大基因组分染色体建库；Docker 内存限制 16G+ |
| FASTA 文件过大上传超时 | 用户体验差 | 高 | 前端分片上传；> 2GB 建议服务器直传 |
| BLAST 查询耗时过长 | 用户等待焦虑 | 高 | 软超时 50min；WebSocket 实时推送进度；支持任务后台运行 |
| 并发查询导致服务器过载 | 系统崩溃 | 中 | 队列限流；每个用户最多 3 个并发任务；Worker 资源限制 |
| 数据库索引文件损坏 | 查询失败 | 低 | 重建时原子替换；定期校验索引完整性 |
| 用户误删生产数据库 | 数据丢失 | 低 | 软删除默认；硬删除需二次确认；操作审计日志 |

---

## 十一、交付物汇总

| 阶段 | 前端文件 | 后端文件 | 配置文件 |
|------|----------|----------|----------|
| Phase 1 | `BlastRightPanel.tsx`, `sequenceAnalysis.ts` | — | — |
| Phase 2 | `useBlastTasks.ts` (hook) | `models/blast.py`, `routes/blast.py`, `tasks/blast_search.py`, `celery_config.py` | `docker-compose.yml` (Celery Worker) |
| Phase 3 | `BlastResultPage.tsx`, `BlastResultTable.tsx`, `BlastAlignmentViewer.tsx`, `BlastTaskHistoryPage.tsx` | `utils/blast_xml_parser.py` | — |
| Phase 4 | `BlastDatabaseAdminPage.tsx` | `tasks/blast_db_build.py` | — |
| Phase 5 | — | `tests/` | `nginx.conf`, `prometheus.yml` |

---

## 十二、附录

### 12.1 相关资源

- NCBI BLAST+ 文档: https://www.ncbi.nlm.nih.gov/books/NBK279690/
- BlasterJS (结果可视化参考): http://sing-group.org/blasterjs/
- SequenceServer (UI 参考): https://sequenceserver.com/
- Celery 最佳实践: https://docs.celeryq.dev/

### 12.2 命名规范

- 前端组件: PascalCase (`BlastRightPanel`)
- 前端工具函数: camelCase (`detectSequenceType`)
- 后端模型: PascalCase (`BlastTask`)
- 后端 API: kebab-case (`/api/blast/tasks/{task-id}`)
- 数据库表: snake_case (`blast_tasks`)
- Celery 任务: snake_case (`blast_search_task`)

### 12.3 版本历史

| 版本 | 日期 | 修改内容 | 作者 |
|------|------|----------|------|
| v1.0 | 2026-07-15 | 初始版本 | Kimi |
