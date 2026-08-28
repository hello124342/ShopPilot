## Why

ShopPilot 的初稿把电商内容营销产品、Agno 运行时和 Agent harness 混成了一个范围过大的系统，导致 Agent Team 的使用边界、流程控制、可验证性和 MVP 目标都不清晰。本变更将产品聚焦为面向电商商家的内容运营 harness：围绕市场调研、营销创意生成和投放数据分析建立可运行、可观察、可评估、可回放的闭环。

## What Changes

- 将产品主线从“多个 Agent 堆叠的内容营销平台”调整为“电商内容运营 Agent harness”，并明确商品、Campaign、素材、指标和优化实验为核心业务对象。
- 固定 Agent、Team、Workflow 和 Tool 的注册能力，取消主 Agent 动态创建任意子 Agent 的设计。
- 将市场调研定义为固定成员的 Research Team；策略、文案、视觉 brief、视频脚本、平台适配和优化主要使用单 Agent；固定顺序、并行、审批和恢复由 Workflow/代码控制。
- 增加结构化的 ResearchPackage、CampaignBrief、CreativePackage、PlatformPayload、ComplianceReport、PerformanceReport 和 OptimizationBrief 产物契约。
- 增加人工审批、受保护发布工具、事实/平台规则校验、运行 trace、replay、评估和故障注入能力。
- 将 MVP 收敛为一次新品广告创意运营任务，使用可复现的研究 fixture 和 mock 发布/指标，暂不覆盖真实平台发布、视频模型、广告预算自动调节及其他电商运营域。

## Capabilities

### New Capabilities

- `ecommerce-operations-harness`: 定义电商内容运营场景、固定 Agent/Team/Workflow 编排、结构化产物、审批与副作用控制、可观察性、回放和评估契约。

### Modified Capabilities

- None. 当前仓库没有既有 `openspec/specs/` 能力规范；本变更建立第一份能力契约。

## Impact

- 新增 Agno SDK/AgentOS 运行层与业务层 harness 边界；实现阶段会影响 Agent、Team、Workflow、Tool、API 和运行记录设计。
- MVP 可先使用 Python、Pydantic、SQLite、本地 fixture 与 pytest/eval CLI；PostgreSQL、Redis、消息队列、向量库、真实平台连接器和多模态生成服务延后。
- 原有初稿中的动态派生 Agent、自建 DAG engine、真实自动发布和全量多媒体范围将不再作为 MVP 要求。
