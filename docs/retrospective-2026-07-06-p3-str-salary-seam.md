# Retrospective — P3: valid STR settles B40 on the salary route (2026-07-06)

The deferred P3 (the #63 route-seam), shipped after a live review of #45 surfaced a genuine case. All
backend, no migration; re-banding-gated (owner-audited + signed off before deploy).

## What Was Built
A family with a valid STR **and** a working member is pushed onto the salary route, where the income
verdict ignored the STR. #45 (father drives e-hailing, no payslip, but IS the STR recipient) fell to a
false "Unsure / informal / no payslip" because the salary headroom couldn't compute and the STR was never
consulted for banding.

`_verdict_income_salary` now consults a valid STR first (str-proof-spec §8):
- New `income_engine.salary_route_str(application)` → `(grade, member)`: the STR's currency grade
  (`current` / `unconfirmed`) **and** the household member whose IC the recipient matches. The recipient
  is matched against the STR's OWN tagged member, then any working member — NOT `income_earner`, which
  need not be the recipient (#45: father's STR, mother the declared earner). Currency-only invalid STRs
  (rejected / wrong-type / stale / unreadable) return `None` → the salary assessment runs unchanged.
- Caller gate: the recipient member's relationship to the student must be confirmed (fraud guard —
  a stranger's or unrelated STR settles nothing). Current → Certain (green), over the headroom; undated →
  Probable (blue), but RED preserved when the salary is clearly over-line.

## What Went Well
- **The earlier deferral was the right call, and the trigger to revisit was concrete.** P3 was parked on
  2026-07-05 with "no live case"; #45 (STR uploaded 2026-07-06) was the first real one. Shipping on a live
  case, with an audit, beat shipping speculatively.
- **The re-banding stayed tiny and provable.** A DB sweep of salary-route apps with a live STR found
  exactly the seam cases; #8/#16 (invalid STRs) correctly don't move; only #45/#63 change, both toward B40.
- **Reused the STR route's own grading vocabulary** (`str_verified` / `str_not_current` items, current/
  unconfirmed states) so no FE change and the two routes now band an STR consistently.

## What Went Wrong
- **The 2026-07-05 P3 audit under-counted because it predated the live STRs.** It concluded "no live case"
  while #45 hadn't uploaded its STR yet and #63's read differently. Root cause: a point-in-time re-banding
  audit rots as new documents arrive. Lesson: when a change is deferred as "no live case," re-run the
  cheap sweep at the next relevant review rather than treating the old count as durable — a deferred-but-
  correct fix should carry a one-line "recheck this query" note, not a closed verdict.

## Design Decisions (see decisions.md)
- A valid STR settles B40 on EITHER route; recipient matched against the STR's tagged member (not the
  declared earner); current overrides the salary headroom, undated respects over-line RED.

## Numbers
- Scholarship pytest 2108 (+5). No migration, backend only. Re-banding: #45 Unsure→Certain, #63
  Unsure→Probable, #115 unchanged.
