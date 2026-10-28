# Session 加速优化 TODO

> 来源：2026-10-27 星尘 AI session 卡顿排查（deepseek-v4-flash + 4 路子 agent 并发分派测试）。
> 诊断结论：非基础设施故障（无 OOM、DB/CPU 健康），是「上下文膨胀 × 模型延迟 × 串行多轮」叠加。
> 关键数据：单轮 prompt 均值 29,189 token；deepseek-v4-flash p50 6.1s / p95 16.2s，最慢一轮 37.8s；
> 同一分钟 760 条 event_sequence_violation；bridge 30 分钟 9,460 次 work-items 403。

## 优化项（按优先级）

### 1. 共享 httpx client + HTTP/2【半天】✅ 2026-10-28 `e2d9d5a2`
- 现状：`infrastructure/ai_provider/openai_compatible.py:504` 每次 LLM 调用新建 `httpx.AsyncClient`，每次重新 TCP + TLS 握手（0.3~2s）；`:727` 健康探测同样问题
- 改法：模块级共享 client，调高连接池 limits，启用 HTTP/2（对 deepseek 单域名高并发收益明显）
- 预期：每轮省 0.3~2s，10 分钟 35 次调用省 10~35s
- 落地：新增 `ai_provider/shared_http.py`（按事件循环缓存共享 client，连接池 + HTTP/2，
  `httpx[http2]` 入锁）；`_stream_once`/`list_models`/`kimi` 全切共享 client；
  池上限走 `llm_http_max_connections`/`llm_http_max_keepalive_connections`

### 2. chat_messages 流式写节流 + 事件序列风暴修复【半天】✅ 2026-10-28 `f6fefa5c`
- 现状：每个 text 事件全量 `UPDATE chat_messages` 重写整条 content（10 分钟 172 次全量写）；
  `chat_event_service._handle_violation`（application/services/chat/chat_event_service.py:75）同一分钟刷 760 条
  `agent_context_reinjected 后必须紧接 agent_turn_continued` 警告
- 改法：写库节流合并（300~500ms flush 一次或按字符数），SSE 出站保持逐 token；修复事件序列/重注入逻辑，
  打断「重注入 → prompt 变大 → 更慢 → 再重注入」恶性循环
- 预期：DB 写入量降一个量级，CPU/IO 压力显著下降
- 落地：① 根因是 Legacy 循环轮级回灌后缺 `agent_turn_continued`（LangGraph 路径本就成对发送），
  补发后与 golden 契约一致，警告风暴根除；② 写库从 %5 chunk 计数改为 0.4s 时间窗口节流
  （`chat_streaming_write_interval_seconds`）；③ `_handle_violation` 加 60s 合并抑制兜底

### 3. 模型分层路由 + 多 key 负载均衡 + max_tokens 收紧【纯配置】◐ 2026-10-28 机制就绪+操作面落地 `7c7fe7c2`
- 现状：ai_provider_configs 已有 tier/weight/latency_budget_ms 字段且 model_health_monitor 在跑，
  但未用于分层；qwen3.8-max 62k prompt 全量调用耗时 50.6s
- 改法：编排/规划轮走 deepseek-v4-flash 等快模型，最终汇总才上大模型；多 API key 按 weight 并行均衡；收紧 max_tokens
- 预期：p95 16s → <8s
- 机制审查结论（2026-10-28）：分层机制已随 LangGraph 运行时就绪且比 TODO 假设更完整——
  `ModelSelector` 每轮按 complexity/model_tier 选主模型（同 tier 健康池按成本+weight 排序），
  失败级联、length 升级 heavy、heavy 超时降级 light、`latency_budget_ms` 纳入健康判定、
  空闲 provider 主动探测；`cached_tokens` 命中率已可观测（`7c62016c`）
- 启用清单（管理员执行）：① .env 设 `DYNAMIC_MODEL_ROUTING_ENABLED=true`（契约见 .env.example `7c7fe7c2`）
  ② 管理端为各 provider 行标注 tier(light/heavy)、weight、cost_per_1m_in/out、latency_budget_ms
  ③ 验证：/admin/ai-metrics/routing/health + model_routing_decisions 审计表 + ai-metrics 延迟趋势
