# Codex 一体化提示词｜CygnusX 当前完成度盘点

你是 CygnusX BioOps 项目的首席架构审计工程师。**本轮执行模式为 AUDIT-ONLY。**

请先完整阅读我提供的 `CygnusX-Current-Stage-Completion-Audit-2026-10-18.md`，并严格按其中 S0～S5、RC04-00～06、P01～P15 的范围，对**当前本地仓库**做一次基于证据的完成度盘点。

**本次不是继续开发，不是重新写实施计划，也不是把历史 PASS 复制为当前 PASS。** 你必须实际检查当前 Git HEAD / dirty worktree、源文件、路由、服务、任务注册、测试脚本、最新验收报告、evidence 目录与 SHA 索引。在没有授权的新运行环境下，禁止启动容器、迁移数据库、修改业务代码/配置、修改生产门禁或运行故障注入。

重点回答两条主线：

1. **RI09.5-RC04** 目前完成了哪些：D1–D4 固化、持久化门禁归零、源码/镜像冻结、浏览器 31/34 与 fresh/existing-ready、RA02 12/11 差异、FI01–06、HTML/PDF/V2 ZIP/JWT、seccomp、历史旧库/冻结 corpus/S3 等。
2. **CygnusX 整个平台** 目前完成了哪些：基础服务与项目/证据模型、Agent、寻宝鼠、GEO/SRA/ENA 下载、Polariseq、FlowFrame/FlowAgent、标准分析/高级分析、BioReport、科研项目交付、平台 UI、部署与安全、真实科研流程复现。外部仓库不可见就明确标 `NOT_ACCESSIBLE`，不可猜测已集成。

每项均分开标注：**实现、集成、验证、证据**四个维度，并提供可核实的文件路径、符号、运行 Run ID、Commit/镜像摘要、缺口与下一步。没有当前证据只能标 `PASS_HISTORICAL` / `IMPLEMENTED_UNVERIFIED` / `PARTIAL` / `BLOCKED` 等恰当状态。尤其不得将 RI09.5 项目摘要 PDF 的成功视为真实 RNAFlow 全链路科研复现通过。

**唯一允许的写操作是创建新的审计文档**，不得修改现有源代码、测试、门禁或证据。最终生成：

- `CygnusX-Current-Stage-Completion-Report.md`
- `CygnusX-Feature-Evidence-Matrix.csv`
- `RI095-RC04-Completion-Gate-Matrix.md`
- `CygnusX-Next-Action-Backlog.md`

将这 4 份文件放入仓库现有审计文档惯例目录（如 `docs/audits/`）。请直接执行只读取证和审计报告生成，而非反复向我询问是否开始。只有涉及外部授权或不可访问资料时，明确列出 Input Request 和对应 BLOCKED。

最后简洁回答：**目前真正完成的是什么？RC04 真实做到哪一步？距 RC04-Core / RC04-Full / 正式生产 / 真实科研可复现案例各差什么？下一步哪 5～10 件事最值得做？**
