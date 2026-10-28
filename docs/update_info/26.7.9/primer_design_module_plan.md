# OmicHub 引物设计模块（PrimerForge）—— 详细实现方案

> **版本**: v1.0  
> **日期**: 2026-07-09  
> **状态**: 设计阶段，待 CC 开发  

---

## 一、模块定位与核心亮点

### 1.1 模块名称

**PrimerForge** —— 引物锻造工坊

> Slogan: *"从序列到合成，一键贯通"*

### 1.2 一句话描述

集成 Primer3 引擎的专业级引物设计工具，支持 PCR / qPCR 引物与探针设计，AI 辅助生成引物合成订单并可自动发送邮件至合成公司，同时支持详细 Excel 报告导出。

### 1.3 核心亮点（差异化卖点）

| 亮点 | 说明 |
|------|------|
| **Primer3 核心引擎** | 业界黄金标准的热力学计算，精确的 Tm、发夹、二聚体分析 |
| **PCR / qPCR 双模式** | 一键切换预设参数，qPCR 支持跨外显子设计与 TaqMan 探针 |
| **AI 合成助手** | 设计完成后，AI 自动生成引物合成订单文案，支持邮件直发合成公司 |
| **多公司邮件模板** | 内置生工生物、擎科生物、诺赛基因等主流合成公司邮件格式 |
| **序列可视化** | 在原始序列上标注引物位置、产物区域、外显子边界 |
| **专业级参数面板** | 对标 Primer3 Plus，支持热力学参数、罚分权重、高级约束 |

### 1.4 在工具箱中的位置

在「生信工具箱」中添加新卡片：

```
[引物锻造工坊 PrimerForge]
图标: 🧬（DNA双螺旋 + 锤子）
描述: 基于 Primer3 引擎的专业引物设计，支持 PCR/qPCR 与探针设计，
      AI 辅助生成合成订单并可自动邮件发送
```

---

## 二、技术架构

### 2.1 整体架构图

```
┌─────────────────────────────────────────────────────────────────────┐
│                          前端 (React + Arco Design)                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │
│  │ 参数配置面板  │  │ 序列可视化区  │  │      统计与操作栏         │  │
│  │ (左侧)        │  │ (中间上方)   │  │      (右侧)              │  │
│  └──────────────┘  └──────────────┘  └──────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                   引物设计结果表格 (中间下方)                  │  │
│  └──────────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │              AI 合成助手抽屉 / 模态框                          │  │
│  │    (引物订单生成 → 公司选择 → 邮件预览 → 一键发送)            │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     后端 API (Python FastAPI)                        │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐  │
│  │ /primer/design   │  │ /primer/blast    │  │ /primer/ai-order │  │
│  │   (Primer3-py)   │  │  (特异性验证)     │  │  (AI订单生成)    │  │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘  │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐  │
│  │ /primer/export   │  │ /primer/mail/send│  │ /primer/history  │  │
│  │   (Excel导出)    │  │  (邮件发送)      │  │  (历史记录)      │  │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
            ┌──────────┐   ┌──────────────┐  ┌─────────────┐
            │Primer3-py│   │  NCBI BLAST  │  │  AI Provider │
            │  (本地)   │   │   (远程API)  │  │  (OpenAI等)  │
            └──────────┘   └──────────────┘  └─────────────┘
```

### 2.2 技术栈选型

| 层级 | 技术 | 说明 |
|------|------|------|
| 前端 | React + Arco Design + Plotly | 与现有 OmicHub 统一，Plotly 做序列可视化 |
| 后端 | Python FastAPI | 异步高性能，与现有后端统一 |
| 引物引擎 | primer3-py (v2.0.3) | Primer3 C 引擎的 Python 绑定 |
| 特异性验证 | NCBI Primer-BLAST API / local BLAST+ | 可选远程或本地 |
| AI 服务 | OpenAI API / 本地模型 | 订单文案生成 |
| 邮件服务 | SMTP (用户自行配置) / SendGrid API | 邮件发送 |
| 导出 | openpyxl | Excel 文件生成 |

### 2.3 Primer3-py 核心依赖

```bash
# 后端 requirements.txt 新增
primer3-py>=2.0.3
biopython>=1.81
openpyxl>=3.1.0
requests>=2.31.0
```

> **注意**: primer3-py v2.0+ 相比旧版本有 API 变更，`designPrimers` → `design_primers`，`calcTm` → `calc_tm`。务必使用新 API。

---

## 三、前端界面设计

### 3.1 整体布局（专业全功能面板）

采用 **三栏式专业布局**，对标 Primer3 Plus 与 SnapGene：

```
┌──────────────────────────────────────────────────────────────────────┐
│  ← 返回工具箱    PrimerForge 引物锻造工坊         [示例数据] [?帮助]  │
├──────────────┬──────────────────────────────┬──────────────────────┤
│              │                              │                      │
│  参数配置     │    序列可视化区域              │    统计与操作栏      │
│  面板        │    (带引物标注的序列图)         │                      │
│  (左侧固定)  │                              │  ┌────────────────┐  │
│              │                              │  │ 设计统计       │  │
│ ┌──────────┐ │                              │  │ • 候选对数: 5  │  │
│ │序列输入   │ │   ┌──────────────────────┐   │  │ • 最佳评分: 98 │  │
│ │          │ │   │ 5'- ATGCGATCG...     │   │  │ • 平均Tm: 59.5°│  │
│ │[粘贴区]  │ │   │      ↑=====产物=====↓  │   │  └────────────────┘  │
│ │[上传区]  │ │   │ 3'- TACGCTAGC...     │   │                      │
│ └──────────┘ │   └──────────────────────┘   │  ┌────────────────┐  │
│              │                              │  │ 快捷操作       │  │
│ ┌──────────┐ │                              │  │ [AI合成助手]   │  │
│ │任务类型   │ │                              │  │ [导出Excel]    │  │
│ │ ○ PCR    │ │                              │  │ [保存历史]     │  │
│ │ ● qPCR   │ │                              │  └────────────────┘  │
│ │ ○ 测序   │ │                              │                      │
│ └──────────┘ │                              │  ┌────────────────┐  │
│              │                              │  │ 引物位置图     │  │
│ ┌──────────┐ │                              │  │ (迷你示意图)   │  │
│ │引物参数   │ │                              │  └────────────────┘  │
│ │ • 长度   │ │                              │                      │
│ │ • Tm     │ │                              └──────────────────────┘
│ │ • GC%    │ │
│ └──────────┘ │
│              │
│ ┌──────────┐ │     ┌──────────────────────────────────────────┐
│ │热力学参数 │ │     │         引物设计结果表格                   │
│ │ • 盐浓度 │ │     │                                          │
│ │ • DNA浓度│ │     │  # │ 正向引物      │ Tm  │ GC  │ 评分 │ 操作 │
│ └──────────┘ │     │  1 │ ATGCGATCG... │ 60° │ 55% │  98  │ [详] │
│              │     │  2 │ CGATCGATG... │ 59° │ 52% │  95  │ [详] │
│ ┌──────────┐ │     │  ...                                         │
│ │高级选项   │ │     └──────────────────────────────────────────┘
│ │ • 罚分   │ │
│ │ • 排除区 │ │
│ └──────────┘ │
│              │
│ [开始设计]   │
└──────────────┴──────────────────────────────────────────────────────┘
```

