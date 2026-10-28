# 具体平台工具联动实现案例深度调研报告

> 调研目标：为 OmicHub 平台 AI 助手与生信工具联动架构设计提供参考
> 调研范围：Galaxy Platform、CWL/BCO、OpenAI Code Interpreter、Anthropic Tool Use、AI+生信实际案例

---

## 1. Galaxy Platform — Tool XML 深度分析

### 1.1 实现细节

#### 完整 Tool XML 结构示例

Galaxy Tool XML（又称 wrapper）是 Galaxy 平台连接底层生信工具的核心描述格式。以下是一个综合示例，展示了关键元素：

```xml
<?xml version="1.0"?>
<tool id="bowtie2" name="Bowtie2" version="2.5.0+galaxy0" profile="21.09">
    <description>map reads against reference genome</description>
    
    <!-- 宏定义 - 可复用的XML片段 -->
    <macros>
        <token name\\u003d"@THREADS@">\\$\\{GALAXY_SLOTS:-4\\}</token>
        <xml name="ref_genome_conditional">
            <conditional name="reference_genome">
                <param name="source" type="select" label="Reference genome source">
                    <option value="indexed">Use built-in genome index</option>
                    <option value="history">Use genome from history</option>
                </param>
                <when value="indexed">
                    <param name="index" type="select" label="Select genome">
                        <options from_data_table="bowtie2_indexes">
                            <filter type="sort_by" column="2"/>
                        </options>
                    </param>
                </when>
                <when value="history">
                    <param name="own_file" type="data" format="fasta" label="Reference genome" />
                </when>
            </conditional>
        </xml>
    </macros>
    
    <!-- 依赖管理 -->
    <requirements>
        <requirement type="package" version="2.5.0">bowtie2</requirement>
        <requirement type="package" version="1.16.1">samtools</requirement>
    </requirements>
    
    <!-- 容器支持 -->
    <container type="docker">quay.io/biocontainers/bowtie2:2.5.0--py39h3321a2d_0</container>
    
    <!-- 版本检测命令 -->
    <version_command>bowtie2 --version 2&gt;&amp;1 | head -1</version_command>
    
    <!-- 命令模板 - 使用Cheetah模板引擎 -->
    <command detect_errors="exit_code"><![CDATA[
        #if str($reference_genome.source) == "indexed":
            #set $reference = $reference_genome.index.fields.path
        #else:
            #set $reference = $reference_genome.own_file
        #end if
        
        bowtie2
        -p @THREADS@
        -x "$reference"
        #if str($reads.paired_select) == "paired":
            -1 "$reads.read1" -2 "$reads.read2"
        #else:
            -U "$reads.read1"
        #end if
        --seed $seed
        $analysis_type.analysis_type_select
        #if str($analysis_type.analysis_type_select) == "sensitive":
            -D $analysis_type.D -R $analysis_type.R
        #end if
        2> "$output_stats"
        | samtools sort -@ \${GALAXY_SLOTS:-2} -o "$output_bam" -
    ]]></command>
    
    <!-- 输入定义 -->
    <inputs>
        <!-- 条件参数 - 单端/双端选择 -->
        <conditional name="reads">
            <param name="paired_select" type="select" label="Read type">
                <option value="single">Single-end</option>
                <option value="paired">Paired-end</option>
            </param>
            <when value="single">
                <param name="read1" type="data" format="fastqsanger" label="Reads" />
            </when>
            <when value="paired">
                <param name="read1" type="data" format="fastqsanger" label="Forward reads" />
                <param name="read2" type="data" format="fastqsanger" label="Reverse reads" />
            </when>
        </conditional>
        
        <!-- 引用宏定义的参考基因组条件参数 -->
        <expand macro="ref_genome_conditional" />
        
        <!-- 分析模式条件参数 -->
        <conditional name="analysis_type">
            <param name="analysis_type_select" type="select" label="Analysis mode">
                <option value="fast">Fast</option>
                <option value="sensitive">Sensitive</option>
                <option value="very-sensitive">Very sensitive</option>
            </param>
            <when value="fast" />
            <when value="sensitive">
                <param name="D" type="integer" value="15" label="Seed extension attempts" />
                <param name="R" type="integer" value="2" label="Re-seed limit" />
            </when>
            <when value="very-sensitive" />
        </conditional>
        
        <!-- 基础参数 -->
        <param name="seed" type="integer" value="0" label="Random seed" />
        
        <!-- 布尔参数 -->
        <param name="no_mixed" type="boolean" truevalue="--no-mixed" falsevalue="" 
               checked="false" label="Disable mixed alignments" />
    </inputs>
    
    <!-- 输出定义 -->
    <outputs>
        <data name="output_bam" format="bam" label="${tool.name} on ${on_string}: BAM" />
        <data name="output_stats" format="txt" label="${tool.name} on ${on_string}: Stats" />
        
        <!-- 动态输出发现 -->
        <collection name="split_output" type="list" label="${tool.name} on ${on_string}: Split">
            <discover_datasets pattern="(?P&lt;name&gt;.+)_\\.bam" format="bam" directory="split_out" />
        </collection>
    </outputs>
    
    <!-- 测试定义 -->
    <tests>
        <test expect_num_outputs="2">
            <conditional name="reads">
                <param name="paired_select" value="single" />
                <param name="read1" ftype="fastqsanger" value="reads_1.fq" />
            </conditional>
            <conditional name="reference_genome">
                <param name="source" value="history" />
                <param name="own_file" ftype="fasta" value="ref.fa" />
            </conditional>
            <param name="seed" value="42" />
            <output name="output_bam" file="out.bam" compare="sim_size" />
            <output name="output_stats">
                <assert_contents>
                    <has_line line="42 reads; of these:" />
                </assert_contents>
            </output>
        </test>
    </tests>
    
    <!-- 帮助文档 -->
    <help><![CDATA[
        **Bowtie2** is an ultrafast and memory-efficient tool for aligning 
        sequencing reads to long reference sequences.
    ]]></help>
    
    <!-- 引用 -->
    <citations>
        <citation type="doi">10.1038/nmeth.1923</citation>
    </citations>
</tool>
```

#### 输入参数类型系统

| 参数类型 | 用途 | LLM Schema 映射 |
|---------|------|----------------|
| `data` | 输入数据集（FASTQ, BAM, VCF 等） | `file_id` reference |
| `text` | 文本输入 | `string` |
| `integer` | 整数参数 | `integer` |
| `float` | 浮点数参数 | `number` |
| `select` | 单选下拉菜单 | `string` + `enum` |
| `boolean` | 复选框 | `boolean` |
| `conditional` | 条件分支UI | `object` + `oneOf` |
| `repeat` | 重复参数组 | `array` |
| `section` | 折叠参数组 | `object` |
| `data_column` | 数据列选择 | `string` (列名) |
| `data_table` | 从数据表选择 | `string` + `enum` |

