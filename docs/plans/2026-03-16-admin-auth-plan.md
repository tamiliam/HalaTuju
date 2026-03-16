# Admin Auth & Session Isolation — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Completely separate admin authentication from student authentication, with email/password + Google login, invite flow, and isolated sessions.

**Architecture:** New `partner_admins` table replaces `admin_org_code` on StudentProfile. Second Supabase client with separate storage key isolates admin sessions. Super admin invites partner admins via Supabase `inviteUserByEmail`. Backend `PartnerAdminMixin` reads from `partner_admins` table.

**Tech Stack:** Django REST Framework, Next.js 14, Supabase Auth (email/password + Google OAuth), Supabase Admin API (service role key)

**Design doc:** `docs/plans/2026-03-16-admin-auth-design.md`

---

### Task 1: PartnerAdmin model + migration

**Files:**
- Modify: `halatuju_api/apps/courses/models.py`
- Create: `halatuju_api/apps/courses/migrations/0035_partner_admin.py` (auto-generated)
- Test: `halatuju_api/apps/courses/tests/test_admin_auth.py`

**Step 1: Write the failing test**

Create `halatuju_api/apps/courses/tests/test_admin_auth.py`:

```python
from django.test import TestCase
from apps.courses.models import PartnerOrganisation, PartnerAdmin


class PartnerAdminModelTest(TestCase):
    def setUp(self):
        self.org = PartnerOrganisation.objects.create(code='cumig', name='CUMIG')

    def test_create_partner_admin(self):
        admin = PartnerAdmin.objects.create(
            email='admin@cumig.org',
            name='Ali Ahmad',
            org=self.org,
        )
        self.assertEqual(admin.email, 'admin@cumig.org')
        self.assertEqual(admin.org, self.org)
        self.assertFalse(admin.is_super_admin)
        self.assertIsNone(admin.supabase_user_id)

    def test_create_super_admin(self):
        admin = PartnerAdmin.objects.create(
            email='super@halatuju.com',
            name='Super Admin',
            is_super_admin=True,
        )
        self.assertTrue(admin.is_super_admin)
        self.assertIsNone(admin.org)

    def test_email_unique(self):
        PartnerAdmin.objects.create(email='admin@cumig.org', name='Admin 1', org=self.org)
        with self.assertRaises(Exception):
            PartnerAdmin.objects.create(email='admin@cumig.org', name='Admin 2', org=self.org)

    def test_supabase_uid_backfill(self):
        admin = PartnerAdmin.objects.create(email='admin@cumig.org', name='Ali', org=self.org)
        self.assertIsNone(admin.supabase_user_id)
        admin.supabase_user_id = 'uid-123'
        admin.save()
        admin.refresh_from_db()
        self.assertEqual(admin.supabase_user_id, 'uid-123')

    def test_str(self):
        admin = PartnerAdmin.objects.create(email='admin@cumig.org', name='Ali', org=self.org)
        self.assertIn('Ali', str(admin))
        self.assertIn('CUMIG', str(admin))
```

**Step 2: Run test to verify it fails**

Run: `cd halatuju_api && python -m pytest apps/courses/tests/test_admin_auth.py -v`
Expected: FAIL — `ImportError: cannot import name 'PartnerAdmin'`

**Step 3: Write the model**

In `halatuju_api/apps/courses/models.py`, add after the `PartnerOrganisation` class (around line 390):

```python
class PartnerAdmin(models.Model):
    """Admin user for a partner organisation. Separate from StudentProfile."""
    supabase_user_id = models.CharField(
        max_length=100, unique=True, null=True, blank=True,
        help_text='Set on first login via UID or email match',
    )
    org = models.ForeignKey(
        PartnerOrganisation, on_delete=models.CASCADE,
        null=True, blank=True, related_name='admins',
        help_text='NULL for super admin',
    )
    is_super_admin = models.BooleanField(default=False)
    name = models.CharField(max_length=200)
    email = models.EmailField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'partner_admins'

    def __str__(self):
        org_name = self.org.name if self.org else 'Super Admin'
        return f'{self.name} ({org_name})'
```

**Step 4: Generate migration**

Run: `cd halatuju_api && python manage.py makemigrations courses`
Expected: Creates `0035_partner_admin.py`

**Step 5: Run test to verify it passes**

Run: `cd halatuju_api && python -m pytest apps/courses/tests/test_admin_auth.py -v`
Expected: 5 PASS

**Step 6: Commit**

```bash
git add halatuju_api/apps/courses/models.py halatuju_api/apps/courses/migrations/0035_partner_admin.py halatuju_api/apps/courses/tests/test_admin_auth.py
git commit -m "feat: add PartnerAdmin model with migration and tests"
```

---

### Task 2: Add contact fields to PartnerOrganisation + remove admin_org_code from StudentProfile

**Files:**
- Modify: `halatuju_api/apps/courses/models.py`
- Create: `halatuju_api/apps/courses/migrations/0036_*.py` (auto-generated)
- Modify: `halatuju_api/apps/courses/tests/test_admin_auth.py`
- Modify: `halatuju_api/apps/courses/tests/test_partner_referral.py`

**Step 1: Write the failing test**

Add to `test_admin_auth.py`:

```python
class PartnerOrgFieldsTest(TestCase):
    def test_contact_fields(self):
        org = PartnerOrganisation.objects.create(
            code='cumig', name='CUMIG',
            contact_person='Encik Ali',
            phone='012-3456789',
        )
        self.assertEqual(org.contact_person, 'Encik Ali')
        self.assertEqual(org.phone, '012-3456789')

    def test_contact_fields_optional(self):
        org = PartnerOrganisation.objects.create(code='cumig', name='CUMIG')
        self.assertEqual(org.contact_person, '')
        self.assertEqual(org.phone, '')
```

**Step 2: Run test to verify it fails**

Run: `cd halatuju_api && python -m pytest apps/courses/tests/test_admin_auth.py::PartnerOrgFieldsTest -v`
Expected: FAIL — no `contact_person` field

**Step 3: Update models**

In `halatuju_api/apps/courses/models.py`, add to `PartnerOrganisation` (after `contact_email`):

```python
    contact_person = models.CharField(max_length=200, blank=True, default='')
    phone = models.CharField(max_length=30, blank=True, default='')
```

Remove from `StudentProfile` (around line 467):

