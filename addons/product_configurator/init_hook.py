import logging

logger = logging.getLogger(__name__)


def post_init_hook(env):
    """Transfer existing weight values to weight_dummy after installation
    since now the weight field is computed.

    FEATURE 2 — Migration of legacy is_saved sessions to bookmarks.
    Any existing product.config.session row with is_saved=True is
    transferred to a product.config.bookmark record so the new
    portal surface picks it up. Idempotent: skips sessions that
    already have an active bookmark.
    """
    env.cr.execute("UPDATE product_product SET weight_dummy = weight")
    _migrate_legacy_bookmarks(env)


def _migrate_legacy_bookmarks(env):
    """One-shot data migration for FEATURE 2.

    Before this release, "saved" configurations lived as flags on
    ``product.config.session`` (``is_saved=True`` + ``bookmark_name``).
    The new ``product.config.bookmark`` model is the authority going
    forward. Migrate existing rows so previously-saved configurations
    appear in the new portal list immediately on upgrade.

    Idempotent — safe to re-run on subsequent module upgrades.
    """
    Bookmark = env["product.config.bookmark"]
    if "is_saved" not in env["product.config.session"]._fields:
        # Field doesn't exist (older install or unrelated stack);
        # nothing to migrate.
        return

    legacy_sessions = env["product.config.session"].search(
        [("is_saved", "=", True)]
    )
    if not legacy_sessions:
        return

    migrated = 0
    skipped_already_migrated = 0
    skipped_no_user = 0

    for session in legacy_sessions:
        # Skip sessions already covered by an active bookmark (re-run
        # of this hook on a previously-migrated DB).
        existing = Bookmark.search(
            [("session_id", "=", session.id), ("active", "=", True)],
            limit=1,
        )
        if existing:
            skipped_already_migrated += 1
            continue

        if not session.user_id:
            # Defensive: a session must have an owner to be migrated.
            # Public/orphan sessions are out of scope for bookmarks.
            skipped_no_user += 1
            continue

        Bookmark.create(
            {
                "name": session.bookmark_name
                or (session.product_tmpl_id.name or "Saved configuration"),
                "session_id": session.id,
                "user_id": session.user_id.id,
            }
        )
        migrated += 1

    logger.info(
        "FEATURE 2 bookmark migration: %d migrated, %d skipped "
        "(already had bookmark), %d skipped (no owner)",
        migrated,
        skipped_already_migrated,
        skipped_no_user,
    )
