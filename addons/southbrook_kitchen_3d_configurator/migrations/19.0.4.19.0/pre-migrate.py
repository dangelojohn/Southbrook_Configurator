# SPDX-License-Identifier: LGPL-3
#
# v19.0.4.19.0 — Kitchen Preview thumbnail + kanban view.
#
# Two cleanups run before the module upgrade phase:
#
#   1. `x_kitchen_image` was first added to production as a
#      state='manual' custom field via Technical > Fields (during
#      the interactive session on 2026-07-01). Delete the manual
#      ir_model_fields row so the code-defined fields.Image on
#      SouthbrookKitchenDesign can adopt the column cleanly.
#      The underlying southbrook_kitchen_design.x_kitchen_image
#      column is left in place — its data survives the takeover.
#
#   2. During the same interactive session, ad-hoc `ir.ui.view`
#      records were created for a new kanban view and a form
#      inherit that adds the image widget. Neither has an
#      `ir_model_data` external-id row, which means on -u they
#      would sit alongside the new module-owned records — the
#      form-inherit collision in particular would cause the
#      view arch to insert `x_kitchen_image` twice, breaking
#      the design form. Delete any ir.ui.view for
#      southbrook.kitchen.design (kanban + inherited form) that
#      is NOT tied to a module.
#
# On fresh installs and untouched databases both statements are
# silent no-ops.


def migrate(cr, version):
    # 1. Release the manual field row.
    cr.execute(
        """
        DELETE FROM ir_model_fields
        WHERE model = 'southbrook.kitchen.design'
          AND name  = 'x_kitchen_image'
          AND state = 'manual'
        """
    )

    # 2. Drop orphan (module-less) kanban + inherited-form views
    #    for our model. Only ir.ui.view rows without an
    #    ir_model_data entry are considered orphan.
    cr.execute(
        """
        DELETE FROM ir_ui_view v
        WHERE v.model = 'southbrook.kitchen.design'
          AND (
                v.type = 'kanban'
             OR (v.type = 'form' AND v.inherit_id IS NOT NULL)
          )
          AND NOT EXISTS (
              SELECT 1
                FROM ir_model_data d
               WHERE d.model  = 'ir.ui.view'
                 AND d.res_id = v.id
          )
        """
    )
