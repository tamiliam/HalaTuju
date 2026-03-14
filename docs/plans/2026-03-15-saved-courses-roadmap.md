# Saved Courses Redesign — Sprint Roadmap

**Design doc:** `docs/plans/2026-03-15-saved-courses-design.md`
**Total sprints:** 2
**Rationale:** Backend and frontend are cleanly separable. Sprint 1 makes the API work for both course types with full test coverage. Sprint 2 fixes every frontend surface and adds the tabbed saved page. Each sprint is ~10 files, well within budget.

---

## Sprint 1: Backend — Dual-FK Model + API (Medium complexity)

**Goal:** SavedCourse supports both SPM and STPM courses. API handles save/list/delete/patch for both types.

**Scope:**
- `halatuju_api/apps/courses/models.py` — make `course` FK nullable, add `stpm_course` FK, check constraint, helper properties
- `halatuju_api/apps/courses/migrations/0023_*.py` — Django migration for new FK + constraint
- Supabase SQL — ALTER TABLE, add column, check constraint, partial unique indexes, backfill existing rows
- `halatuju_api/apps/courses/views.py` — update SavedCoursesView (POST: auto-detect type, GET: return course_type + qualification filter) and SavedCourseDetailView (DELETE/PATCH: check both FKs)
- `halatuju_api/apps/courses/tests/test_saved_courses.py` — expand from 3 to ~13 tests (STPM save, list both types, filter, delete, patch, constraints, idempotent, auto-detect)

**Acceptance criteria:**
- `POST /saved-courses/` with STPM course_id returns 201
- `GET /saved-courses/` returns both SPM and STPM saves with `course_type` field
- `GET /saved-courses/?qualification=STPM` filters correctly
- `DELETE` and `PATCH` work for both types
- Check constraint rejects both-null and both-set
- All existing tests still pass (no regression)
- 420+ tests passing

**Key files (~8):**
1. models.py
2. views.py
3. migration file
4. Supabase SQL (via MCP)
5. test_saved_courses.py
6. test_profile_fields.py (update if affected)
7. api.ts (add course_type to types)
8. CHANGELOG.md

---

## Sprint 2: Frontend — Shared Hook, All Surfaces, Tabbed Saved Page (Medium complexity)

**Goal:** Save works on every page with correct visual states, auth gating, and error toasts.

**Scope:**
- `halatuju-web/src/hooks/useSavedCourses.ts` — new shared hook (load savedIds, toggleSave with auth gate + optimistic update + toast)
- `halatuju-web/src/components/Toast.tsx` — new toast notification component
- `halatuju-web/src/app/layout.tsx` or equivalent — mount toast provider
- `halatuju-web/src/app/dashboard/page.tsx` — replace inline save logic with `useSavedCourses()` hook
- `halatuju-web/src/app/search/page.tsx` — add hook, pass `isSaved` and `onToggleSave` to CourseCard
- `halatuju-web/src/app/course/[id]/page.tsx` — replace broken handleSave with hook, add visual states (green "Saved ✓" / red "Remove from Saved" on hover)
- `halatuju-web/src/app/stpm/[id]/page.tsx` — same as above
- `halatuju-web/src/app/saved/page.tsx` — add SPM/STPM tabs, use qualification filter, link to correct detail page per type
- `halatuju-web/src/lib/api.ts` — update saveCourse to accept course_type, update SavedCourse type

**Acceptance criteria:**
- Dashboard: bookmark works as before (no regression), uses shared hook
- Search page: bookmark icon visible, reflects saved state, toggles correctly
- SPM detail page: button shows "Saved ✓" (green) when saved, "Remove from Saved" (red) on hover, "Save This Course" (blue) when not saved
- STPM detail page: same visual states
- All save attempts show auth gate when not logged in
- Toast shown on success and failure
- Saved page: two tabs (SPM/STPM), correct courses in each, remove/applied/got-offer actions work
- No save logic duplicated — all pages use `useSavedCourses()` hook

**Key files (~10):**
1. hooks/useSavedCourses.ts (new)
2. components/Toast.tsx (new)
3. app/layout.tsx or providers
4. app/dashboard/page.tsx
5. app/search/page.tsx
6. app/course/[id]/page.tsx
7. app/stpm/[id]/page.tsx
8. app/saved/page.tsx
9. lib/api.ts
10. CHANGELOG.md

---

## Risk Notes

- **Sprint 1** has a Supabase schema change (ALTER TABLE on saved_courses). Low risk — table is small, FK addition is non-breaking.
- **Sprint 2** touches many frontend files but each change is small and follows the same pattern (replace inline logic with hook call). Risk is in the visual states — may need Stitch prototype for the detail page button.
- **No dependency on field taxonomy** — these sprints are independent of the planned taxonomy normalisation work.
