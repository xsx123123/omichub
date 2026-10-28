# OmicHub 知识库前端组件文档

## 1. 组件概览

知识库前端由以下核心模块组成：

```
KnowledgeView.vue          # 主视图容器（布局、路由、状态管理）
├── DocTree.vue            # 左侧树形目录导航
├── DocReader.vue          # 阅读模式（Markdown 渲染 + 大纲）
└── DocEditor.vue          # 编辑模式（Markdown 编辑器 + 图片上传）
```

**类型定义**: `types/knowledge.ts`

---

## 2. 类型定义

### `types/knowledge.ts`

```typescript
/** 导航列表项（来自 /docs/knowledge） */
export interface KnowledgeItem {
  id: string
  title: string
  category?: string | null  // 可选分类，前端按它聚合成树
}

/** 文档内容（来自 /docs/knowledge/:docId） */
export interface KnowledgeDoc {
  id: string
  title: string
  content: string
}

/** 树形目录节点（前端由 KnowledgeItem 按 category 聚合而成） */
export interface DocTreeNode {
  key: string              // 叶子节点用文档 id；分类节点用 category 名
  label: string
  docId?: string           // 仅叶子节点有：对应文档 id
  isCategory?: boolean     // 分类节点标识
  children?: DocTreeNode[]
}
```

---

## 3. 主视图：KnowledgeView.vue

### 3.1 职责

- 管理文档目录树和当前选中文档的状态
- 处理路由参数变化，自动加载对应文档
- 控制编辑/阅读模式切换
- 实现文档的 CRUD 操作（创建、读取、更新）

### 3.2 状态管理

```typescript
// 目录与文档
const navTitle = ref('实验室知识库')
const navItems = ref<KnowledgeItem[]>([])
const activeDoc = ref<KnowledgeDoc | null>(null)

// 编辑模式
const isEditMode = ref(false)
const editBuffer = ref('')      // 进入编辑模式时的快照
const draftContent = ref('')    // 当前编辑中的内容

// 加载状态
const loadingNav = ref(false)
const loadingDoc = ref(false)
const saving = ref(false)
```

### 3.3 计算属性：documentTree

将扁平的 `KnowledgeItem[]` 按 `category` 聚合成树形结构：

```typescript
const documentTree = computed<DocTreeNode[]>(() => {
  const groups = new Map<string, KnowledgeItem[]>()
  for (const item of navItems.value) {
    const cat = item.category || '未分类'
    if (!groups.has(cat)) groups.set(cat, [])
    groups.get(cat)!.push(item)
  }
  return Array.from(groups.entries()).map(([cat, items]) => ({
    key: `cat:${cat}`,
    label: cat,
    isCategory: true,
    children: items.map((it) => ({
      key: `doc:${it.id}`,
      label: it.title,
      docId: it.id,
    })),
  }))
})
```

**示例转换**

```
输入:
[
  { id: "a", title: "文档A", category: "分类1" },
  { id: "b", title: "文档B", category: "分类1" },
  { id: "c", title: "文档C", category: "分类2" }
]

输出:
[
  {
    key: "cat:分类1",
    label: "分类1",
    isCategory: true,
    children: [
      { key: "doc:a", label: "文档A", docId: "a" },
      { key: "doc:b", label: "文档B", docId: "b" }
    ]
  },
  {
    key: "cat:分类2",
    label: "分类2",
    isCategory: true,
    children: [
      { key: "doc:c", label: "文档C", docId: "c" }
    ]
  }
]
```

### 3.4 核心方法

#### `fetchNav()`

获取知识库目录导航。

```typescript
async function fetchNav() {
  loadingNav.value = true
  try {
    const res = await apiClient.get<{ title: string; items: KnowledgeItem[] }>(
      '/docs/knowledge',
    )
    navTitle.value = res.data.title
    navItems.value = res.data.items
  } catch {
    message.error('获取知识库目录失败')
    navItems.value = []
  } finally {
    loadingNav.value = false
  }
}
```

#### `fetchDoc(docId)`

