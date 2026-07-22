"""Org-admin powers v1 — the 2026-07-15 batch (docs/plans/2026-07-15-org-admin-powers-v1-brief.md).

Proves the matrix (docs/scholarship/role-matrix.md) for the broadened organisation roles:
  - org_admin + qc WRITE (review-all) on any OWN-ORG application; cross-org still 404;
  - the QC recorder guard (whoever recorded a verdict can never QC that case);
  - assignment delegation to org_admin (own-org reviewer targets only);
  - sponsor-vetting migrated off the reviewer gate onto super/org_admin, and the
    sponsor LIST tightened to super/org_admin/admin (qc + reviewer refused).
"""
import datetime
import jwt
from unittest import mock

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.courses.models import PartnerAdmin, PartnerOrganisation, StudentProfile
from apps.scholarship.models import (
    AssignmentEvent, ScholarshipApplication, ScholarshipCohort, Sponsor,
)

TEST_JWT_SECRET = 'test-supabase-jwt-secret'

_VERDICT_OK = {'identity': 'pass', 'academic': 'pass', 'income': 'pass',
               'pathway': 'pass', 'overall': 'accept'}


# QC refuses to accept a case with no reporting date (owner 2026-07-23) - it sizes the
# bursary, so a missing one is no longer acceptable at the gate. A fresh-entrant date,
# matching the cohort year, so these suites' existing amount assertions are unchanged.
_QC_REPORTING_DATE = datetime.date(2026, 6, 8)


def _token(uid):
    return jwt.encode({'sub': uid, 'aud': 'authenticated', 'role': 'authenticated'},
                      TEST_JWT_SECRET, algorithm='HS256')


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org_a = PartnerOrganisation.objects.create(code='pow-a', name='Org A')
        cls.org_b = PartnerOrganisation.objects.create(code='pow-b', name='Org B')
        cls.cohort_a = ScholarshipCohort.objects.create(
            code='pow-ca', name='CA', year=2026, owning_organisation=cls.org_a)
        cls.cohort_b = ScholarshipCohort.objects.create(
            code='pow-cb', name='CB', year=2026, owning_organisation=cls.org_b)
        prof_a = StudentProfile.objects.create(
            supabase_user_id='pow-stud-a', nric='010101-14-0001', name='Stud A')
        prof_b = StudentProfile.objects.create(
            supabase_user_id='pow-stud-b', nric='010101-14-0002', name='Stud B')
        # Own-org app is pre-assigned to a reviewer so the assignment tests can exercise
        # the (unconditional) REASSIGN path without tripping the first-assign readiness gate.
        cls.rev = PartnerAdmin.objects.create(
            supabase_user_id='pow-rev', role='reviewer', is_active=True,
            owning_organisation=cls.org_a, name='Rev', email='prev@x.com')
        cls.app = ScholarshipApplication.objects.create(reporting_date=_QC_REPORTING_DATE, 
            cohort=cls.cohort_a, profile=prof_a, status='interviewed', assigned_to=cls.rev,
            ai_verdict_snapshot=[], officer_verdict={})
        cls.app_b = ScholarshipApplication.objects.create(reporting_date=_QC_REPORTING_DATE, 
            cohort=cls.cohort_b, profile=prof_b, status='interviewed',
            ai_verdict_snapshot=[], officer_verdict={})
        cls.super = PartnerAdmin.objects.create(
            supabase_user_id='pow-super', is_super_admin=True, is_active=True,
            name='Super', email='psuper@x.com')
        cls.oa = PartnerAdmin.objects.create(
            supabase_user_id='pow-oa', role='org_admin', is_active=True,
            owning_organisation=cls.org_a, name='OA', email='poa@x.com')
        cls.oa2 = PartnerAdmin.objects.create(
            supabase_user_id='pow-oa2', role='org_admin', is_active=True,
            owning_organisation=cls.org_a, name='OA2', email='poa2@x.com')
        cls.qc = PartnerAdmin.objects.create(
            supabase_user_id='pow-qc', role='qc', is_active=True,
            owning_organisation=cls.org_a, name='QC', email='pqc@x.com')
        cls.rev2 = PartnerAdmin.objects.create(
            supabase_user_id='pow-rev2', role='reviewer', is_active=True,
            owning_organisation=cls.org_a, name='Rev2', email='prev2@x.com')
        cls.admin = PartnerAdmin.objects.create(
            supabase_user_id='pow-admin', role='admin', is_active=True,
            owning_organisation=cls.org_a, name='Adm', email='padm@x.com')
        cls.oa_b = PartnerAdmin.objects.create(
            supabase_user_id='pow-oa-b', role='org_admin', is_active=True,
            owning_organisation=cls.org_b, name='OAB', email='poab@x.com')
        cls.rev_b = PartnerAdmin.objects.create(
            supabase_user_id='pow-rev-b', role='reviewer', is_active=True,
            owning_organisation=cls.org_b, name='RevB', email='prevb@x.com')

    def setUp(self):
        self.client = APIClient()

    def _auth(self, uid):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(uid)}')

    def _record_verdict(self, app_id):
        return self.client.post(
            f'/api/v1/admin/scholarship/applications/{app_id}/record-verdict/',
            {'officer_verdict': _VERDICT_OK}, format='json')

    def _qc(self, app_id, decision='accept'):
        return self.client.post(
            f'/api/v1/admin/scholarship/applications/{app_id}/qc-decision/',
            {'decision': decision}, format='json')


