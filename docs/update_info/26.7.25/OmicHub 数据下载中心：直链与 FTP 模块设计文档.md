# OmicHub 数据下载中心：直链与 FTP 模块设计文档

## 一、 界面与交互设计 (前端 Vue 组件层)

在现有的 `公共数据库`、`云盘极速提取`、`云存储直拉` 旁边，新增第四个 Tab 按钮。

### 1.1 顶部 Tab 导航
*   **文案与图标**：`🌐 直链与 FTP` 或 `🔗 万能直链`
*   **样式**：与现有按钮保持一致的圆角胶囊样式，激活态保持当前的紫蓝色渐变。

### 1.2 核心表单区域 (卡片内)
切换到该 Tab 后，表单布局应极度精简，重点突出“输入”与“存储”：

*   **资源链接输入框 (Textarea)**：
    *   **控件类型**：支持自动换行与高度自适应的多行文本框。
    *   **Placeholder**：`支持 HTTP / HTTPS / FTP 协议的直接下载链接。支持多行批量输入，每行一个链接...`
    *   **快捷操作**：右上角可提供一个「清空」和「去重」的小按钮。
*   **存储位置选择 (Select/TreeSelect)**：
    *   **联动**：默认回显用户工作区的根目录（`/workspace` 或其他默认路径），支持下拉选择或新建子目录（如 `/workspace/reference` 或 `/workspace/raw_data`）。
*   **高级选项 (Collapse 折叠面板)**：
    *   **下载并发线程 (Slider/Select)**：默认 4 线程，可选 1、8、16。用于加速大文件（如 WGS 的 FASTQ 文件或组装好的大基因组 FASTA）下载。
    *   **同名文件策略 (Radio)**：`自动重命名 (如 file(1).gz)` / `强制覆盖` / `跳过`。
    *   **目录解析 (Switch)**：开启后，如果输入的是一个 FTP 目录地址，后端会自动抓取该目录下的所有文件并建立对应的文件夹结构。
*   **底部操作区**：
    *   **提交按钮**：`提交下载任务` 按钮（Primary 样式），点击后校验链接合法性（正则匹配是否以 http/https/ftp 开头）。

---

## 二、 生信高频使用场景匹配

作为一个生信数据平台，这个模块必须能完美吃下以下几种高频场景：

1.  **参考基因组与注释文件下载**：
    *   用户直接去 Ensembl 或 UCSC 官网复制了 Reference 的 FTP 链接。
    *   *示例*：`ftp://ftp.ensembl.org/pub/release-110/fasta/homo_sapiens/dna/Homo_sapiens.GRCh38.dna.primary_assembly.fa.gz`
    *   *痛点解决*：几十 GB 的参考基因组，用浏览器下载容易断，丢到这个模块后台多线程拉取，稳如泰山。
2.  **公共测序数据的绕道下载**：
    *   当 NCBI/EBI 的 API 波动，或者用 `公共数据库` Tab 拉取 SRA/ERR 失败时，用户可以直接去 ENA 搜索该样本，复制生成的 `ftp://ftp.sra.ebi.ac.uk/...` 直链到这里作为保底。
3.  **第三方工具数据库更新**：
    *   例如下载 Kraken2、Rfam 等宏基因组或非编码 RNA 的离线数据库压缩包（`.tar.gz`），直接粘贴 HTTP 链接进工作区解压。

---

## 三、 后端服务与下载器实现方案

考虑到平台是基于 Docker 等容器化微服务架构部署的，后台下载任务绝不能阻塞主线程，必须采用**异步任务队列 + 高性能下载引擎**的架构。

### 3.1 核心下载引擎选型：`aria2c`
极度不建议使用原生的 `wget` 或 Python 自带的 `requests`，对于几十 GB 的生信文件，它们的单线程速度太慢且不稳定。
*   **方案**：在后端容器（如基于 FastAPI 的后端镜像）中预装 `aria2c`。
*   **调用命令示例**：
    ```bash
    aria2c -x 16 -s 16 -c -d /path/to/workspace -o output_file.fastq.gz "[https://example.com/data.fastq.gz](https://example.com/data.fastq.gz)"
    ```
    *   `-x 16`：单任务最大连接数（16线程加速）。
    *   `-s 16`：下载分割数。
    *   `-c`：开启断点续传（关键！应对网络波动）。
    *   `-d`：指定工作区存储目录。

