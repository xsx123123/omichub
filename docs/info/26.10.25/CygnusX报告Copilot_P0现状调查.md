# CygnusX 报告 Copilot：P0 代码现状调查

> 调查日期：2026-10-26。范围：当前工作树只读调查，不修改应用代码、数据库、子模块或运行配置。
> 对应任务：[实现计划](CygnusX报告查看与AI解读Copilot实现计划.md)。调查时点状态：调查交付，P1/P2/P3 未实施、未验收。
> 后续进展：用户指示继续后已开展 P1，当前实现与验证见 [P1 施工记录](../../implementation/cygnusx-report-viewer-p1.md)；本调查保留 P0 时点事实，不替代活动架构和阶段人工验收。
> 本文件为施工调查记录。架构现状权威仍为 `ARCHITECTURE_DESIGN/` 中的报告、前端、沙箱、MCP、项目空间和饼干经济活动基线。

## 1. 结论

报告中心已有鉴权列表、详情、HTML 内容预览、文件下载、收藏、版本树和“在 AI 工作台中优化”入口。P1 是将现有预览扩展为平台内查看页，同时解决交互脚本的隔离问题；P2/P3 可复用既有 Chat/MCP/Studio/积分链路，但不能直接把现有工具全部授予报告 Copilot。

必须先纠正五个前提：

1. `ReportModel` 和 `TaskModel` 均没有通用 `project_id`；部分 Dataset 任务可经验证过的关联找到项目，Studio 登记的报告甚至可能没有真实 Task 行。项目目录名不是项目授权依据（`models/report.py#ReportModel`、`models/task.py#TaskModel`、`ResearchProvenanceService.task_scope`、`studio_context_service.py#register_artifact_report`，路径见下表）。
2. 报告只落库流程、样本数等基础字段，没有统一的样本分组/Q30/结果表清单摘要；`project_summary.json` 是磁盘侧输入配置，不能把它等同于已落库测量结果（`ReportService.create_report_from_task`）。
3. 报告中心通过 Bearer 鉴权拉取 HTML，再放进 `sandbox=""` 的 `srcdoc` iframe；不存在可直接复用的报告签名预览 URL。S3 的预签名下载是另一种访问语义（`reports.py#preview_report`、`ReportPreviewModal.vue#loadPreview`、`S3CompatibleStorageBackend.presigned_get_url`）。
4. Studio 默认只读挂载的是**当前用户整个数据目录**，不是当前项目；普通聊天沙箱按用户复用，且输入目录的 Docker mount 目前为 rw。这些现状不能用作 P3 项目级隔离验收证据（`StudioSandboxManager.ensure_running`、`SandboxService.create_session`、`SandboxPool._warm_one`）。
5. 两条沙箱执行路径均按次启动 Python/R 子进程。容器和文件可以复用，Python/R 内存变量不会自然跨轮保留（`SandboxPool._build_exec_command`、`deploy/studio/sandbox_agent.py#_stream_exec`）。

“137 份报告”、现场各流程占比、真实文件可用性、生产镜像版本和网络阻断效果不是代码可证明的事实，本轮没有连接业务数据库或启动/变更业务容器，不标为已验证。

## 2. 能力矩阵

以下 `src/` 路径均相对于仓库根；函数名、类名用于定位，避免并行工作导致行号漂移。

