# OmicHub 数据库模块 - 产品需求文档 (PRD)

## 1. 模块概述

### 1.1 模块名称变更
- **原名**：参考基因组
- **新名**：数据库

### 1.2 模块定位
OmicHub 平台的核心数据基础设施模块，提供基因组数据的集中管理、存储、查询和可视化能力。支持多物种、多版本基因组数据的统一管理，以及基因级信息的深度浏览和跨版本映射。

### 1.3 功能范围
| 功能 | 说明 |
|------|------|
| 数据库管理 | 支持 FA（序列）、GFF（注释）、GO（功能注释）、KEGG（通路）数据的注册和管理 |
| 基因浏览 | 物种/版本选择 → 基因搜索 → 基因详情查看 |
| 跨版本映射 | 同一物种不同基因组版本间的基因坐标和信息映射 |
| 可视化集成 | 基因结构可视化、通路图展示 |

---

## 2. 数据库架构设计

### 2.1 数据模型（参考 GenBank/Ensembl 设计）

```
Species (物种)
  ├── id, scientific_name, common_name, taxonomy_id
  └── GenomeVersions[] (基因组版本)
        ├── version_id, version_name (e.g., "v11"), assembly_name
        ├── is_default, release_date, description
        ├── status (active/archived)
        └── DataFiles[] (数据文件)
              ├── file_type: fasta | gff | go | kegg
              ├── file_path, index_path
              ├── db_path (SQLite 数据库路径)
              └── build_status: pending | building | ready | error
```

### 2.2 基因中心数据模型（Gene-Centered）

参考 NCBI GenBank 的基因中心化架构，以 Gene 为核心实体辐射关联所有数据：

```
Gene (核心实体)
  ├── gene_id (内部唯一标识符)
  ├── gene_symbol (基因符号, e.g., "BRCA2")
  ├── gene_name (基因全称)
  ├── description (功能描述)
  ├── species_id, genome_version_id
  ├── location: {chromosome, start, end, strand}
  ├── aliases[] (别名列表)
  └── 关联数据:
      ├── Transcripts[] (转录本)
      │     ├── transcript_id, biotype, length
      │     ├── cds: {start, end, length_aa}
      │     └── exons[]: {start, end, rank}
      ├── GOAnnotations[] (GO 注释)
      │     ├── go_id, term, namespace (BP/MF/CC)
      │     └── evidence_code, source
      ├── KEGGAnnotations[] (KEGG 通路)
      │     ├── pathway_id, pathway_name, category
      │     └── ko_id, ec_number
      └── Sequence (序列数据)
            ├── genomic_seq (基因组序列)
            ├── cds_seq (编码序列)
            └── protein_seq (蛋白质序列)
```

### 2.3 跨版本映射表

```sql
-- 基因版本映射表
CREATE TABLE gene_version_mapping (
    id SERIAL PRIMARY KEY,
    species_id VARCHAR(50) NOT NULL,
    source_version VARCHAR(20) NOT NULL,    -- 源版本 e.g., "v8"
    target_version VARCHAR(20) NOT NULL,    -- 目标版本 e.g., "v11"
    source_gene_id VARCHAR(100) NOT NULL,
    target_gene_id VARCHAR(100),
    source_location VARCHAR(100),           -- chr:start-end
    target_location VARCHAR(100),
    mapping_quality FLOAT,                  -- 0-1 映射质量
    mapping_tool VARCHAR(50),               -- liftoff/crossmap
    is_primary_mapping BOOLEAN DEFAULT true,
    created_at TIMESTAMP
);
```

---

## 3. YAML 配置规范

### 3.1 数据库注册配置文件

管理员在本地构建数据库后，通过修改 `databases.yaml` 文件注册数据库：

