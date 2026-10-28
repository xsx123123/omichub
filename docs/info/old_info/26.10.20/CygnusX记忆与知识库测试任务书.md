# CygnusX 记忆与知识库测试任务书（Codex 施工版）

> 版本：2026-10-20 v1.1（§1/§4 口径修订 + 追加 §13 核对记录）
> 依据文档：《CygnusX AI 记忆系统当前架构》（as-built，2026-10-20）、《CygnusX 知识库（Knowledge Base）实现架构》（2026-10-20）
> 用途：交给编码 Agent（Codex）在仓库环境中执行的完整测试施工文档。目标是把两份架构文档中"代码已实现、真实环境未验"的能力，逐项变成带证据的验证结论。
> 核心原则：**验收权在用户手里，不接受编码 Agent 自报通过。** 每项结论必须带可复核证据（命令、退出码、文件路径、指标快照）。
> 使用方式：推荐**按阶段分次投喂**——每阶段提示词块（§3～§8）自包含，粘贴给 Codex 执行，拿回报告验收后再发下一阶段；也可整份文档一次性交给 Codex 按顺序执行。

---

## 0. 测试总纪律（每个阶段提示词均引用本节，编号 T0）

**T0-1 只测不改。** 禁止修改 `src/` 与 `frontend/` 下任何现有业务代码、禁止修改现有测试文件的断言、禁止修改任何已有 Alembic 迁移文件的内容。允许的新增仅限四类：
- 新的测试文件（`tests/` 下新建文件，不动旧文件）；
- 新的验证/种子脚本（`scripts/` 下新建文件）；
- 测试环境编排文件（如 `docker-compose.test.yml`、`.env.test` 模板）；
- 测试报告（`docs/info/` 下新建文档）。
发现任何失败：**记录证据 → 归类严重度 → 继续后续项**，禁止顺手修复业务代码。

**T0-2 显式 DSN。** 所有数据库连接只使用专用环境变量（`MEMORY_TEST_DATABASE_URL` / `MEMORY_ACCEPTANCE_DATABASE_URL` / `MEMORY_MAINTENANCE_DATABASE_URL`），禁止回退到 `DATABASE_URL`，禁止对任何非一次性测试库执行迁移、回填或清理。

**T0-3 保护残留。** 禁止删除 `mem0_memories` 表、`agent_memories` 旧表、`.env.example` 的 `MEM0_*` 段。`scripts/check_schema_drift.py` 对 `mem0_memories` 的豁免不得移除。

**T0-4 真实模型调用需逐阶段批准。** 涉及真实 Embedding/抽取模型调用的阶段（§4、§5、§8），执行前先向用户给出预估调用量与成本，得到书面同意再跑；未获批准时用 stub/伪 Provider 替代，并在报告中标注"未经真实模型验证"。

**T0-5 证据纪律。** 报告与日志不输出记忆正文、知识库正文片段、用户 ID、密钥与连接串。所有结论标注文件路径/函数名/命令/退出码。测试数据全部使用合成夹具（假用户、假项目、假会话），不使用任何真实用户数据。

**T0-6 结果分类。** 每个测试项结论只能是：通过 / 失败 / 受阻（blocked，附受阻原因）。失败项按严重度分级：【阻断阶段目标】【阻断灰度准入】【体验不一致】【建议优化】。

---

## 1. 环境前置（用户侧确认项，Codex 开工前逐项打勾）

- [ ] 一台可运行 Docker 的开发机或 CI runner（架构文档记录"当前沙箱 Docker socket 被拒绝"，这是此前真实 PG 验证全部受阻的根因，必须先解决）。
- [ ] 镜像就绪：`pgvector/pgvector:pg15`（或 pg16，pgvector ≥ 0.7，支持 HNSW）、`redis:7`。
- [ ] 仓库后端依赖可安装（requirements、alembic、pytest、asyncpg）。
- [ ] 专用测试库已创建：迁移演练库 `cygnusx_memtest`、只读基线库 `cygnusx_accept`、回填演练库 `cygnusx_maint`。**集成测试库命名必须服从各测试文件内的库名门禁**（2026-10-20 阶段 0 实证：memory 域要求 `memory_acceptance_test` 前缀、project_export 域要求 `project_export_test` 前缀、report 域要求 `report_test` 前缀，以各测试文件开头断言为准），禁止用单一库名通跑，更禁止为迁就库名修改测试文件——该门禁是刻意的防误操作护栏。
- [ ] 如执行 §4/§5/§8：用户已提供 Embedding 与抽取模型的真实密钥（写入 `.env.test`，不进 git），并书面批准该阶段。

---

## 2. 已实现能力清单（测试对象盘点）

> 本清单是两份架构文档的"已实现"侧快照，供 Codex 建立测试对象全景；每格给出代码锚点。详细边界以原文档为准。

### 2.1 记忆系统（v2，默认关闭，代码已完成）

| 域 | 已实现能力 | 代码锚点 |
| --- | --- | --- |
| 数据层 | `memory_blocks`（profile/preferences/current_focus，char_limit、版本 CAS、归档血缘、项目分区部分唯一索引）、`memory_facts`（profile/preference/project/summary/episode，content_hash 去重、supersede 版本链、HNSW cosine）、`memory_settlements` 区间回执 + `chat_sessions.last_settled_message_id` 游标、`memory_recall_batches` 幂等回执、`memory_consolidation_budgets/runs` 账本 | `src/cygnusx/infrastructure/database/models/agent_memory.py` |
| 自动化闸门 | `is_memory_runtime_enabled()`：v2 + DB 存在 + 站点开关，异常按关闭；管理查询异常同样按关闭 | `application/services/memory_runtime_policy.py` |
| 读取链 | 块 → 分区向量召回（无向量走关键词降级，≤8 转义词项）→ 复合排序（relevance × 时间衰减 × 重要性 × 召回强化）→ 字节预算整条目注入（6000/2800/3200，整条省略不截断）→ `<user_memory>` 不可信包装 → 异步召回统计 | `agent_memory_service.py`、`infrastructure/memory/fact_store.py` |
| 写入工具 | 5 个受控工具（save/update 拒绝旧式覆盖/update_block CAS/search/forget 归档）；`memory_write_arbitration_enabled=true` 时显式保存走仲裁模型，仅允许本次候选 ID | `application/services/agent_memory_tool_service.py`、`data/ai/tools/memory.yaml` |
| settle | 游标后增量读取（`(session_id, created_at, message_id)` 覆盖索引）、批次 ≤30 条/8000 字符、单次模型返回 facts+episode+focus、range_key 幂等、同事务写入、失败不结算、AgentTeams 双重排除、尾批开关（默认关） | `infrastructure/celery_app/tasks/memory.py` |
| 周度整理 | advisory lock 互斥、全站周预算 20 次原子预占、≤20 组、新 30+老 30 有界候选、证据校验（输入外 ID/episode 证据数/替代环链拒绝）、块提案快照、同事务提交、按 run dry-run/回滚 | `infrastructure/memory/consolidation.py`、`scripts/rollback_memory_consolidation.py` |
| 冷归档 | >90 天、recall_count=0、last_recalled_at 为空、importance≤3、仅 project/summary/episode，周 ≤500 条，UPDATE 条件复查 | 同上 |
| 遗忘 | 归档语义（不物理删除）、同文不自动复活、显式重存建版本；词面残留提示（默认关）：≤8 个 ≥2 字符词项、`%`/`_` 转义、≤20 条提示、60 字摘录、凭据隐藏、scan_status 四态、点击统计无写副作用 | `application/services/memory_residual_service.py` |
| 项目焦点 | `memory_focus_project01`：blocks.project_id、NULL/非 NULL 两个部分唯一索引、开关默认关、精确匹配不回退、按需 conflict-ignore 创建、降级遇非 NULL 拒绝 | 迁移 `memory_focus_project01` |
| embedding 隔离 | 同模型过滤（默认关）、混合检索 RRF（默认关）、向量/模型成对 NULL 规则、回填 CLI（dry-run 默认、500 行/批、条件更新、显式 DSN、blocked/exit=2）、覆盖率采样任务 | `application/services/memory_embedding_service.py`、`scripts/backfill_memory_embeddings.py` |
| Studio 文件记忆 | `MEMORY.md` 索引（≤200 条、≤8000 字符注入）+ `.memory/` 正文按需读、写入四步事务、Git 检查点（.gitignore 保护、10MB 跳过、20 个引用、restore-before 保护点） | `application/services/studio_context_service.py`、`studio_tools.py`、`studio_checkpoints.py` |
| 管理与观测 | 用户/管理员 memory-overview API、残留提示 POST 入口、前端管理面板；20+ 项指标埋点；迁移链 11 个 revision（破坏性降级拒绝）；漂移检查脚本 ×2；只读基线工具 | `api/v1/users.py`、`admin/users.py`、`scripts/` |

