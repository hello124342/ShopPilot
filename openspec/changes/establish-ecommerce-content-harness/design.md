## Context

仓库当前只有一份产品初稿，没有既有运行时代码或 capability spec。设计需要同时满足电商内容运营闭环和 Agent Harness 的可复现性；Agno 已提供 Agent、Team、Workflow、HITL、后台执行、Tracing 和 Evals 等运行时原语。

## Goals / Non-Goals

**Goals:**

- 用固定 canonical scenario 验证研究、策略、创意、审批、分析和优化闭环。
- 用 Research Team 展示真正需要多角色协作的市场调研能力。
- 用单 Agent、Workflow、确定性校验器和受控 Tool 约束其他阶段。
- 让结构化 artifact、trace、replay、evaluation 和 failure injection 成为一等能力。
- 保持 MVP 可在本地、低基础设施依赖下运行。

**Non-Goals:**

- 不实现动态任意 Agent spawning 或动态任意 DAG 生成。
- 不实现真实社交平台发布、真实广告预算控制或支付相关动作。
- 不在 MVP 训练视频模型或建设完整多租户 SaaS。
- 不把自然语言报告、LLM 自评或 UI 进度动画当作可靠性证明。

## Decisions

### 1. 固定业务 Workflow，按阶段选择 primitive

使用代码定义的 Campaign Workflow 编排 Research Team、Strategy Agent、Creative Workflow、Platform Adapter、Compliance、Approval、Publish、Analytics 和 Optimization。放弃 Main Agent 动态派生子 Agent；若以后需要简单/复杂路径，使用受约束的 classifier 选择预注册 workflow。

替代方案：让一个主 Agent 自由生成子 Agent 和 DAG。该方案灵活但不可复现、难以做权限和副作用控制，因此不采用。

### 2. 只在市场调研使用 Research Team

Research Team 固定包含 Product、Competitor、Audience、Trend 和 Evidence Reviewer 角色，可并行收集证据再汇总。策略、创意、平台适配和优化是明确的单一决策或转换任务，使用单 Agent；多步骤并行使用 Workflow，而非把每个步骤包装成 Team。

### 3. 结构化 artifact 作为边界契约

使用 Pydantic 风格 schema 定义 ResearchPackage、CampaignBrief、CreativePackage、PlatformPayload、ComplianceReport、PerformanceReport 和 OptimizationBrief。每次变更产生新版本并保留来源引用，拒绝非法 artifact 进入下一阶段。

### 4. 硬规则由代码执行，软判断由 Agent 辅助

字数、媒体数量、禁用词、schema、审批和幂等由确定性代码执行；平台语气、创意角度、风险解释和优化假设由 Agent 生成。发布是受审批门禁保护的 Tool，不允许 Agent 直接持有不可控副作用。

### 5. MVP 使用可复现 fixture 和轻量存储

先用本地 JSON/CSV fixture 模拟商品、研究来源、平台规则和指标；运行记录可先落 SQLite/JSONL。等评估证明需要长耗时或并发后，再接入 AgentOS background execution、PostgreSQL 或 Redis。

### 6. Evaluation 以整条任务为单位

评估器同时检查产物、事实、合规、工具调用、审批安全、完成率、时延和成本。LLM Judge 只作为补充，不能替代确定性检查；failure injection 用于验证超时、非法输出、审批拒绝和重复发布的安全路径。

## Risks / Trade-offs

- [研究 fixture 与真实市场差异] -> 明确 fixture 只用于可复现基线，后续增加带来源和时间戳的实时 adapter。
- [Team 增加 token 和延迟] -> 固定成员、并行执行、限制输出 schema，并用评估比较 Team 与单 Agent 的收益。
- [LLM 输出不稳定] -> schema 校验、重试预算、版本化 prompt/model、replay 和 deterministic validators。
- [平台规则变化] -> 将规则版本化为 fixture/policy adapter，记录生成时使用的版本。
- [优化建议被误当作因果结论] -> 强制输出 observation、hypothesis、evidence 和 success metric 四个字段。
- [模拟发布与真实发布语义混淆] -> MVP 只提供 mock tool，并在 API 和 trace 中显式标记 side_effect_mode。

## Migration Plan

先保留原始初稿作为历史参考，并将其同步改写为新的产品边界；实现阶段从本地 fixture 的 canonical scenario 开始。若需要回滚，只需停止使用新 change 的 workflow/fixture，不涉及线上数据迁移或真实平台撤销。

## Open Questions

- 后续接入实时研究时，优先支持哪些市场/平台数据源？
- 真实平台发布是否需要独立的运营人员角色和多级审批？
