# CygnusX 记忆接通真实验收报告 v3

日期：2026-10-22（Asia/Shanghai）。依据新附件、实施文档 Part 11 与 Part 10。**本轮接线修复、真实写召、历史回填与合成 settle 验证已完成。生产指标导出、人工界面体验和一周观察单列后续，未宣告全面生产准入。**

证据目录：`evidence/memory-go-live-v3/`。本轮实际调用累计 **embedding 41/150、抽取/诊断 7/20**；没有在报告中保留密钥、真实用户正文或向量。生产召回阈值、排序及 hybrid 参数保持。

## 1. 环境快照与阻断修复

| 项目 | 本轮事实与证据 |
| --- | --- |
| 密钥来源 | 用户已在 `~/.zshrc` 导出，交互式 Zsh 可见；工具父进程及旧容器未继承。安全写入根目录 `.env`，权限 0600，后经 Compose 重建进入三个容器；不输出值 |
| 接线 | 主栈 Web/Beat 与独立 Worker 都采用根目录 env_file。本次仅这三个服务显式补列五个记忆相关键；Compose 修前/修后渲染对比通过 |
| 容器 | 首轮 force-recreate 同步 Provider，回填 UUID 后第二轮重建；SDK/指标修复后再重建加载代码。最终三服务 healthy，五键均非空；`step3-effective-settings.json` |
| Provider | `provider-embedding-qwen3` 已同步，UUID `f32b6893-4136-43bb-bd0f-6e4abec7690f`，active=true、is_default=false；既有 YAML 指定聊天默认模型保持 DeepSeek |
| Worker ERROR | 旧 Worker 未加载新增任务，日志为 Received unregistered task / KeyError。新注册表已包含 coverage/settle；实际队列 coverage 任务得到回执，不再以未注册任务失败 |
| 同步失败 | Web 启动曾因 `uq_ai_provider_configs_default` 冲突回滚。改为同事务先清除旧默认、后设置目标；隔离 PostgreSQL 复现旧代码失败、新代码成功，临时 schema 清理确认 |
| SDK 维度拦截 | 真实服务初跑在网络请求前收到 UnsupportedParamsError。对显式 OpenAI 兼容 embedding Provider 添加 `allowed_openai_params=["dimensions"]`，保留 1024 校验；实际容器 smoke 返回 1024 |
| 数据库/备份 | 维护 DSN 显式配置，目标 `omichub`；主机验证器只将该 DSN 的 Docker 地址映射到回环端口。重建前全库备份、回填前 memory_facts 表备份均存于 evidence 外的 0700 目录，文件 0600，TOC 校验通过 |
| 入口自动迁移 | 运行库初始 revision 为 memory_settle_cursor01；工作区另有 project_lifecycle01。标准 Web 入口随授权重建执行该现有迁移，最终 head 为 project_lifecycle01；未修改该迁移源码，执行前已有全库备份 |

根因逐项原始证据、文件行号与脱敏上下文见 `step1-diagnosis.json`。备份位置与 SHA-256 分别见 `predeploy-backup.json`、`backfill.json`，不把备份内容放入报告。


## 1.1 逐文件变更摘要

| 文件 | 本轮变更与目的 |
| --- | --- |
| `deploy/docker/docker-compose.yml` | 仅 Web/Beat 显式传递五个记忆配置键 |
| `deploy/docker/docker-compose.worker.yml` | 仅 Worker 同步传递五键 |
| 根目录 `.env`（不提交） | 安全写入密钥、完整模型 ID、真实 UUID、1024 维及显式维护 DSN |
| `infrastructure/database/repositories/ai_provider_repository.py` | 同事务分两步切换默认配置，避免唯一索引使启动同步回滚 |
| `infrastructure/ai_provider/litellm_provider.py` | 仅所选 OpenAI 兼容 embedding 路由放行 dimensions；不改聊天链路 |
| `infrastructure/celery_app/tasks/memory.py` | 真实抽取失败路径补 `memory.settle_extract_failed` 计数 |
| `application/services/memory_embedding_service.py` | 增加显式状态范围；默认 active；绑定状态快照防并发覆盖，覆盖率仍只算 active |
| `scripts/backfill_memory_embeddings.py` | apply 必须独立确认目标库名；转发显式状态范围，保持维护 DSN 唯一来源 |
| 相关单元测试、架构文档 | 补默认切换、SDK 参数、指标、CLI 保护与状态保留回归；回写当前事实 |

