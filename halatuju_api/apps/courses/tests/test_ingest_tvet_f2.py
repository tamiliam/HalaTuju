"""Bumi Sprint F2: the reviewed MARA file (`data/tvet/tvet_new_courses_F2.json`). It rebuilds byte for byte
from its frozen source, names only MARA campuses as MARA-NNN institutions, never reuses an id the catalogue
held before F2, keeps every Bumi page Bumi-only (and a Bumiputera always a citizen), hides a programme
from a colour-blind student when ANY campus page says so, and dry-runs clean through `ingest_tvet_courses`."""
import json
import re
from io import StringIO
from pathlib import Path

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.courses.management.commands.ingest_tvet_courses import (
    held_courses_from_fixtures, load_held_links, load_not_in_prod, precheck_sql, rollback_sql,
    check_sql_ids,
)
from apps.courses.models import Course, CourseInstitution, Institution
from apps.courses.tvet_catalogue_rows import build_review, norm_name, review_summary
from apps.courses.tvet_institutions import mara_kind, state_name

DATA = Path(__file__).resolve().parents[3] / 'data'
F2 = DATA / 'tvet' / 'tvet_new_courses_F2.json'
FIXTURES = Path(__file__).resolve().parents[1] / 'fixtures'
PROD_STATES = {'Johor', 'Kedah', 'Kelantan', 'Melaka', 'Negeri Sembilan', 'Pahang', 'Perak', 'Perlis',
               'Pulau Pinang', 'Sabah', 'Sarawak', 'Selangor', 'Terengganu', 'WP Kuala Lumpur', 'WP Labuan',
               'WP Putrajaya'}


def _review():
    return json.loads(F2.read_text(encoding='utf-8'))


def _ids(path):
    return {c['course_id'] for c in json.loads(path.read_text(encoding='utf-8'))['courses']}


class TestReviewFile:
    def test_rebuilt_byte_for_byte_from_the_committed_source(self):
        source = json.loads((DATA / 'tvet' / 'uptvet_F2_source.json').read_text(encoding='utf-8'))
        links = DATA / 'tvet' / 'held_tvet_links.json'
        review = build_review(source, load_held_links(links), held_courses_from_fixtures(), ('mara',),
                              load_not_in_prod(links))
        review['built_from'] = 'data/tvet/uptvet_F2_source.json'
        review['summary'] = review_summary(review)
        assert json.loads(json.dumps(review, ensure_ascii=False)) == _review()

    def test_only_mara_rows_and_no_held_course(self):
        review = _review()
        assert review['families'] == ['mara'] and all(c['family'] == 'mara' for c in review['courses'])
        assert review['held_links'] == [] and review['held_rule_differences'] == []

    def test_no_flagged_row_is_an_offering(self):
        review = _review()
        flagged = {f['id_kursus'] for f in review['flagged']}
        offered = [o['id_kursus'] for c in review['courses'] for o in c['offerings']]
        assert len(offered) == len(set(offered)) and not set(offered) & flagged
        assert len(offered) + len(flagged) == review['counts']['rows'] == 665

    def test_course_ids_are_new_tvet_ids_of_the_lowest_id_kursus(self):
        review = _review()
        earlier = _ids(DATA / 'tvet' / 'tvet_new_courses_F1.json') | _ids(DATA / 'spm' / 'spm_new_courses_D1.json') \
            | _ids(DATA / 'spm' / 'spm_new_courses_D2.json')
        before_f2 = {c['pk'] for c in json.loads((FIXTURES / 'courses.json').read_text(encoding='utf-8'))} - _ids(F2)
        for course in review['courses']:
            assert course['course_id'] == f"TVET-{min(int(o['id_kursus']) for o in course['offerings'])}"
        ids = [c['course_id'] for c in review['courses']]
        assert len(ids) == len(set(ids)) and not set(ids) & (earlier | before_f2)

    def test_institutions_are_mara_nnn_one_per_campus_in_prods_state_spelling(self):
        review = _review()
        institutions = review['new_institutions']
        assert sorted(institutions) == [f'MARA-{n:03d}' for n in range(1, len(institutions) + 1)]
        for iid, spec in institutions.items():
            assert spec['institution_id'] == iid and spec['type'] == 'ILKA' and spec['category'] == 'MARA'
            assert spec['subcategory'] in ('GIATMARA', 'IKM', 'KKTM', 'MJII') and spec['acronym'] == spec['subcategory']
            assert spec['state'] in PROD_STATES, spec
            assert len(spec['acronym']) <= 20 and len(spec['url']) <= 200
            assert not spec['url'] or re.match(r'^https?://[^\s,]+\.[a-z]{2,}', spec['url']), spec['url']
        campuses = {(o['institution_id'], o['campus']) for c in review['courses'] for o in c['offerings']}
        assert len({iid for iid, _ in campuses}) == len(campuses) == len(institutions)

    def test_every_bumi_course_is_also_citizens_only(self):
        for course in _review()['courses']:
            req = course['requirement']
            assert not req['req_bumiputera'] or req['req_malaysian'], course['course_id']

    def test_colour_hides_when_any_campus_page_excludes_it(self):
        review = _review()
        mixed = [c for c in review['courses'] if c.get('colour_excluded_by')]
        assert mixed and all(c['requirement']['no_colorblind'] for c in mixed)
        source = json.loads((DATA / 'tvet' / 'uptvet_F2_source.json').read_text(encoding='utf-8'))
        for course in mixed:
            assert set(course['colour_excluded_by']) < {o['id_kursus'] for o in course['offerings']}
            assert all(k in source['pages'] for k in course['colour_excluded_by'])

    def test_no_programme_duplicates_a_d2_mara_row(self):
        """D2 ingested the UPU MARA rows (OM Asasi, OP Kolej Profesional MARA diplomas) under MARA-BPT; no
        UP_TVET MARA programme is one of them (lead's check, 2026-10-30)."""
        d2 = [c for c in json.loads((DATA / 'spm' / 'spm_new_courses_D2.json').read_text(encoding='utf-8'))['courses']
              if c['course_id'].startswith(('OM', 'OP'))]
        names = {norm_name(c['course']) for c in d2}
        assert len(d2) == 15 and not names & {norm_name(c['course']) for c in _review()['courses']}

    def test_the_summary(self):
        summary = _review()['summary']
        assert summary['bumi_only_courses'] + summary['open_to_non_bumi_courses'] == len(_review()['courses'])
        assert {s['course'] for s in summary['split_programmes'] if s['differ'] == ['req_bumiputera', 'req_malaysian']}


