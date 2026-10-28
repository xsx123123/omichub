# CygnusX MCP 发布与回滚操作

状态：操作模板，尚未用于生产发布。2026-10-19 MCP验收工作树包含未提交改动及其它并行改动；不能从当前工作树直接构建或发布。当前MCP验收使用的隔离Postgres/Redis已关闭，生产部署状态未验证。

## 发布前冻结

1. 在专用分支整理MCP变更，确认`git status`仅含本次范围，并记录提交SHA、`git diff --binary`补丁SHA-256、依赖锁文件SHA-256及配置版本。禁止把未审阅的其它工作树改动带入发布。
2. 执行`uv sync --frozen`、MCP完整测试、平台MCP双表面测试、相关Ruff/mypy和前端构建；保存命令、退出码、失败/跳过项。至少重采集in-process、STDIO、Streamable HTTP、SSE tools/list并校验name/schema/description一致。
3. 若变更需要Alembic迁移，先确认单head、正向迁移、备份恢复和兼容窗口；数据库迁移与应用镜像的前后兼容性须有独立验证。下载身份迁移失败记录`dwnexec04`属于其它工作树内容，不能随MCP发布夹带。
4. 按`deploy/image-mapping.yaml`构建并验证所需镜像，tag包含Git短SHA且不使用`latest`；记录镜像digest、SBOM/依赖锁、运行配置引用及回滚镜像digest。MCP HTTP Token、平台API Key等secret由部署secret管理注入，不进入镜像、日志或证据包。
5. 备份并记录生产MCP preset/Agent绑定状态、管理员启停状态和相关运行配置；发布前确认旧`ensmbl`、`go-server`的ID、transport与用户绑定，不在本次发布中改名、删除或批量解绑。

## 灰度与验收

先部署到隔离/预发布实例，确认loopback/入口代理策略、HTTP Token独立性、平台Key权限、provider固定HTTPS host和调用预算。执行认证失败、无权工具拒绝、确认门拒绝、只读业务正向样例及各传输协议验收。监控HTTP错误率、provider超时、MCP初始化/工具枚举失败、审计request ID关联和输出预算异常。逐步增加流量；任一权限越界、secret泄漏或工具schema非预期变化立即停止扩量。

生产部署必须使用经审阅的提交和镜像digest，先应用已批准且向前兼容的迁移，再滚动应用服务。发布后复核健康检查、MCP initialize/tools/list、预设有效工具数、管理员关闭状态未被覆盖、Agent裁剪与审计事件；provider live检查仅做低频只读样例，不压力测试公共服务。没有完成该步骤前，状态保持“未部署/未验证”。

## 回滚

1. 触发条件包括权限拒绝失效、确认门绕过、secret/用户数据泄漏、schema或路由意外变化、持续provider错误或健康检查失败。停止扩量并保留request ID、镜像digest和脱敏日志。
2. 将应用与外部MCP桥接镜像回滚到记录的上一组digest；两侧schema必须兼容。若新旧版本不兼容，先撤回流量并恢复桥接与平台API的成对版本，禁止只回滚一端继续接流量。
3. 恢复发布前备份的preset版本、Agent绑定和配置引用，保持secret值由secret管理系统提供，不复制到命令行历史或报告。确认手动禁用项没有被预设同步打开。
4. 数据库仅在迁移负责人完成备份恢复演练并确认没有新版本写入后回退。优先使用向前兼容的应用回滚；禁止直接运行未经演练的`downgrade`。若迁移不可逆，执行已审阅的向前修复迁移并保持服务关闭，直到数据校验通过。
5. 回滚后重复健康检查、四传输协议握手/枚举、只读业务调用、权限负测与审计关联；保存回滚提交SHA、镜像digest、配置版本、数据库revision及验证结果。确认全部通过后才恢复流量。

## 当前限制

本说明没有生产镜像digest、生产数据库revision、secret引用、发布窗口或回滚演练结果，因为本轮没有执行生产发布。它提供发布门禁和恢复步骤，不代表发布已获准或已完成。实际发布前须由部署负责人填入目标环境、已批准提交、镜像digest、配置版本、迁移revision及备份/恢复记录。
