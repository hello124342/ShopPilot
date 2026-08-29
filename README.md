# ShopPilot

ShopPilot 是面向电商商家的 AI 运营工作台：用固定、可审计的 Agno 工作流完成市场研究、营销策略、文案/视觉/视频创意、平台合规、人工审批、效果分析和下一轮优化。

它不是通用聊天机器人，也不自研 Agent runtime。底层直接使用 **Agno 3.0.1** 的 `Agent`、`Team` 和 `Workflow`；ShopPilot 负责电商领域契约、受控工具、审批状态机、Harness、评估和运营界面。

## 一分钟启动

默认 `mock` 模式完全离线，不需要任何 Key：

```powershell
Copy-Item .env.example .env
docker compose up --build -d
.\scripts\verify.ps1
```

浏览器打开 `http://127.0.0.1:8080`（API 地址为 `http://127.0.0.1:8000`）。停止服务：

```powershell
docker compose down
```

数据保存在 Docker named volumes：PostgreSQL、Redis、MinIO 和兼容数据卷。普通 `down` 或容器重启不会删除；只有显式执行 `docker compose down -v` 才会删除本地运行数据。

## 真实 Agno 模式

复制 `.env.example` 后只需调整：

```env
SHOPILOT_RUNTIME_MODE=agno
SHOPILOT_PROVIDER=openai
SHOPILOT_MODEL_ID=gpt-4o-mini
SHOPILOT_API_KEY=your-key
```

OpenAI-compatible 服务还可配置 `SHOPILOT_BASE_URL`。缺少 Key 时服务保持 live，ready 返回 `503 / agno_api_key_missing`，不会静默回退到 mock。

> `.env` 已被忽略。API、健康检查和 ShopPilot JSON 日志永远不返回 Key。请勿记录 Agno model 对象本身，因为第三方对象的 repr 可能包含构造参数。

## 产品工作流

```text
商品与目标输入
  → Research Team（商品 / 竞品 / 人群 / 趋势 / 证据核验）
  → Strategy Agent
  → Creative Workflow（文案 / 视觉 brief / 视频脚本）
  → Platform Adapter + Compliance Agent
  → 人工审批（版本绑定、append-only）
  → Mock Publish
  → Analytics Agent
  → Optimization Agent
```

- Research 是固定成员的 Agno Team；Strategy、Creative、Compliance、Analytics、Optimization 是专业单 Agent。
- Workflow 代码控制状态、重试、权限、审批和副作用，不允许 Agent 自由发布或动态生成 DAG。
- Replay 强制使用 `side_effect_mode=disabled`。
- MVP 没有真实平台 connector；所有“发布”都是本地 Mock Publish。

## 工作台能力

- 运营总览与运行列表；
- 场景快速填充和完整 Campaign 表单；
- 工作流阶段时间线；
- 研究证据、营销策略、多版本创意和平台载荷；
- 合规风险、退回修改、版本化审批；
- Trace、Replay 和三层质量评估；
- mock/agno 模式与安全诊断。

## 前端工作台\n\n正式前端由 React + TypeScript + Vite 构建，包含登录、运营总览、Agent 能力中心、Skill/Tool/MCP 目录、Campaign 阶段工作区、Trace、Evidence、Asset 和人工审核 Gate。Docker 启动后访问 `http://127.0.0.1:8080`。\n\n## Host Python 开发

Docker daemon 不可用时：

```powershell
python -m pip install -e ".[test]"
python -m pytest -q
python -m shopilot.server
```

常用验证：

```powershell
# 离线测试 + 10+ Harness scenarios
.\scripts\offline-test.ps1

# 可选：真实 provider 连接验证（无发布副作用）
$env:SHOPILOT_API_KEY="..."
.\scripts\provider-smoke.ps1

# Docker named volume 重启恢复验证
.\scripts\container-persistence.ps1
```

离线测试通过 `tests/conftest.py` 禁止外部网络连接。

## API

```text
GET  /health/live
GET  /health/ready
GET  /api/runtime
GET  /api/scenarios
GET  /api/runs
POST /api/runs
GET  /api/runs/{run_id}
GET  /api/runs/{run_id}/artifacts
GET  /api/runs/{run_id}/trace
GET  /api/runs/{run_id}/approvals
GET  /api/runs/{run_id}/evaluation
GET  /api/runs/{run_id}/assets
GET  /api/assets/{asset_id}/versions/{version}
GET  /api/assets/{asset_id}/versions/{version}/preview
GET  /api/assets/{asset_id}/versions/{version}/download
POST /api/runs/{run_id}/exports/markdown
POST /api/runs/{run_id}/approve
POST /api/runs/{run_id}/reject
POST /api/runs/{run_id}/replay
POST /api/runs/{run_id}/evaluate
```

错误响应稳定为：

```json
{"error_code":"run_not_found","message":"运行记录不存在","request_id":"..."}
```

## 稳定业务契约

`CampaignInput`、`ResearchPackage`、`CampaignBrief`、`CreativePackage`、`PlatformPayload`、`ComplianceReport`、`PerformanceReport`、`OptimizationBrief`、`TraceEvent`、`ApprovalEvent`、`EvaluationReport`。

新增工具必须定义结构化输入/输出、超时、错误、重试、幂等和副作用模式。真实平台 adapter 属于后续独立变更，必须另行实现 OAuth/密钥管理、沙箱、权限、撤回、审计和平台级幂等，不能复用当前 Mock Publish 作为真实实现。

详见 [开发与交付规范](docs/development.md) 和 [平台运维说明](docs/platform-operations.md)。
