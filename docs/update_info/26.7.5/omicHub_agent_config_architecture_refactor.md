# OmicHub Agent 配置架构重构方案：从分散 YAML 到统一 ai_providers.yaml

> 生成日期：2026-07-05
> 目标：将分散的 agent YAML 文件整合为统一的 `ai_providers.yaml`，并支持 agent 加载控制

---

## 一、现状痛点

当前每个 agent 一个独立 YAML 文件：

```
config/
├── agents/
│   ├── general.yaml
│   ├── rna_expert.yaml
│   ├── atac_expert.yaml
│   └── single_cell_expert.yaml
├── mcp_servers.yaml
├── skills.yaml
└── ai_providers.yaml   ← 目前可能只存了模型提供商配置
```

### 问题

| 痛点 | 说明 |
|------|------|
| 文件碎片化 | 新增/修改 agent 要操作多个文件，容易遗漏 |
| 无加载控制 | 无法在一个地方声明"当前启用哪些 agent"、"默认加载哪个" |
| 配置重复 | 多个 agent 可能共用相同的 model/temperature，重复定义 |
| 与前端割裂 | 前端编辑后无法回写 YAML，或回写后格式混乱 |
| 缺乏版本感 | 无法直观对比 agent 配置的变更历史 |

---

## 二、统一 ai_providers.yaml 结构设计

### 2.1 整体架构

```yaml
# ai_providers.yaml
version: "2.0"                    # 配置格式版本，便于后续迁移
last_updated: "2026-07-05T01:30:00+08:00"

# ── 全局默认值 ──
defaults:
  model: "qwen3.7-max"
  temperature: 0.7
  max_tokens: 4096
  provider: "aliyun"              # 关联到 providers 中的某个 provider

# ── 模型提供商配置 ──
providers:
  aliyun:
    name: "阿里云百炼"
    base_url: "https://dashscope.aliyuncs.com/api/v1"
    api_key: "${ALIYUN_API_KEY}"  # 环境变量引用，避免硬编码
    models:
      - qwen3.7-max
      - qwen3.7-32b
      - qwen3.7-14b
  openai:
    name: "OpenAI"
    base_url: "https://api.openai.com/v1"
    api_key: "${OPENAI_API_KEY}"
    models:
      - gpt-4o
      - gpt-4o-mini

# ── Agent 注册表 ──
# 所有 agent 定义集中在此，替代分散的 agents/ 目录
agents:
  # ── 通用助手 ──
  agent-general:
    enabled: true                 # ← 加载控制：是否启用
    is_default: true              # ← 加载控制：是否为默认 agent
    name: "通用助手"
    description: "覆盖日常问答与通用生信咨询的全能助手。"
    avatar: "🤖"
    color: "#4f8ef7"
    category: "general"
    # 模型配置：可继承 defaults，也可覆盖
    model: "qwen3.7-max"          # 不写则继承 defaults.model
    temperature: 0.7
    max_tokens: 4096
    system_prompt: |
      你是 OmicHub 通用助手，友好、准确、简洁地回答用户问题，
      必要时引导到专业助手。
    welcome_message: "你好！我是通用助手，可以帮你解答生信分析的一般问题。今天想做点什么？"
    # 能力挂载
    mcp_ids:
      - literature
      - genome
    skill_ids: []
    # 功能开关
    features:
      web_search: false
      file_upload: true
      code_execution: false
      deep_thinking: false

  # ── RNA 专家 ──
  agent-rna:
    enabled: true
    is_default: false
    name: "RNA 分析专家"
    description: "专注于 RNA-seq 差异表达、可变剪接、融合基因分析。"
    avatar: "🧬"
    color: "#e74c3c"
    category: "rna"
    model: "qwen3.7-32b"          # 覆盖默认模型
    temperature: 0.3              # 更严谨
    system_prompt: |
      你是 RNA 分析专家，精通 STAR、RSEM、DESeq2、rMATS 等工具。
      用户询问 RNA-seq 分析时，提供专业的参数建议和结果解读。
    welcome_message: "你好！我是 RNA 分析专家，有任何 RNA-seq 相关的问题都可以问我。"
    mcp_ids:
      - literature
      - genome
      - rna_tools
    skill_ids:
      - rna_pipeline
    features:
      web_search: true
      file_upload: true
      code_execution: true
      deep_thinking: true

  # ── ATAC 专家 ──
  agent-atac:
    enabled: false                # ← 未启用，前端不展示
    is_default: false
    name: "ATAC 分析专家"
    description: "专注于染色质可及性分析、peak calling、motif 分析。"
    avatar: "🧪"
    color: "#2ecc71"
    category: "atac"
    model: "qwen3.7-32b"
    temperature: 0.3
    system_prompt: |
      你是 ATAC-seq 分析专家，精通 MACS2、TOBIAS、HOMER 等工具...
    welcome_message: "你好！我是 ATAC 分析专家。"
    mcp_ids: []
    skill_ids: []
    features:
      web_search: false
      file_upload: true
      code_execution: false
      deep_thinking: false

  # ── 单细胞专家 ──
  agent-scrna:
    enabled: true
    is_default: false
    name: "单细胞分析专家"
    description: "专注于 scRNA-seq 降维、聚类、细胞类型注释。"
    avatar: "🔬"
    color: "#9b59b6"
    category: "single_cell"
    model: "qwen3.7-max"
    temperature: 0.5
    system_prompt: |
      你是单细胞分析专家，精通 Seurat、Scanpy、Monocle 等工具...
    welcome_message: "你好！我是单细胞分析专家。"
    mcp_ids:
      - literature
      - genome
    skill_ids:
      - sc_pipeline
    features:
      web_search: true
      file_upload: true
      code_execution: true
      deep_thinking: true

# ── 加载策略（可选，高级控制） ──
loading:
  # 默认加载的 agent（当用户首次进入平台时）
  default_agent_id: "agent-general"
  # 是否允许用户切换 agent
  allow_user_switch: true
  # 按分类分组展示（前端侧边栏/选择器用）
  categories:
    - id: "general"
      name: "通用"
      icon: "🌐"
    - id: "rna"
      name: "RNA 分析"
      icon: "🧬"
    - id: "atac"
      name: "ATAC 分析"
      icon: "🧪"
    - id: "single_cell"
      name: "单细胞"
      icon: "🔬"
```

