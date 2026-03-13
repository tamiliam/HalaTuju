# STPM Sprint 5 Retrospective — Grade Scale Fix + UX Redesign

**Date:** 2026-03-13
**Branch:** `feature/stpm-entrance`

## What Was Built

1. **Grade scale correction** — Fixed STPM grade points: C- from 2.00→1.67, added D+(1.33), removed E from user-facing scale. Kept E and G as legacy aliases in GRADE_ORDER for backward compatibility with parsed CSV requirement data.
2. **Grade entry page redesign** — Complete rewrite of `/onboarding/stpm-grades`:
   - Stream selector (Science/Arts) as Section 1
   - 3 stream-filtered subject slots + 1 open elective (dashed border)
   - Co-curriculum score input (0.00–4.00)
   - Overall CGPA = 90% academic + 10% co-curriculum
   - MUET as plain number buttons (not "Band N")
   - SPM prereqs split into 4 compulsory + 2 optional
3. **Quiz signal localStorage fix** — Dashboard STPM path was reading from wrong localStorage key (`halatuju_student_signals` instead of `halatuju_quiz_signals`), meaning quiz signals never reached the ranking engine.
4. **Ranking engine fix** — `field_interest` default changed from `[]` to `{}` to match quiz engine's dict format.
5. **i18n** — 9 new keys × 3 locales (EN/BM/TA) for stream, koko, formula labels. Audit passed: 433 keys complete.

## What Went Well

- **User feedback drove real corrections** — the grade scale error (E instead of D+) and C- point value (2.00 vs 1.67) would have caused incorrect eligibility results. Caught before deployment.
- **Golden master preserved** — despite changing grade points and scale, backward compatibility with legacy E/G grades in parsed data kept the 1811 baseline intact after debugging.
- **Frontend build clean** — `npm run build` passed first try after the complete page rewrite.
- **i18n discipline** — all 9 new keys added to all 3 locales simultaneously, audit confirmed completeness.

## What Went Wrong

1. **Golden master broke when E was removed from GRADE_ORDER**
   - *Symptom:* Golden master dropped from 1811 to 1763 (48 fewer eligible programmes)
   - *Root cause:* Parsed CSV requirement data contains `min_grade: 'E'` in `stpm_subject_group` JSON fields. Removing E from GRADE_ORDER caused `meets_stpm_grade('C', 'E')` to raise ValueError. The distinction between "user-facing grade scale" and "data-facing grade scale" wasn't considered.
   - *Fix:* Kept E and G as legacy aliases at the end of GRADE_ORDER. Added comment documenting why.
   - *Prevention:* Always run golden master test immediately after any grade scale change, before any other work.

2. **Quiz signals never reached STPM ranking (localStorage key mismatch)**
   - *Symptom:* STPM dashboard showed programmes without fit score differentiation from quiz signals
   - *Root cause:* When the quiz page was built, it stored signals under `halatuju_quiz_signals`. When the STPM dashboard was built later, it read from `halatuju_student_signals` (the SPM key). Copy-paste error across sprints.
   - *Fix:* Changed dashboard line 134 to read `halatuju_quiz_signals`.
   - *Prevention:* Use constants for localStorage keys instead of string literals. Consider a `storageKeys.ts` module.

## Design Decisions

1. **E/G as legacy aliases** — Rather than migrating all parsed CSV data to remove E/G references (risky, time-consuming), we keep them in GRADE_ORDER only. The user-facing grade dropdown (STPM_GRADES in subjects.ts) excludes them. This is a pragmatic trade-off: data compatibility over purity.

2. **90/10 CGPA formula** — Overall = (academic_cgpa × 0.9) + (koko_score × 0.1). This matches the actual STPM grading system where co-curriculum contributes 10%. Stored as `overallCgpa` in localStorage.

3. **3+1 subject model** — 3 stream-specific subjects + 1 open elective mirrors how STPM students actually choose subjects. The elective slot uses a dashed border and can pick from any stream.

4. **SPM prereq split** — 4 compulsory (BM, BI, Sejarah, Math) + 2 optional (Add Math, Science) reflects the actual requirement structure where MT and Science are stream-specific.

## Numbers

- **Tests:** 320 collected, 287 passing, 9 pre-existing JWT failures, 24 skipped
- **Golden masters:** SPM = 8283, STPM = 1811 (both preserved)
- **i18n keys:** 433 across 3 locales (EN/BM/TA)
- **Files changed:** 8 (2 backend, 6 frontend)
- **New test:** 1 (field_interest dict format in stpm_ranking)
