# CygnusX 测试报告：阶段 0 环境基线

测试日期：2026-10-20（Asia/Shanghai）  
范围：仅任务书 §4 阶段 0；未执行阶段 1–5。  
纪律：本报告只保留命令、退出码、计数、版本和 schema 元数据；不包含连接串、密钥、记忆/知识正文或用户标识。

## 1. 环境快照

| 项目 | 快照 |
|---|---|
| 编排 | `docker-compose.test.yml`，Compose 项目 `cygnusx-memory-stage0`；PG/Redis 仅在独立网络运行（文件：`docker-compose.test.yml:6-34`） |
| PostgreSQL | `pgvector/pgvector:pg15`；服务端 `15.19` |
| pgvector | `0.8.7`，满足 HNSW 要求 |
| Redis | `redis:7`；服务端 `7.4.11` |
| 测试库 | `cygnusx_memtest`（迁移/种子）、`cygnusx_accept`（只读基线）、`cygnusx_maint`（已迁移，未写入）；另用一次性命名库验证现有集成测试的命名门禁 |
| Alembic | 单 head：`memory_settle_cursor01`；`alembic history --verbose` 共 90 个 revision；任务书列出的 11 个记忆 revision 与 3 个知识库 revision 全部存在 |
| Flags | 本阶段未注入模型配置：`memory_v2_enabled=false`、`agent_memory_embedding_model=""`、`memory_focus_per_project_enabled=false`、`memory_embedding_model_filter_enabled=false`、`memory_hybrid_retrieval_enabled=false`、`memory_embedding_coverage_enabled=false`、`memory_settle_tail_enabled=false`；其余使用 `Settings` 默认值（代码：`src/cygnusx/core/config.py:264-312`） |

环境命令证据：`docker compose -p cygnusx-memory-stage0 -f docker-compose.test.yml up -d` 退出码 0；版本查询返回 PostgreSQL `15.19`、pgvector `0.8.7`、Redis `7.4.11`。Compose 的数据库初始化钩子只创建一次性 `cygnusx_accept`/`cygnusx_maint`（文件：`scripts/init_memory_test_databases.sh:4-8`）。

## 2. 测试矩阵

