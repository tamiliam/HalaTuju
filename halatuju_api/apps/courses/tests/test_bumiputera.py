"""Bumi coverage Sprint B (owner ruling 2026-10-28): the Bumiputera answer and the STPM unlock.

Bumiputera-only courses (162 UiTM rows carry `req_bumiputera`) become visible ONLY to a Malaysian
student who said they are Bumiputera. The answer is COURSE-GUIDE ONLY: it must never reach the
scholarship app, sponsor views, reports, the partner/admin student detail or the partner CSV export
(the s44(6) "we do not collect ethnicity" stance, docs/decisions.md). The leak guards at the bottom
of this file are written to FAIL the day somebody adds it to one of those.

Covered here:
  * the one rule (`resolve_bumiputera`): only a real yes from a Malaysian counts;
  * the STPM engine param: True sees UiTM; False / None / foreign+True do not;
  * the STPM eligibility endpoint, `CourseSearchView` and `StpmSearchView` (the same rule);
  * the profile writers: PUT, sync, the GET round trip, and the foreign -> NULL rule on the server;
  * the blind readers: partner detail serializer, partner CSV export, Django admin form.
"""
import csv
from io import StringIO
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.test import RequestFactory, TestCase, override_settings
from rest_framework.test import APIClient

from apps.courses.models import PartnerAdmin, StudentProfile, StpmRequirement
from apps.courses.bumiputera import resolve_bumiputera
from apps.courses.stpm_engine import check_stpm_eligibility
from apps.courses.views import ProfileSyncView, ProfileView

# A student strong enough to clear most STPM requirements, so the Bumi rule is what decides.
STRONG = dict(
    stpm_grades={'PA': 'A', 'MATH_T': 'A', 'PHYSICS': 'A', 'CHEMISTRY': 'A', 'BIOLOGY': 'A',
                 'ECONOMICS': 'A', 'ACCOUNTING': 'A'},
    spm_grades={'bm': 'A+', 'eng': 'A+', 'hist': 'A+', 'math': 'A+', 'addmath': 'A+',
                'sci': 'A+', 'phy': 'A+', 'chem': 'A+', 'bio': 'A+'},
    cgpa=4.0, muet_band=6, gender='Lelaki',
)


def _load_stpm():
    call_command('loaddata', 'stpm_courses', 'stpm_requirements', stdout=StringIO(), verbosity=0)


def _bumi_ids():
    return set(StpmRequirement.objects.filter(req_bumiputera=True, course__is_active=True)
               .values_list('course_id', flat=True))


class TestResolveBumiputera:
    """The ONE rule every reader goes through."""

    @pytest.mark.parametrize('value', [True, 'true', '1', 'yes', 'True', ' on '])
    def test_a_yes_from_a_malaysian_counts(self, value):
        assert resolve_bumiputera(value, 'malaysian') is True
        assert resolve_bumiputera(value, 'Warganegara') is True

    @pytest.mark.parametrize('value', [False, None, '', '0', 'false', 'no', 0, 1, 'maybe'])
    def test_anything_else_is_no(self, value):
        assert resolve_bumiputera(value, 'malaysian') is False

    @pytest.mark.parametrize('nat', ['non_malaysian', 'Bukan Warganegara', '', None])
    def test_a_foreign_student_is_never_bumi(self, nat):
        assert resolve_bumiputera(True, nat) is False


@pytest.mark.django_db
class TestStpmEngineBumiParam:
    @pytest.fixture(autouse=True)
    def load(self):
        _load_stpm()

    def _ids(self, **kw):
        return {r['course_id'] for r in check_stpm_eligibility(**STRONG, **kw)}

    def test_the_fixture_holds_bumi_only_courses(self):
        assert len(_bumi_ids()) > 0

    def test_bumi_true_sees_uitm(self):
        assert self._ids(bumiputera=True) & _bumi_ids()

    @pytest.mark.parametrize('value', [False, None])
    def test_false_or_unanswered_does_not(self, value):
        assert not (self._ids(bumiputera=value) & _bumi_ids())

    def test_default_does_not(self):
        assert not (self._ids() & _bumi_ids())

    def test_foreign_with_true_does_not(self):
        assert not (self._ids(bumiputera=True, nationality='Bukan Warganegara') & _bumi_ids())

    def test_bumi_only_adds_the_bumi_courses(self):
        """A yes changes nothing else: the extra results are exactly Bumi-only courses."""
        extra = self._ids(bumiputera=True) - self._ids(bumiputera=False)
        assert extra and extra <= _bumi_ids()


