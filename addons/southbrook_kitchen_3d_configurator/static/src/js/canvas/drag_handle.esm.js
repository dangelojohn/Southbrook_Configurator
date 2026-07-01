/** @odoo-module **/
/**
 * Southbrook Kitchen 3D Configurator — room-width drag handle.
 *
 * Rec D · Sprint 2d · Step 12 · closure-body extraction.
 *
 * Builds the ●-shaped drag handle + its two flanking arrow cones
 * that let the user resize the room's width by dragging on the
 * right wall. Extracted from kitchen_configurator.js:1546-1573
 * verbatim. The caller assigns `handleMesh` + `arrowMeshes` on its
 * own state object (the class T bag today; the future <KitchenCanvas>
 * component tomorrow).
 */

/**
 * @param {typeof THREE} THREE
 * @param {THREE.Scene} scene
 * @param {{ drag: number, arrow: number }} palette
 * @param {number} rw — room width in scene units
 * @param {number} rd — room depth in scene units
 * @returns {{ handleMesh: THREE.Mesh, arrowMeshes: THREE.Mesh[] }}
 */
export function buildDragHandle(THREE, scene, palette, rw, rd) {
    // Drag handle — PBR sphere with a self-emissive glow so it
    // pops against any lighting profile.
    const handleMesh = new THREE.Mesh(
        new THREE.SphereGeometry(0.18, 20, 20),
        new THREE.MeshStandardMaterial({
            color: palette.drag, emissive: 0x001166, emissiveIntensity: 0.4,
            roughness: 0.3, metalness: 0.1,
        }),
    );
    handleMesh.position.set(rw + 0.08, 0.18, rd / 2);
    handleMesh.userData = { isDragHandle: true };
    scene.add(handleMesh);

    // Arrow cones flanking the handle.
    const arrowMeshes = [];
    for (const { offset, rotZ } of [
        { offset: -0.42, rotZ:  Math.PI / 2 },
        { offset:  0.42, rotZ: -Math.PI / 2 },
    ]) {
        const arr = new THREE.Mesh(
            new THREE.ConeGeometry(0.08, 0.22, 8),
            new THREE.MeshStandardMaterial({
                color: palette.arrow, roughness: 0.4, metalness: 0.1,
            }),
        );
        arr.rotation.z = rotZ;
        arr.position.set(rw + offset, 0.18, rd / 2);
        scene.add(arr);
        arrowMeshes.push(arr);
    }

    return { handleMesh, arrowMeshes };
}
