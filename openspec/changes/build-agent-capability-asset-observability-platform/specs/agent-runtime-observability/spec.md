# Agent Runtime Observability Specification

## ADDED Requirements

### Requirement: End-to-end hierarchical tracing

The system SHALL correlate Campaign, Workflow stage, Team, member Agent, model, Skill, Tool/MCP, external request, Artifact, Evidence, and Asset activity in one hierarchical trace.

#### Scenario: Team member tool call

- **WHEN** a Team member Agent calls an MCP Tool
- **THEN** the resulting span SHALL identify its Campaign run, Workflow stage, Team run, member run, Agent/version, MCP Server, Tool/version, and parent span

### Requirement: Agno event bridge

The system SHALL consume supported Agno Agent, Team, Workflow, member, model, and Tool events and map them into a stable ShopPilot canonical event model.

#### Scenario: Agno tool event received

- **WHEN** Agno emits Tool started, completed, or failed events
- **THEN** the bridge SHALL preserve Agno correlation identifiers
- **AND** SHALL add ShopPilot run, tenant, policy, Artifact, Evidence, and Asset associations when available

### Requirement: First-party audit with vendor telemetry disabled

The system SHALL retain first-party operational and audit events independently of external vendor telemetry configuration.

#### Scenario: Vendor telemetry disabled

- **WHEN** Agno vendor telemetry is disabled
- **THEN** ShopPilot SHALL continue to record authorized first-party runtime events and metrics

### Requirement: Model and tool metrics

The system SHALL capture available token, cost, latency, retry, status, and provider request metadata for model and tool calls.

#### Scenario: Model call completes

- **WHEN** a model call completes
- **THEN** the trace SHALL record the available input/output/cached token counts, duration, model/provider, estimated cost, and completion status

### Requirement: Sensitive data redaction

The system SHALL apply field-level allowlists and redaction before Trace data is persisted or returned by APIs.

#### Scenario: Secret appears in tool input

- **WHEN** a Tool input contains a credential or configured sensitive value
- **THEN** the persisted and displayed event SHALL contain only a redacted representation

### Requirement: Observable retries and failures

The system SHALL represent each retry attempt and its terminal outcome without overwriting earlier attempts.

#### Scenario: MCP timeout exhausts retry budget

- **WHEN** an MCP Tool times out until its retry budget is exhausted
- **THEN** the trace SHALL contain each attempt, retry decision, terminal error, and resulting Workflow state

### Requirement: Trace-linked replay

The system SHALL create a new trace for every replay and link it to the source run and recorded dependencies.

#### Scenario: Recorded replay created

- **WHEN** a recorded replay starts
- **THEN** it SHALL receive a new run ID and trace ID
- **AND** SHALL identify the source run, reused Tool outputs, Evidence, Artifacts, and Assets

### Requirement: Operational run graph

The system SHALL expose a queryable run graph and aggregate operational metrics to authorized users.

#### Scenario: Operator inspects failed run

- **WHEN** an operator opens a failed run
- **THEN** the UI SHALL show the failed span in its Team/Agent/Tool hierarchy, redacted inputs and outputs, retries, latency, and linked artifacts

