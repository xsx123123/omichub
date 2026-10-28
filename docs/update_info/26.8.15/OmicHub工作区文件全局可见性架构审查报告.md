# OmicHub 工作区文件全局可见性架构审查报告

> 审查依据：`docs/26.8.15/OmicHub工作区文件全局可见性架构审查提示词.md`  
> 审查性质：只读代码调研，未修改任何代码。  
> 审查日期：2026-08-14

---

## 1. 总体结论

**方向判断：方向正确，但当前实现是“局部统一、整体未闭环”。**

- 平台已经建立了以 `file_records` 表为核心的文件索引、以 `StoragePathFactory` 为核心的本地路径工厂、以及 `FileRegistry` 注册入口，**个人空间内文件的权限隔离做得较好**。
- 但“四个模块统一可见”尚未真正落地：**AI 工作台（Studio/沙盒）产出、聊天轻量沙盒产出、AgentTeams 协作产物、分析流程产物** 都没有完整回流到统一的 `file_records` 索引，导致 AI 助手通过 `list_workspace_files` 等工具看不到这些文件。
- **云/本地双部署路径尚未就绪**：目前只有 `storage_type = "local"` 一条路，代码里大量使用 `Path.read_text`/`write_bytes`，没有可插拔的存储后端抽象层。

---

## 2. 「模块 × 能力」矩阵

| 模块 | 列目录 | 读文件 | 写文件 | 删除 | 权限校验点 | 寻址方式 | 备注 / 代码位置 |
|---|---|---|---|---|---|---|---|
| **1. AI 助手 / 星尘 AI（含 MCP 文件工具）** | 已实现：通过 `/files/workspace` → `FileService.list_workspace_files` | 已实现：通过 `/files/preview` 读前 N 行；MCP 工具 `omichub_read_file_content` | **缺失**：无直接写接口 | 未暴露 | 已存在：`FileRepositoryImpl` 强制 `user_id`；`workspace_file_refs.py` 校验上下文用户一致性 | `file_id`（UUID）/`upload://hex`/`directory://dir_id` | `file_service.py:343`；`api/v1/files.py:258`；`mcp-server/tools/files.py:11,123` |
| **2. AI 工作台 / Studio 沙盒** | 已实现：走 sandbox-agent `/files/list` 或宿主机 `disk_list_files` 回退 | 已实现：`workspace_read` / `disk_read_file`，默认 200 行 | 已实现：`workspace_write`、`workspace_edit`、`sandbox_execute` 写 `/workspace/output` | 已实现：`workspace_delete` | 已存在：`api/v1/studio.py` `_get_studio_session` 校验归属；沙盒只读挂载当前用户目录 | 沙盒相对路径 `/workspace/input/<symlink>`、`/workspace/output/...` | `studio/manager.py:697`；`studio/workspace.py:44,64`；`studio_tools.py:526,569` |
| **3. 团队协作 / AgentTeams** | 部分实现：case 证据在 MinIO，`task_result_summary` 可列任务产物 | 部分实现：`task_file_preview`、`workspace_file_preview` 读本地文件；MinIO 对象通过 `artifact_fetch` 拉取 | 部分实现：仅向 case 证据桶上传/下载 | 未暴露 | 已存在：`AgentTeamsDataToolService._require_context_user` 校验上下文用户；`artifact_fetch` 校验 bucket/case_id 前缀 | `s3://agentteams-evidence/{case_id}/...` 或本地 workspace 相对路径 | `agentteams_data_tool_service.py:22`；`minio_store.py:29` |
| **4. 生信工具箱 / 分析流程** | 部分实现：`PipelineResultService.get_task_summary` 列出任务目录产物；`/files` 仅能看到上传文件 | 部分实现：`PipelineResultService.preview_task_file` 读任务内文件；火山图/KEGG 等工具通过 `tool_bridge_service` 解析 `file://`/`upload://` | 已实现：流程输出到 `projects/.../output`，但**未注册到 `file_records`** | 未暴露 | 已存在：`TaskService.get_task` 带 user_id；`FileService` 文件归属校验 | 任务目录相对路径、`file_id`、`upload://` | `task_service.py:308`；`pipeline_result_service.py:21`；`tool_bridge_service.py:125` |
| **5. 报告中心** | 已实现：`ReportService.list_reports` | 已实现：`preview_html`、`download_file` | 已实现：`create_report_from_task` 写 `ReportFileModel.path` | 已实现：`delete_report` | 已存在：`report_repository` 按 `user_id`；`_resolve_report_path` 防路径穿越 | 报告 ID + 报告文件 ID | `report_service.py:29,183` |

---

## 3. 模块间文件流转链路图（文字版）

