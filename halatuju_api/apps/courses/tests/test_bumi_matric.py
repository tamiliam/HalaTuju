"""⚠ THE TWO BUMIPUTERA-ONLY MATRICULATION TRACKS (Bumi coverage Sprint D2, owner ruling 2026-10-29).

KA0000002 (Sains, 4 semesters) and KA0000006 (Perakaunan Profesional) are held the way the four open
tracks are — a synthetic `matric-<track>` catalogue row (source and merit type 'matric') plus a
`pathways.MATRIC_TRACKS` entry and the course -> track map in `eligibility_service` — with
`req_bumiputera`, so every door that lists catalogue rows hides them from a non-Bumi student. The
one door that lists TRACKS rather than rows, /calculate/pathways/, never reads the answer, so it
never lists them."""
from io import StringIO

import pytest
from django.core.management import call_command
from rest_framework.test import APIClient

from apps.courses.eligibility_service import _MATRIC_TRACK_MAP
from apps.courses.models import Course, CourseRequirement
from apps.courses.pathways import MATRIC_REQUIREMENTS, MATRIC_TRACKS, check_all_pathways, check_matric_track
from apps.courses.spm_catalogue_rows import BUMI_MATRIC_TRACKS
from apps.courses.tests.conftest import load_requirements_df

BUMI_TRACKS = {'matric-sains-4-semester': 'sains_4_semester',
               'matric-perakaunan-profesional': 'perakaunan_profesional'}
# Meets both Bumi tracks' MOHE rules (A- English, A Maths, A in three of the list, ...).
STRONG = {'bm': 'A', 'eng': 'A', 'hist': 'A', 'math': 'A', 'addmath': 'A', 'phy': 'A', 'chem': 'A',
          'bio': 'A', 'geo': 'A', 'ekonomi': 'A', 'poa': 'A'}


class TestTheTracks:
    def test_the_maps_agree(self):
        ids = {t['id'] for t in MATRIC_TRACKS}
        assert set(_MATRIC_TRACK_MAP.values()) == ids == set(MATRIC_REQUIREMENTS)
        assert {t['id'] for t in MATRIC_TRACKS if t.get('bumiputera_only')} == set(BUMI_TRACKS.values())
        assert {v['course_id'] for v in BUMI_MATRIC_TRACKS.values()} == set(BUMI_TRACKS)
        for course_id, track in BUMI_TRACKS.items():
            assert _MATRIC_TRACK_MAP[course_id] == track

    def test_the_pathways_door_never_lists_them(self):
        results = check_all_pathways(STRONG, 8)
        assert len(results) == 6
        assert not {r['track_id'] for r in results} & set(BUMI_TRACKS.values())

    def test_their_merit(self):
        for track in BUMI_TRACKS.values():
            result = check_matric_track(track, STRONG, 8)
            assert result['eligible'] and result['merit'] == 94.4   # 4 x A (24) / 100 x 90 + 8
        assert not check_matric_track('perakaunan_profesional', dict(STRONG, math='B'), 8)['eligible']


@pytest.mark.django_db
class TestTheDoors:
    @pytest.fixture(autouse=True)
    def load(self):
        call_command('loaddata', 'courses', 'requirements', stdout=StringIO(), verbosity=0)
        load_requirements_df()
        self.client = APIClient()

    def test_the_rows_are_bumi_only_matric_rows(self):
        for course_id in BUMI_TRACKS:
            req = CourseRequirement.objects.get(course_id=course_id)
            assert req.req_bumiputera and req.source_type == req.merit_type == 'matric'
            assert Course.objects.get(course_id=course_id).level == 'Pra-U'

    def _eligible(self, **extra):
        body = {'grades': STRONG, 'gender': 'female', 'nationality': 'malaysian', 'coq_score': 8, **extra}
        resp = self.client.post('/api/v1/eligibility/check/', body, format='json')
        assert resp.status_code == 200
        return {c['course_id']: c for c in resp.json()['eligible_courses']}

    @pytest.mark.parametrize('extra', [{}, {'bumiputera': False}, {'bumiputera': None},
                                       {'bumiputera': True, 'nationality': 'non_malaysian'}])
    def test_eligibility_hides_them_from_a_non_bumi_student(self, extra):
        courses = self._eligible(**extra)
        assert not set(BUMI_TRACKS) & set(courses)
        assert 'matric-sains' in courses or extra.get('nationality')   # the open tracks still show

    def test_eligibility_shows_them_to_a_bumi_student_with_a_merit(self):
        courses = self._eligible(bumiputera=True)
        for course_id in BUMI_TRACKS:
            assert course_id in courses
            assert courses[course_id]['merit_label'] is not None

    @pytest.mark.parametrize('params, shown', [({}, False), ({'bumiputera': '1'}, True),
                                               ({'bumiputera': '1', 'nationality': 'Bukan Warganegara'}, False)])
    def test_search(self, params, shown):
        resp = self.client.get('/api/v1/courses/search/', {'q': 'Matrikulasi', 'limit': 100, **params})
        assert resp.status_code == 200
        ids = {c['course_id'] for c in resp.json()['courses']}
        assert 'matric-sains' in ids
        assert (set(BUMI_TRACKS) <= ids) is shown and (not set(BUMI_TRACKS) & ids) is (not shown)

    def test_the_pathways_endpoint(self):
        resp = self.client.post('/api/v1/calculate/pathways/', {'grades': STRONG, 'coq_score': 8,
                                                                 'bumiputera': True}, format='json')
        assert resp.status_code == 200
        assert not {p['track_id'] for p in resp.json()['pathways']} & set(BUMI_TRACKS.values())
