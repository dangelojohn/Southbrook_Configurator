# SPDX-License-Identifier: LGPL-3.0-only
"""southbrook.eco extension — in-flight MO notification (M20).

M20 (Manufacturing PM JTBD 2026-06-01): when an ECO is approved
and the affected BoM gets a new version, every in-flight
manufacturing order using the old version of that BoM was
silently rolling forward against the new spec. PMs had no
notification mechanism; floor managers built cabinets to a spec
that quietly changed under them.

Fix: extend southbrook.eco.action_apply to, after the canonical
apply succeeds, post a chatter message on every mrp.production
that:
    - uses the same BoM the ECO targets
    - is in an in-flight state (confirmed / progress / to_close /
      pending — i.e. not done or cancel)

Each affected MO gets its own chatter post linking to the ECO and
flagging the version change. Subscribed users (assigned
salesperson, Floor Manager group members watching the MO) see it
in their inbox.

Scope of this commit:
    - Cover target_kind='bom' ECOs only (the only kind that
      affects mrp.production routing/components).
    - Cut spec + rule ECO kinds don't touch BoMs directly — they
      affect interpretation, not in-flight production. Out of
      scope.

Future polish:
    - Post on action_reject too — a rejected ECO that was in
      review against an active MO might still warrant a note
      ('change was considered, then rejected; original spec
      stands'). Low value, defer.
    - Wire an automation rule so 'critical' equipment condition
      transitions also post on the work-center's in-flight MOs.
      That's a separate workstream (M13 + M14 fusion).
"""
from markupsafe import Markup

from odoo import _, models


# In-flight MO states for the notification fanout. Aligned with
# the M14 IN_FLIGHT_STATES constant on maintenance.equipment.
_IN_FLIGHT_MO_STATES = ("draft", "confirmed", "progress", "to_close")


class SouthbrookEco(models.Model):
    _inherit = "southbrook.eco"

    def action_apply(self):
        # Capture which BoMs are affected BEFORE super(): the apply
        # handler for target_kind='bom' may mutate or replace bom_id
        # (e.g. clone a new version). Snapshot lets us find MOs
        # against the pre-apply bom_id.
        bom_snapshots = {
            eco.id: eco.bom_id.id
            for eco in self
            if eco.target_kind == "bom" and eco.bom_id
        }

        result = super().action_apply()

        # Post-apply: for each ECO that targeted a BoM, find
        # in-flight MOs and chatter-notify them.
        MO = self.env["mrp.production"]
        for eco in self:
            bom_id = bom_snapshots.get(eco.id)
            if not bom_id:
                continue
            mos = MO.sudo().search([
                ("bom_id", "=", bom_id),
                ("state", "in", list(_IN_FLIGHT_MO_STATES)),
            ])
            if not mos:
                continue

            # New BoM version (if action_apply created one).
            new_bom = eco.new_bom_id or eco.bom_id
            new_version = getattr(new_bom, "southbrook_version", None)
            old_version = (
                new_version - 1
                if isinstance(new_version, int) and new_version > 1
                else None
            )

            # Wrap in Markup so Odoo's chatter renderer treats the
            # HTML as markup rather than escaping the tags into
            # literal text. _() returns a translatable string; the
            # Markup() wrapper signals 'trusted HTML' to the chatter
            # pipeline.
            body = Markup(_(
                "<strong>ECO %(eco_name)s applied to this MO's BoM.</strong>"
                "<br/>"
                "The Bill of Materials this manufacturing order was "
                "issued against has been superseded by a newer version."
                "<br/><br/>"
                "<ul>"
                "<li>ECO: <em>%(eco_title)s</em></li>"
                "<li>BoM: %(bom_code)s</li>"
                "<li>New version: %(new_version)s%(old_note)s</li>"
                "</ul>"
                "Floor Manager / PM should decide: <strong>continue</strong> "
                "with the in-flight spec, <strong>pause</strong> to re-issue "
                "with the new BoM, or <strong>cancel</strong> if the change "
                "is fundamental."
            )) % {
                "eco_name": eco.name,
                "eco_title": eco.title or eco.name,
                "bom_code": new_bom.code or _("(unset)"),
                "new_version": new_version or _("?"),
                "old_note": (
                    _(" (was v%s)") % old_version
                    if old_version is not None
                    else ""
                ),
            }
            for mo in mos:
                mo.message_post(
                    body=body,
                    subject=_("ECO %s applied — in-flight impact") % eco.name,
                    message_type="comment",
                    subtype_xmlid="mail.mt_comment",
                )

        return result
