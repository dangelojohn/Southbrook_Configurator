/**
 * Process-wide bootstrap: registers harness/loader.mjs as a Node module
 * customization hook (node:module `register()`, stable API) so every
 * bare Odoo-style specifier ("@odoo/owl", "@web/core/...",
 * "@southbrook_kitchen_3d_configurator/...") resolves for the whole
 * test run, including inside the real source files' own import
 * statements. Load via `node --import ./harness/register.mjs --test ...`.
 */
import { register } from "node:module";

register("./loader.mjs", import.meta.url);
