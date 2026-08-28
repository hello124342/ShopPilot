## Why

ShopPilot 当前可以在开发环境中运行，但仍需要手工安装依赖，运行配置没有统一环境契约，也缺少 Docker、持久化卷、健康检查和真实模型 provider 接线。需要把它完善为用户只填写模型 API Key 即可通过 Docker Compose 启动、验证和使用的本地完整交付。

## What Changes

- 增加 `.env.example` 和强类型 Settings，统一 runtime mode、provider、model、API Key、数据目录、日志与副作用配置。
- 增加 OpenAI-compatible provider，默认支持 OpenAI API Key，并允许配置兼容服务的 base URL 和 model id。
- 将真实 `agno` 模式接入已有 Agent/Team/Workflow factory；未配置 Key 时明确失败，`mock` 模式保持完全离线。
- 增加生产 Dockerfile、Docker Compose、非 root 用户、持久化数据卷、健康检查和一键启动命令。
- 将运行存储根目录配置化，并保证容器重启后 run、artifact、trace、approval 和 evaluation 数据可恢复。
- 增加 `/health/live`、`/health/ready`、安全配置检查、结构化日志和统一 API 错误响应。
- 完善 UI：运行模式可见、场景选择、运行列表、详情、审批、回放、评估和错误展示。
- 增加容器级 smoke test、Compose 验证、真实模型可选测试和操作文档。

## Capabilities

### New Capabilities

- `local-production-runtime`: 定义环境配置、真实模型 provider、Docker Compose 启动、持久化、健康检查、UI 和运行验证行为。

### Modified Capabilities

- 无。基础 harness capability 尚未归档到主 specs，本 change 以新增本地生产运行能力扩展现有实现。

## Impact

- 影响应用配置、Agno runtime factory、FastAPI 应用生命周期、持久化路径、Web UI 和 CLI。
- 新增 Dockerfile、Compose、环境模板、容器入口和部署文档。
- 用户必须提供的唯一敏感配置是所选模型 provider 的 API Key；默认 mock 模式无需 Key。
- MVP 仍不连接真实社交平台，不启用真实发布副作用。
