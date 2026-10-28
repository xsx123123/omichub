# CygnusX MCP 整改实施清单 v2

更新日期：2026-10-19  
依据：用户提供的《CygnusX MCP 外部验收报告》（report.md）及本轮审查。  
范围：补齐12条模糊描述、收口回归测试、隔离身份验证业务链、导出19个Agent最终工具集合。  
状态：本文件是持续更新的执行清单；已勾选项有当前工作树和证据支持，未勾选项仍未完成。2026-10-19后续隔离验收已建立测试身份并完成有限的真实平台/provider与Agent装配验证；结果只适用于证据明确列出的只读样例，不等同于生产部署或全量安全验收。

补充进展（2026-10-18）：管理端 MCP 配置抽屉的 Resources 页已接入按需发现，可展示外部 Server 的 Resource/Template 名称、URI、描述和 MIME 类型；新增 Admin API `GET /api/v1/mcp/servers/{server_id}/resources`，只返回元数据、不读取资源内容。Builtin 返回空列表，未声明 `resources` capability 的外部 Server 不会收到 resources/list 请求。该功能有 7 项后端单测通过，前端 `vue-tsc` 与 Vitest（90 文件、611 项）通过；它不替代 R4 的真实资源读取和隔离平台业务验收，也不改变下方未完成复选框状态。

补充进展（2026-10-19）：已整改 `optimize_in_sandbox` prompt 中的 `subprocess.run(find, ...)` 示例，改由当前用户可见的平台文件工具发现/预览文件；不可见时停止。五个工作流 Prompt 的参数现在以 JSON 字符串字面量渲染并标注为不可信数据，新增本地 FastMCP 与真实 STDIO、Streamable HTTP、SSE MCP 客户端恶意参数渲染测试（4 项通过，结果见`prompt-transport-safety-2026-10-19.ndjson`）。这只证明四种传输的渲染边界，不代表模型运行时可抵御语义级 prompt injection，相关模型行为验收仍未完成；改动仅在工作树，尚未部署。

补充进展（2026-10-19）：12条描述完成重审，`description-audit.tsv` 为109条逻辑记录，其中97项`valid`、12项`vague`，无缺失、空或纯空白描述；`vague`仅表示用途仍需人工确认。in-process、STDIO、Streamable HTTP、SSE当前清单各109项且名称/schema/描述一致。修复ClinVar桥接后，外部MCP完整套件最新为67项通过（不是本段早期记录的64项）；结果见`mcp-server-full-suite-2026-10-19.txt`。隔离平台、真实provider链和19个Agent上下文的后续状态见下方2026-10-19隔离验收更新。

补充进展（2026-10-19，本轮）：修正 research-data service 固定 host 缺失，补齐 Dfam、bulk/sc Atlas、InterPro、Open Targets；Atlas目录使用独立10 MiB预算、25秒上限和6小时进程内缓存；FASTA响应校验拒绝HTML；Open Targets partial GraphQL errors 显示partial/warning。26个research工具各自有固定host/path路由用例，且builtin handler与认证REST bridge从同一Preset schema拒绝未知/缺失/类型错误参数。相关后端定向测试后续扩展为56项通过，Ruff/mypy通过。五项provider经直接HTTPS抽样：Dfam、Single Cell Atlas、InterPro、Open Targets结构化响应成功；bulk Expression Atlas超时。直连不经过MCP或平台API身份，不计真实端到端验收，记录见`evidence/mcp-external-validation-2026-10-18/provider-direct-smoke-2026-10-19.ndjson`。

补充进展（2026-10-19）：描述审计重建脚本用 Python `csv.writer` 序列化 TSV；本轮另用 `csv.reader` 按逻辑记录校验109条工具记录、13列，分类为97项`valid`和12项`vague`，无缺失/空描述。`frontend/` 的 `npm run type-check` 及 `npm test` 本轮复跑通过（90个测试文件、611项）。

