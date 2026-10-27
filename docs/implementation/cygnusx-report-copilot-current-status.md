# 报告查看与 Copilot 当前阶段交接

日期：2026-10-27
目的：记录目前已完成的 P1/P2 与报告元数据工作，以及下一轮人工验收、存量回填和 P3 推进入口。本文是当前执行状态的交接摘要；细节以链接的专项实施记录和代码为准。

## 当前状态

| 工作包 | 状态 | 说明 |
|---|---|---|
| P0 代码调查 | 已完成代码级调查 | 结论和限制见 P1/P2 实施记录；生产报告目录及真实部署环境尚未验收。 |
| P1 报告查看 | 代码与隔离验证完成 | 平台内查看、预览凭证、授权校验、错误状态及 iframe 隔离已有实现；真实报告和生产 HTTPS/代理验收待做。 |
| P2 Copilot | 代码与隔离验证完成 | 绑定报告的会话、三个只读工具、章节引用跳转和按报告恢复会话已实现；真实报告和真实模型验收待做。 |
| `report.paths.json` 2.1 | 注册链路和迁移已实现 | 新流程产出 2.0 兼容 sidecar，由平台注册时结合 Report/Task/owner 校验并升级到 2.1；旧 2.0 以降级状态兼容。 |
| mock 报告源 | 前端生产引用已移除 | 删除 `mockData.ts`；扫描 `frontend/src` 未发现 `mockData`、`mockReports`、`mockStats` 的生产引用。 |
| 存量报告回填 | 脚本已实现，未运行 | 需要真实报告根目录和目标数据库；脚本默认审计，不带 `--apply` 不写库。 |
| P3 沙箱高级分析 | 未开始 | 仍需单独核实现有沙箱能力，再按隔离、授权、确认、计费及产物注册要求实施。 |

## 已完成的实现

### 报告注册与元数据

- 新增 Alembic revision `reportpaths01`，扩展 ReportModel：报告 schema/sidecar 路径、项目和 owner 关联、client/species/genome/pipeline/analysis date、统计、enrichment 摘要、文件索引和元数据错误摘要。现有必填 `ReportModel.user_id` 继续作为报告 owner；项目 owner 单独保存并交叉校验。
- 新增 sidecar 契约解析器，接受 schema 2.0.0/2.1.0。2.1 校验 project owner、platform 与 Report/Task 绑定、文件角色/说明/格式和规范相对路径。
- 报告完成注册时写入或校验 sidecar，并持久化可供 Copilot 使用的摘要与文件索引；解析失败时报告转为 failed，并写入有界错误摘要。
- RNAFlow、ATACFlow 报告步骤现在产出 2.0 兼容 sidecar；平台注册器再将它绑定当前 report/task/owner 并升级为 2.1。此设计使流程输出保持对旧消费者兼容。
- 回填工具 `scripts/backfill_report_paths_registry.py` 只扫描显式提供的报告根目录，不跟随符号链接；输出 success/failed/manual 三份清单。它不会在请求时遍历目录。

### Copilot 与安全范围

- Copilot 元数据快照优先从已校验的 schema 2.1 读取；legacy 2.0 使用持久化 Task/文件索引兼容路径，并显示 `legacy_degraded`。
- 三个只读工具仍为 `read_report_section`、`list_artifacts`、`query_project_results`。结果查询按文件 `role` 选择登记的 CSV/TSV，并带回文件 description；产物清单来自索引。
- 文件访问拒绝绝对路径、`..`、非规范路径和符号链接替换；使用 pinned no-follow FD 读取并限制文件/响应大小。报告 owner、项目 owner、Task 绑定会在服务端校验。
- 本次没有重做 P1 的 preview grant/HTML 隔离，也没有重做 P2 的三工具白名单或 `postMessage` 章节锚点通道。

### 报告中心

- 移除了 `frontend/src/components/report/mockData.ts`。
- 报告页面已有后端 API/注册表数据读取；删除 mock 文件后扫描生产源码无上述 mock 符号引用。建议接入真实环境后再确认列表数量、收藏/过滤和权限表现。

## 提交与文件入口

