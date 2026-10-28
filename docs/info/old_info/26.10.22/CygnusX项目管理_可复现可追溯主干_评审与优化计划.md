# CygnusX 项目管理——可复现/可追溯主干评审与优化计划

> 评审基线：用户上传的《CygnusX项目管理架构与科研功能未启用调查.md》（调查时间 2026-10-21）
> 评审视角：项目管理是平台 agent 分析流程"可复现 + 可追溯"的最大依靠——对照这个定位，评估框架合理性、核对调查报告、给出优化与实施顺序。
> 本文是跨轮累积的活文档：后续轮次的补充需求追加为新 Part，不另起新文档。

---

## 0. 结论速览

**框架方向是对的**：显式血缘关联、冻结 Handoff/Manifest、四类交付条件分别建模、PLAN_ONLY 人机门禁、分层功能开关——这些都是可复现/可追溯系统该有的骨架，而且是"刻意设计"，不应被任何缺口清单当成待办修掉。

**但主干目前是空转的**：骨架已建好，没有任何真实数据流过——36 个项目、226 个 Task、159 个 Report、484 个会话，而 Dataset 与 AnalysisLink 全为 0。只要 agent 分析执行不在"发生时刻"事务性落地血缘记录，inventory 永远是空的，"可复现可追溯"就停在架构图上。**写路径贯通是唯一的关键路径**，其余都是外围。

**一个被低估的 P0**：报告 §7 把"删除项目可被磁盘回填复活"列在"额外发现"里，从生命周期可信度看，它应该升级为最高优先级——一个会把已删项目"复活"的系统，不能被当作可追溯主干来信任。

---

## 1. 调查报告核对

### 1.1 确认的判断（证据充分，我同意）

1. **三个截图提示的归因链**：九个服务开关全部默认关闭，门禁函数复现均为 FEATURE_DISABLED；第三张卡（可追溯导出）在加载 inventory 时就先被 `research_delivery_read_enabled` 拦下，红条不能单独证明"只缺导出开关"——推理严密，且明确区分了"门禁函数复现的 403"与"已登录 HTTP 实测"，没有把前者冒充后者。
2. **"科研模式"按钮不能解决门禁**：它只写 `settings.research_mode`（新会话默认值），与服务级 Settings 开关是两层；管理员角色也不能绕过无角色分支的源码开关。判定正确。
3. **保持关闭的既有依据成立**：最新验收为 PARTIAL / 生产 NOT_ACCEPTED，真实 corpus、非空交付链、Worker ZIP、授权下载闭环均未验收；不能用旧文档"Docker 没权限"解释现状——本轮已取证 Docker 可访问、三容器在运行。
4. **§7 五个额外发现**均带代码位置，其中删除/回填冲突的推演（删行不删目录 + `_backfill_from_disk` 按 slug 重建 → 已删项目可在列表复活）逻辑成立，虽未做破坏性实测，但作为源码级推演可信。
5. **§8 分阶段开放的总体顺序**（先只读、再真实 corpus、再导出、最后执行/报告）正确，符合"证据先行、逐层授信"的原则。

### 1.2 保留意见与补充（我与报告不同或报告未覆盖的）

1. **删除/回填冲突应升级为 P0**，不是"后续维护问题"。可追溯主干的前提是生命周期可信：删除动作不可靠，项目身份就不可靠。它不依赖任何科研开关，应立即修。
2. **"功能状态展示"应从报告 §8 的阶段 1 解耦，提前为阶段 0 的一部分**。区分"服务关闭/无权限/无数据/请求失败"不需要打开任何科研开关，它是纯前后端展示层改造，收益最快（立刻消除"项目整体故障"的错觉），与后续所有阶段零冲突。
3. **报告未覆盖一组关键核查项——"复现要素的固定范围"**。报告确认了 ProjectArchiveService 归档 README/环境快照/manifest，但没有确认每次运行是否自动固定：输入数据版本哈希、容器镜像 digest、工具与参考数据库版本、模型与 prompt 版本、参数与随机种子。**注意：这是"证据不足、待核查"，不是"断言缺失"**——若代码中已有固定，请指出位置。缺任何一项，"复现"都会打折扣。
4. **FileRegistry 是否内容寻址（SHA）、审计事件覆盖面**（计划审阅/advance、导出创建/重试/下载、门禁拒绝是否有 append-only 记录）——报告未核查，这两项是"追溯"的物证层，建议纳入施工前调查。
5. **Run 的身份问题报告点到但未展开**：overview 靠目录名解析时间、mtime 回退，Run 不是数据库实体。报告自己也承认"一行目录、Task、Run、Step、Job 是不同对象，不能互视为证据"——这正是 Run 需要一等公民化的理由，但属于架构增强，排在血缘有真实数据之后。

### 1.3 "刻意不做"清单（不得被任何后续报告带进待办）

