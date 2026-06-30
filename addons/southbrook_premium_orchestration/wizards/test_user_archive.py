# Copyright 2026 Southbrook Cabinetry
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
"""Test User Archive Wizard.

Phase 1.5 cleanup tool. The Playwright/CI smoke runs between 2026-06-01 and
2026-06-03 created 86 share=True portal users whose logins match a handful of
synthetic patterns (``%@s.test``, ``%@southbrook-test.local``, the lone
``@testcustomer.com``). They have no ``sale.order`` ownership, but they pollute
every res.users-based selection list in the backend (Salesperson, Owner,
Followers, ...).

This wizard lets ``base.group_system`` archive them in a single transaction
with a preview-before-commit gate. The Administrator (uid=2) is excluded by a
hardcoded rule no matter what the operator types in the pattern field.
"""

from odoo import _, api, fields, models
from odoo.exceptions import UserError


ADMIN_UID = 2
SANITY_CAP = 500
SAMPLE_LIMIT = 10


class TestUserArchiveWizard(models.TransientModel):
    """Archive synthetic test-pattern users in bulk with a preview gate."""

    _name = 'test.user.archive.wizard'
    _description = 'Archive Test Users Wizard'

    domain_pattern = fields.Char(
        string='Login Pattern',
        default='%@s.test',
        required=True,
        help='SQL LIKE pattern matched against res.users.login',
    )
    include_southbrook_test_local = fields.Boolean(
        string='Include %@southbrook-test.local',
        default=True,
        help='Also archive %@southbrook-test.local logins',
    )
    include_testcustomer = fields.Boolean(
        string='Include %@testcustomer.com',
        default=True,
        help='Also archive %@testcustomer.com logins',
    )
    preview_count = fields.Integer(
        string='Matching Users',
        compute='_compute_preview_count',
        readonly=True,
    )
    sample_logins = fields.Text(
        string='Sample Logins (first 10)',
        compute='_compute_preview_count',
        readonly=True,
    )
    exclude_user_ids = fields.Many2many(
        'res.users',
        string='Always Keep These Users',
        help='Safety net: these users are never archived even if they match the pattern.',
    )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _build_domain(self):
        """Build the search domain shared by preview + archive.

        Combines all selected LIKE patterns with OR, ANDed with safety filters:
        share=True, active=True, id != Administrator, id NOT IN
        exclude_user_ids.
        """
        self.ensure_one()
        patterns = []
        if self.domain_pattern:
            patterns.append(self.domain_pattern)
        if self.include_southbrook_test_local:
            patterns.append('%@southbrook-test.local')
        if self.include_testcustomer:
            patterns.append('%@testcustomer.com')

        if not patterns:
            # No patterns selected → match nothing.
            return [('id', '=', 0)]

        # OR-chain of login LIKE clauses, polish-notation prefix.
        login_or = []
        for _ in range(len(patterns) - 1):
            login_or.append('|')
        for pat in patterns:
            login_or.append(('login', 'like', pat))

        domain = login_or + [
            ('share', '=', True),
            ('active', '=', True),
            ('id', '!=', ADMIN_UID),
        ]
        if self.exclude_user_ids:
            domain.append(('id', 'not in', self.exclude_user_ids.ids))
        return domain

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------
    @api.depends(
        'domain_pattern',
        'include_southbrook_test_local',
        'include_testcustomer',
        'exclude_user_ids',
    )
    def _compute_preview_count(self):
        Users = self.env['res.users'].with_context(active_test=False)
        for wiz in self:
            domain = wiz._build_domain()
            wiz.preview_count = Users.search_count(domain)
            sample = Users.search(domain, limit=SAMPLE_LIMIT, order='login')
            wiz.sample_logins = '\n'.join(sample.mapped('login')) or ''

    # ------------------------------------------------------------------
    # Action
    # ------------------------------------------------------------------
    def action_archive(self):
        """Archive the matching users. Two hard guards before any write."""
        self.ensure_one()
        domain = self._build_domain()
        users = self.env['res.users'].with_context(active_test=False).search(domain)

        # HARD GUARD 1: never touch Administrator (uid=2).
        if ADMIN_UID in users.ids:
            raise UserError(_(
                'Refusing to archive: Administrator (uid=2) is in the result set. '
                'This is a hard safety rule; the pattern must not match the admin.'
            ))

        # HARD GUARD 2: sanity cap. If more than 500 users match, the operator
        # almost certainly typed a too-broad pattern.
        if len(users) >= SANITY_CAP:
            raise UserError(_(
                'Refusing to archive: %(n)d users match, which is above the '
                'sanity cap of %(cap)d. Narrow the pattern.'
            ) % {'n': len(users), 'cap': SANITY_CAP})

        users.with_context(active_test=False).write({'active': False})

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Archived'),
                'message': _('%d test users archived') % len(users),
                'type': 'success',
                'sticky': False,
            },
        }
