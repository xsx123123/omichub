# Manager 模糊任务补全与二次分派排查

## 排查对象

- 会话 ID：`38b22131-5858-4704-82d0-12ce3f5f3345`
- 用户问题：只有“两个 TP53 分组”和“挖掘新颖发现”，未说明数据模态、分组定义、样本量与输入形态。
- 现场截图：
  - `docs/26.8.6/multi-agent/Screenshot 2026-08-06 at 14.32.49.png`
  - `docs/26.8.6/multi-agent/Screenshot 2026-08-06 at 14.33.54.png`
  - `docs/26.8.6/multi-agent/Screenshot 2026-08-06 at 14.34.10.png`

## 现场结论

1. Manager 没有先澄清数据模态，直接安排了通用、单细胞高级分析、代码和可视化四类任务。
2. “TP53 分组”本身不能证明数据是单细胞；bulk RNA-seq、单细胞、空间组学、蛋白组或临床队列都可能采用 TP53 分组。
3. 子任务执行阶段出现目标映射错误：多个展示为不同专家的任务都报告 `agent-viz` 未标记为可派生 Agent。
4. 全部子任务失败后，Manager 把内部汇总指令和自我推理直接展示给用户。

## 根因

1. 普通路由提示词要求“信息不足仍选最合适首接专家”，会诱导模型根据 TP53、细胞通讯、轨迹等联想硬猜单细胞路线。
2. 超频模式原先只有一次性“Manager 分派 → Worker 并行 → Manager 汇总”，没有 intake 和二次规划阶段。
3. 子 Agent 运行时只保留少量 builtin 工具，未完整透传 `ask_user`、联网搜索、绑定 MCP 与技能读取能力。
4. 旧 fan-out 结果按 Agent 标识关联时，重复或异常目标可能造成结果错配；当前实现已改为按 assignment 下标对齐。

## 修复后的流程

1. 路由前执行通用组学 intake 检查；只有开放式发现、研究设计或详细计划类请求才触发，不阻拦明确的差异分析、富集或绘图任务。
2. 若缺少会改变路线的信息，普通模式确定性路由到通用助手，并强制调用 `ask_user`，不得直接输出假定模态下的计划。
3. 超频模式先派生通用助手收集：数据模态、分组定义、样本/细胞规模和输入形态；需要最新公开背景时允许使用 `web_search`。
4. 原始问题和待补充问题写入会话 `sandbox_meta.overdrive_intake`。用户回答后，Manager 使用“原始请求 + 用户补充信息”重新规划专家任务，并清除待补全状态。
5. 子 Agent 保留安全限制：禁止递归 fan-out、handoff 和长耗时 analysis flow；`ask_user` 与需审批工具升级回 Manager。
6. 子 Agent 可实际调用其已绑定的 backend builtin、MCP、联网搜索与技能读取工具；每次工具执行继续使用独立数据库会话和隔离工作目录。
7. 两个以上不同专家产出有效初步结论后，进入交叉复核轮次。每位专家会收到所有同伴结论，检查冲突、遗漏和不可行假设，再把修订结论交给 Manager 最终汇总。

## 验证

- 模糊 TP53 计划不会调用路由模型硬猜专家，而是进入通用 intake。
- 超频 intake 会保存原始请求并发出结构化 `ask_request`。
- 用户补充后，Manager 提示词同时包含原始请求与补充信息。
- 子 Agent 工具目录包含 `ask_user`、`web_search` 和绑定 MCP，并已验证 MCP 实际调用使用独立子会话上下文。
- 截图中 `agent-viz` 不可派生问题对应配置已补充 `subagents_spawnable: true`；通用、RNA-seq、单细胞、代码和可视化专家当前均可派生。

## 环境限制

当前开发沙盒中的数据库地址是 Compose 内部主机 `db:5432`，没有 Docker socket 权限，也没有本地 OmicHub 服务端口，因此无法直接读取该会话在 `chat_sessions`、`chat_messages` 和 `chat_handoff_events` 中的记录。截图已能证明用户输入、错误分派、`agent-viz` 错误和提示词泄露。

在可访问数据库的 Web/Worker 容器内可执行：

```bash
python scripts/inspect_chat_session.py 38b22131-5858-4704-82d0-12ce3f5f3345 \
  --full-content \
  --output /tmp/tp53-session-audit.json
```

该命令只读查询 `chat_sessions`、`chat_messages`、`chat_handoff_events` 和协作降级事件，不修改数据库。
