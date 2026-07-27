/**
 * F8 contract — scene mesh userData.item must be reference-identical to
 * the matching state.items entry, not a detached clone.
 *
 * `_placeCabinetGroup` (kitchen_canvas.esm.js) builds each cabinet's
 * geometry against a SHALLOW COPY of the state item
 * (`{ ...it, x_position_in: 0, __localFrame: true }`) so the builder's
 * local-frame math (walls/panels reading `__localFrame` to zero their
 * own contribution) works regardless of the enclosing THREE.Group's
 * world transform. Every builder (buildBaseCabinet / buildWallCabinet /
 * buildOtherCabinet / buildEndCapPanel) attaches THAT copy as
 * `mesh.userData.item` via mesh_factory.esm.js's `ud` option.
 *
 * Before the F8 fix, nothing rebound that identity back onto the real
 * item: `mesh.userData.item !== state.items[i]`. Consequence (verified
 * live): kitchen_canvas.esm.js's `_onMouseDown` sets
 * `this.T.movingItem = h.userData.item` (the clone); drag-move and Q/E
 * rotate then mutate the CLONE's x_position_in / rotation_deg, which is
 * discarded on the next rebuild, while `_savePinnedPosition` /
 * `onMoveItem` still persist the clone's values to the DB by
 * layout_key — a silent no-op in the client's own state that only
 * surfaces as a client/DB divergence on reload. The clone's
 * x_position_in is also permanently forced to 0, so anything reading
 * the selected item's x (state.selected is populated straight from
 * `h.userData.item`) read 0.
 *
 * This test exercises the REAL, unmodified `_placeCabinetGroup` and the
 * REAL builders against the REAL vendored r160 Three.js — same pattern
 * as 03_renderer_coords.test.mjs and 06_golden_design83.test.mjs (the
 * closest existing models): no WebGL context needed, pure CPU matrix
 * math, `.call(fake, ...)` against a fake `this.T` rather than a full
 * OWL DOM mount. It renders one back-wall base cabinet and one
 * left-wall wall cabinet (as the brief specifies) and asserts identity
 * — not just deep-equality — between the attached mesh userData.item
 * and the original state.items entries.
 */
import test from "node:test";
import assert from "node:assert/strict";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { setupDom } from "../harness/setup_dom.mjs";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ADDON_ROOT = path.resolve(HERE, "..", "..", "..");
const CANVAS_SRC = path.resolve(ADDON_ROOT, "static", "src", "js", "canvas", "kitchen_canvas.esm.js");
const BASE_CABINET_SRC = path.resolve(ADDON_ROOT, "static", "src", "js", "canvas", "base_cabinet.esm.js");
const WALL_CABINET_SRC = path.resolve(ADDON_ROOT, "static", "src", "js", "canvas", "wall_cabinet.esm.js");

async function loadReal() {
    await setupDom();
    const { KitchenCanvas } = await import(CANVAS_SRC);
    const { buildBaseCabinet } = await import(BASE_CABINET_SRC);
    const { buildWallCabinet } = await import(WALL_CABINET_SRC);
    const THREE = global.window.THREE;
    return { KitchenCanvas, buildBaseCabinet, buildWallCabinet, THREE };
}

function fakeCanvas(THREE) {
    const scene = new THREE.Scene();
    return { T: { THREE, scene, cabObjs: [], clickable: [] } };
}

