# Change: Build Agent Capability, Asset, and Observability Platform

## Why

ShopPilot 已具备可运行的电商运营工作流，但 Skill、Tool、MCP、外部证据、文件资产和 Agent 调用链仍停留在 Demo 级实现。继续增加 Agent 或页面会放大权限、审计、数据血缘和故障定位风险，因此需要先建设统一的 Agent 平台基础能力。

本变更坚持 Agno-first：Agent、Team、Workflow、Skills、Tools、MCP、Media Storage 和运行事件优先采用 Agno 当前锁定版本提供的原生能力。ShopPilot 只补充业务治理、领域契约、资产目录、事件映射和 Harness，不实现第二套 Agent Runtime。

## What Changes

- 建立版本化 Agent/Skill/Tool/MCP 能力目录和集中授权策略。
- 为 Research Team 接入只读搜索、浏览器/网页抽取和标准化证据链。
- 将研究协作明确为“并发采集 -> 证据复核 -> 研究包合成”，并使用 Agno Team/Workflow 原语表达。
- 建立 Artifact 与 Asset 分离的资产模型、存储、血缘、版本、审批和预览能力。
- 将 Agno Agent/Team/Workflow/Tool/Model 事件映射到 ShopPilot 的层级 Trace。
- 增加能力权限、MCP 故障、提示词注入、资产完整性和无副作用 Replay 测试。
- 增加运行图、工具调用、证据引用、资产和成本/时延的最小观察界面。

## Agno-First Guardrail

每项基础能力实施前必须完成当前锁定 Agno 版本的 API 能力审计。存在满足需求的原生能力时必须复用；只有在原生能力无法覆盖 ShopPilot 的业务契约、权限或持久化要求时才允许增加薄适配层。任何自研运行时能力都必须在设计记录中说明缺口、替代方案和升级影响。

优先评估并复用：

- `Agent.skills`、`Agent.tools`、Team 的 skills/tools 与 Toolkits；
- Agno MCP 客户端和 `MCPTools`；
- Agent、Team、Workflow 的事件流、成员事件和运行标识；
- Agno model/tool metrics；
- `MediaStorage`、`AsyncMediaStorage` 和 `store_media`；
- Agno session、storage、memory 与 AgentOS 可用的认证/中间件能力。

## Capabilities

### New Capabilities

- `agent-capability-governance`: 管理 Agent、Skill、Tool、MCP、凭据引用、权限与运行策略。
- `external-research-evidence`: 提供可审计的外部搜索、网页抽取、证据规范化和引用链。
- `managed-digital-assets`: 管理文档、图片和后续视频资产的存储、版本、血缘与生命周期。
- `agent-runtime-observability`: 提供从 Campaign 到模型和工具调用的端到端 Trace、指标与 Replay 关联。

### Modified Capabilities

- `local-production-runtime`: 后续实施时补充能力配置、资产持久化和可观测性服务，但本变更不直接修改主规格。

## Impact

- Affected runtime: `shopilot/runtime`, `shopilot/agents`, `shopilot/teams`, `shopilot/workflows`。
- Affected platform: `shopilot/tools`, 新增 capability/evidence/assets/observability 模块。
- Affected API/UI: 能力状态、证据、资产、Trace graph 和运行指标接口与页面。
- Affected storage: 需要资产 blob/media storage、元数据目录和 Trace 索引。
- External dependencies: 至少一个搜索/浏览器 MCP 或原生 Tool provider；初期只允许管理员配置。

## Out of Scope

- 用户动态安装任意 Skill、Tool 或 MCP Server。
- 自研通用 DAG、Agent 调度器或动态 Agent spawning。
- 真实广告平台开户、投放、支付和自动发布。
- 首阶段的视频生成、转码和大规模 CDN。
- 将外部网页内容直接当作可信指令。

## Success Criteria

- 所有正式 Agent/Team 由 Agno 原语构造，Mock 仅用于测试、CI、Replay 和故障注入。
- 未授权 Agent 无法调用 Tool/MCP，密钥不进入提示词、Trace、Artifact 或浏览器端。
- 研究结论可追溯到来源、抓取时间、内容哈希和 Tool call。
- 文件资产具有稳定 ID、哈希、不可变版本、血缘和审批关联。
- UI 能展示 Campaign -> Stage -> Team -> Agent -> Model/Tool/MCP -> Artifact/Asset 的调用树。
- Replay 默认使用记录结果且不访问外部系统、不产生真实副作用。

