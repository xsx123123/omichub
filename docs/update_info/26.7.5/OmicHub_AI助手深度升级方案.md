# 🧠 OmicHub AI 助手深度升级方案

> **文档版本**: v1.0
> **目标模块**: AI 助手 · 多智能体
> **核心议题**: 聊天界面重构 / 模型切换 / 真正的 Agent 架构
> **交付形态**: 前端交互方案 + 后端架构设计 + 技术选型建议

---

## 一、问题诊断: 现在的 Agent 是什么

从当前截图和 yaml 配置来看, OmicHub 的 Agent 本质上是一个**角色模板(Role Template)**, 而非真正的自主智能体:

| 维度 | 现在的实现 | 真正的 Agent |
|------|-----------|-------------|
| **核心能力** | 预设系统提示词 + 欢迎语 | 自主感知、推理、规划、行动 |
| **记忆** | 单轮/多轮对话上下文 | 短期工作记忆 + 长期知识存储 |
| **工具** | 无(纯文本对话) | 可调用 API、执行代码、查询数据库、操作文件 |
| **规划** | 用户逐轮引导 | 自主将复杂任务分解为子任务并执行 |
| **协作** | 单角色单轮对话 | 多 Agent 角色协作完成复杂工作流 |
| **状态** | 无状态(每次请求独立) | 有状态(维护任务进度、中间结果) |

**结论**: 现在的 Agent 是 "会说话的助手", 真正的 Agent 是 "会干活的员工"。

---

## 二、Phase 1: 聊天界面优化(前端层)

### 2.1 用户输入去气泡化

当前用户输入使用蓝色气泡(右侧对齐), 与 AI 回复的白色卡片风格割裂。建议统一为**扁平文本流**风格。

#### 修改方案

```css
/* 用户消息样式 —— 与 AI 消息统一为文本流 */
.message-user {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 12px 16px;
  background: transparent;
  border-radius: 0;
  justify-content: flex-start;
}

.message-user .avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: linear-gradient(135deg, #4A6CF7, #6B4B96);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 14px;
  flex-shrink: 0;
}

.message-user .content {
  flex: 1;
  color: #1a1a1a;
  font-size: 14px;
  line-height: 1.7;
  background: none;
  box-shadow: none;
  padding: 0;
}

.message-user .meta {
  font-size: 11px;
  color: #999;
  margin-top: 4px;
}

/* AI 消息保持现有白色卡片风格, 微调以统一 */
.message-ai {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 16px;
  background: #ffffff;
  border-radius: 12px;
  border: 1px solid #f0f0f0;
  box-shadow: 0 1px 3px rgba(0,0,0,0.04);
  margin-bottom: 8px;
}

.message-ai .avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: linear-gradient(135deg, #667eea, #764ba2);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 14px;
  flex-shrink: 0;
}

.message-ai .content {
  flex: 1;
  color: #1a1a1a;
  font-size: 14px;
  line-height: 1.7;
}
```

#### 视觉对比

| 元素 | 修改前 | 修改后 |
|------|--------|--------|
| 用户消息 | 蓝色气泡, 右对齐 | 白色文本, 左对齐, 带用户头像 |
| AI 消息 | 白色卡片, 左对齐 | 白色卡片, 左对齐, 带 AI 头像(保持) |
| 整体感 | 像微信聊天 | 像 Notion/Claude 的文档流对话 |

> 建议: 用户头像使用用户昵称首字母或上传头像, AI 头像使用当前 Agent 的图标。

### 2.2 模型切换功能设计

当前模型显示为静态标签 qwen3.7-plus, 需要支持聊天过程中实时切换。

#### 交互方案 A: 顶部下拉切换(推荐)

