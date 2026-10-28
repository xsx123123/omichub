# OmicHub 沙盒终端：卡片对齐修复与第二批镜像（RNA-seq / 组装 / 宏基因组）

> 本文档独立成册，包含本次新增的两件事：
> **Part 1** 镜像卡片对齐修复提示词（第四轮前端优化）；
> **Part 2** 第二批三个用途镜像（RNA-seq / 基因组组装 / 宏基因组）的完整 Dockerfile、
> yaml 注册项与构建验收提示词。
> 前置文档：《OmicHub沙盒终端优化与多用途镜像方案.md》（第一批镜像与前三轮前端优化）。

## 背景速览

- 现状：终端启动页已经三轮优化，滑块等比刻度、推荐标识、内存 GB/MB 格式化均已达标；
  残留唯一问题是**镜像卡片高度不齐**（网格只均分列，行方向高度由内容决定，描述行数
  不同导致卡片长短不一，选中描边还造成 2px 跳动）。
- 已有镜像（5 个）：`base` 基础生信、`scrna` 单细胞、`gatk` 变异检测、`ggplot2` 科研绘图。
- 镜像机制回顾：`docker/Dockerfile.xxx` 构建 → `terminal_images.yaml` 注册（mtime 热重载，
  前端零改动）；生产安全约束：非 root 1000:1000、只读根文件系统、tmpfs /tmp。

---

## Part 1：卡片对齐修复提示词（粘给编码 Agent）

```text
你是一名资深前端工程师。项目为 OmicHub 多助手平台，前端 Vue3 + Naive UI。
涉及文件：frontend/src/components/terminal/ImageSelector.vue。

背景：云端沙盒终端启动页已经过多轮优化，目前唯一问题是镜像卡片高度不齐。
本次只修对齐，禁止改动卡片内容结构、选中逻辑与页面其他部分。

## 问题与修复

1. 同行卡片高度不齐（"基础生信"比"单细胞分析"高一截，第二行两张底边错位）：
   卡片网格设置 grid-auto-rows: 1fr，使所有行等高；卡片自身 display: flex;
   flex-direction: column，底部 meta 行（"默认 X GB / X 核"）设置
   margin-top: auto 吸附卡片底部——4 张卡片的 meta 行横向对齐成一条线。
2. 选中态高度微偏移：选中卡 2px 描边导致内容区比未选中卡小 2px、视觉抖动。
   修复：所有卡片常态预留 2px 透明边框（border: 2px solid transparent），
   选中时仅替换 border-color，不改尺寸；或改用 outline / inset box-shadow 实现描边。
3. 描述区域占位统一：描述固定 2 行高度（line-height 1.6 × 2 ≈ 42px，
   min-height 42px），不足 2 行的卡片占位补齐，保证 tags 行起点一致。

## 验收标准

- [ ] 4 张卡片顶边、底边两两对齐，meta 行在同一水平线
- [ ] 选中/取消选中时卡片无任何尺寸跳动
- [ ] 新增镜像（卡片数变为 5~8 张）后网格依然逐行对齐
- [ ] 1280/1600/1920 三宽度下对齐均成立
```

---

## Part 2：第二批三个用途镜像

### 2.1 选型说明与优先级

| 优先级 | 镜像 | ID | 预装 | 建议资源 |
|---|---|---|---|---|
| ⭐ 首推 | 🧬 RNA-seq 流程 | `rnaseq` | hisat2 / salmon / kallisto / featureCounts / DESeq2 / tximport | 4096MB / 4 核 |
| 次推 | 🧫 基因组组装 | `assembly` | SPAdes / flye / QUAST / BUSCO / minimap2 | 8192MB / 4 核 |
| 可选 | 🦠 宏基因组 | `metagenomics` | kraken2 / bracken / centrifuge / fastp / MultiQC | 8192MB / 4 核 |

- RNA-seq 为生信最高频流程，与已有镜像零重叠；全部走 apt 二进制（含 `r-bioc-deseq2`），构建快；
- **不建议现阶段做**：Jupyter 镜像（当前架构仅暴露 ttyd 7681 单端口，需改网络层）、
  深度学习镜像（CPU 沙盒性价比低，镜像体积 5GB+）；
