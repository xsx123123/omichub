# OmicHub AI 分析工作台（OmicStudio）架构设计

> 版本：v1.0 · 2026-07-17
> 定位：在 OmicHub 中新增「AI 协助下的交互式数据分析模块」，融合 Biomni 任务式工作台交互、LiveAgent 分层 Agent 架构、VS Code 式「代码可编辑可运行」的人机回环，与用户数据、平台内置流程、已有 MCP & Skill 体系全面联动，运行环境基于 Docker Swarm 容器沙盒。

---

## 一、背景与目标

### 1.1 要解决的核心问题

平台现有的分析流程（RNA-seq、ATAC-seq、组学绘图工坊、生信工具箱）是「参数表单 → 固定流程 → 固定报告」的模式。当用户对结果不满意时（图不好看、阈值想换、想加一个分析步骤），现有体系没有出口，只能离开平台自己写代码。

**AI 分析工作台就是这个出口**：用户可以在 AI 协助下，对平台工具产出的结果进行诊断、复现、修改与再分析；也可以从零开始，对话式地完成一次自由数据分析。全程代码可见、可改、可重跑，运行在与平台物理隔离的容器沙盒中。

### 1.2 三个参考对象，各取什么

| 参考对象 | 取用点 | 取用什么 |
| --- | --- | --- |
| **Biomni**（网页版 + A1 Agent） | 交互形态 + Agent 模式 | 任务式三栏工作台（任务/云盘 \| 对话执行流 \| 结果/待办）；「检索增强规划 + 代码执行」的 Agent 范式；Know-How Library ≈ 我们的 Skills |
| **LiveAgent** | 工程架构 | 模型协议层 / Agent Loop / 工具资源层（FS+Bash+MCP+Skills）/ UI 的四层解耦；Skills 渐进式披露；工具循环的流式 UI 呈现 |
| **VS Code + Qoder/Codex** | 人机回环 | 代码编辑器内嵌、AI 生成代码 → 用户手改 → 一键重跑 → 结果对比的工作流 |

**不取什么**：Biomni 本地版「LLM 代码直接全权限跑在宿主机」的模式坚决不要——其官方也明确警告生产环境必须沙盒隔离；我们直接走容器沙盒路线。

### 1.3 设计原则

1. **复用优先**：Agent Runner、多智能体 yaml 配置、MCP 注册、Celery 任务、Docker Swarm 沙盒、NFS 存储全部复用现有设施，新模块是「现有能力的一种新编排」，不是另起炉灶。
2. **yaml 配置驱动**：工作台的智能体、工具集、沙盒镜像、资源限额全部 yaml 声明，与平台现有风格一致。
3. **数据不搬家**：用户数据以只读挂载/软链方式进入沙盒，产物登记回结果报告中心，全程不产生数据孤岛。
4. **代码透明**：AI 写的每一行代码对用户可见、可编辑、可重跑——这是与「黑盒 AI 问答」的本质区别，也是 VS Code 式体验的核心。

---

## 二、模块定位与命名

建议命名 **OmicStudio（AI 分析工作台）**，在平台导航中与「AI 助手」平级、互为入口：

- **AI 助手（多智能体对话）**：轻量问答、咨询、文案，不产生文件产物；
- **OmicStudio（AI 分析工作台）**：重活——有任务、有文件、有代码、有结果产物的完整分析会话。

两者的关系：OmicStudio 的每个会话**必须绑定一位智能体**（通用助手 / 可视化助手 / RNA-seq 分析师 / 代码助手 / 傻妞……），复用现有多智能体页面作为「工作台入口」——从助手卡片点击「进入工作台模式」即创建一个绑定该智能体的 Studio 会话。傻妞的人格设定在 Studio 场景下天然契合（她本来就擅长数据分析）。

---

## 三、总体架构

