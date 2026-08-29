# Design: Agent Capability, Asset, and Observability Platform

## 1. Context

ShopPilot 的核心边界保持不变：Agno 负责 Agent、Team、Workflow 和模型/工具执行；ShopPilot 负责电商运营领域契约、固定流程、权限、审批、版本、Harness 和产品体验。

当前主要缺口是三类平台能力彼此未连接：Agent 不具备受治理的外部能力，运行结果不能沉淀为真实资产，现有 Trace 不能解释 Team 成员、模型和 Tool/MCP 的完整行为。

## 2. Design Principles

1. **Agno-first**：先验证当前锁定版本原生实现，再决定适配层。
2. **No parallel runtime**：不自研 Agent loop、Team scheduler、通用 DAG 或 Tool protocol。
3. **Least privilege**：能力按 Agent、Team、租户、环境和副作用等级授权。
4. **Immutable lineage**：Artifact、Asset、Evidence 和审批均以不可变版本关联。
5. **External data is untrusted**：网页、搜索结果和 MCP 响应必须经过规范化和安全边界。
6. **Replay by recording**：Replay 默认消费已记录的模型/工具结果，不重新触达外部系统。
7. **One correlation model**：ShopPilot run ID 与 Agno workflow/team/agent run ID 全部可关联。

## 3. Agno Capability Audit Gate

每个实施阶段先形成一份轻量 capability matrix：

| Need | Agno primitive to verify | ShopPilot responsibility |
|---|---|---|
| Skill attachment | `Skills`, `Agent.skills`, Team skills | Manifest、版本和授权 |
| Native tools | `Agent.tools`, Team tools, Toolkit | Descriptor、策略和审计 |
| MCP | `MCPTools`, MCP lifecycle | Server allowlist、凭据引用 |
| Media | `MediaStorage`, `store_media` | Asset catalog、血缘和 ACL |
| Events | run/team/workflow/tool events | Canonical event mapping 和查询 |
| Metrics | model/tool metrics | 成本规则、聚合、SLO |
| Persistence | Agno storage/session APIs | 领域索引和租户边界 |

### 3.1 Agno 3.0.1 installed-version findings

- Persistence lives under `agno.db`; the legacy `agno.storage` namespace is not present. SQLite and MCP support are official extras and are enabled through `agno[mcp,sqlite]==3.0.1`.
- `TeamMode.broadcast` is the native fan-out mode. `Team.arun()` executes delegated member calls concurrently, while `Team.run()` is sequential. A Team still delegates through its native model/tool semantics; ShopPilot will not bypass that loop with a custom scheduler.
- `LocalMediaStorage` provides atomic byte persistence and integrity sidecars, but no signed local URL. ShopPilot therefore streams authorized local downloads through its API.
- The executable compatibility gate is `tests/test_agno_capabilities.py`; the full matrix and removable adapter boundaries are recorded in `docs/architecture/agno-capability-audit.md`.

若增加自研实现，PR/ADR 必须回答：原生能力为何不足、适配层边界、测试策略、Agno 升级时如何删除或替换。

## 4. Target Architecture

```text
FastAPI / Operations UI
          |
Campaign Application Service
          |
Agno Workflow ------------------------------------------------+
  |                                                           |
  +-> Agno Team / Agent                                       |
        |                                                     |
        +-> Skill Profile                                     |
        +-> Capability Policy                                 |
        +-> Agno Tool / Toolkit / MCPTools                    |
                 |                                            |
                 +-> Search / Browser / Data Provider         |
                                                              |
Evidence Store <-> Artifact Store <-> Asset Catalog <-> MediaStorage
                                                              |
Agno Event Stream -> Event Bridge -> Trace Store -> Metrics/UI+
```

## 5. Capability Plane

### 5.1 Domain Contracts

- `AgentDefinition`: Agent 稳定 ID、角色、版本、模型策略和 Capability Profile。
- `SkillManifest`: Skill ID、版本、说明、输入输出契约、指令资源、适用 Agent 和评估规则。
- `ToolDescriptor`: Tool ID、版本、输入输出 schema、超时、重试、幂等和副作用等级。
- `MCPServerConfig`: Server ID、transport、命令/URL、健康检查、允许工具和凭据引用。
- `CapabilityPolicy`: subject、resource、action、tenant、environment 和 effect。
- `CredentialReference`: 仅保存秘密管理系统中的引用，不保存明文。

