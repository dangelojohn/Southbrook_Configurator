import logging

from odoo import http, models
from odoo.exceptions import UserError, ValidationError
from odoo.http import request, route
from odoo.tools.safe_eval import safe_eval

from odoo.addons.website_sale.controllers.main import WebsiteSale

# 19.0: website_sale_product_configurator was absorbed into website_sale;
# the controller class now lives there.
from odoo.addons.website_sale.controllers.product_configurator import (
    WebsiteSaleProductConfiguratorController,
)

_logger = logging.getLogger(__name__)


class CustomWebsiteSaleProductConfigurator(WebsiteSaleProductConfiguratorController):
    @route()
    def show_advanced_configurator(
        self,
        product_id,
        variant_values,
        add_qty=1,
        force_dialog=False,
        **kw,
    ):
        """Inherit: skips showing the advanced product configurator modal for
        a product.

        Note (19.0): the 17.0 ``show_advanced_configurator`` endpoint was
        replaced by ``website_sale_should_show_product_configurator`` —
        this override is preserved for any code path that still reaches
        the legacy entry, but the active 19.0 suppression happens in
        ``website_sale_should_show_product_configurator`` below.
        """
        product = request.env["product.product"].browse(int(product_id))
        if product.config_ok:
            return False
        return super().show_advanced_configurator(
            product_id, variant_values, add_qty=add_qty, force_dialog=force_dialog, **kw
        )

    @route()
    def website_sale_should_show_product_configurator(
        self, product_template_id, ptav_ids, is_product_configured
    ):
        """Suppress Odoo 19.0's variant-picker modal for configurable
        templates.

        Surfaced by the W2+W5 manual acceptance walk per spec §4.3.

        For ``config_ok`` templates, the OCA wizard already resolves the
        full variant + session before Add to Cart is ever reached — the
        variant-picker modal is structurally redundant. Worse, the modal's
        ``get_values`` payload tries to read auxiliary "option-products"
        (the price-bearing aux ``product.product`` rows OCA attaches to
        attribute values for extra-cost mechanics), which are blocked by
        the configurator's record rule for public users. Result: an
        ``OwlError → RPC_ERROR`` on Add to Cart that never even reaches
        the patched ``_updateRootProduct``, so the W5 cart-coupling path
        appears broken when it isn't.

        Returning ``False`` here mirrors the design intent of the
        17.0-era ``show_advanced_configurator`` override (above) against
        the new 19.0 surface: the wizard supersedes the picker for these
        templates. ``sudo()`` is used because the public user can't read
        ``config_ok``; the field itself isn't sensitive.
        """
        product_template = (
            request.env["product.template"].sudo().browse(product_template_id)
        )
        if product_template.config_ok:
            return False
        return super().website_sale_should_show_product_configurator(
            product_template_id, ptav_ids, is_product_configured
        )


def get_pricelist():
    sale_order = request.env.context.get("sale_order")
    if sale_order:
        pricelist = sale_order.pricelist_id
    else:
        partner = request.env.user.partner_id
        pricelist = partner.property_product_pricelist
    return pricelist


error_page = "/website_product_configurator/error_page/"


