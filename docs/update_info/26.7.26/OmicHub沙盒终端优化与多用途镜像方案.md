# OmicHub 云端沙盒终端：前端优化与多用途镜像方案

> 本文档独立成册，覆盖沙盒终端的两件事：
> **Part 1** 启动页前端优化（含可直接粘贴给编码 Agent 的提示词）；
> **Part 2** 新增三个用途镜像（单细胞 / GATK&PLINK / ggplot2，含完整 Dockerfile、
> yaml 注册项与构建验收提示词）。
> 依据：`tool_configs/terminal/README.md`（当前架构文档）。

## 背景速览

- 架构：浏览器 xterm.js ↔ FastAPI WebSocket 代理（ttyd 协议翻译）↔ Docker 沙盒容器（ttyd:7681）；
- 镜像机制：`terminal_images.yaml` 定义可用镜像（id/name/description/image/tags/icon/resources/env/enabled），按 mtime 热重载，**前端镜像选择器零改动即时生效**；
- 新增镜像只需：`docker/Dockerfile.xxx` 构建镜像 → yaml 注册条目 → 刷新页面；
- 生产安全约束：非 root（1000:1000）、根文件系统只读、cap_drop ALL、tmpfs `/tmp` 与 `~/.cache`、auto_remove 即用即毁；
- 基础镜像 `omichub/sandbox-terminal:latest`：Ubuntu 22.04 + ttyd 1.7.7 + zsh/oh-my-zsh/oh-my-posh + samtools/bcftools/bedtools/fastqc/seqkit + numpy/pandas/biopython/pysam。

---

## Part 1：终端启动页前端优化

### 1.1 现状问题（对照截图与架构）

1. **镜像选择器按"只有一个镜像"设计**：单卡片 + 大片留白，新镜像接入后布局即崩；
2. **顶部三张统计卡（镜像大小/预装工具/预计启动 3 秒）信息价值低**、占位大，"预计启动"为伪精确指标；
3. **内存滑块刻度为 256M/5.8G/11.3G… 非线性拼接**，无法凭直觉拖动；默认 512MB 对单细胞类镜像必然 OOM——资源默认值未与镜像联动（`images[].resources` 字段后端已支持，前端未消费）；
4. **启动配置预览与左栏信息重复**，挂载目录长路径折行；
5. **内容区限宽过窄**，两侧大量空旷。

### 1.2 提示词：沙盒终端启动页优化（粘给编码 Agent）

```text
你是一名资深前端工程师。项目为 OmicHub 多助手平台，前端 Vue3 + Pinia + Naive UI
（先读代码确认）。涉及文件：frontend/src/views/BioTools/TerminalView.vue、
frontend/src/components/terminal/ImageSelector.vue、ResourceSettings.vue、
frontend/src/stores/terminal.ts。

任务：优化云端沙盒终端启动页布局与信息架构。先阅读上述组件与 GET /terminal/environments
返回的数据结构，理解现状后再修改。禁止推倒重写，禁止改动终端会话（XTerminal.vue /
WebSocket）逻辑。

## 需要修改的问题（逐条执行）

1. 镜像选择器改网格卡片：ImageSelector.vue 从单列卡片改为响应式网格
   （≥1200px 时 2 列，≥1600px 时 3 列），卡片内容：icon + 名称 + 一句话描述 +
   tags 徽标 + 默认资源（如"默认 4GB / 2 核"）。选中态：2px 主题色描边 + 左上角
   勾选角标，hover 态轻微上浮（translateY(-2px)，200ms）。空列表显示空状态。
2. 删除顶部三张统计卡（镜像大小/预装工具/预计启动）：镜像大小与工具数合并为
   选中卡片底部的一行 12px 灰色 meta 文字；"预计启动 3 秒"删除（伪精确指标）。
3. 资源设置重做刻度：内存滑块刻度改为等比档位（0.5G/1G/2G/4G/8G），
   CPU 刻度（0.5/1/2/4/8 核）；滑块为主、数字步进器收起为后缀小控件。
   关键联动：切换镜像时用该镜像 resources 字段重置滑块默认值（基础 512MB/1核、
   单细胞 4GB/2核），默认值在滑块轨道上标注"推荐"刻度点。
4. 启动配置预览压缩：从 6 行分隔列表改为紧凑定义列表（行高 32px、无分割线），
   仅保留 镜像/内存/CPU/挂载目录/生命周期；挂载目录用等宽字体 + 单行省略 +
   tooltip 显示全路径；"用完即毁"保留红色警示。
5. 页面布局：内容区 max-width 从当前值提升至 1400px，改三栏布局
   （左：选择分析环境｜中：资源设置｜右：配置预览+启动按钮），<1200px 时
   退化为上下堆叠。页面级无纵向大段空白。
6. 启动按钮：保持"启动 {镜像名}"动态文案，点击后进入 loading 态并禁用，
   会话创建失败时 toast 报错并恢复可点击。

## 全局约束
- 配色、圆角、字体与平台其他工具页一致；组件库沿用 Naive UI，不引新依赖。
- 与 terminal store 的字段契约（image_id / resources）不变。

## 验收标准
- [ ] 4 个镜像卡片网格展示正常，选中/悬停态清晰
- [ ] 切换镜像时资源默认值联动且标注"推荐"
- [ ] 统计卡已移除，无伪精确启动时间
- [ ] 1280/1600/1920 宽度下布局无破损、无大片留白
- [ ] 创建会话行为与改前一致
```

