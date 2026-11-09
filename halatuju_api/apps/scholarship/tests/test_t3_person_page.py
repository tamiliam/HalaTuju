"""Sprint T3 (owner, 2026-11-09; D8 / D9 / M1-M6): ONE person page for every team member.

The three person pages read three existing detail views, and each now serves the same `person` block
(`staff_person.person`): the tables the person sits in (the "Also in" chips' own source), the lead flag,
Joined, signed in, Last seen, and the Profile tab's fields. The pure mentor's page also serves `may_add`
(D8: the Add-to-table path, only for a viewer the Add endpoint would accept).

Pinned here: the new fields on all three payloads; the PII rules (the home address is never served; the
phone only under `assigner_sees_phone`, or a mentor login's own number); no profile row is created by
looking; the organisation fence still answers 404 across organisations; and each GET's query count.
Made-up people only (example.org).
"""
import json

from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext

from apps.courses.models import PartnerAdmin
from apps.scholarship import staff_person
from apps.scholarship.models import Mentor, ReviewerProfile
from apps.scholarship.tests.factories import TEST_JWT_SECRET, authed_client, make_admin, make_org

API = dict(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
HOME = 'Lorong Contoh 7'          # a home address that must never reach any payload


def _profile(admin, **kw):
    fields = dict(street_address=HOME, address=HOME, postcode='50000', city='Klang', state='Selangor',
                  phone='012-000 0000', job_title='Volunteer lead', about='Likes maths.',
                  highest_qualification='Degree', university='Example University',
                  graduation_year=2010, field_of_study='Physics', english_fluency='fluent',
                  bm_fluency='conversational', tamil_fluency='basic', share_phone_with_team=False)
    fields.update(kw)
    return ReviewerProfile.objects.create(partner_admin=admin, **fields)


@override_settings(**API)
class TestThePersonBlock(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.org = make_org()
        cls.other = make_org()
        cls.super = make_admin('super', super_admin=True)
        cls.lead = make_admin('org_admin', owning_org=cls.org, name='Lead Person',
                              email='lead@example.org')
        cls.admin = make_admin('admin', owning_org=cls.org, name='Ada Admin', email='ada@example.org')
        cls.finance = make_admin('finance', owning_org=cls.org, name='Fin Person',
                                 email='fin@example.org')
        cls.reviewer = make_admin('reviewer', owning_org=cls.org, name='Rev Person',
                                  email='rev@example.org')
        cls.both = make_admin('reviewer', owning_org=cls.org, name='Two Tables',
                              email='two@example.org', mentor=Mentor.objects.create(organisation=cls.org))
        cls.mentor = make_admin('mentor', owning_org=cls.org, name='Men Tor', email='men@example.org',
                                first_seen_at='2026-10-02T08:00:00Z')
        cls.stranger = make_admin('admin', owning_org=cls.other, name='Far Away',
                                  email='far@example.org')
        _profile(cls.admin)
        _profile(cls.reviewer)
        _profile(cls.both)
        _profile(cls.mentor)

    def _get(self, caller, url, status=200):
        r = authed_client(caller).get(url)
        self.assertEqual(r.status_code, status, r.content[:300])
        return r

    @staticmethod
    def _admin_url(a):
        return f'/api/v1/admin/admins/{a.pk}/permissions/'

    @staticmethod
    def _reviewer_url(a):
        return f'/api/v1/admin/reviewers/{a.pk}/'

    @staticmethod
    def _mentor_url(a):
        return f'/api/v1/admin/mentors/{a.mentor_id}/'

    # ── the block itself ────────────────────────────────────────────────────────────────────────
    def test_every_payload_carries_the_person_block(self):
        for url in (self._admin_url(self.admin), self._reviewer_url(self.reviewer),
                    self._mentor_url(self.mentor)):
            body = self._get(self.super, url).json()
            self.assertEqual(set(body['person']), set(staff_person.PERSON_KEYS), url)
            self.assertEqual(set(body['person']['profile']), set(staff_person.PROFILE_KEYS), url)

    def test_the_admin_detail_gains_last_seen_profile_and_tables(self):
        PartnerAdmin.objects.filter(pk=self.admin.pk).update(
            first_seen_at='2026-10-01T08:00:00Z', last_seen_at='2026-11-07T09:30:00Z')
        p = self._get(self.lead, self._admin_url(self.admin)).json()['person']
        self.assertEqual(p['tables'], ['admins'])
        self.assertFalse(p['lead'])
        self.assertTrue(p['signed_in'])
        self.assertTrue(p['last_seen_at'].startswith('2026-11-07'))
        self.assertEqual(p['admin_id'], self.admin.pk)
        self.assertIsNone(p['mentor_id'])
        self.assertEqual(p['profile']['job_title'], 'Volunteer lead')
        self.assertEqual(p['profile']['qualification'], 'Degree')
        self.assertEqual(p['profile']['languages'], ['en', 'ms'])   # 'basic' is not spoken

    def test_an_org_admin_is_the_lead_and_only_a_super_opens_them(self):
        p = self._get(self.super, self._admin_url(self.lead)).json()
        self.assertTrue(p['person']['lead'])
        self.assertEqual(p['person']['tables'], ['admins'])
        self.assertFalse(p['editable'])             # M2: drawn as locked switches
        self._get(self.lead, self._admin_url(make_admin('org_admin', owning_org=self.org)), 404)

    def test_someone_in_two_tables_names_both_and_their_mentor_record(self):
        for url in (self._reviewer_url(self.both), self._admin_url(self.both), self._mentor_url(self.both)):
            p = self._get(self.super, url).json()['person']
            self.assertEqual(p['tables'], ['reviewers', 'mentors'], url)
            self.assertEqual(p['mentor_id'], self.both.mentor_id, url)
            self.assertEqual(p['admin_id'], self.both.pk, url)

    def test_the_header_fields_read_one_shape(self):
        p = self._get(self.super, self._mentor_url(self.mentor)).json()['person']
        self.assertEqual((p['name'], p['email']), ('Men Tor', 'men@example.org'))
        self.assertTrue(p['mentor_only'])
        self.assertEqual(p['tables'], ['mentors'])
        PartnerAdmin.objects.filter(pk=self.reviewer.pk).update(paused_at='2026-11-01T08:00:00Z')
        p = self._get(self.lead, self._reviewer_url(self.reviewer)).json()['person']
        self.assertFalse(p['mentor_only'])
        self.assertTrue(p['paused'])
        self.assertTrue(p['is_active'])
        PartnerAdmin.objects.filter(pk=self.mentor.pk).update(is_active=False)
        self.assertFalse(self._get(self.super, self._mentor_url(self.mentor)).json()['person']['is_active'])

    # ── PII ─────────────────────────────────────────────────────────────────────────────────────
    def test_the_home_address_is_never_served(self):
        for caller, url in ((self.super, self._admin_url(self.admin)),
                            (self.lead, self._admin_url(self.admin)),
                            (self.lead, self._reviewer_url(self.reviewer)),
                            (self.admin, self._reviewer_url(self.reviewer)),
                            (self.lead, self._mentor_url(self.mentor)),
                            (self.admin, self._mentor_url(self.mentor)),
                            (self.lead, self._mentor_url(self.both))):
            text = self._get(caller, url).content.decode()
            for leak in (HOME, '50000', 'Klang', 'Selangor'):
                self.assertNotIn(leak, text, url)
            body = json.loads(text)
            for key in ('address', 'street_address', 'postcode', 'city', 'state'):
                self.assertNotIn(key, body['person']['profile'])

    def test_the_phone_follows_the_team_rule(self):
        # An admin who does not show it to the team and holds no `review`: no phone.
        self.assertEqual(self._get(self.lead, self._admin_url(self.admin)).json()
                         ['person']['profile']['phone'], '')
        # ...until they show it to the team.
        ReviewerProfile.objects.filter(partner_admin=self.admin).update(share_phone_with_team=True)
        self.assertEqual(self._get(self.lead, self._admin_url(self.admin)).json()
                         ['person']['profile']['phone'], '012-000 0000')
        # A reviewer can be handed cases: the assigner sees it (the reviewer detail's own rule).
        self.assertEqual(self._get(self.lead, self._reviewer_url(self.reviewer)).json()
                         ['person']['profile']['phone'], '012-000 0000')
        # A mentor login: their own number, which the inviting organisation sees (S7a).
        self.assertEqual(self._get(self.lead, self._mentor_url(self.mentor)).json()
                         ['person']['profile']['phone'], '012-000 0000')

    def test_looking_never_creates_a_profile(self):
        before = ReviewerProfile.objects.filter(partner_admin=self.finance).exists()
        p = self._get(self.lead, self._admin_url(self.finance)).json()['person']['profile']
        self.assertFalse(before)
        self.assertFalse(ReviewerProfile.objects.filter(partner_admin=self.finance).exists())
        self.assertEqual(p, {'job_title': '', 'about': '', 'qualification': '', 'university': '',
                             'graduation_year': None, 'field_of_study': '', 'phone': '',
                             'languages': [], 'other_language': ''})

    # ── the fence ───────────────────────────────────────────────────────────────────────────────
    def test_another_organisation_still_404s(self):
        far_mentor = make_admin('mentor', owning_org=self.other)
        far_reviewer = make_admin('reviewer', owning_org=self.other)
        self._get(self.lead, self._admin_url(self.stranger), 404)
        self._get(self.lead, self._reviewer_url(far_reviewer), 404)
        self._get(self.lead, self._mentor_url(far_mentor), 404)
        self._get(self.admin, self._mentor_url(far_mentor), 404)

    # ── D8: the pure mentor's Add path ──────────────────────────────────────────────────────────
    def test_may_add_is_the_add_endpoints_own_rule(self):
        self.assertEqual(self._get(self.super, self._mentor_url(self.mentor)).json()['may_add'],
                         ['admins', 'reviewers'])
        self.assertEqual(self._get(self.lead, self._mentor_url(self.mentor)).json()['may_add'],
                         ['admins', 'reviewers'])
        # An admin reads the Mentors table but may not add anybody to a table.
        self.assertEqual(self._get(self.admin, self._mentor_url(self.mentor)).json()['may_add'], [])
        # A staff member who also mentors is already staff: their own tables are changed elsewhere.
        self.assertEqual(self._get(self.super, self._mentor_url(self.both)).json()['may_add'], [])
        # A mentor who has not signed in yet cannot join a table (the Add's own refusal): no path.
        new = make_admin('mentor', owning_org=self.org)
        self.assertEqual(self._get(self.super, self._mentor_url(new)).json()['may_add'], [])
        self.assertFalse(self._get(self.super, self._mentor_url(new)).json()['person']['signed_in'])

    # ── query counts ────────────────────────────────────────────────────────────────────────────
    def _count(self, caller, url):
        client = authed_client(caller)
        client.get(url)   # warm any per-process cache
        with CaptureQueriesContext(connection) as ctx:
            r = client.get(url)
        self.assertEqual(r.status_code, 200)
        return len(ctx)

    def test_query_counts(self):
        measured = {
            'admin': self._count(self.lead, self._admin_url(self.admin)),
            'admin_two_tables': self._count(self.lead, self._admin_url(self.both)),
            'reviewer': self._count(self.lead, self._reviewer_url(self.reviewer)),
            'reviewer_two_tables': self._count(self.lead, self._reviewer_url(self.both)),
            'mentor': self._count(self.lead, self._mentor_url(self.mentor)),
            'mentor_two_tables': self._count(self.lead, self._mentor_url(self.both)),
        }
        # Measured before T3 (2026-11-09): admin 5 / 6, reviewer 7 / 7, mentor 11 / 11. The admin detail
        # selects the profile and the mentor with the row (the two-table person fell 6 -> 5); the reviewer
        # detail already had both; the mentor detail reads the login once more for `person` / `may_add`
        # (+1). ⚠ A rise here is a decision, not a re-record.
        self.assertEqual(measured, {'admin': 5, 'admin_two_tables': 5, 'reviewer': 7,
                                    'reviewer_two_tables': 7, 'mentor': 12, 'mentor_two_tables': 12})