获取指定文档内容。

```typescript
async function fetchDoc(docId: string) {
  loadingDoc.value = true
  try {
    const res = await apiClient.get<KnowledgeDoc>(`/docs/knowledge/${docId}`)
    activeDoc.value = res.data
  } catch {
    message.error('获取文档内容失败')
    activeDoc.value = null
  } finally {
    loadingDoc.value = false
  }
}
```

#### `selectDoc(docId)`

选中文档（编辑模式下阻止切换）。

```typescript
function selectDoc(docId: string) {
  if (isEditMode.value) {
    message.warning('请先保存或取消当前编辑')
    return
  }
  router.push({ name: 'knowledge-doc', params: { docId } })
}
```

#### `startEdit()` / `cancelEdit()` / `saveDoc()`

编辑模式控制。

```typescript
function startEdit() {
  if (!activeDoc.value) return
  editBuffer.value = activeDoc.value.content
  draftContent.value = activeDoc.value.content
  isEditMode.value = true
}

function cancelEdit() {
  draftContent.value = editBuffer.value
  isEditMode.value = false
}

async function saveDoc() {
  if (!activeDoc.value) return
  if (!authStore.isAdmin) {
    message.error('仅管理员可保存文档')
    return
  }
  saving.value = true
  try {
    await apiClient.put(`/docs/knowledge/${activeDoc.value.id}`, {
      content: draftContent.value,
    })
    isEditMode.value = false
    message.success('保存成功')
    await fetchDoc(activeDoc.value.id)
  } catch (err: unknown) {
    const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
    message.error(detail || '保存失败')
  } finally {
    saving.value = false
  }
}
```

### 3.5 生命周期

#### `onMounted`

```typescript
onMounted(async () => {
  await fetchNav()
  // 进入页面若未指定文档，默认选第一个叶子
  const docId = route.params.docId as string | undefined
  if (!docId && documentTree.value.length > 0) {
    const firstLeaf = documentTree.value[0].children?.[0]
    if (firstLeaf?.docId) {
      router.replace({ name: 'knowledge-doc', params: { docId: firstLeaf.docId } })
    }
  }
})
```

#### `watch(route.params.docId)`

路由参数变化时自动加载文档。

```typescript
watch(
  () => route.params.docId as string | undefined,
  (docId) => {
    if (docId) {
      void fetchDoc(docId)
    }
  },
  { immediate: true },
)
```

### 3.6 布局结构

```vue
<div class="docs-layout page-container">
  <!-- 左侧目录树 (250px 固定宽度) -->
  <div class="docs-sider">
    <NCard>
      <DocTree :tree-data="documentTree" :active-id="activeDoc?.id" @select="selectDoc" />
    </NCard>
  </div>

  <!-- 右侧主体 (flex: 1) -->
  <div class="docs-main">
    <NCard>
      <!-- 顶部栏：标题 + 编辑/保存按钮 -->
      <div class="content-header">...</div>
      
      <!-- 内容区：编辑模式或阅读模式 -->
      <div class="content-body">
        <DocEditor v-if="isEditMode" v-model="draftContent" />
        <DocReader v-else :content="activeDoc.content" />
      </div>
    </NCard>
  </div>
</div>
```

### 3.7 CSS 布局要点

```css
/* 全局容器：flex 横向布局 */
.docs-layout {
  display: flex;
  gap: 20px;
  flex: 1;
  min-height: 0 !important;  /* 关键：允许 flex 子元素收缩 */
  overflow: hidden;          /* 防止全局滚动 */
}

/* 左侧目录：固定宽度 */
.docs-sider {
  width: 250px;
  flex-shrink: 0;
}

/* 右侧主体：弹性填充 */
.docs-main {
  flex: 1;
  min-width: 0;
  min-height: 0;
}

/* 内容区：局部滚动 */
.content-body {
  flex: 1;
  overflow-y: auto;  /* 仅内容区滚动 */
  min-height: 0;
}
```

**关键设计**