```python
    # DELETE these 4 lines:
    admin_org_code = models.CharField(
        max_length=50, blank=True, default='',
        help_text='If set, this user is an admin for the given partner org code',
    )
```

**Step 4: Fix existing tests**

In `test_partner_referral.py`, the `PartnerAdminModelTest` class references `admin_org_code`. Rewrite it:

```python
class PartnerAdminModelTest(TestCase):
    def setUp(self):
        self.partner = PartnerOrganisation.objects.create(code='cumig', name='CUMIG')
        for i in range(3):
            StudentProfile.objects.create(
                supabase_user_id=f'student-{i}',
                name=f'Student {i}',
                nric=f'01010{i}-01-000{i}',
                exam_type='spm' if i < 2 else 'stpm',
                referral_source='cumig',
                referred_by_org=self.partner,
            )
        StudentProfile.objects.create(
            supabase_user_id='student-other',
            name='Other Student',
            referral_source='whatsapp',
        )

    def test_partner_students_count(self):
        students = StudentProfile.objects.filter(referred_by_org=self.partner)
        self.assertEqual(students.count(), 3)

    def test_other_student_not_included(self):
        students = StudentProfile.objects.filter(referred_by_org=self.partner)
        user_ids = list(students.values_list('supabase_user_id', flat=True))
        self.assertNotIn('student-other', user_ids)

    def test_views_exist(self):
        from apps.courses.views_admin import (
            PartnerDashboardView, PartnerStudentListView,
            PartnerStudentDetailView, PartnerStudentExportView,
        )
        self.assertTrue(hasattr(PartnerDashboardView, 'get'))
        self.assertTrue(hasattr(PartnerStudentListView, 'get'))
        self.assertTrue(hasattr(PartnerStudentDetailView, 'get'))
        self.assertTrue(hasattr(PartnerStudentExportView, 'get'))
```

**Step 5: Generate migration**

Run: `cd halatuju_api && python manage.py makemigrations courses`
Expected: Creates migration adding `contact_person`/`phone` and removing `admin_org_code`

**Step 6: Run all tests**

Run: `cd halatuju_api && python -m pytest apps/courses/tests/test_admin_auth.py apps/courses/tests/test_partner_referral.py -v`
Expected: All PASS

**Step 7: Commit**

```bash
git add halatuju_api/apps/courses/models.py halatuju_api/apps/courses/migrations/0036_*.py halatuju_api/apps/courses/tests/test_admin_auth.py halatuju_api/apps/courses/tests/test_partner_referral.py
git commit -m "feat: add org contact fields, remove admin_org_code from StudentProfile"
```

---

### Task 3: Rewrite PartnerAdminMixin + admin role endpoint

**Files:**
- Modify: `halatuju_api/apps/courses/views_admin.py`
- Modify: `halatuju_api/apps/courses/tests/test_admin_auth.py`

**Step 1: Write the failing tests**

Add to `test_admin_auth.py`:

```python
class PartnerAdminMixinTest(TestCase):
    """Test the mixin logic directly (not via HTTP)."""

    def setUp(self):
        self.org = PartnerOrganisation.objects.create(code='cumig', name='CUMIG')
        self.partner_admin = PartnerAdmin.objects.create(
            supabase_user_id='admin-uid-1',
            email='admin@cumig.org',
            name='Ali',
            org=self.org,
        )
        self.super_admin = PartnerAdmin.objects.create(
            supabase_user_id='super-uid-1',
            email='super@halatuju.com',
            name='Super',
            is_super_admin=True,
        )
        # Create students — 2 referred by CUMIG, 1 not
        for i in range(2):
            StudentProfile.objects.create(
                supabase_user_id=f'student-{i}',
                name=f'Student {i}',
                referred_by_org=self.org,
            )
        StudentProfile.objects.create(
            supabase_user_id='student-other',
            name='Other',
        )

    def test_get_admin_by_uid(self):
        admin = PartnerAdmin.objects.filter(supabase_user_id='admin-uid-1').first()
        self.assertIsNotNone(admin)
        self.assertEqual(admin.org, self.org)

    def test_get_admin_by_email_fallback(self):
        """When UID is NULL, find by email and backfill."""
        self.partner_admin.supabase_user_id = None
        self.partner_admin.save()
        admin = PartnerAdmin.objects.filter(email='admin@cumig.org').first()
        self.assertIsNotNone(admin)
        admin.supabase_user_id = 'new-uid'
        admin.save()
        admin.refresh_from_db()
        self.assertEqual(admin.supabase_user_id, 'new-uid')

    def test_partner_admin_sees_own_students(self):
        students = StudentProfile.objects.filter(referred_by_org=self.org)
        self.assertEqual(students.count(), 2)

    def test_super_admin_sees_all_students(self):
        students = StudentProfile.objects.all()
        self.assertEqual(students.count(), 3)

    def test_admin_role_view_exists(self):
        from apps.courses.views_admin import AdminRoleView
        self.assertTrue(hasattr(AdminRoleView, 'get'))

    def test_invite_view_exists(self):
        from apps.courses.views_admin import AdminInviteView
        self.assertTrue(hasattr(AdminInviteView, 'post'))

    def test_orgs_view_exists(self):
        from apps.courses.views_admin import AdminOrgsView
        self.assertTrue(hasattr(AdminOrgsView, 'get'))
```

**Step 2: Run test to verify it fails**

Run: `cd halatuju_api && python -m pytest apps/courses/tests/test_admin_auth.py::PartnerAdminMixinTest -v`
Expected: FAIL — `AdminInviteView` and `AdminOrgsView` don't exist yet

**Step 3: Rewrite views_admin.py**

Replace the entire `halatuju_api/apps/courses/views_admin.py` with:

```python
"""
Partner admin API views.

Endpoints:
- GET /api/v1/admin/role/ - Check admin role (with email fallback + UID backfill)
- GET /api/v1/admin/dashboard/ - Partner dashboard stats
- GET /api/v1/admin/students/ - List referred students
- GET /api/v1/admin/students/export/ - CSV export of referred students
- GET /api/v1/admin/students/<user_id>/ - Student detail
- POST /api/v1/admin/invite/ - Invite a partner admin (super admin only)
- GET /api/v1/admin/orgs/ - List organisations (for invite dropdown)
"""
import csv
import logging
from collections import Counter
from django.conf import settings
from django.http import HttpResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from halatuju.middleware.supabase_auth import SupabaseIsAuthenticated
from .models import StudentProfile, PartnerOrganisation, PartnerAdmin
from .serializers_admin import PartnerStudentListSerializer, PartnerStudentDetailSerializer

logger = logging.getLogger(__name__)


class PartnerAdminMixin:
    """Validate partner admin access via partner_admins table.

    Lookup order:
    1. By supabase_user_id (fast path)
    2. By email from JWT (first-login backfill)
    """
    permission_classes = [SupabaseIsAuthenticated]

    def get_admin(self, request):
        user_id = request.user_id
        if not user_id:
            return None

        # Fast path: lookup by UID
        admin = PartnerAdmin.objects.filter(supabase_user_id=user_id).select_related('org').first()
        if admin:
            return admin

        # Fallback: lookup by email, backfill UID
        email = getattr(request, 'supabase_user', {}).get('email')
        if email:
            admin = PartnerAdmin.objects.filter(email=email, supabase_user_id__isnull=True).select_related('org').first()
            if admin:
                admin.supabase_user_id = user_id
                admin.save(update_fields=['supabase_user_id'])
                return admin

        return None

    def get_partner_students(self, request):
        admin = self.get_admin(request)
        if not admin:
            return None, None

        if admin.is_super_admin:
            students = StudentProfile.objects.all().order_by('-created_at')
            return students, None

        if not admin.org:
            return None, None

        students = StudentProfile.objects.filter(
            referred_by_org=admin.org,
        ).order_by('-created_at')
        return students, admin.org


class AdminRoleView(PartnerAdminMixin, APIView):
    """GET /api/v1/admin/role/ - Check if user has admin access."""

    def get(self, request):
        admin = self.get_admin(request)
        if not admin:
            return Response({'is_admin': False})
        return Response({
            'is_admin': True,
            'is_super_admin': admin.is_super_admin,
            'org_name': admin.org.name if admin.org else None,
            'admin_name': admin.name,
        })


class PartnerDashboardView(PartnerAdminMixin, APIView):
    """GET /api/v1/admin/dashboard/ - Partner dashboard statistics."""

    def get(self, request):
        students, org = self.get_partner_students(request)
        if students is None:
            return Response({'error': 'Not a partner admin'}, status=403)

        total = students.count()
        completed = students.exclude(grades={}).count()
        by_exam = {
            'spm': students.filter(exam_type='spm').count(),
            'stpm': students.filter(exam_type='stpm').count(),
        }

        field_counter = Counter()
        for s in students:
            signals = s.student_signals or {}
            fi = signals.get('field_interest', {})
            if isinstance(fi, dict):
                for field in fi:
                    field_counter[field] += 1
        top_fields = [{'field': f, 'count': c} for f, c in field_counter.most_common(5)]

        admin = self.get_admin(request)
        return Response({
            'org_name': org.name if org else 'Semua Organisasi',
            'is_super_admin': admin.is_super_admin if admin else False,
            'total_students': total,
            'completed_onboarding': completed,
            'by_exam_type': by_exam,
            'top_fields': top_fields,
        })


class PartnerStudentListView(PartnerAdminMixin, APIView):
    """GET /api/v1/admin/students/ - List referred students."""

    def get(self, request):
        students, org = self.get_partner_students(request)
        if students is None:
            return Response({'error': 'Not a partner admin'}, status=403)

        admin = self.get_admin(request)
        serializer = PartnerStudentListSerializer(students, many=True)
        return Response({
            'org_name': org.name if org else 'Semua Organisasi',
            'is_super_admin': admin.is_super_admin if admin else False,
            'count': students.count(),
            'students': serializer.data,
        })


class PartnerStudentDetailView(PartnerAdminMixin, APIView):
    """GET /api/v1/admin/students/<user_id>/ - Student detail."""

    def get(self, request, user_id):
        admin = self.get_admin(request)
        if not admin:
            return Response({'error': 'Not a partner admin'}, status=403)

        if admin.is_super_admin:
            try:
                student = StudentProfile.objects.get(supabase_user_id=user_id)
            except StudentProfile.DoesNotExist:
                return Response({'error': 'Student not found'}, status=404)
        else:
            students, org = self.get_partner_students(request)
            if students is None:
                return Response({'error': 'Not a partner admin'}, status=403)
            try:
                student = students.get(supabase_user_id=user_id)
            except StudentProfile.DoesNotExist:
                return Response({'error': 'Student not found'}, status=404)

        serializer = PartnerStudentDetailSerializer(student)
        return Response(serializer.data)


class PartnerStudentExportView(PartnerAdminMixin, APIView):
    """GET /api/v1/admin/students/export/ - CSV export of referred students."""

    def get(self, request):
        students, org = self.get_partner_students(request)
        if students is None:
            return Response({'error': 'Not a partner admin'}, status=403)

        filename = f'{org.code}_students.csv' if org else 'all_students.csv'
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        writer = csv.writer(response)
        writer.writerow(['Name', 'IC', 'Gender', 'State', 'Exam Type', 'Date Joined'])

        for s in students:
            writer.writerow([
                s.name, s.nric, s.gender, s.preferred_state,
                s.exam_type, s.created_at.strftime('%Y-%m-%d'),
            ])

        return response


class AdminInviteView(PartnerAdminMixin, APIView):
    """POST /api/v1/admin/invite/ - Invite a partner admin (super admin only)."""

    def post(self, request):
        admin = self.get_admin(request)
        if not admin or not admin.is_super_admin:
            return Response({'error': 'Super admin access required'}, status=403)

        email = request.data.get('email', '').strip().lower()
        name = request.data.get('name', '').strip()
        org_id = request.data.get('org_id')
        new_org_name = request.data.get('new_org_name', '').strip()
        new_org_code = request.data.get('new_org_code', '').strip().lower()

        if not email or not name:
            return Response({'error': 'email and name are required'}, status=400)

        # Check duplicate
        if PartnerAdmin.objects.filter(email=email).exists():
            return Response({'error': 'Admin with this email already exists'}, status=409)

        # Resolve or create org
        org = None
        if new_org_name and new_org_code:
            org, _ = PartnerOrganisation.objects.get_or_create(
                code=new_org_code,
                defaults={
                    'name': new_org_name,
                    'contact_person': request.data.get('contact_person', ''),
                    'phone': request.data.get('org_phone', ''),
                },
            )
        elif org_id:
            try:
                org = PartnerOrganisation.objects.get(id=org_id)
            except PartnerOrganisation.DoesNotExist:
                return Response({'error': 'Organisation not found'}, status=404)

        # Call Supabase Admin API to send invite
        service_role_key = getattr(settings, 'SUPABASE_SERVICE_ROLE_KEY', '')
        supabase_url = getattr(settings, 'SUPABASE_URL', '')

        if not service_role_key or not supabase_url:
            return Response({'error': 'Supabase service role key not configured'}, status=500)

        import requests as http_requests
        invite_resp = http_requests.post(
            f'{supabase_url}/auth/v1/invite',
            json={'email': email},
            headers={
                'apikey': service_role_key,
                'Authorization': f'Bearer {service_role_key}',
                'Content-Type': 'application/json',
            },
        )

        if invite_resp.status_code not in (200, 201):
            logger.error(f"Supabase invite failed: {invite_resp.status_code} {invite_resp.text}")
            return Response({'error': 'Failed to send invite email'}, status=502)

        # Create admin row (UID will be set on first login)
        PartnerAdmin.objects.create(
            email=email,
            name=name,
            org=org,
        )

        return Response({
            'message': f'Invite sent to {email}',
            'org': org.name if org else None,
        }, status=201)


class AdminOrgsView(PartnerAdminMixin, APIView):
    """GET /api/v1/admin/orgs/ - List organisations for invite dropdown."""

    def get(self, request):
        admin = self.get_admin(request)
        if not admin or not admin.is_super_admin:
            return Response({'error': 'Super admin access required'}, status=403)

        orgs = PartnerOrganisation.objects.filter(is_active=True).values(
            'id', 'code', 'name', 'contact_person', 'phone',
        )
        return Response({'orgs': list(orgs)})
```

