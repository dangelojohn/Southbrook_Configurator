# SPDX-License-Identifier: LGPL-3.0-only
"""
Phase 2F orphan cleanup — runs BEFORE data files load on the upgrade
to 19.0.1.3.0.

Context
-------
The audit Phase 2B/2F gating rules in data/config_rules.xml use
xml_ids like ruleA1_wall_1dr_overlay_when_frameless. On each
upgrade, southbrook_configurator_ux/catalog_expansion.py wipes +
recreates product.template.attribute.line rows. The
product.config.line rules that referenced them via attribute_line_id
get CASCADE-deleted. But the ir.model.data xml_ids that pointed at
those rules survive — orphaned.

On the next config_rules.xml load, Odoo sees the orphan xml_id,
tries to UPDATE a non-existent record, and silently fails to create
the rule. The end state: only the rules for cabinets whose
attribute_lines DIDN'T get caught in the cycle (corner, drawer_bank,
sink_base, vanity) bind correctly — 11 of 47 rules.

The cleanup deletes orphan ir.model.data entries for ruleA* xml_ids
that point at non-existent product.config.line records. The
subsequent config_rules.xml load then creates fresh records and
registers fresh xml_ids.

Idempotent. Safe to re-run.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        # Fresh install — no orphans possible.
        return

    cr.execute("""
        SELECT id, name, res_id
        FROM ir_model_data
        WHERE model = 'product.config.line'
          AND module = 'southbrook_estimating'
          AND name LIKE 'ruleA%'
          AND NOT EXISTS (
              SELECT 1 FROM product_config_line cl
              WHERE cl.id = ir_model_data.res_id
          )
    """)
    orphans = cr.fetchall()
    if not orphans:
        _logger.info("phase2f orphan cleanup: no orphan rule xml_ids found")
        return

    orphan_ids = [row[0] for row in orphans]
    cr.execute(
        "DELETE FROM ir_model_data WHERE id IN %s",
        (tuple(orphan_ids),),
    )
    _logger.info(
        "phase2f orphan cleanup: removed %d orphaned rule xml_ids (sample: %s)",
        len(orphan_ids),
        [row[1] for row in orphans[:5]],
    )
