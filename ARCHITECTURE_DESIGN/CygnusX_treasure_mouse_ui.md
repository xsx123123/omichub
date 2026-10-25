# 科研寻宝鼠：更新接入审计与界面实现

本地核对日期：2026-10-25。范围：平台 `/treasure-mouse` 的现有 React Island 展示树，以及子仓共享 UI；依据用户提供的视觉任务书与当前页面截图。任务书引用的目标截图 B 未随附件提供，因此按其明确的颜色、排版、间距和响应式规范实现，不能声称逐像素复刻 B。

## 1. 更新是否自动生效

| 对象 | 当前行为与证据 |
| --- | --- |
| 本地子仓 | 开始审计时 HEAD 为 `55c8912`，父仓记录为 `51a401d`；已有版本差异不是本次引入的脏改动 |
| 平台界面 | `frontend/package.json` 的 `predev`/`prebuild` 执行 Island 构建，消费子仓当前共享组件和样式；改源码后需要重新构建或重新启动开发服务，并刷新浏览器 |
| 平台业务 | Vue 工作台、BFF、平台账号/项目/会话/API 仍独立维护；独立 SPA 新增消息队列、后台任务、自托管账号/历史不会自动接入 |
| 新增检索工具 | protocols.io 等由实际运行的 Node 服务代码、配置与令牌共同决定；前端重新构建不更新 Node 服务 |
| 当前 Node 容器 | `cygnusx-treasure-mouse-chat:1ea2f79`；容器 `/app/functions/seqout-chat/index.ts` 的 SHA-256 为 `5a323716d51dccc75c22e279694dd724378b9d8e609b77915a7d831d7101f950`，当前源码为 `919e932606d6e09aecd231528d93ce96ea369331dce469fcdab186c9ef4bee9a`，确有运行版本差异；本轮未重启或替换该容器 |
| 当前前端托管 | `cygnusx-nginx` 只读挂载宿主 `frontend/dist`；本地生产构建会更新它实际提供的前端文件。Island 稳定入口已有 `Cache-Control: no-cache`，无需修改缓存策略 |

子仓新版任务协议保留无 `session_ref` 的兼容聊天路径；平台现有 BFF 仍请求受信 `/cygnusx/discovery`，不发送该字段。本轮子仓 Node HTTP/协议测试与平台隔离测试通过，但未将其当作真实模型、真实数据库和跨进程后台任务的运行验收。

共享 UI 修改已在子仓提交为 `e4f462b`；父仓配套提交记录平台代码与该子模块指针，未推送。运行截图和日志保留在本地证据目录，不纳入提交。

## 2. 已修复的兼容问题

1. 临时打包仅复制 `src/`。新版类型引用 `shared/history.ts`，复现 `TS2307`；构建现补复制 `shared/`。
2. Dockerfile 仍 `COPY` 已移走的根 `vite.island.config.ts`；现复制 `archive/island/`、`shared/` 和 `tsconfig.json`，符合当前布局。
3. PoC 脚本和类型声明仍引用已归档路径或旧 `/tmp` 产物；现构建、检查实际 `frontend/public/treasure-island` 产物，类型声明复用平台 DTO。
4. Island 的业务实现导入边界检查继续保留，防止误打包独立 SPA 的账号/会话/网络实现。归档目录不修改；父仓维护两个平台展示覆盖文件。

Docker 冷构建已通过子仓冻结依赖安装及新目录 COPY，随后在父仓原有 `npm ci` 阶段报 `Invalid Version:`，国内源与官方回退相同。未手改或重新生成锁文件，也未声称容器镜像构建成功。

## 3. 页面、状态与设计令牌

原结构：Vue 工作台 → Shadow DOM 中的 `FullPresentation` → `SessionSidebar`、`EmptyState`、`Composer`、`ChatMessage`、桌宠与业务弹层。子仓为 React 19 + TS + Tailwind 4、Lucide 与现有 Radix 组件，父仓为 Vue/Pinia/Naive UI；继续沿用这一边界。

修改前的主要差异是 11px 辅助字号、偏米色背景、分散圆角、示例行层次弱、顶栏窄屏拥挤，以及 768px 对话容器叠加助手 92% 限宽。修改后：

- 颜色：画布 `#F8FAFC` / `#F3F8FD`，侧栏 `#FBFAF8`，品牌绿 `#218747`，浅绿 `#E8F7EC`，浅金 `#FFF4D6`，示例 `#F5F3F0`，正文 `#242B33`，次级文字 `#69737D`，边框 `#E8EBEF`。
- 保留既有字体与双主题；新增 `--canvas-tint`、`--example`、`--grid-dot`、阴影与间距令牌，暗色成对定义。字号 12/13/14/16/22px，欢迎标题桌面 28px；20px 卡片圆角，轻投影。
- 首页、回复与输入共用 `--workspace-width: 960px`；助手占满头像右侧可用空间。桌面卡片两列，640px 以下单列，长编号/英文可换行。
- 侧栏保持品牌、新建、搜索、分组历史、重命名、归档及账号分支；顶栏允许窄屏换行，图标按钮有访问名称，移动点击区域 44px。
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
