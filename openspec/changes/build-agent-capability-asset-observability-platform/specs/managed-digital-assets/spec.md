# Managed Digital Assets Specification

## ADDED Requirements

### Requirement: Artifact and Asset separation

The system SHALL represent structured business outputs as Artifacts and binary or file outputs as Assets connected through typed AssetReferences.

#### Scenario: Creative image output

- **WHEN** a Creative stage produces an image
- **THEN** the image SHALL be stored as an Asset
- **AND** the CreativePackage SHALL reference its stable Asset ID and immutable version rather than a filename-only string

### Requirement: Agno media storage reuse

The system SHALL evaluate and use Agno MediaStorage capabilities for Agent, Team, and Workflow media persistence when compatible with the selected storage backend.

#### Scenario: Supported media backend

- **WHEN** the pinned Agno version supports the required media persistence operation
- **THEN** ShopPilot SHALL use that operation
- **AND** SHALL limit custom code to business metadata, authorization, lineage, and lifecycle

### Requirement: Asset integrity and metadata

The system SHALL assign every Asset a stable ID and record MIME type, size, SHA-256 hash, storage location, status, version, owner, and creation provenance.

#### Scenario: Asset accepted into storage

- **WHEN** an Asset upload or generation completes
- **THEN** the system SHALL calculate and verify its integrity metadata before marking it ready

#### Scenario: Corrupt asset

- **WHEN** an Asset hash or media validation fails
- **THEN** the Asset SHALL NOT become ready
- **AND** SHALL enter failed or quarantined state with an audit event

### Requirement: Immutable lineage

The system SHALL preserve parent/derived relationships and generation parameters for transformed and generated Assets.

#### Scenario: Image variant generated

- **WHEN** a new image is derived from an existing product image
- **THEN** the lineage SHALL reference the parent Asset, creating Agent/Tool call, model, prompt version, and non-secret generation parameters

### Requirement: Version-bound approval

The system SHALL bind approval decisions to immutable Artifact and Asset versions.

#### Scenario: Asset changed after approval

- **WHEN** an approved Asset or its referencing Artifact receives a new version
- **THEN** the previous approval SHALL NOT authorize the new version

### Requirement: Controlled asset access

The system SHALL provide authorized metadata, preview, and download operations without exposing unrestricted storage paths.

#### Scenario: Asset download

- **WHEN** an authorized user requests a ready Asset
- **THEN** the system SHALL return it through a controlled endpoint or time-limited URL
- **AND** SHALL apply tenant and lifecycle policy

### Requirement: Asset retention and replay

The system SHALL apply configurable retention and shall reference existing recorded Assets during default replay.

#### Scenario: Recorded replay

- **WHEN** a run is replayed without live generation
- **THEN** the replay SHALL reference the recorded Asset version
- **AND** SHALL NOT invoke an external media generation provider

