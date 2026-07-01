/** @odoo-module **/
/**
 * Southbrook Kitchen 3D Configurator — selection highlight.
 *
 * Rec D · Sprint 2d · Step 9 · pure-function extraction.
 *
 * Extracted verbatim from kitchen_configurator.js:1651-1665
 * (_highlightSelected). Zero behaviour change; the scene meshes
 * are still mutated in place — the caller passes the array and
 * the palette explicitly so the future <KitchenCanvas> can share
 * the same reset+highlight cycle.
 */

/**
 * Recolor cabinet meshes: reset every mesh flagged as `cab` to the
 * unselected color, then paint the matching item's meshes with the
 * selection color.
 *
 * @param {THREE.Mesh[]} cabObjs — all cabinet meshes in the current scene
 * @param {{ layout_key?: string } | null} item — selected item or null
 * @param {{ cab: number, sel: number }} palette — hex colors
 */
export function highlightSelected(cabObjs, item, palette) {
    cabObjs.forEach(m => {
        if (m.userData?.cab) m.material.color.setHex(palette.cab);
    });
    if (!item) return;
    cabObjs.forEach(m => {
        if (m.userData?.cab &&
            m.userData.item?.layout_key === item.layout_key) {
            m.material.color.setHex(palette.sel);
        }
    });
}
