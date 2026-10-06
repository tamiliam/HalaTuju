# Sprint 15 Retrospective — Career Pathways (MASCO Integration)

**Date**: 2026-02-20
**Duration**: 1 session

## What Was Built

- `MascoOccupation` Django model (272 occupations from Malaysia's official eMASCO portal)
- `Course.career_occupations` ManyToManyField (531 course-to-career links)
- Migration `0005_add_masco_occupations` applied to both local SQLite and Supabase
- `MascoOccupationSerializer` and updated `CourseDetailView` to return career data
- `MascoOccupation` TypeScript type and updated `getCourse()` return type
- "Career Pathways" section on course detail page with clickable indigo pills
- Two new data loaders: `load_masco_occupations` and `load_course_masco_links`
- 8 new tests (3 API + 5 model)

## What Went Well

- **Data already existed**: The `masco_details.csv` and `course_masco_link.csv` files were already in the project from the Streamlit era. This sprint was purely plumbing — connecting existing data to the Django/Next.js stack.
- **Clean integration**: The M2M pattern slotted in naturally. The serializer, view, and frontend changes were minimal — roughly 30 lines across 6 files.
- **Supabase batch loading**: Loading 272 occupations + 531 M2M links via SQL batches worked smoothly. RLS policies applied without issues.
- **Tests passed first time**: All 156 tests green on first run after adding the new 8 tests.

## What Went Wrong

- **Context exhaustion from previous session**: The Lentera review + MASCO discovery + Sprint 15 implementation all happened in one session, which hit context limits. The data loading into Supabase had to be completed in a continuation session.
- **Batch SQL generation was verbose**: Had to generate and paste 272 + 531 INSERT statements through MCP. A bulk SQL file approach or using the management command via Cloud Run would be cleaner for future data loads.

## Design Decisions

1. **masco_code as primary key**: Using the MASCO code directly as PK (not an auto-increment) makes lookups and CSV loading simpler — no need to track generated IDs.
2. **M2M via Django's built-in through table**: Didn't create a custom through model — the simple Course ↔ MascoOccupation link doesn't need extra metadata.
3. **Pills link to eMASCO portal**: Rather than duplicating salary/demand data in our DB, each pill links directly to the official eMASCO page. This keeps our data maintenance burden low and gives users the authoritative source.
4. **Sprint renamed from "UX Polish Phase 2" to "Career Pathways"**: The Lentera vision review revealed career data as the biggest gap, so this sprint pivoted from i18n polish to career pathway integration.

## Numbers

| Metric | Value |
|--------|-------|
| Tests | 156 (+8 from Sprint 14's 148) |
| Golden master | 8280 (unchanged) |
| MASCO occupations | 272 |
| Course-occupation links | 531 |
| Files modified | 8 |
| New migration | 1 (0005) |
| Supabase tables added | 2 (masco_occupations, courses_course_career_occupations) |