### 3.2 左侧参数配置面板（详细）

#### 3.2.1 序列输入区

```yaml
组件: Card (标题: "序列输入")
内容:
  - 序列标识符: Input (placeholder: "如: ACTB_gene")
  - 输入方式:
      - Radio: 直接粘贴 / FASTA文件上传
  - 序列文本域: TextArea
      rows: 8
      placeholder: "粘贴DNA序列 (A/T/G/C/N)，或上传FASTA文件"
  - 序列统计: 自动显示 (长度, GC%, N数量)
  - 目标区域标记:
      - 使用特殊符号标记（兼容Primer3语法）:
          - [start,length]  : 目标区域（引物产物必须覆盖）
          - <start,length>  : 排除区域（引物不能结合）
          - {start,length}  : 包含区域（引物必须在此区域内）
      - 辅助按钮: [标记目标区] [标记排除区] [清除标记]
```

#### 3.2.2 任务类型选择

```yaml
组件: Card (标题: "任务类型")
选项:
  - PCR (常规PCR):
      产物大小: 100-1000 bp
      引物长度: 18-25 mer
      Tm范围: 57-63°C
  - qPCR (实时定量PCR):
      产物大小: 80-250 bp (推荐100-150)
      引物长度: 18-24 mer
      Tm范围: 58-60°C (推荐60)
      GC%: 45-55%
      特殊选项:
        - 跨外显子设计 (自动检测或手动标记剪接位点)
        - 设计TaqMan探针 (INTERNAL OLIGO)
  - 测序引物:
      产物大小: 不适用
      单向引物设计
  - 克隆引物:
      支持添加酶切位点、保护碱基
```

#### 3.2.3 引物参数配置

```yaml
组件: Card (标题: "引物参数", 可折叠)
参数列表:
  引物长度:
    - 最优: InputNumber (default: 20)
    - 最小: InputNumber (default: 18)
    - 最大: InputNumber (default: 25)

  Tm值 (°C):
    - 最优: InputNumber (default: 60.0)
    - 最小: InputNumber (default: 57.0)
    - 最大: InputNumber (default: 63.0)
    - 最大差异: InputNumber (default: 3.0, 正负链Tm差)

  GC含量 (%):
    - 最优: InputNumber (default: 50.0)
    - 最小: InputNumber (default: 20.0)
    - 最大: InputNumber (default: 80.0)
    - 3'端GC Clamp: Switch (default: true)
      Clamp长度: InputNumber (default: 1)

  产物大小范围 (bp):
    - 最小: InputNumber (default: 100)
    - 最大: InputNumber (default: 300)

  返回引物对数:
    - Slider: 1-20 (default: 5)
```

#### 3.2.4 热力学参数

```yaml
组件: Card (标题: "热力学参数", 默认折叠, 高级)
参数:
  一价阳离子浓度 (mM): InputNumber (default: 50.0)
  二价阳离子浓度 (mM): InputNumber (default: 0.0)
  dNTP浓度 (mM): InputNumber (default: 0.0)
  DNA浓度 (nM): InputNumber (default: 50.0)
  最大连续相同碱基: InputNumber (default: 4)
  最大Poly-X长度: InputNumber (default: 5)
  盐校正公式: Select
    - 选项: SantaLucia (默认), Owczarzy, Von Ahsen
```

#### 3.2.5 高级约束与罚分

```yaml
组件: Card (标题: "高级选项", 默认折叠)
约束条件:
  自身互补性:
    - 任意位置最大: InputNumber (default: 8.00, 8bp互补)
    - 3'端最大: InputNumber (default: 3.00, 3bp互补)

  引物对互补性:
    - 任意位置最大: InputNumber (default: 8.00)
    - 3'端最大: InputNumber (default: 3.00)

  发夹结构:
    - 最大稳定性: InputNumber (default: -2.00, ΔG kcal/mol)

  3'端稳定性:
    - 最后5个碱基最大ΔG: InputNumber (default: -9.0)

罚分权重 (Weight):
  - Tm偏离权重: Slider 0-1 (default: 1.0)
  - GC%偏离权重: Slider 0-1 (default: 1.0)
  - 长度偏离权重: Slider 0-1 (default: 1.0)
  - 互补性罚分权重: Slider 0-1 (default: 1.0)
```

#### 3.2.6 探针参数 (qPCR模式显示)

```yaml
组件: Card (标题: "TaqMan探针参数", 条件显示)
参数:
  探针长度: 最优20 / 最小18 / 最大27
  探针Tm: 最优70 / 最小67 / 最大73 (比引物高5-10°C)
  探针GC%: 30-80%
  5'端避免G: Switch (default: true, G会导致淬灭)
  探针与引物最小距离: InputNumber (default: 0)
  荧光标记:
    - 5'端荧光基团: Select (FAM, VIC, HEX, ROX, CY5)
    - 3'端淬灭基团: Select (BHQ1, BHQ2, TAMRA, MGB)
```

### 3.3 中间区域 — 序列可视化

```yaml
组件: 自定义序列可视化 (基于Canvas或SVG)
功能:
  - 水平显示DNA序列 (5' → 3')
  - 正向引物: 蓝色箭头 (→) 在序列上方
  - 反向引物: 红色箭头 (←) 在序列下方
  - 产物区域: 绿色高亮背景
  - 探针 (qPCR): 黄色标记在产物区域内
  - 目标区域 [ ]: 浅绿色背景
  - 排除区域 < >: 灰色背景带斜线
  - 鼠标悬停: 显示当前位置的碱基坐标
  - 缩放: 鼠标滚轮缩放, 拖拽平移
  - 点击引物: 高亮对应引物对
```

### 3.4 右侧统计与操作栏

#### 3.4.1 设计统计卡片

```yaml
实时显示:
  - 候选引物对数: Statistic
  - 最佳评分: Statistic (带颜色: ≥90绿, ≥70黄, <70红)
  - 平均Tm: Statistic
  - 平均GC%: Statistic
  - 设计耗时: Statistic (ms)

设计诊断:
  - 如果有问题 (如序列太短, GC极端):
      Alert 提示具体原因
```

#### 3.4.2 快捷操作

```yaml
按钮组:
  - [AI合成助手]: Button (type: primary, icon: robot)
      描述: "AI生成合成订单并发送邮件"
  - [导出Excel]: Button (type: default, icon: download)
      描述: "导出详细引物报告"
  - [保存历史]: Button (type: default, icon: save)
  - [分享链接]: Button (type: default, icon: share)
```

#### 3.4.3 引物位置迷你图

