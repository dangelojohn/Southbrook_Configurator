# SAMI E2E (Playwright)

Smoke tests run from a real headless Chromium. They catch the failure
modes that Odoo's HTTP test layer cannot — asset-bundle crashes, JS
console errors, redirect chains, and the G6 REST contract shape.

## Run

```bash
cd tests/e2e
npm install               # one-time
npm run install-browsers  # one-time, ~150 MB
npm test                  # against http://localhost:8169 (local stack)
npm run test:prod         # against https://southbrookcabinetry.space
```

`SAMI_URL=…` overrides the target; everything else falls back from
playwright.config.js.

The Makefile in the repo root has equivalents:

```bash
make e2e         # local stack
make e2e-prod    # prod
```

## What it covers

8 tests against the surfaces that have crashed in production before:

1. `/web/login` renders without a 500 (the asset-bundle circular-include
   bug that hit on 2026-06-09 — must never reach prod again).
2. `/web/` redirects sensibly (no 500).
3. `/my/kitchen-projects` redirects anonymous users to `/web/login`.
4. `/my/dealer/orders` blocks anon (401/403/302 acceptable; 500 not).
5. `/api/v1/me` without key returns 401 + G6 error envelope.
6. `/api/v1/me` with wrong key returns 401 + same envelope shape.
7. `/api/v1/auth/login` with malformed JSON returns 400 + `bad_json`.
8. `/api/v1/auth/login` with wrong credentials returns 401 +
   `invalid_credentials`.

Plus a 9th: `/web/login` renders without JS console errors (catches JS
crashes that don't surface as HTTP 500).

## Authenticated journey tests

`journey.spec.js` covers the surfaces anon smoke can't — full
/api/v1 round-trip and a real /web/login form submit.

The journey suite is **env-driven**:

```bash
export SAMI_TEST_USER='portal-test@example.com'
export SAMI_TEST_PASS='portal-test-strong-password'
npm test              # runs smoke + journey together
```

When the env vars are unset, every journey test cleanly skips. CI can
opt-in by injecting the two env vars as secrets.

### One-time setup: create the portal user

The journey suite needs a Southbrook portal user. Easiest path:

1. Log into the Odoo backend as admin.
2. Settings → Users & Companies → Users → Create.
3. Set name + email + password; under "Access Rights", grant only
   the Portal user-type group.
4. Optionally: create one `sb.kitchen.project` with `partner_id` set
   to that user's partner_id so `/api/v1/kitchen-projects` returns
   non-empty data.

### What it does NOT cover
- Three.js KitchenCanvas rendering (would need a project with seeded
  placement_data); covered by visual snapshot when that fixture lands.
- File downloads (installation PDF, quote PDF) — content-type sanity is
  enough at this layer; reportlab unit tests gate the content.

## CI

`.forgejo/workflows/tests.yml` calls `make e2e` after the Odoo backend
tests pass. When the Forgejo runner comes online, every push runs the
full sweep automatically.
