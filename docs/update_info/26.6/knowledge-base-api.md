# OmicHub 知识库 API 参考

## 基础信息

- **Base URL**: `/api/v1/docs`
- **认证方式**: JWT Bearer Token（通过 `Authorization: Bearer <token>` 头）
- **权限模型**: 
  - 读取接口：需要登录用户
  - 写入接口：需要管理员角色（`AdminRequired`）

---

## 接口列表

### 1. 获取知识库目录

获取知识库的导航列表，包含所有文档的 ID、标题和分类。

**请求**

```
GET /api/v1/docs/knowledge
```

**权限**: 需要登录

**响应**

```json
{
  "title": "实验室知识库",
  "items": [
    {
      "id": "getting-started",
      "title": "快速入门",
      "category": "上手指南"
    },
    {
      "id": "atac-seq-guide",
      "title": "ATAC-seq 实验指南",
      "category": "流程说明"
    },
    {
      "id": "rna-seq-tips",
      "title": "RNA-seq 分析小贴士",
      "category": "流程说明"
    }
  ]
}
```

**字段说明**

| 字段 | 类型 | 说明 |
|------|------|------|
| `title` | string | 知识库标题（来自 `meta.yaml`） |
| `items` | array | 文档列表 |
| `items[].id` | string | 文档唯一标识（对应 `.md` 文件名） |
| `items[].title` | string | 文档标题 |
| `items[].category` | string \| null | 分类名称（前端按此聚合成树形结构） |

**错误响应**

| 状态码 | 说明 |
|--------|------|
| 401 | 未登录或 Token 无效 |
| 404 | `docs/knowledge/meta.yaml` 不存在 |

---

### 2. 获取文档内容

获取指定文档的 Markdown 正文。

**请求**

```
GET /api/v1/docs/knowledge/{doc_id}
```

**权限**: 需要登录

**路径参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| `doc_id` | string | 文档 ID（必须在 `meta.yaml` 中注册） |

**响应**

```json
{
  "id": "getting-started",
  "title": "快速入门",
  "content": "# 快速入门\n\n欢迎使用 OmicHub 平台..."
}
```

**字段说明**

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | string | 文档 ID |
| `title` | string | 文档标题 |
| `content` | string | Markdown 格式的文档正文 |

**错误响应**

| 状态码 | 说明 |
|--------|------|
| 401 | 未登录或 Token 无效 |
| 404 | 文档不存在、未注册或文件路径非法 |

**安全说明**

- 服务端通过 `_resolve_doc_path()` 进行路径遍历防护
- 只允许访问 `meta.yaml` 中已注册的文档
- 解析后的路径必须在 `docs/knowledge/` 目录内

---

### 3. 保存文档内容

更新指定文档的 Markdown 正文，直接写入磁盘文件。

**请求**

```
PUT /api/v1/docs/knowledge/{doc_id}
Content-Type: application/json
```

**权限**: 需要管理员（`AdminRequired`）

**路径参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| `doc_id` | string | 文档 ID |

**请求体**

