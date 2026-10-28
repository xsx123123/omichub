使用 frontend.md，仅优化 OmicHub 当前“AI 助手”页面的对话输入框组件。

本次任务的范围必须严格限制为：

- AI 助手页面；
- AI 助手对话输入框；
- AI 助手输入框内部的附件、引用、联网、终端、工具、深度思考和超频模式操作；
- AI 助手输入框外部的免责声明；
- 与 AI 助手输入框直接相关的局部样式、可访问性和响应式适配。

本次暂时不要修改：

- AI 工作台页面；
- AI 工作台页面布局；
- AI 工作台顶部工具栏；
- AI 工作台模式本身的业务逻辑；
- AI 工作台路由、Store、API 和接口契约；
- 其它非 AI 助手页面；
- 知识库阅读页及 fontend.md §34 冻结内容；
- 平台全局导航和 DefaultLayout，除非当前 AI 助手输入框样式确实直接依赖它们，并且修改不会影响其它页面。

如果当前 AI 助手输入框中存在“工作台模式”按钮：

- 只移除它在 AI 助手输入框工具栏中的展示；
- 不删除工作台模式相关的 Store 字段、props、emit、事件处理、路由参数或 API；
- 不修改 AI 工作台页面；
- 不新增或重构 AI 工作台顶部入口；
- 如果暂时无法确认该按钮是否属于 AI 助手页面，不要猜测，先读取父页面和相关组件后再处理；
- 最终报告中明确说明该按钮是否仅从输入框中移除，以及原有业务逻辑是否保留。

## 一、开始前必须读取的内容

不要凭空生成一个独立示例组件。先读取真实项目代码并确认：

1. AI 助手页面的实际路径。
2. AI 助手输入框组件的实际路径，组件可能命名为 `AIComposer.vue`，但不要假设文件名。
3. AI 助手输入框的父组件。
4. 当前使用的是 Naive UI 还是 Arco Design Vue。
5. 当前输入框的 `props`、`emit`、`v-model` 和插槽契约。
6. 当前发送消息、停止生成、附件上传、文件引用、联网、终端、工具、深度思考和超频模式的状态来源。
7. 当前使用的 AI Store、composable、WebSocket、SSE 或流式输出逻辑。
8. `frontend/src/styles/tokens.css`。
9. `frontend/src/styles/global.css`。
10. `frontend/src/App.vue` 中的组件主题配置。
11. 当前项目中已有的 `focus-ring`、按钮、Tooltip、Popover、Dropdown 和输入框样式。
12. 是否已有公共 AI 输入框组件可以直接复用。

先给出简短的现状分析，至少说明：

- 需要修改的真实文件；
- 当前输入框的 DOM 结构；
- 当前免责声明所在位置；
- 当前“工作台模式”按钮的归属和业务来源；
- 当前发送和停止生成逻辑；
- 当前需要保留的 props、emit、Store 和 composable；
- 预计存在的 Naive UI 样式覆盖风险。

分析完成后直接实施修改，不要只输出设计建议。

## 二、设计目标

当前 AI 助手输入框存在以下问题：

- 默认状态蓝色边框和外发光过重；
- 输入框内部存在横向分割线；
- 免责声明放在输入框内部；
- 多个工具按钮同时使用高强调底色；
- “工作台模式”混在输入框工具栏中；
- 空内容时发送按钮仍显示蓝色高亮；
- 图标按钮缺少明确的 Tooltip 或可访问名称；
- 输入框、工具栏和免责声明的层级不清晰。

改造目标：

- 输入框使用安静、稳定的中性卡片表面；
- 默认状态不显示蓝色边框或蓝色外发光；
- 只有输入真正获得焦点时显示平台统一焦点状态；
- 工具按钮默认低强调，选中后才显示品牌色；
- 工作台模式不作为 AI 助手输入框内的操作；
- 免责声明位于输入框外部；
- 发送、停止、附件和流式生成逻辑保持不变；
- 不改变 AI 工作台页面。

## 三、结构与免责声明

输入框内部建议采用以下结构，具体实现以现有组件契约为准：

```text
AI 助手输入区外层
├── Composer 容器
│   ├── 附件/引用文件预览区，可选
│   ├── 多行文本输入区
│   └── 工具栏
│       ├── 左侧上下文操作
│       ├── 中间工具和消息级模式
│       └── 右侧清空、停止或发送
└── 免责声明
```

建议结构：

