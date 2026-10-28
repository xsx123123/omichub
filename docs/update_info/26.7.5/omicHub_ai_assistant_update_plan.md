# OmicHub AI 助手模块更新计划

> 生成日期：2026-07-05
> 目标：美化编辑页面、修复保存/停用功能、增强 MCP 管理能力（参考 Cherry Studio）

---

## 一、现状问题梳理

### 1.1 编辑助手模板页面（图 4/5）

| 问题 | 现状 | 影响 |
|------|------|------|
| 布局松散 | 表单项垂直平铺，无分组卡片，视觉疲劳 | 用户难以快速定位字段 |
| 标签不对齐 | "绑定模型配置"等长标签导致输入框起始位置参差不齐 | 阅读动线混乱 |
| 头像/色值原始 | 头像与色值并排显示，色值以 `#4f8ef7` 文本裸露 | 不直观，不美观 |
| 挂载选择器笨重 | MCP/技能双栏 Transfer 组件占空间过大，"无数据"空状态简陋 | 空间利用率低 |
| 功能开关拥挤 | 开关与文字横向排列但间距不协调 | 操作体验差 |
| 缺乏视觉层次 | 所有字段权重相同，没有信息层级 | 重点不突出 |

### 1.2 保存/停用功能（图 4/5）

| 问题 | 现象 | 初步排查方向 |
|------|------|-------------|
| 保存失败 | 点击保存后提示"保存失败，请检查后端接口" | ① 请求体字段与后端 DTO 不匹配；② 必填字段校验失败；③ 接口 500；④ 权限中间件拦截 |
| 停用按钮无效 | 点击停用无响应或状态未变更 | ① 前端未绑定事件；② 后端状态字段枚举值不一致；③ 缺少 `is_active`/`status` 更新接口 |

### 1.3 MCP 管理能力（图 6 vs 图 7/8）

| 能力 | 现状（OmicHub） | 参考（Cherry Studio） | 差距 |
|------|----------------|----------------------|------|
| 配置详情 | 仅展示名称、传输、状态、工具数、预设 | 名称、描述、类型(stdio/sse)、命令、包管理源、参数、环境变量 | 缺少底层配置可视化 |
| 运行日志 | 无 | 独立日志弹窗，时间戳 + 级别(stderr/info) + 内容 | 无法排查 MCP 运行问题 |
| 状态感知 | 仅 Online/Offline 标签 | 开关控制 + 版本号 + 实时日志 | 状态反馈弱 |
| 参数编辑 | 无 | 表单式编辑命令、参数、包管理源 | 无法动态调整 |

---

## 二、更新计划

### Phase 1：前端编辑页面重构（高优先级，纯前端）

#### 2.1.1 页面结构：分组卡片式布局

将原来的平铺表单改为 5 个分组卡片，采用垂直间距 24px 分隔：

```
┌─ 基本信息卡片 ──────────────────────┐
│  头像 + 名称 + 描述                  │
├─ 模型与交互卡片 ────────────────────┤
│  绑定模型 + 分类 + 欢迎语            │
├─ 系统设定卡片 ──────────────────────┤
│  系统提示词（Textarea，可折叠）       │
├─ 能力挂载卡片 ──────────────────────┤
│  挂载 MCP（紧凑选择器）               │
│  挂载技能（紧凑选择器）               │
├─ 功能开关卡片 ──────────────────────┤
│  联网搜索 / 文件上传 / 代码执行 / 深度思考 │
└─────────────────────────────────────┘
```

#### 2.1.2 各字段具体优化

**① 头像与主题色（图 4 顶部）**

```css
/* 头像选择器 */
.avatar-picker {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  border: 2px solid var(--kimi-color-border);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  cursor: pointer;
  transition: border-color var(--t-fast) var(--ease-out);
}
.avatar-picker:hover {
  border-color: var(--kimi-color-text-primary);
}

/* 色值指示器：用圆形色块替代文本 */
.color-indicator {
  width: 20px;
  height: 20px;
  border-radius: 6px;
  background: var(--agent-theme-color);
  border: 1px solid var(--kimi-color-border);
  cursor: pointer;
}
```

- 头像点击弹出 Emoji 选择器（限制 24px 展示）
- 色值不再显示 `#4f8ef7` 文本，改为圆形色块，点击唤起 Color Picker

**② 标签与输入框对齐**

采用**上下结构**（推荐）或**固定 100px 左标签右输入**结构：

