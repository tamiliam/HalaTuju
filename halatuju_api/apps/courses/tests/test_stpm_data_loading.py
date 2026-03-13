"""Tests for the load_stpm_data management command."""
import pytest
from django.core.management import call_command

from apps.courses.management.commands.load_stpm_data import proper_case_name
from apps.courses.models import StpmCourse, StpmRequirement


@pytest.mark.django_db
class TestStpmDataLoading:

    @pytest.fixture(autouse=True)
    def load_data(self):
        """Run the loader once for the whole class."""
        call_command('load_stpm_data')

    def test_load_creates_courses(self):
        """Loader should create StpmCourse records."""
        assert StpmCourse.objects.count() > 0

    def test_load_creates_requirements(self):
        """Every course should have a requirement."""
        courses = StpmCourse.objects.count()
        requirements = StpmRequirement.objects.count()
        assert courses == requirements

    def test_load_correct_count(self):
        """Should load ~1,113 unique programmes from two CSVs with overlap."""
        count = StpmCourse.objects.count()
        assert 1000 < count < 1300, f'Expected ~1113, got {count}'

    def test_load_idempotent(self):
        """Running twice should not duplicate."""
        count_before = StpmCourse.objects.count()
        call_command('load_stpm_data')
        count_after = StpmCourse.objects.count()
        assert count_before == count_after

    def test_load_parses_subject_group_json(self):
        """JSON subject group should be parsed correctly."""
        # Find any requirement with a non-null stpm_subject_group
        req = StpmRequirement.objects.filter(
            stpm_subject_group__isnull=False,
        ).first()
        assert req is not None, 'No requirement found with stpm_subject_group'
        group = req.stpm_subject_group
        assert isinstance(group, dict), f'Expected dict, got {type(group)}'
        assert 'subjects' in group or 'min_count' in group

    def test_load_boolean_fields(self):
        """PA required for most courses (count > 100)."""
        pa_count = StpmRequirement.objects.filter(stpm_req_pa=True).count()
        assert pa_count > 100, f'Expected >100 PA-required courses, got {pa_count}'

    def test_merit_score_loaded(self):
        """Merit scores are loaded from source CSVs."""
        courses_with_merit = StpmCourse.objects.filter(
            merit_score__isnull=False
        )
        assert courses_with_merit.count() > 0

    def test_merit_score_tiada_is_null(self):
        """Programmes with 'Tiada' merit have null merit_score."""
        courses_without_merit = StpmCourse.objects.filter(
            merit_score__isnull=True
        )
        assert courses_without_merit.exists()

    def test_program_names_are_proper_case(self):
        """After loading, no program_name should contain a plain all-caps word > 2 chars."""
        import re
        bad = [
            c.program_name
            for c in StpmCourse.objects.all()
            if re.search(r'\b[A-Z]{3,}\b', c.program_name)
        ]
        assert bad == [], f'Found {len(bad)} names still in all-caps: {bad[:5]}'


class TestProperCaseName:
    """Unit tests for the proper_case_name() utility (no DB required)."""

    def test_basic_malay_connector(self):
        assert proper_case_name('BACELOR EKONOMI DENGAN KEPUJIAN') == \
            'Bacelor Ekonomi dengan Kepujian'

    def test_parenthesised_campus_suffix(self):
        result = proper_case_name(
            'BACELOR SAINS KOMPUTER (RANGKAIAN KOMPUTER) DENGAN KEPUJIAN'
        )
        assert result == 'Bacelor Sains Komputer (Rangkaian Komputer) dengan Kepujian'

    def test_english_connectors(self):
        assert proper_case_name('BACHELOR OF OPERATIONAL RESEARCH WITH DATA SCIENCE') == \
            'Bachelor of Operational Research with Data Science'

    def test_hash_marker_preserved(self):
        assert proper_case_name('DOKTOR PERUBATAN #') == 'Doktor Perubatan #'

    def test_malay_dan_connector(self):
        assert proper_case_name('BACELOR SAINS DAN TEKNOLOGI MAKANAN DENGAN KEPUJIAN') == \
            'Bacelor Sains dan Teknologi Makanan dengan Kepujian'

    def test_first_word_never_lowercased(self):
        """Even if the first word is a connector, it must be capitalised."""
        assert proper_case_name('DAN LAIN-LAIN') == 'Dan Lain-Lain'

    def test_empty_string_returns_empty(self):
        assert proper_case_name('') == ''

    def test_already_proper_case_unchanged(self):
        name = 'Bacelor Ekonomi dengan Kepujian'
        assert proper_case_name(name) == name

    def test_upm_sarawak_suffix(self):
        result = proper_case_name(
            'BACELOR SAINS AKUAKULTUR DENGAN KEPUJIAN '
            '(UNIVERSITI PUTRA MALAYSIA SARAWAK)'
        )
        assert result == (
            'Bacelor Sains Akuakultur dengan Kepujian '
            '(Universiti Putra Malaysia Sarawak)'
        )
