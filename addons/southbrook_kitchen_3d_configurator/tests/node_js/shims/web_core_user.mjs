/**
 * Boundary shim for "@web/core/user" (the singleton `user` object). Only
 * `user.isInternalUser` is read by the configurator (portalUser
 * detection, kitchen_configurator.js:221) — a plain mutable object is
 * enough; tests reassign `user.isInternalUser` directly before mounting
 * if a case needs the portal-user branch.
 */
export const user = {
    isInternalUser: true,
};
