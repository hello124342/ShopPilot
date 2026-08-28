## Purpose

为本地开发和演示提供一套可配置、可持久化、可诊断的 ShopPilot 运行时，使用户只需配置模型密钥即可启动 mock 或真实 Agno 模式。

## ADDED Requirements

### Requirement: Environment configuration
系统 SHALL 从环境变量或 `.env` 文件读取运行模式、模型 provider、模型名称、API base URL、API key、数据目录、日志级别和副作用模式，并提供无密钥的 mock 默认值。

#### Scenario: Mock startup without key
- **WHEN** 用户未配置模型 API key 且选择 mock 模式
- **THEN** 服务 SHALL 成功启动并使用本地 deterministic fixture，不访问外部模型

#### Scenario: Agno startup without key
- **WHEN** 用户选择 agno 模式但缺少所需 API key
- **THEN** 服务 SHALL 返回明确的配置错误，不静默降级为 mock

### Requirement: Agno provider execution
系统 SHALL 通过 Agno 的 Agent、Team 和 Workflow 原语执行真实模式，并将 provider 错误作为可追踪的运行失败。

#### Scenario: Run with configured provider
- **WHEN** provider、model 和 API key 配置有效
- **THEN** 系统 SHALL 实例化预注册的 Agno primitives 并记录 provider/model 版本

#### Scenario: Provider failure
- **WHEN** 外部模型返回认证、限流或超时错误
- **THEN** 系统 SHALL 保留错误类型和重试信息，并进入 failed 或 human_handoff 状态

### Requirement: Container startup
系统 SHALL 提供单一 Docker Compose 启动方式，包含健康检查、非 root 运行用户、配置注入和数据卷。

#### Scenario: Start stack
- **WHEN** 用户执行 Compose 启动命令
- **THEN** API 容器 SHALL 启动并在 `/health/live` 返回 200，配置错误时 `/health/ready` SHALL 返回非 200 和可读原因

### Requirement: Persistent local data
系统 SHALL 将 run、artifact、trace、approval 和 evaluation 写入可配置目录，并在容器重启后保留。

#### Scenario: Restart container
- **WHEN** API 容器重启且数据卷未删除
- **THEN** 既有 run 和 evaluation SHALL 仍可通过 API 查询

### Requirement: Runtime health and diagnostics
系统 SHALL 暴露 live、ready 健康检查和不泄露密钥的运行诊断信息。

#### Scenario: Health check
- **WHEN** 用户请求健康检查
- **THEN** live 只反映进程可用性，ready 反映配置、存储和 Agno provider 可用性；响应不得包含 API key

### Requirement: Operations UI
系统 SHALL 提供最小 UI 以选择 scenario、创建 run、查看状态/artifact/trace/evaluation、审批/拒绝和 replay。

#### Scenario: Review a run
- **WHEN** 用户打开首页并创建 canonical run
- **THEN** 用户 SHALL 能在同一界面看到当前状态、合规结果并完成批准、拒绝或 replay

### Requirement: Deployment verification
系统 SHALL 提供依赖安装、单元测试、容器 smoke test 和真实 provider 可选验证命令。

#### Scenario: Verify installation
- **WHEN** 用户执行项目验证命令
- **THEN** 命令 SHALL 输出测试结果、健康检查结果和 provider 模式，不得要求真实发布权限
