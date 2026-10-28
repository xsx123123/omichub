# 阿里云 Skills 接入与 Skill 治理能力 实现计划

> 适用平台：OmicHub（Vue 3 + Naive UI / Arco Design，AI 配置中心 → 资源中心 → 技能）
> 目标读者：编码 Agent（kimi code / Claude Code / CODEX）与参赛方案撰写人
> 版本：v1.0（2026-08-01）

---

## 一、背景与目标

赛题要求："Skill 是本赛题必选项。参赛方案可使用阿里云官方用云 Skills，也可将关键能力沉淀为可复用 Skill。Skill 应作为任务能力抽象层，而不是只描述一次性的 Agent 行为。每个方案至少需提供核心 Skill 清单（名称、用途、输入与输出、调用条件、依赖工具、失败处理机制、安全边界、复用价值、与多 Agent 协同流程的关系）。"

平台现状（截图确认）：

- 「AI 配置中心 → 资源中心 → 技能」已支持 SKILL.md 标准技能管理，导入方式已有四种：**市场一键安装、GitHub 链接、zip 上传、JSON 粘贴**，导入前统一预览校验。
- 已入库技能：人/小鼠单细胞注释、植物单细胞注释（市场源，builtin://）、omichub-frontend-design（JSON 导入）。
- 技能市场弹窗已有：数据清洗、差异表达分析、人/小鼠单细胞注释、植物单细胞注释等条目，带安装/重新安装按钮。

本计划解决四件事：

1. **Part 1**：快速接入阿里云官方 Skills（零开发路径 + 一步开发路径 + 运行时打通）
2. **Part 2**：赛题合规的核心 Skill 清单与八要素说明（可直接写进参赛方案）
3. **Part 3**：Agent 调用 Skill 时的可视化提示（调用可观测）
4. **Part 4**：Skill 版本控制与一键回滚（治理闭环）

### 业界约定依据（评估 verdict 的锚点）

- 阿里云官方 Skills 即标准 SKILL.md 包，托管于 GitHub 仓库 `aliyun/alibabacloud-aiops-skills`，支持 `npx skills add` 安装与门户 ZIP 下载（https://skills.aliyun.com）。→ **与平台现有四种导入方式天然兼容，接入零门槛。**
- Claude Code 在 Skill 被调用时向用户渲染 `The "{name}" skill is loading` 可见消息，并提供 PreToolUse / PostSkillUse 等生命周期 Hook。→ **"调用时提示"是主流约定，方向正确。**
- skills CLI 用 `.skill-lock.json` 锁文件记录精确版本，支持 `skills check` / `skills update` / 指定版本回滚；企业级最佳实践为语义化版本 + 不可变快照 + 生产 pin 版本 + 升级前自动备份。→ **"版本控制 + 回滚"有成熟范式，直接借鉴即可。**

---

## 二、Part 1：快速接入阿里云 Skills（三条路径）

### 路径 A：零开发，用现有入口直接导入（今天就能做）

| 导入方式 | 操作步骤 | 适用场景 |
|---|---|---|
| ZIP 上传 | ① 访问 https://skills.aliyun.com → 搜索目标 Skill（如 `alibabacloud-resourcecenter-search`）→ 详情页点"安装引导"→ 切到"下载安装" tab → 下载 ZIP；② 平台「导入技能 → 本地上传」→ 选 ZIP → 预览校验 → 入库 | 网络可访问门户，单个导入 |
| GitHub 链接 | ① 复制仓库地址 `https://github.com/aliyun/alibabacloud-aiops-skills`（或具体 skill 子目录路径）；② 平台「导入技能 → GitHub」→ 粘贴链接、指定子目录与分支 → 预览校验 → 入库 | 需要锁定上游源、后续跟踪更新 |
| JSON 粘贴 | ① 打开 Skill 的 SKILL.md，复制 frontmatter + 正文；② 平台「导入技能 → JSON 粘贴」→ 粘贴 → 校验入库 | 快速试单条、离线环境 |

> 验收：入库后技能卡片显示名称/分类/版本（如 `alibabacloud-resourcecenter-search`，v1.0.0），来源标记为"阿里云官方"。

### 路径 B：技能市场内置"阿里云官方源"（一步开发，推荐）

在现有技能市场基础上新增一个市场源，让阿里云 Skills 像现有"数据清洗/差异表达分析"一样一键安装：

