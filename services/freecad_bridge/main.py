# SPDX-License-Identifier: LGPL-3.0-only
"""SAMI / Southbrook — FreeCAD bridge (Module 2 surface).

Endpoints:
  GET  /health               — liveness probe, no secret required
  GET  /templates            — list .FCStd templates available for render
  POST /validate             — geometric pre-check on a render spec
  POST /render               — kick off an async render job, returns job_id
  GET  /status/{job_id}      — poll a job's state

Auth: all endpoints EXCEPT /health require an X-Bridge-Secret header
matching FREECAD_BRIDGE_SECRET (env var).

Render job pattern (fire-and-forget):
  POST /render
    body: {production_id, template, dimensions: {width_mm, height_mm,
           depth_mm}, family, door_count}
    response: {job_id, status: 'queued'}
  Background task:
    1. spawn freecadcmd render_cabinet.py with the spec on a temp dir
    2. read the generated DXF / SVG / PDF / STEP artifacts
    3. XML-RPC `ir.attachment.create` on each artifact, capturing IDs
    4. HTTP POST /plm/cad_callback on Odoo with X-Bridge-Secret +
       {production_id, status, attachment_ids}

In-memory job table is intentional for Module 2: when the bridge process
dies, all in-flight jobs are lost. A persistent queue (Redis or RQ) is
a Module 2-or-later optimisation explicitly out of initial scope.

Geometry source of truth: when render_cabinet.py runs it imports
southbrook_dims from /srv/shared (same module Odoo's G1 test imports).
Drift between bridge geometry and Odoo BoM is therefore impossible by
construction as long as G1 passes.
"""
from __future__ import annotations

import logging
import os
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger("freecad_bridge")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

app = FastAPI(title="SAMI FreeCAD Bridge", version="0.2.0")

BRIDGE_SECRET = os.environ.get("FREECAD_BRIDGE_SECRET", "")
TEMPLATES_DIR = Path(os.environ.get("FREECAD_TEMPLATES_DIR", "/srv/freecad_templates"))
ODOO_URL = os.environ.get("ODOO_URL", "http://odoo:8069")
ODOO_DB = os.environ.get("ODOO_DB", "southbrook")
ODOO_USER = os.environ.get("ODOO_USER", "admin")
ODOO_API_KEY = os.environ.get("ODOO_API_KEY", "admin")


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
def require_secret(x_bridge_secret: str = Header(default="", alias="X-Bridge-Secret")) -> None:
    """FastAPI dependency: enforce X-Bridge-Secret header on protected routes."""
    if not BRIDGE_SECRET:
        raise HTTPException(status_code=503, detail="bridge_secret_unset")
    if x_bridge_secret != BRIDGE_SECRET:
        raise HTTPException(status_code=401, detail="invalid_bridge_secret")


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
class Dimensions(BaseModel):
    width_mm: float = Field(..., gt=0, le=3000)
    height_mm: float = Field(..., gt=0, le=3000)
    depth_mm: float = Field(..., gt=0, le=1500)


class RenderSpec(BaseModel):
    production_id: int = Field(..., gt=0)
    template: str = Field(..., min_length=1, max_length=128)
    dimensions: Dimensions
    family: str = Field(default="base")
    door_count: int = Field(default=1, ge=0, le=4)


class ValidationResult(BaseModel):
    ok: bool
    errors: List[str] = []
    panel_cut_list: Optional[Dict[str, Any]] = None


JobStatus = str  # 'queued' | 'rendering' | 'done' | 'error'


@dataclass
class JobRecord:
    job_id: str
    spec: RenderSpec
    status: JobStatus = "queued"
    artifacts: Dict[str, str] = field(default_factory=dict)
    attachment_ids: List[int] = field(default_factory=list)
    error: Optional[str] = None


