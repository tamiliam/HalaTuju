# Retrospective — TD-481 (an awaiting-QC case is declined only through the QC gate) — 2026-11-04

Live 2026-11-04: main 307d204c; api halatuju-api-01249-zqp, web halatuju-web-01078-pgb. Both Cloud Builds passed
first time. Commits 62a74f07 (fix) and 307d204c (docs, including the adversarial review notes). No migration, no new
endpoint, no web behaviour change.

## What was built
- `AdminRejectView` (`views_admin/applications.py`) refuses `{category: 'interview'}` on an `interviewed` (awaiting-QC)
  case for everyone, a super included. The answer is 400 `awaiting_qc`, and nothing is written.
- The case is declined only at `qc-decision`, which runs the QC gate, the separation guard and the QC record. The
  check sits at the view, not in `admin_reject`, so the QC decision path is unchanged.
- New test `test_td481_awaiting_qc_decline.py` (11 tests). It was proved red without the guard.
- Two existing tests moved to the new rule: `test_reject_buckets.test_reviewer_interview_reject` now declines from
  `interviewing`; `test_decision_reopen` walks reopen, re-record decline, then QC confirm, with its assertions unchanged.

## What went well
- The adversarial review (Opus) returned SHIP with no blocker, and it named the two doors left open as owner calls
  (TD-487, TD-488) instead of changing them unasked.
- The inventory of QC-outcome doors found TD-486 (a super's Cancel reopen can move a case QC sent back straight to
  `recommended`), so the debt was recorded rather than lost.
- The guard was proved by a deliberate break: the new tests went red with the check removed.

## What went wrong
- **The builder's docs presented the lead's scoping as the owner's ruling.** Symptom: the docs said that a case QC
  reopened stays declinable at `/reject/` because the owner ruled it so. The owner ruled only that an awaiting-QC case
  is declined through the QC gate; the reopened-case scoping was the lead's design. Root cause: the brief did not
  separate owner rulings from lead design, so the builder recorded both as rulings. Fix: a brief marks each rule as
  "owner" or "lead", and the docs keep that label. The lead's scoping is now shown as a lead decision with TD-487 open
  for the owner.
- **The builder used about 199k tokens on a small sprint, past the 120k helper limit.** Symptom: a one-fix sprint ran
  on far past its budget. Root cause: the brief asked for an inventory of every QC door, plus docs, on top of the fix,
  so one agent carried three jobs. Fix: an inventory goes to a separate read-only agent. A builder gets the fix and
  its tests, and the docs go to the lead.

## Design decisions
- The refusal is at the view, not in `admin_reject`. The QC decision keeps calling the same service, so the decline
  logic is written once and the gate lives where the request enters.
- The refusal is for everyone, including a super. A super still declines through the QC decision, where the super is
  exempt from separation, so a super loses no power, only the shortcut.
- Owner ruling (2026-11-04): an awaiting-QC case is declined only through the QC decision. Lead scoping: a case QC
  reopened stays declinable at `/reject/`, pending owner ruling on TD-487.
- No web change: the cockpit never offered the `interview` bucket. A stale comment in `DecisionCard.tsx` was corrected.

## Numbers
- api: 12,118 passed, 3 skipped; `manage.py check` and `makemigrations --check` clean.
- web: 411 suites / 6,381 jest passed; `next build` and the bundle budget passed.
- Open debt raised: TD-486 (found by inventory), TD-487 and TD-488 (owner's calls from the review). Closed: TD-481.

## Next
T5c (team tables, permissions), run in progress under the owner's autonomous-run grant. Each deploy is asked first.
See RUN_STATE.md at the repo root.
