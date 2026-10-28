# 生信工具箱优化任务书：description 工程 + 工具检索化 + GSEA/共线性

> 本文档自包含，可直接交付 Codex 执行。范围：工具箱（/tools）与 Agent 工具链路。
> 明确排除：系统发育树渲染修复、iTOL 集成（用户决定暂缓，不在本期）。
> 全程必须遵守《生信工具箱 · 前端工具设计规范》（tools_design.md）的强制章节：
> §四 接入流程、§5.1.2 异步任务架构、§5.6 绘图规范、§十三 上线检查清单、
> §15.6 Agent 工具注册、§21 MCP 可靠性、§22 路由规范。

## 0. 背景与目标

工具箱现有 17 个工具，已全量通过 `tools_schema.yaml` + `ToolBridgeService` 暴露给 Agent
（双通道 llm_payload/ui_payload、四种 invocation_mode、upload:// 协议、§21 可靠性体系）。
对标 Biomni 的剩余差距是规模化工程：工具选择的准确率与可扩展性。本期四件事：

1. **description 工程化**：为全量工具改写符合规范的 description，并建立 lint 与评测基线。
2. **工具检索化**：工具清单从"全量注入系统提示"升级为"语义召回 Top-N + 元工具发现"，
   为工具箱扩容到 40~50 个铺路。
3. **GSEA 富集分析**新工具（复用 clusterProfiler R 运行时）。
4. **基因组共线性分析**新工具（MCScanX 思路，复用 BLAST 异步任务架构）。

## 仓库锚点

动手前必须先读，禁止推倒重写：

| 文件 | 作用 |
|------|------|
| `tool_configs/tools_schema.yaml` | Agent 工具唯一注册表（description/input_schema/invocation_mode/双通道字段白名单） |
| `tool_configs/tools_setting.yaml` | 工具箱前端注册表（卡片元数据、group、order） |
| `src/omichub/tools/` | 工具 service/shim 实现；`registry/config.py::ToolItem`、`registry/schema.py::ToolItemDTO` |
| ToolBridgeService | `execute()` 分发、`_package()` 双通道封装、`_resolve_upload_refs()` |
| `AgentService.assemble_context()` / `schema_loader.build_system_hint()` | 工具注入 LLM 与系统提示清单生成（检索化的改动点） |
| `tool_configs/enrichments/` | 富集工具参考：`run_enrichment.R`、`species_config.yaml`、`examples/` |
| `deploy/docker/Dockerfile.enrichment` | clusterProfiler R 运行时（GSEA 复用） |
| `deploy/docker/Dockerfile.phylo` | 专用 Worker 参考（共线性新镜像仿此） |
| `frontend/src/views/BioTools/KeggEnrichmentView.vue` | 富集工具页面参考实现 |
| `frontend/src/views/BioTools/ToolsHubView.vue` | GROUP_MAP / ICON_MAP 登记处 |
| `tests/unit/tools/test_tool_bridge.py` | ToolBridge 分发测试 |
| `scripts/skill_mcp_smoke.py` | 冒烟脚本（§21.7，评测脚本仿其口径） |

## 硬性约束（全程有效）

1. **双重注册强制**：新工具必须同时完成 tools_setting.yaml（§四 五步 checklist）与
   tools_schema.yaml（§15.6）注册，缺任一项不算完成。
2. 既有 17 个工具的**行为零变化**：T1 只改 description 文本与注入逻辑，不改
   input_schema、invocation_mode、handler 实现。
3. 高计算工具必须复用 BLAST 异步任务架构（§5.1.2），禁止新建同步执行链路；Web 进程
   不得获得 Docker Socket 权限（§5.1.2 GID 规范）。
4. 密钥与环境差异走环境变量 + `core/config.py`（§5.1.1），禁止写进 YAML 或下发浏览器。
5. 每个任务独立 commit + 定向单测；验收全绿再进下一个。

---

## 任务 T1：工具 description 工程规范 + 全量改写 + 评测基线

