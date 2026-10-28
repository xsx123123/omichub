# 04 模式 3:AgentTeams(Overdrive)

核心判断:编排主链路相对完整、有测试;问题集中在三条"提前实现"的附加通道(room-events 回流、case watch、直接 Case API)以及设计文档与实现的脱节。

## 高严重度

### H1. room-events SSE 事务边界错误:回流消息与 sync cursor 可能永不落库,重连后重复落库

- 位置:`src/omichub/api/v1/chat.py:243-295`,配合 `src/omichub/api/deps.py:22-31`
- 问题:`generate_sse` 内 `service.add_message(...)`(:274)和 `matrix_sync_cursor` 写回(:259-261)只有 `flush`,commit 依赖 `get_db` 在生成器**正常结束**后执行;但 SSE 是长连接,正常永不结束;客户端断开产生 `CancelledError`/`GeneratorExit`(BaseException,不进 `except Exception`),session 关闭时未提交数据全部丢弃。
- 后果:①Element 侧用户发言在断连时整批丢失;②cursor 未持久化 → 下次连接用旧 cursor 回放 → 同一 Matrix 消息被**再次** `add_message`(代码无 `matrix_event_id` 去重)→ 聊天历史重复。
- 修复:每条外部事件处理后立即 `await db.commit()`(或独立 session 提交),并以 `matrix_event_id` 做幂等去重。

### H2. `sandbox_meta` 跨请求 read-modify-write 竞态(lost update)

- 位置:`api/v1/chat.py:252-261`(SSE 持有 meta 快照)× `chat_service.py:2748-2757, 2978-2998, 3004-3017`(超频轮写回)× `agentteams_case_watch_service.py:109-114`(watch 写回)
- 问题:三条并发路径对同一 JSONB 列"读快照→改→整体赋回",无锁/版本控制。挂着几小时的 room-events SSE 连接,其最后一次 flush 会用旧快照覆盖超频轮写入的 `overdrive_runs`/`matrix_room_id`/`overdrive_intake` 等键,反之 cursor 也会被覆盖丢失。
- 修复:`matrix_sync_cursor` 等高频键移出 `sandbox_meta`(独立列/Redis);或 `SELECT ... FOR UPDATE`/乐观锁。这正是设计 §6.4"alembic 列迁移未做"欠下的债。

### H3. 确认卡确认语义过弱:任意用户消息(包括"取消")都算作确认

- 位置:`src/omichub/application/services/agentteams_case_tool_service.py:232-243`
- 问题:`_require_pending_confirmation` 只检查"requested_at 之后存在**任意一条** role=user 消息"。用户在确认卡弹出后回复"不用了/取消/换个方案"同样通过校验,LLM 下一步即可创建 Case。与 `record_confirmation_request` 注释"禁止模型首次调用伪造 `_confirmed` 直接创建"(:141)的安全意图不符。
- 修复:前端确认按钮发送带结构化标记的消息(metadata 或专用类型),后端校验该标记而非任意 user 消息。

### H4. 直接 API `POST /agent-teams/cases` 绕过项目归属与流程白名单

- 位置:`src/omichub/api/v1/agentteams.py:105-119` → `agentteams_service.py:180-241`
- 问题:工具路径有 `_session_owns_project` 校验(`agentteams_case_tool_service.py:81`)和 `agentteams_chat_flow_whitelist` 白名单(:68-71);直接 API 路径**两者都没有**——任何登录用户可为任意 `project_id`、任意 `flow_id` 创建 Case 并触发 preflight,白名单形同虚设。
- 修复:API 层复用项目归属校验与 flow 白名单(或显式文档化"API 路径不受白名单约束"并加管理员审计)。

## 中严重度

### M1. degraded 的 `mode_changed` 每个超频轮重复发送,前端每轮刷一条系统消息

- 位置:`chat_service.py:2774-2778`;前端 `frontend/src/stores/agentHub.ts:1585-1609`
- 问题:Gateway 不可用时**每一轮**超频都 yield `mode_changed{enabled:true, degraded:true}`;前端 `onModeChanged` 每收一次就 push 一条"Matrix Gateway 不可用…"系统消息(id 为 `mode-overdrive-${Date.now()}`,不去重)。契约 §4.3 定义 mode_changed 是"模式被**切换**时发出",降级不是切换。持续对话下聊天区刷屏。
- 修复:同一会话只发一次(状态变化时),或前端按内容去重。

