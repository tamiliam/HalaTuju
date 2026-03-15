# Retrospective — Tech Debt Quick Wins 2 (2026-03-15)

## What Was Built

- **5 tech debt items resolved**: TD-009 (Gemini rate limiting), TD-023 (engine field naming), TD-039 (sentry-sdk pin), TD-040 (numpy pin), TD-046 (CourseListView pagination)
- **Bug 5 resolved**: Trilingual pre-U course descriptions added via i18n message files (EN/MS/TA)
- **Bug 4 reclassified**: Not a bug — pre-U entry requirements are genuinely broad
- **Tech debt doc updated**: 10 items marked resolved (5 stale + 5 new), resolved count 48/52

## What Went Well

- Quick wins were genuinely quick — all 5 fixes implemented and tested in one session
- i18n approach for pre-U descriptions is the right pattern (user caught the DB shortcut)
- All 424 tests pass after changes, including golden master (5319 SPM, 1811 STPM)
- Engine field naming fix (TD-023) eliminated a hidden coupling that had been there since the Streamlit migration

## What Went Wrong

1. **Initially wrote pre-U descriptions to DB fields instead of using i18n system.**
   - *Symptom*: Created a migration and updated fixtures with MS/EN descriptions only — missing Tamil.
   - *Root cause*: Took the path of least resistance (DB fields existed, i18n felt like more work) without considering the project's established trilingual pattern. The DB model only has `description`/`description_en` — no `description_ta` field.
   - *Fix*: User caught it. Reverted migration and fixtures, added i18n keys to all 3 message files. The detail page now checks i18n keys first, falls back to DB fields. This pattern can be extended to other courses.

## Design Decisions

- **i18n over DB for course descriptions**: For a fixed set of courses (6 pre-U), i18n keys in message files are better than DB fields because they support all 3 languages and are versioned with the codebase. DB fields remain for the 390+ dynamically-loaded courses.
- **Rate limiting via Django cache**: Simpler than a counter model. Uses default LocMemCache in dev, database/Redis cache in production via Cloud Run env vars. 3/day limit is generous but prevents abuse.
- **Backwards-compatible pagination**: CourseListView returns all results when no `?page` param is given, preserving existing frontend behaviour. Pagination is opt-in.

## Numbers

| Metric | Value |
|--------|-------|
| Tests | 424 pass, 0 fail, 0 skip |
| SPM golden master | 5319 |
| STPM golden master | 1811 |
| Tech debt resolved | 48/52 (92%) |
| Files changed | 11 |
| i18n keys added | 13 (6 headlines + 6 descriptions + 1 fallback) × 3 languages |
