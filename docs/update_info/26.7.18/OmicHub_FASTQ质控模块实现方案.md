# OmicHub FASTQ 质控模块实现方案（fastp + MultiQC + Celery）

> 版本：v1.0｜面向 OmicHub「FASTQ 极速质控」工具｜配套已有前端页面（参数面板 + 质控前后对比图）

---

## 0. TL;DR

- 前端提交质控任务 → FastAPI 落库 → Celery 投递 → Worker 镜像内依次执行 `fastp`（逐样本）与 `multiqc`（合并报告）→ 结果回写 → 前端轮询/WebSocket 获取状态与图表数据。
- **图表统一不靠嵌入 MultiQC 页面，而靠数据回流**：后端用 MultiQC v1.29+ 的 parquet 输出 / Python API 提取结构化数据，转 JSON 喂给前端 Plotly 按平台风格重绘；MultiQC 原生 HTML 报告仅作为「完整报告」iframe 预览 + 下载。
- 单样本详情页直接解析 `fastp.json`（数据最全，含质控前后全量曲线）；MultiQC 只负责跨样本汇总层。
- Worker 镜像 pin 版本：`fastp>=0.24`、`multiqc>=1.29`（低于 1.29 没有 parquet 输出）。

---

## 1. 需求拆解与技术判定

| 需求 | 判定 | 说明 |
| --- | --- | --- |
| ① 网页端添加任务，Celery 投递队列 | ✅ 直接可行 | 沿用 OmicHub 现有 Celery 投递体系 |
| ② Worker 镜像内 fastp 质控 + MultiQC 合并报告，前端展示与下载 | ✅ 直接可行 | 标准模式，注意镜像内要同时装 fastp 二进制与 Python 环境（MultiQC 是 Python 包） |
| ③ 前端用「MultiQC 的 API」读 `multiqc.parquet` 动态绘图 | ⚠️ 方向对，链路要修正 | `multiqc` 的 API 是 **Python 库**，浏览器无法直接调用。正确链路：**后端 Python 读 parquet / 调 multiqc API → REST JSON → 前端 Plotly 重绘**。这样风格反而能完全统一 |

### 关键事实核验

1. **fastp 输出**：默认产出 `fastp.html` 与 `fastp.json`，JSON 内含 HTML 报告中的全部图表数据（质控前后 per-base 质量曲线、碱基含量、GC、Q20/Q30、duplication、adapter content、KMER 表），单样本页所需数据一个 JSON 全部覆盖。不指定输出文件名时只做 QC 不写 clean 数据。
2. **MultiQC parquet（v1.29+）**：运行后在输出目录生成 `multiqc_data/multiqc.parquet`（文件名必须以 `*multiqc.parquet` 结尾才能被再次识别）。该 parquet 可用于：重新生成报告（`multiqc multiqc_data/multiqc.parquet`）、跨批次合并（把旧 parquet 和新数据一起喂给 multiqc）、以及程序化读取。
3. **MultiQC Python API**（v1.29+，官方文档示例）：

```python
import multiqc

multiqc.parse_logs('multiqc_data/multiqc.parquet')   # 从 parquet 载入一次历史运行
modules = multiqc.list_modules()                     # 载入的模块，如 ['fastp']
plots   = multiqc.list_plots()                       # 本次运行包含的全部 plot 对象
data    = multiqc.get_module_data(module='fastp')    # 按模块取结构化数据
```

4. **两条数据路径的取舍**：
   - 路径 A（保底）：`polars/pandas` 直读 parquet 长表 → 按 plot/样本过滤 → 组装 JSON。不依赖 multiqc 运行时，最稳。
   - 路径 B（进阶）：官方 Python API 拿 plot 对象，序列化后给前端。能保留 MultiQC 的 plot 定义（标题、坐标轴、分面），但要跟版本走。
   - 文档两者都给，实现时先 A 后 B。

---

## 2. 总体架构

