# 阶段 2.1 直接文件操作清点清单

> 生成方式：AST 扫描 `src/**/*.py`，收集 `Path` 方法、`os.*`、`shutil.*` 中属于文件读写的调用。
> 清单按文件分组，保留行号，供阶段 2 收敛时逐项确认。

## 说明

- **无需改动（已收敛或属于基础设施）**：
  - `src/omichub/infrastructure/storage/backend.py`：`StorageBackend` / `LocalStorageBackend` 实现本身。
  - `src/omichub/infrastructure/storage/path_factory.py`：路径工厂，负责本地目录创建，属于后端内部。
  - `src/omichub/infrastructure/storage/minio_store.py`：MinIO SDK 封装。
  - `src/omichub/infrastructure/storage/file_registry.py`：文件注册扫描（已在使用相对路径）。
  - 各类静态配置加载器读取的是代码/配置元数据，不属于用户工作区文件，可保留或单独评估。
- **需要收敛到 FileService / StorageBackend 的核心模块**：
  - API 层：`api/v1/files.py`、`api/v1/chat.py`、`api/v1/docs.py`、`api/v1/studio.py` 等
  - 应用服务层：`upload_service.py`、`download_service.py`、`report_service.py`、`pipeline_controller.py`、`pipeline_result_service.py`、`task_service.py`、`tool_bridge_service.py`、`docs_service.py`、`storage_service.py`、`studio_context_service.py` 等
  - 工具链：`tools/blast/*`、`tools/deg/*`、`tools/jbrowse/*`、`tools/phylogenetic_tree/*` 等
  - 执行层：`infrastructure/execution/*`、`infrastructure/celery_app/tasks/*`、`infrastructure/sandbox/*`、`infrastructure/studio/*`

## 按文件详细清单

src/omichub/api/v1/admin/session_logs.py
  L 140 .exists()
  L 167 .exists()
  L 172 .glob()
  L 173 .is_file()
  L 175 .stat()
  L 189 .open()
  L 191 .read_text()

src/omichub/api/v1/chat.py
  L  65 .is_file()
  L 125 .exists()
  L 128 .read_text()
  L 163 .is_file()

src/omichub/api/v1/docs.py
  L 299 .mkdir()
  L 303 .write_bytes()

src/omichub/api/v1/files.py
  L 274 .is_file()
  L 278 .stat()
  L 282 .stat()
  L 284 .stat()
  L 297 .stat()
  L 478 .is_file()

src/omichub/api/v1/studio.py
  L 189 .exists()
  L 833 .is_file()
  L1049 .exists()
  L1107 .is_file()

src/omichub/application/services/agent_consultation_service.py
  L 316 .read_text()
  L 422 .exists()
  L 432 .is_file()
  L 432 .rglob()
  L 438 .mkdir()
  L 439 shutil.copy2()
  L 441 .open()
  L 451 .stat()

src/omichub/application/services/agent_service.py
  L 350 .is_file()

src/omichub/application/services/agentteams_data_tool_service.py
  L  68 .read_bytes()
  L  69 .stat()
  L  94 .mkdir()
  L 122 .stat()
  L 126 .read_bytes()
  L 126 .write_bytes()
  L 128 .stat()
  L 130 .unlink()
  L 133 .open()

src/omichub/application/services/agentteams_evidence_gc_service.py
  L  48 .is_dir()
  L  50 .iterdir()
  L  53 .is_dir()
  L  54 shutil.rmtree()
  L  56 .unlink()

src/omichub/application/services/agentteams_stale_task_service.py
  L  77 .is_file()

src/omichub/application/services/ai_provider_service.py
  L  90 .exists()
  L  93 .exists()

src/omichub/application/services/ai_provider_yaml_loader.py
  L  34 .exists()

src/omichub/application/services/ai_provider_yaml_writer.py
  L  48 .exists()
  L  49 .read_text()
  L  65 .write_text()
  L  78 .mkdir()

