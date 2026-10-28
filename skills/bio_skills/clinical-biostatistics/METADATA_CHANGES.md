# clinical-biostatistics Skill metadata 补全记录

- 日期：2026-10-25
- 范围：`skills/bio_skills/clinical-biostatistics/`
- 处理对象：该目录下全部 12 个包含 `SKILL.md` 的 Skill（`README.md` 及资源目录不在范围内）
- 变更类型：仅修改 `SKILL.md` 的 YAML frontmatter，正文未改动
- 提交状态：未执行 `git commit`

## 1. 变更目标

为每个 Skill 补齐以下 5 个必填 metadata 字段，修复因字段缺失导致的解析失败：

`version`、`display_name`、`display_name_en`、`description_zh`、`description_en`

## 2. 执行规则

1. 既有字段（`name`、`description`、`tool_type`、`primary_tool`、`goal_approach_exempt`）一律保留原值，不覆盖、不重排、不删除。
2. `version` 统一为 `1.0.0`。
3. `description_en` 直接复用原 `description` 的英文原文，语义不变。
4. 新字段插入在 `description` 之后、`tool_type` 之前，顺序固定为：
   `version` → `display_name` → `display_name_en` → `description_zh` → `description_en`。
5. 多行描述使用 `>-` 折叠块；不引入重复 key。

## 3. 改动文件与字段

共修改 **12 个文件**，每个文件新增 **5 个字段**（合计 84 行新增，0 行删除）。

| Skill 目录 | display_name | display_name_en | version | description_zh 字数 |
|---|---|---|---:|---:|
| `adaptive-designs` | 适应性临床试验设计 | Adaptive Clinical Trial Design | 1.0.0 | 103 |
| `bayesian-trials` | 贝叶斯临床试验设计 | Bayesian Clinical Trial Design | 1.0.0 | 95 |
| `categorical-tests` | 分类变量关联检验 | Categorical Association Tests | 1.0.0 | 135 |
| `cdisc-data-handling` | CDISC 数据读取与验证 | CDISC Data Handling | 1.0.0 | 145 |
| `effect-measures` | 治疗效应量计算 | Treatment Effect Measures | 1.0.0 | 125 |
| `logistic-regression` | 临床试验 logistic 回归 | Logistic Regression for Clinical Trials | 1.0.0 | 134 |
| `missing-data-sensitivity` | 缺失数据敏感性分析 | Missing Data Sensitivity Analysis | 1.0.0 | 146 |
| `multiplicity-graphical` | 多重性图形化控制 | Graphical Multiplicity Control | 1.0.0 | 126 |
| `power-and-sample-size` | 样本量与检验效能 | Power and Sample Size | 1.0.0 | 136 |
| `subgroup-analysis` | 亚组与异质性效应分析 | Subgroup and Heterogeneous Treatment Effect Analysis | 1.0.0 | 131 |
| `survival-analysis` | 生存与时间事件分析 | Survival and Time-to-Event Analysis | 1.0.0 | 135 |
| `trial-reporting` | 临床试验统计报告 | Clinical Trial Statistical Reporting | 1.0.0 | 134 |

每个文件补充的字段集合相同：

- `version`
- `display_name`
- `display_name_en`
- `description_zh`
- `description_en`

## 4. 中文描述明细