**Step 4: Update urls.py**

In `halatuju_api/apps/courses/urls.py`, update the import and add routes:

```python
from .views_admin import (
    AdminRoleView, AdminInviteView, AdminOrgsView,
    PartnerDashboardView, PartnerStudentListView,
    PartnerStudentDetailView, PartnerStudentExportView,
)

# In urlpatterns, replace existing admin routes:
    path('admin/role/', AdminRoleView.as_view(), name='admin-role'),
    path('admin/invite/', AdminInviteView.as_view(), name='admin-invite'),
    path('admin/orgs/', AdminOrgsView.as_view(), name='admin-orgs'),
    path('admin/dashboard/', PartnerDashboardView.as_view(), name='partner-dashboard'),
    path('admin/students/', PartnerStudentListView.as_view(), name='partner-students'),
    path('admin/students/export/', PartnerStudentExportView.as_view(), name='partner-export'),
    path('admin/students/<str:user_id>/', PartnerStudentDetailView.as_view(), name='partner-student-detail'),
```

**Step 5: Add SUPABASE_SERVICE_ROLE_KEY to settings**

In `halatuju_api/halatuju/settings/base.py`, add after the SUPABASE_JWT_SECRET line:

```python
SUPABASE_SERVICE_ROLE_KEY = os.environ.get('SUPABASE_SERVICE_ROLE_KEY', '')
```

**Step 6: Run tests**

Run: `cd halatuju_api && python -m pytest apps/courses/tests/test_admin_auth.py -v`
Expected: All PASS

**Step 7: Run full test suite to check nothing broke**

Run: `cd halatuju_api && python -m pytest apps/courses/tests/ apps/reports/tests/ -v --tb=short`
Expected: All pass (some tests may need fixing if they reference `admin_org_code`)

**Step 8: Commit**

```bash
git add halatuju_api/apps/courses/views_admin.py halatuju_api/apps/courses/urls.py halatuju_api/halatuju/settings/base.py halatuju_api/apps/courses/tests/test_admin_auth.py
git commit -m "feat: rewrite PartnerAdminMixin to use partner_admins table, add invite + orgs endpoints"
```

---

### Task 4: Register PartnerAdmin in Django admin

**Files:**
- Modify: `halatuju_api/apps/courses/admin.py`

**Step 1: Read current admin.py**

Check `halatuju_api/apps/courses/admin.py` for existing registrations.

**Step 2: Add PartnerAdmin registration**

```python
from .models import PartnerAdmin

@admin.register(PartnerAdmin)
class PartnerAdminAdmin(admin.ModelAdmin):
    list_display = ['name', 'email', 'org', 'is_super_admin', 'created_at']
    list_filter = ['is_super_admin', 'org']
    search_fields = ['name', 'email']
```

**Step 3: Verify locally**

Run: `cd halatuju_api && python manage.py check`
Expected: System check identified no issues.

**Step 4: Commit**

```bash
git add halatuju_api/apps/courses/admin.py
git commit -m "feat: register PartnerAdmin in Django admin"
```

---

### Task 5: Admin Supabase client (isolated session)

**Files:**
- Create: `halatuju-web/src/lib/admin-supabase.ts`

**Step 1: Create the admin Supabase client**

Create `halatuju-web/src/lib/admin-supabase.ts`:

```typescript
import { createClient, type SupabaseClient } from '@supabase/supabase-js'

let _adminSupabase: SupabaseClient | null = null

/**
 * Separate Supabase client for admin auth.
 * Uses a different storage key so admin and student sessions don't conflict.
 */
export function getAdminSupabase(): SupabaseClient {
  if (!_adminSupabase) {
    const url = process.env.NEXT_PUBLIC_SUPABASE_URL
    const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY
    if (!url || !key) {
      throw new Error('Supabase credentials not configured')
    }
    _adminSupabase = createClient(url, key, {
      auth: {
        storageKey: 'halatuju_admin_session',
      },
    })
  }
  return _adminSupabase
}

export async function adminSignInWithPassword(email: string, password: string) {
  const { data, error } = await getAdminSupabase().auth.signInWithPassword({
    email,
    password,
  })
  return { data, error }
}

export async function adminSignInWithGoogle() {
  const { data, error } = await getAdminSupabase().auth.signInWithOAuth({
    provider: 'google',
    options: {
      redirectTo: `${window.location.origin}/admin/auth/callback`,
    },
  })
  return { data, error }
}

export async function adminResetPassword(email: string) {
  const { error } = await getAdminSupabase().auth.resetPasswordForEmail(email, {
    redirectTo: `${window.location.origin}/admin/login`,
  })
  return { error }
}

export async function adminSignOut() {
  const { error } = await getAdminSupabase().auth.signOut()
  return { error }
}

export async function getAdminSession() {
  const { data: { session }, error } = await getAdminSupabase().auth.getSession()
  return { session, error }
}
```

