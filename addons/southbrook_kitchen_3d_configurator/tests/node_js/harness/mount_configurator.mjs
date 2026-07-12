/**
 * PR3a — the ONE canonical mount helper for
 * SouthbrookKitchenConfigurator (kitchen_configurator.js), used by every
 * component-level contract test (#1 wall selection, #2 persistence-
 * after-reload, #4 active-wall indicator, #5 callback contract).
 *
 * Boots jsdom, loads the REAL unmodified component (registered into the
 * shimmed actions registry exactly as `actionRegistry.add(...)` does at
 * the bottom of kitchen_configurator.js), wires the RPC boundary to a
 * per-test route table (default: benign empty responses so a test that
 * doesn't care about products/layout/user-defaults isn't forced to stub
 * them), and mounts it under owl's real `mount()`, awaiting the full
 * onWillStart lifecycle (product/defaults load + hydrate-or-refresh)
 * before returning.
 *
 * <KitchenCanvas> is transparently swapped for harness/kitchen_canvas_mock.mjs
 * by the loader (harness/loader.mjs) — the only substitution boundary,
 * per the PR3a brief. Everything else imported by kitchen_configurator.js
 * is the real shipped source file, resolved from disk.
 */
import path from "node:path";
import { fileURLToPath } from "node:url";
import { setupDom } from "./setup_dom.mjs";
import { __resetRpc, __onRoute, __calls } from "../shims/web_core_rpc.mjs";
import { registry } from "../shims/web_core_registry.mjs";
// NOT a static import: kitchen_canvas_mock.mjs imports "@odoo/owl", and
// Owl's ESM build reads DOM globals (Element, Node, ...) at module-
// evaluation time. A static import here would load owl before
// setupDom() below installs those globals. Loaded dynamically, after
// setupDom(), same as "@odoo/owl" itself and the configurator source.

const HERE = path.dirname(fileURLToPath(import.meta.url));
const CONFIGURATOR_SRC = path.resolve(
    HERE, "..", "..", "..", "static", "src", "js", "kitchen_configurator.js",
);

const DEFAULT_ROUTES = {
    "/southbrook_kitchen/configurator/products": () => ({ channel: null, products: [] }),
    "/southbrook_kitchen/configurator/user_defaults": () => ({}),
    "/southbrook_kitchen/configurator/layout": () => ({
        items: [], summary: { base_count: 0, wall_count: 0, total: 0, price: 0, remainder_in: 0 },
    }),
};

let configuratorModuleLoaded = false;

/**
 * @param {object} opts
 * @param {object} [opts.actionParams] — becomes props.action.params (the
 *   real client-action shape; see kitchen_configurator.js setup()'s
 *   own comment on why flat props are a fallback, not the primary path).
 * @param {object} [opts.rawProps] — merged on top of {action:{params}}
 *   for the rare direct-props test path.
 * @param {Record<string, (params:object) => any>} [opts.rpcRoutes] —
 *   per-route handlers; merged over DEFAULT_ROUTES (test overrides win).
 * @param {object} [opts.services] — extra/overriding env.services.
 */
export async function mountConfigurator({
    actionParams = {},
    rawProps = {},
    rpcRoutes = {},
    services = {},
} = {}) {
    const dom = await setupDom();

    __resetRpc();
    for (const [route, handler] of Object.entries({ ...DEFAULT_ROUTES, ...rpcRoutes })) {
        __onRoute(route, handler);
    }
    const { canvasMockCalls } = await import("./kitchen_canvas_mock.mjs");
    canvasMockCalls.lastProps = null;
    canvasMockCalls.mountCount = 0;

    const owl = await import("@odoo/owl");

    if (!configuratorModuleLoaded) {
        await import(CONFIGURATOR_SRC);
        configuratorModuleLoaded = true;
    }
    const Comp = registry.category("actions").get("southbrook_kitchen_configurator");

    const notificationCalls = [];
    const actionCalls = [];
    const defaultServices = {
        notification: {
            add(message, opts) { notificationCalls.push({ message, opts }); },
        },
        action: {
            doAction(action) { actionCalls.push(action); return Promise.resolve(); },
        },
    };
    const env = { services: { ...defaultServices, ...services } };
    const props = { action: { params: actionParams }, ...rawProps };

    const root = dom.window.document.getElementById("root");
    const component = await owl.mount(Comp, root, { props, env });

    return {
        dom, root, component, owl,
        notificationCalls, actionCalls,
        rpcCalls: (route) => __calls(route),
        canvasProps: () => canvasMockCalls.lastProps,
        canvasMountCount: () => canvasMockCalls.mountCount,
    };
}
