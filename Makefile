# SAMI / Southbrook AI Kitchen Platform — local + CI targets.
#
# Every CI run + every local "does it all still pass?" sweep goes through
# this file so the two paths cannot diverge. Forgejo CI calls `make test`;
# you run `make test` on your laptop the same way.

.PHONY: help up down logs install install-fresh test test-quick test-bridge \
        test-mrp-command \
        bridge-build bridge-restart shell psql .check-env \
        e2e-install e2e e2e-prod e2e-smoke e2e-journey

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
DB ?= southbrook
DB_USER ?= odoo
PG_PASS = $(shell grep '^POSTGRES_PASSWORD=' .env 2>/dev/null | cut -d= -f2)

# All 9 SAMI addons that have @tagged southbrook tests. Comma-separated,
# no spaces (Odoo's -u/-i parser splits strictly on comma; spaces become
# extra positional args and crash the parser).
# CI must cold-install everything that runs in production, or it can't catch a
# break in a module it never loads (this is how the x_sbk_estimated_cost outage
# slipped through). This is the VALIDATED cold-installable subset (verified via
# a fresh `-i` on a throwaway DB). 3 deployed modules are still EXCLUDED because
# they do NOT cold-install today — each a real platform-health bug to fix, then
# add back here:
#   - southbrook_mrp_kitchen_workcenters    : source off-main (feature/mrp-kitchen-workcenters)
#   - southbrook_manufacturing_intelligence : source off-main
#   - southbrook_plm_productgraph            : depends on unvendored module product_graph_release
# (estimating_website + mrp_pm were re-added once the configurator currency-fix
#  view was made cold-install-safe — see that view's priority=1 fix.)
MODULES = southbrook_freecad_bridge,southbrook_hardware_catalog,southbrook_kitchen_workspace,southbrook_kitchen_mrp,southbrook_mrp_pm,southbrook_ai_design,southbrook_config_engine,southbrook_configurator_ux,southbrook_estimating,southbrook_estimating_website,southbrook_customer_portal,southbrook_dealer_portal,southbrook_api,southbrook_plm

# Odoo flags every command needs. The 8899/8902 port dodge is mandatory —
# --no-http alone does not stop the gevent worker from binding 8072.
ODOO_FLAGS = \
  --db_host=db --db_user=$(DB_USER) --db_password='$(PG_PASS)' \
  --stop-after-init --no-http \
  --http-port=8899 --gevent-port=8902 \
  --workers=0 --max-cron-threads=0

# ---------------------------------------------------------------------------
# Help
# ---------------------------------------------------------------------------
help:
	@echo "SAMI / Southbrook — common targets:"
	@echo ""
	@echo "  Stack lifecycle"
	@echo "    make up           — docker compose up -d"
	@echo "    make down         — docker compose down (keeps named volumes)"
	@echo "    make logs         — tail Odoo logs"
	@echo "    make shell        — bash inside sami-odoo"
	@echo "    make psql         — psql into the southbrook DB"
	@echo ""
	@echo "  Install / upgrade"
	@echo "    make install      — install (or upgrade) all 9 SAMI addons"
	@echo "    make install-fresh — drop the DB + reinstall from scratch"
	@echo ""
	@echo "  Tests"
	@echo "    make test         — full sweep (~30 s + 18 render-smoke renders)"
	@echo "    make test-quick   — same minus the render smoke (~2 s)"
	@echo "    make test-bridge  — just the bridge module's tests"
	@echo "    make test-mrp-command — MRP command center readiness tests"
	@echo ""
	@echo "  Bridge"
	@echo "    make bridge-build   — rebuild the freecad-bridge image"
	@echo "    make bridge-restart — restart freecad-bridge"
	@echo ""

# ---------------------------------------------------------------------------
# Pre-flight
# ---------------------------------------------------------------------------
.check-env:
	@test -f .env || (echo "ERROR: .env missing. cp .env.example .env" && exit 1)
	@test -n "$(PG_PASS)" || (echo "ERROR: POSTGRES_PASSWORD missing from .env" && exit 1)

# ---------------------------------------------------------------------------
# Stack
# ---------------------------------------------------------------------------
up: .check-env
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f odoo

shell: .check-env
	docker exec -it sami-odoo bash

psql: .check-env
	docker exec -it sami-postgres psql -U $(DB_USER) -d $(DB)

# ---------------------------------------------------------------------------
# Install / upgrade
# ---------------------------------------------------------------------------
install: .check-env
	docker exec sami-odoo odoo -d $(DB) -i $(MODULES) $(ODOO_FLAGS)

install-fresh: .check-env
	docker exec sami-postgres dropdb -U $(DB_USER) --if-exists --force $(DB)
	docker exec sami-postgres createdb -U $(DB_USER) $(DB)
	$(MAKE) install

# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
test: .check-env
	docker exec sami-odoo odoo -d $(DB) -u $(MODULES) \
	  --test-enable --test-tags=southbrook $(ODOO_FLAGS)

test-quick: .check-env
	docker exec sami-odoo odoo -d $(DB) -u $(MODULES) \
	  --test-enable --test-tags=southbrook,-render_smoke $(ODOO_FLAGS)

test-bridge: .check-env
	docker exec sami-odoo odoo -d $(DB) -u southbrook_freecad_bridge \
	  --test-enable --test-tags=southbrook_freecad_bridge $(ODOO_FLAGS)

test-mrp-command: .check-env
	docker exec sami-odoo odoo -d $(DB) -u southbrook_project \
	  --test-enable --test-tags=mrp_command/southbrook_project $(ODOO_FLAGS)

# ---------------------------------------------------------------------------
# Playwright E2E
# ---------------------------------------------------------------------------
e2e-install:
	cd tests/e2e && npm install && npx playwright install chromium

e2e: .check-env
	cd tests/e2e && npm test

e2e-prod:
	cd tests/e2e && SAMI_URL=https://southbrookcabinetry.space npm test

# Run just the anon smoke (skip journey even if SAMI_TEST_USER is set).
e2e-smoke: .check-env
	cd tests/e2e && npx playwright test smoke.spec.js

# Run just the authenticated journey (requires SAMI_TEST_USER + SAMI_TEST_PASS).
e2e-journey: .check-env
	cd tests/e2e && npx playwright test journey.spec.js

# ---------------------------------------------------------------------------
# Bridge
# ---------------------------------------------------------------------------
bridge-build: .check-env
	docker compose build freecad-bridge

bridge-restart: .check-env
	docker compose restart freecad-bridge