src/omichub/application/services/ai_tools.py
  L  91 .exists()
  L  94 .is_file()
  L  95 .stat()

src/omichub/application/services/artifact_service.py
  L  24 .is_dir()
  L  27 .is_file()
  L  29 .stat()
  L  40 .open()

src/omichub/application/services/chat_sandbox_tools.py
  L 143 .mkdir()
  L 168 .is_file()

src/omichub/application/services/chat_service.py
  L2139 .is_dir()
  L2146 .iterdir()
  L2147 .is_file()
  L2149 .stat()
  L4315 .exists()
  L4315 .read_text()
  L7924 .is_file()

src/omichub/application/services/directory_service.py
  L  80 .mkdir()
  L  92 .mkdir()

src/omichub/application/services/docs_service.py
  L 394 .exists()
  L 395 .unlink()
  L 607 .mkdir()
  L 609 .write_text()
  L 619 .exists()
  L 622 .open()
  L 651 .open()
  L 658 .exists()
  L 661 .open()
  L 671 .open()
  L 692 .exists()
  L 761 .exists()
  L 763 .open()
  L 780 .exists()
  L 782 .read_text()
  L 795 .exists()
  L 798 .open()

src/omichub/application/services/download_service.py
  L 173 .mkdir()

src/omichub/application/services/file_service.py
  L 290 .mkdir()
  L 300 .mkdir()
  L 442 .exists()
  L 442 .is_dir()
  L 444 .exists()
  L 444 .stat()
  L 535 .exists()
  L 544 .exists()
  L 562 .exists()
  L 570 .exists()
  L 574 shutil.move()
  L 605 .mkdir()
  L 683 .exists()

src/omichub/application/services/flow_registry.py
  L 178 .exists()
  L 180 .glob()
  L 204 .read_text()
  L 231 .read_text()
  L 239 .read_text()

src/omichub/application/services/knowledge_asset_service.py
  L  49 .is_file()
  L 114 .iterdir()
  L 115 .is_file()
  L 149 .is_file()
  L 212 .open()

src/omichub/application/services/knowledge_audit_service.py
  L  95 .mkdir()
  L  97 .write_text()
  L 107 .exists()
  L 110 .open()
  L 140 .open()

src/omichub/application/services/managed_file_resolver.py
  L 108 .glob()
  L 122 .stat()
  L 138 .stat()

src/omichub/application/services/mas_service.py
  L 194 .is_file()

src/omichub/application/services/overdrive_execution_service.py
  L 251 .mkdir()
  L 285 .exists()
  L 303 .mkdir()
  L 304 .write_text()
  L 541 .mkdir()
  L 543 .write_text()
  L 596 .mkdir()
  L 597 .write_text()

src/omichub/application/services/overdrive_run_service.py
  L1146 .exists()
  L1148 .read_text()
  L1256 .mkdir()
  L1265 .open()
  L1270 .mkdir()
  L1272 .write_text()
  L1273 os.replace()

src/omichub/application/services/overdrive_runtime.py
  L  53 .exists()
  L  54 .read_text()
  L  82 .mkdir()
  L  84 .write_text()
  L  85 os.replace()
  L  93 .exists()
  L  96 .read_text()
  L 265 .mkdir()
  L 266 .open()
  L 271 .exists()
  L 273 .read_text()
  L 277 .exists()
  L 277 .read_text()

src/omichub/application/services/parallel_subagent_service.py
  L 491 .mkdir()

src/omichub/application/services/pipeline_controller.py
  L 152 .exists()
  L 152 .is_dir()
  L 163 .rglob()
  L 164 .is_file()
  L 174 .stat()
  L 209 .rglob()
  L 210 .is_file()

