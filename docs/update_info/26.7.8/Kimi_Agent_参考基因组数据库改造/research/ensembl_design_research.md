# Ensembl 基因组数据库设计模式研究

> 研究时间：2025年7月
> 研究对象：Ensembl Genome Browser (Release 116)
> 研究方法：网站浏览 + 网络搜索 + 文献分析

---

## 1. 基因详情页面布局分析

### 1.1 整体页面架构

Ensembl 的基因详情页采用**三级导航体系**，是生物学数据库界面设计的典范：

#### 1.1.1 顶部面包屑导航（Breadcrumb）
- **物种标识**：如 `Human (GRCh38.p14)`，点击可切换物种
- **位置信息**：如 `Location: 13:32,315,086-32,400,268`，显示基因所在的染色体坐标
- **基因标识**：如 `Gene: BRCA2`，显示当前查看的基因名称和 Ensembl ID
- 这三个层级分别链接到对应的功能页面，形成清晰的导航路径

#### 1.1.2 顶部标签页（Top Tabs）
Ensembl 将视图组织为**四大类标签页**，以蓝色横条显示在页面顶部：

| 标签页 | 内容类型 | 说明 |
|--------|----------|------|
| **Location** | 位置类视图 | 基因组浏览器视图，展示基因在染色体上的上下文 |
| **Gene** | 基因类视图 | 基因级别的信息汇总、同源基因、变异等 |
| **Transcript** | 转录本类视图 | 单个转录本的详细信息（从转录本表格进入） |
| **Variation** | 变异类视图 | 以特定变异为中心的视图 |

> **设计启示**：这种以"实体类型"为维度的标签切换，而非以"信息类型"为维度，让用户始终清楚当前所处的数据层级。

#### 1.1.3 左侧导航菜单（Left-hand Navigation Column）
每个标签页拥有**独立的左侧导航菜单**，列出该实体类型下所有可查看的信息。这种设计使得页面功能组织极为清晰。

**Gene 标签页的左侧菜单示例**：
- **Gene-based displays**：Summary, Splice variants, Transcript comparison
- **Gene alleles**：Sequence
- **Comparative Genomics**：Genomic alignments, Gene tree, Gene gain/loss tree, Orthologues, Paralogues
- **Ontologies**：GO: Biological process, GO: Molecular function, GO: Cellular component
- **Genetic Variation**：Variant table, Variant image, Structural variants
- **External Data**：Gene expression, Pathway, Molecular interactions, External references, Supporting evidence
- **ID History**：Gene history

---

### 1.2 基因摘要面板（Gene Summary Panel）

位于 Gene > Summary 页面顶部，是基因信息的"一站式"概览：

#### 1.2.1 核心信息区
- **基因名称**：如 `BRCA2`
- **Ensembl 稳定 ID**：如 `ENSG00000139618`（带有版本号如 `.19`）
- **描述**：如 `BRCA2 DNA repair associated [Source:HGNC Symbol;Acc:HGNC:1101]`
- **基因同义词**：如 `BRCC2, FACD, FAD, FAD1, FANCD, FANCD1, XRCC11`
- **位置信息**：`Chromosome 13: 32,315,086-32,400,268 forward strand`
- **基因组版本**：`GRCh38:CM000675.2`

#### 1.2.2 关键统计
- **转录本数量**：`This gene has 19 transcripts (splice variants)`
- **同源基因数量**：`174 orthologues`
- **表型关联数量**：`184 phenotypes`

#### 1.2.3 外部数据库交叉引用
- **MANE Select**：标注官方选定转录本（如 `ENST00000380152`）
- **UniProtKB**：蛋白质标识符（如 `P51587`）
- **RefSeq**：RefSeq 转录本对应关系
- **CCDS**：Consensus Coding Sequence 标识符
- **LRG**：Locus Reference Genomic 框架

