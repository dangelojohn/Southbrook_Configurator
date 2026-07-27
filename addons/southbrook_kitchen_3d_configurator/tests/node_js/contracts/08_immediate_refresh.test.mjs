/**
 * PR4.1 contract — immediate refresh on the AUTO-SAVE path.
 *
 * PR4 taught `_saveDesign()` to apply the server's `placed` array
 * (engine-computed poses for non-back-wall cabinets, returned by
 * /southbrook_kitchen/configurator/save — controllers/main.py
 * save_design) onto the matching `state.items`. But a drag-add does
 * NOT call `_saveDesign()` directly — it calls the debounced
 * `_queueAutoSave()`, which (after its 3s timer) calls `_autoSave()`.
 * `_autoSave()` never applied `result.placed`, so a cabinet dropped on
 * a non-back wall persisted correctly server-side (verified in DB:
 * correct wall + engine pose) but stayed drawn on the back wall
 * client-side until a reload. That was the release blocker.
 *
 * PR4.1 extracts the apply logic into a single shared method,
 * `_applyServerPlacements(placed)`, and calls it from BOTH
 * `_saveDesign()` and `_autoSave()` so the two save paths can no
 * longer drift. This contract locks that: it proves the AUTO-SAVE
 * path applies the engine pose to state.items and yields a fresh
 * `state.items` array reference (so <KitchenCanvas>'s prop-change
 * detection would re-render) — no reload — and it guards the
 * `_saveDesign` refactor by re-asserting its behaviour is unchanged.
 *
 * Per docs/2026-07-12-renderer-contract.md: the client only APPLIES
 * fields the engine computed server-side; nothing here computes a
 * coordinate itself.
 */
import test from "node:test";
import assert from "node:assert/strict";
import { mountConfigurator } from "../harness/mount_configurator.mjs";

const LEFT_ITEM = {
    id: 801, layout_key: "left-1", cabinet_type: "base", product_name: "Base 24",
    width_in: 24, height_in: 34.5, depth_in: 24,
    // Deliberately a garbage BACK-wall-style x (the bug this PR fixes) —
    // wall="left" cabinets are never correctly placed by the client.
    x_position_in: 999, y_position_in: 0, z_position_in: 0, rotation_deg: 0,
    wall: "left", price: 500,
};
const BACK_ITEM = {
    id: 802, layout_key: "back-1", cabinet_type: "base", product_name: "Base 24 Back",
    width_in: 24, height_in: 34.5, depth_in: 24,
    x_position_in: 50, y_position_in: 0, z_position_in: 0, rotation_deg: 0,
    wall: "back", price: 500,
};

const ENGINE_PLACED = [{
    layout_key:     "left-1",
    x_position_in:  0,
    y_position_in:  0,
    z_position_in:  12,
    rotation_deg:   90,
}];

async function mountHydrated(extraRoutes = {}) {
    return mountConfigurator({
        actionParams: { design_id: 800 },
        rpcRoutes: {
            "/southbrook_kitchen/configurator/load_design_lines": () => ({
                room: { width_in: 120, depth_in: 96, height_in: 96 },
                design_name: "PR4.1 immediate-refresh test",
                lines: [LEFT_ITEM, BACK_ITEM],
            }),
            ...extraRoutes,
        },
    });
}

function itemByKey(items, key) {
    return items.find(it => it.layout_key === key);
}

test("_autoSave() applies the server's `placed` engine pose onto state.items (the PR4.1 fix)", async () => {
    const h = await mountHydrated({
        "/southbrook_kitchen/configurator/save": () => ({
            id: 800,
            name: "PR4.1 immediate-refresh test",
            placed: ENGINE_PLACED,
        }),
    });

    const itemsBefore = h.component.state.items;
    const leftBefore = itemByKey(itemsBefore, "left-1");
    // Sanity: still the garbage back-wall-style pose pre-fix.
    assert.equal(leftBefore.x_position_in, 999);

    // Call _autoSave() directly — the debounced path a drag-add takes
    // via _queueAutoSave() — without waiting on the 3000ms timer.
    await h.component._autoSave();

    const itemsAfter = h.component.state.items;
    const leftAfter = itemByKey(itemsAfter, "left-1");

    // (a) the item's pose fields now equal the returned engine pose.
    assert.equal(leftAfter.x_position_in, 0);
    assert.equal(leftAfter.y_position_in, 0);
    assert.equal(leftAfter.z_position_in, 12);
    assert.equal(leftAfter.rotation_deg, 90);

    // (b) state.items is a new array reference vs. before — proof
    // _recomputeLayoutFromItems() ran, which is what forces
    // <KitchenCanvas>'s prop-change detection to re-render without a
    // reload.
    assert.notEqual(itemsAfter, itemsBefore);

    // The back-wall item was not in `placed` — its stored pose is
    // unaffected. C2/C5 (2026-07-26): a multi-wall design skips
    // packRow for every row (server-authoritative geometry), so the
    // fixture's stored x=50 survives instead of packing to 0.
    const back = itemByKey(itemsAfter, "back-1");
    assert.equal(back.x_position_in, 50);
    assert.equal(back.wall, "back");
});

test("_autoSave() also sets designId/name/lastAutoSaveAt as before (guards existing auto-save contract)", async () => {
    const h = await mountHydrated({
        "/southbrook_kitchen/configurator/save": () => ({
            id: 800,
            name: "PR4.1 immediate-refresh test",
            placed: ENGINE_PLACED,
        }),
    });

    await h.component._autoSave();

    assert.equal(h.component.state.designId, 800);
    assert.equal(h.component.state.designName, "PR4.1 immediate-refresh test");
    assert.ok(h.component.state.lastAutoSaveAt);
});

test("_saveDesign() still applies `placed` too (guards the _applyServerPlacements extraction)", async () => {
    const h = await mountHydrated({
        "/southbrook_kitchen/configurator/save": () => ({
            id: 800,
            name: "PR4.1 immediate-refresh test",
            placed: ENGINE_PLACED,
        }),
    });

    const itemsBefore = h.component.state.items;

    await h.component._saveDesign();

    const itemsAfter = h.component.state.items;
    const left = itemByKey(itemsAfter, "left-1");

    assert.equal(left.x_position_in, 0);
    assert.equal(left.y_position_in, 0);
    assert.equal(left.z_position_in, 12);
    assert.equal(left.rotation_deg, 90);
    assert.notEqual(itemsAfter, itemsBefore);
});
