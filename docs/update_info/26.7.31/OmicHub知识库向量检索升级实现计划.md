
# OmicHub 知识库向量检索升级 · 实现计划（供 Claude Code 执行）

> **用途**：指导 Claude Code 将知识库 AI 检索从「子串匹配」升级为「chunk 化 + pgvector 混合检索」。
> **最后更新**：2026-07-31
> **前置阅读**：`OmicHub 知识库（Knowledge Base）实现架构` 文档（了解现有数据模型与检索链路）。
> **执行方式**：按阶段顺序执行，每阶段完成后人工验收通过再进入下一阶段。每个阶段的提示词块可直接整段粘贴给 Claude Code。

---

## 0. 背景与目标

### 现状

AI 助手通过内置 function tool `knowledge_search` 检索知识库：SQL 取前 500 篇已发布文档（`kb_documents JOIN doc_revisions ON current_rev`），Python 内存中对「标题 + 分类 + 正文」做大小写不敏感子串匹配，命中后截取关键词前后约 600 字符摘录返回。**不是向量检索，不走 MCP。**

### 四条已知局限（本次升级要解决的问题）

| # | 局限 | 影响 |
|---|---|---|
| 1 | 子串匹配无语义理解 | 同义词/中英文不互通："线粒体比例" ≠ "mitochondrial percentage"，"去批次" ≠ "batch correction" |
| 2 | 500 篇扫描上限 | 文档量再大时新文档可能进不了扫描窗口 |
| 3 | 600 字符摘录 | LLM 只能看到片段，上下文不全 |
| 4 | 关键词由 LLM 生成 | query 取得差时召回为零 |

### 目标

- 单细胞/生信问题支持**语义检索**，中英文、同义词可互通；
- 检索粒度从「整篇文档」细化到「**chunk（语义块）**」，LLM 看到的是完整语义片段而非 600 字符截断；
- 保留关键词匹配能力（精确术语、参数值仍走子串），两路召回合并；
- **检索失败可回退**：配置开关一键切回现有子串匹配。

### 明确不做的事（防止实施时跑偏）

- **不引入独立向量数据库产品**（不上 Milvus/Qdrant/Chroma），用 PostgreSQL 的 pgvector 扩展；
- **不走 MCP**：检索仍是平台内置 function tool，MCP 留给未来接公共数据库（GEO/PubMed）时再评估；
- **不改工具 schema**：`KNOWLEDGE_SEARCH_TOOL` 的参数保持 `query` + `limit` 不变，LLM 侧无感；
- **不动分发链路与前端**：`chat_service.py` 的工具挂载/分发、知识库页面、三开关语义（show_in_lab / ai_searchable / is_enabled）均不改；
- **不重构无关代码**：只动检索取数与匹配逻辑、导入脚本、审核流钩子三处。

---

## 1. 总体设计决策（ADR）

| # | 决策 | 理由 |
|---|---|---|
| D1 | 用 **pgvector** 而非独立向量库 | 数据已全在 PostgreSQL；预估 chunk 量约 2000（209 篇 × 平均 10 块），精确搜索毫秒级，无需新组件与额外运维 |
| D2 | **chunk 化优先**于向量化 | 现痛点"上下文不全"的根源是整篇匹配 + 600 字符截断；切块后向量与关键词两路都受益 |
| D3 | **混合检索**（向量召回 ∪ 关键词命中，RRF 合并） | 向量擅长语义，但对精确术语（`DoubletFinder`、`nFeature_RNA > 200`）子串更准，两路互补 |
| D4 | 检索仍是内置 function tool，**不引入 MCP** | 链路短、复用现有 ai_searchable 开关与 URL 生成逻辑；MCP 是跨平台/多数据源时的扩展点，本期用不上 |
| D5 | Embedding 默认 **bge-m3**（本地 fastembed / sentence-transformers），通过配置可切换 OpenAI 兼容 API | 语料为中英混合生医笔记，bge-m3 中英双语、1024 维、支持 8192 token；抽象 Provider 接口避免锁定 |
| D6 | 检索模式配置开关 `KB_SEARCH_MODE`：`hybrid`（默认）/ `vector` / `keyword` | 出问题一键回退到现有 keyword 行为，降低上线风险 |