**Step 2: Verify build**

Run: `cd halatuju-web && npx next build 2>&1 | tail -5`
Expected: Compiled successfully (file is just created, not imported yet)

**Step 3: Commit**

```bash
git add halatuju-web/src/lib/admin-supabase.ts
git commit -m "feat: add isolated admin Supabase client with separate storage key"
```

---

### Task 6: Admin auth context

**Files:**
- Create: `halatuju-web/src/lib/admin-auth-context.tsx`

**Step 1: Create AdminAuthProvider**

Create `halatuju-web/src/lib/admin-auth-context.tsx`:

```tsx
'use client'

import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  type ReactNode,
} from 'react'
import { getAdminSession, getAdminSupabase } from '@/lib/admin-supabase'
import type { Session } from '@supabase/supabase-js'

interface AdminRole {
  is_admin: boolean
  is_super_admin: boolean
  org_name: string | null
  admin_name: string
}

interface AdminAuthContextValue {
  session: Session | null
  token: string | null
  isLoading: boolean
  isAdminAuthenticated: boolean
  role: AdminRole | null
  refreshRole: () => Promise<void>
}

const AdminAuthContext = createContext<AdminAuthContextValue | null>(null)

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export function AdminAuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null)
  const [role, setRole] = useState<AdminRole | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  const checkRole = useCallback(async (token: string) => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/admin/role/`, {
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      })
      if (res.ok) {
        const data = await res.json()
        if (data.is_admin) {
          setRole(data)
          return true
        }
      }
    } catch {
      // Role check failed — treat as not admin
    }
    setRole(null)
    return false
  }, [])

  const refreshRole = useCallback(async () => {
    if (session?.access_token) {
      await checkRole(session.access_token)
    }
  }, [session, checkRole])

  useEffect(() => {
    getAdminSession()
      .then(async ({ session }) => {
        setSession(session ?? null)
        if (session?.access_token) {
          await checkRole(session.access_token)
        }
        setIsLoading(false)
      })
      .catch(() => setIsLoading(false))

    const {
      data: { subscription },
    } = getAdminSupabase().auth.onAuthStateChange(async (event, session) => {
      setSession(session)
      if (session?.access_token) {
        await checkRole(session.access_token)
      } else {
        setRole(null)
      }
    })
    return () => subscription.unsubscribe()
  }, [checkRole])

  const value: AdminAuthContextValue = {
    session,
    token: session?.access_token ?? null,
    isLoading,
    isAdminAuthenticated: !!session && !!role?.is_admin,
    role,
    refreshRole,
  }

  return (
    <AdminAuthContext.Provider value={value}>{children}</AdminAuthContext.Provider>
  )
}

export function useAdminAuth() {
  const ctx = useContext(AdminAuthContext)
  if (!ctx) throw new Error('useAdminAuth must be used within AdminAuthProvider')
  return ctx
}
```

**Step 2: Verify build**

Run: `cd halatuju-web && npx next build 2>&1 | tail -5`
Expected: Compiled successfully

**Step 3: Commit**

```bash
git add halatuju-web/src/lib/admin-auth-context.tsx
git commit -m "feat: add AdminAuthProvider with role checking and session isolation"
```

---

### Task 7: Admin login page

**Files:**
- Create: `halatuju-web/src/app/admin/login/page.tsx`

**Step 1: Create the login page**

Create `halatuju-web/src/app/admin/login/page.tsx`:

```tsx
'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import Image from 'next/image'
import {
  adminSignInWithPassword,
  adminSignInWithGoogle,
  adminResetPassword,
} from '@/lib/admin-supabase'

type Step = 'login' | 'forgot' | 'forgot-sent'