#### 1.2.4 版本与映射信息
- **Ensembl version**：`ENSG00000139618.19`
- **跨 assembly 映射**：`This gene maps to 32,889,223-32,974,405 in GRCh37 coordinates`
- **GRCh37 Archive 链接**：直接链接到 GRCh37 归档站点的对应基因
- **基因类型**：`Protein coding`
- **注释方法**：`Ensembl automatic + Havana manual curation`

---

### 1.3 基因组浏览器集成（Region in Detail）

#### 1.3.1 图形化展示区
基因摘要页面底部嵌入了一个**基因组区域可视化图形**，展示：
- **转录本结构**：外显子显示为方块，内含子显示为连接线
- **编码区**：填充方块（filled boxes）表示 CDS
- **非编码区**：空心方块（empty boxes）表示 UTR
- **正链/负链**：相对于蓝色中心线（contig track），正链特征显示在上方，负链在下方
- **邻近基因**：显示重叠或邻近的基因
- **其他基因组特征**：如 CpG 岛、重复序列等

#### 1.3.2 交互功能
- **点击转录本**：链接到对应的 Transcript 标签页
- **轨道（Track）系统**：可配置显示的数据层，包括：
  - MANE Select Transcripts 轨道
  - GENCODE Primary 基因注释轨道
  - Contigs 轨道
  - 用户自定义轨道（Custom tracks）
- **配置页面**：`Configure this page` 按钮打开轨道配置面板
- **缩放和导航**：支持在 Region in Detail 视图中缩放和移动

#### 1.3.3 导出功能
- **导出图像**：支持导出为多种格式
- **分享视图**：生成可分享的 URL
- **重置配置**：恢复默认视图

---

### 1.4 转录本表格（Transcript Table）

#### 1.4.1 表格结构
点击 `Show transcript table` 展开，显示该基因的**所有转录本**：

| 列 | 说明 |
|----|------|
| Transcript ID | 稳定 ID（如 ENST00000380152），含超链接 |
| Name | 转录本名称 |
| Biotype | 生物型（protein_coding, nonsense_mediated_decay 等） |
| Flags | 重要标志（MANE Select, Ensembl Canonical, CCDS 等） |
| Length (bp) | 转录本长度 |
| Protein ID | 对应蛋白质 ID（ENSP 前缀） |
| Translation Length (aa) | 蛋白质氨基酸长度 |

#### 1.4.2 关键标志系统
- **MANE Select**：NCBI 和 EMBL-EBI 共同选定的代表性转录本
- **Ensembl Canonical**：Ensembl 推荐的主要转录本
- **CCDS**：Consensus Coding Sequence 成员
- **GENCODE Basic**：GENCODE 基础注释集成员
- **APPRIS**：APPRIS 注释级别

> **设计启示**：Flags 列使用小图标来快速传达转录本的重要性，避免了文字冗长。

---

### 1.5 外显子/内含子结构可视化（Splice Variants View）

Splice variants 页面提供一个专门的转录本结构比较视图：
- **多转录本对齐展示**：所有转录本在同一坐标系下对齐显示
- **外显子以方块表示**，内含子以连接线表示
- **CDS 区域填充**，UTR 区域空心
- **可配置轨道**：支持添加/移除注释轨道
- **支持缩放**：查看详细的外显子-内含子边界

---

### 1.6 同源基因/直向同源面板（Orthologues）

#### 1.6.1 概览统计表
顶部显示按**物种分类群**汇总的统计：

| 分类群 | 包含物种数 | 1:1 Orthologues | 1:Many | Many:Many | 无 Orthologue |
|--------|-----------|-----------------|--------|-----------|--------------|
| Primates | 23 | 22 | 0 | 0 | 1 |
| Rodents | 24 | 22 | 1 | 0 | 1 |
| Laurasiatheria | 38 | 37 | 0 | 0 | 1 |
| Sauropsida | 27 | 23 | 1 | 0 | 3 |
| Fish | 65 | 49 | 1 | 0 | 15 |
| All | 199 | 168 | 3 | 0 | 28 |

