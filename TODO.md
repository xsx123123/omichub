# Session 加速优化 TODO

> 来源：2026-10-27 星尘 AI session 卡顿排查（deepseek-v4-flash + 4 路子 agent 并发分派测试）。
> 诊断结论：非基础设施故障（无 OOM、DB/CPU 健康），是「上下文膨胀 × 模型延迟 × 串行多轮」叠加。
> 关键数据：单轮 prompt 均值 29,189 token；deepseek-v4-flash p50 6.1s / p95 16.2s，最慢一轮 37.8s；
> 同一分钟 760 条 event_sequence_violation；bridge 30 分钟 9,460 次 work-items 403。

## 优化项（按优先级）

### 1. 共享 httpx client + HTTP/2【半天】
- 现状：`infrastructure/ai_provider/openai_compatible.py:504` 每次 LLM 调用新建 `httpx.AsyncClient`，每次重新 TCP + TLS 握手（0.3~2s）；`:727` 健康探测同样问题
- 改法：模块级共享 client，调高连接池 limits，启用 HTTP/2（对 deepseek 单域名高并发收益明显）
- 预期：每轮省 0.3~2s，10 分钟 35 次调用省 10~35s

### 2. chat_messages 流式写节流 + 事件序列风暴修复【半天】
- 现状：每个 text 事件全量 `UPDATE chat_messages` 重写整条 content（10 分钟 172 次全量写）；
  `chat_event_service._handle_violation`（application/services/chat/chat_event_service.py:75）同一分钟刷 760 条
  `agent_context_reinjected 后必须紧接 agent_turn_continued` 警告
- 改法：写库节流合并（300~500ms flush 一次或按字符数），SSE 出站保持逐 token；修复事件序列/重注入逻辑，
  打断「重注入 → prompt 变大 → 更慢 → 再重注入」恶性循环
- 预期：DB 写入量降一个量级，CPU/IO 压力显著下降

### 3. 模型分层路由 + 多 key 负载均衡 + max_tokens 收紧【纯配置】
- 现状：ai_provider_configs 已有 tier/weight/latency_budget_ms 字段且 model_health_monitor 在跑，
  但未用于分层；qwen3.8-max 62k prompt 全量调用耗时 50.6s
- 改法：编排/规划轮走 deepseek-v4-flash 等快模型，最终汇总才上大模型；多 API key 按 weight 并行均衡；收紧 max_tokens
- 预期：p95 16s → <8s

### 4. DeepSeek context caching 前缀稳定化【配合 #2】
- 现状：DeepSeek API 自动磁盘缓存要求前缀 byte 稳定；agent_context_reinjected 反复重注入可能破坏前缀命中
- 改法：system prompt + tools 定义顺序固定，可变内容（对话历史）置后；可通过 ai_provider_configs.extra_params
  透传参数，用响应头 cache hit 字段验证命中率
- 预期：prefill 命中后单轮快 2~5 倍

### 5. bridge work-items 403 鉴权修复【1 天】
- 现状：agentteams professional-pool worker 轮询 `GET /v1/work-items/assigned` 持续 403
  （30 分钟 9,460 次，约 5 次/秒），工作项未被正常认领，4 路 fanout 实际走降级路径
- 改法：修复 worker 鉴权，或 403 时指数退避；或 fanout 改 in-process asyncio.gather
  （参考 chat_service.py:2011 fanout_task）
- 预期：4 路子 agent 真正并行执行，并行测试可测出真实加速比

### 6. uvicorn workers 2→4 + uvloop 确认【运维】
- 现状：deploy/docker/docker-compose.yml:115 `--workers 2`，SSE 长连接占满 worker，并发上限低
- 改法：chat 为 IO 密集型，workers 提到 4；确认 uvloop 已启用

### 7. swap + 磁盘治理【运维】
- 现状：swap 8G 已用 7.9G（历史内存压力痕迹）；磁盘 92%（148G 剩余）
- 改法：找出 swap 占用的进程（大概率是某容器）并处理；清理磁盘

### 8. AgentContextBuilder 装配并行化【中等改动】
- 现状：记忆检索、知识检索、工具 schema、site_settings/agent_templates/ai_provider_configs 查询
  日志看为串行 await（每 ~3 秒一轮的查询风暴）
