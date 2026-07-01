/** @odoo-module **/
/**
 * Southbrook Kitchen 3D Configurator — per-zone drop lanes.
 *
 * Rec D · Sprint 2d · Step 13 · closure-body extraction.
 *
 * Builds the three drop-target lanes (BASE / WALL / TALL_END) that
 * highlight during a drag-from-inventory. Extracted from
 * kitchen_configurator.js:1575-1622 verbatim. Each lane starts
 * `visible=false, opacity=0.0`; the caller flips visibility +
 * opacity as the pointer enters/exits each zone.
 *
 * D16 — the three colors and geometry math are unchanged from the
 * pre-2d block; only their host module moved.
 */

import { IN, WBY } from "@southbrook_kitchen_3d_configurator/js/canvas/constants";

/**
 * @param {typeof THREE} THREE
 * @param {THREE.Scene} scene
 * @param {number} rw — room width in scene units
 * @param {number} rh — room height in scene units
 * @returns {{ base: THREE.Mesh, wall: THREE.Mesh, tall: THREE.Mesh }}
 */
export function buildDropLanes(THREE, scene, rw, rh) {
    const wallH    = 30 * IN;
    const baseD    = 24 * IN;
    const wallBotZ = WBY;

    // BASE lane — thin floor band along the back wall, full room width
    const base = new THREE.Mesh(
        new THREE.PlaneGeometry(rw, baseD),
        new THREE.MeshBasicMaterial({
            color: 0x1866d4, transparent: true, opacity: 0.0,
            side: THREE.DoubleSide, depthWrite: false,
        }),
    );
    base.rotation.x = -Math.PI / 2;
    base.position.set(rw / 2, 0.004, baseD / 2);
    base.visible = false;
    scene.add(base);

    // WALL lane — vertical band on the back wall at wall-cab z
    const wall = new THREE.Mesh(
        new THREE.PlaneGeometry(rw, wallH),
        new THREE.MeshBasicMaterial({
            color: 0x1e9e6a, transparent: true, opacity: 0.0,
            side: THREE.DoubleSide, depthWrite: false,
        }),
    );
    wall.position.set(rw / 2, wallBotZ + wallH / 2, 0.004);
    wall.visible = false;
    scene.add(wall);

    // TALL_END lane — full-height band at the right end of the
    // base run. 24" wide × room_height × cabinet depth, capped at
    // room-height − toe-kick.
    const tallH = Math.max(rh - 3.5 * IN, 60 * IN);
    const tallW = 24 * IN;
    const tall = new THREE.Mesh(
        new THREE.BoxGeometry(tallW, tallH, baseD),
        new THREE.MeshBasicMaterial({
            color: 0xc89b5a, transparent: true, opacity: 0.0,
            depthWrite: false,
        }),
    );
    tall.position.set(rw - tallW / 2, 3.5 * IN + tallH / 2, baseD / 2);
    tall.visible = false;
    scene.add(tall);

    return { base, wall, tall };
}
