# 报告 Copilot P1：平台内报告查看页

> 施工日期：2026-10-26–27。范围：10.25 原计划的 P1；用户指示“继续”后进入实现。
> 状态：代码与隔离自动验证已完成；真实报告人工验收待进行。P2/P3 未实现，不将 P1 当作完整目标完成。

## 实现与权限边界

- `frontend/src/views/ReportViewerView.vue`，路由 `/reports/:reportId/view`，复用 DefaultLayout。列表预览及旧 `?reportId=` 深链接进入同一查看页；过期/未完成报告拦截；ZIP 继续下载。提供标题、流程、状态、时间、收藏、下载、新窗口打开平台路由、加载/错误/404/重试，右下角保留 AI 解读占位。
- `src/cygnusx/api/v1/reports.py` 新增 `preview-url` 和 `preview-content`，复用原报告服务。签发接受活跃 JWT；HTML 请求需要 URL 签名 + HttpOnly 会话签名 + 登录上下文 nonce，实时重验用户/token_version/模块/报告权限。不存在公开静态目录或 access token URL。
- `core/report_preview.py` 的精确路由认证只用于 GET UUID preview-content，不影响其他路由。`utils/reportPreviewSession.ts` 的上下文在登录、退出、认证失效时同步清除；HttpOnly cookie 单独不能授权，两个报告标签页的短时签名可共存。
- `ReportService.preview_html(strict=True)` 为新查看页提供明确状态错误、有界读取、原 SHA 校验和拒绝软链替换的 FD 读取；原 `preview` 文本 API 保持兼容。
- `report_preview_renderer.py` 返回受 CSP 限制的外壳和嵌套原文 iframe。科学报告允许内联交互脚本，执行证据报告自身仍禁脚本；两者均为 opaque origin、禁请求/远程资源/表单/对象/顶层导航/弹窗。原报告字节不变。
- 查看页核对消息窗口、origin、report ID、随机通道，不能把 HTTP 错误页 onload 当成功；30 秒无有效消息后给重试/下载兜底。路由切换和退出后忽略迟到响应。

新增 Settings：`REPORT_PREVIEW_TTL_SECONDS=300`（30–900 秒，另受登录 JWT 有效期约束），
`REPORT_PREVIEW_MAX_BYTES=33554432`（1KiB–128MiB）。无需迁移，不改变镜像、Agent 配置或现有报告登记模型。

10.26 同名新稿的 REPORTS_ROOT / JSON 2.1.0 注册器不在本次 P1 中静默替换原有链路；
其 schema/身份兼容差异见 P0 调查 §9。P1 继续服务已登记报告，不删除或迁移未知来源记录。

## 验证证据

运行日志及截图位于 `evidence/report-copilot-p1/`，不提交运行证据。以下测试均未连接业务数据库，
未写业务存储，未启动或修改业务容器。

| 检查 | 结果/范围 |
|---|---|
| 新增凭证单测 + SQLite/ASGI 报告查看测试 | 27 项通过；覆盖签名/类型/到期/owner/ID/nonce，URL 单独持有、退出、用户禁用、版本撤销、模块禁用、删除/过期/文件丢失/空文件、超限、SHA、软链替换、执行证据脚本隔离，以及原列表/统计/收藏/已读/下载/删除 |
| 报告域扩大回归 | 72 项通过，命令见下方；包含旧执行证据生成/恢复/发布/下载与 RI04 交付包角色、完整性和 ZIP 验证 |
| 前端报告域 | 16 项通过；含窗口/随机通道校验、onload 不能自证成功、404/重试/下载、直达过期、超时、迟到响应、收藏、新窗口和同步退出 |
| 前端全量 | 100 文件、734 测试通过；日志含已有 jsdom ResizeObserver/navigation 警告，不把警告隐藏为额外成功证据 |
| 前端 type-check / build | 均通过；build 包含 vue-tsc -b 和现有 prebuild |
| 本次后端文件 Ruff / mypy | 通过；mypy 检查新安全模块、renderer、API、归档读取、报告服务、DTO、AuthMiddleware |
| 迁移链 | 唯一 head、依赖连通检查通过；本次没有新增迁移 |
| AgentTeams bridge | 190 passed、2 skipped；未改该子工程 |
| 实际 Chromium | Vue DefaultLayout + 真实隔离 API + 合成 HTML：页签切换成功；父页面访问被阻断；外部请求实际发出数 0；匿名复制 URL、篡改 report ID、清除登录上下文均 403；页面未捕获异常 0。记录 `browser-results.json` 与 `viewer-browser.png` |
| 全仓后端门禁 | 尚未全绿。首轮 Ruff 265 项、mypy 最终 1001 项/210 文件；错误位于本次受影响文件之外。首轮 unit/e2e 37 failed / 4153 passed / 22 skipped；修复报告域测试夹具环境串扰后的最终全量为 16 failed / 4174 passed / 22 skipped / 63 deselected |

报告域测试命令：

```bash
uv run pytest tests/unit/test_report_preview_grant.py \
  tests/integration/test_report_viewer_isolated.py \
  tests/integration/test_reproducible_report_isolated.py \
  tests/unit/test_report_service.py tests/unit/test_report_versions.py \
  tests/unit/test_report_delivery_phase2.py \
  tests/unit/test_report_pdf_and_bioreport_phase2.py \
  tests/unit/test_lifecycle_report_delivery.py -q
```

旧 Task 报告的两处测试夹具现在显式固定 `research_delivery_read_enabled=False`，与它们不创建
Dataset/user 表的隔离范围一致，避免继承本机 `.env` 的可选科研门禁。运行配置未改。
在修复夹具前，报告专项原样环境出现 8 项失败；显式默认配置下 49 项通过，定位了环境串扰。
增加 RI04、软链及空文件用例后的最终原样环境结果记录如下，不能用修改生产开关代替测试修复。

最终全量的 16 项未通过分布在 project_lifecycle、provider_retry_policy、report_snapshot、
reproducible_report_phase1、research_tool_pack_binding、studio_approval、studio_manager、
tools/tool_error_codes 和 langgraph_chat_sandbox_approval；没有新增预览用例失败。
其中报告快照/重试两项也是未解决的报告领域门禁，不能因预览专项通过而忽略。未把这些用例
隔离或修改运行功能来获得绿色结果，详细调用栈保留在 `backend-tests-final.log`。

## 人工验收与后续

尚待真实授权报告验证科学 HTML 的页签/图表、生成时间/下载内容、过期/丢失错态、浏览器退出后
底层 URL 拒绝，以及生产代理/HTTPS 的 cookie 与 CSP 行为。浏览器合成测试不能代替这些项目。
外部 CDN 或 eval 依赖不会被自动放行，真实报告如依赖它们应先核对自包含交付契约。

按原计划的逐阶段人工验收顺序，P1 手测通过后才进入 P2 元数据/报告会话/只读工具；
P3 项目挂载、常驻解释器、强制人类保存确认与执行计费仍保留完整目标，不视为已完成。
