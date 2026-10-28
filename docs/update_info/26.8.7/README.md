# AI 三模式排查与优化建议(2026-08-06)

本次对 OmicHub AI 工作台的三种模式做了全面代码审查(只读,未改动代码),所有结论均有 `文件:行号` 级证据。

> 实施状态更新（2026-08-06）：本目录所列 P0/P1/P2 中 Task 1–13 已完成并完成对应定向验证；Task 14 已输出设计说明，等待产品/架构确认后实施。

## 三种模式定位

| 模式 | 前端入口 | 后端链路 | 说明 |
|---|---|---|---|
| 1. 简单 AI 助手 | `/ai` → `AIChatView.vue` | `POST /chat/stream` SSE → `ChatService._route_to_agent` → 专家 agent | router 单次分派;另有 WS Copilot 旧链路 `api/v1/ai.py` |
| 2. AI 工作台 | `/studio/:sessionId?` → `StudioView.vue` | 复用 `/chat/stream` + 每会话 Docker 沙盒(`studio-{session_id[:8]}`),经 Unix Socket 直连容器内 `sandbox_agent.py` | agent 在沙盒中执行代码/文件/MCP |
| 3. AgentTeams | `TasksView?tab=agent-teams` → `/agent-teams/cases/:caseId` | 超频轮(overdrive)+ Matrix room gateway + Bridge case 服务 + celery watch | 多 agent 协作编排 |

模式 1/2 共用同一个全局 Pinia store `agentHub`,靠 `session.mode` 区分;模式 3 基本独立。

## 文档索引

- [01_跨模式共性问题.md](./01_跨模式共性问题.md) — 三种模式共享的系统性根因(事务、并发、SSE、用量统计)
- [02_模式1_AI助手与路由.md](./02_模式1_AI助手与路由.md) — 路由决策、handoff、WS Copilot 旧链路
- [03_模式2_AI工作台Studio.md](./03_模式2_AI工作台Studio.md) — 沙盒生命周期、审批、工作区清理
- [04_模式3_AgentTeams.md](./04_模式3_AgentTeams.md) — 问题最集中的模式,含设计与实现差距
- [05_前端与基础设施.md](./05_前端与基础设施.md) — 前端流式实现、鉴权、已有审查未修复项
- [gpt5.6_implementation_prompt.md](./gpt5.6_implementation_prompt.md) — 供后续 AI 实施修复的详细提示词

## 修复优先级总览

### P0 — 立刻修(成本低、影响大)

1. **[已修复] 流式 token 用量统计丢失**：`litellm_provider.py` 已注入 `stream_options={"include_usage": True}`。
2. **[已修复] AgentTeams 确认卡语义过弱**：仅接受带一次性 token 的结构化确认，不再将任意文本视为授权。
3. **[已修复] 直接 API `POST /agent-teams/cases` 绕过校验**：创建前验证正式 `projects` 记录属于当前用户，并执行 flow 白名单校验。
4. **[已修复] Provider 重试时无条件丢弃 tools**：网络类重试保留 tools，仅兼容性空响应降级移除。
5. **[已修复] degraded `mode_changed` 重复发送**：同一退化周期仅发送一次。

### P1 — 本迭代修(数据正确性)

1. **[已修复] AgentTeams room-events**：cursor 和回流消息即时提交，并以 `matrix_event_id` 建立幂等去重。
2. **[已修复] 前端 room-events 订阅**：建房后重新订阅，断线采用退避重连并在健康 SSE 下暂停轮询。
3. **[已修复] Studio 断连杀沙盒子进程**：流生成器清理时终止进程组。
4. **[已修复] Studio 审批链路**：等待期间发送 SSE 心跳；无活跃流时前端阻止恢复审批。
5. **[已修复] 聊天流关键节点持久化**：用户消息、handoff 审计和 artifact 报告均通过独立 session 提交；artifact 提交失败会清理已复制文件。

### P2 — 架构层面排期

1. **[待设计确认] `sandbox_meta` 拆分**：已输出独立列迁移、回填与回滚设计，尚未实施。
2. **[待设计确认] 会话级流式并发锁**：已设计 Redis 锁、续租与 409 冲突契约，尚未实施。
3. WS Copilot 旧链路收敛,明确模式 1 唯一正统入口。
4. 前端四套流式实现统一(行前缀规则不一致会静默丢事件)。
5. Studio 工作区磁盘清理任务(注释承诺的"7 天清理"逻辑不存在)。
6. **[已修复] case watch**：已加 JSONB 过滤、Redis 分布式锁和 ERROR 级异常日志；队列迁移暂不改动。

### 顺带排期(与三模式无关,既有审查遗留)

- Refresh Token 无轮换可重放(`auth_service.py:194-220`,report/05 A-2)。
- API Key 加密密钥单点不可轮换(report/05 F-1/F-2,加密已做,密钥治理未做)。

## 各模式问题数量分布

| 模式 | 高 | 中 | 低 |
|---|---|---|---|
| 模式 1 AI 助手 | 4 | 12 | 4 |
| 模式 2 工作台 | 4 | 9 | 8 |
| 模式 3 AgentTeams | 4 | 6 | 10 |
| 前端/基础设施 | 5 | 5 | 4 |
