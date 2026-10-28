# 05｜CygnusX 工作包验收证据模板

> 复制本模板为每一项 `evidence/<stage>/<test_id>/record.md`。任何无法观察的字段写 `NOT_OBSERVED`，不得编造默认值。日志、截图、数据库查询和哈希原文件须同时保留。

## A. 唯一上下文

- Work Package：`P0-A / IAT-R3 / G3-E2 / S4`
- Test ID：
- Test Name：
- Tester / Reviewer：
- Run ID / Environment ID：
- 所属已授权测试主机、端口、资源及清理范围：
- 授权依据文档路径（脱敏）：
- 运行开始/结束（含时区）：
- 主仓 HEAD/branch：
- 当前 dirty tracked diff 哈希：
- untracked 文件清单 digest：
- 所有相关子仓 HEAD、dirty 与 nested SHA：
- API/Worker/Node/React/Image SHA256：
- CLI binary digest、Supervisor policy digest、DB/Redis/Broker/Chromium 版本：

## B. 此次验证的真正断言

- 原需求原文：
- 本例覆盖的具体业务子场景：
- 不能从本例得出的结论（例如 PG pass != OS verified）：
- 输入数据来源、GEO metadata 快照/哈希/日期：
- user_id（脱敏）/project_id/session_id/ingestion_id：
- approval_id、task_id、admission_id、attempt_id、epoch、scope_id：
- 预期允许/拒绝码：
- 网络与文件预算单位及阈值：

## C. 实际操作、原始证据

```text
# 命令原文（敏感环境值脱敏，保持真实参数/路径语义）：

# 退出码：

# stdout log path / SHA256：
# stderr log path / SHA256：
# Container/Worker/Node logs path / SHA256：
# SQL read-only query + result path / SHA256：
# Redis TTL/nonce state record path / SHA256：
# HTTP HAR/trace / browser screenshot / console path / SHA256：
# OS cgroup/task scope/process tree/counter/quota path / SHA256：
# FileRegistry database row + local sha256sum path / SHA256：
```

## D. 原因—结果对账

| 时点/事件 | 源系统 | Observed | Evidence file | 不可变断言是否满足 |
|---|---|---|---|---|
| 请求/授权 | Human/JWT/Proposal | | | |
| Task/Admission/预算事务 | PostgreSQL | | | |
| 消息发布/消费 | Broker/Worker | | | |
| OS 启动/停止 | Supervisor | | | |
| RX/quota | OS Data Plane | | | |
| 产物/登记 | FileRegistry/Dataset | | | |
| 页面与会话 | Node/React/SSE | | | |

## E. 结果判定

- `PASS_STATIC / PASS_ISOLATED / PASS_RUNTIME / PASS_E2E / FAIL / BLOCKED / NOT_TESTED / STALE_EVIDENCE`：
- 完整或部分覆盖：
- 若 BLOCKED：资源/权限/代码依赖；是否已记录 STOP：
- 若 FAIL：失败重现命令、实际错误/原因、负责模块和回滚：
- 默认安全门禁仍关闭的证据：
- 是否产生生产副作用（**应为否**）：
- 测试清理是否需人工审批：
- 后续复验条件：
- 独立复核人及日期：

## F. 多项合并报告注意

- 同一日志证明多个子断言时，按 Test ID 引用，同一测量不得多次计算为独立运行。
- 同一文件集的 `pytest 9 skipped`、`0 executed` 不计通过。
- 只读报告不等于在当前环境执行，历史证据必须标 `HISTORICAL` 与源 SHA。
- 若测试期间 dirty/镜像 SHA 变化，必须撤销当前版本的 PASS 并标 `STALE_EVIDENCE`。
