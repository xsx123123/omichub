# RI09.5 真机 Runtime + E2E 验收方案与检查表

版本：2026-10-17。本文是待执行方案，不是运行结果，不授权访问生产或绕过权限。

## 1. 来源、基线和适用范围

依据以下三份上传原文编制。摘要仅标识输入版本，不表示其业务制品已通过完整性验证。

| 来源 | 文件 SHA-256 |
|---|---|
| `cygnusx-runtime-acceptance-environment.md` | `18245dad1ce8dafb015540af436d393604eba4ecd38e08f25a6d7f356653f455` |
| `cygnusx-ri095-runtime-e2e-results.md` | `d00e2b28d42168e60ce4b770124863097578477d4525b880e61065a1c60ea775` |
| `cygnusx-ri095-runtime-stabilization.md` | `3b73125f271faf403e1589d6f13528afe3a23b3fba20a7fd053cb9a6fc3d9020` |

原文共同基线：独立环境配置交付 PARTIAL，离线配置/保护检查 PASS_STATIC；Docker 权限拒绝，所有真实运行项 BLOCKED，无 PASS_RUNTIME、无 PASS_E2E。此前未启动服务，因此历史上无需执行关闭操作。原文称完整业务 Playwright、精确阶段故障注入及全部 RA 自动业务执行器尚未实现，执行前必须重新调查，不能将其当成现成套件。

范围是现有项目报告及交付流程运行闭环，不重写 RI01–RI13/RI09.5，不扩大到所有 BioReport/Quarto 科学模板。本文新增的场景细化是执行检查建议；原 Gate 的确切断言、顺序和预期值必须以原始规范和已核实仓库为准，不得用建议替代原 Gate。

## 2. 状态规则与总体验收

| 状态 | 判定 |
|---|---|
| PASS_STATIC | 本次静态检查实际执行且所有断言符合；不证明容器或业务运行 |
| PASS_RUNTIME | 指定真实运行场景执行，实际断言和证据完整；注明覆盖范围 |
| PASS_E2E | 指定真实端到端场景和浏览器行为均符合，链路证据能关联 |
| FAIL | 已执行，出现断言不符、错误结果或安全违规；保留原始失败 |
| BLOCKED | 前置条件缺失、工具/执行器缺失、无法执行或证据不足；写明原因和解除条件 |

每个场景分别记录 static/runtime/e2e 层级，不把一个层级的 PASS 外推到另一层。未执行默认为 BLOCKED（待执行），不是 FAIL。FAIL 修复后留原记录，新 attempt 记录重跑结果，不覆盖历史。总体验收只有在全部必需 Gate 和业务场景通过、证据齐全、回滚确认后才可关闭；任何必需项 FAIL/BLOCKED 均不能宣布完整通过。对象存储按原文保持独立状态；若项目明确不纳入本轮，须在范围记录中列出排除依据，结论只能称“本地存储范围通过”，不能隐去该 BLOCKED。

## 3. 预检与准入（任何写入前）

- [ ] 正式授权记录：操作者、授权人/依据、主机和 daemon、允许资源、有效时间、测试数据范围。不能把本文当作权限凭据。
- [ ] 仓库绝对路径、commit、分支、dirty 文件、AGENTS.md 与原始三文档版本已记录；已有修改不覆盖。
- [ ] 阅读 `deploy/acceptance/README.md`、Compose/env 示例、Dockerfile、runtime/control/checks/summarize、`run-checks.sh`、只读 `state.sql`、Nginx 和浏览器探针；确认实际路径存在。
- [ ] 从原规范/README/实现建立 RA01–RA06 原文映射，列文件/行号、执行器、前置条件、断言、证据；定义不全或冲突先 BLOCKED。
- [ ] 明确命令、服务名、数据库表/列、API 路由、认证语义、超时/重试/并发窗口、partial 规则均已从仓库验证，没有猜测路径。
- [ ] Docker 正式授权可用且目标正确；权限拒绝则停止，不提权、不变更 socket、不换未经授权 daemon/context。
- [ ] 所有镜像审查并固定 digest，最小扩展 tag 带源码短 SHA；实际 image ID/digest 与源码绑定。扩展只补齐 data/UID10001 目录，不临时安装依赖掩盖缺失。
- [ ] 已批准既有完成任务/制品 corpus 的来源、owner/项目、任务状态、访问授权及可信预期哈希齐全；以隔离副本导入，不连接生产读取。缺少则停止相关业务验收。
- [ ] 专用用户/项目与独立 JWT 密钥准备完成；四个独立随机秘密通过安全方式提供，env 权限 600，不入库、不进入日志。
- [ ] 隔离存储、磁盘/配额、证据目录及保留策略足够；禁止 destructive 清理。

