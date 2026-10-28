# OmicStudio AI 工作台架构梳理

> 梳理时间：2026-08-18
> 基于代码实际状态，覆盖启用机制、前后端架构、组件结构和优化建议。

---

## 一、总览

AI 工作台（OmicStudio）是 OmicHub 平台的核心分析执行环境。用户在 AI 助手中发起对话后，可"进入工作台"获得完整的沙盒代码执行能力——AI 在独立 Docker 容器中编写、运行 Python/R/Bash 代码，产出图表、数据文件和报告。

**核心设计理念**：
- 每个工作台会话拥有独立 Docker 沙盒容器，工作区通过 bind-mount 持久化
- 容器内运行 `sandbox-agent`（FastAPI + UDS），宿主机通过 `StudioSandboxManager` 管理生命周期
- 前端三栏布局：会话/文件树 | 对话+代码编辑器 | 产物+沙盒状态
- 支持监督/放权两种权限模式（HITL）

**发展阶段**：

| 阶段 | 状态 | 关键能力 |
|------|------|---------|
| P0 骨架 | ✅ | 沙盒 + 12 个内置工具 + 三栏工作台 |
| P1 平台联动 | ✅ | 数据引入 + 报告中心 + Context Packager + plan 事件 |
| P2 体验与规模化 | ✅ | diff 回滚 + 长任务 + 预热 + 网络隔离 + MCP/Skills 渐进披露 |
| P3 打磨 | ✅ | 知识库联动 + 会话分享/导出 + 提炼为 Skill + 用量统计 |

---

## 二、启用机制

### 2.1 入口方式

用户有 **3 种方式** 进入 AI 工作台：

#### 方式一：AI 助手中点击"进入工作台"按钮
- 位置：`KimiChatInput.vue` 底部输入栏
- 条件：`showWorkbenchEntry` prop 为 true
- 流程：
  1. 调用 `studioApi.promoteSession()` 将当前聊天会话升级为 Studio 会话
  2. 或调用 `studioApi.createSession()` 创建新 Studio 会话
  3. 路由跳转到 `/studio/:sessionId`

#### 方式二：Agent 配置自动跳转
- 条件：Agent YAML 配置了 `features.studio.default_mode: studio`
- 流程：
  1. `agentHub` store 的 `maybeRedirectToStudio()` 检测到该标志
  2. 自动创建/跳转 Studio 会话
  3. 用户无感知进入工作台
- 已配置此模式的 Agent：`general`（通用助手）、`rnaseq`、`scrna`、`viz`、`code`、`qc`、`data`、`atacseq` 等

#### 方式三：从报告中心"在工作台中优化"
- 入口：`studioApi.createSessionFromReport()`
- 流程：
  1. 验证报告有效性
  2. 创建 Studio 会话
  3. 将报告产物软链接到新工作区
  4. 写入 `context_pack` 供 AI 理解上下文

### 2.2 会话生命周期

```
创建会话 → 预热容器(prewarm) → 沙盒运行中(running) → 空闲回收(idle_ttl=10min)
                                    ↓                        ↓
                              休眠(hibernate)          工作区保留(retention=7天)
                                    ↓                        ↓
                              保留工作区快照            清理(cleanup_expired_workspaces)
```

**关键配置**（`data/ai/studio.yaml`）：
- `session.idle_ttl_minutes: 10` — 空闲 10 分钟后回收容器
- `session.workspace_retention_days: 7` — 工作区保留 7 天
- `session.prewarm_on_create: true` — 创建后立即后台预热容器
- `ui.hibernate_on_leave: true` — 离开页面时自动休眠沙盒

### 2.3 路由定义

```typescript
// frontend/src/router/index.ts
{ path: '/studio/:sessionId?', name: 'studio', component: StudioView, meta: { requiresAuth: true } }
{ path: '/studio/shared/:token', name: 'studio-shared', component: SharedStudioView, meta: { requiresAuth: false } }
```

---

## 三、前端架构

### 3.1 三栏布局（StudioView.vue）

