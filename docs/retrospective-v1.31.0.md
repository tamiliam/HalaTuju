# Retrospective — v1.31.0 (STPM UX Polish, WP Schools, MASCO Backfill)

## What Was Built
- STPM detail page polish: stream-filtered subjects, coloured badges, legend, mobile layout fixes
- Pathway track cards shown inline on dashboard when pills are active
- 16 WP Kuala Lumpur Form 6 schools added to dataset
- MASCO backfill management command for 62 courses
- Quick Facts now shows average merit cutoff (not student merit)
- Title-case fixes preserving uppercase abbreviations (WP, JPN, SMK)

## What Went Well
- Small, focused commits — each fix was isolated and testable
- Data quality improvements (title case, abbreviation preservation) done at source level
- Golden master still passes (8245 valid applications)
- No new test failures beyond the 13 pre-existing JWT auth failures

## What Went Wrong
- Nothing major — this was a polish sprint with low risk

## Design Decisions
- **Average merit cutoff over student merit**: showing the student's own merit in Quick Facts was confusing — students compared it to nothing. Average cutoff across institutions gives context.
- **Stream filtering on STPM page**: subjects are stream-specific, so showing all subjects for all streams created noise. Filter by selected stream.
- **MASCO backfill as management command**: one-time data fix, but packaged as a reusable command in case new courses are added without MASCO codes.

## Numbers
- Backend tests: 215 (13 pre-existing JWT failures)
- Frontend tests: 0 (no Jest test suite set up)
- Golden master: 8245 valid applications (unchanged)
- Commits: 11
- Files touched: ~10