## 4. 隔离拓扑与启动前断言

目标拓扑：Playwright→frontend:8080→api:8000→PostgreSQL；API→Redis Broker DB1→Worker；结果 backend DB2；Beat 仅调度项目 report/export reconcile；Worker→独占私有卷。所有服务无宿主发布端口，网络 internal。

| 核对项 | 必须满足 | 证据 |
|---|---|---|
| Compose | 独立 project、独立 internal 网络，无 external 网络、生产挂载或 socket | 脱敏解析配置、资源清单 |
| 环境继承 | 禁用根 .env/Pydantic .env，不隐式继承宿主 DATABASE_URL、DOCKER_HOST、云密钥 | 控制器检查输出及安全配置审查 |
| PG | 预期 postgres / project_export_test_ri095 / ri095_acceptance；实际身份先于迁移/API/Worker/Beat 核验 | 实际 current_database/current_user/服务身份及控制器日志 |
| Redis | 本次独占实例，Broker DB1/backend DB2，队列 ri095_acceptance | 实际连接/队列元信息（无秘密） |
| 应用权限 | API/Worker/Beat UID10001，cap_drop ALL；无 privileged | 容器 inspect 的脱敏投影、进程身份 |
| 任务注册 | 仅四个项目任务；Beat 仅 report/export reconcile | 实际注册和调度清单，对照源码 |
| Storage | YAML 优先级已处理，有效根 /acceptance-storage 且落在独占命名卷 | 运行时有效配置、挂载及权限 |
| 门禁 | 初始 READS/WRITES/PDF 均 false；只在隔离实例按仓库规则最小开启 | 开启前后实际 flags、进程重启证据 |
| 浏览器 | Linux Playwright 与 Chromium 镜像/包匹配，不用 Snap，sandbox 可运行 | 包/浏览器版本及启动记录 |

任何配置试图读取生产秘密或访问生产立即停止。安全配置不能为了测试通过而放宽。

## 5. 命令占位与仓库验证

以下只给调查示例；本方案未持有仓库，未验证任何业务命令。`<...>` 是不可直接运行的占位。执行 Agent 必须填写下表、核对参数/副作用，并将最终命令与退出码留档。优先使用已验证的验收控制器，它提供环境清理和身份断言；不要用裸 Compose 绕开控制器。

```text
cd <已确认的仓库绝对路径>
git rev-parse HEAD
git status --short
rg --files deploy/acceptance
rg -n 'RA0[1-6]|validating|rendering|publishing|collecting' <已确认的规范和源码目录>
<已核实的授权 Docker 身份探测命令>
<已核实的验收控制器静态检查命令>
<已核实的六项错误配置拒绝回归命令>
<已核实的隔离环境启动命令，指定专用 project/env/固定镜像>
<已核实的实际 PG 身份断言命令>
<已核实的旧模型迁移/各 Gate/API/Worker/浏览器执行命令>
<已核实的证据汇总和隔离环境停止命令>
```

| 步骤 | 最终命令/入口 | 来源文件:行号 | 目标/副作用 | 前置断言 | 超时 | 退出码及日志 |
|---|---|---|---|---|---|---|
| 静态/拒绝回归 | 待核实 | 待填 | 仅合成配置 | 不接触真实服务 | 待定 | 待执行 |
| 启动/身份核对 | 待核实 | 待填 | 专用容器 | 第3、4节通过 | 待定 | 待执行 |
| 迁移/业务/故障/浏览器 | 每项单列 | 待填 | 隔离数据 | 对应 Gate | 待定 | 待执行 |
| 停止/门禁关闭 | 待核实 | 待填 | 本次 project | project 归属复核 | 待定 | 待执行 |

