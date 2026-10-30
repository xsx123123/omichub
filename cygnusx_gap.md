# CygnusX 目标缺口审计（快照 2026-10-29）

> **文档性质**：一次性审计快照，不是 as-built 架构文档。架构现状以 `ARCHITECTURE_DESIGN/README.md` 索引下的文档 + 代码为准；本文只回答"哪些目标完成、哪些没完成、卡在哪里、如何关闭"。
>
> **审计基线**：分支 `feat/report-center-ai-linkage`，HEAD `919caa52`（2026-10-29），领先 `origin/main` 19 个提交。
> **审计范围**：`ARCHITECTURE_DESIGN/`（60+ 文档）、`wiki/`（62 页）、`README.md`、`TODO.md`、`docs/`（历史档案）、`evidence/`、关键源码与测试。
> **审计方式**：静态阅读 + 代码门禁核对 + 历史证据复核。**未执行**全量门禁、E2E、真实 PG/Celery/S3/Chromium 运行和任何写入型操作。

---

## 0. 证据等级与成熟度词表

| 等级 | 含义 |
| --- | --- |
| **A** | 本次审计直接核对代码/提交得出，可复现 |
| **B** | 文档或证据文件记录，但本次未复跑 |
| **C** | 只有计划/说法，没有任何验收记录 |

成熟度阶梯（贯穿全文）：

```text
implemented（有代码）
  ≠ isolated-tested（单测/静态检查通过）
  ≠ runtime-verified（真实依赖跑通）
  ≠ end-to-end-verified（浏览器/多服务全链路）
  ≠ production-approved（有人签字放行）
```

仓库里的"已完成"最多只到第一或第二级；本文凡写"完成"，均指该级。

---

## 1. 结论总览

| 域 | 已完成（代码+测试） | 进行中 | 被门禁阻断 | 未启动 |
| --- | --- | --- | --- | --- |
| 平台地基（认证/RBAC/模块/审计/限流） | ✅ | 部分口径待运行验证 | — | — |
| Agent 运行时（4 种闭环） | ✅ | 统一意图路由默认关 | 写工具门禁 | — |
| MCP / Skill / 沙箱 / Flow | ✅ | 版本治理、外部 MCP 运行验收 | 写入门禁 | MCP 第 2–4 阶段 |
| 科研闭环 M1 | 骨架 + 单测 | 运行验收 **PARTIAL** | 三处源码门禁 | 独立复现、真实语料 |
| 报告中心 | 首批功能 | P0 入口缺失等 | `project_report_write_enabled=False` | 原图重绘、版本关联 |
| 子 Agent 并行 | WP0–WP2 + 契约 | WP3 前端状态机 | `subagent_fanout_enabled=False` | WP4 全量验收 |
| 记忆与知识 | P0 修复 | 质量基线、生产指标 | `memory_v2_enabled=False` | 跨端连续性 |
| L4 协作室 | 房间/案例骨架 | 真实多 Agent 案例 | `mas_enabled=False` | 四个前置条件 |
| 本地客户端加密 | — | — | — | 整个阶段 0 |
| 双 Web 冗余 | ✅ 容器级 | — | — | 数据库/Redis/Nginx/宿主 HA |
| M2 / M3 | — | — | — | 2027-01-01 起 |

**总体判定：`NO-GO`（科研交付与写入路径）。** 与 `evidence/three-workpackages-current-status.json` 的 `overall` 一致：P0-A / IAT-R3 / G3-E2 / S4 四个工作包均为 `PASS_ISOLATED` + `runtime: BLOCKED`。

---

## 2. 已完成基线（可作为后续工作的起点）

以下条目同时具备代码与测试或证据，可作为"已完成"引用；但除特别说明外，均**不含运行验收**。

