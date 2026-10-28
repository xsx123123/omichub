> 后续修正：本目录仅覆盖当时三组卡片及共享消费者，未覆盖工作台重阴影和机制卡分色高亮。最新完整 App/DefaultLayout/生产构建验证与 6px 内缩竖条见 ../home-card-highlight-correction/README.md。

# 共享卡片选中样式统一

## 修改清单

- styles/global.css：共享选中背景/边框/竖条/箭头令牌，200ms ease 状态过渡，hover 无竖条且只抬升 1px；减少动态不抬升。4px 竖条使用内部 left:0/top:12px/bottom:12px，不用负偏移。
- HomeView.vue：快捷入口、技术支柱、科研生态三组使用 cygnusx-selectable-card；清理旧阴影/伪元素覆盖。三组独立选择，快捷入口和生态保留原导航动作，支柱原生按钮支持 Enter/Space，箭头复用 card-state-arrow。
- ImageSelector.vue / AgentCard.vue / chat-theme.css / AgentTeamsRoomView.vue / FastqQCView.vue / DashboardView.vue：删除重复状态表面/边框，复用全局规则。AgentCapabilitiesView / ModelNavBar 等原有 shared class 自动继承，无需重复改写。
- AgentCard.vue：将外部属性/class 传给真实 button，修正 Popover 根组件造成的高亮类未落到按钮问题。
- CygnusX_frontend.md：同步选中协议、颜色、交互与复用清单。

## 验证

browser-result.json：真实 HomeView、ImageSelector、AgentCard 和实际模型选择器 CSS；隔离预览用桩 API、拦截跳转以检查离开首页前的选中状态。未改生产路由或导航行为。

三组任意第一张卡：选中浅色渐变、四边 1px #c7d2fe、蓝箭头 #4f6ef7、内部 4px #6366f1 状态线一致。marker-pixels.json 从三张实际 Chromium 截图采样，竖条均完整占据连续 4 列像素（x=1..4），没有被裁断。

hover 背景 #f8faff / translateY(-1px) / 状态线 opacity 0；focus 单独存在时无选中竖条。测试覆盖支柱键盘选择、旧选项取消、按下态、已有共享组件、减少动态、390px 无横向溢出与深色可读表面。

类型检查、95 文件 697 项前端测试通过；build.log 记录生产构建。截图与预览均为隔离数据，人工视觉验收由用户确认。