### 2.2 关键字段说明

| 字段 | 层级 | 作用 |
|------|------|------|
| `version` | 根 | 配置格式版本，后端读取时做兼容性校验 |
| `defaults` | 根 | 全局默认值，agent 可继承或覆盖 |
| `providers` | 根 | 模型提供商配置（原 ai_providers.yaml 的内容） |
| `agents` | 根 | **所有 agent 定义集中地**，key 为 agent_id |
| `agents.<id>.enabled` | agent | **加载控制**：`false` 时前端不展示、后端不加载 |
| `agents.<id>.is_default` | agent | **加载控制**：用户首次进入时默认选中的 agent |
| `loading` | 根 | 可选的高级加载策略，与 `is_default` 互补 |

---

## 三、加载控制机制

### 3.1 启用/停用（enabled）

```yaml
agents:
  agent-general:
    enabled: true      # ← 前端展示，后端加载
  agent-atac:
    enabled: false     # ← 前端隐藏，后端不加载
```

**前端行为：**
- 侧边栏/选择器只渲染 `enabled: true` 的 agent
- `enabled: false` 的 agent 在"管理后台"中仍可见（带"已停用"标签），管理员可重新启用

**后端行为：**
- 启动时只初始化 `enabled: true` 的 agent
- API `/api/agents` 默认只返回 `enabled: true` 的列表
- 管理员接口 `/api/agents/all` 返回全部（含已停用）

### 3.2 默认加载（is_default / loading.default_agent_id）

两种策略任选其一：

