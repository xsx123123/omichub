# 单细胞分析脚本 Skill 化改造与 OmicHub 整合规范

> 目标：将 `/home/zj/pipeline/scRNA_seq_Analysis_pipeline` 仓库中的单细胞分析流程（README/文档）与 `tools/` 下的分析脚本转换为 OmicHub 平台技能（Skill），挂载到 `agent-scrna`（单细胞分析师），使其从"只会给建议"变成"真正能跑分析"。
> 依据文档：`docs/26.7.27/OmicHub技能加载方案与助手管理页美化实现计划.md`、`data/ai/README.md`、源码 `src/omichub/infrastructure/skills/`。

---

## 一、能不能转？—— 结论先行

**可以，而且仓库里的两类资产分别对应 Skill 的两个标准组成部分：**

| 仓库资产 | 转换目标 | 说明 |
|---|---|---|
| README / docs / 流程文档 | SKILL.md 正文（L2 指令）+ `references/`（L3 参考） | 流程步骤、QC 阈值、注释策略等"知识与流程" |
| `tools/` 分析脚本 | 技能包内 `scripts/` 可执行脚本 | 模型按 SKILL.md 的指引在沙盒中调用，产出真实分析结果 |

OmicHub 的 Skill 遵循 Anthropic Agent Skills 渐进式披露三层模型（解析器见 `src/omichub/infrastructure/skills/skillmd.py`）：

- **L1 索引**：启动时只把 `name + skill_id + description` 注入 system prompt（约 100 tokens/技能），`description` 决定何时触发；
- **L2 正文**：模型通过内置工具 `use_skill` 按需加载 SKILL.md 全文；
- **L3 资源**：模型通过 `skill_resource` 按需读取 `references/`、`assets/`（≤200KB/文件）。

**关键认知：现有 4 个市场技能（如 `human-mouse-cell-annotation`）是"纯知识型"技能——只有指令文本，没有可执行脚本。本次改造的核心升级点是引入"可执行型"技能（带 `scripts/`），这是让 agent 真正动手分析的关键。**

---

## 二、OmicHub Skill 硬规范（必须遵守）

### 2.1 目录与文件结构

一个技能 = 一个文件夹，文件夹名即 `skill_id`（小写字母/数字/连字符，≤48 字符）：

```
data/ai/skill_marketplace/<skill-id>/
├── SKILL.md          # 必填：YAML frontmatter + Markdown 正文
├── scripts/          # 可选：可执行脚本（R/Python/Shell）
├── references/       # 可选：L3 参考文档（marker 表、协议、参数说明）
└── assets/           # 可选：模板、静态资源
```

落点二选一：
- **内置市场（推荐比赛用）**：放 `data/ai/skill_marketplace/<skill-id>/`，启动时 `agent_service._ensure_configured_marketplace_skills()` 自动安装并挂载到声明了它的 agent；
- **运行时安装**：放 `data/ai/skills/` 或经管理 API（`src/omichub/api/v1/admin/skills.py`）导入 zip。

### 2.2 SKILL.md frontmatter 字段

```yaml
---
name: <技能显示名，可中文>        # 必填
description: <何时触发的自然语言描述>  # 必填，缺失直接报错；写清触发场景，模型靠它做 L1 路由
version: 1.0.0                  # 可选，建议填（会话内版本 pin 依赖它）
author: <作者>
icon: 🔬                        # 可选，emoji
category: analysis              # 可选，默认 general
skill_id: <显式指定 id>          # 可选，缺省由 name 生成 slug；中文名务必显式指定
---
```

注意：**不要**混用 `pipelines/RNAFlow/skills/SKILL.md` 那套 frontmatter（`tool_type`/`depends_on`/`qc_checkpoints`），那是流程仓库的独立规范，平台解析器不认识。

### 2.3 硬性限制

| 限制 | 值 | 后果 |
|---|---|---|
| 技能包总大小 | ≤ 1 MiB | 超标拒绝 |
| 单文件大小 | ≤ 512 KB | 超标拒绝 |
| SKILL.md 正文 | 建议 < 20000 字符（约 5000 tokens） | 超过仅告警，但浪费上下文 |
| L3 资源单文件 | ≤ 200 KB（按需读取） | 超过无法通过 `skill_resource` 读取 |

推论：**大型参考数据（SingleR 参考 rds、CellMarker 库、基因注释表）严禁塞进技能包**，应放共享数据卷/对象存储，SKILL.md 只记录路径约定。

### 2.4 挂载到 agent

