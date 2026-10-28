# OmicHub MCP Builder 自生成框架设计文档（完整版）

> **最后更新**：2026-07-29 22:03 +08:00  
> **适用范围**：MCP 注册/发现/调用、沙箱隔离、AI 代码生成、实验性 MCP 生命周期管理、版本管理、审核流程

---

## 目录

1. [现有架构覆盖度分析](#1-现有架构覆盖度分析)
2. [数据库 Schema 扩展](#2-数据库-schema-扩展)
3. [MCP Builder Agent 配置与 Prompt](#3-mcp-builder-agent-配置与-prompt)
4. [版本管理与迭代方案](#4-版本管理与迭代方案)
5. [审核流程设计](#5-审核流程设计)
6. [前端管理页面设计](#6-前端管理页面设计)
7. [完整实施路径](#7-完整实施路径)
8. [关键设计决策](#8-关键设计决策)
9. [查漏补缺](#9-查漏补缺)
10. [总结](#10-总结)

---

## 1. 现有架构覆盖度分析

### 1.1 已具备的能力（直接复用）

| 能力 | 现有组件 | 复用方式 |
|------|---------|---------|
| 隔离运行环境 | `StudioSandboxManager` + Docker + UDS | 新增 `/mcp/start` 端点，容器内启 SSE Server |
| LLM 代码生成 | `ProviderManager` + `deepseek-v4-pro` | Agent 直接调用，temperature=0.2 |
| 网络搜索 | Egress Proxy 白名单 | 允许 `duckduckgo.com`, `serpapi.com`, `github.com` 等 |
| MCP 注册/调用 | `MCPService` + `MCPClient` | 新增 `pool` / `expires_at` 字段 |
| 安全校验 | `validate_stdio_command()` + `validate_sse_url()` | 扩展 AST 静态检查 |
| 用户隔离 | Agent YAML `mcp_ids` + per-user 挂载 | 扩展为 `mcp_visibility` 表 |
| 执行引擎 | LangGraph ReAct | Agent 配置 `engine: langgraph` |
| 日志审计 | `mcp_logs` 表 | 扩展 `source='builder'` 分类 |
| 热加载 | `MCPClient` 每次新建 session | **无需改动，注册立即可用** |

### 1.2 缺失组件清单

| # | 缺失组件 | 优先级 | 复杂度 | 说明 |
|---|---------|--------|--------|------|
| 1 | **MCP 版本管理** | P0 | 中 | 现有 `mcp_servers` 无版本字段，无历史记录 |
| 2 | **MCP 生成记录表** | P0 | 低 | 追踪"谁、何时、用什么 Prompt、生成什么代码" |
| 3 | **审核状态机** | P0 | 中 | `draft` → `pending_review` → `approved` → `published` |
| 4 | **MCP Builder Agent Prompt** | P0 | 中 | 需精心设计 Planning → Search → Code → Test → Doc 流程 |
| 5 | **沙箱 MCP 端点** | P0 | 中 | `sandbox_agent.py` 增加 `/mcp/start` `/mcp/stop` `/mcp/test` |
| 6 | **AST 静态检查器** | P1 | 中 | 白名单 import + 危险调用检测 |
| 7 | **测试数据管理** | P1 | 低 | 测试用例/期望输出存储 |
| 8 | **构建文档生成** | P1 | 低 | Markdown 文档自动写入 `/workspace/docs/` |
| 9 | **前端管理页面** | P1 | 中 | Admin 页面：开关、审核队列、版本对比 |
| 10 | **Celery 定时清理** | P1 | 低 | 过期实验 MCP 自动注销 + 容器销毁 |

---

## 2. 数据库 Schema 扩展

### 2.1 新增表

```sql
-- ============================================
-- 1. mcp_builds: MCP 生成构建记录（核心）
-- ============================================
CREATE TABLE mcp_builds (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id),
    
    -- 需求与规划
    requirement     TEXT NOT NULL,           -- 用户原始需求
    plan_summary    TEXT,                    -- AI 规划的实现方案摘要
    search_queries  JSONB DEFAULT '[]',      -- 联网搜索的查询记录
    search_results  JSONB DEFAULT '[]',      -- 搜索结果摘要
    
    -- 生成产物
    generated_code  TEXT,                    -- 生成的完整代码
    runtime         VARCHAR(20) DEFAULT 'python',
    safety_report   JSONB,                   -- AST 检查结果 {passed, violations[], warnings[]}
    
    -- 版本关联
    mcp_server_id   UUID REFERENCES mcp_servers(id),  -- 关联的 MCP Server
    version         VARCHAR(20) DEFAULT '1.0.0',
    parent_build_id UUID REFERENCES mcp_builds(id),   -- 迭代来源（用于版本链）
    
    -- 状态流转
    status          VARCHAR(30) DEFAULT 'planning' 
                    CHECK (status IN ('planning', 'coding', 'testing', 'reviewing', 'approved', 'rejected', 'published', 'deprecated')),
    
    -- 测试
    test_cases      JSONB DEFAULT '[]',      -- 测试用例 [{input, expected, actual, passed}]
    test_passed     BOOLEAN,
    
    -- 文档
    build_doc       TEXT,                    -- 构建文档（Markdown）
    architecture_doc TEXT,                   -- 架构文档
    
    -- 元数据
    model_used      VARCHAR(50),             -- 使用的模型
    tokens_consumed INTEGER,
    generation_time_ms INTEGER,
    
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_mcp_builds_user ON mcp_builds(user_id);
CREATE INDEX idx_mcp_builds_status ON mcp_builds(status);
CREATE INDEX idx_mcp_builds_server ON mcp_builds(mcp_server_id);

-- ============================================
-- 2. mcp_versions: MCP 版本历史
-- ============================================
CREATE TABLE mcp_versions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    mcp_server_id   UUID NOT NULL REFERENCES mcp_servers(id) ON DELETE CASCADE,
    build_id        UUID REFERENCES mcp_builds(id),
    
    version         VARCHAR(20) NOT NULL,
    version_tag     VARCHAR(50),             -- e.g. "v1.2.0-beta"
    is_major        BOOLEAN DEFAULT FALSE,   -- 是否大版本
    
    code_snapshot   TEXT,                    -- 代码快照
    tools_snapshot  JSONB,                   -- tools/list 结果快照
    changelog       TEXT,                    -- 变更说明
    
    created_by      UUID REFERENCES users(id),
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_mcp_versions_server ON mcp_versions(mcp_server_id);
CREATE UNIQUE INDEX idx_mcp_versions_unique ON mcp_versions(mcp_server_id, version);

-- ============================================
-- 3. mcp_visibility: 用户级 MCP 可见性（细粒度隔离）
-- ============================================
CREATE TABLE mcp_visibility (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    mcp_server_id   UUID NOT NULL REFERENCES mcp_servers(id) ON DELETE CASCADE,
    user_id         UUID NOT NULL REFERENCES users(id),
    
    access_level    VARCHAR(20) DEFAULT 'read' 
                    CHECK (access_level IN ('none', 'read', 'execute', 'admin')),
    
    granted_by      UUID REFERENCES users(id),  -- 谁授权的
    granted_at      TIMESTAMP DEFAULT NOW(),
    expires_at      TIMESTAMP,                  -- NULL 表示永久
    
    UNIQUE(mcp_server_id, user_id)
);

CREATE INDEX idx_mcp_visibility_user ON mcp_visibility(user_id);

-- ============================================
-- 4. mcp_reviews: 审核记录
-- ============================================
CREATE TABLE mcp_reviews (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    build_id        UUID NOT NULL REFERENCES mcp_builds(id),
    reviewer_id     UUID NOT NULL REFERENCES users(id),
    
    decision        VARCHAR(20) CHECK (decision IN ('approved', 'rejected', 'request_changes')),
    comment         TEXT,
    
    created_at      TIMESTAMP DEFAULT NOW()
);

-- ============================================
-- 5. system_settings: 全局开关（新增行）
-- ============================================
INSERT INTO system_settings (key, value, description) VALUES
('mcp_builder_enabled', 'true', '是否启用 MCP Builder 功能'),
('mcp_builder_requires_review', 'true', 'MCP 发布是否需要审核'),
('mcp_builder_max_per_user', '5', '每用户最大实验 MCP 数量'),
('mcp_builder_default_ttl_hours', '24', '实验 MCP 默认 TTL'),
('mcp_builder_allowed_models', '["deepseek-v4-pro"]', '允许用于 MCP 生成的模型');
```

### 2.2 现有表扩展

```sql
-- mcp_servers 表扩展
ALTER TABLE mcp_servers
    ADD COLUMN IF NOT EXISTS pool VARCHAR(20) DEFAULT 'production'
        CHECK (pool IN ('production', 'experimental', 'deprecated')),
    ADD COLUMN IF NOT EXISTS expires_at TIMESTAMP NULL,
    ADD COLUMN IF NOT EXISTS created_by UUID REFERENCES users(id),
    ADD COLUMN IF NOT EXISTS current_version VARCHAR(20) DEFAULT '1.0.0',
    ADD COLUMN IF NOT EXISTS generation_meta JSONB NULL,  -- {build_id, model, safety_report}
    ADD COLUMN IF NOT EXISTS review_status VARCHAR(20) DEFAULT 'approved'
        CHECK (review_status IN ('draft', 'pending', 'approved', 'rejected')),
    ADD COLUMN IF NOT EXISTS is_template BOOLEAN DEFAULT FALSE;  -- 是否作为模板供其他用户复用

-- mcp_logs 表扩展（增加 source 枚举值）
-- 已有 source 字段，增加 'builder' 作为有效值
```

---

## 3. MCP Builder Agent 配置与 Prompt

### 3.1 Agent 配置 (`data/ai/mcp_builder.yaml`)

```yaml
agent_id: agent-mcp-builder
name: MCP 构建师
description: 根据用户需求自动规划、搜索、生成、测试和部署 MCP Server

# 使用性能最好的模型进行代码生成
model: deepseek-v4-pro
temperature: 0.2
max_tokens: 8000

features:
  engine: langgraph
  max_tool_loops: 15          # 构建流程较长，放宽循环限制
  enable_web_search: true     # 允许联网搜索

# 工具包：workspace（文件操作）+ memory（上下文记忆）
tool_packs: [workspace, memory]

# Studio 沙箱配置
studio:
  enabled: true
  default_mode: studio
  runtime_profile: analysis-core
  # 构建专用沙箱需要更长的超时
  exec_timeout_seconds: 1200

# 不预绑定任何 MCP，构建过程中动态注册
mcp_ids: []

# 构建产物存储路径
build_output_dir: /workspace/mcp-builds
```

### 3.2 核心 Prompt (`data/ai/prompts/mcp_builder.md`)

````markdown
# 角色定义

你是 OmicHub 平台的 **MCP 构建师 (MCP Builder)**。你的职责是根据用户的自然语言需求，自动完成 MCP Server 的完整生命周期：规划 → 搜索 → 编码 → 测试 → 文档 → 部署。

你具备以下能力：
- **规划分析**：将模糊需求拆解为可执行的实现方案
- **联网搜索**：获取 API 文档、开源实现参考、最佳实践
- **代码生成**：编写符合 MCP 协议的高质量 Python/Node.js 代码
- **沙箱测试**：在隔离容器中部署并验证功能
- **文档编写**：自动生成架构文档和使用说明

---

## 工作流程（必须严格按顺序执行）

### Phase 1: 需求理解与规划 (PLANNING)

当用户提出需求时，首先进行深度分析：

1. **需求澄清**：如果需求模糊，向用户提出 1-3 个澄清问题
2. **能力映射**：判断该需求是否需要：
   - 外部 API 调用（需要网络权限）
   - 文件系统操作（需要路径权限）
   - 纯计算/数据处理（无需外部依赖）
3. **技术选型**：
   - 运行环境：Python（默认，推荐）或 Node.js
   - 传输方式：STDIO（默认）或 SSE
   - 依赖包：仅从白名单中选择

输出格式：
```json
{
  "phase": "planning",
  "requirement_summary": "用户需要一个能查询 PubMed 文献的 MCP 工具",
  "clarification_questions": ["是否需要摘要提取？", "返回格式偏好 JSON 还是 Markdown？"],
  "technical_decisions": {
    "runtime": "python",
    "transport": "stdio",
    "dependencies": ["httpx", "xml.etree.ElementTree"],
    "needs_network": true,
    "needs_filesystem": false
  },
  "implementation_plan": [
    "1. 使用 NCBI E-utilities API 查询 PubMed",
    "2. 实现 search 和 fetch 两个工具",
    "3. 参数验证使用 Pydantic",
    "4. 错误处理覆盖 API 限流和超时"
  ]
}
```

### Phase 2: 信息搜索 (RESEARCH)

如果需求涉及外部 API、第三方服务或不熟悉的领域，执行联网搜索：

允许的搜索目标：
- 官方 API 文档（如 NCBI、OpenWeather、GitHub API）
- Python/Node.js SDK 文档
- MCP SDK 最新规范 (modelcontextprotocol.io)
- 开源参考实现 (GitHub)

搜索后总结关键信息，记录到 `search_results`。

### Phase 3: 代码生成 (CODING)

基于规划和搜索结果，生成完整的 MCP Server 代码。

**代码规范（必须遵守）**：

1. **协议合规**：
   - 必须实现 `tools/list` handler，返回完整的 JSON Schema
   - 必须实现 `tools/call` handler，路由到具体工具函数
   - 使用 `mcp.server.Server` 或 `FastMCP`

2. **安全红线（绝对禁止）**：
   - 禁止 `os.system`, `subprocess`, `eval`, `exec`, `compile`
   - 禁止 `pickle`, `marshal`, `ctypes`
   - 禁止 `importlib`, `__import__`
   - 禁止访问 `/etc`, `/proc`, `/sys`, `/root`
   - 禁止未声明的网络请求（仅允许白名单域名）

3. **代码结构**：
```python
#!/usr/bin/env python3
"""
MCP Server: {name}
Generated by: MCP Builder
Version: 1.0.0
"""

__exp_mcp_generated__ = True

from mcp.server import Server
from mcp.types import Tool, TextContent
import json
import httpx

# ============ 配置 ============
DEFAULT_TIMEOUT = 30
ALLOWED_DOMAINS = ["api.example.com"]  # 显式声明允许访问的域名

# ============ 工具定义 ============
TOOLS = [
    Tool(
        name="tool_name",
        description="工具描述",
        inputSchema={
            "type": "object",
            "properties": {...},
            "required": [...]
        }
    )
]

# ============ 业务逻辑 ============
async def handle_tool_name(args: dict) -> list:
    """工具实现"""
    try:
        # 实现逻辑
        return [TextContent(type="text", text=json.dumps(result))]
    except Exception as e:
        return [TextContent(type="text", text=json.dumps({"error": str(e)}))]

# ============ MCP 协议处理 ============
server = Server("{name}")

@server.list_tools()
async def list_tools() -> list:
    return TOOLS

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list:
    if name == "tool_name":
        return await handle_tool_name(arguments)
    raise ValueError(f"Unknown tool: {name}")

# ============ 入口 ============
if __name__ == "__main__":
    import asyncio
    from mcp.server.stdio import stdio_server
    
    async def main():
        async with stdio_server(server) as (read, write):
            await server.run(read, write)
    
    asyncio.run(main())
```

4. **错误处理**：
   - 所有异步操作必须 `try/except`
   - 网络请求必须设置超时
   - 返回格式统一为 JSON 字符串包裹在 `TextContent` 中

### Phase 4: 沙箱部署与测试 (TESTING)

代码生成后，执行以下测试流程：

1. **静态检查**：
   - AST 分析：检查 import 白名单
   - 结构验证：确认包含 `tools/list`, `tools/call`
   - 标记验证：确认包含 `__exp_mcp_generated__ = True`

2. **部署到沙箱**：
   - 写入 `/workspace/mcp-builds/{build_id}/server.py`
   - 启动沙箱容器（复用 StudioSandboxManager）
   - 容器内执行 `python server.py` 验证能否正常启动

3. **功能测试**：
   - 发送 `tools/list` 请求，验证工具列表正确
   - 对每个工具发送测试调用（使用模拟参数或用户提供的测试数据）
   - 验证返回格式符合预期

4. **测试数据要求**：
   - 如果用户未提供测试数据，明确请求："请提供一个测试用例，例如..."
   - 记录测试结果：`{input, expected, actual, passed}`

### Phase 5: 文档生成 (DOCUMENTATION)

测试通过后，自动生成两份文档：

**A. 构建文档** (`build.md`)：
```markdown
# MCP Build Report: {name}

## 需求
{原始需求}

## 实现方案
{技术选型 + 架构说明}

## 工具清单
| 工具名 | 描述 | 参数 |
|--------|------|------|
| ... | ... | ... |

## 测试记录
{测试用例和结果}

## 依赖
{白名单依赖列表}

## 生成信息
- 模型: {model}
- 时间: {timestamp}
- 构建ID: {build_id}
```

**B. 架构文档** (`architecture.md`)：
```markdown
# MCP Server Architecture: {name}

## 组件图
[ASCII 或文字描述组件关系]

## 数据流
1. LLM tool_call → MCPClient
2. MCPClient → STDIO → Server
3. Server → [外部API/文件/计算]
4. Server → TextContent → MCPClient

## 安全边界
- 运行环境: Docker 沙箱
- 网络策略: {whitelist/none}
- 资源限制: CPU {cpu}, Memory {mem}
- TTL: {ttl}

## 版本历史
| 版本 | 日期 | 变更 |
|------|------|------|
| 1.0.0 | ... | 初始版本 |
```

### Phase 6: 注册与部署 (DEPLOYMENT)

测试和文档完成后：

1. **版本确定**：
   - 如果是新建：版本 = `1.0.0`
   - 如果是迭代：版本递增（根据变更大小判断 major/minor/patch）

2. **注册到平台**：
   - 调用 `MCPService.register()`，参数：
     - `pool: "experimental"`
     - `created_by: {user_id}`
     - `expires_at: now + TTL`
     - `review_status: "pending"`（如果开启审核）或 `"approved"`（如果关闭审核）

3. **用户通知**：
   - 告知用户 MCP 已部署
   - 提供 MCP 名称、版本、可用工具列表
   - 说明 TTL 和续期方式

---

## 输出格式规范

每个 Phase 完成后，输出结构化 JSON：

```json
{
  "phase": "planning|coding|testing|documenting|deploying",
  "status": "in_progress|completed|failed",
  "artifacts": {
    "code_path": "/workspace/mcp-builds/.../server.py",
    "doc_path": "/workspace/mcp-builds/.../build.md",
    "test_results": [...]
  },
  "next_action": "等待用户测试数据 | 自动继续 | 需要人工确认"
}
```

---

## 约束与红线

1. **绝不生成危险代码**：遇到安全检查时失败，必须重新生成而非绕过
2. **绝不泄露平台内部信息**：代码中不得包含内网地址、数据库连接串、API Key
3. **尊重用户数据**：测试数据仅用于验证，不持久化到平台数据库
4. **明确边界**：如果需求超出 MCP 协议能力（如需持久化状态、GUI），明确告知用户并建议替代方案
5. **版本透明**：每次迭代必须说明与上一版本的差异
````

---

## 4. 版本管理与迭代方案

### 4.1 版本号规则

采用 **SemVer** 扩展：

```
{major}.{minor}.{patch}-{prerelease}

示例：
1.0.0        # 初始发布
1.1.0        # 新增工具
1.1.1        # Bug 修复
2.0.0        # 破坏性变更（重大重构）
1.2.0-beta   # 实验版本
```

**版本自动判定逻辑**：

```python
def determine_version(parent_version: str, change_type: str) -> str:
    """
    change_type: 'feature' | 'fix' | 'breaking' | 'refactor'
    """
    major, minor, patch = map(int, parent_version.split('-')[0].split('.'))
    
    if change_type == 'breaking':
        return f"{major + 1}.0.0"
    elif change_type == 'feature':
        return f"{major}.{minor + 1}.0"
    else:  # fix, refactor
        return f"{major}.{minor}.{patch + 1}"
```

### 4.2 版本链与迭代

```
Build #1 (v1.0.0) ──→ Build #2 (v1.1.0) ──→ Build #3 (v2.0.0)
     │                      │                      │
   初始版本              用户反馈新增工具         重构为 SSE 传输
   parent: null          parent: #1              parent: #2
```

**数据库查询版本链**：

```sql
-- 获取某个 MCP 的完整版本历史
WITH RECURSIVE version_chain AS (
    SELECT id, parent_build_id, version, created_at, 0 as depth
    FROM mcp_builds
    WHERE id = {root_build_id}
    
    UNION ALL
    
    SELECT b.id, b.parent_build_id, b.version, b.created_at, vc.depth + 1
    FROM mcp_builds b
    JOIN version_chain vc ON b.parent_build_id = vc.id
)
SELECT * FROM version_chain ORDER BY depth;
```

### 4.3 版本切换与回滚

```python
class MCPVersionManager:
    """MCP 版本管理器"""
    
    async def publish_version(self, build_id: str, version: str):
        """发布指定版本为当前可用版本"""
        build = await self.db.get_build(build_id)
        
        # 1. 保存当前版本快照到 mcp_versions
        current = await self.db.get_mcp_server(build.mcp_server_id)
        if current:
            await self.db.insert_version(
                mcp_server_id=current.id,
                build_id=build.id,
                version=current.current_version,
                code_snapshot=current.generation_meta.get('code'),
                tools_snapshot=current.tools
            )
        
        # 2. 更新 mcp_servers 为新版
        await self.db.update_mcp_server(
            id=build.mcp_server_id,
            current_version=version,
            tools=build.test_cases[0]['tools_snapshot'] if build.test_cases else None,
            generation_meta={
                'build_id': build.id,
                'model': build.model_used,
                'safety_report': build.safety_report
            }
        )
    
    async def rollback(self, mcp_server_id: str, target_version: str):
        """回滚到指定版本"""
        version_record = await self.db.get_version(mcp_server_id, target_version)
        
        # 恢复代码和配置
        await self.db.update_mcp_server(
            id=mcp_server_id,
            current_version=target_version,
            tools=version_record.tools_snapshot
        )
        
        # 重启沙箱（热重载自动处理）
```

---

## 5. 审核流程设计

### 5.1 状态机

```
                    ┌─────────────┐
         ┌─────────→│  PLANNING   │←────────┐
         │          └──────┬──────┘         │
         │                 │ coding          │
         │                 ▼                 │
         │          ┌─────────────┐          │
         │          │   CODING    │          │
         │          └──────┬──────┘          │
         │                 │ testing         │
         │                 ▼                 │
         │          ┌─────────────┐          │
         │          │   TESTING   │◄─────────┘ 用户补充测试数据
         │          └──────┬──────┘
         │                 │ submit for review
         │                 ▼
         │          ┌─────────────┐
         └─────────→│  REVIEWING  │←─────────┐
                    └──────┬──────┘          │
                           │                  │
              ┌────────────┼────────────┐    │
              ▼            ▼            ▼    │
         ┌────────┐   ┌────────┐   ┌────────┐│
         │APPROVED│   │REJECTED│   │CHANGES ││
         └───┬────┘   └───┬────┘   │REQUEST ││
             │            │        └────┬───┘│
             ▼            │             └────┘
        ┌─────────┐       │
        │PUBLISHED│◄──────┘
        └────┬────┘
             │
             ▼
        ┌─────────┐
        │DEPRECATED│
        └─────────┘
```

### 5.2 审核触发条件

| 场景 | 审核要求 | 说明 |
|------|---------|------|
| 平台关闭审核开关 | 无需审核，测试通过即发布 | 开发环境/内测 |
| 平台开启审核开关 | 必须人工审核 | 生产环境 |
| 用户为 Admin | 可自审核 | 管理员特权 |
| 涉及网络请求 | 强制审核 | 安全风险较高 |
| 纯计算/数据处理 | 可自动审核通过 | 风险较低 |

### 5.3 审核 API

```python
# src/omichub/api/v1/mcp_builder.py

@router.get("/builder/review-queue")
async def get_review_queue(
    status: Optional[str] = "reviewing",
    current_user: User = Depends(get_current_admin_user)
):
    """获取待审核队列（仅 Admin）"""
    builds = await MCPBuildRepository.list_by_status(status)
    return builds

@router.post("/builder/{build_id}/review")
async def submit_review(
    build_id: str,
    decision: ReviewDecision,  # approved | rejected | request_changes
    comment: Optional[str] = None,
    current_user: User = Depends(get_current_admin_user)
):
    """提交审核决定"""
    build = await MCPBuildRepository.get(build_id)
    
    # 记录审核
    await MCPReviewRepository.create(
        build_id=build_id,
        reviewer_id=current_user.id,
        decision=decision,
        comment=comment
    )
    
    # 更新构建状态
    if decision == "approved":
        await MCPBuildRepository.update_status(build_id, "approved")
        # 自动发布
        await MCPVersionManager.publish(build_id)
    elif decision == "rejected":
        await MCPBuildRepository.update_status(build_id, "rejected")
    else:  # request_changes
        await MCPBuildRepository.update_status(build_id, "planning")
    
    return {"status": "ok"}
```

---

## 6. 前端管理页面设计

### 6.1 页面路由

| 路由 | 权限 | 功能 |
|------|------|------|
| `/admin/mcp-builder` | Admin | 总览仪表盘 + 开关配置 |
| `/admin/mcp-builder/review` | Admin | 审核队列 |
| `/admin/mcp-builder/servers` | Admin | 所有 MCP 管理（正式+实验） |
| `/studio/mcp-builder` | User | 用户自己的 MCP 构建历史 |
| `/studio/mcp-builder/new` | User | 新建 MCP（唤起 Agent） |

### 6.2 Admin 管理页面组件

**A. 总览仪表盘 (`McpBuilderDashboard.vue`)**

```
┌─────────────────────────────────────────────────────────────┐
│  MCP Builder 管理面板                    [开关: 启用/禁用]   │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐        │
│  │ 待审核   │  │ 实验中   │  │ 已发布   │  │ 今日构建 │        │
│  │   12    │  │   45    │  │   128   │  │    8    │        │
│  └─────────┘  └─────────┘  └─────────┘  └─────────┘        │
├─────────────────────────────────────────────────────────────┤
│  配置项                                                      │
│  ☑ 构建功能启用                                             │
│  ☑ 发布需要审核                                             │
│  ☐ 允许用户自审核（Admin 除外）                              │
│  每用户最大实验 MCP: [ 5 ]                                   │
│  默认 TTL: [ 24 ] 小时                                      │
│  允许模型: [deepseek-v4-pro] [kimi-k3]                      │
├─────────────────────────────────────────────────────────────┤
│  最近构建记录                                                 │
│  ┌────────┬──────────┬────────┬──────────┬────────┐        │
│  │ 用户   │ MCP名称   │ 版本   │ 状态     │ 操作   │        │
│  │ user1  │ pubmed   │ 1.0.0  │ 待审核   │ [审核] │        │
│  │ user2  │ weather  │ 1.2.0  │ 实验中   │ [查看] │        │
│  └────────┴──────────┴────────┴──────────┴────────┘        │
└─────────────────────────────────────────────────────────────┘
```

**B. 审核队列 (`McpBuilderReviewQueue.vue`)**

```
┌─────────────────────────────────────────────────────────────┐
│  审核队列                                                    │
├─────────────────────────────────────────────────────────────┤
│  [全部] [待审核] [已通过] [已拒绝] [需修改]                   │
├─────────────────────────────────────────────────────────────┤
│  Build #a1b2c3 - PubMed 文献查询 MCP                         │
│  ─────────────────────────────────────────                  │
│  用户: user1@example.com                                    │
│  需求: "我需要一个能查询 PubMed 的 MCP，输入关键词返回标题   │
│         和摘要"                                              │
│  代码: [查看代码]  [下载]                                    │
│  安全报告: ✅ 通过 (0 violations, 1 warning)                 │
│  测试: ✅ 2/2 通过                                          │
│  文档: [查看构建文档] [查看架构文档]                         │
│  ─────────────────────────────────────────                  │
│  [✅ 通过并发布]  [❌ 拒绝]  [📝 要求修改]  [备注...]        │
└─────────────────────────────────────────────────────────────┘
```

**C. MCP 版本管理 (`McpBuilderVersions.vue`)**

```
┌─────────────────────────────────────────────────────────────┐
│  MCP: pubmed-query  版本历史                                 │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ○ v2.0.0  (当前)  2026-07-29  user1                       │
│  │   变更: 重构为 SSE 传输，支持流式返回                    │
│  │   [查看代码] [回滚到此版本] [对比上一版本]                │
│  │                                                          │
│  ○ v1.1.0          2026-07-28  user1                       │
│  │   变更: 新增 fetch_abstract 工具                         │
│  │                                                          │
│  ○ v1.0.0          2026-07-27  user1                       │
│      初始版本                                               │
│                                                             │
│  [⬆ 发布新版本]  [📋 复制为模板]  [🗑 废弃]                  │
└─────────────────────────────────────────────────────────────┘
```

### 6.3 用户构建页面 (`StudioMcpBuilder.vue`)

```
┌─────────────────────────────────────────────────────────────┐
│  🔧 我的 MCP 构建                                            │
├─────────────────────────────────────────────────────────────┤
│  [+ 新建 MCP]                                               │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────┐   │
│  │  📦 pubmed-query    v1.2.0    🟢 运行中            │   │
│  │  工具: search, fetch_abstract                        │   │
│  │  TTL: 剩余 18 小时  [续期]  [编辑]  [删除]          │   │
│  └─────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  📦 weather-tool    v1.0.0    🟡 审核中            │   │
│  │  提交时间: 2026-07-29 14:30                         │   │
│  │  [查看详情]                                         │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## 7. 完整实施路径

### Phase 1: 基础设施（Week 1）

| 天数 | 任务 | 文件 |
|------|------|------|
| Day 1-2 | 数据库 Migration | `migrations/xxx_add_mcp_builder_tables.sql` |
| Day 2-3 | Domain 实体扩展 | `domain/mcp/entities.py` 增加 Build/Version/Visibility |
| Day 3-4 | Repository 层 | `infrastructure/database/repositories/mcp_build_repo.py` |
| Day 4-5 | Service 层 | `application/services/mcp_builder_service.py` |

### Phase 2: Agent 与生成（Week 2）

| 天数 | 任务 | 文件 |
|------|------|------|
| Day 6-7 | Agent 配置 | `data/ai/mcp_builder.yaml` + `prompts/mcp_builder.md` |
| Day 7-8 | 代码生成器 | `infrastructure/mcp/builder/generator.py` |
| Day 8-9 | AST 安全检查 | `infrastructure/mcp/builder/safety.py` |
| Day 9-10 | 沙箱 MCP 端点 | `deploy/studio/sandbox_agent.py` + `/mcp/start` |

### Phase 3: 部署与版本（Week 3）

| 天数 | 任务 | 文件 |
|------|------|------|
| Day 11-12 | 部署流水线 | `infrastructure/mcp/builder/pipeline.py` |
| Day 12-13 | 版本管理 | `application/services/mcp_version_manager.py` |
| Day 13-14 | 测试框架 | `infrastructure/mcp/builder/test_runner.py` |
| Day 14-15 | 文档生成 | `infrastructure/mcp/builder/doc_generator.py` |

### Phase 4: 审核与管理（Week 4）

| 天数 | 任务 | 文件 |
|------|------|------|
| Day 16-17 | Admin API | `api/v1/mcp_builder.py` |
| Day 17-18 | 审核流程 | `application/services/mcp_review_service.py` |
| Day 18-19 | 前端管理页 | `frontend/src/views/admin/McpBuilder/` |
| Day 19-20 | 用户构建页 | `frontend/src/views/studio/McpBuilder/` |

### Phase 5: 集成测试（Week 5）

| 天数 | 任务 |
|------|------|
| Day 21-23 | 端到端测试：需求 → 生成 → 测试 → 审核 → 发布 |
| Day 23-25 | 安全渗透测试：Prompt Injection、代码逃逸、权限绕过 |

---

## 8. 关键设计决策

### 8.1 为什么用 SSE 而非 STDIO 做实验 MCP？

| 方案 | 优点 | 缺点 | 选择 |
|------|------|------|------|
| STDIO | 协议简单，无端口管理 | 每个 MCP 一个容器进程，资源占用高 | ❌ |
| **SSE** | 一个容器可运行多个 MCP，UDS 代理安全 | 需要端口分配和代理 | **✅** |

**实现**：`sandbox_agent` 内启动 SSE Server 在 `127.0.0.1:动态端口`，宿主机通过 UDS 代理访问。

### 8.2 用户隔离策略

```
用户A 的实验 MCP：
  ├─ 仅用户A 的 Agent 上下文可见
  ├─ Admin 在管理面板可见（用于审核）
  ├─ 其他用户完全不可见
  └─ 可设置为模板（is_template=true）供他人复用

用户A 发布的正式 MCP：
  ├─ 所有用户可见（如果 is_public=true）
  ├─ 或仅限指定用户组（通过 mcp_visibility 表）
  └─ 版本历史对所有可见者可读
```

### 8.3 与现有 Preset 的关系

| 类型 | 创建方式 | 生命周期 | 可见性 |
|------|---------|---------|--------|
| Preset | 代码内置 | 永久 | 全局 |
| 外部 MCP | Admin 手动注册 | 永久 | 全局 |
| **实验 MCP** | **AI 自动生成** | **TTL 自动过期** | **创建者 + Admin** |
| **正式 MCP** | **审核后发布** | **永久（可废弃）** | **可配置** |

---

## 9. 查漏补缺

基于需求分析，以下是我识别出的**潜在遗漏点**：

| # | 遗漏点 | 影响 | 建议 |
|---|--------|------|------|
| 1 | **MCP 间依赖管理** | 如果 MCP A 依赖 MCP B 的工具，如何声明？ | 增加 `mcp_dependencies` 字段，构建时检查依赖是否存在 |
| 2 | **并发构建限制** | 同一用户同时发起多个构建，资源竞争 | 增加 `max_concurrent_builds_per_user` 限制，队列化 |
| 3 | **构建失败重试策略** | LLM 生成失败后的自动重试 | 设计指数退避重试（最多 3 次），每次换 temperature |
| 4 | **MCP 性能基准** | 无法判断生成的 MCP 是否性能合格 | 增加冷启动时间、P99 延迟基准测试 |
| 5 | **用户反馈闭环** | 用户使用后如何反馈 Bug 驱动迭代 | 增加 `mcp_feedback` 表，关联到 Build |
| 6 | **多语言支持** | 目前只考虑 Python/Node，用户可能需要 Go/Rust | Phase 2 扩展，先聚焦 Python |
| 7 | **成本管控** | LLM 代码生成消耗大量 token | 增加 `token_budget_per_user` 和用量告警 |
| 8 | **沙箱镜像预热** | 每次构建拉镜像慢 | 预装白名单依赖的基础镜像，减少启动时间 |

---

## 10. 总结

你的架构已经非常成熟，实现 MCP Builder Agent 的核心工作是：

1. **补上版本管理、审核流程、生成元数据追踪**三张表
2. **写好 Agent Prompt**（这是灵魂）
3. **扩展沙箱端点**支持容器内 MCP Server 启动
4. **实现 AST 安全检查器**保障生成代码安全

其余都是工程编排。按上面的 5 周路径推进，第 2 周结束就能跑通第一个端到端 Demo。

