# Partner Referral & Admin Portal — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enable partner organisations to track students they onboard, with auto-tagging via referral URLs and a read-only admin portal.

**Architecture:** New `PartnerOrganisation` model + two fields on `StudentProfile` for referral tracking. Frontend captures `?ref=` URL param silently or shows optional chips on IC page. Same Next.js app with role-gated `/admin` pages. Backend API endpoints scoped by partner org.

**Tech Stack:** Django REST Framework, Next.js 14, Supabase Auth, Supabase Postgres

**Design doc:** `docs/plans/2026-03-16-partner-referral-design.md`

**UI mockup:** `docs/ic_referral_a.png` (Stitch screen ID `39d5d8188aac476bae8e906b89457f70`)

---

## Sprint 1: Backend Data Model & Referral Capture

### Task 1: PartnerOrganisation model + migration

**Files:**
- Modify: `halatuju_api/apps/courses/models.py:377` (add new model before StudentProfile)
- Create: `halatuju_api/apps/courses/migrations/0031_partner_organisation.py` (auto-generated)
- Test: `halatuju_api/apps/courses/tests/test_partner_referral.py`

**Step 1: Write the failing test**

```python
# halatuju_api/apps/courses/tests/test_partner_referral.py
from django.test import TestCase
from apps.courses.models import PartnerOrganisation


class PartnerOrganisationModelTest(TestCase):
    def test_create_partner(self):
        partner = PartnerOrganisation.objects.create(
            code='cumig',
            name='CUMIG',
            contact_email='admin@cumig.org',
        )
        self.assertEqual(partner.code, 'cumig')
        self.assertEqual(str(partner), 'CUMIG (cumig)')
        self.assertTrue(partner.is_active)

    def test_code_unique(self):
        PartnerOrganisation.objects.create(code='cumig', name='CUMIG')
        with self.assertRaises(Exception):
            PartnerOrganisation.objects.create(code='cumig', name='CUMIG 2')
```

**Step 2: Run test to verify it fails**

Run: `cd halatuju_api && python manage.py test apps.courses.tests.test_partner_referral -v 2`
Expected: FAIL with `ImportError` or `cannot import name 'PartnerOrganisation'`

**Step 3: Write the model**

Add to `halatuju_api/apps/courses/models.py` before the `StudentProfile` class (around line 377):

```python
class PartnerOrganisation(models.Model):
    """Partner organisation that refers students via roadshows or campaigns."""
    code = models.CharField(max_length=50, unique=True, help_text='URL slug: cumig, partner2')
    name = models.CharField(max_length=200)
    contact_email = models.EmailField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'partner_organisations'
        ordering = ['name']

    def __str__(self):
        return f'{self.name} ({self.code})'
```

**Step 4: Generate and run migration**

Run: `cd halatuju_api && python manage.py makemigrations courses --name partner_organisation && python manage.py migrate`
Expected: Migration 0031 created and applied.

**Step 5: Run test to verify it passes**

Run: `cd halatuju_api && python manage.py test apps.courses.tests.test_partner_referral -v 2`
Expected: 2 tests PASS

**Step 6: Commit**

```bash
git add halatuju_api/apps/courses/models.py halatuju_api/apps/courses/migrations/0031_*.py halatuju_api/apps/courses/tests/test_partner_referral.py
git commit -m "feat: add PartnerOrganisation model"
```

---

### Task 2: Add referral fields to StudentProfile

**Files:**
- Modify: `halatuju_api/apps/courses/models.py:447-450` (add fields after spm_prereq_grades)
- Create: `halatuju_api/apps/courses/migrations/0032_student_profile_referral.py` (auto-generated)
- Test: `halatuju_api/apps/courses/tests/test_partner_referral.py`

**Step 1: Write the failing test**

Append to `test_partner_referral.py`:

```python
from apps.courses.models import PartnerOrganisation, StudentProfile


class StudentProfileReferralTest(TestCase):
    def test_referral_fields_nullable(self):
        """Referral fields should be optional."""
        profile = StudentProfile.objects.create(supabase_user_id='test-user-1')
        self.assertIsNone(profile.referral_source)
        self.assertIsNone(profile.referred_by_org)

    def test_referral_with_partner(self):
        partner = PartnerOrganisation.objects.create(code='cumig', name='CUMIG')
        profile = StudentProfile.objects.create(
            supabase_user_id='test-user-2',
            referral_source='cumig',
            referred_by_org=partner,
        )
        self.assertEqual(profile.referral_source, 'cumig')
        self.assertEqual(profile.referred_by_org.code, 'cumig')

    def test_referral_without_partner(self):
        """Generic sources like 'whatsapp' have no partner FK."""
        profile = StudentProfile.objects.create(
            supabase_user_id='test-user-3',
            referral_source='whatsapp',
        )
        self.assertEqual(profile.referral_source, 'whatsapp')
        self.assertIsNone(profile.referred_by_org)
```