在 `data/ai/scrna.yaml` 的 `skill_ids` 列表追加技能 id：

```yaml
skill_ids:
  - human-mouse-cell-annotation     # 已有
  - plant-cell-annotation           # 已有
  - scrna-qc-preprocess             # 新增
  - scrna-deg-analysis              # 新增
  - ...
```

agent YAML 与 tool pack 内的 `skill_ids` 会合并去重（`agent_loader.py:185-243`）。运行时模型首轮会话会做版本 pin（`skill_pins`），会话内使用快照。

### 2.5 与沙盒/工具的关系

- Skill 提供"知识与流程"，**执行动作走沙盒工具**（`tool_packs: [workspace, ...]` + `studio.runtime_profile: analysis-scrna`）。
- `scripts/` 中的脚本会在沙盒内被调用，因此：
  - 脚本路径一律用**相对技能的引用方式写进 SKILL.md 指令**（如"执行 `scripts/rds_convert.R`"），由 `use_skill`/`skill_resource` 机制落盘；
  - 运行时画像 `analysis-scrna` 的 `required_capabilities: [python, r, plotting, single-cell, hdf5]` 已声明 R/Python 环境，SKILL.md 中应写明"使用沙盒 R 环境"，不得引用宿主机的 conda/绝对路径。

---

## 三、仓库脚本盘点与 Skill 拆分方案

### 3.1 拆分总览（建议 7 个技能）

| 建议 skill_id | 名称 | 来源脚本 | 类型 |
|---|---|---|---|
| `scrna-pipeline-overview` | 单细胞主流程总控 | README.md、docs/README_zh.md、`scRNAseqMulticommand.yaml` | 知识型（流程编排指令） |
| `scrna-object-convert` | 单细胞对象格式转换与子集操作 | `tools/objectConvert/RDS_convert`、`RDS_utility`、`objectConvert/README.md` | 可执行型（现成 CLI） |
| `scrna-recluster` | 单样本重聚类 | `tools/SingleSampleSubClusterRereduction.r`（`tools/SingleSample/` 副本弃用） | 可执行型（需 wrapper） |
| `scrna-annotation-ref` | 自动注释参考与策略 | `tools/SingleR.r`、`Celldex/` 库清单、`docs/ai_annotation/` | 知识型 + 薄脚本 |
| `scrna-tcell-projectils` | T 细胞 ProjecTIL 精细注释 | `tools/immune_annotation/ProjecTIL_Annotation.r` | 可执行型（需 wrapper） |
| `scrna-deg-analysis` | 差异表达分析 | `tools/DEG/FindMarkers_Celltype_group/`（主力）、`DEG_Annotation_reference/` 说明 | 可执行型（需 wrapper） |
| `scrna-annotation-stats` | 细胞比例统计与可视化 | `tools/AnnotationStats/`（6 脚本 + AnnotationStats.md）、`tools/Statistics_Functions/CalculationPercentAverageExp.r` | 可执行型（需 wrapper） |

主流程本体（`scRNAseqMulticommand` + `src/`）**不建议直接 skill 化**：它是重量级全量管线，适合作为独立容器任务（走 `scripts/run_scrnaseq.py` Docker 封装），Skill 只保留"何时调用完整管线、如何准备 conf.csv、如何解读输出目录"的编排指令（即 `scrna-pipeline-overview`）。

### 3.2 逐脚本处置意见

**可直接封装（已有 CLI，工作量最小，优先做）：**
- `tools/objectConvert/RDS_convert` — RDS↔H5AD/Loom/SCE/MTX 互转，参数完整；
- `tools/objectConvert/RDS_utility` — info/subset/merge/optimize/extract；
- `tools/scRNA_seq_report_merge.R` — 合并多样本 metrics_summary；
- `tools/build_quarto_report.R` — 报告渲染（可选，比赛优先级低）。

**需写薄 CLI wrapper 后封装（R 函数库，用 `optparse`/`argparse` 包一层）：**
- `SingleSampleSubClusterRereduction.r`、`ProjecTIL_Annotation.r`、`FindMarkers_Celltype_group.r`、`AnnotationStats/` 各脚本。
- Wrapper 统一签名：`Rscript <tool>.R --input <rds> --output <dir> [--param value ...]`，stdout 输出结构化 JSON 摘要（产物路径 + 关键统计量），方便 agent 读取结果。