@pytest.mark.django_db
class TestStpmEligibilityEndpoint:
    url = '/api/v1/stpm/eligibility/check/'

    @pytest.fixture(autouse=True)
    def load(self):
        _load_stpm()
        self.client = APIClient()

    def _ids(self, **extra):
        body = {'stpm_grades': STRONG['stpm_grades'], 'spm_grades': STRONG['spm_grades'],
                'cgpa': 4.0, 'muet_band': 6, 'gender': 'male', 'nationality': 'malaysian', **extra}
        resp = self.client.post(self.url, body, format='json')
        assert resp.status_code == 200
        return {c['course_id'] for c in resp.json()['eligible_courses']}

    def test_bumi_true_unlocks(self):
        assert self._ids(bumiputera=True) & _bumi_ids()

    @pytest.mark.parametrize('extra', [{}, {'bumiputera': False}, {'bumiputera': None}])
    def test_absent_false_or_null_does_not(self, extra):
        assert not (self._ids(**extra) & _bumi_ids())

    def test_foreign_with_true_does_not(self):
        assert not (self._ids(bumiputera=True, nationality='non_malaysian') & _bumi_ids())


@pytest.mark.django_db
class TestBothSearchesHideBumiOnlyCourses:
    """`CourseSearchView` and `StpmSearchView` follow the SAME rule (the second used to show all)."""

    @pytest.fixture(autouse=True)
    def load(self):
        _load_stpm()
        self.client = APIClient()

    def _course_search(self, **params):
        resp = self.client.get('/api/v1/courses/search/', {'qualification': 'STPM', **params})
        assert resp.status_code == 200
        return {c['course_id'] for c in resp.json()['courses']}

    def _stpm_search(self, **params):
        resp = self.client.get('/api/v1/stpm/search/', params)
        assert resp.status_code == 200
        return resp.json()

    @pytest.mark.parametrize('params', [{}, {'bumiputera': '0'}, {'bumiputera': 'false'},
                                        {'bumiputera': '1', 'nationality': 'non_malaysian'}])
    def test_hidden_unless_bumi(self, params):
        assert not (self._course_search(**params) & _bumi_ids())
        data = self._stpm_search(**params)
        assert not ({c['course_id'] for c in data['courses']} & _bumi_ids())
        assert data['total_count'] == len(data['courses'])

    @pytest.mark.parametrize('flag', ['1', 'true'])
    def test_shown_to_a_bumi_student(self, flag):
        assert _bumi_ids() <= self._course_search(bumiputera=flag)
        assert _bumi_ids() <= {c['course_id'] for c in self._stpm_search(bumiputera=flag)['courses']}

    def test_both_views_agree(self):
        for params in ({}, {'bumiputera': '1'}):
            assert self._course_search(**params) == {
                c['course_id'] for c in self._stpm_search(**params)['courses']}

    def test_a_bumi_only_university_is_not_offered_as_a_filter_to_others(self):
        bumi_only_unis = (set(StpmRequirement.objects.filter(req_bumiputera=True)
                              .values_list('course__university', flat=True))
                          - set(StpmRequirement.objects.filter(req_bumiputera=False)
                                .values_list('course__university', flat=True)))
        assert bumi_only_unis, 'fixture: expected at least one Bumi-only university'
        assert not (set(self._stpm_search()['filters']['universities']) & bumi_only_unis)
        assert bumi_only_unis <= set(self._stpm_search(bumiputera='1')['filters']['universities'])

    def test_course_search_pick_lists_follow_the_same_rule(self):
        """`CourseSearchView`'s filters (fields, field keys, levels) offer only what the student's
        search can return — a Bumi-only field is no pick for a non-Bumi student."""
        from apps.courses.models import StpmCourse
        c = StpmCourse.objects.create(course_id='UNI-BUMI-ONLY', course_name='Ijazah Bumi Sahaja',
                                      university='UiTM', stream='arts', field='Bidang Bumi Sahaja',
                                      field_key_id=StpmCourse.objects.first().field_key_id)
        StpmRequirement.objects.create(course=c, req_bumiputera=True)

        def filters(**params):
            resp = self.client.get('/api/v1/courses/search/', params)
            assert resp.status_code == 200
            return resp.json()['filters']

        assert 'Bidang Bumi Sahaja' not in filters()['fields']
        assert 'Bidang Bumi Sahaja' not in filters(bumiputera='1', nationality='non_malaysian')['fields']
        assert 'Bidang Bumi Sahaja' in filters(bumiputera='1')['fields']
        bumi_keys = set(StpmCourse.objects.filter(requirement__req_bumiputera=True)
                        .exclude(field_key__isnull=True).values_list('field_key', flat=True))
        open_keys = set(StpmCourse.objects.filter(requirement__req_bumiputera=False)
                        .exclude(field_key__isnull=True).values_list('field_key', flat=True))
        assert not ((bumi_keys - open_keys) & set(filters()['field_keys']))
        assert (bumi_keys - open_keys) <= set(filters(bumiputera='1')['field_keys'])
        # Only Bumi-only degrees left: the STPM level is no pick for a non-Bumi student.
        StpmCourse.objects.exclude(requirement__req_bumiputera=True).update(is_active=False)
        assert 'Ijazah Sarjana Muda' not in filters()['levels']
        assert 'Ijazah Sarjana Muda' in filters(bumiputera='1')['levels']

    def test_the_detail_page_still_shows_a_bumi_course_by_direct_link(self):
        cid = sorted(_bumi_ids())[0]
        resp = self.client.get(f'/api/v1/stpm/courses/{cid}/')
        assert resp.status_code == 200
        assert resp.json()['requirements']['req_bumiputera'] is True


