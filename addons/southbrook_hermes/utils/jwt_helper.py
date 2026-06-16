# SPDX-License-Identifier: LGPL-3.0-only
"""JWT minting + verification + persona resolution for Hermes."""
import datetime
import logging

from odoo.exceptions import AccessError

try:
    import jwt as _pyjwt
except ImportError:  # pragma: no cover
    _pyjwt = None

_logger = logging.getLogger(__name__)

DEFAULT_TTL_SECONDS = 60
JWT_ALGORITHM = "HS256"


def _get_secret(env):
    secret = env["ir.config_parameter"].sudo().get_param(
        "southbrook_hermes.jwt_secret")
    if not secret or secret == "PLACEHOLDER_ROTATE_BEFORE_PRODUCTION":
        raise RuntimeError(
            "southbrook_hermes.jwt_secret is not set. Rotate the placeholder "
            "via Settings → Technical → System Parameters before going live.")
    return secret


def mint_jwt(env, *, tenant, persona, partner_id, tier,
             ttl_seconds=DEFAULT_TTL_SECONDS, extra=None):
    """Mint a short-lived JWT carrying tenant, persona, partner_id, and tier.

    `extra` is merged into the claims (e.g. {"order_id": 235}).
    """
    if _pyjwt is None:
        raise RuntimeError("PyJWT not installed. Add 'jwt' to external_dependencies.")
    now = datetime.datetime.utcnow()
    payload = {
        "iat": int(now.timestamp()),
        "exp": int((now + datetime.timedelta(seconds=ttl_seconds)).timestamp()),
        "tenant": tenant,
        "persona": persona,
        "partner_id": partner_id,
        "tier": tier,
    }
    if extra:
        payload.update(extra)
    return _pyjwt.encode(payload, _get_secret(env), algorithm=JWT_ALGORITHM)


def verify_jwt(env, token):
    """Verify a JWT and return its decoded claims dict. Raises on bad sig or expired."""
    if _pyjwt is None:
        raise RuntimeError("PyJWT not installed.")
    return _pyjwt.decode(token, _get_secret(env), algorithms=[JWT_ALGORITHM])


def resolve_persona(user):
    """Map a res.users record to a Hermes persona string.

    v1.0 ships trade_partner only; sales_rep + mfg_manager will resolve in
    v1.1 and v1.2. If a user matches none, raise AccessError so the proxy
    controller can return 403.
    """
    if user.share:
        return "trade_partner"
    if user.has_group("sales_team.group_sale_salesman"):
        return "sales_rep"
    if user.has_group("southbrook_kitchen_workspace.group_kitchen_ops"):
        return "mfg_manager"
    raise AccessError("Hermes is not available for this user role.")


def tier_for_persona(persona):
    """Default tier mask per persona. Trade partners get T0+T1 — T2 routes to recommendations."""
    return {
        "trade_partner": "T0+T1",
        "sales_rep": "T0+T1+T2",
        "mfg_manager": "T0+T1+T2",
    }.get(persona, "T0")
