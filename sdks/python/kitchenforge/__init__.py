# SPDX-License-Identifier: LGPL-3.0-only
"""KitchenForge Python SDK — typed client for the Odoo 19 agent surface."""
from .client import (
    KitchenForgeClient,
    KitchenForgeError,
    ApiError,
    NotFoundError,
    PreconditionFailedError,
    InstantiateResult,
    AddZoneResult,
    ConfirmQuoteResult,
    ReleaseMosResult,
    RaiseEcoResult,
)

__all__ = [
    "KitchenForgeClient",
    "KitchenForgeError",
    "ApiError",
    "NotFoundError",
    "PreconditionFailedError",
    "InstantiateResult",
    "AddZoneResult",
    "ConfirmQuoteResult",
    "ReleaseMosResult",
    "RaiseEcoResult",
]

__version__ = "0.1.0"
