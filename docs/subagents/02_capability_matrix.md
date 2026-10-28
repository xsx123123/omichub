# 子 Agent 能力矩阵（WP0）

> 日期：2026-10-28｜基线 commit `51003efa`。本矩阵描述**装配后有效工具域**（以 `parallel_subagent_service._prepare_child_tools` 的过滤逻辑为准），非 YAML 声明。
> 生成方式：静态代码推导 + 既有单测佐证；未做运行时 dump。WP1 应补运行时实测列并替换本表「待运行时验证」标注。

## 1. 全局工具过滤规则（`_prepare_child_tools`，parallel_subagent_service.py:555-652）

子任务有效工具 = 按以下顺序处理：

1. 目标 Agent `assemble_context` 装配出的工具（`ctx.tools`），仅保留 `schema.invocation_mode == "backend_sync"` 的注册工具（`analysis_flow` 等长管道被剥，`:620-622`）；未注册且无 MCP/skill 身份的工具被剥（`:623-629`）。
2. 追加（若缺失）：`ask_user`、`knowledge_search`；`web_search` 仅在 Agent features 未禁用联网时追加（`:583-595`）。
3. 剥离控制工具（`:61-72`）：`parallel_subagents`（防递归）、`skill_route`、`transfer_to_agent`、`create_agentteams_case`、`cygnusx_save/update/forget_memory`；AgentTeams Manager 会诊豁免记忆三件套（`:77-84, :614-617`）。
4. `safe_only=True`：仅保留 `ask_user/knowledge_search/web_search/skills` + 带 `readOnlyHint` 且无 `destructiveHint` 的 MCP 工具 + 注册 schema 中 `read_only_hint` 且 `requires_confirm=False` 的工具（`:630-641`）。
5. `workspace_access=True 且非 safe_only`：追加 `_OVERDRIVE_WORKSPACE_TOOL_NAMES`（`:90-102, :643-651`）：
   `sandbox_execute / workspace_write / workspace_edit / workspace_read / workspace_list / datahub_import / platform_result_import / artifact_register / pipeline_query`（不含 `update_plan`）。

AgentTeams 会诊上下文（`agentteams_ctx_var.room_id` 存在）额外注入只读房间工具 `room_messages_read / room_facts_query`（`:564-577`）。

## 2. Agent × spawnable × 模式矩阵

| Agent (registry ID) | spawnable | 普通 fan-out | safe_only 会诊 | 超频 workspace_access | AgentTeams workspace_execution |
|---|---|---|---|---|---|
| code | ✅ | 仅只读/检索/skills，**无执行器** | 只读集 | + 沙盒执行/工作区写 | + 沙盒执行/工作区写 |
| data | ✅ | 同上 | 只读集 | + 工作台集 | + 工作台集 |
| qc | ✅ | 同上 | 只读集 | + 工作台集 | + 工作台集 |
| viz | ✅ | 同上 | 只读集 | + 工作台集 | + 工作台集 |
| atacseq / rnaseq | ✅ | 同上 | 只读集 | + 工作台集 | + 工作台集 |
| cloud_ops / delivery / general | ✅ | 同上 | 只读集 | + 工作台集 | + 工作台集 |
| scrna / scrna_advanced / scrna_integration / scrna_upstream | ✅ | 同上 | 只读集 | + 工作台集 | + 工作台集 |
| agentteams_manager | ❌ | 拒绝（SUBAGENT_NOT_SPAWNABLE） | —（自身即 Manager） | — | — |
| explorer | ❌ | 拒绝 | 单任务豁免可派（allow_non_spawnable_target） | — | — |
| shania | ❌（未声明） | 拒绝 | 单任务豁免可派 | — | — |

「单任务豁免」= `allow_non_spawnable_target and safe_only and len==1`（`:321-323`），当前仅 AgentTeams 只读会诊路径使用（`agent_consultation_service.py`）。

## 3. 能力 → 工具映射与缺口

| Capability（方案 §3.1） | 满足条件（当前代码） | 普通 fan-out 是否可达成 |
|---|---|---|
| `research.retrieve` | knowledge_search / web_search 恒注入 | ✅ |
| `workspace.read` | workspace_read/list 仅 workspace_access 模式 | ❌（普通模式无工作区工具） |
| `python.execute` | sandbox_execute 仅 workspace_access 模式 | ❌（code Agent 普通模式无执行器 → 与「code 无执行器」证据吻合） |
| `artifact.write` | workspace_write/edit 仅 workspace_access 模式；`subagent_workdir` extra 无消费方 | ❌ |
| `artifact.publish` | artifact_register 仅 workspace_access 模式；且产物闭环未实现 | ❌ |
| `approval.request` | requires_confirm 工具在子循环升级为 approval_pending 升级包回 Manager（`:1159-1183`） | ⚠️ 有升级通道，但子循环内不执行需审批工具 |

## 4. 产物写权限结论

- 普通聊天 fan-out：子任务**无任何受控写文件通道**；唯一副作用面是 MCP 写工具（若有）与 memory 工具（已剥）。产物型任务在普通模式必然失败，但当前会以 `ok` 假成功（审计文档 §3.1）。
- 超频前台/后台与 AgentTeams workspace_execution：具备沙盒执行与工作区写，但产物留在子 workdir/沙盒，**无登记/发布/父回读**（审计文档 §3.4）。
- 各模式有效工具集的**运行时 dump** 尚未采集（WP1 Gate 0 测试 R06/R08/R11 时输出实测清单，替换本静态推导表）。
