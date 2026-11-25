@acceptance @gate
Feature: The design gate cannot review or publish the wrong result

  @req:GATE-002 @p0
  Scenario: A stale CI completion does not review the current head
    Given the tested head is "head-1"
    And the current PR head is "head-2"
    When I resolve the review target
    Then the review target is empty

  @req:GATE-002 @p0
  Scenario: The tested head is reviewed when it is still current
    Given the tested head is "head-2"
    And the current PR head is "head-2"
    When I resolve the review target
    Then the review target is "head-2"

  @req:GATE-003 @p1
  Scenario: An older completion cannot overwrite a newer final verdict
    Given a newer final status was created after my run started
    When I check whether publication is superseded
    Then publication is skipped

  @req:GATE-004 @p0
  Scenario: The agent job has no write capability
    Given the checked-in design-gate workflow
    When I inspect its capabilities
    Then the agent job has no write permissions
    And the publish job has the write permissions

  @req:GATE-005 @p0
  Scenario: A failed agent job cannot publish a forged pass
    Given a forged pass report
    And the agent job result is "failure"
    When I apply the finding policy
    Then the gate decision is "block"

  @req:GATE-006 @p0
  Scenario: A gate publication failure is visible
    Given no report artifact
    When I apply the finding policy
    Then the gate decision is "block"
