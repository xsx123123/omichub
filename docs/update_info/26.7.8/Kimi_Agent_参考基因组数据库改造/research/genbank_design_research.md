# GenBank 基因数据库设计模式研究

> 研究时间：2025年7月
> 研究对象：NCBI GenBank / Gene / RefSeq / Datasets 基因数据库系统
> 研究方法：网络搜索、网站浏览、API 文档分析、学术论文调研

---

## 1. 基因详情页面布局分析

### 1.1 概述

NCBI Gene 数据库提供两种主要的基因详情页面展示方式：
1. **传统 Gene 页面**（Legacy Gene Page）：经典的分节式布局，信息丰富
2. **新版 NCBI Datasets Gene 页面**：现代化的精简布局，强调数据下载和 API 访问

### 1.2 传统 Gene 详情页面布局

传统 Gene 详情页面采用 **三栏式布局**，从左到右依次为：主内容区、侧边栏（可折叠）、右侧发现栏。

#### 1.2.1 页面顶部 - 基因摘要区域（Summary Section）

这是页面最重要的区域，包含基因的核心标识信息：

| 字段 | 说明 | 示例（TP53） |
|------|------|-------------|
| Official Symbol | 官方基因符号（由命名机构提供） | TP53 |
| Official Full Name | 官方基因全称 | tumor protein p53 |
| Gene ID | NCBI 内部唯一标识符 | 7157 |
| Gene type | 基因类型 | protein coding |
| RefSeq status | RefSeq 审核状态 | REVIEWED |
| Organism | 物种信息 | Homo sapiens |
| Lineage | 分类谱系 | Eukaryota; Metazoa; Chordata; ... |
| Also known as | 基因别名/曾用名 | P53; BCC7; LFS1; BMFS5; TRP53 |
| Primary source | 主要外部数据源 | HGNC:HGNC:11998 |
| See related | 其他数据库交叉引用 | Ensembl, MIM, AllianceGenome |
| Summary | 基因功能摘要 | 该基因编码肿瘤抑制蛋白... |

**设计特点**：
- 核心标识信息（Symbol、Name、GeneID）在页面最顶部，字体较大
- 官方符号和名称标注来源机构（如 HGNC），并提供链接
- "Also known as" 区域展示别名，支持多种搜索命中
- 外部数据库链接以标签-值对形式展示，点击可跳转

#### 1.2.2 基因组上下文区域（Genomic Context Section）

此区域展示基因在基因组中的定位信息：

| 字段 | 说明 |
|------|------|
| Location | 染色体带位置，如 17p13.1 |
| Exon count | 外显子数量，如 13 |
| Assembly | 基因组组装版本 |
| Chr | 染色体编号 |
| Location coordinates | 精确坐标（如 NC_000017.11 7668421..7687490, complement）|
| Annotation release | 注释版本号 |
| Status | current / previous assembly |

**可视化设计**：
- 提供 **基因组邻接基因图谱**，以箭头形式展示目标基因（深红色）及其上下游邻接基因
- 每个基因箭头均可点击，直接跳转到该基因的 Gene 页面
- 提供 **不同组装版本**的坐标对照（如 GRCh38.p14 vs GRCh37.p13 vs T2T-CHM13v2.0）
- 右上角链接到 **Genome Data Viewer** 全基因组浏览器

#### 1.2.3 基因组区域、转录本和产物区域（Genomic Regions, Transcripts, and Products Section）

此区域是 NCBI Gene 页面最核心的可视化组件：

**功能特点**：
- 嵌入 **NCBI Sequence Viewer**，提供交互式基因组浏览器视图
- 展示基因的内含子/外显子/编码区组织结构
- 标示 RefSeq 基因组、mRNA 和蛋白产物的位置
- 支持添加数据轨道（RNA-seq 数据、变异数据等）
- 支持缩放、平移、导航等交互操作
- 悬停在特征上显示工具提示（tooltip）
- 可配置显示选项（Configure 按钮）

**序列获取链接**：
- **Graphics**：图形化展示
- **FASTA**：FASTA 格式序列
- **GenBank**：完整 GenBank 格式记录

#### 1.2.4 表达区域（Expression Section）

- 基于 RNA-seq 数据的组织特异性表达概览
- 展示基因在不同组织中的表达水平（如 RPKM 值）
- 以简明的文本摘要 + "查看更多"链接的方式展示

