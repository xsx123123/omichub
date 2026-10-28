# GPT-5.6 实施修复提示词(OmicHub AI 三模式问题修复)

> 使用方法:把本文件全文作为系统/首条提示词发给 GPT-5.6(或任何编码 agent),它会按优先级逐项修复。每个任务独立可验收,建议按 Task 顺序执行,每完成一个 Task 跑对应验证。

---

## 0. 你的角色与工作方式

你是资深全栈工程师,在 Linux 机器上工作,项目根目录是 `/home/zj/zj_code_libarary/OmicHub`(FastAPI + Celery + Vue3/Pinia/TS)。你的任务是修复一次代码审查发现的问题。**审查报告全文在 `docs/26.8.7/` 目录**(README.md 是总览,01~05 是分类问题清单,每条带 `文件:行号`、问题描述、修复建议)。动手前必须先读对应条目和涉及的代码。

工作纪律:

1. **最小改动**:只修当前 Task 描述的问题,不顺手重构、不改无关代码风格。
2. **先读后改**:修改任何文件前,先 Read 该文件的相关区域,不要凭记忆或凭本提示词的行号直接改(行号可能已漂移,以符号/函数名定位)。
3. **不破坏已做对的部分**:每份报告的"值得肯定的设计"一节列出的机制(路径防护、jsonb_set 原子合并、分享 token 哈希、HMAC 控制令牌等)必须保持。
4. **禁止 git 变更**:不要 `git commit/push/reset/rebase`,只改工作区文件。
5. **每完成一个 Task 必须验证**:后端跑相关单测(`pytest tests/ -k <关键词>`,项目虚拟环境在 `.venv/`,用 `.venv/bin/pytest`);前端跑 `cd frontend && npx vue-tsc --noEmit`(或 `npm run type-check`,若存在)和 `npm run build` 至少保证不破坏编译。没有现成测试覆盖的新逻辑,在 `tests/unit/` 下补最小测试(参考已有测试的写法)。
6. **遇到前置冲突先报告**:如果代码现状与本提示词描述不符(例如问题已被修过),跳过该 Task 并明确说明,不要强行改。
7. 完成后输出:每个 Task 一段小结——改了哪些文件、为什么这样改、跑了什么验证、结果如何。

## 1. 背景知识(三分钟版)

OmicHub 有三种 AI 交互模式,共享同一套聊天主链路:

- **模式 1 简单 AI 助手**:前端 `/ai`,后端 `POST /chat/stream`(SSE)→ `ChatService._route_to_agent` 用一次 LLM 调用把问题分派给专家 agent,可经 `agent_handoff_service` 转交。另有一条 WS Copilot 旧链路 `api/v1/ai.py`(计划收敛)。
- **模式 2 AI 工作台(Studio)**:前端 `/studio/:sessionId?`,复用 `/chat/stream`,每会话一个 Docker 沙盒容器 `studio-{session_id[:8]}`,Web 经 bind-mount 工作区内的 Unix Socket 直连容器内 `deploy/studio/sandbox_agent.py` 执行代码;`timeout>600s` 的执行转 Celery `run_studio_sandbox`。审批(HITL)= Redis BLPOP 300s。
- **模式 3 AgentTeams**:超频轮(overdrive)多 agent 编排 + Matrix room gateway(消息回流 SSE)+ Bridge case 服务(HTTP)+ celery 60s case watch。

关键基础设施:

- 流式聊天的 DB 事务:`api/v1/chat.py` 的 `generate_sse` 复用请求级 `DbSession`,只在流正常结束(`"done"`)后 `db.commit()`;`api/deps.py:22-31` 在生成器被取消时 rollback。**这是多个问题的共同根因。**
- 会话可扩展状态存在 `ChatSessionModel.sandbox_meta`(JSONB),多条并发路径对它做"读快照→改→整体赋回",存在 lost update。
- LLM 调用公共层:`src/omichub/infrastructure/ai_provider/litellm_provider.py`(litellm)和 `openai_compatible.py`。
- 前端全局单例 store:`frontend/src/stores/agentHub.ts`(模式 1/2 共用);流式 composable 有四套(`useChatStream.ts`、`useAgentChatStream.ts`、`useAIWebSocket.ts`、`useStudioRunStream.ts`)。

