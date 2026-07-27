# SPDX-License-Identifier: LGPL-3.0-only
import json
from urllib import error, request


def build_recommendation_payload(
    name,
    summary,
    recommendation_type="note",
    priority="normal",
    rationale=None,
    proposed_action=None,
    payload=None,
    source_model=None,
    source_res_id=None,
    agent_run_id=None,
    model_provider=None,
    model_name=None,
):
    if not name or not summary:
        raise ValueError("name and summary are required.")
    return {
        "name": name,
        "summary": summary,
        "recommendation_type": recommendation_type,
        "priority": priority,
        "rationale": rationale,
        "proposed_action": proposed_action,
        "payload": payload or {},
        "source_model": source_model,
        "source_res_id": source_res_id,
        "agent_run_id": agent_run_id,
        "model_provider": model_provider,
        "model_name": model_name,
    }


class UrllibTransport:

    def __init__(self, timeout_seconds=30):
        self.timeout_seconds = timeout_seconds

    def post_json(self, url, payload, headers):
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(url, data=body, headers=headers, method="POST")
        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as resp:
                data = resp.read().decode("utf-8")
                return json.loads(data) if data else {}
        except error.HTTPError as exc:
            body = exc.read().decode("utf-8")
            raise RuntimeError(f"Odoo returned HTTP {exc.code}: {body}") from exc


class HermesOdooClient:

    def __init__(self, config, transport=None):
        self.config = config
        self.transport = transport or UrllibTransport(config.timeout_seconds)

    def create_recommendation(self, payload):
        url = (
            self.config.odoo_base_url.rstrip("/")
            + "/hermes/api/v1/recommendations"
        )
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Api-Key": self.config.odoo_api_key,
        }
        return self.transport.post_json(url, payload, headers)
