# OmicHub 工作区文件全局可见性优化实施计划

> 依据：《OmicHub 工作区文件全局可见性架构审查报告》（Kimi Code 只读审查，2026-08-14）
> 及评审核对结论（Part 4）。本文档为分阶段实施计划，每阶段含可直接粘贴给编码 Agent
> 的提示词块与验收 checklist。执行原则：**先读现有代码再改，禁止重构无关模块**。

## 一、背景与目标

**现状一句话**：骨架已具备（`file_records` 索引 + `StoragePathFactory` + 用户级权限隔离），
但四个模块的产出未全部回流到 `file_records`，且无存储后端抽象——"统一可见"是局部现实，
云/本地双部署未就绪。

**目标**：

1. 四个模块（AI 助手 / Studio 工作台 / 团队协作 / 生信工具箱）+ 报告中心，
   所有产出统一注册进 `file_records`，AI 助手 `list_workspace_files` 可见一切；
2. 文件读写收敛到统一网关，权限校验单点可审计；
3. `storage.type = local|s3` 配置化，本地私有化与云端 SaaS 一套代码两个形态。

## 二、总体策略与阶段划分

与审查报告"先抽象统一层"的顺序有一处**有意调整**：把"统一注册"抽为阶段 0 前置。
理由：注册只写元数据索引（`file_records` 存相对路径 + source），不依赖存储后端形态，
与后续抽象层零冲突；且改完立即使"统一可见"从口号变事实，收益最快。

```
阶段 0：产出统一注册（止血，不动架构）          ~1-2 周
阶段 1：StorageBackend 抽象 + 部署配置化        ~2-3 周
阶段 2：FileService 唯一网关收敛（含权限收口）  ~2-3 周
阶段 3：团队协作空间与成员 ACL                  ~2 周
阶段 4：云端部署适配（沙盒投递/双层存储模型）   ~2-3 周
```

阶段 0 与阶段 1 可并行（不同代码区域）；阶段 3 依赖阶段 2 的 scope 概念；
阶段 4 依赖阶段 1 的后端抽象。

---

## 三、阶段 0：产出统一注册（止血前置）

**目标**：四条断裂链路全部回流 `file_records`，AI 助手能看见所有模块的产出。
**原则**：只加注册调用与必要的目录归置，不改存储架构、不改寻址协议。

### 任务清单

| # | 任务 | 现状断点 | 改法 |
|---|------|---------|------|
| 0.1 | 梳理 `FileRegistry.register()` 现有签名与调用方，确定统一注册入口（补齐 source / task_id / 相对路径字段规范） | 注册入口已存在但调用方稀少 | 只做签名确认与文档化，不改行为 |
| 0.2 | Studio `artifact_register` 补调 `FileRegistry.register`（source=`STUDIO`） | 只写 `report_files`，产出已复制到 `users/{uid}/projects/...` 但未入索引（`studio/workspace.py`、`api/v1/studio.py`） | 在现有复制完成后追加注册；保持幂等（重复注册更新而非插重） |
| 0.3 | 分析流程成功完成时批量注册 output 产物（source=`PIPELINE`，关联 task_id） | `projects/{proj}/runs/{ts}/output` 未入索引（仅 EBI/下载任务例外） | 在流程完成钩子处扫描 output 目录注册；失败任务不注册 |
| 0.4 | 聊天轻量沙盒产物注册（source=`CHAT_SANDBOX`） | 产物在 `chat_sandbox/{uid}/{session}/output`，仅作消息附件 | 方案 A（推荐）：执行结束后复制到 `users/{uid}/workspace/chat-output/` 并注册，返回 file_id 供对话引用；方案 B（最小改）：原地注册。任选其一，A 体验更好 |
| 0.5 | 报告中心与文件中心对齐：`create_report_from_task` 生成报告文件时同步写 `file_records` 行（source=`REPORT`） | `report_files` 存绝对路径、与 `file_records` 两张表 | 注册时存相对路径；`report_files.path` 保留不动，避免破坏报告中心现有逻辑 |
| 0.6 | AgentTeams 证据暂不注册（依赖 MinIO 去留决策，见阶段 3），仅在 `file_records` 预留 `source` 枚举值 | 与 `file_records` 完全隔离 | 仅加枚举占位 |