#### 1.2.5 文献区域（Bibliography Section）

- **PubMed 关联文献**：通过自动关联和人工标注，展示与该基因相关的学术论文
- **GeneRIFs（Gene References Into Functions）**：由 NLM 索引人员或公众提交的简短功能描述
- 每条 GeneRIF 都链接到对应的 PubMed 文献
- 支持提交新的 GeneRIF（社区贡献机制）
- 显示文献总数（如 TP53 有 11629 篇关联文献和 9570 条 GeneRIFs）

#### 1.2.6 表型区域（Phenotypes Section）

此区域将基因与临床表型关联：

| 子区域 | 内容 |
|--------|------|
| Associated conditions | 与该基因相关的疾病（链接到 MedGen、OMIM、GeneReviews）|
| Professional guidelines | 临床指南（如 ACMG 指南）|
| BioGRID CRISPR 表型 | 来自 CRISPR 筛选的功能数据 |
| PheGenI | GWAS 表型关联数据 |
| Genetic Testing Registry | 基因检测信息 |

#### 1.2.7 变异区域（Variation Section）

- 链接到 **ClinVar**（临床意义变异）
- 链接到 **dbSNP**（单核苷酸多态性）
- 链接到 **dbVar**（结构变异）
- 链接到 **Variation Viewer** 基因组浏览器
- 链接到 **1000 Genomes Browser** 群体变异数据

#### 1.2.8 通路区域（Pathways Section）

- 内容来自 NCBI **BioSystems** 数据库
- 整合多个通路来源（KEGG、Reactome 等）
- 点击通路链接可查看该通路中的所有基因
- 支持将通路基因导出为表格

#### 1.2.9 一般基因信息区域（General Gene Information Section）

此区域包含多个子部分：

| 子部分 | 内容 |
|--------|------|
| Markers | 遗传标记 |
| Homology | 同源基因信息（包括 Orthologs 和 Paralogs）|
| Clone Names | 克隆名称 |
| Gene Ontology | GO 功能注释（分子功能、生物学过程、细胞组分）|
| Orthologs from Annotation Pipeline | 基于注释流程计算的直系同源基因 |

**GO 注释展示方式**：
- 三列表格：GO Term | Evidence Code | PubMed 链接
- 按分子功能（Function）、生物学过程（Process）、细胞组分（Component）分组
- 每个 GO term 链接到 AmiGO 浏览器
- Evidence Code 链接到 GO 证据代码文档
- PubMed 列提供支持文献链接

#### 1.2.10 蛋白质信息区域（General Protein Information Section）

- 蛋白质名称和 RefSeq 蛋白 ID（如 NP_000537）
- CCDS（Consensus CDS）链接
- 保守结构域（Conserved Domains）
- 蛋白质相互作用（Interactions）

#### 1.2.11 NCBI RefSeq 序列区域（NCBI Reference Sequences Section）

此区域集中展示与该基因相关的所有 RefSeq 序列：

| 序列类型 | Accession 前缀 | 说明 |
|----------|---------------|------|
| Genomic | NC_ 或 NG_ | 基因组序列 |
| mRNA | NM_ | 转录本序列 |
| Protein | NP_ | 蛋白序列 |
| ncRNA | NR_ | 非编码 RNA |
| Predicted mRNA | XM_ | 预测转录本 |
| Predicted Protein | XP_ | 预测蛋白 |

每个序列都提供以下链接：
- 序列记录页面（Entrez Nucleotide / Protein）
- FASTA 格式
- GenBank 格式
- Sequence Viewer 图形展示

#### 1.2.12 相关序列区域（Related Sequences Section）

- 展示与该基因相关的 GenBank 序列记录
- 提供不同来源的序列选择

#### 1.2.13 侧边栏设计（Sidebar）

右侧边栏提供：

| 组件 | 功能 |
|------|------|
| Table of Contents | 快速导航到各个数据区域 |
| Genome Browsers | 链接到外部基因组浏览器（GDV、Variation Viewer、Ensembl、UCSC）|
| Related Information | 链接到其他 NCBI 数据库资源 |
| Find Related Data | 跨数据库关联搜索 |

**设计特点**：
- 侧边栏可折叠（"Hide sidebar"按钮）
- 目录导航实时高亮当前区域
- 所有链接都使用数据库间交叉引用系统

