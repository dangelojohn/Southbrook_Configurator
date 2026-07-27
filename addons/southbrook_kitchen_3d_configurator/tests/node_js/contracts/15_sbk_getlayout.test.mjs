/**
 * T7 (kitchen templates) contract — window.__sbk.getLayout().
 *
 * A read-only automation/diagnostics hook installed in onMounted:
 * returns a deep-copied snapshot of state.items with a FIXED 7-key
 * contract ({id, sku, wall, x_position_in, width_in, cabinet_type,
 * is_filler}). Never a mutation surface: writing to the returned
 * array/objects must not touch state.items.
 */
import test from "node:test";
import assert from "node:assert/strict";
import { mountConfigurator } from "../harness/mount_configurator.mjs";

const BASE_ITEM = {
    id: 901, layout_key: "b-1", cabinet_type: "base", product_name: "Base 24",
    default_code: "B24", width_in: 24, height_in: 34.5, depth_in: 24,
    x_position_in: 0, y_position_in: 0, z_position_in: 0, rotation_deg: 0,
    wall: "back", price: 500,
};
const FILLER_ITEM = {
    id: 902, layout_key: "f-1", cabinet_type: "filler", product_name: "FP3",
    default_code: "FP3", width_in: 3, height_in: 34.5, depth_in: 0.75,
    x_position_in: 24, y_position_in: 0, z_position_in: 0, rotation_deg: 0,
    wall: "back", price: 35,
};

const CONTRACT_KEYS = [
    "id", "sku", "wall", "x_position_in", "width_in",
    "cabinet_type", "is_filler",
];

async function mountHydrated() {
    return mountConfigurator({
        actionParams: { design_id: 900 },
        rpcRoutes: {
            "/southbrook_kitchen/configurator/load_design_lines": () => ({
                room: { width_in: 120, depth_in: 96, height_in: 96 },
                design_name: "T7 getLayout test",
                lines: [BASE_ITEM, FILLER_ITEM],
            }),
        },
    });
}

function sbk() {
    // harness registers jsdom's window as the global `window`
    return globalThis.window.__sbk;
}

test("__sbk.getLayout() exposes exactly the 7 contract keys per item", async () => {
    await mountHydrated();
    assert.ok(sbk(), "window.__sbk must exist after mount");
    assert.equal(typeof sbk().getLayout, "function");
    const layout = sbk().getLayout();
    assert.equal(layout.length, 2);
    for (const entry of layout) {
        assert.deepEqual(Object.keys(entry).sort(), CONTRACT_KEYS.slice().sort());
    }
    const filler = layout.find(e => e.cabinet_type === "filler");
    const base = layout.find(e => e.cabinet_type === "base");
    assert.equal(filler.is_filler, true);
    assert.equal(filler.sku, "FP3");
    assert.equal(base.is_filler, false);
    assert.equal(base.sku, "B24");
    assert.equal(base.wall, "back");
    assert.equal(base.width_in, 24);
});

test("__sbk.getLayout() is a snapshot — mutating it never touches state.items", async () => {
    const h = await mountHydrated();
    const layout = sbk().getLayout();
    layout[0].width_in = 999;
    layout[0].wall = "front";
    layout.push({ bogus: true });
    const items = h.component.state.items;
    assert.equal(items.length, 2, "state.items length untouched");
    assert.equal(items[0].width_in, 24, "state.items width untouched");
    assert.equal(items[0].wall, "back", "state.items wall untouched");
    // A fresh call reflects the REAL state, not the mutated snapshot.
    const again = sbk().getLayout();
    assert.equal(again.length, 2);
    assert.equal(again[0].width_in, 24);
});
