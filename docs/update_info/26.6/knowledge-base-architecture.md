# OmicHub 知识库模块 — 架构总览

## 1. 功能简介

知识库是 OmicHub 平台内置的生信文档管理系统，提供以下能力：

- **文档浏览**：左侧树形目录 + 右侧 Markdown 渲染阅读
- **在线编辑**：管理员可直接在浏览器中编辑并保存文档（Markdown）
- **图片上传**：编辑时支持拖拽/粘贴上传图片，自动保存到静态资源目录
- **AI 检索**：通过 MCP (Model Context Protocol) 内置 `search_knowledge` 工具，AI 助手可检索知识库内容
- **静态资源服务**：文档中的图片通过 `/docs-static/` 路径由 FastAPI StaticFiles + Nginx 代理提供

## 2. 系统架构

```
┌──────────────────────────────────────────────────────────┐
│                      Frontend (Vue 3)                     │
│                                                          │
│  KnowledgeView.vue                                       │
│  ├── DocTree.vue        (左侧树形目录，Naive UI NTree)     │
│  ├── DocReader.vue      (阅读模式，md-editor-v3 MdPreview) │
│  └── DocEditor.vue      (编辑模式，md-editor-v3 MdEditor)  │
│                                                          │
│  Types:  types/knowledge.ts                              │
│  Routes: router/index.ts  →  /knowledge, /knowledge/:id  │
└────────────────────────┬─────────────────────────────────┘
                         │  HTTP (Axios)
                         ▼
┌──────────────────────────────────────────────────────────┐
│                   Backend (FastAPI)                       │
│                                                          │
│  API Layer:   api/v1/docs.py                             │
│  ├── GET  /docs/knowledge          → 目录列表             │
│  ├── GET  /docs/knowledge/:docId   → 文档内容             │
│  ├── PUT  /docs/knowledge/:docId   → 保存文档 (Admin)     │
│  └── POST /docs/knowledge/upload   → 上传图片 (Admin)     │
│                                                          │
│  Service:     application/services/docs_service.py       │
│  ├── list_knowledge()      → 读取 meta.yaml              │
│  ├── get_knowledge_doc()   → 读取 .md 文件               │
│  ├── save_knowledge_doc()  → 原子写回 .md 文件            │
│  └── _resolve_doc_path()   → 路径遍历防护                 │
│                                                          │
│  RBAC:        middleware/rbac.py → AdminRequired          │
│  MCP:         infrastructure/mcp/presets.py → knowledge   │
└────────────────────────┬─────────────────────────────────┘
                         │  File I/O
                         ▼
┌──────────────────────────────────────────────────────────┐
│                   Data Layer (docs/)                      │
│                                                          │
│  docs/knowledge/                                         │
│  ├── meta.yaml              (导航配置：标题、分类、文件映射) │
│  ├── getting-started.md     (Markdown 文档)               │
│  ├── atac-seq-guide.md                                    │
│  ├── rna-seq-tips.md                                      │
│  └── figure/                (图片资源目录)                  │
│      ├── 0R3A1502.jpg                                     │
│      ├── 8b9c979c...svg                                   │
│      └── ...                                              │
└──────────────────────────────────────────────────────────┘
```

## 3. 数据流

### 3.1 文档浏览流

```
用户打开 /knowledge
    → KnowledgeView.fetchNav()
        → GET /api/v1/docs/knowledge
            → DocsService.list_knowledge()
                → 读取 docs/knowledge/meta.yaml
                → 返回 { title, items: [{ id, title, category }] }
    → 前端按 category 聚合成 DocTreeNode[] 树
    → 默认选中第一个叶子节点
        → GET /api/v1/docs/knowledge/:docId
            → DocsService.get_knowledge_doc()
                → 读取对应 .md 文件
                → 返回 { id, title, content }
    → DocReader 渲染 Markdown + 目录大纲
```

### 3.2 文档编辑流（管理员）

```
点击「编辑」按钮
    → isEditMode = true
    → 快照当前 content 到 editBuffer
    → 显示 DocEditor（md-editor-v3 MdEditor）

编辑过程中拖拽图片
    → DocEditor.handleUploadImg()
        → POST /api/v1/docs/knowledge/upload
            → AdminRequired 校验
            → 保存到 docs/knowledge/figure/<uuid>.<ext>
            → 返回 { url: "/docs-static/knowledge/figure/..." }
    → MdEditor 自动插入 ![](url)

点击「保存」
    → PUT /api/v1/docs/knowledge/:docId
        → AdminRequired 校验
        → DocsService.save_knowledge_doc()
            → 原子写：先写 .md.tmp，再 replace
    → 刷新文档内容
```

### 3.3 AI 检索流（MCP）

```
AI 助手调用 search_knowledge(query)
    → MCP preset handler: _search_knowledge()
        → 遍历 docs/knowledge/*.md
        → 匹配 query 关键词
        → 返回前 10 条结果（标题 + 摘要 + 路径）
```

