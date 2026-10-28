# 可直接交给 Codex：IAT-R3 Runtime与科研UI闭环

请在当前CygnusX仓库实施IAT-R3，不只写调查报告。目标是复用既有S3/S4/S5代码与RI095隔离环境，补齐真实Legacy/LangGraph Runtime、科研寻宝鼠Node聊天轮次及React/Vue/Node/FastAPI/PG/Redis/Chromium业务E2E。配套阅读《01_CygnusX_实施优化方案.md》，它是设计输入，不能作为通过证据。

## 强制边界

1. 先读AGENTS.md、当前实现、原S3/S4/S5设计、R2报告、原始证据和更新矩阵。当前已知R2报告HEAD为d9c92cf6ee1c，不假定工作树仍一致。保护已有dirty变更，不重置、不批量格式化、不擅自提交推送。
2. 只使用既有授权非生产环境；不触碰生产容器、队列、数据库、Provider凭据。缺授权仅阻断相关操作，继续完成代码及可运行工作。
3. 复用Gateway、ToolBridge、业务服务、审批、队列和UI；不新增替代业务系统。
4. 不真实下载科研文件，不调用下载执行；所有下载/Agent写执行门禁保持原冻结值。Import Prepare只生成预案，不创建下载Task。若预案持久化需要既有受控prepare权限，只限定隔离配置，不扩大execute权限。
5. 确定性Provider不等于真实第三方模型；直接Gateway调用不等于Runtime完整轮次；Vue登录页不等于React科研业务E2E。

## 实施顺序

### 1 基线与证据纠偏

保存HEAD、dirty摘要、子仓版本、依赖、迁移、服务拓扑、身份和开关。读取R2引用的原始文件，核实describe capabilities与dataset.discover是否各有独立日志；复核MQ-02消息发布语义与78项统计。缺文件记缺失，不编造。父ID保持不变，未覆盖子场景另列child_id。

### 2 隔离数据与Provider

按现有schema创建合法非生产AgentTemplate，分别选择Legacy/LangGraph引擎。使用幂等、带run_id的seed和受限清理。创建测试用户、项目、session、GEO来源快照、DatasetVersion、真实fixture FileRecord与资产关联；synthetic/fixture必须明确，不能伪称真实下载。

实现仅非生产可启用的确定性Provider，走真实Provider装配接口：首轮输出标准tool call，读取真实工具结果后输出后续轮次及最终回答。它不得直接调用Gateway、直接写业务表或伪造工具响应。生产配置检测到该Provider应拒绝启用。

### 3 双引擎真实工具轮次

分别从真实chat API/SSE入口运行Legacy和LangGraph，覆盖成功inspect/prepare及权限拒绝、重放、确认不匹配、超时。验证实际引擎选择、ToolBridge错误映射、无不受控重试及最终SSE终态。

关联用户/项目/session→template/provider→tool_call→invocation→PG audit→Redis nonce→tool result→final response。每个引擎至少一条完整成功轮次及一条拒绝路径。确定性Provider标签写入矩阵；真实外部模型另项，未运行不能算通过。

### 4 真实部署与浏览器业务E2E

按锁文件构建现有React/Vue界面和Node服务，复用FastAPI/PG/Redis。记录实际拓扑，保留Chromium sandbox。浏览器必须经过产品入口、真实Node运行链与持久化业务数据，完成：

- GEO DatasetCard和来源信息→候选文件→Dataset Inspect→Existing DatasetVersion/FileRecord。
- 合法Import Prepare持久化→等待人工确认→刷新后恢复；本run_id下载Task增量为零、执行按钮和直接API均受门禁拒绝。
- A1请求延迟后切A2，再释放A1，确认旧数据与SSE事件不污染A2。
- 归档session、运行中撤权、跨用户/项目访问由服务端拒绝。
- 真实SSE断流与重连，事件去重、最终状态一致；不得用刷新替代。
- 双语关键状态与错误展示。

外部元数据只能访问已授权端点与额度；没有授权使用带来源固定快照，报告写清未验证实时发现。

### 5 S4共同余项

补PG-01并发异常语义、PG-10锁画像、PG-11所有写入路径及角色审计；补MQ-03发布者丢ACK、MQ-05 API终止窗口、MQ-06长期Worker缺席、MQ-07长故障冷却；补REC-04/06/07真实周期/公平性/事务失败和FR-09原断言。

先读原用例，编号含义与实际矩阵不同时以原矩阵为准，记录映射。使用真实Broker/Worker与独立队列，Worker固定SERVICE_NAME=worker并验证连接池。Celery函数succeeded但payload failed不能计为下载成功。所有故障注入限定隔离进程；不凭测试需要放开下载。

## 必须交付

- 实现与最小必要回归、可重复seed/启动/故障注入/清理步骤。
- `docs/implementation/cygnusx-iat-r3-runtime-ui-closure.md`：逐项事实、修复、Runtime与业务E2E、阻断及回滚。
- 更新原验收矩阵，子断言单列，汇总自动生成，禁止手工抬高结论。
- `evidence/<run_id>/`：命令/退出码、脱敏日志、PG/Redis查询、SSE、浏览器trace/截图、配置hash、关联ID和manifest。
- 明确S4/S5各自实际通过范围，G3继续BLOCKED，S6继续NOT_READY；本任务不签发下载准入。

先完成可执行实施，再报告真实结果。遇缺外部条件时列出缺口、已完成产物和最小补齐步骤；未运行写NOT_TESTED，前置阻断写BLOCKED，断言失败写FAIL，skip不计PASS。不得将本提示词的预期复制成验收事实。