- 改法：改 asyncio.gather 并行装配，每轮省 1~3s

## 验证方式
- `ai_call_metrics` 表：关注 avg/p95 duration_ms、平均 prompt_tokens 变化
- web 容器日志：event_sequence_violation 频率、UPDATE chat_messages 频率、connect_tcp/start_tls 出现频率
- bridge 日志：work-items 403 频率
- 端到端：同一并行分派测试的 wall time 对比

---

# 助手聊天界面统一改造 TODO

> 手册：`docs/info/26.10.26/CygnusX助手界面统一实施手册.md`
> 阶段 0 现状报告（已完成）：`docs/info/26.10.26/CygnusX助手界面统一_阶段0现状盘点报告.md`
> 状态：暂不启动，待后续按下列顺序推进；每阶段独立提交、独立验收。

## 推进清单

- [ ] 0. 前置：`git add -A && git commit -m "chore: 统一改造前 WIP 存档"`
- [ ] 1. 阶段 0.5 止血包：投手册 §6.4 提示词（5 条）→ 按附录 A② 验收（6 行对照表）→ commit "feat(agent-chat): 阶段0.5 止血包"
- [ ] 2. 阶段 1 契约先行：投 Part II 阶段 1 提示词 → 按附录 A③ 验收（关键：视觉零变化！）→ commit
- [ ] 3. 阶段 2 FeedbackBar（双渲染器第一个组件，契约里已含 agent_id 埋点）
- [ ] 4. 阶段 3 MetaRow
- [ ] 5. 阶段 4 EntityChip（顺手验证 SRR/PRJNA 高亮）
- [ ] 6. 阶段 5 ProcessCard（steps/progress 双模式 + 路由通知卡同族化）
- [ ] 7. 阶段 6 InputDock（disabledSlots 落地 + 寻宝鼠 onQueue 接线）
- [ ] 8. 阶段 7 MessageShell（回归面最大，放最后）

## 备注

- 清单中的「手册 §6.4 / Part II / 附录 A」在当前 v1.0 手册中未找到对应章节（现文件为 §0~§5），启动前需确认手册版本与章节号。
- 阶段 0 报告已确认：两界面无共享聊天组件，寻宝鼠为 Vue 外壳 + Shadow DOM + React island；统一路线为「契约先行 + 双渲染器」。阶段 1 验收的「视觉零变化」与此一致。

---

# 子 Agent（parallel_subagents）优化与真实验收 TODO

> 来源资料包：`docs/info/26.10.27/CygnusX_SubAgent_优化与测试资料包_2026-10-27/`
> - `CygnusX_SubAgent_执行可靠性与产物闭环优化方案_2026-10-27.md`（优化方案 v1.0，P0/P1 工作包）
> - `CygnusX_SubAgent_代码Agent优化与真实测试提示词_2026-10-27.md`（可直接投喂代码 Agent 的主提示词 + 诊断/冒烟短提示词）
> - `CygnusX_SubAgent_全链路测试矩阵与验收记录模板_2026-10-27.md`（R01–R34 矩阵 + Gate 0~5 + 验收记录模板）
> 状态：待启动。总目标：把"子 Agent 返回了文字"改造为"任务经准入、在有权限的环境真实执行、目标校验通过、生成并登记产物、结构化结果回父 Agent、前端显示与证据一致"。

## 已完成的关联修复（2026-10-27）

- [x] **workspace_write / workspace_edit 产物不回填 artifacts**：主 Agent 用 `workspace_write` 写到 `output/` 的报告不进消息产物窗口。已在 `src/cygnusx/application/services/studio_tools.py` 的 `_workspace_write`/`_workspace_edit` 增加 `_output_artifact_entry` 回填（仅 `output/` 内文件），新增 3 个单测（`tests/unit/test_studio_tools.py`）。前端零改动。
- [ ] **fan-out 子 Agent 产物不回灌父会话**：`parallel_subagent_service.py` fan-out 信封 `ui_payload` 只有 `fanout_run_id/elapsed_s/progress`，子工作目录 `{storage}/subagents/{run_id}/{index}/` 产物不复制进父 chat-output、不注册 file_records。方案：汇总处收集 child workdir 产物 → `chat-output/{parent_session_id}/output/subagents/{task_id}/` + ui_payload.artifacts。

