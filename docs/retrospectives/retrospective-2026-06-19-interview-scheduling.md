# Retrospective — Interview scheduling arc (Calendly picker + emails + cancellation) — 2026-06-19

A long live-review arc on the in-app interview-scheduling surface: the reviewer's propose UI,
the student's booking panel, and every interview email. Worktree `.worktrees/sched` (branch
`feat/interview-scheduling`); 12 commits `a68b442` → `7fcb82d` on `main`. One additive
migration (`scholarship/0063`, applied migrate-first via Supabase MCP).

## What Was Built

1. **Calendly-style propose picker** (`InterviewScheduleCard.tsx` + `lib/interviewSlots.ts`,
   mirrored in `scheduling.py`): month calendar + 12-hour time pills, **08:00–21:30 MYT on
   30-minute steps**, **24-hour minimum lead** (`MIN_LEAD_HOURS`/`SLOT_MIN_LEAD_HOURS`).
   **Exactly 3** required; existing proposals **pre-load**; re-proposing the same set sends
   **no email** (dedupe). Replaced the bare 24h `datetime-local`.
2. **Reviewer-wide conflict blocking**: times the reviewer already holds for another student
   (proposed/booked) are greyed in the grid (`reviewer_busy`, admin-payload only) and rejected
   server-side (`reviewer_conflict`), plus a booking race-check. **Self-reschedule kept.**
3. **Locked "Proposed times" view** once proposed, with **Propose alternative times**
   (reopens the picker pre-loaded), **Cancel**, dustbin remove icon, bigger ‹ › arrows, and a
   **state-aware subheader** (first-time vs revising; quiet when locked/booked/cancelled).
4. **All interview emails → HTML primary + plain-text fallback, bilingual EN+BM** with an
   `english_only` gate, **From `interview@halatuju.xyz`**, an anti-scam note. Redesigned:
   reviewer-assigned ("what happens next", names the interviewer, no contact), pick-a-time
   (button), **booked** (details table + **Add-to-calendar button + attached `interview.ics`**
   + linked "application page"). New reviewer "needs different times" notice.
5. **In-app "request other times" loop** (closes a dead-end): the student's panel has **Ask for
   other times** (+ optional note) → records the request (migration `0063`:
   `interview_alternatives_requested_at`/`_note`), emails the **assigned reviewer directly**,
   shows an amber banner with the note in the cockpit; proposing a fresh menu clears it.
6. **Cancellation fixes**: `cancel()` voids the whole menu + clears booking pointers;
   `propose_slots()` lifts a prior cancellation back to awaiting-a-pick (the sticky-`cancelled`
   dead-end). The booked panel's **Cancel** is now **"Cancel interview" with a confirm step**;
   guardian copy aligned to the emails (minor must be present; drop the misleading "from home").
7. **Scoped unsubscribe safeguard**: interview emails carry our own harmless
   `List-Unsubscribe` (a `mailto:help@`, no one-click) so a mistaken click can't trigger the
   ESP's auto-suppression; all other email classes keep Brevo's default.

## What Went Well

- **One shared slot rule** (`lib/interviewSlots.ts` + a `scheduling.py` mirror) kept the picker,
  the student side, and the server validation in lock-step — no drift between the window/step/lead.
- **Migrate-first** (`0063`) was clean and additive; prod verified before the code push.
- Every change shipped with tests + a local screenshot, and was **investigated from the data**
  (reversed the `pool_ref` alias to find the app id; read the live #16 record) rather than guessed.
- The server guards (`reviewer_conflict`, `too_soon`, `invalid_slot_time`) live at the input
  boundary, so the picker can't be bypassed by a crafted request.

## What Went Wrong

1. **Local previews were non-interactive (dead clicks) for two rounds.**
   - *Symptom:* clicks in the dev-server preview did nothing; console showed `ChunkLoadError`.
   - *Root cause:* I ran `npm run build` (production artifacts) and then `npm run dev` in the same
     folder, corrupting `.next` so chunks failed to load and hydration broke.
   - *Fix:* clear/relocate `.next` when switching between `build` and `dev`. Captured in lessons.md.
2. **"Still seeing the old labels" on #16 after a fix deployed.**
   - *Symptom:* owner saw the broken cancelled state on #16 even though the build was live.
   - *Root cause:* a state-machine code fix does **not** repair records already in the bad state;
     #16 had been left mid-bug from an earlier test.
   - *Fix:* repaired #16 via MCP to the clean state. Lesson: pair a state-bug fix with a data
     repair for affected records. Captured in lessons.md.
3. **`.ics` builder crashed twice (NameError, then TypeError).** `emails.py` doesn't import
   Django's `timezone`, and `from datetime import timezone` is the *class* (`.utc` needed).
   - *Caught by tests before deploy* — root cause: assumed an import; fix: tests covered the new
     helper. No further action.
4. **`preferred_call_language` read off the wrong model.** Assumed it sat on the application; it's
   on `StudentProfile`. Caught by a test. Minor; the lesson (verify which model owns a field) is
   already standard.

## Design Decisions (logged in decisions.md)

- 24-hour minimum scheduling notice; exactly-3 compulsory; in-app request-alternatives over an
  email reply; all interview comms From `interview@`; harmless `List-Unsubscribe` scoped to
  interview mail (Brevo auto-adds it); the `english_only` gate (app-language + no Malay/Tamil call
  preference + A/A+ SPM English).

## Numbers

- Backend: 1361 scholarship pytest (the arc added ~30). Frontend: interviewSlots + i18n guardrail
  green; `next build` clean each round.
- 12 commits; 1 migration (`scholarship/0063`, additive, migrate-first); ~8 deploys across the arc.
- **Carry / owner action:** Brevo **List-Help on transactional** (account-wide unsubscribe fix);
  optionally extend the `mailto:` unsubscribe safeguard to the decision + application-reminder
  emails; reminders + cancelled student emails not yet on the HTML/bilingual standard.
