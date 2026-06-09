# SAMI / Southbrook — custom Odoo 19 image.
#
# Extends odoo:19 with Mako, which the OCA product_configurator family
# depends on but the upstream image does not ship. Without this, a fresh
# `compose run odoo -i product_configurator` fails with:
#   UserError: Unable to install module "product_configurator" because an
#   external dependency is not met: mako
#
# Recorded as a gotcha in the southbrook_plm deploy memory; baking it in
# here means new dev clones don't repeat the manual `pip install Mako` step.

FROM odoo:19

USER root
RUN pip install --break-system-packages --no-cache-dir Mako
USER odoo
