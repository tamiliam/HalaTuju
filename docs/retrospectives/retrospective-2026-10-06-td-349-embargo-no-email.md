# Retrospective — TD-349, an embargoed decline reaching the student with no email (2026-10-06)

Fix, api + web (cockpit), two rounds: the build; then, after the adversarial review, the lead's
redesign of the reopen half. Built locally in the worktree `fix/td-349-embargo-no-email` (cut from
`955897e0`), **not committed, not pushed, not deployed** — the lead re-runs every gate before any push.
No migration, no model change.

---

## 1. What Was Built

* **D1 — a reopen of an embargoed decline is refused (round 2).** `reopen.reopen_decision` raises
  `ReopenError('decline_pending')` when `decline_due_at` or `pending_rejection_category` is set, after
  `not_decided` / `already_reopened` and before `reason_required` and before any write. The old
  marker-only clearing is gone. `ReopenError` carries a `.message`; the reopen view (and the two QC
  calls) answer `{error: e.message, code}` — for `decline_pending` a sentence telling the super to
  cancel the pending decline; every other code reads exactly as before.
* **The cockpit mirrors it.** `lib/decisionReopenOffer.ts` (`isDeclinePending`, `decisionReopenOffer`,
  drift-tested against `reopen.py`) decides the Decision card's header control:
  Reopen, or — while a decline is pending — the existing "Cancel the decline" (existing string,
  existing `doCancelDecline`). Drawn by `view/ReopenHeaderControl.tsx`; `view.tsx` 1354 → 1351 lines,
  `officerCockpit.ts` untouched (1650). `isCaseClosed` ↔ `review_writes_closed` unchanged.
* **D2 — the release sends before it unmasks, and claims before it sends.** For each due id, in its
  own `transaction.atomic()`: `_claim_due_decline` re-selects the row `select_for_update(skip_locked=
  True)` (PostgreSQL; SQLite ignores it) and re-checks it is still pending, still due and still
  `rejected` — otherwise skipped silently, not counted. Then `_release_one_decline` sends first and
  clears the markers only when `_send_decline_for` answers True. A raise or a swallowed mail failure
  is logged at ERROR with the id; the decline stays masked; the batch goes on; the next run retries.
  No address → released without an email, WARNING. The legacy arm that RECORDED a decline at send
  time is removed; a pending marker on a non-rejected case is skipped with a WARNING.
* **One "told" rule.** `_told_of_this_decline` (`decline_email_sent_at >= rejected_at`; no
  `rejected_at` → any stamp is told, documented) is read by the cron and by `cancel_pending_decline`,
  which now also re-reads the embargo facts under a row lock before deciding (beyond the brief — see
  §3.3).

## 2. What Went Well

* **Both defects were confirmed red before a line changed** (round 1: 30 of 39 cases and subtests
  failed on `955897e0`, each for the named reason).
* **The review's four reopen holes were closed by removing a door, not by patching four places.**
* **Every snapshot `admin_reject` can take is built** through `factories.make_application`, and the
  refusal test compares the whole row, the sponsorships, the published profile, the audit table and
  the outbox before and after.

## 3. What Went Wrong

**1. Round 1 reversed the decline inside the reopen, and that reopened INTO the funnel.**
*Symptom:* (review) a funded student reopened at `active` with the reopen flag, where Decline + Save
clears a sponsored student's award; a failed reinstatement only logged; the cancel's `via=cancel`
audit line written by a reopen; a decline from `interviewing` reaching AWAITING QC through
`cancel_reopen`.
*Root cause:* the build composed two actions with different owners (reopen = "the reviewer erred";
cancel = "undo a decision the student never saw") so that one could proceed, and the resulting states
— reopened AND funded, reopened AND restored — were states no control had been designed for. Round 1
even documented two of the consequences (the moving mask, the non-invertible cancel_reopen) as
"decided" rather than as a sign the design was wrong.
*System change:* the reopen refuses; the cancel is the one door (decisions.md 2026-10-06). Lesson
appended to the 2026-10-06 entry in lessons.md: one door per job.

**2. The brief's "send first" alone would not have caught the commonest failure.** The sender
swallows a mail failure and answers False. *System change:* `_send_decline_for` returns whether the
email went and the cron reads it; pinned by `test_a_swallowed_mail_failure_is_a_failure_too`.

**3. A cancel acting on a row loaded before the cron sent could reverse an emailed decline.**
*Symptom:* round 1's own test reopened a stale in-memory row and "reversed" a decline the cron had
sent. *Root cause:* `cancel_pending_decline` decided on the caller's in-memory copy.
*System change:* it re-reads `status`, the markers, `decline_email_sent_at` and `rejected_at` under a
row lock inside its transaction (`test_a_cancel_holding_a_stale_row_cannot_reverse_what_the_cron_just_sent`).
Not in the lead's list; small, and the mirror of the cron's claim — flagged for the reviewer.

**4. Removing the legacy arm is a behaviour change on a row nobody can see locally.** A pending
marker on a case that is not `rejected` used to be recorded as a decline at send time; it is now
skipped with a WARNING every run. No writer produces such a row since the reopen refuses, but
production was not read (no DB access). Worth one read-only count before the deploy:
`SELECT count(*) FROM <applications> WHERE pending_rejection_category <> '' AND status <> 'rejected'`
(expected 0).

## 4. The step-3 sweep — every path that clears the markers or sets `rejected`

