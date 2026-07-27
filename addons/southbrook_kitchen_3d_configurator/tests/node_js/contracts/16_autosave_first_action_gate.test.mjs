/**
 * T7 (kitchen templates) contract — auto-save first-action gate + no
 * silent room growth.
 *
 * save_design is a full-replace writer: a programmatic refresh
 * (hydration echo, template instantiation, prop-driven recompute) that
 * reaches _queueAutoSave() before the rep touches ANYTHING would save
 * over the just-instantiated design. The gate: _queueAutoSave()
 * schedules nothing until the first genuine user mutation flips
 * _userActed (via _markUserAction()).
 *
 * Companion fix locked here too: _addCabinetFromProduct no longer
 * silently grows state.room.width_in when the run exceeds the room
 * (the spec's "54->60->84 growth" defect) — it warns instead.
 */
import test from "node:test";
import assert from "node:assert/strict";
import { mountConfigurator } from "../harness/mount_configurator.mjs";

const BASE_ITEM = {
    id: 911, layout_key: "g-1", cabinet_type: "base", product_name: "Base 24",
    width_in: 24, height_in: 34.5, depth_in: 24,
    x_position_in: 0, y_position_in: 0, z_position_in: 0, rotation_deg: 0,
    wall: "back", price: 500,
};
const CATALOG_PRODUCT = {
    product_id: 42, name: "B24 Base Cabinet", cabinet_type: "base",
    width_in: 24, height_in: 34.5, depth_in: 24, price: 180,
};

async function mountHydrated(roomWidth = 120) {
    return mountConfigurator({
        actionParams: { design_id: 910 },
        rpcRoutes: {
            "/southbrook_kitchen/configurator/load_design_lines": () => ({
                room: { width_in: roomWidth, depth_in: 96, height_in: 96 },
                design_name: "T7 gate test",
                lines: [BASE_ITEM, { ...BASE_ITEM, id: 912,
                                     layout_key: "g-2", x_position_in: 24 }],
            }),
        },
    });
}

test("_queueAutoSave() schedules nothing before the first user action", async (t) => {
    const h = await mountHydrated();
    const c = h.component;
    assert.equal(c._userActed, false, "gate starts closed");
    c._queueAutoSave();
    assert.equal(c._autoSaveTimer, null,
        "programmatic _queueAutoSave must not schedule before user acts");
    // A programmatic refresh doesn't open the gate either.
    c._recomputeLayoutFromItems();
    c._queueAutoSave();
    assert.equal(c._autoSaveTimer, null);
    t.after(() => { if (c._autoSaveTimer) clearTimeout(c._autoSaveTimer); });
});

test("first genuine user add opens the gate and schedules the auto-save", async (t) => {
    const h = await mountHydrated();
    const c = h.component;
    c._addCabinetFromProduct(CATALOG_PRODUCT);
    assert.equal(c._userActed, true, "user add flips the gate");
    assert.ok(c._autoSaveTimer, "auto-save is scheduled after a user add");
    t.after(() => { if (c._autoSaveTimer) clearTimeout(c._autoSaveTimer); });
});

test("_addCabinetFromProduct never silently grows the room", async (t) => {
    // 48" room with 2x24" bases already in it — the added 24" cabinet
    // overflows the run. Pre-fix this mutated room.width_in to
    // ceil(72/6)*6 = 72; the contract is: room untouched, warn instead.
    const h = await mountHydrated(48);
    const c = h.component;
    c._addCabinetFromProduct(CATALOG_PRODUCT);
    assert.equal(c.state.room.width_in, 48,
        "room width must NOT be silently grown to fit the run");
    t.after(() => { if (c._autoSaveTimer) clearTimeout(c._autoSaveTimer); });
});
