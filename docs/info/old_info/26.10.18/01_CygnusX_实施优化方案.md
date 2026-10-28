# CygnusX：IAT-R3 与 G3-E2 详细实施优化方案

版本：2026-10-18 · 性质：实施设计与未来验收要求，非运行验收报告。

## 1. 目标与材料边界

本轮应收敛既有 S3/S4/S5 工作，不重建 Agent 框架、Gateway、下载业务调度、审批系统或资产模型。两条并行工作流分别补齐 Agent 产品链和可信执行设施，S4 可靠性作为共同汇合条件；最终通过 S6 受控下载接入和 S7 科研交付证明整体目标。

本方案实际读取了以下材料：

- `cygnusx-iat-r2-runtime-evidence-closure.md` 全文，运行 ID `cygnusx-iat-r2-20261017-zj`，报告基线 HEAD `d9c92cf6ee1c`。
- 首轮 `acceptance-report.md`，作为前后状态比较材料。
- “平台下载优化”可访问历史对话；其中 S3/S4/S5 说明仅作历史背景。

未取得仓库当前源码、R2 原始 harness/日志、更新后矩阵、最初 S3/S4/S5 完整设计文件。本次没有运行平台或测试。报告中“真实运行”的措辞是报告作者的结论，不等于本次独立复核。所有下文新增设计均为建议，实际符号、表名、路径与 API 以目标仓库为准。

## 2. 当前事实、缺口与需要纠偏的结论

| 项目 | R2 报告陈述 | 本方案可采信范围 | 下一步 |
|---|---|---|---|
| 汇总 | 42 runtime、3 E2E、3 isolated、9 blocked、21 not tested，共78 | 算术成立，逐项统计未独立复核 | 从更新矩阵与证据自动生成汇总 |
| Celery | 专用队列真实发布、消费、重复消息、恢复扫描 | 有报告引用；任务 failed/queued，未真实下载 | 补时序故障，不把 Celery succeeded 当业务成功 |
| Node | Node 24.11 调用 describe capabilities，经 HTTP/Gateway/PG/Redis | 证明适配器能力目录链，不证明完整聊天工具轮次 | 验证模型决定→工具→最终响应 |
| Legacy/LangGraph | agent_templates 空、Provider key 空 | Runtime 层 BLOCKED；矩阵 AG-02/03 为 NOT_TESTED，二者应保留各自语义 | 建合法模板和隔离确定性 Provider |
| React 科研 E2E | 前端未构建、无资产样本 | NOT_TESTED；Vue 登录页不能替代 | 部署既有 React/Vue/Node 拓扑 |
| IAT-01 | 三处 code 修复；4/4、相关69 tests、ruff通过 | 报告陈述的回归结果 | 在当前基线复跑必要回归 |
| PG-11 | raw SQL 可把终态写成 success | 服务层有局部 guard，数据库未强制整个状态机 | 审计写入路径、角色、晚到回写 |
| G3 | Protocol-only，缺 Supervisor/RX/quota/停止证明 | G3-01..09 继续 BLOCKED | 实体实现和独立认证 |
| S6 | 五项条件未全部满足 | NOT_READY | 禁止因R3通过自动开放 |

必须专门核查四处报告歧义：

1. R2 §2 声称“23个”但表内含范围、重复引用与 isolated 项，不能手工数标签替代逐 ID 对账；保留 FR-08 的隔离证据性质。
2. §3 MQ-02 中 redis-py 死端口报错、Kombu publish 返回 ok，不能单凭这一结果认定生产 dispatch 已可靠感知发布失败。“pipeline fire-and-forget”解释需用实际 Kombu/redis 版本、连接时机与抓包复核；区分发布尝试、Broker 接收、Worker 收到、业务领取四个事实。
3. §5 Node 明确调用 describe capabilities，§6 却描述 dataset.discover 数据来源链已闭合。没有额外 discovery 调用日志和返回体时，后者标为待核实，不能算 DatasetCard E2E。
4. §9 “21个 NOT_TESTED”混合主用例与未覆盖子场景。原78项保持原ID；拆分子断言另建 child_id，不把新旧分母混加。