#### 输出发现机制（discover_datasets）

```xml
<!-- 基于正则表达式的动态输出发现 -->
<discover_datasets 
    pattern="(?P<name>.+)\\.(?P<ext>[^.]+)" 
    format="auto"
    directory="outputs"
    recurse="true"
    match_relative_path="false"
    sort_by="filename" />

<!-- 从元数据文件读取输出 -->
<discover_datasets from_provided_metadata="true" />
```

`galaxy.json` 元数据文件示例：
```json
{
    "output1": {
        "ext": "bam",
        "dataset_path": "./results/align.bam",
        "name": "Aligned reads"
    }
}
```

#### Cheetah 变量替换规则

```
${param_name}           → 基本参数替换
${param_name.value}     → 访问复合参数的值
${GALAXY_SLOTS}         → 分配的CPU线程数
${GALAXY_MEMORY_MB}     → 分配的内存(MB)
${__tool_directory__}   → 工具目录路径
${on_string}            → 输入数据集名称
```

### 1.2 架构图/数据流

```
User Input (Form)
       ↓
Galaxy Server ── parses ──→ Tool XML Wrapper
       ↓                         ↓
Cheetah Template          Parameter Validation
       ↓                         ↓
Shell Script ←── renders ── Command Section
       ↓
Job Runner (Slurm/Condor/Docker)
       ↓
Tool Execution
       ↓
Output Discovery (discover_datasets)
       ↓
History Dataset(s)
```

### 1.3 关键设计决策

1. **Cheetah 模板引擎**：选择 Cheetah 而非 Jinja2，因为 Galaxy 开发于 2005 年，Cheetah 是当时最成熟的 Python 模板引擎。历史包袱较重，但功能完整。

2. **条件参数用 XML 而非动态配置**：`conditional` + `when` 的设计使得 UI 渲染、命令生成和测试验证可以统一处理，但 XML 的冗长性是主要痛点。

3. **discover_datasets 的灵活性**：允许工具产生不确定数量的输出文件，通过正则表达式在运行时动态发现，这是处理批量样本分析的关键设计。

4. **Tool Shed 注册机制**：类似 npm/pypi 的包管理，但更侧重于 XML 描述 + 容器镜像的完整封装。

### 1.4 对 OmicHub 的借鉴价值

**可直接借鉴：**
- **参数类型系统**：将 Galaxy 的 param 类型映射为 OpenAI/Anthropic function schema 的 JSON Schema 类型
- **条件参数模式**：`conditional` 可直接映射为 JSON Schema 的 `oneOf` 或 `anyOf`
- **测试定义**：`<tests>` 中的输入/输出断言模式可用于构建工具验证框架
- **discover_datasets**：动态输出发现机制非常适合生信工具的多输出特性

**需规避的陷阱：**
- XML 的冗长性和手工维护成本——OmicHub 应直接用 JSON/YAML 定义工具
- Cheetah 模板的学习曲线——改用更现代的模板引擎或直接 Python f-string
- Tool Shed 的版本兼容性问题——采用语义化版本 + 容器镜像锁定

---

## 2. Common Workflow Language (CWL) / BioCompute Objects

### 2.1 实现细节

#### CWL CommandLineTool 定义结构

```yaml
#!/usr/bin/env cwl-runner

cwlVersion: v1.2
class: CommandLineTool

# 元数据
id: "bwa_mem"
label: "BWA-MEM Aligner"
doc: |
  Align sequencing reads to a reference genome using BWA-MEM algorithm.

# 容器需求
requirements:
  DockerRequirement:
    dockerPull: "quay.io/biocontainers/bwa:0.7.17--h7132678_9"
  ResourceRequirement:
    coresMin: 4
    ramMin: 8192
    outdirMin: 10737418240  # 10GB
  InlineJavascriptRequirement: {}

# 基础命令
baseCommand: [bwa, mem]

# 命令行参数
arguments:
  - prefix: -t
    valueFrom: $(runtime.cores)
  - prefix: -R
    valueFrom: |
      @RG\\tID:$(inputs.read_group_id)\\tSM:$(inputs.sample_name)\\tPL:ILLUMINA

# 输入定义
inputs:
  reference:
    type: File
    format: edam:format_1929  # FASTA
    inputBinding:
      position: 1
    secondaryFiles:
      - .amb
      - .ann
      - .bwt
      - .pac
      - .sa

  reads:
    type: File[]
    format: edam:format_1930  # FASTQ
    inputBinding:
      position: 2
    doc: "Input FASTQ files (1 for SE, 2 for PE)"

  read_group_id:
    type: string
    default: "sample1"

  sample_name:
    type: string
    default: "sample1"

  mark_shorter:
    type: int?
    inputBinding:
      prefix: -k
      position: 3
    doc: "Mark shorter split hits as secondary"

# 输出定义
outputs:
  aligned_bam:
    type: File
    format: edam:format_2572  # BAM
    outputBinding:
      glob: "*.bam"
    secondaryFiles:
      - .bai

  alignment_metrics:
    type: File?
    outputBinding:
      glob: "*.metrics"

# 标准输入输出重定向
stdout: output.sam

# 临时文件要求
tmpdirMin: 2147483648  # 2GB
```

#### CWL Workflow 定义

```yaml
cwlVersion: v1.2
class: Workflow

inputs:
  reads: File[]
  reference: File
  gtf: File

steps:
  fastqc:
    run: tools/fastqc.cwl
    in:
      reads_file: reads
    out: [html_report, zip_report]

  alignment:
    run: tools/star_align.cwl
    in:
      forward_reads: reads[0]
      reverse_reads: reads[1]
      genome_dir: reference
      runThreadN: {default: 8}
    out: [aligned_bam]

  featurecounts:
    run: tools/featurecounts.cwl
    in:
      counts_input_bam: alignment/aligned_bam
      gtf: gtf
    out: [counts_matrix]

outputs:
  qc_report:
    type: File
    outputSource: fastqc/html_report
  gene_counts:
    type: File
    outputSource: featurecounts/counts_matrix
```

#### BioCompute Object (BCO) 结构

