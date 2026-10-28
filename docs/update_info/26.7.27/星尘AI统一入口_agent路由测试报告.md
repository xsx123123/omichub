# 星尘 AI 统一入口 —— Agent 自动分派测试报告

- 测试日期：2026-07-27
- 测试对象：星尘 AI 统一入口（智能路由器 `agent-router`）自动识别用户需求并转接对应专家 agent 的能力
- 测试方式：单元级测试（mock 模型输出，不依赖真实 API key）+ 配置一致性校验
- 测试结论：**61/61 全部通过**，路由分派、容错回退、专家转交、多专家会诊、配置一致性均符合预期；未发现业务代码 bug。

## 1. 被测机制说明

"星尘 AI 统一入口"对应的后端实体是智能路由器 agent：

| 组件 | 位置 |
|---|---|
| 路由执行逻辑 `ChatService._route_to_agent()` | `src/omichub/application/services/chat_service.py:832` |
| 路由 JSON 容错提取 `_extract_route_json()` | `src/omichub/application/services/chat_service.py:124` |
| 路由系统提示词 `ROUTER_SYSTEM_PROMPT` | `src/omichub/application/services/chat_service.py:111` |
| 路由触发点（`features.router=true` 时先分派，SSE 推 `type="route"` 事件） | `src/omichub/application/services/chat_service.py:1103-1120` |
| 路由 agent 配置 | `data/ai/router.yaml` |
| 路由决策规则 prompt | `data/ai/prompts/router.md` |
| 专家间转交（handoff） | `src/omichub/application/services/agent_handoff_service.py` |
| 入口 API | `POST /api/v1/chat/stream`（传 `agent_id="agent-router"`） |

已注册专家 agent（`data/OmicHub.yaml` 的 `agents.enabled`）：

| agent_id | 名称 | 职责 |
|---|---|---|
| agent-router | 智能助手（统一入口） | 识别意图、自动分派 |
| agent-general | 通用助手 | 兜底 / 闲聊 / 意图不明 |
| agent-rnaseq | RNA-seq 分析师 | 转录组、差异表达、富集分析 |
| agent-scrna | 单细胞分析师 | 10x / h5ad / rds 单细胞数据 |
| agent-code | 代码助手 | 写/改/调试代码、沙盒执行 |
| agent-viz | 可视化助手 | 科研绘图 |
| shania | 傻妞 | 点名陪伴式交互 |

## 2. 测试范围与结果

测试文件：
- 新增：`tests/unit/test_agent_router_dispatch.py`（47 个用例）
- 既有：`tests/unit/test_agent_router.py`、`tests/unit/test_agent_handoff_service.py`、`tests/unit/test_multi_expert_consultation_service.py`（14 个用例）

运行命令：

```bash
uv run pytest tests/unit/test_agent_router_dispatch.py \
  tests/unit/test_agent_router.py \
  tests/unit/test_agent_handoff_service.py \
  tests/unit/test_multi_expert_consultation_service.py -v
```

结果：**61 passed, 0 failed**。

### 2.1 能否调用到不同的 agent（核心问题）—— 可以

对每个已注册专家，模拟 router 模型输出分派 JSON，验证统一入口能正确落到目标 agent：

| 用例 | 结果 |
|---|---|
| 分派到 agent-rnaseq / agent-scrna / agent-code / agent-viz / agent-general / shania（参数化 ×6） | 通过，agent_id、reason 透传正确，route 事件元数据（name/avatar/color）齐全 |
| router 幻觉选中 agent-router 自身 | 通过，被正确排除并回退 agent-general |

典型问句 → 期望专家映射（模拟 router 决策，参数化 ×11）：

| 用户问句示例 | 期望分派 | 结果 |
|---|---|---|
| 帮我做 RNA-seq 差异表达分析 / bulk 转录组富集 | agent-rnaseq | 通过 |
| 分析这个 10x 单细胞数据 / h5ad 细胞类型注释 | agent-scrna | 通过 |
| 帮我调试这段 python 代码 / 沙盒里运行脚本 | agent-code | 通过 |
| 画一个火山图 / 美化成出版级 | agent-viz | 通过 |
| 傻妞陪我聊聊 | shania | 通过 |
| 你好 / 我工作区里有什么文件 | agent-general | 通过 |

