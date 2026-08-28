## Why

当前初稿把 ShopPilot 描述成覆盖市场调研、素材生成、发布和数据优化的完整 SaaS，并以“主 Agent 动态派生子 Agent”为核心，范围过大且难以复现、评估和保证安全。现在需要把产品收敛为面向电商内容运营的 Agent Harness：用一个可重复的新品营销场景验证研究、策略、创意、分析和优化闭环，同时明确何时使用 Agent Team、单 Agent、Workflow 和受控 Tool。

## What Changes

- 将产品定位从泛化的内容营销平台收敛为“电商内容运营 Agent Harness”。
- 固定一个 canonical 场景：商品研究 -> 营销策略 -> 广告创意 -> 平台适配 -> 合规 -> 人工审批 -> 模拟发布 -> 指标分析 -> 下一轮优化。
- 移除主 Agent 动态创建或派生任意子 Agent 的设计；只允许调用预注册的 Agent、Team、Workflow 和 Tool。
- 明确 primitive 分工：市场调研使用固定成员的 Research Team；策略、创意、平台适配、合规和优化以单 Agent 为主；流程控制使用 Workflow；发布使用受控 Tool。
- 增加结构化 artifact contract、工具契约、审批门禁、trace、replay、evaluation 和 failure injection 要求。
- 将数据分析拆为确定性指标计算与 Agent 解释；复杂多视角分析可在后续引入 Analytics Team。
- 明确 MVP 的非目标：真实平台发布、视频模型训练、全量实时研究、多租户 SaaS、库存/定价/客服/广告预算自动控制。
- 更新现有 `ShopPilot Spec.md`，使其与新的产品边界和架构原则一致。

## Capabilities

### New Capabilities

- `ecommerce-content-operations-harness`: 定义电商内容运营场景、Agent/Team/Workflow 编排、结构化产物、审批与发布安全、分析优化闭环及 Harness 评估要求。

### Modified Capabilities

- 无。当前仓库没有既有 `openspec/specs/` capability spec；原始 `ShopPilot Spec.md` 将作为项目初稿同步更新，不作为 delta capability。

## Impact

- 新增 OpenSpec 规划产物：proposal、capability spec、design 和 tasks。
- 后续实现将影响 Agno SDK/AgentOS runtime、FastAPI/API 边界、工具适配器、运行轨迹与评估存储，以及可选的演示 UI。
- MVP 依赖优先保持轻量：Agno、Pydantic、SQLite、本地 fixture 和测试/评估 CLI；暂不要求 PostgreSQL、Redis、Celery/ARQ、Vector DB 或真实平台 API。