```
┌──────────────────────────────────────────────────────────────────┐
│ 前端 · OmicStudio 工作台（Vue3 + Arco Design + Monaco Editor）      │
│ ┌────────────┬──────────────────────────────┬─────────────────┐  │
│ │ 左栏        │ 中栏                          │ 右栏             │  │
│ │ · 任务会话   │ · 对话执行流（思考/计划/工具/代码）│ · 结果产物      │  │
│ │ · 工作台文件 │ · 代码编辑器（Tab/抽屉，Monaco）│ · 待办计划      │  │
│ │   （云盘）   │ · 运行控制（运行/停止/重跑）     │ · 沙盒环境状态   │  │
│ └────────────┴──────────────────────────────┴─────────────────┘  │
├──────────────────────────────────────────────────────────────────┤
│ 后端 · Studio Gateway（FastAPI + WebSocket/SSE）                   │
│ ┌────────────────┬───────────────────┬────────────────────────┐  │
│ │ Session Manager│ Agent Runner      │ Tool Registry          │  │
│ │ 会话/上下文/历史 │ 多轮工具循环        │ 内置工具 + MCP + Skills │  │
│ ├────────────────┼───────────────────┼────────────────────────┤  │
│ │ Sandbox Manager│ Artifact Service  │ Context Packager       │  │
│ │ Swarm 容器生命周期│ 产物登记→结果报告中心│ 流程结果→会话上下文打包 │  │
│ └────────────────┴───────────────────┴────────────────────────┘  │
│   长任务卸载 → Celery（复用任务中心）                               │
├──────────────────────────────────────────────────────────────────┤
│ 执行层 · 沙盒容器（Docker Swarm，每会话一个实例）                    │
│ ┌──────────────────────────────────────────────────────────────┐ │
│ │ omichub-sandbox 镜像（分层：base / bio / full）                 │ │
│ │ · Python 3.12 + pandas/scanpy/scikit-learn/matplotlib/plotly │ │
│ │ · 可选 R + 生信 CLI（blast/samtools/bedtools…）               │ │
│ │ 挂载：/workspace（NFS，读写）· /data/user（只读）· /ref（只读） │ │
│ │ 限制：CPU/内存/超时/网络白名单/非 root                         │ │
│ └──────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
```

### 与 LiveAgent 四层架构的对应

| LiveAgent 层 | OmicStudio 对应 | 说明 |
| --- | --- | --- |
| 模型协议层 | 现有模型路由（qwen3.7-max/plus 等） | 直接复用，不新增 |
| 多轮执行层 | Agent Runner | 在现有智能体 runner 上扩展「工作台工具集」即可，不要重写 loop |
| 工具资源层 | Tool Registry（内置 FS/Bash 工具 + MCP + Skills） | Skills 渐进式披露照搬现有实现 |
| UI 层 | OmicStudio 前端三栏 | 新增 |

---

## 四、前端设计

### 4.1 页面布局（对标 Biomni 网页版，按 OmicHub 审美重做）

```
┌────────────────────────────────────────────────────────────────────┐
│ 顶栏：会话名 / 绑定智能体徽章 / 模型选择 / 沙盒状态灯 / 分享·导出      │
├──────────┬──────────────────────────────────────┬──────────────────┤
│ 会话列表  │ 对话执行流                            │ 结果产物          │
│ ──────── │  💭 思考中…（可折叠）                  │  📄 volcano.png  │
│ · 今日    │  📋 计划（6 步，checkbox 联动待办）    │  📄 de_table.csv │
│ · 更早    │  🔧 工具调用卡片（sandbox_execute）    │  📄 report.md    │
│ ──────── │  ┌──────────────────────────────┐    │ ────────────────│
│ 工作台文件 │  │ ▶ code_cell_3.py   [编辑][重跑]│    │ 待办计划         │
│ 📁 input/ │  │ import pandas as pd …        │    │ ☑ 加载数据      │
│ 📁 output/│  └──────────────────────────────┘    │ ☑ 差异分析      │
│ 📁 ref/   │  ✏️ AI 修改了 volcano_plot.py（diff） │ ☐ 火山图重绘    │
│ [+从数据   │  ────────────────────────────────    │ ────────────────│
│  管理引入] │ 输入框 [附件] [引用平台文件] [发送]    │ 沙盒：运行中 🟢  │
│           │                                      │ py3.12 · 2C4G   │
└──────────┴──────────────────────────────────────┴──────────────────┘
```

