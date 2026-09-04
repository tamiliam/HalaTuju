"""Request #10 — Organisation → Reviewers: the table and the detail view.

BrightPath runs on 13 volunteer reviewers and had no way to look at one. Staff invites and revokes;
nothing showed what a person carries, how long cases sit with them, or how their cases ended.

Three claims carry the weight here, and each is asserted from more than one angle:

1. **No figure is inflated by a join.** Counting two multi-valued relations in one queryset
   multiplies them, and `Sum(distinct=True)` — the reflex cure — is wrong for a sum. The workload
   builder groups ONE query in Python instead, so the class of bug is absent rather than guarded;
   `test_two_relations_do_not_inflate_each_other` is what would catch a regression to `annotate()`.

2. **A rejection is only an OVERTURN when the reviewer's own verdict said accept.** Both halves of
   this were got wrong before the owner read a real record, and both mistakes had the same shape —
   reading a stored field as if it answered a question about a person:
     - excluding cases whose verdict somebody else recorded erased work a reviewer had genuinely
       done (app #13: assigned to Balan, HE interviewed and wrote it up, the owner clicked);
     - keying the decline/overturn split on `rejected_by` inverted the common case, because a
       reviewer's decline ALWAYS routes through QC and QC accepting it stamps the QC's name. That
       mislabelled 6 of 13 rejections, telling five volunteers they had been overruled.
   The split now reads `officer_verdict.overall`, and red — an accusation that somebody overruled
   this person — requires positive evidence rather than an absence.

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
            'open_now', 'completed', 'turnaround_days', 'paused', 'paused_at',
            'programme_id', 'programme_name'})

    def test_the_gift_column_is_back_because_its_own_trigger_fired(self):
        """⚠ THIS TEST USED TO ASSERT THE OPPOSITE, and the reason it flipped is the point.

        Owner, 2026-08-02: *"with one programme the column could only say one thing. It comes
        back when a second programme exists."* A second gift was created on 2026-09-03, so the
        condition that ruling NAMED has fired — this is not somebody quietly reversing a
        decision, it is the decision's own clause.

        It is ONE gift, not a list (`programme_id`), per the model's ruling: with two gifts
        "NULL = both" covers every case, and a person covering two of three would need a join
        table. That limit is unreachable until a third gift exists.
        """
        self._auth('rv-oa')
        row = self.client.get(LIST).json()['reviewers'][0]
        self.assertIn('programme_id', row)
        self.assertNotIn('programmes', row, 'one gift, not a list — see the model docstring')

    def test_a_reviewer_with_no_gift_reads_as_EVERY_gift_not_as_a_blank_value(self):
        """⚠ NULL IS THE PERMISSIVE DEFAULT and there is NO BACKFILL — every one of the 17
        org-scoped staff on production still has it. The payload must let the screen say "every
        gift" rather than render an empty cell that reads as missing data."""
        self._auth('rv-oa')
        row = self.client.get(LIST).json()['reviewers'][0]
        self.assertIsNone(row['programme_id'])
        self.assertEqual(row['programme_name'], '')

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

    def test_a_case_SOMEBODY_ELSE_recorded_the_verdict_on_still_counts(self):
        # ⚠ REVERSED 2026-08-02, and production is why. The first cut excluded these, to keep another
        # person's judgement off a volunteer's record. But application #13 was assigned to Balan, HE
        # interviewed the student and submitted his findings, and only the final click was the
        # owner's — excluding it erased a case he genuinely reviewed. The review is his; who pressed
        # the button belongs in the audit trail.
        self._app(reviewer=self.reviewer, status='recommended', decided_days_ago=3,
                  decided_by='dina@rv.test')
        self._auth('rv-oa')
        row = next(x for x in self.client.get(LIST).json()['reviewers'] if x['name'] == 'Anand')
        self.assertEqual(row['completed'], 1)
        d = self.client.get(f'{LIST}{self.reviewer.id}/').json()
        self.assertEqual(d['recommended'], 1)
        self.assertNotIn('decided_by_other', d)   # the exclusion, and its dead-end footnote, are gone

    def test_a_QC_ACCEPTING_a_decline_is_still_the_REVIEWERS_decline(self):
        # ⚠ THE BUG THAT SHIPPED, 2026-08-02. Keying the split on `rejected_by` looked right and was
        # backwards: a reviewer's decline ALWAYS routes through QC, and QC accepting it stamps
        # `rejected_by` with the QC's name. So a rejector who is not the reviewer is the ORDINARY
        # case. It mislabelled 6 of BrightPath's 13 rejections — telling five volunteers they had
        # been overruled when they had declined a student and been agreed with. Vanitha's #56 is
        # this exact shape, and the owner spotted it by reading her record.
        app = self._app(reviewer=self.reviewer, status='rejected', decided_days_ago=5,
                        nric_seed='31')
        app.rejected_by = self.oa.email                       # QC/org_admin upheld it
        app.officer_verdict = {'overall': 'decline'}          # ...but the REVIEWER declined
        app.save(update_fields=['rejected_by', 'officer_verdict'])
        # Bite the guard: reading `rejected_by` instead of the verdict flips this to red.
        self._auth('rv-oa')
        d = self.client.get(f'{LIST}{self.reviewer.id}/').json()
        self.assertEqual(d['declined'], 1)
        self.assertEqual(d['rejected_after_review'], 0)

    def test_an_OVERTURN_is_a_recommend_that_was_rejected_anyway(self):
        # The only shape that earns the red band: the reviewer said ACCEPT and the student was
        # rejected regardless. Balan's #71 and Kalaiyarasi's #21 are the only two on production.
        app = self._app(reviewer=self.reviewer, status='rejected', decided_days_ago=4,
                        nric_seed='32')
        app.rejected_by = self.oa.email
        app.officer_verdict = {'overall': 'accept'}
        app.save(update_fields=['rejected_by', 'officer_verdict'])
        self._auth('rv-oa')
        d = self.client.get(f'{LIST}{self.reviewer.id}/').json()
        self.assertEqual(d['rejected_after_review'], 1)
        self.assertEqual(d['declined'], 0)

    def test_an_UNRECORDED_verdict_is_never_called_an_overturn(self):
        # Red is an accusation — that somebody overruled this reviewer — so it needs positive
        # evidence. A blank or draft verdict falls to their own decline rather than to a claim
        # the data does not support.
        for seed, verdict in (('33', {}), ('34', {'overall': ''})):
            app = self._app(reviewer=self.reviewer2, status='rejected', decided_days_ago=3,
                            nric_seed=seed)
            app.rejected_by = self.oa.email
            app.officer_verdict = verdict
            app.save(update_fields=['rejected_by', 'officer_verdict'])
        self._auth('rv-oa')
        d = self.client.get(f'{LIST}{self.reviewer2.id}/').json()
        self.assertEqual(d['declined'], 2)
        self.assertEqual(d['rejected_after_review'], 0)

    def test_a_case_sitting_with_QC_is_its_OWN_band(self):
        # Without it the bar falls short of the Completed figure printed directly above it — which
        # is what production did: Yuvarajan read Completed 6 over a bar totalling 5.
        self._app(reviewer=self.reviewer, status='interviewed', decided_days_ago=1, nric_seed='34')
        self._auth('rv-oa')
        d = self.client.get(f'{LIST}{self.reviewer.id}/').json()
        self.assertEqual(d['awaiting_qc'], 1)

    def test_the_bands_account_for_every_decided_case(self):
        # ⚠ THE ARITHMETIC GUARD. The four bands must PARTITION the decided cases, so the bar can
        # never disagree with the number above it. A new status that escapes all four fails here
        # instead of silently shrinking the bar.
        self._app(reviewer=self.reviewer, status='awarded', decided_days_ago=9, nric_seed='41')
        self._app(reviewer=self.reviewer, status='rejected', decided_days_ago=8, nric_seed='42')
        self._app(reviewer=self.reviewer, status='interviewed', decided_days_ago=7, nric_seed='43')
        self._app(reviewer=self.reviewer, status='profile_complete', nric_seed='44')  # still open
        self._auth('rv-oa')
        d = self.client.get(f'{LIST}{self.reviewer.id}/').json()
        self.assertEqual(
            d['recommended'] + d['declined'] + d['rejected_after_review'] + d['awaiting_qc'],
            d['completed'])
        self.assertEqual(d['open_now'], 1)

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


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestWhichGiftAReviewerCovers(TestCase):
    """S-ASSIGN, 2026-09-04. Reviewers had NO gift field at all.

    ⚠ IT IS A NARROWING, NOT A FENCE, and every test here is written to keep it one. The org
    boundary is `_org_scoped`; this only decides who is OFFERED a case. NULL means EVERY gift —
    the permissive default all 17 org-scoped staff on production still have, with no backfill.
    """

    @classmethod
    def setUpTestData(cls):
        from apps.scholarship.models import Programme
        cls.org = PartnerOrganisation.objects.create(code='gv', name='Gift Org')
        cls.other = PartnerOrganisation.objects.create(code='gv2', name='Other Org')
        cls.flagship = Programme.objects.create(
            organisation=cls.org, code='gv-flag', name_en='Flagship Bursary')
        # Created switched OFF — the real Sabah shape. A gift is staffed before it opens, which
        # is exactly why the choices list must not filter on `is_active`.
        cls.sabah = Programme.objects.create(
            organisation=cls.org, code='gv-sabah', name_en='Sabah Bursary', is_active=False)
        cls.foreign_gift = Programme.objects.create(
            organisation=cls.other, code='gv-x', name_en='Another Tenant Gift')

        cls.oa = PartnerAdmin.objects.create(
            supabase_user_id='gv-oa', role='org_admin', is_active=True,
            owning_organisation=cls.org, name='Dina', email='dina@gv.test')
        cls.plain_admin = PartnerAdmin.objects.create(
            supabase_user_id='gv-ad', role='admin', is_active=True,
            owning_organisation=cls.org, name='Kulaly', email='kulaly@gv.test')
        cls.reviewer = PartnerAdmin.objects.create(
            supabase_user_id='gv-r1', role='reviewer', is_active=True,
            owning_organisation=cls.org, name='Anand', email='anand@gv.test')
        cls.foreign_reviewer = PartnerAdmin.objects.create(
            supabase_user_id='gv-x', role='reviewer', is_active=True,
            owning_organisation=cls.other, name='Intruder', email='x@gv2.test')

    def setUp(self):
        self.client = APIClient()

    def _auth(self, uid):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(uid)}')

    def _set(self, reviewer, programme_id):
        return self.client.post(f'{LIST}{reviewer.id}/programme/',
                                {'programme_id': programme_id}, format='json')

    def test_it_records_the_gift(self):
        self._auth('gv-oa')
        r = self._set(self.reviewer, self.sabah.id)
        self.assertEqual(r.status_code, 200, r.content)
        self.reviewer.refresh_from_db()
        self.assertEqual(self.reviewer.programme_id, self.sabah.id)

    def test_clearing_it_means_EVERY_gift_never_no_gift(self):
        """The only two states are "this gift" and "all of them". There is no third state in
        which a reviewer is offered nothing — that would strand a volunteer silently."""
        self._auth('gv-oa')
        self._set(self.reviewer, self.sabah.id)
        r = self._set(self.reviewer, None)
        self.assertEqual(r.status_code, 200, r.content)
        self.reviewer.refresh_from_db()
        self.assertIsNone(self.reviewer.programme_id)

    def test_a_gift_that_is_not_switched_on_yet_is_offered(self):
        """⚠ THE CASE THIS EXISTS FOR — a gift is staffed BEFORE it opens."""
        self._auth('gv-oa')
        codes = {p['code'] for p in self.client.get(LIST).json()['programmes']}
        self.assertIn('gv-sabah', codes)

    def test_another_tenants_gift_is_404_never_403(self):
        # A 403 would confirm the other tenant's gift exists.
        self._auth('gv-oa')
        self.assertEqual(self._set(self.reviewer, self.foreign_gift.id).status_code, 404)
        self.reviewer.refresh_from_db()
        self.assertIsNone(self.reviewer.programme_id)

    def test_another_tenants_reviewer_is_404_never_403(self):
        self._auth('gv-oa')
        self.assertEqual(self._set(self.foreign_reviewer, self.flagship.id).status_code, 404)

    def test_a_plain_admin_may_READ_the_surface_but_not_set_this(self):
        """⚠ NARROWER THAN READING IT, exactly like pause. `admin` and `finance` may look at
        the reviewers list; deciding who gets which work is staff management."""
        self._auth('gv-ad')
        self.assertEqual(self.client.get(LIST).status_code, 200)
        self.assertEqual(self._set(self.reviewer, self.flagship.id).status_code, 403)

    def test_a_reviewer_cannot_set_their_own(self):
        self._auth('gv-r1')
        self.assertEqual(self._set(self.reviewer, self.flagship.id).status_code, 403)