### 2.2 知识库（代码已完成）

| 域 | 已实现能力 | 代码锚点 |
| --- | --- | --- |
| 数据层 | `knowledge_bases`（show_in_lab / ai_searchable / is_enabled 三开关）、`kb_documents`（current_rev/pending_rev 双指针、kb_id、project_id）、`doc_revisions`（正文版本化）、`kb_chunks`（章节块 + 1024 维向量 + HNSW + content_hash + embedding_model）、编辑者/审核日志/问题反馈 | `infrastructure/database/models/knowledge_*.py` |
| 导入 | 单细胞笔记批量导入：md5 路径哈希幂等、相对链接重写为 `/docs-static/`、scseq 库兜底自建、原始 md 不动 | `scripts/import_scseq_knowledge.py` |
| 索引 | 发布/审核通过时同事务重建 chunks；按 Markdown 标题切块、每 section ≤1800 字符无 overlap；开机自动对齐（advisory lock、content_hash+模型标签比对、只重建变化文档、失败不阻塞启动） | `application/services/docs_service.py`、`KnowledgeIndexService` |
| 检索 | `knowledge_search` function tool：已发布 + 开关过滤 + 项目范围过滤；查询 ≤1000 字符；向量候选上限 max(limit×8, 40)；缺向量走关键词回退（≤12 词）；向量候选存在时关键词只重排不并集；摘录 ≤600 字符；返回 citation_id/章节/URL/分数；前端只渲染来源集合内引用 | `application/services/studio_tools.py::_knowledge_search`、`VectorRetrievalService` |
| 页面与管理 | KnowledgeView（DocTree/Reader/Editor/审核/反馈）、AI 配置中心知识库 Tab（开关/新建/删除/文档清单） | `frontend/src/views/KnowledgeView.vue`、`components/admin/KnowledgeResourceTab.vue` |

### 2.3 明确未实现（禁止当作缺口报告）

- 程序性记忆/知识卡片引擎；三种记忆载体的统一；语义级遗忘传播；跨组情节联合蒸馏；
- KB 侧双路并集/RRF、多查询扩展、检索质量基线；
- 全部真实环境验收（真实 PG/pgvector、Provider、Worker/Beat、25 案例质量）——**本任务书的目的就是补齐这一类**。

---

## 3. 测试阶段总览

| 阶段 | 目标 | 前置 | 预估工作量 |
| --- | --- | --- | --- |
| §4 阶段 0 | 真实 PG/Redis 环境基线 + 迁移链与降级演练 + 被 skip 集成测试跑通 | Docker 就绪 | 0.5–1 天 |
| §5 阶段 1 | Embedding Provider 实测 + 向量回填与覆盖率 | 阶段 0 + 密钥批准 | 0.5 天 |
| §6 阶段 2 | Celery Worker/Beat 端到端（settle/召回/整理/回滚/冷归档） | 阶段 0、1 | 1–1.5 天 |
| §7 阶段 3 | 分区隔离与安全边界实测 | 阶段 0（部分依赖 1、2） | 1 天 |
| §8 阶段 4 | 知识库全链路（导入→审核→索引→检索→引用） | 阶段 0、1 | 0.5–1 天 |
| §9 阶段 5 | 25 案例记忆质量修前基线 | 阶段 0–2 + 密钥批准 | 1–2 天 |

依赖说明：阶段 1 与阶段 4 的检索部分都需要真实 embedding；阶段 2 的 settle 需要抽取模型；若密钥暂缓，可先做阶段 0、3（隔离类大部分可用 stub 向量/伪 Provider），但报告必须标注哪些项未经真实模型验证。

---

## 4. 阶段 0：真实环境基线（提示词块，直接粘贴给 Codex）

