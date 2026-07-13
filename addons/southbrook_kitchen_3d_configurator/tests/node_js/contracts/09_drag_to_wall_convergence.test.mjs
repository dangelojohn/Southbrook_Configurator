/**
 * PR4b contract — drag-onto-wall converges with select-then-add.
 *
 * Before PR4b the backend configurator had two placement interactions
 * that DIVERGED on which wall a cabinet lands on:
 *
 *   (1) select a wall (click/hover -> state.activeWall) then Add  -> honours the wall
 *   (2) drag a product tile and DROP it onto a wall in the 3D view -> ignored
 *       the drop point and inherited state.activeWall (default BACK)
 *
 * PR4b closes the gap WITHOUT adding any placement math on the client:
 * `_onCanvasDrop` now asks the canvas which wall the pointer dropped onto
 * (`_computeDropWall` -> canvas `computeDropWall` -> the same
 * `_raycastWall` the click/hover wall-picker uses, reading userData.wall
 * off the tagged room-wall meshes) and passes it to
 * `_addCabinetFromProduct(product, targetX, wallOverride)`. The server
 * path is unchanged: a non-back wall is still routed through the pure
 * `kitchen_layout_engine` (_place_lines_on_wall) and the engine pose is
 * applied back onto state.items (_applyServerPlacements, locked by #08).
 *
 * The INVARIANT this contract locks (the lead's release gate): selecting
 * a wall then Add, and dragging a cabinet directly onto that SAME wall,
 * produce an IDENTICAL persisted cabinet record — not visually similar,
 * IDENTICAL canonical model — modulo the intentionally-unique layout_key.
 * Because both inputs carry the same `wall`, they feed the same engine
 * and therefore persist the same pose. Nothing here computes a
 * coordinate; it asserts the two UX paths converge on one record.
 */
import test from "node:test";
import assert from "node:assert/strict";
import { mountConfigurator } from "../harness/mount_configurator.mjs";

const PRODUCT = {
    product_id: 42, name: "Base 24", cabinet_type: "base",
    width_in: 24, height_in: 34.5, depth_in: 24, price: 500,
};

// A fake HTML5 drop event carrying our product in the same MIME slot
// _onProductDragStart writes (kitchen_configurator.js).
function dropEvent(productId) {
    return {
        preventDefault() {},
        dataTransfer: {
            getData(type) {
                if (type === "application/x-sbk-product") {
                    return JSON.stringify({ product_id: productId });
                }
                return "";
            },
        },
    };
}

// Stub the canvas imperative API the component reaches into on drop.
// computeDropWall returns whatever wall we say the pointer hit; the drop
// X is irrelevant to `wall` so it stays null (append-at-end).
function stubCanvas(component, wall) {
    component._canvasApi = {
        computeDropX: () => null,
        computeDropWall: () => wall,
    };
}

function newestItem(component) {
    const items = component.state.items || [];
    return items[items.length - 1];
}

// Strip the intentionally-unique key so two records can be compared for
// canonical identity. (layout_key = `${type}-add-${Date.now()}-…`.)
function canonical(item) {
    const { layout_key, ...rest } = item;
    return rest;
}

async function freshConfigurator() {
    const h = await mountConfigurator({
        rpcRoutes: {
            "/southbrook_kitchen/configurator/products": () => ({
                channel: null, products: [PRODUCT],
            }),
        },
    });
    // Ensure the drop handler can resolve the product id -> product.
    h.component.state.products = [PRODUCT];
    return h;
}

test("dropping a product onto the LEFT wall tags the new cabinet wall='left'", async () => {
    const h = await freshConfigurator();
    stubCanvas(h.component, "left");

    h.component._onCanvasDrop(dropEvent(PRODUCT.product_id));
    clearTimeout(h.component._autoSaveTimer);

    const item = newestItem(h.component);
    assert.ok(item, "a cabinet was added by the drop");
    assert.equal(item.wall, "left");
});

test("a drop that MISSES every wall (computeDropWall null) falls back to activeWall", async () => {
    const h = await freshConfigurator();
    h.component.state.activeWall = "right";      // previously-picked wall
    stubCanvas(h.component, null);               // ray missed all walls

    h.component._onCanvasDrop(dropEvent(PRODUCT.product_id));
    clearTimeout(h.component._autoSaveTimer);

    // Non-regression: with no drop-wall, behaviour is exactly pre-PR4b —
    // inherit the active wall.
    assert.equal(newestItem(h.component).wall, "right");
});

test("a drop with no active wall AND no wall hit defaults to BACK (unchanged default)", async () => {
    const h = await freshConfigurator();
    h.component.state.activeWall = null;
    stubCanvas(h.component, null);

    h.component._onCanvasDrop(dropEvent(PRODUCT.product_id));
    clearTimeout(h.component._autoSaveTimer);

    assert.equal(newestItem(h.component).wall, "back");
});

test("INVARIANT: drag-onto-left and select-left-then-Add produce an identical record", async () => {
    // Path A — select the wall, then Add (no drop override).
    const a = await freshConfigurator();
    a.component.state.activeWall = "left";
    a.component._addCabinetFromProduct(PRODUCT, null /* targetX */);
    clearTimeout(a.component._autoSaveTimer);
    const recordA = canonical(newestItem(a.component));

    // Path B — drag the SAME product and drop it onto the left wall.
    // activeWall is deliberately NOT left, proving the drop determines
    // the wall on its own.
    const b = await freshConfigurator();
    b.component.state.activeWall = null;
    stubCanvas(b.component, "left");
    b.component._onCanvasDrop(dropEvent(PRODUCT.product_id));
    clearTimeout(b.component._autoSaveTimer);
    const recordB = canonical(newestItem(b.component));

    // Byte-identical canonical model (same wall, same y/z, same dims,
    // same everything) — the two UX paths converge. Only layout_key
    // (unique id, stripped by canonical()) differs.
    assert.deepEqual(recordB, recordA);
    assert.equal(recordA.wall, "left");
    assert.equal(recordB.wall, "left");
});