Python 路径均相对 `src/cygnusx/`。工作区存在其他未提交变更，本轮未提交或推送它们。

## 2. Part 10 验收矩阵

| 步骤 | 结果 | 实测与边界 | 证据 |
| --- | --- | --- | --- |
| Step 0 准入 | 通过 | Web/Worker 有效模型、UUID、1024；密钥与维护 DSN 可见；Provider active 且非 default；本轮启动日志无 embedding ERROR。另核对 Beat | `preflight.json`、`step3-effective-settings.json` |
| Step 1 维度 | 通过 | 两次 HTTP 200：不带 dimensions 返回 **4096**，带 1024 返回 **1024**。结论：必须保留显式维度参数 | `step0-dimensions.json` |
| Step 2 写召/KB | 通过 | 3 条不同 scope 合成事实，真实 1024 维和正确标签；个人 scope 落空 Agent 共享分区；跨会话/跨 Agent 命中；跨用户/项目隔离；KB 成对索引和 search_knowledge 命中；遗忘后排除。合成数据清理 | `e2e-write-recall.json` |
| Step 3 历史回填 | 通过 | 活跃 1 条及历史 10 条均完成备份→dry-run 展示→apply；共更新 **11 条**。历史批次 9 archived + 1 superseded 的所有非向量字段保持，未重新激活。全表 1024 维/标签正确，失败和跳过 0；活跃覆盖率 1/1 | `backfill.json`、`historical-backfill-plan.json`、`historical-backfill.json`、`final-database-state.json` |
| 目标库保护 | 通过 | 实际 CLI 错误目标库名配合 --apply 被拒，exit=2、ValueError，发生于连接和 Provider 构造之前。采用 Part 7 允许的目标库名二次确认方案，参数为 --confirm-database | `backfill.json` |
| Step 4 召回/标定 | 完成测量，建议有限 | 10 个真实查询向量、50 次 SQL 召回，过滤关/开各 25；P50 **1.043 ms**、P95 **1.900 ms**，不含向量生成时间。50 命中，另 1 次跨用户负例为空。当前只有 1 条活跃事实，不能推导生产规模性能或独立语义精度 | `recall-real.json`、`recall-real-plan.json` |
| Step 5 settle | 通过 | **生产原配置**下合成会话：成功写事实/游标/settlement；真实模型响应后一次非 JSON 故障，不写内容/回执、不推进游标，settle_extract_failed +1；恢复同区间成功。合成会话与派生内容已清理 | `settle-e2e.json` |
| Step 6 观测 | **验收进程已测，生产导出未通过** | 真实 OTel SDK gauge=1.0，settle 成功/失败计数可读；召回协议计数 50 hit + 1 miss。真实 Worker coverage 任务按现有关闭开关返回 disabled；匿名 Web /metrics=401、短期合成 JWT 请求=200，但没有这些独立验收进程的 memory 序列 | `metrics.json`、`worker-coverage-task.json` |
| Step 7 报告/台账 | 已交付 | 本报告、逐项证据、调用预算、测试 flag 差异与后续命令；列明观测及人工验收边界 | 本文、`call-ledger.json`、`requirements-audit.json` |

早期 SDK 拦截失败记录保留为 `e2e-write-recall.before-sdk-fix.json`；之后修复并完成真实重跑。没有用 stub 的成功值替代最终真实结果。