```yaml
组件: 简化线性示意图
显示:
  - 整条序列的缩略表示
  - 所有候选引物对的位置标记 (彩色小条)
  - 点击标记: 主表格滚动到对应行
```

### 3.5 引物设计结果表格

```yaml
组件: Table
列定义:
  - 排名: # (带颜色: 1金, 2银, 3铜)
  - 正向引物序列: monospace字体, 可复制
  - 正向Tm: °C (带进度条背景)
  - 正向GC%: % (带进度条背景)
  - 反向引物序列: monospace字体
  - 反向Tm: °C
  - 反向GC%: %
  - 产物大小: bp
  - 综合评分: Progress (0-100)
  - 操作: [详情] [选择]

详情展开行:
  显示详细信息:
    - 正向引物: 起始位置, 长度, 序列, Tm, GC%, 稳定性
    - 反向引物: 同上
    - 热力学分析:
        - 自身任意互补: X bp
        - 自身3'端互补: X bp
        - 发夹结构: ΔG = X kcal/mol
        - 引物对任意互补: X bp
        - 引物对3'端互补: X bp
    - 预警信息: (如果有问题, 黄色/红色警示)

行操作:
  - 点击"选择": 在序列可视化区高亮此引物对
  - 点击"AI合成": 直接进入AI合成助手, 预填此引物对
```

---

## 四、后端 API 设计

### 4.1 API 端点总览

| 方法 | 路径 | 功能 |
|------|------|------|
| POST | `/api/v1/primer/design` | 执行引物设计 |
| POST | `/api/v1/primer/validate` | 验证单条引物 |
| POST | `/api/v1/primer/blast` | BLAST特异性验证 |
| POST | `/api/v1/primer/ai-order` | AI生成合成订单 |
| POST | `/api/v1/primer/mail/send` | 发送邮件到合成公司 |
| POST | `/api/v1/primer/export/excel` | 导出Excel报告 |
| GET | `/api/v1/primer/history` | 获取历史记录 |
| POST | `/api/v1/primer/history` | 保存设计到历史 |

### 4.2 核心API: /primer/design

#### 请求体 (Request)

```json
{
  "sequence_id": "ACTB_gene",
  "sequence_template": "ATGCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCG...",
  "task_type": "qPCR",

  "sequence_target": [[100, 200]],
  "sequence_excluded_region": [[50, 20]],

  "primer_parameters": {
    "opt_size": 20,
    "min_size": 18,
    "max_size": 25,
    "opt_tm": 60.0,
    "min_tm": 57.0,
    "max_tm": 63.0,
    "min_gc": 20.0,
    "max_gc": 80.0,
    "max_poly_x": 5,
    "product_size_range": [[80, 250]]
  },

  "thermodynamic_parameters": {
    "salt_monovalent": 50.0,
    "salt_divalent": 0.0,
    "dntp_conc": 0.0,
    "dna_conc": 50.0
  },

  "advanced": {
    "max_self_any": 8.00,
    "max_self_end": 3.00,
    "max_pair_any": 8.00,
    "max_pair_end": 3.00,
    "num_return": 5
  },

  "probe_parameters": {
    "pick_internal_oligo": true,
    "internal_opt_size": 20,
    "internal_min_size": 18,
    "internal_max_size": 27,
    "internal_opt_tm": 70.0,
    "internal_min_tm": 67.0,
    internal_max_tm": 73.0,
    "internal_min_gc": 30.0,
    "internal_max_gc": 80.0,
    "internal_max_poly_x": 4
  }
}
```

#### 响应体 (Response)

```json
{
  "success": true,
  "design_id": "des_20260709_abc123",
  "task_type": "qPCR",
  "runtime_ms": 245,

  "summary": {
    "total_pairs_returned": 5,
    "left_primers_considered": 1483,
    "right_primers_considered": 1493,
    "pair_explanations": "considered 148, unacceptable product size 141, ok 7"
  },

  "primer_pairs": [
    {
      "rank": 1,
      "pair_penalty": 0.12,
      "compl_any": 4.00,
      "compl_end": 2.00,

      "forward_primer": {
        "sequence": "GTAAAACGACGGCCAGT",
        "position": [100, 17],
        "length": 17,
        "tm": 59.85,
        "gc_percent": 52.9,
        "self_any": 6.00,
        "self_end": 2.00,
        "hairpin_tm": 0.0,
        "end_stability": -9.2,
        "warnings": []
      },

      "reverse_primer": {
        "sequence": "CAGGAAACAGCTATGAC",
        "position": [280, 17],
        "length": 17,
        "tm": 58.42,
        "gc_percent": 47.1,
        "self_any": 4.00,
        "self_end": 0.00,
        "hairpin_tm": 0.0,
        "end_stability": -8.4,
        "warnings": []
      },

      "probe": {
        "sequence": "CGATCGATCGATCGATCG",
        "position": [150, 18],
        "length": 18,
        "tm": 68.5,
        "gc_percent": 55.6,
        "self_any": 2.00,
        "warnings": []
      },

      "product_size": 180,
      "quality_score": 98
    }
  ],

  "sequence_visualization": {
    "sequence_length": 1000,
    "annotations": [
      {"type": "primer_forward", "start": 100, "end": 117, "label": "F1"},
      {"type": "primer_reverse", "start": 280, "end": 263, "label": "R1"},
      {"type": "product", "start": 100, "end": 280, "label": "Amplicon"},
      {"type": "probe", "start": 150, "end": 168, "label": "Probe"}
    ]
  }
}
```

### 4.3 后端 Primer3-py 调用代码

