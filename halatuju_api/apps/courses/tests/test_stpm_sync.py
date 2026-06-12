"""Tests for the sync_stpm_mohe management command."""
import csv
import tempfile
import pytest
from io import StringIO
from django.core.management import call_command
from django.core.management.base import CommandError
from apps.courses.models import StpmCourse, FieldTaxonomy
from apps.courses.management.commands.scrape_mohe_stpm import scrape_shortfall


@pytest.fixture
def field_key():
    """Get or create a FieldTaxonomy entry for test courses."""
    ft, _ = FieldTaxonomy.objects.get_or_create(
        key='sains_komputer',
        defaults={
            'name_en': 'Computer Science', 'name_ms': 'Sains Komputer',
            'name_ta': '\u0b95\u0ba3\u0bbf\u0ba9\u0bbf \u0b85\u0bb1\u0bbf\u0bb5\u0bbf\u0baf\u0bb2\u0bcd',
            'image_slug': 'sains-komputer', 'sort_order': 1,
        }
    )
    return ft


@pytest.fixture
def setup_courses(field_key):
    """Create 3 test courses."""
    StpmCourse.objects.create(
        course_id='UM0001', course_name='Course A',
        university='UM', field_key=field_key, merit_score=80.0,
        mohe_url='https://old.url/UM0001',
    )
    StpmCourse.objects.create(
        course_id='USM0002', course_name='Course B',
        university='USM', field_key=field_key, merit_score=70.0,
    )
    StpmCourse.objects.create(
        course_id='UKM0003', course_name='Course C',
        university='UKM', field_key=field_key, merit_score=60.0,
        is_active=True,
    )


def _write_csv(rows):
    """Write rows to a temp CSV and return its path."""
    f = tempfile.NamedTemporaryFile(
        mode='w', suffix='.csv', delete=False, newline='', encoding='utf-8'
    )
    writer = csv.DictWriter(f, fieldnames=[
        'course_id', 'course_name', 'university', 'merit',
        'stream', 'mohe_url', 'badges', 'year',
    ])
    writer.writeheader()
    writer.writerows(rows)
    f.close()
    return f.name


@pytest.mark.django_db
class TestSyncStpmMohe:
    def test_dry_run_reports_removed(self, setup_courses):
        """Dry run should report removed courses but not change DB."""
        csv_path = _write_csv([{
            'course_id': 'UM0001', 'course_name': 'Course A',
            'university': 'UM', 'merit': '80.0',
            'stream': 'science', 'mohe_url': 'https://new.url/UM0001',
            'badges': '', 'year': '2026',
        }])
        out = StringIO()
        call_command('sync_stpm_mohe', csv=csv_path, stdout=out)
        output = out.getvalue()
        assert 'REMOVED' in output
        # DB unchanged — courses still active
        assert StpmCourse.objects.filter(is_active=True).count() == 3

    def test_apply_deactivates_removed(self, setup_courses):
        """--apply should set is_active=False on removed courses."""
        csv_path = _write_csv([{
            'course_id': 'UM0001', 'course_name': 'Course A',
            'university': 'UM', 'merit': '80.0',
            'stream': 'science', 'mohe_url': 'https://new.url/UM0001',
            'badges': '', 'year': '2026',
        }])
        out = StringIO()
        call_command('sync_stpm_mohe', csv=csv_path, apply=True, stdout=out)
        output = out.getvalue()

        assert StpmCourse.objects.get(course_id='UM0001').is_active is True
        assert StpmCourse.objects.get(course_id='USM0002').is_active is False
        assert StpmCourse.objects.get(course_id='UKM0003').is_active is False
        assert 'Deactivated 2' in output

    def test_apply_reactivates_returned_course(self, setup_courses):
        """A previously deactivated course that reappears should be reactivated."""
        StpmCourse.objects.filter(course_id='UKM0003').update(is_active=False)

        csv_path = _write_csv([
            {'course_id': 'UM0001', 'course_name': 'Course A', 'university': 'UM',
             'merit': '80.0', 'stream': 'science', 'mohe_url': '', 'badges': '', 'year': '2026'},
            {'course_id': 'USM0002', 'course_name': 'Course B', 'university': 'USM',
             'merit': '70.0', 'stream': 'science', 'mohe_url': '', 'badges': '', 'year': '2026'},
            {'course_id': 'UKM0003', 'course_name': 'Course C', 'university': 'UKM',
             'merit': '60.0', 'stream': 'science', 'mohe_url': '', 'badges': '', 'year': '2026'},
        ])
        out = StringIO()
        call_command('sync_stpm_mohe', csv=csv_path, apply=True, stdout=out)
        output = out.getvalue()

        assert StpmCourse.objects.get(course_id='UKM0003').is_active is True
        assert 'Reactivated 1' in output

    def test_apply_updates_url(self, setup_courses):
        """--apply should update mohe_url for matched courses."""
        csv_path = _write_csv([{
            'course_id': 'UM0001', 'course_name': 'Course A',
            'university': 'UM', 'merit': '80.0',
            'stream': 'science', 'mohe_url': 'https://new.url/UM0001',
            'badges': '', 'year': '2026',
        }])
        out = StringIO()
        call_command('sync_stpm_mohe', csv=csv_path, apply=True, stdout=out)

        course = StpmCourse.objects.get(course_id='UM0001')
        assert course.mohe_url == 'https://new.url/UM0001'

    def test_reports_merit_changes(self, setup_courses):
        """Merit changes should be reported."""
        csv_path = _write_csv([{
            'course_id': 'UM0001', 'course_name': 'Course A',
            'university': 'UM', 'merit': '85.5',
            'stream': 'science', 'mohe_url': '', 'badges': '', 'year': '2026',
        }])
        out = StringIO()
        call_command('sync_stpm_mohe', csv=csv_path, stdout=out)
        output = out.getvalue()
        assert 'MERIT CHANGES (1)' in output
        assert '80.00%' in output
        assert '85.50%' in output

    def test_reports_new_programmes(self, setup_courses):
        """New programmes in MOHE should be reported."""
        csv_path = _write_csv([
            {'course_id': 'UM0001', 'course_name': 'Course A', 'university': 'UM',
             'merit': '80.0', 'stream': 'science', 'mohe_url': '', 'badges': '', 'year': '2026'},
            {'course_id': 'NEW0001', 'course_name': 'New Course', 'university': 'UPM',
             'merit': '75.0', 'stream': 'science', 'mohe_url': '', 'badges': '', 'year': '2026'},
        ])
        out = StringIO()
        call_command('sync_stpm_mohe', csv=csv_path, stdout=out)
        output = out.getvalue()
        assert 'NEW (1)' in output
        assert 'NEW0001' in output

    def test_dry_run_shows_inactive_count(self, setup_courses):
        """Dry run should show the inactive count."""
        StpmCourse.objects.filter(course_id='UKM0003').update(is_active=False)
        csv_path = _write_csv([
            {'course_id': 'UM0001', 'course_name': 'A', 'university': 'UM',
             'merit': '80.0', 'stream': 'science', 'mohe_url': '', 'badges': '', 'year': '2026'},
            {'course_id': 'USM0002', 'course_name': 'B', 'university': 'USM',
             'merit': '70.0', 'stream': 'science', 'mohe_url': '', 'badges': '', 'year': '2026'},
            {'course_id': 'UKM0003', 'course_name': 'C', 'university': 'UKM',
             'merit': '60.0', 'stream': 'science', 'mohe_url': '', 'badges': '', 'year': '2026'},
        ])
        out = StringIO()
        call_command('sync_stpm_mohe', csv=csv_path, stdout=out)
        output = out.getvalue()
        assert 'Currently inactive: 1' in output


