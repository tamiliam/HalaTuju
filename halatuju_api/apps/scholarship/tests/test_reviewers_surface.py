"""Request #10 — Organisation → Reviewers: the table and the detail view.

BrightPath runs on 13 volunteer reviewers and had no way to look at one. Staff invites and revokes;
nothing showed what a person carries, how long cases sit with them, or how their cases ended.

Three claims carry the weight here, and each is asserted from more than one angle:

1. **No figure is inflated by a join.** Counting two multi-valued relations in one queryset
   multiplies them, and `Sum(distinct=True)` — the reflex cure — is wrong for a sum. The workload
   builder groups ONE query in Python instead, so the class of bug is absent rather than guarded;
   `test_two_relations_do_not_inflate_each_other` is what would catch a regression to `annotate()`.

2. **A decision counts for the reviewer only when THEY recorded it.** An org_admin or qc may record
   a verdict on somebody else's case (3 of BrightPath's 65 today). Attributing that to the assignee
   would put another person's judgement on a volunteer's record.

3. **The home address never leaves `ReviewerProfile`.** Showing an org_admin a volunteer's phone is
   a deliberate widening for assignment; their home address is not, and the payload's exact key set
   is pinned so it cannot arrive later by accident.
"""
import datetime
from unittest import mock

import jwt
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.courses.models import PartnerAdmin, PartnerOrganisation, StudentProfile
from apps.scholarship.models import (
    DecisionReopen, ReviewerProfile, ScholarshipApplication, ScholarshipCohort,
)

TEST_JWT_SECRET = 'test-supabase-jwt-secret'
LIST = '/api/v1/admin/reviewers/'


def _token(uid):
    return jwt.encode({'sub': uid, 'aud': 'authenticated', 'role': 'authenticated'},
                      TEST_JWT_SECRET, algorithm='HS256')


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = PartnerOrganisation.objects.create(code='rv', name='Reviewers Org')
        cls.other = PartnerOrganisation.objects.create(code='rv2', name='Other Org')
        cls.cohort = ScholarshipCohort.objects.create(
            code='rv-2026', name='RV', year=2026, owning_organisation=cls.org)
        cls.other_cohort = ScholarshipCohort.objects.create(
            code='rv2-2026', name='RV2', year=2026, owning_organisation=cls.other)

        cls.oa = PartnerAdmin.objects.create(
            supabase_user_id='rv-oa', role='org_admin', is_active=True,
            owning_organisation=cls.org, name='Dina', email='dina@rv.test')
        cls.reviewer = PartnerAdmin.objects.create(
            supabase_user_id='rv-r1', role='reviewer', is_active=True,
            owning_organisation=cls.org, name='Anand', email='anand@rv.test')
        cls.reviewer2 = PartnerAdmin.objects.create(
            supabase_user_id='rv-r2', role='reviewer', is_active=True,
            owning_organisation=cls.org, name='Kavitha', email='kavitha@rv.test')
        cls.foreign_reviewer = PartnerAdmin.objects.create(
            supabase_user_id='rv-x', role='reviewer', is_active=True,
            owning_organisation=cls.other, name='Intruder', email='x@rv2.test')
        cls.revoked = PartnerAdmin.objects.create(
            supabase_user_id='rv-off', role='reviewer', is_active=False,
            owning_organisation=cls.org, name='Gone', email='gone@rv.test')
        cls.super = PartnerAdmin.objects.create(
            supabase_user_id='rv-su', is_super_admin=True, is_active=True,
            name='Super', email='su@rv.test')

        ReviewerProfile.objects.create(
            partner_admin=cls.reviewer, highest_qualification='BSc', university='UM',
            graduation_year=2014, field_of_study='Social sciences',
            english_fluency='fluent', tamil_fluency='conversational', bm_fluency='',
            phone='+60 12-345 6789', street_address='12 Jalan Rahsia', city='Ipoh')

    def setUp(self):
        self.client = APIClient()

    def _auth(self, uid):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(uid)}')

    def _app(self, *, reviewer=None, status='profile_complete', decided_by=None,
             assigned_days_ago=10, decided_days_ago=None, cohort=None, nric_seed='01'):
        prof = StudentProfile.objects.create(
            supabase_user_id=f'stud-{nric_seed}-{timezone.now().timestamp()}',
            nric=f'0101{nric_seed}-14-0001', name=f'Stud {nric_seed}')
        now = timezone.now()
        app = ScholarshipApplication.objects.create(
            cohort=cohort or self.cohort, profile=prof, status=status,
            assigned_to=reviewer, assigned_at=now - datetime.timedelta(days=assigned_days_ago))
        if decided_days_ago is not None:
            app.verdict_decided_at = now - datetime.timedelta(days=decided_days_ago)
            app.verdict_decided_by = decided_by or (reviewer.email if reviewer else '')
            app.save(update_fields=['verdict_decided_at', 'verdict_decided_by'])
        return app