| 设计 | 为什么是对的 |
| --- | --- |
| `association_scope=explicit_dataset_links_only`、`NO_PROJECT_FK_NO_BACKFILL` | 血缘绝不靠目录名/时间猜测，是可追溯的根基；历史任务关联必须走单独的可审计方案 |
| 计算成功 / 字节完整 / 证据充分 / 可交付 四条件分别建模 | Task success 不能替代其余条件，防止"跑完=可交付"的误推 |
| PLAN_ONLY + WAITING_APPROVAL + LIVE_EXECUTION_BLOCKED + 模型不能自批准 | 人机门禁边界清晰，审阅指定版本与 digest，不批准执行 |
| 导出大小上限（64 MiB / 16 MiB / 80 MiB / 500 文件） | 有界打包，不是无界压缩整个项目目录 |
| 项目单所有者、无项目成员表 | 现阶段产品决策；团队文件 ACL 是独立体系——但应在架构文档中**写死这是刻意决策**，避免后续误读为缺陷 |
| 九开关默认关闭 + `WRITE_RUNTIME_ACCEPTED=False` 源码硬门 | 证据未收口前不授信，环境变量不能冒充验收 |

---

## 2. 框架合理性评估（对照"可复现 + 可追溯"目标）

### 2.1 做对了什么（应保持）

1. **显式血缘、拒绝猜测**——追溯系统最大的敌人是"看起来像关联"，显式 Dataset 链从根上杜绝了伪追溯。
2. **冻结快照**——frozen Handoff / frozen Manifest 提供了不可变参照物，这是"可复现"的物理基础。
3. **门禁分层且各有独立开关**（plan / delivery-read / delivery-write / export / report / pdf / gateway / analysis-write / download-write）——可以逐层授信、逐层回退，粒度合理。
4. **导出链路工程化完整**——独立 Job/Request、幂等、Celery outbox、Beat 恢复、下载时权限与字节复核，是"证据分发"的正确形态。
5. **调查方法论本身就是追溯文化**——机器可读 snapshot.json、可重复执行的只读采集器、白名单输出、SHA-256 存档区分脏工作树。这套做法值得固化成制度（每次架构调查都产 snapshot + collect 脚本）。

### 2.2 结构性风险（按对主干的威胁排序）

| # | 风险 | 证据 | 对可复现/可追溯的影响 | 优化方向 |
| --- | --- | --- | --- | --- |
| R1 | **血缘写路径不通**：执行完成时刻没有事务性落 Dataset/Version/Handoff/Link 的通路 | Dataset/AnalysisLink 全 0；`agent_analysis_write_enabled=false`、`WRITE_RUNTIME_ACCEPTED=False`、`worker_paths_verified=False` 三重门 | **致命**——骨架无血流，主干空转 | 施工前只查不改调查（§5 阶段 1），摸清落库点与三个门的置真前置，再在隔离环境试点一条端到端链 |
| R2 | **双口径聚合并存且无对账**：磁盘 runs 扫描 vs Dataset 链 inventory | 报告 §7 第四行 | 高——"实际发生了什么"与"正式登记了什么"长期发散，无人知道差多少 | 增加"未登记运行"对账视图：磁盘有、血缘无的运行进入人工策展队列（显式关联入口），而不是两个口径各自展示 |
| R3 | **Run 不是一等公民** | 目录命名约定 + mtime 回退；无稳定 Run ID | 高——Task/Report/目录持续"互不能视作证据" | Run 实体化（DB 表 + 稳定 ID + 每 run 一份 manifest.json），同时把 overview 的递归扫描改为读 manifest 索引（一箭双雕解决 R7） |
| R4 | **复现要素固定范围未证实** | 报告只确认归档 README/环境快照/manifest | 高（若缺）——镜像 digest/工具版本/模型与 prompt 版本/种子缺一项，复现就打折 | 列入阶段 1 调查清单，逐项判定"已固定/未固定"，不断言缺失 |
| R5 | **生命周期可信度缺陷** | 删除可被回填复活（a）；科研模式开关不回填（b）；status NULL 当 active（c）；无改名 API（d) | (a) 高——删除不可靠则项目身份不可靠；(b)(c)(d) 低但持续侵蚀信任 | 全部进阶段 0 止血包，不依赖科研开关 |
| R6 | 单所有者 + 无项目级授权路径 | 无 project_members 表；团队文件 ACL 独立 | 中——单人追溯够用，协作复现他人分析时无授权通道 | 现阶段写死"刻意单所有者"；若平台走向协作科研，再立项项目成员/角色（不与团队文件 ACL 混用） |
| R7 | overview 递归扫描成本随目录增长 | 报告 §7 第五行 | 中——性能问题，但顺手与 R3 合并解决 | manifest 索引化 + 分页统计 |
| R8 | 既有架构文档与源码三处漂移 | status 枚举、删除行为、run 发现规则 | 中——文档是追溯叙事的一部分，带病文档会误导后续施工 | 阶段 0 就地修订为源码事实 |

---

## 3. 分阶段实施计划

排序原则：**止血前置**——不依赖架构改动、不依赖科研开关、只差一次修复/一个端点的事项全部提前到阶段 0；**关键路径唯一**——R1 写路径贯通是主干，先只查不改摸清，再试点；其余按报告 §8 的证据分层推进。