## 2. 任务清单(按优先级)

### Task 1(P0,后端,最小):修复流式 token 用量统计丢失

- 文件:`src/omichub/infrastructure/ai_provider/litellm_provider.py`
- 问题:`stream_chat` 的 kwargs 从未传 `stream_options={"include_usage": True}`,OpenAI 兼容端点流式默认不返回 usage,导致 `record_ai_call_metrics(..., usage=None)` 记录 token 全 0,用量统计/成本告警严重失真。
- 修法:在 `_build_kwargs`(约 :128)注入 `stream_options={"include_usage": True}`(仅流式调用);确认 litellm 对不支持端点会自动降级(查项目内 litellm 版本行为,必要时 try/except 兜底去掉该参数重试一次)。
- 验证:新增/更新单测,模拟流式 chunk 末尾带 usage 的场景,断言 metrics 记录了非 0 token。

### Task 2(P0,后端,小):Provider 重试不得无条件丢弃 tools

- 文件:`src/omichub/infrastructure/ai_provider/openai_compatible.py:223-237`
- 问题:`attempt_tools = tools if attempt == 0 else None`,瞬时网络错误重试也丢 tools,该轮模型静默失去全部工具能力。
- 修法:仅当首次失败原因是"带 tools 空响应/疑似 tools 不兼容"时才去 tools 重试;网络类 retryable 错误(`:265-266`)重试保留原 tools。
- 验证:单测覆盖两种重试分支,断言网络错误重试时请求体仍含 tools。

### Task 3(P0,后端,小):AgentTeams 确认卡语义修复

- 文件:`src/omichub/application/services/agentteams_case_tool_service.py:232-243`;前端确认按钮组件(在 `frontend/src` 中搜确认卡/`agentteams` 相关组件)
- 问题:`_require_pending_confirmation` 只检查"requested_at 之后存在任意 role=user 消息",用户回复"取消"也算确认通过,LLM 随即创建 Case——授权漏洞。
- 修法:前端确认按钮发送带结构化标记的消息(如 metadata `{"agentteams_confirm": "<token>"}` 或专用消息类型,沿用项目已有约定);后端校验该标记且与 pending 的 confirmation token 匹配,不再接受任意 user 消息。保持 `record_confirmation_request` 防伪造意图(:141 注释)。
- 验证:单测断言:确认卡后回复"取消"(无标记)→ 拒绝创建;带正确标记 → 通过;标记不匹配 → 拒绝。

### Task 4(P0,后端,小):Case API 补项目归属校验与 flow 白名单

- 文件:`src/omichub/api/v1/agentteams.py:105-119`、`src/omichub/application/services/agentteams_service.py:180-241`
- 问题:直接 API `POST /agent-teams/cases` 没有工具路径的 `_session_owns_project` 校验(`agentteams_case_tool_service.py:81`)和 `agentteams_chat_flow_whitelist`(:68-71),任何登录用户可为任意 project/flow 建 Case。
- 修法:把这两项校验提取为可复用逻辑(或直接复用 service 层函数),API 路径同样执行;无权时返回 403/404(与项目现有归属校验风格一致,如 `_get_studio_session` 的 404 防探测)。
- 验证:单测/集成测试:他人 project_id → 拒绝;非白名单 flow_id → 拒绝;合法请求 → 正常。

### Task 5(P0,前后端,小):degraded mode_changed 去重

- 文件:`src/omichub/application/services/chat_service.py:2774-2778`、`frontend/src/stores/agentHub.ts:1585-1609`
- 问题:Gateway 不可用时每轮超频都发 `mode_changed{degraded:true}`,前端每收一次 push 一条系统消息,刷屏。
- 修法:后端在同一会话内仅在降级状态**变化**时发送(用 `sandbox_meta` 或内存标记记录上次状态,注意并发写方式要与现有 jsonb_set 原子合并一致);前端再按内容去重兜底。
- 验证:单测模拟连续两轮 degraded,断言只产出一次事件。

### Task 6(P1,后端,中):room-events SSE 即时提交 + 幂等去重