JOBS: Dict[str, JobRecord] = {}


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------
def list_templates() -> List[str]:
    if not TEMPLATES_DIR.exists():
        return []
    return sorted(p.stem for p in TEMPLATES_DIR.glob("*.FCStd"))


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.get("/health")
def health() -> dict:
    """Liveness probe — no secret required.

    Reports whether the secret is configured (boolean only — never echo
    the secret itself in any response).
    """
    return {
        "status": "ok",
        "module": "freecad_bridge",
        "phase": "module-2",
        "secret_configured": bool(BRIDGE_SECRET),
        "templates_count": len(list_templates()),
        "jobs_in_memory": len(JOBS),
    }


@app.get("/templates", dependencies=[Depends(require_secret)])
def templates() -> dict:
    """List available .FCStd parametric templates."""
    return {"templates": list_templates()}


@app.post("/validate", dependencies=[Depends(require_secret)])
def validate(spec: RenderSpec) -> ValidationResult:
    """Pre-flight geometric check using shared.southbrook_dims.

    The bridge imports the SAME formulas Odoo's G1 test imports, so a
    /validate result is the same answer Odoo's BoM math would give.
    """
    errors: List[str] = []
    if spec.template not in list_templates():
        errors.append(f"unknown_template:{spec.template}")

    cut_list: Optional[Dict[str, Any]] = None
    try:
        from southbrook_dims import panel_cut_list  # /srv/shared on PYTHONPATH
        cut_list = panel_cut_list(
            spec.dimensions.width_mm,
            spec.dimensions.height_mm,
            spec.dimensions.depth_mm,
            family=spec.family,
            door_count=spec.door_count,
        )
        # Sanity: no negative or zero panel dimensions.
        for name, value in cut_list.items():
            if isinstance(value, tuple) and any(v <= 0 for v in value):
                errors.append(f"non_positive_panel:{name}={value}")
    except ImportError:
        errors.append("southbrook_dims_unavailable")
    except Exception as exc:  # pragma: no cover - defensive
        errors.append(f"geometry_error:{exc}")

    return ValidationResult(ok=not errors, errors=errors, panel_cut_list=cut_list)


@app.post("/render", dependencies=[Depends(require_secret)])
def render(spec: RenderSpec, background: BackgroundTasks) -> dict:
    """Enqueue a render job. Returns immediately with job_id; rendering
    happens off-thread; results go back to Odoo via /plm/cad_callback."""
    job_id = uuid.uuid4().hex
    record = JobRecord(job_id=job_id, spec=spec)
    JOBS[job_id] = record
    background.add_task(_run_render_job, job_id)
    logger.info("render queued: job_id=%s production=%s template=%s",
                job_id, spec.production_id, spec.template)
    return {"job_id": job_id, "status": record.status}


class ElevationSpec(BaseModel):
    production_id: int = Field(..., gt=0)
    dimensions: Dimensions
    family: str = Field(default="base")
    door_count: int = Field(default=1, ge=0, le=4)


@app.post("/render_elevation", dependencies=[Depends(require_secret)])
def render_elevation(spec: ElevationSpec) -> dict:
    """Synchronous TechDraw elevation render.

    Unlike /render (parametric carcass STEP/DXF/SVG, long-running, async),
    this endpoint produces a small, deterministic three-view orthographic
    drawing of the same carcass — fast enough to run inline in the dealer
    portal's installation-PDF export request. Wall-clock on the QNAP is
    under 8 seconds for a single cabinet (most of which is xvfb startup).

    Returns the manifest JSON plus base64-encoded SVG bodies for the
    caller to embed directly (no second round-trip to fetch each view).
    """
    import base64
    import json as _json
    import subprocess
    import tempfile

    output_dir = Path(tempfile.mkdtemp(prefix="elev_"))
    spec_payload = {
        "production_id": spec.production_id,
        "dimensions": {
            "width_mm": spec.dimensions.width_mm,
            "height_mm": spec.dimensions.height_mm,
            "depth_mm": spec.dimensions.depth_mm,
        },
        "family": spec.family,
        "door_count": spec.door_count,
        "output_dir": str(output_dir),
    }
    try:
        result = subprocess.run(
            ["xvfb-run", "-a", "freecadcmd",
             "/app/scripts/render_elevation.py",
             "--", _json.dumps(spec_payload)],
            capture_output=True, text=True, timeout=60,
        )
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="render_timeout")

    if result.returncode != 0:
        logger.error("elevation freecadcmd failed rc=%s stderr=%s",
                     result.returncode, result.stderr[-500:])
        raise HTTPException(
            status_code=500,
            detail=f"freecadcmd_exit_{result.returncode}",
        )

    # Find the manifest JSON on stdout (last line that looks like it).
    manifest_line = None
    for line in result.stdout.splitlines():
        line = line.strip()
        if line.startswith("{") and '"schema"' in line:
            manifest_line = line
    if not manifest_line:
        raise HTTPException(status_code=500,
                            detail="no_manifest_on_stdout")
    manifest = _json.loads(manifest_line)

    # Read every SVG inline as base64 so the caller (dealer portal) can
    # embed without another HTTP round-trip. SVGs are ~1-2 KB each so the
    # response body stays small.
    svgs_b64 = {}
    for svg_path_str in manifest.get("artifacts", {}).get("svg", []):
        p = Path(svg_path_str)
        if p.exists():
            svgs_b64[p.stem] = base64.b64encode(p.read_bytes()).decode()

    return {
        "schema": "southbrook.elevation.v1",
        "manifest": manifest,
        "svgs_b64": svgs_b64,
    }