- 所有父级容器必须设置 `min-height: 0` 以允许 flex 子元素收缩
- `overflow: hidden` 阻止全局滚动
- `content-body` 使用 `overflow-y: auto` 实现局部滚动

---

## 4. 树形目录：DocTree.vue

### 4.1 职责

- 渲染树形导航（基于 Naive UI 的 `NTree` 组件）
- 支持分类节点展开/折叠
- 点击叶子节点触发文档切换

### 4.2 Props

```typescript
defineProps<{
  treeData: DocTreeNode[]   // 树形数据
  activeId?: string         // 当前选中的文档 ID
}>()
```

### 4.3 Events

```typescript
defineEmits<{
  select: [docId: string]   // 选中叶子节点时触发
}>()
```

### 4.4 核心实现

#### 数据转换

```typescript
function toTreeOption(node: DocTreeNode): TreeOption {
  return {
    key: node.key,
    label: node.label,
    isLeaf: !node.isCategory,
    children: node.children?.map(toTreeOption),
  } as TreeOption
}
```

#### 自定义渲染

```typescript
function renderLabel({ option, selected }: { option: TreeOption; selected: boolean }) {
  const node = option as unknown as DocTreeNode
  return h('span', { class: ['tree-label', selected ? 'tree-label--active' : ''] }, [
    h(NIcon, { size: 15, class: 'tree-icon' }, {
      default: () => h(node.isCategory ? FolderOutline : DocumentTextOutline),
    }),
    node.label,
  ])
}
```

#### 选中处理

```typescript
function handleSelect(keys: string[]) {
  const key = keys[0]
  const node = findNode(props.treeData, key)
  if (node?.docId) {
    emit('select', node.docId)
  }
}
```

**注意**: 只有叶子节点（有 `docId`）才会触发选中事件。

### 4.5 样式

```css
/* 选中状态高亮 */
.tree-label--active {
  color: var(--arco-primary);
  font-weight: 500;
}

/* 图标颜色跟随状态 */
.tree-label--active .tree-icon {
  color: var(--arco-primary);
}
```

---

## 5. 阅读器：DocReader.vue

### 5.1 职责

- 渲染 Markdown 文档（使用 `md-editor-v3` 的 `MdPreview`）
- 显示目录大纲（`MdCatalog`）
- 解析文档中的相对图片路径为后端静态资源 URL

### 5.2 Props

```typescript
defineProps<{
  content: string   // Markdown 正文
}>()
```

### 5.3 图片路径解析

**问题**: 文档中使用相对路径引用图片（如 `figure/xxx.png`），但实际需要访问 `/docs-static/knowledge/figure/xxx.png`。

**解决方案**: 在渲染前通过正则替换解析路径。

```typescript
const STATIC_IMAGE_BASE = '/docs-static/knowledge/'

const resolvedContent = computed(() => {
  let text = props.content || ''

  // 1) Markdown 图片语法: ![alt](figure/xxx.png "title")
  text = text.replace(
    /(!\[([^\]]*)\]\()(\.\/|)(figure\/[^)\s]+)(\s*"[^"]*")?(\))/g,
    (_match, prefix, _alt, _dot, relPath, title, suffix) =>
      `${prefix}${STATIC_IMAGE_BASE}${relPath}${title || ''}${suffix}`,
  )

  // 2) HTML <img> 标签: <img src="./figure/xxx.jpg" alt="...">
  text = text.replace(
    /<img\b([^>]*)\bsrc=["'](\.\/|)(figure\/[^"']+)["']([^>]*)>/gi,
    (_match, before, _dot, relPath, after) => {
      const altMatch =
        (after as string).match(/alt=["']([^"']*)["']/) ||
        (before as string).match(/alt=["']([^"']*)["']/)
      const alt = altMatch ? altMatch[1] : ''
      return `![${alt}](${STATIC_IMAGE_BASE}${relPath})`
    },
  )

  return text
})
```

**支持的语法**

- `![alt](figure/xxx.png)`
- `![alt](./figure/xxx.png)`
- `![alt](figure/xxx.png "title")`
- `<img src="figure/xxx.png" alt="...">`
- `<img src="./figure/xxx.png" alt="...">`

