# OmicHub Agent 架构说明与单细胞全流程扩展指南

> 目标读者：准备在一周内搭建大量单细胞分析 tools 并改写 agent 提示词、让 `agent-scrna` 真正跑通单细胞分析全流程的开发者。
> 本文基于 2026-07-27 代码现状整理，所有结论均附文件路径与行号，可直接跳转核对。

## 1. 总体架构一图流

```
用户 → POST /api/v1/chat/stream（agent_id=agent-router，星尘统一入口）
        │
        ▼
ChatService._route_to_agent()          ← 智能路由：LLM 识别意图 → 分派专家
        │                               （chat_service.py:832）
        ▼
AgentService.assemble_context()        ← 组装：模型配置 + system_prompt + tools + skills
        │                               （agent_service.py:447）
        ▼
ChatService.stream_agent_chat()        ← LLM 流式循环，SSE 推 text/tool_call/tool_output
        │                               （chat_service.py:940，工具循环 1448 起）
        ▼
工具执行（按优先级分派）
   ├─ handoff 工具        → 专家间转交（agent_handoff_service.py）
   ├─ skill 工具          → 技能渐进式披露（domain/skill/services.py）
   ├─ Studio 工具         → sandbox_execute / workspace_write / artifact_register …
   │                        （studio_tools.py:53-70，Docker 沙盒里跑 scanpy/R/bash）
   ├─ builtin 工具        → ToolBridgeService → tools_schema.yaml 声明的 service/shim
   │                        （tool_bridge_service.py:37，4 种 invocation_mode）
   └─ MCP server 工具     → 内置 preset（omichub-tools / omichub-platform）或外部 MCP
```

关键认知：**agent 本身不"包含"功能代码**。一个 agent = 一份 YAML（人设 + 模型 + 提示词引用 + 工具白名单 + 运行时画像）。功能全部在工具层，agent 通过 `tool_packs` 挑选自己能用的工具子集。这正是你一周扩展计划的主战场。

## 2. Agent 是如何定义的（以 scrna 为例）

`data/ai/scrna.yaml:1-28`：

| 字段 | 值 / 作用 |
|---|---|
| `agent_id` / `name` / `description` / `avatar` / `color` | 身份与前端展示 |
| `model: qwen3.7-max` | 使用的 LLM（对应 DB 中 AI provider 模型） |
| `prompt_file: prompts/scrna.md` | 系统提示词，**外置 markdown，不内联** |
| `mcp_ids` / `skill_ids` | 绑定的外部 MCP、技能（已挂 human-mouse / plant 细胞注释两个技能） |
| `features.engine: langgraph` | 执行引擎 |
| `tool_packs: [workspace, research, memory, handoff]` | **工具白名单入口**，指向 `data/ai/tools/{pack}.yaml` |
| `handoff.allowed_targets` | 允许转交给哪些专家 |
| `studio.runtime_profile: analysis-scrna` | 沙盒运行时画像 → 决定用哪个 Docker 镜像 |

加载与生效链路：

