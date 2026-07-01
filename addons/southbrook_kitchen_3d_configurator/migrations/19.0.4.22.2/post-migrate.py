# SPDX-License-Identifier: LGPL-3
#
# v19.0.4.22.0 audit P2#9 + P1#6 — two backfills.
#
# 1. Zone lexicon backfill. The `zone` field has default='base_run'
#    so `-u` fills every pre-existing row with 'base_run' the moment
#    the column is added — BEFORE this post-migrate runs. That masks
#    the CASE-based backfill from the pattern that would run only
#    where zone IS NULL. Detect this by joining against a fresh
#    CASE-computed value: if `zone = 'base_run'` AND `cabinet_type
#    != 'base'` AND `cabinet_type != 'corner'`, the row must be
#    the default-fill victim, not a legit user override.
#
# 2. Group assignment. The <function> block in security/groups.xml
#    was intended to sweep every non-share internal user into
#    group_kitchen_manager. Silent no-op in the initial 4.22.0 push
#    (obj() unavailable in <function> eval context on this Odoo
#    build). This SQL fallback assigns every non-share internal
#    user directly into the manager group via res_groups_users_rel;
#    Manager implies Designer + Readonly transitively via _implied_
#    groups, no need to seed the child groups.


def migrate(cr, version):
    # 1a — figure out the module id (needed to resolve the
    # xml_id → group id map). Every module bump goes through the
    # same registry so ir_model_data must have the entry by now.
    cr.execute(
        """
        SELECT res_id FROM ir_model_data
         WHERE module = 'southbrook_kitchen_3d_configurator'
           AND name   = 'group_kitchen_manager'
        """
    )
    row = cr.fetchone()
    manager_gid = row[0] if row else None

    # 1b — safe cabinet_type → zone backfill. Only touches rows
    # that carry the initial default AND whose cabinet_type doesn't
    # map to 'base_run' anyway (base + corner → base_run). Leaves
    # user-set zone values alone if they typed 'base_run' manually.
    cr.execute(
        """
        UPDATE southbrook_kitchen_design_line
           SET zone = CASE cabinet_type
                          WHEN 'base'   THEN 'base_run'
                          WHEN 'wall'   THEN 'wall'
                          WHEN 'tall'   THEN 'tall'
                          WHEN 'corner' THEN 'base_run'
                          WHEN 'filler' THEN 'accessory'
                          WHEN 'panel'  THEN 'accessory'
                          ELSE 'other'
                      END
         WHERE zone = 'base_run'
           AND cabinet_type NOT IN ('base', 'corner')
        """
    )

    # 2 — grant every non-share internal user the Manager group so
    # the pre-taxonomy default (everyone has full CRUD) survives
    # the upgrade. Users have to be explicitly downgraded to
    # Designer/Readonly by an admin post-migration. Idempotent via
    # ON CONFLICT DO NOTHING.
    if manager_gid:
        cr.execute(
            """
            INSERT INTO res_groups_users_rel (gid, uid)
            SELECT %s, u.id
              FROM res_users u
             WHERE u.share = FALSE
               AND u.active = TRUE
            ON CONFLICT DO NOTHING
            """,
            (manager_gid,),
        )
