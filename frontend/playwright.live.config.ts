/**
 * Playwright configuration for the live Docker container smoke test.
 */

import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  testMatch: /live.spec.ts/,
  timeout: 120_000,
  reporter: [["list"]],
  use: { baseURL: "http://127.0.0.1:8080", trace: "retain-on-failure", screenshot: "only-on-failure" },
  projects: [{ name: "live", use: { ...devices["Desktop Chrome"], browserName: "chromium" } }],
});