## 3. 双流计划与依赖

| 工作包 | 可立即完成 | 依赖 | 汇合产物 |
|---|---|---|---|
| A0 证据基线 | 清点源码、运行材料、矩阵 | 仓库及既有授权环境 | baseline、状态差异 |
| A1 Runtime | 合法模板、确定性Provider、Legacy/LangGraph轮次 | 真实API/PG/Redis | Runtime证据 |
| A2 科研E2E | 既有React/Vue/Node部署、资产fixture、Chromium | A1和既有UI契约 | 业务E2E证据 |
| B0 执行设计 | threat model、RX契约、能力预检 | Linux能力及授权范围 | 已冻结边界文档 |
| B1 实体实现 | Supervisor、隔离、出口、quota、receipt | B0 | 可测试Adapter后端 |
| B2 HTTP认证 | 受控源故障矩阵、独立观测 | B1全部就绪 | 范围化认证材料 |
| C S4收尾 | ACK/崩溃/冷却/公平性/写入保护 | 真实Broker/PG/Worker | 可靠性补测 |
| S6 接入准备 | 审批绑定、准入表、撤销、回滚代码 | A/B/C分别验收 | 默认拒绝的接入实现 |
| S6运行准入 | 同Task审批→执行→资产 | 独立准入审核且环境/协议/caller一致 | 受控HTTP运行证据 |
| S7科研验收 | DatasetVersion→FlowFrame→BioReport | S6及分析输入契约 | 可追溯科研交付 |

“并行”表示工程工作包独立推进，不要求创建额外调度系统。先冻结 Gateway 结果、Prepare/Approval 和 Adapter 边界，再分别实现。缺 Linux 能力时，B流可完成代码、设计和隔离测试，但 G3 仍 BLOCKED，不能用宿主 macOS/Docker 普通容器成绩替代 Linux 认证。

## 4. A流：IAT-R3 实施步骤

### A0 基线与环境

清点 Git HEAD、dirty diff hash、子仓版本、迁移、依赖锁、Compose网络和卷、API/Worker身份。复用 RI095 acceptance，确认它仍被授权且不是生产；旧授权不自动覆盖新增宿主内核/磁盘操作。保护用户已有变更。

从部署源码确认 Vue 平台、React Presentation、Node聊天服务、FastAPI 的实际端口、代理、身份与SSE路径；输出拓扑图和配置表。修复构建/代理问题，不重做页面。按锁文件安装依赖、固定运行时，禁止以安装失败为由升级整套依赖。保留 Chromium sandbox。

### A1 确定性 Provider 与真实 Runtime

在非生产配置中增加最小测试 Provider，复用现有 Provider 接口和装配路径；生产禁止启用。它只按固定脚本返回标准模型工具调用及后续最终回答，不直接调用 Gateway、写数据库或返回伪造工具结果。

Legacy 与 LangGraph 分别从产品真实 API/SSE 入口执行：用户上下文→合法 AgentTemplate→Provider 首轮 tool call→现有 MCPClient/ToolBridge/Fixed Callback→Gateway→业务服务→真实 PG/Redis→工具结果回灌→Provider 后续轮次→Runtime 最终事件。记录实际所选引擎，禁止两个入口实际都走同一后端却声称双引擎通过。

至少覆盖：能力查询、合法 dataset inspect、合法 Import Prepare、权限不足、重放、确认记录不匹配、工具超时和SSE错误终态。两引擎都要完成至少一条成功工具轮次和一条拒绝路径。记录输入脚本摘要、工具调用ID、参数hash、invocation ID、context、审计ID、Redis消费事实、SSE序列、最终响应及数据库差异。

确定性 Provider + 真实 Runtime 可以记为 `PASS_RUNTIME`，必须附 `provider_mode=deterministic`；不能称真实外部模型通过。外部 Provider 调用单设验收项，缺额度/端点授权为 BLOCKED或NOT_TESTED，不拖延已有确定性Runtime验收。

