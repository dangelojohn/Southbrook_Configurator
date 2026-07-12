/**
 * PR1 contract — wall selection.
 *   1. <KitchenCanvas> is invoked with activeWall="state.activeWall" and
 *      onWallSelect="(w) => this._onWallSelect(w)" (kitchen_configurator.js
 *      ~line 1811-1812).
 *   2. `_onWallSelect(wall)` sets `state.activeWall` (real method, called
 *      through the captured prop — not re-implemented here).
 *   3. `_wallLabel` maps wall codes to labels, "None" for anything else
 *      (including null/undefined — the pre-selection state).
 */
import test from "node:test";
import assert from "node:assert/strict";
import { mountConfigurator } from "../harness/mount_configurator.mjs";

test("KitchenCanvas is invoked with activeWall + onWallSelect props", async () => {
    const h = await mountConfigurator({});
    const props = h.canvasProps();
    assert.equal(props.activeWall, null, "initial activeWall is null (no wall picked yet)");
    assert.equal(typeof props.onWallSelect, "function");
});

test("_onWallSelect(wall), invoked via the real onWallSelect prop, sets state.activeWall", async () => {
    const h = await mountConfigurator({});
    h.canvasProps().onWallSelect("left");
    assert.equal(h.component.state.activeWall, "left");

    h.canvasProps().onWallSelect("back");
    assert.equal(h.component.state.activeWall, "back");
});

test("_wallLabel maps every known code and falls back to None", async () => {
    const h = await mountConfigurator({});
    const c = h.component;
    assert.equal(c._wallLabel("back"), "Back");
    assert.equal(c._wallLabel("left"), "Left");
    assert.equal(c._wallLabel("right"), "Right");
    assert.equal(c._wallLabel("front"), "Front");
    assert.equal(c._wallLabel(null), "None");
    assert.equal(c._wallLabel(undefined), "None");
    assert.equal(c._wallLabel("bogus"), "None");
});
