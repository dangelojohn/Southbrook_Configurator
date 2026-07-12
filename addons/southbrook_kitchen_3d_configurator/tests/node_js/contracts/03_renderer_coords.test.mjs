/**
 * PR3.0/PR3.1 contract — renderer coordinate consumption.
 *
 * Imports the REAL kitchen_canvas.esm.js by relative path (bypassing
 * the loader's KitchenCanvas->mock alias redirect, which only fires for
 * the "@southbrook_kitchen_3d_configurator/..." bare specifier — see
 * harness/loader.mjs) and calls the REAL, unmodified
 * `_placeCabinetGroup` prototype method plus the REAL builder functions
 * (buildBaseCabinet / buildWallCabinet) against the REAL vendored r160
 * Three.js. No WebGL context is needed: Group/Mesh/Scene/matrixWorld
 * decomposition is pure CPU matrix math.
 */
import test from "node:test";
import assert from "node:assert/strict";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { setupDom } from "../harness/setup_dom.mjs";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const CANVAS_SRC = path.resolve(
    HERE, "..", "..", "..", "static", "src", "js", "canvas", "kitchen_canvas.esm.js",
);
const BASE_CABINET_SRC = path.resolve(
    HERE, "..", "..", "..", "static", "src", "js", "canvas", "base_cabinet.esm.js",
);
const WALL_CABINET_SRC = path.resolve(
    HERE, "..", "..", "..", "static", "src", "js", "canvas", "wall_cabinet.esm.js",
);
const CONSTANTS_SRC = path.resolve(
    HERE, "..", "..", "..", "static", "src", "js", "canvas", "constants.esm.js",
);

async function loadReal() {
    await setupDom();
    const { KitchenCanvas } = await import(CANVAS_SRC);
    const { buildBaseCabinet } = await import(BASE_CABINET_SRC);
    const { buildWallCabinet } = await import(WALL_CABINET_SRC);
    const { IN, WBY } = await import(CONSTANTS_SRC);
    const THREE = global.window.THREE;
    return { KitchenCanvas, buildBaseCabinet, buildWallCabinet, IN, WBY, THREE };
}

function fakeCanvas(THREE) {
    const scene = new THREE.Scene();
    return { T: { THREE, scene, cabObjs: [], clickable: [] } };
}

test("_placeCabinetGroup places a base cabinet's group at (x,y,z)*IN with rotation_deg", async () => {
    const { KitchenCanvas, buildBaseCabinet, IN } = await loadReal();
    const fake = fakeCanvas(global.window.THREE);
    const item = {
        width_in: 24, height_in: 34.5, depth_in: 24,
        x_position_in: 30, y_position_in: 0, z_position_in: 12,
        rotation_deg: 90,
    };
    KitchenCanvas.prototype._placeCabinetGroup.call(fake, item, buildBaseCabinet);
    assert.equal(fake.T.cabObjs.length, 1);
    const grp = fake.T.cabObjs[0];
    assert.ok(Math.abs(grp.position.x - item.x_position_in * IN) < 1e-9);
    assert.ok(Math.abs(grp.position.y - item.y_position_in * IN) < 1e-9);
    assert.ok(Math.abs(grp.position.z - item.z_position_in * IN) < 1e-9);
    assert.ok(Math.abs(grp.rotation.y - (item.rotation_deg * Math.PI) / 180) < 1e-9);
});

test("wall cabinet: explicit y_position_in mount height lands in group Y; z is depth", async () => {
    const { KitchenCanvas, buildWallCabinet, IN } = await loadReal();
    const THREE = global.window.THREE;
    const fake = fakeCanvas(THREE);
    const item = {
        width_in: 24, height_in: 30, depth_in: 12,
        x_position_in: 0, y_position_in: 54, z_position_in: 0,
        rotation_deg: 0,
    };
    KitchenCanvas.prototype._placeCabinetGroup.call(fake, item, buildWallCabinet);
    const grp = fake.T.cabObjs[0];
    assert.ok(Math.abs(grp.position.y - 54 * IN) < 1e-9, "group Y carries the real D8 mount height");

    fake.T.scene.updateMatrixWorld(true);
    // wall_cabinet.esm.js's builder returns `clickable: [wbody]` — the
    // real raycast-target set the shipped code uses to identify "the
    // carcass body mesh" (as opposed to the door face, which shares the
    // same userData.cabType tag). _placeCabinetGroup collects it into
    // T.clickable, so this reads the SAME mesh production code
    // identifies as the body, not a test-side heuristic.
    assert.equal(fake.T.clickable.length, 1);
    const body = fake.T.clickable[0];
    const p = new THREE.Vector3();
    body.matrixWorld.decompose(p, new THREE.Quaternion(), new THREE.Vector3());
    const wbD = item.depth_in * IN;
    assert.ok(Math.abs(p.z - wbD / 2) < 1e-9, "z carries depth, not elevation");
    assert.ok(Math.abs(p.y - (54 * IN + (30 * IN) / 2)) < 1e-6, "world Y = mount height + half cabinet height");
});

test("wall_cabinet __localFrame complement: explicit y (local 0) and falsy y (local WBY) reproduce the SAME world Y", async () => {
    const { KitchenCanvas, buildWallCabinet, IN, WBY } = await loadReal();
    const THREE = global.window.THREE;
    const base = { width_in: 24, height_in: 30, depth_in: 12, x_position_in: 0, z_position_in: 0, rotation_deg: 0 };

    const explicit = fakeCanvas(THREE);
    KitchenCanvas.prototype._placeCabinetGroup.call(
        explicit, { ...base, y_position_in: 54 }, buildWallCabinet,
    );
    const falsy = fakeCanvas(THREE);
    KitchenCanvas.prototype._placeCabinetGroup.call(
        falsy, { ...base, y_position_in: 0 }, buildWallCabinet,
    );

    explicit.T.scene.updateMatrixWorld(true);
    falsy.T.scene.updateMatrixWorld(true);
    const worldY = (fakeT) => {
        let body = null;
        fakeT.T.cabObjs[0].traverse((o) => { if (o.isMesh && o.userData && o.userData.cabType === "wall") body = o; });
        const p = new THREE.Vector3();
        body.matrixWorld.decompose(p, new THREE.Quaternion(), new THREE.Vector3());
        return p.y;
    };
    const yExplicit = worldY(explicit);
    const yFalsy = worldY(falsy);
    assert.ok(Math.abs(yExplicit - 54 * IN - (30 * IN) / 2) < 1e-9);
    assert.ok(Math.abs(yFalsy - WBY - (30 * IN) / 2) < 1e-9);
    assert.ok(
        Math.abs(yExplicit - yFalsy) < 1e-9,
        "hasExplicitY=true (local 0, group carries 54in) and hasExplicitY=false " +
        "(local WBY fallback, group carries 0) are byte-identical by construction " +
        "since 54in IS the default WBY — the __localFrame complement this test exercises",
    );
});
