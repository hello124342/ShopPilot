# ShopPilot Agent Platform Evolution Roadmap

## Purpose

本路线图记录 ShopPilot 从电商运营 Demo 走向可交付 Agent 产品所需的平台化改造。它是后续会话和实施工作的入口；具体规范与验收场景位于 OpenSpec change `build-agent-capability-asset-observability-platform`。

## Non-negotiable Architecture Rule

ShopPilot 的正式运行时采用 Agno。以下能力必须优先使用锁定 Agno 版本的原生实现：

- Agent、Team、Workflow；
- Skills、Tools、Toolkits、MCPTools；
- Team mode 与异步/并发执行；
- Agent/Team/Workflow 事件与 model/tool metrics；
- session、storage 和 media storage。

ShopPilot 不开发第二套 Agent loop、Team scheduler、通用 DAG 或 MCP 协议。自定义代码只负责电商业务契约、能力治理、权限、证据、资产目录、事件映射、审批和 Harness。

## Current Assessment

| Area | Current state | Delivery gap |
|---|---|---|
| Agent runtime | 已构造 Agno Agent/Team；Workflow 仍由业务代码主导 | 能力未正式绑定，Agno 事件未接入 |
| Research | 有固定 Team 和 Mock fixtures | 无搜索/浏览器/MCP，所谓并行未被执行语义保证 |
| Skills/Tools/MCP | 有少量本地确定性 Tool | 无 registry、权限、生命周期、外部能力和凭据治理 |
| Artifacts | JSONL 结构化结果 | 无真实文件资产、哈希、血缘、预览和下载 |
| Trace | 高层手工 TraceEvent | 无 Team member、model、tool/MCP 层级和完整指标 |
| Replay | 面向确定性结果 | 尚未覆盖外部 Tool recording 和媒体资产 |

## Target Product Model

```text
Campaign Workflow
  -> Research Team
     -> concurrent collectors
     -> evidence review
     -> cited ResearchPackage
  -> Strategy Agent
  -> Creative Agent -> Artifact + Assets
  -> Compliance Agent
  -> Human approval bound to versions
  -> Mock Publish
  -> Analytics Agent
  -> Optimization Agent
```

所有环节共享三个平台平面：

```text
Capability Plane: Agent -> Skill -> Policy -> Tool/MCP
Asset Plane:      Artifact -> AssetReference -> Asset/Lineage
Observe Plane:    Run -> Stage -> Team -> Agent -> Model/Tool -> Output
```

## Phase 0: Agno Capability Audit

目标：用可运行 smoke tests 确认当前锁定版本的真实 API，不根据记忆设计接口。

交付：

- Agno primitive capability matrix；
- Agent/Team/Workflow/Skills/Tools/MCP/Media/events smoke tests；
- 必要适配层清单和 ADR；
- 明确 Research 并发所采用的 Team mode 和异步 API。

退出条件：后续每项能力都有“Agno 原生 / 薄适配 / ShopPilot 领域层”的明确归属。

## Phase 1: Capability Governance

目标：Agent 获得可管理、可授权、可观测的能力，而不是任意挂载工具。

交付：

- Agent/Skill/Tool/MCP registry；
- per-Agent allowlist 和 side-effect policy；
- 服务端 Credential Reference；
- MCP health、timeout、retry、circuit breaker；
- 能力健康 API。

退出条件：越权调用在外部执行前被拒绝，密钥不出现在 prompt、Trace、Artifact 或前端。

## Phase 2: Real Research Capability

目标：完成 ShopPilot 第一个真实外部能力闭环。

建议顺序：

1. Search；
2. Browser/Web extraction；
3. Evidence normalization；
4. Evidence review；
5. Cited ResearchPackage。

Research 使用固定三阶段：并发 Collector、Evidence Reviewer、Synthesis。外部内容一律按不可信数据处理，Reviewer 默认不得自行联网补证据。

退出条件：canonical scenario 的每个关键研究结论都有来源、抓取时间、哈希、Tool call 和 citation ID；证据冲突不会被静默消解。

## Phase 3: Managed Assets

目标：让 Agent 输出从 JSON 字段升级为可管理的业务资产。

首批范围：Markdown、HTML、PDF、PNG/JPEG/WebP。视频生成和转码延后。

交付：

- Asset Catalog 和 Agno MediaStorage 集成；
- SHA-256、MIME、大小、状态和不可变版本；
- Artifact/AssetReference 和 AssetLineage；
- 预览、下载、权限、保留和 quarantine；
- 审批与 Artifact/Asset version 绑定。

退出条件：UI 中看到的每个文件都有真实存储对象、稳定 ID、来源和生成血缘，文件更新会使旧审批失效。

## Phase 4: Runtime Observability

目标：可以回答“哪个 Team 成员为何调用哪个工具、用了哪些输入、产出什么、花了多久和多少钱”。

交付：

- Agno Event Bridge；
- canonical span/event schema；
- Campaign 到 model/tool/MCP 的调用树；
- token、成本、时延、重试、授权拒绝和失败原因；
- Evidence/Artifact/Asset 关联；
- 脱敏后的 Run graph UI；
- 可选 OpenTelemetry export。

退出条件：一次失败能从 Campaign 状态追踪到具体 member Agent 和 Tool/MCP attempt，并能定位关联输入输出而不泄露 secrets。

## Phase 5: Replay, Security, and Harness

目标：把外部能力和资产纳入可重复、可故障注入的工程验证。

交付：

- recorded / recompute_local / live_external replay modes；
- Tool/MCP 响应 recording；
- MCP 断连、超时、限流、权限拒绝、恶意网页和资产失败注入；
- SSRF、egress、prompt injection 和 secret leakage 测试；
- 引用覆盖率、资产完整性、成本和阶段时延评估。

退出条件：CI 在断网环境通过；默认 Replay 不联网、不重新生成媒体、不发布。

## Phase 6: Provider Expansion

完成前述基础能力后，再按业务价值增加：

- 电商平台趋势和广告数据 Connector；
- 评论/社媒 listening Connector；
- 图片生成 Provider；
- 文档模板和品牌资产能力；
- 最后才评估视频和真实平台写入。

每个 Provider 必须通过同一 registry、policy、Trace、Asset 和 Harness 契约，不允许绕过平台层直接嵌入 Agent。

## Recommended Implementation Order

```text
Agno audit
  -> capability contracts/policy
  -> search/browser research
  -> evidence store
  -> asset catalog/media storage
  -> Agno event bridge/run graph
  -> replay/security harness
  -> additional providers
```

## Acceptance Summary

- 正式 Agent/Team/Workflow 均由 Agno 实例化和执行。
- Tool/MCP 调用遵守最小权限并全程可审计。
- 外部研究结论具有可验证证据链。
- Agent 生成文件具有版本、哈希、血缘和访问控制。
- Team member、模型、Tool/MCP 和产出在同一 Trace 中关联。
- 审批严格绑定不可变 Artifact/Asset version。
- Mock 只用于测试、Replay 和故障注入。
- 真实发布继续保持在独立安全边界之外。

## Next Session Entry Point

下一会话从 OpenSpec change 的 Task 1 开始：先运行 Agno capability audit 和 smoke tests，再确认 Search/Browser、MediaStorage 与 event stream 的实际 API。不要直接开始自研 registry runtime 或通用调度层。

