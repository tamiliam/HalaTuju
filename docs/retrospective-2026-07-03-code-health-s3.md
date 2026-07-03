# Retrospective — Code-health Sprint 3: money & comms (2026-07-03)

## What Was Built

Sprint 3 of the code-health roadmap (`docs/plans/2026-07-03-code-health-review.md`, findings
#6–#11), executed under the owner's pre-taken decisions of 2026-07-03:

1. **#6 Sponsorship lapse on contractual reject** (owner: auto-lapse). New
   `sponsorship.lapse_holding_sponsorships` called from `services.admin_reject` for the
   `contractual` bucket; `cancel_pending_decline` best-effort reinstates via
   `reinstate_lapsed_sponsorship` (balance-guarded; logged when re-funding is needed). Ledger
   untouched by design — `release_tranche` already refuses non-funded statuses (S6).
2. **#7 Award-offer email stamp only on success** in `send_award_offer_emails`.
3. **#8 Verified, not re-fixed.** Prod query: all 18 sponsorships carry `offer_emailed_at` — the
   2026-06-29 operational backfill covered it. Closed with zero data change (the lessons-file
   check prevented a redundant / risky re-backfill).
4. **#11 `send_sign_invitation_emails` gated on `BURSARY_AGREEMENT_ENABLED`** (mirrors
   `send_bursary_signing_reminders`).
5. **#9 Bank-details error mapping** — DRF field error `account_number_invalid` mapped to a
   specific trilingual message; inline `countDigits` (<5 digits) hint + save-disable mirrors the
   API floor client-side.
6. **#10 Quiz reconciled to the agreement** (owner: draft-for-review, ship dark). All 8
   checkpoints rewritten from `AGREEMENT_CLAUSES` in en/ms/ta with a clause map in the header;
   a jest guardrail pins the structure AND asserts the phantom terms (CGPA figure, 7-day window,
   upload/suspension duty) never reappear. **Owner must review the copy (especially ta) before
   `BURSARY_AGREEMENT_ENABLED` flips.**

## What Went Well

- The pre-taken owner decisions meant zero mid-sprint blocking; the prod verification for #8
  (one SQL query) avoided a pointless backfill entirely.
- The quiz rewrite could anchor every question to a numbered clause because bursary.py keeps the
  clauses as structured data — the header now documents the 1:1 map, and a test enforces the
  negative space (terms that must NOT be taught).

## What Went Wrong

- **The web `node_modules` was broken (`Cannot find module '@jest/core'`)** — jest wouldn't run
  until `npm install`. Root cause: unclear (likely a partial install from a past session); cost
  ~5 minutes. No system change beyond noting that `npm install` is the first move when jest
  fails to even load.
- **Pre-existing type errors surfaced during the tsc pass** (17: stale `.next/types` pointers to
  deleted preview pages + old TS2352 test-file casts). None in files this sprint touched
  (verified against `main`); Cloud Build builds fresh so the `.next` ones are cache artifacts.
  Left for the P3 backlog rather than scope-creeping a money sprint.

## Design Decisions

Logged in `docs/decisions.md`:
- Lapse-at-decline + balance-guarded reinstate-on-cancel (vs lapse-at-release or blocking
  contractual rejects of funded students).
- Quiz content fidelity is enforced as a negative-space test (phantom terms banned) + human
  review, not string-equality with bursary.py (paraphrase is the quiz's job).

## Numbers

- 2,006 scholarship pytest + 1,199 courses/reports + 412 jest = 3,617 tests, 0 failures
  (+9 pytest, +8 jest net new).
- No migration. i18n +1 key ×3 locales (parity maintained); quiz content rewritten in 3 locales.
- Prod data: verified only (one read query); no writes.