---

## 2. 数据模型变更

### 2.1 新增表 `kb_chunks`

文件：`src/omichub/infrastructure/database/models/knowledge_chunk.py`（新建）

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | BigInteger PK 自增 | |
| `document_id` | String FK → kb_documents.doc_id，**ON DELETE CASCADE**，建索引 | 所属文档 |
| `chunk_index` | Integer | 文档内块序号（0 起） |
| `section_path` | String(512) | 章节路径，如 `质控 > 线粒体过滤`（来自 Markdown 标题层级） |
| `content` | Text | 块正文（含标题前缀，见切块策略） |
| `content_hash` | String(32) | md5(content)，用于变更检测跳过重建 |
| `embedding` | `Vector(1024)`（pgvector，维度随配置） | bge-m3 为 1024 维 |
| `updated_at` | DateTime | |

约束：`(document_id, chunk_index)` 唯一。`kb_documents` 增加关系 `chunks`（cascade delete-orphan）。

### 2.2 alembic 迁移

新建迁移（接在 `o3p4q5r6s7t8_add_knowledge_bases` 之后）：

1. `CREATE EXTENSION IF NOT EXISTS vector;`（注意：生产 PG 若为非超级用户/RDS，需提前确认 pgvector 扩展可用，见 §6 风险）；
2. 建 `kb_chunks` 表（含 embedding 列、两个索引）；
3. **不建向量索引**：chunk 量 < 5 万时精确检索足够快；将来量上来再补 `HNSW (embedding vector_cosine_ops)`。

### 2.3 配置项（加入现有配置体系）

| 配置 | 缺省 | 说明 |
|---|---|---|
| `KB_SEARCH_MODE` | `hybrid` | `hybrid` / `vector` / `keyword` |
| `KB_EMBEDDING_PROVIDER` | `fastembed` | `fastembed` / `openai_compatible` |
| `KB_EMBEDDING_MODEL` | `BAAI/bge-m3` | 模型名 |
| `KB_EMBEDDING_DIM` | `1024` | 向量维度，建表与运行时校验用 |
| `KB_EMBEDDING_API_BASE` / `KB_EMBEDDING_API_KEY` | 空 | provider 为 openai_compatible 时使用 |

---

## 3. 分阶段实现

### 阶段 1：基础设施（pgvector 扩展 + kb_chunks 表 + Embedding 服务封装）

**改动点**：

- 新建 `models/knowledge_chunk.py`（表结构见 §2.1），在 `knowledge_document.py` 加 `chunks` 关系；
- 新建 alembic 迁移（§2.2）；
- 新建 `application/services/embedding_service.py`：
  - `EmbeddingProvider` 抽象接口：`embed_texts(list[str]) -> list[list[float]]`、`embed_query(str) -> list[float]`（bge 系模型 query 侧有专用 instruction 前缀，实现里处理）；
  - 两个实现：`FastembedProvider`（默认，`pip install fastembed`，模型 `BAAI/bge-m3`）与 `OpenAICompatibleProvider`（httpx 调 `/embeddings`）；
  - 工厂函数按 `KB_EMBEDDING_PROVIDER` 配置返回实例，**进程级单例缓存**（模型加载很贵）；
  - embedding 失败时抛 `EmbeddingUnavailableError`，调用方捕获后按 §阶段 3 降级为 keyword。

**验收**：

- [ ] 迁移执行成功，`\d kb_chunks` 结构正确，扩展已启用（`SELECT * FROM pg_extension WHERE extname='vector'`）
- [ ] 单测：embedding_service 对 3 条中英文文本产出 1024 维向量，同实例二次调用命中缓存不重复加载模型
- [ ] 现有功能全部不受影响（未接检索链路）

