# CygnusX Report Copilot P2 实施记录

日期：2026-10-27
状态：代码与隔离验证完成；真实报告/真实模型人工验收待完成；P3 未开始。

## 已实现

- `ReportViewerView` 增加按需展开的可调宽 Copilot 侧栏；快捷问题、流式回答、停止生成、章节引用跳转均接入现有 UI。
- `POST /reports/{report_id}/copilot/session` 为当前用户已完成的非交付报告创建普通 Chat 会话。后端清除默认项目身份，并将报告 ID 绑定到 `ChatSessionModel.sandbox_meta.report_copilot`。会话历史复用现有消息存储；前端按报告 ID 缓存会话 ID，重新打开时向服务端复核绑定。
- `POST /reports/{report_id}/copilot/stream` 每次核验报告所有权、会话所有权、活跃状态、报告绑定和服务端模型 ID。输入只保留 user/assistant 消息并限制消息数量和长度；关闭联网、MCP、代码执行及多 Agent 等通用能力，沿用平台 SSE 与 Chat 事件持久化。
- 被绑定的会话在 Chat 服务和 LangGraph 工具执行器中再次收窄为三项白名单只读工具：`read_report_section`、`list_artifacts`、`query_project_results`。工具参数不接收 project ID 或 task ID；数据作用域从当前已验证报告和其 owner 匹配的 Task 派生。
- 查询结果只允许读取该 Task 已登记的 CSV/TSV 文件，限制预览文件大小、top-N、筛选列及返回字段长度。无可验证项目关联时降级为报告 Task scope；没有真实 Task 时可查看报告，但结果表查询不可用。
- 报告章节引用通过预览副本中的双层 `postMessage` 桥滚动定位，校验来源窗口、报告 ID、短期 channel 和章节长度；不改变归档报告字节或摘要。
- 新增合成 SQLite 隔离测试覆盖工具白名单、报告/Task 归属、结果表读取与过滤、拒绝未知列、流请求绑定和普通能力关闭。

## 元数据边界（2026-10-27 更新）

本记录初版中的“尚未实现 ReportModel 元数据迁移/生成期写入/回填脚本”已由后续 schema 2.1 工作完成，不能再作为当前状态。当前注册流程将 `report.paths.json` 作为报告结构化元数据源，ReportModel 持久化 owner、项目、统计、富集摘要和文件索引；Copilot 优先校验并读取 schema 2.1 sidecar。2.0 报告通过 Task/文件索引兼容读取并标记 `legacy_degraded`。历史盘点/回填脚本已实现，但尚未对真实报告目录或数据库运行。字段契约、迁移、回填操作方式及验收边界见 [Report paths schema 2.1 实施记录](cygnusx-report-paths-schema-2.1.md) 与 [当前阶段交接文档](cygnusx-report-copilot-current-status.md)。

## 验证结果

- `uv run pytest tests/integration/test_report_copilot_isolated.py tests/integration/test_report_viewer_isolated.py tests/unit/test_report_preview_grant.py -q`：35 passed，1 个既有 Pydantic 弃用警告（2026-10-27 最新复跑）。
- `uv run ruff check`（本次变更的后端服务、路由、Chat runtime 和测试文件）：通过。
- `uv run mypy src/cygnusx/application/services/report_copilot_service.py src/cygnusx/api/v1/reports.py`：通过。
- `uv run python scripts/check_migrations.py`：迁移依赖、链连通性和唯一 head 检查通过；P2 未新增迁移。
- 在 `frontend/` 执行 `npm run type-check`：通过。
- 在 `frontend/` 执行目标 Vitest（`report-viewer.test.ts`、`reports-delivery.test.ts`）：2 files / 9 tests passed。

以上验证使用合成数据，未覆盖真实 LLM function-call 循环、三类真实工作流报告的分组/QC/差异基因一致性、生产 HTTPS/代理/S3，也不等于 P1/P2 人工验收。计划要求的三种真实报告抽查、top-20 产物对照、跨项目诱导、章节点击和刷新恢复仍需在可用环境手测并留证。P3 沙箱功能没有开始。