```json
{
  "object_id": "https://biocomputeobject.org/BCO_000501/1.1",
  "spec_version": "https://w3id.org/ieee/ieee-2791-schema/2791object.json",
  "etag": "abc123...",
  
  "provenance_domain": {
    "name": "RNA-Seq Differential Expression",
    "version": "1.0.0",
    "created": "2024-01-15T10:00:00Z",
    "modified": "2024-01-20T14:30:00Z",
    "contributors": [
      {
        "name": "Researcher Name",
        "affiliation": "Institution",
        "email": "researcher@example.com"
      }
    ],
    "license": "https://spdx.org/licenses/MIT.html"
  },
  
  "usability_domain": [
    "This workflow performs differential gene expression analysis from RNA-Seq data."
  ],
  
  "description_domain": {
    "pipeline_steps": [
      {
        "step_number": 1,
        "name": "Quality Control",
        "description": "Assess read quality using FastQC",
        "prerequisite": [],
        "input_list": ["fastq_files"],
        "output_list": ["qc_report"],
        "version": "0.12.1"
      },
      {
        "step_number": 2,
        "name": "Read Alignment",
        "description": "Align reads to reference genome using STAR",
        "prerequisite": ["Quality Control"],
        "input_list": ["fastq_files", "reference_genome"],
        "output_list": ["aligned_bam"],
        "version": "2.7.10b"
      }
    ]
  },
  
  "parametric_domain": [
    {
      "param": "min_read_quality",
      "value": "30",
      "step": "Quality Control"
    },
    {
      "param": "max_multimaps",
      "value": "10",
      "step": "Read Alignment"
    }
  ],
  
  "io_domain": {
    "input_subdomain": [
      {
        "uri": {
          "uri": "https://example.com/data/reads.fastq.gz",
          "access_time": "2024-01-15T10:00:00Z"
        }
      }
    ],
    "output_subdomain": [
      {
        "uri": {
          "uri": "https://example.com/results/de_genes.csv",
          "access_time": "2024-01-20T14:30:00Z"
        },
        "mediatype": "text/csv"
      }
    ]
  },
  
  "execution_domain": {
    "script_access_type": "a gcp: us-east4",
    "script": ["https://workflow.example.com/rnaseq.cwl"],
    "software_prerequisites": [
      {
        "name": "cwltool",
        "version": "3.1.0",
        "uri": "https://github.com/common-workflow-language/cwltool"
      }
    ],
    "environment_variables": {
      "THREADS": "8"
    }
  }
}
```

### 2.2 架构图/数据流

```
CWL Tool Definition (YAML/JSON)
       ↓
cwltool / toil / Cromwell (Workflow Engine)
       ↓
DockerRequirement → Pull Container Image
       ↓
Input Binding (File staging)
       ↓
Command Line Construction
       ↓
Container Execution
       ↓
Output Binding (glob pattern matching)
       ↓
Result Files + Provenance Record
       ↓
BCO Generation (optional)
```

### 2.3 关键设计决策

1. **显式的输入/输出声明**：与 Galaxy 的 XML 不同，CWL 强制要求所有输入输出都显式声明，这使其天然适合自动化的 schema 转换。

2. **EDAM Ontology 集成**：通过 `format: edam:format_1929` 等 URI 引用标准化的数据格式定义，有利于 LLM 理解数据类型语义。

3. **容器作为一等公民**：`DockerRequirement` 不是可选组件而是核心设计，确保了可复现性。

4. **BCO 的监管合规性**：IEEE 2791-2020 标准使得工作流可以被监管机构接受，这是 CWL 相对于其他方案的独特优势。

### 2.4 对 OmicHub 的借鉴价值

**可直接借鉴：**
- **CWL 的输入/输出定义模式**：可直接转换为 OpenAI function schema，特别是 `type`、`format` 和 `doc` 字段
- **EDAM Ontology 引用**：用标准化术语描述生信数据类型，有助于 LLM 理解工具语义
- **DockerRequirement**：强制容器化确保可复现性，每个工具都应绑定容器镜像
- **BCO 的 provenance 记录**：自动生成分析溯源记录，满足科研发表和监管要求

**需规避的陷阱：**
- CWL 的学习曲线较陡——OmicHub 应提供图形化工具编辑器自动生成 CWL
- CWL 运行时（cwltool）的调试困难——应提供预配置的执行环境
- BCO 的手动创建繁琐——应自动生成而非要求用户手写

---

## 3. OpenAI Code Interpreter / Advanced Data Analysis

### 3.1 实现细节

#### 执行模型（Sandboxed Python Environment）

Code Interpreter 运行在一个受限的 sandbox 环境中：

```
┌─────────────────────────────────────────────────────────────┐
│                    OpenAI Cloud Infrastructure               │
│  ┌───────────────────────────────────────────────────────┐  │
│  │           Code Interpreter Sandbox                     │  │
│  │  ┌───────────────────────────────────────────────┐   │  │
│  │  │  Python 3.11 Runtime                           │   │  │
│  │  │  - 预装包: numpy, pandas, matplotlib,          │   │  │
│  │  │    scipy, sklearn, PIL, sympy, etc.           │   │  │
│  │  │  - 临时磁盘空间: ~100GB                        │   │  │
│  │  │  - 网络访问: 受限 (无外部API)                  │   │  │
│  │  │  - 执行超时: 约10分钟                          │   │  │
│  │  └───────────────────────────────────────────────┘   │  │
│  │                                                        │  │
│  │  挂载点: /mnt/data/                                    │  │
│  │  文件持久化: 会话级别                                   │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

#### 结果返回的完整数据结构

**Assistant Message 结构：**

```json
{
  "id": "msg_abc123",
  "object": "thread.message",
  "created_at": 1698964262,
  "thread_id": "thread_abc123",
  "role": "assistant",
  "content": [
    {
      "type": "text",
      "text": {
        "value": "I have generated the volcano plot for your differential expression analysis. You can download the results here: \\n\\n[Volcano Plot](sandbox:/mnt/data/volcano_plot.png)",
        "annotations": [
          {
            "type": "file_path",
            "text": "sandbox:/mnt/data/volcano_plot.png",
            "start_index": 95,
            "end_index": 133,
            "file_path": {
              "file_id": "file-volcano-123"
            }
          }
        ]
      }
    }
  ]
}
```

**图片输出类型：**

```json
{
  "type": "image_file",
  "image_file": {
    "file_id": "file-img-456"
  }
}
```

**代码执行步骤日志：**

```json
{
  "id": "step_abc123",
  "object": "thread.run.step",
  "type": "tool_calls",
  "status": "completed",
  "step_details": {
    "type": "tool_calls",
    "tool_calls": [
      {
        "type": "code",
        "code": {
          "input": "import pandas as pd\\nimport matplotlib.pyplot as plt\\n\\ndf = pd.read_csv('/mnt/data/de_results.csv')\\n\\nplt.figure(figsize=(10, 8))\\nplt.scatter(df['log2FoldChange'], -np.log10(df['pvalue']))\\nplt.xlabel('Log2 Fold Change')\\nplt.ylabel('-Log10 P-value')\\nplt.title('Volcano Plot')\\nplt.savefig('/mnt/data/volcano_plot.png')",
          "outputs": [
            {
              "type": "image",
              "image": {
                "file_id": "file-img-456"
              }
            },
            {
              "type": "logs",
              "logs": "Figure saved successfully"
            }
          ]
        }
      }
    ]
  }
}
```

#### 支持的文件格式（完整 MIME 类型列表）

| 扩展名 | MIME 类型 | 用途 |
|--------|-----------|------|
| .csv | text/csv | 数据表格 |
| .json | application/json | 结构化数据 |
| .pdf | application/pdf | 报告文档 |
| .png | image/png | 可视化图表 |
| .jpg | image/jpeg | 图像 |
| .xlsx | application/vnd.openxmlformats-officedocument.spreadsheetml.sheet | Excel |
| .html | text/html | 交互式报告 |
| .fasta | text/plain | 序列文件 |
| .vcf | text/plain | 变异文件 |
| .bam | application/octet-stream | 比对文件 |
| .py | text/x-python | Python 脚本 |
| .md | text/markdown | 文档 |

#### 文件引用的生命周期

```
Upload → file_id 生成 → 绑定到 Thread/Assistant → Code Interpreter 访问
                                                        ↓
                                                  生成新文件
                                                        ↓
                                              file_id 嵌入 annotations
                                                        ↓
                                              客户端通过 Files API 下载
                                                        ↓
                                              会话过期 → 文件清除