**提示词块**（粘给 Claude Code）：

```text
你是一名资深 Python 后端工程师。项目：OmicHub，FastAPI + SQLAlchemy + PostgreSQL + alembic，代码在 src/omichub/。

任务：为知识库向量检索升级搭建基础设施（第一阶段，不接检索链路）。

先阅读以下现有代码再动手，严格复用项目既有模式（模型声明方式、迁移写法、配置读取方式），禁止重构无关代码：
- src/omichub/infrastructure/database/models/knowledge_base.py、knowledge_document.py、knowledge_revision.py
- alembic/versions/o3p4q5r6s7t8_add_knowledge_bases.py（最近一次迁移，新迁移接在它后面）
- 项目现有的配置读取方式（找到 settings/config 模块）

实现内容：
1. 新建 models/knowledge_chunk.py，表 kb_chunks：id 自增主键；document_id 外键指向 kb_documents.doc_id 且 ON DELETE CASCADE；chunk_index int；section_path varchar(512)；content text；content_hash varchar(32)；embedding 用 pgvector 的 Vector 类型，维度从配置 KB_EMBEDDING_DIM（缺省 1024）读取；updated_at。(document_id, chunk_index) 唯一约束。knowledge_document.py 加 chunks 关系，cascade delete-orphan。
2. 新建 alembic 迁移：CREATE EXTENSION IF NOT EXISTS vector（用 op.execute）；建 kb_chunks 表；不建向量索引。downgrade 完整可回滚。
3. 新建 application/services/embedding_service.py：
   - EmbeddingProvider 抽象基类：embed_texts(texts: list[str]) -> list[list[float]]、embed_query(text: str) -> list[float]；
   - FastembedProvider：fastembed 库加载 BAAI/bge-m3（模型名由配置 KB_EMBEDDING_MODEL 控制）；embed_query 使用 bge-m3 推荐的 query instruction 前缀；
   - OpenAICompatibleProvider：httpx POST {KB_EMBEDDING_API_BASE}/embeddings，header 带 KB_EMBEDDING_API_KEY；
   - get_embedding_provider() 工厂，进程级单例（functools.lru_cache）；
   - 定义 EmbeddingUnavailableError，任何 provider 内部异常包装为该异常抛出。
4. 配置项加入项目配置：KB_SEARCH_MODE（缺省 hybrid）、KB_EMBEDDING_PROVIDER（缺省 fastembed）、KB_EMBEDDING_MODEL（缺省 BAAI/bge-m3）、KB_EMBEDDING_DIM（缺省 1024）、KB_EMBEDDING_API_BASE、KB_EMBEDDING_API_KEY。
5. 依赖写入项目的依赖声明文件（fastembed；pgvector 的 SQLAlchemy 支持包 pgvector）。
6. 写 pytest 单测：FastembedProvider 对中英文各一句产出 1024 维向量；工厂单例语义；维度与配置不一致时报错。

验收：alembic upgrade head 成功且 downgrade -1 可回滚；pytest 新增用例通过；现有测试不红。完成后报告改动文件清单。
```

---

### 阶段 2：切块与索引构建（chunker + 导入脚本改造 + 存量回填）

**改动点**：