### A2 科研数据与审批边界

建立用户 A/B、项目 A1/A2/B1、活动与归档 session、GEO 固定元数据样本、DatasetVersion、FileRecord、来源证据和项目资产关联。使用真实合法样本时保存 accession、获取日期、来源URL和快照hash；纯合成样本明确标记 synthetic，不能冒充已下载真实GEO文件。可预置微小测试文件并登记实际hash，但必须标记 fixture、非网络下载所得。

Import Prepare 应持久化合法预案，记录 source/target/budget/expiry/owner 及仓库实际关联键，状态停在等待人工确认。断言准备前后没有新增下载 Task，没有排队/执行副作用。历史测试 Task 不要求清空，以本 run_id 和前后差异判定。

### A3 Chromium业务闭环

1. 从实际产品入口登录，验证 Vue 到 React 工作台的真实集成和身份传递。
2. 由真实 Node 运行轮次生成 GEO DatasetCard，展示来源、候选文件与置信提示；无外部元数据请求时标记固定快照来源。
3. inspect Existing Dataset，展示真实持久化 DatasetVersion/FileRecord 和项目归属。
4. 生成 Import Prepare，刷新/重连后仍显示同一预案；下载执行保持阻断，直接API绕过同样拒绝。
5. A1请求被刻意延迟后切到A2，释放旧响应，断言旧卡片/事件不能污染A2；顺序导航不算该场景通过。
6. 归档session、撤销权限后重试/重放，服务端拒绝；不能只检查按钮隐藏。
7. 中断真实SSE连接并恢复，验证去重、最终状态和持久化事实；刷新不等于SSE恢复。
8. 中英界面检查关键状态和错误语义一致。

保存截图、脱敏网络trace、SSE事件、console错误、API关联ID和PG查询；截图本身不足以证明后端副作用。直接HTTP harness可以作为负例辅助，不能替代业务浏览器操作。

## 5. B流：G3-E2 最小可信HTTP执行边界

### B0 范围与信任模型

第一轮只支持自有受控HTTP测试源、小文件、固定端口和显式允许的目标。HTTPS、FTP、SRA/EBI、OSS/TOS/OBS、任意公网URL均不在认证范围。最小版本可明确禁用重定向、Range、自动重试、压缩和并行下载；如果要支持，则必须覆盖对应认证场景。拒绝功能也须测试，不能用未覆盖冒充已支持。

信任：宿主内核、独立Supervisor、出口执行层、配额执行层、准入验证器。非信任：模型、前端、Worker、下载子进程和其自报计数。Supervisor应独立于Worker生命周期，Worker不持有修改网络/配额/认证的宿主权限。不向下载进程暴露docker.sock、宿主控制接口、云凭据或生产密钥。宿主root/内核被攻破不在本轮防护承诺内。

### B1 Adapter实体与生命周期

先读取现有 `TrustedExecutionAdapter` 协议，逐方法映射实体实现，避免新接口覆盖旧契约。可增加内部类型，以下名称仅为设计示意：

- ExecutionIdentity：task、attempt、不可复用execution_id、fencing_epoch、policy_hash、environment_id。
- ExecutionPolicy：目标集合、协议、RX/磁盘/inode预算、期限、镜像/二进制hash。
- Supervisor API：prepare/start/status/renew/stop/collect；认证通信、调用身份、幂等键和受限参数。
- 生命周期：PREPARED→RUNNING→STOPPING→STOPPED/COMPLETED；失败或缺证明进入UNKNOWN/RECONCILIATION_REQUIRED，不能伪装已安全停止。

prepare先建cgroup、namespace、quota和默认拒绝网络，再确认全部就绪才start。租约以Supervisor单调时钟和不可延期旧epoch为基础；Worker心跳消失、API崩溃、租约过期、预算触顶都触发独立停止。Supervisor重启先隔离未确认执行体，重建清单和检查内核状态后才能恢复；本轮可选择重启后全部终止，不承诺续传。

