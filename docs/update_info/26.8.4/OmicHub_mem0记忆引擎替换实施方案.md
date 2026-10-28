# OmicHub mem0 记忆引擎替换实施方案

> 版本：26.8.4 ｜ 日期：2026-08-04 ｜ 状态：**已实施，灰度验证全部通过**
> 前置调研：本次会话 4-agent 记忆系统核查 + mem0 适配性评估（见 `memory/agent-memory-system-state.md`）
>
> **上线终态**：mem0 v2.0.15 + fastembed（multilingual-e5-large，1024 维）+ pgvector，
> 独立 collection `mem0_memories`；`MEM0_ENGINE_ENABLED=true` 已生效（.env）；
> web 金丝雀 7/7 通过、worker settle 真实会话抽出 4 条事实。回滚：`MEM0_ENGINE_ENABLED=false` + 重建容器。

## 0. TL;DR

- 用 **mem0 v2.0.15（Apache-2.0，Python 库）** 替换 `AgentMemoryService` 的自研存取/抽取/检索内核；
  工具签名、用户 API、前端页面、scope 语义、敏感过滤等**外壳全部保留**。
- 采用**特性开关 `mem0_engine_enabled` 双轨运行**：开关关 = 现有自研实现（回滚位），开关开 = mem0 引擎。
- mem0 数据落 **omichub-db 现有 pgvector（0.8.6）** 的独立 collection `mem0_memories`，
  不改动 `agent_memories` 表（现为 0 行，无迁移负担）。
- 顺带修复三个结构性缺陷：
  ① 记忆沉淀触发点从"仅删会话"扩展为"消息数阈值 + 删会话"；
  ② 子 agent 工具剥离补齐 `update_memory`/`forget_memory`；
  ③ 记忆注入异常不再静默吞掉。
- 最大技术风险：**mem0 embedder 无 litellm provider**。PoC 优先验证现有云端 key 的
  OpenAI 兼容 embedding 端点（阿里云 text-embedding-v3 / 火山 doubao-embedding），
  兜底方案为本机 ollama `bge-m3`（1024 维，已装 ollama 服务）。

---

## 1. 背景

### 1.1 现状核查结论（2026-08-04，4-agent 并行核查 + 运行时实测）

| 层面 | 现状 |
|---|---|
| 短期记忆 | 前端滑窗 20 条 + 后端 200K-token 应急压缩（`chat_service.py:1006`），运行正常 |
| 长期记忆表 | `agent_memories`：schema 完整（含 `embedding vector(1024)` + HNSW 索引），但 **0 行数据** |
| 功能开关 | `auto_summary` / `semantic_retrieval` / `conflict_adjudication` 全默认关，`.env` 无覆盖 |
| 沉淀触发 | 唯一触发点 = 删除会话（`chat_service.py:772`），`summarize_session` 从未执行过 |
| 检索 | 默认仅 ILIKE 关键词；向量链路就绪未通电 |
| 跨 agent | scope 双轨：profile/preference 共享（agent_id=NULL），project/summary 按 agent 隔离 |

### 1.2 自研链路的主要缺陷（本次要解决的）

1. 去重过粗：keywords 有一个交集即判重复（`agent_memory_service.py:461`）
2. 语义检索需手工通电且 embedding 模型未配置
3. 沉淀时机单一（仅删会话）
4. 冲突裁决、confidence 均为装饰
5. 跨 agent 索引仅能靠 `agent_id IS NULL` 技巧，无定向跨 agent 查询

### 1.3 为什么选 mem0

- 事实抽取、去重合并（实体映射）、混合检索（语义+关键词）、时间排序开箱即用
- `user_id`/`agent_id`/`run_id` 三级作用域 + filters，天然匹配平台隔离模型
- pgvector 后端、`AsyncMemory` 全异步、history 审计、Apache-2.0
- 与平台技术栈契合：Python 3.11 ✅ / pgvector 0.8.6 ✅ / LiteLLM ✅

---

## 2. 目标与非目标

**目标**
- G1 长期记忆真正"通电"：对话能沉淀、跨会话能召回、检索走语义
- G2 保持全部对外契约不变（4 个工具、用户/管理员 API、前端、注入格式）
- G3 跨 agent 索引升级：支持省略 agent_id 的跨 agent 检索
- G4 可一键回滚