**关键交互细节**：

1. **代码卡片即编辑器入口**：AI 生成的每段代码以卡片形式呈现在对话流中（语法高亮 + 行号），点击「编辑」展开 Monaco 内联编辑（或全屏抽屉），用户改完点「重跑」直接在沙盒执行——这就是 VS Code 回环的轻量版，不需要真的做一个 IDE。
2. **diff 呈现**：AI 修改已有文件时，用 diff 视图展示改动（参照 LiveAgent 的 `@git-diff-view` 思路，Vue 侧可用 `diff2html`），用户可「接受 / 拒绝 / 手动再改」。
3. **执行过程流式**：工具调用的 stdout/stderr 通过 WebSocket 逐行推到卡片下方，长时间运行折叠为「运行中 · 已输出 N 行 · 点击展开」。
4. **结果产物面板**：沙盒 `/workspace/output` 目录的实时镜像，图片可直接预览（lightbox），表格可预览前 50 行，每个产物带「登记到结果报告中心」「下载」「插入对话引用」三个动作。
5. **沙盒状态灯**：🟢 运行中 / 🟡 启动中 / ⚪ 已回收（再发消息时自动拉起，对用户透明）。
6. **右栏可整体收起**，收起后中栏对话流扩展为宽屏，方便看代码。

### 4.2 与现有「AI 助手」页面的关系

现有助手卡片页增加一个切换：**「对话模式 | 工作台模式」**（卡片右上角或进入后切换）。对话模式保持现状；工作台模式即跳转 `/studio/:sessionId`。历史会话列表合并展示，Studio 会话带一个 📊 角标。

---

## 五、后端设计

### 5.1 模块划分

| 模块 | 职责 | 复用/新增 |
| --- | --- | --- |
| Session Manager | 会话 CRUD、上下文持久化（对话历史 + 文件清单 + 沙盒句柄）、会话恢复 | 在现有助手会话表上扩展 `mode: chat \| studio`、`workspace_id`、`sandbox_id` |
| Agent Runner | 多轮工具循环（assistant → tool_call → tool_result → …），流式事件输出 | **复用**现有智能体 runner，注入 Studio 工具集 |
| Tool Registry | 工具注册与分发：内置工具、MCP 工具、Skills | 复用现有 MCP/Skill 体系，新增内置工具组 |
| Sandbox Manager | 沙盒容器的创建、保活、回收、执行代理、资源审计 | 基于现有 Docker Swarm 沙盒能力扩展 |
| Artifact Service | 产物扫描、缩略图/预览、登记到结果报告中心 | 新增，对接现有结果中心表 |
| Context Packager | 「从流程结果发起优化」时的上下文打包 | 新增 |

### 5.2 Studio 内置工具集（注入 Agent Runner）

Agent Runner 的工具 = 现有 MCP 工具 + 现有 Skills + 以下内置工具：

| 工具 | 说明 | 备注 |
| --- | --- | --- |
| `sandbox_execute` | 在沙盒执行代码：`{language: python\|r\|bash, code, timeout}`，流式返回 stdout/stderr/exit_code/产物清单 | 核心工具 |
| `workspace_write` | 写文件到 `/workspace`（新建/覆盖） | AI 生成脚本用 |
| `workspace_edit` | 精确文本替换（old_string/new_string），返回 diff | 对应 LiveAgent 的 Edit |
| `workspace_read` | 读文件，分页 | |
| `workspace_list` | 列目录，含文件元信息 | |
| `datahub_import` | 从「数据管理」引用文件：`{file_id}` → 在 `/workspace/input/` 建软链 | **数据不搬家** |
| `platform_result_import` | 从「结果报告中心」引用产物：下载链接/软链 + 元数据（来源流程、参数、日志） | 流程联动核心 |
| `artifact_register` | 把 `/workspace/output/*` 登记为结果报告：`{path, title, type, description}` | 回填平台 |
| `pipeline_query` | 查询平台内置流程/工具的说明文档与参数 schema（只读） | 让 AI 知道平台有什么 |

