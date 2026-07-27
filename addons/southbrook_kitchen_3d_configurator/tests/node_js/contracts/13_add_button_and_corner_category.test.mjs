/**
 * F15 / F1 contracts — two small, template-only inventory-panel fixes,
 * verified end-to-end through the REAL rendered OWL template (only
 * <KitchenCanvas> is mocked, same as every other component-level
 * contract in this suite).
 *
 * F15 — adding a cabinet was drag-and-drop only
 * (`_addCabinetFromProduct` even documented a "future click to add
 * button" that was never built) — an accessibility + testability gap.
 * Each catalog row now renders a real, keyboard-reachable "+ Add"
 * <button> (a SIBLING of the row's own button, not nested inside it —
 * buttons cannot legally nest) that calls
 * `_addCabinetFromProduct(product, null, null)` directly.
 *
 * F1 — `_inventoryCategoryTypes` used to map `tall -> ["tall",
 * "corner"]`, so a corner unit had no way to surface under its own
 * filter; it only ever showed up (mislabeled, uncounted as its own
 * category) buried inside the Tall tab. Corner now gets its own
 * key/tab.
 */
import test from "node:test";
import assert from "node:assert/strict";
import { mountConfigurator } from "../harness/mount_configurator.mjs";
import { tick } from "../harness/tick.mjs";

const BASE_PRODUCT = {
    product_id: 42, name: "Base 24", cabinet_type: "base", sku: "B24",
    width_in: 24, height_in: 34.5, depth_in: 24, price: 500,
    available_qty: 10, material: "white_melamine",
};
const CORNER_PRODUCT = {
    product_id: 43, name: "Corner Base 36", cabinet_type: "corner", sku: "CB36",
    width_in: 36, height_in: 34.5, depth_in: 24, price: 650,
    available_qty: 4, material: "white_melamine",
};

async function mountWithProducts(products) {
    return mountConfigurator({
        rpcRoutes: {
            "/southbrook_kitchen/configurator/products": () => ({
                channel: null, products,
            }),
        },
    });
}

test("F15: each catalog row renders a keyboard-reachable + Add button distinct from the row itself", async () => {
    const h = await mountWithProducts([BASE_PRODUCT]);
    await tick();

    const row = h.root.querySelector(".o_sbk_product_row");
    assert.ok(row, "product row rendered");
    assert.equal(row.tagName, "BUTTON", "the row itself stays a real, natively keyboard-operable <button>");

    const addBtn = h.root.querySelector(".o_sbk_prod_add_btn");
    assert.ok(addBtn, "+ Add button rendered");
    assert.equal(addBtn.tagName, "BUTTON", "+ Add must be a real <button> element (keyboard-reachable)");
    assert.notEqual(addBtn, row, "+ Add is a sibling, not the row itself");
    assert.equal(row.contains(addBtn), false, "+ Add must not be nested inside the row <button> (invalid HTML)");
});

test("F15: clicking + Add calls _addCabinetFromProduct(product, null, null) and does not also fire the row preview", async () => {
    const h = await mountWithProducts([BASE_PRODUCT]);
    await tick();

    assert.equal(h.component.state.items.length, 0);
    assert.equal(h.component.state.catalogPreview, null);

    const addBtn = h.root.querySelector(".o_sbk_prod_add_btn");
    addBtn.dispatchEvent(new h.dom.window.Event("click", { bubbles: true }));
    await tick();
    clearTimeout(h.component._autoSaveTimer);

    assert.equal(h.component.state.items.length, 1, "+ Add must append a cabinet to the layout");
    assert.equal(h.component.state.items[0].product_id, BASE_PRODUCT.product_id);
    assert.equal(h.component.state.catalogPreview, null,
        "+ Add is a distinct action from row-click preview and must not set catalogPreview either");
});

test("F1: a corner product gets its own 'Corner' filter tab (not folded into Tall)", async () => {
    const h = await mountWithProducts([BASE_PRODUCT, CORNER_PRODUCT]);
    await tick();

    assert.equal(h.component._categoryCount("tall"), 0, "corner must not be counted under Tall");
    assert.equal(h.component._categoryCount("corner"), 1, "corner has its own count");

    const options = [...h.root.querySelectorAll(".o_sbk_inv_cat_select option")]
        .map((o) => o.value);
    assert.ok(options.includes("corner"), "a Corner <option> renders in the category filter select");

    h.component._setInventoryCategory("corner");
    await tick();
    const filtered = h.component._filteredProducts();
    assert.equal(filtered.length, 1);
    assert.equal(filtered[0].product_id, CORNER_PRODUCT.product_id);
});

test("F1: filtering by 'tall' no longer includes corner products (non-regression check on the old folded mapping)", async () => {
    const h = await mountWithProducts([BASE_PRODUCT, CORNER_PRODUCT]);
    h.component._setInventoryCategory("tall");
    await tick();
    const filtered = h.component._filteredProducts();
    assert.equal(filtered.length, 0, "no tall products in this fixture, and corner must not leak in");
});