```

### 3.2 架构图/数据流

```
User Query
    ↓
LLM (GPT-4o) ── 决策 ──→ 是否调用 Code Interpreter?
    ↓                            ↓
直接回答                    生成 Python 代码
                                ↓
                           Sandbox 执行
                                ↓
                    ┌──────────┼──────────┐
                    ↓          ↓          ↓
                  文本输出    图片输出    文件输出
                    ↓          ↓          ↓
                  logs     image_file  file_id
                    └──────────┼──────────┘
                               ↓
                    结果渲染到 Message Content
                               ↓
                    annotations 标记文件引用
                               ↓
                    前端渲染（图表/表格/下载链接）
```

### 3.3 关键设计决策

1. **沙箱隔离**：代码在完全隔离的环境中执行，防止恶意代码影响主机系统，这是安全性的核心保障。

2. **无状态会话模型**：每次 API 调用都是独立的，通过 Thread 对象维护状态。这简化了扩展但要求客户端管理会话。

3. **annotations 机制**：文件引用不直接嵌入文本，而是通过 `annotations` 数组标记，支持前端将 `sandbox:/mnt/data/` 路径替换为实际下载链接。

4. **MIME 类型驱动渲染**：前端根据 MIME 类型决定如何展示结果（图片直接显示、CSV 渲染为表格、PDF 提供下载）。

### 3.4 对 OmicHub 的借鉴价值

**可直接借鉴：**
- **annotations 文件引用机制**：生信分析工具产生的图表和数据文件可以通过类似的 annotation 模式嵌入回复
- **MIME 类型驱动的结果渲染**：火山图(png)、富集结果(csv)、系统发育树(svg)等不同类型的输出应自动选择最佳渲染方式
- **sandbox 执行模型**：代码执行环境应完全隔离，支持 Python 生态（pandas, matplotlib, scanpy 等）
- **file_id 生命周期管理**：临时文件的创建、引用、下载和清理应有统一管理

**需规避的陷阱：**
- Code Interpreter 无法安装任意 pip 包——OmicHub 需要预装所有生信分析包
- 网络访问受限——OmicHub 需要允许访问外部数据库（KEGG, GO, Ensembl 等）
- 会话隔离导致上下文丢失——需要设计状态持久化机制
- 10 分钟执行超时限制——大批量分析需要异步任务队列

---

## 4. Anthropic Claude Tool Use / Computer Use

### 4.1 实现细节

#### Tool 定义的 JSON Schema 示例

```json
{
  "name": "run_kegg_enrichment",
  "description": "Perform KEGG pathway enrichment analysis on a list of differentially expressed genes. This tool maps gene IDs to KEGG pathways and calculates enrichment p-values using hypergeometric test. Use this when the user asks about pathway enrichment, functional annotation, or wants to understand which biological pathways are overrepresented in their gene list.",
  "input_schema": {
    "type": "object",
    "properties": {
      "gene_list": {
        "type": "array",
        "items": {"type": "string"},
        "description": "List of gene IDs or gene symbols to analyze. Supports Entrez ID, Ensembl ID, or official gene symbols."
      },
      "organism": {
        "type": "string",
        "enum": ["hsa", "mmu", "rno", "dre"],
        "description": "KEGG organism code. hsa=Human, mmu=Mouse, rno=Rat, dre=Zebrafish."
      },
      "p_value_cutoff": {
        "type": "number",
        "minimum": 0,
        "maximum": 1,
        "default": 0.05,
        "description": "P-value threshold for significant pathways."
      },
      "background_genes": {
        "type": "array",
        "items": {"type": "string"},
        "description": "Optional background gene list. If not provided, all genes in the organism will be used."
      }
    },
    "required": ["gene_list", "organism"]
  }
}
```

#### 完整的调用与结果回传消息格式

**Round 1: User 请求 → Assistant 返回 tool_use**

```json
{
  "role": "user",
  "content": "Analyze the enrichment of these genes: TP53, BRCA1, EGFR, MYC, KRAS in human pathways"
}

// Assistant 返回:
{
  "id": "msg_assistant_001",
  "role": "assistant",
  "content": [
    {
      "type": "text",
      "text": "I'll perform KEGG pathway enrichment analysis on these genes."
    },
    {
      "type": "tool_use",
      "id": "toolu_01ABC123xyz",
      "name": "run_kegg_enrichment",
      "input": {
        "gene_list": ["TP53", "BRCA1", "EGFR", "MYC", "KRAS"],
        "organism": "hsa",
        "p_value_cutoff": 0.05
      }
    }
  ],
  "stop_reason": "tool_use",
  "usage": {"input_tokens": 450, "output_tokens": 180}
}
```

**Round 2: User 发送 tool_result → Assistant 返回最终结果**

```json
{
  "role": "user",
  "content": [
    {
      "type": "tool_result",
      "tool_use_id": "toolu_01ABC123xyz",
      "content": {
        "total_pathways_analyzed": 354,
        "significant_pathways": 12,
        "top_pathways": [
          {
            "pathway_id": "hsa05200",
            "pathway_name": "Pathways in cancer",
            "p_value": 1.2e-15,
            "gene_count": 5,
            "genes": ["TP53", "BRCA1", "EGFR", "MYC", "KRAS"]
          },
          {
            "pathway_id": "hsa05224",
            "pathway_name": "Breast cancer",
            "p_value": 3.8e-10,
            "gene_count": 3,
            "genes": ["TP53", "BRCA1", "MYC"]
          }
        ],
        "visualization": "https://omichub.internal/api/plots/kegg_001.png"
      },
      "is_error": false
    }
  ]
}

// Assistant 最终返回:
{
  "role": "assistant",
  "content": [
    {
      "type": "text",
      "text": "KEGG enrichment analysis found 12 significant pathways out of 354 tested. The most significant is \"Pathways in cancer\" (p=1.2e-15), with all 5 input genes participating. Other notable pathways include \"Breast cancer\" (p=3.8e-10) and \"EGFR tyrosine kinase inhibitor resistance\" (p=2.1e-8).\\n\\nA visualization of the top 10 pathways has been generated."
    }
  ],
  "stop_reason": "end_turn"
}
```

#### 多工具并行调用处理

```python
import anthropic
import json