Skill Manifest 是 ShopPilot 对 Agno Skills 的治理元数据，不替代 Agno 的 Skills 运行机制。Tool Descriptor 同理，最终调用必须由 Agno Tool/Toolkit/MCPTools 执行。

### 5.2 Policy Enforcement

能力授权需要在构造时和调用时各检查一次：

```text
Agent factory -> resolve allowed capabilities -> construct Agno runtime
Tool call     -> authorize tenant/environment/side effect -> execute
```

副作用等级：`read_only`、`local_write`、`external_write`、`publish`。Research Agent 初期只允许 `read_only`；发布继续由 Workflow 审批门禁控制。

### 5.3 MCP Operations

- MCP Server 仅允许管理员通过配置注册。
- 启动时验证配置，按需连接，支持超时、健康检查和熔断。
- 每个 Server 和 Tool 使用稳定 ID，调用进入 Trace。
- 密钥由服务端注入，前端和 Agent prompt 只能看到 Credential Reference。
- 禁止 MCP 返回内容直接改变系统指令或能力策略。

## 6. Research Team Topology

研究阶段采用固定的三段式 Agno 编排：

```text
Collection Team (concurrent fan-out)
  - Product Research Agent
  - Competitor Research Agent
  - Audience Research Agent
  - Trend Research Agent
             |
             v
Evidence Reviewer Agent
  - normalize / deduplicate / conflict / confidence
             |
             v
Research Synthesis (Team coordinator or Agent)
  - ResearchPackage with citations
```

实施时必须显式配置 Agno Team mode，并用当前版本支持并发的 API（优先异步运行）验证实际并发；不能依赖 prompt 中的“并行”字样。Evidence Reviewer 默认只读 Evidence Store，不独立浏览网络，避免审查者悄悄引入新证据。

Research Team 之外继续采用既定结构：Strategy、Creative、Compliance、Analytics、Optimization 使用单 Agent，由固定 Campaign Workflow 串联。只有确实需要并行专长或相互审查的环节才升级为 Team。

## 7. Evidence Plane

`EvidenceRecord` 包含 source URL/type、标题、摘录、抓取时间、内容哈希、collector、tool call、置信度和引用状态。

处理流程：

```text
Search result -> Browser extraction -> sanitize -> normalize
 -> content hash/deduplicate -> conflict detection -> Evidence Store
 -> citation IDs -> ResearchPackage
```

安全要求：域名/协议限制、响应大小限制、内容类型校验、超时、重定向上限、私网地址阻断、HTML 清洗、提示词注入标记和敏感数据脱敏。

## 8. Asset Plane

### 8.1 Separation

- Artifact：结构化业务对象，例如 `CampaignBrief`、`CreativePackage`。
- Asset：真实文件或媒体，例如 Markdown、PDF、PNG、MP4。
- AssetReference：Artifact 的某个不可变版本如何使用 Asset。
- AssetLineage：父资产、派生资产和变换参数。

### 8.2 Storage

优先使用 Agno `MediaStorage`/`AsyncMediaStorage` 承接运行时媒体保存。ShopPilot 在其之上维护领域级 Asset Catalog；若 Agno 原生接口无法覆盖文档或所选后端，只实现窄的 storage adapter。

初期支持本地持久化和 Docker Volume；接口保持可迁移到 S3-compatible storage。对象键采用 tenant/run/sha256 或等价的内容寻址策略，数据库只存元数据和 storage URI。

### 8.3 Lifecycle and Safety

状态：`pending`、`generating`、`ready`、`failed`、`quarantined`、`archived`、`deleted`。

保存时计算 SHA-256、MIME、大小和媒体元数据；下载使用受控端点或短期签名 URL。审批绑定 Artifact/Asset version，生成新版本后旧审批失效。保留策略、配额、内容审核和删除审计必须可配置。

首阶段资产：Markdown、HTML、PDF、PNG/JPEG/WebP。视频生成、转码和 CDN 延后。

## 9. Observability Plane

### 9.1 Canonical Hierarchy

```text
Campaign Run
  Workflow Stage
    Team Run
      Member Agent Run
        Model Call
        Skill Application
        Tool/MCP Call
          External Request
        Artifact/Asset Production
```