| 调查项 | 当前实现与证据 | 对施工的影响 |
|---|---|---|
| RNA 报告生成 | `pipelines/RNAFlow/rules/14.Report.smk#generate_docker_json` 生成 `report_data/project_summary.json`；`#Report` 运行 Quarto 报告容器，写 `config['data_deliver']/Analysis_Report/index.html`；规则说明为自包含 HTML | 调用方是流程，不是列表 API；本轮不改子模块 |
| ATAC 报告生成 | `pipelines/ATACFlow/rules/13.Report.smk#generate_docker_json`、`#Report`，通过 Apptainer 写同类路径 | 不应假设所有生成任务都经过一个新的平台渲染函数 |
| 平台侧报告渲染 | `src/cygnusx/application/services/bioreport_adapter.py#BioReportAdapter` 另有受控 BioReport 渲染适配；`report_audit_renderer.py` 渲染执行证据 HTML | 科学报告、执行证据、交付包和项目综合报告须区分；不能把全列表当同一种 BioReport |
| 成功后登记 | `src/cygnusx/infrastructure/celery_app/tasks/analysis.py` 成功分支调用 `ReportService.create_report_from_task`；Dataset 分支改走 provenance reconcile 与独立报告 job | 预览不能触发重算或重新生成报告 |
| 存储与入口发现 | `src/cygnusx/application/services/report_service.py#_load_result_manifest` 在 work、相邻/内部 `data_deliver` 查 ARDP manifest；`#_evaluate_result_manifest` 校验入口、非空及声明 md5；无 manifest 时回退 `Analysis_Report/index.html` | 必须复用登记文件与 StorageBackend，不能拼 `/projects/{id}/results` |
| 报告身份 | `src/cygnusx/infrastructure/database/models/report.py#ReportModel`：id、task_id、user_id、flow_id/version、parent_id/version、kind、snapshot_id、result_observation_id；Task 身份非空但非通用项目键 | 前端路由使用 report ID；后端先 owner 校验，再派生真实作用域 |
| 报告元数据 | 同模型有 `sample_count`、`duration`、标题、描述、时间与状态；`ReportService.create_report_from_task` 仅从 summary 读取标题/物种/基因组/样本数 | P2 需新增有来源、有缺失状态的结构化摘要；不能用描述字符串代替 QC 表 |
| 产物记录 | `src/cygnusx/infrastructure/database/models/report.py#ReportFileModel` 保存名称/类型/大小/path/主文件/可选 FileRecord 与 SHA；`create_report_from_task` 登记 HTML/PDF | `report.files` 不是全部项目分析结果；DEG/富集表需另找可信清单 |
| 项目关联 | `src/cygnusx/application/services/research_provenance_service.py#task_scope` 校验 Task owner，并通过 DatasetAnalysisLink → DatasetVersion → Dataset 校验项目和 normalized_request；`models/task.py#TaskModel` 无 project_id | 有合法关联才有项目 scope；legacy 报告不能按工作目录名称猜项目 |
| 非 Task 报告 | `src/cygnusx/application/services/studio_context_service.py#register_artifact_report` 创建 Studio 报告时使用随机 task_id 哨兵；`models/project_report.py` 则是独立项目报告体系，ReportFile 用 XOR 关联 | Copilot 需要处理“无真实 Task/无项目”并降级；本阶段入口不能混淆独立项目报告 ID |
| 列表/筛选/收藏 | `src/cygnusx/api/v1/reports.py#list_reports/#toggle_star/#delete_report` → `ReportService` → `src/cygnusx/infrastructure/database/repositories/report_repository.py` | 保留列表契约，查看页复用详情与收藏 API |
| HTML 访问 | `src/cygnusx/api/v1/reports.py#preview_report` 返回 PlainTextResponse；`ReportService.preview_html` 校验 owner、可选科研 scope、路径和可用字节摘要；前端 `frontend/src/api/report.ts#previewReport` 用统一 axios | 不是静态公开目录；新预览路径须保留这些校验 |
| 鉴权/签名 | `src/cygnusx/api/deps.py#get_current_user_id/#_authenticate_jwt` 接受 Bearer/API Key，检查 active/token_version；`src/cygnusx/application/services/file_service.py#create_presigned_download` 与 `infrastructure/storage/s3_backend.py#presigned_get_url` 是对象存储下载能力，本地 backend 默认不支持 | Bearer 不会自动随 iframe 导航发送；仅有签名的 URL 是持有即访问，不能满足“复制到未登录浏览器仍拒绝” |
| 下载 | `src/cygnusx/api/v1/reports.py#download_report_file`：本地科学报告用 FileResponse；执行证据/交付包/非本地存储用 `ReportService.object_download`；`frontend/src/api/report.ts#downloadReportFile` 带鉴权取 Blob | 保留 attachment 和完整性检查，不改为裸链接 |
| 现有预览 UI | `frontend/src/views/ReportsView.vue#handlePreview` 打开 `components/report/ReportPreviewModal.vue`；`?reportId=` 也打开它；iframe 空 sandbox，关闭/切换有 requestEpoch 保护 | 有预览但无独立查看页；空 sandbox 禁用 BioReport JS；旧深链接须兼容 |
| 页面外壳/浮层 | `frontend/src/router/index.ts` 的 `DefaultLayout` children 下有 `/reports`；`frontend/src/layouts/DefaultLayout.vue` 提供顶栏/侧栏；`components/ai-chat/KimiChatInput.vue`、`ApprovalCard.vue`、`ApprovalDrawer.vue` 与 Naive UI Drawer 已存在 | `/reports/:reportId/view` 可挂同一布局；嵌入面板须复用聊天事件与审批，不另造消息协议 |
| 安全交互参考 | `frontend/src/components/ai-chat/AgentTeamsReportPreview.vue#injectContentSecurityPolicy` 已采用 `allow-scripts` + opaque origin + 禁 connect/frame/form 等 CSP | 可参考此模式，但不等于报告中心已经支持；禁止加入 allow-same-origin 或新窗口裸执行 HTML |
| AI 工具注册 | `src/cygnusx/infrastructure/mcp/presets.py#PLATFORM_PRESET_TOOLS/#PLATFORM_HANDLERS/#PRESET_SERVERS`、`pipeline_preset.py#build_pipeline_preset`；`application/services/tool_bridge_service.py#ToolBridgeService` 消费 `tool_configs/tools_schema.yaml` | 已有 builtin MCP 与 schema bridge；命名遵守现有 snake_case；不能另建模型工具路由 |
| 调用内部上下文 | `src/cygnusx/application/schemas/tool_invocation.py#ToolInvocationContext` 有 user_id/agent_id/session_id/db/extra；`infrastructure/mcp/client.py` 仅向 builtin handler 传 context，阻止外部透传 | report scope 应从已授权会话解析到内部 context；不把模型参数或 page_context 当授权 |
| 现有只读结果能力 | `src/cygnusx/application/services/pipeline_result_service.py#PipelineResultService` 有 owner Task 查询、结果根解析、文件预览（默认 20KB）、产物列表（最多 200）、DEG 摘要（表限制 10MiB） | 可复用底层解析，但当前 task_id 仍是调用参数，列表到上限没有显式 truncation；尚无本计划的三个报告锚定工具 |
| 聊天持久化 | `src/cygnusx/infrastructure/database/models/chat.py#ChatSessionModel` 有 project_id、sandbox_meta；`application/schemas/chat.py#ChatStreamRequest` 有 session_id/project_id/page_context，无 report_id | P2 必须新增并校验报告绑定，刷新恢复不能只依赖浏览器“当前报告”字符串 |
| 从报告进入 AI | `frontend/src/views/ReportsView.vue#handleOptimize` → `src/cygnusx/api/v1/studio.py#create_studio_session_from_report` 调用应用函数；`studio_context_service.py#create_session_from_report` 校验 owner，建 Studio session，把文件软链到 input，保存 source report ID/context_pack | 已有报告→AI 上下文基础，可复用设计；它新建工作台会话且 require_project=False，并非只读报告 Copilot |
| 沙箱执行入口 | `src/cygnusx/application/services/chat_sandbox_tools.py#execute_chat_sandbox(args,user_id,on_output,session_id)` → `SandboxService.execute_code` → pool；Studio 用 `StudioSandboxManager.exec(session_id,language,code,timeout_sec,image,user_id)` → UDS `/exec` NDJSON | 已有 stdout/stderr/图表/产物双通道，不必重新造执行协议 |
| 产物保存 | `src/cygnusx/application/services/studio_context_service.py#register_artifact_report` 限 output 路径、复制独立 run output、登记目录链/Report/ReportFile/FileRegistry；父报告来自 context_pack；`api/v1/studio.py` 有人类保存入口 | 已有闭环基础；source 当前为 STUDIO，需明确新增来源“AI 沙箱分析”和对话关联，不能自动把结果覆盖为原报告 |
| 保存审批 | `src/cygnusx/application/services/studio_approval_service.py#needs_approval` 仅 supervised 且非 always_allow 时拦 artifact_register；`ChatStreamRequest.auto_approve` 和 ChatService 有跳过机制 | 不符合“每次保存都明确确认”的硬门；P3 需服务端强制、绑文件内容的一次性确认，不受 auto/always_allow 绕过 |
| 积分 | `src/cygnusx/application/services/cookie_service.py#CookieService.pre_deduct/#settle/#refund` 已有；TaskService 与 Celery analysis 使用；`chat_sandbox_tools.py#execute_chat_sandbox` 未接这组执行计费 | 复用积分服务和定价，不把 token 扣费当执行结算；还需执行 ID 幂等、失败/超时退款及中断对账 |

