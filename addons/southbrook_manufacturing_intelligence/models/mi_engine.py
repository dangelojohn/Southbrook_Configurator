# SPDX-License-Identifier: LGPL-3.0-only
import logging
import math
import json

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class SouthbrookMiEngine(models.AbstractModel):
    _name = "southbrook.mi.engine"
    _description = "Southbrook Manufacturing Intelligence Engine"

    @api.model
    def _status_from_severities(self, severities):
        if "blocker" in severities:
            return "blocked"
        if "warning" in severities:
            return "review"
        return "ok"

    @api.model
    def _sheet_area_m2(self):
        params = self.env["ir.config_parameter"].sudo()
        width = float(
            params.get_param("southbrook_mi.sheet_width_mm", default=2440) or 2440
        )
        height = float(
            params.get_param("southbrook_mi.sheet_height_mm", default=1220) or 1220
        )
        return (width * height) / 1000000.0

    @api.model
    def _sheet_dimensions_mm(self):
        params = self.env["ir.config_parameter"].sudo()
        width = float(
            params.get_param("southbrook_mi.sheet_width_mm", default=2440) or 2440
        )
        height = float(
            params.get_param("southbrook_mi.sheet_height_mm", default=1220) or 1220
        )
        return width, height

    @api.model
    def _compute_cut_summary(self, panels):
        panel_area_m2 = 0.0
        edge_band_m = 0.0
        duplicate_index = {}

        for panel in panels:
            qty = panel.get("qty") or 0
            length = panel.get("length_mm") or 0
            width = panel.get("width_mm") or 0
            thickness = panel.get("thickness_mm") or 0
            substrate = panel.get("substrate") or ""
            grain_dir = panel.get("grain_dir") or ""
            panel_area_m2 += (length * width * qty) / 1000000.0
            edge_band_m += (
                self._edge_band_length_mm(panel, length, width) * qty / 1000.0
            )
            key = (length, width, thickness, substrate, grain_dir)
            duplicate_index.setdefault(key, 0)
            duplicate_index[key] += qty

        sheet_area_m2 = self._sheet_area_m2()
        sheet_count = int(math.ceil(panel_area_m2 / sheet_area_m2)) if panel_area_m2 else 0
        gross_sheet_area_m2 = sheet_count * sheet_area_m2
        yield_pct = (
            (panel_area_m2 / gross_sheet_area_m2) * 100.0
            if gross_sheet_area_m2
            else 0.0
        )
        waste_area_m2 = max(gross_sheet_area_m2 - panel_area_m2, 0.0)
        duplicate_groups = [
            {
                "length_mm": key[0],
                "width_mm": key[1],
                "thickness_mm": key[2],
                "substrate": key[3],
                "grain_dir": key[4],
                "qty": qty,
            }
            for key, qty in duplicate_index.items()
            if qty > 1
        ]
        return {
            "panel_area_m2": panel_area_m2,
            "sheet_count": sheet_count,
            "gross_sheet_area_m2": gross_sheet_area_m2,
            "yield_pct": yield_pct,
            "waste_area_m2": waste_area_m2,
            "edge_band_m": edge_band_m,
            "duplicate_groups": duplicate_groups,
        }

    @api.model
    def _edge_band_length_mm(self, panel, length_mm, width_mm):
        config = panel.get("edge_banding_config")
        if not config:
            return 2 * (length_mm + width_mm)
        if isinstance(config, str):
            try:
                config = json.loads(config)
            except json.JSONDecodeError:
                return 2 * (length_mm + width_mm)
        if not isinstance(config, dict):
            return 2 * (length_mm + width_mm)
        total = 0.0
        if config.get("front"):
            total += length_mm
        if config.get("back"):
            total += length_mm
        if config.get("left"):
            total += width_mm
        if config.get("right"):
            total += width_mm
        return total

    @api.model
    def _cut_checks_from_panels(self, panels, summary):
        checks = []
        sheet_width, sheet_height = self._sheet_dimensions_mm()

        for panel in panels:
            length = panel.get("length_mm") or 0
            width = panel.get("width_mm") or 0
            name = panel.get("panel_name") or "Panel"
            fits_straight = length <= sheet_width and width <= sheet_height
            fits_rotated = width <= sheet_width and length <= sheet_height
            if length and width and not fits_straight and not fits_rotated:
                checks.append(
                    {
                        "name": "Oversized panel",
                        "severity": "blocker",
                        "category": "cut",
                        "message": "%s is %.0f x %.0f mm and does not fit a %.0f x %.0f mm sheet."
                        % (name, length, width, sheet_width, sheet_height),
                        "recommendation": "Split the part, select a larger sheet, or confirm a special-order blank before cutting.",
                    }
                )
            elif (
                length
                and width
                and not fits_straight
                and fits_rotated
                and (panel.get("grain_dir") or "") not in ("", "none", "no_grain")
            ):
                checks.append(
                    {
                        "name": "Grain direction rotation review",
                        "severity": "warning",
                        "category": "cut",
                        "message": "%s only fits the sheet when rotated." % name,
                        "recommendation": "Confirm visible grain direction and customer-facing orientation before nesting.",
                    }
                )

        if (summary or {}).get("waste_area_m2", 0.0) >= 0.09:
            checks.append(
                {
                    "name": "Reusable offcut",
                    "severity": "info",
                    "category": "cut",
                    "message": "Estimated sheet waste is %.2f m2."
                    % summary.get("waste_area_m2", 0.0),
                    "recommendation": "Label reusable offcuts by material, thickness, grain, and usable dimensions before moving the sheet.",
                }
            )
        return checks

    @api.model
    def _unlink_existing_checks(self, production=None, package=None):
        domain = []
        if production:
            domain.append(("production_id", "=", production.id))
        if package:
            domain.append(("production_package_id", "=", package.id))
        if domain:
            self.env["southbrook.mi.check"].sudo().search(domain).unlink()

    @api.model
    def _create_check(self, values):
        return self.env["southbrook.mi.check"].sudo().create(values)

    @api.model
    def _production_package(self, production):
        return self.env["sb.production.package"].search(
            [("mo_id", "=", production.id)], limit=1
        )

    @api.model
    def _production_cutlist(self, production):
        package = self._production_package(production)
        return package.cutlist_id if package and package.cutlist_id else False

    @api.model
    def _panels_from_cutlist(self, cutlist):
        panels = []
        for line in cutlist.line_ids:
            panels.append(
                {
                    "sequence": line.sequence,
                    "panel_name": line.panel_name,
                    "qty": line.qty,
                    "length_mm": line.length_mm,
                    "width_mm": line.width_mm,
                    "thickness_mm": line.thickness_mm,
                    "substrate": line.substrate,
                    "grain_dir": line.grain_dir,
                    "edge_banding_config": line.edge_banding_config,
                }
            )
        return panels

    @api.model
    def _assembly_checks_from_panels(self, panels):
        checks = []
        for panel in panels:
            name = (panel.get("panel_name") or "").lower()
            if "shelf" in name and (panel.get("length_mm") or 0) > 900:
                checks.append(
                    {
                        "name": "Long shelf requires assembly review",
                        "severity": "warning",
                        "category": "assembly",
                        "message": "%s is longer than 900 mm."
                        % (panel.get("panel_name") or "Shelf"),
                        "recommendation": "Confirm support, pin spacing, and handling before release.",
                    }
                )
        return checks

    @api.model
    def _hardware_checks_from_summary(self, summary):
        if not summary:
            return [
                {
                    "name": "Missing hardware package",
                    "severity": "blocker",
                    "category": "hardware",
                    "message": "Production package has no linked hardware package.",
                    "recommendation": "Generate or link the hardware pick list before releasing to the shop floor.",
                }
            ]

        checks = []
        if not summary.get("line_count"):
            checks.append(
                {
                    "name": "Empty hardware pick list",
                    "severity": "blocker",
                    "category": "hardware",
                    "message": "Hardware package has no pick lines.",
                    "recommendation": "Resolve hinges, slides, pulls, fasteners, shelf pins, and install hardware before release.",
                }
            )
        if summary.get("has_pricing_pending"):
            checks.append(
                {
                    "name": "Hardware pricing pending",
                    "severity": "warning",
                    "category": "hardware",
                    "message": "One or more hardware SKUs still have pending pricing.",
                    "recommendation": "Confirm supplier price and availability before purchasing or staging hardware.",
                }
            )
        if summary.get("state") == "draft":
            checks.append(
                {
                    "name": "Hardware not picked",
                    "severity": "warning",
                    "category": "hardware",
                    "message": "Hardware package is still in draft.",
                    "recommendation": "Pick or reserve hardware before moving the cabinet package to assembly.",
                }
            )
        return checks

    @api.model
    def _install_checks_from_dimensions(self, width_mm, height_mm, depth_mm):
        checks = []
        if height_mm and height_mm >= 2400:
            checks.append(
                {
                    "name": "Tall cabinet install review",
                    "severity": "warning",
                    "category": "install",
                    "message": "Cabinet height is %.0f mm." % height_mm,
                    "recommendation": "Confirm ceiling clearance, lift path, and on-site handling.",
                }
            )
        checks.append(
            {
                "name": "Filler and scribe confirmation",
                "severity": "info",
                "category": "install",
                "message": "Confirm filler, scribe, and site tolerance requirements.",
                "recommendation": "Review install drawings before shipping.",
            }
        )
        return checks

    @api.model
    def _install_check_lines_for_pdf(self, checks):
        lines = []
        for check in checks:
            label = dict(check._fields["severity"].selection).get(
                check.severity, check.severity
            )
            lines.append("%s: %s - %s" % (label, check.name, check.message))
        return lines

    # P3 — Auto-remediation flag. When ON, the engine attempts to
    # generate the missing cutlist via the P1 builder before deciding
    # the blocker is unavoidable.
    _AUTO_REMEDIATE_FLAG = (
        "southbrook_manufacturing_intelligence.auto_remediate_cutlist"
    )

    @api.model
    def _recompute_production(self, production):
        self._unlink_existing_checks(production=production)
        cutlist = self._production_cutlist(production)

        # P3 — Self-heal Missing cutlist for MOs whose source order line
        # carries a complete configuration. CAD status is intentionally
        # NOT auto-cleared; only the cutlist blocker is remediable here.
        remediation_note = None
        if not cutlist and self._p3_auto_remediate_enabled():
            order_line = self._p3_source_order_line(production)
            if order_line and self._p3_config_is_complete(order_line):
                package = self._p3_try_emit_package(order_line, production)
                if package:
                    cutlist = self._production_cutlist(production)
                    if cutlist:
                        remediation_note = (
                            "Auto-generated by MI on %s (audit P3 — "
                            "configurator config was complete; "
                            "Missing cutlist self-healed via "
                            "sb.production.package.build_from_order_line)."
                            % fields.Datetime.now()
                        )

        if not cutlist:
            self._create_check(
                {
                    "production_id": production.id,
                    "name": "Missing cutlist",
                    "severity": "blocker",
                    "category": "cut",
                    "message": "Manufacturing intelligence requires a linked cutlist.",
                    "recommendation": "Create or link a production package with a cutlist.",
                }
            )
            # Without this reset, stale yield/waste from a previous
            # cutlist persists after unlink — mirrors the zero-write
            # _recompute_package does below.
            production.write({
                "x_mi_yield_pct": 0.0,
                "x_mi_waste_area_m2": 0.0,
            })
        else:
            if remediation_note:
                # Record the auto-heal as an info check so the audit
                # trail survives a re-run that doesn't re-fire.
                self._create_check(
                    {
                        "production_id": production.id,
                        "name": "Cutlist auto-generated",
                        "severity": "info",
                        "category": "cut",
                        "message": remediation_note,
                        "recommendation": "Verify cutlist before releasing.",
                    }
                )
            summary = self._compute_cut_summary(self._panels_from_cutlist(cutlist))
            production.write(
                {
                    "x_mi_yield_pct": summary["yield_pct"],
                    "x_mi_waste_area_m2": summary["waste_area_m2"],
                }
            )

        if "x_cad_status" in production._fields and production.x_cad_status != "done":
            self._create_check(
                {
                    "production_id": production.id,
                    "name": "CAD not complete",
                    "severity": "warning",
                    "category": "cad",
                    "message": "CAD status is not done.",
                    "recommendation": "Complete CAD before releasing production.",
                }
            )

        checks = self.env["southbrook.mi.check"].sudo().search(
            [("production_id", "=", production.id)]
        )
        severities = checks.mapped("severity")
        production.write(
            {
                "x_mi_status": self._status_from_severities(severities),
                "x_mi_blocker_count": len(checks.filtered(lambda c: c.severity == "blocker")),
                "x_mi_warning_count": len(checks.filtered(lambda c: c.severity == "warning")),
                "x_mi_next_action": self._next_action_from_checks(checks),
            }
        )
        return True

    # ------------------------------------------------------------------
    # P3 — Auto-remediation helpers
    # ------------------------------------------------------------------
    @api.model
    def _p3_auto_remediate_enabled(self):
        flag = self.env["ir.config_parameter"].sudo().get_param(
            self._AUTO_REMEDIATE_FLAG, default="False")
        return str(flag).strip().lower() in ("1", "true", "yes", "on")

    @api.model
    def _p3_source_order_line(self, production):
        """Resolve the sale.order.line that materialised this MO."""
        if not production:
            return self.env["sale.order.line"]
        line = production.sale_line_id
        if line:
            return line
        # Fallback: search by origin = SO.name; useful for MOs created
        # manually that didn't carry sale_line_id at create time.
        origin = production.origin
        if origin:
            order = self.env["sale.order"].search(
                [("name", "=", origin)], limit=1)
            if order:
                for ol in order.order_line:
                    if (ol.product_id and production.product_id
                            and ol.product_id.id == production.product_id.id):
                        return ol
        return self.env["sale.order.line"]

    @api.model
    def _p3_config_is_complete(self, order_line):
        """True iff the configured line has enough data for a deterministic
        cutlist. The audit names "Door Style = 'Custom (Signature)'" as
        the canonical ambiguity case — keep that disqualifier explicit so
        future authors don't drift the heuristic silently.
        """
        if not order_line or not order_line.product_id:
            return False
        picks = order_line.product_id.product_template_attribute_value_ids
        if not picks:
            return False
        # The audit's ambiguity disqualifiers — value names containing
        # "Custom" hint at signature/bespoke specs that the deterministic
        # builder can't safely fill in.
        for ptav in picks:
            val_name = (ptav.product_attribute_value_id.name or "").lower()
            if "custom" in val_name:
                return False
        # Need at least Width for the deterministic geometry.
        for ptav in picks:
            if (ptav.attribute_id.name or "").lower() == "width":
                return True
        # No Width attribute on this template — can't compute geometry.
        return False

    @api.model
    def _p3_try_emit_package(self, order_line, production):
        """Defer to the P1 builder. Logged but never re-raises so a
        remediation hiccup doesn't crash the engine recomputation."""
        try:
            Package = self.env["sb.production.package"]
            return Package.build_from_order_line(order_line, mo=production)
        except Exception:  # noqa: BLE001
            _logger.warning(
                "P3 auto-remediate: build_from_order_line raised for "
                "MO %s / order_line %s — leaving the Missing cutlist "
                "blocker in place.", production.id, order_line.id,
                exc_info=True,
            )
            return self.env["sb.production.package"]

    @api.model
    def _recompute_package(self, package):
        self._unlink_existing_checks(package=package)
        summary = {
            "yield_pct": 0.0,
            "waste_area_m2": 0.0,
            "edge_band_m": 0.0,
        }
        if not package.cutlist_id:
            self._create_check(
                {
                    "production_package_id": package.id,
                    "name": "Missing cutlist",
                    "severity": "blocker",
                    "category": "cut",
                    "message": "Production package has no cutlist.",
                    "recommendation": "Link or generate a cutlist before release.",
                }
            )
        else:
            panels = self._panels_from_cutlist(package.cutlist_id)
            summary = self._compute_cut_summary(panels)
            if summary["yield_pct"] and summary["yield_pct"] < 45:
                self._create_check(
                    {
                        "production_package_id": package.id,
                        "name": "Low sheet yield",
                        "severity": "warning",
                        "category": "cut",
                        "message": "Sheet yield is %.1f%%." % summary["yield_pct"],
                        "recommendation": "Review nesting, duplicate panels, and sheet selection.",
                    }
                )
            for check in self._cut_checks_from_panels(panels, summary):
                check["production_package_id"] = package.id
                self._create_check(check)
            for check in self._assembly_checks_from_panels(panels):
                check["production_package_id"] = package.id
                self._create_check(check)

            hardware_summary = None
            if package.hardware_package_id:
                hardware_summary = {
                    "line_count": package.hardware_package_id.line_count,
                    "state": package.hardware_package_id.state,
                    "has_pricing_pending": package.hardware_package_id.has_pricing_pending,
                }
            for check in self._hardware_checks_from_summary(hardware_summary):
                check["production_package_id"] = package.id
                self._create_check(check)

            if hasattr(package, "_derive_box_dimensions"):
                dimensions = package._derive_box_dimensions()
                if dimensions:
                    for check in self._checks_from_dimensions_result(dimensions):
                        check["production_package_id"] = package.id
                        self._create_check(check)

        checks = self.env["southbrook.mi.check"].sudo().search(
            [("production_package_id", "=", package.id)]
        )
        severities = checks.mapped("severity")
        package.write(
            {
                "x_mi_status": self._status_from_severities(severities),
                "x_mi_yield_pct": summary["yield_pct"],
                "x_mi_waste_area_m2": summary["waste_area_m2"],
                "x_mi_edge_band_m": summary["edge_band_m"],
                "x_mi_blocker_count": len(checks.filtered(lambda c: c.severity == "blocker")),
                "x_mi_warning_count": len(checks.filtered(lambda c: c.severity == "warning")),
                "x_mi_install_warning_count": len(
                    checks.filtered(
                        lambda c: c.category == "install" and c.severity == "warning"
                    )
                ),
                "x_mi_next_action": self._next_action_from_checks(checks),
            }
        )
        return True

    @api.model
    def _checks_from_dimensions_result(self, dimensions):
        if isinstance(dimensions, dict):
            width = dimensions.get("width_mm") or dimensions.get("width")
            height = dimensions.get("height_mm") or dimensions.get("height")
            depth = dimensions.get("depth_mm") or dimensions.get("depth")
        else:
            width, height, depth = dimensions[:3]
        return self._install_checks_from_dimensions(width, height, depth)

    @api.model
    def _next_action_from_checks(self, checks):
        blocker = checks.filtered(lambda c: c.severity == "blocker")[:1]
        if blocker:
            return blocker.recommendation or blocker.message
        warning = checks.filtered(lambda c: c.severity == "warning")[:1]
        if warning:
            return warning.recommendation or warning.message
        return "Manufacturing intelligence checks are clear."