```
┌────────────────────────────────────────────────────────────────────┐
│  前端 React (Arco Design + Plotly.js)                               │
│  ┌──────────────┐  ┌──────────────────┐  ┌───────────────────────┐ │
│  │ 任务创建面板  │  │ 单样本详情页      │  │ 批次合并报告页        │ │
│  │ (截图已有)    │  │ fastp.json → 图表 │  │ parquet→JSON→Plotly  │ │
│  └──────┬───────┘  └────────┬─────────┘  └──────────┬────────────┘ │
└─────────┼───────────────────┼───────────────────────┼──────────────┘
          │ REST              │ REST (chart-data)     │ REST (chart-data)
┌─────────▼───────────────────▼───────────────────────▼──────────────┐
│  FastAPI 服务                                                       │
│  POST /api/qc/tasks          创建任务(落库+celery投递)              │
│  GET  /api/qc/tasks/{id}     任务状态/进度                          │
│  GET  /api/qc/tasks/{id}/samples/{sample}/chart  单样本图表数据     │
│  GET  /api/qc/tasks/{id}/multiqc/chart           合并报告图表数据   │
│  GET  /api/qc/tasks/{id}/report.html             iframe 预览(静态)  │
│  GET  /api/qc/tasks/{id}/download                打包下载           │
└─────────┬──────────────────────────────────────────────────────────┘
          │ Celery (broker: Redis/RabbitMQ, queue: qc)
┌─────────▼──────────────────────────────────────────────────────────┐
│  Celery Worker（Docker Swarm 服务，镜像 omichub/qc-worker:x.y）     │
│  task: run_qc_pipeline(task_id)                                     │
│    1. 逐样本调用 fastp（可子进程并发）                               │
│    2. 汇总 fastp.json 目录 → 调用 multiqc                           │
│    3. 校验产物（json/parquet/html 存在性）                           │
│    4. 回写任务状态 + 关键指标摘要入库                                │
└─────────┬──────────────────────────────────────────────────────────┘
          │ 共享卷 (NFS 挂载 /data/omichub)
┌─────────▼──────────────────────────────────────────────────────────┐
│  /data/omichub/qc/tasks/{task_id}/                                  │
│    input/  output/  reports/  multiqc/  logs/  task.yaml            │
└─────────────────────────────────────────────────────────────────────┘
```

**组件清单**

| 组件 | 技术 | 备注 |
| --- | --- | --- |
| 前端 | React + Arco Design + Plotly.js | 沿用现有栈，图表全部自绘统一风格 |
| API 层 | FastAPI + SQLAlchemy(MySQL) | 任务表、样本表、指标摘要表 |
| 队列 | Celery + Redis | queue 独立命名 `qc`，与平台其他任务隔离 |
| Worker | Docker Swarm service，镜像内 fastp + multiqc + python | 资源限制：CPU 8 / MEM 16G 起步 |
| 存储 | NFS `/data/omichub` | 与平台现有共享目录一致 |

---

## 3. 任务流与状态机

### 3.1 任务粒度

- 一个 QC 任务 = 1~N 个样本（每个样本 SE 或 PE）。
- Worker 内对每个样本跑独立 fastp；全部成功后跑 1 次 multiqc 合并。
- 任一 fastp 失败 → 该样本标记 FAILED，任务整体状态 = PARTIAL（其余样本照常出报告，multiqc 只聚合成功样本）。不允许一个坏样本拖死整批。

### 3.2 状态机

```
PENDING → QUEUED → RUNNING_FASTP → RUNNING_MULTIQC → SUCCESS
                                               ↘→ PARTIAL（部分样本失败）
                                               ↘→ FAILED（fastp 全灭 / multiqc 失败 / 超时）
任意状态 → CANCELED（用户取消，revoke terminate=True）
```

- 进度上报：样本粒度。`progress = done_samples / total_samples`，前端进度条 + 当前正在跑的样本名。
- 状态存 MySQL， Celery 只承担执行，不承担状态存储。

---

## 4. 存储目录规范

```
/data/omichub/qc/tasks/{task_id}/
├── task.yaml                     # 任务快照：参数、样本清单、版本信息（幂等溯源）
├── input/                        # 用户上传的原始 fastq（或软链到上传区，避免拷贝）
├── output/                       # clean fastq
│   ├── {sample}.clean_R1.fastq.gz
│   └── {sample}.clean_R2.fastq.gz
├── reports/                      # fastp 单样本报告
│   ├── {sample}.fastp.json       # ← 单样本详情页数据源
│   └── {sample}.fastp.html
├── multiqc/
│   ├── multiqc_report.html       # ← iframe 预览 + 下载
│   └── multiqc_data/
│       ├── multiqc.parquet       # ← 合并图表页数据源（v1.29+）
│       ├── multiqc_data.json
│       └── multiqc_general_stats.txt
├── logs/
│   ├── {sample}.fastp.log
│   └── multiqc.log
└── result.zip                    # 任务完成后惰性打包（首次点击下载时生成并缓存）
```

