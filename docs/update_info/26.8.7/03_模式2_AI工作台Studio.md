# 03 模式 2:AI 工作台(Studio)

运行方式:每会话一个 Docker 容器(`studio-{session_id[:8]}`),Web 经 bind-mount 工作区里的 Unix Socket 直连容器内 `deploy/studio/sandbox_agent.py` 执行代码/文件/MCP,全程同步;仅 `timeout>600s` 的 `sandbox_execute` 转 Celery(`tasks/studio.py:run_studio_sandbox`)。状态机制:聊天/重跑=SSE(无心跳无断线续传);终端=WS(前端有重连);审批=Redis BLPOP(300s TTL);沙盒回收=Redis ZSET + beat 每 5 分钟。

## 高严重度

### H1. 客户端断连后沙盒内子进程不被杀死 —— 孤儿执行

- 位置:`deploy/studio/sandbox_agent.py:216-344`(`_stream_exec`)
- 问题:`killpg` 只在超时分支(303-313)执行。SSE 客户端断开(用户点"停止"、关页面)时,`finally`(316-325)只关溢出日志和删脚本,**不杀子进程**。前端 `useStudioRunStream.abort()` 和 `stopStreaming()` 只是中断 HTTP,服务端无取消语义。用户看到"已停止",代码却在沙盒里继续跑(写文件、烧 CPU)直到容器被空闲回收(最坏 30min+);`timeout` 检查也随生成器死亡而失效,进程可无限期运行。
- 修复:`finally` 中增加 `if proc.returncode is None: os.killpg(proc.pid, 9)`(配合短 wait);或 agent 侧检测响应流关闭即终止进程组。

### H2. Studio 工作区磁盘永不清理,与注释承诺不符 —— 磁盘泄漏

- 位置:`chat_service.py:1681-1689`(`delete_session` 只标记 deleted 不删目录);`celery_app/celery.py:107-110`(beat 只有容器回收,无工作区清理);`studio_context_service.py:9` 与 `:350` 注释声称"工作区 7 天后会被清理"——**该清理逻辑不存在**。
- 问题:每个 Studio 会话的工作区(含 output 产物、.logs、软链)永久累积,磁盘只增不减;注释还在误导后续设计者。
- 修复:加 beat 任务:对已删除/超 N 天未活跃会话,先 `studio_sandbox_manager.stop()` 再删工作区目录;或删除会话时同步清理。

### H3. 审批等待期间 SSE 完全空闲 + 恢复的审批卡"批准了也不会执行"

- 位置:`chat_service.py:5452-5454`;`studio_approval_service.py:109-132`(`wait_resolution`);`agentHub.ts:1331-1352`
- 问题:①聊天流在 `await wait_resolution()`(BLPOP 300s)期间 SSE 零字节无心跳,nginx 空闲超时(常见 60s)切断连接,消费决议的 BLPOP 随之消失。②前端刷新后从 Redis 重建的审批卡仍可点"批准",`resolve()` 把决议 RPUSH 进结果 list,但**此时没有任何 BLPOP 消费者**——工具永远不执行,前端永远停在 awaiting_approval。supervised 模式是 Studio 的 HITL 安全闸,这两个路径都让"批准"变成哑操作且无错误提示。
- 修复:SSE 加周期性心跳(15s 注释行);恢复审批卡时若会话无存活流,禁止批准并提示"请重新发送消息触发执行",或把批准决议持久化让下一条消息消费。

### H4. 聊天整轮单事务:断流即整轮回滚,与前端"已停止"展示矛盾

见 `01_跨模式共性问题.md` C1。Studio 侧叠加:`register_artifact_report`(`studio_context_service.py:391`)在工具执行时已把产物复制到报告中心目录,DB 回滚后留下无主孤儿文件;残留的 Redis 审批记录(H3)也因消息回滚失去锚点。

## 中严重度

### M1. `ensure_running` 无并发锁,预热与首次执行竞态导致启动失败

- 位置:`src/omichub/infrastructure/studio/manager.py:343-444`;触发点 `studio.py:148-170`(预热)
- 问题:创建会话即后台预热容器;用户立刻发消息触发懒启动,两个协程同时 `containers.get` 都 NotFound,都 `containers.run(name=...)`,后一个拿 docker 409 Conflict。`recycle_idle`(606-622)先 `_is_busy` 后 `stop`,与进行中的 `ensure_running` 存在 TOCTOU,新请求的容器可能被回收任务杀掉。
- 修复:每 session_id 一把 `asyncio.Lock`(进程内)+ Redis 锁(跨进程);回收前二次确认活跃态。

### M2. Docker 可用性一次性缓存,Docker 恢复后 Studio 永久不可用

- 位置:`manager.py:104-114` — `is_available()` 首次失败后 `_available=False` 永不再试,Docker daemon 重启/恢复后必须重启 Web 进程。
- 修复:缓存加 TTL(如 30s)或失败时不缓存。

### M3. 容器名只用 session_id 前 8 位,跨会话/跨用户前缀碰撞

- 位置:`manager.py:162-164`;`chat_service.py:1358`(session_id=uuid4)
- 问题:uuid4 前 8 个 hex 字符仅 32-bit 空间,约 7~8 万会话即有 50% 碰撞概率。碰撞时 `containers.get` 会拿到**另一个会话(可能是别的用户)的容器**:none 网络模式下能通过 `_validate_container_network`,随后 `_wait_ready` 在自己工作区等不到 UDS 而超时,报误导性错误。
- 修复:像 `session_network_name` 一样用 `sha256(session_id)[:12]` 或更长前缀命名容器。

### M4. 文件读取整文件入内存再分页;edit 会损坏非 UTF-8 文件

