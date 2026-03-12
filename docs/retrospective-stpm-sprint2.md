# STPM Entrance Sprint 2 Retrospective

**Sprint:** STPM Entrance — Frontend Onboarding + Grade Entry
**Date:** 2026-03-12
**Branch:** feature/stpm-entrance

## What Was Built

- **STPM subject definitions** — `lib/subjects.ts` constants (20 subjects, grade scale, MUET bands, SPM prereqs) aligned with backend engine keys
- **Frontend CGPA calculator** — `lib/stpm.ts` mirrors backend `stpm_engine.py` grade-point mapping
- **Exam type activation** — `/onboarding/exam-type` page enables STPM selection (was "Coming Soon"), sets localStorage key
- **STPM grade entry page** — `/onboarding/stpm-grades` single combined page: PA compulsory + 4 optional subjects, MUET band pills, auto-calculated CGPA, SPM prerequisites (6 subjects)
- **STPM API client** — `checkStpmEligibility()` in `lib/api.ts` with typed request/response interfaces
- **Dashboard STPM routing** — conditional rendering: STPM programme cards or SPM course cards based on `exam_type`
- **Backend profile fields** — `StudentProfile` gains `exam_type`, `stpm_grades`, `stpm_cgpa`, `muet_band`, `spm_prereq_grades` with profile sync + API support
- **i18n** — 14 new translation keys across EN/MS/TA for STPM onboarding flow

## What Went Well

- **Subagent-driven development** continued to work well — fresh context per task, spec + quality reviews after each
- **Single combined page decision** (Option A) proved correct — SPM prerequisites section is compact (6 subjects), no need for a separate step
- **Frontend-backend key alignment** was validated early via `stpm_engine.py` inspection — no key mismatches at integration
- **Zero regressions** — all 261 tests pass, both golden masters intact (SPM 8283, STPM 1811)
- **6 new backend tests** cover the profile field additions comprehensively

## What Went Wrong

- **Rate limit hit mid-sprint** — first attempt at Task 2 was blocked by API rate limiting. Recovered by re-dispatching the subagent. Minor time cost.
- **No automated frontend tests** — all 6 new frontend files lack test coverage. The project has no frontend testing infrastructure yet (no Jest/Vitest setup). This is technical debt.

## Design Decisions

1. **Single combined page (Option A) over two-step flow** — SPM prerequisites section is only 6 subjects in a 2-column grid. Splitting into a separate page would add unnecessary navigation. Users see everything on one scrollable page.

2. **localStorage for STPM state** — Matches existing SPM pattern (`halatuju_grades`, `halatuju_profile`). New keys: `halatuju_exam_type`, `halatuju_stpm_grades`, `halatuju_stpm_cgpa`, `halatuju_muet_band`, `halatuju_spm_prereq`.

3. **SPM prerequisite keys use engine keys (bm, eng, hist)** — Not UI keys (BM, BI, SEJ). The STPM engine expects engine keys directly, unlike SPM which goes through a serializer mapping layer.

4. **Gender/nationality mapping in dashboard** — Frontend stores `male`/`female` and `malaysian`/`non_malaysian`. Dashboard maps these to Malay labels (`Lelaki`/`Perempuan`, `Warganegara`/`Bukan Warganegara`) before sending to STPM API, matching existing SPM dashboard behaviour.

5. **PA (Pengajian Am) locked as compulsory** — All STPM students take PA. The UI shows it with a lock icon and pre-selected, requiring only a grade selection.

## Numbers

| Metric | Value |
|--------|-------|
| New frontend files | 2 (stpm-grades/page.tsx, lib/stpm.ts) |
| Modified frontend files | 4 (exam-type/page, dashboard/page, lib/api, lib/subjects) |
| New backend tests | 6 |
| Total tests | 294 collected, 261 passing |
| SPM golden master | 8283 (unchanged) |
| STPM golden master | 1811 (unchanged) |
| New i18n keys | 14 (across 3 locales) |
| Commits | 7 |
| Migration | 0013 (5 new StudentProfile fields) |
