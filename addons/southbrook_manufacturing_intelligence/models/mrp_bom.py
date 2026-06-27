# SPDX-License-Identifier: LGPL-3.0-only
"""mrp.bom extension for W025 — First Article Inspection gate.

When a new mrp.bom is released into production (via ProductGraph's
``pg.release.action_execute_release`` OR via ``southbrook.eco`` BOM
re-versioning), the next MO created against the BOM is auto-gated:
it must have a passing FAI ``southbrook.mi.check`` (category='fai')
before ``action_assign`` will release it to the shop floor.

The gate clears as soon as the first MO's FAI check is passed — the
flag on the BOM flips to ``False`` and every subsequent MO on the
same BOM skips the gate entirely.

Why we detect "new BOM" inside create() rather than at the call site:
  * pg.release._create_mrp_bom is in product_graph_release, a soft
    dep (not in MI's manifest depends list). We can't hook there
    without making PG a hard dep.
  * southbrook.eco._apply_bom is in southbrook_plm. We do depend on
    it transitively, but the ECO has many kinds (bom / cut_spec /
    rule / document) — only 'bom' produces a new mrp.bom, and the
    cleanest seam to detect "new BOM that needs FAI" is at create()
    time itself.

Detection heuristics inside create():
  * `pg_release_id` set → PG release flow → FAI required.
  * `southbrook_version > 1` → PLM ECO re-version → FAI required.
  * Otherwise (a hand-authored BOM with no provenance stamp) → leave
    fai_required at its default (False) — admins who hand-create
    BOMs are not the FAI gate's target population.

Either detection can be overridden by passing
``context={'_w025_skip_fai_default': True}`` — used by tests and
data-migration tooling that needs to seed BOMs without the gate.
"""
from odoo import _, api, fields, models


class MrpBom(models.Model):
    _inherit = "mrp.bom"

    # ------------------------------------------------------------------
    # W025 — First Article Inspection gate
    # ------------------------------------------------------------------
    fai_required = fields.Boolean(
        string="FAI Required",
        default=False, copy=False, tracking=True, index=True,
        help="When True, the next mrp.production created against this "
             "BOM is auto-gated: a southbrook.mi.check (category='fai') "
             "is auto-created and must be passed before action_assign "
             "will release the MO to the shop. The flag clears when "
             "the FAI passes; subsequent MOs on the same BOM are not "
             "gated.",
    )
    fai_passed_at = fields.Datetime(
        string="FAI Passed At",
        readonly=True, copy=False,
        help="UTC datetime the First Article Inspection was signed off.",
    )
    fai_passed_by = fields.Many2one(
        "res.users", string="FAI Passed By",
        readonly=True, copy=False,
        help="The QC inspector / engineer who signed off the FAI. "
             "Cannot be the same user who created this BOM "
             "(segregation of duties).",
    )
    fai_passing_mi_check_id = fields.Many2one(
        "southbrook.mi.check", string="FAI Sign-off Check",
        readonly=True, copy=False, ondelete="set null",
        help="The southbrook.mi.check (category='fai') whose "
             "action_fai_pass cleared this BOM's gate. Pinned for "
             "warranty-trace queries.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        """Stamp `fai_required=True` on new BOMs released via PG or PLM ECO.

        See the module docstring for the detection heuristics. Honours
        the `_w025_skip_fai_default` context flag so test fixtures and
        data migrations can seed BOMs without triggering the gate.
        """
        skip = self.env.context.get("_w025_skip_fai_default")
        if not skip:
            for vals in vals_list:
                # Don't clobber an explicit caller intent.
                if "fai_required" in vals:
                    continue
                # PG-release-created BOMs always carry pg_release_id.
                # The field may not exist if product_graph_release
                # isn't installed; guard with `in self._fields`.
                if "pg_release_id" in self._fields and vals.get("pg_release_id"):
                    vals["fai_required"] = True
                    continue
                # PLM ECO _apply_bom uses old.copy({'southbrook_version': old+1}).
                # That copy() takes the same path as create(), so any
                # vals carrying southbrook_version > 1 is an ECO output.
                if (
                    "southbrook_version" in self._fields
                    and (vals.get("southbrook_version") or 0) > 1
                ):
                    vals["fai_required"] = True
                    continue
        return super().create(vals_list)
