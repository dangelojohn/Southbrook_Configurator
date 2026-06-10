# SAMI / Southbrook — custom Odoo 19 image.
#
# Three runtime deps baked in so container recreates don't lose them:
#
#   Mako       — OCA product_configurator family hard-depends on it; without
#                it `odoo -i product_configurator` fails with UserError
#                "external dependency is not met: mako". Documented as a
#                deploy gotcha in [[southbrook_plm_deploy]].
#
#   ezdxf      — services/freecad_bridge invokes freecadcmd which calls
#                back into odoo; the southbrook_dealer_portal installation
#                PDF also expects it for any future DXF embedding. Pinned to
#                match the bridge container's pin.
#
#   reportlab  — southbrook_dealer_portal.export_installation_pdf builds
#                multi-page PDFs (cut list + hardware schedule + KD holes).
#                Already shipped with most Odoo images but pinning the
#                version makes the QNAP deploy reproducible.
#
#   svglib     — used by export_installation_pdf to convert TechDraw
#                elevation SVGs (returned by the freecad-bridge
#                /render_elevation endpoint, base64 in the response) into
#                ReportLab Drawing objects that platypus embeds directly
#                in the multi-page PDF. Brings tinycss2 + cssselect2 as
#                transitive deps but those are pure-python.
#
# Pin versions match what gets installed via `pip install` post-recreate
# today, so swapping to this image is behaviour-preserving.

FROM odoo:19

USER root
RUN pip install --break-system-packages --no-cache-dir \
        Mako==1.3.12 \
        ezdxf==1.4.2 \
        reportlab==4.1.0 \
        svglib==1.5.1
USER odoo
