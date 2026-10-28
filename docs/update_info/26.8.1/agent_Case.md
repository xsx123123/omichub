# AgentTeams Case 与 Element 协作聊天室架构说明

> 更新日期：2026-08-01  
> 状态：OmicHub 的 AgentTeams Case、聊天入口与 Element 嵌入能力已实现；Case 关联聊天室房间的数据面（Bridge `element_room_url` 字段 + 按 Case 解析房间地址）已实现；真实 Matrix / Element 控制面及 AgentTeams Matrix Gateway 尚未在当前开发环境部署。

## 1. 目标

在不替换 OmicHub 既有 AI 助手、分析流程、工作区和任务系统的前提下，为复杂分析交付提供可审计的多角色协作闭环：

```text
OmicHub AI 助手
  → 创建 AgentTeams Case
  → 预检 / 人工审批 / 工作项分派 / 分析执行 / 交付验收
  → 可选进入 Element 协作聊天室，查看和参与多角色沟通
```

Element 聊天室不是新的 OmicHub Agent，也不替换现有 AI 助手。它是让当前平台 Agent、项目负责人和审批人能够在同一个受控房间中协作的通信界面。

## 2. 术语与职责

| 名称 | 职责 | 是否已在当前项目实现 |
|---|---|---|
| OmicHub Agent | 当前平台的通用、RNA-seq、单细胞、代码、可视化等 Agent；负责推理、工具调用、分析与报告 | 是 |
| AgentTeams Case | 复杂任务的协作载体，记录项目、目标、预检、审批、工作项、执行证据与交付状态 | 是 |
| AgentTeams Bridge | OmicHub 与独立 AgentTeams 控制面的受限 REST 适配器；不暴露 Worker 凭据给浏览器 | 是 |
| Matrix | 协作消息后端；负责账号、房间、成员、消息历史与权限 | 否，需独立部署 |
| Element | Matrix 的 Web 聊天客户端；在 OmicHub AI 页面中以抽屉方式嵌入 | OmicHub 嵌入入口已实现；服务本体未部署 |
| Matrix Gateway | 让现有 OmicHub Agent 以 Matrix Bot 身份收发协作消息的适配层 | 否，规划中 |

## 3. 总体架构

### 3.1 当前已落地架构

```text
浏览器
  ├─ OmicHub AI 助手页
  │    ├─ 普通 Agent 聊天
  │    ├─ 协作 Case 确认卡 / Case 状态卡
  │    └─ “协作聊天室”抽屉（嵌入已配置的 Element 房间）
  │
  └─ OmicHub API
       ├─ ChatService / 现有 Agent Runtime
       ├─ /api/v1/agent-teams/* 受登录态保护的 Case API
       ├─ AgentTeams Bridge 设置服务
       └─ AgentTeams Service（仅服务端持有 Bridge 身份令牌）
                    │
                    ▼
       独立 AgentTeams Bridge 容器
                    │
                    ▼
       预检、审批、任务提交、审计事件与 Case 状态
```

### 3.2 目标完整架构

```text
项目负责人 / OmicHub 用户
       │
       ▼
OmicHub AI 助手页
  ├─ 现有平台 Agent 对话
  └─ Element 协作聊天室
       │                         ┌────────────────────────────────────┐
       └────────────────────────▶│ Matrix / Element 独立协作控制面     │
                                 │  Case 房间 / 成员 / 权限 / 消息历史 │
                                 └────────────────────────────────────┘
                                                   ▲
                                                   │
                              ┌────────────────────┴───────────────────┐
                              │ AgentTeams Matrix Gateway（规划中）    │
                              │ 受控读取/发送消息，映射平台 Agent 身份 │
                              └────────────────────┬───────────────────┘
                                                   │
                                                   ▼
                     现有 OmicHub Agent Runtime / AgentTeams Bridge
                      ├─ RNA-seq Agent
                      ├─ Data Steward
                      ├─ Workflow Operator
                      ├─ Quality Auditor
                      └─ Delivery Reporter
```

设计原则：**Agent 仍是 OmicHub 现有 Agent；Matrix/Element 只负责协作通信。** 不应在 Matrix 容器中复制一套脱离 OmicHub 权限、工作区和工具策略的 Agent 运行时。

## 4. 已完成内容

### 4.1 Case 与聊天入口

- 支持在聊天中经用户确认调用 `create_agentteams_case` 创建协作 Case。
- 内置 Agent 会在 Case 工具可用时获得运行时协作说明，避免旧数据库提示词遗漏该能力。
- 支持 Case 状态卡、Case 详情页、预检、人工审批、受控任务提交和事件审计。
- AgentTeams 聊天入口由平台配置 `agentteams_chat_entry_enabled` 控制。

相关实现：

