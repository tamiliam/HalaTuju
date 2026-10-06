# Retrospective — Subject Key Unification Sprint (2026-03-15)

## What Was Built

Eliminated the SPM subject key fork between frontend and backend. The grades page now sends engine keys (`bm`, `eng`, `math`) directly instead of uppercase frontend keys (`BM`, `BI`, `MAT`). The serializer's `GRADE_KEY_MAP` and `validate_grades` method were removed. `subjects.ts` is now the single source of truth with structured metadata.

## What Went Well

- **Scope investigation saved work.** Initial estimate was 14+ files. Investigation revealed only `grades/page.tsx` used uppercase keys — `subjects.ts` already used backend keys. STPM keys were consistent. Narrowed to 6 files in design, expanded to 10 during implementation.
- **Design-first approach.** The brainstorming session identified the report engine bug (`phys`, `sc`, `add_math` keys) that would have been missed in a narrow fix.
- **Clean extraction.** `SPM_SUBJECTS` array with category metadata eliminates the need to define subjects in multiple places. Adding a subject now touches one place.

## What Went Wrong

1. **Scope undercount in design doc.** Listed 6 files but `views.py` (2 calculate endpoints), `test_api.py` (25 grade dicts), `test_auth.py`, `test_integration.py`, and `test_preu_courses.py` also referenced `GRADE_KEY_MAP` or uppercase keys. Root cause: `grep` for `GRADE_KEY_MAP` and uppercase keys wasn't done during design. Fix: design docs should include a mechanical search for all references before finalising the file list.

2. **`replace_all` doubled a prefix.** Replacing `CORE_SUBJECTS` → `SPM_CORE_SUBJECTS` also hit the import line where it was already `SPM_CORE_SUBJECTS`, creating `SPM_SPM_CORE_SUBJECTS`. Root cause: `replace_all` is a blunt instrument when the replacement string contains the search string. Fix: use targeted edits for rename operations, not `replace_all`.

## Design Decisions

- **Engine keys as the canonical format** (not uppercase, not display names). Engine keys are stable, lowercase, and already used by 90% of the codebase.
- **`getSubjectName()` for display** instead of i18n `t()` keys. Avoids maintaining translations for subject names that are proper nouns (same in BM/EN).
- **No localStorage migration.** Beta testers only — they'll re-enter grades.

## Numbers

- Files changed: 10 (6 production, 4 additional test files)
- Lines removed: ~120 (inline arrays, GRADE_KEY_MAP, validate_grades)
- Lines added: ~80 (SPM_SUBJECTS array, vocational SUBJECT_NAMES entries, report labels)
- Tests: 411 pass, 0 fail, 0 skip (was 407)
- Tech debt resolved: TD-013
