# Spec Delta

## Purpose

Provide one acceptance contract that binds requirements, executable scenarios, CI checks and review
findings to the same IDs and severity policy.

## ADDED Requirements

### Requirement: Requirements have stable IDs and verification targets

Every behavior requirement MUST have a unique ID, a severity, an owner and at least one existing
verification target.

#### Scenario: A missing verification target fails the contract
- **WHEN** a requirement's verification path does not exist
- **THEN** the contract gate fails and names the requirement

### Requirement: P0 requirements have executable scenarios

Every P0 requirement in the changed scope MUST have at least one Gherkin scenario tagged with its ID,
and that scenario MUST pass in the BDD job.

#### Scenario: A P0 requirement without a scenario is blocked
- **WHEN** a P0 requirement has no `@req:` scenario
- **THEN** the contract gate fails

### Requirement: Review findings carry requirement and severity

A design-review finding MUST carry a requirement ID when it is P0; P1 and P2 findings without an ID
are advisory. P0 findings block; P1 findings become follow-ups; P2 findings are advisory.

#### Scenario: A failed gate cannot be turned into a pass
- **WHEN** the agent job did not succeed
- **THEN** the publication decision is block regardless of a report claiming pass

### Requirement: Gate capabilities are split

The agent job MUST NOT hold status, issue, pull-request or action write permission; a separate
publish job MUST hold status and issue write permission and MUST NOT execute pull-request code.

#### Scenario: The capability gate rejects a write-capable agent job
- **WHEN** the agent job has `statuses: write`
- **THEN** the capability gate fails
