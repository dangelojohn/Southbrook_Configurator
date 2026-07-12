/**
 * Minimal jsdom bootstrap for mounting the REAL OWL
 * SouthbrookKitchenConfigurator component headlessly in Node (no
 * browser/Chromium available in this environment — see the PR3a
 * runnability gate findings in tests/node_js/README.md).
 *
 * Must run (and be awaited) BEFORE any dynamic `import("@odoo/owl")` or
 * import of source files that transitively import it — Owl's ESM build
 * reads `Element`/`Node`/etc. at module-evaluation time, not lazily.
 * Every test file therefore calls `await setupDom()` first, then uses
 * dynamic `import()` for everything else.
 */
import { JSDOM } from "jsdom";
import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const HERE = path.dirname(fileURLToPath(import.meta.url));
const VENDORED_THREE = path.resolve(
    HERE, "..", "..", "..", "..", "southbrook_estimating",
    "static", "lib", "three", "three.min.js",
);

let installed = false;

export async function setupDom() {
    const dom = new JSDOM(
        "<!doctype html><html><body><div id='root'></div></body></html>",
        { url: "http://localhost/odoo/southbrook_kitchen_configurator" },
    );
    dom.window.requestAnimationFrame = (cb) => setTimeout(cb, 0);
    dom.window.cancelAnimationFrame = (id) => clearTimeout(id);

    global.window = dom.window;
    global.document = dom.window.document;
    for (const key of Object.getOwnPropertyNames(dom.window)) {
        if (key in global) continue;
        try { global[key] = dom.window[key]; } catch { /* getter-only, skip */ }
    }
    global.requestAnimationFrame = dom.window.requestAnimationFrame;
    global.cancelAnimationFrame = dom.window.cancelAnimationFrame;

    // three_loader.esm.js::loadThreeJS() reads `window.THREE` — in
    // production the vendored r160 UMD build loads as a plain <script>
    // via web.assets_backend before kitchen_configurator.js runs. Same
    // artifact, same global-attach contract, here via CJS require.
    if (!installed) {
        dom.window.THREE = require(VENDORED_THREE);
        installed = true;
    } else {
        dom.window.THREE = global.__sbk_three_cache;
    }
    global.__sbk_three_cache = dom.window.THREE;

    return dom;
}
