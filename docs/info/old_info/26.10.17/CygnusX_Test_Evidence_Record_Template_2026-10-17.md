# CygnusX BioOps｜单项验收证据记录模板

> 复制本模板到 `<EVIDENCE_ROOT>/<ENVIRONMENT_ID>/<TEST_ID>/result.md`，不要覆盖其他运行的记录。本文是空白记录，不代表通过。

## A. 审批与环境

| 字段 | 填写 |
|---|---|
| Test ID | `待填：ENV-01 / PG-01 / MQ-01 / AG-01 ...` |
| 测试名称 | 待填 |
| 责任人 | 待填 |
| ENVIRONMENT_ID | 待填 |
| 授权单/范围 | 待填：仅引用脱敏编号 |
| 机器/容器 | 待填：非生产标识 |
| 开始 UTC | 待填 |
| 结束 UTC | 待填 |
| 主仓 commit | 待填 |
| dirty worktree fingerprint | 待填 |
| FlowFrame / Treasure-Seeking_Mouse commit | 待填 |
| 镜像 digest / 服务版本 | 待填 |
| 测试 DB / Broker / Redis 身份 | 待填：脱敏；不得填写密码 |

## B. 前置条件与安全门禁

- [ ] 目标明确为获授权独立非生产资源。
- [ ] 没有连接生产数据库/队列、没有生产存储挂载。
- [ ] 操作所需端口、额度、故障注入范围已批准。
- [ ] 核对 `DOWNLOAD_TRANSPORT_RUNTIME_ACCEPTED=False` 和 `WRITE_RUNTIME_ACCEPTED=False` 的实际运行语义。
- [ ] 不会执行未经认证的真实文件下载。
- [ ] 工作树、镜像、Worker 队列和测试服务版本一致。
- [ ] 已评估和限制日志/截图/HAR 中的个人信息与秘密。

若任一 P0 前提不满足，停止，状态填写 `BLOCKED`。

## C. 测试操作与期望

**输入测试数据 / 用户项目 / Task ID**：

> 待填；只用测试账号及测试项目，必要时使用脱敏 ID。

**预期断言**：

1. 待填。
2. 待填。
3. 待填。

**实际执行命令/页面操作**：

```text
待填。禁止粘贴含凭据的原始 curl Authorization header。
```

**退出码、原始输出路径与时间**：

```text
exit_code: NOT_TESTED
stdout_or_log: N/A
started_at_utc: N/A
ended_at_utc: N/A
```

## D. 关键持久事实（按需填写）

| 项目 | 测试前 | 测试后 | 证据路径 |
|---|---|---|---|
| Task 行/状态/归属 | N/A | N/A | N/A |
| FileRecord 行及 task/source/owner | N/A | N/A | N/A |
| DatasetVersion / scientific_ready | N/A | N/A | N/A |
| request_key / digest / aliases | N/A | N/A | N/A |
| Broker message / Worker claim | N/A | N/A | N/A |
| Redis nonce/TTL/确认消费 | N/A | N/A | N/A |
| Proposal / 确认状态 | N/A | N/A | N/A |
| 文件大小 / SHA-256 / 配额 | N/A | N/A | N/A |
| 浏览器网络/SSE/截图 | N/A | N/A | N/A |
| G3 Supervisor scope / RX / inode | N/A | N/A | N/A |

**注意**：`N/A` = 此项与当前测试无关；`NOT_TESTED` = 应测试却没运行；`0` = 实际测得零。三者不可混用。

## E. 结果判定

- 结果：`NOT_TESTED`（可选 `PASS_ISOLATED` / `PASS_RUNTIME` / `PASS_E2E` / `FAIL` / `BLOCKED` / `SKIPPED`）
- 满足全部预期断言：`未判定`
- 证据足以达到声明的运行层级：`未判定`
- 未执行或跳过项：`待填`
- 观察到的安全风险：`待填`
- 关联问题编号：`待填`
- 下一步/责任人：`待填`
- 复测所用代码 revision：`待填`
- Reviewer / 审批日期：`待填`

**不可使用的结论：**“pytest 退出码 0，因此 E2E 通过”“网页能打开，因此 Gateway 认证通过”“Task CANCELLED，因此进程已停止”“HTTP 通过，因此所有下载协议已认证”。

## F. 证据索引与完整性

| 文件 | 产生方式 | SHA-256 | 脱敏检查 |
|---|---|---|---|
| `*.log` | 待填 | 待填 | 待填 |
| `*.json` | 待填 | 待填 | 待填 |
| `*.png` | 待填 | 待填 | 待填 |
| `*.har` | 待填 | 待填 | 待填 |

不要上传 `.env`、JWT、访问令牌、签名 URL、生产 DB dump 或未经脱敏的 HAR。
