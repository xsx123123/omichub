# 报告中心 AI 联动 v2 计划 — 现状差距分析与实施基线

日期：2026-10-28
依据：`docs/info/26.10.28/报告中心AI联动与交付测试_综合实现计划_v2.md`（下称"v2 计划"）
分支：`feat/report-center-ai-linkage`

## 探索阶段结果（v2 计划第 0 节）

1. 样本目录 `/data/omichub/Flow_report/X101SC26098749-Z01-J001/`（152MB）：
   `data/`（fastq_screen_report、QualiMap、fastp_trim_report、index、res/DEG、res/Enrichments）、
   `delivery_manifest.json/.md5`、`project_summary.json`（7.4M）、`report.paths.json`、
   报告 HTML（**85.9MB**）+ 中英 PDF。
2. `report.paths.json`：schema_version 2.0.0，`path_base: "."`（相对 run 根目录）；
   `input_files`/`enrichment.go|kegg.contrasts.*` 中均为相对路径；`project`/`software_versions`/`report` 元数据齐全。
3. `delivery_manifest.json`：`{meta, files}` 结构；`files` 为 文件名 → **构建机绝对路径** 映射
   （`/data/jzhang/project/Temp/.../report_data/...`），验证时需把绝对路径折算回 run 根目录相对路径。
4. `project_summary.json`：顶层键 `schema_version/path_base/project_meta/stats/input_files/enrichment`；
   enrichment 内含 go/kegg 两个分区，每分区含 parameters 与 contrasts（每 contrast 含 UP/DOWN，带 term_count 与 terms 明细）。
5. 前端技术栈：**Vue 3 + TS(strict) + naive-ui + Pinia**（非 v2 计划假设的 React）；后端 FastAPI。
   已有 AI 会话组件：`frontend/src/components/report/ReportCopilotPanel.vue`（SSE 流式，复用 `useAgentChatStream`）。
6. 报告 HTML 结构（F4 前提）：85MB 自包含文件是**外壳加载器**——内嵌 gzip+base64 的 zh/en 两个版本，
   运行时经 `DecompressionStream` 解压后写入嵌套 `srcdoc` iframe；超过预览上限
   （`report_preview_max_bytes` = 32MB），在线预览按 REPORT_TOO_LARGE 降级为下载（与 F6 一致）。
   外壳本身不含 h1-h3 章节标签；章节提取针对平台内渲染的报告正文（interactive 预览）实施。

## 与平台现状的差距（关键）

平台已有 P1（报告查看）/P2（Copilot）实现，详见 `docs/implementation/cygnusx-report-copilot-current-status.md`。
v2 计划大部分"新功能"已存在等价物，**不重复造轮子**：

| v2 计划项 | 平台现状 | 差距/决策 |
|---|---|---|
| T1 受控端点 | `GET /api/v1/reports/{id}/preview-url`（签名 grant + HttpOnly session cookie + 模块门禁）+ `preview-content`（grant 校验 + owner 校验 + REPORT_TOO_LARGE + no-follow FD 读 + sha256 校验）；文件下载 `/{id}/files/{file_id}/download` 按登记文件授权 | **已满足且更强**。不新增 `/api/reports/{id}/file/{relpath}` 裸路径端点（避免引入新的路径面；既有 file_id 授权模型更安全） |
| T5 消毒层 | 无内容消毒；采用**隔离模型**：`render_preview` 外层 CSP `sandbox allow-scripts; default-src 'none'; connect-src 'none'…` + srcdoc 嵌套 iframe（无 allow-same-origin，opaque origin）+ sha256 完整性校验 | **路线偏离**：以隔离代替内容重写。nh3/bleach 白名单会误杀 Plotly 内联脚本（85MB 自包含报告全靠内联脚本），CSP 已断网、断同源、断表单，达成 v2 计划的防 XSS/防同源目标。E-13 消毒测试改写为"隔离有效性"测试（脚本无法出网/无法触 parent） |
| T2 iframe 预览 | 已实现：签名 URL + CSP 外层 + srcdoc 内层 + 30s 加载超时降级 + REPORT_TOO_LARGE 降级 + 骨架 loading | 已满足；本计划补划选桥接 |
| T3 划选捕获 | **不存在**。现有 postMessage 仅支持 AI→报告 章节滚动（`cygnusx:report-section`） | **本次新增**：报告→平台 的 `cygnusx:report-selection` 通道 + 悬浮"问 AI"按钮 + F8 模板填充 + 2000 字符截断 + 章节提取 |
| T4 AI 抽屉 | `ReportCopilotPanel` 已实现：会话绑定 report_id、SSE 流式、章节引用跳转、按报告恢复会话、切报告重建会话（watch reportId → initialize） | 补充：上下文预填入口、常驻免责页脚、首发前一次性提示 |
| T6 加载态/大文件 | 骨架屏、30s 超时、REPORT_TOO_LARGE 均已实现（阈值 32MB 而非 10MB，配置项可调） | 已满足 |
| 测试 A–D/F | 不存在 | **本次新增** `tests/test_flow_report.py`（离线产物审计，pytest） |
| 测试 E | `tests/unit/test_report_preview_grant.py` + `tests/integration/test_report_viewer_isolated.py` 覆盖端点安全 | 补 E-14 上下文模板测试；E-15 Playwright E2E 按 v2 计划 SKIP（环境无 Playwright） |

## 安全模型说明（对 v2 计划 F3/F5/F7 的映射）

- 同源隔离：既有实现用 CSP sandbox + srcdoc opaque origin 达成"禁止同源"，比 Blob URL 更强（外加签名 grant 与 sha256 校验）。
- 路径穿越：不开放 relpath 端点，所有文件经 ReportModel 登记的 file_id 授权 + no-follow FD + 大小上限；既有集成测试覆盖 `../` 拒绝。
- 划选桥接安全：bridge 脚本由后端 `render_preview` 注入（内容可控），消息带 reportId+channel 校验，父页校验 `event.source`/类型/长度；选中文本在注入侧截断，前端二次截断。

## 本次实施清单

1. `report_preview_renderer.py`：interactive 报告的 inner bridge 增加 mouseup/keyup 划选捕获与章节提取（h1-h4/[role=heading]/.section-title/[data-section]/caption/th → "未命名区域"），外层桥转发到平台页。
2. `ReportViewerView.vue`：接收 selection 消息 → 选区右下悬浮"问 AI"按钮（防溢出）→ 点击打开 Copilot 并按 F8 模板填充（>2000 字符截断并告警）。
3. `ReportCopilotPanel.vue`：支持预填草稿、常驻免责页脚、首次发送前一次性提示（localStorage 记忆"不再提示"）。
4. 前端 vitest 单测 + 后端 renderer 单测。
5. `tests/test_flow_report.py`：交付物审计 A–D + F 自证（离线、只读源文件、产物写 /tmp/flow_report_test/）。