#### 1.6.2 详细表格
- **物种名称**：如 `African ostrich (Struthio camelus australis)`
- **同源类型**：1-to-1, 1-to-many, many-to-many
- **Orthologue ID**：目标物种中的基因 ID（含超链接）
- **位置信息**：目标物种中的染色体坐标
- **序列一致性**：Target %id（同源序列匹配人类序列的百分比）、Query %id
- **GOC Score**：Gene Order Conservation Score (0-100)
- **WGA Coverage**：Whole Genome Alignment Coverage (0-100)
- **High Confidence**：是否为高置信度同源关系

#### 1.6.3 交互功能
- **动态过滤**：可按分类群筛选（Show details 按钮）
- **自定义物种列表**：Configure this page 选择自定义物种
- **序列导出**：导出同源基因的序列（FASTA 格式）
- **区域比较**：Compare Regions 链接，并排查看同源基因
- **基因树查看**：View Gene Tree 链接
- **分页显示**：支持 10/25/50/100/All 条目数选择
- **列显示/隐藏**：Show/hide columns 功能
- **表格搜索**：Filter 输入框实时过滤

---

### 1.7 变异面板（Variation Table）

#### 1.7.1 过滤区
- **Global MAF 过滤**：按最小等位基因频率过滤
- **SIFT 过滤**：按功能影响预测过滤
- **PolyPhen 过滤**：按蛋白质功能预测过滤
- **Consequences 过滤**：按变异后果类型过滤
- **其他列过滤**：多条件组合过滤

#### 1.7.2 变异表格列

| 列 | 说明 |
|----|------|
| Variant ID | 变异标识符（如 rs2072242904），链接到变异详情页 |
| Chr:bp | 染色体位置 |
| Alleles | 等位基因（如 A/C） |
| Global MAF | 全局最小等位基因频率 |
| Class | 变异类型（SNP, indel 等） |
| Source | 数据来源（dbSNP 等） |
| Evidence | 证据等级 |
| Clin. Sig. | 临床意义（来自 ClinVar） |
| Conseq. Type | 后果类型（SO terms，如 splice_donor_variant） |
| AA | 氨基酸变化 |
| AA coord | 氨基酸坐标 |
| SIFT | SIFT 功能预测 |
| PolyPhen | PolyPhen 功能预测 |
| CADD | CADD 评分 |
| REVEL | REVEL 评分 |
| AlphaMissense | AlphaMissense 评分 |
| ESM1b | ESM1b 评分 |
| Transcript | 受影响的转录本 ID |

> **设计启示**：将多种功能预测工具（SIFT, PolyPhen, CADD, REVEL 等）集成在同一表格中，为用户提供多维度的变异影响评估。

---

### 1.8 功能注释面板（Ontologies）

#### 1.8.1 GO 术语展示
GO 术语分为三个独立页面：
- **GO: Biological process**：生物学过程（如 DNA repair）
- **GO: Molecular function**：分子功能（如 ATP binding）
- **GO: Cellular component**：细胞组分（如 nucleus）

每个表格包含：
- GO accession 号（链接到 GO 数据库）
- GO 术语描述
- 证据代码（Evidence code）
- 注释来源
- 关联的转录本稳定 ID

#### 1.8.2 表型面板（Phenotypes）
显示与基因相关的表型信息，分为三个表格：
- 与基因直接关联的表型
- 与基因内变异关联的表型
- 与其他物种该基因同源基因关联的表型

---

### 1.9 序列下载面板

#### 1.9.1 序列查看
- **FASTA 格式**显示序列
- **默认显示基因上下游 600bp** 的侧翼序列
- **高亮显示**：外显子区域高亮标注
- **可配置选项**：
  - 显示/隐藏变异
  - 添加行号
  - 调整侧翼区域长度
  - 显示 1000 Genomes 变异

#### 1.9.2 序列下载
- **Download sequence** 按钮
- 支持格式：
  - **FASTA**：纯文本序列，适用于下游分析
  - **RTF**：富文本格式，保留颜色标注，适用于可视化分析

---