```python
# backend/services/primer_design.py

import primer3
from typing import List, Dict, Optional
from dataclasses import dataclass

@dataclass
class PrimerDesignRequest:
    sequence_id: str
    sequence_template: str
    task_type: str = "generic"
    sequence_target: Optional[List[List[int]]] = None
    sequence_excluded_region: Optional[List[List[int]]] = None
    primer_parameters: Optional[Dict] = None
    thermodynamic_parameters: Optional[Dict] = None
    advanced: Optional[Dict] = None
    probe_parameters: Optional[Dict] = None


class PrimerDesignService:
    """Primer3-py 引物设计服务"""

    # 任务类型预设参数
    TASK_PRESETS = {
        "PCR": {
            "PRIMER_PRODUCT_SIZE_RANGE": [[100, 1000]],
            "PRIMER_OPT_SIZE": 20,
            "PRIMER_MIN_SIZE": 18,
            "PRIMER_MAX_SIZE": 25,
            "PRIMER_OPT_TM": 60.0,
            "PRIMER_MIN_TM": 57.0,
            "PRIMER_MAX_TM": 63.0,
        },
        "qPCR": {
            "PRIMER_PRODUCT_SIZE_RANGE": [[80, 250]],
            "PRIMER_OPT_SIZE": 20,
            "PRIMER_MIN_SIZE": 18,
            "PRIMER_MAX_SIZE": 24,
            "PRIMER_OPT_TM": 60.0,
            "PRIMER_MIN_TM": 58.0,
            "PRIMER_MAX_TM": 60.0,
            "PRIMER_MIN_GC": 30.0,
            "PRIMER_MAX_GC": 70.0,
            "PRIMER_MAX_POLY_X": 4,
        },
        "sequencing": {
            "PRIMER_PICK_LEFT_PRIMER": 1,
            "PRIMER_PICK_RIGHT_PRIMER": 0,
            "PRIMER_PRODUCT_SIZE_RANGE": [[500, 1000]],
        },
    }

    @staticmethod
    def design(request: PrimerDesignRequest) -> Dict:
        """
        执行引物设计

        使用 primer3-py v2.0+ API:
        - design_primers(seq_args, global_args, misprime_lib, mishyb_lib)
        """

        # 1. 构建序列参数 (seq_args)
        seq_args = {
            'SEQUENCE_ID': request.sequence_id,
            'SEQUENCE_TEMPLATE': request.sequence_template.upper(),
        }

        if request.sequence_target:
            seq_args['SEQUENCE_TARGET'] = request.sequence_target
        if request.sequence_excluded_region:
            seq_args['SEQUENCE_EXCLUDED_REGION'] = request.sequence_excluded_region

        # 2. 构建全局参数 (global_args)
        global_args = {
            'PRIMER_TASK': 'generic',
            'PRIMER_PICK_LEFT_PRIMER': 1,
            'PRIMER_PICK_RIGHT_PRIMER': 1,
            'PRIMER_PICK_INTERNAL_OLIGO': 0,
            'PRIMER_NUM_RETURN': 5,
        }

        # 3. 加载任务预设
        if request.task_type in PrimerDesignService.TASK_PRESETS:
            global_args.update(
                PrimerDesignService.TASK_PRESETS[request.task_type]
            )

        # 4. 应用用户自定义参数
        if request.primer_parameters:
            param_mapping = {
                'opt_size': 'PRIMER_OPT_SIZE',
                'min_size': 'PRIMER_MIN_SIZE',
                'max_size': 'PRIMER_MAX_SIZE',
                'opt_tm': 'PRIMER_OPT_TM',
                'min_tm': 'PRIMER_MIN_TM',
                'max_tm': 'PRIMER_MAX_TM',
                'min_gc': 'PRIMER_MIN_GC',
                'max_gc': 'PRIMER_MAX_GC',
                'max_poly_x': 'PRIMER_MAX_POLY_X',
                'product_size_range': 'PRIMER_PRODUCT_SIZE_RANGE',
            }
            for key, p3_key in param_mapping.items():
                if key in request.primer_parameters:
                    global_args[p3_key] = request.primer_parameters[key]

        # 5. 热力学参数
        if request.thermodynamic_parameters:
            thermo_mapping = {
                'salt_monovalent': 'PRIMER_SALT_MONOVALENT',
                'salt_divalent': 'PRIMER_SALT_DIVALENT',
                'dntp_conc': 'PRIMER_DNTP_CONC',
                'dna_conc': 'PRIMER_DNA_CONC',
            }
            for key, p3_key in thermo_mapping.items():
                if key in request.thermodynamic_parameters:
                    global_args[p3_key] = request.thermodynamic_parameters[key]

        # 6. 探针参数 (qPCR)
        if request.probe_parameters and request.probe_parameters.get('pick_internal_oligo'):
            global_args['PRIMER_PICK_INTERNAL_OLIGO'] = 1
            probe_mapping = {
                'internal_opt_size': 'PRIMER_INTERNAL_OPT_SIZE',
                'internal_min_size': 'PRIMER_INTERNAL_MIN_SIZE',
                'internal_max_size': 'PRIMER_INTERNAL_MAX_SIZE',
                'internal_opt_tm': 'PRIMER_INTERNAL_OPT_TM',
                'internal_min_tm': 'PRIMER_INTERNAL_MIN_TM',
                'internal_max_tm': 'PRIMER_INTERNAL_MAX_TM',
                'internal_min_gc': 'PRIMER_INTERNAL_MIN_GC',
                'internal_max_gc': 'PRIMER_INTERNAL_MAX_GC',
            }
            for key, p3_key in probe_mapping.items():
                if key in request.probe_parameters:
                    global_args[p3_key] = request.probe_parameters[key]

        # 7. 调用 Primer3 引擎
        try:
            result = primer3.design_primers(seq_args, global_args)
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'error_type': 'primer3_engine_error'
            }

        # 8. 解析结果并格式化
        return PrimerDesignService._parse_result(
            result, request.sequence_template
        )

    @staticmethod
    def _parse_result(raw_result: Dict, template: str) -> Dict:
        """解析 Primer3 原始输出为结构化数据"""

        num_pairs = raw_result.get('PRIMER_PAIR_NUM_RETURNED', 0)
        pairs = []

        for i in range(num_pairs):
            pair = {
                'rank': i + 1,
                'pair_penalty': raw_result.get(f'PRIMER_PAIR_{i}_PENALTY', 0),
                'compl_any': raw_result.get(f'PRIMER_PAIR_{i}_COMPL_ANY', 0),
                'compl_end': raw_result.get(f'PRIMER_PAIR_{i}_COMPL_END', 0),
                'product_size': raw_result.get(f'PRIMER_PAIR_{i}_PRODUCT_SIZE', 0),

                'forward_primer': {
                    'sequence': raw_result.get(f'PRIMER_LEFT_{i}_SEQUENCE', ''),
                    'position': raw_result.get(f'PRIMER_LEFT_{i}', [0, 0]),
                    'length': raw_result.get(f'PRIMER_LEFT_{i}', [0, 0])[1],
                    'tm': raw_result.get(f'PRIMER_LEFT_{i}_TM', 0),
                    'gc_percent': raw_result.get(f'PRIMER_LEFT_{i}_GC_PERCENT', 0),
                    'self_any': raw_result.get(f'PRIMER_LEFT_{i}_SELF_ANY', 0),
                    'self_end': raw_result.get(f'PRIMER_LEFT_{i}_SELF_END', 0),
                    'hairpin_tm': raw_result.get(f'PRIMER_LEFT_{i}_HAIRPIN_TH', 0),
                    'end_stability': raw_result.get(f'PRIMER_LEFT_{i}_END_STABILITY', 0),
                },

                'reverse_primer': {
                    'sequence': raw_result.get(f'PRIMER_RIGHT_{i}_SEQUENCE', ''),
                    'position': raw_result.get(f'PRIMER_RIGHT_{i}', [0, 0]),
                    'length': raw_result.get(f'PRIMER_RIGHT_{i}', [0, 0])[1],
                    'tm': raw_result.get(f'PRIMER_RIGHT_{i}_TM', 0),
                    'gc_percent': raw_result.get(f'PRIMER_RIGHT_{i}_GC_PERCENT', 0),
                    'self_any': raw_result.get(f'PRIMER_RIGHT_{i}_SELF_ANY', 0),
                    'self_end': raw_result.get(f'PRIMER_RIGHT_{i}_SELF_END', 0),
                    'hairpin_tm': raw_result.get(f'PRIMER_RIGHT_{i}_HAIRPIN_TH', 0),
                    'end_stability': raw_result.get(f'PRIMER_RIGHT_{i}_END_STABILITY', 0),
                },
            }

            # 探针信息
            probe_seq = raw_result.get(f'PRIMER_INTERNAL_{i}_SEQUENCE', '')
            if probe_seq:
                pair['probe'] = {
                    'sequence': probe_seq,
                    'position': raw_result.get(f'PRIMER_INTERNAL_{i}', [0, 0]),
                    'length': raw_result.get(f'PRIMER_INTERNAL_{i}', [0, 0])[1],
                    'tm': raw_result.get(f'PRIMER_INTERNAL_{i}_TM', 0),
                    'gc_percent': raw_result.get(f'PRIMER_INTERNAL_{i}_GC_PERCENT', 0),
                }

            # 计算质量评分 (0-100)
            pair['quality_score'] = PrimerDesignService._calculate_score(pair)
            pairs.append(pair)

        return {
            'success': True,
            'total_pairs': num_pairs,
            'pairs': pairs,
            'raw_explanations': {
                'left': raw_result.get('PRIMER_LEFT_EXPLAIN', ''),
                'right': raw_result.get('PRIMER_RIGHT_EXPLAIN', ''),
                'pair': raw_result.get('PRIMER_PAIR_EXPLAIN', ''),
                'internal': raw_result.get('PRIMER_INTERNAL_EXPLAIN', ''),
            }
        }

    @staticmethod
    def _calculate_score(pair: Dict) -> int:
        """
        计算引物对综合质量评分 (0-100)

        评分维度:
        - Tm 平衡性 (30%): 两条引物 Tm 差异越小越好
        - GC 平衡性 (20%): GC% 在 45-55% 区间得分最高
        - 特异性 (25%): 互补性越低越好
        - 结构稳定性 (25%): 发夹 Tm 越低越好
        """
        import math

        score = 100.0

        # Tm 平衡 (差异 < 2°C 满分)
        tm_diff = abs(pair['forward_primer']['tm'] - pair['reverse_primer']['tm'])
        tm_score = max(0, 30 * (1 - tm_diff / 5))

        # GC% 理想度 (45-55% 满分)
        gc_f = pair['forward_primer']['gc_percent']
        gc_r = pair['reverse_primer']['gc_percent']
        gc_score = 20 * (1 - (abs(gc_f - 50) + abs(gc_r - 50)) / 100)

        # 特异性 (互补性 < 3 满分)
        compl = pair['compl_any']
        spec_score = max(0, 25 * (1 - compl / 12))

        # 结构稳定性
        hairpin_f = pair['forward_primer'].get('hairpin_tm', 0) or 0
        hairpin_r = pair['reverse_primer'].get('hairpin_tm', 0) or 0
        struct_score = max(0, 25 * (1 - max(hairpin_f, hairpin_r) / 40))

        return int(min(100, max(0, tm_score + gc_score + spec_score + struct_score)))
```

