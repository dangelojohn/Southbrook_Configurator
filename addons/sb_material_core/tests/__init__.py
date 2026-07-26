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
