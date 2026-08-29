# ShopPilot 开发与交付规范

## 1. 架构边界

```text
app        FastAPI 生命周期、API、静态 UI、错误与日志
domain     稳定 Pydantic 业务契约与状态
runtime    Agno primitive 和模型 provider 构造
agents     单职责业务 Agent
teams      固定成员 Agent Team
workflows  确定性状态、重试、审批和副作用编排
tools      研究、规则、平台、发布和指标工具
harness    scenario、fixture、trace、replay、failure injection、evaluation
```

`domain` 不依赖 Web、Agno 或具体 LLM。`app` 不实现 Agent 编排。测试与 Harness 不依赖真实 provider。任何智能执行必须复用 Agno 原语，不新增自研 Agent runtime、动态 spawning 或任意 DAG。

## 2. 环境契约

所有配置由 `shopilot.settings.Settings` 统一加载，环境变量使用 `SHOPILOT_*` 前缀：

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `SHOPILOT_RUNTIME_MODE` | `mock` | `mock` 或 `agno` |
| `SHOPILOT_SIDE_EFFECT_MODE` | `mock` | `disabled`、`mock`、`real`；MVP 不实现 real connector |
| `SHOPILOT_PROVIDER` | `openai` | `openai` 或 `openai-compatible` |
| `SHOPILOT_MODEL_ID` | `gpt-4o-mini` | Agno model id |
| `SHOPILOT_BASE_URL` | OpenAI v1 | 兼容服务 API 根地址 |
| `SHOPILOT_API_KEY` | 空 | 仅 agno 模式必需 |
| `SHOPILOT_DATA_DIR` | `.shopilot` | run 文件存储根目录；容器固定 `/app/data` |
| `SHOPILOT_RETRY_BUDGET` | `2` | 有限重试预算 |
| `SHOPILOT_PROVIDER_TIMEOUT` | `60` | provider 超时秒数 |
| `SHOPILOT_LOG_LEVEL` | `INFO` | JSON 应用日志等级 |
| `SHOPILOT_HOST/PORT` | `0.0.0.0:8000` | HTTP 监听配置 |

安全诊断只允许 `api_key_configured: boolean`。禁止日志、Trace、Artifact、Evaluation、错误消息或 API 响应包含 Key。特别禁止将 Agno model/client 对象传给日志格式化器；第三方 repr 不属于可信脱敏边界。

## 3. Agno primitive 选择

- 市场研究需要多视角、证据冲突处理，使用固定 Research Team。
- 策略、创意、合规、分析、优化输出职责单一，使用单 Agent。
- Campaign 和 Creative 是固定 Workflow；状态转换、重试和审批由代码控制。
- Tool 只暴露最小能力，Agent 不获得真实发布权限。
- mock 和 agno 输出必须落到相同领域 schema，UI 与评估器不得分支依赖 provider。

真实 provider smoke 使用：

```powershell
$env:SHOPILOT_RUNTIME_MODE="agno"
$env:SHOPILOT_SIDE_EFFECT_MODE="disabled"
$env:SHOPILOT_API_KEY="..."
python -m shopilot.cli provider-smoke
```

该命令实际调用 Agno Agent，但不调用 Publish Tool。

## 4. Artifact 与状态规则

阶段间只传递通过 Pydantic 校验的版本化 Artifact。`artifacts.jsonl`、`trace.jsonl`、`approvals.jsonl` 和 `evaluations.jsonl` 是 append-only；`run.json` 与 `evaluation.json` 是当前状态/最新结果投影。

状态主路径：

```text
pending → running → waiting_review → approved → published → analyzed → optimized
```

异常状态为 `revision_required`、`failed`、`cancelled`、`human_handoff`。拒绝会生成新的 `PlatformPayload.artifact_version`；任何旧版本审批都不能授权新版本。Replay 始终复制输入并强制 `side_effect_mode=disabled`。

文件 Store 面向本地单实例。多 worker 或多副本部署必须先将 Store 接口迁移到支持事务和并发控制的数据库。

