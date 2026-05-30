# SPDX-License-Identifier: LGPL-3.0-only
#
# Models populate progressively per docs/drafts/PHASE_1_FIRST_5_COMMITS.md.
# Commit 2: res_partner.
# Commit 3: product_attribute_value (Q3 lead_time_extra + Q4 dual storage).
# Commit 4: product_pricelist + sale_order (channel resolution + refacing margin-target).
# Commit 5: product_config_line override stub + mrp_bom partial lead_time_extra rollup.
# Commit 6: southbrook_order_analytics.
from . import res_partner
from . import product_attribute_value