## 3. 报告生成到展示/下载的链路

```text
RNAFlow generate_docker_json / Report；ATACFlow 同类规则
  → data_deliver/report_data/project_summary.json + Analysis_Report/index.html
  → Celery analysis 成功分支（Dataset 任务另走 reconcile / report jobs）
  → ReportService.create_report_from_task
      旧目录约定；或 ARDP result_manifest.json → entry/产物校验
      summary → 基础字段；Report + ReportFile → repository / DB
  → GET /api/v1/reports → ReportsView → ReportCardMinimal
      ├─ 预览 → handlePreview → ReportPreviewModal
      │   → axios Bearer GET /reports/{id}/preview
      │   → owner / scope / 路径 / 可选 SHA 检查 → StorageBackend → HTML 文本
      │   → iframe srcdoc + sandbox=""（脚本禁用）
      └─ 下载 → axios Bearer GET /reports/{id}/files/{fileId}/download
          → 报告 owner + file.report_id 校验
          → 本地科学报告 FileResponse / 其他路径 object_download → attachment Blob
```

对应位置依次为两份 `.smk#Report`、`tasks/analysis.py` 成功分支、`ReportService.create_report_from_task/_evaluate_result_manifest`、`reports.py#list_reports/#preview_report/#download_report_file`、`ReportsView.vue#handlePreview`、`ReportPreviewModal.vue#loadPreview`、`frontend/src/api/report.ts#downloadReportFile`。具体完整路径见能力矩阵。

