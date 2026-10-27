# Web 与异步队列性能测试

`scripts/web_load_test.py` 对真实 HTTP 服务执行 10 / 20 / 50 / 100 个虚拟用户的
闭环测试，每个用户最多一个在途请求。默认每次请求后等待约 1 秒；
`--think-time 0` 用于持续请求测试。报告区分成功 RPS、错误率、HTTP 状态码、
成功请求 P50/P95/P99、分接口 P95 和压测机事件循环延迟。
API 返回 HTML、非 200 或错误正文均计为失败，不把限流错误算成业务容量。

在 Web 容器内创建本次专属的 100 个普通账号（不使用已有用户或管理员）：

```bash
# prefix 每次唯一；JWT 有效 30 分钟，文件权限 0600。不要把凭证放进 evidence/git。
docker exec -e APP_DEBUG=false cygnusx-web python /app/scripts/provision_web_load_users.py \
  --prefix webperf_unique_run_001 --output /tmp/webperf_unique_run_001.json
docker cp cygnusx-web:/tmp/webperf_unique_run_001.json /tmp/webperf_unique_run_001.json
chmod 600 /tmp/webperf_unique_run_001.json

uv run --frozen python scripts/web_load_test.py \
  --tokens-file /tmp/webperf_unique_run_001.json --duration 60 \
  --output evidence/web-capacity/business-paced.json
uv run --frozen python scripts/web_load_test.py \
  --tokens-file /tmp/webperf_unique_run_001.json --duration 60 --think-time 0 \
  --output evidence/web-capacity/business-saturated.json
```

默认 business 场景轮询个人信息、项目列表、最近任务、会话列表、模块注册表，
经过真实认证/权限/数据库链路；它不生成 LLM 回复、不执行分析任务或创建沙箱。
新账号没有历史数据，结果不能代替大数据量、上传、SSE、登录密码校验测试。
默认门槛为错误率 ≤1%、成功请求 P95 ≤1000ms，失败退出码 1；可用
`--max-error-rate` 和 `--max-p95-ms` 调整。

入口另测 `--base-url http://127.0.0.1:8888`。
现有 Nginx 按来源 IP 限制 10r/s，单压测机的拒绝可能是限流；
`8000` 直连仅说明后端容量，不能声称入口已通过。不要为测数字关闭线上限流。
`--profile public` 测站点设置/内容，`--profile static --path /` 测 SPA HTML；
可重复 `--path` 添加从实际 HTML 提取的静态资源。静态测试不执行浏览器 JS。

完成后删除本次账号并撤销凭证，清理只匹配指定 prefix 且带本次标记的普通账号：

```bash
docker exec -e APP_DEBUG=false cygnusx-web python /app/scripts/provision_web_load_users.py \
  --prefix webperf_unique_run_001 --output /tmp/webperf_unique_run_001.json --cleanup
rm /tmp/webperf_unique_run_001.json
```

队列单独运行（与 Web 容量测试依次执行，减少互相干扰）：

```bash
docker exec -e APP_DEBUG=false cygnusx-web python -m scripts.celery_load_test \
  --output /tmp/celery-capacity.json
docker cp cygnusx-web:/tmp/celery-capacity.json evidence/web-capacity/celery.json
```

该命令使用当前配置的 Redis broker/result backend，启动临时的专用队列与
4 进程 Worker，prefetch=1、每子进程 10 次任务后回收，与现有平台配置口径一致。
每用户连续投递并等待 10 个 10ms 合成任务，记录完成吞吐、发布至执行 P95、
执行 P95、端到端 P95、采样队列深度。结束停止临时 Worker、删除本次队列及结果。
它验证 broker/worker/result 往返能力，不代表生产业务 Worker、HTTP 投递、
数据库事务、重试/故障恢复或生信任务吞吐；并发投递线程的开销也包括在内。

加 `--production-builtin` 可把 Celery 内置的 `celery.accumulate(1)` 空任务投递到
当前 `analysis` 队列，由现有 Worker 执行；先检查 Worker/任务注册，不部署新业务
task，不删除共享队列。该模式只报告端到端延迟，共享队列深度包括已有定时任务；
不能把空任务吞吐当作分析任务吞吐。两种模式均轮询 Redis 结果元数据，
端到端时间包含约 10ms 的轮询粒度。

