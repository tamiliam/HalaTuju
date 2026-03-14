# Retrospective — Refactoring Sprint (TD-045, TD-044)

**Date:** 2026-03-14

## What Was Built

- **Service module extraction (TD-045):** `EligibilityCheckView.post()` reduced from ~310 lines to ~100 lines. Five pure functions extracted to `eligibility_service.py`: `compute_student_merit`, `compute_course_merit`, `deduplicate_pismp`, `sort_eligible_courses`, `compute_stats`.
- **Double iteration fix (TD-044):** PISMP req hash collection merged into the main eligibility loop, eliminating a redundant DataFrame iteration.
- **TVET guard removal:** Removed the `source_type != 'tvet'` guard from merit calculation after confirming 0/84 TVET courses have merit data. The guard was defensive code with no actual effect.
- **19 new unit tests** covering all service functions, with TDD red-green-refactor cycle.

## What Went Well

- **Proposal-first approach worked.** User asked for a solution explanation before coding. This caught the TVET guard question early — user asked to remove it, we verified via data query, and removed it cleanly.
- **TDD caught real issues.** Writing tests first for the PISMP deduplication revealed that test IDs (`PI0101001`) didn't match real ID patterns (`50PD010M00P`). The zone code extraction `[4:6]` would have silently passed with wrong test data.
- **Zero regressions.** 387 existing tests continued passing after the refactoring (406 total with new tests).
- **Clean extraction.** The service module has no Django/DRF dependencies — pure Python functions that are easy to test and reason about.

## What Went Wrong

- **PISMP test IDs were initially wrong.** First test draft used fabricated IDs where `[4:6]` gave the wrong zone codes. Root cause: didn't check real PISMP course IDs before writing tests. Fix: verified against actual `course_id` patterns in the database before finalising tests.

## Design Decisions

- **Pure functions over class methods.** Service functions take explicit parameters rather than being methods on a service class. This avoids unnecessary state and makes testing trivial — no setUp, no mocking.
- **View stays as orchestrator.** The view handles HTTP concerns (request parsing, response building) and calls service functions for business logic. This follows the "thin views, fat services" pattern.
- **No tvet guard.** Removed rather than extracting — the guard had no effect and its presence suggested TVET courses might one day have merit data, which isn't planned.

## Numbers

| Metric | Before | After |
|--------|--------|-------|
| `EligibilityCheckView.post()` lines | ~310 | ~100 |
| Service module | — | 246 lines (5 public functions) |
| Test files | 0 service tests | 19 service tests |
| Total tests | 387 | 406 |
| DataFrame iterations per request | 2 | 1 |
| Tech debt items resolved | 15/52 | 17/52 |
