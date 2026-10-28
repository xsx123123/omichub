# OmicHub 技能加载方案与助手管理页美化实现计划

## 一、背景与目标

OmicHub 目前的"导入技能"弹窗只支持「URL 拉取 JSON 配置」和「JSON 粘贴」两种方式，与业界主流的 Agent Skills 标准（SKILL.md 文件夹格式）不兼容，外部生态技能无法直接导入；同时助手模板编辑页（抽屉式表单）视觉粗糙、信息层级弱。本文档分两部分：

1. **Part A**：调研业界主流 skills 加载方式 → 评审现有导入界面 → 给出最适合本平台的加载方案与改造提示词。
2. **Part B**：助手管理页（编辑助手模板抽屉）美化提示词。

---

## 二、Part A：Agent Skills 加载方式调研与平台方案

### 2.1 业界现状调研结论

**1. 事实标准：SKILL.md 文件夹格式（Anthropic Agent Skills，2025 年 10 月发布）**

一个技能就是一个文件夹，核心是带 YAML frontmatter（`name` + `description`）的 `SKILL.md`，可选携带 `scripts/`、`references/`、`assets/`。该格式已被 Claude Code、Codex、Cursor、OpenClaw 等主流编码 Agent 兼容，是跨平台事实标准 [^1^][^2^]。

**2. 核心加载机制：渐进式披露（Progressive Disclosure），三层加载**

| 层级 | 内容 | 加载时机 | 上下文开销 |
|---|---|---|---|
| L1 元数据 | name + description | 启动时常驻系统提示 | 约 100 tokens/技能 |
| L2 指令正文 | SKILL.md 正文（建议 <5000 tokens） | 任务与描述匹配时加载 | 1000~5000 tokens |
| L3 资源/脚本 | references/、scripts/、assets/ | 用到时才读或执行；脚本代码不进上下文，只有输出进 | 按需 |

实测对比：50 个技能的初始上下文消耗仅约 5000 tokens；某 MCP 服务直接全量加载工具 schema 消耗 16000 tokens，改用 Skills 包装后初始仅 500 tokens [^3^][^4^][^5^]。

**3. MCP 全量注入的教训与"懒加载"趋势**

MCP 在连接时通过 `tools/list` 注入全部工具 JSON Schema，单个 Playwright MCP 就占 200k 上下文的 8%；20~30 个工具全量注入可达 50~100KB，造成上下文膨胀、成本上升、模型注意力分散 [^6^][^7^]。因此业界正在把"注册元数据、按需加载"模式推广到一切上下文组件：Claude Code 的 ToolSearch 已证明该模式可节省 85% 工具 schema token，社区正在进一步推动 SkillSearch（技能也懒加载）和 MCP 延迟连接 [^8^]；LobeHub 也已提出 Progressive Tool Loading 的 RFC，将渐进式披露从 Skills 推广到 Tools [^7^]。

**4. 分层定位：三者互补而非互替**

2026 年的主流实践是三层架构：AGENTS.md / 规则文件负责环境级背景（"我们怎么写代码"），Skills 负责可调用的工作流（"怎么做一次发布"），MCP 负责实时数据与工具访问。Skills 封装知识与流程，MCP 提供动作与数据 [^2^][^9^]。

**5. 工程化形态**

- 单 Agent/少技能：进程内 Skill Registry（启动扫描目录、解析 frontmatter、注入索引即可）[^10^]。
- 多 Agent 平台（本平台场景）：集中式技能库 + 按助手挂载子集 + 运行时按渐进式披露加载；技能可独立更新而无需重新部署 [^10^]。
- 安全治理：技能应像代码依赖一样对待——安装前审查、版本锁定、信任分级，已发生真实供应链攻击 [^4^]。

### 2.2 现有"导入技能"界面评审

现有弹窗为「URL 拉取 / JSON 粘贴」双 Tab，填 GitHub raw JSON URL 后拉取解析。

**可取之处**：远程拉取 + 手动粘贴双通道的思路是对的，交互轻量。

**不合适之处**：

1. **格式不兼容生态**：以"单个 JSON 配置"为中心，与业界 SKILL.md 文件夹标准（含 frontmatter + scripts/references/assets）不兼容，GitHub 上数千个现成技能无法直接导入。
2. **入口太单一**：没有本地文件/zip 上传，没有技能市场/列表浏览，用户必须自己拼 raw URL。
3. **无导入前校验与预览**：拉取后看不到技能的名称、描述、依赖工具、是否含可执行脚本，点"导入"即入库，缺少安全把关。
4. **无版本管理**：无法锁定版本、无法感知上游更新。
5. **与"挂载到助手"割裂**：导入进库与在助手模板里勾选挂载是两套裸下拉（当前"挂载技能"只有一个空下拉），技能多了无法检索、看不到描述。

### 2.3 最适合本平台的加载方法（推荐方案）

**总原则：存储对齐 SKILL.md 开放格式，运行时采用三层渐进式披露，导入多入口 + 先审后入。**

**① 存储层——技能库标准化**

- 平台技能库中的每个技能 = 一个 SKILL.md 标准文件夹：`SKILL.md`（frontmatter 含 name/description，正文为指令）+ 可选 `scripts/`、`references/`、`assets/`。
- 存量 JSON 配置型技能做一次性迁移：JSON 中的提示词/流程字段映射为 SKILL.md 正文，元信息映射为 frontmatter。

**② 运行时——三层渐进式披露加载**

- L1：助手被挂载的技能，仅把 `name + description` 注入该助手的系统提示（每技能约 100 tokens），几十个技能也无压力。
- L2：模型判断任务与某技能描述匹配时，调用内部 `use_skill(name)` 加载该技能 SKILL.md 正文进入上下文。
- L3：正文引用到的 references/scripts/assets 按需读取或执行；脚本代码不进上下文，只回收执行输出。
- 助手挂载的技能集合 = 该助手可见的技能索引，未挂载的技能不进上下文。

**③ 导入层——四个入口（替代现有双 Tab）**

1. **技能市场/列表浏览**：平台内置技能列表（卡片：名称、描述、作者、版本、是否含脚本），一键安装，作为默认主入口。
2. **GitHub 仓库/文件夹 URL**：粘贴仓库或子目录链接（不必是 raw JSON），后端拉取整个文件夹并解析 SKILL.md。
3. **本地上传**：支持 zip 包或文件夹上传。
4. **JSON 粘贴**：保留作为兼容入口（老格式）。

四个入口统一进入**导入预览页**：展示解析结果（名称、描述、包含文件清单、是否含可执行脚本的安全提示、版本号），用户确认后才入库。入库时记录版本/commit，支持"检查更新"。

**④ 治理层**

- 导入前静态校验：frontmatter 必填字段、SKILL.md 正文长度（<5000 tokens 提示拆分）、脚本白名单/危险命令扫描。
- 版本锁定 + 上游更新提醒。
- 助手维度启停开关；含脚本的技能在挂载选择器中带"含可执行脚本"标识。

