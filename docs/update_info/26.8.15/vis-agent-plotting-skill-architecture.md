# Vis Agent 绘图教程 Skill 化架构方案

> 目标：将个人积累的绘图教程沉淀为可复用 Skill，挂载到 `agent-viz`，并强制绘图前先查知识库与 Skill，最后才用模型内部知识。

---

## 1. 架构结论

**可行，且无需改动代码。** 项目已具备：

- `knowledge_search` 工具：所有 Agent 自动挂载，用于检索平台知识库。
- `use_skill` / `skill_resource` 工具：加载已挂载 Skill 的 L2 正文与 L3 参考资料。
- 内置 Skill 市场：`data/ai/skill_marketplace/`，配合 `data/ai/<agent>.yaml` 的 `skill_ids` 自动安装。
- Skill 三层渐进式披露：L1 `name+description` 常驻 system prompt，L2 `SKILL.md` 按需加载，L3 `references/` 按需读取。

唯一缺口：`agent-viz` 不能动态发现未挂载 Skill，因此需要把绘图教程 Skill 显式声明到 `viz.yaml` 的 `skill_ids` 中。

---

## 2. Skill 拆分策略

不要把所有教程塞进一个 Skill。建议**按图型/分析场景拆分**，每个 Skill 聚焦一类图：

| Skill ID | 触发场景 |
|---|---|
| `plot-volcano-tutorial` | 差异表达火山图、阈值标注、显著基因标签 |
| `plot-heatmap-tutorial` | 基因表达热图、聚类、注释条 |
| `plot-umap-tutorial` | 单细胞 UMAP/tSNE/PCA 降维图、分群着色 |
| `plot-boxplot-violin-tutorial` | 箱线图、小提琴图、组间比较 |
| `plot-phylo-tree-tutorial` | 系统发育树、ggtree 注释 |
| `plot-enrichment-bubble-tutorial` | 富集气泡图/条形图 |
| `plot-km-curve-tutorial` | 生存 KM 曲线、风险表 |
| `plot-venn-upset-tutorial` | 多集合 Venn / UpSet 图 |
| `plot-correlation-tutorial` | 相关性热图、散点矩阵 |
| `plot-manhattan-tutorial` | Manhattan 图、QQ 图 |

**拆分原则：**

- 有明确输入格式、输出产物、执行步骤的 → 做成 Skill。
- 偏经验、FAQ、案例赏析的 → 放入知识库，走 `knowledge_search`。
- 同一图型的不同变体（静态/交互、R/Python）可放在一个 Skill 内用章节区分。

---

## 3. 目录结构

```text
data/ai/skill_marketplace/
├── plot-volcano-tutorial/
│   ├── SKILL.md
│   └── references/
│       ├── examples.md
│       └── common-mistakes.md
├── plot-heatmap-tutorial/
│   ├── SKILL.md
│   └── references/
│       └── color-scheme-guide.md
├── plot-umap-tutorial/
│   ├── SKILL.md
│   └── references/
│       └── marker-gene-examples.md
├── plot-boxplot-violin-tutorial/
│   └── SKILL.md
├── plot-phylo-tree-tutorial/
│   ├── SKILL.md
│   └── references/
│       └── ggtree-cheat-sheet.md
└── ...
```

---

## 4. SKILL.md 模板

```markdown
---
name: plot-volcano-tutorial
description: 火山图绘制教程。当用户要求绘制差异表达火山图、log2FC/padj 散点图，或需要标注显著基因、调整阈值、配色与图注时触发。
skill_id: plot-volcano-tutorial
version: 1.0.0
category: visualization
---

## 何时使用

- 输入为差异表达结果表（含 log2FoldChange、padj/pvalue、gene/Symbol）。
- 用户要求火山图、差异散点图、标注上下调基因。
- 需要调整阈值、配色、标签数量或导出规格。

## 输入契约

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `gene` / `Symbol` | string | 是 | 基因名，用于标签 |
| `log2FoldChange` | float | 是 | log2 倍数变化 |
| `padj` | float | 推荐 | 校正后 p 值；若无则用 `pvalue` |
| `pvalue` | float | 可选 | 未校正 p 值 |

## 执行步骤

1. 校验输入列；缺失必填列时停止并说明。
2. 计算显著性分组（默认 `padj < 0.05` 且 `|log2FoldChange| > 1`）。
3. 按「内置配色方案」选择色盲安全色板：Up 用 `#D55E00`，Down 用 `#0072B2`，NS 用 `grey70`。
4. 生成 ggplot2 代码，以 `ggpubr::theme_pubclean()` 为基础主题。
5. 同时导出 PDF（投稿）与 PNG（预览，600 DPI）。

## 参考范式

```r
library(ggpubr)
library(ggrepel)

deg_res$significance <- with(deg_res,
  ifelse(padj < 0.05 & log2FoldChange >  1, "Up",
  ifelse(padj < 0.05 & log2FoldChange < -1, "Down", "NS")))

ggplot(deg_res, aes(x = log2FoldChange, y = -log10(padj), color = significance)) +
  geom_point(size = 0.8, alpha = 0.7) +
  geom_hline(yintercept = -log10(0.05), linetype = "dashed", color = "grey50") +
  geom_vline(xintercept = c(-1, 1), linetype = "dashed", color = "grey50") +
  scale_color_manual(
    name   = "Regulation",
    values = c("Up" = "#D55E00", "Down" = "#0072B2", "NS" = "grey70"),
    labels = c("Up" = "Up-regulated", "Down" = "Down-regulated", "NS" = "Not Significant")
  ) +
  geom_text_repel(data = subset(deg_res, padj < 0.05 & abs(log2FoldChange) > 1),
                  aes(label = gene), size = 3, max.overlaps = 20) +
  labs(x = expression(log[2]~FoldChange), y = expression(-log[10]~adjusted~P),
       title = "火山图：Treatment vs Control") +
  theme_pubclean() +
  theme(legend.position = "right", plot.title = element_text(hjust = 0.5))
```

