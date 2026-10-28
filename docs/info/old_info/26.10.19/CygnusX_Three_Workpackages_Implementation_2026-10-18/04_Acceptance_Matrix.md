# 04｜P0-A / IAT-R3 / G3-E2 / S4 联合验收矩阵

## 1. 完成口径和证据强度

- `PASS_STATIC`：静态检查/代码链接，可只说明文件有效。
- `PASS_ISOLATED`：单测/模拟服务，必须明确替身与覆盖边界。
- `PASS_RUNTIME`：明确授权的非生产真实 PostgreSQL/Redis/Celery/Node/OS 进程，具备日志与数据库事实。
- `PASS_E2E`：真实 Chromium 对真实研究业务场景验证 + HTTP trace/PG对应。
- `BLOCKED`：环境/授权/实现不满足，不可跳过后宣称成功。
- `NOT_TESTED`：未执行，不能填成功次数、耗时=0 或通过率。
- `STALE_EVIDENCE`：源码/build/前端 bundle 与运行 manifest 不一致；需要重建重测。

**规则**：一条测试只能证明它确实断言的事实；Weak assertions（如仅 `len(keys)>=1`、仅空数组类型、仅返回 401 或登录页）不可提升为原业务场景 PASS。

## 2. P0-A：控制平面最低验收门槛

| ID | 实施位置/数据 | 真实场景 | 阶段完成判定 |
|---|---|---|---|
| PA-01 | Approval/ingestion + Admission service | 模型伪造人工审批 → 0 可执行 Admission | 未见受信 DB 核验则 BLOCKED |
| PA-02 | Project/owner role | A→B 越权和交叉 nonce | PG 多用户拒绝 |
| PA-03 | Canonical source/tool digest | 审批后改候选文件/工具 | 同 Task 拒绝，不改预算 |
| PA-04 | Admission Claim CAS | 双消费者同一 attempt/epoch | PG 恰一 claim，无双 scope |
| PA-05 | parent shared Budget | 2+ Task 并发总额度 | reserved/admitted 总账不超限 |
| PA-06 | PG 字节字段 | >=2GiB 边界、负/0、溢出 | PG CHECK / BigInteger 或显式限额 |
| PA-07 | after_commit + txn | savepoint/outer rollback/commit failure | 无孤儿许可、无早发布 |
| PA-08 | Revoke before claim | 撤销/已过期 | claim 拒绝；额度按可信状态处置 |
| PA-09 | Revoke after claim | 无可信 stop 回执 | 状态 UNKNOWN/RECONCILIATION，不假停止 |
| PA-10 | Epoch & lease | Worker death/旧 attempt retry | 拒绝 replay、不重获满额 |
| PA-11 | JWT/nonce + Redis/PG | 双确认/TTL/重放 | 单次消费、跨 owner 拒绝 |
| PA-12 | Legacy compatibility | 旧 Task/旧目录无 Admission | 不执行/不改历史文件 |
| PA-13 | caller/env/tool/protocol | 不匹配或签名变更 | fail closed；HTTP 也暂不开放 |
| PA-14 | Gate | 默认写/执行门禁 | false且独立检查 |

**阶段 DoD**：PA-01..14 全部具有确定性隔离结果，核心 PA-02/04/05/06/07/08/10/11 具有真实 PG/Redis；所有计划支持场景无可利用 fail-open。不能将“审批键消费正确”扩写为“OS egress 已停止”。

## 3. IAT-R3：产品闭环最低验收门槛

| ID | 真正入口 | 成功的强断言 | 非替代 |
|---|---|---|---|
| RA-01 | 真实 API→Legacy | tool call→Gateway PG audit→assistant final→SSE done | 直接 Gateway 调用 |
| RA-02 | 真实 API→LangGraph | 独立工具轮次+最终消息+错误语义 | Legacy 已通过 |
| RA-03 | 原 Node chat | 真实 delegated POST/Redis NX/PG audit/result 回灌 | `adapter.call` 单次手测 |
| RA-04 | Node 多用户 | scope/token/session 撤销、跨项目拒绝 | Mock callback |
| RA-05 | Metadata/GEO | 真实授权 GET 或有 provenance 标记的离线固定快照 | 没有出处的 UI 文本 |
| RA-06 | 原 Dataset service | Asset/Version/FileRecord SHA 可关联 | 手填数据库假关联 |
| RA-07 | Import Prepare | 合法 proposal 持久化，Task 下载增量=0 | 非法 accession 拒绝 |
| RA-08 | Chromium React | 真正的 FullPresentation/ResearchWorkbench mount | 主站登录页 |
| RA-09 | Chromium DatasetCard | 来源、candidate、confidence 标记显示与 DTO 一致 | 首页 200 |
| RA-10 | Chromium permission | A/B 跨项目、Session 归档、撤权后拒绝 | 无 token 401 |
| RA-11 | Chromium SSE | cursor/replay、迟到帧隔离、去重、断连 | 页面重复导航 |
| RA-12 | Chromium Safe prepare | 待审批状态，API 执行拒绝，无下载 Task | CSS disabled |
| RA-13 | UI/Node fault | timeout/error/空数据/i18n，无凭据泄漏 | 单纯 snapshot |
| RA-14 | Runtime restart | 跨进程取消/恢复声明严格不超出当前实现 | in-process 模拟 |

