# SPDX-License-Identifier: LGPL-3.0-only
import math
import json

from odoo import api, models


class SouthbrookMiEngine(models.AbstractModel):
    _name = "southbrook.mi.engine"
    _description = "Southbrook Manufacturing Intelligence Engine"

    @api.model
    def _stage_values(self, stage, sequence, is_gate=True, workcenter=False):
        values = {
            "stage": stage,
            "sequence": sequence,
            "is_gate": is_gate,
        }
        if workcenter:
            values["workcenter_id"] = workcenter.id
        return values

    @api.model
    def _stage_rollup_from_checks(self, checks):
        stages = [
            "saw",
            "cnc",
            "edgeband",
            "assembly",
            "finish_qc",
            "delivery",
            "install",
        ]
        rollup = {
            "x_mi_blocked_stage": False,
            "x_mi_next_stage_action": False,
        }
        for stage in stages:
            rollup["x_mi_%s_blocker_count" % stage] = len(
                checks.filtered(
                    lambda c, stage=stage: c.stage == stage
                    and c.severity == "blocker"
                )
            )
        blocker = checks.filtered(lambda c: c.severity == "blocker").sorted(
            key=lambda c: (c.sequence or 100, c.id)
        )[:1]
        if blocker:
            rollup["x_mi_blocked_stage"] = blocker.stage
            rollup["x_mi_next_stage_action"] = (
                blocker.recommendation or blocker.message
            )
            return rollup
        warning = checks.filtered(lambda c: c.severity == "warning").sorted(
            key=lambda c: (c.sequence or 100, c.id)
        )[:1]
        if warning:
            rollup["x_mi_next_stage_action"] = (
                warning.recommendation or warning.message
            )
        return rollup

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
    def _cut_batching_checks_from_summary(self, summary):
        checks = []
        for group in (summary or {}).get("duplicate_groups", []):
            qty = group.get("qty") or 0
            if qty < 4:
                continue
            checks.append(
                {
                    "name": "Batch cut duplicate panels",
                    "severity": "info",
                    "category": "cut",
                    "message": "%s identical panels at %.0f x %.0f x %.0f mm."
                    % (
                        qty,
                        group.get("length_mm") or 0,
                        group.get("width_mm") or 0,
                        group.get("thickness_mm") or 0,
                    ),
                    "recommendation": "Batch cut and label these parts together to reduce saw setup time and part mix-ups.",
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
    def _material_handling_checks_from_panels(self, panels):
        checks = []
        density_by_substrate = {
            "melamine_white_5_8": 680.0,
            "melamine_oak_5_8": 680.0,
            "mdf_5_8": 750.0,
            "ply_3_4": 600.0,
            "hardboard_1_4": 900.0,
        }
        for panel in panels:
            length = panel.get("length_mm") or 0.0
            width = panel.get("width_mm") or 0.0
            thickness = panel.get("thickness_mm") or 0.0
            if not length or not width or not thickness:
                continue
            density = density_by_substrate.get(panel.get("substrate"), 680.0)
            weight_kg = length * width * thickness * density / 1000000000.0
            name = panel.get("panel_name") or "Panel"
            if weight_kg >= 60.0:
                checks.append(
                    {
                        "name": "Mechanical lift required",
                        "severity": "blocker",
                        "category": "assembly",
                        "message": "%s is estimated at %.1f kg." % (name, weight_kg),
                        "recommendation": "Plan lift equipment, staging space, and extra handling before cutting or assembly.",
                    }
                )
            elif weight_kg >= 23.0:
                checks.append(
                    {
                        "name": "Two-person panel handling",
                        "severity": "warning",
                        "category": "assembly",
                        "message": "%s is estimated at %.1f kg." % (name, weight_kg),
                        "recommendation": "Assign two-person handling and confirm the panel path through saw, edgebander, and assembly.",
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
        if height_mm and depth_mm:
            tip_up_diagonal_mm = math.sqrt((height_mm * height_mm) + (depth_mm * depth_mm))
            if tip_up_diagonal_mm >= 2440:
                checks.append(
                    {
                        "name": "Tip-up clearance review",
                        "severity": "warning",
                        "category": "install",
                        "message": "Cabinet tip-up diagonal is %.0f mm."
                        % tip_up_diagonal_mm,
                        "recommendation": "Confirm ceiling height, soffits, lights, sprinklers, and the actual path before delivery.",
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

    @api.model
    def _recompute_production(self, production):
        self._unlink_existing_checks(production=production)
        cutlist = self._production_cutlist(production)
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
        else:
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
            for check in self._cut_batching_checks_from_summary(summary):
                check["production_package_id"] = package.id
                self._create_check(check)
            for check in self._assembly_checks_from_panels(panels):
                check["production_package_id"] = package.id
                self._create_check(check)
            for check in self._material_handling_checks_from_panels(panels):
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
