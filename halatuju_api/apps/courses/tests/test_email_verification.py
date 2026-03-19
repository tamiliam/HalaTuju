import unittest.mock
import uuid
from datetime import timedelta
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIRequestFactory
from apps.courses.models import StudentProfile, EmailVerification
from apps.courses.views import SendVerificationView, VerifyEmailView


class TestEmailVerificationModel(TestCase):

    def test_create_verification(self):
        profile = StudentProfile.objects.create(
            supabase_user_id='verify-1', nric='040815-01-2022'
        )
        v = EmailVerification.objects.create(
            profile=profile,
            email='test@example.com',
            token=uuid.uuid4(),
            expires_at=timezone.now() + timedelta(hours=24),
        )
        self.assertFalse(v.used)
        self.assertEqual(v.email, 'test@example.com')

    def test_expired_token(self):
        profile = StudentProfile.objects.create(
            supabase_user_id='verify-2', nric='040815-02-2022'
        )
        v = EmailVerification.objects.create(
            profile=profile,
            email='test@example.com',
            token=uuid.uuid4(),
            expires_at=timezone.now() - timedelta(hours=1),
        )
        self.assertTrue(v.is_expired)

    def test_not_expired_token(self):
        profile = StudentProfile.objects.create(
            supabase_user_id='verify-2b', nric='040815-02-2023'
        )
        v = EmailVerification.objects.create(
            profile=profile,
            email='test@example.com',
            token=uuid.uuid4(),
            expires_at=timezone.now() + timedelta(hours=23),
        )
        self.assertFalse(v.is_expired)


class TestSendVerification(TestCase):

    def setUp(self):
        self.factory = APIRequestFactory()
        self.profile = StudentProfile.objects.create(
            supabase_user_id='send-v-1', nric='040815-03-2022'
        )

    def _post(self, data):
        request = self.factory.post('/api/v1/profile/verify-email/send/', data, format='json')
        request.user_id = 'send-v-1'
        request.supabase_user = {'id': 'send-v-1', 'email': 'old@gmail.com'}
        return SendVerificationView.as_view()(request)

    @unittest.mock.patch('django.core.mail.send_mail')
    def test_send_email_in_malay(self, mock_send):
        resp = self._post({'email': 'new@example.com', 'lang': 'ms'})
        self.assertEqual(resp.status_code, 200)
        mock_send.assert_called_once()
        call_kwargs = mock_send.call_args
        self.assertEqual(call_kwargs[1]['subject'], 'HalaTuju — Sahkan e-mel anda')
        self.assertIn('Klik pautan ini', call_kwargs[1]['message'])

    @unittest.mock.patch('django.core.mail.send_mail')
    def test_send_email_in_tamil(self, mock_send):
        resp = self._post({'email': 'new@example.com', 'lang': 'ta'})
        self.assertEqual(resp.status_code, 200)
        mock_send.assert_called_once()
        call_kwargs = mock_send.call_args
        self.assertEqual(
            call_kwargs[1]['subject'],
            'HalaTuju — உங்கள் மின்னஞ்சலை சரிபார்க்கவும்',
        )

    @unittest.mock.patch('django.core.mail.send_mail')
    def test_send_email_defaults_to_english(self, mock_send):
        resp = self._post({'email': 'new@example.com'})
        self.assertEqual(resp.status_code, 200)
        mock_send.assert_called_once()
        call_kwargs = mock_send.call_args
        self.assertEqual(call_kwargs[1]['subject'], 'HalaTuju — Verify your email')

    @unittest.mock.patch('django.core.mail.send_mail')
    def test_send_email_invalid_lang_falls_back_to_english(self, mock_send):
        resp = self._post({'email': 'new@example.com', 'lang': 'xx'})
        self.assertEqual(resp.status_code, 200)
        mock_send.assert_called_once()
        call_kwargs = mock_send.call_args
        self.assertEqual(call_kwargs[1]['subject'], 'HalaTuju — Verify your email')

    def test_send_creates_token(self):
        resp = self._post({'email': 'new@example.com'})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(EmailVerification.objects.filter(
            profile=self.profile, email='new@example.com'
        ).exists())

    def test_send_missing_email_400(self):
        resp = self._post({})
        self.assertEqual(resp.status_code, 400)

    def test_send_invalidates_previous_tokens(self):
        """Sending a new verification invalidates old tokens for same email."""
        self._post({'email': 'new@example.com'})
        self._post({'email': 'new@example.com'})
        active = EmailVerification.objects.filter(
            profile=self.profile, email='new@example.com', used=False
        )
        self.assertEqual(active.count(), 1)

    def test_rate_limit_blocks_after_3_requests(self):
        """Max 3 verification emails per hour per profile."""
        for i in range(3):
            resp = self._post({'email': f'test{i}@example.com'})
            self.assertEqual(resp.status_code, 200)
        resp = self._post({'email': 'test4@example.com'})
        self.assertEqual(resp.status_code, 429)

    def test_rate_limit_resets_after_old_tokens_expire(self):
        """Tokens older than 1 hour don't count towards the limit."""
        old_time = timezone.now() - timedelta(hours=2)
        for i in range(3):
            v = EmailVerification.objects.create(
                profile=self.profile,
                email=f'old{i}@example.com',
                token=uuid.uuid4(),
                expires_at=timezone.now() + timedelta(hours=24),
            )
            # Backdate the created_at
            EmailVerification.objects.filter(pk=v.pk).update(created_at=old_time)
        # Should be allowed since old tokens are > 1 hour ago
        resp = self._post({'email': 'new@example.com'})
        self.assertEqual(resp.status_code, 200)


class TestVerifyEmail(TestCase):

    def setUp(self):
        self.factory = APIRequestFactory()
        self.profile = StudentProfile.objects.create(
            supabase_user_id='verify-e-1', nric='040815-04-2022'
        )
        self.token = uuid.uuid4()
        self.verification = EmailVerification.objects.create(
            profile=self.profile,
            email='verified@example.com',
            token=self.token,
            expires_at=timezone.now() + timedelta(hours=24),
        )

    def _get(self, token):
        request = self.factory.get(f'/api/v1/profile/verify-email/{token}/')
        return VerifyEmailView.as_view()(request, token=str(token))

    def test_valid_token_verifies_email(self):
        resp = self._get(self.token)
        self.assertEqual(resp.status_code, 200)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.contact_email, 'verified@example.com')
        self.assertTrue(self.profile.contact_email_verified)

    def test_expired_token_rejected(self):
        self.verification.expires_at = timezone.now() - timedelta(hours=1)
        self.verification.save()
        resp = self._get(self.token)
        self.assertEqual(resp.status_code, 400)

    def test_used_token_rejected(self):
        self.verification.used = True
        self.verification.save()
        resp = self._get(self.token)
        self.assertEqual(resp.status_code, 400)

    def test_invalid_token_404(self):
        resp = self._get(uuid.uuid4())
        self.assertEqual(resp.status_code, 404)

    def test_token_marked_used_after_verification(self):
        self._get(self.token)
        self.verification.refresh_from_db()
        self.assertTrue(self.verification.used)
