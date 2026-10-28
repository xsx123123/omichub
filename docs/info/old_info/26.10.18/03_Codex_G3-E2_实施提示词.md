# 可直接交给 Codex：G3-E2 TrustedExecutionAdapter实体实现

请在CygnusX仓库实现可信下载执行设施，并完成可运行的受控HTTP认证准备及授权范围内的真实测试。阅读《01_CygnusX_实施优化方案.md》，先核对原S3/G3契约，所有新增类型和路径以仓库为准。目标是把Protocol-only变成实体后端，不能只补Mock、注释或配置开关。

## 不可突破的边界

- 当前依据R2报告，G3-01..09全部BLOCKED；本提示词不是认证或宿主授权。不得动生产资源。
- DOWNLOAD_TRANSPORT_RUNTIME_ACCEPTED、WRITE_RUNTIME_ACCEPTED、agent_*_write_enabled保持冻结。测试通过独立、受限、非生产Adapter认证入口调用实际设施，不能monkeypatch生产门禁或给Agent执行能力。
- 仅自有受控HTTP源和小文件。HTTPS/FTP/SRA/EBI/OSS/TOS/OBS等继续不受认证。
- Worker/模型/下载进程自报计量与停止JSON都不是可信证明。文件大小、Content-Length、轮询du、超时后kill、普通Docker隔离均不能替代硬边界。
- 特权宿主、挂载、配额、网络规则变更须在已有明确授权范围内；不清楚时先完成可审查实现与精确操作清单，再仅对缺授权动作请求确认。

## 1. 先完成可审查设计和预检

读取TrustedExecutionAdapter、现有trusted driver/fixture、DownloadService/TaskService/FileRegistry、原G3九项和S6规则。输出协议逐方法映射、信任模型、威胁边界、部署拓扑、所需宿主能力及逐项验收映射。

冻结RX定义：既有S3要求是什么？建议计量点是否满足？区分任务边界admitted RX和宿主物理/计费observed RX。若要求物理入站绝不超B，本机drop不能满足，必须保持相应项BLOCKED，不偷换成应用read预算。

预检Linux版本、cgroup v2/kill、namespace、网络hook字节语义与原子能力、quota enforcement和block/inode限制。任一硬前置缺失拒绝start；可完成代码和隔离测试，但不能声称PASS_RUNTIME。

## 2. 实现独立Supervisor及Adapter

复用Adapter契约，将特权执行从Worker剥离。实现prepare/start/status/lease/stop/evidence的等效操作，认证调用方并限制参数。执行身份绑定task/attempt/execution/epoch/policy/environment；幂等与fencing阻止旧Worker重启、续租或finalize。

先建所有边界再启动：受限cgroup、namespace、非特权UID、只读rootfs、受限capabilities/syscalls、独立工作目录及配额、默认拒绝网络。无docker.sock或宿主控制入口。

Supervisor独立处理租约过期、Worker/API崩溃、取消、预算触顶。Supervisor重启默认隔离并终止未知旧执行体，未证明前不得恢复下载。使用单调时钟处理期限，持久化epoch及消耗状态，避免重启重置预算。

## 3. 实现唯一出口和RX同步硬限制

首版可以拒绝重定向、Range、重试、并发、压缩，但必须在策略与运行中明确拒绝。仅允许受控HTTP目标IP/端口，禁其他scheme/CONNECT/upgrade/proxy env。DNS如需要由可信层解析验证并固定连接，防重绑定；IPv4/IPv6、已有连接和旁路均覆盖。私网受控源只能精确例外。

在可信任务入口对全部连接/CPU使用同一原子预算：compare-and-reserve packet bytes，超额整包拒绝并锁定停止，不允许先放行再统计。明确响应头、失败响应、TCP重传、分片/offload和控制流量口径。记录admitted/observed/dropped而不是只记录payload。

证明不存在绕过该入口的网络通路。评估内核hook与共享原子状态后再选实现，不能只挂一个计数器或使用不经证明的非原子每CPU总和。任何计量设施失效、规则丢失或状态不确定都失败关闭。

## 4. 实现文件系统硬quota

在专用测试文件系统验证project quota或等效内核机制，配置block/inode hard limit和继承。覆盖output/HOME/TMP/cache/checkpoint/子进程；其余挂载只读或分别受限。必要tmpfs和Supervisor日志单列硬限并纳入总资源预算。

测试写满、海量空文件、稀疏/预分配、unlink后仍打开、symlink/hardlink、rename跨边界及子进程。证据必须包含内核拒写与quota查询，不能用du阈值冒充。保留共享文件系统总容量的并发预留和回收机制。

## 5. 实现停止回执与可信资产发布

先撤销数据通路及既有连接，再TERM/有限等待/KILL整个cgroup，确认populated=0和网络撤销，两者分别证明。超时/缺证据进入UNKNOWN或RECONCILIATION_REQUIRED，不写success、不发布资产。

receipt绑定执行身份、epoch、policy/binary hash、Supervisor身份、nonce、停止原因/时间、进程检查、网络撤销、RX口径与计数、quota配置与最终状态、清理状态、产物manifest hash；通过认证通道或签名防伪、防重放。验证旧epoch、伪造与跨任务receipt被拒。

复用既有Task/DownloadService/FileRegistry；受信完成证明、终态guard、文件校验全部通过才发布不可变产物。取消/失败后晚到success不能复活；临时目录释放前完成安全转移，避免校验后修改。

## 6. 运行与证据

先isolated/单元验证接口，再在授权Linux环境真实运行：正常小文件、目标拒绝、预算边界与并发超额、错误/慢响应、quota填满、取消、租约失效、Worker崩溃、Supervisor重启、计量失败、伪造receipt与清理失败。

逐项映射原G3-01..09并保留全部断言；新增E2测试ID不能替代原含义。独立抓包/源日志/cgroup/quota快照交叉验证Supervisor，解释offload与观测位置。保留不支持功能拒绝证据。

## 7. 交付

- 实体Adapter、Supervisor、网络执行层、quota配置、受控HTTP源及测试驱动；受限部署和回滚说明。
- `docs/implementation/cygnusx-g3-e2-trusted-http-runtime.md`，包含实际已实现/已运行/未运行/阻断，不是预填PASS。
- `evidence/<run_id>/`的原始命令、退出码、内核能力、计数、quota/cgroup、源日志、stop receipts、DB差异、hash清单；不得泄漏凭据。
- 范围化认证候选记录：环境/内核/镜像/策略/协议/caller/期限/撤销条件及证据。未完成原九项不能认证；HTTP通过不认证其他协议。
- 所有生产及Agent门禁保持关闭。是否进入S6由独立准入检查决定；本任务禁止自动开放。

完成授权范围内所有工作，最后如实报告。没有Linux或宿主能力时交付可审查代码、精确预检/部署操作和阻断表，不假称运行完成，也不要只停在通用调查。
