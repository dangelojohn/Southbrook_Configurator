# SPDX-License-Identifier: LGPL-3.0-only
"""Smoke tests for the KitchenForge SDK.

Uses requests-mock to stub the Odoo agent endpoints; verifies the SDK
shapes payloads correctly, sends headers, decodes results.
"""
from __future__ import annotations

import json
import uuid

import pytest
import requests_mock

from kitchenforge import (
    ApiError,
    KitchenForgeClient,
    NotFoundError,
    PreconditionFailedError,
)


BASE = "https://kf.test"
KEY = "kfk-test-abcd"


def _client() -> KitchenForgeClient:
    return KitchenForgeClient(BASE, KEY)


# ----------------------------------------------------------------------
# Tools
# ----------------------------------------------------------------------
def test_instantiate_happy_path():
    with requests_mock.Mocker() as m:
        m.post(
            f"{BASE}/agent/v1/tools/instantiate",
            json={
                "ok": True,
                "project_id": 137,
                "project_path": "/projects/137.yaml",
                "sale_order_id": 412,
                "sale_order_name": "S00412",
                "quote_path": "/projects/137/quote.yaml",
                "schema": "southbrook.flutter.api.v1",
            },
        )
        kf = _client()
        result = kf.tools.instantiate(
            template_id=7, partner_id=42,
            dims={"room_width_mm": 4200},
        )
        assert result.ok is True
        assert result.project_id == 137
        assert result.sale_order_name == "S00412"
        req = m.last_request
        assert req.headers["X-Api-Key"] == KEY
        # SDK auto-generated an idempotency key.
        assert "Idempotency-Key" in req.headers
        # And it parses as a UUID.
        uuid.UUID(req.headers["Idempotency-Key"])
        body = req.json()
        assert body["template_id"] == 7
        assert body["partner_id"] == 42
        assert body["dims"] == {"room_width_mm": 4200}


def test_instantiate_caller_idempotency_key_preserved():
    with requests_mock.Mocker() as m:
        m.post(
            f"{BASE}/agent/v1/tools/instantiate",
            json={
                "ok": True, "project_id": 1, "project_path": "/p/1.yaml",
                "sale_order_id": 2, "sale_order_name": "S2",
                "quote_path": "/p/1/q.yaml",
            },
        )
        kf = _client()
        kf.tools.instantiate(
            template_id=7, partner_id=42,
            idempotency_key="caller-supplied-key-xyz",
        )
        assert m.last_request.headers["Idempotency-Key"] == "caller-supplied-key-xyz"


def test_add_zone_shapes_payload():
    with requests_mock.Mocker() as m:
        m.post(
            f"{BASE}/agent/v1/tools/add_zone",
            json={"ok": True, "project_id": 137,
                  "zones_path": "/projects/137/zones",
                  "line_count": 3},
        )
        kf = _client()
        zone = {"product_id": 311, "width_mm": 900, "quantity": 2}
        result = kf.tools.add_zone(project_id=137, zone=zone)
        assert result.line_count == 3
        body = m.last_request.json()
        assert body == {"project_id": 137, "zone": zone}


def test_confirm_quote_already_confirmed():
    with requests_mock.Mocker() as m:
        m.post(
            f"{BASE}/agent/v1/tools/confirm_quote",
            json={"ok": True, "already_confirmed": True,
                  "sale_order": "S00412"},
        )
        kf = _client()
        result = kf.tools.confirm_quote(project_id=137)
        assert result.already_confirmed is True
        assert result.sale_order == "S00412"


def test_release_mos_returns_typed_list():
    with requests_mock.Mocker() as m:
        m.post(
            f"{BASE}/agent/v1/tools/release_mos",
            json={"ok": True, "released_count": 2, "mos": [
                {"id": 901, "name": "MO/00901", "state": "confirmed"},
                {"id": 902, "name": "MO/00902", "state": "confirmed"},
            ]},
        )
        kf = _client()
        result = kf.tools.release_mos(project_id=137)
        assert result.released_count == 2
        assert result.mos[0]["name"] == "MO/00901"


def test_raise_eco_optional_fields():
    with requests_mock.Mocker() as m:
        m.post(
            f"{BASE}/agent/v1/tools/raise_eco",
            json={"ok": True, "eco_id": 55, "stage": "Draft",
                  "requires_approver": True},
        )
        kf = _client()
        result = kf.tools.raise_eco(
            title="Swap hinges",
            reason="Soft-close not stocked",
            project_id=137,
        )
        assert result.eco_id == 55
        body = m.last_request.json()
        assert "target_bom_id" not in body  # omitted -> not sent
        assert body["title"] == "Swap hinges"


# ----------------------------------------------------------------------
# Filesystem
# ----------------------------------------------------------------------
def test_fs_get_root():
    with requests_mock.Mocker() as m:
        m.get(
            f"{BASE}/agent/v1/files",
            json={"kind": "dir", "path": "/", "schema": "kitchenforge.agent.fs.v1",
                  "entries": []},
        )
        kf = _client()
        listing = kf.fs_get()
        assert listing["kind"] == "dir"


