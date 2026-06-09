// SPDX-License-Identifier: LGPL-3.0-only
//
// SAMI / Southbrook Playwright config.
//
// Default target is the local dev stack at http://localhost:8169.
// Override with SAMI_URL=… to point at any deployment (e.g.
// SAMI_URL=https://southbrookcabinetry.space for prod smoke).

import { defineConfig, devices } from "@playwright/test";

const baseURL = process.env.SAMI_URL || "http://localhost:8169";

export default defineConfig({
  testDir: ".",
  timeout: 30_000,
  expect: { timeout: 5_000 },
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 2 : undefined,
  reporter: process.env.CI ? "github" : "list",
  use: {
    baseURL,
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
    // Public site uses Let's Encrypt + Cloudflare; trust real certs.
    // Local stack uses Odoo's bundled cert OR runs on http://. Either way
    // ignore TLS errors for the smoke target — the test is not validating
    // the TLS chain.
    ignoreHTTPSErrors: true,
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
