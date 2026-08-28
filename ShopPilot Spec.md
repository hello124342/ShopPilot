# ShopPilot 产品与架构 Spec

## 1. 产品定位

ShopPilot 是一个面向电商商家的 AI 内容运营 Agent Harness。它围绕一个商品或营销活动，验证并运行“市场研究 -> 营销策略 -> 广告创意 -> 平台适配 -> 合规审核 -> 人工审批 -> 模拟投放 -> 数据分析 -> 下一轮优化”的闭环。

它不是一个让主 Agent 任意创建子 Agent 的平台，也不是第一阶段就覆盖库存、定价、客服和真实广告账户控制的完整 SaaS。

## 2. 核心用户价值

商家能够：

1. 了解商品、人群、竞品和平台趋势；
2. 把研究结果转化为可执行的营销策略和 Creative Brief；
3. 生成多组广告文案、图片创意 brief 和视频脚本/分镜；
4. 根据平台规则适配内容并完成事实、品牌和广告政策检查；
5. 在人工审批后模拟发布；
6. 基于曝光、点击、转化和成本分析下一轮实验。

系统重点不是 Agent 数量，而是结果是否可复现、可观察、可评估、可回放且副作用可控。

## 3. Canonical 场景

用户提交商品、品牌、目标人群、平台、营销目标和约束。系统执行：

```text
商品/品牌资料 -> Research Team -> Strategy Agent -> Creative Workflow
-> Platform Adapter + 硬规则校验 -> Compliance -> Human Approval
-> Mock Publish -> 指标计算 + Analytics Agent -> Optimization Agent
```

输出为 ResearchPackage、CampaignBrief、CreativePackage、PlatformPayload、ComplianceReport、PerformanceReport 和 OptimizationBrief。

## 4. Agent / Team / Workflow 分工

### 4.1 原则

- 只使用预注册的 Agent、Team、Workflow 和 Tool。
- 取消 Main Agent 动态创建或派生任意子 Agent。
- Workflow/代码负责顺序、分支、重试、权限、审批和副作用。
- Agent/Team 负责理解、研究、生成、解释和提出假设。
- 不把每个环节都包装成 Team。

### 4.2 Primitive 选择表

| 环节 | 原语 | 说明 |
|---|---|---|
| 任务分类 | 规则或轻量单 Agent | 仅从预注册 workflow 中选择 |
| 市场调研 | Research Team | 固定成员并行研究、证据汇总和冲突消解 |
| 营销策略 | Strategy Agent | 将研究包转成单一 Campaign Brief |
| 文案/图片/视频创意 | 单 Agent | 分别生成文案、图片 brief、视频脚本/分镜 |
| 多模态编排 | Creative Workflow | 并行生成后统一汇总和校验 |
| 平台适配 | Platform Agent + validators | Agent 处理软风格，代码处理硬约束 |
| 合规检查 | 单 Agent + validators | 事实、禁用词、政策和风险说明 |
| 人工审核 | Workflow/状态机 | 不是 Agent；审批事件不可覆盖 |
| 发布 | 受控 Tool/Service | 校验审批、版本和幂等键 |
| 指标计算 | 确定性代码 | CTR、CVR、CPA、ROAS 等 |
| 数据解释 | Analytics Agent | 区分事实、推断和建议 |
| 深度数据分析 | Analytics Team（后续） | 多人群、多素材、多漏斗分析时启用 |
| 下一轮优化 | Optimization Agent | 产出实验 Brief，不直接改预算或重投 |

### 4.3 Research Team

Research Team 是 MVP 中明确需要协作能力的环节，成员固定为 Product Analyst、Competitor Analyst、Audience Analyst、Trend Analyst 和 Evidence Reviewer。输出必须带来源或 fixture 引用、置信度和冲突标记；冲突不得静默消解。

## 5. 结构化业务产物

阶段之间只通过版本化、可校验的 artifact 传递结果：

- `ResearchPackage`：研究事实、洞察、机会、风险和证据；
- `CampaignBrief`：目标、受众、卖点、创意方向、平台、CTA、成功指标和测试假设；
- `CreativePackage`：文案、图片 brief、视频脚本/分镜和变体信息；
- `PlatformPayload`：目标平台的标题、正文、媒体和 CTA；
- `ComplianceReport`：事实支持、品牌规则、平台规则、风险和修改建议；
- `PerformanceReport`：原始指标、派生指标、事实、推断和建议；
- `OptimizationBrief`：观察、假设、改变变量、保持变量、下一步动作和成功指标。

非法 schema、缺失证据或无法验证的关键字段不得进入下一阶段。

## 6. 安全与人工审批

schema、字数、媒体数量、格式、禁用词、审批和幂等由确定性校验器执行；平台语气、创意角度、风险解释和优化假设由 Agent 辅助。未经审批或版本不一致的内容不得发布。用户拒绝后生成新版本，旧版本和审批记录不可覆盖。

状态至少包括：

```text
PENDING -> RUNNING -> WAITING_REVIEW -> APPROVED -> PUBLISHED
                         └-> REVISION_REQUIRED
任何阶段 -> FAILED / CANCELLED
```

## 7. 数据分析与优化

系统先用确定性逻辑计算 CTR、CVR、CPA、ROAS 等指标。Analytics Agent 必须区分 Observation、Hypothesis、Recommendation 和 Evidence。Optimization Agent 只能生成下一轮实验计划，不得自动修改真实预算或重投。

## 8. Harness 能力

每个 scenario 定义输入、约束、期望产物和评分标准。MVP 使用本地 JSON/CSV fixture 模拟商品资料、研究来源、平台规则和投放指标，以保证离线可复现。

每次 run 记录 run、step、agent/team、模型和 prompt 版本、工具调用、artifact、审批、耗时、成本和错误。相同 scenario、fixture 和配置可以 replay，默认关闭真实副作用。

评估至少覆盖 schema 通过率、事实支持率、政策违规率、审批绕过率、工具成功率、任务完成率、时延、成本和重试次数。LLM Judge 只能作为补充，不能覆盖确定性失败。Harness 必须支持工具超时、非法输出、审批拒绝、重复发布和指标延迟等故障注入。

## 9. MVP 边界

### 包含

- 一个新品内容运营 canonical scenario；Research Team；策略、创意、平台、合规、分析和优化单 Agent；Campaign/Creative/Approval/Analytics Workflow；mock publish 和 mock metrics；本地 fixture、trace、replay、evaluation 和 failure injection；CLI 或最小 API/页面。

### 不包含

- 动态任意 Agent/DAG；真实平台发布和广告预算控制；视频模型训练；全量实时市场搜索；多租户和复杂 RBAC；库存、定价、客服和 ERP；PostgreSQL、Redis、Celery/ARQ、Vector DB，除非评估证明本地方案不足。

## 10. 技术路线与验收

第一阶段优先使用 Python、Agno SDK/AgentOS、Pydantic、SQLite/JSONL、本地 fixture、pytest 和 evaluation CLI。Agno 提供 Agent、Team、Workflow、HITL、后台执行、Tracing 和 Evals；业务层补充电商 artifact、policy、approval、mock connector 和 evaluator。

至少提供五个正常场景和五个异常场景，并证明：无网络可运行、产物通过 schema、事实有来源、未审批不可发布、失败可回放、trace 可追踪、replay 无真实副作用、evaluation 输出稳定、分析区分事实/推断/建议，以及 Research Team 相对单 Agent baseline 的收益可比较。