**策略 A：agent 级标记（简单）**
```yaml
agents:
  agent-general:
    is_default: true   # 唯一 true，其余 false
```

**策略 B：全局配置（灵活）**
```yaml
loading:
  default_agent_id: "agent-general"
```

> 推荐 **策略 B**，因为可以在不修改 agent 定义的情况下切换默认 agent。

### 3.3 运行时切换

用户在前端切换 agent 时，前端发送请求：

```http
POST /api/chat/session/agent
Content-Type: application/json

{
  "session_id": "sess_xxx",
  "agent_id": "agent-rna"
}
```

后端从 `ai_providers.yaml` 中读取对应 agent 配置，重建对话上下文。

---

## 四、与前端编辑的联动

### 4.1 编辑流程

```
用户在前端编辑 Agent
        ↓
前端调用 PUT /api/agents/{agent_id}
        ↓
后端更新内存中的配置对象
        ↓
后端将完整 ai_providers.yaml 写回磁盘
        ↓
（可选）Git 自动提交变更，记录修改历史
```

### 4.2 后端回写注意事项

```python
import yaml
from ruamel.yaml import YAML  # 推荐 ruamel.yaml，保留注释和格式

class AgentConfigManager:
    def __init__(self, config_path: str = "config/ai_providers.yaml"):
        self.config_path = config_path
        self.yaml = YAML()
        self.yaml.preserve_quotes = True
        self.yaml.default_flow_style = False
        self._load()

    def _load(self):
        with open(self.config_path, 'r', encoding='utf-8') as f:
            self.config = self.yaml.load(f)

    def update_agent(self, agent_id: str, updates: dict):
        """更新指定 agent，并回写 YAML"""
        if agent_id not in self.config['agents']:
            raise KeyError(f"Agent {agent_id} not found")

        # 只更新允许的字段
        allowed_fields = {
            'enabled', 'is_default', 'name', 'description', 'avatar',
            'color', 'category', 'model', 'temperature', 'max_tokens',
            'system_prompt', 'welcome_message', 'mcp_ids', 'skill_ids', 'features'
        }

        agent = self.config['agents'][agent_id]
        for key, value in updates.items():
            if key in allowed_fields:
                agent[key] = value

        # 如果修改了 is_default，确保其他 agent 的 is_default 为 false
        if updates.get('is_default') is True:
            for aid, a in self.config['agents'].items():
                if aid != agent_id:
                    a['is_default'] = False

        self._save()
        return agent

    def _save(self):
        """原子写回，防止写坏文件"""
        import tempfile
        import os

        with tempfile.NamedTemporaryFile(
            mode='w', 
            encoding='utf-8', 
            suffix='.yaml',
            delete=False
        ) as f:
            self.yaml.dump(self.config, f)
            temp_path = f.name

        # 原子替换
        os.replace(temp_path, self.config_path)

    def get_active_agents(self) -> list:
        """获取所有启用的 agent"""
        return [
            {"agent_id": k, **v} 
            for k, v in self.config['agents'].items() 
            if v.get('enabled', True)
        ]

    def get_default_agent(self) -> dict:
        """获取默认 agent"""
        default_id = self.config.get('loading', {}).get('default_agent_id')
        if default_id and default_id in self.config['agents']:
            agent = self.config['agents'][default_id]
            if agent.get('enabled', True):
                return {"agent_id": default_id, **agent}

        # fallback：找第一个 enabled 且 is_default 的 agent
        for k, v in self.config['agents'].items():
            if v.get('enabled', True) and v.get('is_default', False):
                return {"agent_id": k, **v}

        # 最终 fallback：第一个 enabled 的 agent
        for k, v in self.config['agents'].items():
            if v.get('enabled', True):
                return {"agent_id": k, **v}

        raise RuntimeError("No active agent found")
```

### 4.3 热重载（可选）

如果不想每次编辑都重启后端，可以实现文件监听：

