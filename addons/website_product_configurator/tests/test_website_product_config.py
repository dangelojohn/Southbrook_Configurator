import odoo.tests
from odoo.tests import tagged


@odoo.tests.common.tagged("post_install", "-at_install")
@tagged("configurator")
class TestUi(odoo.tests.HttpCase):
    def test_01_admin_config_tour(self):
        self.start_tour("/web", "config", login="admin")

    def test_02_demo_config_tour(self):
        self.start_tour("/web", "config", login="demo")
