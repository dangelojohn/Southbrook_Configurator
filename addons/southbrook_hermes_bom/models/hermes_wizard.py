# SPDX-License-Identifier: LGPL-3.0-only
"""Hermes research + BOM-build wizard.

The wizard is a TransientModel — its job is to hold the proposed
enrichment + BOM between the "Research" step and the "Apply" step so
the reviewer can selectively accept fields. Audit lives on
hermes.research.job, which outlives the wizard.

External API call goes through services.hermes_service.HermesService; we
never embed the API key in the wizard record (the key is read fresh from
ir.config_parameter every dispatch).
"""
import base64
import ipaddress
import json
import logging
import socket
from urllib.parse import urlparse

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import html_sanitize

from ..services.hermes_service import HermesService


# Caps on the attach-documents pass. Bounded so a hostile/runaway
# Hermes response can't fill the attachment store.
ATTACH_MAX_BYTES = 8 * 1024 * 1024     # 8 MiB / file
ATTACH_MAX_COUNT = 10                  # at most 10 attachments / run
ATTACH_TIMEOUT_SECONDS = 30            # per-URL HTTP timeout


# ──────────────────────────────────────────────────────────────────
# Pure-Python HTML renderers for the wizard's review form.
#
# The proposed_* JSON fields hold arbitrary Hermes output. The view
# renders the computed *_html fields with widget="html" so the
# reviewer sees a table / linked list instead of raw JSON. All
# user-visible strings flow through escape() to defeat XSS via
# crafted Hermes response.
# ──────────────────────────────────────────────────────────────────
def _esc(s):
    """HTML-escape arbitrary input → str."""
    from markupsafe import escape
    if s is None:
        return ""
    return str(escape(str(s)))


def _parse_json_list(raw):
    if not raw:
        return []
    try:
        v = json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        return []
    if isinstance(v, list):
        return v
    return []


def _render_kv_table(raw, keys):
    """Render a list of {keys[0]: ..., keys[1]: ...} as a 2-col table."""
    items = _parse_json_list(raw)
    if not items:
        return ""
    label_key, value_key = keys
    rows = []
    for item in items:
        if isinstance(item, dict):
            label = _esc(item.get(label_key) or item.get("label") or "")
            value = _esc(item.get(value_key) or item.get("value") or "")
        else:
            label, value = "", _esc(item)
        rows.append(
            "<tr><th class=\"text-start\">%s</th><td>%s</td></tr>"
            % (label, value)
        )
    return "<table class=\"table table-sm\"><tbody>%s</tbody></table>" % (
        "".join(rows),
    )


def _render_text_list(raw):
    items = _parse_json_list(raw)
    if not items:
        return ""
    parts = []
    for item in items:
        if isinstance(item, dict):
            text = _esc(item.get("text") or item.get("note") or item.get(
                "value") or "")
        else:
            text = _esc(item)
        if text:
            parts.append("<li>%s</li>" % text)
    if not parts:
        return ""
    return "<ul>%s</ul>" % "".join(parts)


def _render_url_list(raw):
    """Source URLs rendered as a clickable list. http(s) only."""
    items = _parse_json_list(raw)
    if not items:
        return ""
    parts = []
    for item in items:
        if isinstance(item, dict):
            url = item.get("url") or ""
            label = item.get("label") or url
        else:
            url = str(item) if item else ""
            label = url
        if not url.startswith(("http://", "https://")):
            continue
        parts.append(
            "<li><a href=\"%s\" target=\"_blank\" rel=\"noopener noreferrer\">"
            "%s</a></li>"
            % (_esc(url), _esc(label))
        )
    if not parts:
        return ""
    return "<ul>%s</ul>" % "".join(parts)


def _render_bom_table(raw):
    """Proposed BOM rendered as a table of SKU / Name / Qty rows."""
    if not raw:
        return ""
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        return ""
    if not isinstance(payload, dict):
        return ""
    lines = payload.get("lines") or []
    if not isinstance(lines, list) or not lines:
        return ""
    rows = []
    for line in lines:
        if not isinstance(line, dict):
            continue
        sku = _esc(line.get("sku") or "")
        name = _esc(line.get("name") or "")
        qty = _esc(line.get("qty") or "")
        rows.append(
            "<tr><td>%s</td><td>%s</td><td class=\"text-end\">%s</td></tr>"
            % (sku, name, qty)
        )
    return (
        "<table class=\"table table-sm\">"
        "<thead><tr>"
        "<th>SKU</th><th>Name</th><th class=\"text-end\">Qty</th>"
        "</tr></thead>"
        "<tbody>%s</tbody></table>"
    ) % "".join(rows)

_logger = logging.getLogger(__name__)