### 4.4 BLAST 特异性验证 API

```python
# backend/services/primer_blast.py

class PrimerBlastService:
    """
    NCBI Primer-BLAST 特异性验证服务

    两种模式:
    1. 远程模式: 调用 NCBI Primer-BLAST API (适合少量验证)
    2. 本地模式: 使用本地 BLAST+ 数据库 (适合大量验证, 需自建数据库)
    """

    NCBI_PRIMER_BLAST_URL = "https://www.ncbi.nlm.nih.gov/tools/primer-blast/"

    @staticmethod
    def validate_remote(
        forward_seq: str,
        reverse_seq: str,
        database: str = "nr",
        organism: Optional[str] = None,
        expect_value: float = 1000,
        word_size: int = 7
    ) -> Dict:
        """
        远程 Primer-BLAST 验证

        Parameters:
            forward_seq: 正向引物序列 (5'-3')
            reverse_seq: 反向引物序列 (5'-3')
            database: BLAST数据库 (nr, refseq_rna, genome)
            organism: 物种限定 (如 "Homo sapiens")
        """
        # 实现NCBI API调用
        # 注意: NCBI有频率限制, 需要实现队列和重试机制
        pass

    @staticmethod
    def validate_local(
        forward_seq: str,
        reverse_seq: str,
        db_path: str,
        num_threads: int = 4
    ) -> Dict:
        """
        本地 BLAST+ 验证

        需要预先构建的BLAST数据库:
        - 人类基因组: GRCh38
        - 小鼠基因组: GRCm39
        - 自定义物种数据库

        数据库路径配置在 /data/omichub/blast_db/
        """
        import subprocess

        # 构建查询序列
        query = f">primer_pair\n{forward_seq}\n{reverse_seq}"

        # 运行 blastn
        cmd = [
            'blastn',
            '-db', db_path,
            '-outfmt', '6 std stitle',
            '-evalue', '1000',
            '-word_size', '7',
            '-num_threads', str(num_threads),
            '-dust', 'no'
        ]

        result = subprocess.run(
            cmd, input=query, text=True, capture_output=True
        )

        # 解析BLAST结果
        return PrimerBlastService._parse_blast_result(result.stdout)
```

---

## 五、AI 合成助手模块

### 5.1 功能概述

设计完成后，用户点击 **「AI合成助手」** 按钮，系统:

1. **自动生成订单文案** —— AI 根据引物信息生成专业合成订单
2. **选择合成公司** —— 内置多家主流合成公司模板
3. **预览邮件** —— 用户可以编辑邮件内容
4. **一键发送** —— 通过 SMTP 发送邮件到合成公司

### 5.2 合成公司配置

```yaml
# /data/omichub/config/primer_synthesis_companies.yaml

companies:
  - id: sangon
    name: 生工生物
    full_name: 生工生物工程(上海)股份有限公司
    email: order@sangon.com
    phone: 400-821-0008
    website: https://www.sangon.com
    order_template: sangon
    features:
      - 普通引物
      - HPLC纯化
      - 修饰引物 (荧光标记, 磷酸化)
    delivery_days: 2-3
    price_hint: 普通引物 1.2元/bp

  - id: tsingke
    name: 擎科生物
    full_name: 北京擎科生物科技股份有限公司
    email: order@tsingke.com
    phone: 400-610-8836
    website: https://www.tsingke.com
    order_template: tsingke
    features:
      - 普通引物
      - PAGE纯化
      - 长链引物 (up to 150mer)
    delivery_days: 1-2
    price_hint: 普通引物 1.0元/bp

  - id: genscript
    name: 金斯瑞
    full_name: 南京金斯瑞生物科技有限公司
    email: order@genscript.com.cn
    phone: 400-025-8686
    website: https://www.genscript.com.cn
    order_template: genscript
    features:
      - 基因合成
      - 高通量引物板
      - 特殊修饰
    delivery_days: 2-5
    price_hint: 普通引物 1.5元/bp

  - id: novogene
    name: 诺禾致源
    full_name: 北京诺禾致源科技股份有限公司
    email: order@novogene.com
    phone: 400-966-0802
    website: https://www.novogene.com
    order_template: novogene
    features:
      - 普通引物
      - NGS相关引物
    delivery_days: 2-3
    price_hint: 普通引物 1.3元/bp

  - id: invitrogen
    name: Invitrogen (Thermo)
    full_name: Thermo Fisher Scientific
    email: 通过网站下单
    website: https://www.thermofisher.com
    order_template: invitrogen
    features:
      - 国际品质
      - 多种纯化选项
    delivery_days: 5-10
    price_hint: 价格较高, 品质保证
```