- 新建 `application/services/knowledge_chunker.py`——Markdown 切块器，策略：
  1. 按标题行（`#{1,4}`）切分为 section，维护标题层级栈生成 `section_path`（如 `质控 > 线粒体过滤`）；
  2. 目标块长 **800 字符**，硬上限 **1200**：section 超长时按段落（空行）二级切分，仍超长按句号硬切；
  3. 相邻块 **overlap 100 字符**（仅段落级切分产生的块之间）；
  4. 代码块（```围栏）不切半，整体归入当前块；
  5. **入库 content 加前缀**：`【文档标题 > section_path】\n{正文}`——让 embedding 带上文档与章节上下文；
  6. 纯图片/空块（去空白后 < 30 字符）丢弃。
- 新建 `application/services/knowledge_indexer.py`——`reindex_document(doc)`：删除旧 chunks → 切块 → embed_texts → 写入；`content_hash` 未变的块保留原 embedding 不重复计算（增量更新）。
- 改 `scripts/import_scseq_knowledge.py`：导入/更新文档后调用 `reindex_document`；**embedding 服务不可用时打印警告并继续**（文档入库不阻塞，检索侧会降级）。
- 新建 `scripts/reindex_knowledge.py`：存量回填，支持 `--kb scseq`、`--doc <doc_id>`、`--force`（忽略 hash 全量重建），带进度输出与失败汇总。

**验收**：

- [ ] `python scripts/reindex_knowledge.py --kb scseq` 跑完，209 篇全部产出 chunks，失败 0
- [ ] 抽查 3 篇：chunks 的 section_path 正确、无代码块被切半、块长均在 1200 内（除单一代码块例外）
- [ ] 重复执行回填脚本，无内容变化的文档 embedding 不重算（日志中跳过计数 = 文档数）

**提示词块**：

```text
你是一名资深 Python 后端工程师。项目：OmicHub，FastAPI + SQLAlchemy + PostgreSQL（pgvector）。阶段 1 已完成：kb_chunks 表、embedding_service（get_embedding_provider / EmbeddingUnavailableError）已就绪。

任务：实现知识库 Markdown 切块与索引构建（第二阶段，不接检索链路）。

先阅读再动手，复用既有模式，禁止重构无关代码：
- scripts/import_scseq_knowledge.py（现有导入流程，幂等逻辑在里面）
- src/omichub/infrastructure/database/models/knowledge_chunk.py、knowledge_document.py
- src/omichub/application/services/embedding_service.py

实现内容：
1. 新建 application/services/knowledge_chunker.py，函数 chunk_markdown(title: str, markdown: str) -> list[Chunk]（Chunk 为 dataclass：chunk_index/section_path/content/content_hash）：
   - 按 Markdown 标题行（# 到 ####）切 section，用栈维护层级得到 section_path（如 "质控 > 线粒体过滤"），正文在标题前的部分 section_path 为空串；
   - 目标块长 800 字符、硬上限 1200：section 超限先按空行段落二级切，单段落仍超限按 "。"/". " 硬切；段落级切分产生的相邻块保留 100 字符 overlap；
   - 围栏代码块（```...```）视为原子，绝不从中间切开，允许其所在块超 1200；
   - 入库 content 加前缀："【{title} > {section_path}】\n"（section_path 为空时用 "【{title}】\n"）；
   - 去空白后不足 30 字符的块丢弃；content_hash = md5(content)。
2. 新建 application/services/knowledge_indexer.py：
   - reindex_document(session, doc) -> 统计信息：读出 doc 的 current_rev 正文 → chunk_markdown → 与库内现有 chunks 按 content_hash 对比：未变的块保留原 embedding 直接复用，新增/变化的块批量 embed_texts，删除消失的块，重排 chunk_index；
   - embedding_service 抛 EmbeddingUnavailableError 时：向上抛出 IndexUnavailableError（自定义），由调用方决定降级。
3. 改 scripts/import_scseq_knowledge.py：文档写入（新建或更新）后调用 reindex_document；捕获 IndexUnavailableError 打印警告继续，不阻塞导入。
4. 新建 scripts/reindex_knowledge.py（存量回填）：参数 --kb（按知识库过滤）、--doc（单篇）、--force（忽略 hash 全量重建）；逐篇输出进度，结尾汇总成功/跳过/失败数；单篇失败不中断整体。
5. pytest 单测：chunker 对含多级标题 + 长代码块 + 超长 section 的样本输出符合上述全部规则；indexer 增量语义（改一段只重算变化的块）。

