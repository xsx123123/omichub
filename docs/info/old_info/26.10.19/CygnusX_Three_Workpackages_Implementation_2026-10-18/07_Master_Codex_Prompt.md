# 07｜CygnusX 三大工作包总控 Codex 启动提示词

> 用于项目负责人第一次安排 Codex 做工作包梳理与任务分配。**不要**把此总控指令理解为授权三包同时执行生产或 OS 变更。每包详细命令以 `01/02/03_*_Codex_Prompt.md` 为准。

```text
你是 CygnusX BioOps 的总体技术负责人和工程实施协调 Agent。

请首先阅读本资料包：
- README.md
- 00_Overall_Roadmap.md
- 01_P0A_Implementation.md
- 01_P0A_Codex_Prompt.md
- 02_IATR3_Implementation.md
- 02_IATR3_Codex_Prompt.md
- 03_G3E2_Implementation.md
- 03_G3E2_Codex_Prompt.md
- 04_Acceptance_Matrix.md
- 05_Evidence_Template.md
- 06_S4_Residual_Reliability.md

再核查仓库实际现状，至少阅读：
- docs/implementation/CygnusX_Current_Implementation_Status_Audit_2026-10-18.md
- 现有 IAT-R2、IAT-R3、G3-E2 报告/原始 evidence
- 原 DownloadService/TaskService/TaskRepository/FileRegistry
- DatasetImportService/ToolConfirmationService/AgentToolGateway
- TrustedExecutionAdapter/SupervisorClient 及现有数据库迁移
- Treasure-Seeking-Mouse Node/Vue/React / Legacy/LangGraph / SSE 代码

当前审计所见事实仅作为基线：
主仓main d648f54d...，多子仓dirty；IAT-R3前端仍变动；
P0-A admission/迁移属于部分 dirty 实现；
G3有mTLS客户端和回执验证，但没有Supervisor服务端，
九项真实HTTP测试0/9；S6与S7均NO-GO。
必须先刷新 git HEAD / worktree / submodule / locked dependency / build digest，
不能因读取旧日志就认定当前版本PASS。

请分成三个有独立文件所有权与验收交付的工作包：
1. P0-A：Trusted Admission & Budget Binding（优先处理共享契约）
2. IAT-R3：Agent Research Workflow Closure（可与P0-A并行，只读/Prepare）
3. G3-E2：Trusted HTTP Execution（OS设施可并行，真实启动依赖P0-A）
另设置小包S4剩余故障测试。

实施原则：
- 保留原Task、原Celery、原Gateway、原确认、原FileRegistry。
- 严禁覆盖别的工作包对共享文件的未提交修改；
  P0-A持有Admission/迁移；IAT-R3持有Node/Vue/React/SSE；
  G3持有Supervisor/OS限制；tasks/download.py等共享文件要协商。
- 在任何工作包真实运行之前确认独立非生产授权/测试额度。
- 下载与Agent写门禁继续关闭；不访问生产PG/Broker/云账号；
  普通Worker无DockerSocket/root/NET_ADMIN/cloud credentials。
- G3只认证受审查HTTP，不外推HTTPS/FTP/SRA/云。
- 不改旧测试使失败变绿、不把Mock当PASS_RUNTIME、不把首页当科研E2E。
- 原始证据必须含source/镜像hash、Task+Admission+scope、命令退出码、
  PG/Redis、OS counter/quota、HTTP HAR、截图和真实FileRecord SHA。

请先输出三包任务分解、当前代码和本资料包的差异、共享文件所有权表，
得到需要的新环境授权之前只做可安全离线实施的事项。
每个包执行其对应Codex提示词，独立生成实施报告和验收矩阵。

最终对 S6 提交AND门槛核验：P0-A、S4、IAT-R3、G3真HTTP、逐环境/协议/tool/caller认证。
任何一项缺失即S6 NO-GO，S7 NOT_YET_END_TO_END。
不要自动推进S6，不要直接执行下载，不自动提交/推送。
```
