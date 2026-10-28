# 首页 Hero 浅色优化：任务 1 交付证据

实现完成，视觉人工验收待用户确认；未实施任务 2，未部署或提交。

- before-desktop.png：同一 HomeView 修改前样式的隔离预览。
- after-desktop.png / after-mobile.png：当前真实 Vue 组件在 1440px / 390px 下的隔离预览，使用默认站点文案、JIAN 展示名、空工作台 API 桩；不是生产账号截图。
- after-hover.png：次按钮悬停效果。
- browser-check.log：浏览器计算样式、两个按钮 hover 配色。
- contrast.json：WCAG 相对亮度计算，正文 7.15–7.47:1，按钮文字均大于 4.5:1。
- type-check.log / tests.log / build.log：类型检查、94 文件 691 项测试、生产构建，命令退出码均为 0。
- preview.html / preview.ts：临时隔离预览入口的备份，不参与应用构建。

本次仅修改 HomeView 的 Hero 样式和对应前端架构说明。与本轮开始时 HomeView 比较，script/template 完全一致，文案、路由、布局尺寸与其他模块保持原样；上一轮的圆点修复保留。

## 背景动画恢复

按用户反馈恢复首页原有 Canvas 动画；桌面透明度 0.32、手机 0.24，局部滤镜适配浅色底。浏览器已验证相隔 700ms 的 Canvas 帧不同（动画实际运行）、装饰层不拦截点击。最新截图为 after-animation-desktop.png；此前 after-* 截图为首次浅色方案的历史证据。
