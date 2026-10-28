# 科研寻宝鼠：更新接入审计与界面实现

本地核对日期：2026-10-25。范围：平台 `/treasure-mouse` 的现有 React Island 展示树，以及子仓共享 UI；依据用户提供的视觉任务书与当前页面截图。任务书引用的目标截图 B 未随附件提供，因此按其明确的颜色、排版、间距和响应式规范实现，不能声称逐像素复刻 B。

## 1. 更新是否自动生效

| 对象 | 当前行为与证据 |
| --- | --- |
| 本地子仓 | 开始审计时 HEAD 为 `55c8912`，父仓记录为 `51a401d`；已有版本差异不是本次引入的脏改动 |
| 平台界面 | `frontend/package.json` 的 `predev`/`prebuild` 执行 Island 构建，消费子仓当前共享组件和样式；改源码后需要重新构建或重新启动开发服务，并刷新浏览器 |
| 平台业务 | Vue 工作台、BFF、平台账号/项目/会话/API 仍独立维护；独立 SPA 新增消息队列、后台任务、自托管账号/历史不会自动接入 |
| 新增检索工具 | protocols.io 等由实际运行的 Node 服务代码、配置与令牌共同决定；前端重新构建不更新 Node 服务 |
| 当前 Node 容器 | 已在平台统计接入时更新为 `cygnusx-treasure-mouse-chat:16f2376`；镜像来自该子仓已提交源码，容器 `/app/functions/seqout-chat/index.ts` 与提交版本 SHA-256 均为 `61fb4bd6dea98bd6d91672bcb02b1215e854f4ab49eab3af915221fcf2b0f147`。未把工作区其他未提交改动打入镜像，验证范围见 §10 |
| 当前前端托管 | `cygnusx-nginx` 只读挂载宿主 `frontend/dist`；本地生产构建会更新它实际提供的前端文件。Island 稳定入口已有 `Cache-Control: no-cache`，无需修改缓存策略 |

子仓新版任务协议保留无 `session_ref` 的兼容聊天路径；平台现有 BFF 仍请求受信 `/cygnusx/discovery`，不发送该字段。本轮子仓 Node HTTP/协议测试与平台隔离测试通过，但未将其当作真实模型、真实数据库和跨进程后台任务的运行验收。

共享 UI 修改已在子仓提交为 `e4f462b`；父仓配套提交记录平台代码与该子模块指针，未推送。运行截图和日志保留在本地证据目录，不纳入提交。

## 2. 已修复的兼容问题

1. 临时打包仅复制 `src/`。新版类型引用 `shared/history.ts`，复现 `TS2307`；构建现补复制 `shared/`。
2. Dockerfile 仍 `COPY` 已移走的根 `vite.island.config.ts`；现复制 `archive/island/`、`shared/` 和 `tsconfig.json`，符合当前布局。
3. PoC 脚本和类型声明仍引用已归档路径或旧 `/tmp` 产物；现构建、检查实际 `frontend/public/treasure-island` 产物，类型声明复用平台 DTO。
4. Island 的业务实现导入边界检查继续保留，防止误打包独立 SPA 的账号/会话/网络实现。归档目录不修改；父仓维护平台展示覆盖文件。

Docker 冷构建已通过子仓冻结依赖安装及新目录 COPY，随后在父仓原有 `npm ci` 阶段报 `Invalid Version:`，国内源与官方回退相同。未手改或重新生成锁文件，也未声称容器镜像构建成功。

## 3. 页面、状态与设计令牌

原结构：Vue 工作台 → Shadow DOM 中的 `FullPresentation` → `SessionSidebar`、`EmptyState`、`Composer`、`ChatMessage`、桌宠与业务弹层。子仓为 React 19 + TS + Tailwind 4、Lucide 与现有 Radix 组件，父仓为 Vue/Pinia/Naive UI；继续沿用这一边界。

修改前的主要差异是 11px 辅助字号、偏米色背景、分散圆角、示例行层次弱、顶栏窄屏拥挤，以及 768px 对话容器叠加助手 92% 限宽。修改后：