# Fields that may be overwritten only when (a) the existing value is
# empty/False, or (b) the per-field confidence in the Hermes response
# meets HIGH_CONFIDENCE_THRESHOLD, or (c) the reviewer explicitly opts
# in. Order is the display order in the review dialog.
#
# Manufacturer / manufacturer_pn are deliberately NOT in this map:
# the closest target fields (x_hardware_brand_id / x_marathon_sku) are
# Marathon-Hardware-specific and overwriting them auto-magically would
# corrupt the hardware-catalog source of truth. Those proposed values
# still appear in the review form and the chatter summary; applying
# them is left to the reviewer.
ENRICHMENT_FIELD_MAP = [
    # (proposed_field_on_wizard, target_field_on_product_template, label)
    ("proposed_name", "name", "Name"),
    ("proposed_short_description", "description_sale", "Sales Description"),
    ("proposed_long_description", "description", "Internal Notes"),
    ("proposed_technical_description", "description_purchase",
     "Purchase Description"),
]

HIGH_CONFIDENCE_THRESHOLD = 0.85

# Fields that appear on customer-facing documents (quote/PDF). In demo mode
# these are NEVER written to the product master — even to an empty value —
# so mock/demo enrichment text can't reach a customer. (L3 fix 2026-07-06:
# demo mode previously overwrote description_sale via a fake 0.9 confidence;
# the confidence is now low, but this is the hard guarantee that demo text
# can't leak even into a product whose description was blank.)
CUSTOMER_VISIBLE_ENRICHMENT_FIELDS = ("name", "description_sale")

# Marker stored on bom.code so we can identify Hermes-managed BOMs
# without bolting a new field onto mrp.bom.
HERMES_BOM_CODE_SUFFIX = "Hermes"

# Stable, module-scoped advisory-lock namespace (high 32 bits of the
# (key1, key2) pair to pg_advisory_xact_lock). The exact value doesn't
# matter — just that it doesn't collide with other modules in the
# southbrook stack. Chosen by hashing the module name; baked in so
# future redeploys keep the same key and old-cursor locks still match.
HERMES_BOM_LOCK_NS = 0x48424F4D  # "HBOM" in ASCII as int

# Placeholder names we treat as overwriteable even when "non-empty"
# (Odoo's product create-from-form default).
PLACEHOLDER_NAMES = {"", "e.g. Cheese Burger", "New", "False", None}


