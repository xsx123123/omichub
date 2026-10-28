# OmicHub BLAST 结果页可视化与表格样式优化实现计划

> 版本：v1.0　日期：2026-07-27
> 范围：序列检索 BLAST 页（参数输入区布局 + 结果摘要 + Graphic Summary + 比对结果表格
> + 序列比对详情）
> 性质：**已有页面的样式优化 + 1 个数据 bug 排查（Coverage 显示 0.0%）**，不是重新设计；
> 不改路由、不改 BLAST 执行逻辑与数据接口
> 表格规范沿用《OmicHub最近任务卡片表格样式优化实现计划》定下的任务中心表格规范
> （列居中、表头 `#f7f8fa`、tabular-nums、单行不折行、行高 52~64px、行 hover 浅色反馈）

---

## 1. 背景与目标

BLAST 结果页当前能正常出结果，但视觉与布局问题集中：

1. 左侧参数区被切成 6 个零碎小卡片，纵向冗长、留白多；
2. 「比对结果」表格与任务中心已定规范脱节——长数字折行、列挤压、Coverage 空灰条、
   1 条数据也挂大分页器；
3. Graphic Summary 与序列比对详情的可视化粗糙：坐标无刻度、色条无交互、卡片底部
   大面积空白、统计项摊成稀疏的 label:value 长行；
4. **疑似数据 bug**：Query 1–79 全长比对（Align 79 bp、Mismatch 0），Coverage 却显示
   0.0%，需排查覆盖率计算。

目标：一次改对，结果区达到任务中心同级的表格质感，可视化达到 NCBI BLAST
Graphic Summary 的可读性水平，且风格与平台首页/工作台一致。

## 2. 问题清单与修改 Spec

### 问题 1【Bug 排查】：Coverage 显示 0.0% 与比对数据矛盾

- **现状**：Hit #1 的 Query Range = 1–79（Query 全长 79 bp），Align Len = 79 bp，
  但「比对结果」表格 Coverage 列和「序列比对详情」里 Coverage 均为 0.0%，且表格里
  Coverage 单元格显示一条满宽灰色空槽，看起来像组件坏掉。
- **修改 spec**：
  - 定位 Coverage 计算代码，打印原始字段确认量纲：正确口径应为
    `coverage = align_len / query_len`（本例应 ≈ 100%）；常见错误是误用
    `align_len / subject_len`（本例 subject 为 30,427,671 bp，算出来 ≈ 0.00026%，
    与现象吻合，优先排查这个方向），或 XML/JSON 字段映射拿错；
  - 修正后 Coverage 显示为 0~100% 一位小数，进度条按值填充；
  - 进度条轨道色 `#eef0f2`，填充色用主题色（或沿用 identity 四档色），
    轨道宽度固定（如 64px）+ 右侧百分比文字 `width: 48px; text-align: right;
    font-variant-numeric: tabular-nums; white-space: nowrap;`。
- **预期效果**：全长命中显示 ~100.0%，进度条填充与数值一致，不再出现误导性空槽。

### 问题 2：「比对结果」表格未按任务中心表格规范处理

- **现状**：
  - Length 列 `30,427,671 bp` 被折成「30,427,67 / 1 bp」两行，数字被从中间截断；
  - 11 列挤在一起，表头密、行高松散，与任务中心表格质感不一致；
  - Subject Description 长文本无省略策略，把整行撑高；
  - 只有 1 条数据仍显示完整分页器（上一页/1/下一页/50 每页），视觉噪音大。
- **修改 spec**（逐项对齐任务中心规范）：
  - 表头行背景 `#f7f8fa`，行高收紧至 52~56px，行 hover 浅色反馈 `#f9fafb`；
  - **列对齐**：短值同构列全部居中——`#`、Subject ID、Length、Identity %、E-value、
    Bit Score、Align Len、Query Range、Subject Range、Coverage；唯一例外是
    Subject Description 长文本列左对齐，`max-width` 截断 + 省略号 + hover title；
    若表格组件库支持 column 级 `align` 属性，优先用组件配置；
  - 所有数值列加 `font-variant-numeric: tabular-nums;`；
  - Length、E-value、Bit Score、Range 各列 `white-space: nowrap`，
    Length 列 `min-width: 140px`（容纳 `30,427,671 bp` 单行），
    Range 列 `min-width: 96px`；
  - Identity % 保留浅绿胶囊，但规格统一：圆角胶囊 `padding: 2px 8px`、
    字号 12px、tabular-nums；
  - 分页器：数据 ≤ 1 页时只显示「共 N 条」文本，隐藏页码与页大小切换；
    默认页大小 10/20，不出现「50 / 页」配 1 条数据的反差。
