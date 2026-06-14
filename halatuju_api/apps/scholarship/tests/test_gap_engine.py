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
    def test_caps_at_three(self, mock_call):
        mock_call.return_value = {'gaps': [
            {'code': f'g{i}', 'question': f'Question {i}?', 'why': 'w'} for i in range(6)]}
        self.assertEqual(len(gap_engine.generate_interview_gaps(self.app)['gaps']), 3)

    @patch('apps.scholarship.vision._call_gemini_json')
    def test_generate_more_excludes_existing(self, mock_call):
        mock_call.return_value = {'gaps': [
            {'code': 'dup', 'question': 'Already asked?', 'why': 'repeat'},   # same as existing → dropped
            {'code': 'fresh', 'question': 'Something new?', 'why': 'ok'},
        ]}
        existing = [{'code': 'old', 'question': 'Already asked?', 'why': 'w'}]
        gaps = gap_engine.generate_interview_gaps(self.app, existing=existing)['gaps']
        questions = [g['question'] for g in gaps]
        self.assertIn('Something new?', questions)
        self.assertNotIn('Already asked?', questions)        # not repeated
        # the prompt told the model what to avoid
        prompt = mock_call.call_args.args[0]
        self.assertIn('ALREADY SUGGESTED', prompt)
        self.assertIn('Already asked?', prompt)

    def test_prompt_includes_verdict_flags_and_answered(self):
        prompt = gap_engine._build_gap_prompt(self.app)
        self.assertIn('VERIFICATION VERDICT', prompt)
        self.assertIn('PRE-INTERVIEW FLAGS', prompt)
        self.assertIn('ALREADY ANSWERED', prompt)
        self.assertIn('ACADEMIC RECORD', prompt)

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
        cls.reviewer = PartnerAdmin.objects.create(supabase_user_id=REVIEWER, role='reviewer', is_active=True,
                                                   name='Rev', email='r@x.com')
        cls.app.assigned_to = cls.reviewer
        cls.app.save(update_fields=['assigned_to'])
        PartnerAdmin.objects.create(supabase_user_id=VIEWER, role='admin', is_active=True,
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
    def test_append_extends_existing(self, mock_gen):
        self.app.interview_gaps = [{'code': 'g1', 'question': 'Q1?', 'why': 'W'}]
        self.app.save(update_fields=['interview_gaps'])
        mock_gen.return_value = {'gaps': [{'code': 'g2', 'question': 'Q2?', 'why': 'W2'}]}
        self._auth(REVIEWER)
        r = self.client.post(self._url(), {'append': True}, format='json')
        self.assertEqual(r.status_code, 200)
        self.app.refresh_from_db()
        codes = [g['code'] for g in self.app.interview_gaps]
        self.assertEqual(codes, ['g1', 'g2'])                      # appended, not replaced
        self.assertEqual(mock_gen.call_args.kwargs.get('existing'),
                         [{'code': 'g1', 'question': 'Q1?', 'why': 'W'}])

    @patch('apps.scholarship.gap_engine.generate_interview_gaps')
    def test_fresh_replaces_existing(self, mock_gen):
        self.app.interview_gaps = [{'code': 'old', 'question': 'Old?', 'why': 'W'}]
        self.app.save(update_fields=['interview_gaps'])
        mock_gen.return_value = {'gaps': [{'code': 'new', 'question': 'New?', 'why': 'W'}]}
        self._auth(REVIEWER)
        r = self.client.post(self._url())   # no append → replace
        self.assertEqual(r.status_code, 200)
        self.app.refresh_from_db()
        self.assertEqual([g['code'] for g in self.app.interview_gaps], ['new'])

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
        self.app.assigned_to = PartnerAdmin.objects.get(supabase_user_id=REVIEWER)
        self.app.save(update_fields=['assigned_to'])
        self._auth(REVIEWER)
        r = self.client.get(f'/api/v1/admin/scholarship/applications/{self.app.id}/')
        self.assertEqual(r.status_code, 200)
        mock_gen.assert_not_called()