client = anthropic.Anthropic()

# 定义多个生信工具
tools = [
    {
        "name": "run_kegg_enrichment",
        "description": "KEGG pathway enrichment analysis",
        "input_schema": {
            "type": "object",
            "properties": {
                "gene_list": {"type": "array", "items": {"type": "string"}},
                "organism": {"type": "string"}
            },
            "required": ["gene_list", "organism"]
        }
    },
    {
        "name": "plot_volcano",
        "description": "Generate volcano plot for differential expression results",
        "input_schema": {
            "type": "object",
            "properties": {
                "data_file": {"type": "string", "description": "Path to DE results CSV"},
                "logfc_col": {"type": "string", "default": "log2FoldChange"},
                "pval_col": {"type": "string", "default": "padj"},
                "thresholds": {
                    "type": "object",
                    "properties": {
                        "logfc": {"type": "number", "default": 1.0},
                        "pvalue": {"type": "number", "default": 0.05}
                    }
                }
            },
            "required": ["data_file"]
        }
    },
    {
        "name": "build_phylogenetic_tree",
        "description": "Construct phylogenetic tree from multiple sequence alignment",
        "input_schema": {
            "type": "object",
            "properties": {
                "alignment_file": {"type": "string"},
                "method": {"type": "string", "enum": ["neighbor_joining", "maximum_likelihood", "upgma"]},
                "bootstrap": {"type": "integer", "default": 100}
            },
            "required": ["alignment_file", "method"]
        }
    }
]

# 多工具并行调用循环
def chat_with_bioinformatics_tools(user_message, conversation_history=None):
    messages = conversation_history or [{"role": "user", "content": user_message}]
    
    while True:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            tools=tools,
            tool_choice={"type": "auto"},  # 允许 Claude 自主选择工具
            messages=messages
        )
        
        messages.append({"role": "assistant", "content": response.content})
        
        if response.stop_reason != "tool_use":
            return response
        
        # 并行处理所有 tool_use 请求
        tool_results = []
        tool_tasks = []
        
        for block in response.content:
            if block.type == "tool_use":
                tool_tasks.append({
                    "tool_use_id": block.id,
                    "name": block.name,
                    "input": block.input
                })
        
        # 并行执行（所有工具调用相互独立）
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = {
                executor.submit(execute_tool, task): task 
                for task in tool_tasks
            }
            for future in concurrent.futures.as_completed(futures):
                task = futures[future]
                result = future.result()
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": task["tool_use_id"],
                    "content": json.dumps(result),
                    "is_error": result.get("error") is not None
                })
        
        messages.append({"role": "user", "content": tool_results})

# 工具执行函数
def execute_tool(task):
    name = task["name"]
    params = task["input"]
    
    if name == "run_kegg_enrichment":
        return run_kegg_enrichment(**params)
    elif name == "plot_volcano":
        return plot_volcano(**params)
    elif name == "build_phylogenetic_tree":
        return build_phylogenetic_tree(**params)
    else:
        return {"error": f"Unknown tool: {name}"}
```

#### Computer Use 的截图+Action循环

```json
// Computer Use 工具定义
{
  "type": "computer_20251124",
  "name": "computer",
  "display_width_px": 1024,
  "display_height_px": 768,
  "display_number": 1
}

// 截图请求 → Action 响应循环
{
  "role": "assistant",
  "content": [
    {
      "type": "tool_use",
      "id": "toolu_computer_001",
      "name": "computer",
      "input": {
        "action": "screenshot"
      }
    }
  ]
}

// 返回截图结果
{
  "role": "user",
  "content": [
    {
      "type": "tool_result",
      "tool_use_id": "toolu_computer_001",
      "content": [
        {
          "type": "image",
          "source": {
            "type": "base64",
            "media_type": "image/png",
            "data": "iVBORw0KGgoAAAANSUhEUgAA..."
          }
        }
      ]
    }
  ]
}

// Claude 看到截图后，返回下一个 Action
{
  "role": "assistant",
  "content": [
    {
      "type": "tool_use",
      "id": "toolu_computer_002",
      "name": "computer",
      "input": {
        "action": "left_click",
        "coordinate": [520, 340]
      }
    }
  ]
}
```

### 4.2 架构图/数据流

```
User Message
    ↓
Message API (with tools definition)
    ↓
Claude Decision Layer
    ↓
    ├─→ end_turn (直接回答)
    └─→ tool_use (调用工具)
            ↓
    ┌───────┼───────┐
    ↓       ↓       ↓
 Tool1   Tool2   Tool3
    └───────┼───────┘
            ↓
    Parallel Execution
            ↓
    tool_result blocks
            ↓
    Return to Claude
            ↓
    Final Answer