### 5.4 目录大纲

```vue
<div class="reader-layout">
  <!-- 预览区 80% -->
  <div class="reader-preview">
    <MdPreview
      :model-value="resolvedContent"
      :previewTheme="'default'"
      :codeTheme="'github'"
    />
  </div>
  
  <!-- 大纲 20% -->
  <aside class="reader-toc">
    <div class="toc-title">大纲</div>
    <MdCatalog
      :model-value="resolvedContent"
      :editorId="previewId"
      :scrollElement="scrollElement"
    />
  </aside>
</div>
```

**滚动同步**

```typescript
const scrollElement = ref<HTMLElement>(document.documentElement)

onMounted(() => {
  const previewEl = document.getElementById(previewId)
  const scrollParent = previewEl?.closest('.content-body') as HTMLElement | null
  if (scrollParent) scrollElement.value = scrollParent
})
```

`MdCatalog` 会监听 `scrollElement` 的滚动事件，自动高亮当前可视区域的标题。

### 5.5 响应式布局

```css
/* 桌面端：横向布局 */
.reader-layout {
  display: flex;
  gap: 24px;
}
.reader-preview { flex: 0 0 80%; }
.reader-toc { flex: 0 0 20%; position: sticky; top: 16px; }

/* 移动端 (<1024px)：纵向堆叠 */
@media (max-width: 1024px) {
  .reader-layout { flex-direction: column; }
  .reader-preview { flex: 1 1 auto; }
  .reader-toc {
    position: static;
    max-height: 240px;
    overflow-y: auto;
  }
}
```

---

## 6. 编辑器：DocEditor.vue

### 6.1 职责

- 提供 Markdown 编辑界面（使用 `md-editor-v3` 的 `MdEditor`）
- 支持图片拖拽/粘贴上传
- 双向绑定编辑内容

### 6.2 Props & Events

```typescript
defineProps<{
  modelValue: string   // 当前 Markdown 内容
}>()

defineEmits<{
  'update:modelValue': [value: string]
}>()
```

### 6.3 图片上传

```typescript
async function handleUploadImg(files: File[], callback: (urls: string[]) => void) {
  const urls: string[] = new Array(files.length)
  try {
    await Promise.all(
      files.map(async (file, index) => {
        const formData = new FormData()
        formData.append('file', file)
        const res = await apiClient.post<{ url: string }>(
          '/knowledge/upload',
          formData,
          { headers: { 'Content-Type': 'multipart/form-data' } }
        )
        urls[index] = res.data.url
      }),
    )
    callback(urls)  // MdEditor 自动插入 ![](url)
  } catch (err: unknown) {
    const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
    message.error(detail || '图片上传失败')
  }
}
```

**流程**

1. 用户拖拽/粘贴图片到编辑器
2. `MdEditor` 触发 `@on-upload-img` 事件
3. 并发上传所有图片到 `/knowledge/upload`
4. 后端返回 `{ url: "/docs-static/knowledge/figure/..." }`
5. 调用 `callback(urls)`，`MdEditor` 自动插入 `![](url)` 到文档

### 6.4 配置

```vue
<MdEditor
  :model-value="props.modelValue"
  :preview="false"
  :toolbars-exclude="['github', 'save', 'pageFullscreen', 'catalog']"
  :style="{ height: 'calc(100vh - 220px)' }"
  placeholder="在此编写 Markdown 文档…"
  @update:model-value="handleChange"
  @on-upload-img="handleUploadImg"
/>
```

**关键配置**

- `:preview="false"`: 纯编辑模式（不显示实时预览）
- `:toolbars-exclude`: 隐藏不需要的工具栏按钮
- `:style`: 高度自适应（减去顶部导航和工具栏高度）

---

## 7. 路由配置

### `router/index.ts`