```vue
<div class="ai-composer-shell">
  <div class="ai-composer">
    <div
      v-if="attachments.length"
      class="ai-composer__attachments"
    >
      <!-- 保留现有附件预览和移除逻辑 -->
    </div>

    <NInput
      v-model:value="draft"
      type="textarea"
      :autosize="{ minRows: 3, maxRows: 8 }"
      <!-- 保留当前已有的 props 和事件 -->
    />

    <div class="ai-composer__toolbar">
      <!-- 附件、引用、联网、终端、工具、消息级模式 -->
      <!-- 清空、停止生成或发送 -->
    </div>
  </div>

  <p class="ai-composer__disclaimer">
    星尘由硅基演算，请以你的判断为准。
  </p>
</div>
```

不得为了套用该结构而破坏当前组件已有的：

- `props`；
- `emit`；
- `v-model`；
- 插槽；
- 文件上传逻辑；
- 文件引用逻辑；
- 流式输出逻辑；
- 停止生成逻辑；
- 错误处理逻辑。

### 横向分割线

移除 AI 助手 Composer 内部用于区分文本区和工具栏的横向分割线，包括：

- `border-bottom`；
- `border-top`；
- 用于绘制横线的 `::before` 或 `::after`；
- 工具栏顶部或底部的贯穿式分隔线。

只删除输入框内部的装饰性横线，不要删除：

- Composer 外层实体边框；
- 弹窗、菜单和下拉层自身边框；
- 附件条必要的边界；
- 页面其它区域的分隔线；
- AI 工作台页面中的任何分割线。

### 免责声明

将以下文字移出 Composer 容器：

```text
星尘由硅基演算，请以你的判断为准。
```

要求：

```css
.ai-composer__disclaimer {
  margin: 4px 0 0;
  color: var(--neutral-text-3);
  font-size: 12px;
  line-height: 18px;
  text-align: center;
}
```

具体间距优先复用项目已有间距变量。

免责声明必须：

- 位于输入框外部正下方；
- 不参与输入框内部工具栏布局；
- 不使用绝对定位；
- 不覆盖发送按钮或工具栏；
- 窄屏允许自然换行；
- 深色模式下继续使用语义文本变量。

## 四、边框与表面材质

默认状态下 Composer 使用：

```css
background: var(--neutral-card);
border: 1px solid var(--neutral-border);
box-shadow: none;
```

禁止：

- 默认蓝色边框；
- 默认蓝色外发光；
- 默认渐变描边；
- 多层蓝色阴影；
- 通过伪元素绘制额外蓝色外圈；
- 使用浅色主题硬编码白色作为背景；
- 使用 `rgba()` 或 `opacity` 破坏深色模式表面层级。

### 聚焦状态

只有 `textarea` 或 Composer 内部真正获得焦点时才显示焦点状态。

优先复用项目已有的 `.focus-ring`。如果当前项目没有适用规则，使用精确的 `:focus-within`：

```css
.ai-composer:focus-within {
  border-color: var(--arco-primary);
  box-shadow: 0 0 0 2px color-mix(
    in srgb,
    var(--arco-primary) 18%,
    transparent
  );
}
```

要求：

- 不在默认状态显示焦点颜色；
- 不同时给 `NInput` 内部和 Composer 外层绘制两套完整蓝色边框；
- 不使用厚重发光；
- 焦点环符合平台 `2px` 主色、约 `3px` 外偏移的可访问性要求；
- 高对比度模式下边界必须更清晰；
- 减少透明度模式下不使用依赖模糊或透明度的焦点表达。

如果使用 Naive UI：

1. 先检查 `NInput` 和 `NButton` 的真实内部类名；
2. 优先使用组件 API 和应用级主题；
3. 必要时使用组件根 class 加内部类的精确选择器；
4. 不使用全局 `!important` 批量覆盖 `n-*`；
5. 不使用 `.ai-composer > *`、`.ai-composer > div` 等过宽选择器设置 `position`、`z-index`、`display`、`flex` 或 margin；
6. 使用 `:deep()` 时只命中具体内部节点。

## 五、工具栏精简与重排

### 输入框内允许保留的操作

左侧上下文操作：

- 添加附件；
- 引用工作区文件；
- 选择文件或资源。

中间工具和消息级模式：

- 联网；
- 终端；
- 工具；
- 深度思考；
- 超频模式，仅当当前产品明确将其定义为消息级模式时保留。

右侧执行操作：

- 清空输入，仅在有草稿、附件或引用内容时显示；
- 停止生成，仅在流式生成中显示；
- 发送，仅在可发送且未生成时显示。

