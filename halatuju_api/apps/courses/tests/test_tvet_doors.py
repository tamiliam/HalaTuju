"""⚠ THE TVET PATHWAY DOORS (Bumi coverage Sprint F1). Two new pathways, "mara" (F2's data) and
"tvet_other" (every other public body), derived from the offering institution's category. Every door
that names a pathway must know them: the pathway map, the search filter and pick-list, the sort, the
course page's chip, the scholarship families and the funding estimate. The Bumiputera gate is
source-type independent, so a Bumi-only TVET row (KEMAS) is hidden from a non-Bumi student everywhere.
"""
import json
from io import StringIO
from pathlib import Path

import pytest
from django.apps import apps
from django.core.management import call_command
from rest_framework.test import APIClient

from apps.courses.eligibility_service import compute_stats, sort_eligible_courses
from apps.courses.models import Course, CourseInstitution, CourseRequirement, Institution
from apps.courses.serializers import CourseRequirementSerializer
from apps.courses.tests.conftest import load_requirements_df
from apps.courses.tvet_families import TVET_CATEGORY_PATHWAY, TVET_PATHWAYS
from apps.scholarship.funding_estimate import _classify_programme
from apps.scholarship.offer_pathway import pathway_family
from apps.scholarship.results_route import POST_SPM_CODES

KEMAS = {'TVET-47045', 'TVET-47051'}   # the two Bumi-only F1 rows ("Berbangsa Melayu ...")


def _institution(iid, category, subcategory=''):
    return Institution.objects.create(institution_id=iid, institution_name=iid, type='ILKA', state='Perak',
                                      category=category, subcategory=subcategory)


@pytest.mark.django_db
class TestDoors:
    @pytest.fixture(autouse=True)
    def load(self):
        call_command('loaddata', 'courses', 'requirements', stdout=StringIO(), verbosity=0)
        other, mara = _institution('ILKA-001', 'TVET', 'KEMAS'), _institution('MARA-001', 'MARA', 'MARA')
        CourseInstitution.objects.create(course_id='TVET-47045', institution=other)
        CourseInstitution.objects.create(course_id='TVET-18170', institution=other)
        # A stand-in MARA course (Sprint F2 brings the real ones): one F1 row linked to a MARA campus.
        CourseInstitution.objects.create(course_id='TVET-31450', institution=mara)
        load_requirements_df()
        apps.get_app_config('courses')._load_data()
        self.client = APIClient()

    def test_the_pathway_map_reads_the_institution_category(self):
        pathway = apps.get_app_config('courses').course_pathway_map
        assert pathway['TVET-18170'] == 'tvet_other' and pathway['TVET-31450'] == 'mara'
        assert set(TVET_CATEGORY_PATHWAY.values()) == set(TVET_PATHWAYS)

    def _search(self, **params):
        resp = self.client.get('/api/v1/courses/search/', {'qualification': 'SPM', 'limit': 500, **params})
        assert resp.status_code == 200
        return resp.json()

    def test_the_search_filter_and_pick_list(self):
        rows = self._search(source_type='tvet_other')['courses']
        assert {r['course_id'] for r in rows} == {'TVET-18170'}   # KEMAS is Bumi-only: hidden
        assert all(r['pathway_type'] == 'tvet_other' for r in rows)
        assert {r['course_id'] for r in self._search(source_type='mara')['courses']} == {'TVET-31450'}
        types = self._search()['filters']['source_types']
        assert {'iljtm', 'ilkbs', 'mara', 'tvet_other'} <= set(types)

    def test_a_bumi_only_tvet_row_is_hidden_from_a_non_bumi_search_and_shown_to_a_bumi_one(self):
        assert not KEMAS & {r['course_id'] for r in self._search(q='Jahitan')['courses']}
        shown = {r['course_id'] for r in self._search(q='Jahitan', bumiputera='true')['courses']}
        assert 'TVET-47045' in shown

    def test_the_eligibility_check_keeps_the_bumi_gate_on_tvet_rows(self):
        body = {'grades': {'bm': 'C', 'hist': 'C'}, 'gender': 'male', 'nationality': 'malaysian'}
        plain = {c['course_id'] for c in self.client.post('/api/v1/eligibility/check/', body,
                                                           format='json').json()['eligible_courses']}
        bumi = {c['course_id'] for c in self.client.post('/api/v1/eligibility/check/', {**body, 'bumiputera': True},
                                                          format='json').json()['eligible_courses']}
        assert not plain & KEMAS and KEMAS <= bumi
        assert 'TVET-18170' in plain   # an open public row: every citizen meets it

    def test_the_course_page_names_the_pathway(self):
        data = CourseRequirementSerializer(CourseRequirement.objects.get(course_id='TVET-18170')).data
        assert data['pathway_type'] == 'tvet_other' and data['source_type'] == 'tvet'
        assert data['remarks'].startswith('Umur')
        held = CourseRequirementSerializer(CourseRequirement.objects.get(course_id='UE4344001')).data
        assert held['pathway_type'] == 'university'

    def test_the_course_detail_serves_age_and_health_as_text(self):
        resp = self.client.get('/api/v1/courses/TVET-18170/')
        assert resp.status_code == 200
        req = resp.json()['requirements']
        assert 'Sihat tubuh badan' in req['remarks'] and req['pathway_type'] == 'tvet_other'


class TestSortAndStats:
    def test_every_tvet_pathway_sorts_and_counts_like_iljtm(self):
        courses = [{'course_id': p, 'course_name': 'Sijil X', 'source_type': 'tvet', 'pathway_type': p,
                    'merit_cutoff': None} for p in TVET_PATHWAYS]
        ordered = sort_eligible_courses(courses)
        assert [c['pathway_type'] for c in ordered] == sorted(TVET_PATHWAYS)   # a tie, broken by name
        _, by_pathway = compute_stats(courses)
        assert all(by_pathway[p] == 1 for p in TVET_PATHWAYS)