```
[用户上传]
   │
   ▼
users/{uid}/inbox/{filename} ──► file_records (file_id)
   │
   ├──► AI 助手 MCP /files/*、list_workspace_files
   ├──► Studio datahub_import ──► /workspace/input/<symlink>（只读）
   ├──► 分析流程 sample_sheet (file_id) ──► users/{uid}/projects/{proj}/runs/{ts}/input
   └──► AgentTeams workspace_file_preview（users/{uid}/workspace）

[分析流程 / Snakemake]
   │
   ▼
users/{uid}/projects/{proj}/runs/{ts}/output
   │
   ├──► ReportService ──► reports + report_files（绝对路径）
   ├──► PipelineResultService.get_task_summary / preview_task_file
   └──► platform_result_import 可软链回 Studio

[Studio 沙盒]
   │
   ▼
{storage_path}/studio/{session_id}/output
   │
   └──► artifact_register ──► 复制到 users/{uid}/projects/{proj}/runs/studio-{ts}/output
        └──► 生成 reports + report_files
   └──► 聊天中通过 platform_result_import 可再引入

[聊天轻量沙盒]
   │
   ▼
{storage_path}/chat_sandbox/{uid}/{session}/output
   │
   └──► 仅作为消息附件下载，不入 file_records，其他模块不可见

[AgentTeams 协作]
   │
   ▼
s3://agentteams-evidence/{case_id}/{work_item}/...
   │
   └──► artifact_fetch ──► 本地 /data/omichub/output/agentteams/{case_id}/downloads
   └──► 与 file_records 完全隔离
```

**关键断裂点：**
- Studio 产出 → `file_records`：**断裂**。`register_artifact_report` 只写 `report_files`，没调 `FileRegistry`。
- 分析流程产出 → `file_records`：**断裂**。`ReportService.create_report_from_task` 只写 `report_files`；仅 EBI/下载任务会写 `file_records`。
- 聊天轻量沙盒产出 → 工作区：**断裂**。产物落在 `chat_sandbox/` 且未注册。
- AgentTeams MinIO 证据 → 统一文件索引：**断裂**。

---

## 4. 风险与缺口清单（按严重度）

### 4.1 阻断云端迁移 / 阻断 SaaS 多租户扩展

| # | 风险 | 代码证据 |
|---|---|---|
| 1 | **无统一存储后端抽象**：所有文件操作都基于本地 `Path`，没有 `StorageBackend` 接口。切换到对象存储需要改写大量服务。 | `omichub/core/config.py:87` `storage_type: str = "local"`；`omichub/infrastructure/storage/path_factory.py:30` `StoragePathFactory` 直接返回 `Path`；`file_service.py:250` `_resolve_abs` 使用 `Path.resolve()` |
| 2 | **仅 AgentTeams 使用 MinIO**，且仅用于 case 证据，不是工作区统一存储。 | `omichub/infrastructure/storage/minio_store.py:29`；`agentteams_data_tool_service.py:34` 初始化 `MinioStore` |
| 3 | **沙盒挂载假设本地盘**：Studio 通过 Docker bind-mount `{storage_path}/users/{uid}` 到 `/data/platform`。云端对象存储无法直接 bind-mount。 | `omichub/infrastructure/studio/manager.py:393-399` `volumes = {str(workspace): {"bind": "/workspace"} ... }` |
| 4 | **配置没有 cloud/local 统一开关**：`storage_type` 字段存在但代码里没看到非 local 分支；`data/OmicHub.yaml` 只配了 `data_root`。 | `omichub/core/config.py:87`；`data/OmicHub.yaml:29-33` |

### 4.2 权限安全隐患

| # | 风险 | 代码证据 |
|---|---|---|
| 5 | **聊天沙盒产物目录按 `user_id` 隔离**，但未注册到 `file_records`，依赖下载端点手工校验；如果未来其他模块直接读取该路径，容易漏校验。 | `chat_sandbox_tools.py:132` `host_dest = Path(get_settings().storage_path) / "chat_sandbox" / user_id / ...` |
| 6 | **Studio 工作区路径独立于用户根目录**（`{storage_path}/studio/{session_id}`），虽然会话归属校验存在，但工作区文件与 `file_records` 不同源，跨会话/跨用户复用容器时依赖 bind-mount 正确性。 | `studio/loader.py:124,150` `workspace_root = {storage_path}/studio` |
| 7 | **BLAST 等旧工具配置直接写原始路径**，未见到统一权限校验；如果实现中直接拼接路径，可能绕过 `FileService` 的边界检查。 | `tool_configs/blast/blast_config.yaml:5-7` |

### 4.3 体验不一致 / 功能缺口

