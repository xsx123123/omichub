# R4 投喂用：P3 提示词（按 R3 实测修订稿）

> 版本：v1.0（2026-10-28）
> 来源：《CygnusX报告查看与AI解读Copilot实现计划.md》第八节 P3 提示词全文
> 修订依据：《CygnusX报告Copilot_R3沙箱能力核实.md》（同目录）
> 修订动作（手册 R4 节规定的两处）：
> 1. 「前置确认」段已替换为 R3 实测结论（逐项标代码位置）；
> 2. 开头追加「阶段 0」（R3 阻断缺口 G1–G4），完成并验证前禁止注册执行工具。
> 投喂前提：R3 报告经人工核对通过；R2 真实验收全部通过。

---

```text
你是一名资深后端/平台工程师。在 P2 已完成的 AI 面板中新增沙箱执行工具，使 AI 能对当前
项目结果数据做代码级高级分析。先阅读沙箱调用契约
（src/cygnusx/infrastructure/studio/manager.py#StudioSandboxManager.exec、
deploy/studio/sandbox_agent.py#_stream_exec）与 P2 工具注册机制，遵从既有规范。

## 阶段 0：先补齐以下四项能力并测试强制边界，完成并验证前禁止注册执行工具

（以下缺口来自 R3 沙箱能力核实报告，逐项给了实现参照点）

1. 项目粒度只读挂载：新增「项目结果根 → 容器 /data（ro）」的注册式挂载机制，
   projectId 由后端从会话上下文注入，模型不可指定；宿主路径强制限定在存储根内。
   实现参照：manager.py:186 register_workdir_mount 的注册模式、
   manager.py:798 _container_mounts_match 的复用前挂载基线校验（缺挂载/源不匹配
   自动重建容器）、manager.py:195-199 的存储根防逃逸校验。
   现状红线：现有 ro 挂载是整个用户目录（manager.py:510-524），Copilot 沙箱
   不得沿用该粒度，必须收窄到当前项目结果根。
2. 常驻解释器跨轮状态：现有执行器每次新建子进程（sandbox_agent.py:581
   create_subprocess_shell），容器/文件复用不等于变量保留。须在 sandbox-agent
   补常驻解释器协议（同对话内变量/中间结果跨轮保留，对话结束或超时销毁），
   并用测试验证跨轮变量；不允许默默缩减为文件级状态。
3. 执行计费接线：沙箱执行路径当前零计费（studio_tools.py 无 CookieService 调用）。
   按执行 ID 做 pre_deduct（预估时长）→ 执行 → settle（按 result 事件的
   duration_ms 实结，多退少补）→ 异常/取消 refund；幂等仿
   cookie_service.py:221 的按 source 查重模式。接口现成：
   cookie_service.py:114 pre_deduct / :135 settle / :182 refund，
   任务链路实战范例 task_cookie_consumer.py:47/74/90。
4. 保存强制确认不可旁路：现有审批可被 auto_approve=true（chat_service.py:2745-2748）、
   permissions.always_allow（studio_approval_service.py:78-90）、非 supervised
   权限模式绕过。「保存到项目产物」必须每次由人类确认具体文件内容，走不受这三条
   旁路影响的强制确认通道（如专用 approval_kind 或独立拦截名单），服务端一次性
   凭证不可被模型自证或自动审批跳过。可复用框架：
   studio_approval_service.py（Redis 跨进程记录 + BLPOP 决议 + audit_logs 审计）、
   前端 ApprovalCard.vue / PendingApprovalBar.vue。

阶段 0 验收：四项各有针对强制边界的测试（越界挂载被拒绝且容器重建、跨轮变量
保留与销毁、预扣/实结/退款流水与幂等、auto_approve 与 always_allow 下保存仍
弹确认）。

## 前置确认（R3 实测结论，以下为已具备能力，直接复用，禁止重造）

- 调用契约：manager.py:1199 exec（session_id/language/code/timeout/image/user_id
  → NDJSON 流，终态 result 含 exit_code/duration_ms/artifacts/run_log）；
  宿主↔容器走工作区 Unix Socket，不发布端口。
- 网络策略已具备：studio_loader.py:79 StudioNetworkConfig，mode 默认 none
  （容器 network_mode=none，manager.py:655-656）；whitelist 模式为每会话
  internal bridge + 出站代理（manager.py:257，egress_proxy.py：仅放行
  studio.yaml sandbox.network.allow 声明域名、拒绝 IP 字面量与私网、DNS 固定
  公网 IP、仅 80/443）。放行 PyPI/CRAN 仅需把域名写入 allow 并切 whitelist。
- 资源限额已具备：2C/4G/pids512/只读 rootfs/uid 10001/cap_drop ALL/
  no-new-privileges/seccomp（manager.py:627-654，默认值 studio_loader.py:130-150）；
  执行超时 min(请求值, 600s 默认, 3600s 上限) 且超时整进程组强杀
  （sandbox_agent.py:516/586/682）；单通道流内输出 10KB 上限、超出落 .logs
  溢出并结构化标注（sandbox_agent.py:51/594-638/736-740）；工作区配额 10GB。
- 隔离与销毁已具备：一会话一容器（manager.py:238）、TTL 空闲回收（:1178）、
  hibernate/stop/purge_workspace（:1103/:1150/:1171）、复用前安全基线与挂载
  基线校验（:833/:798）。
- 产物登记主链路已具备：studio_context_service.py:488 register_artifact_report
  （/workspace/output 产物复制进项目运行目录并登记报告中心版本树）。
- 计费接口与 HITL 框架已具备（见阶段 0 第 3/4 项引用位置）。

## 权限边界（硬性要求，逐条对应实现与测试）

1. 数据挂载：沙箱启动时仅将「当前项目」的结果目录以只读挂载到容器内 /data；
   projectId 由后端从会话上下文注入，模型不可指定。另挂会话级可写工作区 /workspace。
   （依赖阶段 0 第 1 项落地；阶段 0 完成前本工具不得注册。）
2. 网络：默认禁出网（沿用现有 none 基线）；如需装包，仅按前置确认中的白名单
   机制放行 PyPI/CRAN 域名，其余拒绝。
3. 限额：沿用现有 2C/4G 硬限额与超时/输出截断机制；Copilot 会话如需不同档位，
   走配置而非代码常量。超限即终止并返回结构化错误（沿用现有行为）。
4. 确认门：AI 将 /workspace 中的产出「保存到项目产物」时，前端弹确认卡片
   （文件名/类型/大小/预览），用户确认后才执行注册；AI 无权直接写项目正式目录。
   确认不得被 auto_approve/always_allow/权限模式旁路（阶段 0 第 4 项）。
5. 计费：执行前按预估时长预扣积分，结束后按实际用量实结多退少补；余额不足时
   在对话内明确提示，不发起执行（阶段 0 第 3 项接线后复用）。

## 功能需求

1. 新工具 run_sandbox_code：入参 {language, code, purpose}；返回 {stdout/stderr 摘要,
   生成文件清单（含图表）, 资源用量}；图表以图片形式直接渲染进对话消息。
   资源用量至少含 duration_ms（result 事件现成），CPU/内存峰值可复用
   manager.py:1048 metrics 快照模式补充。
2. 会话复用：同一对话内沙箱会话持续（变量/中间结果保留，依赖阶段 0 第 2 项的
   常驻解释器协议），对话结束或超时后销毁；复用现有 TTL 回收与
   hibernate/stop 生命周期管理。
3. 产出注册：确认保存的产出登记到项目产物列表（数据管理/报告中心可见），记录来源
   「AI 沙箱分析」与关联对话 ID；在 register_artifact_report 链路上扩字段实现。
   这是与既有模块的闭环点，必须有。
4. 典型场景自检（作为 e2e 用例，用合成夹具数据）：
   a. 「用差异分析结果重画一张火山图，标注我指定的基因」→ 返回图片；
   b. 「对富集结果按 p.adjust < 0.01 过滤并统计各 ONTOLOGY 条目数」→ 返回表格；
   c. 恶意/越权用例：代码中尝试访问宿主/其他项目/其他会话数据、尝试出网、
      尝试写项目目录 → 均被阻断并返回明确错误（记录错误信息与阻断位置）。
      容器运行库、解释器及 /tmp 等必要路径本身不作为未授权数据；
      另验证目录穿越/软链（防逃逸实现参照 manager.py:178 workspace_dir、
      manager.py:195-199）。
5. 降级：沙箱服务不可用时工具返回「暂不可用」结构化错误（复用
   StudioSandboxUnavailableError 语义），对话面板其他功能不受影响。

## 验收标准

- [ ] 阶段 0 四项边界测试全部通过
- [ ] e2e 场景 a/b 通过，图表渲染进对话，数据与产物文件一致
- [ ] 越权用例 c 三项全部阻断，后端日志/审计有记录（不接受仅前端表现为据）
- [ ] 保存产出经确认卡片后出现在数据管理产物列表，来源字段正确，
      且在 auto_approve / always_allow / 非 supervised 三种模式下确认均不可跳过
- [ ] 积分预扣/实结流水正确，按执行 ID 幂等（重复结算不重复扣费），余额不足路径有提示
- [ ] 对话内多轮代码执行共享沙箱变量状态；关闭对话后沙箱销毁（查容器清单为据）
```

---

## 投喂检查单（用户侧）

- [ ] R3 报告已人工核对（尤其 G1–G4 缺口判断无异议）
- [ ] R2 真实验收全部通过
- [ ] 本提示词块整体复制投喂，占位符无残留
