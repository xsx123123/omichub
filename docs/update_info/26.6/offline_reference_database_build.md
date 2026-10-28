# 离线构建参考基因组数据库文件

本文档说明如何用 `fa/gff/go/ko/kegg` 原始文件离线生成 OmicHub 数据库资产。核心原则是：**平台不负责转换，不在 Web 请求或 Celery 任务中构建数据库**。管理员在单独机器、登录服务器终端或维护窗口运行脚本，平台只读取已经生成好的文件路径。

## 1. 推荐数据流

```text
原始文件
  ├── genome.fa                 # 参考序列
  ├── annotation.gff3           # 基因结构注释
  ├── go_annotations.tsv        # 可选：gene -> GO
  ├── go_terms.tsv 或 go-basic.obo # 可选：GO ID -> term/namespace 补全
  ├── ko_annotations.tsv        # 可选：gene -> KO
  └── kegg_annotations.tsv      # 可选：gene -> KO、gene -> pathway 或 KO -> pathway
        │
        ▼
离线命令 omichubtools refdb build
        │
        ├── genome.fa.fai 或指定 .fai
        ├── database.sqlite     # 查询数据库文件
        ├── database_manifest.json
        ├── jbrowse_assembly_snippet.yaml
        └── build_report.json
        │
        ▼
管理员把 snippet 合并到 tool_configs/jbrowse/jbrowse_config.yaml
        │
        ▼
平台 reload 配置，只展示和查询，不做转换
```

## 2. 输入文件约定

### 2.1 FASTA

必填。建议放在 `/data/omichub/omichub_data/db/<species>/<version>/` 或 `/data/omichub/omichub_data/jbrowse/ref/<assembly>/` 下，保证 web/nginx 容器可读。

```text
>chr1
ATGC...
>chr2
ATGC...
```

脚本会为未压缩 FASTA 生成 `.fai`。如果使用 `.fa.gz`，建议先用 `samtools faidx` 建好索引，并通过 `--fai` 指定，或确保构建环境有 `samtools`。

### 2.2 GFF3/GTF

可选但强烈建议提供。脚本会解析 9 列 GFF/GTF，写入 `features`、`genes`、`transcripts`、`exons`、`relations` 等表。

```text
chr1	source	gene	100	900	.	+	.	ID=Gene001;Name=ABC1;biotype=protein_coding
chr1	source	mRNA	100	900	.	+	.	ID=Gene001.1;Parent=Gene001
chr1	source	exon	100	200	.	+	.	Parent=Gene001.1
```

### 2.3 GO 注释 TSV

可选。支持带表头或无表头。最小格式只需要 `gene_id -> go_id`；如果同时提供 `--go-terms`，脚本会离线补全 `term` 与 `namespace`。

推荐表头：

```text
gene_id	go_id	term	namespace	evidence_code	source
Gene001	GO:0005524	ATP binding	MF	IEA	InterPro
```

最小表头：

```text
gene_id	go_id
Gene001	GO:0005524
Gene002	GO:0006355;GO:0005634
```

无表头时按以下列解释：

```text
gene_id  go_id  term  namespace  evidence_code  source
```

### 2.4 GO term 补全文件

可选，通过 `--go-terms` 传入。支持两种格式：

1. TSV/CSV：

```text
go_id	term	namespace	definition	source
GO:0005524	ATP binding	MF	Interacting selectively and non-covalently with ATP	GO
GO:0006355	regulation of transcription	BP	Any process that modulates transcription	GO
```

2. OBO：可直接传 `go-basic.obo`，脚本会读取 `[Term]` 里的 `id/name/namespace/def`，并跳过 obsolete term。

`namespace` 支持 `BP/MF/CC`，也支持 OBO 中的 `biological_process/molecular_function/cellular_component`，脚本会自动归一化。

### 2.5 KO 注释 TSV

可选。表示 `gene -> KO`。

推荐表头：

```text
gene_id	ko_id	description	source
Gene001	K14486	auxin response factor	KofamScan
```

无表头时按以下列解释：

```text
gene_id  ko_id  description  source
```

### 2.6 KEGG 注释 TSV

可选。脚本支持三种格式。

格式 A：`gene -> pathway`，可直接生成 `kegg_annotations`：

```text
gene_id	pathway_id	pathway_name	category	ko_id	ec_number	source
Gene001	ko04075	Plant hormone signal transduction	Environmental Information Processing	K14486		KEGG
```

格式 B：`gene -> KO`，适合你的 KEGG 结果只有基因和 `Kxxxxx`：

```text
gene_id	kegg_id	source
Gene001	K14486	KofamScan
Gene002	K00844	eggNOG
```

这种文件会写入 `ko_annotations`。如果还想展开到 pathway，需要再提供格式 C 的 KO-pathway 表，或把 pathway 直接写成格式 A。

格式 C：`KO -> pathway`，适合你已经有 KO 注释，但 KEGG 文件只描述 KO 归属通路的情况：

```text
ko_id	pathway_id	pathway_name	category	source
K14486	ko04075	Plant hormone signal transduction	Environmental Information Processing	KEGG
```

当同时存在 `gene -> KO` 和 `KO -> pathway` 信息时，脚本会自动展开成 `gene -> pathway`，不需要平台在线查询 KEGG。

## 3. 构建命令


先安装工具包：

```bash
pip install -e ./scripts
```

安装后使用 `omichubtools refdb build`：

示例：构建生菜 v11。

