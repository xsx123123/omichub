# OmicHub 数据存储排查与迁移规划报告

> 生成时间: 2026-07-06
> 排查对象: 当前运行环境（单机 Docker Compose 部署）
> 核心结论: 平台数据并非全部在 /data/omichub。文件/对象类数据已落在 /data/omichub，但用户信息与元数据存储在 PostgreSQL，位于 Docker 命名卷中，不在 /data/omichub。要做快速迁移，需同时搬运三类资产。

> 📌 **2026-07-06 更新（omichub_data 收口）**：五类核心数据（`_pgdata` / `_redis` / `jbrowse` / `knowledge` / `welcome`）已从 `/data/omichub/` 根下进一步集中迁移到 `/data/omichub/omichub_data/` 子目录。下文中出现的 `/data/omichub/_pgdata`、`/data/omichub/_redis`、`/data/omichub/jbrowse`、`/data/omichub/welcome`、`/data/omichub/knowledge` 等路径，实际位置均改为 `/data/omichub/omichub_data/<同名子目录>`。`data_root` 仍为 `/data/omichub`，`rsync /data/omichub` 可整体带走。详见 README「数据目录结构」与 `docs/knowledge/data-directory-guide.md`。

---

## 一、环境总览

| 组件 | 实现 | 容器 | 数据落点 |
|------|------|------|----------|
| 关系数据库 | PostgreSQL 14 | omichub-db | Docker 命名卷 docker_pg_data（非 /data/omichub）|
| 缓存/队列 | Redis 7 | omichub-cache | Docker 命名卷 docker_redis_data（非 /data/omichub）|
| Web API | FastAPI | omichub-web | 代码 bind-mount 仓库 + /data/omichub |
| 异步计算 | Celery Worker | omichub-worker | bind-mount /data/omichub + 宿主 conda |
| 定时器 | Celery Beat | omichub-beat | 无持久数据（写 /tmp）|
| 监控 | Flower | omichub-flower | 无持久数据 |
| 反向代理 | Nginx | omichub-nginx | 只读挂载 /data/omichub + 前端 dist |

磁盘: /dev/mapper/ubuntu--vg-ubuntu--lv 共 1.8T，已用 1.1T（65%），剩余 591G。

---

## 二、数据库（PostgreSQL）—— 用户信息与全部元数据在这里

### 位置
- ✅ 已改为 bind mount: /data/omichub/_pgdata（2026-07-06 完成迁移）
- 容器内挂载点: /var/lib/postgresql/data
- 属主: postgres (uid 70, postgres:14-alpine)，宿主用户无权直接读（正常）
- 数据目录实际大小: 70 MB（含 WAL/系统目录），数据库内容: 12 MB
- 旧 Docker 命名卷 docker_pg_data 仍保留作备份，验证无误后可删除

### 连接信息（来自 .env）
```
POSTGRES_HOST=db   POSTGRES_PORT=5432
POSTGRES_USER=omichub   POSTGRES_DB=omichub
DATABASE_URL=postgresql+asyncpg://omichub:omichub_dev_password@db:5432/omichub
```
> ⚠️ 密码为开发默认值 omichub_dev_password，生产前必须更换。

### 规模
- 数据库大小: 12 MB（当前数据量极小，主要是表结构）
- Alembic 迁移版本: 7ec7e0105527
- 共 28 张表，实际数据: users 2 行、site_settings 1 行，其余业务表（tasks/samples/file_records/reports/workspaces/ai_conversations 等）均为 0 行

### 表清单（按域分组）
| 域 | 表 |
|----|----|
| 用户/账户 | users |
| 目录/配额 | user_directories、workspaces |
| 文件/上传 | file_records、upload_sessions |
| 任务/样本 | tasks、samples |
| 报告 | reports、report_files |
| AI 对话 | ai_conversations、ai_messages、ai_provider_configs |
| 聊天 | chat_sessions、chat_messages、chat_assistants |
| 沙箱 | sandbox_sessions、agent_templates、skills |
| MCP | mcp_servers、mcp_logs |
| 通知 | notifications |
| 积分系统 | cookie_accounts、cookie_transactions、cookie_ledger、cookie_consumption_logs、cookie_pricing |
| 站点配置 | site_settings |
| 迁移版本 | alembic_version |

> 结论: 用户账号、配额、任务记录、文件元数据、报告索引、AI 会话历史等结构化数据全部在 PostgreSQL。这是迁移必须带走的第一类资产。

---

## 三、缓存与队列（Redis）