验收：python scripts/reindex_knowledge.py --kb scseq 全量跑完失败为 0；重复跑第二次全部跳过；抽查块质量；pytest 通过。完成后报告改动文件清单与回填统计。
```

---

### 阶段 3：检索逻辑升级（hybrid 召回替换 `_knowledge_search` 内部实现）

**改动点**（只动 `studio_tools.py` 的 `_knowledge_search` 内部，函数签名、返回结构、工具 schema、分发链路一律不变）：

- 返回结构保持 `{doc_id, title, category, excerpt, url}`；`excerpt` 改为命中 chunk 的 content（完整语义块，不再是 600 字符截断）；**同一文档最多返回 2 个 chunk**，避免单篇挤占 limit 名额。
- `KB_SEARCH_MODE` 三模式：
  - `keyword`：现有子串逻辑原样保留（回退路径）；
  - `vector`：query 经 `embed_query` 向量化 → `kb_chunks JOIN kb_documents JOIN doc_revisions ON current_rev`（过滤条件与现有 SQL 完全一致：status=1 + 知识库 ai_searchable/is_enabled + kb_id IS NULL 兼容）→ `embedding <=> query_vec` 余弦距离升序取 top 20 → 相似度 < 0.3 的丢弃（余弦相似度 = 1 - 距离）；
  - `hybrid`（默认）：向量路 top 20 + 关键词路（对 chunks 的 content 做子串匹配）top 20，**RRF 合并**（k=60：`score = Σ 1/(60+rank)`），取合并后 top N，再按"每文档 ≤ 2 chunk"截断到 limit 条。
- **降级**：`embed_query` 抛 `EmbeddingUnavailableError` → 记 warning 日志，自动落到 keyword 路径（本次请求内），不报错给用户。
- 结果附带检索元信息（`search_mode` 实际用值、`vector_hits`/`keyword_hits` 数）写进 debug 日志，便于上线后观测。

**验收**：

- [ ] 三模式均可用配置切换且行为符合定义
- [ ] 语义用例（见 §4）全部命中预期文档
- [ ] 停掉 embedding 服务后检索自动降级 keyword，日志有 warning，用户侧不报错
- [ ] 工具 schema、chat 分发、知识库页面三处零改动（git diff 确认）

**提示词块**：

```text
你是一名资深 Python 后端工程师。项目：OmicHub，FastAPI + SQLAlchemy + PostgreSQL（pgvector）。阶段 1/2 已完成：kb_chunks 已有数据，embedding_service、KB_SEARCH_MODE 配置可用。

任务：升级 AI 助手知识库检索为混合检索（第三阶段）。

硬性约束（违反即返工）：
- 只改 src/omichub/application/services/studio_tools.py 的 _knowledge_search 函数内部实现（约 795-852 行）；
- KNOWLEDGE_SEARCH_TOOL 的 schema（query + limit 参数）、chat_service.py 的挂载/分发/系统提示、前端、知识库页面、三开关过滤逻辑一律不动；
- 现有 SQL 过滤条件原样保留：kb_documents JOIN doc_revisions ON current_rev、status=1、知识库 ai_searchable=true AND is_enabled=true、kb_id IS NULL 向后兼容。

实现内容：
1. _knowledge_search 按配置 KB_SEARCH_MODE 分三条路径：
   - keyword：现有子串匹配逻辑原样搬入，行为与现状完全一致；
   - vector：embedding_service.embed_query(query) 向量化 → 查 kb_chunks JOIN kb_documents JOIN doc_revisions ON current_rev（过滤条件同上）→ ORDER BY embedding <=> :query_vec 余弦距离取 top 20 → 丢弃余弦相似度 < 0.3 的结果；
   - hybrid（默认）：vector 路 top 20 与 keyword 路（对 kb_chunks.content 做大小写不敏感子串匹配）top 20 做 RRF 合并，k=60，score = 1/(60+rank) 求和，按总分降序；
