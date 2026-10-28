# Multi-Agent 提示词框架现状与 Domain Pack 重构设计

> 日期:2026-08-06 · 范围:`chat_service.py` 调度认知层 + `data/ai/` 提示词体系
> 目标:让 multi-agent 对新分析任务类型的适配 = **加数据(YAML),不改调度代码、不补调度 prompt**

---

## 1. 背景与问题定义

当前 multi-agent(超频轮/Overdrive)只在 rna-seq 场景做过完整验证。排查发现:执行骨架(波次调度、manifest 状态机、fan-out 隔离、摘要协议)是任务无关的,但**认知层**(识别意图 → 澄清 intake → 选派专家 → 兜底分工)把大量任务特定知识写死在 Python 关键词表和调度 prompt 条款里。同时 agent 提示词近 10 天体积涨 2–6 倍(git 证据),增长模式是"每类新任务/新坑 → 往 prompt 塞一段"。

本文给出:

- §2 当前提示词框架全景(分层、清单、膨胀证据);
- §3 问题精确定位(7 个任务知识渗漏点,全部带行号);
- §4 **Domain Pack 完整 schema 定义**(核心交付物);
- §5 五个函数 + 两个关联函数的重构方案(现状行为 → 新行为 → schema 映射 → 伪代码);
- §6 DomainRegistry 服务设计;
- §7 prompt 收敛(共享段抽取);
- §8 回归测试策略(行为等价用例);
- §9 分阶段实施计划与验收标准。

---

## 2. 当前提示词框架全景

### 2.1 分层结构

```
┌─────────────────────────────────────────────────────────┐
│ L0 调度层 prompt(代码内嵌,chat_service.py)              │
│   ROUTER_SYSTEM_PROMPT(:203-229)     路由分派            │
│   OVERDRIVE_MANAGER_PROMPT(:258-282) 超频 Manager 规划   │
│   OVERDRIVE_SUMMARY_SYSTEM_PROMPT(:284-292) 汇总         │
│   各 suffix(:186/:192/:231/:240/:1168-1196)              │
├─────────────────────────────────────────────────────────┤
│ L1 Agent 人格 prompt(data/ai/prompts/*.md)               │
│   由 agent YAML 的 prompt_file 挂载(agent_loader.py:97)  │
├─────────────────────────────────────────────────────────┤
│ L2 共享片段(目前靠复制粘贴,无 include 机制)              │
│   沙盒目录规范 ~27 行 × 6 文件;装包协议 × 5 文件          │
├─────────────────────────────────────────────────────────┤
│ L3 按需加载知识(架构正确,利用率低)                      │
│   skill 市场 36 技能 1.3MB(use_skill 按需加载)           │
│   pgvector 知识库(链路完整,内容≈只有用户个人笔记)        │
├─────────────────────────────────────────────────────────┤
│ L4 结构化声明(data/ai/*.yaml, flows/*.yaml)              │
│   capability_tags / accepts_inputs / produces_outputs /  │
│   trigger_hints / handoff —— 纯数据,设计合理             │
└─────────────────────────────────────────────────────────┘
```

### 2.2 提示词清单与膨胀证据(git:faa06f7 07-26 → HEAD 08-05)

| 文件 | 行/字节 | 10 天涨幅 | 任务特定内容 |
|---|---|---|---|
| `data/ai/prompts/router.md` | 51 / 4.4KB | — | 少量判歧规则 |
| `general.md` | 155 / 11.2KB | 3.6× | ~70% 是平台协议(应从领域 prompt 剥离) |
| `rnaseq.md` | 119 / 8.5KB | 2.2× | DESeq2/edgeR 方法论 ~30% |
| `scrna.md` | 103 / 7.4KB | 2.4× | QC/HVG/Leiden ~40% |
| `code.md` | 146 / 9.9KB | 3.2× | 混合 |
| `visualization.md` | 333 / 18.7KB | **6.4×** | ggtree 输入确认(:17-23)、调色板 hex 清单(:48-62) |
| `mcp_builder.md` | 456 / 19.9KB | — | 生成流程+AST 安全规则 |
| `studio/system.md` | 91 / 8KB | — | 与 agent prompt 大段重复 |

**膨胀的典型形态**:`visualization.md:17-23` 新增"系统发育树与 ggtree 输入确认"整节——纯任务特定知识硬编码进系统 prompt;沙盒目录规范逐字出现在 6 个文件,修一处改六处。