class ProductConfigWebsiteSale(WebsiteSale):
    def get_config_session(self, product_tmpl_id):
        # JSON-key-stringification note: ``request.session`` is JSON-
        # serialized by Odoo's session middleware. Python int dict keys
        # round-trip to strings (``{49: 58}`` → ``{"49": 58}``), so the
        # lookup MUST use ``str(product_tmpl_id.id)`` to match. The
        # original OCA code coerced the VALUE side correctly
        # (``int(cfg_session_id)`` below) but missed the KEY side, so
        # ``dict.get(product_tmpl_id.id)`` always returned None for
        # public users — and combined with
        # ``create_get_session(force_create=is_public_user=True)``,
        # every page GET created a fresh session. Invisible in the
        # normal wizard flow (JS form carries config_session_id in
        # POSTs, which the controller uses directly), but exposed in
        # the reconfigure GET→GET hop where the dict is the only
        # carrier of the session linkage.
        cfg_session_obj = request.env["product.config.session"]
        cfg_session = False
        product_config_sessions = request.session.get("product_config_session", {})
        is_public_user = request.env.user.has_group("base.group_public")
        cfg_session_id = product_config_sessions.get(str(product_tmpl_id.id))
        if cfg_session_id:
            cfg_session = cfg_session_obj.search(
                [("id", "=", int(cfg_session_id))], limit=1
            )

        # Retrieve an active configuration session or create a new one.
        if not cfg_session or not cfg_session.exists():
            cfg_session = cfg_session_obj.sudo().create_get_session(
                product_tmpl_id.id,
                force_create=is_public_user,
                user_id=request.env.user.id,
            )
            product_config_sessions = {str(product_tmpl_id.id): cfg_session.id}
            request.session["product_config_session"] = product_config_sessions

        if cfg_session.user_id.has_group("base.group_public") and not is_public_user:
            cfg_session.user_id = request.env.user
        return cfg_session

    @http.route()
    def product(self, product, category="", search="", **kwargs):
        # Use parent workflow for regular products
        if not product.config_ok or not product.attribute_line_ids:
            return super().product(product, category=category, search=search, **kwargs)
        try:
            cfg_session = self.get_config_session(product_tmpl_id=product)
        except Exception:
            return request.redirect(error_page)

        # Set config-step in config session when it creates from wizard
        # because select state not exist on website
        if not cfg_session.config_step:
            cfg_session.config_step = "select"
            res = self.set_config_next_step(cfg_session)
            if res.get("error", False):
                return request.redirect(error_page)
        # Render the configuration template based on the configuration session
        config_form = self.render_form(
            cfg_session, product=product, category=category, search=search, **kwargs
        )

        return config_form

    def _prepare_product_values(self, product, category, **kwargs):
        """Inherit: sudo the product argument for config_ok templates so
        the chain into core's ``_prepare_product_values`` and downstream
        ``product._get_combination_info()`` can read auxiliary
        ``product.product`` records (option-products attached to
        attribute values).

        Sudo note (PUBLIC-BUYER ACL — pre-existing OCA defect, also
        present in 17.0): the configurator's "extras" pricing
        mechanism attaches ``product.product`` rows to attribute
        values (Silver Paint, 218d Coupé, Auto Steptronic, Sport
        Line, etc.) for price computation. Those auxiliary products
        are NOT ``website_published`` — they're internal records, not
        catalog items. Core Odoo's ``ir.rule`` "Public product
        template" denies public + portal reads on non-published
        templates, so any traversal through them — including
        ``_get_combination_info()`` which iterates variants for
        pricing — raises ``AccessError`` and the wizard page 403s.

        The bug is invisible to OCA's automated tests because the
        tour ``TestUi.test_01_admin_config_tour`` runs as admin
        (bypasses all ir.rules). Surfaces in production only for the
        SECOND anonymous buyer onwards of any config_ok template
        (the first buyer's wizard creates the resolved variant; once
        that variant exists, subsequent renders traverse into the
        auxiliary option-products and 403).

        Scope discipline: sudo() is applied ONLY to the ``product``
        argument, ONLY when ``product.config_ok`` is True. Non-
        configurable products take the unchanged super() path. The
        sudo'd product is consumed inside core's
        ``_prepare_product_values`` and the values it returns
        populate the QWeb template — which already renders to the
        buyer (the buyer needs to see option-product prices to
        configure). No sudo'd recordset is written through, exposed
        in a field the buyer shouldn't see, or escapes to a
        different controller.
        """
        if product.config_ok:
            product = product.sudo()
        return super()._prepare_product_values(product, category, **kwargs)

    def get_image_vals(self, image_line_ids, model_name):
        if isinstance(image_line_ids[:1], models.Model):
            model_name = image_line_ids[:1]._name
            image_line_ids = image_line_ids.ids
        config_image_vals = {
            "config_image_ids": image_line_ids,
            "name": model_name,
        }
        return config_image_vals

    def get_render_vals(self, cfg_session):
        """Return dictionary with values required for website template
        rendering"""

        # if no config step exist
        product_configurator_obj = request.env["product.configurator"]
        open_cfg_step_lines = cfg_session.get_open_step_lines()
        cfg_step_lines = cfg_session.get_all_step_lines()
        custom_val_id = cfg_session.get_custom_value_id()
        check_val_ids = (
            cfg_session.product_tmpl_id.attribute_line_ids.mapped("value_ids")
            + custom_val_id
        )
        available_value_ids = cfg_session.values_available(
            check_val_ids=check_val_ids.ids
        )
        extra_attribute_line_ids = self.get_extra_attribute_line_ids(
            cfg_session.product_tmpl_id
        )

        # If one remove/add config steps in middle of session
        active_step = False
        if cfg_step_lines:
            active_step = cfg_session.get_active_step()
            if (
                not active_step
                and extra_attribute_line_ids
                and cfg_session.config_step == "configure"
            ):
                pass
            elif not active_step or active_step not in open_cfg_step_lines:
                active_step = open_cfg_step_lines[:1]
                cfg_session.config_step = "%s" % (active_step.id)

        cfg_session = cfg_session.sudo()
        config_image_ids = False
        if cfg_session.value_ids:
            config_image_ids = cfg_session._get_config_image(
                cfg_session.value_ids.ids, cfg_session._get_custom_vals_dict()
            )
        if not config_image_ids:
            config_image_ids = cfg_session.product_tmpl_id

        weight_prec = (
            request.env["decimal.precision"].precision_get("Stock Weight") or 2
        )
        website_tmpl_xml_id = cfg_session.get_config_form_website_template()
        pricelist = request.website._get_and_cache_current_pricelist()
        product_tmpl = cfg_session.product_tmpl_id
        attr_value_ids = product_tmpl.attribute_line_ids.mapped("value_ids")
        av_obj = request.env["product.attribute.value"]
        extra_prices = av_obj.sudo().get_attribute_value_extra_prices(
            product_tmpl_id=product_tmpl.id,
            pt_attr_value_ids=attr_value_ids,
            pricelist=pricelist,
        )

        # [REF] (e) — compute stock availability for the current
        # configuration's selected option-products and surface in the
        # wizard. See product.config.session.get_config_stock_info()
        # for aggregation rules. Sudo is applied INSIDE that method
        # because the option-product reads are subject to the same
        # public-buyer ACL block the W1 fix addresses (commit 5c15859);
        # the method handles the sudo scope, the controller just
        # threads the result.
        stock_info = cfg_session.get_config_stock_info()

        vals = {
            "cfg_session": cfg_session,
            "cfg_step_lines": cfg_step_lines,
            "open_cfg_step_lines": open_cfg_step_lines,
            "active_step": active_step,
            "value_ids": cfg_session.value_ids,
            "custom_value_ids": cfg_session.custom_value_ids,
            "available_value_ids": available_value_ids,
            "product_tmpl": cfg_session.product_tmpl_id,
            "prefixes": product_configurator_obj._prefixes,
            "custom_val_id": custom_val_id,
            "extra_attribute_line_ids": extra_attribute_line_ids,
            "config_image_vals": self.get_image_vals(
                image_line_ids=config_image_ids,
                model_name=config_image_ids[:1]._name,
            ),
            "weight_prec": weight_prec,
            "main_object": cfg_session.product_tmpl_id,
            "default_website_template": website_tmpl_xml_id,
            "pricelist": pricelist,
            "extra_prices": extra_prices,
            "stock_info": stock_info,
        }
        return vals

    def render_form(
        self, cfg_session, product, category, search, values=None, **kwargs
    ):
        """Render the website form for the given template and configuration
        session"""
        if values is None:
            values = {}
        product_values = self._prepare_product_values(
            product=product, category=category, search=search, **kwargs
        )
        config_vals = self.get_render_vals(cfg_session)
        values.update(product_values)
        values.update(config_vals)
        return request.render(
            "website_product_configurator.product_configurator", values
        )

    def remove_recursive_list(self, values):
        """Return dictionary by removing extra list
        :param: values: dictionary having values in form [[4, 0, [2, 3]]]
        :return: dictionary
        EX- {2: [2, 3]}"""
        new_values = {}
        for key, value in values.items():
            if isinstance(value, tuple):
                value = value[0]
            if isinstance(value, list):
                value = value[0][2]
            new_values[key] = value
        return new_values

    def get_current_configuration(self, form_values, cfg_session):
        """Return list of ids of selected attribute-values
        :param: form_values: dictionary of field name and selected values
            Ex: {
                __attribute-attr-id: attribute-value,
                __custom-attr-id: custom-value
            }
        :param: cfg_session: record set of config session"""

        product_tmpl_id = cfg_session.product_tmpl_id
        product_configurator_obj = request.env["product.configurator"]
        field_prefix = product_configurator_obj._prefixes.get("field_prefix")
        # custom_field_prefix = product_configurator_obj._prefixes.get(
        #    'custom_field_prefix')
        custom_val_id = cfg_session.get_custom_value_id()

        product_attribute_lines = product_tmpl_id.attribute_line_ids
        value_ids = []
        for attr_line in product_attribute_lines:
            field_name = f"{field_prefix}{attr_line.attribute_id.id}"
            attr_values = form_values.get(field_name, False)
            if attr_line.custom and attr_values == custom_val_id.id:
                pass
            else:
                if not attr_values:
                    continue
                if not isinstance(attr_values, list):
                    attr_values = [attr_values]
                elif isinstance(attr_values[0], list):
                    attr_values = attr_values[0][2]
                value_ids += attr_values
        return value_ids

    def _prepare_configurator_values(self, form_vals, config_session_id):
        """Return dictionary of fields and values present
        on configuration wizard"""
        config_session_id = config_session_id.sudo()
        product_tmpl_id = config_session_id.product_tmpl_id
        config_fields = {
            "state": config_session_id.state,
            "config_session_id": config_session_id.id,
            "product_tmpl_id": product_tmpl_id.id,
            "product_preset_id": config_session_id.product_preset_id.id,
            "price": config_session_id.price,
            "value_ids": [[6, False, config_session_id.value_ids.ids]],
            "attribute_line_ids": [
                [4, line.id, False] for line in product_tmpl_id.attribute_line_ids
            ],
        }
        config_fields.update(form_vals)
        return config_fields

    def get_orm_form_vals(self, form_vals, config_session):
        """Return dictionary of dynamic field and its values
        :param: form_vals: list of dictionary
            Ex: [{'name': field-name, 'value': field-value},]
        :param: cfg_session: record set of config session"""

        product_tmpl_id = config_session.product_tmpl_id
        values = {}
        for form_val in form_vals:
            dict_key = form_val.get("name", False)
            dict_value = form_val.get("value", False)
            if not dict_key or not dict_value:
                continue
            if dict_key not in values:
                values.update({dict_key: []})
            values[dict_key].append(dict_value)

        product_configurator_obj = request.env["product.configurator"]
        field_prefix = product_configurator_obj._prefixes.get("field_prefix")
        custom_field_prefix = product_configurator_obj._prefixes.get(
            "custom_field_prefix"
        )

        config_vals = {}
        for attr_line in product_tmpl_id.attribute_line_ids.sorted():
            attribute_id = attr_line.attribute_id.id
            field_name = f"{field_prefix}{attribute_id}"
            custom_field = f"{custom_field_prefix}{attribute_id}"

            field_value = values.get(field_name, [])
            field_value = [int(s) for s in field_value]
            custom_field_value = values.get(custom_field, False)

            if attr_line.custom and custom_field_value:
                custom_field_value = custom_field_value[0]
                if attr_line.attribute_id.custom_type in ["int", "float"]:
                    custom_field_value = safe_eval(custom_field_value)

            if attr_line.multi:
                field_value = [[6, False, field_value]]
            else:
                field_value = field_value and field_value[0] or False

            config_vals.update(
                {field_name: field_value, custom_field: custom_field_value}
            )
        return config_vals

    def get_config_product_template(self, form_vals):
        """Return record set of product template"""
        product_template_id = request.env["product.template"]
        for val in form_vals:
            if val.get("name") == "product_tmpl_id":
                product_tmpl_id = val.get("value")

        if product_tmpl_id:
            product_template_id = product_template_id.browse(int(product_tmpl_id))
        return product_template_id

    def get_extra_attribute_line_ids(self, product_template_id):
        """Retrieve attribute lines defined on the product_template_id
        which are not assigned to configuration steps"""

        extra_attribute_line_ids = (
            product_template_id.attribute_line_ids
            - product_template_id.config_step_line_ids.mapped("attribute_line_ids")
        )
        return extra_attribute_line_ids

    @http.route(
        "/website_product_configurator/onchange",
        type="jsonrpc",
        methods=["POST"],
        auth="public",
        website=True,
    )
    def onchange(self, form_values, field_name, **post):
        """Capture onchange events in the website and forward data to backend
        onchange method"""
        # config session and product template
        product_configurator_obj = request.env["product.configurator"]
        product_template_id = self.get_config_product_template(form_values)
        try:
            config_session_id = self.get_config_session(
                product_tmpl_id=product_template_id
            )
        except Exception as Ex:
            return {"error": Ex}

        # prepare dictionary in formate needed to pass in onchage
        form_values = self.get_orm_form_vals(form_values, config_session_id)
        config_vals = self._prepare_configurator_values(form_values, config_session_id)

        # call onchange
        specs = product_configurator_obj._onchange_spec()
        updates = {}
        try:
            updates = product_configurator_obj.sudo().apply_onchange_values(
                values=config_vals, field_names=[field_name], field_onchange=specs
            )
            updates["value"] = self.remove_recursive_list(updates["value"])
        except Exception as Ex:
            return {"error": Ex}

        # get open step lines according to current configuation
        value_ids = updates["value"].get("value_ids")
        if not value_ids:
            value_ids = self.get_current_configuration(form_values, config_session_id)
        try:
            open_cfg_step_line_ids = (
                config_session_id.sudo().get_open_step_lines(value_ids).ids
            )
        except Exception as Ex:
            return {"error": Ex}

        # if no step is defined or some attribute remains to add in a step
        open_cfg_step_line_ids = [
            "%s" % (step_id) for step_id in open_cfg_step_line_ids
        ]
        extra_attr_line_ids = self.get_extra_attribute_line_ids(product_template_id)
        if extra_attr_line_ids:
            open_cfg_step_line_ids.append("configure")

        # configuration images
        config_image_ids = config_session_id._get_config_image(value_ids=value_ids)
        if not config_image_ids:
            config_image_ids = product_template_id

        image_vals = self.get_image_vals(
            image_line_ids=config_image_ids,
            model_name=config_image_ids[:1]._name,
        )
        pricelist = request.website._get_and_cache_current_pricelist()
        updates["open_cfg_step_line_ids"] = open_cfg_step_line_ids
        updates["config_image_vals"] = image_vals
        decimal_prec_obj = request.env["decimal.precision"]
        updates["decimal_precision"] = {
            "weight": decimal_prec_obj.precision_get("Stock Weight") or 2,
            "price": pricelist.currency_id.decimal_places or 2,
        }
        return updates

    def set_config_next_step(
        self, config_session_id, current_step=False, next_step=False
    ):
        """Return next step of configuration wizard
        param: current_step: (string) current step of configuration wizard
        param: current_step: (string) next step of configuration wizard
            (in case when someone click on step directly instead
            of clicking on next button)
        return: (string) next step"""
        config_session_id = config_session_id.sudo()
        extra_attr_line_ids = self.get_extra_attribute_line_ids(
            config_session_id.product_tmpl_id
        )
        if extra_attr_line_ids and current_step == "configure":
            if next_step:
                config_session_id.config_step = next_step
                return {"next_step": next_step}
            else:
                next_step = config_session_id.check_and_open_incomplete_step()
            if not next_step:
                return {"next_step": False}

        if not next_step:
            try:
                next_step = config_session_id.get_next_step(
                    state=current_step,
                )
            except (UserError, ValidationError) as Ex:
                return {"error": Ex}
        if not next_step and extra_attr_line_ids and current_step != "configure":
            next_step = "configure"

        if not next_step:
            next_step = config_session_id.check_and_open_incomplete_step()
        if next_step and isinstance(
            next_step, type(request.env["product.config.step.line"])
        ):
            next_step = "%s" % (next_step.id)
        if next_step:
            config_session_id.config_step = next_step
        return {"next_step": next_step}

    @http.route(
        "/website_product_configurator/save_configuration",
        type="jsonrpc",
        methods=["POST"],
        auth="public",
        website=True,
    )
    def save_configuration(
        self, form_values, current_step=False, next_step=False, **post
    ):
        """Save current configuration in related session and
        next step if exist otherwise create variant using
        configuration redirect to product page of configured product"""
        product_template_id = self.get_config_product_template(form_values)
        try:
            config_session_id = self.get_config_session(
                product_tmpl_id=product_template_id
            )
        except Exception as Ex:
            return {"error": Ex}

        form_values = self.get_orm_form_vals(form_values, config_session_id)
        try:
            # save values
            config_session_id.sudo().update_session_configuration_value(
                vals=form_values, product_tmpl_id=product_template_id
            )

            # next step
            check_next_step = True
            if post.get("submit_configuration"):
                try:
                    valid = config_session_id.sudo().validate_configuration()
                    if valid:
                        check_next_step = False
                except Exception:
                    _logger.error("Error validating configuration.")
            if check_next_step:
                result = self.set_config_next_step(
                    config_session_id=config_session_id,
                    current_step=current_step,
                    next_step=next_step,
                )
                if result.get("next_step", False):
                    return {"next_step": result.get("next_step")}
                elif result.get("error", False):
                    return {"error": result.get("error")}
            if not (config_session_id.value_ids or config_session_id.custom_value_ids):
                return {
                    "error": (
                        "You must select at least one "
                        "attribute in order to configure a product"
                    )
                }
            # create variant
            config_session_id.sudo().action_confirm()
            product = config_session_id.product_id
            if product:
                redirect_url = "/product_configurator/product"
                redirect_url += "/%s" % (request.env["ir.http"]._slug(config_session_id))
                return {
                    "product_id": product.id,
                    "config_session": config_session_id.id,
                    "redirect_url": redirect_url,
                }
        except Exception as Ex:
            return {"error": Ex}
        return {}

    @http.route(
        "/product_configurator/product/"
        '<model("product.config.session"):cfg_session_id>',
        type="http",
        auth="public",
        website=True,
    )
    def cfg_session(self, cfg_session_id, **post):
        """Render product page of product_id"""
        if (
            not cfg_session_id.exists()
            or cfg_session_id.user_id != request.env.user
            or cfg_session_id.state != "done"
        ):
            return request.render("website.page_404")
        product_id = cfg_session_id.product_id.sudo()
        product_tmpl_id = product_id.product_tmpl_id

        custom_vals = sorted(
            cfg_session_id.custom_value_ids,
            key=lambda obj: obj.attribute_id.sequence,
        )
        vals = sorted(
            product_id.product_template_attribute_value_ids.mapped(
                "product_attribute_value_id"
            ),
            key=lambda obj: obj.attribute_id.sequence,
        )
        pricelist = get_pricelist()
        product_config_session = request.session.get("product_config_session")

        # str() cast for the same reason as get_config_session above:
        # JSON-stored dict has string keys, ``.get(int)`` always misses.
        if product_config_session and product_config_session.get(str(product_tmpl_id.id)):
            request.session.pop("product_config_session", None)

        reconfigure_product_url = "/product_configurator/reconfigure/%s" % request.env["ir.http"]._slug(
            product_id
        )
        values = {
            "product_variant": product_id,
            "product": product_tmpl_id,
            "cfg_session_id": cfg_session_id,
            "pricelist": pricelist,
            "custom_vals": custom_vals,
            "vals": vals,
            "reconfigure_product_url": reconfigure_product_url,
        }
        return request.render("website_product_configurator.cfg_product", values)

    def _check_reconfigure_ownership(self, product):
        """IDOR guard for /product_configurator/reconfigure/<id>.

        Returns True iff the requesting buyer owns this variant.

        Branch (a): variant is in the buyer's cart, via two explicit
          channels we control (NOT ``request.cart``, whose internal
          sudo/scope is a website_sale implementation detail subject
          to change):
          (a1) Anonymous + authenticated alike — sale_order_id from
               the server-side browser session (Odoo middleware
               writes; buyer cannot spoof). Sudo-browse, confirm the
               variant is a line.
          (a2) Authenticated (non-public) only — partner-linked draft
               sale.order on the current website. Covers a portal
               buyer reaching /reconfigure on a fresh browser session
               where (a1) is empty but the buyer has a cart on
               another device.

        Branch (b): variant was produced by one of the buyer's recent
          config sessions, restricted to ``state == 'done'`` sessions
          only. Required for the post-wizard-pre-cart UX flow (the
          "Reconfigure" link renders on the resolved-variant detail
          page BEFORE the buyer clicks Add to Cart; in that window
          branch (a) returns False). ``state='done'`` guarantees the
          session has a resolved ``product_id`` — drafts (which would
          over-grant) are excluded.

        All channels consult only server-side state the buyer cannot
        influence via URL. Set of variant ids that satisfy ownership
        is buyer-attributable by construction.

        Without this check, the sudo().browse() in
        ``reconfigure_product`` would create an IDOR — buyer A could
        be impersonated by anyone iterating product.product ids in
        the URL, learning their configuration and stealing it into
        their own session.
        """
        # (a1) cart via session-tracked sale_order_id
        sale_order_id = request.session.get("sale_order_id")
        if sale_order_id:
            cart = (
                request.env["sale.order"]
                .sudo()
                .browse(sale_order_id)
                .exists()
            )
            if cart and product.id in cart.order_line.mapped("product_id").ids:
                return True

        # (a2) partner-linked draft cart (authenticated only)
        if not request.env.user.has_group("base.group_public"):
            partner_cart = (
                request.env["sale.order"]
                .sudo()
                .search(
                    [
                        ("partner_id", "=", request.env.user.partner_id.id),
                        ("state", "=", "draft"),
                        ("website_id", "=", request.website.id),
                    ],
                    limit=1,
                    order="id desc",
                )
            )
            if (
                partner_cart
                and product.id in partner_cart.order_line.mapped("product_id").ids
            ):
                return True

        # (b) recent done-state config sessions
        session_dict = request.session.get("product_config_session") or {}
        cfg_session_ids = [v for v in session_dict.values() if v]
        if not cfg_session_ids:
            return False
        cfg_sessions = (
            request.env["product.config.session"]
            .sudo()
            .search(
                [
                    ("id", "in", cfg_session_ids),
                    ("state", "=", "done"),
                ]
            )
        )
        return product.id in cfg_sessions.mapped("product_id").ids

    @http.route(
        "/product_configurator/reconfigure/<int:product_id>",
        type="http",
        auth="public",
        website=True,
    )
    def reconfigure_product(self, product_id, **post):
        """Re-open a previously configured cart/order line.

        19.0 ACL note: the prior route signature
        ``<model("product.product"):product_id>`` forced Odoo's URL
        converter to ``browse()`` + read product.product with the
        public user's environment, which is denied by core Odoo's
        ``ir.rule`` "Public product template" for config_ok variants
        (option-products and resolved variants are not
        ``website_published``). That produced a 403 BEFORE the
        controller body ran — making the route unreachable for the
        anonymous buyer it's intended to serve.

        The signature is now ``<int:product_id>`` so the converter
        doesn't read the variant. The controller body then does the
        read under sudo() — scoped to this one ``browse()`` call —
        and IMMEDIATELY enforces ownership via
        ``_check_reconfigure_ownership`` to prevent IDOR.

        Failure cases (variant doesn't exist OR ownership fails) both
        redirect to the OCA error page — fail-closed.
        """
        # Sudo-browse: ACL would deny public read on config_ok
        # variants whose templates are not website_published.
        # SCOPED to this browse call only; the returned recordset is
        # checked by ownership BEFORE any further field traversal.
        product = (
            request.env["product.product"]
            .sudo()
            .browse(product_id)
            .exists()
        )
        if not product:
            return request.redirect(
                "/website_product_configurator/error_page/1"
            )

        # IDOR guard (fail-closed)
        if not self._check_reconfigure_ownership(product):
            return request.redirect(
                "/website_product_configurator/error_page/1"
            )

        try:
            product_tmpl_id = product.product_tmpl_id

            cfg_session = self.get_config_session(product_tmpl_id=product_tmpl_id)
            tmpl_value_ids = product.product_template_attribute_value_ids
            cfg_session.value_ids = tmpl_value_ids.mapped("product_attribute_value_id")
            cfg_session.product_id = product.id
            return request.redirect(
                "/shop/product/%s" % (request.env["ir.http"]._slug(product_tmpl_id))
            )
        except Exception:
            error_code = 1
            return request.redirect(
                "/website_product_configurator/error_page/%s" % (error_code)
            )

    @http.route(
        [
            error_page,
            "%s<string:message>" % error_page,
            "%s<string:error>/<string:message>" % error_page,
        ],
        type="http",
        auth="public",
        website=True,
    )
    def render_error(self, error=None, message="", **post):
        error = error and True or False
        if not message:
            message = (
                "Due to technical issues the requested operation is not"
                "available. Please try again later."
            )
        vals = {"message": message, "error": error}
        return request.render("website_product_configurator.error_page", vals)

    # ------------------------------------------------------------------
    # [REF] (f) — Saved-configurations bookmark endpoint
    # ------------------------------------------------------------------
    # NOTE: this is intentionally distinct from
    # /website_product_configurator/save_configuration above. That
    # endpoint commits the configuration to a variant (action_confirm),
    # which is a sale-intent step. This endpoint marks the current
    # draft session as a buyer-facing bookmark — it does NOT confirm,
    # does NOT create a variant, and does NOT add to cart. The buyer
    # can return to /my/configurations later and either continue
    # editing or proceed to add-to-cart.
    @http.route(
        "/website_product_configurator/save_configuration_bookmark",
        type="jsonrpc",
        methods=["POST"],
        auth="user",
        website=True,
    )
    def save_configuration_bookmark(self, session_id, name=None, **post):
        """Mark a draft configuration session as a saved bookmark.

        Requires auth='user' (not 'public') — anonymous buyers have
        no portal home to return to, so the bookmark would be lost.
        If a public buyer wants to save, the storefront should prompt
        for login first.

        :param int session_id: id of the product.config.session
        :param str name: optional buyer-supplied label (<=128 chars)
        :return: {"ok": True, "session_id": id, "name": stored_name}
                 or {"ok": False, "error": str}
        """
        try:
            session_id = int(session_id)
        except (TypeError, ValueError):
            return {"ok": False, "error": "invalid session_id"}

        # Ownership check via search() — NOT browse().exists().
        # Odoo's .exists() does a raw SQL row-existence query that
        # bypasses ir.rule (it only confirms the row is physically
        # present in the table). search() applies rules normally.
        #
        # We also include an explicit ``user_id == current_user``
        # filter in the domain so internal users (who are unaffected
        # by the portal ir.rule) can't bookmark someone else's
        # session either — defense in depth.
        session = request.env["product.config.session"].search(
            [
                ("id", "=", session_id),
                ("user_id", "=", request.env.user.id),
            ],
            limit=1,
        )
        if not session:
            # Same shape for "doesn't exist" and "not yours" — don't
            # leak existence of other users' sessions.
            return {"ok": False, "error": "session not found"}

        # Sudo the write: portal users have perm_write=0 on
        # product.config.session via ir.model.access.csv. We've
        # already proven ownership in the search above, so sudo is
        # scoped to a known-owned record and writes only the two
        # legacy fields via action_save_config.
        #
        # FEATURE 2 — action_save_config now ALSO creates or refreshes
        # a product.config.bookmark record via the inheritance in
        # product_config_bookmark.py. The legacy fields stay synced
        # (is_saved=True, bookmark_name=name) for backwards compat.
        try:
            bookmark = session.sudo().action_save_config(name=name)
        except Exception as exc:  # noqa: BLE001 — surface to JSON-RPC
            _logger.exception("save_configuration_bookmark failed")
            return {"ok": False, "error": str(exc)}

        # Defensive: action_save_config returns the bookmark record
        # in the FEATURE 2 path, but a plain truthy in legacy paths
        # (e.g., if an extension overrides action_save_config without
        # calling super). Normalize the response.
        bookmark_id = bookmark.id if hasattr(bookmark, "id") else False
        return {
            "ok": True,
            "session_id": session.id,
            "bookmark_id": bookmark_id,
            "name": session.sudo().bookmark_name or "",
        }
