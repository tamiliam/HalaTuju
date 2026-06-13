"""Tests for the sync_spm_mohe management command.

The critical behaviour under test is the RESTRICTION: only MOHE-coded (KOD PROGRAM) courses
are ever compared/deactivated — the synthetic-ID Poly/KK/TVET/PISMP catalogue is never touched.
"""
import csv
import tempfile
import pytest
from io import StringIO
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.courses.models import Course, CourseRequirement, FieldTaxonomy
from apps.courses.management.commands.sync_spm_mohe import is_mohe_coded


@pytest.fixture
def field_key(db):
    ft, _ = FieldTaxonomy.objects.get_or_create(
        key='sains_komputer',
        defaults={
            'name_en': 'Computer Science', 'name_ms': 'Sains Komputer',
            'name_ta': 'CS', 'image_slug': 'sains-komputer', 'sort_order': 1,
        },
    )
    return ft


def _make_course(course_id, field_key, *, name='Course', merit=80.0, is_active=True):
    c = Course.objects.create(
        course_id=course_id, course=name, level='Asasi', department='Dept',
        field='Umum', field_key=field_key, is_active=is_active,
    )
    CourseRequirement.objects.create(course=c, merit_cutoff=merit)
    return c


def _write_csv(rows):
    f = tempfile.NamedTemporaryFile(
        mode='w', suffix='.csv', delete=False, newline='', encoding='utf-8',
    )
    writer = csv.DictWriter(f, fieldnames=[
        'course_id', 'course_name', 'university', 'merit',
        'stream', 'mohe_url', 'badges', 'year',
    ])
    writer.writeheader()
    for r in rows:
        writer.writerow({k: r.get(k, '') for k in writer.fieldnames})
    f.close()
    return f.name


def _row(course_id, merit='', name='Course', university='UA'):
    return {'course_id': course_id, 'course_name': name, 'university': university,
            'merit': merit, 'stream': 'current'}


# ── is_mohe_coded ──────────────────────────────────────────────────
class TestIsMoheCoded:
    @pytest.mark.parametrize('cid', ['UK0010001', 'UR4521002', 'UZ4221001'])
    def test_mohe_codes_match(self, cid):
        assert is_mohe_coded(cid)

    @pytest.mark.parametrize('cid', [
        'POLY-DIP-036', 'KKOM-CET-029', 'IKBN-CET-027', '50PD047R00P', '', None, 'UK001', 'UKM00010001',
    ])
    def test_non_mohe_codes_excluded(self, cid):
        assert not is_mohe_coded(cid)


# ── restriction: synthetic IDs are never touched ───────────────────
@pytest.mark.django_db
class TestRestriction:
    def test_synthetic_ids_never_deactivated_even_if_absent_from_scrape(self, field_key):
        # A Poly course (synthetic ID) absent from the scrape must NOT be deactivated.
        _make_course('POLY-DIP-001', field_key, name='Poly course')
        _make_course('UK0010001', field_key, name='UA course')
        csv_path = _write_csv([_row('UK0010001', merit='80.0')])  # only the UA course present

        call_command('sync_spm_mohe', '--csv', csv_path, '--apply')

        assert Course.objects.get(course_id='POLY-DIP-001').is_active is True
        assert Course.objects.get(course_id='UK0010001').is_active is True

    def test_non_mohe_scrape_rows_dropped_from_comparison(self, field_key):
        _make_course('UK0010001', field_key, merit=80.0)
        out = StringIO()
        # Scrape carries a Poly code too — it should be dropped, not treated as NEW.
        csv_path = _write_csv([_row('UK0010001', merit='80.0'), _row('POLY-DIP-999', merit='50.0')])
        call_command('sync_spm_mohe', '--csv', csv_path, stdout=out)
        report = out.getvalue()
        assert 'dropped 1 non-MOHE-coded' in report
        assert 'POLY-DIP-999' not in report  # never surfaced as NEW


