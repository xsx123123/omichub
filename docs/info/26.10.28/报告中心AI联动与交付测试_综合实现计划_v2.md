# 综合任务：报告中心 AI 联动 + 报告交付物自动化测试（优化版 v2）
> 优化点：iframe 安全模型改为 postMessage bridge（防同源 XSS）；路径穿越规则明确化；划选长度截断与章节提取策略；技术栈假设写入；执行顺序调整（消毒先行）；增加 E2E 测试项。
> 使用方式：整段交给编码 Agent。先执行【探索阶段】，再进入开发。

═══════════════════════════════════════
# 0. 探索阶段（编码 Agent 必须先做）
═══════════════════════════════════════

在写任何代码前，先完成以下探索并打印到控制台：
1. `ls -R /data/omichub/Flow_report/X101SC26098749-Z01-J001/` 并打印树形结构；
2. `cat /data/omichub/Flow_report/X101SC26098749-Z01-J001/report.paths.json`（打印原始 JSON，推断路径格式）；
3. `cat /data/omichub/Flow_report/X101SC26098749-Z01-J001/delivery_manifest.json | head -n 30`（打印前 30 行，推断清单结构）；
4. `head -n 50 /data/omichub/Flow_report/X101SC26098749-Z01-J001/project_summary.json`（推断模块分区键名）；
5. 检查现有前端技术栈：查看 package.json 中的主要依赖（React/Vue、UI 库、现有 AI 助手组件位置）。

**以上 5 条结果未打印出来，不允许进入 T1 开发。**

═══════════════════════════════════════
# 第一部分：报告中心 × AI 联动（Feature）
═══════════════════════════════════════

## F1. 功能定义

结果报告中心打开报告在线预览：主区渲染报告 HTML（Plotly 可交互），右侧 AI 问答抽屉；用户在 HTML 中划选内容 → 弹"问 AI"悬浮按钮 → 点击自动填充【选中内容+报告上下文】到 AI 输入框 → 追问 → AI 基于上下文回答。

## F2. 技术栈假设（不要引入新框架）

- 前端：现有 React 应用（由 package.json 确认），复用现有 UI 组件库（如 Ant Design / shadcn）；
- AI 抽屉：复用现有 AI 助手/工作台组件（SSE 流式、会话管理），不要重写聊天引擎；
- 后端：现有 FastAPI/Flask（由 requirements 确认），新增只读端点；
- 报告 HTML：自包含（Plotly 离线模式，图表数据内嵌 JSON），无外部 CDN。

## F3. 关键决策（已修正安全模型）

| 决策点 | 方案 | 理由 |
|---|---|---|
| 嵌入 | iframe（sandbox="allow-scripts" **无 allow-same-origin**），src 为 Blob URL 或 `about:blank` 后写入内容 | **禁止同源**：防止报告 HTML 中任何脚本访问 parent 的 localStorage/cookie/DOM。Blob URL origin 为 null，天然隔离 |
| 跨帧通信 | iframe 内注入轻量 bridge 脚本：监听 mouseup/keyup → getSelection() → 通过 `window.parent.postMessage({type:'selection', text, section, path}, '*')` 传出。Parent 校验 `event.origin === "null"` 或 `event.source === iframe.contentWindow` 后接收 | 同源隔离下，标准跨域通信方式；bridge 脚本在写入 iframe 时注入，内容可控 |
| 文件服务 | 受控只读端点 `GET /api/reports/{report_id}/file/{relpath}`：鉴权 + 路径穿越防护（见 F5）+ Content-Type 白名单（html/png/pdf/csv/tsv/json/md/txt） | 不暴露文件系统；复用平台权限模型 |
| 划选捕获 | iframe 内 bridge 脚本：mouseup 非空选区 → 取文本 + 就近章节标题（见 F4 章节提取策略）+ 文件路径；选区非空且文本长度 >0 才触发 | 空白点击不误触发 |
| 划选长度 | 截断策略：选中文本 > 2000 字符时，取前 1800 字符 + "...（已截断）"，悬浮按钮旁显示黄色警告图标"选中内容过长，已自动截断" | 防止用户误划整页导致上下文爆炸；AI token 可控 |
| 填充时机 | 划选后弹悬浮【问 AI】按钮（选区右下，防溢出），点击才填充，不自动塞 | 不打断阅读流 |
| AI 面板 | 右侧抽屉，复用现有 AI 会话组件（SSE 流式）；会话严格绑定 report_id + run_id + flow_type；**切换报告时自动清空上下文并新开会话** | 防止跨报告上下文污染 |

## F4. 章节标题提取策略（必须明确，不要猜）

iframe 内 bridge 脚本按以下优先级找"最近章节标题"：
1. 向上遍历 DOM，找最近的 `<h1>`, `<h2>`, `<h3>` 标签的 innerText；
2. 若无 heading 标签，找最近的 `.section-title`, `.panel-title`, `[data-section]` 等 class（先打印实际 HTML 结构，观察生成端用了哪些标记，再定具体 selector）；
3. 仍无则取当前元素最近的 `<caption>` 或 `<th>` 文本；
4. 仍无则标记为"未命名区域"。

