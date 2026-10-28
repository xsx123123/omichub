# 基因组数据库技术架构研究

> 研究日期：2025年7月  
> 研究范围：GFF/GTF存储、GO/KEGG数据组织、FASTA索引、基因组版本映射、JBrowse 2适配层

---

## 1. GFF/GTF 数据存储方案

### 1.1 概述

GFF（General Feature Format）和 GTF（Gene Transfer Format）是基因组注释的标准文本格式。GFF3 是当前最广泛使用的版本，而 GTF 是 GFF2 的精炼版本，主要用于基因注释。将 GFF/GTF 数据存储到关系数据库中可以大幅提升查询性能，支持复杂的区间查询和层级关系检索。

### 1.2 gffutils 数据库 Schema（SQLite）

**gffutils** 是 Python 中最流行的 GFF/GTF 数据库处理库，基于 SQLite3 构建。其数据库结构如下：

#### 核心表结构

```sql
-- 主特征表，存储每个 GFF/GTF 行的基本信息
CREATE TABLE features (
    id text,              -- 主键，特征的唯一标识符
    seqid text,           -- 染色体/序列 ID
    source text,          -- 注释来源
    featuretype text,     -- 特征类型（gene, mRNA, exon, CDS 等）
    start int,            -- 起始位置（1-based）
    end int,              -- 结束位置（1-based，包含）
    score text,           -- 得分
    strand text,          -- 链方向 (+, -, .)
    frame text,           -- 阅读框 (0, 1, 2, .)
    attributes text,      -- JSON 序列化的属性字典
    extra text,           -- JSON 序列化的额外字段
    bin int,              -- UCSC 基因组 bin 值
    primary key (id)
);

-- 关系表，存储特征间的层级关系（Parent-Child）
CREATE TABLE relations (
    parent text,          -- 父特征 ID
    child text,           -- 子特征 ID
    level int,            -- 关系层级（1=直接父子，2=祖孙等）
    primary key (parent, child, level)
);

-- 元数据表
CREATE TABLE meta (
    dialect text,         -- GFF/GTF 方言信息
    version text          -- gffutils 版本
);

-- 指令表
CREATE TABLE directives (
    directive text        -- GFF3 文件中的 ## 指令
);

-- 自增 ID 管理表
CREATE TABLE autoincrements (
    base text,            -- 特征类型前缀
    n int,                -- 当前自增序号
    primary key (base)
);

-- 重复 ID 映射表
CREATE TABLE duplicates (
    idspecid text,        -- 原始 ID
    newid text,           -- 新生成的唯一 ID
    primary key (newid)
);
```

#### 索引策略

gffutils 自动创建以下索引以优化查询：

```sql
-- 关系表索引
CREATE INDEX relationsparent ON relations (parent);
CREATE INDEX relationschild ON relations (child);

-- 特征类型索引
CREATE INDEX featuretype ON features (featuretype);

-- 基因组坐标索引
CREATE INDEX seqidstartend ON features (seqid, start, end);
CREATE INDEX seqidstartendstrand ON features (seqid, start, end, strand);

-- UCSC bin 索引（用于区间查询优化）
CREATE INDEX binindex ON features (bin);
```

### 1.3 使用 gffutils 创建和查询数据库

```python
import gffutils

# 创建数据库
db = gffutils.create_db(
    './annotation.gff3',
    dbfn='annotation.db',
    verbose=True,
    merge_strategy='error',  # ID 冲突时抛出异常
    disable_infer_transcripts=True,
    disable_infer_genes=True,
)

# 连接已有数据库
db = gffutils.FeatureDB('annotation.db')

# 按 ID 查询特征
gene = db['gene_001']
print(gene.seqid, gene.start, gene.end, gene.strand)

# 按类型查询
for mrna in db.features_of_type('mRNA'):
    print(mrna.id)

# 按基因组区域查询
for feature in db.region(seqid='chr1', start=1000, end=5000):
    print(feature)

# 查询子特征
for exon in db.children('transcript_001', featuretype='exon'):
    print(exon)

# 查询父特征
for gene in db.parents('transcript_001', featuretype='gene'):
    print(gene)
```

### 1.4 PostgreSQL 表结构设计建议

对于大规模基因组注释数据，PostgreSQL 提供更强大的查询能力：

```sql
-- 特征主表
CREATE TABLE features (
    id VARCHAR(255) PRIMARY KEY,
    seqid VARCHAR(100) NOT NULL,
    source VARCHAR(100),
    featuretype VARCHAR(100) NOT NULL,
    start INT NOT NULL,
    "end" INT NOT NULL,
    score VARCHAR(50),
    strand CHAR(1),
    frame CHAR(1),
    attributes JSONB,        -- PostgreSQL JSONB 支持高效查询
    bin INT                 -- UCSC binning 策略
);

-- 属性展开表（用于快速属性查询）
CREATE TABLE feature_attributes (
    feature_id VARCHAR(255) REFERENCES features(id),
    attr_key VARCHAR(100) NOT NULL,
    attr_value TEXT NOT NULL,
    PRIMARY KEY (feature_id, attr_key)
);

-- 层级关系表
CREATE TABLE feature_relations (
    parent_id VARCHAR(255) REFERENCES features(id),
    child_id VARCHAR(255) REFERENCES features(id),
    level INT NOT NULL DEFAULT 1,
    PRIMARY KEY (parent_id, child_id, level)
);

-- 创建索引
CREATE INDEX idx_features_seqid_start_end ON features(seqid, start, "end");
CREATE INDEX idx_features_featuretype ON features(featuretype);
CREATE INDEX idx_features_bin ON features(bin);
CREATE INDEX idx_features_seqid ON features(seqid);
CREATE INDEX idx_attrs_key_value ON feature_attributes(attr_key, attr_value);
CREATE INDEX idx_attrs_value ON feature_attributes USING GIN(attr_value gin_trgm_ops);
CREATE INDEX idx_features_attrs ON features USING GIN(attributes);  -- JSONB GIN 索引
```