def _req(method, data=None, user_id='bumi-user'):
    factory = RequestFactory()
    if method == 'GET':
        request = factory.get('/api/v1/profile/')
    elif method == 'PUT':
        request = factory.put('/api/v1/profile/', data=data, content_type='application/json')
    else:
        request = factory.post('/api/v1/profile/sync/', data=data, content_type='application/json')
    request.user_id = user_id
    request.data = data or {}
    return request


@pytest.mark.django_db
class TestProfileWritersAndRoundTrip:
    def _get(self):
        return ProfileView().get(_req('GET')).data

    def test_new_profile_is_unanswered(self):
        StudentProfile.objects.create(supabase_user_id='bumi-user')
        assert self._get()['bumiputera'] is None

    def test_put_round_trip(self):
        StudentProfile.objects.create(supabase_user_id='bumi-user', nationality='malaysian')
        for value in (True, False, None):
            assert ProfileView().put(_req('PUT', {'bumiputera': value})).status_code == 200
            assert self._get()['bumiputera'] is value

    def test_sync_round_trip(self):
        resp = ProfileSyncView().post(_req('POST', {'gender': 'male', 'nationality': 'malaysian',
                                                    'bumiputera': True}))
        assert resp.status_code == 200
        assert self._get()['bumiputera'] is True

    def test_a_sync_without_the_field_keeps_the_stored_answer(self):
        StudentProfile.objects.create(supabase_user_id='bumi-user', nationality='malaysian',
                                      bumiputera=True)
        ProfileSyncView().post(_req('POST', {'gender': 'female'}))
        assert StudentProfile.objects.get(supabase_user_id='bumi-user').bumiputera is True

    def test_foreign_and_true_is_stored_null(self):
        resp = ProfileSyncView().post(_req('POST', {'nationality': 'non_malaysian',
                                                    'bumiputera': True}))
        assert resp.status_code == 200
        assert StudentProfile.objects.get(supabase_user_id='bumi-user').bumiputera is None

    def test_true_sent_to_a_stored_foreign_profile_is_stored_null(self):
        StudentProfile.objects.create(supabase_user_id='bumi-user', nationality='non_malaysian')
        ProfileView().put(_req('PUT', {'bumiputera': True}))
        assert StudentProfile.objects.get(supabase_user_id='bumi-user').bumiputera is None

    @pytest.mark.parametrize('view', ['put', 'sync'])
    def test_switching_to_foreign_wipes_a_stored_yes(self, view):
        StudentProfile.objects.create(supabase_user_id='bumi-user', nationality='malaysian',
                                      bumiputera=True)
        body = {'nationality': 'non_malaysian'}
        if view == 'put':
            ProfileView().put(_req('PUT', body))
        else:
            ProfileSyncView().post(_req('POST', body))
        assert StudentProfile.objects.get(supabase_user_id='bumi-user').bumiputera is None

    def test_a_malaysian_change_of_other_fields_keeps_the_answer(self):
        StudentProfile.objects.create(supabase_user_id='bumi-user', nationality='Warganegara',
                                      bumiputera=False)
        ProfileView().put(_req('PUT', {'nationality': 'malaysian', 'city': 'Ipoh'}))
        assert StudentProfile.objects.get(supabase_user_id='bumi-user').bumiputera is False