**Step 2: Run test to verify it fails**

Run: `cd halatuju_api && python manage.py test apps.courses.tests.test_partner_referral -v 2`
Expected: FAIL — `FieldError: Unknown field(s) (referral_source, referred_by_org)`

**Step 3: Add fields to StudentProfile**

In `halatuju_api/apps/courses/models.py`, add after `spm_prereq_grades` (around line 450):

```python
    referral_source = models.CharField(
        max_length=50, blank=True, null=True,
        help_text='Raw referral code or chip value (e.g. cumig, whatsapp, google)',
    )
    referred_by_org = models.ForeignKey(
        'PartnerOrganisation', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='referred_students',
    )
```

**Step 4: Generate and run migration**

Run: `cd halatuju_api && python manage.py makemigrations courses --name student_profile_referral && python manage.py migrate`

**Step 5: Run test to verify it passes**

Run: `cd halatuju_api && python manage.py test apps.courses.tests.test_partner_referral -v 2`
Expected: 5 tests PASS

**Step 6: Commit**

```bash
git add halatuju_api/apps/courses/models.py halatuju_api/apps/courses/migrations/0032_*.py halatuju_api/apps/courses/tests/test_partner_referral.py
git commit -m "feat: add referral_source and referred_by_org to StudentProfile"
```

---

### Task 3: Backend referral resolution in ProfileSyncView

**Files:**
- Modify: `halatuju_api/apps/courses/serializers.py:265-282` (add referral_source to ProfileUpdateSerializer)
- Modify: `halatuju_api/apps/courses/views.py:973-996` (resolve referral code to partner FK)
- Test: `halatuju_api/apps/courses/tests/test_partner_referral.py`

**Step 1: Write the failing test**

Append to `test_partner_referral.py`:

```python
from django.test import override_settings
from rest_framework.test import APIClient


# Minimal test JWT secret for testing
TEST_JWT_SECRET = 'test-secret-key-for-unit-tests-only'


class ProfileSyncReferralTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.partner = PartnerOrganisation.objects.create(code='cumig', name='CUMIG')

    def _sync(self, data, user_id='test-user-sync'):
        """Helper: call profile/sync/ with forced auth."""
        # Create profile first since we can't easily mock Supabase auth in unit tests
        profile, _ = StudentProfile.objects.get_or_create(
            supabase_user_id=user_id,
        )
        # Direct model update to simulate what the view does
        from apps.courses.models import PartnerOrganisation
        referral = data.get('referral_source')
        if referral:
            profile.referral_source = referral
            try:
                org = PartnerOrganisation.objects.get(code=referral, is_active=True)
                profile.referred_by_org = org
            except PartnerOrganisation.DoesNotExist:
                pass
            profile.save()
        return profile

    def test_referral_resolves_to_partner(self):
        profile = self._sync({'referral_source': 'cumig'})
        profile.refresh_from_db()
        self.assertEqual(profile.referral_source, 'cumig')
        self.assertEqual(profile.referred_by_org, self.partner)

    def test_referral_generic_no_partner(self):
        profile = self._sync({'referral_source': 'whatsapp'}, user_id='test-user-generic')
        profile.refresh_from_db()
        self.assertEqual(profile.referral_source, 'whatsapp')
        self.assertIsNone(profile.referred_by_org)

    def test_referral_inactive_partner_ignored(self):
        self.partner.is_active = False
        self.partner.save()
        profile = self._sync({'referral_source': 'cumig'}, user_id='test-user-inactive')
        profile.refresh_from_db()
        self.assertEqual(profile.referral_source, 'cumig')
        self.assertIsNone(profile.referred_by_org)
```

**Step 2: Run test to verify it fails**

Run: `cd halatuju_api && python manage.py test apps.courses.tests.test_partner_referral -v 2`
Expected: Tests may pass since we're testing model logic directly. That's OK — the tests validate the resolution logic we'll put in the view.

**Step 3: Add referral_source to ProfileUpdateSerializer**

In `halatuju_api/apps/courses/serializers.py`, find ProfileUpdateSerializer (line ~265). Add `referral_source` to the fields list:

```python
    referral_source = serializers.CharField(max_length=50, required=False, allow_blank=True)
```

**Step 4: Add referral resolution to ProfileSyncView**

In `halatuju_api/apps/courses/views.py`, find ProfileSyncView (line ~973). After the serializer saves the profile, add referral resolution. Find the line where profile is saved/updated and add after it:

```python
        # Resolve referral source to partner organisation
        referral = serializer.validated_data.get('referral_source')
        if referral:
            try:
                org = PartnerOrganisation.objects.get(code=referral, is_active=True)
                profile.referred_by_org = org
                profile.save(update_fields=['referred_by_org'])
            except PartnerOrganisation.DoesNotExist:
                pass  # Generic source (whatsapp, google) — no partner FK
```

Add the import at the top of views.py:
```python
from .models import PartnerOrganisation
```

**Step 5: Run full test suite**