### 1.5 UCSC Binning 策略

UCSC binning 是一种用于加速基因组区间查询的经典算法：

- 将基因组划分为不同大小的 bin（512Mb, 64Mb, 8Mb, 1Mb, 128kb, 16kb, 2kb）
- 每个特征根据其 start/end 计算所属的 bin
- 查询时先按 bin 过滤，再精确匹配坐标
- 可将区间查询复杂度从 O(n) 降低到 O(1) 级别

### 1.6 关键设计要点

| 设计决策 | 推荐方案 | 说明 |
|---------|---------|------|
| 数据库类型 | SQLite（中小型）/ PostgreSQL（大型） | SQLite 适合单机分析，PG 适合多用户服务 |
| 主键 | 特征 ID（GFF3 ID 属性） | 保证唯一性，支持快速查找 |
| 属性存储 | JSON/JSONB | 灵活存储可变属性，支持索引 |
| 层级关系 | 独立 relations 表 | 支持多层级查询（gene → mRNA → exon → CDS） |
| 区间查询 | UCSC bin + 坐标索引 | 双重优化，快速区间查询 |
| 坐标系统 | 1-based inclusive | GFF3 标准 |

---

## 2. GO 数据组织与查询

### 2.1 GO（Gene Ontology）概述

GO 是一个标准化的基因功能分类体系，采用有向无环图（DAG）结构组织，包含三个独立的本体：

- **BP (Biological Process)**：生物过程，如细胞分裂、代谢过程
- **MF (Molecular Function)**：分子功能，如激酶活性、DNA 结合
- **CC (Cellular Component)**：细胞组分，如线粒体、细胞核

### 2.2 GO 术语关系类型

GO 中的关系类型定义了术语间的语义关联：

| 关系类型 | 描述 | 可用于分组注释 |
|---------|------|-------------|
| `is_a` | A 是 B 的子类型，最基本的关系 | 是 |
| `part_of` | A 是 B 的组成部分 | 是 |
| `has_part` | A 必然包含 B 作为部分 | 否 |
| `regulates` | A 调控 B 的 manifestation | 可用于基因集富集 |
| `negatively_regulates` | A 负调控 B | 同上 |
| `positively_regulates` | A 正调控 B | 同上 |

### 2.3 GO 数据库存储结构

#### 核心表设计（参考 GO MySQL 数据库）

```sql
-- GO 术语表（DAG 的节点）
CREATE TABLE term (
    id INT PRIMARY KEY,           -- 内部数字 ID（非稳定）
    name VARCHAR(255) NOT NULL,   -- GO 术语名称
    term_type VARCHAR(50),        -- BP, MF, CC
    acc VARCHAR(20) UNIQUE,       -- 公开 ID，如 GO:0008150
    is_obsolete INT DEFAULT 0,    -- 是否已废弃
    is_root INT DEFAULT 0         -- 是否为根节点
);

-- 术语间直接关系（DAG 的边）
CREATE TABLE term2term (
    id INT PRIMARY KEY,
    relationship_type_id INT,     -- 关系类型 ID
    term1_id INT REFERENCES term(id),  -- 子术语
    term2_id INT REFERENCES term(id)   -- 父术语
);

-- 传递闭包表（预计算的祖先-后代关系）
CREATE TABLE graph_path (
    id INT PRIMARY KEY,
    term1_id INT REFERENCES term(id),  -- 后代术语
    term2_id INT REFERENCES term(id),  -- 祖先术语
    relationship_type_id INT,
    distance INT                      -- 距离（层级差）
);

-- 基因产物表
CREATE TABLE gene_product (
    id INT PRIMARY KEY,
    symbol VARCHAR(255),
    dbxref_id INT,
    species_id INT,
    type_id INT
);

-- 基因-GO 关联表（注释）
CREATE TABLE association (
    id INT PRIMARY KEY,
    gene_product_id INT REFERENCES gene_product(id),
    term_id INT REFERENCES term(id),
    source_id INT,
    evidence_code VARCHAR(10),    -- IEA, IDA, IPI, IMP 等
    is_not INT DEFAULT 0          -- 是否为否定注释
);
```

#### 传递闭包查询示例

```sql
-- 查找所有属于 "blood coagulation" 的 GO 术语（包括后代）
SELECT child.*
FROM term AS parent
JOIN graph_path ON graph_path.term2_id = parent.id
JOIN term AS child ON child.id = graph_path.term1_id
WHERE parent.acc = 'GO:0007596';

-- 查找某个基因注释的所有 GO 术语（包括祖先，用于富集分析）
SELECT DISTINCT ancestor.acc, ancestor.name
FROM association a
JOIN graph_path gp ON gp.term1_id = a.term_id
JOIN term ancestor ON ancestor.id = gp.term2_id
WHERE a.gene_product_id = ?;
```

### 2.4 使用 goatools 进行 GO 分析