**不建议 skill 化（一次性/硬编码严重，仅作 references 素材）：**
- `tools/Seurat.r`（历史模板，硬编码项目路径）、`Create_Seurat_object_form_txt.r`、`Seurt2Anndata`（被 RDS_convert 取代）、`Extert_DEG.PY`、`MCA_Altas_merge.py`、`count_loc.py`（开发工具）。

**功能重叠需收敛：**
- DEG 四脚本只保留 `FindMarkers_Celltype_group.r` 进 skill，其余（`findmarker.r`、`FindClusterMarkersDotplot.r`、`multithreadingFindMarkerCluster.r`）的能力在 SKILL.md 正文中以参数形式体现；
- `propplot.r` / `Proplot.r` 二选一；
- `SingleSampleSubClusterRereduction.r` 以 tools 根目录版本为准，删 `SingleSample/` 副本。

### 3.3 改造前置工作（阻塞项）

1. **清除硬编码路径**：`SingleR.r`、`multithreadingFindMarkerCluster.r`、`scRNAseqMulticommand.yaml` 中的 `/titan3/...`、`/glusterfs/...`、`/home/zj/miniconda3/envs/scvi` 全部参数化，参考库路径改为环境变量（如 `SCRNA_REF_DIR`）或 CLI 参数；
2. **统一 I/O 契约**：每个脚本"输入一个 RDS/H5AD 路径 + 输出目录"，输出目录内固定 `result.*` + `summary.json`（产物清单），与平台 `分析流程结果交付协议_v1.md` 对齐；
3. **参考数据库外置**：`Celldex/*.rds`、CellMarker/PanglaoDB/ScTypeDB、`DEG_Annotation_reference/` 放共享数据目录，SKILL.md 中写路径约定和缺失时的报错指引；
4. **依赖清单**：在技能 `references/environment.md` 中列出 R 包及版本（对照 `build_analysis_env/scRNAseqMulticommand_environment.yml`），并确认沙盒镜像已包含——`analysis-scrna` 画像声明了 r/single-cell 能力，需在沙盒镜像中核对 Seurat 5.x、SingleR、ProjecTILs、scCustomize 是否齐备。

---

## 四、SKILL.md 编写模板（本项目标准）

```markdown
---
name: 单细胞差异表达分析
description: 当用户需要对已注释的 scRNA-seq Seurat 对象按"细胞类型 × 分组"做批量差异表达分析（FindMarkers）、基因注释和火山图可视化时触发。输入为 RDS/H5AD 对象路径与分组列名。
version: 1.0.0
author: zj
icon: 🧬
category: analysis
skill_id: scrna-deg-analysis
---

# 单细胞差异表达分析

## 何时使用（Trigger）
- 用户已完成聚类和细胞类型注释，持有 Seurat RDS 对象；
- 用户要求"比较 Treat vs Control 在某细胞类型中的差异基因"或"对每个细胞类型做组间 DEG"。

## 输入契约（Input）
| 参数 | 必填 | 说明 |
|---|---|---|
| input | 是 | Seurat RDS 文件路径（沙盒工作区内） |
| group_col | 是 | meta.data 分组列名（如 group） |
| celltype_col | 是 | 细胞类型列名 |
| pairs | 是 | 比较对，如 "Treat,Control" |
| output | 是 | 输出目录 |

若用户未提供必填参数，先简短追问，不要臆测默认值。

## 执行步骤（Workflow）
1. 用 `workspace` 工具确认输入文件存在、对象含分组列；
2. 在沙盒执行：
   ```bash
   Rscript scripts/FindMarkers_Celltype_group.R \
     --input {input} --group-col {group_col} --celltype-col {celltype_col} \
     --pairs {pairs} --output {output}
   ```
3. 读取 `{output}/summary.json`，向用户汇报每个细胞类型的 DEG 数量与火山图路径；
4. 若某细胞类型细胞数 < 30，提示统计功效不足并跳过。

## 输出契约（Output）
- `{output}/DEG/<celltype>_<pair>-DEG-infor.csv`：差异基因表（含基因注释）；
- `{output}/figure/<celltype>_<pair>_volcano.png`：火山图；
- `{output}/summary.json`：产物清单 + 关键统计量。

## 质控与失败处理（QC）
- p_val_adj 阈值默认 0.05，|avg_log2FC| ≥ 0.25，用户可覆盖；
- 脚本报错时原样返回 stderr，不要伪造结果；
- 参考：详见 `references/deg_params.md`（参数详解与基因注释库说明）。

## 严格限制（Constraints）
- 不修改输入 RDS；所有产物写入用户指定 output 目录；
- 比较对中的组别必须在 group_col 中真实存在，先验证再执行。
```

