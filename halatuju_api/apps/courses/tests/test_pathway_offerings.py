"""GET /api/v1/courses/offerings/?pathway= — the scholarship pickers' institution-first catalogue
(Scholarship My Plans redesign, owner rulings 2026-10-30).

What this pins:
  * one pathway's institutions (id, name, state) and the courses EACH one offers;
  * UNFILTERED: Bumiputera-only and inactive courses are served (Option A; a student may already be
    enrolled on a course MOHE has since dropped) — nothing reads a student, a token or a result;
  * `degree` serves the STPM catalogue grouped by the university the catalogue names, the same
    spelling `offer_pathway._campus_rows` compares an offer letter against;
  * read-only, public, cacheable; an unknown pathway is refused, never answered with everything.
"""
import pytest
from django.apps import apps
from rest_framework.test import APIClient

from apps.courses.models import (Course, CourseInstitution, CourseRequirement, FieldTaxonomy,
                                 Institution, StpmCourse, StpmRequirement)
from apps.courses.views_offerings import OFFERING_PATHWAYS

URL = '/api/v1/courses/offerings/'


def _course(cid, name, source_type='poly', bumi=False, active=True):
    c = Course.objects.create(course_id=cid, course=name, level='Diploma', department='-', field='-',
                              field_key_id='eng', is_active=active)
    CourseRequirement.objects.create(course=c, source_type=source_type, req_bumiputera=bumi)
    return c


def _inst(iid, name, state):
    return Institution.objects.create(institution_id=iid, institution_name=name, type='Politeknik',
                                      state=state)


@pytest.fixture
def catalogue(monkeypatch):
    FieldTaxonomy.objects.get_or_create(key='eng', defaults={
        'name_en': 'Engineering', 'name_ms': 'Kejuruteraan', 'name_ta': 'Eng', 'image_slug': 'eng',
        'sort_order': 1})
    puo, pkb = _inst('POLY-PUO', 'Politeknik Ungku Omar', 'Perak'), _inst('POLY-PKB', 'Politeknik Kota Bharu', 'Kelantan')
    elek = _course('P-ELEK', 'Diploma Kejuruteraan Elektrik')
    mek = _course('P-MEK', 'Diploma Kejuruteraan Mekanikal', active=False)       # MOHE dropped it
    bumi = _course('P-BUMI', 'Diploma Bumiputera Sahaja', bumi=True)             # Bumi-only
    _course('K-KOM', 'Sijil Komuniti', source_type='kkom')                      # another pathway
    for c, i in ((elek, puo), (mek, puo), (bumi, pkb), (elek, pkb)):
        CourseInstitution.objects.create(course=c, institution=i)
    uitm = _inst('UITM', 'Universiti Teknologi MARA (UiTM)', 'Selangor')
    deg = StpmCourse.objects.create(course_id='UI-LAW', course_name='Ijazah Sarjana Muda Undang-Undang',
                                    university='Universiti Teknologi MARA', institution=uitm,
                                    field_key_id='eng')
    StpmRequirement.objects.create(course=deg, req_bumiputera=True)
    StpmCourse.objects.create(course_id='UM-OLD', course_name='Ijazah Lama', university='Universiti Malaya',
                              field_key_id='eng', is_active=False)
    config = apps.get_app_config('courses')
    monkeypatch.setattr(config, 'course_pathway_map',
                        {'P-ELEK': 'poly', 'P-MEK': 'poly', 'P-BUMI': 'poly', 'K-KOM': 'kkom'}, raising=False)


def _get(**params):
    return APIClient().get(URL, params)