## 3. 相似度建议

| 指标 | 真实命中相似度 |
| --- | ---: |
| Min / P05 | 0.7316 |
| P50 | 0.7494 |
| P95 / Max | 0.8290 |
| 下一轮标注评估候选阈值 | **0.68** |
| 生产当前阈值 | None，保持 |

候选值按目标命中 P05 减 0.05 得到，非已验证最优值。50 次测量来自 10 个查询与 1 条活跃事实，重复样本有关联，缺独立人工标注负例。**不建议据此直接改生产默认值，也不能沿用未经验证的 0.9。** 详见 `similarity-distribution.json`、`threshold-recommendation.md`。

## 4. 抽取模型与测试 flag 差异

生产 `MEMORY_EXTRACTION_MODEL=qwen3.7-plus` 名称与默认 Provider 的 DeepSeek 名称不同，但实际合成诊断请求成功。进一步核对：现有 `_build_kwargs` 没有消费 `chat(model=...)` 的 model 覆盖参数，因此实际 HTTP 请求模型仍为 `deepseek-v4-flash`。本轮保留聊天链路原行为，**没有修改生产抽取模型设置**；不能把配置中的 Qwen 名称当作实际已验模型。先前针对模型差异提出的修改选项已撤回，无需用户处理。此现存覆盖参数问题单列后续事项。

| 配置/行为 | 生产值 | 最终验收进程 | 说明 |
| --- | --- | --- | --- |
| embedding 模型/UUID/维度 | Qwen 完整 ID / 同步 UUID / 1024 | 相同 | 真实配置已落进程 |
| memory_v2_enabled | true | true | 沿用，不改代码默认 false |
| memory_extraction_model | qwen3.7-plus | 相同 | 实际 Provider 模型 DeepSeek；最终 settle 无模型覆盖 |
| memory_embedding_model_filter_enabled | 现有值 | 仅性能测试局部切换 false/true，各 25 次，结束恢复 | 生产未改 |
| memory_hybrid_min_similarity / 排序/hybrid 参数 | 现有值 | 相同 | 建议不落配置 |
| knowledge_auto_reindex_enabled | false | false | 避免批量隐式重索引调用，沿用既有值 |
| memory_settle_tail_enabled | false | false | 不扫描、沉淀真实用户会话 |
| memory_embedding_coverage_enabled | false | false；直接调用真实 coverage 服务采集 | Worker 队列回执 disabled，不冒充启用 |
| telemetry_enabled | true | 验证器局部 false，手动安装真实 OTel SDK InMemoryMetricReader | 测实际业务仪表，非生产导出链路证明；容器配置未改 |
| DATABASE_URL（验证器） | 容器原配置 | 显式维护 DSN 的同一目标，经 Docker 回环传输 | Provider 和 settle 会话工厂同库；无业务 DSN 回退 |
| 非 JSON 故障 | 无 | 实际模型响应后仅一次受控破坏，然后恢复 | 真实模型调用照样计入预算 |

最初一次 settle 曾在验证器局部设置抽取模型为 Provider 的 model；其证据另存 `settle-e2e.test-model-override.json`。最终以不覆盖生产配置的重跑为准，两轮成本均计入台账。

## 5. 调用、成本与验证

真实 embedding 41 次、抽取/合成诊断 7 次，剩余 109 / 13。每个 HTTP 尝试发送前持久计数，SDK 重试也计数；两次 curl 维度探测单独预留、记录结果。容器 smoke 逐请求通过主机台账确认后再发送。当前没有不明在途调用。

返回的数值 usage 已保留于台账，维度探测与容器 smoke 等部分请求没有保存 usage，因此汇总 token 只代表有 usage 的请求。未查询账单，金额记为 **未知**，不能把调用后的成本写成 0。

