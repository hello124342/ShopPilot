# Tasks

## 1. Agno-first foundation audit

- [x] 1.1 锁定并记录 Agno/Python 依赖版本，核对升级策略。
- [x] 1.2 对 Skills、Tools/Toolkits、MCPTools、MediaStorage、events、metrics、storage/session 做可运行 capability matrix。
- [x] 1.3 为 Agent、Team、Workflow、MCP、MediaStorage 和 event stream 增加最小 smoke tests。
- [x] 1.4 记录所有需要 ShopPilot 适配层的 Agno 缺口，禁止无记录地自研 runtime 能力。

## 2. Capability contracts and registry

- [x] 2.1 定义 `AgentDefinition`、`SkillManifest`、`ToolDescriptor`、`MCPServerConfig`、`CapabilityPolicy`、`CredentialReference` schema。
- [x] 2.2 建立版本化 Skill/Tool/MCP registry 和启动时配置校验。
- [x] 2.3 在 Agno runtime factory 中解析 profile，并绑定原生 Skills、Tools/Toolkits 和 MCPTools。
- [x] 2.4 实现构造时和调用时授权、side-effect 分类及拒绝审计。
- [x] 2.5 实现 MCP 连接生命周期、健康检查、超时、重试、熔断和凭据引用。
- [x] 2.6 增加能力状态/健康 API，确保响应不泄露 secrets。

## 3. External research and evidence

- [x] 3.1 选择并验证 Search + Browser Extraction 的 Agno 原生 Tool 或 allowlisted MCP adapter。
- [x] 3.2 定义 `EvidenceRecord`、citation 和 conflict schema，建立 Evidence Store。
- [x] 3.3 实现 URL/协议/私网限制、内容大小限制、HTML 清洗、重定向控制和提示词注入标记。
- [x] 3.4 将 Research collection 明确配置为 Agno 支持的并发 Team 执行，并用时序测试证明并发。
- [x] 3.5 将 Evidence Reviewer 作为独立复核阶段，只允许读取规范化 Evidence。
- [x] 3.6 生成带 citation IDs、冲突和置信度的 `ResearchPackage`。
- [x] 3.7 增加来源失效、证据冲突、超时、注入内容和重复内容场景。

## 4. Managed asset plane

- [x] 4.1 定义 `Asset`、`AssetReference`、`AssetLineage` 和生命周期 schema。
- [x] 4.2 基于 Agno MediaStorage 能力实现本地/Docker Volume backend；仅在必要处增加薄适配层。
- [x] 4.3 建立 Asset Catalog、SHA-256 内容寻址、MIME/大小/媒体元数据和不可变版本。
- [x] 4.4 将 Artifact 输出中的媒体字符串迁移为类型化 AssetReference，同时保留旧 run 兼容读取。
- [x] 4.5 实现资产预览、下载、元数据和 lineage API，增加权限与安全响应头。
- [x] 4.6 实现审批与 Artifact/Asset version 绑定，新版本使旧审批失效。
- [x] 4.7 接入首个文档导出和图片生成 adapter；视频保持未实现状态。
- [x] 4.8 增加哈希、去重、损坏、quarantine、配额和保留策略测试。

## 5. Runtime observability

- [x] 5.1 定义 canonical `TraceSpan`、`TraceEvent`、`ModelCallMetrics`、`ToolCallRecord` 和 correlation schema。
- [x] 5.2 启用并验证 Agno workflow/team/member/tool/model 事件和运行标识。
- [x] 5.3 实现 Agno Event Bridge，映射层级关系并关联 Evidence、Artifact 和 Asset。
- [x] 5.4 实现 prompt/tool input/output 的字段级脱敏和 secret 检测。
- [x] 5.5 建立 Trace Store 查询、分页、保留和聚合指标能力。
- [x] 5.6 增加可选 OpenTelemetry exporter，默认本地模式无需外部服务。
- [x] 5.7 增加事件完整性、父子 span、成本、token、重试和错误关联测试。

## 6. Replay and harness

- [x] 6.1 定义 `recorded`、`recompute_local`、`live_external` replay mode。
- [x] 6.2 记录并重放 Tool/MCP 结果，默认禁止网络和所有真实副作用。
- [x] 6.3 扩展 failure injection：MCP 断连、超时、授权拒绝、限流、恶意网页和资产写入失败。
- [x] 6.4 增加 capability denial、secret non-disclosure、SSRF/egress 和 prompt injection 测试。
- [x] 6.5 更新 evaluation，加入引用覆盖率、工具成功率、资产完整性、成本和阶段时延。
- [x] 6.6 保证全部 Mock/Replay 测试在网络禁用状态下通过。

## 7. API and operations UI

- [x] 7.1 增加 run graph/span、evidence、asset、lineage、capability health 和 metrics API。
- [x] 7.2 在运行详情中展示 Stage/Team/Agent/Model/Tool/MCP 调用树。
- [x] 7.3 增加证据来源、冲突、引用覆盖和原始来源跳转。
- [x] 7.4 增加资产预览、版本、血缘、审批状态和下载入口。
- [x] 7.5 增加 Tool/MCP 错误、重试、成本和时延视图，所有敏感字段默认脱敏。
- [x] 7.6 增加 replay mode 选择和副作用警示，不在 UI 中实现 Agent 编排。

## 8. Documentation and delivery

- [x] 8.1 更新架构、开发、配置、Skill/Tool/MCP 添加规范和 Agno primitive 选择原则。
- [x] 8.2 更新 `.env.example`，只加入占位符、配置说明和安全注释。
- [x] 8.3 更新 Docker persistence、备份、资产保留和 Trace 保留说明。
- [x] 8.4 运行完整离线测试、Agno smoke、API 集成测试和前端 Playwright 检查。
- [ ] 8.5 使用至少一个真实搜索/浏览能力完成 canonical research scenario，保留 Trace 和 Evidence。
- [x] 8.6 完成安全审查和验收清单后，再决定是否进入真实平台 adapter 设计。


