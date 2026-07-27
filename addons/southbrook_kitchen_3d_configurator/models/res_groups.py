# SPDX-License-Identifier: LGPL-3.0-only
"""res.groups helper for the Kitchen-3D group taxonomy.

The install-time "sweep every internal user into the Manager group" step used
to live as an inline `<value eval>` in security/groups.xml that called
`obj().env['res.users'].search(...)`. In Odoo 19 `obj` is NOT available inside
a `<value>` child of a `<function>` (a `<value>` node carries no `model=`
attribute, so `_get_eval_context` never injects `obj`), which raised
`NameError: name 'obj' is not defined` and FAILED the whole module install on a
current v19 CE build. This method moves that logic into Python where it has a
real `self.env`; the data file now calls it argument-free.
"""
from odoo import api, models


class ResGroups(models.Model):
    _inherit = "res.groups"

    @api.model
    def _southbrook_kitchen_sweep_managers(self):
        """Add every non-share internal user to the Kitchen 3D Manager group.

        Preserves the documented pre-taxonomy full-access default (every
        internal user → Manager). Idempotent via (4, id). Called from
        security/groups.xml on -i and -u.

        NOTE (2026-07-11 security review, HIGH-2): this blanket sweep nullifies
        the per-designer isolation the record rules otherwise enforce. It is
        kept here only to preserve the existing deployed behaviour — retiring
        it (and assigning reps to group_kitchen_designer instead) is a
        business-policy decision for the owner; see the module code review.
        """
        mgr = self.env.ref(
            "southbrook_kitchen_3d_configurator.group_kitchen_manager",
            raise_if_not_found=False,
        )
        base_user = self.env.ref("base.group_user", raise_if_not_found=False)
        if not mgr or not base_user:
            return
        users = self.env["res.users"].search([
            ("group_ids", "in", [base_user.id]),
            ("share", "=", False),
        ])
        if users:
            mgr.write({"user_ids": [(4, u.id) for u in users]})