Canonical span 至少包含 `trace_id`、`span_id`、`parent_span_id`、ShopPilot run ID、Agno run/session IDs、主体 ID/版本、状态、时间、错误和关联资源。Event 记录开始、完成、失败、重试、授权拒绝、证据/资产生成等事实。

### 9.2 Agno Event Bridge

优先启用 Agno 自带的 event storage/streaming、member events、tool call events 和 metrics。Event Bridge 只负责：

1. 将不同 Agno event 类型映射为稳定的 ShopPilot canonical schema；
2. 添加 tenant、campaign、artifact、asset 和 policy decision 关联；
3. 按规则脱敏 prompt、tool input/output 和错误；
4. 写入本地 Trace Store，并可选导出 OpenTelemetry。

`telemetry=False` 可以继续关闭厂商遥测，但不得关闭产品自身审计事件。

### 9.3 Metrics and UI

聚合完成率、阶段/队列/模型/工具时延、token、估算成本、重试、工具错误、授权拒绝、引用覆盖率和资产生成失败率。

UI 提供 Run graph、span 详情、工具调用摘要、证据引用、Artifact/Asset 关联和 Replay 来源。默认不显示密钥、完整敏感 prompt 或未脱敏外部响应。

## 10. Replay Semantics

- 默认 `recorded`：读取已记录模型/工具/MCP 输出及资产引用。
- 可选 `recompute_local`：只重跑确定性本地步骤。
- `live_external` 必须显式选择并再次授权，且不是 CI 默认模式。
- Replay 产生新的 run ID，并通过 `replayed_from_run_id` 关联原运行。
- 发布和其他真实写操作在 Replay 中始终禁用，除非进入独立的受控产品流程；本 change 不开放该能力。

## 11. Configuration

环境变量只提供配置入口，不把密钥写进仓库：

- Runtime mode 与 model provider；
- MCP server allowlist/config references；
- Search/browser provider credential references；
- Asset storage backend/root/bucket；
- Trace retention/export；
- Redaction 和 egress policy。

`.env.example` 只包含占位符和说明，真实值由部署环境注入。

## 12. Migration

1. 保持现有公共业务 schema 稳定，新增 ID/引用字段时提供兼容默认值。
2. 将现有本地 Tools 逐步包装为 Agno Tool/Toolkit，不一次性删除 Mock fixtures。
3. 将现有高层 `TraceEvent` 迁移到 canonical event adapter。
4. 为旧 JSONL Artifact 生成兼容读取路径，新运行写入新版 catalog。
5. UI 先读取新查询 API，旧 run 缺少 span/asset 时显示 legacy 状态。

## 13. Risks and Mitigations

- **Agno API 版本变化**：锁定版本，runtime factory 集中适配，增加 primitive smoke tests。
- **MCP 扩大攻击面**：管理员白名单、最小权限、网络出口限制和内容不可信策略。
- **Trace 泄露数据**：schema 级脱敏、字段 allowlist、保留周期和访问控制。
- **资产存储膨胀**：内容去重、配额、生命周期和派生文件回收。
- **事件量过大**：原始事件与聚合指标分层存储，采样仅用于非审计 span。
- **并发结果不稳定**：结构化输出、Evidence Reviewer、冲突保留和稳定评估集。

## 14. Product Decisions

- 首个真实外部能力：Web Search + Browser Extraction。
- 首批资产：研究报告/活动文档和图片；视频延后。
- MCP Server：管理员配置和白名单，不开放用户动态安装。
- Secret：服务端 Credential Reference，Agent 和前端不可见。
- Replay：默认 recorded，不重新联网。
- Team：只用于并发专长或交叉审查，其余使用单 Agent + Workflow。

## 15. Open Questions for Implementation

- 选择 Agno 当前版本原生支持度最好的 Search/Browser Tool 还是外部 MCP Server。
- 本地资产目录采用现有 store 扩展还是独立 SQLite catalog。
- Trace Store 首期使用 SQLite、JSONL + index，还是 Agno storage backend。
- 首个图片生成 provider 及其内容审核能力。

这些问题必须在对应实施任务开始时通过 capability audit 和小型 spike 决策，不阻塞本规划归档。