---

## Part 2：三个用途镜像

### 2.1 设计说明

- 三个镜像均 `FROM omichub/sandbox-terminal:latest`，继承 ttyd 1.7.7 + zsh/oh-my-zsh 环境与启动命令，只增量安装工具链；
- 遵守生产安全约束：构建时装完即切回 `USER 1000`；运行时根文件系统只读，故**缓存类目录必须指向 tmpfs**（`NUMBA_CACHE_DIR`、`MPLCONFIGDIR` → `/tmp`），否则 scanpy(numba) / matplotlib 启动即崩；
- R 包一律走 Ubuntu apt 二进制 `r-cran-*`，禁止容器内源码编译 tidyverse；
- 注册走 `terminal_images.yaml` 热重载，前端零改动；
- 单细胞镜像建议将 `terminal_config.yaml` 的 `max_resources.memory_mb` 从 4096 调至 8192（视宿主机余量）。

镜像总览：

| 镜像 | ID | 预装 | 建议默认资源 |
|---|---|---|---|
| 🧬 单细胞分析 | `scrna` | scanpy / anndata / leiden / Harmony / Scrublet / scVelo | 4096MB / 2 核 |
| 🧪 变异检测 GATK & PLINK | `gatk` | GATK4 (OpenJDK 17) / PLINK1.9 / PLINK2 / tabix | 4096MB / 4 核 |
| 📊 科研绘图 ggplot2 | `ggplot2` | R + tidyverse / ggrepel / cowplot / 中文字体 / plotnine | 1024MB / 1 核 |

### 2.2 Dockerfile.scrna（单细胞分析）

```dockerfile
# tool_configs/terminal/docker/Dockerfile.scrna
# 构建: docker build -t omichub/sandbox-scrna:latest -f tool_configs/terminal/docker/Dockerfile.scrna tool_configs/terminal/docker/
FROM omichub/sandbox-terminal:latest

USER root

RUN apt-get update && apt-get install -y --no-install-recommends \
      python3-pip libhdf5-dev pkg-config \
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install --no-cache-dir \
      "scanpy>=1.10" "anndata>=0.10" \
      leidenalg python-igraph \
      harmonypy scrublet scvelo \
      openpyxl xlrd

# 只读根文件系统下，numba / matplotlib 缓存必须落到 tmpfs /tmp
ENV NUMBA_CACHE_DIR=/tmp \
    MPLCONFIGDIR=/tmp \
    OMP_NUM_THREADS=2

USER 1000
# CMD 继承基础镜像: ttyd -p 7681 -W ... zsh
```

### 2.3 Dockerfile.gatk（变异检测 GATK & PLINK）