### B2 隔离与唯一出口

使用经预检支持的Linux cgroup v2、独立网络/挂载/PID等namespace、非特权UID、只读根文件系统、受限capabilities和系统调用。进程不能创建新网络出口或迁出cgroup。CPU/内存/pids限制与磁盘quota分别管理，不能互相替代。

默认无网络，仅受信出口层允许绑定到本 execution identity 的目的IP/端口；明确拦截IPv4/IPv6绕过、loopback、link-local、metadata、私网和Unix控制socket。受控实验源若位于私网，使用专门精确IP/端口例外，只限该隔离环境，不构成通用私网放行。

DNS由受信层解析并验证，连接固定已批准地址；处理全部解析结果，防DNS重绑定。最小版不需要DNS时只用冻结IP与Host映射。禁止继承HTTP_PROXY/ALL_PROXY等；任何重定向逐跳重新授权，最小版直接拒绝。URL凭据、非HTTP scheme、CONNECT、协议升级均拒绝。只做应用URL校验不足以证明无旁路。

### B3 RX硬预算：必须先冻结定义

**不能将用户态read累加、Content-Length、文件大小、速率限制或事后抓包当RX硬上限。**

建议定义：每 execution_id 在可信网络边界“准入到任务侧”的L3 RX包字节总和，覆盖HTTP响应头、错误响应、TCP重传、连接失败阶段流量，以及支持时的重试/Range/并发连接。明确L3头是否计入、分片/重组/GRO/GSO处理和计数位置。若既有S3要求不同口径，应遵循原契约并补足设计，不静默替换。

在唯一任务入口执行同步原子compare-and-reserve，所有CPU/连接共享同一预算；仅当 packet_length≤remaining 时扣减并放行，否则整包拒绝并锁定该执行体停止状态。drop/observed/admitted分别计数，控制流量的归属必须明确且不能成为不计费数据通道。固定计数键要防Task/attempt复用和重启归零；恢复必须继承已耗预算或结束旧执行体。

推荐评估宿主veth任务入口的内核执行层及可核验原子状态。具体eBPF/其他机制需通过目标内核能力、hook字节语义、并发与旁路测试后选择，不能仅因“使用eBPF”就认证。若单一可信代理实现同等边界，也必须证明其任务侧全部流量受控、唯一出口且无代理预读遗漏。

必须区分两项：`admitted_rx_bytes <= B`可以作为任务侧严格预算；超限后仍抵达宿主网卡的包已产生物理入站流量，丢弃并不能撤销，`observed_rx_bytes`可能大于B。若原G3要求宿主/上游实际入站或计费字节也绝不超过B，需上游受信执行设施约束并独立认证；仅本机丢包不满足，保持BLOCKED。文档必须保留“原契约是否允许该计量点”的待决项，禁止降级语义换通过。

### B4 文件系统块/inode硬配额

建议使用独立测试文件系统上的XFS project quota，或证明等效的内核配额机制。先验证mount选项、accounting和enforcement均开启，再分配不可冲突project ID，设置block和inode hard limit及目录继承，最后启动进程。cgroup `io.max`仅限吞吐，不能替代容量quota。

覆盖output、HOME、TMP/TMPDIR、cache、checkpoint、子进程工作目录及所有可写挂载。rootfs只读；独立tmpfs如必须存在，则明确容量/inode和内存上限，汇总总预算；日志由Supervisor限额管理，禁止无限stdout消耗宿主。测试hardlink/symlink、rename跨边界、稀疏文件、预分配、打开后unlink仍占块、海量空文件及子进程写盘。禁止逃到未配额卷。调用方不能关闭quota或修改project ID。

超额应观察内核拒写/创建和配额计数，而非定时du后杀进程。块分配粒度与metadata余量在准入时预留；不要声称文件payload精确等于磁盘物理消耗。共享文件系统总容量仍需独立保留空间与并发准入，避免每任务合规却整体磁盘耗尽。