- 后端新增 `SkillSource` 类型 `aliyun-official`：定时（每日）拉取 `aliyun/alibabacloud-aiops-skills` 仓库的 skill 清单（GitHub API 或浅克隆），生成市场条目（名称、描述、分类、版本、更新时间、图标）。
- 市场弹窗加分组或 Tab：「平台内置」「阿里云官方」，阿里云条目带官方标识 badge。
- "安装"按钮行为 = 拉取该 skill 目录（SKILL.md + references/）→ 走现有预览校验流程 → 入库。
- 已安装的阿里云条目显示「检查更新」（对齐 `npx skills check` 语义），有更新时显示小红点，点击升级走 Part 4 的版本快照流程。

### 路径 C：运行时打通（让平台 Agent 真正能执行用云 Skills）

技能入库只是"挂载"，要执行阿里云的 Skill 还需运行时依赖，这部分涉及安全边界，按需开启：

- Agent 沙箱镜像预装：Node.js 18+、阿里云 CLI（≥3.3.3）。
- 凭证注入：通过平台「模型配置」侧的密钥管理机制注入 AK/SK 或 STS 临时凭证，**凭证只注入沙箱环境变量，不进对话上下文、不写日志**。
- 权限最小化：默认只授只读策略（如资源中心搜索只需 `AliyunResourceCenterReadOnlyAccess`）；写操作类 Skill（创建/修改/删除云资源）必须走人工确认（HITL）——在 Agent 执行链路中对写操作弹确认卡片。
- 服务开通检查：Skill 首次调用前执行预检（如 `aliyun sts get-caller-identity` 验证凭证、`aliyun resourcecenter enable-resource-center` 确认服务开通），预检失败给出可操作的修复提示而不是裸报错。

> 参赛建议：路径 A 当天完成用于演示，路径 B 作为开发任务落地，路径 C 只开通"资源搜索/诊断"等只读链路作为安全示范，写操作留给 HITL 流程图展示。

---

## 三、Part 2：赛题合规——核心 Skill 清单与八要素说明

以下清单可直接放入参赛方案。分两类：平台自研沉淀 Skill（对应"将关键能力沉淀为可复用 Skill"）与阿里云官方用云 Skill（对应"使用阿里云官方用云 Skills"）。所有 Skill 均遵循 SKILL.md 标准，作为**任务能力抽象层**被多个 Agent 复用，而非一次性提示词。

### 3.1 平台自研核心 Skill

#### S1 数据清洗（data-cleaning）

| 要素 | 说明 |
|---|---|
| 用途 | 表格数据（CSV/Excel）清洗、去重、缺失值处理、格式标准化与质量体检 |
| 输入 | 用户上传的表格文件 + 清洗要求（自然语言或规则）；输出 | 清洗后文件 + 质量体检报告（缺失率、重复行、类型分布） |
| 调用条件 | 用户上传表格数据并提出清洗/去重/标准化/质检诉求时由 Agent 自动匹配 |
| 依赖工具 | 沙箱 Python（pandas）、文件存储服务 |
| 失败处理 | 单步清洗失败回退到上一步快照；无法自动判定的列类型列出候选让用户确认；全部失败返回原始文件 + 失败原因 |
| 安全边界 | 只在沙箱内处理，文件不出用户空间；不执行文件内嵌公式/宏 |
| 复用价值 | 所有数据分析、生信上游任务的前置步骤，被多个分析 Skill 与 Agent 复用 |
| 多 Agent 协同 | 分析流水线中"数据工程 Agent"的入口能力，产物交付给下游差异分析/注释 Agent |

#### S2 差异表达分析（deg-analysis）

| 要素 | 说明 |
|---|---|
| 用途 | RNA-seq 表达矩阵（counts/TPM）+ 分组信息的差异表达分析、DEG 筛选、火山图/热图绘制 |
| 输入 | 表达矩阵 + 分组表 + 阈值参数（p 值、|log2FC|）；输出 | DEG 表 + 火山图/热图 + 统计摘要 |
| 调用条件 | 用户提供表达矩阵与分组信息并要求差异分析/筛 DEG/画火山图热图时触发 |
| 依赖工具 | 沙箱 R/Python（DESeq2 / edgeR / limma 或 pydeseq2）、绘图库 |
| 失败处理 | 矩阵校验（维度、重复样本名、非负整数检查）前置，校验失败给出具体行列定位；分组样本不足时拒绝并提示最小样本量 |
| 安全边界 | 只读输入文件，输出写入任务目录；不联网 |
| 复用价值 | 转录组类任务的标准分析件，参数化后可服务 bulk/scRNA 伪 bulk 多场景 |
| 多 Agent 协同 | 上游接数据清洗 Agent，下游为富集分析/注释 Agent 提供 DEG 清单 |