```css
/* 上下结构：标签在上，输入框在下，适合移动端和紧凑桌面端 */
.form-row {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 16px;
}
.form-label {
  font-size: 13px;
  font-weight: 500;
  color: var(--kimi-color-text-primary);
}
.form-input {
  height: 36px;
  padding: 0 12px;
  border: 1px solid var(--kimi-color-border);
  border-radius: 8px;
  font-size: 14px;
  background: var(--kimi-color-surface);
  transition: border-color var(--t-fast) var(--ease-out);
}
.form-input:focus {
  border-color: var(--kimi-color-text-primary);
  outline: none;
}
```

**③ 系统设定（Textarea）**

- 默认展示 3 行，支持展开/收起
- 右下角显示字符计数（如 `124/2000`）
- 添加"恢复默认"按钮

```css
.system-prompt-area {
  min-height: 80px;
  max-height: 300px;
  resize: vertical;
  padding: 12px;
  border: 1px solid var(--kimi-color-border);
  border-radius: 10px;
  font-size: 14px;
  line-height: 1.6;
  background: var(--kimi-color-surface);
  font-family: var(--kimi-font-sans);
}
```

**④ 挂载 MCP / 技能选择器（替代笨重 Transfer）**

改为**紧凑 Tag 选择器 + 下拉面板**模式：

```
挂载 MCP                          [+ 添加]
┌─────────────────────────────────────┐
│  🧬 literature  [x]  🧪 genome [x]  │
│  💻 code [x]                        │
└─────────────────────────────────────┘
```

点击"+ 添加"弹出下拉面板（复选框列表），已选项以可删除 Tag 展示。

```css
.mcp-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border-radius: 6px;
  background: color-mix(in srgb, var(--kimi-chart-1) 10%, transparent);
  color: var(--kimi-chart-1);
  font-size: 12px;
  font-weight: 500;
}
.mcp-tag .remove {
  opacity: 0;
  transition: opacity var(--t-fast);
}
.mcp-tag:hover .remove {
  opacity: 1;
}
```

**⑤ 功能开关**

改为独立开关行，每行一个 Switch + 标签 + 描述：

```
┌─────────────────────────────────────┐
│  [Switch]  联网搜索                 │
│            允许助手访问互联网获取最新信息 │
├─────────────────────────────────────┤
│  [Switch]  文件上传                 │
│            允许用户上传文件进行分析   │
└─────────────────────────────────────┘
```

```css
.switch-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  padding: 12px 0;
  border-bottom: 1px solid var(--kimi-color-border);
}
.switch-row:last-child {
  border-bottom: none;
}
.switch-info {
  flex: 1;
}
.switch-title {
  font-size: 14px;
  font-weight: 500;
  color: var(--kimi-color-text-primary);
}
.switch-desc {
  font-size: 12px;
  color: var(--kimi-color-text-tertiary);
  margin-top: 2px;
}
```

#### 2.1.3 页面底部操作栏

固定底部操作栏（sticky），避免长表单滚动后找不到保存按钮：

```
┌─────────────────────────────────────┐
│  [取消]                    [保存]   │
└─────────────────────────────────────┘
```

- 保存按钮在表单无变更时置灰（`disabled`），有变更时高亮
- 保存中显示 Loading 状态

---

### Phase 2：保存/停用接口修复（高优先级，前后端联调）

#### 2.2.1 保存失败排查清单

**前端排查：**

1. [ ] 打开浏览器 DevTools → Network，确认保存请求的 **URL、Method、Status Code**
2. [ ] 检查请求体 `payload` 是否包含后端需要的全部字段：
   ```json
   {
     "id": "agent_xxx",
     "name": "通用助手",
     "description": "...",
     "avatar": "🤖",
     "theme_color": "#4f8ef7",
     "model_config_id": "model_xxx",
     "category": "通用",
     "welcome_message": "你好！...",
     "system_prompt": "你是 OmicHub...",
     "attached_mcp_ids": ["mcp_lit", "mcp_genome"],
     "attached_skill_ids": [],
     "features": {
       "web_search": false,
       "file_upload": false,
       "code_execution": false,
       "deep_thinking": false
     }
   }
   ```
3. [ ] 确认字段命名与后端 DTO 完全一致（注意驼峰/下划线）
4. [ ] 检查请求头是否携带 `Authorization: Bearer <token>`
5. [ ] 检查是否有字段为空但后端标记为 `@NotNull`/`required`

**后端排查：**