class TestScholarshipSide:
    def test_the_new_pathways_are_tertiary_post_spm(self):
        for code in ('mara', 'tvet_other'):
            assert pathway_family(code) == 'tertiary' and code in POST_SPM_CODES

    def test_a_tvet_programme_is_never_estimated_as_a_university_diploma(self):
        assert _classify_programme({'course_id': 'TVET-47351', 'course_name': 'Diploma Teknologi Elektronik'}) is None


_F2 = Path(__file__).resolve().parents[3] / 'data' / 'tvet' / 'tvet_new_courses_F2.json'


@pytest.mark.django_db
class TestMaraDoors:
    """Bumi Sprint F2: the REAL MARA rows (`tvet_new_courses_F2.json`) through every door, linked to their
    MARA-NNN campuses as `ingest_tvet_courses --apply` links them. 178 are Bumi-only; the 4 GIATMARA
    campus pages silent on Bumiputera are open. A non-Bumi or foreign student sees no Bumi-only row."""

    @pytest.fixture(autouse=True)
    def load(self):
        call_command('loaddata', 'courses', 'requirements', stdout=StringIO(), verbosity=0)
        self.review = json.loads(_F2.read_text(encoding='utf-8'))
        Institution.objects.bulk_create([Institution(**spec) for spec in self.review['new_institutions'].values()])
        CourseInstitution.objects.bulk_create([
            CourseInstitution(course_id=c['course_id'], institution_id=o['institution_id'], hyperlink=o['hyperlink'])
            for c in self.review['courses'] for o in c['offerings']])
        load_requirements_df()
        apps.get_app_config('courses')._load_data()
        self.client = APIClient()
        self.ids = {c['course_id'] for c in self.review['courses']}
        self.bumi_only = {c['course_id'] for c in self.review['courses'] if c['requirement']['req_bumiputera']}
        self.open = self.ids - self.bumi_only

    def _search(self, **params):
        resp = self.client.get('/api/v1/courses/search/', {'qualification': 'SPM', 'limit': 1000, **params})
        assert resp.status_code == 200
        return resp.json()

    def _eligible(self, **body):
        body = {'grades': {'bm': 'C', 'hist': 'C', 'eng': 'C', 'math': 'C', 'phy': 'C', 'geo': 'C'},
                'gender': 'male', 'nationality': 'malaysian', **body}
        resp = self.client.post('/api/v1/eligibility/check/', body, format='json')
        assert resp.status_code == 200
        return resp.json()

    def test_every_mara_row_is_on_the_mara_pathway(self):
        pathway = apps.get_app_config('courses').course_pathway_map
        assert {pathway[cid] for cid in self.ids} == {'mara'}
        assert len(self.bumi_only) == 178 and len(self.open) == 4

    def test_the_search_filter_hides_bumi_only_rows_from_a_non_bumi_student(self):
        plain = {r['course_id'] for r in self._search(source_type='mara')['courses']}
        assert plain == self.open
        bumi = self._search(source_type='mara', bumiputera='true')
        assert {r['course_id'] for r in bumi['courses']} == self.ids
        assert all(r['pathway_type'] == 'mara' for r in bumi['courses'])
        foreign = {r['course_id'] for r in self._search(source_type='mara', bumiputera='true',
                                                         nationality='non_malaysian')['courses']}
        assert not foreign & self.bumi_only

    def test_the_pick_list_names_mara_when_a_mara_row_is_visible(self):
        assert 'mara' in self._search()['filters']['source_types']
        assert 'mara' in self._search(bumiputera='true')['filters']['source_types']

    def test_the_eligibility_check_and_dashboard_counts(self):
        plain = self._eligible()
        assert not {c['course_id'] for c in plain['eligible_courses']} & self.bumi_only
        bumi = self._eligible(bumiputera=True)
        mine = {c['course_id'] for c in bumi['eligible_courses']} & self.ids
        assert mine & self.bumi_only
        assert bumi['pathway_stats']['mara'] == len(mine)
        assert all(c['pathway_type'] == 'mara' for c in bumi['eligible_courses'] if c['course_id'] in self.ids)
        foreign = self._eligible(bumiputera=True, nationality='non_malaysian')
        assert not {c['course_id'] for c in foreign['eligible_courses']} & self.bumi_only

    def test_the_course_page_names_the_pathway_and_shows_the_text(self):
        cid = next(c['course_id'] for c in self.review['courses'] if 'Program Remedial' in c['requirement']['remarks'])
        data = CourseRequirementSerializer(CourseRequirement.objects.get(course_id=cid)).data
        assert data['pathway_type'] == 'mara' and data['req_bumiputera']
        resp = self.client.get(f'/api/v1/courses/{cid}/')
        assert resp.status_code == 200 and 'Program Remedial Matematik' in resp.json()['requirements']['remarks']
        assert {i['institution_id'] for i in resp.json()['institutions']} <= set(self.review['new_institutions'])

    def test_sort_and_funding_estimate(self):
        bumi = self._eligible(bumiputera=True)['eligible_courses']
        ordered = sort_eligible_courses(bumi)
        assert {c['course_id'] for c in ordered} == {c['course_id'] for c in bumi}
        diploma = next(c for c in self.review['courses'] if c['level'] == 'Diploma')
        assert _classify_programme({'course_id': diploma['course_id'], 'course_name': diploma['course']}) is None
        assert pathway_family('mara') == 'tertiary'
