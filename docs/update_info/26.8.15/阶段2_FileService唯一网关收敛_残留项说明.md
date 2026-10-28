# 阶段 2「FileService 唯一网关收敛」残留项说明

> 依据：`docs/26.8.15/OmicHub工作区文件全局可见性优化实施计划.md` 阶段 2 验收要求：
> “清点清单中的直接 Path 操作全部收敛（残留项需逐条书面说明理由）”。

## 1. 阶段 2 收敛范围界定

本次收敛聚焦**用户工作区文件**的实体读写，即落入以下目录树的文件：

- `users/{uid}/inbox/`、`users/{uid}/workspace/`、`users/{uid}/projects/.../output/`
- `users/{uid}/tasks/`、`users/{uid}/downloads/`
- Studio 工作区：`studio/{session_id}/input|output|...`
- Overdrive 运行目录：`studio/{session_id}/output/overdrive/{run_id}/...`

对不落在上述范围、或属于系统/管理/本地容器挂载机制的直接文件操作，作为**残留项**记录。

## 2. 已收敛模块（回归测试覆盖）

| 模块 | 收敛内容 |
|------|----------|
| `file_service.py` | 目录创建、文件搜索、移动、预览、文本读取全部改走 `StorageBackend`；`_normalize_directory` 对 `..` 显式拒绝 |
| `directory_service.py` | 子目录创建改走 `backend.ensure_dir` |
| `upload_service.py` | 分片清理改走 `backend.delete_tree` |
| `pipeline_result_service.py` | 产物遍历、预览路径解析改走 `backend.stat/read/is_symlink`；新增 `preview_workspace_file` |
| `agentteams_data_tool_service.py` | `workspace_file_preview`、本地 `artifact_fetch` 改走 `PipelineResultService` 统一接口 |
| `report_service.py` | 报告 HTML 预览/下载改走 `StorageBackend`；`create_report_from_task` 扫描改走 `backend.exists/stat/read` |
| `studio_context_service.py` | 聊天上传文件解析、报告产物校验、`import_datahub_file`、`register_artifact_report` 复制改走 `StorageBackend` |
| `studio/workspace.py`、`studio_sharing.py` | 工作区文件列表、读取、产物扫描改走 `StorageBackend` |
| `file_registry.py` | 注册时用 `backend.stat/list` 取代 `Path.glob/rglob` |
| `chat_sandbox_tools.py` | 产物目录创建与存在性校验改走 `StorageBackend` |
| `overdrive_execution_service.py` | `OverdrivePreflightService.run`、`DeliveryAssembler.write/write_readme` 改走 `StorageBackend` |
| `overdrive_run_service.py` | `save_research`、计划快照校验、README 生成、事件投影、`manifest.json`/`control.json` 快照改走 `StorageBackend` |
| `celery_app/tasks/overdrive.py` | worker 结果写入、Manager 证据账本、产物路径校验改走 `StorageBackend` |
| `storage/backend.py`、`s3_backend.py` | 新增 `copy`、`delete_tree`、`is_symlink` 抽象方法 |

全量回归套件当前结果：**244 passed, 1 warning**。

## 3. 残留项逐条说明

