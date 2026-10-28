# CygnusX 记忆接线修复与验收进展

> **2026-10-22 后续状态**：以下为密钥注入前的准备快照。用户提供的环境变量已安全导入并进入重建后的 Web/Worker/Beat；Provider 同步、1024 维真实写召、11 条备份回填和合成 settle 已完成。最终结论、调用台账与观测缺口见 [真实验收报告 v3](../26.10.22/CygnusX记忆接通真实验收报告-v3.md)。

范围：新附件及《CygnusX记忆模块复审与优化建议-2026-10-21_new.md》Part 11，衔接 Part 10 全套验收。当前完成诊断、接线准备、同步阻断代码修复及专项验证；尚缺用户提供的 SiliconFlow key，未重建容器，尚未完成真实接通验收。

## 1. 诊断结论

- Web/Worker/Beat 通过 `env_file: ../../.env` 读取根目录配置，原本就覆盖任意新键；不是固定键清单漏传。三个容器 Created 时间均为 2026-10-18，根目录 `.env` 修改时间为 2026-10-21。容器虽在后续重新启动，Created 时间未更新，进程环境仍缺记忆配置。mtime 是整份文件时间，不能单独证明每个键的修改时点。
- Web/Worker 的 `/app/data` 是宿主 `data/` 的只读 bind mount，Provider YAML 无需重新构建镜像即可读取。Beat 不负责 Provider 同步。
- Worker 实际注册表只有旧的三项记忆任务，缺 `cygnusx.infrastructure.celery_app.tasks.memory.collect_embedding_coverage`。日志反复报 `Received unregistered task` / `KeyError`；源码已包含并注册该任务，但运行中的 Worker 导入状态未刷新，须 force-recreate 后验证。
- **新增定位：Provider 启动同步曾执行但失败**。Web 日志显示 `IntegrityError / UniqueViolationError`，约束名 `uq_ai_provider_configs_default`。数据库现有默认标记在已停用条目上，仓储的批量 ORM flush 可能先启用新默认、后取消旧默认，导致整个同步事务回滚，新向量 Provider 随之未落库。此结论修正此前“同步未执行”的推测。

所有诊断只保留键是否存在、容器时间、代码路径、异常类、约束名和任务名，不保存日志正文、SQL 参数或真实用户内容。逐项证据见 `evidence/memory-go-live-v3/step1-diagnosis.json`。

## 2. 逐文件改动

| 文件 | 改动与原因 |
| --- | --- |
| `deploy/docker/docker-compose.yml` | 仅 Web、Beat 显式列出模型、Provider UUID、维度、key、维护 DSN 五个键；保持空模型/空 Provider/1024 维默认语义。须按现有范式用 `--env-file .env` 插值 |
| `deploy/docker/docker-compose.worker.yml` | 仅 Worker 同样列出五个键，由现有 `worker-compose.sh` 导出根目录环境；其他服务保持原状 |
| 根目录 `.env`（不提交） | 模型修为 YAML 完整 ID `Qwen/Qwen3-Embedding-8B`；原名称形式 Provider ID 暂清空，待同步后填写 UUID；维度 1024；按已核实的 `POSTGRES_*` 参数显式构造目标为 `omichub` 的维护 DSN，无 `DATABASE_URL` 回退。key 仍为空，等待用户提供 |
| `ai_provider_repository.py` | 默认切换改为同一事务内先清除旧默认，再设置目标默认，避免即时部分唯一索引冲突；不改 YAML 指定的默认目标或 active 语义 |
| `test_ai_provider_default_switch.py` | 使用真实 SQLite 唯一索引验证修前失败、修后成功及重复切换；只适配异步调用边界 |
| `scripts/backfill_memory_embeddings.py` | 添加 `--confirm-database` 目标库名二次确认，apply 缺确认或库名不符时，在创建连接和 Provider 前拒绝；满足原实施文档 Part 7 允许的“白名单/二次确认”保护要求 |
| `test_memory_embedding_cli.py` | 覆盖错误/缺失目标确认在连接前被拒、默认 dry-run 与显式 DSN 保持、输出不泄漏凭据 |
| 活动数据库架构与 embedding 运行手册 | 回写默认切换事务约束与新增 apply 参数 |