1. [ ] 查看后端日志，定位保存接口的异常堆栈
2. [ ] 检查 Agent 实体是否有字段长度限制（如 `system_prompt` 超过 `TEXT` 容量）
3. [ ] 检查 `attached_mcp_ids` 外键约束：删除 MCP 后，关联的 Agent 是否导致更新失败
4. [ ] 检查乐观锁（`version` 字段）是否导致并发更新失败
5. [ ] 检查权限：当前用户是否有权限修改该 Agent

**修复方案：**

```python
# 后端伪代码：Agent Update 接口
def update_agent(agent_id, payload, user):
    agent = Agent.query.get(agent_id)
    if not agent:
        raise NotFound("Agent not found")
    if agent.owner_id != user.id and not user.is_admin:
        raise Forbidden("No permission")

    # 允许部分更新，未传字段保持原值
    for field in ['name', 'description', 'avatar', 'theme_color', 
                  'model_config_id', 'category', 'welcome_message', 
                  'system_prompt', 'features']:
        if field in payload:
            setattr(agent, field, payload[field])

    # MCP 关联：先清后加，或对比 diff
    if 'attached_mcp_ids' in payload:
        agent.mcp_servers = [MCP.query.get(i) for i in payload['attached_mcp_ids']]

    db.session.commit()
    return agent.to_dict()
```

#### 2.2.2 停用按钮修复

**问题定位：**

1. [ ] 检查前端是否绑定了 `onClick` 事件（可能只绑定了"删除"，漏了"停用"）
2. [ ] 检查停用调用的 API 地址是否正确（如 `/api/agents/{id}/deactivate` vs `/api/agents/{id}`）
3. [ ] 检查后端是否有独立的 `toggle_status` 接口，或是否复用 `PUT /api/agents/{id}` 但缺少 `status` 字段处理

**修复方案：**

前端：
```tsx
const handleToggleStatus = async () => {
  const newStatus = agent.status === 'active' ? 'inactive' : 'active';
  try {
    await api.patch(`/agents/${agent.id}/status`, { status: newStatus });
    message.success(newStatus === 'active' ? '已启用' : '已停用');
    refresh();
  } catch (e) {
    message.error('操作失败：' + e.message);
  }
};
```

后端：
```python
@app.patch('/api/agents/<id>/status')
def toggle_agent_status(id):
    agent = Agent.query.get_or_404(id)
    agent.status = request.json.get('status')  # 'active' | 'inactive'
    agent.updated_at = datetime.now()
    db.session.commit()
    return {'code': 0, 'data': agent.to_dict()}
```

---

### Phase 3：MCP 管理增强（中优先级，参考 Cherry Studio）

#### 2.3.1 MCP 详情配置抽屉/页面（参考图 7）

点击 MCP 服务行或"配置"按钮，弹出右侧抽屉（Drawer）或进入详情页，展示：

```
┌─ MCP 配置 ─────────────────────────┐
│  🔌 mcp    [v1.28.0]  [日志] [删除] │
├─────────────────────────────────────┤
│  通用 / 工具(1) / 提示(1) / 资源    │  ← Tab 切换
├─────────────────────────────────────┤
│  * 名称                             │
│  ┌─────────────────────────────┐  │
│  │ mcp                         │  │
│  └─────────────────────────────┘  │
│  描述                               │
│  ┌─────────────────────────────┐  │
│  │ 描述                        │  │
│  └─────────────────────────────┘  │
│  * 类型                             │
│  ┌─────────────────────────────┐  │
│  │ 标准输入 / 输出 (stdio) ▼   │  │
│  └─────────────────────────────┘  │
│  * 命令                             │
│  ┌─────────────────────────────┐  │
│  │ uvx                         │  │
│  └─────────────────────────────┘  │
│  包管理源 ?                         │
│  ○ 默认  ○ 中科大  ○ 阿里云 ...  │
│  参数 ?                             │
│  ┌─────────────────────────────┐  │
│  │ mcp-server-fetch            │  │
│  └─────────────────────────────┘  │
│  环境变量                           │
│  ┌─────────────────────────────┐  │
│  │ KEY=VALUE 格式，每行一个    │  │
│  └─────────────────────────────┘  │
│                                     │
│              [取消]  [保存]         │
└─────────────────────────────────────┘
```

**字段说明：**

