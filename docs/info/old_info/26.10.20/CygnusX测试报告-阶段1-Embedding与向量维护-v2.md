# CygnusX 测试报告：阶段 1 Embedding Provider 与向量维护 v2

日期：2026-10-21，Asia/Shanghai。总结果：**受阻**。本版依用户最新口径完成全部零调用项目，真实调用项目因指定配置文件在当前工作区不存在而受阻；未沿用 v1 的整体停止规则。未修改业务代码、既有测试和迁移。

## 1. 环境快照

| 项目 | 本次证据 |
|---|---|
| 数据库 | 显式 `MEMORY_MAINTENANCE_DATABASE_URL`，仅一次性 `cygnusx_maint`，独立 schema `stage1_a85f08ffca4c`；无 `DATABASE_URL` 回退 |
| PG / pgvector | PostgreSQL `15.19`、pgvector `0.8.7`，实际查询 `environment.json` |
| Alembic head | 实际查询 public.alembic_version：`memory_settle_cursor01` |
| Redis | `docker exec cygnusx-memory-stage0-redis-1 redis-server --version`，退出码 0，`7.4.11` |
| 配置文件 | A.1 前检查 `/home/zj/zj_code_libarary/OmicHub/.env.test`，`file_exists=false`；`A1-preflight.json`。用户所述配置与当前文件系统不一致，未搜索其他密钥来源 |
| 数据 | 本地固定随机种子生成 10,000 条独立 1024 维向量，当前/旧模型各 5,000 行，另有少量功能夹具；无真实用户数据 |

本次测试隔离 Settings 使用 `_env_file=None`，模型标签为 `synthetic-current`，仅用于零调用数据匹配，不能当作真实模型名称。Flags：`memory_v2_enabled=true`，`memory_embedding_coverage_enabled=true`，interval=300；模型过滤按 D.1/D.2 从 false 切 true；hybrid 按 D.3 从 false 切 true、min_similarity=0.9、vector_limit=20、keyword_limit=20、rrf_k=60。其余 memory Flags 完整快照在 `evidence/memory-stage1-v2/environment.json`，测试未更改任何持久部署配置或站点开关。

## 2. 测试矩阵

以下证据目录统一为 `evidence/memory-stage1-v2/`。命令均在仓库根目录执行，DSN 由环境变量注入，不在日志中展开。

