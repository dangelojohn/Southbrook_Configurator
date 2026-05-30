/** @odoo-module **/

/*
 * Extends the WebsiteSale Interaction's _updateRootProduct method to inject
 * the configurator's session id into the add-to-cart payload (rootProduct).
 *
 * 19.0 migration notes:
 * - In 17.0 this extended `publicWidget.registry.WebsiteSale` via .include().
 *   In 19.0 the WebsiteSale class was migrated off the legacy publicWidget
 *   framework to the new Interactions framework
 *   (`@web/public/interaction`), and the extension idiom is now `patch()`
 *   from `@web/core/utils/patch` against the class prototype.
 * - The form is now a native HTMLFormElement (was a jQuery object). Read
 *   via form.querySelector instead of $form.find().val().
 * - _updateRootProduct signature changed from ($form, productId) to (form);
 *   productId is read from form.querySelector inside the base method now.
 *
 * Behavior preserved: when a configurable product's storefront form
 * carries a hidden config_session_id input, its value is added to
 * this.rootProduct before WebsiteSale calls the cart service. The
 * downstream effect — the created sale.order.line referencing the
 * configured variant + session — is unchanged.
 */

import { patch } from "@web/core/utils/patch";
import { WebsiteSale } from "@website_sale/interactions/website_sale";

patch(WebsiteSale.prototype, {
    /**
     * @override
     * @param {HTMLFormElement} form
     */
    _updateRootProduct(form) {
        super._updateRootProduct(form);

        const configSessionIdEl = form.querySelector(
            'input[name="config_session_id"]'
        );
        if (configSessionIdEl?.value) {
            // Preserve the raw form-input string. OCA's downstream
            // `_cart_find_product_line` override checks
            // `config_session_id.isdigit()`, which requires a string.
            // The original 17.0 code path passed the value as-is from
            // `$form.find('input[name="config_session_id"]').val()` —
            // jQuery `.val()` always returned a string, so OCA's Python
            // side standardized on string-typed session ids. Don't
            // `parseInt()` here; let the Python side decide on numeric
            // coercion.
            this.rootProduct.config_session_id = configSessionIdEl.value;
        }
    },
});