```yaml
# databases.yaml - OmicHub 数据库注册配置
# 位置: /data/omichub_data/config/databases.yaml

version: "1.0"

# 物种列表
species:
  - id: "Lsat"                          # 物种内部ID（唯一）
    scientific_name: "Lactuca sativa"    # 学名
    common_name: "生菜"                  # 中文名
    taxonomy_id: "4236"                  # NCBI Taxonomy ID
    description: "生菜参考基因组"         # 描述
    icon: "🥬"                          # 图标/emoji

    # 基因组版本列表
    genome_versions:
      - version_id: "Lsat_v11"           # 版本唯一ID
        version_name: "v11"              # 显示名称
        assembly_name: "Lsat.1.v11"      # 组装名称
        is_default: true                 # 是否为默认版本
        status: "active"                 # active | archived
        release_date: "2023-05"
        description: "最新版，染色体级组装"
        stats:                           # 统计信息
          chromosomes: 9
          total_genes: 38678
          protein_coding: 34210
          genome_size: "2.69 Gb"
        
        # 数据文件配置
        data_files:
          fasta:                         # 参考基因组序列
            path: "/data/omichub_data/db/Lsat/v11/Lsat.1.v11.fa"
            index_path: "/data/omichub_data/db/Lsat/v11/Lsat.1.v11.fa.fai"
            format: "fasta"
            build_required: true
            
          gff:                           # 基因注释
            path: "/data/omichub_data/db/Lsat/v11/Lsat.1.v11.gff3"
            db_path: "/data/omichub_data/db/Lsat/v11/annotation.db"
            format: "gff3"
            build_required: true
            build_tool: "gffutils"        # gffutils | custom
            
          go:                            # GO 注释
            path: "/data/omichub_data/db/Lsat/v11/go_annotations.tsv"
            db_path: "/data/omichub_data/db/Lsat/v11/go.db"
            format: "tsv"
            build_required: true
            build_tool: "custom"
            
          kegg:                          # KEGG 注释
            path: "/data/omichub_data/db/Lsat/v11/kegg_annotations.tsv"
            db_path: "/data/omichub_data/db/Lsat/v11/kegg.db"
            format: "tsv"
            build_required: true
            build_tool: "custom"

      - version_id: "Lsat_v8"
        version_name: "v8"
        assembly_name: "Lsat.1.v8"
        is_default: false
        status: "active"
        release_date: "2020-11"
        description: "稳定版"
        stats:
          chromosomes: 9
          total_genes: 35241
          protein_coding: 31100
          genome_size: "2.65 Gb"
        data_files:
          fasta:
            path: "/data/omichub_data/db/Lsat/v8/Lsat.1.v8.fa"
            index_path: "/data/omichub_data/db/Lsat/v8/Lsat.1.v8.fa.fai"
            format: "fasta"
            build_required: true
          gff:
            path: "/data/omichub_data/db/Lsat/v8/Lsat.1.v8.gff3"
            db_path: "/data/omichub_data/db/Lsat/v8/annotation.db"
            format: "gff3"
            build_required: true
            build_tool: "gffutils"

    # 跨版本映射配置
    version_mappings:
      - source: "Lsat_v8"
        target: "Lsat_v11"
        mapping_file: "/data/omichub_data/db/Lsat/mappings/v8_to_v11_mapping.tsv"
        mapping_tool: "liftoff"
        build_required: true

  # 更多物种...
  - id: "Ath"
    scientific_name: "Arabidopsis thaliana"
    common_name: "拟南芥"
    taxonomy_id: "3702"
    description: "模式植物拟南芥"
    icon: "🌱"
    genome_versions:
      - version_id: "Ath_TAIR10"
        version_name: "TAIR10"
        ...

# 全局设置
settings:
  db_storage_path: "/data/omichub_data/db"      # 数据库存储根目录
  default_species: "Lsat"                        # 默认物种
  enable_version_mapping: true                   # 启用版本映射
  go_obo_path: "/data/omichub_data/db/go/go-basic.obo"  # GO 本体文件
  kegg_cache_ttl: 86400                          # KEGG 缓存时间(秒)
```

### 3.2 数据库构建流程

