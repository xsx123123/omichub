# Plan: OmicHub 系统发育树构建工具 — 实现架构设计

## 目标
为 OmicHub 生信工具箱设计「系统发育树构建工具」的完整实现方案与架构文档。

## 阶段

### Stage 1 — 需求分析与计算复杂度评估
- 梳理系统发育树构建的完整生物信息学流程
- 评估每一步的计算复杂度，确定哪些在web服务器同步执行、哪些投递Celery
- 确定支持的功能范围（MSA → 距离矩阵 → 树构建 → 可视化）

### Stage 2 — 技术架构设计
- 前端可视化库选型（phylotree.js vs ECharts tree）
- 后端服务架构（同步API vs Celery异步任务）
- 数据流设计（文件上传 → 任务投递 → 结果轮询 → 前端渲染）
- 与现有OmicHub架构的集成点

### Stage 3 — 前端页面设计
- 遵循tools_design.md规范，设计三栏布局
- 参数面板：输入配置、比对工具选择、树构建方法、进化模型、Bootstrap
- 工作区：树形可视化（支持多种布局）
- 辅助面板：树统计信息、节点列表、导出选项

### Stage 4 — 后端与Celery任务设计
- YAML配置（tool_configs/phylogenetic-tree/）
- API端点设计（上传、提交任务、查询状态、获取结果）
- Celery任务链设计（MSA → Tree Building）
- 生物信息学工具封装（mafft, iqtree, fasttree, muscle）

### Stage 5 — 输出完整架构文档
- 汇总为一份详细的implementation guide文档
- 包含具体的文件清单、代码骨架、部署步骤
