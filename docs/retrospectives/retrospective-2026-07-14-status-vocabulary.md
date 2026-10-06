# Retrospective — one status vocabulary: shared labels + semantic stage colours (2026-07-14)

Branch `feat/status-vocabulary` (worktree `.worktrees/status-vocab`), Stream B of the
2026-07-14 parallel remote-station batch. Plan:
`docs/plans/2026-07-14-status-vocabulary-and-stage-colours.md`. No deploy yet — primary
does the final merge to `main`.

## What Was Built

A single source of truth for how a `ScholarshipApplication`'s stage is named and coloured on
the officer-facing admin surface, replacing four drifting labels and two contradictory colour maps.

- **`halatuju-web/src/lib/applicationStatus.ts`** — `APPLICATION_STATUSES` (13, funnel order),
  `SYNTHETIC_STATUSES` (`reopened`), `statusLabelKey`, `statusTone` (literal Tailwind classes),
  `hasStatusTone`, `displayStatus`. Pure, jest-testable, no React/i18n import.
- **Both admin screens rewired** off the module — `admin/scholarship/page.tsx` (deleted
  `STATUS_LABELS`/`statusLabel`/`statusBadge`/`STATUS_OPTIONS`) and `admin/scholarship/[id]/page.tsx`
  (deleted `STATUS_TONE`/`statusTone`). Same word and same colour on both now.
- **The list's status column translates** for the first time (was hardcoded English); its filter
  dropdown is built from `APPLICATION_STATUSES` so it no longer omits `withdrawn`/`expired`.
- **`profile_complete` renamed "Completed" → "Awaiting review"** in en/ms/ta, in the admin FAQ prose
  (plus "Declined" → "Rejected" there), and in the backend `STATUS_CHOICES` (**migration
  `0096_status_awaiting_review`**, choices-only).
- **New guardrail** `applicationStatus.test.ts` that catches the label/colour drift the existing
  i18n orphan test is structurally blind to.

## What Went Well

- **The plan was exact.** File/line references were current; the work was mechanical once the shared
  module existed. No scope creep — the three other `statusBadge`-style maps (sponsor vetting,
  course-interest, maintenance sub-state) are different enums and were left alone as instructed.
- **Staggered heavy runs held the 8 GB line.** Full jest → `next build` (exit 0, unpiped) → then
  backend pytest, never concurrent; 0 python processes at start confirmed Stream A wasn't mid-suite.
  A coordination note went into the shared log before and after.
- **The `verdict` field's shared `STATUS_CHOICES` was a non-event.** makemigrations altered both
  `status` and `verdict`; both are choices-only metadata (max_length unchanged), so it stayed the
  no-DDL migration the plan promised.

## What Went Wrong

- **The tone-coverage test's first premise was wrong, and the test caught it — one iteration.**
  - *What happened:* the first guardrail asserted `statusTone(s) !== DEFAULT_TONE` for every status;
    it failed on `closed`/`withdrawn`/`expired`.
  - *Why:* those ended states are *legitimately* grey — the same grey as the unknown-status default.
    "Differs from grey" conflates "explicitly mapped" with "not grey", which is false for a design
    where grey is a real semantic tone AND the safe fallback.
  - *Fix (applied this sprint):* exported `hasStatusTone(s)` (map membership) and asserted on that
    instead. The lesson — *when a default value is also a legitimate value, test membership not the
    returned value* — is captured in `lessons.md`.

## Design Decisions

See `docs/decisions.md`:
- Semantic colour with a depth ramp (not per-stage identity hues), amber reserved for needs-attention.
- Keys not strings: the shared module returns i18n keys, the caller does `t(...)`.

## Numbers

- Full jest **501/501**; `next build` **exit 0**; `pytest apps/scholarship` **2408 passed, 0 fail**;
  `makemigrations scholarship --check` clean.
- Files: 1 new lib module, 1 new test, 2 screens rewired, 3 i18n files (1 key value each), 1 FAQ,
  1 model, 1 migration. i18n key set unchanged → parity test green.
- No migration DDL, no backfill; frontend-only apart from the choices-only migration.