```text
你是一名资深后端工程师，在 CygnusX 仓库中执行「记忆与知识库真实环境基线测试」。
先阅读任务书第 0 节总纪律（T0-1 只测不改、T0-2 显式 DSN、T0-3 保护残留、T0-5 证据纪律、
T0-6 结果分类），全程遵守。禁止修改 src/ 与 frontend/ 现有代码与已有迁移文件；
只允许新增 docker-compose.test.yml、tests/ 新文件、scripts/ 新文件与测试报告。

背景：记忆 v2 与知识库向量索引代码已完成，但从未在真实 PostgreSQL/pgvector 上运行过。
迁移链（记忆相关 11 个 revision）：m5n6o7p8q9r0 → n6o7p8q9r0s1 → memory_project01 →
memory_episode01 → memory_rank01 → memory_partition01 → memory_consolidate01 →
memory_focus_project01 → memory_consolidate_rollback01 → memory_recall_purge01 →
memory_settle_cursor01；知识库相关：o3p4q5r6s7t8、p4q5r6s7t8u9、j4k5l6m7n8o9。

任务：
A. 环境编排
   1. 新建 docker-compose.test.yml：pgvector/pgvector:pg15（或 pg16）+ redis:7；
      创建一次性测试库 cygnusx_memtest / cygnusx_accept / cygnusx_maint；
      集成测试另按各测试文件内的库名门禁建库（如 memory_acceptance_test_stage0），
      命名规则见任务书 §1。
   2. 记录服务端版本、pgvector 版本（须 ≥0.7 支持 HNSW），写入报告。

B. 迁移链演练（对 cygnusx_memtest）
   1. alembic upgrade head：从空库升到 head；确认迁移链单 head；导出完整 revision 列表。
   2. 逐项验证 schema 落地：memory_facts 的 HNSW cosine 索引存在（\d+ 或 pg_indexes 证据）、
      memory_blocks 的 NULL/非 NULL 项目两个部分唯一索引存在、kb_chunks 的
      embedding vector(1024) 与 HNSW 索引存在、(session_id, created_at, message_id)
      settle 覆盖索引存在、memory_recall_purge01 的 created_at 索引存在。
   3. 降级保护演练（每个用种子数据构造条件后执行 downgrade，必须拒绝且不丢数据）：
      - memory_focus_project01：存在非 NULL 项目块时 downgrade 拒绝；
      - memory_consolidate01：存在整理审计历史时 downgrade 拒绝；
      - memory_episode01：存在超长正文时 downgrade 拒绝自动截断；
      - memory_consolidate_rollback01：已有回滚记录时 downgrade 拒绝。
      另验证：无上述数据时这些 revision 可正常 downgrade 再 upgrade 往返。
      【核对后补充】每个拒绝用例必须记录拒绝原因（异常类名 + 错误信息关键行 +
      对应迁移文件:行号），证明拒绝来自预期保护逻辑而非 incidental 报错。
   4. scripts/check_schema_drift.py 对当前库执行通过（mem0_memories 豁免不移除）；
      scripts/check_env_example_drift.py 通过。

C. 被跳过集成测试的真实运行
   1. 配置 MEMORY_TEST_DATABASE_URL 指向命名合规库（如 memory_acceptance_test_stage0，
      以 tests/integration/ 各文件开头的库名断言为准）；
   2. 运行 tests/integration/test_memory_focus_postgres.py——此前因未配置 DSN 全部 skip，
      本轮必须真实执行：迁移/8 路并发创建/拒绝降级/往返演练，逐项记录结果；
      【核对后补充】附 pytest -v 输出与通过测试函数内的断言点清单。
   3. 全仓检索其他因缺 DSN/缺 PG 被 skip 的测试（grep skip 条件与 MEMORY_/PG 相关标记），
      列清单并全部真实运行，报告每项通过/失败。

D. 只读基线工具
   1. MEMORY_ACCEPTANCE_DATABASE_URL 指向 cygnusx_accept（先跑迁移），
      执行 scripts/inspect_memory_baseline.py：确认输出 status=ok/collected、只读事务、
      不输出正文/用户 ID/凭据；记录服务端/pgvector 版本与 Alembic revision 字段。
   2. 不配置 DSN 时再跑一次：确认返回 status=blocked、exit=2（保护行为）。

E. 种子数据脚本（新增 scripts/seed_memory_test_data.py）
   生成合成夹具供后续阶段使用：2 个用户、每用户 2 个 Agent、2 个项目、若干普通会话
   （含可结算的消息序列、含跨项目会话、含 1 个 AgentTeams mode 会话）、若干预置事实
   （覆盖 profile/preference/project/summary/episode 各 scope、含 inactive、
   含不同 importance/recall_count/时间分布）。全部假数据，脚本支持 --dsn 显式指定、
   默认 dry-run 打印计划。

交付：docs/info/26.10.xx/CygnusX测试报告-阶段0-环境基线.md，格式按任务书 §10；
能力矩阵逐项标注 通过/失败/受阻 + 证据（命令、退出码、文件:行号）。
```

**阶段 0 验收 checklist**

| # | 操作 | 期望现象 | 不通过时的处理 |
| --- | --- | --- | --- |
| 0-1 | 用户手测：`git status --short` 查看改动（含未跟踪文件） | 只有新增文件（compose/种子脚本/报告），`src/`、`frontend/`、已有迁移零改动 | 有改动 → 要求 Codex 还原并说明原因 |
| 0-2 | Codex 执行：空库 `alembic upgrade head` | 单 head，全部 11 个记忆 revision + 3 个知识库 revision 在链上 | 多 head/断链 → 报告受阻项，拿回给我核对 |
| 0-3 | Codex 执行：4 个降级保护用例 | 有保护数据时 downgrade 全部明确拒绝（附异常类名与错误信息）且数据未丢；无保护数据时往返成功 | 任何一个静默丢数据 → 【阻断灰度准入】 |
| 0-4 | Codex 执行：`test_memory_focus_postgres.py` | 不再 skip，真实执行通过（含 8 路并发创建），附 pytest -v 与断言点清单 | 失败 → 只记录证据不修代码，拿回核对 |
| 0-5 | 用户手测：抽 1 条报告中的命令重跑 | 结果与报告一致 | 不一致 → 报告证据不可信，整阶段重交 |

---

## 5. 阶段 1：Embedding Provider 与向量维护实测（提示词块）

```text
你是一名资深后端工程师，在 CygnusX 仓库执行「Embedding Provider 与向量维护实测」。
遵守任务书 §0 总纪律（尤其 T0-4：真实模型调用先报预估调用量，得到用户书面批准再跑）。
前置：阶段 0 已通过；种子数据已入库。

背景：记忆与知识库共用 AGENT_MEMORY_EMBEDDING_MODEL（1024 维契约）。向量/模型成对保存：
缺向量或缺有效模型标识时都为 NULL；_embed 在维度不符、非有限数、空返回、Provider 异常时
降级为空向量。回填 CLI scripts/backfill_memory_embeddings.py 默认 dry-run，要求显式
MEMORY_MAINTENANCE_DATABASE_URL，--apply 才写库，每批 ≤500 行，先完成模型调用再条件更新。
注意（阶段 0 实证）：tests/integration/test_memory_embedding_postgres.py 已在真实 PG 上
跑通 HNSW/model filter/backfill/EXPLAIN 的正确性路径；本阶段 D 项是性能口径，不重复、
不可省略。

任务：
A. 真实 Provider 契约验证
   1. 配置真实 AGENT_MEMORY_EMBEDDING_MODEL；对 10 条种子事实触发向量生成：
      断言维度=1024、非 NaN/Infinity；记录 memory.embedding_outcomes 各取值计数。
   2. 故障注入（逐项）：指向错误端点 → provider_error 路径、返回错误维度（用 mock
      Provider）→ dimension_mismatch、返回空 → empty；每种情况下事实行的
      embedding 与 embedding_model 必须成对为 NULL，服务不崩、指标正确。
B. 回填 CLI 实测（对 cygnusx_maint，先迁移+种子）
   1. 默认 dry-run：只计数不调用模型不写库（用 Provider 调用计数证明零调用）。
   2. --apply：missing 模式回填；验证"先完成整批模型调用再条件更新"——
      用一条在回填期间被并发修改正文/归档的事实，断言该行被 skipped 而非覆盖。
   3. 换模型名后跑 --mode mismatch：旧标签行被重建；生成失败的行保留原向量与标签。
   4. 无 MEMORY_MAINTENANCE_DATABASE_URL 时运行：确认 blocked/exit=2 且零写入。
C. 覆盖率采样任务
   开启 memory_embedding_coverage_enabled（interval 300），确认：只读、analysis 队列、
   复查运行闸门；memory.embedding_model_mismatch_rows / embedding_model_coverage /
   embedding_coverage_sample_timestamp_seconds 三个指标按 storage 区分输出；
   空表覆盖率为 0 的行为与文档一致。
D. 真实 pgvector 查询计划与性能
   1. 在 ≥1 万条合成向量行（脚本批量生成随机向量+标签）上执行 FactStore 分区向量查询，
      EXPLAIN (ANALYZE, BUFFERS) 记录执行计划：确认走 HNSW 索引而非全表顺序扫描；
      记录 P50/P95 延迟（各 50 次）。
   2. 开启 memory_embedding_model_filter_enabled 后重复：确认 SQL 限定
      embedding_model = 当前模型，旧模型行只出现在词面候选。
   3. 开启 memory_hybrid_retrieval_enabled 并设置 memory_hybrid_min_similarity：
      验证同分区向量+关键词候选 RRF 合并、低于下限的向量被排除。
E. 知识库侧向量链路（为 §8 铺垫）
   对种子知识库文档触发索引，确认 kb_chunks 的 embedding/embedding_model 成对写入；
   断开 embedding 配置后索引仍保存无向量 chunk（关键词路径兜底）。

交付：阶段1报告（§10 格式），含模型调用总次数与成本计数。
```