```tsx
// 聊天界面顶部栏
<ChatHeader>
  <AgentInfo>
    <AgentAvatar src={agent.icon} />
    <AgentName>{agent.name}</AgentName>
  </AgentInfo>
  
  <ModelSelector>
    <Dropdown 
      value={currentModel}
      options={availableModels}
      onChange={handleModelSwitch}
      prefix={<ZapIcon size={14} />}
      suffix={<ChevronDown size={14} />}
    />
    {modelSwitched && (
      <SwitchNotice>
        已切换至 {currentModel.name}, 后续回复将使用该模型
      </SwitchNotice>
    )}
  </ModelSelector>
  
  <AgentCapabilityButton 
    icon={<Lightbulb size={16} />}
    onClick={showCapabilities}
  >
    查看该智能体能力
  </AgentCapabilityButton>
</ChatHeader>
```

#### 交互方案 B: 输入框快捷切换(备选)

在输入框下方工具栏增加模型切换按钮。

#### 后端逻辑

```python
# 伪代码: 模型切换 API
class ChatSession:
    def __init__(self, agent_config):
        self.agent_config = agent_config
        self.current_model = agent_config.default_model
        self.message_history = []
    
    def switch_model(self, new_model_id: str):
        # 1. 验证新模型是否在当前 agent 支持的模型列表中
        if new_model_id not in self.agent_config.allowed_models:
            raise ValueError(f"模型 {new_model_id} 不在该智能体的支持列表中")
        
        # 2. 切换模型
        old_model = self.current_model
        self.current_model = new_model_id
        
        # 3. 在消息历史中插入系统提示(可选)
        self.message_history.append({
            "role": "system",
            "content": f"[系统提示] 用户已将模型从 {old_model} 切换至 {new_model_id}"
        })
        
        return {"status": "success", "current_model": new_model_id}
    
    def chat(self, user_message: str):
        return llm_client.chat(
            model=self.current_model,
            messages=self.message_history,
            system_prompt=self.agent_config.system_prompt
        )
```

#### 数据模型扩展

```yaml
# agent 配置增加模型支持列表
meta:
  id: code_assistant
  name: "代码助手"
  color: "#4f8ef7"

model:
  default: "qwen3.7-plus"
  allowed:                          # 该 agent 支持切换的模型列表
    - "qwen3.7-plus"
    - "gpt-4o"
    - "claude-4.5-sonnet"
    - "deepseek-v3"
  switchable: true                  # 是否允许用户在聊天中切换
  
model_prompts:
  "gpt-4o": "你是一位精通 Python 和 R 的代码专家..."
  "claude-4.5-sonnet": "你是一位擅长代码审查和重构的专家..."
```

---

## 三、Phase 2: 真正的 Agent 架构(后端层)

### 3.1 真正的 Agent 需要具备什么

根据 2026 年主流 Agent 框架(LangGraph、CrewAI、AutoGPT)的架构共识, 真正的 Agent 必须具备以下核心组件:

| 组件 | 功能 | OmicHub 现状 |
|------|------|-------------|
| **感知层** | 接收用户输入、环境状态、工具返回结果 | 已有(用户消息) |
| **推理引擎** | LLM 进行思考、规划、决策 | 已有(模型调用) |
| **记忆系统** | 短期对话记忆 + 长期知识存储 | 仅有短期上下文 |
| **工具集成** | 调用外部 API、执行代码、查询数据库 | 暂无 |
| **规划模块** | 自主分解任务、制定执行计划 | 暂无 |
| **行动执行** | 执行工具调用、返回结果给用户 | 暂无 |
| **状态管理** | 维护任务进度、中间结果、循环控制 | 暂无 |
| **多 Agent 编排** | 多个专业 Agent 协作完成复杂任务 | 暂无 |
| **可观测性** | 日志、追踪、调试 Agent 行为 | 暂无 |

### 3.2 技术选型: 推荐 LangGraph + CrewAI 混合架构

#### 为什么不直接用 yaml 配置?

yaml 配置适合定义**角色属性**(名称、提示词、欢迎语), 但无法定义**行为逻辑**(何时调用工具、如何分解任务、如何管理状态)。真正的 Agent 需要代码级的编排能力。

#### 推荐架构: LangGraph 作为核心引擎