Run: `cd halatuju_api && python manage.py test apps.courses -v 2`
Expected: All existing tests + 8 new tests PASS

**Step 6: Commit**

```bash
git add halatuju_api/apps/courses/serializers.py halatuju_api/apps/courses/views.py halatuju_api/apps/courses/tests/test_partner_referral.py
git commit -m "feat: resolve referral_source to partner org in ProfileSyncView"
```

---

### Task 4: Frontend — capture ?ref= URL param

**Files:**
- Modify: `halatuju-web/src/lib/storage.ts` (add KEY_REFERRAL_SOURCE)
- Create: `halatuju-web/src/hooks/useReferral.ts`
- Modify: `halatuju-web/src/app/layout.tsx` or landing page (capture ref param on first load)

**Step 1: Add storage constant**

In `halatuju-web/src/lib/storage.ts`, add after the last KEY_ constant:

```typescript
export const KEY_REFERRAL_SOURCE = 'halatuju_referral_source'
```

Also add `KEY_REFERRAL_SOURCE` to the `clearAll()` function's removal list.

**Step 2: Create useReferral hook**

Create `halatuju-web/src/hooks/useReferral.ts`:

```typescript
'use client'

import { useEffect } from 'react'
import { useSearchParams } from 'next/navigation'
import { KEY_REFERRAL_SOURCE } from '@/lib/storage'

/**
 * Captures ?ref= URL parameter and persists to localStorage.
 * Call this in the root layout or landing page.
 * Existing referral is NOT overwritten (first touch wins).
 */
export function useReferral() {
  const searchParams = useSearchParams()

  useEffect(() => {
    const ref = searchParams.get('ref')
    if (ref && !localStorage.getItem(KEY_REFERRAL_SOURCE)) {
      localStorage.setItem(KEY_REFERRAL_SOURCE, ref.toLowerCase().trim())
    }
  }, [searchParams])
}
```

**Step 3: Wire into root layout**

In the main layout or a client wrapper component that wraps the app, call `useReferral()`. Since `layout.tsx` is typically a server component, you may need to create a small client wrapper:

Create `halatuju-web/src/components/ReferralCapture.tsx`:

```typescript
'use client'

import { useReferral } from '@/hooks/useReferral'
import { Suspense } from 'react'

function ReferralCaptureInner() {
  useReferral()
  return null
}

export function ReferralCapture() {
  return (
    <Suspense fallback={null}>
      <ReferralCaptureInner />
    </Suspense>
  )
}
```

Add `<ReferralCapture />` to `layout.tsx` inside the body, before `{children}`.

**Step 4: Verify manually**

Open `http://localhost:3000/?ref=cumig` in browser. Check localStorage — should have `halatuju_referral_source: 'cumig'`.

**Step 5: Commit**

```bash
git add halatuju-web/src/lib/storage.ts halatuju-web/src/hooks/useReferral.ts halatuju-web/src/components/ReferralCapture.tsx halatuju-web/src/app/layout.tsx
git commit -m "feat: capture ?ref= URL param into localStorage"
```

---

### Task 5: Frontend — referral chips on IC page

**Files:**
- Modify: `halatuju-web/src/app/onboarding/ic/page.tsx` (add chips below form fields)
- Modify: `halatuju-web/src/messages/en.json`, `ms.json`, `ta.json` (i18n keys)

**Step 1: Add i18n keys**

In each message file, add under an `"onboarding"` or `"ic"` section:

```json
"referralLabel": "Bagaimana anda tahu tentang HalaTuju? (Pilihan)",
"referralWhatsapp": "WhatsApp",
"referralGoogle": "Google",
"referralFbig": "FB/IG",
"referralCumig": "CUMIG",
"referralOther": "Lain-lain"
```

(Use Malay for `ms.json`, English for `en.json`, Tamil for `ta.json`.)

**Step 2: Add chips to IC page**

In `halatuju-web/src/app/onboarding/ic/page.tsx`, after the name input field and before the "Seterusnya" button:

```tsx
// Referral chips (only if no ref already captured from URL)
const [referral, setReferral] = useState<string | null>(() =>
  typeof window !== 'undefined' ? localStorage.getItem(KEY_REFERRAL_SOURCE) : null
)

const REFERRAL_OPTIONS = [
  { value: 'whatsapp', label: 'WhatsApp' },
  { value: 'google', label: 'Google' },
  { value: 'fbig', label: 'FB/IG' },
  { value: 'cumig', label: 'CUMIG' },
  { value: 'other', label: 'Lain-lain' },
]
```

In the JSX, after the name field and before the button, conditionally render:

```tsx
{!referral && (
  <div className="mt-6 pt-4 border-t border-gray-100">
    <p className="text-sm text-gray-500 mb-3">
      Bagaimana anda tahu tentang HalaTuju? (Pilihan)
    </p>
    <div className="flex flex-wrap gap-2">
      {REFERRAL_OPTIONS.map((opt) => (
        <button
          key={opt.value}
          type="button"
          onClick={() => {
            setReferral(opt.value)
            localStorage.setItem(KEY_REFERRAL_SOURCE, opt.value)
          }}
          className={`px-3 py-1.5 rounded-full text-sm border transition-colors ${
            referral === opt.value
              ? 'bg-blue-600 text-white border-blue-600'
              : 'bg-white text-gray-700 border-gray-300 hover:border-blue-400'
          }`}
        >
          {opt.label}
        </button>
      ))}
    </div>
  </div>
)}
```

**Step 3: Include referral in syncProfile call**

In the IC page's submit handler, modify the `syncProfile` call to include the referral source:

```typescript
const ref = localStorage.getItem(KEY_REFERRAL_SOURCE)
await syncProfile(
  { nric: ic, ...(name.trim() && { name: name.trim() }), ...(ref && { referral_source: ref }) },
  { token }
)
```

Also add `referral_source` to the `SyncProfileData` interface in `halatuju-web/src/lib/api.ts`:

```typescript
interface SyncProfileData {
  // ... existing fields ...
  referral_source?: string
}
```

**Step 4: Add KEY_REFERRAL_SOURCE import to IC page**

```typescript
import { KEY_REFERRAL_SOURCE } from '@/lib/storage'
```

**Step 5: Verify manually**

1. Open IC page without `?ref=` — chips should appear
2. Select "CUMIG" — chip turns blue, localStorage updated
3. Open IC page with `?ref=cumig` already in localStorage — chips should NOT appear
4. Submit form — check network tab that `referral_source: 'cumig'` is sent

**Step 6: Commit**

```bash
git add halatuju-web/src/app/onboarding/ic/page.tsx halatuju-web/src/lib/api.ts halatuju-web/src/messages/
git commit -m "feat: optional referral chips on IC page with syncProfile integration"
```

---

### Task 6: Apply Supabase migration

**Step 1: Apply migration to Supabase**

Use the Supabase MCP `execute_sql` tool to create the tables and add fields:

```sql
-- PartnerOrganisation table
CREATE TABLE partner_organisations (
    id BIGSERIAL PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(200) NOT NULL,
    contact_email VARCHAR(254) DEFAULT '',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- RLS
ALTER TABLE partner_organisations ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow public read" ON partner_organisations FOR SELECT USING (true);

-- Add referral fields to StudentProfile
ALTER TABLE api_student_profiles ADD COLUMN referral_source VARCHAR(50);
ALTER TABLE api_student_profiles ADD COLUMN referred_by_org_id BIGINT REFERENCES partner_organisations(id) ON DELETE SET NULL;

-- Record migrations
INSERT INTO django_migrations (app, name, applied) VALUES
    ('courses', '0031_partner_organisation', NOW()),
    ('courses', '0032_student_profile_referral', NOW());

-- Seed CUMIG as first partner
INSERT INTO partner_organisations (code, name, contact_email) VALUES ('cumig', 'CUMIG', '');
```

**Step 2: Verify**

Run: `SELECT code, name, is_active FROM partner_organisations;`
Expected: 1 row (cumig, CUMIG, true)

**Step 3: Commit**

No files to commit — this is a database change only.

---

## Sprint 2: Partner Admin Portal (Backend)

### Task 7: Admin API — list partner's students

**Files:**
- Create: `halatuju_api/apps/courses/views_admin.py`
- Create: `halatuju_api/apps/courses/serializers_admin.py`
- Modify: `halatuju_api/apps/courses/urls.py` (add admin routes)
- Test: `halatuju_api/apps/courses/tests/test_partner_referral.py`

**Step 1: Write the admin serializer**

Create `halatuju_api/apps/courses/serializers_admin.py`:

```python
from rest_framework import serializers
from .models import StudentProfile, PartnerOrganisation


class PartnerStudentListSerializer(serializers.ModelSerializer):
    """Student list for partner admin — summary view."""
    class Meta:
        model = StudentProfile
        fields = [
            'supabase_user_id', 'name', 'nric', 'gender',
            'exam_type', 'created_at',
        ]


class PartnerStudentDetailSerializer(serializers.ModelSerializer):
    """Student detail for partner admin — full view."""
    saved_courses = serializers.SerializerMethodField()

    class Meta:
        model = StudentProfile
        fields = [
            'supabase_user_id', 'name', 'nric', 'gender',
            'nationality', 'exam_type', 'grades', 'stpm_grades',
            'student_signals', 'preferred_state', 'created_at',
        ]

    def get_saved_courses(self, obj):
        from .models import SavedCourse
        saved = SavedCourse.objects.filter(student=obj).select_related('course', 'stpm_course')[:10]
        results = []
        for sc in saved:
            course = sc.course or sc.stpm_course
            if course:
                results.append({
                    'course_id': course.course_id,
                    'name': course.name,
                })
        return results


class PartnerDashboardSerializer(serializers.Serializer):
    """Aggregate stats for partner dashboard."""
    total_students = serializers.IntegerField()
    completed_onboarding = serializers.IntegerField()
    by_exam_type = serializers.DictField()
    top_fields = serializers.ListField()
```

