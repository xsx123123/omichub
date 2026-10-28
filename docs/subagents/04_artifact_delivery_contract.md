# 子 Agent 产物交付契约（WP2 交付）

> 日期：2026-10-28｜实现：`parallel_subagent_service._collect_and_publish_artifacts`
> 复用：`artifact_manifest.build_manifest`（size/sha256 实测）、StorageBackend、FileRegistry（source=CHAT_SANDBOX）

## 1. 四阶段闭环

| 阶段 | 机制 | 证据 |
|---|---|---|
| Produced | 子任务结束后扫描 `{storage}/subagents/{run_id}/{index}/`（排除 `result.json` 审计文件与符号链接） | manifest entries（path/size/sha256，读取失败标 error 不抛出） |
| Verified | `build_manifest` 逐文件流式 sha256 | `sha256` 字段非空即 verified；`unverified` 保留可见不可交付 |
| Registered | 已发布产物登记 `file_records`（directory=`workspace/chat-output/{parent_session}/output/subagents/{run_id}/{task_label}`，checksum=sha256）；登记失败仅日志 | file_records 行 |
| Published | 复制到父工作区 `users/{uid}/workspace/chat-output/{parent_session_id}/output/subagents/{run_id}/{task_label}/`，随后**父以自己的存储后端回读字节并重算 sha256** | `parent_reopen_check=passed` 才算交付成功 |

判 FAIL 保护：父空间回读 hash 不一致 → `lifecycle=publish_failed / parent_reopen_check=failed`，manifest 如实记录，**不冒充交付**。

## 2. 安全与幂等

- 路径安全：`task_label` 仅保留 `[a-zA-Z0-9\-_:]`（80 字符），阻断 `../` 与特殊字符逃逸；扫描排除符号链接（防链接逃逸）。
- R26 重名/重试：目标已存在**不覆盖**，回读对账后照常标记；同 hash 重复发布天然幂等。命名空间为 `run_id`，跨 run 物理隔离。
- 产物文件数上限 50/子任务，超出保留在子 workdir 并在 manifest 记 `files_truncated=true`。
- 跨项目越权：发布目标固定在父会话自己的 chat-output 之下，归属校验沿用下载端点的用户 id 机制；登记/发布失败均不阻断已完成子任务。

## 3. 透出字段

- `ui_payload.artifacts[]`：`{index, agent_id, task_id, path, size, sha256, published_ref}`
- `llm_payload.results[].artifacts[]`：含 `lifecycle / published_ref / parent_reopen_check / error`
- run 级 `manifest.json` 落盘 `workdir_root/manifest.json`（schema_version=1，按任务分组）
- 契约任务 `artifact_status` 用实测结果刷新：`published_count>0 → published`；仅 verified → `verified`；无产物 → 保持 `not_created`
- summary 附加「产物 N 件已发布到父工作区 subagents/{run_id}/」

## 4. 已知限制（诚实列缺）

- 进程内单 worker 语义；S3 后端下父回读经 `backend.read` 全字节读入内存（大文件需改流式，WP4 前限制单文件 ≤ 发布上限约束）。
- PNG 可解码性、业务断言（R23 深度校验）目前以「sha256 + 类型由前端/下载端确认」为准，未引入图像解码器。
- 取消/超时后已验证产物的保留策略=保留（部分失败任务产物不清理），父任务状态由 outcome 汇总体现。