```typescript
{
  path: 'knowledge',
  name: 'knowledge',
  component: () => import('@/views/KnowledgeView.vue'),
  meta: { title: '实验室知识库', requiresAuth: true, fullscreen: true }
},
{
  path: 'knowledge/:docId',
  name: 'knowledge-doc',
  component: () => import('@/views/KnowledgeView.vue'),
  meta: { title: '实验室知识库', requiresAuth: true, fullscreen: true }
}
```

**`fullscreen: true` 的作用**

在 `DefaultLayout.vue` 中，`fullscreen` meta 控制以下行为：

```typescript
const contentStyle = computed(() =>
  route.meta.fullscreen
    ? 'padding: 0; display: flex; flex-direction: column; flex: 1; min-height: 0;'
    : 'padding: 24px;'
)

const useNativeScrollbar = computed(() => route.meta.fullscreen === true)
```

- **启用 flex 布局**: 使 `NLayoutContent` 成为 flex 容器，约束子元素高度
- **使用原生滚动条**: 禁用 Naive UI 的虚拟滚动条，避免创建额外的滚动容器
- **移除内边距**: 由 `KnowledgeView` 自行控制 padding

**为什么需要 fullscreen**

如果不设置 `fullscreen: true`，Naive UI 的虚拟滚动条会创建自己的滚动容器，绕过父级的 `overflow: hidden`，导致全局滚动（灰色背景也跟着滚动）。

---

## 8. 布局容器：DefaultLayout.vue

### 8.1 知识库相关的布局逻辑

```typescript
// 根据路由 meta 动态切换内容区样式
const contentStyle = computed(() =>
  route.meta.fullscreen
    ? 'padding: 0; display: flex; flex-direction: column; flex: 1; min-height: 0; background: var(--neutral-bg);'
    : 'padding: 24px; background: var(--neutral-bg);'
)

// fullscreen 模式使用原生滚动条
const useNativeScrollbar = computed(() => route.meta.fullscreen === true)
```

### 8.2 Deep 样式覆盖

```css
/* 强制 Naive UI 内部容器遵循 flex 约束 */
.main-layout :deep(.n-layout-scroll-container) {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden !important;
}

.main-layout :deep(.n-layout-content) {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden !important;
}
```

**目的**: Naive UI 的 `NLayout` 组件内部会创建多层嵌套容器，必须通过 `:deep()` 穿透样式，确保每一层都遵循 flex 约束。

---

## 9. 全局样式：global.css

### 9.1 根元素重置

```css
html, body, #app {
  height: 100vh !important;
  max-height: 100vh !important;
  overflow: hidden !important;
}
```

**作用**: 阻止浏览器默认的全局滚动行为，确保只有指定的内容区域可以滚动。

### 9.2 页面容器

```css
.page-container {
  padding: 24px;
  min-height: 100%;
  background: var(--neutral-bg);
}
```

**注意**: `KnowledgeView` 通过 `padding: 0` 覆盖此默认 padding，改由外层 `NLayoutContent` 提供。

---

## 10. 常见问题与调试

### Q1: 知识库页面出现全局滚动（灰色背景跟着滚动）

**原因**: 路由缺少 `fullscreen: true`，导致 Naive UI 使用虚拟滚动条创建额外滚动容器。

**解决**:

```typescript
// router/index.ts
meta: { title: '实验室知识库', requiresAuth: true, fullscreen: true }
```

### Q2: 文档中的图片无法显示

**检查清单**:

1. 图片路径是否正确：`figure/xxx.png` 或 `./figure/xxx.png`
2. 文件是否存在于 `docs/knowledge/figure/` 目录
3. FastAPI 是否挂载了静态资源：`app.mount("/docs-static", ...)`
4. Nginx 是否配置了代理：`location ^~ /docs-static/ { proxy_pass ...; }`

### Q3: 编辑模式下图片上传失败

**检查清单**:

1. 用户是否为管理员（`authStore.isAdmin`）
2. 文件格式是否在白名单内（`.png`, `.jpg`, `.gif`, `.svg`, `.webp`）
3. 文件大小是否超过 10MB
4. 后端是否有 `docs/knowledge/figure/` 目录的写权限

