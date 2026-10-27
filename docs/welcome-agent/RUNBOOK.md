# 欢迎语运行与回滚手册

## 上线准备

使用同一代码版本的 Web、Worker、Beat 和前端；生产发布遵守仓库原有流程。2026-10-27 已按用户授权重启现有 Web/Worker/Beat 并核验热挂载源码与新前端；没有发布新后端镜像或主动改写既有欢迎池。单 Beat，worker 必须消费 analysis。不得起第二套调度器；不得复制密钥到欢迎语配置。

本次切换记录见 `WELCOME_ACCEPTANCE_REPORT.md` 与 `evidence/welcome-agent/rollout-2026-10-27/`。新私有备份位于 `/home/zj/.local/state/cygnusx/welcome-rollout-20261027T090810/`；原始容器配置含敏感数据，仅在私有目录保存。当前 `general=false`、`auto_publish=true` 是实测状态；首发人工批准尚无证据，不将现状开关当成批准证明。默认模型最近返回 402，先按既有供应商运维流程恢复余额/可用性，再观察 2026-11-01 03:00 上海时间的自然生成及 11-02 00:00 发布；不因欢迎语任务擅自改全局模型路由。

发布前在受控位置备份现行服务配置、DB schema/数据和相关数据卷。含 compose 渲染配置、env 或 provider key 的备份必须只允许运维账号读取，不能提交到仓库。备份至少包括 schema、四张 welcome 表（若存在）、data/CygnusX.yaml、Agent YAML/prompts、部署环境配置；volume 按现有存储备份规范创建快照。先确认恢复可用。

1. 设置 `WELCOME_ENABLED=false`、`WELCOME_GENERAL_ENABLED=false`、`WELCOME_AUTO_PUBLISH=false`。保留旧 YAML 文件，不修改权限，不自动导入。
2. 用现有迁移作业执行 `uv run alembic upgrade head`，确认包含 `welcome_pool01`，再运行 `uv run python scripts/check_schema_drift.py`。entrypoint 的 drift 检查要求先完成迁移。
3. 部署同版本 Web/Worker/Beat/前端；确认 Beat 仅一个，`welcome.generate/reconcile` 已注册且 analysis 有消费者。
4. 设置 `WELCOME_ENABLED=true`。管理员 POST `/api/v1/admin/welcome/generate`，请求如 `{"audience":"admin","target_week":"2026-11-02","revision":1}`；general 同样生成，展示开关仍关闭。revision 与周界必须明确，周一日期；重复同 revision 幂等，补生成传 revision+1。
5. 通知公告管理 → 欢迎语，审查两受众各至少 18 条、四主题、无旧品牌及不实能力；检查 prompt SHA/run/model/QA/token/费用。首发人工批准后，当前周可点审核发布，未来周等到期；开启 `WELCOME_AUTO_PUBLISH=true` 供后续周任务自动 scheduled。尚未批准时应保持 false。
6. 管理员灰度确认 Toast source（仅后台/网络可见，不给普通用户显示）为 agent_pool，并有 shown 回执。`WELCOME_GENERAL_ALLOWLIST='["用户UUID"]'` 可灰度；稳定后再开 general 全量。
7. 观察下一次周日生成和周一发布：确认没有人工执行命令，检查两个受众的 scheduled→active、唯一 active 约束、fallback 比例、池年龄和 claim 延迟。记录真实 wall-clock 时间、代码 SHA、镜像 digest、迁移与 run IDs。

## 设置

Settings / 环境变量是 feature 配置来源：

