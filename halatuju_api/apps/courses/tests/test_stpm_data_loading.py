"""Tests for the load_stpm_data management command."""
import pytest
from django.core.management import call_command

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