#### S3 人/小鼠单细胞注释（human-mouse-cell-annotation）

| 要素 | 说明 |
|---|---|
| 用途 | 基于人类或小鼠 scRNA-seq Cluster 的 FindMarkers 差异基因与 marker 参考表做细胞类型注释 |
| 输入 | FindMarkers 结果表 + marker 参考表 + 样本背景（物种、组织）；输出 | Cluster→细胞类型映射表 + 证据说明（命中 marker 列表）+ 置信度 |
| 调用条件 | 用户提供人/小鼠 scRNA-seq cluster 差异基因并要求细胞类型注释时触发 |
| 依赖工具 | marker 参考数据库（知识库）、沙箱统计环境 |
| 失败处理 | 低置信 cluster 标记为"待人工确认"并给出候选类型排序，不强行指派；物种/参考表不匹配时中止并提示 |
| 安全边界 | 仅使用平台知识库内参考数据；不修改原始表达数据 |
| 复用价值 | 单细胞分析通用件，参考表可扩展，跨项目复用 |
| 多 Agent 协同 | 注释 Agent 核心能力；产出供细胞互作、拟时序等下游 Agent 消费 |

#### S4 植物单细胞注释（plant-cell-annotation）

| 要素 | 说明 |
|---|---|
| 用途 | 植物 scRNA-seq cluster 差异基因 + marker 参考表 + 组织背景的细胞类型注释 |
| 输入/输出 | 同 S3，物种范围为植物（拟南芥、水稻等） |
| 调用条件 | 用户提供植物 scRNA-seq 差异基因并请求注释时触发 |
| 依赖工具 | 植物 marker 参考库 |
| 失败处理 / 安全边界 / 复用价值 / 协同关系 | 同 S3；与 S3 共用注释引擎，仅参考库与物种校验不同（引擎复用、知识分库） |

#### S5 omichub-frontend-design

| 要素 | 说明 |
|---|---|
| 用途 | OmicHub 科学工作台前端设计系统（Vue 3，Naive UI 与 Arco Design Vue 双组件库统一 token），约束页面、布局、仪表盘、表单、表格、空/加载/错误态、主题与动效的实现与评审 |
| 输入 | 页面/组件需求描述或待评审界面；输出 | 符合设计系统的实现规格或评审意见 |
| 调用条件 | 实现或评审 OmicHub 前端页面、迁移设计系统到其他 Vue 平台时触发 |
| 依赖工具 | 平台前端仓库、设计 token 文件 |
| 失败处理 | 组件库不支持的模式给降级方案；token 缺失时回退到默认色阶并记录待办 |
| 安全边界 | 仅产出样式/结构建议，不改业务逻辑与路由 |
| 复用价值 | 保证全平台 UI 一致性的横向能力，被所有前端开发 Agent 复用 |
| 多 Agent 协同 | 前端 Agent 的规范层 Skill，与功能实现类 Skill 组合使用 |

### 3.2 阿里云官方用云 Skill（排障链路示例）

四个 Skill 串联"资源搜索 → ECS 诊断 → 网络可达性分析 → 安全态势查询"排障链路，演示平台对官方 Skills 的编排能力：

| Skill 名称 | 用途 | 输入 → 输出 | 调用条件 | 依赖工具 | 失败处理 | 安全边界 | 复用价值 | 多 Agent 协同 |
|---|---|---|---|---|---|---|---|---|
| alibabacloud-resourcecenter-search | 全局云资源搜索与统计 | 地域/类型等条件 → 资源列表、分布统计 | 用户询问账号下云资源时 | 阿里云 CLI、资源中心服务 | 凭证失效/服务未开通给修复指引；空列表属正常返回 | 只读权限（AliyunResourceCenterReadOnlyAccess） | 一切用云任务的资源发现入口 | 排障链路第 1 步，产出实例 ID 给下游 |
| alibabacloud-ecs-diagnose | ECS 实例健康诊断 | 实例 ID → 诊断报告 | 获得目标实例后 | 阿里云 CLI、ECS API | 诊断项失败单列，不阻断其他项 | 只读诊断；不执行修复动作 | 实例层排障标准件 | 链路第 2 步 |
| alibabacloud-network-reachability-analysis | 网络可达性分析 | 源/目的 + 端口 → 路径可达性结论 | 怀疑网络链路问题时 | 阿里云 CLI、网络智能服务 | 路径不存在时给出排查清单 | 只读分析，不改安全组/路由 | 网络层排障标准件 | 链路第 3 步 |
| alibabacloud-sas-overview | 云安全中心安全态势查询 | 时间窗 → 告警与态势摘要 | 需要安全事件维度时 | 阿里云 CLI、SAS API | 无告警返回空并说明 | 只读查询 | 安全维度标准件 | 链路第 4 步，与前序结果汇合出结论 |