补充进展（2026-10-19，隔离运行验收）：专用隔离Postgres/Redis及普通测试用户已就绪；外部MCP经STDIO、Streamable HTTP、SSE到隔离平台并调用ClinVar成功。16项已实现provider各经外部STDIO MCP→隔离平台REST尝试一次，15项成功、Expression Atlas bulk目录超时；ClinVar旧`vcv_accession`参数被桥接传入的None默认值覆盖，现已修复为省略None并由13项定向回归覆盖，修复后ClinVar VCV及InterPro样例成功。逐项状态、请求日志与request ID见`evidence/mcp-external-validation-2026-10-18/provider-mcp-platform-2026-10-19.ndjson`及followup文件。STRING未实现。19个Agent已导出隔离DB真实上下文快照，逐项工具数/schema字节数见`agent-loading-summary.tsv`；platform-only临时上下文16工具、BioThings/Research Data均0，事务回滚；flows-only key经MCP调用Research Data工具被403拒绝、provider未触发。该对照只覆盖一个Agent/server binding及API scope，不覆盖所有用户capability/case。隔离DB revision为`dwnlease03`（更高的未提交迁移失败）；测试任务/报告/工作区资产、Prompt模型语义注入和生产部署仍未验收。修复后外部MCP完整套件67/67通过。

补充进展（2026-10-19，本轮后续）：内置 `cygnusx-research-data` 与外部 `mcp-server/tools/research_resources.py` 的 26 项工具签名由 AST 回归测试逐项对齐，避免参数名/schema 漂移；Reactome 查询同时记录 database release/version，Gramene 查询拒绝原始 Solr 语法并保留 provider taxonomy 说明，Ensembl lookup 校验返回物种，RCSB 查询限定 UniProt accession 与 experimental 结果。研究数据/MCP/API/双表面定向回归为56项通过，Ruff 与 mypy 通过；完整外部 MCP 套件先后复跑为58项和63项通过，当前最新结果为64/64（含Prompt参数渲染安全用例）。上述均为代码契约和直连适配器证据，不改变隔离平台身份缺失导致的 R3/R4/R5 未完成状态。

历史评估（2026-10-19，官方STRING MCP；当前实现状态见第10节）：官方Streamable HTTP端点真实initialize成功，tools/list返回17项；只读`string_resolve_proteins(TP53, species=9606)`返回结构化人类蛋白映射，`string_help(version_and_citation)`报告其数据版本v12.0。官方API版本页列v12.5，托管MCP说明仍在开发且不提供不可变版本pin；工具面包含图像/文件生成能力，未验证与平台文件权限/输出预算的映射，故官方托管MCP不直接注册。证据见`string-official-mcp-probe-2026-10-19.json`。

补充进展（2026-10-19，provider直连扩展）：除STRING未实现外，16项provider均有小规模直接HTTPS adapter探测记录，14项返回成功envelope，Ensembl Plants与bulk Expression Atlas超时；这些不是外部MCP→平台REST验收，且部分响应受3000字节预算裁剪。探测复现并促成修复Reactome `database/version` 的 `Accept: text/plain` 与Europe PMC `/article/{source}/{id}?resultType=core` 路径；内置和外部FastMCP双表面同步，Reactome/Europe PMC修复后直连均返回成功envelope。状态见`provider-direct-followup-2026-10-19.ndjson`、`provider-status.tsv`、`provider-verification-matrix.tsv`。研究适配器/双表面回归56/56、外部MCP完整套件64/64通过；仍无隔离测试身份，因此R4的真实MCP平台调用与缓存miss证明未完成。

补充进展（2026-10-19，本轮收口）：外部测试兼容 FastMCP 2.x/3.x 的 `input_schema`/`inputSchema` 字段，修正研究外部桥接测试使用已发布的 `pathway_id` 参数；使用 `PYTHONPATH=. uv run --project mcp-server --with pytest --with pytest-asyncio --with 'fastmcp==3.4.4' pytest -q tests` 复跑为 58 项通过。README 中残留的 `find` 沙箱示例已同步为平台文件工具；新增 `capability-dedup-matrix.tsv`、`business-e2e.ndjson`、`provider-verification-matrix.tsv`、`runtime-snapshot-2026-10-19.json`，并重新生成 checksums。

补充进展（2026-10-19，R5 可执行部分）：新增 `application/services/tool_manifest.py`，legacy 和 LangGraph 在回合开始、首次 Provider 调用前对工具数组生成脱敏 manifest，随 `agent_turn_started` 流事件输出。manifest 包含 `tool_count`、schema UTF-8 字节数、总 `manifest_sha256`，以及每项工具的 name/description/inputSchema/server/preset 来源和 `contract_digest`；不含用户消息、凭据或完整会话。它目前是运行时采集点，不是逐次 Provider 尝试的持久审计记录，后续轮次/重试也未分别导出。新增单测并与 LangGraph/golden 回归合计45项通过，证据及源文件哈希见 `evidence/mcp-external-validation-2026-10-18/`。该能力提供最终序列化清单采集路径，但没有隔离身份时仍不能生成19个Agent的真实DB裁剪快照。