要点：

- `task.yaml` 在投递前由 API 层写入，Worker 只读不写——任务可重放、可审计，符合平台 yaml 配置驱动的习惯。
- parquet 文件名保持 `multiqc.parquet`，不要改名（MultiQC 重新识别有文件名后缀要求）。

---

## 5. Worker 镜像

```dockerfile
# omichub/qc-worker
FROM python:3.12-slim

# fastp：官方静态二进制，免编译
ARG FASTP_VERSION=0.24.1
ADD https://github.com/OpenGene/fastp/releases/download/v${FASTP_VERSION}/fastp /usr/local/bin/fastp
RUN chmod +x /usr/local/bin/fastp

# MultiQC 必须 >=1.29 才有 parquet 输出；pyarrow/polars 用于读 parquet
RUN pip install --no-cache-dir \
      "multiqc>=1.29" \
      polars pyarrow \
      celery[redis] requests

# 时区 & 编码
ENV TZ=Asia/Shanghai PYTHONUNBUFFERED=1

WORKDIR /app
COPY qc_tasks.py /app/
ENTRYPOINT ["celery", "-A", "qc_tasks", "worker", "-Q", "qc", "--concurrency=2"]
```

- `--concurrency=2`：fastp 自身多线程（`-w 8`），单 worker 跑 2 个任务已能压满 16 核机器；宁可加 worker 副本数，别把 concurrency 开高导致 IO 互踩。
- Swarm 部署时挂载 `/data/omichub` 为共享卷（NFS driver），资源 `limits: cpus=8 memory=16G`。

---

## 6. Celery 任务实现（核心骨架）

```python
# qc_tasks.py
import json, subprocess, shutil, zipfile, yaml
from pathlib import Path
from celery import Celery

app = Celery("qc", broker="redis://redis:6379/0", backend="redis://redis:6379/1")
DATA_ROOT = Path("/data/omichub/qc/tasks")

FASTP_TIMEOUT = 60 * 60 * 4      # 单样本 4h 上限
MULTIQC_TIMEOUT = 60 * 30

def run(cmd: list[str], log_path: Path, timeout: int):
    """统一子进程执行：stdout/stderr 落日志，超时报错"""
    with open(log_path, "w") as lf:
        p = subprocess.run(cmd, stdout=lf, stderr=subprocess.STDOUT, timeout=timeout)
    if p.returncode != 0:
        raise RuntimeError(f"cmd failed ({p.returncode}): {' '.join(cmd)}, see {log_path}")

def fastp_cmd(sample: dict, tdir: Path, params: dict) -> list[str]:
    """按 SE/PE 自动组装 fastp 命令；params 与前端参数面板一一对应"""
    s, out, rep = sample["name"], tdir / "output", tdir / "reports"
    cmd = ["fastp", "-w", str(params.get("threads", 8)),
           "-j", str(rep / f"{s}.fastp.json"),
           "-h", str(rep / f"{s}.fastp.html")]
    if sample.get("r2"):  # PE
        cmd += ["-i", sample["r1"], "-I", sample["r2"],
                "-o", str(out / f"{s}.clean_R1.fastq.gz"),
                "-O", str(out / f"{s}.clean_R2.fastq.gz"),
                "--detect_adapter_for_pe"]
    else:                 # SE
        cmd += ["-i", sample["r1"], "-o", str(out / f"{s}.clean_R1.fastq.gz")]
    if q := params.get("qualified_quality_phred"):      # 前端滑块：Phred 阈值
        cmd += ["-q", str(q)]
    if params.get("trim_to_len"):                        # 前端滑块：截断长度
        cmd += ["--max_len1", str(params["trim_to_len"])]
    if not params.get("adapter_trim", True):             # 前端开关：去接头
        cmd += ["--disable_adapter_trimming"]
    return cmd

@app.task(bind=True, name="qc.run_pipeline")
def run_qc_pipeline(self, task_id: str):
    tdir = DATA_ROOT / task_id
    cfg = yaml.safe_load((tdir / "task.yaml").read_text())
    for d in ("output", "reports", "multiqc", "logs"):
        (tdir / d).mkdir(parents=True, exist_ok=True)

    samples, failed = cfg["samples"], []
    set_status(task_id, "RUNNING_FASTP")
    for i, sample in enumerate(samples):
        if (tdir / "reports" / f'{sample["name"]}.fastp.json').exists():
            continue                                   # 幂等：已完成的样本跳过（重试不重复跑）
        try:
            run(fastp_cmd(sample, tdir, cfg["params"]),
                tdir / "logs" / f'{sample["name"]}.fastp.log', FASTP_TIMEOUT)
        except Exception as e:
            failed.append({"sample": sample["name"], "error": str(e)})
        update_progress(task_id, done=i + 1, total=len(samples), current=sample["name"])

    ok_jsons = [p for p in (tdir / "reports").glob("*.fastp.json")]
    if not ok_jsons:
        set_status(task_id, "FAILED", error="all samples failed")
        return

    set_status(task_id, "RUNNING_MULTIQC")
    run(["multiqc", str(tdir / "reports"), "-o", str(tdir / "multiqc"),
         "-n", "multiqc_report.html", "-f", "--no-ansi"],
        tdir / "logs" / "multiqc.log", MULTIQC_TIMEOUT)

    # 产物校验：少了任何一个都视为失败，便于上游重试
    expect = [tdir / "multiqc" / "multiqc_report.html",
              tdir / "multiqc" / "multiqc_data" / "multiqc.parquet"]
    missing = [str(p) for p in expect if not p.exists()]
    if missing:
        set_status(task_id, "FAILED", error=f"missing artifacts: {missing}")
        return

    summary = build_summary(ok_jsons)                  # 提取 Q30/GC/保留率入库，供列表页展示
    set_status(task_id, "PARTIAL" if failed else "SUCCESS",
               failed_samples=failed, summary=summary)
```