### 阶段 0 提示词

```text
你是一名资深全栈工程师。本项目为 OmicHub 生信分析平台（Python 后端，文件索引表
file_records，注册入口 FileRegistry）。先阅读以下文件再动手，禁止重构无关代码：
- src/omichub/application/services/file_service.py（list_workspace_files:343）
- src/omichub/infrastructure/studio/workspace.py 与 api/v1/studio.py（artifact_register）
- src/omichub/application/services/pipeline_result_service.py 与 task_service.py
- src/omichub/infrastructure/sandbox/chat_sandbox_tools.py（:132 附近）
- src/omichub/application/services/report_service.py（create_report_from_task）

任务：把四个模块的文件产出统一注册进 file_records，使 AI 助手的 list_workspace_files
能看到所有产出。逐条实施：
1. Studio：artifact_register 现有复制逻辑完成后，追加 FileRegistry.register
   （source=STUDIO），幂等（重复注册更新而非插入重复行）
2. 分析流程：任务成功完成钩子处扫描 runs/{ts}/output 目录，批量注册（source=PIPELINE，
   关联 task_id）；失败/取消任务不注册
3. 聊天沙盒：执行结束后将 output 产物复制到 users/{uid}/workspace/chat-output/ 并注册
   （source=CHAT_SANDBOX），同时在聊天响应中返回 file_id，使后续对话可 @ 引用
4. 报告中心：create_report_from_task 生成报告文件时同步写 file_records（source=REPORT，
   存相对路径）；report_files 表保持不动
5. file_records 的 source 枚举补充 STUDIO/PIPELINE/CHAT_SANDBOX/REPORT/AGENTTEAMS（占位）

要求：
- 注册失败不阻断主流程（log + 重试一次后降级跳过），但不能静默吞错
- 大文件（BAM/FASTQ 等）只注册元数据，不做任何内容读取
- 每条改动附单元测试：模拟对应模块产出 → 断言 list_workspace_files 可见

验收：
- [ ] Studio 跑一次分析后，问 AI 助手"工作区里有哪些新文件"能列出 Studio 产物
- [ ] 流程跑完后 output 产物出现在文件中心与 AI 助手目录清单
- [ ] 聊天沙盒产出的图表文件可被下一轮对话 @ 引用
- [ ] 报告中心文件在统一文件列表可见，且报告中心原有预览/下载不回归
```

---

## 四、阶段 1：StorageBackend 抽象 + 部署配置化

**目标**：文件实体读写收敛到可插拔后端；`storage.type = local|s3` 成为真正的后端选择器。

### 任务清单

| # | 任务 | 说明 |
|---|------|------|
| 1.1 | 定义 `StorageBackend` 接口 | `read(path, offset, limit)` / `write(path, content)` / `list(dir)` / `delete(path)` / `exists(path)` / `get_local_path(path)`（为必须 POSIX 的场景兜底，local 直接返回、s3 抛 Unsupported 或触发物化） |
| 1.2 | `LocalStorageBackend`：复用 `StoragePathFactory` 现有逻辑搬入 | 行为与现状完全一致，纯搬迁 |
| 1.3 | `S3CompatibleStorageBackend`：基于已有 MinIO SDK 封装（复用 `minio_store.py` 的连接配置） | 对象键规范：`users/{uid}/...` 与现有相对路径模型一一对应 |
| 1.4 | 配置化：`data/OmicHub.yaml` 增加 `storage.type`、`storage.s3.{endpoint,bucket,region,access_key}`；`core/config.py` 增加 `deployment_mode = local\|cloud` | local 部署默认全 local；cloud 默认 s3 |
| 1.5 | `file_records` 表增加 `storage_backend` 字段（默认 `local`），为双后端共存做准备 | 迁移脚本 + 默认值回填 |
| 1.6 | `FileService` 内部读写改为经 StorageBackend，对外签名不变 | 此阶段只改 FileService 内部，其他模块仍在阶段 2 收敛 |