100 个并发用户与 10000 RPS 是不同指标。闭环压测在服务变慢时会自动降低
到达率，不能证明固定 10000 RPS。该目标应在多机预发布环境用开放到达率负载
分级验证 100 / 500 / 1000 / 2000 / 5000 / 10000 / 12000 RPS，
同时要求无丢弃到达、错误率 <1%、业务 P95 <300ms、P99 <1s、
队列积压可消退；10000 RPS 至少持续 30 分钟，并覆盖实际数据规模。

`tests/performance/k6_web.js` 提供固定到达率验收：每个 iteration 恰好一个真实
业务 GET，门槛还包括 `dropped_iterations == 0`，避免压测机丢弃负载后误报通过。
到达率模型见 [k6 官方说明](https://grafana.com/docs/k6/latest/using-k6/scenarios/executors/constant-arrival-rate/)。

```bash
# 在独立预发布环境逐档提升 RATE；先生成 TTL 足够的专属测试凭证。
# 30 分钟验收应在 provision 时设置 --ttl-minutes 120，并按实际数据量填充账号。
TOKENS_FILE=/private/webperf.json BASE_URL=https://staging.example.invalid \
RATE=10000 DURATION=30m PREALLOCATED_VUS=1000 MAX_VUS=4000 \
k6 run --summary-export=evidence/k6-10000-summary.json tests/performance/k6_web.js
```

多 VU 会复用测试账号；账号数量和真实用户数据规模需与验收口径一致。脚本的
10000 RPS 参数是目标，不是已达到的性能结论。生产入口的 per-IP 限流应使用
多压测来源/预发布专用策略验证，不要在线上伪造 X-Forwarded-For 绕过限流。

隔离 Web 实例可用以下入口，使用真实路由/守卫但跳过迁移、种子同步、Provider 探测和
沙箱预热，只适合容量验证，**不得作为生产入口**：

```bash
docker exec -e APP_DEBUG=false -e DATABASE_POOL_SIZE=4 -e DATABASE_MAX_OVERFLOW=0 \
  -e CYGNUSX_LOG_DIR=/tmp/webperf cygnusx-web python -m scripts.web_capacity_server \
  --port 18101 --stop-after 180 --manifest /tmp/webperf-server.json
```

在另一个终端从私有网络访问容器 IP 的 `18101` 端口进行测试，端口不需要发布到公网。
加 `--legacy-wrappers` 可在该进程内恢复 Audit / CookieRequired 原有包装进行同配置对照；
加 `--profile /tmp/webperf.pstats` 可剖析 CPU。使用 `--stop-after` 有界结束，保证剖析结果
导出；cProfile 会显著拖慢服务，不能把剖析时的 RPS 当作正常容量。
本次同机 1/2/4 进程验证与配置见[第二轮报告](../../ARCHITECTURE_DESIGN/CygnusX_web_capacity_optimization.md)。

`TELEMETRY_ROUTE_CACHE_SIZE=0` / `1024` 可在隔离实例中对照原有/优化后的
静态路由 span 标签解析，`--query-stats /tmp/webperf-sql.json` 在停止时导出
SELECT 计数和标签缓存命中数。保留 `TELEMETRY_ENABLED=true`，以免把关闭监控的
收益算入该优化。第四轮 [1250 RPS 快照](../../ARCHITECTURE_DESIGN/CygnusX_web_telemetry_capacity.md)
仍是同机、空业务数据、30 秒实验，不能替代多机持续容量验收。

生成器校验：

```bash
uv run --frozen pytest tests/performance/test_web_load_test.py -q
```

## BLAST 性能测试

## 50 并发查询

```bash
CYGNUSX_ACCESS_TOKEN=<access-token> \
CYGNUSX_BLAST_DB_ID=<optional-db-uuid> \
uvx locust -f tests/performance/locust_blast.py \
  --host http://localhost:8000 \
  --headless --users 50 --spawn-rate 5 --run-time 10m \
  --html artifacts/blast-locust.html
```

验收：平均 API 响应时间低于 3 秒，失败率为 0，提交的任务均能进入终态。结果缓存开启后，重复查询应直接返回 `completed`。
