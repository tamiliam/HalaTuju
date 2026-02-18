"""
Tests for the AI report engine.

All Gemini API calls are mocked — no real API keys needed.

Covers:
- Prompt formatting (BM and EN)
- Data formatting helpers (grades, signals, courses, insights)
- Model cascade behaviour (fallback on failure)
- Missing API key handling
- View integration (generate endpoint)
"""
from unittest.mock import patch, MagicMock

from django.test import TestCase

from apps.reports.report_engine import (
    generate_report,
    _format_grades,
    _format_signals,
    _format_courses,
    _format_insights,
)
from apps.reports.prompts import get_prompt, get_persona_for_model


# Sample data matching real eligibility output
SAMPLE_GRADES = {
    'bm': 'A',
    'eng': 'B+',
    'math': 'B',
    'sc': 'A-',
    'hist': 'B+',
}

SAMPLE_COURSES = [
    {
        'course_id': 'DIP001',
        'course_name': 'Diploma Kejuruteraan Mekanikal',
        'level': 'Diploma',
        'field': 'Kejuruteraan',
        'source_type': 'poly',
        'merit_label': 'High',
    },
    {
        'course_id': 'DIP002',
        'course_name': 'Diploma Kejuruteraan Elektrik',
        'level': 'Diploma',
        'field': 'Kejuruteraan',
        'source_type': 'poly',
        'merit_label': 'Fair',
    },
    {
        'course_id': 'TVET01',
        'course_name': 'Sijil Teknologi Automotif',
        'level': 'Sijil',
        'field': 'Automotif',
        'source_type': 'tvet',
        'merit_label': None,
    },
]

SAMPLE_INSIGHTS = {
    'stream_breakdown': [
        {'source_type': 'poly', 'label': 'Politeknik', 'count': 2},
        {'source_type': 'tvet', 'label': 'TVET', 'count': 1},
    ],
    'top_fields': [
        {'field': 'Kejuruteraan', 'count': 2},
        {'field': 'Automotif', 'count': 1},
    ],
    'level_distribution': [
        {'level': 'Diploma', 'count': 2},
        {'level': 'Sijil', 'count': 1},
    ],
    'merit_summary': {'high': 1, 'fair': 1, 'low': 0, 'no_data': 1},
    'summary_text': 'Anda layak memohon 3 kursus merentasi 2 aliran.',
}

SAMPLE_SIGNALS = {
    'work_style': {'structured': 3, 'creative': 1},
    'environment': {'outdoor': 2, 'office': 1},
}


class TestFormatHelpers(TestCase):
    """Test data formatting functions."""

    def test_format_grades_with_data(self):
        """Grades are formatted with Malay subject labels."""
        result = _format_grades(SAMPLE_GRADES)
        self.assertIn('Bahasa Melayu: A', result)
        self.assertIn('Matematik: B', result)
        self.assertIn('Bahasa Inggeris: B+', result)

    def test_format_grades_empty(self):
        """Empty grades return a safe default."""
        result = _format_grades({})
        self.assertIn('Tiada', result)

    def test_format_signals_with_data(self):
        """Signals are formatted into a readable string."""
        result = _format_signals(SAMPLE_SIGNALS)
        self.assertIn('structured', result)
        self.assertNotIn('kuiz belum', result)

    def test_format_signals_empty(self):
        """Empty signals indicate quiz not taken."""
        result = _format_signals({})
        self.assertIn('kuiz belum', result)

    def test_format_courses_limits_to_three(self):
        """At most 3 courses are formatted."""
        many_courses = SAMPLE_COURSES * 5  # 15 courses
        result = _format_courses(many_courses)
        lines = [l for l in result.strip().split('\n') if l.strip()]
        self.assertEqual(len(lines), 3)

    def test_format_insights_includes_summary(self):
        """Insights formatting includes the summary text."""
        result = _format_insights(SAMPLE_INSIGHTS)
        self.assertIn('3 kursus', result)
        self.assertIn('Kejuruteraan', result)


class TestPrompts(TestCase):
    """Test prompt template functions."""

    def test_get_prompt_bm(self):
        """BM prompt contains Malay text."""
        prompt = get_prompt('bm')
        self.assertIn('kaunselor', prompt)
        self.assertIn('{student_name}', prompt)

    def test_get_prompt_en(self):
        """EN prompt contains English text."""
        prompt = get_prompt('en')
        self.assertIn('career counselor', prompt)
        self.assertIn('{student_name}', prompt)

    def test_persona_for_model(self):
        """Correct persona is returned for each model family."""
        p = get_persona_for_model('gemini-2.5-flash')
        self.assertEqual(p['name'], 'Cikgu Gopal')

        p = get_persona_for_model('gemini-2.0-flash')
        self.assertEqual(p['name'], 'Cikgu Guna')

        p = get_persona_for_model('unknown-model')
        self.assertEqual(p['name'], 'Cikgu Guna')  # default


class TestGenerateReport(TestCase):
    """Test the generate_report function with mocked Gemini."""

    @patch('apps.reports.report_engine.settings')
    def test_missing_api_key_returns_error(self, mock_settings):
        """Missing GEMINI_API_KEY returns an error dict."""
        mock_settings.GEMINI_API_KEY = ''

        result = generate_report(
            grades=SAMPLE_GRADES,
            eligible_courses=SAMPLE_COURSES,
            insights=SAMPLE_INSIGHTS,
        )
        self.assertIn('error', result)
        self.assertIn('API key', result['error'])

    @patch('google.generativeai.GenerativeModel')
    @patch('google.generativeai.configure')
    @patch('apps.reports.report_engine.settings')
    def test_successful_generation(self, mock_settings, mock_configure,
                                   mock_model_cls):
        """Successful Gemini call returns markdown + metadata."""
        mock_settings.GEMINI_API_KEY = 'test-key'

        mock_response = MagicMock()
        mock_response.text = 'Salam sejahtera pelajar, saya Cikgu Gopal...'

        mock_model = MagicMock()
        mock_model.generate_content.return_value = mock_response
        mock_model_cls.return_value = mock_model

        result = generate_report(
            grades=SAMPLE_GRADES,
            eligible_courses=SAMPLE_COURSES,
            insights=SAMPLE_INSIGHTS,
            lang='bm',
        )

        self.assertIn('markdown', result)
        self.assertIn('Cikgu Gopal', result['markdown'])
        self.assertIn('model_used', result)
        self.assertIn('counsellor_name', result)
        self.assertNotIn('error', result)

    @patch('google.generativeai.GenerativeModel')
    @patch('google.generativeai.configure')
    @patch('apps.reports.report_engine.settings')
    def test_cascade_fallback_on_failure(self, mock_settings, mock_configure,
                                         mock_model_cls):
        """If first model fails, cascade tries the next one."""
        mock_settings.GEMINI_API_KEY = 'test-key'

        mock_response = MagicMock()
        mock_response.text = 'Report from fallback model.'

        call_count = [0]

        def side_effect(model_name):
            model = MagicMock()
            call_count[0] += 1
            if call_count[0] == 1:
                # First model fails
                model.generate_content.side_effect = Exception('Rate limited')
            else:
                # Second model succeeds
                model.generate_content.return_value = mock_response
            return model

        mock_model_cls.side_effect = side_effect

        result = generate_report(
            grades=SAMPLE_GRADES,
            eligible_courses=SAMPLE_COURSES,
            insights=SAMPLE_INSIGHTS,
        )

        self.assertIn('markdown', result)
        self.assertNotIn('error', result)
        # Should have tried at least 2 models
        self.assertGreaterEqual(call_count[0], 2)