| 阶段 | 内容 | 对应报告 §8 | 依赖 |
| --- | --- | --- | --- |
| **0 止血包** | 修 R5(a)(b)(c)(d) 四个生命周期缺陷；修 R8 文档漂移；上"能力状态端点 + 三卡片错误分型"（R 报告 §8.1 提前） | §8.1 提前 + §7 落地 | 无——不动科研开关，不改架构 |
| **1 施工前调查（只查不改）** | R1/R4 事实清单：写路径落库点、Handoff 复现要素、FileRegistry 寻址、审计覆盖面、三重门置真前置、对账代码有无 | 新增 | 阶段 0 不阻塞，可并行 |
| **2 只读开放与空状态验收** | 隔离环境开 RESEARCH_PLAN / DELIVERY_READ，核对用户/项目/模块权限，PLAN_ONLY 空状态 | §8.2 | 阶段 0 的错误分型先做，体验才好 |
| **3 真实 corpus 与写路径试点** | 真实 DatasetVersion/Handoff/Link 来源；隔离环境试点一条端到端链（真实分析 → 血缘落库 → inventory 可见） | §8.3 扩展 | 阶段 1 报告 |
| **4 已有成果导出闭环验收** | PROJECT_EXPORT 独立开，JWT 创建 → Worker 打包 → ZIP/SHA → JWT 下载，覆盖重试/重复派发/撤权/恢复 | §8.4 | 阶段 3 有真实链路后 |
| **5 Run 实体化 + 对账视图 + manifest 索引** | R2/R3/R7 架构增强 | 新增 | 阶段 3 之后（有真实数据再动架构） |
| **6 执行与正式报告/PDF 评审** | Worker 路径/输入验证、真实分析案例、报告渲染依赖 | §8.5 | 最后 |

**阶段 2 及以后的 paste-ready 提示词，在阶段 1 调查报告拿回后按核对 loop 补充进本文档**——现在写会基于未证实的事实。

---

## 4. 阶段 0 提示词（paste-ready，交给编码 Agent）

```
任务：在现有 CygnusX 仓库上完成项目管理生命周期的四个止血修复、一处文档就地修订、以及一个项目能力状态端点与前端错误分型。先读现有代码再改，禁止推倒重写；不动任何科研功能开关（research_plan / research_delivery / project_export / report / pdf / tool_gateway / agent_analysis_write / agent_download_write 均保持现状），不改无关模块。

背景证据（来自 2026-10-21 只读调查报告）：
1. 删除/回填冲突：delete_project 只删项目行与目录索引、保留物理目录；list/count 的 _backfill_from_disk 会为缺失 slug 重建项目——已删除项目可能在后续列表中以新记录"复活"。位置：src/cygnusx/application/services/project_service.py。
2. 科研模式开关不回填：前端 projectResearchDefault 初始为 false、切换项目时重置 false、加载 overview 后未从 settings 赋值——已保存 true 的项目刷新后显示关闭。位置：frontend/src/views/ProjectDetailView.vue:39 附近。
3. projects.status 允许 NULL 并按 active 解释；现网 36 行全部为 NULL。实际枚举为 active / completed / handed_over。
4. 项目名/描述无修改入口：PATCH 只接受 status 与整体替换的 settings。
5. 文档漂移：ARCHITECTURE_DESIGN/CygnusX_project_workspace_architecture.md 三处与源码不一致——status 枚举误写为 archived/deleted；删除行为易被理解为删除物理目录（实际保留）；run 发现误写为依赖命名正则/标记（实际接受所有非隐藏一级子目录，正则仅用于时间解析）。
6. 前端三卡片（ResearchPlanWorkbench / ResearchDeliveryChain / ProjectResearchDelivery）catch 所有失败后显示统一"检查功能及权限"，功能关闭、权限不足、无数据、网络失败四种情况无法区分，视觉上像项目整体故障。ProjectDetailView.vue:555 只用 v-if="overview" 挂载，未按能力状态预先处理。

施工要求：
A. 删除/回填冲突（最高优先）：先读 project_service.py 现状，然后在以下两个方案中二选一并说明取舍理由——
   (a) 删除时将物理目录重命名为隐藏目录（如 .deleted-<slug>-<timestamp>），回填天然跳过隐藏目录；
   (b) 增加删除 tombstone（表或标记文件），回填时跳过有 tombstone 的 slug。
   无论选哪个，补回归测试：创建→删除→list/count→刷新后不再出现；回填对真实历史目录的行为不变。
B. 科研模式开关回填：加载项目详情/overview 后，从 project.settings.research_mode.enabled 回填开关；切换项目时按新项目的已保存值重置而不是一律 false。补前端组件测试（已保存 true 的项目挂载后开关为开）。
C. status 显式化：Alembic 迁移把存量 NULL 回填为 'active'，列改为 NOT NULL DEFAULT 'active'；读取侧的 NULL 兼容分支保留一个版本并注明移除版本号。
D. 项目名/描述修改：扩展 PATCH 支持 name/description 的可选修改（slug 不变，避免目录与链接失效）；校验与创建一致；补测试。
E. 文档就地修订：把上述三处漂移改写为源码事实（status: active/completed/handed_over，NULL 兼容期说明；删除保留物理目录；run 发现接受所有非隐藏一级子目录）。只改这三处，不重写整篇。
F. 能力状态端点 + 错误分型：
   - 后端新增 GET /projects/{id}/capability-status（或并入现有 overview 响应，二选一说明取舍），返回当前用户视角三项能力的 {enabled, allowed, reason}：research_plan / research_delivery_read / project_export。匿名 401、非 owner 403、owner 200 三态都要有。
   - 前端三卡片改为按 服务未启用 / 当前用户无权限 / 暂无数据 / 请求失败 四类分型展示，文案分别写清；服务未启用时卡片降级为说明条，不再发起必然失败的请求。
   - 禁止把四类失败继续合并成一句"检查功能及权限"。

验收（不接受只跑单测，每条给出手测路径）：
- A：创建一个测试项目→删除→多次刷新列表与 count→不再出现；确认物理目录按所选方案处置；带真实历史 runs 目录的既有项目不受影响。
- B：对 settings.research_mode.enabled=true 的项目，刷新页面后开关显示为开；切换到未开启项目显示为关。
- C：迁移后 36 行存量全部为 active；新建项目默认 active；completed/handed_over 流转与休眠打包行为不变。
- D：PATCH 改名/改描述成功，slug 不变，详情页显示新值；非法输入被拒。
- F：匿名访问 capability-status 返回 401；非 owner 返回 403；owner 拿到三门真实状态；手工把某门保持 false 时，对应卡片显示"服务未启用"说明条且不再发失败请求。

交付：每个修复单独一段说明（根因 → 改法 → 文件:行号），不要合并成一句"已修复"；完成后列出改动的全部文件清单与测试输出。验收权在我手里，不接受自报通过。
```