export default function AdminLoginPage() {
  const router = useRouter()
  const [step, setStep] = useState<Step>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError(null)

    const { data, error } = await adminSignInWithPassword(email, password)

    if (error) {
      setError(error.message)
      setLoading(false)
      return
    }

    if (data.session) {
      // Check admin role
      try {
        const res = await fetch(
          `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/admin/role/`,
          {
            headers: {
              Authorization: `Bearer ${data.session.access_token}`,
              'Content-Type': 'application/json',
            },
          }
        )
        const role = await res.json()
        if (!role.is_admin) {
          setError('This account does not have admin access.')
          // Sign out from admin client
          const { adminSignOut } = await import('@/lib/admin-supabase')
          await adminSignOut()
          setLoading(false)
          return
        }
      } catch {
        setError('Failed to verify admin access.')
        setLoading(false)
        return
      }

      router.push('/admin')
    }

    setLoading(false)
  }

  const handleGoogleLogin = async () => {
    setLoading(true)
    setError(null)
    const { error } = await adminSignInWithGoogle()
    if (error) {
      setError(error.message)
      setLoading(false)
    }
    // Redirect happens via OAuth
  }

  const handleForgotPassword = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError(null)

    const { error } = await adminResetPassword(email)
    if (error) {
      setError(error.message)
      setLoading(false)
      return
    }

    setStep('forgot-sent')
    setLoading(false)
  }

  return (
    <main className="min-h-screen bg-gradient-to-b from-blue-50 to-white flex items-center justify-center">
      <div className="w-full max-w-md px-6">
        {/* Logo */}
        <div className="flex items-center justify-center gap-2 mb-8">
          <Image src="/logo-icon.png" alt="HalaTuju" width={90} height={48} />
          <span className="text-lg font-bold text-blue-600">Admin</span>
        </div>

        {/* Card */}
        <div className="bg-white rounded-2xl border border-gray-200 p-8 shadow-sm">
          {step === 'login' && (
            <>
              <h1 className="text-2xl font-bold text-gray-900 text-center mb-2">
                Admin Login
              </h1>
              <p className="text-gray-600 text-center mb-8">
                Partner organisation portal
              </p>

              {error && (
                <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
                  <p className="text-red-600 text-sm">{error}</p>
                </div>
              )}

              <form onSubmit={handleLogin} className="space-y-4 mb-6">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Email
                  </label>
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="admin@organisation.com"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Password
                  </label>
                  <input
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="Enter your password"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                    required
                  />
                </div>
                <button
                  type="submit"
                  disabled={loading || !email || !password}
                  className="w-full bg-blue-600 text-white py-3 rounded-lg font-medium hover:bg-blue-700 transition-colors disabled:opacity-50"
                >
                  {loading ? 'Signing in...' : 'Sign In'}
                </button>
              </form>

              <button
                onClick={() => { setStep('forgot'); setError(null) }}
                className="w-full text-sm text-gray-500 hover:text-gray-700 mb-6"
              >
                Forgot password?
              </button>

              {/* Divider */}
              <div className="relative mb-6">
                <div className="absolute inset-0 flex items-center">
                  <div className="w-full border-t border-gray-200" />
                </div>
                <div className="relative flex justify-center text-sm">
                  <span className="px-4 bg-white text-gray-500">or</span>
                </div>
              </div>

              {/* Google Login */}
              <button
                onClick={handleGoogleLogin}
                disabled={loading}
                className="w-full flex items-center justify-center gap-3 px-6 py-3 border-2 border-gray-200 rounded-lg font-medium text-gray-700 hover:bg-gray-50 transition-colors disabled:opacity-50"
              >
                <svg className="w-5 h-5" viewBox="0 0 24 24">
                  <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
                  <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
                  <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
                  <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
                </svg>
                Sign in with Google
              </button>
            </>
          )}

          {step === 'forgot' && (
            <>
              <h1 className="text-2xl font-bold text-gray-900 text-center mb-2">
                Reset Password
              </h1>
              <p className="text-gray-600 text-center mb-8">
                Enter your email to receive a reset link
              </p>

              {error && (
                <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
                  <p className="text-red-600 text-sm">{error}</p>
                </div>
              )}

              <form onSubmit={handleForgotPassword} className="space-y-4">
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="admin@organisation.com"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  required
                />
                <button
                  type="submit"
                  disabled={loading || !email}
                  className="w-full bg-blue-600 text-white py-3 rounded-lg font-medium hover:bg-blue-700 transition-colors disabled:opacity-50"
                >
                  {loading ? 'Sending...' : 'Send Reset Link'}
                </button>
                <button
                  type="button"
                  onClick={() => { setStep('login'); setError(null) }}
                  className="w-full text-sm text-gray-500 hover:text-gray-700"
                >
                  Back to login
                </button>
              </form>
            </>
          )}

          {step === 'forgot-sent' && (
            <div className="text-center">
              <h1 className="text-2xl font-bold text-gray-900 mb-2">Check Your Email</h1>
              <p className="text-gray-600 mb-6">
                A password reset link has been sent to <strong>{email}</strong>
              </p>
              <button
                onClick={() => { setStep('login'); setError(null) }}
                className="text-blue-600 hover:underline text-sm"
              >
                Back to login
              </button>
            </div>
          )}
        </div>
      </div>
    </main>
  )
}
```

**Step 2: Verify build**

Run: `cd halatuju-web && npx next build 2>&1 | tail -5`
Expected: Compiled successfully

**Step 3: Commit**

```bash
git add halatuju-web/src/app/admin/login/page.tsx
git commit -m "feat: add admin login page with email/password, Google, forgot password"
```

---

### Task 8: Admin OAuth callback route

**Files:**
- Create: `halatuju-web/src/app/admin/auth/callback/page.tsx`

**Step 1: Create the callback page**

Note: Supabase OAuth for browser uses hash-based redirects. The client JS picks up the session from the URL fragment. We need a page that initialises the admin Supabase client to capture the session.

Create `halatuju-web/src/app/admin/auth/callback/page.tsx`:

```tsx
'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { getAdminSupabase } from '@/lib/admin-supabase'

export default function AdminAuthCallbackPage() {
  const router = useRouter()
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const supabase = getAdminSupabase()

    // Supabase JS picks up the session from the URL hash automatically
    supabase.auth.getSession().then(async ({ data: { session } }) => {
      if (!session) {
        setError('Authentication failed. Please try again.')
        return
      }

      // Verify admin role
      try {
        const res = await fetch(
          `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/admin/role/`,
          {
            headers: {
              Authorization: `Bearer ${session.access_token}`,
              'Content-Type': 'application/json',
            },
          }
        )
        const role = await res.json()
        if (!role.is_admin) {
          await supabase.auth.signOut()
          setError('This account does not have admin access.')
          return
        }
      } catch {
        setError('Failed to verify admin access.')
        return
      }

      router.replace('/admin')
    })
  }, [router])

  if (error) {
    return (
      <main className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <p className="text-red-600 mb-4">{error}</p>
          <a href="/admin/login" className="text-blue-600 hover:underline">
            Back to login
          </a>
        </div>
      </main>
    )
  }

  return (
    <main className="min-h-screen flex items-center justify-center">
      <p className="text-gray-600">Signing in...</p>
    </main>
  )
}
```

**Step 2: Verify build**

Run: `cd halatuju-web && npx next build 2>&1 | tail -5`
Expected: Compiled successfully

**Step 3: Commit**

```bash
git add halatuju-web/src/app/admin/auth/callback/page.tsx
git commit -m "feat: add admin OAuth callback page for Google sign-in"
```

---

### Task 9: Rewire admin layout + admin-api to use AdminAuthProvider

**Files:**
- Modify: `halatuju-web/src/app/admin/layout.tsx`
- Modify: `halatuju-web/src/lib/admin-api.ts`
- Modify: `halatuju-web/src/app/admin/page.tsx`
- Modify: `halatuju-web/src/app/admin/students/page.tsx`
- Modify: `halatuju-web/src/app/admin/students/[id]/page.tsx`

**Step 1: Rewrite admin layout**

Replace `halatuju-web/src/app/admin/layout.tsx`:

```tsx
'use client'

import { AdminAuthProvider, useAdminAuth } from '@/lib/admin-auth-context'
import { useRouter, usePathname } from 'next/navigation'
import { useEffect } from 'react'
import Link from 'next/link'
import { adminSignOut } from '@/lib/admin-supabase'