`ReportService.preview_html` 对“无 HTML/普通科学报告文件丢失”有返回 `<p>` 的兼容行为，HTTP 成功不代表报告成功加载；审计/交付报告丢失才抛 NotFoundError。新查看页要有可区分的 404/过期/加载失败契约，不能只靠 iframe `onload` 判成功。

## 4. 沙箱四项隔离事实与差距

| 项目 | 普通 Chat 池 | Studio | P3 还须证明的事实 |
|---|---|---|---|
| 网络 | `core/config.py` 默认 sandbox_network_isolated=True；`SandboxPool._warm_one` 使用 network_mode=none，可配置改为普通网络 | `data/ai/studio.yaml` 当前 whitelist；`StudioSandboxManager._ensure_whitelist_network` 建 internal 会话网络并连接代理；`deploy/studio/egress_proxy.py` 按域名/端口限制 | 报告专用 profile 默认 none；如果启白名单，必须真实验证绕过代理、IP/其他域名均失败，不继承普通网络配置 |
| 挂载 | `_warm_one` 将 input/output/chat_output 以 rw 绑定；没有当前项目 ro mount | `ensure_running`：workspace rw；`/data/platform` 是 users/{user_id} 整根 ro；可附加 workdir rw；cloud scratch 为另一分支 | 创建时仅挂当前获准项目结果 ro + 独立 workspace rw；不得同时存在用户整根 mount；验证 symlink、路径穿越及容器 inspect |
| 限额 | 默认 4g、PID 512、UID 10001、只读 rootfs、cap_drop ALL；CPU 用 cpu_shares（相对权重，非 2 核硬上限）；单次默认 300s，pool timeout guard 尝试杀 exec | 当前 YAML CPU=2、memory=4g、PID=512、exec timeout=600s、workspace quota=10GiB；manager 使用 nano_cpus；sandbox-agent `_stream_exec` 限时强杀进程组、流内输出截断并写日志 | 使用硬 CPU 配额，验证超时/内存/输出上限；图像/文件总字节也要设上限；不能只验证 stdout 摘要大小 |
| 生命周期 | `SandboxService.create_session` 复用同 user 活跃会话；`recycle_expired` 回收，Settings 默认 session_timeout=300s；container 文件可持续，进程变量不持续 | `ensure_running` 按 chat session 建容器；`recycle_idle` 默认空闲 10 分钟；`stop/hibernate` 移除容器；持久工作区另受保留策略；执行 lease 防忙碌误回收 | 报告/会话独立、并发隔离、结束/超时清理的真实证据；变量保留需要常驻解释器协议，不能用“同一个容器”代替 |