- 颜色：画布 `#F8FAFC` / `#F3F8FD`，侧栏 `#FBFAF8`，品牌绿 `#218747`，浅绿 `#E8F7EC`，浅金 `#FFF4D6`，示例 `#F5F3F0`，正文 `#242B33`，次级文字 `#69737D`，边框 `#E8EBEF`。
- 保留既有字体与双主题；新增 `--canvas-tint`、`--example`、`--grid-dot`、阴影与间距令牌，暗色成对定义。字号 12/13/14/16/22px，欢迎标题桌面 28px；20px 卡片圆角，轻投影。
- 首页、回复与输入共用 `--workspace-width: 960px`；助手占满头像右侧可用空间。桌面卡片两列，640px 以下单列，长编号/英文可换行。
- 历史侧栏默认折叠为桌面窄轨，用户可手动展开；移动端默认关闭抽屉。展开后保持品牌、新建、搜索、分组历史、重命名、归档及账号分支；顶栏允许窄屏换行，图标按钮有访问名称，移动点击区域 44px。
- 平台桌宠默认收起，通过顶栏设置召回后继续支持互动/拖拽/静默；独立 SPA 默认行为保留。修正新会话手机端错误自动滚底；欢迎区彩蛋仍在 Shadow DOM 内呈现。

## 4. 文件变更清单

子仓（`pipelines/Treasure-Seeking_Mouse/`）：

| 文件 | 主要修改 |
| --- | --- |
| `src/styles.css` | 统一亮暗令牌、画布、工作区宽度、卡片/示例、输入和顶栏响应式 |
| `src/components/chat/EmptyState.tsx` | 欢迎区、2×2 能力卡、示例样式；保留八条示例与彩蛋 |
| `src/components/chat/Composer.tsx` | 统一输入与回复宽度、44px 操作、模型长文本与图标名称 |
| `src/components/chat/ChatMessage.tsx` | 去掉助手内部额外的 92% 宽度限制 |
| `src/components/chat/SessionSidebar.tsx` | 浅绿色主操作、独立搜索、账号区、当前会话语义与关闭按钮访问名称 |
| `src/components/pet/TreasureMouse.tsx` | 可选 `startQuiet`，平台由既有顶栏召回，独立 SPA 默认不变 |
| `src/routes/index.tsx` | 独立 SPA 复用相同顶栏与回复宽度样式 |
| `docs/ARC/frontend-style-spec.md` | 同步当前视觉规范 |

父仓：

| 文件 | 主要修改 |
| --- | --- |
| `frontend/treasure-island/index.tsx` | 从冻结适配器接管平台挂载入口；保留 Shadow DOM、portal 与资源清理，移除重复顶栏内联样式 |
| `frontend/treasure-island/FullPresentation.tsx` | 平台展示覆盖层；顶栏、侧栏、宽回复、新会话滚动与桌宠初态 |
| `frontend/treasure-island/ResearchWorkflowPanel.tsx` | Dataset 与通用下载/分析预案共用的展示层；按每条预案的实际 prepare 能力、状态及有效期控制人工审批，审批路由由 Vue 持有 |
| `frontend/treasure-island/README.md` | 说明暂存编译与业务所有权 |
| `frontend/scripts/build-treasure-island.mjs` | 新布局复制与覆盖层暂存；保留 TS/依赖边界检查 |
| `deploy/docker/Dockerfile.frontend` | 修复旧 COPY 路径，沿用冻结依赖与国内源/官方回退 |
| `frontend/poc/treasure-island/{island.d.ts,vite.config.ts,vitest.config.ts}` | 真实产物路径和平台类型来源 |
| `frontend/poc/treasure-island/{setup.ts,island.poc.ts,platform-entry.poc.ts}` | jsdom 媒体 API、当前文案/侧栏初态、异步受控输入等待；保留业务断言 |
| `scripts/poc/check-treasure-island.sh` | 将回归入口更新为当前构建流程 |
| `scripts/poc/treasure-ui-browser.mjs` | Chromium 实际渲染、视口和交互检查及截图 |
| 本文与寻宝鼠架构文档 | 接入审计、设计与验证结果 |
| `ARCHITECTURE_DESIGN/README.md`、镜像国内加速协议台账 | 文档入口与修改的 Dockerfile 登记 |

## 5. 验证结果与证据边界