class TestTheTable(_Base):
    def test_it_lists_this_organisations_reviewers_only(self):
        self._auth('rv-oa')
        r = self.client.get(LIST)
        self.assertEqual(r.status_code, 200, r.content)
        names = {x['name'] for x in r.json()['reviewers']}
        self.assertEqual(names, {'Anand', 'Kavitha'})   # not the other org's, not the revoked one

    def test_a_super_sees_every_organisations_reviewers(self):
        self._auth('rv-su')
        names = {x['name'] for x in self.client.get(LIST).json()['reviewers']}
        self.assertIn('Intruder', names)

    def test_a_revoked_reviewer_is_absent(self):
        # Revoking is an account kill-switch; they cannot act, so they are not staff to look at.
        self._auth('rv-oa')
        self.assertNotIn('Gone', {x['name'] for x in self.client.get(LIST).json()['reviewers']})

    def test_the_row_key_set_is_exact(self):
        # An allowlist, pinned — a column added to PartnerAdmin cannot reach this screen by accident.
        self._auth('rv-oa')
        row = self.client.get(LIST).json()['reviewers'][0]
        self.assertEqual(set(row), {
            'id', 'name', 'email', 'role', 'languages',
            'open_now', 'completed', 'turnaround_days', 'paused'})

    def test_there_is_NO_programmes_key(self):
        # Owner, 2026-08-02: with one programme the column could only say one thing. It comes back
        # when a second programme exists; until then everyone serves the BrightPath Bursary.
        self._auth('rv-oa')
        self.assertNotIn('programmes', self.client.get(LIST).json()['reviewers'][0])

    def test_the_table_carries_NO_corrections_figure(self):
        # Owner decision, 2026-08-02: reopens appear on the detail page WITH their reasons, never as
        # a bare count beside a volunteer's name on a list somebody assigns work from.
        self._auth('rv-oa')
        body = self.client.get(LIST).content.decode()
        self.assertNotIn('correction', body.lower())

    def test_languages_come_from_the_reviewer_profile(self):
        self._auth('rv-oa')
        rows = {x['name']: x for x in self.client.get(LIST).json()['reviewers']}
        self.assertEqual(sorted(rows['Anand']['languages']), ['en', 'ta'])   # bm is '' — excluded
        self.assertEqual(rows['Kavitha']['languages'], [])                   # no profile at all


class TestTheFigures(_Base):
    def test_open_completed_and_outcomes(self):
        self._app(reviewer=self.reviewer, status='interviewing')
        self._app(reviewer=self.reviewer, status='profile_complete', nric_seed='02')
        self._app(reviewer=self.reviewer, status='recommended', decided_days_ago=4,
                  nric_seed='03')
        self._app(reviewer=self.reviewer, status='rejected', decided_days_ago=2, nric_seed='04')
        self._auth('rv-oa')
        row = next(x for x in self.client.get(LIST).json()['reviewers'] if x['name'] == 'Anand')
        self.assertEqual(row['open_now'], 2)
        self.assertEqual(row['completed'], 2)

    def test_a_verdict_recorded_by_SOMEBODY_ELSE_is_not_theirs(self):
        # The claim in the docstring, asserted directly: an org_admin recording on their case must
        # not land on the reviewer's record.
        self._app(reviewer=self.reviewer, status='recommended', decided_days_ago=3,
                  decided_by='dina@rv.test')
        self._auth('rv-oa')
        row = next(x for x in self.client.get(LIST).json()['reviewers'] if x['name'] == 'Anand')
        self.assertEqual(row['completed'], 0)
        d = self.client.get(f'{LIST}{self.reviewer.id}/').json()
        self.assertEqual(d['decided_by_other'], 1)

    def test_turnaround_is_a_MEDIAN_and_is_None_when_nothing_is_decided(self):
        self._auth('rv-oa')
        row = next(x for x in self.client.get(LIST).json()['reviewers'] if x['name'] == 'Kavitha')
        self.assertIsNone(row['turnaround_days'])   # not 0 — "no reviews yet" is not "instant"

        self._app(reviewer=self.reviewer2, status='recommended',
                  assigned_days_ago=20, decided_days_ago=18, nric_seed='05')   # 2 days
        self._app(reviewer=self.reviewer2, status='recommended',
                  assigned_days_ago=20, decided_days_ago=16, nric_seed='06')   # 4 days
        self._app(reviewer=self.reviewer2, status='recommended',
                  assigned_days_ago=20, decided_days_ago=0, nric_seed='07')    # 20 days
        row = next(x for x in self.client.get(LIST).json()['reviewers'] if x['name'] == 'Kavitha')
        self.assertEqual(row['turnaround_days'], 4.0)   # median, not the 8.7 mean the outlier gives

    def test_two_relations_do_not_inflate_each_other(self):
        # The join-fan-out trap. A reviewer with 3 applications AND 2 reopens must read 3 and 2 —
        # an annotate()-based count would read 6 of each. This is the test that catches a rewrite.
        apps = [self._app(reviewer=self.reviewer, status='recommended', decided_days_ago=3,
                          nric_seed=f'1{i}') for i in range(3)]
        for a in apps[:2]:
            DecisionReopen.objects.create(application=a, reviewer=self.reviewer,
                                          reason='check the band', resulted_in_change=True)
        self._auth('rv-oa')
        row = next(x for x in self.client.get(LIST).json()['reviewers'] if x['name'] == 'Anand')
        self.assertEqual(row['completed'], 3)
        self.assertEqual(len(self.client.get(f'{LIST}{self.reviewer.id}/').json()['reopens']), 2)

    def test_figures_are_org_fenced_for_a_non_super(self):
        # A super's own view of the same reviewer may legitimately be wider; an org_admin's must not
        # count another tenant's applications.
        self._app(reviewer=self.reviewer, status='recommended', decided_days_ago=3,
                  cohort=self.other_cohort, nric_seed='21')
        self._auth('rv-oa')
        row = next(x for x in self.client.get(LIST).json()['reviewers'] if x['name'] == 'Anand')
        self.assertEqual(row['completed'], 0)


