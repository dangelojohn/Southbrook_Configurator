/** @odoo-module **/
/* SPDX-License-Identifier: LGPL-3.0-only */
/*
 * Systray button → opens the Training Help dialog.
 *
 * Mounting point: the top-right systray, grouped with notifications.
 * Click → opens HelpPanelDialog (see help_panel.js).
 *
 * v19 OWL pattern: register a {Component} into category("systray").
 */
import {Component} from "@odoo/owl";
import {registry} from "@web/core/registry";
import {useService} from "@web/core/utils/hooks";
import {HelpPanelDialog} from "@southbrook_training_hub/help/help_panel";

export class HelpSystrayItem extends Component {
    static template = "southbrook_training_hub.HelpSystrayItem";
    static props = {};

    setup() {
        this.dialog = useService("dialog");
    }

    onClick() {
        this.dialog.add(HelpPanelDialog, {});
    }
}

registry.category("systray").add(
    "southbrook_training_hub.help",
    {Component: HelpSystrayItem},
    {sequence: 95},
);