## 2. 数据库架构特点

### 2.1 数据库组织方式

Ensembl 采用**多数据库分离架构**：

#### 2.1.1 按物种分离
- 每个物种拥有**独立的数据库**，命名格式：`<species>_<database_type>_<release>_<assembly>`
- 例如：`homo_sapiens_core_116_38`（人类核心数据库，release 116，GRCh38）
- 不同物种的数据库完全隔离，确保数据独立性

#### 2.1.2 按数据类型分离
每个物种内部，数据按功能域分为多个数据库：

| 数据库类型 | 说明 | 示例表 |
|-----------|------|--------|
| **Core** | 基因注释核心数据 | gene, transcript, exon, translation |
| **Compara** | 比较基因组学 | homology, gene_tree, species_tree |
| **Variation** | 变异数据 | variation_feature, variation_set |
| **Regulation** | 调控元件 | regulatory_feature, motif_feature |
| **Funcgen** | 功能基因组学 | peak, regulatory_build |
| **Mart** | 数据挖掘优化 | 查询优化的 schema |

#### 2.1.3 Core Database 关键表结构

```
gene (1) ----< transcript (*) ----< exon_transcript (*) >---- exon (*)
    |                               |
    |                               >---- translation (0 or 1)
    |
gene_stable_id (1)
```

**核心表说明**：
- **gene**：基因基本信息（seq_region, start, end, strand, status, biotype）
- **transcript**：转录本信息，通过 gene_id 关联到 gene
- **exon**：外显子坐标信息
- **exon_transcript**：外显子-转录本关联表，rank 列表示 5' 到 3' 的顺序
- **translation**：翻译信息，描述 CDS 组成，seq_start/seq_end 指向起始和终止外显子
- **protein_feature**：蛋白质结构域特征（Pfam, InterPro 等）
- **stable_id_event**：稳定 ID 变更历史追踪

### 2.2 物种命名与 ID 前缀系统

#### 2.2.1 稳定 ID 前缀约定
Ensembl 使用**物种特定的前缀**来区分不同来源的 ID：

| 前缀 | 物种 | 示例 |
|------|------|------|
| ENSG/ENST/ENSP | Human (Homo sapiens) | ENSG00000139618 |
| ENSMUSG/ENSMUST/ENSMUSP | Mouse (Mus musculus) | ENSMUSG00000041147 |
| ENSDARG/ENSDART/ENSDARP | Zebrafish (Danio rerio) | ENSDARG00000104330 |
| FBgn | Fruit fly (Drosophila) | FBgn0002183 |

#### 2.2.2 ID 版本管理
- 稳定 ID 包含**版本号**，格式：`ENSG00000139618.19`
- 版本号在基因模型更新时递增
- 版本历史通过 `stable_id_event` 表追踪
- `gene_archive` 和 `peptide_archive` 表保存被删除或变更的快照

### 2.3 Assembly 与 Annotation 的分离

#### 2.3.1 坐标系统设计
- 外显子的染色体位置存储在**seq_region 坐标系**中
- 使用 **coord_system** 表管理多种坐标系（chromosome, scaffold, contig 等）
- **assembly** 表记录 contig 到染色体的组装映射关系
- **seq_region_mapping** 表记录不同 release 之间 seq_region 的变更

#### 2.3.2 组装变更的处理
- 当基因组组装更新时，外显子在 contig 级别的坐标保持不变
- 染色体坐标通过 assembly 表重新计算
- 这种设计使得基因注释可以"相对无痛"地在不同组装版本间迁移

### 2.4 Virtual Contig 架构

Ensembl 的核心设计创新之一是 **Virtual Contig (VC) 对象**：
- 将分散存储的基因组序列片段（contigs）抽象为连续的 DNA 序列
- 上层应用无需关心底层存储方式
- 支持 draft 基因组数据的无缝处理
- 使不同组装版本之间的切换"相对无痛"
- Features 始终存储在 raw contig 级别，VC 是"真正虚拟的"

---

