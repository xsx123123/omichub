# AI 工作台（Studio）人机协作设计：权限模式 + 脚本审核 + 计划先行（2026-07-21）

## 1. 需求拆解

| 需求 | 现状 | 缺口 |
|---|---|---|
| 运行窗口：沙盒内跑命令 | ✅ 已有 `sandbox_execute` + `StudioTerminal`（xterm）+ 代码卡片输出区 | 无（满足） |
| 创建脚本先给用户看，审核后运行 | ❌ 工具即时执行 | **审批协议**（核心） |
| 用户可让 AI 改 / 自己改脚本 | 代码卡片可编辑、可重跑（用户手动） | 审核卡片需支持"编辑后批准"+"退回理由" |
| 关键操作需用户批准 | ❌ 仅 analysis_flow 有确认（内存态、仅任务提交） | 通用工具审批闸 |
| 完全放权：一键从原始数据到结果 | ❌ 无权限模式概念 | **会话级权限模式** |
| 分析先生成计划 | ✅ `update_plan` + 右栏待办面板 | 提示词约束（先做计划再动手） |
| 需求不清时与用户互动确认 | ❌ 无结构化澄清机制 | `ask_user` 工具 |

## 2. 权限模式（会话级）

`sandbox_meta.permissions = {"mode": "supervised" | "auto"}`，默认 `supervised`。

- **supervised（监督模式，默认）**：写/执行类工具需用户批准——`sandbox_execute`、`workspace_write`、`workspace_edit`、`artifact_register`。只读工具（`workspace_read/list`、`pipeline_query`、`knowledge_search`、`update_plan`、capabilities、`datahub_import`）直接执行。
- **auto（放权模式）**：全部工具即时执行，实现"原始数据 → 结果"一键式；顶栏有明显标识。

切换入口：Studio 顶栏开关 → `PATCH /studio/sessions/{id}/permissions {mode}` → 写 sandbox_meta；`GET /sessions/{id}` 返回 permissions。

## 3. 审批协议（核心新增）

### 3.1 SSE 事件（ChatChunk 新增 type）

- `approval_request`：`{approval_id, tool_call_id, tool_name, arguments, risk_hint, timeout_seconds}`
- `approval_resolved`：`{approval_id, tool_call_id, action: "approved"|"edited"|"rejected"|"timeout"}`

### 3.2 REST 端点（api/v1/studio.py）

- `POST /studio/approvals/{approval_id}/approve` body `{modified_args?: dict}` — 原样批准或带用户编辑后的参数批准
- `POST /studio/approvals/{approval_id}/reject` body `{reason?: str}` — 退回，理由回灌 LLM 让其修改后重试

### 3.3 存储与等待

- 记录存 **Redis**（`studio:approval:{id}`，TTL 1800s），多进程安全（规避 tool_confirmation_service 进程内内存的坑；顺带修 `ai.py:206` reject 非单例 bug）。
- chat_service 在 Studio 工具分支前插审批闸（supervised 且命中受控工具）：发 `approval_request` → `await` Redis BLPOP 等结果 → 批准则（用 modified_args）继续走 `stream_studio_tool`；拒绝则 result=`{success: false, rejected: true, reason}` 按普通 tool_result 回灌，AI 据此修改脚本后发起新一轮审批；超时按拒绝处理（reason="用户未响应（超时）"）。

### 3.4 ask_user 工具（澄清交互）

新增 Studio 内置工具 `ask_user(question, options?)`：执行即产生 `ask_request` 事件（复用 approval 通道：question 卡片）并以"本轮结束"收尾——用户在下一条聊天消息里回答，对话自然继续。避免新增一轮 REST 往返，协议最简。

## 4. 计划先行（提示词层）

更新 Studio 系统提示词后缀（`STUDIO_SYSTEM_PROMPT_SUFFIX`）：

1. 收到分析类任务，先 `update_plan`（3-8 步）再动手；
2. supervised 模式下，脚本类操作先说明意图再提交审批；
3. 需求/参数不明确（缺物种、缺文件、缺阈值）时先 `ask_user` 澄清，不要编造参数；
4. auto 模式下仍须先出计划，但不再等待批准。

## 5. 前端改动

- **顶栏权限开关**：supervised/auto 切换（auto 模式高亮警示色），调 permissions PATCH。
- **审批卡片**（KimiMessageItem 扩展）：`approval_request` 到达时工具卡片状态 `awaiting_approval`：Monaco 只读展示脚本（可切编辑）、按钮组【批准运行】【编辑后运行】【让 AI 修改（填理由）】；`approval_resolved` 更新卡片状态。
- **ask_user 卡片**：问题 + 选项快捷回复（点击即作为下一条消息发送）。
- `useAgentChatStream.ts` 新增三个事件 case；`agentHub.ts` 加审批状态与 approve/reject API 调用。
- 运行窗口复用现有 `StudioTerminal` + 代码卡片输出区，不新建。

## 6. 实施分期

| 期 | 内容 |
|---|---|
| P1（本次） | 后端审批协议 + 权限模式 + ask_user + 提示词；前端审批卡片 + 权限开关 |
| P2 | 审批超时策略配置化（studio.yaml）、审批历史落库、auto 模式操作审计 |
| P3 | 与 LangGraph interrupt 融合（HITL 节点替代手写等待）、checkpoint 断点恢复 |
