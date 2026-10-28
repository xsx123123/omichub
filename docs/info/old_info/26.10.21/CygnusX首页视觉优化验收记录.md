# CygnusX 首页视觉优化验收记录

实施范围：原页面 P0～P2；P3 导航与信息架构调整未实施。无新增项目依赖，无路由、请求或任务执行逻辑改动。以下为自动化验证与代码核查结果，最终视觉验收仍由用户确认。

## 改动对照

| 提示词条目 | 文件 | 实现与证据 |
| --- | --- | --- |
| 1 标题断行 | `frontend/src/views/HomeView.vue` | 首个中文逗号后分行；`clamp(24px, 2.5vw, 38px)`、`text-wrap: balance`、`word-break: keep-all`；保留后台文案和窄屏兜底。1280/1440/2560px 实测均为两行。 |
| 2 首屏高度 | 同上 | `min-height: 380px`、桌面 `padding: 40px 32px`；压缩介绍、标签、按钮与愿景间距。1440×1440 视口实测 Hero 高约 427px，工作台标题 top≈655px。内容超出最小高度时自然展开。 |
| 3 玻璃卡对比度 | 同上 | 白色 10% 背景、18% 边框、16px 模糊，白色主文字/85% 白副文字；Hero 加局部压暗遮罩，减少透明度时回退实色。对 1280/1440/2560px 下各文字区域逐一采样，按 85% 白文字计算的对比度最低 5.15:1。 |
| 4 公告关闭记忆 | `HomeView.vue`、`components/AnnouncementBanner.vue` | 首页显式启用 `remember-dismissal`，localStorage key 包含公告 ID 与标题、描述、图标、链接、按钮的内容版本；关闭后跨刷新/跨日隐藏，内容或 ID 更新后重现。其他使用方保留 daily/forever/none。存储不可用仍可关闭当前横幅。Hero 与公告间距 16px。 |
| 5 工作台网格 | `components/home/ResearchWorkbenchPanel.vue` | 保留 `repeat(3, minmax(0, 1fr))`，删除“两列＋末列跨列”，视口 `<1280px` 改单列；长标题省略且带完整 title。1440px 三列均为 364px。 |
| 6 状态 badge | 同上 | 任务和报告共用 `NTag.status-badge`，24px 高、统一圆角/字重/内边距；运行蓝、完成绿、过期灰，排队黄、失败红，提供明暗主题色。保留所有原状态文案。 |
| 7 管理按钮 | `HomeView.vue` | 按钮与左缘装饰改用 `--brand-gradient`，hover 上移 1px。管理入口仍跳 `/admin/users`。 |
| 8 卡片层级 | `HomeView.vue`、`ResearchWorkbenchPanel.vue` | 工作台和快捷卡 hover 上移 2px；伪元素阴影 `0 8px 24px rgba(0,0,0,.35)`，200ms transform/opacity 过渡；技术支柱与生态卡静态。首页入场缩至 400ms，公告离场去掉高度、margin、padding 动画。减少动态时关闭位移/过渡与入场。 |
| 9 积分胶囊 | `components/CookieBalanceBadge.vue`、`layouts/DefaultLayout.vue` | tag `padding: 4px 12px`、不收缩、tabular-nums；胶囊明确叠层，顶栏右侧 gap=12px。实测 `26732.3` 完整显示，scrollWidth=clientWidth=85px，与相邻控件间距 12px。 |
| 10 历史运行任务核查 | 只读 DB 查询与代码，见下 | 当前 38 条 running 全部为演示种子数据，并非真实执行中，也没有证据表明这些记录来自状态回写丢失。未修改任务数据。 |

计划中额外要求的三个“全部”已核实分别为 `/projects`、`/tasks`、`/reports`，无需修正。

## 浏览器与交互验证

证据目录：`evidence/home-visual-20261021/`（本地运行证据，不纳入提交）。使用真实 Vue 首页、DefaultLayout、Naive UI 和路由，API 响应由浏览器测试拦截提供固定样本；这些结论不替代后端业务 E2E 或用户人工验收。