| 字段 | 类型 | 说明 |
|------|------|------|
| 名称 | string | MCP 服务唯一标识，如 `mcp`、`literature` |
| 版本 | string | 只读，从服务元数据读取，如 `1.28.0` |
| 描述 | string | 可选，服务用途说明 |
| 类型 | enum | `stdio`（标准输入输出）或 `sse`（Server-Sent Events） |
| 命令 | string | 启动命令，如 `uvx`、`npx`、`python` |
| 参数 | string | 传递给命令的参数，如 `mcp-server-fetch` |
| 包管理源 | enum | `default`、`tsinghua`、`aliyun`、`ustc`、`huawei`、`tencent` |
| 环境变量 | textarea | `KEY=VALUE` 格式，每行一个，用于注入 `env` |
| 工作目录 | string | 可选，MCP 进程的工作目录 |
| 超时时间 | number | 可选，默认 30s |

**前端实现（Drawer）：**

```tsx
<Drawer
  title={
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <span>{mcp.name}</span>
      <Tag size="small">{mcp.version}</Tag>
      <Button type="text" size="small" icon={<FileTextOutlined />} onClick={openLogs}>
        日志
      </Button>
    </div>
  }
  width={520}
  open={visible}
  onClose={onClose}
>
  <Tabs items={[
    { key: 'general', label: '通用', children: <GeneralForm mcp={mcp} /> },
    { key: 'tools', label: `工具 (${mcp.tools.length})`, children: <ToolsList tools={mcp.tools} /> },
    { key: 'prompts', label: `提示 (${mcp.prompts.length})`, children: <PromptsList prompts={mcp.prompts} /> },
    { key: 'resources', label: '资源', children: <ResourcesList /> },
  ]} />
</Drawer>
```

#### 2.3.2 MCP 运行日志查看器（参考图 8）

点击 MCP 卡片/行上的"日志"按钮，弹出日志弹窗：

```
┌─ 日志 ─────────────────────────────┐
│  3:21:26 PM  [stderr]  Installed 44 packages in 54ms  │
│  3:21:30 PM  [info]    Server connected                │
│  3:21:30 PM  [info]    Server activated                │
│  ...                                                   │
└─────────────────────────────────────┘
```

**日志数据结构：**

```typescript
interface MCPLogEntry {
  timestamp: string;      // ISO 8601，前端格式化为本地时间
  level: 'info' | 'stderr' | 'error' | 'warn';
  message: string;
  source?: string;        // 可选，来源模块
}
```

**前端样式：**

```css
.log-entry {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 8px 12px;
  font-size: 13px;
  font-family: var(--kimi-font-mono);
  border-bottom: 1px solid var(--kimi-color-border);
}
.log-entry:last-child {
  border-bottom: none;
}
.log-time {
  color: var(--kimi-color-text-quaternary);
  white-space: nowrap;
  flex-shrink: 0;
}
.log-level {
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 500;
  flex-shrink: 0;
}
.log-level.info {
  background: color-mix(in srgb, var(--kimi-chart-1) 15%, transparent);
  color: var(--kimi-chart-1);
}
.log-level.stderr {
  background: color-mix(in srgb, var(--kimi-chart-2) 15%, transparent);
  color: var(--kimi-chart-2);
}
.log-level.error {
  background: color-mix(in srgb, var(--kimi-color-danger) 15%, transparent);
  color: var(--kimi-color-danger);
}
.log-message {
  color: var(--kimi-color-text-primary);
  word-break: break-all;
}
```

**后端实现：**

```python
# 方案 A：WebSocket 实时推送（推荐，适合长连接 MCP）
# 方案 B：轮询接口（简单实现）

@app.get('/api/mcp/<id>/logs')
def get_mcp_logs(id, tail: int = 100):
    # 获取最近 N 条日志
    mcp = MCPService.query.get_or_404(id)
    logs = MCPLog.filter_by(service_id=id).order_by(desc(MCPLog.timestamp)).limit(tail).all()
    return {
        'code': 0,
        'data': [{
            'timestamp': log.timestamp.isoformat(),
            'level': log.level,
            'message': log.message
        } for log in reversed(logs)]  # 按时间正序返回
    }
```

**日志采集方案：**

| 方案 | 原理 | 优点 | 缺点 |
|------|------|------|------|
| A. 重定向 stderr/stdout | 启动 MCP 时捕获管道输出 | 简单，无侵入 | 需要持久化进程 |
| B. MCP SDK 回调 | 使用 `mcp.client` 的日志回调 | 结构化，可过滤 | 依赖 SDK 支持 |
| C. 进程 wrapper | 用 `subprocess` 包装，实时读取 | 通用性强 | 需要维护进程生命周期 |