- 边界：Legacy 手写循环与超频 fanout **不经过**该路由（仍用 Agent 静态绑定）；如需覆盖需专项接线（受保护轮次）
- 待决策：max_tokens 收紧值按 Agent 逐个评估（Agent YAML/DB agent_templates）

### 4. DeepSeek context caching 前缀稳定化【配合 #2】✅ 2026-10-28 `7c62016c`（验证面）+ 构造审查
- 现状：DeepSeek API 自动磁盘缓存要求前缀 byte 稳定；agent_context_reinjected 反复重注入可能破坏前缀命中
- 改法：system prompt + tools 定义顺序固定，可变内容（对话历史）置后；可通过 ai_provider_configs.extra_params
  透传参数，用响应头 cache hit 字段验证命中率
- 预期：prefill 命中后单轮快 2~5 倍
- 构造审查结论：Legacy 循环 system_prompt/tools 每条消息装配一次、轮间不变，messages 仅尾部追加，
  前缀天然稳定；`_compress_context_if_needed` 压缩轮会重写早期历史（预期内失效）；重注入只追加尾部
- 已落地（命中率验证面）：`ai_call_metrics` 新增 cached_tokens 列（迁移 z5a6b7c8d9e0），
  record_ai_call 落库，daily_trend/model_breakdown 聚合 cache_hit_ratio——
  管理端 `/admin/ai-metrics/trend?model=deepseek` 可直接观察命中率，验证前缀稳定化收益
- 待做：线上观测命中率；若长期 <30% 再排查 tools 顺序/元数据抖动

### 5. bridge work-items 403 鉴权修复【1 天】◐ 2026-10-28 防御侧已落地 `db43d5fe`
- 现状：agentteams professional-pool worker 轮询 `GET /v1/work-items/assigned` 持续 403
  （30 分钟 9,460 次，约 5 次/秒），工作项未被正常认领，4 路 fanout 实际走降级路径
- 改法：修复 worker 鉴权，或 403 时指数退避；或 fanout 改 in-process asyncio.gather
  （参考 chat_service.py:2011 fanout_task）
- 预期：4 路子 agent 真正并行执行，并行测试可测出真实加速比
- 已落地（防御侧）：`production_runner.main()` 对 403 指数退避（5s 起步倍增至
  `AGENTTEAMS_WORKER_AUTH_FAILURE_BACKOFF_MAX_SECONDS`，默认 300s），成功一轮即恢复；
  403 风暴（5/s）在鉴权修好前被压制
- 待做（根因侧）：worker 身份/token 与 Bridge 侧 `worker.env` 配置不一致的排查修复；
  修复后 4 路 fanout 真实并行验收

### 6. uvicorn workers 2→4 + uvloop 确认【运维】✅ 2026-10-28 `aff39e32`
- 现状：deploy/docker/docker-compose.yml:115 `--workers 2`，SSE 长连接占满 worker，并发上限低
- 改法：chat 为 IO 密集型，workers 提到 4；确认 uvloop 已启用
- 落地：dev compose workers 2→4（与 prod/cross-web 既有 4 对齐）+ 显式 `--loop uvloop`
  （uvloop 0.22.1 本就在锁文件，auto 探测会选用，显式声明防漂移）

### 7. swap + 磁盘治理【运维】◐ 2026-10-28 已排查（`aff39e32` 记录）
- 现状：swap 8G 已用 7.9G（历史内存压力痕迹）；磁盘 92%（148G 剩余）
- 排查结论：swap 7.8G 为**历史残留**——全部存活进程 VmSwap 合计 <40MB（仅 zsh 零碎），
  内存 93G/空闲 70G，无活跃压力；可回收方式：swapoff && swapon（需 root，短暂抖动）
- 待做：磁盘清理（146G 可用，维持原建议找大文件）

### 8. AgentContextBuilder 装配并行化【中等改动】◐ 2026-10-28 `01ef80b3`（会诊路径）
- 现状：记忆检索、知识检索、工具 schema、site_settings/agent_templates/ai_provider_configs 查询
  日志看为串行 await（每 ~3 秒一轮的查询风暴）