**LangGraph**(LangChain 生态)是 2026 年最成熟的 Agent 框架, 生产成功率达 94%, P99 延迟 2.1s。

```
                    OmicHub 平台前端
              (React + 聊天界面 + Agent 配置面板)
                              |
                              v
                  OmicHub API Gateway
         (统一路由 / 鉴权 / 会话管理 / 模型切换)
                              |
              +---------------+---------------+
              |               |               |
              v               v               v
    +--------------+ +--------------+ +--------------+
    |  简单对话模式  | |  Agent 模式   | |  多 Agent 模式 |
    |  (直接 LLM)   | | (LangGraph)  | |  (CrewAI)     |
    +--------------+ +--------------+ +--------------+
                              |
                              v
              LangGraph Agent Engine (Python)
  +---------+ +---------+ +---------+ +---------+
  | 感知节点 | | 推理节点 | | 工具节点 | | 记忆节点 |
  +---------+ +---------+ +---------+ +---------+
  +---------+ +---------+ +---------+
  | 规划节点 | | 执行节点 | | 状态管理 |
  +---------+ +---------+ +---------+
                              |
              +---------------+---------------+
              |               |               |
              v               v               v
    +--------------+ +--------------+ +--------------+
    |   LLM API    | |   工具集     | |  向量数据库   |
    | (qwen/gpt/   | | (代码执行/   | | (长期记忆)    |
    |  claude...)  | |  文件操作/   | |               |
    |              | |  API 调用)   | |               |
    +--------------+ +--------------+ +--------------+
```

#### 为什么不选其他框架?

| 框架 | 优点 | 缺点 | 适合场景 |
|------|------|------|----------|
| **LangGraph** | 状态管理最强、支持循环/分支、工具生态丰富 (700+)、可观测性好 | 学习曲线较陡 | **生产级 Agent, 复杂工作流** |
| **CrewAI** | 角色定义直观、代码量少、快速原型 | 状态管理较弱、不适合复杂逻辑 | 多 Agent 协作、内容生成 |
| **AutoGPT** | 完全自主、零人工干预 | 可靠性低 (45% 成功率)、Token 消耗高 | 实验性项目 |
| **AutoGen** | 对话式多 Agent、低延迟 | 生产稳定性差 (70% 成功率) | 研究场景 |
| **OpenClaw** | 本地优先、24/7 自主运行、消息平台集成 | 需要独立部署、与现有平台集成成本高 | 个人自动化助手 |

> 建议: 以 **LangGraph** 为主引擎, **CrewAI** 用于特定多 Agent 场景(如 "研究员 + 写手 + 审核" 的内容生成工作流)。

### 3.3 Agent 定义方式升级: 从 yaml 到代码 + 配置混合

#### 现有 yaml 的局限

```yaml
# 现在的配置只能定义"人设", 无法定义"行为"
meta:
  id: code_assistant
  name: "代码助手"
  system_prompt: "你是代码助手..."  # 只是静态提示词
  model: "qwen3.7-plus"
  # 无法定义: 何时调用代码执行器?
  # 无法定义: 如何分解复杂编程任务?
  # 无法定义: 出错时如何重试?
```

#### 升级方案: yaml 定义角色 + Python 定义行为

```yaml
# agents/code_assistant/config.yaml
meta:
  id: code_assistant
  name: "代码助手"
  color: "#4f8ef7"
  description: "擅长 Python/R 代码编写、调试和优化"
  category: "编程"

model:
  default: "qwen3.7-plus"
  allowed: ["qwen3.7-plus", "gpt-4o", "claude-4.5-sonnet"]
  switchable: true

agent:
  type: "langgraph"
  behavior_module: "code_agent"
  
  tools:
    - "code_executor"
    - "file_reader"
    - "file_writer"
    - "web_search"
    - "pip_install"
  
  memory:
    short_term: true
    long_term: true
    session_persistence: true
  
  planning:
    enabled: true
    max_iterations: 10
    allow_self_correction: true
```

