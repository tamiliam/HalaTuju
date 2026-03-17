# Identity, Authentication & Contact Verification — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make NRIC the identity anchor with claim/reclaim, add verified contact email/phone, fix profile completeness bugs.

**Architecture:** NRIC becomes the logical primary key (unique constraint, required). Supabase Auth ID remains the physical PK but is updatable when a new login claims an existing NRIC. Contact email/phone are separate from login credentials, verified via Django-sent email links.

**Tech Stack:** Django 5, Next.js 14, Supabase Auth, Gmail SMTP, PostgreSQL (Supabase)

**Design doc:** `docs/plans/2026-03-17-identity-verification-design.md`

---

### Task 1: Add Contact Fields + NRIC Unique Constraint (Backend Model)

**Files:**
- Modify: `halatuju_api/apps/courses/models.py:419-512`
- Create: `halatuju_api/apps/courses/migrations/XXXX_identity_contact_fields.py` (auto-generated)

**Step 1: Write failing test for new fields**

Add to `halatuju_api/apps/courses/tests/test_profile_fields.py`:

```python
class TestContactFields(TestCase):
    """Contact email/phone fields with verification status."""

    def test_contact_email_default_blank(self):
        profile = StudentProfile.objects.create(supabase_user_id='contact-test-1')
        self.assertEqual(profile.contact_email, '')
        self.assertFalse(profile.contact_email_verified)

    def test_contact_phone_default_blank(self):
        profile = StudentProfile.objects.create(supabase_user_id='contact-test-2')
        self.assertEqual(profile.contact_phone, '')
        self.assertFalse(profile.contact_phone_verified)

    def test_contact_email_can_be_set(self):
        profile = StudentProfile.objects.create(
            supabase_user_id='contact-test-3',
            contact_email='test@example.com',
            contact_email_verified=True,
        )
        profile.refresh_from_db()
        self.assertEqual(profile.contact_email, 'test@example.com')
        self.assertTrue(profile.contact_email_verified)

    def test_contact_phone_can_be_set(self):
        profile = StudentProfile.objects.create(
            supabase_user_id='contact-test-4',
            contact_phone='+60123456789',
            contact_phone_verified=False,
        )
        profile.refresh_from_db()
        self.assertEqual(profile.contact_phone, '+60123456789')
        self.assertFalse(profile.contact_phone_verified)


class TestNricUniqueness(TestCase):
    """NRIC must be unique across profiles."""

    def test_nric_unique_constraint(self):
        StudentProfile.objects.create(
            supabase_user_id='nric-uniq-1', nric='040815-01-2022'
        )
        with self.assertRaises(Exception):  # IntegrityError
            StudentProfile.objects.create(
                supabase_user_id='nric-uniq-2', nric='040815-01-2022'
            )

    def test_blank_nric_not_unique(self):
        """Multiple profiles can have blank NRIC (pre-onboarding)."""
        StudentProfile.objects.create(supabase_user_id='blank-nric-1', nric='')
        StudentProfile.objects.create(supabase_user_id='blank-nric-2', nric='')
        self.assertEqual(
            StudentProfile.objects.filter(nric='').count(), 2
        )
```

**Step 2: Run tests to verify they fail**

Run: `cd halatuju_api && python -m pytest apps/courses/tests/test_profile_fields.py::TestContactFields -v`
Expected: FAIL — fields don't exist yet

Run: `cd halatuju_api && python -m pytest apps/courses/tests/test_profile_fields.py::TestNricUniqueness -v`
Expected: FAIL — no unique constraint

**Step 3: Add fields to StudentProfile model**

In `halatuju_api/apps/courses/models.py`, in the `StudentProfile` class, after the `phone` field (line ~448):

```python
    # Contact details (separate from login credentials)
    contact_email = models.EmailField(blank=True, default='',
                                       help_text="Verified contact email")
    contact_email_verified = models.BooleanField(default=False)
    contact_phone = models.CharField(max_length=20, blank=True, default='',
                                      help_text="Verified contact phone")
    contact_phone_verified = models.BooleanField(default=False)
```

Change the `nric` field to add a unique constraint that allows blank:

```python
    nric = models.CharField(max_length=14, blank=True, default='',
                            help_text="NRIC: XXXXXX-XX-XXXX",
                            unique=True)
```

**Important:** Blank NRICs need special handling. Add a custom `save()` method or use `UniqueConstraint` with a condition:

Replace the simple `unique=True` on nric with a constraint in `Meta`:

```python
    nric = models.CharField(max_length=14, blank=True, default='',
                            help_text="NRIC: XXXXXX-XX-XXXX")
```

And in the `Meta` class:

```python
    class Meta:
        db_table = 'api_student_profiles'
        constraints = [
            models.UniqueConstraint(
                fields=['nric'],
                name='unique_nric_when_set',
                condition=~models.Q(nric=''),
            ),
        ]
```

This allows multiple blank NRICs (pre-onboarding) but enforces uniqueness when set.

**Step 4: Generate and run migration**

Run: `cd halatuju_api && python manage.py makemigrations courses`
Run: `cd halatuju_api && python manage.py migrate`