```

### 4.3 关键设计决策

1. **工具定义完全由客户端控制**：不像 OpenAI 的内置工具（Code Interpreter），Anthropic 的所有工具都是用户定义的，给了更大的灵活性但也要求更多配置。

2. **tool_use_id 配对机制**：每个 tool_use 有唯一 ID，tool_result 必须引用该 ID，严格的配对检查确保了调用追踪。这是处理多轮调用的核心机制。

3. **并行工具调用**：一次 assistant 消息可以包含多个 tool_use block，客户端可以并行执行，显著提升多工具场景的效率。

4. **严格的 message 顺序要求**：Anthropic API 强制要求 tool_use 和 tool_result 严格交替，且 tool_result 必须在下一个 user message 中第一个出现。

5. **Computer Use 的视觉-动作循环**：通过 base64 编码的截图传递视觉信息，通过坐标和动作类型控制鼠标/键盘，这是 VLM + 工具使用的典范模式。

### 4.4 对 OmicHub 的借鉴价值

**可直接借鉴：**
- **严格的 tool_use/tool_result 配对模式**：确保每个工具调用都有明确的结果回传和追踪
- **input_schema 的 JSON Schema 验证**：工具参数的类型、范围、枚举值都在 schema 中声明
- **并行工具执行模式**：生信分析中经常需要同时运行多个独立工具（如 KEGG + GO 富集并行）
- **tool_choice 控制**：支持 `auto`/`any`/`tool`/`none` 四种模式，可用于强制调用特定工具
- **is_error 标记**：工具执行失败时标记错误，让 LLM 决定是否重试或换方案

**需规避的陷阱：**
- 工具描述（description）的质量直接决定调用准确率——需要精心编写每个工具的描述
- 严格的 message 顺序要求增加了状态管理复杂度——需要完善的会话管理中间件
- 没有内置的文件上传/下载机制——需要自己实现文件传递层

---

## 5. 实际 AI + 生信案例分析

### 5.1 GeneGPT — NCBI API 工具增强的基因组问答

#### 实现细节

GeneGPT 由 NCBI 团队开发，是**最早的生信工具增强 LLM 之一**，核心创新是"增强解码算法"（augmented decoding）：

```python
# GeneGPT 的核心推理循环（简化版）
class GeneGPT:
    def __init__(self, api_key):
        self.llm = OpenAI(api_key=api_key, model="code-davinci-002")
        self.ncbi_apis = {
            "esearch": "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
            "efetch": "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi",
            "esummary": "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi",
            "blast": "https://blast.ncbi.nlm.nih.gov/Blast.cgi"
        }
    
    def generate(self, question, max_steps=10):
        """增强解码：在生成过程中检测并执行 API 调用"""
        prompt = self.build_prompt(question)
        generated_text = ""
        
        for step in range(max_steps):
            # 调用 LLM 生成下一个片段
            response = self.llm.completions.create(
                model="code-davinci-002",
                prompt=prompt + generated_text,
                max_tokens=256,
                temperature=0,
                stop=["\n\n", "-> RESULT"]
            )
            
            chunk = response.choices[0].text
            generated_text += chunk
            
            # 检测 API 调用标记
            if "->" in chunk:
                api_call = self.extract_api_call(chunk)
                # 执行 API 调用
                result = self.execute_ncbi_api(api_call)
                # 将结果注入生成上下文
                generated_text += f"\n-> RESULT: {result}\n"
        
        return self.extract_answer(generated_text)
    
    def build_prompt(self, question):
        """构建包含 API 文档和示例的 prompt"""
        return f"""
You are a genomic question answering assistant. You can use NCBI APIs to retrieve information.

Available APIs:
- esearch(db, term): Search for IDs in a database
- efetch(db, id): Retrieve full records
- esummary(db, id): Get summaries
- blastn(sequence): Run BLAST search

Examples:
Q: What is the function of gene TP53?
A: Let me search for this gene.
esearch(db=gene, term=TP53[Gene]) -> 7157
efetch(db=gene, id=7157) -> RESULT: ...tumor suppressor...
The TP53 gene encodes a tumor suppressor protein.

Q: {question}
A: """
```

**性能数据**：
- GeneTuring benchmark：平均得分 0.83（远超 Bing 的 0.44、GPT-3 的 0.16）
- 支持多跳推理（multi-hop questions）
- 局限：依赖已停产的 Codex 模型

### 5.2 OpenBioLLM — 多智能体基因组问答架构

#### 实现细节

OpenBioLLM 采用 **LangGraph** 框架实现模块化多智能体架构：

```python
# OpenBioLLM 多智能体架构（基于 LangGraph）
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode

class OpenBioLLM:
    def __init__(self):
        # 三个 Pipeline 控制器
        self.router = Qwen25_32B()       # 任务路由
        self.evaluator = Qwen25_32B()    # 结果评估
        self.generator = Qwen25_32B()    # 答案生成
        
        # 三个工具智能体
        self.eutils_agent = Qwen25_14B()   # NCBI E-utils
        self.blast_agent = Qwen25_14B()    # BLAST 搜索
        self.web_agent = Qwen25_14B()      # 网页搜索
    
    def build_graph(self):
        """构建状态图工作流"""
        workflow = StateGraph(OpenBioState)
        
        # 添加节点
        workflow.add_node("router", self.route_query)
        workflow.add_node("eutils_agent", self.call_eutils)
        workflow.add_node("blast_agent", self.call_blast)
        workflow.add_node("web_agent", self.search_web)
        workflow.add_node("evaluator", self.evaluate_result)
        workflow.add_node("generator", self.generate_answer)
        
        # 设置边
        workflow.set_entry_point("router")
        workflow.add_conditional_edges(
            "router",
            self.decide_tool,
            {
                "eutils": "eutils_agent",
                "blast": "blast_agent",
                "web": "web_agent",
                "direct": "generator"
            }
        )
        workflow.add_edge("eutils_agent", "evaluator")
        workflow.add_edge("blast_agent", "evaluator")
        workflow.add_edge("web_agent", "evaluator")
        workflow.add_conditional_edges(
            "evaluator",
            self.check_sufficiency,
            {
                "sufficient": "generator",
                "insufficient": "router",
                "max_retries": END
            }
        )
        workflow.add_edge("generator", END)
        
        return workflow.compile()
    
    def route_query(self, state):
        """Router：决定使用哪个工具"""
        prompt = f"""Based on the query: {state['query']}
Available tools: eutils (for gene/sequence queries), blast (for sequence alignment), web (for general search)
Respond with JSON: {{"tool": "eutils|blast|web", "reason": "..."}}"""
        
        decision = self.router.generate(prompt)
        return {"next_tool": json.loads(decision)["tool"]}
    
    def evaluate_result(self, state):
        """Evaluator：评估结果是否充分"""
        prompt = f"""Query: {state['query']}
Tool results: {state['tool_results']}
Is this sufficient to answer? Respond with JSON:
{{"next_step": "sufficient|insufficient", "reason": "..."}}"""
        
        evaluation = self.evaluator.generate(prompt)
        return {"evaluation": json.loads(evaluation)}
```

**性能数据**：
- GeneTuring 得分：0.849（vs GeneGPT 的 0.83）
- GeneHop 得分：0.830
- 延迟降低 40-50%（相比单体架构）
- 完全开源：使用 Qwen2.5 和 Llama3.1

### 5.3 BioNext-MCP — Claude Desktop 的生信分析助手

#### 实现细节

BioNext-MCP 是一个基于 **Model Context Protocol (MCP)** 的 Claude Desktop 插件：

```json
// MCP Server 配置
{
  "mcpServers": {
    "bioinformatics-workflow": {
      "command": "node",
      "args": ["D:\\path\\to\\BioNext-mcp\\dist\\index.js"],
      "env": {
        "PROJECT_PATH": "D:\\path\\to\\analysis"
      }
    }
  }
}
```

```typescript
// MCP Tool 定义示例
const bioinformaticsTools = [
  {
    name: "run_scrna_analysis",
    description: "Perform single-cell RNA-seq analysis including QC, normalization, clustering, and marker identification. Supports Seurat/Scanpy workflows.",
    inputSchema: {
      type: "object",
      properties: {
        input_file: { type: "string", description: "Path to .h5ad or .rds file" },
        min_genes: { type: "integer", default: 200 },
        min_cells: { type: "integer", default: 3 },
        n_top_genes: { type: "integer", default: 2000 },
        resolution: { type: "number", default: 0.8 },
        output_umap: { type: "boolean", default: true },
        output_heatmap: { type: "boolean", default: true }
      },
      required: ["input_file"]
    }
  },
  {
    name: "run_kegg_enrichment",
    description: "Perform KEGG pathway enrichment analysis",
    inputSchema: {
      type: "object",
      properties: {
        gene_list: { type: "array", items: { type: "string" } },
        organism: { type: "string", enum: ["hsa", "mmu", "rno"] },
        p_value_cutoff: { type: "number", default: 0.05 }
      },
      required: ["gene_list", "organism"]
    }
  },
  {
    name: "plot_volcano",
    description: "Generate publication-quality volcano plot",
    inputSchema: {
      type: "object",
      properties: {
        data_file: { type: "string" },
        logfc_threshold: { type: "number", default: 1.0 },
        pval_threshold: { type: "number", default: 0.05 },
        highlight_genes: { type: "array", items: { type: "string" } }
      },
      required: ["data_file"]
    }
  }
];
```

**核心特性**：
- 自动 Python 环境检测和包安装
- UTF-8 编码支持中文
- 自动生成 HTML 分析报告
- 支持 scRNA-seq、基因组学、转录组学、蛋白质组学

### 5.4 NVIDIA BioNeMo Agent Toolkit

#### 实现细节

NVIDIA BioNeMo Agent Toolkit（2025年5月发布）是**目前最成熟的商业化生信 AI Agent 平台**：

```python
# BioNeMo Agent Toolkit 工具定义（概念架构）
from bionemo.agent import AgentToolkit, ToolSkill