class TestTheDetail(_Base):
    def test_reopens_carry_their_reason(self):
        app = self._app(reviewer=self.reviewer, status='recommended', decided_days_ago=3)
        DecisionReopen.objects.create(
            application=app, reviewer=self.reviewer, reopened_by='dina@rv.test',
            reason='Merit reason does not match the 5A- result on file.', resulted_in_change=True)
        self._auth('rv-oa')
        row = self.client.get(f'{LIST}{self.reviewer.id}/').json()['reopens'][0]
        self.assertIn('5A-', row['reason'])
        self.assertEqual(row['reopened_by'], 'dina@rv.test')

    def test_a_cancelled_reopen_is_NOT_a_correction(self):
        # Counting model B (owner, 2026-06-18): only a reopen that led to a changed decision counts.
        app = self._app(reviewer=self.reviewer, status='recommended', decided_days_ago=3)
        DecisionReopen.objects.create(application=app, reviewer=self.reviewer,
                                      reason='looked again, no change', resulted_in_change=False)
        self._auth('rv-oa')
        self.assertEqual(self.client.get(f'{LIST}{self.reviewer.id}/').json()['reopens'], [])

    def test_the_HOME_ADDRESS_never_appears(self):
        # The deliberate half-widening. Phone yes (assignment needs it), address no.
        self._auth('rv-oa')
        r = self.client.get(f'{LIST}{self.reviewer.id}/')
        body = r.content.decode()
        self.assertIn('+60 12-345 6789', body)
        self.assertNotIn('Jalan Rahsia', body)
        self.assertNotIn('Ipoh', body)
        self.assertNotIn('address', set(r.json()))

    def test_credentials_are_shown(self):
        self._auth('rv-oa')
        d = self.client.get(f'{LIST}{self.reviewer.id}/').json()
        self.assertEqual(d['qualification'], 'BSc')
        self.assertEqual(d['graduation_year'], 2014)

    def test_a_reviewer_with_no_profile_still_renders(self):
        self._auth('rv-oa')
        d = self.client.get(f'{LIST}{self.reviewer2.id}/').json()
        self.assertEqual(d['qualification'], '')
        self.assertIsNone(d['graduation_year'])


class TestTheFence(_Base):
    def test_a_cross_org_reviewer_is_404_not_403(self):
        # Never leak that another tenant's staff member exists.
        self._auth('rv-oa')
        self.assertEqual(
            self.client.get(f'{LIST}{self.foreign_reviewer.id}/').status_code, 404)

    def test_a_reviewer_cannot_open_the_surface(self):
        self._auth('rv-r1')
        self.assertEqual(self.client.get(LIST).status_code, 403)

    def test_anonymous_is_refused(self):
        self.assertIn(self.client.get(LIST).status_code, (401, 403))