### 1.3 新版 NCBI Datasets Gene 页面

新版 Datasets Gene 页面采用更简洁的现代化设计，强调数据下载和 API 可访问性。

#### 1.3.1 页面结构

```
+--------------------------------------------------+
| BETA 标签 | 页面标题 (TP53 - tumor protein p53)     |
+--------------------------------------------------+
| 导航标签: Summary | Transcripts and proteins |     |
|          Orthologs | Gene ontology | Download       |
+--------------------------------------------------+
| Summary 面板                                      |
| - Gene name, symbol, GeneID, Organism, Gene type  |
| - Synonyms, Protein count, Transcript count       |
| - MANE Select 转录本                              |
| - RefSeq summary                                  |
+--------------------------------------------------+
| Genome Data Viewer 嵌入区域                       |
| - 基因组上下文和注释                               |
+--------------------------------------------------+
| Publications (最新论文列表)                        |
+--------------------------------------------------+
```

#### 1.3.2 设计特点

- **标签页导航**：将信息分为 Summary、Transcripts and proteins、Orthologs、Gene ontology、Download 五个主要标签
- 强调数据可下载性（蓝色下载按钮）
- 提供 CLI 命令示例
- API 调用示例在页面顶部展示
- 精简的信息展示，去除了部分非核心信息
- 保留了指向传统 Gene 页面的链接（"View the legacy Gene page"）

---

## 2. 信息架构分析

### 2.1 核心实体关系

NCBI Gene 数据库的信息架构围绕 **Gene（基因）** 这一核心实体构建，形成星型辐射结构：

```
                    +-------------+
                    |    Gene     |
                    |  (核心实体)  |
                    +------+------+
                           |
        +------------------+------------------+
        |                  |                  |
   +----v----+      +------v------+     +-----v-----+
   |  Nucleotide|     |   Protein   |     |  Genome   |
   |  (序列)    |     |   (蛋白质)  |     |  (基因组)  |
   +----+----+      +------+------+     +-----+-----+
        |                  |                  |
   NM_, NR_, XM_       NP_, XP_, YP_      NC_, NG_, NT_
   
        +------------------+------------------+
        |                                     |
   +----v----+      +------v------+     +-----v-----+
   |   GO     |     |  Pathways   |     | Variation |
   |功能注释   |     |   (通路)     |     |  (变异)    |
   +----+----+      +------+------+     +-----+-----+
        |                  |                  |
   +----v----+      +------v------+     +-----v-----+
   |  PubMed  |     |  Phenotypes |     | Orthologs |
   | (文献)   |     |   (表型)     |     | (同源基因) |
   +---------+      +-------------+     +-----------+
```

### 2.2 数据层次结构

#### 2.2.1 基因组层次

```
Assembly (组装版本)
  |
  +-- Chromosome (染色体)
       |
       +-- Gene (基因)
            |
            +-- Transcript (转录本)
                 |
                 +-- Exon (外显子)
                 |    |
                 |    +-- 5' UTR
                 |    +-- CDS (编码序列)
                 |    +-- 3' UTR
                 |
                 +-- Intron (内含子)
```

#### 2.2.2 序列记录层次

**GenBank Flat File 格式**的标准分区结构：

```
LOCUS       - 序列标识和基本信息
DEFINITION  - 序列描述
ACCESSION   - 唯一访问号
VERSION     - 版本号
KEYWORDS    - 关键词
SOURCE      - 来源生物体
  ORGANISM  - 物种分类
REFERENCE   - 参考文献
  AUTHORS
  TITLE
  JOURNAL
  PUBMED
FEATURES    - 特征注释表
  source    - 来源特征（必填）
  gene      - 基因特征
  mRNA      - mRNA 特征
  CDS       - 编码序列
  exon      - 外显子
  ...
ORIGIN      - 序列数据
```

### 2.3 交叉引用系统（Cross-References）

NCBI Gene 通过 `db_xref` 和外部链接系统建立了与众多数据库的交叉引用：