> Skills 的处理与现有体系一致：系统提示中只放 skill 元数据清单，模型按需 `read_skill` 加载全文（渐进式披露）。

### 5.3 流式协议（WebSocket 事件类型）

```
session.status     会话状态（沙盒启动中/就绪/回收）
agent.thinking     思考流（delta）
agent.plan         计划生成/更新（同步右栏待办）
tool.call          工具调用开始（工具名 + 参数）
tool.output        工具输出流（stdout/stderr delta）
tool.result        工具完成（exit_code + 产物清单）
file.changed       工作区文件变更（create/update/delete + diff）
artifact.new       新产物登记
agent.message      助手消息（delta）
agent.done / agent.error
```

---

## 六、沙盒容器设计

### 6.1 镜像分层

```
omichub-sandbox:base        # python:3.12-slim + pandas/numpy/matplotlib/plotly/seaborn
                            # + scikit-learn/scipy/statsmodels + openpyxl/pyarrow
omichub-sandbox:bio         # base + scanpy/anndata/scanpy/pysam/bioinfokit
                            # + blast+/samtools/bedtools/seqkit（CLI）
omichub-sandbox:full        # bio + R 4.x（r-base + tidyverse + ggplot2，via conda 或 apt）
```

- 默认用 `bio`；`full` 体积大，仅当智能体 yaml 声明 `needs_r: true` 时使用。
- 镜像内预装一个 **sandbox-agent 小服务**（HTTP，`/exec` `/files/*`），Sandbox Manager 通过它与容器交互，不要在宿主上 `docker exec` 拼字符串。
- 统一非 root 用户（uid 10001），只读根文件系统，`/workspace` 单独可写。

### 6.2 生命周期

| 阶段 | 行为 |
| --- | --- |
| 创建 | 会话首次发送消息时拉起（懒启动），Swarm service 名 `studio-{session_id[:8]}`，前端显示 🟡 |
| 保活 | 每次执行心跳续约；空闲 30 min 自动回收（service scale 0 / remove） |
| 恢复 | 回收后再发消息 → 重新拉起同镜像容器，**`/workspace` 在 NFS 上持久**，用户无感 |
| 销毁 | 会话删除时清理 service；`/workspace` 保留 7 天后清 |
| 长任务 | 单次 `sandbox_execute` 超 10 min → 转 Celery 投递（复用任务中心），完成后事件回推会话 |

### 6.3 挂载与数据流

| 容器路径 | 来源 | 权限 | 说明 |
| --- | --- | --- | --- |
| `/workspace` | NFS `/data/omichub/studio/{session_id}/` | 读写 | 会话工作区，AI 和用户共享 |
| `/workspace/input` | 软链 → 数据管理文件 | 只读 | 经 `datahub_import` 建立 |
| `/workspace/ref` | NFS `/data/omichub/reference/`（NT/NR、基因组等） | 只读 | 复用现有参考库 |
| `/workspace/output` | — | 读写 | 约定产物目录，Artifact Service 监听 |

### 6.4 安全红线

1. 网络白名单：默认**全断网**；仅按 yaml 显式放行（如 pypi、NCBI）。数据库类 MCP 走平台侧代理，不经沙盒网络。
2. 资源限额：默认 2C/4G/单任务 10 min，yaml 可按智能体上调；超限强杀并回报。
3. 沙盒内**没有任何平台密钥**：LLM API key、数据库凭据只存在于 Gateway，沙盒对平台内网不可达（Swarm overlay 网络隔离，复用现有物理隔离思路）。
4. 文件逃逸防护：`workspace_*` 工具所有路径归一化后必须落在 `/workspace` 内；软链解析后同样校验。
5. 审计：每次 `sandbox_execute` 的代码、输出、产物落审计日志（含用户、会话、耗时），方便事后追溯。

