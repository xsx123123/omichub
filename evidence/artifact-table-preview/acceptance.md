# 分析产物表格预览验收

实现范围：消息级 `MessageArtifactGallery` 和 `StudioArtifactsPanel`，CSV/TSV/XLSX/XLS。下载、图片/PDF、TXT/Markdown 原有逻辑保留。

## 浏览器证据

`browser-results.json` 为 Playwright 实际检查结果。真实文件包括 GSE280781_sample_manifest.tsv（17 列、20 行数据）、tomato_enrichment_result.csv、ScTypeDB_full.xlsx。多工作表 XLSX/XLS 从真实 manifest 构造；125 行与超长平台字段为基于真实记录的边界样本。

- 表头/内容列宽一致；横向和纵向滚动后表头位置不变。
- 125 行样本只保留 100 行，底部显示总行数与截断提示。
- 长平台字段在 hover 后显示全文；暗色表格文字与背景可读。
- XLSX/XLS 默认第一张表，所有 sheet 可切换；Studio 共用同一预览组件。
- 空 CSV 显示占位；损坏 Excel 回退纯文本。
- 已知大小超过 5 MiB：用户确认前无文件请求。
- 清单无大小：流式请求检查响应头后停止，确认后重拉；无 Content-Length 的超限流取消由传输单测覆盖。
- 下载后的文件名与原文件一致，字节内容完全相同。
- 明暗桌面、390px 移动端截图见本目录 PNG。

运行命令（ARTIFACT_TSV 指向本地真实样本）：

```bash
ARTIFACT_TSV=/path/to/GSE280781_sample_manifest.tsv \
PLAYWRIGHT_MODULE=/path/to/playwright/index.mjs \
CHROMIUM_PATH=/path/to/chrome node scripts/poc/artifact-table-browser.mjs
```

## 自动检查

- TypeScript 类型检查通过；前端全量 102 文件、753 测试通过。
- 生产构建输出至 `/tmp/omichub-artifact-table-dist`，未覆盖现有部署。
- 迁移链检查通过；bridge：190 passed、2 skipped。
- 当前工作区后端门禁未全绿：Ruff 265 项；mypy 988 项；单元/E2E 21 failed、4211 passed、22 skipped、63 deselected。详见同目录日志。本次未修改 Python 文件。
- 用户获知现有后端门禁失败后明确指示 commit；已分别提交表格预览（315b7a65）和 Logo 替换（45030a94）。原有暂存内容及工作区改动保持原样，范围校验见 commit-receipt.json。

## 提交前复验

2026-10-28：TypeScript 检查通过；当前前端全量 102 文件、758 测试通过，日志见 frontend-tests-precommit.log。两项提交未再修改代码，仅改变 Git 记录。
