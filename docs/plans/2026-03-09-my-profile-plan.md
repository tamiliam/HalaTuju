# My Profile Page — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a full `/profile` page with expanded student fields (NRIC, address, phone, family income, siblings) and course interests with status tags, accessible from the nav bar.

**Architecture:** Backend-first approach. Add new fields to `StudentProfile` and `SavedCourse` Django models via migration, extend the existing profile and saved-courses API endpoints to handle them, then build the frontend `/profile` page that reads/writes via those APIs. Nav bar updated to link to the new page.

**Tech Stack:** Django REST (backend), Next.js 14 + Tailwind (frontend), Supabase PostgreSQL (database), existing JWT auth middleware.

**Design doc:** `docs/plans/2026-03-09-my-profile-design.md`
**Stitch mockup:** [Preview](https://stitch.withgoogle.com/preview/13238979537238863747?node-id=8a5b67ac384143b18d5c2a445e8d5df1)

---

## Task 1: Backend — Add new fields to StudentProfile model

**Files:**
- Modify: `halatuju_api/apps/courses/models.py:332-383` (StudentProfile)
- Create: `halatuju_api/apps/courses/migrations/0010_expand_student_profile.py`

**Step 1: Write the failing test**

Create test in `halatuju_api/apps/courses/tests/test_profile_fields.py`:

```python
"""Tests for expanded StudentProfile fields."""
import pytest
from apps.courses.models import StudentProfile


@pytest.mark.django_db
class TestProfileNewFields:

    def test_profile_has_nric_field(self):
        p = StudentProfile.objects.create(
            supabase_user_id='test-nric',
            nric='010203-14-1234',
        )
        p.refresh_from_db()
        assert p.nric == '010203-14-1234'

    def test_profile_has_address_field(self):
        p = StudentProfile.objects.create(
            supabase_user_id='test-addr',
            address='123 Jalan Merdeka, Petaling Jaya',
        )
        p.refresh_from_db()
        assert p.address == '123 Jalan Merdeka, Petaling Jaya'

    def test_profile_has_phone_field(self):
        p = StudentProfile.objects.create(
            supabase_user_id='test-phone',
            phone='+60123456789',
        )
        p.refresh_from_db()
        assert p.phone == '+60123456789'

    def test_profile_has_family_income_field(self):
        p = StudentProfile.objects.create(
            supabase_user_id='test-income',
            family_income='RM1,001-3,000',
        )
        p.refresh_from_db()
        assert p.family_income == 'RM1,001-3,000'

    def test_profile_has_siblings_field(self):
        p = StudentProfile.objects.create(
            supabase_user_id='test-siblings',
            siblings=3,
        )
        p.refresh_from_db()
        assert p.siblings == 3

    def test_new_fields_default_blank(self):
        p = StudentProfile.objects.create(supabase_user_id='test-defaults')
        p.refresh_from_db()
        assert p.nric == ''
        assert p.address == ''
        assert p.phone == ''
        assert p.family_income == ''
        assert p.siblings is None
```

**Step 2: Run test to verify it fails**

Run: `cd halatuju_api && python -m pytest apps/courses/tests/test_profile_fields.py -v`
Expected: FAIL — fields don't exist yet.

**Step 3: Add fields to StudentProfile model**

In `halatuju_api/apps/courses/models.py`, add after the `school` field (line 355):

```python
    # Contact & location
    address = models.TextField(blank=True, default='',
                               help_text="Home address")
    phone = models.CharField(max_length=20, blank=True, default='',
                             help_text="Phone number")

    # Identity (Lentera longitudinal tracking)
    nric = models.CharField(max_length=14, blank=True, default='',
                            help_text="NRIC: XXXXXX-XX-XXXX")

    # Family background
    family_income = models.CharField(max_length=30, blank=True, default='',
                                     help_text="Family monthly income range")
    siblings = models.IntegerField(null=True, blank=True,
                                   help_text="Number of siblings")
```

**Step 4: Create migration**

Run: `cd halatuju_api && python manage.py makemigrations courses --name expand_student_profile`

**Step 5: Apply migration and run tests**

Run: `cd halatuju_api && python manage.py migrate && python -m pytest apps/courses/tests/test_profile_fields.py -v`
Expected: All 6 tests PASS.

**Step 6: Commit**

```bash
git add halatuju_api/apps/courses/models.py halatuju_api/apps/courses/migrations/0010_expand_student_profile.py halatuju_api/apps/courses/tests/test_profile_fields.py
git commit -m "feat: add NRIC, address, phone, income, siblings to StudentProfile"
```

---

## Task 2: Backend — Add interest_status to SavedCourse model

**Files:**
- Modify: `halatuju_api/apps/courses/models.py:385-407` (SavedCourse)
- Create: `halatuju_api/apps/courses/migrations/0011_add_interest_status.py`

**Step 1: Write the failing test**

Add to `halatuju_api/apps/courses/tests/test_profile_fields.py`:

```python
from apps.courses.models import SavedCourse, Course


@pytest.mark.django_db
class TestSavedCourseInterestStatus:

    def _make_course(self):
        return Course.objects.create(
            course_id='TEST-001',
            course='Test Course',
            level='Diploma',
        )

    def test_default_status_is_interested(self):
        profile = StudentProfile.objects.create(supabase_user_id='test-status')
        course = self._make_course()
        sc = SavedCourse.objects.create(student=profile, course=course)
        sc.refresh_from_db()
        assert sc.interest_status == 'interested'

    def test_can_set_planning_status(self):
        profile = StudentProfile.objects.create(supabase_user_id='test-planning')
        course = self._make_course()
        sc = SavedCourse.objects.create(
            student=profile, course=course, interest_status='planning'
        )
        sc.refresh_from_db()
        assert sc.interest_status == 'planning'

    def test_can_set_got_offer_status(self):
        profile = StudentProfile.objects.create(supabase_user_id='test-offer')
        course = self._make_course()
        sc = SavedCourse.objects.create(
            student=profile, course=course, interest_status='got_offer'
        )
        sc.refresh_from_db()
        assert sc.interest_status == 'got_offer'
```

**Step 2: Run test to verify it fails**

Run: `cd halatuju_api && python -m pytest apps/courses/tests/test_profile_fields.py::TestSavedCourseInterestStatus -v`
Expected: FAIL — field doesn't exist.

**Step 3: Add interest_status to SavedCourse**

In `halatuju_api/apps/courses/models.py`, add after `notes` field (line 399):

```python
    interest_status = models.CharField(
        max_length=20,
        choices=[
            ('interested', 'Interested'),
            ('planning', 'Planning to apply'),
            ('applied', 'Applied'),
            ('got_offer', 'Got offer'),
        ],
        default='interested',
        help_text="Student's self-reported interest level"
    )
```

**Step 4: Create and apply migration**

Run: `cd halatuju_api && python manage.py makemigrations courses --name add_interest_status && python manage.py migrate`

**Step 5: Run tests**

Run: `cd halatuju_api && python -m pytest apps/courses/tests/test_profile_fields.py -v`
Expected: All 9 tests PASS.

**Step 6: Commit**

```bash
git add halatuju_api/apps/courses/models.py halatuju_api/apps/courses/migrations/0011_add_interest_status.py halatuju_api/apps/courses/tests/test_profile_fields.py
git commit -m "feat: add interest_status field to SavedCourse model"
```

---

## Task 3: Backend — Extend profile and saved-courses API endpoints

**Files:**
- Modify: `halatuju_api/apps/courses/views.py:609-678` (ProfileView, ProfileSyncView)
- Modify: `halatuju_api/apps/courses/views.py:564-606` (SavedCoursesView, SavedCourseDetailView)

**Step 1: Write failing API tests**

Add to `halatuju_api/apps/courses/tests/test_profile_fields.py`:

```python
from django.test import RequestFactory
from apps.courses.views import ProfileView, SavedCoursesView, SavedCourseDetailView


def _auth_request(method, data=None, user_id='api-test-user'):
    """Create a fake authenticated request."""
    factory = RequestFactory()
    if method == 'GET':
        request = factory.get('/api/v1/profile/')
    elif method == 'PUT':
        request = factory.put(
            '/api/v1/profile/',
            data=data,
            content_type='application/json',
        )
    elif method == 'PATCH':
        request = factory.patch(
            '/api/v1/saved-courses/TEST-001/',
            data=data,
            content_type='application/json',
        )
    request.user_id = user_id
    request.data = data or {}
    return request


@pytest.mark.django_db
class TestProfileAPINewFields:

    def test_get_profile_returns_new_fields(self):
        StudentProfile.objects.create(
            supabase_user_id='api-test-user',
            nric='010203-14-1234',
            address='Jalan Test',
            phone='+60123456789',
            family_income='RM1,001-3,000',
            siblings=3,
        )
        request = _auth_request('GET')
        response = ProfileView().get(request)
        assert response.status_code == 200
        assert response.data['nric'] == '010203-14-1234'
        assert response.data['address'] == 'Jalan Test'
        assert response.data['phone'] == '+60123456789'
        assert response.data['family_income'] == 'RM1,001-3,000'
        assert response.data['siblings'] == 3

    def test_put_profile_updates_new_fields(self):
        StudentProfile.objects.create(supabase_user_id='api-test-user')
        request = _auth_request('PUT', data={
            'nric': '010203-14-1234',
            'address': 'New Address',
            'phone': '+60199999999',
            'family_income': 'RM3,001-5,000',
            'siblings': 5,
        })
        response = ProfileView().put(request)
        assert response.status_code == 200
        p = StudentProfile.objects.get(supabase_user_id='api-test-user')
        assert p.nric == '010203-14-1234'
        assert p.siblings == 5


@pytest.mark.django_db
class TestSavedCoursesAPIInterestStatus:

    def _setup(self, user_id='saved-api-user'):
        profile = StudentProfile.objects.create(supabase_user_id=user_id)
        course = Course.objects.create(
            course_id='TEST-001', course='Test Course', level='Diploma'
        )
        SavedCourse.objects.create(student=profile, course=course)
        return profile, course

    def test_get_saved_courses_includes_interest_status(self):
        self._setup()
        factory = RequestFactory()
        request = factory.get('/api/v1/saved-courses/')
        request.user_id = 'saved-api-user'
        response = SavedCoursesView().get(request)
        assert response.status_code == 200
        assert 'interest_status' in response.data['saved_courses'][0]
        assert response.data['saved_courses'][0]['interest_status'] == 'interested'

    def test_patch_saved_course_updates_status(self):
        self._setup(user_id='patch-user')
        factory = RequestFactory()
        request = factory.patch(
            '/api/v1/saved-courses/TEST-001/',
            data={'interest_status': 'planning'},
            content_type='application/json',
        )
        request.user_id = 'patch-user'
        request.data = {'interest_status': 'planning'}
        response = SavedCourseDetailView().patch(request, course_id='TEST-001')
        assert response.status_code == 200
        sc = SavedCourse.objects.get(student_id='patch-user', course_id='TEST-001')
        assert sc.interest_status == 'planning'
```

**Step 2: Run tests to verify they fail**

Run: `cd halatuju_api && python -m pytest apps/courses/tests/test_profile_fields.py::TestProfileAPINewFields -v && python -m pytest apps/courses/tests/test_profile_fields.py::TestSavedCoursesAPIInterestStatus -v`
Expected: FAIL — new fields not in API response, PATCH method doesn't exist.

**Step 3: Update ProfileView GET to return new fields**

In `views.py:622-632`, update the response dict to include:

```python
        return Response({
            'grades': profile.grades,
            'gender': profile.gender,
            'nationality': profile.nationality,
            'colorblind': profile.colorblind,
            'disability': profile.disability,
            'student_signals': profile.student_signals,
            'preferred_state': profile.preferred_state,
            'name': profile.name,
            'school': profile.school,
            'nric': profile.nric,
            'address': profile.address,
            'phone': profile.phone,
            'family_income': profile.family_income,
            'siblings': profile.siblings,
        })
```

**Step 4: Update ProfileView PUT and ProfileSyncView to accept new fields**

In `views.py:640-642`, expand the field list:

```python
        for field in ['grades', 'gender', 'nationality', 'colorblind',
                      'disability', 'student_signals', 'preferred_state',
                      'name', 'school', 'nric', 'address', 'phone',
                      'family_income', 'siblings']:
```

Same change in `ProfileSyncView` at line 665-668.

**Step 5: Update SavedCoursesView GET to include interest_status**

In `views.py:572-576`, change GET to return interest_status per saved course:

```python
    def get(self, request):
        saved = SavedCourse.objects.filter(
            student_id=request.user_id
        ).select_related('course')
        data = []
        for sc in saved:
            course_data = CourseSerializer(sc.course).data
            course_data['interest_status'] = sc.interest_status
            data.append(course_data)
        return Response({'saved_courses': data})
```

**Step 6: Add PATCH method to SavedCourseDetailView**

In `views.py`, add to `SavedCourseDetailView` (after `delete` method):

```python
    def patch(self, request, course_id):
        try:
            sc = SavedCourse.objects.get(
                student_id=request.user_id,
                course_id=course_id,
            )
        except SavedCourse.DoesNotExist:
            return Response({'error': 'Not found'}, status=404)

        status = request.data.get('interest_status')
        valid = ['interested', 'planning', 'applied', 'got_offer']
        if status and status in valid:
            sc.interest_status = status
            sc.save(update_fields=['interest_status'])
            return Response({'message': 'Status updated'})
        return Response({'error': 'Invalid status'}, status=400)
```

**Step 7: Run all tests**

Run: `cd halatuju_api && python -m pytest apps/courses/tests/test_profile_fields.py -v`
Expected: All tests PASS.

Run: `cd halatuju_api && python -m pytest apps/courses/tests/ -v`
Expected: No regressions. 164+ pass (9 pre-existing JWT failures OK).

**Step 8: Commit**

```bash
git add halatuju_api/apps/courses/views.py halatuju_api/apps/courses/tests/test_profile_fields.py
git commit -m "feat: extend profile and saved-courses API for new fields + interest status"
```

---

## Task 4: Frontend — Create /profile page

**Files:**
- Create: `halatuju-web/src/app/profile/page.tsx`

**Step 1: Create the profile page**

Create `halatuju-web/src/app/profile/page.tsx`. This is a client component that:

1. Requires auth (redirect to `/login` if not authenticated)
2. On mount, fetches `GET /api/v1/profile/` and `GET /api/v1/saved-courses/`
3. Populates form fields from profile response
4. Shows saved courses with interest_status dropdowns
5. On "Save Changes", sends `PUT /api/v1/profile/` with all profile fields
6. On status change, sends `PATCH /api/v1/saved-courses/<course_id>/` per course
7. On remove, sends `DELETE /api/v1/saved-courses/<course_id>/`

Key sections matching the Stitch design:
- **Personal Details** card: name, nric, gender toggle, nationality toggle
- **Contact & Location** card: state dropdown, address textarea, phone input
- **Family & Background** card: income dropdown, siblings number, special needs checkboxes
- **My Course Interests** card: saved courses list with status pill dropdowns

Use the same design patterns as the exam-type page redesign:
- `bg-[#f8fafc]` page background
- `bg-white border border-gray-100 rounded-xl shadow-sm` cards
- Gradient icon boxes for section headers (like exam-type page)
- `border-gray-300 rounded-lg focus:border-primary-500 focus:ring-1 focus:ring-primary-500` inputs

Malaysian states constant: reuse from `onboarding/profile/page.tsx`.

Income ranges: `['< RM1,000', 'RM1,001 – RM3,000', 'RM3,001 – RM5,000', 'RM5,001 – RM10,000', '> RM10,000']`

Status pill colours:
- interested: `bg-gray-100 text-gray-600`
- planning: `bg-blue-100 text-blue-700`
- applied: `bg-amber-100 text-amber-700`
- got_offer: `bg-green-100 text-green-700`

**Step 2: Verify it renders**

Run dev server: `cd halatuju-web && npm run dev`
Navigate to `http://localhost:3000/profile`
Expected: Page renders with all 4 sections. Form fields load from API.

**Step 3: Commit**

```bash
git add halatuju-web/src/app/profile/page.tsx
git commit -m "feat: add /profile page with expanded fields and course interests"
```

---

## Task 5: Frontend — Update navigation

**Files:**
- Modify: `halatuju-web/src/components/AppHeader.tsx:36-40` (navLinks array)
- Modify: `halatuju-web/src/components/AppHeader.tsx:120-129` (profile dropdown "My Profile" link)
- Modify: `halatuju-web/src/components/AppHeader.tsx:215-221` (mobile "My Profile" link)

**Step 1: Add "My Profile" to nav links**

In `AppHeader.tsx:36-40`, add profile to navLinks:

```typescript
  const navLinks = [
    { href: '/dashboard', label: t('common.dashboard') },
    { href: '/search', label: t('search.nav') },
    { href: '/saved', label: t('common.saved') },
    { href: '/profile', label: t('header.myProfile') },
  ]
```

**Step 2: Update profile dropdown link**

In `AppHeader.tsx:120-129`, change the "My Profile" link `href` from `/onboarding/grades` to `/profile`:

```tsx
<Link
    href="/profile"
    className="flex items-center gap-3 px-4 py-2 text-sm text-gray-700 hover:bg-gray-50"
    onClick={() => setProfileOpen(false)}
>
```

**Step 3: Update mobile menu link**

In `AppHeader.tsx:215-221`, change mobile "My Profile" link `href` from `/onboarding/grades` to `/profile`:

```tsx
<Link
    href="/profile"
    className="block px-3 py-2.5 rounded-lg text-sm text-gray-600 hover:bg-gray-50"
    onClick={() => setMobileOpen(false)}
>
```

**Step 4: Verify navigation**

Navigate to `http://localhost:3000/dashboard`
Expected: "My Profile" appears in top nav bar. Clicking it goes to `/profile`. Active state highlights correctly. Profile dropdown also links to `/profile`. Mobile menu links to `/profile`.

**Step 5: Commit**

```bash
git add halatuju-web/src/components/AppHeader.tsx
git commit -m "feat: add My Profile to nav bar and update dropdown links"
```

---

## Task 6: Add i18n keys for profile page

**Files:**
- Modify: i18n translation files (check `halatuju-web/src/lib/i18n.ts` or equivalent for EN/BM/TA keys)

**Step 1: Identify i18n file location**

Check where translations are stored. Look for existing keys like `header.myProfile`.

**Step 2: Add new keys**

Add translation keys for:
- `profile.title` — "My Profile" / "Profil Saya" / "என் சுயவிவரம்"
- `profile.subtitle` — "Manage your personal information and course interests"
- `profile.personalDetails` — "Personal Details"
- `profile.contactLocation` — "Contact & Location"
- `profile.familyBackground` — "Family & Background"
- `profile.courseInterests` — "My Course Interests"
- `profile.nric` — "NRIC"
- `profile.address` — "Address"
- `profile.phone` — "Phone Number"
- `profile.familyIncome` — "Family Monthly Income"
- `profile.siblings` — "Number of Siblings"
- `profile.saveChanges` — "Save Changes"
- `profile.lastSaved` — "Last saved"
- `profile.noCourses` — "Save courses from the dashboard to track them here"
- `profile.status.interested` — "Interested"
- `profile.status.planning` — "Planning to apply"
- `profile.status.applied` — "Applied"
- `profile.status.got_offer` — "Got offer"

**Step 3: Commit**

```bash
git add halatuju-web/src/lib/i18n.ts
git commit -m "feat: add i18n keys for profile page (EN/BM/TA)"
```

---

## Task 7: Run full test suite and verify

**Step 1: Run backend tests**

Run: `cd halatuju_api && python -m pytest apps/courses/tests/ -v`
Expected: 173+ tests collected, 170+ pass (9 pre-existing JWT failures OK). Golden master = 8280.

**Step 2: Run frontend build check**

Run: `cd halatuju-web && npm run build`
Expected: Build succeeds with no errors.

**Step 3: Manual verification**

1. Open `http://localhost:3000/profile` — all 4 sections render
2. Fill in fields, click Save — data persists on page refresh
3. Change a course interest status — pill colour changes, persists
4. Remove a course — disappears from list
5. Check nav — "My Profile" link active on profile page
6. Check mobile menu — same behaviour

**Step 4: Final commit**

```bash
git add -A
git commit -m "feat: My Profile page — expanded student fields, course interests, nav integration"
```

---

## Supabase Post-Migration Checklist

After applying migrations to production:

1. Run Supabase Security Advisor — ensure 0 errors
2. New columns (`nric`, `address`, `phone`, `family_income`, `siblings`, `interest_status`) are on existing RLS-protected tables, so no new RLS policies needed
3. Verify with: `SELECT * FROM api_student_profiles LIMIT 1` — new columns should appear with defaults

---

## Summary

| Task | What | Files | Tests |
|------|------|-------|-------|
| 1 | StudentProfile new fields | models.py, migration 0010 | 6 |
| 2 | SavedCourse interest_status | models.py, migration 0011 | 3 |
| 3 | API endpoint extensions | views.py | 4 |
| 4 | /profile page (frontend) | profile/page.tsx | Manual |
| 5 | Nav update | AppHeader.tsx | Manual |
| 6 | i18n keys | i18n.ts | Manual |
| 7 | Full test suite verification | — | All |

**Estimated new tests:** 13 automated + manual UI verification
