# Retrospective — TD-390: a skipped IC second opinion is our outage, never the student's mismatch (2026-10-25)

Commit `46b1c0bd` (rebased onto request #45, `01da2a1a`; pushed to main 2026-10-25). Built in the
worktree `ai-outage` from `f3105a5b`, with two review rounds and an owner ruling before the push.
CHANGELOG: "TD-390 — an IC whose Gemini second opinion our outage skipped is 'service down', never a
mismatch". Decision: `docs/decisions.md` 2026-10-24, item 3b (scenario B). Register: TD-390 closed;
TD-400, TD-401 and TD-402 raised.

## What Was Built

- **The mark.** `vision.run_vision_for_document` records a REQUIRED Gemini second opinion that failed on
  our side (`read_errors.is_ai_service_error`; a refusal of the image is not ours) as
  `ic_second_opinion_error` + a 72-hour `ic_second_opinion_until` (renewed by a new outage once lapsed),
  and the outcome `ic_second_opinion` (`ok` / `ours` / `theirs`). Any later outcome clears it. A re-run
  never replaces a read the second opinion completed; a re-run failing at Vision keeps the half read.
- **The gate, not looser.** `ic_identity_blockers` answers `ic_service_down` where the half read would
  block, and a half-read card passes only on a VERIFIED NRIC.
- **Readers say pending, each about its own card.** The parent-IC check, the cluster coach,
  `doc_match_verdict`, the unreadable / red blockers, the STR / birth-certificate / guardianship /
  payslip cross-checks, both verdict income routes, the identity verdict, the help coach, the student's
  chips, `identity.compare`, the officer anomalies. `VERDICT_ENGINE_VERSION` 2026-10-25.1.
- **Owner ruling (scenario B, option A).** An STR we cannot judge only because the earner's own card is
  half-read blocks the income gate with the existing "try later" copy on both routes
  (`income_str_ownership.str_pending_blocks_submission`) — never passes, never `str_not_household`.
- **Expiry.** `ic_second_opinion_deferred` counts only inside the window; past it the stored read is
  complete again and every mismatch, "unreadable" and flag returns.
- **Self-heal and alert.** The hourly sweep re-runs marked ICs under `read_retry`'s gate; the outage alert
  counts a required second opinion as a Gemini attempt, by the IC's own read stamp.

## What Went Well

- **The design was the owner's before a line was written** (mark, honest gate, pending readers, sweep,
  alert), so the reviews argued about scope, not direction.
- **Every fix was bitten.** Each of the build's 24 fixes and each review fix was reverted by a
  fault-injection script (original bytes restored and digest-checked) and its own test went red. Silent
  or mis-landed bites were found and fixed in the same round: an injection that broke the module's
  syntax, a needle that missed an LF-only file, the IC branch of `doc_match_verdict` that no test reached,
  and a salary-route test that only compared two equal answers.
- **The per-reader table** made the review checkable: every reader of an IC read was listed with what it
  does now, so the reviewer could see the one that was scoped wrongly.

## What Went Wrong

1. **Round 1's STR check let a stranger's STR pass on another member's deferred card.** The household
   match turned a recipient mismatch into `no_ref` when ANY household IC carried the mark, so a cleanly
   read father's card that disagreed with a stranger's STR was overruled by an unrelated mother card
   still awaiting its second opinion — the gate that blocks today (`str_not_household`) passed.
   *Root cause:* the deferral was written as a property of the HOUSEHOLD rather than of the one
   comparison it defers; every other converted reader compared one card, and the one reader that
   compares several was given the same one-line guard. *System change:* the hold now applies only when
   the earner's own card is half-read and no clean card was compared on that field; every converted
   reader was re-audited for the "any marker anywhere" shape; regression tests pin the reviewer's
   scenario on both routes (and scenarios B and C); lesson recorded.
2. **The marker never expired.** `ic_second_opinion_deferred` ignored its own deadline, so after the
   sweep gave up every reader would have suppressed for ever: mismatches, "unreadable", the under-age
   guardian flag, and a student stuck on "try later". *Root cause:* the window was built for the SWEEP
   (when to stop re-reading) and never for the READERS (when to stop deferring) — two consumers of one
   deadline, and only one was written. *System change:* the predicate reads the window; past it the
   stored read is complete again (frozen-clock test at 71 h and 73 h); a new outage on a lapsed mark
   starts a new window; lesson recorded.
3. **A vacuous anomaly test.** `test_no_officer_anomaly_is_raised_off_half_a_read` asserted
   `'vision_nric_mismatch' not in [a.code for a in detect_anomalies(...)]`, but `detect_anomalies` returns
   DICTS: on any non-empty list the comprehension raises, and on the empty list it asserts nothing — the
   round-1 bite that "turned it red" did so by an AttributeError, not by the assertion. *Root cause:* a
   negative assertion with no positive control, written against an assumed return shape. *System
   change:* both tests read `a['code']`; the negative test now has a positive control (the same read with
   the mark removed DOES raise the flag) — the H19 rule "pair every negative with a positive" applied.

## Review (sprint-close step 4b)

No `/code-review` run, by the coordinator's instruction: two adversarial review rounds and an owner
ruling, each answered in full in the worktree —
- **Round 1 (3 findings):** the "any marker anywhere" STR shape (blocker); a half-read own IC passing on a
  matching name with no NRIC; the marker never expiring. All fixed and bitten.
- **Round 2 (3):** scenario B (owner ruling A: block with `ic_service_down`, never pass, never blame);
  renewing the window on a new outage; TD-401 raised for the pre-existing name-without-NRIC pass. Fixed
  and bitten; TD-401 left for its own sprint.
- **Final review:** TD-402 raised by the lead (a stranger's STR via a re-pointed earner whose IC was never
  uploaded — pre-existing).

## Numbers

- API (`python -m pytest -q -n auto -p no:cacheprovider`): 8,659 → 8,687 passed / 3 skipped in the
  worktree (`test_td390_ic_second_opinion.py`: 28 tests); 8,698 / 3 skipped on the rebased tree.
- Web (`npm run gates`, on the rebased tree, by the lead): 4,420 jest / 275 suites, gates green (no web
  change).
- No migration. `VERDICT_ENGINE_VERSION` 2026-10-25.1. Register: 132 open.