> 协同范式说明（可写进方案）：编排 Agent 接收复合任务（如"应用偶发超时，先诊断实例、再分析 80 端口可达性、最后查 24h 安全告警"）→ 依次调用 S 链路 Skills，前一 Skill 的输出（实例 ID、端口、时间窗）作为后一 Skill 的输入 → 汇总 Agent 生成定界结论。这正是"Skill 作为任务能力抽象层"的体现：每个 Skill 可独立复用，也可被编排进任意多 Agent 流程。

---

## 四、Part 3：Agent 调用 Skill 时的可视化提示

**Verdict：可以做，且与主流约定一致。** Claude Code 在 Skill 被调用时向用户渲染可见的加载消息，并提供 PreToolUse / PostSkillUse 生命周期 Hook；调用可见性是 Agent 平台的标配能力。你的平台按下面方案实现即可。

### 4.1 事件模型（后端）

在 Agent 执行链路中，Skill 匹配/加载/结束三个时机发出事件（SSE 或 WebSocket，复用现有会话推送通道）：

```json
// skill.invoked —— Skill 被匹配并加载时
{ "type": "skill.invoked", "task_id": "...", "agent": "注释Agent",
  "skill": { "id": "human-mouse-cell-annotation", "name": "人/小鼠单细胞注释",
             "version": "1.0.0", "source": "market" }, "ts": 1754064000 }

// skill.completed / skill.failed —— Skill 执行结束时
{ "type": "skill.completed", "task_id": "...", "skill_id": "human-mouse-cell-annotation",
  "duration_ms": 8200, "summary": "完成 12 个 cluster 注释" }
```

落库 `skill_invocation` 表（skill_id、version、agent、task_id、status、duration、ts），用于资源中心的"最近调用"展示与审计。

### 4.2 前端展示 spec（复用现有设计体系）

1. **会话流内：技能调用卡片**。在 Agent 消息流中插入一张卡片：技能图标 + 名称 + 版本 tag + 状态（加载中 spinner → 成功✓/失败✗）+ 耗时；可展开查看该 Skill 的用途摘要与本次输入摘要。风格对齐现有消息气泡，加载态只用 opacity/transform 动画，尊重 prefers-reduced-motion。
2. **轻提示**：首次调用某 Skill 时发一条 message 通知："Agent 正在使用技能「人/小鼠单细胞注释」v1.0.0"（可关）。
3. **资源中心技能卡片**：复用卡片上已有的时钟图标位，展示"最近调用：x 分钟前 · 累计 N 次"，点击弹出调用记录列表（时间、Agent、任务、状态、耗时）。

### 4.3 边界情况

- 同一会话多次调用同一 Skill：卡片合并为一条并显示次数，不刷屏。
- Agent 自主匹配但未实际加载成功（SKILL.md 缺失/版本被停用）：显示失败卡片并给"查看技能详情"入口。
- 技能被禁用/回滚中：Agent 侧回退到无 Skill 的通用流程，并在卡片上标注"技能不可用，已回退通用能力"。

---

## 五、Part 4：Skill 版本控制与一键回滚

**Verdict：可以做，直接借鉴成熟范式。** skills CLI 的 `.skill-lock.json` 锁版本 + `check/update` + 指定版本回滚，以及企业级实践的"语义化版本 + 不可变快照 + pin 生产版本 + 升级前自动备份"，组合落地如下。

### 5.1 版本数据模型