| 数据库 | 引用类型 | 说明 |
|--------|----------|------|
| HGNC | 命名授权 | 人类基因官方命名 |
| MIM/OMIM | 疾病关联 | 孟德尔遗传疾病 |
| Ensembl | 基因组注释 | 欧洲生物信息学研究所 |
| UniProt | 蛋白质信息 | 蛋白质序列和功能 |
| AllianceGenome | 整合基因信息 | 模式生物基因联盟 |
| GO | 功能注释 | 基因本体论 |
| KEGG | 通路信息 | 代谢通路数据库 |
| PubMed | 文献引用 | 生物医学文献 |
| ClinVar | 临床变异 | 变异临床意义 |
| dbSNP | 变异信息 | 单核苷酸多态性 |

### 2.4 RefSeq 序列命名体系

RefSeq 采用系统化的 accession 前缀体系来区分分子类型和管理状态：

| 前缀 | 分子类型 | 管理状态 | 说明 |
|------|----------|----------|------|
| NC_ | 基因组 | Reviewed/Provisional | 完整基因组分子（参考组装）|
| NG_ | 基因组 | Reviewed/Provisional | 不完整基因组区域 |
| NM_ | mRNA | Reviewed/Predicted/Provisional | 蛋白编码转录本 |
| NR_ | RNA | Reviewed/Provisional | 非编码 RNA |
| NP_ | 蛋白质 | Reviewed/Predicted/Provisional | 蛋白质 |
| NT_ | 基因组 | Model | 基因组 contig |
| NW_ | 基因组 | Model | WGS contig |
| XM_ | mRNA | Model | 预测转录本 |
| XR_ | RNA | Model | 预测非编码 RNA |
| XP_ | 蛋白质 | Model | 预测蛋白 |
| YP_ | 蛋白质 | Reviewed | 基因组直接注释蛋白 |
| WP_ | 蛋白质 | Reviewed | 跨物种非冗余蛋白 |

### 2.5 数据整合策略

NCBI Gene 采用 **"基因中心化"（Gene-centered）** 的数据整合策略：

1. **单一入口点**：以 GeneID 为核心标识符，将所有相关数据聚合到一个页面
2. **分层信息展示**：从摘要到详细信息的分层递进
3. **自动关联与人工审核结合**：大部分数据通过算法自动关联，关键数据由人工审核
4. **多版本共存**：支持不同基因组组装版本的坐标映射
5. **社区贡献**：GeneRIF 等功能允许社区参与数据建设

---

## 3. 交互设计分析

### 3.1 基因搜索界面

#### 3.1.1 基本搜索

- 顶部导航栏提供全局搜索框，可选择数据库（默认 Gene）
- 支持关键词、基因符号、GeneID、物种名等多种搜索方式
- 自动建议和历史记录功能

#### 3.1.2 高级搜索（Advanced Search Builder）

高级搜索支持以下搜索字段：

| 字段 | 说明 | 示例 |
|------|------|------|
| All Fields | 所有字段 | TP53 |
| Gene Name | 基因名称 | tumor protein p53 |
| Gene ID | GeneID | 7157 |
| Symbol | 基因符号 | TP53 |
| Alias | 别名 | P53 |
| Title | 标题 | tumor protein |
| Organism | 物种 | Homo sapiens |
| Chromosome | 染色体 | 17 |
| Accession | Accession 号 | NM_000546 |
| Property | 属性 | alive[prop] |

搜索语法支持布尔运算符（AND, OR, NOT）和字段限定符（如 `TP53[Gene] AND Homo sapiens[Organism]`）。

### 3.2 搜索结果页面

#### 3.2.1 结果展示格式

搜索结果默认以 **Tabular 格式** 展示：

| 列名 | 内容 |
|------|------|
| Name/GeneID | 首选基因符号和 GeneID（链接到详情页）|
| Description | 基因描述（完整名称和物种）|
| Location | 基因组位置（染色体、坐标、方向）|
| Aliases | 别名 |
| MIM | 人类基因对应的 MIM 编号 |

**设计特点**：
- 每行左侧有复选框，可选择多个记录进行批量操作
- 列标题可点击排序
- 基因符号链接到 Full Report 详情页
- 结果数量多时支持分页

#### 3.2.2 过滤器侧边栏（Filter Sidebar）

过滤器侧边栏位于结果列表左侧，提供多维度筛选：

**Gene sources（基因来源）**：
- Genomic（染色体基因）
- Mitochondrial（线粒体基因）
- Organelles（细胞器基因）
- Plastids（质体基因）