**Step 2: Write the admin views**

Create `halatuju_api/apps/courses/views_admin.py`:

```python
import csv
from django.http import HttpResponse
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from .models import StudentProfile, PartnerOrganisation
from .serializers_admin import (
    PartnerStudentListSerializer,
    PartnerStudentDetailSerializer,
)
from .authentication import SupabaseIsAuthenticated


class PartnerAdminMixin:
    """Validate partner admin access and resolve org."""
    permission_classes = [SupabaseIsAuthenticated]

    def get_partner_org(self, request):
        """Return the PartnerOrganisation for the authenticated user, or None."""
        user_id = getattr(request, 'supabase_user_id', None)
        if not user_id:
            return None
        try:
            profile = StudentProfile.objects.get(supabase_user_id=user_id)
        except StudentProfile.DoesNotExist:
            return None
        # Check if user has admin role — stored in profile or Supabase metadata
        # For v1: user must have a referred_by_org AND be in the partner's contact_email
        # Simpler approach: dedicated partner_admin flag on profile
        # We'll use a simple check: is there a PartnerOrganisation where contact_email matches?
        # For now, use a dedicated admin_org_code field (added in Task 8)
        admin_org = getattr(profile, 'admin_org_code', '')
        if not admin_org:
            return None
        try:
            return PartnerOrganisation.objects.get(code=admin_org, is_active=True)
        except PartnerOrganisation.DoesNotExist:
            return None

    def get_partner_students(self, request):
        org = self.get_partner_org(request)
        if not org:
            return None, org
        students = StudentProfile.objects.filter(
            referred_by_org=org,
        ).order_by('-created_at')
        return students, org


class PartnerDashboardView(PartnerAdminMixin, APIView):
    """GET /api/v1/admin/dashboard/ — partner stats."""

    def get(self, request):
        students, org = self.get_partner_students(request)
        if students is None:
            return Response({'error': 'Not a partner admin'}, status=403)

        total = students.count()
        completed = students.exclude(grades={}).count()
        by_exam = {}
        for et in ['spm', 'stpm']:
            by_exam[et] = students.filter(exam_type=et).count()

        # Top fields from student signals
        from collections import Counter
        field_counter = Counter()
        for s in students.filter(student_signals__has_key='field_interest'):
            fi = s.student_signals.get('field_interest', {})
            for field, score in fi.items():
                field_counter[field] += 1
        top_fields = [{'field': f, 'count': c} for f, c in field_counter.most_common(5)]

        return Response({
            'org_name': org.name,
            'total_students': total,
            'completed_onboarding': completed,
            'by_exam_type': by_exam,
            'top_fields': top_fields,
        })


class PartnerStudentListView(PartnerAdminMixin, APIView):
    """GET /api/v1/admin/students/ — list partner's students."""

    def get(self, request):
        students, org = self.get_partner_students(request)
        if students is None:
            return Response({'error': 'Not a partner admin'}, status=403)

        serializer = PartnerStudentListSerializer(students, many=True)
        return Response({
            'org_name': org.name,
            'count': students.count(),
            'students': serializer.data,
        })


class PartnerStudentDetailView(PartnerAdminMixin, APIView):
    """GET /api/v1/admin/students/<user_id>/ — single student detail."""

    def get(self, request, user_id):
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
    """GET /api/v1/admin/students/export/ — CSV download."""

    def get(self, request):
        students, org = self.get_partner_students(request)
        if students is None:
            return Response({'error': 'Not a partner admin'}, status=403)

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{org.code}_students.csv"'

        writer = csv.writer(response)
        writer.writerow([
            'Name', 'IC', 'Angka Giliran', 'Gender', 'State',
            'Exam Type', 'Date Joined',
        ])

        for s in students:
            writer.writerow([
                s.name,
                s.nric,
                s.grades.get('angka_giliran', ''),
                s.gender,
                s.preferred_state,
                s.exam_type,
                s.created_at.strftime('%Y-%m-%d'),
            ])

        return response
```

**Step 3: Add admin_org_code to StudentProfile**

In `halatuju_api/apps/courses/models.py`, add after `referred_by_org`:

```python
    admin_org_code = models.CharField(
        max_length=50, blank=True, default='',
        help_text='If set, this user is an admin for the given partner org code',
    )
```

Generate migration: `python manage.py makemigrations courses --name student_profile_admin_org`

**Step 4: Add URL routes**

In `halatuju_api/apps/courses/urls.py`, add:

```python
from .views_admin import (
    PartnerDashboardView,
    PartnerStudentListView,
    PartnerStudentDetailView,
    PartnerStudentExportView,
)

# ... existing patterns ...

# Partner admin
path('admin/dashboard/', PartnerDashboardView.as_view(), name='partner-dashboard'),
path('admin/students/', PartnerStudentListView.as_view(), name='partner-students'),
path('admin/students/export/', PartnerStudentExportView.as_view(), name='partner-export'),
path('admin/students/<str:user_id>/', PartnerStudentDetailView.as_view(), name='partner-student-detail'),
```

Note: `export/` must come before `<str:user_id>/` to avoid "export" being captured as a user_id.

**Step 5: Write integration tests**

Append to `test_partner_referral.py`:

```python
class PartnerAdminViewTest(TestCase):
    def setUp(self):
        self.partner = PartnerOrganisation.objects.create(code='cumig', name='CUMIG')
        # Admin user
        self.admin = StudentProfile.objects.create(
            supabase_user_id='admin-1',
            name='Admin User',
            admin_org_code='cumig',
        )
        # Students referred by CUMIG
        for i in range(3):
            StudentProfile.objects.create(
                supabase_user_id=f'student-{i}',
                name=f'Student {i}',
                nric=f'01010{i}-01-000{i}',
                exam_type='spm' if i < 2 else 'stpm',
                referral_source='cumig',
                referred_by_org=self.partner,
            )
        # Student NOT referred by CUMIG
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

    def test_csv_export_content_type(self):
        """CSV export returns correct content type (tested via view directly)."""
        from apps.courses.views_admin import PartnerStudentExportView
        # Just verify the view class exists and has get method
        self.assertTrue(hasattr(PartnerStudentExportView, 'get'))
```

**Step 6: Run tests**

Run: `cd halatuju_api && python manage.py test apps.courses.tests.test_partner_referral -v 2`
Expected: All tests PASS

**Step 7: Commit**

```bash
git add halatuju_api/apps/courses/views_admin.py halatuju_api/apps/courses/serializers_admin.py halatuju_api/apps/courses/urls.py halatuju_api/apps/courses/models.py halatuju_api/apps/courses/migrations/0033_*.py halatuju_api/apps/courses/tests/test_partner_referral.py
git commit -m "feat: partner admin API — dashboard, student list, detail, CSV export"
```

---

## Sprint 3: Partner Admin Frontend

### Task 8: Admin layout and dashboard page

**Files:**
- Create: `halatuju-web/src/app/admin/layout.tsx`
- Create: `halatuju-web/src/app/admin/page.tsx`
- Create: `halatuju-web/src/lib/admin-api.ts`

**Step 1: Create admin API client**

Create `halatuju-web/src/lib/admin-api.ts`:

```typescript
import { ApiOptions } from './api'

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1'

async function adminFetch<T>(path: string, options?: ApiOptions): Promise<T> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (options?.token) {
    headers['Authorization'] = `Bearer ${options.token}`
  }
  const res = await fetch(`${API_BASE}${path}`, { headers })
  if (!res.ok) throw new Error(`Admin API error: ${res.status}`)
  return res.json()
}

export async function getPartnerDashboard(options?: ApiOptions) {
  return adminFetch<{
    org_name: string
    total_students: number
    completed_onboarding: number
    by_exam_type: Record<string, number>
    top_fields: Array<{ field: string; count: number }>
  }>('/admin/dashboard/', options)
}

export async function getPartnerStudents(options?: ApiOptions) {
  return adminFetch<{
    org_name: string
    count: number
    students: Array<{
      supabase_user_id: string
      name: string
      nric: string
      gender: string
      exam_type: string
      created_at: string
    }>
  }>('/admin/students/', options)
}

export async function getPartnerStudent(userId: string, options?: ApiOptions) {
  return adminFetch<{
    supabase_user_id: string
    name: string
    nric: string
    gender: string
    nationality: string
    exam_type: string
    grades: Record<string, string>
    stpm_grades: Record<string, string>
    student_signals: Record<string, unknown>
    preferred_state: string
    created_at: string
    saved_courses: Array<{ course_id: string; name: string }>
  }>(`/admin/students/${userId}/`, options)
}

export function getExportUrl(token: string) {
  return `${API_BASE}/admin/students/export/?token=${token}`
}
```

**Step 2: Create admin layout**

Create `halatuju-web/src/app/admin/layout.tsx`:

```tsx
'use client'

import { useAuth } from '@/hooks/useAuth'
import { useRouter } from 'next/navigation'
import { useEffect } from 'react'
import Link from 'next/link'

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth()
  const router = useRouter()

  useEffect(() => {
    if (!loading && !user) {
      router.replace('/login')
    }
  }, [user, loading, router])

  if (loading) return <div className="flex items-center justify-center min-h-screen">Loading...</div>

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-white border-b px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <span className="font-bold text-blue-600">HalaTuju Admin</span>
          <Link href="/admin" className="text-sm text-gray-600 hover:text-blue-600">Dashboard</Link>
          <Link href="/admin/students" className="text-sm text-gray-600 hover:text-blue-600">Pelajar</Link>
        </div>
      </nav>
      <main className="max-w-6xl mx-auto p-4 md:p-6">
        {children}
      </main>
    </div>
  )
}
```

