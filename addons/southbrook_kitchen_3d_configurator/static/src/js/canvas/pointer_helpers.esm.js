/** @odoo-module **/
/**
 * Southbrook Kitchen 3D Configurator — pointer/event helpers.
 *
 * Rec D · Sprint 2d · Step 3 · pure-function extraction.
 *
 * Extracted from kitchen_configurator.js:1732-1739. The pre-2d
 * method read `this.canvas3dRef.el` for the bounding rect; the
 * extracted function takes the DOM element as an explicit arg so
 * the future <KitchenCanvas> component can pass its own canvas
 * element without needing to inherit or bind the class.
 */

/**
 * Convert a pointer event's screen coordinates into normalized-
 * device-coordinates ({x, y}) relative to the given canvas DOM
 * element. Both x and y are in [-1, 1]. Returns {x:0, y:0} when
 * the canvas element is null (e.g. before OWL has mounted).
 *
 * @param {MouseEvent|PointerEvent} event
 * @param {HTMLElement|null} canvasEl
 * @returns {{x: number, y: number}}
 */
export function ndcFromEvent(event, canvasEl) {
    const rect = canvasEl?.getBoundingClientRect();
    if (!rect) return { x: 0, y: 0 };
    return {
        x:  ((event.clientX - rect.left) / rect.width)  * 2 - 1,
        y: -((event.clientY - rect.top)  / rect.height) * 2 + 1,
    };
}
