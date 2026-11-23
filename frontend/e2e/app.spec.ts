/**
 * Browser end-to-end tests against the built SPA served by vite preview.
 */

import { expect, test } from "@playwright/test";

import { metricsFixture, providerFixtures, healthFixtures } from "../tests/msw";

const TOKEN = "e2e-token";

test.beforeEach(async ({ page }) => {
  await page.route("**/admin/providers", async (route) => {
    if (route.request().method() === "PUT") {
      return route.fulfill({ json: { providers: providerFixtures } });
    }
    return route.fulfill({ json: { providers: providerFixtures, health: healthFixtures } });
  });
  await page.route("**/admin/metrics**", (route) => route.fulfill({ json: metricsFixture }));
  await page.route("**/admin/simulate", (route) =>
    route.fulfill({
      json: {
        model: "deepseek-v4.1-flash",
        prompt_length: 5,
        ranking: [{ provider_id: "amr", success: 0.98, speed: 1, cost: 1, cache: 0.2, total: 0.94, priority: 1 }],
        decisions: [{ provider_id: "amr", model: "m", eligible: true, reasons: [] }],
      },
    }),
  );
  await page.route("**/v1/chat/completions", async (route) => {
    const body = route.request().postDataJSON() as { stream?: boolean };
    if (body.stream) {
      return route.fulfill({
        status: 200,
        contentType: "text/event-stream",
        body: 'data: {"choices":[{"delta":{"content":"PONG"}}],"model":"amr"}\n\ndata: [DONE]\n\n',
      });
    }
    return route.fulfill({
      json: { model: "amr", choices: [{ message: { content: "PONG" } }], usage: { prompt_tokens: 5, completion_tokens: 2 } },
    });
  });
});

test("dashboard shows provider cards and KPI totals", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("admin-token").fill(TOKEN);
  await page.getByRole("button", { name: "Enter" }).click();
  await expect(page.getByTestId("provider-amr")).toBeVisible();
  await expect(page.getByTestId("provider-zen")).toBeVisible();
  await expect(page.getByText("Traffic (calls per bucket)")).toBeVisible();
});

test("provider editor saves changes", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("admin-token").fill(TOKEN);
  await page.getByRole("button", { name: "Enter" }).click();
  await page.getByRole("button", { name: "Providers" }).click();
  await expect(page.getByRole("button", { name: "Save providers" })).toBeVisible();
  await page.getByLabel("priority-0").fill("3");
  await page.getByRole("button", { name: "Save providers" }).click();
  await expect(page.getByRole("button", { name: "Save providers" })).toBeEnabled();
});

test("routes simulation renders candidates", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("admin-token").fill(TOKEN);
  await page.getByRole("button", { name: "Enter" }).click();
  await page.getByRole("button", { name: "Routes" }).click();
  await page.getByRole("button", { name: "Simulate" }).click();
  await expect(page.getByText("Candidates")).toBeVisible();
  await expect(page.getByText("0.940")).toBeVisible();
});

test("playground runs a chat and shows the response", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("admin-token").fill(TOKEN);
  await page.getByRole("button", { name: "Enter" }).click();
  await page.getByRole("button", { name: "Playground" }).click();
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.getByTestId("playground-output")).toHaveText("PONG");
});