# ── core diff behaviour (mirrors test_stpm_sync) ───────────────────
@pytest.mark.django_db
class TestSyncBehaviour:
    def test_dry_run_reports_removed_does_not_apply(self, field_key):
        _make_course('UK0010001', field_key)
        _make_course('UK0010002', field_key, name='Gone')
        csv_path = _write_csv([_row('UK0010001', merit='80.0')])  # UK0010002 removed
        out = StringIO()
        call_command('sync_spm_mohe', '--csv', csv_path, stdout=out)
        assert 'REMOVED' in out.getvalue()
        # Dry run: nothing changed.
        assert Course.objects.get(course_id='UK0010002').is_active is True

    def test_apply_deactivates_removed(self, field_key):
        _make_course('UK0010001', field_key)
        _make_course('UK0010002', field_key, name='Gone')
        csv_path = _write_csv([_row('UK0010001', merit='80.0')])
        call_command('sync_spm_mohe', '--csv', csv_path, '--apply')
        assert Course.objects.get(course_id='UK0010002').is_active is False

    def test_apply_reactivates_returned(self, field_key):
        _make_course('UK0010001', field_key, is_active=False)  # was inactive
        csv_path = _write_csv([_row('UK0010001', merit='80.0')])  # back in scrape
        call_command('sync_spm_mohe', '--csv', csv_path, '--apply')
        assert Course.objects.get(course_id='UK0010001').is_active is True

    def test_apply_updates_merit_cutoff(self, field_key):
        _make_course('UK0010001', field_key, merit=80.0)
        csv_path = _write_csv([_row('UK0010001', merit='88.5')])
        call_command('sync_spm_mohe', '--csv', csv_path, '--apply')
        assert Course.objects.get(course_id='UK0010001').requirement.merit_cutoff == pytest.approx(88.5)

    def test_new_reported_not_added(self, field_key):
        _make_course('UK0010001', field_key)
        csv_path = _write_csv([_row('UK0010001', merit='80.0'), _row('UK9999999', merit='70.0', name='Brand new')])
        out = StringIO()
        call_command('sync_spm_mohe', '--csv', csv_path, '--apply', stdout=out)
        assert 'NEW' in out.getvalue() and 'UK9999999' in out.getvalue()
        assert not Course.objects.filter(course_id='UK9999999').exists()


# ── mass-deactivation guard ────────────────────────────────────────
@pytest.mark.django_db
class TestGuard:
    def test_guard_blocks_mass_deactivation(self, field_key):
        # 60 active MOHE-coded courses; a scrape with only 1 would deactivate 59 (98%) -> abort.
        for i in range(60):
            _make_course(f'UK00{i:05d}', field_key)
        csv_path = _write_csv([_row('UK0000000', merit='80.0')])
        with pytest.raises(CommandError, match='Refusing to apply'):
            call_command('sync_spm_mohe', '--csv', csv_path, '--apply')
        # Nothing deactivated (scope to our IDs — the test DB carries unrelated seeded rows).
        assert Course.objects.filter(course_id__startswith='UK000', is_active=False).count() == 0

    def test_force_overrides_guard(self, field_key):
        for i in range(60):
            _make_course(f'UK00{i:05d}', field_key)
        csv_path = _write_csv([_row('UK0000000', merit='80.0')])
        call_command('sync_spm_mohe', '--csv', csv_path, '--apply', '--force')
        assert Course.objects.filter(course_id__startswith='UK000', is_active=False).count() == 59

    def test_small_catalogue_not_guarded(self, field_key):
        # Below GUARD_MIN_ACTIVE (50) the guard is inactive (tests / fresh DB).
        _make_course('UK0010001', field_key)
        _make_course('UK0010002', field_key)
        csv_path = _write_csv([])  # both removed
        call_command('sync_spm_mohe', '--csv', csv_path, '--apply')
        assert Course.objects.filter(course_id__startswith='UK0010', is_active=False).count() == 2