- `src/omichub/application/services/agentteams_case_tool_service.py`
- `src/omichub/application/services/agentteams_service.py`
- `src/omichub/api/v1/agentteams.py`
- `frontend/src/components/ai-chat/AgentTeamsCaseCard.vue`
- `frontend/src/views/AgentTeamsCaseView.vue`

注：原 `/agent-teams` "Agent 协作中心"页面（创建表单 + Case 列表）已于 2026-08-01 移除；创建统一走聊天内 `create_agentteams_case` 确认卡，Case 详情页从聊天 Case 卡片进入。Case 列表自 2026-08-02 起并入任务中心：`/tasks` 页内 "AgentTeams 协作" tab（`frontend/src/components/task/AgentTeamsCasesPanel.vue`），支持 `/tasks?tab=agent-teams` 深链，Case 详情页返回按钮指向该地址。

### 4.2 AI 助手页中的 Element 聊天室入口

AI 助手头部已增加“协作聊天室”按钮。点击后打开 `AgentTeamsChatDrawer`：

1. 向 `GET /api/v1/agent-teams/chat-room` 请求当前可用的公开 Element 房间地址；
2. 在右侧抽屉中以 `iframe` 嵌入 Element Web；
3. 当部署策略禁止 iframe 嵌入时，提供“在新窗口打开”回退；
4. 未配置时显示明确空状态，而不伪造聊天室可用；
5. Element 的登录、成员资格、消息权限继续由 Matrix / AgentTeams 控制面处理，OmicHub 不保存 Matrix 密码或访问令牌。
6. `GET /api/v1/agent-teams/chat-room` 支持可选 `case_id` 参数：传了则优先返回该 Case 关联的 `element_room_url`（同样经过 URL 安全校验），未关联时回落全局配置地址；响应带 `source`（`case` / `global`）标识来源。
7. AI 聊天流中的 Case 状态卡与 Case 详情页均有"协作聊天室"入口，点击后直接打开对应 Case 的房间抽屉。

相关实现：

- `frontend/src/components/agent-workspace/AgentSandbox.vue`
- `frontend/src/components/agent-workspace/AgentTeamsChatDrawer.vue`
- `frontend/src/api/agentTeams.ts`
- `src/omichub/api/v1/agentteams.py`

### 4.3 Element 房间地址配置与安全边界

管理员可在 **设置 → AgentTeams Bridge → Element 协作房间地址** 配置公开的 Element 房间 URL；也可通过环境变量配置：

```dotenv
AGENTTEAMS_ELEMENT_URL=https://element.example.org/#/room/!bioops:example.org
```

该地址必须是完整的 `http` 或 `https` URL，且不允许包含：

- `access_token`
- `login_token`
- `password`

浏览器只会获得经过校验的公开房间地址；AgentTeams Bridge 的 Manager、Data Steward、Approval Authority、Workflow Operator 身份令牌仍只存在于服务端加密配置或环境变量中。

相关实现：

- `src/omichub/application/services/agentteams_bridge_settings_service.py`
- `src/omichub/infrastructure/database/models/agentteams_bridge.py`
- `src/omichub/application/schemas/agentteams_bridge.py`
- `frontend/src/components/admin/AgentTeamsBridgeTab.vue`
- `alembic/versions/c7d8e9f0a1b2_add_agentteams_element_url.py`

## 5. 当前运行状态与限制

当前开发环境已经启动：

- OmicHub Web、Nginx、Worker、Beat；
- 独立 `agentteams-omichub-agentteams-bridge-1` Bridge 容器；
- Case、预检、审批、任务提交、审计与聊天室入口相关 API。

当前开发环境尚未启动：

- Matrix Homeserver；
- Element Web；
- AgentTeams Matrix Gateway；
- 可供当前用户加入的真实协作房间。

因此 `AGENTTEAMS_ELEMENT_URL` 为空时，AI 页面会显示“AgentTeams Element 聊天室尚未配置”。这是预期安全行为，不代表 Case 或 Bridge 不可用。

## 6. 推荐部署方式

不要把所有内容塞入一个万能容器。本项目的部署资产已经按"三个独立面"拆分，全部位于 `deploy/` 下，部署 Matrix / Element 时**直接复用这些已有 Dockerfile、Compose 与 Helm 配置**，不要另起一套协作栈：

```text
deploy/
  ├─ docker/                          # OmicHub 主栈（已构建）
  │    ├─ Dockerfile                  # Web / API 镜像
  │    ├─ Dockerfile.worker           # Worker 镜像
  │    ├─ Dockerfile.frontend         # 前端镜像
  │    └─ docker-compose.yml          # Web / Nginx / Worker / Beat 等
  │
  └─ agentteams/                      # AgentTeams sidecar（已构建）
       ├─ docker-compose.agentteams.yml      # 独立 Bridge 容器（只读、no-new-privileges、健康检查）
       ├─ docker-compose.omichub-proxy.yml   # 主栈叠加网络 override，接入 omichub_bridge_gateway
       ├─ bridge.env.example                 # Bridge 部署管理的密钥模板
       ├─ preflight.py                       # 部署前配置校验（拒绝占位符、缺失身份）
       ├─ verify_control_plane.py            # 控制面验收：只读检查 default-deny 与非特权 Pod
       └─ kubernetes/network-policy.default-deny.yaml
```

