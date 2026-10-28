# OmicHub 系统发育树构建工具 — 后端架构设计文档

> **版本**: v1.0  
> **作者**: 生物信息学架构组  
> **日期**: 2025-07-01  
> **适用平台**: OmicHub 生信工具箱 v2.x

---

## 目录

1. [生物信息学流程分析](#1-生物信息学流程分析)
2. [支持的构建方法矩阵](#2-支持的构建方法矩阵)
3. [Celery 任务设计](#3-celery-任务设计)
4. [后端 API 设计](#4-后端-api-设计)
5. [YAML 配置设计](#5-yaml-配置设计)
6. [Docker 镜像策略](#6-docker-镜像策略)
7. [输出格式规范](#7-输出格式规范)

---

## 1. 生物信息学流程分析

### 1.1 完整流程（从输入到输出）

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        系统发育树构建 — 完整数据流                                │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  用户输入                    服务端处理                    结果产出              │
│  ─────────                  ───────────                  ─────────              │
│                                                                                 │
│  ┌─────────────┐           ┌──────────────┐           ┌─────────────────┐       │
│  │ 输入文件    │──────────▶│ 输入验证     │──────────▶│ 预处理FASTA     │       │
│  │(FASTA/Phylip│           │(格式/序列数/ │ 同步       │(去重/去gap/重命名)│     │
│  │ /NEXUS)    │           │ 长度检查)    │ <5s        └─────────────────┘       │
│  └─────────────┘           └──────────────┘                    │                │
│                                                               ▼  Celery         │
│  ┌─────────────┐           ┌──────────────┐           ┌─────────────────┐       │
│  │ 参数配置    │──────────▶│ 参数校验     │──────────▶│ 多序列比对(MSA) │       │
│  │(工具/模型  │           │(依赖矩阵检查)│            │ MAFFT/ClustalO  │       │
│  │ Bootstrap) │           └──────────────┘            │ /Muscle         │       │
│  └─────────────┘                                      └─────────────────┘       │
│                                                                │                │
│                                                               ▼                 │
│                                                       ┌─────────────────┐       │
│                                                       │ 比对后处理       │       │
│                                                       │ (修剪/转格式)   │       │
│                                                       └─────────────────┘       │
│                                                                │                │
│                                                               ▼                 │
│                                                       ┌─────────────────┐       │
│                                                       │ 进化树构建       │       │
│                                                       │ NJ/UPGMA/ML/BI  │       │
│                                                       └─────────────────┘       │
│                                                                │                │
│                                                               ▼                 │
│                                                       ┌─────────────────┐       │
│                                                       │ Bootstrap评估   │       │
│                                                       │ (可选)          │       │
│                                                       └─────────────────┘       │
│                                                                │                │
│                                                               ▼                 │
│                                                       ┌─────────────────┐       │
│                                                       │ 结果格式化输出   │       │
│                                                       │ Newick/NEXUS/   │       │
│                                                       │ PhyloXML+统计   │       │
│                                                       └─────────────────┘       │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 每一步计算复杂度评估

| 步骤 | 算法复杂度 | 预估耗时 (100条序列) | 预估耗时 (1000条序列) | 内存占用 | 执行模式 |
|------|-----------|---------------------|----------------------|---------|---------|
| **输入验证** | O(n × L) 读取文件 | < 1s | < 3s | ~10MB | **同步** |
| **序列预处理** | O(n × L) 字符串操作 | < 1s | < 2s | ~50MB | **同步** |
| **MAFFT 比对** | O(n² × L) FFT-NS-2 | 5-15s | 2-10min | 100MB-2GB | **Celery** |
| **ClustalOmega** | O(n × log n × L) | 3-10s | 1-5min | 100MB-1GB | **Celery** |
| **MUSCLE5** | O(n² × L²) | 10-30s | 5-20min | 200MB-4GB | **Celery** |
| **Neighbor-Joining** | O(n³) 距离矩阵 | < 1s | 10-60s | 50MB-500MB | **Celery** |
| **UPGMA** | O(n² × log n) | < 1s | 5-30s | 50MB-300MB | **Celery** |
| **FastTree (ML近似)** | O(n × L × log n) | 5-30s | 2-10min | 200MB-2GB | **Celery** |
| **IQ-TREE (ML精确)** | O(n³ × L) 启发式搜索 | 30s-5min | 10min-2h | 500MB-8GB | **Celery** |
| **MrBayes (BI)** | O(n × iter × L) MCMC | 5-30min | 1-8h | 500MB-4GB | **Celery** |
| **Bootstrap (100次)** | ×100 树构建时间 | 5× 树构建时间 | 5× 树构建时间 | 与树构建相同 | **Celery** |
| **结果格式化** | O(n) 树遍历 | < 1s | < 2s | ~20MB | **同步** |

> **说明**: n = 序列数量, L = 序列平均长度, iter = MCMC迭代次数  
> **决策边界**: 任何预计超过 5 秒的操作都投递 Celery 异步执行。

### 1.3 同步 vs 异步执行决策

```python
# 同步执行（Web服务器直接处理，前端等待）
SYNC_STEPS = {
    "input_validation": "检查FASTA格式、序列数量上限(≤5000)、长度一致性",
    "sequence_preprocessing": "去重、去除全gap列、序列重命名(兼容Newick)",
    "parameter_validation": "校验工具依赖矩阵(如ML必须要求MSA)",
    "result_formatting": "生成Newick/NEXUS/PhyloXML和统计JSON"
}

# 异步执行（Celery投递，前端轮询）
ASYNC_STEPS = {
    "multiple_sequence_alignment": "MAFFT/ClustalOmega/MUSCLE5",
    "phylogenetic_tree_building": "NJ/UPGMA/FastTree/IQ-TREE/MrBayes",
    "bootstrap_analysis": "重复采样构建一致性树",
    "model_selection": "IQ-TREE的ModelFinder(可选)"
}
```

---

## 2. 支持的构建方法矩阵

### 2.1 多序列比对(MSA)工具选择

| 工具 | 算法特点 | 适用场景 | 序列数上限 | 速度评级 | 精度评级 | Docker镜像 |
|------|---------|---------|-----------|---------|---------|-----------|
| **MAFFT** | FFT-NS-2 / L-INS-i / G-INS-i | 通用首选，蛋白质/核酸均可 | ≤30,000 | ★★★★★ | ★★★★☆ | `quay.io/biocontainers/mafft:7.525--h031d066_0` |
| **ClustalOmega** | HHalign + mBed | 大规模序列(>1000条)，蛋白质 | ≤100,000 | ★★★★★ | ★★★☆☆ | `quay.io/biocontainers/clustalo:1.2.4--hdbdd923_7` |
| **MUSCLE5** | PPP算法，迭代精修 | 高精度需求，中等规模 | ≤20,000 | ★★★☆☆ | ★★★★★ | `quay.io/biocontainers/muscle:5.1--h9f5acd7_3` |

> **推荐策略**: 
> - ≤500 条序列 → **MAFFT L-INS-i** (速度+精度平衡)
> - 500-5000 条 → **MAFFT FFT-NS-2** 或 **ClustalOmega**
> - >5000 条 → **ClustalOmega** (专为大规模优化)
> - 需要最高精度 → **MUSCLE5**

### 2.2 进化树构建方法

| 方法 | 算法类型 | 适用场景 | 计算复杂度 | 推荐Bootstrap | 工具实现 |
|------|---------|---------|-----------|-------------|---------|
| **Neighbor-Joining** | 距离法 | 快速预览、大规模初步聚类 | O(n³) | 100-1000次 | `phylip nj`, `FastTree -nni` |
| **UPGMA** | 距离法 | 等速率进化假设、教学演示 | O(n² log n) | 100-500次 | `phylip kitsch`, Bio.Phylo |
| **FastTree** | 近似最大似然 | 大规模快速ML (≤10⁴序列) | O(nL log n) | 100-1000次 | `FastTree` / `FastTreeMP` |
| **IQ-TREE** | 最大似然 | 精确ML分析，模型选择 | O(n³L) 启发式 | 1000次(Ultrafast) | `iqtree2` |
| **MrBayes** | 贝叶斯推断 | 需要分支支持度(后验概率) | O(n × iter × L) | 不需要(内置) | `mrbayes` |

### 2.3 进化替代模型矩阵

| 模型 | 类型 | 参数数 | 适用数据 | 说明 |
|------|------|--------|---------|------|
| **JC69** | 最简单 | 0 | 核酸 | Jukes-Cantor, 所有替换等概率 |
| **K2P** | 简单 | 1 | 核酸 | Kimura 2-parameter, 转换/颠换比率 |
| **HKY** | 中等 | 4+n | 核酸 | Hasegawa-Kishino-Yano, 考虑碱基频率 |
| **GTR** | 通用 | 8+n | 核酸 | General Time Reversible, 最灵活 |
| **+G** | 扩展 | +1 | 核酸/蛋白 | Gamma分布模拟位点异质性 |
| **+I** | 扩展 | +1 | 核酸/蛋白 | 不变位点比例 |
| **+G+I** | 扩展 | +2 | 核酸/蛋白 | 同时考虑不变位点和Gamma分布 |
| **LG** | 蛋白质 | 0 | 蛋白质 | Le-Gascuel, 蛋白质默认模型 |
| **WAG** | 蛋白质 | 0 | 蛋白质 | Whelan-And-Goldman |

> **模型选择策略**:
> - **快速分析**: K2P+G (核酸), LG (蛋白质)
> - **标准分析**: GTR+G+I (核酸), 由IQ-TREE ModelFinder自动选择
> - **精确分析**: IQ-TREE ModelFinder自动选择最佳模型 + Bootstrap

### 2.4 方法依赖矩阵（参数校验用）

```python
METHOD_DEPENDENCY_MATRIX = {
    # MSA工具 → 支持的树构建方法
    "mafft":        ["nj", "upgma", "fasttree", "iqtree", "mrbayes"],
    "clustalomega": ["nj", "upgma", "fasttree", "iqtree", "mrbayes"],
    "muscle5":      ["nj", "upgma", "fasttree", "iqtree", "mrbayes"],
    
    # 树构建方法 → 需要MSA输入
    "nj":           {"requires_msa": True,  "dna_models": ["JC69","K2P","HKY","GTR","+G","+I"],
                     "protein_models": ["LG","WAG","JTT"]},
    "upgma":        {"requires_msa": True,  "dna_models": ["JC69","K2P","HKY","GTR"],
                     "protein_models": ["LG","WAG"]},
    "fasttree":     {"requires_msa": True,  "dna_models": ["GTR","+G"],
                     "protein_models": ["LG","WAG","JTT"]},
    "iqtree":       {"requires_msa": True,  "dna_models": ["GTR+G+I"],  # ModelFinder自动
                     "protein_models": ["LG+G"],
                     "auto_model": True},
    "mrbayes":      {"requires_msa": True,  "dna_models": ["GTR","HKY","+G","+I"],
                     "protein_models": ["LG","WAG","Mixed"],
                     "burnin": 0.25, "ngen": 1000000},
}
```

### 2.5 Bootstrap策略

| 方法 | Bootstrap类型 | 推荐次数 | 时间开销 |
|------|-------------|---------|---------|
| NJ/UPGMA | 标准Bootstrap | 100-1000 | ×100-1000 |
| FastTree | Shimodaira-Hasegawa (SH) test | 1000 | ×1 (内建) |
| IQ-TREE | Ultrafast Bootstrap (UFBoot) | 1000 | ×5-10 |
| MrBayes | 后验概率 (PP) | N/A (MCMC) | 内置 |

---

## 3. Celery 任务设计

### 3.1 任务拆分策略

**结论: 采用单任务模式，内部按阶段报告进度。**

原因分析：
1. MSA输出 → 树构建输入 是强依赖链，无法并行
2. 拆分两个任务增加调度开销和状态同步复杂度
3. 单任务内部分阶段报告进度更符合用户心智模型
4. 失败时可从MSA或树构建阶段分别重试

```
                    ┌─────────────────────────────────────────┐
                    │         build_phylogenetic_tree          │
                    │              (单Celery任务)              │
                    └─────────────────────────────────────────┘
                                        │
                    ┌───────────────────┼───────────────────┐
                    ▼                   ▼                   ▼
            ┌───────────┐      ┌───────────────┐     ┌──────────────┐
            │  ALIGNING │ ──▶  │   BUILDING    │ ──▶ │  BOOTSTRAP   │
            │   Phase   │      │    Phase      │     │    Phase     │
            │ (20-40%)  │      │   (40-80%)    │     │   (80-100%)  │
            └───────────┘      └───────────────┘     └──────────────┘
```

### 3.2 Celery 任务实现代码

```python
# tasks/phylo_tree.py
"""
系统发育树构建 Celery 任务
负责: MSA → 树构建 → Bootstrap → 结果格式化
"""
import os
import json
import subprocess
import shutil
import tempfile
from pathlib import Path
from typing import Dict, Optional, List
from dataclasses import dataclass, asdict

from celery import shared_task, current_task
from celery.exceptions import SoftTimeLimitExceeded

from omichub.utils.file_utils import validate_fasta, preprocess_sequences
from omichub.utils.phylo_utils import (
    run_mafft, run_clustalomega, run_muscle5,
    run_nj, run_upgma, run_fasttree, run_iqtree, run_mrbayes,
    parse_newick, compute_tree_statistics, convert_format
)

# ───────────────────────────────────────────────
# 任务常量
# ───────────────────────────────────────────────

TASK_TIMEOUT = 3600 * 2          # 2小时超时
TASK_SOFT_TIMEOUT = 3600 * 1     # 1小时软超时
MAX_SEQUENCES = 5000             # 最大序列数
MAX_SEQUENCE_LENGTH = 50000      # 最大序列长度

# 阶段权重（用于进度计算）
PHASE_WEIGHTS = {
    "alignment": 0.35,           # MSA占35%
    "tree_building": 0.40,       # 树构建占40%
    "bootstrap": 0.20,           # Bootstrap占20%
    "formatting": 0.05,          # 格式化占5%
}

# ───────────────────────────────────────────────
# 数据模型
# ───────────────────────────────────────────────

@dataclass
class PhyloTaskInput:
    """系统发育树任务输入参数"""
    # 输入文件
    input_file: str                    # 用户上传的FASTA/Phylip文件路径
    sequence_type: str                 # "dna" | "protein"
    
    # MSA参数
    alignment_tool: str                # "mafft" | "clustalomega" | "muscle5" | "none"
    alignment_params: Optional[Dict] = None
    
    # 树构建参数
    tree_method: str                   # "nj" | "upgma" | "fasttree" | "iqtree" | "mrbayes"
    substitution_model: str            # "auto" | "JC69" | "K2P" | "HKY" | "GTR" | "LG" | ...
    
    # Bootstrap参数
    bootstrap_enabled: bool = True
    bootstrap_replicates: int = 1000
    bootstrap_type: str = "standard"   # "standard" | "ultrafast" | "sh-test"
    
    # 输出参数
    output_formats: List[str] = None   # ["newick", "nexus", "phyloxml"]
    output_prefix: str = "tree"
    
    def __post_init__(self):
        if self.output_formats is None:
            self.output_formats = ["newick"]
        if self.alignment_params is None:
            self.alignment_params = {}


@dataclass
class PhyloTaskResult:
    """系统发育树任务结果"""
    task_id: str
    status: str                        # "COMPLETED" | "FAILED"
    output_files: Dict[str, str]       # 格式 → 文件路径
    statistics: Dict                   # 树统计信息
    execution_time: float              # 总执行时间(秒)
    phases_completed: List[str]        # 完成的阶段列表
    log_file: Optional[str] = None
    error_message: Optional[str] = None


# ───────────────────────────────────────────────
# 主任务
# ───────────────────────────────────────────────

@shared_task(
    bind=True,
    name="omichub.phylo.build_tree",
    time_limit=TASK_TIMEOUT,
    soft_time_limit=TASK_SOFT_TIMEOUT,
    max_retries=2,
    default_retry_delay=60,
)
def build_phylogenetic_tree(self, task_input: Dict) -> Dict:
    """
    系统发育树构建主任务
    
    完整流程: MSA → 树构建 → Bootstrap → 结果格式化
    
    Args:
        task_input: PhyloTaskInput 的字典表示
        
    Returns:
        PhyloTaskResult 的字典表示
    """
    task_id = self.request.id
    params = PhyloTaskInput(**task_input)
    start_time = time.time()
    phases_completed = []
    work_dir = None
    
    try:
        # ── 创建工作目录 ──
        work_dir = Path(tempfile.mkdtemp(prefix=f"phylo_{task_id}_"))
        log_file = work_dir / "execution.log"
        
        def log(msg: str):
            with open(log_file, "a") as f:
                f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
        
        log(f"任务启动 | task_id={task_id} | method={params.tree_method}")
        
        # ═══════════════════════════════════════════
        # PHASE 1: 多序列比对 (MSA)
        # ═══════════════════════════════════════════
        if params.alignment_tool != "none":
            _update_progress(self, "ALIGNING", 0.05, "开始多序列比对...")
            
            aligned_file = work_dir / "alignment.fasta"
            
            if params.alignment_tool == "mafft":
                run_mafft(
                    input_file=params.input_file,
                    output_file=str(aligned_file),
                    mode=params.alignment_params.get("mode", "auto"),
                    threads=params.alignment_params.get("threads", 4),
                    callback=lambda p, msg: _update_progress(
                        self, "ALIGNING", 0.05 + p * PHASE_WEIGHTS["alignment"], msg
                    )
                )
            elif params.alignment_tool == "clustalomega":
                run_clustalomega(
                    input_file=params.input_file,
                    output_file=str(aligned_file),
                    threads=params.alignment_params.get("threads", 4),
                    callback=lambda p, msg: _update_progress(
                        self, "ALIGNING", 0.05 + p * PHASE_WEIGHTS["alignment"], msg
                    )
                )
            elif params.alignment_tool == "muscle5":
                run_muscle5(
                    input_file=params.input_file,
                    output_file=str(aligned_file),
                    iterations=params.alignment_params.get("iterations", 16),
                    callback=lambda p, msg: _update_progress(
                        self, "ALIGNING", 0.05 + p * PHASE_WEIGHTS["alignment"], msg
                    )
                )
            else:
                raise ValueError(f"不支持的比对工具: {params.alignment_tool}")
            
            phases_completed.append("alignment")
            log(f"MSA完成 | tool={params.alignment_tool} | output={aligned_file}")
        else:
            # 用户已提供比对后的序列
            aligned_file = Path(params.input_file)
            _update_progress(self, "ALIGNING", 0.05 + PHASE_WEIGHTS["alignment"], 
                           "跳过比对(使用预比对输入)")
            phases_completed.append("alignment_skipped")
        
        # ═══════════════════════════════════════════
        # PHASE 2: 进化树构建
        # ═══════════════════════════════════════════
        _update_progress(self, "BUILDING", 
                        0.05 + PHASE_WEIGHTS["alignment"],
                        "开始构建进化树...")
        
        tree_file = work_dir / f"{params.output_prefix}.tree"
        
        if params.tree_method == "nj":
            run_nj(
                alignment_file=str(aligned_file),
                output_file=str(tree_file),
                model=params.substitution_model,
                callback=lambda p, msg: _update_progress(
                    self, "BUILDING",
                    0.05 + PHASE_WEIGHTS["alignment"] + p * PHASE_WEIGHTS["tree_building"],
                    msg
                )
            )
        elif params.tree_method == "upgma":
            run_upgma(
                alignment_file=str(aligned_file),
                output_file=str(tree_file),
                model=params.substitution_model,
                callback=lambda p, msg: _update_progress(
                    self, "BUILDING",
                    0.05 + PHASE_WEIGHTS["alignment"] + p * PHASE_WEIGHTS["tree_building"],
                    msg
                )
            )
        elif params.tree_method == "fasttree":
            run_fasttree(
                alignment_file=str(aligned_file),
                output_file=str(tree_file),
                sequence_type=params.sequence_type,
                model=params.substitution_model,
                callback=lambda p, msg: _update_progress(
                    self, "BUILDING",
                    0.05 + PHASE_WEIGHTS["alignment"] + p * PHASE_WEIGHTS["tree_building"],
                    msg
                )
            )
        elif params.tree_method == "iqtree":
            run_iqtree(
                alignment_file=str(aligned_file),
                output_file=str(tree_file),
                sequence_type=params.sequence_type,
                model=params.substitution_model,  # "auto" 启用ModelFinder
                bootstrap_replicates=params.bootstrap_replicates if params.bootstrap_enabled else 0,
                bootstrap_type=params.bootstrap_type,  # "ultrafast" 推荐
                threads=params.alignment_params.get("threads", 4),
                callback=lambda p, msg: _update_progress(
                    self, "BUILDING",
                    0.05 + PHASE_WEIGHTS["alignment"] + p * PHASE_WEIGHTS["tree_building"],
                    msg
                )
            )
        elif params.tree_method == "mrbayes":
            run_mrbayes(
                alignment_file=str(aligned_file),
                output_file=str(tree_file),
                sequence_type=params.sequence_type,
                model=params.substitution_model,
                ngen=params.alignment_params.get("ngen", 1000000),
                burnin=params.alignment_params.get("burnin_fraction", 0.25),
                nchains=params.alignment_params.get("nchains", 4),
                callback=lambda p, msg: _update_progress(
                    self, "BUILDING",
                    0.05 + PHASE_WEIGHTS["alignment"] + p * PHASE_WEIGHTS["tree_building"],
                    msg
                )
            )
        else:
            raise ValueError(f"不支持的树构建方法: {params.tree_method}")
        
        phases_completed.append("tree_building")
        log(f"树构建完成 | method={params.tree_method} | output={tree_file}")
        
        # ═══════════════════════════════════════════
        # PHASE 3: Bootstrap (如未在工具内完成)
        # ═══════════════════════════════════════════
        if params.bootstrap_enabled and params.tree_method in ["nj", "upgma"]:
            _update_progress(self, "BOOTSTRAPPING",
                           0.05 + PHASE_WEIGHTS["alignment"] + PHASE_WEIGHTS["tree_building"],
                           "开始Bootstrap评估...")
            
            bootstrap_tree_file = work_dir / f"{params.output_prefix}_bootstrap.tree"
            _run_bootstrap(
                alignment_file=str(aligned_file),
                tree_file=str(tree_file),
                output_file=str(bootstrap_tree_file),
                method=params.tree_method,
                replicates=params.bootstrap_replicates,
                model=params.substitution_model,
                callback=lambda p, msg: _update_progress(
                    self, "BOOTSTRAPPING",
                    0.05 + PHASE_WEIGHTS["alignment"] + PHASE_WEIGHTS["tree_building"]
                    + p * PHASE_WEIGHTS["bootstrap"],
                    msg
                )
            )
            tree_file = bootstrap_tree_file  # 使用带Bootstrap的树
            phases_completed.append("bootstrap")
            log(f"Bootstrap完成 | replicates={params.bootstrap_replicates}")
        else:
            phases_completed.append("bootstrap_skipped")
        
        # ═══════════════════════════════════════════
        # PHASE 4: 结果格式化输出
        # ═══════════════════════════════════════════
        _update_progress(self, "FORMATTING", 0.95, "格式化输出结果...")
        
        output_files = {}
        base_path = work_dir / params.output_prefix
        
        # 始终输出 Newick
        final_newick = str(base_path) + ".nwk"
        shutil.copy(str(tree_file), final_newick)
        output_files["newick"] = final_newick
        
        # 可选 NEXUS
        if "nexus" in params.output_formats:
            nexus_file = str(base_path) + ".nex"
            convert_format(str(tree_file), nexus_file, "nexus",
                          alignment_file=str(aligned_file) if params.alignment_tool != "none" else None)
            output_files["nexus"] = nexus_file
        
        # 可选 PhyloXML
        if "phyloxml" in params.output_formats:
            phyloxml_file = str(base_path) + ".xml"
            convert_format(str(tree_file), phyloxml_file, "phyloxml")
            output_files["phyloxml"] = phyloxml_file
        
        # 统计信息
        tree_stats = compute_tree_statistics(str(tree_file))
        stats_file = str(base_path) + ".stats.json"
        with open(stats_file, "w") as f:
            json.dump(tree_stats, f, indent=2, ensure_ascii=False)
        output_files["statistics"] = stats_file
        
        phases_completed.append("formatting")
        log("结果格式化完成")
        
        # ═══════════════════════════════════════════
        # 任务完成
        # ═══════════════════════════════════════════
        execution_time = time.time() - start_time
        
        result = PhyloTaskResult(
            task_id=task_id,
            status="COMPLETED",
            output_files=output_files,
            statistics=tree_stats,
            execution_time=round(execution_time, 2),
            phases_completed=phases_completed,
            log_file=str(log_file)
        )
        
        _update_progress(self, "COMPLETED", 1.0, "任务完成!")
        log(f"任务完成 | 耗时={execution_time:.1f}s")
        
        return asdict(result)
        
    except SoftTimeLimitExceeded:
        error_msg = f"任务执行超时(超过{TASK_SOFT_TIMEOUT}秒)"
        log(error_msg)
        return _build_error_result(task_id, error_msg, phases_completed, log_file)
    except Exception as e:
        error_msg = f"任务执行失败: {str(e)}"
        log(error_msg)
        # 重试逻辑
        if self.request.retries < self.max_retries:
            log(f"准备第{self.request.retries + 1}次重试...")
            raise self.retry(exc=e, countdown=60)
        return _build_error_result(task_id, error_msg, phases_completed, 
                                    log_file if 'log_file' in dir() else None)
    finally:
        # 清理临时工作目录（保留结果文件）
        if work_dir and work_dir.exists():
            # 结果文件已复制到用户目录，可安全删除
            pass


# ───────────────────────────────────────────────
# 辅助函数
# ───────────────────────────────────────────────

def _update_progress(task, phase: str, progress: float, message: str):
    """更新任务进度到Celery后端"""
    task.update_state(
        state="PROGRESS",
        meta={
            "phase": phase,                    # 当前阶段
            "progress": round(progress, 4),    # 0.0 ~ 1.0
            "message": message,                # 人类可读描述
            "timestamp": time.time(),
        }
    )


def _build_error_result(task_id: str, error: str, phases: List[str], 
                        log_file: Optional[str] = None) -> Dict:
    """构建错误结果"""
    return asdict(PhyloTaskResult(
        task_id=task_id,
        status="FAILED",
        output_files={},
        statistics={},
        execution_time=0,
        phases_completed=phases,
        log_file=log_file,
        error_message=error
    ))


def _run_bootstrap(alignment_file: str, tree_file: str, output_file: str,
                   method: str, replicates: int, model: str,
                   callback=None):
    """
    对NJ/UPGMA方法执行标准Bootstrap
    
    使用seqboot + 对应树方法 + consense流程
    """
    # 实现细节略，调用PHYLIP工具包
    pass
```

### 3.3 任务状态流转图

```
                         ┌─────────────┐
                         │   PENDING   │ ◀── 任务已投递，等待Worker
                         └──────┬──────┘
                                │ Worker领取任务
                                ▼
                    ┌───────────────────────┐
                    │      ALIGNING         │ ◀── 执行MSA比对
                    │   (进度 0% ~ 35%)     │
                    └───────────┬───────────┘
                                │
                    ┌───────────┴───────────┐
                    ▼                       ▼
          ┌─────────────────┐    ┌─────────────────┐
          │    BUILDING     │    │     FAILED      │
          │ (进度 35% ~ 80%)│    │  (MSA失败/参数错)│
          └────────┬────────┘    └─────────────────┘
                   │
       ┌───────────┴───────────┐
       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐
│  BOOTSTRAPPING  │    │  BUILDING_DONE  │ ◀── Bootstrap已跳过
│ (进度 80% ~ 95%)│    │  (直接→FORMATTING)│
└────────┬────────┘    └─────────────────┘
         │
         ▼
┌───────────────────────┐
│     FORMATTING        │ ◀── 格式化输出
│   (进度 95% ~ 100%)   │
└───────────┬───────────┘
            │
            ▼
    ┌───────────────┐
    │   COMPLETED   │ ◀── 任务完成，结果可下载
    └───────────────┘
```

### 3.4 前端轮询接口

```python
# api/phylo_tree.py (Celery任务状态查询)

@router.get("/tasks/{task_id}/status")
async def get_task_status(task_id: str):
    """
    查询系统发育树构建任务状态
    
    响应示例 (PROGRESS状态):
    {
        "task_id": "abc-123",
        "status": "PROGRESS",           # PENDING / PROGRESS / SUCCESS / FAILURE
        "phase": "BUILDING",            # 当前阶段
        "progress": 0.52,               # 0.0 ~ 1.0
        "message": "IQ-TREE启发式搜索第3轮...",
        "created_at": "2025-07-01T10:00:00Z",
        "updated_at": "2025-07-01T10:05:23Z"
    }
    
    响应示例 (SUCCESS状态):
    {
        "task_id": "abc-123",
        "status": "SUCCESS",
        "result": {
            "output_files": {
                "newick": "/results/user_123/tree.nwk",
                "statistics": "/results/user_123/tree.stats.json"
            },
            "statistics": { ... },
            "execution_time": 186.5,
            "phases_completed": ["alignment", "tree_building", "bootstrap_skipped", "formatting"]
        }
    }
    """
    task_result = AsyncResult(task_id, app=celery_app)
    
    response = {
        "task_id": task_id,
        "status": task_result.status,
    }
    
    if task_result.status == "PENDING":
        response["message"] = "任务等待执行中..."
        
    elif task_result.status == "PROGRESS":
        meta = task_result.info or {}
        response.update({
            "phase": meta.get("phase", "UNKNOWN"),
            "progress": meta.get("progress", 0),
            "message": meta.get("message", ""),
        })
        
    elif task_result.status == "SUCCESS":
        response["result"] = task_result.result
        
    elif task_result.status == "FAILURE":
        response["error"] = str(task_result.result)
    
    return response
```

### 3.5 前端轮询策略

```javascript
// 前端 Vue 3 轮询逻辑示例

const POLLING_INTERVAL = 2000;      // 2秒轮询一次
const POLLING_INTERVAL_FAST = 500;  // 快速阶段 0.5秒轮询

class PhyloTaskPoller {
  constructor(taskId, onProgress, onComplete, onError) {
    this.taskId = taskId;
    this.onProgress = onProgress;
    this.onComplete = onComplete;
    this.onError = onError;
    this.timer = null;
  }

  async poll() {
    const resp = await fetch(`/api/phylo/tasks/${this.taskId}/status`);
    const data = await resp.json();

    switch (data.status) {
      case "PENDING":
        this.schedulePoll(POLLING_INTERVAL);
        break;
        
      case "PROGRESS":
        this.onProgress({
          phase: data.phase,
          percent: Math.round(data.progress * 100),
          message: data.message
        });
        // 根据阶段调整轮询频率
        const interval = ["ALIGNING", "BUILDING"].includes(data.phase) 
          ? POLLING_INTERVAL_FAST 
          : POLLING_INTERVAL;
        this.schedulePoll(interval);
        break;
        
      case "SUCCESS":
        this.onComplete(data.result);
        break;
        
      case "FAILURE":
        this.onError(data.error);
        break;
    }
  }

  schedulePoll(interval) {
    this.timer = setTimeout(() => this.poll(), interval);
  }

  stop() {
    if (this.timer) clearTimeout(this.timer);
  }
}

// 使用示例
const poller = new PhyloTaskPoller(
  taskId,
  (progress) => { /* 更新进度条 UI */ },
  (result) => { /* 展示结果树 */ },
  (error) => { /* 展示错误信息 */ }
);
poller.poll();
```

---

## 4. 后端 API 设计

### 4.1 API 路由总览

| 方法 | 路由 | 功能 | 执行模式 |
|------|------|------|---------|
| POST | `/api/phylo/upload` | 上传序列文件 | 同步 |
| POST | `/api/phylo/submit` | 提交树构建任务 | 同步(投递Celery) |
| GET | `/api/phylo/tasks/{id}/status` | 查询任务状态 | 同步 |
| GET | `/api/phylo/tasks/{id}/result` | 获取任务结果 | 同步 |
| DELETE | `/api/phylo/tasks/{id}/cancel` | 取消任务 | 同步 |
| GET | `/api/phylo/download/{id}/{format}` | 下载结果文件 | 同步 |
| GET | `/api/phylo/methods` | 获取支持的构建方法列表 | 同步 |
| POST | `/api/phylo/validate` | 预验证参数组合 | 同步 |

### 4.2 FastAPI 路由实现

```python
# routers/phylo_tree.py
"""
系统发育树构建工具 — FastAPI 路由
"""
import os
import uuid
import shutil
from pathlib import Path
from typing import Optional, List
from datetime import datetime

from fastapi import APIRouter, File, UploadFile, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field, validator
from celery import Celery

# ───────────────────────────────────────────────
# 配置
# ───────────────────────────────────────────────

UPLOAD_DIR = Path("/data/omichub/uploads/phylo")
RESULTS_DIR = Path("/data/omichub/results/phylo")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

# Celery实例
celery_app = Celery("omichub")

router = APIRouter(prefix="/api/phylo", tags=["系统发育树构建"])

# ───────────────────────────────────────────────
# Pydantic 请求/响应模型
# ───────────────────────────────────────────────

class TreeSubmitRequest(BaseModel):
    """提交树构建任务的请求参数"""
    input_file_id: str = Field(..., description="上传文件ID")
    sequence_type: str = Field("dna", regex="^(dna|protein)$")
    
    # MSA
    alignment_tool: str = Field("mafft", 
        regex="^(mafft|clustalomega|muscle5|none)$")
    alignment_mode: Optional[str] = "auto"  # MAFFT模式
    
    # 树构建
    tree_method: str = Field("iqtree",
        regex="^(nj|upgma|fasttree|iqtree|mrbayes)$")
    substitution_model: str = Field("auto")
    
    # Bootstrap
    bootstrap_enabled: bool = True
    bootstrap_replicates: int = Field(1000, ge=100, le=10000)
    bootstrap_type: str = Field("ultrafast", 
        regex="^(standard|ultrafast|sh-test)$")
    
    # 输出
    output_formats: List[str] = Field(default_factory=lambda: ["newick"])
    
    # 资源
    threads: int = Field(4, ge=1, le=16)
    
    @validator("output_formats")
    def validate_formats(cls, v):
        allowed = {"newick", "nexus", "phyloxml"}
        for f in v:
            if f not in allowed:
                raise ValueError(f"不支持的输出格式: {f}")
        return v
    
    @validator("substitution_model")
    def validate_model(cls, v, values):
        if v == "auto":
            return v
        tree_method = values.get("tree_method", "")
        # 校验模型与方法兼容性
        valid_models = {
            "nj": ["JC69", "K2P", "HKY", "GTR"],
            "upgma": ["JC69", "K2P", "HKY", "GTR"],
            "fasttree": ["GTR", "LG", "WAG", "JTT"],
            "iqtree": ["auto", "GTR+G+I", "LG+G", "K2P+G"],
            "mrbayes": ["GTR", "HKY", "LG", "WAG"],
        }
        if tree_method and v not in valid_models.get(tree_method, []):
            raise ValueError(f"模型 {v} 不适用于方法 {tree_method}")
        return v


class TaskResponse(BaseModel):
    """统一任务响应"""
    code: int = 200
    message: str = "success"
    data: dict = {}


# ───────────────────────────────────────────────
# API 实现
# ───────────────────────────────────────────────

@router.post("/upload", response_model=TaskResponse)
async def upload_sequence_file(
    file: UploadFile = File(..., description="序列文件 (FASTA/Phylip/NEXUS格式)")
):
    """
    上传序列文件
    
    - 支持格式: FASTA (.fa/.fasta/.fna), Phylip (.phy), NEXUS (.nex)
    - 最大文件大小: 50MB
    - 最大序列数: 5000条
    - 自动检测序列类型 (DNA/Protein)
    """
    # 生成文件ID
    file_id = f"phylo_{uuid.uuid4().hex[:12]}_{datetime.now().strftime('%Y%m%d')}"
    file_ext = Path(file.filename).suffix.lower()
    
    # 验证文件扩展名
    allowed_exts = {".fa", ".fasta", ".fna", ".faa", ".phy", ".nex", ".nexus"}
    if file_ext not in allowed_exts:
        raise HTTPException(400, f"不支持的文件格式: {file_ext}")
    
    # 保存文件
    save_path = UPLOAD_DIR / f"{file_id}{file_ext}"
    try:
        with open(save_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
    except Exception as e:
        raise HTTPException(500, f"文件保存失败: {str(e)}")
    
    # 验证文件内容
    try:
        validation_result = validate_sequence_file(str(save_path))
    except Exception as e:
        save_path.unlink(missing_ok=True)
        raise HTTPException(400, f"文件验证失败: {str(e)}")
    
    return TaskResponse(data={
        "file_id": file_id,
        "original_name": file.filename,
        "file_size": save_path.stat().st_size,
        "sequence_count": validation_result["sequence_count"],
        "sequence_type": validation_result["sequence_type"],
        "avg_length": validation_result["avg_length"],
        "uploaded_at": datetime.now().isoformat()
    })


@router.post("/submit", response_model=TaskResponse)
async def submit_tree_task(request: TreeSubmitRequest):
    """
    提交系统发育树构建任务
    
    任务投递到Celery异步执行，返回task_id用于轮询
    """
    # 查找上传文件
    # 支持匹配任意扩展名
    input_files = list(UPLOAD_DIR.glob(f"{request.input_file_id}.*"))
    if not input_files:
        raise HTTPException(404, "上传文件不存在或已过期")
    input_file = str(input_files[0])
    
    # 构建任务参数
    task_input = {
        "input_file": input_file,
        "sequence_type": request.sequence_type,
        "alignment_tool": request.alignment_tool,
        "alignment_params": {
            "mode": request.alignment_mode,
            "threads": request.threads,
        },
        "tree_method": request.tree_method,
        "substitution_model": request.substitution_model,
        "bootstrap_enabled": request.bootstrap_enabled,
        "bootstrap_replicates": request.bootstrap_replicates,
        "bootstrap_type": request.bootstrap_type,
        "output_formats": request.output_formats,
        "output_prefix": f"tree_{request.input_file_id}",
    }
    
    # 投递Celery任务
    task = celery_app.send_task(
        "omichub.phylo.build_tree",
        args=[task_input],
        queue="phylo_tree",           # 专用队列
        priority=5,                    # 中等优先级
    )
    
    return TaskResponse(data={
        "task_id": task.id,
        "status": "PENDING",
        "submitted_at": datetime.now().isoformat(),
        "estimated_duration": _estimate_duration(task_input),
    })


@router.get("/tasks/{task_id}/status", response_model=TaskResponse)
async def get_task_status(task_id: str):
    """查询任务执行状态和进度"""
    from celery.result import AsyncResult
    
    result = AsyncResult(task_id, app=celery_app)
    
    data = {
        "task_id": task_id,
        "status": result.status,
    }
    
    if result.status == "PROGRESS":
        meta = result.info or {}
        data.update({
            "phase": meta.get("phase"),
            "progress": meta.get("progress"),
            "message": meta.get("message"),
        })
    elif result.status == "SUCCESS":
        data["result"] = result.result
    elif result.status == "FAILURE":
        data["error"] = str(result.result)
    
    return TaskResponse(data=data)


@router.get("/tasks/{task_id}/result")
async def get_task_result(task_id: str, format: str = "json"):
    """
    获取任务结果
    
    - format=json: 返回JSON格式的结果摘要和统计
    - format=newick: 直接返回Newick文本
    - format=nexus: 返回NEXUS文件
    - format=phyloxml: 返回PhyloXML文件
    """
    from celery.result import AsyncResult
    
    result = AsyncResult(task_id, app=celery_app)
    
    if result.status != "SUCCESS":
        raise HTTPException(400, f"任务未完成，当前状态: {result.status}")
    
    task_result = result.result
    output_files = task_result.get("output_files", {})
    
    if format == "json":
        return TaskResponse(data={
            "statistics": task_result.get("statistics", {}),
            "execution_time": task_result.get("execution_time"),
            "phases_completed": task_result.get("phases_completed"),
            "available_formats": list(output_files.keys()),
            "download_links": {
                fmt: f"/api/phylo/download/{task_id}/{fmt}"
                for fmt in output_files.keys()
            }
        })
    
    elif format in ["newick", "nexus", "phyloxml"]:
        file_path = output_files.get(format)
        if not file_path or not os.path.exists(file_path):
            raise HTTPException(404, f"{format} 格式结果不存在")
        
        media_types = {
            "newick": "text/plain",
            "nexus": "text/plain",
            "phyloxml": "application/xml",
        }
        return FileResponse(
            file_path,
            media_type=media_types.get(format, "text/plain"),
            filename=f"phylogenetic_tree.{format}"
        )
    
    else:
        raise HTTPException(400, f"不支持的格式: {format}")


@router.delete("/tasks/{task_id}/cancel", response_model=TaskResponse)
async def cancel_task(task_id: str):
    """取消正在执行的任务"""
    from celery.result import AsyncResult
    
    result = AsyncResult(task_id, app=celery_app)
    
    if result.status in ["PENDING", "PROGRESS", "RETRY"]:
        celery_app.control.revoke(task_id, terminate=True, signal="SIGTERM")
        return TaskResponse(data={
            "task_id": task_id,
            "status": "CANCELLED",
            "message": "任务已取消"
        })
    else:
        return TaskResponse(code=400, message=f"任务状态为 {result.status}，无法取消")


@router.get("/download/{task_id}/{file_format}")
async def download_result_file(task_id: str, file_format: str):
    """下载结果文件"""
    from celery.result import AsyncResult
    
    result = AsyncResult(task_id, app=celery_app)
    if result.status != "SUCCESS":
        raise HTTPException(400, "任务未完成")
    
    output_files = result.result.get("output_files", {})
    file_path = output_files.get(file_format)
    
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(404, "文件不存在")
    
    ext_map = {
        "newick": ".nwk", "nexus": ".nex", 
        "phyloxml": ".xml", "statistics": ".json"
    }
    return FileResponse(
        file_path,
        filename=f"tree_{task_id}{ext_map.get(file_format, '')}"
    )


@router.get("/methods", response_model=TaskResponse)
async def list_supported_methods():
    """获取支持的构建方法和参数选项"""
    return TaskResponse(data={
        "alignment_tools": [
            {"key": "mafft", "name": "MAFFT", "description": "快速傅里叶变换比对", 
             "modes": ["auto", "FFT-NS-1", "FFT-NS-2", "L-INS-i", "G-INS-i"]},
            {"key": "clustalomega", "name": "ClustalOmega", 
             "description": "适合大规模序列"},
            {"key": "muscle5", "name": "MUSCLE5", 
             "description": "高精度迭代比对"},
            {"key": "none", "name": "跳过比对", 
             "description": "输入已比对的序列"},
        ],
        "tree_methods": [
            {"key": "nj", "name": "Neighbor-Joining", "type": "距离法", 
             "speed": "快", "accuracy": "中"},
            {"key": "upgma", "name": "UPGMA", "type": "距离法", 
             "speed": "快", "accuracy": "低"},
            {"key": "fasttree", "name": "FastTree", "type": "近似最大似然", 
             "speed": "很快", "accuracy": "中高"},
            {"key": "iqtree", "name": "IQ-TREE", "type": "最大似然", 
             "speed": "中", "accuracy": "高", "features": ["ModelFinder", "UFBoot"]},
            {"key": "mrbayes", "name": "MrBayes", "type": "贝叶斯推断", 
             "speed": "慢", "accuracy": "很高", "features": ["后验概率"]},
        ],
        "substitution_models": {
            "dna": ["JC69", "K2P", "HKY", "GTR", "+G", "+I", "+G+I"],
            "protein": ["LG", "WAG", "JTT", "Dayhoff", "+G", "+I"],
        },
        "bootstrap_options": {
            "types": ["standard", "ultrafast", "sh-test"],
            "replicates_range": {"min": 100, "max": 10000, "default": 1000},
        }
    })


@router.post("/validate", response_model=TaskResponse)
async def validate_parameters(request: TreeSubmitRequest):
    """
    预验证参数组合是否合法
    
    在正式提交前检查参数兼容性
    """
    warnings = []
    errors = []
    
    # 检查模型与方法兼容性
    if request.tree_method == "iqtree" and request.substitution_model != "auto":
        warnings.append("IQ-TREE推荐启用ModelFinder自动选择模型")
    
    if request.tree_method == "mrbayes" and request.bootstrap_enabled:
        warnings.append("MrBayes使用后验概率评估支持度，建议关闭Bootstrap")
    
    if request.tree_method in ["nj", "upgma"] and not request.bootstrap_enabled:
        warnings.append("距离法建议启用Bootstrap以评估分支支持度")
    
    # 检查序列数与方法兼容性
    # (实际序列数需要从文件读取)
    
    if errors:
        return TaskResponse(code=400, message="参数验证失败", data={"errors": errors})
    
    return TaskResponse(data={
        "valid": True,
        "warnings": warnings,
        "estimated_memory": _estimate_memory(request),
        "estimated_duration": _estimate_duration(request.dict()),
    })


# ───────────────────────────────────────────────
# 辅助函数
# ───────────────────────────────────────────────

def validate_sequence_file(file_path: str) -> dict:
    """验证序列文件并返回基本信息"""
    # 实际实现使用Biopython SeqIO
    from Bio import SeqIO
    
    sequences = list(SeqIO.parse(file_path, "fasta"))
    if not sequences:
        raise ValueError("文件中未找到有效序列")
    if len(sequences) > MAX_SEQUENCES:
        raise ValueError(f"序列数量 {len(sequences)} 超过上限 {MAX_SEQUENCES}")
    
    lengths = [len(s) for s in sequences]
    avg_len = sum(lengths) / len(lengths)
    
    # 自动检测序列类型
    sample = str(sequences[0].seq)[:1000].upper()
    dna_chars = set("ATGCN-")
    protein_chars = set("ACDEFGHIKLMNPQRSTVWY-")
    
    seq_type = "dna" if set(sample).issubset(dna_chars) else "protein"
    
    return {
        "sequence_count": len(sequences),
        "sequence_type": seq_type,
        "avg_length": round(avg_len, 1),
        "min_length": min(lengths),
        "max_length": max(lengths),
    }


def _estimate_duration(params: dict) -> str:
    """预估任务执行时间"""
    # 简化估算逻辑
    seq_count = params.get("sequence_count", 100)
    method = params.get("tree_method", "iqtree")
    bootstrap = params.get("bootstrap_enabled", True)
    
    base_times = {"nj": 10, "upgma": 5, "fasttree": 30, "iqtree": 120, "mrbayes": 1800}
    base = base_times.get(method, 60)
    
    # 根据序列数调整
    scale = max(1, seq_count / 100)
    if method in ["iqtree", "mrbayes"]:
        scale = scale ** 1.5
    
    # Bootstrap倍率
    if bootstrap and method in ["nj", "upgma"]:
        base *= 5
    elif bootstrap and method == "iqtree":
        base *= 2
    
    estimated = int(base * scale)
    if estimated < 60:
        return f"约 {estimated} 秒"
    elif estimated < 3600:
        return f"约 {estimated // 60} 分钟"
    else:
        return f"约 {estimated // 3600} 小时 {estimated % 3600 // 60} 分钟"


def _estimate_memory(params) -> str:
    """预估内存需求"""
    # 简化估算
    return "512MB - 4GB (取决于序列数量和长度)"
```

### 4.3 API 时序图

```
前端(Vue3)                    OmicHub后端                  Celery Worker
   │                              │                              │
   │  1. POST /upload (FASTA)    │                              │
   │ ─────────────────────────▶  │                              │
   │                              │  保存文件/验证格式            │
   │  返回 file_id               │                              │
   │ ◀─────────────────────────  │                              │
   │                              │                              │
   │  2. POST /submit            │                              │
   │  {file_id, method, model}   │                              │
   │ ─────────────────────────▶  │                              │
   │                              │  参数校验                     │
   │                              │  投递Celery任务               │
   │                              │ ───────────────────────────▶ │
   │  返回 task_id               │                              │
   │ ◀─────────────────────────  │                              │
   │                              │                              │
   │  3. GET /tasks/{id}/status  │                              │
   │ ─────────────────────────▶  │                              │
   │  (轮询, 每2秒)              │  查询Redis结果后端            │
   │                              │                              │
   │  返回 PROGRESS 状态         │                              │  执行任务
   │ ◀─────────────────────────  │                              │  ALIGNING
   │  ...                        │                              │  BUILDING
   │  ...                        │                              │  BOOTSTRAP
   │                              │                              │
   │  返回 SUCCESS + 结果链接    │                              │  COMPLETED
   │ ◀─────────────────────────  │                              │
   │                              │                              │
   │  4. GET /download/{id}/nwk  │                              │
   │ ─────────────────────────▶  │                              │
   │                              │  读取结果文件                 │
   │  返回 Newick 文件           │                              │
   │ ◀─────────────────────────  │                              │
```



---

## 5. YAML 配置设计

### 5.1 目录结构

```
tool_configs/
├── tools_setting.yaml              # 全局工具注册表
└── phylogenetic-tree/              # 本工具专属配置目录
    ├── config.yaml                 # 主配置文件
    ├── defaults.yaml               # 默认参数配置
    ├── methods.yaml                # 构建方法详细配置
    ├── presets/                    # 预配置场景
    │   ├── 16s-rrna.yaml           # 16S rRNA细菌系统发育
    │   ├── cov-spike.yaml          # 冠状病毒刺突蛋白
    │   ├── housekeeping-genes.yaml # 持家基因家族
    │   └── protein-superfamily.yaml# 蛋白质超家族
    └── docker/                     # Docker资源配置
        └── resource-limits.yaml
```

### 5.2 主配置文件 `config.yaml`

```yaml
# tool_configs/phylogenetic-tree/config.yaml
# 系统发育树构建工具 — 主配置

meta:
  name: "phylogenetic-tree"
  version: "1.0.0"
  description: "多序列比对与系统发育树构建工具，支持NJ/UPGMA/ML/BI多种方法"
  author: "OmicHub Bioinfo Team"
  last_updated: "2025-07-01"

# ─────────────────────────────────────────────
# 功能开关
# ─────────────────────────────────────────────
features:
  multiple_sequence_alignment: true    # MSA功能
  tree_building: true                  # 树构建功能
  bootstrap_analysis: true             # Bootstrap评估
  model_selection: true                # 自动模型选择(ModelFinder)
  tree_visualization_data: true        # 生成前端可视化数据
  format_conversion: true              # 多格式输出

# ─────────────────────────────────────────────
# 输入限制
# ─────────────────────────────────────────────
input_limits:
  max_file_size_mb: 50                 # 最大上传文件50MB
  max_sequences: 5000                  # 最大序列数
  max_sequence_length: 50000           # 最大序列长度
  supported_formats:
    - ext: ".fasta"
      mime: "text/x-fasta"
      parser: "biopython_seqio"
    - ext: ".fa"
      mime: "text/x-fasta"
      parser: "biopython_seqio"
    - ext: ".fna"
      mime: "text/x-fasta"
      parser: "biopython_seqio"
    - ext: ".faa"
      mime: "text/x-fasta"
      parser: "biopython_seqio"
    - ext: ".phy"
      mime: "text/x-phylp"
      parser: "biopython_seqio_phylip"
    - ext: ".phylip"
      mime: "text/x-phylip"
      parser: "biopython_seqio_phylip"
    - ext: ".nex"
      mime: "text/x-nexus"
      parser: "biopython_seqio_nexus"
    - ext: ".nexus"
      mime: "text/x-nexus"
      parser: "biopython_seqio_nexus"

# ─────────────────────────────────────────────
# 任务执行配置
# ─────────────────────────────────────────────
execution:
  # Celery队列配置
  celery:
    queue: "phylo_tree"
    routing_key: "phylo.tree.build"
    priority: 5                        # 1-10, 10最高
    time_limit_seconds: 7200           # 2小时硬超时
    soft_time_limit_seconds: 3600      # 1小时软超时
    max_retries: 2
    retry_delay_seconds: 60
  
  # 资源限制
  resources:
    default_threads: 4
    max_threads: 16
    default_memory_mb: 4096            # 4GB
    max_memory_mb: 32768               # 32GB
  
  # 进度报告
  progress_reporting:
    enabled: true
    min_interval_seconds: 1            # 最小报告间隔
    phases:
      - name: "ALIGNING"
        weight: 0.35
        description: "多序列比对"
      - name: "BUILDING"
        weight: 0.40
        description: "进化树构建"
      - name: "BOOTSTRAPPING"
        weight: 0.20
        description: "Bootstrap评估"
      - name: "FORMATTING"
        weight: 0.05
        description: "结果格式化"

# ─────────────────────────────────────────────
# 工具路径 (Docker内路径)
# ─────────────────────────────────────────────
tools:
  mafft:
    binary: "/opt/biotools/mafft/bin/mafft"
    version: "7.525"
    threads_flag: "--thread"
    default_mode: "auto"
    modes:
      FFT_NS_1: "--retree 1"
      FFT_NS_2: "--retree 2"
      L_INS_i: "--localpair --maxiterate 1000"
      G_INS_i: "--genafpair --maxiterate 1000"
      E_INS_i: "--ep 0 --genafpair --maxiterate 1000"
  
  clustalomega:
    binary: "/opt/biotools/clustalo/bin/clustalo"
    version: "1.2.4"
    threads_flag: "--threads"
  
  muscle5:
    binary: "/opt/biotools/muscle5/bin/muscle"
    version: "5.1.0"
    default_iterations: 16
  
  fasttree:
    binary: "/opt/biotools/fasttree/bin/FastTree"
    version: "2.1.11"
    mp_binary: "/opt/biotools/fasttree/bin/FastTreeMP"
  
  iqtree2:
    binary: "/opt/biotools/iqtree2/bin/iqtree2"
    version: "2.2.2.7"
    threads_flag: "-T"
    model_finder: true
    ultrafast_bootstrap: true
  
  mrbayes:
    binary: "/opt/biotools/mrbayes/bin/mb"
    version: "3.2.7"
    default_ngen: 1000000
    default_nchains: 4
    default_burnin_fraction: 0.25
  
  phyml:
    binary: "/opt/biotools/phyml/bin/phyml"
    version: "3.3.20220408"

# ─────────────────────────────────────────────
# 输出配置
# ─────────────────────────────────────────────
output:
  default_formats: ["newick", "statistics"]
  available_formats:
    - key: "newick"
      ext: ".nwk"
      mime: "text/plain"
      description: "Newick标准格式"
    - key: "nexus"
      ext: ".nex"
      mime: "text/plain"
      description: "NEXUS格式"
    - key: "phyloxml"
      ext: ".xml"
      mime: "application/xml"
      description: "PhyloXML格式"
    - key: "statistics"
      ext: ".stats.json"
      mime: "application/json"
      description: "统计信息JSON"
  
  # 可视化数据 (供前端渲染)
  visualization:
    enabled: true
    generate_json: true               # D3.js/Phylocanvas兼容JSON
    generate_nhx: false               # NHX格式(含注释)
```

### 5.3 工具注册 `tools_setting.yaml`

```yaml
# tool_configs/tools_setting.yaml (新增条目)
- key: "phylogenetic-tree"
  title: "系统发育树构建"
  description: "多序列比对与系统发育分析，支持NJ/UPGMA/最大似然/贝叶斯推断"
  icon: "GitBranchOutline"           # Naive UI 图标
  gradient: "linear-gradient(135deg, #1890FF 0%, #36CFC9 100%)"
  route: "/tools/phylogenetic-tree"
  enabled: true
  order: 70                          # 在工具列表中的排序位置
  config_dir: "tool_configs/phylogenetic-tree"
  category: "evolution"              # 工具分类
  tags: ["phylogenetics", "MSA", "alignment", "tree", "evolution"]
```

### 5.4 预配置场景

```yaml
# tool_configs/phylogenetic-tree/presets/16s-rrna.yaml
# 16S rRNA 细菌系统发育 — 预配置

preset:
  name: "16S rRNA 细菌系统发育"
  description: "基于16S rRNA基因序列的细菌分类与系统发育分析"
  tags: ["16S", "bacteria", "taxonomy", "rRNA"]
  
  # 推荐参数
  recommended:
    alignment_tool: "mafft"
    alignment_mode: "L_INS_i"         # 高精度局部比对
    tree_method: "iqtree"
    substitution_model: "auto"         # IQ-TREE ModelFinder自动选择
    bootstrap_enabled: true
    bootstrap_type: "ultrafast"
    bootstrap_replicates: 1000
    sequence_type: "dna"
  
  # 进化模型偏好（ModelFinder约束）
  model_preferences:
    - "GTR+G+I"                       # 通用时间可逆模型
    - "HKY+G+I"                       # Hasegawa-Kishino-Yano
    - "SYM+G+I"                       # 对称模型
  
  # 参考数据
  references:
    silva_db: "https://www.arb-silva.de/"
    greengenes_db: "http://greengenes.secondgenome.com/"
  
  # 注释
  notes: |
    16S rRNA是细菌系统发育分析的金标准分子标记。
    推荐使用L-INS-i模式进行比对，以确保保守区域的高精度对齐。
    对于超过500条序列的大规模分析，建议切换为MAFFT FFT-NS-2或ClustalOmega。
```

```yaml
# tool_configs/phylogenetic-tree/presets/cov-spike.yaml
# 冠状病毒刺突蛋白 — 预配置

preset:
  name: "冠状病毒刺突蛋白进化分析"
  description: "SARS-CoV-2及相关冠状病毒刺突蛋白序列的进化关系分析"
  tags: ["SARS-CoV-2", "spike", "coronavirus", "protein"]
  
  recommended:
    alignment_tool: "mafft"
    alignment_mode: "L_INS_i"
    tree_method: "iqtree"
    substitution_model: "auto"
    bootstrap_enabled: true
    bootstrap_type: "ultrafast"
    bootstrap_replicates: 1000
    sequence_type: "protein"
  
  model_preferences:
    - "LG+G4+F"                       # Le-Gascuel + Gamma
    - "WAG+G4+F"                      # Whelan-And-Goldman
    - "JTT+G4+F"                      # Jones-Taylor-Thornton
  
  notes: |
    冠状病毒刺突蛋白进化速度快，建议关注高变区域(RBD)。
    蛋白质序列分析推荐LG+G模型。
    如需分析密码子偏好性，可切换为DNA模式分析全长S基因。
```

```yaml
# tool_configs/phylogenetic-tree/presets/housekeeping-genes.yaml
# 持家基因家族 — 预配置

preset:
  name: "持家基因家族系统发育"
  description: "基于持家基因(如gapA, gyrB, rpoB)的多基因座系统发育分析"
  tags: ["housekeeping", "multilocus", "MLSA", "bacteria"]
  
  recommended:
    alignment_tool: "muscle5"
    alignment_mode: null              # MUSCLE5无模式选项
    tree_method: "iqtree"
    substitution_model: "auto"
    bootstrap_enabled: true
    bootstrap_type: "ultrafast"
    bootstrap_replicates: 1000
    sequence_type: "dna"
  
  model_preferences:
    - "GTR+G+I"
    - "GTR+G"
  
  notes: |
    多基因座序列分型(MLSA)推荐MUSCLE5以获得最高比对精度。
    各基因座应分别比对后串联(concatenate)，再进行树构建。
    本工具暂不支持自动串联，需用户预先处理。
```

### 5.5 默认参数配置 `defaults.yaml`

```yaml
# tool_configs/phylogenetic-tree/defaults.yaml

defaults:
  # 快速分析预设 (速度优先)
  quick:
    description: "快速预览分析"
    alignment_tool: "mafft"
    alignment_mode: "FFT_NS_2"
    tree_method: "fasttree"
    substitution_model: "GTR"
    bootstrap_enabled: false
    output_formats: ["newick"]
    threads: 4
    estimated_time: "< 1分钟 (100条序列)"
  
  # 标准分析预设 (精度与速度平衡)
  standard:
    description: "标准系统发育分析"
    alignment_tool: "mafft"
    alignment_mode: "auto"
    tree_method: "iqtree"
    substitution_model: "auto"
    bootstrap_enabled: true
    bootstrap_type: "ultrafast"
    bootstrap_replicates: 1000
    output_formats: ["newick", "nexus", "statistics"]
    threads: 4
    estimated_time: "5-30分钟 (100条序列)"
  
  # 高精度分析预设 (精度优先)
  accurate:
    description: "高精度系统发育分析"
    alignment_tool: "muscle5"
    alignment_mode: null
    tree_method: "iqtree"
    substitution_model: "auto"
    bootstrap_enabled: true
    bootstrap_type: "ultrafast"
    bootstrap_replicates: 5000
    output_formats: ["newick", "nexus", "phyloxml", "statistics"]
    threads: 8
    estimated_time: "30分钟-2小时 (100条序列)"
  
  # 贝叶斯推断预设
  bayesian:
    description: "贝叶斯推断分析"
    alignment_tool: "mafft"
    alignment_mode: "L_INS_i"
    tree_method: "mrbayes"
    substitution_model: "GTR"
    bootstrap_enabled: false           # MrBayes使用后验概率
    mrbayes_ngen: 1000000
    mrbayes_nchains: 4
    mrbayes_burnin: 0.25
    output_formats: ["newick", "nexus", "statistics"]
    threads: 4
    estimated_time: "2-8小时 (100条序列)"
```

### 5.6 参数配置加载器 (Python)

```python
# utils/phylo_config.py
"""
系统发育树工具 YAML 配置加载器
"""
import os
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

# 配置目录
CONFIG_DIR = Path("tool_configs/phylogenetic-tree")
PRESETS_DIR = CONFIG_DIR / "presets"


@dataclass
class PhyloConfig:
    """解析后的配置对象"""
    meta: Dict
    features: Dict
    input_limits: Dict
    execution: Dict
    tools: Dict
    output: Dict
    
    @classmethod
    def load(cls) -> "PhyloConfig":
        """加载主配置"""
        config_path = CONFIG_DIR / "config.yaml"
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return cls(
            meta=data.get("meta", {}),
            features=data.get("features", {}),
            input_limits=data.get("input_limits", {}),
            execution=data.get("execution", {}),
            tools=data.get("tools", {}),
            output=data.get("output", {}),
        )
    
    def get_tool_path(self, tool_name: str) -> Optional[str]:
        """获取工具二进制路径"""
        tool = self.tools.get(tool_name)
        return tool.get("binary") if tool else None
    
    def get_tool_version(self, tool_name: str) -> Optional[str]:
        """获取工具版本"""
        tool = self.tools.get(tool_name)
        return tool.get("version") if tool else None
    
    def get_preset(self, preset_name: str) -> Optional[Dict]:
        """加载预配置场景"""
        preset_path = PRESETS_DIR / f"{preset_name}.yaml"
        if not preset_path.exists():
            return None
        with open(preset_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data.get("preset")
    
    def list_presets(self) -> List[Dict]:
        """列出所有可用预配置"""
        presets = []
        for f in PRESETS_DIR.glob("*.yaml"):
            with open(f, "r", encoding="utf-8") as fp:
                data = yaml.safe_load(fp)
            preset = data.get("preset", {})
            presets.append({
                "key": f.stem,
                "name": preset.get("name", f.stem),
                "description": preset.get("description", ""),
                "tags": preset.get("tags", []),
            })
        return presets
    
    def get_defaults(self, preset_key: str = "standard") -> Dict:
        """获取默认参数预设"""
        defaults_path = CONFIG_DIR / "defaults.yaml"
        with open(defaults_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data.get("defaults", {}).get(preset_key, {})
    
    def validate_params(self, params: Dict) -> tuple[bool, List[str]]:
        """
        验证参数组合合法性
        
        Returns:
            (是否合法, 错误信息列表)
        """
        errors = []
        
        # 验证MSA工具
        alignment_tool = params.get("alignment_tool")
        valid_tools = list(self.tools.keys())
        if alignment_tool and alignment_tool not in valid_tools:
            errors.append(f"不支持的比对工具: {alignment_tool}")
        
        # 验证树构建方法
        tree_method = params.get("tree_method")
        # 树方法需要额外验证
        
        # 验证序列数限制
        seq_count = params.get("sequence_count", 0)
        if seq_count > self.input_limits.get("max_sequences", 5000):
            errors.append(f"序列数 {seq_count} 超过上限")
        
        # 验证Bootstrap
        if params.get("bootstrap_enabled"):
            replicates = params.get("bootstrap_replicates", 0)
            if replicates < 100 or replicates > 10000:
                errors.append("Bootstrap重复次数需在100-10000之间")
        
        return len(errors) == 0, errors


# 全局配置实例（单例）
_phylo_config: Optional[PhyloConfig] = None

def get_phylo_config() -> PhyloConfig:
    """获取全局配置（懒加载）"""
    global _phylo_config
    if _phylo_config is None:
        _phylo_config = PhyloConfig.load()
    return _phylo_config
```

---

## 6. Docker 镜像策略

### 6.1 镜像架构决策

**结论: 采用「单镜像 + 分层构建」策略**

```
┌─────────────────────────────────────────────────────────────────────┐
│                    omichub/phylo-toolkit:latest                      │
│                     (系统发育工具套件镜像)                            │
├─────────────────────────────────────────────────────────────────────┤
│  Layer 4: 应用层 (OmicHub层)                                        │
│  - Python 3.11 + FastAPI + Celery                                   │
│  - Biopython, DendroPy, Phylo, ETE3                                │
│  - OmicHub任务执行框架                                               │
├─────────────────────────────────────────────────────────────────────┤
│  Layer 3: 系统发育工具层                                            │
│  - MAFFT 7.525, ClustalOmega 1.2.4, MUSCLE5 5.1                   │
│  - FastTree 2.1.11, IQ-TREE 2.2.2.7, MrBayes 3.2.7                │
│  - PHYLIP 3.697                                                      │
├─────────────────────────────────────────────────────────────────────┤
│  Layer 2: 科学计算基础层                                            │
│  - BLAST+, HMMER                                                     │
│  - R 4.3 + ape, phangorn packages                                    │
│  - OpenMP, MPI (多线程支持)                                          │
├─────────────────────────────────────────────────────────────────────┤
│  Layer 1: 基础镜像层                                                │
│  - ubuntu:22.04 / condaforge/mambaforge                              │
│  - build-essential, gcc, g++, make, cmake                           │
│  - libopenmpi-dev, libgomp1                                          │
└─────────────────────────────────────────────────────────────────────┘
```

### 6.2 Dockerfile

```dockerfile
# ============================================================
# OmicHub 系统发育工具套件 Docker 镜像
# 构建: docker build -t omichub/phylo-toolkit:1.0.0 .
# ============================================================
FROM condaforge/mambaforge:23.11.0-0 AS base

LABEL maintainer="OmicHub Team <bioinfo@omichub.org>"
LABEL description="Phylogenetic analysis toolkit for OmicHub platform"
LABEL version="1.0.0"

# ── 基础环境 ──
ENV DEBIAN_FRONTEND=noninteractive
ENV CONDA_DEFAULT_ENV=phylo
ENV PATH=/opt/conda/envs/phylo/bin:$PATH

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    gfortran \
    make \
    cmake \
    wget \
    curl \
    libopenmpi-dev \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# ── 创建Conda环境 ──
RUN mamba create -n phylo python=3.11 -y

# ── Layer 2: 科学计算基础 ──
RUN mamba install -n phylo -c bioconda -c conda-forge \
    biopython=1.83 \
    numpy=1.26 \
    scipy=1.12 \
    pandas=2.2 \
    dendropy=4.6 \
    ete3=3.1 \
    -y && mamba clean -a -y

# ── Layer 3: 多序列比对工具 ──
RUN mamba install -n phylo -c bioconda \
    mafft=7.525 \
    clustalo=1.2.4 \
    muscle=5.1 \
    -y && mamba clean -a -y

# ── Layer 3: 树构建工具 ──
RUN mamba install -n phylo -c bioconda \
    fasttree=2.1.11 \
    iqtree=2.2.2.7 \
    mrbayes=3.2.7 \
    phylip=3.697 \
    -y && mamba clean -a -y

# ── Layer 3: 辅助工具 ──
RUN mamba install -n phylo -c bioconda \
    seqkit=2.7 \
    newick-utils=1.6 \
    -y && mamba clean -a -y

# ── Layer 4: Python依赖 ──
COPY requirements-phylo.txt /tmp/
RUN /opt/conda/envs/phylo/bin/pip install --no-cache-dir \
    -r /tmp/requirements-phylo.txt

# ── 工作目录和权限 ──
WORKDIR /workspace
RUN mkdir -p /workspace/input /workspace/output /workspace/temp \
    && chmod 777 /workspace -R

# ── 健康检查 ──
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import Bio; print('OK')" || exit 1

# ── 入口 ──
ENTRYPOINT ["/opt/conda/envs/phylo/bin/python"]
CMD ["--version"]
```

### 6.3 Docker Compose 服务配置

```yaml
# docker-compose.phylo.yml
version: "3.8"

services:
  # ── 系统发育树构建 Worker ──
  phylo-worker:
    image: omichub/phylo-toolkit:1.0.0
    container_name: omichub-phylo-worker
    restart: unless-stopped
    
    # Celery Worker 启动
    command: >
      celery -A omichub.celery_app worker
      -Q phylo_tree
      -n phylo@%h
      --concurrency=2
      --prefetch-multiplier=1
      --loglevel=info
    
    # 资源限制
    deploy:
      resources:
        limits:
          cpus: '8.0'
          memory: 16G
        reservations:
          cpus: '2.0'
          memory: 4G
    
    # 环境变量
    environment:
      - CELERY_BROKER_URL=redis://redis:6379/0
      - CELERY_RESULT_BACKEND=redis://redis:6379/1
      - OMP_NUM_THREADS=4
      - OPENBLAS_NUM_THREADS=4
      - MKL_NUM_THREADS=4
    
    # 数据卷
    volumes:
      - /data/omichub/uploads:/data/uploads:ro
      - /data/omichub/results:/data/results:rw
      - /data/omichub/temp:/tmp:rw
    
    # 网络
    networks:
      - omichub-backend
    
    # 健康检查
    healthcheck:
      test: ["CMD", "celery", "-A", "omichub.celery_app", "inspect", "ping"]
      interval: 30s
      timeout: 10s
      retries: 3

  # ── 高内存 Worker (MrBayes/IQ-TREE大任务) ──
  phylo-worker-highmem:
    image: omichub/phylo-toolkit:1.0.0
    container_name: omichub-phylo-worker-highmem
    restart: unless-stopped
    
    command: >
      celery -A omichub.celery_app worker
      -Q phylo_tree_highmem
      -n phylo-highmem@%h
      --concurrency=1
      --prefetch-multiplier=1
      --loglevel=info
    
    deploy:
      resources:
        limits:
          cpus: '16.0'
          memory: 32G
        reservations:
          cpus: '4.0'
          memory: 8G
    
    environment:
      - CELERY_BROKER_URL=redis://redis:6379/0
      - CELERY_RESULT_BACKEND=redis://redis:6379/1
      - OMP_NUM_THREADS=8
    
    volumes:
      - /data/omichub/uploads:/data/uploads:ro
      - /data/omichub/results:/data/results:rw
      - /data/omichub/temp:/tmp:rw
    
    networks:
      - omichub-backend

networks:
  omichub-backend:
    external: true
```

### 6.4 工具版本锁定策略

| 工具 | 锁定版本 | 锁定方式 | 升级策略 |
|------|---------|---------|---------|
| MAFFT | 7.525 | Conda pin | 半年检查新版，验证后升级 |
| ClustalOmega | 1.2.4 | Conda pin | 随bioconda更新 |
| MUSCLE5 | 5.1.0 | Conda pin | 大版本更新时评估 |
| FastTree | 2.1.11 | Conda pin | 稳定版本，不频繁升级 |
| IQ-TREE | 2.2.2.7 | Conda pin | 关注新版本功能发布 |
| MrBayes | 3.2.7 | Conda pin | 稳定版本 |
| Biopython | 1.83 | pip pin | 关注新版本兼容性 |

```python
# 版本检查工具 (CI/CD中运行)
# scripts/check_tool_versions.py

TOOL_VERSIONS = {
    "mafft": {"current": "7.525", "latest_check": "bioconda"},
    "clustalo": {"current": "1.2.4", "latest_check": "bioconda"},
    "muscle": {"current": "5.1", "latest_check": "bioconda"},
    "fasttree": {"current": "2.1.11", "latest_check": "bioconda"},
    "iqtree": {"current": "2.2.2.7", "latest_check": "github"},
    "mrbayes": {"current": "3.2.7", "latest_check": "github"},
}

def check_updates():
    """检查工具更新，生成报告"""
    # 实现略，调用各工具API/仓库检查最新版本
    pass
```

### 6.5 资源限制策略

```python
# utils/resource_manager.py

RESOURCE_PROFILES = {
    # 根据序列数量和长度选择资源配置
    "small": {
        # ≤100条序列, ≤2000bp
        "cpu": 2,
        "memory_mb": 2048,
        "timeout": 300,
        "queue": "phylo_tree",
    },
    "medium": {
        # 100-1000条序列, ≤5000bp
        "cpu": 4,
        "memory_mb": 8192,
        "timeout": 1800,
        "queue": "phylo_tree",
    },
    "large": {
        # 1000-5000条序列, ≤10000bp
        "cpu": 8,
        "memory_mb": 16384,
        "timeout": 7200,
        "queue": "phylo_tree",
    },
    "xlarge": {
        # >5000条 或 MrBayes长时间运行
        "cpu": 16,
        "memory_mb": 32768,
        "timeout": 28800,  # 8小时
        "queue": "phylo_tree_highmem",
    },
}

def select_resource_profile(sequence_count: int, 
                            avg_length: int,
                            tree_method: str) -> dict:
    """根据任务规模选择合适的资源配置"""
    # MrBayes始终使用高内存配置
    if tree_method == "mrbayes":
        return RESOURCE_PROFILES["xlarge"]
    
    # 根据序列数和长度选择
    if sequence_count <= 100 and avg_length <= 2000:
        return RESOURCE_PROFILES["small"]
    elif sequence_count <= 1000 and avg_length <= 5000:
        return RESOURCE_PROFILES["medium"]
    elif sequence_count <= 5000 and avg_length <= 10000:
        return RESOURCE_PROFILES["large"]
    else:
        return RESOURCE_PROFILES["xlarge"]
```

---

## 7. 输出格式规范

### 7.1 Newick 格式 (必输出)

```
Newick格式是系统发育树的标准文本表示，所有树构建工具均支持。

格式示例:
((A:0.1,B:0.2):0.3,(C:0.4,D:0.5):0.6);

带Bootstrap支持度:
((A:0.1,B:0.2)95:0.3,(C:0.4,D:0.5)88:0.6)100;

扩展Newick (注释):
((A[&&NHX:species=Homo_sapiens]:0.1,
  B[&&NHX:species=Pan_troglodytes]:0.2):0.3,
 (C[&&NHX:species=Mus_musculus]:0.4,
  D[&&NHX:species=Rattus_norvegicus]:0.5):0.6);
```

### 7.2 NEXUS 格式 (可选)

```
#NEXUS
Begin Taxa;
  Dimensions NTax=4;
  TaxLabels A B C D;
End;

Begin Trees;
  Tree tree1 = ((A:0.1,B:0.2):0.3,(C:0.4,D:0.5):0.6);
End;
```

### 7.3 PhyloXML 格式 (可选)

```xml
<?xml version="1.0" encoding="UTF-8"?>
<phyloxml xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
          xsi:schemaLocation="http://www.phyloxml.org http://www.phyloxml.org/1.10/phyloxml.xsd"
          xmlns="http://www.phyloxml.org">
  <phylogeny rooted="true">
    <name>Phylogenetic Tree</name>
    <clade>
      <branch_length>0</branch_length>
      <confidence type="bootstrap">100</confidence>
      <clade>
        <branch_length>0.3</branch_length>
        <confidence type="bootstrap">95</confidence>
        <clade>
          <name>A</name>
          <branch_length>0.1</branch_length>
        </clade>
        <clade>
          <name>B</name>
          <branch_length>0.2</branch_length>
        </clade>
      </clade>
      <clade>
        <branch_length>0.6</branch_length>
        <confidence type="bootstrap">88</confidence>
        <clade>
          <name>C</name>
          <branch_length>0.4</branch_length>
        </clade>
        <clade>
          <name>D</name>
          <branch_length>0.5</branch_length>
        </clade>
      </clade>
    </clade>
  </phylogeny>
</phyloxml>
```

### 7.4 统计信息 JSON 格式

```json
{
  "tree_summary": {
    "total_tips": 100,
    "total_internal_nodes": 98,
    "total_nodes": 198,
    "total_branches": 197,
    "is_rooted": true,
    "is_bifurcating": true,
    "has_branch_lengths": true,
    "has_bootstrap_support": true
  },
  "branch_statistics": {
    "total_tree_length": 2.4567,
    "mean_branch_length": 0.0125,
    "median_branch_length": 0.0089,
    "max_branch_length": 0.1876,
    "min_branch_length": 0.0001,
    "std_branch_length": 0.0213
  },
  "bootstrap_statistics": {
    "replicates": 1000,
    "mean_support": 87.5,
    "median_support": 92.0,
    "min_support": 45.0,
    "max_support": 100.0,
    "branches_above_95": 67,
    "branches_above_70": 89,
    "branches_below_50": 3
  },
  "tip_statistics": {
    "mean_tip_distance": 0.2345,
    "max_tip_distance": 0.4567,
    "min_tip_distance": 0.1234,
    "longest_tip_name": "Homo_sapiens_chr1_gene_ABC123",
    "tip_name_max_length": 35
  },
  "method_info": {
    "alignment_tool": "mafft",
    "alignment_version": "7.525",
    "tree_method": "iqtree",
    "tree_version": "2.2.2.7",
    "substitution_model": "GTR+F+I+G4",
    "bootstrap_type": "UFBoot",
    "bootstrap_replicates": 1000,
    "aic_score": 45678.23,
    "aic_c_score": 45689.45,
    "bic_score": 45901.67,
    "log_likelihood": -22834.11
  },
  "execution_info": {
    "started_at": "2025-07-01T10:00:00Z",
    "completed_at": "2025-07-01T10:05:23Z",
    "duration_seconds": 323.45,
    "phases_completed": ["alignment", "tree_building", "bootstrap", "formatting"],
    "resource_usage": {
      "peak_memory_mb": 2048,
      "cpu_threads": 4
    }
  }
}
```

### 7.5 前端可视化 JSON 格式

```json
{
  "visualization": {
    "format": "hierarchy",
    "root": {
      "name": "root",
      "branch_length": 0,
      "bootstrap": 100,
      "children": [
        {
          "name": "",
          "branch_length": 0.3,
          "bootstrap": 95,
          "children": [
            {"name": "A", "branch_length": 0.1, "bootstrap": null},
            {"name": "B", "branch_length": 0.2, "bootstrap": null}
          ]
        },
        {
          "name": "",
          "branch_length": 0.6,
          "bootstrap": 88,
          "children": [
            {"name": "C", "branch_length": 0.4, "bootstrap": null},
            {"name": "D", "branch_length": 0.5, "bootstrap": null}
          ]
        }
      ]
    }
  }
}
```

### 7.6 格式转换工具代码

```python
# utils/phylo_format.py
"""
系统发育树格式转换工具
支持: Newick <-> NEXUS <-> PhyloXML
"""
from Bio import Phylo
from io import StringIO
from typing import Optional
import json


def convert_format(input_file: str, output_file: str, 
                   output_format: str,
                   input_format: str = "newick",
                   alignment_file: Optional[str] = None) -> str:
    """
    转换系统发育树格式
    
    Args:
        input_file: 输入树文件路径
        output_file: 输出文件路径
        output_format: 输出格式 (newick/nexus/phyloxml/json)
        input_format: 输入格式
        alignment_file: 可选的比对文件(NEXUS输出需要)
    
    Returns:
        输出文件路径
    """
    # 读取树
    trees = list(Phylo.parse(input_file, input_format))
    
    if output_format == "newick":
        Phylo.write(trees, output_file, "newick")
        
    elif output_format == "nexus":
        if alignment_file:
            # 需要比对数据生成完整的NEXUS
            _write_nexus_with_alignment(trees, alignment_file, output_file)
        else:
            Phylo.write(trees, output_file, "nexus")
            
    elif output_format == "phyloxml":
        Phylo.write(trees, output_file, "phyloxml")
        
    elif output_format == "json":
        # 转换为D3.js层次结构JSON
        tree = trees[0]
        hierarchy = _tree_to_hierarchy(tree)
        with open(output_file, "w") as f:
            json.dump(hierarchy, f, indent=2)
    
    return output_file


def _tree_to_hierarchy(tree) -> dict:
    """将Biopython树转换为D3.js层次结构"""
    def node_to_dict(clade):
        result = {
            "name": clade.name or "",
            "branch_length": round(float(clade.branch_length or 0), 6),
        }
        # 提取Bootstrap (从confidence或name中)
        if clade.confidences:
            result["bootstrap"] = clade.confidences[0].value
        
        if clade.clades:
            result["children"] = [node_to_dict(c) for c in clade.clades]
        
        return result
    
    return {"visualization": {"format": "hierarchy", "root": node_to_dict(tree.root)}}


def compute_tree_statistics(tree_file: str, input_format: str = "newick") -> dict:
    """
    计算系统发育树的统计信息
    
    Returns:
        包含各类统计指标的字典
    """
    from Bio import Phylo
    import statistics
    
    tree = Phylo.read(tree_file, input_format)
    
    # 收集所有分支长度
    branch_lengths = []
    tip_distances = []
    bootstrap_values = []
    tip_count = 0
    internal_count = 0
    
    def traverse(clade, root_dist=0):
        nonlocal tip_count, internal_count
        
        if clade.is_terminal():
            tip_count += 1
            tip_distances.append(root_dist)
        else:
            internal_count += 1
            # 收集Bootstrap
            if clade.confidences:
                bootstrap_values.append(clade.confidences[0].value)
        
        bl = clade.branch_length or 0
        branch_lengths.append(bl)
        
        for child in clade.clades:
            traverse(child, root_dist + bl)
    
    traverse(tree.root)
    
    # 计算统计量
    total_branches = len(branch_lengths) - 1  # 排除根节点的branch_length(通常为0或None)
    
    valid_bl = [bl for bl in branch_lengths if bl is not None and bl > 0]
    
    stats = {
        "tree_summary": {
            "total_tips": tip_count,
            "total_internal_nodes": internal_count,
            "total_nodes": tip_count + internal_count,
            "total_branches": total_branches,
            "is_rooted": bool(tree.root.branch_length is not None),
            "is_bifurcating": all(len(n.clades) in [0, 2] for n in tree.get_nonterminals()),
            "has_branch_lengths": len(valid_bl) > 0,
            "has_bootstrap_support": len(bootstrap_values) > 0,
        },
        "branch_statistics": {
            "total_tree_length": round(sum(valid_bl), 6),
            "mean_branch_length": round(statistics.mean(valid_bl), 6) if valid_bl else 0,
            "median_branch_length": round(statistics.median(valid_bl), 6) if valid_bl else 0,
            "max_branch_length": round(max(valid_bl), 6) if valid_bl else 0,
            "min_branch_length": round(min(valid_bl), 6) if valid_bl else 0,
            "std_branch_length": round(statistics.stdev(valid_bl), 6) if len(valid_bl) > 1 else 0,
        },
    }
    
    # Bootstrap统计
    if bootstrap_values:
        stats["bootstrap_statistics"] = {
            "mean_support": round(statistics.mean(bootstrap_values), 2),
            "median_support": round(statistics.median(bootstrap_values), 2),
            "min_support": round(min(bootstrap_values), 2),
            "max_support": round(max(bootstrap_values), 2),
            "branches_above_95": sum(1 for v in bootstrap_values if v >= 95),
            "branches_above_70": sum(1 for v in bootstrap_values if v >= 70),
            "branches_below_50": sum(1 for v in bootstrap_values if v < 50),
        }
    
    # Tip距离统计
    if tip_distances:
        stats["tip_statistics"] = {
            "mean_tip_distance": round(statistics.mean(tip_distances), 6),
            "max_tip_distance": round(max(tip_distances), 6),
            "min_tip_distance": round(min(tip_distances), 6),
        }
    
    return stats
```

---

## 附录

### A. 完整的数据流时序图

```
用户                          前端(Vue3)              FastAPI              Celery              Worker
 │                              │                      │                    │                    │
 │  ① 上传FASTA文件             │                      │                    │                    │
 │ ──────────────────────────▶  │                      │                    │                    │
 │                              │  POST /upload        │                    │                    │
 │                              │ ──────────────────▶  │                    │                    │
 │                              │                      │  保存/验证文件      │                    │
 │                              │  返回file_id         │                    │                    │
 │                              │ ◀──────────────────  │                    │                    │
 │  返回文件ID和序列信息        │                      │                    │                    │
 │ ◀──────────────────────────  │                      │                    │                    │
 │                              │                      │                    │                    │
 │  ② 选择参数(工具/模型/Bootstrap)                     │                    │                    │
 │  ③ 点击"构建系统发育树"      │                      │                    │                    │
 │ ──────────────────────────▶  │                      │                    │                    │
 │                              │  POST /submit        │                    │                    │
 │                              │  {file_id, method...}│                    │                    │
 │                              │ ──────────────────▶  │                    │                    │
 │                              │                      │  参数校验           │                    │
 │                              │                      │  投递Celery任务     │                    │
 │                              │                      │ ─────────────────▶ │                    │
 │                              │  返回task_id         │                    │  领取任务           │
 │                              │ ◀──────────────────  │                    │ ───────────────▶   │
 │  显示任务ID,开始轮询         │                      │                    │                    │
 │ ◀──────────────────────────  │                      │                    │                    │
 │                              │                      │                    │                    │
 │  显示进度条"比对中 15%"      │                      │                    │                    │
 │ ◀──────────────────────────  │  GET /status (轮询)  │                    │  更新进度           │
 │                              │ ──────────────────▶  │ ◀───────────────   │ ◀──────────────    │
 │                              │ ◀──────────────────  │                    │                    │
 │  显示"构建树 45%"            │                      │                    │                    │
 │ ◀──────────────────────────  │  GET /status (轮询)  │                    │  更新进度           │
 │                              │ ──────────────────▶  │ ◀───────────────   │ ◀──────────────    │
 │                              │ ◀──────────────────  │                    │                    │
 │  显示"Bootstrap 80%"         │                      │                    │                    │
 │ ◀──────────────────────────  │  GET /status (轮询)  │                    │  更新进度           │
 │                              │ ──────────────────▶  │ ◀───────────────   │ ◀──────────────    │
 │                              │ ◀──────────────────  │                    │                    │
 │                              │                      │                    │  任务完成           │
 │                              │                      │  结果存入Redis      │ ───────────────    │
 │  显示完成,展示结果链接       │                      │ ◀──────────────    │                    │
 │ ◀──────────────────────────  │  返回SUCCESS         │                    │                    │
 │                              │ ◀──────────────────  │                    │                    │
 │                              │                      │                    │                    │
 │  ④ 点击"下载Newick"          │                      │                    │                    │
 │ ──────────────────────────▶  │                      │                    │                    │
 │                              │  GET /download       │                    │                    │
 │                              │ ──────────────────▶  │                    │                    │
 │  下载.nwk文件                │                      │  读取结果文件       │                    │
 │ ◀──────────────────────────  │ ◀──────────────────  │                    │                    │
 │                              │                      │                    │                    │
 │  ⑤ 点击"查看统计信息"        │                      │                    │                    │
 │ ──────────────────────────▶  │                      │                    │                    │
 │                              │  GET /result?fmt=json│                    │                    │
 │                              │ ──────────────────▶  │                    │                    │
 │  展示统计面板(AIC/Bootstrap) │                      │  读取stats.json     │                    │
 │ ◀──────────────────────────  │ ◀──────────────────  │                    │                    │
 │                              │                      │                    │                    │
```

### B. 错误码定义

| 错误码 | 说明 | 触发场景 |
|--------|------|---------|
| PHYLO_001 | 文件格式不支持 | 上传非FASTA/Phylip/NEXUS文件 |
| PHYLO_002 | 序列数量超限 | 超过5000条序列 |
| PHYLO_003 | 序列长度过长 | 单条序列超过50000bp |
| PHYLO_004 | 参数组合不合法 | 如MrBayes+Bootstrap |
| PHYLO_005 | MSA执行失败 | 比对工具返回非零退出码 |
| PHYLO_006 | 树构建失败 | 树构建工具执行失败 |
| PHYLO_007 | 任务超时 | 超过2小时未完成 |
| PHYLO_008 | 内存不足 | 容器OOM被Kill |
| PHYLO_009 | 模型选择失败 | ModelFinder无法确定最佳模型 |
| PHYLO_010 | 结果文件缺失 | 输出文件生成失败 |

### C. 与前端组件对接说明

```javascript
// 前端组件使用的数据结构

// 1. 进度条组件
const progressProps = {
  phase: "ALIGNING" | "BUILDING" | "BOOTSTRAPPING" | "FORMATTING",
  percent: 0-100,
  message: "当前步骤描述",
  phaseLabels: {
    ALIGNING: "多序列比对",
    BUILDING: "构建进化树", 
    BOOTSTRAPPING: "Bootstrap评估",
    FORMATTING: "格式化结果"
  }
};

// 2. 结果展示组件
const resultProps = {
  treeData: {
    newick: "((A:0.1,B:0.2):0.3,...)",
    hierarchy: {/* D3.js JSON */}
  },
  statistics: {
    totalTips: 100,
    meanBootstrap: 87.5,
    treeLength: 2.456,
    model: "GTR+F+I+G4",
    aic: 45678.23,
    logL: -22834.11
  },
  downloadLinks: {
    newick: "/api/phylo/download/xxx/newick",
    nexus: "/api/phylo/download/xxx/nexus",
    statistics: "/api/phylo/download/xxx/statistics"
  }
};
```

### D. 目录结构总览

```
omichub/
├── tool_configs/
│   ├── tools_setting.yaml              # 全局工具注册表(新增phylo条目)
│   └── phylogenetic-tree/
│       ├── config.yaml                 # 主配置
│       ├── defaults.yaml               # 默认参数预设
│       ├── methods.yaml                # 方法详细配置
│       ├── presets/
│       │   ├── 16s-rrna.yaml
│       │   ├── cov-spike.yaml
│       │   ├── housekeeping-genes.yaml
│       │   └── protein-superfamily.yaml
│       └── docker/
│           └── resource-limits.yaml
│
├── tasks/
│   └── phylo_tree.py                   # Celery任务定义
│
├── routers/
│   └── phylo_tree.py                   # FastAPI路由
│
├── utils/
│   ├── phylo_config.py                 # YAML配置加载器
│   ├── phylo_format.py                 # 格式转换工具
│   ├── phylo_utils.py                  # MSA/树构建工具包装函数
│   └── resource_manager.py             # 资源管理
│
├── docker/
│   ├── Dockerfile.phylo                # 工具套件Dockerfile
│   └── docker-compose.phylo.yml        # Worker服务编排
│
└── scripts/
    └── check_tool_versions.py          # 工具版本检查
```

---

> **文档结束**  
> 本文档完整定义了 OmicHub 系统发育树构建工具的后端架构，涵盖从生物信息学流程到 Celery 任务调度、API 设计、YAML 配置和 Docker 部署的全链路技术方案。

