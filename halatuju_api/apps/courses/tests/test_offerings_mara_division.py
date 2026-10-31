"""MARA's own diplomas sit under MARA in the scholarship picker (owner, 2026-10-31).

`MARA-BPT` ("Majlis Amanah Rakyat (MARA) - Bahagian Pendidikan Tinggi") offers OM Asasi courses and
OP diplomas. `course_pathway_map` files the OP diplomas under `university`; the scholarship offerings
endpoint serves them under `mara` instead (`views_offerings.MARA_DIVISION`), with the division marked
`no_campus`. Asasi is unchanged, and so is the map itself (the course guide reads it).

The readers of `chosen_pathway='mara'` with an OP course are pinned at the bottom: the funding
estimate is exactly today's, and a UPU diploma offer is the same pathway family as `mara`.
"""
from types import SimpleNamespace

import pytest
from django.apps import apps
from rest_framework.test import APIClient

from apps.courses.models import Course, CourseInstitution, CourseRequirement, FieldTaxonomy, Institution
from apps.courses.views_offerings import MARA_DIVISION

URL = '/api/v1/courses/offerings/'
MAP = {'OP4-AKAUN': 'university', 'OP4-KEJ': 'university', 'OM-ASASI': 'asasi', 'UK-DIP': 'university',
       'MARA-TVET': 'mara'}


def _course(cid, name, source_type):
    c = Course.objects.create(course_id=cid, course=name, level='Diploma', department='-', field='-',
                              field_key_id='eng')
    CourseRequirement.objects.create(course=c, source_type=source_type)
    return c


@pytest.fixture
def catalogue(monkeypatch):
    FieldTaxonomy.objects.get_or_create(key='eng', defaults={
        'name_en': 'Engineering', 'name_ms': 'Kejuruteraan', 'name_ta': 'Eng', 'image_slug': 'eng',
        'sort_order': 1})
    bpt = Institution.objects.create(institution_id=MARA_DIVISION, type='IPTA', state='WP Kuala Lumpur',
                                     institution_name='Majlis Amanah Rakyat (MARA) - Bahagian Pendidikan Tinggi')
    ukm = Institution.objects.create(institution_id='UNIV-UKM', institution_name='Universiti Kebangsaan Malaysia',
                                     type='IPTA', state='Selangor')
    kktm = Institution.objects.create(institution_id='MARA-001', institution_name='KKTM Kemaman',
                                      type='MARA', state='Terengganu')
    for cid, name, src, inst in (('OP4-AKAUN', 'Diploma Perakaunan', 'ua', bpt),
                                 ('OP4-KEJ', 'Diploma Kejuruteraan', 'ua', bpt),
                                 ('OM-ASASI', 'Asasi Sains', 'ua', bpt),
                                 ('UK-DIP', 'Diploma Sains', 'ua', ukm),
                                 ('MARA-TVET', 'Diploma Teknologi', 'tvet', kktm)):
        CourseInstitution.objects.create(course=_course(cid, name, src), institution=inst)
    monkeypatch.setattr(apps.get_app_config('courses'), 'course_pathway_map', dict(MAP), raising=False)


def _body(pathway):
    resp = APIClient().get(URL, {'pathway': pathway})
    assert resp.status_code == 200
    return resp.json()


def _insts(body):
    return {i['id']: i for i in body['institutions']}


@pytest.mark.django_db
class TestOfferings:
    def test_university_leaves_out_the_division_and_its_diplomas(self, catalogue):
        body = _body('university')
        assert set(_insts(body)) == {'UNIV-UKM'}
        assert {c['course_id'] for c in body['courses']} == {'UK-DIP'}

    def test_mara_adds_the_division_with_its_diplomas_never_its_asasi(self, catalogue):
        body = _body('mara')
        insts = _insts(body)
        assert set(insts) == {'MARA-001', MARA_DIVISION}
        assert insts[MARA_DIVISION]['course_ids'] == ['OP4-AKAUN', 'OP4-KEJ']
        assert insts[MARA_DIVISION]['no_campus'] is True
        assert 'no_campus' not in insts['MARA-001']
        assert {c['course_id'] for c in body['courses']} == {'MARA-TVET', 'OP4-AKAUN', 'OP4-KEJ'}

    def test_asasi_is_unchanged(self, catalogue):
        body = _body('asasi')
        assert _insts(body) == {MARA_DIVISION: {
            'id': MARA_DIVISION, 'institution_id': MARA_DIVISION, 'state': 'WP Kuala Lumpur',
            'name': 'Majlis Amanah Rakyat (MARA) - Bahagian Pendidikan Tinggi', 'course_ids': ['OM-ASASI']}}

    def test_the_pathway_map_itself_is_untouched(self, catalogue):
        _body('mara')
        assert apps.get_app_config('courses').course_pathway_map == MAP