### 阶段 1 提示词

```text
你是一名资深后端工程师。本项目 OmicHub（Python，FastAPI + SQLAlchemy），当前文件
读写全部基于本地 pathlib（StoragePathFactory 拼路径，FileService 用 Path.resolve），
仅 AgentTeams 证据用了 MinIO（infrastructure/storage/minio_store.py）。
先阅读这些文件再动手：
- src/omichub/infrastructure/storage/path_factory.py
- src/omichub/application/services/file_service.py
- src/omichub/infrastructure/storage/minio_store.py
- src/omichub/core/config.py 与 data/OmicHub.yaml

任务：引入可插拔存储后端抽象。
1. 定义 StorageBackend 抽象接口：read(path, offset, limit) / write(path, content) /
   list(dir) / delete(path) / exists(path) / get_local_path(path)
2. LocalStorageBackend：搬迁 StoragePathFactory 现有逻辑，行为与现状完全一致
3. S3CompatibleStorageBackend：基于 minio_store.py 已有连接封装，对象键与现有
   users/{uid}/... 相对路径一一对应
4. 配置：OmicHub.yaml 增加 storage.type=local|s3 与 storage.s3.* 连接项；
   config.py 增加 deployment_mode=local|cloud；依赖注入按配置选择后端
5. file_records 增加 storage_backend 字段（默认 local，写迁移脚本回填存量行）
6. FileService 内部所有 Path 读写改走 StorageBackend，对外方法签名不变

要求：
- local 模式下全量回归测试必须通过（行为零变化是本阶段的硬约束）
- s3 模式至少跑通：上传 → list_workspace_files → preview → 下载 全链路
- 禁止在本阶段改动 Studio / 流水线 / AgentTeams 的存储调用（属后续阶段）

验收：
- [ ] storage.type=local 时平台行为与改造前完全一致（回归测试全绿）
- [ ] storage.type=s3（本地 MinIO 模拟）时上传/预览/下载链路可用
- [ ] 切换后端只需改配置，无需改代码
```

---

## 五、阶段 2：FileService 唯一网关收敛（含权限收口）

**目标**：消灭绕过 FileService 的直接 Path 读写；权限校验单点可审计。

### 任务清单

| # | 任务 | 依据（审查报告风险编号） |
|---|------|------------------------|
| 2.1 | 全仓清点 `Path.read_text / write_bytes / open(` 的直接调用点，按模块列清单，逐一改走 FileService/StorageBackend | 风险 1 |
| 2.2 | BLAST 等旧工具配置中的原始路径寻址改为 file_id / 统一校验入口 | 风险 7（`tool_configs/blast/blast_config.yaml:5-7`） |
| 2.3 | `_normalize_directory` 对 `..` 由静默剔除改为显式拒绝（抛 400），统一非法路径语义 | 权限风险（`file_service.py:264`） |
| 2.4 | 统一大文件"元数据 + 预览"接口：收敛 `/files/preview`（>400KB 空行）、MCP 5MB 上限、Studio 2000 行三套策略为单一预览服务，二进制文件统一只返回元数据 | 风险 10 |
| 2.5 | 沙盒内文件访问：Studio agent 经平台 API 或统一挂载访问工作区，不再直接拼宿主路径 | 风险 6 |
| 2.6 | 寻址协议收敛：对外统一 `file://{UUID}` 为唯一文件引用协议；`upload://` 保留为兼容别名（内部解析到 file_records），新代码禁止再引入新协议 | 体验不一致风险 8 |

### 阶段 2 提示词