**非目标**
- 不动短期记忆（前端滑窗 + 200K 压缩）
- 不动知识库（kb_chunks）检索链路
- 不引入 mem0 的 graph memory（需 Neo4j，过度设计）
- 不做 agent_memories 历史数据迁移（0 行）

---

## 3. 总体架构

```
            ┌────────────────────── 外壳（保持不变）──────────────────────┐
            │  4个LLM工具            用户API             前端            │
            │  omichub_{save,        GET/DELETE          ProfileView     │
            │  update,forget,        /users/me/memories  列表/删除/清空  │
            │  search}_memory        (users.py)                          │
            │        │                    │                 │            │
            │  AgentMemoryToolService     │                 │            │
            │        └────────┬───────────┴─────────────────┘            │
            │                 ▼                                          │
            │        AgentMemoryService（public 签名不变）               │
            │        ┌────────┴────────┐                                 │
            │        │ mem0_engine_    │  False → 现有自研实现（回滚位） │
            │        │ enabled?        │                                 │
            │        └────────┬────────┘                                 │
            └─────────────────┼──────────────────────────────────────────┘
                              ▼ True
            ┌── 新内核 Mem0Engine（infrastructure/memory/mem0_engine.py）─┐
            │  mem0 AsyncMemory 单例                                      │
            │  ├─ vector_store: pgvector @ omichub-db                     │
            │  │    collection=mem0_memories, hnsw=True                   │
            │  ├─ llm: litellm provider → openai/qwen3.7-plus(api_base)   │
            │  ├─ embedder: openai兼容端点 / ollama bge-m3（PoC定）       │
            │  └─ 敏感过滤 + 条数上限（复用现有包装逻辑）                  │
            └─────────────────────────────────────────────────────────────┘
```

### 部署形态

| 组件 | 形态 | 说明 |
|---|---|---|
| mem0 本体 | **Python 库**，装进 web/worker 镜像 | `uv add mem0ai==2.0.15`；mem0 是库不是服务，**无需独立容器** |
| 向量存储 | 复用 omichub-db | pgvector 0.8.6 已装，mem0 自建表于独立 collection |
| 抽取 LLM | 复用现有 provider | qwen3.7-plus（可配），走 mem0 的 litellm provider |
| Embedding | 云端端点优先，本地 ollama 兜底 | 见 §4 D5 |

> 注：用户提到"可以本地创建容器"——mem0 本身不需要容器；唯一可能新增的本地服务是
> embedding（若云端 key 均不支持 embedding 模型，则 `ollama pull bge-m3`，ollama 已在运行）。

---

## 4. 关键设计决策

### D1 存储：独立 collection，双轨并存
- mem0 在 omichub-db 中建 `mem0_memories` + history 表（mem0 自动建表，需验证 history 后端，见 PoC）
- `agent_memories` 表保留不动，作为 `mem0_engine_enabled=false` 时的回滚位
- 两套数据不互通（反正旧表 0 行）

### D2 scope → mem0 映射

| 平台概念 | mem0 表达 |
|---|---|
| user_id | `user_id` 参数 |
| agent 私有（project/summary） | `agent_id` 参数 |
| 跨 agent 共享（profile/preference） | **不传** `agent_id`（仅 user_id） |
| scope 四值 | `metadata={"scope": "...", "keywords": [...], "source_session": "..."}` |
| 会话溯源 | `run_id=session_id` |
| confidence | 废弃（mem0 用检索分数排序）；DTO 字段保留返回 1.0 兼容前端 |

### D3 跨 agent 索引升级
- 写入规则不变（profile/preference 共享，project/summary 私有）
- **检索升级**：`search_memory` 工具与 L2 注入默认"私有 + 共享"（filters: user_id +
  `agent_id` 等于当前 **或** 不带 agent_id 的共享条目）；新增可选参数 `cross_agent=true`
  时省略 agent_id 过滤 → 跨全部 agent 检索（供 router/orchestrator 类场景，灰度后再开放）
- 实现依赖：PoC 验证 mem0 filters 对"agent_id 存在性"的表达力；若不支持 OR，则两次查询合并去重

### D4 抽取 LLM
- 新增配置 `mem0_extraction_model`（默认 `qwen3.7-plus`，即 providers.yaml 中的注册名）
- 经 mem0 的 `litellm` provider 接入：model=`openai/qwen3.7-plus` + api_base/api_key 从
  provider 注册表解析（复用 `AIProviderService`/runtime 解析逻辑）