| 用例编号 | 层级 | 结果 | 证据（命令 + 关键输出 / 文件:行号 / DB 关键字段） |
|---|---|---|---|
| 0-A1 | 环境 | 通过 | `docker compose ... config --quiet` 退出码 0；PG/Redis 容器 healthy；Compose 定义见 `docker-compose.test.yml:7-34` |
| 0-A2 | 环境 | 通过 | PG 15.19、pgvector 0.8.7、Redis 7.4.11；版本查询无正文/密钥输出 |
| 0-B1 | 迁移 | 通过 | `DATABASE_URL=<显式测试 DSN> uv run alembic upgrade head` 退出码 0；head=`memory_settle_cursor01`；完整 history 计数 90；14 个目标 revision 均可由 `ScriptDirectory` 找到 |
| 0-B2a | DB schema | 通过 | `pg_indexes`：`idx_memory_facts_embedding_hnsw` 使用 `hnsw (embedding vector_cosine_ops)`；`uq_memory_blocks_general` 与 `uq_memory_blocks_project` 分别带 `project_id IS NULL/IS NOT NULL` |
| 0-B2b | DB schema | 通过 | `pg_indexes`：`ix_kb_chunks_embedding_hnsw` 为 HNSW cosine；`format_type` 返回 `vector(1024)` |
| 0-B2c | DB schema | 通过 | `pg_indexes`：`ix_chat_messages_session_created_message` 覆盖 `(session_id, created_at, message_id)`；`ix_memory_recall_batches_created_at` 存在 |
| 0-B3a | 迁移降级 | 通过 | `memory_focus_project01`：保护数据 downgrade 退出码 1，行数 `1→1`；清除条件后 downgrade/upgrade 退出码 `0/0` |
| 0-B3b | 迁移降级 | 通过 | `memory_consolidate01`：审计行存在时退出码 1，行数 `1→1`；无审计行往返 `0/0` |
| 0-B3c | 迁移降级 | 通过 | `memory_episode01`：正文长度超过旧上限时退出码 1，行数 `1→1`；无长正文往返 `0/0` |
| 0-B3d | 迁移降级 | 通过 | `memory_consolidate_rollback01`：已有回滚记录时退出码 1，行数 `1→1`；无回滚记录往返 `0/0` |
| 0-B4a | 漂移检查 | 通过 | `DATABASE_URL=<显式测试 DSN> uv run python scripts/check_schema_drift.py` 退出码 0，输出 schema 无漂移；`mem0_memories` 仍在豁免集合（`scripts/check_schema_drift.py:32,53-57`） |
| 0-B4b | 配置检查 | 通过 | `uv run python scripts/check_env_example_drift.py` 退出码 0；输出 `MEM0_* excluded`；保护逻辑见 `scripts/check_env_example_drift.py:71-83` |
| 0-C1-taskdsn | 集成测试 | 失败 | `MEMORY_TEST_DATABASE_URL=<cygnusx_memtest 显式 DSN> uv run pytest tests/integration/test_memory_focus_postgres.py -q` 退出码 1：测试文件 `tests/integration/test_memory_focus_postgres.py:30-32` 硬性要求库名以 `memory_acceptance_test` 开头 |
| 0-C2-taskdsn | 集成测试 | 失败 | 同一 `cygnusx_memtest` 显式 DSN 运行 `test_memory_embedding_postgres.py` 退出码 1；同一命名门禁见 `tests/integration/test_memory_embedding_postgres.py:30-34` |
| 0-C1-contract | 集成测试 | 通过 | 一次性 `memory_acceptance_test_stage0` 库（已安装 pgvector）运行 focus 测试：`1 passed`，退出码 0；覆盖 8 路并发、保护 downgrade、往返（测试主体：`tests/integration/test_memory_focus_postgres.py:64-80`） |
| 0-C2-contract | 集成测试 | 通过 | 同一命名合规库运行 vector 测试：`1 passed`，退出码 0；实际 HNSW/model filter/backfill/EXPLAIN 路径（`tests/integration/test_memory_embedding_postgres.py:55-127`） |
| 0-C3a | 集成测试 | 通过 | `PROJECT_EXPORT_TEST_DATABASE_URL=<显式一次性 project_export_test DSN> uv run pytest ...test_project_delivery_postgres.py -q`：`1 passed`，退出码 0 |
| 0-C3b | 集成测试 | 受阻 | `CYGNUSX_REPORT_TEST_DATABASE_URL=<显式一次性 report_test DSN> uv run pytest ...test_reproducible_report_postgres.py -q`：3 个测试在 fixture 初始化报 `ModuleNotFoundError: psycopg2`；未修改依赖或测试 |
| 0-C3c | 集成测试 | 受阻 | `uv run pytest tests/integration/test_phase0b_redis.py -q`：`1 skipped`，原因是 host 无 `redis-server`（`tests/integration/test_phase0b_redis.py:20-28`）；Compose 内 Redis 已通过 `PONG`，但该测试明确要求 host 二进制/Unix socket |
| 0-C3d | 集成测试 | 受阻 | `DATABASE_URL=<显式 memtest DSN> uv run pytest tests/integration/test_agent_service.py -q -rs`：`6 passed, 6 skipped`；6 项因 asyncpg 连接跨 event loop 被 fixture 按“数据库未就绪”跳过（`tests/integration/test_agent_service.py:23-31`） |
| 0-D1 | 只读工具 | 通过 | `MEMORY_ACCEPTANCE_DATABASE_URL=<显式 accept DSN> uv run python scripts/inspect_memory_baseline.py` 退出码 0；`status=collected`、`read_only=true`、PG/pgvector/head 字段齐全；事务设置见 `scripts/inspect_memory_baseline.py:44-57` |
| 0-D2 | 只读工具 | 通过 | 未设置 `MEMORY_ACCEPTANCE_DATABASE_URL`、同时设置无效 `DATABASE_URL` 时退出码 2，返回 `status=blocked`；无回退行为（`scripts/inspect_memory_baseline.py:138-149`） |
| 0-E1 | 种子脚本 | 通过 | `uv run python scripts/seed_memory_test_data.py --dsn <显式 DSN>` 退出码 0，默认 `status=dry-run`；脚本强制 `--dsn` 且仅 `--apply` 写入（`scripts/seed_memory_test_data.py:152-175`） |
| 0-E2 | 种子脚本 | 通过 | `--apply` 退出码 0，计划为 2 用户、4 Agent 标识、2 项目、6 会话、36 消息、12 blocks、10 facts；真实库聚合计数含迁移往返产生的历史行，未输出正文 |
| 0-1 | 只测不改 | 通过 | `git diff -- src frontend alembic/versions` 为空；新增仅 Compose、初始化脚本、种子脚本、阶段报告（任务书文件为开工前已存在的未跟踪文件） |

## 3. 失败与受阻清单

### 【阻断阶段目标】

- `0-C1-taskdsn`、`0-C2-taskdsn`：任务书要求用 `cygnusx_memtest` 真实执行，但现有两个集成测试在文件内拒绝该库名；因此 `cygnusx_memtest` 上的“被 skip 测试真实通过”未成立。证据为上表退出码 1 及 `tests/integration/test_memory_*_postgres.py:30-34`。

### 【阻断灰度准入】

- 无新增业务数据丢失或 schema 破坏证据；四项 downgrade 保护均在保护数据存在时拒绝且行数不变。

### 【体验不一致】

- `0-C3b`：report PostgreSQL 集成测试的 URL 未带 async 驱动，当前环境缺少 `psycopg2`，导致 3 项 fixture 初始化错误。
- `0-C3c`：Redis 容器可用，但测试契约只接受 host `redis-server` 与 Unix socket，无法使用已启动的隔离 Redis 服务。
- `0-C3d`：Agent service 集成 fixture 在部分用例中因 asyncpg event loop 绑定问题自我 skip。

### 【建议优化】