| 项 | 证据 |
| --- | --- |
| 认证/RBAC/模块门禁/审计/限流中间件链 | `src/cygnusx/middleware/`、`data/MODULE_LOCKED.yaml`（18 模块） |
| 4 种 Agent 执行闭环（Legacy ReAct / LangGraph / Studio Loop / Worker ReAct） | `data/ai/*.yaml`、`infrastructure/config/agent_loader.py` |
| 19 个已启用 Agent 装配 + 提示词共享片段注入 | `data/CygnusX.yaml` 的 `agents.enabled` |
| MCP 内置 Preset + 外部 Server 双表面 | `infrastructure/mcp/`、`tests/unit/test_mcp_dual_surface_parity.py`（8 通过，B） |
| 沙箱基线（uid 10001 / cap_drop=ALL / `/workspace/input` 只读） | `CygnusX_sandbox_architecture.md` |
| FlowFrame v2.0 六段式 Flow + `GenericFlowBuilder` + `TaskService.submit` 九步链 | `flows/*.yaml`、`CygnusX_flow_architecture.md` |
| 异步执行 reconcile-only + RocketMQ 双消费 | `infrastructure/celery_app/`、`task_queue/` |
| 身份/管理/ Cookie / 节日/通知/项目等业务域 | 对应 `application/services/` |
| 科研闭环 WP0–WP4 骨架（工作区归档、执行历史、环境还原、长任务三契约、Notebook 导出） | `wiki/research/plan-and-loop.md`、单测 |
| 报告中心首批：外部 Flow_report 导入（`7a930f57`）、Copilot 只读工具修复（`9f5832bd`）、查看页/选区（`b7482e6f`/`0642f5dd`） | git log + `CygnusX_report_center_architecture.md` |
| 性能项 #1/#2/#4/#6（详见 `TODO.md`） | `TODO.md` 勾选状态 |
| 双 Web 容器 + Nginx `least_conn` | `ARCHITECTURE_DESIGN/CygnusX_web_redundancy_architecture.md`（30/30 请求 200，B） |
| 71 个迁移至单 head `dwnscope06` | `scripts/check_migrations.py`（B） |
| 60+ 架构文档 + 62 wiki 页 | `ARCHITECTURE_DESIGN/README.md`、`wiki/_Sidebar.md` |

> 注意：双 Web 冗余只解决"同机 Web 容器故障"，不覆盖数据库、Redis、Nginx、宿主机，也不宣称吞吐翻倍或 10k RPS。

---

## 3. 详细缺口清单

### 3.1 M1 科研闭环运行验收（最高优先级）

最新运行验收记录：`CygnusX_Research_Feature_Runtime_Acceptance.md`，run `20261019-235848-bootstrap`，总体 **PARTIAL**，生产 **NOT_ACCEPTED**。

| ID | 缺口 | 证据 | 影响 | 关闭标准 |
| --- | --- | --- | --- | --- |
| **M1-01** | 当前源码未做全链路 E2E | 验收记录停在 2026-10-19；此后 19 个提交未回归 | 无法证明现有 HEAD 可跑通 | 在 HEAD 起真实栈，跑通"发现→预案→导入→Dataset 冻结→Handoff→Task→报告" |
| **M1-02** | RC04 只完成 31/34，FI01–FI06 未跑 | 同上验收文档 | 失败注入与边界场景未覆盖 | 补跑 3 项 RC04 + 6 项 FI |
| **M1-03** | 非空科研语料未验证 | 验收时 Task=0 / Report=0 / ExportJob=0 | "能跑"只是空库能跑 | 用真实 GSE/ENA 数据完成一次端到端 |
| **M1-04** | 科学正确性未验证 | 无 BioReport 科学结论验收 | 交付内容可能"形式对、结论错" | 人工复核一次完整 BioReport 的统计口径与结论 |
| **M1-05** | 独立复现未执行 | `reproduction_status=NOT_RUN` | 结果不可复现 | 换人/换机按 manifest 复跑并比对 |
| **M1-06** | 真实 PG/Celery/S3/Chromium 未验证 | 三工作包 runtime 全 BLOCKED | 生产风险未知 | 授权环境跑 `runtime-provenance-audit` 并出 GO |
| **M1-07** | 三工作包 NO-GO | `evidence/three-workpackages-current-status.json` | 写入路径不可开放 | P0-A / IAT-R3 / G3-E2 / S4 四个 runtime 转 PASS |

**三工作包各自缺失项（原文口径）**

| 工作包 | 孤立验证 | 运行验证 | 缺失 |
| --- | --- | --- | --- |
| P0-A | PASS_ISOLATED | BLOCKED | 授权独立 PostgreSQL 并发与迁移演练 |
| IAT-R3 | PASS_ISOLATED | BLOCKED | 当前源码的 listening API/Node/PG/Redis + Chromium 业务流 |
| G3-E2 | PASS_ISOLATED | BLOCKED | Linux Supervisor 强制 + 九个真实 HTTP 场景 |
| S4 | PASS_ISOLATED | BLOCKED | 授权 PG/Broker/Worker/Beat 故障窗口 |