**Categories（类别）**：
- Alternatively spliced（可变剪接）
- Annotated genes（已注释基因）
- Non-coding（非编码）
- Protein-coding（蛋白编码）
- Pseudogene（假基因）

**Sequence content（序列内容）**：
- CCDS（共识 CDS）
- Ensembl（Ensembl 注释）
- RefSeq（RefSeq 序列）
- RefSeqGene（RefSeqGene 项目）

**Status（状态）**：
- Current（当前）
- 其他状态

**Chromosome locations（染色体位置）**：
- 按染色体编号筛选

**Top Organisms（主要物种）**：
- 按物种筛选结果

**设计特点**：
- 只显示当前结果集中有效的筛选选项
- 多个筛选条件之间使用 AND 逻辑
- 激活的筛选器旁边显示勾选标记
- 支持 "Clear all" 一键清除所有筛选
- 可通过 "Show additional filters" 添加更多筛选组

#### 3.2.3 显示设置（Display Settings）

- **Tabular**（默认）：表格格式
- **Tabular (text)**：制表符分隔文本格式（最多 200 条）
- **Summary**：摘要列表格式
- **UI List**：简洁列表
- **Gene Table**：基因表格式
- **GeneRIF**：仅显示 GeneRIF
- **XML / ASN.1**：机器可读格式

### 3.3 基因之间的关联展示

#### 3.3.1 基因组上下文导航

- 基因详情页中的基因组图谱显示邻接基因
- 每个邻接基因都是可点击的链接
- 点击后直接跳转到该基因的详情页
- 支持在 Genome Data Viewer 中浏览更大的基因组区域

#### 3.3.2 同源基因展示

- **NCBI Orthologs**：提供跨物种直系同源基因比较
- 以表格形式展示多个物种中的同源基因
- 包含基因符号、GeneID、RefSeq 产物等列
- 支持跳转到 Multiple Comparative Genome Viewer (MCGV)

#### 3.3.3 蛋白质相互作用

- 在 Interactions 区域展示蛋白质-蛋白质相互作用
- 以表格形式展示：相互作用蛋白 | 相互作用类型 | 证据文献
- 支持分页浏览大量相互作用数据

### 3.4 序列查看器集成

#### 3.4.1 NCBI Sequence Viewer

Sequence Viewer 是嵌入在各种 NCBI 页面中的核心可视化组件：

**在 Gene 页面中的集成**：
- 嵌入在 "Genomic regions, transcripts, and products" 区域
- 默认显示基因及其周围区域
- 显示基因注释轨道（NCBI RefSeq Annotation）
- 显示基因外显子/内含子结构

**主要交互功能**：

| 功能 | 说明 |
|------|------|
| 缩放 | 通过工具栏或鼠标滚轮缩放 |
| 平移 | 拖拽或使用方向键平移 |
| 轨道配置 | 通过 "Tracks" 按钮添加/移除数据轨道 |
| 工具提示 | 悬停显示特征详细信息 |
| 下载 | 导出 PDF/SVG 图像或序列数据 |
| BLAST | 直接从序列启动 BLAST 搜索 |
| 引物设计 | 启动 Primer-BLAST |

**支持的数据轨道**：

| 轨道类型 | 说明 |
|----------|------|
| Genes | 基因注释 |
| MANE Select | MANE 项目精选转录本 |
| RNA-seq | 表达数据 |
| Variants | 变异数据（dbSNP、ClinVar）|
| Assembly | 组装信息 |
| User Data | 用户上传的自定义数据 |

#### 3.4.2 Genome Data Viewer (GDV)

GDV 是全基因组级别的浏览器，提供更全面的基因组浏览能力：

**页面组件**：

| 组件 | 功能 |
|------|------|
| Ideogram View | 染色体核型图谱，显示当前区域位置 |
| Chromosome Region Selector | 交互式染色体导航 |
| Sequence Viewer | 核心序列展示（嵌入）|
| Exon Navigator | 外显子导航器 |
| BLAST Widget | 集成 BLAST 搜索 |
| Assembly Details | 组装详细信息 |

**从 Gene 到 GDV 的导航**：
- Gene 页面提供 "Genome Data Viewer" 链接
- 点击后自动定位到该基因在基因组中的位置
- GDV 中基因标记为绿色箭头
- 支持在多个基因组组装版本间切换

### 3.5 数据下载交互

#### 3.5.1 "Send to" 功能

