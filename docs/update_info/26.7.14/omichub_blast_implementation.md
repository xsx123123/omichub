# OmicHub BLAST 模块完整实现方案

> 版本: v1.0  
> 日期: 2026-07-14  
> 目标: 在 OmicHub 平台中集成自托管 BLAST 工具，支持用户提交查询、Celery 异步执行、结果可视化，以及管理员在线管理 BLAST 数据库索引。

---

## 一、架构总览

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           用户层 (React + Arco Design)                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐ │
│  │ BLAST 查询页  │  │ 任务中心      │  │ 结果详情页    │  │ 数据库管理   │ │
│  │ (序列输入)    │  │ (进度/历史)   │  │ (BlasterJS)  │  │ (管理员)     │ │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬──────┘ │
│         │                 │                 │                 │        │
└─────────┼─────────────────┼─────────────────┼─────────────────┼────────┘
          │ POST /api/blast │  GET /api/tasks │  GET /api/blast │
          │ /submit         │  /{task_id}     │  /results/{id}  │
          ▼                 ▼                 ▼                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     API 网关层 (FastAPI + OAuth2 JWT)                    │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  路由: /api/blast/*                                              │   │
│  │  中间件: 权限校验 (普通用户/管理员) + 请求限流 + 日志追踪            │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
          │ 投递 Celery Task │ 查询任务状态 │ 读取结果文件 │ 调用 makeblastdb
          ▼                 ▼                 ▼                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     任务队列层 (Celery + Redis Broker)                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐ │
│  │ blast_search │  │ blast_db_build│  │ file_cleanup │  │ notify_user │ │
│  │ (查询任务)    │  │ (建索引任务)   │  │ (定时清理)   │  │ (WebSocket) │ │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬──────┘ │
└─────────┼─────────────────┼─────────────────┼─────────────────┼────────┘
          │ 调用 docker exec │ 调用 docker exec│                 │
          ▼                 ▼                 ▼                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     计算层 (Docker Swarm / 独立 Worker)                  │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  Docker 容器: ncbi/blast:latest                                   │   │
│  │  挂载卷: /data/omichub/blast_db:/blast_db:ro                    │   │
│  │  挂载卷: /data/omichub/blast_tmp:/tmp                           │   │
│  │  命令: blastn/blastp/tblastx -db /blast_db/xxx -query ...      │   │
│  │  输出: /tmp/blast_{task_id}.xml (outfmt 5)                      │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
          │ 写入结果文件
          ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     存储层 (NFS / 本地共享目录)                          │
│  /data/omichub/blast_db/          ← BLAST 数据库 (.nhr .nin .nsq)      │
│  /data/omichub/blast_results/     ← 任务结果 (.xml .json .txt)         │
│  /data/omichub/blast_uploads/     ← 用户上传的查询序列 (FASTA)         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 二、数据库设计 (PostgreSQL)

### 2.1 blast_databases 表（BLAST 数据库元数据）

```sql
CREATE TABLE blast_databases (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(128) NOT NULL UNIQUE,        -- 显示名称: "水稻泛基因组 (Rice Pan-Genome)"
    db_key          VARCHAR(64) NOT NULL UNIQUE,         -- 目录名/标识: "rice_pan_genome_v2"
    db_type         VARCHAR(16) NOT NULL CHECK (db_type IN ('nucl', 'prot')), -- nucleotide / protein
    source_species  VARCHAR(128),                         -- 物种信息
    source_version  VARCHAR(64),                          -- 版本号
    file_path       VARCHAR(512) NOT NULL,                -- 绝对路径: /data/omichub/blast_db/rice_pan_genome_v2
    file_size_mb    FLOAT,                                -- 数据库大小
    sequence_count  INTEGER,                              -- 序列数量
    build_status    VARCHAR(32) DEFAULT 'pending' 
                    CHECK (build_status IN ('pending', 'building', 'ready', 'failed', 'deprecated')),
    is_public       BOOLEAN DEFAULT TRUE,                 -- 是否对所有用户可见
    created_by      INTEGER REFERENCES users(id),         -- 创建者 (管理员)
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW(),
    build_log       TEXT                                  -- 建索引时的日志输出
);

-- 索引
CREATE INDEX idx_blast_db_status ON blast_databases(build_status);
CREATE INDEX idx_blast_db_type ON blast_databases(db_type);
```

### 2.2 blast_tasks 表（查询任务记录）

```sql
CREATE TABLE blast_tasks (
    id              SERIAL PRIMARY KEY,
    task_id         VARCHAR(64) NOT NULL UNIQUE,          -- Celery task UUID
    user_id         INTEGER NOT NULL REFERENCES users(id),
    db_id           INTEGER NOT NULL REFERENCES blast_databases(id),

    -- 查询参数
    program         VARCHAR(16) NOT NULL,                   -- blastn / blastp / blastx / tblastn / tblastx
    query_title     VARCHAR(256),                         -- 用户自定义的查询名称
    query_sequence  TEXT NOT NULL,                        -- 查询序列 (FASTA 格式)
    query_file_path VARCHAR(512),                        -- 上传文件路径 (如果用户上传了文件)
    evalue          FLOAT DEFAULT 0.00001,
    max_target_seqs INTEGER DEFAULT 10,
    word_size       INTEGER,                              -- 可选参数
    gapopen         INTEGER,                              -- 可选参数
    gapextend       INTEGER,                              -- 可选参数

    -- 任务状态
    status          VARCHAR(32) DEFAULT 'queued' 
                    CHECK (status IN ('queued', 'running', 'completed', 'failed', 'cancelled')),
    progress        INTEGER DEFAULT 0,                    -- 0-100

    -- 结果信息
    result_format   VARCHAR(16) DEFAULT 'xml',             -- xml / json / text
    result_path     VARCHAR(512),                         -- 结果文件路径
    result_size_kb  INTEGER,
    hit_count       INTEGER,                              -- 命中数
    top_hit_identity FLOAT,                               -- 最高匹配度
    top_hit_evalue   FLOAT,                               -- 最佳 E-value

    -- 时间戳
    submitted_at    TIMESTAMP DEFAULT NOW(),
    started_at      TIMESTAMP,
    completed_at    TIMESTAMP,

    -- 错误信息
    error_message   TEXT
);

-- 索引
CREATE INDEX idx_blast_task_user ON blast_tasks(user_id);
CREATE INDEX idx_blast_task_status ON blast_tasks(status);
CREATE INDEX idx_blast_task_submitted ON blast_tasks(submitted_at DESC);
```

---

## 三、API 设计 (FastAPI)

### 3.1 用户端接口

```python
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Optional, Literal
import uuid
from datetime import datetime

router = APIRouter(prefix="/api/blast", tags=["BLAST"])

# ─────────────────────────────────────────────
# 1. 获取可用数据库列表
# ─────────────────────────────────────────────
@router.get("/databases")
async def list_blast_databases(
    db_type: Optional[Literal["nucl", "prot"]] = None,
    current_user: User = Depends(get_current_user)
):
    """
    返回当前用户可用的 BLAST 数据库列表。
    普通用户只能看到 is_public=True 且 build_status='ready' 的数据库。
    """
    pass

# ─────────────────────────────────────────────
# 2. 提交 BLAST 查询任务
# ─────────────────────────────────────────────
class BlastSubmitRequest(BaseModel):
    db_id: int = Field(..., description="目标数据库 ID")
    query_sequence: Optional[str] = Field(None, description="直接粘贴的 FASTA 序列")
    query_title: Optional[str] = Field("Untitled Query", description="查询名称")
    program: Literal["blastn", "blastp", "blastx", "tblastn", "tblastx"] = "blastn"
    evalue: float = 0.00001
    max_target_seqs: int = Field(10, ge=1, le=100)
    # 高级参数可选
    word_size: Optional[int] = None
    gapopen: Optional[int] = None
    gapextend: Optional[int] = None

@router.post("/submit")
async def submit_blast_task(
    request: BlastSubmitRequest = None,
    query_file: Optional[UploadFile] = File(None),
    background_tasks: BackgroundTasks = None,
    current_user: User = Depends(get_current_user)
):
    """
    提交 BLAST 查询任务。

    流程:
    1. 校验数据库存在且可用
    2. 保存查询序列到 /data/omichub/blast_uploads/{user_id}/{task_id}.fasta
    3. 自动推断 program（如果用户未指定）:
       - query 为 nucleotide + db_type='nucl' → blastn
       - query 为 protein + db_type='prot' → blastp
       - query 为 nucleotide + db_type='prot' → blastx
       - query 为 protein + db_type='nucl' → tblastn
    4. 创建数据库记录 (status='queued')
    5. 投递 Celery 任务: blast_search_task.delay(task_id)
    6. 返回 task_id 和预估排队位置
    """
    pass

# ─────────────────────────────────────────────
# 3. 查询任务状态 / 进度
# ─────────────────────────────────────────────
@router.get("/tasks/{task_id}")
async def get_task_status(
    task_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    返回任务状态、进度百分比、以及 (如果完成) 结果摘要。
    """
    pass

# ─────────────────────────────────────────────
# 4. 获取任务结果
# ─────────────────────────────────────────────
@router.get("/results/{task_id}")
async def get_blast_results(
    task_id: str,
    format: Literal["json", "xml", "text", "summary"] = "json",
    current_user: User = Depends(get_current_user)
):
    """
    返回 BLAST 结果。
    - format='json': 解析后的结构化 JSON，供前端 BlasterJS/自定义组件渲染
    - format='xml': 原始 BLAST XML (outfmt 5)
    - format='text': 原始 BLAST 文本 (outfmt 0)
    - format='summary': 仅返回统计摘要 (hit_count, top_hit 等)
    """
    pass

# ─────────────────────────────────────────────
# 5. 取消任务
# ─────────────────────────────────────────────
@router.post("/tasks/{task_id}/cancel")
async def cancel_blast_task(
    task_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    仅允许取消 queued 或 running 状态的任务。
    调用 celery.control.revoke(task_id, terminate=True)
    """
    pass

# ─────────────────────────────────────────────
# 6. 获取用户历史任务列表
# ─────────────────────────────────────────────
@router.get("/tasks")
async def list_user_tasks(
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(get_current_user)
):
    """
    分页返回当前用户的 BLAST 任务历史。
    """
    pass
```

### 3.2 管理员端接口

```python
# ─────────────────────────────────────────────
# 7. 上传 FASTA 并创建新数据库 (管理员)
# ─────────────────────────────────────────────
@router.post("/admin/databases")
async def create_blast_database(
    name: str = Field(..., description="数据库显示名称"),
    db_key: str = Field(..., regex=r"^[a-z0-9_]+$"),  # 小写+下划线
    db_type: Literal["nucl", "prot"] = "nucl",
    source_species: Optional[str] = None,
    source_version: Optional[str] = None,
    fasta_file: UploadFile = File(...),
    is_public: bool = True,
    current_user: User = Depends(require_admin)
):
    """
    管理员上传 FASTA 文件，后端自动:
    1. 保存到 /data/omichub/blast_db/{db_key}/source.fasta
    2. 创建数据库记录 (build_status='pending')
    3. 投递 Celery 任务: blast_db_build_task.delay(db_id)
    4. 返回 db_id 和预估构建时间
    """
    pass

# ─────────────────────────────────────────────
# 8. 查看数据库构建状态 / 日志
# ─────────────────────────────────────────────
@router.get("/admin/databases/{db_id}/build-status")
async def get_db_build_status(
    db_id: int,
    current_user: User = Depends(require_admin)
):
    """
    返回数据库构建状态、进度、以及 makeblastdb 的实时日志。
    """
    pass

# ─────────────────────────────────────────────
# 9. 重新构建数据库索引
# ─────────────────────────────────────────────
@router.post("/admin/databases/{db_id}/rebuild")
async def rebuild_blast_database(
    db_id: int,
    current_user: User = Depends(require_admin)
):
    """
    重新运行 makeblastdb（用于源 FASTA 更新后）。
    """
    pass

# ─────────────────────────────────────────────
# 10. 删除数据库 (软删除 / 硬删除)
# ─────────────────────────────────────────────
@router.delete("/admin/databases/{db_id}")
async def delete_blast_database(
    db_id: int,
    hard_delete: bool = False,  # 默认软删除 (标记 deprecated)
    current_user: User = Depends(require_admin)
):
    """
    软删除: 标记为 deprecated，不影响已有任务结果。
    硬删除: 删除文件 + 数据库记录（仅当无关联任务时允许）。
    """
    pass

# ─────────────────────────────────────────────
# 11. 所有任务监控面板
# ─────────────────────────────────────────────
@router.get("/admin/tasks")
async def list_all_tasks(
    status: Optional[str] = None,
    user_id: Optional[int] = None,
    page: int = 1,
    page_size: int = 50,
    current_user: User = Depends(require_admin)
):
    """
    管理员查看全平台 BLAST 任务，支持按状态/用户筛选。
    """
    pass
```

---

## 四、Celery 任务设计

### 4.1 任务配置

```python
# celery_config.py
from celery import Celery
from celery.signals import task_prerun, task_postrun, task_failure

app = Celery('omichub_blast')
app.conf.update(
    broker_url='redis://redis:6379/1',
    result_backend='redis://redis:6379/2',
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Asia/Shanghai',
    enable_utc=True,
    task_track_started=True,           # 记录任务开始时间
    task_time_limit=3600,              # 硬超时: 1小时
    task_soft_time_limit=3000,         # 软超时: 50分钟，触发 SoftTimeLimitExceeded
    worker_prefetch_multiplier=1,      # 每个 worker 只预取 1 个任务，避免堵塞
    task_routes={
        'tasks.blast_search': {'queue': 'blast_search'},
        'tasks.blast_db_build': {'queue': 'blast_db_build'},
    },
)
```

### 4.2 BLAST 查询任务

```python
# tasks/blast_search.py
import subprocess
import os
import xml.etree.ElementTree as ET
from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import BlastTask

@shared_task(bind=True, queue='blast_search', max_retries=2)
def blast_search_task(self, task_id: str):
    """
    执行 BLAST 查询任务。

    步骤:
    1. 从数据库读取任务参数
    2. 准备输入文件 (query FASTA)
    3. 构建 blast+ 命令
    4. 在 Docker 容器中执行 (或本地子进程)
    5. 解析结果 XML，提取统计信息
    6. 更新数据库状态
    7. 清理临时文件
    """
    db = SessionLocal()
    try:
        task = db.query(BlastTask).filter(BlastTask.task_id == task_id).first()
        if not task:
            raise ValueError(f"Task {task_id} not found")

        # 更新状态为 running
        task.status = 'running'
        task.started_at = datetime.utcnow()
        db.commit()

        # 构建输出路径
        result_dir = f"/data/omichub/blast_results/{task.user_id}"
        os.makedirs(result_dir, exist_ok=True)
        xml_path = f"{result_dir}/{task_id}.xml"
        json_path = f"{result_dir}/{task_id}.json"

        # 获取数据库路径
        blast_db = db.query(BlastDatabase).filter(BlastDatabase.id == task.db_id).first()
        db_path = blast_db.file_path

        # 构建命令
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
            '-outfmt', '5',  # XML 格式
            '-out', f'/results/{task_id}.xml',
            '-num_threads', '4'
        ]

        # 可选参数
        if task.word_size:
            cmd.extend(['-word_size', str(task.word_size)])
        if task.gapopen:
            cmd.extend(['-gapopen', str(task.gapopen)])
        if task.gapextend:
            cmd.extend(['-gapextend', str(task.gapextend)])

        # 执行
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=3000  # 50分钟
        )

        if result.returncode != 0:
            raise RuntimeError(f"BLAST failed: {result.stderr}")

        # 解析 XML 提取统计信息
        stats = parse_blast_xml(xml_path)

        # 同时生成 JSON 格式供前端使用
        convert_xml_to_json(xml_path, json_path)

        # 更新任务状态
        task.status = 'completed'
        task.completed_at = datetime.utcnow()
        task.result_path = xml_path
        task.result_size_kb = os.path.getsize(xml_path) // 1024
        task.hit_count = stats['hit_count']
        task.top_hit_identity = stats.get('top_identity')
        task.top_hit_evalue = stats.get('top_evalue')
        db.commit()

        # 可选: 发送 WebSocket 通知
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
        # 重试逻辑
        if self.request.retries < 2:
            raise self.retry(exc=e, countdown=60)
        raise
    finally:
        db.close()


def parse_blast_xml(xml_path: str) -> dict:
    """
    解析 BLAST XML，提取关键统计信息。
    """
    tree = ET.parse(xml_path)
    root = tree.getroot()

    hits = root.findall('.//Hit')
    stats = {
        'hit_count': len(hits),
        'top_identity': None,
        'top_evalue': None,
    }

    if hits:
        first_hit = hits[0]
        hsp = first_hit.find('.//Hsp')
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

### 4.3 数据库构建任务

```python
# tasks/blast_db_build.py
import subprocess
import os
from celery import shared_task
from app.database import SessionLocal
from app.models import BlastDatabase

@shared_task(bind=True, queue='blast_db_build', max_retries=1)
def blast_db_build_task(self, db_id: int):
    """
    管理员上传 FASTA 后，自动构建 BLAST 数据库索引。

    命令: makeblastdb -in source.fasta -dbtype nucl -out db_name -parse_seqids
    """
    db = SessionLocal()
    try:
        blast_db = db.query(BlastDatabase).filter(BlastDatabase.id == db_id).first()
        if not blast_db:
            raise ValueError(f"Database {db_id} not found")

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
            '-dbtype', blast_db.db_type,  # 'nucl' or 'prot'
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

        # 验证索引文件是否生成
        expected_files = [
            f"{db_dir}/{blast_db.db_key}.nhr",
            f"{db_dir}/{blast_db.db_key}.nin",
            f"{db_dir}/{blast_db.db_key}.nsq"
        ] if blast_db.db_type == 'nucl' else [
            f"{db_dir}/{blast_db.db_key}.phr",
            f"{db_dir}/{blast_db.db_key}.pin",
            f"{db_dir}/{blast_db.db_key}.psq"
        ]

        for f in expected_files:
            if not os.path.exists(f):
                raise FileNotFoundError(f"Missing index file: {f}")

        # 统计序列数量
        seq_count = count_fasta_sequences(source_fasta)

        blast_db.build_status = 'ready'
        blast_db.sequence_count = seq_count
        blast_db.file_size_mb = sum(os.path.getsize(f) for f in expected_files) / (1024 * 1024)
        blast_db.build_log = result.stdout + "\n" + result.stderr
        db.commit()

        return {"db_id": db_id, "status": "ready", "sequences": seq_count}

    except Exception as e:
        blast_db.build_status = 'failed'
        blast_db.build_log = str(e)
        db.commit()
        raise
    finally:
        db.close()
```

---

## 五、Docker 配置

### 5.1 BLAST Worker 容器

```dockerfile
# docker/blast-worker/Dockerfile
FROM ncbi/blast:latest

# 安装额外工具 (如果需要)
RUN apt-get update && apt-get install -y     python3-pip     && rm -rf /var/lib/apt/lists/*

# 创建工作目录
WORKDIR /blast_work

# 默认命令
CMD ["blastn", "-help"]
```

### 5.2 Docker Compose 片段

```yaml
# docker-compose.yml (节选)
services:
  blast_worker:
    build:
      context: ./docker/blast-worker
      dockerfile: Dockerfile
    image: omichub/blast-worker:latest
    volumes:
      - /data/omichub/blast_db:/blast_db:ro
      - /data/omichub/blast_uploads:/uploads:ro
      - /data/omichub/blast_results:/results
    deploy:
      replicas: 2
      resources:
        limits:
          cpus: '4'
          memory: 8G
        reservations:
          cpus: '2'
          memory: 4G
    networks:
      - omichub_net
    # 注意: 这个容器不常驻，由 Celery 在需要时 docker run --rm 调用
```

### 5.3 Celery Worker 服务

```yaml
  celery_blast_search:
    build: .
    command: celery -A app.celery worker -Q blast_search -n blast_search@%h --concurrency=2
    volumes:
      - /data/omichub:/data/omichub
      - /var/run/docker.sock:/var/run/docker.sock  # 允许 Celery 调用 Docker
    environment:
      - CELERY_BROKER_URL=redis://redis:6379/1
      - CELERY_RESULT_BACKEND=redis://redis:6379/2
    depends_on:
      - redis
      - postgres
    networks:
      - omichub_net

  celery_blast_db_build:
    build: .
    command: celery -A app.celery worker -Q blast_db_build -n blast_db_build@%h --concurrency=1
    volumes:
      - /data/omichub:/data/omichub
      - /var/run/docker.sock:/var/run/docker.sock
    environment:
      - CELERY_BROKER_URL=redis://redis:6379/1
      - CELERY_RESULT_BACKEND=redis://redis:6379/2
    depends_on:
      - redis
      - postgres
    networks:
      - omichub_net
```

> ⚠️ **安全提示**: 挂载 `/var/run/docker.sock` 允许 Celery 调用 Docker，这在 Swarm 模式下需要谨慎。生产环境建议使用 Docker API 或 Kubernetes Job 替代。

---

## 六、前端组件设计 (React + Arco Design)

### 6.1 页面路由

```typescript
// src/router.tsx (节选)
const routes = [
  {
    path: '/tools/blast',
    component: BlastQueryPage,
    title: '序列检索 BLAST',
    icon: <IconDna />
  },
  {
    path: '/tools/blast/tasks',
    component: BlastTaskHistoryPage,
    title: 'BLAST 任务历史',
  },
  {
    path: '/tools/blast/results/:taskId',
    component: BlastResultPage,
    title: 'BLAST 结果详情',
  },
  // 管理员路由
  {
    path: '/admin/blast-databases',
    component: BlastDatabaseAdminPage,
    title: 'BLAST 数据库管理',
    requireAdmin: true,
  },
];
```

### 6.2 BLAST 查询页 (BlastQueryPage.tsx)

```typescript
import React, { useState, useEffect } from 'react';
import {
  Form, Input, Select, Button, Message, Card,
  Radio, InputNumber, Upload, Spin, Grid
} from '@arco-design/web-react';
import { IconUpload, IconPlayArrow, IconHistory } from '@arco-design/web-react/icon';
import { useNavigate } from 'react-router-dom';

const FormItem = Form.Item;
const { TextArea } = Input;
const { Row, Col } = Grid;

interface BlastDatabase {
  id: number;
  name: string;
  db_key: string;
  db_type: 'nucl' | 'prot';
  build_status: string;
}

const BlastQueryPage: React.FC = () => {
  const [form] = Form.useForm();
  const [databases, setDatabases] = useState<BlastDatabase[]>([]);
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const navigate = useNavigate();

  // 加载可用数据库
  useEffect(() => {
    fetch('/api/blast/databases')
      .then(r => r.json())
      .then(data => setDatabases(data.filter((d: BlastDatabase) => d.build_status === 'ready')));
  }, []);

  // 自动推断序列类型
  const detectSequenceType = (seq: string): 'nucl' | 'prot' | 'unknown' => {
    const clean = seq.replace(/\s/g, '').toUpperCase();
    const validNucl = /^[ATCGUatcguNRYMKSWHBVDnrymkswhbvd]+$/;
    const validProt = /^[ACDEFGHIKLMNPQRSTVWYacdefghiklmnpqrstvwy]+$/;

    if (validNucl.test(clean) && clean.length > 10) return 'nucl';
    if (validProt.test(clean) && clean.length > 5) return 'prot';
    return 'unknown';
  };

  // 自动推荐 program
  const autoRecommendProgram = (queryType: string, dbType: string) => {
    if (queryType === 'nucl' && dbType === 'nucl') return 'blastn';
    if (queryType === 'prot' && dbType === 'prot') return 'blastp';
    if (queryType === 'nucl' && dbType === 'prot') return 'blastx';
    if (queryType === 'prot' && dbType === 'nucl') return 'tblastn';
    return 'blastn';
  };

  const handleSequenceChange = (value: string) => {
    const queryType = detectSequenceType(value);
    const dbId = form.getFieldValue('db_id');
    const db = databases.find(d => d.id === dbId);
    if (db && queryType !== 'unknown') {
      const recommended = autoRecommendProgram(queryType, db.db_type);
      form.setFieldsValue({ program: recommended });
    }
  };

  const handleSubmit = async (values: any) => {
    setSubmitting(true);
    try {
      const res = await fetch('/api/blast/submit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(values),
      });
      const data = await res.json();
      if (res.ok) {
        Message.success(`任务已提交，任务 ID: ${data.task_id}`);
        navigate(`/tools/blast/tasks`);
      } else {
        Message.error(data.detail || '提交失败');
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div style={{ padding: 24 }}>
      <Card title="序列检索 BLAST" bordered={false}>
        <Form form={form} onSubmit={handleSubmit} layout="vertical">
          <Row gutter={24}>
            <Col span={12}>
              <FormItem
                label="目标数据库"
                field="db_id"
                rules={[{ required: true, message: '请选择数据库' }]}
              >
                <Select placeholder="选择 BLAST 数据库">
                  {databases.map(db => (
                    <Select.Option key={db.id} value={db.id}>
                      {db.name} ({db.db_type === 'nucl' ? '核酸' : '蛋白'})
                    </Select.Option>
                  ))}
                </Select>
              </FormItem>
            </Col>
            <Col span={12}>
              <FormItem
                label="比对算法 (自动推断可修改)"
                field="program"
                initialValue="blastn"
              >
                <Select>
                  <Select.Option value="blastn">blastn (核酸 vs 核酸)</Select.Option>
                  <Select.Option value="blastp">blastp (蛋白 vs 蛋白)</Select.Option>
                  <Select.Option value="blastx">blastx (核酸 vs 蛋白，翻译查询)</Select.Option>
                  <Select.Option value="tblastn">tblastn (蛋白 vs 核酸，翻译数据库)</Select.Option>
                  <Select.Option value="tblastx">tblastx (核酸 vs 核酸，双向翻译)</Select.Option>
                </Select>
              </FormItem>
            </Col>
          </Row>

          <FormItem
            label="查询序列 (FASTA 格式)"
            field="query_sequence"
            rules={[
              { required: true, message: '请输入查询序列' },
              {
                validator: (value: string) => {
                  if (!value.startsWith('>')) {
                    return 'FASTA 格式应以 > 开头';
                  }
                  return true;
                }
              }
            ]}
          >
            <TextArea
              rows={8}
              placeholder=">{OsNAC14}\nATGGCTGACGCCGACGACGACGACGGCGGCG..."
              onChange={handleSequenceChange}
            />
          </FormItem>

          <FormItem label="或上传 FASTA 文件" field="query_file">
            <Upload
              accept=".fasta,.fa,.txt"
              limit={1}
              autoUpload={false}
              onChange={(fileList) => {
                if (fileList[0]?.originFile) {
                  const reader = new FileReader();
                  reader.onload = (e) => {
                    form.setFieldsValue({ query_sequence: e.target?.result });
                    handleSequenceChange(e.target?.result as string);
                  };
                  reader.readAsText(fileList[0].originFile);
                }
              }}
            >
              <Button icon={<IconUpload />}>上传 FASTA</Button>
            </Upload>
          </FormItem>

          <Row gutter={24}>
            <Col span={8}>
              <FormItem label="E-value 阈值" field="evalue" initialValue={0.00001}>
                <InputNumber step={0.00001} min={0} max={10} style={{ width: '100%' }} />
              </FormItem>
            </Col>
            <Col span={8}>
              <FormItem label="最大匹配数" field="max_target_seqs" initialValue={10}>
                <InputNumber min={1} max={100} style={{ width: '100%' }} />
              </FormItem>
            </Col>
            <Col span={8}>
              <FormItem label="查询名称" field="query_title" initialValue="Untitled Query">
                <Input placeholder="自定义查询名称" />
              </FormItem>
            </Col>
          </Row>

          {/* 高级参数折叠面板 */}
          <Card size="small" title="高级参数" style={{ marginBottom: 16 }}>
            <Row gutter={24}>
              <Col span={8}>
                <FormItem label="Word Size" field="word_size">
                  <InputNumber min={2} style={{ width: '100%' }} />
                </FormItem>
              </Col>
              <Col span={8}>
                <FormItem label="Gap Open" field="gapopen">
                  <InputNumber style={{ width: '100%' }} />
                </FormItem>
              </Col>
              <Col span={8}>
                <FormItem label="Gap Extend" field="gapextend">
                  <InputNumber style={{ width: '100%' }} />
                </FormItem>
              </Col>
            </Row>
          </Card>

          <FormItem>
            <Button type="primary" htmlType="submit" loading={submitting} icon={<IconPlayArrow />}>
              开始检索
            </Button>
            <Button style={{ marginLeft: 12 }} onClick={() => navigate('/tools/blast/tasks')} icon={<IconHistory />}>
              查看历史
            </Button>
          </FormItem>
        </Form>
      </Card>
    </div>
  );
};

