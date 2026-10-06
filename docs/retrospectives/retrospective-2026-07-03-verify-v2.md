# Retrospective — Verification-Model Roadmap Sprint V2 (Resolution Correctness)

**Date:** 2026-07-03
**Branch/worktree:** `feat/verify-v2` in `.worktrees/verify-model` (off main incl. V1)
**Roadmap:** `docs/plans/2026-07-03-verification-model-roadmap.md` (V2 of V1–V6)
**Findings source:** `docs/plans/2026-07-03-check-model-audit.md` (#3, #4, #16)
**Migration:** NONE — all logic in `resolution.py` + `check2_queries.py` + `help_engine.py` +
`documentHelp.ts`.
**Tests:** 2040 scholarship pytest (+15 net) + 412 jest (+1 documentHelp case) + tsc clean.

## What Was Built

The re-upload/resolve path must **verify what it resolves** — closing the ways a task could
auto-close on an unverified or wrong-member document.

- **#3 — a non-official offer no longer resolves an "official offer" request.**
  `doc_match_verdict`'s `offer_letter` branch now returns `'mismatch'` when
  `pathway_engine.offer_official_status(doc) == 'not_genuine'` (a conditional / private-IPTS /
  pemakluman / UPU-semakan notification). `'unknown'` (genuineness not scored — flag off / AI
  outage / not re-run) deliberately defers to the reviewer and never gates. Runs after the
  name/IC mismatch so an identity clash still wins.
- **#4a — salary_slip / epf / birth_certificate now HOLD an unread/errored read.** They had no
  pending/unreadable branch, so a Gemini error → empty fields → `'ok'` → request resolved
  unverified. Now (mirroring results_slip and V1's guardianship/income_support branches): not
  scanned (`student_verdict ∈ {'', 'review_manually'}`) → `'pending'`; read nothing/badly
  (`{'wrong_doc','unreadable','incomplete'}`) → `'unreadable'`.
- **#4b — `resolve_doc_items_for_upload` is member-aware + criterion-aware.** A member-tagged
  request (V1.3 now writes `params.household_member`) clears **only** on an upload for that
  member — a mother's payslip no longer resolves the father's request. And `income_doc_stale`
  re-checks recency (`income_engine.stale_income_proof`) before clearing, so a
  freshly-uploaded-but-still-stale slip can't silence the "send a current one" ask.
- **#4c — doc-kind Check-2 requests are re-raisable.** `sync_check2_queries`'s DOC_SPECS loop
  now re-opens a **resolved** doc-request when its gap re-fires (the proof was removed or
  replaced with a bad one), clearing the stale resolving doc/text and re-notifying. Only
  doc-kind items — clarifies stay once-ever (a typed answer isn't re-asked).
- **#16 — finished the S4 STR-coach-states unification.** `help_engine.verdict_for_document`
  and the FE `documentHelp.shouldShowCoach` hardcoded `('stale','rejected')`; both now use the
  shared `income_engine.STR_COACH_STATES` (`wrong_type / rejected / stale / unreadable /
  unconfirmed`), so a `wrong_type`/`unreadable` STR re-upload gets the doc-anchored Gopal
  instead of a silent red task.

## What Went Well

- **V2 built directly on V1's seam.** The member-aware resolve (#4b) only works because V1.3
  started writing `params.household_member`; the pending/unreadable holds (#4a) reuse the exact
  `student_verdict` pattern V1 introduced for guardianship/income_support. The two sprints
  compose cleanly — a sign the roadmap ordering (integrity → correctness) was right.
- **The STR-coach-states unification was a true one-liner each side** once `STR_COACH_STATES`
  existed (S4). The audit's "two missed consumers" were exactly that — two literals to replace.
- **Every fix keys off a signal that already exists** (`offer_official_status`, `student_verdict`,
  `stale_income_proof`, `STR_COACH_STATES`) — no new state, no migration.

## What Went Wrong

1. **Three clean-doc test fixtures broke because they modelled a "read" doc without a
   `student_verdict`.** Adding the pending/unreadable hold to BC/EPF made
   `test_birth_certificate_clean_ok` + two IC-chain tests return `'pending'` — the fixtures set
   `vision_fields.fields` but no `student_verdict`, which in production a read doc always carries.
   - *Root cause:* the fixtures pre-dated the accept path gating on `student_verdict`; they
     encoded "the check says match" without the "it actually read" signal that now matters.
   - *Fix:* set `student_verdict='ok'` on the clean-read fixtures (`_bc_doc`, `_epf_doc`, the
     resolution clean-BC test) and added explicit blank/errored companions. **System note:** when
     you make an accept path depend on a *new* field, every fixture that models the ACCEPT case
     must set that field — a fixture missing it now silently flips to the hold branch. (This is
     the V1 "tests encoded the loose version" lesson recurring one layer down — the fix tightened
     an accept, and the fixtures modelling the accept were the ones to update.)

## Design Decisions

Logged in `docs/decisions.md` (V2 block): (a) a non-official offer HOLDS (mismatch) but
`'unknown'` genuineness never gates — defer to the reviewer rather than block on our own missing
signal; (b) doc-kind Check-2 requests are re-raisable while clarifies stay once-ever — a document
gap is a live condition (proof can be removed/replaced), a typed answer is a one-time fact.

## Numbers

- 3 findings closed (#3, #4, #16); 0 migrations; ~6 files (backend 4, frontend 2).
- +15 net scholarship tests (offer official/genuine/unknown, salary hold ×3, BC hold ×2,
  member-aware resolve, stale-recency ×2, doc re-raise, STR-coach ×3) + 1 jest (STR states).
  2040 pytest + 412 jest.
