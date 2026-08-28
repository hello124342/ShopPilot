## Context

现有 change 已完成 deterministic Harness、Agno primitive smoke test、FastAPI API 和内存级 mock 发布。当前工作区没有 Dockerfile、Compose、统一 settings 或 provider 配置；Docker Desktop 客户端可见但本次探测未能访问 Docker daemon，需要由用户本地权限决定。

## Goals / Non-Goals

**Goals:**

- 让 `docker compose up --build` 成为唯一推荐启动入口。
- 统一 mock/agno、provider、model、base URL、data directory 和 side-effect 配置。
- 保留 mock 离线能力，并将真实 Agno provider 配置做成显式模式。
- 提供可持久化运行记录、健康检查、结构化错误和最小操作 UI。

**Non-Goals:**

- 不在本 change 接入真实社交平台发布。
- 不存储或展示 API key。
- 不引入 PostgreSQL、Redis 或 Kubernetes；本地 Docker 使用单容器和文件卷。
- 不让 UI 绕过 Workflow 或审批状态机。

## Decisions

### 1. Settings 使用 Pydantic Settings

统一通过 `SHOPILOT_*` 环境变量读取配置，`.env.example` 只列变量名和示例值。mock 是无 key 的默认模式；agno 模式缺 key 直接 readiness failure。相比散落的 `os.environ`，强类型 settings 能在启动时一次性报告错误。

### 2. Agno provider 采用 OpenAI-compatible 配置

使用 provider、model、base URL 和 API key 注入 Agno model factory；默认 provider 为 OpenAI-compatible。这样既支持 OpenAI，也支持兼容 API 的本地/云端服务，且不改变业务 Agent contract。真实 provider 只在 `runtime_mode=agno` 创建。

### 3. 单容器 + 数据卷

Compose 只运行 API 容器，挂载 `shopilot_data` 到配置的数据目录。SQLite/JSONL 保持与当前 Harness 一致，避免为了本地启动引入数据库服务。健康检查调用 live endpoint；ready 检查配置和数据目录可写。

### 4. API 生命周期和诊断

FastAPI 在应用启动时加载 settings、创建 store、runtime factory 和 workflow。统一异常 handler 返回 `{error_code, message, request_id}`；日志使用 JSON，敏感配置只记录 provider/model 和 mode。

### 5. UI 作为观察层

继续使用服务端返回的最小 HTML/JS，不添加独立前端构建链。UI 调用既有 API；scenario 列表来自 Harness registry；按钮状态由 run status 和 approval 状态决定。

### 6. Verification commands

提供 `make` 等价的 PowerShell/CLI 命令：安装、离线测试、启动、健康检查、scenario 全量评估和真实 provider smoke。真实 provider smoke 默认不执行发布，需显式开启且仍受 side-effect gate 保护。

## Risks / Trade-offs

- [Docker daemon 权限或 Windows named pipe 不可用] -> 文档提供 host Python fallback，并让容器检查失败时输出明确诊断。
- [不同 OpenAI-compatible provider 的模型协议差异] -> provider factory 显式记录配置；只保证标准 chat/structured output 能力。
- [文件存储并发能力有限] -> 本地 MVP 明确单实例限制，未来升级数据库时保持 Store 接口不变。
- [真实 API key 泄露] -> `.env` gitignore、日志脱敏、健康响应只返回 boolean/config error code。

## Migration Plan

保留现有 mock CLI/API 行为，新增 settings-aware app 作为推荐入口。首次启动创建数据目录；已有 `.shopilot` 数据可通过 `SHOPILOT_DATA_DIR` 指向原路径。回滚时继续运行 host Python 入口，不需要数据迁移。

## Open Questions

无。provider 默认值、容器形态、存储策略和 UI 方案已在本设计中确定。