```python
from goatools.base import download_go_basic_obo
from goatools.obo_parser import GODag
from goatools.associations import read_gaf
from goatools.goea.go_enrichment_ns import GOEnrichmentStudy

# 1. 加载 GO DAG
obo_fname = download_go_basic_obo()
godag = GODag('go-basic.obo')

# 2. 加载基因-GO 关联（从 GAF 文件）
geneid2gos = read_gaf('gene_association.gaf', namespace='BP', godag=godag)

# 3. 创建富集分析对象
goeaobj = GOEnrichmentStudy(
    population=population_genes,  # 背景基因集
    assoc=geneid2gos,             # 基因-GO 关联字典
    obo_dag=godag,                # GO DAG 对象
    propagate_counts=True,        # 向父节点传播计数
    alpha=0.05,                   # 显著性阈值
    methods=['fdr_bh']            # FDR 校正方法
)

# 4. 运行富集分析
results = goeaobj.run_study(study_genes)

# 5. 输出结果
for r in results:
    if r.p_fdr_bh < 0.05:
        print(f"{r.GO} {r.name}: p={r.p_fdr_bh:.4e}")
```

### 2.5 GO DAG 在 Python 中的表示

```python
from goatools.obo_parser import GODag

# 加载 OBO 文件
godag = GODag('go-basic.obo')

# 查询 GO 术语
go_term = godag['GO:0008150']  # biological_process
print(go_term.name)           # biological_process
print(go_term.namespace)      # biological_process
print(go_term.depth)          # DAG 深度
print(go_term.level)          # 层级

# 遍历父节点
for parent in go_term.parents:
    print(f"Parent: {parent}")

# 遍历子节点
for child in go_term.children:
    print(f"Child: {child}")

# 获取所有后代
all_descendants = go_term.get_all_children()

# 获取所有祖先
all_ancestors = go_term.get_all_parents()
```

### 2.6 设计建议

| 设计决策 | 推荐方案 | 说明 |
|---------|---------|------|
| GO 结构存储 | OBO 文件 + 内存 DAG | goatools 的 GODag 对象 |
| 基因-GO 关联 | 字典 {gene: set(GO_terms)} | 内存高效，查询快速 |
| 传递闭包 | 预计算 graph_path 表 | 避免运行时递归查询 |
| 富集分析 | goatools GOEnrichmentStudy | 支持多种校正方法 |
| 存储格式 | SQLite/PostgreSQL + 预计算 | 适合大规模查询 |

---

## 3. KEGG 数据存储方案

### 3.1 KEGG 概述

KEGG（Kyoto Encyclopedia of Genes and Genomes）是一个综合性的生物信息学数据库，包含：

- **Pathway**：代谢通路、调控通路、疾病通路等
- **Genes**：基因注释（以物种代码区分，如 hsa 为人类）
- **Compound**：化合物/代谢物信息
- **Reaction**：生化反应
- **Enzyme**：酶信息
- **Disease**：疾病与基因关联
- **Drug**：药物信息

### 3.2 KEGG REST API

KEGG 提供 REST API，基础 URL 为 `https://rest.kegg.jp/`，核心操作包括：

| 操作 | 端点 | 说明 |
|-----|------|------|
| info | `/info/<database>` | 获取数据库信息 |
| list | `/list/<database>` | 列出条目 |
| find | `/find/<database>/<query>` | 关键词搜索 |
| get | `/get/<entry>` | 获取详细信息 |
| conv | `/conv/<target_db>/<source_db>` | ID 转换 |
| link | `/link/<target_db>/<source_db>` | 交叉引用 |

#### API 使用示例

```python
import requests

BASE_URL = "https://rest.kegg.jp"

# 获取数据库信息
info = requests.get(f"{BASE_URL}/info/pathway").text

# 列出所有通路
pathways = requests.get(f"{BASE_URL}/list/pathway/hsa").text

# 获取特定通路详情
pathway = requests.get(f"{BASE_URL}/get/hsa00010").text  # 糖酵解通路

# 获取基因列表
genes = requests.get(f"{BASE_URL}/list/hsa").text

# ID 转换（KEGG ID → NCBI Gene ID）
conv = requests.get(f"{BASE_URL}/conv/ncbi-geneid/hsa:10458").text

# 获取通路中的基因
link = requests.get(f"{BASE_URL}/link/hsa/pathway+hsa00010").text
```

### 3.3 使用 bioservices 库

```python
from bioservices import KEGG

# 初始化 KEGG 客户端
k = KEGG()

# 获取通路列表
pathways = k.pathwayIds  # 所有通路 ID

# 获取特定通路信息
pathway_info = k.get("hsa00010")

# 按通路获取基因
genes = k.get_pathway_by_gene("hsa:10458", "hsa")

# 富集分析（自定义实现）
from collections import defaultdict
import scipy.stats as stats

def kegg_enrichment(gene_list, gene2pathways, all_genes, all_pathways):
    """
    KEGG 通路富集分析
    
    Parameters:
        gene_list: 研究基因集
        gene2pathways: {gene: [pathway_ids]} 映射
        all_genes: 背景基因集
        all_pathways: 所有通路 {pathway_id: [genes]}
    """
    results = []
    n_total = len(all_genes)
    n_study = len(gene_list)
    study_set = set(gene_list)
    
    for pw_id, pw_genes in all_pathways.items():
        pw_set = set(pw_genes)
        
        # 列联表
        a = len(study_set & pw_set)  # 在研究中且在通路中
        b = n_study - a               # 在研究中但不在通路中
        c = len(pw_set) - a           # 不在研究中但在通路中
        d = n_total - n_study - c     # 既不在研究中也不在通路中
        
        if a < 2:  # 至少2个基因
            continue
            
        # Fisher 精确检验
        odds_ratio, pvalue = stats.fisher_exact([[a, b], [c, d]], 'greater')
        
        results.append({
            'pathway_id': pw_id,
            'p_value': pvalue,
            'enriched_genes': list(study_set & pw_set),
            'gene_count': a
        })
    
    return results
```

### 3.4 KEGG 数据库表设计

