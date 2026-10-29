"""`ingest_spm_courses` (Bumi Sprint D1): dry run by default, refuses an unsafe file, writes Course +
CourseRequirement + ONE CourseInstitution on --apply, idempotently; and the review-file builder."""
import json
from io import StringIO
from pathlib import Path

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.courses.models import Course, CourseInstitution, CourseRequirement, FieldTaxonomy, Institution
from apps.courses.spm_catalogue_rows import build_entry, clean_name, parse_merit

D1 = Path(__file__).resolve().parents[3] / 'data' / 'spm' / 'spm_new_courses_D1.json'
CSV = Path(__file__).resolve().parents[3] / 'data' / 'spm' / 'mohe_bumi_2026-10-29.csv'


def _run(*args):
    out = StringIO()
    call_command('ingest_spm_courses', *args, stdout=out)
    return out.getvalue()


@pytest.fixture
def uitm(db):
    return Institution.objects.create(institution_id='UITM-TEST', institution_name='Universiti Teknologi MARA',
                                      type='IPTA', state='Selangor')


@pytest.fixture
def small_file(tmp_path):
    data = json.loads(D1.read_text(encoding='utf-8'))
    data['courses'] = data['courses'][:3]
    path = tmp_path / 'd1.json'
    path.write_text(json.dumps(data), encoding='utf-8')
    return path, data


@pytest.mark.django_db
class TestIngest:
    def test_dry_run_writes_nothing(self, uitm, small_file):
        path, data = small_file
        out = _run('--file', str(path), '--institution-id', uitm.institution_id)
        assert 'DRY RUN' in out and out.count('CREATE ') == 3
        assert not Course.objects.filter(course_id=data['courses'][0]['course_id']).exists()

    def test_apply_writes_course_requirement_and_one_parent_institution(self, uitm, small_file):
        path, data = small_file
        _run('--file', str(path), '--institution-id', uitm.institution_id, '--apply')
        entry = data['courses'][0]
        course = Course.objects.get(course_id=entry['course_id'])
        assert course.course == entry['course'] and course.field_key_id == entry['field_key']
        req = CourseRequirement.objects.get(course=course)
        assert req.req_bumiputera and req.source_type == 'ua'
        assert req.complex_requirements == entry['requirement']['complex_requirements']
        links = CourseInstitution.objects.filter(course=course)
        assert [link.institution_id for link in links] == [uitm.institution_id]
        assert links[0].hyperlink == entry['mohe_url']

    def test_apply_is_idempotent_and_can_clear_a_flag(self, uitm, small_file, tmp_path):
        path, data = small_file
        _run('--file', str(path), '--institution-id', uitm.institution_id, '--apply')
        cid = data['courses'][0]['course_id']
        CourseRequirement.objects.filter(course_id=cid).update(pass_islam=True)
        _run('--file', str(path), '--institution-id', uitm.institution_id, '--apply')
        assert Course.objects.filter(course_id=cid).count() == 1
        assert CourseInstitution.objects.filter(course_id=cid).count() == 1
        assert not CourseRequirement.objects.get(course_id=cid).pass_islam

    def test_refuses_without_an_existing_institution(self, small_file):
        path, _ = small_file
        with pytest.raises(CommandError, match='institution-id is required'):
            _run('--file', str(path), '--apply')
        with pytest.raises(CommandError, match='does not exist'):
            _run('--file', str(path), '--institution-id', 'NOPE', '--apply')

    def test_refuses_an_unknown_field_key_or_an_unparsed_row(self, uitm, small_file, tmp_path):
        _, data = small_file
        data['courses'][0]['field_key'] = 'not-a-key'
        data['courses'][1]['unparsed'] = ['ATAU']
        path = tmp_path / 'bad.json'
        path.write_text(json.dumps(data), encoding='utf-8')
        with pytest.raises(CommandError) as err:
            _run('--file', str(path), '--institution-id', uitm.institution_id, '--apply')
        assert 'not-a-key' in str(err.value) and 'ATAU' in str(err.value)
        assert not Course.objects.filter(course_id=data['courses'][2]['course_id']).exists()

    def test_every_d1_field_key_is_a_taxonomy_key(self):
        keys = set(FieldTaxonomy.objects.values_list('key', flat=True))
        data = json.loads(D1.read_text(encoding='utf-8'))
        assert {c['field_key'] for c in data['courses']} <= keys


class TestBuild:
    def test_the_d1_file_is_what_the_builder_makes(self, tmp_path):
        """The reviewed file in the repo is reproducible from the scrape (no hand edits hiding)."""
        out = tmp_path / 'd1.json'
        call_command('ingest_spm_courses', '--build-from-csv', str(CSV), '--prefix', 'UE',
                     '--out', str(out), stdout=StringIO())
        built = json.loads(out.read_text(encoding='utf-8'))
        stored = json.loads(D1.read_text(encoding='utf-8'))
        assert built['courses'] == stored['courses'] and built['flagged'] == stored['flagged']
        assert len(built['courses']) == 84
        assert [f['course_id'] for f in built['flagged']] == ['UE0520001', 'UE0545001', 'UE4811004']

    def test_names_and_merit(self):
        assert clean_name('DIPLOMA SENI HALUS\n          \n      Baru') == 'Diploma Seni Halus'
        assert clean_name('ASASI UNDANG-UNDANG (UITM)') == 'Asasi Undang-Undang (UiTM)'
        assert parse_merit('') is None and parse_merit('Baru') is None and parse_merit('86.64') == 86.64

    def test_an_entry_keeps_its_source_texts(self):
        row = {'course_id': 'UE4344001', 'course_name': 'DIPLOMA PERAKAUNAN', 'merit': '81.90',
               'university': 'Universiti Teknologi Mara', 'mohe_url': 'https://x',
               'syarat_am': 'AM', 'syarat_khas': 'KHAS'}
        entry = build_entry(row)
        assert entry['source'] == {'syarat_am': 'AM', 'syarat_khas': 'KHAS'}
        assert entry['level'] == 'Diploma' and entry['department'] == 'Perniagaan Dan Pengurusan'
        assert entry['unparsed']  # 'AM' is not a Syarat Am: flagged, never guessed