```
管理员操作流程:
1. 准备原始数据文件（FA, GFF, GO, KEGG）
2. 上传到服务器指定目录
3. 编辑 databases.yaml 注册数据库配置
4. 运行构建脚本：python build_databases.py --config databases.yaml
5. 构建脚本自动：
   a. 创建 fai 索引（samtools faidx）
   b. 创建 GFF SQLite 数据库（gffutils）
   c. 创建 GO 关联数据库
   d. 创建 KEGG 通路数据库
   e. 运行 Liftoff 生成版本映射（如配置）
6. 前端自动检测新的数据库配置并加载
```

---

## 4. 前端页面设计

### 4.1 整体风格

**与首页（OmicHub 星尘工作站）风格统一：**
- 蓝紫渐变主题色（延续首页 Hero 区域的渐变风格）
- 星空粒子背景效果（可选，仅在页面顶部区域）
- 圆角卡片式布局
- 白色内容卡片 + 浅灰背景
- 统一的阴影和间距系统

### 4.2 页面路由结构

```
/database                    # 数据库主页（数据库列表）
/database/:speciesId         # 物种基因组版本列表
/database/:speciesId/:versionId   # 基因浏览器/搜索页
/database/:speciesId/:versionId/gene/:geneId   # 基因详情页
/database/:speciesId/mapping # 跨版本映射工具
```

### 4.3 页面 1: 数据库主页 (/database)

**参考当前"参考基因组库"页面，扩展为数据库卡片列表。**

#### 布局设计
```
+----------------------------------------------------------+
|  Hero Banner (蓝紫渐变，星空粒子背景)                      |
|  🧬 数据库                                                |
|  管理基因组数据，探索基因奥秘 ✨ 让科研变得丝滑起来～        |
+----------------------------------------------------------+
|  搜索栏: [🔍 搜索物种、基因组版本...]  [+ 注册新数据库]     |
+----------------------------------------------------------+
|  筛选标签: [全部] [植物] [动物] [微生物] [我的收藏]         |
+----------------------------------------------------------+
|  +------------------------+  +------------------------+   |
|  | 🥬 生菜                |  | 🌱 拟南芥              |   |
|  | Lactuca sativa         |  | Arabidopsis thaliana   |   |
|  |                        |  |                        |   |
|  | v11 🏷️最新版 染色体级  |  | TAIR10 🏷️稳定         |   |
|  | Lsat.1.v11             |  |                        |   |
|  | 9 条染色体 · 38,678 基因|  | 5 条染色体 · 27,655 基因|  |
|  | 2.69 Gb · 2023-05 发布 |  | 135 Mb · 2010 发布     |   |
|  |                        |  |                        |   |
|  | [查看详情] [设为默认]   |  | [查看详情] [设为默认]   |   |
|  +------------------------+  +------------------------+   |
|  +------------------------+  +------------------------+   |
|  | 🍅 番茄                |  | 🌾 水稻                |   |
|  | ...                    |  | ...                    |   |
|  +------------------------+  +------------------------+   |
+----------------------------------------------------------+
```

#### 数据库卡片组件
- **图标区**：物种 emoji 图标 + 默认版本标签
- **信息区**：学名、中文名、版本列表、统计数据
- **操作区**："查看详情"按钮、"设为默认"按钮
- **状态标识**：构建中/就绪/错误 状态标签
- **渐变底边**：每张卡片底部有蓝紫渐变线条装饰

### 4.4 页面 2: 基因浏览器页 (/database/:speciesId/:versionId)

**参考 Ensembl 的 Gene 标签页 + GenBank 的搜索设计。**

