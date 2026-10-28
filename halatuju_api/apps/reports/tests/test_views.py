"""
Tests for report API views.

Covers:
- GET /api/v1/reports/ — list reports
- GET /api/v1/reports/<id>/ — get report detail
- POST /api/v1/reports/generate/ — validation (no real Gemini calls)
- FK bug regression: views must filter by student__supabase_user_id, not student_id
"""
from unittest.mock import patch, ANY
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from apps.courses.models import StudentProfile
from apps.reports.models import GeneratedReport

TEST_USER_ID = 'test-user-report-456'
OTHER_USER_ID = 'other-user-report-789'


@override_settings(ROOT_URLCONF='halatuju.urls')
class TestReportViews(TestCase):
    """Tests for report list, detail, and generate endpoints."""

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        # Create test student profile
        self.profile = StudentProfile.objects.create(
            supabase_user_id=TEST_USER_ID,
            nric='010101-01-1234',
            grades={'bm': 'A', 'eng': 'B+', 'math': 'A-'},
            gender='male',
            nationality='malaysian',
        )
        # Create a report for this user
        self.report = GeneratedReport.objects.create(
            student=self.profile,
            title='Laporan Kaunseling — Cikgu Gopal',
            content='# Report\n\nSalam sejahtera pelajar.',
            summary='Test summary',
            student_profile_snapshot={'grades': {'bm': 'A'}},
            eligible_courses_snapshot=[{'course_id': 'C001'}],
            model_used='gemini-2.5-flash',
            generation_time_ms=1500,
        )
        # Create another user's report (should NOT be visible)
        other_profile = StudentProfile.objects.create(
            supabase_user_id=OTHER_USER_ID,
            grades={'bm': 'B'},
        )
        self.other_report = GeneratedReport.objects.create(
            student=other_profile,
            title='Other Report',
            content='Other content',
            summary='Other summary',
            student_profile_snapshot={},
            eligible_courses_snapshot=[],
            model_used='gemini-2.0-flash',
        )
        # Patch both jwt.get_unverified_header and jwt.decode in middleware
        self._header_patcher = patch(
            'halatuju.middleware.supabase_auth.jwt.get_unverified_header',
            return_value={'alg': 'HS256'},
        )
        self._decode_patcher = patch(
            'halatuju.middleware.supabase_auth.jwt.decode',
            return_value={
                'sub': TEST_USER_ID,
                'aud': 'authenticated',
                'role': 'authenticated',
            },
        )
        self._header_patcher.start()
        self._decode_patcher.start()
        self.client.credentials(HTTP_AUTHORIZATION='Bearer fake-but-patched')

    def tearDown(self):
        self._decode_patcher.stop()
        self._header_patcher.stop()

    def test_list_reports_returns_own_reports_only(self):
        """GET /api/v1/reports/ returns only the authenticated user's reports."""
        response = self.client.get('/api/v1/reports/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['count'], 1)
        self.assertEqual(data['reports'][0]['report_id'], self.report.id)

    def test_get_report_detail_returns_own_report(self):
        """GET /api/v1/reports/<id>/ returns the report when it belongs to the user."""
        response = self.client.get(f'/api/v1/reports/{self.report.id}/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['report_id'], self.report.id)
        self.assertIn('Salam sejahtera', data['markdown'])

    def test_get_report_detail_404_for_other_users_report(self):
        """GET /api/v1/reports/<id>/ returns 404 for another user's report."""
        response = self.client.get(f'/api/v1/reports/{self.other_report.id}/')
        self.assertEqual(response.status_code, 404)

    @patch('apps.reports.views.generate_report')
    def test_generate_passes_student_name(self, mock_gen):
        """POST /api/v1/reports/generate/ passes profile.name as student_name."""
        # Set a name on the profile
        self.profile.name = 'Ahmad bin Ali'
        self.profile.save()

        mock_gen.return_value = {
            'markdown': '# Report\nHello Ahmad.',
            'model_used': 'gemini-2.5-flash',
            'generation_time_ms': 100,
        }

        self.client.post(
            '/api/v1/reports/generate/',
            {'eligible_courses': [{'course_id': 'C001'}], 'insights': {}},
            format='json',
        )

        mock_gen.assert_called_once()
        call_kwargs = mock_gen.call_args[1]
        # profile.name is normalised to CAPS at the write boundary (owner 2026-07-16).
        self.assertEqual(call_kwargs['student_name'], 'AHMAD BIN ALI')

    @patch('apps.reports.views.generate_report')
    def test_generate_defaults_student_name_when_blank(self, mock_gen):
        """POST /api/v1/reports/generate/ defaults student_name to 'pelajar' when name is blank."""
        # Ensure name is blank
        self.profile.name = ''
        self.profile.save()

        mock_gen.return_value = {
            'markdown': '# Report\nHello pelajar.',
            'model_used': 'gemini-2.5-flash',
            'generation_time_ms': 100,
        }

        self.client.post(
            '/api/v1/reports/generate/',
            {'eligible_courses': [{'course_id': 'C001'}], 'insights': {}},
            format='json',
        )

        mock_gen.assert_called_once()
        call_kwargs = mock_gen.call_args[1]
        self.assertEqual(call_kwargs['student_name'], 'pelajar')

    def test_generate_report_requires_eligible_courses(self):
        """POST /api/v1/reports/generate/ returns 400 without eligible_courses."""
        response = self.client.post(
            '/api/v1/reports/generate/',
            {'insights': {}},
            format='json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('eligible_courses', response.json()['error'])

    @patch('apps.reports.views.generate_report')
    def test_stpm_student_passes_exam_type(self, mock_gen):
        """POST /api/v1/reports/generate/ passes STPM data for STPM students."""
        mock_gen.return_value = {
            'markdown': 'text', 'model_used': 'gemini-2.5-flash',
            'generation_time_ms': 100,
        }
        self.profile.exam_type = 'stpm'
        self.profile.stpm_grades = {'PA': 'A', 'PHYSICS': 'B+'}
        self.profile.stpm_cgpa = 3.50
        self.profile.muet_band = 4
        self.profile.save()

        self.client.post(
            '/api/v1/reports/generate/',
            {'eligible_courses': [{'course_name': 'BSc'}], 'insights': {}},
            format='json',
        )

        mock_gen.assert_called_once()
        call_kwargs = mock_gen.call_args[1]
        self.assertEqual(call_kwargs['exam_type'], 'stpm')
        self.assertEqual(call_kwargs['stpm_grades'], {'PA': 'A', 'PHYSICS': 'B+'})
        self.assertEqual(call_kwargs['stpm_cgpa'], 3.50)
        self.assertEqual(call_kwargs['muet_band'], 4)

    @patch('apps.reports.views.generate_report')
    def test_the_bumiputera_answer_never_reaches_the_report(self, mock_gen):
        """Bumi coverage Sprint B (owner ruling 2026-10-28): the answer is COURSE-GUIDE ONLY. It is
        neither handed to the report writer nor stored in the report's profile snapshot — fails the
        day somebody adds it to either (the s44(6) stance, docs/decisions.md)."""
        mock_gen.return_value = {
            'markdown': 'text', 'model_used': 'gemini-2.5-flash', 'generation_time_ms': 100,
        }
        self.profile.bumiputera = True
        self.profile.save()
        self.client.post('/api/v1/reports/generate/',
                         {'eligible_courses': [{'course_name': 'Diploma IT'}], 'insights': {}},
                         format='json')
        mock_gen.assert_called_once()
        self.assertFalse([k for k in mock_gen.call_args[1] if 'bumi' in k.lower()])
        snap = GeneratedReport.objects.latest('id').student_profile_snapshot
        self.assertNotIn('bumiputera', snap)
        self.assertNotIn('bumi', str(snap).lower())

    @patch('apps.reports.views.generate_report')
    def test_spm_student_passes_spm_exam_type(self, mock_gen):
        """POST /api/v1/reports/generate/ passes exam_type='spm' and no STPM data for SPM students."""
        mock_gen.return_value = {
            'markdown': 'text', 'model_used': 'gemini-2.5-flash',
            'generation_time_ms': 100,
        }

        self.client.post(
            '/api/v1/reports/generate/',
            {'eligible_courses': [{'course_name': 'Diploma IT'}], 'insights': {}},
            format='json',
        )

        mock_gen.assert_called_once()
        call_kwargs = mock_gen.call_args[1]
        self.assertEqual(call_kwargs['exam_type'], 'spm')
        self.assertIsNone(call_kwargs['stpm_grades'])
        self.assertIsNone(call_kwargs['stpm_cgpa'])
        self.assertIsNone(call_kwargs['muet_band'])

    @patch('apps.reports.views.generate_report')
    def test_a_third_route_student_gets_the_stpm_equivalent_report_path(self, mock_gen):
        """Third results route S2b (supersedes S2a's PIN, which held this route on the SPM prompt
        until S2b owned its content, roadmap section 4): a Matriculation holder reaches the engine
        as 'matric' with her results (the qualification, the CGPA as printed, the server's overall
        CGPA, the co-curriculum score, MUET) and her SPM grades from the ONE reader
        (`spm_grades_for`, the STPM page's block included); the prompt is the STPM-equivalent one,
        never the SPM leaver's."""
        from apps.reports.prompts import get_prompt
        mock_gen.return_value = {
            'markdown': 'text', 'model_used': 'gemini-2.5-flash', 'generation_time_ms': 100,
        }
        self.profile.exam_type = self.profile.results_exam_type = 'matric'
        self.profile.higher_cgpa, self.profile.higher_koko, self.profile.muet_band = 3.5, 8, 4
        self.profile.completed_qualifications = ['spm', 'matric']
        self.profile.spm_prereq_grades = {'hist': 'B'}
        self.profile.save()
        self.client.post('/api/v1/reports/generate/',
                         {'eligible_courses': [{'course_name': 'Ijazah'}], 'insights': {}},
                         format='json')
        kw = mock_gen.call_args[1]
        self.assertEqual(kw['exam_type'], 'matric')
        self.assertIsNone(kw['stpm_grades'])
        self.assertIsNone(kw['stpm_cgpa'])
        self.assertEqual(kw['higher'], {'label': 'Matriculation', 'cgpa': 3.5, 'overall_cgpa': 3.47,
                                        'koko': 8.0, 'muet_band': 4})
        self.assertEqual(kw['grades'], {'bm': 'A', 'eng': 'B+', 'math': 'A-', 'hist': 'B'})
        self.assertEqual(get_prompt('bm', exam_type='matric'), get_prompt('bm', exam_type='stpm'))
        self.assertNotEqual(get_prompt('en', exam_type='diploma'), get_prompt('en', exam_type='spm'))
        snap = GeneratedReport.objects.latest('id').student_profile_snapshot
        self.assertEqual((snap['exam_type'], snap['higher']['overall_cgpa']), ('matric', 3.47))

    @patch('apps.reports.views.generate_report')
    def test_a_declared_third_route_with_no_cgpa_reads_its_spm_results(self, mock_gen):
        """The card tapped, no CGPA entered, SPM grades on file: `results_held` reads SPM (the Form
        Six rule, extended in S2a), and so does the report — never a third-route report on nothing."""
        mock_gen.return_value = {
            'markdown': 'text', 'model_used': 'gemini-2.5-flash', 'generation_time_ms': 100,
        }
        self.profile.exam_type = 'asasi'
        self.profile.save()
        self.client.post('/api/v1/reports/generate/',
                         {'eligible_courses': [{'course_name': 'Diploma IT'}], 'insights': {}},
                         format='json')
        kw = mock_gen.call_args[1]
        self.assertEqual(kw['exam_type'], 'spm')
        self.assertIsNone(kw['higher'])

    @patch('apps.reports.views.generate_report')
    def test_a_form_six_explorer_gets_the_report_for_the_results_she_holds(self, mock_gen):
        """S2b review: the HELD qualification on every route. Declared STPM, no STPM results, SPM
        grades on file -> `results_held` is SPM, and so is the report (it used to be the STPM
        prompt over "no STPM grades")."""
        mock_gen.return_value = {
            'markdown': 'text', 'model_used': 'gemini-2.5-flash', 'generation_time_ms': 100,
        }
        self.profile.exam_type = 'stpm'
        self.profile.save()
        self.client.post('/api/v1/reports/generate/',
                         {'eligible_courses': [{'course_name': 'Diploma IT'}], 'insights': {}},
                         format='json')
        kw = mock_gen.call_args[1]
        self.assertEqual(kw['exam_type'], 'spm')
        self.assertIsNone(kw['stpm_grades'])