原 `.env` 已保存在 evidence 外的 0700 临时目录中，备份文件和当前 `.env` 权限均为 0600；位置仅记录于 `step2-wiring.json`。未修改现有 Provider YAML 条目、召回参数、生产阈值或 Phase 2/2.5/5 功能。

## 3. 验证结果与边界

- Compose 修前/修后渲染对比通过：仅允许的三个服务五个环境键发生变化；与根目录配置逐项核对通过。key 尚空，Provider UUID 尚待同步。
- `make validate-image-mapping` 通过：17 镜像、19 Agent；`load_agent_configs()` 实际加载 19 个 Agent。
- Provider/YAML 专项初跑 22 passed、3 个既有 quarantine 用例排除；加默认切换回归后 23 passed、3 排除。隔离项为现有 writer 的键命名/占位符断言、loader prune 断言，已翻查，未修改。
- CLI/embedding/default/provider 组合最终 40 passed。新增代码专项 Ruff、两源文件 mypy、迁移链单 head 和 `git diff --check` 通过。不是全仓门禁全绿，未提交。
- 在现有隔离 Stage 0 PostgreSQL 的 `cygnusx_maint` 中创建临时 schema，使用 HEAD 旧仓储代码复现 `IntegrityError`，新代码成功且重复执行保持唯一默认、旧 active 状态不变；schema 已删除并查询确认不存在。证据：`provider-default-postgres.json`。未在业务库应用这些测试写入。
- 测试退出仍有既有 OTel 向已关闭流写日志提示；pytest exit=0。单元测试的模型调用均为测试替身，不计作 Part 10 的真实验收，也没有用它们替代真实 Provider 结果。

## 4. 当前前置与后续步骤

目前缺少非空 `SILICONFLOW_API_KEY`，已向用户请求安全写入根目录 `.env`。为避免把空凭据同步入 Provider，尚未执行任何重建/运行库同步，UUID 尚未回填。`step3-effective-settings.json` 明确记录为 `not_executed_pending_credential`，不宣称进程配置已生效。

用户 key 就绪后按实际两个 Compose 栈执行，不把独立 Worker 当作主栈服务：

```bash
# 第一次重建；只影响三个指定服务，不触发依赖服务重建或镜像构建。
docker compose --project-name cygnusx --env-file .env \
  -f deploy/docker/docker-compose.yml \
  -f deploy/docker/docker-compose.pgvector.yml \
  -f deploy/agentteams/docker-compose.cygnusx-proxy.yml \
  up -d --no-deps --no-build --pull never --force-recreate web beat
scripts/worker-compose.sh --project-name cygnusx \
  up -d --no-deps --no-build --pull never --force-recreate worker
```

重建前检查 Worker 活跃任务数量，等待已有任务完成；记录当前默认 Provider 元数据，重建后核对同步结果。确认向量 Provider active、非 default 后取真实 UUID 写回 `.env`，再重复上述 force-recreate。随后验证三个进程有效 Settings、Worker 注册表及一次真实 coverage 任务、启动日志，再更新 `step3-effective-settings.json` 与 `preflight.json`。

Part 10 维度两次探测、真实保存/跨 Agent 召回/KB 成对写入、备份与 dry-run 展示后 10 条回填、50 次召回与阈值建议、合成 settle 成功/故障/补偿/清理、运行指标及最终报告 v3 **全部尚未执行**。原始维度探测脚本没有全局调用预算封装，执行前还需将其真实请求计入同一台账，保留既有累计值。不得把本轮专项测试计作这些步骤通过。

当前累计真实调用：embedding 0/150，抽取 0/20；未执行业务库回填或修改生产阈值。详见 `call-ledger.json`。完整目标仍未完成。