#### 布局设计（三栏式）
```
+--------------------------------------------------------------------------+
| 面包屑: 数据库 > 生菜 (Lactuca sativa) > v11                               |
+--------------------------------------------------------------------------+
| 物种信息卡片                                                              |
| 🥬 生菜 Lactuca sativa | v11 Lsat.1.v11 | 9 条染色体 | 38,678 基因       |
+--------------------------------------------------------------------------+
| 版本切换: [v11 ●] [v8] [映射工具]                                         |
+--------------------------------------------------------------------------+
| 搜索栏: [🔍 搜索基因名称、ID、染色体位置... ]  [高级搜索]                  |
+--------------------------------------------------------------------------+
| 左侧面板 (20%)      | 主内容区 (80%)                                      |
|                     |                                                     |
| 筛选器               | 基因列表 / 基因组浏览器                             |
| ┌───────────────┐  |                                                     |
| │ 基因类型       |  |  列表视图:                                           |
| │ ☑ 蛋白编码     |  |  +----------------------------------------------+  |
| │ ☑ 非编码RNA    |  |  | Gene ID    | Symbol | 位置          | 类型    |  |
| │ ☑ 假基因       |  |  |------------|--------|---------------|---------|  |
| │                |  |  | Lsat_1g001 | GeneA  | chr1:100-500  | coding  |  |
| │ 染色体         |  |  | Lsat_1g002 | GeneB  | chr1:800-1200 | coding  |  |
| │ ☑ chr1         |  |  | ...        | ...    | ...           | ...     |  |
| │ ☑ chr2         |  |  +----------------------------------------------+  |
| │ ...            |  |                                                     |
| │                |  |  或浏览器视图 (JBrowse 2 嵌入):                      |
| │ GO 分类        |  |  +----------------------------------------------+  |
| │ ☑ 生物过程     |  |  |  [JBrowse 2 Genome Browser 嵌入区域]          |  |
| │ ☑ 分子功能     |  |  |                                               |  |
| │ ☑ 细胞组分     |  |  +----------------------------------------------+  |
| └───────────────┘  |                                                     |
+--------------------------------------------------------------------------+
```

#### 搜索功能设计（参考 Ensembl Psychic Search）
- 支持基因符号搜索
- 支持 Gene ID 搜索
- 支持染色体位置搜索（如 chr1:1000-5000）
- 搜索建议下拉列表
- 搜索结果高亮

#### 基因列表组件
- 表格列：Gene ID, Symbol, Name, Location, Type, Length, 操作
- 可排序、可筛选
- 分页显示
- 点击行进入基因详情页

### 4.5 页面 3: 基因详情页 (/database/:speciesId/:versionId/gene/:geneId)

**核心页面！参考 NCBI GenBank + Ensembl 基因页面设计。**

#### 整体布局（参考 Ensembl 三级导航 + GenBank 信息分区）
```
+--------------------------------------------------------------------------+
| 面包屑: 数据库 > 生菜 > v11 > Gene: Lsat_1g001                            |
+--------------------------------------------------------------------------+
| 顶部标签导航: [Summary] [Transcripts] [GO Annotations] [KEGG] [Sequence] |
+--------------------------------------------------------------------------+
```

#### Tab 1: Summary（基因摘要）
```
+--------------------------------------------------------------------------+
| 基因摘要卡片 (蓝紫渐变顶部边框)                                            |
+--------------------------------------------------------------------------+
| 基因符号: Lsat_1g001                                                      |
| 基因名称: Lsat_1g001 (hypothetical protein)                               |
| 基因类型: protein_coding                                                  |
| 位置: chr1:1,234,567-1,235,890 (+ strand)                                |
| 长度: 1,324 bp | 外显子数: 5 | 转录本数: 1                               |
|                                                                           |
| 版本映射: v11 chr1:1,234,567-1,235,890 ↔ v8 chr1:1,198,234-1,199,557    |
|           [在 v8 中查看此基因]                                            |
+--------------------------------------------------------------------------+
| 功能描述                                                                  |
| This gene encodes a hypothetical protein involved in...                   |
+--------------------------------------------------------------------------+
| 邻接基因图谱 (水平箭头图)                                                  |
| [← GeneA] [← GeneB] [→ Lsat_1g001 →] [← GeneC] [→ GeneD]               |
|  点击箭头可跳转到对应基因                                                  |
+--------------------------------------------------------------------------+
| 基因结构可视化 (外显子/内含子图)                                            |
| ├────■━━━━■━━━━■━━━━■━━━━■────┤  (■=外显子, ━=内含子)                  |
| 5'UTR  CDS        CDS       3'UTR                                        |
+--------------------------------------------------------------------------+
```