补充进展（2026-10-19，R5 Provider 边界）：在 OpenAI-compatible Provider 实际发送 HTTP payload 前，新增 `provider_tool_manifest` 事件，基于已去重的最终 `tools` 数组生成脱敏 manifest；因此每轮、瞬时重试和无 tools 降级前的真实请求均有可观测清单。Provider 边界回归（排除既有 quarantine）23项通过，证据见 `provider-tool-manifest-tests-2026-10-19.txt`。该事件仍是运行时采集点，尚未落独立持久审计表；19个Agent的实际隔离上下文仍待测试身份。

补充进展（2026-10-19，R5 裁剪快照）：`AgentService.assemble_context` 现在保留脱敏的候选工具决策，记录 `server_disabled`、`server_review_denied`、`pack_disabled`、`user_denied` 和 `included`；新增 `build_agent_tool_snapshot(context)` 输出最终 schema、绑定 server、BioThings/Research Data 计数和裁剪原因，不输出系统提示、用户消息或凭据。新增只读入口 `scripts/export_agent_tool_snapshots.py`，要求显式隔离测试用户 UUID，并关闭读取时的模型绑定自动修复后按启用 Agent 清单导出；快照/导出回归10项通过，证据见 `agent-tool-snapshot-tests-2026-10-19.txt`。该能力已接入真实装配入口，但没有隔离测试身份时仍不能生成19份实际快照。

补充进展（2026-10-19，环境复核）：本机 Compose 的 Postgres/Redis 为 healthy，`http://127.0.0.1:8000/health` 返回200；但检查到的 `.env` 测试/认证相关变量中只有 `DATABASE_URL`，没有专用平台 API Key、MCP HTTP Token、测试用户/租户标识。运行中的本地栈不能据此认定为隔离测试租户；未发起认证业务调用。R3仍需专用测试身份与隔离数据。更新后的脱敏记录在`evidence/mcp-external-validation-2026-10-18/test-environment.json`。

补充进展（2026-10-19，provider响应预算）：BioThings 与 research-data service 的 JSON、文本/FASTA HTTP 响应均改为流式读取，累计超过字节上限时停止读取并关闭响应；测试使用可计数分块验证未继续消费后续内容。BioThings/research preset、Research Data API 与双表面契约回归64/64通过，Ruff/mypy通过。测试日志和修改后源文件哈希见`evidence/mcp-external-validation-2026-10-18/provider-streaming-budget-tests-2026-10-19.txt`及`provider-streaming-budget-source-hashes-2026-10-19.txt`。该项只验证客户端响应预算，不构成provider live或平台业务验收。

补充进展（2026-10-19，MyVariant组装与GET/POST契约）：官方 query 文档将 GET 用于查询、POST 用于带 `q/scopes/fields` 的批量查询；adapter 现令普通 DSL search 使用GET、resolve使用表单POST，并在 `assembly=hg19|hg38` 时强制投影对应的`dbsnp.hg19`/`dbsnp.hg38`坐标字段。真实adapter对rs699分别调用GET search和POST resolve，两者均返回`chr1:g.230710048A>G`及hg38坐标；同一rsID查询下`hg38=true`未改变坐标，不能把区间查询参数当通用assembly切换。未执行liftover。相关组合回归65/65通过，Ruff/mypy通过；日志、脱敏返回和源文件哈希见`myvariant-get-post-tests-2026-10-19.txt`、`myvariant-get-post-probe-2026-10-19.json`、`myvariant-get-post-source-hashes-2026-10-19.txt`。仍属直连provider证据，不代表MCP→平台REST完整链或cache miss。