### D5 Embedder 选型（定案：fastembed 进程内 ONNX）
演进记录（PoC→灰度期间实测）：
- ❌ 阿里云 token-plan 端点：`GET /v1/models` 无 embedding 模型
- ❌ 火山 Ark：coding plan key 在标准 `/api/v3` 返回 401
- ❌ 宿主 ollama 直接暴露：仅监听 127.0.0.1，改全网暴露被安全评审否决
- ❌ compose 独立 `ollama-embed` 容器：ollama 镜像（~4GB）所有 registry 源拉取均卡死
  （daemon 镜像源列表全试遍）；服务定义保留在 compose（profiles: embed-ollama 隔离备用）
- ✅ **fastembed 进程内 ONNX**（mem0 原生 provider）：
  - 模型 `sentence-transformers/paraphrase-multilingual-mpnet-base-v2`（768 维，免前缀，
    多语含中文，Apache-2.0）——e5-large 因 fastembed 不加 query/passage 前缀、
    无关分数虚高（0.79）弃用；bge-m3 不在 fastembed 支持列表
  - 模型缓存：`FASTEMBED_CACHE_PATH=/data/omichub/mem0-cache`（web/worker 共享卷），
    下载源 `HF_ENDPOINT=https://hf-mirror.com`
  - ⚠ 换模型后分数分布变化，`mem0_search_score_threshold` / `mem0_dedup_similarity_threshold`
    须按实测分布重调（见灰度记录）

### D6 特性开关与配置项（新增，core/config.py）

```python
mem0_engine_enabled: bool = False            # 总开关（回滚位）
mem0_extraction_model: str = "qwen3.7-plus"  # 抽取/摘要 LLM
mem0_embedding_provider: str = ""            # openai_compatible | ollama（PoC 后定）
mem0_embedding_model: str = ""               # 模型名
mem0_embedding_dims: int = 1024
mem0_collection: str = "mem0_memories"
mem0_llm_temperature: float = 0.1
```

### D7 同步/异步
- 服务层（FastAPI 异步上下文）用 `AsyncMemory`
- Celery 任务（sync 上下文）用 `asyncio.run(...)` 包一层，或直接用 sync `Memory`
  （PoC 验证 mem0 sync/async 客户端能否共享同一 collection 无冲突）

### D8 v2.0.15 实测 API 约束（PoC 内省确认，适配层必须遵守）

| 约束 | 说明 |
|---|---|
| `search`/`get_all` **拒绝顶层 user_id/agent_id** | 必须用 `filters={"user_id": ..., "agent_id": ...}`，否则抛 ValueError |
| `add` 仍接受顶层 `user_id/agent_id/run_id/metadata` | 另有 `infer=False`（直存不抽取）、`expiration_date`（原生 TTL！）、`timestamp`、`memory_type`、`prompt` |
| `search` 参数 | `top_k=20, filters, threshold=0.1, rerank, show_expired, reference_date` |
| `update(memory_id, text/data, metadata, expiration_date)` / `delete` / `delete_all(user_id=, agent_id=, run_id=)` / `history(memory_id)` | 顶层作用域参数仅 delete_all 保留 |
| LLM 接线 | mem0 的 `litellm` wrapper **不透传 api_base**；OpenAI 兼容端点要用 `provider="openai"` + `OpenAIConfig(openai_base_url=..., api_key=...)` |
| Embedder | 无 litellm provider；`ollama` provider 用 `BaseEmbedderConfig(model, embedding_dims, ollama_base_url)`；`openai` embedder 支持 `openai_base_url` |
| pgvector | `PGVector(dbname, collection_name, embedding_model_dims, user, password, host, port, hnsw, connection_string?, connection_pool?)`，自动建表 |
| history 存储 | **sqlite**（`history_db_path`，默认 `~/.mem0/history.db`），无 postgres 后端；容器内须给 `MEM0_DIR` 挂可写卷 |
| `custom_instructions` | MemoryConfig 支持自定义抽取指令 → 注入中文生信领域提示 |
| 依赖 | 需 `psycopg[pool]`（psycopg2 亦可）、ollama embedder 需 `ollama` 客户端库；mem0 自带 posthog 遥测，部署须设 `MEM0_TELEMETRY=false` |
| MemoryItem 形态 | `{id, memory, hash, metadata, score, created_at, updated_at}` |

---

## 5. 对外契约（不可变更清单）

### 5.1 LLM 工具（tool_configs/tools_schema.yaml，data/ai/tools/memory.yaml）