---

## 3. 任务知识渗漏点精确定位

| # | 位置 | 渗漏内容 | 性质 |
|---|---|---|---|
| S1 | `chat_service.py:345-352` `_is_overdrive_planning_request` | "规划类请求"识别 = 规划词 × (rna/组学/基因/tp53/突变) | Python 关键词表 |
| S2 | `chat_service.py:355-447` `_analysis_intake_questions` | 模态问题(bulk/单细胞/空间写死)、TP53 分组问题特判(:419-431)、样本量问题 | Python 关键词表 |
| S3 | `chat_service.py:455-501` `_extract_overdrive_intake_slots` | 树任务槽位提取:task_type/input_format/sequence_type/msa_status/tree_method/tree_scope,全是 phylo 专场 | Python 关键词表 |
| S4 | `chat_service.py:504-570` `_filter_overdrive_questions` | 树任务的分支互斥与"已答不再问"过滤(序列类型/MSA/建树软件) | Python 关键词表 |
| S5 | `chat_service.py:667-717` `_overdrive_capability_profile` | rnaseq/scrna/viz/code/general 五档 profile if-elif | Python 硬编码 |
| S6 | `chat_service.py:720-813` `_default_overdrive_assignments` | 树任务→可视化专家(:758-769)、单细胞/bulk→领域 agent(:753-756)、兜底 task 文案 | Python 关键词表 |
| S7 | `chat_service.py:634-653` `_minimize_overdrive_assignments` | 写死 `task_type == "tree_visualization"` 时只留可视化专家 | Python 硬编码 |
| P1 | `chat_service.py:276` Manager prompt 规则 10 | 整段系统发育树规则(分支互斥、禁问建树软件) | 调度 prompt 任务条款 |
| P2 | `chat_service.py:221` Router prompt 规则 9 | RNA-seq vs scrna 判歧规则 | 调度 prompt 任务条款 |

S1–S7 是本次重构对象;P1–P2 随之从 prompt 中删除,改为数据注入。

---

## 4. Domain Pack 完整 Schema 定义

### 4.1 设计原则

1. **一个领域一个文件**:`data/ai/domains/<domain>.yaml`,mtime 热重载,加载失败不影响其他领域(与 `flow_registry.py` 同一模式);
2. **schema 只描述"这个领域要澄清什么、已确认什么、怎么选派",不含执行逻辑**——逻辑全部留在通用代码里;
3. 现有 rna-seq/组学与 phylo 行为是 schema 的**第一个迁移实例**,迁移后行为必须等价(§8 回归用例保证);
4. 全局通用部分(规划词表、代码/可视化兜底)不进 domain pack,留在代码默认值或全局配置。

### 4.2 Schema 全量定义

