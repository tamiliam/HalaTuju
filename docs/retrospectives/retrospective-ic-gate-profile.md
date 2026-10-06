# Retrospective — IC Gate + Profile Redesign Sprint (2026-03-15)

## What Was Built

Three connected features replacing the school name input with a compulsory IC gate:

1. **IC Gate**: New modal step after auth (Gmail/phone) with auto-dash formatting (`XXXXXX-XX-XXXX`), DOB age 15–23 validation, Malaysian state code check, and masked display (`****-**-1234`). Returning users with existing NRIC skip this step.

2. **Profile Redesign**: View mode by default with per-section Edit/Save/Cancel. Three editable sections (Identity, Contact, Family), one read-only field (IC). Course Interests section unchanged.

3. **Incompleteness Badge**: Red badge on nav profile link and avatar showing count of 8 unfilled profile fields. Disappears when all fields are filled.

## What Went Well

- **Subagent-driven development** worked smoothly — 8 tasks dispatched to fresh subagents, each completing cleanly with commits
- **Backend already had `nric` field** — zero model/migration changes needed, just wiring the frontend to use it
- **Validation rules were agreed upfront** with user — no scope creep during implementation
- **TypeScript compilation** caught one type error immediately (the `as Record<string, unknown>` cast)

## What Went Wrong

1. **Jest wasn't configured for TypeScript in the frontend project.**
   - Symptom: `ic-utils.test.ts` failed with "Cannot use import statement outside a module"
   - Root cause: No `jest.config.js` existed — jest was installed but with no TypeScript transform configured. The project had never had frontend tests before.
   - Fix: Added `jest.config.js` with `ts-jest` transform and `@/` path alias. This is now committed and reusable for future frontend tests.

2. **Backend test count discrepancy (424 → 293).**
   - Symptom: Expected 424 tests but `python manage.py test --parallel` reported 293.
   - Root cause: `manage.py test` uses Django's test runner which only finds `tests/test_*.py` pattern by default. The documented `pytest` command collects more test files. The 424 count in CLAUDE.md is from pytest.
   - Fix: No code change needed — both runners pass. But CLAUDE.md test commands should clarify which runner yields which count.

## Design Decisions

- **IC validation is simple by design** — user explicitly said "the validation should be simple" and "we may not display it in profile, we'll just show the last four digit". No gender derivation from IC, no checksum validation on last 4 digits.
- **IC is immutable after entry** — once set during the auth gate, it cannot be edited on the profile page. This prevents students from changing their IC to game eligibility.
- **School input removed entirely** — replaced by IC, not moved elsewhere. School field still exists in the model but is not collected during the auth flow.

## Numbers

- Commits: 9 (8 feature + 1 docs)
- Files created: 5 (ic-utils.ts, ic-utils.test.ts, IcInput.tsx, useProfileCompleteness.ts, jest.config.js)
- Files modified: 7 (AuthGateModal.tsx, api.ts, AppHeader.tsx, profile/page.tsx, en.json, ms.json, ta.json)
- Frontend tests: 17 (all new — IC utils)
- Backend tests: 293 (manage.py) / 424 (pytest) — all pass, 0 failures
- i18n keys added: 16 × 3 languages = 48 total