```json
{
  "content": "# 更新后的文档内容\n\n..."
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `content` | string | 是 | 新的 Markdown 正文（不能为空） |

**响应**

```json
{
  "id": "getting-started",
  "title": "快速入门",
  "message": "保存成功"
}
```

**错误响应**

| 状态码 | 说明 |
|--------|------|
| 400 | 正文为空 |
| 401 | 未登录或 Token 无效 |
| 403 | 用户不是管理员 |
| 404 | 文档不存在或路径非法 |

**实现细节**

- 使用原子写入：先写入 `.md.tmp` 临时文件，再调用 `Path.replace()` 替换原文件
- 防止写入过程中断导致文件损坏
- 写入后立即返回，无需额外刷新

---

### 4. 上传图片

上传知识库文档配图，保存到 `docs/knowledge/figure/` 目录。

**请求**

```
POST /api/v1/docs/knowledge/upload
Content-Type: multipart/form-data
```

**权限**: 需要管理员（`AdminRequired`）

**请求体**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `file` | File | 是 | 图片文件 |

**支持的文件格式**

- `.png`
- `.jpg` / `.jpeg`
- `.gif`
- `.svg`
- `.webp`

**文件大小限制**: 10 MB

**响应**

```json
{
  "url": "/docs-static/knowledge/figure/a1b2c3d4e5f6.png",
  "filename": "a1b2c3d4e5f6.png"
}
```

**字段说明**

| 字段 | 类型 | 说明 |
|------|------|------|
| `url` | string | 图片的可访问 URL（相对路径） |
| `filename` | string | 保存后的文件名（UUID 格式） |

**错误响应**

| 状态码 | 说明 |
|--------|------|
| 400 | 未提供文件名、格式不支持或文件过大 |
| 401 | 未登录或 Token 无效 |
| 403 | 用户不是管理员 |

**实现细节**

- 文件名使用 `uuid.uuid4().hex` 生成，避免重名和特殊字符
- 目录不存在时自动创建（`mkdir(parents=True, exist_ok=True)`）
- 返回的 URL 可直接在 Markdown 中引用：`![alt](url)`

---

## 静态资源访问

知识库图片通过 FastAPI StaticFiles 挂载提供访问：

**URL 格式**

```
/docs-static/knowledge/figure/{filename}
```

**示例**

```
GET /docs-static/knowledge/figure/a1b2c3d4e5f6.png
```

**Nginx 配置**

```nginx
location ^~ /docs-static/ {
    proxy_pass http://omichub_backend;
}
```

**注意**: 必须使用 `^~` 前缀匹配，防止 Nginx 的正则规则（如 `\.(jpg|png)$`）抢占请求导致 404。

---

## MCP 工具：search_knowledge

知识库内容可通过 MCP (Model Context Protocol) 被 AI 助手检索。

**工具定义**

```json
{
  "name": "search_knowledge",
  "description": "检索 OmicHub 知识库文档",
  "inputSchema": {
    "type": "object",
    "properties": {
      "query": {
        "type": "string",
        "description": "搜索关键词"
      }
    },
    "required": ["query"]
  }
}
```

**调用示例**

```json
{
  "tool": "search_knowledge",
  "arguments": {
    "query": "ATAC-seq"
  }
}
```

**响应**

```json
{
  "results": [
    {
      "title": "ATAC-seq 实验指南",
      "path": "docs/knowledge/atac-seq-guide.md",
      "snippet": "ATAC-seq (Assay for Transposase-Accessible Chromatin...)..."
    }
  ],
  "total": 1
}
```

**实现细节**

- 遍历 `docs/knowledge/*.md` 文件
- 使用简单的字符串匹配（`query in text.lower()`）
- 返回前 10 条结果
- 摘要截取匹配位置前后的文本片段

---

## 数据模型

### meta.yaml 格式

```yaml
title: "实验室知识库"
items:
  - id: "getting-started"
    title: "快速入门"
    file: "getting-started.md"
    category: "上手指南"
  
  - id: "atac-seq-guide"
    title: "ATAC-seq 实验指南"
    file: "atac-seq-guide.md"
    category: "流程说明"
```

**字段说明**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `title` | string | 是 | 知识库标题 |
| `items` | array | 是 | 文档列表 |
| `items[].id` | string | 是 | 文档唯一标识（用于 URL 和 API 调用） |
| `items[].title` | string | 是 | 文档显示标题 |
| `items[].file` | string | 是 | 对应的 Markdown 文件名（相对于 `docs/knowledge/`） |
| `items[].category` | string | 否 | 分类名称（前端按此聚合成树形目录） |

**安全约束**

- `file` 路径不能包含 `../` 等目录遍历字符
- 解析后的绝对路径必须在 `docs/knowledge/` 目录内
- 只能引用已存在的文件

---

## 错误码汇总

| HTTP 状态码 | 场景 | 说明 |
|-------------|------|------|
| 400 | 请求体校验失败 | 正文为空、文件格式不支持等 |
| 401 | 未认证 | 缺少或无效的 JWT Token |
| 403 | 权限不足 | 非管理员尝试写入操作 |
| 404 | 资源不存在 | 文档 ID 无效、文件不存在或路径非法 |
| 500 | 服务器内部错误 | 文件 I/O 异常等 |

---

## 测试示例

### cURL

**获取目录**

```bash
curl -X GET "http://localhost:8000/api/v1/docs/knowledge" \
  -H "Authorization: Bearer <token>"
```

**获取文档**

```bash
curl -X GET "http://localhost:8000/api/v1/docs/knowledge/getting-started" \
  -H "Authorization: Bearer <token>"
```

**保存文档**

```bash
curl -X PUT "http://localhost:8000/api/v1/docs/knowledge/getting-started" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"content": "# 新内容\n\n更新后的文档..."}'
```

**上传图片**

```bash
curl -X POST "http://localhost:8000/api/v1/docs/knowledge/upload" \
  -H "Authorization: Bearer <token>" \
  -F "file=@/path/to/image.png"
```

### Python (httpx)

```python
import httpx

async with httpx.AsyncClient() as client:
    headers = {"Authorization": f"Bearer {token}"}
    
    # 获取目录
    res = await client.get(
        "http://localhost:8000/api/v1/docs/knowledge",
        headers=headers
    )
    nav = res.json()
    
    # 获取文档
    res = await client.get(
        f"http://localhost:8000/api/v1/docs/knowledge/{doc_id}",
        headers=headers
    )
    doc = res.json()
    
    # 保存文档
    res = await client.put(
        f"http://localhost:8000/api/v1/docs/knowledge/{doc_id}",
        headers=headers,
        json={"content": "# 新内容..."}
    )
    
    # 上传图片
    res = await client.post(
        "http://localhost:8000/api/v1/docs/knowledge/upload",
        headers=headers,
        files={"file": open("image.png", "rb")}
    )
```