**Step 5: Migrate existing phone data to contact_phone**

Create a data migration:

Run: `cd halatuju_api && python manage.py makemigrations courses --empty -n migrate_phone_to_contact_phone`

Edit the generated migration:

```python
from django.db import migrations

def migrate_phone_data(apps, schema_editor):
    StudentProfile = apps.get_model('courses', 'StudentProfile')
    for profile in StudentProfile.objects.exclude(phone=''):
        profile.contact_phone = profile.phone
        profile.save(update_fields=['contact_phone'])

class Migration(migrations.Migration):
    dependencies = [
        ('courses', 'XXXX_previous'),  # auto-filled
    ]
    operations = [
        migrations.RunPython(migrate_phone_data, migrations.RunPython.noop),
    ]
```

Run: `cd halatuju_api && python manage.py migrate`

**Step 6: Run tests to verify they pass**

Run: `cd halatuju_api && python -m pytest apps/courses/tests/test_profile_fields.py::TestContactFields -v`
Expected: PASS (all 4 tests)

Run: `cd halatuju_api && python -m pytest apps/courses/tests/test_profile_fields.py::TestNricUniqueness -v`
Expected: PASS (both tests)

**Step 7: Run full test suite to check for regressions**

Run: `cd halatuju_api && python -m pytest apps/courses/tests/ apps/reports/tests/ -v`
Expected: All 615+ tests pass

**Step 8: Commit**

```bash
git add halatuju_api/apps/courses/models.py halatuju_api/apps/courses/migrations/ halatuju_api/apps/courses/tests/test_profile_fields.py
git commit -m "feat: add contact fields + NRIC unique constraint"
```

---

### Task 2: NRIC Claim/Reclaim API Endpoint (Backend)

**Files:**
- Modify: `halatuju_api/apps/courses/views.py:925-987`
- Modify: `halatuju_api/apps/courses/urls.py:52-54`
- Create: `halatuju_api/apps/courses/tests/test_nric_claim.py`

**Step 1: Write failing tests for NRIC claim**

Create `halatuju_api/apps/courses/tests/test_nric_claim.py`:

```python
from django.test import TestCase
from rest_framework.test import APIRequestFactory
from apps.courses.models import StudentProfile
from apps.courses.views import NricClaimView


class TestNricClaim(TestCase):
    """NRIC claim/reclaim logic."""

    def setUp(self):
        self.factory = APIRequestFactory()

    def _post(self, user_id, nric):
        request = self.factory.post('/api/v1/profile/claim-nric/',
                                    {'nric': nric}, format='json')
        request.user_id = user_id
        request.supabase_user = {'id': user_id, 'email': f'{user_id}@test.com'}
        return NricClaimView.as_view()(request)

    def test_claim_new_nric_creates_profile(self):
        """First claim of a new NRIC creates the profile."""
        resp = self._post('user-a', '040815-01-2022')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['status'], 'created')
        profile = StudentProfile.objects.get(nric='040815-01-2022')
        self.assertEqual(profile.supabase_user_id, 'user-a')

    def test_claim_existing_nric_returns_exists(self):
        """Claiming an existing NRIC returns exists status for confirmation."""
        StudentProfile.objects.create(
            supabase_user_id='user-a', nric='040815-01-2022', name='Student A'
        )
        resp = self._post('user-b', '040815-01-2022')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['status'], 'exists')
        self.assertEqual(resp.data['name'], 'Student A')
        # Profile not transferred yet — needs confirmation
        profile = StudentProfile.objects.get(nric='040815-01-2022')
        self.assertEqual(profile.supabase_user_id, 'user-a')

    def test_confirm_claim_transfers_profile(self):
        """Confirming claim updates supabase_user_id."""
        StudentProfile.objects.create(
            supabase_user_id='user-a', nric='040815-01-2022', name='Student A'
        )
        request = self.factory.post('/api/v1/profile/claim-nric/',
                                    {'nric': '040815-01-2022', 'confirm': True},
                                    format='json')
        request.user_id = 'user-b'
        request.supabase_user = {'id': 'user-b', 'email': 'b@test.com'}
        resp = NricClaimView.as_view()(request)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['status'], 'claimed')
        profile = StudentProfile.objects.get(nric='040815-01-2022')
        self.assertEqual(profile.supabase_user_id, 'user-b')

    def test_claim_own_nric_no_op(self):
        """Claiming NRIC you already own returns linked."""
        StudentProfile.objects.create(
            supabase_user_id='user-a', nric='040815-01-2022'
        )
        resp = self._post('user-a', '040815-01-2022')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['status'], 'linked')

    def test_claim_cleans_up_empty_profile(self):
        """When user-b claims an NRIC, their old empty profile is deleted."""
        StudentProfile.objects.create(supabase_user_id='user-b', nric='')
        StudentProfile.objects.create(
            supabase_user_id='user-a', nric='040815-01-2022', name='Student A'
        )
        request = self.factory.post('/api/v1/profile/claim-nric/',
                                    {'nric': '040815-01-2022', 'confirm': True},
                                    format='json')
        request.user_id = 'user-b'
        request.supabase_user = {'id': 'user-b', 'email': 'b@test.com'}
        resp = NricClaimView.as_view()(request)
        self.assertEqual(resp.status_code, 200)
        # Old empty profile cleaned up
        self.assertFalse(
            StudentProfile.objects.filter(supabase_user_id='user-b', nric='').exists()
        )

    def test_invalid_nric_format_rejected(self):
        """Invalid NRIC format returns 400."""
        resp = self._post('user-a', '12345')
        self.assertEqual(resp.status_code, 400)

    def test_missing_nric_rejected(self):
        """Missing NRIC returns 400."""
        request = self.factory.post('/api/v1/profile/claim-nric/', {}, format='json')
        request.user_id = 'user-a'
        request.supabase_user = {'id': 'user-a', 'email': 'a@test.com'}
        resp = NricClaimView.as_view()(request)
        self.assertEqual(resp.status_code, 400)
```

