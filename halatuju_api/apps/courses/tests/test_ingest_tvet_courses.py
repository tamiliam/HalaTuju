"""`ingest_tvet_courses` (Bumi Sprint F1): the review file is reproducible from the committed source, the
ingest is a dry run by default, refuses an unsafe file, writes ONE course with MANY campus offerings,
never touches a held course's rule, and creates a proposed institution only on purpose."""
import json
from io import StringIO
from pathlib import Path

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.courses.management.commands.ingest_tvet_courses import (
    held_courses_from_fixtures, load_held_links,
)
from apps.courses.models import Course, CourseInstitution, CourseRequirement, Institution
from apps.courses.tvet_catalogue_rows import build_review, clean_name, field_of, level_of, semesters_of
from apps.courses.tvet_institutions import HELD, held_institution

DATA = Path(__file__).resolve().parents[3] / 'data' / 'tvet'
F1 = DATA / 'tvet_new_courses_F1.json'


def _review():
    return json.loads(F1.read_text(encoding='utf-8'))


def _run(*args):
    out = StringIO()
    call_command('ingest_tvet_courses', *args, stdout=out)
    return out.getvalue()


class TestReviewFile:
    def test_rebuilt_byte_for_byte_from_the_committed_source(self):
        source = json.loads((DATA / 'uptvet_F1_source.json').read_text(encoding='utf-8'))
        review = build_review(source, load_held_links(DATA / 'held_tvet_links.json'), held_courses_from_fixtures())
        review['built_from'] = 'data/tvet/uptvet_F1_source.json'
        assert json.loads(json.dumps(review, ensure_ascii=False)) == _review()

    def test_no_mara_row_and_no_flagged_row_is_a_course(self):
        review = _review()
        flagged = {f['id_kursus'] for f in review['flagged']}
        assert all(c['family'] != 'mara' for c in review['courses'])
        offered = {o['id_kursus'] for c in review['courses'] for o in c['offerings']}
        assert not offered & flagged
        assert {x['id_kursus'] for x in review['held_links']}.isdisjoint(flagged)

    def test_course_ids_are_the_lowest_id_kursus_of_each_group(self):
        for course in _review()['courses']:
            assert course['course_id'] == f"TVET-{min(int(o['id_kursus']) for o in course['offerings'])}"

    def test_every_offering_names_a_held_or_proposed_institution(self):
        review = _review()
        known = set(HELD) | set(review['new_institutions'])
        assert {o['institution_id'] for c in review['courses'] for o in c['offerings']} <= known
        assert {x['institution_id'] for x in review['held_links']} <= known

    def test_proposed_institutions_follow_the_scheme(self):
        for iid, spec in _review()['new_institutions'].items():
            assert spec['type'] == 'ILKA' and iid not in HELD
            if spec['category'] == 'ILKBS':
                assert iid.startswith('IKBN-')
            else:
                assert spec['category'] == 'TVET' and iid.startswith('ILKA-')

    def test_held_courses_keep_their_rule_differences_for_review_only(self):
        review = _review()
        assert review['held_rule_differences'] and all(d['course_id'].startswith(('IJTM-', 'IKBN-'))
                                                       for d in review['held_rule_differences'])
        assert not any(c['course_id'].startswith(('IJTM-', 'IKBN-')) for c in review['courses'])


class TestDerivations:
    def test_names(self):
        assert clean_name('DIPLOMA TEKNOLOGI ELEKTRIK (PENJAGA JENTERA ELEKTRIK - A1)') == \
            'Diploma Teknologi Elektrik (Penjaga Jentera Elektrik - A1)'
        assert clean_name('Sijil Teknologi Automotif (Pembuatan) #') == 'Sijil Teknologi Automotif (Pembuatan)'

    def test_level_semesters_field(self):
        assert level_of('SIJIL LANJUTAN TEKNOLOGI MARIN', 'Sijil Kemahiran Malaysia / Sijil Tahap 3') == 'Sijil Lanjutan'
        assert level_of('Sijil X', 'Diploma Kemahiran Malaysia / Diploma Tahap 4') == 'Diploma'
        assert semesters_of('27 Bulan') == 4 and semesters_of('') is None
        assert field_of('Diploma Teknologi Pembuatan Makanan (Pemprosesan)')[1] == 'kulinari'
        assert field_of('Sijil Teknologi Automotif (Pembuatan)')[1] == 'automotif'
        assert field_of('Sijil Kursus Tanpa Bidang') is None

    def test_the_field_rules_agree_with_the_held_courses(self):
        """The rules were written against the 84 hand-classified held courses; most must agree."""
        held = json.loads((Path(__file__).resolve().parents[1] / 'fixtures' / 'courses.json').read_text(encoding='utf-8'))
        rows = [c['fields'] for c in held if c['pk'].startswith(('IJTM-', 'IKBN-'))]
        agree = sum(1 for r in rows if (field_of(r['course']) or ('', ''))[1] == r['field_key'])
        assert agree >= 0.85 * len(rows), agree

    def test_campuses(self):
        assert held_institution('iljtm', 'ADTEC JTM KAMPUS PEDAS (ILP PEDAS)') == 'IJTM-019'
        assert held_institution('ilkbs', 'INSTITUT KEMAHIRAN TINGGI BELIA NEGARA PAGOH') == 'IKBN-006'
        assert held_institution('ilkbs', 'INSTITUT KEMAHIRAN BELIA NEGARA KEMASIK') == 'IKBN-017'
        assert held_institution('ilkbs', 'INSTITUT KEMAHIRAN SUKAN NEGARA (AKBG)') is None


