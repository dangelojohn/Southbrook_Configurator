/**
 * Contract — the depth (front-wall) room puller must be wired parent-side.
 *
 * Regression guard for the "left/front puller does nothing while the
 * right/width puller works" defect (2026-07-27). The child
 * <KitchenCanvas> was always fully wired for BOTH handles: the depth pin
 * enters draggingDepth and fires the guarded
 * `this.props.onResizeRoomDepth(nd, inFlight)` on move and on release,
 * symmetric with `onResizeRoom` for width. The parent, however, bound
 * only onResizeRoom and defined only _onCanvasResize — so
 * props.onResizeRoomDepth was undefined, the child's guard skipped the
 * call, state.room.depth_in never updated, and no layout regen ran.
 *
 * Locks two things, in lockstep with the width path forever:
 *   1. the template binds onResizeRoomDepth on <KitchenCanvas>;
 *   2. _onCanvasResizeDepth mirrors _onCanvasResize on the depth axis
 *      (live write in-flight; regen + auto-save only on commit).
 */
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import { mountConfigurator } from "../harness/mount_configurator.mjs";

const __dirname = dirname(fileURLToPath(import.meta.url));
const SRC = readFileSync(resolve(
    __dirname, "../../../static/src/js/kitchen_configurator.js"), "utf8");

test("template binds onResizeRoomDepth on <KitchenCanvas>, symmetric with width", () => {
    // Anchor on the width binding itself and take its enclosing element:
    // the first bare "<KitchenCanvas" in the file is inside a COMMENT, so
    // anchoring there would slice 90KB of source instead of the template.
    const bindAt = SRC.indexOf("onResizeRoom=");
    assert.notEqual(bindAt, -1, "sanity: width binding must exist");
    const el = SRC.slice(
        SRC.lastIndexOf("<KitchenCanvas", bindAt),
        SRC.indexOf("/>", bindAt) + 2,
    );
    assert.ok(el.length > 2 && el.length < 4000,
        "could not isolate the <KitchenCanvas> template element");
    assert.match(el, /onResizeRoom=/, "sanity: width binding must exist");
    assert.match(
        el,
        /onResizeRoomDepth\s*=\s*"\(nd,\s*f\)\s*=>\s*this\._onCanvasResizeDepth\(nd,\s*f\)"/,
        "depth binding must delegate to _onCanvasResizeDepth on the same element",
    );
});

async function mountWithSpies() {
    const h = await mountConfigurator({});
    const calls = { refresh: 0, autoSave: 0 };
    h.component._refreshLayout = () => {
        calls.refresh += 1;
        return Promise.resolve();
    };
    h.component._queueAutoSave = () => { calls.autoSave += 1; };
    return { h, calls };
}

test("_onCanvasResizeDepth exists on the mounted component", async () => {
    const h = await mountConfigurator({});
    assert.equal(typeof h.component._onCanvasResizeDepth, "function");
});

test("commit (inFlight=false) writes depth, regenerates layout, auto-saves", async () => {
    const { h, calls } = await mountWithSpies();
    h.component._onCanvasResizeDepth(120, false);
    assert.equal(h.component.state.room.depth_in, 120,
        "depth_in must be written");
    await Promise.resolve();
    await Promise.resolve();
    assert.equal(calls.refresh, 1, "_refreshLayout must run once on commit");
    assert.equal(calls.autoSave, 1, "_queueAutoSave must run once on commit");
});

test("in-flight (inFlight=true) writes depth live but does NOT regen/save", async () => {
    const { h, calls } = await mountWithSpies();
    h.component._onCanvasResizeDepth(48, true);
    assert.equal(h.component.state.room.depth_in, 48,
        "depth must track the pointer live");
    await Promise.resolve();
    assert.equal(calls.refresh, 0, "no layout regen mid-drag");
    assert.equal(calls.autoSave, 0, "no auto-save mid-drag");
});

test("depth handler is axis-symmetric with the width handler", async () => {
    const { h } = await mountWithSpies();
    const w0 = h.component.state.room.width_in;
    h.component._onCanvasResizeDepth(200, true);
    assert.equal(h.component.state.room.depth_in, 200);
    assert.equal(h.component.state.room.width_in, w0,
        "depth path must not touch width");

    const { h: h2 } = await mountWithSpies();
    const d0 = h2.component.state.room.depth_in;
    h2.component._onCanvasResize(200, true);
    assert.equal(h2.component.state.room.width_in, 200);
    assert.equal(h2.component.state.room.depth_in, d0,
        "width path must not touch depth");
});

// ── 2026-07-27 (user decision) — pullers regenerate on SAVED designs too ──
// The room-resize family passes { force: true } through _refreshLayout's
// hydration guard: resizing a reopened design regenerates (replacing the
// saved arrangement) and drops hydration semantics on success.

test("puller commit passes force:true to _refreshLayout", async () => {
    const h = await mountConfigurator({});
    const seen = [];
    h.component._refreshLayout = (opts) => {
        seen.push(opts);
        return Promise.resolve();
    };
    h.component._queueAutoSave = () => {};
    h.component._onCanvasResizeDepth(120, false);
    h.component._onCanvasResize(140, false);
    await Promise.resolve();
    assert.equal(seen.length, 2);
    assert.ok(seen.every(o => o && o.force === true),
        "both pullers must pierce the hydration guard with force:true");
});

test("forced regen on a hydrated design regenerates and drops hydration", async () => {
    let layoutCalls = 0;
    const h = await mountConfigurator({
        actionParams: { design_id: 4242 },
        rpcRoutes: {
            "/southbrook_kitchen/configurator/load_design_lines": () => ({
                room: { width_in: 120, depth_in: 96, height_in: 96 },
                design_name: "saved design",
                lines: [{
                    id: 1, product_id: 1, layout_key: "b-1",
                    product_name: "Base 24", cabinet_type: "base",
                    width_in: 24, height_in: 34.5, depth_in: 24,
                    x_position_in: 0, y_position_in: 0, z_position_in: 0,
                    rotation_deg: 0, wall: "back", price: 100,
                }],
            }),
            "/southbrook_kitchen/configurator/layout": () => {
                layoutCalls += 1;
                return { items: [], summary: {}, warnings: [] };
            },
        },
    });
    // Sanity: hydration succeeded and the guard is armed.
    assert.equal(h.component._hydratedFromDesign, true,
        "fixture must start hydrated");
    h.component._queueAutoSave = () => {};

    h.component._onCanvasResizeDepth(72, false);
    // _refreshLayout awaits the /layout rpc; flush microtasks.
    await new Promise((r) => setTimeout(r, 0));
    assert.equal(layoutCalls, 1,
        "puller commit on a hydrated design must hit /layout (regenerate)");
    assert.equal(h.component._hydratedFromDesign, false,
        "successful forced regen must drop hydration semantics");
    assert.equal(h.component.state.hydratedFromDesign, false,
        "reactive mirror must drop too (re-enables F12 controls)");
});