```dockerfile
# tool_configs/terminal/docker/Dockerfile.gatk
# 构建: docker build -t omichub/sandbox-gatk:latest -f tool_configs/terminal/docker/Dockerfile.gatk tool_configs/terminal/docker/
FROM omichub/sandbox-terminal:latest

USER root

ARG GATK_VERSION=4.5.0.0
ARG PLINK1_BUILD=20231211
ARG PLINK2_BUILD=20240105

RUN apt-get update && apt-get install -y --no-install-recommends \
      openjdk-17-jre-headless python3-pip tabix \
    && rm -rf /var/lib/apt/lists/*

# GATK4（含 gatk wrapper 脚本，依赖 python3 与 java）
RUN wget -q "https://github.com/broadinstitute/gatk/releases/download/${GATK_VERSION}/gatk-${GATK_VERSION}.zip" -O /tmp/gatk.zip \
    && unzip -q /tmp/gatk.zip -d /opt \
    && ln -s /opt/gatk-${GATK_VERSION}/gatk /usr/local/bin/gatk \
    && rm /tmp/gatk.zip

# PLINK 1.9
RUN wget -q "https://s3.amazonaws.com/plink1-assets/plink_linux_x86_64_${PLINK1_BUILD}.zip" -O /tmp/plink1.zip \
    && unzip -q /tmp/plink1.zip -d /opt/plink1 \
    && ln -s /opt/plink1/plink /usr/local/bin/plink \
    && rm /tmp/plink1.zip

# PLINK 2
RUN wget -q "https://s3.amazonaws.com/plink2-assets/alpha5/plink2_linux_x86_64_${PLINK2_BUILD}.zip" -O /tmp/plink2.zip \
    && unzip -q /tmp/plink2.zip -d /opt/plink2 \
    && ln -s /opt/plink2/plink2 /usr/local/bin/plink2 \
    && rm /tmp/plink2.zip

ENV JAVA_OPTS="-Xmx3g"

USER 1000
```

> 注：PLINK 构建号随上游发布变化，构建失败时先到 https://www.cog-genomics.org/plink/ 查最新 build 号再改 ARG。

### 2.4 Dockerfile.ggplot2（科研绘图）

```dockerfile
# tool_configs/terminal/docker/Dockerfile.ggplot2
# 构建: docker build -t omichub/sandbox-ggplot2:latest -f tool_configs/terminal/docker/Dockerfile.ggplot2 tool_configs/terminal/docker/
FROM omichub/sandbox-terminal:latest

USER root

# r-base + apt 二进制 R 包（避免源码编译）+ 中文字体（ggplot 中文标签不乱码）
RUN apt-get update && apt-get install -y --no-install-recommends \
      r-base \
      r-cran-ggplot2 r-cran-dplyr r-cran-tidyr r-cran-readr \
      r-cran-stringr r-cran-forcats r-cran-tibble r-cran-purrr \
      r-cran-ggrepel r-cran-cowplot r-cran-rcolorbrewer r-cran-viridis \
      fonts-noto-cjk fontconfig \
    && rm -rf /var/lib/apt/lists/* \
    && fc-cache -f

# Python 侧绘图（plotnine = ggplot 语法 Python 版）
RUN pip3 install --no-cache-dir plotnine matplotlib seaborn

ENV MPLCONFIGDIR=/tmp

USER 1000
```

### 2.5 terminal_images.yaml 注册项（追加到 images 列表）

```yaml
images:
  # ... 保留现有 base 条目 ...
  - id: scrna
    name: 单细胞分析
    description: 预装 scanpy / anndata / leiden / Harmony / Scrublet / scVelo，适合 10x 数据质控、聚类与细胞注释
    image: omichub/sandbox-scrna:latest
    tags: [单细胞, scanpy]
    icon: 🧬
    resources:
      memory_mb: 4096
      cpu_cores: 2.0
      pid_limit: 200
    env:
      - { name: NUMBA_CACHE_DIR, value: /tmp }
      - { name: MPLCONFIGDIR, value: /tmp }
    enabled: true
  - id: gatk
    name: 变异检测 GATK & PLINK
    description: 预装 GATK4 / PLINK1.9 / PLINK2 / tabix，配合基础 samtools 链完成变异检测与群体遗传分析
    image: omichub/sandbox-gatk:latest
    tags: [变异检测, WGS, GWAS]
    icon: 🧪
    resources:
      memory_mb: 4096
      cpu_cores: 4.0
      pid_limit: 200
    enabled: true
  - id: ggplot2
    name: 科研绘图 ggplot2
    description: 预装 R + tidyverse(ggplot2/dplyr/tidyr) / ggrepel / cowplot / 中文字体，以及 Python plotnine
    image: omichub/sandbox-ggplot2:latest
    tags: [绘图, R, ggplot2]
    icon: 📊
    resources:
      memory_mb: 1024
      cpu_cores: 1.0
      pid_limit: 100
    env:
      - { name: MPLCONFIGDIR, value: /tmp }
    enabled: true
```