class HermesWizard(models.TransientModel):
    _name = "hermes.wizard"
    _description = "Hermes Research Wizard"

    job_id = fields.Many2one(
        comodel_name="hermes.research.job",
        required=True,
        ondelete="cascade",
    )
    product_template_id = fields.Many2one(
        related="job_id.product_template_id",
        store=False,
        readonly=False,
    )
    state = fields.Selection(
        selection=[
            ("collecting", "Collecting"),
            ("researching", "Researching"),
            ("review", "Review"),
            ("applying", "Applying"),
            ("done", "Done"),
            ("error", "Error"),
        ],
        default="collecting",
        required=True,
    )
    status_message = fields.Char(string="Status")

    # ── Proposed enrichment ─────────────────────────────────────────
    proposed_name = fields.Char(string="Proposed Name")
    proposed_short_description = fields.Text(string="Proposed Short Description")
    proposed_long_description = fields.Html(string="Proposed Long Description")
    proposed_technical_description = fields.Text(
        string="Proposed Technical Description")
    proposed_manufacturer = fields.Char(string="Proposed Manufacturer")
    proposed_manufacturer_pn = fields.Char(string="Proposed Manufacturer P/N")
    proposed_dimensions_json = fields.Text(string="Proposed Dimensions (JSON)")
    proposed_specs_json = fields.Text(string="Proposed Specs (JSON)")
    proposed_install_notes_json = fields.Text(
        string="Proposed Install Notes (JSON)")
    proposed_bom_json = fields.Text(string="Proposed BOM (JSON)")
    source_urls_json = fields.Text(string="Source URLs (JSON)")
    confidence_score = fields.Float(string="Confidence (0..1)")

    # ── Reviewer toggles ────────────────────────────────────────────
    apply_enrichment = fields.Boolean(string="Apply Enrichment", default=True)
    apply_bom = fields.Boolean(string="Apply BOM", default=True)
    apply_attachments = fields.Boolean(string="Apply Attachments", default=True)
    apply_chatter_note = fields.Boolean(
        string="Post Summary to Chatter", default=True)

    # ── Existing-BOM disposition ────────────────────────────────────
    existing_bom_id = fields.Many2one(
        comodel_name="mrp.bom", string="Existing Hermes BOM")
    existing_bom_state = fields.Selection(
        selection=[
            ("none", "None"),
            ("draft", "Draft (will be replaced)"),
            ("confirmed", "Confirmed (replace blocked)"),
        ],
        default="none",
    )

    user_notes = fields.Text(string="Reviewer Notes")
    error_detail = fields.Text(string="Error Detail")

    # ── Early validation (before dispatch) ─────────────────────────
    # Computed rather than stored so a config-parameter change (e.g.
    # setting the api_key or flipping demo_mode) is reflected the next
    # time the wizard form is opened/refreshed, with no stale value to
    # worry about.
    hermes_available = fields.Boolean(
        string="Hermes Runnable", compute="_compute_hermes_available",
    )
    hermes_config_hint = fields.Char(
        string="Hermes Config Hint", compute="_compute_hermes_available",
    )

    @api.depends_context("uid")
    def _compute_hermes_available(self):
        ICP = self.env["ir.config_parameter"].sudo()
        api_key = ICP.get_param("southbrook_hermes_bom.api_key", "")
        # Share the service's single demo-mode source of truth so this
        # UI gate can't drift from what research() actually does.
        demo_mode = HermesService.is_demo_mode(self.env)
        available = bool(demo_mode or api_key)
        hint = "" if available else _(
            "Hermes can't run: set the 'southbrook_hermes_bom.api_key' "
            "System Parameter, or enable demo mode "
            "('southbrook_hermes_bom.demo_mode') to test offline."
        )
        for w in self:
            w.hermes_available = available
            w.hermes_config_hint = hint

    # ── Current-side mirrors of product.template (read-only) ──────
    # Surfaced so the review form can show "current vs proposed" side
    # by side without the view having to dot-walk job_id →
    # product_template_id.* (which 19's view validator dislikes
    # inside notebook pages with multiple readonly target paths).
    current_name = fields.Char(
        string="Current Name",
        related="product_template_id.name", readonly=True,
    )
    current_description = fields.Html(
        string="Current Internal Notes",
        related="product_template_id.description", readonly=True,
    )
    current_description_sale = fields.Text(
        string="Current Sales Description",
        related="product_template_id.description_sale", readonly=True,
    )
    current_description_purchase = fields.Text(
        string="Current Purchase Description",
        related="product_template_id.description_purchase", readonly=True,
    )

    # ── Parsed-HTML render targets ────────────────────────────────
    # Computed on the fly from the corresponding *_json columns so
    # the form view can render with widget="html" instead of raw JSON.
    dimensions_html = fields.Html(
        string="Dimensions",
        compute="_compute_render_jsons", sanitize=True,
    )
    specs_html = fields.Html(
        string="Specs",
        compute="_compute_render_jsons", sanitize=True,
    )
    install_notes_html = fields.Html(
        string="Install Notes",
        compute="_compute_render_jsons", sanitize=True,
    )
    source_urls_html = fields.Html(
        string="Sources",
        compute="_compute_render_jsons", sanitize=True,
    )
    proposed_bom_html = fields.Html(
        string="Proposed BOM",
        compute="_compute_render_jsons", sanitize=True,
    )

    @api.depends("proposed_dimensions_json", "proposed_specs_json",
                 "proposed_install_notes_json", "source_urls_json",
                 "proposed_bom_json")
    def _compute_render_jsons(self):
        for w in self:
            w.dimensions_html = _render_kv_table(
                w.proposed_dimensions_json, ("label", "value")
            )
            w.specs_html = _render_kv_table(
                w.proposed_specs_json, ("name", "value")
            )
            w.install_notes_html = _render_text_list(
                w.proposed_install_notes_json
            )
            w.source_urls_html = _render_url_list(w.source_urls_json)
            w.proposed_bom_html = _render_bom_table(w.proposed_bom_json)

    # ============================================================
    # Step 1 — collect + dispatch
    # ============================================================
    def action_collect_and_research(self):
        """Build the outbound payload, call Hermes, populate review fields."""
        self.ensure_one()
        if not self.product_template_id:
            raise UserError(_("No product template attached to this wizard."))
        self.write({
            "state": "researching",
            "status_message": _("Collecting product context…"),
        })
        payload = self._collect_product_payload()
        self.job_id.sudo().write({
            "state": "running",
            "hermes_request_payload": json.dumps(payload, default=str),
        })
        self.write({"status_message": _("Calling Hermes…")})
        service = HermesService(self.env)
        try:
            response = service.research(payload)
        except UserError:
            self._mark_error(_("Hermes call failed (see job)."))
            raise
        except Exception as exc:  # noqa: BLE001 — convert to user-visible
            _logger.exception("Hermes dispatch crashed")
            self._mark_error(str(exc))
            raise UserError(
                _("Hermes call failed: %s") % exc
            ) from exc

        self.job_id.sudo().write({
            "hermes_raw_response": json.dumps(response, default=str),
        })
        self._populate_from_response(response)
        self._detect_existing_bom()
        self.write({
            "state": "review",
            "status_message": _("Review proposed changes"),
        })
        self.job_id.sudo().write({"state": "review"})
        return self._reload_action()

    def _collect_product_payload(self):
        """Build the structured payload sent to Hermes.

        Uses only fields verified to exist on this codebase (see the
        inspection step that preceded the build) — anything optional is
        guarded by hasattr so the addon survives in deployments where a
        sibling module is absent.
        """
        self.ensure_one()
        t = self.product_template_id

        def get_attr(field):
            return getattr(t, field) if hasattr(t, field) else None

        attribute_lines = [
            {
                "attribute_name": line.attribute_id.name,
                "values": line.value_ids.mapped("name"),
            }
            for line in t.attribute_line_ids
        ]
        config_restrictions = []
        for line in t.config_line_ids:
            config_restrictions.append({
                "attribute_line": (
                    line.attribute_line_id.attribute_id.name
                    if line.attribute_line_id else ""
                ),
                "values": line.value_ids.mapped("name"),
                "domain_rule": line.domain_id.name if line.domain_id else "",
            })
        config_steps = []
        for step_line in t.config_step_line_ids:
            step = step_line.config_step_id
            config_steps.append({
                "name": step.name,
                "sequence": step_line.sequence,
                "attribute_lines": [
                    al.attribute_id.name
                    for al in step_line.attribute_line_ids
                ],
            })

        session = self.env["product.config.session"].search(
            [
                ("product_tmpl_id", "=", t.id),
                ("state", "=", "done"),
            ],
            order="id desc",
            limit=1,
        )
        latest_session = {}
        if session:
            latest_session = {
                "session_id": session.id,
                "reference": session.name,
                "selected_values": session.value_ids.mapped("name"),
                "price": session.price,
                "weight": session.weight,
            }

        existing_boms = [
            {
                "id": bom.id,
                "reference": bom.code or "",
                "type": bom.type,
                "configurable": bool(bom.config_ok),
                "component_count": len(bom.bom_line_ids),
            }
            for bom in t.bom_ids
        ]

        return {
            "product_template_id": t.id,
            "product_name": t.name,
            "internal_reference": t.default_code,
            "barcode": t.barcode,
            "category": t.categ_id.name if t.categ_id else None,
            "sales_price": t.list_price,
            "cost": t.standard_price,
            "product_type": t.type,
            "internal_notes": t.description or "",
            "onshape_cad_url": get_attr("x_onshape_cad_url") or "",
            "southbrook_category": get_attr("southbrook_category") or "",
            "southbrook_description": get_attr("southbrook_description") or "",
            "southbrook_dimensions": get_attr("southbrook_dimensions") or "",
            "hardware_category": get_attr("x_hardware_category") or "",
            "hardware_brand": (
                t.x_hardware_brand_id.name
                if hasattr(t, "x_hardware_brand_id") and t.x_hardware_brand_id
                else ""
            ),
            "marathon_sku": get_attr("x_marathon_sku") or "",
            "attribute_lines": attribute_lines,
            "configuration_restrictions": config_restrictions,
            "configuration_steps": config_steps,
            "latest_configuration_session": latest_session,
            "existing_boms": existing_boms,
            "user_notes": self.user_notes or "",
        }

    def _clip(self, text, limit):
        """Coerce untrusted Hermes text to a safe, bounded plain string.

        Hermes output is external, untrusted content. Before it lands
        in a Char/Text field we (a) coerce to str, (b) strip ASCII
        control characters other than newline/tab (defends against a
        response smuggling e.g. terminal escapes or NUL bytes into
        chatter/exports), and (c) truncate to `limit` characters so a
        runaway/hostile response can't blow up a Char column or the
        review form. long_description is exempt — it's Html and
        already goes through html_sanitize() separately.
        """
        s = "" if text is None else str(text)
        s = "".join(
            ch for ch in s
            if ch in ("\n", "\t") or (ord(ch) >= 0x20 and ord(ch) != 0x7F)
        )
        return s[:limit]

    # Hard cap on the number of items kept from any list-shaped
    # enrichment field, so a runaway/hostile (real) Hermes response
    # can't produce a giant JSON blob / heavy review-form HTML table.
    _MAX_LIST_ITEMS = 50

    def _clip_list(self, seq):
        """Return a list of at most _MAX_LIST_ITEMS from `seq`; [] if it
        isn't a list (untrusted Hermes output)."""
        if not isinstance(seq, list):
            return []
        return seq[: self._MAX_LIST_ITEMS]

    def _cap_bom(self, bom):
        """Return the bom dict with its `lines` capped to _MAX_LIST_ITEMS.
        Non-dict / missing-lines input degrades to a safe empty shape."""
        if not isinstance(bom, dict):
            return {}
        capped = dict(bom)
        if isinstance(capped.get("lines"), list):
            capped["lines"] = capped["lines"][: self._MAX_LIST_ITEMS]
        return capped

    def _populate_from_response(self, response):
        """Stash response fields onto the wizard for the review form."""
        enrichment = response.get("product_enrichment", {}) or {}
        bom = response.get("bom", {}) or {}
        audit = response.get("audit", {}) or {}

        vals = {
            "proposed_name": self._clip(enrichment.get("name") or "", 256),
            "proposed_short_description": self._clip(
                enrichment.get("short_description") or "", 1024),
            "proposed_long_description": html_sanitize(
                enrichment.get("long_description") or "",
            ),
            "proposed_technical_description": self._clip(
                enrichment.get("technical_description") or "", 8192),
            "proposed_manufacturer": self._clip(
                enrichment.get("manufacturer") or "", 256),
            "proposed_manufacturer_pn": self._clip(
                enrichment.get("manufacturer_pn") or "", 128),
            "proposed_dimensions_json": json.dumps(
                self._clip_list(enrichment.get("dimensions")), default=str),
            "proposed_specs_json": json.dumps(
                self._clip_list(enrichment.get("specs")), default=str),
            "proposed_install_notes_json": json.dumps(
                self._clip_list(enrichment.get("install_notes")), default=str),
            "proposed_bom_json": json.dumps(self._cap_bom(bom), default=str),
            "source_urls_json": json.dumps(
                self._clip_list(audit.get("source_urls")), default=str),
            "confidence_score": float(
                audit.get("overall_confidence", 0.0) or 0.0
            ),
        }
        self.write(vals)
        self.job_id.sudo().write({
            "hermes_parsed_enrichment": json.dumps(enrichment, default=str),
            "hermes_parsed_bom": json.dumps(bom, default=str),
            "source_urls": vals["source_urls_json"],
            "confidence_summary": "%.0f%%" % (vals["confidence_score"] * 100),
        })

    def _detect_existing_bom(self):
        """Set existing_bom_id / existing_bom_state based on prior Hermes runs."""
        bom = self._find_hermes_bom()
        if not bom:
            self.write({
                "existing_bom_id": False,
                "existing_bom_state": "none",
            })
            return
        # mrp.bom doesn't carry a "state" in core (it's always editable until
        # consumed). We approximate "confirmed" as "has been used by an MO".
        used = bool(self.env["mrp.production"].sudo().search_count([
            ("bom_id", "=", bom.id)
        ]))
        self.write({
            "existing_bom_id": bom.id,
            "existing_bom_state": "confirmed" if used else "draft",
        })

    def _hermes_bom_code(self):
        """Canonical code for the Hermes-managed BOM on this template.

        Deliberately deterministic: `<default_code> Hermes`. Detection
        and creation use the same expression so we never see a
        substring-match false positive against a user-created BOM
        with 'Hermes' in its name (e.g. 'Hermes Special Edition').
        """
        return "%s %s" % (
            self.product_template_id.default_code or "",
            HERMES_BOM_CODE_SUFFIX,
        )

    def _find_hermes_bom(self):
        return self.env["mrp.bom"].search(
            [
                ("product_tmpl_id", "=", self.product_template_id.id),
                ("code", "=", self._hermes_bom_code()),
            ],
            limit=1,
        )

    # ============================================================
    # Step 2 — apply
    # ============================================================
    def action_apply(self):
        self.ensure_one()
        if self.state != "review":
            raise UserError(_("Wizard is not in review state."))
        self.write({
            "state": "applying",
            "status_message": _("Applying changes…"),
        })
        applied = []
        if self.apply_enrichment:
            applied.extend(self._apply_enrichment())
        if self.apply_bom:
            applied.extend(self._apply_bom())
        if self.apply_attachments:
            applied.extend(self._attach_documents())
        if self.apply_chatter_note:
            self._post_chatter_summary(applied)

        self.job_id.sudo().write({
            "state": "applied",
            "applied_fields": json.dumps(applied, default=str),
        })
        self.write({
            "state": "done",
            "status_message": _("Applied %d changes") % len(applied),
        })
        return {
            "type": "ir.actions.act_window",
            "name": _("Product Template"),
            "res_model": "product.template",
            "res_id": self.product_template_id.id,
            "view_mode": "form",
            "target": "current",
        }

    def _apply_enrichment(self):
        """Write proposed_* fields to product.template under safety rules.

        Rules (the spec calls these out explicitly):
          * Never overwrite a non-empty existing value unless confidence
            >= HIGH_CONFIDENCE_THRESHOLD OR the reviewer opted in (which
            we represent as the wizard's apply_enrichment toggle being
            on AND the field being non-empty in the proposed payload).
          * Names get the placeholder treatment — overwrite blank names
            and the Odoo "e.g. Cheese Burger" placeholder freely.
        """
        applied = []
        t = self.product_template_id
        confidence = self.confidence_score or 0.0
        demo_mode = HermesService.is_demo_mode(self.env)
        for wizard_field, target_field, label in ENRICHMENT_FIELD_MAP:
            proposed = self[wizard_field]
            if not proposed:
                continue
            if demo_mode and target_field in CUSTOMER_VISIBLE_ENRICHMENT_FIELDS:
                # Demo/mock text must never reach a customer-facing field,
                # regardless of confidence or whether the target is empty.
                _logger.info(
                    "Demo mode: skipping customer-visible field %s "
                    "(would have written mock enrichment text).", target_field
                )
                continue
            if not hasattr(t, target_field):
                _logger.warning(
                    "Skipping enrichment field %s — not present on "
                    "product.template in this deployment.", target_field
                )
                continue
            current = t[target_field]
            if target_field == "name":
                # Names: overwrite only when blank or placeholder
                if current and str(current).strip() not in PLACEHOLDER_NAMES:
                    if confidence < HIGH_CONFIDENCE_THRESHOLD:
                        _logger.warning(
                            "Refusing to overwrite non-placeholder product "
                            "name '%s' with low-confidence proposal "
                            "(score=%.2f).", current, confidence
                        )
                        continue
            else:
                if current and confidence < HIGH_CONFIDENCE_THRESHOLD:
                    _logger.warning(
                        "Refusing to overwrite non-empty %s "
                        "(confidence=%.2f).", target_field, confidence
                    )
                    continue
            t.write({target_field: proposed})
            applied.append({
                "model": "product.template",
                "field": target_field,
                "label": label,
                "old": str(current) if current else "",
                "new": str(proposed),
            })
        return applied

    def _apply_bom(self):
        """Create or update the Hermes-managed BOM.

        Idempotency rules:
          * Search for a BOM on this template whose code contains
            "Hermes".
          * If found AND we know it has been used by an MO
            (existing_bom_state == 'confirmed'): refuse.
          * If found AND not used: drop+recreate its lines, update its
            code.
          * If not found: create new with `code = "<SKU> Hermes"`.
        """
        applied = []
        try:
            bom_payload = json.loads(self.proposed_bom_json or "{}")
        except json.JSONDecodeError as exc:
            raise UserError(_("Proposed BOM JSON is invalid: %s") % exc) from exc
        # A reviewer can hand-edit proposed_bom_json — valid JSON that isn't an
        # object (e.g. `["x"]`) would AttributeError on .get() below.
        if not isinstance(bom_payload, dict):
            raise UserError(_("Proposed BOM JSON must be an object."))
        lines_payload = bom_payload.get("lines") or []
        if not lines_payload:
            _logger.info("Hermes BOM payload empty — skipping BOM apply.")
            return applied

        # Postgres advisory lock keyed by template id. Held until end
        # of transaction; serializes _find_hermes_bom → create across
        # concurrent reviewers so two simultaneous applies can't both
        # see "no existing BOM" and create duplicates. The first arg
        # is a stable namespace hash so we don't collide with other
        # modules' advisory locks.
        self.env.cr.execute(
            "SELECT pg_advisory_xact_lock(%s, %s)",
            (HERMES_BOM_LOCK_NS, self.product_template_id.id),
        )
        existing = self._find_hermes_bom()
        # TOCTOU re-check: existing_bom_state was captured at research
        # time. A foreign MO could have started referencing this BOM
        # between research and apply. Re-evaluate against live state.
        if existing:
            consumed_now = self.env["mrp.production"].sudo().search_count([
                ("bom_id", "=", existing.id),
            ])
            if consumed_now:
                raise UserError(_(
                    "A Hermes-managed BOM for this product has already "
                    "been used in a manufacturing order. Archive or "
                    "detach it before running Hermes again."
                ))

        bom_code = self._hermes_bom_code()
        bom_type = bom_payload.get("bom_type") or "normal"
        # Only Community-supported mrp.bom.type values. 'subcontract' is
        # an Enterprise selection — accepting it would raise ValueError
        # on the create/write below.
        if bom_type not in ("normal", "phantom"):
            _logger.warning(
                "Hermes proposed unsupported bom_type=%r — falling back "
                "to 'normal'.", bom_type
            )
            bom_type = "normal"

        ProductProduct = self.env["product.product"]
        new_line_vals = []
        missing = []
        for line in lines_payload:
            if not isinstance(line, dict):
                missing.append(str(line)[:60])
                continue
            sku = (line.get("sku") or "").strip()
            name = (line.get("name") or "").strip()
            # qty is required and must be positive. Silently defaulting
            # to 1.0 hid malformed Hermes responses where a 4-pack was
            # written as qty=None and shipped as qty=1.
            raw_qty = line.get("qty")
            try:
                qty = float(raw_qty) if raw_qty is not None else 0.0
            except (TypeError, ValueError):
                qty = 0.0
            if qty <= 0.0:
                missing.append({"sku": sku, "name": name,
                                "reason": "invalid_qty"})
                continue
            product = self.env["product.product"]
            if sku:
                product = ProductProduct.search(
                    [("default_code", "=", sku), ("active", "=", True)],
                    limit=1,
                )
            if not product and name:
                product = ProductProduct.search(
                    [("name", "=", name), ("active", "=", True)],
                    order="id asc", limit=1,
                )
            if not product:
                missing.append({"sku": sku, "name": name,
                                "reason": "not_found"})
                continue
            new_line_vals.append((0, 0, {
                "product_id": product.id,
                "product_qty": qty,
            }))

        # If every proposed line failed matching/validation, do NOT
        # destroy the existing Hermes BOM by writing an empty
        # bom_line_ids set. Surface the problem and bail.
        if not new_line_vals:
            self.product_template_id.message_post(body=_(
                "Hermes: every proposed BOM line was unmatched or "
                "invalid; existing BOM left untouched. Skipped: %s"
            ) % ", ".join(
                "%s/%s (%s)" % (
                    m.get("sku"), m.get("name"), m.get("reason"),
                ) for m in missing
            ))
            _logger.warning(
                "Hermes BOM apply produced zero valid lines for "
                "template %s; refusing to touch existing BOM.",
                self.product_template_id.id,
            )
            return applied

        if existing:
            existing.bom_line_ids.unlink()
            existing.write({
                "code": bom_code,
                "type": bom_type,
                "config_ok": True,
                "bom_line_ids": new_line_vals,
            })
            bom = existing
            applied.append({
                "model": "mrp.bom",
                "field": "bom_line_ids",
                "label": "BOM lines",
                "old": "(replaced)",
                "new": "%d lines" % len(new_line_vals),
            })
        else:
            bom = self.env["mrp.bom"].create({
                "product_tmpl_id": self.product_template_id.id,
                "code": bom_code,
                "type": bom_type,
                "config_ok": True,
                "bom_line_ids": new_line_vals,
            })
            applied.append({
                "model": "mrp.bom",
                "field": "_create",
                "label": "BOM created",
                "old": "",
                "new": bom_code,
            })

        self.job_id.sudo().write({"bom_id": bom.id})

        if missing:
            self.product_template_id.message_post(body=_(
                "Hermes: %d proposed BOM line(s) could not be matched "
                "to existing products and were skipped: %s"
            ) % (len(missing), ", ".join(
                "%s/%s" % (m.get("sku"), m.get("name")) for m in missing
            )))
        return applied

    @staticmethod
    def _is_safe_public_url(url):
        """SSRF guard: True only if every IP the host resolves to is a
        global/public address. Hermes is an AI agent (prompt-injectable,
        explicitly untrusted), so a manipulated source_url could point at
        cloud-metadata (169.254.169.254), loopback, or an internal service.
        Rejects private/loopback/link-local/reserved/multicast ranges.
        """
        try:
            parsed = urlparse(url)
            if parsed.scheme not in ("http", "https"):
                return False
            host = parsed.hostname
            if not host:
                return False
            infos = socket.getaddrinfo(host, None)
        except (ValueError, OSError):
            return False
        for info in infos:
            ip_str = info[4][0]
            try:
                ip = ipaddress.ip_address(ip_str)
            except ValueError:
                return False
            if not ip.is_global or ip.is_reserved or ip.is_multicast:
                return False
        return True

    def _attach_documents(self):
        """Fetch each source URL and attach the response to the template.

        Bounded by ATTACH_MAX_BYTES per file and ATTACH_MAX_COUNT total
        so a hostile or runaway Hermes response can't fill the
        attachment store. URLs that 404, time out, or exceed the size
        cap are listed in the chatter so the reviewer knows what was
        skipped. Returns the list of applied-fields entries (one per
        successfully attached file).
        """
        applied = []
        try:
            urls = json.loads(self.source_urls_json or "[]") or []
        except (TypeError, ValueError, json.JSONDecodeError):
            urls = []
        if not urls:
            return applied
        urls = [u for u in urls if isinstance(u, str) and u.startswith(
            ("http://", "https://"))][:ATTACH_MAX_COUNT]
        if not urls:
            return applied
        try:
            import requests
        except ImportError:
            _logger.warning(
                "Hermes _attach_documents: `requests` unavailable; "
                "skipping source download."
            )
            return applied

        skipped = []
        for url in urls:
            # SSRF guard: block private/loopback/metadata hosts, and disable
            # redirects (a public URL could 3xx-bounce to an internal host).
            if not self._is_safe_public_url(url):
                skipped.append("%s (blocked: non-public host)" % url)
                continue
            try:
                resp = requests.get(
                    url, timeout=ATTACH_TIMEOUT_SECONDS, stream=True,
                    allow_redirects=False,
                )
                resp.raise_for_status()
                # Read with a hard size cap; abort if the source is too big.
                data = bytearray()
                for chunk in resp.iter_content(chunk_size=16384):
                    data.extend(chunk)
                    if len(data) > ATTACH_MAX_BYTES:
                        skipped.append("%s (too large)" % url)
                        data = None
                        break
                if data is None:
                    continue
                name = url.rsplit("/", 1)[-1] or "hermes_source"
                # Strip query string from filename.
                if "?" in name:
                    name = name.split("?", 1)[0]
                if len(name) > 120:
                    name = name[:120]
                self.env["ir.attachment"].sudo().create({
                    "name": "Hermes: %s" % name,
                    "datas": base64.b64encode(bytes(data)).decode("ascii"),
                    "res_model": "product.template",
                    "res_id": self.product_template_id.id,
                    "description": "Hermes source URL: %s" % url,
                })
                applied.append({
                    "model": "ir.attachment",
                    "field": "datas",
                    "label": "Source attachment",
                    "old": "",
                    "new": name,
                })
            except requests.exceptions.Timeout:
                skipped.append("%s (timeout)" % url)
            except requests.exceptions.RequestException as exc:
                skipped.append("%s (%s)" % (url, type(exc).__name__))
            except Exception as exc:  # noqa: BLE001
                _logger.exception(
                    "Hermes _attach_documents unexpected failure for %s", url,
                )
                skipped.append("%s (%s)" % (url, type(exc).__name__))

        if skipped:
            self.product_template_id.message_post(body=_(
                "Hermes: %(n)d source URL(s) could not be attached: "
                "%(list)s"
            ) % {"n": len(skipped), "list": "; ".join(skipped)})
        return applied

    def _post_chatter_summary(self, applied):
        # Named-token .format keeps translations TypeError-safe: a
        # translator can reorder or drop tokens by name without
        # breaking the call site (positional %s would raise).
        body = _(
            "<b>Hermes research applied</b><br/>"
            "Confidence: {confidence}<br/>"
            "Changes: {count} field(s)/record(s)<br/>"
            "Job: {job}"
        ).format(
            confidence=self.job_id.confidence_summary or "?",
            count=len(applied),
            job=self.job_id.name,
        )
        self.product_template_id.message_post(body=body)
        self.job_id.message_post(body=body)

    # ============================================================
    # Helpers
    # ============================================================
    def _mark_error(self, msg):
        """Persist the failure even when the caller re-raises.

        The wizard's action methods convert most failures back into a
        UserError so the browser-side widget can display them. Re-raise
        rolls back the surrounding HTTP-dispatcher savepoint, which
        otherwise erases the state='error' writes we just made — the
        audit row ends up frozen at state='running' and the job looks
        stuck. Writing through a fresh cursor keeps the audit row
        regardless of what the outer transaction does.
        """
        wizard_id, job_id = self.id, self.job_id.id
        try:
            with self.env.registry.cursor() as cr:
                env = self.env(cr=cr)
                env["hermes.wizard"].browse(wizard_id).write({
                    "state": "error", "error_detail": msg,
                })
                env["hermes.research.job"].browse(job_id).write({
                    "state": "failed", "error_message": msg,
                })
        except Exception:  # noqa: BLE001
            _logger.exception(
                "Hermes _mark_error failed to persist failure for "
                "wizard %s / job %s", wizard_id, job_id,
            )

    def _reload_action(self):
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    @api.constrains("confidence_score")
    def _check_confidence_bounds(self):
        for w in self:
            if w.confidence_score and not (0.0 <= w.confidence_score <= 1.0):
                raise ValidationError(_(
                    "Confidence score must be between 0.0 and 1.0."
                ))
