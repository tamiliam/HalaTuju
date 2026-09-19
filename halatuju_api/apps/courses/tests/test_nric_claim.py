from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIRequestFactory
from apps.courses.models import ProfileLoginAlias, StudentProfile, SavedCourse, Course
from apps.courses.views import NricClaimView


class TestNricClaim(TestCase):
    """NRIC LOOK-UP logic.

    ⚠ This file used to end with four tests of a TRANSFER — `confirm: true` moved the profile's
    primary key in raw SQL. TD-254 removed that door (an account takeover with no challenge and
    no record); those four are replaced below by the behaviour that took its place. The whole
    new flow is tested in `test_profile_claim.py`.
    """

    def setUp(self):
        cache.clear()                    # the claim rate limits count in the cache
        self.factory = APIRequestFactory()

    def _post(self, user_id, data):
        request = self.factory.post('/api/v1/profile/claim-nric/', data, format='json')
        request.user_id = user_id
        request.auth_sub = user_id
        request.supabase_user = {'id': user_id, 'email': f'{user_id}@test.com'}
        return NricClaimView.as_view()(request)

    def test_claim_new_nric_creates_profile(self):
        resp = self._post('user-a', {'nric': '040815-01-2022'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['status'], 'created')
        profile = StudentProfile.objects.get(nric='040815-01-2022')
        self.assertEqual(profile.supabase_user_id, 'user-a')

    def test_claim_existing_nric_returns_exists_and_names_nobody(self):
        StudentProfile.objects.create(
            supabase_user_id='user-a', nric='040815-01-2022', name='Student A'
        )
        resp = self._post('user-b', {'nric': '040815-01-2022'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['status'], 'exists')
        # ⚠ TD-254: the holder's NAME used to be returned right here. That is a disclosure to
        # anyone who can type an IC, so the answer is now the challenge CHANNELS and nothing
        # else — and this profile has no verified contact, so there are none.
        self.assertEqual(sorted(resp.data.keys()), ['channels', 'status'])
        self.assertEqual(resp.data['channels'], [])
        profile = StudentProfile.objects.get(nric='040815-01-2022')
        self.assertEqual(profile.supabase_user_id, 'user-a')

    def test_confirm_transfers_nothing_any_more(self):
        StudentProfile.objects.create(
            supabase_user_id='user-a', nric='040815-01-2022', name='Student A'
        )
        resp = self._post('user-b', {'nric': '040815-01-2022', 'confirm': True})
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.data['code'], 'confirm_removed')
        profile = StudentProfile.objects.get(nric='040815-01-2022')
        self.assertEqual(profile.supabase_user_id, 'user-a')
        self.assertFalse(ProfileLoginAlias.objects.exists())

    def test_claim_own_nric_no_op(self):
        StudentProfile.objects.create(
            supabase_user_id='user-a', nric='040815-01-2022'
        )
        resp = self._post('user-a', {'nric': '040815-01-2022'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['status'], 'linked')

    def test_the_caller_own_empty_profile_is_never_deleted(self):
        """⚠ The old confirm path DELETED it before moving the other record over. A claim now
        deletes nothing at all, which is what makes revoking an alias a complete undo."""
        StudentProfile.objects.create(supabase_user_id='user-b', nric='')
        StudentProfile.objects.create(
            supabase_user_id='user-a', nric='040815-01-2022', name='Student A'
        )
        self._post('user-b', {'nric': '040815-01-2022', 'confirm': True})
        self.assertTrue(
            StudentProfile.objects.filter(supabase_user_id='user-b', nric='').exists()
        )

    def test_invalid_nric_format_rejected(self):
        resp = self._post('user-a', {'nric': '12345'})
        self.assertEqual(resp.status_code, 400)

    def test_invalid_nric_date_month_rejected(self):
        resp = self._post('user-a', {'nric': '041315-01-2022'})  # month 13
        self.assertEqual(resp.status_code, 400)

    def test_invalid_nric_date_day_rejected(self):
        resp = self._post('user-a', {'nric': '040800-01-2022'})  # day 00
        self.assertEqual(resp.status_code, 400)

    def test_invalid_nric_date_zeros_rejected(self):
        resp = self._post('user-a', {'nric': '040015-01-2022'})  # month 00
        self.assertEqual(resp.status_code, 400)

    def test_invalid_nric_age_too_old_rejected(self):
        resp = self._post('user-a', {'nric': '800815-01-2022'})  # born 1980, age 46
        self.assertEqual(resp.status_code, 400)

    def test_invalid_nric_age_too_young_rejected(self):
        resp = self._post('user-a', {'nric': '150815-01-2022'})  # born 2015, age 11
        self.assertEqual(resp.status_code, 400)

    def test_invalid_state_code_rejected(self):
        resp = self._post('user-a', {'nric': '040815-99-2022'})  # invalid state 99
        self.assertEqual(resp.status_code, 400)

    def test_valid_foreign_born_state_code_accepted(self):
        resp = self._post('user-a', {'nric': '040815-71-2022'})  # foreign born, valid
        self.assertEqual(resp.status_code, 200)

    def test_missing_nric_rejected(self):
        resp = self._post('user-a', {})
        self.assertEqual(resp.status_code, 400)

    def test_a_refused_confirm_leaves_every_child_row_where_it_was(self):
        """The old path re-parented saved courses, outcomes, reports and email verifications by
        hand — and silently left the scholarship application behind, which is why it could not
        have worked for a real applicant. Nothing is re-parented now."""
        profile = StudentProfile.objects.create(
            supabase_user_id='user-a', nric='040815-01-2022', name='Student A'
        )
        course = Course.objects.first()  # Use any existing course from fixtures
        if course:
            saved = SavedCourse.objects.create(student=profile, course=course)
            self._post('user-b', {'nric': '040815-01-2022', 'confirm': True})
            saved.refresh_from_db()
            self.assertEqual(saved.student_id, 'user-a')

    def test_new_nric_updates_existing_empty_profile(self):
        """If caller already has a profile with blank NRIC, update it."""
        StudentProfile.objects.create(supabase_user_id='user-a', nric='', name='Temp')
        resp = self._post('user-a', {'nric': '040815-01-2022'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['status'], 'created')
        profile = StudentProfile.objects.get(supabase_user_id='user-a')
        self.assertEqual(profile.nric, '040815-01-2022')
        self.assertEqual(profile.name, 'TEMP')  # Existing data preserved (CAPS-normalised on save)
