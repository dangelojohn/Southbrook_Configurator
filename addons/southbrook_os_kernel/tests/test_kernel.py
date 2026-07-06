# SPDX-License-Identifier: LGPL-3.0-only
from unittest.mock import MagicMock, patch

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook_os_kernel")
class TestOsAiKernel(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Switch = cls.env["southbrook.os.switch"]
        cls.Kernel = cls.env["southbrook.os.ai.kernel"]
        cls.Request = cls.env["southbrook.os.ai.request"]
        cls.ICP = cls.env["ir.config_parameter"].sudo()

        # NO network calls ever in this test file: pin the mock transport
        # as the class-wide default; individual tests that need to exercise
        # the http path override it locally (and never provide an endpoint).
        cls.ICP.set_param("os.ai.transport", "mock")

        # Master kill-switch on by default for this class; the one test
        # that needs it off flips it locally within its own method.
        cls.Switch.set_switch("os.ai.enabled", True, name="AI Kernel - master")

        cls.messages = [{"role": "user", "content": "hello"}]

    def test_master_off_blocks(self):
        self.Switch.set_switch("os.ai.enabled", False, name="AI Kernel - master")
        out = self.Kernel.run("smoke_test", self.messages)
        self.assertFalse(out["ok"])
        self.assertEqual(out["error"], "blocked:master")
        self.assertIsNotNone(out["request_id"])
        row = self.Request.browse(out["request_id"])
        self.assertEqual(row.state, "blocked")

    def test_master_and_feature_on_mock_success(self):
        # Feature switch absent -> allowed by default (default=True semantics).
        out = self.Kernel.run("smoke_test", self.messages)
        self.assertTrue(out["ok"])
        self.assertIsNone(out["error"])
        self.assertTrue(out["content"].startswith("MOCK:"))
        self.assertEqual(out["content"], "MOCK:smoke_test")
        self.assertIsNotNone(out["request_id"])
        row = self.Request.browse(out["request_id"])
        self.assertEqual(row.state, "done")
        self.assertEqual(row.tokens_prompt, 1)
        self.assertEqual(row.tokens_completion, 1)

    def test_feature_disabled_blocks(self):
        self.Switch.set_switch(
            "os.ai.feature.smoke_test", False, name="Smoke test feature"
        )
        out = self.Kernel.run("smoke_test", self.messages)
        self.assertFalse(out["ok"])
        self.assertEqual(out["error"], "blocked:feature")
        row = self.Request.browse(out["request_id"])
        self.assertEqual(row.state, "blocked")

    def test_run_never_raises_on_bad_http_transport(self):
        # transport=http with no endpoint configured must NOT raise -- it
        # must come back as a normal (ok=False) result with a ledger row.
        self.ICP.set_param("os.ai.transport", "http")
        self.ICP.set_param("os.ai.endpoint", "")
        try:
            out = self.Kernel.run("smoke_test", self.messages)
        except Exception as exc:  # pragma: no cover - the thing under test
            self.fail(f"run() raised instead of returning a result: {exc}")
        self.assertFalse(out["ok"])
        self.assertIsNotNone(out["error"])
        self.assertIsNotNone(out["request_id"])
        row = self.Request.browse(out["request_id"])
        self.assertIn(row.state, ("error", "blocked"))

    def test_run_never_raises_shape_always_present(self):
        # Whatever happens, every key of the contract dict must be present.
        out = self.Kernel.run("smoke_test", self.messages)
        for key in (
            "ok", "content", "error", "request_id",
            "tokens_prompt", "tokens_completion", "cost_usd",
        ):
            self.assertIn(key, out)

    def test_run_never_raises_on_bad_anthropic_transport(self):
        # transport=anthropic with no api_key configured must NOT raise --
        # same never-raises contract as the http-transport test above, no
        # network call is ever attempted (missing key is checked first).
        self.ICP.set_param("os.ai.transport", "anthropic")
        self.ICP.set_param("os.ai.api_key", "")
        try:
            out = self.Kernel.run("smoke_test", self.messages)
        except Exception as exc:  # pragma: no cover - the thing under test
            self.fail(f"run() raised instead of returning a result: {exc}")
        self.assertFalse(out["ok"])
        self.assertEqual(out["error"], "transport_error: os.ai.api_key not configured")
        row = self.Request.browse(out["request_id"])
        self.assertEqual(row.state, "error")
        self.assertEqual(row.provider, "anthropic")

    def test_split_system_extracts_and_joins(self):
        # Pure helper: Anthropic wants system as a top-level string, not a
        # message role -- verify extraction without any network involved.
        messages = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "hi"},
            {"role": "system", "content": "Be concise."},
            {"role": "assistant", "content": "ok"},
        ]
        system, rest = self.Kernel._split_system(messages)
        self.assertEqual(system, "You are helpful.\n\nBe concise.")
        self.assertEqual(rest, [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "ok"},
        ])

    def test_split_system_none_when_absent(self):
        messages = [{"role": "user", "content": "hi"}]
        system, rest = self.Kernel._split_system(messages)
        self.assertIsNone(system)
        self.assertEqual(rest, messages)

    def test_split_system_handles_block_list_content(self):
        # A system message's content may be a list of Anthropic-style
        # content blocks rather than a plain string -- must extract text,
        # not stringify the list repr.
        messages = [
            {"role": "system", "content": [
                {"type": "text", "text": "Be helpful."},
                {"type": "text", "text": "Be concise."},
            ]},
            {"role": "user", "content": "hi"},
        ]
        system, rest = self.Kernel._split_system(messages)
        self.assertEqual(system, "Be helpful.Be concise.")
        self.assertEqual(rest, [{"role": "user", "content": "hi"}])

    def test_anthropic_success_mocked_http(self):
        # Full round trip through _call_anthropic with requests.post mocked
        # (no real network) -- verifies wire-format payload/headers, system
        # extraction, response parsing, and ledger correctness together.
        self.ICP.set_param("os.ai.transport", "anthropic")
        self.ICP.set_param("os.ai.api_key", "sk-ant-test-dummy")
        messages = [
            {"role": "system", "content": "Be helpful."},
            {"role": "user", "content": "hello"},
        ]
        fake_resp = MagicMock()
        fake_resp.status_code = 200
        fake_resp.json.return_value = {
            "content": [{"type": "text", "text": "hi there"}],
            "usage": {"input_tokens": 12, "output_tokens": 34},
        }
        with patch("requests.post", return_value=fake_resp) as mock_post:
            out = self.Kernel.run("smoke_test", messages)

        self.assertTrue(out["ok"])
        self.assertEqual(out["content"], "hi there")
        self.assertEqual(out["tokens_prompt"], 12)
        self.assertEqual(out["tokens_completion"], 34)

        row = self.Request.browse(out["request_id"])
        self.assertEqual(row.state, "done")
        self.assertEqual(row.provider, "anthropic")
        self.assertEqual(row.model_name, "claude-sonnet-5")

        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertEqual(args[0], "https://api.anthropic.com/v1/messages")
        payload = kwargs["json"]
        self.assertEqual(payload["system"], "Be helpful.")
        self.assertEqual(
            payload["messages"], [{"role": "user", "content": "hello"}]
        )
        self.assertEqual(payload["thinking"], {"type": "disabled"})
        self.assertNotIn("temperature", payload)
        self.assertNotIn("top_p", payload)
        self.assertEqual(kwargs["headers"]["x-api-key"], "sk-ant-test-dummy")
        self.assertEqual(
            kwargs["headers"]["anthropic-version"], "2023-06-01"
        )

    def test_anthropic_malformed_response_never_raises(self):
        # A 200 response whose body isn't the expected shape (e.g. a bare
        # JSON array, or a response with no "content" list) must degrade to
        # a normal error result -- never raise -- per the F4 fix.
        self.ICP.set_param("os.ai.transport", "anthropic")
        self.ICP.set_param("os.ai.api_key", "sk-ant-test-dummy")
        fake_resp = MagicMock()
        fake_resp.status_code = 200
        fake_resp.json.return_value = ["not", "a", "dict"]
        with patch("requests.post", return_value=fake_resp):
            try:
                out = self.Kernel.run("smoke_test", self.messages)
            except Exception as exc:  # pragma: no cover - the thing under test
                self.fail(f"run() raised instead of returning a result: {exc}")
        self.assertFalse(out["ok"])
        self.assertEqual(out["error"], "transport_error: malformed response")
        row = self.Request.browse(out["request_id"])
        self.assertEqual(row.state, "error")