### 5.3 AI 订单生成 Prompt

```python
# backend/services/ai_order.py

PRIMER_ORDER_PROMPT = """你是一位专业的分子生物学实验助理，擅长撰写引物合成订单。

请根据以下引物信息，生成一封专业的引物合成订单邮件。

## 引物信息
{primer_info}

## 合成要求
- 合成公司: {company_name}
- 纯化方式: {purification}
- 合成规模: {scale}
- 交付形式: {delivery_form}
- 特殊要求: {special_requirements}

## 要求
1. 邮件主题清晰明确，包含实验室名称和订单类型
2. 正文简洁专业，列出所有引物的详细信息
3. 引物序列必须5'-3'方向，使用等宽字体
4. 包含联系人信息和回寄地址
5. 语气礼貌但不过于客套
6. 如果有qPCR探针，需特别标注荧光基团和淬灭基团

## 输出格式
- subject: 邮件主题
- body: 邮件正文 (Markdown格式)
"""


def generate_order_email(
    primer_pairs: List[Dict],
    company_id: str,
    user_config: Dict,
    purification: str = "STD",
    scale: str = "25nmol",
    delivery_form: str = "冻干粉",
    special_requirements: str = ""
) -> Dict[str, str]:
    """
    使用AI生成引物合成订单邮件

    Args:
        primer_pairs: 选中的引物对列表
        company_id: 合成公司ID
        user_config: 用户信息 (姓名, 实验室, 地址, 电话)
        purification: 纯化方式 (STD/HPLC/PAGE)
        scale: 合成规模
        delivery_form: 交付形式
        special_requirements: 特殊要求
    """

    # 格式化引物信息
    primer_info_text = ""
    for i, pair in enumerate(primer_pairs, 1):
        primer_info_text += f"\n### 引物对 #{i}\n"
        primer_info_text += f"- 正向引物: 5'-{pair['forward_primer']['sequence']}-3'\n"
        primer_info_text += f"- 反向引物: 5'-{pair['reverse_primer']['sequence']}-3'\n"
        if 'probe' in pair:
            primer_info_text += f"- TaqMan探针: 5'-{pair['probe']['sequence']}-3'\n"

    # 加载公司信息
    company = load_company_config(company_id)

    # 构建 Prompt
    prompt = PRIMER_ORDER_PROMPT.format(
        primer_info=primer_info_text,
        company_name=company['name'],
        purification=purification,
        scale=scale,
        delivery_form=delivery_form,
        special_requirements=special_requirements or "无"
    )

    # 调用AI API
    response = call_ai_api(prompt)

    return {
        "subject": response.get("subject", ""),
        "body": response.get("body", ""),
        "recipient": company['email'],
        "company_name": company['name']
    }
```

### 5.4 邮件发送服务

```python
# backend/services/mail_service.py

from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

class PrimerMailService:
    """引物合成邮件发送服务"""

    def __init__(self, smtp_config: Dict):
        """
        smtp_config:
            host: SMTP服务器地址
            port: 端口
            username: 邮箱账号
            password: 邮箱密码/授权码
            use_tls: 是否使用TLS
        """
        self.smtp_config = smtp_config

    async def send_order_email(
        self,
        recipient: str,
        subject: str,
        body: str,
        cc: Optional[List[str]] = None
    ) -> Dict:
        """
        发送引物合成订单邮件

        Args:
            recipient: 合成公司邮箱
            subject: 邮件主题
            body: 邮件正文 (HTML/Markdown)
            cc: 抄送列表 (如导师邮箱)
        """
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.smtp_config['username']
            msg['To'] = recipient
            if cc:
                msg['Cc'] = ', '.join(cc)

            # 添加HTML正文
            html_body = markdown_to_html(body)
            msg.attach(MIMEText(html_body, 'html', 'utf-8'))

            # 连接SMTP服务器
            server = smtplib.SMTP(
                self.smtp_config['host'],
                self.smtp_config['port']
            )
            if self.smtp_config.get('use_tls', True):
                server.starttls()
            server.login(
                self.smtp_config['username'],
                self.smtp_config['password']
            )

            # 发送
            server.send_message(msg)
            server.quit()

            return {
                'success': True,
                'message': f'邮件已发送至 {recipient}',
                'timestamp': datetime.now().isoformat()
            }

        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'error_type': 'smtp_error'
            }
```

### 5.5 AI合成助手前端交互流程

```
用户点击 [AI合成助手]
        │
        ▼
┌─────────────────────────┐
│ Step 1: 选择引物          │
│ 显示所有候选引物对        │
│ 用户选择要合成的引物 (可多选)│
└─────────────────────────┘
        │
        ▼
┌─────────────────────────┐
│ Step 2: 选择合成公司      │
│ 卡片式展示各公司:         │
│ 生工 | 擎科 | 金斯瑞 | ... │
│ 显示价格、交期、特色       │
└─────────────────────────┘
        │
        ▼
┌─────────────────────────┐
│ Step 3: 合成参数配置      │
│ • 纯化方式 (STD/HPLC/PAGE) │
│ • 合成规模 (25nmol/100nmol) │
│ • 交付形式 (冻干粉/液体)   │
│ • 特殊修饰 (荧光基团等)    │
│ • 特殊要求备注            │
└─────────────────────────┘
        │
        ▼
┌─────────────────────────┐
│ Step 4: AI生成订单        │
│ 显示Loading动画           │
│ "正在为您撰写专业订单..."  │
│ (调用 /primer/ai-order)   │
└─────────────────────────┘
        │
        ▼
┌─────────────────────────┐
│ Step 5: 邮件预览与编辑    │
│ 分栏显示:                 │
│ 左: Markdown编辑区        │
│ 右: HTML预览区            │
│ 可修改邮件内容            │
└─────────────────────────┘
        │
        ▼
┌─────────────────────────┐
│ Step 6: 发送确认          │
│ 显示收件人、主题摘要       │
│ [确认发送] [保存草稿] [取消]│
│ (调用 /primer/mail/send)  │
└─────────────────────────┘
        │
        ▼
┌─────────────────────────┐
│ 发送成功 / 失败提示       │
│ 保存到历史记录            │
└─────────────────────────┘
```

---

## 六、Excel 导出功能

### 6.1 导出内容设计

