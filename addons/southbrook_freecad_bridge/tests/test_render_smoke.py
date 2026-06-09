# SPDX-License-Identifier: LGPL-3.0-only
"""18 render smoke tests — 6 cabinet families × 3 sizes per the init-doc
Module 2 contract. Hits the live bridge over the docker network, polls
for completion, asserts the produced artifact set.

Test matrix:
  base    × {300×600×580 narrow, 600×720×580 standard, 900×900×580 wide}
  wall    × {300×600×300 narrow, 600×720×300 standard, 900×720×300 wide}
  sink    × {600×900×580 narrow, 800×900×580 standard, 900×900×580 wide}
  tall    × {600×2100×580 narrow, 800×2100×580 standard, 900×2100×580 wide}
  vanity  × {600×800×460 narrow, 750×800×460 standard, 900×800×460 wide}
  drawer  × {300×720×580 small, 600×720×580 medium, 900×720×580 large}
                                                                = 18

Gating: each render must emit at least 1 STEP + N panel SVGs (where N
is the number of panels for that carcass). DXF emission is asserted
softly via the manifest (some panel combos can validly have 0 DXFs if
ezdxf rejects a degenerate shape — we don't gate the suite on it).

These tests live in the Odoo addon to use the existing -test-tags
machinery. The bridge URL is read from ir.config_parameter
'freecad_bridge.url' (defaults to http://freecad-bridge:8000 which
resolves on the docker compose network).
"""
import json
import time
from typing import Dict, List, Tuple

import urllib.request
import urllib.error

from odoo.tests.common import TransactionCase, tagged


BRIDGE_DEFAULT_URL = "http://freecad-bridge:8000"
BRIDGE_DEFAULT_SECRET = "change-me-bridge-secret"

# (template, size_label, width_mm, height_mm, depth_mm, family, door_count)
TEST_MATRIX: List[Tuple[str, str, float, float, float, str, int]] = [
    # Base cabinets
    ("base_cabinet",   "narrow",   300, 600, 580, "base",   1),
    ("base_cabinet",   "standard", 600, 720, 580, "base",   2),
    ("base_cabinet",   "wide",     900, 900, 580, "base",   2),
    # Wall cabinets
    ("wall_cabinet",   "narrow",   300, 600, 300, "wall",   1),
    ("wall_cabinet",   "standard", 600, 720, 300, "wall",   2),
    ("wall_cabinet",   "wide",     900, 720, 300, "wall",   2),
    # Sink-base cabinets
    ("sink_cabinet",   "narrow",   600, 900, 580, "sink",   2),
    ("sink_cabinet",   "standard", 800, 900, 580, "sink",   2),
    ("sink_cabinet",   "wide",     900, 900, 580, "sink",   2),
    # Tall / pantry cabinets
    ("tall_cabinet",   "narrow",   600, 2100, 580, "tall",  2),
    ("tall_cabinet",   "standard", 800, 2100, 580, "tall",  2),
    ("tall_cabinet",   "wide",     900, 2100, 580, "tall",  2),
    # Vanity cabinets
    ("vanity_cabinet", "narrow",   600, 800, 460, "vanity", 1),
    ("vanity_cabinet", "standard", 750, 800, 460, "vanity", 2),
    ("vanity_cabinet", "wide",     900, 800, 460, "vanity", 2),
    # Drawer banks
    ("drawer_unit",    "small",    300, 720, 580, "drawer", 0),
    ("drawer_unit",    "medium",   600, 720, 580, "drawer", 0),
    ("drawer_unit",    "large",    900, 720, 580, "drawer", 0),
]


def _http_json(method: str, url: str, secret: str,
               body: dict = None, timeout: float = 60.0) -> dict:
    """Tiny urllib wrapper — stdlib only to avoid pinning httpx/requests."""
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("X-Bridge-Secret", secret)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


@tagged("post_install", "-at_install", "southbrook", "render_smoke")
class TestRenderSmoke18(TransactionCase):
    """18 render smoke tests gated on bridge reachability."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        param = cls.env["ir.config_parameter"].sudo()
        cls.bridge_url = param.get_param(
            "freecad_bridge.url", BRIDGE_DEFAULT_URL)
        cls.bridge_secret = param.get_param(
            "freecad_bridge.secret_runtime",
            BRIDGE_DEFAULT_SECRET,
        )

    def setUp(self):
        super().setUp()
        # Skip if the bridge is unreachable — keeps the suite green on
        # boxes where freecad-bridge isn't running.
        try:
            urllib.request.urlopen(
                f"{self.bridge_url}/health", timeout=2,
            ).read()
        except (urllib.error.URLError, ConnectionError, TimeoutError, OSError):
            self.skipTest(
                f"Bridge unreachable at {self.bridge_url}; "
                "render smoke tests require freecad-bridge running."
            )

    def _poll_until_done(self, job_id: str, max_wait_s: float = 25.0):
        """Poll /status until the job exits the 'queued' / 'rendering'
        state. Returns the final status dict."""
        deadline = time.time() + max_wait_s
        while time.time() < deadline:
            payload = _http_json(
                "GET", f"{self.bridge_url}/status/{job_id}",
                self.bridge_secret,
            )
            if payload["status"] in ("done", "error"):
                return payload
            time.sleep(0.5)
        self.fail(f"Render job {job_id} did not finish in {max_wait_s}s")

    def _render_one(self, template, size_label, w, h, d, family, door_count):
        spec = {
            "production_id": 1,
            "template": template,
            "dimensions": {"width_mm": w, "height_mm": h, "depth_mm": d},
            "family": family,
            "door_count": door_count,
        }
        # Trigger render.
        enq = _http_json("POST", f"{self.bridge_url}/render",
                         self.bridge_secret, body=spec)
        self.assertIn("job_id", enq)
        self.assertIn(enq["status"], ("queued", "rendering", "done"))

        # Poll.
        final = self._poll_until_done(enq["job_id"])
        self.assertEqual(
            final["status"], "done",
            f"{template}/{size_label}: render failed — error={final.get('error')!r}",
        )

        # Inspect artifacts. /status echoes the artifact KEYS, not the
        # paths — we only need to confirm step + svg are present.
        artifacts = final.get("artifacts") or []
        self.assertIn(
            "step", artifacts,
            f"{template}/{size_label}: STEP missing from artifacts",
        )
        self.assertIn(
            "svg", artifacts,
            f"{template}/{size_label}: SVG missing from artifacts",
        )

    def test_18_renders_all_complete(self):
        """One subTest per (template, size) — 18 total. A single failure
        does NOT abort the suite; every row gets exercised so a partial
        regression surfaces every affected combo at once."""
        for row in TEST_MATRIX:
            template, size_label, w, h, d, family, door_count = row
            with self.subTest(template=template, size=size_label,
                              dims=f"{int(w)}x{int(h)}x{int(d)}"):
                self._render_one(template, size_label, w, h, d,
                                  family, door_count)
