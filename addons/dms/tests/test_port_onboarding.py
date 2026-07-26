from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "dms_port")
class TestPortOnboarding(TransactionCase):
    def test_company_has_no_dead_onboarding_fields(self):
        self.assertNotIn("documents_onboarding_state", self.env["res.company"]._fields)

    def test_save_storage_step_no_crash(self):
        # the onboarding "create storage" footer action must not raise
        self.env["dms.storage"].action_save_onboarding_storage_step()