- `skill` 表：技能主档（id、名称、分类、来源、当前 active_version）。
- `skill_version` 表：**不可变快照**——每次导入/更新/回滚生成一条：semver 版本号、SKILL.md 全文与附件、内容 hash、来源 ref（市场/GitHub commit/ZIP 包名）、changelog、操作人、时间、状态（active / archived）。
- 版本号规则：语义化版本。市场源更新 = 跟随上游版本；手工编辑 = patch+1；frontmatter 的 description/触发条件变更 = minor+1（影响 Agent 匹配行为，视为不兼容增强）。

### 5.2 更新与回滚流程

1. **检查更新**：市场/GitHub 来源的技能定时比对上游 hash 或版本号，有更新在卡片显示红点（对齐 `npx skills check`）。
2. **升级**：点击升级 → 拉取新内容生成新版本快照 → active 指针切换 → 旧版本自动归档保留（**升级必留快照，这是回滚的前提**）。
3. **回滚**：技能卡片时钟图标 → 版本历史抽屉 → 列表展示各版本（版本号、时间、来源、changelog、"查看 diff / 回滚到此版本"按钮）→ 回滚 = active 指针切到旧快照，同时生成一条 rollback 审计记录（谁、何时、从 vX 回滚到 vY）。
4. **Agent 侧 pin**：会话启动时读取技能 active 版本并在整个会话内锁定（对齐 Claude Code"加载后持续有效"约定），会话中途升级不影响进行中的任务，新会话用新版本。

### 5.3 删除保护

被助手/AgentTeams 引用中的技能删除时二次确认，并提示引用方；删除仅删主档，版本快照保留 N 天可恢复（软删除）。

---

## 六、分阶段实现与编码 Agent 提示词

### 阶段 1：阿里云 Skills 导入与市场源（0.5–1 天）

- 验证路径 A 三种现有入口可导入阿里云 SKILL.md 包；开发路径 B 市场源。
- 验收：市场弹窗出现"阿里云官方"分组，`alibabacloud-resourcecenter-search` 可一键安装入库，卡片显示官方标识。

```text
你是一名资深全栈工程师。项目技术栈：Vue 3 + Naive UI / Arco Design Vue，AI 配置中心已有"资源中心 → 技能"模块（市场一键安装/GitHub/zip/JSON 四种导入 + 预览校验）。

任务：在现有技能市场基础上新增"阿里云官方"技能源。先阅读现有技能市场与导入相关代码（市场弹窗组件、技能入库接口、预览校验逻辑），复用现有组件与样式体系，禁止重构无关代码。

## 功能需求
1. 后端新增 SkillSource 类型 aliyun-official：定时同步 GitHub 仓库 aliyun/alibabacloud-aiops-skills 的 skill 清单（名称/描述/版本/更新时间），生成市场条目。
2. 市场弹窗新增"阿里云官方"分组（或 Tab），条目带官方 badge；安装 = 拉取该 skill 目录走现有预览校验入库。
3. 已安装条目显示"检查更新"，上游有新版本时显示红点。
4. 空态（同步失败/无网络）：显示"官方源暂不可用"占位，不影响平台内置条目。

## UI 要求
- 复用现有市场条目卡片样式与安装/重新安装按钮交互，风格与平台整体一致。

## 验收标准
- [ ] 阿里云官方分组正常列出条目，可一键安装
- [ ] 安装后技能卡片来源标识正确
- [ ] 官方源不可用时内置条目不受影响
```

### 阶段 2：Skill 调用提示（1 天）

```text
你是一名资深全栈工程师。项目技术栈：Vue 3 + Naive UI / Arco Design Vue，平台 Agent 会话通过 SSE 推送消息流。

任务：实现 Skill 调用可视化提示。先阅读 Agent 执行链路与会话消息流渲染代码，复用现有 SSE 通道与消息气泡组件，禁止重构无关代码。

## 功能需求
1. 后端：Skill 匹配/加载/结束三个时机发 skill.invoked / skill.completed / skill.failed 事件（含 skill id、名称、版本、来源、agent、task_id、耗时），并落库 skill_invocation 表。
2. 前端会话流：插入技能调用卡片（图标+名称+版本 tag+状态+耗时，可展开看用途摘要）；同一 Skill 多次调用合并显示次数。
3. 首次调用发一条可关闭的 message 通知。
4. 资源中心技能卡片展示"最近调用时间 · 累计次数"，点击看调用记录列表。
5. Skill 加载失败/被禁用：显示失败卡片，Agent 回退通用流程并标注。

## UI 要求
- 卡片风格对齐现有消息气泡；加载动画只用 opacity/transform，尊重 prefers-reduced-motion。

## 验收标准
- [ ] 三类事件在会话流正确渲染状态流转
- [ ] 多次调用合并、失败/禁用回退提示正确
- [ ] 资源中心调用记录可查
```