```sql
-- KEGG 通路表
CREATE TABLE kegg_pathways (
    pathway_id VARCHAR(20) PRIMARY KEY,  -- 如 hsa00010
    name VARCHAR(255) NOT NULL,
    description TEXT,
    category VARCHAR(100),               -- Metabolism, Genetic Information Processing 等
    organism VARCHAR(10),                -- 物种代码（如 hsa）
    map_id VARCHAR(10)                   -- 参考 map 编号（如 map00010）
);

-- KEGG 基因表
CREATE TABLE kegg_genes (
    gene_id VARCHAR(30) PRIMARY KEY,     -- 如 hsa:10458
    symbol VARCHAR(50),
    name VARCHAR(255),
    organism VARCHAR(10),
    definition TEXT,
    ncbi_gene_id VARCHAR(20),
    uniprot_id VARCHAR(20)
);

-- 基因-通路关联表（核心富集分析表）
CREATE TABLE kegg_gene_pathway (
    gene_id VARCHAR(30) REFERENCES kegg_genes(gene_id),
    pathway_id VARCHAR(20) REFERENCES kegg_pathways(pathway_id),
    PRIMARY KEY (gene_id, pathway_id)
);

-- 通路中的化合物
CREATE TABLE kegg_pathway_compound (
    pathway_id VARCHAR(20),
    compound_id VARCHAR(20),
    PRIMARY KEY (pathway_id, compound_id)
);

-- 创建索引
CREATE INDEX idx_kegg_pw_org ON kegg_pathways(organism);
CREATE INDEX idx_kegg_gene_org ON kegg_genes(organism);
CREATE INDEX idx_kegg_gp_pathway ON kegg_gene_pathway(pathway_id);
CREATE INDEX idx_kegg_gp_gene ON kegg_gene_pathway(gene_id);
```

### 3.5 数据获取与更新策略

```python
"""KEGG 数据定期同步脚本"""
import sqlite3
import requests
import time

BASE_URL = "https://rest.kegg.jp"
DB_PATH = "kegg_data.db"

def sync_kegg_data(organism="hsa"):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 1. 获取并存储通路列表
    response = requests.get(f"{BASE_URL}/list/pathway/{organism}")
    for line in response.text.strip().split('\n'):
        parts = line.split('\t')
        if len(parts) == 2:
            pw_id = parts[0].replace('path:', '')
            name = parts[1]
            cursor.execute(
                "INSERT OR REPLACE INTO kegg_pathways (pathway_id, name, organism) VALUES (?, ?, ?)",
                (pw_id, name, organism)
            )
    
    # 2. 获取基因-通路关联
    response = requests.get(f"{BASE_URL}/link/{organism}/pathway+{organism}")
    for line in response.text.strip().split('\n'):
        parts = line.split('\t')
        if len(parts) == 2:
            pathway_id = parts[0].replace('path:', '')
            gene_id = parts[1]
            cursor.execute(
                "INSERT OR IGNORE INTO kegg_gene_pathway (pathway_id, gene_id) VALUES (?, ?)",
                (pathway_id, gene_id)
            )
    
    conn.commit()
    conn.close()
    
    # API 限流：每秒最多 3 次请求
    time.sleep(0.4)
```

### 3.6 设计要点

| 设计决策 | 推荐方案 | 说明 |
|---------|---------|------|
| 数据获取 | KEGG REST API | 学术免费，限流 3次/秒 |
| 存储方式 | SQLite/PostgreSQL | 本地缓存，减少 API 调用 |
| 基因-通路关联 | 多对多关系表 | 支持快速富集分析查询 |
| ID 映射 | kegg_conv API | KEGG ID ↔ NCBI/UniProt |
| 富集分析 | Fisher 精确检验 + FDR 校正 | 标准统计方法 |
| Python 工具 | bioservices, KEGGRESTpy | 封装 API 调用 |

---

## 4. FASTA 序列索引方案

### 4.1 .fai 索引文件格式

FASTA 索引（.fai）是由 samtools faidx 创建的二进制索引，用于快速随机访问 FASTA 序列。

#### 文件格式

.fai 文件是制表符分隔的文本文件，每行包含 5 列：

| 列 | 名称 | 说明 |
|----|------|------|
| 1 | NAME | 序列名称（FASTA 头行 `>` 后的第一个单词） |
| 2 | LENGTH | 序列总长度（碱基数） |
| 3 | OFFSET | 文件中该序列第一个碱基的偏移量（字节，0-based） |
| 4 | LINEBASES | 每行包含的碱基数 |
| 5 | LINEWIDTH | 每行字节数（含换行符） |

#### 示例

```
# .fai 文件示例
chr1    248956422    52    60    61
chr2    242193529    2521669070    60    61
chr3    198295559    4926331608    60    61
```

### 4.2 使用 samtools faidx

```bash
# 创建索引
samtools faidx reference.fa

# 提取完整序列
samtools faidx reference.fa chr1

# 提取子序列（1-based 坐标，inclusive）
samtools faidx reference.fa chr1:1000-2000

# 提取多个区域
samtools faidx reference.fa chr1:1-100 chr2:500-1000

# 从文件读取区域列表
samtools faidx reference.fa -r regions.txt

# 反向互补
samtools faidx reference.fa chr1:1000-2000 -i -o output.fa

# 生成 BED 格式文件
samtools faidx reference.fa && awk '{print $1"\t0\t"$2}' reference.fa.fai > reference.bed
```

### 4.3 基于 fai 索引的快速子序列提取原理