### 2.4 提示词 A：技能导入与加载机制改造（粘给编码 Agent）

```text
你是一名资深全栈工程师。项目为 OmicHub 多助手平台（沿用项目现有前后端技术栈与组件库，
先读代码确认，不要引入新组件库）。

任务：改造技能系统。先阅读现有"导入技能"弹窗、技能存储模型、助手"挂载技能"选择器、
以及运行时拼装系统提示词的代码，理解现状后再修改。禁止重构无关模块。

## 一、技能存储对齐 SKILL.md 标准
1. 技能模型从"单个 JSON 配置"升级为 SKILL.md 文件夹结构：frontmatter
   （name/description 必填）+ Markdown 正文 + 可选 scripts/、references/、assets/。
2. 提供存量 JSON 技能的一次性迁移脚本：提示词/流程字段 → SKILL.md 正文，
   元信息 → frontmatter。

## 二、导入入口改造（替换现有"URL 拉取 / JSON 粘贴"弹窗）
1. 四入口：技能市场列表（卡片含名称/描述/作者/版本/是否含脚本，一键安装）、
   GitHub 仓库或子目录 URL（后端拉取整个文件夹解析 SKILL.md）、本地 zip/文件夹上传、
   JSON 粘贴（兼容保留）。
2. 所有入口统一进入导入预览页：展示名称、描述、文件清单、版本号；含可执行脚本时
   显示醒目的安全提示；用户确认后才入库。
3. 入库时记录版本号或 commit hash，技能卡片支持"检查更新"。

## 三、运行时三层渐进式披露加载
1. L1：助手运行时系统提示中只注入已挂载技能的 name + description 索引。
2. L2：新增内部工具 use_skill(name)，模型命中时调用，返回该技能 SKILL.md 正文。
3. L3：正文引用的 references/scripts/assets 按需读取或执行；脚本只回收输出，
   代码不进入上下文。
4. 未挂载到该助手的技能不出现在其索引中。

## 四、挂载体验
1. 助手编辑页的"挂载技能"从裸下拉改为可搜索多选：选项展示技能名称 + 一句话描述，
   已选项以标签呈现，含脚本的技能带标识徽标。

## 验收标准
- [ ] GitHub 上一个标准 SKILL.md 技能文件夹可通过 URL 直接导入并使用
- [ ] zip 上传与 JSON 粘贴两条路径均可导入
- [ ] 导入预览页信息完整，含脚本技能有安全提示
- [ ] 挂载 N 个技能后系统提示仅增加约 N×100 tokens 的索引，正文按需加载
- [ ] 存量 JSON 技能迁移后行为不变
```

---

## 三、Part B：助手管理页（编辑助手模板抽屉）美化

### 3.1 现状问题清单（对照截图）

1. **信息层级弱**：五个分区（基本信息/模型与交互/系统设定/能力挂载/功能开关）都是白卡 + 小号标题，视觉上平铺，长页面找不到重点。
2. **表单全部通栏单列**：名称、描述、分类等短字段也拉满整行，抽屉内纵向滚动过长。
3. **主题色展示原始**：色块旁直接显示 `#4f8ef7` 纯文本，没有取色器。
4. **模型选择器被截断**：`qwen3.7-max (qwen3...`，旁边悬浮一个孤立的刷新图标，含义不明。
5. **MCP 挂载暴露原始 UUID**：`3e353945-c631-5ba6-a63d-0e5e6c1f03` 直接作为标签展示，不可读。
6. **挂载技能是空裸下拉**：占位文字"选择要挂载的技能"，看不到技能描述，无法搜索。
7. **系统提示词区逼仄**：默认收起成小输入框，字数统计（43/2000）换行挤压，"展开/恢复默认"是小灰字链接，不显眼。
8. **功能开关注册感弱**：四个开关纯列表，关闭态灰扑扑，没有状态反馈。
9. **底部按钮不固定**：取消/保存沉在长滚动底部。

### 3.2 提示词 B：编辑助手模板抽屉视觉优化（粘给编码 Agent）

```text
你是一名资深前端工程师。项目为 OmicHub 多助手平台（沿用现有框架与组件库，先读代码
确认是 Ant Design / Arco / 其他，不要引入新组件库、不要改动任何功能逻辑与接口）。

任务：在现有"编辑助手模板"抽屉组件基础上做视觉优化。先阅读该抽屉及其子组件的
现有代码，理解当前实现后再修改。禁止推倒重写，禁止改动表单字段、提交逻辑和路由。

## 需要修改的问题（逐条执行）

1. 分区层级：五个分区标题（基本信息/模型与交互/系统设定/能力挂载/功能开关）
   升级为 16px / 600 字重，左侧加 4px 宽主题色竖条，标题下加 12px 灰色辅助说明
   一行；分区卡片统一 16px 圆角、24px 内边距、卡片间距 16px， hover 不加分页式阴影。
2. 表单布局：抽屉内桌面宽度下基本信息区改为两列网格（名称、分类各占一列；
   描述、欢迎语通栏），短字段不再全部拉满整行。
3. 主题色：色块 + 文本 "#4f8ef7" 替换为组件库取色器（ColorPicker），选中色同步
   更新头像预览底色，保留 hex 值可复制。
4. 模型选择器：下拉宽度加至完整显示模型名（不被截断），刷新图标收入选择器
   右侧后缀位并加 tooltip "刷新模型列表"。
5. MCP 挂载标签：禁止直接展示 UUID。标签展示 MCP 服务名称，UUID 移入 tooltip；
   无名称时显示名称缺失占位而非裸 ID。
6. 挂载技能选择器：改为可搜索多选，下拉选项为两行结构（技能名称 14px/500 +
   描述 12px 灰色），已选项以标签展示并支持单独移除；空数据显示空状态插画/文案
   "暂无可用技能，请先在技能库导入"。
7. 系统提示词区：默认展示 4 行 textarea，字数统计"43/2000"固定在右下角不换行；
   "展开"改为次按钮样式置于字段右上角，点击后弹出大编辑模态；"恢复默认"加二次确认。
8. 功能开关卡片：四项开关改为图标 + 名称 + 说明的行式列表，行间距 8px 分割线；
   开启态开关使用主题色，开启后该项名称加深以作状态反馈。
9. 底部操作条：取消/保存改为吸底固定栏（毛玻璃背景 rgba(255,255,255,0.8) +
   backdrop-filter: blur(8px)，上边框 1px 分割线），保存为主按钮并带 loading 态。

## 全局约束

- 配色与组件风格必须与平台首页及其他管理页一致，主题色沿用现有 token。
- 抽屉在 1280px 与 1920px 宽度下均无布局破损；表单校验提示位置不变。
- 动画时长 200~300ms，不添加循环动效。

## 验收标准（逐条自检）

- [ ] 上述 9 条问题均有对应改动，可对照修改前截图逐条确认
- [ ] 所有表单字段、提交数据结构与改前完全一致
- [ ] UUID 不再裸露，模型名完整可见
- [ ] 底部按钮吸底，长滚动时始终可见
- [ ] 与平台其他页面风格一致

完成后简述：每条问题对应的修改文件与关键样式改动。
```

