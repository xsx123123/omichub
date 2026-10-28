# 06｜S4 下载任务可靠性剩余故障窗口收尾计划（并行小包）

## 1. 目的

这不是第四套系统重构，而是对已有 S4-A/S4-B0 的 PG/Redis/Celery 核心机制进行**精确补测**。2026-10-18 审计指出历史 IAT-R2 的部分用例语义不足，包括：PG-01 返回原始 `IntegrityError`、PG-07 只断言任意别名长度、REC-02 声明 100+5 而只报告 100 个 unique IDs、MQ-02 真实 Broker 错误注入与 dispatch 替身事实混写、MQ-03 真实 ACK 丢失/HTTP API crash/长期 Worker absence/Beat 周期缺证。审计仅提供源代码与旧日志对账，新一轮真实测试需独立授权。

## 2. 任务重点及场景

| 先后 | 行动 | 通过条件 |
|---|---|---|
| SR-01 | 真实 PG 两连接同一 Task/intent 请求 | 一个 Task，合法重试返回该 Task 或稳定 409/明确业务冲突；不泄露内部 IntegrityError；无死锁 |
| SR-02 | 指定 Task 三个请求别名并发追加 | 指定 Task 行内三个别名都存在，先后顺序明确；不只看任意行 `len>=1` |
| SR-03 | 105 queued + 101 legacy batch | 跨批 100+5，实际唯一ID并集=105，重复=0，不因 updated_at 乱序永远饥饿 |
| SR-04 | 真实 Broker 接受消息但故障造成 ACK 丢失 | 原消息可能重复；Worker 一次领取，Task/FileRecord/预算不二次落库 |
| SR-05 | DB commit 之后、enqueue 之前 API 进程 SIGKILL | queued Task 可被 Beat 恢复、消息最终消费；不误报 rollback |
| SR-06 | Worker 长时间离线、恢复后重复接收 | 只有原 Task 状态，running 不盲重跑，reconciliation 必须保守 |
| SR-07 | Broker 长期断连/恢复 | recovery_attempts/backoff/延迟/写入量可观测，有限任务不会永久饥饿 |
| SR-08 | 真实 Celery Beat 实时 600 秒周期（或获授权短周期专项配置） | 真实调度时间线，非手动 `reconcile` 充当周期 PASS |
| SR-09 | cancel/finalize 真实并发冲突 | 终态不复活，原 FileRegistry 不二次登记、不重复扣配额 |
| SR-10 | worker test route / service identity | 测试下载 Worker 订阅测试队列且 `SERVICE_NAME=worker`；不让报表 Worker 接下载 |

## 3. 执行边界

1. 只能在明确授权的 disposable nonprod 环境中对**测试 API/Broker/Worker**注入故障；有时间/消息/连接/CPU/磁盘额度与恢复计划。
2. 原 Celery、PG、FileRegistry 唯一权威；不新建 scheduler/outbox/queue，不把运营 Worker 加 root/docker.sock。
3. G3 关闭期间允许用合法的“最终业务 failed/queued”受控测试证明调度、状态恢复，**不得**声明下载成功或 OS 安全认证。
4. 实测从原始 Task DB、PG SQL、Broker 消息、Worker received/claim、FileRecord SHA、取消时序获取；不得将 Celery `succeeded` 误当业务 Task `success`。

## 4. Codex 最小执行提示词

> 请针对 `06_S4_Residual_Reliability.md`，先读 `CygnusX_Current_Implementation_Status_Audit_2026-10-18.md` 的第 6、11、14、15 节，复核现有 `download_service.py`、`infrastructure/download/reliability.py`、`task_repository.py` 与 Celery tests。保留已有 after_commit、User 锁、queued→running、FileRegistry 机制。先补弱断言（指定 Task、严格 105 IDs 并集、真实 ACK/API death 证据），再于**明确授权的专用 PG/Broker/Worker/Beat**执行 SR-01..10。不可重复设计队列或开放 G3，不能操作生产环境。结果输出 `docs/implementation/cygnusx-s4-reliability-last-gaps.md`、逐案例原始 logs/exit/SQL，未运行项 BLOCKED。修改前先保护当前 dirty/source digest；完成停止，不提交推送。

## 5. 完成条件与后续依赖

只有真实 Broker/Worker/Beat、双 PG 会话、ACK/crash/长故障窗口、幂等和 FileRecord 最终一致性满足强断言，才能为 S6 贡献“可靠性运行认证”范围。S4 通过并不能替代 P0-A 授权或 G3 OS/网络/盘硬限制。失败文件或 UNKNOWN stop 状态必须进入对账，不得自动 READY。