- 文件:`src/omichub/api/v1/chat.py:243-295`、相关 `agentteams_room_gateway_service.py` / `chat_service` 的 add_message 路径
- 问题:room-events 是长连接 SSE,`add_message` 和 `matrix_sync_cursor` 只有 flush,commit 依赖生成器正常结束(永不发生)→ 断连时整批丢失;cursor 未持久化 → 重连用旧 cursor 回放 → 消息重复(无 `matrix_event_id` 去重)。
- 修法:每条外部事件处理后即时 commit(用独立 session,避免与请求级 session 纠缠);消息落库以 `matrix_event_id` 幂等去重(查重或唯一约束,选与项目迁移风格一致的方案;若加列需要 alembic 迁移,在 `alembic/versions/` 下新增,参考最近一个迁移文件的写法)。
- 验证:测试模拟:同一 event_id 两次投递只落一条;断连重连后无重复消息。

### Task 7(P1,前端,小):建房后重新订阅 room-events + 断线重连

- 文件:`frontend/src/stores/agentHub.ts:244-282`(调用点 :974、:1580)
- 问题:`startRoomEvents` 只在会话加载时调一次,新会话此刻房间未建(404 静默 return),之后超频建房后无人重新订阅,流意外结束也无重试——新会话的 Matrix 回流完全失效。
- 修法:超频轮首次出现 `matrix_room_id` 时(可在 SSE chunk 处理或会话 meta 刷新处)触发 `startRoomEvents`;流断开加指数退避重连(1s→30s 封顶,参考 Task 13 的统一重连策略)。
- 验证:手动或组件测试:新会话首轮超频后 room-events 连接建立。

### Task 8(P1,后端,中):Studio 断连杀子进程

- 文件:`deploy/studio/sandbox_agent.py:216-344`(`_stream_exec`)
- 问题:客户端断连时 `finally` 只清理日志/脚本,不杀子进程;`killpg` 只在超时分支执行。用户"停止"后代码继续跑,timeout 检查也失效。
- 修法:`finally` 中增加 `if proc.returncode is None: os.killpg(...)` + 短 wait;注意与超时分支去重(避免二次 kill 报错)。
- 验证:集成/手动测试:启动一个 sleep 长命令,中断 SSE,确认沙盒内进程组已退出。

### Task 9(P1,后端,中):审批链路修复(心跳 + 恢复语义)

- 文件:`src/omichub/api/v1/chat.py:119-163`、`src/omichub/application/services/studio_approval_service.py:109-132, 134-169`、`src/omichub/api/v1/studio.py:538-576`、前端 `agentHub.ts:1331-1352`
- 问题:①BLPOP 等待期间 SSE 零字节,网关 60s 空闲超时断连,消费决议的 BLPOP 消失;②刷新后恢复的审批卡点"批准"时无消费者,永远不执行;③`resolve()` 非原子,并发 approve/reject 落账状态与实际执行可能相反。
- 修法:①SSE 主循环加周期心跳(`: heartbeat\n\n` 注释帧,15s),注意要在等待 `wait_resolution` 期间也能发出(可用 asyncio.wait 超时切片);②恢复审批卡时若无存活流,前端禁止批准并提示重新发送消息,或后端把决议持久化由下一条消息消费(选实现成本低的);③`resolve()` 改 Lua 脚本或 WATCH/CAS 原子化。
- 验证:测试模拟 BLPOP 期间连接保持(心跳帧存在);并发 approve+reject 只有一个生效且状态一致。

### Task 10(P1,后端,中):聊天流关键节点即时 commit

- 文件:`src/omichub/api/v1/chat.py:119-163`、`src/omichub/application/services/chat_service.py`(:1789-1807 全程只 flush;:5644-5648 handoff 事件)、`studio_context_service.py:391`
- 问题:整轮单事务,断流全回滚:用户消息消失、handoff 审计丢失、artifact 已复制文件成孤儿。
- 修法:用户消息落库、handoff 审计事件、artifact 报告行改用独立 session 即时 commit(与请求事务解耦);`register_artifact_report` 的文件复制要么延迟到 commit 后,要么接受孤儿文件但加清理。不要试图把整条流拆成小事务,只保关键锚点。
- 验证:测试模拟流中途取消:用户消息仍在库,AI 部分内容可缺失(接受),无孤儿报告行指向不存在的消息。