```
┌─────────────────────────────────────────────────────────────────────┐
│  顶栏：智能体名称 / 模型选择 / 权限开关 / 沙盒状态 / 操作按钮       │
├──────────┬──────────────────────────────────┬───────────────────────┤
│          │  视图模式切换栏                     │                      │
│  左栏     │  [对话] [分屏] [代码]  ✦ 跟随AI   │  右栏                │
│  260px   ├──────────────────────────────────┤  232px               │
│          │                                  │                      │
│ ┌──────┐ │  对话面板    │  代码编辑器面板     │ ┌──────────────────┐ │
│ │分析   │ │  (KimiMsg   │  (Monaco Editor    │ │研究结果           │ │
│ │任务   │ │   List)     │   + Terminal)      │ │(ArtifactsPanel)  │ │
│ │列表   │ │             │                    │ ├──────────────────┤ │
│ ├──────┤ │             │                    │ │沙盒状态           │ │
│ │工作区 │ │             │                    │ │CPU/内存指标       │ │
│ │文件树 │ │             │                    │ │网络/镜像信息      │ │
│ │      │ │             │                    │ └──────────────────┘ │
│ └──────┘ │             │                    │                      │
└──────────┴──────────────────────────────────┴───────────────────────┘
```

### 3.2 三种视图模式

| 模式 | 说明 | 布局 |
|------|------|------|
| **chat** | 纯对话模式 | 中栏全宽显示对话流 |
| **split** | 分屏模式 | 左 40% 对话 + 右 60% 代码编辑器（可拖拽分割线） |
| **code** | 代码工作室 | 中栏全宽代码编辑器，对话收起为右下角浮动按钮（FAB） |

**视图模式保护机制**（`studioViewGuard.ts`）：
- 用户手动切换视图后（`viewModeTouched = true`），流式期间不再接受服务端 view_mode 回写
- 防止 SSE 轮询把用户刚打开的分屏打回 chat 模式

### 3.3 核心组件清单

#### 页面级组件

| 文件 | 说明 |
|------|------|
| `views/StudioView.vue` | 主工作台页面（三栏布局，~1200 行） |
| `views/SharedStudioView.vue` | 只读分享查看器 |

#### 工作台组件（`components/studio/`）

| 文件 | 说明 | 关键特性 |
|------|------|---------|
| `context.ts` | provide/inject 上下文 | `StudioContextKey`：sessionId、refreshWorkspace、openFileInEditor |
| `StudioCodeCard.vue` | 对话中的代码执行卡片 | 重跑功能、ANSI 过滤、图片预览、diff 视图（workspace_edit） |
| `StudioFileTree.vue` | 工作区文件树 | 懒加载目录、右键菜单、导入数据、引用到对话 |
| `StudioWorkspaceEditor.vue` | 代码编辑器工作区 | 多标签页、冲突解决（逐 hunk accept/reject）、终端面板 |
| `StudioMonacoEditor.vue` | Monaco 编辑器封装 | 自定义 OmicHub 主题、Ctrl+S/Ctrl+Enter 快捷键 |
| `StudioMonacoDiffEditor.vue` | Monaco diff 编辑器 | 只读、自动布局 |
| `StudioTerminal.vue` | xterm.js 终端 | WebSocket 连接沙盒 PTY、自动重连、OSC 633 退出码追踪 |
| `StudioArtifactsPanel.vue` | 产物面板 | 图片缩略图、CSV 表格预览、Markdown 渲染、登记到报告中心 |
| `StudioPlanTimeline.vue` | 分析计划时间线 | 步骤标题 + 状态（pending/in_progress/done） |
| `StudioTaskUnderstanding.vue` | 任务理解展示 | 解析任务/领域/目标 |
| `ResearchToolEventCard.vue` | 研究工具事件卡片 | 文件读取、联网搜索等紧凑展示 |

#### 状态管理

| 文件 | 说明 |
|------|------|
| `stores/agentHub.ts` | 主 store：会话管理、Studio 重定向、权限、SSE 事件处理 |
| `api/studio.ts` | API 客户端：~50 个方法覆盖全部 Studio 端点 |
| `composables/useStudioRunStream.ts` | SSE 重跑代码 composable |
| `composables/useAgentChatStream.ts` | 聊天流 SSE（含 Studio 扩展事件） |

