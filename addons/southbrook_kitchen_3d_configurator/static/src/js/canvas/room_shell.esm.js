/** @odoo-module **/
/**
 * Southbrook Kitchen 3D Configurator — room-shell mesh builder.
 *
 * Rec D · Sprint 2d · Step 11 · closure-body extraction.
 *
 * Builds the fixed room geometry: floor plane, back + left walls (full
 * height), right + front wall selection strips (low), wainscoting rail on
 * the back wall, and the floor grid. Extracted from
 * kitchen_configurator.js:1303-1322 (back/left verbatim).
 *
 * The caller passes:
 *   - THREE (vendored module) — needed for PlaneGeometry/BoxGeometry/
 *     GridHelper constructors
 *   - scene — the target Three.js scene (grid is added directly;
 *     the four PBR meshes go through `mk`)
 *   - mk — the closure that maps to the shared makeMesh factory in
 *     canvas/mesh_factory.esm.js
 *   - palette — hex colors {floor, wall1, wall2, cabDark, grid}
 *   - {rw, rh, rd} — room dimensions in scene units
 *
 * Returns the objects array the caller pushes into roomObjs, so the
 * dispose pass at the top of _buildScene can walk them uniformly.
 */

import { IN } from "@southbrook_kitchen_3d_configurator/js/canvas/constants.esm";

/**
 * @param {typeof THREE} THREE
 * @param {THREE.Scene} scene
 * @param {(geo:any, color:number, pos:any, rotE:any, opts?:object) => THREE.Mesh} mk
 * @param {{ floor: number, wall1: number, wall2: number, cabDark: number, grid: number }} palette
 * @param {number} rw
 * @param {number} rh
 * @param {number} rd
 * @returns {{ objects: THREE.Object3D[], grid: THREE.GridHelper }}
 */
export function buildRoomShell(THREE, scene, mk, palette, rw, rh, rd) {
    const floor = mk(
        new THREE.PlaneGeometry(rw, rd), palette.floor,
        [rw/2, 0, rd/2], [-Math.PI/2, 0, 0],
        { rs: true, rough: 0.95, metal: 0.0 },
    );
    // Room walls carry a `wall` tag so the canvas can raycast + select them
    // (interactive walls). Back + left are the FAR walls of the open cutaway,
    // rendered full height. Right + front are the NEAR (open) side — rendering
    // them full height would enclose the room and block the iso view, so they
    // are drawn as low floor strips at the room boundary: always visible +
    // clickable + glow-highlightable exactly like the tall walls, but too low
    // to occlude. The toolbar wall-picker is the guaranteed way to select any
    // wall; these strips add the click-to-select affordance in 3D.
    //
    // F7 fix (2026-07-27) — "back"/"left" here MUST match
    // constants.esm.js's FULL_HEIGHT_WALLS; kitchen_canvas.esm.js's
    // drop-inference raycast (`_raycastDropWall`) reads that constant
    // to decide which wall meshes a drag-drop is allowed to land on
    // (never the low kick-strips built below for right/front). If a
    // wall ever moves between the full-height and kick-strip render
    // paths, update FULL_HEIGHT_WALLS in the same commit.
    const bwall = mk(
        new THREE.PlaneGeometry(rw, rh), palette.wall1,
        [rw/2, rh/2, 0], null,
        { rs: true, rough: 0.9, metal: 0.0,
          ud: { isRoomWall: true, wall: "back" } },
    );
    const lwall = mk(
        new THREE.PlaneGeometry(rd, rh), palette.wall2,
        [0, rh/2, rd/2], [0, Math.PI/2, 0],
        { rs: true, rough: 0.9, metal: 0.0,
          ud: { isRoomWall: true, wall: "left" } },
    );
    const stripH = 12 * IN;   // low "kick wall" — marks the wall without blocking
    const rwall = mk(
        new THREE.BoxGeometry(0.03, stripH, rd), palette.wall2,
        [rw, stripH/2, rd/2], null,
        { rs: true, rough: 0.9, metal: 0.0,
          ud: { isRoomWall: true, wall: "right" } },
    );
    const fwall = mk(
        new THREE.BoxGeometry(rw, stripH, 0.03), palette.wall1,
        [rw/2, stripH/2, rd], null,
        { rs: true, rough: 0.9, metal: 0.0,
          ud: { isRoomWall: true, wall: "front" } },
    );

    // Wainscoting rail on back wall — semi-gloss wood trim
    const railY = 36 * IN;
    const rail = mk(
        new THREE.BoxGeometry(rw, 0.012, 0.02), palette.cabDark,
        [rw/2, railY, 0.01], null,
        { rough: 0.55, metal: 0.0 },
    );

    // Floor grid
    const gSz = Math.max(rw, rd) + 6;
    const grid = new THREE.GridHelper(gSz, Math.ceil(gSz * 2), palette.grid, palette.grid);
    grid.position.set(rw/2, 0.002, rd/2);
    grid.material.transparent = true;
    grid.material.opacity     = 0.18;
    scene.add(grid);

    return { objects: [floor, bwall, lwall, rwall, fwall, rail, grid], grid,
             walls: { back: bwall, left: lwall, right: rwall, front: fwall } };
}