- OmicHub：`d28e643b feat(reports): index BioReport paths metadata`
- RNAFlow 子模块：`951f4f2 feat(report): emit BioReport paths sidecar`
- ATACFlow 子模块：`e4e2805 feat(report): emit BioReport paths sidecar`
- P1 记录：[cygnusx-report-viewer-p1.md](cygnusx-report-viewer-p1.md)
- P2 记录：[cygnusx-report-copilot-p2.md](cygnusx-report-copilot-p2.md)
- Schema/注册/回填记录：[cygnusx-report-paths-schema-2.1.md](cygnusx-report-paths-schema-2.1.md)
- 代码计划：[CygnusX 报告查看与 AI 解读 Copilot 实现计划](../info/26.10.27/CygnusX报告查看与AI解读Copilot实现计划.md)

## 已执行的验证

- 后端隔离回归：

  ```bash
  uv run pytest tests/integration/test_report_copilot_isolated.py \
    tests/integration/test_report_viewer_isolated.py \
    tests/unit/test_report_preview_grant.py -q
  ```

  结果：35 passed，1 个既有 Pydantic 弃用警告。
- 变更 Python 模块与回填脚本 Ruff：通过。
- 变更 Python 模块与回填脚本 mypy：7 source files 无错误。
- `uv run python scripts/check_migrations.py`：迁移依赖、链拓扑和唯一 head 检查通过。
- 前端 `npm run type-check` 及目标报告 Vitest：通过；2 个文件、9 项测试。
- RNAFlow/ATACFlow helper 的 `py_compile` 与 Ruff：通过。Snakemake dry-run 因当前机器缺少配置引用的参考基因组文件而中止，不能算完整工作流验证。
- 未执行真实数据库迁移、真实报告根目录扫描/回填、真实模型工具循环或生产浏览器验收。

## 建议的下一步推进顺序

### 1. 在可用环境完成迁移预演

先备份目标数据库，并在与目标版本一致的测试库执行：

```bash
make check-migrations
make migrate
```

确认迁移后新旧报告行、owner 字段、JSON 列和唯一 head。当前仅通过静态迁移检查，未在真实 PostgreSQL 上执行迁移。

### 2. 先审计存量报告，再人工处理异常

准备准确的报告根目录和只读数据库连接，先运行审计模式：

```bash
uv run python scripts/backfill_report_paths_registry.py \
  --reports-root /absolute/path/to/reports \
  --database-url 'postgresql+asyncpg://USER:PASSWORD@HOST:PORT/DB' \
  --output /absolute/path/to/report-paths-audit
```

检查生成的 `success.json`、`failed.json`、`manual.json`：确认报告 ID、owner、Task 匹配和文件路径；对 manual/failed 项先定位原因，不要将不确定的归属自动写入。审计范围、数据库连接和结果都应留存到验收证据。

审计清单确认后，再对目标环境显式执行带 `--apply` 的回填。该脚本会写数据库，应在维护窗口、备份和回滚策略就绪后执行；不要将审计输出路径与报告根目录混用。

### 3. 抽查真实报告并完成 P1/P2 人工验收

至少抽查 RNA-seq、ATAC-seq 及另一类可用流程各一份：

- 比对报告 HTML 中项目、样本、分组、QC、富集和差异结果与 2.1 sidecar/数据库快照。
- 检查文件索引中的 `role`、description、format、路径与真实 TSV/CSV 内容对应。
- Copilot 对样本数/分组、QC 和 top 结果的回答必须能与报告/文件逐项核对；测试跨项目诱导、越权 owner、`../` 路径拒绝及旧 2.0 的降级提示。
- 检查章节锚点、刷新恢复会话、真实代理/HTTPS 下 preview 凭证、退出登录和报告过期状态。
- 留存报告 ID、操作步骤、结果截图或日志，以及不通过项；不要用合成 SQLite 用例代替人工验收。

### 4. 再进入 P3 设计与实现

P3 尚未开始。开工前先针对现有沙箱确认只读报告挂载、默认网络策略、CPU/内存/时长/输出限制、会话隔离与销毁、审批确认、积分预扣/实结、产物回注册契约。缺任一项时先补齐并测试强制边界，再注册执行工具；执行结果默认留在会话工作区，正式写回项目产物须显式人类确认。

## 尚未证明的事项

- `report.paths.json` 2.1 在实际生产工作流端到端生成/升级并正确反映各流程字段。
- migration 在真实 PostgreSQL 版本及现存报告数据上的运行时间、锁影响和回滚方式。
- 回填脚本面对真实存量目录的成功/失败/manual 分布及 owner/Task 关联准确性。
- 真实 LLM function-call 工具循环是否按 role 查到正确结果、回答是否可复核。
- 真实 HTTPS/反向代理/CDN 配置下报告预览和 iframe CSP 行为。
- P3 沙箱高级分析能力、安全边界及计费闭环。