### 工作台模式处理

“工作台模式”不属于 AI 助手输入框工具栏。

本次只做以下处理：

- 从 AI 助手输入框工具栏中移除其视觉入口；
- 如果父页面已经提供工作台模式入口，不再重复添加；
- 保留已有状态、事件、Store、路由参数和 API；
- 不修改 AI 工作台页面；
- 不修改 AI 工作台顶部工具栏；
- 不修改 AI 工作台布局；
- 不重构工作台模式本身；
- 不删除与工作台模式有关的类型或业务逻辑。

如果移除按钮后发现 AI 助手页面没有任何可访问的工作台模式入口，不要擅自修改 AI 工作台。只在最终报告中说明该情况。

## 六、工具按钮视觉状态

所有非主操作工具按钮默认使用低强调样式：

```css
color: var(--neutral-text-2);
background: transparent;
border-color: transparent;
box-shadow: none;
```

hover 使用轻微中性反馈：

```css
background: var(--neutral-hover);
color: var(--neutral-text-1);
```

selected/active 使用品牌色和浅色背景：

```css
color: var(--arco-primary);
background: var(--arco-primary-light);
border-color: color-mix(
  in srgb,
  var(--arco-primary) 30%,
  transparent
);
```

要求：

- 默认状态不要同时出现多个蓝色实心按钮；
- 联网、终端、工具、深度思考和超频模式默认均为幽灵/文本/弱化按钮；
- 只有实际选中或启用时显示主色；
- 选中态必须同时使用 `aria-pressed`、图标、勾选标记或文字说明表达；
- hover 位移不超过 `2px`；
- 不使用弹跳、持续脉冲或强烈发光；
- `prefers-reduced-motion: reduce` 下取消位移动画。

每个纯图标按钮必须有：

- `NTooltip`；
- 或明确的 `aria-label`；
- 最好同时提供 Tooltip 和 `aria-label`。

Tooltip 文案使用动作语义，例如：

```text
添加附件
引用工作区文件
联网搜索
打开终端
选择工具
开启深度思考
开启超频模式
清空输入
停止生成
发送消息
```

## 七、发送按钮逻辑

必须复用当前项目已有的可发送条件。如果当前没有统一的计算属性，应根据实际业务状态补充：

```ts
const canSend = computed(() => {
  const hasText = draft.value.trim().length > 0
  const hasAttachments = attachments.value.length > 0
  const hasReferences = references.value.length > 0

  return hasText || hasAttachments || hasReferences
})
```

实际字段名称必须以当前组件为准。

### 空内容

当没有文本、附件和引用内容时：

- 发送按钮必须设置 `disabled`；
- 使用禁用色；
- 去除蓝色背景；
- 去除蓝色外发光；
- 不响应点击；
- 保持固定宽高，避免布局跳动；
- 保留 `aria-label="发送消息"`。

### 有内容

有文本、附件或引用内容时：

- 使用项目已有主按钮规范；
- 发送按钮使用 `NButton type="primary"` 或现有等价实现；
- 支持点击发送；
- 支持 Enter 发送；
- 发送中阻止重复发送；
- 不使用路由刷新或整页刷新。

### 生成中

生成中将发送按钮切换为停止按钮：

- 使用现有停止生成事件；
- 显示停止图标和 `aria-label="停止生成"`；
- 不清空已生成内容；
- 停止期间使用 loading 或稳定的处理中状态；
- 停止后恢复输入区可用状态。

## 八、文本输入配置

确保使用：

```vue
<NInput
  v-model:value="draft"
  type="textarea"
  :autosize="{ minRows: 3, maxRows: 8 }"
/>
```

要求：

- 计算后的最小高度不低于 `72px`；
- 最大高度不超过约 `200px`，具体遵循现有设计；
- `Enter` 发送；
- `Shift+Enter` 换行；
- 输入法 composition 期间按 Enter 不得误发送；
- 保留当前 placeholder，除非现有文案明显与 AI 助手场景不符；
- 保留当前字数、附件、引用和错误状态；
- 输入框获取焦点后，焦点环清晰但克制；
- 生成中是否允许继续编辑必须遵循当前业务逻辑，不要擅自禁用已有能力。

## 九、响应式要求

至少检查：

- `375px`；
- `640px`；
- `768px`；
- `1024px`；
- `1280×720`；
- `1440px`。

要求：

