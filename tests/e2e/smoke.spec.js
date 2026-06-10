// SPDX-License-Identifier: LGPL-3.0-only
//
// SAMI / Southbrook smoke gate.
//
// Eight tests covering the surfaces that have failed in production before
// (asset bundles, public-facing routes, /api/v1 contract shape). Each is
// fast, network-only, and does not require a logged-in session.
//
// To exercise login + portal pages, see the (out-of-scope) `journey.spec.js`
// once test credentials are wired through env.

import { test, expect } from "@playwright/test";

const SCHEMA = "southbrook.flutter.api.v1";

// ---------------------------------------------------------------------------
// Public surfaces — these MUST render without 500 on every deploy.
// ---------------------------------------------------------------------------
test("/web/login renders without a server error", async ({ page }) => {
  // The asset-bundle circular include bug that surfaced on the 2026-06-09
  // QNAP deploy crashed THIS exact URL with 500. Run this test on every
  // push to catch any future asset-bundle regression before deploy.
  const resp = await page.goto("/web/login");
  expect(resp).not.toBeNull();
  expect(resp.status()).toBe(200);
  // Form must be present — confirms the page actually rendered.
  await expect(page.locator('form[action*="/web/login"]')).toBeVisible();
  // No JS console errors should fire during the initial render.
  // (We collect them in a beforeEach below.)
});

test("/web/database/selector or login redirects sensibly", async ({ page }) => {
  // GET /web/ should not 500 — typical behaviour is a redirect to the
  // database selector or login.
  const resp = await page.goto("/web/");
  expect(resp.status()).toBeLessThan(500);
});

// ---------------------------------------------------------------------------
// Portal routes — must require auth, must redirect anon traffic to login.
// ---------------------------------------------------------------------------
test("/my/kitchen-projects redirects anon to login", async ({ page }) => {
  const resp = await page.goto("/my/kitchen-projects", { waitUntil: "load" });
  // After the redirect chain, the URL must include /web/login.
  expect(page.url()).toContain("/web/login");
  expect(resp).not.toBeNull();
});

test("/my/dealer/orders blocked for anon", async ({ page }) => {
  // Either 401/403 (preferred) or redirect to login. Definitely not 500.
  const resp = await page.goto("/my/dealer/orders", { waitUntil: "commit" });
  expect(resp).not.toBeNull();
  const status = resp.status();
  const url = page.url();
  expect([200, 301, 302, 303, 401, 403]).toContain(status);
  // If 200, must be the login page (not the dealer dashboard).
  if (status === 200) {
    expect(url).toContain("/web/login");
  }
});

// ---------------------------------------------------------------------------
// REST API — health endpoint (no auth, for monitors + smoke).
// ---------------------------------------------------------------------------
test("/api/v1/health returns 200 + schema + status ok", async ({ request }) => {
  const resp = await request.get("/api/v1/health");
  expect(resp.status()).toBe(200);
  const body = await resp.json();
  expect(body.schema).toBe(SCHEMA);
  expect(body.status).toBe("ok");
  expect(body.service).toBe("southbrook_api");
  expect(body.api_version).toBe("v1");
});

// ---------------------------------------------------------------------------
// REST API — G6 contract shape on error envelopes.
// ---------------------------------------------------------------------------
test("/api/v1/me without X-Api-Key returns 401 + schema", async ({ request }) => {
  const resp = await request.get("/api/v1/me");
  expect(resp.status()).toBe(401);
  const body = await resp.json();
  expect(body.schema).toBe(SCHEMA);
  expect(body.error).toBe("invalid_api_key");
});

test("/api/v1/me with wrong key returns 401 + same schema", async ({ request }) => {
  const resp = await request.get("/api/v1/me", {
    headers: { "X-Api-Key": "0000000000000000000000000000000000000000000000000000000000000000" },
  });
  expect(resp.status()).toBe(401);
  const body = await resp.json();
  expect(body.schema).toBe(SCHEMA);
  expect(body.error).toBe("invalid_api_key");
});

test("/api/v1/auth/login with bad JSON returns 400 + schema", async ({ request }) => {
  const resp = await request.post("/api/v1/auth/login", {
    headers: { "Content-Type": "application/json" },
    data: "not json at all",
  });
  expect(resp.status()).toBe(400);
  const body = await resp.json();
  expect(body.schema).toBe(SCHEMA);
  expect(body.error).toBe("bad_json");
});

test("/api/v1/auth/login with wrong credentials returns 401", async ({ request }) => {
  const resp = await request.post("/api/v1/auth/login", {
    data: { email: "nonexistent.smoketest@example.com", password: "wrong-password" },
  });
  expect(resp.status()).toBe(401);
  const body = await resp.json();
  expect(body.schema).toBe(SCHEMA);
  expect(body.error).toBe("invalid_credentials");
});

// ---------------------------------------------------------------------------
// Console error guard — catch JS crashes that don't surface as HTTP 500.
// ---------------------------------------------------------------------------
test("/web/login renders without console errors", async ({ page }) => {
  const errors = [];
  page.on("pageerror", (err) => errors.push(err.message));
  page.on("console", (msg) => {
    if (msg.type() === "error") errors.push(msg.text());
  });
  await page.goto("/web/login", { waitUntil: "networkidle" });
  // Filter out a few non-bug errors Odoo emits that aren't ours:
  // - cookieStore is null (cookie-consent extension noise)
  // - Failed to load resource: anything 404 on optional assets
  const ours = errors.filter(
    (e) =>
      !e.includes("cookieStore") &&
      !e.includes("Failed to load resource") &&
      !e.includes("favicon"),
  );
  expect(ours, `Unexpected console errors:\n${ours.join("\n")}`).toEqual([]);
});