- 统一阶段 0 集成测试的专用库命名契约，或将任务书的 `cygnusx_memtest` 加入现有测试允许名单；不在本阶段修改旧测试。
- 为 report 测试提供已锁定的 async PostgreSQL 驱动并在依赖门禁中显式验证。
- 将 Redis 两进程测试改为可显式接收隔离 TCP/Unix endpoint，避免把 Compose 服务与 host 二进制能力混为一谈。

## 4. 模型调用与成本

本阶段未调用 Embedding 或抽取模型：Embedding 调用 `0` 次、抽取调用 `0` 次、模型 token `0`、成本 `0`。仅使用数据库迁移、合成数据和现有测试中的 stub/vector literal；因此没有真实模型批准预算或账单偏差。

## 5. 下一阶段准入建议

结论：**受阻**，暂不进入阶段 1。迁移链、schema、降级保护、只读工具和合成夹具已具备通过证据；但任务书要求的 `cygnusx_memtest` 集成测试因现有库名硬校验失败，且全仓相关集成测试仍有依赖/运行时受阻项。需由用户先确认测试命名契约和依赖处理，再进行阶段验收复核。

## 附录 A：补证据（2026-10-21）

本附录只追加证据，不更改原报告结论。用户已在任务书 §13 确认阶段 0 通过，原报告中的库名冲突与准入意见以该核对记录为准。

### A.1 四项降级拒绝原因

命令：`MEMORY_TEST_DATABASE_URL=<显式一次性测试 DSN> .venv/bin/python scripts/verify_memory_downgrade_guards.py`，退出码 0。数据库为 `memory_acceptance_test_stage0`；脚本在随机独立 schema 中构造最小保护数据，绑定真实 Alembic Operations 并调用原迁移 `downgrade()`，逐项确认拒绝后行数仍为 1，随后移除本脚本创建的 schema。不重复完整迁移链往返，不修改已有迁移。

| 用例 | 异常类名与关键错误行（运行输出） | 触发保护逻辑 | 行数 |
|---|---|---|---|
| 0-B3a | `RuntimeError: Project focus content must be exported/reviewed before downgrade` | `alembic/versions/memory_focus_project01_scope_focus_blocks.py:27-28`，存在非 NULL 项目块 | 1→1 |
| 0-B3b | `RuntimeError: Export/review consolidation audit history before schema downgrade` | `alembic/versions/memory_consolidate01_add_consolidation_ledger.py:34-35`，存在整理审计行 | 1→1 |
| 0-B3c | `RuntimeError: Cannot downgrade while long memory facts exist; reviewed data conversion required` | `alembic/versions/memory_episode01_expand_fact_content.py:19-20`，正文长度超过 300 | 1→1 |
| 0-B3d | `RuntimeError: Export/review consolidation rollback history before schema downgrade` | `alembic/versions/memory_consolidate_rollback01.py:20-28`，存在 rollback 类型或回滚时间 | 1→1 |

运行证据：`evidence/memory-stage1/downgrade-guards.jsonl`；可复核脚本：`scripts/verify_memory_downgrade_guards.py`。这些是本次补跑的实际异常，非从源码推断历史报错。

### A.2 contract 测试 verbose 输出

命令：`MEMORY_TEST_DATABASE_URL=<显式 memory_acceptance_test_stage0 DSN> .venv/bin/pytest tests/integration/test_memory_focus_postgres.py tests/integration/test_memory_embedding_postgres.py -v --tb=short`，退出码 0。完整输出保存在 `evidence/memory-stage1/contract-pytest.txt`，关键原文：

```text
collecting ... collected 2 items

tests/integration/test_memory_focus_postgres.py::test_focus_migration_concurrent_create_and_protected_downgrade PASSED [ 50%]
tests/integration/test_memory_embedding_postgres.py::test_pgvector_model_filter_lexical_backfill_and_explain PASSED [100%]

========================= 2 passed, 1 warning in 0.64s =========================
```

警告为现有 Pydantic class-based config 弃用提示，无 skip。

| 测试文件 | 实际断言点清单 |
|---|---|
| `tests/integration/test_memory_focus_postgres.py` | 61–62：执行 upgrade 后一般块正文保留；70：8 路并发创建（20 秒超时）；72：同项目仅一行；73–75：downgrade 抛 RuntimeError 且匹配 `exported/reviewed`；77–80：删除项目块后 downgrade 保留一般块、再次 upgrade 后项目块为零 |
| `tests/integration/test_memory_embedding_postgres.py` | 92：同模型向量搜索只返回当前模型；96：合并搜索保留旧模型词面命中；108–109：向量候选只有当前模型、词面候选只有旧模型；113：mismatch 待处理 1 行；116：回填更新 1 行且剩余 0；117：再次回填更新 0；118–127：执行 EXPLAIN 并用 record_property 记录计划 |

证据边界：embedding 文件 62 行创建 ORM 表（包含 HNSW 索引），但没有独立的 HNSW 索引存在断言；EXPLAIN 仅记录计划，没有断言使用 HNSW。该用例通过不能证明万行数据性能或 HNSW 被规划器选中，后者仍属于阶段 1-D。
