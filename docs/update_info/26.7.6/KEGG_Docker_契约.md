# OmicHub 富集分析 —— R Docker 容器输入/输出契约

> 面向「自己造镜像」的实现者。后端（Python）只负责拼 `docker run` 命令、读写挂载目录、
> 解析 CSV、生成 Plotly；**R 镜像内部跑什么、吃什么、吐什么**全由本文档约束。
>
> 配套：物种配置见 `tool_configs/enrichments/species_config.yaml`；后端调度见
> `src/omichub/infrastructure/execution/enrichment_runner.py`。

---

## 1. 镜像总览

| 项 | 值 |
|----|----|
| 镜像名 | `omichub-r-enrichment:v1`（可经 `ENRICHMENT_DOCKER_IMAGE` 覆盖） |
| 职责 | 读入基因 ID 列表 → 调 `clusterProfiler::enrichKEGG()` → 产出结果 CSV |
| 产出 | **仅一个 CSV 文件**（路径由 `--output` 指定）；Plotly 由后端生成，R 不负责 |
| 入口 | `Rscript /app/run_enrichment.R ...`（由后端在 `docker run` 末尾追加） |
| 网络 | 加入 `omichub_enrichment_net`，出站经 squid 代理（仅放行 KEGG 域名） |

镜像必须以**非交互**方式运行并退出，退出码反映成败。

---

## 2. 镜像内必备 R 包

| 包 | 用途 |
|----|------|
| `clusterProfiler` | `enrichKEGG()` 富集分析主函数 |
| `org.Hs.eg.db` | 人类 ID 映射（物种：human） |
| `org.At.tair.db` | 拟南芥 ID 映射（物种：arabidopsis） |
| `argparse` | 解析命令行参数 |
| `KEGGREST`（可选） | `enrichKEGG` 内部依赖，通常随 clusterProfiler 装好 |

新增物种时，对应 `org.Xx.eg.db` 必须装进镜像，并在 `species_config.yaml` 声明 `org_db`。

---

## 3. R 脚本契约（`/app/run_enrichment.R`）

### 3.1 命令行参数

| 参数 | 必填 | 含义 |
|------|------|------|
| `--input` | 是 | 输入基因列表文件路径（容器内绝对路径） |
| `--output` | 是 | 输出 CSV 文件路径（容器内绝对路径） |
| `--kegg_code` | 是 | KEGG 物种三字码，如 `hsa` / `ath` |
| `--org_db` | 是 | OrgDb 包名，如 `org.Hs.eg.db` |
| `--id_type` | 否 | 基因 ID 类型，如 `SYMBOL` / `TAIR`（v1 由 `enrichKEGG` 自治，预留扩展） |

### 3.2 输入文件格式（`--input`）

- 纯文本，**UTF-8 无 BOM**；
- **每行一个基因 ID，无表头**；后端已去空白行、去重；
- 示例：
  ```
  TP53
  BRCA1
  EGFR
  ```

### 3.3 输出 CSV schema（`--output`）

- **UTF-8 无 BOM**，逗号分隔，**含表头**，列名必须严格一致；
- 至少包含下列列（顺序不限，多余列后端忽略）：

| 列名 | 类型 | 示例 | 后端用途 |
|------|------|------|---------|
| `ID` | str | `hsa04110` | 表格「通路 ID」+ 图表悬停 |
| `Description` | str | `Cell cycle` | 表格「通路描述」+ 图表 Y 轴 |
| `GeneRatio` | str | `5/100` | 表格「GeneRatio」+ 图表 X 轴（后端解析为数值） |
| `BgRatio` | str | `126/8000` | v1 不用，保留 |
| `pvalue` | float | `1.2e-05` | 表格「pvalue」 |
| `p.adjust` | float | `3.4e-04` | 表格「p.adjust」+ 图表颜色（-log10） |
| `geneID` | str | `TP53/BRCA1/EGFR` | v1 不用，保留（未来通路映射） |
| `Count` | int | `5` | 表格「Count」+ 图表气泡大小 |