export default BlastQueryPage;
```

### 6.3 结果详情页 (BlastResultPage.tsx)

```typescript
import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { Card, Spin, Table, Message, Button, Tag } from '@arco-design/web-react';
import { IconDownload } from '@arco-design/web-react/icon';

// 自定义比对可视化组件 (替代 BlasterJS 或基于它封装)
const BlastAlignmentViewer: React.FC<{ data: any }> = ({ data }) => {
  // 实现比对条可视化、序列高亮、E-value 颜色编码等
  return <div className="blast-alignment-viewer">{/* ... */}</div>;
};

const BlastResultPage: React.FC = () => {
  const { taskId } = useParams<{ taskId: string }>();
  const [loading, setLoading] = useState(true);
  const [resultData, setResultData] = useState<any>(null);

  useEffect(() => {
    fetch(`/api/blast/results/${taskId}?format=json`)
      .then(r => r.json())
      .then(data => {
        setResultData(data);
        setLoading(false);
      })
      .catch(() => {
        Message.error('加载结果失败');
        setLoading(false);
      });
  }, [taskId]);

  const columns = [
    { title: 'Query', dataIndex: 'query_id', width: 120 },
    { title: 'Subject', dataIndex: 'subject_id', width: 200 },
    { title: 'Identity %', dataIndex: 'identity', width: 100, 
      render: (v: number) => <Tag color={v > 90 ? 'green' : v > 70 ? 'blue' : 'orange'}>{v.toFixed(1)}%</Tag> },
    { title: 'E-value', dataIndex: 'evalue', width: 120,
      render: (v: number) => v < 1e-100 ? <Tag color="red">{v.toExponential(2)}</Tag> : v.toExponential(2) },
    { title: 'Bit Score', dataIndex: 'bit_score', width: 100 },
    { title: 'Align Length', dataIndex: 'align_length', width: 100 },
    { title: 'Query Range', dataIndex: 'query_range', width: 140 },
  ];

  if (loading) return <Spin size={40} style={{ display: 'block', margin: '100px auto' }} />;

  return (
    <div style={{ padding: 24 }}>
      <Card
        title={`BLAST 结果: ${resultData?.query_title || taskId}`}
        extra={
          <>
            <Button size="small" style={{ marginRight: 8 }} onClick={() => window.open(`/api/blast/results/${taskId}?format=xml`)}>
              下载 XML
            </Button>
            <Button size="small" onClick={() => window.open(`/api/blast/results/${taskId}?format=text`)}>
              下载 Text
            </Button>
          </>
        }
      >
        <div style={{ marginBottom: 16 }}>
          <Tag color="blue">数据库: {resultData?.database_name}</Tag>
          <Tag color="green">命中数: {resultData?.hit_count}</Tag>
          <Tag color="purple">Program: {resultData?.program}</Tag>
        </div>

        <Table
          columns={columns}
          data={resultData?.hits || []}
          rowKey="subject_id"
          pagination={{ pageSize: 10 }}
          scroll={{ x: 1000 }}
        />

        {/* 比对详情可视化 */}
        <BlastAlignmentViewer data={resultData} />
      </Card>
    </div>
  );
};

