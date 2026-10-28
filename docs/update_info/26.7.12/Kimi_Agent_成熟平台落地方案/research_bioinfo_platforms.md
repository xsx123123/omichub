# 主流生物信息学平台工具集成模式深度调研报告

> 调研目标：为 OmicHub 平台 AI 助手与生物信息学工具联动架构提供设计参考
> 调研日期：2025年7月

---

## 目录

1. [Galaxy Platform](#1-galaxy-platform)
2. [Terra (Broad Institute)](#2-terra-broad-institute)
3. [DNAnexus](#3-dnanexus)
4. [Seqera Platform / Nextflow Tower](#4-seqera-platform--nextflow-tower)
5. [其他值得关注的平台](#5-其他值得关注的平台)
6. [跨平台对比总结表](#6-跨平台对比总结表)
7. [对 OmicHub 的综合建议](#7-对-omichub-的综合建议)

---

## 1. Galaxy Platform

### 1.1 工具注册/发现机制

#### Tool Shed：中央工具仓库

Galaxy 的工具生态系统围绕 **Tool Shed** 构建，这是一个专用的工具注册仓库服务，功能类似于生物信息学领域的 "App Store"。

**核心概念：**
- **Repository（仓库）**：Tool Shed 中的基本单位，一个仓库通常包含一个工具的完整定义（一个 repository 对应一个工具是最佳实践）
- **.shed.yml**：仓库的元数据配置文件，定义名称、描述、分类、所有者等
- **Revision（版本）**：每个仓库可以有多个版本（changeset revisions），支持版本追溯

**工具发现流程：**
1. 用户通过 Galaxy 界面访问 Tool Shed 搜索工具（支持按名称、描述、分类、标签搜索）
2. Galaxy 实例定期轮询 Tool Shed 检查更新（`enable_tool_shed_check`、`hours_between_check` 配置）
3. 发现工具后，通过 Galaxy 管理界面一键安装到本地实例
4. 安装过程自动处理依赖（Conda 包或容器）

**发布流程（通过 Planemo）：**
```bash
# 初始化仓库元数据
planemo shed_init --name="samtools_sort" --owner="iuc" --description="Sort BAM files"

# 创建/更新仓库
planemo shed_create --shed_target toolshed    # 首次创建
planemo shed_update --shed_target toolshed    # 更新版本

# 运行测试
planemo shed_test --shed_target testtoolshed
```

**最佳实践（Intergalactic Utilities Commission, IUC）：**
- 每个 repository 只包含一个工具
- 工具必须经过 Planemo lint 检查通过
- 必须包含功能测试（`<tests>` 块）
- 依赖应通过 Conda/Bioconda 解析

#### Dockstore 集成与 GA4GH TRS

Galaxy 还支持通过 **GA4GH Tool Registry Service (TRS)** API 从 Dockstore 发现和导入工作流。Galaxy 内置了 TRS 工作流搜索和导入功能，用户可以使用关键字搜索 Dockstore 上发布的工作流，或通过 TRS ID 直接导入。

#### 工具推荐系统

Galaxy 内置了基于 **RNN 的工具推荐系统**，根据用户活动历史和数据输入类型推荐下一个最合适的工具，帮助用户构建分析流程。

---

### 1.2 工具 Schema 定义

#### Tool XML 完整结构

Galaxy 的工具 Schema 使用 XML 定义，由 XSD (XML Schema Definition) 正式规范。以下是核心结构：

```xml
<tool id="tool_id" name="Display Name" version="1.0.0" profile="21.09">
    <!-- 描述信息 -->
    <description>Short description of what the tool does</description>
    
    <!-- 可选：宏定义，用于复用 -->
    <macros>
        <import>macros.xml</import>
    </macros>
    
    <!-- 必需：软件依赖 -->
    <requirements>
        <requirement type="package" version="1.9">samtools</requirement>
        <requirement type="package" version="1.1">pysam</requirement>
    </requirements>
    
    <!-- 容器声明（可选） -->
    <container type="docker">biocontainers/samtools:1.9</container>
    
    <!-- 必需：命令模板（Cheetah 模板引擎） -->
    <command><![CDATA[
        samtools sort 
        -@ \${GALAXY_SLOTS:-1}
        #if str(\$options.settings_type) == "advanced":
            -m \$options.memory
        #end if
        '\$input'
        -o '\$output'
    ]]></command>
    
    <!-- 可选：配置文件 -->
    <configfiles>
        <configfile name="config">...</configfile>
    </configfiles>
    
    <!-- 必需：输入参数定义 -->
    <inputs>
        <param name="input" type="data" format="bam" label="Input BAM file"/>
        <conditional name="options">
            <param name="settings_type" type="select" label="Settings">
                <option value="default">Default</option>
                <option value="advanced">Advanced</option>
            </param>
            <when value="default"/>
            <when value="advanced">
                <param name="memory" type="text" value="768M" label="Memory per thread"/>
            </when>
        </conditional>
    </inputs>
    
    <!-- 必需：输出定义 -->
    <outputs>
        <data name="output" format="bam" label="\${tool.name} on \${on_string}: sorted BAM"/>
    </outputs>
    
    <!-- 可选：测试用例 -->
    <tests>
        <test>
            <param name="input" ftype="bam" value="test.bam"/>
            <output name="output" ftype="bam" file="sorted.bam" compare="sim_size"/>
        </test>
    </tests>
    
    <!-- 可选：工具帮助文档（reStructuredText 格式） -->
    <help><![CDATA[
        **What it does**
        Sorts BAM files using samtools sort.
    ]]></help>
    
    <!-- 可选：引用 -->
    <citations>
        <citation type="doi">10.1093/bioinformatics/btp352</citation>
    </citations>
</tool>
```

#### 参数类型体系

| 参数类型 | 用途 | 示例 |
|---------|------|------|
| `data` | 输入数据集引用 | BAM, FASTQ, VCF 文件 |
| `text` | 文本输入 | 字符串参数 |
| `integer` | 整数 | 线程数 |
| `float` | 浮点数 | 阈值 |
| `boolean` | 布尔值 | 开关选项 |
| `select` | 单选/多选 | 下拉菜单 |
| `conditional` | 条件参数组 | 高级选项 |
| `repeat` | 可重复参数 | 多文件输入 |
| `section` | 参数分组 | 折叠面板 |
| `data_column` | 数据列引用 | 表格列选择 |
| `color` | 颜色选择 | 可视化 |

#### 数据类型系统

Galaxy 拥有丰富的数据类型定义（`datatypes_conf.xml`），支持自动格式嗅探、数据类型转换、元数据提取。输出格式可以通过 `format_source` 从输入继承，或通过 `<change_format>` 根据参数动态变更。

---

### 1.3 工具执行调度

#### Job Runner 插件架构

Galaxy 采用**插件化的 Job Runner 架构**，通过 `job_conf.xml` 配置：

```xml
<job_conf>
    <plugins>
        <!-- 本地直接执行 -->
        <plugin id="local" type="runner" load="galaxy.jobs.runners.local:LocalJobRunner"/>
        <!-- DRMAA 标准（SGE/SLURM） -->
        <plugin id="drmaa" type="runner" load="galaxy.jobs.runners.drmaa:DRMAAJobRunner"/>
        <!-- Pulsar 远程作业执行 -->
        <plugin id="pulsar" type="runner" load="galaxy.jobs.runners.pulsar:PulsarRESTJobRunner"/>
        <!-- HTCondor -->
        <plugin id="condor" type="runner" load="galaxy.jobs.runners.condor:CondorJobRunner"/>
        <!-- Kubernetes -->
        <plugin id="k8s" type="runner" load="galaxy.jobs.runners.kubernetes:KubernetesJobRunner"/>
    </plugins>
    
    <destinations default="cluster">
        <destination id="cluster" runner="drmaa">
            <param id="native_specification">-pe threads 4 -l h_vmem=8G</param>
        </destination>
        <destination id="remote" runner="pulsar">
            <param id="url">http://pulsar.example.org:8913</param>
            <param id="dependency_resolution">remote</param>
        </destination>
    </destinations>
    
    <!-- 按工具路由到不同目的地 -->
    <tools>
        <tool id="trinity" destination="remote"/>
    </tools>
</job_conf>
```

#### 关键执行特性

| 特性 | 实现 |
|------|------|
| **同步/异步** | 完全异步执行，作业提交后通过 Job Manager 轮询状态 |
| **容器化** | 支持 Docker 和 Singularity 容器执行 |
| **依赖解析** | 多层级解析器：Conda → Tool Shed → Container → System |
| **Pulsar** | 远程作业执行系统，支持跨地域计算资源整合 |
| **消息队列** | 支持 RabbitMQ/AMQP 用于 Pulsar 通信 |

#### 容器解析策略

Galaxy 实现了智能的**容器解析器（Container Resolver）**层级：

1. **显式声明**：工具 XML 中直接指定 `<container>` 标签
2. **BioContainers 自动匹配**：根据 `<requirements>` 中的 Conda 包自动匹配预构建的 BioContainers（通过 mulled hash）
3. **按需构建**：使用 Involucro 工具从 Conda 依赖实时构建容器
4. **缓存复用**：解析后的容器 ID 缓存避免重复解析

---

### 1.4 与 AI/自动化的集成

Galaxy 在 AI/LLM 集成方面有多项前沿探索：

#### MCP-based AI Agent（最新）

- 开发了 **MCP (Model Context Protocol) server**，允许 AI 助手连接 Galaxy 实例
- AI agent 可以：搜索工具、运行工具、管理工作流、与 Galaxy 生态系统交互
- 这与 OmicHub 的 MCP 架构直接相关

#### Galactic Wizard（LLM 对话助手）

- 集成大型语言模型的对话式 AI 助手
- 可以回答用户关于 Galaxy 使用的问题
- 基于自然语言的工作流构建辅助

#### 工具推荐系统

- 基于 RNN（循环神经网络）的智能工具推荐
- 根据用户在 history 中的操作序列和当前数据集类型推荐下一个工具
- 学习用户行为模式，提供个性化建议

#### ML/AI 工具生态

Galaxy ToolShed 提供 3500+ 工具，其中 ML/AI 相关包括：
- **AlphaFold**：蛋白质结构预测
- **CellPose**：细胞分割
- **Cleanlab**：数据质量检测
- **TabPFN**：表格数据基础模型
- **Whisper**：语音识别
- **Flux**：文本到图像生成

---

### 1.5 可借鉴的设计模式

1. **XML Schema + Cheetah 模板的双层抽象**：Galaxy 将工具的参数 schema（XML）与命令生成逻辑（Cheetah 模板）分离，使得同一 schema 可以驱动 UI 渲染、命令构建、测试验证。OmicHub 可采用类似的 "Schema + 模板" 双层模式，将工具描述与执行逻辑解耦。

2. **Tool Shed 的去中心化注册模式**：Tool Shed 允许多个独立实例（Main/Test/Local），每个 Galaxy 实例可配置多个 Shed 源。OmicHub 可借鉴此模式，构建中心化的工具注册服务，同时允许自定义工具源。

3. **容器解析器的层级回退策略**：Galaxy 的容器解析不是单一策略，而是多层级回退（显式声明 → BioContainers 匹配 → 按需构建），这种优雅降级机制极大提高了兼容性。OmicHub 的工具执行环境选择也可采用类似回退策略。

### 1.6 需要规避的陷阱

1. **XML 的维护负担**：Galaxy 的 Tool XML 虽然强大，但随着工具复杂度增加，XML 文件变得冗长且难以维护。现代方案应优先选择 JSON/YAML 等更轻量的格式。

2. **Tool Shed 的版本碎片化**：Tool Shed 中不同版本间的依赖关系管理复杂，版本冲突和依赖地狱问题时有发生。严格的版本锁定和依赖隔离是必须的。

---

## 2. Terra (Broad Institute)

### 2.1 工具注册/发现机制

#### Dockstore：工作流注册中心

Terra 本身**不直接管理独立工具**，而是通过 **Dockstore** 注册和发现完整的分析工作流（Workflow）。

**核心架构：**
- **Dockstore** 是 GA4GH TRS (Tool Registry Service) 标准的主要实现
- 支持注册用 WDL、CWL、Galaxy 和 Nextflow 编写的工作流
- 工作流程版本通过 Git 标签/分支管理
- 与 GitHub、Quay.io 集成实现自动同步

**工具发现流程：**
1. 工作流开发者在 GitHub 上托管 WDL 文件
2. GitHub App 自动推送变更到 Dockstore
3.  dockstore 解析 WDL 中的 tool/Docker 引用
4. Terra 用户通过 "Import from Dockstore" 导入工作流
5. Terra 通过 GA4GH TRS API 拉取工作流定义

**Terra 自身的工具发现方式：**
- **Workspace 共享**：通过共享 Workspace 模板传播分析流程
- **Broad Methods Repository**：WDL 方法的私有/公共注册库
- **Notebook 环境**：Jupyter Notebook 中直接调用安装生信工具

#### FISS-MCP 集成（最新）

Broad Institute 开发了 **FISS-MCP**：一个 MCP (Model Context Protocol) server for Terra，使 AI 助手能够：
- 列出和描述 workspace 中的数据表
- 提交/监控/中止 WDL 工作流
- 管理工作流配置（method configs）
- 上传/更新实体数据

---

### 2.2 工具 Schema 定义

#### WDL (Workflow Description Language)

WDL 是 Terra 的核心工作流语言，其工具/任务描述结构如下：

```wdl
version 1.0

# 工作流定义（编排多个 task）
workflow SamtoolsWorkflow {
  input {
    File bamfile
  }
  
  call idxstats {
    input: bamfile = bamfile
  }
  
  output {
    File results = idxstats.idxstats
  }
}

# 任务定义（单个工具的封装）
task idxstats {
  input {
    File bamfile
    String docker_image = "biocontainers/samtools:v1.9-4-deb_cv1"
  }
  
  # 命令块
  command <<<
    samtools index ~{bamfile}
    samtools idxstats ~{bamfile} > idxstats.txt
  >>>
  
  # 输出定义
  output {
    File idxstats = "idxstats.txt"
  }
  
  # 运行时配置（容器、资源）
  runtime {
    docker: docker_image
    memory: "4 GB"
    cpu: 2
    disks: "local-disk 50 HDD"
  }
}
```

#### WDL Schema 关键元素

| 元素 | 用途 |
|------|------|
| `workflow` | 工作流编排，定义 task 间的数据流 |
| `task` | 单个工具/命令的封装单元 |
| `command` | 实际执行的 shell 命令（支持模板插值） |
| `input` | 强类型输入声明（File, String, Int, Boolean, Array 等） |
| `output` | 输出文件/值的声明 |
| `runtime` | 执行环境配置（docker, memory, cpu, disks） |

#### Cromwell 执行引擎

- **Cromwell** 是 WDL 的生产级执行引擎（Scala 编写）
- 支持本地执行、Google Cloud Platform、AWS、Azure、HPC 集群
- 处理工作流的调度、重试、缓存（call caching）和分布式执行

---

### 2.3 工具执行调度

#### 执行模式

| 特性 | 实现 |
|------|------|
| **同步/异步** | 完全异步，通过 Submission 系统提交和监控 |
| **容器化** | WDL `runtime` 块中声明 Docker 镜像，Cromwell 自动拉取 |
| **资源管理** | `runtime` 块声明 memory、cpu、disk，Cromwell 请求对应资源 |
| **分布式** | 支持 scatter-gather 并行、条件执行、子工作流 |
| **缓存** | Call Caching：相同输入自动复用历史结果 |

#### Notebook 环境中的工具调用

Terra 的 Jupyter Notebook 环境支持两种工具调用方式：

1. **直接命令行调用**：Notebook 中通过 `!samtools` 等方式直接调用预安装工具
2. **WDL 包装执行**：通过 Papermill 将 Notebook 参数化和程序化执行

```python
# 示例：在 Notebook 中调用 WDL 工作流
import firecloud.api as fapi
fapi.create_submission(
    namespace="my-namespace",
    workspace="my-workspace",
    cnamespace="methods",
    method="samtools_idxstats",
    entity="sample_set",
    etype="sample_set"
)
```

---

### 2.4 与 AI/自动化的集成

#### FISS-MCP Server

- 提供 MCP 标准接口，使 AI 助手可以直接操作 Terra
- 工具包括：列出 workspace、提交工作流、检查状态、管理数据表
- 采用只读默认模式，写操作需 `--allow-writes` 标志

#### AI 自动生成 DOI 和主题句

- Dockstore 1.16+ 使用 AI 自动生成工作流的主题句描述
- 自动 DOI 生成和发现

### 2.5 可借鉴的设计模式

1. **WDL 的 task/workflow 双层抽象**：WDL 将单个工具封装（task）与工作流编排（workflow）清晰分离，每个 task 自包含 input/output/runtime。OmicHub 的工具箱系统可借鉴这种 "工具封装 + 流程编排" 的双层模型。

2. **Dockstore + GA4GH TRS 的标准化注册**：Dockstore 作为 TRS 标准的领先实现，提供了跨平台的工具发现互操作能力。OmicHub 的工具注册 API 可考虑兼容 GA4GH TRS 标准。

3. **MCP Server 作为 AI 接口层**：Broad 的 FISS-MCP 展示了如何通过 MCP 协议将云平台能力暴露给 AI 助手，这是一种比传统 API 更 AI-native 的集成方式。

### 2.6 需要规避的陷阱

1. **WDL 的学习曲线**：WDL 虽然强大，但对非程序员用户不够友好。需要提供可视化编辑器或 AI 辅助生成。

2. **Terra 缺乏细粒度的单工具管理**：Terra 主要管理工作流级别，而非单个工具级别。对于需要频繁调用单个生信工具的场景不够灵活。

---

## 3. DNAnexus

### 3.1 工具注册/发现机制

#### App / Applet 双层体系

DNAnexus 采用独特的 **Applet → App** 双层打包体系：

| 层级 | 可见性 | 用途 |
|------|--------|------|
| **Applet** | 项目内私有 | 开发阶段的轻量级可执行单元 |
| **App** | 全局可发现 | 发布后供社区使用的正式工具 |

**Applet 开发周期：**
```bash
# 1. 本地编写代码
# 2. 构建 applet
dx build my_applet/

# 3. 运行测试
dx run my_applet -i input_file=file-xxxx

# 4. 查看日志
dx watch job-xxxx

# 5. 发布为全局 App
dx publish app-my_applet
```

**工具发现机制：**
- **Tool Library**：DNAnexus 维护的全局 App 库（类似应用商店）
- **项目间共享**：Applet 可跨项目共享
- **版本管理**：App 支持多版本（默认运行最新版本）
- **搜索**：通过 `dx find apps` 命令或 Web UI 搜索

---

### 3.2 工具 Schema 定义

#### dxapp.json 完整结构

```json
{
  "name": "samtools_count",
  "title": "SAMtools Count Reads",
  "summary": "Count aligned reads in a BAM file",
  "dxapi": "1.0.0",
  "version": "1.0.0",
  "inputSpec": [
    {
      "name": "mappings_bam",
      "label": "BAM File",
      "help": "Input BAM file to count reads from",
      "class": "file",
      "patterns": ["*.bam"],
      "optional": false
    },
    {
      "name": "count_flags",
      "label": "SAM Flags",
      "help": "Optional SAM flags to filter",
      "class": "int",
      "optional": true,
      "default": 0
    },
    {
      "name": "output_prefix",
      "label": "Output Prefix",
      "class": "string",
      "optional": false
    }
  ],
  "outputSpec": [
    {
      "name": "count_txt",
      "label": "Read Count",
      "help": "Text file with read count",
      "class": "file",
      "patterns": ["*.count.txt"]
    },
    {
      "name": "total_reads",
      "label": "Total Reads",
      "class": "int"
    }
  ],
  "runSpec": {
    "interpreter": "bash",
    "file": "src/script.sh",
    "timeoutPolicy": {
      "main": {"hours": 2}
    },
    "release": "20.04",
    "distribution": "Ubuntu"
  },
  "access": {
    "project": "CONTRIBUTE",
    "network": ["*"]
  },
  "regionalOptions": {
    "aws:us-east-1": {
      "systemRequirements": {
        "main": {"instanceType": "mem1_ssd1_v2_x4"}
      }
    }
  }
}
```

#### Input/Output Class 类型系统

| Class 类型 | 说明 |
|-----------|------|
| `file` | 文件输入/输出 |
| `int` | 整数 |
| `float` | 浮点数 |
| `string` | 字符串 |
| `boolean` | 布尔值 |
| `hash` | JSON 对象 |
| `record` | DNAnexus 记录对象 |
| `applet` | 另一个 Applet 引用 |
| `array:<type>` | 以上类型的数组 |

#### 执行脚本中的变量约定

```bash
# dxapp.json 中声明的输入自动映射为环境变量
mappings_bam          # 输入文件 ID
download "${mappings_bam}"     # 下载文件

# 自动生成的辅助变量
mappings_bam_name     # 原始文件名
mappings_bam_prefix   # 去除 pattern 后缀的文件名
```

---

### 3.3 工具执行调度

#### 执行架构

| 特性 | 实现 |
|------|------|
| **同步/异步** | 完全异步，`dx run` 提交后返回 Job ID，通过 `dx watch` 监控 |
| **容器化** | 基于 Ubuntu VM（非容器），但可以运行 Docker 命令 |
| **资源管理** | `regionalOptions.systemRequirements` 声明实例类型 |
| **区域选择** | 支持 AWS/Azure/GCP 多区域执行 |
| **超时控制** | `timeoutPolicy` 配置超时策略 |
| **计费** | 按实例使用时长计费 |

#### 工作流编排

DNAnexus 支持通过 **WDL 和 Nextflow** 进行工作流编排：
- 使用 `dxCompiler` 将 WDL 编译为 DNAnexus 原生工作流
- 支持 Cromwell 执行引擎
- 工作流由多个 App/Applet 节点组成

---

### 3.4 与 AI/自动化的集成

DNAnexus 在 AI 集成方面相对传统，主要通过：
- **REST API** (`/system/findExecutables`) 进行程序化工具发现
- **命令行工具** (`dx`) 支持脚本化工作流
- 缺乏原生的 LLM/AI 助手集成

### 3.5 可借鉴的设计模式

1. **dxapp.json 的声明式工具定义**：dxapp.json 将工具的元数据、输入输出 schema、执行配置、资源需求整合在一个 JSON 文件中，简洁且完整。OmicHub 的工具注册可以采用类似的单一 JSON 描述文件。

2. **Applet → App 的发布审批流程**：从私有的 Applet 到全局的 App 需要显式发布操作，这种分层可见性控制值得借鉴。

3. **输入输出的强类型系统**：DNAnexus 的 class 类型系统（file/int/string/boolean/hash/array）清晰明确，且自动生成辅助变量（_name, _prefix）简化脚本编写。

### 3.6 需要规避的陷阱

1. **平台锁定风险**：DNAnexus 的 Applet/App 模型是平台专用的，与开放标准（如 CWL/WDL）的互操作性有限。

2. **VM 执行模式的局限性**：基于 VM 而非容器的执行模式导致环境不可完全复现，且启动时间较长。

---

## 4. Seqera Platform / Nextflow Tower

### 4.1 工具注册/发现机制

#### nf-core/modules 注册中心

Seqera/Nextflow 的工具生态主要通过 **nf-core/modules** 和 **Nextflow Registry** 管理：

**Nextflow Registry** (`registry.nextflow.io`)：
- 集中注册 Nextflow 模块（module）、子工作流（subworkflow）和管道（pipeline）
- 每个模块包含：元数据、关键词、描述、版本历史
- 支持按关键词搜索（如 `bwa`, `variant`, `trimming`）
- 提供 API 和 OCI Store 分发

**nf-core 模块发现：**
```bash
# 列出所有可用模块
nf-core modules list remote

# 安装模块到本地管道
nf-core modules install bwa/mem

# 创建新模块（自动填充容器信息）
nf-core modules create bwa/mem
```

**模块注册信息示例（网页展示）：**
```
Module: nf-core/bwa/mem
Keywords: mem, bwa, alignment, map, fastq, bam, sam
Description: Performs fastq alignment to a fasta reference using BWA
Version: 0.0.0-0c7146d
Download URL: https://registry.nextflow.io/api/v1/modules/nf-core%2Fbwa%2Fmem/...
```

#### Seqera Platform 管道管理

Seqera Platform（原 Nextflow Tower）提供：
- **Pipeline 注册**：通过 Git 仓库 URL 注册管道
- **版本管理**：自动跟踪 Git commit/tag
- **Launchpad**：一键启动管道，自动解析参数 schema
- **Workspace**：组织和共享管道、数据集、计算环境

---

### 4.2 工具 Schema 定义

#### Nextflow DSL2 模块结构

```groovy
// modules/nf-core/bwa/mem/main.nf
process BWA_MEM {
    tag "$meta.id"
    label 'process_high'
    
    // 容器声明（自动解析自 Bioconda）
    conda "bioconda::bwa=0.7.17 bioconda::samtools=1.16.1"
    container "${workflow.containerEngine == 'singularity' 
        ? 'https://depot.galaxyproject.org/singularity/mulled-v2-...' 
        : 'biocontainers/mulled-v2-...'}"
    
    // 输入定义
    input:
    tuple val(meta), path(reads)
    path index
    val sort_bam
    
    // 输出定义
    output:
    tuple val(meta), path("*.bam"), emit: bam
    path "versions.yml"           , emit: versions
    
    // 脚本
    script:
    def args = task.ext.args ?: ''
    def prefix = task.ext.prefix ?: "${meta.id}"
    def read_group = "@RG\\tID:${meta.id}..."
    """
    bwa mem \\
        $args \\
        -R "$read_group" \\
        \${index}/genome \\
        $reads \\
        | samtools sort -@ ${task.cpus} -o ${prefix}.bam -
    
    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        bwa: \$(bwa 2>&1 | head -n 1 | sed 's/^.*Version: //')
        samtools: \$(echo \$(samtools --version 2>&1) | sed 's/^.*samtools //')
    END_VERSIONS
    """
}
```

#### nextflow_schema.json（管道参数 Schema）

```json
{
  "$schema": "http://json-schema.org/draft-07/schema",
  "$id": "https://raw.githubusercontent.com/nf-core/rnaseq/master/nextflow_schema.json",
  "title": "nf-core/rnaseq pipeline parameters",
  "description": "RNA sequencing analysis pipeline",
  "type": "object",
  "definitions": {
    "input_output_options": {
      "title": "Input/output options",
      "type": "object",
      "properties": {
        "input": {
          "type": "string",
          "format": "file-path",
          "description": "Path to comma-separated file containing information about the samples"
        },
        "outdir": {
          "type": "string",
          "format": "directory-path",
          "description": "The output directory where the results will be saved"
        }
      },
      "required": ["input", "outdir"]
    }
  }
}
```

---

### 4.3 工具执行调度

#### 执行架构

| 特性 | 实现 |
|------|------|
| **同步/异步** | 管道整体异步执行，但任务间通过 channel 数据流驱动 |
| **容器化** | 每个 process 可独立声明容器，Wave 服务支持按需构建 |
| **资源管理** | `label` 系统映射到 CPU/内存配置，`task.cpus`/`task.memory` 动态分配 |
| **执行器** | 支持 Local、SLURM、SGE、AWS Batch、Azure Batch、Google Life Sciences、Kubernetes |
| **缓存** | 基于 work dir 的 resume 机制，已完成的任务自动跳过 |

#### Wave 容器服务

Seqera 的 **Wave** 是一个革命性的容器服务：
- **按需构建**：从 Conda/Dockerfile 配方实时构建容器
- **无需 Dockerfile**：直接声明 Conda 包依赖
- **自动缓存**：构建后的容器缓存到注册表
- **跨架构**：支持 x86_64 和 ARM64
- **Fusion FS**：高性能远程文件系统集成

```groovy
// 使用 Wave 的容器声明
process SAMTOOLS {
    conda "bioconda::samtools=1.20"
    // Wave 会自动从 conda 声明构建容器
    
    """
    samtools --version-only
    """
}
```

#### 资源优化

Seqera Platform 提供**自动化资源优化**：
- 收集每个 process 的实际资源使用数据
- 自动生成 per-process 的资源推荐
- 例如 viralrecon 管道的 ARTIC_GUPPYPLEX 步骤：
  - 默认分配 12 cores
  - 实际使用 0.96-2.2 cores
  - 优化建议：3 cores 足够

---

### 4.4 与 AI/自动化的集成

#### Seqera AI CLI / Co-Scientist

Seqera 在 AI 集成方面走在生信领域前沿：

**Co-Scientist**（Seqera 的 AI 助手）：
- 自然语言交互构建、运行和调试 Nextflow 管道
- 三种工作模式：build（构建）、plan（规划）、goal（目标驱动）
- 支持会话恢复 (`seqera ai -c`)

**核心 AI 功能：**

| 功能 | Slash 命令 | 说明 |
|------|-----------|------|
| 脚本转换 | `/convert-r-script` | 将 R 脚本转为 Nextflow 管道 |
| 配置生成 | `/config` | 生成 nextflow.config |
| Schema 生成 | `/schema` | 生成 nextflow_schema.json |
| 调试分析 | `/debug` | 智能失败分析和修复建议 |
| 管道启动 | 自然语言 | "启动我的管道到 AWS" |
| 容器构建 | Wave 集成 | 从 Conda 包生成容器 |
| 语言迁移 | `/migrate-from` | 从 WDL 转为 Nextflow |
| 测试生成 | `/write-nf-test` | 自动生成管道测试 |

**nf-core 集成：**
- AI 助手可以直接搜索和发现 1000+ nf-core 模块
- 获取即用型 Nextflow 命令
- 管道开发者可以通过自然语言查找合适的模块

#### Pipeline Actions（自动化触发）

Seqera Platform 支持自动化管道执行：
- **Git 事件触发**：代码推送自动执行管道
- **定时触发**：Cron 风格的定期执行
- **Webhook 触发**：外部系统集成
- **自动恢复**：失败自动重试

---

### 4.5 可借鉴的设计模式

1. **Wave 容器的按需构建模式**：Wave 将容器构建从开发时延迟到运行时，从 Conda 声明自动生成容器，极大降低了维护负担。OmicHub 的容器管理可以考虑类似的按需构建策略。

2. **nextflow_schema.json 的自动化参数发现**：Nextflow 管道通过 `nextflow_schema.json` 自动生成参数 UI，结合 AI CLI 的自然语言参数设置，形成了从 schema 定义到 AI 交互的完整链路。OmicHub 工具参数暴露给 AI 助手可以借鉴此模式。

3. **Co-Scientist 的上下文感知 AI 助手**：Co-Scientist 将 AI 助手与平台 workspace、本地环境、知识库三层上下文结合，实现了真正有用（而非花哨）的 AI 集成。OmicHub 的 AI 助手设计可以直接参考此架构。

### 4.6 需要规避的陷阱

1. **Nextflow DSL 的学习门槛**：Nextflow 的 DSL2 语法对生物学家来说仍有学习曲线，需要配合 AI 辅助或可视化工具。

2. **管道级别的工具复用不够灵活**：nf-core 的模块系统以管道为中心，单个工具的独立调用和发现不如 Galaxy 灵活。

---

## 5. 其他值得关注的平台

### 5.1 BioContainers / Bioconda 生态

虽然不是独立平台，但 **BioContainers** 是整个生信容器生态的基础设施：

**核心机制：**
- 所有 Bioconda 包自动构建为 Docker/Singularity 容器
- 9000+ 工具、29000+ 软件版本、130000+ 容器
- 遵循 GA4GH TRS 标准的 RESTful API
- 多注册表冗余（DockerHub + Quay.io + Galaxy Depot）

**对 OmicHub 的启示：**
- OmicHub 的工具容器化可以直接复用 BioContainers
- 工具发现可以通过 BioContainers Registry API 增强

### 5.2 CWL (Common Workflow Language) 与工具描述

**CWL 工具描述的核心结构：**

```yaml
cwlVersion: v1.2
class: CommandLineTool
baseCommand: samtools
arguments: [sort]

inputs:
  input_bam:
    type: File
    inputBinding:
      position: 1
  threads:
    type: int?
    default: 1
    inputBinding:
      prefix: "-@"

outputs:
  sorted_bam:
    type: File
    outputBinding:
      glob: "*.sorted.bam"

requirements:
  DockerRequirement:
    dockerPull: biocontainers/samtools:1.9
```

**关键特点：**
- YAML/JSON 格式，人类可读
- 标准化的输入/输出/参数/容器声明
- 支持多个执行引擎（cwltool, toil, Arvados, Rabix）
- 与 bio.tools 和 Dockstore 集成

### 5.3 ELIXIR bio.tools 注册表

**bio.tools** 是 ELIXIR 维护的生物信息学软件注册表：
- 30000+ 工具/数据库的元数据
- 标准化的 **biotoolsSchema** 元数据格式
- 使用 **EDAM Ontology** 标注工具功能、输入输出数据类型
- 提供持久标识符（biotools ID）
- 与 FAIRsharing、re3data 互补

### 5.4 GA4GH 标准族

GA4GH (Global Alliance for Genomics and Health) 定义了多个与工具集成相关的标准：

| 标准 | 用途 |
|------|------|
| **TRS** (Tool Registry Service) | 工具/工作流注册和发现的标准 API |
| **WES** (Workflow Execution Service) | 工作流执行的标准 API |
| **DRS** (Data Repository Service) | 数据访问的标准 API |
| **TES** (Task Execution Service) | 单个任务执行的标准 API |

---

## 6. 跨平台对比总结表

### 6.1 核心维度对比

| 维度 | Galaxy | Terra | DNAnexus | Seqera/Nextflow |
|------|--------|-------|----------|-----------------|
| **注册方式** | Tool Shed 仓库 | Dockstore (GA4GH TRS) | Applet/App 双层体系 | Nextflow Registry + nf-core/modules |
| **Schema 格式** | Tool XML (XSD) | WDL | dxapp.json (JSON) | Nextflow DSL2 + nextflow_schema.json |
| **执行模式** | 异步 Job Runner | 异步 Cromwell | 异步 dx run | 异步 Nextflow |
| **容器化** | Docker/Singularity + BioContainers 自动匹配 | Docker (runtime 声明) | Ubuntu VM (非原生容器) | Docker/Singularity + Wave 按需构建 |
| **依赖管理** | Conda → BioContainers → 按需构建 | Docker 镜像 | 自定义/手动安装 | Conda → BioContainers/Wave |
| **工具粒度** | 单个工具 | 工作流 (WDL) | Applet (可组合) | Process (模块) |
| **AI 集成度** | MCP Server + 工具推荐 + Wizard | FISS-MCP | 低（仅 API） | Co-Scientist AI CLI + 资源优化 |
| **标准兼容** | GA4GH TRS (导入) | GA4GH TRS (Dockstore) | 自定义 | GA4GH TRS (导出) |
| **资源管理** | job_conf.xml 目的地配置 | runtime 块声明 | regionalOptions 实例类型 | label 系统 + 动态优化 |
| **社区规模** | 10000+ 工具 | 4400+ 工作流 | 商业平台 | 1000+ nf-core 模块 |

### 6.2 工具发现机制对比

| 平台 | 发现入口 | 搜索方式 | 版本管理 | 社交功能 |
|------|---------|---------|----------|---------|
| **Galaxy Tool Shed** | Web UI / API | 关键字/分类/标签 | Changeset revision | 评分/评论 |
| **Dockstore** | Web UI / TRS API | 面搜索/组织/标签 | Git tags/branches | 收藏/组织 |
| **DNAnexus** | Tool Library / dx find | 名称搜索 | App 版本号 | 全局/私有 |
| **Nextflow Registry** | Web UI / API | 关键词搜索 | Semantic + commit | 下载统计 |

### 6.3 Schema 表达能力对比

| 能力 | Galaxy XML | WDL | dxapp.json | Nextflow DSL2 |
|------|-----------|-----|-----------|--------------|
| 参数类型 | 丰富 (10+ 类型) | 强类型 | 中等 (基本类型) | 强类型 (Groovy) |
| 条件参数 | conditional/repeat | if/else | 无 | when/branch |
| 动态输出 | filter/change_format | 条件输出 | 固定声明 | optional emit |
| 测试定义 | 内置 tests | 外部测试 | 无内置 | nf-test 框架 |
| 文档嵌入 | help (reST) | 注释 | Readme.md | 注释 + docs |
| 容器声明 | requirements | runtime.docker | runSpec | conda/container |

### 6.4 AI 集成成熟度对比

| 平台 | AI 助手 | 自然语言交互 | 工具发现 AI | 代码生成 | MCP 兼容 |
|------|---------|-------------|------------|---------|---------|
| **Galaxy** | Galactic Wizard | 有限 | RNN 推荐 | 无 | 是 (MCP Server) |
| **Terra** | 无原生 | 无 | 无 | 无 | 是 (FISS-MCP) |
| **DNAnexus** | 无 | 无 | 无 | 无 | 否 |
| **Seqera** | Co-Scientist | 完整 | 自然语言搜索 | 完整 | 间接支持 |

---

## 7. 对 OmicHub 的综合建议

### 7.1 架构设计建议

基于以上调研，建议 OmicHub 采用以下分层架构：

```
+-----------------------------------------------------+
|  AI 助手层 (MCP Server / Function Calling)          |
|  - Co-Scientist 风格的上下文感知助手                  |
|  - 工具发现、参数填充、执行监控                       |
+-----------------------------------------------------+
|  工具注册与发现层 (Tool Registry)                    |
|  - 兼容 GA4GH TRS 标准                               |
|  - 混合注册：中心仓库 + 自定义源                      |
|  - 类似 bio.tools 的元数据标注                       |
+-----------------------------------------------------+
|  工具 Schema 层 (Tool Schema)                        |
|  - JSON Schema 为主 (兼容 nextflow_schema.json 风格) |
|  - 工具描述：输入/输出/参数/容器/测试/帮助            |
|  - EDAM Ontology 语义标注                            |
+-----------------------------------------------------+
|  执行调度层 (Execution Engine)                       |
|  - 同步 (轻量) / 异步 (重计算) 双模式                |
|  - 容器化执行 (Wave/BioContainers 按需构建)          |
|  - 资源管理与优化                                    |
+-----------------------------------------------------+
|  工具箱层 (Toolbox)                                  |
|  - 前端纯计算工具                                    |
|  - 后端同步工具 (KEGG 等)                            |
|  - 后端异步工具 (系统发育树等)                        |
+-----------------------------------------------------+
```

### 7.2 具体设计模式借鉴

| OmicHub 需求 | 推荐借鉴来源 | 具体模式 |
|-------------|------------|---------|
| 工具描述格式 | Seqera schema.json + CWL | JSON Schema 声明 + YAML 工具描述 |
| 工具注册发现 | Galaxy Tool Shed + Dockstore | 中心仓库 + GA4GH TRS API |
| AI 助手集成 | Seqera Co-Scientist + Galaxy MCP | MCP Server + 上下文感知 |
| 容器管理 | Seqera Wave + Galaxy BioContainers | Conda 声明 → 按需容器构建 |
| 资源优化 | Seqera Platform | 实际使用数据分析 + 自动推荐 |
| 工具推荐 | Galaxy RNN Recommender | 基于历史行为的智能推荐 |
| 参数 UI 生成 | Galaxy XML + Nextflow Schema | Schema 驱动自动生成 |
| 测试框架 | Galaxy tests + nf-test | 声明式测试 + 持续集成 |

### 7.3 关键技术决策建议

1. **Schema 格式**：优先使用 JSON Schema，兼容 GA4GH TRS 和 bio.tools 元数据标准
2. **容器策略**：复用 BioContainers 生态，集成 Wave 按需构建能力
3. **AI 集成**：以 MCP Server 为核心，参考 Co-Scientist 的三层上下文架构
4. **执行模式**：轻量工具同步执行，计算密集型工具异步执行
5. **标准兼容**：优先兼容 GA4GH TRS 和 CWL/WDL 导入导出

### 7.4 实施优先级

| 优先级 | 任务 | 参考平台 |
|-------|------|---------|
| P0 | 定义工具 JSON Schema | CWL + Seqera schema |
| P0 | 实现 MCP Server 工具暴露 | Galaxy MCP + FISS-MCP |
| P1 | 构建工具注册中心 | Galaxy Tool Shed + Dockstore |
| P1 | 容器化执行集成 | Wave + BioContainers |
| P2 | AI 工具推荐 | Galaxy RNN Recommender |
| P2 | 资源自动优化 | Seqera Platform |
| P3 | GA4GH TRS 兼容 | Dockstore |

---

> **文档结束**
>
> 本报告基于对 Galaxy Platform、Terra (Broad Institute)、DNAnexus、Seqera Platform 的深度调研，覆盖工具注册发现机制、Schema 定义、执行调度、AI 集成等核心维度，并结合 BioContainers、CWL、GA4GH 标准等开放生态，为 OmicHub 平台的 AI 助手与工具联动架构提供设计参考。