要点：

- **幂等**：样本级跳过已完成产物，Worker 重试/容器重启后不重复计算。
- **摘要入库**：`build_summary` 从各 `fastp.json` 抽 `filtering_result.passed_filter_reads`、`q30_rate`、`gc_content` 等写入 MySQL，任务列表页不用翻文件。
- `set_status/update_progress` 为平台 DB 写函数，按现有封装替换。

---

## 7. API 设计

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/qc/tasks` | 创建任务：写 task.yaml + 落库 + `run_qc_pipeline.delay()` |
| GET | `/api/qc/tasks` | 任务列表（读 MySQL 摘要，不碰文件系统） |
| GET | `/api/qc/tasks/{task_id}` | 状态、进度、失败样本、参数快照 |
| GET | `/api/qc/tasks/{task_id}/samples/{sample}/chart` | 单样本图表 JSON（解析 fastp.json，见 §8.2） |
| GET | `/api/qc/tasks/{task_id}/multiqc/plots` | 合并报告图表清单 + 数据（读 parquet，见 §8.3） |
| GET | `/api/qc/tasks/{task_id}/report.html` | MultiQC HTML，iframe 预览 |
| GET | `/api/qc/tasks/{task_id}/download` | result.zip（首次请求惰性打包缓存） |
| DELETE | `/api/qc/tasks/{task_id}` | 取消（`celery.control.revoke(terminate=True)`）+ 可选清理目录 |

创建任务请求体（与前端参数面板对应）：

```json
{
  "name": "水稻RIL群体_Q1批次",
  "params": {"qualified_quality_phred": 19, "trim_to_len": 260, "adapter_trim": true, "threads": 8},
  "samples": [
    {"name": "RIL_001", "r1": "/data/omichub/uploads/xxx/RIL_001_R1.fastq.gz",
                        "r2": "/data/omichub/uploads/xxx/RIL_001_R2.fastq.gz"}
  ]
}
```

---

## 8. 前端图表统一方案（核心，对应需求 ③）

展示分三层，职责清晰，互不绑架：

### 8.1 三层展示策略

| 层级 | 页面 | 数据源 | 形态 |
| --- | --- | --- | --- |
| L1 平台风格图表 | 单样本详情页（即截图页） | `fastp.json` | 后端转 JSON，Plotly.js 自绘，100% 平台风格 |
| L2 平台风格图表 | 批次合并对比页 | `multiqc.parquet` | 后端转 JSON，Plotly.js 自绘 |
| L3 完整原生报告 | 「完整报告」Tab / 下载 | `multiqc_report.html` + `fastp.html` | iframe 预览 + 下载，一字不改 |

L3 存在的意义：MultiQC 交互报告（样本隐藏/高亮/重命名工具箱）用户有时就是要原版；而 L1/L2 保证平台日常体验统一。

### 8.2 L1：单样本页（fastp.json → 前端）

`fastp.json` 结构直接可用，后端只做裁剪转发，不做聚合：

```python
# FastAPI 侧（精简）
import json
from pathlib import Path

