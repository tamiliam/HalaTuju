"""Request #69 (2026-11-17): "Highest position held" on staff profiles, with a sponsor summary.

- the field and its four choices (blank = not given);
- `PATCH admin/me/` saves, clears and refuses it, and makes the profile row when there is none — only the
  caller's own row; a super, a source user or a referral partner is never asked and is refused (review
  rounds 2 and 3);
- the Team person page serves it beside the job title (`test_t3_person_page.py` pins the key sets);
- the sponsor Trust page's `volunteers`: no figures below five answers; at five or more a BANDED count
  (never the exact one), the headline and the right shares (largest remainder, summing to 100) — the
  shares withheld when a level holds everyone or exactly one person; other organisations, supers,
  source users, archived, revoked and suspended (Suspend turns the login off) never count; paused
  reviewers and active people with a deactivated mentor link (stopped mentoring, "No group", Admin to
  Finance) do (review round 3);
- completion counts it for every kind (`test_profile_completion.py`).
"""
import json

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.scholarship import mentor_invite, staff_mentor, volunteer_positions
from apps.scholarship.models import Mentor, Sponsor, SponsorProgrammeMembership, StaffProfile
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

    def test_every_team_kind_may_answer_it(self):
        for role in ('org_admin', 'admin', 'reviewer', 'qc', 'finance', 'mentor', 'member'):
            with self.subTest(role=role):
                admin = make_admin(role, owning_org=self.org)
                self.assertTrue(authed_client(admin).get(ME).json()['asks_highest_position'])
                r = self._patch(admin, {'highest_position': 'individual'})
                self.assertEqual(r.status_code, 200, r.content)
                self.assertEqual(r.json()['highest_position'], 'individual')

    def test_a_source_user_or_referral_partner_is_never_asked_and_is_refused(self):
        for role in ('source_partner', 'partner'):
            with self.subTest(role=role):
                admin = make_admin(role, owning_org=self.org)
                self.assertFalse(authed_client(admin).get(ME).json()['asks_highest_position'])
                for value in ('head', ''):
                    r = self._patch(admin, {'highest_position': value})
                    self.assertEqual((r.status_code, r.json()['code']), (400, 'bad_highest_position'))
                self.assertFalse(StaffProfile.objects.filter(partner_admin=admin).exists())
                # A save without the field still works (the page never sends it for them).
                self.assertEqual(self._patch(admin, {'job_title': 'Coordinator'}).status_code, 200)
                self.assertEqual(StaffProfile.objects.get(partner_admin=admin).highest_position, '')

    def test_a_super_is_never_asked_and_is_refused(self):
        admin = make_admin('super', super_admin=True)
        self.assertFalse(volunteer_positions.asked(admin))
        self.assertFalse(authed_client(admin).get(ME).json()['asks_highest_position'])
        for value in ('head', ''):
            r = self._patch(admin, {'highest_position': value})
            self.assertEqual((r.status_code, r.json()['code']), (400, 'bad_highest_position'))
        self.assertFalse(StaffProfile.objects.filter(partner_admin=admin).exists())

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
        self.assertEqual(volunteer_positions.summary_for_organisation(self.org.id)['count_at_least'], 5)

    def test_the_count_is_banded_never_exact(self):
        for total, want in ((4, None), (5, 5), (9, 5), (10, 10), (19, 10), (20, 20), (49, 20), (50, 50),
                            (199, 100), (200, 200), (499, 200), (500, 500), (1234, 500)):
            with self.subTest(total=total):
                self.assertEqual(volunteer_positions.band(total), want)

    def test_shares_at_five_and_more(self):
        for pos in ['c_level'] * 2 + ['head'] * 4 + ['manager'] * 3 + ['individual'] * 5:
            _answered(self.org, pos)
        s = volunteer_positions.summary_for_organisation(self.org.id)
        # 2/14 = 14.29, 4/14 = 28.57, 3/14 = 21.43, 5/14 = 35.71 -> floors 14+28+21+35 = 98; the two
        # largest remainders (individual .71, head .57) get the two points left. 14 answers -> "10+".
        self.assertEqual(s, {'count_at_least': 10, 'senior_pct': 43,
                             'shares': {'c_level': 14, 'head': 29, 'manager': 21, 'individual': 36}})
        self.assertEqual(sum(s['shares'].values()), 100)
        self.assertNotIn('count', s)   # the exact count is never served

    def test_one_person_at_a_level_withholds_the_bars_but_not_the_headline(self):
        for pos in ('c_level', 'head', 'head', 'manager', 'manager', 'individual', 'individual'):
            _answered(self.org, pos)
        # 1/7 = 14.29, 2/7 = 28.57 x3 -> floors 14+28+28+28 = 98; head and manager (.57, the higher
        # levels first on the tie with individual) get the points: 14, 29, 29, 28 -> headline 43.
        self.assertEqual(volunteer_positions.summary_for_organisation(self.org.id),
                         {'count_at_least': 5, 'senior_pct': 43, 'shares': None})

    def test_everyone_at_one_level_withholds_the_bars(self):
        for _ in range(6):
            _answered(self.org, 'manager')
        self.assertEqual(volunteer_positions.summary_for_organisation(self.org.id),
                         {'count_at_least': 5, 'senior_pct': 0, 'shares': None})

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
        _answered(self.org, 'c_level', archived_at=timezone.now(), is_active=True)   # archived, still active
        lead = make_admin('org_admin', owning_org=self.org)                              # no profile row
        suspended = _answered(self.org, 'c_level', role='mentor', first_seen_at=timezone.now())
        self.assertEqual(mentor_invite.deactivate(lead, suspended.mentor, suspended), (True, None))  # Suspend
        suspended.refresh_from_db()
        self.assertFalse(suspended.is_active)                       # Suspend turns the login off
        _answered(self.org, '')
        make_admin('admin', owning_org=self.org)          # no profile row at all
        # Counted whatever their group: a mentor login, a "No group" member, an organisation admin.
        _answered(self.org, 'individual', role='mentor')
        _answered(self.org, 'individual', role='member')
        _answered(self.org, 'c_level', role='org_admin')
        _answered(self.org, 'manager', paused_at=timezone.now())                        # paused still counts
        self.assertEqual(volunteer_positions.counts_for_organisation(self.org.id),
                         {'c_level': 2, 'head': 2, 'manager': 2, 'individual': 3})

    def test_active_people_with_a_deactivated_mentor_link_still_count(self):
        # Review round 3: each keeps a Mentor row stamped deactivated, and each is still active team.
        lead = make_admin('org_admin', owning_org=self.org)                              # no profile row
        now = timezone.now()
        stopped = _answered(self.org, 'head', role='admin', first_seen_at=now,
                            mentor=Mentor.objects.create(organisation=self.org))
        self.assertEqual(staff_mentor.stop(lead, stopped.mentor, stopped), (0, None))  # Stop mentoring
        no_group = _answered(self.org, 'manager', role='mentor', first_seen_at=now)
        self.assertEqual(staff_mentor.remove_mentor_login(lead, no_group.mentor, no_group), (0, None))
        finance = _answered(self.org, 'individual', role='finance',                    # Admin -> Finance
                            mentor=Mentor.objects.create(organisation=self.org, deactivated_at=now))
        for person, role in ((stopped, 'admin'), (no_group, 'member'), (finance, 'finance')):
            with self.subTest(role=role):
                person.refresh_from_db()
                self.assertEqual((person.role, person.is_active), (role, True))
                self.assertIsNotNone(Mentor.objects.get(pk=person.mentor_id).deactivated_at)
        self.assertEqual(volunteer_positions.counts_for_organisation(self.org.id),
                         {'c_level': 0, 'head': 1, 'manager': 1, 'individual': 1})

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
        for i, pos in enumerate(('c_level', 'c_level', 'head', 'head', 'head', 'manager', 'manager')):
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

    def test_the_sponsors_own_organisation_banded_and_totals_only(self):
        v = self._volunteers(self.sponsor)
        # 7 answers: 2/7 = 28.57, 3/7 = 42.86, 2/7 = 28.57, 0 -> floors 28+42+28+0 = 98; head (.86) and
        # then c_level (.57, the higher level on the tie with manager) get the points. 7 -> "5+".
        self.assertEqual(v, {'count_at_least': 5, 'senior_pct': 72,
                             'shares': {'c_level': 29, 'head': 43, 'manager': 28, 'individual': 0}})
        blob = json.dumps(v)
        for name in self.names:
            self.assertNotIn(name, blob)
        self.assertEqual(set(v), {'count_at_least', 'senior_pct', 'shares'})
        self.assertEqual(set(v['shares']), set(KEYS))
        self.assertNotIn(7, [v['count_at_least'], v['senior_pct'], *v['shares'].values()])   # never exact

    def test_one_person_at_a_level_sends_no_bars(self):
        StaffProfile.objects.filter(pk=StaffProfile.objects.filter(
            partner_admin__owning_organisation=self.org, highest_position='head').first().pk,
        ).update(highest_position='individual')
        # 2/7, 2/7, 2/7, 1/7 -> 29, 29, 28, 14 (c_level and head take the tie) -> headline 58.
        self.assertEqual(self._volunteers(self.sponsor), {'count_at_least': 5, 'senior_pct': 58, 'shares': None})

    def test_below_five_the_api_sends_no_figures(self):
        StaffProfile.objects.filter(partner_admin__owning_organisation=self.org,
                                    highest_position__in=('manager', 'c_level')).update(highest_position='')
        self.assertIsNone(self._volunteers(self.sponsor))

    def test_no_single_organisation_no_figures(self):
        self.assertIsNone(self._volunteers(self._sponsor('req69-none')))
        self.assertIsNone(self._volunteers(self._sponsor('req69-two', self.org, self.other)))
        pending = self._sponsor('req69-pending')
        SponsorProgrammeMembership.objects.create(sponsor=pending, programme=make_programme(organisation=self.org),
                                                  status='pending')
        self.assertIsNone(self._volunteers(pending))
