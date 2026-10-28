# Task 14 设计：会话高频状态拆分与流式互斥

> 状态：待确认后实施。本文只定义迁移与兼容策略，不改变运行时行为。

## 目标

解决 `ChatSessionModel.sandbox_meta` 被长连接 room-events、超频运行时和 Case watch 并发读改写时的 lost update，并阻止同一聊天会话同时启动两条流式执行。

## 数据模型变更

向 `chat_sessions` 增加以下可空列：

| 列 | 类型 | 用途 |
| --- | --- | --- |
| `matrix_room_id` | `String(255)` | Matrix 房间标识；由建房/聊天房间流程维护。 |
| `matrix_sync_cursor` | `Text` | room-events 已提交游标；每批事件即时提交。 |

迁移步骤：

1. 新增两列与索引，不删除 JSONB 原键。
2. 数据迁移：从 `sandbox_meta.matrix_room_id` / `matrix_sync_cursor` 回填空列。
3. 读取优先独立列，空值时兼容读取 JSONB；写入只写独立列。
4. 一个发布周期后清理 JSONB 冗余键（单独迁移，保留回滚窗口）。

`overdrive_runs` 保持 JSONB，但所有更新改为 PostgreSQL `jsonb_set` 局部更新，禁止把旧快照整体赋回。

## 会话流式锁

- Redis key：`chat:stream:lock:{session_id}`。
- 获取：`SET key <random-token> NX EX <max_stream_seconds>`；TTL 与服务端允许的最长空闲/审批等待时间一致，并在心跳或每轮工具执行前续租。
- 冲突：`POST /api/v1/chat/stream` 在开始生成器前返回 HTTP `409`，错误码 `CHAT_STREAM_CONFLICT`，前端保留当前流并提示“该会话正在执行”。
- 释放：仅用 Lua 比较 token 后删除；`done`、error、客户端断连、异常 `finally` 均释放。
- 新会话：先创建并提交 session，再获取锁，避免临时 session ID 锁冲突。

## 兼容与验收

- 前端不改 SSE payload；仅识别 409 并不创建第二个助手占位消息。
- 并发测试：同 `session_id` 两次流式请求，第二个请求 409；第一个结束后可重新请求。
- 数据一致性测试：room cursor、overdrive 状态、Case watch 状态并发更新后均保留各自键。
- 迁移测试：已有 JSONB 数据回填后 room-events 从独立 cursor 恢复，不重复入库。

## 回滚

代码先保留 JSONB 读取 fallback；若独立列写入异常，停止新版本实例并回滚到读取 JSONB 的上一版本。不得在完成一个稳定发布周期前删除旧键。
