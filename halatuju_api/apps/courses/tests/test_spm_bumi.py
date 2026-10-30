"""⚠ THE SPM BUMIPUTERA DOORS (Bumi coverage Sprint D1). The UiTM rows are `CourseRequirement.
req_bumiputera`; every door that can show an SPM course must follow ONE rule — shown only to a
Malaysian who said yes (`bumiputera.resolve_bumiputera`) — except the course page, which shows the
course to anyone with a "Bumiputera only" badge. The STPM side is `test_bumiputera.py`."""
from io import StringIO

import pytest
from django.core.management import call_command
from rest_framework.test import APIClient

from apps.courses.engine import StudentProfile, check_eligibility
from apps.courses.models import CourseRequirement
from apps.courses.tests.conftest import load_requirements_df

# A student strong enough for most UiTM diplomas, so the Bumi rule is what decides.
STRONG = {'bm': 'A+', 'eng': 'A+', 'hist': 'A+', 'math': 'A+', 'addmath': 'A+', 'phy': 'A+',
          'chem': 'A+', 'bio': 'A+', 'sci': 'A+', 'islam': 'A+', 'geo': 'A'}


def _student(**kw):
    return StudentProfile(grades=STRONG, gender='Lelaki', nationality='Warganegara',
                          colorblind=False, disability=False, **kw)


class TestEngineGate:
    REQ = {'req_bumiputera': 1, 'source_type': 'ua'}

    def test_default_is_not_bumi(self):
        assert _student().bumiputera is False
        ok, audit = check_eligibility(_student(), self.REQ)
        assert not ok and audit[-1] == {'label': 'chk_bumiputera', 'passed': False, 'reason': 'fail_bumiputera'}

    def test_a_real_true_opens_it(self):
        assert check_eligibility(_student(bumiputera=True), self.REQ)[0]

    @pytest.mark.parametrize('value', ['true', 1, None, 'yes'])
    def test_only_a_real_true(self, value):
        assert not check_eligibility(_student(bumiputera=value), self.REQ)[0]

    def test_a_course_without_the_flag_ignores_it(self):
        assert check_eligibility(_student(), {'source_type': 'ua'})[0]


@pytest.mark.django_db
class TestDoors:
    @pytest.fixture(autouse=True)
    def load(self):
        call_command('loaddata', 'courses', 'requirements', stdout=StringIO(), verbosity=0)
        load_requirements_df()
        self.client = APIClient()
        self.bumi_ids = set(CourseRequirement.objects.filter(req_bumiputera=True)
                            .values_list('course_id', flat=True))
        # 84 D1 UiTM + 52 D2 (47 non-UiTM, 3 UiTM D1 flagged, 2 Bumi matric tracks) + 2 F1 (KEMAS)
        # + 177 F2 (MARA UP_TVET; the other 4 MARA rows are GIATMARA pages silent on Bumiputera)
        assert len(self.bumi_ids) == 315, 'fixture: the D1, D2, F1 and F2 Bumi-only rows'

    # --- Door 1: the SPM eligibility check ---
    def _eligible(self, **extra):
        body = {'grades': STRONG, 'gender': 'male', 'nationality': 'malaysian', **extra}
        resp = self.client.post('/api/v1/eligibility/check/', body, format='json')
        assert resp.status_code == 200
        return {c['course_id'] for c in resp.json()['eligible_courses']}

    def test_eligibility_bumi_true_unlocks(self):
        assert self._eligible(bumiputera=True) & self.bumi_ids

    @pytest.mark.parametrize('extra', [{}, {'bumiputera': False}, {'bumiputera': None}])
    def test_eligibility_absent_false_or_null_does_not(self, extra):
        assert not (self._eligible(**extra) & self.bumi_ids)

    def test_eligibility_foreign_with_true_does_not(self):
        assert not (self._eligible(bumiputera=True, nationality='non_malaysian') & self.bumi_ids)

    def test_eligibility_bumi_adds_only_bumi_courses(self):
        assert self._eligible(bumiputera=True) - self._eligible() <= self.bumi_ids

    # --- Door 4: the course search, results AND pick-lists ---
    def _search(self, **params):
        resp = self.client.get('/api/v1/courses/search/', {'qualification': 'SPM', **params})
        assert resp.status_code == 200
        return resp.json()

    @pytest.mark.parametrize('params', [{}, {'bumiputera': '0'},
                                        {'bumiputera': '1', 'nationality': 'non_malaysian'}])
    def test_search_hides_them_unless_bumi(self, params):
        data = self._search(**params)
        assert not ({c['course_id'] for c in data['courses']} & self.bumi_ids)
        assert data['total_count'] == len(data['courses'])

    def test_search_shows_them_to_a_bumi_student(self):
        assert self.bumi_ids <= {c['course_id'] for c in self._search(bumiputera='1')['courses']}

    def test_search_pick_lists_follow_the_same_rule(self):
        from apps.courses.models import Course
        Course.objects.filter(course_id__in=self.bumi_ids).update(field='Bidang Bumi Sahaja')
        assert 'Bidang Bumi Sahaja' not in self._search()['filters']['fields']
        assert 'Bidang Bumi Sahaja' in self._search(bumiputera='1')['filters']['fields']
        Course.objects.exclude(course_id__in=self.bumi_ids).update(level='Sijil')
        assert 'Diploma' not in self._search()['filters']['levels']
        assert 'Diploma' in self._search(bumiputera='1')['filters']['levels']

    # --- Door 5: the course page shows it, with the badge data ---
    def test_the_course_page_still_shows_a_bumi_course(self):
        cid = sorted(self.bumi_ids)[0]
        resp = self.client.get(f'/api/v1/courses/{cid}/')
        assert resp.status_code == 200
        req = resp.json()['requirements']
        assert req['req_bumiputera'] is True
        assert {'key': 'req_bumiputera', 'label': 'Bumiputera sahaja'} in req['general']

    def test_an_open_course_page_says_false(self):
        cid = CourseRequirement.objects.filter(req_bumiputera=False).first().course_id
        assert self.client.get(f'/api/v1/courses/{cid}/').json()['requirements']['req_bumiputera'] is False