```yaml
# ============ data/ai/domains/<domain>.yaml ============
# Domain Pack v1 —— 领域认知声明(供超频认知层消费)

# ---- 身份 ----
domain: phylo                    # 必填,全局唯一,小写 [a-z0-9_-]+
version: 1                       # 必填,schema 版本,当前恒为 1
display_name: 系统发育分析        # 必填,面向日志/调试
enabled: true                    # 可选,默认 true;false 时注册但不参与匹配

# ---- 领域识别:用户消息是否属于本领域 ----
match:
  domain_markers:                # 必填,≥1;消息小写子串命中任一即"属于本领域"
    - 系统发育
    - 进化树
    - phylogenetic
    - newick
  planning_markers: []           # 可选,领域附加的规划词;与全局规划词表取并集
                                 # (全局表: 计划/方案/研究设计/研究路线/挖掘/新颖发现)

# ---- intake:该领域做规划类请求时需要澄清的槽位 ----
intake:
  # 4.2.1 澄清问题模板(替代 _analysis_intake_questions 的硬编码问题)
  questions:
    - id: modality               # 必填,问题 id(用于日志)
      when_markers_absent:       # 可选:消息中这些词全都没出现时才问
        - bulk
        - 单细胞
        - 空间
      question: "你的数据属于哪种模态?这会决定后续分析路线和可分配的专家。"
      options: ["bulk RNA-seq", "单细胞 RNA-seq", "空间转录组", "多组学/其他"]
    - id: grouping
      when_markers_present: ["分组"]        # 可选:与 absent 条件可同时声明(都满足才问)
      when_markers_absent: ["突变 vs", "野生型", "高表达", "敲除", "对照", ...]
      question: "这两个{subject}分组是如何定义的?"   # {subject} 见 subject_rules
      options: ["病例 vs 对照", "治疗/干预 vs 对照", "高值 vs 低值", "其他定义"]
      subject_rules:             # 可选:按消息关键词改写问题主语与选项(替代 TP53 特判)
        - markers: ["tp53"]
          subject: "TP53 "
          options: ["TP53 突变 vs 野生型", "TP53 高表达 vs 低表达",
                    "TP53 敲除/过表达 vs 对照", "其他定义"]

  # 4.2.2 槽位提取器(替代 _extract_overdrive_intake_slots)
  slots:
    - key: task_type             # 必填,槽位名;写入 sandbox_meta.overdrive_intake
      values:
        - value: tree_visualization
          markers:               # 消息去空格小写后子串命中
            - 处理/美化已有树
            - 处理已有树
            - 已有newick
            - 已有树文件
        - value: phylogeny_construction
          markers: ["从头建树", "从头构建系统发育树"]
      priority: first_match      # 可选:first_match(默认,按 values 顺序)| last_match
    - key: input_format
      values:
        - value: treefile
          markers: ["treefile", ".treefile"]
        - value: newick
          markers: ["newick", ".nwk", ".newick", ".tree"]
        - value: contree
          markers: [".contree", "contree文件"]
    # ... sequence_type / msa_status / tree_method / tree_scope 同构

  # 4.2.3 问题过滤规则(替代 _filter_overdrive_questions)
  question_filters:
    - when_slot_is: {task_type: tree_visualization}   # 条件:槽位=值
      drop_question_markers:                          # Manager 产出的问题文本含这些词则丢弃
        [序列类型, 蛋白质序列, 氨基酸, 多序列比对, msa, 建树软件, 建树算法, iqtree]
    - when_slot_missing: [task_type]                  # 条件:槽位未确认且存在分支待定问题
      requires_pending_question_markers: [核心需求, 从头构建, 处理/美化已有树]
      drop_question_markers: [序列类型, msa, 建树软件, iqtree]
    - when_slot_present: [input_format]               # 条件:槽位已确认 → 不再问对应问题
      drop_question_markers: [输入数据是什么格式, 输入格式]
    - when_slot_present: [sequence_type]
      drop_question_markers: [序列类型]
    - when_slot_present: [msa_status]
      drop_question_markers: [多序列比对, msa, 完成比对]
    - when_slot_present: [tree_method]
      drop_question_markers: [建树软件, 建树算法, iqtree]

# ---- 兜底分工(替代 _default_overdrive_assignments / _minimize_overdrive_assignments) ----
assignments:
  rules:
    - id: tree-viz-only
      when_slot_is: {task_type: tree_visualization}
      agent_match: ["agent-viz", "visualization", "可视化"]   # 对 catalog 项的
                                              # agent_id+name+category 小写子串匹配,同现状
      minimize_to_single: true               # true → 命中后仅保留该任务并清空 depends_on
                                             # (等价于 _minimize_overdrive_assignments 的行为)
      task_id: tree-visualization
      task: "处理用户已有的系统发育树文件,先验证 Newick/treefile 可解析性,再完成树注释、美化和 publication-ready 图表交付;不要重新执行序列比对或建树。"
    - id: domain-plan
      when: planning_or_analysis             # 内置条件枚举:planning_or_analysis
      agent_match: ["agent-phylo", "系统发育"]
      task_id: domain-analysis
      task: "直接完成本领域的分析计划、统计方法、关键参数、风险和解释边界。"

# ---- Manager/Router 提示注入(替代 prompt 写死条款 P1/P2) ----
prompt_injections:
  manager_notes: |                 # 匹配到本领域时,作为"已确认的领域约束"数据段
    系统发育树任务必须先区分"从序列建树"和"处理已有树"。已确认 task_type 后,
    互斥分支的问题不得放在同一批 questions 中;tree_visualization 下优先只分配
    可视化专家,只有实际解析/脚本执行不可缺少时才增加代码专家。
  router_notes: |                  # 匹配时注入 Router catalog 的附加判歧说明
    用户明确写出 RNA-seq、bulk RNA 或转录组且无单细胞锚点时,必须选择 agent-rnaseq。
```