对应的三层部署形态：

```text
OmicHub 主栈（deploy/docker/docker-compose.yml）
  └─ ChatService / 既有 Agent Runtime / Studio / MAS / Celery / Snakemake / 任务与报告

AgentTeams Bridge sidecar（deploy/agentteams/docker-compose.agentteams.yml）
  └─ 独立 Compose 项目，经外部网络 omichub_bridge_gateway 与主栈受限互通；
     该网络只暴露 OmicHub API 网关，绝不暴露数据库、Redis 或 Worker 服务

AgentTeams 控制面（官方 Helm chart，独立 K8s 命名空间 agentteams-system）
  ├─ Tuwunel Matrix     # 账号、房间、成员、消息与权限
  ├─ Element Web        # Element 聊天 UI
  ├─ MinIO / Higress    # 控制面自有组件
  └─ matrix-gateway     # 规划中：平台 Agent 与 Matrix Bot 身份适配
```

部署顺序与关键命令（详见 `deploy/agentteams/README.md`）：

```bash
# 1. 启动 Bridge sidecar（先建网关网络，再启动 Bridge）
docker network create omichub_bridge_gateway
docker compose -f deploy/agentteams/docker-compose.agentteams.yml up --build -d

# 2. 主栈叠加 proxy override 启动 Web（保留既有 app / data / Worker / Sandbox 网络）
docker compose \
  -f deploy/docker/docker-compose.yml \
  -f deploy/agentteams/docker-compose.omichub-proxy.yml \
  up -d web

# 3. 部署前校验（拒绝 replace-* / change-me-* 占位符与缺失 Worker 身份）
python3 deploy/agentteams/preflight.py \
  --bridge-env deploy/agentteams/bridge.env \
  --omichub-env .env

# 4. Matrix / Element 控制面：官方 AgentTeams Helm chart，独立命名空间
helm install agentteams higress.io/agentteams \
  --namespace agentteams-system --create-namespace \
  --render-subchart-notes \
  --set credentials.llmApiKey="$AGENTTEAMS_LLM_API_KEY" \
  --set credentials.adminPassword="$AGENTTEAMS_ADMIN_PASSWORD"

# 5. 控制面验收门：先 default-deny，再只读核验
kubectl apply -f deploy/agentteams/kubernetes/network-policy.default-deny.yaml
python3 deploy/agentteams/verify_control_plane.py --namespace agentteams-system
```

这样可以保证：

- Matrix / Element 运行在独立 K8s 命名空间，受 `network-policy.default-deny.yaml` 约束，不接触 OmicHub PostgreSQL、Redis、Docker Socket 或用户工作目录；
- Bridge 容器以只读文件系统、`no-new-privileges` 运行，宿主端口默认只绑定 `127.0.0.1:8088`；
- Element 不接触 Bridge Worker 令牌；Bridge 调用 OmicHub 仅使用最小权限的集成用户 API Key（建议仅 `flows:read`、`tasks:read`、`tasks:submit`、`tasks:cancel` 四个 scopes）；
- Matrix Gateway（规划中）只可调用受控 Agent Gateway 或明确允许的 OmicHub API；
- 真实分析仍由 OmicHub 流程、任务与权限体系执行。

## 7. Agent 在聊天室中如何协作

部署 Matrix Gateway 后，聊天室成员应映射到当前平台已有的 Agent 角色，而不是再创建独立的分析系统：

| Matrix 身份 | 对应 OmicHub 职责 |
|---|---|
| `bioops-manager` | Case 分解、工作项协调、过程汇总 |
| `data-steward` | 样本表、元数据、输入完整性预检 |
| `workflow-operator` | 已审批流程提交、运行状态与失败分流 |
| `quality-auditor` | QC 门禁、结果质量结论 |
| `delivery-reporter` | 交付清单、报告与验收说明 |
| 当前用户 | 需求补充、确认、审批和验收 |

推荐消息流：

```text
用户在 OmicHub 创建 Case
  → Bridge 创建或关联 Matrix 房间
  → Matrix Gateway 将 Case 上下文映射给指定平台 Agent
  → Agent 通过受控工具发送协作消息
  → 用户在 Element 房间补充信息或确认审批
  → Gateway 校验用户和 Case 归属后回写 AgentTeams / OmicHub 状态机
```