- 改法：改 asyncio.gather 并行装配，每轮省 1~3s
- 已落地（会诊路径）：`multi_expert_consultation_service.collect()` 原先把多位专家 assemble 并发跑在
  同一 AsyncSession——SQLAlchemy async session 禁止并发操作（InvalidRequestError），异常被
  return_exceptions 静默丢弃 = 缓存未命中时会诊只幸存首位专家意见。已改为每专家独立会话真正并行，
  并加回归测试
- 关键约束（后续切片必读）：**同一 AsyncSession 不能并发查询**（已实测验证）；并行装配必须
  每协程独立会话（get_session_factory 新建），且会话需存活至 ORM 对象消费完毕
- 待做：消息装配主路径（chat_service 记忆召回 ∥ site_settings ∥ bridge 配置的串行 await，
  ~3633-3696 行）并行化；`assemble_context` 内 `_resolve_model`/`get_by_ids`/`_load_skills`
  独立会话并行化

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

---

# 报告中心与 AI 报告优化 TODO

> 来源：2026-10-28 Flow_report 接入、HTML 预览及 Report Copilot 真实会话排查。
> 现状依据：[报告中心架构](ARCHITECTURE_DESIGN/CygnusX_report_architecture.md)，尤其“外部 Flow_report”与“Copilot 结构化读取与显著性修复”相关章节。
> 状态：自动归档、预览、选文解读和结构化表格查询已验证；图表提取、重绘及优化报告交付尚未完成端到端验收。以下未勾选项为待办，不代表已实现。

## 已完成的前置修复

- [x] **外部报告归档**：按当前指定归属 root 扫描 `/data/omichub/Flow_report`，独立队列每 60 秒导入、按摘要去重；保留原始交付文件，登记项目目录及报告来源，不伪造分析 Task。
- [x] **真实报告预览与选文**：完成大 HTML、中英文切换、DataTables 兼容、选中文字带入 Copilot；真实浏览器验证父页面隔离、匿名预览拒绝与原始文件 Range 下载。
- [x] **Copilot 读取修复**：排除 MD5 清单，支持受控角色别名、完整相对路径、大 CSV 和 QC TXT；清单分页、章节避开目录、错误分类、有界上下文与数值筛选已落地，清单不再显示为新生成产物。
- [x] **真实数据解读验证**：同一报告实际 LLM 完成 6 次成功工具调用，浏览器可恢复回答。`Salt_A_vs_WTSalt` 的 DEG 在 `padj<0.05 && abs(log2FoldChange)>1` 下为 4620/21989 行；GO_UP 在 `p.adjust<0.05` 下为 30/751 行，751 仅为输入条目数。此结果只代表该比较组与阈值。

## P0：完成“解读 → 优化 → 交付”链路

- [ ] **补齐可用的“进入工作台优化”入口**：报告列表已有 `handleOptimize` 和事件声明，但最小报告卡片缺少实际触发按钮；核对查看页/Copilot 的入口并接通。将报告、当前比较组、选文、用户需求和阈值传入工作台，缺少比较组时先明确选择。验收：从真实外部报告一键创建并打开正确工作台会话，刷新后绑定仍在，`task_id=null` 不报错。
- [ ] **工作台接入完整分析数据**：现有 `link_report_files()` 遍历 `Report.files`，需核对是否只带入 HTML/PDF，补齐报告索引中的 DEG/GO/KEGG 及必要图表数据。复核当前 owner/项目权限、文件存在性与路径边界，将来源和摘要写入 Context Pack。验收：工作台能读取指定比较组的真实表格；缺文件明确提示；跨用户访问被拒绝。
- [ ] **区分原图提取与重新绘图**：先识别原报告的静态图片、内嵌图或交互图，明确可直接导出的格式；需要重新绘图时走工作台已有授权执行能力，显式记录比较组、原始/校正 P 值、fold-change 阈值、标签和输出格式。验收：火山图预览与下载可用，点数/显著数与源表一致；提取失败或缺源数据时给出具体原因。
- [ ] **优化产物登记与报告版本关联**：工作台生成的 PNG/SVG/PDF 或新版报告必须完成文件校验、登记、授权下载，并关联源报告、源表、参数和会话。复用现有产物/报告机制，核对追加产物与新版本的语义。验收：文件中心、消息产物和报告中心都能重新打开产物，原始交付文件摘要不变；失败或无文件时不显示“已生成”。