### M2. 前端 room-events 无重连,且新建房间后不会订阅

- 位置:`frontend/src/stores/agentHub.ts:244-282`(调用点 :974、:1580)
- 问题:`startRoomEvents` 只在会话加载/创建时调一次:新会话此刻房间未建 → 404 静默 return;之后第一轮超频建房后**没有任何地方重新调用**它;流意外结束也无重试(对比 `AgentTeamsCaseView.vue:294` 有 300ms 自动重连)。结果:新会话的 Matrix 外部消息回流在刷新页面前完全不可用——设计 §6.5 的"双向同步"对新会话实际失效。
- 修复:超频轮首次建房成功后触发订阅;流断开加退避重连。

### M3. Case watch 全表扫描 + 无并发/重叠防护 + 失败静默

- 位置:`agentteams_case_watch_service.py:49-55`;`infrastructure/celery_app/tasks/agentteams.py:27-35`;`celery_app/celery.py:124-126`
- 问题:①每 60s(`config.py:130`)拉出**所有** `sandbox_meta` 非空会话(不用 JSONB 过滤 `agentteams_case_ids`),逐个串行 HTTP 调 Bridge,规模大后单次扫描可能超过间隔;②beat 任务重叠时两个扫描读同一 meta 快照,`seen` 去重只在各自内存 → 同一状态变化通知两次、插入两条 system 消息;③任务吞掉所有异常仅 `logger.warning`,无重试/告警/指标;④跑在 `analysis` 队列(celery.py:79),可能被重型分析任务饿死。
- 修复:JSONB 存在性过滤;加分布式锁/singleton 守卫;失败计数接告警;迁到独立队列。

### M4. `approve_and_submit_task` TOCTOU;`create_case` 三步无补偿

- 位置:`agentteams_service.py:250-300`、`:207-241`
- 问题:审批提交是"查状态→建 approval→(可能)建 submit-01→提交 task"四步,并发双击/重试会完整走两遍(submit-01 查重基于旧快照);task 提交带固定 `idempotency_key`(:290)兜底,但 approval 和 work-item 会重复创建。`create_case` 建 Case→建 work-item→preflight 三步无补偿,preflight 失败留下半成品 Case(有 preflight work-item 但无输入快照,后续 `approve_and_submit_task` 因快照缺失永远报错,:253-255)。
- 修复:Case 创建加幂等键/补偿删除;submit 流程在 Bridge 侧做事务化。

### M5. HTTP 客户端错误语义吞噬 + 无防护的 `response.json()`

- 位置:`agentteams_service.py:412-420`;`agentteams_room_gateway_service.py:100-115`
- 问题:除 404 外所有错误(含 400 校验失败、401/403 令牌错误)统一变成"暂时不可用",排障时无法区分配置错误与网络故障;`response.json()` 在 try 块外,非 JSON 响应抛未包装异常直达 500。两处客户端均无重试、每请求新建 `httpx.AsyncClient`(连接无法复用)。
- 修复:按状态码分层错误(4xx→配置/校验错误,5xx/网络→暂不可用);`response.json()` 包 try;复用 client。

### M6. Overdrive manifest 文件状态机无锁

- 位置:`overdrive_runtime.py:69-77, 158-237`
- 问题:同一 session 用户连发两条消息 → 两个 `_run_overdrive_turn` 并发读改写同一 `manifest.json`,`os.replace` 最后写入者胜,任务状态/pause 指令丢失。另外:①resume 触发条件(:161-164)对英文 "resume" 子串误判(用户说"看我的 resume 文件"即触发恢复);②兜底工作区 `/tmp/omichub-overdrive-workspaces`(:60)未收紧权限,多租户主机有跨用户可见风险。
- 修复:同会话超频轮串行化(会话级锁);文件操作用 `fcntl` 锁;兜底目录 `chmod 700`。

## 低严重度

