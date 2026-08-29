# Agent Capability Governance Specification

## ADDED Requirements

### Requirement: Agno-native runtime capabilities

The system SHALL use capabilities provided by the pinned Agno version for Agent skills, tools, toolkits, MCP connectivity, media handling, and runtime events whenever those capabilities satisfy the requirement.

#### Scenario: Native capability exists

- **WHEN** an implementation task requires a runtime capability already supported by the pinned Agno version
- **THEN** the implementation SHALL integrate the Agno primitive through the runtime factory
- **AND** SHALL NOT introduce a parallel Agent runtime or protocol

#### Scenario: Native capability is insufficient

- **WHEN** the Agno capability cannot satisfy a ShopPilot business, governance, or persistence requirement
- **THEN** the implementation MAY add a narrow adapter
- **AND** SHALL document the exact gap, boundary, tests, and upgrade impact

### Requirement: Versioned capability catalog

The system SHALL maintain versioned definitions for Agents, Skills, Tools, and MCP Servers independently from provider credentials.

#### Scenario: Runtime construction

- **WHEN** an Agent or Team runtime is created
- **THEN** the factory SHALL resolve an explicit capability profile
- **AND** SHALL bind only the allowed Agno Skills, Tools, Toolkits, and MCPTools

### Requirement: Least-privilege authorization

The system SHALL authorize every capability by Agent or Team identity, tenant, environment, action, and side-effect class.

#### Scenario: Unauthorized tool request

- **WHEN** an Agent requests a Tool or MCP capability outside its allowlist
- **THEN** the system SHALL reject the call before external execution
- **AND** SHALL emit a redacted authorization-denied event

#### Scenario: Research capability

- **WHEN** a Research Agent executes in the initial production scope
- **THEN** it SHALL only receive read-only external capabilities
- **AND** SHALL NOT receive publish or external-write capabilities

### Requirement: Server-side credential references

The system SHALL keep provider and MCP credentials server-side and expose only credential references to configuration and runtime policies.

#### Scenario: Trace and artifact persistence

- **WHEN** prompts, events, artifacts, errors, or tool results are persisted
- **THEN** credentials and secret values SHALL be removed or redacted

### Requirement: Managed MCP lifecycle

The system SHALL allow only operator-configured MCP Servers and SHALL manage their validation, connection lifecycle, health, timeout, and failure state.

#### Scenario: Unregistered MCP server

- **WHEN** a user or Agent attempts to connect to an unregistered MCP Server
- **THEN** the system SHALL reject the connection

#### Scenario: MCP server failure

- **WHEN** an allowed MCP Server times out or becomes unhealthy
- **THEN** the system SHALL apply the declared retry/circuit-breaker policy
- **AND** SHALL surface the terminal failure in the run trace

### Requirement: Explicit research collaboration mode

The system SHALL express Research collaboration using explicit Agno Team and Workflow primitives rather than prompt-only concurrency instructions.

#### Scenario: Parallel collection

- **WHEN** a Research collection stage starts
- **THEN** the configured collector members SHALL execute with a verified Agno concurrency mechanism
- **AND** their outputs SHALL be independently identifiable

#### Scenario: Evidence review

- **WHEN** collection finishes
- **THEN** the Evidence Reviewer SHALL consume normalized stored evidence
- **AND** SHALL preserve unresolved conflicts in the ResearchPackage