```python
# agents/code_assistant/behavior.py
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolExecutor
from typing import TypedDict, Annotated
import operator

class AgentState(TypedDict):
    messages: Annotated[list, operator.add]
    next_step: str
    tool_calls: list
    iteration_count: int
    error_count: int

tools = [
    CodeExecutor(),
    FileManager(),
    WebSearch(),
    PackageInstaller()
]
tool_executor = ToolExecutor(tools)

def perception_node(state: AgentState):
    # 感知节点: 理解用户意图
    pass

def reasoning_node(state: AgentState):
    # 推理节点: LLM 思考下一步
    response = llm.invoke(state["messages"])
    pass

def tool_node(state: AgentState):
    # 工具节点: 执行工具调用
    pass

def planning_node(state: AgentState):
    # 规划节点: 分解复杂任务
    pass

workflow = StateGraph(AgentState)
workflow.add_node("perception", perception_node)
workflow.add_node("reasoning", reasoning_node)
workflow.add_node("tool", tool_node)
workflow.add_node("planning", planning_node)

workflow.set_entry_point("perception")
workflow.add_edge("perception", "planning")
workflow.add_conditional_edges(
    "planning",
    lambda state: "tool" if state["tool_calls"] else "reasoning"
)
workflow.add_conditional_edges(
    "reasoning",
    lambda state: END if state["next_step"] == "finish" else "tool"
)
workflow.add_edge("tool", "reasoning")

agent = workflow.compile()
```

### 3.4 与现有平台的集成方案

不需要推翻现有平台, 采用**渐进式增强**:

```
现有平台架构(保持不变)
+-- React 前端
+-- Node.js / Go API Gateway
+-- 用户系统、权限系统
+-- 数据管理、任务中心
+-- 模型调用层(直接调用 LLM API)
        |
        v
新增 Agent 服务层(Python 微服务)
+-- LangGraph Agent Engine
+-- 工具注册中心
+-- 向量数据库(ChromaDB / Milvus)
+-- 沙箱执行环境(Docker / gVisor)
        |
        v
通过 gRPC / REST 与现有平台通信
```

#### 通信协议

```protobuf
service AgentService {
  rpc CreateSession(CreateSessionRequest) returns (Session);
  rpc Chat(stream ChatMessage) returns (stream ChatChunk);
  rpc SwitchModel(SwitchModelRequest) returns (SwitchModelResponse);
  rpc GetExecutionState(SessionId) returns (ExecutionState);
  rpc ExecuteTool(ToolRequest) returns (ToolResult);
}

message ExecutionState {
  string current_node = 1;
  int32 iteration_count = 2;
  repeated string tool_calls = 3;
  string thought_process = 4;
}
```

### 3.5 用户可见的 Agent 能力升级

| 场景 | 现在的行为 | 升级后的行为 |
|------|----------|------------|
| **代码调试** | 给出文字建议 | 自动执行代码 -> 捕获错误 -> 分析堆栈 -> 修复 -> 验证 |
| **数据分析** | 给出分析思路 | 自动读取数据文件 -> 执行统计 -> 生成图表 -> 输出报告 |
| **文献检索** | 建议搜索关键词 | 自动联网搜索 -> 下载 PDF -> 提取关键信息 -> 生成综述 |
| **多步骤任务** | 用户逐轮引导 | Agent 自主规划步骤 -> 逐步执行 -> 汇总结果 |
| **错误处理** | 用户发现后反馈 | Agent 自我检测错误 -> 自动重试 -> 调整策略 |

#### 展示 Agent 思考过程(关键 UX)

```tsx
<ThinkingProcess>
  <ThinkingStep status="done" icon="">
    分析用户需求: 需要绘制差异表达基因火山图
  </ThinkingStep>
  <ThinkingStep status="done" icon="">
    读取文件: /data/deseq2_results.csv(12,340 行 x 8 列)
  </ThinkingStep>
  <ThinkingStep status="done" icon="">
    执行代码: 使用 ggplot2 绘制火山图...
  </ThinkingStep>
  <ThinkingStep status="done" icon="">
    生成结果: volcano_plot.png(已保存至 /output/)
  </ThinkingStep>
</ThinkingProcess>

<AIResponse>
  已为您生成差异表达基因火山图!
  <ImagePreview src="/output/volcano_plot.png" />
  <ActionButtons>
    <Button>下载图片</Button>
    <Button>查看代码</Button>
    <Button>重新绘制</Button>
  </ActionButtons>
</AIResponse>
```