**阶段 1 验收 checklist**

| # | 操作 | 期望现象 | 不通过时的处理 |
| --- | --- | --- | --- |
| 1-1 | Codex 执行：维度契约 | 真实向量 1024 维；四种故障路径全部成对 NULL、零崩溃 | 任何故障路径写入脏向量 → 【阻断灰度准入】 |
| 1-2 | Codex 执行：回填并发用例 | 并发修改行被 skipped，dry-run 零模型调用 | dry-run 有调用 → CLI 契约破坏，记录并停阶段 |
| 1-3 | Codex 执行：EXPLAIN 证据 | 向量查询走 HNSW 索引；报告含计划原文与延迟分布 | 顺序扫描且无可解释原因 → 记录，暂不调参 |
| 1-4 | 用户手测：报告调用量 vs 实际账单/用量 | 数量级一致 | 偏差大 → 要求补埋点证据 |

---

## 6. 阶段 2：Worker/Beat 端到端（提示词块）

```text
你是一名资深后端工程师，在 CygnusX 仓库执行「记忆异步链路端到端测试」。
遵守任务书 §0 总纪律。前置：阶段 0、1 通过；本阶段在 docker-compose.test.yml 中增加
celery worker（analysis 队列）与 celery beat 服务，全部指向测试库与测试 Redis。

背景契约（来自架构文档，作为断言依据）：
- settle：普通会话消息达阈值投递；新消息 <4 条返回 too_short；尾批需 memory_settle_tail_enabled
  + force_tail，最少 tail_min_messages（默认 2）；每批 ≤30 条/8000 字符；游标消息缺失返回
  cursor_missing；首条超预算返回 input_budget；两者保留区间不重放不跳过；range_key 唯一
  防重复结算；抽取/写入失败不结算、游标不动；AgentTeams（mode / system status /
  "agentteams:" ID 前缀）三重排除且跳过时不写 settlement 不动游标。
- 召回统计：record_recall_batch 先插回执再批量递增 recall_count；同 batch_id 重复投递
  不重复计数；TTL 清理按 memory_recall_batch_ttl_days（默认 14）/ purge_limit（5000）。
- 周度整理：PostgreSQL session advisory lock 互斥（忙则跳过、解锁失败废弃连接）；
  全站周预算默认 20 次、调用前原子预占且失败也消耗；≤20 组；新事实 30 天内 ≤30 条 +
  老候选 ≤30 条；输入 ≤18000 字符、60 秒超时；模型引用输入外 ID / 合并 episode /
  替代环链 → 拒绝；仅 episode 证据时默认需 ≥2 个独立非 AgentTeams 会话；事实替代+块更新+
  审计+水位同事务；支持按 run dry-run/回滚（scripts/rollback_memory_consolidation.py），
  回滚遇后续人工修改返回冲突不覆盖，已回滚 run 拒绝重复执行。
- 冷归档：>90 天 + recall_count=0 + last_recalled_at 为空 + importance≤3 +
  仅 project/summary/episode；周 ≤500 条；个人事实不参与；不在回滚范围。

任务（每项都要 DB 物证，不接受日志自述）：
A. settle 端到端
   1. 种子普通会话（6 条消息）→ 投递 settle → 断言同事务产物：普通事实（≤200 字符）、
      episode（≤1000 字符）、current_focus、settlement 回执、游标前移一致；
      memory.settle_succeeded 计数 +1。
   2. 3 条消息会话 → too_short，无 settlement、游标不动。
   3. 开启尾批：空闲会话 2 条尾消息 + force_tail → 正常结算；关闭开关时 Beat 尾批
      扫描零投递（memory.settle_tail_enqueued 不增）。
   4. 删除游标消息 → cursor_missing；首条消息超 8000 字符 → input_budget；
      两者区间保留、游标不动、不从头重放。
   5. AgentTeams 三种特征各造一个会话 → memory.settle_skipped +3，零写入。
   6. 幂等：同一区间并发投递两次 → 只一条 settlement、事实无重复；
      （文档已声明回执检查前可能重复调用抽取模型——如实记录调用次数，不算失败）。
   7. 故障注入：抽取 Provider 挂掉 → memory.settle_failed{阶段=extraction} +1、
      无 settlement、游标不动；DB 写入中途失败（用约束触发）→ 整体回滚。
B. 召回批次
   同一 batch_id 投递两次 → recall_count 只 +1；构造 created_at 超 TTL 的回执 →
   清理任务删除且不超过 purge_limit；入队失败不阻塞请求路径（用 broker 断连模拟）。
C. 周度整理
   1. 并发跑两个 consolidate 实例 → 一个持锁执行、一个忙跳过（advisory lock 证据）。
   2. 预算：把 memory_consolidation_max_calls 调小（测试配置 2）→ 第 3 次拒绝；
      让第 1 次模型调用失败 → 额度仍被消耗（预占语义证据）。
   3. 用可控 stub 模型逐项返回非法计划：输入外 ID、合并 episode、替代环、替代链 →
      全部拒绝且该组 run 记录失败原因；合法计划 → 事实替代+块更新+审计+水位
      在同一事务（制造最后一步失败验证整体回滚）。
   4. 仅 1 个 episode 证据的画像提案 → 拒绝；≥2 个独立会话 episode → 允许。
   5. 回滚：成功 run 先 dry-run（零写入证据）再执行 → 事实恢复、块按快照恢复且
      版本 +1、rolled_back_at 落库、生成回滚审计 run；对同一 run 重复回滚 → 拒绝；
      回滚前人工改过一个被替代事实 → 整次回滚拒绝、零覆盖。
D. 冷归档
   种子满足/不满足四条件的混合事实各若干 → 只有全满足的 project/summary/episode 被归档；
   个人事实零归档；归档 ID 记审计、正文保留；单次 ≤500。
E. Beat 编排
   确认 memory 任务路由 analysis 队列；周日 03:00（北京时间）调度项存在；
   尾批扫描（开启时）每 300 秒、最多 200 个空闲 30 分钟会话、排除 AgentTeams、
   任务体复查运行闸门——用测试时钟/手动触发验证，不等真实周期。

交付：阶段2报告（§10 格式），每项附 DB 查询证据（表名+关键字段，隐去正文）。
```