- 位置:`deploy/studio/sandbox_agent.py:501-521`(`read_file`);`src/omichub/infrastructure/studio/workspace.py:63-87`(`disk_read_file`);`sandbox_agent.py:613-647`(`edit_file`)
- 问题:两处 read 都是 `read_text(...).splitlines()` 后切片——GB 级文本(生信场景常见)直接把进程打到 OOM。`edit_file` 用 `errors="replace"` 读入再写回,任何非 UTF-8 字节被 U+FFFD 替换后**静默损坏文件**,且 content/old_string 无大小上限。
- 修复:分页改流式逐行读(`itertools.islice`);读前 stat 限大小(如 100MB 拒绝);edit 检测非 UTF-8 直接报错。

### M5. Celery 长任务运行期无失败恢复,worker 崩溃即僵尸

- 位置:`src/omichub/infrastructure/celery_app/tasks/studio.py:22-44`
- 问题:`run_studio_sandbox` 无 `acks_late`、无 retry、无对账任务;投递失败有补偿(`studio_task_service.py:77-89`)但**运行期** worker 崩溃/重启后,任务行永远停在 RUNNING,沙盒内执行变孤儿(叠加 H1)。任务也没有用户可见的取消入口。
- 修复:`acks_late=True` + `reject_on_worker_lost`,或加 beat 对账(RUNNING 超时标记 FAILED);提供取消 API 并传播到沙盒 exec。

### M6. mkdir/rename/delete 端点缺少异常收敛,agent 4xx 直接变 500

- 位置:`src/omichub/api/v1/studio.py:730-745` — 三个端点直接 `return await studio_sandbox_manager.xxx(...)`,不像 save/edit(706-722、764-782)那样捕获 `StudioSandboxUnavailableError`/`httpx.HTTPStatusError`。
- 修复:套用与 `save_workspace_file` 相同的 try/except 包装。

### M7. 终端忙碌租约上限 62 分钟,长命令+无键盘输入会被回收误杀

- 位置:`studio.py:909`(`_set_busy(session_id, 3600)`);`manager.py:289-301`(租约封顶 min(t,3600)+120);`studio.py:927-940`
- 问题:`_touch` 只在浏览器→agent 方向(keystroke)调用,agent→浏览器输出不续约。用户跑 1 小时以上命令且不敲键盘:30min 空闲 TTL 过后、62min 租约到期,`recycle_idle` 把容器连同正在跑的命令一起回收。
- 修复:`agent_to_browser` 输出时也 `_touch`;或终端 WS 周期性续约租约。

### M8. 审批消费非原子,并发 approve/reject 状态与执行可能相反

- 位置:`studio_approval_service.py:134-169`;`studio.py:538-576`
- 问题:`resolve()` 是 get→判断 pending→setex→rpush 的非原子序列,端点层 pending 检查 TOCTOU 同理。并发 approve+reject:两者都通过检查都 RPUSH 决议,BLPOP 只消费第一个(决定工具是否执行),而记录状态被第二个覆盖——落账状态与实际执行可能相反。
- 修复:用 Lua 脚本或 Redis WATCH/CAS 把"检查 pending + 置状态 + 推决议"做成原子操作。

### M9. 同一会话无流式并发锁

见共性问题 C2。Studio 叠加:两轮 agent 循环并发在同一沙盒里写文件/执行。

## 低严重度

- **L1** `celery_app/tasks/studio.py:195-199` `_append_bounded`:每次 append 都 `sum(len(...))` 全量求和,大量小 chunk 时 O(n²)。维护 running total 即可。
- **L2** `studio.py:385-397` `promote_session_to_studio`:jsonb_set 直写后未 `db.refresh`,返回 DTO 的 `sandbox_meta` 是过期内存值。
- **L3** `studio_tools.py:968-994` `stream_studio_tool`:生成器被关闭时不取消内部 task;`_on_output` 在队列满(32)时阻塞 put,客户端死亡后 task 可悬挂至租约到期(最长 62min)。
- **L4** `studio.py:876` + `StudioTerminal.vue:26-29`:终端 WS 的 access token 走 query string,会进入 nginx access log。建议一次性 ticket 或 Sec-WebSocket-Protocol。
- **L5** `sandbox_agent.py:54-60`(UDS chmod 0666)+ `manager.py:152-160`(chown 失败退化 chmod 0777):非 root 部署时宿主任意本地用户可直连任意会话沙盒执行代码。建议 socket 收 0660 + 专组,或文档标注单机可信前提。
- **L6** `sandbox_agent.py:585、600`:rename/delete 的 input 保护用 `target.parts[len(WORKSPACE_ROOT.parts):...]` 切片,`WORKSPACE_ROOT` 含软链时保护会失效;建议改用 `relative_to(realpath(root)).parts[0] == 'input'`。
- **L7** `manager.py:869-888` `_agent_call`:读超时 `read=None`,agent 死锁时 Web 协程永久悬挂(仅靠租约过期+回收兜底);建议加兜底读超时(如 10min)。
- **L8** `studio_task_service.py:44-45`:任务参数持久化 `code_preview` 前 500 字符,代码里若硬编码密钥会落进任务中心 DB。可考虑脱敏或不存。

## 值得肯定的设计(勿在修复中破坏)

- 路径防护(`paths.py` / `sandbox_agent.py` 双侧同源 realpath + 词法双重校验)实现严谨,平台挂载翻译有二级软链外跳校验;多租户按 `users/{user_id}` 挂载是正确红线。
- `sandbox_meta` 并发写用 jsonb_set 原子合并、审批存 Redis 跨进程、分享 token 哈希落库、分享产物有 output 目录限定。
