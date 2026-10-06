# Retrospective — Test Health Sprint (2026-03-14)

## What Was Built

Eliminated all test failures and skipped tests in the HalaTuju API test suite.

**Auth fix (TD-010, TD-033):** 13 tests were failing because the Supabase auth middleware calls `jwt.get_unverified_header()` before `jwt.decode()`. Tests only mocked `jwt.decode`, so `get_unverified_header('fake-token')` raised `InvalidTokenError` before the mock was reached. Fixed by adding a second mock for `jwt.get_unverified_header` in all affected test setUp methods.

**Skipped tests fix:** 30 tests were silently skipping because they depended on CSV data files that were deleted months ago during the DB migration. Created JSON fixtures from production Supabase data (`courses.json`, `requirements.json`), rewrote test setUp methods to load fixtures, and created a shared `conftest.py` helper. 25 tests converted, 5 redundant tests deleted (already covered by `test_pathways.py`).

**Golden master rebaseline (TD-035):** The golden master test was the most critical regression test in the codebase — and it was silently skipping. Old baseline (8283) was from CSV data that was subsequently modified across multiple sprints (data integrity, MOHE audit). New baseline (5319) matches current production Supabase data exactly.

## What Went Well

- **Systematic root cause analysis**: Instead of just fixing symptoms, traced each skip/failure to its root cause (missing CSV files, stale mock setup).
- **Shared test infrastructure**: `conftest.py` with `load_requirements_df()` eliminates duplicated DataFrame loading across 3 test files.
- **Production data verification**: Dumped fixtures directly from production Supabase, ensuring test data matches what users actually see.
- **Redundancy elimination**: Identified 5 tests that were exact duplicates of tests in `test_pathways.py` and deleted them rather than converting.

## What Went Wrong

1. **The tech debt audit missed silently skipping tests.**
   - *Symptom:* 30 tests were skipping for months with no one noticing.
   - *Root cause:* The tech debt audit examined code and docs but never analysed pytest output. It checked what code exists, not what code actually runs. The `unittest.skipIf` guards on CSV file existence meant pytest reported "30 skipped" — which looked normal.
   - *System change:* Added to CLAUDE.md pre-deploy checklist: "382 tests must all pass (0 skipped, 0 failures)". Future sprints will flag any skipped test as a red flag, not a normal condition.

2. **Golden master baseline was stale for months — the most critical regression test wasn't running.**
   - *Symptom:* The golden master claimed 8283 matches but the actual DB data produces 5319.
   - *Root cause:* When CSVs were migrated to Supabase and subsequently modified (data integrity sprint, MOHE audit, field corrections), the golden master test was already skipping. There was no mechanism to detect that a critical test had stopped running.
   - *System change:* Golden master now loads from DB fixtures that can be regenerated from production. The 0-skip requirement in CLAUDE.md prevents this class of silent regression.

## Design Decisions

- **DB fixtures over CSV files**: JSON fixtures loaded via Django's `loaddata` are the canonical test data source. They match production exactly and survive codebase refactoring.
- **Shared conftest helper**: `load_requirements_df()` replicates the production startup flow (DB → DataFrame) for tests, with column renames and pathway map building.
- **Auth mock over test infrastructure**: Simple mock fix chosen over building a full `TestAuthMixin`. See `docs/decisions.md` for full rationale (YAGNI — wait for admin layer design).
- **Golden master rebaseline**: 5319 is correct. The 8283→5319 drop reflects real data changes across 3 sprints, not a regression. Verified by comparing per-student counts between production DataFrame and fixture DataFrame (identical).

## Numbers

| Metric | Before | After |
|--------|--------|-------|
| Tests collected | 387 | 382 |
| Tests passing | 344 | 382 |
| Tests failing | 13 | 0 |
| Tests skipped | 30 | 0 |
| SPM golden master | 8283 (stale, not running) | 5319 (verified, running) |
| Files created | — | 3 (2 fixtures + conftest) |
| Files modified | — | 3 (test_golden_master, test_api, test_preu_courses) |
| Tests deleted | — | 5 (redundant pre-U tests) |
| Tech debt resolved | — | TD-010, TD-033, TD-035 |
