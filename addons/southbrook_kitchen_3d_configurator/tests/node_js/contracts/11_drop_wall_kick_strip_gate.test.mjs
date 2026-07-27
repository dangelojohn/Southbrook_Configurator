/**
 * F7 contract (part b) — a drop-inference raycast must never resolve
 * onto a "kick-strip" wall.
 *
 * room_shell.esm.js renders back+left as FULL-HEIGHT wall planes but
 * right+front as low 12" floor strips ("kick-strip" walls) — present so
 * those walls stay click-selectable (toolbar + 3D click-to-select)
 * without enclosing the open-cutaway iso/persp view. All four meshes
 * carry the same `userData.wall` tag and are equally valid raycast
 * targets for CLICK/HOVER (`_raycastWall`, used by `_onMouseDown` /
 * `_onMouseOver`).
 *
 * Before the F7 fix, `_computeDropWall` (the HTML5-drop wall inference
 * `_onCanvasDrop` -> `_addCabinetFromProduct` consults) also raycast
 * through `_raycastWall` — all four meshes, kick-strips included. A drop
 * over open floor near the room boundary could land on an invisible
 * kick-strip and get silently inferred as a deliberate drop-onto-wall,
 * which (via kitchen_configurator.js's old wallOverride-first
 * precedence, also fixed by F7) could override a rep's actual Active
 * Wall selection.
 *
 * `_raycastDropWall` is the fix: it filters `wallMeshes` down to
 * `FULL_HEIGHT_WALLS` (constants.esm.js — back/left today) BEFORE
 * testing intersection, so a kick-strip mesh is never even offered to
 * the raycaster for a drop. `_raycastWall` (click/hover) is unchanged
 * and unfiltered — kick-strip walls stay explicitly clickable.
 *
 * This test doesn't need a camera/NDC/real raycast geometry — it
 * exercises the REAL, unmodified `_raycastWall` / `_raycastDropWall`
 * methods directly against a fake raycaster whose `intersectObjects`
 * reports a hit only for whichever mesh object is actually present in
 * the candidate list it's given, so the assertion is really about WHICH
 * meshes each method offers to the raycaster — the actual bug/fix.
 */
import test from "node:test";
import assert from "node:assert/strict";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { setupDom } from "../harness/setup_dom.mjs";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ADDON_ROOT = path.resolve(HERE, "..", "..", "..");
const CANVAS_SRC = path.resolve(ADDON_ROOT, "static", "src", "js", "canvas", "kitchen_canvas.esm.js");
const CONSTANTS_SRC = path.resolve(ADDON_ROOT, "static", "src", "js", "canvas", "constants.esm.js");

async function loadReal() {
    await setupDom();
    const { KitchenCanvas } = await import(CANVAS_SRC);
    const { FULL_HEIGHT_WALLS } = await import(CONSTANTS_SRC);
    return { KitchenCanvas, FULL_HEIGHT_WALLS };
}

// A fake THREE.Raycaster: "hits" `targetMesh` if and only if it appears
// in the candidate array `_raycastWall`/`_raycastDropWall` pass in —
// i.e. it simulates the ray genuinely intersecting that mesh, and the
// production methods are what decide whether that mesh was even a
// candidate.
function fakeRaycasterHitting(targetMesh) {
    return {
        intersectObjects(meshes) {
            return meshes.includes(targetMesh) ? [{ object: targetMesh }] : [];
        },
    };
}

function fakeWallMeshes() {
    return {
        back:  { userData: { isRoomWall: true, wall: "back" } },
        left:  { userData: { isRoomWall: true, wall: "left" } },
        right: { userData: { isRoomWall: true, wall: "right" } },   // kick-strip
        front: { userData: { isRoomWall: true, wall: "front" } },  // kick-strip
    };
}

test("FULL_HEIGHT_WALLS is exactly back+left (the room_shell.esm.js full-height walls)", async () => {
    const { FULL_HEIGHT_WALLS } = await loadReal();
    assert.deepEqual([...FULL_HEIGHT_WALLS].sort(), ["back", "left"]);
});

test("_raycastWall (click/hover) still resolves a hit on a kick-strip wall (right)", async () => {
    const { KitchenCanvas } = await loadReal();
    const wallMeshes = fakeWallMeshes();
    const fake = { T: { wallMeshes } };
    const raycaster = fakeRaycasterHitting(wallMeshes.right);

    const result = KitchenCanvas.prototype._raycastWall.call(fake, raycaster);
    assert.equal(result, "right",
        "click/hover wall-picking must still be able to select a kick-strip wall");
});

test("_raycastDropWall (drop-inference) NEVER resolves a hit on a kick-strip wall (right)", async () => {
    const { KitchenCanvas } = await loadReal();
    const wallMeshes = fakeWallMeshes();
    const fake = { T: { wallMeshes } };
    // The ray genuinely hits the right kick-strip mesh (same fake
    // raycaster as the click/hover test above) — but drop-inference
    // must not even offer that mesh to the raycaster.
    const raycaster = fakeRaycasterHitting(wallMeshes.right);

    const result = KitchenCanvas.prototype._raycastDropWall.call(fake, raycaster);
    assert.equal(result, null,
        "a drop must never be inferred onto a kick-strip wall, even if the ray geometrically hits it");
});

test("_raycastDropWall (drop-inference) NEVER resolves a hit on a kick-strip wall (front)", async () => {
    const { KitchenCanvas } = await loadReal();
    const wallMeshes = fakeWallMeshes();
    const fake = { T: { wallMeshes } };
    const raycaster = fakeRaycasterHitting(wallMeshes.front);

    const result = KitchenCanvas.prototype._raycastDropWall.call(fake, raycaster);
    assert.equal(result, null);
});

test("_raycastDropWall DOES resolve a hit on a full-height wall (left)", async () => {
    const { KitchenCanvas } = await loadReal();
    const wallMeshes = fakeWallMeshes();
    const fake = { T: { wallMeshes } };
    const raycaster = fakeRaycasterHitting(wallMeshes.left);

    const result = KitchenCanvas.prototype._raycastDropWall.call(fake, raycaster);
    assert.equal(result, "left",
        "a genuine drop onto a full-height wall must still resolve normally");
});
