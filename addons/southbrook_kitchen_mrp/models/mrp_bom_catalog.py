# SPDX-License-Identifier: LGPL-3.0-only
"""Catalog-wide cabinet BoM generator — M4 gap-fix.

Root cause fixed here (see PUNCHLIST / M4 ticket): only two narrow, opt-in
paths ever created an mrp.bom for a cabinet template —

  1. southbrook_kitchen_3d_configurator.kitchen_design._ensure_kitchen_bom,
     which only runs on the 3D-configurator "Create Quotation" action and
     seeds a STUB bom with EMPTY bom_line_ids (see that method's own
     docstring: "bom_line_ids stays empty; the shop team fills it in
     manually or a follow-up commit wires it up." — this IS that follow-up
     commit, for the catalog as a whole rather than one design at a time).
  2. The Hermes wizard, on explicit human Apply.

Fillers/accessories and any cabinet never pushed through the 3D
configurator's quote flow got neither, so the Order Builder's BoM Preview
warns and order confirmation spawns a placeholder MO with no cutlist.

This module adds ``mrp.bom._southbrook_generate_catalog_boms()`` — an
@api.model, catalog-wide, idempotent generator that MATERIALIZES real
bom_line_ids (never an empty stub) from:

  * The panel geometry ``mrp.bom._compute_panel_dimensions`` already
    computes (southbrook_estimating, ~mrp_bom.py) — previously computed
    then only logged, per _ensure_kitchen_bom's docstring.
  * The real Marathon hardware SKUs resolved via
    ``southbrook.hardware.catalog.resolve()`` (southbrook_hardware_catalog,
    "Module 3") — the exact same resolution path
    sb.production.package.generate_from_mo() and the FreeCAD bridge
    already use to append hardware lines post-render.

It is conservative by construction: it only ever CREATES a BoM for a
template that has none; it never mutates or deletes an existing one
(hand-built, Hermes-applied, or 3D-configurator stub alike).

KNOWN AMBIGUITY — panel/carcass raw material mapping (see
_southbrook_get_or_create_raw_material's docstring): this codebase has NO
real purchasable sheet-stock product data anywhere for panel substrates
(melamine/hardboard/plywood). Hardware lines bind to real, already-seeded
Marathon SKUs (unambiguous). Panel lines bind to a clearly-labeled
"Raw Material: ..." placeholder product, get-or-created once per
substrate, counted 1-unit-per-panel (not per real sheet/area) — flagged
in the module README and the delivery report rather than guessing a real
SKU, supplier, or unit of measure that isn't in any of the source
artifacts.

PROD DEFECT (confirmed 2026-07-06) — empty catalog BoMs on config_ok
templates
--------------------------------------------------------------------
The 12 catalog templates that are ``config_ok=True`` (SB-BASE-1DR,
SB-BASE-2DR, SB-WALL-1DR, SB-WALL-2DR, SB-DRAWER, SB-SINK-BASE,
SB-TALL-OVEN, SB-TALL-PANTRY, SB-CORNER, SB-VANITY, SB-ACCESSORY, and
``worktop`` — the 11 tagged via
southbrook_kitchen_3d_configurator/data/canonical_catalog_tag.xml plus
``worktop`` itself, deliberately left untagged there) ended up with a
template-level ``mrp.bom`` carrying ZERO ``bom_line_ids`` on prod.

Root cause, confirmed by reading both BoM-seeding paths side by side:
these are exactly the templates a customer/rep pushes through the 3D
configurator's "Create Quotation" action, so
``kitchen_design._ensure_kitchen_bom`` gets there FIRST and creates its
known-empty ``KitchenAutoSeed-*`` stub (``bom_line_ids: []`` by design —
see that method's own comment). When
``_southbrook_generate_catalog_boms`` later runs, its "skip if a normal
BoM already exists" guard (correct in isolation — never mutate a
pre-existing BoM) treats that empty stub as "already handled" and moves
on, so the hazardous empty BoM is never replaced with a real one and
never flagged. Fixed-dimension, non-configurable cabinets (B24, W24, T24,
FP3, etc. from demo_cabinets.xml) never go through that quote flow, so
they had no pre-existing BoM and the generator built them correctly —
matching the observed prod split (fixed cabinets: real lines;
config_ok cabinets: empty).

NOTE: this is NOT this generator directly manufacturing an empty BoM —
_southbrook_build_cabinet_bom already refused to create with zero
bom_line_vals before this fix, and still does (belt-and-suspenders). The
actual gap is that this generator's own scope should never have included
config_ok=True templates in the first place: those 12 templates DO carry
non-zero template-level ``southbrook_width_in`` / ``_height_in`` /
``_depth_in`` scalars (a MIDPOINT of the width envelope, per
canonical_catalog_dimensions.xml's own comment — "this template-level
scalar is a fallback the configurator uses when no variant is picked"),
so ``_compute_panel_dimensions`` would happily return real-looking panel
tuples from that midpoint fallback. Building a template-level BoM from a
midpoint that isn't what any real customer chose is exactly the "invent
a nominal dimension for a configurable cabinet" trap — wrong for a
different, subtler reason than "empty". Configurable products get their
real, correctly-dimensioned BoM per-VARIANT at config time via
``kitchen_design._ensure_kitchen_bom`` / the config-session flow — that
path is correct and untouched. This generator now hard-skips every
``config_ok=True`` template up front (``skipped_configurable``) rather
than attempting to build from template-scalar fallback dimensions, and
separately refuses to ever CREATE a BoM that would materialize zero
lines (``skipped_empty``) for the non-configurable remainder. See
``_southbrook_cleanup_empty_catalog_boms`` below for removing the 12
empty stubs already sitting on prod.
"""
import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


