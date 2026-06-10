// @ts-check
const { defineConfig, devices } = require('@playwright/test');

/**
 * Live-server config — runs against the QNAP stack at 192.168.68.108:9443.
 *
 * No webServer block: we don't start Odoo, we drive the running instance.
 * The QNAP cert is self-signed → ignoreHTTPSErrors:true.
 *
 * Hostname matters: Caddy routes by Host header. Use the IP and override
 * with a Host header via extraHTTPHeaders for the public site, OR use
 * the .space domain when DNS is reachable.
 */
module.exports = defineConfig({
  testDir: './tests',
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  retries: 0,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    // Caddy's configured vhost is southbrookcabinetry.local, NOT .space.
    // The .space domain is the public Cloudflare-tunnel entry — when
    // cloudflared forwards to QNAP it rewrites Host to .local. From LAN
    // we have to use the .local hostname directly so Caddy matches the
    // right reverse_proxy block; otherwise the request falls through to
    // a default vhost and Odoo's dbfilter rejects with "Database not
    // found." Chromium's --host-resolver-rules maps the hostname to
    // the QNAP IP at the network stack so we don't need /etc/hosts.
    baseURL: process.env.SB_BASE_URL || 'https://southbrookcabinetry.local:9443',
    ignoreHTTPSErrors: true,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    launchOptions: {
      args: [
        '--host-resolver-rules=MAP southbrookcabinetry.local 192.168.68.108',
        '--ignore-certificate-errors',
      ],
    },
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
});