### 2.2 边界与容错（18 个用例，全部通过）

- router 输出为空、纯思考无 JSON、`agent_id` 为空或 null → 均安全回退 `agent-general`
- 未知/幻觉 agent_id → 回退 `agent-general`
- 模型调用异常 → 返回 None，按原 agent 继续，不中断会话
- JSON 包裹在 markdown 代码块 / 夹杂解释文字 → 可容错提取
- `consult_agent_ids` 中幻觉 agent 被过滤、与主专家去重、超 max_experts 截断、功能关闭时恒为空、非列表类型安全忽略
- `expect_handoff` 异常值（"yes"、空串、None、0/1、列表等 ×10）→ 按 `bool()` 宽松转换，不抛异常（见 3.2 观察项）

### 2.3 专家转交与多专家会诊（既有测试，全部通过）

- handoff 数据包大小受预算约束、产物路径限制在相对工作区内
- handoff 指令能从 toolbridge 信封中提取，目标 agent 白名单强制校验
- 多专家会诊：并行收集各专家意见，个别失败不影响整体

### 2.4 配置一致性（11 个用例，全部通过）

- `agents.enabled` 的 7 个 agent 配置文件全部存在且可正常加载（agent_id、system_prompt 非空）
- `data/ai/prompts/router.md` 候选表中的 agent_id 集合与实际注册表**严格一致**，无 prompt/注册表漂移

## 3. 问题与观察项

### 3.1 缺陷

未发现业务代码缺陷。

### 3.2 观察项（非 bug，建议关注）

1. **`expect_handoff` 解析过于宽松**（`chat_service.py:893`）：模型输出 "yes"、"0" 等异常值时按 `bool()` 宽松转换（如 `"0"` 会被当作 True）。当前安全（不会崩），但建议后续改为严格布尔校验，避免模型输出非布尔值时意外触发转交。
2. **`orchestrator.yaml` 不在默认路由候选中**：该 agent 仅在 `settings.mas_enabled=true` 时动态追加（`agent_loader.py:37-38`）。默认配置下 router prompt 不含它属预期，但开启 MAS 后需确认 `router.md` 同步更新，否则 router 无法分派到 orchestrator。
3. **路由正确性依赖 LLM 决策质量**：本次测试 mock 了 router 模型输出，验证的是"分派执行"链路的正确性。真实场景下"问句 → 正确专家"的命中率取决于 `qwen3.7-max` 对 `router.md` 规则的遵循度，需要真实 API key 做端到端评测（见第 4 节）。
4. 既有警告：`src/omichub/application/schemas/ai_provider.py:30` 使用 Pydantic V2 已废弃的 class-based config，建议迁移到 `ConfigDict`。

## 4. 未覆盖项与后续建议

本次为 mock 级测试，以下需真实环境补充：

- **端到端路由命中率评测**：配置有效 `AL_API_KEY`（DashScope）后，起服务（`make dev`），用真实问句集调用 `POST /api/v1/chat/stream`（需登录 JWT），统计 router 分派准确率与 SSE `route` 事件正确性。
- **多轮会话中的路由稳定性**：同一 session 连续提问时 agent 切换是否符合预期。
- **前端联动**：`route` 事件在 `frontend/src/components/ai-chat/` 中的展示（专家卡片、头像、切换动画）。
- **开启 `mas_enabled` 后** orchestrator 的分派与会诊链路。

## 5. 复现方式

```bash
# 全部路由相关测试（无需 API key）
uv run pytest tests/unit/test_agent_router_dispatch.py \
  tests/unit/test_agent_router.py \
  tests/unit/test_agent_handoff_service.py \
  tests/unit/test_multi_expert_consultation_service.py -v
```