**阶段 2 验收 checklist**

| # | 操作 | 期望现象 | 不通过时的处理 |
| --- | --- | --- | --- |
| 2-1 | Codex 执行：settle 六产物一致性 | 同事务、游标前移、指标 +1 | 任一缺失 → 【阻断阶段目标】 |
| 2-2 | Codex 执行：幂等与故障注入 | 重复投递零重复写入；失败零结算、游标不动 | 出现部分写入 → 【阻断灰度准入】 |
| 2-3 | Codex 执行：整理锁与预算 | 并发互斥；失败也耗额度；非法计划全拒绝 | 预算可绕过 → 【阻断灰度准入】 |
| 2-4 | Codex 执行：回滚三用例 | dry-run 零写入；冲突拒绝；重复回滚拒绝 | 回滚覆盖人工修改 → 【阻断灰度准入】 |
| 2-5 | 用户手测：抽 2 项报告的 DB 证据查询重跑 | 与报告一致 | 不一致 → 整阶段证据重交 |

---

## 7. 阶段 3：分区隔离与安全边界实测（提示词块）

```text
你是一名资深后端工程师，在 CygnusX 仓库执行「记忆分区隔离与安全边界测试」。
遵守任务书 §0 总纪律。前置：阶段 0 通过；语义类用例可用 stub 向量或真实向量
（若阶段 1 已完成）。测试方式：应用服务层 + 受控工具层 + REST 层三层都要覆盖，
不能只测一层。

背景契约：
- 共享个人事实/块：agent_id 为空字符串 + project NULL，同用户跨 Agent 跨项目可见；
  共享查询只允许个人 scope，须阻断历史错分区项目事实泄露。
- 项目事实：user+agent 分区；普通检索 = 无项目事实 + 当前项目事实；无当前项目时只取
  NULL 项目；项目候选仲裁用当前项目精确边界。
- episode：读取严格匹配 user/agent/project；摘要只替代同 source_session 旧摘要。
- current_focus：开关关闭只用通用焦点；开启后精确匹配、无项目只读 NULL、缺项目焦点
  不回退 NULL；关闭后项目内容保留只读。
- 工具：user_id 必须与 ToolInvocationContext 受控身份一致；项目从同用户拥有的会话
  派生，不接模型自传项目；forget 不物理删除、自动同文插入不复活 inactive、显式重存
  走历史哈希槽新版本。
- 残留扫描（默认关）：词项 ≤8 个且 ≥2 字符、%/_ 转义、合并 ≤20 条、摘录 ≤60 字、
  命中凭据规则隐藏摘录、日志零正文；只扫同 user active 数据且不越过当前项目/Agent
  边界；扫描失败回滚保存点保留归档并返回 failed；residual-actions 只记录点击无写副作用。
- 注入：总预算 6000 / 块 2800 / 情节 3200 字节；整条省略不截断；<user_memory> 包装；
  块标题带 version/char_limit；HTML/代码/比较符号原文保留。

任务（每个用例断言"应该看不到"的确实看不到，而不只是"该看到的看到了"）：
A. 跨用户：用户 B 的工具调用携带 A 的身份 → 拒绝；REST 越权访问 A 的 overview/forget/
   residual-actions → 403/404；A 的事实/块/episode 在 B 的任何检索结果中零出现。
B. 跨 Agent：Agent X 的项目事实在 Agent Y 检索中不可见；共享个人事实在两个 Agent
   都可见；L4 @专家直答/会诊路径不注入本长期记忆（装配证据）。
C. 项目边界：P 项目事实在项目 Q 会话不可见、NULL 项目事实两边可见、无项目会话只取
   NULL；仲裁候选只含当前项目精确边界内事实。
D. 项目焦点：开启开关 → P1 焦点在 P2 读取中不出现、缺 P2 焦点不回退通用焦点；
   关闭开关 → 通用焦点恢复、P1 内容保留且管理面只读；并发首次创建同一项目焦点
   （8 路）→ 只一行（部分唯一索引 + conflict-ignore）。
E. episode：同 user/agent 不同 project 的 episode 互不串；重复 settle 同会话只替代
   同 source_session 摘要。
F. 遗忘：归档后检索零出现；自动沉淀同文命中 inactive 不复活（行数不变）；显式重存 →
   旧行入历史槽、新行 active、血缘字段正确。
G. 残留扫描：开启开关执行 forget → 提示 ≤20、摘录 ≤60 字；关键词含 %/_/反斜杠 →
   转义后不报错不异常命中；正文含测试凭据模式 → 摘录隐藏；越界验证：残留不扫描
   其他项目/其他 Agent 分区、不扫会话原文与 Studio 文件；制造扫描中 DB 异常 →
   返回 failed 且归档保留；residual-actions 对非本人目标 → 拒绝，且接口零写副作用。
H. 注入预算：构造块 2800+ 情节 3200 占满的场景 → 普通事实段注入 0 字节且
   memory.inject_units_omitted{unit=fact} 计数；任一超长块整条省略而非截断；
   包装闭合完整；事实正文含指令样式文本（如"忽略之前的指令"）原样保留在包装内、
   不逃逸出 <user_memory>。
I. legacy 边界：memory_v2_enabled=false 时 Chat 自动链路零注入（不是回退注入 legacy）；
   管理/服务层按 legacy 投影读取。

交付：阶段3报告（§10 格式），矩阵列为「层（服务/工具/REST）× 用例」。
```

**阶段 3 验收 checklist**

