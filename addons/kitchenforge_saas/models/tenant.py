# SPDX-License-Identifier: LGPL-3.0-only
"""KitchenForge tenant — one record per cabinet-shop subscriber.

Mirrors the QNAP demo-stack pattern (per-tenant docker-compose + Caddy
snippet) as a first-class Odoo model. The Odoo addon is the control plane:
status, billing, lifecycle, and an audit log. The actual docker side is
owned by an off-Odoo provisioner reachable via webhook.
"""
import logging
import re
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$")


class KitchenForgeTenant(models.Model):
    _name = "kitchenforge.tenant"
    _description = "KitchenForge Tenant"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc"
    _rec_name = "name"

    # --- Identity ------------------------------------------------------
    name = fields.Char(required=True, tracking=True)
    slug = fields.Char(
        required=True, copy=False, index=True, tracking=True,
        help="Kebab-case identifier used as the subdomain "
             "`<slug>.kitchenforge.app`. Must be unique.")
    status = fields.Selection(
        [
            ("pending", "Pending"),
            ("provisioning", "Provisioning"),
            ("live", "Live"),
            ("suspended", "Suspended"),
            ("cancelled", "Cancelled"),
        ],
        required=True, default="pending", tracking=True, index=True,
    )
    tier = fields.Selection(
        [
            ("marathon_channel", "Marathon Channel"),
            ("direct", "Direct"),
            ("enterprise", "Enterprise"),
        ],
        required=True, default="direct", tracking=True,
    )
    plan_id = fields.Many2one(
        "kitchenforge.subscription.plan",
        string="Plan", tracking=True,
        help="Pricing tier this tenant is subscribed to. Auto-resolved from "
             "`tier` on create if not set explicitly.")

    # --- Billing -------------------------------------------------------
    billing_provider = fields.Selection(
        [
            ("stripe", "Stripe"),
            ("manual", "Manual / Invoiced"),
        ],
        required=True, default="stripe", tracking=True,
    )
    stripe_customer_id = fields.Char(copy=False, tracking=True)
    stripe_subscription_id = fields.Char(copy=False, tracking=True)
    mrr_usd = fields.Float(
        string="MRR (USD)", default=0.0, tracking=True,
        help="Monthly recurring revenue from this tenant. Set on "
             "provision from the plan; can be overridden manually.")
    seats = fields.Integer(default=1, tracking=True)
    cabinets_last_30d = fields.Integer(
        string="Cabinets (30d)", default=0, readonly=True,
        help="Cabinets confirmed on the tenant in the last 30 days. "
             "Recomputed nightly by cron_recompute_usage().")

    # --- Channel -------------------------------------------------------
    marathon_referred = fields.Boolean(
        string="Marathon Referred", default=False, tracking=True,
        help="When true, the rebate split favours the Marathon Hardware "
             "partner for cabinets confirmed on this tenant.")

    # --- People + linkage ---------------------------------------------
    admin_email = fields.Char(required=True, tracking=True)
    admin_user_id = fields.Many2one("res.users", ondelete="set null")
    partner_id = fields.Many2one(
        "res.partner", string="Billing Partner", ondelete="set null")
    company_ids = fields.One2many(
        "res.company", "kitchenforge_tenant_id", string="Companies")

    # --- Provisioned infra pointers -----------------------------------
    docker_compose_path = fields.Char(
        help="Filesystem path to the docker-compose.yml the provisioner "
             "wrote for this tenant on the host. Informational only.")
    caddy_snippet_path = fields.Char(
        help="Filesystem path to the Caddy snippet (route block) wired "
             "into the host's parent Caddyfile.")

    # --- Agent surface keys -------------------------------------------
    api_key_ids = fields.One2many(
        "southbrook.api.key",
        compute="_compute_api_key_ids",
        string="API Keys",
        help="API keys whose owning user has this tenant's admin_user_id. "
             "Computed; rotation is managed in the API Key model.")
    api_key_count = fields.Integer(
        compute="_compute_api_key_ids", string="API Key Count")

    # --- Lifecycle timestamps -----------------------------------------
    created_at = fields.Datetime(
        readonly=True, default=lambda self: fields.Datetime.now())
    provisioned_at = fields.Datetime(readonly=True, copy=False)
    suspended_at = fields.Datetime(readonly=True, copy=False)
    cancelled_at = fields.Datetime(readonly=True, copy=False)

    # --- Audit log ----------------------------------------------------
    event_ids = fields.One2many(
        "kitchenforge.tenant.event", "tenant_id",
        string="Lifecycle Events")
    event_count = fields.Integer(
        compute="_compute_event_count", string="Event Count")

    _sql_constraints = [
        ("slug_uniq", "unique(slug)",
         "Tenant slug must be unique across the control plane."),
    ]

    # ------------------------------------------------------------------
    # Computes + constraints
    # ------------------------------------------------------------------
    @api.depends("admin_user_id")
    def _compute_api_key_ids(self):
        ApiKey = self.env["southbrook.api.key"].sudo()
        for rec in self:
            if rec.admin_user_id:
                keys = ApiKey.search([("user_id", "=", rec.admin_user_id.id)])
            else:
                keys = ApiKey.browse()
            rec.api_key_ids = keys
            rec.api_key_count = len(keys)

    @api.depends("event_ids")
    def _compute_event_count(self):
        for rec in self:
            rec.event_count = len(rec.event_ids)

    @api.constrains("slug")
    def _check_slug_shape(self):
        for rec in self:
            if not rec.slug:
                raise ValidationError(_("Tenant slug is required."))
            if len(rec.slug) < 2 or len(rec.slug) > 40:
                raise ValidationError(_(
                    "Slug must be 2-40 characters: %s") % rec.slug)
            if not SLUG_RE.match(rec.slug):
                raise ValidationError(_(
                    "Slug %s must be kebab-case (lowercase letters, "
                    "digits, hyphens; no leading/trailing hyphen).") % rec.slug)

    @api.constrains("admin_email")
    def _check_email(self):
        for rec in self:
            if rec.admin_email and "@" not in rec.admin_email:
                raise ValidationError(_(
                    "Admin email %s is not a valid address.") % rec.admin_email)

    # ------------------------------------------------------------------
    # Defaults + onchange
    # ------------------------------------------------------------------
    @api.onchange("tier")
    def _onchange_tier_resolves_plan(self):
        for rec in self:
            if rec.tier and not rec.plan_id:
                plan = self.env["kitchenforge.subscription.plan"].search(
                    [("code", "=", rec.tier)], limit=1)
                if plan:
                    rec.plan_id = plan
                    rec.mrr_usd = plan.monthly_usd

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # Auto-resolve plan from tier if missing.
            tier = vals.get("tier") or "direct"
            if not vals.get("plan_id"):
                plan = self.env["kitchenforge.subscription.plan"].search(
                    [("code", "=", tier)], limit=1)
                if plan:
                    vals["plan_id"] = plan.id
                    vals.setdefault("mrr_usd", plan.monthly_usd)
            if not vals.get("created_at"):
                vals["created_at"] = fields.Datetime.now()
        records = super().create(vals_list)
        for rec in records:
            rec._log_event("created", "Tenant record created.")
        return records

    # ------------------------------------------------------------------
    # Lifecycle actions
    # ------------------------------------------------------------------
    def action_provision(self):
        """Flip status to provisioning, signal off-Odoo provisioner.

        The actual docker-compose write + Caddy reload is done by an
        external provisioner that calls back into the control-plane REST
        to flip status to `live` and stamp provisioned_at. The webhook
        here is fire-and-forget; failure to deliver leaves the tenant in
        `provisioning` for a human to retry.
        """
        for rec in self:
            if rec.status not in ("pending", "suspended"):
                raise UserError(_(
                    "Cannot provision a tenant in status %s.") % rec.status)
            rec.status = "provisioning"
            rec._log_event(
                "provision_requested",
                "action_provision() called; provisioner webhook signalled.")
            rec._signal_provisioner("provision")
            # If billing_provider is stripe and there's no subscription
            # yet, attempt to create one. Falls back to no-op + warning
            # if stripe isn't importable or the secret key isn't set.
            if (rec.billing_provider == "stripe"
                    and not rec.stripe_subscription_id
                    and rec.plan_id):
                from .stripe_client import StripeClient
                StripeClient(rec.env).create_subscription(rec, rec.plan_id)
        return True

    def mark_provisioned(self, docker_compose_path=None,
                         caddy_snippet_path=None):
        """Provisioner callback — flip status to `live` and stamp paths."""
        for rec in self:
            if rec.status != "provisioning":
                _logger.warning(
                    "mark_provisioned called on tenant %s in status %s",
                    rec.slug, rec.status)
            rec.status = "live"
            rec.provisioned_at = fields.Datetime.now()
            if docker_compose_path:
                rec.docker_compose_path = docker_compose_path
            if caddy_snippet_path:
                rec.caddy_snippet_path = caddy_snippet_path
            rec._log_event(
                "provisioned",
                "Tenant marked live by provisioner callback.")
        return True

    def action_suspend(self):
        """Suspend a live tenant — locks SO confirms + kills sessions."""
        for rec in self:
            if rec.status not in ("live", "provisioning"):
                raise UserError(_(
                    "Cannot suspend a tenant in status %s.") % rec.status)
            rec.status = "suspended"
            rec.suspended_at = fields.Datetime.now()
            rec._kill_active_sessions()
            rec._signal_provisioner("suspend")
            rec._log_event("suspended", "action_suspend() called.")
        return True

    def action_resume(self):
        """Resume a suspended tenant — flips back to live."""
        for rec in self:
            if rec.status != "suspended":
                raise UserError(_(
                    "Cannot resume a tenant in status %s.") % rec.status)
            rec.status = "live"
            rec.suspended_at = False
            rec._signal_provisioner("resume")
            rec._log_event("resumed", "action_resume() called.")
        return True

    def action_cancel(self):
        """Cancel a tenant — terminal state, cancels Stripe sub."""
        for rec in self:
            if rec.status == "cancelled":
                continue
            if rec.billing_provider == "stripe" and rec.stripe_subscription_id:
                from .stripe_client import StripeClient
                StripeClient(rec.env).cancel_subscription(rec)
            rec.status = "cancelled"
            rec.cancelled_at = fields.Datetime.now()
            rec._signal_provisioner("cancel")
            rec._log_event("cancelled", "action_cancel() called.")
        return True

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _log_event(self, event_type, message, payload=None):
        self.ensure_one()
        return self.env["kitchenforge.tenant.event"].sudo().create({
            "tenant_id": self.id,
            "event_type": event_type,
            "message": message,
            "payload_json": payload or False,
        })

    def _signal_provisioner(self, action):
        """POST to the provisioner webhook. Fire-and-forget."""
        self.ensure_one()
        url = self.env["ir.config_parameter"].sudo().get_param(
            "kitchenforge_saas.provisioner_webhook_url", "")
        if not url:
            _logger.info(
                "saas provisioner webhook not configured; skipping %s for %s",
                action, self.slug)
            return False
        try:
            import requests  # bundled with Odoo
        except ImportError:
            _logger.warning("requests unavailable; cannot signal provisioner")
            return False
        body = {
            "schema": "kitchenforge.saas.provisioner.v1",
            "action": action,
            "tenant_id": self.id,
            "slug": self.slug,
            "tier": self.tier,
            "plan_code": self.plan_id.code if self.plan_id else None,
            "admin_email": self.admin_email,
            "marathon_referred": self.marathon_referred,
        }
        try:
            resp = requests.post(url, json=body, timeout=10)
            if resp.status_code >= 400:
                _logger.warning(
                    "provisioner webhook %s for %s -> %s: %s",
                    action, self.slug, resp.status_code, resp.text[:200])
                return False
        except Exception as exc:  # noqa: BLE001 — webhook is best-effort
            _logger.warning(
                "provisioner webhook %s for %s failed: %s",
                action, self.slug, exc)
            return False
        return True

    def _kill_active_sessions(self):
        """Best-effort: revoke API keys owned by the tenant's admin user.

        The actual session store is per-tenant Odoo instance, which the
        provisioner restarts on suspend. Here we revoke the agent-surface
        API keys so an in-flight agent loses its grip immediately.
        """
        self.ensure_one()
        if not self.admin_user_id:
            return 0
        keys = self.env["southbrook.api.key"].sudo().search([
            ("user_id", "=", self.admin_user_id.id),
            ("revoked_at", "=", False),
        ])
        keys.write({
            "revoked_at": fields.Datetime.now(),
            "revoked_reason": "tenant_suspended",
        })
        return len(keys)

    # ------------------------------------------------------------------
    # Cron — recompute usage
    # ------------------------------------------------------------------
    @api.model
    def cron_recompute_usage(self):
        """Nightly: count cabinets confirmed in the last 30 days per tenant.

        We approximate `cabinets confirmed` as the number of confirmed
        sale.order.line records whose product carries the configurator
        attribute set since 30 days ago. Where the tenant has no admin
        user, we fall back to the partner_id; if neither is set, leave
        the counter alone.
        """
        cutoff = fields.Datetime.now() - timedelta(days=30)
        SaleOrder = self.env["sale.order"].sudo()
        # Confirmed states across v17/v18/v19.
        confirmed_states = ("sale", "done")
        for tenant in self.search([("status", "=", "live")]):
            domain = [
                ("state", "in", confirmed_states),
                ("date_order", ">=", cutoff),
            ]
            if tenant.partner_id:
                domain.append(("partner_id", "=", tenant.partner_id.id))
            elif tenant.admin_user_id:
                domain.append(("user_id", "=", tenant.admin_user_id.id))
            else:
                continue
            try:
                orders = SaleOrder.search(domain)
                # Count lines (proxy for cabinets); ignore section/note rows.
                count = sum(
                    1 for line in orders.mapped("order_line")
                    if (line.product_id and not line.display_type))
            except Exception as exc:  # noqa: BLE001
                _logger.warning(
                    "cron_recompute_usage failed for tenant %s: %s",
                    tenant.slug, exc)
                continue
            tenant.cabinets_last_30d = count
        return True

    # ------------------------------------------------------------------
    # UI buttons (return act_window dicts where helpful)
    # ------------------------------------------------------------------
    def action_view_events(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Lifecycle Events"),
            "res_model": "kitchenforge.tenant.event",
            "view_mode": "list,form",
            "domain": [("tenant_id", "=", self.id)],
            "context": {"default_tenant_id": self.id},
        }