```bash
omichubtools refdb build \
  --species-id Lsat \
  --scientific-name "Lactuca sativa" \
  --common-name "生菜" \
  --taxonomy-id 4236 \
  --version-id Lsat_v11 \
  --version-name v11 \
  --assembly-name Lsat.1.v11 \
  --display-name "生菜 (Lsat.1.v11)" \
  --category plant \
  --release-date 2023-05 \
  --description "生菜 v11 参考基因组与功能注释库" \
  --fasta /data/omichub/omichub_data/db/Lsat/v11/Lsat.1.v11.fa \
  --gff /data/omichub/omichub_data/db/Lsat/v11/Lsat.1.v11.gff3 \
  --go /data/omichub/omichub_data/db/Lsat/v11/go_annotations.tsv \
  --go-terms /data/omichub/omichub_data/db/Lsat/v11/go_terms.tsv \
  --ko /data/omichub/omichub_data/db/Lsat/v11/ko_annotations.tsv \
  --kegg /data/omichub/omichub_data/db/Lsat/v11/kegg_annotations.tsv \
  --out-dir /data/omichub/omichub_data/db/Lsat/v11/build \
  --force
```

最小命令只需要 FASTA：

```bash
omichubtools refdb build \
  --species-id Lsat \
  --version-id Lsat_v11 \
  --fasta /data/omichub/omichub_data/db/Lsat/v11/Lsat.1.v11.fa \
  --out-dir /data/omichub/omichub_data/db/Lsat/v11/build
```

## 4. 输出文件

| 文件 | 说明 |
| --- | --- |
| `database.sqlite` | 统一 SQLite 查询库，包含 GFF 特征、基因、转录本、GO term、GO、KO、KEGG 注释 |
| `<fasta>.fai` | FASTA 随机访问索引；默认输出在 `--out-dir`，也可以用 `--fai` 指定已有索引 |
| `database_manifest.json` | 构建产物清单，记录物种、版本、输入文件、统计量和路径 |
| `jbrowse_assembly_snippet.yaml` | 可合并进 `tool_configs/jbrowse/jbrowse_config.yaml` 的 assembly 配置片段 |
| `build_report.json` | 构建统计报告，便于排查基因数、注释数、通路数是否合理 |

## 5. SQLite 表结构摘要

| 表 | 来源 | 用途 |
| --- | --- | --- |
| `fasta_sequences` | FASTA/FAI | 染色体/contig 长度与索引偏移 |
| `features` | GFF/GTF | 全量 feature 行，支持按类型、坐标、gene_id 查询 |
| `relations` | GFF/GTF Parent | gene/transcript/exon 层级关系 |
| `genes` | GFF/GTF | 基因中心表 |
| `transcripts` | GFF/GTF | 转录本表 |
| `exons` | GFF/GTF | 外显子表 |
| `go_terms` | GO terms TSV/CSV/OBO | GO ID -> term/namespace/definition |
| `go_annotations` | GO TSV | gene -> GO，必要时由 `go_terms` 补全 term/namespace |
| `ko_annotations` | KO TSV 或 KEGG TSV 格式 B | gene -> KO |
| `ko_pathway_links` | KEGG TSV 格式 C | KO -> pathway |
| `kegg_annotations` | KEGG TSV 或 KO 展开 | gene -> pathway |

## 6. 注册到平台

脚本不会直接修改平台配置。构建完成后：

1. 打开输出目录里的 `jbrowse_assembly_snippet.yaml`。
2. 将其中的 `- id: ...` 片段追加到 `tool_configs/jbrowse/jbrowse_config.yaml` 的 `assemblies:` 下。
3. 如果 GFF 要作为 JBrowse 轨道显示，还需要在 `preset_tracks:` 下追加对应轨道。
4. 调用配置 reload 接口，或等待配置加载器基于 mtime 热重载。

```bash
curl -X POST http://localhost:8000/api/v1/jbrowse/config/reload
```

当前平台侧只会读取 YAML 中的 `path`、`index_path`、`db_path` 和状态字段，不会触发 FA/GFF/KO/KEGG 转换。

## 7. 排查清单

| 问题 | 排查方式 |
| --- | --- |
| FASTA 打不开 | 确认路径在 `/data/omichub` 下，web/nginx 容器有读取权限 |
| JBrowse 无法加载序列 | 检查 `fasta` 和 `fai` 路径是否都存在，染色体名是否与轨道一致 |
| gene 数量为 0 | 检查 GFF 第 3 列是否存在 `gene`，属性里是否有 `ID` 或 `gene_id` |
| transcript/exon 数量为 0 | 检查 GFF 是否有 `mRNA/transcript/exon`，以及 `Parent` 关系是否正确 |
| KEGG 注释为 0 | 如果 KEGG 是 KO->pathway，必须同时传 `--ko`，否则无法展开到 gene |
| 平台压力升高 | 确认没有在 Web/Celery 中调用构建脚本；构建应只在命令行或独立机器执行 |
| 输出 DB 已存在 | 使用 `--force` 覆盖，或换一个 `--out-dir` |

## 8. 建议的运维边界

- 大物种首次构建建议在独立计算节点或低峰维护窗口执行。
- 原始文件和生成库都放在 `/data/omichub/omichub_data/db/`，平台只读。
- 不要在用户请求链路中运行 `samtools`、GFF 解析、KO/KEGG 展开。
- 构建完成后先看 `build_report.json`，确认 gene、GO、KO、KEGG 数量再注册到平台。
- 后续如需要正式 API，可让后端只查询 `database.sqlite`，仍不要在平台内做转换。
