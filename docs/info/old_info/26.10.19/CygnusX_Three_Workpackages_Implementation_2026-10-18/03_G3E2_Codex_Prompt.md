# 03-Prompt｜直接交给 Codex：G3-E2 Trusted HTTP Execution

---

你是 CygnusX BioOps 的**Linux 安全隔离 / 网络强制 / 受信执行控制平面 / Python-Celery 集成工程师**。本轮执行 **G3-E2 · Trusted HTTP Execution**。先阅读 `03_G3E2_Implementation.md`、`00_Overall_Roadmap.md`、最新审计与当前 `trusted_execution.py` / `supervisor_client.py` / 既有 `tests/integration/test_download_trusted_http_boundary.py`。你的任务是**真正实现**非生产环境可验证的最小可信 HTTP 执行，不是继续编写纯 Protocol/DTO 或用 `skip` 宣告通过。

## 当前审计起点，必须逐文件核查而不是盲信

- 已存在 `TrustedExecutionAdapter` Protocol、mTLS Supervisor **客户端**（start/observe/renew/stop/evidence）、签名 HTTP publication receipt + nonce 验证。
- 初始审计时**没有**可确认的独立 Supervisor 服务端；当前源码已具备默认拒绝 Supervisor 骨架、启动前 seam 与 Worker 生命周期 seam，但仍没有 Linux scope/网络/磁盘强制、不可绕过 RX、可实际运行的 trusted_http_driver。真实 HTTP 九项为 0/9，默认 skip。
- P0-A 的 Admission Model/Repository/迁移处于 dirty 开发，未完成真实人工审批/同 Task/budget 运行验证；切勿绕过它。

## 绝对禁止

1. 不允许修改 `DOWNLOAD_TRANSPORT_RUNTIME_ACCEPTED=False`、`WRITE_RUNTIME_ACCEPTED=False`、Agent download/analysis write 默认门禁以造出成功；不允许真实用户下载准入。
2. 不允许用 `Content-Length`、成品文件字节数、代理环境变量、`ulimit -f`、父进程 `terminate()`、Docker CPU/IO 限速假装实现 OS 硬强制。
3. 不允许把 `docker.sock`/`NET_ADMIN`/root/PG/Redis/Broker/云凭据给普通 Worker 或下载 CLI；不可 `chmod 666 docker.sock`。
4. 不允许直接在生产 Worker、云出口或共享存储做故障注入；不能从现有共享 worker 继承环境变量直接启动 CLI。
5. 不允许用普通 Mock/内存驱动替换真实 HTTP 九场景；**没有被授权的 Linux/netns/cgroup/FS quota/自有 HTTP 端点就停止危险执行，标注 BLOCKED**。
6. 只认证固定 HTTP 来源范围、固定版本工具与策略；HTTPS/FTP/SRA/ENA/OSS/TOS/OBS 均保持 BLOCKED。不能让 caller 自报 `certified=true`。
7. 不能创建第二套业务 Task/approval/queue/FileRegistry；不能自动提交或推送。

## E2-0：可执行环境与代码保护

1. 只读记录主仓/子仓 HEAD、所有 dirty、可信下载核心文件 SHA、工具镜像 digest、用户/文件系统/内核版本。避免覆盖 P0-A Codex 的 admission 与迁移文件；约定共享 Worker 接线的文件所有权。
2. 对授权非生产 Linux 出具 `Environment ID`、批准的 OS 权限、测试 CPU/内存/网 RX/磁盘/inode/时长上限、清理负责人、自有 allow/deny/redirect HTTP 服务地址、被允许的内核与 quota 驱动版本。
3. 可只读 inspect：cgroup v2 controllers/subtree、namespace、network policy/backend、filesystem quota、UID、caps、rootless/no_new_privs、worker Docker Socket/FD/env、出站路由。**readable/installed 不等于 enforced**。若缺一项不可替代的强设施则输出 Blocker 和最小条件，不尝试高风险绕过。

## E2-1：独立 Supervisor Server 与 mTLS Admission

- 在受信运维侧新增**独立 OS Supervisor 服务端**，复用现有客户端的 DTO、证书身份验证和签名/nonce契约。使用固定配置、只允许审核过的 HTTP 工具 digest/argv/env/network destination；Worker 只能提交原 Task + Admission 等不可自报的引用。
- 服务端通过受信 P0-A 持久状态 revalidate：owner/project、人工 actor/ingestion/approval、Task 状态、attempt/epoch、caller、protocol、environment、tool/policy digest、expiry、预算余额、撤销状态；缺 P0-A 的引用即拒绝 start，**不得用测试假 Approval 代替正向验收**。
- start 必须幂等地建立唯一 `execution_id/scope_id`；同 Task/epoch 不能双 scope；旧 epoch 不得 renew；所有服务端动作有可观测审计，但不输出凭据。

## E2-2：启动前 Task 专属 OS 边界