| # | 位置 | 仍存在的直接文件操作 | 保留理由 | 建议后续处理 |
|---|------|----------------------|----------|--------------|
| 3.1 | `application/services/overdrive_runtime.py` | `OverdriveManifest` 全部方法（`load/initialize/update_task/set_status/write_artifacts/append_progress/progress_tail/read_summary/control/write_control/consume_directive`）以及 `_atomic_write`/`atomic_write_json`/`read_json` 使用 `Path.write_text/read_text/open` | 这是一个**同步运行时状态机**，被 `chat_service.py` 中约 45 处同步调用点密集使用。若改为异步并接入 `StorageBackend`，需要：① 把 `OverdriveManifest` 所有方法改为 `async`；② 在 `chat_service.py` 所有调用点注入 `await`；③ 处理 `manifest.load().get(...)` 等链式表达式的括号优先级；④ 重写 `tests/unit/test_overdrive_runtime.py`。改动面跨越大且极易引入运行时 `TypeError`，超出阶段 2 的收敛范围。 | 建议在阶段 4（云端部署适配）或独立 PR 中处理：可引入一个**同步的 `StorageBackend` 本地适配层**供 `OverdriveManifest` 专用，或一次性把 `chat_service.py` 的 Overdrive 控制循环改为异步并全量回归。 |
| 3.2 | `application/services/storage_service.py` | `shutil.disk_usage`、`du -s` 子进程、`os.walk`/`os.path.getsize` | 这是**全局磁盘容量/按用户用量统计**后台服务，不读写用户文件内容；`du` 依赖本地文件系统的 statvfs/GNU coreutils，对象存储没有等价语义。 | 在 `storage.type=s3` 或 `deployment_mode=cloud` 时，该服务需要完全重写为基于对象存储桶容量 API / CloudWatch 指标的实现；本地模式保留现有实现。 |
| 3.3 | `application/services/studio_context_service.py` | `report_file_mount_rel`、`_resolve_storage_file` 使用 `Path.resolve()/relative_to()` 做纯字符串校验；`link_platform_file`/`list_input_links` 使用 `os.symlink`/`os.readlink`/`os.listdir` | 前两者**不触碰文件内容**，仅做路径容器校验；后两者属于 Studio 沙盒的**本地 bind-mount 软链机制**，是容器内外共享数据的 P1 设计（数据不搬家），对象存储形态下需由阶段 4 的“临时 POSIX scratch 卷”替代。 | 阶段 4 统一替换为 cloud 模式下的物化/回传模型；local 模式保留软链机制。 |
| 3.4 | `application/services/report_service.py` | `_resolve_report_path` 使用 `Path.resolve()` 校验报告路径 | 仅用于**路径字符串校验**，不读取文件；后续可改为纯字符串归一化以减少一次 `stat`。 | 低优先级：改为基于 `PathFactory.is_within_root` 的字符串校验即可。 |
| 3.5 | `infrastructure/storage/path_factory.py` | `create_project_run_dir`、`remove_user_root`、`ensure_task_dirs` 使用 `mkdir`/`shutil.rmtree` | 路径工厂本身负责**目录结构创建**，属于 StorageBackend 本地实现的一部分；`remove_user_root` 是管理员删除用户数据入口。 | `create_project_run_dir`/`ensure_task_dirs` 可被 `LocalStorageBackend.ensure_dir` 替代；`remove_user_root` 建议作为后台管理命令而非运行时文件操作。阶段 4 评估是否统一纳入 `StorageBackend.delete_tree`。 |
| 3.6 | `application/services/docs_service.py` `knowledge_audit_service.py` | 管理 `docs/` 知识库文档 | 属于**平台知识库文档管理**，不是用户工作区文件，阶段 0 已明确 out of scope。 | 不在本次计划内。 |
| 3.7 | `api/v1/docs.py`、`api/v1/admin/session_logs.py`、`api/v1/terminal.py` |  respectively 知识库上传、日志归档、Docker 环境检查 | 均为**系统/管理类操作**，不落在用户工作区文件范围。 | 不在本次计划内。 |
| 3.8 | AgentTeams 证据（MinIO） | `infrastructure/storage/minio_store.py` 直接操作 MinIO 对象 | 阶段 0/3 明确：AgentTeams 证据去留依赖 MinIO 决策，暂只在 `file_records.source` 预留 `AGENTTEAMS` 枚举值。 | 阶段 3 决策后统一归档到 `file_records`。 |

## 4. 结论

阶段 2 已将**用户工作区文件**的主要读写路径收敛到 `StorageBackend`，直接文件操作从 `file_service`、`upload_service`、`pipeline_result_service`、`studio_context_service`、`overdrive_execution_service`、`overdrive_run_service`、`celery_app/tasks/overdrive.py` 等核心模块中移除。

剩余残留项要么**不读写用户文件内容**（统计、路径校验、知识库管理），要么属于**本地容器挂载机制/同步运行时状态机**（`OverdriveManifest`、Studio 软链），需要在阶段 3/4 结合权限模型和云端部署形态统一处理。
