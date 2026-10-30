# Retrospective — Student maintenance Sprint 6a: one Student communications page, and switches for the safe emails (2026-10-30)

Roadmap: `docs/plans/2026-10-29-student-maintenance-roadmap.md` (Sprint 6, first half; the owner split it — 6b,
letters, waits for an approved design). Shipped as `a1c9f85b` (feature) and `002c6ad7` (fixes for the 7 adversarial
review findings, 0 HIGH); live as api-01209-74s at about 08:20 UTC. Migration `scholarship/0189` (two new tables
and one index on `usage_events`) was applied by hand first.

## What Was Built

- **The owner's ask (2026-10-30):** "All [student communications] should be [documented], under proper headings ...
  If there is an option to switch on and off the comms (provided it won't break the workflow), the switch could be
  provided there itself ... For each comms, there are three languages. I think this could be done more compactly."
- **`student_email_catalogue.py`** — every email a student receives (29), under six headings (her account, applying,
  interview, award and contract, results, closure): senders, languages, the switch or a lock with its reason, the env
  flag that outranks it, how "last sent" is read, and the wording read from the SENDING module's own dict. A drift
  test sorts every `send_*` in `apps.scholarship.emails` into the catalogue or `NOT_STUDENT_SENDERS`.
- **Switches for the safe emails only** (owner ruling) — `StudentEmailSwitch`, no row means on; ONE gate,
  `may_send`, at every send site of the nine switchable emails; a locked key always sends, even with a row written
  behind the API; the env flags still outrank the row. `POST …/student-emails/switch/` (super, org_admin; 400
  `not_switchable`).
- **Last sent** — the worded results family from the new `StudentEmailLog`; code-owned emails from `usage_events` (the
  meter names each row after its sender), with an index for it.
- **The page** (owner ruling: layout A) — one grouped list, one row per email (not one per language), the reviewer
  panel's shape, language chips, an editor with a tab per language; the partner-access notice links to Sources.
- **Billing, forward-only** — nine student sends that metered to no organisation now run inside `usage_context`,
  and the three query emails, which left no usage row at all, are metered. No backfill (an invoiced month's basis is
  frozen); with one tenant no money moves.

## What Went Well

- The pre-flight inventory was concrete enough for the owner to rule on four questions in one reply, before a line
  of code — the layout, the switchable set, and two rulings for 6b.
- The catalogue's drift test made "every student email is documented" a property the suite holds, not a promise.
- The bite-checks (7 at build) each went red on the expected assertion.
- `sponsorship.py` (1007) and `bursary.py` (903), both oversize, were held level through both commits.

## What Went Wrong — the 7 adversarial review findings

1. **MED — "award confirmed" was switchable, but its TEXT is her onboarding step.** The pre-flight judged it a
   courtesy because no stamp or clock waits on its send. On the live path it carries the link she follows next.
   **Root cause:** switchability was decided by reading what the CODE does after the send (stamps, clocks, tasks),
   not what the EMAIL asks the student to do. **System change:** owner ruling — LOCKED (`next_step`); the gate in
   `_finalise_award` removed; nine switchable; the `next_step` reason reworded so it is true of both rows.
2. **LOW — the gate could break what it guards.** A failed switch read would have raised into a submit, a confirm
   or a sweep; a failed log write after a send would have turned a sent email into an error; one bad application
   stopped the interview job. **Root cause:** a new read on a path that was best-effort was written as if it were
   load-bearing. **System change:** `may_send` logs and SENDS on any error; the log write is fenced; the interview
   job fences each application. Each tested with an injected database error.
3. **LOW — "off" still wrote.** `results_due` claimed the term row, sent nothing, then gave the claim back.
   **System change:** the switch is asked before the claim (a test proves no UPDATE). Switching back on reaches
   every student now due or late — said plainly on the page rather than capped.
4. **LOW — a page-sized aggregate on every write.** Every switch and every save recomputed "last sent" over the
   organisation's whole usage history, and the interview job read the switch for every booking, due or not.
   **System change:** an index (organisation, service, source, created_at) in 0189; a switch answers `{key,
   enabled}`, a save the wording only; the job reads the switch only when a reminder is due, by organisation id.
5. **LOW — a failed toggle restored the whole page** from a stale copy, undoing a neighbour's switch that had
   succeeded. **System change:** set and restore ONE row.
6. **LOW — the dry run lied.** `send_query_reminders --dry-run` listed students the live run would skip.
   **System change:** it asks the switch too.
7. **LOW — an email promised what a switch could withdraw.** "Profile complete" said "with a reminder before the
   call", and the interview reminder became switchable. **System change:** the line removed (en, ms); the email
   golden regenerated for exactly that line.

**Main lesson (lessons.md):** an email's switchability is decided by what its TEXT asks the student to do — and by
what any OTHER email promises about it — not only by what stamps its code sets.

## Design Decisions

- Owner rulings 2026-10-30 (decisions.md): layout A; only the safe emails switch off (amended the same day: award
  confirmed locked); termination and suspension letters are documents only; letter PDFs in English or Malay.
- No row means on; nothing seeded; the platform env flags outrank the organisation's row.
- "Last sent" for code-owned emails reads the meter (an ATTEMPT, so a failed send can read as sent), for the worded
  family the log (successful sends only).

## Numbers

- api 10,660 passed / 3 skipped (pre-flight baseline 10,534 on `e4bad359`); web 5,270 / 329 suites (5,081); i18n
  6,259 keys per locale; first-load median 147.493 kB of 148 — **0.5 kB of headroom, no slack route left** (TD-427).
- 42 files across both commits; one migration.

## Carried Forward

- **6b, letters** — needs a design approved by the owner first (Letters tab on the file, the student's Letters tab,
  the Letters heading on the comms page). Rulings already made: documents only, PDFs in English or Malay.
- **TD-427** — the first-load median has 0.5 kB of headroom; the next student-route feature must pay for its words.
- **TD-428** — the email-verification mail is a bare `send_mail` (unmetered, never billed).
- The "your interviewer" email still says "if necessary, reminders before the call" — hedged, but the same class as
  finding 7; reword it when that email is next touched.
- The nudge and R1–R3 completion reminders stay locked until "off" can stop the stamp or ladder they unlock.