#### Tab 2: Transcripts（转录本信息，参考 Ensembl 转录本表格）
```
+--------------------------------------------------------------------------+
| 转录本列表                                                                 |
+------+-----------+------------------+------+---------+-------------------+
| ID   | Biotype   | Length (bp)      | Exons| CDS(aa) | Flags             |
+------+-----------+------------------+------+---------+-------------------+
| t001 | protein_coding | 1,324       | 5    | 312     | ⭐ Canonical       |
+------+-----------+------------------+------+---------+-------------------+
|                                                                           |
| 外显子结构图:                                                              |
| Transcript t001: ├─E1─┼─E2─┼─E3─┼─E4─┼─E5─┤                             |
|                  [5'UTR][====CDS====][3'UTR]                             |
+--------------------------------------------------------------------------+
```

#### Tab 3: GO Annotations（GO 功能注释，参考 GenBank GO 展示）
```
+--------------------------------------------------------------------------+
| 分子功能 (Molecular Function)                                              |
+------------+--------------------------+---------------+------------------+
| GO ID      | Term                     | Evidence      | Source           |
+------------+--------------------------+---------------+------------------+
| GO:0005524 | ATP binding              | IEA           | InterPro         |
| GO:0004674 | protein serine/threonine | ISS           | UniProt          |
|            | kinase activity            |               |                  |
+------------+--------------------------+---------------+------------------+
|                                                                           |
| 生物学过程 (Biological Process)                                            |
+------------+--------------------------+---------------+------------------+
| GO:0006468 | protein phosphorylation  | IEA           | InterPro         |
| GO:0006355 | regulation of transcrip..| IEA           | Ensembl          |
+------------+--------------------------+---------------+------------------+
|                                                                           |
| 细胞组分 (Cellular Component)                                              |
+------------+--------------------------+---------------+------------------+
| GO:0005634 | nucleus                  | IEA           | InterPro         |
+------------+--------------------------+---------------+------------------+
+--------------------------------------------------------------------------+
```

#### Tab 4: KEGG Pathways（KEGG 通路注释）
```
+--------------------------------------------------------------------------+
| KEGG 通路注释                                                              |
+---------------+---------------------------+------------------------------+
| Pathway ID    | Pathway Name              | Genes in Pathway             |
+---------------+---------------------------+------------------------------+
| Lsa00010      | Glycolysis / Gluconeogen..| 45 genes                     |
| Lsa00130      | Ubiquinone and other ter..| 23 genes                     |
| Lsa04075      | Plant hormone signal tran..| 89 genes                     |
+---------------+---------------------------+------------------------------+
|                                                                           |
| 通路图预览 (KEGG API 获取图片):                                            |
| +------------------------------------------------------+                 |
| | [KEGG Pathway Map with gene highlighted in red]      |                 |
| +------------------------------------------------------+                 |
+--------------------------------------------------------------------------+
```

#### Tab 5: Sequence（序列信息，参考 GenBank 序列区）
```
+--------------------------------------------------------------------------+
| 序列下载选项                                                               |
| [Genomic DNA] [cDNA] [CDS] [Protein]                                     |
|                                                                           |
| FASTA 格式预览:                                                           |
| >Lsat_1g001 | Lactuca sativa chr1:1234567-1235890 (+)                   |
| ATGCGATCGATCGATCGATCGATCGATCGATCGATCGATCG...                             |
|                                                                           |
| [复制序列] [下载 FASTA] [下载 GenBank]                                    |
+--------------------------------------------------------------------------+
```

### 4.6 页面 4: 跨版本映射工具 (/database/:speciesId/mapping)