### B5 停止回执与资产发布

停止顺序：冻结继续放行→撤销网络能力/现有流通路→TERM→有限等待→cgroup.kill或受支持等效机制→确认子树无存活进程→核查socket/路由/规则与quota状态→封存日志/产物。撤销必须覆盖已建立连接，不能只阻止新连接。超时或任一步无法证明则receipt标记不完整并隔离执行环境。

回执至少记录：execution/task/attempt/epoch、Supervisor身份、policy与二进制hash、起止/撤销时间、停止原因、退出/信号、cgroup identity及populated核验、网络规则版本及撤销结果、RX admitted/observed/drop与口径、quota hard limits/最终使用、清理结果、产物清单hash、证据引用。以受信服务认证通道或签名防伪，并绑定nonce、防重放和有效期；Worker的JSON不能充当权威证明。cgroup空不等于网络已撤销，必须分别观测。

只有受信完成证明、业务状态guard和文件校验全部通过后，现有FileRegistry/DownloadService才允许发布产物。失败、取消、过期和UNKNOWN保持隔离，不登记成可分析资产；若现有契约保留失败文件记录，必须显式不可消费。先复制/校验到受控不可变资产区再释放临时quota，避免校验后源文件变化。晚到success不能覆盖取消/失败。

## 6. G3测试与认证映射

下表为新增工作包编号，不冒充原 G3-01..09 含义；到仓库读取原九项逐条建立映射，任何原断言不能因合并测试而消失。

| 新ID | 场景 | 必须证明 |
|---|---|---|
| E2-01 | 预检缺cgroup/网络hook/quota | start前拒绝，无任务进程/出口残留 |
| E2-02 | 正常小HTTP文件 | 字节hash正确，真实计量/配额/receipt可关联 |
| E2-03 | 错误scheme/目标/重绑定/私网绕路/IPv6 | 不允许目标没有成功建立数据通路 |
| E2-04 | 无长度、伪长度、chunked、大响应头、错误响应、慢流 | 硬预算与deadline真实生效 |
| E2-05 | 多连接并发、边界包、重传、重试与Range | 原子总预算无超发；禁用功能确实被拒 |
| E2-06 | 填块、inode风暴、HOME/TMP/cache/子进程 | 所有可写面受硬限且不能逃逸 |
| E2-07 | cancel、lease过期、Worker崩溃、Supervisor重启 | 旧执行体无进程/网络能力；失败关闭 |
| E2-08 | 伪造/重放/旧epoch receipt、晚到finalize | 不能发布资产或复活终态 |
| E2-09 | 清理失败、计量设施失联、quota失效 | 拒绝新任务、隔离与对账，不假成功 |

每项保存受控源日志、网络边界计数、独立抓包、cgroup/进程与quota快照、Supervisor日志、任务/资产数据库差异。抓包用于交叉验证，不替代执行限制。比较计量时处理offload与抓包位置差异。认证仅覆盖实际测试的环境、内核、镜像、策略、协议和caller通道；代码完成、isolated通过、fixture去skip都不能直接得到PASS_RUNTIME。

## 7. S4可靠性收尾

| 项目 | 注入方式与断言 |
|---|---|
| PG-01幂等竞争 | 两API连接同intent同时提交，返回同Task或契约化冲突；不能泄漏原始IntegrityError；冲突参数必须拒绝 |
| PG-10 | 保存真实EXPLAIN计划、锁等待/事务时间线，合理样本量，避免空表计划代表生产 |
| PG-11 | 枚举所有生产写状态路径/角色；旧epoch finalize拒绝；raw SQL绕过如仍可行，写清信任边界；触发器需有实际需求才引入 |
| MQ-03丢ACK | Broker已接收但发布者未确认后重试，证明重复投递但单次业务领取；区分publisher确认与consumer ACK |
| MQ-05 API终止 | commit前、commit后publish前、publish后多个窗口杀API；证明无幽灵任务、queued可恢复 |
| MQ-06 Worker缺席 | 长时间无消费者，任务持久；恢复后唯一claim；超租约旧Worker不能finalize |
| MQ-07长故障 | Broker持续故障跨多轮Beat，attempt/cooldown受控、无热循环，恢复后公平推进 |
| REC-04/06/07 | 高低优先任务公平时间线、扫描事务失败回滚、多个真实Beat周期，不以手动调用代替周期证据 |
| FR-09 | 核对原预期，区分路径幂等观察与强安全保证；残留marker不能成为授权依据 |