# ── LEAK GUARDS: the answer is course-guide only ───────────────────────────────────────────────

SUPER_UID = 'partner-super-admin'


@override_settings(ROOT_URLCONF='halatuju.urls')
class TestPartnerViewsNeverSeeIt(TestCase):
    """The partner/admin student detail and the partner CSV export are blind to the answer."""

    def setUp(self):
        self.client = APIClient()
        self._p1 = patch('halatuju.middleware.supabase_auth.jwt.get_unverified_header',
                         return_value={'alg': 'HS256'})
        self._p2 = patch('halatuju.middleware.supabase_auth.jwt.decode',
                         return_value={'sub': SUPER_UID, 'aud': 'authenticated',
                                       'role': 'authenticated'})
        self._p1.start(); self._p2.start()
        self.addCleanup(self._p1.stop); self.addCleanup(self._p2.stop)
        self.client.credentials(HTTP_AUTHORIZATION='Bearer fake-but-patched')
        PartnerAdmin.objects.create(supabase_user_id=SUPER_UID, email='s@example.com',
                                    name='Super', is_super_admin=True)
        StudentProfile.objects.create(supabase_user_id='student-x', name='TEST STUDENT',
                                      nationality='malaysian', bumiputera=True)

    def test_detail_serializer_does_not_carry_it(self):
        from apps.courses.serializers_admin import (PartnerStudentDetailSerializer,
                                                    PartnerStudentListSerializer)
        assert 'bumiputera' not in PartnerStudentDetailSerializer.Meta.fields
        assert 'bumiputera' not in PartnerStudentListSerializer.Meta.fields
        data = PartnerStudentDetailSerializer(
            StudentProfile.objects.get(supabase_user_id='student-x')).data
        assert 'bumiputera' not in data

    def test_detail_endpoint_does_not_carry_it(self):
        resp = self.client.get('/api/v1/admin/students/student-x/')
        assert resp.status_code == 200
        assert 'bumiputera' not in resp.json()
        assert 'bumi' not in resp.content.decode().lower()

    def test_csv_export_has_no_bumi_column(self):
        with patch('apps.courses.views_admin._fetch_auth_data', return_value={}):
            resp = self.client.get('/api/v1/admin/students/export/')
        assert resp.status_code == 200
        rows = list(csv.reader(StringIO(resp.content.decode())))
        assert not any('bumi' in h.lower() for h in rows[0])
        assert 'bumi' not in resp.content.decode().lower()


def test_django_admin_form_excludes_it():
    from django.contrib import admin as dj_admin
    model_admin = dj_admin.site._registry[StudentProfile]
    assert 'bumiputera' in (model_admin.exclude or [])