| 工具 | 参数 | 说明 |
|---|---|---|
| `omichub_save_memory` | content(≤200字), scope∈四值, keywords(≤8) | 写入 |
| `omichub_update_memory` | memory_id, content, keywords? | 更新 |
| `omichub_forget_memory` | memory_id | 软删除 |
| `omichub_search_memory` | query, scope?, limit(1-5) | 检索 |

### 5.2 REST API
- `GET /users/me/memories`（agent_id/scope/project_id 过滤）
- `DELETE /users/me/memories/{memory_id}`、`DELETE /users/me/memories`（批量归档）
- `GET /admin/users/{user_id}/memories`（含归档，只读）

### 5.3 Prompt 注入格式（chat_service.py:2013-2028 / 2216-2228）
```
## 用户记忆（跨会话，可能过时；与当前对话冲突时以当前对话为准）
- <记忆1>
```
预算 3200 字节、L1(≤10) + L2(≤5) 结构保留。

### 5.4 DTO 字段映射（mem0 record → AgentMemory DTO）

| DTO 字段 | mem0 来源 |
|---|---|
| id | mem0 memory_id（UUID 字符串，直接透传） |
| content | `memory` 字段 |
| scope / keywords / source_session | `metadata.*` |
| agent_id / user_id / project_id | mem0 原生字段 / metadata.project_id |
| confidence | 恒定 1.0（兼容） |
| use_count / last_used_at | mem0 无此概念 → 0/None（前端仅展示不依赖）|
| created_at / updated_at | mem0 `created_at`/`updated_at` payload |
| status | mem0 只存活跃条目 → 恒 "active"；归档语义由 delete 承担 |

> 精确字段以 `schemas/agent_memory.py` 为准（见附录 A 契约快照）。

---

## 6. 分阶段施工计划

### Phase 0：PoC（0.5~1 天）——验证三个硬风险

**步骤**
1. `uv add mem0ai==2.0.15`（锁版本）
2. **Embedding 探针**：脚本探测 ①阿里云 text-embedding-v3 ②火山 doubao-embedding
   是否可用（用现有 key，输出维度与错误）；均失败则 `ollama pull bge-m3`
3. **PoC 脚本** `scripts/poc/mem0_poc.py`（主机上跑，直连 omichub-db）：
   - 初始化 `Memory`：pgvector(collection=`mem0_poc`) + llm(litellm→qwen) + embedder(步骤2结果)
   - 用例 A：add 3 条事实 → search 语义召回正确
   - 用例 B：**同一事实换表述 add 3 次** → get_all 计数，观察 ADD-only 重复堆积率
   - 用例 C：user_id/agent_id/run_id 隔离 + 省略 agent_id 跨 agent 检索
   - 用例 D：metadata.scope 过滤是否支持
   - 用例 E：history() 审计与后端落点
4. 清理：`DROP` mem0_poc 相关表

**验收标准**
| # | 标准 | 结果 |
|---|---|---|
| P1 | embedder 接通（ollama bge-m3），维度 1024 确定 | ✅ |
| P2 | qwen3.7-plus 抽取走通（openai provider + openai_base_url） | ✅ 中文对话抽出 3 条自包含事实 |
| P3 | pgvector 落库、HNSW 语义检索正常 | ✅ DESeq2 事实 top1 召回 |
| P4 | 重复堆积率可接受 | ✅✅ **同义 x3 → 仅 1 条**（实体映射自动合并） |
| P5 | 跨 agent（省略 agent_id）检索可行 | ✅ 省略=全见；带 agent_id=仅私有 |

**PoC 额外结论（影响适配层设计）**
1. 带 `agent_id` 过滤时**共享条目不可见**（共享条目无 agent_id 字段）→ "私有+共享"
   召回需两次查询合并去重（L1/L2 注入按此实现）
2. 服务端 `metadata.*` 嵌套过滤不可靠（count=0）→ **scope 过滤放客户端**
   （候选池 ≤500/用户，Python 侧过滤无性能问题）
3. `infer=False` 直存可用 → 工具主动写入路径免二次抽取、零 LLM 成本
4. history 审计可用（sqlite）→ 容器部署需给 MEM0_DIR 挂卷
5. `expiration_date` 原生 TTL 可用 → 后续可给 summary 类记忆设过期（暂不启用）
6. PoC 数据已清理（delete_all）；脚本保留于 scripts/poc/mem0_poc.py

### Phase 1：适配层（2~3 天）

