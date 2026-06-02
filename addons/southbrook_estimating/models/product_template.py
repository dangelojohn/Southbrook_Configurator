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
from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    # ------------------------------------------------------------------
    # 2026-06-02 catalog-picker redesign — display metadata.
    #
    # Four fields exposed on every product.template so the redesigned
    # customer Order Builder catalog picker can render category badges,
    # one-sentence descriptions, reference dimensions, and an icon
    # thumbnail directly from authoritative ORM state (rather than from
    # a controller-side hardcoded lookup table).
    #
    # All four are prefixed `southbrook_` because the unprefixed names
    # collide with Odoo core (product.template.description is a stock
    # field; categ_id is the standard category) and because the
    # codebase convention prefixes Southbrook extensions on shared core
    # models — see e.g. southbrook_submitted_date on sale.order,
    # southbrook_condition on maintenance.equipment.
    #
    # Seed data for the 12 Q8 cabinets lives in
    # data/cabinet_catalog_metadata.xml. Existing-DB upgrades are
    # covered by migrations/19.0.1.1.0/post-migrate.py which backfills
    # the four fields on the 12 cabinets by default_code.
    # ------------------------------------------------------------------
    southbrook_category = fields.Selection(
        selection=[
            ("Wall", "Wall"),
            ("Base", "Base"),
            ("Drawer", "Drawer"),
            ("Tall", "Tall"),
            ("Vanity", "Vanity"),
            ("Extras", "Extras"),
        ],
        string="Southbrook Catalog Category",
        help=(
            "Display category used by the customer Order Builder "
            "catalog picker to group / filter cabinets. Distinct from "
            "categ_id (the Odoo internal category) and from the "
            "product_configurator family attribute (the operational "
            "9-family taxonomy). Six values mirror the catalog picker's "
            "filter pills: Wall, Base, Drawer, Tall, Vanity, Extras."
        ),
    )

    southbrook_description = fields.Char(
        string="Southbrook Catalog Description",
        translate=True,
        help=(
            "One-sentence customer-facing description rendered on the "
            "catalog picker card. Translatable so non-English Southbrook "
            "deployments can localise without re-seeding. Distinct from "
            "the inherited product.template.description (which is "
            "internal / sales-rep notes)."
        ),
    )

    southbrook_dimensions = fields.Char(
        string="Southbrook Catalog Dimensions",
        help=(
            "Canonical reference dimensions displayed next to the "
            "ruler icon on the catalog picker card "
            "(e.g. '18\"W x 34 1/2\"H x 24\"D' or 'Varies' / "
            "'Per linear ft' for non-cabinet entries like accessories "
            "and worktops). Free-form Char so we can carry both "
            "imperial and metric without a unit-conversion layer."
        ),
    )

    southbrook_icon_key = fields.Char(
        string="Southbrook Catalog Icon Key",
        help=(
            "Key matching one of the inline-SVG icons in "
            "static/src/js/portal_boot.esm.js (CABINET_ICONS map): "
            "wall1, wall2, base1, base2, drawer, sink, pantry, oven, "
            "corner, vanity, extra, worktop. Unknown keys fall back "
            "to 'extra' at render time via cabinetIcon()."
        ),
    )

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
