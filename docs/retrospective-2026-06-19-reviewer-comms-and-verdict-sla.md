# Retrospective — Reviewer comms consistency, reschedule, verdict SLA (2026-06-19)

A 3-sprint roadmap (commits `a3c5d31` → `1d89393`) decomposed via `implementation-planning.md`,
worked in worktree `.worktrees/sched` / `feat/interview-scheduling` (isolation maintained). Each
sprint shipped + deployed independently; migration `scholarship/0064` applied migrate-first.

This followed the earlier same-day reviewer-email consistency pass and the cancellation-email +
reschedule-toggle small change (`ee8b819`, `f0d0310`).

## What Was Built

**Sprint 1 — interview email set completed + 10-day SLA.** The last two plain-text student
interview emails (1-day/1-hour **reminder**, **cancellation** confirmation) became HTML primary +
plain-text fallback, bilingual EN+BM with the `english_only` gate, From `interview@` — matching
their booked/slots-proposed siblings. `REVIEW_SLA_DAYS` 7 → 10.

**Sprint 2 — reviewer reschedule.** A reviewer can MOVE a booked interview from the cockpit
("Reschedule (move the time)" + confirm): releases the booking (slot + Meet/calendar event +
fields), reopens the picker, and the student gets the "pick a time" email with a moved-the-time
preface. No reviewer self-cancel by design; a true hand-off is an admin reassignment. Backend:
`propose_slots(..., release_booking=True)` + a `reschedule` flag on the propose endpoint.

**Sprint 3 — verdict-completion SLA (TD-131).** `send_review_nudges` cron (dark behind
`REVIEW_NUDGES_ENABLED`): verdict due = `assigned_at + REVIEW_SLA_DAYS`; nudge the reviewer 2 days
before + once overdue; escalate to all super-admins 4 days after due. Idempotent via 3 stamps
(migration `0064`) reset on every (re)assignment; a recorded `verdict_decided_at` drops the case.
Verdict-due date also rides on the reviewer interview reminder (different clocks).

**Sprint 4 — accept/decline lifecycle: DROPPED** after critical evaluation (owner agreed).

## What Went Well
- **Decompose-then-ship-per-sprint** kept each deploy small and independently green; the migration
  was isolated to Sprint 3 and applied migrate-first (verified columns + `django_migrations` row on
  prod before the code push).
- **Reuse over rebuild** (L236): reschedule reused the propose flow + the existing "pick a time"
  email (a `rescheduled` preface), and the new HTML emails reused `_html_email_shell`/`_email_button`
  — no new picker, no new student email.
- **Critical evaluation killed a weak feature before any code** (Sprint 4): the one-click
  accept/decline + auto-unassign was refused on safety (email-bot prefetch/forgery), friction, and
  redundancy with the escalation already being built.

## What Went Wrong
- **Build-status times reported in UTC read as an 8-hour misalignment.** *Symptom:* the owner said
  "your time and mine appear unaligned" — I'd quoted `08:03 UTC` while it was 4:03 pm MYT. *Root
  cause:* passed the build tool's raw UTC timestamp straight through to a UTC+8 user. *Fix:* convert
  build/deploy times to MYT in status reports (lesson added).
- **Reset-on-reassign test failed first run.** *Symptom:* `test_reassignment_resets_nudge_stamps`
  asserted a same-reviewer reassign clears the stamps; it didn't. *Root cause:* `assign_reviewer`
  short-circuits a no-op when the assignee is unchanged, so the reset path never ran. *Fix:* test the
  reset with a DIFFERENT assignee (the real reassignment path); the no-op behaviour is correct.
- **Test helper baked in a field a test needed to vary.** *Symptom:* `_app(... status='rejected')`
  raised `TypeError: multiple values for 'status'`. *Root cause:* the helper hardcoded `status` as a
  create kwarg. *Fix:* make varying fields parameters with defaults — a generic test-helper habit.

## Design Decisions (see docs/decisions.md)
- Reviewer reschedule (not self-cancel) + verdict-SLA enforcement (nudge cadence, all-supers
  escalation, idempotency reset on reassign) — 2026-06-19.

## Numbers
- Commits: `a3c5d31` (S1) → `ed35017` (S2) → `1d89393` (S3). Migration `0064` (3 nullable stamps).
- Tests: +3 (S1) +3 (S2) +7 (S3) scholarship tests; all suites green.
- Three api builds (S1, S3 backend-only) + one web+api build (S2), all SUCCESS.

## Carry / owner actions
- Turn the SLA cron ON: `REVIEW_NUDGES_ENABLED=1` on the api + a daily Cloud Scheduler `review-nudges`
  job (with `X-Cron-Secret`). Dark until then.
- Still parked from the prior scheduling sprint: flip `INTERVIEW_SCHEDULING_ENABLED=1` after the
  reviewer briefing; add the merged SPF record; Guide scheduling screenshot (TD-126); Brevo
  List-Help on transactional (TD-130).
