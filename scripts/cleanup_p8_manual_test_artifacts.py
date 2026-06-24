# SPDX-License-Identifier: LGPL-3.0-only
"""Cleanup orphan data left by the 2026-06-18 manual P8 scan E2E.

Removes:
  - sb.production.package id 23 (E2E-SCAN-TEST-MO85)
  - sb.production.package id 34 (E2E-SCAN-TEST-MO86)
  - sb.production.package id 36 (E2E-SCAN-TEST-MO88)
  - Resets prematurely-finished 'Cut Panels' WOs on WH/MO/00085,
    WH/MO/00086, and WH/MO/00088 to ready state (clears consumption
    rows, lifecycle latch, finish/start timestamps, qty_produced,
    duration).

Run via Odoo shell against the southbrook DB:

    docker exec -i southbrook-odoo odoo shell -d southbrook --no-http \\
        --http-port=8899 --gevent-port=8902 \\
        --workers=0 --max-cron-threads=0 \\
        < scripts/cleanup_p8_manual_test_artifacts.py

Idempotent — running it twice is a no-op the second time.
"""
TEST_PACKAGE_IDS = [23, 34, 36]
RESET_MO_NAMES = ["WH/MO/00085", "WH/MO/00086", "WH/MO/00088"]
RESET_OPERATION_NAME = "Cut Panels"

# Package cleanup — capture FK targets first so ondelete=restrict on
# cutlist/hardware_package doesn't block the unlink.
test_packages = env["sb.production.package"].browse(TEST_PACKAGE_IDS).exists()
print("[cleanup] %d test package(s) found: %s" % (
    len(test_packages), test_packages.mapped("name")))
for pkg in test_packages:
    cutlist = pkg.cutlist_id
    hardware = pkg.hardware_package_id
    print("[cleanup]   unlink package %d (%s)" % (pkg.id, pkg.name))
    pkg.unlink()
    if cutlist.exists():
        cutlist.line_ids.unlink()
        cutlist.unlink()
        print("[cleanup]     + cleared cutlist %d" % cutlist.id)
    if hardware.exists():
        hardware.line_ids.unlink()
        hardware.unlink()
        print("[cleanup]     + cleared hardware_package %d" % hardware.id)

# WO reset — back-roll the prematurely finished Cut Panels WOs.
mos = env["mrp.production"].search([("name", "in", RESET_MO_NAMES)])
print("[cleanup] %d MO(s) found for reset: %s" % (
    len(mos), mos.mapped("name")))
for mo in mos:
    cut_wos = mo.workorder_ids.filtered(
        lambda w: (w.operation_id.name or "") == RESET_OPERATION_NAME
                  and w.state == "done"
    )
    for wo in cut_wos:
        # Phase 1: ORM-unlink consumption rows so the unlink() hook
        # (shipped in southbrook_mrp_kitchen_tools 19.0.0.2.0) restores
        # asset life cleanly. Skips when there are zero rows.
        consumption_count = len(wo.sbk_consumption_ids)
        wo.sbk_consumption_ids.unlink()
        # Phase 2: SQL-direct state reset — bypasses Odoo's MRP
        # "cannot unplan a single WO" + "cannot change qty_produced on
        # done/cancel" guards. Safe for orphan test MOs being restored
        # to a pre-scan state; do NOT use this on real production WOs.
        env.cr.execute("""
            UPDATE mrp_workorder
            SET state = 'ready',
                date_finished = NULL,
                date_start = NULL,
                qty_produced = 0.0,
                duration = 0.0,
                sbk_lifecycle_processed = false
            WHERE id = %s
        """, (wo.id,))
        print("[cleanup]   reset WO %d on %s "
              "(removed %d consumption row(s))" % (
                  wo.id, mo.name, consumption_count))

env.cr.commit()
print("[cleanup] complete - DB committed")