---

## 七、平台联动设计（本模块的灵魂）

### 7.1 与「数据管理」联动

- 工作台左栏「+ 从数据管理引入」打开平台文件选择器（复用现有组件），选中后调 `datahub_import` 建软链，对话中 AI 立即可见文件路径。
- 用户也可以直接在输入框粘贴/上传文件，落到 `/workspace/input/uploads/`。

### 7.2 与「内置流程 & 结果报告中心」联动 —— 一键优化（核心场景）

**触发入口**：结果报告中心每个报告增加按钮「在 AI 工作台中优化」；组学绘图工坊每张图增加「用 AI 继续调整」。

**Context Packager 打包内容**（创建 Studio 会话时作为系统上下文注入）：

```yaml
context_pack:
  source:
    pipeline: rnaseq_deseq2          # 来源流程
    run_id: task_20260716_xxxx
    params: {...}                    # 用户当时的参数
    report_id: rpt_xxxx
  files:                             # 软链进 /workspace/input/
    - {path: de_result.csv, role: 差异分析结果表}
    - {path: volcano.png, role: 当前火山图}
    - {path: run.log, role: 流程日志}
  hint: 用户对上述结果不满意，希望在你的协助下诊断并改进。
        可复现、可修改、可重跑，产物可登记为新版本报告。
```

AI 进入会话即知：这是什么流程跑出来的、参数是什么、结果文件在哪、日志有没有报错。**优化完成后**，用户点「保存为新版本」→ `artifact_register` → 结果报告中心生成 `v2` 报告，并回链到原报告（版本树）。

### 7.3 与 MCP & Skills 联动

- Studio 会话的工具面 = `studio_tools`（内置）+ 该智能体 yaml 里已声明的 `mcp` + `skills`，**零新增配置**。
- 反过来，Studio 里沉淀出的好用脚本，管理员可一键「提炼为 Skill」：把脚本 + 说明打包进 Skills 目录，下次任何智能体都能调用——形成「AI 帮用户改 → 改完沉淀为平台能力」的飞轮。

### 7.4 与「任务中心 / 流程监控」联动

- 沙盒内长任务（如全基因组扫描）转 Celery 后，任务中心出现对应记录（类型 `studio_sandbox`），完成/失败回推会话。
- 流程监控页能看到沙盒容器资源占用（与现有 Swarm 监控同源）。

### 7.5 与「实验室知识库」联动（可选增强）

`pipeline_query` 之外，可加 `knowledge_search` 工具，让 AI 在改代码时引用知识库里的流程文档/FAQ，回答更有平台语境。

---

## 八、核心场景流程

### 场景 A：流程结果不满意 → AI 协助优化（P0 必做）

1. 用户在结果报告中心看 RNA-seq 火山图，觉得配色和阈值线不对 → 点「在 AI 工作台中优化」；
2. 系统创建 Studio 会话（绑定可视化助手），Context Packager 注入结果文件 + 参数 + 日志；
3. AI 读取 `de_result.csv`，复现火山图（`sandbox_execute`），解释当前图的问题；
4. AI 生成修改版 `volcano_v2.py`（新配色、阈值线、标注基因）→ 执行 → 右栏产物面板出现新图；
5. 用户点开代码卡片，把某个基因标注颜色手动改掉 → 「重跑」→ 3 秒后新图刷新；
6. 满意 → 「保存为新版本」→ 结果报告中心出现 `火山图 v2`，挂回原报告版本树。

### 场景 B：自由数据分析（P1）

用户上传自己的表达矩阵 → 对话「帮我看看这批样本的聚类情况，顺便找找离群样本」→ AI 出计划（待办面板）→ PCA + 层次聚类 → 产物面板出图 → 用户追问「把离群的 S12 去掉重画」→ 迭代 → 最终登记报告。

### 场景 C：工具结果二次分析（P1）

