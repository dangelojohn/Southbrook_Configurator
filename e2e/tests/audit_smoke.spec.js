// @ts-check
const { test, expect } = require('@playwright/test');

/**
 * Audit Phase 2 browser smoke — drives the live QNAP configurator.
 *
 * Pre-reqs:
 *   - QNAP reachable on 192.168.68.108:9443
 *   - DNS for southbrookcabinetry.space mapped via --host-resolver-rules
 *     (set in playwright.config.js launchOptions)
 *   - Admin credentials via SB_ADMIN_LOGIN / SB_ADMIN_PASSWORD
 *
 * What this verifies:
 *   1. /web/login renders, admin login lands on /odoo (or /web)
 *   2. opening SB-BASE-1DR's configurator wizard shows 4 step labels
 *   3. Soft-Close appears as a value in the wizard
 *
 * Why two tests instead of four: each test pays a ~30-60s registry +
 * login cost on the live system. Bundling the wizard checks into one
 * test halves wall-clock for the same coverage.
 *
 * Why page.evaluate(fetch) instead of page.request.post: Playwright's
 * apiRequestContext uses Node's DNS resolver which resolves
 * southbrookcabinetry.space to the Cloudflare tunnel IP and times out
 * against the local QNAP. Chromium's resolver respects the
 * --host-resolver-rules flag we set, so a browser-side fetch reaches
 * the QNAP directly.
 */

const ADMIN_LOGIN = process.env.SB_ADMIN_LOGIN || 'admin';
const ADMIN_PASSWORD = process.env.SB_ADMIN_PASSWORD || 'admin';

async function login(page) {
  // Initial page-load so Chromium gets a session_id cookie to upgrade.
  await page.goto('/web/login');
  // Programmatic backend-scoped auth via /web/session/authenticate.
  // The website form login can leave the session in a website/portal
  // scope where /web/dataset/call_kw raises 'Session expired'; this
  // endpoint upgrades the session to an internal-user one.
  const authResult = await page.evaluate(
    async ({ login, password }) => {
      const res = await fetch('/web/session/authenticate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          jsonrpc: '2.0',
          method: 'call',
          params: { db: 'southbrook', login, password },
        }),
      });
      return await res.json();
    },
    { login: ADMIN_LOGIN, password: ADMIN_PASSWORD },
  );
  if (authResult.error) {
    throw new Error(`Login failed: ${JSON.stringify(authResult.error)}`);
  }
  // After auth, navigate to /odoo so subsequent UI assertions land on
  // the backend chrome.
  await page.goto('/odoo');
  await page.waitForURL(/\/(odoo|web)(\?|$|\/)/, { timeout: 20_000 });
}

/**
 * Browser-side RPC: runs inside Chromium so DNS resolution honors
 * the --host-resolver-rules flag and cookies from the page session
 * are sent automatically.
 */
async function rpc(page, { model, method, args = [], kwargs = {} }) {
  return await page.evaluate(
    async ({ model, method, args, kwargs }) => {
      const res = await fetch('/web/dataset/call_kw', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          jsonrpc: '2.0',
          method: 'call',
          params: { model, method, args, kwargs },
        }),
      });
      const json = await res.json();
      if (json.error) throw new Error(JSON.stringify(json.error));
      return json.result;
    },
    { model, method, args, kwargs },
  );
}

test.describe('Audit Phase 2 — live wizard smoke', () => {
  test('login + landing', async ({ page }) => {
    await login(page);
    await expect(page).toHaveURL(/\/(odoo|web)/);
    await expect(page.locator('body')).toBeVisible();
  });

  test('configurator wizard shows 4 audit step labels + Soft-Close', async ({ page }) => {
    test.setTimeout(180_000);
    await login(page);

    // Resolve SB-BASE-1DR product.template id via browser-side RPC.
    const tmpls = await rpc(page, {
      model: 'product.template',
      method: 'search_read',
      args: [[['default_code', '=', 'SB-BASE-1DR']], ['id', 'name']],
    });
    expect(tmpls.length, 'SB-BASE-1DR not found').toBeGreaterThan(0);
    const tmplId = tmpls[0].id;

    // Launch the OCA configurator wizard for that template. The action
    // expects active_id + active_model in the URL params.
    await page.goto(
      `/odoo/action-product_configurator.action_config_start?active_id=${tmplId}&active_model=product.template`,
      { waitUntil: 'domcontentloaded' },
    );

    // Wait for either a form view or modal dialog to render.
    await expect(
      page.locator('.o_form_view, .modal-dialog, .o_action_manager').first(),
    ).toBeVisible({ timeout: 30_000 });

    // The audit seeds 4 step buckets. They render as fieldset headers,
    // notebook tab labels, or step buttons depending on the OCA wizard
    // mode. We just verify the literal label string appears anywhere
    // on the rendered page — the audit's contract is "user sees these
    // four bucket names", not a specific widget chrome.
    const stepLabels = [
      'Construction & Sizing',
      'Door & Finish',
      'Hardware & Sides',
      'Interior & Accessories',
    ];
    for (const label of stepLabels) {
      await expect(
        page.getByText(label, { exact: false }).first(),
      ).toBeVisible({ timeout: 20_000 });
    }

    // Soft-Close (the post-audit default value on Accessories) must
    // also be visible somewhere on the wizard.
    await expect(page.getByText('Soft-Close', { exact: false }).first())
      .toBeVisible({ timeout: 20_000 });
  });
});
