"""TD-153 (b) — the last three oversight lists that any admin could read now gate on ROLE.

Each gate is the union of roles that legitimately reach the data (decisions.md 2026-09-30):

  endpoint                                  allowed (super always passes)
  /admin/sponsorships/                      org_admin, admin, finance   (the Sponsors roles)
  /admin/graduation-messages/               reviewer, admin             (moderator + ex-'viewer')
  /admin/scholarship/verdict-metrics/       org_admin, admin, qc, reviewer (Applications roles)

lessons.md 2026-09-28: "for a rule keyed on role, loop EVERY role that can reach the screen" — so
every test below walks the whole `PartnerAdmin.ROLE_CHOICES` vocabulary, not a sample.
"""
from django.test import TestCase, override_settings

from apps.courses.models import PartnerAdmin
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_cohort,
)

ROLES = tuple(code for code, _ in PartnerAdmin.ROLE_CHOICES)

GATES = {
    '/api/v1/admin/sponsorships/': {'super', 'org_admin', 'admin', 'finance'},
    '/api/v1/admin/graduation-messages/': {'super', 'reviewer', 'admin'},
    '/api/v1/admin/scholarship/verdict-metrics/': {'super', 'org_admin', 'admin', 'qc',
                                                  'reviewer'},
}


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class OversightListRoleGateTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = make_cohort().owning_organisation
        # One active admin per role, inside the organisation, so a refusal can only be the ROLE.
        cls.admins = {role: make_admin(role, owning_org=cls.org, super_admin=(role == 'super'))
                      for role in ROLES}

    def test_the_vocabulary_is_the_one_the_gates_were_derived_from(self):
        # A new role must be placed in (or out of) each gate by a person, not by default.
        self.assertEqual(set(ROLES), {'super', 'admin', 'org_admin', 'partner', 'reviewer', 'qc',
                                      'finance'})

    def _check(self, path):
        allowed = GATES[path]
        got = {role: authed_client(self.admins[role]).get(path).status_code for role in ROLES}
        want = {role: (200 if role in allowed else 403) for role in ROLES}
        self.assertEqual(got, want, path)

    def test_the_sponsorships_list(self):
        self._check('/api/v1/admin/sponsorships/')

    def test_the_graduation_message_queue(self):
        self._check('/api/v1/admin/graduation-messages/')

    def test_the_verdict_metrics(self):
        self._check('/api/v1/admin/scholarship/verdict-metrics/')

    def test_a_legacy_super_flag_passes_every_gate(self):
        legacy = make_admin('reviewer', owning_org=self.org, super_admin=True)
        for path in GATES:
            self.assertEqual(authed_client(legacy).get(path).status_code, 200, path)
