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
 * Room-depth drag: Z-axis counterpart of {@link resolveRoomWidthFromDrag},
 * mapping vertical pointer travel to depth. Same 55px≈1ft feel, 6" snap,
 * [12, 288]" clamp.
 *
 * SIGN NOTE: dragging the pointer DOWN (clientY increasing) grows depth.
 * The correct sign depends on the camera orientation of the active view;
 * if a live check shows the drag feels inverted, flip the sign of `dy`
 * here (that is the single knob — no other change needed).
 *
 * @param {number} clientY — current pointer Y
 * @param {number} dragY0  — pointer Y where drag started
 * @param {number} dragD0  — room depth at drag start (inches)
 * @returns {number} snapped, clamped new depth in inches
 */
export function resolveRoomDepthFromDrag(clientY, dragY0, dragD0) {
    const dy = clientY - dragY0;
    const nd = Math.max(12, Math.min(288, dragD0 + dy * (12 / 55)));
    return Math.round(nd / 6) * 6;
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
 * Width uses the ew-resize (horizontal) cursor; depth uses ns-resize
 * (vertical). An in-flight drag wins over any hover; width wins over
 * depth only in the impossible case both flags are set at once.
 *
 * @param {{ dragging: boolean, draggingDepth?: boolean, onHandle: boolean, onDepthHandle?: boolean, onCabinet: boolean }} state
 * @returns {string} CSS cursor value
 */
export function cursorForPointerState({ dragging, draggingDepth, onHandle, onDepthHandle, onCabinet }) {
    if (dragging) return "ew-resize";
    if (draggingDepth) return "ns-resize";
    if (onHandle) return "ew-resize";
    if (onDepthHandle) return "ns-resize";
    if (onCabinet) return "grab";
    return "default";
}
