from django.test import TestCase
from rest_framework.test import APIRequestFactory
from apps.courses.models import StudentProfile
from apps.courses.views import NricClaimView


class TestNricClaim(TestCase):
    """NRIC claim/reclaim logic."""

    def setUp(self):
        self.factory = APIRequestFactory()

    def _post(self, user_id, data):
        request = self.factory.post('/api/v1/profile/claim-nric/', data, format='json')
        request.user_id = user_id
        request.supabase_user = {'id': user_id, 'email': f'{user_id}@test.com'}
        return NricClaimView.as_view()(request)

    def test_claim_new_nric_creates_profile(self):
        resp = self._post('user-a', {'nric': '040815-01-2022'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['status'], 'created')
        profile = StudentProfile.objects.get(nric='040815-01-2022')
        self.assertEqual(profile.supabase_user_id, 'user-a')

    def test_claim_existing_nric_returns_exists(self):
        StudentProfile.objects.create(
            supabase_user_id='user-a', nric='040815-01-2022', name='Student A'
        )
        resp = self._post('user-b', {'nric': '040815-01-2022'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['status'], 'exists')
        self.assertEqual(resp.data['name'], 'Student A')
        # Profile NOT transferred yet
        profile = StudentProfile.objects.get(nric='040815-01-2022')
        self.assertEqual(profile.supabase_user_id, 'user-a')

    def test_confirm_claim_transfers_profile(self):
        StudentProfile.objects.create(
            supabase_user_id='user-a', nric='040815-01-2022', name='Student A'
        )
        resp = self._post('user-b', {'nric': '040815-01-2022', 'confirm': True})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['status'], 'claimed')
        profile = StudentProfile.objects.get(nric='040815-01-2022')
        self.assertEqual(profile.supabase_user_id, 'user-b')

    def test_claim_own_nric_no_op(self):
        StudentProfile.objects.create(
            supabase_user_id='user-a', nric='040815-01-2022'
        )
        resp = self._post('user-a', {'nric': '040815-01-2022'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['status'], 'linked')

    def test_claim_cleans_up_empty_profile(self):
        StudentProfile.objects.create(supabase_user_id='user-b', nric='')
        StudentProfile.objects.create(
            supabase_user_id='user-a', nric='040815-01-2022', name='Student A'
        )
        resp = self._post('user-b', {'nric': '040815-01-2022', 'confirm': True})
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(
            StudentProfile.objects.filter(supabase_user_id='user-b', nric='').exists()
        )

    def test_invalid_nric_format_rejected(self):
        resp = self._post('user-a', {'nric': '12345'})
        self.assertEqual(resp.status_code, 400)

    def test_missing_nric_rejected(self):
        resp = self._post('user-a', {})
        self.assertEqual(resp.status_code, 400)

    def test_new_nric_updates_existing_empty_profile(self):
        """If caller already has a profile with blank NRIC, update it."""
        StudentProfile.objects.create(supabase_user_id='user-a', nric='', name='Temp')
        resp = self._post('user-a', {'nric': '040815-01-2022'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['status'], 'created')
        profile = StudentProfile.objects.get(supabase_user_id='user-a')
        self.assertEqual(profile.nric, '040815-01-2022')
        self.assertEqual(profile.name, 'Temp')  # Existing data preserved