class TestADivisionPickIsStoredAsUniversity:
    """Review fix, 2026-10-31: the picker SHOWS the division under MARA but SAVES `chosen_pathway=
    'university'` (`planPicker.storedPathway`), because the money and document readers key on the
    stored pathway. Each test shows the reader on the stored value AND what `mara` would have done."""

    @staticmethod
    def _app(**kw):
        base = dict(pathway_certainty='sure', chosen_pathway='university', intended_pathway='',
                    chosen_programme={'course_id': 'OP4100001', 'course_name': 'Diploma Perakaunan',
                                      'institution_id': MARA_DIVISION},
                    pathways_considered=[], profile=None, cohort=None)
        base.update(kw)
        return SimpleNamespace(**base)

    def test_the_payment_calendar_is_the_university_one(self, monkeypatch):
        from apps.scholarship import award, contracts
        from apps.scholarship.default_schedule import default_rows
        monkeypatch.setattr(award, '_stpm_continuing', lambda app: False)
        row = contracts.pick_schedule_row(default_rows(), self._app())
        assert (row.pathway, row.start_month) == ('university', 8)      # August, November skipped
        assert 3 not in row.paid_offsets
        # Stored as 'mara' it would fall to the default row: July, ten months straight.
        stray = contracts.pick_schedule_row(default_rows(), self._app(chosen_pathway='mara'))
        assert (stray.pathway, stray.start_month) == ('default', 7)

    def test_a_continuing_student_is_still_asked_for_her_semester_result(self, monkeypatch):
        from apps.scholarship import pathway_engine
        from apps.scholarship.income_engine import epf_evidence
        monkeypatch.setattr(epf_evidence, '_docs_or_none', lambda app: [])
        monkeypatch.setattr(epf_evidence, '_has_read_doc', lambda app, kind: False)
        monkeypatch.setattr(epf_evidence, 'heading_for', lambda prof: 'spm')
        monkeypatch.setattr(pathway_engine, 'started_before_cohort', lambda app: True)
        assert epf_evidence.semester_result_gap(self._app()) is True
        assert epf_evidence.semester_result_gap(self._app(chosen_pathway='mara')) is False

    def test_funding_estimate_is_a_university_diplomas(self):
        # The whole estimate for a division pick, stored the way the picker stores it, equals a plain
        # UA diploma's — and is NOT what a MARA skills-campus course gets (no estimate at all).
        from apps.scholarship.funding_estimate import estimate_funding
        division = estimate_funding(self._app())
        plain = estimate_funding(self._app(chosen_programme={
            'course_id': 'UK-DIP', 'course_name': 'Diploma Sains', 'institution_id': 'UNIV-UKM'}))
        campus = estimate_funding(self._app(chosen_pathway='mara', chosen_programme={
            'course_id': 'TVET-MARA-1', 'course_name': 'Diploma Teknologi', 'institution_id': 'MARA-001'}))
        assert division == plain
        assert division['known'] is True and division['pathway'] == 'university'
        assert campus['known'] is False

    def test_a_upu_diploma_offer_is_the_same_pathway_family(self):
        from apps.scholarship import offer_pathway as op
        offer_type = op.detect_pathway_type('DIPLOMA PERAKAUNAN', 'KOLEJ PROFESIONAL MARA BERANANG')
        assert offer_type == 'diploma'
        assert op.pathway_family(offer_type) == op.pathway_family('university') == 'tertiary'


@pytest.mark.django_db
def test_results_route_sends_a_division_diploma_to_post_spm(catalogue):
    """The COURSE ID branch decides: `university` alone is ambiguous (''), and a degree-sounding name
    cannot make an SPM-catalogue OP diploma a degree — only the id (not in `stpm_courses`) answers."""
    from apps.courses.models import StpmCourse
    from apps.scholarship.results_route import DEGREE, POST_SPM, UNDECIDED, destination

    def app(cp):
        return SimpleNamespace(chosen_pathway='university', pre_u_track='', profile=None, chosen_programme=cp)

    assert destination(app({})) == UNDECIDED
    assert destination(app({'course_id': 'OP4-AKAUN', 'course_name': 'Ijazah Sarjana Muda Perakaunan'})) == POST_SPM
    StpmCourse.objects.create(course_id='UM-LAW', course_name='Diploma Sains', university='Universiti Malaya',
                              field_key_id='eng')
    assert destination(app({'course_id': 'UM-LAW', 'course_name': 'Diploma Sains'})) == DEGREE


def test_op4_names_the_division_and_nothing_else():
    """The web picker's `/^OP4/` fallback (`planPicker.isDivisionPick`) reads an OP4 course as a pick of
    the division, for picks saved before the institution id was. That holds only while every OP4 course
    in the catalogue's source files is MARA-BPT's and no MARA campus course id starts with OP4."""
    import json
    from pathlib import Path
    data = Path(__file__).resolve().parents[3] / 'data'
    spm = [c for f in ('spm/spm_new_courses_D1.json', 'spm/spm_new_courses_D2.json')
           for c in json.loads((data / f).read_text(encoding='utf-8'))['courses']]
    tvet = [c for f in ('tvet/tvet_new_courses_F1.json', 'tvet/tvet_new_courses_F2.json')
            for c in json.loads((data / f).read_text(encoding='utf-8'))['courses']]
    op4 = [c for c in spm if c['course_id'].upper().startswith('OP4')]
    assert len(op4) == 13
    assert {c.get('institution_id') for c in op4} == {MARA_DIVISION}
    mara_campus = [c for c in tvet if c.get('family') == 'mara']
    assert mara_campus, 'the MARA campus courses moved: point this test at their new file'
    assert not [c['course_id'] for c in tvet if c['course_id'].upper().startswith('OP4')]
    assert not [o for c in tvet for o in c.get('offerings', []) if o.get('institution_id') == MARA_DIVISION]
