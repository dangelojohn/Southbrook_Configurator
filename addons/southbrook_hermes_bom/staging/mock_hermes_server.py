# SPDX-License-Identifier: LGPL-3.0-only
"""Tiny Hermes mock server for staging integration tests.

This is NOT the real Hermes endpoint — it's a stand-in that returns a
deterministic, hermes-shaped JSON response so a developer (or an
automated end-to-end test) can exercise the southbrook_hermes_bom
wizard against a real HTTP socket instead of a unittest.mock patch.

Run standalone:

    python3 staging/mock_hermes_server.py --port 7100 --token TEST-KEY

Configure southbrook_hermes_bom against it (admin shell):

    env['ir.config_parameter'].sudo().set_param(
        'southbrook_hermes_bom.api_key', 'TEST-KEY')
    env['ir.config_parameter'].sudo().set_param(
        'southbrook_hermes_bom.endpoint',
        'http://127.0.0.1:7100/v1/research')

Then open any Configurable Template, click "Research & Build BOM with
Hermes", run the wizard, and the dispatch hits THIS server instead of
the real (unconfigured) Hermes service.

The server inspects the inbound payload and tailors the canned
response so the smoke trace is interesting (proposed_name echoes the
real product name, BOM lines pick the first two component-shaped
products it can see referenced in the payload's existing_boms).

Dependency: standard library only — no Flask, no FastAPI. Bound to
loopback by default so the staging mock can never be exposed
accidentally.
"""
import argparse
import json
import logging
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

_logger = logging.getLogger("hermes_mock")


CANNED_BOM_LINES = [
    {"sku": "HBOM-MOCK-A", "name": "Mock Component A", "qty": 2.0},
    {"sku": "HBOM-MOCK-B", "name": "Mock Component B", "qty": 1.0},
]


def _build_response(payload):
    """Tailor the canned response to the inbound payload.

    Echos `product_name` back into the proposed name so the wizard's
    'current vs proposed' view shows something familiar. Picks the
    first ATTRIBUTE_LINES attribute values for proposed_specs so the
    Specs page also renders something product-specific.
    """
    name = (payload.get("product_name") or "Hermes-Researched Item").strip()
    attr_lines = payload.get("attribute_lines") or []
    specs = []
    for line in attr_lines[:5]:
        if not isinstance(line, dict):
            continue
        attr = line.get("attribute_name") or ""
        values = line.get("values") or []
        if attr and values:
            specs.append({"name": attr, "value": ", ".join(map(str, values))})

    dims = []
    if payload.get("southbrook_dimensions"):
        dims.append({
            "label": "Catalog dimension",
            "value": payload["southbrook_dimensions"],
        })
    dims.extend([
        {"label": "Width", "value": "18\""},
        {"label": "Depth", "value": "24\""},
    ])

    return {
        "product_enrichment": {
            "name": "%s (Hermes-enriched)" % name,
            "short_description": (
                "Mock-research summary for %s. Replace with a real "
                "Hermes deployment when one is online." % name
            ),
            "long_description": (
                "<p><b>%s</b> — mock-enrichment narrative.</p>"
                "<p>Source: staging mock server.</p>"
            ) % name,
            "technical_description": (
                "Body, hardware, and accessories assembled per "
                "Southbrook spec book convention."
            ),
            "manufacturer": "Marathon Hardware (mock)",
            "manufacturer_pn": payload.get("marathon_sku") or "MK-MOCK-001",
            "dimensions": dims,
            "specs": specs,
            "install_notes": [
                {"text": "Pre-drill before fastening (mock note)."},
                {"text": "Mock note 2: align to grid."},
            ],
        },
        "bom": {
            "bom_type": "normal",
            "lines": CANNED_BOM_LINES,
        },
        "audit": {
            "source_urls": [
                "https://mock.example.com/datasheet.pdf",
                {"url": "https://mock.example.com/install-guide",
                 "label": "Install guide"},
            ],
            "overall_confidence": 0.91,
        },
    }


def make_handler(expected_token):
    """Closure so the handler class can read the expected bearer token."""

    class MockHermesHandler(BaseHTTPRequestHandler):

        # Keep stdout uncluttered — log via the module logger instead.
        def log_message(self, fmt, *args):  # noqa: D401
            _logger.info("%s - %s", self.address_string(), fmt % args)

        def _reply(self, status, body, ctype="application/json"):
            data = body if isinstance(body, bytes) else body.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.path == "/health":
                self._reply(200, json.dumps({"ok": True}))
                return
            self._reply(404, json.dumps({"error": "not found"}))

        def do_POST(self):
            if self.path != "/v1/research":
                self._reply(404, json.dumps({"error": "not found"}))
                return
            auth = self.headers.get("Authorization") or ""
            m = re.match(r"Bearer\s+(\S+)", auth)
            if not m or m.group(1) != expected_token:
                self._reply(401, json.dumps({"error": "unauthorized"}))
                return
            length = int(self.headers.get("Content-Length") or "0")
            raw = self.rfile.read(length) if length else b"{}"
            try:
                payload = json.loads(raw or b"{}")
            except json.JSONDecodeError:
                self._reply(400, json.dumps({"error": "invalid JSON"}))
                return
            response = _build_response(payload)
            _logger.info(
                "research: template=%s name=%r → enriched_name=%r",
                payload.get("product_template_id"),
                payload.get("product_name"),
                response["product_enrichment"]["name"],
            )
            self._reply(200, json.dumps(response))

    return MockHermesHandler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1",
                        help="Bind host (default loopback only — DO NOT "
                             "expose; staging-only).")
    parser.add_argument("--port", type=int, default=7100)
    parser.add_argument("--token", default="TEST-KEY",
                        help="Bearer token the wizard must send.")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    server = ThreadingHTTPServer(
        (args.host, args.port), make_handler(args.token),
    )
    _logger.info(
        "Hermes mock listening on http://%s:%d (token=%s…%s, len=%d)",
        args.host, args.port, args.token[:3],
        args.token[-3:] if len(args.token) > 6 else "***",
        len(args.token),
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        _logger.info("Hermes mock shutting down")
        server.server_close()


if __name__ == "__main__":
    main()