**阶段 DoD**：RA-01/02/03/04/06/07 必须 PASS_RUNTIME，RA-08/09/10/11/12 必须 PASS_E2E；外部 metadata 只在授权后升为 `REAL_EXTERNAL`，否则 `OFFLINE_FIXTURE` 限定标记；RA-14 若设计尚不支持必须显式 BLOCKED，不得谎报完整跨进程语义。

## 4. G3-E2：安全设施与九场景（两个不同命名空间）

**设施前提**：`EG-01 Supervisor 已在服务端实体化`、`EG-02 启动前OS scope`、`EG-03唯一强制出口`、`EG-04 Task RX原子硬计量`、`EG-05 blocks/inodes全域硬quota`、`EG-06可信 stop/empty scope`、`EG-07独立 lease/死亡回收`、`EG-08同Task Admission/receipt/FileRegistry`、`EG-09真实测试驱动/证据`。不要将这组 `EG-XX` 与仓库已有 G3-01..09 场景编号混用。

| 场景编号 | 原集成测试名称 | OS 证据必须证明 | PASS_RUNTIME 依赖 |
|---|---|---|---|
| G3-01 | small_file | 真网络、预算计数>0、scope stop、真实 FileRecord SHA | EG01-09 |
| G3-02 | unauthorized_address | 未授权 IPv4/v6 / direct connect 被阻断 | EG01-09 |
| G3-03 | unauthorized_redirect | 受控未授权 302 目标未被访问 | EG01-09 |
| G3-04 | unknown_length | 无 Content-Length 仍有真实计数/硬预算 | EG01-09 |
| G3-05 | network_over_budget | 多连接重试/Range 的 RX admitted ≤ hard limit | EG01-09 |
| G3-06 | disk_quota_exhausted | blocks/inodes 硬拒绝，旁 Task 不受影响 | EG01-09 |
| G3-07 | cancel | request/stop/egress off/scope empty/Task cancelled | EG01-09 |
| G3-08 | worker_sigkill | Worker 不在仍 lease 回收，签名真实回执 | EG01-09 |
| G3-09 | partial_reconciliation | 部分文件不成功冒领，Task/Registry/sha对账 | EG01-09 |

**G3 的 9/9 指的是九项真 HTTP 运行测试**；此前 `9 skipped` 绝不算通过。即使 9/9 完成，此认证也仅限具体 EnvironmentID、固定 HTTP source/tool/policy digest、明确 caller，有效期后必须再评审；不能外推 HTTPS/FTP/SRA/云。

## 5. S4 余项（P0-D，可并行）

| ID | 必须新增的真实故障窗口 | 历史弱证据说明 |
|---|---|---|
| SR-01 | PG-01 合法并发请求的可理解冲突重读/409 | 1 Task + IntegrityError 不足以证明 API 幂等体验 |
| SR-02 | PG-07 指定 Task k2/k3 别名都不丢 | `len(keys)>=1` 过弱 |
| SR-03 | REC-02 100+5 分批 ID 全并集105且无重复 | 之前 unique_ids=100 |
| SR-04 | MQ-03 发布成功、ACK 丢失真实时序 | 旧替身不证明 |
| SR-05 | MQ-05 API 提交后发布前 crash | queued task 恢复真实 Broker |
| SR-06 | MQ-06 Worker 长期缺席→重启 | 不能以两次业务 failed 冒充整个恢复窗口 |
| SR-07 | MQ-07 长时间 Broker 故障与冷却 | 总重投/延迟/队列增长有量测 |
| SR-08 | REC-07 原 Beat 周期实际运行 | 定时记录而非手工触发 |
| SR-09 | FR-05 取消/finalize 真并发 | 顺序两个连接不够 |
| SR-10 | AG-15 非空 200 上限数据 | 空列表/类型检查不够 |

## 6. 跨包发布门槛

`P0-A PASS_RUNTIME AND S4-RELEVANT PASS_RUNTIME AND IAT-R3 PASS_RUNTIME/PASS_E2E AND G3-E2 (HTTP) 9/9 PASS_RUNTIME AND caller/environment/protocol/tool digest governance approved` 才**允许申请** S6 受限准入，仍不等于自动开放。缺一项 `NO-GO`；S7 还需同一个科研案例 FlowFrame 真计算、科学输入类型/参数审查、BioReport 真科学结果、来源和可复现证据。

## 7. 发布模板摘要

```text
Environment ID:
Source main HEAD / all dirty hashes / submodule SHA:
Image digest / CLI digest / Policy digest:
Test ID:
Scope supported:
Actual services & OS policy:
Command / start/end / exit:
DB/Redis/HTTP/Chromium/OS evidence:
Observed result:
Expected invariant:
Result: PASS_RUNTIME | PASS_E2E | PASS_ISOLATED | BLOCKED | NOT_TESTED | FAIL | STALE_EVIDENCE
Defects / known gaps:
Reviewer / independent sign-off:
```