### 3.2 报告中心

`TODO.md` 的 P0 复选框仍全空，但代码已有部分落地，需要按实际状态修正。

| ID | 缺口 | 证据（A/B） | 影响 | 关闭标准 |
| --- | --- | --- | --- | --- |
| **RPT-01** | "进入工作台优化"入口实际不可点 | A：`ReportCardMinimal.vue:24` 声明 `optimize`，但全文无 `emit('optimize')`；`ReportsView.vue:290` 已接 `@optimize`，`:114` 有 `handleOptimize` | 卡片上无按钮，功能对用户不可见 | 卡片补按钮并接通 `createSessionFromReport` |
| **RPT-02** | "工作台接入完整分析数据"未验收 | B：后端 `studio_context_service.py:166-196` 会把**全部** `report.files` 软链到 `input/`，但无验收记录 | 无法证明 DEG/GO/KEGG 真能被 Agent 读取 | 用含多文件的真实报告验证挂载清单与可读性 |
| **RPT-03** | 未区分"原图提取"与"重新绘图" | A：无相关代码分支 | 优化产物可能覆盖原图语义 | 增加产物类型标记与分支文案 |
| **RPT-04** | 优化产物未登记、未关联报告版本 | A：`flow_report_import_service.py:324` 只做导入登记；无版本回写 | 优化结果无法追溯来源报告 | 产物登记 + 报告版本关联字段与 UI |
| **RPT-05** | 无图表/对比/GO/KEGG 选择器 | B：`TODO.md` P1 | 交互颗粒度不足 | 按图/表/章节选择送入工作台 |
| **RPT-06** | 旧会话复用体验未验证 | B：仅新建 session 路径 | 重复优化会产生大量会话 | 支持复用/续接并验证 |
| **RPT-07** | 导入无删除/抑制/归属校验加固 | A：导入循环只新增，未见删除或抑制逻辑 | 错误导入无法清理，可能串号 | 补删除/抑制语义 + owner 校验用例 |
| **RPT-08** | 导入缺可观测性 | A：无导入指标/审计埋点证据 | 失败难定位 | 增加结构化日志与计数 |
| **RPT-09** | 大报告预算未定 | B：无体积/文件数上限记录 | 可能打爆工作区 | 定义并测试上限 |
| **RPT-10** | 扩展矩阵（多 Flow 报告）未验证 | C | 只覆盖单一报告类型 | 用 2+ 类 Flow 报告验证 |
| **RPT-11** | 前端存在存量失败与类型债 | B：验收记录 9 失败/16 跳过；mypy 997 项 | 局部全绿不代表 CI 绿 | 先修与报告页相关的失败项 |
| **RPT-12** | 预览受限 | A：82 MiB 上限 + CSP/opaque-origin 限制 | 超大报告无法预览 | 明确降级策略与提示 |
| **RPT-13** | 回填脚本未执行 | B：脚本存在，无执行记录 | 历史报告缺新字段 | 在授权环境跑一次并记录 |

> **文档债提醒**：`TODO.md` 把这些标为"未开始"，但 RPT-01/02 的后端与视图接线已存在，属于"部分实现 + 未验收"，直接照 TODO 施工会重复劳动。

### 3.3 子 Agent 并行（fan-out）

代码已落地 WP1/WP2（提交 `a2f14ea1`，2026-10-28），但 `TODO.md` 仍写"待启动"，P0 全未勾选。

