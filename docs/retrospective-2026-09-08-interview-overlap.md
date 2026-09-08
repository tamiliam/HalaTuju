# Retrospective — A booked hour is an hour, not a start time (TD-233)

**Date:** 2026-09-08 · **Branch:** `feat/interview-overlap` · **Worktree:** `.worktrees/interview-overlap`
**Base:** `origin/main` @ `ee9630cb` · **Migration:** none

---

## What Was Built

Conflict checking for interview times now compares **blocks**, not start times.

`scheduling.held_starts` (a set of start datetimes) is deleted and replaced by
`held_intervals` (start + the slot's own stored `duration_min`) plus `overlaps`. Five call sites
read them:

| # | Call site | Was |
|---|-----------|-----|
| 1 | `propose_slots` reviewer-conflict guard | `start in held` |
| 2 | `book_slot`, re-pick branch | `start in held` |
| 3 | `book_slot`, first-booking branch | its **own** query on `interview_start` |
| 4 | student's re-pick menu (`interview_schedule_payload`) | `start not in taken` |
| 5 | reviewer's picker (`reviewer_busy`) | the held starts, sent raw |

Call site 5 changed shape: the server now sends the **expanded** set of grid starts at which a new
interview could not begin (`blocked_starts`). The browser's rule is unchanged —
`reviewerBusy.has(value)` — so it never learns what a duration is. Serve, don't mirror.

**The defect, in one line:** a 45-minute interview at 10:00 runs to 10:45; 10:30 has a different
start; both were offered; the reviewer was double-booked for fifteen minutes, silently. Nobody
would have filed a bug — a student would have sat in an empty room.

**What was NOT built, deliberately:** a `step >= duration` fence at the registry. See Design
Decisions.

---

## What Went Well

- **The owner's arithmetic settled the design in one message.** Asked "why offer two settings if
  they must be in sync?", the honest answer turned out to be that they must NOT be in sync — and
  the worked example (45-minute interview: a 60 step cannot reach 11:30, a 45 step drifts, so 30
  is right) killed the cheap fix on the spot. Three messages of plain arithmetic beat a day of
  implementation.
- **Grepping the STATE found the fifth caller.** `held_starts` had four callers. `reviewer_conflict`
  — the error the rule raises — had five. The extra one hand-wrote its own query and would have
  kept comparing bare starts. This is the half-fixed shape that produces "but we fixed that" bugs.
- **The seam from Org Config Sprint D paid for itself.** `reviewer_busy` was already a served list
  the browser only membership-tested, so making the answer correct cost **zero lines of frontend
  logic**. Had the picker held its own copy of the rules (as it did before Sprint D), this sprint
  would have been a two-sided change with a lock-step comment.
- **No migration.** `InterviewSlot.duration_min` already stored the length and is what goes on the
  calendar invite, so the block is what the reviewer is genuinely committed to. Nothing to backfill,
  and nothing to renumber against the two branches in flight (`bc-verdict`, `brightpath-requests`).
- **Every one of the 7 new tests bit.** Three fault injections; each new test failed under at least
  one, and the whole suite went green again after each restore.

---

## What Went Wrong

**1. I recommended the fix my own debt note had already rejected — a day after writing it.**

- *Symptom:* offered the owner two options and ranked FIRST the cheap fence "step cannot be smaller
  than length". The owner's reply demolished it in four lines: that fence bans 45-on-a-30-grid,
  which is the correct setting.
- *Root cause:* TD-233's own entry, written by me on 2026-09-07, says in as many words that *"a
  naive `duration <= step` fence is NOT the fix: it forbids a legitimate configuration."* I re-read
  the entry to answer the owner's question, took the "what" and the "why it does not bite" from it,
  and re-derived the rejected option from the code because it was a fifth of the work. **Reading a
  debt note is not the same as reading its argument** — by the time you are pricing options, the
  rejected-alternatives paragraph has already scrolled past as background.
- *System change:* (a) the lesson is in `docs/lessons.md` as a habit — *treat a debt entry's
  rejected alternatives as findings and quote them back before proposing one*; (b) the refusal now
  lives **in the code that would be changed**, as a comment beside `interview_duration_min` in
  `org_config.py` telling the next reader not to add that fence and why, so it is found by someone
  editing the registry, not only by someone who opens `decisions.md`.

**2. A test asserted a count against a slot length no organisation uses.**

- *Symptom:* `test_payload_reviewer_busy_admin_only` failed after the change (2 busy starts, not 1)
  and briefly read as a regression.
- *Root cause:* the fixture called `InterviewSlot.objects.create()` with no `duration_min`, taking
  the **model default of 45** — which is never the effective value, because `propose_slots` always
  writes the organisation's resolved 30. That column was inert for conflict logic until this sprint,
  so nothing punished the inaccuracy. Making a dormant column load-bearing changes what its default
  means. (Same family as *"making a previously-EMPTY field populated is a change to every reader"*,
  2026-07-26 — here it was a previously-IGNORED column.)
- *System change:* the fixture now passes `duration_min` explicitly with a comment saying why, and
  every new test does the same. The 45-vs-30 trap keeps its warning in `halatuju_api/CLAUDE.md`.

**3. Editing three locale files through a JSON round-trip produced unrelated churn.**

- *Symptom:* a one-string copy change came out as a 3-line diff per locale — it re-indented two
  unrelated keys a previous edit had left crooked, and rewrote every line ending.
- *Root cause:* reached for `json.load` → `json.dumps` because the standing rule is *verify the
  resolved dotted path*, and a parsed document is the obvious way to do that. But that rule is about
  VERIFICATION; it does not require the EDIT to go through a serializer. A whole-file rewrite makes
  every formatting decision in the file mine.
- *System change:* reverted and used a single-line replace (the key proved unique in all three
  files), then verified the resolved dotted path by loading the JSON afterwards. Edit surgically;
  verify by parsing. They are separate steps.

---

## Design Decisions

Logged in full in `docs/decisions.md` — *"The slot step is a grid to PLACE a block on, not a cadence
to FILL"*. In brief:

- **Two settings, not one.** The owner asked whether to merge them. Rejected: length sets the
  calendar invite's end time, step sets the clickable grid. Merging forces them equal and deletes
  both the "30-minute interviews on the hour, half an hour to write notes" setup and free placement
  of a long block.
- **No fence between them, ever.** Written into the registry as well as the decisions log.
- **The block's length comes from the slot row, not from the organisation's current setting.** If
  an org changes its length tomorrow, interviews already on people's calendars keep the length they
  were booked at. The stored value is the promise that was made.
- **`booked_only` keeps the two deliberately different strengths at booking time** — a first booking
  is blocked only by a confirmed booking elsewhere (first to book wins), a re-pick by anything the
  reviewer now holds. Only the comparison moved; the hold semantics of 2026-07-02 are untouched.
- **One consequence accepted:** call site 3 now asks about the SLOT's reviewer rather than the
  application's current `assigned_to`. They differ only when a case is reassigned after its
  interview is booked, and the person holding the calendar invite is the one who must not be
  double-booked.

---

## Numbers

| Gate | Result |
|---|---|
| pytest | **6034** passed (+7), 219 subtests |
| jest | **1877** passed, 117 suites |
| `tsc --noEmit` | **24** errors — unchanged baseline (TD-221) |
| `next lint` | **0** errors |
| `check-i18n` | ALL PASSED, **4897 × 3** |
| `next build` | exit 0 |
| `makemigrations --check` | No changes detected |
| Migrations added | **0** |
| Bite-checks | 3 fault injections; all 7 new tests bit |

**Files touched: 10** — 2 backend code, 1 backend test, 3 locale strings, 4 docs.
No frontend logic changed.