| # | 文件 | 改动 |
|---|---|---|
| 1 | `pyproject.toml` + `uv.lock` | 加 `mem0ai==2.0.15`、`psycopg[pool]>=3.1`、`ollama>=0.6.2`（镜像重建自动装）；dev 热装：容器 venv 无 pip，须 `docker exec -u root <c> sh -c "python /tmp/get-pip.py && python -m pip install ..."`；worker 镜像缺 libpq，须装 `psycopg[binary]`；注意 pip 会连带升级 packaging，须回 pin `packaging<26`（snakemake 约束） |
| 2 | `core/config.py` | 新增 D6 配置项 |
| 3 | **新** `infrastructure/memory/mem0_engine.py` | `Mem0Engine` 单例：from_config 构造、provider 解析、add/search/get_all/update/delete 封装、metadata↔DTO 映射 |
| 4 | `agent_memory_service.py` | public 方法签名不变；方法体首行按 `mem0_engine_enabled` 分流：True→Mem0Engine，False→现有实现（原代码保留） |
| 5 | `agent_memory_tool_service.py` | 不改（透过 service 分流） |
| 6 | `chat_service.py` 注入段 | 不改调用；`build_prompt_context` 内部已分流 |
| 7 | `api/v1/admin/users.py:468` | 用户删除级联处追加：mem0 引擎开启时同步 `delete_all(user_id=...)` |

**关键实现细节**
- Mem0Engine 初始化时从 provider 注册表解析 extraction model 的 api_base/api_key（参考
  `LiteLLMProvider._route_model` 的 `openai/{model}` + api_base 模式）
- 敏感过滤、200 字上限、500 条上限逻辑在 service 分流**之前**执行（两轨共用）
- save→`add(messages=[{"role":"user","content":content}], user_id, agent_id?, run_id?, metadata)`
  ；注意 mem0 add 会触发 LLM 抽取——工具主动写入场景应传 `infer=False`（若 v2 支持直存）
  绕过二次抽取，PoC 验证此参数
- search→`search(query, filters)`，结果映射回 DTO
- **`list_memories` 兼容技巧**：`users.py`/`admin/users.py` 端点对返回值逐条调
  `AgentMemoryService._serialize(memory)`（静态方法，读 13 个属性）。mem0 轨返回
  **transient `AgentMemoryModel` 实例**（不入 session，仅填属性），端点零改动；
  `id` 需为 `uuid.UUID`（mem0 id 本身是 UUID 字符串，`uuid.UUID(mid)` 转换，失败则
  用 `uuid.uuid5(NAMESPACE, mid)` 派生稳定 UUID）
- `forget_memory` 软删除语义：mem0 无 status 字段 → 直接 `delete(memory_id)`（对用户等价）；
  `clear_memories` → `delete_all(user_id, agent_id?)`，返回删除条数
- `backfill_embeddings` 任务：mem0 轨直接返回 `{"status": "not_needed"}`（mem0 写入即向量化）

### Phase 2：沉淀触发修复（1 天）

| # | 改动 | 位置 |
|---|---|---|
| 1 | `tasks/memory.py`：新增 `settle_session_memory(session_id)` —— 读会话最近 N 条消息（30条/8000字，复用现有裁剪），mem0 引擎开→`mem0.add(messages, user_id, agent_id, run_id=session_id, metadata={"scope":"summary"})`；旧引擎→保留原 summarize 逻辑 | celery tasks/memory.py |
| 2 | 触发点①（保留）：`delete_session` | chat_service.py:772 |
| 3 | 触发点②（新增）：`add_message` 中 assistant 消息落库后，`message_count % settle_every_n == 0`（n 默认 20，可配）→ enqueue settle 任务（countdown 防读到未提交数据，沿用现有 5s 模式） | chat_service.py |
| 4 | 队列沿用 `analysis`（celery.py:78 已有 memory.* 路由） | 无改动 |

### Phase 3：结构性小修（0.5 天）

| # | 改动 | 位置 |
|---|---|---|
| 1 | 子 agent 剥离名单补 `omichub_update_memory`、`omichub_forget_memory`（**保留 search**，只读对子任务有用） | parallel_subagent_service.py:42-50 |
| 2 | 注入失败日志 warning→error + 计数（为可观测性留钩子） | chat_service.py:2027, 2227 |
| 3 | `search_memory` 工具 limit 上限 5→10（底层本就支持） | tools_schema.yaml |

### Phase 4：联调与灰度（1 天）

