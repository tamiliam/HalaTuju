"""
Tests for the deterministic insights engine.

Covers:
- generate_insights() with typical eligible courses
- Empty input handling
- Stream breakdown counting
- Top fields ranking (correct order)
- Level distribution grouping
- Merit summary aggregation
"""
from django.test import TestCase
from apps.courses.insights_engine import generate_insights


# Sample eligible courses (mimics EligibilityCheckView output)
SAMPLE_COURSES = [
    {'course_id': 'DIP001', 'course_name': 'Diploma Kejuruteraan Mekanikal',
     'level': 'Diploma', 'field': 'Kejuruteraan', 'source_type': 'poly',
     'merit_cutoff': 45.0, 'student_merit': 50.0, 'merit_label': 'High', 'merit_color': '#22c55e'},
    {'course_id': 'DIP002', 'course_name': 'Diploma Kejuruteraan Elektrik',
     'level': 'Diploma', 'field': 'Kejuruteraan', 'source_type': 'poly',
     'merit_cutoff': 48.0, 'student_merit': 50.0, 'merit_label': 'High', 'merit_color': '#22c55e'},
    {'course_id': 'DIP003', 'course_name': 'Diploma Akauntansi',
     'level': 'Diploma', 'field': 'Perniagaan', 'source_type': 'poly',
     'merit_cutoff': 40.0, 'student_merit': 50.0, 'merit_label': 'High', 'merit_color': '#22c55e'},
    {'course_id': 'TVET01', 'course_name': 'Sijil Teknologi Automotif',
     'level': 'Sijil', 'field': 'Automotif', 'source_type': 'tvet',
     'merit_cutoff': None, 'student_merit': 50.0, 'merit_label': None, 'merit_color': None},
    {'course_id': 'TVET02', 'course_name': 'Sijil Teknologi Elektrik',
     'level': 'Sijil', 'field': 'Kejuruteraan', 'source_type': 'tvet',
     'merit_cutoff': None, 'student_merit': 50.0, 'merit_label': None, 'merit_color': None},
    {'course_id': 'UA001', 'course_name': 'Asasi Sains',
     'level': 'Asasi', 'field': 'Sains', 'source_type': 'ua',
     'merit_cutoff': 55.0, 'student_merit': 50.0, 'merit_label': 'Fair', 'merit_color': '#eab308'},
    {'course_id': '50PD01', 'course_name': 'Bahasa Melayu Pendidikan Rendah',
     'level': 'Ijazah Sarjana Muda Pendidikan', 'field': 'Pendidikan', 'source_type': 'pismp',
     'merit_cutoff': 60.0, 'student_merit': 50.0, 'merit_label': 'Low', 'merit_color': '#ef4444'},
    {'course_id': '50PD02', 'course_name': 'Matematik Pendidikan Rendah',
     'level': 'Ijazah Sarjana Muda Pendidikan', 'field': 'Pendidikan', 'source_type': 'pismp',
     'merit_cutoff': 58.0, 'student_merit': 50.0, 'merit_label': 'Low', 'merit_color': '#ef4444'},
]


class TestInsightsEmpty(TestCase):
    """Test insights with empty input."""

    def test_empty_courses_returns_defaults(self):
        """Empty course list produces safe default insights."""
        result = generate_insights([])
        self.assertEqual(result['stream_breakdown'], [])
        self.assertEqual(result['top_fields'], [])
        self.assertEqual(result['level_distribution'], [])
        self.assertEqual(result['merit_summary']['high'], 0)
        self.assertIn('Tiada', result['summary_text'])


class TestInsightsStreamBreakdown(TestCase):
    """Test stream breakdown counting."""

    def test_stream_counts_correct(self):
        """Each source_type is counted correctly."""
        result = generate_insights(SAMPLE_COURSES)
        breakdown = {s['source_type']: s['count'] for s in result['stream_breakdown']}
        self.assertEqual(breakdown['poly'], 3)
        self.assertEqual(breakdown['tvet'], 2)
        self.assertEqual(breakdown['ua'], 1)
        self.assertEqual(breakdown['pismp'], 2)

    def test_stream_labels_in_malay(self):
        """Stream labels use Malay display names."""
        result = generate_insights(SAMPLE_COURSES)
        labels = {s['source_type']: s['label'] for s in result['stream_breakdown']}
        self.assertEqual(labels['poly'], 'Politeknik')
        self.assertEqual(labels['tvet'], 'TVET')


class TestInsightsTopFields(TestCase):
    """Test top fields ranking."""

    def test_top_field_is_most_common(self):
        """The field with the most courses appears first."""
        result = generate_insights(SAMPLE_COURSES)
        # Kejuruteraan appears 3 times (DIP001, DIP002, TVET02)
        self.assertEqual(result['top_fields'][0]['field'], 'Kejuruteraan')
        self.assertEqual(result['top_fields'][0]['count'], 3)

    def test_top_fields_limited_to_five(self):
        """At most 5 fields are returned."""
        result = generate_insights(SAMPLE_COURSES)
        self.assertLessEqual(len(result['top_fields']), 5)


class TestInsightsMeritSummary(TestCase):
    """Test merit summary aggregation."""

    def test_merit_counts(self):
        """Merit labels are counted correctly."""
        result = generate_insights(SAMPLE_COURSES)
        merit = result['merit_summary']
        self.assertEqual(merit['high'], 3)    # DIP001, DIP002, DIP003
        self.assertEqual(merit['fair'], 1)    # UA001
        self.assertEqual(merit['low'], 2)     # 50PD01, 50PD02
        self.assertEqual(merit['no_data'], 2) # TVET01, TVET02 (no merit)


class TestInsightsLevelDistribution(TestCase):
    """Test level distribution grouping."""

    def test_level_counts(self):
        """Levels are grouped and counted correctly."""
        result = generate_insights(SAMPLE_COURSES)
        levels = {l['level']: l['count'] for l in result['level_distribution']}
        self.assertEqual(levels['Diploma'], 3)
        self.assertEqual(levels['Sijil'], 2)
        self.assertEqual(levels['Asasi'], 1)
        self.assertEqual(levels['Ijazah Sarjana Muda Pendidikan'], 2)


class TestInsightsSummaryText(TestCase):
    """Test summary text generation."""

    def test_summary_mentions_total_and_streams(self):
        """Summary text includes total course count and stream count."""
        result = generate_insights(SAMPLE_COURSES)
        self.assertIn('8', result['summary_text'])   # 8 courses
        self.assertIn('4', result['summary_text'])   # 4 streams
        self.assertIn('Kejuruteraan', result['summary_text'])  # top field