## 3. 跨版本映射功能

### 3.1 归档站点系统（Archive Sites）

#### 3.1.1 归档站点命名规则
Ensembl 为每个 release 维护独立的**归档站点**，命名格式：
- `<month><year>.archive.ensembl.org`
- 例如：`jan2024.archive.ensembl.org`, `jul2023.archive.ensembl.org`

#### 3.1.2 可用归档版本示例

| 版本 | 日期 | 归档 URL |
|------|------|----------|
| GRCh37 | Feb 2014 | https://grch37.ensembl.org |
| Ensembl 111 | Jan 2024 | https://jan2024.archive.ensembl.org |
| Ensembl 110 | Jul 2023 | https://jul2023.archive.ensembl.org |
| Ensembl 109 | Feb 2023 | https://feb2023.archive.ensembl.org |
| ... | ... | ... |

- 从 Ensembl 74（2013年12月）开始，归档站点至少保留 **5 年**
- 每个 Ensembl Genomes 子站点也有独立的归档（如 `eg56-metazoa.ensembl.org`）

#### 3.1.3 归档访问方式
- 主页底部点击 `View in archive site`
- 通过 biomaRt 的 `listEnsemblArchives()` 函数获取列表
- 通过 REST API 的 archive 端点访问

### 3.2 坐标转换工具（Assembly Mapper）

#### 3.2.1 REST API 坐标转换
```
GET /map/:species/:asm_one/:region/:asm_two
```

示例：将 GRCh37 坐标转换为 GRCh38
```
GET /map/human/GRCh37/13:32890000-32900000/GRCh38
```

#### 3.2.2 支持的转换类型
- **Assembly-to-assembly**：不同基因组组装版本间的坐标转换
- **Translation-to-genomic**：蛋白质坐标到基因组坐标的转换
- **CDNA-to-genomic**：cDNA 坐标到基因组坐标的转换

#### 3.2.3 跨版本 ID 映射
- **ID History 页面**：追踪基因、转录本、蛋白质 ID 的变更历史
- **stable_id_event 表**：记录每次 mapping session 中的 ID 变更事件
  - 删除的 ID
  - 新创建的 ID
  - ID 之间的关联关系
- **mapping_session 表**：记录映射会话的详细信息（旧数据库和新数据库）

### 3.3 GRCh37 专用站点

Ensembl 维护一个**永久性的 GRCh37 专用站点**（`https://grch37.ensembl.org`）：
- 为临床和研究社区保留对旧版参考基因组的访问
- 使用独立的 REST API 端点（`https://grch37.rest.ensembl.org`）
- 在基因页面上显示到 GRCh37 坐标的映射链接

### 3.4 数据持久性策略

- **FTP 归档**：所有历史 release 的数据文件永久保留在 FTP 站点
- **数据库访问**：通过 Perl API 和 REST API 可访问所有历史数据
- **缓存文件**：VEP 等工具的缓存文件按 release 归档
- **Pre!Site**：新基因组组装的预览站点（`http://pre.ensembl.org`），提供基础注释

---

## 4. 搜索和浏览设计

### 4.1 搜索框设计（Psychic Search）

#### 4.1.1 搜索界面
Ensembl 主页的搜索框设计简洁但功能强大：
- **物种选择下拉框**：可选择特定物种或"All species"
- **搜索输入框**：支持自由文本输入
- **搜索按钮**：触发搜索
- **搜索示例链接**：如 `BRCA2`, `rat 5:62797383-63627669`, `rs699`, `coronary heart disease`

#### 4.1.2 支持的查询类型

| 查询类型 | 示例 | 说明 |
|----------|------|------|
| **基因符号** | BRCA2, TP53 | HGNC 基因符号 |
| **Ensembl ID** | ENSG00000139618 | 稳定 ID |
| **染色体区域** | 13:32315086-32400268 | 坐标范围 |
| **SNP rsID** | rs699, rs1805007 | dbSNP 参考 SNP ID |
| **表型/疾病** | coronary heart disease | 与基因或变异关联的表型 |
| **蛋白质 ID** | P51587 | UniProt ID |
| **GO 术语** | GO:0006915 | Gene Ontology ID |
| **关键词** | apoptosis, kinase | 功能描述关键词 |

