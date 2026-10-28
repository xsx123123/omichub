# 首页卡片高亮的完整布局修正

用户两张截图定位到此前未覆盖的科研工作台与 Agent × Skill × Flow 卡片，不能把此前三组卡片裁图的 4px 像素验证当作完整首页视觉验收。

本轮修正：

- 首页根容器移除 overflow-x:hidden，避免工作台阴影沿内容左缘被切成直边。
- 工作台移除 0.35 黑色重阴影及专用 ::after，机制/Evidence 移除按图标色变化的高亮伪元素，统一复用 global.css 的 hover/selected。
- 共享竖条从贴边改为内缩 6px，仍为完整 4px 宽、上下各 12px 留白，卡片边框和竖条之间有明确间隔。
- 工作台点击/聚焦内部区域时标记当前分组；机制/Evidence 原生按钮支持选择。原链接/按钮的业务动作保持原样。
- 主体各组箭头复用 card-state-arrow；机制连接箭头保持在卡片间隙，该组使用 overflow:visible 避免箭头被剪掉。

验证基于**正式生产构建的 App + DefaultLayout + 原路由**，通过本地 vite preview 5200 托管 frontend/dist，没有替换页面布局或组件。认证与 API 为明确的浏览器测试桩，展示合成项目、任务与报告；非真实账号/数据运行验收。首次 AI 助手提示通过既有“已读”偏好关闭，不遮挡截图。

browser-result.json：六类卡片（工作台/快捷入口/机制/Evidence/支柱/生态）的 hover/selected 渐变、边框、阴影、竖条及箭头配色逐项一致；hover 无竖条；首页 overflow 为 visible；选中工作台竖条实图有连续 4 列完整像素，位于卡片内 x=7..10。1280/820/390px 无横向溢出，减少动态无抬升，浏览器无 pageerror。

workbench-hover-full-page.png / workbench-selected-full-page.png / mechanism-selected-full-page.png 均保留完整平台导航和页面左右留白，能同时观察阴影是否被裁断、竖条与边框之间的距离及其他卡片的一致性。home-1280.png / home-820.png / home-390.png 为响应式截图。

类型检查、95 文件 697 项前端测试、生产构建通过；人工视觉验收仍以用户确认为准。