## 4. 静态资源服务

### 4.1 FastAPI 挂载

```python
# main.py
docs_static_path = Path("docs")
if docs_static_path.is_dir():
    app.mount("/docs-static", StaticFiles(directory=docs_static_path), name="docs-static")
```

- 所有 `docs/` 目录下的文件可通过 `/docs-static/` 路径访问
- 例如：`docs/knowledge/figure/47.jpg` → `/docs-static/knowledge/figure/47.jpg`

### 4.2 Nginx 代理

**开发环境 (nginx.conf)**：
```nginx
# 必须用 ^~ 前缀匹配，防止正则规则抢占
location ^~ /docs-static/ {
    proxy_pass http://omichub_backend;
}
```

**生产环境 (nginx.prod.conf)**：
```nginx
location /docs-static/ {
    proxy_pass http://omichub_backend;
}
```

## 5. 权限模型

| 操作 | 路径 | 权限要求 |
|------|------|---------|
| 浏览目录 | `GET /docs/knowledge` | 需登录 (JWT) |
| 阅读文档 | `GET /docs/knowledge/:id` | 需登录 (JWT) |
| 保存文档 | `PUT /docs/knowledge/:id` | 需管理员 (`AdminRequired`) |
| 上传图片 | `POST /docs/knowledge/upload` | 需管理员 (`AdminRequired`) |

`AdminRequired` 依赖定义在 `middleware/rbac.py`，实时查询数据库校验用户角色。

## 6. 文件清单

### 前端 (Frontend)

| 文件 | 职责 |
|------|------|
| `frontend/src/types/knowledge.ts` | 类型定义：KnowledgeItem, KnowledgeDoc, DocTreeNode |
| `frontend/src/views/KnowledgeView.vue` | 主视图：布局、路由监听、CRUD 逻辑 |
| `frontend/src/components/knowledge/DocTree.vue` | 树形目录组件（Naive UI NTree） |
| `frontend/src/components/knowledge/DocReader.vue` | 阅读组件（MdPreview + MdCatalog） |
| `frontend/src/components/knowledge/DocEditor.vue` | 编辑组件（MdEditor + 图片上传） |
| `frontend/src/router/index.ts` | 路由配置（fullscreen: true） |
| `frontend/src/layouts/DefaultLayout.vue` | 布局容器（contentStyle 动态切换） |

### 后端 (Backend)

| 文件 | 职责 |
|------|------|
| `src/omichub/api/v1/docs.py` | API 端点定义（4 个知识库接口） |
| `src/omichub/api/v1/router.py` | 路由注册（prefix="/docs"） |
| `src/omichub/application/services/docs_service.py` | 业务逻辑（读写 YAML/Markdown） |
| `src/omichub/middleware/rbac.py` | 权限校验（AdminRequired） |
| `src/omichub/main.py` | 静态资源挂载（/docs-static） |
| `src/omichub/infrastructure/mcp/presets.py` | MCP 知识库检索工具 |

### 数据 (Data)

| 文件 | 职责 |
|------|------|
| `docs/knowledge/meta.yaml` | 导航配置（文档 ID、标题、文件路径、分类） |
| `docs/knowledge/*.md` | Markdown 文档正文 |
| `docs/knowledge/figure/` | 图片资源目录 |

### 部署 (Deploy)

| 文件 | 职责 |
|------|------|
| `deploy/docker/nginx/nginx.conf` | 开发 Nginx 配置（^~ /docs-static/ 代理） |
| `deploy/docker/nginx/nginx.prod.conf` | 生产 Nginx 配置（/docs-static/ 代理） |

## 7. 关键设计决策

### 7.1 文件存储而非数据库

知识库文档直接存储为 `.md` 文件而非写入数据库，优势：
- 文档可通过 Git 版本控制
- 支持离线编辑和批量导入
- 降低数据库负载
- 原子写入（`.tmp` → `replace`）防止文件损坏

### 7.2 路径遍历防护

`DocsService._resolve_doc_path()` 通过 `Path.resolve().relative_to(section_dir)` 确保：
- 只能访问 `meta.yaml` 中已注册的文档
- 防止 `../` 等路径注入攻击
- 写入操作限制在 `docs/knowledge/` 目录内

### 7.3 路由 fullscreen 模式

知识库路由设置 `meta: { fullscreen: true }` 使 DefaultLayout：
- 使用原生滚动条而非虚拟滚动条
- 应用 flex 约束 (`display: flex; flex: 1; min-height: 0`)
- 实现局部滚动（仅文档内容区域滚动，全局布局固定）

### 7.4 图片路径解析

`DocReader.vue` 在渲染时通过正则替换将 Markdown 中的相对路径（`figure/xxx.png`、`./figure/xxx.png`）解析为 `/docs-static/knowledge/figure/xxx.png`，同时处理 `![alt]()` 和 `<img>` 两种语法。
