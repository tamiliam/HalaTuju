# Retrospective — Org Config Sprint D: the interview grid becomes organisation-tunable

**Date:** 2026-09-07
**Worktree:** `.worktrees/org-config-sprint-d`, branch `feat/org-config-sprint-d` (base = the
Sprint C close, `5a677f91`)
**Migration:** none. Registry entries + wired read sites + rows on the existing tab.

---

## What the sprint was

The roadmap's Sprint D: `interview_duration_min`, the booking window (start / end / step),
`slot_min_lead_hours` and `reschedule_cutoff_hours` become organisation-tunable, with a standing
warning attached — *"`interviewSlots.ts` mirrors the window constants in the FE — this sprint
must serve them to the FE instead of the lock-step copy."*

That warning was written when Sprint C proved the serve-don't-mirror pattern on the role payload
and the staff list. This sprint is the third exercise of it, and the first where the mirror was
**announced in a comment** rather than discovered.

## What shipped

**Six settings, one new group.** `interview_duration_min` (30), `interview_window_start_min`
(08:00), `interview_window_end_min` (21:30), `interview_slot_step_min` (30),
`interview_min_lead_hours` (24), `interview_reschedule_cutoff_hours` (12).

**One seam serves both screens.** `interview_schedule_payload` was already the shared payload for
the reviewer's cockpit and the student's booking panel, and it already served
`reschedule_cutoff_hours`. Adding the other four there meant no new endpoint, no new fetch, and
no possibility of the two screens being served different rules.

**Two engine additions, both demanded by these settings:**

- `allowed` — a setting whose vocabulary is a LIST, not a range. The slot step must divide 60,
  because `slot_in_window` reads `minute % step`; a 45-minute grid is not a grid across an hour
  boundary. Rendered as a menu, so the constraint is in the keyboard rather than in a refusal.
- Cross-field rules (`_ORDERED_PAIRS`) — a window must open before it closes. A single key's
  bounds cannot say this.

**The clock box.** The window bounds are stored as minutes past midnight like every other
integer setting, but typed as HH:MM. The owner chose this over plain minute numbers, and the
reason is the whole point of the tab: an organisation sets a value it can read back.

## What was found on the way

**A four-way dead default.** `INTERVIEW_DURATION_MIN` had four fallbacks of **45** against a
`base.py` value of **30** — and `base.py`'s own comment says the 30 exists to match the "about 30
minutes" copy shown to students. The 45s could not fire. They were also, all four, one deleted
settings line away from putting a 45-minute block on a student's calendar under a 30-minute
promise. This is the same shape as Sprint C's SLA default and was fixed the same way: one home,
not four agreeing copies.

**The mirror that no type-checker can see.** Grepping for the constants found the code copies.
Grepping the *message files* found two more: the reviewer's caption **"Available times
(8:00am–9:30pm, 30-min)"** and the student's **"it's a short video call (about 30 minutes)"**.
Both stated the rules as fixed words, in three languages. Nothing would have failed. The screen
would have shown a 10:00–16:00 picker under a caption promising 8:00am–9:30pm, and the student
would have been promised half an hour for an interview the organisation had set to an hour.

Both are now interpolated from the served values, and a jest guard fails if a number goes back
into either sentence.

**A bug my own change introduced, caught by an existing test.** Reading the stored values through
`org.configuration` to validate the merged result cached the pre-save row on the `org` instance,
so the endpoint answered a successful save with the values as they had been. `test_null_clears_
back_to_the_platform_default` failed immediately. The fix is to read by query. Worth recording
because the failure mode — a save that looks ignored until you reload — is one a person would
report as "it didn't save", and the cause would be nowhere near the save.

## What did NOT change, deliberately

- **`RESCHEDULE_MIN_LEAD_HOURS` (2h) stays a front-end constant.** It is not a mirror of a server
  rule; it is a UI-only relaxation on a reviewer reschedule (TD-137), and the backend deliberately
  accepts any future slot on that path.
- **`InterviewSlot.duration_min` keeps its model default of 45.** Changing it needs a migration
  this sprint promised not to make, and it is never the effective value — `propose_slots` always
  writes the organisation's resolved duration. A test pins that.
- **Nothing checks duration against step.** An organisation setting a 60-minute interview on a
  30-minute grid can have its reviewer's own proposals overlap, because conflict-blocking compares
  START times only (`held_starts`). The owner was told before the sprint began and chose to ship
  it as a documented limit rather than a guard.

## Numbers

| Gate | Result |
|------|--------|
| pytest (`apps/`) | **5935** (+11; `test_org_config.py` 45 → 56) |
| jest | **1767** (+13) |
| `next lint` | 0 errors |
| `tsc --noEmit` | 24 (baseline, none new) |
| i18n | **4832 × 3** (+16 keys; ms/ta first drafts) |
| `next build` | compiled successfully |
| `makemigrations --check` | no changes detected |

Four bite-checks landed and were restored by writing the original back: the window de-orged, the
payload serving a platform constant, the cross-field rule disabled, and the browser ignoring the
served rules.

## The lesson worth carrying

Sprint C's lesson was *grep a rule's read sites across the whole product, not just the backend*.
This sprint extends it one step further: **the message files are read sites too.** A sentence that
states a value is a consumer of that value, and it is the only kind of consumer that no compiler,
type, or component test will ever flag.
