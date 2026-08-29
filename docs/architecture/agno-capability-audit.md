# Agno 3.0.1 Capability Audit

Audit date: 2026-08-28

## Supported Baseline

- Python is constrained to `>=3.12,<3.13`; local and container validation use Python 3.12.
- Agno is pinned to `agno[mcp,sqlite,website]==3.0.1`.
- Direct dependencies are exact pins in `pyproject.toml`; `uv.lock` is the transitive dependency record.
- Upgrade Agno only in an isolated change. Regenerate the lock, run the Agno smoke suite, all offline and API tests, and the canonical live research scenario.
- Runtime primitives remain Agno-owned. ShopPilot adapters are allowed only for the documented governance, domain, persistence, and product gaps below.

## Executable Capability Matrix

| Need | Agno 3.0.1 primitive | Verified behavior | ShopPilot responsibility | Smoke |
|---|---|---|---|---|
| Skills | `Skills`, `LocalSkills`, `Agent.skills` | Native loading and Agent attachment | Versioned manifest and authorization | Load a local skill and run an Agent |
| Tools | `Agent.tools`, Team tools, `Toolkit`, hooks | Registration, filters, timeouts, caching and hooks | Descriptor, side-effect class and policy audit | Attach callable Toolkit to Agent |
| MCP | `MCPTools` | stdio/SSE/streamable HTTP, native session lifecycle, timeout and filters | Operator allowlist, credential references, health, retry and circuit state | Initialize allowlisted fake protocol session offline |
| Team | `Team`, `TeamMode.broadcast`, `arun` | Broadcast `arun` runs members concurrently | Fixed research topology and normalized outputs | Execute broadcast Team with offline Model |
| Workflow | `Workflow`, `Step`, `Parallel` | Native steps, parallel execution and typed streaming events | Fixed campaign stages, approvals and transitions | Execute Workflow and assert event sequence |
| Media | `MediaStorage`, `AsyncMediaStorage`, `LocalMediaStorage` | Atomic local upload/download/exists/delete; local signed URL unavailable | Catalog, hashes, ACL, lineage, quota and lifecycle | Byte round trip and delete |
| Events | Agent/Team/Workflow run event enums | Model, tool, member, step and workflow events include run IDs | Canonical mapping, redaction, retention and domain links | Workflow event stream |
| Metrics | `RunMetrics` and run output metrics | Tokens, cache, reasoning, duration and optional cost | Price policy, aggregation and SLOs | Construct and preserve metric fields |
| Session storage | `agno.db`, `SqliteDb`, Agent/Team/Workflow sessions | Agno 3.0.1 uses `agno.db`, not legacy `agno.storage` | Tenant boundaries and domain indexes | SQLite session upsert/read |

The executable gate is `tests/test_agno_capabilities.py`. It is offline and requires no provider key.

## Required Thin Adapters

1. Capability governance. Agno attaches primitives but does not provide ShopPilot's versioned registry, tenant/environment rules, side-effect policy, or denial audit. These belong around the runtime factory and tool hooks.
2. MCP operations. `MCPTools` owns MCP protocol and connections. ShopPilot adds only configured-server allowlisting, server-side credential resolution, health state, bounded retry/circuit behavior, and trace records.
3. Research egress. Provider tools do not implement ShopPilot's SSRF, redirects, response-size, content-type, sanitization, deduplication, or prompt-injection rules. A read-only wrapper must enforce them before Evidence reaches Agents.
4. Research topology. The old runtime put the Evidence Reviewer in an implicit Team with collectors. The target uses explicit concurrent collection followed by an isolated reviewer that reads normalized Evidence only.
5. Assets. Agno MediaStorage persists bytes and runtime media references; it is not an Asset Catalog. ShopPilot owns stable IDs, content addressing, immutable versions, lineage, approvals, ACL, quarantine, quota, and retention.
6. Observability. Agno emits typed events and metrics. ShopPilot maps them into a stable Campaign hierarchy, redacts sensitive values, links Evidence/Artifacts/Assets, stores query indexes, and optionally exports OpenTelemetry.
7. Domain persistence. Agno session storage remains the Agent/Team/Workflow history store. Evidence, Asset, and canonical Trace indexes are ShopPilot domain data linked by Agno run/session IDs.
8. Replay. Agno history alone does not enforce recorded-only, no-network, no-side-effect replay. The harness applies those gates before capability construction.

## Upgrade and Removal Strategy

All Agno integration is centralized under `shopilot/runtime`. On upgrade, compare public signatures and event enums against this matrix. Remove an adapter when Agno natively satisfies the same contract and the replacement passes contract tests. Stored canonical IDs and legacy reads remain stable even if Agno event types change.