@app.get("/status/{job_id}", dependencies=[Depends(require_secret)])
def status(job_id: str) -> dict:
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="unknown_job")
    return {
        "job_id": job.job_id,
        "status": job.status,
        "production_id": job.spec.production_id,
        "artifacts": list(job.artifacts.keys()),
        "attachment_ids": job.attachment_ids,
        "error": job.error,
    }


# ---------------------------------------------------------------------------
# Background worker
# ---------------------------------------------------------------------------
def _run_render_job(job_id: str) -> None:
    job = JOBS.get(job_id)
    if not job:
        return

    job.status = "rendering"
    logger.info("render starting: job_id=%s", job_id)

    try:
        import json as _json
        import subprocess
        import tempfile

        output_dir = Path(tempfile.mkdtemp(prefix=f"render_{job_id}_"))
        spec_payload = {
            "production_id": job.spec.production_id,
            "dimensions": {
                "width_mm": job.spec.dimensions.width_mm,
                "height_mm": job.spec.dimensions.height_mm,
                "depth_mm": job.spec.dimensions.depth_mm,
            },
            "family": job.spec.family,
            "door_count": job.spec.door_count,
            "output_dir": str(output_dir),
        }
        result = subprocess.run(
            ["freecadcmd", "/app/scripts/render_cabinet.py",
             "--", _json.dumps(spec_payload)],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"freecadcmd exited {result.returncode}: {result.stderr[-500:]}"
            )
        manifest_line = None
        for line in result.stdout.splitlines():
            line = line.strip()
            if line.startswith("{") and '"schema"' in line:
                manifest_line = line
        if not manifest_line:
            raise RuntimeError("render script produced no manifest on stdout")
        manifest = _json.loads(manifest_line)
        job.artifacts = manifest.get("artifacts") or {}
        job.attachment_ids = []
        job.status = "done"
        logger.info("render done: job_id=%s panels=%s",
                    job_id, manifest.get("panel_count"))
    except Exception as exc:
        job.status = "error"
        job.error = str(exc)
        logger.exception("render failed: job_id=%s", job_id)

    # 2026-06-25 — implementation of the Odoo callback (Module 2 phase 2).
    # Gates on ODOO_API_KEY being set; back-compat with prior "deferred"
    # behaviour — if the env var is missing the bridge silently keeps the
    # job locally and Odoo never hears about it (same as before).
    try:
        _post_callback_to_odoo(job)
    except Exception:  # never let the callback crash the worker
        logger.exception("callback to Odoo failed: job_id=%s", job_id)