---

## 四、Phase 3: 实施路线图

### 4.1 阶段划分

| 阶段 | 周期 | 目标 | 交付物 |
|------|------|------|--------|
| **Phase 1** | 1 周 | 聊天界面优化 | 去气泡化 UI、模型切换功能 |
| **Phase 2** | 2 周 | Agent 服务搭建 | Python 微服务、LangGraph 基础框架、工具注册中心 |
| **Phase 3** | 2 周 | 首个生产级 Agent | 代码助手升级(支持代码执行、调试、文件操作) |
| **Phase 4** | 2 周 | 多 Agent 协作 | 引入 CrewAI、支持 "研究员-写手-审核" 工作流 |
| **Phase 5** | 持续 | 生态扩展 | 更多工具、更多 Agent 角色、社区插件市场 |

### 4.2 技术栈建议

| 层级 | 技术选型 | 说明 |
|------|----------|------|
| Agent 引擎 | **LangGraph** + LangChain | 状态管理、工具调用、循环控制 |
| 多 Agent 编排 | **CrewAI** | 角色定义、协作流程 |
| 服务框架 | FastAPI | Python 异步 API, 性能优异 |
| 通信协议 | gRPC + REST | 流式对话用 gRPC, 简单调用用 REST |
| 向量数据库 | ChromaDB / Milvus | 长期记忆存储 |
| 代码沙箱 | Docker + gVisor | 安全执行用户代码 |
| 可观测性 | LangSmith / OpenTelemetry | Agent 执行追踪、调试 |
| 部署 | Docker Compose / K8s | 容器化部署 |

### 4.3 风险与应对

| 风险 | 影响 | 应对策略 |
|------|------|----------|
| LangGraph 学习曲线陡 | 开发周期延长 | 先实现简单 ReAct Agent, 再逐步引入复杂状态图 |
| 代码执行安全风险 | 系统被攻击 | 使用 gVisor 沙箱 + 资源限制 + 超时控制 |
| Token 消耗激增 | 成本上升 | 设置迭代上限、引入缓存机制、支持用户选择 "简单模式/Agent 模式" |
| 与现有平台耦合 | 重构成本高 | 保持 Agent 服务独立, 通过 API 通信, 现有平台改动最小化 |

---

## 五、总结与建议

### 5.1 三个问题的回答

1. **聊天界面去气泡**: 用户消息改为左对齐文本流, 与 AI 消息风格统一, 增加用户头像, 去掉蓝色气泡背景。

2. **模型切换**: 在聊天顶部增加下拉选择器, 支持在对话过程中切换模型, 后端保留历史上下文并插入切换提示。

3. **真正的 Agent**:
   - 现在的 yaml 配置只是**角色模板**, 不是真正的 Agent。
   - 建议引入 **LangGraph** 作为 Agent 引擎, 独立部署为 Python 微服务。
   - 通过 gRPC/REST 与现有平台通信, 渐进式增强而非推翻重建。
   - 首个落地场景建议升级"代码助手", 赋予其代码执行、调试、文件操作能力。

### 5.2 下一步行动

1. **立即执行**: 修改前端聊天界面样式(去气泡 + 模型切换 UI)
2. **本周启动**: 搭建 LangGraph 基础服务框架, 实现最简单的 ReAct Agent
3. **两周内**: 将"代码助手"升级为真正的 Agent(支持代码执行和调试)
4. **一个月内**: 验证架构可行性, 决定是否扩展到其他 Agent 角色

---

*文档由 OmicHub 技术委员会(阿姨)编制*
*Agent 不是会说话的助手, 而是会干活的员工。*