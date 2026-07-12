/**
 * Boundary shim for "@web/core/registry". The configurator only uses
 * `registry.category("actions").add(tag, Component)` (module bottom) and
 * the harness reads it back with `.get(tag)` to obtain the real,
 * unmodified `SouthbrookKitchenConfigurator` class for mounting — no
 * export exists on the source file, exactly mirroring how Odoo's own
 * action service looks it up at runtime.
 */
const categories = new Map();

function makeCategory(name) {
    const entries = new Map();
    return {
        name,
        add(key, value) { entries.set(key, value); return this; },
        get(key) {
            if (!entries.has(key)) {
                throw new Error(`[registry shim] no entry "${key}" in category "${name}"`);
            }
            return entries.get(key);
        },
    };
}

export const registry = {
    category(name) {
        if (!categories.has(name)) categories.set(name, makeCategory(name));
        return categories.get(name);
    },
};