1. `agent_loader.load_agent_configs()`（`src/omichub/infrastructure/config/agent_loader.py:24`）按 `data/OmicHub.yaml:84-92` 的 `agents.enabled` 列表逐个加载。
2. `_load_single_agent()` 把 `prompt_file` 读进 `system_prompt`（行 106）；`_apply_tool_packs()`（行 181-239）合并各 pack 的 `builtin_tools` / `platform_tools` / `mcp_ids` / `skill_ids`；`studio` 段校验 `runtime_profile` 必须存在于 `data/ai/runtime_images.yaml`。
3. `AgentService.ensure_builtin_agents()`（`agent_service.py:77`）把 YAML 同步进数据库。**改 YAML 或 prompts/*.md 后无需重启**——每次 `list_agents()`（前端刷新 agent 列表）都会触发重同步（`agent_service.py:213`）。

## 3. 工具系统：三层来源

### 3.1 builtin 工具（`tools_schema.yaml`，你新增工具的主入口）

- 注册表：`tool_configs/tools_schema.yaml`（当前仅 10 个工具：volcano、manhattan、KEGG 富集、系统树、记忆、转交）。文件头注释（行 1-30）自带完整字段手册。
- 四种 `invocation_mode`：
  - `backend_sync`：反射调用 `src/omichub/tools/<x>/service.py` 的类（同步、进程内）
  - `backend_shim`：动态 import `src/omichub/tools/shims/<x>.py` 的 `execute()`（如 `shims/volcano.py:174`，纯 Python 解析 CSV→Plotly JSON，**注意 shim 跑在后端进程内，不进沙盒**）
  - `backend_async`：投 ARQ 队列异步执行
  - `open_page`：前端路由跳转
- 加载器 `src/omichub/tools/schema_loader.py` 按 **mtime 热重载，改完即生效，无需重启**。
- 执行桥 `ToolBridgeService`（`tool_bridge_service.py:37`）统一分派，并把结果打包成**双通道**：
  - `llm_payload`（≤3KB 摘要，回灌给 LLM 继续推理）
  - `ui_payload`（Plotly 图、表格、下载链接等，经 SSE `tool_output` 给前端渲染；字段白名单在各工具的 `ui_result_fields` 声明）

### 3.2 内置 MCP preset（进程内伪 MCP）

`src/omichub/infrastructure/mcp/presets.py`：

- `omichub-tools`：把 tools_schema.yaml 的工具包装成 MCP 接口，最终仍走 ToolBridgeService。
- `omichub-platform`：平台能力工具——`platform_sandbox_execute`（行 100）、工作区读写搜索（行 307-499）等。

### 3.3 Studio 工具（agent 的"手"，单细胞重计算推荐路径）

`src/omichub/application/services/studio_tools.py:53-70`，共 12 个：

`sandbox_execute`（python/r/bash，跑在 Docker 沙盒）、`workspace_write/edit/read/list`、`datahub_import`、`platform_result_import`（把平台文件/任务结果导入沙盒 `/workspace`）、`artifact_register`（产物注册给前端）、`update_plan`、`pipeline_query`、`knowledge_search`、`ask_user`。

沙盒由 `src/omichub/infrastructure/studio/manager.py` 管理（Docker 容器 + egress 代理），镜像由 `data/ai/runtime_images.yaml` 定义。**`analysis-scrna` 画像已存在**（行 58-70）：镜像 `omichub-analysis:scrna-2026.07`，Dockerfile 在 `deploy/runtime-images/scrna.Dockerfile`，预装 scanpy 1.10.4、anndata、leidenalg、R-Seurat 5.1.0 全家桶。

### 3.4 其他执行路径（按需了解）

- 旧 sandbox 池：`sandbox_service.py:38`（platform_sandbox_execute 用）
- MAS 容器化重计算：`src/omichub/infrastructure/mas/scanpy.py`（受限 scanpy QC 命令构造，输入必须 `/workspace/input` 下 .h5ad）、Celery 调度
- Flow 流程：`flows/*.yaml` 编译为 MCP 工具（`flow_schema_compiler.py`），提交 Snakemake/Nextflow 管线——**目前无单细胞 flow**

## 4. 提示词组织与修改生效方式

- 目录：`data/ai/prompts/`（agent 直引）+ `registry.yaml`（`prompt_ref` 注册表机制，带 mtime 热载）。
- 单细胞提示词：**`data/ai/prompts/scrna.md`（当前仅 53 行）**。已有角色设定、标准流程骨架（QC→归一化→HVG→PCA/UMAP/Leiden→注释→下游），但"工具使用协议"小节只有一句占位——**这是你本周要补写的核心**。
- 生效：改完文件后，前端刷新 agent 列表（触发 `list_agents()` → `ensure_builtin_agents()` 重同步 DB）或重启服务即可。
- 另外注意 `assemble_context()`（`agent_service.py:557-577`）会在你的 prompt 之后自动拼接：skills L1 索引 + omichub-tools 清单 hint + 工作区文件说明后缀。所以提示词里不用罗列工具清单，重点写**流程编排规则和决策约束**。

## 5. 你的一周扩展计划：最短落地路径

现有资产盘点：agent 有了、运行时镜像有了、2 个细胞注释 skill 有了、提示词骨架有了；**缺口在工具层——tools_schema.yaml 里目前没有任何单细胞专用工具**。

### 第 1 步：新增单细胞工具（主工作量）

在 `tool_configs/tools_schema.yaml` 追加 `omichub_scrna_*` 系列工具，并在 `src/omichub/tools/` 下实现。建议的工具面（对齐 scrna.md 的标准流程）：

| 工具 | 建议 invocation_mode | 说明 |
|---|---|---|
| `omichub_scrna_qc` | backend_sync 或复用 MAS `mas/scanpy.py` | 质控、过滤、mt% 计算 |
| `omichub_scrna_normalize_hvg` | backend_sync | 归一化 + 高变基因 |
| `omichub_scrna_cluster` | backend_sync | PCA/UMAP/Leiden 聚类 |
| `omichub_scrna_annotate` | backend_sync + 现有 2 个注释 skill 协同 | 细胞类型注释 |
| `omichub_scrna_deg` | backend_sync | 差异表达 |
| `omichub_scrna_plot_*` | backend_shim（参考 `shims/volcano.py` 模式） | UMAP/小提琴/点图等出图 |

实现参考样板：service 模式看 `src/omichub/tools/enrichments/service.py`（KEGG）；shim 模式看 `src/omichub/tools/shims/volcano.py:174-242`。每个工具别忘了声明 `ui_result_fields`，让图能推到前端。

**重计算（大 h5ad）不要塞进 backend_sync/shim**（它们在后端进程内跑）。两条路：
- 轻/中量：直接让 agent 用 Studio 的 `sandbox_execute` 在 `analysis-scrna` 镜像里跑 scanpy 脚本——零新工具开发，提示词引导即可，建议第一周先用这条快速跑通；
- 重量/受限执行：走 MAS 模式扩展 `mas/scanpy.py` 的命令构造。

### 第 2 步：绑定工具到 agent

新建 `data/ai/tools/scrna.yaml` tool_pack（仿照现有 workspace/research pack 的格式），在 `builtin_tools` 白名单里列你的 `omichub_scrna_*`，然后把它加进 `data/ai/scrna.yaml:21` 的 `tool_packs` 列表。

### 第 3 步：改写提示词

改写 `data/ai/prompts/scrna.md` 的"工具使用协议"小节，写清楚：
- 全流程各阶段调用哪个工具、输入输出如何衔接（h5ad 在工作区/沙盒 `/workspace` 中的流转约定）；
- 何时直接调专用工具、何时退到 `sandbox_execute` 写 scanpy 代码；
- 产物规范：每个阶段 `artifact_register` 注册什么（图、表、h5ad），`llm_payload` 摘要里该报告什么指标；
- 与 skill 的协同：注释阶段先 `use_skill` 加载 marker 规范再判读。

### 第 4 步：验证

- schema 热重载 + agent 列表刷新即生效，无需重启。
- 测试参考：`tests/unit/tools/test_tool_bridge.py`、`tests/unit/test_agent_loader_studio.py`，建议为每个新工具补单元测试。
- 端到端：起服务后用真实 h5ad 提问"帮我做质控→聚类→注释"，观察 SSE 的 tool_call/tool_output 序列是否符合提示词编排。

### 可选第 5 步：流程化（如需要"一键跑完整流程"）

新建 `flows/scrna_seq.yaml` + `pipelines/` 下的管线，经 `flow_schema_compiler` 编译为工具，走带确认卡的异步任务路径。工作量大，建议第二迭代再做。

## 6. 关键文件速查表

| 你要动的地方 | 路径 |
|---|---|
| 新增工具注册 | `tool_configs/tools_schema.yaml`（字段手册见文件头 1-30 行） |
| 工具实现 | `src/omichub/tools/`（service / shims） |
| 新建 tool pack | `data/ai/tools/scrna.yaml`（新建） |
| 绑定 pack 到 agent | `data/ai/scrna.yaml:21` |
| 改写提示词 | `data/ai/prompts/scrna.md` |
| 运行时镜像（如需加依赖） | `deploy/runtime-images/scrna.Dockerfile` + `data/ai/runtime_images.yaml:58-70` |
| 细胞注释技能 | `data/ai/skill_marketplace/human-mouse-cell-annotation/`、`plant-cell-annotation/` |
| 执行桥（排查工具行为） | `src/omichub/application/services/tool_bridge_service.py` |
| 上下文组装（排查工具没注入） | `src/omichub/application/services/agent_service.py:447-590` |

## 7. 容器绑定机制与提示词参数化（2026-07-27 补充，待评估）

### 7.1 单细胞容器的自动绑定：已实现，无需提示词限定

`agent-scrna` 在 Studio 模式下自动使用单细胞容器，镜像是**会话级绑定**的，LLM 无权选择也无法破坏：

1. `data/ai/scrna.yaml:25-28` 声明 `studio.runtime_profile: analysis-scrna`；
2. `agent_loader.py` 加载时把 profile 解析为镜像 `omichub-analysis:scrna-2026.07` 写入 agent 配置；
3. 创建 Studio 会话时，`chat_service.py:1060` 将镜像存进会话 `sandbox_meta.image`；
4. 该会话内所有 Studio 工具（`sandbox_execute` / `workspace_write` 等）统一带 `image=studio_image` 执行（`chat_service.py:1824`），容器首次创建后复用。

提示词在这里只做**行为引导**：要求 agent 分析计算一律走 `sandbox_execute`（python/r/bash），不得凭空编造结果。

注意事项：

- 必须是 **Studio 模式**（`mode="studio"`）才生效。普通 chat 模式没有 `sandbox_execute`，只有 `platform_sandbox_execute`，走旧沙盒池（`sandbox_service.py`），默认镜像不是单细胞镜像。需确认 scrna 会话默认进入 Studio 模式。
- 会话创建后镜像固定在 `sandbox_meta`，改 YAML 只影响**新会话**。

### 7.2 提示词参数化（`prompt_vars` 提案，尚未实现）

现状两套提示词机制都不支持从 agent yaml 传参：

- `prompt_file`：外置 markdown，改文件生效，但无法参数化；
- `prompt_ref` + `registry.yaml`：支持 `{{var}}` 渲染与热载，但变量定义在 registry 内，agent yaml 传不进去。

提案：给 agent yaml 增加 `prompt_vars` 字段，加载时注入提示词渲染：

```yaml
# data/ai/scrna.yaml
prompt_file: prompts/scrna.md
prompt_vars:
  qc_min_genes: 200
  qc_mt_percent_max: 20
  leiden_resolution: 0.5
```

```markdown
<!-- data/ai/prompts/scrna.md -->
质控标准：保留基因数 ≥ {{qc_min_genes}}、线粒体比例 ≤ {{qc_mt_percent_max}}% 的细胞；
Leiden 聚类默认分辨率 {{leiden_resolution}}。
```

实现方案：在 `agent_loader._load_single_agent()` 读入 prompt 后做一次 `{{var}}` 替换（约十几行，仿照 `prompt_loader.py` 的渲染逻辑）；改 YAML 后随 `list_agents()` 重同步即生效，无需重启。

评估要点：

- 收益：分析参数（QC 阈值、聚类分辨率等）集中在 YAML 调参，不用改提示词文本；多 agent 可复用同一 prompt 模板配不同参数。
- 成本/风险：渲染变量缺失时的兜底策略需定义（保留原文 / 报错 / 空值）；DB 同步的是渲染后的文本，调参排障时需注意"DB 里是展开后的 prompt"。

### 7.3 通用助手容器化（已实施，2026-07-27）

目标：让 `agent-general` 借助预装 uv + micromamba 的基础容器，现场搭环境完成轻量复杂任务。

事实基础：`agent-general` 本就已绑定 Studio 容器（`data/ai/general.yaml:25-28` → `analysis-core`，micromamba 基础镜像，Python 3.12 + R 4.4 + DESeq2/edgeR/limma）。本次补齐了"现场装包"的两个缺口：

已做改动（3 处）：

| 改动 | 文件 | 内容 |
|---|---|---|
| 镜像加 uv | `deploy/runtime-images/core.Dockerfile:23` | micromamba 安装列表新增 `uv=0.5`（conda-forge 渠道）；plot/scrna 镜像基于 core 构建，自动继承 |
| 放行包源 | `data/ai/studio.yaml:24-25` | egress `allow` 白名单放行 `conda.anaconda.org / pypi.org / files.pythonhosted.org / mirrors.aliyun.com / mirrors.ustc.edu.cn`，其余仍断网 |
| 提示词引导 | `data/ai/prompts/general.md`（"沙盒执行与现场装包"小节） | 引导 agent 用 `sandbox_execute` 执行，缺包时优先 `uv pip install`、系统包用 `micromamba install`；装包失败如实告知；多步/正式交付任务仍转介专家 |

生效与验证：

- **镜像改动需重新构建**：`deploy/runtime-images/build.sh`（或手动 `docker build -f deploy/runtime-images/core.Dockerfile -t omichub-analysis:core-2026.07 deploy/runtime-images/`），已有会话的容器不受影响，新会话用新镜像。
- studio.yaml / general.md 改动随服务重载与 agent 列表刷新生效，无需额外操作。
- 验证：新建 agent-general 的 Studio 会话，提问"用 Python 帮我读一下这个 csv 并画分布图，缺包自己装"，观察 `sandbox_execute` 中 `uv pip install` 是否走通代理白名单。

待评估的风险点：

- **安全面**：断网是刻意的防外泄设计，本次仅放行包源域名；如需收紧可移除镜像源只留官方源。egress 代理需确认 `omichub-studio-egress-proxy` 容器实际按 `allow` 名单拦截。
- **权限面**：Studio 默认 `supervised` 模式，`sandbox_execute` 每次需用户批准（`chat_service.py:1017`）。若希望通用助手放手跑可切 `auto`，但建议先保持 supervised 观察。
- **资源面**：现场装包会撑大容器层，`analysis-core` 资源限额 `cpu: 2 / memory: 4g`（`runtime_images.yaml:33`），重型依赖可能 OOM。

### 7.4 澄清交互机制（ask_user）现状与全局化方案（2026-07-27，待评估）

目标场景：用户与 AI 沟通时信息模糊（缺物种、缺数据格式、缺分组等），AI 主动调用"询问工具"弹出澄清卡片，让用户选择方向、补充缺失信息，再进入下游分析。

#### 现状：机制已端到端存在（仅 Studio 模式）

- **工具定义**：`src/omichub/application/services/studio_tools.py:316-336` 的 `ask_user`，参数 `question` + `options[]`（快捷选项列表）；工具描述已要求"信息不足时先用本工具，不要编造参数"。
- **后端拦截**：`chat_service.py:1729` 拦截该调用（不进沙盒），推 SSE `ask_request` 事件（`chat_service.py:1739-1746`，带 tool_call_id/question/options），本轮回复收尾，等待用户下一条消息（`:1996`）。
- **前端卡片**：`frontend/src/components/ai-chat/KimiMessageItem.vue:859` 渲染澄清卡片（问题 + 选项快捷回复按钮，`:449` 点击即把选项文本作为下一条消息发送，回答后标记"已回答"）；用户也可自由输入补充信息（`stores/agentHub.ts:1295`，等价于发送下一条用户消息）。
- 已覆盖诉求：选择描述方向（options 按钮）+ 补充缺失信息（自由文本）。

#### 限制 1：仅 Studio 模式可用

`ask_user` 属于 Studio 内置工具集（`studio_tools.py:53-70`），普通 chat 模式（星尘统一入口首轮）没有此工具，而信息模糊恰恰最常发生在入口首轮。

**全局化方案（待实施，中等改动）**：

1. 在 `tool_configs/tools_schema.yaml` 注册 `ask_user` 为 builtin 工具（invocation_mode 需新增一种"会话澄清"直返模式，或走 backend_shim 直接返回结构化结果）；
2. 复用现有 SSE `ask_request` 事件与前端澄清卡片渲染，前端无需改动；
3. 在 `data/ai/tools/` 的公共 tool_pack（如 workspace 或新建 clarify pack）中声明，让各 agent 默认挂载。

#### 限制 2：提示词缺少强制使用约定

目前各专家提示词只泛泛要求"信息不足先确认"，agent 是否调用 ask_user 不稳定。需在各专家提示词补充明确触发规则，模板：

```markdown
### 澄清规则
开始分析前，以下信息任一缺失时必须调用 ask_user，并为每项给出 2-4 个常见选项：
物种（人 / 小鼠 / 植物…）、数据格式（10x 矩阵 / h5ad / rds / fastq）、分组变量、分析目标。
禁止假设默认值后直接开始分析；用户回答后再启动工具调用链。
```

建议优先补 `data/ai/prompts/scrna.md`（与单细胞工具建设同步），再推广到 rnaseq / viz。

#### 评估要点

- 收益：显著降低"agent 假设错误参数白跑一轮"的返工；澄清卡片比纯文本追问的交互成本更低、信息更结构化。
- 风险：过度澄清会打断体验——触发规则要限定"分析启动前、关键参数缺失"场景，闲聊/问答不触发；options 过多时卡片臃肿，建议 ≤4 项。
- 工作量：全局化约涉及 tools_schema + tool_bridge 分派 + 1 个 tool_pack；提示词规则为纯文本改动，随列表刷新生效。

## 8. HCTP × 单细胞全流程：重计算落地映射（2026-07-27，待评估）

依据：`Protocol/高算力容器分析工具架构协议_v1.md`（HCTP v1.0）。结论：单细胞重计算应走 HCTP，与既有的 Studio 沙盒、Flow 形成三级分工。

### 8.1 三条计算路径的分工

| 路径 | 适用场景 | 单细胞里对应 |
|---|---|---|
| Studio 沙盒（`sandbox_execute` + `analysis-scrna` 镜像） | 交互式、探索性、轻中量计算 | 看数据、试参数、出草图、小规模 h5ad 快速分析 |
| **HCTP 工具**（Celery + 短生命周期容器 + 标准产物契约） | 重计算、输入输出契约明确的一次性分析 | QC / 归一化 / 聚类 / 注释 / DEG 等定型步骤的正式执行 |
| Flow / ARDP（Snakemake 多阶段） | 多阶段流水线、进报告中心 | 未来"一键全流程"交付报告 |

选型理由：scanpy 跑 10 万级细胞的聚类需数分钟到数十分钟，不能塞进 agent 会话的 `sandbox_execute` 同步等（`studio.yaml:17` 的 600s 执行超时）；HCTP"提交即返回 + 任务轮询"天然支持长任务、断线续查、结果复用。

### 8.2 单细胞工具按 HCTP 落地的映射

按协议 §10 接入清单，每个单细胞工具（建议拆分为多个，见 §8.4）：

| HCTP 条款 | 单细胞落地 |
|---|---|
| §3.1 六件套 | `src/omichub/tools/scrna_<step>/`（api/schema/config/service/tasks/runner），照 `enrichments/` 抄骨架；路由自动注册（§3.2），零接线 |
| §6 镜像 | 可引用现有 `omichub-analysis:scrna-2026.07`——`runtime_images.yaml:80-85` boundaries 允许镜像层被工具箱执行器引用（不复用容器/池/挂载）；但 §5.4 要求脚本烘焙进镜像（`/app/run_scrna_<step>.py`，argparse CLI），需加分析脚本层或新建 `deploy/docker/Dockerfile.scrna_<step>` |
| §5.5 标准产物 | 恒定列 CSV：QC 指标表（`qc_metrics.csv`）、聚类表（`clusters.csv`）、注释表、DEG 表；**h5ad 属"大体量数据"，只落盘 + 给下载路径，不进 `task.parameters["result"]`**（§5.5-4、§11-7） |
| §5.5 退出码 | 多阶段/多对比时用"局部失败保留成功部分"语义 |
| §3.5 AI 暴露 | `tools_schema.yaml` 加 `omichub_run_scrna_qc` 等条目，`backend_sync` 包裹 `<Tool>Service.submit`；agent 拿 `task_id` 后经 `platform_get_task` 轮询——**这是 agent 全流程中重计算的正规出路**：轻步骤 `sandbox_execute`，重步骤调 HCTP 工具 |
| §8 产物登记 | h5ad/结果表登记进 `file_records`（`FileRegistry.register` + `FileSource` 加枚举），被下一步工具和「文件管理」复用，形成 **QC → 聚类 → 注释 → DEG → 富集** 工具链闭环（§12.5 DEG→富集为同构先例） |
| §4 配置三层 | 物种/参考/默认阈值进 `tool_configs/scrna_<step>/*.yaml`（公开边界：宿主参考路径绝不回浏览器）；镜像/网络/资源/超时进 `core/config.py` 的 `scrna_*` 八键 |

### 8.3 Agent 编排约定（提示词侧）

`data/ai/prompts/scrna.md` 的工具使用协议应按此分工写：

- 轻步骤（数据窥探、试参、草图）→ `sandbox_execute`（Studio 会话容器，scanpy 直接跑）
- 重步骤（定型分析正式执行）→ 调 `omichub_run_scrna_*` HCTP 工具 → `platform_get_task` 轮询 → 完成后读结果摘要继续
- 步骤间数据衔接：前步产物经 `file_records` 的 file_id 引用为后步输入（`upload://`/`file://` 引用机制）

### 8.4 待决策项：工具拆分粒度

- **方案 A（推荐）：多个独立工具**（`scrna-qc` / `scrna-cluster` / `scrna-annotate` / `scrna-deg`）——符合 §6.2 一工具一职责，agent 精细编排、失败重跑粒度小；代价是六件套抄多份（协议设计即"照骨架填空"）。
- **方案 B：单工具带阶段参数**（`scrna-analysis --step qc`）——接入量少，但违背一工具一镜像原则，阶段间失败语义与产物契约会复杂化。

### 8.5 评估要点

- 收益：重计算不再受会话超时限制；任务可轮询/可复现/结果跨工具复用；AI 与网页同入口（§2.3 双提交通道），用户在工具箱页面手动跑与 agent 代跑状态一致。
- 成本：每个工具约 2.5–3.5 人日（§12.6 的 DEG 估计，含前端工作台；若仅 AI 暴露不做页面可省前端部分）。
- 风险：HCTP 要求 Worker 持 Docker Socket（§11-1 红线），部署形态需具备 Celery Worker 容器；`analysis-scrna` 镜像 12g 内存画像与 HCTP 容器资源键（`scrna_memory` 等）需对齐。

### 7.5 沙盒网络放开与国内镜像源加速（已实施，2026-07-27）

目标：所有沙盒镜像开启网络（白名单制），并预置国内镜像源加速 pip / mamba 装包。

已做改动（5 处）：

| 改动 | 文件 | 内容 |
|---|---|---|
| 网络模式放开 | `data/ai/studio.yaml:19` | sandbox 网络 `mode: none → whitelist`（合法取值仅 none/whitelist，见 `studio_loader.py:50-56`），配合既有 egress `allow` 包源白名单生效 |
| core 镜像预置 .condarc | `deploy/runtime-images/core.Dockerfile`（`USER "$MAMBA_USER"` 之后） | 写入中科大源 `.condarc`（default/custom channels 指向 USTC，channels: conda-forge/bioconda/defaults）；plot、scrna 镜像 `FROM` core/plot 链自动继承 |
| 旧沙盒镜像预置 .condarc | `deploy/sandbox/Dockerfile`（ENV 之后） | 同样内容写入 `/root/.condarc`（mambaforge 基础镜像） |
| 提示词镜像源约定 | `data/ai/prompts/general.md`、`code.md`、`scrna.md` | 约定：pip 装包必须加 `-i https://pypi.mirrors.ustc.edu.cn/simple`（Python 包优先 `uv pip install`）；conda/mamba 装包直接 `micromamba install`，镜像已预置 .condarc 无需指定源 |

验证：生成的 .condarc 经 YAML 解析通过；`studio.yaml` 解析通过且 mode=whitelist（loader 校验值合法）。

生效注意：

- **镜像改动需重建**：core → plot → scrna 链依次重建（`deploy/runtime-images/build.sh`）；旧沙盒镜像单独重建（`docker build -t omichub/sandbox-base:latest -f deploy/sandbox/Dockerfile deploy/sandbox`）。只对新建容器生效。
- **egress 代理白名单需包含** `mirrors.ustc.edu.cn`（已在 7.3 放行）；若代理只按域名精确匹配，注意 USTC 的 anaconda 路径与 pypi simple 路径都走同一域名，无需额外放行。
- 提示词改动随 agent 列表刷新生效，无需重启。

遗留说明：HCTP 工具镜像（`deploy/docker/Dockerfile.enrichment` 等）是任务型容器、默认不出网（HCTP §6.4），本次未加 .condarc；如后续需要可在各自 Dockerfile 参照同样方式添加。

**7.5 增补（2026-07-27，全量覆盖）**：按"所有可能装软件的 agent 和镜像"要求扩展——

- 提示词镜像源约定追加到 `rnaseq.md`、`visualization.md`（连同已改的 general/code/scrna，共 5 个实际执行沙盒计算的 agent）。shania/router/orchestrator 不直接执行装包（人格/路由/编排角色），未加。
- pip 类镜像统一预置 `/etc/pip.conf`（`index-url = https://pypi.mirrors.ustc.edu.cn/simple`，构建期与运行期全局生效）：
  - `deploy/runtime-images/core.Dockerfile`（root 段，plot/scrna 链继承）
  - `deploy/studio/base.Dockerfile`（`bio.Dockerfile` FROM 该基础镜像继承）
  - `deploy/sandbox/Dockerfile`（mambaforge 旧沙盒，同时有 .condarc + pip.conf）
  - `tool_configs/terminal/docker/Dockerfile`（终端基础镜像，rnaseq/scrna/gatk/ggplot2/assembly/metagenomics 六个终端子镜像全部 FROM 它继承）
- conda/mamba 类镜像 .condarc 覆盖：`deploy/runtime-images/core.Dockerfile`、`deploy/sandbox/Dockerfile`（见 7.5 正文）。
- 未覆盖说明：HCTP R 工具镜像（`deploy/docker/Dockerfile.enrichment/deg/phylo`，bioconductor R 生态，无 conda/pip，按 HCTP §6.4 默认不出网）；平台后端/Worker/前端构建镜像（基础设施构建期，非 agent 运行环境）。如需要可后续加 R 的 CRAN/Bioc 镜像源配置。
