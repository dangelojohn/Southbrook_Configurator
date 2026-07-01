/** @odoo-module **/
/**
 * Southbrook Kitchen 3D Configurator — pin-aware row packer.
 *
 * Rec D · Sprint 2d · Step 6 · closure extraction.
 *
 * Pack unpinned items into the free gaps between pinned items,
 * left-to-right. Any overflow extends past the rightmost pinned
 * item. When no item is pinned, behaviour reduces to the classic
 * "pack from x=0" cascade — bit-identical to the pre-2d output.
 *
 * Extracted verbatim from the closure inside
 * kitchen_configurator.js's `_recomputeLayoutFromItems`
 * (was line 696-727). Zero behaviour change.
 *
 * Mutates the passed items' `x_position_in` in place; no return value.
 */

const sortX = (a, b) => (a.x_position_in || 0) - (b.x_position_in || 0);

/**
 * @param {Array<{ x_position_in?: number, width_in?: number, pinned?: boolean }>} row
 */
export function packRow(row) {
    const pinned   = row.filter(it => it.pinned).sort(sortX);
    const unpinned = row.filter(it => !it.pinned);
    let cursor = 0;
    let pi = 0;
    for (const u of unpinned) {
        const w = u.width_in || 0;
        while (pi < pinned.length
               && (pinned[pi].x_position_in || 0) <= cursor) {
            cursor = Math.max(
                cursor,
                (pinned[pi].x_position_in || 0)
                    + (pinned[pi].width_in || 0),
            );
            pi++;
        }
        if (pi < pinned.length
            && (pinned[pi].x_position_in || 0) >= cursor + w) {
            u.x_position_in = cursor;
            cursor += w;
        } else if (pi < pinned.length) {
            cursor = (pinned[pi].x_position_in || 0)
                   + (pinned[pi].width_in || 0);
            pi++;
            u.x_position_in = cursor;
            cursor += w;
        } else {
            u.x_position_in = cursor;
            cursor += w;
        }
    }
}
