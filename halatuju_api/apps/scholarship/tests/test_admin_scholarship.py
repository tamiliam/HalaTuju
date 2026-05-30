"""Tests for the MyNadi admin API + AI profile drafting (Sprint 6a)."""
from unittest.mock import patch

import jwt
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.courses.models import PartnerAdmin, StudentProfile
from apps.scholarship.models import (
    ApplicantDocument, Referee, ScholarshipApplication, ScholarshipCohort, SponsorProfile,
)

TEST_JWT_SECRET = 'test-supabase-jwt-secret'
ADMIN = 'admin-uid'
STUDENT = 'student-uid'


def _token(uid):
    return jwt.encode(
        {'sub': uid, 'aud': 'authenticated', 'role': 'authenticated'},
        TEST_JWT_SECRET, algorithm='HS256',
    )


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestAdminScholarship(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = PartnerAdmin.objects.create(
            supabase_user_id=ADMIN, is_super_admin=True, is_active=True,
            name='Admin', email='admin@example.com',
        )
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)
        cls.profile = StudentProfile.objects.create(
            supabase_user_id='stud-prof', nric='030101-14-1234', name='Priya', school='SMK X',
            # academic + financial data is canonical on the profile
            grades={f'sub{i}': 'A' for i in range(10)},
            household_income=2500, receives_str=True,
        )
        cls.app = ScholarshipApplication.objects.create(
            cohort=cls.cohort, profile=cls.profile, status='shortlisted', bucket='A',
            aspirations='Become an auditor', justification='Low income family',
        )

    def setUp(self):
        self.client = APIClient()

    def _auth(self, uid):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(uid)}')

    def test_non_admin_forbidden(self):
        self._auth(STUDENT)
        r = self.client.get('/api/v1/admin/scholarship/applications/')
        self.assertEqual(r.status_code, 403)

    def test_requires_auth(self):
        r = self.client.get('/api/v1/admin/scholarship/applications/')
        self.assertEqual(r.status_code, 401)

    def test_admin_list(self):
        self._auth(ADMIN)
        r = self.client.get('/api/v1/admin/scholarship/applications/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['total_count'], 1)
        self.assertEqual(r.json()['applications'][0]['name'], 'Priya')

    def test_admin_list_filter_bucket(self):
        self._auth(ADMIN)
        r = self.client.get('/api/v1/admin/scholarship/applications/?bucket=B')
        self.assertEqual(r.json()['total_count'], 0)

    def test_admin_detail(self):
        self._auth(ADMIN)
        r = self.client.get(f'/api/v1/admin/scholarship/applications/{self.app.id}/')
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body['aspirations'], 'Become an auditor')
        self.assertEqual(body['name'], 'Priya')
        self.assertIn('documents', body)
        self.assertIn('referees', body)
        self.assertIsNone(body['sponsor_profile'])

    @patch('apps.scholarship.views_admin.generate_sponsor_profile',
           return_value={'markdown': '# Priya\nA strong candidate.', 'model_used': 'gemini-2.5-flash'})
    def test_generate_profile(self, _mock):
        self._auth(ADMIN)
        r = self.client.post(f'/api/v1/admin/scholarship/applications/{self.app.id}/generate-profile/')
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body['status'], 'draft')
        self.assertIn('strong candidate', body['draft_markdown'])
        self.assertEqual(body['model_used'], 'gemini-2.5-flash')

    @patch('apps.scholarship.views_admin.generate_sponsor_profile', return_value={'error': 'AI down'})
    def test_generate_profile_ai_error(self, _mock):
        self._auth(ADMIN)
        r = self.client.post(f'/api/v1/admin/scholarship/applications/{self.app.id}/generate-profile/')
        self.assertEqual(r.status_code, 503)

    def test_edit_and_publish(self):
        SponsorProfile.objects.create(application=self.app, draft_markdown='draft text')
        self._auth(ADMIN)
        r = self.client.put(
            f'/api/v1/admin/scholarship/applications/{self.app.id}/profile/',
            {'edited_markdown': 'edited text', 'status': 'approved'}, format='json',
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['edited_markdown'], 'edited text')
        self.assertEqual(r.json()['status'], 'approved')
        self.assertEqual(r.json()['current_markdown'], 'edited text')
        r2 = self.client.post(f'/api/v1/admin/scholarship/applications/{self.app.id}/publish/')
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r2.json()['status'], 'published')

    def test_publish_nothing_400(self):
        SponsorProfile.objects.create(application=self.app)  # empty draft + edited
        self._auth(ADMIN)
        r = self.client.post(f'/api/v1/admin/scholarship/applications/{self.app.id}/publish/')
        self.assertEqual(r.status_code, 400)

    # ── S11a: verify & accept ──────────────────────────────────────────────
    def _verify_url(self):
        return f'/api/v1/admin/scholarship/applications/{self.app.id}/verify-accept/'

    def _complete_app(self):
        """Phase C: the accept-gate now hard-requires a complete profile.
        Satisfy all 7 completeness parts on self.app."""
        from apps.scholarship.models import Consent, FundingNeed
        self.profile.student_signals = {'field_interest': {'it': 5}}
        self.profile.address = 'No. 1 Jalan ABC'
        self.profile.postal_code = '62100'
        self.profile.city = 'Putrajaya'
        self.profile.save()
        ScholarshipApplication.objects.filter(pk=self.app.id).update(plans='Study hard')
        FundingNeed.objects.create(application=self.app, categories=['living'], programme_months=36)
        for dt in ('ic', 'results_slip', 'parent_ic', 'str'):
            ApplicantDocument.objects.create(application=self.app, doc_type=dt, storage_path=f'x/{dt}')
        Consent.objects.create(application=self.app, version='t', is_active=True)

    def test_verify_accept_locks_nric_and_advances(self):
        self._complete_app()
        self._auth(ADMIN)
        r = self.client.post(
            self._verify_url(),
            {'checklist': {'nric': True, 'name': True, 'results': True, 'document': True}},
            format='json',
        )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body['status'], 'accepted')
        self.assertTrue(body['nric_verified'])
        self.assertEqual(body['verified_by'], 'admin@example.com')
        self.assertIsNotNone(body['verified_at'])
        self.assertTrue(body['verify_checklist']['document'])
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.nric_verified)  # NRIC is now locked

    def test_verify_accept_only_shortlisted(self):
        ScholarshipApplication.objects.filter(pk=self.app.id).update(status='submitted')
        self._auth(ADMIN)
        r = self.client.post(self._verify_url())
        self.assertEqual(r.status_code, 400)
        self.profile.refresh_from_db()
        self.assertFalse(self.profile.nric_verified)

    def test_verify_accept_nric_conflict(self):
        # Soft-NRIC: another profile already has this NRIC verified → 409 (TD-054).
        # Must be complete to pass the Phase C accept-gate and reach the NRIC check.
        self._complete_app()
        StudentProfile.objects.create(
            supabase_user_id='other-uid', nric='030101-14-1234', nric_verified=True,
        )
        self._auth(ADMIN)
        r = self.client.post(self._verify_url())
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.json().get('code'), 'nric_conflict')
        self.profile.refresh_from_db()
        self.assertFalse(self.profile.nric_verified)

    def test_verify_accept_requires_admin(self):
        self._auth(STUDENT)
        r = self.client.post(self._verify_url())
        self.assertEqual(r.status_code, 403)

    def test_mentoring_toggle(self):
        self._auth(ADMIN)
        r = self.client.patch(
            f'/api/v1/admin/scholarship/applications/{self.app.id}/',
            {'mentoring_candidate': True}, format='json',
        )
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()['mentoring_candidate'])
        self.app.refresh_from_db()
        self.assertTrue(self.app.mentoring_candidate)

    # ── S5b: admin records the referee at verify-&-accept ───────────────────
    def _referees_url(self):
        return f'/api/v1/admin/scholarship/applications/{self.app.id}/referees/'

    def test_admin_list_referees_empty(self):
        self._auth(ADMIN)
        r = self.client.get(self._referees_url())
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['referees'], [])

    def test_admin_add_referee(self):
        self._auth(ADMIN)
        r = self.client.post(
            self._referees_url(),
            {'name': 'Cikgu Devi', 'role': 'teacher', 'relationship': 'class teacher',
             'phone': '0123456789', 'email': 'devi@smkx.edu.my'},
            format='json',
        )
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json()['name'], 'Cikgu Devi')
        self.assertEqual(Referee.objects.filter(application=self.app).count(), 1)

    def test_admin_add_referee_requires_name(self):
        self._auth(ADMIN)
        r = self.client.post(self._referees_url(), {'role': 'teacher'}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_admin_list_after_add(self):
        Referee.objects.create(application=self.app, name='Mr Tan', role='counsellor')
        self._auth(ADMIN)
        r = self.client.get(self._referees_url())
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json()['referees']), 1)
        self.assertEqual(r.json()['referees'][0]['name'], 'Mr Tan')

    def test_admin_delete_referee(self):
        ref = Referee.objects.create(application=self.app, name='Mr Tan')
        self._auth(ADMIN)
        r = self.client.delete(f'{self._referees_url()}{ref.id}/')
        self.assertEqual(r.status_code, 204)
        self.assertFalse(Referee.objects.filter(pk=ref.id).exists())

    def test_admin_delete_referee_wrong_application_404(self):
        """A referee id that belongs to a different application is not deletable here."""
        other_cohort = ScholarshipCohort.objects.create(code='c2', name='B40-2', year=2027)
        other_app = ScholarshipApplication.objects.create(
            cohort=other_cohort, profile=self.profile, status='shortlisted',
        )
        ref = Referee.objects.create(application=other_app, name='Someone Else')
        self._auth(ADMIN)
        r = self.client.delete(f'{self._referees_url()}{ref.id}/')
        self.assertEqual(r.status_code, 404)
        self.assertTrue(Referee.objects.filter(pk=ref.id).exists())

    def test_referee_endpoints_require_admin(self):
        self._auth(STUDENT)
        self.assertEqual(self.client.get(self._referees_url()).status_code, 403)
        self.assertEqual(
            self.client.post(self._referees_url(), {'name': 'X'}, format='json').status_code, 403,
        )

    # ── S13: admin re-runs Vision OCR on an existing IC document ────────────
    def _rerun_vision_url(self, doc_id):
        return f'/api/v1/admin/scholarship/applications/{self.app.id}/documents/{doc_id}/re-run-vision/'

    @patch('apps.scholarship.vision.run_vision_for_document')
    def test_admin_rerun_vision_on_ic(self, mock_vision):
        from django.utils import timezone as _tz

        def update_doc(doc):
            doc.vision_nric = '030101-14-1234'
            doc.vision_name = 'PRIYA D/O KRISHNAN'
            doc.vision_run_at = _tz.now()
            doc.vision_error = ''
            doc.save(update_fields=['vision_nric', 'vision_name', 'vision_run_at', 'vision_error'])
            return {'nric': '030101-14-1234', 'name': 'PRIYA D/O KRISHNAN', 'error': None}
        mock_vision.side_effect = update_doc
        ic = ApplicantDocument.objects.create(application=self.app, doc_type='ic', storage_path='ic/abc')
        self._auth(ADMIN)
        r = self.client.post(self._rerun_vision_url(ic.id))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(mock_vision.called)
        body = r.json()
        self.assertEqual(body['vision_nric'], '030101-14-1234')
        self.assertEqual(body['vision_name'], 'PRIYA D/O KRISHNAN')

    def test_admin_rerun_vision_rejects_non_ic(self):
        results = ApplicantDocument.objects.create(application=self.app, doc_type='results_slip', storage_path='r/abc')
        self._auth(ADMIN)
        r = self.client.post(self._rerun_vision_url(results.id))
        self.assertEqual(r.status_code, 400)

    def test_admin_rerun_vision_404_for_wrong_application(self):
        other_cohort = ScholarshipCohort.objects.create(code='c3', name='B40-3', year=2028)
        other_app = ScholarshipApplication.objects.create(cohort=other_cohort, profile=self.profile, status='shortlisted')
        ic = ApplicantDocument.objects.create(application=other_app, doc_type='ic', storage_path='ic/zzz')
        self._auth(ADMIN)
        r = self.client.post(self._rerun_vision_url(ic.id))
        self.assertEqual(r.status_code, 404)

    def test_admin_rerun_vision_requires_admin(self):
        ic = ApplicantDocument.objects.create(application=self.app, doc_type='ic', storage_path='ic/abc')
        self._auth(STUDENT)
        r = self.client.post(self._rerun_vision_url(ic.id))
        self.assertEqual(r.status_code, 403)