## 5. 新增 Agent、Tool 与 Scenario

新增 Agent：

1. 先在 domain 定义输出 schema；
2. 给出证据和工具 allowlist；
3. 在 `AgnoRuntimeFactory` 注册，不动态构造角色；
4. 增加 deterministic fixture、单元测试和 trace 断言；
5. 明确失败进入 `failed` 还是 `human_handoff`。

新增 Tool 必须说明输入/输出、超时、重试、幂等键、副作用等级和错误码。外部文本始终是不可信数据，不能修改系统指令、工具权限或审批状态。

新增 Scenario 在 `shopilot.harness.scenarios` 指定输入、故障注入和期望状态。每次运行必须产生 run、artifact、trace 和 `evaluation.json`；故障场景也必须留下可诊断记录。

## 6. API 与错误规范

- 业务错误使用稳定 `error_code`，中文 `message` 可迭代；
- 每个响应带 `X-Request-ID`，错误 body 同时返回 `request_id`；
- 404 不得因读取动作创建空 run 目录；
- `/health/live` 只反映进程；`/health/ready` 检查配置与数据目录可写；
- Agno 缺 Key 时 API 保持 live，但 run 创建返回 503，不得降级；
- 不提供绕过审批的 `/publish` endpoint。

## 7. 前端规范

前端位于 `shopilot/app/static`，是 API 的观察与操作层，不保存 Agent 编排状态。所有动作按钮必须由服务器 run 状态控制可用性；页面需要明确的 loading、empty、error、success、disabled 状态。Artifact 优先用业务卡片呈现，原始 JSON 只作为诊断 tab。

桌面和移动端都要验证：首页、创建任务、运行列表、详情 tabs、退回、批准、Replay、Evaluate 和设置页。任何 API 错误必须显示用户消息和 request id。

## 8. 验证顺序

```powershell
python -m pip install -e ".[test]"
python -m pytest -q
python -m shopilot.cli scenarios
docker compose config
docker compose build
docker compose up -d
.\scripts\verify.ps1
.\scripts\container-persistence.ps1
```

离线 pytest 的 autouse fixture 会阻断 `socket.create_connection`。真实 provider smoke 是显式可选命令，不能加入默认 CI。Docker daemon 不可用时允许使用 `python -m shopilot.server` 作为 host fallback，但不能把 host 测试声称为容器构建通过。

'## 9. 后续开发流程与完成定义

本项目后续开发不再使用 OpenSpec skill，也不自动创建新的 OpenSpec change。需求、设计、实现、测试和验收直接在代码仓库中由工程任务、架构文档、测试和变更记录闭环管理。需要新增能力时，先审查现有 Agno 3.0.1 原生能力和当前产品边界，再实现最小可交付改动。

每次交付至少更新相关代码、测试、配置或运维文档，并运行与改动范围匹配的验证。禁止新建自研 Agent Runtime、Team Scheduler、通用 DAG 或 MCP Protocol。

'

1. 更新 OpenSpec requirement/task；
2. 修改 schema 与 deterministic test；
3. 实现最小范围行为；
4. 运行单元、集成、Scenario 与浏览器验收；
5. 容器相关改动运行 Compose config、build、health 和持久化验证；
6. 验收行为全部成立后才勾选 OpenSpec task。

完成必须满足：pytest 全通过、mock 完全离线、agno 缺 Key 明确失败、未审批无法发布、Replay 无副作用、10+ 场景生成稳定评估、UI 可完成审批闭环、文档命令可复制执行。

## 10. 真实平台 adapter 边界

真实小红书/抖音/电商平台发布不是当前 MockPublishTool 的配置开关。后续 connector 需要独立 OpenSpec，至少覆盖 OAuth/密钥轮换、平台沙箱、账号和资源权限、内容预览、审批主体、限流、幂等、失败补偿、撤回、审计保留和平台政策更新。在此之前，`side_effect_mode=real` 的真实请求必须被拒绝。