---

## 四、Part C：@ 与 / 唤起面板语义拆分

### 4.1 背景与评估结论

现状：对话输入框的 `@` 面板混合展示文件夹与 Agent，UUID 命名的文件夹排在最前，把"通用助手""代码助手"压在下面；`/` 面板仅展示技能命令。

**评估结论：拆分方案可行，与业界约定一致，建议采纳并做两处微调。**

- ✅ `@` = 上下文引用（文件/文件夹/知识库），`/` = 能力调用（命令/技能/智能体）正是 Claude Code / Codex / Cursor 的事实约定，用户零学习成本 [^11^][^12^]。
- ✅ 语义自洽：`@` 管"给什么上下文"，`/` 管"让谁/什么能力执行"。
- ⚠️ 微调 1：`@` 提人的 IM 肌肉记忆很强（平台聊天区已有"@傻妞"气泡）。不要删除 @agent 体验，而是把入口挪进 `/` 面板的"智能体"分组，选中后向输入框插入 `@助手名` mention 标签，渲染与提交逻辑不变。opencode 社区同样在 @ 补全中优先排 agent、保持排序干净 [^14^]。
- ⚠️ 微调 2：更深层的问题是文件条目裸显 UUID（`e0b76987-885f-...`），即使拆分后 `@` 列表依然不可用，必须同步修复命名展示。

### 4.2 提示词 C：@ 与 / 唤起面板拆分（粘给编码 Agent）

```text
你是一名资深前端工程师。项目为 OmicHub 多助手平台（沿用现有框架与组件库，先读代码确认，不要引入新组件库、不要改动对话提交与渲染逻辑）。

任务：重构对话输入框的 @ 与 / 唤起面板。先阅读现有 mention 弹窗与 slash 弹窗的实现代码（含数据源接口、键盘导航、选中后插入逻辑），理解现状后再修改。禁止推倒重写。

## 一、语义拆分（核心需求）
1. @ 面板：仅展示"上下文引用"类条目——文件、文件夹、知识库。不再出现 Agent、Skill。
2. / 面板：仅展示"能力调用"类条目，分三个分组（带分组标题）：
   - 技能（Skills）：现有 /analysis、/rna、/go 等；
   - 智能体（Agents）：通用助手、代码助手等；
   - 内置命令（如已有，无则省略该分组）。
3. 在 / 面板选中智能体时，向输入框插入 "@助手名 " 的 mention 标签，标签渲染样式、提交数据结构必须与现有 @ 提及完全一致（聊天区的 @傻妞 气泡效果不变）。

## 二、文件条目展示修复
1. 文件/文件夹条目主行禁止显示 UUID：显示真实文件名或用户别名；UUID 仅作为 tooltip。
2. 副行 12px 灰色显示路径（如 enrichment/xxx/），超长中间截断。
3. 文件夹与文件用不同图标区分，右侧保留类型徽标（Folder/File/KB）。

## 三、两个面板统一体验
1. 模糊搜索：按名称 + 描述匹配，输入即过滤；无结果显示空状态文案
   （@ 面板："没有匹配的文件"；/ 面板："没有匹配的技能或智能体"）。
2. 排序：最近使用置顶（本地存储最近 5 条），其余按名称排序。
3. 键盘导航沿用现有实现（↑↓ 导航、Enter 选择、Esc 关闭），分组标题不可选中。
4. 面板宽度与输入框对齐，最大高度 320px 内部滚动。

## 全局约束
- 选中文件后的引用数据结构、选中技能后的命令提交行为与改前完全一致。
- 风格与聊天区现有 UI 一致，动画 200~300ms。

## 验收标准
- [ ] @ 面板只出现文件/文件夹/知识库，无 Agent 与 Skill
- [ ] / 面板按 技能/智能体 分组展示，选智能体插入的 @ 标签与手动 @ 效果一致
- [ ] 文件条目不再裸显 UUID
- [ ] 模糊搜索、最近使用、键盘导航均可用
- [ ] 引用与调用的提交行为与改前一致，对话链路无回归
```

---

## 五、Part D：Web 基因组浏览器查看区空间优化

### 5.1 现状问题

为与其他工具页保持一致，基因组浏览器套用了"页头 + 工具条卡片 + 居中限宽容器"的通用外壳，导致：

1. JBrowse 查看容器高度不撑满剩余视口（固定/auto 高度），会话区被压小；
2. 居中限宽 + 左右大留白浪费横向空间，轨道一多就不够用；
3. 页头（标题+副标题）与工具条卡片占两行约 200px 垂直空间；
4. 无全屏沉浸模式，不符合 IGV/JBrowse 类工具的通行交互。

原则：**风格可以一致，空间分配必须按工具类型差异化**——表单类页面留白是舒适感，可视化工具留白是浪费。

### 5.2 提示词 D：基因组浏览器查看区空间优化（粘给编码 Agent）

```text
你是一名资深前端工程师。项目为 OmicHub 多助手平台（沿用现有框架与组件库，先读代码确认，不要引入新组件库、不要改动 JBrowse 集成逻辑与数据接口）。

任务：优化"Web 基因组浏览器"工具页的空间利用。先阅读该工具页的布局代码（页面外壳、工具条卡片、JBrowse 嵌入容器），理解现状后再修改。禁止推倒重写，禁止改动其他工具页。

## 需要修改的问题（逐条执行）

1. 查看区撑满剩余高度：JBrowse 嵌入容器改为 flex 布局下的 flex: 1 + min-height: 0，
   高度 = 100vh - 页头高度 - 工具条高度 - 页面 padding，设置最小高度 480px 兜底；
   容器 overflow: hidden，滚动交给 JBrowse 内部。禁止再用固定 px 或 auto 高度。
2. 取消该页的居中限宽：本工具页内容区宽度改为 100%（左右仅保留 16px 页面 padding），
   不影响其他工具页的限宽规则——如外壳是共用组件，给本页加 full-width 变体 prop。
3. 页头与工具条压缩合并：标题区垂直 padding 压缩至 12px；副标题"基于 JBrowse 2 ·
   支持 BAM/BigWig/VCF/GFF3 流式浏览"改为标题旁 12px 灰色小字；工具条卡片去除
   卡片式大圆角大留白，改为与页头同一视觉层级的紧凑横条（高度约 48px），
   参考基因组选择、区间输入、跳转、上传文件、我的文件保持一行排布，窄屏折行。
4. 增加全屏沉浸模式：工具条右侧加"全屏"图标按钮，点击后隐藏平台页头与侧边导航，
   查看区占满整个视口（可用 Fullscreen API 或 fixed 定位实现），Esc 或再次点击退出；
   全屏态保留工具条可操作。
5. 空状态适配：JBrowse 的 Start a new session / Recent sessions 欢迎界面在撑满后的
   容器内垂直居中，不再出现上半截内容、下半截大段空白的割裂感。

## 全局约束
- 页头配色、字体、控件样式与平台其他工具页保持一致（改的是空间分配，不是视觉语言）。
- 1280px 与 1920px 宽度下查看区均占满剩余视口，无双重滚动条（页面级不出现纵向滚动）。
- 修改仅在基因组浏览器工具页生效，共用外壳组件的改动必须向后兼容。

## 验收标准（逐条自检）
- [ ] 打开会话后基因组查看区高度 ≥ 视口高度的 70%
- [ ] 页面级无纵向滚动条，查看区内滚动正常
- [ ] 全屏模式进出正常，Esc 可退出
- [ ] 跳转、上传、我的文件等功能行为与改前一致
- [ ] 其他工具页布局零变化
```