```python
class FastaIndex:
    """基于 .fai 索引的快速 FASTA 随机访问"""
    
    def __init__(self, fasta_path):
        self.fasta_path = fasta_path
        self.fai_path = fasta_path + '.fai'
        self.index = {}
        self._load_index()
    
    def _load_index(self):
        """加载 fai 索引"""
        with open(self.fai_path) as f:
            for line in f:
                parts = line.strip().split('\t')
                self.index[parts[0]] = {
                    'length': int(parts[1]),
                    'offset': int(parts[2]),
                    'linebases': int(parts[3]),
                    'linewidth': int(parts[4])
                }
    
    def fetch(self, seqname, start, end):
        """
        提取子序列
        
        Args:
            seqname: 序列名称
            start: 起始位置（0-based）
            end: 结束位置（exclusive）
        """
        if seqname not in self.index:
            raise ValueError(f"Sequence {seqname} not found")
        
        idx = self.index[seqname]
        length = idx['length']
        linebases = idx['linebases']
        linewidth = idx['linewidth']
        
        # 边界检查
        start = max(0, start)
        end = min(length, end)
        
        # 计算文件偏移量
        seq_offset = idx['offset']
        start_offset = seq_offset + (start // linebases) * linewidth + (start % linebases)
        end_offset = seq_offset + ((end - 1) // linebases) * linewidth + ((end - 1) % linebases) + 1
        
        # 读取序列数据
        with open(self.fasta_path, 'rb') as f:
            f.seek(start_offset)
            raw = f.read(end_offset - start_offset).decode()
        
        # 去除换行符
        seq = raw.replace('\n', '')
        return seq
```

### 4.4 SQLite 中存储序列的方案

对于需要频繁查询的场景，可以将序列数据存储在 SQLite 中：

```sql
-- 序列表
CREATE TABLE sequences (
    seq_id VARCHAR(100) PRIMARY KEY,
    length INT NOT NULL,
    sequence TEXT NOT NULL
);

-- 创建索引
CREATE INDEX idx_seq_length ON sequences(length);
```

```python
import sqlite3

def import_fasta_to_sqlite(fasta_path, db_path):
    """将 FASTA 导入 SQLite 数据库"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sequences (
            seq_id TEXT PRIMARY KEY,
            length INTEGER,
            sequence TEXT
        )
    ''')
    
    current_id = None
    current_seq = []
    
    with open(fasta_path) as f:
        for line in f:
            if line.startswith('>'):
                # 保存上一个序列
                if current_id:
                    seq = ''.join(current_seq)
                    cursor.execute(
                        'INSERT OR REPLACE INTO sequences VALUES (?, ?, ?)',
                        (current_id, len(seq), seq)
                    )
                # 开始新序列
                current_id = line[1:].split()[0].strip()
                current_seq = []
            else:
                current_seq.append(line.strip())
        
        # 保存最后一个序列
        if current_id:
            seq = ''.join(current_seq)
            cursor.execute(
                'INSERT OR REPLACE INTO sequences VALUES (?, ?, ?)',
                (current_id, len(seq), seq)
            )
    
    conn.commit()
    conn.close()

# 查询子序列
def get_subsequence(db_path, seq_id, start, end):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        'SELECT SUBSTR(sequence, ?, ?) FROM sequences WHERE seq_id = ?',
        (start + 1, end - start, seq_id)
    )
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None
```

### 4.5 索引格式对比

| 特性 | .fai 索引 | .gzi 索引（BGZF） |
|-----|----------|-----------------|
| 压缩支持 | 否 | 是（BGZF 格式） |
| 随机访问 | 是 | 是 |
| 文件大小 | 小（纯文本索引） | 稍大（块偏移索引） |
| 适用场景 | 未压缩 FASTA | 压缩 FASTA |
| 工具支持 | samtools, pysam | samtools, pysam, JBrowse 2 |

### 4.6 设计建议

| 设计决策 | 推荐方案 | 说明 |
|---------|---------|------|
| 索引方式 | .fai 文件 | 标准、高效、广泛支持 |
| 压缩存储 | BGZF + .gzi | 节省空间，支持随机访问 |
| 子序列提取 | samtools faidx | O(1) 时间复杂度 |
| 数据库存储 | SQLite + SUBSTR | 适合小规模或频繁查询 |
| Python 库 | pysam, pyfaidx | 高性能 Python 绑定 |

---

## 5. 基因组版本映射技术

### 5.1 概述

基因组版本映射（Lift Over）是将一个基因组版本上的坐标转换到另一个基因组版本的过程。当参考基因组更新时（如 hg19 → hg38），已有的注释数据需要转换到新版本。

### 5.2 UCSC Chain 文件格式

Chain 文件描述了两个基因组组装之间的成对比对关系，是坐标映射的核心数据结构。

#### 格式规范

```
chain score tName tSize tStrand tStart tEnd qName qSize qStrand qStart qEnd id
size dt dq
...
\n
```

**Header 行字段说明：**

| 字段 | 说明 |
|-----|------|
| `chain` | 文件类型标识 |
| `score` | 比对得分 |
| `tName` | 目标基因组染色体名 |
| `tSize` | 目标基因组染色体大小 |
| `tStrand` | 目标链（通常为 +） |
| `tStart` | 目标比对起始 |
| `tEnd` | 目标比对结束 |
| `qName` | 查询基因组染色体名 |
| `qSize` | 查询基因组染色体大小 |
| `qStrand` | 查询链（+ 或 -） |
| `qStart` | 查询比对起始 |
| `qEnd` | 查询比对结束 |
| `id` | 链 ID |

**数据行字段说明：**

| 字段 | 说明 |
|-----|------|
| `size` | 匹配块大小 |
| `dt` | 目标基因组上当前块与下一块的间隙 |
| `dq` | 查询基因组上当前块与下一块的间隙 |

#### Chain 文件示例

```
chain 1000000 chr1 248956422 + 10000 50000 chr1_alt 150000 + 2000 42000 1
1000 50 30
2000 0 0
5000
```

