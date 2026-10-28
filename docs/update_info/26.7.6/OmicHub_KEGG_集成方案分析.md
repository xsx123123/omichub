# OmicHub 平台 —— KEGG 集成方案分析文档

> 基于《OmicHub 平台 - 富集分析工具详细实现方案》中 KEGG 相关内容的梳理与评估

---

## 一、架构总览

```
┌──────────────┐      ┌──────────────────┐      ┌─────────────────────┐
│   前端 (UI)   │ ──── │  后端 (Python)    │ ──── │  计算引擎 (R Docker) │
│              │      │                  │      │                     │
│ Gene ID 输入 │      │ YAML 配置解析     │      │ clusterProfiler     │
│ 物种下拉菜单  │ ──── │ Docker 命令拼接  │ ──── │ enrichKEGG()        │
│ Plotly 图表  │      │ Plotly JSON 生成 │      │                     │
└──────────────┘      └──────────────────┘      └─────────────────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │ Squid Proxy      │
                    │ 仅放行 KEGG 域名  │
                    └──────────────────┘
```

---

## 二、KEGG 核心配置设计

### 2.1 目录结构

```
/data/omichub/refdata/enrichments/
├── species_config.yaml    # 全局物种配置（含 KEGG 参数）
├── human/
│   ├── GO_bp.gmt
│   └── KEGG.RData        # KEGG 离线数据（预留）
└── arabidopsis/
    ├── GO_bp.gmt
    └── KEGG.RData
```

### 2.2 YAML 配置字段

```yaml
species_list:
  - id: "human"
    display_name: "Homo sapiens (人类)"
    enabled: true
    kegg_code: "hsa"               # ⭐ KEGG API 物种三字码
    org_db: "org.Hs.eg.db"         # R OrgDb 包名
    id_type: "SYMBOL"              # 基因 ID 类型
    files:
      go_gmt: "human/GO_bp.gmt"
      kegg_rdata: "human/KEGG.RData"  # 离线数据路径（预留）
```

### 2.3 已定义物种参数

| 物种 | kegg_code | org_db | id_type |
|------|-----------|--------|---------|
| 人类 (Homo sapiens) | `hsa` | `org.Hs.eg.db` | `SYMBOL` |
| 拟南芥 (Arabidopsis thaliana) | `ath` | `org.At.tair.db` | `TAIR` |

---

## 三、R 计算层 — KEGG 富集实现

### 3.1 容器镜像

```
omichub-r-enrichment:v1
```

内嵌 `clusterProfiler` 等生信包，封闭运行。

### 3.2 核心代码

```r
library(argparse)
library(clusterProfiler)

parser <- ArgumentParser()
parser$add_argument("--input",  help="输入基因列表路径")
parser$add_argument("--output", help="输出 CSV 路径")
parser$add_argument("--kegg_code", help="KEGG 物种三字码 (如 hsa)")
parser$add_argument("--org_db",    help="OrgDb 包名")
parser$add_argument("--id_type",   help="基因 ID 类型")
args <- parser$parse_args()

# 读取基因列表
gene_list <- read.table(args$input, header=FALSE)$V1

# 动态加载 OrgDb
dyn.load(args$org_db, character.only = TRUE)

# ⭐ KEGG 富集分析（调用 KEGG 在线 API）
kegg_res <- enrichKEGG(
    gene = gene_list,
    organism = args$kegg_code
)

# 结果导出
write.csv(as.data.frame(kegg_res), file=args$output, row.names=FALSE)
```

### 3.3 命令行调用示例

```bash
docker run --rm \
    --network omichub_enrichment_net \
    -e http_proxy=http://squid-proxy:3128 \
    -v /data/omichub:/data/omichub \
    omichub-r-enrichment:v1 \
    Rscript /app/run_enrichment.R \
    --input /data/gene_list.txt \
    --output /data/kegg_result.csv \
    --kegg_code hsa \
    --org_db org.Hs.eg.db \
    --id_type SYMBOL
```

---

## 四、后端调度层（Python）

### 4.1 动态菜单接口

解析 YAML 文件，返回已启用的物种列表：

```python
# 返回格式
[
    {"id": "human", "name": "Homo sapiens (人类)"},
    {"id": "arabidopsis", "name": "Arabidopsis thaliana (拟南芥)"}
]
```

### 4.2 容器调度流程

```python
import subprocess
import yaml

# 根据用户选择的 species_id 从 YAML 提取参数
species_meta = load_species_config(species_id)

cmd = [
    "docker", "run", "--rm",
    "--network", "omichub_enrichment_net",
    "-e", "http_proxy=http://squid-proxy:3128",
    "-v", "/data/omichub:/data/omichub",
    "omichub-r-enrichment:v1",
    "Rscript", "/app/run_enrichment.R",
    "--input", task_input_path,
    "--output", task_output_path,
    "--kegg_code", species_meta["kegg_code"],
    "--org_db", species_meta["org_db"],
    "--id_type", species_meta["id_type"]
]
subprocess.run(cmd, check=True)
```

### 4.3 Plotly 可视化生成

