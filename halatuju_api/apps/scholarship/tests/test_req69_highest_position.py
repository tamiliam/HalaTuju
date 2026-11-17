"""Request #69 (2026-11-17): "Highest position held" on staff profiles, with a sponsor summary.

- the field and its four choices (blank = not given);
- `PATCH admin/me/` saves, clears and refuses it, and makes the profile row when there is none — only the
  caller's own row;
- the Team person page serves it beside the job title (`test_t3_person_page.py` pins the key sets);
- the sponsor Trust page's `volunteers`: no figures below five answers; at five or more the right
  shares (largest remainder, summing to 100); other organisations, supers, source users, archived and
  revoked staff never count; the payload holds the count and the four shares only;
- completion counts it for every kind (`test_profile_completion.py`).
"""
import json

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.scholarship import volunteer_positions
from apps.scholarship.models import Sponsor, SponsorProgrammeMembership, StaffProfile
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_org, make_programme,
)

ME = '/api/v1/admin/me/'
TRUST = '/api/v1/sponsor/trust/'
API = dict(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
KEYS = ('c_level', 'head', 'manager', 'individual')


def _answered(org, position, role='reviewer', **kw):
    admin = make_admin(role, owning_org=org, **kw)
    StaffProfile.objects.create(partner_admin=admin, highest_position=position)
    return admin


class TestTheField(TestCase):
    def test_four_choices_exactly_and_blank_is_not_given(self):
        field = StaffProfile._meta.get_field('highest_position')
        self.assertEqual([k for k, _ in field.choices], list(KEYS))
        self.assertEqual(dict(field.choices), {
            'c_level': 'C-level, founder or business owner',
            'head': 'Head of department or senior manager',
            'manager': 'Manager',
            'individual': 'Individual contributor (academic, doctor, etc.)'})
        self.assertTrue(field.blank)
        self.assertEqual(field.default, '')
        self.assertEqual(field.db_default, '')   # the migrate-first deploy: old inserts still pass


@override_settings(**API)
class TestAdminMe(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = make_org()

    def _patch(self, admin, body):
        return authed_client(admin).patch(ME, body, content_type='application/json')

    def test_saving_makes_the_missing_row_and_only_the_callers(self):
        admin = make_admin('finance', owning_org=self.org)
        other = make_admin('reviewer', owning_org=self.org)
        StaffProfile.objects.create(partner_admin=other, highest_position='manager')
        self.assertFalse(StaffProfile.objects.filter(partner_admin=admin).exists())
        r = self._patch(admin, {'highest_position': 'c_level'})
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()['highest_position'], 'c_level')
        self.assertEqual(StaffProfile.objects.get(partner_admin=admin).highest_position, 'c_level')
        self.assertEqual(StaffProfile.objects.get(partner_admin=other).highest_position, 'manager')
        done = {i['key']: i['done'] for i in r.json()['completion']['items']}
        self.assertTrue(done['highest_position'])

    def test_every_kind_may_answer_it(self):
        for role in ('org_admin', 'admin', 'reviewer', 'qc', 'finance', 'mentor', 'member', 'source_partner'):
            with self.subTest(role=role):
                r = self._patch(make_admin(role, owning_org=self.org), {'highest_position': 'individual'})
                self.assertEqual(r.status_code, 200, r.content)
                self.assertEqual(r.json()['highest_position'], 'individual')

    def test_blank_clears_it_and_the_get_serves_blank(self):
        admin = _answered(self.org, 'head', role='admin')
        client = authed_client(admin)
        self.assertEqual(client.get(ME).json()['highest_position'], 'head')
        r = self._patch(admin, {'highest_position': ''})
        self.assertEqual((r.status_code, r.json()['highest_position']), (200, ''))
        self.assertEqual(StaffProfile.objects.get(partner_admin=admin).highest_position, '')

    def test_anything_else_is_refused_and_nothing_changes(self):
        admin = _answered(self.org, 'head', role='admin')
        for bad in ('ceo', 'Manager', ' manager', None, 3, ['head'], {'k': 'head'}):
            with self.subTest(bad=bad):
                r = self._patch(admin, {'highest_position': bad})
                self.assertEqual((r.status_code, r.json()['code']), (400, 'bad_highest_position'))
        self.assertEqual(StaffProfile.objects.get(partner_admin=admin).highest_position, 'head')

    def test_a_profile_without_it_still_saves(self):
        admin = make_admin('admin', owning_org=self.org)
        r = self._patch(admin, {'job_title': 'Coordinator'})
        self.assertEqual((r.status_code, r.json()['highest_position']), (200, ''))


class TestTheSummary(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = make_org()
        cls.other = make_org()

    def test_below_five_answers_there_are_no_figures(self):
        for pos in ('c_level', 'head', 'manager', 'individual'):
            _answered(self.org, pos)
        self.assertIsNone(volunteer_positions.summary_for_organisation(self.org.id))
        _answered(self.org, 'manager')
        self.assertEqual(volunteer_positions.summary_for_organisation(self.org.id)['count'], 5)

    def test_shares_at_five_and_more(self):
        for pos in ('c_level', 'head', 'head', 'manager', 'individual', 'individual', 'individual'):
            _answered(self.org, pos)
        s = volunteer_positions.summary_for_organisation(self.org.id)
        # 1/7 = 14.29, 2/7 = 28.57, 1/7 = 14.29, 3/7 = 42.86 -> floors 14+28+14+42 = 98; the two
        # largest remainders (head .57, individual .86) get the two points left.
        self.assertEqual(s, {'count': 7, 'shares': {'c_level': 14, 'head': 29, 'manager': 14, 'individual': 43}})
        self.assertEqual(sum(s['shares'].values()), 100)

    def test_who_counts(self):
        for pos in ('head', 'head', 'manager', 'individual', 'c_level'):
            _answered(self.org, pos)
        # Never counted: another organisation, a super, a source user, a referral partner, an archived
        # and a revoked team member, and somebody who has not answered.
        for _ in range(5):
            _answered(self.other, 'c_level')
        _answered(None, 'c_level', role='reviewer', super_admin=True)
        _answered(self.org, 'c_level', role='source_partner')
        _answered(self.org, 'c_level', role='partner')
        _answered(self.org, 'c_level', archived_at=timezone.now(), is_active=False)
        _answered(self.org, 'c_level', is_active=False)
        _answered(self.org, '')
        make_admin('admin', owning_org=self.org)          # no profile row at all
        # Counted whatever their group: a mentor login, a "No group" member, an organisation admin.
        _answered(self.org, 'individual', role='mentor')
        _answered(self.org, 'individual', role='member')
        _answered(self.org, 'c_level', role='org_admin')
        self.assertEqual(volunteer_positions.counts_for_organisation(self.org.id),
                         {'c_level': 2, 'head': 2, 'manager': 1, 'individual': 3})

    def test_shares_always_sum_to_one_hundred(self):
        for counts in ({'c_level': 1, 'head': 1, 'manager': 1, 'individual': 0},
                       {'c_level': 1, 'head': 1, 'manager': 1, 'individual': 3},
                       {'c_level': 5, 'head': 0, 'manager': 0, 'individual': 0},
                       {'c_level': 2, 'head': 2, 'manager': 2, 'individual': 3}):
            with self.subTest(counts=counts):
                shares = volunteer_positions.shares(counts)
                self.assertEqual(sum(shares.values()), 100)
                total = sum(counts.values())
                for k in KEYS:
                    self.assertLessEqual(abs(shares[k] - counts[k] * 100 / total), 1)
        # A three-way tie of thirds: the extra point goes to the higher level.
        self.assertEqual(volunteer_positions.shares({'c_level': 1, 'head': 1, 'manager': 1, 'individual': 0}),
                         {'c_level': 34, 'head': 33, 'manager': 33, 'individual': 0})


@override_settings(**API, SPONSOR_POOL_ENABLED=True)
class TestTheTrustPage(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = make_org()
        cls.other = make_org()
        cls.names = []
        for i, pos in enumerate(('c_level', 'head', 'head', 'manager', 'individual')):
            cls.names.append(_answered(cls.org, pos, name=f'Volunteer Sample {i}').name)
        for i in range(6):
            _answered(cls.other, 'individual', name=f'Elsewhere Sample {i}')
        cls.sponsor = cls._sponsor('req69-sp', cls.org)

    @classmethod
    def _sponsor(cls, uid, *orgs):
        sponsor = Sponsor.objects.create(supabase_user_id=uid, name='Sample Sponsor', email=f'{uid}@x.test',
                                         phone='0123', source='friend', consent_at=timezone.now(),
                                         status='approved')
        for org in orgs:
            SponsorProgrammeMembership.objects.create(sponsor=sponsor, programme=make_programme(organisation=org),
                                                      status='approved')
        return sponsor

    def _volunteers(self, sponsor):
        r = authed_client(sponsor.supabase_user_id).get(TRUST)
        self.assertEqual(r.status_code, 200, r.content)
        return r.json()['volunteers']

    def test_the_sponsors_own_organisation_and_totals_only(self):
        v = self._volunteers(self.sponsor)
        self.assertEqual(v, {'count': 5, 'shares': {'c_level': 20, 'head': 40, 'manager': 20, 'individual': 20}})
        blob = json.dumps(v)
        for name in self.names:
            self.assertNotIn(name, blob)
        self.assertEqual(set(v), {'count', 'shares'})
        self.assertEqual(set(v['shares']), set(KEYS))

    def test_below_five_the_api_sends_no_figures(self):
        StaffProfile.objects.filter(partner_admin__owning_organisation=self.org,
                                    highest_position='manager').update(highest_position='')
        self.assertIsNone(self._volunteers(self.sponsor))

    def test_no_single_organisation_no_figures(self):
        self.assertIsNone(self._volunteers(self._sponsor('req69-none')))
        self.assertIsNone(self._volunteers(self._sponsor('req69-two', self.org, self.other)))
        pending = self._sponsor('req69-pending')
        SponsorProgrammeMembership.objects.create(sponsor=pending, programme=make_programme(organisation=self.org),
                                                  status='pending')
        self.assertIsNone(self._volunteers(pending))