推荐 **方案 C**（subprocess wrapper），在 Python 中：

```python
import subprocess
import threading

class MCPProcess:
    def __init__(self, command, args, env):
        self.process = subprocess.Popen(
            [command] + args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env={**os.environ, **env},
            text=True
        )
        self._start_log_threads()

    def _start_log_threads(self):
        def read_stream(stream, level):
            for line in iter(stream.readline, ''):
                MCPLog.create(
                    service_id=self.service_id,
                    level=level,
                    message=line.strip(),
                    timestamp=datetime.now()
                )

        threading.Thread(target=read_stream, args=(self.process.stdout, 'info'), daemon=True).start()
        threading.Thread(target=read_stream, args=(self.process.stderr, 'stderr'), daemon=True).start()
```

#### 2.3.3 MCP 列表页增强（图 6）

在现有列表基础上增加：

1. **状态开关**：每行右侧添加 Switch，可直接启用/停用 MCP 服务
2. **版本标签**：在名称旁展示版本号（如 `mcp 1.28.0`）
3. **日志入口**：操作列增加"日志"图标按钮
4. **配置入口**：操作列增加"配置"图标按钮，点击打开详情 Drawer
5. **测试连接**：操作列增加"测试"按钮，点击后后端尝试连接 MCP，返回结果 toast

```
服务              传输      状态      工具数   预设   操作
─────────────────────────────────────────────────────────────
▼ 🧬 literature   builtin   [●]Offline  1      是    [日志] [配置] [测试]
  文献检索 MCP...

  内部工具 (1)
  ─────────────────────────────────────────────────

🧪 genome        builtin   [●]Offline  2      是    [日志] [配置] [测试]
基因组工具 MCP...
```

---

### Phase 4：数据模型与接口变更（后端）

#### 2.4.1 Agent 模型扩展

```python
class Agent(Base):
    __tablename__ = 'agents'

    id = Column(String(36), primary_key=True)
    name = Column(String(100), nullable=False)
    description = Column(String(500))
    avatar = Column(String(10), default='🤖')        # emoji
    theme_color = Column(String(7), default='#4f8ef7') # hex color

    # 模型配置
    model_config_id = Column(String(36), ForeignKey('model_configs.id'))
    category = Column(String(50), default='通用')
    welcome_message = Column(String(500))
    system_prompt = Column(Text)

    # 功能开关（JSON 存储）
    features = Column(JSON, default={
        'web_search': False,
        'file_upload': False,
        'code_execution': False,
        'deep_thinking': False
    })

    # 关联
    mcp_servers = relationship('MCPService', secondary='agent_mcp', backref='agents')
    skills = relationship('Skill', secondary='agent_skill', backref='agents')

    # 状态
    status = Column(String(20), default='active')  # active | inactive
    is_preset = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
```

#### 2.4.2 MCP Service 模型扩展

```python
class MCPService(Base):
    __tablename__ = 'mcp_services'

    id = Column(String(36), primary_key=True)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(String(500))
    version = Column(String(20))

    # 配置
    transport = Column(String(20), default='stdio')  # stdio | sse
    command = Column(String(200))                    # 如 uvx, npx
    args = Column(JSON, default=[])                  # 参数列表
    env = Column(JSON, default={})                   # 环境变量
    working_dir = Column(String(500))
    timeout = Column(Integer, default=30)

    # 包管理源（仅对 stdio 类型有效）
    registry = Column(String(50), default='default')  # default | tsinghua | aliyun ...

    # 状态
    status = Column(String(20), default='offline')   # online | offline | error
    is_enabled = Column(Boolean, default=True)
    is_preset = Column(Boolean, default=False)

    # 元数据（从服务 discover 获取）
    tools = Column(JSON, default=[])
    prompts = Column(JSON, default=[])
    resources = Column(JSON, default=[])

    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
```

#### 2.4.3 MCP 日志表

```python
class MCPLog(Base):
    __tablename__ = 'mcp_logs'

    id = Column(Integer, primary_key=True, autoincrement=True)
    service_id = Column(String(36), ForeignKey('mcp_services.id'), index=True)
    timestamp = Column(DateTime, default=datetime.now, index=True)
    level = Column(String(20), default='info')  # info | stderr | error | warn
    message = Column(Text, nullable=False)
    source = Column(String(100))  # stdout | stderr | internal
```