def _small(tmp_path, review=None):
    review = review or _review()
    course = next(c for c in review['courses'] if len(c['offerings']) > 1)
    proposed = next(c for c in review['courses'] if any(o['institution_id'].startswith('ILKA-') for o in c['offerings']))
    link = next(x for x in review['held_links'] if not x['already_linked'])
    data = {'courses': [course, proposed], 'held_links': [link], 'flagged': review['flagged'][:2],
            'new_institutions': review['new_institutions']}
    path = tmp_path / 'f1.json'
    path.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
    return path, data


@pytest.fixture
def catalogue(db):
    call_command('loaddata', 'courses', 'requirements', stdout=StringIO(), verbosity=0)
    for iid, (name, subcategory, state) in HELD.items():
        Institution.objects.create(institution_id=iid, institution_name=name, type='ILKA', state=state,
                                   category='ILJTM' if iid.startswith('IJTM') else 'ILKBS', subcategory=subcategory)


@pytest.mark.django_db
class TestIngest:
    def test_dry_run_writes_nothing(self, catalogue, tmp_path):
        path, data = _small(tmp_path)
        out = _run('--file', str(path), '--create-institutions')
        assert 'DRY RUN' in out and 'CREATE INSTITUTION ILKA-' in out and 'LINK ' in out
        assert not Course.objects.filter(course_id=data['courses'][0]['course_id']).exists()
        assert not Institution.objects.filter(institution_id__startswith='ILKA-').exists()

    def test_refuses_a_missing_institution_without_create(self, catalogue, tmp_path):
        path, _ = _small(tmp_path)
        with pytest.raises(CommandError, match='does not exist'):
            _run('--file', str(path), '--apply')

    def test_apply_writes_one_course_many_campuses_and_the_held_link(self, catalogue, tmp_path):
        path, data = _small(tmp_path)
        link = data['held_links'][0]
        held_before = CourseRequirement.objects.filter(course_id=link['course_id']).values()[0]
        _run('--file', str(path), '--create-institutions', '--apply')
        entry = data['courses'][0]
        course = Course.objects.get(course_id=entry['course_id'])
        assert course.course == entry['course'] and course.description == entry['description']
        req = CourseRequirement.objects.get(course=course)
        assert req.source_type == 'tvet' and req.remarks == entry['requirement']['remarks']
        offerings = CourseInstitution.objects.filter(course=course)
        assert sorted(o.institution_id for o in offerings) == sorted(o['institution_id'] for o in entry['offerings'])
        assert all(o.hyperlink.startswith('https://mohon.tvet.gov.my/') for o in offerings)
        assert CourseInstitution.objects.filter(course_id=link['course_id'], institution_id=link['institution_id']).exists()
        assert CourseRequirement.objects.filter(course_id=link['course_id']).values()[0] == held_before
        new = Institution.objects.filter(institution_id__startswith='ILKA-')
        assert new.exists() and all(i.category == 'TVET' and i.type == 'ILKA' for i in new)

    def test_apply_is_idempotent_and_never_overwrites_an_institution(self, catalogue, tmp_path):
        path, data = _small(tmp_path)
        iid = next(iter(data['new_institutions']))
        Institution.objects.create(institution_id=iid, institution_name='Already here', type='IPTA', state='X')
        _run('--file', str(path), '--create-institutions', '--apply')
        _run('--file', str(path), '--create-institutions', '--apply')
        assert Institution.objects.get(institution_id=iid).institution_name == 'Already here'
        cid = data['courses'][0]['course_id']
        assert CourseInstitution.objects.filter(course_id=cid).count() == len(data['courses'][0]['offerings'])

    def test_an_existing_held_link_is_left_as_it_is(self, catalogue, tmp_path):
        path, data = _small(tmp_path)
        link = data['held_links'][0]
        CourseInstitution.objects.create(course_id=link['course_id'], institution_id=link['institution_id'],
                                         hyperlink='https://example.org/kept', tuition_fee_semester='Percuma')
        _run('--file', str(path), '--create-institutions', '--apply')
        kept = CourseInstitution.objects.get(course_id=link['course_id'], institution_id=link['institution_id'])
        assert kept.hyperlink == 'https://example.org/kept'

    def test_refuses_a_link_to_a_held_course_that_does_not_exist(self, catalogue, tmp_path):
        path, data = _small(tmp_path)
        data['held_links'][0]['course_id'] = 'IJTM-CET-999'
        path.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
        with pytest.raises(CommandError, match='IJTM-CET-999'):
            _run('--file', str(path), '--create-institutions', '--apply')

    def test_the_full_file_dry_runs_clean(self, catalogue):
        out = _run('--file', str(F1), '--create-institutions')
        assert 'Refusing' not in out
        assert f"{len(_review()['courses'])} new courses" in out