补充进展（2026-10-19，ClinVar VCV）：平台内置 `cygnusx_clinvar_get` 已从把 VCV accession 传给 ESummary UID 参数，改为 NCBI EFetch `rettype=vcv` XML；VCV accession/version、Variation ID、germline、somatic clinical impact、oncogenicity、review status 与 submitter evidence 分栏返回。平台 service 与外部 adapter 的 XML 入口均拒绝 DTD/ENTITY 声明并限制 2 MiB 响应，且校验返回的 accession/显式版本与请求匹配。结果按3000字节预算裁剪，保留记录身份并将被裁分类/review显式标记。内置 research/API/双表面回归63项通过，外部 MCP 全套64项通过，Ruff/mypy通过。一个真实 NCBI VCV 样例验证了 EFetch 响应封装层及 VariationArchive 字段位置，未覆盖 RCV/SCV/Variation/Allele 输入或平台认证业务链，故ClinVar整体语义要求未全部关闭。详细输出与源哈希见`evidence/mcp-external-validation-2026-10-18/clinvar-vcv-tests-2026-10-19.txt`、`clinvar-vcv-source-hashes-2026-10-19.txt`及`clinvar-vcv-contract-probe-2026-10-19.json`。

补充进展（2026-10-19，ClinVar typed-ID 后续）：保留兼容参数 `vcv_accession`，新增 `identifier` + `identifier_type`，类型明确为VCV、RCV、SCV、VariationID或受控拒绝的AlleleID。RCV走`rettype=clinvarset`；SCV经JSON ESearch `[clv_acc]`解析Variation UID，再取VCV并核对响应中SCV accession/version；VariationID使用`is_variationid=true&from_esearch=true`并核对VariationArchive的VariationID。provider直连service对VCV000014206、RCV000015270.27、SCV000035529.2、VariationID 14206均取得匹配记录，脱敏记录见`evidence/mcp-external-validation-2026-10-18/clinvar-typed-identifiers-2026-10-19.json`。测试覆盖旧VCV参数、类型参数配对/互斥、RCV/SCV/Variation路由、错配拒绝和AlleleID零网络拒绝；平台定向回归54/54，外部ClinVar工具回归12/12，Ruff/mypy通过。SCV搜索改用JSON响应以避开上游ESearch XML中的DTD，同时保留所有XML DTD/ENTITY拒绝。以上仅是adapter/provider直连与本地合同验证，未经过FastMCP→认证平台REST→provider，缓存状态未观测；因此R4复选项和ClinVar端到端验收保持未完成。

## 1. 本轮基线与执行顺序

报告称：109个工具描述已非空，其中12条仍模糊；STDIO/HTTP/SSE握手与枚举成功；完整回归组曾有SSE失败；平台API使用dummy地址且无测试Key；19个Agent只做了静态配置盘点；17项provider未完成经平台MCP的真实调用，STRING未实现。

**不再把原“13个描述为空”当作待修事实；本轮目标是12条描述质量与真实业务验收。** 数量以当前证据重建为准，出现新增/减少需解释，不能凑数。

执行顺序：

1. R0 固定证据与代码基线。
2. R1 补齐12条描述，R2重跑完整回归及四组schema对比。
3. 并行准备R3隔离测试身份和R5工具集合导出所需环境；依赖未就绪不阻塞R1/R2。
4. R3就绪后进行R4真实业务链验收，同时执行R5逐Agent导出。
5. R6汇总缺口、更新报告与制品校验。

优先修复与验收现有实现，不顺手重构全部MCP、批量解绑Agent或部署生产。既有17资源整体规划不变；STRING已在工作树新增固定REST实现，但平台业务链、Agent授权与部署验证仍是缺口。

## 2. R0：基线与证据可复现

- [x] 保存当前HEAD SHA、MCP工作树diff哈希、必要源文件哈希与环境版本；未记录secret、密钥或完整env。证据：`followup-baseline-2026-10-19.json`、`mcp-server-source-hashes-2026-10-19.txt`。
- [x] 记录本次工作树补丁SHA-256；范围含既有MCP工作树改动，未声称所有内容均由本轮产生。
- [x] 取得并校验审计TSV、四路工具清单、schema-diff、完整测试结果、checksums及重建脚本。
- [x] 当前快照记录实际工具数、静态Agent名单、已知preset工具数、四面一致性和契约指纹可用性；`runtime-snapshot-2026-10-19.json` 明确记录DB开关/运行时裁剪/逐preset digest仍不可用。
- [x] 建立本轮修复前工具baseline并完成name、inputSchema、description兼容比较；原13空描述修复前快照不可取得，且handler绑定未捕获，已明确标记不可回溯验证。