### 2.6 提示词：构建并接入三个镜像（粘给编码 Agent）

```text
你是一名资深 DevOps/后端工程师。项目为 OmicHub 多助手平台。先阅读
tool_configs/terminal/README.md 与 tool_configs/terminal/docker/Dockerfile（基础镜像），
理解镜像注册机制（terminal_images.yaml mtime 热重载、registry_prefix、非 root 1000:1000、
read_only 根文件系统、tmpfs /tmp 与 ~/.cache）后再动手。

任务：新增三个用途镜像并完成接入。完整 Dockerfile 与 yaml 条目见《OmicHub沙盒终端优化
与多用途镜像方案.md》Part 2（Dockerfile.scrna / Dockerfile.gatk / Dockerfile.ggplot2），
可直接采用并按需微调。

## 一、构建三个镜像（Dockerfile 放 tool_configs/terminal/docker/）
1. Dockerfile.scrna → omichub/sandbox-scrna:latest（scanpy 全家桶；
   必须设置 NUMBA_CACHE_DIR=/tmp、MPLCONFIGDIR=/tmp，只读根文件系统下不设置会崩）
2. Dockerfile.gatk → omichub/sandbox-gatk:latest（OpenJDK 17 + GATK4 +
   PLINK1.9/PLINK2；gatk wrapper 需 python3 可用；验证 gatk --version 与 plink2 --version）
3. Dockerfile.ggplot2 → omichub/sandbox-ggplot2:latest（r-base + apt 二进制 r-cran-*
   包，禁止源码编译 tidyverse；fonts-noto-cjk 中文字体；plotnine）

## 二、注册与资源联动
1. terminal_images.yaml 增加三个条目（id/name/description/tags/icon/resources/env/enabled），
   resources 分别 4096MB/2核、4096MB/4核、1024MB/1核；保存后确认热重载生效
   （GET /terminal/environments 返回新镜像，无需重启后端）。
2. 若 terminal_config.yaml 的 max_resources.memory_mb 为 4096，评估宿主机余量后
   调至 8192，使单细胞镜像可申请到足够内存。

## 三、逐镜像验收（必须实际跑通）
1. docker run 起容器（模拟生产参数：--user 1000:1000 --read-only --tmpfs /tmp
   --cap-drop ALL），wget --spider localhost:7681 健康检查通过。
2. 容器内验证工具可用：scanpy 导入并跑 sc.pp.filter_cells 示例；gatk --version、
   plink2 --version；Rscript -e 'library(ggplot2)' 并输出一张 png 到 /home/omichub/workspace。
3. 通过平台前端各创建一个会话，终端正常进 zsh、工具可用、workspace 挂载读写正常、
   销毁后容器 auto_remove。

## 验收标准
- [ ] 三个镜像构建成功且体积合理（记录各镜像大小）
- [ ] 前端镜像选择器出现三张新卡片，资源默认值正确联动
- [ ] 三镜像在生产安全参数下 ttyd 正常、工具可用
- [ ] 现有 base 镜像与终端功能零回归
```

---

## 实施顺序与风险

**建议顺序**：先做 Part 2（构建镜像，纯增量、热重载注册，约半天）→ 再做 Part 1（前端优化）。镜像多了之后，网格卡片选择器和资源联动才物尽其用。

| 风险 | 应对 |
|---|---|
| 新镜像构建失败 / 体积失控 | 逐镜像单独构建验收，失败的保持 `enabled: false`；PLINK 构建号失效先查上游最新 build 再改 ARG |
| 只读根文件系统下工具崩溃 | 所有缓存类环境变量（NUMBA_CACHE_DIR/MPLCONFIGDIR）指向 tmpfs /tmp；验收必须在 `--read-only` 参数下实测 |
| yaml 配置错误导致镜像列表异常 | 配置加载器会回退默认配置（仅 base 镜像），不影响现有功能；改完先 `GET /terminal/environments` 验证 |
| 前端资源联动改动波及会话创建 | store 字段契约（image_id/resources）不变；改完跑一遍完整"选镜像 → 调资源 → 启动 → 销毁"流程 |