```python
# backend/services/excel_export.py

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

def export_primer_excel(
    design_result: Dict,
    user_info: Dict,
    export_config: Optional[Dict] = None
) -> bytes:
    """
    导出引物设计结果为专业Excel报告

    工作表结构:
    1. 设计概览 (Summary)
    2. 引物详情 (Primer Details)
    3. 热力学分析 (Thermodynamics)
    4. 合成订单 (Synthesis Order) - 可直接打印发给公司
    """

    wb = Workbook()

    # === Sheet 1: 设计概览 ===
    ws_summary = wb.active
    ws_summary.title = "设计概览"

    # 标题
    ws_summary['A1'] = 'OmicHub PrimerForge 引物设计报告'
    ws_summary['A1'].font = Font(size=18, bold=True, color='1A73E8')
    ws_summary.merge_cells('A1:H1')

    # 基本信息
    info_data = [
        ['报告生成时间', datetime.now().strftime('%Y-%m-%d %H:%M')],
        ['序列ID', design_result['sequence_id']],
        ['任务类型', design_result['task_type']],
        ['序列长度', len(design_result['sequence_template'])],
        ['设计引物对数', design_result['total_pairs']],
        ['设计者', user_info.get('name', 'Unknown')],
        ['实验室', user_info.get('lab', 'Unknown')],
    ]
    for i, (key, value) in enumerate(info_data, 3):
        ws_summary[f'A{i}'] = key
        ws_summary[f'B{i}'] = value
        ws_summary[f'A{i}'].font = Font(bold=True)

    # === Sheet 2: 引物详情 ===
    ws_details = wb.create_sheet("引物详情")

    headers = [
        '排名', '正向引物序列(5\'-3\')', '正向Tm(°C)', '正向GC%',
        '正向位置', '反向引物序列(5\'-3\')', '反向Tm(°C)', '反向GC%',
        '反向位置', '产物大小(bp)', '综合评分'
    ]
    for col, header in enumerate(headers, 1):
        cell = ws_details.cell(1, col, header)
        cell.font = Font(bold=True, color='FFFFFF')
        cell.fill = PatternFill(start_color='1A73E8', end_color='1A73E8', fill_type='solid')
        cell.alignment = Alignment(horizontal='center')

    for i, pair in enumerate(design_result['pairs'], 2):
        ws_details.cell(i, 1, pair['rank'])
        ws_details.cell(i, 2, pair['forward_primer']['sequence'])
        ws_details.cell(i, 3, round(pair['forward_primer']['tm'], 2))
        ws_details.cell(i, 4, round(pair['forward_primer']['gc_percent'], 1))
        ws_details.cell(i, 5, f"{pair['forward_primer']['position'][0]}-{pair['forward_primer']['position'][0] + pair['forward_primer']['position'][1]}")
        ws_details.cell(i, 6, pair['reverse_primer']['sequence'])
        ws_details.cell(i, 7, round(pair['reverse_primer']['tm'], 2))
        ws_details.cell(i, 8, round(pair['reverse_primer']['gc_percent'], 1))
        ws_details.cell(i, 9, f"{pair['reverse_primer']['position'][0] - pair['reverse_primer']['position'][1]}-{pair['reverse_primer']['position'][0]}")
        ws_details.cell(i, 10, pair['product_size'])
        ws_details.cell(i, 11, pair['quality_score'])

        # 评分颜色标注
        score_cell = ws_details.cell(i, 11)
        if pair['quality_score'] >= 90:
            score_cell.fill = PatternFill(start_color='C8E6C9', end_color='C8E6C9', fill_type='solid')
        elif pair['quality_score'] >= 70:
            score_cell.fill = PatternFill(start_color='FFF9C4', end_color='FFF9C4', fill_type='solid')
        else:
            score_cell.fill = PatternFill(start_color='FFCCBC', end_color='FFCCBC', fill_type='solid')

    # === Sheet 3: 合成订单 ===
    ws_order = wb.create_sheet("合成订单")
    ws_order['A1'] = '引物合成订单 (可直接发送给合成公司)'
    ws_order['A1'].font = Font(size=16, bold=True)
    ws_order.merge_cells('A1:F1')

    # 公司信息
    ws_order['A3'] = '收件公司:'
    ws_order['B3'] = '[请填写]'
    ws_order['A4'] = '联系人:'
    ws_order['B4'] = user_info.get('name', '')
    ws_order['A5'] = '联系电话:'
    ws_order['B5'] = user_info.get('phone', '')
    ws_order['A6'] = '回寄地址:'
    ws_order['B6'] = user_info.get('address', '')

    # 订单表格
    order_headers = ['编号', '名称', '序列(5\'-3\')', '纯化方式', '规模', '备注']
    for col, header in enumerate(order_headers, 1):
        cell = ws_order.cell(8, col, header)
        cell.font = Font(bold=True)
        cell.fill = PatternFill(start_color='E3F2FD', end_color='E3F2FD', fill_type='solid')

    row = 9
    for i, pair in enumerate(design_result['pairs'], 1):
        ws_order.cell(row, 1, i)
        ws_order.cell(row, 2, f"{design_result['sequence_id']}_F{i}")
        ws_order.cell(row, 3, pair['forward_primer']['sequence'])
        ws_order.cell(row, 4, 'STD')
        ws_order.cell(row, 5, '25nmol')
        row += 1

        ws_order.cell(row, 1, i)
        ws_order.cell(row, 2, f"{design_result['sequence_id']}_R{i}")
        ws_order.cell(row, 3, pair['reverse_primer']['sequence'])
        ws_order.cell(row, 4, 'STD')
        ws_order.cell(row, 5, '25nmol')
        row += 1

    # 自动调整列宽
    for ws in wb.worksheets:
        for col in ws.columns:
            max_length = 0
            column = col[0].column_letter
            for cell in col:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min(max_length + 2, 60)
            ws.column_dimensions[column].width = adjusted_width

    # 保存到内存
    from io import BytesIO
    output = BytesIO()
    wb.save(output)
    output.seek(0)
    return output.getvalue()
```

---

## 七、数据库设计

### 7.1 数据表结构