| 用例编号 | 层级 | 结果 | 命令、关键输出与断言位置 |
|---|---|---|---|
| A.1 | 服务 | 受阻 | A.1 前单次配置准入检查：`A1-preflight.json` 为 file_exists=false、real_calls=0；未调用 Provider，未验证 10 条真实向量/成功指标 |
| A.2-dimension | 服务/DB | 通过 | `MEMORY_MAINTENANCE_DATABASE_URL=<显式 DSN> .venv/bin/python scripts/verify_memory_stage1_zero.py`，最终退出码 0；真实 `_embed` 收到 mock 单维返回，`dimension_mismatch=1`；FactStore 落库 embedding/model 均 NULL。`A2.json`；脚本 87–107 |
| A.2-empty | 服务/DB | 通过 | 同命令、同证据，empty=1；事实行两字段 NULL，未崩溃 |
| A.2-non_finite | 服务/DB | 通过 | 同命令、同证据，1024 维 NaN 返回，non_finite=1；事实行两字段 NULL，未崩溃 |
| A.2-provider_error | 服务/DB | 通过 | mock 抛 ConnectionError，provider_error=1；事实行两字段 NULL。遵守用户指定的 mock 故障注入口径，未向真实错误端点发请求 |
| B.1 | CLI/DB | 通过 | 运行现有 CLI `run(... apply=False)`，未传 apply，相当于默认 dry-run；`MEMORY_MAINTENANCE_DATABASE_URL=<显式 DSN> .venv/bin/python -m scripts.verify_memory_stage1_supplement`，退出码 0。`B1.json`：dry_run、updated=0、pending=5、Provider 构造=0、全程 DML=0。脚本 39–48 |
| B.2 | CLI/DB | 受阻 | 缺授权配置，未执行真实 missing 回填与批内并发修改/归档 skipped 验证；不以 stub 的结果抵充 |
| B.3 | CLI/DB | 受阻 | 缺授权配置，未执行真实 mismatch 回填与失败保留原向量/模型验证；未用别名向其他模型发请求 |
| B.4 | CLI | 通过 | `env -u MEMORY_MAINTENANCE_DATABASE_URL .venv/bin/python scripts/backfill_memory_embeddings.py`，独立 subprocess 退出码 **2**；`B4.json`：status=blocked、reason=专用 DSN 未配置。现有 main 在构建 engine 前返回，零连接/零写入；源码 `scripts/backfill_memory_embeddings.py:124-130` |
| C-readonly | 服务/DB | 通过 | zero 脚本实际 `SET TRANSACTION READ ONLY`，SHOW 返回 on；supplement 在只读事务执行空范围 UPDATE 被 DB 拒绝，`C-readonly.json` error_type=DBAPIError。采样 SQL 为一条聚合 SELECT；未持久修改开关 |
| C-metrics | 服务 | 通过 | `C.json`：facts active=5、compatible=0、coverage=0；legacy active=0、coverage=0。三项 gauge 的 `.set` 由测试收集器截获，按 facts/legacy 两个 storage 输出，时间戳>0；未声称 Prometheus 服务已采集 |
| C-task | 任务 | 通过 | 实际调用 `_collect_embedding_coverage()`：运行闸门 mock 关闭返回 disabled；打开返回真实 PG collected，各复查一次。真实 Celery 配置 schedule=300、queue=analysis。`C.json`。不代表 Worker/Beat 跨进程验收（属阶段 2） |
| D.1 | 服务/DB | 通过 | zero 脚本 135–180：10,000 行随机向量 + ANALYZE；调用实际 `_search_facts_merged`/FactStore 50 次；默认规划器使用 idx_memory_facts_embedding_hnsw。`D.json`、`D-plan-filter-False.json` |
| D.2 | 服务/DB | 通过 | 同上，启用模型过滤后再测 50 次；捕获实际 ORM SQL 包含 embedding_model 等值限定，结果均当前模型；独立夹具确认旧模型仅在关键词候选。`D.json`、`D-plan-filter-True.json`、`D-hybrid.json` |
| D.3 | 服务/DB | 通过 | supplement 49–67：同分区当前高相似、旧模型关键词、正交低相似三条夹具；开启 hybrid、floor=0.9，向量仅当前高相似一条，旧模型只进关键词，低相似不进向量；最终两条结果的 RRF 分数与独立公式逐条相等。`D-hybrid.json` |
| E-real | 服务/DB | 受阻 | 缺授权配置，未执行真实 Provider 索引/1024 维成对写入验证 |
| E-no-config | 服务/DB | 通过 | supplement 79–103：实际 `KnowledgeIndexService.index_document` 保存一个无向量 chunk，embedding/model 均 NULL；实际 `VectorRetrievalService.search_knowledge` 关键词返回一条结果；Provider 调用=0。`E-no-config.json` |

### 指标与断言边界

A.2 使用实际 `AgentMemoryService._embed` + 实际 FactStore 插入；测试代码把返回值交给写入层，未模拟完整工具/settle 链。指标为真实计数器调用点的内存截获，不是外部监控平台截图。C 的 gauge 对应：`_mismatch`→`memory.embedding_model_mismatch_rows`、`_coverage`→`memory.embedding_model_coverage`、`_sample_time`→`memory.embedding_coverage_sample_timestamp_seconds`，见 `memory_embedding_service.py:23-30`。运行闸门由测试注入两种返回值，未修改站点 DB 设置。

### 性能与计划证据