#### 工具函数

| 文件 | 说明 |
|------|------|
| `utils/studioViewGuard.ts` | 视图模式保护：防止流式期间服务端覆盖用户选择 |
| `utils/studioPresentation.ts` | 展示层辅助：任务类型推断、状态推断、工具元数据 |

### 3.4 顶栏功能按钮

| 按钮 | 功能 |
|------|------|
| 返回箭头 | 返回 AI 助手（`/ai`） |
| 智能体徽章 + 模型选择 | 显示当前绑定的 Agent 和模型，可切换 |
| Overdrive 开关 | 高性能模式切换 |
| 监督/放权模式开关 | HITL 权限模式切换 |
| 沙盒状态灯 | 实时状态（运行中/已停止/不存在）+ CPU/内存指标 |
| 提炼为 Skill | 管理员专属：将工作区脚本提炼为可复用 Skill |
| 分享 | 创建只读分享链接 |
| 打印/PDF | 导出 HTML 可打印报告 |
| 释放沙盒 | 保留工作区快照，释放容器资源 |
| 刷新 | 刷新文件树和产物列表 |
| 左栏/右栏折叠 | 收起/展开侧栏 |

### 3.5 设计令牌（CSS Variables）

`styles/tokens.css` 定义了 Studio 专用的亮色/暗色主题变量：

```css
--studio-bg / --studio-card / --studio-border
--studio-primary / --studio-primary-soft
--studio-text / --studio-text-sub
--studio-terminal / --studio-ok / --studio-warn / --studio-err
```

---

## 四、后端架构

### 4.1 分层结构

```
API 层 (studio.py:1138行)
  ↓
Service 层
  ├── studio_tools.py (1054行) — 12 个工具定义与执行
  ├── studio_capabilities.py (272行) — MCP/Skills 渐进披露
  ├── studio_approval_service.py (200行) — HITL 审批
  ├── studio_context_service.py (571行) — Context Packager
  ├── studio_sharing.py (170行) — 分享/导出
  ├── studio_skill_service.py (83行) — 提炼为 Skill
  └── studio_task_service.py (99行) — 长任务提交
  ↓
Infrastructure 层
  ├── studio/manager.py (983行) — StudioSandboxManager 单例
  ├── studio/workspace.py (231行) — 磁盘回退 + 平台文件链接
  ├── studio/paths.py (106行) — 路径安全防护
  └── studio/control_client.py (98行) — Worker→Web 控制面
  ↓
容器层
  └── sandbox_agent.py (947行) — 容器内 FastAPI 服务
```

### 4.2 沙盒容器架构

```
宿主机                                    Docker 容器
┌─────────────────────┐                ┌──────────────────────────┐
│ StudioSandboxManager│                │ sandbox-agent (FastAPI)  │
│                     │   UDS          │                          │
│  ensure_running() ──┼───────→       │  /healthz                │
│  exec()           ──┼───────→       │  /exec (NDJSON 流)       │
│  list_files()    ──┼───────→       │  /files/*                │
│  write_file()    ──┼───────→       │  /terminal (WebSocket)   │
│                     │                │  /mcp/* (MCP Builder)    │
│  bind-mount:        │                │                          │
│  /data/studio/{ws} → /workspace     │  uid=10001 (非 root)     │
│  /data/platform    → /data (只读)   │  Agg (无头 matplotlib)   │
└─────────────────────┘                └──────────────────────────┘
```

**关键设计决策**：
- 通信走 Unix Domain Socket（`/workspace/.agent.sock`），不发布端口
- 每会话独立容器，不复用跨用户 standby（bind-mount 不可安全重绑）
- 网络隔离：默认 `network_mode=none`（完全断网）；白名单模式走独立出站代理
- 容器内非 root（uid 10001），路径防护用 realpath 防逃逸

### 4.3 内置工具系统（12 个）