BLAST 结果页 →「在 AI 工作台中打开」→ AI 读取结果 XML/表格 → 按用户要求筛选、注释、出图 → 可再调平台 MCP 工具（如 JBrowse 定位）交叉验证。

---

## 九、yaml 配置示例

```yaml
# config/studio.yaml
studio:
  enabled: true
  default_image: omichub-sandbox:bio
  session:
    idle_ttl_minutes: 30
    workspace_retention_days: 7
  sandbox:
    cpu: 2
    memory: 4g
    exec_timeout_seconds: 600
    network:
      mode: whitelist
      allow: [pypi.org, files.pythonhosted.org, ftp.ncbi.nlm.nih.gov]
    mounts:
      workspace: /data/omichub/studio
      reference: /data/omichub/reference
  tools:
    builtin: [sandbox_execute, workspace_write, workspace_edit,
              workspace_read, workspace_list, datahub_import,
              platform_result_import, artifact_register, pipeline_query]
  images:
    base: {dockerfile: docker/sandbox/base.Dockerfile}
    bio:  {dockerfile: docker/sandbox/bio.Dockerfile}
    full: {dockerfile: docker/sandbox/full.Dockerfile, needs_r: true}

# 智能体侧：在现有 agents yaml 中为每个智能体追加
agents:
  visualization_assistant:
    studio:
      enabled: true
      image: omichub-sandbox:base
      extra_skills: [plotly-best-practice, matplotlib-style]
  rnaseq_analyst:
    studio:
      enabled: true
      image: omichub-sandbox:bio
      sandbox: {cpu: 4, memory: 8g}     # 按需上调
```

---

## 十、分阶段实施计划

| 阶段 | 内容 | 验收标准 | 预估 |
| --- | --- | --- | --- |
| **P0 骨架** | sandbox-agent 小服务 + base/bio 镜像；Sandbox Manager；`sandbox_execute` + 4 个 workspace 工具；最简 Studio 页（对话流 + 代码卡片可编辑可重跑 + 产物列表） | 会话里 AI 能写 pandas 代码跑通、用户能改代码重跑、产物出现在右栏 | 1.5 周 |
| **P1 联动** | 数据管理引入；结果中心「一键优化」+ Context Packager + 版本回填；待办计划面板；智能体 yaml 接入 | 场景 A 全流程走通 | 1.5 周 |
| **P2 体验** | diff 视图；长任务转 Celery；沙盒状态灯与自动回收；MCP/Skill 全量接入；产物预览增强 | 场景 B/C 走通，空闲沙盒自动回收 | 1 周 |
| **P3 打磨** | 会话分享/导出 PDF 报告；「提炼为 Skill」；知识库联动；配额与用量统计接入 | 与现有用量统计页打通 | 1 周 |

**关键风险与对策**：

1. *沙盒启动慢*（镜像大）→ 镜像预拉取到各 Swarm 节点 + 保 1 个预热池，启动控制在 5s 内；
2. *AI 写的代码死循环/超内存* → 硬超时 + 资源限额 + 输出截断，前端明确报错卡片并允许「停止」；
3. *上下文爆炸*（大文件内容进对话）→ 工具层强制：read 默认只回前 N 行 + 摘要，`sandbox_execute` 输出超 10KB 落文件只回引用；
4. *用户改了代码 AI 不知道* → 文件变更事件（含用户手动编辑）实时注入上下文，保持单一事实源是工作区文件本身。

---

## 十一、CC 实施提示词（分阶段投喂）

### P0 提示词