### 5.3 回归测试重点

- **共用外壳组件**：若通过加 full-width 变体 prop 实现，确认其他工具页布局零变化。
- **JBrowse resize**：flex 撑满后，窗口尺寸变化时 JBrowse 内部轨道应自适应拉伸（iframe 嵌入需确认 resize 事件透传；组件嵌入需确认监听到容器尺寸变化）。

---

## 六、Part E：云端沙盒终端启动页前端优化

### 6.1 现状问题（对照截图与 README 架构）

1. 镜像选择器按"只有一个镜像"设计：单卡片 + 大片留白，新镜像接入后布局即崩；
2. 顶部三张统计卡（镜像大小/预装工具/预计启动 3 秒）信息价值低、占位大，"预计启动"为伪精确指标；
3. 内存滑块刻度为 256M/5.8G/11.3G… 非线性拼接，无法凭直觉拖动；默认 512MB 对单细胞类镜像必然 OOM，资源默认值未与镜像联动（README 中 `images[].resources` 字段已支持，前端未消费）；
4. 启动配置预览与左栏信息重复，挂载目录长路径折行；
5. 内容区限宽过窄，两侧空旷（与 Part D 同类问题）。

### 6.2 提示词 E：沙盒终端启动页优化（粘给编码 Agent）

```text
你是一名资深前端工程师。项目为 OmicHub 多助手平台，前端 Vue3 + Pinia + Naive UI
（先读代码确认）。涉及文件：frontend/src/views/BioTools/TerminalView.vue、
frontend/src/components/terminal/ImageSelector.vue、ResourceSettings.vue、
frontend/src/stores/terminal.ts。

任务：优化云端沙盒终端启动页布局与信息架构。先阅读上述组件与 GET /terminal/environments
返回的数据结构，理解现状后再修改。禁止推倒重写，禁止改动终端会话（XTerminal.vue /
WebSocket）逻辑。

## 需要修改的问题（逐条执行）

1. 镜像选择器改网格卡片：ImageSelector.vue 从单列卡片改为响应式网格
   （≥1200px 时 2 列，≥1600px 时 3 列），卡片内容：icon + 名称 + 一句话描述 +
   tags 徽标 + 默认资源（如"默认 4GB / 2 核"）。选中态：2px 主题色描边 + 左上角
   勾选角标，hover 态轻微上浮（translateY(-2px)，200ms）。空列表显示空状态。
2. 删除顶部三张统计卡（镜像大小/预装工具/预计启动）：镜像大小与工具数合并为
   选中卡片底部的一行 12px 灰色 meta 文字；"预计启动 3 秒"删除（伪精确指标）。
3. 资源设置重做刻度：内存滑块刻度改为等比档位（0.5G/1G/2G/4G/8G），
   CPU 刻度（0.5/1/2/4/8 核）；滑块为主、数字步进器收起为后缀小控件。
   关键联动：切换镜像时用该镜像 resources 字段重置滑块默认值（基础 512MB/1核、
   单细胞 4GB/2核），默认值在滑块轨道上标注"推荐"刻度点。
4. 启动配置预览压缩：从 6 行分隔列表改为紧凑定义列表（行高 32px、无分割线），
   仅保留 镜像/内存/CPU/挂载目录/生命周期；挂载目录用等宽字体 + 单行省略 +
   tooltip 显示全路径；"用完即毁"保留红色警示。
5. 页面布局：内容区 max-width 从当前值提升至 1400px，改三栏布局
   （左：选择分析环境｜中：资源设置｜右：配置预览+启动按钮），<1200px 时
   退化为上下堆叠。页面级无纵向大段空白。
6. 启动按钮：保持"启动 {镜像名}"动态文案，点击后进入 loading 态并禁用，
   会话创建失败时 toast 报错并恢复可点击。

## 全局约束
- 配色、圆角、字体与平台其他工具页一致；组件库沿用 Naive UI，不引新依赖。
- 与 terminal store 的字段契约（image_id / resources）不变。

## 验收标准
- [ ] 4 个镜像卡片网格展示正常，选中/悬停态清晰
- [ ] 切换镜像时资源默认值联动且标注"推荐"
- [ ] 统计卡已移除，无伪精确启动时间
- [ ] 1280/1600/1920 宽度下布局无破损、无大片留白
- [ ] 创建会话行为与改前一致
```

---

## 七、Part F：三个用途镜像（单细胞 / GATK&PLINK / ggplot2）

### 7.1 设计说明

- 三个镜像均 `FROM omichub/sandbox-terminal:latest`，继承 ttyd 1.7.7 + zsh/oh-my-zsh 环境与启动命令，只增量安装工具链；
- 遵守生产安全约束：构建时装完即切回 `USER 1000`；运行时根文件系统只读，故**缓存类目录必须指向 tmpfs**（`NUMBA_CACHE_DIR`、`MPLCONFIGDIR` → `/tmp`），否则 scanpy(numba) / matplotlib 启动即崩；
- R 包一律走 Ubuntu apt 二进制 `r-cran-*`，禁止容器内源码编译 tidyverse；
- 注册走 `terminal_images.yaml` 热重载（README「新增镜像步骤」），前端零改动；
- 单细胞镜像建议将 `terminal_config.yaml` 的 `max_resources.memory_mb` 从 4096 调至 8192（视宿主机余量）。

### 7.2 Dockerfile.scrna（单细胞分析）

