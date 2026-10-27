# Retrospective — TD-409 (an unmatched STR never closes an STR request) (2026-10-27)

`ddd46dda` + `ddb26b60` (on `2cb9d113`) — pushed, builds running. Built in the worktree `td404-name-forms`.
Register: TD-409 closed; TD-410 raised.

## What Was Built

- **The upload's verdict.** `resolution.doc_match_verdict` gives an STR that no household card matched
  `pending`; it is red only when `str_check_names_a_stranger` proves it a stranger's. A near-miss or
  "cannot judge" STR used to read red (any positive field mismatch), or `ok` when nothing could be compared.
- **Requests are held, not closed** (owner ruling A: an unmatched STR never counts). An Action-Centre upload
  of such an STR holds every open STR request it answers for the officer (`hold_for_officer`, the "our team is
  checking" card) and answers `ok`. Both syncs hold, rather than auto-resolve, an STR request whose gap
  cleared while such an STR is live (`income_str_ownership.hold_if_str_unmatched`) — unless a working
  member's income is shown on its own, which is then what cleared it. A re-opened Check-2 request drops the
  hold (`offer_issuers.released_from_officer`).
- **The live slot.** `promotion.should_promote` keeps an unmatched STR from displacing a matched one that
  still counts (current / unconfirmed); a stale, future or rejected matched copy is replaced (TD-403).
- **Check 2** raises `str_needs_recipient_ic` for a near-miss STR with no IC number, off one STR reading
  (`str_check2_ic_asks`), Action-Centre copy en/ms/ta. No band moves; no `VERDICT_ENGINE_VERSION` bump.

## What Went Well

- **Every change was bitten** (twelve mutations across the build and the review fixes), including a false
  bite caught and re-run: a mutation that left a dangling line continuation "bit" by syntax error.
- **The query budget caught a second STR read** in the Check-2 pass at once (+1 in every shape); the two
  ownership asks now share one reading instead of raising the budget.
- **The review probes became the tests** — each finding is pinned by its exact scenario.

## What Went Wrong

1. **The first promotion guard protected a stale matched STR and undid TD-403.** Making an unmatched STR
   `pending` made it *usable* for promotion, so a guard was added: an unmatched STR never displaces a matched
   one. It never asked whether the matched one still counted. The review's probe: the father's 2025 STR
   (matched, stale) is live; the mother's 2026 STR arrives before her IC — it was refused the slot, the gate
   kept saying "your STR is from 2025", and her IC slot (read off the live stale STR) was never offered,
   before submission too. *Root cause:* a guard keyed on "matched" without "still counts" — protecting a
   document by one of its properties while ignoring the property that decides whether it is worth
   protecting. *System change:* the guard protects only a matched STR that still counts (current /
   unconfirmed), pinned by the probe's test and a test that a current matched STR is still protected; lesson
   recorded.
2. **The sync hold was scoped too broadly.** `hold_if_str_unmatched` held every open STR request whose gap
   cleared while an unmatched STR was live, even when something else cleared it (the father's payslip clears
   `income_proof_missing`): the student was told "our team is checking" about a request already answered.
   *Root cause:* the hold asked "is the live STR unmatched?" instead of "is this request open BECAUSE of the
   STR?". *System change:* no hold while any working member's income is shown on its own; a test. The check
   it reuses, `income_shown`, counts a suspect payslip — pre-existing, raised as TD-410.
3. **A hold outlived its request.** `needs_officer_eye` was never removed, so a Check-2 request that re-opened
   still showed "our team is checking" instead of the real ask. *System change:* the re-open drops the hold.
   By design, an officer's STR request already on hold stays held after a later matching card, until the
   officer closes it.

## Review (sprint-close step 4b)

Two review rounds by the coordinator. Round 1: the promotion blocker, the over-broad hold, the lingering
hold — all fixed in `ddb26b60`. Round 2: nothing blocks; notes — protecting an undated matched STR is harmless
(it already passes the gate); `income_shown` is lenient (TD-410); `released_from_officer` touches only a
re-opened Check-2 request.

## Numbers

- API 9,098 → 9,122 (+14 TD-409 tests; two older tests adjusted). Web 4,606 jest / 294 suites. Bundle budget
  ok — the median first-load JS has only **0.4 kB** of headroom under 180 kB.
- No migration. `check2_queries.py` 674 / 675; `doc_match_verdict` 186 / 187.