1. 单测：`tests/test_mem0_engine.py`（mock mem0 客户端，验证映射/分流/过滤）
2. 运行时冒烟（记忆教训：web/worker 均不热重载）：
   `docker restart omichub-web omichub-worker`
3. 灰度开启：`.env` 加 `MEM0_ENGINE_ENABLED=true` + embedding 配置 → restart →
   用 shania/general 跑端到端 case：
   - Case1 主动写入：对话中让 agent save_memory → GET /users/me/memories 可见
   - Case2 跨会话召回：新会话提及相关事实 → 注入块出现该记忆
   - Case3 跨 agent 共享：agent A 写 preference → agent B 会话能召回
   - Case4 自动沉淀：聊满 20 条 → settle 任务执行 → summary 记忆出现
   - Case5 回滚：开关关 → 旧链路无异常
4. 验收后更新 memory 笔记与本文档状态

---

## 6.5 灰度部署记录（2026-08-04 实操）

1. **依赖声明**：`mem0ai==2.0.15`、`psycopg[pool]>=3.1`、`ollama>=0.6.2`、`fastembed>=0.8.0`
   已进 pyproject/uv.lock；**镜像重建是唯一可靠的依赖落地方式**——
   容器热装（ensurepip 失败→get-pip.py -u root 可成）会随 `up -d` 重建丢失。
2. **worker 镜像缺 libpq**：psycopg 纯 python 版 import 失败，镜像重建后由
   `psycopg[pool]` 声明解决（若急用热装须装 `psycopg[binary]`）。
3. **`docker restart` 不重读 env_file**：新增 .env 变量必须 `up -d` 重建容器才生效；
   worker 栈用 `bash scripts/worker-compose.sh up -d worker`（脚本透传 compose 子命令）。
4. **embedding 模型缓存**：`/data/omichub/mem0-cache`（web/worker 共享卷）
   已预置 multilingual-e5-large；容器内首次加载若缺缓存会走 HF_ENDPOINT 自下载（约5分钟）。
   ⚠ fastembed 缓存目录里 `models--*` HF snapshot 布局与新版宿主 onnxruntime 的
   external-data 校验冲突（宿主侧报错）；容器 onnxruntime 版本可正常加载——
   宿主侧脚本若报 "External data path escapes model directory"，删除缓存中
   `models--*` 目录让其走 tar 解压布局。
5. **分数阈值**：e5-large（fastembed 无前缀）实测分布——同义≥0.96 / 同领域不同工具≈0.90 /
   跨话题≈0.85 / 无关≈0.80 → `mem0_dedup_similarity_threshold=0.95`、
   `mem0_search_score_threshold=0.87`。
6. **ollama 镜像拉取教训**：daemon 镜像源列表对 ~4GB 大层全部卡死（docker.io/daocloud/1ms.run）；
   小镜像正常。大镜像优先评估进程内（fastembed）或国内可达的专用源。
7. **mem0 v2 抽取三个隐形坑（均已修）**：
   - 内容含 `<`/`>`（如 `padj<0.05`）→ 抽取静默产出 0 条事实；
     已在 `add_inferred` 前置 `_sanitize_for_extraction`（`<`→小于、`>`→大于）
   - 传原生 `agent_id` + 消息含 assistant 角色 → mem0 切换到 "agent memory extraction"
     分支，对平台会话产出 0 条；settle 路径不再传原生 agent_id，隔离全靠 metadata
   - fastembed 返回 numpy ndarray，psycopg3 无法适配 → 引擎构建后给
     `vector_store.insert/search/update` 打 ndarray→list 补丁
8. **db 镜像漂移陷阱**：基础 compose 的 db 原为 `postgres:14-alpine`，任何不带
   pgvector overlay 的 `docker compose up -d <任意服务>` 都会把 db 重建回无 pgvector
   镜像（数据卷中扩展目录仍在 → 全部向量操作报 `$libdir/vector`）。**已将基础 compose
   db 镜像改为 `pgvector/pgvector:pg14`**（与 PG14 数据兼容），overlay 文件仅留兼容。
9. **worker 镜像缺 libpq**：psycopg 纯 python 版不可用，pyproject 已改
   `psycopg[binary,pool]`（wheel 自带 libpq）。

## 6.7 二期增强：管理开关 / 用户可见性 / 加密落盘（2026-08-04 同日实施并验证）