## 核心问题清单（按优先级）

### P0
- [ ] **假成功**：汇总 `4/4 ok` 但 code 子 Agent 实际无执行器、未生成文件。拆分三个判定：`execution_status`（循环正常结束）/ `outcome_status`（有外部可验证证据）/ `artifact_status`（文件真实存在+可访问）；执行/产物型任务必须由服务端 tool receipts + 文件校验判定，禁止 LLM 自评成功；纯问答标记 `answered_unverified`。
- [ ] **B/C/D 正文丢失**：只有状态无正文。沿 `Provider → SubAgentRunner → ChildResult → aggregate → llm_payload → 父模型 → SSE/前端` 逐层比对存在性/长度/hash；大正文持久化为 `detail_ref`，父 LLM 只收短摘要+引用。
- [ ] **Capability Preflight**：按任务能力（`python.execute`/`artifact.write`/`research.retrieve`/`artifact.publish`/`approval.request`）而非 Agent 名称准入；实际工具集服务端求交，缺失即 `blocked/CAPABILITY_MISSING`，严禁静默成功；产出真实 `subagent_capability_matrix.md`（agent × mode × 有效工具 × 产物写权限）。
- [ ] **产物四阶段闭环**：Produced（子沙盒 stat）→ Verified（类型/大小/sha256/断言）→ Registered（artifact_id+receipt 关联）→ Published（父工作区/文件中心可访问，`parent_reopen_check=passed`）。父空间 MISSING 只能证明"父空间不可见"，不能推断未生成。
- [ ] **配额时机**：5 任务超上限被拒不占 accepted quota；同轮改 4 任务应能受理（validation retry）；accepted 后再投不同集合拒 `SUBAGENT_TURN_LIMIT`；同 request_key 重放返回原 run、不同 payload 报 conflict；统一意图预分派与 Legacy/LangGraph 共享 coordinator 防双占。顺序：`validate → resolve agents → spawnable → capability preflight → policy → atomic reserve → run_started`。

### P1
- [ ] **SSE/前端状态机**：按 `run_id/task_id/seq` 去重投影，拒绝不出现幽灵任务卡；`max_parallel=4/max_concurrent=3` 应显示 3 running+1 queued；`completed` 与 `verified succeeded` 分开展示；blocked 不显示绿色成功；产物不可用不出假下载链接。普通聊天用紧凑 Fan-out 卡片，超频保留 Wave 壳层，TaskCard 共享。
- [ ] **schema/配置漂移统一**：`tool_configs/tools_schema.yaml` maxItems、运行时上限（4/3）、提示词、运行时 policy 一致化；`shania` 等非 spawnable 目标预检拒绝。
- [ ] **子任务级并行实测**：现有证据只是工具层 4×sleep(5)（并行 5.14s/串行 20.23s）。需在 SubAgentRunner 采服务端 spans（同进程 monotonic），验证峰值 active≤3、queued 时间、≥2 任务重叠；预期两批 ≥10s，不能把"4 路 5s 全完成"当验收条件。
- [ ] **超时/重试/计费**：1200s/24 轮按 source/mode 拆分预算；重试仅限明确瞬态错误且核对幂等键；`cached_tokens` 合并单测红灯先修（quarantine 不掩盖）；审计不落明文 key/绝对路径。

## 分阶段工作包