Gene 页面右上角提供 "Send to:" 菜单：

| 选项 | 功能 |
|------|------|
| File | 下载为文件 |
| Clipboard | 复制到剪贴板 |
| Collections | 保存到 MyNCBI 收藏 |
| Format options | 选择输出格式 |

#### 3.5.2 NCBI Datasets 下载

新版 Datasets 系统提供更强大的下载功能：

**Gene Data Package 包含**：
- `data_report.jsonl` - 基因元数据（JSON Lines 格式）
- `rna.fna` - 转录本序列（FASTA）
- `protein.faa` - 蛋白质序列（FASTA）
- `dataset_catalog.json` - 文件目录

**下载方式**：
- 网页界面点击下载按钮
- CLI 工具：`datasets download gene gene-id 7157`
- REST API 调用

---

## 4. 数据模型洞察

### 4.1 核心实体模型

从页面布局推断，NCBI Gene 数据库的核心数据模型可以抽象为以下实体：

#### 4.1.1 Gene（基因实体）

```
Gene:
  - GeneID (Primary Key)
  - OfficialSymbol
  - OfficialFullName
  - GeneType (protein-coding, rRNA, tRNA, snRNA, etc.)
  - Organism (Taxonomy ID)
  - Chromosome
  - GenomicLocation (start, end, strand)
  - Aliases[]
  - Summary
  - RefSeqStatus (REVIEWED, PROVISIONAL, etc.)
  - ExternalReferences[] (HGNC, MIM, Ensembl, etc.)
```

#### 4.1.2 Transcript（转录本实体）

```
Transcript:
  - Accession (NM_, NR_, XM_, XR_)
  - Version
  - GeneID (Foreign Key)
  - TranscriptType (mRNA, ncRNA, etc.)
  - Length
  - Exons[]
  - CDS (coding sequence)
  - UTR5, UTR3
  - MANEStatus (MANE Select / MANE Plus Clinical)
```

#### 4.1.3 Protein（蛋白质实体）

```
Protein:
  - Accession (NP_, XP_, YP_, WP_)
  - Version
  - GeneID (Foreign Key)
  - TranscriptAccession (Foreign Key)
  - Length (aa)
  - MolecularWeight
  - Domains[]
  - CCDSID
```

#### 4.1.4 Feature（特征注释）

```
Feature:
  - FeatureID
  - SequenceAccession (Foreign Key)
  - FeatureType (source, gene, mRNA, CDS, exon, ...)
  - Location (start, end, strand, join, complement)
  - Qualifiers[] (key-value pairs)
```

### 4.2 关系模型

#### 4.2.1 一对多关系

| 父实体 | 子实体 | 关系说明 |
|--------|--------|----------|
| Gene | Transcript | 一个基因可以有多个转录本（可变剪接）|
| Gene | Alias | 一个基因有多个别名 |
| Transcript | Exon | 一个转录本由多个外显子组成 |
| Transcript | Protein | 一个转录本对应一个蛋白质（通常）|
| Gene | GOAnnotation | 一个基因有多个 GO 注释 |
| Gene | Publication | 一个基因对应多篇文献 |

#### 4.2.2 多对多关系

| 实体1 | 实体2 | 关系说明 |
|--------|--------|----------|
| Gene | Pathway | 一个基因属于多个通路，一个通路包含多个基因 |
| Gene | Phenotype | 一个基因与多个表型相关，一个表型涉及多个基因 |
| Gene | Variation | 一个基因有多种变异，一个变异可能影响多个基因 |
| Protein | Protein | 蛋白质-蛋白质相互作用 |

### 4.3 数据版本管理

NCBI Gene 数据库实现了精细的版本管理体系：

#### 4.3.1 序列版本

- **Accession.Version** 格式：如 NM_000546.6
- 每次序列变更版本号递增
- 旧版本可通过历史记录访问

#### 4.3.2 基因组组装版本

- 支持多个组装版本的坐标映射
- 如 GRCh38.p14（当前）、GRCh37.p13（历史）、T2T-CHM13v2.0（新）
- 每个组装版本有独立的 GCF_ accession

#### 4.3.3 注释版本

- Annotation Release 编号（如 RS_2025_08）
- 注释版本独立于基因组组装版本更新

### 4.4 数据质量控制模型

#### 4.4.1 RefSeq 状态分级

