# Retrospective — Tech Debt Sprint 4 (2026-03-14)

**Date:** 2026-03-14
**Duration:** Single session
**Scope:** Fix 6 critical correctness and code quality issues from `docs/technical-debt.md`

## What Was Built

6 tech debt items resolved:

| ID | Fix | Files Changed |
|----|-----|---------------|
| TD-001 | Added `spm_pass_bi` and `spm_pass_math` to `SIMPLE_CHECKS` | `stpm_engine.py` |
| TD-050 | Quiz page uses `useT()` locale instead of wrong localStorage key | `quiz/page.tsx` |
| TD-007 | Bare `except:` narrowed to `except (ValueError, TypeError):` | `engine.py` |
| TD-020 | Removed duplicate `credit_stv` key | `serializers.py` |
| TD-018 | Removed duplicate `Count, Subquery, OuterRef` import | `views.py` |
| TD-019 | Moved inline `json`/`defaultdict` imports to file top | `views.py` |

## What Went Well

- **Impact analysis before fixing.** Querying Supabase before TD-001 confirmed zero programmes set `spm_pass_bi` or `spm_pass_math` to `true`. This meant the fix was purely defensive — no eligibility results changed, no users were affected, and the golden master baseline stayed at 1,811. The analysis saved us from unnecessary user notifications.
- **All fixes were surgical.** Each change was 1-5 lines. No cascading effects, no test regressions.
- **Tech debt register works as a living document.** Having the exact file paths and line numbers from the audit made each fix trivial to locate and implement.

## What Went Wrong

Nothing significant. This was a clean sprint with well-scoped, pre-audited fixes.

## Design Decisions

- **TD-001 scope finding:** See `docs/decisions.md` for the full decision entry. Zero programmes affected, but fix applied defensively for future data correctness.
- **TD-050 locale mapping:** Backend quiz API accepts `en`/`bm`/`ta` but frontend i18n uses `en`/`ms`/`ta`. Rather than changing either convention, added a simple `locale === 'ms' ? 'bm' : locale` mapping at the call site. This is the smallest possible fix.

## Numbers

| Metric | Value |
|--------|-------|
| Tests passing | 332 (courses: 320, reports: 12) |
| Tests failing | 13 (all pre-existing JWT auth) |
| Tests skipped | 30 |
| Golden master (SPM) | 8,283 (unchanged) |
| Golden master (STPM) | 1,811 (unchanged) |
| Files changed | 6 |
| Tech debt items resolved | 6 of 52 (46 remaining) |