不要把包含凭据的完整 `docker inspect`、Compose config、进程环境、HTTP header 原样写入共享证据。秘密只验证存在性、独立性及权限；命令记录用脱敏参数。捕获真实退出码，不用日志管道的成功掩盖执行失败。

## 6. 分阶段执行与 Gate 检查表

### S0 静态与保护检查

重新运行离线 Compose 渲染和原有六项错误配置拒绝回归，逐项从仓库列出真实错误配置及预期拒绝原因，不编造六项内容。检查 Ruff/format、Node 语法等已有相关检查。输出 PASS_STATIC 仅覆盖本次实际检查项。首页探针仅为探针。

### S1 PostgreSQL 和认证基础

先启动最小依赖并核验实际 PG，再进行迁移；API/Worker/Beat 不能先于身份检查开始操作。

| Gate | 必做场景 | 通过所需证据 |
|---|---|---|
| RA01 旧模型升级/迁移顺序 | 构建原规范要求的旧 schema 状态，用批准数据副本真实升级；记录每步 revision 和先后关系、最终状态 | 迁移前后 schema/revision、SQL 输出及退出码、旧数据兼容断言；空库 head 不替代 |
| RA02 XOR/FK/冻结/旧报告 | 分别执行合法/非法 XOR、FK、冻结及旧报告兼容场景，使用真实 PostgreSQL；准确预期从原规范取得 | 正负 SQL 断言、SQLSTATE、事务及最终只读 state 快照；失败事务回滚证据 |
| RA03 并发/锁/项目保留 | 8 个真实业务 API 请求并发，验证 advisory lock 和原规范的唯一性/冲突语义；验证项目删除/停用后的保留要求 | 8 请求时间窗口、状态码、关联 ID、锁观测、Job/项目最终状态、删除/停用与保留结果 |

JWT 基础：现有注册/登录生成真实测试身份和 token；调用真实创建接口；保留脱敏请求/响应和 owner/项目关联。API key 必须在要求 JWT 的路径按原规范被拒绝。身份建立失败则停止依赖身份的 Gate，不用伪 token 顶替。

### S2 Worker/Beat 与故障恢复（RA04–RA06）

三份原文只将 RA04–06 合称 Celery，未给出逐 Gate 完整定义。下表必须在仓库核对后填完，当前三项均 BLOCKED（待核对/执行）。不得将下列公共场景擅自分配为 RA04/05/06。

| Gate | 原定义与来源:行号 | 执行器/缺口 | 精确断言/阶段 | 本次证据 | 状态 |
|---|---|---|---|---|---|
| RA04 | 待核对 | 待核对 | 待核对 | 无 | BLOCKED |
| RA05 | 待核对 | 待核对 | 待核对 | 无 | BLOCKED |
| RA06 | 待核对 | 待核对 | 待核对 | 无 | BLOCKED |

共同证据要求：真实 Broker/Worker/Beat 连接和注册、专用队列；重复投递、中断和恢复；消息/task/job ID、重试与 reconcile 时间线、最终状态及制品。验证原规范的幂等和锁行为，没有重复发布或孤立状态。报告阶段为 validating/rendering/publishing；collecting 是导出阶段。

精确故障注入须使用可定位到目标 Job/阶段、可确认触发时刻、可解除的测试机制，记录注入前/中/后状态。禁止广域杀进程、破坏共享 Broker 或真实源制品。若执行器不存在，可在隔离分支补齐最小测试工具并审查其目标与清理方式；未补齐前对应场景 BLOCKED。随机 kill 和启动日志不证明阶段恢复已覆盖。

### S3 报告、私有存储和授权负面场景

