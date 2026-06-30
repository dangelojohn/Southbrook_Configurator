# SPDX-License-Identifier: LGPL-3.0-only
from dataclasses import dataclass
import os


DEFAULT_MODEL_PROVIDER = "google"
DEFAULT_MODEL_NAME = "gemini-3.5-flash"
DEFAULT_SERVICE_INTERVAL_SECONDS = 300


@dataclass(frozen=True)
class HermesConfig:
    odoo_base_url: str
    odoo_api_key: str
    model_provider: str = DEFAULT_MODEL_PROVIDER
    model_name: str = DEFAULT_MODEL_NAME
    timeout_seconds: int = 30
    service_interval_seconds: int = DEFAULT_SERVICE_INTERVAL_SECONDS


def load_config(env=None):
    source = env or os.environ
    base_url = (source.get("HERMES_ODOO_BASE_URL") or "").strip()
    api_key = (source.get("HERMES_ODOO_API_KEY") or "").strip()
    if not base_url or not api_key:
        raise RuntimeError(
            "HERMES_ODOO_BASE_URL and HERMES_ODOO_API_KEY are required.",
        )
    timeout = int(source.get("HERMES_TIMEOUT_SECONDS") or "30")
    service_interval = int(
        source.get("HERMES_SERVICE_INTERVAL_SECONDS")
        or str(DEFAULT_SERVICE_INTERVAL_SECONDS),
    )
    return HermesConfig(
        odoo_base_url=base_url,
        odoo_api_key=api_key,
        model_provider=(
            source.get("HERMES_MODEL_PROVIDER") or DEFAULT_MODEL_PROVIDER
        ).strip(),
        model_name=(
            source.get("HERMES_MODEL") or DEFAULT_MODEL_NAME
        ).strip(),
        timeout_seconds=timeout,
        service_interval_seconds=service_interval,
    )