- **无富集结果时仍写一个只含表头的空 CSV**（退出码 0），不要报错；
- 行内字段含逗号时须用双引号包裹（标准 CSV 转义）。

### 3.4 退出码

| 退出码 | 含义 | 后端行为 |
|--------|------|---------|
| `0` | 成功，CSV 已写入 `--output` | 解析 CSV 返回结果 |
| 非 `0` | 失败 | 后端抛 `TaskExecutionError`，把 **stderr 末尾 800 字**回传前端 |

### 3.5 日志约定

- 正常进度信息写 **stdout**（后端记日志，不回传前端）；
- 错误信息写 **stderr**，人类可读（后端截取末尾回传用户）；
- 切勿把结果 CSV 内容打到 stdout（后端只读文件）。

---

## 4. `docker run` 调用形态（后端实际拼接）

后端 `EnrichmentDockerRunner.build_command()` 生成如下命令（参数全部来自 settings）：

```bash
docker run --rm \
    --name omichub-enrich-<task_id前8位> \
    --network omichub_enrichment_net \
    -e http_proxy=http://squid-proxy:3128 \
    -e https_proxy=http://squid-proxy:3128 \
    -e no_proxy=localhost,127.0.0.1 \
    -v /data/omichub:/data/omichub \
    --memory 2g \
    --cpus 2.0 \
    omichub-r-enrichment:v1 \
    Rscript /app/run_enrichment.R \
    --input  /data/omichub/users/<user_id>/enrichment/<task_id>/gene_list.txt \
    --output /data/omichub/users/<user_id>/enrichment/<task_id>/kegg_result.csv \
    --kegg_code hsa \
    --org_db org.Hs.eg.db \
    --id_type SYMBOL
```

对应 settings（`.env` 可覆盖）：

| setting | 默认值 | 说明 |
|---------|--------|------|
| `ENRICHMENT_DOCKER_IMAGE` | `omichub-r-enrichment:v1` | 镜像 |
| `ENRICHMENT_DOCKER_NETWORK` | `omichub_enrichment_net` | Docker 网络（须与 squid 同网） |
| `ENRICHMENT_PROXY_URL` | `http://squid-proxy:3128` | 出站代理 |
| `ENRICHMENT_DATA_MOUNT` | `/data/omichub` | 宿主挂载源（容器内同路径） |
| `ENRICHMENT_EXEC_TIMEOUT` | `120` | 超时秒数，超时 kill 容器 |
| `ENRICHMENT_MEMORY` | `2g` | 容器内存上限 |
| `ENRICHMENT_CPUS` | `2.0` | 容器 CPU 核数 |

---

## 5. 网络与代理

- 容器加入 `omichub_enrichment_net` 桥接网络，与 `squid-proxy` 同网；
- 出站 HTTP/HTTPS 经 `http_proxy` / `https_proxy` 走 squid，**仅放行 `.kegg.jp` / `.genome.jp`**，其余域名 squid 拒绝；
- 镜像**不应**内置其它外网依赖（如 Bioconductor 在线安装），所有包须在构建时离线装好；
- `enrichKEGG()` 会实时拉取 KEGG REST 接口，网络抖动可能失败 → 失败时按 §3.4 非 0 退出 + stderr。

squid.conf 关键段（供部署参考）：
```
acl kegg_domain dstdomain .kegg.jp .genome.jp
http_access allow kegg_domain
http_access deny all
```

---

## 6. 路径与权限约定

- 宿主 `/data/omichub` 与容器内 `/data/omichub` **同路径挂载**，故 `--input` / `--output`
  直接用宿主绝对路径，容器内所见一致；
- 容器对挂载目录有**读写权限**（写 `--output`）；
- 容器**只允许写** `--output` 指定文件与 `/tmp`，不得污染其它路径；
- 结果目录 `/data/omichub/users/<user_id>/enrichment/<task_id>/` 由后端预先创建，
  容器无需 `mkdir`。

---

## 7. 示例

### 7.1 输入（gene_list.txt）
```
TP53
BRCA1
EGFR
MYC
CDK2
```