- 工具栏在窄屏下可以换行；
- 低频操作可以收入更多菜单；
- 发送或停止按钮始终可见；
- 纯图标按钮触控区域不小于约 `40px`；
- 工具按钮文字不得裁切；
- 附件文件名支持省略和 Tooltip；
- 免责声明允许自然换行；
- Composer 不产生页面级横向滚动；
- 不通过固定宽度、负 margin 或绝对定位强行修复窄屏布局；
- 移动端软键盘弹出时不遮挡输入框和发送按钮；
- 不使用会裁剪内容的固定 `100vh`。

## 十、必须验证的状态

至少验证：

1. 空内容；
2. 有文本；
3. 只有附件；
4. 有文本和附件；
5. 有引用文件；
6. 联网关闭；
7. 联网开启；
8. 终端关闭；
9. 终端开启；
10. 工具未选中；
11. 工具已选中；
12. 深度思考关闭；
13. 深度思考开启；
14. 超频模式关闭；
15. 超频模式开启；
16. 正在发送；
17. 正在生成；
18. 停止生成；
19. 发送失败；
20. WebSocket/SSE 连接中；
21. WebSocket/SSE 断开；
22. 正在重连；
23. 浅色模式；
24. 深色模式；
25. `prefers-reduced-motion: reduce`；
26. `prefers-reduced-transparency: reduce`；
27. 高对比度模式；
28. 键盘 Tab；
29. Enter；
30. Shift+Enter；
31. Escape；
32. 输入法组合状态。

## 十一、明确禁止修改的范围

本次任务中不得修改：

- AI 工作台页面；
- AI 工作台顶部操作组；
- AI 工作台的布局和样式；
- 工作台模式的业务实现；
- DefaultLayout；
- 平台全局导航；
- 知识库阅读页；
- 与 AI 助手输入框无关的页面和组件；
- 后端 API；
- WebSocket/SSE 协议；
- 其它页面的全局主题语义。

如果必须修改 `global.css`、`tokens.css` 或 `App.vue` 才能完成，请先确认现有语义变量是否已经可以满足需求。只有在确实缺少平台级令牌时，才允许新增最小范围的全局变量，并同时补齐明暗主题和更新 fontend.md。

## 十二、代码质量要求

- 使用 Vue 3 `<script setup lang="ts">`；
- 保留当前组件的 props、emit、v-model 和业务事件契约；
- 优先复用现有 Naive UI、Arco Design Vue、`@vicons/*` 和共享 CSS；
- 不新增第三方依赖；
- 不使用硬编码浅色主题颜色；
- 不使用无依据的 `!important`；
- 不通过 `.container > *` 等通配选择器处理定位；
- 不复制 API 请求逻辑；
- 不把用户路径展示为平台存储根目录；
- 不使用 mock 数据；
- 不因为改视觉而删除 loading、error、empty、success 和 stopped 状态；
- 组件样式必须避免影响 AI 工作台和其它页面。

## 十三、验证要求

完成修改后执行：

```bash
cd frontend
npm run type-check
npm run build
git diff --check
```

如果项目存在相关测试，继续运行：

```bash
npm run test
npm run test:e2e
```

如果脚本名称不同，使用仓库中现有的测试命令。

同时完成以下检查：

1. 使用 Playwright 检查 AI 助手空输入状态。
2. 检查 AI 助手有文本时的发送状态。
3. 检查 AI 助手生成中的停止状态。
4. 检查免责声明已经位于 Composer 外部。
5. 检查 Composer 内部没有非必要横向分割线。
6. 检查默认状态没有蓝色外发光。
7. 检查聚焦状态只有一套克制的 focus-ring。
8. 检查工作台模式没有出现在 AI 助手 Composer 中。
9. 检查 AI 工作台页面没有产生任何修改或视觉回归。
10. 检查所有图标按钮都有 Tooltip 或 `aria-label`。
11. 检查 `375px` 下没有按钮重叠、文字裁切或页面级横向滚动。
12. 检查浅色、深色、减少动态、减少透明度和高对比度。
13. 在 `frontend/dist/assets` 中定位 AI 助手实际路由 CSS chunk。
14. grep 关键选择器，确认修改已经进入构建产物。
15. 最终报告：
    - 修改文件；
    - 未修改且明确保持不变的 AI 工作台文件；
    - 保留的业务逻辑；
    - 新增或调整的状态；
    - 执行的验证命令；
    - 截图位置；
    - 未完成的验证；
    - 剩余风险。

不要只输出一个脱离仓库上下文的示例组件。必须基于当前项目真实代码实施，并保证 AI 助手现有发送、附件、引用、流式输出和停止逻辑继续工作。
