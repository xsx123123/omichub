# SiliconFlow embedding 接入实施报告

日期：2026-10-21。范围：独立 embedding Provider 选择、维度请求参数、启动检查、YAML/Settings 示例与相关测试。代码实现已完成；真实维度探测受阻；全仓门禁未全绿。未重建容器、未同步运行库、未做真实回填、未调用抽取模型。

## 1. 逐文件改动

| 文件 | 改动与理由 |
|---|---|
| `data/ai/providers.yaml` | 补齐末尾向量条目的 name=`provider-embedding-qwen3`、model=`Qwen/Qwen3-Embedding-8B`、tier=light；base_url 为 SiliconFlow /v1，密钥引用 `${SILICONFLOW_API_KEY}`，active=true、default=false。未改变既有四个条目的默认/启用状态。移除无加载器消费的字符串 id，避免冒充数据库 UUID |
| `src/cygnusx/core/config.py:265` | 新增 `agent_memory_embedding_provider_id: str=""` 和 `agent_memory_embedding_dimensions: int=1024`（正整数校验） |
| `.env.example` | 声明两字段及密钥注入变量，合并记忆段重复模型/Provider/维度键；Provider 默认留空，保留旧选择链，删除重复的非 UUID 名称示例 |
| `src/cygnusx/infrastructure/ai_provider/litellm_provider.py:432` | 独立解析 embedding UUID。缺失、无效、未激活或 DB 不可用均报错，不回退聊天链。维护 CLI 显式 Provider 必须与选择 UUID 一致，避免跨到默认业务库 |
| 同文件 468、492 | 独立选择启用时传 dimensions；对 OpenAI-compatible 自定义端点，将含厂商命名空间的 Qwen 模型路由为 `openai/Qwen/Qwen3-Embedding-8B`，防止把 Qwen 当 LiteLLM provider。未改聊天 `_get_config`、`_route_model`；选择键空时保持旧请求，无 dimensions 参数 |
| `src/cygnusx/main.py:81、312` | YAML 同步完成后核对所选 Provider；错误用 ERROR 级记录且不输出凭据，误设全局 default 时 WARNING。仅查询配置、不请求模型；不阻断整个 Web 启动 |
| `tests/unit/test_embedding_provider_selection.py` | 新增 13 个用例，覆盖选择/拒绝回退/维度/旧链/聊天隔离/维护库显式配置/启动告警，以及记忆、KB 索引和 KB 查询共用选择逻辑 |
| `scripts/probe_siliconflow_embedding_dimensions.py` | 可复核的 curl 探测入口，最多两次，密钥通过 curl stdin 配置传递、不进入 argv；只保存 HTTP 状态/维度，不保存向量、正文或密钥。已尝试过真实请求时禁止盲目重跑 |

记忆 `_embed`、KB `KnowledgeIndexService._embed` 和 `VectorRetrievalService._embed` 原本均创建 LiteLLMProvider，因此无需逐调用点修改。相关新增测试验证三条消费链均到达同一独立 Provider。

## 2. Step 0 维度探测

执行：`uv run python scripts/probe_siliconflow_embedding_dimensions.py`，退出码 **2**。

| 请求 | 是否发出 | 返回维度 | 结果 |
|---|---|---|---|
| 不带 dimensions | 否 | 未取得 | 受阻：未配置密钥 |
| dimensions=1024 | 否 | 未取得 | 受阻：未配置密钥 |

检查时 `.env`、`.env.test` 和进程环境的 `SILICONFLOW_API_KEY` / `EMBEDDING_PLATFORM_API_KEY` 均无有效值。没有寻找其他凭据。证据：`evidence/embedding-provider-siliconflow/step0.json`。真实 embedding 请求累计 **0/2**；抽取调用 **0**。

