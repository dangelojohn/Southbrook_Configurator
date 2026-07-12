/**
 * Boundary shim for "@web/core/network/rpc" (real module lives in Odoo's
 * web addon; not an npm package). The configurator's only network
 * boundary — every RPC the component under test makes goes through this
 * single mockable function so tests assert against a call log and a
 * per-route response table instead of hitting a live Odoo server.
 *
 * Import this shim directly (relative path) from test files to configure
 * routes; the loader (harness/loader.mjs) resolves the SAME absolute
 * file for the "@web/core/network/rpc" specifier the real source files
 * import, so both sides share one module-cache singleton.
 */

let routes = new Map();     // route -> (params) => value | Promise<value> | throws
let callLog = [];           // [{route, params}]

export function __resetRpc() {
    routes = new Map();
    callLog = [];
}

/** Register (or overwrite) a handler for an exact route string. */
export function __onRoute(route, handler) {
    routes.set(route, handler);
}

/** Make an exact route reject (simulates a failed/erroring RPC). */
export function __rejectRoute(route, error) {
    routes.set(route, () => { throw (error instanceof Error ? error : new Error(String(error))); });
}

export function __calls(route) {
    return route ? callLog.filter(c => c.route === route) : callLog.slice();
}

export async function rpc(route, params = {}) {
    callLog.push({ route, params });
    const handler = routes.get(route);
    if (!handler) {
        throw new Error(
            `[rpc shim] no handler registered for route "${route}" — ` +
            `call __onRoute("${route}", fn) before mounting.`
        );
    }
    const result = handler(params);
    return result;
}