| # | 风险 | 代码证据 |
|---|---|---|
| 8 | **AI 助手无法“看见”工作区产出**：`list_workspace_files` 只读 `file_records`，但 Studio/流程/聊天沙盒产物多数不在其中。 | `file_service.py:343` `list_workspace_files` 查询 `FileRecordModel` |
| 9 | **报告中心与文件中心两张表**：`report_files.path` 存绝对路径，`file_records.storage_path` 存相对路径；统一检索需要分别查。 | `report_service.py:249-258`；`infrastructure/database/models/file.py:45` |
| 10 | **大文件预览策略不一致**：AI 助手 `/files/preview` 对 >400KB 返回空行；MCP `file://` 文本替换上限 5MB；Studio read 2000 行。二进制大文件（BAM/FASTQ）元数据可读但内容不会被误读，策略基本正确，但缺少“统一元数据 + 预览”接口。 | `api/v1/files.py:278-284`；`workspace_file_refs.py:26`；`studio/manager.py:710` |

---

## 5. 双部署路径就绪度

| 维度 | 本地私有化 | 云端 SaaS |
|---|---|---|
| **存储后端** | ✅ 已就绪，`storage_path` + `StoragePathFactory` 即可运行 | ❌ 未就绪，全部基于本地 `Path` |
| **多租户隔离** | ✅ 用户目录隔离 + DB `user_id` 强制过滤 | ⚠️ 目录隔离可行，但缺少对象存储租户隔离 |
| **沙盒挂载** | ✅ Docker bind-mount 本地目录 | ❌ 需要 s3fs/CSI 或预签名 URL 方案 |
| **配置化切换** | ⚠️ 只有一个 `storage_type="local"`，没有 local 分支也成立 | ❌ 无 cloud 分支 |
| **MinIO 兜底** | ✅ AgentTeams 已接入 MinIO，可作为本地对象存储参考 | ⚠️ 未扩展到工作区文件 |

---

## 6. 演进建议

建议采用 **“先抽象统一层，再分模块补齐”** 的策略，理由：当前直接连存储的模块数量较多（Studio、聊天沙盒、分析流程、AgentTeams、BLAST 配置），如果先分模块补齐，会导致每条链路都要重复实现对象存储适配；先抽象层可以把变化收敛到一个接口。

### 建议的落地顺序

1. **定义 `StorageBackend` 抽象**
   - 接口至少包含：`read(path, offset, limit)`、`write(path, content)`、`list(dir)`、`delete(path)`、`register(user_id, path, source, task_id)`。
   - 实现 `LocalStorageBackend`（复用 `StoragePathFactory`）和 `S3CompatibleStorageBackend`（基于 MinIO SDK）。
   - 配置 `storage_type` 决定注入哪个实现。

2. **让 `FileService` 成为唯一文件网关**
   - 所有读/写/列目录操作都走 `FileService` 方法，而不是直接 `Path.read_text`。
   - 沙盒内通过 agent 调用平台 API，或挂载统一存储，避免绕过 `FileService`。

3. **统一注册所有产出**
   - Studio `artifact_register`、分析流程成功完成、聊天沙盒执行结束、AgentTeams 本地产物，都调用 `FileRegistry.register()` 写 `file_records`。
   - `report_files` 与 `file_records` 对齐：报告文件也生成对应的 `file_records` 行（source=`REPORT`），或统一搜索时合并两表。

4. **补齐沙盒回写闭环**
   - Studio 沙盒执行结束后自动扫描 `/workspace/output`，将新增文件注册到 `file_records`。
   - 聊天轻量沙盒产物从 `chat_sandbox/` 移到用户可见目录并注册，或至少提供 `file_id` 供 AI 助手引用。

5. **团队协作空间边界**
   - 决定 case 证据是继续走 MinIO 还是纳入统一存储层；若保留 MinIO，则在统一文件列表 API 中聚合“个人文件 + 共享 case 文件”，并统一做权限校验。

6. **双部署配置化**
   - 在 `data/OmicHub.yaml` / `core.config.py` 中明确定义 `storage.type = local|s3`、endpoint、bucket、region 等。
   - 本地私有化默认 `local`；云端切换为 `s3` 时，沙盒挂载使用 s3fs/MinIO CSI，或改为下载到本地 scratch 后上传。

---

## 7. 一句话总结

OmicHub 已经具备“工作区统一可见”的骨架（`file_records` + `StoragePathFactory` + 用户级权限隔离），但四个模块的实际文件产出还没有全部回流到这张表中，也缺少云端对象存储的抽象层。优先做统一存储抽象和全产出注册，是实现“四模块统一可见”和“云/本地双部署”的最短路径。
