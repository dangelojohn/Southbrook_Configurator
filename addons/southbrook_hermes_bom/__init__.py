from . import models
from . import services


def uninstall_hook(env):
    """Cut the implied_ids link from base.group_system to our group.

    Without this, uninstalling this module drops `group_hermes_user`
    but leaves base.group_system pointing at the now-deleted id; on a
    subsequent reinstall the id is fresh and the implied_ids entry is
    a dangling reference — admins do NOT auto-inherit the new group
    until someone manually re-adds it.

    Tearing the link down here keeps the uninstall+reinstall path
    clean: reinstall re-creates the group AND re-establishes the
    implied_ids link via the module data (see
    security/hermes_security.xml).
    """
    group = env.ref(
        "southbrook_hermes_bom.group_hermes_user", raise_if_not_found=False,
    )
    if not group:
        return
    base_system = env.ref("base.group_system", raise_if_not_found=False)
    if not base_system:
        return
    if group in base_system.implied_ids:
        base_system.sudo().write({"implied_ids": [(3, group.id)]})