| Path | What it does | Unmasks before the email? |
|---|---|---|
| `services/decline.py` `_record_reject` | sets `rejected`; every decline passes through it | Not by itself — masking is the caller's job |
| `admin_reject` with a window | records, then sets the markers | No — masked until the release |
| `admin_reject` with no window | records, sends at once | **Never masked**; a failed send leaves `rejected` with no email and no retry — TD-355 |
| `org_admin_reject` | records, sends at once, by design | **Never masked**; same failure — TD-355 |
| `cancel_pending_decline` | clears the markers; reverses the decline unless she was told of THIS decline | No — it un-declines, or she was already told |
| `_claim_due_decline` / `_release_one_decline` | **fixed** — claim, send, then clear | No (was yes: D2) |
| `reopen.reopen_decision` | **refuses** a pending decline | No (was yes: D1) |
| `services/intake.release_decision` | flips `submitted` to the verdict, stamps `decision_released_at`, then sends | Not an embargo, same shape: a failed send is never retried — TD-355 |
| `send_pending_decision_emails` | loops `release_decision` with no per-application `try` | One raise stops the run before the decline release — TD-355 |

Read-only users of the markers (`student_status.py`, `apply_gate.py`, `serializers_admin.py`) need
nothing.

## 5. Review findings and their answers

| # | Finding | Answer |
|---|---|---|
| 1 | A reopened embargoed CONTRACTUAL decline lands a funded student at `active`/`maintenance` with the reopen flag; Decline + Save then clears a sponsored student's award; a failed reinstatement is only logged | **Fixed by the refusal** — the reopen never runs; the cancel restores with no reopen flag |
| 2, 4 | The release is not serialised against a cancel or a second run; nothing re-checks the row right before the send | **Fixed** — per-row claim (`select_for_update(skip_locked=True)`) + re-check; the cancel also re-reads under a lock |
| 3 | `cancel_pending_decline` decides "told" with `decline_email_sent_at is None`, the cron with `>= rejected_at` | **Fixed** — one rule, `_told_of_this_decline`, read by both |
| 5 | A stamp-save failure after the SMTP accept re-sends, and a cancel in that state reverses an emailed decline | **Debt** — TD-359; recorded in decisions.md |
| 6 | A permanently failing send retries every run for ever, logs ERROR each time, and is metered each attempt | **Debt** — TD-357 |
| 7 | The `via=cancel` audit line is written inside a reopen | **Fixed by the refusal** |
| 8 | A decline from `interviewing`, reopened then cancelled, reaches AWAITING QC without the verify step | **Fixed by the refusal**; the pre-existing form (any decided `interviewing` reopen) stays as TD-356, API-only |
| 9 | The no-address release is visible only in a log | **Debt** — TD-358 |

## 6. Bite-checks

Each fault injected after a scratch backup, the named tests run, the original restored and its
SHA-256 matched. Round 1: `emb_reopen.py.bak` 8e64f6f6…, `emb_decline.py.bak` f0f66a37…; round 2:
`emb_r2_reopen.py.bak` 9885a44d…, `emb_r2_decline.py.bak` c350b37d…, `emb_r2_decisionReopenOffer.ts.bak`
4c5c972e….

| # | Guard | Fault injected | Result |
|---|---|---|---|
| a (r1) | D1 tests | `reopen_decision` clears the three markers only (the original code) | **RED** — 27 failed |
| b (r1) | D2 tests | the markers cleared and saved BEFORE the send (the original order) | **RED** — 3 failed |
| c (r1) | D2 tests | the send's return value ignored + the "already told" guard removed | **RED** — 2 failed |
| d (r2) | refusal tests | the `decline_pending` refusal disabled (reopen allowed again) | **RED** — 12 failed (9 + the view, the re-pointed reopen test, the money test) |
| e (r2) | claim tests | the re-check removed (the claim returns any row it locks) | **RED** — 3 failed (cancel after read, re-declined, live case) |
| f (r2) | told tests | the cancel back on `decline_email_sent_at is None` + no re-read | **RED** — 2 failed (older stamp, stale row) |
| g (r2) | jest | `decisionReopenOffer` offers Reopen while a decline is pending | **RED** — 3 failed (2 rule, 1 rendered) |

## 7. Numbers

* api: round 1 **7988 passed, 3 skipped**; round 2 **7990 passed, 3 skipped** (3030 subtests), once,
  11 min 36 s (a docstring-only reflow in `decline.py` after it; its three suites re-run green).
* New: `test_td349_embargo_no_email.py` 19 tests; `decisionReopenOffer.test.ts` 13; `view.decision.test.tsx`
  +2 (36 in the two files). Re-pointed: `test_decision_reopen.test_reopen_refuses_a_pending_decline`
  (it asserted the defect), `test_contractual_reject_money`'s reopen test (now: refused, no money moves).
* web: typecheck clean; lint 0 errors (17 warnings, none in a touched file); targeted jest 22 suites /
  269 tests (incl. `codeStandards`, `officerGateDrift`, every cockpit suite); `bundle-budget` ok —
  89 routes, **median 228.022 kB** against 229 (1.0 kB headroom; 4 routes within 1 kB of the median),
  `/admin/scholarship/[id]` 267 kB (not individually budgeted).
* Files: `services/decline.py` 311 → **411**, `reopen.py` 203 → **222**, `views_admin/verdict.py` 491
  (unchanged length), `view.tsx` 1354 → **1351**, `officerCockpit.ts` 1650 (untouched). New:
  `decisionReopenOffer.ts` 26, `view/ReopenHeaderControl.tsx` 42. `makemigrations --check`: no changes.
* Debt: TD-349 closed; TD-355 (C · M), TD-356 (B · M, API-only since round 2), TD-357 (D · S),
  TD-358 (C · S), TD-359 (C · M) raised.
