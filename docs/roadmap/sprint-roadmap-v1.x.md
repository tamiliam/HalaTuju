# HalaTuju Sprint Roadmap — Full Django + Next.js Migration

> **Status**: ACTIVE
> **Created**: 2026-02-16
> **Total**: 20 sprints, 7 phases (expanded from original 15)
> **Plan file**: `.claude/plans/silly-zooming-kay.md`

## Phases

| Phase | Sprints | Objective |
|-------|---------|-----------|
| 0: Foundation | 1-2 | Git cleanup, auth, saved courses, missing pages |
| 1: Intelligence | 3-6 | Quiz API, ranking engine, quiz frontend, dashboard redesign |
| 2: Data | 7-9 | PISMP integration, course detail, data gaps |
| 3: AI Reports | 10-12 | Insights, Gemini reports, PDF download |
| 4: Polish | 13-14 | Localisation (EN/BM/TA), UX polish |
| 5: Lentera | 15 | Career pathways (MASCO integration) |
| 6: Registration | 16 | Auth gate, profile sync, name+school |
| 7: Outcomes + Polish | 17-20 | Outcome tracking, remaining i18n, filters, cleanup |

## Sprint Tracker

| Sprint | Name | Status | Tests | Deploy |
|--------|------|--------|-------|--------|
| 1 | Git Housekeeping + Auth | DONE (2026-02-16) | +11 | No |
| 2 | Saved Courses + Page Shells | DONE (2026-02-16) | +3 | Yes |
| 3 | Quiz API Backend | DONE (2026-02-16) | +14 | No |
| 4 | Ranking Engine Backend | DONE (2026-02-17) | +34 | No |
| 5 | Quiz Frontend | DONE (2026-02-17) | +0 | Yes |
| 6 | Dashboard Redesign (Card Grid) | DONE (2026-02-17) | +2 | Yes |
| 7 | PISMP Integration | DONE (2026-02-18) | +8 | Yes |
| 8 | Course Detail Enhancement | DONE (2026-02-18) | +5 | Yes |
| 9 | Data Gap Filling | DONE (2026-02-18) | +5 | Yes |
| 10 | Deterministic Insights | DONE (2026-02-18) | +8 | Yes |
| 11 | AI Report Backend | DONE (2026-02-18) | +12 | No |
| 12 | Report Frontend + PDF | DONE (2026-02-18) | +4 | Yes |
| 13 | Localisation (EN/BM/TA) | DONE (2026-02-18) | +0 | Yes |
| 14 | TVET Data Fix + UX Polish | DONE (2026-02-20) | +0 | Yes |
| 15 | Career Pathways (MASCO Integration) | DONE (2026-02-20) | +8 | No |
| 16 | Registration Gate (AuthGateModal, ProfileSync) | DONE (2026-02-22) | +10 | Yes |
| 17 | Outcome Tracking (AdmissionOutcome CRUD) | DONE (2026-02-22) | +10 | Yes |
| 18 | UX Polish Phase 2 (remaining i18n) | NOT STARTED | 0 | TBD |
| 19 | TVET/ILKA Frontend Filters | NOT STARTED | 0 | TBD |
| 20 | Cleanup + Documentation | NOT STARTED | 0 | Yes |

## Key Decisions Made

- **Dashboard layout**: Card grid + merit traffic lights (3 col desktop, 2 tablet, 1 mobile)
- **Quiz**: Optional, with prominent "Take Quiz" button on dashboard
- **Scope**: Full migration (all 15 sprints)

See full plan at `.claude/plans/silly-zooming-kay.md` for detailed sprint deliverables.
