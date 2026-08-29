ShopPilot Platform Operations

Runtime modes

- mock: default, deterministic and offline; no API key required.
- agno: uses pinned Agno 3.0.1 Agent/Team/Workflow primitives. Set SHOPILOT_API_KEY; use SHOPILOT_BASE_URL for an OpenAI-compatible endpoint.
- recorded: replay forces mock runtime and disabled side effects, and reuses content-addressed evidence/assets.

Persistence

The local deployment stores run JSONL, Evidence SQLite, Asset Catalog SQLite, Trace SQLite, and Agno MediaStorage files below SHOPILOT_DATA_DIR. Docker maps this to the shopilot_data named volume. Back up the volume while the service is stopped. Schedule AssetService retention and TraceStore pruning, and monitor quota usage.

Security boundary

The browser extractor accepts only HTTP(S), rejects URL credentials, non-global DNS targets, non-allowlisted domains, unsafe redirects, oversized responses, and non-text MIME types. HTML scripts and active elements are removed. Suspected prompt injection is marked as data and never treated as instructions.

Asset downloads are served through API endpoints and never expose storage keys. Responses include nosniff, private caching, and restrictive CSP. Keep the app bound to localhost or place it behind an authenticated reverse proxy before exposing it to a network.

Agno primitive policy

Use native Agent, Team, Workflow, Skills, Toolkit, MCPTools, MediaStorage, streams, and metrics first. ShopPilot adapters are limited to capability governance, domain catalogs, security boundaries, evidence normalization, canonical trace persistence, and product APIs. Do not add a custom agent loop, scheduler, DAG engine, or MCP protocol.

Adding a capability

Add a versioned registry descriptor, profile reference, explicit side-effect class, timeout/retry/idempotency behavior, default-deny policy, and offline tests. Resolve secrets through CredentialReference; never put secret values in JSON config, traces, artifacts, or errors.

Delivery checklist

Run uv lock, uv run pytest tests -q, uv run python -m shopilot.cli scenarios, and docker compose config. Live provider smoke is opt-in, requires the user's API key, and must use disabled side effects.