# SPDX-License-Identifier: LGPL-3.0-only
#
# Models populate progressively per docs/drafts/PHASE_1_FIRST_5_COMMITS.md.
# Commit 2: res_partner.
# Commit 3: product_attribute_value (Q3 lead_time_extra + Q4 dual storage).
# Commit 4: product_pricelist + sale_order (channel resolution + refacing margin-target).
# Commit 5: product_config_line override stub + mrp_bom partial lead_time_extra rollup.
# Commit 6: southbrook_order_analytics.
from . import res_partner
from . import res_users
from . import product_attribute_value
from . import product_pricelist
from . import southbrook_room
from . import southbrook_room_wall
from . import southbrook_room_constraint
from . import southbrook_room_template
from . import sale_order
from . import sale_order_line
from . import product_config_line
from . import product_config_session
from . import product_configurator
from . import config_template_picker
from . import product_template
from . import mrp_bom
from . import southbrook_order_analytics
from . import cabinet_archetype
from . import template_code
from . import template_archetype
from . import product_product
from . import builder_po_intake
from . import qr_kind_handlers
from . import ptav_price_extra_seed
# M1 rules-as-data corner cabinetry layer (09-rule-engine-spec.md §6-7).
from . import placement_rule
# T4a (kitchen templates) — SB-CORNER variant data repair helper
# (shared by the 19.0.9.1.0 migration and the configurator tests).
from . import corner_sku_repair