- ⚠️ 前置条件：`terminal_config.yaml` 的 `max_resources.memory_mb` 必须 ≥8192，
  否则组装/宏基因组的 8GB 推荐值无法申请；
- ⚠️ kraken2/bracken 数据库（几十 GB）不进镜像，用户放 workspace 后 `--db` 指定。

### 2.2 Dockerfile.rnaseq

```dockerfile
# tool_configs/terminal/docker/Dockerfile.rnaseq
# 构建: docker build -t omichub/sandbox-rnaseq:latest -f tool_configs/terminal/docker/Dockerfile.rnaseq tool_configs/terminal/docker/
FROM omichub/sandbox-terminal:latest

USER root

# 全部走 apt 二进制（Debian Med 源）：比对/定量 + DESeq2 差异表达
RUN apt-get update && apt-get install -y --no-install-recommends \
      hisat2 salmon subread \
      r-base-core r-bioc-deseq2 r-bioc-tximport r-cran-readr \
    && rm -rf /var/lib/apt/lists/*

# kallisto：apt 版本若 <0.46 则改用官方二进制
ARG KALLISTO_VERSION=0.48.0
RUN apt-get update && apt-get install -y --no-install-recommends kallisto \
    || (wget -q "https://github.com/pachterlab/kallisto/releases/download/v${KALLISTO_VERSION}/kallisto_linux-v${KALLISTO_VERSION}.tar.gz" -O /tmp/kallisto.tar.gz \
        && tar -xzf /tmp/kallisto.tar.gz -C /opt \
        && ln -s /opt/kallisto/kallisto /usr/local/bin/kallisto \
        && rm /tmp/kallisto.tar.gz) \
    && rm -rf /var/lib/apt/lists/*

USER 1000
```

### 2.3 Dockerfile.assembly

```dockerfile
# tool_configs/terminal/docker/Dockerfile.assembly
# 构建: docker build -t omichub/sandbox-assembly:latest -f tool_configs/terminal/docker/Dockerfile.assembly tool_configs/terminal/docker/
FROM omichub/sandbox-terminal:latest

USER root

# 二代 SPAdes + 三代 flye + 质量评估 QUAST/BUSCO + minimap2
RUN apt-get update && apt-get install -y --no-install-recommends \
      spades flye quast busco minimap2 \
    && rm -rf /var/lib/apt/lists/*

USER 1000
```

### 2.4 Dockerfile.metagenomics

```dockerfile
# tool_configs/terminal/docker/Dockerfile.metagenomics
# 构建: docker build -t omichub/sandbox-metagenomics:latest -f tool_configs/terminal/docker/Dockerfile.metagenomics tool_configs/terminal/docker/
FROM omichub/sandbox-terminal:latest

USER root

RUN apt-get update && apt-get install -y --no-install-recommends \
      kraken2 bracken centrifuge fastp \
    && rm -rf /var/lib/apt/lists/* \
    && pip3 install --no-cache-dir multiqc

# 注意：kraken2/bracken 数据库不进镜像（几十 GB），
# 用户需将数据库放 /home/omichub/workspace 或 raw_data，通过 --db 指定

USER 1000
```

### 2.5 terminal_images.yaml 注册项（追加）

```yaml
  - id: rnaseq
    name: RNA-seq 流程
    description: 预装 hisat2 / salmon / kallisto / featureCounts / DESeq2 / tximport，覆盖比对、定量到差异表达全流程
    image: omichub/sandbox-rnaseq:latest
    tags: [转录组, 差异表达]
    icon: 🧬
    resources: { memory_mb: 4096, cpu_cores: 4.0, pid_limit: 200 }
    enabled: true
  - id: assembly
    name: 基因组组装
    description: 预装 SPAdes / flye / QUAST / BUSCO / minimap2，二代三代组装与质量评估一体
    image: omichub/sandbox-assembly:latest
    tags: [组装, SPAdes, 三代]
    icon: 🧫
    resources: { memory_mb: 8192, cpu_cores: 4.0, pid_limit: 200 }
    enabled: true
  - id: metagenomics
    name: 宏基因组
    description: 预装 kraken2 / bracken / centrifuge / fastp / MultiQC（数据库需自行放入 workspace 后 --db 指定）
    image: omichub/sandbox-metagenomics:latest
    tags: [宏基因组, 物种注释]
    icon: 🦠
    resources: { memory_mb: 8192, cpu_cores: 4.0, pid_limit: 200 }
    enabled: true
```

