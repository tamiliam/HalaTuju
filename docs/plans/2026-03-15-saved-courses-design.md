# Saved Courses Redesign — Design Document

**Date:** 2026-03-15
**Status:** Approved
**Author:** tamiliam + Claude

## Problem

The saved courses system is broken in multiple ways:

1. **STPM courses cannot be saved** — `SavedCourse` model has a FK to `Course` (SPM only). All STPM saves fail with 404.
2. **Detail pages don't pass auth token** — `saveCourse(courseId)` called without `{ token }`, API rejects with 401, error swallowed silently.
3. **Search page hides save entirely** — CourseCard rendered without `onToggleSave` callback, bookmark button never appears.
4. **Detail pages don't load saved state** — always starts as `useState(false)`, never checks backend. A previously saved course shows "Save" instead of "Saved".
5. **No error feedback** — save failures logged to console only, user sees nothing.
6. **No auth gate on detail pages** — clicking Save while logged out doesn't prompt login.

## Goals

- Save works consistently for both SPM and STPM courses across every page
- Login required before saving (auth gate pattern)
- Clear visual indication of saved state (bookmark icon, button text)
- Toast notifications for success/failure
- Admin analytics preserved (which courses popular, applied, offered)
- Future-proof for course comparison feature

## Non-Goals

