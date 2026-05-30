# SPDX-License-Identifier: LGPL-3.0-only
"""
NF2 override stub for the OCA product_configurator
validate_configuration mechanism (per Build Spec section 9.1).

Upstream status (OCA v19.0.1.0.0):
  - `product.config.session.validate_configuration()` returns a dict
    `{"value": True}` on success or `{"value": False, "reason": str}`
    on rule-blocked. Brief section 2.2 ("rule reason visible to sales rep")
    works with this dict-return today.
  - There is a `# TODO: Raise ConfigurationError with reason` marker at
    `product_configurator/models/product_config.py:1500`. If OCA upstream
    converts the dict-return to a raise-with-reason pattern, this override
    is the swap point.

Current behaviour: this override is a NO-OP — it does not change the
dict-return contract. Its purpose is to RESERVE the override site so
that swapping from dict-return to raise is a single-file change in
southbrook_estimating, NOT a per-call-site fixup across the codebase.

When OCA upstream switches:
  1. Remove the super() call below.
  2. Replace with a wrapper that catches ConfigurationError, builds the
     same {"value": False, "reason": str(e)} dict, and returns it.
  3. Or invert: convert the dict-return into a raise for consumers that
     prefer exception flow.
"""
from odoo import models


class ProductConfigLine(models.Model):
    """Reserved hook for the NF2 override.

    Currently no-op. See module docstring for the swap rationale.
    """
    _inherit = "product.config.line"

    # No methods overridden today. The class declaration itself is what
    # gives southbrook_estimating priority in the inheritance chain when
    # the swap is needed.


class ProductConfigSession(models.Model):
    """Reserved hook for the NF2 validate_configuration override.

    Currently passes through to upstream verbatim. Locks in the override
    site so future swap is a one-file change.
    """
    _inherit = "product.config.session"

    def validate_configuration(
        self, product_tmpl_id=None, value_ids=None, custom_vals=None, final=True
    ):
        """Pass-through. See module docstring."""
        return super().validate_configuration(
            product_tmpl_id=product_tmpl_id,
            value_ids=value_ids,
            custom_vals=custom_vals,
            final=final,
        )