| ID | 缺口 | 证据 | 影响 | 关闭标准 |
| --- | --- | --- | --- | --- |
| **SUB-01** | 文档状态与代码不符 | A：`a2f14ea1` 已实现契约；`TODO.md` 未更新 | 决策基于错误信息 | 修正 TODO 状态 |
| **SUB-02** | 前端状态机不完整 | A：`useAgentChatStream.ts:918-921` 只把 `started` 映射为 `queued`，无 verified/partial/artifact/replay 展示 | 用户看不到子任务真实进度 | 补齐完整状态机与 UI |
| **SUB-03** | WP4 全量验收未跑 | B：R01–R34 / Gate0–5 无执行记录 | 契约只是"写着" | 按用例表全跑并留证 |
| **SUB-04** | 无子任务 span / 追踪 | A：未见 sub-task span 实现 | 故障无法定位到子任务 | 接入 tracing |
| **SUB-05** | schema 与运行时上限不一致 | A：schema `maxItems` 2000 字符级 vs 服务端 20000 字符口径需对齐核查 | 长任务被截断或误拒 | 统一上限并加用例 |
| **SUB-06** | 默认关闭 | A：`config.py:352 subagent_fanout_enabled=False` | 功能对用户不可达 | 验收后灰度开启 |
| **SUB-07** | 剩余覆盖缺口 | B：`docs/subagents/02_capability_matrix.md` 中 R17–R19（span）、R28–R33（UI）、R04/R05（幂等） | 局部行为未守 | 补测试 |
| **SUB-08** | 文档 05/06 缺失 | B：`docs/subagents/` 只有 01–04 + 索引 | 验收与发布无据 | 补写并评审 |

已实现且可引用的部分（A）：`parallel_subagent_service.py:632` 结果聚合、`:1109` `outcome_status`、`:1164` 四阶段产物发布、`:2004+` 能力预检 `CAPABILITY_MISSING`；`tests/unit/test_parallel_subagent_service.py` 51 用例。

### 3.4 记忆与知识

| ID | 缺口 | 证据 | 影响 | 关闭标准 |
| --- | --- | --- | --- | --- |
| **MEM-01** | 25 条记忆质量基线未建立 | B：`CygnusX_memory_optimization_audit.md` | 无法判断检索是否变好 | 建立基线集与评分 |
| **MEM-02** | 生产指标缺失 | C | 线上表现未知 | 采集命中率/延迟/覆盖率 |
| **MEM-03** | L4 / Chat / Studio 记忆连续性未验证 | C | 跨端体验断裂 | 跨端脚本验证 |
| **MEM-04** | 项目隔离负向用例不足 | B：部分 `project_id` 已落 | 存在串项目风险 | 补越权召回用例 |
| **MEM-05** | settle tail 未在真实 Worker/Beat 验证 | A：`config.py:326 memory_settle_tail_enabled=False` | 尾差可能丢失 | 开小流量观测 |
| **MEM-06** | 恢复演练未做 | C | 崩溃后状态未知 | 演练并留证 |
| **KNOW-01** | 正式库 367 文档 / 2778 分块未向量化 | B：无执行记录 | 知识库检索覆盖不足 | 跑 `make sync-knowledge` 并核对 |
| **KNOW-02** | 自动重建默认行为不确定 | A：`config.py:283 knowledge_auto_reindex_enabled=True`，但 Web 环境变量据文档为 false | 配置漂移 | 统一配置并验证 |
| **KNOW-03** | 生产规模未压测 | C | 容量未知 | 按真实文档量压测 |

> 记忆相关门禁：`memory_v2_enabled=False`（`config.py:292`），语义检索、冲突裁决、混合检索、embedding 过滤、覆盖率、forget 残差扫描均为 False。

### 3.5 L4 协作室

`CygnusX_platform_vision.md:117-134` 的四个前置条件均未满足：

1. 地基仍在进行中（M1 未 GO）；
2. Agent 升级规则未定义；
3. 双注册表（`data/ai` 与 DB）待核查；
4. 可观测性仅部分覆盖。

| ID | 缺口 | 证据 | 关闭标准 |
| --- | --- | --- | --- |
| **L4-01** | 四前置条件未闭环 | B：vision 文档 | 逐条给结论 |
| **L4-02** | Bridge work-items 403 只做了退避 | A/B：修复提交 `db43d5fe` 仅退避，未解根因 | 定位并修复鉴权根因 |
| **L4-03** | 真实多 Agent 案例与故障恢复未验证 | C | 跑通并注入故障 |
| **L4-04** | 设计文档废弃但代码仍是现状 | B：`agentteams_*` 文档已废弃 | 补一份 as-built 说明 |

相关门禁：`mas_enabled=False`（`config.py:265`），`multi_expert_consultation_enabled=False`（`:337`）。