src/omichub/application/services/pipeline_result_service.py
  L  66 .read_bytes()
  L  67 .stat()
  L 130 .exists()
  L 138 .is_file()
  L 138 .rglob()
  L 142 .is_file()
  L 156 .stat()
  L 164 .is_file()
  L 164 .rglob()
  L 167 .is_file()
  L 167 .stat()
  L 185 .is_file()
  L 185 .rglob()
  L 188 .is_file()
  L 190 .stat()
  L 198 .read_text()
  L 242 .open()
  L 288 .is_file()
  L 297 .open()

src/omichub/application/services/project_service.py
  L 130 .mkdir()
  L 131 .mkdir()
  L 171 .exists()
  L 180 .iterdir()
  L 181 .is_dir()

src/omichub/application/services/report_service.py
  L 139 .exists()
  L 143 .read_text()
  L 158 .exists()
  L 216 .exists()
  L 218 .read_text()
  L 232 .exists()
  L 252 .exists()
  L 258 .stat()

src/omichub/application/services/site_content_service.py
  L  86 .exists()
  L  89 .open()

src/omichub/application/services/skill_import_service.py
  L  80 .is_dir()
  L 190 .is_dir()
  L 191 .iterdir()
  L 193 .is_dir()
  L 193 .is_file()
  L 223 .is_file()
  L 252 .mkdir()
  L 291 .iterdir()
  L 292 .is_dir()
  L 293 shutil.rmtree()
  L 296 .mkdir()
  L 302 .mkdir()
  L 303 .write_bytes()
  L 338 .mkdir()
  L 431 .is_file()
  L 559 .is_dir()
  L 564 .glob()
  L 564 .is_dir()
  L 782 .rglob()
  L 783 .is_file()
  L 786 .stat()
  L 790 .read_bytes()
  L 893 .open()
  L 924 .read_text()
  L 933 .write_text()
  L 944 .open()

src/omichub/application/services/storage_service.py
  L 108 .exists()
  L 113 .is_dir()
  L 113 .iterdir()

src/omichub/application/services/studio_context_service.py
  L  70 .glob()
  L  83 .is_file()
  L  85 .stat()
  L 116 .is_file()
  L 326 .is_file()
  L 437 .is_file()
  L 465 .exists()
  L 499 .stat()
  L 526 .unlink()

src/omichub/application/services/studio_sharing.py
  L  88 .exists()
  L 142 .is_file()

src/omichub/application/services/studio_skill_service.py
  L  42 .is_file()
  L  45 .stat()
  L  47 .read_text()

src/omichub/application/services/task_service.py
  L 301 .write_text()
  L 319 .mkdir()
  L 321 .mkdir()

src/omichub/application/services/tool_bridge_service.py
  L 159 .glob()

src/omichub/application/services/upload_service.py
  L  78 .mkdir()
  L 156 .mkdir()
  L 158 .write_bytes()
  L 191 .exists()
  L 195 .open()
  L 198 .exists()
  L 200 .read_bytes()
  L 205 .stat()
  L 225 shutil.rmtree()
  L 228 .exists()
  L 229 shutil.rmtree()
  L 245 shutil.rmtree()
  L 247 .exists()
  L 248 shutil.rmtree()

src/omichub/application/services/welcome_service.py
  L 135 .exists()
  L 138 .open()
  L 149 .mkdir()
  L 150 .open()
  L 155 .exists()
  L 158 .open()
  L 169 .mkdir()
  L 170 .open()

src/omichub/application/services/workspace_references.py
  L  88 .is_dir()
  L 155 .is_dir()
  L 163 .is_file()
  L 165 .stat()

src/omichub/core/logging.py
  L  57 .mkdir()
  L  59 .write_text()
  L  60 .unlink()

src/omichub/core/retention.py
  L  42 .glob()
  L  43 .is_file()
  L  46 .stat()
  L  50 .unlink()

src/omichub/core/span_store.py
  L 121 .exists()
  L 121 .stat()
  L 127 .exists()
  L 149 .open()
  L 187 .open()
  L 189 .read_text()
  L 197 .exists()
  L 201 .glob()
  L 201 .is_file()
  L 203 .stat()