以上为代码和配置事实，未读取生产 `.env` 覆写、未执行容器 inspect，也未进行现场攻击测试。两条路径都是 Docker 实现，不能表述为已采用 Firecracker/microVM。代码允许的 `/tmp`、运行时库、解释器文件也必然在 `/data` 外；P3 恶意用例应具体指“宿主/其他项目/其他会话的未授权数据”，而非拒绝所有 `/data` 外读取。

## 5. 风险与缺口（按阻断阶段）

| 等级/阶段 | 缺口 | 关闭条件 |
|---|---|---|
| 阻断 P1 交互验收 | 空 sandbox 禁脚本；直接给同源 HTML 开脚本或裸开新窗口会突破当前预览边界 | 新查看页 opaque origin + allow-scripts，禁止 allow-same-origin/顶层导航；响应级隔离策略；真实 BioReport 页签与恶意 HTML 浏览器回归；执行证据报告保留既有安全语义 |
| 阻断 P1 鉴权验收 | 签名 URL 本身不证明浏览器登录；现有 Bearer 不随 iframe 导航发送 | 单独的短时报告预览凭证，绑定 report/user/浏览器会话并复核权限；签名 URL 单独复制、改 ID、过期/删除/撤权均拒绝；下载仍走 Bearer；不把 access token 放 URL |
| 阻断 P1 错态验收 | 普通预览丢文件返回 HTTP 200 提示 HTML；列表 handlePreview 没有集中状态拒绝 | 新接口对 missing/expired/not-ready 给结构化状态；查看页直达与列表入口都校验；保留旧消费者兼容 |
| 阻断 P2 | 无可信通用项目映射、无完整结构化摘要、无按报告持久化会话绑定 | 服务器从实际关联解析 report → owner/task/project；无法确定项目时只允许该报告授权数据/通用解读；显式缺失，不猜项目、不扩大为用户全部数据 |
| 阻断 P2 工具验收 | 现有 Task 只读工具可接收其他 Task ID；未实现章节定位与 top-N/filter 查询 | 三个工具的 schema 不收 project/task ID 或绝对路径；每次执行重验 session/report/current permissions；有界读取、列校验、真实表筛选和显式截断；P2 工具白名单中不得含执行/写入/跨范围浏览工具 |
| 阻断 P3 | Studio 的用户整根只读挂载、Chat 的用户级复用/rw input/CPU shares 均不满足需求 | 报告专用会话作用域和挂载策略；不可用时 fail closed；真实 Docker mount/network/资源/销毁用例 |
| 阻断 P3 状态验收 | 两条执行器均新建子进程 | 补受限常驻解释器/内核协议并验证跨轮变量；保留按会话文件本身不算该条通过 |
| 阻断 P3 保存验收 | artifact_register 可被权限模式/auto_approve/always_allow 跳过确认 | 人类 JWT 端点签发单次确认，绑定 session/report/文件清单与内容摘要；模型不能自证，文件变化须重确认；正式登记有来源及对话 ID |
| 阻断 P3 计费验收 | 沙箱执行未接执行预扣实结；现有服务存在不等于该链路通过 | 估价→余额检查→预扣持久化→执行→实结/退款与恢复；按执行 ID 幂等；不足余额不执行；并发/中断/重复结算与流水验证 |
| 可延后，但不能宣称已验收 | 生产报告数/所有报告自包含/真实三流程样本/镜像及网络实测未知 | P1/P2/P3 各阶段使用真实授权报告及隔离夹具验收；开发机合成测试与人工验收分开记录 |

## 6. 已有能力的复用清单

