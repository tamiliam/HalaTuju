# Retrospective — WhatsApp go-live + cockpit fixes + reminder-notice gating (2026-06-21)

Covers the deliverables shipped this session **after** the request-owned-doc-slots close (`e2282bf`, its own retro).
All on `main`, deployed. Driven by a long live owner session (Twilio/Meta setup → smoke test → behaviour refinement).

## What Was Built / Shipped
1. **Cockpit date + save-draft fixes** (`9197467`) — `_validate_findings` now accepts `verdict=''` (Save-draft no longer
   400s and loses the reviewer's notes); the AI gap-spotter is told today's date (MYT) so it stops calling past events
   "future". Backend-only, no migration. +2 tests.
2. **WhatsApp comms — go-live** (`8aaef6d`/`1dfbf0a`/`d1df9de` + merge `40bf3ac`). Renumbered `scholarship/0067→0068`
   (main took 0067), migrate-first applied courses `0059` (`whatsapp_opt_in`, 99 backfilled on) + scholarship `0068`
   (`whatsapp_messages`, RLS deny-by-default), shipped DARK, then **flipped live**: owner set the two Twilio secrets in
   Cloud Run, agent set the non-secret vars + `WHATSAPP_ENABLED=1` (rev `…00490-h96`). **Smoke test delivered** the
   approved template to the owner's WhatsApp (`status: delivered`). Interview reminders (1-day + 1-hour) now send a real
   WhatsApp alongside the email, opt-in gated.
3. **Interview-reminder notice gating** (`1c15ca6`) — each reminder gates on `interview_start − interview_booked_at`:
   24h reminder needs ≥24h notice, 1h reminder needs ≥1h. Kills the wart where a same-day/last-minute booking fired an
   instant "reminder" at the next cron tick. Firing stays late-tolerant. `book_slot` now stamps `interview_booked_at` on
   every (re)booking so reschedules re-gate. All three channels (student email + WhatsApp + reviewer email). +5 tests.

## What Went Well
- **Migrate-first discipline held under a live merge race.** `0067` collided with the parallel doc-slots branch; caught it
  before merge, renumbered to `0068`, applied to prod via Supabase MCP, verified, then pushed. Zero prod breakage.
- **Dark-first go-live.** Shipped the code + schema dark, set non-secret config, then flipped one flag with a verified
  smoke test — blast radius checked first (0 due interviews at flip time).
- **Secrets never transited chat.** Non-secret env (sender number, template SID) set by the agent; the two Twilio secrets
  set by the owner in the Cloud Run console.
- **Owner's "thinking aloud" turned into a clean, tested rule** (the booking-notice reminder gate) in one pass.

## What Went Wrong
1. **`sqlmigrate` output was SQLite, not Postgres — nearly the wrong DDL to prod.**
   - *Symptom:* `manage.py sqlmigrate courses 0059` printed a full SQLite table-rebuild (`CREATE new__…; INSERT…SELECT;
     DROP; RENAME`) because the local dev DB is SQLite.
   - *Root cause:* local dev runs SQLite; prod is Postgres. `sqlmigrate` renders for the *configured* backend.
   - *Prevention:* lesson added — for migrate-first via MCP, hand-write the Postgres DDL (`ALTER TABLE … ADD COLUMN`),
     never paste `sqlmigrate` output; verify against the live schema first.
2. **Two parallel branches both grabbed migration `0067`.**
   - *Symptom:* doc-slots and whatsapp-comms each created `scholarship/0067`.
   - *Root cause:* both branched off the same `origin/main`; neither could see the other's number.
   - *Prevention:* lesson + a sprint-close habit — check `max(migration)` on `main` before merging any parallel branch;
     renumber the later one.
3. **The reminder window had no lower bound (pre-existing).** A same-day booking fired an instant "24h reminder."
   - *Root cause:* "fire when within X hours" with no floor.
   - *Prevention:* gate on the *notice the trigger gave* (`start − booked_at`), not just "is it within the window now."

## Design Decisions
- See `docs/decisions.md` → "Interview reminders gate on booking notice." (WhatsApp consent-is-implied + urllib-not-SDK
  were logged with the WhatsApp commits.)

## Numbers
- 3 deliverables, ~3 deploys (cockpit, whatsapp dark+flag, reminder-notice). Prod migrations: scholarship `0068`,
  courses `0059`. +9 tests across the three. `next build` clean; jest 363.
- WhatsApp: LIVE, smoke-test delivered. Cost ≈ RM0.09/utility message → single-digit RM/month at pilot volume.