### 4.3 字段约束与校验规则(DomainRegistry 加载期校验)

| 规则 | 失败处理 |
|---|---|
| `domain` 全局唯一,重复拒绝 | 后加载文件记入 errors,保留先加载 |
| `version` 必须为 1(未知版本拒绝) | 记入 errors 并跳过该文件 |
| `match.domain_markers` 非空 | 记入 errors 并跳过 |
| `slots[].values[].value` 在同一 key 内唯一 | 记入 errors 并跳过该 key |
| `assignments.rules[].when` 仅允许枚举 `{planning_or_analysis}`,或与 `when_slot_is` 二选一 | 记入 errors |
| `prompt_injections.manager_notes` ≤ 800 字符(防把 pack 当 prompt 垃圾场) | 截断并 warning |
| 所有 markers 按"去空格 + lower"规范化后存储 | 加载时统一处理 |
| `question_filters` 中引用的槽位 key 必须在 `slots` 中声明 | 记入 errors |

### 4.4 迁移实例一:`data/ai/domains/omics.yaml`(承接 S1/S2/S6 的组学部分)

```yaml
domain: omics
version: 1
display_name: 组学研究规划
match:
  domain_markers: [rna, 转录组, 表达, 基因, 突变, 分组, 组学, 细胞, 样本,
                   蛋白组, 代谢组, 甲基化, atac, chip, 空间组学]
intake:
  questions:
    - id: modality
      when_markers_absent: [bulk, 单细胞, 单 cell, scrna, 空间, spatial, snrna, 蛋白组]
      question: "你的数据属于哪种模态?这会决定后续分析路线和可分配的专家。"
      options: ["bulk RNA-seq", "单细胞 RNA-seq", "空间转录组", "多组学/其他"]
    - id: grouping
      when_markers_present: ["分组"]
      when_markers_absent: [突变 vs, 突变与, 野生型, 高表达, 低表达, 敲除, 过表达,
                            对照, 病例, 治疗前, 治疗后, 响应, 不响应, 敏感, 耐药, 组定义]
      question: "这两个{subject}分组是如何定义的?"
      options: ["病例 vs 对照", "治疗/干预 vs 对照", "高值 vs 低值", "其他定义"]
      subject_rules:
        - markers: ["tp53"]
          subject: "TP53 "
          options: ["TP53 突变 vs 野生型", "TP53 高表达 vs 低表达",
                    "TP53 敲除/过表达 vs 对照", "其他定义"]
    - id: sample_size
      when_markers_absent: [样本, 细胞, "n=", 病例, 队列]
      question: "每组大约有多少样本或细胞?目前可提供哪些输入(原始测序、count 矩阵或已处理对象)?"
      options: ["已有 count/表达矩阵", "已有单细胞对象(h5ad/rds)",
                "只有原始测序数据", "暂未确定"]
assignments:
  rules:
    - id: scrna-domain
      when: planning_or_analysis
      when_message_markers: [单细胞, scrna]
      agent_match: ["agent-scrna", "单细胞分析师"]
      task_id: domain-analysis
      task: "直接完成本领域的分析计划、统计方法、关键参数、风险和解释边界。"
    - id: rnaseq-domain
      when: planning_or_analysis
      when_message_markers: [bulk, rna-seq, 转录组, 表达矩阵]
      agent_match: ["agent-rnaseq", "rna-seq 分析师"]
      task_id: domain-analysis
      task: "直接完成本领域的分析计划、统计方法、关键参数、风险和解释边界。"
prompt_injections:
  router_notes: "用户明确写出 RNA-seq、bulk RNA 或转录组,且无单细胞、scRNA、Seurat、Scanpy、Cell Ranger 锚点时,必须选择 agent-rnaseq。"
```

> schema 补充:`assignments.rules[]` 增加可选 `when_message_markers`(消息子串条件),与 `when_slot_is` 可叠加,全部满足才命中。规则按文件内顺序求值,先命中先生效。

### 4.5 迁移实例二:`data/ai/domains/phylo.yaml`

即 §4.2 的示例全文,承接 S3/S4/S6-tree/S7 与 P1 的全部行为。