| Skill | description_zh |
|---|---|
| `adaptive-designs` | 设计采用成组序贯、样本量重估、无缝 II/III 期与应答适应性随机化的适应性临床试验，覆盖 FDA 2019 适应性设计指南及 ICH E20 草案。适用于规划期中分析、样本量重估及主方案/平台试验设计。 |
| `bayesian-trials` | 设计贝叶斯临床试验，涵盖 BOIN/CRM 剂量探索、MAP 先验与 EXNEX 外部数据借用、安全性事件层级模型及后验概率停止规则。适用于剂量探索研究、平台试验及采用信息先验的敏感性分析。 |
| `categorical-tests` | 对临床数据中的分类变量开展关联检验，提供卡方、Fisher 精确检验、Boschloo、Cochran-Mantel-Haenszel 及 McNemar 变体，并给出 Wilson、Newcombe 等校准置信区间。适用于分类结局、配对二分类终点及试验中的独立性检验。 |
| `cdisc-data-handling` | 读取、校验并整理 CDISC SDTM 与 ADaM 临床试验数据，涵盖域连接、ADSL/BDS/OCCDS/ADTTE 追溯、TEAE 约定、Define-XML 2.1 及 Pinnacle 21/CORE 校验。适用于处理监管递交所需的 SDTM/ADaM 数据集与准备分析就绪数据。 |
| `effect-measures` | 计算并解释 OR、RR、RD、HR、NNT 等治疗效应量及其校准置信区间，支持 MOVER、剖面似然与 Bender NNT 方法，并按 FDA 2023 协变量调整指南区分边际与条件估计目标。适用于确证性试验的效应报告、跨研究效应比较及森林图绘制。 |
| `logistic-regression` | 对临床试验的二分类、有序及多分类结局拟合 logistic 回归，提供 g-computation 标准化边际效应、modified Poisson 估计 RR、Firth 惩罚与 Hauck-Donner 诊断。适用于确证性或探索性试验中二分类与有序终点的建模分析。 |
| `missing-data-sensitivity` | 实现确证性试验的缺失数据敏感性分析，包括 MAR 下的 MMRM（Kenward-Roger 校正）、基于参照的多元插补（J2R、CR、CIR、LMCF）、delta 调整与 tipping-point 分析。适用于按 NRC 2010 与 ICH E9(R1) 处理主要或次要终点缺失数据。 |
| `multiplicity-graphical` | 采用 Bretz-Maurer-Hommel 图形法、gatekeeping 策略与闭检验原理控制确证性试验的多重性，支持 Hochberg/Hommel/Holm 及 PRDS 条件。适用于为主要终点、关键次要终点及亚组层级设计 FWER 控制策略。 |
| `power-and-sample-size` | 计算连续、二分类及生存终点的样本量与检验效能，支持优效、非劣效与等效设计，涵盖 FDA 2016 M1/M2 界值框架、Schoenfeld/Lakatos 生存公式及 Schuirmann TOST。适用于按 CONSORT 2025 在方案或 SAP 中论证试验规模。 |
| `subgroup-analysis` | 开展亚组及异质性治疗效应（HTE）分析，涵盖 Mantel-Haenszel 合并、Breslow-Day、交互检验、RERI 相加交互，以及 STEPP、SIDES、causal forests 与贝叶斯收缩方法。适用于监管递交或精准医学主张中的亚组效应评估。 |
| `survival-analysis` | 分析临床试验的时间事件终点，包括 Cox 比例风险及 PH 诊断、非 PH 下的 RMST、Fine-Gray 竞争风险、加权 log-rank 与 MaxCombo，以及复发事件和区间删失数据。适用于肿瘤等领域 OS、PFS、DOR、TTR、TTNT 终点的统计分析。 |
| `trial-reporting` | 按 CONSORT 2025、SPIRIT 2025、ICH E9(R1) 估计目标及 FDA 2023 协变量调整指南编制临床试验统计报告，涵盖 Table 1、分析人群、MMRM 与基于参照的多元插补。适用于准备监管递交材料、定义估计目标及实施缺失数据敏感性分析。 |

## 5. 变更示例

以 `adaptive-designs/SKILL.md` 为例，frontmatter 变为：

```yaml
---
name: bio-clinical-biostatistics-adaptive-designs
description: Designs adaptive clinical trials including group-sequential ...
version: 1.0.0
display_name: 适应性临床试验设计
display_name_en: Adaptive Clinical Trial Design
description_zh: >-
  设计采用成组序贯、样本量重估、无缝 II/III 期与应答适应性随机化的适应性临床试验，覆盖 FDA 2019 适应性设计指南及 ICH E20 草案。适用于规划期中分析、样本量重估及主方案/平台试验设计。
description_en: >-
  Designs adaptive clinical trials including group-sequential ...
tool_type: r
primary_tool: rpact
goal_approach_exempt: true
---
```

`description` 与 `description_en` 内容一致，后者仅改为 `>-` 折叠块形式。

## 6. 校验结果

使用仓库根目录的 `check_skill_meta.py`：

```bash
python3 check_skill_meta.py skills/bio_skills/clinical-biostatistics
```

输出：

```text
检查 12 个文件，问题 0 个
```

校验项全部通过：

- 5 个字段均存在且非空
- frontmatter 可被 PyYAML 正常解析，0 报错
- 无重复 key
- 字段顺序符合约定
- `display_name` 长度 7–16 字（≤20）
- `description_zh` 长度 95–146 字（60–150）

## 7. 改动范围确认

```text
12 files changed, 84 insertions(+), 0 deletions(-)
```

`git diff -U0` 检查确认没有任何被删除或修改的原有行，正文内容未受影响。

## 8. 备注

- 校验脚本 `check_skill_meta.py` 位于仓库根目录，为本次任务的辅助文件，尚未纳入版本控制。
- 按任务要求未执行 `git commit`；后续可按类别单独提交。