```python
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class ConfigReloadHandler(FileSystemEventHandler):
    def __init__(self, manager: AgentConfigManager):
        self.manager = manager

    def on_modified(self, event):
        if event.src_path.endswith('ai_providers.yaml'):
            print("[Config] ai_providers.yaml changed, reloading...")
            self.manager._load()

# 启动监听
observer = Observer()
observer.schedule(ConfigReloadHandler(manager), path='config/')
observer.start()
```

---

## 五、迁移路径：从分散 YAML 到统一文件

### 5.1 迁移脚本

```python
#!/usr/bin/env python3
"""
migrate_agents.py
将 agents/ 目录下的分散 YAML 合并到 ai_providers.yaml
"""

import os
import yaml
from glob import glob
from datetime import datetime

def migrate():
    # 1. 读取现有的 ai_providers.yaml（只含 providers）
    with open('config/ai_providers.yaml', 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f) or {}

    # 2. 确保必要结构存在
    config.setdefault('version', '2.0')
    config.setdefault('last_updated', datetime.now().isoformat())
    config.setdefault('defaults', {
        'model': 'qwen3.7-max',
        'temperature': 0.7,
        'max_tokens': 4096
    })
    config.setdefault('agents', {})
    config.setdefault('loading', {'default_agent_id': None})

    # 3. 遍历 agents/ 目录
    agent_files = glob('config/agents/*.yaml')

    for filepath in agent_files:
        with open(filepath, 'r', encoding='utf-8') as f:
            agent = yaml.safe_load(f)

        agent_id = agent.get('agent_id')
        if not agent_id:
            print(f"Warning: {filepath} missing agent_id, skipping")
            continue

        # 转换旧格式到新格式
        config['agents'][agent_id] = {
            'enabled': True,
            'is_default': agent_id == 'agent-general',  # 假设通用助手是默认
            'name': agent.get('name', ''),
            'description': agent.get('description', ''),
            'avatar': agent.get('avatar', '🤖'),
            'color': agent.get('color', '#4f8ef7'),
            'category': agent.get('category', 'general'),
            'model': agent.get('model', config['defaults']['model']),
            'temperature': agent.get('temperature', config['defaults']['temperature']),
            'max_tokens': agent.get('max_tokens', config['defaults']['max_tokens']),
            'system_prompt': agent.get('system_prompt', ''),
            'welcome_message': agent.get('welcome_message', ''),
            'mcp_ids': agent.get('mcp_ids', []),
            'skill_ids': agent.get('skill_ids', []),
            'features': agent.get('features', {
                'web_search': False,
                'file_upload': False,
                'code_execution': False,
                'deep_thinking': False
            })
        }

        print(f"Migrated: {agent_id} from {filepath}")

    # 4. 设置默认 agent
    if config['agents']:
        default_candidates = [
            k for k, v in config['agents'].items() 
            if v.get('is_default') or 'general' in k
        ]
        config['loading']['default_agent_id'] = default_candidates[0] if default_candidates else list(config['agents'].keys())[0]

    # 5. 写回
    with open('config/ai_providers.yaml', 'w', encoding='utf-8') as f:
        yaml.dump(config, f, allow_unicode=True, sort_keys=False, width=120)

    print(f"\nDone! Migrated {len(agent_files)} agents to ai_providers.yaml")
    print(f"Default agent: {config['loading']['default_agent_id']}")
    print("\nNext steps:")
    print("  1. Review the generated ai_providers.yaml")
    print("  2. Remove the old agents/ directory")
    print("  3. Update backend to use AgentConfigManager")

if __name__ == '__main__':
    migrate()
```

### 5.2 迁移后目录结构

```
config/
├── ai_providers.yaml          # ← 唯一配置入口（agent + provider + loading）
├── mcp_servers.yaml           # MCP 服务配置（可后续也合并进来）
├── skills.yaml                # 技能配置
└── README.md                  # 配置说明

# 旧的 agents/ 目录已删除，所有 agent 定义在 ai_providers.yaml 的 agents 字段中
```

