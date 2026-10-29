"""Bumi coverage Sprint D2: which MOHE rows it adds (the bucket rule), how the parser reads their new
shapes (ATAU through reviewed scopes, "A- in ONE AND B in THREE", MARA's Syarat Am), that the review
file is reproducible, and how `ingest_spm_courses` links each row to its own parent institution and
creates the proposed MARA row only when asked."""
import copy
import csv
import json
from collections import Counter
from io import StringIO
from pathlib import Path

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.courses.engine import StudentProfile, check_eligibility
from apps.courses.models import Course, CourseInstitution, CourseRequirement, Institution
from apps.courses.spm_atau_scopes import ATAU_SCOPES
from apps.courses.spm_catalogue_rows import BUMI_MATRIC_TRACKS, INSTITUTION_IDS, NEW_INSTITUTIONS
from apps.courses.spm_syarat import parse_requirements

DATA = Path(__file__).resolve().parents[3] / 'data' / 'spm'
CSV = DATA / 'mohe_bumi_2026-10-29.csv'
D1 = DATA / 'spm_new_courses_D1.json'
D2 = DATA / 'spm_new_courses_D2.json'
IDS = DATA / 'spm_new_courses_D2.ids'
FIXTURE = Path(__file__).resolve().parents[1] / 'fixtures' / 'courses.json'
HELD_ELSEWHERE = {'Politeknik', 'Kolej Komuniti', 'Bahagian Matrikulasi, Kpm', 'Universiti Teknologi Mara'}
PROD_ONLY = {'UL0481001'}   # prod holds it, the fixture does not (lesson L710); not Bumi, not Islamic
ISLAMIC = {'islam', 'pqs', 'psi', 'usul_aldin', 'al_syariah', 'hifz_alquran', 'maharat_alquran',
           'turath_quran_sunnah', 'turath_islamiah', 'manahij', 'tasawwur_islam', 'adab_balaghah',
           'bahasa_arab', 'bahasa_arab_tinggi', 'turath_bahasa_arab', 'lughah_arabiah'}


def _rows():
    with open(CSV, encoding='utf-8') as f:
        return {r['course_id']: r for r in csv.DictReader(f)}


def _ids():
    return [line.split('#')[0].strip() for line in IDS.read_text(encoding='utf-8').splitlines()
            if line.split('#')[0].strip()]


def _d2():
    return json.loads(D2.read_text(encoding='utf-8'))


def _keys(obj):
    """Every subject key named anywhere in a requirement's JSON."""
    if isinstance(obj, dict):
        return set().union(*(_keys(v) for k, v in obj.items() if k not in ('grade', 'count')), set())
    if isinstance(obj, list):
        return set().union(*(_keys(v) for v in obj), set())
    return {obj} if isinstance(obj, str) else set()


class TestTheBuckets:
    def test_the_ids_are_the_rule(self):
        """47 Bumi-only non-UiTM university / MARA rows + 14 open ones never loaded, then the 3 UiTM
        rows D1 flagged and the 2 Bumi Matrikulasi programmes. Nothing else, nothing held before."""
        rows, ids = _rows(), _ids()
        fixture = {o['pk'] for o in json.loads(FIXTURE.read_text(encoding='utf-8'))}
        d1 = {c['course_id'] for c in json.loads(D1.read_text(encoding='utf-8'))['courses']}
        d2 = {c['course_id'] for c in _d2()['courses']}
        original = fixture - d1 - d2
        new = {cid for cid, r in rows.items() if r['university'] not in HELD_ELSEWHERE
               and cid not in original and cid not in PROD_ONLY}
        bumi = {cid for cid in new if rows[cid]['bumi_portal'] == 'Y'}
        assert len(bumi) == 47 and len(new - bumi) == 14
        assert Counter(rows[c]['university'] for c in bumi) == {
            'Universiti Islam Antarabangsa Malaysia': 20, 'Mara, Bahagian Pendidikan Tinggi': 15,
            'Universiti Malaysia Sabah': 4, 'Universiti Malaysia Sarawak': 3, 'Universiti Malaya': 3,
            'Universiti Sultan Zainal Abidin': 2}
        assert Counter(rows[c]['university'] for c in new - bumi) == {
            'Universiti Sultan Zainal Abidin': 9, 'Universiti Sains Islam Malaysia': 4, 'Universiti Malaya': 1}
        matric = {cid for cid, r in rows.items() if r['university'] == 'Bahagian Matrikulasi, Kpm'
                  and r['bumi_portal'] == 'Y'}
        assert matric == set(BUMI_MATRIC_TRACKS)
        assert set(ids) == new | {'UE0520001', 'UE0545001', 'UE4811004'} | matric and len(ids) == 66

    def test_every_row_has_both_bumi_signals_agreeing(self):
        rows = _rows()
        assert all(rows[cid]['bumi_agreement'] in ('both', 'neither') for cid in _ids())


