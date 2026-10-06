# B40 Redesign — Sprint 11b Retrospective (2026-05-24)

The applicant-facing half of S11: the `accepted` application state + the dashboard login banner. Frontend only,
branch `feature/b40-redesign`, not deployed.

## What Was Built
- `/scholarship/application` gains a distinct **accepted** ("confirmed") card — congratulations + "our team will be
  in touch about your award" — separate from the neutral received card. Status map: submitted → received ·
  shortlisted → follow-up · accepted → confirmed · rejected/withdrawn → neutral.
- **`ScholarshipBanner`** — a self-contained dashboard banner that fetches the caller's application and renders only
  when shortlisted/accepted (links to the application page), nothing otherwise. EN/MS/TA i18n.

## What Went Well
- Making the banner a **self-contained component** (its own fetch + early `return null`) kept the large dashboard
  change to a one-line insert + an import — no wrangling the dashboard's render tree or its query plumbing.
- Caught the empty-gap trap early: a `mb-6` *wrapper* around a component that returns null leaves a phantom gap for
  the majority (non-applicants), so the margin lives on the banner element itself.

## What Went Wrong
- Nothing notable — small, additive, frontend-only sprint. No new pure logic, so no jest delta (display + one fetch).

## Numbers
- Frontend jest unchanged (**49**); backend unchanged (**1100**); i18n **1107 keys × 3** (parity); `next build`
  clean. ~5 files (application page, new banner component, dashboard insert, 3 i18n). No migration, no backend change.
  States approved via local screenshot.