**Agent 必须在探索阶段打印 HTML 前 200 行，确认 heading 结构后再写提取逻辑。**

## F5. 路径穿越防护规则（后端硬编码，不可省略）

端点 `GET /api/reports/{report_id}/file/{relpath}` 必须逐条校验：
1. `report_id` 存在且当前用户有读权限；
2. `relpath` 不得以 `/` 开头；
3. `relpath` 不得包含 `..` 或空字节 `\x00`；
4. 拼接后路径 `report_root / relpath` 必须位于 `report_root` 之内（用 `pathlib.Path.resolve()` 比对）；
5. 后缀在白名单内（html/png/pdf/csv/tsv/json/md/txt）；
6. 拒绝目录遍历请求（不以文件结尾的请求返回 400）。

违反任一条返回 **403**（穿越/越权）或 **400**（非法格式），不返回 404 以隐藏文件存在信息。

## F6. 大文件策略

- 在线预览阈值：**>10MB** 的 HTML 默认不 iframe 渲染，直接展示"文件过大（{size}），建议下载后本地查看" + 下载按钮；
- 10MB 以内正常 iframe 加载，加骨架屏（Loading...）；
- 加载超时（>10s）自动降级为下载提示。

## F7. 安全与免责

- **消毒层位置**：后端优先。T1 端点返回 HTML 前，用 DOMPurify（Python 可用 nh3 或 bleach 替代，或 Node 预渲染）按白名单消毒：允许标签 `div,span,p,h1-h6,table,thead,tbody,tr,td,th,img,svg,script(仅内联 Plotly 相关),style`；允许属性 `class,id,style,data-*,src(仅 data:)`；`script` 标签内容必须匹配 Plotly 已知 hash 或白名单正则，否则整标签剥离；
- iframe 额外加 `referrerpolicy="no-referrer"`；
- AI 回答页脚常驻"AI 解读仅供参考，关键结论请复核原始数据与流程参数"；
- 用户在 AI 抽屉发送第一条消息前，弹一次轻量提示"即将把报告选中内容发送至 AI 助手，请勿发送敏感个人信息"（一次即可，可勾选"不再提示"）。

## F8. 上下文模板（填充格式）

```
【报告上下文】
报告：{report_title}（run: {run_id}，流程：{flow_type}）
章节：{section_heading}
选中内容：
"""
{selected_text}
"""
请基于上述报告上下文回答我的问题：
```

服务端把 report_id 注入会话元数据；AI 侧若有报告读取工具，可自动调取该 run 的 project_summary.json 做数字复核。

## F9. 任务拆解

| # | 任务 | 验收标准 |
|---|---|---|
| T1 | 报告文件受控端点（鉴权、F5 路径穿越防护、类型白名单） | 未登录 401；路径穿越 403；白名单外 400；示例 run 的 report.paths.json 内文件全部可经端点下载 |
| T5 | 后端消毒层：HTML 返回前过白名单消毒；构造 `<script>alert(1)</script>` 的请求，响应中必须不含该脚本 | 注入脚本被剥离；Plotly 内联脚本保留 |
| T2 | ReportViewer 页：iframe 用 Blob URL + bridge 脚本加载 HTML；加载失败降级（下载按钮）；10MB 以上自动降级 | 示例 run X101SC26098749-Z01-J001 打开正常、Plotly 可交互；同源隔离验证（iframe 内脚本尝试访问 parent.localStorage 必须抛 SecurityError） |
| T3 | 划选捕获模块：bridge 脚本内 mouseup → postMessage；parent 接收后弹悬浮按钮；记录 {text, section, path}；长度截断；章节提取 | 文本/表格数字可选；空白点击不误触发；超长自动截断并提示；章节标题非空率 >80%（抽样 10 个区域） |
| T4 | AI 抽屉：上下文填充、流式对话、"清空上下文"；切换报告自动隔离会话 | 填充格式与 F8 一致；不串报告；会话隔离有单测 |
| T6 | 加载态 + 大文件降级 | 骨架屏正常；>10MB 提示下载；超时 10s 降级 |

## F10. 边界

- 只读联动：AI 不可修改报告产物（写权限不存在）；
- 消毒默认开启，宁可图表降级为静态图，不可脚本逃逸；
- 若示例 run 的 HTML 含非平台生成内容（如用户上传），一律按不可信处理，消毒不可关闭。

═══════════════════════════════════════
# 第二部分：报告交付物自动化测试（Test）
═══════════════════════════════════════

## S1. 测试样本

