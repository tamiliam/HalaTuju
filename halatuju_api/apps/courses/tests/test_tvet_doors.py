"""⚠ THE TVET PATHWAY DOORS (Bumi coverage Sprint F1). Two new pathways, "mara" (F2's data) and
"tvet_other" (every other public body), derived from the offering institution's category. Every door
that names a pathway must know them: the pathway map, the search filter and pick-list, the sort, the
course page's chip, the scholarship families and the funding estimate. The Bumiputera gate is
source-type independent, so a Bumi-only TVET row (KEMAS) is hidden from a non-Bumi student everywhere.
"""
from io import StringIO

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
