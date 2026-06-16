# SPDX-License-Identifier: LGPL-3.0-only
"""@hermes_tool decorator and the in-process TOOL_REGISTRY."""
import functools
import inspect

TOOL_REGISTRY = []


def hermes_tool(*, personas, tier, scope, description, parameters=None):
    def wrap(fn):
        slug = fn.__name__
        params = parameters or _extract_params_from_signature(fn)
        TOOL_REGISTRY.append({
            "slug": slug,
            "qualified_slug": f"southbrook__{slug}",
            "personas": list(personas),
            "tier": tier,
            "scope": scope,
            "description": description,
            "parameters": params,
            "fn": fn,
        })
        @functools.wraps(fn)
        def call(env, **kwargs):
            return fn(env, **kwargs)
        return call
    return wrap


def _extract_params_from_signature(fn):
    sig = inspect.signature(fn)
    props = {}
    required = []
    for name, param in sig.parameters.items():
        if name == "env":
            continue
        json_type = "string"
        if param.annotation is int:
            json_type = "integer"
        elif param.annotation is bool:
            json_type = "boolean"
        elif param.annotation is float:
            json_type = "number"
        props[name] = {"type": json_type}
        if param.default is inspect.Parameter.empty:
            required.append(name)
    return {"type": "object", "properties": props, "required": required}


def registry_for_persona(persona, tier_mask):
    allowed_tiers = set(tier_mask.split("+"))
    return [
        {k: v for k, v in t.items() if k != "fn"}
        for t in TOOL_REGISTRY
        if persona in t["personas"] and t["tier"] in allowed_tiers
    ]


def get_tool_function(slug):
    for t in TOOL_REGISTRY:
        if t["slug"] == slug:
            return t["fn"]
    return None
