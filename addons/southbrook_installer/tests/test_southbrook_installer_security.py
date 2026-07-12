# SPDX-License-Identifier: LGPL-3.0-only
"""Security + regression tests added by the code review:

* the dispatcher bus notification no longer raises (v19 removed
  bus.bus._sendmany — the whole live-dispatcher feature was silently dead);
* the new record rules scope crew to their assigned jobs while broad roles
  (dispatcher/warehouse/finance/ops) keep company-wide visibility.
"""
from datetime import datetime, timedelta

from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook_installer")
class TestInstallerSecurity(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Job = cls.env["southbrook.installer.job"]
        cls.project = cls.env["project.project"].create({"name": "Sec Test"})
        cls.partner = cls.env["res.partner"].create({"name": "Builder Co"})

        base_user = cls.env.ref("base.group_user").id
        helper_grp = cls.env.ref(
            "southbrook_installer.group_sami_installer_helper").id
        disp_grp = cls.env.ref(
            "southbrook_installer.group_sami_dispatcher").id

        def _user_emp(login, grp):
            user = cls.env["res.users"].create({
                "name": login, "login": login,
                "group_ids": [(6, 0, [base_user, grp])],
            })
            emp = cls.env["hr.employee"].create({
                "name": login, "user_id": user.id})
            return user, emp

        cls.helper_user, cls.helper_emp = _user_emp("inst_helper", helper_grp)
        cls.disp_user, cls.disp_emp = _user_emp("inst_disp", disp_grp)
        cls.other_emp = cls.env["hr.employee"].create({"name": "Other Lead"})

    def _make_job(self, lead, crew=None):
        return self.Job.create({
            "project_id": self.project.id,
            "unit_number": "T-101",
            "site_address": "1 Test Lane",
            "builder_contact_id": self.partner.id,
            "lead_installer_id": lead.id,
            "assigned_crew_ids": [(6, 0, crew.ids)] if crew else False,
            "scheduled_date": datetime.now() + timedelta(days=1),
        })

    # ─── bus regression (v19 _sendmany removal) ─────────────────────
    def test_dispatcher_bus_notify_does_not_raise(self):
        job = self._make_job(self.other_emp)
        product = self.env["product.product"].create({"name": "Cabinet Door"})
        flag = self.env["southbrook.damage.flag"].create({
            "job_id": job.id,
            "product_id": product.id,
            "issue_type": "damaged_transit",
            "urgency": "blocking",
            "description": "cracked door",
        })
        # Previously raised AttributeError (bus.bus._sendmany removed in v19);
        # must now complete cleanly.
        flag._notify_dispatcher_bus("created")

    # ─── record-rule scoping ────────────────────────────────────────
    def test_crew_sees_only_assigned_jobs(self):
        mine_lead = self._make_job(self.helper_emp)
        mine_crew = self._make_job(self.other_emp, crew=self.helper_emp)
        not_mine = self._make_job(self.other_emp)

        visible = self.Job.with_user(self.helper_user).search([]).ids
        self.assertIn(mine_lead.id, visible, "helper must see jobs they lead")
        self.assertIn(mine_crew.id, visible, "helper must see jobs they crew")
        self.assertNotIn(
            not_mine.id, visible,
            "helper must NOT see jobs they're neither lead nor crew on")

    def test_dispatcher_sees_all_jobs(self):
        j1 = self._make_job(self.helper_emp)
        j2 = self._make_job(self.other_emp)
        visible = self.Job.with_user(self.disp_user).search([]).ids
        self.assertIn(j1.id, visible)
        self.assertIn(j2.id, visible,
                      "dispatcher must retain company-wide visibility")
