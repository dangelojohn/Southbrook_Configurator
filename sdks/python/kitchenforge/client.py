# SPDX-License-Identifier: LGPL-3.0-only
"""KitchenForge HTTP client.

Pure-Python wrapper over `/agent/v1/...`. Uses `requests`; the dependency is
declared in pyproject.toml. Idempotency keys are auto-generated as `uuid4()`
unless the caller passes one in. All writes accept an optional `if_match`
ETag for concurrency control.

Surface:

    client = KitchenForgeClient("https://southbrookcabinetry.space", "kfk-...")
    listing = client.fs_get("templates")
    proj = client.tools.instantiate(template_id=7, partner_id=42)
    client.tools.confirm_quote(project_id=proj["project_id"])
    client.tools.release_mos(project_id=proj["project_id"])
    events = client.marathon.telemetry(limit=100)
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union
from urllib.parse import quote

import requests


# ----------------------------------------------------------------------
# Errors
# ----------------------------------------------------------------------
class KitchenForgeError(Exception):
    """Base class for SDK errors."""


class ApiError(KitchenForgeError):
    """Server returned a 4xx/5xx error envelope."""

    def __init__(self, status: int, code: str, message: str,
                 details: Optional[dict] = None):
        self.status = status
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(f"[{status} {code}] {message}")


class NotFoundError(ApiError):
    """HTTP 404."""


class PreconditionFailedError(ApiError):
    """HTTP 412 / ETag mismatch."""


# ----------------------------------------------------------------------
# Tool results (typed dicts via dataclasses; convertible from server JSON)
# ----------------------------------------------------------------------
@dataclass
class InstantiateResult:
    ok: bool
    project_id: int
    project_path: str
    sale_order_id: int
    sale_order_name: str
    quote_path: str
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AddZoneResult:
    ok: bool
    project_id: int
    zones_path: str
    line_count: int
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConfirmQuoteResult:
    ok: bool
    sale_order: Optional[str] = None
    state: Optional[str] = None
    mo_path: Optional[str] = None
    already_confirmed: bool = False
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ReleaseMosResult:
    ok: bool
    released_count: int
    mos: List[Dict[str, Any]]
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RaiseEcoResult:
    ok: bool
    eco_id: int
    stage: Optional[str]
    requires_approver: bool
    raw: Dict[str, Any] = field(default_factory=dict)


# ----------------------------------------------------------------------
# Internal helpers
# ----------------------------------------------------------------------
def _idem(idempotency_key: Optional[str]) -> str:
    return idempotency_key or str(uuid.uuid4())


def _raise_for_envelope(resp: requests.Response) -> Dict[str, Any]:
    """Decode JSON; if status >= 400, raise the matching ApiError subclass."""
    try:
        body = resp.json()
    except ValueError:
        body = {"error": "non_json", "message": resp.text[:500]}
    if resp.status_code >= 400:
        code = body.get("error", "unknown")
        msg = body.get("message", "")
        details = body.get("details")
        if resp.status_code == 404:
            raise NotFoundError(resp.status_code, code, msg, details)
        if resp.status_code in (409, 412):
            raise PreconditionFailedError(resp.status_code, code, msg, details)
        raise ApiError(resp.status_code, code, msg, details)
    return body


def _encode_fs_path(path: str) -> str:
    path = (path or "").lstrip("/")
    # Preserve slashes between segments, encode the rest.
    return "/".join(quote(seg, safe="") for seg in path.split("/") if seg != "")


# ----------------------------------------------------------------------
# Sub-clients
# ----------------------------------------------------------------------
class _ToolsClient:
    def __init__(self, parent: "KitchenForgeClient"):
        self._p = parent

    def list(self) -> Dict[str, Any]:
        """Fetch the JSON-Schema tool catalog."""
        return self._p._request("GET", "/agent/v1/tools")

    def instantiate(self, *, template_id: int, partner_id: int,
                    dims: Optional[Dict[str, int]] = None,
                    target_date: Optional[str] = None,
                    idempotency_key: Optional[str] = None
                    ) -> InstantiateResult:
        body = {"template_id": template_id, "partner_id": partner_id}
        if dims:
            body["dims"] = dims
        if target_date:
            body["target_date"] = target_date
        data = self._p._request(
            "POST", "/agent/v1/tools/instantiate",
            json_body=body, idempotency_key=_idem(idempotency_key))
        return InstantiateResult(
            ok=data.get("ok", False),
            project_id=data["project_id"],
            project_path=data["project_path"],
            sale_order_id=data["sale_order_id"],
            sale_order_name=data["sale_order_name"],
            quote_path=data["quote_path"],
            raw=data,
        )

    def add_zone(self, *, project_id: int, zone: Dict[str, Any],
                 idempotency_key: Optional[str] = None) -> AddZoneResult:
        body = {"project_id": project_id, "zone": zone}
        data = self._p._request(
            "POST", "/agent/v1/tools/add_zone",
            json_body=body, idempotency_key=_idem(idempotency_key))
        return AddZoneResult(
            ok=data.get("ok", False),
            project_id=data["project_id"],
            zones_path=data["zones_path"],
            line_count=data["line_count"],
            raw=data,
        )

    def confirm_quote(self, *, project_id: int,
                      idempotency_key: Optional[str] = None
                      ) -> ConfirmQuoteResult:
        data = self._p._request(
            "POST", "/agent/v1/tools/confirm_quote",
            json_body={"project_id": project_id},
            idempotency_key=_idem(idempotency_key))
        return ConfirmQuoteResult(
            ok=data.get("ok", False),
            sale_order=data.get("sale_order"),
            state=data.get("state"),
            mo_path=data.get("mo_path"),
            already_confirmed=data.get("already_confirmed", False),
            raw=data,
        )

    def release_mos(self, *, project_id: int,
                    idempotency_key: Optional[str] = None
                    ) -> ReleaseMosResult:
        data = self._p._request(
            "POST", "/agent/v1/tools/release_mos",
            json_body={"project_id": project_id},
            idempotency_key=_idem(idempotency_key))
        return ReleaseMosResult(
            ok=data.get("ok", False),
            released_count=data.get("released_count", 0),
            mos=data.get("mos", []),
            raw=data,
        )

    def raise_eco(self, *, title: str, reason: Optional[str] = None,
                  project_id: Optional[int] = None,
                  target_bom_id: Optional[int] = None,
                  idempotency_key: Optional[str] = None) -> RaiseEcoResult:
        body: Dict[str, Any] = {"title": title}
        if reason is not None:
            body["reason"] = reason
        if project_id is not None:
            body["project_id"] = project_id
        if target_bom_id is not None:
            body["target_bom_id"] = target_bom_id
        data = self._p._request(
            "POST", "/agent/v1/tools/raise_eco",
            json_body=body, idempotency_key=_idem(idempotency_key))
        return RaiseEcoResult(
            ok=data.get("ok", False),
            eco_id=data["eco_id"],
            stage=data.get("stage"),
            requires_approver=data.get("requires_approver", True),
            raw=data,
        )


class _MarathonClient:
    def __init__(self, parent: "KitchenForgeClient"):
        self._p = parent

    def telemetry(self, limit: int = 200) -> Dict[str, Any]:
        return self._p._request(
            "GET", "/agent/v1/marathon/telemetry",
            params={"limit": limit})

    def rebates(self, period: Optional[str] = None) -> Dict[str, Any]:
        params: Dict[str, Any] = {}
        if period:
            params["period"] = period
        return self._p._request(
            "GET", "/agent/v1/marathon/rebates", params=params)


# ----------------------------------------------------------------------
# Main client
# ----------------------------------------------------------------------
class KitchenForgeClient:
    """Synchronous HTTP client for the KitchenForge agent surface.

    Args:
        base_url: e.g. "https://southbrookcabinetry.space" (no trailing slash needed)
        api_key:  per-user API key from Settings -> Users -> API Keys.
        timeout:  per-request timeout in seconds.
        session:  optional pre-configured `requests.Session`.
    """

    def __init__(self, base_url: str, api_key: str,
                 timeout: float = 30.0,
                 session: Optional[requests.Session] = None):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self._session = session or requests.Session()
        self.tools = _ToolsClient(self)
        self.marathon = _MarathonClient(self)

    # -- low-level -------------------------------------------------------
    def _request(self, method: str, path: str,
                 json_body: Any = None,
                 params: Optional[Dict[str, Any]] = None,
                 idempotency_key: Optional[str] = None,
                 if_match: Optional[str] = None,
                 raw_body: Optional[bytes] = None,
                 extra_headers: Optional[Dict[str, str]] = None,
                 expect_json: bool = True) -> Any:
        url = f"{self.base_url}{path}"
        headers = {"X-Api-Key": self.api_key, "Accept": "application/json"}
        if json_body is not None or raw_body is not None:
            headers["Content-Type"] = "application/json"
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        if if_match:
            headers["If-Match"] = if_match
        if extra_headers:
            headers.update(extra_headers)

        data: Optional[bytes] = raw_body
        if json_body is not None and raw_body is None:
            data = json.dumps(json_body).encode("utf-8")

        resp = self._session.request(
            method, url, headers=headers, params=params, data=data,
            timeout=self.timeout)
        if not expect_json:
            return resp
        return _raise_for_envelope(resp)

    # -- manifest --------------------------------------------------------
    def manifest(self) -> Dict[str, Any]:
        """GET /.well-known/ai-agent.json (no auth)."""
        url = f"{self.base_url}/.well-known/ai-agent.json"
        resp = self._session.get(url, timeout=self.timeout)
        return _raise_for_envelope(resp)

    # -- filesystem ------------------------------------------------------
    def fs_get(self, path: str = "") -> Dict[str, Any]:
        """GET /agent/v1/files/<path>. Returns a dir listing or file payload."""
        return self._request("GET", self._fs_url(path))

    def fs_put(self, path: str, body: Dict[str, Any],
               if_match: Optional[str] = None,
               idempotency_key: Optional[str] = None) -> Dict[str, Any]:
        """PUT /agent/v1/files/<path>. Returns the new file representation."""
        return self._request(
            "PUT", self._fs_url(path), json_body=body,
            if_match=if_match, idempotency_key=_idem(idempotency_key))

    def fs_head(self, path: str) -> Optional[str]:
        """HEAD /agent/v1/files/<path>. Returns the ETag (or None if missing)."""
        resp = self._request(
            "HEAD", self._fs_url(path), expect_json=False)
        if resp.status_code == 404:
            return None
        if resp.status_code >= 400:
            raise ApiError(resp.status_code, "head_failed", resp.text[:200])
        return resp.headers.get("ETag")

    def _fs_url(self, path: str) -> str:
        encoded = _encode_fs_path(path)
        if not encoded:
            return "/agent/v1/files"
        return f"/agent/v1/files/{encoded}"

    # -- context-manager convenience ------------------------------------
    def close(self) -> None:
        self._session.close()

    def __enter__(self) -> "KitchenForgeClient":
        return self

    def __exit__(self, *_exc: Any) -> None:
        self.close()