### 4.6 Agent 能力 profile 迁移(S5,不属于 domain pack)

`_overdrive_capability_profile` 的五档 if-elif 改为**纯读 agent YAML features**。在 `data/ai/<agent>.yaml` 的 `features:` 下新增字段:

```yaml
features:
  default_role: "bulk RNA-seq 领域方案与统计分析"        # 新增
  capability_scope: [bulk RNA-seq, QC, 差异表达, 通路富集, 网络分析]  # 新增(优先于 capability_tags)
  capability_tags: [...]   # 保留兼容:capability_scope 缺省时回落到它
```

迁移表(按现有 if-elif 逐字搬出,rnaseq.yaml 的 capability_scope 即 :680-681 的内容;scrna/viz/code/general 同理);未填写的 agent 落入现 else 分支文案(:704-705),行为不变。

---

## 5. 函数级重构方案

### 5.1 总览

```
现状:五个函数各自持有任务知识(Python 关键词表)
目标:五个函数变成 DomainRegistry 的"通用求值器",不含任何领域字面量
```

### 5.2 `_is_overdrive_planning_request`(:345-352)

- 现状行为:全局规划词 ∧ 领域词(rna/组学/tp53…)。
- 新行为:`global_planning_markers(代码常量) ∧ registry.any_domain_matches(content)`。
- 伪代码:
  ```python
  def _is_overdrive_planning_request(content: str) -> bool:
      normalized = content.lower()
      return any(m in normalized for m in _GLOBAL_PLANNING_MARKERS) and \
             get_domain_registry().matches_any(normalized)
  ```
- 注意:`matches_any` 同时考虑各 pack 的 `planning_markers` 附加词(并入第一组判断)。无 domain 命中时返回 False——**未知任务类型不再被误判为规划请求**,Manager 走通用规划+主动提问路径(这正是期望的降级)。

### 5.3 `_analysis_intake_questions`(:355-447)

- 现状行为:规划词∧组学词 → 模态/分组(含 TP53 特判)/样本三问。
- 新行为:遍历所有 enabled pack;对每个 pack:若 `planning∧domain` 命中,按其 `intake.questions[]` 逐条求值(`when_markers_present`/`when_markers_absent`/`subject_rules` 按 §4.2 语义),收集问题(去重按 `id`,上限沿用现有 Manager questions 1–3 的约束)。
- TP53 特判(:419-431)由 `subject_rules` 数据化,代码里不再出现 "tp53"。
- 多领域同时命中时:按 `domain` 字母序取第一个 pack 的问题(确定性),并在 debug 日志记录多命中。**不允许**两个 pack 的问题混排(避免互斥分支同批出现,P1 的语义)。

### 5.4 `_extract_overdrive_intake_slots`(:455-501)

- 现状行为:6 个 phylo 槽位的 markers→value。
- 新行为:对每个命中领域的 `intake.slots[]` 求值;同一 key 多个 pack 冲突时**最新明确回答覆盖旧值**的现有语义保留(`slots = dict(existing or {})` 后按 pack 顺序更新);`priority: first_match` 对应现有 `if/elif` 顺序语义。
- 泛化点:现有代码对 `.treefile` 等做了 `in normalized` 子串判断,新实现统一为"markers 规范化后子串匹配",不再区分前缀/后缀写法。

### 5.5 `_filter_overdrive_questions`(:504-570)

- 现状行为:三种过滤(分支待定禁问建树细节 / tree_visualization 禁问 / 槽位已答不再问)。
- 新行为:遍历所有 pack 的 `question_filters`,按条件类型求值:
  - `when_slot_is` → slots 值相等;
  - `when_slot_present` → key 存在;
  - `when_slot_missing` + `requires_pending_question_markers` → 槽位缺失且当前批次存在分支待定问题(对应现 `branch_question_pending` 逻辑 :509-515)。
- 过滤逻辑(问题文本去空格小写后子串命中 `drop_question_markers` 即丢弃)与现状完全一致。

### 5.6 `_overdrive_capability_profile`(:667-717)

- 现状行为:五档 if-elif + YAML `capability_tags` 覆盖。
- 新行为:纯 YAML 读取:`features.capability_scope`(新)> `features.capability_tags`(兼容)> else 分支文案;`default_role` 从 `features.default_role` 读,缺省用 else 文案。if-elif 整段删除;`accepts_inputs`/`produces_outputs`/`default_stage` 透传逻辑(:710-716)保留不变。

