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
    SIGNAL_LABELS,
    STRENGTH_LABELS,
)
from apps.reports.prompts import get_prompt, get_persona_for_model


# Sample data matching real eligibility output (engine keys)
SAMPLE_GRADES = {
    'bm': 'A',
    'eng': 'B+',
    'math': 'B',
    'sci': 'A-',
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
    'work_style': {'hands_on': 3, 'creative': 1},
    'environment': {'workshop_environment': 2, 'office_environment': 1},
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
        """Signals are formatted into human-readable BM labels."""
        result = _format_signals(SAMPLE_SIGNALS, lang='bm')
        self.assertIn('Kerja Amali', result)
        self.assertIn('kuat', result)
        self.assertNotIn('kuiz belum', result)

    def test_format_signals_empty(self):
        """Empty signals indicate quiz not taken."""
        result = _format_signals({}, lang='bm')
        self.assertIn('kuiz belum', result)

    def test_format_signals_bm_labels(self):
        """BM output uses Malay labels and strength words."""
        result = _format_signals(SAMPLE_SIGNALS, lang='bm')
        self.assertIn('Kecenderungan pelajar:', result)
        self.assertIn('- Kerja Amali (kuat)', result)
        self.assertIn('- Kreatif (sederhana)', result)
        self.assertIn('- Persekitaran Bengkel (kuat)', result)
        self.assertIn('- Persekitaran Pejabat (sederhana)', result)

    def test_format_signals_en_labels(self):
        """EN output uses English labels and strength words."""
        result = _format_signals(SAMPLE_SIGNALS, lang='en')
        self.assertIn('Student inclinations:', result)
        self.assertIn('- Hands-on Work (strong)', result)
        self.assertIn('- Creative (moderate)', result)
        self.assertIn('- Workshop Environment (strong)', result)
        self.assertIn('- Office Environment (moderate)', result)

    def test_format_signals_empty_en(self):
        """Empty signals in EN return English message."""
        result = _format_signals({}, lang='en')
        self.assertIn('quiz not taken', result)

    def test_format_signals_none(self):
        """None signals return safe default."""
        result = _format_signals(None, lang='bm')
        self.assertIn('kuiz belum', result)

    def test_format_signals_all_zero(self):
        """All-zero signals return no dominant message."""
        signals = {'work_style': {'hands_on': 0, 'creative': 0}}
        result = _format_signals(signals, lang='bm')
        self.assertIn('Tiada kecenderungan dominan', result)

    def test_format_signals_unknown_key_falls_back(self):
        """Unknown signal keys use the raw key as label."""
        signals = {'misc': {'unknown_signal': 2}}
        result = _format_signals(signals, lang='bm')
        self.assertIn('unknown_signal', result)

    def test_format_signals_strength_threshold(self):
        """Score >= 2 is kuat/strong, score 1 is sederhana/moderate."""
        signals = {'test': {'hands_on': 2, 'creative': 1}}
        bm = _format_signals(signals, lang='bm')
        self.assertIn('Kerja Amali (kuat)', bm)
        self.assertIn('Kreatif (sederhana)', bm)
        en = _format_signals(signals, lang='en')
        self.assertIn('Hands-on Work (strong)', en)
        self.assertIn('Creative (moderate)', en)

    def test_format_courses_limits_to_five(self):
        """At most 5 courses are formatted (default limit)."""
        many_courses = SAMPLE_COURSES * 5  # 15 courses
        result = _format_courses(many_courses)
        lines = [l for l in result.strip().split('\n') if l.strip()]
        self.assertEqual(len(lines), 5)

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

    @patch('google.genai.Client')
    @patch('apps.reports.report_engine.settings')
    def test_successful_generation(self, mock_settings, mock_client_cls):
        """Successful Gemini call returns markdown + metadata."""
        mock_settings.GEMINI_API_KEY = 'test-key'

        mock_response = MagicMock()
        mock_response.text = 'Salam sejahtera pelajar, saya Cikgu Gopal...'

        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response
        mock_client_cls.return_value = mock_client

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

    @patch('google.genai.Client')
    @patch('apps.reports.report_engine.settings')
    def test_cascade_fallback_on_failure(self, mock_settings, mock_client_cls):
        """If first model fails, cascade tries the next one."""
        mock_settings.GEMINI_API_KEY = 'test-key'

        mock_response = MagicMock()
        mock_response.text = 'Report from fallback model.'

        call_count = [0]

        def side_effect(**kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise Exception('Rate limited')
            return mock_response

        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = side_effect
        mock_client_cls.return_value = mock_client

        result = generate_report(
            grades=SAMPLE_GRADES,
            eligible_courses=SAMPLE_COURSES,
            insights=SAMPLE_INSIGHTS,
        )

        self.assertIn('markdown', result)
        self.assertNotIn('error', result)
        # Should have tried at least 2 models
        self.assertGreaterEqual(call_count[0], 2)


class TestSmartCourseSelection(TestCase):
    """Test fit_score sorting and display in course formatting."""

    def test_courses_sorted_by_fit_score(self):
        """Courses are sorted by fit_score descending."""
        courses = [
            {'course_name': 'Low', 'field': 'A', 'fit_score': 30},
            {'course_name': 'High', 'field': 'B', 'fit_score': 70},
            {'course_name': 'Mid', 'field': 'C', 'fit_score': 50},
        ]
        result = _format_courses(courses)
        lines = result.strip().split('\n')
        self.assertTrue(lines[0].startswith('1. High'))
        self.assertTrue(lines[1].startswith('2. Mid'))
        self.assertTrue(lines[2].startswith('3. Low'))

    def test_courses_limit_5(self):
        """Default limit is 5 courses."""
        courses = [{'course_name': f'C{i}', 'field': 'X', 'fit_score': i}
                   for i in range(10)]
        result = _format_courses(courses)
        lines = [l for l in result.strip().split('\n') if l.strip()]
        self.assertEqual(len(lines), 5)

    def test_courses_without_fit_score_still_work(self):
        """Courses without fit_score default to 0 and still format."""
        courses = [
            {'course_name': 'A', 'field': 'X'},
            {'course_name': 'B', 'field': 'Y'},
        ]
        result = _format_courses(courses)
        self.assertIn('A', result)
        self.assertIn('B', result)

    def test_fit_score_displayed(self):
        """fit_score is shown in the output when present."""
        courses = [{'course_name': 'Test', 'field': 'X', 'fit_score': 65}]
        result = _format_courses(courses)
        self.assertIn('Skor Kesesuaian: 65', result)

    def test_field_display_in_course_format(self):
        """field_display is used instead of raw field key when available."""
        courses = [
            {'course_name': 'Diploma Kejuruteraan', 'field': 'kejuruteraan',
             'field_display': 'Kejuruteraan Mekanikal'},
        ]
        result = _format_courses(courses)
        self.assertIn('Kejuruteraan Mekanikal', result)
        # Raw key should not appear before the display name
        self.assertNotIn('kejuruteraan', result.split('Kejuruteraan Mekanikal')[0])

    def test_field_fallback_when_no_display(self):
        """Falls back to raw field value when field_display is absent."""
        courses = [{'course_name': 'Test', 'field': 'sains'}]
        result = _format_courses(courses)
        self.assertIn('sains', result)