初始阶段可采用“一个 BioOps 团队公共房间”；生产阶段推荐“一个 Case 一个房间”，以隔离项目上下文和成员权限。

## 8. 后续实施清单

### 8.1 Matrix / Element 控制面

控制面部署直接使用 `deploy/agentteams/` 已有资产，不再新建 Compose 栈：

1. 按第 6 节命令安装官方 AgentTeams Helm chart 到独立命名空间 `agentteams-system`（自带 Tuwunel Matrix、Element Web、MinIO、Higress）。
2. 应用 `deploy/agentteams/kubernetes/network-policy.default-deny.yaml`，并运行 `verify_control_plane.py` 通过控制面验收门；仅对 Controller/Worker-to-Bridge 流量和已批准的 Matrix/MinIO 网关追加 allow 策略。
3. 配置 HTTPS、备份、受控账号注册与用户登录策略；Controller API、Matrix homeserver、MinIO、Higress 控制台保持内网，只暴露经认证的 Matrix/Element 网关。
4. 配置 Element Web 允许被 OmicHub 域名 iframe 嵌入（`frame-ancestors` / `X-Frame-Options`），否则聊天室抽屉只能走新窗口回退。
5. 为 BioOps 角色创建受控 Bot / Application Service 身份。
6. 创建团队公共房间或按 Case 自动创建独立房间。

### 8.2 自动房间发现，替代手工 URL

数据面已经落地（2026-08-01）：

- Bridge 的 `CaseRecord` 与 Case 创建请求支持可选 `element_room_url` 字段，校验规则与全局 Element URL 一致（http/https、禁止内嵌 `access_token` / `login_token` / `password`），所有 Case 对外响应均携带该字段（`integrations/agentteams/bridge/omichub_agentteams_bridge/models.py`、`service.py`）。
- `GET /api/v1/agent-teams/chat-room?case_id=...` 按 Case 解析房间：Case 关联了合法房间地址时返回该地址（`source="case"`），否则回落全局 `AGENTTEAMS_ELEMENT_URL`（`source="global"`）；访问他人 Case 沿用既有鉴权拒绝。
- 前端 Case 状态卡与 Case 详情页可直接打开对应 Case 的聊天室抽屉，不再只有全局面级入口。

当前 `AGENTTEAMS_ELEMENT_URL` 仍是开发与过渡阶段的全局兜底地址。完整方案中"创建 Case 时由 Bridge / AgentTeams Controller 自动建 Matrix 房间并回填 `element_room_url`"尚未实现，依赖 Matrix 控制面部署：

```text
AI 助手点击“协作聊天室”
  → OmicHub 查询当前 Case（已实现）
  → Bridge / AgentTeams Controller 返回该 Case 的 Matrix room_id 或 Element room URL（数据字段已就绪，自动建房待 Matrix 部署）
  → 前端自动打开对应房间（已实现）
```

### 8.3 Matrix Gateway

1. 实现每个 Agent 角色的受控 Matrix Client / Bot 身份。
2. 仅允许 Gateway 在已授权 Case 房间内读写消息。
3. Gateway 不直接访问 OmicHub 数据库、Docker Socket 或用户目录。
4. Gateway 通过受控 Agent Gateway 调用现有 OmicHub Agent，而不是复制 Agent Prompt、模型和工具执行逻辑。
5. 将关键协作消息、审批和房间关联记录为 AgentTeams 审计事件。

## 9. 验证记录

已完成的本地验证：

- `tests/unit/test_agentteams_bridge_settings_service.py` 与 `tests/unit/test_agentteams_service.py`：20 项通过；
- AgentTeams Element URL 的格式与敏感参数校验通过；
- 前端 `vue-tsc --noEmit` 通过；
- 前端生产构建通过；
- Alembic 已应用 `c7d8e9f0a1b2_add_agentteams_element_url.py`；
- 运行中的 `/api/v1/agent-teams/chat-room` 已出现在 OpenAPI；
- OmicHub Web 与 AgentTeams Bridge 健康检查通过。

2026-08-01 按 Case 解析房间的增量验证：

- `pytest tests/unit -k agentteams`：37 项通过（含 chat-room 按 Case 解析、URL 注入拒绝、越权传播等 6 个新增用例）；
- Bridge 契约测试 `integrations/agentteams/bridge/tests/`：36 项通过（含 `element_room_url` 序列化全路径与非法 URL 拒绝等 9 个新增用例）；
- 前端 `vue-tsc --noEmit` 通过，`agentteams-case-card.test.ts` 通过。

尚未完成的端到端验证：真实 Matrix 登录、真实 Element 房间加入、Agent Bot 发消息、用户消息回流到 OmicHub Agent。该部分依赖 Matrix / Element / Matrix Gateway 的实际部署与身份配置。