class MrpBom(models.Model):
    _inherit = "mrp.bom"

    # ------------------------------------------------------------------
    # Cabinet-type -> family classification. Mirrors
    # southbrook_kitchen_3d_configurator.kitchen_design._ensure_kitchen_bom
    # 's own family_map exactly (Rule 3 / NF14), so both BoM-seeding paths
    # treat the same southbrook_cabinet_type identically.
    # ------------------------------------------------------------------
    _SOUTHBROOK_FAMILY_MAP = {
        "base": "base",
        "wall": "wall",
        "tall": "tall",
        "corner": "corner",
        "filler": "accessory",
        "panel": "accessory",
    }

    # Panel key -> substrate slug. Mirrors the INTENT of
    # southbrook_kitchen_mrp.sb_cutlist.DEFAULT_SUBSTRATE_BY_PANEL (sides/
    # top/bottom/shelf = melamine carcass stock, back = hardboard, door =
    # plywood), adapted to the key names mrp.bom._compute_panel_dimensions
    # actually returns ("shelf"/"door", not "adjustable_shelf" — that's a
    # SEPARATE geometry source, shared.southbrook_dims.panel_cut_list,
    # consumed by sb.cutlist/sb.production.package for the per-MO cutlist;
    # this generator only touches the template-level mrp.bom and does not
    # change that other, already-working path).
    _SOUTHBROOK_PANEL_SUBSTRATE = {
        "side_L": "melamine_white_5_8",
        "side_R": "melamine_white_5_8",
        "top": "melamine_white_5_8",
        "bottom": "melamine_white_5_8",
        "shelf": "melamine_white_5_8",
        "back": "hardboard_1_4",
        "door": "ply_3_4",
    }

    _SOUTHBROOK_SUBSTRATE_LABELS = {
        "melamine_white_5_8": "Raw Material: 5/8in White Melamine Panel Stock",
        "hardboard_1_4": "Raw Material: 1/4in Hardboard Panel Stock",
        "ply_3_4": "Raw Material: 3/4in Plywood Panel Stock",
    }

    @api.model
    def _southbrook_generate_catalog_boms(self):
        """Catalog-wide cabinet BoM generator (M4).

        Searches every ``product.template`` flagged
        ``southbrook_is_cabinet = True`` (the southbrook_kitchen_3d_
        configurator catalog — B24, DB24, SB30, FP3 filler, etc. — incl.
        accessories/fillers) that has no 'normal'-type mrp.bom yet, and
        CREATES one with real, non-empty bom_line_ids. Never touches a
        template that already has a normal BoM (of any origin), and never
        creates an empty one — see the module docstring's "PROD DEFECT"
        section for the confirmed root cause of the 12 empty catalog BoMs.

        Three categories are skipped without creating anything:
          * ``skipped_existing_bom`` — a normal-type BoM already exists
            (hand-built, Hermes-applied, or a 3D-configurator stub —
            empty or not; never mutated or deleted here).
          * ``skipped_configurable`` — ``config_ok=True``. These
            templates' real dimensions are chosen per-VARIANT at config
            time (``kitchen_design._ensure_kitchen_bom`` / the
            config-session flow); the only dims available at the
            template level are a midpoint fallback, and building a BoM
            from that would be inventing a nominal dimension for a
            genuinely configurable cabinet. Skipped unconditionally,
            never attempted.
          * ``skipped_empty`` — belt-and-suspenders: the non-configurable
            build path genuinely produced zero materializable lines
            (should not happen for real catalog data; see
            ``_southbrook_build_cabinet_bom``).

        Idempotent — safe to re-run; the second pass finds every BoM
        created by the first pass (now covered by skipped_existing_bom)
        and skips those templates again.

        Returns ``{"created": int, "skipped": int, "skipped_existing_bom":
        int, "skipped_configurable": int, "skipped_empty": int, "details":
        [...]}``. ``skipped`` is the sum of the three specific counters,
        kept for callers (e.g. the nightly cron log line) that only care
        about the total.
        """
        Template = self.env["product.template"].sudo()
        empty_result = {
            "created": 0,
            "skipped": 0,
            "skipped_existing_bom": 0,
            "skipped_configurable": 0,
            "skipped_empty": 0,
            "details": [],
        }
        if "southbrook_is_cabinet" not in Template._fields:
            # southbrook_kitchen_3d_configurator (owner of the flag) isn't
            # installed in this database. Nothing is in scope — this is
            # not an error, mirrors the getattr-defensive pattern already
            # used in southbrook_estimating.sale_order for the same field.
            _logger.info(
                "Southbrook catalog BoM generator: southbrook_is_cabinet "
                "field not present (southbrook_kitchen_3d_configurator not "
                "installed) — nothing to do."
            )
            return empty_result

        templates = Template.with_context(active_test=False).search(
            [("southbrook_is_cabinet", "=", True)]
        )

        created = 0
        skipped_existing_bom = 0
        skipped_configurable = 0
        skipped_empty = 0
        details = []
        for tmpl in templates:
            # Fast path — a normal-type BoM already exists (hand-built,
            # Hermes-applied, or the 3D-configurator's own stub, empty or
            # not). Never touch it. active_test=False so an archived
            # normal BoM still counts (mirrors _ensure_kitchen_bom's own
            # guard).
            existing = tmpl.with_context(active_test=False).bom_ids.filtered(
                lambda b: b.type == "normal"
            )
            if existing:
                skipped_existing_bom += 1
                continue

            # config_ok=True — the template's own scalar dims are a
            # midpoint fallback, not what any real customer configured.
            # Never build a template-level BoM from that; the real BoM
            # is created per-variant elsewhere. getattr-defensive: some
            # databases may not have product_configurator's config_ok
            # field merged in yet, though southbrook_is_cabinet already
            # implies southbrook_estimating (and hence product_
            # configurator) is installed.
            if getattr(tmpl, "config_ok", False):
                skipped_configurable += 1
                continue

            bom = self._southbrook_build_cabinet_bom(tmpl)
            if not bom:
                skipped_empty += 1
                continue

            created += 1
            details.append({
                "template_id": tmpl.id,
                "template": tmpl.display_name,
                "bom_id": bom.id,
                "line_count": len(bom.bom_line_ids),
            })

        skipped = skipped_existing_bom + skipped_configurable + skipped_empty
        _logger.info(
            "Southbrook catalog BoM generator: created=%s "
            "skipped_existing_bom=%s skipped_configurable=%s "
            "skipped_empty=%s",
            created, skipped_existing_bom, skipped_configurable,
            skipped_empty,
        )
        return {
            "created": created,
            "skipped": skipped,
            "skipped_existing_bom": skipped_existing_bom,
            "skipped_configurable": skipped_configurable,
            "skipped_empty": skipped_empty,
            "details": details,
        }

    @api.model
    def _southbrook_cleanup_empty_catalog_boms(self):
        """One-time (repeatable) cleanup for the empty catalog BoMs.

        Prod carries 12 template-level ``mrp.bom`` records on
        ``config_ok=True`` cabinet templates with ZERO ``bom_line_ids`` —
        see the module docstring's "PROD DEFECT" section for the
        confirmed root cause (``kitchen_design._ensure_kitchen_bom``'s
        known-empty ``KitchenAutoSeed-*`` stub, created before this
        generator ever saw the template, which then treated the empty
        stub as "already handled").

        This method finds every EMPTY (``bom_line_ids`` falsy),
        normal-type ``mrp.bom`` on a ``southbrook_is_cabinet=True``
        template whose ``code`` marks it as machine-autoseeded by one of
        the two known auto-stub paths — ``CatalogAutoBOM-*`` (this
        generator; should be unreachable after the fix above, but cheap
        to also cover) or ``KitchenAutoSeed-*``
        (``kitchen_design._ensure_kitchen_bom``, the actual source of the
        12 empties on prod) — and unlinks it, UNLESS it is referenced by
        any ``mrp.production`` (confirmed or not — an MO pointing at it
        means it is "in use", not orphaned, and must never be deleted
        out from under a production order).

        A hand-built or Hermes-applied BoM never carries either code
        prefix, so this can never delete real shop-authored data even if
        it happens to be empty.

        Idempotent — a second run finds nothing left to delete.

        Returns ``{"deleted": int, "deleted_details": [...],
        "refused_in_use": [...]}``.
        """
        Bom = self.env["mrp.bom"].sudo()
        Production = self.env["mrp.production"].sudo()
        Template = self.env["product.template"].sudo()

        if "southbrook_is_cabinet" not in Template._fields:
            _logger.info(
                "Southbrook catalog BoM cleanup: southbrook_is_cabinet "
                "field not present — nothing to do."
            )
            return {"deleted": 0, "deleted_details": [], "refused_in_use": []}

        AUTOSEED_PREFIXES = ("CatalogAutoBOM-", "KitchenAutoSeed-")

        candidates = Bom.with_context(active_test=False).search([
            ("type", "=", "normal"),
            ("bom_line_ids", "=", False),
            ("product_tmpl_id.southbrook_is_cabinet", "=", True),
        ])
        candidates = candidates.filtered(
            lambda b: (b.code or "").startswith(AUTOSEED_PREFIXES)
        )

        deleted = 0
        deleted_details = []
        refused_in_use = []
        for bom in candidates:
            in_use_count = Production.search_count([("bom_id", "=", bom.id)])
            if in_use_count:
                refused_in_use.append({
                    "bom_id": bom.id,
                    "template_id": bom.product_tmpl_id.id,
                    "template": bom.product_tmpl_id.display_name,
                    "code": bom.code,
                    "production_count": in_use_count,
                })
                continue

            deleted_details.append({
                "bom_id": bom.id,
                "template_id": bom.product_tmpl_id.id,
                "template": bom.product_tmpl_id.display_name,
                "code": bom.code,
            })
            bom.unlink()
            deleted += 1

        _logger.info(
            "Southbrook catalog BoM cleanup: deleted=%s refused_in_use=%s",
            deleted, len(refused_in_use),
        )
        return {
            "deleted": deleted,
            "deleted_details": deleted_details,
            "refused_in_use": refused_in_use,
        }

    def _southbrook_build_cabinet_bom(self, tmpl):
        """Build ONE real mrp.bom for a single cabinet template.

        Caller (``_southbrook_generate_catalog_boms``) only invokes this
        for templates that already passed the ``config_ok`` and
        "no existing BoM" guards, so ``tmpl`` here is always a
        non-configurable, BoM-less cabinet — but this method still
        builds ``bom_line_vals`` FIRST and only calls ``Bom.create()`` if
        it ends up non-empty, as a second, independent line of defense:
        never create the BoM record at all if nothing would end up on it.

        Returns the created mrp.bom, or an empty recordset if there was
        genuinely nothing sensible to put on it (defensive guard — should
        not happen for real catalog data, but a BoM with zero
        bom_line_ids would be no better than the stub this replaces, so
        it is refused rather than created).
        """
        Bom = self.env["mrp.bom"].sudo()

        w_in = tmpl.southbrook_width_in or 24.0
        h_in = tmpl.southbrook_height_in or 34.5
        d_in = tmpl.southbrook_depth_in or 24.0
        width_mm = w_in * 25.4
        height_mm = h_in * 25.4
        depth_mm = d_in * 25.4

        cabinet_type = tmpl.southbrook_cabinet_type or "base"
        family = self._SOUTHBROOK_FAMILY_MAP.get(cabinet_type, "base")

        # Rule 3 (Southbrook_Excel_to_Odoo_Mapping.md §3.4) — width -> door
        # count for boxed families; accessories carry no door. Mirrors
        # kitchen_design._ensure_kitchen_bom exactly, for consistency
        # between the two BoM-seeding paths.
        if family == "accessory":
            door_count = 0
        elif w_in >= 24.0:
            door_count = 2
        else:
            door_count = 1

        bom_line_vals = []
        shelf_count = 0

        if family == "accessory":
            # AMBIGUITY FLAG: a filler/decorative panel (southbrook_
            # cabinet_type "filler"/"panel") is a single flat board, not a
            # 6-panel box. Calling _compute_panel_dimensions here would
            # wrongly synthesize sides/top/bottom/back/shelf for a product
            # that is physically just one panel — that would be guessing
            # a wrong cutlist, which the task explicitly warns against.
            # Minimal sensible BoM instead: one panel-stock line, the same
            # substrate sb_cutlist.py's DEFAULT_SUBSTRATE_BY_PANEL falls
            # back to for an unrecognized panel key ("melamine_white_5_8").
            # The EXACT substrate a given filler/end-panel should consume
            # (e.g. matching the door finish) is not modeled anywhere in
            # this codebase yet — flagged in the delivery report, not
            # guessed further here.
            product = self._southbrook_get_or_create_raw_material(
                "melamine_white_5_8"
            )
            bom_line_vals.append((0, 0, {
                "product_id": product.id,
                "product_qty": 1.0,
            }))
        else:
            panel = Bom._compute_panel_dimensions(
                width_mm=width_mm,
                height_mm=height_mm,
                depth_mm=depth_mm,
                family=family,
                door_count=door_count,
                drawer_count=0,
                finished_sides="none",
            )
            shelf_count = int(panel.get("shelf_count") or 0)
            counts = {}
            for key, substrate in self._SOUTHBROOK_PANEL_SUBSTRATE.items():
                value = panel.get(key)
                if value is None:
                    continue
                if key == "shelf":
                    qty = shelf_count
                elif key == "door":
                    qty = int(panel.get("door_count") or 0)
                else:
                    qty = 1
                if qty <= 0:
                    continue
                counts[substrate] = counts.get(substrate, 0) + qty
            for substrate, qty in counts.items():
                product = self._southbrook_get_or_create_raw_material(substrate)
                bom_line_vals.append((0, 0, {
                    "product_id": product.id,
                    "product_qty": float(qty),
                }))

        # Hardware — real Marathon SKUs, the exact same resolution path
        # Module 3/4 already use post-render
        # (sb.production.package.generate_from_mo). soft_close mirrors
        # Rule 4 (bi-fold corner cabinets ship without soft-close).
        # drawer_count is always 0 here: this catalog's
        # southbrook_cabinet_type selection has no drawer-count signal at
        # all (verified — even "DB24 3-Drawer Base" in demo_cabinets.xml
        # is tagged cabinet_type="base"), the exact same limitation
        # kitchen_design._ensure_kitchen_bom already lives with.
        Catalog = self.env["southbrook.hardware.catalog"]
        hardware_picks = Catalog.resolve(
            cabinet_family=family,
            door_count=door_count,
            drawer_count=0,
            shelf_count=shelf_count,
            soft_close=(family != "corner"),
        )
        for product, qty in hardware_picks:
            if qty <= 0:
                continue
            bom_line_vals.append((0, 0, {
                "product_id": product.id,
                "product_qty": float(qty),
            }))

        if not bom_line_vals:
            _logger.warning(
                "Southbrook catalog BoM generator: %s produced zero "
                "sensible bom_line_ids — skipped rather than creating an "
                "empty BoM.",
                tmpl.display_name,
            )
            return Bom.browse()

        default_code = tmpl.default_code or ("TMPL-%d" % tmpl.id)
        bom = Bom.create({
            "product_tmpl_id": tmpl.id,
            "type": "normal",
            "product_qty": 1.0,
            "code": "CatalogAutoBOM-%s" % default_code,
            "bom_line_ids": bom_line_vals,
        })
        return bom

    def _southbrook_get_or_create_raw_material(self, substrate):
        """Get-or-create a placeholder raw-material product for a panel
        substrate slug (melamine_white_5_8 / hardboard_1_4 / ply_3_4).

        KNOWN AMBIGUITY (flagged per task instructions, not guessed away):
        this codebase has NO real sheet-stock product data anywhere.
        ``southbrook.kitchen.material`` (southbrook_mrp_kitchen_workcenters)
        is shop-routing classification metadata, not an inventory/purchase
        record. The ``southbrook_kitchen_mrp.product_substrate_<slug>``
        xmlids that ``sb.cutlist._resolve_offcut_product`` defensively
        looks up (with ``raise_if_not_found=False``) don't exist either.

        Rather than invent a real purchasable SKU, supplier, or unit of
        measure that isn't in any of the source artifacts, this method
        creates ONE clearly-labeled "Raw Material: ..." consu product per
        substrate, get-or-created by a stable xmlid so re-runs and every
        template that needs the same substrate share one product instead
        of multiplying rows. Quantity on the BoM line is counted PER PANEL
        (1 unit = 1 panel-equivalent leaf), not per real sheet or square
        metre — the real sheet-yield/nesting accounting already exists
        downstream (sb.cutlist / to_nesting_envelope) and is untouched by
        this. Swap this method for a real purchasable SKU lookup when the
        raw-material catalog lands; the panel-count math above does not
        change.
        """
        xmlid = "raw_material_%s" % substrate
        product = self.env.ref(
            "southbrook_kitchen_mrp.%s" % xmlid, raise_if_not_found=False
        )
        if product:
            return product

        Product = self.env["product.product"].sudo()
        label = self._SOUTHBROOK_SUBSTRATE_LABELS.get(
            substrate, "Raw Material: %s" % substrate
        )
        product = Product.create({
            "name": label,
            "default_code": "RM-%s" % substrate.upper(),
            "type": "consu",
            "is_storable": True,
            "purchase_ok": True,
            "sale_ok": False,
        })
        self.env["ir.model.data"].create({
            "module": "southbrook_kitchen_mrp",
            "name": xmlid,
            "model": "product.product",
            "res_id": product.id,
            "noupdate": True,
        })
        return product