### T1.1 先建评测基线（先于改写，用于证明改进）

新增 `scripts/tool_selection_eval.py` + 评测数据集
`tool_configs/evals/tool_selection_cases.yaml`：

- 数据集 ≥30 条：每个现有工具 1~2 条正向自然语言 query（覆盖口语化说法，如
  "帮我看看这些基因富集到什么通路""画个火山图""这两个基因组有没有共线性"），
  外加 ≥5 条易混淆/负向用例（不该调用任何工具箱工具的 query）。
- 每条标注：`expected_tool`（或 null）、`acceptable_alternatives`、`notes`。
- 脚本离线回放：对每条 query 跑当前的工具注入与选择逻辑（不调用真实 LLM 时用
  规则/相似度模拟器均可，但要固定可复现），输出 top-1 命中率与逐条明细。
- **先跑一次基线并记录数值**，报告注明执行日期与代码版本（口径遵守 §21.7）。

### T1.2 description 规范（写入 tools_design.md §15 新增小节）

每条工具 description 必须依次包含四个成分（可合写为连贯段落）：

1. **能力句**：动词开头，说清 输入 → 输出（如"对基因列表做 GO/KEGG 富集，返回
   分来源的通路表与气泡图"）。
2. **适用场景**：2~3 个典型用户说法或任务特征，让 LLM 能匹配口语化请求。
3. **边界句**：什么时候**不要**用、该改用哪个工具（按下方的近似工具分工矩阵写）。
4. **输入契约**：关键参数格式要求；支持 `upload://file_id` 的参数必须显式说明。

硬性规则：

- 长度 80~300 字符（中文计 1 字符）；禁止营销词（"极速""专业""一站式"等）；
  禁止与 input_schema 矛盾（如声称支持某格式但 schema 未收）。
- 每个工具在 `tools_schema.yaml` 新增 `keywords` 字段（同义词/英文别名/常见缩写，
  如火山图: `["volcano", "差异表达图", "DEG plot"]`），供 T2 召回使用。

近似工具分工矩阵（边界句的权威依据，写进规范）：

| 易混淆组 | 分工约定 |
|----------|----------|
| 组学绘图工坊 / 火山图绘制 / 表达矩阵 Explorer / 富集气泡图 | 自由探索绘图→工坊；DEG 结果（log2FC+padj）→火山图；表达矩阵质控（PCA/分布/方差）→Explorer；富集结果→气泡图图种 |
| 序列魔术师 / 格式轻量转换器 | 序列内容处理（清洗/翻译/ORF/Motif）→魔术师；文件格式互转（GFF/GTF/BED）→转换器 |
| DEG 差异表达 / GO-KEGG 富集 / GSEA（T3 新增） | 原始 counts→DEG；基因列表→富集；全基因排序列表→GSEA |

### T1.3 全量改写 + lint

- 按规范改写 `tools_schema.yaml` 中全部现有工具的 description 与 keywords。
- 新增 `tests/unit/tools/test_tool_schema_lint.py`：`omichub_` 前缀、长度区间、
  禁用词、四成分齐全（用标记句型或结构化子字段校验）、keywords 非空、
  schema 中每个参数在 description 或参数描述中有说明、工具名唯一（§21.1.4）。
- 改写后重跑 T1.1 评测，报告基线 vs 改写后的 top-1 命中率对比。

**T1 验收**：
- [ ] 基线数值已记录；改写后命中率不低于基线，且易混淆用例有改善
- [ ] lint 测试全绿并纳入既有测试入口
- [ ] 规范小节已追加进 tools_design.md §15
- [ ] 既有工具行为回归：test_tool_bridge.py 与冒烟脚本全绿

## 任务 T2：工具检索化（语义召回 Top-N 注入）

把 `assemble_context()` 的"全量注入"升级为"召回注入"，支撑工具箱扩容。