src/omichub/domain/flow/services.py
  L  39 .exists()

src/omichub/domain/mas/tool_policy.py
  L  87 .read_text()

src/omichub/domain/mas/workspace.py
  L  39 .mkdir()

src/omichub/infrastructure/celery_app/logging.py
  L  34 .mkdir()

src/omichub/infrastructure/celery_app/tasks/analysis.py
  L  34 .is_dir()

src/omichub/infrastructure/celery_app/tasks/download.py
  L  43 .glob()
  L  63 .glob()
  L 485 os.makedirs()
  L 662 os.makedirs()
  L 799 .is_file()
  L 799 .rglob()
  L 813 .stat()

src/omichub/infrastructure/celery_app/tasks/mas.py
  L 113 .mkdir()
  L 117 .write_bytes()
  L 239 .mkdir()
  L 274 .write_text()
  L 299 .is_file()
  L 330 .write_text()
  L 334 .read_text()
  L 334 .write_text()
  L 437 .read_bytes()
  L 553 .mkdir()
  L 565 .write_text()
  L 569 .write_text()
  L 697 .mkdir()
  L 703 .read_text()
  L 712 .write_text()
  L 713 .write_text()
  L 715 .write_text()
  L 864 .mkdir()
  L 883 .exists()
  L 884 .write_text()
  L 886 .open()
  L 955 .open()
  L 996 .mkdir()
  L1001 .write_bytes()
  L1006 .is_file()
  L1006 .is_file()
  L1009 .exists()
  L1009 .read_text()
  L1009 .write_text()

src/omichub/infrastructure/celery_app/tasks/overdrive.py
  L 472 .mkdir()
  L 479 .write_text()
  L 620 .is_file()
  L1051 .mkdir()
  L1054 .write_text()
  L1076 .exists()
  L1082 .stat()
  L1151 .exists()
  L1246 .exists()
  L1317 .is_file()

src/omichub/infrastructure/celery_app/tasks/storage.py
  L  45 .exists()
  L  99 shutil.rmtree()
  L 129 .mkdir()
  L 131 .exists()
  L 132 shutil.move()
  L 149 .rglob()
  L 150 .is_file()
  L 152 .stat()
  L 160 .unlink()

src/omichub/infrastructure/config/agent_ability_catalog.py
  L  31 .stat()
  L  39 .read_text()

src/omichub/infrastructure/config/agent_loader.py
  L  53 .exists()
  L  56 .open()
  L  74 .exists()
  L  79 .open()
  L 176 .read_text()
  L 188 .read_text()
  L 215 .read_text()

src/omichub/infrastructure/config/domain_pack_loader.py
  L  49 .exists()
  L  52 .glob()
  L  52 .glob()
  L  54 .stat()
  L  61 .exists()
  L  63 .glob()
  L  63 .glob()
  L  65 .read_text()

src/omichub/infrastructure/config/module_registry.py
  L 133 .exists()
  L 136 .open()

src/omichub/infrastructure/config/prompt_loader.py
  L  39 .stat()
  L  47 .read_text()
  L  84 .stat()
  L  91 .read_text()
  L 103 .read_text()

src/omichub/infrastructure/config/runtime_image_loader.py
  L 150 .stat()
  L 156 .read_text()

src/omichub/infrastructure/config/storage_config.py
  L  57 .exists()
  L  60 .open()
  L 120 .mkdir()

src/omichub/infrastructure/config/studio_loader.py
  L 171 .exists()
  L 174 .open()
  L 186 .exists()
  L 191 .stat()

src/omichub/infrastructure/database/repositories/flow_repository.py
  L  66 .exists()
  L  70 .glob()
  L  70 .stat()
  L  76 .glob()
  L  76 .stat()
  L  92 .exists()
  L  97 .glob()
  L  97 .glob()

src/omichub/infrastructure/download/progress_crypto.py
  L  39 .exists()
  L  41 .read_text()

