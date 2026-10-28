# 任务：实现受控 Agent Gateway 与 scientific-interpretation Skill

> 本文件是给 AI 编码助手（ChatGPT 等）的实施提示词，配套设计文档为
> `docs/26.8.1/AgentTeams_非侵入式多Agent协作编排实施方案.md`。

## 背景

你在 OmicHub 仓库中工作。OmicHub 是一个多组学生信分析平台（FastAPI + Celery + Snakemake + Vue3）。
我们正在落地「AgentTeams 非侵入式多 Agent 协作编排」方案，设计文档为：

- `docs/26.8.1/AgentTeams_非侵入式多Agent协作编排实施方案.md`（先完整阅读，特别是 §1.1.1、§4、§5.2、§7.2、§9.2、§14）

已落地的部分：独立 Bridge（`integrations/agentteams/bridge/`）、OmicHub 受控代理
`/api/v1/agent-teams`、前端 `/agent-teams` 协作中心、Skill 契约
（`integrations/agentteams/skills/contracts.yaml`）。

## 你要实现的

目标链路中缺失的一环：

```text
AgentTeams Manager → 受控 Agent Gateway → 现有 OmicHub 专业 Agent
                   → 结构化科学解读/建议/证据 →（人工审批后由 Workflow Operator 提交任务）
```

交付物（新目录 `integrations/agentteams/gateway/`）：

1. **Gateway 服务**：独立可部署服务（与 Bridge 同级，不侵入 OmicHub 主代码），暴露
   `scientific-interpretation` Skill 的 REST 接口，供 Manager 按白名单调用现有专业 Agent
   （`agent-rnaseq`、`agent-scrna`、`agent-viz` 等，配置驱动可扩展）。
2. **白名单与只读策略**：每个可调用的专业 Agent 配允许的能力范围（解释/计划建议/结果解读/QC 建议）
   与允许的工具白名单（只读 MCP 工具，如 ensmbl 的 lookup_gene/search_genes）；
   禁止任务提交、取消、写文件、数据库访问、shell。
3. **固定输出 Schema**：返回 `{schema_version, conclusion, recommendations[], evidence_refs[], risks[],
   agent_id, schema_ver, duration_ms, token_usage}`，不返回原始会话、工具调用记录或原始文件内容。
   失败时返回 `manual_review` 状态，绝不降级为自动执行。
4. **成本护栏**：单次调用超时（默认 120s 可配）、每 Case 调用次数上限（默认 5）、每 Case token
   上限（默认 200k），超限返回结构化拒绝。
5. **审计事件**：每次调用写 `agent.consultation` 事件（case_id、目标角色、问题摘要、Schema 版本、
   耗时、token 成本、证据引用），格式与 Bridge 现有 JSONL 审计事件一致。
6. **契约与测试**：在 `integrations/agentteams/skills/contracts.yaml` 增加
   `scientific-interpretation` 契约；为白名单拦截、Schema 校验、成本护栏、审计事件写聚焦单测
   （对齐 Bridge 现有测试风格，Ruff 检查通过）。

## 硬约束（违反即为不合格）

- 不修改 `ChatService`、LangGraph runtime、MAS DAG、Celery 的既有行为；Gateway 调用专业 Agent
  走 OmicHub 既有受控入口（HTTP API 或进程内服务层只读调用），不 import `TaskService` 直写数据库。
- 专业 Agent 被调用时不得自行提交/取消/重规划计算任务；执行动作永远属于人工审批后的 Workflow Operator。
- LLM 产出的建议不直接进入执行规格；执行参数仍只能来自预检快照 + 审批令牌链路。
- 凭证不出现在代码、日志、审计事件或返回体中。
- 不在文档或注释里把未联调的能力描述为已上线。

## 验收标准（对应方案文档 §15.2 Gateway 待验收项）

- Manager 可按白名单调用 `agent-rnaseq` 并获得符合固定 Schema 的结构化解读；
- 越权调用（未白名单的 Agent/工具、试图触发任务提交）被拦截并留有审计事件；
- 超时/次数/token 超限被拒绝且返回结构化错误；
- 全部新测试通过，`ruff check` 与 `ruff format --check` 通过；
- 更新方案文档实施状态段落：只勾掉已完成验收的项，保持诚实状态描述。

## 工作方式

- 先读设计文档与 `integrations/agentteams/bridge/`、`integrations/agentteams/skills/` 现有代码，
  沿用其分层、配置、审计与测试惯例，不引入新框架；
- 改动最小化，复用现有依赖，不随意加新三方包；
- 完成后输出：变更文件清单、新增接口契约、测试运行结果、以及联调待办清单（需要真实 AgentTeams
  环境才能验证的部分如实列出）。
