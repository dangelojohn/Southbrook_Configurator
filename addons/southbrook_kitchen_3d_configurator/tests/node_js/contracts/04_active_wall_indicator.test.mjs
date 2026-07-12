/**
 * PR1 contract — active-wall indicator. The count-strip's
 * `<strong t-esc="_wallLabel(state.activeWall)"/>` (kitchen_configurator.js
 * ~line 1845) must reflect `state.activeWall`, reading "None" until a
 * wall is picked. This renders the REAL parent template end-to-end
 * (only <KitchenCanvas> is mocked) and reads the actual DOM text —
 * stronger than asserting _wallLabel() in isolation (contract #1).
 */
import test from "node:test";
import assert from "node:assert/strict";
import { mountConfigurator } from "../harness/mount_configurator.mjs";
import { tick } from "../harness/tick.mjs";

function indicatorText(root) {
    const items = [...root.querySelectorAll(".o_sbk_count_item")];
    const el = items.find((n) => n.textContent.includes("Active Wall"));
    return el ? el.textContent.replace(/\s+/g, " ").trim() : null;
}

test("active-wall indicator reads 'None' before any wall is picked", async () => {
    const h = await mountConfigurator({});
    await tick();
    const text = indicatorText(h.root);
    assert.ok(text, "indicator element found in the real rendered DOM");
    assert.match(text, /Active Wall:\s*None/);
});

test("active-wall indicator reflects state.activeWall after a pick", async () => {
    const h = await mountConfigurator({});
    h.canvasProps().onWallSelect("right");
    await tick();
    const text = indicatorText(h.root);
    assert.match(text, /Active Wall:\s*Right/);
});
