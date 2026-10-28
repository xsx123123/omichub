# 02-Prompt｜直接交给 Codex：IAT-R3 Agent Research Workflow Closure

---

你是 CygnusX BioOps 的**高级 Agent Runtime / FastAPI / Node / Vue3 / React / PostgreSQL / Redis / Playwright 工程师**。执行 **IAT-R3 · Agent Research Workflow Closure**，依据 `02_IATR3_Implementation.md`、`00_Overall_Roadmap.md` 和最新审计。目标不是新增 Agent 框架，而是让现有科研 Agent 的**真实业务链路运行且证据齐全**。

### 绝对限制

- 保留 Gateway/ToolBridge/MCPClient、Node `platform-tools.ts` 和 `FullPresentation`、主站 Vue typed adapter、真实 `DatasetImportService.prepare`、SSE cursor/replay，不建立平行业务 API/UI。
- 只读与 Prepare 可以在获授权非生产环境按既有独立门禁开放；**不得**开放下载执行/Agent write、绕开 JWT/委托或自动确认。
- 禁止触碰生产 treasure-mouse 容器、用户 PG、Broker/Worker；不使用生产模型 API Key；Chromium 保留 sandbox。
- 审计时 `TreasureResearchWorkbench.vue` 等前端 dirty，五子仓也 dirty；开工前固定完整 source manifest，避免旧 R3 单测冒充最新 E2E。

### 阶段 R3-0：现状/环境

1. 只读确认当前源码和 dirty，定位：`infrastructure/ai_provider/testing.py`、`agent_templates` 实体、Legacy/LangGraph Runtime 的 `chat/stream` 正式入口；`pipelines/Treasure-Seeking_Mouse/functions/seqout-chat/platform-tools.ts`、Node index，React island，Vue `TreasureResearchWorkbench.vue`，`research_treasure_service` SSE。
2. 记录主仓/子仓与嵌套 submodule SHA、dirty 源码指纹、lockfile 哈希、UI bundle digest。列出改动文件所有权，**不要覆盖其他 Codex 正在修改的 Admission、download Worker 等文件**。
3. 检查是否具备明确授权的独立 Compose、PG/Redis、Node API、Chromium。没有授权环境：先实现代码/静态和隔离测试，真实运行明确 BLOCKED，不伪造日志。

### 阶段 R3-A：两种 Runtime 真实连接

1. 只在非生产 PG 中创建合法 `agent_templates`、测试 users/projects/sessions 和**确定性测试 Provider** 配置，经正式 `ProviderManager` 和原 API 装配。
2. 分别从**真实监听 FastAPI** `chat/stream` 触发 Legacy 与 LangGraph：模型工具请求→`ToolBridge`→现有 Gateway→PG audit/Redis→Tool Result→下一步 Assistant 回复→done。
3. 对每种 Runtime 单独记录实际工具名、tool_call_id、会话/项目、源请求和 final response；错误时 `success=false/is_error=true`，不将未授权返回伪装成功。
4. 负测：模型注入 owner/project/scopes；用户 A 使用 B 的 Session；scope 降权、撤销、超过工具轮次上界、模型 SSE 中断。必须真实验证 permission 及无新增 Download Task。
5. 不要用 `gateway.invoke` 直接调用/ASGI mocked DB 冒充正式 Runtime PASS_RUNTIME。真实第三方 LLM 质量测试不是此阶段必需；如果有独立授权才另测。

### 阶段 R3-B：Node Research Runtime 全聊天工具轮次

1. 构建、启动原 Node 服务；从**真实 Node chat 入口**触发一次可识别的科研查询（不仅执行 `platformToolAdapter.call` 方法）。
2. 经原 `platform-tools.ts` 走实际 HTTP 委托：签发 JWT scope→Redis NX 防重放→FastAPI delegated invoke→Gateway Audit PG row→工具结果返回 Node→触发 Assistant 完整答复/卡片。
3. 验证 GEO discover、Capability 目录和已有资产 read 在允许的 schema 中正确返回；模型不允许决定 callback URL、运行凭据、submit/cancel，30s超时/redirect 禁止逻辑不得退化。
4. 双用户跨项目、相同 token 重放、scope 吊销、Session 归档、HTTP 超时、非法工具均必须 fail closed，保留 Node server logs、HTTP trace、PG 审计、Redis key（脱敏）。

### 阶段 R3-C：资产与合法 Import Prepare

1. 使用可信测试元数据快照（准确标明 offline fixture/公开出处/日期/digest）或**经单独批准**的少量 GEO/ENA metadata GET。未经授权不外呼、不下载文件。
2. 在非生产 PG 中通过原服务创建 A/P1、B/P2 两组 DatasetAsset/Version、原 FileRegistry/SHA 或使用受审查的受控小文件 fixture。**不得直接写假 SHA 充当原文件登记完成**。
3. 在 Node/Gateway 浏览真实 GEO DatasetCard、source_evidence/confidence_flags、文件候选、现有版本。触发合法 `dataset.prepare_import`：断言持久 Proposal/Ingestion 和 source digest/项目归属正确；下载 Task 数不增加。
4. 明确返回“待人工审批”；仅检查批准/拒绝 UI，不触发受控执行。非法 accession 拒绝测试只是负测，不替代合法 Prepare。

### 阶段 R3-D：原 React/Vue Chromium 业务 E2E

1. 安装匹配锁文件的 Node/pnpm 依赖，构建 React `FullPresentation` 和 Vue `TreasureResearchWorkbench`，在独立浏览器真实渲染。
2. 验证 Element marker + network route + source digest，确认打开的是原科研工作台而非 Vue 登录页。
3. 按 `02_IATR3_Implementation.md` 的 `R3-BR01..R3-BR10` 执行：GEO卡片、Dataset 真实版本、合法 Prepare、无下载、项目切换迟到帧、撤销/归档、断流 cursor 重连、浏览器多用户、错误页面/i18n。
4. 截图/HAR/network/console/PG/Redis 与同一 `request_id`、`session_id`、`project_id` 关联；SSE duplicate 不重复显示；若 producer 是进程内，跨进程取消绝不可伪称通过。
5. 保证 UI 真实业务测试断言具有区分力：未找到实际 DatasetCard 或 PG Proposal 时**必须失败**；不允许以首页 200、单个 401、空表为 PASS_E2E。

### 阶段 R3-E：回归、补漏及证据

- 复跑之前隔离 R3/前端单测，但不把旧日志摘要当本轮运行结果。
- 单独修复 ToolBridge 通用错误码与目录截断的有限问题（若当前代码实际仍存在），不能扩大为新的 MCP 平台。
- 检查 Node/R3 真实取消与断线语义；找不到跨进程恢复实现就标记 BLOCKED，并提供最小改进建议，不得伪造真相。
- 报告写入 `docs/implementation/cygnusx-iat-r3-research-workflow-closure.md`，保存 `evidence/iat-r3-runtime/`。每例写：Test ID、真实代码入口、环境/镜像/SHA、数据 fixture、命令、退出码、日志/截图/HAR、PG/Redis 断言、PASS_RUNTIME/PASS_E2E/BLOCKED、残余风险。
- 更新现有矩阵，不新增冲突的 78/120 数字口径；逐项列出原弱断言纠偏。不得擅自提交/推送或部署生产。

**完成 R3 后停止**；不自动执行 P0-A/G3/S6，不更改任何下载执行门禁。若运行环境丢失或前端变动导致 SHA 不匹配，停止使用旧证据并重新构建后再验收。