class BioNeMoAgent:
    def __init__(self):
        self.toolkit = AgentToolkit()
        
        # 注册分子工具
        self.toolkit.register_skill(ToolSkill(
            name="molecular_generation",
            model="MolMIM",  # 分子生成 NIM
            input_schema={"smiles": "string", "num_molecules": "integer"},
            container="nvcr.io/nvidia/molmim:1.0"
        ))
        
        self.toolkit.register_skill(ToolSkill(
            name="protein_structure_prediction",
            model="AlphaFold3-NIM",
            input_schema={"sequence": "string", "ligand_smiles": "string?"},
            gpu_requirements={"vram_gb": 80, "count": 1}
        ))
        
        self.toolkit.register_skill(ToolSkill(
            name="genomic_variant_calling",
            model="DeepVariant-NIM",
            input_schema={"bam_file": "file", "reference": "file"},
            accelerator="Parabricks"
        ))
        
        # 使用 Nemotron 模型进行推理
        self.reasoning_engine = NemotronModel(
            model="nemotron-4-340b",
            tool_use_training="bionemo-specialized"
        )
    
    def execute_workflow(self, natural_language_request):
        """自然语言驱动工作流执行"""
        # 1. 意图理解
        intent = self.reasoning_engine.parse_intent(natural_language_request)
        
        # 2. 工具规划
        plan = self.reasoning_engine.create_tool_plan(
            intent=intent,
            available_tools=self.toolkit.list_skills()
        )
        
        # 3. 并行执行
        results = self.toolkit.execute_parallel(plan.steps)
        
        # 4. 结果整合
        return self.reasoning_engine.synthesize_results(results)
```

**生态系统集成**：

| 集成方 | 角色 |
|--------|------|
| Anthropic, OpenAI | 推理模型提供商 |
| Benchling, Databricks, Snowflake | 数据平台 |
| Boltz, Chai Discovery | AI 原生生物公司 |
| Thermo Fisher, Tecan | 实验室自动化 |
| 礼来 (Lilly), Natera | 药企 |

### 5.5 案例对比总结

| 维度 | GeneGPT | OpenBioLLM | BioNext-MCP | NVIDIA BioNeMo |
|------|---------|------------|-------------|----------------|
| 架构 | 单体 (Codex) | 多智能体 (LangGraph) | MCP 插件 | 企业级 Agent Toolkit |
| 模型 | code-davinci-002 | Qwen2.5/Llama3.1 | Claude Desktop | Nemotron + 多种 |
| 工具类型 | NCBI Web APIs | NCBI APIs + Web | Python 脚本执行 | NIM Microservices |
| 可视化 | 无 | 无 | HTML 报告 | 集成可视化 |
| 开源 | 是 | 是 | 是 | 部分 |
| 容器化 | 否 | 否 | 否 | 是 (Docker) |
| 性能 | 0.83 (GeneTuring) | 0.849 (GeneTuring) | 未评测 | 商业级 |

---

## 6. 国内相关案例分析

### 6.1 BioNext-MCP（中国开发者）

BioNext-MCP 是由中国开发者 Cherine0205 开发的开源项目，托管在 ModelScope 平台。这是**目前国内最接近 OmicHub 愿景的产品**：

- **自然语言驱动**：支持中文对话进行生信分析
- **MCP 协议**：基于 Anthropic 的 Model Context Protocol 标准
- **分析覆盖**：scRNA-seq、基因组学、转录组学、蛋白质组学、多组学整合
- **输出形式**：自动生成 HTML 报告，包含可视化图表

### 6.2 华大基因相关探索

华大基因（BGI）在 AI 与生信结合方面有如下探索：

- **多组学大模型**：开发面向基因组、转录组、蛋白质组的预训练模型
- **自动化分析管线**：在高通量测序数据分析中引入智能化流程编排
- **尚未公开面向用户的 AI 助手产品**

### 6.3 国内生信云平台现状

| 平台 | AI 集成程度 | 特点 |
|------|------------|------|
| 华大基因 BGI Online | 低 | 高通量测序分析，传统工作流 |
| 诺禾致源（Novogene）| 低 | 测序服务为主 |
| 百迈客（Biomarker）| 低 | 多组学分析平台 |
| Galaxy China | 中 | Galaxy 国内镜像，无 AI 功能 |

**国内缺口**：目前尚无集**自然语言交互 + 生信工具调用 + 智能报告生成**于一体的成熟产品。

---

## 7. 设计模式汇总

### 7.1 通用设计模式

#### 模式一：Tool Schema → LLM Function Definition 自动转换

所有平台都需要将工具描述转换为 LLM 可理解的 function schema：

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────────┐
│ Tool Definition │────→│ Schema Converter │────→│ LLM Function Schema │
│ (XML/YAML/JSON) │     │                  │     │ (OpenAI/Anthropic)  │
└─────────────────┘     └──────────────────┘     └─────────────────────┘
```

**关键映射规则**：
| 源格式 | 目标格式 | 映射要点 |
|--------|---------|---------|
| Galaxy param `type="data"` | JSON Schema `type: string` | file_id 引用 |
| Galaxy param `type="select"` | JSON Schema `enum` | 选项列表映射 |
| Galaxy `conditional` | JSON Schema `oneOf` | 条件分支映射 |
| CWL `inputBinding` | JSON Schema `description` | 命令行参数语义化 |
| CWL `format` (EDAM) | JSON Schema `format` | 数据类型标注 |

#### 模式二：Observation-Action Loop（观察-行动循环）

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐     ┌─────────────┐
│   Human     │────→│     LLM      │────→│   Tool Exec  │────→│  Result     │
│   Input     │     │  (Reasoning) │     │  (Action)    │     │  (Obs)      │
└─────────────┘     └──────────────┘     └──────────────┘     └──────┬──────┘
     ↑                                                                │
     └────────────────────────────────────────────────────────────────┘
                              (Feedback Loop)