2. 统一出口：从合并结果中按"同一 doc_id 最多 2 个 chunk"截断到 limit 条；每条返回 {doc_id, title, category, excerpt, url: /knowledge/{doc_id}}，excerpt = 命中 chunk 的完整 content（不再做 600 字符截断）；
3. 降级：embed_query 抛 EmbeddingUnavailableError 时记 warning 日志并自动落到 keyword 路径完成本次请求，不向用户报错；
4. debug 日志输出 search_mode（实际生效值）、vector_hits、keyword_hits、final_count；
5. pytest 单测（用内存 SQLite + 假 embedding provider 或 mock）：三模式行为、RRF 排序正确性、每文档 2 块截断、EmbeddingUnavailableError 降级路径。

验收：pytest 通过；git diff 确认改动仅限 studio_tools.py（+ 测试文件）；本地起服务用阶段 4 文档里的测试用例手动验证语义召回。完成后报告改动文件清单。
```

---

### 阶段 4：变更同步（审核流钩子 + 编辑重建索引）

**改动点**：

- 找到审核通过逻辑（`docs_service.py` 中 pending_rev 切换为 current_rev 的位置）与 `PUT /docs/knowledge/{doc_id}` 直接发布路径：在 **current_rev 发生切换后**调用 `reindex_document`；
- 索引失败（`IndexUnavailableError`）不阻塞审核/发布主流程，记 error 日志 + 可选写入 `kb_issues` 类型备注，由回填脚本兜底（提供 `--stale` 参数重建「有文档无 chunks 或 chunks 过期」的文档）；
- 文档删除（若有此操作）依赖 cascade 自动清 chunks，验证即可。

**验收**：

- [ ] 在线编辑一篇文档并审核通过后，库内 chunks 已更新为新正文内容
- [ ] embedding 服务停掉时审核流程正常完成，日志有 error，`--stale` 回填可补齐
- [ ] 删除文档后其 chunks 级联消失

**提示词块**：

```text
你是一名资深 Python 后端工程师。项目：OmicHub。阶段 1-3 已完成（kb_chunks、reindex_document、混合检索可用）。

任务：接上索引变更同步（第四阶段）。

先阅读 src/omichub/application/services/docs_service.py，找到两处「current_rev 生效」的位置：审核通过（pending_rev 切换为 current_rev）与直接发布（PUT /docs/knowledge/{doc_id} 无审核路径，若存在）。

实现内容：
1. 在上述两处 current_rev 生效后调用 knowledge_indexer.reindex_document；
2. 捕获 IndexUnavailableError：记 error 日志（含 doc_id），不阻塞审核/发布主流程，不向前端报错；
3. scripts/reindex_knowledge.py 增加 --stale 模式：扫描"文档存在但无 chunks"或"文档 current_rev 对应 content 与 chunks 的 content_hash 对不上"的文档并重建，供兜底与定时任务使用；
4. 验证文档删除时 chunks 级联清理（cascade 已在阶段 1 配好，写个集成测试确认）；
5. pytest：审核通过后 chunks 更新；索引服务不可用时审核仍成功且有 error 日志；--stale 能找出并补齐缺索引文档。

验收：pytest 通过；手动走一遍"编辑→审核→检索命中新内容"全流程。完成后报告改动文件清单。
```

---

### 阶段 5：系统提示微调与上线观测

**改动点**：

- `KNOWLEDGE_SEARCH_SYSTEM_PROMPT_SUFFIX`（`chat_service.py:337-341`）文案强化：明确"凡涉及 scRNA-seq/生信流程、参数阈值、实验经验、平台使用的问题，**必须先调用 knowledge_search 再作答**；检索结果为空时如实说明并基于自身知识回答，注明非来自知识库"。（只改文案，不改挂载逻辑）
- 上线后观察 1-2 周：从 debug 日志统计 `vector_hits=0 且 keyword_hits=0` 的真实用户 query，用于调整切块参数或补充语料。

**提示词块**：

```text
项目：OmicHub。任务：微调知识库检索的系统提示文案（唯一改动）。