产物：`baseline.json`、`baseline-tools.json`、受控补丁或提交引用、`checksums.txt`。

## 3. R1：补齐12条模糊描述

先读取`description-audit.tsv`每条reason，再对照真实函数、调用服务和schema编写。下表“核对重点”是调查问题，不是已经确认的工具行为。

| 工具名（报告基线） | 编写前需核对的重点 | 完成 |
|---|---|---|
| cygnusx_list_runs | run含义、所属范围、筛选/分页、返回摘要 | [x] |
| cygnusx_get_run_status | ID类型、可见性、状态含义与失败返回 | [x] |
| cygnusx_get_run_logs | 日志来源、条数/偏移、截断和数据边界 | [x] |
| cygnusx_verify_artifact | 验证的是存在/完整性/校验和中的哪些项，是否有副作用 | [x] |
| cygnusx_confirm_run_plan | 真实确认凭证/人类确认要求、是否改变状态、幂等与后续动作 | [x] |
| cygnusx_preview_analysis | 预览范围、必要参数、是否不提交任务及后续流程 | [x] |
| atac_seq_status | task/run参数、真实状态来源、适用流程 | [x] |
| cygnusx_gene_search | 物种、query模式、投影/分页与候选语义 | [x] |
| cygnusx_chem_search | 名称/ID搜索、盐型/异构体、多匹配、非结构计算边界 | [x] |
| cygnusx_genome_sequence | 对象/区域/序列类型、物种/assembly、大小与资产交付 | [x] |
| cygnusx_plant_get | 实际provider、实体/ID、物种/版本、缺失处理 | [x] |
| cygnusx_expression_studies | bulk/sc目录、过滤/分页、不是定量表达值查询 | [x] |

每条必须有：用途、适用场景、决定行为的关键参数/约束、主要返回语义、必要限制。不要冗述全部schema字段，不补函数实际不支持的能力或默认值，不把有副作用的confirm工具称作只读。

- [x] 沿用现有有效runtime描述和YAML fallback机制，并更新真正生效的描述来源。证据：`description-changes.tsv`与描述回归测试。
- [x] YAML与docstring同步维护，没有引入第二套优先级。
- [x] 每条均有old/new/source/reason四列；语义按handler、schema和约束核对。
- [x] 描述改动没有修改工具name、inputSchema、默认值、返回结构、handler、权限、确认流程与副作用。历史修复前handler绑定快照未保存，因此不声称已做历史绑定前后独立比较。
- [x] 全量重审`description-audit.tsv`共109条逻辑记录，97条`valid`、12条`vague`，无missing/blank；12条修改均可追溯。

产物：`description-changes.tsv`、新版`description-audit.tsv`、代码diff与测试结果。

## 4. R2：收口回归和真实协议验收

### 4.1 描述与兼容回归

- [x] YAML fallback、空白fallback、有效描述保留、精确工具名映射、无映射告警、禁用组不注册等测试通过。
- [x] 工具名集合、inputSchema与数量未变；仅预期12条description变化。历史handler绑定快照缺失，未做回溯比较。
- [x] 审计TSV用正规序列化/解析，支持多行docstring；按逻辑记录统计，检查列数，不以物理行数统计工具。重建脚本使用`csv.writer`；另用`csv.reader`校验109条工具记录、13列及分类状态。

### 4.2 四组工具清单一致性

- [x] 已分别捕获in-process runtime、STDIO、Streamable HTTP、SSE完整tools/list。
- [x] 四组按工具名规范化后对比name、inputSchema、description。
- [x] `schema-diff.json`列出四组及差异；均为109项且无差异。
- [x] 所有启用工具description非空，12条新描述在三种外部传输中可见。

### 4.3 完整测试组重跑

- [x] SSE测试helper已改用GET并按当前transport契约验证。
- [x] 最新完整MCP套件67项收集、67通过、0失败、0跳过；Seqout部分用确定性adapter fixture，不代表provider live成功。当前工作树重跑同样为67/67。详见`mcp-server-full-suite-2026-10-19.txt`。
- [x] 缺/错Token、平台Key不能替代MCP Token、短Token与非loopback拒绝测试保留并通过。
- [x] dummy平台地址结果仅计协议/安全负测，不计平台业务成功。
- [x] 真实外部客户端initialize→tools/list→tools/call的代表性只读协议调用有证据：STDIO SDK 客户端及 HTTP Inspector 均完成握手/枚举/只读调用；HTTP 调用到达工具但因 dummy 平台地址失败。另有官方 STRING MCP 独立只读调用。它们证明协议调用路径，不证明 CygnusX 平台业务正向成功；正向成功仍需R4隔离实例。

