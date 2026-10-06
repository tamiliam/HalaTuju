# Retrospective — v1.32.0 Pathway Ranking, Quiz Flow, Data Persistence

**Date**: 2026-03-11
**Sprint**: v1.32.0

## What Was Built

1. **Matric/STPM in ranked results** — pre-university pathways now compete alongside diploma/degree courses in the ranked list, scored with prestige bonus (+8), academic bonus (merit/mata gred thresholds), and quiz signal adjustments (±10 cap). Fit score range ~103-122.

2. **Quiz signal adjustments for pathways** — all 8 quiz questions evaluated for Matric/STPM relevance. concept-first learners boosted, hands-on preference penalised, pathway-priority students get +3. Balanced so pathways aren't stuck at base 100 while quiz-boosted courses reach 120.

3. **Quiz-then-report flow** — report generation gated by `halatuju_report_generated` localStorage flag. Retaking quiz resets the gate. "Retake Quiz" now navigates to `/quiz` instead of staying on dashboard.

4. **Data persistence** — localStorage cleared on logout (all `halatuju_*` keys). On login, returning users get grades/demographics/quiz signals restored from Supabase via `GET /api/v1/profile/`.

5. **STPM data fixes** — 3 school data errors fixed (duplicate pp, PK→PAKN, redundant MM/PP). 5 missing subjects added to legend (BT, BC, KMK, ICT, L.ENG).

## What Went Well

- **Scoring design conversation** — user provided deep domain knowledge about matric/STPM thresholds, allowances, and flexibility of pre-university tracks. This led to a well-calibrated scoring system.
- **No backend changes needed** — all pathway scoring runs on frontend (pathways.ts). Supabase sync already existed — just needed the restore-on-login and wipe-on-logout wiring.
- **Build passes** — no TypeScript errors, no regressions.

## What Went Wrong

- **Context exhaustion** — the session ran out of context mid-task, requiring a continuation. The scoring discussion was valuable but lengthy.
- **v1.31.0 sprint close was premature** — it was done mid-session before the main features (pathway ranking, quiz flow, data persistence) were implemented. Should have waited.

## Design Decisions

1. **Prestige bonus (+8)** — pre-university pathways are inherently prestigious in Malaysian education. Without this, they'd be submerged beneath quiz-boosted vocational courses for top students.

2. **Academic thresholds**: Matric uses merit (92/87/82 → 8/5/3), STPM Science uses mata gred (6/10/14/18 → 8/5/3/1), STPM Social Science (4/7/10/12 → 8/5/3/1). Below thresholds = student likely won't qualify.

3. **Signal cap ±10** — prevents quiz signals from dominating. Pathways max at ~122 (8 prestige + 8 academic + 6 signal from base 100).

4. **localStorage as primary store, Supabase as backup** — anonymous users work entirely from localStorage. Logged-in users get sync on signup and restore on login. Logout wipes everything for device-sharing safety.

5. **No signal_strength sync** — only `student_signals` (the nested signal groups) synced to Supabase. `signal_strength` is a computed summary that can be recomputed from signals. Kept it simple.

## Numbers

- Frontend commits: 5
- Backend commits: 0
- Files touched: ~6 (pathways.ts, dashboard/page.tsx, CourseCard.tsx, quiz/page.tsx, auth-context.tsx, AppHeader.tsx, stpm-schools.json, stpm/page.tsx)
- Tests: 212 collected, 203 passing (unchanged)
- Golden master: 8245 (unchanged)