要点：
- **description 是路由依据**：写清"什么输入 + 什么意图"触发，避免与相邻技能（如已有 `differential-expression` 通用技能）边界含糊——本技能的描述要强调"单细胞 + 细胞类型 × 分组批量"以区分；
- **正文五段式**：何时使用 → 输入契约 → 执行步骤（含确切命令行） → 输出契约 → 质控与限制；
- **命令行必须可直接复制执行**，参数用占位符标注来源；
- 正文控制在 5000 tokens 内，细节参数表、marker 库说明、示例数据说明下沉到 `references/`。

---

## 五、与现有技能的整合与边界划分

现有 `skill_ids` 已有 `human-mouse-cell-annotation`、`plant-cell-annotation`（注释知识型）和市场里的 `data-cleaning`、`differential-expression`（通用型）。新技能挂载后必须避免路由打架：

| 已有技能 | 新技能 | 边界约定 |
|---|---|---|
| `human/mouse/plant-cell-annotation`（知识型，解读 marker 做注释判断） | `scrna-annotation-ref`、`scrna-tcell-projectils`（执行型，跑 SingleR/ProjecTIL） | 执行型技能负责"跑工具产出候选注释"，知识型技能负责"对结果做专家裁决"；`scrna-annotation-ref` 的正文末尾引导模型调用知识型技能的判断框架 |
| `differential-expression`（通用 DEG 知识） | `scrna-deg-analysis`（单细胞专用执行） | 描述中明确"单细胞 Seurat 对象、细胞类型×分组"，通用技能处理非单细胞场景 |
| `data-cleaning` | `scrna-pipeline-overview` 的 QC 段 | 主流程技能只写单细胞特有的 QC（MAD 阈值、Doublet、DecontX），通用清洗规则不重复 |

整合操作清单（按序执行）：

1. 在 `data/ai/skill_marketplace/` 下按第三节方案建 7 个技能目录；
2. 每个技能写 SKILL.md（第四节模板），CLI 脚本放入 `scripts/`，参数文档放入 `references/`；
3. `data/ai/scrna.yaml` 的 `skill_ids` 追加全部新 id；`scrna_advanced.yaml` 按需追加 `scrna-tcell-projectils`、`scrna-annotation-stats`；
4. 更新 `data/ai/prompts/scrna.md`：在流程段落注明"各分析步骤优先调用对应技能的 scripts，而非自己重写 R 代码"；
5. 重启服务，验证启动日志中市场技能自动安装成功；
6. 端到端验证：上传测试数据（仓库 `data/testdata/` 的 PBMC 样本），让 agent-scrna 完成"格式转换 → 重聚类 → 注释 → DEG → 比例统计"全链路。

---

## 六、优化建议（除 skill 化外的仓库改进）

1. **脚本瘦身合并**：按 3.2 收敛重叠脚本，仓库保留单一权威版本，减少 skill 维护面；
2. **统一 wrapper 规范**：所有 R 函数库补 `optparse` CLI，签名统一 `--input/--output/--params`，stdout 输出 JSON 摘要；一次投入，全部技能受益；
3. **README 版本对齐**：中文 README 仍写已移除的 `-T/--scRNAtype` 参数，以英文版 v4.1.1 为准修订，避免 SKILL.md 抄错接口；
4. **版本 pin 意识**：技能 `version` 字段改动才会触发会话快照更新，改脚本时记得 bump version；
5. **比赛演示路径**：优先完成 `scrna-object-convert`、`scrna-deg-analysis` 两个可执行技能（CLI 现成/半现成），配合现有注释知识技能即可演示"真正分析"的完整闭环，其余技能按 3.1 顺序补齐；
6. **大小红线自查**：技能打包前跑一遍 `du -sh`（≤1MiB）与单文件 ≤512KB 检查，参考数据一律外置。

---

## 附：关键源码索引

- Skill 解析/限制：`src/omichub/infrastructure/skills/skillmd.py`
- 磁盘存储与 L3 读取：`src/omichub/infrastructure/skills/skill_store.py`
- 运行时注入（L1 索引 / `use_skill` / `skill_resource`）：`src/omichub/domain/skill/services.py`
- Agent 声明式定义与 skill 合并：`src/omichub/infrastructure/config/agent_loader.py`、`data/ai/scrna.yaml`
- 市场自动安装：`agent_service._ensure_configured_marketplace_skills()`
- 平台 Skill 设计文档：`docs/26.7.27/OmicHub技能加载方案与助手管理页美化实现计划.md`
