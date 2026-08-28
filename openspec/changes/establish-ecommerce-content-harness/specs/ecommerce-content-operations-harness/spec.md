## Purpose

为电商商家提供一个可重复、可观察、可评估的内容运营任务执行能力，覆盖从商品研究到创意生成、审批、模拟投放、数据分析和下一轮优化的闭环。

## ADDED Requirements

### Requirement: Canonical campaign scenario
系统 SHALL 支持以商品、品牌、目标人群、投放平台、营销目标和约束为输入，执行新品内容运营场景。

#### Scenario: Run a campaign
- **WHEN** 用户提交完整的商品营销请求
- **THEN** 系统 SHALL 生成并保存研究包、Campaign Brief、创意包、平台载荷、合规报告、审批记录、发布结果、表现报告和优化 Brief

#### Scenario: Missing required input
- **WHEN** 商品、平台或营销目标缺失且无法从知识库确认
- **THEN** 系统 SHALL 停止生成不可验证的结论，并返回待补充字段

### Requirement: Fixed primitive composition
系统 SHALL 仅调用预注册的 Agent、Agent Team、Workflow 和 Tool，不得由模型动态创建任意 Agent、工具或执行图。

#### Scenario: Select the research team
- **WHEN** canonical campaign 进入市场调研阶段
- **THEN** 系统 SHALL 调用固定成员的 Research Team，并汇总其结构化结果

#### Scenario: Select non-team stages
- **WHEN** campaign 进入策略、创意、平台适配、合规或优化阶段
- **THEN** 系统 SHALL 使用预注册的单 Agent、Workflow 或确定性校验器完成该阶段，不得为了增加角色数量而强制使用 Team

### Requirement: Research team output
Research Team SHALL 从商品、竞品、人群和趋势视角收集证据，并输出带来源、置信度和冲突标记的 Research Package。

#### Scenario: Evidence-backed research
- **WHEN** 研究成员完成检索或分析
- **THEN** 每个可影响营销决策的事实 SHALL 关联来源或 fixture 引用，并标记置信度

#### Scenario: Conflicting evidence
- **WHEN** 不同来源对价格、参数或卖点存在冲突
- **THEN** Research Package SHALL 保留冲突并标记为待确认，不得静默选择一个值

### Requirement: Structured campaign artifacts
系统 SHALL 以版本化、可校验的结构化 artifact 在阶段之间传递结果，至少包括 ResearchPackage、CampaignBrief、CreativePackage、PlatformPayload、ComplianceReport、PerformanceReport 和 OptimizationBrief。

#### Scenario: Invalid artifact
- **WHEN** 任一 Agent 输出不符合 artifact schema
- **THEN** 系统 SHALL 拒绝其进入下一阶段，并记录校验错误和重试/人工处理状态

### Requirement: Creative generation and platform adaptation
系统 SHALL 基于 Campaign Brief 生成多个广告创意变体，并将创意转换为目标平台载荷；平台硬约束 SHALL 由确定性校验器执行。

#### Scenario: Generate creative variants
- **WHEN** Campaign Brief 已通过校验
- **THEN** 系统 SHALL 生成文案、图片 brief 和视频脚本/分镜中的适用产物，并说明每个变体的创意角度和目标指标

#### Scenario: Platform validation
- **WHEN** 创意被适配到目标平台
- **THEN** 系统 SHALL 校验字数、媒体数量、格式、禁用表达等硬约束；失败载荷不得进入审批或发布

### Requirement: Fact and policy safety
系统 SHALL 在内容进入人工审批前执行商品事实、品牌约束和平台广告政策检查，并输出风险、证据和修改建议。

#### Scenario: Unsupported claim
- **WHEN** 文案包含商品资料无法支持的参数、功效或承诺
- **THEN** ComplianceReport SHALL 标记风险并阻止该版本发布

#### Scenario: Policy violation
- **WHEN** 内容命中禁用词或平台硬性政策
- **THEN** 系统 SHALL 将状态置为 revision_required，并保留可追溯的规则命中记录

### Requirement: Human approval gate
系统 SHALL 在任何发布或模拟发布动作前要求人工审批，且审批状态必须可审计。

#### Scenario: Approved content
- **WHEN** 内容通过合规检查且用户明确批准指定版本
- **THEN** 系统 SHALL 允许受控 Publish Tool 执行一次对应版本的发布动作

#### Scenario: Rejected content
- **WHEN** 用户拒绝内容或要求修改
- **THEN** 系统 SHALL 阻止发布，并允许基于反馈生成新版本；旧版本审批记录不得被覆盖

### Requirement: Controlled side effects
发布 SHALL 由受控 Tool/Service 执行，而不是由 Agent 直接执行；工具必须校验审批、平台载荷和幂等键。

#### Scenario: Publish without approval
- **WHEN** 任意调用缺少有效审批或审批版本与载荷版本不一致
- **THEN** Publish Tool SHALL 拒绝调用并记录原因

#### Scenario: Duplicate publish
- **WHEN** 同一幂等键被重复提交
- **THEN** 工具 SHALL 返回原始发布结果或安全拒绝，不得创建重复发布

### Requirement: Analytics and optimization loop
系统 SHALL 将指标计算与解释分离，基于表现数据生成带证据的优化假设和下一轮实验 Brief。

#### Scenario: Analyze performance
- **WHEN** 系统收到模拟或导入的曝光、点击、转化和成本数据
- **THEN** 确定性计算 SHALL 产生 CTR、CVR、CPA、ROAS 等指标，Analytics Agent SHALL 区分事实、推断和建议

#### Scenario: Plan next experiment
- **WHEN** 表现报告完成
- **THEN** Optimization Agent SHALL 指明观察、假设、要改变的变量、保持不变的变量和成功指标，不得直接修改真实预算或自动重投

### Requirement: Harness observability and replay
系统 SHALL 保存每次运行的 Agent/Team/Workflow 步骤、模型版本、输入输出、工具调用、审批事件、耗时、成本和错误，并支持使用相同 fixture replay。

#### Scenario: Inspect trace
- **WHEN** 用户或评估程序查询一次运行
- **THEN** 系统 SHALL 返回按时间排序的可关联 trace events 和版本化 artifacts

#### Scenario: Replay a scenario
- **WHEN** 使用相同 scenario、fixture 和配置重新运行
- **THEN** 系统 SHALL 产生可比较的新 run，且不触发真实外部发布副作用

### Requirement: Evaluation and failure injection
Harness SHALL 提供确定性评估、可选的模型评审、成本/时延统计和可控故障注入。

#### Scenario: Evaluate a run
- **WHEN** 一次 scenario run 完成或失败
- **THEN** 评估结果 SHALL 至少包含 schema 通过率、事实支持率、政策违规率、审批绕过率、工具成功率、完成率、时延和成本

#### Scenario: Inject a tool failure
- **WHEN** fixture 配置指定工具超时、非法输出或发布错误
- **THEN** 系统 SHALL 按定义的重试、暂停、人工接管或安全失败路径运行，并在 trace 中记录故障
