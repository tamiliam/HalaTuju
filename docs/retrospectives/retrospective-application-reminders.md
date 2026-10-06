# Retrospective — Application Completion Reminders + Auto-close (2026-06-06)

Built, shipped, and **activated on prod in one session**: an escalating reminder sequence for
shortlisted-but-incomplete students, with an auto-close at the end. Backend + email only
(no FE). Migration `0041`. Deployed, scheduler wired, backfilled, first batch (R1) sent live.

## What Was Built

- **Cadence** from `reminder_anchor_at`: R1 +2d · R2 +9d · R3 +23d · R4/final +53d (the "5 days
  or we close" warning); then a 5-day grace → auto-close to a new `expired` status.
- **`reminder_anchor_at` as a separate clock knob** (not `shortlisted_at`): new shortlists set it
  to the invitation time (`release_decision`); the launch backfill set the in-flight cohort to
  *today − 2 days* (so R1 fired immediately). Decouples "when reminders count from" from the audit
  timestamp, and gives a re-anchor lever for future grace extensions.
- **`services.send_application_reminders`** — idempotent, one stage per run, burst-proof; the close
  is gated on the final reminder *actually having gone out ≥5 days earlier*, never on raw elapsed
  days. `reminder_stage`/`last_reminder_at`/`expired_at` track state.
- **5 trilingual emails** (R1–R4 + closure), each linking to `/scholarship/application` and naming
  the built-in AI helper **Cikgu Gopal** + a human fallback (`tamiliam@gmail.com`, temporary).
- **Restart after close**: the per-(cohort, profile) unique constraint became **partial** (excludes
  `expired`), and the create-view guard excludes `expired` — so a closed student can re-apply, old
  row kept as history.
- **Ops**: `send_application_reminders` + `backfill_reminder_anchors` commands; cron whitelist entry
  `application-reminders`; a daily Cloud Scheduler (`halatuju-application-reminders`, 9am Asia/KL)
  hitting the HTTP cron endpoint (mirrors `halatuju-vision-outage`).

## What Went Well

- **~60% was already there.** The 55-min/48-h reveal, the email helper, the status funnel, the cron
  endpoint, and a copy-able auto-expiry pattern (`lapse_expired_offers`) all pre-existed — so this
  was mostly new logic + 4 fields, not new infrastructure.
- **Designed the cutover with the user before coding.** The "today = day 2" backfill + the
  `reminder_anchor_at` knob came out of the conversation, so the in-flight cohort was handled cleanly
  (no one ambushed by a final warning) with no rework.
- **Activated safely end-to-end:** migrate-first via MCP → deploy → scheduler → endpoint smoke-test
  (0/0) → dry-run backfill list (eyeballed with the user) → real backfill → manual R1 trigger
  (9 sent). Every step verified before the next.

## What Went Wrong

1. **The re-apply fix initially only relaxed the VIEW guard, not the DB constraint.** Symptom: the
   re-apply test failed with `IntegrityError: UNIQUE constraint failed (cohort_id, profile_id)` even
   after excluding `expired` in the view. Root cause: I assumed uniqueness lived only at the view
   layer and didn't check `Meta.constraints` — there was a DB-level `UniqueConstraint`. Fix (applied):
   make the constraint **partial** (`condition=… & ~Q(status='expired')`). System change: when changing
   an application-creation/uniqueness rule, grep the model `Meta.constraints` first — a view-level
   `.exists()` guard usually has a DB twin. (Captured as a lesson.) The TDD test caught it immediately,
   which is the safety net working.

2. **Reminders land ~1 day later than their nominal day-count.** Symptom: R2 (the +9-day mark for a
   4-Jun anchor) fires on 14 Jun, not 13 Jun. Root cause: the backfill anchored at `now()` (clock time
   01:15) while the daily scheduler ticks at a fixed 09:00 KL (01:00 UTC) — 15 min *before* the anchor's
   time-of-day — so `floor((now - anchor).days)` is one short at the tick and crosses the threshold a
   day later. Impact: harmless for a reminder cadence (consistent 1-day slip). System change (deferred,
   TD): anchor reminders to a **date** (midnight) or compare on date boundaries rather than a
   floor-of-timedelta, if day-exact timing ever matters.

## Design Decisions (logged in decisions.md)

- `reminder_anchor_at` as a separate clock knob (cutover + future grace re-anchoring).
- Partial unique constraint excluding `expired` (enables restart at the DB layer, not just the view).
- "Today = day 2" launch cutover for the in-flight backlog (immediate R1, no ambush).
- Auto-close gated on the final reminder having been sent, never raw elapsed days.

## Numbers

- **1790 backend pytest** (1037 courses/reports + 753 scholarship) + 262 jest (unchanged — no FE).
- No FE change; no i18n-json change (emails are Python templates). i18n parity unchanged (2020).
- Scholarship migrations through **`0041`** on prod (applied migrate-first via MCP).
- **Live**: api rev `halatuju-api-00298-xhp`; scheduler `halatuju-application-reminders` (9am KL);
  9 students anchored, R1 sent, all at `reminder_stage = 1`.