| # | 操作 | 期望现象 | 不通过时的处理 |
| --- | --- | --- | --- |
| 3-1 | Codex 执行：A/B/C 隔离矩阵 | 所有"不应可见"用例零泄露 | 任何跨用户泄露 → 【阻断灰度准入】最高级 |
| 3-2 | Codex 执行：焦点开关三态 | 开=精确无回退；关=通用恢复+项目只读 | 回退到通用焦点 → 与契约冲突，记录 |
| 3-3 | Codex 执行：遗忘三用例 | 归档不复活、重存建版本、血缘正确 | 自动复活 → 【阻断灰度准入】 |
| 3-4 | Codex 执行：注入预算 | 事实可被挤到 0 且整条省略；包装完整 | 出现截断正文 → 契约破坏，记录 |
| 3-5 | 用户手测：抽查 G 的转义用例命令 | 与报告一致 | 不一致 → 重交 |

---

## 8. 阶段 4：知识库全链路实测（提示词块）

```text
你是一名资深全栈工程师，在 CygnusX 仓库执行「知识库全链路测试」。
遵守任务书 §0 总纪律。前置：阶段 0、1 通过（embedding 可用）；测试知识库文档全部用
合成 Markdown 夹具（新建 tests/fixtures/knowledge/ 目录），不使用仓库真实语料做断言基础。

背景契约：
- 导入：scripts/import_scseq_knowledge.py 遍历 docs/knowledge/sc-seq/**.md；
  doc_id = "scseq-" + md5(相对路径)[:12]，幂等重跑跳过；标题取首个 H1、分类取顶层
  目录名；相对图片/附件链接重写为 /docs-static/<相对docs/路径>（逐段 URL 编码），
  不存在则保留并计数；status=1 直接发布；scseq 库行不存在时兜底自建；原始 md 不动。
- 索引：发布与审核通过时同一事务删旧 chunks + 按 Markdown 标题切块写新 chunks；
  每 section ≤1800 字符、无 overlap；content_hash + 模型标签用于增量对账；
  开机 KNOWLEDGE_AUTO_REINDEX_ENABLED 异步扫描（advisory lock 防多实例重复），
  ensure_document_indexed 只重建变化文档，失败告警但不阻塞启动；缺 embedding 配置
  或生成失败仍存无向量 chunk。
- 检索：knowledge_search（query ≤1000 字符、limit 1–8 默认 5）；只取已发布 +
  ai_searchable + is_enabled + kb_id IS NULL 兼容 + 文档/知识库项目范围过滤；
  向量候选上限 max(limit×8, 40)；缺模型/生成失败/维度不符/向量 SQL 失败/无向量命中 →
  关键词候选（≤12 词，匹配正文与标题）；向量候选存在时关键词只重排不并集；
  摘录 ≤600 字符；返回 citation_id/doc_id/标题/类别/章节路径/摘录/URL/分数。
- 页面：导航与详情校验 show_in_lab + is_enabled；编辑写 pending_rev，管理员审核后
  才切 current_rev；历史/编辑者/问题反馈可查。
- 管理：/admin/knowledge-bases CRUD；库内有文档时拒绝删除；三开关语义：
  show_in_lab 关=页面消失检索不受限；ai_searchable 关=检索不到页面不受限；
  is_enabled 关=两者皆失效。

任务：
A. 导入与幂等
   1. 夹具 md 树（含嵌套目录、根目录文件、相对图片存在/缺失各一）跑导入两次：
      第二次零新增；doc_id 稳定；链接重写正确（存在的→/docs-static/ 绝对路径，
      缺失的→保留原样且计数）；原始 md 文件内容零改动（哈希对照）。
   2. 删掉 scseq 知识库行再跑导入 → 兜底自建成功。
B. 索引事务与增量
   1. 发布一篇夹具文档 → 同事务 chunks 落库；模拟索引写失败（用约束/断开模拟）→
      发布整体回滚（文档不留 published 状态）。
   2. 切块断言：按标题层级切分、每块 ≤1800 字符、相邻块无重叠、section_path 正确、
      (document_id, chunk_index) 唯一。
   3. 编辑文档改一段 → ensure_document_indexed 只重建该文档；未变文档零重建
      （用 DB 写入计数或 chunk 行不变证明）。
   4. 断开 embedding 配置重建 → chunk 保存且 embedding/embedding_model 为 NULL。
C. 检索全路径
   1. 向量路径：提问命中 → 结果含稳定 citation_id、章节路径、≤600 字摘录、URL；
      同一查询两次 citation_id 一致。
   2. 回退路径：unset AGENT_MEMORY_EMBEDDING_MODEL（测试配置）→ 走关键词候选且
      结果合理；制造维度不符 → 同样回退。
   3. 重排语义：向量候选存在时构造一个关键词强匹配但向量不相关的 chunk →
      确认它只影响重排、不会作为额外候选并入（文档 §6.4 已知局限，验证行为与
      文档一致即可，不算缺陷，但要在报告中留一条证据记录）。
   4. 权限矩阵（三开关 × 两消费方共 6 格 + 项目范围 2 格）：
      show_in_lab=false 且 ai_searchable=true → 页面无、检索有；
      反转 → 页面有、检索无；is_enabled=false → 双无；
      项目会话可读平台级+本项目文档、不可读其他项目文档。
   5. query 传 1500 字符 → 截断到 1000 后执行（不报错）。
D. 审核流与页面
   页面编辑 → pending_rev（检索仍只见到旧 current_rev）→ 审核通过 → current_rev 切换
   且 chunks 重建 → 检索见到新内容；拒绝路径 → current_rev 不变；
   历史/编辑者/issues 接口数据正确。
E. 引用渲染（前端单测级即可）
   消息来源集合中存在的 citation_id → 渲染来源按钮；不存在的标记 → 不生成可点击引用
   （跑现有相关 Vitest 用例并补充缺失断言，只允许新增测试文件）。
F. 静态附件
   /docs-static 对存在的附件 200、对越界路径（../ 逃逸尝试）拒绝；
   可读附件文本成为派生 chunk 的路径（如已实现）用一篇带附件夹具验证。

交付：阶段4报告（§10 格式），权限矩阵 8 格逐项证据。
```

**阶段 4 验收 checklist**

| # | 操作 | 期望现象 | 不通过时的处理 |
| --- | --- | --- | --- |
| 4-1 | Codex 执行：导入幂等 | 二次导入零新增、md 原文哈希不变 | 重复文档 → 【阻断阶段目标】 |
| 4-2 | Codex 执行：索引事务 | 索引失败时发布回滚 | 出现 published 但无 chunks 的文档 → 【阻断灰度准入】 |
| 4-3 | Codex 执行：权限矩阵 8 格 | 与开关语义逐格一致 | 检索越权读其他项目文档 → 【阻断灰度准入】 |
| 4-4 | Codex 执行：回退路径 | 无向量时关键词兜底可用 | 直接报错 → 契约破坏，记录 |
| 4-5 | 用户手测：页面对一篇夹具文档走一遍编辑→审核→检索 | 审核前检索旧内容、审核后检索新内容 | 用户复现失败 → 阶段重交 |

---

## 9. 阶段 5：25 案例记忆质量修前基线（提示词块）

