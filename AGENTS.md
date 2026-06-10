# Repository Guidelines

## Project Structure & Module Organization

This repository contains Odoo 19 CE addons for Southbrook Cabinetry. Custom Southbrook modules live under `addons/southbrook_*`; bundled OCA configurator modules live under `addons/product_configurator*` and `addons/website_product_configurator`. Each addon follows standard Odoo layout: `models/`, `views/`, `controllers/`, `security/`, `data/`, `static/`, and `tests/`. Canonical design and operating context are in `README.md`, `CLAUDE.md`, `PUNCHLIST.md`, and `docs/`.

## Build, Test, and Development Commands

Install or update an addon in Odoo:

```bash
odoo --addons-path=/mnt/extra-addons,/usr/lib/python3/dist-packages/odoo/addons \
  -d <dbname> -i southbrook_estimating --stop-after-init --no-http
```

Run module tests with Odoo:

```bash
odoo -d <dbname> -u southbrook_estimating \
  --test-enable --test-tags /southbrook_estimating \
  --stop-after-init --no-http
```

For the QNAP deployment, use `system-docker compose` in `/share/CACHEDEV3_DATA/Container/southbrook`; regular `docker` may not see the live stack.

## Coding Style & Naming Conventions

Use Odoo conventions: 4-space Python indentation, snake_case model fields/methods, XML ids prefixed by the addon or feature area, and QWeb templates grouped by purpose. Keep OCA modules as close to upstream as possible; avoid mixing bundled snapshots with partial upstream changes. Put website assets under `static/src/js` and `static/src/scss`.

## Testing Guidelines

Tests live in each addon’s `tests/` package and should use Odoo’s test framework. Name files `test_*.py` and focus tests on business behavior: pricing, configurator state, portal endpoints, BoM/cut-list outputs, and view loading. When editing XML views, verify the target addon updates cleanly and smoke-test the affected menu/page.

## Commit & Pull Request Guidelines

Commit history uses conventional prefixes such as `fix(...)`, `docs:`, and numbered work markers like `P1` or locked-decision references. Keep commits scoped to one addon or behavior. PRs should include a concise summary, affected modules, test commands/results, deployment notes, and screenshots for website/UI changes.

## Security & Configuration Tips

Do not commit credentials, database passwords, production dumps, or local server notes. Production runs behind Cloudflare/Caddy and QNAP Container Station; confirm the target container and database before running module updates. For Odoo 19, prefer `<list>` over legacy `<tree>` in new views.
