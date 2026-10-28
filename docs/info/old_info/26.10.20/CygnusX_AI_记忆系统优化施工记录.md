# CygnusX AI 记忆系统优化施工记录

目标来源：[优化实施方案](CygnusX_AI_记忆系统优化实施方案.md)。当前 as-built 以 [记忆架构](../../../ARCHITECTURE_DESIGN/CygnusX_memory_architecture.md) 为准。

本记录跟踪整个实施范围，不把局部代码通过视为发布门禁通过。当前 v2 默认关闭，未合并发布分支、未部署、未触碰生产数据。

| 工作项 | 当前状态 | 完成证据或缺口 |
| --- | --- | --- |
| 0-A 生产快照副本迁移/回退 | 待环境 | Docker socket 操作被拒绝；无本地 postgres/psql/pg_dump。新增只读统计工具，尚未采集真实数据库 |
| 0-B 25 案例基线 | 待实测 | 协议已有；未取得实际 Provider、隔离账号、快照及评分证据，不能补造历史基线 |
| 0-C Worker/Beat/Provider | 待联调 | 无可用的明确专用环境配置；不得据 mock/SQLite 判通过 |
| 1-A 项目焦点 | 代码已接，真实迁移/并发待验 | 列与部分唯一索引、精确读写/无回退、受控来源与管理项目授权、概览与 UI 分组、默认关闭开关及指标已接；SQL/CAS/HTTP/DOM 隔离验证已过。PG 用例因缺专用 DSN 跳过，门禁 1 未通过 |
| 1-B 残留扫描/人工清理 | 代码已接，隔离验证通过；运行待验 | 默认关闭；拥有者/可见项目边界、有界摘录、失败保存点、工具/报告 API/UI 与显式确认清理、曝光/点击指标已接。archived_reason/同义重写为可选未实现项 |
| 2-A 模型过滤/重嵌入 | 代码已接、隔离验证通过；真实 PG/Provider/性能待验 | 默认关闭过滤与采样；旧模型词面补位、成对写入、CLI dry-run/500 行条件重建、覆盖率与采样时间、运行手册已接。真实 pgvector 用例 skipped，不能判定运行门禁通过 |
| 2-B 混合检索 | 代码已接，质量阈值与真实评测待验 | 双路有界候选、RRF、相似度下限、关键词降级、开关和专项回归已接；25+专项实体案例对比待做 |
| 3-A SQL 游标/尾批 | 代码已接，真实 PG/Beat 待验 | 游标后复合 SQL、覆盖索引、有界批次、空闲尾批、force_tail、跟进积压批次与指标已接；PG 查询计划与 Worker/Beat 联调待做 |
| 3-B 整理回滚 | 代码已接，真实演练待做 | 管理员 API、显式 DSN 运维 CLI、dry-run/冲突清单、事务恢复、版本单调、操作者审计、防重复及拒绝降级迁移已接；真实演练待做 |
| 3-C 回执治理 | 代码已接，重投窗口待核对 | 召回回执 TTL/批量上限、索引、每日清理任务与指标已接；14 天必须在部署前与实际任务重试窗口核对，整理快照留存未裁定 |
| 3-D 监控与告警 | 部分埋点已接，运维面未完成 | settle 成功分母、装配成功耗时与既有分项指标可由遥测导出；预算/队列观测、看板、告警规则与接收渠道仍待做 |
| 3-E 配置漂移 | 代码已实现，隔离验证通过 | 示例与 Settings 对齐；MEM0 仅加废弃说明保留原值；静态检查接 CI；启动摘要无密钥 |
| G1–G5 灰度 | 未开始 | 阶段 0、整理回滚、告警与观察周期均未完成；不启用新能力 |
| 4-A/B/C 收敛 | 未开始 | 保持方案的灰度稳定前置条件，不提前移除 legacy 或改变管理投影 |
| 4-D 文档/手册 | 部分准备 | 架构现状与本施工记录已同步；embedding 手册已有；迁移演练、整理回滚手册和完整阶段门禁证据仍待补齐 |

## 当前新增工具

仓库根目录执行：

```bash
UV_CACHE_DIR=/tmp/cygnusx-uv-cache uv run --frozen python scripts/check_env_example_drift.py
# 由验收环境的 Secret 注入 MEMORY_ACCEPTANCE_DATABASE_URL，不把 DSN 写进命令行或报告。
UV_CACHE_DIR=/tmp/cygnusx-uv-cache uv run --frozen python scripts/inspect_memory_baseline.py --output /tmp/memory-baseline.json
```

配置检查只读 Settings 源码和 `.env.example`，不加载真实 `.env`，MEM0_* 豁免。有效 MEMORY_/AGENT_MEMORY_ 示例必须对应 Settings 字段、默认值一致且不重复；旧无消费摘要变量现为注释。失败仅报告字段名和原因，不输出变量值。