### 7.2 输出（kegg_result.csv）
```csv
ID,Description,GeneRatio,BgRatio,pvalue,p.adjust,geneID,Count
hsa04110,Cell cycle,3/100,126/8000,1.2e-05,3.4e-04,TP53/BRCA1/CDK2,3
hsa03430,Mismatch repair,1/100,23/8000,8.9e-04,1.2e-02,BRCA1,1
```

### 7.3 失败（stderr，退出码 1）
```
Error: cannot connect to KEGG REST API (timeout after 30s)
```
后端将回传：`富集分析失败 (exit=1): Error: cannot connect to KEGG REST API ...`

---

## 8. 参考 R 脚本

镜像内的 `/app/run_enrichment.R` 可参照如下实现（按 §3 契约约束）：

```r
library(argparse)
library(clusterProfiler)

parser <- ArgumentParser()
parser$add_argument("--input",      help="输入基因列表路径（每行一个 ID，无表头）")
parser$add_argument("--output",     help="输出 CSV 路径")
parser$add_argument("--kegg_code",  help="KEGG 物种三字码，如 hsa")
parser$add_argument("--org_db",     help="OrgDb 包名，如 org.Hs.eg.db")
parser$add_argument("--id_type",    help="基因 ID 类型（预留）", required=FALSE)
args <- parser$parse_args()

# 读入基因列表
gene_list <- read.table(args$input, header=FALSE, stringsAsFactors=FALSE)$V1
gene_list <- unique(gene_list[nzchar(gene_list)])

# 空输入：写空 CSV（仅表头）后成功退出
if (length(gene_list) == 0) {
    df <- data.frame(ID=character(), Description=character(), GeneRatio=character(),
                     BgRatio=character(), pvalue=numeric(), p.adjust=numeric(),
                     geneID=character(), Count=integer())
    write.csv(df, file=args$output, row.names=FALSE)
    quit(status=0)
}

# KEGG 富集（在线 API，走 http_proxy）
res <- tryCatch(
    enrichKEGG(gene=gene_list, organism=args$kegg_code, pvalueCutoff=1.0),
    error=function(e) {
        message(as.character(e))   # 进 stderr
        quit(status=1)
    }
)

# 无命中：写空 CSV（仅表头）
if (is.null(res) || nrow(as.data.frame(res)) == 0) {
    df <- data.frame(ID=character(), Description=character(), GeneRatio=character(),
                     BgRatio=character(), pvalue=numeric(), p.adjust=numeric(),
                     geneID=character(), Count=integer())
    write.csv(df, file=args$output, row.names=FALSE)
    quit(status=0)
}

write.csv(as.data.frame(res), file=args$output, row.names=FALSE)
```

> `pvalueCutoff=1.0` 保留全部通路，由后端/前端排序展示 Top N；如需更严可在镜像内调。

---

## 9. Dockerfile 示例

```dockerfile
FROM rocker/r-ver:4.4

RUN apt-get update && apt-get install -y --no-install-recommends libxml2-dev libcurl4-openssl-dev && \
    rm -rf /var/lib/apt/lists/*

RUN R -e 'install.packages(c("argparse"), repos="https://cloud.r-project.org")'
RUN R -e 'BiocManager::install(c("clusterProfiler","org.Hs.eg.db","org.At.tair.db"), update=FALSE, ask=FALSE)'

COPY run_enrichment.R /app/run_enrichment.R

WORKDIR /app
ENTRYPOINT ["Rscript", "/app/run_enrichment.R"]
```

构建：`docker build -t omichub-r-enrichment:v1 .`

---

## 10. 联调检查清单

- [ ] `docker run --rm omichub-r-enrichment:v1 --help` 正常打印参数
- [ ] 离线空输入 → 退出 0，CSV 仅表头
- [ ] 正常基因列表 → 退出 0，CSV 含 `ID/Description/GeneRatio/pvalue/p.adjust/Count`
- [ ] 断网/代理失败 → 退出非 0，stderr 有可读错误
- [ ] 容器未写 `--output` 与 `/tmp` 之外的路径
- [ ] 镜像已预装所有 OrgDb，启动时不联网装包