export default BlastResultPage;
```

### 6.4 管理员数据库管理页 (BlastDatabaseAdminPage.tsx)

```typescript
import React, { useState, useEffect } from 'react';
import {
  Card, Table, Button, Modal, Form, Input, Select,
  Upload, Message, Progress, Tag, Popconfirm
} from '@arco-design/web-react';
import { IconPlus, IconRefresh, IconDelete } from '@arco-design/web-react/icon';

const BlastDatabaseAdminPage: React.FC = () => {
  const [databases, setDatabases] = useState([]);
  const [visible, setVisible] = useState(false);
  const [form] = Form.useForm();
  const [uploading, setUploading] = useState(false);

  const columns = [
    { title: 'ID', dataIndex: 'id', width: 60 },
    { title: '名称', dataIndex: 'name', width: 200 },
    { title: '标识', dataIndex: 'db_key', width: 150 },
    { title: '类型', dataIndex: 'db_type', width: 80, render: (v: string) => v === 'nucl' ? '核酸' : '蛋白' },
    { title: '状态', dataIndex: 'build_status', width: 100,
      render: (v: string) => {
        const colors: Record<string, string> = {
          pending: 'gray', building: 'blue', ready: 'green',
          failed: 'red', deprecated: 'orange'
        };
        return <Tag color={colors[v] || 'default'}>{v}</Tag>;
      }
    },
    { title: '序列数', dataIndex: 'sequence_count', width: 100 },
    { title: '大小 (MB)', dataIndex: 'file_size_mb', width: 100 },
    { title: '创建时间', dataIndex: 'created_at', width: 180 },
    {
      title: '操作',
      render: (_: any, record: any) => (
        <>
          <Button size="small" icon={<IconRefresh />} onClick={() => handleRebuild(record.id)}>重建</Button>
          <Popconfirm title="确认删除?" onOk={() => handleDelete(record.id)}>
            <Button size="small" status="danger" icon={<IconDelete />} style={{ marginLeft: 8 }}>删除</Button>
          </Popconfirm>
        </>
      )
    }
  ];

  const handleCreate = async (values: any) => {
    setUploading(true);
    const formData = new FormData();
    Object.keys(values).forEach(key => {
      if (key === 'fasta_file') {
        formData.append(key, values[key][0]?.originFile);
      } else {
        formData.append(key, values[key]);
      }
    });

    try {
      const res = await fetch('/api/blast/admin/databases', {
        method: 'POST',
        body: formData,
      });
      const data = await res.json();
      if (res.ok) {
        Message.success(`数据库创建任务已提交，ID: ${data.db_id}`);
        setVisible(false);
        form.resetFields();
        // 轮询构建状态
        pollBuildStatus(data.db_id);
      } else {
        Message.error(data.detail || '创建失败');
      }
    } finally {
      setUploading(false);
    }
  };

  const pollBuildStatus = (dbId: number) => {
    const interval = setInterval(async () => {
      const res = await fetch(`/api/blast/admin/databases/${dbId}/build-status`);
      const data = await res.json();
      if (data.build_status === 'ready' || data.build_status === 'failed') {
        clearInterval(interval);
        Message[data.build_status === 'ready' ? 'success' : 'error'](
          data.build_status === 'ready' ? '数据库构建完成!' : `构建失败: ${data.build_log}`
        );
        // 刷新列表
        fetchDatabases();
      }
    }, 3000);
  };

  return (
    <div style={{ padding: 24 }}>
      <Card
        title="BLAST 数据库管理"
        extra={
          <Button type="primary" icon={<IconPlus />} onClick={() => setVisible(true)}>
            新建数据库
          </Button>
        }
      >
        <Table columns={columns} data={databases} rowKey="id" />
      </Card>

      <Modal
        title="新建 BLAST 数据库"
        visible={visible}
        onOk={() => form.submit()}
        onCancel={() => setVisible(false)}
        confirmLoading={uploading}
      >
        <Form form={form} onSubmit={handleCreate} layout="vertical">
          <Form.Item label="数据库名称" field="name" rules={[{ required: true }]}>
            <Input placeholder="例如: 水稻泛基因组 v2" />
          </Form.Item>
          <Form.Item label="数据库标识 (db_key)" field="db_key" rules={[{ required: true }]}>
            <Input placeholder="小写字母+下划线，例如: rice_pan_genome_v2" />
          </Form.Item>
          <Form.Item label="序列类型" field="db_type" initialValue="nucl">
            <Select>
              <Select.Option value="nucl">核酸 (Nucleotide)</Select.Option>
              <Select.Option value="prot">蛋白 (Protein)</Select.Option>
            </Select>
          </Form.Item>
          <Form.Item label="物种" field="source_species">
            <Input placeholder="例如: Oryza sativa" />
          </Form.Item>
          <Form.Item label="版本" field="source_version">
            <Input placeholder="例如: v2.1" />
          </Form.Item>
          <Form.Item label="FASTA 文件" field="fasta_file" rules={[{ required: true }]}>
            <Upload accept=".fasta,.fa,.fna" limit={1}>
              <Button>选择文件</Button>
            </Upload>
          </Form.Item>
          <Form.Item label="公开可见" field="is_public" initialValue={true}>
            <Select>
              <Select.Option value={true}>是 (所有用户可见)</Select.Option>
              <Select.Option value={false}>否 (仅管理员可见)</Select.Option>
            </Select>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default BlastDatabaseAdminPage;
```

---

## 七、评估：管理员网页创建序列 Index 更新模块是否合适？

### 结论: ✅ 非常合适，但需要注意几个关键点

#### 7.1 为什么合适

| 维度 | 评估 |
|------|------|
| **用户体验** | 管理员无需 SSH 到服务器执行 `makeblastdb`，在网页上点几下就能完成，极大降低运维门槛 |
| **安全性** | 通过 Web 界面可以严格控制输入校验（db_key 格式、文件类型、大小限制），比命令行更安全 |
| **可追溯性** | 所有建库操作都记录在 `blast_databases` 表中，谁建的、什么时候建的、成功还是失败，一目了然 |
| **异步处理** | 建库可能耗时几分钟到几小时（大基因组），用 Celery 异步执行，管理员可以关闭页面等通知 |
| **与现有架构一致** | 复用已有的用户权限体系、文件上传组件、任务队列，不引入新的技术栈 |

#### 7.2 需要注意的风险和优化点

| 风险 | 解决方案 |
|------|----------|
| **FASTA 文件过大导致上传超时** | 前端限制 2GB，大文件建议用 `rsync` / `scp` 传到服务器指定目录后，管理员在网页上"选择已有文件" |
| **makeblastdb 内存不足** | Docker 容器设置 `memory: 16G` 或更高；对超大基因组建议分染色体建库 |
| **同名 db_key 覆盖** | 强制 db_key 唯一，重建时先备份旧索引，构建成功后再原子替换 |
| **构建失败后的脏数据** | 构建失败时保留 `source.fasta` 和 `build_log`，但删除半成品索引文件，方便排查 |
| **并发构建导致资源争抢** | `blast_db_build` 队列的并发数设为 1 (`--concurrency=1`)，保证一次只构建一个库 |

#### 7.3 建议的增强功能

1. **文件预校验**: 上传后先检查 FASTA 格式是否合法（序列数量、是否有非法字符）
2. **构建进度实时推送**: 通过 WebSocket 或 Server-Sent Events 把 `makeblastdb` 的 stdout 实时推送到前端
3. **数据库版本管理**: 支持同一 db_key 的多版本共存（`rice_pan_genome_v2_20260714`），方便回滚
4. **自动定时重建**: 如果源 FASTA 是从外部同步的（如 NCBI 自动下载），可以设置 Cron 任务定期重建

---

## 八、部署检查清单

- [ ] 服务器已安装 Docker，且 Celery Worker 有权限调用 `docker run`
- [ ] `/data/omichub/blast_db` 目录已创建，权限正确
- [ ] `ncbi/blast:latest` 镜像已拉取
- [ ] Redis 和 PostgreSQL 服务正常运行
- [ ] Celery Worker 已启动并监听 `blast_search` 和 `blast_db_build` 队列
- [ ] Nginx 已配置 `/api/blast/*` 路由到 FastAPI 服务
- [ ] 文件上传大小限制已调整（Nginx + FastAPI 都要配）
- [ ] 日志收集已配置（`blast_tasks` 的 `build_log` 和 `error_message` 字段）

---

## 九、附录: 相关资源

| 资源 | 链接 |
|------|------|
| NCBI BLAST+ 文档 | https://www.ncbi.nlm.nih.gov/books/NBK279690/ |
| BlasterJS 官网 | http://sing-group.org/blasterjs/ |
| SequenceServer (参考 UI) | https://sequenceserver.com/ |
| Celery 最佳实践 | https://docs.celeryq.dev/en/stable/userguide/tasks.html |
| Arco Design React | https://arco.design/react/docs/start |
