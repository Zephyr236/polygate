@acceptance @auth
Feature: Caller keys stay inside their allowlists

  @req:AUTH-001 @p0
  Scenario: A key cannot select a provider outside its allowlist
    Given a gateway with providers "a" and "b"
    And a client key "team-a" allowing only "a"
    When I evaluate the client policy for provider "a"
    Then the policy allows the provider
    When I evaluate the client policy for provider "b"
    Then the policy rejects the provider

  @req:AUTH-001 @p0
  Scenario: A client key cannot reuse another principal's secret
    Given a gateway with an admin token "admin-secret"
    And a client key whose resolved value is "admin-secret"
    When I build the gateway configuration
    Then configuration fails with a credential collision

  @req:CFG-001 @p1
  Scenario: An unprovisioned optional key does not take down legacy access
    Given a gateway with providers "a"
    And an unprovisioned optional client key
    And a legacy proxy key "legacy-secret"
    When I build the gateway configuration
    Then configuration succeeds

  @req:CFG-001 @p1
  Scenario: A fully unusable credential set fails startup
    Given a gateway with providers "a"
    And an unprovisioned optional client key
    When I build the gateway configuration
    Then configuration fails with no usable credential

  @req:AUTH-003 @p0
  Scenario: A generated key keeps its allowlist and tier policy
    Given a generated key record for tier "economy" allowing only "zen"
    When I resolve the generated key policy
    Then the generated policy rejects provider "amr"
    And the generated policy uses economy weights
