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
    // Use the real hostname so Caddy's vhost routing fires; Chromium's
    // --host-resolver-rules maps it to the QNAP IP at the network stack
    // level (sidesteps the forbidden Host header override and the need
    // for a local /etc/hosts entry).
    baseURL: process.env.SB_BASE_URL || 'https://southbrookcabinetry.space:9443',
    ignoreHTTPSErrors: true,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    launchOptions: {
      args: [
        '--host-resolver-rules=MAP southbrookcabinetry.space 192.168.68.108',
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