src/omichub/infrastructure/execution/generic_builder.py
  L  51 .mkdir()
  L  90 .open()
  L 200 .open()

src/omichub/infrastructure/execution/local.py
  L  47 .mkdir()
  L  49 .write_bytes()
  L  50 .write_bytes()
  L 159 .exists()
  L 164 .exists()

src/omichub/infrastructure/mas/agent_capabilities.py
  L  15 .read_text()

src/omichub/infrastructure/mas/apptainer.py
  L  32 .is_dir()
  L  34 .is_dir()

src/omichub/infrastructure/mas/artifact_schemas.py
  L  17 .read_text()

src/omichub/infrastructure/mas/ebi.py
  L  59 .rglob()
  L  60 .is_file()
  L  65 .stat()
  L  72 .write_text()
  L  78 .open()

src/omichub/infrastructure/mas/qc_metrics.py
  L  16 .rglob()
  L  25 .open()

src/omichub/infrastructure/mas/rnaflow.py
  L  21 .read_text()

src/omichub/infrastructure/mas/volcano.py
  L  58 .mkdir()
  L  86 .is_file()
  L  89 .open()

src/omichub/infrastructure/mcp/presets.py
  L  73 .read_text()
  L 382 .is_dir()
  L 427 .is_file()
  L 557 .glob()
  L 565 .stat()
  L 734 .is_dir()
  L 735 .iterdir()
  L 736 .is_file()
  L 739 .stat()
  L 757 .is_file()
  L 757 .iterdir()
  L 758 .stat()
  L 765 .stat()
  L 820 .is_file()
  L 853 .is_file()
  L 867 .stat()

src/omichub/infrastructure/mcp/workspace_file_refs.py
  L  87 .stat()

src/omichub/infrastructure/memory/mem0_engine.py
  L  70 .mkdir()
  L  72 .exists()
  L  73 .read_bytes()
  L  76 .write_text()
  L  77 .chmod()
  L 275 os.makedirs()

src/omichub/infrastructure/sandbox/pool.py
  L 266 .mkdir()
  L 268 .open()
  L 277 .is_dir()
  L 280 .iterdir()
  L 282 .exists()
  L 283 .is_dir()
  L 284 shutil.rmtree()
  L 286 .unlink()
  L 290 .rglob()
  L 291 .is_file()
  L 293 .stat()

src/omichub/infrastructure/skills/skill_store.py
  L  34 .exists()
  L  35 shutil.rmtree()
  L  36 .mkdir()
  L  39 .write_text()
  L  48 .mkdir()
  L  50 .write_text()
  L  64 .is_dir()
  L  66 .write_text()
  L  77 .is_file()
  L  82 .read_text()
  L  87 .read_text()
  L 116 .is_file()
  L 118 .stat()
  L 121 .read_bytes()
  L 132 .is_dir()
  L 136 .rglob()
  L 137 .is_file()
  L 146 .is_dir()
  L 147 shutil.rmtree()

src/omichub/infrastructure/storage/backend.py
  L 119 .is_file()
  L 125 .open()
  L 136 .mkdir()
  L 137 .write_bytes()
  L 141 .is_file()
  L 155 .is_file()
  L 156 .stat()
  L 158 .is_dir()
  L 159 .stat()
  L 167 .is_dir()
  L 174 .iterdir()
  L 174 .rglob()
  L 178 .is_dir()
  L 185 .stat()
  L 188 .is_file()
  L 189 .stat()
  L 203 .is_file()

src/omichub/infrastructure/storage/file_registry.py
  L  90 .exists()
  L  90 .stat()
  L 133 .is_dir()
  L 142 .glob()
  L 143 .is_file()
  L 146 .is_file()

src/omichub/infrastructure/storage/minio_store.py
  L 110 .mkdir()

src/omichub/infrastructure/storage/path_factory.py
  L  58 .exists()
  L  60 shutil.rmtree()
  L 117 .mkdir()
  L 119 .mkdir()
  L 194 .mkdir()
  L 201 .mkdir()