---

## 5. 阶段 1 提示词（paste-ready，只查不改的施工前调查）

```
任务：只做代码级调查与评估，禁止修改任何代码、配置、数据库与文档；先读代码再下结论，所有结论必须标注文件路径与关键代码位置（文件:行号或 文件#函数名）。不带证据位置的结论不予接受。

调查目标：为"agent 分析流程的血缘写路径贯通"做施工前调查。CygnusX 的可复现/可追溯主干是 Dataset → DatasetVersion / frozen Handoff → DatasetAnalysisLink → Task → 真实产物 / Observation → 科学报告 这条链，但现网数据库中 Dataset 与 AnalysisLink 均为 0——骨架已建好，没有数据流过。需要摸清写路径的每一个事实，为后续试点一条端到端链做准备。

逐项核查清单：
1. 落库点：agent 分析执行从开始到结束的完整链路中，哪些位置已有、或可以事务性创建 Dataset / DatasetVersion / Handoff / AnalysisLink 记录？现有代码里有没有写了一半的入口（被 WRITE_RUNTIME_ACCEPTED 或 agent_analysis_write_enabled 挡住的分支）？逐处列出位置与当前行为。
2. Handoff schema 复现要素核对：冻结 Handoff 实际固定了哪些字段？逐项判定 已固定/未固定 + 证据位置：
   a. 输入数据版本哈希；b. 容器镜像 digest；c. 工具与参考数据库版本；d. 模型与 prompt 版本（LLM 步骤）；e. 运行参数；f. 随机种子。
3. FileRegistry：产物登记是否内容寻址（SHA-256 或等同）？同一产物重复登记的行为是什么（幂等/报错/重复行）？导出 ZIP 的 SHA 校验用的是哪一层哈希？
4. 审计事件：计划审阅/advance、导出创建/重试/下载、门禁拒绝（FEATURE_DISABLED/403），分别有没有 append-only 的审计记录？写在哪张表/哪个日志？没有记录的逐条列出。
5. 三重门的置真前置：WRITE_RUNTIME_ACCEPTED（agent_tool_gateway.py:47）与 Handoff 中 worker_paths_verified=False，代码与注释、测试、验收文档里各自写明的置真前置条件是什么？列出距离置真还差哪些已命名的事项。agent_analysis_write_enabled 这个配置门与源码硬门的叠加判定顺序是什么？
6. 对账：现有 Celery Beat 对账只覆盖导出 Job 恢复，还是已有任何"磁盘 runs 目录 vs 血缘记录"的比对代码？若无，确认无；若有，列出位置。
7. Run 实体化可行性：现有一次分析运行（projects/{slug}/runs/ 下一级目录）在数据库里对应的实体有哪些、缺哪些？ProjectArchiveService 归档的 README/环境快照/manifest 是在什么时机、由谁触发写入的？

交付格式（写死，作为拿回报告后的核对 checklist）：
1. 能力矩阵表：环节 × 是否已有代码 × 文件:行号 × 门禁（哪个开关/硬门挡着）。
2. Handoff 复现要素核对表：要素 × 已固定/未固定 × 证据位置。
3. 写路径链路图（文字版）：从"一次 agent 分析执行完成"到"inventory 可见"的每一跳，标注断点与门禁。
4. 按严重度分级的缺口清单：必须区分"刻意门禁"（如 WRITE_RUNTIME_ACCEPTED 未验收）与"真缺失"（代码里根本不存在），不得把前者写成后者。
5. 对"试点一条端到端血缘链"的最小改动面估计：只列位置与改动点描述，不写实现代码。
```

---

## 6. 阶段 0 验收对照表（用户手测版）