- **预期效果**：表格与任务中心页一眼同源，长数字单行完整，行高一致。

### 问题 3：Graphic Summary 粗糙 + 卡片底部大面积空白

- **现状**：
  - Query 轴只有一根灰线 + 两端「1」「79」，无任何刻度，无法读位置；
  - Hit 色条无 hover 信息、无点击联动，纯装饰；
  - 图例「Identity: ■ ≥90% …」字号过大（约 20px）且字重粗，压在卡片中缝；
  - 卡片内容只占了上半部分，底部约 40% 是空白（疑似固定 min-height）。
- **修改 spec**：
  - **坐标轴**：Query 轴加刻度系统——按 Query 长度自适应取整刻度（如 79 bp 用
    每 10 bp 小刻度、50 bp 主刻度标数字；长序列自动切 nice number 步长），
    轴线 `#d1d5db` 1.5px，刻度标签 11px 次要色 `#6b7280`，tabular-nums；
  - **Hit 条**：高度 16px、圆角 3px，沿用 identity 四档配色
    （≥90% `#22c55e`、≥70% `#3b82f6`、≥40% `#f59e0b`、<40% `#ef4444`）；
    每条 hit 一行，行高 28px，按 E-value 升序排列；
    hover 显示 tooltip（Subject ID · Identity · E-value · Query Range），
    点击平滑滚动到下方对应「序列比对详情」卡片并短暂高亮；
  - **图例**：字号降至 12px、字重 400、正文字体族，色块 10×10px 圆角 2px，
    整体右对齐或放在标题行右侧；
  - **卡片高度**：去掉固定 min-height / 拉伸约束，内容自适应
    （`height: auto`，卡片 `padding: 16~20px`），消除底部空白；
  - Query 标签（"Query"）与 hit 标签（"Chr1"）左列宽 88px、12px 次要色右对齐，
    与图区基线对齐。
- **预期效果**：可读坐标、可交互色条、紧凑无空白，达到 NCBI Graphic Summary
  同级的信息密度。

### 问题 4：序列比对详情统计区稀疏、覆盖条与 Graphic Summary 重复且同样粗糙

- **现状**：
  - 10 个统计项以 `label:value` 形式摊成两行通栏长行，项与项之间空隙巨大
    （用户说的"有些地方是空的"主要指这里）；
  - 「Query 覆盖位置」色条与 Graphic Summary 信息重复，且同样无刻度；
  - Hit 头部（Hit #1 / Chr1 胶囊 / 描述 / 100.0% / 对齐）元素基线不齐。
- **修改 spec**：
  - **统计区改为 stat 网格**：3~4 列网格（`grid-template-columns: repeat(auto-fit,
    minmax(160px, 1fr))`），每项「label 12px 次要色在上 + value 14px/500 主色在下」，
    value 加 tabular-nums；项数不是列宽整数倍时左对齐排列，不再均摊整行；
  - **Query 覆盖条**：与 Graphic Summary 共用同一轨道样式（轨道 `#eef0f2`、
    覆盖段按 identity 档位着色、高度 10px、圆角 3px），两端标注起止坐标
    （本例 1 / 79），11px 次要色；
  - **Hit 头部**：一行 flex 布局垂直居中——`Hit #n` 加粗 + Subject ID 胶囊 +
    描述文本省略号，右侧 identity 胶囊 + 「查看对齐」文字按钮（主题色）；
  - Hit 卡片：白底 `#ffffff`、圆角 12px、1px 边框 `#e5e7eb`，与结果区其他卡片一致。
- **预期效果**：统计信息紧凑成网格、一眼扫读；覆盖条与上方图风格统一。

### 问题 5：左侧参数区 6 个碎卡片，纵向冗长