- [ ] 在同一实际 Worker 镜像记录 UID、镜像 digest、Pandoc/Typst/字体版本和中文字体可用性。
- [ ] 对照 project-summary.v1 / project-summary-adapter.v1 源码，核验实际模板/renderer 版本，记录输入数据和报告 Job。
- [ ] 真实生成 HTML/PDF，记录文件大小、SHA-256、FileRegistry 及 Job 关联；渲染 PDF 全页并检查中文、分页、截断和缺失图文。
- [ ] 报告失败恢复按实际阶段验证；不能只检查 PDF 文件存在。
- [ ] 私有存储验证原子发布、回读摘要、owner/项目归属、生命周期和配额；注入漂移、丢失、符号链接及撤权，逐项验证拒绝/失败和恢复语义。
- [ ] 漂移/丢失只操作本次隔离副本；预期摘要来自可信基线，不能仅“生成哈希”就宣称完整性校验通过。
- [ ] JWT 验证跨 owner、跨项目拒绝；停用/撤权后重复 API、文件读取与下载，核验实时重检及不泄露文件内容。响应状态码以仓库契约为准，不能臆定一律 403。
- [ ] 对象存储仅在独立测试 Bucket、凭据和前缀获明确授权后测试；禁止使用生产 Bucket。否则单独 BLOCKED，不以 local backend 通过替代。

每种负面场景保留预期/实际、注入范围、请求和最终状态，不把“没有报错”当成安全断言。

### S4 M0→Report→M1→ZIP

M0/M1 字段和成员语义须以仓库契约为准；本文不臆造 schema。

1. 冻结原 M0、旧 ZIP 和对应成员清单，保存可信摘要与只读副本；不覆写历史制品。
2. 用批准的真实完成任务触发 Report，关联真实 Job、HTML/PDF 和 FileRegistry。
3. 按现有接口生成/取得 M1，比较 M0→M1 的允许变化与报告引用，确认输入/版本/owner/项目一致。
4. 通过真实导出任务生成新 ZIP，逐成员比对清单、大小和 SHA-256，核对缺失、重复、意外文件、路径安全及 partial 声明是否符合仓库契约。
5. 验证失败/不完整场景：实际缺失与 partial/失败标识一致，不把 partial 当作完整成功；重试和重复投递不会破坏原制品。
6. 重新计算旧 M0 和旧 ZIP 摘要，必须与冻结基线一致；发现变化立即停止并保留现场。
7. 用真实 JWT 下载新 ZIP，比较下载内容与私有存储中的预期摘要；撤权后重新下载必须按契约拒绝。

保存 manifest 差异、ZIP 成员摘要表、Job 时间线、HTTP 下载结果与权限负面结果。孤立脚本直接打包不替代真实业务导出。

### S5 浏览器 E2E

Linux Playwright/匹配 Chromium，在 1920、768、390 三个 viewport 宽度运行，记录高度、deviceScaleFactor 和版本。全部使用隔离 frontend→API 真实服务，不 mock 关键链路。

| 场景 | 浏览器断言 | 证据 |
|---|---|---|
| 正常链路 | 登录→项目/任务→报告提交和状态→查看/下载→M1/ZIP 导出和下载 | 各宽度关键截图、trace、请求/Job ID、下载摘要 |
| 权限 | API key 拒绝；跨 owner/项目、停用/撤权后 UI 与下载行为一致 | 脱敏网络结果、截图、服务端对应断言 |
| 恢复 | 报告/导出失败与恢复可见；重复操作符合幂等契约；刷新后状态一致 | 注入关联、前后截图、任务/网络时间线 |
| 响应式 | 三宽度无关键遮挡/溢出，操作和状态可访问 | 截图及人工检查结论 |
| 浏览器健康 | 无未解释 console error/失败请求，下载内容正确 | console/网络日志与下载回读 |

完整 spec 缺失时记录缺口并实现可复跑的最小完整业务 spec；不能把首页打开、jsdom、原单测或截图本身称为 PASS_E2E。

## 7. 证据组织与最小结果格式

建议在仓库 `evidence/runtime-acceptance/<run-id>/` 保存，每次 run-id 唯一，重跑使用 attempt 子目录。实际路径以仓库规则确认。