#### 4.1.3 搜索结果展示
- 按物种分组显示结果
- 热门物种（人、小鼠、斑马鱼）排在最前
- 左侧过滤器可按物种或特征类型限制结果
- 每个结果包含基因名称、描述、位置等信息
- 点击基因名称或 ID 进入 Gene 标签页

### 4.2 BioMart 数据挖掘工具

BioMart 是 Ensembl 提供的**无需编程**的数据批量提取工具，采用三步查询模式：

#### 4.2.1 选择 Mart 数据库和数据集
- **数据库类型**：Ensembl Genes, Ensembl Variation, Ensembl Regulation, Vega
- **数据集**：选择物种（如 `Homo sapiens genes`）

#### 4.2.2 设置过滤器（Filters）
过滤器定义查询的约束条件（输入）：
- **Region**：染色体、起始/终止位置
- **GENE**：基因类型（protein_coding, lncRNA 等）
- **ID LIST LIMIT**：限制特定的 ID 列表
- **GO**：GO 术语过滤
- **PROTEIN DOMAINS**：蛋白质结构域过滤
- **MULTI SPECIES COMPARISONS**：同源基因相关过滤
- **VARIATION**：变异相关过滤

#### 4.2.3 选择属性（Attributes）
属性定义输出列（输出）：
- **Features**：Ensembl Gene ID, Transcript ID, Protein ID 等
- **External**：外部数据库 ID（RefSeq, UniProt, HGNC 等）
- **Structures**：外显子/内含子结构信息
- **Sequences**：各种序列类型（cDNA, CDS, 肽段, UTR 等）
- **Homology**：同源基因信息
- **Protein Domains**：InterPro, Pfam 等结构域
- **Statistics**：统计信息（% GC content, exon count 等）

#### 4.2.4 结果预览和导出
- **Count 按钮**：预览匹配记录数
- **Results 按钮**：预览结果（默认前 10 行）
- **导出格式**：TSV, CSV, XLS, FASTA, HTML

### 4.3 过滤和排序功能

#### 4.3.1 表格级过滤
- **实时文本过滤**：在 Filter 输入框中输入关键词实时过滤
- **下拉选择过滤**：如按后果类型、MAF 范围等
- **多条件组合**：支持多个过滤条件同时生效

#### 4.3.2 列显示控制
- **Show/hide columns**：自定义显示哪些列
- **列重排序**：通过拖拽调整列顺序

#### 4.3.3 分页设计
- 支持每页显示 10/25/50/100/All 条记录
- 页码导航

---

## 5. REST API 设计

### 5.1 API 整体架构

Ensembl REST API 遵循 **RESTful 设计原则**，提供**语言无关**的 Ensembl 数据访问。

#### 5.1.1 基础信息
- **基础 URL**：`https://rest.ensembl.org`
- **GRCh37 专用**：`https://grch37.rest.ensembl.org`
- **当前版本**：与 Ensembl Release 同步（当前 Release 116）
- **速率限制**：匿名用户 15 请求/秒（约 54,000 请求/小时）
- **支持格式**：JSON, XML, FASTA, YAML, JSONP
- **HTTP 方法**：GET（单个查询）, POST（批量查询）

#### 5.1.2 响应头信息
API 返回 HTTP 响应头描述速率限制状态：
- `X-RateLimit-Limit`：速率上限
- `X-RateLimit-Remaining`：剩余请求数
- `X-RateLimit-Reset`：限制重置时间
- `Retry-After`：超限后建议等待时间

### 5.2 端点分类体系

REST API 将功能组织为 **17 个端点类别**：