**Step 2: Run tests to verify they fail**

Run: `cd halatuju_api && python -m pytest apps/courses/tests/test_nric_claim.py -v`
Expected: FAIL — NricClaimView doesn't exist

**Step 3: Implement NricClaimView**

In `halatuju_api/apps/courses/views.py`, after `ProfileSyncView` (line ~1024):

```python
class NricClaimView(APIView):
    """
    POST /api/v1/profile/claim-nric/

    Claim or reclaim an NRIC. Three outcomes:
    - NRIC is new → create profile, return status='created'
    - NRIC exists, owned by someone else → return status='exists' (needs confirmation)
    - NRIC exists, confirm=True → transfer profile to caller, return status='claimed'
    - NRIC exists, owned by caller → return status='linked' (no-op)
    """
    permission_classes = [SupabaseIsAuthenticated]

    def post(self, request):
        import re
        nric = request.data.get('nric', '').strip()
        confirm = request.data.get('confirm', False)

        if not nric:
            return Response({'error': 'NRIC is required'}, status=status.HTTP_400_BAD_REQUEST)

        # Basic format check: 6 digits, dash, 2 digits, dash, 4 digits
        if not re.match(r'^\d{6}-\d{2}-\d{4}$', nric):
            return Response({'error': 'Invalid NRIC format'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            existing = StudentProfile.objects.get(nric=nric)
        except StudentProfile.DoesNotExist:
            existing = None

        if existing is None:
            # New NRIC — create or update caller's profile
            profile, created = StudentProfile.objects.get_or_create(
                supabase_user_id=request.user_id
            )
            profile.nric = nric
            profile.save(update_fields=['nric'])
            return Response({'status': 'created'})

        if existing.supabase_user_id == request.user_id:
            # Already own this NRIC
            return Response({'status': 'linked'})

        if not confirm:
            # NRIC belongs to someone else — ask for confirmation
            return Response({
                'status': 'exists',
                'name': existing.name or None,
            })

        # Confirmed — transfer profile ownership
        # Delete caller's empty/temporary profile if it exists
        StudentProfile.objects.filter(
            supabase_user_id=request.user_id, nric=''
        ).delete()

        # Transfer the existing profile to the caller
        existing.supabase_user_id = request.user_id
        existing.save(update_fields=['supabase_user_id'])

        return Response({'status': 'claimed'})
```

**Step 4: Add URL**

In `halatuju_api/apps/courses/urls.py`, after line 54:

```python
    path('profile/claim-nric/', views.NricClaimView.as_view(), name='profile-claim-nric'),
```

**Step 5: Run tests to verify they pass**

Run: `cd halatuju_api && python -m pytest apps/courses/tests/test_nric_claim.py -v`
Expected: All 8 tests pass

**Step 6: Run full test suite**

Run: `cd halatuju_api && python -m pytest apps/courses/tests/ apps/reports/tests/ -v`
Expected: All tests pass

**Step 7: Commit**

```bash
git add halatuju_api/apps/courses/views.py halatuju_api/apps/courses/urls.py halatuju_api/apps/courses/tests/test_nric_claim.py
git commit -m "feat: add NRIC claim/reclaim API endpoint"
```

---

### Task 3: Email Verification Model + API (Backend)

**Files:**
- Create: `halatuju_api/apps/courses/models.py` (add EmailVerification model)
- Modify: `halatuju_api/apps/courses/views.py` (add verification endpoints)
- Modify: `halatuju_api/apps/courses/urls.py` (add routes)
- Create: `halatuju_api/apps/courses/tests/test_email_verification.py`

**Step 1: Write failing tests**

Create `halatuju_api/apps/courses/tests/test_email_verification.py`:

```python
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


class TestSendVerification(TestCase):

    def setUp(self):
        self.factory = APIRequestFactory()
        self.profile = StudentProfile.objects.create(
            supabase_user_id='send-v-1', nric='040815-03-2022'
        )

    def test_send_creates_token(self):
        request = self.factory.post('/api/v1/profile/verify-email/send/',
                                    {'email': 'new@example.com'}, format='json')
        request.user_id = 'send-v-1'
        request.supabase_user = {'id': 'send-v-1', 'email': 'old@gmail.com'}
        resp = SendVerificationView.as_view()(request)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(EmailVerification.objects.filter(
            profile=self.profile, email='new@example.com'
        ).exists())

    def test_send_missing_email_400(self):
        request = self.factory.post('/api/v1/profile/verify-email/send/',
                                    {}, format='json')
        request.user_id = 'send-v-1'
        request.supabase_user = {'id': 'send-v-1', 'email': 'old@gmail.com'}
        resp = SendVerificationView.as_view()(request)
        self.assertEqual(resp.status_code, 400)


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

    def test_valid_token_verifies_email(self):
        request = self.factory.get(f'/api/v1/profile/verify-email/{self.token}/')
        resp = VerifyEmailView.as_view()(request, token=str(self.token))
        self.assertEqual(resp.status_code, 200)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.contact_email, 'verified@example.com')
        self.assertTrue(self.profile.contact_email_verified)

    def test_expired_token_rejected(self):
        self.verification.expires_at = timezone.now() - timedelta(hours=1)
        self.verification.save()
        request = self.factory.get(f'/api/v1/profile/verify-email/{self.token}/')
        resp = VerifyEmailView.as_view()(request, token=str(self.token))
        self.assertEqual(resp.status_code, 400)

    def test_used_token_rejected(self):
        self.verification.used = True
        self.verification.save()
        request = self.factory.get(f'/api/v1/profile/verify-email/{self.token}/')
        resp = VerifyEmailView.as_view()(request, token=str(self.token))
        self.assertEqual(resp.status_code, 400)

    def test_invalid_token_404(self):
        request = self.factory.get(f'/api/v1/profile/verify-email/{uuid.uuid4()}/')
        resp = VerifyEmailView.as_view()(request, token=str(uuid.uuid4()))
        self.assertEqual(resp.status_code, 404)
```

**Step 2: Run tests to verify they fail**

Run: `cd halatuju_api && python -m pytest apps/courses/tests/test_email_verification.py -v`
Expected: FAIL — models and views don't exist

**Step 3: Add EmailVerification model**

In `halatuju_api/apps/courses/models.py`, after `StudentProfile`:

```python
class EmailVerification(models.Model):
    """Token-based email verification for contact email."""
    profile = models.ForeignKey(
        StudentProfile, on_delete=models.CASCADE, related_name='email_verifications'
    )
    email = models.EmailField()
    token = models.UUIDField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used = models.BooleanField(default=False)

    class Meta:
        db_table = 'email_verifications'

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at

    def __str__(self):
        return f"Verify {self.email} for {self.profile_id}"
```

Add `from django.utils import timezone` at the top of models.py if not already present.

**Step 4: Generate and run migration**

Run: `cd halatuju_api && python manage.py makemigrations courses && python manage.py migrate`

**Step 5: Implement SendVerificationView and VerifyEmailView**

In `halatuju_api/apps/courses/views.py`:

```python
class SendVerificationView(APIView):
    """
    POST /api/v1/profile/verify-email/send/

    Generates a verification token and sends an email with a verification link.
    """
    permission_classes = [SupabaseIsAuthenticated]

    def post(self, request):
        import uuid
        from datetime import timedelta
        from django.utils import timezone
        from django.core.mail import send_mail
        from django.conf import settings
        from .models import EmailVerification

        email = request.data.get('email', '').strip()
        if not email:
            return Response({'error': 'Email is required'}, status=status.HTTP_400_BAD_REQUEST)

        profile = StudentProfile.objects.get(supabase_user_id=request.user_id)

        # Invalidate previous tokens for this profile+email
        EmailVerification.objects.filter(profile=profile, email=email, used=False).update(used=True)

        token = uuid.uuid4()
        EmailVerification.objects.create(
            profile=profile,
            email=email,
            token=token,
            expires_at=timezone.now() + timedelta(hours=24),
        )

        # Send verification email
        verify_url = f"{settings.FRONTEND_URL}/verify-email?token={token}"
        try:
            send_mail(
                subject='HalaTuju — Verify your email',
                message=f'Click this link to verify your email: {verify_url}\n\nThis link expires in 24 hours.',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                fail_silently=False,
            )
        except Exception:
            pass  # Log but don't fail — token exists for retry

        return Response({'status': 'sent'})


class VerifyEmailView(APIView):
    """
    GET /api/v1/profile/verify-email/<token>/

    Public endpoint (no auth required) — student clicks link from email.
    """
    permission_classes = []  # Public — accessed from email link

    def get(self, request, token):
        from django.utils import timezone
        from .models import EmailVerification

        try:
            verification = EmailVerification.objects.get(token=token)
        except EmailVerification.DoesNotExist:
            return Response({'error': 'Invalid token'}, status=status.HTTP_404_NOT_FOUND)

        if verification.used:
            return Response({'error': 'Token already used'}, status=status.HTTP_400_BAD_REQUEST)

        if verification.is_expired:
            return Response({'error': 'Token expired'}, status=status.HTTP_400_BAD_REQUEST)

        # Mark token as used and update profile
        verification.used = True
        verification.save(update_fields=['used'])

        profile = verification.profile
        profile.contact_email = verification.email
        profile.contact_email_verified = True
        profile.save(update_fields=['contact_email', 'contact_email_verified'])

        return Response({'status': 'verified', 'email': verification.email})
```