class TestTheFile:
    def test_it_is_what_the_builder_makes(self, tmp_path):
        out = tmp_path / 'd2.json'
        call_command('ingest_spm_courses', '--build-from-csv', str(CSV), '--ids-file', str(IDS),
                     '--out', str(out), stdout=StringIO())
        built, stored = json.loads(out.read_text(encoding='utf-8')), _d2()
        assert built['courses'] == stored['courses'] and built['flagged'] == stored['flagged'] == []
        assert built['new_institutions'] == stored['new_institutions'] == NEW_INSTITUTIONS
        assert len(stored['courses']) == 66

    def test_bumi_flag_institution_and_islamic_subject(self):
        rows = _rows()
        for entry in _d2()['courses']:
            req = entry['requirement']
            code = entry.get('mohe_code', entry['course_id'])
            assert req['req_bumiputera'] == (rows[code]['bumi_portal'] == 'Y'), code
            if not req['req_bumiputera']:   # the 14 open rows: each needs an Islamic subject
                assert _keys(req['complex_requirements']) & ISLAMIC, code
            expected = None if code in BUMI_MATRIC_TRACKS else INSTITUTION_IDS[rows[code]['university']]
            assert entry['institution_id'] == expected, code

    def test_no_rule_is_met_by_the_general_subjects_alone(self):
        """Lesson (D1): a clause every applicant meets is a wrong reading. A Bumi Malaysian with only
        BM and Sejarah, however high, meets no D2 row."""
        student = StudentProfile(grades={'bm': 'A+', 'hist': 'A+'}, gender='Lelaki',
                                 nationality='Warganegara', colorblind=False, disability=False,
                                 bumiputera=True)
        for entry in _d2()['courses']:
            row = {**entry['requirement'], 'course_id': entry['course_id']}
            assert not check_eligibility(student, row)[0], entry['course_id']


class TestRealShapes:
    def _parse(self, cid, scope='reviewed'):
        row = _rows()[cid]
        return parse_requirements(row['syarat_am'], row['syarat_khas'],
                                  ATAU_SCOPES.get(cid) if scope == 'reviewed' else scope)

    def _eligible(self, cid, grades):
        entry = next(e for e in _d2()['courses'] if e.get('mohe_code', e['course_id']) == cid)
        student = StudentProfile(grades=grades, gender='Perempuan', nationality='Warganegara',
                                 colorblind=False, disability=False, bumiputera=True)
        return check_eligibility(student, {**entry['requirement'], 'course_id': entry['course_id']})[0]

    def test_an_atau_row_without_its_scope_is_flagged(self):
        assert any('no reviewed scope' in p for p in self._parse('UY0000004', None)['unparsed'])

    def test_a_scope_that_does_not_fit_is_flagged(self):
        assert any('does not fit' in p or 'covers' in p for p in self._parse('UY0000004', [[1, 1]])['unparsed'])
        assert any('does not fit' in p for p in self._parse('UQ0010002', [[1, 2]])['unparsed'])

    def test_nursing_takes_any_one_science_alternative(self):
        # UY0000004: C in BM, B in English, B in an Islamic subject, C in Sejarah, B in Maths, then
        # C in Kimia/Fizik/Biologi ATAU A in Sains ATAU B in Sains Tambahan, and two more at C.
        base = {'bm': 'C', 'eng': 'B', 'islam': 'B', 'hist': 'C', 'math': 'B', 'geo': 'C', 'poa': 'C',
                'ekonomi': 'C', 'business': 'C'}
        assert self._eligible('UY0000004', {**base, 'bio': 'C'})
        assert self._eligible('UY0000004', {**base, 'sci': 'A'})
        assert not self._eligible('UY0000004', {**base, 'sci': 'B'})

    def test_law_reads_arabic_with_the_b_plus_alternative(self):
        # UY0000007 (scope [[1, 2]]): A- in English, OR B+ in English AND B in an Arabic subject.
        base = {'bm': 'B', 'islam': 'B', 'hist': 'B', 'math': 'C', 'geo': 'C', 'poa': 'C', 'ekonomi': 'C',
                'business': 'C'}
        assert self._eligible('UY0000007', {**base, 'eng': 'A-'})
        assert self._eligible('UY0000007', {**base, 'eng': 'B+', 'bahasa_arab': 'B'})
        assert not self._eligible('UY0000007', {**base, 'eng': 'B+'})

    def test_engineering_needs_four_different_subjects(self):
        # UE0520001: B in English; A- in ONE AND B in THREE of Fizik / Add Maths / Kimia / Maths.
        base = {'bm': 'C', 'hist': 'E', 'eng': 'B', 'geo': 'C', 'poa': 'C', 'ekonomi': 'C', 'business': 'C'}
        assert self._eligible('UE0520001', {**base, 'phy': 'A-', 'addmath': 'B', 'chem': 'B', 'math': 'B'})
        assert not self._eligible('UE0520001', {**base, 'phy': 'A', 'addmath': 'A', 'chem': 'A'})

    def test_mara_syarat_am_is_a_pass_in_bm_and_sejarah(self):
        parsed = self._parse('OP4344001')
        assert parsed['unparsed'] == []
        assert parsed['fields']['pass_bm'] and parsed['fields']['pass_history']
        # "C in one more not yet counted": BM / Sejarah (Am) and Maths / English (Khas) never fill it.
        block = parsed['fields']['complex_requirements']['count_once'][-1]
        assert block['remaining'][0]['exclude'] == ['bm', 'hist', 'math', 'eng']

    def test_the_bumi_matric_rows(self):
        by_id = {e['course_id']: e for e in _d2()['courses']}
        for code, track in BUMI_MATRIC_TRACKS.items():
            req = by_id[track['course_id']]['requirement']
            assert req['req_bumiputera'] and req['source_type'] == req['merit_type'] == 'matric'
            assert by_id[track['course_id']]['level'] == 'Pra-U'