### 位置
- ✅ 已改为 bind mount: /data/omichub/_redis（2026-07-06 完成迁移）
- 容器内挂载点: /data
- 属主: redis (uid 999)，数据文件 dump.rdb
- 实际大小: 76 KB
- 旧 Docker 命名卷 docker_redis_data 仍保留作备份，验证无误后可删除

### 内容
| DB | 用途 | Key 数 | 是否持久 |
|----|------|--------|----------|
| db0 | 应用缓存 | 1 | 短 TTL，可丢 |
| db1 | Celery Broker（任务队列）| 3 | 迁移时清空即可 |
| db2 | Celery Result Backend（任务结果）| 286 | 有 TTL，可丢 |

> 结论: Redis 数据可丢失、可重建，迁移时无需搬运，新环境启动即自愈。

---

## 四、文件存储 /data/omichub —— 对象/文件类数据在这里 ✅

### 总览
- 总大小: 6.2 GB
- 由 .env 的 STORAGE_PATH=/data/omichub 定义，src/omichub/core/config.py:64 默认值同为 /data/omichub
- web / worker / nginx 三个容器均挂载此目录（web、worker 可写，nginx 只读）

### 子目录构成与分类

| 子目录 | 大小 | 内容 | 数据性质 | 迁移/存储建议 |
|--------|------|------|----------|---------------|
| jbrowse/ref/ | 3.2G | GRCh38.p14.genome.fa 人类参考基因组 | 共享参考数据（只读、可重新下载）| 适合对象存储 / NAS 共享卷，无需备份 |
| jbrowse/tracks/ | 3.0G | gencode.v50.basic.annotation.gff3 基因注释 | 共享参考数据（只读、可重新下载）| 同上 |
| bin/ | 38M | EBIDownload 二进制 + yaml | 工具二进制 | 随镜像/脚本分发，可不入对象存储 |
| refdata/enrichments/ | 248K | 富集分析前后端代码（docker-compose 子项目）| 第三方子应用代码 | 归入仓库或独立仓库 |
| users/&lt;uuid&gt;/ | 180K | 每用户独立目录，含 raw_data/ 等 | 用户私有数据（当前几乎为空）| 必须随迁移，适合 NAS / 对象存储 |
| uploads/ | 28K | 上传会话临时目录（含 ebi_download 残留）| 临时/中转数据 | 可清理，迁移非必需 |
| welcome/ | 12K | welcome.yaml + welcome_state.yaml 欢迎词与轮询游标 | 平台配置 | 随迁移（小）|
| knowledge/ | 4K | 知识库（空）| 平台数据 | 随迁移 |
| .tmp/ | 4K | 临时目录（空）| 临时 | 可清理 |

### 路径约定（源码确认）
- 用户私有根: /data/omichub/users/&lt;user_id&gt;/（jbrowse_service.py:6 做归属校验）
- BAM 轨道目录: /data/omichub/users/&lt;user_id&gt;/bam/（jbrowse_config.py:63）
- 上传目录: /data/omichub/users/&lt;user_id&gt;/uploads/（jbrowse_config.py:77）
- 富集结果: /data/omichub/users/&lt;user_id&gt;/enrichment/&lt;task_id&gt;/（enrichment_service.py:5）
- 沙箱: sandbox_data_dir = /data/omichub（config.py:143）
- conda envs: SNAKEMAKE_CONDA_PREFIX=/data/omichub/.conda_envs（worker 运行时生成）
- 富集子应用: 通过 enrichment_data_mount 宿主→容器同路径挂载（enrichment_runner.py:69）
- nginx 轨道流读: /data/omichub 经 /tracks/ 路径供 JBrowse2 流式读取（只读）

> 结论: /data/omichub 已经是平台文件类数据的统一收口目录，设计正确，后续产出会持续落到此（主要在 users/&lt;uuid&gt;/ 下）。

---

## 五、应用配置（仓库内 data/）

### 位置
- 物理路径: /home/zj/zj_code_libarary/OmicHub/data（仓库内）
- 容器内: /app/data（web 只读 bind-mount）
- 大小: 9.1M

### 内容
ai_providers.yaml、jbrowse_config.yaml、OmicHub.yaml、provider_templates.yaml、AI 示例 json/png 等

### 性质
随代码仓库版本管理，不属于运行时数据，迁移靠 git 即可。

---

## 六、回答你的核心问题

### Q1: 数据库用户信息和平台数据都保存在哪里？

