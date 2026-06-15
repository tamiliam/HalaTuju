"""Family roster: profile-level home + two-way link with an OPEN application.

The structured roster lives on the StudentProfile (the durable home, edited on
/profile for everyone). While a B40 application is OPEN the two copies stay in
sync (edit either side → both update); once the application is DECIDED its copy
freezes and a /profile edit no longer touches it. Also covers the /profile GET
surfaces (family fields, merit score, Google-identity email verified, pathway).
"""
import jwt
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.courses.models import StudentProfile
from apps.scholarship.models import ScholarshipApplication, ScholarshipCohort, ApplicantDocument
from apps.scholarship.services import save_application_details
from apps.scholarship.family import (
    copy_family_roster, PROFILE_FAMILY_FIELDS, copy_pathway, PROFILE_PATHWAY_FIELDS,
)

_PATHWAY = {
    'pathway_certainty': 'sure', 'chosen_pathway': 'matric', 'pre_u_track': 'sains',
    'pre_u_institution': 'KM Melaka', 'chosen_programme': {}, 'pathways_considered': [],
    'uncertainty_reasons': [], 'uncertainty_note': '',
}

_TEST_JWT_SECRET = 'test-supabase-jwt-secret'


def _token(uid, email=''):
    payload = {'sub': uid, 'aud': 'authenticated', 'role': 'authenticated'}
    if email:
        payload['email'] = email
    return jwt.encode(payload, _TEST_JWT_SECRET, algorithm='HS256')


_ROSTER = {
    'father_name': 'MURUGAN A/L SAMY', 'father_occupation': 'driver',
    'father_occupation_other': '',
    'mother_name': 'KAMALA A/P RAJU', 'mother_occupation': 'homemaker',
    'mother_occupation_other': '',
    'other_family_members': [{'role': 'brother', 'occupation': 'factory'}],
    'siblings_in_school': 2, 'siblings_in_tertiary': 0,
}


class TestCopyRoster(TestCase):
    def test_copy_is_field_for_field(self):
        prof = StudentProfile.objects.create(supabase_user_id='cp1', **_ROSTER)
        app = ScholarshipApplication.objects.create(
            cohort=ScholarshipCohort.objects.create(code='cp', name='B40', year=2026),
            profile=prof, status='submitted')
        copy_family_roster(prof, app)
        for f in PROFILE_FAMILY_FIELDS:
            self.assertEqual(getattr(app, f), getattr(prof, f), f)


class TestStorySaveMirrorsToProfile(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)

    def _app(self, status):
        prof = StudentProfile.objects.create(supabase_user_id=f'{status}-{self.id()}')
        return ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=prof, status=status), prof

    def test_open_app_story_save_mirrors_back_to_profile(self):
        app, prof = self._app('profile_complete')
        save_application_details(app, dict(_ROSTER))
        prof.refresh_from_db()
        self.assertEqual(prof.father_name, 'MURUGAN A/L SAMY')
        self.assertEqual(prof.siblings_in_school, 2)
        self.assertEqual(prof.other_family_members, [{'role': 'brother', 'occupation': 'factory'}])

    def test_decided_app_story_save_does_not_touch_profile(self):
        app, prof = self._app('accepted')          # frozen
        save_application_details(app, dict(_ROSTER))
        prof.refresh_from_db()
        self.assertEqual(prof.father_name, '')     # profile left untouched


@override_settings(SUPABASE_JWT_SECRET=_TEST_JWT_SECRET)
class TestProfilePutMirrorsToOpenApp(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)

    def setUp(self):
        self.client = APIClient()
        self.profile = StudentProfile.objects.create(
            supabase_user_id='put-1', nric='080115-05-0132')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(self.profile.supabase_user_id)}')

    def test_profile_edit_flows_into_open_app(self):
        app = ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=self.profile, status='shortlisted')
        r = self.client.put('/api/v1/profile/', _ROSTER, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        app.refresh_from_db()
        self.assertEqual(app.father_name, 'MURUGAN A/L SAMY')
        self.assertEqual(app.siblings_in_school, 2)

    def test_profile_edit_does_not_touch_decided_app(self):
        app = ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=self.profile, status='rejected',
            father_name='OLD NAME')
        r = self.client.put('/api/v1/profile/', _ROSTER, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        app.refresh_from_db()
        self.assertEqual(app.father_name, 'OLD NAME')   # frozen


@override_settings(SUPABASE_JWT_SECRET=_TEST_JWT_SECRET)
class TestProfileGetSurfaces(TestCase):
    def setUp(self):
        self.client = APIClient()

    def _get(self, profile):
        email = 'arjun@gmail.com'
        self.client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {_token(profile.supabase_user_id, email=email)}')
        return self.client.get('/api/v1/profile/')

    def test_get_returns_family_fields(self):
        prof = StudentProfile.objects.create(supabase_user_id='g1', **_ROSTER)
        r = self._get(prof)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.data['father_name'], 'MURUGAN A/L SAMY')
        self.assertEqual(r.data['siblings_in_school'], 2)

    def test_contact_email_verified_when_it_is_the_google_identity(self):
        # contact_email == the authenticated Google address → verified (no false amber).
        prof = StudentProfile.objects.create(
            supabase_user_id='g2', contact_email='arjun@gmail.com',
            contact_email_verified=False)
        r = self._get(prof)
        self.assertTrue(r.data['contact_email_verified'])

    def test_contact_email_not_verified_when_different(self):
        prof = StudentProfile.objects.create(
            supabase_user_id='g3', contact_email='other@example.com',
            contact_email_verified=False)
        r = self._get(prof)
        self.assertFalse(r.data['contact_email_verified'])

    def test_merit_score_computed_from_grades(self):
        prof = StudentProfile.objects.create(
            supabase_user_id='g4',
            grades={'bm': 'A', 'eng': 'A', 'math': 'A', 'sci': 'B', 'hist': 'B'})
        r = self._get(prof)
        self.assertIsNotNone(r.data['merit_score'])
        self.assertIsInstance(r.data['merit_score'], float)

    def test_merit_score_none_without_grades(self):
        prof = StudentProfile.objects.create(supabase_user_id='g5', grades={})
        r = self._get(prof)
        self.assertIsNone(r.data['merit_score'])


