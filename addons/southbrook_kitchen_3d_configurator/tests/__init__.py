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
