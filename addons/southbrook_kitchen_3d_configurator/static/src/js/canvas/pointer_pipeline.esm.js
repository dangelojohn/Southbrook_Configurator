/** @odoo-module **/
/**
 * Southbrook Kitchen 3D Configurator — pointer pipeline.
 *
 * Rec D · Sprint 2d · Step 23 · fine-grained extraction.
 *
 * Small pure helpers pulled out of _onMouseDown / _onMouseMove /
 * _onMouseUp / _onMouseOver. Each excises a testable-in-isolation
 * piece (geometry math, threshold check, cursor decision table)
 * while leaving `this.T` / `this.state` mutations in the class
 * body — the coherence the ~2000-line class needs.
 *
 * The class-side handlers still own:
 *   - `this.T.dragging | movingItem | moveStartClient | ...` writes
 *   - `this.state.room.width_in` / `state.selected` writes
 *   - `_selectCabinet`, `_savePinnedPosition`, `_queueAutoSave`
 *   - `_recomputeLayoutFromItems`, `_buildScene`, `_refreshLayout`
 *   - `this.notification.add(...)`
 *   - `renderer.domElement.style.cursor` writes
 *   - `e.preventDefault()` / `e.stopPropagation()` (must not move
 *     these into pure helpers — the capture-phase stopPropagation
 *     is what gates OrbitControls vs cabinet-move)
 */

/**
 * The drag handle only tracks room width in views where the right
 * edge is visible and maps intuitively to width. Other views fall
 * through to cabinet selection.
 */
export function isHandleActiveView(viewName) {
    return viewName === "iso" || viewName === "top";
}

/**
 * Room-width drag: 55px screen ≈ 1ft world at typical zoom. Snap
 * to the 6" grid. Clamp [12, 288] inches (1 ft to 24 ft).
 *
 * @param {number} clientX — current pointer X
 * @param {number} dragX0  — pointer X where drag started
 * @param {number} dragW0  — room width at drag start (inches)
 * @returns {number} snapped, clamped new width in inches
 */
export function resolveRoomWidthFromDrag(clientX, dragX0, dragW0) {
    const dx = clientX - dragX0;
    const nw = Math.max(12, Math.min(288, dragW0 + dx * (12 / 55)));
    return Math.round(nw / 6) * 6;
}

/**
 * D15 — 5px cursor travel threshold before a mousedown+move counts
 * as a cabinet drag rather than a click+select. Prevents jittery
 * clicks from committing accidental moves.
 *
 * @param {{ x: number, y: number }} startClient
 * @param {{ clientX: number, clientY: number }} current
 * @param {number} threshold — pixels, default 5
 * @returns {boolean}
 */
export function isCabinetDragCommitted(startClient, current, threshold = 5) {
    const dx = current.clientX - startClient.x;
    const dy = current.clientY - startClient.y;
    return Math.hypot(dx, dy) >= threshold;
}

/**
 * Fillers + panels are server-placed (see _recomputeLayoutFromItems
 * comments); they are not user-pinnable per Stage 1 spec. Every
 * other cabinet type flips pinned=true on drag commit.
 */
export function isPinnable(cabinetType) {
    return !["filler", "panel"].includes(cabinetType);
}

/**
 * Cursor state table for _onMouseOver. The decision precedence:
 *   1. If any width drag is in flight → resize cursor
 *   2. Else if hovering the width-drag handle → resize cursor
 *   3. Else if hovering a cabinet → grab cursor
 *   4. Default
 *
 * Do NOT call from _onMouseMove — mid-drag the class body sets
 * "move" and expects _onMouseOver's early-return to preserve it.
 *
 * @param {{ dragging: boolean, onHandle: boolean, onCabinet: boolean }} state
 * @returns {string} CSS cursor value
 */
export function cursorForPointerState({ dragging, onHandle, onCabinet }) {
    if (dragging) return "ew-resize";
    if (onHandle) return "ew-resize";
    if (onCabinet) return "grab";
    return "default";
}