产物：四组原始清单、`schema-diff.json`、`before-after-contract-diff.json`、完整测试输出与协议日志。

## 5. R3：隔离测试身份与环境准备

- [x] 使用loopback隔离平台实例、专用Postgres/Redis和普通测试用户（role=user）；无生产管理员身份。测试DB版本边界见`isolated-platform-identity-2026-10-19.json`。
- [x] 专用平台API Key以临时进程环境注入，权限为`flows:read`/`research:read`；MCP HTTP Token与平台Key独立配置。正向业务调用使用STDIO，凭据值未入证据。
- [x] `CYGNUSX_BASE_URL`指向隔离API `http://127.0.0.1:8017`，health为200；经实际MCP→平台→ClinVar成功响应验证，见`platform-chain-positive-2026-10-19.json`。
- [x] 19个Agent的隔离DB绑定/preset状态只读快照已导出；隔离Redis已提供，但确认门/Redis链未执行，不据此声称通过。
- [ ] 尚无可读测试任务、报告和工作区文件。隔离身份下`cygnusx://flows/catalog`已读到2项结构化目录数据；`cygnusx://user/storage`因测试Key缺少scope被拒绝，task/report模板仍未用真实测试资产读取。证据：`resources-platform-chain-2026-10-19.ndjson`。
- [x] 隔离服务经固定HTTPS host对16项已实现provider发起小规模只读调用；Expression Atlas bulk目录超时，详见provider MCP证据。
- [x] 外部请求携带X-Request-ID，MCP client log记录平台HTTP状态与request ID；平台审计记录对应用户、路由与状态，详见相邻日志。

剩余R3条件为可读任务/报告/工作区测试资产及Redis确认门验收；静态Resource目录的正向读取已完成，但用户存储Resource尚无正向授权样例。隔离实例已在验收后关闭，测试身份与临时Key已清理；不将真实Key写入聊天或报告。

产物：脱敏`test-environment.json`、权限/资产准备记录。原始secret不交付。

## 6. R4：验证真实业务链与17资源状态

### 6.1 平台与工具正向样例

- [x] 外部MCP→隔离平台REST→ClinVar样例成功返回业务数据；STDIO、Streamable HTTP、SSE各有独立trace，见`platform-chain-positive-2026-10-19.json`。这只验证ClinVar样例，不代表所有平台工具。
- [ ] Resource读取完整验收仍未完成：`cygnusx://flows/catalog`经外部STDIO MCP→隔离REST返回2项结构化数据；`cygnusx://user/storage`返回scope 403，属于真实授权拒绝而非读取成功。task outputs/report模板没有真实测试对象，越权与不存在对象的对照也未跑。证据：`resources-platform-chain-2026-10-19.ndjson`。
- [x] STDIO、Streamable HTTP、SSE各完成ClinVar代表性业务正向调用；其它provider逐项用STDIO抽测。

### 6.2 逐provider调用

17项必须逐项列状态，原始三库不得省略：MyGene、MyVariant、MyChem、Ensembl Plants、Gramene、Dfam、Expression Atlas、Single Cell Atlas、STRING、Europe PMC、ClinVar、Open Targets、UniProt、RCSB PDB、AlphaFold DB、Reactome、InterPro。

- [x] 16项已实现provider均经外部MCP→隔离平台API→service/adapter尝试：15项业务成功，Expression Atlas bulk目录超时；逐工具输入、结果摘要、时间、request ID见`provider-mcp-platform-2026-10-19.ndjson`和followup日志。STRING单列未实现。
- [ ] 缓存证据未全覆盖：代码中除Atlas目录外未发现应用结果缓存；single-cell目录在隔离API进程首次请求成功，bulk首次请求超时。其余工具没有独立cache-miss埋点，需保持该限制。
- [ ] 检查业务内容：JSON/FASTA/XML按预期解析；HTML200、GraphQL errors、认证错误不算成功；not_found为负样例，不满足正向命中验收。
- [ ] Gene/Variant/Chem额外检查物种/assembly/盐型与候选语义；其他关键边界按完整文档选择代表性测试，不对公共服务压测。
- [ ] Reactome知识与Analysis、Atlas目录与定量、InterPro查询与Scan等子能力分别标状态，不以一个GET成功覆盖整个数据库全部功能。
- [x] STRING未以stub冒充已接通；已新增版本固定的REST adapter和两个只读工具。其MCP→认证平台REST、Agent授权与部署仍未验证，须按`implemented_unverified`记录，不算live验收通过。