### Task 11(P1,后端,小):case watch 加固

- 文件:`src/omichub/application/services/agentteams_case_watch_service.py:49-55`、`src/omichub/infrastructure/celery_app/tasks/agentteams.py:27-35`、`celery_app/celery.py:79,124-126`
- 问题:全表扫描(不用 JSONB 过滤)、beat 重叠重复通知、异常全吞无告警、跑在 analysis 队列易被饿死。
- 修法:查询加 JSONB 存在性过滤(`sandbox_meta.has_key('agentteams_case_ids')`);beat 任务加 Redis 分布式锁防重叠;连续失败计数接现有告警/日志体系(至少 ERROR 级 + 指标);队列迁移视部署成本决定(可只做前三项)。
- 验证:单测断言过滤条件生效、锁竞争时第二个实例直接跳过。

### Task 12(P2,后端,中):LLM 公共层加重试

- 文件:`src/omichub/infrastructure/ai_provider/litellm_provider.py:90-137`
- 修法:kwargs 加 `num_retries=2`,仅对 `RateLimitError`/`APIConnectionError`/`Timeout` 重试(litellm 原生支持,确认版本行为);与 Task 2 的 openai_compatible 重试语义保持一致。
- 验证:单测 mock 一次 429 后成功,断言最终成功且重试次数正确。

### Task 13(P2,前端,中):流式连接治理

- 文件:`frontend/src/stores/agentHub.ts:973-974`、`frontend/src/views/AgentTeamsCaseView.vue:235,281,294`、`frontend/src/components/studio/StudioCodeCard.vue:162,310-313`
- 内容:①`selectSession` 仅在 `session.multi_agent` 或存在 AgentTeams case 时才启动两条 SSE,离开 AI 区统一 stop;②CaseView 重连改指数退避(1s→30s)+ 失败 N 次后退回纯轮询,SSE 健康时暂停 20s 轮询;③`StudioCodeCard` `onUnmounted` 调 `abort()`。
- 验证:`vue-tsc` 通过;组件测试或手动验证卸载后无悬挂连接(浏览器 devtools Network)。

### Task 14(P2,后端,大,需设计确认后再动手):`sandbox_meta` 拆分与会话并发锁

- 背景:高频键(`matrix_sync_cursor`、`overdrive_runs`)寄居 JSONB,三路径 lost update(报告 04-H2);同会话无流式并发锁(报告 01-C2)。
- 修法方向(动手前先输出一页设计说明给用户确认):`matrix_room_id`/`matrix_sync_cursor` 补 alembic 迁移成独立列(设计 §6.4 自认欠账);Redis 每会话流式锁,`/chat/stream` 冲突返回 409。
- 验证:并发测试:两个流式请求同会话,其一 409;meta 并发写不丢更新。

### 暂缓项(不要主动做,除非用户明确要求)

- WS Copilot 旧链路(`ai.py`)收敛、前端四套流式实现统一、Studio 工作区磁盘清理任务、路由多轮上下文/粘性(报告 02-H1)、Refresh Token 轮换、API Key 密钥轮换。这些涉及产品决策或较大重构,先在报告层面确认方案。

## 3. 环境速查

- 后端虚拟环境:`.venv/`,测试:`.venv/bin/pytest tests/ -k <kw> -x`
- 数据库迁移:`alembic/versions/` 下新增文件,参考最近迁移的 `revision/down_revision` 链
- 前端:`frontend/`,`npm run build` 可验证编译;类型检查看 `package.json` scripts
- Celery 配置:`src/omichub/infrastructure/celery_app/celery.py`(beat schedule、队列路由)
- Studio 沙盒 agent:`deploy/studio/sandbox_agent.py`(容器内进程,改动需注意镜像重建流程,见 `deploy/runtime-images/`)
- 设计文档:`ARCHITECTURE_DESIN/agentteams.md` 等(契约章节 §4.3/§4.4 与实现已有偏差,修改 chunk 类型时同步更新文档)

## 4. 完成定义

- 每个 Task:代码改完 + 验证通过 + 一段小结。
- 全部完成后:汇总表(Task / 状态 / 改动文件 / 验证方式),并把 `docs/26.8.7/README.md` 的优先级总览更新为修复状态。
