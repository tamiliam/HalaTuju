# Retrospective — Post-Sprint 20: Search Page Stitch Alignment

**Date:** 2026-02-25
**Version:** v1.23.2

## What Was Built

Aligned the `/search` (Course Explorer) page with the Stitch design screen `ff7ddb0e2bed4181ab1927263a3f1c03`. Focused on two areas:

1. **Filter bar redesign** — "Clear Filters" button (visible when filters active), eligibility toggle restyled as a pill switch with descriptive subtitle, moved into the filter row (right-aligned on desktop, wraps on mobile)

2. **Course card info** — Institution name + state (with pin icon) + "+N more" count on search cards. Book icon added to field text. All passed as optional props to `CourseCard` so dashboard/saved pages are unaffected.

## What Went Well

- **Backend Subquery approach** worked cleanly — two annotations on the existing search queryset, no N+1 queries, no new endpoints needed
- **Optional props pattern** for CourseCard kept the change contained — dashboard and saved pages untouched
- **All 3 new tests passed first try** — good test data setup in the existing fixture class
- **i18n done in all 3 languages** simultaneously — EN, BM, TA

## What Went Wrong

- Nothing significant. This was a small, focused change.

## Design Decisions

| Decision | Rationale |
|----------|-----------|
| Show alphabetically first institution on card | Course can have many offerings; showing the first alphabetically is deterministic and consistent |
| Optional props vs separate SearchCourseCard | CourseCard already handles 2 variants (eligible/ranked); adding 3 optional props is less maintenance than a new component |
| Pill toggle for eligibility filter | Matches Stitch design; more discoverable than a plain checkbox buried in the results meta row |
| `flex-1 min-w-0` spacer for toggle alignment | Pushes toggle right on desktop; collapses on mobile so toggle wraps naturally |

## Numbers

| Metric | Value |
|--------|-------|
| Files changed | 8 |
| Lines added/modified | ~140 |
| Tests (total) | 173 collected, 164 passing |
| New tests | 3 |
| Pre-existing failures | 9 (JWT auth) |
| Golden master | 8,280 |
