/**
 * PR3.1 golden artifact — tests/golden/design83.snapshot.json.
 *
 * Wires the deploy-time byte-identity check (captured live in Chrome
 * against Design 83: 4 base + 4 wall cabinets, all rotation_deg=0, back
 * wall, room 96x96 -> hash 3591767287, mesh_count 48) into an automated
 * guard: this test rebuilds the 8 cabinets through the REAL builders
 * (buildBaseCabinet / buildWallCabinet) + the REAL _placeCabinetGroup,
 * snapshots them exactly like KitchenCanvas._sbSceneSnapshot() does
 * (same rounding, same sort), and asserts the result equals the golden
 * `rows`.
 *
 * HONESTY NOTE (read before trusting this as "the real design-83 rows"):
 * design_id 83 does not exist in any local/clone database reachable
 * from this environment (checked: the local `southbrook` dev DB has no
 * such row) — only the QNAP production DB has it, and this harness must
 * never touch live data. The 8 items below were NOT read from a
 * database; they were algebraically RECOVERED from the golden `rows`
 * themselves by solving each builder's own (verbatim, unmodified)
 * position formulas backwards — e.g. base_cabinet.esm.js's toekick
 * mesh sits at local Y = 3.5*IN/2; golden row [1,0.146,1,0] gives
 * world Y 0.146 = 3.5*IN/2 exactly with x_position_in=0, cbD=24in
 * (z=1=cbD/2) — repeated for every one of the 48 rows until all matched
 * uniquely. This is therefore a PROOF (by reconstruction through the
 * real formulas) that these specific 8 items, run through the real
 * unmodified code, reproduce the golden output — not independent
 * confirmation that they are literally what was in design_id 83's DB
 * row. The regression-guard value is identical either way: if
 * `_placeCabinetGroup`, `buildBaseCabinet`, or `buildWallCabinet` ever
 * change in a way that alters this output, this test goes red.
 *
 * The stored `hash` (3591767287) was produced by an ad-hoc snippet run
 * live in a browser console at capture time; its exact algorithm is not
 * recorded anywhere in the shipped codebase (grepped: no hash/crc32/
 * fnv/djb2 function exists in this addon), and a handful of common
 * 32-bit string hashes (Java String.hashCode, FNV-1a, djb2, sdbm) over
 * JSON.stringify(rows) and over the flattened rows do not reproduce it
 * — so this test does NOT attempt to re-derive that integer. The gate
 * is the stronger, more direct check: deep-equality against `rows`
 * itself, which is the actual regression signal the comment in
 * design83.snapshot.json asks PR3a to wire up.
 */
import test from "node:test";
import assert from "node:assert/strict";
import path from "node:path";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { setupDom } from "../harness/setup_dom.mjs";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ADDON_ROOT = path.resolve(HERE, "..", "..", "..");
const CANVAS_SRC = path.resolve(ADDON_ROOT, "static", "src", "js", "canvas", "kitchen_canvas.esm.js");
const BASE_CABINET_SRC = path.resolve(ADDON_ROOT, "static", "src", "js", "canvas", "base_cabinet.esm.js");
const WALL_CABINET_SRC = path.resolve(ADDON_ROOT, "static", "src", "js", "canvas", "wall_cabinet.esm.js");
const GOLDEN_PATH = path.resolve(ADDON_ROOT, "tests", "golden", "design83.snapshot.json");

// Reconstructed design-83 items — see the file-level HONESTY NOTE above.
const BASE_ITEMS = [0, 24, 48, 72].map((x) => ({
    cabinet_type: "base",
    width_in: 24, height_in: 34.5, depth_in: 24,
    x_position_in: x, y_position_in: 0, z_position_in: 0, rotation_deg: 0,
}));
const WALL_ITEMS = [0, 15, 30, 45].map((x) => ({
    cabinet_type: "wall",
    width_in: 15, height_in: 30, depth_in: 12,
    x_position_in: x, y_position_in: 54, z_position_in: 0, rotation_deg: 0,
}));

test("design-83 reconstruction, run through the real builders + _placeCabinetGroup, matches the golden snapshot rows", async () => {
    await setupDom();
    const { KitchenCanvas } = await import(CANVAS_SRC);
    const { buildBaseCabinet } = await import(BASE_CABINET_SRC);
    const { buildWallCabinet } = await import(WALL_CABINET_SRC);
    const THREE = global.window.THREE;

    const scene = new THREE.Scene();
    const fake = { T: { THREE, scene, cabObjs: [], clickable: [] } };

    for (const it of BASE_ITEMS) {
        KitchenCanvas.prototype._placeCabinetGroup.call(fake, it, buildBaseCabinet);
    }
    for (const it of WALL_ITEMS) {
        KitchenCanvas.prototype._placeCabinetGroup.call(fake, it, buildWallCabinet);
    }

    // Same algorithm as KitchenCanvas._sbSceneSnapshot() (kitchen_canvas.esm.js):
    // decompose every leaf mesh's matrixWorld, round, sort.
    const rows = KitchenCanvas.prototype._sbSceneSnapshot.call(fake);

    const golden = JSON.parse(readFileSync(GOLDEN_PATH, "utf8"));
    assert.equal(rows.length, golden.mesh_count, `mesh_count: expected ${golden.mesh_count}, got ${rows.length}`);
    assert.deepEqual(
        rows, golden.rows,
        "reconstructed scene snapshot must byte-match tests/golden/design83.snapshot.json's `rows` " +
        "(the PR3.1 byte-identity baseline) — a mismatch means _placeCabinetGroup or a builder changed " +
        "the renderer's coordinate output",
    );
});
