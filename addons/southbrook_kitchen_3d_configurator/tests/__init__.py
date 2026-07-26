# SPDX-License-Identifier: LGPL-3.0-only
# 2026-07-01 E2E audit — baseline test suite. Before this session the
# addon shipped ZERO tests (0/0/0). This is the first regression pin.
from . import test_save_design_acl

# 2026-07-02 Track B end-to-end regression insurance for the fixes
# landed across 5.6.3 → 5.6.7 (mrp.bom.note removal, autoseed order,
# Manufacture route defense-in-depth, savepoint action_confirm, plus
# the 5.6.7 UX pack: portal-partner autofill, walk-in singleton,
# active field, unlink guard).
from . import test_track_b_end_to_end

# 2026-07-06 — M1 (design totals ignore order-added cabinet lines) and
# M2 (reconcile cron can create a duplicate room) regression pins.
from . import test_m1_m2_reconcile_fixes

# 2026-07-12 — auto-arrange lifecycle: idempotence, no canonical loss, no
# derived accumulation, atomic rollback, mirror-reflects-visible.
from . import test_auto_arrange_service

# 2026-07-12 — COORDINATE_CONTRACT.md enforceability (living ledger).
from . import test_coordinate_contract

# PR2 (2026-07-12) — `wall` becomes part of the canonical persistence
# path: save_design write + validation, load_design_lines read emission.
from . import test_wall_persistence

# 2026-07-12 — Save -> Load is identity: save_design(items) ->
# load_design_lines() -> save_design(loaded items) must reproduce the
# exact same canonical model. Permanent regression pin for the
# controller-layer persistence round-trip.
from . import test_save_load_identity

# PR3.0 (2026-07-12) — y/z field-semantics migration
# (migrations/19.0.5.18.0/post-migrate.py): design-line + sale-order-
# line-mirror transform + idempotency.
from . import test_yz_semantics_migration

# PR4 (2026-07-12) — backend save_design routes non-back-wall
# configurator lines through the shared engine-placement helper
# (southbrook.kitchen.design._place_lines_on_wall); back-wall lines are
# left exactly as the client sent them.
from . import test_wall_placement_engine

# Task B3 (Materials geometry-writeback plan, Increment B) — thread
# per-instance cabinet dims (drag-resize/filler overrides) from
# design.line through action_create_quotation onto sale.order.line, plus
# the narrow sale.order.line -> mrp.bom.line mapping seam.
from . import test_geo_b3_line_dims