@pytest.fixture
def small_d2(tmp_path):
    """Three D2 rows: a UIAM row (existing parent), a MARA row (proposed parent), a matric row."""
    data = _d2()
    pick = [next(c for c in data['courses'] if c['institution_id'] == 'UNIV-006'),
            next(c for c in data['courses'] if c['institution_id'] == 'MARA-BPT'),
            next(c for c in data['courses'] if c['institution_id'] is None)]
    data['courses'] = copy.deepcopy(pick)
    path = tmp_path / 'd2.json'
    path.write_text(json.dumps(data), encoding='utf-8')
    return path, data


def _run(*args):
    out = StringIO()
    call_command('ingest_spm_courses', *args, stdout=out)
    return out.getvalue()


@pytest.mark.django_db
class TestIngestD2:
    @pytest.fixture(autouse=True)
    def uiam(self):
        Institution.objects.create(institution_id='UNIV-006', institution_name='Universiti Islam Antarabangsa Malaysia',
                                   type='IPTA', state='Selangor')

    def test_a_missing_parent_is_refused_without_the_flag(self, small_d2):
        path, _ = small_d2
        with pytest.raises(CommandError, match="'MARA-BPT' does not exist"):
            _run('--file', str(path), '--apply')
        assert not Institution.objects.filter(institution_id='MARA-BPT').exists()

    def test_the_dry_run_shows_the_institution_and_writes_nothing(self, small_d2):
        path, data = small_d2
        out = _run('--file', str(path), '--create-institutions')
        assert 'CREATE INSTITUTION MARA-BPT' in out and 'DRY RUN' in out
        assert not Institution.objects.filter(institution_id='MARA-BPT').exists()
        assert not Course.objects.filter(course_id=data['courses'][0]['course_id']).exists()

    def test_apply_links_each_row_to_its_own_parent(self, small_d2):
        path, data = small_d2
        _run('--file', str(path), '--create-institutions', '--apply')
        mara = Institution.objects.get(institution_id='MARA-BPT')
        assert mara.acronym == 'MARA' and mara.institution_name == NEW_INSTITUTIONS['MARA-BPT']['institution_name']
        uiam_row, mara_row, matric_row = (c['course_id'] for c in data['courses'])
        assert list(CourseInstitution.objects.filter(course_id=uiam_row).values_list('institution_id', flat=True)) == ['UNIV-006']
        assert list(CourseInstitution.objects.filter(course_id=mara_row).values_list('institution_id', flat=True)) == ['MARA-BPT']
        assert not CourseInstitution.objects.filter(course_id=matric_row).exists()
        assert CourseRequirement.objects.get(course_id=matric_row).merit_type == 'matric'
        # A re-run creates nothing new and does not fail on the held institution.
        out = _run('--file', str(path), '--create-institutions', '--apply')
        assert 'created 0 institutions' in out and Institution.objects.filter(institution_id='MARA-BPT').count() == 1

    def test_a_command_line_parent_cannot_override_the_rows_own(self, small_d2):
        path, _ = small_d2
        with pytest.raises(CommandError, match='names each row'):
            _run('--file', str(path), '--institution-id', 'UNIV-006', '--create-institutions', '--apply')

    def test_only_a_matric_row_may_have_no_parent(self, small_d2, tmp_path):
        _, data = small_d2
        data['courses'][0]['institution_id'] = None
        path = tmp_path / 'bad.json'
        path.write_text(json.dumps(data), encoding='utf-8')
        with pytest.raises(CommandError, match='not a matric row'):
            _run('--file', str(path), '--create-institutions', '--apply')