| 数据类型 | 实际位置 | 是否在 /data/omichub |
|----------|----------|----------------------|
| 用户账号/密码/配额 | PostgreSQL → /data/omichub/_pgdata/ | ✅ 是（已迁移）|
| 任务/样本/报告元数据 | PostgreSQL → /data/omichub/_pgdata/ | ✅ 是（已迁移）|
| AI 会话历史 | PostgreSQL → /data/omichub/_pgdata/ | ✅ 是（已迁移）|
| 用户上传/分析结果文件 | /data/omichub/users/&lt;uuid&gt;/ | ✅ 是 |
| 参考基因组/注释 | /data/omichub/jbrowse/ | ✅ 是 |
| 任务队列/缓存 | Redis → /data/omichub/_redis/ | ✅ 是（已迁移）|
| 应用配置 YAML | 仓库 data/ | ❌ 否（随 git）|

✅ 2026-07-06 完成 bind mount 改造后，除应用配置（随 git）外，**所有运行时数据均已收口到 /data/omichub**，迁移时 rsync 此目录即可带走全部数据。

### Q2: 后续平台产生的数据能否都放到 /data/omichub？

可以，现已全部落地：
- 文件类数据：所有用户产出、上传、结果落到 /data/omichub/users/&lt;user_id&gt;/ 下
- 数据库：已 bind mount 到 /data/omichub/_pgdata/，PG 直接写入此目录
- 缓存/队列：已 bind mount 到 /data/omichub/_redis/，Redis 持久化文件在此

---

## 七、NAS 与对象存储划分建议

按数据性质三层划分：

### 第一层：热数据 / 结构化数据 —— 留本地 SSD（IOPS 敏感）
| 数据 | 当前位置 | 建议 |
|------|----------|------|
| PostgreSQL | /data/omichub/_pgdata/ | 留本地 SSD；若上 NAS 必须用块设备（NFS 会丢数据一致性）|
| Redis | /data/omichub/_redis/ | 留本地 SSD，无需 NAS |

### 第二层：温数据 / 用户文件 —— NAS 共享卷（多节点共享读写）
| 数据 | 当前位置 | 建议 |
|------|----------|------|
| users/&lt;uuid&gt;/ | /data/omichub/users/ | 迁到 NAS，多 worker 节点共享读写 |
| uploads/ | /data/omichub/uploads/ | NAS（中转，可配 TTL 清理）|
| welcome/ knowledge/ | /data/omichub/ | NAS（小，随主目录）|
| .conda_envs/ | /data/omichub/.conda_envs | NAS（worker 共享，避免每节点重建）|

### 第三层：冷数据 / 参考数据 —— 对象存储（只读、大文件、可重新下载）
| 数据 | 当前位置 | 大小 | 建议 |
|------|----------|------|------|
| jbrowse/ref/ | /data/omichub/jbrowse/ref/ | 3.2G | 对象存储，首次启动按需拉取到本地缓存 |
| jbrowse/tracks/ | /data/omichub/jbrowse/tracks/ | 3.0G | 同上 |
| bin/ | /data/omichub/bin/ | 38M | 对象存储或随镜像分发 |

> 划分后 /data/omichub 本质变成「NAS 挂载点 + 对象存储本地缓存」的统一入口，应用代码无需改动路径。

---

## 八、快速迁移方案（三要素）

要实现「基于仓库 + /data/omichub 的快速迁移」，需迁移以下资产：

| 序号 | 资产 | 来源 | 大小 | 必需性 |
|------|------|------|------|--------|
| 1 | 代码仓库 | /home/zj/zj_code_libarary/OmicHub | 4.4G | 必需（含配置 data/、alembic 迁移）|
| 2 | 全部运行时数据 | /data/omichub（含 _pgdata + _redis + 用户文件 + 参考）| 6.2G | 必需 |
| 3 | 宿主 conda | /home/zj/miniconda3 + ~/.local/share/mamba | 较大 | 必需（worker 运行 snakemake）|

> ✅ bind mount 改造后，数据库 + Redis + 文件数据全部在 /data/omichub 下，不再需要单独处理 Docker 卷。

### 迁移步骤清单（简化版）

#### Step 1: 停服（源机）
```bash
docker compose -f deploy/docker/docker-compose.yml -f deploy/docker/docker-compose.worker.yml down
```

#### Step 2: 同步全部数据到目标机（一条命令搞定）
```bash
# /data/omichub（含 PG + Redis + 用户文件 + 参考基因组，rsync 增量可断点续传）
sudo rsync -aP --info=progress2 /data/omichub/ <目标机>:/data/omichub/

# 仓库（git clone 更干净，或 rsync）
rsync -aP --exclude '.git' /home/zj/zj_code_libarary/OmicHub/ <目标机>:OmicHub/
```

> 注意：_pgdata 属主为 uid 70、_redis 属主为 uid 999，rsync -a 会保留属主，目标机无需额外修权限。