```text
你是一名资深后端/质量工程师，在 CygnusX 仓库执行「记忆质量修前基线测量」。
遵守任务书 §0 总纪律（尤其 T0-4：本阶段模型调用量最大，先把 25 案例 × 预计会话轮数 ×
每轮调用数 的估算交给用户批准）。前置：阶段 0–2 通过；仓库内存在验收协议
docs/info/26.10.20/CygnusX记忆质量验收集-2026-10-20.md（若文件名有出入，grep
"验收" 或 "25" 定位）。

本阶段只测量、不调参：所有配置使用"灰度拟定默认值"（v2 开启、其余开关维持默认，
逐项列出快照），目标是建立修前基线，为后续开关与参数决策提供对照。

任务：
A. 协议落地
   1. 通读验收协议的 25 个案例，把每个案例转成可脚本化执行的会话序列（合成用户、
      固定脚本消息、真实 Chat 链路、真实 settle）；无法脚本化的案例单列清单并说明
      原因（不得偷偷改成可脚本化的近似版）。
   2. 每个案例记录：注入预算实际分布（块/情节/事实三段各自字节数与条目数）、
      被选中事实 ID 与复合得分、settle 产出物、模型调用次数、用户可见响应中
      记忆使用的正误（按协议判定标准人工+规则混合判定，标注判定方式）。
B. 三个结构性观察项（与 25 案例并行采集）
   1. 事实段饥饿：统计 25 案例中普通事实段注入字节数分布——块+情节占满导致事实段
      为 0 的案例占比（预算 6000/2800/3200 的结构性问题，只测不改）。
   2. 重要性分布：导出本阶段所有由抽取模型打出的 importance 直方图，检查是否堆在
      5–8（自评膨胀假设）；同时统计满足冷归档条件（importance≤3）的事实占比——
      验证"冷归档在实践中是否近似死代码"。
   3. 时间衰减敏感性：取 3 条内容相近、age 分别为 7/35/90 天的种子事实，固定查询
      记录复合得分排序，验证 lambda=0.02（半衰期约 35 天）对项目级事实的实际影响。
C. 输出基线报告
   每案例：通过/失败/部分 + 证据；三观察项单独成节；汇总表给出 25 案例通过率、
   模型调用总量与成本；最后给"建议优先验证的开关/参数"清单（只列项，不实施）。

交付：阶段5报告（§10 格式）+ 原始数据（JSON，隐去正文只留 ID/分数/字节数）。
```

**阶段 5 验收 checklist**

| # | 操作 | 期望现象 | 不通过时的处理 |
| --- | --- | --- | --- |
| 5-1 | 用户手测：抽 3 个案例人工核对判定 | 报告判定与你的人工判定一致 | 判定口径不一致 → 与我核对后再定稿 |
| 5-2 | Codex 执行：三观察项数据齐全 | 直方图、饥饿占比、衰减排序均有数据 | 缺项 → 补采，不进入调参讨论 |
| 5-3 | 用户确认：调用量与批准估算偏差 | 偏差 <20% | 超支 → 说明原因，后续阶段重新报批 |

---

## 10. 报告交付格式（Codex 每阶段必须遵守）

每阶段一份 `docs/info/26.10.xx/CygnusX测试报告-阶段N-名称.md`，结构固定：

1. **环境快照**：PG/pgvector/Redis 版本、Alembic head revision、本阶段 Flags 快照
  （只列开关名与取值，不含密钥）、测试库名。
2. **测试矩阵**：｜用例编号｜层级（服务/工具/REST/任务）｜结果（通过/失败/受阻）｜
   证据（命令 + 关键输出摘录 + 文件：行号 / DB 查询 + 关键字段）｜——矩阵不许缺格。
3. **失败与受阻清单**：按【阻断阶段目标】【阻断灰度准入】【体验不一致】【建议优化】
   分级，每条附证据；**只记录，不修复**。
4. **模型调用与成本**：本阶段各类模型调用次数、token 估算、与批准预算的偏差。
5. **下一阶段准入建议**：Codex 自己的判断，最终准入权在用户。

---

## 11. 用户验收对照表（总表，各阶段 checklist 的汇总视角）

| 验收项 | 谁执行 | 操作 | 期望现象 | 不通过路径 |
| --- | --- | --- | --- | --- |
| 只测不改红线 | 用户 | 每阶段后 `git status --short` + `git diff --stat` | 只有新增文件；src/、frontend/、已有迁移零改动 | 要求还原并说明；不改不进入下阶段 |
| 迁移链完整 | 用户 | 对照报告 revision 列表与 `alembic history` | 11+3 个 revision 在链、单 head | 拿回给我（本对话）核对 |
| 降级保护 | Codex+用户抽查 | 4 个保护用例 + 抽查 1 个（附拒绝原因证据） | 拒绝降级且零数据丢失 | 【阻断灰度准入】 |
| 集成测试真实运行 | Codex | 原 skip 用例配合规命名 DSN 后全跑 | 全部真实执行（无 skip），附 pytest -v | 失败项只记录，拿回核对 |
| settle 事务性 | Codex | §6 A 组全部用例 | 六产物同事务、失败零结算 | 【阻断灰度准入】 |
| 整理锁/预算/回滚 | Codex | §6 C 组 | 互斥、预占、冲突拒绝 | 【阻断灰度准入】 |
| 隔离零泄露 | Codex+用户抽查 | §7 矩阵 + 抽查跨用户用例 | 所有"不应可见"零泄露 | 【阻断灰度准入】最高级 |
| KB 权限矩阵 | Codex+用户手测 | §8 C.4 + 页面手测一篇 | 8 格全对 | 【阻断灰度准入】 |
| 25 案例基线 | 双方 | §9 协议落地 + 抽 3 例人工核对 | 数据齐全、判定一致 | 判定分歧拿回核对 |
| 证据可信 | 用户 | 每阶段随机抽 1–2 条命令重跑 | 与报告一致 | 该阶段证据整体重交 |

---

## 12. 拿回报告后的核对 loop（用户侧流程）

1. 每阶段拿回报告后，把报告发回本对话，我按 §10 格式逐项核对：确认的问题 /
   保留意见 / 行动顺序建议，并区分"设计如此"（如回执检查前可能重复调用抽取模型）
   与"真缺陷"，不把刻意约束当待办。
2. 出现【阻断灰度准入】项时：先不修，回本对话对齐根因与修复方案，再决定是否
   进入修复提示词阶段（修复提示词另行生成，强制端到端验收，不接受只跑单测）。
3. 全部阶段通过后，本任务书 §2.3 的"未实现"清单才进入下一轮建设讨论
  （载体终局 / 程序性记忆 / 检索内核统一）。

---

## 附录 A：关键代码与配置锚点速查