- 本轮最终相关域回归：**229 passed**；此前专项 61/40/23 等结果有重叠，不相加。
- 修改 Python 文件专项 Ruff 通过；memory 任务、回填服务、CLI、Provider 仓储四文件 strict mypy 通过。
- LiteLLMProvider 全文件 mypy 仍有 2 项错误：BadRequestError 导出标记与 stream 变量类型。HEAD shadow-file 基线同样 2 项，未修改聊天分支来消除存量问题。
- 镜像清单 17 镜像/19 Agent 校验、实际 Agent 加载 19 个、迁移链单 head、git diff --check 通过。
- 测试退出存在既有 OTel closed-stream 日志，pytest exit=0。未将局部结果宣称全仓门禁全绿；未提交、未推送。

## 6. 剩余清单与准入建议

1. **历史维护已完成**：按原任务的历史 10 条要求继续，新增显式 `--statuses archived superseded`，默认仍为 active；备份并展示计划后执行。9 archived + 1 superseded 全部补向量和标签；数据库指纹核对所有其他列保持。新增测试覆盖默认范围、显式范围、状态并发变化、模型失败及非法范围。没有改变线上召回对 active 的过滤。
2. **生产指标导出未验证成功**：将 coverage 开关、Worker 指标出口与实际采集链列入 Phase 3 观测事项。匿名 /metrics 被当前 AuthMiddleware 拦截；本轮只读核查，没有扩大匿名访问权限或擅自打开生产开关。
3. **抽取 model 覆盖参数不生效**：已有行为，真实 settle 成功但实际用默认 Provider 模型。与 embedding 接通分开处理，避免改聊天链路。
4. 用户人工界面验收、25 案例与后续一周自动沉淀观察仍应按原文档执行；当前小数据测量不足以支持全面生产准入。

接线故障可关闭排查，保留已接通配置。本轮工程交付逐项完成；Part 10.2 明确允许将缺失生产指标列为 Phase 3 观测缺口，因此如实交付该缺口。用户侧界面体验与一周观察仍需按手工 checklist 执行，不能用服务层证据替代全面生产准入。

## 7. 复核与解锁后命令

以下命令从仓库根目录运行，凭据仅从安全环境/根目录 `.env` 读取，不放命令行参数。真实调用脚本会继续沿用累计预算，禁止清空台账重跑。

| 阶段 | 复核/解锁命令与条件 |
| --- | --- |
| 接线与 Step 0 | `uv run --frozen python evidence/memory-go-live-v3/collect_preflight.py`（只读）；三服务重建命令保存在 recreate-first.json |
| 维度 | `cat evidence/memory-go-live-v3/step0-dimensions.json`；已完成限定 2 次探测，原脚本会拒绝重复调用，无需再探测 |
| 写召/KB | `uv run --frozen python evidence/memory-go-live-v3/step2_real.py`；会真实调用并清理合成数据，已有通过结果时无需重复 |
| 回填 | `uv run --frozen python evidence/memory-go-live-v3/step3_backfill.py dry`；仅重算 active 计划。历史范围复核用 `uv run --frozen python scripts/backfill_memory_embeddings.py --statuses archived superseded --dry-run`（先在安全环境加载显式维护 DSN）；历史批次已完成，无需重复 apply |
| 标定 | `uv run --frozen python evidence/memory-go-live-v3/step4_recall.py`；有新样本或明确需要复测时才运行，会继续计费 |
| settle | `uv run --frozen python evidence/memory-go-live-v3/step5_settle.py`；仅合成会话，真实调用按台账计数；现有通过结果无需重复 |
| 指标 | `uv run --frozen python evidence/memory-go-live-v3/step6_metrics.py` 测验收进程 SDK 指标；不能用它解锁生产 Worker 导出验收，生产采集方案尚待确定 |
| 报告与预算 | `cat evidence/memory-go-live-v3/requirements-audit.json`、`cat evidence/memory-go-live-v3/call-ledger.json`；核对阻断及累计值 |
