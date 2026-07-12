/**
 * <KitchenCanvas> mock — the one Three.js/WebGL/DOM-canvas boundary the
 * PR3a brief calls out to mock ("mock only the canvas's THREE/scene/RPC
 * boundaries, not the logic under test"). Captures every prop the real
 * parent (SouthbrookKitchenConfigurator) passes it — including the four
 * callback props (onWallSelect/onSelectItem/onMoveItem/onResizeRoom/
 * onViewChange/onReady) — into `canvasMockCalls.lastProps` so a test can
 * invoke `canvasMockCalls.lastProps.onWallSelect("left")` to simulate a
 * canvas-originated event and assert it round-trips into the parent's
 * OWL state, without ever touching Three.js or a WebGL context.
 *
 * The loader (harness/loader.mjs) redirects the bare specifier
 * "@southbrook_kitchen_3d_configurator/js/canvas/kitchen_canvas.esm" to
 * THIS file for every test that imports the real
 * kitchen_configurator.js's module graph. Contracts #3/#6 (renderer
 * coordinate math + golden snapshot) import the REAL
 * kitchen_canvas.esm.js by relative path instead, bypassing this mock
 * entirely — see contracts/03_renderer_coords.test.mjs.
 */
import { Component, xml } from "@odoo/owl";

export const canvasMockCalls = {
    lastProps: null,
    mountCount: 0,
};

export class KitchenCanvas extends Component {
    static template = xml`<div class="o_sbk_canvas_mock" t-att-data-active-wall="props.activeWall"/>`;

    setup() {
        canvasMockCalls.lastProps = this.props;
        canvasMockCalls.mountCount++;
    }
}