def sample_chart(task_id: str, sample: str):
    j = json.loads(Path(f"{DATA_ROOT}/{task_id}/reports/{sample}.fastp.json").read_text())
    return {
        "summary": {                       # 顶部三张指标卡：保留率 / 保留Reads / GC
            "survival_rate": j["filtering_result"]["passed_filter_reads"]
                             / j["summary"]["before_filtering"]["total_reads"],
            "passed_reads": j["filtering_result"]["passed_filter_reads"],
            "gc_content": j["summary"]["after_filtering"]["gc_content"],
        },
        "quality_curves": {                # 截图主图：质控前后 per-base 质量
            "before": j["read1_before_filtering"]["quality_curves"],
            "after":  j["read1_after_filtering"]["quality_curves"],
        },
        "base_content": {                  # 可扩展的第二张图：碱基含量
            "before": j["read1_before_filtering"]["content_curves"],
            "after":  j["read1_after_filtering"]["content_curves"],
        },
        "kmer": j["read1_before_filtering"]["kmer_count"],   # 需要时再给，量大
    }
```

- PE 样本补 `read2_*` 字段；前端加 R1/R2 Tab 切换。
- 后端加进程内 LRU 缓存（fastp.json 几 MB，重复请求不重复读盘解析）。
- 截图页面里的「质控前/质控后」双线图、`mean` 曲线直接用 `quality_curves.mean`；前端即可实现，无需等 MultiQC。

### 8.3 L2：批次合并页（parquet → 前端）

**路径 A：polars 直读（先落地）**

```python
import polars as pl

def multiqc_general_stats(task_id: str):
    pq = Path(f"{DATA_ROOT}/{task_id}/multiqc/multiqc_data/multiqc.parquet")
    df = pl.read_parquet(pq)
    # 首次接入时先打印 df.columns / df.head() 摸清实际 schema，
    # 再按 module=='fastp' 过滤、按 plot/dataset 分组组装成前端需要的 series。
    return df.filter(pl.col("module") == "fastp").to_dicts()
```

parquet 是长表结构（样本 × 指标 × plot），具体列名以 v1.29+ 实际输出为准——**接入第一件事：对一个真实任务跑一次，把 `df.columns` 打印出来固化映射表**，不要凭猜。

**路径 B：官方 Python API（第二步迭代）**

```python
import multiqc

multiqc.parse_logs(str(pq_path))
data = multiqc.get_module_data(module="fastp")   # 结构化模块数据
plots = multiqc.list_plots()                      # plot 对象清单，可序列化后供前端
```

plot 对象保留标题/轴/分组定义，比裸 parquet 省前端配置；但 API 形态随版本演进，封装一层 `multiqc_adapter.py` 隔离，版本升级只改这一个文件。

**前端约定（L1/L2 通用）**：后端统一返回 `{ plot_type: "line"|"bar", series: [{name, x, y, color?}], layout: {...} }`，前端一个 `<PlotlyChart>` 组件通吃，和组学绘图工坊的渲染管线复用。

### 8.4 下载

- `result.zip`：clean fastq + reports + multiqc 整目录，惰性打包。
- 单独下载：`{sample}.fastp.html`、`multiqc_report.html`、`multiqc.parquet`（给想自己做二次分析的用户）。

---

## 9. 配置体系：tool_configs 双层模型

配置分两层，职责分离：

| 层 | 文件 | 谁来改 | 作用 |
| --- | --- | --- | --- |
| L1 工具默认配置 | `tool_configs/fastq_qc/config.yaml` | 你（管理员） | 镜像、资源、fastp/multiqc 默认值、前端可覆盖白名单。改它 = 改平台默认行为 |
| L2 任务快照 | `/data/omichub/qc/tasks/{task_id}/task.yaml` | 创建任务时由 API 自动生成 | L1 与前端参数的**合并结果固化**，此后不再变，保证可复现 |

**合并优先级**：`task.yaml.params` = `config.yaml.fastp.defaults` + 前端覆盖项（仅限 `overridable` 白名单）。已创建任务不受 config.yaml 后续修改影响——半年前的任务重跑，参数环境和当时一模一样。

**目录约定**（平台级规范，后续所有工具照此办理）：

```
tool_configs/
├── fastq_qc/
│   └── config.yaml          # 本工具的全部配置
├── hisat2/                  # 后续工具同样模式
│   └── config.yaml
└── ...
```

### 9.1 config.yaml 完整定义

```yaml
# tool_configs/fastq_qc/config.yaml
tool:
  name: fastq_qc
  display_name: "FASTQ 极速质控"
  version: "1.0.0"
  enabled: true                     # false 时前端隐藏入口，API 拒绝创建任务