| 类别 | 说明 | 示例端点 |
|------|------|----------|
| **Information** | 物种、组装等元数据 | `/info/species`, `/info/assembly/:species` |
| **Lookup** | ID 查找和解析 | `/lookup/id/:id`, `/lookup/symbol/:species/:symbol` |
| **Archive** | 归档 ID 查询 | `/archive/id/:id` |
| **Sequence** | 序列获取 | `/sequence/id/:id`, `/sequence/region/:species/:region` |
| **Comparative Genomics** | 同源基因和基因树 | `/homology/id/:id`, `/gene_tree/id/:id` |
| **Cross References** | 外部数据库交叉引用 | `/xrefs/id/:id`, `/xrefs/symbol/:species/:symbol` |
| **Ontologies & Taxonomy** | GO 和分类学 | `/ontology/id/:id`, `/taxonomy/id/:id` |
| **Mapping** | 坐标转换 | `/map/:species/:asm_one/:region/:asm_two` |
| **Variation** | 变异查询 | `/variation/:species/:id`, `/vep/:species/hgvs/:hgvs` |
| **VEP** | 变异效应预测 | `/vep/:species/region/:region/:allele/` |
| **Phenotype annotations** | 表型注释 | `/phenotype/gene/:species/:gene` |
| **Regulation** | 调控数据 | `/regulatory/species/:species/id/:id` |
| **Overlap** | 区域重叠查询 | `/overlap/id/:id`, `/overlap/region/:species/:region` |
| **Transcript Haplotypes** | 转录本单倍型 | `/transcript_haplotypes/:species/:id` |
| **GA4GH** | 全球基因组与健康联盟标准 | `/ga4gh/beacon`, `/ga4gh/variants/:id` |
| **Variant Recoder** | 变异标识符转换 | `/variant_recoder/:species/:id` |

### 5.3 端点设计模式

#### 5.3.1 URL 设计
- **资源导向**：`/sequence/id/:id` 而非 `getSequenceById`
- **层级结构**：`/species/:species/id/:id` 表达从属关系
- **动作通过 HTTP 方法**：GET 获取, POST 批量获取
- **参数通过 URL 路径和查询字符串**：
  - 路径参数：物种名、ID
  - 查询参数：`?expand=1`, `?content-type=application/json`

#### 5.3.2 批量查询
- 支持 POST 方法批量提交 ID 列表
- 示例：`POST /lookup/id`，请求体为 JSON 数组
- 显著提高批量数据获取效率

#### 5.3.3 文档设计
每个端点配有自动生成的文档页面，包含：
- 参数说明（名称、类型、描述、默认值、示例值）
- 必需/可选参数标记
- 示例 URL 和输出
- 多语言示例代码（Perl, Python, Ruby, Java, Curl, Wget）
- 响应格式说明

### 5.4 API 设计哲学

- **语言无关**：任何支持 HTTP 的语言都可以使用
- **只读访问**：API 仅提供数据查询，不支持写入
- **与 Archive 同步**：API 版本随 Ensembl release 更新，归档版本的 API 也保留
- **稳定性优先**：端点设计追求长期稳定，变更时提供版本迁移指南
- **网络延迟限制**：不适合大规模数据挖掘（推荐 BioMart 或 Perl API）
- **无镜像**：仅有主服务器，无地理分布式镜像
- **与 Ensembl 对象模型对齐**：端点设计反映底层数据库的对象关系

---

## 6. 对 OmicHub 数据库模块的设计启示

### 6.1 页面布局设计建议

#### 6.1.1 三级导航体系
借鉴 Ensembl 的 **Breadcrumb + Top Tabs + Left Menu** 三级导航：
- **面包屑**：物种 > 基因组版本 > 基因/区域 > 具体视图
- **顶部标签页**：按实体类型组织（Gene, Transcript, Variant, Protein）
- **左侧菜单**：每个实体类型下的信息子视图

#### 6.1.2 基因摘要面板
设计一个**信息密度高**的基因摘要区，包含：
- 基因名称、ID、描述
- 基因组位置（含基因组版本）
- 关键统计数据（转录本数、同源基因数、变异数）
- 外部数据库交叉引用（使用徽章/图标快速识别）
- 跨版本映射信息（如 GRCh37/GRCh38 坐标）

