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


class TestReadersOfMaraWithADivisionDiploma:
    """`chosen_pathway='mara'` + an OP course: what the server does with it."""

    @staticmethod
    def _app(**kw):
        base = dict(pathway_certainty='sure', chosen_pathway='mara', intended_pathway='',
                    chosen_programme={'course_id': 'OP4100001', 'course_name': 'Diploma Perakaunan'},
                    pathways_considered=[])
        base.update(kw)
        return SimpleNamespace(**base)

    def test_funding_estimate_is_exactly_todays(self):
        from apps.scholarship.funding_estimate import classify_pathway
        # 'mara' has no estimate category, so the programme decides: an OP id has no no-estimate
        # prefix and its name says Diploma -> 'university', the same as under chosen_pathway='university'.
        assert classify_pathway(self._app()) == 'university'
        assert classify_pathway(self._app(chosen_pathway='university')) == 'university'

    def test_a_upu_diploma_offer_is_the_same_pathway_family(self):
        from apps.scholarship import offer_pathway as op
        offer_type = op.detect_pathway_type('DIPLOMA PERAKAUNAN', 'KOLEJ PROFESIONAL MARA BERANANG')
        assert offer_type == 'diploma'
        assert op.pathway_family(offer_type) == op.pathway_family('mara') == 'tertiary'
        assert not op.is_pre_u('mara')

    def test_results_route_reads_post_spm(self):
        from apps.scholarship.results_route import POST_SPM_CODES
        assert 'mara' in POST_SPM_CODES