- Course comparison UI (future sprint)
- Notes field on saved courses (keep column, don't surface)
- Offline/localStorage save (login is prerequisite)

---

## Data Model

### SavedCourse — Two Nullable FKs

```python
class SavedCourse(models.Model):
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name='saved_courses')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, null=True, blank=True)
    stpm_course = models.ForeignKey(StpmCourse, on_delete=models.CASCADE, null=True, blank=True)
    saved_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)
    interest_status = models.CharField(max_length=20, choices=[
        ('interested', 'Interested'),
        ('planning', 'Planning to apply'),
        ('applied', 'Applied'),
        ('got_offer', 'Got offer'),
    ], default='interested')

    class Meta:
        db_table = 'saved_courses'
        constraints = [
            models.CheckConstraint(
                check=(
                    Q(course__isnull=False, stpm_course__isnull=True) |
                    Q(course__isnull=True, stpm_course__isnull=False)
                ),
                name='exactly_one_course_type'
            ),
        ]

    @property
    def course_id_value(self):
        return self.course_id if self.course_id else self.stpm_course_id

    @property
    def course_type(self):
        return 'stpm' if self.stpm_course_id else 'spm'
```

Unique constraints:
- `(student, course)` WHERE `course IS NOT NULL`
- `(student, stpm_course)` WHERE `stpm_course IS NOT NULL`

### Why Two FKs (not generic string)

- Referential integrity — cascading deletes, no orphans
- Admin analytics — `JOIN` queries work directly
- Tabbed UI maps naturally — SPM tab = `course IS NOT NULL`, STPM tab = `stpm_course IS NOT NULL`
- Pattern is clear for a third type (add another nullable FK)

---

## API Changes

### POST /api/v1/saved-courses/

Request:
```json
{ "course_id": "POLY-DIP-044" }
{ "course_id": "stpm-sains-001", "course_type": "stpm" }
```

Logic:
1. If `course_type == 'stpm'` OR `course_id` starts with `stpm-` → look up StpmCourse, save with `stpm_course` FK
2. Otherwise → look up Course, save with `course` FK
3. `get_or_create` for idempotency

### GET /api/v1/saved-courses/

Optional filter: `?qualification=SPM|STPM`

Response adds `course_type`:
```json
{
  "saved_courses": [
    { "course_id": "POLY-DIP-044", "course_type": "spm", "interest_status": "interested", ... },
    { "course_id": "stpm-sains-001", "course_type": "stpm", "interest_status": "planning", ... }
  ]
}
```

Without filter: returns all (for dashboard savedIds loading).
With filter: returns filtered (for tabbed saved page).

### DELETE /api/v1/saved-courses/{course_id}/

Check both FKs when looking up. No other change.

### PATCH /api/v1/saved-courses/{course_id}/

Same — check both FKs.

---

## Frontend Architecture

### Shared Hook: `useSavedCourses()`

Single hook replaces all duplicated save logic:

```typescript
function useSavedCourses() {
  const { token, isAuthenticated, showAuthGate } = useAuth()
  const [savedIds, setSavedIds] = useState<Set<string>>(new Set())

  // Load saved IDs on mount when authenticated
  useEffect(() => {
    if (token) {
      getSavedCourses({ token })
        .then(({ saved_courses }) => setSavedIds(new Set(saved_courses.map(c => c.course_id))))
        .catch(() => {})
    }
  }, [token])

  // Toggle with auth gate + optimistic update + error toast
  const toggleSave = (courseId: string, courseType?: 'spm' | 'stpm') => {
    if (!isAuthenticated) {
      showAuthGate('save', { courseId })
      return
    }
    // optimistic update → API call → revert on error + showToast
  }

  return { savedIds, toggleSave }
}
```

Used by: dashboard, search page, SPM detail page, STPM detail page.

### Visual States

**CourseCard bookmark icon:**
- Not saved: grey outline
- Saved: filled blue

**Detail page button:**
- Not saved: "Save This Course" — primary blue solid
- Saved: "Saved ✓" — green outline
- Hover on saved: "Remove from Saved" — red outline

### Toast Notifications

Small toast component at app layout level:

| Scenario | Message | Type |
|----------|---------|------|
| Save success | "Course saved" | success (green) |
| Remove success | "Course removed from saved" | info (grey) |
| Course not found | "This course is no longer available" | error (red) |
| Network/server error | "Could not save course. Please try again." | error (red) |

### Saved Page — Tabbed

Two tabs matching search page pattern:
- **SPM** tab → `GET /saved-courses/?qualification=SPM`
- **STPM** tab → `GET /saved-courses/?qualification=STPM`

Each tab shows courses with remove / applied / got-offer actions.
Course cards link to correct detail page based on type.

---

## Error Handling & Edge Cases

| Edge Case | Handling |
|-----------|----------|
| Course deleted after saving | Cascading FK delete removes SavedCourse row automatically |
| Double save (race condition) | `get_or_create` is idempotent, returns 201 |
| Navigate between pages | Hook loads savedIds on mount — every page reflects current state |
| Auth token expires | API returns 401, hook shows auth gate |
| Not logged in | Auth gate shown before any save attempt |

---

## Testing

### Backend (additions to test_saved_courses.py)

- Save STPM course → 201, stpm_course FK set, course FK null
- Save SPM course → 201 (existing, preserved)
- List returns both types with `course_type` field
- List with `?qualification=STPM` → only STPM
- Delete STPM saved course
- PATCH interest_status on STPM saved course
- Idempotent save (same course twice → 201, no duplicate)
- Check constraint: both FKs null → rejected
- Check constraint: both FKs set → rejected
- Auto-detect STPM from `stpm-*` prefix

### Frontend (manual verification)

- Save from dashboard CourseCard → bookmark fills blue
- Save from search page CourseCard → bookmark fills blue
- Save from SPM detail page → button changes to "Saved ✓"
- Save from STPM detail page → same
- Saved page SPM tab → correct courses
- Saved page STPM tab → correct courses
- Remove from saved page → course disappears
- Not logged in → auth gate on any save attempt
- Network error → toast shown

---

## Future: Course Comparison

The compare feature will work from the saved list as a selection source. Students select 2-3 saved courses and see them side-by-side (merit, fees, location, duration, WBL, etc.). This design supports that without changes — saved courses store clean FKs that can be joined with full course data.

Two comparison modes anticipated:
1. **Same course, different institutions** — comparing offerings (CourseInstitution rows)
2. **Different courses** — comparing programme attributes side by side