`/data/omichub/Flow_report/X101SC26098749-Z01-J001/`，结构：
```
data/ | delivery_manifest.json | delivery_manifest.md5
project_summary.json(7.4M) | report.paths.json | *_report.en.pdf
```
**原则：delivery_manifest.json 是唯一权威清单，不硬编码文件名。**

## S2. 测试项

### A. 清单完整性
1. manifest 可解析、字段结构合法；
2. manifest 声明文件逐条存在（先推断路径基准：探索阶段打印 manifest 确认路径是相对 run 根目录还是 data/ 子目录）；
3. 反向查孤儿文件（磁盘有、清单无）→ WARN 列出；
4. 按 delivery_manifest.md5 全量重算比对，不一致列出（路径/期望/实际）。

### B. 索引与报告文件
5. report.paths.json 引用路径全部存在；
6. PDF 可打开：页数≥1、可提取文本（pdfplumber）；
7. HTML（由 report.paths.json 发现）：可离线打开（自包含 PASS，外链 WARN）；无头浏览器加载无 JS 报错、Plotly 渲染非空、中文字体无乱码。无外网/无 Playwright 时 SKIP 并注明。

### C. 数据一致性（project_summary.json ↔ 交付文件）
8. 可解析、模块分区齐全（先打印结构再定断言）；
9. 抽样 5 个关键统计量，到对应 csv/tsv 复核一致（浮点容忍 1e-6）；
10. JSON 引用文件路径全部有效。

### D. 可复现性
11. 有重跑入口则重放比对 MD5；无则 SKIP。

### E. 新功能专项（第一部分交付后执行）
12. T1 端点安全：未登录 401 / 路径穿越（`../etc/passwd`）403 / 白名单外（`.exe`）400 / 越权 report_id 403；
13. 消毒有效性：构造含 `<script>alert(1)</script>` 与 `<img src=x onerror=alert(1)>` 的假报告 HTML 请求 T1 端点，响应体必须不含 `alert(1)` 与 `onerror`；同时构造合法 Plotly 内联脚本，响应必须保留（确保不误杀）；
14. 上下文模板：模拟划选 {text,section,path} → 生成的填充串字段完整、格式与 F8 模板一致；
15. **E2E 链路测试（Playwright 或无头浏览器）**：打开 ReportViewer → 划选一段文本 → 确认悬浮按钮出现 → 点击按钮 → 确认 AI 抽屉打开且输入框已填充 → 发送消息 → 确认流式回复到达。任一步失败即 FAIL。

### F. 测试自证（防假绿）
16. 复制样本到 /tmp 后：
    (a) 删一个交付文件 → A-2/A-4 必 FAIL；
    (b) 篡改 summary 中一个统计值 → C-9 必 FAIL；
    (c) 构造路径穿越请求 → E-12 必 403。
    三项都检出才算测试有效。

## S3. 交付要求

- 脚本 `tests/test_flow_report.py`（pytest，存量产物测试 A–D + F） + `tests/test_report_viewer.py`（pytest，新功能测试 E + 集成）；
- 先目录探索再断言；探索输出另存 `exploration_log.json`；
- 批量入口：扫描 /data/omichub/Flow_report/ 全部 run；
- 输出：控制台摘要 + `test_report.md`（按 run 分节 + 功能测试节，逐项状态表）；
- 环境 Python 3.12（pytest/pdfplumber）；Playwright 为可选依赖，未安装时 B-7/E-15 SKIP；
- 测试产物写 /tmp/flow_report_test/，只读源文件；FAIL 只报告不修复，疑似流程 bug 另附 `issues_found.md`（现象/复现/建议修复位置）。

## S4. 执行顺序（已调整）

```
T1（受控端点）
  → T5（后端消毒层，先做安全，再开前端）
    → T2（iframe 加载已消毒内容）
      → T3（划选捕获 bridge）
        → T4（AI 抽屉）
          → T6（加载态/降级）
            → 测试 A–D（存量产物）
              → 测试 E–F（新功能 + 自证）
```

**纪律：T5 未上线前，T2 不允许对外暴露。**

═══════════════════════════════════════
# 编码 Agent 排错速查表
═══════════════════════════════════════

- **iframe 加载空白**：检查 Blob URL 是否正确创建；检查后端端点返回 Content-Type 是否为 text/html；检查 console 是否有 CSP 拦截；
- **getSelection() 为空**：确认 iframe 已完全加载（load 事件后绑定）；确认用户确实选中了文本元素而非空白容器；
- **postMessage 收不到**：parent 监听器必须在 iframe 创建前注册；校验 event.source === iframeRef.current.contentWindow；
- **Plotly 不渲染**：检查消毒层是否误剥离了 Plotly 内联 script；检查 iframe sandbox 是否遗漏 allow-scripts；
- **路径穿越测试失败**：检查是否正确使用 pathlib.Path.resolve() 做真实路径比对，而不是字符串包含判断；
- **Playwright 安装失败**：标记 B-7/E-15 SKIP，其余测试继续运行，不中断流水线。