def _post_callback_to_odoo(job: "JobRecord") -> None:
    """Upload artifacts via XML-RPC, then POST /plm/cad_callback.

    Stdlib-only (xmlrpc.client + urllib.request) — keeps the bridge image
    free of an extra `requests` dependency. The controller side
    (/plm/cad_callback) accepts a list of attachment_ids that this
    function returns; the Odoo controller then writes them onto the MO's
    x_cad_attachment_ids and flips x_cad_status.
    """
    import base64
    import json as _json
    import os
    import urllib.request
    import xmlrpc.client
    from pathlib import Path
    from urllib.error import HTTPError, URLError

    odoo_url = os.environ.get("ODOO_URL", "http://odoo:8069").rstrip("/")
    odoo_db = os.environ.get("ODOO_DB", "southbrook")
    odoo_user = os.environ.get("ODOO_USER", "admin")
    odoo_api_key = os.environ.get("ODOO_API_KEY", "")
    bridge_secret = os.environ.get("FREECAD_BRIDGE_SECRET", "")
    if not odoo_api_key:
        logger.info("ODOO_API_KEY unset — skipping callback for job %s",
                    job.job_id)
        return

    # Step 1 — upload every artifact as an ir.attachment via XML-RPC.
    # We do this even on `error` jobs (manifest may be empty, but the
    # callback still tells Odoo the MO failed).
    attachment_ids = []
    if job.status == "done" and job.artifacts:
        common = xmlrpc.client.ServerProxy(f"{odoo_url}/xmlrpc/2/common")
        try:
            uid = common.authenticate(
                odoo_db, odoo_user, odoo_api_key, {}
            )
        except Exception as exc:  # pragma: no cover — auth failure
            logger.error(
                "XML-RPC authenticate failed for job %s: %s",
                job.job_id, exc,
            )
            uid = None
        if uid:
            models = xmlrpc.client.ServerProxy(
                f"{odoo_url}/xmlrpc/2/object", allow_none=True,
            )
            mimetype_for = {
                "dxf": "application/dxf",
                "svg": "image/svg+xml",
                "step": "model/step",
            }
            # job.artifacts is shape {kind: [path, ...]}.
            for kind, paths in (job.artifacts or {}).items():
                if not isinstance(paths, (list, tuple)):
                    continue
                for raw_path in paths:
                    p = Path(raw_path)
                    if not p.exists():
                        logger.warning(
                            "artifact missing on disk: %s", raw_path,
                        )
                        continue
                    try:
                        with open(p, "rb") as fh:
                            payload_bytes = fh.read()
                        attachment_id = models.execute_kw(
                            odoo_db, uid, odoo_api_key,
                            "ir.attachment", "create", [{
                                "name": p.name,
                                "res_model": "mrp.production",
                                "res_id": job.spec.production_id,
                                "datas": base64.b64encode(payload_bytes).decode("ascii"),
                                "mimetype": mimetype_for.get(kind, "application/octet-stream"),
                            }],
                        )
                        if isinstance(attachment_id, int):
                            attachment_ids.append(attachment_id)
                            logger.info(
                                "uploaded artifact: kind=%s name=%s id=%s",
                                kind, p.name, attachment_id,
                            )
                    except Exception:  # don't stop the loop on one failure
                        logger.exception(
                            "ir.attachment.create failed for %s", p.name,
                        )

    # Step 2 — fire the callback POST. Even on render error we tell
    # Odoo so the MO flips out of `rendering` purgatory.
    callback_payload = {
        "job_id": job.job_id,
        "production_id": job.spec.production_id,
        "status": job.status if job.status in ("done", "error") else "error",
        "attachment_ids": attachment_ids,
    }
    if job.error:
        callback_payload["error"] = str(job.error)[:1000]
    body = _json.dumps(callback_payload).encode("utf-8")
    req = urllib.request.Request(
        f"{odoo_url}/plm/cad_callback",
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Bridge-Secret": bridge_secret,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp_body = resp.read().decode("utf-8", "replace")
            logger.info(
                "callback delivered: job_id=%s status=%s http=%s body=%s",
                job.job_id, callback_payload["status"], resp.status,
                resp_body[:200],
            )
    except HTTPError as exc:
        logger.error(
            "callback HTTP %s for job %s: %s",
            exc.code, job.job_id, exc.read()[:300],
        )
    except URLError as exc:
        logger.error(
            "callback URL error for job %s: %s",
            job.job_id, exc.reason,
        )
