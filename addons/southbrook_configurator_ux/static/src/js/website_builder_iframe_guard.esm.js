/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { WebsiteBuilderClientAction } from "@website/client_actions/website_preview/website_builder_action";

/*
 * Southbrook website-builder iframe guard.
 *
 * Odoo 19's WebsiteBuilderClientAction assumes iframe.contentDocument is
 * readable as soon as the iframe load event fires. Immediately after website
 * asset/template upgrades, Chrome can emit that event while contentDocument is
 * still null (or while a redirect/security error document is being swapped in),
 * which raises "Cannot read properties of null (reading 'body')" before the
 * core method reaches its own redirect handling.
 */
patch(WebsiteBuilderClientAction.prototype, {
    onIframeLoad(ev) {
        const iframe = this.websiteContent?.el;
        if (!iframe?.contentWindow || !iframe.contentDocument?.body) {
            ev.stopImmediatePropagation?.();
            setTimeout(() => {
                if (this.websiteContent?.el?.contentDocument?.body) {
                    super.onIframeLoad(ev);
                }
            }, 0);
            return;
        }
        return super.onIframeLoad(ev);
    },
});