- [ ] **WP0 只读调查**：8 类入口矩阵（Legacy/LangGraph/统一意图/超频前台/超频 Celery/AgentTeams/Goal/MAS DAG）；输出 `docs/subagents/01_current_runtime_audit.md`、`02_capability_matrix.md`、`evidence_index.md`；每条问题有代码行号 + run/trace ID 证据。关键代码：`parallel_subagent_service.py`（子循环/semaphore/preflight）、`parallel_subagent_tool_service.py`（薄壳）、`chat_service.py`（Legacy/预分派/超频前台/SSE）、`chat/runtimes/langgraph_runtime.py`、`goal_adapters/fanout_adapter.py`、`infrastructure/celery_app/tasks/overdrive.py`（超频后台 workspace 授权）、`core/config.py`（subagent_* 配置）、`agent_service._filter_runtime_builtin_tools`、前端 `useAgentChatStream.ts`。
- [ ] **WP1 结果与准入 P0**：versioned ChildResult v2 + TaskContract（兼容旧字段）；outcome evaluator 不靠 LLM；配额先验后占 + 双路由幂等。退出条件：R01–R12 全绿，`4/4 ok` 不再覆盖目标失败。
- [ ] **WP2 产物闭环**：复用 Case/Artifact/Evidence/Manifest + MinIO/PG 做五步闭环；幂等键 `run_id+task_id+logical_name+digest`；取消/超时保留已验证的其他子任务产物（父任务=partial）。退出条件：manifest 带 hash、父空间重读 hash 一致、跨项目越权拒绝。
- [ ] **WP3 UI/SSE**：`CollaborationContainer → FanoutCompactPanel/OverdriveWavePanel → 共享 SubagentTaskCard`（按现有组件最小增量改造，不重复造同职责组件）；状态机 + 事件版本；断线走授权 snapshot/replay；取消透传到子执行器。退出条件：拒绝/运行/阻塞/部分完成/超时/重连截图无错配。
- [ ] **WP4 灰度回归**：先纯问答 → code/viz 授权工作台 → 白名单扩大；输出修复报告（变更文件/提交/测试通过表/权限复核/回滚方法）。

## 测试矩阵执行顺序（R01–R34，详见资料包测试矩阵文档）

- [ ] Gate 0 只读诊断：R01、R06、R07、R08、R11、R15
- [ ] Gate 1 契约单测/集成：R01–R16、R20（重点：R02 同轮 5→4、R09 双引擎一致、R10 预分派不双占、R15 B/C/D 正文缺失检测）
- [ ] Gate 2 并行与失败隔离：R17–R19（子任务级 spans，非工具层外推）
- [ ] Gate 3 授权执行/产物：R21–R27（print('hello') stdout、.py sha256、matplotlib PNG 可解码、发布父回读、重名幂等、`../` 拒绝）
- [ ] Gate 4 UI/生命周期：R28–R33（SSE 乱序重连、5 拒无幽灵卡、4/3 queued、三态 UI、取消传播、前后台 gate 一致）
- [ ] Gate 5 CI/部署：R34 + `pytest tests/unit -m "not quarantine"` 全绿（存量失败显式列债，不 skip）
- 运行纪律：隔离环境、registry canonical ID、每 case 记录 run_id/turn_id/task_id + evidence_ref；指标分离 `accepted/terminal/verified_success/published_artifact` 四计数；验收记录按资料包 G 节模板逐条填。

## 红线（判 FAIL）

- 未执行代码却 `4/4 成功`；用常识结果冒充真实 stdout；`LLM response received` 映射 `task succeeded`；B/C/D 正文丢失但聚合不报告；子隔离目录有文件但父空间无访问引用却写"已交付"；工具层并行冒充子循环层并行；`4/3` 显示 4 running 或拒绝分派却 `0/5` 全绿；绕过 safe_only/审批给普通 Agent 提权；修一个入口破坏超频/AgentTeams/Goal/MAS。

## 快捷提示词（直接复制使用，全文见资料包）

- **诊断短提示词**：只读调查 5 大问题（假成功 / code 无执行器 / B/C/D 无正文 / 产物不回流 / 配额双拒），输出函数路径 + 有效工具清单 + 准入顺序 + P0/P1 优先级，不改代码不提权。
- **主提示词**：G0 审计 → G1 假成功 → G2 正文回灌 → G3 capability preflight → G4 产物闭环 → G5 配额幂等 → G6 SSE/UI → G7 子任务级并行验证 → G8 R01–R34 回归；Phase 0~4 顺序执行，交付 `docs/subagents/01~06` 文档组。
- **冒烟提示词**（需 P0 已修）：Gate 0→5 真实 E2E——5→4 同轮重试幂等 → 四路短答 ChildResult/detail_ref → serial/parallel 对照 → 授权工作台 print/Py/PNG + sha256/manifest/发布/父空间重读。
