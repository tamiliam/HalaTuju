# Retrospective — Interview comms channel + slot-release model (2026-07-03)

**Branch:** `feat/interview-comms` (worktree `.worktrees/interview-comms`, off `main` a42e6488).
**Migration:** `scholarship/0089_interviewmessage` (additive CreateModel — apply **migrate-first** via
Supabase MCP + RLS before push). **Resolves TD-151 + TD-152.**

## Why

Live-testing the scheduler surfaced two faults in one sitting:

1. **Phantom holds (TD-151).** Rohini proposed 3 Friday-evening times to #80 (Tavanisah); Tavanisah booked
   8:00pm — but the unpicked 8:30/9:00pm siblings stayed active AND kept counting as reviewer-busy, so
   Moven's (#78) picker showed them struck through. With a 3.5-hour bookable evening, every completed
   booking silently blocked two extra slots. (The "later completely removed" the owner saw was the separate
   24h-minimum-lead window rolling past the last slot of the day — by design, not a bug.)
2. **No channel inside the cutoff (TD-152).** Once booked, reschedule/cancel lock 12h out and
   "Ask for other times" refuses when booked — so a student falling sick one hour before the call had
   no way to tell anyone. Reviewer contact details are deliberately never shared (the dead
   `share_phone_with_students` toggle records the rollback), and email replies land in the shared
   interview@ mailbox.

## What shipped

### Slot release (owner-specified model)
- **A booked application HOLDS only its booked slot.** Unpicked siblings are RELEASED: they stay
  `is_active` as the student's re-pick menu, but no longer block the reviewer offering those times to
  another student. First to book wins; a released time re-offered elsewhere disappears from the original
  student's re-pick menu, and a stale-page re-pick of it is server-refused (`reviewer_conflict`).
- **One source of truth: `scheduling.held_starts(reviewer, exclude_application=)`**, used by:
  the `propose_slots` guard · the `reviewer_busy` admin payload · the student slot list in
  `interview_schedule_payload` (booked apps only) · the `book_slot` race backstop.
- **Booking guard has two strengths:** a FIRST booking blocks only on a confirmed booking elsewhere
  (a mere proposal must not beat the student who acts first); a RE-PICK blocks on anything held.

### "Message your interviewer" (always-open channel)
- `scheduling.send_student_message` → new `InterviewMessage` row + best-effort
  `emails.send_reviewer_student_message_email` (plain reviewer email, includes the booked time when known).
  Guards: non-empty, 1000-char cap, **5/hour rate limit**, requires an assigned reviewer.
- `POST /api/v1/scholarship/applications/<pk>/interview/message/` (own-application scoped; deliberately
  **no state gate and no cutoff**).
- Student panel: a message section rendered in **every** state (proposed / booked / locked / cancelled).
  Cockpit: "Messages from the student" block on the schedule card. Payload carries the last 20 messages.
- i18n en/ms/ta (Tamil first-draft → refine queue).

## Gates

- **1976 scholarship pytest** (main 1960 + 16 new in `test_interview_comms.py`) · **406 jest** ·
  `tsc --noEmit` clean on changed files (13 pre-existing errors in 3 untouched test files, excluded from
  `next build`) · i18n parity via the jest guardrail.

## Lessons

- The first cut of the booking guard blocked FIRST bookings on other students' unbooked proposals —
  caught by the existing `test_book_rejects_reviewer_conflict` sibling test. First-to-book-wins needs the
  two-strength guard, not one blanket rule.
- Django's `F('id')` inside a joined `Q` resolves against the queryset's base model — the released-sibling
  exclusion works as one exclude(), no subquery needed.

## Deploy

1. Migrate-first via Supabase MCP: create `interview_messages` + enable RLS (deny-by-default) + record the
   `0089` row in `django_migrations`.
2. Owner pushes `main` (api + web rebuild). No env/flag changes — the surface rides the already-ON
   `INTERVIEW_SCHEDULING_ENABLED`.
3. Post-deploy eyeball: propose times to #78 (Moven) — Rohini's released #80 siblings must now be pickable;
   send a test message from a student account and confirm the reviewer email + cockpit thread.