对账工具要求显式专用 PostgreSQL DSN，不读默认 DATABASE_URL。所有查询处于只读可重复读事务，只输出聚合计数及版本，不查询记忆正文。超时/连接异常仅输出类型。未配置 DSN 返回 blocked/exit=2，本次实际结果亦如此；该结果不能计为真实演练通过。

## 本轮验证

- 配置检查与阶段 0 工具共 13 项单元测试通过，覆盖拒绝隐式生产 DSN、异常不回显凭据、拒绝非 PG、静态默认解析、未知/重复/缺失配置与默认漂移。
- 配置检查结合运行闸门 27 项测试通过；其中配置 10 项与上述 13 项重叠，不相加统计。
- 专项 Ruff 与两个新增脚本的 strict mypy 均通过；mypy 首次发现的列表推断问题已修复。
- 当前不执行新迁移、不启动生产或修改真实 `.env`。方案门禁 1/2 均未通过。

## 尚需环境与决策

需要已有预发布环境配置路径、同生产大版本 PG/pgvector 和快照副本、专用 Worker/Redis/Provider。密码/密钥由原 Secret 管理机制提供，不在聊天、文档或命令行回显。已向用户询问环境是否存在，代码独立工作继续推进。

方案列出的用户白名单、项目归档关联策略、archived_reason、整理快照保留期、legacy 退役日期、尾批阈值与告警接收渠道尚未裁定；实现时保持独立开关与方案安全默认，不推断生产授权或人为评分结果。

## 2-B / 3-A / 3-B / 3-C 本轮补齐

- 混合检索已同时读取当前模型向量候选与词面候选，按 RRF 合并；相似度下限未提供或模型不匹配时不启用混合路径，实际阈值仍须从案例基线校准。
- settle 改为先定位游标，再按 `(created_at, message_id)` 读取有界后续消息，并增加 `(session_id, created_at, message_id)` 索引；空闲扫描按未结算消息筛选，会话分批以避免堆积，默认关闭并受站点运行闸门保护。批次回执仍是写入幂等边界。
- 管理员可对单次整理 run 做 dry-run 和回滚；事实替代关系或块版本发生后续变化时整次回滚返回冲突。块快照恢复写新版本，回滚记录含管理员身份且不可重复执行。
- 召回回执按 14 天 TTL、每批最多 5000 条清理，时间索引与每日 Beat 任务已接。TTL 是否大于真实部署的所有重试/重投窗口尚未验证。
- 新增 settle 成功区间分母与记忆装配耗时直方图，便于后续计算失败率和 P95；指标 Worker 导出、仪表盘与告警仍未配置。

### 本轮验证

- 记忆/Chat/L4 后端相关单测 282 passed；前端记忆管理面板 DOM 测试 4 passed。
- Ruff、相关新代码 strict mypy、环境变量漂移检查、迁移链拓扑/单 head 与 `git diff --check` 通过。管理员用户路由全文件 mypy 仍报告原有未注解方法和旧 ORM update/delete 类型错误；新增端点本身无新增类型错误。
- 真实 PostgreSQL 快照迁移/回退、pgvector EXPLAIN、Worker/Beat/Provider 联调、25 案例基线、看板告警和生产灰度都未执行；G1–G5 仍未开始，新开关维持默认关闭。


## 1-A 本轮实现与回退边界

- 新增 `memory_focus_project01`，NULL/非 NULL 两部分唯一索引，不猜测回填旧焦点；存在项目块时 downgrade 明确拒绝。仅编写迁移，未执行真实 upgrade，未合并发布分支。
- `MEMORY_FOCUS_PER_PROJECT_ENABLED=false` 保持默认；开启后 user/agent/project 精确读写，无回退通用焦点。关闭恢复通用读写，项目数据保留。管理面关闭后保留的项目块只读，API 显式项目编辑被拒，避免操作通用块。
- settle 与工具传受控会话项目；管理 API 验证 UUID 与项目拥有者；共享块仍只写 NULL 项目。焦点首次写入懒创建，CAS/凭据/归档语义不变。
- 用户/管理员界面按项目分组，编辑携带选中块自己的 project_id/version；用户可明确清空块内容。新增无身份标签的 memory.focus_operations 指标。
- 独立 PG 用例为 `tests/integration/test_memory_focus_postgres.py`，只允许显式 `MEMORY_TEST_DATABASE_URL` 指向 memory_acceptance_test*；当前实际结果为 skipped，不能记为 PG 验收通过。


### 1-A 验证结果

- 17 份相关后端测试最终 239 passed（exit=0），包括真实 SQLite SQL/CAS、拥有者/开关检查与 settle 项目传递；旧测试 fake Settings/块字段随新 schema 补齐。
- 前端全量 91 files / 613 tests passed；npm run build（含 vue-tsc -b）成功。两个新增 DOM 用例验证分组、选中项目与版本、清空保存、开关关闭后的项目只读。
- 专项 Ruff、七文件 strict mypy、配置漂移检查、迁移链单 head、diff 空白检查通过。用户路由全文件 mypy 仍有 10 项既有用户管理方法类型错误；未宣称全仓类型门禁通过。
- 真实 PG 单例因缺专用 DSN skipped；完整快照演练、Provider/队列、质量基线与生产灰度门禁仍未过。后端退出仍有既有 OTel closed-stream 日志错误，pytest exit=0。