Worker启动预检固定 `SERVICE_NAME=worker`，验证目标连接池行为；真实 `run_download`/`reconcile_downloads` 注册且只订阅专属队列。Celery“succeeded”仅指函数正常返回，业务payload为failed时必须记业务失败。消息语义采用至少一次投递与幂等副作用，不宣称端到端exactly-once。

## 8. S6/S7汇合规则

S6执行准入必须同时具备：S4所需真实可靠性断言通过；S5两引擎、Node业务链、权限/审批事实通过；G3实体与原九项在目标环境认证；人类JWT确认与同一Task/预案/项目/source/budget/nonce/expiry绑定且单次消费；服务端环境×协议×caller授权及撤销机制到位。默认拒绝，不能靠前端按钮或单全局布尔变量授权。

R3和G3-E2任务均不自行翻转 `DOWNLOAD_TRANSPORT_RUNTIME_ACCEPTED`、`WRITE_RUNTIME_ACCEPTED`、`agent_*_write_enabled`。G3受控HTTP测试通过独立认证入口调用真实Adapter设施，不绕过生产门禁。即使HTTP认证通过，既有全局门禁继续关闭，直到独立S6准入动作明确完成。

S7选取输入兼容、规模适中的授权数据：发现来源→Prepare→人类确认→受控执行→校验→FileRecord→冻结DatasetVersion→FlowFrame真实分析→BioReport→evidence manifest。若FlowFrame需要HTTPS/SRA才能取得真实研究数据，HTTP实验认证不能满足，须新增协议认证或选择符合已认证范围的合法数据源；不能将本地fixture分析写成真实GEO下载闭环。

交接清单至少绑定数据hash、版本、项目、来源/许可、过滤与预处理、参数、分析代码/容器/依赖版本、随机种子、运行ID和产物hash。失败重跑不覆盖旧版本。BioReport的科学结论须能回溯实际分析产物，并区分元数据示例、合成fixture和真实科学数据。

## 9. 交付与退出

每流交付：实现变更、最小必要回归、部署/预检/回滚说明、逐断言矩阵、原始证据索引、已知限制。全部结果从同一机器可读矩阵生成，保留原78项父ID与新增子断言。状态允许PASS_ISOLATED/PASS_RUNTIME/PASS_E2E/FAIL/BLOCKED/NOT_TESTED；部分覆盖用子断言呈现，父项不提升。

停止前关闭隔离读/测试开关、撤销租约和出口，保留受限证据及约定测试卷；不要删除用户数据或清空共享Redis。若停止证明缺失则隔离告警并保留现场。完成文档或代码不等于阶段验收完成。

## 10. 技术依据与适用限制

Linux cgroup v2 文档说明cgroup.kill对子树进程的终止能力和cgroup.events的populated状态；网络撤销仍需独立实现和证明：[内核文档](https://docs.kernel.org/6.7/admin-guide/cgroup-v2.html)。

XFS支持project quota的计量及可选强制执行；目标挂载与hard limit必须实际验证：[XFS内核文档](https://docs.kernel.org/admin-guide/xfs.html)。通用quota将块和inode列为不同限制：[Quota subsystem](https://www.kernel.org/doc/html/latest/filesystems/quota.html)。

这些资料支持机制选择，不证明CygnusX已经实现或目标机器可用。RX原子执行层、receipt格式和准入结构是本方案的工程设计建议，尚需目标内核验证和原S3契约审查。
