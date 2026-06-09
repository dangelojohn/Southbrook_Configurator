# SPDX-License-Identifier: LGPL-3.0-only
"""SAMI / Southbrook — FreeCAD bridge (Module 0 skeleton).

Only /health is implemented at Module 0. Module 2 fills in:
  POST /render             — async render job (returns job_id)
  GET  /status/{job_id}    — poll a job's state
  POST /validate           — geometric pre-check on a render spec
  GET  /templates          — list available FreeCAD .FCStd templates

The shared secret in the X-Bridge-Secret header is the auth scheme. Module 0
parses the env var but does not enforce it on /health (intentional — /health
must work without secrets so liveness/orchestrator probes can use it).
"""
from __future__ import annotations

import os

from fastapi import FastAPI

app = FastAPI(title="SAMI FreeCAD Bridge", version="0.0.0")

# Read at import time; later endpoints will validate this on every call.
BRIDGE_SECRET = os.environ.get("FREECAD_BRIDGE_SECRET", "")


@app.get("/health")
def health() -> dict:
    """Liveness probe. Does not require the shared secret."""
    return {
        "status": "ok",
        "module": "freecad_bridge",
        "phase": "module-0-skeleton",
        "secret_configured": bool(BRIDGE_SECRET),
    }