改 src/omichub/application/services/chat_service.py 中 KNOWLEDGE_SEARCH_SYSTEM_PROMPT_SUFFIX（约 337-341 行）的文案为以下含义（可润色，保持简洁）：凡涉及 scRNA-seq/生信分析流程、参数阈值、实验经验、平台使用的问题，必须先调用 knowledge_search 检索再作答；检索结果为空时如实告知用户"知识库未找到相关内容"，再基于自身知识回答并注明非来自知识库；禁止编造知识库中不存在的文档或链接。

只改这个常量字符串，其他一律不动。完成后展示 diff。
```

---

## 4. 验收测试用例（阶段 3 完成后统一跑）

| # | 用户 query | 预期 |
|---|---|---|
| 1 | "线粒体比例高的细胞怎么过滤" | 命中 QC/质控相关笔记（即使正文只写 mitochondrial / mt.percent） |
| 2 | "DoubletFinder 的 pK 怎么选" | 命中双联体去除相关笔记（关键词路） |
| 3 | "多样本整合去批次用什么方法" | 命中 Harmony / integration 相关笔记（语义路） |
| 4 | "nFeature_RNA 阈值一般设多少" | 命中质控阈值笔记（关键词路，精确术语） |
| 5 | "怎么给细胞注释 marker" | 命中细胞注释笔记（语义路，"注释" 与 "annotation" 互通） |
| 6 | "今天天气怎么样" | 不调用工具或返回空，LLM 如实说明与知识库无关 |

---

## 5. 上线步骤

1. 部署代码 → `alembic upgrade head`（确认 pgvector 扩展就绪）；
2. `pip install` 新依赖（fastembed 首次运行会下载 bge-m3 模型约 2GB，**生产环境提前预下载或挂模型缓存卷**）；
3. `python scripts/reindex_knowledge.py --force` 全量建索引；
4. 默认 `KB_SEARCH_MODE=hybrid` 灰度；观察 debug 日志；
5. 异常时 `KB_SEARCH_MODE=keyword` 即刻回退到现状，无需回滚代码。

## 6. 风险与回退

| 风险 | 应对 |
|---|---|
| 生产 PG 无 pgvector 扩展权限（RDS 需参数组开启 / 非超户） | 部署前在目标库执行 `CREATE EXTENSION vector` 验证；不可用时保持 `KB_SEARCH_MODE=keyword`，迁移暂不上 |
| bge-m3 模型下载/加载慢（约 2GB） | Docker 构建期预下载或挂载模型缓存；embedding 全程失败时检索自动降级 keyword |
| 切块质量不佳（块太碎/跨主题） | 调 chunker 参数（800/1200/100）后用 `--force` 重建；无需改表 |
| 向量路相似度阈值 0.3 误杀 | 观测 `vector_hits` 分布后微调阈值 |
| 整体回退 | `KB_SEARCH_MODE=keyword` 一键回到现有子串匹配；kb_chunks 表保留无副作用 |

## 7. 关键文件清单（执行前必读）

| 层 | 文件 |
|---|---|
| 现有检索 | `application/services/studio_tools.py`（`_knowledge_search`，约 795-852 行） |
| 工具定义/分发 | `application/services/chat_service.py`（schema 249-274、系统提示 337-341、分发 2305/2642）——**只读，不改** |
| 导入 | `scripts/import_scseq_knowledge.py` |
| 模型 | `infrastructure/database/models/knowledge_*.py` |
| 迁移 | `alembic/versions/o3p4q5r6s7t8_add_knowledge_bases.py`（新迁移接其后） |
| 审核流 | `application/services/docs_service.py`（current_rev 切换处） |
| 新建 | `models/knowledge_chunk.py`、`services/embedding_service.py`、`services/knowledge_chunker.py`、`services/knowledge_indexer.py`、`scripts/reindex_knowledge.py` |