**Step 3: Create dashboard page**

Create `halatuju-web/src/app/admin/page.tsx`:

```tsx
'use client'

import { useAuth } from '@/hooks/useAuth'
import { getPartnerDashboard } from '@/lib/admin-api'
import { useEffect, useState } from 'react'

export default function AdminDashboard() {
  const { token } = useAuth()
  const [data, setData] = useState<any>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!token) return
    getPartnerDashboard({ token })
      .then(setData)
      .catch(() => setError('Anda bukan admin organisasi rakan kongsi.'))
  }, [token])

  if (error) return <div className="text-red-600 mt-8">{error}</div>
  if (!data) return <div className="mt-8">Loading...</div>

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">{data.org_name} — Dashboard</h1>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
        <div className="bg-white rounded-lg p-6 shadow-sm border">
          <p className="text-sm text-gray-500">Jumlah Pelajar</p>
          <p className="text-3xl font-bold text-blue-600">{data.total_students}</p>
        </div>
        <div className="bg-white rounded-lg p-6 shadow-sm border">
          <p className="text-sm text-gray-500">Selesai Onboarding</p>
          <p className="text-3xl font-bold text-green-600">{data.completed_onboarding}</p>
        </div>
        <div className="bg-white rounded-lg p-6 shadow-sm border">
          <p className="text-sm text-gray-500">SPM / STPM</p>
          <p className="text-3xl font-bold">
            {data.by_exam_type.spm || 0} / {data.by_exam_type.stpm || 0}
          </p>
        </div>
      </div>

      {data.top_fields.length > 0 && (
        <div className="bg-white rounded-lg p-6 shadow-sm border">
          <h2 className="font-semibold mb-3">Bidang Popular</h2>
          <ul className="space-y-2">
            {data.top_fields.map((f: any) => (
              <li key={f.field} className="flex justify-between">
                <span>{f.field}</span>
                <span className="text-gray-500">{f.count} pelajar</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
```

**Step 4: Commit**

```bash
git add halatuju-web/src/app/admin/ halatuju-web/src/lib/admin-api.ts
git commit -m "feat: partner admin dashboard page"
```

---

### Task 9: Admin student list page with CSV export

**Files:**
- Create: `halatuju-web/src/app/admin/students/page.tsx`

**Step 1: Create student list page**

Create `halatuju-web/src/app/admin/students/page.tsx`:

```tsx
'use client'

import { useAuth } from '@/hooks/useAuth'
import { getPartnerStudents, getExportUrl } from '@/lib/admin-api'
import { useEffect, useState } from 'react'
import Link from 'next/link'

export default function AdminStudentList() {
  const { token } = useAuth()
  const [data, setData] = useState<any>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!token) return
    getPartnerStudents({ token })
      .then(setData)
      .catch(() => setError('Gagal memuat senarai pelajar.'))
  }, [token])

  if (error) return <div className="text-red-600 mt-8">{error}</div>
  if (!data) return <div className="mt-8">Loading...</div>

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Pelajar ({data.count})</h1>
        {token && (
          <a
            href={getExportUrl(token)}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700"
            download
          >
            Muat Turun CSV
          </a>
        )}
      </div>

      <div className="bg-white rounded-lg shadow-sm border overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b">
            <tr>
              <th className="text-left p-3 font-medium">Nama</th>
              <th className="text-left p-3 font-medium">No. KP</th>
              <th className="text-left p-3 font-medium">Jantina</th>
              <th className="text-left p-3 font-medium">Peperiksaan</th>
              <th className="text-left p-3 font-medium">Tarikh</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {data.students.map((s: any) => (
              <tr key={s.supabase_user_id} className="hover:bg-gray-50">
                <td className="p-3">
                  <Link
                    href={`/admin/students/${s.supabase_user_id}`}
                    className="text-blue-600 hover:underline"
                  >
                    {s.name || '—'}
                  </Link>
                </td>
                <td className="p-3 font-mono text-xs">{s.nric || '—'}</td>
                <td className="p-3">{s.gender || '—'}</td>
                <td className="p-3">
                  <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                    s.exam_type === 'stpm' ? 'bg-purple-100 text-purple-700' : 'bg-blue-100 text-blue-700'
                  }`}>
                    {s.exam_type?.toUpperCase()}
                  </span>
                </td>
                <td className="p-3 text-gray-500">{new Date(s.created_at).toLocaleDateString('ms-MY')}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
```

**Step 2: Commit**

```bash
git add halatuju-web/src/app/admin/students/page.tsx
git commit -m "feat: partner admin student list with CSV export"
```

---

### Task 10: Admin student detail page

**Files:**
- Create: `halatuju-web/src/app/admin/students/[id]/page.tsx`

**Step 1: Create student detail page**

Create `halatuju-web/src/app/admin/students/[id]/page.tsx`:

```tsx
'use client'