# ---- 镜像与部署 ----
image:
  repository: omichub/qc-worker
  tag: "1.0.0"                      # 升 fastp/multiqc 版本 = 升 tag，滚动更新
  pull_policy: IfNotPresent

resources:
  worker:
    concurrency: 2                  # celery --concurrency
    cpu_limit: 8
    mem_limit: "16G"
  fastp:
    threads: 8                      # fastp -w，资源项，不开放给前端

# ---- 队列与超时 ----
queue:
  name: qc
  task_soft_time_limit: 16200       # 4.5h，先触发可清理的异常
  task_time_limit: 18000            # 5h 硬杀
  max_retries: 1

# ---- fastp ----
fastp:
  bin: fastp
  timeout_per_sample: 14400         # 单样本 4h
  defaults:                         # 平台默认值，前端面板初始值从这里读
    qualified_quality_phred: 19     # -q
    unqualified_percent_limit: 40   # -u
    n_base_limit: 5                 # -n
    length_required: 15             # -l
    trim_to_len: 0                  # --max_len1，0 = 不截断
    adapter_trim: true
    detect_adapter_for_pe: true
    correction: false               # PE overlap 校正
    compression_level: 6            # -z
  overridable:                      # 前端参数面板允许覆盖的白名单（安全闸）
    - qualified_quality_phred
    - trim_to_len
    - adapter_trim
  extra_args: []                    # 追加原生参数，高级调试逃生舱

# ---- multiqc ----
multiqc:
  min_version: "1.29"               # parquet 红线，启动校验
  report_name: multiqc_report.html
  force: true                       # -f 覆盖重跑
  modules: [fastp]                  # -m fastp 只聚合 fastp 模块，提速
  require_parquet: true             # 产物校验开关（对应 §6 产物校验）
  extra_args: []
  timeout: 1800

# ---- 存储 ----
storage:
  root: /data/omichub/qc/tasks
  subdirs: [input, output, reports, multiqc, logs]
  zip_lazy: true                    # 首次下载时惰性打包

# ---- worker 启动自检 ----
validation:
  on_worker_start:
    - check_fastp_binary            # fastp --version 可执行
    - check_multiqc_version         # >= multiqc.min_version
    - check_data_root_writable      # storage.root 可写
```

要点：

- `overridable` 白名单是关键安全闸：前端只能调质量阈值、截断长度、接头开关这三个，`-w` 线程数、超时这类资源参数永不暴露，防止用户面板把服务器打爆。
- `extra_args` 留逃生舱：临时想给 fastp 加个 `--low_complexity_filter` 之类，改 yaml 就行，不用改代码。
- `image.tag` 单独成项：以后升版本只改这一个字段 + 推新镜像，Swarm 滚动更新。

### 9.2 配置加载器（worker 与 API 共用）

```python
# tool_config.py —— API 与 worker 容器内都挂载 tool_configs/ 目录
import os, yaml
from pathlib import Path
from pydantic import BaseModel

CONFIG_DIR = Path(os.getenv("OMICHUB_TOOL_CONFIGS", "/app/tool_configs"))

class FastpCfg(BaseModel):
    bin: str = "fastp"
    timeout_per_sample: int = 14400
    defaults: dict
    overridable: list[str] = []
    extra_args: list[str] = []

class MultiqcCfg(BaseModel):
    min_version: str = "1.29"
    report_name: str = "multiqc_report.html"
    force: bool = True
    modules: list[str] = ["fastp"]
    require_parquet: bool = True
    extra_args: list[str] = []
    timeout: int = 1800

class ToolConfig(BaseModel):
    tool: dict
    image: dict
    resources: dict
    queue: dict
    fastp: FastpCfg
    multiqc: MultiqcCfg
    storage: dict
    validation: dict

