# SPDX-License-Identifier: LGPL-3.0-only
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
