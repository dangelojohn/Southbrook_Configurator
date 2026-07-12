# SPDX-License-Identifier: LGPL-3.0-only
"""southbrook.qr.kind — abstract base for kind handlers.

Other addons register their kinds by inheriting this and setting
`_kind_name` + `_target_model` (+ optionally action overrides).

Pattern:

    class AsbuiltKind(models.AbstractModel):
        _name = "southbrook.qr.kind.asbuilt"
        _inherit = "southbrook.qr.kind"
        _kind_name = "asbuilt"
        _target_model = "southbrook.asbuilt"
        # Override actions:
        def handle_action(self, record, action, params):
            if action == "seal":
                record.action_seal()
                return {"ok": True}
            return super().handle_action(record, action, params)

Controller resolves the kind by walking env's registry for any
AbstractModel inheriting southbrook.qr.kind with _kind_name == X.
"""
from odoo import _, api, models
from odoo.exceptions import UserError


class QrKind(models.AbstractModel):
    _name = "southbrook.qr.kind"
    _description = "Southbrook QR Kind Handler (abstract base)"

    # Subclasses override:
    _kind_name = None         # short alias, e.g. "asbuilt"
    _target_model = None      # Odoo model name to open
    _default_action = "open"  # 'open' = ir.actions.act_window
    _expires_in_seconds = 0   # 0 = no expiry. >0 = TTL enforcement.

    @api.model
    def resolve_kind(self, kind):
        """Find the registered handler for `kind`.

        Convention: each kind handler's model name is
        'southbrook.qr.kind.<kind>'. Returns env-bound instance.
        Returns False if no handler is registered for that kind.
        """
        if not kind:
            return False
        target_model_name = f"southbrook.qr.kind.{kind}"
        if target_model_name in self.env:
            return self.env[target_model_name]
        return False

    @api.model
    def get_record(self, ident):
        """Resolve a record from `ident`. Default: int id lookup on
        _target_model. Override for slug-based kinds."""
        if not self._target_model:
            raise UserError(
                _("Kind handler %s has no _target_model") % self._name)
        try:
            rid = int(ident)
        except (TypeError, ValueError):
            raise UserError(_("ident must be int: %s") % ident)
        rec = self.env[self._target_model].browse(rid).exists()
        if not rec:
            raise UserError(
                _("%s id=%s not found") % (self._target_model, ident))
        # ACL check: read access to the record. check_access() (v19)
        # replaces the deprecated check_access_rights()/check_access_rule()
        # pair and raises AccessError on denial, which the controller maps
        # to result='access_denied'.
        rec.check_access("read")
        return rec

    @api.model
    def handle_action(self, record, action, params):
        """Default action handler. 'open' returns an act_window.
        Other actions raise NotImplementedError unless overridden."""
        if action == "open":
            return {
                "ok": True,
                # v19 record-open URL (the old `action-base.action_open_view`
                # xmlid does not exist and the `action-` prefix is for numeric
                # action ids only). JSON-API clients can follow this directly.
                "redirect": f"/odoo/{self._target_model}/{record.id}",
                "act_window": {
                    "type": "ir.actions.act_window",
                    "res_model": self._target_model,
                    "res_id": record.id,
                    "view_mode": "form",
                    "target": "current",
                },
                "record_name": record.display_name,
                "record_id": record.id,
                "model": self._target_model,
            }
        raise NotImplementedError(
            _("Kind %s does not handle action %s") % (self._kind_name, action))