```
+--------------------------------------------------------------------------+
| 面包屑: 数据库 > 生菜 > 基因组版本映射                                      |
+--------------------------------------------------------------------------+
| 版本映射工具                                                                |
|                                                                           |
| 源版本: [v8 ▼]  ===== Liftoff =====>  目标版本: [v11 ▼]                  |
|                                                                           |
| 输入方式: [基因列表] [染色体区域] [上传文件]                                |
| ┌──────────────────────────────────────────────┐                         |
| | 输入基因ID (每行一个，或逗号分隔):             |                         |
| | Lsat_1g001                                  |                         |
| | Lsat_1g002                                  |                         |
| | Lsat_2g100                                  |                         |
| └──────────────────────────────────────────────┘                         |
| [开始映射]                                                                 |
|                                                                           |
| 映射结果:                                                                  |
+------------+----------------------------+----------------------------+-----+
| Source Gene| v8 Location                | v11 Location               | Q   |
+------------+----------------------------+----------------------------+-----+
| Lsat_1g001 | chr1:1198234-1199557       | chr1:1234567-1235890       |0.98 |
| Lsat_1g002 | chr1:2456789-2457890       | chr1:2678901-2680002       |0.95 |
| Lsat_2g100 | chr2:5678901-5681234       | chr2:6123456-6125789       |0.87 |
+------------+----------------------------+----------------------------+-----+
| [导出结果] [在浏览器中查看]                                                |
+--------------------------------------------------------------------------+
```

---

## 5. API 设计

### 5.1 REST API 端点

```
# 物种和数据库管理
GET    /api/database/species                          # 获取所有物种列表
GET    /api/database/species/:speciesId               # 获取物种详情
GET    /api/database/species/:speciesId/versions      # 获取基因组版本列表
GET    /api/database/species/:speciesId/versions/:versionId  # 获取版本详情

# 基因搜索和查询
GET    /api/database/species/:speciesId/versions/:versionId/search?q=...  # 基因搜索
GET    /api/database/species/:speciesId/versions/:versionId/genes         # 基因列表
GET    /api/database/species/:speciesId/versions/:versionId/genes/:geneId # 基因详情

# 基因关联数据
GET    /api/database/genes/:geneId/transcripts        # 转录本列表
GET    /api/database/genes/:geneId/go                 # GO 注释
GET    /api/database/genes/:geneId/kegg               # KEGG 通路
GET    /api/database/genes/:geneId/sequence           # 序列数据

# 版本映射
GET    /api/database/species/:speciesId/mappings/:sourceVer/:targetVer    # 获取映射关系
POST   /api/database/mapping/convert                # 坐标转换
GET    /api/database/genes/:geneId/mapping?target=versionId               # 基因版本映射

# JBrowse 2 配置
GET    /api/database/species/:speciesId/versions/:versionId/jbrowse-config  # JBrowse 2 配置
```

### 5.2 关键 API 响应格式

```json
// 基因详情响应
{
  "gene_id": "Lsat_1g001",
  "gene_symbol": "Lsat_1g001",
  "gene_name": "hypothetical protein",
  "description": "This gene encodes a hypothetical protein...",
  "gene_type": "protein_coding",
  "species": {
    "id": "Lsat",
    "scientific_name": "Lactuca sativa",
    "common_name": "生菜"
  },
  "genome_version": {
    "version_id": "Lsat_v11",
    "version_name": "v11",
    "assembly_name": "Lsat.1.v11"
  },
  "location": {
    "chromosome": "chr1",
    "start": 1234567,
    "end": 1235890,
    "strand": "+",
    "display": "chr1:1,234,567-1,235,890 (+)"
  },
  "aliases": ["LOC123456", "gene-LOC123456"],
  "transcript_count": 1,
  "exon_count": 5,
  "transcripts": [...],
  "go_annotations": [...],
  "kegg_annotations": [...],
  "version_mapping": {
    "Lsat_v8": {
      "gene_id": "Lsat_1g001",
      "location": "chr1:1,198,234-1,199,557",
      "quality": 0.98
    }
  }
}
```

---

## 6. 组件清单

### 6.1 页面级组件
| 组件 | 路径 | 说明 |
|------|------|------|
| DatabaseHome | /database | 数据库主页，物种卡片列表 |
| GenomeBrowser | /database/:speciesId/:versionId | 基因浏览器/搜索页 |
| GeneDetail | /database/:speciesId/:versionId/gene/:geneId | 基因详情页 |
| VersionMapping | /database/:speciesId/mapping | 跨版本映射工具 |

