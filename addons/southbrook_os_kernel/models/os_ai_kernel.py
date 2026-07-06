# SPDX-License-Identifier: LGPL-3.0-only
"""``southbrook.os.ai.kernel`` — the OS Kernel's AI routing API.

Implements OS_KERNEL_SPEC.md §3. Every AI feature in the platform is meant
to route its chat-completion calls through :meth:`run` instead of talking to
a provider directly, so kill-switches, budgets, and the ledger are always
honoured.

Hard contract: ``run()`` NEVER raises. Every return path — success,
kill-switch block, budget block, transport failure, unexpected internal
error — returns the same dict shape. The ledger insert itself is wrapped in
its own try/except (a logging failure must never take down the caller's
answer).

The budget probe tests registry membership (``"southbrook.os.agent" in
self.env``) rather than truthiness, and skips budget checks when the model
is absent. ``southbrook.os.agent`` ships in this same module, so in practice
it is always present; the guard is deliberate defense-in-depth against
partial registry states (mid-upgrade, module uninstall ordering) and keeps
the kernel's never-raises contract independent of the budget subsystem.
"""
import json
import time

from odoo import api, models

try:
    import requests
except ImportError:  # pragma: no cover - exercised via config, not import
    requests = None


class SouthbrookOsAiKernel(models.AbstractModel):
    _name = "southbrook.os.ai.kernel"
    _description = "Southbrook OS AI Kernel"

    @api.model
    def run(self, feature, messages, model=None, temperature=None,
            max_tokens=None, timeout=45, source=None):
        """Route one chat-completion call. NEVER raises — always returns:
        {"ok": bool, "content": str|None, "error": str|None,
         "request_id": int|None, "tokens_prompt": int,
         "tokens_completion": int, "cost_usd": float}
        source: optional (model_name, res_id) tuple for provenance.
        """
        start = time.monotonic()
        result = {
            "ok": False,
            "content": None,
            "error": None,
            "request_id": None,
            "tokens_prompt": 0,
            "tokens_completion": 0,
            "cost_usd": 0.0,
        }
        try:
            return self._run(feature, messages, model, temperature,
                              max_tokens, timeout, source, start, result)
        except Exception as exc:
            # Absolute last-resort guard: even an unforeseen bug anywhere
            # in the flow above must surface as a normal blocked/error
            # result, never as a raised exception to the caller. The result
            # dict may already carry ok=True/content from a partially
            # completed flow — reset it so the error result is coherent.
            result["ok"] = False
            result["content"] = None
            result["error"] = "kernel_exception: %s" % exc
            result["request_id"] = self._safe_log(
                feature, messages, "error", result["error"],
                self._elapsed_ms(start), source,
            )
            return result

    # ------------------------------------------------------------------
    # Internal flow (steps per OS_KERNEL_SPEC.md §3)
    # ------------------------------------------------------------------
    def _run(self, feature, messages, model, temperature, max_tokens,
              timeout, source, start, result):
        Switch = self.env["southbrook.os.switch"]

        # Step 1: master switch (default False -> off by default / ships dark)
        try:
            master_on = Switch.is_on("os.ai.enabled", default=False)
        except Exception:
            master_on = False
        if not master_on:
            result["error"] = "blocked:master"
            result["request_id"] = self._safe_log(
                feature, messages, "blocked", result["error"],
                self._elapsed_ms(start), source,
            )
            return result

        # Step 2: feature switch (default True -> absent means allowed)
        try:
            feature_on = Switch.is_on(f"os.ai.feature.{feature}", default=True)
        except Exception:
            feature_on = True
        if not feature_on:
            result["error"] = "blocked:feature"
            result["request_id"] = self._safe_log(
                feature, messages, "blocked", result["error"],
                self._elapsed_ms(start), source,
            )
            return result

        # Step 3: budget (southbrook.os.agent may not exist yet -- probe by
        # membership, never by truthiness, per the AbstractModel falsy trap)
        agent = None
        try:
            if "southbrook.os.agent" in self.env:
                agent = self.env["southbrook.os.agent"].sudo().search(
                    [("feature_key", "=", feature)], limit=1
                )
                if agent:
                    est_tokens = max_tokens or 1024
                    if not agent.check_and_consume(est_tokens=est_tokens):
                        result["error"] = "blocked:budget"
                        result["request_id"] = self._safe_log(
                            feature, messages, "blocked", result["error"],
                            self._elapsed_ms(start), source,
                        )
                        return result
        except Exception:
            # Budget subsystem failing must never block a call it cannot
            # actually evaluate.
            agent = None

        # Step 4: transport
        transport = self.env["ir.config_parameter"].sudo().get_param(
            "os.ai.transport", "http"
        )
        provider = "openai_compat"
        model_name = model or None
        content = None
        tokens_prompt = 0
        tokens_completion = 0
        error = None

        if transport == "mock":
            content = "MOCK:" + feature
            tokens_prompt = 1
            tokens_completion = 1
        else:
            try:
                content, tokens_prompt, tokens_completion, error = (
                    self._call_http(messages, model, temperature, max_tokens,
                                     timeout)
                )
            except Exception as exc:
                error = "transport_exception: %s" % exc

        if error:
            result["error"] = error
            result["request_id"] = self._safe_log(
                feature, messages, "error", error, self._elapsed_ms(start),
                source, provider=provider, model_name=model_name,
            )
            return result

        # Step 5: cost
        try:
            cost_usd = self._compute_cost(tokens_prompt, tokens_completion)
        except Exception:
            cost_usd = 0.0

        result.update({
            "ok": True,
            "content": content,
            "error": None,
            "tokens_prompt": tokens_prompt,
            "tokens_completion": tokens_completion,
            "cost_usd": cost_usd,
        })

        # Step 6: ledger row (always written; failure here must not affect
        # the answer already computed above)
        if not model_name:
            try:
                model_name = self._default_model()
            except Exception:
                model_name = None
        result["request_id"] = self._safe_log(
            feature, messages, "done", None, self._elapsed_ms(start),
            source, provider=provider, model_name=model_name,
            tokens_prompt=tokens_prompt, tokens_completion=tokens_completion,
            cost_usd=cost_usd, response_preview=content,
        )

        # Step 7: post actual usage to the matched budget agent, if any
        if agent:
            try:
                agent.record_usage(tokens_prompt + tokens_completion)
            except Exception:
                pass

        return result

    # ------------------------------------------------------------------
    # Transport
    # ------------------------------------------------------------------
    def _call_http(self, messages, model, temperature, max_tokens, timeout):
        """OpenAI-compatible chat-completions POST.

        Returns (content, tokens_prompt, tokens_completion, error). ``error``
        is None on success; any failure returns a description string and
        leaves content/tokens at their zero defaults -- never raises.
        """
        if requests is None:
            return None, 0, 0, "transport_error: requests library not available"

        icp = self.env["ir.config_parameter"].sudo()
        endpoint = icp.get_param("os.ai.endpoint")
        api_key = icp.get_param("os.ai.api_key")
        default_model = icp.get_param("os.ai.default_model")

        if not endpoint:
            return None, 0, 0, "transport_error: os.ai.endpoint not configured"

        payload = {
            "model": model or default_model,
            "messages": messages,
        }
        if temperature is not None:
            payload["temperature"] = temperature
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        try:
            resp = requests.post(
                f"{endpoint}/chat/completions",
                json=payload,
                headers=headers,
                timeout=timeout,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            return None, 0, 0, "transport_error: %s" % exc

        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            return None, 0, 0, "transport_error: malformed response"

        usage = data.get("usage") or {}
        tokens_prompt = usage.get("prompt_tokens") or 0
        tokens_completion = usage.get("completion_tokens") or 0
        return content, tokens_prompt, tokens_completion, None

    # ------------------------------------------------------------------
    # Cost / helpers
    # ------------------------------------------------------------------
    def _compute_cost(self, tokens_prompt, tokens_completion):
        icp = self.env["ir.config_parameter"].sudo()
        price_prompt = float(icp.get_param("os.ai.price_per_1k_prompt", 0.0) or 0.0)
        price_completion = float(
            icp.get_param("os.ai.price_per_1k_completion", 0.0) or 0.0
        )
        return (tokens_prompt / 1000.0) * price_prompt + (
            tokens_completion / 1000.0
        ) * price_completion

    def _default_model(self):
        return self.env["ir.config_parameter"].sudo().get_param("os.ai.default_model")

    @staticmethod
    def _elapsed_ms(start):
        return int((time.monotonic() - start) * 1000)

    @staticmethod
    def _dump_messages(messages):
        try:
            text = json.dumps(messages)
        except Exception:
            text = str(messages)
        if len(text) > 2000:
            return text[:2000]
        return text

    def _safe_log(self, feature, messages, state, error, duration_ms, source,
                   provider=None, model_name=None, tokens_prompt=0,
                   tokens_completion=0, cost_usd=0.0, response_preview=None):
        """Create the ledger row. Wrapped so a logging failure can never
        break the caller's already-computed result."""
        try:
            vals = {
                "feature": feature,
                "state": state,
                "provider": provider,
                "model_name": model_name,
                "error": error,
                "duration_ms": duration_ms,
                "tokens_prompt": tokens_prompt,
                "tokens_completion": tokens_completion,
                "cost_usd": cost_usd,
                "prompt_preview": self._dump_messages(messages),
                "response_preview": response_preview,
            }
            if source:
                source_model, source_res_id = source
                vals["source_model"] = source_model
                vals["source_res_id"] = source_res_id
            request = self.env["southbrook.os.ai.request"].sudo().create(vals)
            return request.id
        except Exception:
            return None