src/omichub/infrastructure/studio/manager.py
  L 151 .mkdir()
  L 160 .chmod()
  L 391 .unlink()
  L 398 .is_dir()
  L 597 .unlink()
  L 620 .exists()
  L 624 shutil.rmtree()
  L 625 .exists()

src/omichub/infrastructure/studio/workspace.py
  L  35 .stat()
  L  38 .is_dir()
  L  54 .exists()
  L  56 .is_dir()
  L  58 .iterdir()
  L  75 .is_file()
  L  78 .read_text()
  L  95 .is_dir()
  L  97 .rglob()
  L  98 .is_file()
  L 101 .stat()
  L 160 .mkdir()
  L 164 .iterdir()
  L 207 .is_dir()

src/omichub/infrastructure/yaml/festival_config_loader.py
  L 200 .exists()
  L 212 .exists()
  L 212 .stat()
  L 250 .stat()

src/omichub/infrastructure/yaml/workflow_monitor_template_loader.py
  L  38 .exists()
  L  42 .glob()
  L  57 .stat()
  L  77 .exists()

src/omichub/main.py
  L 431 .is_dir()

src/omichub/reference_genomes/config.py
  L 128 .exists()
  L 131 .open()
  L 140 .exists()
  L 145 .stat()

src/omichub/reference_genomes/indexer.py
  L 194 .exists()
  L 201 .exists()
  L 201 .stat()
  L 201 .stat()
  L 205 .open()
  L 212 .exists()
  L 212 .stat()
  L 212 .stat()
  L 246 .exists()
  L 372 .exists()
  L 438 .exists()
  L 490 .exists()
  L 576 .exists()
  L 674 .exists()
  L 716 .exists()
  L 750 .exists()
  L 792 .exists()
  L 799 .exists()
  L1023 .exists()
  L1024 .unlink()
  L1025 .exists()
  L1026 .unlink()
  L1044 os.replace()
  L1049 .exists()
  L1089 .exists()
  L1115 .exists()
  L1116 .stat()

src/omichub/reference_genomes/sequence.py
  L 124 .exists()

src/omichub/reference_genomes/service.py
  L  90 .exists()
  L 153 .exists()
  L 153 .exists()
  L 155 .stat()
  L 161 .exists()
  L 163 .stat()
  L 165 .exists()
  L 167 .stat()
  L 221 .stat()
  L 244 .exists()
  L 297 .exists()
  L 356 .exists()
  L 607 .exists()
  L 607 .exists()
  L 635 .exists()
  L 635 .exists()
  L 851 .exists()
  L1007 .exists()
  L1007 .exists()
  L1101 .exists()
  L1101 .exists()

src/omichub/tools/blast/config.py
  L  98 .exists()
  L 101 .open()
  L 110 .exists()
  L 110 .stat()

src/omichub/tools/blast/core.py
  L 295 .exists()
  L 458 .mkdir()
  L 465 .write_text()
  L 522 .exists()
  L 544 .mkdir()
  L 591 .glob()
  L 592 .unlink()
  L 602 .exists()
  L 603 .glob()
  L 604 .unlink()
  L 607 .glob()
  L 613 .stat()
  L 626 .open()

src/omichub/tools/blast/service.py
  L  98 .exists()
  L 104 .exists()
  L 109 .exists()
  L 114 .exists()
  L 170 .mkdir()
  L 184 .open()
  L 193 shutil.rmtree()
  L 199 .open()
  L 202 shutil.rmtree()
  L 205 shutil.rmtree()
  L 312 .open()
  L 382 .exists()
  L 383 shutil.rmtree()
  L 554 .mkdir()
  L 556 .write_text()
  L 818 .write_text()
  L 827 .exists()
  L 888 .exists()
  L 889 .unlink()
  L 952 .is_file()
  L 953 .stat()
  L 997 .is_file()
  L 999 .read_text()
  L1004 .open()
  L1008 .unlink()
  L1016 .open()
  L1019 .is_file()
  L1021 .open()
  L1023 .stat()
  L1034 .exists()