def _make_courses(field_key, n, active=True):
    """Bulk-create N active StpmCourses with ids G0000..G(N-1) for guard tests."""
    StpmCourse.objects.bulk_create([
        StpmCourse(
            course_id=f'G{i:04d}', course_name=f'Course {i}', university='U',
            field_key=field_key, merit_score=70.0, is_active=active,
        )
        for i in range(n)
    ])


def _csv_for_ids(ids):
    return _write_csv([
        {'course_id': cid, 'course_name': 'X', 'university': 'U', 'merit': '70.0',
         'stream': 'science', 'mohe_url': '', 'badges': '', 'year': '2026'}
        for cid in ids
    ])


@pytest.mark.django_db
class TestSyncSafetyGuard:
    """A partial/failed scrape must not deactivate a large slice of the catalogue."""

    def test_apply_aborts_on_mass_deactivation(self, field_key):
        _make_courses(field_key, 60)  # 60 active
        # CSV lists only 50 → 10 would deactivate (16.7% > 10% guard)
        csv_path = _csv_for_ids([f'G{i:04d}' for i in range(50)])
        with pytest.raises(CommandError):
            call_command('sync_stpm_mohe', csv=csv_path, apply=True)
        # Guard fired before any write — nothing deactivated
        assert StpmCourse.objects.filter(is_active=True).count() == 60

    def test_force_overrides_guard(self, field_key):
        _make_courses(field_key, 60)
        csv_path = _csv_for_ids([f'G{i:04d}' for i in range(50)])
        call_command('sync_stpm_mohe', csv=csv_path, apply=True, force=True)
        assert StpmCourse.objects.filter(is_active=False).count() == 10

    def test_small_change_applies_without_force(self, field_key):
        _make_courses(field_key, 60)
        # 3 removed of 60 = 5% < 10% → applies normally
        csv_path = _csv_for_ids([f'G{i:04d}' for i in range(57)])
        call_command('sync_stpm_mohe', csv=csv_path, apply=True)
        assert StpmCourse.objects.filter(is_active=False).count() == 3

    def test_guard_skipped_for_tiny_catalogue(self, setup_courses):
        """Below GUARD_MIN_ACTIVE (50) the guard is off, so small DBs/tests still apply."""
        csv_path = _csv_for_ids(['UM0001'])  # 2 of 3 removed = 66%, but only 3 active
        call_command('sync_stpm_mohe', csv=csv_path, apply=True)
        assert StpmCourse.objects.filter(is_active=False).count() == 2


class TestScrapeShortfall:
    """The scrape sanity check: flag a scrape far below MOHE's reported total."""

    def test_complete_scrape_is_ok(self):
        assert scrape_shortfall(1000, 1002) is False  # within 95% tolerance

    def test_partial_or_zero_scrape_is_shortfall(self):
        assert scrape_shortfall(10, 1002) is True
        assert scrape_shortfall(0, 1002) is True

    def test_unknown_total_is_not_shortfall(self):
        assert scrape_shortfall(0, 0) is False    # couldn't read 'daripada N'
        assert scrape_shortfall(500, 0) is False