class TestOrgWideWrite(_Base):
    """org_admin + qc may act on ANY own-org application (review-all)."""
    def test_org_admin_records_verdict_own_org(self):
        with mock.patch('apps.scholarship.verdict_engine.build_verdict', return_value=[]):
            self._auth('pow-oa')
            r = self._record_verdict(self.app.id)
        self.assertEqual(r.status_code, 200)
        self.app.refresh_from_db()
        self.assertEqual(self.app.verdict_decided_by, 'poa@x.com')

    def test_qc_records_verdict_own_org(self):
        with mock.patch('apps.scholarship.verdict_engine.build_verdict', return_value=[]):
            self._auth('pow-qc')
            r = self._record_verdict(self.app.id)
        self.assertEqual(r.status_code, 200)

    def test_org_admin_cross_org_write_404(self):
        self._auth('pow-oa')
        r = self._record_verdict(self.app_b.id)
        self.assertEqual(r.status_code, 404)


class TestQcRecorderGuard(_Base):
    """Two-person control: the person who RECORDED the verdict can never QC it."""
    def test_recorder_cannot_qc_own_verdict(self):
        self.app.verdict_decided_by = 'poa@x.com'
        self.app.save(update_fields=['verdict_decided_by'])
        self._auth('pow-oa')
        r = self._qc(self.app.id)
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.json().get('code'), 'self_verdict_qc_forbidden')

    def test_recorder_match_is_case_insensitive(self):
        self.app.verdict_decided_by = 'POA@X.COM'
        self.app.save(update_fields=['verdict_decided_by'])
        self._auth('pow-oa')
        self.assertEqual(self._qc(self.app.id).status_code, 403)

    def test_other_org_admin_may_qc_the_recorded_case(self):
        self.app.verdict_decided_by = 'poa@x.com'
        self.app.save(update_fields=['verdict_decided_by'])
        with mock.patch('apps.scholarship.views_admin.build_verdict', return_value=[]):
            self._auth('pow-oa2')
            r = self._qc(self.app.id)
        self.assertEqual(r.status_code, 200)
        self.app.refresh_from_db()
        self.assertEqual(self.app.status, 'recommended')

    def test_qc_role_may_qc_another_recorders_case(self):
        self.app.verdict_decided_by = 'poa@x.com'
        self.app.save(update_fields=['verdict_decided_by'])
        with mock.patch('apps.scholarship.views_admin.build_verdict', return_value=[]):
            self._auth('pow-qc')
            r = self._qc(self.app.id)
        self.assertEqual(r.status_code, 200)

    def test_super_may_qc_own_recorded_verdict(self):
        # Super is the owner override — exempt from the recorder guard.
        self.app.verdict_decided_by = 'psuper@x.com'
        self.app.save(update_fields=['verdict_decided_by'])
        with mock.patch('apps.scholarship.views_admin.build_verdict', return_value=[]):
            self._auth('pow-super')
            r = self._qc(self.app.id)
        self.assertEqual(r.status_code, 200)

    def test_existing_self_assignment_guard_still_holds(self):
        # A qc who was the ASSIGNED reviewer (no verdict recorded yet) still can't QC.
        self.app.assigned_to = self.qc
        self.app.verdict_decided_by = ''
        self.app.save(update_fields=['assigned_to', 'verdict_decided_by'])
        self._auth('pow-qc')
        r = self._qc(self.app.id)
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.json().get('code'), 'self_qc_forbidden')