### 6.2 共享组件
| 组件 | 说明 |
|------|------|
| SpeciesCard | 物种数据库卡片（渐变边框、统计信息） |
| GeneSearchBar | 基因搜索栏（支持多种查询类型） |
| GeneFilterPanel | 基因筛选面板（左侧） |
| GeneTable | 基因数据表格 |
| GeneSummaryCard | 基因摘要卡片（渐变顶部边框） |
| TranscriptTable | 转录本表格（参考 Ensembl Flags） |
| GOAnnotationTable | GO 注释表格 |
| KEGGPathwayTable | KEGG 通路表格 |
| SequenceViewer | 序列查看器 |
| ExonStructureChart | 外显子结构图（水平条形图） |
| NeighborGeneMap | 邻接基因图谱 |
| VersionBadge | 版本标签（最新版、稳定版等） |
| StatusBadge | 状态标签（就绪、构建中、错误） |
| BreadcrumbNav | 面包屑导航 |
| TabNavigation | 标签页导航 |

---

## 7. JBrowse 2 集成方案

### 7.1 嵌入方式
- 在基因浏览器页和基因详情页的 Summary Tab 中嵌入 JBrowse 2
- 使用 JBrowse 2 React 组件 `@jbrowse/react-linear-genome-view`
- 通过 API 动态生成 JBrowse 2 配置文件

### 7.2 数据准备
- FASTA: `samtools faidx` + `bgzip` → BgzipFastaAdapter
- GFF: `jbrowse sort-gff` → `bgzip` → `tabix` → Gff3TabixAdapter
- 文本搜索: `jbrowse text-index` → TrixTextSearchAdapter

---

## 8. 数据库构建脚本设计

### 8.1 构建流程
```python
# build_databases.py
# 读取 databases.yaml 配置
# 对每个数据库:
#   1. 检查原始文件是否存在
#   2. 根据 file_type 调用对应构建器
#   3. 更新构建状态
#   4. 生成构建报告

class DatabaseBuilder:
    def build_fasta(self, config):
        """构建 FA 索引: samtools faidx"""
        pass
    
    def build_gff(self, config):
        """构建 GFF 数据库: gffutils"""
        pass
    
    def build_go(self, config):
        """构建 GO 关联数据库"""
        pass
    
    def build_kegg(self, config):
        """构建 KEGG 通路数据库"""
        pass
    
    def build_mapping(self, config):
        """构建版本映射: Liftoff"""
        pass
```

---

## 9. 参考设计来源

| 功能 | 参考来源 | 借鉴点 |
|------|----------|--------|
| 基因详情页布局 | NCBI GenBank Gene Page | 信息分区、可折叠区域 |
| 三级导航体系 | Ensembl | 面包屑 + 标签页 + 左侧菜单 |
| 基因摘要卡片 | Ensembl Gene Summary | 信息密度高的摘要区 |
| 转录本表格 | Ensembl Transcript Table | Flags 系统、排序筛选 |
| GO 注释展示 | GenBank GO Section | 三列表格、按命名空间分组 |
| 搜索功能 | Ensembl Psychic Search | 多类型查询支持 |
| 基因中心化架构 | NCBI GenBank | 以 Gene 为核心聚合数据 |
| 版本映射 | Ensembl Assembly Mapper | 坐标转换 API |
| 数据模型 | Ensembl Core Schema | gene→transcript→exon 层级 |

---

## 10. 实现优先级

### Phase 1 (MVP)
1. 数据库主页（物种卡片列表）
2. YAML 配置解析和加载
3. 基因搜索和列表页
4. 基因详情页 Summary Tab
5. GFF 数据库查询 API

### Phase 2
1. 转录本信息 Tab
2. GO 注释 Tab
3. KEGG 通路 Tab
4. 序列下载 Tab
5. JBrowse 2 嵌入

### Phase 3
1. 跨版本映射工具
2. 数据库构建脚本
3. 高级搜索功能
4. 数据导出功能
