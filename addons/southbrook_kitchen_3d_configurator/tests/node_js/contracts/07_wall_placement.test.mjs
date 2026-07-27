/**
 * PR4 contract — wall-aware placement (client side).
 *
 * The backend now routes non-back-wall configurator lines through the
 * pure `kitchen_layout_engine` on save (southbrook.kitchen.design.
 * _place_lines_on_wall) and returns the engine-corrected poses as
 * `result.placed` from /southbrook_kitchen/configurator/save
 * (controllers/main.py save_design). This contract covers the CLIENT
 * side of that: `_saveDesign()` must apply those returned poses onto
 * the matching `state.items` (by layout_key) so a left/right/front-wall
 * cabinet visibly jumps onto its wall immediately, without a reload —
 * and the legacy single-axis `packRow` (driven by
 * `_recomputeLayoutFromItems`) must never re-pack a non-back-wall
 * item's geometry back onto the X axis, whether that recompute runs
 * during hydration or right after a save applies the engine's pose.
 *
 * Per docs/2026-07-12-renderer-contract.md: the client only APPLIES
 * the fields the engine computed server-side — no wall math is added
 * to the client here, and nothing in this contract computes a
 * coordinate; it only asserts values already returned by the (mocked)
 * server are copied onto state.items untouched, and are never
 * overwritten by the legacy back-wall-only packer.
 */
import test from "node:test";
import assert from "node:assert/strict";
import { mountConfigurator } from "../harness/mount_configurator.mjs";

const LEFT_ITEM = {
    id: 601, layout_key: "left-1", cabinet_type: "base", product_name: "Base 24",
    width_in: 24, height_in: 34.5, depth_in: 24,
    // Deliberately a garbage BACK-wall-style x (the bug this PR fixes) —
    // wall="left" cabinets are never correctly placed by the client.
    x_position_in: 999, y_position_in: 0, z_position_in: 0, rotation_deg: 0,
    wall: "left", price: 500,
};
const BACK_ITEM = {
    id: 602, layout_key: "back-1", cabinet_type: "base", product_name: "Base 24 Back",
    width_in: 24, height_in: 34.5, depth_in: 24,
    // Deliberately NOT already packed to 0 — packRow must still fix
    // this up for the back wall (legacy behaviour preserved).
    x_position_in: 50, y_position_in: 0, z_position_in: 0, rotation_deg: 0,
    wall: "back", price: 500,
};

async function mountHydrated(extraRoutes = {}) {
    return mountConfigurator({
        actionParams: { design_id: 700 },
        rpcRoutes: {
            "/southbrook_kitchen/configurator/load_design_lines": () => ({
                room: { width_in: 120, depth_in: 96, height_in: 96 },
                design_name: "PR4 wall-placement test",
                lines: [LEFT_ITEM, BACK_ITEM],
            }),
            ...extraRoutes,
        },
    });
}

function itemByKey(items, key) {
    return items.find(it => it.layout_key === key);
}

test("packRow (via _recomputeLayoutFromItems on hydrate) leaves a non-back-wall item's pose untouched", async () => {
    const h = await mountHydrated();
    const left = itemByKey(h.component.state.items, "left-1");
    const back = itemByKey(h.component.state.items, "back-1");

    // The left-wall item's garbage back-wall x must survive hydration's
    // _recomputeLayoutFromItems() call unchanged — packRow must not
    // treat it as a back-wall run member.
    assert.equal(left.x_position_in, 999);
    assert.equal(left.wall, "left");

    // C2/C5 (2026-07-26) — this design is MULTI-WALL (it has a left
    // item), so geometry is server-owned end-to-end and packRow is
    // skipped for EVERY row, back wall included: repacking the back run
    // from x=0 client-side would shove it into the engine's reserved
    // corner cell. The stored x therefore survives untouched. (A
    // single-back-wall design still packs exactly as before — locked
    // by the other contracts in this suite.)
    assert.equal(back.x_position_in, 50);
});

test("_saveDesign applies the server's `placed` poses onto matching state.items by layout_key", async () => {
    const h = await mountHydrated({
        "/southbrook_kitchen/configurator/save": () => ({
            id: 700,
            name: "PR4 wall-placement test",
            placed: [{
                layout_key:     "left-1",
                x_position_in:  0,
                y_position_in:  0,
                z_position_in:  12,
                rotation_deg:   90,
            }],
        }),
    });

    await h.component._saveDesign();

    const left = itemByKey(h.component.state.items, "left-1");
    assert.equal(left.x_position_in, 0);
    assert.equal(left.y_position_in, 0);
    assert.equal(left.z_position_in, 12);
    assert.equal(left.rotation_deg, 90);

    // The back-wall item was not in `placed` — its stored pose must be
    // unaffected. C2/C5 (2026-07-26): the design is multi-wall, so the
    // hydrate-time recompute no longer repacks the back row either
    // (server-authoritative mode) — the fixture's stored x=50 survives.
    const back = itemByKey(h.component.state.items, "back-1");
    assert.equal(back.x_position_in, 50);
    assert.equal(back.wall, "back");
});

test("the post-save recompute does not let packRow re-pack the newly-applied wall pose", async () => {
    // Two LEFT-wall items: if packRow ever ran over them (bug), it
    // would sort by x_position_in and force-pack them onto the X axis
    // starting at 0/width — clobbering the just-applied z-based poses.
    const leftA = { ...LEFT_ITEM, id: 611, layout_key: "left-a" };
    const leftB = { ...LEFT_ITEM, id: 612, layout_key: "left-b", x_position_in: 500 };
    const h = await mountConfigurator({
        actionParams: { design_id: 701 },
        rpcRoutes: {
            "/southbrook_kitchen/configurator/load_design_lines": () => ({
                lines: [leftA, leftB],
            }),
            "/southbrook_kitchen/configurator/save": () => ({
                id: 701,
                name: "PR4 wall-placement multi test",
                placed: [
                    { layout_key: "left-a", x_position_in: 0, y_position_in: 0, z_position_in: 12, rotation_deg: 90 },
                    { layout_key: "left-b", x_position_in: 0, y_position_in: 0, z_position_in: 36, rotation_deg: 90 },
                ],
            }),
        },
    });

    await h.component._saveDesign();

    const a = itemByKey(h.component.state.items, "left-a");
    const b = itemByKey(h.component.state.items, "left-b");
    // Exactly the engine's along-the-wall (z) values — NOT re-packed
    // onto x by packRow (which would have written x=0/24 and left z
    // alone, or otherwise disturbed these).
    assert.equal(a.z_position_in, 12);
    assert.equal(a.x_position_in, 0);
    assert.equal(b.z_position_in, 36);
    assert.equal(b.x_position_in, 0);
});

test("_saveDesign with no `placed` key in the response leaves every item's pose untouched", async () => {
    const h = await mountHydrated({
        "/southbrook_kitchen/configurator/save": () => ({ id: 700, name: "No placed key" }),
    });
    const beforeLeft = { ...itemByKey(h.component.state.items, "left-1") };

    await h.component._saveDesign();

    const left = itemByKey(h.component.state.items, "left-1");
    assert.equal(left.x_position_in, beforeLeft.x_position_in);
    assert.equal(left.z_position_in, beforeLeft.z_position_in);
    assert.equal(left.rotation_deg, beforeLeft.rotation_deg);
});