class TestAssignmentDelegation(_Base):
    """An org_admin (re)assigns their OWN org's reviewers only."""
    def setUp(self):
        super().setUp()
        # A case may only change hands while a review is live (profile_complete/interviewing);
        # the fixture app is 'interviewed' (awaiting QC) so move it to an assignable status.
        ScholarshipApplication.objects.filter(pk=self.app.id).update(status='profile_complete')
        self.app.refresh_from_db()

    def _assign(self, app_id, reviewer_id):
        return self.client.post(
            f'/api/v1/admin/scholarship/applications/{app_id}/assign/',
            {'reviewer_id': reviewer_id}, format='json')

    def test_org_admin_reassigns_own_org_reviewer(self):
        self._auth('pow-oa')
        r = self._assign(self.app.id, self.rev2.id)
        self.assertEqual(r.status_code, 200)
        self.app.refresh_from_db()
        self.assertEqual(self.app.assigned_to_id, self.rev2.id)
        self.assertTrue(AssignmentEvent.objects.filter(application=self.app).exists())

    def test_org_admin_cross_org_reviewer_rejected(self):
        self._auth('pow-oa')
        r = self._assign(self.app.id, self.rev_b.id)
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json().get('code'), 'bad_assignee')

    def test_org_admin_super_target_rejected(self):
        self._auth('pow-oa')
        self.assertEqual(self._assign(self.app.id, self.super.id).status_code, 400)

    def test_org_admin_admin_target_rejected(self):
        # Only a role='reviewer' target — a view-all admin is not assignable by an org_admin.
        self._auth('pow-oa')
        self.assertEqual(self._assign(self.app.id, self.admin.id).status_code, 400)

    def test_org_admin_cross_org_app_404(self):
        self._auth('pow-oa')
        self.assertEqual(self._assign(self.app_b.id, self.rev_b.id).status_code, 404)

    def test_reviewer_cannot_assign(self):
        self._auth('pow-rev')
        self.assertEqual(self._assign(self.app.id, self.rev2.id).status_code, 403)


class TestSponsorMigration(_Base):
    """Sponsor vetting migrated to super/org_admin; the list to super/org_admin/admin."""
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.sponsor = Sponsor.objects.create(
            supabase_user_id='pow-spon', name='Sponsor', email='spon@x.com', status='pending')

    def _review(self, action='approve'):
        return self.client.post(
            f'/api/v1/admin/sponsors/{self.sponsor.id}/review/', {'action': action}, format='json')

    def test_org_admin_can_vet_sponsor(self):
        self._auth('pow-oa')
        r = self._review('approve')
        self.assertEqual(r.status_code, 200)
        self.sponsor.refresh_from_db()
        self.assertEqual(self.sponsor.status, 'approved')

    def test_reviewer_can_no_longer_vet_sponsor(self):
        # Regression on the OLD reviewer gate — vetting is now super/org_admin only.
        self._auth('pow-rev')
        self.assertEqual(self._review('approve').status_code, 403)

    def test_super_org_admin_admin_see_sponsor_list(self):
        for uid in ('pow-super', 'pow-oa', 'pow-admin'):
            self._auth(uid)
            self.assertEqual(self.client.get('/api/v1/admin/sponsors/').status_code, 200, uid)

    def test_qc_reviewer_refused_sponsor_list(self):
        for uid in ('pow-qc', 'pow-rev'):
            self._auth(uid)
            self.assertEqual(self.client.get('/api/v1/admin/sponsors/').status_code, 403, uid)
