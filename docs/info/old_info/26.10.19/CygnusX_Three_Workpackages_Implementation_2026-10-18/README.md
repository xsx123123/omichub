# CygnusX BioOps｜P0-A / IAT-R3 / G3-E2 实施与验收资料包

**编制日期**：2026-10-18  
**依据**：`CygnusX_Current_Implementation_Status_Audit_2026-10-18.md`（用户提供、2026-10-18 只读审计）、`cygnusx-iat-r2-runtime-evidence-closure.md`、`download-s4b0-reliability-hardening.md`、`download-s3-e1-trusted-execution-boundary.md`。  
**本包性质**：规划、工作包实施说明、Codex 执行提示词、验收标准。它本身不是运行证据；当前源码增量与隔离证据以各包的 `docs/implementation/` 报告及 `evidence/` 为准。

## 先读哪份文件

| 文件 | 用途 | 谁先执行 |
|---|---|---|
| `00_Overall_Roadmap.md` | 事实基线、三个工作包依赖、Go/No-Go、安全门禁、主线任务顺序 | 项目负责人 / 所有 Codex |
| `01_P0A_Implementation.md` | 持久审批、Task/Admission/预算绑定的详细技术设计 | 后端 Codex A |
| `01_P0A_Codex_Prompt.md` | 可直接复制的 P0-A 分阶段执行指令 | 后端 Codex A |
| `02_IATR3_Implementation.md` | 两 Runtime、Node、React/Vue、PG/Redis/Chromium 产品闭环 | 全栈 Codex B |
| `02_IATR3_Codex_Prompt.md` | 可直接复制的 IAT-R3 指令 | 全栈 Codex B |
| `03_G3E2_Implementation.md` | 独立 OS Supervisor、HTTP 出口、硬预算/配额、九项真实验收 | 安全/基础设施 Codex C |
| `03_G3E2_Codex_Prompt.md` | 可直接复制的 G3-E2 指令 | 安全/基础设施 Codex C |
| `04_Acceptance_Matrix.md` | 各工作包测试清单、门禁、交接与 DoD | 验收人员 |
| `05_Evidence_Template.md` | 每例原始证据记录模板与版本关联 | 验收人员 |
| `06_S4_Residual_Reliability.md` | S4 残余故障窗口的独立收尾计划 | 可靠性 Codex D（并行） |
| `07_Master_Codex_Prompt.md` | 三包协作、文件所有权、统一 Go/No-Go 的总控提示词 | 项目负责人 / Codex 总控 |

当前身份/迁移验收补充报告：`docs/implementation/cygnusx-p0a-g3-runtime-identity-acceptance.md`；其隔离命令摘要在 `evidence/p0a-g3-runtime-identity/isolated-verification.json`，当前工作树快照在 `evidence/p0a-g3-runtime-identity/current-baseline/`。该报告不提升真实 PG、Supervisor OS 或 G3 HTTP 的阻断状态。

## 当前工作树离线复核

以下结果来自当前 dirty 工作树，只证明代码契约或隔离测试，不改变本资料包定义的运行态门禁：

| 范围 | 当前结果 | 证据 |
|---|---|---|
| P0-A / Supervisor / trusted execution | `PASS_ISOLATED`；定向后端回归 127 项，Linux fail-closed 4 项 | `tests/unit/test_download_execution_admission.py`、`test_download_supervisor_authority.py`、`test_linux_scope_backend.py` |
| IAT-R3 后端与 Redis/研究链 | `PASS_ISOLATED`；定向回归 47 项 | `tests/unit/test_treasure_native_access.py`、`test_research_search_optimizer.py`、`test_redis_client.py` |
| S4 现有可靠性回归 | `PASS_ISOLATED`；76 项 | `tests/unit/test_download_s4a_reliability.py`、`test_lifecycle_download_security.py` |
| IAT-R3 前端 | 类型检查通过；Vitest 90 文件/611 项；production build 通过 | `evidence/iat-r3-runtime/commands.json` |
| G3 九项真实 HTTP | `BLOCKED`；集成入口显式 9 skipped | `tests/integration/test_download_trusted_http_boundary.py` |

真实 PostgreSQL、Redis、Worker、Node、Chromium、Linux cgroup/netns/quota 与受控 HTTP 端点仍未获得独立非生产授权；因此 `PASS_RUNTIME`、`PASS_E2E`、S6 和 S7 状态保持原定义，不以以上隔离结果替代。

## 绝对边界

1. **三个包分别运行、分别验收**：P0-A 的 PG 通过不等于 G3 OS 执行通过；IAT-R3 的页面通过不等于下载成功。
2. **不得自动开放** `DOWNLOAD_TRANSPORT_RUNTIME_ACCEPTED=False`、`WRITE_RUNTIME_ACCEPTED=False`、Agent 下载/分析写权限或 `worker_paths_verified=False`。通过验收以后还需要单独的逐环境、逐协议、逐调用方的准入评审；不得全局翻转代替认证。
3. 禁止访问/故障注入生产 PG/Redis/Broker/Worker、使用生产数据、擅自 `docker.sock` 暴露到任务 Worker、扩权运行普通下载子进程。
4. 未取得明确的非生产 OS/容器/网络/文件系统授权时：允许代码及隔离测试，**必须阻断真实执行和危险故障注入**。
5. 旧运行日志是历史证据，不能自动证明当前 `main`、dirty worktree、子模块已被重新验收。
6. 任何 `PASS_RUNTIME` 需真实 PG/Redis/进程/Worker；任何 `PASS_E2E` 需真实浏览器和业务断言；`0/9 skipped` 不算 G3 通过。

## 当前基线（来自审计，不代表此刻在线）

- 审计时主仓 `main`、HEAD `d648f54d24affd2bd3787332a49a5f4c96494cef`，多子仓及 React/Vue 前端存在 dirty；Codex 开始时必须重新记录状态。
- P0-A 已有 dirty `src/cygnusx/infrastructure/database/models/download_execution.py`、`repositories/download_execution_admission.py`、`alembic/versions/dwnadmission01_add_download_execution_admissions.py`，**先保护并检查，禁止重新创建平行模型**。
- IAT-R3 有确定性 Provider 两 Runtime 隔离轮次、React/Vue typed adapter 与 SSE 回放代码；真实部署、Node 完整聊天、科学页面 Chromium 工作流未通过。
- G3 有 mTLS supervisor 客户端、默认拒绝 Supervisor 服务骨架、Worker HTTP 生命周期 seam 和签名发布回执验证；尚无 Linux 强制后端，硬 RX/磁盘配额与九项真实 HTTP 仍未通过。
- S6 `NOT_READY`；S7 `NOT_YET_END_TO_END`。

## 建议执行顺序

先阅读 `00_Overall_Roadmap.md`，然后在**隔离的工作树/明确文件所有权**下并行 P0-A 与 IAT-R3；G3-E2 可以先做受信执行设施，待 P0-A 语义稳定后才能接生产业务 Task。S4 故障测试按 `06_S4_Residual_Reliability.md` 并行。

> 本文档包并未对用户仓库实施修改、执行数据库迁移、启动容器或开放真实下载；实施、测试与认证仍需 Codex 在授权环境逐步完成。