| 场景 | 次数 | P50 ms | P95 ms | 最小/最大 ms | HNSW |
|---|---:|---:|---:|---|---|
| 模型过滤关闭 | 50 | 5.1803 | 5.8732 | 4.3542 / 8.3486 | 是 |
| 模型过滤开启 | 50 | 5.5587 | 6.2609 | 4.5234 / 8.3011 | 是 |

P50 为中位数，P95 为 nearest-rank 第 48/50 个样本；单进程、本机数据库、包含共享/当前 Agent 分区两路服务调用、无并发压力，不能外推生产容量。原始 50 个样本均在 D.json。EXPLAIN 使用相同分区、排序、模型条件的显式 SQL（投影为 SELECT *），实际 ORM 查询另截获模型谓词；不声称 EXPLAIN 文本就是 ORM 原始 SQL。未设置 enable_seqscan=false 等规划器强制项。

计划 JSON 原文（仅脱敏合成所有者标签）分别见上述两个 D-plan 文件，均含 ANALYZE 与 BUFFERS。开启过滤的关键原文摘录：

```text
"Node Type": "Index Scan"
"Index Name": "idx_memory_facts_embedding_hnsw"
"Actual Rows": 10
"Rows Removed by Filter": 15
```

完整计划保留距离排序、本地随机查询向量、分区与模型过滤条件、Shared Hit/Read Blocks 和规划/执行时间，便于复核。

## 3. 失败与受阻清单

【阻断阶段目标】A.1、B.2、B.3、E-real 受阻。虽然用户通知配置已就绪，A.1 前检查指定绝对路径仍不存在（A1-preflight.json）。未尝试调用其他模型、其他密钥来源或抽取模型。需该文件在此工作区实际可见后才能完成真实调用验收。

【阻断灰度准入】真实 Provider 维度/有限数、真实回填并发保护与失败保留、真实 KB 向量成对写入尚缺证据，不能以零调用项通过代替准入。

【体验不一致】无业务失败证据。首轮新增验证脚本的随机数据绑定将整数传入 text 参数，报 DataError；已修正新脚本为字符串，重跑退出码 0，未修改业务代码。B.1 初版 SQL 采样范围包含准备数据 INSERT，已在补充脚本中重新清空采样区间并实测 DML=0；报告引用最终 B1.json。

【建议优化】无本轮业务修改建议；只记录验收边界，不修复或调参。

## 4. 模型调用与成本

| 子任务 | 真实 embedding 调用 | token 估算 | 说明 |
|---|---:|---:|---|
| A.1 | 0 | 0 | 配置准入受阻 |
| A.2 | 0 | 0 | 四种 mock 返回/异常 |
| B.1 | 0 | 0 | Provider 构造=0，DML=0 |
| B.2 | 0 | 0 | 受阻 |
| B.3 | 0 | 0 | 受阻 |
| B.4 | 0 | 0 | 无 DSN，启动前退出 |
| C | 0 | 0 | 聚合 SQL/运行闸门/队列配置 |
| D | 0 | 0 | 数据及查询向量本地随机生成 |
| E | 0 | 0 | 真实部分受阻，断配置分支零调用 |
| 合计 | **0** | **0** | 抽取模型亦为 **0** 次 |

批准上限 150 次，累计使用 0、剩余 150；成本 0。上限不是预估消费数，因此不计算“少于预算百分比”作为偏差。机器可读台账：`call-ledger.json`。本轮未发生任何真实模型请求。

## 5. 下一阶段准入建议

**受阻**：零调用项目已取得真实 PG/服务/CLI 证据；真实调用部分未验证。需要先让授权的 `.env.test` 在当前仓库路径实际可见，再执行 A.1、B.2、B.3、E-real；沿用 150 次累计上限和抽取零调用约束。阶段 1 完整验收及阶段 2 准入权归用户。

验证资产：`scripts/verify_memory_stage1_zero.py`、`scripts/verify_memory_stage1_supplement.py`，Ruff 均通过。证据目录为运行产物；未执行 commit。