@override_settings(SUPABASE_JWT_SECRET=_TEST_JWT_SECRET)
class TestPathwayProfileLink(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='pw', name='B40', year=2026)

    def setUp(self):
        self.client = APIClient()
        self.profile = StudentProfile.objects.create(supabase_user_id='pw-1', nric='080115-05-0132')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(self.profile.supabase_user_id)}')

    def test_copy_pathway_field_for_field(self):
        prof = StudentProfile.objects.create(supabase_user_id='pw-cp', **_PATHWAY)
        app = ScholarshipApplication.objects.create(cohort=self.cohort, profile=prof, status='submitted')
        copy_pathway(prof, app)
        for f in PROFILE_PATHWAY_FIELDS:
            self.assertEqual(getattr(app, f), getattr(prof, f), f)

    def test_profile_pathway_edit_flows_into_open_app(self):
        app = ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=self.profile, status='shortlisted')
        r = self.client.put('/api/v1/profile/', _PATHWAY, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        app.refresh_from_db()
        self.assertEqual(app.chosen_pathway, 'matric')
        self.assertEqual(app.pre_u_track, 'sains')
        self.assertEqual(app.pre_u_institution, 'KM Melaka')

    def test_profile_pathway_edit_does_not_touch_decided_app(self):
        app = ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=self.profile, status='accepted',
            chosen_pathway='stpm', pre_u_track='sains_sosial')
        r = self.client.put('/api/v1/profile/', _PATHWAY, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        app.refresh_from_db()
        self.assertEqual(app.chosen_pathway, 'stpm')        # frozen
        self.assertEqual(app.pre_u_track, 'sains_sosial')

    def test_get_returns_pathway_fields_from_profile(self):
        prof = StudentProfile.objects.create(supabase_user_id='pw-get', **_PATHWAY)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(prof.supabase_user_id)}')
        r = self.client.get('/api/v1/profile/')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.data['chosen_pathway'], 'matric')
        self.assertEqual(r.data['pathway'], 'matric')        # back-compat alias
        self.assertEqual(r.data['pre_u_track'], 'sains')


@override_settings(SUPABASE_JWT_SECRET=_TEST_JWT_SECRET)
class TestIdentityVerified(TestCase):
    """The Name + IC "Verified" badges on /profile reflect the IC SCAN (name + IC No match
    the uploaded MyKad), not just the admin nric_verified lock."""
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='iv', name='B40', year=2026)

    def _get(self, profile):
        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(profile.supabase_user_id)}')
        return c.get('/api/v1/profile/')

    def _ic(self, prof, vname, vnric):
        app = ScholarshipApplication.objects.create(cohort=self.cohort, profile=prof, status='shortlisted')
        ApplicantDocument.objects.create(application=app, doc_type='ic',
                                         storage_path='ic/x', vision_name=vname, vision_nric=vnric)

    def test_verified_when_ic_scan_matches(self):
        prof = StudentProfile.objects.create(
            supabase_user_id='iv1', name='ELANJELIAN VENUGOPAL', nric='710829-02-5709')
        self._ic(prof, 'ELANJELIAN A/L VENUGOPAL', '710829-02-5709')   # A/L stripped → name match; NRIC match
        self.assertTrue(self._get(prof).data['identity_verified'])

    def test_not_verified_when_nric_differs(self):
        prof = StudentProfile.objects.create(
            supabase_user_id='iv2', name='ELANJELIAN VENUGOPAL', nric='710829-02-5709')
        self._ic(prof, 'ELANJELIAN A/L VENUGOPAL', '999999-99-9999')
        self.assertFalse(self._get(prof).data['identity_verified'])

    def test_not_verified_without_ic_doc(self):
        prof = StudentProfile.objects.create(
            supabase_user_id='iv3', name='ELANJELIAN VENUGOPAL', nric='710829-02-5709')
        self.assertFalse(self._get(prof).data['identity_verified'])

    def test_admin_lock_alone_verifies(self):
        prof = StudentProfile.objects.create(
            supabase_user_id='iv4', name='X', nric='710829-02-5709', nric_verified=True)
        self.assertTrue(self._get(prof).data['identity_verified'])