```sql
-- 引物设计历史记录
CREATE TABLE primer_design_history (
    id              VARCHAR(36) PRIMARY KEY,
    user_id         VARCHAR(36) NOT NULL,
    design_id       VARCHAR(50) UNIQUE NOT NULL,
    sequence_id     VARCHAR(200),
    task_type       ENUM('PCR', 'qPCR', 'sequencing', 'cloning') DEFAULT 'PCR',
    sequence_template TEXT,
    sequence_length INT,
    total_pairs     INT DEFAULT 0,
    parameters      JSON,           -- 存储所有设计参数
    result_summary  JSON,           -- 结果摘要
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_user_id (user_id),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 引物对详情
CREATE TABLE primer_pairs (
    id              VARCHAR(36) PRIMARY KEY,
    design_id       VARCHAR(36) NOT NULL,
    rank_number     INT,
    pair_penalty    DECIMAL(8,4),
    quality_score   INT,
    product_size    INT,
    compl_any       DECIMAL(8,4),
    compl_end       DECIMAL(8,4),

    -- 正向引物
    forward_sequence VARCHAR(100),
    forward_position_start INT,
    forward_length  INT,
    forward_tm      DECIMAL(6,2),
    forward_gc      DECIMAL(5,2),
    forward_self_any DECIMAL(8,4),
    forward_self_end DECIMAL(8,4),
    forward_hairpin_tm DECIMAL(6,2),

    -- 反向引物
    reverse_sequence VARCHAR(100),
    reverse_position_start INT,
    reverse_length  INT,
    reverse_tm      DECIMAL(6,2),
    reverse_gc      DECIMAL(5,2),
    reverse_self_any DECIMAL(8,4),
    reverse_self_end DECIMAL(8,4),
    reverse_hairpin_tm DECIMAL(6,2),

    -- 探针 (qPCR)
    probe_sequence  VARCHAR(100),
    probe_position_start INT,
    probe_tm        DECIMAL(6,2),
    probe_gc        DECIMAL(5,2),

    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (design_id) REFERENCES primer_design_history(id) ON DELETE CASCADE,
    INDEX idx_design_id (design_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 合成订单记录
CREATE TABLE primer_synthesis_orders (
    id              VARCHAR(36) PRIMARY KEY,
    design_id       VARCHAR(36) NOT NULL,
    user_id         VARCHAR(36) NOT NULL,
    company_id      VARCHAR(50),
    company_name    VARCHAR(100),
    email_recipient VARCHAR(200),
    email_subject   VARCHAR(500),
    email_body      TEXT,
    purification    VARCHAR(20),
    synthesis_scale VARCHAR(20),
    delivery_form   VARCHAR(20),
    status          ENUM('draft', 'sent', 'confirmed', 'delivered') DEFAULT 'draft',
    sent_at         TIMESTAMP NULL,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (design_id) REFERENCES primer_design_history(id) ON DELETE SET NULL,
    INDEX idx_user_id (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

---

## 八、分阶段实施计划

### Phase 1: 核心引物设计 (Day 1-3)

| 天数 | 任务 | 产出 |
|------|------|------|
| Day 1 | 后端: Primer3-py 封装 + /primer/design API | 可运行的引物设计接口 |
| Day 1 | 前端: 页面骨架 + 左侧参数面板UI | 参数输入界面 |
| Day 2 | 前端: 序列可视化组件 + 结果表格 | 序列图 + 引物表格 |
| Day 2 | 前后端联调: 设计流程打通 | 端到端可设计引物 |
| Day 3 | 前端: 右侧统计栏 + 交互优化 | 完整设计界面 |
| Day 3 | 测试: PCR 与 qPCR 双模式 | 两种模式可用 |

### Phase 2: AI 合成助手 (Day 4-5)

| 天数 | 任务 | 产出 |
|------|------|------|
| Day 4 | 后端: AI订单生成 API + 公司配置 | /primer/ai-order 可用 |
| Day 4 | 后端: SMTP邮件发送服务 | /primer/mail/send 可用 |
| Day 5 | 前端: AI助手抽屉 (6步流程) | 完整的AI合成助手界面 |
| Day 5 | 前端: 邮件预览编辑器 | Markdown编辑 + HTML预览 |

### Phase 3: 导出与历史 (Day 6)

| 天数 | 任务 | 产出 |
|------|------|------|
| Day 6 | 后端: Excel导出服务 | /primer/export/excel 可用 |
| Day 6 | 前端: 导出按钮 + 下载 | 可下载Excel报告 |
| Day 6 | 数据库: 历史记录表 + API | 设计历史可保存/查看 |

### Phase 4: 优化与上线 (Day 7)

| 天数 | 任务 | 产出 |
|------|------|------|
| Day 7 | BLAST特异性验证 (可选) | /primer/blast 可用 |
| Day 7 | 性能优化 + Bug修复 | 生产就绪 |
| Day 7 | 工具箱卡片接入 | 从工具箱可进入 |

### 总计工期: **7 天**

---

## 九、接口 Mock 数据 (前端先行开发)

```json
// POST /api/v1/primer/design (Mock Response)
{
  "success": true,
  "design_id": "des_20260709_abc123",
  "task_type": "qPCR",
  "runtime_ms": 245,
  "summary": {
    "total_pairs_returned": 5,
    "left_primers_considered": 1483,
    "right_primers_considered": 1493
  },
  "primer_pairs": [
    {
      "rank": 1,
      "pair_penalty": 0.12,
      "compl_any": 4.00,
      "compl_end": 2.00,
      "forward_primer": {
        "sequence": "GTAAAACGACGGCCAGT",
        "position": [100, 17],
        "length": 17,
        "tm": 59.85,
        "gc_percent": 52.9,
        "self_any": 6.00,
        "self_end": 2.00,
        "hairpin_tm": 0.0,
        "end_stability": -9.2,
        "warnings": []
      },
      "reverse_primer": {
        "sequence": "CAGGAAACAGCTATGAC",
        "position": [280, 17],
        "length": 17,
        "tm": 58.42,
        "gc_percent": 47.1,
        "self_any": 4.00,
        "self_end": 0.00,
        "hairpin_tm": 0.0,
        "end_stability": -8.4,
        "warnings": []
      },
      "probe": {
        "sequence": "CGATCGATCGATCGATCG",
        "position": [150, 18],
        "length": 18,
        "tm": 68.5,
        "gc_percent": 55.6,
        "self_any": 2.00,
        "warnings": []
      },
      "product_size": 180,
      "quality_score": 98
    }
  ]
}
```

---

## 十、风险与应对

| 风险 | 影响 | 应对方案 |
|------|------|----------|
| Primer3-py 安装失败 | 后端无法运行 | 提供预编译 wheel 文件; Docker 容器预装 |
| NCBI BLAST API限流 | 特异性验证慢 | 本地BLAST+备选; 异步队列处理 |
| 长序列设计超时 | 用户体验差 | 设置30s超时; 序列长度限制(≤10kb) |
| SMTP配置复杂 | 邮件发送失败 | 提供详细的SMTP配置教程; 支持QQ/163/Gmail |
| AI订单生成质量 | 邮件不专业 | 优化Prompt; 允许用户编辑后再发送 |

---

## 十一、后续可扩展功能

1. **引物数据库集成**: 对接 PrimerBank、RTPrimerDB
2. **多物种基因组 BLAST**: 本地构建常见物种数据库 (人/小鼠/拟南芥/水稻)
3. **引物批次管理**: 实验室级别的引物库存管理
4. **实验验证反馈**: 用户标记引物实际效果, 形成质量评分数据库
5. **引物联盟**: 实验室间共享验证过的引物
6. **LAMP/RPA 等温扩增**: 支持更多扩增技术的引物设计

---

> **下一步**: CC 可根据本文档开始 Phase 1 开发。建议先实现后端 `/primer/design` API 与前端的参数面板 + 结果表格, 即可进行首次联调。