| 工具 | 说明 |
|------|------|
| `sandbox_execute` | 执行代码（Python/R/Bash），NDJSON 流式返回 stdout/stderr |
| `workspace_write` | 写入文件到工作区 |
| `workspace_edit` | 精确文本替换（old_string → new_string），返回 unified diff |
| `workspace_read` | 读取文件（默认前 200 行，支持分页） |
| `workspace_list` | 列出目录内容 |
| `datahub_import` | 从数据管理导入文件（软链接到 `/workspace/input/`） |
| `platform_result_import` | 从平台结果导入 |
| `artifact_register` | 登记产物到报告中心（含版本树） |
| `update_plan` | 更新分析计划步骤状态 |
| `pipeline_query` | 查询平台已有分析流程 |
| `knowledge_search` | 检索平台知识库 |
| `ask_user` | 向用户澄清（弹窗选择） |

**工具执行流程**：
1. LLM 发起 tool call → `chat_service.py` 路由到 Studio
2. 监督模式下：`StudioApprovalService` 创建审批（Redis BLPOP 等待，TTL 300s）
3. `execute_studio_tool()` 分发到对应执行器
4. `stream_studio_tool()` 包装为流式（带心跳防超时）
5. 执行结果通过 SSE `tool_output` 事件推送到前端

### 4.4 HITL（Human-in-the-Loop）审批

**需要审批的工具**：`sandbox_execute`、`workspace_write`、`workspace_edit`、`artifact_register`

**权限模式**：
- **监督模式（supervised）**：每次执行前弹出审批卡片，用户可批准/编辑/拒绝
- **放权模式（auto）**：所有工具自动执行，不等待批准

**实现**：
- `StudioApprovalService`：Redis 原子 Lua 脚本，跨进程安全
- 前端 `PendingApprovalBar`：浮动审批栏 + `ApprovalCard`/`ApprovalDrawer`

### 4.5 MCP/Skills 渐进披露

`studio_capabilities.py` 实现了按需加载机制：
- 初始只暴露 `studio_capabilities_list` 和 `studio_capability_load` 两个元工具
- AI 先查看可用能力目录，再按需加载具体 MCP Server 或 Skill
- 避免一次性注入过多工具定义导致 LLM 上下文膨胀

### 4.6 API 端点汇总

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/sessions` | 创建 Studio 会话 |
| POST | `/sessions/{id}/promote` | 升级聊天会话为 Studio |
| POST | `/sessions/from-report` | 从报告创建 Studio |
| GET | `/sessions` | 列出 Studio 会话 |
| GET | `/sessions/{id}` | 会话详情（含沙盒状态+文件+计划+能力+UI+权限+分享） |
| PATCH | `/sessions/{id}/ui` | 保存 UI 状态（视图模式/分屏比例/跟随AI） |
| POST | `/sessions/{id}/permissions` | 设置权限模式 |
| GET | `/approvals` | 列出待审批项 |
| POST | `/approvals/{id}/approve` | 批准 |
| POST | `/approvals/{id}/reject` | 拒绝 |
| POST | `/sessions/{id}/sandbox/hibernate` | 休眠沙盒 |
| POST | `/sessions/{id}/share` | 创建分享 |
| PUT | `/sessions/{id}/files/write` | 保存文件 |
| POST | `/sessions/{id}/files/edit` | 精确文本替换 |
| GET | `/sessions/{id}/files` | 目录列表 |
| GET | `/sessions/{id}/files/download` | 下载文件 |
| WS | `/sessions/{id}/terminal` | WebSocket PTY 终端 |
| POST | `/sessions/{id}/run` | 重跑代码（SSE 流） |
| GET | `/sessions/{id}/artifacts` | 列出产物 |
| POST | `/sessions/{id}/artifacts/register` | 登记到报告中心 |
| POST | `/sessions/{id}/skills/extract` | 提炼为 Skill |
| GET | `/sessions/{id}/export` | HTML 可打印报告 |

---

## 五、配置系统

### 5.1 核心配置（`data/ai/studio.yaml`）

```yaml
studio:
  enabled: true
  default_image: omichub-analysis:core-2026.07
  session:
    idle_ttl_minutes: 10        # 空闲回收
    workspace_retention_days: 7  # 工作区保留
    prewarm_on_create: true      # 创建即预热
  ui:
    default_view_mode: chat      # 默认视图
    follow_ai_default: true      # 默认跟随 AI
    hibernate_on_leave: true     # 离开即休眠
  sandbox:
    cpu: 2
    memory: 4g
    exec_timeout_seconds: 600    # 单次执行超时 10 分钟
    network:
      mode: whitelist            # 白名单网络
      allow: [conda.anaconda.org, pypi.org, ...]  # 包源域名
