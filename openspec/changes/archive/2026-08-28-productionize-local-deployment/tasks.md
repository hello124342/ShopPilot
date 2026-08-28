## 1. Runtime configuration

- [x] 1.1 Add Pydantic Settings with `SHOPILOT_*` environment variables and safe defaults; verify mock starts without a key and Agno mode fails clearly without one
- [x] 1.2 Add `.env.example`, `.gitignore` rules, and configuration documentation; verify no secret value is tracked or emitted in diagnostics
- [x] 1.3 Refactor app/workflow construction to use one settings object and configurable data directory; verify existing mock tests still pass

## 2. Agno provider integration

- [x] 2.1 Implement OpenAI-compatible Agno model factory from provider/model/base URL/API key settings; verify configured values reach Agno without logging the key
- [x] 2.2 Wire real Agno Agents, Research Team, and Campaign Workflow behind `runtime_mode=agno`; verify a provider smoke run records model/provider metadata
- [x] 2.3 Add provider authentication, timeout, rate-limit, and structured-output error mapping; verify failures become traceable failed or human_handoff runs

## 3. Persistence and operations

- [x] 3.1 Make RunStore create and use the configured data directory with append-only artifacts, trace, approvals, and evaluations; verify data survives process restart
- [x] 3.2 Add structured logging with request/run correlation and secret redaction; verify logs contain mode/status but never API key values
- [x] 3.3 Add `/health/live`, `/health/ready`, and safe runtime diagnostics; verify readiness distinguishes mock, valid Agno config, and missing-key states
- [x] 3.4 Add unified API error responses with request IDs; verify missing runs, invalid payloads, and provider failures return stable error codes

## 4. Container delivery

- [x] 4.1 Create a non-root multi-stage Dockerfile with pinned dependency installation and a production Uvicorn entrypoint; verify image builds successfully
- [x] 4.2 Create Docker Compose with environment injection, data volume, healthcheck, restart policy, and localhost port mapping; verify `docker compose config` is valid
- [x] 4.3 Add PowerShell and cross-platform startup/verification commands; verify mock stack can be started and health-checked without API keys
- [x] 4.4 Verify persistence across container restart using the named volume; verify existing run IDs remain queryable

## 5. UI and API completion

- [x] 5.1 Add run list/detail views with runtime mode, status, artifacts, compliance, trace, and evaluation output; verify UI handles loading and error states
- [x] 5.2 Add scenario selector and actions for create, approve, reject, replay, and evaluate; verify action availability follows run state and approval gate
- [x] 5.3 Add API integration tests for all documented endpoints and health checks; verify no endpoint can publish without approval

## 6. Verification and documentation

- [x] 6.1 Add five happy-path and five failure-path container-compatible scenario checks; verify each writes evaluation JSON
- [x] 6.2 Add offline test command and optional real-provider smoke command; verify offline tests never access the network
- [x] 6.3 Run Python, package-install, API, and Docker smoke verification; record known Docker daemon prerequisites and fallback host-Python command
- [x] 6.4 Update README and development docs with only-required user configuration, Agno setup, runtime modes, persistence, troubleshooting, and real-platform adapter boundary
