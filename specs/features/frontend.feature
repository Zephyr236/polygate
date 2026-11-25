@acceptance @frontend
Feature: Dashboard formatting stays stable

  @req:TEST-001 @p1
  Scenario: Cost and ratio formatting is deterministic
    Given a cost of 0.00042 dollars
    When the dashboard formats it
    Then the result is "$0.000420"
    And a ratio of 0.125 formats as "12.5%"