## 1-B 遗忘残留提示与人工清理

新增默认关闭 `MEMORY_FORGET_RESIDUAL_SCAN_ENABLED=false`、`MEMORY_FORGET_RESIDUAL_LIMIT=20`。
新增应用服务 MemoryResidualService 与带报告的 POST forget 接口；兼容 DELETE 仍为 204。
仅扫描本人当前可见范围的 active 块/事实/episode，最多 8 个转义词项、返回最多 20 个候选，
每条摘录 <=60 字，凭据规则命中则隐藏摘录。不会扫描其他项目/Agent、会话原文、Studio 或审计。

归档先完成，扫描置于保存点；可恢复扫描失败返回 failed，不假装没有残留，也不撤销归档。
前端明示词面扫描边界，块跳转已有 CAS 编辑，事实/episode 经第二次确认归档；清理后重新
扫描最初归档源，保留其他未处理提示。Agent 工具传受控会话分区，Chat 提示词不承诺全部清除。

新增 residual_hits/actions/scans 指标。点击接口校验本人已归档源和本人 active 目标，只记本人
报告的点击，不编辑/归档对象。点击/曝光比不是清理完成率、模型遵循率或去重用户率。
未新建迁移，未修改真实 .env 或开启站点/新开关；可选 archived_reason 尚未实现。


### 1-B 验证结果

- 18 份相关后端回归 249 passed，exit=0；后补外部用户目标点击拒绝断言后，10 项新增专项再过。SQL 测试验证归档保存、扫描保存点失败回滚、行/项目/用户隔离、转义与截取；HTTP 测试验证 404/422 与点击接口没有清理副作用。
- 前端全量 91 files / 615 tests passed；记忆面板 4 个 DOM 用例包含 2 个新增案例。候选摘录按纯文本展示，未确认不归档，不自动改写块；处理一项后重新扫描最初归档源，保留未解决提示。
- 新增服务/应用服务/工具/DTO/Settings 五文件 strict mypy、专项 Ruff、配置漂移检查与前端生产构建通过。后端仍有既有 OTel closed-stream 退出日志错误；全仓门禁/真实环境验收未因此改变。


## 2-A 模型隔离与向量维护

- 新增默认关闭 MEMORY_EMBEDDING_MODEL_FILTER_ENABLED，向量 SQL 只比较当前模型；不兼容/无向量行保留词面补位，legacy 回退也不比较旧向量。没有擅自上线完整 RRF 或调整排序权重。
- 新事实的向量/有效模型标识必须成对；不规范新输入降级为无向量事实。legacy 编辑关闭语义生成时清掉旧向量，避免新正文绑定旧向量。
- 新增 MemoryEmbeddingService 与 CLI，默认 dry-run；显式 DSN，Provider 只读同一库配置。mismatch 模式处理缺失/不兼容，每批最多 500，绑定目标模型，先做模型调用再条件写入；被归档/改正文/他人已回填的行跳过，生成失败保留原数据。
- 覆盖率采样独立默认关闭，analysis 任务复查运行闸门；指标含 mismatched/coverage/sample_timestamp、提交后的行结果，不把停采旧值当实时值。
- 实测发现 Vector.cosine_distance 的结果类型原是 Vector，现改为 Float，右侧参数仍 Vector；本轮增加结果处理器契约及知识召回回归。仅静态/隔离验证，未冒充真实 PG 证明。
- 新增 [换模型手册](../../../ARCHITECTURE_DESIGN/CygnusX_memory_embedding_operations.md)；没有显式维护 DSN 的本次 CLI dry-run 真实返回 blocked/exit=2。真实 PG 模型隔离/合成 EXPLAIN 测试已准备，但因缺 MEMORY_TEST_DATABASE_URL skipped；生产快照、真实 Provider、P95 与质量基线仍待验。


### 2-A 验证结果

- 新增模型/CLI/任务与向量契约、知识 SQL 回归专项 65 passed；扩大 23 份相关后端回归 284 passed、exit=0。首次 legacy 排序测试因两对象时间戳不同触发合法同分排序差异，已固定同一时间戳后验证不比较旧模型向量。
- 服务/任务/FactStore/Settings/CLI/Vector 七文件 strict mypy、专项 Ruff、配置漂移与 diff 检查通过。未改前端，不重跑前端验证；上一轮证据为 615 tests 与构建通过。
- 真实 pgvector 用例仍 skipped；实际 CLI dry-run 因缺显式维护 DSN 返回 blocked/exit=2。无生产向量回填、无排序效果结论、无灰度开关变更。门禁 1/2 仍未通过。