```

**实现要点**：
- Anthropic 的 `tool_use` → `tool_result` 是最严格的实现
- OpenAI 的 Code Interpreter 将 loop 封装在 Assistant API 内部
- GeneGPT 的 augmented decoding 是 loop 的变体

#### 模式三：结果分层渲染

```
Tool Output
    ├── 结构化数据 (JSON/CSV) → 表格渲染
    ├── 图像 (PNG/SVG/PDF)  → 直接显示
    ├── 文件引用              → 下载链接
    └── 日志/文本             → 格式化显示
```

#### 模式四：多智能体协作（OpenBioLLM 模式）

```
┌─────────┐    ┌──────────┐    ┌──────────┐
│ Router  │───→│ Tool     │───→│ Evaluator│
│ Agent   │    │ Agent(s) │    │ Agent    │
└─────────┘    └──────────┘    └─────┬────┘
     ↑                               │
     └───────────────────────────────┘
              (Feedback Loop)
                    ↓
              ┌──────────┐
              │ Generator│
              │ Agent    │
              └──────────┘
```

#### 模式五：容器化工具封装

```
Tool Definition (JSON)
       ↓
DockerRequirement
       ↓
Container Image (locked version)
       ↓
Sandbox Execution
       ↓
Reproducible Results + Provenance
```

### 7.2 OmicHub 的差异化定位

基于以上分析，OmicHub 的差异化路线应聚焦以下方向：

#### 差异化一："面向生信优化的 Tool Schema 自动生成"

现有方案的问题：
- Galaxy XML → 手动编写，冗长
- CWL → 需专家知识
- NVIDIA BioNeMo → 闭源生态

**OmicHub 的机会**：
- 从 Python/R 函数签名自动提取参数信息，生成 LLM function schema
- 内置生信参数类型库（organism codes, gene ID formats, p-value thresholds 等）
- 支持 `scanpy`, `Seurat`, `DESeq2`, `clusterProfiler` 等主流包的自动 wrapping

#### 差异化二："中国特色分析场景的深度覆盖"

- 中文自然语言理解优化（物种名、基因名的中英文对照）
- 中国人群基因组数据库集成（如 ChinaMAP）
- 国内常用数据库和工具的预集成

#### 差异化三："分析结果的知识化增强"

- 不只是返回图表，而是返回**带解读的分析报告**
- 自动关联文献、通路数据库、临床注释
- 结果可追溯（BCO 标准集成）

#### 差异化四："开放生态 + 企业级部署"

- 开源核心（对标 Galaxy + BioNext-MCP）
- 企业级扩展（对标 NVIDIA BioNeMo 的部分能力）
- 支持私有化部署和国产算力适配

---

## 8. 技术架构建议

### 8.1 OmicHub AI 助手架构参考

```
┌─────────────────────────────────────────────────────────────┐
│                        User Interface                        │
│         (Web Chat / Desktop / API)                          │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│              Natural Language Understanding                  │
│         (Intent Recognition + Entity Extraction)            │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                 Tool Planner / Router                        │
│    (OpenAI Function Calling / Anthropic Tool Use)           │
│              OR Local LLM (Qwen2.5/Llama3)                   │
└──────────┬───────────────────────────────┬──────────────────┘
           │                               │
┌──────────▼──────────┐      ┌─────────────▼──────────────┐
│   Tool Registry     │      │    Session Manager         │
│  (JSON/YAML defs)   │      │  (State + File + Context)  │
└──────────┬──────────┘      └─────────────┬──────────────┘
           │                               │
┌──────────▼───────────────────────────────▼──────────────────┐
│                  Tool Execution Engine                       │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │ Code Runner │  │  Container  │  │  External API       │ │
│  │ (Python/R)  │  │  (Docker)   │  │  (KEGG/Ensembl/GO)  │ │
│  └─────────────┘  └─────────────┘  └─────────────────────┘ │
└──────────┬──────────────────────────────────────────────────┘
           │
┌──────────▼──────────────────────────────────────────────────┐
│                  Result Processing Layer                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │  Renderer   │  │  File Store │  │  Provenance Tracker │ │
│  │ (Chart/Table│  │  (Temp/Pers │  │  (BCO Generation)   │ │
│  │  /Report)   │  │   istent)   │  │                     │ │
│  └─────────────┘  └─────────────┘  └─────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

### 8.2 关键实施建议

| 优先级 | 建议 | 参考案例 |
|--------|------|---------|
| P0 | 采用 Anthropic Tool Use 协议作为工具调用标准 | Anthropic Computer Use |
| P0 | 实现 tool_use → tool_result 的完整循环 | OpenBioLLM |
| P0 | 支持容器化工具执行 (Docker) | CWL DockerRequirement |
| P1 | 构建 Galaxy Tool XML → JSON Schema 转换器 | Galaxy |
| P1 | 实现文件 annotation 和分层渲染 | OpenAI Code Interpreter |
| P1 | 多智能体架构（Router + Tool Agent + Evaluator） | OpenBioLLM |
| P2 | BCO 自动生成和合规性支持 | BioCompute Objects |
| P2 | MCP 协议支持（Claude Desktop 集成） | BioNext-MCP |
| P2 | 中文自然语言优化和本土化数据库 | 中国开发者案例 |

---

## 9. 结论

本次调研覆盖了 5 个主要维度的工具联动实现案例，为 OmicHub 的设计提供了丰富的参考：

1. **Galaxy** 提供了成熟的参数类型系统和工具封装模式
2. **CWL/BCO** 提供了标准化的工作流定义和监管合规性框架
3. **OpenAI Code Interpreter** 提供了优秀的结果渲染和文件管理机制
4. **Anthropic Tool Use** 提供了严格的工具调用协议和状态管理模型
5. **GeneGPT/OpenBioLLM/BioNext-MCP/NVIDIA BioNeMo** 展示了 AI + 生信工具集成的多种路径

OmicHub 的核心差异化在于：**将生信领域知识深度融入工具定义和调用链路**，使得 LLM 不仅能"调用工具"，更能"理解生信分析的语义上下文"。

---

## 参考资源

- Galaxy Tool XML Schema: https://docs.galaxyproject.org/en/master/dev/schema.html
- CWL Specification: https://www.commonwl.org/v1.2/
- BioCompute Objects (IEEE 2791-2020): https://biocomputeobject.org/
- OpenAI Assistants Code Interpreter: https://platform.openai.com/docs/assistants/tools/code-interpreter
- Anthropic Tool Use Documentation: https://docs.anthropic.com/en/docs/build-with-claude/tool-use
- GeneGPT Paper: https://arxiv.org/abs/2304.09667
- OpenBioLLM Paper: https://arxiv.org/abs/2511.15061
- BioNext-MCP: https://github.com/Cherine0205/BioNext-mcp
- NVIDIA BioNeMo Agent Toolkit: https://developer.nvidia.com/bionemo