### Q4: 目录大纲不随滚动高亮

**原因**: `MdCatalog` 的 `scrollElement` 未正确指向实际滚动容器。

**解决**:

```typescript
onMounted(() => {
  const previewEl = document.getElementById(previewId)
  const scrollParent = previewEl?.closest('.content-body') as HTMLElement | null
  if (scrollParent) scrollElement.value = scrollParent
})
```

### Q5: 编辑后取消编辑，内容未还原

**原因**: `editBuffer` 未在进入编辑模式时正确快照。

**检查**:

```typescript
function startEdit() {
  editBuffer.value = activeDoc.value.content  // 必须在此处快照
  draftContent.value = activeDoc.value.content
  isEditMode.value = true
}

function cancelEdit() {
  draftContent.value = editBuffer.value  // 还原快照
  isEditMode.value = false
}
```

---

## 11. 性能优化建议

### 11.1 大文档渲染

对于超长 Markdown 文档（>1000 行），`MdPreview` 可能会有渲染延迟。可考虑：

- 启用虚拟滚动（如果 `md-editor-v3` 支持）
- 分段加载文档内容
- 使用 Web Worker 异步解析 Markdown

### 11.2 图片懒加载

`MdPreview` 默认不启用图片懒加载。对于包含大量图片的文档，可自定义渲染器：

```typescript
<MdPreview
  :model-value="resolvedContent"
  :renderers={{
    image: (node) => h('img', { src: node.url, loading: 'lazy', alt: node.alt })
  }}
/>
```

### 11.3 目录树虚拟滚动

如果知识库包含数百个文档，`DocTree` 可改用虚拟滚动：

```typescript
<NTree
  virtual-scroll
  :data="treeOptions()"
  ...
/>
```

---

## 12. 扩展开发指南

### 12.1 添加新的文档分类

编辑 `docs/knowledge/meta.yaml`：

```yaml
items:
  - id: "new-doc"
    title: "新文档"
    file: "new-doc.md"
    category: "新分类"  # 前端会自动创建分类节点
```

### 12.2 自定义 Markdown 渲染

修改 `DocReader.vue` 的 `MdPreview` 配置：

```typescript
<MdPreview
  :model-value="resolvedContent"
  :previewTheme="'default'"
  :codeTheme="'github'"
  :renderers={customRenderers}
/>
```

### 12.3 添加文档搜索

在 `KnowledgeView.vue` 中添加搜索框，过滤 `navItems`：

```typescript
const searchQuery = ref('')
const filteredItems = computed(() =>
  navItems.value.filter(item =>
    item.title.toLowerCase().includes(searchQuery.value.toLowerCase())
  )
)
```

### 12.4 支持文档版本历史

- 后端：在 `save_knowledge_doc()` 中调用 Git 提交
- 前端：添加版本选择器，通过 API 获取历史版本

---

## 13. 依赖库版本

| 库 | 版本 | 用途 |
|----|------|------|
| `md-editor-v3` | ^4.x | Markdown 编辑器和预览器 |
| `naive-ui` | ^2.x | UI 组件库（NTree, NCard, NButton 等） |
| `@vicons/ionicons5` | ^0.x | 图标库（文件夹、文档图标） |
| `vue-router` | ^4.x | 路由管理 |
| `axios` | ^1.x | HTTP 请求 |

---

## 14. 文件路径速查

```
frontend/src/
├── types/knowledge.ts                    # 类型定义
├── views/KnowledgeView.vue               # 主视图
├── components/knowledge/
│   ├── DocTree.vue                       # 树形目录
│   ├── DocReader.vue                     # 阅读器
│   └── DocEditor.vue                     # 编辑器
├── router/index.ts                       # 路由配置
├── layouts/DefaultLayout.vue             # 布局容器
└── styles/global.css                     # 全局样式

docs/knowledge/
├── meta.yaml                             # 导航配置
├── getting-started.md                    # 文档
├── atac-seq-guide.md
├── rna-seq-tips.md
└── figure/                               # 图片资源
```