- **L1** `chat_service.py:2468-2474`:manager_sender 的 `name` 硬编码 `"Manager"`,设计 §1.1 要求 Manager 以当前会话 agent 人格(星尘 AI)出现——应用 `manager.name`。
- **L2** `agentteams_case_tool_service.py:37`:`agentteams_next_actor` 返回 `"quality-controller"`,但 Bridge 身份体系是 `quality-auditor`(`integrations/agentteams/bridge/.../models.py:12`、设计 §2.3)——展示给用户的"下一步处理人"是不存在的身份。
- **L3** `chat_service.py:2510-2518 / 2968-2974`:对 `get_session()` 结果的"二次 await + `coroutine.close()`"防御代码——`get_session` 是确定性 async 函数(:1377),永不双重 awaitable。死代码,疑似盲修历史 bug,应清理。
- **L4** `agentteams_bridge_settings_service.py:126-128`:`_resolve_secret` 使已存 token 无法通过 API 清空(空串/掩码都解析为保留);用户把 token 字面设为 `"********"` 会被静默忽略。
- **L5** sandbox_meta 只增不删:`agentteams_case_idempotency`(:265-270)、`agentteams_case_confirmation`(:158-160)、`agentteams_case_ids/status/notified/titles` 随会话寿命无限膨胀(`overdrive_runs` 有 `[-9:]` 截断,其它没有)。
- **L6** `agentHub.ts:216`(`applyRoomSpeechEvent`)与 `:173`(`applyAgentTeamsCaseEvent`):`find(...) || currentSession` 兜底会把 session_id 不匹配的事件塞进当前会话——应丢弃而非兜底。
- **L7** `_validate_element_url`(`agentteams_bridge_settings_service.py:160-168`)仅校验 scheme + 几个子串;Bridge 下发的 `element_room_url` 经 `chat_room`(`agentteams_service.py:128-145`)直接进前端 iframe——Bridge 被攻破即成钓鱼入口,建议加域白名单。
- **L8** `api/v1/agentteams.py:165-183`:Case 事件 SSE 的归属校验在生成器首迭代内(`agentteams_service.py:347`),200 响应头已发出后才抛 BusinessError——无权访问表现为"200 后断流"而非 403。
- **L9** 命名分歧:room_speech 实时 chunk 用蛇形 `task_status`/`error_summary`(`chat_service.py:2832-2833`),落库 metadata 用驼峰 `taskStatus`/`errorSummary`(:2802-2803);前端两套都读,能工作但契约 §4.3/§4.4 未记录此分歧。
- **L10** `agentteams.py:62`:`sample_sheet` 上限 1 万条任意 dict、无单条大小约束,超限只能等 Bridge 的 `max_request_bytes` 拒绝。

## 设计与实现的差距

1. **"冻结契约"已实质膨胀**。契约 §4.3 只有 `mode_changed`/`room_speech` 两种新 chunk;实现额外发出 `overdrive_progress`、`room_speech_delta`、`worker_stalled`、`schedule_warning`、`schedule_fallback`、`ask_request`(chat_service.py:2840-2904, 3043, 3261-3278),文档只字未提。第三方按契约对接会丢一半信息。
2. **事件序列与契约不符**。§4.3 规定 `room_speech(manager)×1 → worker×N → room_speech(manager 汇总) → done`;实现 assignments=0 时只发一条 manager 发言就 return(`chat_service.py:2906-2916`),无收尾。契约应补"0 分工时只有 1 条"。
3. **Agent 发现口径与文档不一致**。§2.4 定义"所有可用 agent"=`active_only` + 排除 router;实现额外要求 `features.subagents_spawnable`(`chat_service.py:2480-2482`)。未标该 feature 的 agent 在超频中不可见,与"自动发现当前所有可用 Agent"的愿景(§1.1)不符——文档或种子 YAML 有一处需要同步。
4. **Matrix 数据面是"过渡方案"且自认未完成**(§6.3/§6.6):Worker 不驻留房间、端到端 Element 联调未验收、room-events 对新会话实际不通(M2)——双向同步目前只是单向镜像 + 一条不可靠的回流通道。
5. **`matrix_room_id` 的 alembic 迁移未做**(§6.4 自认),过渡寄生的 `sandbox_meta` 正是 H2 竞态与 H1 提交问题的温床;第二期验收前必须补上。
6. **已做对的部分(勿破坏)**:第二期"OmicHub 永不持有 Matrix 凭证"满足(gateway 代理 + `require_manager` 用 `secrets.compare_digest`,gateway/security.py:18);Bridge 生产密钥有启动校验(bridge/config.py:35-60);防双重回答(:4110-4111 return)、关键词否定优先(:281-291)、降级不阻断对话、masked secret 回显、TOTP 保护管理端点,均符合设计。

## 修复建议优先级

H1/H3 修复成本都很低,优先;随后 H4、H2;M1/M2 直接影响用户可感知体验,建议同迭代完成。
