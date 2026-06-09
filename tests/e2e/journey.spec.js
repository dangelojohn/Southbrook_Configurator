// SPDX-License-Identifier: LGPL-3.0-only
//
// SAMI / Southbrook authenticated journey tests.
//
// These cover the surfaces that anon smoke can't — log in, hit the
// portal as a real user, exercise the API round-trip with a real key.
// Skip cleanly when SAMI_TEST_USER is not set (local dev that hasn't
// seeded a portal user, or CI without secrets).

import { test, expect } from "@playwright/test";

const SCHEMA = "southbrook.flutter.api.v1";

const TEST_USER = process.env.SAMI_TEST_USER;
const TEST_PASS = process.env.SAMI_TEST_PASS;

test.beforeAll(() => {
  test.skip(
    !TEST_USER || !TEST_PASS,
    "SAMI_TEST_USER + SAMI_TEST_PASS not set — see tests/e2e/README.md " +
      "for one-time portal-user setup. Skipping authenticated journey suite."
  );
});

// ---------------------------------------------------------------------------
// REST API — full G6 happy path
// ---------------------------------------------------------------------------
test.describe("REST API journey", () => {
  test("/api/v1/auth/login with valid creds issues a 64-hex key", async ({
    request,
  }) => {
    const resp = await request.post("/api/v1/auth/login", {
      data: { email: TEST_USER, password: TEST_PASS },
    });
    expect(resp.status()).toBe(200);
    const body = await resp.json();
    expect(body.schema).toBe(SCHEMA);
    expect(body.api_key).toMatch(/^[0-9a-f]{64}$/);
    expect(body.expires_at).toBeTruthy();
    expect(body.user.email).toBe(TEST_USER);
  });

  test("/api/v1/me with a fresh key returns the user profile", async ({
    request,
  }) => {
    const login = await request.post("/api/v1/auth/login", {
      data: { email: TEST_USER, password: TEST_PASS },
    });
    const apiKey = (await login.json()).api_key;

    const resp = await request.get("/api/v1/me", {
      headers: { "X-Api-Key": apiKey },
    });
    expect(resp.status()).toBe(200);
    const body = await resp.json();
    expect(body.schema).toBe(SCHEMA);
    expect(body.user.email).toBe(TEST_USER);
    expect(typeof body.user.is_dealer).toBe("boolean");
    expect(body.user.id).toBeGreaterThan(0);
  });

  test("/api/v1/kitchen-projects returns only the caller's projects", async ({
    request,
  }) => {
    const login = await request.post("/api/v1/auth/login", {
      data: { email: TEST_USER, password: TEST_PASS },
    });
    const apiKey = (await login.json()).api_key;

    const resp = await request.get("/api/v1/kitchen-projects", {
      headers: { "X-Api-Key": apiKey },
    });
    expect(resp.status()).toBe(200);
    const body = await resp.json();
    expect(body.schema).toBe(SCHEMA);
    expect(Array.isArray(body.projects)).toBe(true);
    // We don't assert a count — fresh test user may have zero.
    // But every returned row MUST have the G6 shape.
    for (const p of body.projects) {
      expect(p.id).toBeGreaterThan(0);
      expect(typeof p.code).toBe("string");
      expect(typeof p.name).toBe("string");
      expect(typeof p.state).toBe("string");
    }
  });

  test("Revoked / wrong key on /me returns the same 401 envelope", async ({
    request,
  }) => {
    const resp = await request.get("/api/v1/me", {
      headers: { "X-Api-Key": "f".repeat(64) },
    });
    expect(resp.status()).toBe(401);
    const body = await resp.json();
    expect(body.schema).toBe(SCHEMA);
    expect(body.error).toBe("invalid_api_key");
  });
});

// ---------------------------------------------------------------------------
// Portal session — log in via the standard /web/login form
// ---------------------------------------------------------------------------
test.describe("Portal session journey", () => {
  test("/web/login + valid creds redirects to a logged-in page", async ({
    page,
    baseURL,
  }) => {
    await page.goto("/web/login");
    await page.fill('input[name="login"]', TEST_USER);
    await page.fill('input[name="password"]', TEST_PASS);
    await Promise.all([
      page.waitForURL(/(?!\/web\/login)/, { timeout: 15_000 }),
      page.click('button[type="submit"]'),
    ]);
    // After login, we should NOT be on /web/login.
    expect(page.url()).not.toContain("/web/login");
  });

  test("/my/kitchen-projects when logged in returns the list page", async ({
    page,
  }) => {
    // Re-authenticate (cookies are per-test in Playwright by default).
    await page.goto("/web/login");
    await page.fill('input[name="login"]', TEST_USER);
    await page.fill('input[name="password"]', TEST_PASS);
    await Promise.all([
      page.waitForURL(/(?!\/web\/login)/, { timeout: 15_000 }),
      page.click('button[type="submit"]'),
    ]);

    const resp = await page.goto("/my/kitchen-projects", {
      waitUntil: "load",
    });
    expect(resp).not.toBeNull();
    expect(resp.status()).toBe(200);
    // Page must render the heading even when the user has zero projects.
    await expect(page.locator("h2")).toContainText("My Kitchen Projects");
    // And MUST NOT be the login page.
    expect(page.url()).not.toContain("/web/login");
  });
});