[SiliconFlow 官方 embeddings 文档](https://api-docs.siliconflow.cn/docs/api/embeddings-post)列出完整模型 ID 与 1024 维 dimensions 支持；模型本身最高支持 4096 维。本实现先按官方接口透传 1024，但由于两次探测未完成，尚不能把“参数在当前账号/端点实际可用”或“不传参数的实际默认维度”当作实测结论。若真实接口拒绝 dimensions，需按任务要求记录响应证据后再调整，当前没有凭空认定拒绝而删参数。

## 3. 测试与门禁

证据目录：`evidence/embedding-provider-siliconflow/`。

| 命令 | 结果 | 证据 |
|---|---|---|
| `AGENT_MEMORY_EMBEDDING_PROVIDER_ID='' uv run pytest tests/unit/test_embedding_provider_selection.py tests/unit/test_memory_embedding_models.py tests/unit/test_memory_embedding_cli.py tests/unit/test_provider_retry_policy.py::test_litellm_embedding_routes_custom_openai_endpoint -q --tb=short` | **37 passed**，退出码 0 | `focused-tests.txt` |
| 同时扩大运行整个 `test_provider_retry_policy.py` | **53 passed, 1 failed**，退出码 1 | `tests.txt`；失败为 DeepSeek thinking 参数断言，涉及适配器与测试均与 HEAD 相同，未顺手修改 |
| `uv run ruff check src/ tests/ --output-format=json` | 274 个问题，退出码 1 | `ruff-all.json`；本次改动的 Python 文件无对应诊断 |
| 对三个修改的源码文件、新测试、新探测脚本执行 Ruff | **通过**，退出码 0 | `ruff-focused.txt` |
| `uv run mypy src/cygnusx/` | 1,028 个错误/216 文件，退出码 1 | `mypy.txt` |
| 以 HEAD 版本三个修改源码为 shadow-file 执行相同 mypy | 同样 1,028 个错误/216 文件 | `mypy-baseline.txt`；按文件+错误内容比较，新增/消除诊断均 0，见 `mypy-comparison.json` |
| `uv run python scripts/check_env_example_drift.py` | **通过**，退出码 0，MEM0_* 仍被排除 | `env-drift.txt` |
| 本次修改文件 `git diff --check` | **通过** | 无空白错误 |

测试显式清空新选择环境键，是为了检验“不启用新键时保持旧行为”。本机 `.env` 中已有字符串 Provider 名称，这不符合数据库 UUID 契约；未修改本机 `.env` 来掩盖配置问题。

测试结束时存在 OTel 日志退出阶段的 closed-stream 提示，不影响 37 项测试退出码；不将此提示当成真实 Provider 验证。

## 4. 用户侧启用说明

先通过现有管理同步入口或部署启动同步 YAML。加载器依据 name 更新/创建 Provider，生成/保留数据库 UUID；不会采用 YAML 的 `id: provider-embedding-qwen3`。在管理端取得 `provider-embedding-qwen3` 的实际 UUID，再设置 `.env` 三行：

```dotenv
AGENT_MEMORY_EMBEDDING_MODEL=Qwen/Qwen3-Embedding-8B
AGENT_MEMORY_EMBEDDING_PROVIDER_ID=<同步后该Provider的数据库UUID>
AGENT_MEMORY_EMBEDDING_DIMENSIONS=1024
```

密钥由运维安全注入运行进程环境（或根目录 `.env` 的 `SILICONFLOW_API_KEY`）。YAML 的 `${SILICONFLOW_API_KEY}` 在启动加载时从进程环境展开；仅设置在未加载的 `.env.test` 中不会自动注入服务。密钥不得提交。插值避免 YAML 明文，但当前仓库层会把 Provider 密钥加密保存到 DB，不应称作“密钥不落库”。

保持向量 Provider `is_default=false`，保留原聊天默认设置。由用户按原 Compose 配置重建相关进程后验证有效 Settings；本次未进行这些部署操作。后续维护 CLI 若显式传 Provider，必须选择与上述 UUID 相同且属于目标维护库的配置；否则明确拒绝，不跨库回退。

不要立刻做全量真实回填。先补齐密钥并完成两次维度探测，再在隔离数据上验证写入/检索，随后由用户决定回填。当前全仓 Ruff/mypy 与扩大回归存在失败，报告不宣称全量门禁通过或生产记忆已启用。

## 5. 未完成项

1. 密钥就绪后执行两次真实 curl 探测，记录不传/传 dimensions 的真实返回维度或报错，并据此最终确认 dimensions 分支。
2. 全仓门禁存量问题未处理；不属于本文件授权的修复范围。
3. 容器重建和历史数据回填按明确排除项留给下一轮，不纳入本轮已完成声明。