| 配置 | 默认 |
| --- | --- |
| WELCOME_ENABLED | true |
| WELCOME_GENERAL_ENABLED | false |
| WELCOME_GENERAL_ALLOWLIST | []，UUID 字符串 JSON 数组 |
| WELCOME_TIMEZONE | Asia/Shanghai |
| WELCOME_TARGET_COUNT / WELCOME_MIN_VALID_COUNT | 24 / 18 |
| WELCOME_MAX_RETRIES | 2，差额补生成轮次 |
| WELCOME_TIMEOUT_SECONDS | 180，每轮 |
| WELCOME_MAX_OUTPUT_TOKENS | 4096，每轮；不大于 Agent YAML 上限 |
| WELCOME_GENERATION_HOUR / MINUTE | 3 / 0，周日 feature 时区 |
| WELCOME_PREVIOUS_POOL_AGE_DAYS | 7，上期最多延用一周 |
| WELCOME_RESERVATION_SECONDS | 300 |
| WELCOME_AUTO_PUBLISH | true，首发准备期建议显式 false |

内部 Agent 只能接收公开事实、历史已批准欢迎文案，不得传用户资料。使用现有 provider 管理，不保存新密钥。改变 YAML/prompt 须更新 prompt_version 和文件；每批保留哈希。

## 手工维护与故障

`uv run python scripts/welcome_agent.py generate --week 2026-11-02 --audience admin --revision 2` 直接执行维护任务；生产优先使用管理端/Celery。`uv run python scripts/welcome_agent.py reconcile` 检查发布并投递缺失/过期任务，不在 Web 请求内运行。

- Provider 超时/坏 JSON/质量不达标：查看批次 run.calls/error_code/validation_report。旧 active 不变；限次自动重试已耗尽时，人工修正配置后补新 revision，不手工修改 DB 让旧任务复活。
- Provider HTTP 402：先恢复既有默认供应商余额或由管理员在原模型管理流程调整配置；不要反复触发生成探测。已有 DB 分发继续工作，过龄内容按旧池/静态降级规则处理。
- 供应商不返回用量或中途断流：usage_complete=false，费用仅已知部分估算，不能承诺绝对成本；输出 token、轮次、超时和租约次数均有限制。
- 发布任务丢失：分钟 reconcile 补偿；批次到期且 scheduled 即可原子发布。事务失败先回滚，下次再尝试。
- 单条质量问题：禁用；整批问题：撤回。低于发布门槛的 scheduled 批次会回到 validated，不阻断另一个受众。
- 异常新池：撤回后对一个经验证 retired 批次执行 rollback，带审核说明；静态/旧池降级仍受每日账本约束。过龄旧池不分发。
- Redis 故障：欢迎模块无 Redis 依赖；既有鉴权/限流的处理仍由原模块负责。DB 故障：welcome claim 静默无内容；不能据此宣称 DB 故障时平台鉴权仍正常。

## 回滚

优先将 `WELCOME_ENABLED=false`，保留四表与审计，不需要恢复目录游标。内容问题用管理端 withdraw/rollback，无需 schema 回退。代码版本回滚时旧 YAML 链路属于旧版本行为，不能据此保证新频率契约；推荐保留当前 DB 分发兼容入口，仅关闭 feature。

若确需 schema downgrade，先关闭所有 welcome 任务/请求并导出四表。`uv run alembic downgrade project_lifecycle01` 会删除欢迎内容与审计；仅在确认备份后执行，不得在有其他新迁移的库上盲目回到旧 head。再升级运行 `alembic upgrade head`，重新导入审核过的 DB 数据或生成新 revision，禁止将历史 OmicHub YAML 自动灌池。

## 隔离复验

独立 PostgreSQL（数据库名包含 welcome_test），先跑完整 Alembic head，再设置：

```bash
WELCOME_TEST_DATABASE_URL=postgresql+asyncpg://.../welcome_test \
  uv run pytest tests/unit/test_welcome_agent.py tests/integration/test_welcome_pool.py -q
cd frontend && npx vitest run src/composables/__tests__/welcome-toast.test.ts && npx vue-tsc --noEmit
```

集成测试会 truncate welcome 表，仅允许专用测试库；测试模型流是明确标注的 fixture，真实模型结果另存验收 evidence。无需改锁文件或安装新产品依赖。
