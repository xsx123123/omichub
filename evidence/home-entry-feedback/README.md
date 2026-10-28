# 首页入口、卡片反馈与关于页英文

- 首页 CTA：`start=new` / `start=plan`，同一原生寻宝鼠新会话 API；后者仅预填研究方案引导草稿。
- 浏览器使用真实 HomeView、TreasureMouseView/Workbench、FlowsView 与 AboutView，Vue/React 展示树不替换。API 为明确桩数据（包含一条旧会话）；未调用真实模型、数据库或科研执行。
- 隔离预览用 hash 路由与临时导航替代平台登录壳；主平台路由/菜单文件未修改。Vite dev 不支持直接导入 public 内 Island，因此浏览器为该资源返回磁盘上实际构建的 JS，模拟生产静态托管。
- browser-result.json / browser.log：两个 CTA 共创建 2 个新会话，旧消息读取次数为 0；输入聚焦、方案草稿、后退、分析中心流程列表正常。四类卡片 hover、生态链接键盘焦点、减少动态、手机无横向溢出及关于页中英落款已检查。
- new-conversation.png / plan-conversation.png：两个入口状态截图。
- pillars-hover.png / ecosystem-focus.png / mobile.png：卡片交互与响应式截图。
- about-desktop.png / about-mobile.png：中英落款，宽屏并排、手机换行。
- type-check.log / tests.log：类型检查与 95 文件 697 项测试通过；build.log 记录生产构建。jsdom 存量环境提示不作为真实后端运行证据。
- preview.html / preview.ts / browser-check.cjs：隔离浏览器验证脚本备份，不参与生产构建。

人工视觉验收由用户确认。修改未提交或推送；构建产物由本地 frontend/dist 生成。