class TestDerivations:
    def test_mara_kinds_and_states(self):
        assert mara_kind('TVETMARA SIK (INSTITUT KEMAHIRAN MARA SIK)') == 'IKM'
        assert mara_kind('TVETMARA PETALING JAYA (KOLEJ KEMAHIRAN TINGGI MARA PETALING JAYA)') == 'KKTM'
        assert mara_kind('TVETMARA MARA-JAPAN INDUSTRIAL INSTITUTE (MARA JAPAN INDUSTRIAL INSTITUTE)') == 'MJII'
        assert mara_kind('GIATMARA MUAR') == 'GIATMARA'
        assert state_name('W.PERSEKUTUAN (KL)') == 'WP Kuala Lumpur' and state_name('W.PERSEKUTUAN (LABUAN)') == 'WP Labuan'
        assert state_name('W.PERSEKUTUAN (PUTRAJAYA)') == 'WP Putrajaya' and state_name('PULAU PINANG') == 'Pulau Pinang'


def _run(*args):
    out = StringIO()
    call_command('ingest_tvet_courses', *args, stdout=out)
    return out.getvalue()


@pytest.fixture
def catalogue(db):
    call_command('loaddata', 'courses', 'requirements', stdout=StringIO(), verbosity=0)


@pytest.mark.django_db
class TestIngest:
    def test_the_full_file_dry_runs_clean_once_its_rows_are_new(self, catalogue):
        review = _review()
        Course.objects.filter(course_id__in=[c['course_id'] for c in review['courses']]).delete()
        out = _run('--file', str(F2), '--create-institutions')
        assert 'Refusing' not in out and 'DRY RUN' in out
        assert out.count('CREATE INSTITUTION MARA-') == len(review['new_institutions'])
        assert out.count('\nCREATE TVET-') + out.startswith('CREATE TVET-') == len(review['courses'])
        assert 'UPDATE ' not in out and 'LINK ' not in out
        assert f"{len(review['courses'])} new courses ({review['counts']['new_offerings']} campus offerings); " \
               f"0 new campus links to held courses (0 already held); {len(review['flagged'])} flagged rows" in out

    def test_the_fixture_holds_the_f2_rows_so_apply_refuses_an_existing_id(self, catalogue):
        with pytest.raises(CommandError, match='already in the catalogue'):
            _run('--file', str(F2), '--create-institutions', '--apply')
        assert not Institution.objects.filter(institution_id__startswith='MARA-').exists()

    def test_apply_writes_mara_campuses_and_offerings(self, catalogue, tmp_path):
        review = _review()
        course = max(review['courses'], key=lambda c: len(c['offerings']))
        wanted = {o['institution_id'] for o in course['offerings']}
        small = {'courses': [course], 'held_links': [], 'flagged': [],
                 'new_institutions': {k: v for k, v in review['new_institutions'].items() if k in wanted}}
        path = tmp_path / 'f2.json'
        path.write_text(json.dumps(small, ensure_ascii=False), encoding='utf-8')
        Course.objects.filter(course_id=course['course_id']).delete()
        _run('--file', str(path), '--create-institutions', '--apply')
        assert set(Institution.objects.filter(category='MARA').values_list('institution_id', flat=True)) == wanted
        assert CourseInstitution.objects.filter(course_id=course['course_id']).count() == len(course['offerings'])