```dockerfile
# tool_configs/terminal/docker/Dockerfile.scrna
# 构建: docker build -t omichub/sandbox-scrna:latest -f tool_configs/terminal/docker/Dockerfile.scrna tool_configs/terminal/docker/
FROM omichub/sandbox-terminal:latest

USER root

RUN apt-get update && apt-get install -y --no-install-recommends \
      python3-pip libhdf5-dev pkg-config \
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install --no-cache-dir \
      "scanpy>=1.10" "anndata>=0.10" \
      leidenalg python-igraph \
      harmonypy scrublet scvelo \
      openpyxl xlrd

# 只读根文件系统下，numba / matplotlib 缓存必须落到 tmpfs /tmp
ENV NUMBA_CACHE_DIR=/tmp \
    MPLCONFIGDIR=/tmp \
    OMP_NUM_THREADS=2

USER 1000
# CMD 继承基础镜像: ttyd -p 7681 -W ... zsh
```

### 7.3 Dockerfile.gatk（变异检测 GATK & PLINK）

```dockerfile
# tool_configs/terminal/docker/Dockerfile.gatk
# 构建: docker build -t omichub/sandbox-gatk:latest -f tool_configs/terminal/docker/Dockerfile.gatk tool_configs/terminal/docker/
FROM omichub/sandbox-terminal:latest

USER root

ARG GATK_VERSION=4.5.0.0
ARG PLINK1_BUILD=20231211
ARG PLINK2_BUILD=20240105

RUN apt-get update && apt-get install -y --no-install-recommends \
      openjdk-17-jre-headless python3-pip tabix \
    && rm -rf /var/lib/apt/lists/*

# GATK4（含 gatk wrapper 脚本，依赖 python3 与 java）
RUN wget -q "https://github.com/broadinstitute/gatk/releases/download/${GATK_VERSION}/gatk-${GATK_VERSION}.zip" -O /tmp/gatk.zip \
    && unzip -q /tmp/gatk.zip -d /opt \
    && ln -s /opt/gatk-${GATK_VERSION}/gatk /usr/local/bin/gatk \
    && rm /tmp/gatk.zip

# PLINK 1.9
RUN wget -q "https://s3.amazonaws.com/plink1-assets/plink_linux_x86_64_${PLINK1_BUILD}.zip" -O /tmp/plink1.zip \
    && unzip -q /tmp/plink1.zip -d /opt/plink1 \
    && ln -s /opt/plink1/plink /usr/local/bin/plink \
    && rm /tmp/plink1.zip

# PLINK 2
RUN wget -q "https://s3.amazonaws.com/plink2-assets/alpha5/plink2_linux_x86_64_${PLINK2_BUILD}.zip" -O /tmp/plink2.zip \
    && unzip -q /tmp/plink2.zip -d /opt/plink2 \
    && ln -s /opt/plink2/plink2 /usr/local/bin/plink2 \
    && rm /tmp/plink2.zip

ENV JAVA_OPTS="-Xmx3g"

USER 1000
```

> 注：PLINK 构建号随上游发布变化，构建失败时先到 https://www.cog-genomics.org/plink/ 查最新 build 号再改 ARG。

### 7.4 Dockerfile.ggplot2（科研绘图）

```dockerfile
# tool_configs/terminal/docker/Dockerfile.ggplot2
# 构建: docker build -t omichub/sandbox-ggplot2:latest -f tool_configs/terminal/docker/Dockerfile.ggplot2 tool_configs/terminal/docker/
FROM omichub/sandbox-terminal:latest

USER root

# r-base + apt 二进制 R 包（避免源码编译）+ 中文字体（ggplot 中文标签不乱码）
RUN apt-get update && apt-get install -y --no-install-recommends \
      r-base \
      r-cran-ggplot2 r-cran-dplyr r-cran-tidyr r-cran-readr \
      r-cran-stringr r-cran-forcats r-cran-tibble r-cran-purrr \
      r-cran-ggrepel r-cran-cowplot r-cran-rcolorbrewer r-cran-viridis \
      fonts-noto-cjk fontconfig \
    && rm -rf /var/lib/apt/lists/* \
    && fc-cache -f

# Python 侧绘图（plotnine = ggplot 语法 Python 版）
RUN pip3 install --no-cache-dir plotnine matplotlib seaborn

ENV MPLCONFIGDIR=/tmp

USER 1000
```

### 7.5 terminal_images.yaml 注册项（追加到 images 列表）

```yaml
images:
  # ... 保留现有 base 条目 ...
  - id: scrna
    name: 单细胞分析
    description: 预装 scanpy / anndata / leiden / Harmony / Scrublet / scVelo，适合 10x 数据质控、聚类与细胞注释
    image: omichub/sandbox-scrna:latest
    tags: [单细胞, scanpy]
    icon: 🧬
    resources:
      memory_mb: 4096
      cpu_cores: 2.0
      pid_limit: 200
    env:
      - { name: NUMBA_CACHE_DIR, value: /tmp }
      - { name: MPLCONFIGDIR, value: /tmp }
    enabled: true
  - id: gatk
    name: 变异检测 GATK & PLINK
    description: 预装 GATK4 / PLINK1.9 / PLINK2 / tabix，配合基础 samtools 链完成变异检测与群体遗传分析
    image: omichub/sandbox-gatk:latest
    tags: [变异检测, WGS, GWAS]
    icon: 🧪
    resources:
      memory_mb: 4096
      cpu_cores: 4.0
      pid_limit: 200
    enabled: true
  - id: ggplot2
    name: 科研绘图 ggplot2
    description: 预装 R + tidyverse(ggplot2/dplyr/tidyr) / ggrepel / cowplot / 中文字体，以及 Python plotnine
    image: omichub/sandbox-ggplot2:latest
    tags: [绘图, R, ggplot2]
    icon: 📊
    resources:
      memory_mb: 1024
      cpu_cores: 1.0
      pid_limit: 100
    env:
      - { name: MPLCONFIGDIR, value: /tmp }
    enabled: true
```

### 7.6 提示词 F：构建并接入三个镜像（粘给编码 Agent）