## P1：解读可靠性与导入生命周期

- [ ] **比较组、方向和显著性选择**：提供可发现的比较组及 GO/KEGG、UP/DOWN 选择，回答保留源表路径、过滤条件、匹配数/扫描数和截断说明；复核多比较组时的澄清行为。验收：不混用比较组、不把输入行数当显著数、不凭富集条目多少推断整体激活/抑制。
- [ ] **旧会话与能力说明**：旧消息中的“数据不可读取”和“已生成 124 个产物”仍属于历史记录；提供清晰的重新查询/新建会话入口，说明当前解读与工作台优化的能力边界，不静默改写历史消息。验收：用户可从旧会话发起新查询并获得真实结果，文件清单不会再次投影为新生成产物。
- [ ] **导入删除、归属与版本规则**：补齐删除后的抑制/恢复策略，避免删除记录后被周期扫描重新导入；当前统一归 root，后续增加明确的项目归属映射与受信任 Task 关联规则。审查源目录移除、内容 A→B→A、同名项目及嵌套运行目录的行为。验收：每种场景的版本与可见状态明确、重扫幂等，归属调整不造成越权。
- [ ] **导入可观测性与修复恢复**：记录逐项目导入状态、失败原因和重试结果；明确上游交付完成信号，避免扫描半成品；核查相同摘要跳过时的归档缺失/损坏检测、复制失败残留目录与并发导入恢复。验收：失败可定位、可安全重试；未完成目录不发布，缺失归档不会被当作健康报告。

## P2：性能、兼容与回归债务

- [ ] **大报告与多轮上下文预算**：对相同模型、相同提问做修复前后可比测量，记录 token、首响应/总时延、内存及并发；覆盖多页清单、长历史、超过 64 MiB/200000 行的表格和超大图。按证据优化索引缓存、按需读取与续查，确保截断有提示且结构化结果有效；不得仅提高上限掩盖资源开销。
- [ ] **扩展真实验收矩阵**：在已通过的 root 样本基础上，增加其他报告版本/比较组、多用户隔离、权限撤销、源更新、报告删除、HTTPS/代理及对象存储场景；补齐“列表 → 预览 → 选文 → AI 查询 → 工作台 → 图表 → 下载”的浏览器闭环。真实 PostgreSQL 并发、broker、存储和交付包/PDF 场景分别记录通过或阻塞，不能以单个外部样本代替全部交付链验收。
- [ ] **收敛关联测试与类型检查存量失败**：本次报告读取/导入/预览及 Chat golden 专项 80 个用例通过；扩展 Chat/sandbox 回归仍有 8 个既有失败（seq 断言、fixture 缺 `_db` 等），Chat 两个大文件仍有存量 mypy 错误。先重现并明确责任域，再分逻辑变更修复，禁止通过扩大 quarantine 或删除断言换取通过；最终按仓库要求执行完整门禁。

## 实施与验收约束

- Report Copilot 保持三项只读工具；图表生成/报告优化通过平台授权的工作台能力完成，不向 Copilot 添加 shell、流程 YAML 或 DB 写权限。
- 保持 HTML 预览 opaque-origin 隔离及现有网络/导航限制，不为兼容图表放开父页面、平台存储或凭据访问。
- 数值结论须来自当前授权源表；每项交付保留来源、参数和真实文件证据。涉及新行为时同步更新 as-built 文档，并按对应域执行测试。
- 本次运行证据索引见架构文档；`/tmp/omichub-report-breakpoint/` 与 `/tmp/report-copilot-repair/` 为临时验收材料，后续验收前将必要脱敏记录归档到项目规定位置，不能依赖临时目录长期留存。