- **现状**：左列依次是 目标数据库 / 查询序列(FASTA) / 比对算法 / E-value+最大匹配数 /
  查询名称 / Word Size+Gap Open+Gap Extend 共 6 张独立小卡片，卡片间缝隙多、
  每卡内容只有一两行，整列远高于中右两列，产生大量空白。
- **修改 spec**：
  - 合并为 **2 张卡片**：
    - 「查询设置」：目标数据库 + 查询序列(FASTA) + 上传 FASTA 文件按钮；
    - 「比对参数」：比对算法 + E-value 阈值 + 最大匹配数 + 查询名称；
      Word Size / Gap Open / Gap Extend 收进「高级参数」折叠区（默认收起，
      展开箭头旋转动画 200ms）；
  - 卡片内部表单项间距 14~16px，卡片统一平台卡片样式：白底 `#ffffff`、
    圆角 12px、1px 边框 `#e5e7eb` + 轻投影；
  - 左列固定宽 320~360px，中右列自适应；中列「序列实时分析」与右列「最近任务」
    卡片 `align-self: start`，**高度按内容自适应，禁止被 grid 拉伸**（这是中列
    卡片下半截空白的根因之一）。
- **预期效果**：左列长度缩短约一半，三列顶部齐平、底部不再拖出大空白。

### 问题 6：结果摘要条（任务状态 + 六项指标）样式不统一

- **现状**：任务状态徽章单独一行，下面 数据库/算法/Query 长度/命中数/最佳 E-value/
  最佳 Identity 六项摊成一行通栏，下载按钮 XML/JSON/Text 另起一行；数字未做
  tabular-nums。
- **修改 spec**：
  - 合并为一张「结果摘要」卡片：左侧状态徽章（已完成=绿）+ 任务名，
    中部六项 stat（label 12px 次要色在上 + value 16px/600 在下，tabular-nums），
    右侧三个下载按钮（描边小按钮，图标 14px）；
  - 卡片样式同平台统一卡片（白底/圆角 12px/边框 `#e5e7eb`）。
- **预期效果**：结果概览集中一张卡片，下载入口固定右对齐。

## 3. 全局约束

- 在现有 BLAST 页组件基础上修改，**先读现有代码再动手**，禁止推倒重写；
- 不改路由、不改 BLAST 任务提交/轮询/结果解析逻辑、不改 XML/JSON/Text 下载行为；
- 不引入新依赖（如图表库确有必要先说明理由；Graphic Summary 建议手写 SVG/div，
  现有量级无需引入图表库）；
- 配色、圆角、阴影、主题色与平台首页/工作台/任务中心一致，不引入新色系；
  identity 四档色固定为 `#22c55e / #3b82f6 / #f59e0b / #ef4444`；
- 保持响应式：列宽收缩按省略策略处理，不出现横向滚动条；
- 表格规范以任务中心已落地的实现为参照，能复用的样式（表头底色、行高、hover、
  tabular-nums）直接复用，不要另起一套。

## 4. 实施步骤（分阶段，每阶段独立可验）

| 阶段 | 内容 | 依赖 |
|---|---|---|
| 阶段 1 | 问题 1（Coverage bug 排查修复）+ 问题 2（结果表格规范）+ 问题 6（摘要条） | 无，先修数据正确性 |
| 阶段 2 | 问题 3（Graphic Summary）+ 问题 4（序列比对详情） | 阶段 1 的 identity 配色与覆盖条样式 |
| 阶段 3 | 问题 5（左侧参数区合并与三列布局） | 无，可与阶段 2 并行 |

## 5. 编码 Agent 提示词