| # | 操作 | 期望现象 | 不通过时的处理 |
| --- | --- | --- | --- |
| 1 | 新建测试项目 → 删除 → 连续刷新项目列表与数量接口 | 项目不再出现，且后续任何刷新不"复活" | 让编码 Agent 交 `_backfill_from_disk` 对该 slug 的判定日志，核对所选方案（隐藏目录/tombstone）是否真生效 |
| 2 | 对科研模式已开启的项目，刷新项目详情页 | "新会话默认开启科研模式"开关显示为开 | 交 overview 响应 JSON，确认 `settings.research_mode.enabled` 已返回且前端已回填 |
| 3 | 切换到从未开启科研模式的项目 | 开关显示为关（不是继承上一个项目的值） | 检查切换项目时的重置逻辑是否按新项目 settings 赋值 |
| 4 | 查看数据库 projects 表 | 36 行存量 status 全为 active，无 NULL | 核对 Alembic 迁移脚本与执行记录 |
| 5 | PATCH 修改项目名/描述 | 详情页显示新值，slug 不变，runs 目录不受影响 | 交请求/响应与数据库行前后对照 |
| 6 | 匿名访问 capability-status | 401 | 核对路由注册与认证依赖顺序 |
| 7 | 非 owner 登录访问该端点 | 403 | 核对 owner 校验分支 |
| 8 | owner 访问，且三个科研开关保持 false | 三卡片显示"服务未启用"说明条，浏览器 Network 里不再有必然失败的三个请求 | 逐卡片截图 + Network 面板对照 |
| 9 | 阅读修订后的架构文档三处 | status 枚举、删除行为、run 发现规则与源码事实一致 | 逐句对照源码位置（§1.2 证据） |

测试分工：1/4/5 由编码 Agent 跑自动化 + 用户抽查；2/3/6/7/8/9 用户手测为主。

---

## 7. 风险与回退

1. **阶段 0 的最大风险是 A 项方案选择**：方案 (a)（重命名物理目录）改动文件系统行为，若存在其他按路径引用的历史记录需先普查；方案 (b)（tombstone）改动更小但多一张表/标记。编码 Agent 必须在动手前先交现状普查（谁还引用 `projects/{slug}` 路径），再定方案。
2. **status 迁移回退**：迁移前备份 projects 表；NULL 兼容分支保留一个版本，确认无异常后再移除。
3. **capability-status 不能泄露门禁内部细节**：响应只给当前用户视角的 enabled/allowed/reason，不暴露其他用户或系统配置值。
4. **阶段 1 调查本身零风险**（只查不改已写死），但拿回报告后必须按交付格式逐项核对：能力矩阵缺格、把"刻意门禁"写成"真缺失"的，退回补全后再定稿。
5. **任何阶段都不以"前端显示正常"作为跑通证据**——凡涉及"通没通"的结论，以后端日志/审计事件/数据库记录为物证。

---

## 8. 本文档目前覆盖范围

- 第 1 轮（2026-10-21）：对《CygnusX项目管理架构与科研功能未启用调查》的核对结论、框架合理性评估（R1–R8）、六阶段实施顺序、阶段 0/阶段 1 的 paste-ready 提示词、阶段 0 验收对照表。
- 待后续轮次补充：阶段 1 调查报告拿回后的核对结论（确认/保留/行动顺序三块）；阶段 2–6 的 paste-ready 提示词；若调查证伪本文任何判断，在此显式留修正记录（哪条旧判断、被什么证据推翻）。

---

# Part II　三方评审对照与融合目标态（2026-10-21 第二轮）

> 输入：另两位 Agent 对同一份《调查》的评审（下称 **Agent A**＝"双轨制割裂"四痛点版；**Agent B**＝评分卡 + ResearchRun 身份体系版）。本 Part 做三方对照，并给出融合后的最终目标态与路线图。

## 9. 三方共识（共性）——这些判断已经被独立验证三次，可直接锁定

| # | 共识 | 我 | A | B |
| --- | --- | :-: | :-: | :-: |
| C1 | 底座设计正确，不推倒重建（显式血缘、冻结 Manifest、四条件分别建模、PLAN ONLY、分层门禁） | ✓ | ✓ | ✓ |
| C2 | 最大问题＝血缘空转/双轨制：磁盘 runs 与 DB 血缘互不相通，存量 226 Task / 159 Report 进不了交付链 | ✓ R1+R2 | ✓ 痛点 1 | ✓ 问题 1 |
| C3 | 删除/磁盘回填导致"幽灵项目复活"，是 P0 级生命周期缺陷 | ✓ | ✓ | ✓ |
| C4 | Run 必须成为一等公民（稳定身份 + 元数据入库），overview 告别递归扫盘 | ✓ R3/R7 | ✓ | ✓ |
| C5 | 生命周期小修包：设置回填、PATCH 改名、status NULL→active、文档漂移 | ✓ | ✓ | ✓ |
| C6 | 写执行门禁应从源码硬编码走向"审批 + 预检验证"动态驱动 | ✓（先调查） | ✓ 三条件令牌 | ✓ 方法治理绑定 |
| C7 | 存量历史运行必须显式、可审计地纳管，绝不靠名称/时间猜测 | ✓ 对账队列 | ✓ 显式认领 API | ✓ 历史迁移向导 |
| C8 | 后端下发能力状态 + 前端错误分型，消除"报错风暴" | ✓ | ✓ | — |
| C9 | 项目角色体系（owner/reviewer/member/viewer）是协作科研的必经路 | ✓（节奏不同，见 D1） | ✓ | ✓ |

## 10. 各家独有的增量（差异）——不是冲突，是互补的三层

