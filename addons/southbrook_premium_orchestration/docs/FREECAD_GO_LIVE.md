# FreeCAD Bridge Go-Live Checklist

**Date:** 2026-06-15
**Owner:** Southbrook Cabinetry — Premium MRP Orchestration (Phase 3.2)
**Scope:** Flip `southbrook_freecad_bridge` from dormant to live render jobs.

---

## Prerequisite

The FreeCAD bridge daemon must be deployed and reachable at the configured URL
(default: `http://southbrook-freecad-bridge:8000`). Before flipping the enable
flag, **confirm the container is actually running on the QNAP stack** — the
default URL resolves only on `alfacore-caddy`'s docker network. If you're not
sure, check `docker ps | grep freecad` from inside the QNAP system-docker shell.

---

## Steps

1. **Confirm reachability from inside the Odoo container.** From the
   `southbrook-odoo` container shell:
   ```bash
   curl -i http://southbrook-freecad-bridge:8000/health
   ```
   Must return `HTTP/1.1 200 OK`. If the connection is refused, the daemon
   is not deployed — fix the deploy first, do **not** flip the flag against
   a missing bridge.
2. **Open the activation wizard.** Either:
    - Settings → Technical → Actions → "Activate FreeCAD" (`action_freecad_activation_wizard`); or
    - Kitchen Ops → Generative → Activate FreeCAD (Phase 3.5 menu surface).
3. **Run the health check.** Confirm the URL, leave **Run Health Check**
   ticked, click **Apply**. A green notification confirms the bridge replied
   200 to `/health`.
4. **Enable.** With **Enable After Health Check** ticked, the wizard flips
   `ir.config_parameter.freecad_bridge.enabled` to `True` in the same Apply.
   The activator's "Bridge Enabled" field should now read True.
5. **Render the first MO.** Tick **Render Oldest Pending MO** and re-run
   Apply (or use the activator's "Render First MO" action directly). The
   wizard picks the oldest `mrp.production` with `x_cad_status='pending'`
   and invokes its existing render entry point (`action_regenerate_cad`).
   Watch `x_cad_status` flip **pending → rendering → done**, and the
   activator's "CAD Attachments" count increment by 1 (a DXF or STEP).
6. **Open the rendered attachment.** Download the new attachment from the
   MO form. Confirm it opens in any DXF/STEP viewer.

---

## Failure modes

- **502 / connection refused from the bridge.** The daemon is not deployed
  on the QNAP. Deploy it (`docker compose up -d freecad-bridge` in the
  southbrook stack), or pull the FreeCAD capability from the pitch — do
  not ship a half-on integration.
- **Render returns OK but no attachment appears.** The bridge is not
  writing back to Odoo. Check the bridge's XML-RPC callback config and
  the `freecad_bridge.secret` ir.config_parameter. Fix the bridge's return
  contract before re-running.
- **Health check OK but `action_enable` raises UserError.** The activator
  refuses to flip the flag unless the most recent health check is OK.
  Re-run the check, then enable.

---

## Rollback

Open the FreeCAD Activator record → click **Disable**. This sets
`freecad_bridge.enabled` back to `False`; new MOs will not POST render
jobs. In-flight renders complete normally and write their attachments
back; only the next batch is gated.