- `browser-verified.json`：1280/1440/2560px 三列等宽、标题两行且页面无横向溢出；1279/1024/390px 单列且无横向溢出；1280/1440px 长报告名实际省略。
- `home-1280.png` / `home-1440.png` / `home-2560.png`：对应截图；另有移动端与断点截图。
- 关闭公告并刷新、更新内容后刷新：分别隐藏、重新出现。
- 刷新工作台会重新请求 running/queued 任务；项目/任务/报告原有请求保留。
- 主按钮、AI 按钮、六张快捷卡、管理按钮的点击目标全部与原实现一致；浏览器守卫捕获目标并取消导航，以免触发无关模块的实际业务操作。
- 工作台/快捷卡普通偏好 hover 上移 2px；减少动态时无位移；技术支柱/生态卡两种偏好均不位移。
- 浏览器无 pageerror。
- 补充主题切换核验：运行/完成/过期三类 badge 的文字对比度在深色模式最低 6.88:1、浅色模式最低 5.38:1，均超过 4.5:1；原始计算见 `badge-contrast.json`。

## 第 10 条核查结论

**演示种子数据遗留，非真实任务持续运行。**

对当前部署的 `cygnusx-db` 执行只读事务查询：38 条 `status='running'` 记录全部同时满足 `idempotency_key LIKE 'seed-demo-%'`、`parameters.seed='demo-v1'`、`work_dir=''`、`finished_at IS NULL`。最新一条 `66356324-1ee9-42e9-8061-f89fdafdc2c5`，名称「RNA-seq 差异表达 - 运行中 #36」，创建时间转上海时区为 2026-10-03 00:01:26。

`scripts/seed_demo_data.py` 的 `_make_task()` 及“1a. 运行中任务”分支，直接构造上述种子标记和 `status='running'` 写库；没有向执行器投递任务。`TaskService.list_tasks()` 从数据库查询并返回状态，首页也只展示返回值。实际 Snakemake 执行路径在 `infrastructure/celery_app/tasks/analysis.py` 根据执行结果转换 SUCCESS/FAILED 并提交事务，种子记录不经过该路径，因此不会自动收敛成终态。该证据足以解释本次截图中的长期 running；不据此断言其他真实任务不存在状态同步问题。

原始查询与输出见 `task-state-query.sql`、`task-state-query.txt`。本轮按“只查不改”要求保留数据与后端逻辑。

## 验证命令与门禁

| 检查 | 结果 |
| --- | --- |
| `cd frontend && npm run type-check` | 通过 |
| `cd frontend && npm test` | 92 个文件、619 项测试通过（包含 4 项新增公告回归测试）；现有 jsdom 警告见日志 |
| `cd frontend && npm run build` | 通过，包含 prebuild 和 `vue-tsc -b` |
| `uv run python scripts/check_migrations.py` | 通过，单一 head |
| `cd integrations/agentteams/bridge && uv run pytest -q` | 190 passed，2 skipped |
| `uv run ruff check src/ tests/` | 失败：274 项现有后端/测试问题；本轮未修改任何 Python 文件 |
| `uv run mypy src/cygnusx/` | 失败：216 个文件共 1028 项错误；本轮未修改任何 Python 文件 |
| `uv run pytest tests/unit tests/e2e -q -m 'not quarantine'` | 3963 passed，15 failed，22 skipped，63 deselected；失败集中于现有 Agent/Provider/Studio/Tool 后端用例 |

完整输出保存在证据目录 `cygnusx-home-*.log`。全量后端门禁存在上述失败，不能将本次前端验证描述为仓库全量门禁通过。用户在知悉该限制后明确要求提交，本轮仅按逻辑拆分提交首页及品牌图标相关改动，保留无关工作区改动，不推送远端。


## 后续交付

以上尺寸与样式对照表为初轮 P0～P2 验收快照。后续字号、Hero 生命周期卡片放大及「AI 规划研究方案」按钮文案见 [字号可读性优化记录](CygnusX首页字号可读性优化记录.md)；当前实现以 `ARCHITECTURE_DESIGN/CygnusX_frontend.md` 和代码为准。

浏览器 favicon、顶栏与手机侧栏品牌图标已统一使用 `frontend/public/cygnusx-logo.png`，保留用户原图像素及透明通道。最新前端类型检查、619 项测试与构建均通过；实际页面与资源加载验证见 `evidence/brand-logo-20261021/`。

首页三列同时加载失败的日志权限故障已恢复，真实项目/任务/报告接口及刷新行为验证通过，详见 [加载失败排查记录](CygnusX首页工作台加载失败排查记录.md)。本地运行证据、截图、用户上传的 docs 图片及其他未关联改动不纳入本轮提交。
