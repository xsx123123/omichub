# CygnusX 报告 Copilot — R3 沙箱能力核实报告

> 版本：v1.0（2026-10-28）
> 配套：《CygnusX报告Copilot剩余阶段提示词手册.md》R3 节；主计划第八节 P3
> 执行方式：只读代码核查，未修改任何代码；每条结论标注代码位置（文件:行号 或 文件#函数名）
> 结论用途：投喂 R4（P3）前，把手册 R4 节的「前置确认」替换为本报告实测结果；
> 「阻断 P3」项按手册规则作为 P3 阶段 0 先补齐并验证，完成前禁止注册执行工具。

---

## 一、能力矩阵（核查项 × 现状 × 代码位置）

| # | 核查项 | 结论 | 证据（代码位置） |
|---|---|---|---|
| 1 | 调用入口与契约 | **已具备** | 管理器 `infrastructure/studio/manager.py:1199#exec`（session_id/language/code/timeout/image/user_id → NDJSON 流，终态 `{"type":"result","exit_code","duration_ms","artifacts","run_log"}`）；容器内执行器 `deploy/studio/sandbox_agent.py:513#_stream_exec` + `:744 @app.post("/exec")`；宿主↔容器走工作区 Unix Socket（`manager.py:856#_agent_client`），不发布端口、不 docker exec。现有调用方：`application/services/studio_tools.py:862`（sandbox_execute 工具）、`api/v1/studio.py:280`、`infrastructure/celery_app/tasks/studio.py`、`application/services/chat_service.py:2935/3437/3799`。另有普通聊天池 `infrastructure/sandbox/pool.py:593#stream_execute`（docker SDK exec + `%%IMAGE%%`/`%%ECHARTS%%` 协议），与 Studio 是两套独立通道。 |
| 2 | 挂载能力 | **部分具备**（ro 挂载机制有，reportId 粒度没有） | 现有挂载事实：① 会话工作区 bind rw → `/workspace`（`manager.py:501-503`）；② **整用户数据根** `{storage_path}/users/{user_id}` ro → `/data/platform`（`manager.py:510-524`，注释明确"只挂 users/{user_id}，绝不整根挂 storage_path"）；③ 会诊 workdir 注册挂载 rw → `/workspace/workdir`（`manager.py:186#register_workdir_mount`，宿主路径强制限定在存储根内）。**缺失**：把「单个报告/项目结果目录」以 ro 挂到容器 `/data` 的机制——当前 ro 挂载粒度是整个用户目录，Copilot 场景挂整用户目录会把该用户全部项目数据暴露给沙箱，违反 P3 权限边界第 1 条。可复用的扩展点：`register_workdir_mount` 的注册-校验模式 + `_container_mounts_match`（`manager.py:798`）复用前挂载基线校验（缺挂载/源不匹配自动重建容器）。 |
| 3 | 网络策略 | **已具备** | 配置模型 `infrastructure/config/studio_loader.py:79#StudioNetworkConfig`：`mode` 仅允许 `none`/`whitelist`，**默认 `none`**（`studio_loader.py:84`）。none 模式容器 `network_mode="none"`（`manager.py:655-656`）；whitelist 模式每会话创建 internal bridge + 出站代理（`manager.py:257#_ensure_whitelist_network`，复用容器时校验网络唯一附着，`manager.py:776#_validate_container_network`）。代理 `deploy/studio/egress_proxy.py`：仅放行 `studio.yaml sandbox.network.allow` 声明域名（精确或子域匹配），拒绝 IP 字面量与私网/回环地址，DNS 解析固定为已校验公网 IP（防 DNS rebinding），仅允许 80/443 端口。白名单域名配置侧禁止 IP 与通配符（`studio_loader.py:108-127`）。放行 PyPI/CRAN 只是配置项，机制已就绪。 |
| 4 | 资源限额 | **已具备** | 容器硬限额：CPU `nano_cpus`（默认 2.0 核）、内存（默认 4g）、pids 512、只读 rootfs + 受限 tmpfs、uid 10001、cap_drop ALL、no-new-privileges、seccomp（`manager.py:627-654`，默认值 `studio_loader.py:130-150`）。执行时长：请求超时取 `min(req.timeout, 600s 默认, 3600s 上限)`（`sandbox_agent.py:516`，常量 `:62-63`），超时整进程组强杀（`sandbox_agent.py:586 start_new_session` + `:682#_terminate_process_group`）。输出体积：单通道流内上限 10KB，超出落 `.logs` 溢出文件并在 result 标注（`sandbox_agent.py:51 STREAM_CAP_BYTES`、`:594-638`、`:736-740`）；plotly 单图 3MB（`:57`）；工作区配额 10GB 经环境变量下发 agent 周期检查（`manager.py:647-652`，`studio_loader.py:148-149`）。超限行为均为结构化错误返回，不是静默失败。 |
| 5 | 隔离与销毁 | **已具备** | 一会话一容器（`manager.py:238#container_name`，非 UUID 会话 ID 走哈希后缀防碰撞共享）；每会话独立 internal 网络（见 #3）；复用前安全基线校验（CPU/pids/rootfs/cap/user/seccomp，不合即重建，`manager.py:833#_validate_container_security`）+ 挂载基线校验（`manager.py:798`）。回收：Redis ZSET 跨进程 last_activity + 执行租约防误收（`manager.py:370-430`），Celery beat 按 TTL 回收空闲容器（`manager.py:1178#recycle_idle`）；`stop`（`:1103`）移除容器+会话网络+socket，`hibernate`（`:1150`）保工作区收容器，`purge_workspace`（`:1171`）连工作区一起清。会话间文件系统隔离=容器边界；唯一跨会话通道是 ro 挂载的用户目录（见 #2，Copilot 需收窄）。 |
| 6 | 产物回注册通道 | **部分具备**（主链路有，P3 所需字段要扩） | 现成路径：`application/services/studio_context_service.py:488#register_artifact_report`——把 `/workspace/output/` 产物复制到项目运行目录 `output/` 并登记为报告中心新报告（版本树 parent_id/version，`studio_context_service.py:548-560`），经 `studio_tools.py:1235#_artifact_register` 工具暴露；cloud 模式另有 `manager.py:1089#finalize_outputs` → `ScratchVolumeManager.register_outputs` 注册 file_records。**缺口**：P3 要求登记到**项目产物列表**并记录来源「AI 沙箱分析」+ 关联对话 ID——现有登记落点是报告中心版本树/file_records，来源枚举（`domain/file/value_objects.py#FileSource` 现有 STUDIO 等值）与对话关联字段需要扩展；工作量小，不阻断架构。 |
| 7 | 计费接口 | **部分具备**（接口有，沙箱执行路径未接线） | 现成接口：`application/services/cookie_service.py:114#pre_deduct`（FREEZE 冻结，余额不足抛 BusinessError）、`:135#settle`（多退少补：SPEND 补扣 / UNFREEZE 退还）、`:182#refund`；已被流程任务链路使用（`task_cookie_consumer.py:47/74/90`、`task_service.py:204-340`，预扣额存 `task.parameters["_cookie_pre_deducted"]`）。幂等范式可参考 `cookie_service.py:221`（按 source 查重防重复扣费）。**缺口**：沙箱执行路径零计费——`application/services/studio_tools.py` 全文无 CookieService/积分调用（已全文检索确认），需新增按执行 ID 的预扣-实结接线与计费幂等。 |
| 8 | 确认门（人工确认卡片） | **已具备**（注意 P3 需强制确认、防绕过） | 后端：`application/services/studio_approval_service.py`——Redis 存储（跨进程，TTL 300s）、`create`/`wait_resolution`（BLPOP）/`resolve`（Lua 原子决议，校验归属与 pending），决议落 `audit_logs`（`:93#record_approval_audit`）；拦截名单含 `sandbox_execute`/`chat_sandbox_execute`/`artifact_register` 等（`:30-43`），另并集 `tools_schema.yaml` 中 `requires_confirm: true` 工具（`:50-63`）；REST 端点 + 断流重建 `list_pending`。前端：`frontend/src/components/ai-chat/ApprovalCard.vue`——参数预览（CodeMirror 只读代码/路径+标题）、【批准运行】【编辑后运行】【本会话不再询问】【让 AI 修改】、终态徽标；`PendingApprovalBar.vue` 刷新后重建待审批卡。**注意（非缺口但 P3 必须处理）**：现有旁路——① AI 助手页面 `auto_approve=true` 直接放行（`chat_service.py:2745-2748`）；② `permissions.always_allow` 同会话免重复审批（`studio_approval_service.py:78-90`）；③ 权限模式非 supervised 时普通工具不拦截。P3「每次保存须人类确认具体文件内容」必须让保存工具走不受这三条旁路影响的强制确认通道（如专用 approval_kind/工具名单），不能复用默认拦截逻辑了事。 |