src/omichub/tools/blast/tasks.py
  L 124 .exists()
  L 124 .stat()

src/omichub/tools/blast/yaml_sync.py
  L  62 .exists()
  L  65 .open()
  L  77 .mkdir()
  L  95 .open()

src/omichub/tools/deg/config.py
  L 110 .exists()
  L 113 .open()
  L 122 .exists()
  L 127 .stat()

src/omichub/tools/deg/service.py
  L  82 .exists()
  L 354 .is_file()
  L 509 .mkdir()
  L 510 .write_bytes()
  L 511 .write_bytes()
  L 512 .write_bytes()

src/omichub/tools/deg/tasks.py
  L  75 .mkdir()
  L  80 .exists()
  L  80 .exists()
  L  80 .exists()
  L 111 .exists()
  L 132 .exists()
  L 133 .read_text()
  L 146 .exists()
  L 147 .open()
  L 170 .exists()
  L 171 .open()
  L 192 .exists()
  L 199 .is_file()
  L 199 .iterdir()
  L 200 .exists()
  L 217 .exists()

src/omichub/tools/download/config.py
  L  74 .exists()
  L  77 .stat()
  L  82 .open()

src/omichub/tools/enrichments/config.py
  L 104 .exists()
  L 107 .open()
  L 116 .exists()
  L 121 .stat()

src/omichub/tools/enrichments/service.py
  L 168 .exists()
  L 168 .exists()
  L 415 .open()
  L 431 .exists()
  L 434 .open()

src/omichub/tools/enrichments/tasks.py
  L  68 .exists()
  L  71 .mkdir()
  L  72 .exists()

src/omichub/tools/fastq_qc/config.py
  L 151 .exists()
  L 154 .open()
  L 162 .exists()
  L 165 .stat()

src/omichub/tools/jbrowse/api.py
  L 175 .stat()

src/omichub/tools/jbrowse/config.py
  L 145 .exists()
  L 148 .open()
  L 157 .exists()
  L 162 .stat()
  L 204 .mkdir()

src/omichub/tools/jbrowse/service.py
  L 343 .exists()
  L 356 .stat()
  L 388 .exists()
  L 409 .exists()
  L 495 .exists()
  L 502 .exists()
  L 502 .exists()

src/omichub/tools/jbrowse/tasks.py
  L  70 .exists()
  L  88 .exists()
  L 126 .exists()
  L 135 .stat()

src/omichub/tools/phylogenetic_tree/config.py
  L 207 .exists()
  L 209 .open()
  L 218 .exists()
  L 218 .stat()
  L 222 .exists()
  L 222 .stat()

src/omichub/tools/phylogenetic_tree/core.py
  L  94 .mkdir()
  L  96 .mkdir()

src/omichub/tools/phylogenetic_tree/runner.py
  L  73 .exists()
  L 161 .open()
  L 216 .open()
  L 245 .exists()
  L 267 .write_text()
  L 282 .exists()
  L 297 .exists()
  L 469 .write_text()

src/omichub/tools/phylogenetic_tree/service.py
  L  76 .mkdir()
  L  81 .open()
  L 101 .write_text()
  L 120 .exists()
  L 122 .read_text()
  L 164 .mkdir()
  L 299 .exists()

src/omichub/tools/registry/config.py
  L  71 .exists()
  L  74 .open()
  L  83 .exists()
  L  88 .stat()

src/omichub/tools/schema_loader.py
  L 103 .exists()
  L 106 .open()
  L 136 .exists()
  L 142 .stat()

src/omichub/tools/terminal/config.py
  L 196 .exists()
  L 199 .open()
  L 207 .exists()
  L 210 .open()
  L 219 .exists()
  L 224 .stat()
  L 242 .exists()
  L 248 .stat()