```text
authorization/        授权引用、目标和范围（脱敏）
baseline/             commit、源文档摘要、corpus 批准和可信预期摘要
preflight/            环境/镜像/版本/隔离配置和命令映射
ra01/ ... ra06/       逐场景命令、SQL/API/Worker、前后状态
report/ storage/ auth/
chain/                M0、M1、差异、新旧 ZIP 成员和摘要
browser/              viewport、截图、console、脱敏 trace/网络、下载
rollback/             flags、停止/重启、保留资源核对
results.md            逐项结果、失败、阻断、修复和范围
index.json            证据路径、大小、SHA-256、采集时间和关联 ID
```

每项结果必填：run-id/attempt、Gate 与来源、场景、前置条件、预期断言、实际观察、开始/结束时间（含时区）、最终命令、退出码、commit/image digest、task/job/project/owner 的脱敏 ID、证据路径/摘要、状态、失败或阻断原因、下一步。容器日志和客户端证据须能通过 ID 与时间关联。

原始证据只在受控私有目录保留；共享副本去除密码、JWT、cookie、连接串及敏感 corpus 内容。HAR/trace 可能含 token，未经检查不可外发。先保留原始失败，再生成脱敏副本及各自摘要；索引排除自身避免递归哈希。摘要能标识证据版本，但不能替代断言或可信预期哈希。

## 8. 失败停止、最小修复和回滚

| 事件 | 动作 |
|---|---|
| 权限拒绝/目标无法确认 | 不启动或停止本次受控操作；BLOCKED；请求授权方修复正式环境，不自行绕过 |
| 命中生产/隔离破坏/旧制品变化 | 立即停止写入与依赖任务，保留现场和受影响范围；已执行异常记 FAIL，未执行依赖记 BLOCKED |
| 无 corpus/缺原 Gate/缺工具 | 对应项及依赖项 BLOCKED，列解除条件；无关只读检查可继续 |
| 业务断言失败 | FAIL；停止依赖阶段，保留数据库、Job、日志与制品；排查后最小修复 |
| 超时或恢复不收敛 | 保存最后状态、超时值和日志；断言超时记 FAIL，环境不可执行记 BLOCKED，不无上限重试 |

修复限隔离分支和验收必要范围，记录变更、原因、影响及 commit。原失败不删除，同场景以相同输入/环境重跑，再回归受影响 Gate；不得删断言、放宽门禁、用 mock 替代真实场景或改旧制品。需要扩大授权/触碰生产时停止该动作，交给负责人。

收尾顺序：

1. 冻结证据和最后只读状态；核对本次 Compose project 与资源归属。
2. 通过仓库已核实的控制器停止本专用 project；不得停止其他项目。
3. 将私有 env 的 READS/WRITES/PDF 全设 false，确认旧进程确实退出。单改 env 不算回滚。
4. 若需只读重启，先核对实际运行 flags；不能凭配置文件推断生效。
5. 保留独立 PG/Redis/私有卷、Job 和冻结证据。禁止 downgrade、drop、`down -v`、prune 或清除审计事实。
6. 记录停机/重启命令、时间、退出码、剩余容器与资源、flags、未收敛任务。保留资源的后续清理由另行授权决定。

## 9. 最终签核检查表

- [ ] 所有 RA01–RA06 均保持原定义并有真实证据；缺口没有被泛化场景掩盖。
- [ ] HTML/PDF、私有存储、JWT、M0/M1/ZIP、三宽度浏览器正负及恢复场景逐项通过。
- [ ] 无把 PASS_STATIC、探针、空库迁移、SQL 并发或合成配置外推为真实业务通过。
- [ ] 镜像、源码、corpus、环境、命令与证据可追溯且已脱敏。
- [ ] FAIL 的修复/重跑可追溯；BLOCKED 的原因、依赖、责任方和解除条件明确。
- [ ] 对象存储及全部 BioReport/Quarto 模板的覆盖边界单列。
- [ ] 生产默认值和旧 Manifest/ZIP 未变，有本次可验证依据。
- [ ] 回滚/门禁实际生效已核对，资源和审计事实保留。

最终报告填写“本次实际通过范围 / FAIL / BLOCKED / 未覆盖范围 / 证据索引 / 回滚状态”。只有全部必需项具备真实通过证据时才可宣称对应范围完成；当前本文的运行结果仍为 BLOCKED（待执行）。