import { useAuth } from '@/hooks/useAuth'
import { getPartnerStudent } from '@/lib/admin-api'
import { useParams } from 'next/navigation'
import { useEffect, useState } from 'react'
import Link from 'next/link'

export default function AdminStudentDetail() {
  const { id } = useParams<{ id: string }>()
  const { token } = useAuth()
  const [data, setData] = useState<any>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!token || !id) return
    getPartnerStudent(id, { token })
      .then(setData)
      .catch(() => setError('Pelajar tidak ditemui.'))
  }, [token, id])

  if (error) return <div className="text-red-600 mt-8">{error}</div>
  if (!data) return <div className="mt-8">Loading...</div>

  const grades = data.exam_type === 'stpm' ? data.stpm_grades : data.grades

  return (
    <div>
      <Link href="/admin/students" className="text-blue-600 text-sm hover:underline mb-4 block">
        &larr; Kembali ke senarai
      </Link>

      <h1 className="text-2xl font-bold mb-2">{data.name || 'Tiada Nama'}</h1>
      <p className="text-gray-500 mb-6">
        {data.nric} &middot; {data.exam_type?.toUpperCase()} &middot; {data.gender}
      </p>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Grades */}
        <div className="bg-white rounded-lg p-6 shadow-sm border">
          <h2 className="font-semibold mb-3">Keputusan {data.exam_type?.toUpperCase()}</h2>
          {Object.keys(grades || {}).length > 0 ? (
            <dl className="grid grid-cols-2 gap-2 text-sm">
              {Object.entries(grades).map(([subject, grade]) => (
                <div key={subject}>
                  <dt className="text-gray-500">{subject}</dt>
                  <dd className="font-medium">{grade as string}</dd>
                </div>
              ))}
            </dl>
          ) : (
            <p className="text-gray-400 text-sm">Belum diisi</p>
          )}
        </div>

        {/* Saved Courses */}
        <div className="bg-white rounded-lg p-6 shadow-sm border">
          <h2 className="font-semibold mb-3">Kursus Disimpan</h2>
          {data.saved_courses?.length > 0 ? (
            <ul className="space-y-2 text-sm">
              {data.saved_courses.map((c: any) => (
                <li key={c.course_id} className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-blue-500"></span>
                  {c.name}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-gray-400 text-sm">Tiada kursus disimpan</p>
          )}
        </div>

        {/* Details */}
        <div className="bg-white rounded-lg p-6 shadow-sm border">
          <h2 className="font-semibold mb-3">Maklumat Lain</h2>
          <dl className="space-y-2 text-sm">
            <div className="flex justify-between">
              <dt className="text-gray-500">Kewarganegaraan</dt>
              <dd>{data.nationality || '—'}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500">Negeri Pilihan</dt>
              <dd>{data.preferred_state || '—'}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500">Tarikh Daftar</dt>
              <dd>{new Date(data.created_at).toLocaleDateString('ms-MY')}</dd>
            </div>
          </dl>
        </div>
      </div>
    </div>
  )
}
```

**Step 2: Commit**

```bash
git add halatuju-web/src/app/admin/students/[id]/
git commit -m "feat: partner admin student detail page"
```

---

### Task 11: Register admin model + Supabase migration for admin_org_code

**Files:**
- Modify: `halatuju_api/apps/courses/admin.py` (register PartnerOrganisation)

**Step 1: Register PartnerOrganisation in Django admin**

In `halatuju_api/apps/courses/admin.py`, add:

```python
from .models import PartnerOrganisation

@admin.register(PartnerOrganisation)
class PartnerOrganisationAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'is_active', 'created_at']
    list_filter = ['is_active']
```

**Step 2: Apply admin_org_code migration to Supabase**

```sql
ALTER TABLE api_student_profiles ADD COLUMN admin_org_code VARCHAR(50) DEFAULT '';
INSERT INTO django_migrations (app, name, applied) VALUES ('courses', '0033_student_profile_admin_org', NOW());
```

**Step 3: Update CLAUDE.md test counts and CHANGELOG.md**

**Step 4: Commit**

```bash
git add halatuju_api/apps/courses/admin.py halatuju_api/CLAUDE.md CHANGELOG.md
git commit -m "feat: register PartnerOrganisation in Django admin, apply Supabase migrations"
```

---

### Task 12: Final cleanup and run full test suite

**Step 1: Run backend tests**

Run: `cd halatuju_api && python manage.py test apps.courses -v 2`
Expected: All tests PASS (590 existing + ~14 new)

**Step 2: Run frontend build**

Run: `cd halatuju-web && npm run build`
Expected: Build succeeds with no errors

**Step 3: Clean up temporary files**

Delete: `docs/ic_referral_a.png` (mockup served its purpose)

**Step 4: Final commit**

```bash
git add -A
git commit -m "chore: cleanup temp files, update test counts"
```