```text
你是一名资深后端工程师。OmicHub 平台已完成 StorageBackend 抽象（阶段 1），FileService
内部已走统一后端。本阶段任务：把所有绕过 FileService 的文件读写收敛到统一网关，
并收口权限校验。先全仓搜索清点，再逐模块修改；禁止改变任何模块的功能行为。

1. 全仓搜索 Path.read_text / write_bytes / open( / os.remove 等直接文件操作，
   输出调用点清单（按模块分组），先给我确认清单再动手
2. 逐模块改走 FileService / StorageBackend：
   - pipeline_controller.py、pipeline_result_service.py
   - tool_bridge_service.py、tools/blast/（含 tool_configs/blast/blast_config.yaml
     的原始路径寻址改为 file_id 或经 FileService 校验的路径解析）
   - studio/manager.py、studio/workspace.py 中宿主侧文件操作
3. file_service.py 的 _normalize_directory：对 .. 由静默剔除改为显式拒绝（HTTP 400），
   检查所有调用方确认无误判后切换
4. 新增统一预览接口 FileService.preview(file_id, max_lines, max_bytes)：文本按行/字节
   截断，二进制只返回元数据（大小/类型/修改时间）；改造 /files/preview、MCP
   workspace_read_file、Studio workspace_read 三处共用此接口，收敛三套截断策略
5. 寻址收敛：file://{UUID} 为唯一对外引用协议；upload:// 保留为兼容别名内部解析到
   file_records；代码中新增其他 URI 协议的，在 code review 约定中明确禁止

要求：
- 每个模块改完跑该模块现有测试 + 冒烟（上传/读取/流程执行）
- 权限收口后补一组越权测试：用户 B 的 token 访问用户 A 的 file_id 各入口必须 403/404

验收：
- [ ] 清点清单中的直接 Path 操作全部收敛（残留项需逐条书面说明理由）
- [ ] .. 路径在各入口统一返回 400，不再静默剔除
- [ ] BAM 等大文件在 AI 助手 / Studio / 工具箱三处均只返回元数据，行为一致
- [ ] 越权测试全绿
```

---

## 六、阶段 3：团队协作空间与成员 ACL

**目标**：团队/共享空间成为一等存储主体；成员可见彼此文件有真实授权模型支撑。

### 任务清单

| # | 任务 | 说明 |
|---|------|------|
| 3.1 | `file_records` 增加 `owner_scope`（`personal` / `team`）+ `team_id` 字段 | 支撑共享空间实体 |
| 3.2 | 成员角色模型：READER / WRITER / OWNER（对标业界 workspace 三级权限），权限判定收敛到 FileService 单点 | 依赖阶段 2 的网关收敛 |
| 3.3 | AgentTeams 证据去留决策：**建议**保留 MinIO 作为证据暂存，但案例归档产物注册进 `file_records`（source=`AGENTTEAMS`，owner_scope=team），统一列表 API 聚合"个人文件 + 团队文件" | 避免证据高频读写冲击主索引 |
| 3.4 | 协作室 UI：团队空间目录树与个人空间并列展示，权限不足的操作按钮置灰并提示 | 前端配合 |

### 阶段 3 提示词

```text
你是一名资深全栈工程师。OmicHub 已完成统一存储抽象与 FileService 网关收敛
（阶段 1、2）。本阶段实现团队协作空间与成员权限。先阅读：
- src/omichub/api/v1/agentteams.py（context_refs 现状）
- src/omichub/infrastructure/storage/minio_store.py
- src/omichub/application/services/file_service.py

任务：
1. file_records 增加 owner_scope（personal/team）与 team_id 字段，含迁移脚本
2. 实现团队成员角色模型（READER/WRITER/OWNER），所有文件访问在 FileService 单点
   判定：个人文件仅 owner；团队文件按角色（READER 只读，WRITER 可写不可删他人文件，
   OWNER 全权）
3. AgentTeams 证据保留 MinIO 暂存；案例完成/归档时将关键产物注册进 file_records
   （source=AGENTTEAMS，owner_scope=team）；统一文件列表 API 聚合个人 + 团队文件
4. context_refs 保留为引用记录，不再承担授权职责
5. 协作室前端：团队空间与个人空间并列目录树；无权限操作置灰 + tooltip 说明

验收：
- [ ] 团队成员按角色看到对应文件集合；越权访问返回 403
- [ ] 案例归档产物在团队空间可见，AI 助手在团队上下文中可列出
- [ ] 个人空间文件对团队成员不可见（除非显式共享）
```

---

## 七、阶段 4：云端部署适配