_cache: dict[str, tuple[float, ToolConfig]] = {}

def load_tool_config(name: str = "fastq_qc") -> ToolConfig:
    """mtime 缓存热更新：改完 yaml 下一个任务即生效，无需重启服务"""
    p = CONFIG_DIR / name / "config.yaml"
    mtime = p.stat().st_mtime
    if name in _cache and _cache[name][0] == mtime:
        return _cache[name][1]
    cfg = ToolConfig(**yaml.safe_load(p.read_text()))
    _cache[name] = (mtime, cfg)
    return cfg

def merge_params(cfg: ToolConfig, frontend_params: dict) -> dict:
    """config 默认值 + 前端覆盖（仅白名单），生成 task.yaml 的 params"""
    allowed = set(cfg.fastp.overridable)
    overrides = {k: v for k, v in frontend_params.items() if k in allowed}
    rejected = set(frontend_params) - allowed
    if rejected:
        logger.warning(f"参数被白名单拦截: {rejected}")
    return {**cfg.fastp.defaults, **overrides}
```

`fastp_cmd()` 相应改为从 `cfg` 读取（`bin`、`extra_args`、`threads` 都走配置），`multiqc` 命令同理：

```python
mq = cfg.multiqc
cmd = [ "multiqc", str(tdir / "reports"), "-o", str(tdir / "multiqc"),
        "-n", mq.report_name, "--no-ansi" ]
if mq.force:   cmd.append("-f")
for m in mq.modules: cmd += ["-m", m]
cmd += mq.extra_args
```

### 9.3 任务快照 task.yaml（API 创建任务时生成）

```yaml
# /data/omichub/qc/tasks/{task_id}/task.yaml —— 由 config.yaml 合并固化，此后只读
task_id: "qc_20260718_a1b2c3"
name: "水稻RIL群体_Q1批次"
created_at: "2026-07-18T10:30:00+08:00"
tool:
  name: fastq_qc
  config_version: "1.0.0"           # 快照时 config.yaml 的 tool.version
image: "omichub/qc-worker:1.0.0"    # 快照时使用的镜像
versions:
  fastp: "0.24.1"                   # worker 执行时回填实际 --version
  multiqc: "1.29"
params:                             # ← merge_params() 的合并结果
  qualified_quality_phred: 19
  trim_to_len: 260
  adapter_trim: true
  threads: 8
samples:
  - name: RIL_001
    r1: /data/omichub/uploads/u_xxx/RIL_001_R1.fastq.gz
    r2: /data/omichub/uploads/u_xxx/RIL_001_R2.fastq.gz
status: SUCCESS
```

**Worker 只读 task.yaml，不再读 config.yaml**——这是双层模型的纪律：任务执行环境完全由快照决定，config.yaml 中途改动不会引发运行中任务行为漂移。config.yaml 只在两个时机被读：① 创建任务合并参数；② worker 启动自检。

### 9.4 部署挂载

```yaml
# docker-compose / swarm stack 片段
services:
  qc-worker:
    image: omichub/qc-worker:1.0.0
    volumes:
      - /data/omichub:/data/omichub
      - ./tool_configs:/app/tool_configs:ro    # 只读挂载，mtime 缓存热更新
    deploy:
      resources:
        limits: { cpus: "8", memory: 16G }
  api:
    volumes:
      - ./tool_configs:/app/tool_configs:ro    # API 侧合并参数用