```text
你是一名资深 DevOps/后端工程师。项目为 OmicHub 多助手平台。先阅读
tool_configs/terminal/README.md 与 tool_configs/terminal/docker/Dockerfile（基础镜像），
理解镜像注册机制（terminal_images.yaml mtime 热重载、registry_prefix、非 root 1000:1000、
read_only 根文件系统、tmpfs /tmp 与 ~/.cache）后再动手。

任务：新增三个用途镜像并完成接入。完整 Dockerfile 与 yaml 条目见实现计划文档 Part F
（Dockerfile.scrna / Dockerfile.gatk / Dockerfile.ggplot2），可直接采用并按需微调。

## 一、构建三个镜像（Dockerfile 放 tool_configs/terminal/docker/）
1. Dockerfile.scrna → omichub/sandbox-scrna:latest（scanpy 全家桶；
   必须设置 NUMBA_CACHE_DIR=/tmp、MPLCONFIGDIR=/tmp，只读根文件系统下不设置会崩）
2. Dockerfile.gatk → omichub/sandbox-gatk:latest（OpenJDK 17 + GATK4 +
   PLINK1.9/PLINK2；gatk wrapper 需 python3 可用；验证 gatk --version 与 plink2 --version）
3. Dockerfile.ggplot2 → omichub/sandbox-ggplot2:latest（r-base + apt 二进制 r-cran-*
   包，禁止源码编译 tidyverse；fonts-noto-cjk 中文字体；plotnine）

## 二、注册与资源联动
1. terminal_images.yaml 增加三个条目（id/name/description/tags/icon/resources/env/enabled），
   resources 分别 4096MB/2核、4096MB/4核、1024MB/1核；保存后确认热重载生效
   （GET /terminal/environments 返回新镜像，无需重启后端）。
2. 若 terminal_config.yaml 的 max_resources.memory_mb 为 4096，评估宿主机余量后
   调至 8192，使单细胞镜像可申请到足够内存。

## 三、逐镜像验收（必须实际跑通）
1. docker run 起容器（模拟生产参数：--user 1000:1000 --read-only --tmpfs /tmp
   --cap-drop ALL），wget --spider localhost:7681 健康检查通过。
2. 容器内验证工具可用：scanpy 导入并跑 sc.pp.filter_cells 示例；gatk --version、
   plink2 --version；Rscript -e 'library(ggplot2)' 并输出一张 png 到 /home/omichub/workspace。
3. 通过平台前端各创建一个会话，终端正常进 zsh、工具可用、workspace 挂载读写正常、
   销毁后容器 auto_remove。

## 验收标准
- [ ] 三个镜像构建成功且体积合理（记录各镜像大小）
- [ ] 前端镜像选择器出现三张新卡片，资源默认值正确联动
- [ ] 三镜像在生产安全参数下 ttyd 正常、工具可用
- [ ] 现有 base 镜像与终端功能零回归
```

---

## 八、Part G：后台"系统管理"导航合并与折叠样式优化

### 8.1 现状问题（对照截图）

1. **菜单过碎**：9 个子项中两对同域菜单应合并——饼干账户管理 + 饼干定价管理（同属计费体系）、AI 模型配置 + AI 资源中心（同属 AI 配置）；
2. **双重高亮**：父级"系统管理"整颗填充药丸高亮（实为容器），当前叶子页也高亮，一屏两个高亮，层级混乱；
3. **层级重复表达**：父级左侧蓝竖条 + 子项缩进竖线表达同一层级关系；
4. **折叠交互粗糙**：chevron 小且淡、点击热区不明、无过渡动画；
5. **图标不统一**：AI 两个菜单复用同一图标。

### 8.2 合并方案（9 项 → 7 项）

- 饼干账户管理 + 饼干定价管理 → 「饼干中心」（页内 Tab：账户管理 / 定价管理）
- AI 模型配置 + AI 资源中心 → 「AI 配置中心」（页内 Tab：模型配置 / 资源中心）
- 可选增强：分组小标题 运营 / 计费 / AI / 基础设施

### 8.3 提示词 G：后台导航合并与折叠样式优化（粘给编码 Agent）

```text
你是一名资深前端工程师。项目为 OmicHub 多助手平台，前端 Vue3 + Naive UI（先读代码
确认菜单组件实现方式，是 NMenu 还是自研）。涉及文件：后台布局的侧边导航组件、
路由配置、饼干账户/定价两个页面、AI 模型配置/资源中心两个页面。

任务：重构"系统管理"分组的菜单结构与折叠样式。先读现有导航与路由代码再修改。
合并菜单时保留原有页面组件，只改路由与页面外壳，不重写业务逻辑。

## 一、菜单合并（9 项 → 7 项）

1. 「饼干账户管理」+「饼干定价管理」合并为「饼干中心」：新页面以 Tab 承载
   （账户管理 / 定价管理），原两个页面组件作为 Tab 内容复用，路由改为
   /admin/biscuits/accounts 与 /admin/biscuits/pricing（或 ?tab= 参数），
   旧路由 301 重定向到新路由。
2. 「AI 模型配置」+「AI 资源中心」合并为「AI 配置中心」：同上，
   Tab 为 模型配置 / 资源中心，旧路由重定向。
3. Tab 状态写入 URL（刷新/分享链接不丢 Tab）；浏览器标题随 Tab 更新。
4. 两个合并页的 Tab 栏样式：下划线式 Tabs，与平台其他页内 Tab 一致。

## 二、折叠交互与样式修复

1. 消除双重高亮：父级分组（系统管理）仅为容器，不使用填充高亮样式——
   常态为 14px/500 文字 + chevron，hover 浅灰底（rgba(0,0,0,0.04)），
   展开态 chevron 旋转 180°。当前页高亮只出现在叶子菜单：左侧 3px 主题色
   竖条 + 浅主题色底（rgba 主题色 0.08）+ 主题色文字。
2. 去除层级重复表达：父级左侧蓝竖条删除；子项缩进 16px，缩进引导竖线
   改为 1px rgba(0,0,0,0.06)，仅贯穿子项列表。
3. 父级整行均为点击热区（不只是 chevron）；chevron 14px，颜色
   rgba(0,0,0,0.45)，旋转过渡 200ms。
4. 展开/收起加高度过渡动画（200~250ms ease-in-out，可用 grid-template-rows
   0fr→1fr 或 max-height 方案），收起时不闪跳。
5. 图标统一：全部使用同一图标库的线性 16px 图标，为「AI 配置中心」
   「饼干中心」分配各自独立图标，不再复用同一图标。

## 三、可选增强（做不做请告知）

- 子项超过 6 个时加分组小标题：运营（用户管理/首页入口管理/通知公告）、
  计费（饼干中心）、AI（AI 配置中心）、基础设施（沙盒终端管理/BLAST 数据库管理）；
  小标题 12px rgba(0,0,0,0.4)，上间距 16px。

## 全局约束

- 菜单折叠/展开状态持久化（localStorage），刷新不丢。
- 仅改系统管理分组，不动其他顶级菜单；路由守卫与权限逻辑不变。

## 验收标准

- [ ] 菜单为 7 项，两对合并入口的 Tab 均可正常切换且 URL 可直达
- [ ] 旧路由访问自动跳转新路由，页面功能与改前一致
- [ ] 任意时刻全导航只有一个高亮项（当前叶子页）
- [ ] 折叠/展开动画流畅无闪跳，chevron 旋转同步
- [ ] 折叠状态刷新后保持
```

### 8.4 回归测试重点

- 旧路由重定向：检查是否有其他页面/文档硬编码了旧菜单链接；
- 权限守卫：合并后的新路由需挂同样的 AdminRequired 校验；
- 菜单激活态：Tab 切换时侧边栏高亮需跟随子路由（/admin/biscuits/pricing 时"饼干中心"保持高亮）。

