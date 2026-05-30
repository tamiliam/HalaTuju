"""Phase B interview gap-spotter: engine (mocked Gemini) + admin-on-demand endpoint."""
from unittest.mock import patch

import jwt
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.courses.models import PartnerAdmin, StudentProfile
from apps.scholarship import gap_engine
from apps.scholarship.models import ScholarshipApplication, ScholarshipCohort

TEST_JWT_SECRET = 'test-supabase-jwt-secret'
REVIEWER, VIEWER, STUDENT = 'gap-reviewer', 'gap-viewer', 'gap-student'


def _token(uid):
    return jwt.encode({'sub': uid, 'aud': 'authenticated', 'role': 'authenticated'},
                      TEST_JWT_SECRET, algorithm='HS256')


class TestGapEngine(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)
        cls.profile = StudentProfile.objects.create(supabase_user_id=STUDENT, nric='030101-14-1234', name='Priya')
        cls.app = ScholarshipApplication.objects.create(
            cohort=cls.cohort, profile=cls.profile, status='shortlisted',
            aspirations='Become a doctor', plans='Study hard', fears='Money',
            daily_life='Help at home', family_context='Single parent')

    @patch('apps.scholarship.vision._call_gemini_json')
    def test_normalises_clamps_dedupes(self, mock_call):
        mock_call.return_value = {'gaps': [
            {'code': 'Unclear Funding!', 'question': 'How will you bridge the gap?', 'why': 'Vague'},
            {'code': 'unclear_funding', 'question': 'Second q', 'why': 'dup-ish code'},   # dup slug
            {'question': 'No code here', 'why': 'ok'},                                     # missing code
            {'code': 'empty_q', 'question': '   ', 'why': 'dropped'},                       # empty question → dropped
        ] + [{'code': f'x{i}', 'question': f'q{i}', 'why': 'w'} for i in range(6)]}        # > 6 → clamp
        out = gap_engine.generate_interview_gaps(self.app)
        gaps = out['gaps']
        self.assertLessEqual(len(gaps), 6)
        codes = [g['code'] for g in gaps]
        self.assertEqual(len(codes), len(set(codes)))           # deduped
        self.assertEqual(codes[0], 'unclear_funding')           # slugified
        self.assertTrue(all(g['question'].strip() for g in gaps))   # no empties

    @patch('apps.scholarship.vision._call_gemini_json')
    def test_engine_error_returns_error(self, mock_call):
        mock_call.return_value = {'_error': 'All AI models failed: boom'}
        self.assertIn('boom', gap_engine.generate_interview_gaps(self.app)['error'])

    @override_settings(GEMINI_API_KEY='')
    def test_missing_api_key_no_call(self):
        # key guard in the shared seam → error, no SDK import/call
        self.assertIn('error', gap_engine.generate_interview_gaps(self.app))

    def test_thin_narrative_builds_prompt(self):
        thin = ScholarshipApplication.objects.create(
            cohort=self.cohort,
            profile=StudentProfile.objects.create(supabase_user_id='thin', nric='050101-14-2222'),
            status='shortlisted')
        # Should not raise even with empty narrative.
        self.assertIn('APPLICANT', gap_engine._build_gap_prompt(thin))


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestSuggestGapsEndpoint(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)
        cls.profile = StudentProfile.objects.create(supabase_user_id=STUDENT, nric='030101-14-1234', name='Priya')
        cls.app = ScholarshipApplication.objects.create(cohort=cls.cohort, profile=cls.profile, status='shortlisted')
        PartnerAdmin.objects.create(supabase_user_id=REVIEWER, role='reviewer', is_active=True,
                                    name='Rev', email='r@x.com')
        PartnerAdmin.objects.create(supabase_user_id=VIEWER, role='viewer', is_active=True,
                                    name='Vie', email='v@x.com')

    def setUp(self):
        self.client = APIClient()

    def _auth(self, uid):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(uid)}')

    def _url(self):
        return f'/api/v1/admin/scholarship/applications/{self.app.id}/suggest-gaps/'

    @patch('apps.scholarship.gap_engine.generate_interview_gaps')
    def test_reviewer_stores_gaps(self, mock_gen):
        mock_gen.return_value = {'gaps': [{'code': 'g1', 'question': 'Q?', 'why': 'W'}]}
        self._auth(REVIEWER)
        r = self.client.post(self._url())
        self.assertEqual(r.status_code, 200)
        self.app.refresh_from_db()
        self.assertEqual(self.app.interview_gaps[0]['code'], 'g1')
        self.assertIsNotNone(self.app.interview_gaps_run_at)

    @patch('apps.scholarship.gap_engine.generate_interview_gaps')
    def test_viewer_forbidden(self, mock_gen):
        self._auth(VIEWER)
        r = self.client.post(self._url())
        self.assertEqual(r.status_code, 403)
        mock_gen.assert_not_called()

    @patch('apps.scholarship.gap_engine.generate_interview_gaps')
    def test_engine_error_503(self, mock_gen):
        mock_gen.return_value = {'error': 'down'}
        self._auth(REVIEWER)
        self.assertEqual(self.client.post(self._url()).status_code, 503)

    @patch('apps.scholarship.gap_engine.generate_interview_gaps')
    def test_get_detail_does_not_call_gemini(self, mock_gen):
        self._auth(REVIEWER)
        r = self.client.get(f'/api/v1/admin/scholarship/applications/{self.app.id}/')
        self.assertEqual(r.status_code, 200)
        mock_gen.assert_not_called()