**我独有（施工纪律层）**：阶段 0/1 的 paste-ready 提示词与验收对照表；"刻意不做"保护清单（防止后续报告把刻意设计当缺口）；先只查不改、摸清 Handoff 已固定了哪些复现要素再动工；报告核对 loop。

**Agent A 独有（机制设计层）**：
1. **"会话即上下文，执行必挂链"默认契约**——93 个已绑定 project_id 的会话里触发分析时，网关自动初始化/关联 DatasetVersion 并在派发 Task 时自动写 DatasetAnalysisLink，增量分析 100% 自动入链。这是 R1 写路径最具体的落法。
2. **存量 Run 显式认领 API**——项目所有者勾选磁盘历史 run 目录 → 校验 ProjectArchiveService 已归档的 manifest 完整性 → 显式补建 DatasetVersion + AnalysisLink，完成"血缘转正"。
3. **Handoff 预检协议**——轻量 Celery 探针核验输入文件在 Worker 视角的可读性/大小/SHA，通过后把 `worker_paths_verified` 置真并固化签名。
4. **审批令牌门禁**——`WRITE_RUNTIME_ACCEPTED` 硬编码改为三条件同时满足：环境开关开 + 该步骤对应 Plan 版本与 digest 已获 owner 显式批准 + Handoff `worker_paths_verified==True`。
5. settings 局部合并（JSON Merge Patch）替代整体替换。

**Agent B 独有（架构愿景层）**：
1. **统一 ResearchRun 身份体系**——Project / PlanVersion / Run / Attempt / StepRun / Artifact / EvidenceManifest 七类 ID 各司其职；Run、Task、Attempt 不可合并（重试必须有可区分的 Attempt，重复派发不得重复登记）。
2. **Manifest 三阶段证据契约**——执行前冻结（数据/工作流版本、参数、代码提交、镜像 digest、审批记录）、执行中采集（命令、环境、Worker 身份、stdout/stderr 摘要）、执行后结算（产物 URI、校验值、验证状态）。这把我的 R4"待核查项"直接展开成了目标规范。
3. **统一 Provenance Event 协议**——`RUN_CREATED → INPUTS_VERIFIED → PLAN_APPROVED → RUN_AUTHORIZED → STEP_STARTED → STEP_COMPLETED → ARTIFACT_REGISTERED → EVIDENCE_SETTLED`，事务内写状态 + Outbox 异步投递，不必一上来建 Event Sourcing。
4. **国际标准映射**——内部保留自有契约，对外映射 W3C PROV / OpenLineage / Workflow Run RO-Crate（其 Process/Workflow/Provenance Run 分层与 FlowFrame + BioReport 很贴近）。
5. **FlowFrame 双模式 = 科学方法治理层**——探索模式（Agent 脚本，留证据）与受控科研模式（审批冻结工作流版本 + 参数范围 + 输入约束，执行时校验匹配，改方法须重新审批）。
6. **L1–L4 分级证据标准**——Traceable / Re-executable / Computationally Reproducible / Scientifically Validated；承认 LLM 规划内容不可逐字复现，平台保证的是"方法、数据、工具行为可追溯 + 受控计算可按条件重放"。
7. **黄金案例验收基准**——一条真实 RNA-seq 端到端链（发现数据 → 接入登记 → 方法冻结审批 → Worker 执行 → BioReport → 交付 Manifest），作为以后所有架构迭代的固定回归基准。

## 11. 真正的分歧点（需要用户拍板的只有三处）

| # | 分歧 | 三方立场 | 融合建议 |
| --- | --- | --- | --- |
| D1 | project_members 时机 | A/B：纳入路线；我：先写死"刻意单所有者"再延后 | 阶段 0 在架构文档写死当前为刻意决策；角色体系排到阶段 6，与审批/执行分离可配置一起落地 |
| D2 | 回填机制怎么拆 | A：直接从 list/count 移除（改管理员 CLI）；我：隐藏目录重命名或 tombstone 二选一；B：软删除/tombstone，DB 为身份权威 | 先普查 `projects/{slug}` 路径的现存引用；大概率收敛为"tombstone/软删除 + 回填改为显式同步接口"，写副作用从读接口剥离 |
| D3 | 写执行开放的先后 | B 把证据闭环放 P1（激进）；A 放 P3（保守）；我居中 | 拆成两步：真实链"写路径试点"（阶段 2–3，隔离环境、只读/prepare 起步）远早于"完全写执行开放"（阶段 5，需预检 + 审批令牌 + 验收证据） |

## 12. 融合后的路线图（三方并集，顺序取交集）

| 阶段 | 内容 | 来源 |
| --- | --- | --- |
| 0 止血包 | 幽灵项目、设置回填、PATCH、status、文档漂移、能力状态端点 + 错误分型 | 三方 C3/C5/C8 |
| 1 只查不改调查 | Handoff 复现要素、落库点、审计事件、三重门置真前置、对账代码 | 我（A/B 的机制设计依赖它的事实） |
| 2 增量挂链 + 只读开放 | "会话即上下文、执行必挂链"契约；只读门开放与空状态验收 | A + 原报告 §8.2 |
| 3 存量转正 + Run 身份 | 显式认领 API / 对账队列；Run 物化入库；overview 索引化 | A + 我 + B（问题 1/7） |
| 4 导出闭环 | ZIP/SHA/授权/重试/撤权/恢复全链路验收；RO-Crate 导出映射 | 三方 + B |
| 5 受控写执行 | Handoff 预检协议 + 审批令牌门禁 + Provenance Event 协议 + FlowFrame 方法治理 | A + B |
| 6 团队与长期 | project_members 角色、审批/执行分离可配置、L1–L4 标准落地、黄金案例成为固定回归基准 | B + A |