- 实现并在 exec **之前**校验：专属 cgroup v2、network namespace/路由封闭、只读 rootfs/工具、受限 user/mount namespace、task quota writable domain、FD/env allowlist、非 root/cap_drop/NoNewPrivs。
- `HOME/TMP/XDG_CACHE/下载路径/checkpoint` 全归 Task 配额域，禁止使用共享 `cwd` 冒充隔离，禁止 Docker socket/cloud credentials 出现在子进程。
- 默认无互联网直连；CLI 任意更改 proxy/DNS/IPv6/argv 不得绕过强制出口；不得在没有受信边界时 fallback 到老 `BinaryExecutor`。

## E2-3：唯一受控出口与同步 RX 硬预算

- 明确你采用的强制实现（例如 OS ingress + 单一受限出口/原子 credit），并写出其**可证明的网络 RX 计量语义**：Task 边界，所有连接共享、包含响应头/失败/Ranges/重试；字节在放行给 Task 前原子扣减。
- 真实核验 IPv4/IPv6、DNS rebind、redirect 逐跳、未授权直连、网络 namespace 出口以及 tcp chunk/range 并发。只有经测试批准的 allow URL/端口/IP 可达；拒绝未授权受控 endpoint。
- 如果实际 enforcement 存在缓冲/分片超额，不能用“数值差不多”标 PASS；必须停下分析根因，修复或将该测试明确 FAIL/BLOCKED。不要用 CLI 日志估算硬 RX。
- 网络运行计数与 P0-A 持久预算对账；丢失计数时必须 UNKNOWN/fail closed。

## E2-4：文件 quota、生命周期、发布回执

- 使用真实支持 project quota 或等效块+inode双硬限的受管文件系统，为每 Task 包住**所有**可写路径；通过块/inode 真实耗尽证明限制有效，其他 Task 不受影响。不能只限制 output 文件夹，而让 /tmp/cache 越界。
- 实现独立 watchdog lease：超时、取消、Worker SIGKILL、Supervisor 重启后默认断出口、清理所有后代（不限父PID）、确认 scope empty 并生成受信回执；停止与 revoke 幂等且有 epoch fencing。
- 复用原 `_verify_http_download_publication_receipt` 的签名/nonce/Task/scope/attempt/epoch 绑定；没有真实 OS 观测回执不允许 FileRegistry SUCCESS。未知或部分文件存 `RECONCILIATION_REQUIRED`，保留文件待对账。
- 在**仅隔离测试队列**注册原 `run_download` / `reconcile_downloads`，Worker 使用正确 `SERVICE_NAME=worker`；不开放报告 Worker 的生产任务路由；Task/原 Celery/原 FileRegistry 唯一权威。

## E2-5：九项真实 HTTP 安全认证

严格调用仓库已有 `tests/integration/test_download_trusted_http_boundary.py` 九场景，提供受审核的**真实** `trusted_http_driver`。测试全部使用自有授权 HTTP 小流量端点，不能用 Mock、假文件复制、换标题绕过现有 skip。必测：

1. `small_file` —— HTTP 真下载、RX/SHA/FileRecord/Task 关联；
2. `unauthorized_address` —— 未授权受控 IP/端口与 IPv4/IPv6 直连拒绝；
3. `unauthorized_redirect` —— 302 跳 deny endpoint 不产生越权请求；
4. `unknown_length` —— Chunked/无Content-Length真实计量；
5. `network_over_budget` —— 并发/重试/Range 仍严格不超过 RX hard limit；
6. `disk_quota_exhausted` —— blocks/inodes 强制拒绝、其他 Task 安全；
7. `cancel` —— 经原用户取消，egress off、scope empty、不可复活；
8. `worker_sigkill` —— 独立租约回收后代，真实退出时间线；
9. `partial_reconciliation` —— 失败/部分文件原 Registry/SHA/状态不伪造科学 READY。

每例记录实际 Environment/host kernel/cgroup/quota/backend、tool/image digest、批准的 HTTP endpoint、Task/owner/project/admission/attempt/epoch/scope、mTLS 身份、计量点、网络 admitted/dropped、块/inode、CPU/Mem、进程树、停止回执签名和 nonce、FileRegistry DB 行/独立 SHA、原始测试命令/exit/log。在所有真实环境都具备而且九项无 skip 前，G3 结论只能 `BLOCKED/NOT_TESTED/PARTIAL`。

## E2-6：安全与发布结论

- 单独运行 G3 单测、兼容性测试以及 S4/Admission/Gateway 的最小回归，指出 PASS_ISOLATED 与 PASS_RUNTIME 范围，严禁不同套件结果相加。
- 对“运行认证”明确限定 `{environment, protocol=http, source_allowlist, tool_digest, policy_digest, caller, expiry}`；本轮不启动任何生产下载和 Agent 通道。全局 gate 保持 false。
- 输出 `docs/implementation/cygnusx-g3-e2-trusted-http-acceptance.md`、`evidence/g3-e2-runtime/`，分文件列源码/部署配置、真实 OS 截图/命令/数据面证据、九项逐ID、阻断、回滚、回退/独立 lease、与 P0-A 原 Task 的实证关联。

**如果当前主机不具备所需权限或可信核验/预算未接线，允许产出实现代码和隔离测试，但必须停止真实 HTTP 运行与认证；不能为了“交差”放宽门禁或人为制造绿色。** 任务结束后停止，不自动启用 S6、不提交推送。
