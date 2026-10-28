# 平台 GitHub 入口迁移

统一目标：https://github.com/CygnusX-Labs

修改：data/CygnusX.yaml 的 platform.github（关于页顶部/页脚共用），FlowsView.vue 的“GitHub 开源代码”，README.md 中 CygnusX BioOps 平台链接。独立生态组件及分析管线的仓库链接继续按组件提供，未改克隆地址、子模块或历史资料。

验证：实际 SiteContentService 从当前 YAML 读取并返回新目标；浏览器使用该真实服务输出驱动 AboutView / FlowsView，确认 3 个实际锚点 href、target 和 rel（browser-result.json）。隔离预览只替换 API 数据和登录壳，不访问真实 GitHub 或执行科研操作。

类型检查、95 文件 697 项前端测试、10 项站点内容测试、镜像/Agent 配置静态校验通过。build.log 记录生产构建；最终源码和生产产物排查旧平台仓库地址，无命中。