状态词汇：`not_implemented`、`registered_unverified`、`implemented_unverified`（需实现代码证据）、`blocked_precondition`、`passed_live`、`failed_live`、`not_tested`。另列`attempted/cache_status/transport_verified/platform_verified/provider_verified`，避免混淆。

失败与环境阻塞保留真实状态；没有全部完成时最终仍写部分验收。

产物：`provider-status.tsv`（17项逐资源状态）、`provider-verification-matrix.tsv`、`business-e2e.ndjson`、脱敏trace索引与失败分类。各项仅代表表中注明的单一或少量样例，不代表资源全部子能力。

## 7. R5：导出19个Agent最终工具清单

R3环境就绪后可与R4同时推进；不等待17库全部成功才导出。

- [x] 固定启用清单19个Agent ID并以隔离测试用户/context_ref导出；名单、工具数见`agent-loading-summary.tsv`。
- [x] 19个Agent均经隔离实例真实DB上下文装配，快照记录preset绑定、enabled状态、白名单及实际裁剪原因；未配置case-specific能力矩阵，不声称该维度已覆盖。
- [ ] 尚未对19个Agent逐一发送Provider请求。已有Provider发包边界manifest运行时实现/回归，但逐Agent快照停在最终AgentContext集合，未发生模型调用，Provider后续过滤/merge仍未逐Agent实测。
- [x] 逐Agent统计最终context工具及BioThings/Research Data数量，见逐AgentJSON与`agent-loading-summary.tsv`。
- [x] 每个context工具导出name、description、inputSchema、server/preset来源和contract digest；无secret、提示词、消息或会话。
- [x] 导出代码实际产生的候选工具裁剪原因；没有发生的case_gate等原因不伪造。
- [x] 已统计19个Agent实际工具数/schema字节数（工具数72–98）；详见TSV，不以静态36项推断过载。
- [x] platform-only受限上下文16个工具，BioThings/Research Data均为0；flows-only身份经MCP调用Research Data工具被403拒绝、provider未触发。证据见`agent-general-restricted-context-2026-10-19.json`及`agent-general-restricted-mcp-invoke-2026-10-19.json`。只覆盖一次server裁剪和API scope，不覆盖所有用户capability/case规则。
- [x] 输出能力裁剪建议：19个Agent当前统一装配research pack中的BioThings 10项和Research Data 26项；结合实际tool snapshot，后续应按Agent用途拆分数据库pack，并优先对非检索/非科研Agent做逐Agent allowlist评估。此建议未改绑定；旧`ensmbl`/`go-server`外部注册和生产用户绑定状态仍不可由隔离DB证明，保留原名/ID并要求部署侧盘点后再去重。详见`capability-dedup-matrix.tsv`与`agent-loading-summary.tsv`。

建议文件：`agents/<agent_id>/final-tools.json`、`agents/<agent_id>/filter-decisions.json`、`agent-tool-loading.tsv`。

TSV至少包含：agent_id/name、context_ref、bound_presets、enabled_presets、final_tool_count、biothings_count、research_data_count、schema_bytes、token_measurement_method、unexpected_tools、evidence_ref。当前`agent-loading-summary.tsv`已从19份隔离快照重建为12列；token测量与Agent专用allowlist尚未执行，分别显式记为`not_measured`和`not_assessed`，schema字节数不等于token估算。只导出工具相关元数据，不导出完整系统提示、会话、患者信息或secret。

## 8. R6：报告与交付收口