#### 6.1.3 转录本表格设计
- 使用 Flags 系统（小图标）标注重要转录本
- 支持展开/折叠
- 包含关键列：ID、名称、生物型、长度、蛋白质信息
- 支持排序和过滤

### 6.2 数据架构设计建议

#### 6.2.1 数据库分离策略
- **按物种分离数据库**：避免数据混杂，便于独立更新
- **按数据类型分离**：Core（基因注释）、Variation（变异）、Compara（比较基因组）
- **使用稳定 ID 系统**：确保跨版本的数据可追踪性
- **ID 版本管理**：在 ID 后附加版本号，追踪注释变更

#### 6.2.2 坐标系管理
- 设计**灵活的坐标系表**，支持多种坐标系（chromosome, scaffold, contig）
- 将特征存储在稳定的坐标系（如 contig），通过映射表转换到染色体坐标
- 支持不同基因组组装版本间的坐标转换

### 6.3 跨版本管理设计建议

#### 6.3.1 归档系统设计
- 为每个主要 release 保留**可访问的归档**
- 提供归档版本的 API 和数据库访问
- 维护稳定 ID 历史表，追踪 ID 的创建、删除和关联

#### 6.3.2 坐标转换
- 提供**REST API 端点**进行跨组装版本坐标转换
- 在基因详情页显示主要基因组版本的坐标映射

### 6.4 搜索系统设计建议

#### 6.4.1 多类型搜索
- 支持基因符号、ID、染色体区域、变异 ID、表型术语等多种查询类型
- 提供搜索示例引导用户
- 搜索结果按物种和类型分组

#### 6.4.2 数据批量导出
- 设计类似 BioMart 的**过滤器-属性**查询界面
- 支持非编程用户进行复杂的数据提取
- 提供多种导出格式（TSV, CSV, FASTA）

### 6.5 交互设计建议

#### 6.5.1 表格交互
- 实时文本过滤
- 列显示/隐藏控制
- 分页（支持自定义每页条数）
- 表格数据导出

#### 6.5.2 可视化集成
- 嵌入基因组浏览器视图
- 可配置的轨道系统
- 外显子-内含子结构可视化

#### 6.5.3 外部数据链接
- 每个外部引用都提供**超链接**到源数据库
- 使用统一的图标系统表示不同的外部数据库

### 6.6 API 设计建议

#### 6.6.1 端点组织
- 按功能域组织端点（/genes, /transcripts, /variants, /homology）
- 使用 RESTful URL 设计（资源导向）
- 支持 GET 和 POST 方法
- 提供批量查询能力

#### 6.6.2 文档和示例
- 每个端点提供详细的参数说明
- 提供多语言的示例代码
- 说明速率限制和使用最佳实践

---

## 附录：参考资源

1. **Ensembl 官方网站**: https://www.ensembl.org/
2. **Ensembl REST API 文档**: https://rest.ensembl.org/documentation
3. **Ensembl 训练材料**: https://training.ensembl.org/
4. **Ensembl Core Schema 文档**: http://www.ensembl.org/info/docs/api/core/core_schema.html
5. **Ensembl 论文（2009）**: Cunningham F et al. Ensembl 2009. Nucleic Acids Res.
6. **Ensembl REST API 论文**: Yates A et al. The Ensembl REST API. Bioinformatics 2015.
7. **Ensembl BioMart 论文**: Smedley D et al. Ensembl BioMarts. BMC Genomics 2015.
8. **Ensembl 比较基因组学**: Herrero J et al. Ensembl comparative genomics resources. Nucleic Acids Res. 2016.
9. **Ensembl Core 软件库**: Stabenau A et al. The Ensembl Core Software Libraries. Genome Biology 2004.
10. **Ensembl Variant Effect Predictor**: McLaren W et al. The Ensembl Variant Effect Predictor. Genome Biology 2016.
