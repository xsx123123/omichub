# OmicHub 实验室知识库升级改造方案

> 版本：v1.0 | 日期：2026-07-10
> 目标：在前端实现新建文档、编辑审核机制、编辑者标识、Issue 留言模块

---

## 目录

1. [总体架构](#1-总体架构)
2. [数据库设计](#2-数据库设计)
3. [API 接口设计](#3-api-接口设计)
4. [前端组件改造](#4-前端组件改造)
5. [后端核心逻辑](#5-后端核心逻辑)
6. [存量数据迁移](#6-存量数据迁移)
7. [与文件系统的协作](#7-与文件系统的协作)
8. [实施计划](#8-实施计划)

---

## 1. 总体架构

### 1.1 改造后的架构图

```
+------------------------------------------------------------------+
|                        Frontend (Vue 3)                           |
|  +------------------+  +------------------+  +------------------+ |
|  | DocTree.vue      |  | DocReader.vue    |  | DocEditor.vue    | |
|  |  - 状态角标      |  |  - MdPreview     |  |  - MdEditor      | |
|  |  - 新建按钮      |  |  - 审核状态条    |  |  - 编辑摘要      | |
|  |  - 审核入口      |  |  - DocEditors    |  |  - 提交审核按钮  | |
|  +------------------+  |  - DocIssues     |  +------------------+ |
|                        +------------------+                       |
|  +------------------+  +------------------+  +------------------+ |
|  | DocCreateModal   |  | AuditPendingPanel|  | (现有组件保留)   | |
|  | (新建文档弹窗)   |  | (待审核列表)     |  |                  | |
|  +------------------+  +------------------+  +------------------+ |
+------------------------------------------------------------------+
                              |
                              v
+------------------------------------------------------------------+
|                        Backend (FastAPI)                          |
|  +------------------+  +------------------+  +------------------+ |
|  | docs.py (扩展)   |  | docs_service.py  |  | (新增 service)   | |
|  |  - CRUD 接口     |  |  (重构)          |  | audit_service.py | |
|  |  - 审核接口      |  |  - 双写策略      |  | issue_service.py | |
|  |  - Issue 接口    |  |  - 版本管理      |  +------------------+ |
|  +------------------+  +------------------+                       |
|  | presets.py (MCP) |                                              |
|  |  - 改查数据库    |                                              |
|  +------------------+                                              |
+------------------------------------------------------------------+
                              |
                    +---------+---------+
                    |                   |
                    v                   v
+----------------------------+  +---------------------------+
|  Database (MySQL)          |  | File System               |
|  - kb_documents            |  | docs/knowledge/           |
|  - doc_revisions           |  | - meta.yaml               |
|  - doc_editors             |  | - *.md                    |
|  - kb_issues               |  | - figure/                 |
|  - audit_logs              |  +---------------------------+
+----------------------------+
```

### 1.2 核心设计原则

| 原则 | 说明 |
|------|------|
| **数据库为权威源** | 文档内容优先从 `doc_revisions` 读取，文件系统作为「发布镜像」 |
| **双写策略** | 管理员操作即时同步文件系统；普通用户操作仅入库，审核通过后落盘 |
| **版本隔离** | `current_rev`（已发布）与 `pending_rev`（待审核）严格分离 |
| **用户无感知** | 审核期间用户始终看到 `current_rev` 内容，不暴露中间状态 |
| **向后兼容** | 保留 `/docs-static/` 静态资源服务、`meta.yaml` 配置格式不变 |

---

## 2. 数据库设计

### 2.1 ER 关系图

```
+----------------+       +------------------+       +----------------+
| kb_documents   |<------| doc_revisions    |       | doc_editors    |
| (文档主表)     | 1:N   | (版本历史表)     |       | (编辑者记录)   |
+----------------+       +------------------+       +----------------+
        |
        | 1:N
        v
+----------------+       +------------------+
| kb_issues      |<------| audit_logs       |
| (Issue主表)    | 1:N   | (审核日志表)     |
+----------------+       +------------------+
```

### 2.2 表结构

#### kb_documents — 文档主表

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | PK bigint unsigned | 自增主键 |
| `doc_id` | varchar(64) UNIQUE | URL 标识，如 `"getting-started"` |
| `title` | varchar(255) | 文档标题 |
| `category` | varchar(128) | 分类（单级） |
| `file_path` | varchar(500) | md 文件相对路径 |
| `status` | tinyint NOT NULL DEFAULT 1 | `1=已发布 2=待审核 3=已拒绝` |
| `current_rev` | FK bigint unsigned | 当前生效版本 ID → `doc_revisions.id` |
| `pending_rev` | FK bigint unsigned | 待审核版本 ID → `doc_revisions.id` |
| `created_by` | FK bigint unsigned | 创建者 user_id |
| `created_at` | datetime | 创建时间 |
| `updated_at` | datetime | 更新时间 |

#### doc_revisions — 版本历史表

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | PK bigint unsigned | 自增主键 |
| `document_id` | FK bigint unsigned | 关联 `kb_documents.id` |
| `content` | longtext | Markdown 正文 |
| `edit_summary` | varchar(500) | 编辑摘要/变更说明 |
| `edited_by` | FK bigint unsigned | 编辑者 user_id |
| `status` | tinyint NOT NULL DEFAULT 1 | `1=已发布 2=待审核 3=已拒绝 4=已归档` |
| `created_at` | datetime | 创建时间 |

#### doc_editors — 编辑者记录表

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | PK bigint unsigned | 自增主键 |
| `document_id` | FK bigint unsigned | 关联 `kb_documents.id` |
| `user_id` | FK bigint unsigned | 编辑者 user_id |
| `user_name` | varchar(128) | 编辑者昵称（快照） |
| `edit_count` | int NOT NULL DEFAULT 1 | 编辑次数 |
| `first_edit` | datetime | 首次编辑时间 |
| `last_edit` | datetime | 最后编辑时间 |
| **UNIQUE** | `(document_id, user_id)` | 每个用户对每篇文档一条记录 |

#### kb_issues — Issue 留言表

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | PK bigint unsigned | 自增主键 |
| `document_id` | FK bigint unsigned | 关联 `kb_documents.id` |
| `user_id` | FK bigint unsigned | 创建者 user_id |
| `user_name` | varchar(128) | 创建者昵称（快照） |
| `content` | text | 留言内容 |
| `reply_to` | FK bigint unsigned NULL | 回复哪个 issue（NULL = 顶层留言） |
| `status` | tinyint NOT NULL DEFAULT 0 | `0=正常 1=已解决 2=已关闭` |
| `created_at` | datetime | 创建时间 |
| `updated_at` | datetime | 更新时间 |

#### audit_logs — 审核日志表

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | PK bigint unsigned | 自增主键 |
| `document_id` | FK bigint unsigned | 关联 `kb_documents.id` |
| `revision_id` | FK bigint unsigned | 关联 `doc_revisions.id` |
| `action` | varchar(32) | `submit` / `approve` / `reject` |
| `actor_id` | FK bigint unsigned | 操作者 user_id |
| `actor_name` | varchar(128) | 操作者昵称 |
| `reason` | varchar(500) | 审核意见 / 拒绝原因 |
| `created_at` | datetime | 操作时间 |

### 2.3 建表 SQL（MySQL）

```sql
-- 文档主表
CREATE TABLE kb_documents (
    id              BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    doc_id          VARCHAR(64) NOT NULL UNIQUE COMMENT 'URL标识',
    title           VARCHAR(255) NOT NULL COMMENT '文档标题',
    category        VARCHAR(128) NOT NULL COMMENT '分类',
    file_path       VARCHAR(500) NOT NULL COMMENT 'md文件路径',
    status          TINYINT NOT NULL DEFAULT 1 COMMENT '1已发布 2待审核 3已拒绝',
    current_rev     BIGINT UNSIGNED COMMENT '当前生效版本ID',
    pending_rev     BIGINT UNSIGNED COMMENT '待审核版本ID',
    created_by      BIGINT UNSIGNED COMMENT '创建者',
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_category (category),
    INDEX idx_status (status),
    INDEX idx_created_by (created_by)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='知识库文档主表';

-- 版本历史表
CREATE TABLE doc_revisions (
    id              BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    document_id     BIGINT UNSIGNED NOT NULL COMMENT '关联文档ID',
    content         LONGTEXT NOT NULL COMMENT 'Markdown正文',
    edit_summary    VARCHAR(500) COMMENT '编辑摘要',
    edited_by       BIGINT UNSIGNED NOT NULL COMMENT '编辑者',
    status          TINYINT NOT NULL DEFAULT 1 COMMENT '1已发布 2待审核 3已拒绝 4已归档',
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_document_id (document_id),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='文档版本历史';

-- 编辑者记录表
CREATE TABLE doc_editors (
    id              BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    document_id     BIGINT UNSIGNED NOT NULL COMMENT '关联文档ID',
    user_id         BIGINT UNSIGNED NOT NULL COMMENT '编辑者',
    user_name       VARCHAR(128) NOT NULL COMMENT '编辑者昵称快照',
    edit_count      INT NOT NULL DEFAULT 1 COMMENT '编辑次数',
    first_edit      DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_edit       DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_doc_user (document_id, user_id),
    INDEX idx_document_id (document_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='文档编辑者记录';

-- Issue 留言表
CREATE TABLE kb_issues (
    id              BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    document_id     BIGINT UNSIGNED NOT NULL COMMENT '关联文档ID',
    user_id         BIGINT UNSIGNED NOT NULL COMMENT '创建者',
    user_name       VARCHAR(128) NOT NULL COMMENT '创建者昵称快照',
    content         TEXT NOT NULL COMMENT '留言内容',
    reply_to        BIGINT UNSIGNED COMMENT '回复哪个issue',
    status          TINYINT NOT NULL DEFAULT 0 COMMENT '0正常 1已解决 2已关闭',
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_document_id (document_id),
    INDEX idx_reply_to (reply_to)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='知识库Issue留言';

-- 审核日志表
CREATE TABLE audit_logs (
    id              BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    document_id     BIGINT UNSIGNED NOT NULL COMMENT '关联文档ID',
    revision_id     BIGINT UNSIGNED NOT NULL COMMENT '关联版本ID',
    action          VARCHAR(32) NOT NULL COMMENT 'submit/approve/reject',
    actor_id        BIGINT UNSIGNED NOT NULL COMMENT '操作者',
    actor_name      VARCHAR(128) NOT NULL COMMENT '操作者昵称',
    reason          VARCHAR(500) COMMENT '审核意见/拒绝原因',
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_document_id (document_id),
    INDEX idx_action (action)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='审核日志';
```

---

## 3. API 接口设计

### 3.1 接口总览

| Method | Path | 权限 | 说明 |
|--------|------|------|------|
| `GET` | `/api/v1/docs/knowledge` | 登录用户 | 获取文档目录树（含状态） |
| `GET` | `/api/v1/docs/knowledge/:docId` | 登录用户 | 获取文档当前生效版本 |
| `POST` | `/api/v1/docs/knowledge` | 登录用户 | **新建文档** |
| `PUT` | `/api/v1/docs/knowledge/:docId` | 登录用户 | **提交编辑** |
| `POST` | `/api/v1/docs/knowledge/upload` | 管理员 | 图片上传（保持现有） |
| `GET` | `/api/v1/docs/knowledge/:docId/history` | 登录用户 | 版本历史 |
| `GET` | `/api/v1/docs/knowledge/:docId/editors` | 登录用户 | **编辑者列表** |
| `GET` | `/api/v1/docs/knowledge/audit/pending` | **管理员** | **待审核列表** |
| `POST` | `/api/v1/docs/knowledge/:docId/audit` | **管理员** | **审核通过/拒绝** |
| `GET` | `/api/v1/docs/knowledge/:docId/audit` | 登录用户 | 审核日志 |
| `GET` | `/api/v1/docs/knowledge/:docId/issues` | 登录用户 | **Issue 列表** |
| `POST` | `/api/v1/docs/knowledge/:docId/issues` | 登录用户 | **发表 Issue** |
| `DELETE` | `/api/v1/docs/knowledge/issues/:id` | 本人 | 删除 Issue |

### 3.2 关键接口详情

#### POST /api/v1/docs/knowledge — 新建文档

**Request:**
```json
{
  "docId": "rna-seq-guide",
  "title": "RNA-seq 分析指南",
  "category": "上手指南",
  "content": "# RNA-seq 分析指南\\n\\n## 1. 环境准备...",
  "editSummary": "新建文档"
}
```

**Response:**
```json
{
  "id": 42,
  "docId": "rna-seq-guide",
  "title": "RNA-seq 分析指南",
  "status": "pending",
  "revisionId": 128,
  "message": "文档已提交，等待管理员审核"
}
```

**权限逻辑:**
- **管理员** → `kb_documents.status = 1`（已发布），`doc_revisions.status = 1`，立即写入 `meta.yaml` 和 `.md` 文件
- **普通用户** → `kb_documents.status = 2`（待审核），`doc_revisions.status = 2`，不碰文件系统

#### PUT /api/v1/docs/knowledge/:docId — 提交编辑

**Request:**
```json
{
  "content": "# RNA-seq 分析指南\\n\\n## 1. 环境准备\\n\\n> 更新：新增了质控步骤...",
  "editSummary": "新增质控步骤说明"
}
```

**Response:**
```json
{
  "revisionId": 129,
  "status": "pending",
  "message": "修改已提交，等待管理员审核通过后生效"
}
```

**权限逻辑:**
- **管理员** → 直接更新 `current_rev`，写 `.md` 文件，即时生效
- **普通用户** → 创建新版本记录到 `pending_rev`，等待审核

#### POST /api/v1/docs/knowledge/:docId/audit — 审核操作

**Request:**
```json
{
  "action": "approve",
  "reason": "内容准确，通过"
}
```
or
```json
{
  "action": "reject",
  "reason": "BLAST 参数有误，请核实后重新提交"
}
```

**approve 后端逻辑:**
1. `doc_revisions.status = 1`（已发布）
2. `kb_documents.current_rev = revision.id`
3. `kb_documents.pending_rev = NULL`
4. `kb_documents.status = 1`
5. 将 `revision.content` 原子写入 `.md` 文件
6. 如是新文档，追加到 `meta.yaml`
7. 写 `audit_logs`（`action = approve`）

**reject 后端逻辑:**
1. `doc_revisions.status = 3`（已拒绝）
2. `kb_documents.pending_rev = NULL`
3. `kb_documents.status` 保持原值
4. 不写文件系统
5. 写 `audit_logs`（`action = reject`，带 `reason`）

#### GET /api/v1/docs/knowledge/:docId — 获取文档

**Response:**
```json
{
  "id": 42,
  "docId": "rna-seq-guide",
  "title": "RNA-seq 分析指南",
  "category": "上手指南",
  "status": "published",
  "content": "# RNA-seq 分析指南...",
  "currentRevision": {
    "id": 128,
    "editedBy": "管理员",
    "editSummary": "初始版本",
    "createdAt": "2026-07-10T10:00:00Z"
  },
  "pendingRevision": {
    "id": 129,
    "editedBy": "张三",
    "editSummary": "新增质控步骤说明",
    "createdAt": "2026-07-10T15:30:00Z"
  },
  "editors": [
    { "userName": "管理员", "editCount": 5, "lastEdit": "2026-07-10T10:00:00Z" },
    { "userName": "张三", "editCount": 2, "lastEdit": "2026-07-10T15:30:00Z" }
  ]
}
```

> `pendingRevision` 仅对管理员和提交者本人返回，其他用户看不到此字段。

#### GET/POST /api/v1/docs/knowledge/:docId/issues — Issue 留言

**GET Response:**
```json
[
  {
    "id": 1,
    "userName": "王五",
    "content": "这里的 BLAST 参数是不是应该更新到 v2 版本？",
    "status": 0,
    "createdAt": "2026-07-10T12:00:00Z",
    "replies": [
      {
        "id": 2,
        "userName": "管理员",
        "content": "已更新，感谢反馈！",
        "createdAt": "2026-07-10T13:00:00Z"
      }
    ]
  }
]
```

**POST Request:**
```json
{
  "content": "建议附录添加参考基因组下载链接",
  "replyTo": null
}
```
Reply to 某条留言：
```json
{
  "content": "好的，我补充一下",
  "replyTo": 1
}
```

---

## 4. 前端组件改造

### 4.1 组件清单

| 组件 | 类型 | 说明 |
|------|------|------|
| `KnowledgeView.vue` | 修改 | 主视图：新增新建按钮、审核入口 |
| `DocTree.vue` | 修改 | 目录树：新增状态角标 |
| `DocReader.vue` | 修改 | 阅读器：新增审核状态条、编辑者标识、Issue 模块 |
| `DocEditor.vue` | 修改 | 编辑器：新增编辑摘要、提交审核按钮 |
| `DocCreateModal.vue` | **新增** | 新建文档弹窗 |
| `AuditPendingPanel.vue` | **新增** | 待审核列表面板（管理员） |
| `DocEditors.vue` | **新增** | 编辑者标识组件 |
| `DocIssues.vue` | **新增** | Issue 留言模块 |

### 4.2 各组件改造详情

#### DocCreateModal.vue（新增）

新建文档弹窗，所有人可见：

```
+------------------------------------------+
|  新建文档                          [×]   |
+------------------------------------------+
|  文档ID (docId):  [________________]    |
|  标题:            [________________]    |
|  分类:            [下拉▼ / 新建___]     |
|  编辑摘要:        [________________]    |
|                                          |
|  内容 (MdEditor):                        |
|  +------------------------------------+  |
|  |                                    |  |
|  |                                    |  |
|  +------------------------------------+  |
|                                          |
|  [取消]                      [提交审核]  |
+------------------------------------------+
```

- `docId`：URL 标识，只能包含字母、数字、连字符
- 分类：支持下拉选择已有分类，或输入新建
- 普通用户点击「提交审核」→ 后端 status = 2
- 管理员点击「保存并发布」→ 后端 status = 1

#### AuditPendingPanel.vue（新增，仅管理员）

待审核文档面板，以抽屉（Naive UI `NDrawer`）形式从右侧滑出：

```
+------------------------------------------+
|  待审核文档 (3)                   [×]    |
+------------------------------------------+
|  +------------------------------------+  |
|  | 📄 基因组注释指南                   |  |
|  |    提交者: 张三 | 2小时前            |  |
|  |    变更: "补充了BLAST参数说明"       |  |
|  |    [查看差异] [✅通过] [❌拒绝]     |  |
|  +------------------------------------+  |
|  +------------------------------------+  |
|  | 📄 快速入门                         |  |
|  |    提交者: 李四 | 5小时前            |  |
|  |    [查看差异] [✅通过] [❌拒绝]     |  |
|  +------------------------------------+  |
+------------------------------------------+
```

- 每条显示提交者、时间、编辑摘要
- 支持「查看差异」（可选 v1.1 实现）：对比 `current_rev` 与 `pending_rev` 的 diff
- 「通过」→ 立即生效，写文件系统
- 「拒绝」→ 弹出输入框填写拒绝原因

#### DocEditors.vue（新增）

位于 `DocReader.vue` 底部，文档内容之后：

```
+------------------------------------------+
| 👤 贡献者                                 |
| +--------+ +--------+ +--------+         |
| | 管理员 | | 张三   | | 李四   |  +2    |
| | 12次   | | 5次    | | 2次    |         |
| +--------+ +--------+ +--------+         |
+------------------------------------------+
```

- 横向排列贡献者卡片
- 显示用户名 + 编辑次数
- 超过 3 个折叠为 `+N`
- 按 `last_edit` 倒序排列

#### DocIssues.vue（新增）

位于 `DocReader.vue` 最底部，编辑者标识之下：

```
+------------------------------------------+
| 💬 讨论 (5)                               |
+------------------------------------------+
| +--------------------------------------+ |
| | 👤 王五 · 3小时前                     | |
| | 这里的BLAST参数是不是应该更新？        | |
| | [回复]                                | |
| |  └─ 👤 管理员 · 2小时前               | |
| |      已更新，感谢反馈！                | |
| +--------------------------------------+ |
| +--------------------------------------+ |
| | 👤 赵六 · 1天前                       | |
| | 建议附录添加参考基因组下载链接         | |
| | [回复] [已解决 ✓]                     | |
| +--------------------------------------+ |
|                                          |
| [写一条新留言...                 ] [发送]|
+------------------------------------------+
```

- 顶层留言按时间正序排列
- 支持回复（二级嵌套，不做更深层级）
- 本人可删除自己的留言
- 管理员可将留言标记为「已解决」

#### DocReader.vue — 改造后布局

```
+----------------------------------------------+
|  文档标题                                       |
+----------------------------------------------+
|  ⚠️ 审核状态条（仅 pending 时显示）              |
|  "当前版本正在审核中，您看到的是上一个已发布版本"   |
+----------------------------------------------+
|                                                |
|  MdPreview 正文渲染                             |
|                                                |
+----------------------------------------------+
|  DocEditors（编辑者标识）                        |
+----------------------------------------------+
|  DocIssues（Issue 留言模块）                     |
+----------------------------------------------+
```

#### DocTree.vue — 改造

每个节点右侧显示状态指示器：

| 状态 | 显示 | 可见性 |
|------|------|--------|
| 已发布 | 无标记 | — |
| 审核中（自己提交的） | 🟠 橙色小圆点 | 仅自己 |
| 审核中（他人提交的） | 🟠 橙色小圆点 | 仅管理员 |
| 审核拒绝（自己提交的） | 🔴 红色小圆点 | 仅自己 |

#### DocEditor.vue — 改造

- 保存按钮上方增加「编辑摘要」输入框（可选填）
- 按钮文案：
  - 管理员：「保存并发布」
  - 普通用户：「提交审核」
- 保存成功提示：
  - 管理员：「文档已更新」
  - 普通用户：「修改已提交，等待管理员审核通过后生效」

---

## 5. 后端核心逻辑

### 5.1 文档创建流程

```
用户填写新建表单
      │
      ▼
POST /api/v1/docs/knowledge
      │
      ▼
┌──────────────────────────────────────────┐
│ 1. 校验 doc_id 是否已存在               │
│ 2. 校验 meta.yaml 中是否已注册           │
│ 3. 创建 kb_documents 记录                │
│    • status = isAdmin ? 1 : 2            │
│ 4. 创建 doc_revisions 记录               │
│    • content = 用户提交的 Markdown        │
│ 5. 设置 current_rev / pending_rev         │
│    • 管理员: current_rev = 新版本ID       │
│    • 普通用户: pending_rev = 新版本ID     │
│ 6. 写入 meta.yaml（仅管理员）             │
│ 7. 写入 .md 文件（仅管理员）              │
│ 8. 写 audit_logs（action=submit）         │
│ 9. 记录 doc_editors                      │
└──────────────────────────────────────────┘
```

### 5.2 文档编辑流程

```
用户在编辑器修改内容
      │
      ▼
PUT /api/v1/docs/knowledge/:docId
      │
      ▼
┌──────────────────────────────────────────┐
│ 1. 查找文档，校验存在性                   │
│ 2. 检查编辑权限                          │
│    • 普通用户只能编辑已发布(status=1)文档 │
│    • 不能编辑他人正在审核中的版本          │
│ 3. 创建新的 doc_revisions 记录           │
│    • status = isAdmin ? 1 : 2            │
│ 4. 更新 kb_documents                     │
│    • 管理员: current_rev = 新版本ID       │
│                立即写 .md 文件            │
│    • 普通用户: pending_rev = 新版本ID     │
│                不写文件系统               │
│ 5. UPSERT doc_editors 记录               │
│    • edit_count += 1                      │
│    • last_edit = NOW()                    │
│ 6. 写 audit_logs（action=submit）         │
└──────────────────────────────────────────┘
```

### 5.3 审核流程

```
管理员打开待审核面板
      │
      ▼
GET /api/v1/docs/knowledge/audit/pending
      │
      ▼
返回所有 status=2 的文档列表
      │
      ▼
管理员点击 [通过] 或 [拒绝]
      │
  ┌───┴───┐
  ▼       ▼
通过    拒绝
  │       │
  ▼       ▼
┌──────────────┐    ┌──────────────┐
│ 1. revision  │    │ 1. revision  │
│    status=1  │    │    status=3  │
├──────────────┤    ├──────────────┤
│ 2. document  │    │ 2. document  │
│    current_rev│   │    pending_rev│
│    = rev.id  │    │    = NULL    │
│    pending_rev│   │    status不变 │
│    = NULL    │    │              │
│    status=1  │    │              │
├──────────────┤    ├──────────────┤
│ 3. 原子写入   │    │ 3. 不写文件  │
│    .md 文件  │    │              │
├──────────────┤    ├──────────────┤
│ 4. 更新      │    │ 4. 写日志    │
│    meta.yaml │    │    reject    │
│    (新文档)  │    │    + reason  │
├──────────────┤    └──────────────┘
│ 5. 写日志    │
│    approve   │
└──────────────┘
```

### 5.4 文档读取流程

```
GET /api/v1/docs/knowledge/:docId
      │
      ▼
┌──────────────────────────────────────────┐
│ 1. 从 kb_documents 查找记录              │
│ 2. 权限检查                              │
│    • status=1(已发布) → 所有人可见        │
│    • status=2(待审核) → 仅提交者和        │
│      管理员可见完整信息                   │
│ 3. 读取 current_rev 的 content            │
│    （始终返回已发布版本）                  │
│ 4. 如果是提交者/管理员且 pending 存在     │
│    额外返回 pendingRevision 字段           │
│    用于前端显示"您的修改正在审核中"        │
└──────────────────────────────────────────┘
```

---

## 6. 存量数据迁移

### 6.1 迁移脚本

执行一次性的迁移，将现有 `meta.yaml` + `.md` 文件导入数据库：

```python
import yaml
from pathlib import Path
from datetime import datetime

def migrate_knowledge_base(meta_yaml_path: str, admin_user_id: int, db_session):
    """
    将现有的 knowledge base 从文件系统迁移到数据库
    仅需执行一次
    """
    section_dir = Path(meta_yaml_path).parent

    with open(meta_yaml_path, 'r', encoding='utf-8') as f:
        meta = yaml.safe_load(f)

    migrated = 0
    for item in meta.get('items', []):
        doc_id = item['id']
        title = item['title']
        category = item.get('category', '未分类')
        md_file = item['file']
        file_path = section_dir / md_file

        # 读取 .md 内容
        content = file_path.read_text(encoding='utf-8') if file_path.exists() else ''

        # 1. 创建文档记录
        doc_result = db_session.execute("""
            INSERT INTO kb_documents (doc_id, title, category, file_path, status, created_by, created_at)
            VALUES (%s, %s, %s, %s, 1, %s, NOW())
        """, [doc_id, title, category, str(file_path), admin_user_id])

        document_id = doc_result.lastrowid

        # 2. 创建初始版本
        rev_result = db_session.execute("""
            INSERT INTO doc_revisions (document_id, content, edit_summary, edited_by, status, created_at)
            VALUES (%s, %s, '初始版本（系统迁移）', %s, 1, NOW())
        """, [document_id, content, admin_user_id])

        revision_id = rev_result.lastrowid

        # 3. 关联当前版本
        db_session.execute("""
            UPDATE kb_documents SET current_rev = %s WHERE id = %s
        """, [revision_id, document_id])

        # 4. 记录编辑者
        db_session.execute("""
            INSERT INTO doc_editors (document_id, user_id, user_name, edit_count, first_edit, last_edit)
            VALUES (%s, %s, '管理员', 1, NOW(), NOW())
        """, [document_id, admin_user_id])

        migrated += 1

    db_session.commit()
    print(f"迁移完成：共导入 {migrated} 篇文档")
```

### 6.2 迁移后验证清单

- [ ] 所有 `meta.yaml` 中的文档都在 `kb_documents` 中有记录
- [ ] 每篇文档都有至少一条 `doc_revisions` 记录（初始版本）
- [ ] `kb_documents.current_rev` 已正确关联
- [ ] `doc_editors` 中有一条管理员记录
- [ ] 文件系统中的 `.md` 文件与数据库 `current_rev.content` 内容一致

---

## 7. 与文件系统的协作

### 7.1 双写策略

| 操作 | 管理员 | 普通用户 |
|------|--------|----------|
| 新建文档 | 写数据库 + 写 `meta.yaml` + 写 `.md` | 只写数据库 |
| 编辑文档 | 写数据库 + 写 `.md` | 只写数据库（`pending_rev`） |
| 审核通过 | 写数据库 + 写 `.md` + 更新 `meta.yaml`（新文档） | — |
| 审核拒绝 | 只更新数据库 | — |

### 7.2 读取优先级

| 场景 | 数据来源 |
|------|----------|
| 前端读取文档内容 | 数据库 `doc_revisions`（`current_rev`） |
| 静态图片资源 `/docs-static/` | 文件系统（不变） |
| MCP AI 检索 | 优先数据库，fallback 文件系统 |
| 目录树 | 数据库 `kb_documents` + `category` 聚合 |

### 7.3 向后兼容

- `meta.yaml` 继续维护，作为文件系统的「配置入口」
- `/docs-static/` 静态资源服务不变
- 运行时副本 `/data/omichub/omichub_data/knowledge/` 的 rsync 可继续保留
- 极端情况下数据库不可用，可降级为读取文件系统

---

## 8. 实施计划

### 8.1 实施顺序（推荐）

| 阶段 | 任务 | 涉及文件 | 预估工时 |
|------|------|----------|----------|
| **Phase 1** | 数据库建表 + 迁移脚本 | SQL + Python 脚本 | 0.5 天 |
| **Phase 2** | 后端 Service 层 | `docs_service.py` 重构 + 新增 `audit_service.py` / `issue_service.py` | 1 天 |
| **Phase 3** | 后端 API 层 | `docs.py` 扩展新接口 | 0.5 天 |
| **Phase 4** | 前端基础组件 | `DocCreateModal.vue` + `AuditPendingPanel.vue` | 0.5 天 |
| **Phase 5** | 前端阅读器扩展 | `DocEditors.vue` + `DocIssues.vue` + `DocReader.vue` 改造 | 1 天 |
| **Phase 6** | 前端编辑器 + 目录树 | `DocEditor.vue` + `DocTree.vue` 改造 | 0.5 天 |
| **Phase 7** | 联调测试 + MCP 适配 | `presets.py` 改查数据库 | 0.5 天 |

**总计：约 4.5 天**

### 8.2 Phase 1 详细步骤

```bash
# 1. 在 MySQL 中执行建表 SQL
mysql -u <user> -p <database> < schema.sql

# 2. 运行迁移脚本（管理员执行一次）
python scripts/migrate_knowledge_base.py \
  --meta-yaml docs/knowledge/meta.yaml \
  --admin-user-id 1

# 3. 验证迁移结果
python scripts/verify_migration.py
```

### 8.3 关键检查点

- [ ] **Phase 1 完成**：数据库有数据，文件系统内容一致
- [ ] **Phase 3 完成**：所有新 API 可用，`GET /docs/knowledge/:docId` 返回正确结构
- [ ] **Phase 5 完成**：前端能看到编辑者列表和 Issue 模块
- [ ] **Phase 7 完成**：完整流程走通：新建 → 提交 → 审核通过 → 发布

---

## 附录：状态码定义

| 状态码 | 适用表 | 含义 |
|--------|--------|------|
| 0 | `kb_issues` | 正常 |
| 1 | `kb_documents` / `doc_revisions` | 已发布 |
| 1 | `kb_issues` | 已解决 |
| 2 | `kb_documents` / `doc_revisions` | 待审核 |
| 2 | `kb_issues` | 已关闭 |
| 3 | `kb_documents` / `doc_revisions` | 已拒绝 |
| 4 | `doc_revisions` | 已归档（旧版本） |

---

## 附录：接口变更兼容性

| 现有接口 | 变更 | 兼容性 |
|----------|------|--------|
| `GET /docs/knowledge` | 返回结构新增 `status` 字段 | 前端需适配 |
| `GET /docs/knowledge/:docId` | 返回结构大幅扩展 | 前端需适配 |
| `PUT /docs/knowledge/:docId` | 新增 `editSummary` 参数 | 可选，兼容旧调用 |
| `POST /docs/knowledge/upload` | **不变** | 完全兼容 |
| `meta.yaml` | **格式不变** | 完全兼容 |
| `/docs-static/` | **不变** | 完全兼容 |