### 阶段 3：版本控制与回滚（1–1.5 天）

```text
你是一名资深全栈工程师。项目技术栈：Vue 3 + Naive UI / Arco Design Vue，技能模块已有入库/启停/删除。

任务：为技能模块加版本控制与一键回滚。先阅读技能入库与更新相关代码，禁止重构无关代码。

## 功能需求
1. 新增 skill_version 不可变快照表：semver、SKILL.md 全文与附件、内容 hash、来源 ref、changelog、操作人、时间、状态(active/archived)。
2. 导入/市场升级/手工编辑均生成新快照；升级前旧版本自动归档。
3. 技能卡片时钟图标 → 版本历史抽屉：版本列表 + diff 查看 + "回滚到此版本"；回滚生成审计记录。
4. Agent 会话启动 pin 当前 active 版本，会话内不随升级变化。
5. 删除保护：被引用的技能删除需二次确认，快照软删除保留可恢复。
6. 版本号规则：上游更新跟随上游版本；手工编辑 patch+1；description/触发条件变更 minor+1。

## 验收标准
- [ ] 升级后旧版本可查看 diff、可一键回滚，回滚有审计记录
- [ ] 进行中会话不受升级影响
- [ ] 被引用技能删除有二次确认
```

### 阶段 4：赛题文档输出

将本文 Part 2 的八要素清单 + Part 3/4 的治理能力截图（调用卡片、版本历史抽屉）整理进参赛方案的"Skill 体系"章节。

---

## 七、风险与回退

| 风险 | 应对 |
|---|---|
| GitHub 官方源同步失败（网络） | 保留 ZIP 上传与 JSON 粘贴兜底；市场分组显示"暂不可用"不阻塞内置条目 |
| 阿里云 Skill 执行依赖凭证与 RAM 权限 | 路径 C 默认只开只读链路；写操作一律 HITL 确认；凭证只注入沙箱环境变量 |
| 版本快照存储膨胀 | SKILL.md 为文本，快照量小；附件去重（按内容 hash 存一份） |
| 升级导致 Agent 匹配行为变化 | description 变更强制 minor 版本 + changelog 必填；生产会话 pin 版本 |
| 调用事件打断会话流阅读 | 卡片默认收起摘要，合并重复调用，通知可关闭 |

---

## 参考来源

[^1^]: 阿里云帮助文档《快速使用阿里云Skills》https://help.aliyun.com/zh/skillsportal/quickly-use-alibaba-cloud-skills
[^2^]: 阿里云 Agent Skills 门户 https://skills.aliyun.com/
[^3^]: 阿里云 EMR 文档：使用 Agent Skills 管理实例（Claude Code/OpenClaw 安装与更新）https://help.aliyun.com/zh/emr/emr-serverless-starrocks/getting-started/use-emr-starrocks-agent-skills
[^4^]: antfu/skills-cli（npx skills 命令参考：list/check/update/lock）https://github.com/antfu/skills-cli
[^5^]: Claude Code Skills 指南（Skill 加载消息、frontmatter、生命周期）https://www.claudecode.xyz/articles/claude-code-skills-moz440iw
[^6^]: Versioning Agent Skills: SemVer, Compatibility, Deprecation https://aiquinta.ai/blog/versioning-agent-skills-semver-compatibility-deprecation/
[^7^]: codebase-index CHANGELOG（skill-update / skill-rollback 备份恢复实践）https://github.com/denfry/codebase-index/blob/main/CHANGELOG.md
[^8^]: Microsoft Agent Framework Skills 安全最佳实践（审计与日志）https://learn.microsoft.com/en-us/agent-framework/agents/skills

---

## 八、实现记录（2026-08-01 落地）

### 阶段 1：阿里云官方技能市场源 ✅