| 状态 | 说明 | 可信度 |
|------|------|--------|
| REVIEWED | NCBI 人工审核 | 最高 |
| VALIDATED | 经验证 | 高 |
| PROVISIONAL | 临时 | 中 |
| PREDICTED | 预测 | 中低 |
| MODEL | 计算模型 | 低 |
| INFERRED | 推断 | 低 |

#### 4.4.2 证据系统

- GO 注释使用 **Evidence Code** 系统：
  - EXP（实验证据）、IDA（直接分析）、IPI（蛋白质相互作用）
  - IEA（电子注释）、IBA（生物信息学分析）等
- 每个注释都链接到支持文献（PubMed）

### 4.5 API 和数据访问模型

#### 4.5.1 E-utilities API（传统）

NCBI 提供基于 URL 的 E-utilities API 用于程序化数据访问：

| 工具 | 功能 |
|------|------|
| ESearch | 搜索数据库，返回 ID 列表 |
| ESummary | 获取记录摘要 |
| EFetch | 获取完整记录 |
| ELink | 查找数据库间的关联 |
| EInfo | 获取数据库元信息 |
| EGQuery | 全局搜索 |
| ESpell | 拼写建议 |
| ECitMatch | 文献匹配 |

**速率限制**：无 API key 时 3 requests/秒，有 API key 时 10 requests/秒。

#### 4.5.2 NCBI Datasets API（新版）

提供现代化的 REST API：

| 端点 | 功能 |
|------|------|
| `/gene` | 基因元数据查询 |
| `/genome` | 基因组数据查询 |
| `/taxonomy` | 分类学数据查询 |
| `/virus` | 病毒基因组数据 |

**数据包格式**：
- ZIP 归档包含 FASTA、GFF3、JSON 等格式
- JSON Lines (jsonl) 格式的元数据报告
- 支持分页（page_size, page_token）

---

## 5. 对 OmicHub 数据库模块的设计启示

### 5.1 页面布局设计建议

#### 5.1.1 基因详情页布局

借鉴 NCBI Gene 的设计，OmicHub 基因详情页可以采用以下布局：

```
+--------------------------------------------------+
| 基因摘要卡片 (Gene Summary Card)                   |
| - 基因符号、全称、ID、物种、类型                    |
| - 状态标签（审核状态、数据质量）                    |
+--------------------------------------------------+
| 基因组导航栏                                        |
| - 染色体位置 | 基因组浏览器链接 | 组装版本          |
+--------------------------------------------------+
| 左侧: 数据区域 (可折叠)            | 右侧: 导航/链接 |
|                                    |                |
| [+] 转录本与蛋白质结构              | 快速导航目录    |
| [+] 功能注释 (GO)                   | 外部数据库链接  |
| [+] 表达数据                        | 下载选项       |
| [+] 相关文献                        | 分析工具链接   |
| [+] 表型关联                        |                |
| [+] 变异数据                        |                |
| [+] 通路信息                        |                |
| [+] 同源基因                        |                |
+--------------------------------------------------+
```

#### 5.1.2 关键设计原则

1. **信息分层**：核心信息（摘要）突出显示，详细信息折叠/按需展开
2. **视觉引导**：使用颜色编码区分不同数据类型
3. **交叉引用**：每个数据点尽可能链接到来源或详情
4. **下载友好**：提供多种格式的数据下载选项

### 5.2 信息架构设计建议

#### 5.2.1 核心数据模型

```
Gene (核心实体)
|-- BasicInfo (符号、名称、别名、描述)
|-- Location (染色体、坐标、链、组装版本)
|-- Transcripts[] (转录本集合)
|   |-- Exons[] (外显子)
|   |-- CDS (编码区)
|   |-- UTRs (非翻译区)
|-- Proteins[] (蛋白质集合)
|   |-- Domains[] (结构域)
|-- GOAnnotations[] (GO注释)
|-- Pathways[] (通路)
|-- Publications[] (文献)
|-- Phenotypes[] (表型)
|-- Variants[] (变异)
|-- Orthologs[] (同源基因)
|-- ExternalRefs[] (外部引用)
```

#### 5.2.2 借鉴点

1. **基因中心化**：以 Gene 为核心聚合所有相关数据
2. **Accession 体系**：建立系统化的 ID 分配和管理体系
3. **版本管理**：支持序列和注释的版本追踪
4. **分层注释**：区分人工审核和自动预测的数据