## 13. 最终可以实现的效果（目标态）

把三方并集收敛成一句话：**项目管理从"项目空间管理"升级为"以可信科研运行和证据为中心的项目工作空间"**。具体可兑现为六件事：

1. **每一次 Agent 分析自动入籍**：项目绑定会话里发生的分析，自动获得 Run 身份、冻结输入版本、血缘记录——不再靠事后补录，增量 100% 进链。
2. **存量历史可合法转正**：226 个 Task、磁盘历史 runs 经显式认领（校验 manifest）进入血缘，全程可审计，绝不猜测归属。
3. **每张图都能反查**：从 BioReport 里任一张图/统计表，反查到数据版本、参数、容器镜像 digest、审批记录、执行者与 Attempt 轨迹。
4. **分级复现承诺**：L1 可追溯（证据关联完整）→ L2 可重执行（环境与方法快照）→ L3 计算可复现（确定性结果精确匹配）→ L4 科学验证（方法审核 + 独立验证）；LLM 规划部分诚实声明"可追溯但不逐字复现"。
5. **交付即可验证证据包**：冻结 Manifest + ZIP/SHA + 授权下载 + RO-Crate 映射，外部可核验、支持的环境下可重放。
6. **生命周期可信、协作可扩展**：删除不复活、改名不断链、DB 为身份权威；角色与审批/执行分离为未来课题组场景预留。

---

# Part III　Codex 施工提示词（三方融合版，2026-10-21 第二轮追加）

> 本 Part 的提示词取代 §4/§5 的旧版：阶段 0 融入 Agent A 的"读接口剥离写副作用 / JSON Merge Patch"与 Agent B 的"DB 为身份权威、写死单所有者决策"；阶段 1 融入 A 的会话挂链点/预检探针/审批令牌可行性与 B 的 Run 模型普查、事件基础设施现状。两份可同时下发（阶段 1 只读，与阶段 0 修复不冲突）。

## 14. 阶段 0 提示词（止血包，paste-ready）

```
任务：在现有 CygnusX 仓库上完成项目管理生命周期的止血修复包 + 一个项目能力状态端点与前端错误分型。先读现有代码再改，禁止推倒重写；不动任何科研功能开关（research_plan / research_delivery_read / research_delivery_write / project_export / project_report / tool_gateway / agent_analysis_write / agent_download_write 均保持现状），不改无关模块，不启用任何科研功能。

背景证据（来自 2026-10-21 只读调查报告，位置均已核实）：
1. 删除/回填冲突：delete_project 只删项目行与目录索引、保留物理目录；list/count 的 _backfill_from_disk 会为缺失 slug 重建项目——已删除项目可能在后续列表中"复活"。位置：src/cygnusx/application/services/project_service.py。
2. 科研模式开关不回填：frontend/src/views/ProjectDetailView.vue:39 附近，projectResearchDefault 初始 false、切换项目重置 false、加载 overview 后未从 settings 回填——已保存 true 刷新后显示关闭。
3. projects.status 允许 NULL 按 active 解释；现网 36 行全部 NULL；实际枚举为 active / completed / handed_over。
4. PATCH 只接受 status 与整体替换的 settings，无 name/description 修改入口；settings 整体替换有误覆盖其他键的风险。
5. 文档漂移：ARCHITECTURE_DESIGN/CygnusX_project_workspace_architecture.md 三处与源码不一致（status 枚举误写 archived/deleted；删除行为易被理解为删除物理目录，实际保留；run 发现误写为依赖命名正则/标记，实际接受所有非隐藏一级子目录，正则仅用于时间解析）。
6. 前端三卡片（ResearchPlanWorkbench / ResearchDeliveryChain / ProjectResearchDelivery）catch 所有失败显示统一"检查功能及权限"；ProjectDetailView.vue:555 只用 v-if="overview" 挂载。

施工要求：
A. 删除/回填冲突（最高优先）：
   1. 先普查代码库中所有按 projects/{slug} 路径引用的位置，交引用清单；
   2. 首选方案：数据库为项目身份唯一权威——项目表加软删除/tombstone（deleted_at 或独立 tombstone 表），list/count 的 _backfill_from_disk 跳过已删 slug，并把回填的隐式写从读接口剥离为显式同步入口（管理员 CLI 或专用端点）；物理目录保留不删；
   3. 若普查发现软删除方案有硬冲突，退回备选：删除时物理目录重命名为 .deleted-<slug>-<timestamp>（回填天然跳过隐藏目录）。说明取舍理由；
   4. 回归测试：创建→删除→list/count/刷新不再出现；既有带 runs 目录的项目行为不变；显式同步入口可正常回填真正缺失的目录。
B. 科研模式开关回填：加载项目详情/overview 后从 project.settings.research_mode.enabled 回填；切换项目按新项目已保存值重置。补组件测试（已保存 true 挂载后开关为开；切换到未开启项目为关）。
C. status 显式化：Alembic 迁移回填存量 NULL 为 'active'，列改 NOT NULL DEFAULT 'active'；读取侧 NULL 兼容分支保留一个版本并注明移除版本。
D. PATCH 扩展：支持 name/description 可选修改（slug 不变）；settings 改为局部合并（JSON Merge Patch 语义），禁止整对象覆盖丢失其他键；校验规则与创建一致；补测试。
E. 文档就地修订三处为源码事实，并在同文档显式补一句："项目当前为刻意单所有者模型，无 project_members 表是设计决策而非缺陷"。只改这几处，不重写整篇。
F. 能力状态端点 + 错误分型：
   - 后端 GET /projects/{id}/capability-status（或在 overview 响应内下发 feature_gates 字典，二选一说明取舍），返回当前用户视角 research_plan / research_delivery_read / project_export 三门的 {enabled, allowed, reason}；匿名 401、非 owner 403、owner 200；响应只含当前用户视角，不泄露系统配置细节；
   - 前端三卡片按 服务未启用 / 当前用户无权限 / 暂无数据 / 请求失败 四类分型展示，文案分别写清；服务未启用时降级为说明条，不再发起必然失败的请求；禁止继续合并成一句"检查功能及权限"。

验收（不接受只跑单测，每条给手测路径）：
- A：建测试项目→删除→多次刷新列表与 count→不复活；物理目录保留；显式同步入口验证一次。
- B/C/D/E/F：按上述要求逐条手测，交请求/响应或数据库行前后对照。
交付：每修复一段说明（根因→改法→文件:行号）+ 全部改动文件清单 + 测试输出；验收权在我，不接受自报通过。
```