> 注意：`mas/mas_room_service.py` 现在会启动/续跑 MAS run，`CygnusX_architecture_coverage_audit.md` 中"只持久化发言"的表述已过时。

### 3.6 安全与运维

| ID | 缺口 | 证据 | 影响 | 关闭标准 |
| --- | --- | --- | --- | --- |
| **SEC-01** | 本地客户端加密零落地 | A：无 tauri、无 `client/bootstrap`、无 `cluster/heartbeat`、无 `cluster_nodes`、无 `ClientCert`/Device 模型；仅下载 supervisor 有 mTLS 片段 | 12 月计划整体未启动 | 从阶段 0 开始 |
| **SEC-02** | TOTP 仅 3 处 | A：覆盖面窄 | 高权限操作保护不足 | 扩展到管理端 |
| **SEC-03** | 前端无管理员角色守卫 | A：仅后端拦截 | 越权页面可见 | 加路由守卫 |
| **SEC-04** | 中间件顺序隐患 | A：`CookieRequired` 先于 Auth 空闲校验；`ModuleGate` 疑似 fail-open | 可能绕过或误放 | 补用例并修正 |
| **OPS-01** | 通知靠 60s 轮询 | A：无 SSE | 延迟高 | 评估 SSE |
| **OPS-02** | `schedules` 队列无消费者 | A | 定时任务不执行 | 补 worker 或移除队列 |
| **OPS-03** | Task cookie 计费无幂等，`TaskCookieConsumer` 未接线 | A | 重复计费风险 | 幂等键 + 接线 |
| **OPS-04** | goal 的 Redis/DB 租约不一致 | A | 状态漂移 | 统一租约源 |
| **OPS-05** | ingest HMAC 可选 | A | 弱校验 | 强制校验 |
| **OPS-06** | RocketMQ 忽略 `task_routes` | A | 路由错配 | 对齐路由 |
| **OPS-07** | Beat 单实例、无积压告警 | A/B | 单点 + 静默失败 | 加告警与恢复预案 |

门禁：`goal_runtime_enabled=False`（`config.py:277`），`goal_fanout_enabled=False`（`:278`）。

### 3.7 性能与容量

| ID | 缺口 | 证据 | 关闭标准 |
| --- | --- | --- | --- |
| **CAP-01** | 1500/2000/10k RPS 目标未通过 | B：无压测记录 | 分级压测并留证 |
| **CAP-02** | DB/Redis/Nginx/宿主均为单点 | B：冗余文档自述 | 明确 HA 方案或写清不可用边界 |
| **CAP-03** | 动态模型路由默认关且被旁路 | A：`config.py:69 dynamic_model_routing_enabled=False`；Legacy/overdrive 路径绕过 | 统一入口或明确例外 |
| **CAP-04** | 主 Chat 上下文装配串行 | A | 并行化并测延迟 |
| **CAP-05** | 磁盘清理未落地 | B：`TODO.md` | 实现定时清理 |
| **CAP-06** | 每 Agent `max_tokens` 评估未做 | B | 出评估表 |
| **CAP-07** | 在线缓存命中率未观测 | B | 接入指标 |

> `ROUTER_MAX_TOKENS=10000` 属受保护常量，不要在容量优化中顺手改。

### 3.8 项目 / 存储 / MCP

| ID | 缺口 | 证据 | 关闭标准 |
| --- | --- | --- | --- |
| **PRJ-01** | 项目评审建议未实现 | B | 实现并入 UI |
| **PRJ-02** | F01–F03 测试计划未执行 | C | 执行并留证 |
| **PRJ-03** | 导出/报告写入默认关闭 | A：`config.py:97/99/100` | 验收后开启 |
| **STO-01** | 存储 Gap 3 前缀策略未决 | B：存储架构文档 | 定策略并迁移 |
| **STO-02** | Phase 4 注册表未完成 | B | 完成注册表 |
| **MCP-01** | 去固化第 2–4 阶段未做 | B：`CygnusX_mcp_architecture.md` | 按阶段推进 |
| **MCP-02** | MCP 版本治理缺失 | B | 版本锁定与回滚 |
| **MCP-03** | 外部 MCP / HTTP、STDIO 真实链路未验收 | B/C | 真实 server 联调 |

### 3.9 已规划但未启动