### 5.3 交互设计建议

#### 5.3.1 搜索功能

| 功能 | 实现建议 |
|------|----------|
| 基本搜索 | 全局搜索框，支持基因符号、ID、关键词 |
| 高级搜索 | 搜索构建器，支持多字段组合查询 |
| 搜索建议 | 自动补全和搜索建议 |
| 结果筛选 | 侧边栏多维度筛选器 |
| 结果排序 | 按相关性、符号、位置等排序 |

#### 5.3.2 可视化组件

1. **基因组浏览器集成**：
   - 嵌入 IGV.js 或其他开源基因组浏览器
   - 支持基因结构可视化（外显子/内含子）
   - 支持多轨道数据叠加

2. **交互式图谱**：
   - 蛋白质相互作用网络图
   - 通路图高亮
   - 表达热力图

3. **数据表格**：
   - 可排序、可筛选
   - 分页加载
   - 行内展开详情

### 5.4 数据质量与管理建议

| 方面 | 建议 |
|------|------|
| 状态分级 | 建立数据审核状态分级体系（审核/临时/预测/模型）|
| 证据追踪 | 每条注释标注证据来源和可信度 |
| 版本控制 | 实现序列和注释的版本管理 |
| 社区贡献 | 提供用户反馈和数据修正机制 |
| 交叉引用 | 与主要外部数据库建立交叉引用 |

### 5.5 API 设计建议

| 方面 | 建议 |
|------|------|
| REST API | 提供标准化的 RESTful API |
| 数据格式 | 支持 JSON 和 TSV 格式 |
| 批量查询 | 支持批量 ID 查询 |
| 分页机制 | 实现游标分页 |
| 速率限制 | 设置合理的访问频率限制 |
| 下载包 | 提供打包下载功能（ZIP 包含多种格式）|

### 5.6 技术架构建议

```
OmicHub 基因数据库架构建议：

Frontend:
  - React/Vue 组件化 UI
  - 嵌入式基因组浏览器
  - 交互式可视化图表

Backend:
  - Gene 核心数据服务
  - 搜索引擎 (Elasticsearch)
  - 序列数据存储
  - 文件生成服务

Database:
  - 关系型数据库 (PostgreSQL) - 基因元数据
  - 序列数据库 - FASTA/GenBank 文件
  - 缓存层 (Redis) - 热点数据

External Integrations:
  - NCBI Entrez API
  - Ensembl API
  - UniProt API
  - KEGG API
```

---

## 6. 总结

NCBI GenBank/Gene 数据库经过二十多年的发展，形成了一套成熟的基因数据管理、展示和交互体系。其核心设计理念包括：

1. **基因中心化**：以 Gene 为核心实体聚合所有相关生物信息
2. **分层信息展示**：从摘要到详细的分层递进式信息架构
3. **交叉引用网络**：与全球主要生物数据库建立广泛的交叉引用
4. **版本管理体系**：精细的序列和注释版本追踪
5. **社区参与机制**：GeneRIF 等功能鼓励社区贡献
6. **多模式访问**：同时支持 Web 界面、API 和批量下载

这些设计模式和最佳实践为 OmicHub 的基因数据库模块建设提供了重要的参考和借鉴价值。

---

## 参考资源

1. NCBI Gene Help Documentation: https://www.ncbi.nlm.nih.gov/books/NBK3841/
2. NCBI Datasets Documentation: https://www.ncbi.nlm.nih.gov/datasets/docs/
3. Genome Data Viewer Help: https://www.ncbi.nlm.nih.gov/gdv/help/
4. GenBank Flat File Format: https://www.ncbi.nlm.nih.gov/genbank/feature_table/
5. E-utilities API Documentation: https://www.ncbi.nlm.nih.gov/books/NBK25501/
6. Maglott D, et al. "Entrez Gene: gene-centered information at NCBI." Nucleic Acids Res. 2011.
7. Rangwala SH, et al. "Accessing NCBI data using the NCBI Sequence Viewer and Genome Data Viewer (GDV)." Genome Res. 2021.
8. NCBI RefSeq Accession Prefix Reference: https://www.ncbi.nlm.nih.gov/books/NBK21091/table/ch18.T.refseq_accession_numbers_and_mole/
