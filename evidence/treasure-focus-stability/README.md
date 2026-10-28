# 寻宝鼠回复连续性与历史侧栏默认折叠

## 排查与修复

源代码中 window focus 直接调用 refreshAccess：中断流、清空消息/会话，再读取最近会话。空消息时 FullPresentation 展示 EmptyState，因此会造成“回复 → 欢迎首页 → 回复”的界面闪现；该路径不是路由跳转。新增回归在旧代码下 7 项中 6 项失败（before-regression.log）。

窗口聚焦现独立做后台能力/项目权限校验，保留当前会话、消息和正在接收的流，不重新读取最近会话/历史。模块读权限、401/403、当前项目授权失效仍清理私有数据；临时网络故障保留回复并提示；迟到的旧会话/旧项目/旧校验结果丢弃。初始预检的重启行为保留。

FullPresentation 的 collapsed 初始值为 true：桌面默认窄轨，移动端默认关闭抽屉。正常回复/标题/权限更新不重置用户手动展开状态。

## 验证

- 新增 9 项聚焦回归：当前会话非最近会话、待定预检、生成中聚焦后的后续增量、结束与标题生成交错、模块撤权、HTTP 401/403、网络错误、旧请求跨会话、项目撤权（部分用例综合验证多个条件）。
- 主前端：类型检查、97 文件 712 项测试、生产构建通过（含本轮开始前已有迎新相关变更；未修改这些文件）。
- 实际构建 React Island 接入：2 文件 16 项 PoC 测试通过，包含侧栏默认折叠和展开/收起。
- 浏览器加载正式 frontend/dist 的 App/DefaultLayout/路由。独立 HTTP fixture 服务分段写出 SSE（前段→后段→结束），在生成中和结束后触发共 3 次 focus，并延迟标题响应，MutationObserver 监测回复 DOM 连续性。
- browser-result.json：emptyFrames=0，session list/message GET 均只读初始 1 次，SSE 1 次且无提前 abort，路径始终 /treasure-mouse。默认折叠、用户展开状态跨回复保留、手机抽屉开关通过。

截图 default-collapsed.png / completed-reply-collapsed.png / mobile-reply.png 使用明确的模拟账号、模拟 API 和合成回复，未调用真实模型、科研后端或用户历史。浏览器是真实 HTTP 分段流测试，不是生产模型运行验收。未修改子仓，变更位于平台 Vue 外壳、父仓 React 展示覆盖层及相关回归/文档。
