# Sprint 14 Retrospective — TVET Data Fix + UX Polish

**Date**: 2026-02-20
**Duration**: 1 session
**Branch**: `feature/v1.1-stream-logic`

## What Was Delivered

1. **TVET data fix** — The big one. All 84 TVET courses were orphaned (zero institution links) because of a silent loader bug. Fixed the loader and inserted 181 course-institution links into Supabase.
2. **Institution taxonomy fix** — 55 ILKBS/ILJTM institutions were incorrectly typed as IPTA. Changed to ILKA in both CSV and DB.
3. **Settings page redesign** — Language selector, clear data button, about section, fully localised.
4. **Saved page i18n** — Localised with useT() hook across EN/BM/TA.
5. **Gemini SDK migration** — `google-generativeai` → `google-genai` v1.x (Client API pattern).
6. **Cloud Run deploy** — Both services updated.

## What Went Well

- **Root cause analysis was thorough.** We traced the TVET orphan problem from "courses have 0 institutions" all the way to the exact line in the loader (`filter().update()` on non-existent records).
- **Fix was clean.** Changed one method in the loader, applied data directly to Supabase, verified with counts.
- **Settings + i18n work was straightforward** — committed and deployed without issues.

## What Went Wrong

- **Silent data failure went undetected for 6 sprints.** The TVET courses were loaded in Sprint 9 (data gap filling) but nobody noticed they had zero institution links until Sprint 14 when the user spotted it manually.
- **No data integrity test for course-institution links.** The golden master tests eligibility logic, not data completeness. A simple "every course with source_type='tvet' should have at least 1 institution" test would have caught this immediately.
- **Institution taxonomy was wrong from the start.** ILKBS and ILJTM institutions were imported as type IPTA instead of ILKA. This was a data modelling gap in the original CSV, not a code bug.

## Lessons Learned

1. **`.filter().update()` is a silent no-op when nothing matches.** Use `update_or_create` when records may not exist yet. Django doesn't warn you.
2. **Data loader pipelines need end-to-end coverage tests.** If step A creates base records and step B enriches them, test that ALL categories have records after step A. Otherwise step B silently skips entire categories.
3. **Add data completeness assertions** alongside logic tests. The golden master validates eligibility calculations but not "does every course have at least one institution link?"

## Action Items for Future Sprints

- [ ] Add a data completeness test: every course should have ≥1 institution link
- [ ] Add a data completeness test: institution type distribution matches expected taxonomy
- [ ] Consider adding `audit_data` to CI or pre-deploy checks