### 5.3 Chain 文件获取

```bash
# UCSC 提供预计算的 chain 文件
# hg38 → hg19
wget https://hgdownload.soe.ucsc.edu/goldenPath/hg38/liftOver/hg38ToHg19.over.chain.gz

# hg19 → hg38
wget https://hgdownload.soe.ucsc.edu/goldenPath/hg19/liftOver/hg19ToHg38.over.chain.gz

# GRCh37(hg19) → GRCh38(hg38)
wget https://hgdownload.soe.ucsc.edu/goldenPath/hg19/liftOver/hg19ToHg38.over.chain.gz

# Ensembl 也提供 chain 文件
# 人类 Human to Human
wget ftp://ftp.ensembl.org/pub/assembly_mapping/homo_sapiens/GRCh37_to_GRCh38.chain.gz
```

### 5.4 CrossMap 工具

**CrossMap** 是一个基于 chain 文件的坐标转换工具，支持多种文件格式。

#### 安装

```bash
pip install CrossMap
```

#### 使用示例

```bash
# BED 文件坐标转换
CrossMap bed hg19ToHg38.over.chain.gz input.bed output.bed

# GFF/GTF 坐标转换
CrossMap gff hg19ToHg38.over.chain.gz input.gtf output.gtf

# BAM 文件坐标转换
CrossMap bam hg19ToHg38.over.chain.gz input.bam output.bam

# VCF 坐标转换
CrossMap vcf hg19ToHg38.over.chain.gz input.vcf ref.fa output.vcf

# Wig/BigWig 坐标转换
CrossMap bigwig hg19ToHg38.over.chain.gz input.bw output.bw

# 查看 chain 文件内容
CrossMap viewchain hg19ToHg38.over.chain.gz
```

#### Python API

```python
from CrossMap import CrossMap

# 加载 chain 文件
mapper = CrossMap('hg19ToHg38.over.chain.gz')

# 转换单个坐标
result = mapper.map_coordinates('chr1', 1000000, 1000500, '+')
# 返回: [(chr1, 1000035, 1000535, +, 0.98)]

# 转换 BED 格式坐标
for chrom, start, end, strand in bed_records:
    mapped = mapper.map_coordinates(chrom, start, end, strand)
    if mapped:
        print(mapped)
```

### 5.5 Liftoff 工具

**Liftoff** 是一个独立的基因注释映射工具，不需要预先生成 chain 文件。它使用 Minimap2 将参考基因组的基因序列比对到目标基因组。

#### 特点

- **无需 chain 文件**：直接使用两个基因组 FASTA 和参考注释
- **保留基因结构**：最大化序列一致性同时保留外显子/转录本结构
- **处理重叠基因**：自动检测并解决基因映射冲突
- **发现额外拷贝**：可选查找目标基因组中额外的基因拷贝

#### 安装与使用

```bash
# 安装
conda install -c bioconda liftoff
# 或
pip install Liftoff

# 基本用法
liftoff -g reference.gff -o output.gff target.fa reference.fa

# 保留额外拷贝
liftoff -g reference.gff -o output.gff -copies target.fa reference.fa

# 指定最小覆盖度和一致性
liftoff -g reference.gff -o output.gff -a 0.5 -s 0.5 target.fa reference.fa

# 并行处理
liftoff -g reference.gff -o output.gff -p 8 target.fa reference.fa
```

#### 参数说明

| 参数 | 说明 | 默认值 |
|-----|------|--------|
| `-g` | 参考基因组注释（GFF/GTF） | 必需 |
| `-o` | 输出文件 | stdout |
| `-u` | 未映射特征文件 | unmapped_features.txt |
| `-a` | 最小比对覆盖度 | 0.5 |
| `-s` | 最小序列一致性 | 0.5 |
| `-p` | 并行进程数 | 1 |
| `-copies` | 查找额外基因拷贝 | False |
| `-d` | 距离缩放因子 | 2.0 |
| `-flank` | 侧翼序列比例 | 0.0 |

#### Python API

```python
from liftoff import liftover_annotation

# 程序化调用
liftover_annotation.main(
    args=['-g', 'reference.gff',
          '-o', 'output.gff',
          '-a', '0.5',
          '-s', '0.5',
          'target.fa',
          'reference.fa']
)
```

### 5.6 创建 Chain 文件

```bash
# 使用 UCSC 工具链创建自定义 chain 文件
# 1. 准备 2bit 格式
faToTwoBit ref.fa ref.2bit
faToTwoBit query.fa query.2bit

# 2. 运行 blat 生成 PSL
blat ref.2bit query.2bit aln.psl -tileSize=12 -minScore=100 -minIdentity=98

# 3. 生成 chain 文件
axtChain -linearGap=medium -psl aln.psl ref.2bit query.2bit output.chain

# 4. 合并和排序 chain
chainMergeSort *.chain | chainSplit chaindir stdin
```

### 5.7 版本映射数据存储方案

```sql
-- 坐标映射表
CREATE TABLE coordinate_mapping (
    id SERIAL PRIMARY KEY,
    source_assembly VARCHAR(20) NOT NULL,   -- 源基因组版本
    target_assembly VARCHAR(20) NOT NULL,   -- 目标基因组版本
    source_chr VARCHAR(50) NOT NULL,
    source_start INT NOT NULL,
    source_end INT NOT NULL,
    target_chr VARCHAR(50),
    target_start INT,
    target_end INT,
    strand CHAR(1),
    mapping_quality FLOAT,
    is_mapped BOOLEAN DEFAULT true
);

-- 基因组版本信息表
CREATE TABLE genome_assemblies (
    assembly_id VARCHAR(20) PRIMARY KEY,   -- hg19, hg38, GRCh38
    species VARCHAR(100),
    version VARCHAR(20),
    release_date DATE,
    source VARCHAR(50)
);

-- 创建索引
CREATE INDEX idx_map_source ON coordinate_mapping(source_assembly, source_chr, source_start, source_end);
CREATE INDEX idx_map_target ON coordinate_mapping(target_assembly, target_chr, target_start, target_end);
```

