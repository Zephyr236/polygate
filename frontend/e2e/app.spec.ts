/**
 * Browser end-to-end tests against the built SPA served by vite preview.
 */

import { expect, test } from "@playwright/test";

import { apiKeyFixtures, metricsFixture, providerFixtures, healthFixtures } from "../tests/msw";

const TOKEN = "e2e-token";

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => window.localStorage.setItem("polygate.locale", "en"));
  await page.route("**/admin/auth/status", (route) => route.fulfill({ json: { configured: true } }));
  await page.route("**/admin/auth/login", (route) => route.fulfill({ json: { token: "e2e-session" } }));
  await page.route("**/admin/providers", async (route) => {
    if (route.request().method() === "PUT") {
      return route.fulfill({ json: { providers: providerFixtures } });
    }
    return route.fulfill({ json: { providers: providerFixtures, health: healthFixtures } });
  });
  await page.route("**/admin/metrics**", (route) => route.fulfill({ json: metricsFixture }));
  await page.route("**/admin/api-keys", async (route) => {
    if (route.request().method() === "POST") {
      const body = route.request().postDataJSON() as {
        name: string;
        tier: string;
        allowed_providers: string[];
      };
      return route.fulfill({
        json: {
          id: "key_e2e",
          name: body.name,
          prefix: "pg_e2esecret",
          tier: body.tier,
          allowed_providers: body.allowed_providers,
          token: "pg_e2esecret_token",
        },
      });
    }
    return route.fulfill({ json: { keys: apiKeyFixtures } });
  });
  await page.route("**/admin/api-keys/*", (route) => route.fulfill({ json: { ok: true } }));
  await page.route("**/admin/simulate", (route) =>
    route.fulfill({
      json: {
        model: "deepseek-v4.1-flash",
        prompt_length: 5,
        ranking: [
          { provider_id: "amr", success: 0.98, speed: 1, cost: 1, cache: 0.2, total: 0.94, priority: 1 },
        ],
        decisions: [{ provider_id: "amr", model: "m", eligible: true, reasons: [] }],
      },
    }),
  );
  await page.route("**/admin/playground", async (route) => {
    const body = route.request().postDataJSON() as { stream?: boolean };
    if (body.stream) {
      return route.fulfill({
        status: 200,
        contentType: "text/event-stream",
        body: 'data: {"choices":[{"delta":{"content":"PONG"}}],"model":"amr"}\n\ndata: [DONE]\n\n',
      });
    }
    return route.fulfill({
      json: {
        model: "amr",
        choices: [{ message: { content: "PONG" } }],
        usage: { prompt_tokens: 5, completion_tokens: 2 },
      },
    });
  });
});

test("dashboard shows provider cards and KPI totals", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("admin-password").fill(TOKEN);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByTestId("provider-amr")).toBeVisible();
  await expect(page.getByTestId("provider-zen")).toBeVisible();
  await expect(page.getByText("Traffic (calls per bucket)")).toBeVisible();
});

test("provider editor saves changes", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("admin-password").fill(TOKEN);
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.getByRole("button", { name: "Providers" }).click();
  await expect(page.getByRole("button", { name: "Save providers" })).toBeVisible();
  await page.getByLabel("toggle-provider-0").click();
  await page.getByLabel("priority-0").fill("3");
  await page.getByRole("button", { name: "Save providers" }).click();
  await expect(page.getByRole("button", { name: "Save providers" })).toBeEnabled();
});

test("routes simulation renders candidates", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("admin-password").fill(TOKEN);
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.getByRole("button", { name: "Routes" }).click();
  await page.getByRole("button", { name: "Simulate" }).click();
  await expect(page.getByText("Candidates")).toBeVisible();
  await expect(page.getByText("0.940")).toBeVisible();
});

test("generates a scoped API key and shows the secret once", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("admin-password").fill(TOKEN);
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.getByRole("button", { name: "API keys" }).click();
  await expect(page.getByTestId("api-key-key_alpha")).toBeVisible();
  await page.getByLabel("api-key-name").fill("Team E2E");
  await page.getByLabel("api-key-tier").selectOption("economy");
  await page.getByRole("option", { name: "provider-option-zen" }).click();
  await page.getByRole("button", { name: "Generate key" }).click();
  await expect(page.getByText("pg_e2esecret_token")).toBeVisible();
  await expect(page.getByText("Key generated")).toBeVisible();
});

test("playground runs a chat and shows the response", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("admin-password").fill(TOKEN);
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.getByRole("button", { name: "Playground" }).click();
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.getByTestId("playground-output")).toHaveText("PONG");
});