```

### 5.2 热重载

`StudioConfigManager` 基于 mtime 检测，配置变更自动重载，无需重启服务。

### 5.3 Agent 级 Studio 配置

每个 Agent YAML 可声明 Studio 支持：
```yaml
studio:
  enabled: true
  image: omichub-analysis:core-2026.07  # 可选，覆盖默认镜像
  default_mode: studio  # 自动进入工作台模式
```

---

## 六、数据流与状态同步

### 6.1 消息发送流程

```
用户输入 → KimiChatInput.handleSend()
  → agentHub.sendMessage()
    → POST /chat/stream (SSE)
      → chat_service 检测 session.mode == "studio"
        → _studio_runtime() 注入 Studio 工具 + 系统提示
        → LLM 返回 tool_call
          → execute_studio_tool() → sandbox-agent /exec
            → NDJSON 流 → SSE tool_output 事件
              → 前端 StudioCodeCard 渲染
```

### 6.2 视图状态保护

```
服务端 SSE 推送 ui_state → studioViewGuard.shouldApplyServerUi()
  → 流式中？→ 拒绝（防止覆盖用户操作）
  → 用户已手动切换？→ 拒绝（viewModeTouched = true）
  → 否则 → 接受
```

---

## 七、优化建议

### 7.1 前端体验优化

#### A. 首次进入体验
- **问题**：空态页面只有一句"还没有工作台会话"和返回按钮，新用户不知工作台能做什么
- **建议**：增加交互式引导或示例任务卡片（如"尝试单细胞分析"、"绘制火山图"），点击后自动创建 Studio 会话并预填提示

#### B. 视图切换动画
- **问题**：chat/split/code 三种模式切换是硬切，没有过渡动画
- **建议**：添加 CSS transition（如 split 面板的宽度变化用 `transition: width 0.3s ease`），提升视觉连贯性

#### C. 终端体验
- **问题**：终端 WebSocket 断连后用户只能看到重连提示，无法手动触发重连
- **建议**：在终端面板增加手动重连按钮；断连时保留最后可见内容（当前 xterm 已支持，但 UI 反馈不够明确）

#### D. 代码编辑器协同
- **问题**：AI 修改文件时，编辑器需要手动刷新才能看到变化
- **建议**：利用 `workspace_edit` 返回的 diff 信息，在编辑器中自动高亮 AI 的修改（类似 VS Code 的 SCM diff 视图）

#### E. 产物预览增强
- **问题**：ArtifactsPanel 只支持图片/CSV/Markdown 预览
- **建议**：增加 HTML 报告预览（iframe sandbox）、JSON 数据表格预览、PDF 预览

### 7.2 后端架构优化

#### F. 沙盒预热池
- **问题**：当前 `prewarm_on_create` 只在工作台创建时预热单个容器，高并发时仍有冷启动延迟
- **建议**：实现 per-user 预热池（维护 1-2 个 standby 容器），创建会话时直接分配而非新建

#### G. 执行超时与长任务
- **问题**：`exec_timeout_seconds: 600`（10 分钟）对大型分析可能不够
- **建议**：对已提交 Celery 长任务（`run_studio_sandbox`）支持进度回调，前端展示进度条而非只有"正在跑长任务，去倒杯咖啡？"

#### H. 网络白名单维护
- **问题**：包源域名硬编码在 `studio.yaml`，新增镜像源需要改配置重启
- **建议**：管理后台增加网络白名单配置界面，支持热更新

#### I. 资源配额
- **问题**：当前 CPU 2 核 / 内存 4G 是全局配置，无法按用户或 Agent 差异化
- **建议**：支持 Agent 级或用户级资源配额覆盖（如 VIP 用户 4 核 8G）

### 7.3 安全与稳定性

#### J. 沙盒逃逸检测
- **问题**：路径防护依赖 realpath，但没有运行时监控异常文件访问
- **建议**：在 sandbox-agent 增加文件访问审计日志，异常路径访问告警

#### K. 容器健康检查
- **问题**：当前健康检查只在 `ensure_running` 时做一次 `/healthz` 轮询
- **建议**：运行期间定期探活（如每 30s），检测到 agent 无响应时自动重启容器并通知用户

#### L. 工作区备份
- **问题**：工作区保留 7 天后直接清理，没有归档机制
- **建议**：清理前自动打包归档到对象存储，用户可在历史会话中恢复

### 7.4 功能增强

#### M. 协作编辑
- **问题**：当前工作台是单用户独占，不支持多人协作
- **建议**：利用已有的分享机制扩展为协作模式（多人共享同一 session_id 的 SSE 流）

#### N. 版本控制
- **问题**：工作区文件没有版本历史，误操作无法回退
- **建议**：对 `workspace_write` / `workspace_edit` 操作记录版本快照（可基于 git 或简单 diff 链）

#### O. 离线分析包
- **问题**：白名单模式下安装新包依赖网络，首次安装可能较慢
- **建议**：预构建常用分析场景的扩展镜像（如 `omichub-analysis:spatial`），减少运行时安装

#### P. 移动端适配
- **问题**：三栏布局在移动端完全不可用
- **建议**：至少支持 chat 模式的响应式布局（左右栏收起为抽屉，中栏全宽）

---

## 八、文件索引

### 前端关键文件

| 路径 | 行数 | 说明 |
|------|------|------|
| `frontend/src/views/StudioView.vue` | ~1200 | 主页面（三栏布局） |
| `frontend/src/components/studio/StudioCodeCard.vue` | ~400 | 代码执行卡片 |
| `frontend/src/components/studio/StudioWorkspaceEditor.vue` | ~500 | 代码编辑器工作区 |
| `frontend/src/components/studio/StudioTerminal.vue` | ~150 | xterm.js 终端 |
| `frontend/src/components/studio/StudioFileTree.vue` | ~300 | 文件树 |
| `frontend/src/components/studio/StudioArtifactsPanel.vue` | ~250 | 产物面板 |
| `frontend/src/api/studio.ts` | ~500 | API 客户端 |
| `frontend/src/stores/agentHub.ts` | ~3000 | 主 store |
| `frontend/src/utils/studioViewGuard.ts` | ~30 | 视图保护 |

### 后端关键文件

| 路径 | 行数 | 说明 |
|------|------|------|
| `src/omichub/api/v1/studio.py` | 1138 | API 路由 |
| `src/omichub/application/services/studio_tools.py` | 1054 | 工具系统 |
| `src/omichub/infrastructure/studio/manager.py` | 983 | 沙盒管理器 |
| `deploy/studio/sandbox_agent.py` | 947 | 容器内 Agent |
| `src/omichub/application/services/studio_context_service.py` | 571 | Context Packager |
| `src/omichub/application/services/studio_capabilities.py` | 272 | 渐进披露 |
| `src/omichub/application/services/studio_approval_service.py` | 200 | HITL 审批 |
| `src/omichub/infrastructure/config/studio_loader.py` | 218 | 配置加载 |
| `data/ai/studio.yaml` | 43 | 配置文件 |
| `data/ai/prompts/studio/system.md` | 35 | 系统提示词 |

### 测试文件（20+）

位于 `tests/unit/`，覆盖：计划拦截、审批服务、文件挂载、长任务、配置加载、出站代理、分享、预热、工具系统、能力披露、Skill 提炼、控制面、管理器、保留策略、平台工具、工作区、路径安全等。