## 二、缺口分级

### 阻断 P3（阶段 0 先补，验证强制边界前禁止注册执行工具）

| # | 缺口 | 说明与落点 |
|---|---|---|
| G1 | reportId/项目粒度只读挂载缺失 | 现仅整用户目录 ro 挂载（`manager.py:510-524`）。P3 需新增「项目结果根 → 容器 /data（ro）」的注册式挂载，projectId 由后端从会话上下文注入；复用 `register_workdir_mount` 注册模式 + `_container_mounts_match` 复用校验 + 存储根防逃逸校验。 |
| G2 | 跨轮变量状态（常驻解释器）缺失 | 当前每次执行新建子进程（`sandbox_agent.py:581#asyncio.create_subprocess_shell`），容器/文件复用 ≠ 变量保留。P3 功能需求第 2 条要求同对话内沙箱会话变量/中间结果保留，须在 sandbox-agent 补常驻解释器协议（如 Jupyter kernel 式会话），不允许默默缩减为文件级状态。 |
| G3 | 沙箱执行计费未接线 | `studio_tools.py` 无任何 CookieService 调用。需按执行 ID 做 pre_deduct（预估时长）→ 执行 → settle（实际 `duration_ms`，已在 result 事件返回）→ 异常 refund，幂等仿 `cookie_service.py:221` 按 source 查重。 |
| G4 | 保存确认可被 auto_approve/always_allow/权限模式绕过 | P0 修订第 8 条与 P3 权限边界第 4 条要求每次保存强制人类确认。需为「保存到项目产物」工具设不可旁路的强制确认（不接受 always/auto_approve/非 supervised 跳过）。 |

