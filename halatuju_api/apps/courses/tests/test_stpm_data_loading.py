"""Tests for STPM fixture data integrity and proper_case_name utility."""
import re
import pytest
from django.core.management import call_command
from io import StringIO

from apps.courses.utils import proper_case_name, tidy_parentage_marker
from apps.courses.models import StpmCourse, StpmRequirement


@pytest.mark.django_db
class TestStpmFixtureIntegrity:
    """Verify STPM fixture data is complete and well-formed."""

    @pytest.fixture(autouse=True)
    def load_data(self):
        call_command('loaddata', 'stpm_courses', 'stpm_requirements', stdout=StringIO(), verbosity=0)

    def test_courses_loaded(self):
        assert StpmCourse.objects.count() > 0

    def test_every_course_has_requirement(self):
        courses = StpmCourse.objects.count()
        requirements = StpmRequirement.objects.count()
        assert courses == requirements

    def test_correct_count(self):
        count = StpmCourse.objects.count()
        assert 1000 < count < 1300, f'Expected ~1113, got {count}'

    def test_subject_group_json_parsed(self):
        req = StpmRequirement.objects.filter(
            stpm_subject_group__isnull=False,
        ).first()
        assert req is not None, 'No requirement found with stpm_subject_group'
        group = req.stpm_subject_group
        assert isinstance(group, list), f'Expected list, got {type(group)}'
        assert len(group) > 0, 'Expected at least one subject group'
        assert isinstance(group[0], dict), f'Expected dict in list, got {type(group[0])}'
        assert 'subjects' in group[0] or 'min_count' in group[0]

    def test_boolean_fields(self):
        pa_count = StpmRequirement.objects.filter(stpm_req_pa=True).count()
        assert pa_count > 50, f'Expected >50 PA-required courses, got {pa_count}'

    def test_merit_scores_present(self):
        assert StpmCourse.objects.filter(merit_score__isnull=False).count() > 0

    def test_merit_score_null_for_tiada(self):
        assert StpmCourse.objects.filter(merit_score__isnull=True).exists()

    def test_course_names_are_proper_case(self):
        bad = [
            c.course_name
            for c in StpmCourse.objects.all()
            if re.search(r'\b[A-Z]{3,}\b', c.course_name)
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


class TestTidyParentageMarker:
    """`tidy_parentage_marker` — the WRITE-boundary half of the spaced-marker problem.

    `vision._NAME_NOISE` tolerates 'A/ P' when COMPARING names (added for application #20 so a
    typed space would stop reading as a false Name mismatch against the student's own IC). That
    tolerance is why nothing ever flagged #20's stored name — she typed 'SHARVANI A/ P
    KANAGEVELLU' on the truthfulness declaration, `submit_application` promoted the signature to
    `profile.name` verbatim, and her MyKad reads 'SHARVANI A/P KANAGEVELLU'.
    """

    def test_the_real_case(self):
        assert tidy_parentage_marker('SHARVANI A/ P KANAGEVELLU') == \
            'SHARVANI A/P KANAGEVELLU'

    @pytest.mark.parametrize('typed', [
        'PRIYA A/ P MURUGAN', 'PRIYA A / P MURUGAN', 'PRIYA A /P MURUGAN',
        'PRIYA A/P MURUGAN',
    ])
    def test_every_spacing_variant_lands_on_one_form(self, typed):
        assert tidy_parentage_marker(typed) == 'PRIYA A/P MURUGAN'

    @pytest.mark.parametrize('marker', ['A/L', 'A/P', 'S/O', 'D/O'])
    def test_all_four_markers(self, marker):
        spaced = marker.replace('/', '/ ')
        assert tidy_parentage_marker(f'RAJ {spaced} KUMAR') == f'RAJ {marker} KUMAR'

    def test_idempotent(self):
        once = tidy_parentage_marker('SHARVANI A/ P KANAGEVELLU')
        assert tidy_parentage_marker(once) == once

    def test_leaves_a_name_without_a_marker_completely_alone(self):
        for name in ['TAN WEI MING', 'NUR AISYAH BINTI ABDULLAH', 'SHARVANI KANAGEVELLU', '']:
            assert tidy_parentage_marker(name) == name

    def test_never_touches_spacing_between_NAME_words(self):
        # The guard that matters: it is a marker fix, not a name fix. Only whitespace INSIDE
        # the slash marker moves — the double space between given names survives untouched.
        assert tidy_parentage_marker('PRIYA  DEVI A/ P MURUGAN') == 'PRIYA  DEVI A/P MURUGAN'

    def test_cannot_eat_a_letter_from_an_adjacent_name(self):
        # 'A' and 'P' as whole tokens only — a name ENDING in those letters is not a marker.
        assert tidy_parentage_marker('KALAI A/ P SUPRAMANIAM') == 'KALAI A/P SUPRAMANIAM'
        assert tidy_parentage_marker('MAYA / P SOMETHING') == 'MAYA / P SOMETHING'
