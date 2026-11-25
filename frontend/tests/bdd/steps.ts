import assert from "node:assert/strict";

import { Given, Then, When } from "@cucumber/cucumber";

import { percent, usd } from "../../src/utils/format";

let cost = 0;
let formatted = "";

Given("a cost of {float} dollars", (value: number) => {
  cost = value;
});

When("the dashboard formats it", () => {
  formatted = usd(cost);
});

Then("the result is {string}", (expected: string) => {
  assert.equal(formatted, expected);
});

Then("a ratio of {float} formats as {string}", (value: number, expected: string) => {
  assert.equal(percent(value), expected);
});