class TestSql:
    """The lead's read-only pre-check and the rollback come from the file itself (`--sql`, `--rollback-sql`)."""

    def test_the_precheck_names_exactly_the_files_ids_and_reads_only(self):
        review = _review()
        sql = precheck_sql(review)
        statements = [s for s in sql.splitlines() if not s.startswith('--')]
        assert len(statements) == 2 and all(s.startswith('SELECT ') for s in statements)
        assert set(re.findall(r"'(TVET-\d+)'", statements[0])) == {c['course_id'] for c in review['courses']}
        assert set(re.findall(r"'(MARA-\d{3})'", statements[1])) == set(review['new_institutions'])

    def test_the_rollback_is_one_transaction_children_first_institutions_last(self):
        review = _review()
        lines = [s for s in rollback_sql(review).splitlines() if not s.startswith('--')]
        assert all(s.startswith('SELECT ') for s in lines[:lines.index('BEGIN;')])
        body = lines[lines.index('BEGIN;') + 1:lines.index('COMMIT;')]
        tables = [re.match(r'DELETE FROM (\w+)', s).group(1) for s in body]
        assert tables == ['saved_courses', 'admission_outcomes', 'course_tags', 'courses_career_occupations',
                          'course_requirements', 'course_institutions', 'courses', 'institutions']
        assert set(re.findall(r"'(TVET-\d+)'", body[-2])) == {c['course_id'] for c in review['courses']}
        assert set(re.findall(r"'(MARA-\d{3})'", body[-1])) == set(review['new_institutions'])

    def test_the_command_prints_them(self):
        out = _run('--file', str(F2), '--sql')
        assert out.startswith('-- 1. none of the 181 new course ids') and 'DELETE' not in out
        assert 'BEGIN;' in _run('--file', str(F2), '--rollback-sql')

    def test_the_pre_rollback_checks_count_saved_courses(self):
        lines = rollback_sql(_review()).splitlines()
        checks = lines[:lines.index('BEGIN;')]
        assert any(s.startswith('SELECT count(*) FROM saved_courses WHERE course_id IN (') for s in checks)

    @pytest.mark.parametrize('field, value', [
        ('course_id', "TVET-1'; DROP TABLE courses; --"), ('course_id', 'IJTM-CET-001'), ('course_id', 'TVET-12a'),
        ('institution', "MARA-001'"), ('institution', 'MARA-1'), ('institution', 'UNIV-012'),
    ])
    def test_sql_refuses_an_id_outside_the_expected_shapes(self, field, value, tmp_path):
        review = _review()
        if field == 'course_id':
            review['courses'][0]['course_id'] = value
        else:
            review['new_institutions'][value] = dict(next(iter(review['new_institutions'].values())),
                                                     institution_id=value)
        with pytest.raises(CommandError, match='outside the expected shapes'):
            check_sql_ids(review)
        path = tmp_path / 'bad.json'
        path.write_text(json.dumps(review, ensure_ascii=False), encoding='utf-8')
        for flag in ('--sql', '--rollback-sql'):
            with pytest.raises(CommandError, match='outside the expected shapes'):
                _run('--file', str(path), flag)

    def test_the_f1_and_f2_files_pass_the_id_check(self):
        check_sql_ids(_review())
        check_sql_ids(json.loads((DATA / 'tvet' / 'tvet_new_courses_F1.json').read_text(encoding='utf-8')))