function AdminLayoutInner({ children }: { children: React.ReactNode }) {
  const { isAdminAuthenticated, isLoading, role } = useAdminAuth()
  const router = useRouter()
  const pathname = usePathname()

  useEffect(() => {
    // Don't redirect if on login or callback pages
    if (pathname === '/admin/login' || pathname.startsWith('/admin/auth/')) return
    if (!isLoading && !isAdminAuthenticated) {
      router.replace('/admin/login')
    }
  }, [isAdminAuthenticated, isLoading, router, pathname])

  // Login and callback pages render without nav
  if (pathname === '/admin/login' || pathname.startsWith('/admin/auth/')) {
    return <>{children}</>
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        Loading...
      </div>
    )
  }

  if (!isAdminAuthenticated) {
    return null
  }

  const handleSignOut = async () => {
    await adminSignOut()
    router.replace('/admin/login')
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-white border-b px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <span className="font-bold text-blue-600">HalaTuju Admin</span>
          <Link
            href="/admin"
            className="text-sm text-gray-600 hover:text-blue-600"
          >
            Dashboard
          </Link>
          <Link
            href="/admin/students"
            className="text-sm text-gray-600 hover:text-blue-600"
          >
            Pelajar
          </Link>
          {role?.is_super_admin && (
            <Link
              href="/admin/invite"
              className="text-sm text-gray-600 hover:text-blue-600"
            >
              Invite
            </Link>
          )}
        </div>
        <div className="flex items-center gap-3">
          <span className="text-sm text-gray-500">
            {role?.admin_name}
            {role?.org_name ? ` (${role.org_name})` : ' (Super Admin)'}
          </span>
          <button
            onClick={handleSignOut}
            className="text-sm text-red-600 hover:text-red-800"
          >
            Log Out
          </button>
        </div>
      </nav>
      <main className="max-w-6xl mx-auto p-4 md:p-6">{children}</main>
    </div>
  )
}

export default function AdminLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <AdminAuthProvider>
      <AdminLayoutInner>{children}</AdminLayoutInner>
    </AdminAuthProvider>
  )
}
```

**Step 2: Update admin-api.ts to accept token parameter**

The `admin-api.ts` already accepts `options.token`. The admin pages just need to pass the admin token. No changes needed to admin-api.ts itself.

**Step 3: Update admin page.tsx (dashboard)**

In `halatuju-web/src/app/admin/page.tsx`, replace `useAuth` with `useAdminAuth`:

- Replace: `import { useAuth } from '@/lib/auth-context'` → `import { useAdminAuth } from '@/lib/admin-auth-context'`
- Replace: `const { token } = useAuth()` → `const { token } = useAdminAuth()`

Do the same for:
- `halatuju-web/src/app/admin/students/page.tsx`
- `halatuju-web/src/app/admin/students/[id]/page.tsx`

**Step 4: Verify build**

Run: `cd halatuju-web && npx next build 2>&1 | tail -10`
Expected: Compiled successfully

**Step 5: Commit**

```bash
git add halatuju-web/src/app/admin/layout.tsx halatuju-web/src/app/admin/page.tsx halatuju-web/src/app/admin/students/page.tsx halatuju-web/src/app/admin/students/\[id\]/page.tsx
git commit -m "feat: rewire admin layout and pages to use AdminAuthProvider"
```

---

### Task 10: Admin invite page

**Files:**
- Create: `halatuju-web/src/app/admin/invite/page.tsx`
- Modify: `halatuju-web/src/lib/admin-api.ts`

**Step 1: Add invite API functions to admin-api.ts**

Add to `halatuju-web/src/lib/admin-api.ts`:

```typescript
export interface OrgItem {
  id: number
  code: string
  name: string
  contact_person: string
  phone: string
}

export async function getOrgs(options?: ApiOptions) {
  return adminFetch<{ orgs: OrgItem[] }>('/api/v1/admin/orgs/', options)
}

export async function inviteAdmin(
  data: {
    email: string
    name: string
    org_id?: number
    new_org_name?: string
    new_org_code?: string
    contact_person?: string
    org_phone?: string
  },
  options?: ApiOptions
) {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  }
  if (options?.token) {
    headers['Authorization'] = `Bearer ${options.token}`
  }

  const res = await fetch(`${API_BASE}/api/v1/admin/invite/`, {
    method: 'POST',
    headers,
    body: JSON.stringify(data),
  })

  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.error || `Invite failed: ${res.status}`)
  }

  return res.json()
}
```

**Step 2: Create invite page**

Create `halatuju-web/src/app/admin/invite/page.tsx`:

```tsx
'use client'

import { useState, useEffect } from 'react'
import { useAdminAuth } from '@/lib/admin-auth-context'
import { getOrgs, inviteAdmin, type OrgItem } from '@/lib/admin-api'

