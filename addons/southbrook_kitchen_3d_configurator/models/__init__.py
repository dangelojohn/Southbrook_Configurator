from . import res_groups
from . import product_template, kitchen_design
# Recommendation D · Sprint 1 unification bridge
from . import sale_order_line, southbrook_room, reconcile
# Recommendation D · Sprint 2c · sale.order "Open in 3D"
from . import sale_order
# 2026-07-02 · reverse of the ordered→SO transition: when the SO is
# cancelled, revert its kitchen.design back to state='configured' and
# clear sale_order_id so it becomes editable + re-quotable.
from . import sale_order_cancel_sync