---

## 九、Part H：数据下载与聚合页面风格统一

### 9.1 现状问题（对照四张截图）

功能结构合格（四来源 Tab + 提示条 + 表单 + 任务表），但**视觉语言与平台脱节**：
渐变紫蓝按钮 + 厚投影 + 黑描边药丸 Tab + emoji 图标，而平台体系是灰底白卡 +
平面化 + 主题蓝 + 线性图标；表单仍为旧式右侧窄标签列；任务表空状态占大半屏空白。

### 9.2 提示词 H：数据下载与聚合页面风格统一优化（粘给编码 Agent）

```text
你是一名资深前端工程师。项目为 OmicHub 多助手平台，前端 Vue3 + Naive UI。
涉及文件：数据下载与聚合页面组件（四个来源 Tab：公共数据库/云盘极速提取/
云存储直拉/直链与 FTP）及其子组件、任务列表组件。

任务：在现有页面基础上做视觉统一优化，使其与平台设计体系一致。先阅读该页面
代码及平台其他工具页（如沙盒终端、分析中心）的样式实现，提取平台设计 token
后修改。禁止推倒重写，禁止改动四个来源的提交逻辑、接口与任务轮询。

## 一、视觉语言对齐平台（核心）

1. 去除渐变与厚投影：所有按钮改用平台规范——主按钮为纯色主题色（沿用平台
   primary token）+ 常规 hover 加深，次按钮为描边样式；删除蓝紫渐变、
   box-shadow 发光/厚重投影、黑色描边。
2. 来源切换 Tab：从黑边框药丸改为平台统一 Tab 组件（下划线式或分段式，
   与其他页面页内 Tab 一致）；选中态为主题色，无渐变无投影。
3. 图标：四个 Tab 的 emoji（🧬☁️🏢🔗）替换为平台统一线性图标库的 16px
   图标（数据库/云/存储/链接），与导航图标风格一致。
4. 提示条：保留浅蓝信息条，但四个 Tab 的文案统一句式（"支持……，
   完成后自动入库"），图标用统一 info 线性图标。

## 二、表单区规范化

1. 标签布局与平台新规范一致：label 上置（14px/500，必填红色 * 于右侧），
   帮助说明 12px 灰色置于控件下方 4px；弃用右侧对齐窄标签列。
2. 表单卡片：白卡 12px 圆角、24px 内边距、1px 浅边框、无投影；
   内容区 max-width 1080px 居中，控件合理宽度（输入框 ≤520px，
   select ≤320px），卡片右侧不再留大片空白。
3. 两个"高级选项"折叠条统一为同一组件样式：整行浅灰底（hover 加深）+
   左侧标题 14px/500 + 右侧 12px 灰说明 + chevron，展开 200ms 过渡。
4. 提交按钮统一文案格式"提交拉取任务"/"提交下载任务"，左侧下载图标
   用线性图标，提交中 loading + 禁用。

## 三、任务列表优化

1. 空状态高度收敛：空表区域固定 240px 高，居中 = 48px 线性图标 +
   "暂无下载任务"（14px）+ 一行 12px 灰色引导文案（"提交任务后，
   下载完成的文件将自动出现在「数据管理」中"）；不再出现大半屏空白。
2. 表格规范：表头 13px/500 灰底行；状态列用平台状态徽标（运行中蓝/
   完成绿/失败红/排队灰，与其他任务页一致）；进度列用细进度条 + 百分比；
   操作列统一为文字按钮（查看/重试/删除），删除二次确认。
3. 表头行："下载任务 · 共 N 个"中 N 用主题色；右侧状态筛选 select
   （160px）+ 刷新图标按钮，与平台其他列表页一致。
4. 有数据时任务名称列宽度收敛（≤320px，超出省略 + tooltip），
   登录号列等宽字体。

## 全局约束

- 全部颜色/圆角/字号走平台现有设计 token，页面内不得新增独立色值；
- 与平台其他页面一致的灰底 + 白卡体系，动画 200~300ms；
- 不改任何提交、轮询、状态接口逻辑。

## 验收标准

- [ ] 页面无渐变、无厚投影、无黑描边、无 emoji 图标
- [ ] 四个 Tab 与平台页内 Tab 样式一致，提示条句式统一
- [ ] 表单 label 上置，卡片右侧无大片空白
- [ ] 空状态收敛至 240px，含引导文案
- [ ] 与沙盒终端页并排对比，视觉语言一致（同 token、同卡片、同按钮）
- [ ] 四个来源的提交流程功能与改前一致
```

### 9.3 回归测试重点

- 四个来源的提交与任务轮询逻辑零改动，各提交一次验证；
- 与沙盒终端页/分析中心页并排截图对比，确认 token 级一致（按钮、卡片、Tab、状态徽标）。

---

## 十、Part I：引入 auto-animate 统一列表动效

### 10.1 选型结论（2026-07 调研）

- **@formkit/auto-animate**：一行指令实现列表增删/重排自动补间，零配置、体积极小，
  覆盖平台 80% 动效场景（任务表、卡片网格、样本表）——本次引入；
- **motion-v**（Motion 官方 Vue 运行时，活跃维护）：复杂交互（MAS DAG 进度图、
  手势、布局动画）备用，按需引入；
- **GSAP**：仅限首页/落地页滚动叙事，工具页不用；
- 禁区：React 系库不碰；velocity/popmotion 等停更库不碰；一个项目最多两个动画库。

### 10.2 提示词 I：接入 auto-animate（粘给编码 Agent）