class TestReviewProbes:
    """Review round 1 (2026-10-29): the strict "not listed above" reading (owner ruling) and a
    subject counting once per group. Each probe runs the REAL D1 row through the engine."""

    @staticmethod
    def _run(cid, grades):
        import json
        from pathlib import Path
        d1 = Path(__file__).resolve().parents[3] / 'data' / 'spm' / 'spm_new_courses_D1.json'
        rows = {c['course_id']: c for c in json.loads(d1.read_text(encoding='utf-8'))['courses']}
        req = dict(rows[cid]['requirement'], course_id=cid)
        student = StudentProfile(grades, 'Lelaki', 'Warganegara', False, False, bumiputera=True)
        return check_eligibility(student, req)[0]

    def test_one_pertanian_is_not_two_subjects(self):
        base = {'bm': 'C', 'hist': 'E', 'eng': 'C', 'math': 'C', 'islam': 'C', 'moral': 'C'}
        assert not self._run('UE4621001', dict(base, pertanian='E'))
        assert self._run('UE4621001', dict(base, pertanian='E', chem='E'))

    def test_sains_komputer_bm_and_sejarah_cannot_be_the_two_others(self):
        assert not self._run('UE4481001', {'bm': 'C', 'hist': 'C', 'eng': 'C', 'math': 'C', 'phy': 'C'})
        assert self._run('UE4481001', {'bm': 'C', 'hist': 'C', 'eng': 'C', 'math': 'C', 'phy': 'C',
                                       'geo': 'C', 'islam': 'C'})

    def test_aktuari_needs_a_subject_not_named(self):
        g = {'bm': 'C', 'hist': 'E', 'eng': 'C', 'math': 'C', 'addmath': 'C'}
        assert not self._run('UE4462002', g)
        assert self._run('UE4462002', dict(g, geo='C', islam='C'))

    def test_nursing_add_maths_listed_beside_maths_is_not_selain(self):
        g = {'bm': 'C', 'hist': 'E', 'eng': 'C', 'math': 'C', 'addmath': 'C', 'bio': 'C', 'chem': 'C'}
        assert not self._run('UE4723001', g)
        assert self._run('UE4723001', dict(g, geo='C'))

    def test_tesl_bm_cannot_be_one_of_the_three(self):
        g = {'bm': 'A-', 'hist': 'E', 'eng': 'A', 'math': 'C', 'geo': 'A-', 'islam': 'A-', 'moral': 'C', 'ekonomi': 'C'}
        assert not self._run('UE0222001', g)
        assert self._run('UE0222001', dict(g, ekonomi='A-'))
