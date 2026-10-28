# AI Agent工具调用架构深度调研报告

> 调研时间：2025年7月
> 调研目的：为OmicHub平台AI助手与生信工具联动架构设计提供决策依据
> 核心问题：已有Agentic对话流（SSE流式、MCP builtin/stdio/sse、8轮tool闭环），如何设计工具箱对LLM的可见性联动层

---

## 目录

1. [MCP (Model Context Protocol) 生态](#1-mcp-model-context-protocol-生态)
2. [OpenAI Function Calling 演进](#2-openai-function-calling-演进)
3. [Anthropic Claude Tool Use / Computer Use](#3-anthropic-claude-tool-use--computer-use)
4. [LangChain / LlamaIndex 工具抽象](#4-langchain--llamaindex-工具抽象)
5. [GitHub Copilot Chat / Cursor 工具集成](#5-github-copilot-chat--cursor-工具集成)
6. [结果回传与渲染方案](#6-结果回传与渲染方案)
7. [跨架构对比总结表](#7-跨架构对比总结表)
8. [对OmicHub的具体建议](#8-对omichub的具体建议)

---

## 1. MCP (Model Context Protocol) 生态

### 核心设计

**MCP (Model Context Protocol)** 是由Anthropic于2024年11月推出的开放协议，旨在解决AI应用与外部工具/数据源之间的N*M集成问题。MCP采用JSON-RPC 2.0作为底层传输协议，定义了标准化的能力发现、调用和结果回传机制。

**协议版本演进：**
| 版本 | 时间 | 关键特性 |
|------|------|----------|
| 2024-11-05 | 初始稳定版 | Tools基础能力 |
| 2025-03-26 | Streamable HTTP | 替换旧HTTP+SSE双端点设计 |
| 2025-06-18 | Stable | 结构化工具输出、Elicitation、Resource Links |
| 2025-11-25 | Latest Stable | OpenID Connect Discovery、工具图标元数据、Tasks(实验性) |

**MCP四大核心能力原语：**

1. **Tools（工具）** - 可被LLM调用的动作/函数，如查询数据库、运行代码、调用API
2. **Resources（资源）** - 只读的数据上下文，如文件内容、数据库记录、文档
3. **Prompts（提示模板）** - 可复用的提示模板，客户端可填充参数后使用
4. **Sampling（采样）** - 服务端可请求客户端LLM进行推理，实现双向交互

**MCP架构设计哲学：**
- **完全解耦**：Server不知道哪个LLM在使用它，Client不知道Tool的内部实现
- **能力协商**：初始化时通过`initialize`方法交换capabilities（clientCapabilities/serverCapabilities）
- **持续会话**：MCP设计为长连接协议，支持Progress通知、Cancellation、ListChanged事件
- **生命周期管理**：明确的连接建立、初始化、运行、关闭流程

### Tool Schema定义方式

MCP Tool的Schema采用JSON Schema格式，在2025-06-18版本后支持结构化输出定义：

```json
{
  "name": "run_differential_expression",
  "title": "差异表达分析",
  "description": "对基因表达矩阵进行差异表达分析，返回显著差异基因列表",
  "inputSchema": {
    "type": "object",
    "properties": {
      "expression_matrix": { "type": "string", "description": "表达矩阵文件路径" },
      "group_A": { "type": "array", "items": { "type": "string" }, "description": "样本组A" },
      "group_B": { "type": "array", "items": { "type": "string" }, "description": "样本组B" },
      "method": { "type": "string", "enum": ["DESeq2", "edgeR", "limma"], "default": "DESeq2" }
    },
    "required": ["expression_matrix", "group_A", "group_B"]
  },
  "outputSchema": {
    "type": "object",
    "properties": {
      "significant_genes": { "type": "array", "description": "显著差异基因列表" },
      "p_values": { "type": "object", "description": "基因到p值的映射" },
      "volcano_plot": { "type": "string", "description": "火山图base64编码" }
    }
  },
  "annotations": {
    "readOnlyHint": false,
    "title": "差异表达分析",
    "openWorld": false
  }
}
```

**关键设计细节：**
- `inputSchema` 使用标准JSON Schema Draft 2020-12
- `outputSchema` 为可选字段（2025-06-18+），客户端可据此验证输出
- `annotations` 提供工具行为元数据（是否只读、是否幂等、是否需要确认）
- `name` 必须符合 `^[a-zA-Z0-9_-]{1,64}$` 正则
- 支持 `listChanged` 通知，Server可在工具列表变更时主动推送

### 工具调用流程

**完整数据流（从发现到结果回传）：**

```
1. 连接建立
   Client ──transport(stdio/sse/http)──> Server

2. 能力协商
   Client: {jsonrpc:"2.0", method:"initialize", params:{protocolVersion:"2025-06-18", capabilities:{sampling:{},roots:{}}, clientInfo:{name:"OmicHub",version:"1.0"}}}
   Server: {protocolVersion:"2025-06-18", capabilities:{tools:{listChanged:true},resources:{subscribe:true},prompts:{listChanged:true}}, serverInfo:{name:"bioinfo-tools",version:"2.1"}}

3. 工具发现
   Client: {method:"tools/list", params:{cursor?}}
   Server: {tools:[{name:"run_de", inputSchema:{...}}, {name:"pathway_enrichment", inputSchema:{...}}], nextCursor?}

4. LLM决策调用
   Client将tools列表转换为LLM的tools参数（如OpenAI格式）
   LLM返回tool_calls决策

5. 工具执行
   Client: {method:"tools/call", params:{name:"run_de", arguments:{expression_matrix:"data.csv", group_A:["S1","S2"], group_B:["S3","S4"]}}}
   Server: 执行实际计算...

6. 结果回传
   Server: {content:[{type:"text",text:"差异表达分析完成..."}, {type:"image",data:"base64...",mimeType:"image/png"}], isError:false, structuredContent:{significant_genes:["BRCA1","TP53"],p_values:{...}}}

7. 上下文管理
   Client将tool_result格式化为LLM消息格式，追加到对话历史
   重复步骤4-7直到LLM不再调用工具
```

### 大结果/异步处理

**MCP对异步/大结果的支持机制：**

1. **Progress通知**：长时间运行的工具可通过`notifications/progress`向客户端发送进度更新
2. **Cancellation**：客户端可通过`notifications/cancel`取消正在执行的工具调用
3. **Pagination**：工具/资源列表通过cursor分页，避免单次传输过大
4. **结构化内容分离**：`content`（展示给模型）与`structuredContent`（机器可读结构化数据）分离，避免大JSON浪费token
5. **Resource Links**：工具结果可引用外部资源而非内联全部内容

**Transport选择对异步的影响：**
| Transport | 适用场景 | 异步支持 | 连接模型 |
|-----------|----------|----------|----------|
| **builtin** | 同进程内调用 | 最佳 | 函数调用 |
| **stdio** | 本地CLI工具 | 有限 | 1进程/1用户 |
| **SSE** | 远程服务（旧版） | 好 | 长连接流 |
| **Streamable HTTP** | 远程服务（推荐） | 最好 | HTTP POST+GET复用 |

**关键演进：** 旧版HTTP+SSE双端点设计已被Streamable HTTP（2025-03-26+）取代，Streamable HTTP在一个端点上同时支持POST请求和GET流式响应。

### 实际Adoption情况

**采用数据（截至2025年中）：**
- MCP Server下载量：从2024年11月的~10万增长到2025年4月的超800万
- 已编目MCP Server：~14,000个，MCP Client：~300个
- 80%的头部Server支持远程部署
- 超80%的Fortune 500公司在生产中部署AI Agent
- 2025年12月捐赠给Linux Foundation的Agentic AI Foundation

**已支持MCP的主要产品/平台：**
| 产品/公司 | MCP支持方式 | 来源 |
|-----------|-------------|------|
| Claude Desktop / Claude Code | 原生MCP Client，参考实现 | Anthropic官方 |
| OpenAI / ChatGPT | Responses API支持remote MCP servers | OpenAI MCP文档 |
| Google Gemini | Gemini SDK支持MCP tools | Google Agent Builder |
| Microsoft Copilot Studio | Streamable transport连接MCP | Microsoft Learn |
| GitHub | 官方GitHub MCP Server | GitHub Changelog |
| VS Code | MCP Client支持 | Microsoft |
| Cursor | MCP tools支持（40工具限制） | Cursor文档 |
| Vercel | MCP server部署 + AI SDK MCP client | Vercel |
| Block | 大规模生产部署（50-75%效率提升） | 公开报道 |
| Bloomberg / Amazon | 企业级部署 | 行业报告 |

### 与OmicHub的适配评估

**适配度：★★★★★（极高）**

OmicHub已经具备MCP builtin/stdio/sse三种transport的支持，8轮tool闭环的agentic对话流，这是非常好的基础。当前disconnect仅在于"工具箱对LLM不可见"，而MCP正好提供了标准化的工具发现（tools/list）和调用（tools/call）机制。

**具体原因：**
1. OmicHub已有SSE流式架构，与MCP Streamable HTTP天然兼容
2. 生信工具（DESeq2、STAR、GATK等）可以包装为MCP Server
3. 平台型持续会话场景是MCP的核心设计目标
4. MCP的工具schema标准化解决了"工具箱对LLM不可见"的问题

### 可借鉴的具体设计

1. **Capability Negotiation（能力协商）模式**：初始化时交换capabilities的设计值得借鉴，OmicHub可以在对话开始时就确定可用的工具集、支持的特性（如progress通知、cancellation），避免后续假设不一致

2. **Content + StructuredContent分离**：MCP将展示内容（给人/模型看）与结构化数据（给下游处理）分离的设计，非常适合生信场景——大的表达矩阵作为structuredContent传递，文本摘要作为content给模型

3. **Tool Annotations（工具元数据标注）**：`readOnlyHint`、`destructiveHint`、`idempotent`等标注让客户端知道何时需要用户确认，这在生信分析中很重要（如写文件、删除数据等操作需要用户确认）

---

## 2. OpenAI Function Calling 演进

### 核心设计

OpenAI的工具调用能力经历了从`functions`到`tools`的演进，并在2025年3月推出**Responses API**作为新的统一原语。

**演进时间线：**
| 时间 | 版本/特性 | 关键变化 |
|------|-----------|----------|
| 2023.06 | Function Calling v1 | `functions`参数 + `function_call` |
| 2023.12 | Tool Calling | `tools`参数 + `tool_choice`，支持并行调用 |
| 2024 | Streaming tool calls | 流式工具调用增量传输 |
| 2025.03 | Responses API | 统一原语，内置工具，stateful对话 |
| 2025.04+ | MCP Support | Responses API支持remote MCP servers |

**核心协议设计（Chat Completions API）：**

请求中通过`tools`数组定义可用工具：
```json
{
  "model": "gpt-4o",
  "messages": [{"role": "user", "content": "分析GSE12345的差异表达基因"}],
  "tools": [
    {
      "type": "function",
      "function": {
        "name": "run_deseq2",
        "description": "使用DESeq2进行差异表达分析",
        "parameters": {
          "type": "object",
          "properties": {
            "counts_file": {"type": "string", "description": "基因计数矩阵文件路径"},
            "metadata_file": {"type": "string", "description": "样本分组信息文件"},
            "design_formula": {"type": "string", "default": "~condition"}
          },
          "required": ["counts_file", "metadata_file"]
        },
        "strict": true
      }
    }
  ],
  "tool_choice": "auto",
  "parallel_tool_calls": true
}
```

**Responses API的新设计：**
```json
{
  "model": "gpt-5",
  "tools": [
    {"type": "function", "function": {"name": "run_deseq2", "parameters": {...}}},
    {"type": "web_search"},
    {"type": "file_search", "vector_store_ids": ["vs_xxx"]}
  ],
  "input": "分析GSE12345的差异表达基因",
  "previous_response_id": "resp_xxx"
}
```

### Tool Schema定义方式

OpenAI使用JSON Schema定义工具参数，支持以下特性：

- **标准JSON Schema Draft 7+**：`type`、`properties`、`required`、`enum`、`description`
- **`strict`模式**：启用后模型严格遵循schema，减少幻觉参数
- **`additionalProperties: false`**：strict模式下自动设置
- **嵌套对象**：支持复杂嵌套结构
- **数组类型**：支持`items`定义
- **不支持**：`oneOf`（复杂场景需要workaround）、递归schema

**工具类型扩展：**
| 工具类型 | 说明 | API |
|----------|------|-----|
| `function` | 开发者定义的函数 | Chat/Responses |
| `web_search` | 内置网络搜索 | Responses API |
| `file_search` | 向量存储检索 | Responses API |
| `code_interpreter` | 沙箱Python执行 | Responses API |
| `computer_use` | 浏览器/桌面控制 | Responses API (preview) |
| `mcp` | 远程MCP服务器 | Responses API |

### 工具调用流程

**完整数据流：**

```
Step 1: 请求发送
  Client ──POST /v1/chat/completions──> OpenAI API
  包含tools定义 + messages历史

Step 2: LLM决策（Tool Choice）
  API返回choices[0].message:
    - content: null（如仅调用工具）
    - tool_calls: [
        {
          "id": "call_abc123",
          "type": "function",
          "function": {
            "name": "run_deseq2",
            "arguments": "{\"counts_file\":\"/data/counts.csv\",\"metadata_file\":\"/data/meta.csv\"}"
          }
        }
      ]
    - finish_reason: "tool_calls"

Step 3: 工具执行（Client端）
  Client解析tool_calls，按name路由到对应函数
  执行run_deseq2函数，获取结果

Step 4: 结果回传
  Client将结果作为tool消息追加：
  messages.append({
    "role": "tool",
    "tool_call_id": "call_abc123",
    "content": JSON.stringify({significant_genes: [...], plot_url: "..."})
  })

Step 5: 下一轮决策
  Client重新发送完整messages（包含tool结果）
  LLM决定：再次调用工具 或 返回最终答案

Step 6: 最终结果
  API返回content文本，finish_reason="stop"
```

**Streaming Tool Calls的增量传输：**
```
data: {"choices":[{"delta":{"role":"assistant","content":null,"tool_calls":[{"index":0,"id":"call_abc","type":"function","function":{"name":"run_deseq2","arguments":""}}]},"finish_reason":null}]}

data: {"choices":[{"delta":{"tool_calls":[{"index":0,"function":{"arguments":"{\"counts"}}]},"finish_reason":null}]}

data: {"choices":[{"delta":{"tool_calls":[{"index":0,"function":{"arguments":"_file\":\""}}]},"finish_reason":null}]}
...（逐字符/逐字段传输arguments JSON）...

data: {"choices":[{"delta":{},"finish_reason":"tool_calls"}]}
data: [DONE]
```

关键规则：
- 第一个chunk包含`id`、`type`、`function.name`
- 后续chunk只包含`function.arguments`增量（前序chunk的name为null）
- 最后以`finish_reason="tool_calls"`的chunk结束

### 大结果/异步处理

OpenAI原生API对大结果的处理有限，主要依靠客户端策略：

1. **结果截断**：大结果在客户端截断或摘要后再传入context
2. **文件引用**：工具返回文件URL/引用而非完整内容
3. **Streaming实时渲染**：客户端可实时显示流式返回的文本
4. **内置工具的stateful处理**：Code Interpreter/File Search在服务端管理状态

**Responses API的改进：**
- `previous_response_id`支持轻量级状态保持
- 内置`code_interpreter`支持长时间运行（session级别）
- `background`模式支持最长10分钟的任务
- 40-80%的缓存利用率提升

### 与OmicHub的适配评估

**适配度：★★★★☆（很高）**

OmicHub已经使用OpenAI格式的tools/function calling，这是非常好的对齐。Responses API的stateful特性和内置工具（code_interpreter、file_search）对生信分析场景很有价值。

**适配优势：**
- 现有OpenAI格式工具调用无需大改
- Responses API的stateful特性减少上下文传输
- 内置code_interpreter可辅助生信数据探索
- MCP server可通过Responses API接入

**注意事项：**
- OpenAI格式需要转换层才能给其他模型（Claude、Gemini）使用
- 大结果处理主要依赖客户端策略
- 严格的JSON Schema子集可能限制复杂工具定义

### 可借鉴的具体设计

1. **Streaming tool_calls增量传输协议**：OpenAI定义的流式工具调用分片传输格式（index-based增量arguments）已成为事实标准，LangChain、LlamaIndex等都基于此格式做适配

2. **`strict`模式保证schema遵循**：启用strict后模型严格按schema输出参数，减少参数幻觉，这对生信分析中精确的参数传递很重要

3. **Tool types扩展模式**：从纯function扩展到web_search、file_search、code_interpreter等多种工具类型，OmicHub可借鉴设计内置工具类型（如`bio_database_search`、`expression_analysis`等）

---

## 3. Anthropic Claude Tool Use / Computer Use

### 核心设计

Anthropic的Tool Use是与OpenAI Function Calling对标的工具调用机制，但在协议格式上有显著差异。Anthropic使用基于content blocks的消息格式，工具调用和结果都以typed content blocks的形式嵌入对话。

**核心协议格式：**

```python
# 工具定义（传给API的tools参数）
tools = [
    {
        "name": "run_deseq2_analysis",
        "description": "使用DESeq2进行差异表达分析，返回差异基因列表和统计结果",
        "input_schema": {
            "type": "object",
            "properties": {
                "counts_matrix": {"type": "string", "description": "基因计数矩阵文件路径"},
                "sample_groups": {
                    "type": "object",
                    "properties": {
                        "treatment": {"type": "array", "items": {"type": "string"}},
                        "control": {"type": "array", "items": {"type": "string"}}
                    },
                    "required": ["treatment", "control"]
                },
                "padj_threshold": {"type": "number", "default": 0.05}
            },
            "required": ["counts_matrix", "sample_groups"]
        }
    }
]

# 工具调用（LLM返回的tool_use block）
{
    "role": "assistant",
    "content": [
        {
            "type": "tool_use",
            "id": "toolu_01THXXX",
            "name": "run_deseq2_analysis",
            "input": {
                "counts_matrix": "/data/counts.csv",
                "sample_groups": {"treatment": ["S1", "S2"], "control": ["S3", "S4"]}
            }
        }
    ]
}

# 工具结果回传（tool_result block）
{
    "role": "user",
    "content": [
        {
            "type": "tool_result",
            "tool_use_id": "toolu_01THXXX",
            "content": "差异表达分析完成。共鉴定出1,247个显著差异表达基因（padj<0.05），其中上调基因523个，下调基因724个。",
            "is_error": False
        }
    ]
}
```

### Tool Schema定义方式

Claude的`input_schema`本质上是JSON Schema，但有以下特点：

- **必须使用JSON Schema**：所有工具参数必须通过`input_schema`定义
- **`strict`模式支持**：支持`strict: true`启用更严格的schema验证
- **Strict限制**：strict模式下不支持`minimum/maximum`、`minLength/maxLength`、`pattern`等数值/字符串约束
- **类型支持**：`object`、`array`、`string`、`integer`、`number`、`boolean`、`null`、`enum`、`const`、`anyOf`/`allOf`、`$ref`/`$defs`
- **描述至关重要**：Anthropic文档明确说明description是工具使用正确性的最重要因素

**tool_choice控制：**
| 值 | 行为 |
|----|------|
| `auto`（默认） | Claude自行决定是否调用工具 |
| `any` | 强制调用至少一个工具 |
| `tool` | 强制调用指定工具 |
| `none` | 禁止调用工具 |
| `disable_parallel_tool_use: true` | 限制每轮最多一个工具调用 |

### 工具调用流程

**Claude Tool Use Loop（与OpenAI的关键差异）：**

```
1. 发送用户消息 + tools定义
   POST /v1/messages
   {model:"claude-sonnet-4", max_tokens:4096, tools:[...], messages:[{role:"user",content:"分析GSE12345"}]}

2. Claude决策返回
   {
     content: [
       {type:"text", text:"我来为您进行差异表达分析。"},
       {type:"tool_use", id:"toolu_01XXX", name:"run_deseq2_analysis", input:{...}}
     ],
     stop_reason: "tool_use",
     usage: {...}
   }

   ★ 关键差异：Claude可以同时在content中返回text + tool_use blocks
   ★ OpenAI在tool_calls时content通常为null

3. 客户端执行工具
   执行run_deseq2_analysis，获取结果

4. 回传工具结果
   必须将assistant的完整content原样追加到messages：
   messages.append({role:"assistant", content:response.content})
   messages.append({
     role:"user",
     content:[{type:"tool_result", tool_use_id:"toolu_01XXX", content:"结果...", is_error:false}]
   })

   ★ 关键差异：必须原样保留assistant content（包括text+tool_use blocks）

5. 获取最终响应
   重新发送messages，Claude基于tool_result生成最终回答
```

**与OpenAI的核心差异对比：**

| 维度 | OpenAI | Anthropic Claude |
|------|--------|------------------|
| 参数名 | `parameters` | `input_schema` |
| 工具调用结构 | `tool_calls`数组在message上 | `tool_use` content blocks |
| 工具结果结构 | `role:"tool"` + `tool_call_id` | `tool_result` content block |
| 文本+工具混合 | content通常为null | 支持text+tool_use同时返回 |
| 错误处理 | 客户端控制 | `is_error: true`原生支持 |
| 并行调用 | `parallel_tool_calls`参数 | `disable_parallel_tool_use`参数 |
| Schema约束 | 相对宽松 | strict模式约束更严格 |

### Computer Use 特殊设计

Computer Use是Anthropic特有的API级计算机控制能力，设计为一个特殊的beta tool：

```python
# Computer Use工具定义
tools = [
    {
        "type": "computer_20251124",
        "name": "computer",
        "display_width_px": 1920,
        "display_height_px": 1080,
        "display_number": 1
    }
]
```

**Computer Use核心循环：**
```
Loop:
  1. 截图当前屏幕
  2. 发送给Claude（带任务上下文）
  3. Claude分析截图，返回action：
     - click(x, y)       - 鼠标点击
     - type("text")      - 键盘输入
     - key("Enter")      - 特殊按键
     - screenshot()      - 重新截图
  4. 执行action
  5. 返回tool_result（新截图或执行结果）
  6. 循环直到任务完成
```

**关键设计约束：**
- 额外token开销：466-499系统提示token + 735工具定义token
- 截图分析有最大尺寸限制，需要坐标缩放映射
- 需要专用VM/容器运行（安全建议）
- 支持版本：computer-use-2025-11-24（Claude 4.6）、computer-use-2025-01-24（Claude 4.5）

**Computer Use vs API vs Product路线：**
| 路线 | 控制方 | 适用场景 |
|------|--------|----------|
| API Computer Use | 开发者控制VM和loop | 构建自动化产品 |
| Claude Code | Anthropic桌面产品管理 | 本地开发任务 |
| Cowork | Anthropic桌面产品管理 | 通用桌面任务委托 |

### 大结果/异步处理

Claude对大结果的处理：

1. **100+工具路由模式**：Claude Code内部使用两阶段路由——第一阶段选择工具类别，第二阶段暴露该类别的工具
2. **tool_result content截断**：大结果应在客户端截断或摘要
3. **错误作为数据**：通过`is_error: true`标记，让模型自己决定如何恢复
4. **采样（Sampling）**：MCP server可请求客户端LLM完成，实现嵌套推理
5. **Thinking/Extended Thinking**：支持reasoning过程，可在工具调用前进行深度推理

### 与OmicHub的适配评估

**适配度：★★★★☆（很高）**

Claude的Tool Use在功能上与OpenAI Function Calling对等，但格式不同。OmicHub支持OpenAI格式，需要转换层来支持Claude原生格式。

**适配优势：**
- MCP作为中间层可屏蔽OpenAI/Claude格式差异
- Claude的text+tool_use混合返回提供更好的用户体验
- `is_error`原生错误处理简化错误传播

**适配挑战：**
- 需要message格式转换层（OpenAI<->Anthropic）
- 100+工具时的两阶段路由模式值得借鉴
- Strict schema约束可能需要调整现有工具定义

### 可借鉴的具体设计

1. **Text + Tool Use混合返回**：Claude允许在同一个response中返回解释文本+工具调用，用户体验更好。OmicHub可在展示层支持这种模式（即使后端模型是OpenAI格式，也可在渲染时分离说明文本和工具调用UI）

2. **两阶段工具路由（100+工具场景）**：Claude Code处理大量工具时采用"先选类别再选工具"的两阶段路由，OmicHub若有大量生信工具时可借鉴（如先选"测序分析"类别，再暴露该类别下的具体工具）

3. **`is_error`语义化错误传播**：Claude的`is_error`标记让模型能区分正常结果和错误，自主决定重试或解释。OmicHub应在tool result中引入类似的错误语义标记



---

## 4. LangChain / LlamaIndex 工具抽象

### 核心设计

**LangChain** 是Python/JS生态中最流行的LLM应用框架，提供了标准化的工具抽象层，使开发者可以定义一次工具并在多个模型提供商间复用。

**LangChain工具栈核心组件：**

```python
from langchain_core.tools import tool, BaseTool, StructuredTool
from langgraph.prebuilt import ToolNode, create_react_agent

# 方式1: @tool装饰器（最简单）
@tool
def run_deseq2(counts_file: str, metadata_file: str, design_formula: str = "~condition") -> dict:
    """使用DESeq2进行差异表达分析。
    
    Args:
        counts_file: 基因计数矩阵文件路径（CSV格式）
        metadata_file: 样本分组信息文件路径
        design_formula: 设计公式，默认为~condition
    
    Returns:
        包含差异基因列表、统计结果和可视化路径的字典
    """
    # 实际分析逻辑
    return {"significant_genes": [...], "plot_path": "/results/volcano.png"}

# 方式2: StructuredTool（完全控制）
deseq2_tool = StructuredTool.from_function(
    func=run_deseq2_impl,
    name="run_deseq2",
    description="使用DESeq2进行差异表达分析",
    args_schema=DESeq2InputSchema,  # Pydantic BaseModel
    return_direct=False,  # 结果是否直接返回（不经过LLM重写）
    response_format="content_and_artifact"  # 内容+结构化数据分离
)

# 方式3: 继承BaseTool（最灵活）
class DESeq2Tool(BaseTool):
    name: str = "run_deseq2"
    description: str = "DESeq2差异表达分析工具"
    args_schema: type[BaseModel] = DESeq2InputSchema
    
    def _run(self, counts_file: str, metadata_file: str, **kwargs) -> str:
        # 同步执行
        return "..."
    
    async def _arun(self, counts_file: str, metadata_file: str, **kwargs) -> str:
        # 异步执行
        return "..."
```

**`bind_tools` 方法：**

`bind_tools` 是LangChain ChatModel上的核心方法，将工具定义绑定到模型实例：

```python
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic

# 工具列表（provider无关）
tools = [run_deseq2, run_enrichment, get_gene_info]

# OpenAI模型绑定
openai_model = ChatOpenAI(model="gpt-4o").bind_tools(
    tools,
    tool_choice="auto",  # "auto" | "none" | "required" | "<tool_name>"
    parallel_tool_calls=True
)

# Anthropic模型绑定（同一套工具）
claude_model = ChatAnthropic(model="claude-sonnet-4").bind_tools(
    tools,
    tool_choice="auto",
    disable_parallel_tool_use=False
)

# 调用返回AIMessage，通过tool_calls属性访问工具调用
response = openai_model.invoke("分析GSE12345的差异表达基因")
print(response.tool_calls)  # [{"name": "run_deseq2", "args": {...}, "id": "call_xxx"}]
```

### Tool Schema定义方式

LangChain支持多种工具schema定义方式：

| 方式 | 输入 | 自动转换 | 适用场景 |
|------|------|----------|----------|
| `@tool`装饰器 | 函数签名+docstring | 自动推断JSON Schema | 快速原型 |
| `StructuredTool.from_function` | Pydantic `BaseModel` | 通过`args_schema` | 生产级 |
| 继承`BaseTool` | 完整控制 | 手动定义 | 复杂逻辑 |
| 字典格式 | OpenAI格式dict | 直接传递 | 兼容层 |

**自动JSON Schema转换：**
LangChain通过`convert_to_openai_tool()`将Python函数/Pydantic模型自动转换为OpenAI格式的工具schema：
```python
from langchain_core.utils.function_calling import convert_to_openai_tool

tool_schema = convert_to_openai_tool(run_deseq2)
# 输出:
# {
#   "type": "function",
#   "function": {
#     "name": "run_deseq2",
#     "description": "使用DESeq2进行差异表达分析...",
#     "parameters": {"type": "object", "properties": {...}, "required": [...]}
#   }
# }
```

### 工具注册与路由器模式

**LangGraph的ToolNode架构：**

```python
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.graph import StateGraph, MessagesState, START, END

# 工具注册
tools = [run_deseq2, run_enrichment, get_gene_info]
tool_node = ToolNode(tools)

# 构建Agent图
builder = StateGraph(MessagesState)
builder.add_node("agent", model_with_tools)  # LLM决策节点
builder.add_node("tools", tool_node)         # 工具执行节点

builder.add_edge(START, "agent")
builder.add_conditional_edges("agent", tools_condition, {"tools": "tools", END: END})
builder.add_edge("tools", "agent")  # 工具结果回到LLM

agent = builder.compile()
```

**ToolNode核心行为：**
1. **自动分发**：根据`AIMessage.tool_calls`中的`name`匹配工具
2. **并行执行**：同一消息中的多个tool_calls使用`ThreadPoolExecutor`并发执行
3. **错误处理**：工具异常被捕获并包装为包含错误信息的`ToolMessage`
4. **消息关联**：每个`ToolMessage`携带匹配的`tool_call_id`

**路由模式（Router Pattern）：**

```python
# 多Agent路由：先选择工具类别，再调用具体工具
def router_agent(state: MessagesState):
    """根据用户意图选择工具类别"""
    category_model = llm.bind_tools([select_category_tool])
    response = category_model.invoke(state["messages"])
    category = response.tool_calls[0]["args"]["category"]
    return category  # "sequencing" | "expression" | "pathway"

# 条件路由
builder.add_conditional_edges("router", router_agent, {
    "sequencing": "seq_tools",
    "expression": "expr_tools", 
    "pathway": "pathway_tools"
})
```

### 工具调用流程

**LangChain/LangGraph完整数据流：**

```
1. 工具定义（开发者）
   @tool装饰函数 → 自动生成JSON Schema → bind_tools绑定到模型

2. LLM决策
   model_with_tools.invoke(messages) → 返回AIMessage
   AIMessage.tool_calls = [{name, args, id}, ...]
   AIMessage.content = "说明文本"（可选）

3. 工具执行（ToolNode）
   for each tool_call in parallel:
     - 查找匹配的工具（by name）
     - 调用工具函数（**args解包）
     - 包装结果为ToolMessage（tool_call_id关联）
   return list[ToolMessage]

4. 消息状态更新
   MessagesState.messages += ToolMessages
   add_messages reducer自动去重（by id）

5. 循环决策
   tools_condition检查最后一条消息：
   - 如有tool_calls → 路由到tools节点
   - 否则 → END

6. 上下文管理
   LangGraph checkpointer保存super-step边界状态
   支持中断、恢复、重试
```

**流式工具调用支持：**
```python
# 流式执行
async for event in agent.astream_events(messages, version="v2"):
    if event["event"] == "on_tool_start":
        print(f"开始执行: {event['name']}")
    elif event["event"] == "on_tool_end":
        print(f"执行完成: {event['data']['output']}")
    elif event["event"] == "on_chat_model_stream":
        print(event["data"]["chunk"].content, end="")
```

### 大结果/异步处理

**LangChain的异步与大数据处理：**

1. **Async工具**：`@tool`装饰器自动创建同步+异步版本
   ```python
   @tool
   async def async_analysis(query: str) -> dict:
       result = await long_running_task(query)
       return {"status": "completed", "result": result}
   ```

2. **`response_format="content_and_artifact"`**：将展示内容（给模型看的文本）与结构化数据（给下游代码用的数据）分离
   ```python
   @tool(response_format="content_and_artifact")
   def get_expression_matrix(gene_ids: list[str]) -> tuple[str, pd.DataFrame]:
       df = load_data(gene_ids)
       summary = f"Loaded {len(df)} genes with {len(df.columns)} samples"
       return summary, df  # (content, artifact)
   ```

3. **ToolNode并行执行**：多个独立工具同时运行，总延迟 = max(各工具延迟) + 2次LLM调用

4. **超时处理**：ToolNode默认不强制超时，需在外层包装
   ```python
   import httpx
   @tool
   def api_call_with_timeout(query: str) -> str:
       return httpx.get(url, timeout=30.0).text
   ```

**LlamaIndex的工具设计：**

LlamaIndex的工具抽象与LangChain类似但有自己的特色：

```python
from llama_index.core.tools import FunctionTool, BaseTool
from llama_index.core.agent.workflow import FunctionAgent

# 从函数创建工具
tools = [
    FunctionTool.from_defaults(run_deseq2),
    FunctionTool.from_defaults(run_enrichment)
]

# FunctionAgent（简化版agent）
agent = FunctionAgent(llm=llm, tools=tools)
response = await agent.run("分析GSE12345的差异表达基因")

# LoadAndSearchToolSpec：大数据工具的分拆模式
from llama_index.core.tools.tool_spec.load_and_search import LoadAndSearchToolSpec
# 将一个大结果工具拆分为"加载"和"搜索"两个工具
agent = FunctionAgent(tools=LoadAndSearchToolSpec.from_defaults(big_tool).to_tool_list())
```

### 与OmicHub的适配评估

**适配度：★★★☆☆（中等，作为可选层）**

LangChain/LangGraph是强大的抽象层，但OmicHub已有成熟的MCP基础设施和Agentic对话流，引入LangChain需要评估ROI。

**引入LangChain的优势：**
- 统一工具定义，自动转换多provider格式
- LangGraph提供强大的图编排能力（并行、条件分支、状态检查点）
- 丰富的预构建工具生态（1000+社区工具）
- `content_and_artifact`分离模式对生信场景很有价值

**不引入的理由：**
- OmicHub已有8轮tool闭环，LangGraph的agent循环是重复造轮子
- MCP本身已提供provider无关的抽象层
- LangChain版本迭代快，维护成本高
- 已有SSE流式架构与LangGraph的stream events可能冲突

**建议方案：** 可选集成层——使用LangChain的工具定义和转换能力（`convert_to_openai_tool`等），但不需要引入LangGraph的agent编排。

### 可借鉴的具体设计

1. **`content_and_artifact`分离模式**：工具返回`(human_readable_string, structured_data)`元组，文本给LLM上下文，结构化数据给下游处理。这对生信分析非常有价值（大矩阵作为artifact，摘要文本作为content）

2. **ToolNode的并行执行模式**：同一轮中多个独立工具通过ThreadPoolExecutor并发执行，总延迟从`sum(latencies)`降到`max(latencies)`。OmicHub在支持多独立生信分析时可借鉴

3. **工具注册表（Tool Registry）模式**：通过name到工具的映射表实现动态路由，配合两阶段路由处理大量工具。OmicHub的工具箱可按类别组织，实现"先选类别再选工具"的分层发现

---

## 5. GitHub Copilot Chat / Cursor 工具集成

### 核心设计

**GitHub Copilot Chat** 和 **Cursor** 是两种主流的AI编程助手，它们的工具集成方式反映了AI产品在实际工程环境中的设计取舍。

### GitHub Copilot Chat

**架构概览：**
GitHub Copilot Chat的架构包含三个核心组件：
1. **Copilot Extension（VS Code本地）**：捕获提示、扫描工作区、格式化数据
2. **Copilot Proxy（云端）**：速率限制、认证、安全检查、转发请求
3. **Backend LLM**：OpenAI模型处理提示+上下文生成建议

**工具发现与调用机制：**

Copilot Chat采用**三层上下文注入**机制而非传统工具调用：

| 机制 | 符号 | 功能 | 示例 |
|------|------|------|------|
| **Chat Participants** | `@` | 领域专家路由 | `@workspace`、`@terminal`、`@vscode` |
| **Slash Commands** | `/` | 预定义快捷指令 | `/explain`、`/fix`、`/tests` |
| **Chat Variables** | `#` | 上下文变量注入 | `#codebase`、`#fetch`、`#websearch` |

**Participant机制：**
- `@workspace`：Copilot扫描整个代码库作为上下文
- `@terminal`：注入终端输出作为上下文
- `@vscode`：注入编辑器状态（打开文件、诊断信息）

**Slash Commands的底层本质：**
```
/explain → 系统prompt: "解释以下代码的工作原理..."
/fix     → 系统prompt: "修复以下代码中的问题..."
/tests   → 系统prompt: "为以下代码生成单元测试..."
```

Slash commands本质上是**预定义的prompt模板**，不是schema化的工具调用。

**MCP集成（最新）：**
- Copilot支持MCP作为外部工具连接方式
- 支持MCP OAuth进行安全第三方集成
- Enterprise用户获得私有MCP注册表
- 通过prompt files可创建自定义slash commands访问MCP servers

### Cursor

**架构特点：**
Cursor是VS Code的分支IDE，采用**Agent-First架构**：
- **Composer**：AI Agent的核心编排器
- **Supermaven**：最快的tab completion引擎
- **Semantic Search**：代码库语义搜索
- **支持最多8个并行agents**

**Cursor的MCP集成：**

```yaml
# Cursor MCP配置（~/.cursor/mcp.json）
{
  "mcpServers": {
    "bioinformatics": {
      "command": "python",
      "args": ["/path/to/bioinfo_mcp_server.py"],
      "env": { "API_KEY": "..." }
    },
    "remote-tools": {
      "url": "https://mcp.company.internal/tools",
      "headers": { "Authorization": "Bearer ${API_TOKEN}" }
    }
  }
}
```

**Cursor MCP限制：**
- 仅支持tools（不支持resources/prompts）
- 40个工具上限（只发送前40个工具给Agent）
- 支持stdio和SSE transports
- SSH访问时MCP可能不正常工作
- MCP Apps 2.6+支持交互式UI（图表、图示直接内嵌在对话中）

**Cursor的Agent模式工具调用：**
1. 用户输入自然语言描述任务
2. Agent分析任务，自主选择合适的MCP工具
3. 执行工具，获取结果
4. 如果需要用户确认（文件修改等），弹出approval对话框
5. 循环直到任务完成

### 工具调用流程对比

```
GitHub Copilot Chat流程：
1. 用户输入: "@workspace /explain this function"
2. Extension扫描工作区，收集相关代码上下文
3. 上下文+prompt通过Copilot Proxy发送到LLM
4. LLM生成解释文本
5. 结果流式返回VS Code Chat面板

Cursor Agent流程：
1. 用户输入: "分析这个表达矩阵的差异基因"
2. Agent决定调用MCP工具：run_deseq2
3. 执行工具（可能需要用户确认参数）
4. 获取结果，决定下一步（如调用enrichment分析）
5. 最终汇总结果返回给用户
```

### 与OmicHub的适配评估

**适配度：★★☆☆☆（低-中等，参考意义为主）**

Copilot Chat和Cursor是面向编程场景的IDE工具，与OmicHub的平台型生信分析场景有本质差异。但以下设计值得参考：

**可参考的设计点：**
1. **三层上下文注入（@/#/）**：Copilot的Participant/Variable/Command分层是很好的UX设计，OmicHub可设计类似的上下文注入机制（如`@database`、`#dataset`、`/pipeline`）
2. **Approval机制**：Cursor的文件修改需要用户确认，OmicHub的生信分析工具（尤其是写文件、删除数据类）应设计类似的确认流程
3. **40工具上限的分层策略**：Cursor的40工具限制和选择策略值得借鉴——OmicHub应该设计工具的分层/分类暴露机制

### 可借鉴的具体设计

1. **Agent Approval Flow**：Cursor在执行重要操作前弹出确认对话框的设计，OmicHub在调用耗时/破坏性生信工具前应有类似的显式确认机制

2. **MCP Apps交互式UI**：Cursor 2.6+在Agent聊天中直接渲染图表和图示的能力，OmicHub应设计工具结果的富渲染（火山图、热图、通路图直接在对话中展示）

3. **Prompt Files自定义命令**：Copilot通过prompt files让开发者创建自定义slash commands的模式，OmicHub可让用户创建自定义分析流程模板（如"/rnaseq-pipeline"一键执行完整的RNA-Seq分析流程）

---

## 6. 结果回传与渲染方案

### 各平台如何处理大结果

**问题背景**：生信分析结果往往非常大（差异基因列表上千行、表达矩阵数百万值、可视化图片高分辨率），直接传入LLM context会超出token限制。

**各平台策略对比：**

| 平台 | 截断策略 | 摘要策略 | 文件引用 | 流式结果 |
|------|----------|----------|----------|----------|
| **MCP** | `structuredContent`分离 | 客户端处理 | Resource Links | Progress通知 |
| **OpenAI** | 客户端截断 | 客户端摘要 | 无原生支持 | 流式文本 |
| **Claude** | 客户端截断 | 客户端摘要 | 无原生支持 | 流式文本+工具 |
| **LangChain** | `content_and_artifact` | 工具内摘要 | artifact引用 | 流式events |
| **Cursor** | 内部截断 | 自动摘要 | 文件内联 | 流式Markdown |

### MCP的结果回传设计（最详细）

MCP定义了最完善的结果回传机制：

```json
{
  "content": [
    { "type": "text", "text": "差异表达分析完成。共鉴定出1,247个显著DEGs。" },
    { "type": "image", "data": "base64encoded...", "mimeType": "image/png", "annotations": { "audience": ["user"], "priority": 0.9 } },
    { "type": "resource", "resource": { "uri": "file:///results/degs.csv", "mimeType": "text/csv" } }
  ],
  "isError": false,
  "structuredContent": {
    "total_genes": 20547,
    "significant_genes": 1247,
    "upregulated": 523,
    "downregulated": 724,
    "top_genes": [{"gene": "BRCA1", "log2FoldChange": 2.34, "padj": 0.001}]
  }
}
```

**Content Block类型：**
| 类型 | 用途 | 是否给LLM |
|------|------|-----------|
| `text` | 人类可读摘要 | 是 |
| `image` | 图表/可视化（base64） | 是（多模态模型） |
| `audio` | 音频结果 | 视场景 |
| `resource` | 文件引用 | 否（仅展示给用户） |

### 图表/表格的渲染方式

**各平台渲染方案：**

1. **MCP**：
   - Image content block：PNG/JPG的base64编码直接嵌入
   - Resource link：外部文件引用，客户端自行渲染
   - 无原生表格类型，需转换为text/markdown

2. **OpenAI Chat Completions**：
   - 纯文本/JSON，渲染完全依赖客户端
   - Code Interpreter生成PNG文件链接
   - 表格通常以Markdown格式返回

3. **Responses API（改进）**：
   - Code Interpreter支持内联图像输出
   - File Search返回结构化引用

4. **Cursor MCP Apps**：
   - 支持交互式图表直接渲染在对话中
   - 支持Mermaid图示

5. **推荐方案（OmicHub）**：
   ```json
   {
     "content": [
       { "type": "text", "text": "## 差异表达分析结果\n\n共鉴定出**1,247**个显著DEGs..." },
       { "type": "image", "data": "iVBORw0KGgo...", "mimeType": "image/png" },
       { "type": "text", "text": "| Gene | log2FC | padj |\n|------|--------|------|\n| BRCA1 | 2.34 | 0.001 |" }
     ],
     "structuredContent": {
       "full_results_url": "/api/results/deg_12345.csv",
       "interactive_plot_url": "/api/plots/volcano_12345.html"
     }
   }
   ```

### 多轮工具调用的上下文管理

**Context压缩策略：**

| 策略 | 说明 | 适用场景 |
|------|------|----------|
| **Truncation** | 直接截断早期消息 | 简单场景 |
| **Summarization** | 用LLM摘要早期工具结果 | 中等复杂度 |
| **Compaction API** | OpenAI Responses的显式上下文压缩 | 长对话 |
| **Checkpointing** | LangGraph的超级步骤检查点 | 需要恢复的场景 |
| **Structured Content Filtering** | 只保留structuredContent的部分字段 | 生信大数据场景 |

**OmicHub推荐的上下文管理方案：**

```python
# 生信场景的context管理
class BioinfoContextManager:
    def manage_tool_results(self, messages: list, max_tool_token: int = 4000):
        """
        1. 保留所有tool_call决策（LLM需要知道调用了什么工具）
        2. 对tool_result进行智能截断：
           - 保留前50行差异基因 + "...（共N个，完整结果见链接）"
           - 保留图表的image content block
           - structuredContent存入外部存储，替换为引用链接
        3. 超过8轮tool闭环时触发摘要
        """
        for msg in messages:
            if msg.role == "tool":
                content = msg.content
                if len(content) > max_tool_token:
                    # 截断策略：保留头部摘要 + 统计信息
                    msg.content = self._truncate_bio_result(content)
        return messages
```

### 可借鉴的具体设计

1. **MCP Content Block多类型结果**：将文本摘要、图片（base64）、文件引用统一封装在content数组中，客户端根据类型选择渲染方式

2. **Content + StructuredContent分离**：文本摘要给LLM推理用，结构化数据（CSV/JSON）给下游分析和下载用，避免大JSON浪费token

3. **Progress通知+流式渲染**：长时间生信分析（如DESeq2、STAR比对）通过MCP Progress通知实时更新进度，前端展示进度条

---

## 7. 跨架构对比总结表

### 核心维度对比

| 维度 | MCP | OpenAI Function Calling | Claude Tool Use | LangChain | GitHub Copilot | Cursor |
|------|-----|------------------------|-----------------|-----------|----------------|--------|
| **协议类型** | JSON-RPC 2.0 over stdio/SSE/HTTP | REST API (Chat/Responses) | REST API (/v1/messages) | Python抽象层 | VS Code Extension | IDE内置 |
| **Schema格式** | JSON Schema (input/output) | JSON Schema (parameters) | JSON Schema (input_schema) | OpenAI/Claude格式自动转换 | 无（prompt模板） | MCP格式 |
| **传输协议** | stdio/SSE/Streamable HTTP | HTTPS REST/SSE | HTTPS REST/SSE | 任意（通过provider） | HTTPS (via Proxy) | stdio/SSE (MCP) |
| **异步支持** | ★★★★★ (Progress/Cancel/Pagination) | ★★★☆☆ (Streaming) | ★★★☆☆ (Streaming) | ★★★★☆ (Async/Parallel) | ★★☆☆☆ | ★★★☆☆ |
| **并行工具调用** | 客户端控制 | parallel_tool_calls参数 | disable_parallel_tool_use | ToolNode自动并行 | 不支持 | Agent自动调度 |
| **生态成熟度** | ★★★★☆ (14K+ servers) | ★★★★★ (最广泛) | ★★★★☆ (Claude生态) | ★★★★★ (最流行框架) | ★★★★★ (最大用户群) | ★★★★☆ (增长快) |
| **与MCP兼容性** | 原生协议 | Responses API支持MCP | 通过MCP适配 | MCP客户端SDK | MCP支持（新） | 原生MCP Client |
| **结果回传丰富度** | ★★★★★ (多content类型) | ★★☆☆☆ (文本为主) | ★★☆☆☆ (文本为主) | ★★★★☆ (content+artifact) | ★★★☆☆ | ★★★★☆ (MCP Apps) |
| **平台型持续会话** | ★★★★★ (为持续会话设计) | ★★★★☆ (previous_response_id) | ★★★☆☆ (无原生stateful) | ★★★★☆ (LangGraph checkpoint) | ★★☆☆☆ | ★★★☆☆ |
| **科学计算适用性** | ★★★★★ | ★★★★☆ | ★★★★☆ | ★★★★☆ | ★★☆☆☆ | ★★★☆☆ |

### 协议设计细节对比

| 特性 | MCP | OpenAI | Anthropic |
|------|-----|--------|-----------|
| **工具发现** | `tools/list` RPC方法 | API定义时静态传入 | API定义时静态传入 |
| **工具变更通知** | `notifications/tools/list_changed` | 不支持（每轮重新传入） | 不支持（每轮重新传入） |
| **进度通知** | `notifications/progress` | 不支持 | 不支持 |
| **取消执行** | `notifications/cancel` | 不支持 | 不支持 |
| **错误标记** | `isError` in result | 客户端控制 | `is_error: true` |
| **Schema版本** | 2020-12 Draft | Draft 7 subset | Draft 7 subset (strict受限) |
| **嵌套调用** | Sampling (server→client LLM) | 不支持 | 不支持 |
| **工具元数据** | annotations (readOnly/destructive) | 无 | 无 |
| **多模态结果** | text/image/audio/resource | 文本+image_url | text+image block |
| **工具命名约束** | `^[a-zA-Z0-9_-]{1,64}$` | `^[a-zA-Z0-9_-]+$` | `^[a-zA-Z0-9_-]{1,64}$` |

---

## 8. 对OmicHub的具体建议

### 总体架构建议

基于调研结果，建议OmicHub采用 **"MCP原生 + OpenAI格式兼容层 + 分层工具发现"** 的架构模式：

```
┌─────────────────────────────────────────────────────────┐
│                    OmicHub 前端层                        │
│         (SSE流式渲染 / 图表展示 / 确认对话框)              │
├─────────────────────────────────────────────────────────┤
│                   Agent编排层                            │
│    (8轮tool闭环 / 上下文管理 / 会话状态 / Checkpoint)      │
├─────────────────────────────────────────────────────────┤
│                MCP Client层 (已有)                        │
│    (builtin/stdio/sse transport / capability协商)        │
├─────────────────────┬───────────────────────────────────┤
│   MCP适配层          │   OpenAI格式兼容层                 │
│   (MCP↔LLM格式转换)  │   (转换到OpenAI tools格式)         │
├─────────────────────┴───────────────────────────────────┤
│              工具发现与注册中心                           │
│   (分层工具目录 / 动态注册 / Schema管理 / 版本控制)        │
├─────────────────────────────────────────────────────────┤
│              生信MCP Server层                            │
│   (DESeq2 Server / GATK Server / Pathway Server / ...)  │
└─────────────────────────────────────────────────────────┘
```

### 具体设计建议

#### 建议1：工具箱对LLM可见性的联动层设计

**问题**：现有工具箱对LLM不可见，需要桥接。

**方案**：
```python
class OmicHubToolRegistry:
    """OmicHub工具注册中心——桥接工具箱与LLM"""
    
    def __init__(self):
        self.mcp_client: MCPClient  # 已有MCP客户端
        self.tool_cache: dict[str, dict] = {}  # name -> MCP Tool schema缓存
        
    async def discover_tools(self) -> list[dict]:
        """发现所有可用工具并转换为OpenAI格式"""
        mcp_tools = await self.mcp_client.list_tools()
        openai_tools = []
        for tool in mcp_tools:
            # MCP Tool -> OpenAI Tool格式转换
            openai_tool = {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.inputSchema,
                    "strict": True
                }
            }
            openai_tools.append(openai_tool)
            self.tool_cache[tool.name] = tool
        return openai_tools
    
    async def execute_tool(self, name: str, arguments: dict) -> dict:
        """执行工具调用（MCP格式）"""
        result = await self.mcp_client.call_tool(name, arguments)
        # MCP Result -> OpenAI tool_result格式转换
        return {
            "role": "tool",
            "tool_call_id": result.tool_call_id,
            "content": self._format_result_for_llm(result)
        }
```

#### 建议2：分层工具发现机制

生信工具数量庞大（测序、表达、变异、通路等），参考Claude Code的两阶段路由：

```python
# 第一层：工具类别选择
category_tools = [
    {
        "name": "select_analysis_category",
        "description": "选择生信分析类别。当用户请求不明确涉及哪个分析领域时使用。",
        "parameters": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "enum": ["rna_seq", "dna_seq", "epigenomics", "proteomics", "pathway", "visualization"]
                }
            }
        }
    }
]

# 第二层：各类别下的具体工具（按需暴露）
rna_seq_tools = [run_star_align, run_deseq2, run_edger, ...]
dna_seq_tools = [run_gatk_variant_call, run_mutect2, run_cnv_analysis, ...]
pathway_tools = [run_go_enrichment, run_kegg_analysis, run_gsea, ...]

# 动态工具暴露逻辑
async def get_tools_for_context(conversation_history: list) -> list[dict]:
    """根据对话上下文动态选择要暴露的工具"""
    # 如果对话已涉及具体类别，只暴露该类别的工具
    # 否则暴露类别选择工具+各类别代表工具
    # 始终暴露基础工具（如get_gene_info, plot_volcano等）
```

#### 建议3：生信分析结果的标准化回传格式

```json
{
  "content": [
    {
      "type": "text",
      "text": "## 差异表达分析完成\n\n- 总基因数：20,547\n- 显著DEGs (padj<0.05)：**1,247**\n- 上调基因：523\n- 下调基因：724\n\nTop 5差异基因：\n| 基因 | log2FC | padj |\n|------|--------|------|\n| BRCA1 | 2.34 | 0.001 |\n| TP53 | -1.89 | 0.003 |\n| ..."
    },
    {
      "type": "image",
      "data": "base64/iVBORw0KGgo...",
      "mimeType": "image/png",
      "annotations": { "title": "火山图", "figure_type": "volcano_plot" }
    }
  ],
  "structuredContent": {
    "analysis_type": "differential_expression",
    "method": "DESeq2",
    "summary_stats": {
      "total_genes": 20547,
      "significant_genes": 1247,
      "upregulated": 523,
      "downregulated": 724
    },
    "downloads": {
      "full_results": "/api/download/degs_20250715_001.csv",
      "normalized_counts": "/api/download/norm_counts_20250715_001.csv",
      "interactive_plot": "/api/plots/volcano_20250715_001.html"
    },
    "next_analysis_suggestions": [
      {"tool": "run_go_enrichment", "description": "GO富集分析"},
      {"tool": "run_kegg_analysis", "description": "KEGG通路分析"},
      {"tool": "run_gsea", "description": "GSEA基因集富集分析"}
    ]
  },
  "isError": false
}
```

#### 建议4：长时间运行的生信工具处理

```python
class AsyncToolExecutor:
    """处理长时间运行的生信分析工具"""
    
    async def execute_with_progress(self, tool_name: str, args: dict):
        """
        1. 立即返回任务ID和接受确认
        2. 通过SSE推送进度更新
        3. 完成后推送最终结果
        4. 支持中途取消
        """
        task_id = generate_task_id()
        
        # 启动后台任务
        asyncio.create_task(self._run_tool_with_progress(task_id, tool_name, args))
        
        return {
            "status": "accepted",
            "task_id": task_id,
            "message": f"分析任务已启动，预计运行时间: {self.estimate_time(tool_name, args)}"
        }
    
    async def _run_tool_with_progress(self, task_id: str, tool_name: str, args: dict):
        """后台执行+进度推送"""
        try:
            async for progress in self.mcp_client.call_tool_streaming(tool_name, args):
                await self.sse_emit(task_id, {
                    "type": "progress",
                    "progress": progress.percentage,
                    "status": progress.status_message
                })
            
            result = await self.mcp_client.get_result(task_id)
            await self.sse_emit(task_id, {
                "type": "completed",
                "result": result
            })
        except CancelledError:
            await self.sse_emit(task_id, {"type": "cancelled"})
```

#### 建议5：多模型兼容性策略

OmicHub使用OpenAI格式，应保留此格式作为主要接口，但通过MCP适配层支持多模型：

```python
class MultiModelAdapter:
    """多模型适配器——将MCP Tool转换为各模型格式"""
    
    def to_openai_format(self, mcp_tools: list[MCPTool]) -> list[dict]:
        """转换为OpenAI tools格式（OmicHub主要格式）"""
        return [self._mcp_to_openai(t) for t in mcp_tools]
    
    def to_anthropic_format(self, mcp_tools: list[MCPTool]) -> list[dict]:
        """转换为Anthropic tools格式"""
        return [{"name": t.name, "description": t.description, "input_schema": t.inputSchema} for t in mcp_tools]
    
    def from_openai_tool_calls(self, tool_calls: list[dict]) -> list[MCPToolCall]:
        """将OpenAI tool_calls转换为MCP调用"""
        return [MCPToolCall(id=tc["id"], name=tc["function"]["name"], 
                           arguments=json.loads(tc["function"]["arguments"])) for tc in tool_calls]
```

### 技术选型总结

| 组件 | 推荐方案 | 理由 |
|------|----------|------|
| **工具协议** | MCP原生 | 已有基础设施，生态成熟，解耦LLM与工具 |
| **LLM接口格式** | OpenAI格式（主要） | 已有实现，最广泛支持 |
| **Transport** | Streamable HTTP（远程）+ builtin（本地） | stdio适合本地dev，HTTP适合生产 |
| **Agent编排** | 自研（基于现有8轮闭环） | 已有成熟实现，不需LangGraph |
| **工具定义** | LangChain工具转换（可选） | 利用其format转换能力 |
| **结果回传** | MCP Content Blocks + structuredContent | 最完善的格式设计 |
| **大结果处理** | 摘要+文件引用+分页 | 避免token溢出 |
| **长时间任务** | Progress通知 + 后台执行 | MCP原生支持 |
| **多模型支持** | 适配层模式 | OpenAI为主，Claude/Gemini通过适配 |

### 实施路线图

**Phase 1（立即）：MCP工具发现层**
- 实现MCP `tools/list` → OpenAI `tools`格式转换
- 工具注册中心（分层目录、动态注册）
- 基本的结果回传格式标准化

**Phase 2（短期）：增强Agent体验**
- 两阶段工具路由（类别→具体工具）
- Progress通知+流式渲染
- `content_and_artifact`分离模式
- 图表内联渲染

**Phase 3（中期）：高级特性**
- Tool Annotations（readOnly/destructive标记+用户确认）
- 长时间任务后台执行+取消
- 多模型适配层
- 自定义分析流程模板（Prompt Files模式）

**Phase 4（长期）：生态建设**
- 发布OmicHub生信MCP Server到社区
- 支持用户自定义工具注册
- 工具市场/目录

---

> **报告结束**
> 
> 本报告基于2024-2025年公开技术文档、GitHub仓库、官方API文档和社区讨论综合调研生成。
> 关键参考来源：MCP Specification (2025-11-25), OpenAI API Docs, Anthropic API Docs, LangChain/LangGraph Docs, Cursor Docs, GitHub Copilot Docs。