| 命令 / 范围 | 结果 |
| --- | --- |
| 子仓 `npm run typecheck`、`npm test`、`npm run build` | 通过；195 passed，1 skipped；仅已有大 chunk 提示 |
| 父前端 `npm run type-check`、`npm test`、`npm run build` | 通过；94 文件、691 测试；测试环境有已有 jsdom 提示 |
| `scripts/poc/check-treasure-island.sh`（设置浏览器路径） | Island TS、16 项接入测试、Vue PoC 类型/构建、Chromium 检查 |
| 后端寻宝鼠两个相关测试文件 | 46 passed |
| 全仓迁移链检查 | 通过，单 head |
| AgentTeams bridge 测试 | 190 passed，2 skipped |
| 全仓 Ruff | 265 个问题；本次未修改相关 Python 文件 |
| 全仓 mypy | 1009 个错误，涉及 212 文件；本次未修改相关 Python 文件 |
| 全仓 unit + e2e，排除 quarantine | 4127 passed，14 failed，22 skipped，63 deselected；失败位于已有并行子代理、provider、研究 MCP 绑定、Studio 授权/挂载、工具确认码及 LangGraph 沙箱批准测试；详见证据摘要 |
| Docker 冷构建 | 父前端原有 npm 锁文件 `Invalid Version:` 阻断，未改锁文件 |

没有新增业务接口、迁移、数据库写入或 UI 依赖。平台接入用例仍验证会话隔离、权限禁用、消息流、卡片/grounding/下载提示历史投影、数据集预案、语言/主题隔离与原弹层。浏览器使用明确的 fixture props 和回调驱动实际构建的 React 展示层，并非真实账号或科研数据回归；真实后端链路的准入结论继续以主架构文档为准。

浏览器视口：1440×900、1280×800、1024×768、390×844，各检查中文/英文、浅色/深色以及欢迎/回复状态；覆盖长文本、图片、列数、横向溢出、新建/搜索/历史、示例/输入/模型/停止、禁用/错误、主题/语言、桌宠召回/静默、移动抽屉、彩蛋与 Escape、减少动态效果。

证据在 [`evidence/treasure-ui-refresh/`](../evidence/treasure-ui-refresh/)，含 JSON 检查结果、24 张截图及测试/构建日志。关键截图：

- [桌面欢迎页](../evidence/treasure-ui-refresh/welcome-1440-zh-light.png)
- [加宽回复区](../evidence/treasure-ui-refresh/chat-1440-light.png)
- [手机英文深色](../evidence/treasure-ui-refresh/welcome-390-en-dark.png)
- [完整检查结果](../evidence/treasure-ui-refresh/browser-result.json)
- [全仓后端失败摘要](../evidence/treasure-ui-refresh/backend-full-suite-summary.txt)

## 6. 尚存差异与后续更新

目标截图 B 缺失，当前按文字规范统一而非像素对齐；保留现有产品的四类入口、文案与夜探矿洞暗色主题。主平台外层 CygnusX 导航、真实登录和项目权限继续由平台负责，本轮没有模拟替换产品业务。

需要更新 Node 检索/任务能力时，应单独按现有镜像 SHA 规范构建并核对运行镜像，再验证平台受信端点；不能把子仓拉取、前端重建或本轮截图当作后端已升级。全新容器安装还需先处理原有前端锁文件问题。其他人的文档移动和技能元数据改动未纳入本次变更。


## 7. 首页研究入口

首页 Hero 两个 CTA 通过命名路由 `treasure-mouse` 传入一次性 `start=new` / `start=plan`。`TreasureMouseView` 初始化时读取意图并用 `router.replace` 仅移除该参数，保留其余 query/hash；不新增历史项，后退回首页，刷新/前进不重复创建。

`TreasureResearchWorkbench` 在原能力预检和项目/会话列表加载后，跳过默认恢复最近会话，复用原 `createSession()` 创建全局上下文新会话。`plan` 预填“请帮我规划一项研究方案，先和我确认研究问题、研究对象、已有数据与预期目标。”；未新增方案模式或后端接口，也不自动发送。无入口参数时原最近会话恢复行为保留。权限不足与创建失败沿用既有错误提示；离开页面后迟到预检不触发创建。