1. **召回器**：对 `name + description + keywords` 建 BM25 索引（中文分词用 jieba，
   依赖固定版本写入部署镜像；预留 embedding 召回的接口位，本期不实现）。
   `tools_schema.yaml` mtime 变化时重建索引（沿用 mtime 热重载模式）。
2. **注入策略**（三段式）：
   - **Pinned**：核心工具始终注入（ask_user、transfer_to_agent、web_search 及
     Agent YAML 显式 pinned 的工具）；
   - **Recalled**：按本轮用户 query 召回 Top-N（默认 8，可配）；
   - **Discovery**：新增元工具 `omichub_toolbox_search(query)`，返回完整工具清单的
     名称+一句话摘要，让 Agent 能主动发现未召回工具（对齐工作台 MCP/Skills 渐进披露
     的思路）。
3. **配置与降级**：`tool_configs/tools_schema.yaml` 全局节或 Agent YAML 增加
   `tool_selection: {mode: full|retrieval, top_n: 8}`；工具总数 ≤15 或索引构建失败时
   自动回落 full 模式，并在日志注明。
4. **观测**：每次召回记录 query、命中工具、本轮实际被调工具，写入结构化日志，
   供 T1 评测脚本复用（检索模式下的命中率也要出报告）。
5. 注意与 §21.4 健康状态记录兼容；召回失败不得导致工具调用链路整体失败
   （回落至 full 即可）。

**T2 验收**：
- [ ] 构造 30+ 工具的配置（可用 mock 工具补齐），retrieval 模式下注入 token 数有界
      且明显低于 full 模式
- [ ] 召回模式评测报告：命中率 ≥ T1 基线；未召回的工具可通过 `omichub_toolbox_search`
      在一次额外调用内被发现并使用
- [ ] 索引构建失败 / 工具数 ≤15 时自动回落 full，无报错
- [ ] 既有 Agent 默认行为不变（未配置时维持 full 模式）

## 任务 T3：GSEA 富集分析工具

复用 `Dockerfile.enrichment` 的 clusterProfiler R 运行时与富集工具的异步任务模式。

1. **后端**：`tool_configs/gsea/`（`run_gsea.R`、`gsea_config.yaml`、`resources.yaml`、
   `examples/`）+ 对应 Pydantic 配置模型与加载器（§5.1.1）。输入：排序基因列表
   （gene_id + score 两列，如 log2FC；支持粘贴/上传/`upload://file_id`）、物种
   （复用 enrichments 的物种配置模式）、基因集（GO_BP/MF/CC、KEGG，本地参考库）、
   p/q cutoff（服务端计算参数，随任务提交）。
2. **执行**：BLAST 异步架构（§5.1.2）。R 脚本用 `clusterProfiler::GSEA`；结果目录
   约定：结果 TSV（ID/Description/NES/pvalue/p.adjust/qvalue/setSize/leading edge 计数）
   + Top term 的 running score 曲线数据点 JSON。**图表不在容器内出静态图**，曲线数据
   交前端 Plotly 渲染（§5.1.2-7）。结果路径沿用
   `{data_mount}/users/{user_id}/gsea/{project_slug}/{task_id}/` 模式，项目 ID 校验与
   目录名清洗同富集工具。
3. **前端**：`GseaEnrichmentView.vue` + `gseaProcessor.ts`，两栏布局、PageHeader +
   ToolActionBar（吸底"提交分析"）、历史任务列表。分来源独立展示（§5.6.3.2），
   每来源：富集曲线（running score，英文图内标注）、结果表、PNG/SVG/CSV 导出
   （300/600/1000 DPI）。
4. **双重注册**：tools_setting.yaml（`group: "function"`，order 留间隔）+
   tools_schema.yaml（`backend_async`，`omichub_run_gsea`；llm_payload ≤3KB：
   Top 10 term 的 ID/NES/p.adjust；ui_payload 含 task_id + progress_url）。
5. description 与 keywords 按 T1 规范书写（边界句："基因列表无排序信息时用
   GO/KEGG 富集；有全基因排序（如 log2FC）时用本工具"）。