| ID | 项 | 依据 | 说明 |
| --- | --- | --- | --- |
| **PLAN-01** | M2 | `CygnusX_platform_next_stage_roadmap.md` | 2027-01-01 起，尚未设计 |
| **PLAN-02** | M3 | 同上 | 更远期 |
| **PLAN-03** | TODO-1A / 1B | `docs/todo/roadmap_todo_review_2026-09.md` | 零代码 |
| **PLAN-04** | TODO-4 | 同上 | 零痕迹 |
| **PLAN-05** | TODO-3 | 同上 | 存在许可证冲突（Apache-2.0 + Commons Clause） |
| **PLAN-06** | 技能优先沙箱 | B | 未开始 |
| **PLAN-07** | 领域提示词沉淀 | B | 未开始 |
| **PLAN-08** | 助手聊天 UI 统一 | `TODO.md` | 未开始 |
| **PLAN-09** | 本地客户端加密全阶段 | `TODO.md` + A 级 grep 结论 | 阶段 0 都未开始 |

**PLAN-05 需要单独注意**：许可证冲突属法务问题，不是代码问题，不应在技术排期里被默认消化。

---

## 4. 源码门禁矩阵（A 级，改配置也绕不过）

| 门禁 | 位置 | 值 | 后果 |
| --- | --- | --- | --- |
| `WRITE_RUNTIME_ACCEPTED` | `application/services/agent_tool_gateway.py:47` | `False` | 所有 Task 写入拒绝 |
| `DOWNLOAD_TRANSPORT_RUNTIME_ACCEPTED` | `infrastructure/download/policy.py:18` | `False` | 传输层不可用 |
| `worker_paths_verified` | `dataset_handoff_service.py:313`、`dataset_analysis_service.py:282/481` | `False` | Handoff 不是 READY |
| `tool_gateway_read_enabled` | `core/config.py:84` | `False` | Gateway 只读关闭 |
| `research_plan_enabled` | `core/config.py:87` | `False` | ResearchPlan 默认关 |
| `research_delivery_read_enabled` | `core/config.py:94` | `False` | 交付链只读关闭 |
| `research_delivery_write_enabled` | `core/config.py:95` | `False` | 交付链写入关闭 |
| `project_export_enabled` | `core/config.py:97` | `False` | 导出关闭 |
| `project_report_write_enabled` | `core/config.py:99` | `False` | 报告写入关闭 |
| `project_report_pdf_enabled` | `core/config.py:100` | `False` | PDF 关闭 |
| `agent_download_write_enabled` | `core/config.py:131` | `False` | Agent 下载写关闭 |
| `agent_analysis_write_enabled` | `core/config.py:132` | `False` | Agent 分析写关闭 |
| `agent_task_cancel_enabled` | `core/config.py:133` | `False` | Agent 取消任务关闭 |
| `flow_report_import_enabled` | `core/config.py:171` | `False` | 报告导入关闭 |
| `dynamic_model_routing_enabled` | `core/config.py:69` | `False` | 动态路由关闭 |
| `memory_v2_enabled` | `core/config.py:292` | `False` | 记忆 v2 关闭 |
| `subagent_fanout_enabled` | `core/config.py:352` | `False` | 并行子 Agent 关闭 |
| `mas_enabled` | `core/config.py:265` | `False` | 协作室关闭 |
| `goal_runtime_enabled` | `core/config.py:277` | `False` | Goal 运行时关闭 |
| `unified_intent_router_enabled` | `core/config.py:349` | `False` | 统一意图路由关闭 |

> 结论：**当前仓库的"能力"是"代码在，门关着"。** 任何把功能说成"已上线"的表述都需要先解释这些常量。

---

## 5. 文档债与陈旧表述