- **后端**：`SkillImportService` 新增官方源同步（`sync_aliyun_marketplace`）、状态（`aliyun_status`）、安装（`install_aliyun`）；`list_marketplace` 合并内置 + 阿里云两分组；`check_update` 支持 `aliyun_official`（优先比对本地 manifest commit，零网络）。
- **同步机制**：整仓 codeload tar.gz 单次拉取 → 结构无关扫描（任意深度的 `*/SKILL.md` 目录均识别）→ 落运行时可写缓存目录 `/data/omichub/skill_marketplace_aliyun/`（技能文件夹 + `manifest.json`）；上游 commit 未变幂等跳过；配置分支不可用自动回落默认分支（该仓库实为 `master`）；失败保留旧缓存 + 记录 `last_error`。
- **API**：`GET /admin/skills/marketplace/aliyun/status`、`POST /admin/skills/marketplace/aliyun/sync`、`POST /admin/skills/marketplace/aliyun/{skill_id}/install`。
- **前端**：市场弹窗拆「平台内置 / 阿里云官方」两组，官方条目带「官方」badge、同步时间、过期红点与手动同步按钮；未同步/不可用有占位空态；首次打开自动首同步；安装按 source 路由。
- **迁移**：`e9f0a1b2c3d4` 放宽 `skills.skill_id` / `skill_versions.skill_id` 至 varchar(100)（官方技能 ID 可达 57+ 字符）。
- **实测**：真同步 `aliyun/alibabacloud-aiops-skills`（1 个技能，含 SKILL.md + references/ + scripts/）→ 一键安装 → source/commit 落库 → 检查更新「已是最新」→ 覆盖升级留 r2 快照，全链路通过。

### 阶段 2：Skill 调用可视化 ✅

- **后端**：`use_skill`（L2 加载）三时机发 `ChatChunk(type="skill")`：`invoked` → `completed`/`failed`（含 duration_ms/summary/error/agent）；落库 `skill_invocations` 表（迁移 `f0a1b2c3d4e5`），落库失败只记日志不阻断对话。
- **API**：`GET /admin/skills/invocation-stats`（聚合：累计次数 + 最近调用 + 末次状态，PG DISTINCT ON）、`GET /admin/skills/{skill_id}/invocations`。
- **前端**：`useAgentChatStream` 新增 `onSkill` 回调；会话流内 `SkillInvocationCard`（spinner → ✓/✗ + 耗时，可展开 ID/摘要/错误，同技能多次调用合并计数，动画仅 opacity/transform 且尊重 prefers-reduced-motion），按 timeline 交错插入正文流；首调轻提示（localStorage 去重，可关）；资源中心技能卡片展示「最近调用 x · 累计 N 次」，点击看调用记录表。

### 阶段 3：版本控制与回滚治理 ✅（原有快照/历史/回滚基础上补全）

- **diff**：新增 `GET /{skill_id}/versions/{revision}` 版本快照详情；版本历史抽屉每行加「对比」按钮 → LCS 行级 diff 弹窗（增/删着色）。
- **会话 pin**：会话首轮把挂载技能的活跃 revision 快照进 `sandbox_meta.skill_pins`；`use_skill` 优先读取被 pin 的快照正文（手写循环与 LangGraph 两条执行路径均已穿透），会话中途升级不影响进行中任务，新会话用新版本。
- **删除保护**：`GET /{skill_id}/references`（JSONB 包含查询，兼容 json 列 cast）；删除被引用技能需 `?force=true` 二次确认（前端 dialog 列出引用助手）；主档删除后版本快照保留（软删除语义，实测 4 份快照留存）。
- **版本号规则**：手工更新自动 bump——description 变更 = minor+1（影响 Agent 匹配），其他内容 = patch+1；上游导入跟随上游版本；实测 1.2.3 →（改正文）1.2.4 →（改描述）1.3.0。
- **顺手修复的既有 bug**：`skill_service` 变异方法（update/rollback/toggle）flush 后缺 `db.refresh`，服务端 onupdate 列过期后在 asyncio 下触发 MissingGreenlet。

### 验收对照

| 计划验收项 | 状态 |
|---|---|
| 阿里云官方分组列出条目、一键安装、来源标识 | ✅ E2E 实测 |
| 官方源不可用时内置条目不受影响 | ✅ 失败保留缓存 + 分组独立 |
| 三类事件会话流状态流转 / 多次调用合并 / 失败回退提示 | ✅ 代码落地（事件/卡片/合并/fallback 标注） |
| 资源中心调用记录可查 | ✅ stats + records API + UI |
| 升级后 diff / 一键回滚 / 回滚审计 | ✅ diff 弹窗 + 既有回滚 + rollback 快照 |
| 进行中会话不受升级影响 | ✅ skill_pins |
| 被引用技能删除二次确认 | ✅ references + force |