### 5.7 `_default_overdrive_assignments`(:720-813)与 `_minimize_overdrive_assignments`(:634-653)

- 现状行为:树→viz 单任务;planning+领域命中→领域 agent;代码/可视化关键词兜底;general 兜底。
- 新行为分两段:
  1. **领域规则段**(数据化):对每个 pack 的 `assignments.rules[]` 按序求值(`when_slot_is`/`when_message_markers`/`when: planning_or_analysis`),命中即用 `agent_match` 在 catalog 查找(查找逻辑同现 `find()`),按模板构造 assignment;`minimize_to_single: true` 的规则命中时**直接返回单任务列表**(吞并 `_minimize_overdrive_assignments` 的行为,该函数删除)。
  2. **通用兜底段**(保留在代码):code/viz 关键词分支(:775-792)与 general 兜底(:804-812)是任务无关的,保留为代码默认值;task 文案保持不变。
- 调用点调整:`_minimize_overdrive_assignments` 的调用处(超频轮主循环)改为在 `_default_overdrive_assignments` 内部处理;Manager 产出分工后的 minimize 语义由 `minimize_to_single` 规则在归一化后统一执行(保持现有调用时序:Manager 分工 → normalize → minimize)。

### 5.8 prompt 修改点(P1/P2)

- `OVERDRIVE_MANAGER_PROMPT`(:258-282):删除规则 10;规则 3 的"典型关键信息包括数据模态(bulk RNA-seq / 单细胞 / 空间组学等)"改为不枚举领域的通用表述。新增占位 `{domain_notes}`:匹配到领域时注入该 pack 的 `prompt_injections.manager_notes`(拼在 `{intake_context}` 之后),无匹配时为空串。
- `ROUTER_SYSTEM_PROMPT`(:203-229):删除规则 9;在 catalog JSON 的每个 agent 条目里新增可选 `routing_notes` 字段,由 registry 按 agent 归属领域注入 `prompt_injections.router_notes`。Router 看到的是**数据**而不是规则条款。

---

## 6. DomainRegistry 服务设计

新文件(遵循项目分层):

- `src/omichub/domain/domains/schema.py`:`DomainPack` pydantic 模型(对应 §4.2 全部字段)+ 校验(§4.3);
- `src/omichub/infrastructure/config/domain_pack_loader.py`:目录扫描、YAML 解析、mtime 热重载、错误收集(模式照抄 `flow_repository.py:109-112` 的"单文件失败不阻断");
- `src/omichub/application/services/domain_registry.py`:单例服务,暴露:
  ```python
  class DomainRegistry:
      def reload_if_changed(self) -> None: ...
      def matches_any(self, normalized_content: str) -> bool: ...
      def match_domains(self, normalized_content: str) -> list[DomainPack]: ...  # 确定性排序
      def intake_questions(self, content: str) -> list[dict]: ...
      def extract_slots(self, content: str, existing: dict) -> dict: ...
      def filter_questions(self, questions: list[dict], slots: dict) -> list[dict]: ...
      def assignment_rules(self, content: str, slots: dict) -> list[AssignmentRule]: ...
      def manager_notes(self, content: str) -> str: ...
      def router_notes_for(self, agent_id: str) -> str: ...  # agent → domain 归属由 agent_match 反查
      @property
      def errors(self) -> list[str]: ...
  ```
- 配置项:`core/config.py` 加 `domains_yaml_dir: str = "data/ai/domains"`(一行,与 `flow_yaml_dir` 同风格);
- agent→domain 归属:agent YAML `features.domain: phylo`(可选字段)显式声明优先;缺省时用 `agent_match` 反推(仅用于 router_notes 注入,不影响路由决策本身)。
- `chat_service.py` 中五个函数改为薄封装,内部委托 `get_domain_registry()`;registry 加载失败/为空时**退化为**:不做 intake 预检、不提取槽位、不做兜底分派——Manager LLM 通用规划路径仍可用(安全降级)。

---

## 7. prompt 收敛(配套止血,独立小任务)

