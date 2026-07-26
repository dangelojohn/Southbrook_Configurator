# SPDX-License-Identifier: LGPL-3.0-only
from . import test_family
from . import test_material_fields
from . import test_attribute_link
from . import test_material_geometry_dualunit
from . import test_material_seed_data
# Repair Wave 2, Upgrade 1 — family/density backfill for pre-existing materials.
from . import test_family_density_backfill
# Repair Wave 3 — product.template.material_id fallback for _resolve_material().
from . import test_product_material_fallback
# Task 1 — supplierinfo.uom_yield_qty for procurement (Phase-2 T1).
from . import test_supplierinfo_yield
# Task 2 — _effective_waste_pct() material/family fallback (Phase-2 T2).
from . import test_effective_waste
# Hygiene A2 — thickness-specific materials (mat_mel_58 / mat_hardboard_14)
# for the 2 live legacy sheet components that previously fell back to the
# 3/4"=19.05mm cut constant via the generic melamine/mdf materials.
from . import test_thickness_specific_materials
