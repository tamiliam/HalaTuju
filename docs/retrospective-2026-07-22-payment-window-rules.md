# Retrospective — Payment back/advance-pay window rules — 2026-07-22

## What Was Built

Payment eligibility now asks *"is this student payable for the MONTH being paid for?"* rather than
*"…as at the run's payment date"*, plus a guard on how early an advance run may be paid.

- **`payments._has_started`** compares the pathway floor AND `reporting_date` against
  `period_month`, never `payment_date`. Reporting must be **strictly before** the month begins.
- **`payments.earliest_payment_date()` + `too_early`** — an advance run may be paid no earlier
  than the 25th of the preceding month; `create_run` refuses otherwise.
- The API returns `earliest` with the error; the cockpit renders it (`admin.payments.tooEarly`,
  en/ms/ta). +17 tests, no migration.

## What Went Well

- **The owner's three worked cases drove the design, and became the tests verbatim.** They
  surfaced two things I had wrong in my own proposal: I had assumed a student reporting *during*
  the paid month should count (owner: no — strictly before), and I had not considered that the
  pathway floors are a *consequence* of the reporting rule rather than an independent policy.
  Asking for cases beat asking for a spec.
- **The regression tests were verified to fail against the pre-fix code.** All 13 new
  service-level cases failed when the two comparisons were temporarily reverted — so they pin the
  behaviour rather than merely passing alongside it. Same technique caught nothing this time on
  the i18n guard, but it is cheap and it is the only proof a regression test is real.
- **Audited the blast radius before claiming safety.** Rather than asserting "no money was
  misspent", queried every completed run for a student paid for a month before their pathway
  opened: exactly one row, and it traced to the hand-entered `backfill-2026-06-30` (empty
  `created_by`, non-standard reference), not an engine selection. The engine's history was clean.
- **Declined to create a sixth keep-in-sync pair** — the UI needed a date, not the rule that
  computes it, so the server sends the date. See lessons.md.

## What Went Wrong

- **Nothing broke, but the bug had been live since the payments module shipped** and was only
  found because the owner asked why a run selected 19 students. Root cause of the *original*
  defect: `_has_started` was written when runs were same-month only, so `payment_date` and
  `period_month` were interchangeable; when back/advance pay was introduced, the two diverged and
  only this function was left behind — every other check (`_schedule_status`,
  `_already_paid_for_period`) had already moved to `period_month`. **The generalisable form:**
  when a concept splits into two (one date became "when we pay" + "what we pay for"), grep every
  consumer of the original and confirm which of the two each one meant — a function left on the
  old parameter still compiles and still passes its old tests.
- **My first instinct on the reporting-date question was wrong and I nearly shipped it as a
  recommendation.** I proposed including a student who reports *during* the paid month, reasoning
  from "they qualify for that month". The owner's rule is the opposite. It cost nothing because I
  asked rather than assumed — but the lesson is that "qualifies for month X" was my inference,
  not a stated requirement, and I had presented it as the recommended default.

## Design Decisions

- **Eligibility is a property of the covered month; the payment date only governs whether the run
  may be made.** See decisions.md.
- **An out-of-window run is refused, not emitted empty** (owner agreed) — an empty draft explains
  nothing. See decisions.md.

## Numbers

- **4255 pytest** (+17) + **617 jest**. No migration. `next build` + `tsc` clean.
- `PR-2026-07-26` (August): **19 → 30** students once regenerated. The remaining exclusions are
  correct — 4 PISMP (open in September) and 9 without a confirmed eWallet ID.