- **已有报告内预览与鉴权下载**：`reports.py`、`ReportService`、`ReportPreviewModal.vue`、`frontend/src/api/report.ts`；新增路由不需重写报表。
- **已有隔离交互预览参考**：`AgentTeamsReportPreview.vue` 的 opaque-origin iframe/CSP；可复用策略，不挪用 Case 鉴权。
- **已有结果目录解析、表摘要、文件预览**：`PipelineResultService`；增加报告绑定和有界查询，而非重新扫描用户目录。
- **已有报告→Studio context_pack**：`create_session_from_report`；不是完整摘要、不是报告面板持久绑定。
- **已有会话容器、stdout/图表双通道、审计与回收**：`chat_sandbox_tools.py`、`SandboxPool`、`StudioSandboxManager`、`sandbox_agent.py`；项目级挂载和解释器状态仍缺。
- **已有产物注册及版本树**：`register_artifact_report`、FileRegistry、StoragePathFactory；补强每次确认和来源关联，不引入覆盖原报告行为。
- **已有积分预扣/实结/退款和定价**：`CookieService`、Task/Celery 调用链；补沙箱执行调用及恢复，不新建第二本积分账。

## 7. P1–P3 参数替换与待实施设计

以下是基于现状的施工约束，**不表示已实现或已通过人工验收**。

| 计划占位 | 替换值/设计 |
|---|---|
| 技术栈 | Vue 3/TS + Naive UI；FastAPI/SQLAlchemy；沿用统一 `/api/v1` axios |
| 列表、路由、布局 | `frontend/src/views/ReportsView.vue`；`frontend/src/router/index.ts`；`frontend/src/layouts/DefaultLayout.vue` |
| 新查看页 | `frontend/src/views/ReportViewerView.vue`，`/reports/:reportId/view`，挂 DefaultLayout；`?reportId=` 旧入口转入同一页；只在 P1 实施 |
| 新预览 API | `GET /api/v1/reports/{report_id}/preview-url` 由已登录请求签发；对应受限 HTML 响应也绑定短时浏览器预览会话，不能仅验 URL 签名；复用 ReportService 文件/owner/完整性检查；具体签名和 cookie scope 在 P1 实现评审与测试中固定 |
| 新窗口 | 打开同样受控的平台查看路由，不直接 window.open Blob/srcdoc/原始 HTML；复制底层 URL 到无预览会话浏览器须拒绝 |
| P2 摘要 | 新增版本化 report metadata，保留 report/task/project 可空关联、来源及缺失状态，样本/分组/QC/结果表/产物引用；独立迁移，不改冻结 ReportSnapshot；在登记成功路径提取并落库；回填脚本只读来源、默认 dry-run、幂等且不重算/不覆盖 HTML |
| P2 工具接入 | 现有 builtin MCP / ToolInvocationContext / 请求级工具裁剪；三个报告绑定只读工具复用 PipelineResultService 底层能力；不能只把 schema 中的 scope 隐藏后仍信任工具参数 |
| P2 章节定位 | 在**预览响应副本**注入 listener，不覆盖归档文件或 SHA；postMessage 校验父窗口/消息结构/当前报告；opaque iframe 的接收端必须核对 event.source，不能只靠 origin；引用绑定服务器认可章节 ID |
| P3 沙箱 | 复用 Studio 管理器的生命周期/NDJSON，增加报告专用项目挂载 profile；禁用户整根 mount、默认禁网；需要跨轮变量的受限常驻解释器；不新建一套 Docker 管理器、不改普通会话默认行为 |
| P3 产物/计费 | 复用 FileRegistry/目录协议/积分服务；每次正式保存强制人类确认；执行预扣实结按独立 execution ID 关联并可恢复；不得以随机 Task 伪装真实科研计算 |

保留原 P1/P2/P3 全部目标。未关联项目的历史报告仍须可查看并给明确解读降级；它们不因此获得任意项目访问或保存权限。通用问题降级不等于跨项目/项目级验收完成。

## 8. 本轮交付与验收界线

- 已完成六项代码调查、能力矩阵、生成→存储→访问链路、沙箱四项事实、分阶段缺口及复用清单。
- 实现计划同步记录上述事实修订；未把历史提案当作 as-built，未修改架构基线来宣称新能力已存在。
- 未修改应用代码/迁移/配置/子模块；不提交工作区中原有其他变更。纯调查文档不需要应用测试。
- P0 人工核对、P1/P2/P3 开发与各阶段人工验收仍未完成。原计划明确“每阶段人工验收后再进入下一阶段”；不以本调查替代该验收。

