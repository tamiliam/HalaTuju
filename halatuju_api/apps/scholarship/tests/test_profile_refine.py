"""Phase D profile refine: engine (mocked Gemini) + admin-on-demand finalise endpoint."""
from unittest.mock import patch

import jwt
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.courses.models import PartnerAdmin, StudentProfile
from apps.scholarship import profile_engine
from apps.scholarship.models import (
    InterviewSession, ScholarshipApplication, ScholarshipCohort, SponsorProfile,
)

TEST_JWT_SECRET = 'test-supabase-jwt-secret'
REVIEWER, VIEWER, STUDENT = 'refine-reviewer', 'refine-viewer', 'refine-student'


def _token(uid):
    return jwt.encode({'sub': uid, 'aud': 'authenticated', 'role': 'authenticated'},
                      TEST_JWT_SECRET, algorithm='HS256')


def _submitted_session(app, **kw):
    defaults = dict(
        status='submitted', submitted_at=timezone.now(),
        findings={'unclear_funding': {'verdict': 'resolved', 'rationale': 'Will use PTPTN top-up'},
                  'manual_1': {'verdict': 'new_concern', 'rationale': 'Mother recently lost her job'}},
        rubric={'clarity_of_plan': 4, 'financial_need': 5},
        overall_note='Strong, motivated candidate; genuine need.')
    defaults.update(kw)
    return InterviewSession.objects.create(application=app, **defaults)


class TestRefineEngine(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)
        cls.profile = StudentProfile.objects.create(supabase_user_id=STUDENT, nric='030101-14-1234', name='Priya')
        cls.app = ScholarshipApplication.objects.create(
            cohort=cls.cohort, profile=cls.profile, status='interviewed',
            aspirations='Become a doctor', plans='Study hard',
            interview_gaps=[{'code': 'unclear_funding', 'question': 'How will you cover the gap?', 'why': 'Vague'}])

    def test_render_interview_includes_verdict_rationale_and_gap_question(self):
        session = _submitted_session(self.app)
        findings, rubric, note = profile_engine._render_interview(self.app, session)
        self.assertIn('resolved at interview', findings)
        self.assertIn('Will use PTPTN top-up', findings)
        self.assertIn('How will you cover the gap?', findings)   # gap question used as context
        self.assertIn('new concern raised at interview', findings)
        self.assertIn('financial_need: 5', rubric)
        self.assertIn('motivated candidate', note)

    def test_render_interview_empty_findings(self):
        session = _submitted_session(self.app, findings={}, rubric={}, overall_note='')
        findings, rubric, note = profile_engine._render_interview(self.app, session)
        self.assertIn('No specific findings', findings)
        self.assertEqual(rubric, 'not scored')
        self.assertEqual(note, 'none')

    @override_settings(GEMINI_API_KEY='')
    def test_refine_without_api_key_is_graceful(self):
        session = _submitted_session(self.app)
        self.assertIn('error', profile_engine.refine_sponsor_profile(self.app, 'draft', session))

    @patch('apps.scholarship.profile_engine._call_gemini_text')
    def test_refine_success_passes_draft_and_findings(self, mock_call):
        mock_call.return_value = {'markdown': '## Background\nRefined.', 'model_used': 'gemini-2.5-flash'}
        session = _submitted_session(self.app)
        out = profile_engine.refine_sponsor_profile(self.app, 'draft profile', session, language='en')
        self.assertEqual(out['markdown'], '## Background\nRefined.')
        # the prompt fed to the model must carry the draft + a finding
        prompt = mock_call.call_args.args[0]
        self.assertIn('draft profile', prompt)
        self.assertIn('PTPTN top-up', prompt)

    @patch('apps.scholarship.profile_engine._call_gemini_text')
    def test_refine_propagates_engine_error(self, mock_call):
        mock_call.return_value = {'error': 'All AI models failed: boom'}
        session = _submitted_session(self.app)
        self.assertIn('boom', profile_engine.refine_sponsor_profile(self.app, 'd', session)['error'])


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestFinaliseProfileEndpoint(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)
        cls.profile = StudentProfile.objects.create(supabase_user_id=STUDENT, nric='030101-14-1234', name='Priya')
        cls.app = ScholarshipApplication.objects.create(cohort=cls.cohort, profile=cls.profile, status='interviewed')
        cls.reviewer = PartnerAdmin.objects.create(supabase_user_id=REVIEWER, role='reviewer', is_active=True, name='Rev', email='r@x.com')
        cls.app.assigned_to = cls.reviewer
        cls.app.save(update_fields=['assigned_to'])
        PartnerAdmin.objects.create(supabase_user_id=VIEWER, role='admin', is_active=True, name='Vie', email='v@x.com')

    def setUp(self):
        self.client = APIClient()

    def _auth(self, uid):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(uid)}')

    def _url(self):
        return f'/api/v1/admin/scholarship/applications/{self.app.id}/finalise-profile/'

    def _draft(self):
        return SponsorProfile.objects.create(application=self.app, draft_markdown='## Background\nDraft.')

    @patch('apps.scholarship.views_admin.refine_sponsor_profile')
    def test_reviewer_stores_final(self, mock_refine):
        mock_refine.return_value = {'markdown': '## Background\nFinal v2.', 'model_used': 'gemini-2.5-flash'}
        self._draft(); _submitted_session(self.app)
        self._auth(REVIEWER)
        r = self.client.post(self._url())
        self.assertEqual(r.status_code, 200)
        sp = SponsorProfile.objects.get(application=self.app)
        self.assertEqual(sp.final_markdown, '## Background\nFinal v2.')
        self.assertEqual(sp.final_model_used, 'gemini-2.5-flash')
        self.assertIsNotNone(sp.finalised_at)

    @patch('apps.scholarship.views_admin.refine_sponsor_profile')
    def test_viewer_forbidden(self, mock_refine):
        self._draft(); _submitted_session(self.app)
        self._auth(VIEWER)
        self.assertEqual(self.client.post(self._url()).status_code, 403)
        mock_refine.assert_not_called()

    @patch('apps.scholarship.views_admin.refine_sponsor_profile')
    def test_no_draft_400(self, mock_refine):
        _submitted_session(self.app)   # interview exists, but no draft profile
        self._auth(REVIEWER)
        r = self.client.post(self._url())
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'no_draft')
        mock_refine.assert_not_called()

    @patch('apps.scholarship.views_admin.refine_sponsor_profile')
    def test_no_submitted_interview_400(self, mock_refine):
        self._draft()
        InterviewSession.objects.create(application=self.app, status='draft')  # draft only, not submitted
        self._auth(REVIEWER)
        r = self.client.post(self._url())
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'no_interview')
        mock_refine.assert_not_called()

    @patch('apps.scholarship.views_admin.refine_sponsor_profile')
    def test_engine_error_503(self, mock_refine):
        mock_refine.return_value = {'error': 'down'}
        self._draft(); _submitted_session(self.app)
        self._auth(REVIEWER)
        self.assertEqual(self.client.post(self._url()).status_code, 503)

    @patch('apps.scholarship.views_admin.refine_sponsor_profile')
    def test_get_detail_does_not_call_gemini(self, mock_refine):
        self._draft(); _submitted_session(self.app)
        self.app.assigned_to = PartnerAdmin.objects.get(supabase_user_id=REVIEWER)
        self.app.save(update_fields=['assigned_to'])
        self._auth(REVIEWER)
        r = self.client.get(f'/api/v1/admin/scholarship/applications/{self.app.id}/')
        self.assertEqual(r.status_code, 200)
        mock_refine.assert_not_called()