```

以后改 fastp 默认质量阈值、换镜像 tag、调 multiqc 模块列表，都只动 `tool_configs/fastq_qc/config.yaml` 这一个文件，下一个任务自动生效，零代码改动、零服务重启。

---

## 10. 工程细节与避坑清单

1. **版本红线**：`multiqc<1.29` 没有 parquet。镜像构建和 worker 启动时都 `multiqc --version` 校验，不满足直接拒绝启动。
2. **大样本量**：>100 样本时 MultiQC 自动把交互图切成静态图（内部 Matplotlib），parquet 数据不受影响，L2 层照常工作；L3 报告体积可控，不用特殊处理。
3. **IO 是瓶颈**：fastp 吃磁盘 IO 远胜 CPU。NFS 上跑大批量时，`output/` 写本地盘、完成后再 rsync 回 NFS，比全程直写 NFS 快且稳。二期优化项。
4. **并发模型**：worker `--concurrency=2` + fastp `-w 8`；不要在单容器内再开多样本子进程并行（Swarm 里靠加副本横向扩）。
5. **fastp 只 QC 不出 clean 的模式**：如果用户只想看质量不需要 trimmed 数据，传参时不给 `-o/-O`，速度快一截——前端面板可加「仅评估不过滤」开关（二期）。
6. **上传安全**：样本路径必须校验在 `/data/omichub/uploads/{uid}/` 前缀下，防路径穿越；fastq 大小写后缀统一归一（.fq.gz/.fastq.gz）。
7. **失败可诊断**：每条失败样本保留 fastp log 尾部 50 行入库，前端失败样本卡片直接展示，不用登服务器翻日志。
8. **取消语义**：revoke 时 `terminate=True` 杀子进程，同时清理该任务 output 半成品文件（保留 reports 里已完成的，便于幂等重试）。
9. **parquet 文件名**：保持 `multiqc.parquet` 原名，改名后 `multiqc <file>` 重识别会失败（要求 `*multiqc.parquet` 后缀）。

---

## 11. 里程碑

| 阶段 | 内容 | 验收 |
| --- | --- | --- |
| M1（1 天） | qc-worker 镜像 + task.yaml 规范 + Celery 任务骨架，命令行可跑通单样本 | 容器内 fastp→multiqc 全绿，产物齐 |
| M2（1 天） | FastAPI 七个路由 + MySQL 表 + 前端任务创建/列表/进度 | 页面提交任务到看到 SUCCESS 全流程 |
| M3（1 天） | L1 单样本页接通 fastp.json，截图页面所有图表真实数据渲染 | 指标卡 + 质量曲线前后对比正确 |
| M4（1 天） | L2 合并页 parquet 路径 A + L3 iframe/下载/打包 | 合并图渲染、报告可预览可下载 |
| M5（0.5 天） | 取消/重试/失败日志展示 + 20 样本压测 | 批量任务 PARTIAL 语义正确 |

---

## 12. 交付给 CC 的执行提示词（可直接粘贴）

```text
你是 OmicHub 平台的后端工程师。请按 /mnt/agents/output/OmicHub_FASTQ质控模块实现方案.md 实现 FASTQ 质控模块后端，要求：
1. 严格按文档 §5 构建 omichub/qc-worker 镜像，pin fastp==0.24.1、multiqc>=1.29；
2. 按 §9 实现双层配置体系：tool_configs/fastq_qc/config.yaml（Pydantic 校验 + mtime 热更新）、merge_params 白名单合并、API 创建任务时固化 task.yaml 快照、worker 执行只读 task.yaml、启动自检读 config.yaml；
3. 按 §6 实现 qc_tasks.py：fastp SE/PE 自动组装（bin/threads/extra_args 全部走配置）、样本级幂等跳过、PARTIAL 状态语义、产物存在性校验（multiqc_report.html + multiqc.parquet 缺一不可）；
4. 按 §7 实现 FastAPI 七个路由，任务表/样本表/摘要表用 SQLAlchemy + MySQL，状态机按 §3.2；
5. §8.2 单样本 chart 接口直接解析 fastp.json 裁剪转发，加 LRU 缓存；
6. §8.3 合并图表接口先走路径 A（polars 直读 parquet），接入第一步打印并固化 parquet 实际 schema 映射；
7. 所有样本路径强制校验 /data/omichub/uploads/{uid}/ 前缀；
8. 单元测试覆盖：fastp_cmd 组装（SE/PE/各参数组合）、merge_params 白名单拦截、幂等跳过、失败样本 PARTIAL。
完成后给出：镜像 Dockerfile、qc_tasks.py、api 路由文件、建表 SQL、pytest 文件，以及一份本地 docker-compose（redis + worker + api）用于联调。
```

---

## 附：参考事实来源

- fastp 官方仓库（输出格式、命令行参数、并行批处理脚本）：https://github.com/opengene/fastp
- MultiQC 官方文档 · Downstream analysis（parquet 输出、`parse_logs` / `list_plots` / `get_module_data`、parquet 重跑与合并）：https://github.com/MultiQC/MultiQC/blob/main/docs/markdown/usage/downstream.md
- Seqera MultiQC 文档 · Using MultiQC in scripts（v1.29+ 生成 `multiqc_data/multiqc.parquet`）：https://docs.seqera.io/multiqc/usage/scripts