**Step 6: Add URLs**

In `halatuju_api/apps/courses/urls.py`:

```python
    path('profile/verify-email/send/', views.SendVerificationView.as_view(), name='verify-email-send'),
    path('profile/verify-email/<uuid:token>/', views.VerifyEmailView.as_view(), name='verify-email'),
```

**Step 7: Add SMTP settings**

In `halatuju_api/halatuju/settings/base.py` (or production.py), add:

```python
# Email (Gmail SMTP for verification)
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'noreply@halatuju.com')
FRONTEND_URL = os.environ.get('FRONTEND_URL', 'https://halatuju.com')
```

**Step 8: Run tests to verify they pass**

Run: `cd halatuju_api && python -m pytest apps/courses/tests/test_email_verification.py -v`
Expected: All 7 tests pass

**Step 9: Run full test suite**

Run: `cd halatuju_api && python -m pytest apps/courses/tests/ apps/reports/tests/ -v`
Expected: All tests pass

**Step 10: Commit**

```bash
git add halatuju_api/apps/courses/models.py halatuju_api/apps/courses/views.py halatuju_api/apps/courses/urls.py halatuju_api/apps/courses/migrations/ halatuju_api/apps/courses/tests/test_email_verification.py halatuju_api/halatuju/settings/
git commit -m "feat: add email verification model + send/verify API endpoints"
```

---

### Task 4: Update Profile API to Return Contact Fields (Backend)

**Files:**
- Modify: `halatuju_api/apps/courses/views.py:925-987` (ProfileView GET/PUT)
- Modify: `halatuju_api/apps/courses/serializers.py:265-282` (ProfileUpdateSerializer)
- Modify: `halatuju_api/apps/courses/tests/test_profile_fields.py`

**Step 1: Write failing tests**

Add to `halatuju_api/apps/courses/tests/test_profile_fields.py`:

```python
class TestProfileContactAPI(TestCase):
    """Profile API returns and accepts contact fields."""

    def test_get_profile_returns_contact_fields(self):
        profile = StudentProfile.objects.create(
            supabase_user_id='contact-api-1',
            contact_email='test@example.com',
            contact_email_verified=True,
            contact_phone='+60123456789',
            contact_phone_verified=False,
        )
        request = APIRequestFactory().get('/api/v1/profile/')
        request.user_id = 'contact-api-1'
        request.supabase_user = {'id': 'contact-api-1', 'email': 'login@gmail.com'}
        from apps.courses.views import ProfileView
        resp = ProfileView.as_view()(request)
        self.assertEqual(resp.data['contact_email'], 'test@example.com')
        self.assertTrue(resp.data['contact_email_verified'])
        self.assertEqual(resp.data['contact_phone'], '+60123456789')
        self.assertFalse(resp.data['contact_phone_verified'])
        self.assertEqual(resp.data['email'], 'login@gmail.com')

    def test_put_contact_email_resets_verified(self):
        """Editing contact_email resets verification status."""
        profile = StudentProfile.objects.create(
            supabase_user_id='contact-api-2',
            contact_email='old@example.com',
            contact_email_verified=True,
        )
        request = APIRequestFactory().put('/api/v1/profile/',
            {'contact_email': 'new@example.com'}, format='json')
        request.user_id = 'contact-api-2'
        request.supabase_user = {'id': 'contact-api-2', 'email': 'login@gmail.com'}
        from apps.courses.views import ProfileView
        resp = ProfileView.as_view()(request)
        self.assertEqual(resp.status_code, 200)
        profile.refresh_from_db()
        self.assertEqual(profile.contact_email, 'new@example.com')
        self.assertFalse(profile.contact_email_verified)
```

**Step 2: Run tests to verify they fail**

Run: `cd halatuju_api && python -m pytest apps/courses/tests/test_profile_fields.py::TestProfileContactAPI -v`
Expected: FAIL

**Step 3: Update ProfileView GET response**

In `halatuju_api/apps/courses/views.py`, in `ProfileView.get()`, add to the response dict:

```python
            'contact_email': profile.contact_email,
            'contact_email_verified': profile.contact_email_verified,
            'contact_phone': profile.contact_phone,
            'contact_phone_verified': profile.contact_phone_verified,
```

**Step 4: Update ProfileUpdateSerializer**

In `halatuju_api/apps/courses/serializers.py`, add `contact_email`, `contact_phone` to the `fields` list in `ProfileUpdateSerializer.Meta`.

**Step 5: Add verified-reset logic to ProfileView PUT**

In `ProfileView.put()`, after `profile = serializer.save()`, add:

```python
        # Reset verification when contact details change
        if 'contact_email' in serializer.validated_data:
            profile.contact_email_verified = False
            profile.save(update_fields=['contact_email_verified'])
        if 'contact_phone' in serializer.validated_data:
            profile.contact_phone_verified = False
            profile.save(update_fields=['contact_phone_verified'])
```