`TreasureOriginalDisplay` 的可选 `focusDraft` 在真实 Island 同步挂载/更新后定位开放 Shadow DOM 内的可编辑 textarea，仅聚焦一次，不改 React/子仓的 Composer 或业务行为。两按钮对应的新会话与草稿不写入历史会话。

分析中心 `/flows`、平台导航及首页多组学快捷入口保持独立。前端回归包含新会话不恢复历史、方案草稿、不重复创建、权限/失败/导航竞态；浏览器隔离验证使用实际 Vue 页面与构建后的 React Island、桩 API，覆盖聚焦、后退、分析中心列表和移动端。此验证不等同生产模型或后端执行验收。


## 8. 聚焦校验与回复连续性

问题路径：原工作台将 window focus 直接绑定 refreshAccess()，每次先中断当前 SSE、清空会话/消息，再重新打开最近会话。等待历史消息期间会出现空消息欢迎页，造成“回复 → 寻宝鼠首页 → 回复”的闪跳；SSE 终态与标题更新本身未执行路由跳转。

工作台现将 focus 绑定独立的后台权限校验：正常授权时仅更新能力与项目列表，保留 activeSessionId、messages、loading 状态和进行中的流，不加载最近会话、不恢复历史消息。校验用 sessionGeneration 与请求序号丢弃旧会话/旧项目/旧焦点请求的迟到结果。初始预检期间的 focus 仍允许重启预检，保留既有过期项目结果隔离行为。

read_sessions 被撤销、401/403、当前项目授权被移除时，仍中断流并清理私有历史；发现能力被撤销时禁用发送并中断生成，保留仍有权读取的历史。临时网络错误保留当前回复并显示原错误提示。显式新建、会话切换、项目切换及工具/执行授权沿用原有入口。

FullPresentation 的 collapsed 初始值为 true；更新消息/终态/标题不会重新初始化该 React 状态，用户主动展开后仍保持展开，移动端抽屉仍由独立 drawer 状态控制。

验证包含聚焦期间与回复终态/标题更新交错、SSE 后续增量、当前会话不是最近会话、权限撤销/网络故障/项目撤权/过期结果等回归。浏览器用正式构建 App/DefaultLayout、真实 HTTP 分段 SSE、隔离 API 桩监测回复 DOM 连续性，不等同真实模型/科研后端运行验收。

## 9. 草稿编辑与光标连续性

`Composer` 用 React 本地状态即时控制 textarea，Vue 工作台通过 `onValueChange` 在下一 tick 回显草稿。外部 prop 同步 effect 原先同时依赖 `value` 和 `localValue`，本地输入后会先把旧 prop 写回，再接收 Vue 新值；浏览器复现：在 `ABCDEFGH` 的 `AB` 后连续输入 `123` 得到 `AB1CDEFGH23`，光标被 value 重写移到文末。

共享组件现仅在外部 `value` 真正变化时同步，保留组合输入本地状态及外部示例预填、清空行为。修改位于子仓活动 `src/components/chat/Composer.tsx`，平台仍经原 Island 构建消费，不修改归档适配器。

浏览器回归入口为父仓 `scripts/poc/chat-input-editing-browser.mjs`：挂载真实 `TreasureOriginalDisplay` 和构建后 React Island，通过 Vue v-model 回显，覆盖欢迎/对话两布局的连续插入、选中替换、中间删除、多行、中文插入、CDP composition、外部预填及无关渲染的选区保留。同一脚本挂载 AI 助手/工作台复用的 `KimiChatInput` 和真实全局侧栏组件，后端与模型为隔离桩；系统中文输入法候选窗口不属于自动化范围。

本轮验证：上述浏览器检查全部通过（`evidence/chat-input-editing/browser-result.json`）；父前端 type-check、100 文件/739 测试、生产构建通过，Island 接入 16 测试通过；子仓 typecheck、195 测试通过/1 跳过、构建通过。AI 助手/工作台共用组件未复现同类跳光标，侧栏另外修复中文候选确认 Enter 误发送（composition 状态、229 与结束后 200ms 保护），普通 Enter 发送仍通过。未把隔离组件验证当作真实模型链路验收。

## 10. 平台排行榜、昵称与使用统计