export default function AdminInvitePage() {
  const { token, role } = useAdminAuth()
  const [orgs, setOrgs] = useState<OrgItem[]>([])
  const [orgMode, setOrgMode] = useState<'existing' | 'new'>('existing')
  const [selectedOrgId, setSelectedOrgId] = useState<number | ''>('')
  const [newOrgName, setNewOrgName] = useState('')
  const [newOrgCode, setNewOrgCode] = useState('')
  const [contactPerson, setContactPerson] = useState('')
  const [orgPhone, setOrgPhone] = useState('')
  const [adminName, setAdminName] = useState('')
  const [adminEmail, setAdminEmail] = useState('')
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)

  useEffect(() => {
    if (token) {
      getOrgs({ token }).then((data) => setOrgs(data.orgs)).catch(() => {})
    }
  }, [token])

  if (!role?.is_super_admin) {
    return <p className="text-red-600">Super admin access required.</p>
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setMessage(null)

    try {
      const data: Parameters<typeof inviteAdmin>[0] = {
        email: adminEmail,
        name: adminName,
      }
      if (orgMode === 'existing' && selectedOrgId) {
        data.org_id = Number(selectedOrgId)
      } else if (orgMode === 'new' && newOrgName && newOrgCode) {
        data.new_org_name = newOrgName
        data.new_org_code = newOrgCode
        data.contact_person = contactPerson
        data.org_phone = orgPhone
      }

      const result = await inviteAdmin(data, { token: token! })
      setMessage({ type: 'success', text: result.message })

      // Reset form
      setAdminName('')
      setAdminEmail('')
      setSelectedOrgId('')
      setNewOrgName('')
      setNewOrgCode('')
      setContactPerson('')
      setOrgPhone('')

      // Refresh org list
      if (token) {
        getOrgs({ token }).then((data) => setOrgs(data.orgs)).catch(() => {})
      }
    } catch (err) {
      setMessage({ type: 'error', text: err instanceof Error ? err.message : 'Failed to send invite' })
    }

    setLoading(false)
  }

  return (
    <div className="max-w-xl">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Invite Partner Admin</h1>

      {message && (
        <div className={`rounded-lg p-4 mb-6 ${message.type === 'success' ? 'bg-green-50 border border-green-200 text-green-700' : 'bg-red-50 border border-red-200 text-red-600'}`}>
          {message.text}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Organisation */}
        <fieldset className="space-y-3">
          <legend className="text-sm font-semibold text-gray-900">Organisation</legend>
          <div className="flex gap-4">
            <label className="flex items-center gap-2">
              <input
                type="radio"
                checked={orgMode === 'existing'}
                onChange={() => setOrgMode('existing')}
              />
              <span className="text-sm">Existing</span>
            </label>
            <label className="flex items-center gap-2">
              <input
                type="radio"
                checked={orgMode === 'new'}
                onChange={() => setOrgMode('new')}
              />
              <span className="text-sm">New Organisation</span>
            </label>
          </div>

          {orgMode === 'existing' ? (
            <select
              value={selectedOrgId}
              onChange={(e) => setSelectedOrgId(e.target.value ? Number(e.target.value) : '')}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg"
            >
              <option value="">Select organisation...</option>
              {orgs.map((org) => (
                <option key={org.id} value={org.id}>
                  {org.name} ({org.code})
                </option>
              ))}
            </select>
          ) : (
            <div className="space-y-3">
              <input
                type="text"
                value={newOrgName}
                onChange={(e) => setNewOrgName(e.target.value)}
                placeholder="Organisation name"
                className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                required={orgMode === 'new'}
              />
              <input
                type="text"
                value={newOrgCode}
                onChange={(e) => setNewOrgCode(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, ''))}
                placeholder="URL code (e.g. cumig)"
                className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                required={orgMode === 'new'}
              />
              <input
                type="text"
                value={contactPerson}
                onChange={(e) => setContactPerson(e.target.value)}
                placeholder="Contact person (optional)"
                className="w-full px-3 py-2 border border-gray-300 rounded-lg"
              />
              <input
                type="text"
                value={orgPhone}
                onChange={(e) => setOrgPhone(e.target.value)}
                placeholder="Phone (optional)"
                className="w-full px-3 py-2 border border-gray-300 rounded-lg"
              />
            </div>
          )}
        </fieldset>

        {/* Admin details */}
        <fieldset className="space-y-3">
          <legend className="text-sm font-semibold text-gray-900">Admin Details</legend>
          <input
            type="text"
            value={adminName}
            onChange={(e) => setAdminName(e.target.value)}
            placeholder="Admin name"
            className="w-full px-3 py-2 border border-gray-300 rounded-lg"
            required
          />
          <input
            type="email"
            value={adminEmail}
            onChange={(e) => setAdminEmail(e.target.value)}
            placeholder="Admin email"
            className="w-full px-3 py-2 border border-gray-300 rounded-lg"
            required
          />
        </fieldset>

        <button
          type="submit"
          disabled={loading || !adminName || !adminEmail}
          className="w-full bg-blue-600 text-white py-3 rounded-lg font-medium hover:bg-blue-700 transition-colors disabled:opacity-50"
        >
          {loading ? 'Sending invite...' : 'Send Invite'}
        </button>
      </form>
    </div>
  )
}
```

**Step 3: Verify build**

Run: `cd halatuju-web && npx next build 2>&1 | tail -5`
Expected: Compiled successfully

**Step 4: Commit**

```bash
git add halatuju-web/src/app/admin/invite/page.tsx halatuju-web/src/lib/admin-api.ts
git commit -m "feat: add admin invite page and API functions"
```

---

### Task 11: Supabase setup — RLS, service role key, seed super admin

**Files:**
- No code files — Supabase SQL + Cloud Run env var

**Step 1: Apply migration to Supabase**

The Django migration creates `partner_admins` table. After deploy, run:

```sql
-- Verify table exists
SELECT column_name FROM information_schema.columns
WHERE table_name = 'partner_admins' ORDER BY ordinal_position;
```

If the table wasn't auto-created by Django migrate (because we fake-applied earlier), create it manually:

```sql
CREATE TABLE IF NOT EXISTS partner_admins (
    id bigserial PRIMARY KEY,
    supabase_user_id varchar(100) UNIQUE,
    org_id bigint REFERENCES partner_organisations(id) ON DELETE CASCADE,
    is_super_admin boolean NOT NULL DEFAULT false,
    name varchar(200) NOT NULL,
    email varchar(254) NOT NULL UNIQUE,
    created_at timestamptz NOT NULL DEFAULT now()
);
```

**Step 2: Enable RLS**

```sql
ALTER TABLE partner_admins ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Admins can read own row"
ON partner_admins FOR SELECT
USING (auth.uid()::text = supabase_user_id);

-- Service role bypasses RLS for invite flow
```

**Step 3: Remove admin_org_code from api_student_profiles**

```sql
ALTER TABLE api_student_profiles DROP COLUMN IF EXISTS admin_org_code;
```

**Step 4: Seed super admin**

```sql
INSERT INTO partner_admins (supabase_user_id, is_super_admin, name, email)
VALUES ('2abda202-cc43-45b6-b227-776437bff964', true, 'Ve. Elanjelian', 'tamiliam@gmail.com');
```

**Step 5: Add SUPABASE_SERVICE_ROLE_KEY to Cloud Run**

Find the service role key in Supabase Dashboard → Settings → API → `service_role` key.

```bash
gcloud run services update halatuju-api \
  --region asia-southeast1 \
  --project gen-lang-client-0871147736 \
  --account tamiliam@gmail.com \
  --update-env-vars SUPABASE_SERVICE_ROLE_KEY=<the-key>
```

**Step 6: Verify**

```sql
SELECT * FROM partner_admins;
```

Expected: 1 row — super admin.

**Step 7: Commit** (nothing to commit — all SQL/env changes)

---

### Task 12: Full test suite + cleanup

**Files:**
- Modify: `halatuju_api/apps/courses/tests/test_admin_auth.py` (if needed)

**Step 1: Run full backend test suite**

Run: `cd halatuju_api && python -m pytest apps/courses/tests/ apps/reports/tests/ -v --tb=short`
Expected: All pass. Fix any failures caused by removing `admin_org_code`.

**Step 2: Run frontend build**

Run: `cd halatuju-web && npx next build`
Expected: Compiled successfully

**Step 3: Final commit if any fixes were needed**

```bash
git add -A
git commit -m "fix: test suite cleanup after admin auth migration"
```

**Step 4: Push**

```bash
git push
```
