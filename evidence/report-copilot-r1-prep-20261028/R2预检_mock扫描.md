# R2 预检：生产源码 mock 引用扫描（验收项 4 局部）

> 日期：2026-10-28 · 只测不改，仅记录与分级
> 范围：R2 验收项 4「生产源码 mock 引用为零」中可在无真实环境下执行的部分。
> 报告中心（Reports/Copilot 链路）mock = **零**；另发现 2 处报告域外 mock 痕迹，按严重度分级记录。

## 扫描命令与输出

```bash
# ① P2.5 施工记录同款三标识符（frontend/src）
cd frontend && grep -rnE 'mockData|mockReports|mockStats' src/
# 输出：无匹配（exit=1）→ 报告中心生产源码 mock 引用为零 ✅

# ② 报告域后端生产文件通用 mock 扫描
grep -rniE 'mock' src/cygnusx/api/v1/reports.py \
  src/cygnusx/application/services/report_service.py \
  src/cygnusx/application/services/report_copilot_service.py \
  src/cygnusx/application/services/report_paths_registry.py \
  src/cygnusx/application/services/report_paths_contract.py
# 输出：无匹配 → 后端报告域零 mock ✅

# ③ 报告相关前端文件通用 mock 扫描（大小写不敏感）
cd frontend && grep -rnilE 'mock' src/views/ReportsView.vue src/views/ReportViewerView.vue \
  src/api/reports*.ts src/components/report/
# 输出：仅 src/components/report/__tests__/ 三个测试文件（测试用途，允许）✅

# ④ 全前端生产源码通用 mock 扫描（排除测试）
cd frontend && grep -rlni 'mock' src/ --include='*.ts' --include='*.vue' | grep -vE '__tests__|\.test\.'
```

## 报告域外发现（非报告中心范围，记录备查，未修改）

| 严重度 | 位置 | 事实 |
|---|---|---|
| 低（死文件） | `frontend/src/mock/referenceGenomes.ts` | 存在但**全仓零引用**（`grep "from '@/mock"` 无匹配），属参考基因组功能的历史残留；会让「存在 src/mock 目录」的字面检查误报，R2 正式验收时建议说明或清理 |
| 低（设计内） | `frontend/src/utils/geneIdMapData.ts` + `geneIdMap.ts` | IdConverter 工具的**内置 mock 映射数据**（`MOCK_SPECIES_DATA` / `buildMockEntries`），是基因 ID 转换功能的当前数据源，与报告中心无关；注释已声明"内置 mock 数据" |

## 结论

R2 验收项 4 的「生产源码 mock 引用为零」（报告中心范围）在代码层面**通过**：
报告中心列表/查看页/Copilot 的前后端生产源码无任何 mock 数据引用。
R2 正式验收时此项可直接引用本记录与命令输出；两项域外发现按上表分级处理。