排行榜与统计改由 Vue 宿主的 `researchAgentApi` 调用 `/research-agent/leaderboard?period=all|week`、`GET /research-agent/stats`、`PATCH /research-agent/nickname`，经 `PlatformStatsProps` 和 React PresentationContext 传给共享组件。构建阶段只扩展暂存 contract，不修改子仓归档文件。三个接口均复用平台 JWT/账号激活状态、寻宝鼠模块权限与 native 开关，读取历史统计不依赖 Node 在线；不调用独立站账号接口、不接访客设备统计，也不接受浏览器上报计数。

`ResearchStatsService` 流式读取带 `research-treasure-mouse` 标记的会话及 terminal assistant 消息快照（含已归档会话，排除仍在生成的消息、普通 AI 聊天和非 active 用户）。宝藏为每轮去重后的发现卡片数，不代表已验证或已导入的 Dataset；同卡在不同轮次出现仍分别计数。下铲为完成或失败的工具调用，排除 running 中间帧及 intent_plan/grounding_check 审计项。统计依据当前保留的消息，无新表、无迁移、无重复刷新/重放增量。周界为 `TREASURE_STATS_TIMEZONE`（默认 Asia/Shanghai）的周一 00:00；服务端分别排序周榜/累计榜并返回前 100 名及完整总数，周榜只含本周有终态记录的用户。

公开响应仅含哈希用户键、显示昵称和聚合计数；不返回用户 UUID、邮箱、登录名、会话/项目/消息内容或凭证。`ownKey` 用于标记“我”。昵称校验为 trim 后 1–16 字、无控制字符，行锁下合并写入本人 `users.preferences.treasure_mouse_nickname`，保留其他设置，不改变平台昵称/登录身份；默认优先平台公开昵称，否则使用匿名显示名。平台只显示“平台寻宝榜”，不展示无对应身份源的“临时矿工”。

供应商每轮 usage 由 Node 的独立请求上下文累积，以新增 `usage` 帧传给 BFF，并在 terminal 消息保存 `metadata_json.usage` / `llm_calls`；旧客户端忽略未知帧，重放只读取同一快照。此数据仅用于统计，不改扣费规则、不用字符估算补齐缺失历史 Token。统计响应含 `usageRecordedChats`，页面明确显示记录覆盖率，完全没有记录时显示“—”。错误/重试与迟到请求隔离由共享展示组件处理，回调不随草稿变动重复请求。

验证包含真实 PostgreSQL 独立 schema + HTTP/JWT 的统计/隐私/改名持久化/权限/周界与去重测试、BFF usage 重放测试、Node 并发请求用量隔离测试，以及实际 Vue 工作台、构建 React Island、axios HTTP fixture 的浏览器检查。浏览器入口 `scripts/poc/treasure-stats-browser.mjs`，证据 `evidence/treasure-platform-stats/`。联网真实模型不用于测试数据生成，历史缺失用量不回填。

本次运行验收：前端 102 文件/758 测试、type-check、生产构建通过；后端相关单元与 PostgreSQL 隔离接口测试 55 项通过，新增服务/DTO/路由 Ruff 和定向 mypy 通过，迁移检查通过。以子仓 `16f2376` 的 git archive 构建镜像（197 测试通过、1 跳过），已替换本机寻宝服务并重启 Web，两者 healthy。真实 JWT 的累计/周榜/统计接口均 HTTP 200，生产 `/treasure-mouse` 浏览器通过；验收时保留数据为 308 张卡片、本周 117 张、9 轮、17 次工具调用、2 个账号，历史 Token 记录覆盖 0/9。真实运行镜像另用隔离 OpenAI SSE fixture 验证解析 37 输入/5 输出并发出 total=42 的 usage 帧：`scripts/poc/treasure-runtime-usage.mjs <image:sha>`；未调用真实模型或修改真实用户昵称。

门禁边界：最后一次 Island PoC 为 14/16 通过，2 项数据集检查/导入预案测试在并行共享工具适配变更后失败，不属于排行榜回调验证；本次不覆盖该并行变更。额外直接编译 Node tasks 依赖闭包仍有原有类型问题（RoundDigest 重复导入、GroundingReport/存储快照转换等）；子仓规范的前端 typecheck 与实际 Node HTTP/协议测试通过，不将其表述为整个 Node 后端严格类型检查全绿。全仓既存后端 Ruff/mypy/测试失败结论不因本次定向通过而改变。
