# OmicHub AI 助手架构优化调研报告

> **调研日期**：2026-07-04
> **调研范围**：Cherry Studio (v1.9.x, 33K+ Stars) + Open WebUI + OmicHub 当前架构
> **核心目标**：针对用户提出的 5 个问题，提供可落地的架构优化方案

---

## 目录

1. [问题总览与根因分析](#1-问题总览与根因分析)
2. [Cherry Studio 架构借鉴](#2-cherry-studio-架构借鉴)
3. [Open WebUI 架构借鉴](#3-open-webui-架构借鉴)
4. [五大问题专项解决方案](#4-五大问题专项解决方案)
5. [分阶段实施路线图](#5-分阶段实施路线图)
6. [架构对比矩阵](#6-架构对比矩阵)

---

## 1. 问题总览与根因分析

### 1.1 问题清单

| # | 问题描述 | 严重程度 | 根因定位 |
|---|---------|---------|---------|
| 1 | Agent 调用的模型与设置不一致 | 🔴 高 | Agent 模板 `model` 字段与 Provider 配置未建立正确映射 |
| 2 | 无法手动/自动检测所有可用模型 | 🔴 高 | 缺少模型发现（Model Discovery）机制，Provider 仅静态配置 |
| 3 | 模型设置与 MCP/Skill/Agent 分离 | 🟡 中 | 数据模型层面未做统一关联，配置分散在多张表 |
| 4 | 文件上传 / 联网搜索 / 代码执行不可用 | 🔴 高 | UI 已预留但后端实现缺失，前端状态与后端能力未打通 |
| 5 | 希望引入 Cherry Studio 架构同时保留现有样式 | 🟡 中 | 需要选择性移植架构能力，非全盘替换 |

### 1.2 根因深度分析

#### 问题 1：Agent 模型调用不一致

**从架构文档和截图分析：**

- 截图 6（助手管理）显示：通用助手绑定模型 `gpt-4o`，RNA-seq 分析师绑定 `claude-3-5-sonnet`
- 截图 3（AI 模型配置）显示：实际配置的 Provider 模型名是 `qwen3.7-max`、`doubao-seed-2.0-pro`、`deepseek-v4-pro` 等
- 架构文档显示：`AgentService.assemble_context()` 中 `agent.model_id → ai_provider_configs` 的解析逻辑

**根因：**

```
Agent 模板表 (agent_templates)
    ├── model 字段存储的是"模型名称字符串"（如 "gpt-4o"）
    │
    └── 但 ai_provider_configs 表中的 model 字段可能是 "qwen3.7-max"
        
        问题：没有建立 agent.model → provider.model 的正确映射关系！
        
        可能的情况：
        a) agent.model 是硬编码的展示名，实际调用时 fallback 到默认 provider
        b) agent.model 匹配不到任何 provider 配置，使用环境变量回退
        c) 存在多个同名 provider，选择了错误的那个
```

**数据流中的断点：**

```
用户选择 Agent "通用助手" (model="gpt-4o")
    │
    ▼
AgentService.assemble_context(agent_id)
    ├─ 查询 agent_templates 表 → 得到 model="gpt-4o"
    ├─ 查询 ai_provider_configs 表 → 需要匹配 model="gpt-4o" 的 provider
    │      └── 但表中没有 model="gpt-4o" 的配置！
    │      └── 可能 fallback 到 is_default=true 的 provider
    │           └── 结果调用了 qwen3.7-max 而不是 gpt-4o
    │
    └─ 最终：用户看到的是 gpt-4o，实际调用的是 qwen3.7-max
```

#### 问题 2：模型自动检测缺失

**从架构文档分析：**

- Provider 配置完全依赖手动录入（截图 3：管理员在后台手动填写 name/provider_type/model/base_url/api_key）
- 没有 `/models` 自动发现端点的实现（虽然 `chat.py` 有 `GET /models`，但可能是静态返回）
- Cherry Studio 支持 **60+ 内置 Provider 模板**，且能自动调用 `/v1/models` 获取可用模型列表

**缺失的能力：**

| 能力 | Cherry Studio | OmicHub | 差距 |
|------|--------------|---------|------|
| 内置 Provider 模板 | ✅ 60+ 模板（OpenAI/Anthropic/DeepSeek/本地等） | ❌ 完全手动配置 | 🔴 |
| 自动模型列表获取 | ✅ 调用 `/v1/models` 自动填充 | ❌ 无 | 🔴 |
| 模型可用性检测 | ✅ 一键测试连通性 | ✅ 有"测试"按钮（截图3） | ✅ |
| 模型参数预设 | ✅ 按场景保存 temperature/topP 等 | ⚠️ 全局配置 | 🟡 |

#### 问题 3：配置分离

**从数据库 ER 图分析：**

```
ai_provider_configs (1) ──────< chat_sessions
       │                            │
       │                            ├──< chat_messages
       │                            │
       ├──────< chat_assistants     │
       │                            │
       └──────< agent_templates ────┘
                      │
                      └── mcp_ids (JSON array)     ← 仅存储 ID 列表
                      └── skill_ids (JSON array)   ← 仅存储 ID 列表
```

**问题：**
- `agent_templates` 通过 JSON 数组引用 mcp_ids 和 skill_ids，没有外键约束
- `chat_sessions` 同时关联 `assistant_id`、`agent_id`、`model_id`，但 assistant 和 agent 可能各自有独立的 model 偏好
- 模型配置（`ai_provider_configs`）与 Agent 配置（`agent_templates`）是两张独立表，没有统一的"配置中心"

**Cherry Studio 的做法：**
- 助手配置 = {模型 + System Prompt + MCP 工具权限 + 知识库} 统一在一个配置对象中
- 用户创建助手时，一站式选择所有能力，而非分散配置

#### 问题 4：文件上传 / 联网搜索 / 代码执行

**从前端截图分析（截图 7：输入框）：**

```
输入框底部工具栏：
    ├── 💡（提示/快捷指令）
    ├── 📎（文件上传 — 有图标但不可用）
    ├── 🌐（联网搜索 — 有图标但不可用）
    ├── 💻（代码执行 — 有图标但不可用）
    ├── ✨ 深度思考
    └── 🗑️ / ⬆️（清空/发送）
```

**从架构文档分析：**

| 功能 | 前端状态 | 后端状态 | 缺失环节 |
|------|---------|---------|---------|
| 文件上传 | ✅ UI 图标已预留 | ⚠️ `metadata_json(JSONB)` 已预留多模态存储 | 上传 API + 文件解析 + 消息组装 |
| 联网搜索 | ✅ UI 图标已预留 | ⚠️ MCP 架构天然支持 | 搜索 MCP Server + 结果注入 Prompt |
| 代码执行 | ✅ UI 图标已预留 | ⚠️ MCP 工具调用可接入 | 代码执行后端 / 浏览器端 WASM |

**结论：** 前端 UI 已就绪，后端实现需要补齐。

---

## 2. Cherry Studio 架构借鉴

### 2.1 最值得借鉴的 5 个架构设计

#### ① Provider Registry + 自动模型发现

```typescript
// Cherry Studio 的 Provider 注册表模式
interface ProviderRegistry {
  // 60+ 内置 Provider 模板
  providers: Map<ProviderType, ProviderTemplate>;
  
  // 自动获取模型列表
  async fetchModels(provider: ProviderConfig): Promise<Model[]> {
    const response = await fetch(`${provider.baseUrl}/v1/models`, {
      headers: { 'Authorization': `Bearer ${provider.apiKey}` }
    });
    return response.data.map(m => ({ id: m.id, name: m.id }));
  }
}
```

**对 OmicHub 的启示：**
- 新增 `ProviderTemplate` 内置模板（覆盖主流云服务商）
- `POST /api/v1/admin/ai-providers/discover` 自动发现端点
- 前端模型选择器支持"刷新模型列表"

#### ② Agent = 模型 + Prompt + MCP + 知识库 统一配置

```typescript
// Cherry Studio 的助手配置（统一对象）
interface AssistantConfig {
  id: string;
  name: string;
  icon: string;
  
  // 模型配置（内联，不引用外部表）
  model: {
    providerId: string;
    modelId: string;
    temperature: number;
    maxTokens: number;
  };
  
  // 能力配置
  systemPrompt: string;
  mcpServers: string[];        // 启用的 MCP Server ID 列表
  knowledgeBases: string[];    // 关联的知识库 ID 列表
  skills: string[];            // 挂载的技能 ID 列表
  
  // 行为配置
  enableWebSearch: boolean;
  enableCodeExecution: boolean;
  enableDeepThinking: boolean;
}
```

**对 OmicHub 的启示：**
- 将 Agent 配置从"分散多表"改为"统一配置对象"
- 前端 Agent 创建/编辑页变为"一站式配置向导"

#### ③ 消息 Block 化渲染

```typescript
// Cherry Studio 的消息块系统
interface MessageBlock {
  id: string;
  type: 'text' | 'code' | 'image' | 'tool-call' | 'thinking' | 'file';
  content: string;
  metadata?: {
    language?: string;      // code block
    toolName?: string;      // tool-call block
    toolStatus?: 'running' | 'success' | 'error';
    fileUrl?: string;       // file block
    fileType?: string;
  };
}
```

**对 OmicHub 的启示：**
- 将当前纯文本消息重构为 Block 数组
- 文件上传 → `file` block，联网搜索结果 → `tool-call` block，代码执行 → `code` block

#### ④ MCP 工具动态启用 UI

```
Cherry Studio 输入框底部：
    ├── MCP 工具图标 → 弹出可用 MCP Server 列表
    │                    ├── 勾选启用（可多选）
    │                    └── 每个 Server 显示状态（🟢/🟡/🔴）
    │
    └── 每次对话前可动态开启/关闭 MCP 工具
```

**对 OmicHub 的启示：**
- 当前 `AgentCapabilityDrawer` 仅展示 Agent 绑定的 MCP，用户无法在对话中动态启用
- 参考 Cherry Studio，在输入框增加 MCP 工具开关

#### ⑤ 本地 RAG 知识库

```
Cherry Studio RAG Pipeline：
    文档上传 → 解析 → 分块 → Embedding → 向量存储 → 检索 → 注入 Prompt
```

**对 OmicHub 的启示：**
- 生物信息学场景特别需要知识库（文献、实验方案、基因数据库）
- 复用现有 PostgreSQL + pgvector 扩展即可实现

---

## 3. Open WebUI 架构借鉴

### 3.1 最值得借鉴的 3 个架构设计

#### ① 多层代码执行架构

Open WebUI 提供 **4 层代码执行方案**：

| 层级 | 技术 | 隔离性 | 适用场景 |
|------|------|--------|---------|
| L1: 浏览器 WASM | Pyodide | 浏览器沙箱 | 即时执行、零后端改动 |
| L2: Jupyter Kernel | 服务端共享内核 | 无隔离 | 单用户开发环境 |
| L3: Docker 容器 | 容器级隔离 | 进程隔离 | 小团队共享 |
| L4: QEMU MicroVM | 硬件虚拟化 | 完全隔离 | 企业多租户 |

**对 OmicHub 的启示：**
- **立即可落地 L1（Pyodide）**：纯前端方案，用户点击代码块"运行"按钮即可在浏览器执行 Python
- **中期落地 L3（Docker）**：通过 MCP Server 接入容器化代码执行环境

#### ② 流式 Markdown 渲染优化

Open WebUI 使用 **逐 token 更新 + ContentRenderer 组件**，解决流式 Markdown 渲染的闪烁和格式抖动问题。

**行业方案对比：**

| 方案 | 框架 | 核心机制 |
|------|------|---------|
| Streamdown | React | 增量解析 + Memoized 渲染 |
| vue-mdr | Vue | 文本拆分 + Shiki 流式高亮 |
| Open WebUI 原生 | Svelte | 逐 token 更新 + 虚拟 DOM 优化 |

**对 OmicHub 的启示：**
- 当前 `KimiMessageItem.vue` 使用常规 Markdown 渲染器，流式场景下可能闪烁
- 建议引入增量 Markdown 解析器或自研流式优化方案

#### ③ Pipeline-Filter 插件模式

```
用户输入 → [Inlet Filters] → LLM 调用 → [Outlet Filters] → 响应输出
              ↓                                    ↓
         身份验证/预处理                     后处理/格式化
         RAG 上下文注入                      日志/监控
         工具定义注入                        缓存管理
```

**对 OmicHub 的启示：**
- 当前 Agent 调度是硬编码的 8 轮循环
- 可借鉴 Pipeline 模式，将"联网搜索注入"、"RAG 检索注入"、"敏感词过滤"等实现为可插拔 Filter

---

## 4. 五大问题专项解决方案

### 4.1 问题 1：Agent 模型调用不一致

#### 根因确认

Agent 模板中存储的模型名称与实际 Provider 配置未建立正确映射。

#### 解决方案

**方案 A：模型 ID 引用制（推荐）**

```
改造前：
    agent_templates.model = "gpt-4o"  (字符串，易失效)
    
改造后：
    agent_templates.default_model_id = "uuid-of-provider-config"  (外键引用)
    
    // 同时保留 model_name 作为展示名（冗余，只读）
    agent_templates.default_model_name = "gpt-4o"
```

**数据库变更：**

```sql
-- 1. 新增外键字段
ALTER TABLE agent_templates 
ADD COLUMN default_model_id UUID REFERENCES ai_provider_configs(id);

-- 2. 迁移数据：将现有 model 字符串匹配到 provider 配置
UPDATE agent_templates a
SET default_model_id = p.id
FROM ai_provider_configs p
WHERE a.model = p.model;

-- 3. 删除旧字段（验证无误后）
ALTER TABLE agent_templates DROP COLUMN model;
```

**后端逻辑变更：**

```python
# application/services/agent_service.py
async def assemble_context(self, agent_id: str) -> AgentContext:
    agent = await self.agent_repo.get(agent_id)
    
    # 改造前：用字符串匹配，易出错
    # provider = await self.provider_repo.get_by_model_name(agent.model)
    
    # 改造后：直接外键引用，100% 准确
    provider = await self.provider_repo.get(agent.default_model_id)
    
    return AgentContext(
        provider=provider,
        system_prompt=agent.system_prompt,
        tools=self.collect_mcp_tools(agent.mcp_ids),
    )
```

**前端变更：**

```vue
<!-- Agent 编辑页：模型选择改为下拉选择（从 provider 列表选） -->
<template>
  <n-select
    v-model:value="form.default_model_id"
    :options="providerOptions"
    placeholder="选择模型"
  />
</template>
```

#### 验证检查清单

- [ ] Agent 创建时模型选择从字符串输入改为下拉选择
- [ ] 数据库建立外键约束
- [ ] `assemble_context()` 使用外键而非字符串匹配
- [ ] 旧数据迁移脚本
- [ ] 删除冗余的 model 字符串字段

---

### 4.2 问题 2：模型自动检测

#### 解决方案

**后端：新增模型发现 API**

```python
# api/v1/admin/ai_providers.py

@router.post("/{provider_id}/discover-models")
async def discover_models(
    provider_id: UUID,
    service: AIProviderService = Depends(get_provider_service),
):
    """自动发现指定 Provider 下的所有可用模型"""
    provider = await service.get(provider_id)
    
    # 调用 /v1/models 端点
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{provider.base_url}/v1/models",
            headers={"Authorization": f"Bearer {provider.api_key}"},
            timeout=30.0
        )
    
    models = response.json()["data"]
    return {
        "provider_id": provider_id,
        "models": [
            {
                "id": m["id"],
                "name": m.get("name", m["id"]),
                "owned_by": m.get("owned_by", "unknown"),
            }
            for m in models
        ]
    }
```

**前端：模型选择器增强**

```vue
<!-- 模型选择组件 -->
<template>
  <div class="model-selector">
    <n-select
      v-model:value="selectedModelId"
      :options="modelOptions"
      :loading="loading"
    />
    <n-button @click="refreshModels" :loading="loading">
      <template #icon><RefreshIcon /></template>
      刷新模型列表
    </n-button>
  </div>
</template>

<script setup>
async function refreshModels() {
  loading.value = true;
  // 1. 获取所有 provider
  const providers = await adminProviderApi.list();
  
  // 2. 并行调用发现接口
  const discoveries = await Promise.all(
    providers.map(p => adminProviderApi.discoverModels(p.id))
  );
  
  // 3. 合并结果到模型列表
  modelOptions.value = discoveries.flatMap(d => 
    d.models.map(m => ({
      label: `${m.name} (${d.provider_name})`,
      value: `${d.provider_id}:${m.id}`,
    }))
  );
  loading.value = false;
}
</script>
```

**内置 Provider 模板（参考 Cherry Studio）：**

```yaml
# data/ai/provider_templates.yaml
providers:
  - name: "OpenAI"
    type: "openai_compatible"
    base_url: "https://api.openai.com/v1"
    default_models: ["gpt-4o", "gpt-4o-mini", "o1-preview", "o1-mini"]
    
  - name: "Anthropic"
    type: "openai_compatible"
    base_url: "https://api.anthropic.com/v1"
    default_models: ["claude-3-5-sonnet", "claude-3-opus", "claude-3-haiku"]
    
  - name: "DeepSeek"
    type: "openai_compatible"
    base_url: "https://api.deepseek.com/v1"
    default_models: ["deepseek-chat", "deepseek-reasoner"]
    
  - name: "Kimi (Moonshot)"
    type: "openai_compatible"
    base_url: "https://api.moonshot.cn/v1"
    default_models: ["kimi-k2", "kimi-k1.5", "moonshot-v1-8k"]
    
  - name: "Ollama (本地)"
    type: "openai_compatible"
    base_url: "http://localhost:11434/v1"
    default_models: []  # 动态发现
```

---

### 4.3 问题 3：模型设置与 MCP/Skill/Agent 统一配置

#### 解决方案：统一配置中心

**数据库设计变更：**

```sql
-- 统一配置表（替代分散配置）
CREATE TABLE agent_configurations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    icon VARCHAR(255),
    category VARCHAR(100),
    
    -- 模型配置（内联，不引用外部表）
    model_config JSONB NOT NULL DEFAULT '{}',
    -- {
    --   "provider_id": "uuid",
    --   "model_id": "gpt-4o",
    --   "temperature": 0.7,
    --   "max_tokens": 4096,
    --   "top_p": 1.0
    -- }
    
    -- 能力配置
    system_prompt TEXT,
    mcp_server_ids JSONB DEFAULT '[]',
    skill_ids JSONB DEFAULT '[]',
    knowledge_base_ids JSONB DEFAULT '[]',
    
    -- 功能开关
    features JSONB DEFAULT '{}',
    -- {
    --   "enable_web_search": false,
    --   "enable_code_execution": false,
    --   "enable_deep_thinking": false,
    --   "enable_file_upload": true
    -- }
    
    is_builtin BOOLEAN DEFAULT false,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 迁移：从 agent_templates + chat_assistants 合并
INSERT INTO agent_configurations (
    id, name, description, icon, category,
    model_config, system_prompt, mcp_server_ids, skill_ids
)
SELECT 
    at.id, at.name, at.description, at.icon, at.category,
    jsonb_build_object(
        'provider_id', at.default_model_id,
        'model_id', apc.model,
        'temperature', apc.temperature,
        'max_tokens', apc.max_tokens
    ),
    at.system_prompt,
    at.mcp_ids,
    at.skill_ids
FROM agent_templates at
LEFT JOIN ai_provider_configs apc ON at.default_model_id = apc.id;
```

**前端：一站式配置向导**

```
Agent 配置向导（3 步）：
    
Step 1: 基础信息
    ├── 名称
    ├── 图标
    ├── 分类
    └── 描述
    
Step 2: 模型与行为
    ├── 模型选择（下拉，支持刷新）
    ├── Temperature 滑块
    ├── Max Tokens 输入
    ├── System Prompt 编辑器
    └── 深度思考开关
    
Step 3: 能力挂载
    ├── MCP 服务（勾选列表，显示状态 🟢🟡🔴）
    ├── 技能（勾选列表）
    ├── 知识库（勾选列表）
    └── 功能开关（联网搜索 / 代码执行 / 文件上传）
```

---

### 4.4 问题 4：文件上传 / 联网搜索 / 代码执行

#### 4.4.1 文件上传

**前端（已预留图标，需连接逻辑）：**

```typescript
// stores/agentHub.ts
async function sendMessage(content: string, options: {
  attachments?: File[];        // 新增：附件列表
  enableWebSearch?: boolean;   // 新增：联网搜索开关
  enableCodeExecution?: boolean; // 新增：代码执行开关
}) {
  // 1. 上传文件
  const uploadedFiles = options.attachments 
    ? await Promise.all(options.attachments.map(uploadFile))
    : [];
  
  // 2. 组装消息（多模态格式）
  const message = {
    role: 'user',
    content: content,
    attachments: uploadedFiles.map(f => ({
      type: f.mimeType.startsWith('image/') ? 'image' : 'file',
      url: f.url,
      name: f.name,
    }))
  };
  
  // 3. 发送 SSE 请求
  await streamChat({
    agentId: currentAgentId,
    messages: [...context, message],
    sessionId: currentSessionId,
  });
}
```

**后端（多模态消息处理）：**

```python
# application/services/chat_service.py
async def stream_agent_chat(self, request: ChatStreamRequest):
    # 解析多模态消息
    messages = []
    for msg in request.messages:
        if msg.attachments:
            # 构建 OpenAI 多模态消息格式
            content = [{"type": "text", "text": msg.content}]
            for att in msg.attachments:
                if att.type == "image":
                    content.append({
                        "type": "image_url",
                        "image_url": {"url": att.url}
                    })
                else:
                    # 文件：读取内容注入
                    file_content = await self.read_file(att.url)
                    content.append({
                        "type": "text",
                        "text": f"\n\n[文件: {att.name}]\n{file_content}\n"
                    })
            messages.append({"role": msg.role, "content": content})
        else:
            messages.append({"role": msg.role, "content": msg.content})
    
    # 继续原有流式逻辑...
```

#### 4.4.2 联网搜索

**方案：MCP 搜索工具 + 结果注入**

```python
# 1. 接入搜索 MCP Server（或自建）
# 例如：使用 mcp-server-fetch 或自建百度搜索 MCP

# 2. 在 Agent 调度中注入搜索能力
async def stream_agent_chat(self, request: ChatStreamRequest):
    # 检查是否启用联网搜索
    if request.enable_web_search:
        # 将搜索工具注入 tools 列表
        tools.append(self.web_search_tool)
    
    # 原有工具调用循环...
```

**前端搜索开关：**

```vue
<!-- KimiChatInput.vue -->
<template>
  <div class="chat-input-toolbar">
    <!-- 联网搜索开关 -->
    <n-tooltip>
      <template #trigger>
        <n-switch v-model:value="enableWebSearch" size="small">
          <template #checked-icon>🌐</template>
        </n-switch>
      </template>
      联网搜索
    </n-tooltip>
    
    <!-- 其他工具... -->
  </div>
</template>
```

#### 4.4.3 代码执行

**方案：Pyodide 浏览器端 WASM（零后端改动，立即落地）**

```typescript
// composables/usePyodide.ts
import { loadPyodide } from 'pyodide';

export function usePyodide() {
  let pyodide: any = null;
  
  async function init() {
    if (!pyodide) {
      pyodide = await loadPyodide({
        indexURL: 'https://cdn.jsdelivr.net/pyodide/v0.26.0/full/',
      });
      // 预装常用库
      await pyodide.loadPackage(['numpy', 'pandas', 'matplotlib']);
    }
    return pyodide;
  }
  
  async function execute(code: string): Promise<{
    output: string;
    images: string[];  // base64 图表
    error?: string;
  }> {
    const py = await init();
    
    // 捕获 stdout
    let output = '';
    py.setStdout({ batched: (text: string) => { output += text; } });
    
    // 捕获 matplotlib 图表
    py.runPython(`
      import matplotlib.pyplot as plt
      plt.switch_backend('agg')
    `);
    
    try {
      await py.runPythonAsync(code);
      
      // 获取图表
      const images = await extractImages(py);
      
      return { output, images };
    } catch (e) {
      return { output, images: [], error: String(e) };
    }
  }
  
  return { init, execute };
}
```

**代码块运行按钮（前端）：**

```vue
<!-- KimiMessageItem.vue 中的代码块 -->
<template>
  <div class="code-block">
    <div class="code-header">
      <span class="language">{{ block.language }}</span>
      <n-button size="tiny" @click="runCode(block.content)">
        ▶ 运行
      </n-button>
    </div>
    <pre><code>{{ block.content }}</code></pre>
    
    <!-- 执行结果 -->
    <div v-if="executionResult" class="execution-result">
      <pre>{{ executionResult.output }}</pre>
      <img v-for="img in executionResult.images" :src="img" />
    </div>
  </div>
</template>
```

**后端补充方案（Docker 沙箱）：**

```python
# 通过 MCP Server 接入代码执行
# infrastructure/mcp/code_execution_server.py

class CodeExecutionMCPServer:
    """Docker 容器内代码执行 MCP Server"""
    
    async def execute(self, code: str, language: str = "python") -> str:
        # 启动临时容器
        container = await docker.containers.create({
            'image': 'python:3.11-slim',
            'command': ['python', '-c', code],
            'mem_limit': '512m',
            'cpu_quota': 100000,  # 限制 CPU
            'network_mode': 'none',  # 无网络
        })
        
        await container.start()
        result = await container.wait()
        logs = await container.logs()
        await container.delete()
        
        return logs.decode()
```

---

### 4.5 问题 5：保留样式 + 引入 Cherry Studio 架构

#### 策略：架构能力移植，UI 风格保留

```
┌─────────────────────────────────────────────────────┐
│  保留 OmicHub 现有 UI 风格                           │
│  ├── Vue 3 + Pinia（不换 React/Redux）               │
│  ├── NaiveUI 组件库（不引入 Tailwind）               │
│  ├── 现有配色/布局/交互模式                          │
│  └── 生物信息学领域特色 UI                           │
├─────────────────────────────────────────────────────┤
│  引入 Cherry Studio 架构能力                         │
│  ├── Provider Registry + 模型自动发现                │
│  ├── Agent 统一配置中心                              │
│  ├── 消息 Block 化渲染                               │
│  ├── MCP 动态启用 UI                                 │
│  ├── RAG 知识库 Pipeline                             │
│  └── 多模型对比对话（可选）                          │
├─────────────────────────────────────────────────────┤
│  引入 Open WebUI 架构能力                            │
│  ├── Pyodide 浏览器端代码执行                        │
│  ├── 流式 Markdown 渲染优化                          │
│  └── Pipeline-Filter 插件模式（可选）                │
└─────────────────────────────────────────────────────┘
```

#### 前端组件映射

| Cherry Studio 组件 | OmicHub 对应组件 | 改造方式 |
|-------------------|-----------------|---------|
| `MessageBlock` | `KimiMessageItem.vue` | 重构为 Block 数组渲染 |
| `MCPSelector` | `AgentCapabilityDrawer.vue` | 新增动态启用功能 |
| `ModelSelector` | `stores/chat.ts` 中的模型选择 | 增加自动发现 + 刷新 |
| `KnowledgeBaseDrawer` | 新增 | 全新开发 |
| `ReasoningPanel` | 新增 | 新增可折叠面板 |
| `ToolCallChain` | `KimiMessageItem.vue` 工具展示 | 升级为卡片式可视化 |

---

## 5. 分阶段实施路线图

### Phase 1：紧急修复（1-2 周）

**目标：修复问题 1（模型调用不一致）**

```
Week 1:
    ├── 数据库：agent_templates 增加 default_model_id 外键
    ├── 后端：AgentService.assemble_context() 改用外键引用
    └── 前端：Agent 编辑页模型选择改为下拉
    
Week 2:
    ├── 数据迁移：将现有 model 字符串匹配到 provider
    ├── 回归测试：验证所有 Agent 调用正确模型
    └── 清理：删除冗余 model 字符串字段
```

### Phase 2：核心能力补齐（3-6 周）

**目标：修复问题 2、3、4**

```
Week 3-4: 模型自动发现 + 统一配置中心
    ├── 后端：新增 /discover-models API
    ├── 后端：Provider 内置模板（YAML）
    ├── 数据库：agent_configurations 统一配置表
    └── 前端：模型选择器增强（刷新按钮 + 自动发现）
    
Week 5-6: 文件上传 + 联网搜索
    ├── 后端：文件上传 API + 多模态消息格式
    ├── 后端：联网搜索 MCP Server 接入
    ├── 前端：连接上传图标逻辑
    └── 前端：联网搜索开关连接 SSE
    
Week 7-8: 代码执行
    ├── 前端：Pyodide WASM 集成（零后端改动）
    ├── 前端：代码块"运行"按钮
    ├── 可选：后端 Docker 沙箱 MCP Server
    └── 测试：常见生物信息学代码执行（pandas, matplotlib）
```

### Phase 3：体验升级（4-6 周）

**目标：引入 Cherry Studio 高级能力**

```
Week 9-10: 消息 Block 化 + 渲染优化
    ├── 重构 ChatMessage 类型为 Block 数组
    ├── 新增 ReasoningPanel 组件
    ├── 新增 ToolCallChain 组件
    └── 流式 Markdown 渲染优化（减少闪烁）
    
Week 11-12: RAG 知识库
    ├── 后端：pgvector 集成 + 文档解析 Pipeline
    ├── 后端：Embedding 服务接入
    ├── 前端：KnowledgeBaseDrawer 组件
    └── 管理后台：知识库 CRUD
    
Week 13-14: Agent 体验打磨
    ├── MCP 动态启用 UI（输入框工具开关）
    ├── Token 消耗显示
    ├── 深度思考折叠面板
    └── Legacy Store 清理
```

### Phase 4：高级功能（6-8 周）

```
Week 15-16: 多模型对比对话
    ├── useAgentChatStream 多实例并行
    ├── AgentSandbox 响应式分栏布局
    └── 后端：支持 model_id 参数覆盖
    
Week 17-18: 主题系统 + 对话导出
    ├── 自定义 CSS 支持
    ├── Markdown / Word / 图片导出
    └── 全局搜索（历史对话 + 知识库）
    
Week 19-20: 稳定性优化
    ├── Provider 收敛（下线 LiteLLM + Kimi Provider）
    ├── 上下文管理升级（token 级而非消息数）
    └── 性能测试与优化
```

---

## 6. 架构对比矩阵

### 6.1 三架构横向对比

| 维度 | OmicHub (当前) | Cherry Studio | Open WebUI |
|------|---------------|---------------|-----------|
| **产品形态** | Web B/S | Electron C/S | Web B/S |
| **前端框架** | Vue 3 + Pinia | React + Redux | SvelteKit |
| **后端框架** | FastAPI | Go + Node (企业版) | FastAPI |
| **通信协议** | SSE | SSE/HTTP | Socket.IO |
| **模型管理** | 手动配置 | 60+ 模板 + 自动发现 | 手动配置 |
| **Agent 调度** | 后端 8 轮循环 | 本地 API Server | Pipeline-Filter |
| **MCP 支持** | builtin/stdio/sse | builtin/stdio/sse | Filters |
| **代码执行** | MCP 外部 | 无内置 | Pyodide/WASM/Docker |
| **知识库** | ❌ | ✅ 本地 RAG | ✅ 可插拔 RAG |
| **多模型对话** | ❌ | ✅ | ✅ |
| **文件上传** | ⚠️ UI 预留 | ✅ | ✅ |
| **联网搜索** | ⚠️ UI 预留 | ✅ MCP fetch | ✅ |
| **安全设计** | Fernet 加密 + 沙箱 | 本地优先 | exec() 风险 |
| **流式渲染** | 基础 Markdown | Cherry Markdown (10ms) | ContentRenderer |

### 6.2 能力补齐优先级

```
P0 (立即修复):
    ├── 问题 1: Agent 模型调用不一致
    └── 问题 4: 文件上传 / 联网搜索 / 代码执行
    
P1 (1-2 月):
    ├── 问题 2: 模型自动检测
    ├── 问题 3: 统一配置中心
    └── 消息 Block 化 + Agent 体验升级
    
P2 (3-4 月):
    ├── RAG 知识库
    ├── 多模型对比对话
    └── 流式渲染优化
    
P3 (长期):
    ├── 主题系统
    ├── 对话导出
    └── Legacy 全面清理
```

---

## 附录：关键代码文件变更清单

| 文件 | 变更类型 | 变更内容 |
|------|---------|---------|
| `domain/ai_provider/entities.py` | 新增 | `ProviderTemplate` 内置模板实体 |
| `domain/agent/entities.py` | 修改 | `default_model_id` 外键替代 `model` 字符串 |
| `application/services/agent_service.py` | 修改 | `assemble_context()` 使用外键引用 |
| `application/services/chat_service.py` | 修改 | 支持多模态消息、联网搜索开关 |
| `api/v1/admin/ai_providers.py` | 新增 | `/discover-models` 自动发现端点 |
| `infrastructure/ai_provider/openai_compatible.py` | 修改 | 支持 `/v1/models` 调用 |
| `stores/agentHub.ts` | 修改 | 支持 attachments、enableWebSearch 等选项 |
| `stores/chat.ts` | 修改 | 模型选择器增加自动发现 |
| `components/ai-chat/KimiChatInput.vue` | 修改 | 连接上传/搜索/代码执行逻辑 |
| `components/ai-chat/KimiMessageItem.vue` | 重构 | Block 化渲染 |
| `components/agent-workspace/AgentCapabilityDrawer.vue` | 修改 | 增加 MCP 动态启用 |
| `composables/usePyodide.ts` | 新增 | Pyodide WASM 代码执行 |
| `composables/useAgentChatStream.ts` | 修改 | 支持多实例并行 |

---

> **报告总结**：OmicHub 当前的 SSE + MCP + DDD 分层架构是现代化且合理的选择。核心问题在于**配置层面的数据模型设计**（问题 1/2/3）和**前端预留功能的后端补齐**（问题 4）。建议优先修复模型调用一致性（外键引用制），然后并行推进模型自动发现、统一配置中心和文件上传/搜索/代码执行三大能力。Cherry Studio 的 Provider Registry、统一配置对象和消息 Block 化是最值得移植的架构设计；Open WebUI 的 Pyodide 代码执行是最值得借鉴的功能实现。