#### Step 3: 迁移 conda 环境（worker 依赖）
```bash
rsync -aP /home/zj/miniconda3/ <目标机>:/home/zj/miniconda3/
rsync -aP /home/zj/.local/share/mamba/ <目标机>:.local/share/mamba/
```

#### Step 4: 目标机启动
```bash
cd OmicHub
docker network create omichub_net 2>/dev/null
docker compose -f deploy/docker/docker-compose.yml up -d
docker compose -f deploy/docker/docker-compose.worker.yml up -d
```

#### Step 5: 验证
```bash
docker exec omichub-db psql -U omichub -d omichub -c "SELECT count(*) FROM users;"
docker exec omichub-cache redis-cli info keyspace
curl -s http://localhost:8888/api/v1/health
```

---

## 九、✅ 已完成：数据库纳入 /data/omichub（统一数据目录）

> 2026-07-06 已实施。原 Docker 命名卷 pg_data / redis_data 已改为 bind mount，数据已迁移并验证。

### 改动内容

**deploy/docker/docker-compose.yml**：
```yaml
  db:
    volumes:
      # 原: - pg_data:/var/lib/postgresql/data
      - /data/omichub/omichub_data/_pgdata:/var/lib/postgresql/data   # bind mount
  cache:
    volumes:
      # 原: - redis_data:/data
      - /data/omichub/omichub_data/_redis:/data   # bind mount
```
底部 `volumes:` 段（pg_data / redis_data 声明）已删除。

**deploy/docker/docker-compose.prod.yml**：
```yaml
  db:
    volumes:
      - /data/omichub/omichub_data/_pgdata:/var/lib/postgresql/data   # 同步改为 bind mount
```

### 迁移过程（已完成）
1. 停服 → 2. 创建 /data/omichub/_pgdata、_redis → 3. 用临时容器 cp -a 原样拷贝卷数据（保留 uid 70/999 属主）→ 4. 改 compose → 5. 启动 → 6. 验证 users=2 / tables=28 / alembic=7ec7e0105527 / Redis keys 一致

### 验证结果
- PG: 用户 2 行、表 28 张、alembic 版本 7ec7e0105527 ✅
- Redis: db1=3 keys、db2=286 keys ✅
- 全部 7 容器 healthy ✅
- 旧命名卷 docker_pg_data / docker_redis_data 保留作备份，确认稳定后可删：
  `docker volume rm docker_pg_data docker_redis_data`

> 注意：_pgdata 属主为 postgres(uid 70)，宿主普通用户无法直接读，属正常现象；迁移时 rsync -a 会保留属主，目标机启动即用。

---

## 十、风险与注意事项

1. **数据库密码**：当前为开发默认值 omichub_dev_password，迁移到生产前务必在 .env 更换
2. **alembic 版本**：迁移后首次启动会自动 `alembic upgrade head`，确保仓库 alembic 版本 ≥ 数据库版本
3. **PG 大版本**：pg_dump 导出可跨版本恢复；直接拷卷要求源/目标 PG 大版本完全一致（当前 14）
4. **文件权限**：web/worker 以 PUID=1000 运行，rsync 时加 -a 保留属主，否则可能写权限错误
5. **conda 路径硬编码**：worker compose 里 PATH 和挂载点写死 /home/zj/miniconda3，目标机用户名需一致或改配置
6. **jbrowse 参考数据 6.1G**：若目标机可联网，可不下传，改用脚本重新下载（download_jbrowse2.sh）省带宽
7. **uploads/ 残留**：含 .._etc_passwd 异常目录（疑似 EBI download 工具误建），迁移前建议清理

---

## 附录：关键路径速查

| 用途 | 路径 |
|------|------|
| 应用代码 | /home/zj/zj_code_libarary/OmicHub |
| 应用配置 | OmicHub/data/（仓库内，随 git）|
| 环境变量 | OmicHub/.env |
| **数据总根（迁移只需此目录）** | **/data/omichub** |
| 用户数据 | /data/omichub/users/&lt;uuid&gt;/ |
| 参考基因组 | /data/omichub/jbrowse/ref/、tracks/ |
| PostgreSQL 数据 | /data/omichub/_pgdata/（bind mount，uid 70）|
| Redis 数据 | /data/omichub/_redis/（bind mount，uid 999）|
| conda 运行时 | /home/zj/miniconda3、/home/zj/.local/share/mamba |
| 流程代码 | /home/zj/pipeline（worker 只读挂载）|
| compose 编排 | deploy/docker/docker-compose.yml + .worker.yml + .prod.yml |
| 旧 Docker 卷（备份，可删）| docker_pg_data、docker_redis_data |