```text
你是一名资深前端工程师。项目使用 Vue3 + 现有样式体系（组件库以项目实际为准）。

任务：在现有「序列检索 BLAST」页面基础上做视觉优化与 1 个数据 bug 排查。
先阅读现有代码（BLAST 页面组件、结果表格、Graphic Summary、序列比对详情、
任务中心页表格实现），理解当前实现后再修改。禁止推倒重写，禁止改动路由、
BLAST 任务提交/轮询/结果解析逻辑和无关页面，禁止引入新依赖（确有必要先说明理由）。
表格样式规范参照已落地的「任务中心」页表格实现，能复用的直接复用。

## 需要修改的问题（逐条执行）

1. 【Bug：Coverage 显示 0.0%】Hit 的 Query Range 为 1-79（Query 全长 79 bp）、
   Align Len 79 bp，Coverage 却显示 0.0%，表格里 Coverage 单元格还是一条满宽
   灰色空槽。先打印原始字段排查计算口径：正确口径应为 coverage = align_len/query_len
   （本例应约 100%）；重点排查是否误用了 align_len/subject_len（本例 subject
   30,427,671 bp，结果约 0.0003%，与现象吻合）或字段映射错误。修正后显示 0~100%
   一位小数；Coverage 单元格改为「64px 宽轨道（#eef0f2）+ 按值填充的进度条
   + 右侧百分比文字（width 48px、右对齐、tabular-nums、nowrap）」。

2. 【比对结果表格按任务中心规范重做样式】
   - 表头行背景 #f7f8fa，行高收紧至 52~56px，行 hover #f9fafb；
   - 列对齐：#、Subject ID、Length、Identity %、E-value、Bit Score、Align Len、
     Query Range、Subject Range、Coverage 全部居中；Subject Description 长文本列
     左对齐 + max-width 截断 + 省略号 + hover title；组件库支持 column 级 align
     就优先用组件配置；
   - 所有数值列 font-variant-numeric: tabular-nums；
   - Length/E-value/Bit Score/Range 列 white-space: nowrap，Length 列
     min-width 140px（当前 30,427,671 bp 被折成两行，必须单行），
     Range 列 min-width 96px；
   - Identity % 浅绿胶囊统一为 padding 2px 8px、12px、tabular-nums；
   - 分页器：数据不超过 1 页时只显示「共 N 条」，隐藏页码和页大小切换；
     默认页大小 10/20。

3. 【Graphic Summary 精修】
   - Query 轴加刻度：按 Query 长度自适应取整步长（79 bp 示例：10 bp 小刻度、
     50 bp 主刻度标数字；长序列自动切 nice number），轴线 #d1d5db 1.5px，
     刻度标签 11px #6b7280 + tabular-nums；
   - Hit 条高 16px、圆角 3px，每 hit 一行（行高 28px，按 E-value 升序），
     identity 四档配色：≥90% #22c55e、≥70% #3b82f6、≥40% #f59e0b、<40% #ef4444；
   - Hit 条 hover 出 tooltip（Subject ID · Identity · E-value · Query Range），
     点击平滑滚动到对应「序列比对详情」卡片并短暂高亮；
   - 图例缩至 12px/400/正文字体，色块 10x10px 圆角 2px，放标题行右侧；
   - 卡片去掉固定 min-height，高度随内容自适应，消除底部大片空白；
   - 左列标签（Query/Chr1）宽 88px、12px 次要色右对齐，与图区基线对齐。
   用 SVG 或 div 实现均可，不引入图表库。

4. 【序列比对详情精修】
   - 统计区从稀疏的 label:value 通栏长行改为 stat 网格：
     grid-template-columns: repeat(auto-fit, minmax(160px, 1fr))，
     每项 label 12px 次要色在上、value 14px/500 在下，value 加 tabular-nums；
   - 「Query 覆盖位置」条与 Graphic Summary 共用轨道样式：轨道 #eef0f2、
     覆盖段按 identity 档位着色、高 10px、圆角 3px，两端标起止坐标（11px 次要色）；
   - Hit 头部一行 flex 垂直居中：Hit #n 加粗 + Subject ID 胶囊 + 描述省略，
     右侧 identity 胶囊 + 「查看对齐」主题色文字按钮；
   - Hit 卡片白底、圆角 12px、1px 边框 #e5e7eb。

5. 【左侧参数区 6 卡合并为 2 卡】
   - 「查询设置」卡：目标数据库 + 查询序列(FASTA) + 上传 FASTA 按钮；
   - 「比对参数」卡：比对算法 + E-value 阈值 + 最大匹配数 + 查询名称，
     Word Size/Gap Open/Gap Extend 收进「高级参数」折叠区（默认收起）；
   - 卡片统一：白底 #ffffff、圆角 12px、1px 边框 #e5e7eb + 轻投影，
     表单项间距 14~16px；
   - 左列固定宽 320~360px；中列「序列实时分析」和右列「最近任务」卡片
     align-self: start，高度按内容自适应，禁止被 grid 拉伸（当前中列卡片
     下半截空白就是拉伸造成的）。

6. 【结果摘要条整合为一张卡片】
   - 一张「结果摘要」卡：左侧状态徽章（已完成=绿）+ 任务名；中部六项 stat
     （数据库/算法/Query 长度/命中数/最佳 E-value/最佳 Identity，label 12px 次要色
     在上 + value 16px/600 在下，tabular-nums）；右侧 XML/JSON/Text 三个描边
     小按钮右对齐；
   - 卡片样式与平台统一卡片一致。

## 全局约束

- 配色、圆角、阴影、主题色与平台首页/工作台/任务中心一致，不引入新色系；
- 保持响应式，列宽收缩按省略策略处理，不出现横向滚动条；
- 不改 BLAST 执行与下载功能行为；折叠区、tooltip、点击滚动为纯展示层增强。

## 验收标准（逐条自检）

- [ ] Coverage 显示与 align_len/query_len 一致（全长命中约 100%），进度条按值填充
- [ ] 结果表格与任务中心表格同风格：表头 #f7f8fa、短值列居中、长文本列左对齐省略、
      数值 tabular-nums、Length 单行不折行、行高 52~56px
- [ ] 1 条数据时分页器只剩「共 N 条」
- [ ] Graphic Summary 有刻度可读、hit 条 hover 出 tooltip、点击滚动到详情、
      卡片无底部空白、图例 12px
- [ ] 详情统计区为 stat 网格，不再摊成稀疏长行；覆盖条与上图同风格
- [ ] 左侧合并为 2 张卡片，高级参数默认折叠；三列顶部齐平、卡片不被拉伸
- [ ] 结果摘要一张卡，下载按钮右对齐
- [ ] BLAST 提交、轮询、下载、查看对齐功能与改前完全一致
- [ ] 桌面与较窄宽度下无布局破损、无横向滚动

完成后简述：每个问题对应的修改文件与关键属性改动；问题 1 必须说明根因
（覆盖率在哪里被算错、原始字段是什么）。
```

