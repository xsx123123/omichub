# OmicHub Pipelines MCP

## 目标

`omichub-pipelines` 将 OmicHub 已有 RNA-seq 与 ATAC-seq 分析中心接入 MCP。它不实现新的分析流程，而是复用：

- `flows/rna_seq.yaml` 与 `flows/atac_seq.yaml` 流程定义；
- `FlowSubmissionValidator` 参数和样本表校验；
- `ToolConfirmationService` 预检确认记录；
- `TaskService` 任务提交、权限检查和状态查询；
- RNAFlow、ATACFlow 现有 Snakemake 执行链路。

原有分析中心表单和 `/api/v1/tasks` 提交方式保持不变。

## 架构

```text
AI 助手 / 外部 MCP Client
          │
          ├─ 平台内置 MCP: omichub-pipelines
          │      └─ PipelineController
          │
          └─ 独立 FastMCP: pipelines_main.py
                 └─ /api/v1/pipelines/*
                        └─ PipelineController
                               ├─ RNASeqPipeline
                               ├─ ATACSeqPipeline
                               ├─ AnalysisFlowToolService
                               ├─ TaskService
                               └─ PipelineResultService
```

`RNASeqPipeline` 和 `ATACSeqPipeline` 只负责将 MCP 的稳定公开参数映射到现有 Flow YAML 参数。所有提交仍经过同一套确认记录和任务调度系统。

## MCP 工具

| 工具 | 用途 |
| --- | --- |
| `rna_seq_prepare` | 校验 RNA-seq 参数、工作区权限、FASTQ 完整性、样本匹配并预估资源 |
| `rna_seq_submit` | 使用 `prepared_params` 提交已预检任务 |
| `rna_seq_status` | 查询 RNA-seq 任务状态和进度 |
| `rna_seq_results` | 获取差异基因摘要、报告地址和产物清单 |
| `atac_seq_prepare` | 校验 ATAC-seq 参数与数据完整性 |
| `atac_seq_submit` | 提交已预检的 ATAC-seq 任务 |
| `atac_seq_status` | 查询 ATAC-seq 任务状态和进度 |
| `atac_seq_results` | 获取 ATAC-seq 结果摘要和产物清单 |
| `list_available_pipelines` | 列出可用完整分析流程、必填参数和预计耗时 |
| `check_workspace_data` | 独立检查工作区 FASTQ 数量、配对情况和总大小 |

## Prepare 输入

RNA-seq 和 ATAC-seq 的 `prepare` 工具使用相同公开字段：

```json
{
  "raw_data_path": "inbox/project-a",
  "species": "Homo sapiens",
  "genome_version": "hg38",
  "sample_sheet": [
    {"sample": "C1", "sample_name": "Control 1", "group": "control"},
    {"sample": "T1", "sample_name": "Treat 1", "group": "treat"}
  ],
  "comparisons": [
    {"name": "Treat_vs_Control", "Control": "control", "Treat": "treat"}
  ],
  "library_type": "fr-unstranded",
  "project_name": "Project A",
  "extra_parameters": {"only_qc": false, "report": true}
}
```

成功后返回的 `prepared_params` 包含短期有效的 `confirmation_id`。`submit` 只接受该对象，不接受重新拼装的任务参数，从而避免预检后参数被篡改。

## 安全规则

- 数据路径必须位于当前用户的 OmicHub 用户根目录内；拒绝 `..` 路径穿越和跨用户绝对路径。
- API Key 在全局认证中验证，并映射到所属用户；外部 MCP Server 不传递数据库会话等内部上下文。
- 状态和结果查询均通过 `TaskService` 校验任务归属，越权时按任务不存在处理。
- 结果读取只遍历任务目录内的普通文件，跳过符号链接并限制产物数量和表格大小。
- 最终结果仅允许在任务成功后读取。

## 启动独立 MCP Server

```bash
cd mcp-server
export OMICSHUB_BASE_URL="https://your-omichub.example"
export OMICSHUB_API_KEY="your-api-key"
python pipelines_main.py
```

SSE 模式：

```bash
python pipelines_main.py --transport sse --port 8901
```

统一 MCP Server 的 `pipelines` 工具组默认也已启用，可继续使用 `python main.py`。

## 示例对话

### RNA-seq

> 用户：检查 `inbox/brain-rna` 的数据，然后提交人类 hg38 RNA-seq 差异表达分析。

AI 助手依次调用：

1. `check_workspace_data(analysis_type="rna_seq", data_path="inbox/brain-rna")`
2. `rna_seq_prepare(...)`
3. 向用户展示样本数、比较组和资源预估并请求确认
4. `rna_seq_submit(prepared_params=...)`
5. 周期调用 `rna_seq_status(task_id=...)`
6. 完成后调用 `rna_seq_results(task_id=..., result_types=["summary", "artifacts"])`

消息气泡会嵌入 `PipelineTaskCard`，显示进度、差异基因数量、上下调数量以及结果操作。

### 参数修正

> AI 助手：样本 `T2` 未匹配到 FASTQ 文件。请确认文件名是否以 `T2` 开头，或者修改样本表中的 `sample` 字段。

校验错误以结构化 `field/code/message` 返回，模型可据此引导用户修正，而不会创建任务。