**Step 6: Run tests**

Run: `cd halatuju_api && python -m pytest apps/courses/tests/test_profile_fields.py -v`
Expected: All pass

**Step 7: Run full suite**

Run: `cd halatuju_api && python -m pytest apps/courses/tests/ apps/reports/tests/ -v`
Expected: All pass

**Step 8: Commit**

```bash
git add halatuju_api/apps/courses/views.py halatuju_api/apps/courses/serializers.py halatuju_api/apps/courses/tests/test_profile_fields.py
git commit -m "feat: profile API returns contact fields, resets verified on edit"
```

---

### Task 5: Update NRIC Gate / Onboarding IC Page (Frontend)

**Files:**
- Modify: `halatuju-web/src/app/onboarding/ic/page.tsx:39-65`
- Modify: `halatuju-web/src/lib/api.ts` (add claimNric function)
- Modify: `halatuju-web/src/app/login/page.tsx:70-88`

**Step 1: Add API function for NRIC claim**

In `halatuju-web/src/lib/api.ts`, add:

```typescript
export async function claimNric(
  nric: string,
  confirm: boolean = false,
  options?: ApiOptions
): Promise<{ status: 'created' | 'exists' | 'claimed' | 'linked'; name?: string }> {
  return apiRequest('/api/v1/profile/claim-nric/', {
    method: 'POST',
    body: JSON.stringify({ nric, confirm }),
    ...options,
  })
}
```

**Step 2: Update IC onboarding page to use claim/reclaim flow**

Replace `handleSubmit` in `halatuju-web/src/app/onboarding/ic/page.tsx`:

```typescript
  const [showConfirm, setShowConfirm] = useState(false)
  const [existingName, setExistingName] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const validationErr = validateIc(ic)
    if (validationErr) {
      setError(validationErr)
      return
    }
    if (!token) {
      setError('Not signed in. Please go back and sign in again.')
      return
    }

    setLoading(true)
    setError(null)

    try {
      const { claimNric } = await import('@/lib/api')
      const result = await claimNric(ic, false, { token })

      if (result.status === 'created' || result.status === 'linked') {
        // New NRIC or already own it — sync name & referral
        const ref = localStorage.getItem(KEY_REFERRAL_SOURCE)
        await syncProfile(
          { ...(name.trim() && { name: name.trim() }), ...(ref && { referral_source: ref }) },
          { token }
        )
        router.replace('/onboarding/exam-type')
      } else if (result.status === 'exists') {
        // Someone else has this NRIC — ask confirmation
        setExistingName(result.name || null)
        setShowConfirm(true)
        setLoading(false)
      }
    } catch {
      setError('Failed to save. Please try again.')
      setLoading(false)
    }
  }

  const handleConfirmClaim = async () => {
    setLoading(true)
    try {
      const { claimNric } = await import('@/lib/api')
      await claimNric(ic, true, { token })
      router.replace('/onboarding/exam-type')
    } catch {
      setError('Failed to claim. Please try again.')
      setLoading(false)
    }
  }

  const handleDenyClaim = () => {
    setShowConfirm(false)
    setExistingName(null)
    setIc('')
  }
```

**Step 3: Add confirmation UI**

In the JSX, add a confirmation dialog when `showConfirm` is true:

```tsx
{showConfirm && (
  <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 mb-4">
    <p className="text-sm text-amber-800 mb-3">
      {t('onboarding.nricExists', {
        name: existingName || t('onboarding.anotherStudent')
      })}
    </p>
    <div className="flex gap-3">
      <button
        onClick={handleConfirmClaim}
        disabled={loading}
        className="px-4 py-2 bg-primary-600 text-white rounded-lg text-sm font-medium"
      >
        {t('onboarding.yesThisIsMe')}
      </button>
      <button
        onClick={handleDenyClaim}
        className="px-4 py-2 bg-white border border-gray-300 rounded-lg text-sm font-medium"
      >
        {t('onboarding.noReenter')}
      </button>
    </div>
  </div>
)}
```

**Step 4: Add translation keys**

Add to all three language files (`en.json`, `bm.json`, `ta.json`) under `onboarding`:

```json
"nricExists": "This IC number is registered to {name}. Is this your account?",
"anotherStudent": "another student",
"yesThisIsMe": "Yes, this is me",
"noReenter": "No, let me re-enter"
```

**Step 5: Build and verify**

Run: `cd halatuju-web && npx next build`
Expected: Build succeeds

**Step 6: Commit**

```bash
git add halatuju-web/src/app/onboarding/ic/page.tsx halatuju-web/src/lib/api.ts halatuju-web/public/locales/
git commit -m "feat: NRIC claim/reclaim flow on onboarding IC page"
```

---

### Task 6: Update Login Routing + Grade Check (Frontend)

**Files:**
- Modify: `halatuju-web/src/app/login/page.tsx:70-88`
- Modify: `halatuju-web/src/lib/auth-context.tsx:105-115`

**Step 1: Update post-login routing in login page**

