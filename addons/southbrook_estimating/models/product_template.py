# SPDX-License-Identifier: LGPL-3.0-only
"""
Southbrook-specific extensions on product.template.

Phase-2 Track-1 addition (NF26 — 2026-05-30 live install verification):
the OCA `product_configurator` ships a "Configure Product" button in
the form header gated on `product_configurator.group_product_configurator`.
On the QNAP southbrook stack, even users in that group don't see the
header button reliably — likely because the `<header>` injection by
OCA's xpath either lands AFTER our southbrook view inherits or is
suppressed by another inherit chain.

Rather than wrestle with inherit ordering, this module adds a
deterministic SOUTHBROOK button as a stat-button in the form's
button_box (which exists on every product.template form view). The
button always renders for `config_ok=True` templates regardless of
group membership.

The button delegates to the OCA `configure_product` method — same
session creation, same wizard action — so picking either entry point
lands the user on the same wizard form with the southbrook 3D viewport
embedded (per Track 1 commits 1-5).
"""
from odoo import models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    def action_southbrook_launch_3d_configurator(self):
        """Launch the OCA configurator wizard for this template.

        Returns the action dict the OCA's configure_product produces —
        an ir.actions.act_window opening the product.configurator form
        with the session pre-created.

        Mirrors what the OCA "Configure Product" button does. Exists as
        a separate Southbrook method so:
          • we can swap the entry point without touching the OCA module
          • we can extend with seed-mode context or telemetry later
            without conflicting with upstream
        """
        self.ensure_one()
        # OCA's configure_product is the canonical session+wizard launcher.
        # Pass-through — no behaviour change today.
        return self.configure_product()
