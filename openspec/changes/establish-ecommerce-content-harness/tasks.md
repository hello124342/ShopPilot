## 1. Project foundation

- [x] 1.1 Create the Python package layout for agents, teams, workflows, tools, schemas, and harness modules; verify syntax with compileall
- [x] 1.2 Add Agno, Pydantic, SQLite/JSONL and test dependencies with pinned compatible versions; verify editable installation succeeds
- [x] 1.3 Define versioned configuration for model, prompt, scenario, fixture, policy, and side-effect mode; verify configuration is attached to the workflow runtime

## 2. Domain contracts and fixtures

- [x] 2.1 Define schemas for CampaignInput, ResearchPackage, CampaignBrief, CreativePackage, PlatformPayload, ComplianceReport, PerformanceReport, and OptimizationBrief; verify model validation declarations compile
- [x] 2.2 Create deterministic product, brand policy, platform policy, market research, and metrics fixtures; verify the scenario code has no network dependency
- [x] 2.3 Implement versioned artifact persistence and source/evidence references; verify JSONL store preserves append-only versions

## 3. Agents and team composition

- [x] 3.1 Implement fixed Research Team members for product, competitor, audience, trend, and evidence review; verify output model contains sources, confidence, and conflicts
- [x] 3.2 Implement Strategy Agent producing a validated Campaign Brief; verify output is typed and evidence-linked
- [x] 3.3 Implement Copy Agent, Visual Brief Agent, and Video Script Agent producing creative variants; verify each variant contains angle, evidence references, and target metric
- [x] 3.4 Implement Platform Adapter Agent plus deterministic platform validators; verify length, media count, format, and prohibited-expression checks are present
- [x] 3.5 Implement Compliance Agent and deterministic fact/policy validators; verify policy failures enter revision_required state
- [x] 3.6 Implement Analytics Agent and Optimization Agent; verify typed output separates facts, hypotheses, actions, and success metrics

## 4. Workflow, approval, and side effects

- [x] 4.1 Implement the fixed Campaign Workflow using the selected Agno primitives and stage transitions; verify the happy-path path is represented by run plus approval/analyze methods
- [x] 4.2 Implement schema-failure, timeout, retry-budget, partial-failure, cancellation, and human-handoff paths; verify each failure is represented in run state and trace
- [x] 4.3 Implement approval state machine with immutable approval events; verify rejection creates a new revision and cannot publish the rejected version
- [x] 4.4 Implement mock Publish Tool with approval/version checks and idempotency keys; verify unapproved and duplicate publish calls are safely rejected by unit-level logic
- [x] 4.5 Implement mock metrics ingestion and deterministic metric calculations (CTR, CVR, CPA, ROAS); verify formulas are encoded against known fixture values

## 5. Harness observability and evaluation

- [x] 5.1 Record run, step, model/prompt version, artifact, approval, and error trace events; verify chronological correlation is represented by sequence fields
- [x] 5.2 Implement scenario replay with side effects disabled; verify replay creates a comparable run and never invokes real external publishing
- [x] 5.3 Implement deterministic evaluators for schema, evidence, facts, policy, tool use, approval gate, completion, latency, and cost; verify JSON evaluation reports are generated
- [x] 5.4 Add optional LLM-judge evaluation as a supplemental score without overriding deterministic failures; verify a deterministic failure remains a failure
- [x] 5.5 Add failure-injection controls for tool timeout, invalid output, approval rejection, and duplicate publish; verify expected recovery or safe-failure behavior
- [x] 5.6 Create at least five happy-path and five failure-path scenarios and run them in CI; verify exit code and report artifacts are stable

## 6. API and demonstration surface

- [x] 6.1 Expose API/CLI commands to create a run, inspect artifacts and trace, approve/reject, replay, and evaluate; verify endpoint definitions compile
- [x] 6.2 Build a minimal campaign/run inspection view showing artifacts, approval state, trace, and evaluation results; verify API integration test follows one run end to end
- [x] 6.3 Document MVP boundaries, primitive-selection rationale, fixture limitations, and the path to real platform adapters; verify README matches the evaluated behavior

## 7. Quality and handoff

- [x] 7.1 Run the complete test and evaluation suite with network disabled; verify all required scenarios pass and failures are explainable
- [x] 7.2 Review security and side-effect controls, including secrets handling, prompt-injection inputs, and publish authorization; verify no unapproved side effect is possible
- [x] 7.3 Produce a short benchmark comparing Research Team against a single-agent baseline on quality, latency, cost, and evidence coverage; verify the Team choice is evidence-backed
