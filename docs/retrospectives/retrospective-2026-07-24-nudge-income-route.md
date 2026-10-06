# Retrospective — "Almost done" nudge + income-route reconciliation — 2026-07-24

Three shipped deliverables from one session, all backend-led, all live on prod. Ran alongside a
second agent's Sprint 15 (Requests) in the same repo — see "What Went Well" for how that was kept
conflict-free.

## What Was Built

1. **"You haven't submitted yet" nudge** (`e7fdc879`, migration `0110`).
   A shortlisted student who consents but never presses the final Review & submit sits in silent
   limbo. Recovery: a one-time **automatic** email ~30 min after consent (cron `application-nudges`,
   every 15 min, Cloud Scheduler `halatuju-application-nudges`), plus a **manual** org-admin button
   in the cockpit Blockers box (`AdminNudgeStudentView`, super/org_admin only) — visible-but-blocked
   before the auto fires, then live with a 24h cooldown. Fires ONLY when `consent_blockers` is empty
   (truly one press from submitting); a student who slipped back into a blocked state is excluded and
   the generic reminders own that case. `ScholarshipApplication.nudge_sent_at`; whole button state is
   server-computed (`nudge.nudge_state`).

2. **Income-route symmetric gate + silent reconcile at consent** (`1c515954`, no migration).
   Off #114: declared STR, documented salary (payslip + IC, no STR). The gate let him through
   (route-agnostic) but the AI Prediction, reading the declared route, flagged INCOME red for a
   document that wasn't missing. Two changes, together: (a) **symmetric gate** — the salary branch of
   `income_doc_blockers` now clears on a dispositive STR (`household_str_status`), exactly as the STR
   branch already clears on a complete salary cluster; (b) **`reconcile_income_route`** at consent —
   silently relabels the route to whichever evidence actually settled income (reuses
   `switch_income_route`, audit-logged, never re-blocks).

3. **Warmer "almost done" nudge email** (`b8bf2311`, copy-only).
   The automated email read like a reminder — subject said "reminder", it opened on the omission,
   and it hedged "complete any remaining steps" (inaccurate, since the nudge only fires when nothing
   is outstanding). Rewritten to lead with what the student has completed, drop "reminder", and point
   at the single last action. EN + BM; HTML bolds the key phrases, plain-text strips the tags.

## What Went Well

- **Zero-conflict co-tenancy with a second agent.** The other agent was editing the same HalaTuju
  tree (income wizard + i18n + a whole Requests feature) throughout. Every commit staged EXPLICIT
  paths (never `-A`), each preceded by a `git fetch` + `git status` check to confirm my files carried
  only my hunks. Their in-flight work was never swept; both features shipped independently.
- **Live proof, not just green tests.** The nudge cron was manually fired once post-deploy: it nudged
  the one blocker-free student and correctly skipped a stuck one — proving the "only when nothing
  outstanding" rule in production, not just in unit tests. And the whole exercise validated itself:
  #101 (Janu) submitted after her manual nudge.

## What Went Wrong

1. **The nudge email copy went out of sync with its own eligibility rule.**
   - *Symptom:* the automated email hedged "complete any remaining steps" and opened like a nag — the
     owner flagged it as reading like "yet another reminder."
   - *Root cause:* the copy was written early to work "whether or not the student had stray items,"
     then the eligibility was tightened so the nudge ONLY fires for students with nothing outstanding.
     The copy was never revisited when the gating condition changed, so it hedged about work that can
     no longer exist.
   - *Fix:* when a gating/eligibility condition is narrowed, re-read the user-facing copy that assumed
     the old, looser condition. Added as a lesson.

2. **The first income-route design didn't cover students blocked BEFORE consent.**
   - *Symptom:* the initial plan (auto-switch the route at consent) would silently fail for a
     genuinely-STR student who picked "salary" — the owner caught it ("does that mean the student is
     locked in / stuck?").
   - *Root cause:* I designed a "fix it at step N (consent)" mechanism without verifying that every
     affected student could REACH step N. A genuinely-STR salary-route student was blocked by the
     salary gate's member-IC demand and never reached consent, so the reconcile could never run.
   - *Fix:* this is exactly why the **symmetric gate** was added alongside the reconcile — the two
     belong together. General lesson: a "reconcile at step N" fix must be paired with proving the
     affected population can get to step N. Added as a lesson.

## Design Decisions

(Logged in `docs/decisions.md`.)
- **Nudge fires only when `consent_blockers` is empty**, and the manual button is visible-but-blocked
  until the auto has fired, with a 24h cooldown.
- **The salary gate honours a dispositive STR WITHOUT also demanding the relationship doc (BC)
  up-front** — the "enough to submit, officer verifies" rule; a missing BC surfaces as a soft Check-2
  item after the auto-switch, never a submission block.

## Numbers

- 3 commits, all deployed + verified live; 1 migration (`0110`, migrate-first); 1 Cloud Scheduler job.
- +27 backend tests (19 nudge + 8 income-route) + 4 jest; full scholarship suite green.

## Carry-forward

- **Shorter, punchier manual follow-up email** — a distinct second-touch template (so the human
  follow-up isn't an identical re-send). Draft written + presented; **awaiting owner approval**; not
  built or deployed.
- Tamil first-drafts for the nudge strings (`admin.scholarship.blockers.nudge.*`) — normal refine
  queue.
- #114 was manually switched to salary (data fix, pre-deploy consent); every future case is now
  auto-handled at consent.