```python
import pandas as pd
import plotly.express as px
import numpy as np

def generate_kegg_plot(csv_path):
    df = pd.read_csv(csv_path).sort_values('p.adjust').head(20)
    df['-log10(p.adjust)'] = -np.log10(df['p.adjust'])

    fig = px.scatter(
        df,
        x='GeneRatio',
        y='Description',
        size='Count',
        color='-log10(p.adjust)',
        hover_name='ID',
        title='KEGG Pathway Enrichment Top 20'
    )
    return fig.to_json()
```

---

## 五、网络安全层（Squid Proxy）

### 5.1 核心配置

```
# squid.conf
acl kegg_domain dstdomain .kegg.jp .genome.jp
http_access allow kegg_domain
http_access deny all
```

### 5.2 网络拓扑

```
┌─────────────────────────────────────────────┐
│          Docker Bridge 网络                  │
│      omichub_enrichment_net                  │
│                                              │
│   ┌──────────────┐    ┌──────────────────┐  │
│   │  squid-proxy  │    │  R 计算容器       │  │
│   │  (3128端口)   │◄───│  http_proxy      │  │
│   │  白名单过滤   │    │  强制走代理       │  │
│   └──────┬───────┘    └──────────────────┘  │
│          │                                   │
│          ▼ (仅允许)                           │
│     ┌─────────┐    ┌──────────┐              │
│     │ kegg.jp │    │genome.jp │              │
│     └─────────┘    └──────────┘              │
└─────────────────────────────────────────────┘
```

---

## 六、前端 UI 设计

### 6.1 模块位置

生信工具箱面板 → **「通路富集分析」**

### 6.2 输入区

| 组件 | 功能 |
|------|------|
| 多行文本域 | 手动粘贴 Gene ID 列表 |
| 文件上传 | 上传基因列表文件 |
| 物种下拉菜单 | 选择物种（自动对接 YAML 配置接口） |

### 6.3 结果展示区

| 视图 | 功能 |
|------|------|
| **图表视图** | Plotly.js 渲染交互式气泡图（支持悬停、缩放） |
| **表格视图** | 分页展示完整富集结果，支持导出 CSV |

### 6.4 气泡图展示字段

- **X 轴**：GeneRatio
- **Y 轴**：通路 Description
- **气泡大小**：Count（富集基因数）
- **颜色**：-log10(p.adjust)
- **悬停信息**：通路 ID

---

## 七、方案评估

### 7.1 优势

| 优势 | 说明 |
|------|------|
| 物种扩展灵活 | YAML 配置驱动，新增物种只需添加配置 |
| 安全隔离 | Squid 代理严格限制外网访问，仅放行 KEGG |
| 容器化 | R 环境封闭运行，避免依赖冲突 |
| 交互式可视化 | Plotly 图表支持悬停、缩放，体验好 |

### 7.2 潜在问题与风险

| 问题 | 风险等级 | 说明 |
|------|---------|------|
| **在线 API 依赖** | 🔴 高 | `enrichKEGG()` 实时调用 KEGG 外网接口，网络不稳定时分析会失败 |
| `KEGG.RData` 未使用 | 🟡 中 | 目录结构中有离线数据文件，但 R 代码中未使用，与在线调用策略矛盾 |
| 可视化图表单一 | 🟡 中 | 仅实现了气泡图，缺少柱状图、通路网络图（cnetplot）、树状图等常见展示 |
| 新物种 KEGG 支持 | 🟡 中 | 并非所有物种都有 KEGG 注释，需提前校验 `kegg_code` 有效性 |
| 无外网环境 | 🔴 高 | 完全离线环境下无法运行，需考虑本地 KEGG 数据库方案 |

### 7.3 优化建议

#### 建议 1：增加离线 fallback 机制

```r
# 策略：先尝试在线，失败后使用本地 KEGG.RData
kegg_res <- tryCatch({
    # 在线模式
    enrichKEGG(gene = gene_list, organism = args$kegg_code)
}, error = function(e) {
    # 离线模式
    load(args$kegg_rdata)  # 加载本地 KEGG 数据
    enricher(gene = gene_list, TERM2GENE = kegg_term2gene)
})
```

#### 建议 2：丰富可视化类型

| 图表类型 | 用途 |
|---------|------|
| 柱状图（Bar Plot） | 展示 Top 通路 p-value 比较 |
| 气泡图（Dot Plot） | 已支持，展示 GeneRatio + Count + pvalue |
| 通路网络图（Cnet Plot） | 展示基因与通路的关系网络 |
| 树状图（Enrichment Tree） | 聚类展示通路间的层次关系 |
|  upset 图 | 展示多个通路间的基因重叠情况 |

#### 建议 3：增加 KEGG 通路映射功能

分析完成后提供跳转到 KEGG 官方通路图的链接：
```
https://www.kegg.jp/kegg-bin/show_pathway?hsa04110/基因列表
```

#### 建议 4：物种 KEGG 可用性校验

在 YAML 配置中添加 `kegg_supported` 标记，前端自动灰度不支持 KEGG 的物种。

---

## 八、总结

该方案整体架构清晰，采用 YAML 配置驱动 + 容器化计算 + 代理隔离的设计思路比较成熟。核心依赖 `clusterProfiler::enrichKEGG()` 在线调用 KEGG API，适合有稳定外网的环境。建议补充**离线 fallback** 和**多类型可视化**，使工具更加健壮和实用。

---

*文档生成时间：2026-07-06*
*基于 OmicHub 富集分析工具方案 v1.0*
