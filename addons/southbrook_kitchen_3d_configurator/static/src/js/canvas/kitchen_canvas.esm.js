/** @odoo-module **/
/**
 * Southbrook Kitchen 3D Configurator — reusable 3D canvas component.
 *
 * Rec D · Sprint 2d · Step 24 · component wrapper.
 *
 * KitchenCanvas owns the Three.js scene lifecycle (mount, build,
 * dispose) and the pointer + camera + zoom interactions. Consumers
 * — backend Kitchen Configurator, /kitchen-planner, portal Room
 * Layout — pass a canned {items, room, view, selected} snapshot
 * as props and get user gestures back as callback events. State
 * ownership stays with the parent (one-way reactive flow).
 *
 * Migration status: 24a skeleton — empty template registered so
 * the module id resolves. No mount/scene wiring yet; that lands
 * in 24b once the parent still owns the visible scene.
 */

import { Component, xml } from "@odoo/owl";

/**
 * @typedef {Object} KitchenCanvasProps
 * @property {Array}   items    — cabinet items to render
 * @property {Object}  room     — { width_in, depth_in, height_in }
 * @property {string}  view     — iso / top / front / left / right / persp
 * @property {Object?} selected — selected item or null
 * @property {Object?} draggedProduct — inventory item mid-drag or null
 * @property {boolean} dragHover      — drop-target hover state
 * @property {Function} onSelectItem
 * @property {Function} onMoveItem
 * @property {Function} onResizeRoom
 * @property {Function} onViewChange
 */

export class KitchenCanvas extends Component {
    static template = xml`
        <div t-ref="kitchenCanvas" class="o_sbk_kitchen_canvas">
            <!-- 24a skeleton: parent still owns the visible scene. -->
        </div>
    `;
    static props = {
        items:          { type: Array, optional: true },
        room:           { type: Object, optional: true },
        view:           { type: String, optional: true },
        selected:       { type: [Object, { value: null }], optional: true },
        draggedProduct: { type: [Object, { value: null }], optional: true },
        dragHover:      { type: Boolean, optional: true },
        onSelectItem:   { type: Function, optional: true },
        onMoveItem:     { type: Function, optional: true },
        onResizeRoom:   { type: Function, optional: true },
        onViewChange:   { type: Function, optional: true },
    };
    static defaultProps = {
        items: [],
        room: {},
        view: "iso",
        selected: null,
        draggedProduct: null,
        dragHover: false,
    };
}
