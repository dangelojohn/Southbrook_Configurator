# SPDX-License-Identifier: LGPL-3.0-only
from dataclasses import dataclass
import os


@dataclass(frozen=True)
class HermesConfig:
    odoo_base_url: str
    odoo_api_key: str
    model_provider: str = "openai"
    model_name: str = "gpt-5"
    timeout_seconds: int = 30


def load_config(env=None):
    source = env or os.environ
    base_url = (source.get("HERMES_ODOO_BASE_URL") or "").strip()
    api_key = (source.get("HERMES_ODOO_API_KEY") or "").strip()
    if not base_url or not api_key:
        raise RuntimeError(
            "HERMES_ODOO_BASE_URL and HERMES_ODOO_API_KEY are required.",
        )
    timeout = int(source.get("HERMES_TIMEOUT_SECONDS") or "30")
    return HermesConfig(
        odoo_base_url=base_url,
        odoo_api_key=api_key,
        model_provider=(source.get("HERMES_MODEL_PROVIDER") or "openai").strip(),
        model_name=(source.get("HERMES_MODEL") or "gpt-5").strip(),
        timeout_seconds=timeout,
    )