**T3 验收**：
- [ ] 示例数据一键载入并跑通完整链路（提交→排队→进度→结果→曲线→导出）
- [ ] §5.6.3.2 分来源展示、英文图内标注、DPI 导出全部满足
- [ ] 任务归属校验：他人 task_id 不可查（§5.1.2-5）
- [ ] Agent 链路：自然语言请求触发 `omichub_run_gsea`，进度卡片与结果摘要正确
- [ ] lint（T1）、§十三、§15.6 检查清单全过

## 任务 T4：基因组共线性分析工具（MCScanX 思路）

1. **范围（MVP）**：输入 GFF3 + BLASTP outfmt6 结果（上传 / `upload://` / 从平台 BLAST
   任务结果导入），容器内跑 MCScanX，输出共线性区块表；暂不做 Ka/Ks。
2. **镜像**：`deploy/docker/Dockerfile.synteny`（MCScanX + 结果解析脚本），构建上下文
   `tool_configs/synteny/`，提供 `make docker-build-synteny`，并同步
   `deploy/docker/README.md` 与 worker 启动检查（§5.1.2 Dockerfile 规范）。
3. **执行**：BLAST 异步架构。容器产物为结构化 TSV/JSON（block id、染色体对、基因对
   列表、坐标）；**dot plot 由前端 Plotly scattergl 渲染**（基因对 >5 万时提示先做
   染色体级过滤，并在设计说明中登记该阈值，§5.6.4-7）。
4. **前端**：`SyntenyView.vue` + `syntenyProcessor.ts`，group `genome`。工作区：
   dot plot（hover 显示基因对、点击定位区块表行）+ 区块 NDataTable + 导出。
5. **双重注册**：`backend_async`，`omichub_run_synteny`；llm_payload 含区块数、
   最大区块、Top 染色体对摘要。与 BLAST 工具的衔接写进双方 description 边界句
   （"BLAST 结果可直接作为本工具输入"）。

**T4 验收**：
- [ ] 示例数据（小型两染色体 demo）全链路跑通；dot plot 万级点对流畅
- [ ] 超限输入给出明确过滤提示而非卡死
- [ ] 镜像经 Make 入口可构建，worker 启动自动检查镜像存在
- [ ] Agent 链路触发正确；§5.1.2、§十三、§15.6、§21.8 清单全过

## 任务 T5：全程回归与评测报告

1. T1 基线、T1 改写后、T2 检索模式三份评测数值汇总成一份报告
   （注明执行日期、代码版本，口径遵守 §21.7）。
2. 全量回归：`tests/unit/tools/` 全部、`scripts/skill_mcp_smoke.py --only mcp`、
   前端 `vue-tsc` + `npm run build` 通过，构建后重启 nginx（§十三）。
3. §21.8 MCP 上线检查清单逐项过一遍并记录。

## 交付要求

1. 顺序：T1 → T2 →（T3 与 T4 可并行）→ T5。每个任务独立 commit（注明任务编号）。
2. T3/T4 的新工具页面先复制 §19.6 最小模板，再填充业务内容；视觉与既有工具零抖动。
3. 任一验收不通过即停止，输出问题清单等待指示。
4. 最终交付：git diff、三份评测数值、T5 回归报告。

## 风险与应对

| 风险 | 应对 |
|------|------|
| description 改写后个别工具反而选不准 | 先留基线数值，评测驱动改写；易混淆组以分工矩阵为权威 |
| 检索召回漏掉冷门工具 | Discovery 元工具兜底 + top_n 可配 + 工具数 ≤15 自动 full |
| BM25 对英文/缩写 query 召回差 | keywords 字段强制登记英文别名；评测集含英文 query 用例 |
| MCScanX 容器构建/许可问题 | 镜像构建列为 T4 第一步先行验证；失败则降级为纯解析用户自备 MCScanX 输出的方案并回报 |
| GSEA 基因集版权（MSigDB 等） | 本期只做 GO/KEGG 本地库；商用授权存疑的基因集不内置 |
