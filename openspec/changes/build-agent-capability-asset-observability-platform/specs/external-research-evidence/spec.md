# External Research Evidence Specification

## ADDED Requirements

### Requirement: Traceable external evidence

The system SHALL normalize every externally acquired research fact into an EvidenceRecord with a stable ID, source, retrieval timestamp, content hash, collector, and originating tool call.

#### Scenario: Web evidence collected

- **WHEN** a Research Agent obtains content from search or browser extraction
- **THEN** the system SHALL persist its source URL, excerpt, retrieval time, content hash, Agent identity, and Tool call identity

### Requirement: Evidence-backed research output

The system SHALL require research conclusions to reference EvidenceRecord IDs and SHALL report citation coverage.

#### Scenario: Unsupported conclusion

- **WHEN** a ResearchPackage contains a material external claim without a valid EvidenceRecord reference
- **THEN** business-rule evaluation SHALL fail that claim
- **AND** SHALL prevent silent promotion as verified evidence

### Requirement: Conflict preservation

The system SHALL detect and preserve conflicting evidence rather than silently selecting a preferred statement.

#### Scenario: Conflicting sources

- **WHEN** normalized evidence contains incompatible claims about the same subject
- **THEN** the Evidence Reviewer SHALL mark the conflict, identify participating evidence IDs, and assign an explicit resolution status

### Requirement: Untrusted content boundary

The system SHALL treat search results, web pages, uploaded content, and MCP responses as untrusted data.

#### Scenario: Instruction found in web content

- **WHEN** external content contains text attempting to modify system instructions, permissions, credentials, or tool behavior
- **THEN** the system SHALL mark it as suspected prompt injection
- **AND** SHALL NOT apply it as an instruction or policy

### Requirement: Safe browser and network access

The system SHALL enforce URL scheme, redirect, response size, content type, timeout, and private-network restrictions for research browsing.

#### Scenario: Private network target

- **WHEN** a browser or extraction request resolves to a blocked local or private network destination
- **THEN** the request SHALL be rejected and audited

### Requirement: Recorded research replay

The system SHALL replay external research from recorded normalized results by default.

#### Scenario: Offline replay

- **WHEN** a run is replayed in recorded mode
- **THEN** no search, browser, MCP, or external data request SHALL be executed
- **AND** the new run SHALL retain links to the original evidence records