### 5.8 工具对比

| 特性 | CrossMap | Liftoff | UCSC liftOver |
|-----|---------|---------|--------------|
| 输入 | chain 文件 | 两个基因组 + 注释 | chain 文件 |
| 预计算 | 需要 chain 文件 | 无需预计算 | 需要 chain 文件 |
| 基因结构保留 | 逐行转换 | 保留外显子结构 | 逐行转换 |
| 处理断裂 | 可能分裂 | 智能处理 | 可能分裂 |
| 额外拷贝 | 否 | 是（-copies） | 否 |
| 适用场景 | 通用坐标转换 | 基因注释映射 | 通用坐标转换 |
| 格式支持 | BED/GFF/BAM/VCF等 | GFF/GTF | BED |

---

## 6. JBrowse 2 适配层设计

### 6.1 JBrowse 2 架构概述

JBrowse 2 是一个模块化的基因组浏览器，采用插件化架构，支持：

- **多种视图**：线性基因组视图、点图、共线性视图、环形视图
- **数据适配器**：支持多种数据格式（BAM, VCF, GFF, BigWig 等）
- **文本搜索**：支持按基因名搜索
- **插件系统**：可扩展的插件架构

### 6.2 数据适配器类型

JBrowse 2 定义了多种适配器接口：

| 适配器类型 | 说明 | 示例 |
|-----------|------|------|
| Feature Adapter | 返回区域内的特征（基因、变异等） | BamAdapter, VcfTabixAdapter |
| Regions Adapter | 定义组装中的区域（染色体及大小） | ChromSizesAdapter |
| Sequence Adapter | 返回区域内的序列 | BgzipFastaAdapter, IndexedFastaAdapter |
| RefName Alias Adapter | 参考序列名别名映射 | RefNameAliasAdapter |
| Text Search Adapter | 文本搜索索引 | TrixTextSearchAdapter |

### 6.3 适配器基础接口

```typescript
// 特征适配器的核心接口
class BaseFeatureDataAdapter {
  // 返回参考序列名称
  async getRefNames(): Promise<string[]>;
  
  // 返回指定区域内的特征
  getFeatures(region: Region, opts: Options): Observable<Feature>;
  
  // 释放资源（可选）
  freeResources(region: Region): void;
}

// Region 对象结构
interface Region {
  refName: string;      // 染色体名，如 "chr1"
  start: number;        // 起始位置（0-based）
  end: number;          // 结束位置（exclusive）
  assemblyName: string; // 组装名
}
```

### 6.4 为 JBrowse 2 准备基因组数据

#### 添加参考基因组（Indexed FASTA）

```bash
# 1. 准备 FASTA 文件
samtools faidx reference.fa

# 2. 使用 JBrowse CLI 添加组装
jbrowse add-assembly reference.fa --out /var/www/html/jbrowse2 --load copy

# 或使用 BgzipFasta（推荐，支持压缩）
samtools faidx reference.fa
bgzip reference.fa
samtools faidx reference.fa.gz

jbrowse add-assembly reference.fa.gz --out /var/www/html/jbrowse2 --load copy
```

#### 添加 GFF 轨道（Gff3Tabix）

```bash
# 1. 排序 GFF3 文件
jbrowse sort-gff annotation.gff3 > sorted.gff

# 2. 压缩和索引
bgzip sorted.gff
tabix -p gff sorted.gff.gz

# 3. 添加轨道
jbrowse add-track sorted.gff.gz --out /var/www/html/jbrowse2 --load copy \
  --assemblyNames hg38
```

#### 添加 BAM/CRAM 轨道

```bash
# BAM 文件需要排序和索引
samtools sort -o sorted.bam input.bam
samtools index sorted.bam

jbrowse add-track sorted.bam --out /var/www/html/jbrowse2 --load copy \
  --assemblyNames hg38
```

#### 添加 BigWig 轨道

```bash
jbrowse add-track signal.bw --out /var/www/html/jbrowse2 --load copy \
  --assemblyNames hg38
```

### 6.5 JBrowse 2 配置文件结构

```json
{
  "assemblies": [
    {
      "name": "hg38",
      "sequence": {
        "type": "ReferenceSequenceTrack",
        "trackId": "hg38-refseq",
        "adapter": {
          "type": "BgzipFastaAdapter",
          "fastaLocation": {
            "uri": "hg38.fa.gz"
          },
          "faiLocation": {
            "uri": "hg38.fa.gz.fai"
          },
          "gziLocation": {
            "uri": "hg38.fa.gz.gzi"
          }
        }
      },
      "refNameAliases": {
        "adapter": {
          "type": "RefNameAliasAdapter",
          "location": {
            "uri": "hg38_aliases.txt"
          }
        }
      }
    }
  ],
  "tracks": [
    {
      "type": "FeatureTrack",
      "trackId": "genes",
      "name": "Gene Annotations",
      "assemblyNames": ["hg38"],
      "adapter": {
        "type": "Gff3TabixAdapter",
        "gffGzLocation": {
          "uri": "genes.gff.gz"
        },
        "index": {
          "location": {
            "uri": "genes.gff.gz.tbi"
          },
          "indexType": "TBI"
        }
      }
    },
    {
      "type": "AlignmentsTrack",
      "trackId": "alignments",
      "name": "BAM Alignments",
      "assemblyNames": ["hg38"],
      "adapter": {
        "type": "BamAdapter",
        "bamLocation": {
          "uri": "alignments.bam"
        },
        "index": {
          "location": {
            "uri": "alignments.bam.bai"
          },
          "indexType": "BAI"
        }
      }
    }
  ],
  "plugins": []
}
```