**索引建议：**
- `service_id + timestamp` 联合索引，加速日志查询
- 日志表数据量大，考虑按时间分表或自动清理（保留 7 天）

---

### Phase 5：交互与状态管理（前端）

#### 2.5.1 表单状态管理

```typescript
interface AgentFormState {
  // 基本信息
  name: string;
  description: string;
  avatar: string;
  themeColor: string;

  // 模型
  modelConfigId: string;
  category: string;
  welcomeMessage: string;

  // 系统设定
  systemPrompt: string;

  // 挂载
  attachedMcpIds: string[];
  attachedSkillIds: string[];

  // 功能开关
  features: {
    webSearch: boolean;
    fileUpload: boolean;
    codeExecution: boolean;
    deepThinking: boolean;
  };
}

// 使用 useReducer 或 zustand 管理复杂表单状态
// 实现 dirty check：对比初始值和当前值，控制保存按钮状态
```

#### 2.5.2 自动保存草稿（可选增强）

- 表单变更后 3 秒无操作，自动保存到 `localStorage`
- 页面刷新后恢复草稿，提示"检测到未保存的更改，是否恢复？"

#### 2.5.3  MCP 实时状态

- 列表页每 30 秒轮询一次 MCP 状态，或 WebSocket 推送
- 状态变更时，行级 toast 提示（如 `literature 服务已上线`）

---

## 三、实施排期

| 阶段 | 内容 | 预估工时 | 依赖 |
|------|------|----------|------|
| Phase 1 | 编辑页面 UI 重构（分组卡片、选择器、开关） | 1.5 天 | 无 |
| Phase 2.1 | 保存接口联调（前后端字段对齐） | 0.5 天 | Phase 1 |
| Phase 2.2 | 停用按钮修复 | 0.5 天 | Phase 1 |
| Phase 3.1 | MCP 详情配置 Drawer | 1 天 | 无 |
| Phase 3.2 | MCP 日志采集与展示 | 1.5 天 | Phase 3.1 |
| Phase 3.3 | MCP 列表页增强（开关、测试、日志入口） | 0.5 天 | Phase 3.1 |
| Phase 4 | 后端模型迁移 + 接口开发 | 1.5 天 | Phase 2+3 |
| Phase 5 | 联调测试 + 边界 case 处理 | 1 天 | 全部 |
| **总计** | | **~7 天** | |

---

## 四、验收标准

### 4.1 编辑页面
- [ ] 表单分为 5 个分组卡片，视觉层次清晰
- [ ] 头像点击可切换 emoji，色值以圆形色块展示
- [ ] 系统设定支持展开/收起，显示字符计数
- [ ] MCP/技能挂载以 Tag 形式展示，添加/删除流畅
- [ ] 功能开关每行独立，含标题和描述
- [ ] 底部操作栏固定，保存按钮随表单变更状态切换

### 4.2 保存/停用
- [ ] 编辑任意字段后点击保存，3 秒内返回成功，无报错
- [ ] 保存失败后，前端展示具体错误信息（而非笼统"检查后端接口"）
- [ ] 停用按钮点击后，Agent 状态实时切换，列表页同步更新

### 4.3 MCP 管理
- [ ] 点击 MCP 行"配置"按钮，弹出详情 Drawer，展示名称/版本/类型/命令/参数/包管理源
- [ ] 配置可修改并保存，保存后 MCP 服务自动重启（或提示手动重启）
- [ ] 点击"日志"按钮，弹出日志弹窗，展示最近 100 条日志
- [ ] 日志按时间正序排列，stderr 红色标签，info 蓝色标签
- [ ] MCP 列表页可直接开关启用/停用，状态实时反馈
- [ ] 点击"测试"按钮，5 秒内返回连接结果（成功/失败 + 错误信息）

---

## 五、风险与回滚

| 风险 | 影响 | 应对 |
|------|------|------|
| 后端模型变更导致旧数据不兼容 | 高 | 编写 Alembic 迁移脚本，新字段设默认值；保留旧字段兼容期 1 个版本 |
| MCP 日志表数据膨胀 | 中 | 设置自动清理策略（保留 7 天），或按服务分表 |
| 前端大改引入新 Bug | 中 | 保留旧版组件代码（注释或分支），2 周内可快速回滚 |
| WebSocket 日志实时推送实现复杂 | 低 | 先用轮询方案（5 秒/次），后续迭代升级 |

---

*计划由 Kimi 生成，可直接作为 Sprint 任务拆解交付开发团队。*
