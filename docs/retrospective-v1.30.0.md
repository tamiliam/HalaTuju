# Retrospective — v1.30.0 (Matric/STPM Detail Pages + UX Fixes)

**Date:** 2026-03-10

## What Was Built

- Matriculation detail page (`/pathway/matric`) with 15 KPM colleges, 4 tracks, state filter, merit traffic light
- STPM detail page (`/pathway/stpm`) with 568 schools, 2 bidang, state + PPD filters, load-more pagination
- PathwayTrackCard component — course-card-style cards for matric tracks and STPM bidang on dashboard
- Static data files: `matric-colleges.ts` and `stpm-schools.json`
- About page rewritten with mission statement, localised in EN/BM/TA
- Pathway pills as clickable filters (matric/stpm navigate to detail pages, others filter courses)
- Course detail cleanup (removed duplicate field/duration, added student merit to Quick Facts)
- "Apply" renamed to "More Info" on institution links
- Phone login gracefully blocked with "coming soon" message

## What Went Well

- **Parallel subagents**: Tasks 2, 3, and 5 (matric page, STPM page, i18n) ran in parallel, saving significant time
- **Data extraction**: Matric college-to-track mapping extracted from MOE Soalan Lazim PDF was accurate
- **Existing STPM data**: SchoolScraper CSV from prior project had exactly what we needed (568 schools)
- **Build-first**: Building after each change caught the Suspense boundary issue early

## What Went Wrong

- **Wrong GCP deploy**: One deploy went to SJKTConnect project instead of HalaTuju because gcloud config drifted. Now an orphaned `halatuju-web` service exists on the wrong project. Need to delete it.
- **Multiple deploys**: 5 deploys in one session (rev 54-58). Could have batched changes better.
- **Stitch generation**: Stitch MCP returned empty output for the detail page design. Had to skip and code directly.

## Design Decisions

- **Static data over API**: Matric colleges (15) and STPM schools (568) bundled as static JSON/TS files in frontend. Too small to justify an API endpoint.
- **URL search params**: Detail pages use `?track=sains` and `?stream=sains` to select which track/bidang to show, enabling deep linking from cards.
- **Supabase images reused**: PathwayTrackCards map to existing field images (e.g., sains→kimia-alam-sekitar, kejuruteraan→kejuruteraan-am) rather than creating new ones.
- **Phone login blocked at source**: `signInWithPhone()` returns error immediately rather than attempting Supabase call, avoiding potential billing issues.

## Numbers

- Frontend revisions: 54 → 58 (4 deploys to correct project + 1 accidental to wrong project)
- Backend: unchanged (rev 42)
- New files: 6 (2 data files, 1 component, 2 detail pages, 1 plan doc)
- Modified files: ~12 (dashboard, PathwayCards, course detail, supabase, about, 3 i18n files, CHANGELOG, CLAUDE.md)
- Tests: 203 passing (unchanged)