@pytest.mark.django_db
class TestPathwayOfferings:
    def test_each_institution_lists_the_courses_it_offers(self, catalogue):
        resp = _get(pathway='poly')
        assert resp.status_code == 200
        body = resp.json()
        assert body['pathway'] == 'poly'
        insts = {i['id']: i for i in body['institutions']}
        assert set(insts) == {'POLY-PUO', 'POLY-PKB'}
        assert insts['POLY-PUO'] == {'id': 'POLY-PUO', 'institution_id': 'POLY-PUO',
                                     'name': 'Politeknik Ungku Omar', 'state': 'Perak',
                                     'course_ids': ['P-ELEK', 'P-MEK']}
        assert sorted(insts['POLY-PKB']['course_ids']) == ['P-BUMI', 'P-ELEK']
        assert {c['course_id'] for c in body['courses']} == {'P-ELEK', 'P-MEK', 'P-BUMI'}
        elek = next(c for c in body['courses'] if c['course_id'] == 'P-ELEK')
        assert elek == {'course_id': 'P-ELEK', 'course_name': 'Diploma Kejuruteraan Elektrik',
                        'field_key': 'eng', 'aliran': None}

    def test_unfiltered_bumi_only_and_inactive_courses_are_served(self, catalogue):
        ids = {c['course_id'] for c in _get(pathway='poly').json()['courses']}
        assert 'P-BUMI' in ids     # Option A: every course to every student
        assert 'P-MEK' in ids      # inactive: a student may already be enrolled on it

    def test_one_pathway_only(self, catalogue):
        body = _get(pathway='kkom').json()
        assert [c['course_id'] for c in body['courses']] == ['K-KOM']
        assert body['institutions'] == []          # no campus linked in this fixture

    def test_degrees_group_by_the_catalogue_university_inactive_included(self, catalogue):
        body = _get(pathway='degree').json()
        insts = {i['name']: i for i in body['institutions']}
        # The catalogue's own spelling — what the offer-letter comparison reads (`_campus_rows`).
        assert insts['Universiti Teknologi MARA'] == {
            'id': 'UITM', 'institution_id': 'UITM', 'name': 'Universiti Teknologi MARA',
            'state': 'Selangor', 'course_ids': ['UI-LAW']}
        # Not linked to an Institution row: grouped by name, no institution id invented.
        assert insts['Universiti Malaya']['institution_id'] == ''
        assert insts['Universiti Malaya']['course_ids'] == ['UM-OLD']   # inactive, still served
        assert {c['course_id'] for c in body['courses']} == {'UI-LAW', 'UM-OLD'}  # Bumi-only too

    def test_unknown_pathway_is_refused(self, catalogue):
        for bad in ('', 'matric', 'everything'):
            resp = _get(pathway=bad)
            assert resp.status_code == 400
            assert resp.json()['error'] == 'unknown_pathway'

    def test_public_and_cacheable(self, catalogue):
        resp = _get(pathway='poly')            # no token
        assert resp.status_code == 200
        assert 'public' in resp['Cache-Control'] and 'max-age=3600' in resp['Cache-Control']

    def test_a_failed_boot_load_is_retried_before_answering(self, catalogue, monkeypatch):
        # Review 2026-10-30: the boot load failed, so the pathway map is empty; the route asks the
        # app to retry (TD-047's `ensure_data`) instead of answering "no courses" for an hour.
        config = apps.get_app_config('courses')
        monkeypatch.setattr(config, 'course_pathway_map', {}, raising=False)
        retried = []

        def ensure_data():
            retried.append(True)
            config.course_pathway_map = {'P-ELEK': 'poly'}
            return None
        monkeypatch.setattr(config, 'ensure_data', ensure_data)
        body = _get(pathway='poly').json()
        assert retried
        assert [c['course_id'] for c in body['courses']] == ['P-ELEK']

    def test_an_empty_answer_is_never_cached(self, catalogue, monkeypatch):
        config = apps.get_app_config('courses')
        monkeypatch.setattr(config, 'course_pathway_map', {}, raising=False)
        monkeypatch.setattr(config, 'ensure_data', lambda: None)
        resp = _get(pathway='poly')
        assert resp.status_code == 200 and resp.json()['courses'] == []
        assert 'public' not in resp['Cache-Control'] and 'no-store' in resp['Cache-Control']

    def test_pismp_rows_carry_their_school_type(self, catalogue, monkeypatch):
        c = _course('PISMP-SJKT', 'Pendidikan Bahasa Tamil (SJKT)', source_type='pismp')
        monkeypatch.setattr(apps.get_app_config('courses'), 'course_pathway_map', {c.course_id: 'pismp'})
        row = _get(pathway='pismp').json()['courses'][0]
        assert row['aliran'] == 'sjkt'

    def test_every_programme_pathway_the_web_asks_for_is_served(self):
        # The web's PATHWAY_ORDER minus the two pre-U pathways (fixed lists), plus `degree`.
        assert set(OFFERING_PATHWAYS) == {'asasi', 'university', 'poly', 'kkom', 'pismp', 'iljtm',
                                          'ilkbs', 'mara', 'tvet_other', 'degree'}