```text
你是一名资深前端工程师。项目为 OmicHub 多助手平台，前端 Vue3 + Naive UI。

任务：引入 @formkit/auto-animate，为平台的列表增删与布局重排场景提供统一、
克制的过渡动画。先阅读平台现有动效相关代码（各页面是否已有 Transition 封装、
主题 token、是否已有 prefers-reduced-motion 处理）后再动手。禁止在页面里
各自手写动画逻辑，必须收敛为统一封装。

## 一、安装与全局封装

1. 安装 @formkit/auto-animate（最新稳定版）。
2. 封装全局指令 v-animate-list（注册在 main.ts 或独立 directives 模块）：
   底层调 autoAnimate，统一默认参数 { duration: 250, easing: 'ease-in-out' }，
   支持指令修饰符覆盖时长（如 v-animate-list.200）。
3. 无障碍降级：封装内检测 window.matchMedia('(prefers-reduced-motion: reduce)')，
   命中时 duration 置 0（直接跳变，不做补间）；提供平台级开关预留。
4. 禁止直接在各组件 import autoAnimate 散用，统一走 v-animate-list 指令，
   便于后续全局调整与卸载。

## 二、接入点（逐个接入并验证，不改任何业务逻辑）

1. 数据下载与聚合页：下载任务表格的行新增/状态变化/删除；
   状态筛选导致列表过滤重排。
2. 云端沙盒终端启动页：镜像卡片网格（窗口尺寸变化或镜像增减时的重排）、
   配置预览行的增删。
3. 分析中心（RNA-seq 等流程页）：样本表行添加/删除、差异比较组卡片的
   添加/删除。
4. 对话页：@ 与 / 唤起面板的选项过滤重排（如性能可接受，否则跳过并说明）。
5. 助手管理/后台列表页：表格行增删（如任务列表、镜像管理列表存在增删场景）。

接入原则：只加在"容器元素"上（列表/网格/卡片的父级），不加在单个卡片或
行上；同一页面同一容器只挂一次。

## 三、边界与禁区

1. 不对虚拟滚动/大列表（>200 行）启用，避免全量 DOM 补间卡顿；
   样本表超过 100 行时自动禁用（封装内判断子元素数量）。
2. 不与 Naive UI 组件自带的过渡冲突：弹窗、抽屉、下拉、折叠面板保持
   组件原生过渡，不叠加 auto-animate。
3. 不用于路由级页面切换动画（本次范围外）。
4. 表格场景优先挂在 tbody 或行容器上；若 Naive UI NDataTable 的 DOM
   结构导致补间异常，退而在其包装容器使用或改用 CSS 过渡，并在代码
   注释中说明取舍。
5. 所有动画只动 transform/opacity（auto-animate 默认即如此，不得改配置
   引入 layout 属性动画）。

## 四、验证

1. 逐接入点人工验证：增/删/重排时动画流畅（250ms 左右）、无跳动、
   无双重动画。
2. 开启系统"减弱动态效果"后动画全部退化为直接跳变。
3. 大数据量场景（样本表 150 行）无掉帧、无全列表补间。
4. 打包体积：auto-animate 应为全项目唯一新增运行时依赖，
   报告 gzip 后增量（预期 <5KB）。

## 验收标准

- [ ] v-animate-list 统一封装存在，各页面无散用的 autoAnimate 调用
- [ ] 五个接入点动画生效且业务行为与改前一致
- [ ] prefers-reduced-motion 下动画禁用
- [ ] 大列表/虚拟滚动场景无性能退化
- [ ] 与 Naive UI 原生过渡无冲突（弹窗/抽屉/折叠无双重动画）
```

### 10.3 回归测试重点

- NDataTable 的 DOM 结构与 auto-animate 兼容性（异常时按提示词第三条第 4 款降级处理）；
- 样本表 150 行大数据量场景帧率；
- 系统"减弱动态效果"开启后全平台无补间动画。

---

## 十一、实施顺序建议

1. **先做 Part B（助手编辑抽屉美化）与 Part D（基因组浏览器空间优化）**：均为纯前端、无数据模型变更，可并行，各自半天内可验收。
2. **再做 Part F（三个沙盒镜像）**：纯增量、走热重载注册，构建+验收约半天；完成后镜像多了，**Part E（终端启动页优化）** 的收益立刻显现，建议 F → E 连着做。
3. **再做 Part C（@ / 面板拆分）**：纯前端交互重构，用户可感知最强；注意回归测试 mention 提交链路。
4. **再做 Part A 的导入层改造**（四入口 + 预览页）。
5. **最后做运行时三层加载**：涉及 agent 运行时系统提示拼装，需回归测试对话链路。

## 九、风险与回退

- **存量技能迁移失败** → 迁移脚本先跑 dry-run 输出差异报告，确认后再写库；保留原 JSON 字段一个版本周期。
- **三层加载改变模型行为** → L1 索引中 description 必须写清"何时触发"，上线前用典型任务回归测试技能命中率。
- **美化改动波及表单校验** → 提示词中已约束不改提交逻辑，验收时跑一遍完整创建/编辑流程。
- **@ / 拆分改变用户习惯** → 老用户习惯在 @ 里找 Agent，可在 @ 面板空态或底部加一行提示"想找智能体？输入 / 试试"，观察 1~2 个版本后撤掉。
- **基因组浏览器外壳改动污染其他工具页** → full-width 变体必须通过 prop 显式开启、默认行为不变；改完抽查 2~3 个其他工具页确认布局无回归。
- **新镜像构建失败/体积失控** → 逐镜像单独构建验收，失败的镜像保持 `enabled: false` 不上线；PLINK 构建号失效时先查上游最新 build 再改 ARG；yaml 配置错误会回退默认配置，不影响 base 镜像。
- **只读根文件系统下工具崩溃** → 所有缓存类环境变量（NUMBA_CACHE_DIR/MPLCONFIGDIR）必须指向 tmpfs /tmp，验收时必须在 `--read-only` 参数下实测。

---

## 参考来源

[^1^]: Agent Skills 开放标准与文件夹结构 — https://agentskills.io/home
[^2^]: AGENTS.md vs .cursorrules vs Claude Skills 2026 对比 — https://blog.buildbetter.ai/agents-md-vs-cursorrules-vs-claude-skills-2026-comparison/
[^3^]: Agent Skills 渐进式加载设计解析 — https://blog.csdn.net/weixin_41645817/article/details/157548745
[^4^]: AI Agent Skills 完整指南 2026 — https://www.thepromptindex.com/how-to-use-ai-agent-skills-the-complete-guide.html
[^5^]: Agent Skills 与 MCP：智能体能力扩展的两种范式 — https://github.com/datawhalechina/hello-agents/blob/main/Extra-Chapter/Extra05-AgentSkills%E8%A7%A3%E8%AF%BB.md
[^6^]: 从 MCP 到 Agent Skills — https://www.luozhiyun.com/archives/893
[^7^]: LobeHub RFC 150 — Progressive Tool Loading — https://github.com/lobehub/lobehub/discussions/12491
[^8^]: Claude Code Issue — Lazy context loading / ToolSearch / SkillSearch — https://github.com/anthropics/claude-code/issues/44536
[^9^]: Agent Skills：大模型能力的渐进式封装与按需加载 — https://juejin.cn/post/7596926832912482367
[^10^]: Two Ways to Build a Skill Server for Your AI Agent — https://pub.towardsai.net/two-ways-to-build-a-skill-server-for-your-ai-agent-f05d7a7b8d68
[^11^]: Cherry Studio RFC — Unified @ and / Command System（/ 为命令、@ 为实体引用）— https://github.com/CherryHQ/cherry-studio/issues/15664
[^12^]: The AI Chat Interface Playbook — Slash Commands 与 Context Mentions 模式 — https://aiuxplayground.com/blog/ai-chat-playbook
[^13^]: Claude Code Skills vs Slash Commands — https://www.mindstudio.ai/blog/claude-code-skills-vs-slash-commands-2
[^14^]: opencode-chamber CHANGELOG — @ 补全优先排 agent、清理排序 — https://github.com/syntax-syndicate/opencode-chamber/blob/main/CHANGELOG.md