The routing logic in `handleOtpSubmit` (line 70-88) and the Google login callback both need the same flow. Ensure both paths:

1. Check profile exists (has NRIC)
2. If no NRIC → `/onboarding/ic`
3. If has NRIC → check grades (backend, not just localStorage) → dashboard or `/onboarding/exam-type`

In `halatuju-web/src/app/login/page.tsx`, update the routing block:

```typescript
    if (data.session) {
      try {
        const { getProfile } = await import('@/lib/api')
        const profile = await getProfile({ token: data.session.access_token })
        if (!profile.nric) {
          router.push('/onboarding/ic')
          return
        }
        // Has NRIC — restore profile to localStorage and check grades
        const { restoreProfileToLocalStorage } = await import('@/lib/auth-context')
        await restoreProfileToLocalStorage(data.session.access_token)

        const { KEY_GRADES, KEY_STPM_GRADES } = await import('@/lib/storage')
        const hasGrades = localStorage.getItem(KEY_GRADES) || localStorage.getItem(KEY_STPM_GRADES)
        router.push(hasGrades ? '/dashboard' : '/onboarding/exam-type')
      } catch {
        // No profile — needs IC
        router.push('/onboarding/ic')
      }
    }
```

**Step 2: Update Google login callback**

Find the auth callback page (`/auth/callback/page.tsx` or equivalent). Ensure the same routing logic applies after Google OAuth redirect.

**Step 3: Build and verify**

Run: `cd halatuju-web && npx next build`
Expected: Build succeeds

**Step 4: Commit**

```bash
git add halatuju-web/src/app/login/page.tsx halatuju-web/src/app/auth/
git commit -m "feat: update post-login routing with NRIC + grade checks"
```

---

### Task 7: Profile Page Redesign — Contact Section (Frontend)

**Files:**
- Modify: `halatuju-web/src/app/profile/page.tsx`
- Modify: `halatuju-web/src/lib/api.ts` (add sendVerificationEmail function)
- Modify: `halatuju-web/src/lib/useProfileCompleteness.ts`

**Step 1: Add API function for verification**

In `halatuju-web/src/lib/api.ts`:

```typescript
export async function sendVerificationEmail(
  email: string,
  options?: ApiOptions
): Promise<{ status: string }> {
  return apiRequest('/api/v1/profile/verify-email/send/', {
    method: 'POST',
    body: JSON.stringify({ email }),
    ...options,
  })
}
```

**Step 2: Restructure profile page sections**

Restructure the profile page to have 5 sections:

1. **Personal Details** — IC (locked), Name, Gender, Nationality
2. **Contact Details** (new) — Login method (display), Contact Email (with verify button + badge), Contact Phone (with verify button + badge)
3. **Contact & Location** — State, Address
4. **Family & Background** — Income, Siblings, Colour Blindness, Physical Disability
5. **Application Tracking** — Angka Giliran

Move email and phone from Section 1 to Section 2. Add login method display (read from `session.user.email` or `session.user.phone`). Add "Verify" button next to contact email that calls `sendVerificationEmail`. Show verified/unverified badge.

**Step 3: Update useProfileCompleteness**

In `halatuju-web/src/lib/useProfileCompleteness.ts`, update the fields to check:

```typescript
const COMPLETENESS_FIELDS = [
  'name', 'nric', 'gender', 'preferred_state',
  'contact_email', 'contact_phone',
  'family_income', 'siblings', 'address',
  'angka_giliran',
] as const
```

Update the counting logic to require **at least one verified contact method** instead of both being filled:

```typescript
      // Count standard fields
      for (const field of COMPLETENESS_FIELDS) {
        if (field === 'contact_email' || field === 'contact_phone') continue
        const val = (profile as unknown as Record<string, unknown>)[field]
        if (val === null || val === undefined || val === '') count++
      }
      // At least one verified contact method required
      const hasVerifiedContact =
        profile.contact_email_verified || profile.contact_phone_verified
      if (!hasVerifiedContact) count++
```

**Step 4: Build and verify**

Run: `cd halatuju-web && npx next build`
Expected: Build succeeds

**Step 5: Commit**

```bash
git add halatuju-web/src/app/profile/page.tsx halatuju-web/src/lib/api.ts halatuju-web/src/lib/useProfileCompleteness.ts
git commit -m "feat: profile page contact section with verification"
```

---

### Task 8: Email Verification Landing Page (Frontend)

**Files:**
- Create: `halatuju-web/src/app/verify-email/page.tsx`

**Step 1: Create verification landing page**

When the student clicks the link in their email, they land on `/verify-email?token=<uuid>`. This page:

1. Reads the `token` from the URL
2. Calls `GET /api/v1/profile/verify-email/<token>/`
3. Shows success or error message