- 服务层：`src/cygnusx/application/services/agent_memory_service.py`、`memory_runtime_policy.py`、`agent_memory_tool_service.py`、`memory_residual_service.py`、`memory_embedding_service.py`
- 基础设施：`src/cygnusx/infrastructure/memory/fact_store.py`、`consolidation.py`；`infrastructure/celery_app/tasks/memory.py`、`celery.py`
- ORM：`src/cygnusx/infrastructure/database/models/agent_memory.py`、`knowledge_*.py`
- API：`api/v1/users.py`、`admin/users.py`、`docs.py`、`admin/knowledge_bases.py`
- 前端：`frontend/src/components/agent-workspace/MemoryManagementPanel.vue`、`views/AdminMemoryView.vue`、`views/KnowledgeView.vue`、`components/admin/KnowledgeResourceTab.vue`
- 脚本：`scripts/check_schema_drift.py`、`check_env_example_drift.py`、`inspect_memory_baseline.py`、`backfill_memory_embeddings.py`、`rollback_memory_consolidation.py`、`import_scseq_knowledge.py`
- 工具授权：`data/ai/tools/memory.yaml`
- 已有验证资产：`tests/integration/test_memory_focus_postgres.py`（真实 PG 用例）、`docs/info/26.10.20/CygnusX记忆质量验收集-2026-10-20.md`（25 案例协议）、`docs/adr/0001-memory-storage.md`

## 附录 B：Flags 快照清单（阶段报告逐项列出取值）

memory_v2_enabled / memory_focus_per_project_enabled / memory_forget_residual_scan_enabled(+limit) / memory_embedding_model_filter_enabled / memory_hybrid_retrieval_enabled(+vector_limit/keyword_limit/rrf_k/min_similarity) / memory_embedding_coverage_enabled(+interval) / agent_memory_embedding_model / memory_extraction_model / memory_settle_min_new_messages / max_messages / max_chars / memory_settle_tail_enabled(+idle/tail_min) / memory_settle_candidate_limit / memory_prompt_max_bytes / blocks_max_bytes / episode_max_bytes / memory_fact_time_decay_lambda / memory_importance_weight / recall_weight / recall_boost_scale / memory_recall_tracking_enabled / recall_batch_ttl_days / purge_limit / memory_write_arbitration_enabled / memory_consolidation_enabled(+max_calls/max_groups/lookback/candidate/max_chars/min_episodes/timeout) / memory_cold_after_days / max_importance / batch_limit / KNOWLEDGE_AUTO_REINDEX_ENABLED

## 附录 C：指标名速查（证据采集用）

memory.runtime_gate_degraded / memory.embedding_model_mismatch_rows / embedding_model_coverage / embedding_coverage_sample_timestamp_seconds / memory.embedding_backfill_rows / memory.embedding_outcomes / memory.settle_failed / settle_succeeded / settle_skipped / settle_tail_enqueued / memory.recall_batches_purged / memory.l4_inject_degraded / memory.inject_units_omitted / memory.inject_latency_ms / memory.recall_enqueue_failed / memory.forget_residual_hits / actions / scans / memory.write_arbitration_calls / failed / memory.consolidation_groups / memory.focus_operations

---

## 13. 核对记录（本对话侧，逐阶段追加）

### 阶段 0 报告核对（2026-10-20，报告：《CygnusX测试报告-阶段0-环境基线》）

**判定：阶段 0 通过（附一项口径修订），准入阶段 1。** 报告自述"受阻"，核对后不采纳——
其"阻断阶段目标"项实为任务书口径错误，且实质验收目标已由 contract 用例的通过证据覆盖。
报告格式符合 §10，纪律执行良好（如实报失败而非悄悄换库名，值得保持）。

**确认的问题：**

1. **任务书口径错误（已就地修订 §1/§4）**：任务书指定单一 `cygnusx_memtest` 库通跑集成测试，
   与仓库既有"按域库名前缀门禁"（`memory_acceptance_test` / `project_export_test` /
   `report_test`）冲突。该门禁是刻意的防误操作护栏，判定为"设计如此"——**不改测试文件，
   改任务书**。Codex 的"建议优化"中"把 memtest 加入测试允许名单"一条不予采纳。
2. **仓库既有测试基建债（不阻断记忆验证，排入杂项，本任务书不跟踪修复）**：
   report 集成测试缺 psycopg2；`test_phase0b_redis.py` 只认 host redis-server/Unix socket；
   `test_agent_service.py` 6 项因 asyncpg 跨 event loop 自我 skip。
   三项均与记忆/知识库链路无关，未来单独开测试基建小任务处理。

**保留意见（Codex 补证据，不需重跑迁移）：**

1. 0-B3a-d 四个降级拒绝只有"退出码 1 + 行数不变"：需补每个用例的拒绝原因
   （异常类名 + 错误信息关键行 + 对应迁移文件:行号），证明拒绝来自预期保护逻辑
   而非 incidental 报错。（已就地补进 §4 B.3 提示词）
2. 0-C1/C2-contract 各只有 "1 passed"：需补 `pytest -v` 输出与通过测试函数内的
   断言点清单，证明迁移 / 8 路并发 / 拒绝降级 / 往返（focus 文件）与
   HNSW / model filter / backfill / EXPLAIN（embedding 文件）都在执行路径内。
   （已就地补进 §4 C.2 提示词）
3. 0-1 的只测不改证据用 `git diff`（只覆盖已跟踪文件）：用户手测
   `git status --short` 一次，复核未跟踪文件仅为 Compose/初始化脚本/种子脚本/报告四类。
   （§11 总表已同步改为 `git status --short`）

**阶段 1 准入前提：**

- 用户提供真实 `AGENT_MEMORY_EMBEDDING_MODEL` 密钥（写入 `.env.test`，不进 git）；
- Codex 先交阶段 1 预估调用量，用户书面批准（T0-4）；
- 注意：0-C2-contract 已在真实 PG 上跑通 model filter / backfill / EXPLAIN 的**正确性**
  路径，阶段 1-D 是**性能口径**（≥1 万合成向量行、P50/P95、执行计划证据），
  不重复、也不可省略（已就地补进 §5 背景说明）。

### 阶段 0 补证据 + 阶段 1 合并执行授权（2026-10-20，用户指示）

用户指示"补证据 + 阶段 1"一次完成。T0-4 对本阶段的一次性修订：以**预算上限预授权**替代
"估算→批准→执行"两轮往返——真实 embedding 调用上限 150 次（仅限
`AGENT_MEMORY_EMBEDDING_MODEL`，密钥由用户预先写入 `.env.test`），超限即停并在报告
标注受阻；抽取模型（`memory_extraction_model`）的任何调用不在本次授权范围。
**阶段 2、5 仍按原 T0-4 流程（先估算、书面批准、再执行）。**

合并提示词要点（已交付用户，聊天正文）：任务一按 §13 保留意见 1/2 补阶段 0 报告附录；
任务二按 §5 完整执行，执行顺序先零调用项（dry-run / 覆盖率 / 随机向量装载）后真实
调用项，报告附调用量台账（逐子任务次数、token 估算、与 150 上限对照）；
密钥缺失或不可用时任务二整体标受阻，不得自行寻找其他密钥来源。
