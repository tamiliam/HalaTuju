"""Two guards on the officer cockpit's payload — deliberately NOT a key-set snapshot (2026-07-30).

`AdminApplicationDetailSerializer` carries 154 fields. The sponsor and finance serializers are
pinned by exact key-set snapshots because they cross an AUDIENCE boundary — a sponsor must never
see a student's identity, finance must never acquire B40 student data — and there the snapshot IS
the boundary made mechanical.

This payload has no such boundary: it is the back office reading its own applicant, already
org-fenced (and that fence has its own CI guard in `test_org_fence.py`). A 154-key snapshot here
would fail on every legitimate field addition, the fix would be to paste in the new key, and
after the third time nobody reads what they are blessing — manufacturing the APPEARANCE of review
while removing the friction that made it real. Worse than no test, because it gets cited as
coverage.

So these pin the two properties that actually carry weight, and neither needs touching when a
field is added.
"""
import jwt
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.courses.models import PartnerAdmin, PartnerOrganisation, StudentProfile
from apps.scholarship.models import ScholarshipApplication, ScholarshipCohort
from apps.scholarship.serializers_admin import AdminApplicationDetailSerializer

TEST_JWT_SECRET = 'test-supabase-jwt-secret'


def _token(uid):
    return jwt.encode({'sub': uid, 'aud': 'authenticated', 'role': 'authenticated',
                       'email': f'{uid}@x.com'}, TEST_JWT_SECRET, algorithm='HS256')


class TestThePayloadIsAnAllowlistByConstruction(TestCase):
    """The structural property, which is what actually prevents a leak here.

    A new column on `ScholarshipApplication` cannot reach an admin screen by accident while the
    serializer names its fields explicitly. Switch to `__all__` or `exclude` and every future
    column ships to the cockpit — and to any log or CSV built from this payload — silently. The
    154 names may change freely; the allowlist-ness may not.
    """
    def test_fields_are_named_explicitly(self):
        meta = AdminApplicationDetailSerializer.Meta
        self.assertTrue(hasattr(meta, 'fields'), 'the serializer must name its fields')
        self.assertNotEqual(meta.fields, '__all__',
                            "'__all__' ships every future column to the cockpit silently")
        self.assertIsInstance(meta.fields, (list, tuple))
        self.assertFalse(hasattr(meta, 'exclude'),
                         'a denylist inverts the guard — a new column is included by default')

    def test_the_allowlist_is_not_trivially_empty_or_tiny(self):
        # Guards the other direction: a refactor that empties the list would pass the test above
        # while breaking every screen. Deliberately a floor, not the exact count, so a field
        # addition does not fail this.
        self.assertGreater(len(AdminApplicationDetailSerializer.Meta.fields), 100)


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestEveryRoleSeesTheSamePayload(TestCase):
    """Role-invariance, which is an OWNER DECISION and until 2026-07-30 was an accident.

    Owner: the record should be "open to anyone who has access to the relevant pages" — so access
    is decided by the page gate, and the payload is not trimmed per role. Nothing stated that
    before; it was merely true because nobody had differentiated.

    Pinning it makes the next super-only field a DECISION rather than a side effect. It is also
    the question a key-set snapshot would have forced, isolated to the part that matters: this is
    how `qc_override_reason` came to reach reviewers, and the owner has now confirmed that is
    intended rather than incidental.
    """
    @classmethod
    def setUpTestData(cls):
        cls.org = PartnerOrganisation.objects.create(code='pay-org', name='Pay')
        for uid, role, sup in (('p-sup', 'super', True), ('p-oa', 'org_admin', False),
                               ('p-qc', 'qc', False), ('p-rev', 'reviewer', False)):
            PartnerAdmin.objects.create(
                supabase_user_id=uid, role=role, is_super_admin=sup, is_active=True,
                name=uid, email=f'{uid}@x.com', owning_organisation=cls.org)
        cls.cohort = ScholarshipCohort.objects.create(
            code='c-pay', name='B40', year=2026, owning_organisation=cls.org)
        profile = StudentProfile.objects.create(
            supabase_user_id='pay-prof', nric='030101-14-1234', name='Priya')
        cls.app = ScholarshipApplication.objects.create(
            cohort=cls.cohort, profile=profile, status='shortlisted',
            owning_organisation=cls.org, assigned_to_id=None,
            # the field that prompted this guard: a QC accepted over a red fact, with a reason
            qc_override_by='p-sup@x.com', qc_override_reason='STR is valid B40 evidence.',
        )

    def _keys(self, uid):
        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(uid)}')
        r = c.get(f'/api/v1/admin/scholarship/applications/{self.app.id}/')
        self.assertEqual(r.status_code, 200, f'{uid}: {r.content[:200]}')
        return set(r.json().keys())

    def test_the_key_set_does_not_vary_by_role(self):
        baseline = self._keys('p-sup')
        for uid in ('p-oa', 'p-qc'):
            with self.subTest(role=uid):
                self.assertEqual(
                    self._keys(uid), baseline,
                    f'{uid} sees a different payload shape from a super. If that is deliberate, '
                    f'say so here — access is meant to be decided by the PAGE gate, not by '
                    f'trimming fields (owner, 2026-07-30).')

    def test_the_qc_override_trail_is_part_of_it(self):
        """It reaches everyone who can open the page — confirmed by the owner, not assumed."""
        keys = self._keys('p-oa')
        for f in ('qc_override_by', 'qc_override_by_name', 'qc_override_at', 'qc_override_reason'):
            self.assertIn(f, keys)