def test_fs_get_nested_path_encoded():
    with requests_mock.Mocker() as m:
        m.get(
            f"{BASE}/agent/v1/files/templates/full-kitchen.yaml",
            json={"kind": "file", "path": "/templates/full-kitchen.yaml",
                  "etag": "abc", "schema": "kitchenforge.agent.fs.v1",
                  "content": {"name": "Full Kitchen"}},
            headers={"ETag": "abc"},
        )
        kf = _client()
        f = kf.fs_get("templates/full-kitchen.yaml")
        assert f["content"]["name"] == "Full Kitchen"


def test_fs_put_with_if_match():
    with requests_mock.Mocker() as m:
        m.put(
            f"{BASE}/agent/v1/files/projects/137/zones/001-base-30.yaml",
            json={"kind": "file",
                  "path": "/projects/137/zones/001-base-30.yaml",
                  "etag": "new-etag",
                  "schema": "kitchenforge.agent.fs.v1",
                  "content": {"quantity": 2}},
        )
        kf = _client()
        kf.fs_put(
            "projects/137/zones/001-base-30.yaml",
            {"quantity": 2},
            if_match="old-etag",
        )
        assert m.last_request.headers["If-Match"] == "old-etag"
        assert "Idempotency-Key" in m.last_request.headers


def test_fs_head_returns_etag():
    with requests_mock.Mocker() as m:
        m.head(
            f"{BASE}/agent/v1/files/projects/137.yaml",
            headers={"ETag": "proj-etag"},
        )
        kf = _client()
        assert kf.fs_head("projects/137.yaml") == "proj-etag"


def test_fs_head_404_returns_none():
    with requests_mock.Mocker() as m:
        m.head(
            f"{BASE}/agent/v1/files/projects/99999.yaml",
            status_code=404,
        )
        kf = _client()
        assert kf.fs_head("projects/99999.yaml") is None


# ----------------------------------------------------------------------
# Marathon
# ----------------------------------------------------------------------
def test_marathon_telemetry_limit_param():
    with requests_mock.Mocker() as m:
        m.get(
            f"{BASE}/agent/v1/marathon/telemetry",
            json={"schema": "kitchenforge.marathon.telemetry.v1",
                  "tenant": "alfacore-prod", "count": 0, "events": []},
        )
        kf = _client()
        kf.marathon.telemetry(limit=50)
        assert m.last_request.qs["limit"] == ["50"]


def test_marathon_rebates_period_param():
    with requests_mock.Mocker() as m:
        m.get(
            f"{BASE}/agent/v1/marathon/rebates",
            json={"schema": "kitchenforge.marathon.rebates.v1",
                  "tenant": "alfacore-prod", "summary": {}},
        )
        kf = _client()
        kf.marathon.rebates(period="2026-05")
        assert m.last_request.qs["period"] == ["2026-05"]


# ----------------------------------------------------------------------
# Errors
# ----------------------------------------------------------------------
def test_404_raises_not_found_error():
    with requests_mock.Mocker() as m:
        m.get(
            f"{BASE}/agent/v1/files/templates/missing.yaml",
            status_code=404,
            json={"error": "not_found",
                  "message": "no template matches 'missing'",
                  "schema": "southbrook.flutter.api.v1"},
        )
        kf = _client()
        with pytest.raises(NotFoundError) as exc:
            kf.fs_get("templates/missing.yaml")
        assert exc.value.code == "not_found"
        assert exc.value.status == 404


def test_etag_mismatch_raises_precondition_failed():
    with requests_mock.Mocker() as m:
        m.put(
            f"{BASE}/agent/v1/files/projects/137/zones/001-foo.yaml",
            status_code=409,
            json={"error": "etag_mismatch", "message": "stale",
                  "schema": "southbrook.flutter.api.v1"},
        )
        kf = _client()
        with pytest.raises(PreconditionFailedError):
            kf.fs_put(
                "projects/137/zones/001-foo.yaml",
                {"quantity": 1}, if_match="stale-etag",
            )


def test_invalid_api_key_raises_api_error():
    with requests_mock.Mocker() as m:
        m.post(
            f"{BASE}/agent/v1/tools/confirm_quote",
            status_code=401,
            json={"error": "invalid_api_key",
                  "message": "Missing or invalid X-Api-Key header.",
                  "schema": "southbrook.flutter.api.v1"},
        )
        kf = _client()
        with pytest.raises(ApiError) as exc:
            kf.tools.confirm_quote(project_id=137)
        assert exc.value.status == 401
        assert exc.value.code == "invalid_api_key"


# ----------------------------------------------------------------------
# Manifest
# ----------------------------------------------------------------------
def test_manifest_no_auth():
    with requests_mock.Mocker() as m:
        m.get(
            f"{BASE}/.well-known/ai-agent.json",
            json={"schema_version": "v1", "name_for_model": "kitchenforge",
                  "auth": {"type": "api_key", "header_name": "X-Api-Key"},
                  "filesystem": {"base_url": f"{BASE}/agent/v1/files",
                                  "verbs": ["GET", "PUT", "HEAD"]},
                  "tools_url": f"{BASE}/agent/v1/tools"},
        )
        kf = _client()
        m_data = kf.manifest()
        assert m_data["name_for_model"] == "kitchenforge"


# ----------------------------------------------------------------------
# Context-manager close
# ----------------------------------------------------------------------
def test_context_manager_closes_session():
    with KitchenForgeClient(BASE, KEY) as kf:
        assert kf.api_key == KEY