```
你是 OmicHub 平台的后端+前端工程师。现在为平台新增「OmicStudio AI 分析工作台」P0 骨架。
平台现状：Vue3 + Arco Design 前端；FastAPI 后端；Celery；Docker Swarm 部署；已有 yaml 配置驱动的
多智能体对话（Agent Runner 支持多轮工具循环与 MCP 工具）、Docker Swarm 沙盒能力、NFS 挂载 /data/omichub。

请完成：
1. 编写 docker/sandbox/base.Dockerfile 与 bio.Dockerfile（见架构文档 §6.1 依赖清单），
   镜像内预装 sandbox-agent（FastAPI 小服务，提供 POST /exec 流式执行与 /files/* 文件读写，
   非 root uid=10001，只读根文件系统，/workspace 可写）。
2. 实现 Sandbox Manager：会话首次发消息时通过 docker SDK 创建 Swarm service
   （名 studio-{session8}，挂载 NFS /data/omichub/studio/{session_id} 到 /workspace，
   cpu=2/mem=4g，overlay 网络隔离），空闲 30min 回收，重发消息自动拉起。
3. 在现有 Agent Runner 上注册 5 个内置工具：sandbox_execute（流式）、workspace_write、
   workspace_edit（返回 diff）、workspace_read（默认前 200 行）、workspace_list。
   所有路径强制归一化在 /workspace 内。
4. 前端新增 /studio/:sessionId 页面（三栏布局，见架构文档 §4.1）：左栏会话列表+工作区文件树，
   中栏对话执行流（思考/计划/工具调用卡片/代码卡片），右栏产物列表+沙盒状态灯。
   代码卡片用 Monaco Editor，支持「编辑→重跑」，工具输出 WebSocket 逐行流式渲染。
5. WebSocket 事件协议按架构文档 §5.3 实现。
约束：复用现有模型路由/会话表（加 mode 字段）/MCP 体系；不引入新的状态存储；
所有可配置项进 config/studio.yaml（见 §9）。
```

### P1 提示词

```
在 OmicStudio P0 基础上完成平台联动：
1. 数据管理联动：Studio 左栏「从数据管理引入」复用平台文件选择器，选定后调用 datahub_import
   在 /workspace/input/ 建只读软链，并把文件清单注入 Agent 上下文。
2. 结果报告中心每个报告新增「在 AI 工作台中优化」按钮 → 调 Context Packager 接口：
   打包来源流程、run_id、参数、日志、产物文件（软链），创建 Studio 会话并注入系统上下文
   （格式见架构文档 §7.2 context_pack）。
3. 实现 artifact_register 工具 + 右栏产物「保存为新版本」动作：写入结果报告中心，
   与原报告建立版本树（parent_id）。
4. 待办计划面板：agent.plan 事件驱动右栏 checkbox 列表，随执行自动勾选。
5. 智能体 yaml 增加 studio 段（enabled/image/资源覆盖），Agent Runner 按智能体加载对应配置。
验收：架构文档 §8 场景 A 全流程可演示。
```

### P2 提示词

```
在 OmicStudio P1 基础上完成体验与规模化：
1. workspace_edit 结果用 diff2html 渲染 diff 卡片，支持「接受/拒绝」。
2. sandbox_execute 预估超 10min 的任务转 Celery（复用任务中心，类型 studio_sandbox），
   完成后 WebSocket 回推结果；任务中心与流程监控页可见沙盒任务与资源。
3. 沙盒状态灯（🟡启动/🟢运行/⚪回收）+ 回收后透明重启 + 预热池（常驻 1 个 standby）。
4. 该智能体 yaml 声明的 MCP 工具与 Skills 全量注入 Studio 会话（渐进式披露不变）。
5. 产物预览增强：图片 lightbox、CSV 前 50 行表格预览、md 渲染。
6. 输出防爆：单次工具输出超 10KB 自动落 /workspace/.logs/ 只回引用与尾部摘要。
验收：架构文档 §8 场景 B/C 可演示；空闲 30min 沙盒自动回收；长任务在任务中心可追踪。
```

---

## 十二、一句话总结

OmicStudio = **Biomni 的任务式工作台外壳** × **LiveAgent 的四层工具循环内核** × **VS Code 的代码可改可跑回环**，跑在你已经建好的 Swarm 沙盒与 yaml 多智能体体系之上——它不是新系统，而是把 OmicHub 现有能力编排成「用户不满意时的那个出口」。