### 管理员运行时开关
- `site_settings.agent_memory_enabled`（迁移 `k5l6m7n8o9p0`，默认 true）；
  前端「设置 → 平台设置」卡片切换，免 TOTP（非敏感功能开关名单）。
- **三态门控**（`AgentMemoryService._memory_mode`）：
  | env MEM0_ENGINE_ENABLED | 管理端开关 | 行为 |
  |---|---|---|
  | false | * | legacy 旧链路 |
  | true | true | mem0 引擎 |
  | true | false | off：读返回空、写入报「平台记忆功能当前已被管理员关闭」、settle 返回 disabled_by_admin |
- 消费点：service 八入口 + chat_service `_enqueue_memory_summary` /
  `_maybe_enqueue_memory_settle`（转实例方法带 db 门控）+ celery settle。

### 用户可见性（ProfileView「我的记忆」）
- scope 筛选（全部/用户画像/偏好/项目/对话沉淀）、Agent 友好名映射、
  来源会话标记（source_session 悬停可见）、文案明确"来自与 AI 的对话、自动沉淀、加密存储"。

### 加密落盘（`/data/omichub/omichub_data/_mem0/`）
- **密钥**：`MEM0_ENCRYPTION_KEY`（env 优先）→ 自动生成 `_mem0/master.key`（0600）。
  密钥丢失 = 存量记忆不可恢复；多副本须显式共享同一密钥。
- **加密边界**：mem0 vector_store 补丁（引擎 `_patch_vector_store`）——
  insert/update 写前加密 payload.data；search/get/list 读后解密；
  mem0 内部抽取/去重/实体合并经同一补丁读回明文，行为不变。
  兼容 pgvector list 的嵌套返回 `[[OutputData]]`；解密失败按明文历史数据放行。
- **history 审计**：sqlite 迁至 `_mem0/history/history.db`，old/new memory 写前加密
  （`_patch_history`）；`client.history()` 返回密文，平台暂不解密展示。
- **实测**：SQL 直查 payload 为 `gAAAAA…` 密文、明文零泄露；应用读回明文正常。

### 二期踩坑
- `docker restart` 不重读 env_file（本日第二次踩）：改 .env 后必须 `up -d` 重建，
  否则 MEM0_HISTORY_DIR 等旧值残留。
- 补丁函数命名 `list` 会遮蔽内置类型导致 `isinstance(x, list)` TypeError → 命名 `list_`。

## 7. 回滚方案

- 一键回滚：`MEM0_ENGINE_ENABLED=false` + `docker restart omichub-web omichub-worker`
- mem0 collection 数据保留不删（重新开启即恢复）
- 旧 `agent_memories` 链路与 Celery 旧任务全程未删

## 8. 风险与缓解

| 风险 | 级别 | 缓解 |
|---|---|---|
| embedder 云端端点均不可用 | 🔴 | ollama bge-m3 兜底（已装 ollama） |
| v2 ADD-only 重复堆积 | 🟡 | PoC 用例 B 量化；不达标则适配层加写入前语义查重 |
| mem0 版本激进演进 | 🟡 | pin 2.0.15；适配层隔离（外壳不变） |
| 每次 add 消耗 LLM 调用 | 🟡 | settle 走 Celery 异步；工具主动写用 infer=False |
| history 后端不支持 postgres | 🟡 | PoC 验证；最差接受 sqlite 落 web 容器卷 |
| metadata 过滤表达力不足 | 🟢 | 两次查询合并去重兜底 |
| 容器内缺依赖 | 🟢 | dev 热装验证，正式重建镜像 |

## 9. 工作量估算

| 阶段 | 估时 |
|---|---|
| Phase 0 PoC | 0.5~1 天 |
| Phase 1 适配层 | 2~3 天 |
| Phase 2 触发修复 | 1 天 |
| Phase 3 小修 | 0.5 天 |
| Phase 4 联调灰度 | 1 天 |
| **合计** | **5~6.5 天**（单人，含验证） |

---

## 附录 A：现有代码契约快照

### A.1 DTO（schemas/agent_memory.py，33 行）
```python
MemoryScope = Literal["profile", "project", "preference", "summary"]

class AgentMemoryDTO(OmicsHubBaseSchema):
    id: str
    agent_id: str | None = None
    project_id: str | None = None
    scope: MemoryScope
    content: str
    keywords: list[str] = []
    source_session: str | None = None
    confidence: float = 1.0
    use_count: int = 0
    last_used_at: datetime | None = None
    status: str = "active"
    created_at: datetime | None = None
    updated_at: datetime | None = None
```
前端（ProfileView.vue）仅消费 5 字段：`id, scope, content, agent_id, updated_at`。