## 15. 阶段 1 提示词（只查不改调查，paste-ready）

```
任务：只做代码级调查与评估，禁止修改任何代码、配置、数据库与文档；先读代码再下结论，所有结论标注 文件:行号 或 文件#函数名。不带证据位置的结论不予接受。

调查目标：为"agent 分析流程血缘写路径贯通 + 统一 Run 身份 + 受控写执行开放"做施工前调查。背景：主干链 Dataset → DatasetVersion / frozen Handoff → DatasetAnalysisLink → Task → 产物/Observation → 报告 已建模，但现网 Dataset 与 AnalysisLink 均为 0；93 个 chat_sessions 已有非空 project_id。

逐项核查清单：
1. 落库点与挂链点：agent 分析执行完整链路中，哪些位置已有或可以事务性创建 Dataset / DatasetVersion / Handoff / AnalysisLink？被 WRITE_RUNTIME_ACCEPTED / agent_analysis_write_enabled 挡住的半成品入口逐处列出。另：项目绑定会话（chat_sessions.project_id 非空）里触发分析/上传数据时，网关或调度层有没有可挂载"自动初始化/关联 DatasetVersion + 自动写 AnalysisLink"的现有调用点？
2. Handoff schema 复现要素核对（逐项判定 已固定/未固定 + 证据位置）：a. 输入数据版本哈希；b. 容器镜像 digest；c. 工具与参考数据库版本；d. 模型与 prompt 版本；e. 运行参数；f. 随机种子。
3. FileRegistry 是否内容寻址（SHA-256 或等同）？同一产物重复登记的行为？导出 ZIP 的 SHA 校验用的是哪层哈希？
4. 事件与审计现状：计划审阅/advance、导出创建/重试/下载、门禁拒绝分别有没有 append-only 审计记录，写在哪？现有 Celery outbox 模式是否在导出之外可复用（事务内写状态 + 异步投递的基础设施是否已存在）？
5. 三重门置真前置：WRITE_RUNTIME_ACCEPTED（agent_tool_gateway.py:47）与 worker_paths_verified=False 的代码/注释/测试/验收文档里写明的置真条件各是什么？另评估两个改造的可行性（只评估不实现）：a. 预检探针——用现有 Celery 基础设施在冻结 Handoff 时核验输入文件在 Worker 视角的可读性/大小/SHA，卡点在哪；b. 审批令牌——网关侧能否读取"该步骤对应 Plan 版本与 digest 已获 owner 批准"的状态，现有 plan review 数据是否足以支撑这个判定。
6. 已有 Run 模型普查：仓库与数据库中现存所有 Run 相关模型/表（计算 Task、数据库 Run、runs/ 目录等）逐个列出职责与关联字段——统一 ResearchRun 身份体系应优先复用哪个，避免新建重复系统。ProjectArchiveService 归档的 README/环境快照/manifest 在什么时机、由谁触发写入？
7. 对账：Beat 对账是否只覆盖导出 Job 恢复？有没有任何"磁盘 runs vs 血缘记录"的比对代码？

交付格式（写死，作为后续核对 checklist）：
1. 能力矩阵表：环节 × 是否已有代码 × 文件:行号 × 门禁。
2. Handoff 复现要素核对表。
3. 写路径链路图（文字版）：从"agent 分析执行完成"到"inventory 可见"每一跳，标注断点与门禁；另附"会话挂链"候选调用点。
4. 分级缺口清单：必须区分"刻意门禁"与"真缺失"。
5. 最小改动面估计：试点一条端到端血缘链 + Run 身份复用建议，只列位置与改动点描述，不写实现代码。
```