## 6. 验收 Checklist

| 项 | 验收点 | 通过标准 |
|---|---|---|
| 1 | Coverage 数值 | = align_len/query_len，全长命中 ≈100%，进度条按值填充 |
| 2 | 表格规范 | 与任务中心同风格：表头底色、列居中、行高、hover、tabular-nums |
| 3 | Length 折行 | `30,427,671 bp` 单行完整显示 |
| 4 | 分页器 | 单页数据只显示「共 N 条」 |
| 5 | Graphic Summary | 刻度可读、tooltip、点击联动、无底部空白、图例 12px |
| 6 | 详情统计区 | stat 网格紧凑排列，覆盖条与 Graphic Summary 同风格 |
| 7 | 左侧参数区 | 2 张卡片、高级参数折叠、三列顶部齐平、卡片不拉伸 |
| 8 | 结果摘要 | 单卡片、六项 stat、下载按钮右对齐 |
| 9 | 功能回归 | 提交/轮询/下载/查看对齐行为不变 |
| 10 | 响应式 | 桌面与较窄宽度无布局破损、无横向滚动 |

## 7. 风险与回退

- **Coverage 修复方向风险**：改前先在控制台打印 query_len / subject_len / align_len
  原始值确认口径，避免把对的改错；若后端 XML/JSON 本身缺 coverage 字段，前端按
  align_len/query_len 兜底计算并在代码注释中说明；
- **表格列宽**：11 列 + min-width 约束在中等宽度（<1440px）可能触发横向滚动，
  此时按任务中心既有策略处理（容器内横向滚动或次要列省略），不要压缩 Length 列；
- **点击滚动联动**：Graphic Summary 与详情卡片的锚点 id 需与 hit 序号一一对应，
  多 hit 场景重点自测；
- **卡片合并**：左侧表单组件的校验/事件绑定保持原样，只做 DOM 归并，
  不改字段 key 与提交参数结构；
- 本轮改动集中在 BLAST 页，与任务中心等页面无代码耦合（仅复用样式约定），
  若线上出问题按文件级回退即可。