## 输出契约

- 矢量图：`output/figures/<项目名>_volcano.pdf`
- 预览图：`output/figures/<项目名>_volcano.png`，dpi = 600
- 脚本：`output/scripts/<项目名>_volcano.R`
- 图注草稿：包含统计阈值、样本数、显著基因数。

## 限制与诚实约束

- 不负责差异检验本身；输入必须是已完成统计的结果表。
- 不虚构显著基因、不调整真实 p 值。
- 输入行数过少（如 n < 10）时改用散点+条形替代火山图。
```

---

## 5. Agent 配置修改

### 5.1 修改 `data/ai/viz.yaml`

在 `skill_ids` 中追加所有绘图教程 Skill：

```yaml
skill_ids:
  # 绘图工具技能（来源：pipelines/tools/skills/）
  - r-plot-library
  - dotplot
  # 自定义绘图教程 Skill（新增）
  - plot-volcano-tutorial
  - plot-heatmap-tutorial
  - plot-umap-tutorial
  - plot-boxplot-violin-tutorial
  - plot-phylo-tree-tutorial
  - plot-enrichment-bubble-tutorial
  - plot-km-curve-tutorial
  - plot-venn-upset-tutorial
  - plot-correlation-tutorial
  - plot-manhattan-tutorial
```

### 5.2 修改 `data/ai/prompts/visualization.md`

在「工具、Skill 与工作区协议」章节之后新增强制检索章节：

```markdown
## 知识检索与 Skill 使用优先级（强制）

开始任何具体绘图设计、代码生成或图形选型之前，按以下顺序检索，除非用户已明确要求使用某种特定方法：

1. **优先检索平台知识库**：调用 `knowledge_search`，查询与用户需求相关的平台笔记、实验经验、参数阈值或历史案例。
2. **优先使用已挂载 Skill**：如果 `knowledge_search` 结果不足，或问题明显匹配某个已挂载 Skill 的 `description`，调用 `use_skill` 加载对应 Skill 的完整教程，严格按其中的输入契约、执行步骤和范例执行。
3. **最后才使用模型内部知识**：仅当知识库和已挂载 Skill 都没有相关内容时，才基于模型内部知识进行分析和绘图。

禁止跳过前两步直接凭内部知识生成绘图代码，尤其当用户提到具体图型（火山图、热图、UMAP、系统发育树等）或平台已有相关 Skill 时。
```

> 提示：原提示词第 15–17 行已有「知识检索与证据规则」，但表述较弱，建议替换为上述强制优先级章节。

---

## 6. 实施步骤（明日执行清单）

1. 在 `data/ai/skill_marketplace/` 下创建第一批 Skill 目录。
2. 为每个 Skill 编写 `SKILL.md`，把教程内容按「何时使用 / 输入契约 / 执行步骤 / 参考范式 / 输出契约 / 限制」组织。
3. 把通用参考资料（色板、字体配置、导出规格）放到 `references/` 下。
4. 修改 `data/ai/viz.yaml`，追加所有新 Skill ID。
5. 修改 `data/ai/prompts/visualization.md`，新增强制检索优先级章节。
6. 重启服务，让 `AgentService._ensure_configured_marketplace_skills()` 自动安装 Skill。
7. 在管理端检查 `agent-viz` 的 `skill_ids` 是否同步（若管理员曾手动覆盖 system_prompt，需手动同步或清除覆盖）。
8. 做一次端到端测试：让 vis agent 绘制一个火山图，验证它会先 `use_skill` 再生成代码。

---

## 7. 注意事项

- **Token 预算**：每个 Skill 的 `name` + `description` 会作为 L1 索引注入 system prompt。Skill 过多时考虑合并相似图型，或把低频图型放入知识库。
- **Skill 位置**：只有 `data/ai/skill_marketplace/` 下的 Skill 会被自动安装；`skills/` 目录仅作示例/参考。
- **RAG 与 Skill 的分工**：
  - Skill：结构化、可执行、有明确输入输出。
  - 知识库：经验、案例、非结构化问答。
- **提示词覆盖**：如果管理员在 UI 修改过 vis agent 的 system prompt，重启不会自动覆盖 YAML。需要在管理端重新同步，或删除 UI 覆盖记录。
- **校验**：新增 Skill 后可用 `SkillService` / `skillmd.py` 解析校验，确保 frontmatter 字段完整。

---

## 8. 验收标准

- [ ] `data/ai/skill_marketplace/` 下新增至少 3 个绘图教程 Skill。
- [ ] `data/ai/viz.yaml` 的 `skill_ids` 包含这些 Skill ID。
- [ ] `data/ai/prompts/visualization.md` 包含「知识检索与 Skill 使用优先级（强制）」章节。
- [ ] 重启后 Skill 成功安装到 `skills` 表。
- [ ] 测试对话中，vis agent 在绘制目标图型前调用了 `use_skill` 加载对应教程。