### 2.6 提示词：构建三个新镜像（粘给编码 Agent）

```text
你是一名资深 DevOps/后端工程师。项目为 OmicHub 多助手平台。先阅读
tool_configs/terminal/README.md 与 docker/ 目录下现有 Dockerfile（基础镜像及
scrna/gatk/ggplot2 三个已交付镜像），沿用同一模式：FROM omichub/sandbox-terminal:latest、
构建期 USER root 安装后切回 USER 1000、apt 二进制优先、禁止源码编译。

任务：新增三个镜像并注册，完成后逐镜像验收。

## 一、构建（Dockerfile 放 tool_configs/terminal/docker/）
1. Dockerfile.rnaseq → omichub/sandbox-rnaseq:latest
   apt 安装：hisat2 salmon kallisto subread r-base-core r-bioc-deseq2
   r-bioc-tximport r-cran-readr；若 apt 的 kallisto 版本过旧（<0.46），
   改用 GitHub release 官方二进制。
2. Dockerfile.assembly → omichub/sandbox-assembly:latest
   apt 安装：spades flye quast busco minimap2 samtools。
3. Dockerfile.metagenomics → omichub/sandbox-metagenomics:latest
   apt 安装：kraken2 bracken centrifuge fastp；pip3 install multiqc。
   注意：kraken2/bracken 数据库不进镜像，在镜像描述与欢迎信息中提示用户
   将数据库放 /home/omichub/workspace 或 raw_data 后通过 --db 指定。

## 二、注册 terminal_images.yaml（热重载，无需重启）
- id: rnaseq，名称"RNA-seq 流程"，icon 🧬，tags [转录组, 差异表达]，
  resources: 4096MB / 4核 / pid 200
- id: assembly，名称"基因组组装"，icon 🧫，tags [组装, SPAdes, 三代]，
  resources: 8192MB / 4核 / pid 200
- id: metagenomics，名称"宏基因组"，icon 🦠，tags [宏基因组, 物种注释]，
  resources: 8192MB / 4核 / pid 200
- 前置检查：terminal_config.yaml 的 max_resources.memory_mb 必须 ≥8192，
  不足先调整。

## 三、逐镜像验收（生产安全参数：--user 1000:1000 --read-only --tmpfs /tmp --cap-drop ALL）
1. ttyd 健康检查通过（wget --spider localhost:7681）。
2. rnaseq：hisat2 --version、salmon --version、featureCounts -v、
   Rscript -e 'library(DESeq2)' 全通过。
3. assembly：spades.py --version、flye --version、quast.py --version 全通过。
4. metagenomics：kraken2 --version、bracken -v、fastp --version、
   multiqc --version 全通过。
5. 前端各建一个会话验证终端可用、workspace 读写正常、销毁 auto_remove。

## 验收标准
- [ ] 三镜像构建成功，记录各自体积
- [ ] 前端选择器出现 7 张卡片且逐行对齐（配合 ImageSelector 对齐修复）
- [ ] 三镜像只读根文件系统下工具全部可用
- [ ] base 与已有四镜像零回归
```

---

## 实施顺序与风险

- **两部分可并行**：对齐修复只动 `ImageSelector.vue` 一个文件；镜像构建为纯增量。
  验收时合并检查"7 张卡片逐行对齐"。
- **风险**：① SPAdes/kraken2 内存大户，`max_resources.memory_mb` 未调到 8192 则推荐值
  无法申请（前置条件必须先做）；② apt 包名/版本在不同 Ubuntu 源可能有差异，构建失败时
  先 `apt-cache policy <pkg>` 确认再改用官方二进制回退方案；③ 宏基因组镜像需向用户
  明确"数据库自备"预期，避免误以为开箱即用。