## 9. 续查：同名新稿与 mock 数据源核对

本次续查发现工作树另有 `docs/info/26.10.26/CygnusX报告查看与AI解读Copilot实现计划.md`。
其 Part 3/4 增加 `report.paths.json` 2.0.0/2.1.0 注册、`REPORTS_ROOT`、目录式报告 ID、
存量扫描注册，以及“mock 数据源切换”。它是新增目标描述，不是已实现架构；当前任务仍引用
10.25 计划，尚未取得 P0 人工确认，不将同名新稿自动当成已验收的范围变更。

### 9.1 列表和统计当前已经读库

| 核对位置 | 代码事实 | 可得出的结论 |
|---|---|---|
| `frontend/src/views/ReportsView.vue` 的 `useApi` 装配 | 分别调用 `reportApi.getReports(filter.value)` 和 `reportApi.getReportStats()`；初始列表为空，统计为零 | 该页面没有用 mock 数组填充，也没有失败后转 mock 的分支 |
| `frontend/src/api/report.ts#getReports/#getReportStats` | 请求 `/reports` 与 `/reports/stats` | 页面列表和统计走真实 API 契约 |
| `frontend/src/api/client.ts`、`frontend/src/main.ts`、`frontend/vite.config.ts` | axios 为 `/api/v1` 附 Bearer；页面启动未装配报告 mock；Vite `/api` 代理到 `:8888` | 所检查客户端启动/请求路径没有报告 mock 拦截器；部署中的代理或旧构建仍须现场核验 |
| `src/cygnusx/api/v1/reports.py#list_reports/#get_report_stats` → `ReportService.list_reports/#stats` | 使用当前用户调用 ReportRepository | 列表与统计已有 owner-scoped 后端链路 |
| `src/cygnusx/infrastructure/database/repositories/report_repository.py#ReportRepositoryImpl.list_by_user/#count_by_user` | 查询 reports 表，按 user_id 限定，并排除 flow_id=studio；列表支持 SQL 筛选/分页，统计用 SQL count | 当前不是请求时扫描报告目录的列表；“盘面文件数”等于“可见报告数”也不是当前契约 |
| `frontend/src/components/report/mockData.ts#mockReports/#mockStats` | 全量搜索 `frontend/src` 的 mockReports/mockStats 引用只命中本文件导出；mockStats.total=5 | 文件是遗留演示资产；它本身不能解释现场 137 条的来源，也不能据此认定数据库里的记录均为真实科学报告 |

因此，“137 条是演示数据”的新稿描述可能涉及现场旧构建或数据库中的演示记录，本轮代码
证据不能定位其来源。后续若处理该问题，应先对账实际网络响应、部署构建与报告登记来源；
不应删除未知归属报告、引入 mock 回退开关，或把已经读库的列表重复改成另一套注册表。

### 9.2 新稿的接口与身份差异

- 新稿引用的《BioReport JSON Schema 2.1.0 更新计划.md》以及 `report.paths.json`
  示例在当前仓库 `rg --files` 结果中未找到；新稿写出的字段摘要不能证明完整 schema
  已经在本工作树落地。若后续采用这项扩展，需先拿到并核对权威 schema。
- 现有 `reports.py` 的详情/预览/下载参数均为 UUID，`ReportModel` 要求非空 task_id；
  新稿示例 `<project_id>_<yyyymmdd-hhmmss>` 是另一种目录标识。需要明确它与数据库 UUID、
  可空真实 Task 的映射和迁移，不能直接替换既有 ID 或造 Task 记录满足约束。
- 新稿的独立 REPORTS_ROOT 与当前用户项目 run 目录/StorageBackend 是不同存储入口。
  即使后续采用新入口，也必须保留现有科学、执行证据和交付包的授权读取路径，不能把旧记录
  当成未注册数据整体下线；未解析到可信 owner/project 的目录只能进入人工处理清单。

本节补充的是新发现的代码证据与范围差异。P0 人工确认仍未收到，未实施 P1 或新稿 Part 4，
未运行迁移、扫描业务存储或清理演示数据。