test("F8: back-wall base cabinet's clickable mesh userData.item is the REAL state item, not a clone", async () => {
    const { KitchenCanvas, buildBaseCabinet, THREE } = await loadReal();
    const fake = fakeCanvas(THREE);

    // Simulates a real state.items entry — same shape _addCabinetFromProduct
    // / load_design_lines produce.
    const backItem = {
        layout_key: "back-1", cabinet_type: "base", wall: "back",
        width_in: 24, height_in: 34.5, depth_in: 24,
        x_position_in: 30, y_position_in: 0, z_position_in: 0, rotation_deg: 0,
    };

    KitchenCanvas.prototype._placeCabinetGroup.call(fake, backItem, buildBaseCabinet);

    assert.equal(fake.T.clickable.length, 1);
    const body = fake.T.clickable[0];

    // Reference identity, not deep-equality: before the F8 fix this mesh's
    // userData.item was `{ ...backItem, x_position_in: 0, __localFrame: true }`
    // — a DIFFERENT object with x_position_in forced to 0.
    assert.equal(body.userData.item, backItem,
        "clickable mesh userData.item must be === the real state item");
    assert.equal(body.userData.item.x_position_in, 30,
        "must read the item's REAL x, not the local-frame copy's forced 0");

    // The enclosing group also carries the rebound identity.
    assert.equal(fake.T.cabObjs[0].userData.item, backItem);

    // Mutation proof: mutating the field the drag/rotate handlers write
    // (kitchen_canvas.esm.js's _onMouseMove / _rotateSelected in
    // kitchen_configurator.js both write straight onto
    // `h.userData.item` / `this.T.movingItem`) must be visible on the
    // SAME object callers hold a reference to (state.items[i]) — this is
    // exactly what was silently broken before F8.
    body.userData.item.x_position_in = 999;
    body.userData.item.rotation_deg = 90;
    assert.equal(backItem.x_position_in, 999,
        "a drag-move mutation via userData.item must land on the real state item");
    assert.equal(backItem.rotation_deg, 90,
        "a rotate mutation via userData.item must land on the real state item");
});

test("F8: left-wall wall cabinet's clickable mesh userData.item is the REAL state item, not a clone", async () => {
    const { KitchenCanvas, buildWallCabinet, THREE } = await loadReal();
    const fake = fakeCanvas(THREE);

    const leftItem = {
        layout_key: "left-1", cabinet_type: "wall", wall: "left",
        width_in: 24, height_in: 30, depth_in: 12,
        x_position_in: 0, y_position_in: 54, z_position_in: 18, rotation_deg: 90,
    };

    KitchenCanvas.prototype._placeCabinetGroup.call(fake, leftItem, buildWallCabinet);

    assert.equal(fake.T.clickable.length, 1);
    const body = fake.T.clickable[0];

    assert.equal(body.userData.item, leftItem,
        "clickable mesh userData.item must be === the real state item");
    assert.equal(body.userData.item.__localFrame, undefined,
        "the real state item never carries the builder-only __localFrame " +
        "marker — that marker only exists on the local-frame copy " +
        "_placeCabinetGroup builds against; seeing it here would mean " +
        "userData.item is still that copy, not the real item");

    // Mutation proof: mutating the field the drag handler writes
    // (kitchen_canvas.esm.js's _onMouseMove writes straight onto
    // `this.T.movingItem.x_position_in`, which is `h.userData.item`)
    // must be visible on the SAME object callers hold a reference to
    // (state.items[i]) — before F8 this mutated a detached clone the
    // real leftItem never saw.
    body.userData.item.x_position_in = 777;
    assert.equal(leftItem.x_position_in, 777,
        "a drag-move mutation via userData.item must land on the real state item");
});

test("F8: two cabinets placed together each keep their OWN distinct real-item identity", async () => {
    const { KitchenCanvas, buildBaseCabinet, buildWallCabinet, THREE } = await loadReal();
    const fake = fakeCanvas(THREE);

    const backItem = {
        layout_key: "back-1", cabinet_type: "base", wall: "back",
        width_in: 24, height_in: 34.5, depth_in: 24,
        x_position_in: 0, y_position_in: 0, z_position_in: 0, rotation_deg: 0,
    };
    const leftItem = {
        layout_key: "left-1", cabinet_type: "wall", wall: "left",
        width_in: 24, height_in: 30, depth_in: 12,
        x_position_in: 0, y_position_in: 54, z_position_in: 36, rotation_deg: 90,
    };

    KitchenCanvas.prototype._placeCabinetGroup.call(fake, backItem, buildBaseCabinet);
    KitchenCanvas.prototype._placeCabinetGroup.call(fake, leftItem, buildWallCabinet);

    assert.equal(fake.T.clickable.length, 2);
    const [backBody, leftBody] = fake.T.clickable;

    assert.equal(backBody.userData.item, backItem);
    assert.equal(leftBody.userData.item, leftItem);
    assert.notEqual(backBody.userData.item, leftBody.userData.item);

    // Mutating one must never bleed onto the other (would indicate they
    // somehow share the same detached clone).
    backBody.userData.item.x_position_in = 111;
    assert.equal(backItem.x_position_in, 111);
    assert.equal(leftItem.x_position_in, 0, "leftItem must be untouched by a mutation on backItem");
});