---

## 六、前端适配要点

### 6.1 读取 Agent 列表

```typescript
// 从统一配置读取
const getActiveAgents = async (): Promise<Agent[]> => {
  const res = await api.get('/agents');  // 后端从 ai_providers.yaml 读取
  return res.data.map((agent: any) => ({
    id: agent.agent_id,
    name: agent.name,
    avatar: agent.avatar,
    color: agent.color,
    category: agent.category,
    isDefault: agent.is_default,
    enabled: agent.enabled,
  }));
};
```

### 6.2 编辑后回写

```typescript
const saveAgent = async (agentId: string, updates: Partial<AgentConfig>) => {
  // 前端校验
  if (updates.system_prompt && updates.system_prompt.length > 8000) {
    message.error('系统提示词不能超过 8000 字符');
    return;
  }

  // 提交到后端，后端回写 ai_providers.yaml
  await api.put(`/agents/${agentId}`, updates);
  message.success('保存成功');
};
```

### 6.3 加载控制 UI

在管理后台增加"启用/停用"开关和"设为默认"按钮：

```
┌─ Agent 管理 ───────────────────────┐
│                                     │
│  🤖 通用助手    [默认] [停用] [编辑] │
│  🧬 RNA 专家              [停用] [编辑] │
│  🧪 ATAC 专家   [已停用]  [启用] [编辑]│
│  🔬 单细胞专家            [停用] [编辑] │
│                                     │
│  [+ 新建 Agent]                     │
└─────────────────────────────────────┘
```

---

## 七、与之前更新计划的衔接

本次架构重构与《AI 助手模块更新计划》的关系：

| 原 Phase | 内容 | 架构重构后的变化 |
|----------|------|----------------|
| Phase 1 | 编辑页面 UI 重构 | 编辑后通过 `AgentConfigManager` 回写 `ai_providers.yaml` |
| Phase 2 | 保存/停用修复 | 停用 = 设置 `enabled: false`，保存 = 更新 YAML 并原子写回 |
| Phase 3 | MCP 增强 | MCP 配置可独立为 `mcp_servers.yaml`，或后续合并进 `ai_providers.yaml` |
| Phase 4 | 后端模型 | 如果走 YAML 配置驱动，可**跳过数据库表**，直接读写 YAML |

### 关键决策点

**方案 A：YAML 配置驱动（推荐，适合当前阶段）**
- 所有配置在 `ai_providers.yaml` 中
- 后端启动时加载到内存
- 前端编辑后后端回写 YAML
- 优点：简单、版本可控（Git 管理）、无需数据库迁移
- 缺点：多实例部署时需要共享文件或改用数据库

**方案 B：数据库驱动（适合后期多用户/多实例）**
- `ai_providers.yaml` 作为初始配置模板
- 启动时导入数据库
- 前端编辑直接修改数据库
- 优点：支持多实例、并发编辑、用户级自定义
- 缺点：需要维护数据库模型和迁移脚本

> 建议现阶段用 **方案 A**，等用户量和实例数上来后再平滑迁移到方案 B（`AgentConfigManager` 的接口可以保持不变，底层实现从 YAML 切换到 DB）。

---

## 八、总结

| 决策 | 内容 |
|------|------|
| 统一文件 | `ai_providers.yaml` 包含 providers + agents + loading 策略 |
| Agent 定义 | 集中在 `agents` 字典中，key 为 `agent_id` |
| 加载控制 | `enabled` 控制是否启用，`loading.default_agent_id` 控制默认加载 |
| 编辑联动 | 前端编辑 → 后端 `AgentConfigManager` → 原子写回 YAML |
| 迁移路径 | 运行 `migrate_agents.py` 合并旧文件，然后删除 `agents/` 目录 |
| 扩展性 | 后续 MCP/skills 也可合并进来，成为平台唯一的配置入口 |

---

*方案由 Kimi 生成，可直接作为架构重构的 PRD 交付。*
