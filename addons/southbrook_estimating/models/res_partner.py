# SPDX-License-Identifier: LGPL-3.0-only
"""
Extend res.partner with the channel + tradesperson_tier fields.

The channel field is the keystone of southbrook_estimating's pricing
resolution — sale.order.action_confirm reads partner.channel via the
custom routine #3 dispatcher (_resolve_channel_pricelist, lands in commit 4)
to pick the right pricelist.

Per Q5 locked decision: the channel selection uses `tradesperson` as the
technical key (grep-safe), and the workbook vocabulary ("Contractor
Pricing") is preserved as the UI label. The series-vs-channel naming
clash is resolved by keeping `contractor` for the entry-level series
attribute value and `tradesperson` for the cost-plus channel.

Per NF5 locked decision: `tradesperson_tier` is nullable on the model.
`_resolve_channel_pricelist` (commit 4) handles three paths:
  - tier=1 → pricelist_tradesperson_tier_1
  - tier=2 → pricelist_tradesperson_tier_2
  - tier=3 → pricelist_tradesperson_tier_3
  - tier=None → pricelist_tradesperson (base; cost+5% only)
New tradesperson partners default to tier 3 (the entry tier per
the Pricing Evolution tab of #5). Existing untiered partners get a
soft warning at order creation (logged, not blocking).
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = "res.partner"

    # ------------------------------------------------------------------
    # Pipeline stage (2026-07-06) — customer classification by where they
    # sit in the sales pipeline, DERIVED from their own orders so it can
    # never drift (unlike a manual tag). Groupable/filterable in Contacts:
    # answers "is this customer in the Quote module or the Sales module".
    # Property TYPE (house/condo/apartment/office/retail/...) is handled
    # the Odoo-native way via Contact Tags (res.partner.category) seeded in
    # data/customer_category_tags.xml — a stable attribute a rep sets,
    # where tags are the right tool; pipeline stage is derived state, where
    # a computed field is the right tool.
    # ------------------------------------------------------------------
    southbrook_pipeline_stage = fields.Selection(
        [
            ("prospect", "Prospect"),
            ("quote", "Quote"),
            ("proposal", "Proposal"),
            ("active_job", "Active Job"),
        ],
        string="Pipeline Stage",
        compute="_compute_southbrook_pipeline_stage",
        store=True,
        help="Where this customer sits in the sales pipeline, derived from "
             "their orders: Active Job (a confirmed order — Sales module) > "
             "Proposal (a sent quotation) > Quote (a draft quotation — Quote "
             "module) > Prospect (a customer with no orders yet).",
    )

    @api.depends("sale_order_ids.state")
    def _compute_southbrook_pipeline_stage(self):
        for partner in self:
            states = set(partner.sale_order_ids.mapped("state"))
            if "sale" in states:
                partner.southbrook_pipeline_stage = "active_job"
            elif "sent" in states:
                partner.southbrook_pipeline_stage = "proposal"
            elif "draft" in states:
                partner.southbrook_pipeline_stage = "quote"
            else:
                partner.southbrook_pipeline_stage = "prospect"

    # ------------------------------------------------------------------
    # Customer identity resolver (2026-07-06).
    #
    # The Order Builder is used by internal staff/dealers building an order
    # ON BEHALF OF a customer — the logged-in user is NOT the customer.
    # Every order-creation path historically bound order.partner_id to
    # request.env.user.partner_id (i.e. "whoever is logged in"), so orders
    # created by an employee (e.g. Administrator) had no real customer and
    # no customer was ever captured. This is the one canonical routine that
    # resolves-or-creates the distinct CUSTOMER contact from captured
    # details, so order.partner_id is always a real, fully-described
    # customer. Used by the Order Builder set-customer endpoint and the
    # room-chat capture path; mirrors southbrook_agent_gateway's proven
    # _find_or_create_partner but lives here (the base module) so every
    # funnel can share it.
    # ------------------------------------------------------------------
    _SOUTHBROOK_CUSTOMER_FIELDS = (
        "phone", "street", "street2", "city", "zip", "function",
    )

    @api.model
    def _southbrook_resolve_customer(self, vals, trusted=False):
        """Find-or-create the customer a Southbrook order is for.

        vals: dict with at least ``name`` OR ``email``; optional phone,
        street, street2, city, zip, state_id, country_id, function,
        is_company.
        trusted: True when an authenticated internal rep entered the data
        (blank fields on a matched existing contact are backfilled). False
        for unverified/public submissions (an existing contact is never
        mutated — a stranger can't plant data on a real customer by
        guessing their email).
        Returns the res.partner (customer_rank ≥ 1 so it lists as a
        customer). Never returns the calling user's own partner.
        """
        Partner = self.env["res.partner"].sudo()
        name = (vals.get("name") or "").strip()
        email = (vals.get("email") or "").strip()
        if not name and not email:
            raise ValidationError(_(
                "A customer name or email is required to identify who this "
                "order is for."))

        partner = Partner.browse()
        if email:
            partner = Partner.search(
                [("email_normalized", "=", email.lower())], limit=1)
        if partner:
            if trusted:
                backfill = {}
                if name and not partner.name:
                    backfill["name"] = name
                for f in self._SOUTHBROOK_CUSTOMER_FIELDS:
                    if vals.get(f) and not partner[f]:
                        backfill[f] = vals[f]
                if backfill:
                    partner.write(backfill)
            return partner

        create_vals = {
            "name": name or email,
            "email": email or False,
            "customer_rank": 1,
            "company_type": "company" if vals.get("is_company") else "person",
        }
        for f in self._SOUTHBROOK_CUSTOMER_FIELDS:
            if vals.get(f):
                create_vals[f] = vals[f]
        # Geo is best-effort — never fail creation on an unmatched id.
        for f in ("state_id", "country_id"):
            if vals.get(f):
                create_vals[f] = vals[f]
        return Partner.create(create_vals)

    # --- Channel (Q1 + Q5 + Q21) ----------------------------------------
    channel = fields.Selection(
        selection=[
            ("retail", "Retail (Walk-in)"),
            ("dealer", "Dealer (−50%)"),
            ("tradesperson", "Contractor Pricing"),
            ("kd", "Central KD"),
            ("bigbox", "Big-Box Wholesale"),
            ("refacing", "Refacing (CTHS)"),
        ],
        string="Southbrook Channel",
        default="retail",
        help=(
            "The sales channel for this partner. Drives pricelist "
            "resolution at sale.order creation via "
            "_resolve_channel_pricelist (custom routine #3). "
            "Workbook label 'Contractor' is preserved as the UI label "
            "for the 'tradesperson' technical key per Q5 — grep-safety "
            "in code, fidelity in UI."
        ),
    )

    # --- Tradesperson tier (NF5) ----------------------------------------
    tradesperson_tier = fields.Selection(
        selection=[
            ("1", "Tier 1 (−25%)"),
            ("2", "Tier 2 (−30%)"),
            ("3", "Tier 3 (−35%)"),
        ],
        string="Tradesperson Tier",
        help=(
            "Only meaningful when channel='tradesperson'. Default for new "
            "tradesperson partners is Tier 3 (the entry tier per the "
            "workbook's Pricing Evolution tab). Tier-determined discount "
            "is applied as a second-stage multiplier on top of the "
            "cost+5% floor; see pricelists.xml."
        ),
    )

    # ------------------------------------------------------------------
    # Defaults: when channel is set to 'tradesperson' and no tier is set,
    # default to '3' per NF5. Apply via onchange so existing records
    # aren't disturbed at install time — only fresh user actions trigger.
    # ------------------------------------------------------------------
    @api.onchange("channel")
    def _onchange_channel_default_tier(self):
        for partner in self:
            if partner.channel == "tradesperson" and not partner.tradesperson_tier:
                partner.tradesperson_tier = "3"
            elif partner.channel != "tradesperson":
                # Tier is meaningless off-channel; clear silently.
                partner.tradesperson_tier = False
