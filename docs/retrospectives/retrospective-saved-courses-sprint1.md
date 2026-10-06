# Retrospective — Saved Courses Sprint 1 (Backend)

**Date:** 2026-03-15
**Sprint scope:** Dual-FK SavedCourse model, API for both SPM/STPM, Supabase migration, tests

---

## What Was Built

- SavedCourse model with two nullable FKs (`course` + `stpm_course`) and DB check constraint
- SavedCoursesView: POST auto-detects STPM from prefix/course_type, GET returns `course_type` and supports `?qualification=` filter
- SavedCourseDetailView: DELETE/PATCH check both FKs via Q filter
- Supabase migration: new column, nullable course_id, check constraint, partial unique indexes
- Frontend api.ts types updated (course_type, qualification filter, courseType option)
- 17 tests (was 3) covering both course types, filtering, idempotency, constraint enforcement

## What Went Well

- **Prior session did most of the work.** The model, views, migration, and tests had already been committed in the previous session's sprint close. This session verified everything was consistent, applied the Supabase migration, and updated supplementary files.
- **Clean test run first time.** All 17 new tests passed on first run, plus all 408 existing tests. Only fix needed was `query_params` compatibility for raw Django requests in one existing test.
- **Design doc paid off.** Having an approved design doc (`2026-03-15-saved-courses-design.md`) meant zero ambiguity during implementation. Every decision was already made.

## What Went Wrong

1. **Forward reference error in models.py.** Used `StpmCourse` directly instead of `'StpmCourse'` string reference, since SavedCourse is defined before StpmCourse in the file. Root cause: didn't check model ordering before writing the FK. Fix: always use string references for FKs to models defined later in the same file.

2. **Missing Q import in models.py.** The CheckConstraint uses `Q()` objects but the import wasn't added. Root cause: wrote the constraint without checking existing imports. Fix: when adding Django ORM features to a file, verify the import line first.

3. **saveCourse API signature broke existing callers.** Added `courseType` as the second positional parameter, but existing callers passed `{ token }` as the second arg. Root cause: didn't check call sites before changing the signature. Fix: added `courseType` as an optional field inside the existing options object instead. Lesson: always grep for callers before changing function signatures.

## Design Decisions

- **Dual nullable FK (not generic string)**: Referential integrity, cascading deletes, direct JOINs for analytics. Pattern extends cleanly for a third qualification type.
- **Auto-detect STPM from `stpm-*` prefix**: All STPM course IDs follow this convention. Explicit `course_type` param is a fallback for non-standard IDs.
- **`condition` not `check` for CheckConstraint**: Django 5.x deprecated `check=` in favour of `condition=`. Used the new API to avoid deprecation warnings.

## Numbers

| Metric | Before | After |
|--------|--------|-------|
| Tests | 411 | 425 |
| Saved course tests | 3 | 17 |
| Files changed | — | 8 |
| Supabase tables altered | 0 | 1 (saved_courses) |