- [x] 更新结论为各层独立状态：描述质量、协议传输、平台业务、provider、Agent最终装配；不能用一个“通过”覆盖全部。报告仍明确结论为部分验收。
- [x] 明确当前版本四组schema对比，与修复前后兼容性比较是两种测试。
- [x] 报告中所有数量来自可解析产物，TSV按记录、测试按收集结果、provider按独立资源统计。
- [x] 对`optimize_in_sandbox`的subprocess示例读取当前安全契约；确认与Agent无shell边界冲突后，已替换为已有文件工具，并保留未部署风险记录。
- [x] 记录未进行的Prompt模型语义级对抗/写确认/Redis等测试；in-process、STDIO、Streamable HTTP、SSE渲染边界4项通过，不把局部测试或dummy负测扩大成安全全通过。
- [x] 交付证据已含描述对照、四组schema、完整MCP套件、provider MCP traces、17项资源状态、19 Agent清单与checksums；仍待补Resource任务/报告/工作区真实资产、其余cache miss独立证明、逐Agent Provider实发集合、模型级Prompt攻击验证和生产部署验证。逐项17资源与去重状态汇总见验收报告和`provider-status.tsv`/`capability-dedup-matrix.tsv`。
- [x] 不自动修改生产注册项、删除旧MCP、全量重绑Agent或部署生产；本轮验收仍仅针对隔离环境，未把工作树修正写成已部署。

## 9. 完成判据

**描述与回归整改完成**：本轮12条描述准确可见；名称/schema/绑定/行为无非预期变化；原完整回归与新增测试无未解释失败；四组清单对比证据完整。

**业务与Agent验收完成**：真实隔离身份下平台正向链成功；17资源都有可追溯状态（未实现/未测不算通过）；19Agent的最终工具与裁剪原因均已导出。若仍有provider或环境缺口，明确部分验收，不得写17库全部接通。

最终摘要固定回答：改了哪12条？完整测试通过/失败/跳过多少？四组是否一致？平台真实成功哪些？17库各状态？19Agent实际分别加载多少？剩余阻塞是什么？没有证据的项写未验证。

## 10. 后续工作树更新（2026-10-19）

按完整实施提示词继续实现STRING：不注册版本不可固定且能力面未受平台权限/预算约束的官方托管MCP，新增固定 `https://version-12-5.string-db.org/api/tsv` REST adapter。内置 `cygnusx-research-data` preset 增至28项，外部FastMCP组新增 `cygnusx_string_resolve` 和 `cygnusx_string_network`，经既有认证 `/api/v1/research-data/{tool_name}` 桥接到同一 `research_data_service`；research Agent工具包白名单加入两工具。实现要求 taxon 显式、候选不自动消歧、functional/physical/regulatory分开、默认节点扩展关闭、最多50条、响应2 MiB上限及共享Redis 1秒限速。regulatory保留 source→target 方向；所有网络行保留provider字段并补充明确的partner ID/name字段。Redis Lua限速已通过真实隔离Redis多进程探测：4个独立Python进程各获取2次名额，7个相邻间隔均为1001 ms；Redis关闭后服务返回ConnectionError失败。证据见string-redis-multiprocess-2026-10-19.json及同目录probe脚本。该结果仅证明名额获取间隔，不替代HTTP发包或认证平台链验收。

真实只读adapter抽样：TP53/taxon 9606映射到`9606.ENSP00000269305`；physical样例首个伙伴为SIRT1，regulatory样例为TP53→MDM2。范围仅为当前本地FastMCP `call_tool`→外部adapter→STRING REST直连，没有经过MCP wire或认证平台REST；不能把它记作平台链验收。证据为`evidence/mcp-external-validation-2026-10-18/string-rest-direct-probe-2026-10-19.json`。STRING状态是`implemented_unverified`。19个Agent快照早于这两工具加入，尚未对新工具做隔离用户裁剪复验或模型Provider发包验证。

STRING的注册错位回归修复：Europe PMC annotations 已从 STRING 注册函数作用域拆出并重新归属 clinical_literature；外部研究工具定向测试18/18、平台API/research-preset/双表面回归71/71、外部MCP完整套件72/72通过，Ruff和相关service/preset strict mypy通过。四面工具清单重新捕获为111项，名称、schema和描述一致；当前描述审计111条、99 valid、12 vague，无空描述。相对旧109项基线新增两工具；累计兼容差异含之前ClinVar schema变化，详见`before-after-contract-diff.json`，不是STRING单独造成的差异。未部署生产。R4仍缺STRING平台正向链、Resource真实资产、全provider cache-miss；R5仍缺19 Agent实际Provider发包集合；模型级Prompt injection和生产部署均未完成，结论保持部分验收。