1. 新建 `data/ai/prompts/shared/sandbox_protocol.md`:从 6 个文件中提取逐字重复的"沙盒目录使用规范"(~27 行)+ "装包协议"(conda-meta-mcp 段);
2. `agent_loader.py:_load_single_agent` 加载 `prompt_file` 后统一追加共享段(或 prompt_loader 支持 `{{include: shared/xxx}}` 占位,二选一,推荐前者——改动小);
3. 6 个 agent prompt 删除重复段;`studio/system.md` 同样处理;
4. `visualization.md:17-23`(ggtree 输入确认)与 :48-62(调色板)迁移为 skill `phylo-tree-viz` 与 `chart-palettes`(放 `data/ai/skill_marketplace/`),`visualization.yaml` 挂 `skill_ids`;
5. 护栏约定写入 `data/ai/README.md`:任何 prompt 文件超过 120 行需在 PR 说明为何不能下沉到 skill/knowledge/domain pack。

---

## 8. 回归测试策略(行为等价是验收硬标准)

**先写测试,再重构**:把现有函数的已知输入→输出固化为参数化测试(`tests/unit/test_domain_pack_regression.py`),重构前后跑同一份。

| # | 输入 | 期望(等价于现状) |
|---|---|---|
| R1 | "帮我设计一个 TP53 相关的 rna 挖掘方案" | `_is_overdrive_planning_request` = True |
| R2 | "给我做个代码审查计划" | False(无领域词) |
| R3 | "帮我设计一个 TP53 突变 vs 野生型的 rna 挖掘方案" | intake 含 modality?否(无模态词→含);grouping?否(已含"突变 vs");sample?含 |
| R4 | "设计一个分组研究的组学方案" | grouping 问题出现,无 TP53 主语 |
| R5 | "设计一个 tp53 分组方案" | grouping 问题带 "TP53 " 主语与 TP53 选项 |
| R6 | "处理/美化已有树" | slots.task_type = tree_visualization |
| R7 | "我有一个 .treefile 文件" | slots.input_format = treefile |
| R8 | slots={task_type: tree_visualization} + Manager 提问含"建树软件" | 该问题被过滤 |
| R9 | slots 无 task_type + 批次含"核心需求"分支问题 + "MSA 状态"问题 | MSA 问题被过滤,分支问题保留 |
| R10 | agent-rnaseq profile | default_role/scope 与现 :679-681 逐字一致 |
| R11 | 未知 agent(xyz) | else 文案 :704-705 |
| R12 | "处理已有树"+ Manager 未分工 | 单任务 → viz agent,task_id=tree-visualization |
| R13 | "做个单细胞分析计划"+ Manager 未分工 | 单任务 → agent-scrna |
| R14 | "写个 python 脚本"(非规划) | code 兜底分支 |
| R15 | 空 domains 目录(registry 为空) | 五函数全部安全降级,不抛异常 |

另补:DomainRegistry 加载校验测试(重复 domain 拒绝、坏 YAML 不阻断、热重载生效)。

---

## 9. 分阶段实施计划

| 阶段 | 内容 | 涉及文件 | 验收 |
|---|---|---|---|
| P0 | 回归测试先行(§8 R1–R15 对现状全部通过) | `tests/unit/test_domain_pack_regression.py` | 测试绿 |
| P1 | schema + loader + DomainRegistry(§4/§6) | 3 个新文件 + `core/config.py` | 加载校验测试绿 |
| P2 | 迁移 omics/phylo 两个 pack + 12 个 agent YAML 的 `default_role/capability_scope`(§4.4–4.6) | `data/ai/domains/*.yaml`、`data/ai/*.yaml` | 目检 + 加载无 errors |
| P3 | 五函数重构为 registry 委托(§5.2–5.7),删除 `_minimize_overdrive_assignments` | `chat_service.py` | R1–R15 全绿 |
| P4 | Manager/Router prompt 去任务条款 + `{domain_notes}`/`routing_notes` 注入(§5.8) | `chat_service.py:203-292` | 手测 rna-seq 路由、phylo 超频行为等价 |
| P5 | prompt 收敛(§7) | `data/ai/prompts/`、agent_loader | prompt 总量降 ≥30%,行为不变 |

**完成定义**:新增一个分析任务类型(如 WGS)时,调度认知层的适配 = 新增 `data/ai/domains/wgs.yaml` 一个文件;`chat_service.py` 与调度 prompt 零改动;未知任务类型走"通用规划 + 主动提问"降级而非关键词误命中。