**目标**：`deployment_mode=cloud` 时平台完整可跑；本地私有化安装有前置校验。

### 任务清单

| # | 任务 | 说明 |
|---|------|------|
| 4.1 | 沙盒资料投递：cloud 模式下 Studio/Terminal 容器不再 bind-mount 工作区，改为执行前按 file_id 清单物化到临时 POSIX scratch 卷，执行后产物回传对象存储并注册 | 生信工具必须 POSIX，采用"对象存储持久层 + 临时 POSIX 执行卷 + 同步器"双层模型 |
| 4.2 | 大文件传输：预签名 URL 上传/下载，绕过应用服务器 | 依赖阶段 1 的 S3 后端 |
| 4.3 | 本地私有化安装前置校验脚本：Docker socket 可用性、bind mount 权限、容器 UID/GID、多机部署时 RWX（NAS/NFS/CephFS）检测 | 审查报告 4.2 节缺口 |
| 4.4 | `deployment_mode` 驱动差异项集中声明（沙盒挂载方式、URL 生成、产物回收策略），禁止散落 if-else | 配置收口 |

### 阶段 4 提示词

```text
你是一名资深平台工程师。OmicHub 已完成 StorageBackend 抽象（local|s3）与
deployment_mode 配置。本阶段实现云端部署适配。先阅读：
- src/omichub/infrastructure/studio/manager.py（bind-mount 现状 :393-399）
- src/omichub/infrastructure/terminal/docker_manager.py（:111,121）
- src/omichub/infrastructure/storage/（StorageBackend 实现）

任务：
1. cloud 模式下 Studio/Terminal 容器执行流程改为：解析输入 file_id 清单 →
   从对象存储物化到临时 POSIX scratch 卷 → 容器挂载 scratch → 执行结束后扫描
   output → 回传对象存储 → FileRegistry.register → 回收 scratch
2. local 模式保持现有 bind-mount 不变（本地私有化性能优先）
3. 实现预签名 URL 上传/下载（大文件不经过应用服务器）
4. 编写私有化部署前置校验脚本：Docker socket、bind mount、UID/GID、
   多机部署时检测 RWX 共享存储并给出明确报错文案
5. deployment_mode 差异项集中到单独模块声明，业务代码不出现 deployment_mode 判断

验收：
- [ ] MinIO 模拟云端环境：Studio 完整分析流程跑通，产物回流 file_records
- [ ] local 模式回归零变化
- [ ] 10GB 级文件上传下载走预签名，应用服务器内存无峰值
- [ ] 前置校验脚本在缺 Docker 权限 / 无共享存储的机器上给出可操作的报错
```

---

## 八、全局风险与回退

| 风险 | 缓解 |
|------|------|
| 阶段 0 注册改动引入重复行 | register 幂等设计（file_id 唯一约束 + upsert）；上线前存量数据跑一次回填脚本 |
| 阶段 2 收敛面广、易回归 | 先出清点清单人工确认；每模块独立 PR 独立回归；残留项书面记录 |
| `..` 改显式拒绝可能误伤存量调用 | 先加"拒绝 + 告警日志"灰度模式观察一周，再转硬拒绝 |
| 阶段 3 权限模型影响现有协作室 | 默认全部 personal 不启用 team 逻辑，功能开关灰度 |
| 阶段 4 物化/回传增加大文件延迟 | scratch 卷用本地 NVMe；物化清单只含任务声明的输入，不做全量同步 |

## 九、总体验收 checklist（全部阶段完成后）

- [ ] 任一模块产出文件后，AI 助手 `list_workspace_files` 立即可见
- [ ] 同一文件在四个模块 + 报告中心用同一 `file://` 引用可互相跳转
- [ ] `storage.type=s3` + `deployment_mode=cloud` 全流程跑通；`local` 回归零变化
- [ ] 团队成员按 READER/WRITER/OWNER 看到正确文件集合
- [ ] 越权访问测试（跨用户、跨团队、路径穿越）全绿
- [ ] BAM/FASTQ 等大文件全平台只走元数据 + 预览，无全量读取路径
