# SPDX-License-Identifier: LGPL-3.0-only
"""Flip base.CAD currency symbol position to "before" — English-Canada.

Why a migration script instead of a data XML?
---------------------------------------------
The base module ships ``base.CAD`` with its own ``ir.model.data`` row
marked ``noupdate=True`` (because base records should not silently
mutate on every Odoo core upgrade). When a downstream module declares
``<record id="base.CAD">`` inside a data XML with ``noupdate="0"``,
Odoo respects the EXISTING noupdate flag on the first ir.model.data
row — our override is no-op'd on ``-u``.

The reliable pattern for forcibly updating a base record is a
migration script. Migrations always run when the module's recorded
version on ir_module_module differs from the manifest version, so
this fires once per version bump.

Idempotent: writing position="before" when it's already "before" is
a no-op write the ORM optimizes away.

Why this scope?
---------------
Flipping ``base.CAD.position`` propagates the fix to every surface
that renders Canadian dollar amounts via ``res.currency.position``:
storefront /shop, configurator price tile, /my portal, sale.order
and account.move report PDFs, and the back-office sale/invoice forms.

If a future Quebec-French storefront is needed, branch a non-base
``southbrook.CAD_fr`` record with position="after" rather than
flipping ``base.CAD`` back.
"""
import logging


_logger = logging.getLogger(__name__)


def migrate(cr, version):
    _logger.info(
        "southbrook_configurator_ux 19.0.1.2.0: flipping base.CAD "
        "currency.position to 'before' (English-Canada convention)"
    )
    cr.execute(
        "UPDATE res_currency "
        "   SET position = 'before' "
        " WHERE id = (SELECT res_id FROM ir_model_data "
        "             WHERE module = 'base' AND name = 'CAD') "
        "   AND position IS DISTINCT FROM 'before'"
    )
    if cr.rowcount:
        _logger.info("base.CAD position flipped (%s row).", cr.rowcount)
    else:
        _logger.info("base.CAD position was already 'before' — no-op.")