```typescript
'use client'

import { useEffect, useState } from 'react'
import { useSearchParams } from 'next/navigation'
import Link from 'next/link'

export default function VerifyEmailPage() {
  const searchParams = useSearchParams()
  const token = searchParams.get('token')
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading')
  const [email, setEmail] = useState('')
  const [errorMsg, setErrorMsg] = useState('')

  useEffect(() => {
    if (!token) {
      setStatus('error')
      setErrorMsg('No verification token provided.')
      return
    }

    const apiUrl = process.env.NEXT_PUBLIC_API_URL || ''
    fetch(`${apiUrl}/api/v1/profile/verify-email/${token}/`)
      .then(res => res.json().then(data => ({ ok: res.ok, data })))
      .then(({ ok, data }) => {
        if (ok) {
          setStatus('success')
          setEmail(data.email)
        } else {
          setStatus('error')
          setErrorMsg(data.error || 'Verification failed.')
        }
      })
      .catch(() => {
        setStatus('error')
        setErrorMsg('Network error. Please try again.')
      })
  }, [token])

  return (
    <main className="min-h-screen bg-[#f8fafc] flex items-center justify-center p-4">
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-8 max-w-md w-full text-center">
        {status === 'loading' && <p className="text-gray-600">Verifying your email...</p>}
        {status === 'success' && (
          <>
            <div className="w-12 h-12 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <svg className="w-6 h-6 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <h1 className="text-lg font-semibold text-gray-900 mb-2">Email Verified</h1>
            <p className="text-sm text-gray-600 mb-4">{email} has been verified.</p>
            <Link href="/profile" className="text-primary-600 text-sm font-medium hover:underline">
              Go to Profile
            </Link>
          </>
        )}
        {status === 'error' && (
          <>
            <div className="w-12 h-12 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <svg className="w-6 h-6 text-red-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </div>
            <h1 className="text-lg font-semibold text-gray-900 mb-2">Verification Failed</h1>
            <p className="text-sm text-gray-600 mb-4">{errorMsg}</p>
            <Link href="/profile" className="text-primary-600 text-sm font-medium hover:underline">
              Go to Profile
            </Link>
          </>
        )}
      </div>
    </main>
  )
}
```

**Step 2: Build and verify**

Run: `cd halatuju-web && npx next build`
Expected: Build succeeds

**Step 3: Commit**

```bash
git add halatuju-web/src/app/verify-email/
git commit -m "feat: email verification landing page"
```

---

### Task 9: Supabase RLS + Migration (Database)

**Files:**
- Migration applied via Supabase MCP

**Step 1: Apply migration to Supabase**

Run the Django migration against Supabase to create the new fields and `email_verifications` table.

**Step 2: Enable RLS on email_verifications table**

```sql
ALTER TABLE email_verifications ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Service role full access on email_verifications"
  ON email_verifications
  FOR ALL
  USING (true)
  WITH CHECK (true);
```

**Step 3: Run Supabase Security Advisor**

Verify 0 errors.

**Step 4: Commit migration files**

```bash
git add halatuju_api/apps/courses/migrations/
git commit -m "chore: Supabase migration for contact fields + email verification"
```

---

### Task 10: Environment Variables + Final Integration Test

**Files:**
- Modify: Cloud Run env vars (halatuju-api)
- Modify: `.env` (local development)

**Step 1: Set up Gmail App Password**

Create a Gmail App Password for `tamiliam@gmail.com` (or a dedicated noreply address). Add to `.env`:

```
EMAIL_HOST_USER=tamiliam@gmail.com
EMAIL_HOST_PASSWORD=<app-password>
DEFAULT_FROM_EMAIL=HalaTuju <tamiliam@gmail.com>
FRONTEND_URL=https://halatuju-web-<hash>-as.a.run.app
```

**Step 2: Add env vars to Cloud Run**

```bash
gcloud run services update halatuju-api \
  --region asia-southeast1 \
  --project gen-lang-client-0871147736 \
  --account tamiliam@gmail.com \
  --update-env-vars "EMAIL_HOST_USER=tamiliam@gmail.com,EMAIL_HOST_PASSWORD=<app-password>,DEFAULT_FROM_EMAIL=HalaTuju <tamiliam@gmail.com>,FRONTEND_URL=https://halatuju-web-<hash>-as.a.run.app"
```

**Step 3: Run full backend test suite**

Run: `cd halatuju_api && python -m pytest apps/courses/tests/ apps/reports/tests/ -v`
Expected: All tests pass (615 + new tests)

**Step 4: Run frontend build**

Run: `cd halatuju-web && npx next build`
Expected: Build succeeds

**Step 5: Commit and push**

```bash
git add -A
git commit -m "feat: identity verification system — NRIC anchor, contact verification, profile redesign"
git push
```

---

## Task Dependency Graph

```
Task 1 (model fields)
  ├→ Task 2 (NRIC claim API)
  │    └→ Task 5 (IC page frontend)
  │         └→ Task 6 (login routing)
  ├→ Task 3 (email verification API)
  │    └→ Task 8 (verify landing page)
  ├→ Task 4 (profile API update)
  │    └→ Task 7 (profile page redesign)
  └→ Task 9 (Supabase RLS)
       └→ Task 10 (env vars + integration)
```

Tasks 2, 3, 4 can run in parallel after Task 1.
Tasks 5, 7, 8 can run in parallel after their dependencies.
Tasks 9 and 10 are final.
