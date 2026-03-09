# Retrospective — v1.26.0 My Profile & Course Interests

**Date:** 2026-03-09
**Sprint:** Post-v1.25.1 (My Profile feature)

## What Was Built

- Expanded `StudentProfile` model with 5 new fields for Lentera longitudinal tracking (NRIC, address, phone, family income, siblings)
- `SavedCourse.interest_status` field to reframe "My Applications" as a wishlist/intentions log
- Full `/profile` page with 4 card sections, gradient icon headers, status pill dropdowns
- Navigation integration (top nav, dropdown, mobile menu)
- i18n for EN, BM, TA
- Exam-type page visual redesign
- Course detail page critical review document (10 issues identified, prioritised)

## What Went Well

- **Brainstorming-first approach**: Clarifying questions before design prevented building the wrong thing. Key pivot: "applications" became "course interests" after learning UPU handles actual applications
- **Subagent-driven execution**: 7 tasks dispatched sequentially, each with clean TDD. Zero regressions
- **Backend-first strategy**: Models + API tested and committed before any frontend work. Clean separation
- **Parallel deploys**: Backend and frontend deployed simultaneously, both succeeded first try
- **Stitch mockup**: Generated profile page design for visual approval before coding

## What Went Wrong

- **Stitch generation silent failures**: Two generation attempts in the existing project returned no output and no screen. Had to create a new project. The tool gives no error message when this happens
- **No formal sprint number**: This work sits between v1.25.1 and Sprint 21. Should have been Sprint 21 or a named sprint

## Design Decisions

1. **Onboarding stays minimal** — expanded profile is a separate page, not part of onboarding flow
2. **Student self-reports all data** — no counsellor portal needed yet
3. **PDPA consent deferred** — collect fields now, add consent when Lentera formalises
4. **Course interests, not applications** — HalaTuju provides guidance only; status tags are self-reported reference notes
5. **Interest status on SavedCourse** — simpler than a separate model; status lives where the bookmark lives

## Numbers

| Metric | Value |
|--------|-------|
| Backend tests | 188 collected, 179 pass |
| New tests added | 13 |
| Golden master | 8280 (unchanged) |
| Pre-existing failures | 9 (JWT auth) |
| Frontend build | Clean |
| Backend rev | 40 (was 33) |
| Frontend rev | 44 (was 42) |
| Files touched | ~12 |
| Commits | 10 |