### A.2 AgentMemoryService public 签名（agent_memory_service.py）
```python
def __init__(self, db: AsyncSession, embedding_client: Any | None = None)
async save_memory(*, user_id, content, scope, keywords=None, agent_id=None,
                  project_id=None, source_session=None, confidence=1.0) -> dict
async update_memory(*, user_id, memory_id, content, keywords=None, source_session=None) -> dict
async forget_memory(*, user_id, memory_id, **_kwargs) -> dict          # {"memory_id","forgotten":True}
async search_memory(*, user_id, query, scope=None, limit=5, agent_id=None,
                    project_id=None, **_kwargs) -> dict                # {"memories":[...],"count":N}
async list_memories(user_id, *, agent_id=None, scope=None, project_id=None,
                    status="active", include_archived=False, limit=100) -> list[AgentMemoryModel]
async delete_memory(user_id, memory_id) -> None
async clear_memories(user_id, *, agent_id=None) -> int
async build_prompt_context(user_id, agent_id, query, *, project_id=None) -> str
```
写操作返回 `{"memory": _serialize(m), "action": "created|updated|discarded"}`；
`_serialize` 是静态方法，读 ORM 实例的 13 个属性（见 A.1）。
模块常量：`MEMORY_SCOPES`、`_MAX_MEMORIES_PER_USER=500`、`_MAX_CONTENT_LENGTH=200`、
`_MAX_KEYWORDS=8`、`_SENSITIVE_PATTERN`（api_key/token/password/bearer/sk-/AKIA 正则）。

### A.3 工具桥（agent_memory_tool_service.py）
- `_memory_agent_id(scope, context)`：profile/preference→None（共享），否则 context.agent_id
- `_project_id(context)`：从 ChatSessionModel 查 session.project_id
- 4 方法透传 service 并在返回值上加 `success` + `summary` 中文文案

### A.4 API 端点
| 端点 | Service 调用 |
|---|---|
| GET /users/me/memories | list_memories → `_serialize` → DTO |
| DELETE /users/me/memories/{id} (204) | delete_memory |
| DELETE /users/me/memories | clear_memories → `{"cleared_count": N}` |
| GET /admin/users/{id}/memories | list_memories(include_archived=True) |
| admin/users.py:468 用户删除级联 | `AgentMemoryModel.__table__.delete().where(user_id==...)` |

### A.5 chat_service 注入点
- 主路径 2013-2028 / handoff 2216-2228：`AgentMemoryService(self._db).build_prompt_context(...)`
  拼入 system_prompt；异常仅 warning 静默跳过
- `MEMORY_TOOL_NAMES`（390）+ `MEMORY_SYSTEM_PROMPT_SUFFIX`（397）
- `_enqueue_memory_summary`（775-790）：仅 delete_session(772) 调用；
  gate=`agent_memory_auto_summary_enabled`；countdown=5

### A.6 Celery（tasks/memory.py）
- `summarize_session(session_id)`：gate 开关→读会话消息（≥min_messages）→截 30 条/8000 字
  →LLM 提炼一句≤200字→`save_memory(scope="summary", confidence=0.7)`
- `backfill_embeddings(limit=100)`：调私有 `_populate_embedding`；队列 `analysis`

### A.7 配置（core/config.py:92-99）
8 个 `agent_memory_*` 开关/模型名（默认全关/空）——本方案不改它们，新增 `mem0_*` 组。

### A.8 影响面清单
- `AgentMemoryService` 引用：tool_service、chat_service×2、users.py×3 端点、admin/users.py、
  tasks/memory.py×2
- `AgentMemoryModel` 引用：models/__init__、admin/users.py:407/468、tasks/memory.py、service 本体
- 反射加载：tools_schema.yaml 的 `service:` 字符串指向 AgentMemoryToolService（不可改名/改路径）

### A.9 不可变契约（红线）
1. 4 个工具名（写死在 MEMORY_TOOL_NAMES / memory.yaml / tools_schema.yaml 三处）
2. 4 个 scope 值（前后端正则/枚举硬编码）
3. DTO 13 字段 + `_serialize` 消费方式
4. `build_prompt_context` 返回 str、空串=无记忆
5. scope 隔离规则（profile/preference 共享）
6. AgentMemoryToolService 类路径（YAML 反射）