### 需补齐（随工具开发同步做，不阻断开工）

| # | 缺口 | 说明 |
|---|---|---|
| G5 | 产物注册扩展 | 登记时记录来源「AI 沙箱分析」+ 关联对话 ID，确保在数据管理/报告中心可见；在 `register_artifact_report` 链路上扩字段。 |
| G6 | 资源用量回报 | result 已有 `duration_ms`；CPU/内存实际峰值可用 `manager.py:1048#metrics` 快照模式补充进执行结果，供计费与展示。 |

### 可延后（机制已在，仅配置/运维动作）

| # | 事项 | 说明 |
|---|---|---|
| G7 | PyPI/CRAN 白名单域名清单 | whitelist 机制完整（egress_proxy.py），Copilot 沙箱若需装包，把 `pypi.org`/`files.pythonhosted.org`/CRAN 镜像域名写进 `studio.yaml sandbox.network.allow` 并将网络模式切 whitelist 即可；默认 none 已是安全基线。 |

## 三、已具备能力（R4 提示词直接引用，不得报成缺口）

1. 沙箱调用契约与流式协议：`manager.py:1199#exec` + `sandbox_agent.py:744 /exec`（NDJSON：stdout/stderr/result{exit_code, duration_ms, artifacts, run_log, truncated_output_files}）。
2. 默认禁出网 + 域名白名单代理：`studio_loader.py:79-127`、`manager.py:257/655/776`、`deploy/studio/egress_proxy.py`。
3. 硬限额全家桶：2C/4G/pids512/只读 rootfs/uid10001/cap_drop ALL/no-new-privileges/seccomp + 600s 默认超时整组强杀 + 10KB 流内输出截断 + 10GB 工作区配额（`manager.py:627-654`、`sandbox_agent.py:51/62-63/516/586/594-638`、`studio_loader.py:130-150`）。
4. 一会话一容器隔离、TTL 回收、复用安全/挂载基线校验与自动重建：`manager.py:238/833/798/1103/1150/1178`。
5. HITL 审批框架（Redis 跨进程 + 审计落库 + 前端确认卡片）：`studio_approval_service.py`、`frontend/src/components/ai-chat/ApprovalCard.vue`、`PendingApprovalBar.vue`。
6. 积分预扣/实结/退款接口：`cookie_service.py:114/135/182`（任务链路已实战使用：`task_cookie_consumer.py`）。
7. 产物登记主链路：`studio_context_service.py:488#register_artifact_report`（版本树 + 项目运行目录复制）；cloud 模式 `manager.py:1089#finalize_outputs`。

## 四、对 R4（P3 提示词）的修订建议

1. 「前置确认」段替换为：网络策略/资源限额/会话隔离销毁/确认门框架/计费接口/产物登记主链路**已具备**（引用本报告第三节代码位置）；「前置确认」仅剩 G1–G4 四项缺口。
2. 按手册 R4 规则在 P3 提示词开头追加阶段 0：「先补齐以下隔离能力并测试强制边界：G1 项目粒度只读挂载、G2 常驻解释器跨轮状态、G3 执行计费预扣实结、G4 保存强制确认不可旁路；完成并验证前禁止注册 run_sandbox_code 工具」。
3. e2e 越权用例按 G1 落地形态改写：恶意读取验收=宿主/其他项目/其他会话数据（运行库与 /tmp 不算）；另验证目录穿越/软链（`manager.py:178#workspace_dir` 与 `register_workdir_mount:195-199` 的防逃逸模式可作实现参照）。