| ID | 问题 | 位置 | 处理 |
| --- | --- | --- | --- |
| **DOC-01** | 子 Agent TODO 仍写"待启动" | `TODO.md` | 按 `a2f14ea1` 更新 |
| **DOC-02** | MAS 房间描述过时 | `CygnusX_architecture_coverage_audit.md` | 改为"已启动/续跑 run" |
| **DOC-03** | Legacy AI 残留未说明 | `api/v1/ai.py`、`GlobalAiAssistantSidebar.vue` | 标注 deprecated 或删除 |
| **DOC-04** | claims 端点未进交付文档 | `research/claims` API | 补文档 |
| **DOC-05** | 提示词管理（DB 发布）未成文 | `agent_loader.py` + 管理端 | 补 as-built |
| **DOC-06** | 最新验收证据停在 10-19/20 | `evidence/`、`ARCHITECTURE_DESIGN/` | 重跑后更新，不要用旧证据 |
| **DOC-07** | Worker 镜像计划无闭环验收 | `deploy/` 相关计划 | 补验收或标记未验证 |
| **DOC-08** | `make sync-knowledge` 未执行 | `TODO.md` | 跑完记录结果 |
| **DOC-09** | 历史证据不可提升 | `evidence/runtime-acceptance/results.json` 的 PASS_RUNTIME 属旧 RI09.5 | 明确不得作为当前验收 |

> `ARCHITECTURE_DESIGN/deprecated/`、`CygnusX_studio_handover.md`、任何 `*_plan`/`vision_2026-*` 提案都不能当作现状依据——这条在本次审计中被多次触发，建议在文档首页加固定提示。

---

## 6. 建议推进波次

### 波次 1：M1 闭环（阻塞一切对外承诺）
1. 在 HEAD 起真实栈，复跑 `20261019-235848-bootstrap` 同等验收。
2. 补 RC04 3 项 + FI01–FI06。
3. 用非空语料跑通一次完整科研交付。
4. 四工作包 runtime 逐项转 PASS，更新 `three-workpackages-current-status.json`。

### 波次 2：报告中心 P0 + 文档同步
1. 修 RPT-01（补按钮），验收 RPT-02。
2. 落 RPT-03/04 的产物类型与版本关联。
3. 同步 `TODO.md` 与 SUB 状态，消除 DOC-01/02。

### 波次 3：安全与运维债
SEC-01 阶段 0 → SEC-02/03/04 → OPS-01…07。这些是"不修就会在真实流量下爆炸"的项。

### 波次 4：质量验收
子 Agent WP3/WP4、记忆 25 用例基线、知识库向量化、L4 真实多 Agent 案例。

### 波次 5：容量与 HA
CAP-01…07，以及是否真的要做数据库/Redis/Nginx/宿主 HA——先决策，再排期。

### 波次 6：计划阶段
M2/M3、TODO-1A/1B/3/4、技能优先沙箱、领域提示词、UI 统一、客户端加密。

---

## 7. 复验清单（建议在授权环境执行）

```bash
# 静态
uv run ruff check src/ tests/ && uv run mypy src/cygnusx/
uv run python scripts/check_migrations.py
uv run python scripts/check_schema_drift.py        # 需真实库

# 单测
uv run pytest tests/unit -q -m "not quarantine"
uv run pytest tests/e2e -q -m "not quarantine"

# 前端
cd frontend && npm run type-check && npm test -- --run && npm run build

# 运行验收
uv run python scripts/...                          # runtime-provenance-audit 同类脚本
```

**已知历史结果（B，仅作对照，不是当前结论）**

| 门禁 | 最近记录 |
| --- | --- |
| ruff | 267 / 277 项（两次记录） |
| mypy | 983 / 997 项 |
| unit | 4244 通过 / 13 失败 / 16 跳过；另一 run 3755 通过 / 9 失败 / 16 跳过 |
| frontend | 90 文件 / 611 用例通过；build 通过 |
| migrations | 单 head `dwnscope06` |

> 两套数字来自不同时间点，不能混用；也不存在"全仓全绿"的记录。

---

## 8. 本次审计的限制

1. **纯静态**：未执行任何会写库、发消息、改配置的操作。
2. **未跑全量门禁**：第 7 节的命令是建议，不是本次结果。
3. **未复跑 E2E**：所有"运行验收"结论均转引自 `evidence/` 与架构文档。
4. **子模块未审计**：`pipelines/Treasure-Seeking_Mouse` 处于 dirty 状态（`m`），其内部改动不在本次范围。
5. **19 个提交未合入 main**：本文结论只对 `feat/report-center-ai-linkage@919caa52` 成立。
6. **故意不做的判断**：不评估代码质量、不评估科学正确性、不评估许可证合规（PLAN-05 仅提示）。
7. **"完成"的下限**：本文所有 ✅ 最多表示 isolated-tested，不表示 runtime-verified。
