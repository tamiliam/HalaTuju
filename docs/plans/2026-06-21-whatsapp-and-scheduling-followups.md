# Roadmap — WhatsApp & interview-scheduling follow-ups

**Date:** 2026-06-21 · **Status:** **S1 ✅ · S2 ✅ LIVE · S3 ✅ LIVE** (Meta templates approved + env set on halatuju-api
rev …00504, 2026-06-21) · **S5 ✅ deployed** (inert until owner sets the Twilio inbound-webhook URL) · **S4 ⏸** (needs
decision: WhatsApp vs SMS, all vs opt-in). Booking confirmation is EMAIL-ONLY (dropped from WA scope). All WA templates
are EN + EN+BM variants picked by english_only.
**Source:** owner discussion 2026-06-21 after WhatsApp go-live, captured as TD-135–138 + the deferred template polish.

## Goal
Build out the interview-scheduling comms now that WhatsApp is live: nudge students to respond, make reminders richer and
more useful on a phone, relax the reschedule lead-time, and round out consent/data-quality. Each sprint is a vertical
slice, tested, ≤ a handful of files, no over-stuffing.

## External blockers (flag up front)
- **Meta template approvals** gate Sprints 2 and 3 (every business-initiated WhatsApp needs an approved template). Per the
  agreed process: **draft + sandbox-test the wording first, then submit to Meta**; the button layout only renders after
  approval. To save an approval round, **submit both new templates (Sprints 2 + 3) together** even though the code ships
  per-sprint.
- **Twilio Verify** (Sprint 4) needs Verify enabled on the Twilio account (owner one-time) + carries a small per-verify cost.

## Sprint roadmap (5 sprints)

### Sprint 1 — Reschedule lead-time relax (TD-137)
- **Goal:** when a reviewer *reschedules*, let them offer slots sooner than the 24h floor (the candidate already waited).
- **Scope:** FE only — `halatuju-web/src/lib/interviewSlots.ts` + the reviewer picker: drop the `MIN_LEAD_HOURS` floor in
  reschedule mode (use a small floor, e.g. 2h, or just "future + the existing booking cutoff"). Backend already accepts any
  future slot — no change. Tests (jest helper).
- **Acceptance:** in reschedule mode the picker offers <24h slots; first-propose still enforces 24h; backend unchanged.
- **Complexity:** low. No template, no migration, no backend.

### Sprint 2 — Proposed-slots WhatsApp nudge (TD-138)  ⭐ highest value
- **Goal:** when a reviewer proposes times, WhatsApp the student to go pick one (email alone leaves bookings stalled).
- **Scope:** new Meta template ("Hi {{1}}, your B40 interview times are ready — please choose one: {{2}}", link to the
  application page); `whatsapp.send_whatsapp(...)` in `scheduling.propose_slots` (opt-in gated; also fires on the reschedule
  re-propose); a `TWILIO_WHATSAPP_PROPOSED_CONTENT_SID` env var; tests + CHANGELOG/decisions.
- **Acceptance:** with the flag on + a consenting number, proposing slots delivers a WhatsApp that deep-links to the page;
  logged in `whatsapp_messages`; email still sends; sandbox-tested then template approved.
- **Complexity:** medium. New template (Meta), no migration.

### Sprint 3 — Richer interview reminder (Join button / Meet deep-link)
- **Scope of WhatsApp messages is fixed at two: reminders + the pick-a-slot nudge. Booking confirmation is EMAIL-ONLY**
  (owner, 2026-06-21) — NOT a WhatsApp message. S3 only enhances the existing reminder.
- **Goal:** make the reminder a one-tap "Join" from the phone.
- **Scope:** new reminder template v2 with a **CTA URL button** (dynamic suffix → the Meet code) + a code tweak in
  `send_interview_reminders` to pass the meet code into the button var + point to the new ContentSid. Tests + CHANGELOG.
  (The reminder already carries the Meet link inline/tappable, so the button is UX polish.)
- **Acceptance:** the reminder renders a tappable Join button that opens Meet; opt-in gated; sandbox-tested then approved.
- **Complexity:** low–medium. New template (Meta), no migration. *Owner decision: one Join button vs two (Join + View
  details); whether to name the interviewer in the reminder.*

### Sprint 4 — Phone verification via Twilio Verify (TD-136)
- **Goal:** let a student verify their `contact_phone` so `contact_phone_verified` becomes meaningful (data quality before
  leaning harder on WhatsApp).
- **Scope:** backend — a "send code" + "check code" pair using the **Twilio Verify API** (WhatsApp or SMS channel),
  rate-limited; flip `contact_phone_verified=True` on success; FE — a "Verify my number" control in /profile Contact
  Details. Tests. No Meta template (Verify-managed).
- **Acceptance:** a student requests a code, enters it, and their number shows Verified; wrong/expired codes rejected;
  editing the phone resets verified (already true).
- **Complexity:** medium. Owner one-time: enable Verify on Twilio. Small per-verify cost.

### Sprint 5 — Inbound STOP → opt-out sync (TD-135)
- **Goal:** when a student replies STOP on WhatsApp, record it so our `whatsapp_opt_in` matches reality (lawful + honest UI).
- **Scope:** a Twilio inbound webhook endpoint → on STOP flip `whatsapp_opt_in=False` (and START → True); secure the
  endpoint (Twilio signature); reflect in /profile. Tests.
- **Acceptance:** a STOP message flips the flag (and stops future sends); START re-enables; endpoint rejects unsigned calls.
- **Complexity:** low–medium. No template, no migration.

## Sequencing & rationale
1 (quick FE win, owner-requested) → 2 (highest value, needs template) → 3 (polish, needs template — submit its template
**with** Sprint 2's) → 4 (standalone data-quality feature) → 5 (consent completeness). 5 sprints because each is an
independently shippable, reviewable slice; 2 and 3 share the one Meta-approval round.

## NOT engineering sprints (owner / ops — tracked elsewhere)
- **Nudge student #50** — re-raise the open offer-letter request so the (now-built) notification fires. One cockpit action.
- **Owner long-leads** — R5 Trust hub real content (auditor/trustees), TD-101 sponsor fund-UX sign-off, Tamil copy review.

## Open decisions for the owner
1. Sprint 3: one "Join" button or two (Join + View details)? Include the **booking-confirmation WhatsApp** in Sprint 3 or defer?
2. Sprint 4: verify over **WhatsApp or SMS**? Verify all students, or only those who opt to?
3. Priority order OK, or pull anything forward (e.g. Sprint 4 phone-verify before the template work)?