### 6.6 创建文本搜索索引

```bash
# 创建 trix 搜索索引
jbrowse text-index --out /var/www/html/jbrowse2 \
  --tracks=genes \
  --assembly=hg38
```

### 6.7 支持的文件格式与索引

| 格式 | 索引 | 适配器类型 | 说明 |
|------|------|----------|------|
| FASTA | .fai / .gzi | IndexedFastaAdapter / BgzipFastaAdapter | 参考序列 |
| GFF3 | tabix (.tbi/.csi) | Gff3TabixAdapter | 基因注释 |
| VCF | tabix (.tbi/.csi) | VcfTabixAdapter | 变异数据 |
| BAM | .bai / .csi | BamAdapter | 比对数据 |
| CRAM | .crai | CramAdapter | 压缩比对 |
| BigWig | 内置索引 | BigWigAdapter | 定量数据 |
| BigBed | 内置索引 | BigBedAdapter | 区间注释 |
| PAF | - | PAFAdapter | 共线性比对 |

### 6.8 插件系统

JBrowse 2 的插件系统允许扩展以下元素：

| 可扩展元素 | 说明 |
|-----------|------|
| Data Adapters | 读取和解析新数据格式 |
| Text Search Adapters | 自定义文本搜索 |
| Track Types | 新轨道类型 |
| Display Types | 视图中的显示方式 |
| Renderer Types | 绘制特征的渲染器 |
| View Types | 全新视图类型 |
| Widgets | 侧边栏工具 |

---

## 7. 综合技术架构建议

### 7.1 推荐技术栈

| 组件 | 推荐方案 | 备选方案 |
|------|---------|---------|
| GFF/GTF 存储 | gffutils (SQLite) | PostgreSQL + 自定义 schema |
| GO 数据 | goatools + OBO 文件 | GO.db (R) + 自定义 SQL |
| KEGG 数据 | bioservices + SQLite 缓存 | KEGGRESTpy + PostgreSQL |
| FASTA 索引 | samtools faidx + .fai | pyfaidx, pysam |
| 版本映射 | Liftoff（基因注释） | CrossMap（通用坐标） |
| 可视化 | JBrowse 2 | UCSC Genome Browser, IGV |

### 7.2 数据流架构

```
┌─────────────────────────────────────────────────────┐
│                    数据层 (Data Layer)                │
├─────────────────────────────────────────────────────┤
│  GFF/GTF  →  gffutils/SQLite  →  Feature Query API  │
│  GO/OBO   →  goatools GODag   →  Enrichment API     │
│  KEGG     →  REST API + Cache →  Pathway API        │
│  FASTA    →  .fai/.gzi Index  →  Sequence API       │
└─────────────────────────────────────────────────────┘
                         │
┌─────────────────────────────────────────────────────┐
│                  服务层 (Service Layer)               │
├─────────────────────────────────────────────────────┤
│  Coordinate Mapping  (Liftoff/CrossMap)             │
│  Enrichment Analysis (goatools/custom)              │
│  Data Transformation (format conversion)            │
└─────────────────────────────────────────────────────┘
                         │
┌─────────────────────────────────────────────────────┐
│                 展示层 (Presentation Layer)           │
├─────────────────────────────────────────────────────┤
│  JBrowse 2 (Web)                                    │
│  Custom APIs (REST/GraphQL)                         │
│  Command-line Tools                                 │
└─────────────────────────────────────────────────────┘
```

### 7.3 性能优化建议

1. **索引策略**：
   - 基因组坐标查询使用 UCSC binning + 组合索引
   - 文本搜索使用 trix 或 trigram 索引
   - GO 查询使用预计算传递闭包

2. **缓存策略**：
   - KEGG API 结果本地缓存（限流 3次/秒）
   - GO 富集分析结果缓存
   - 序列片段 LRU 缓存

3. **数据压缩**：
   - FASTA 使用 BGZF 压缩
   - GFF 使用 bgzip + tabix 索引
   - BAM/CRAM 使用标准压缩

4. **并行处理**：
   - 使用多进程加速 gffutils 数据库创建
   - Liftoff 支持 `-p` 并行参数
   - JBrowse 2 使用 Web Worker 渲染

### 7.4 关键设计模式

| 模式 | 应用场景 |
|-----|---------|
| 适配器模式 | JBrowse 2 数据适配器 |
| 缓存模式 | KEGG API 本地缓存 |
| 索引模式 | fai/bin 加速查询 |
| 传递闭包 | GO DAG 祖先/后代查询 |
| 管道模式 | GFF → 排序 → 压缩 → 索引 |

---

## 参考文献

1. gffutils 官方文档: https://daler.github.io/gffutils/
2. GOATOOLS 论文: Klopfenstein et al. (2018) Scientific Reports
3. KEGG API 文档: https://www.kegg.jp/kegg/api.html
4. samtools faidx: http://www.htslib.org/doc/samtools-faidx.html
5. Liftoff 论文: Shumate & Salzberg (2021) Bioinformatics
6. CrossMap 文档: https://crossmap.sourceforge.net/
7. JBrowse 2 文档: https://jbrowse.org/jb2/docs/
8. UCSC Chain 格式: https://genome.ucsc.edu/goldenPath/help/chain.html
9. GO 数据库指南: http://geneontology.org/docs/ontology-relations/
10. FAIDX 格式规范: http://www.htslib.org/doc/faidx.html