### 3.2 任务调度与异步架构
1.  **任务提交**：前端将链接列表、目标目录发给后端 API。
2.  **消息队列**：后端解析链接，如果是 10 个链接，则拆分成 10 个独立的下载子任务，推送到任务队列（如 Redis + Celery，或轻量级的 Background Tasks）。
3.  **状态轮询 (SSE / WebSocket / 定时 Ajax)**：
    *   在界面下方的「下载任务」列表中，实时反馈每个直链的下载状态。
    *   后端通过解析 `aria2c` 的 RPC 接口或读取日志，将 `下载进度 (%)`、`当前速度 (MB/s)`、`状态 (Downloading/Completed/Failed)` 实时推送到前端表格。

### 3.3 FTP 目录批量抓取 (进阶实现)
如果用户开启了「目录解析」，后端的处理逻辑：
1.  使用 Python 的 `ftplib` 或 `wget --spider` 先探测该 URL 是文件还是目录。
2.  若是目录，递归获取目录下的所有文件路径。
3.  在用户的目标 `/workspace` 中使用 `os.makedirs` 创建对应的树状目录结构。
4.  把探测到的所有底层文件 URL 转成单独的 `aria2c` 下载任务并执行。

---

## 四、 异常兜底机制

*   **超时与重试**：设置 `aria2c` 的重试次数（如 `--max-tries=5`）。如果国外节点（如 EBI、UCSC）连接彻底超时，任务状态变更为“失败”，前端列表提供「重新尝试」按钮。
*   **磁盘空间预检**：如果是 HTTP 链接，后端先发送 `HEAD` 请求获取 `Content-Length`，预先判断用户工作区剩余配额是否足够，不足则在提交时直接弹窗拦截，避免下载到 99% 时由于磁盘写满而报错。

## 五、当前实现落地约定

本方案复用现有数据下载任务聚合，不新增下载任务表：

- `DownloadRequest.source` 新增 `direct_link`，`links` 接收批量 HTTP / HTTPS / FTP 地址；服务端校验协议、主机和 URL 凭据，拒绝本机/内网 IP。
- 三类下载器的开关、二进制路径、aria2c 参数和链接上限统一维护在 `tool_configs/download/download_config.yaml`，由 `src/omichub/tools/download/config.py` 按 mtime 热重载。
- `DownloadService` 继续创建 `flow_id=ebi_download` 的通用任务，任务产物统一落到用户 `raw_data` 目录并登记为文件资产。
- Celery `run_download` 根据 `source` 分发到直链执行器；执行器调用 `aria2c`，启用断点续传、5 次重试、超时、完整性检查和 1/4/8/16 并发连接。
- 同名策略映射为 `auto_rename`、`overwrite`、`skip`；以 `/` 结尾的匿名 FTP 地址在启用目录解析时递归展开为文件清单，随后交由 `aria2c` 执行并统一归档到本次任务目录。
- 功能开关为 `enable_direct_download`，二进制路径为 `direct_download_binary`，默认关闭；部署环境需安装 `aria2c` 并显式开启开关后才对用户开放。
- 前端第四个 Tab 为「直链与 FTP」，支持多行粘贴、清空、去重、工作区目录、并发、同名策略和 FTP 目录解析；任务状态继续使用现有下载列表与任务详情页。

### 5.1 API 示例

```json
{
  "source": "direct_link",
  "links": [
    "https://example.org/reference.fa.gz",
    "ftp://ftp.example.org/pub/annotation.gff3.gz"
  ],
  "download_threads": 4,
  "overwrite_policy": "auto_rename",
  "recursive": false,
  "target_directory": "reference"
}
```

提交接口仍为 `POST /api/v1/downloads`；列表、任务详情和进度接口保持不变。生产验收必须同时检查 aria2c 可执行、用户工作区配额、任务状态回写和失败重试入口。
