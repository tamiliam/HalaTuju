# Retrospective — STPM offer no longer blocks submission — 2026-07-20

## What Was Built

A Form-Six (STPM) student whose offer document can't be machine-verified is no longer blocked at
the submission door. `_offer_blocks` (the submission/consent gate) now returns `False` for
`chosen_pathway == 'stpm'`, so the student submits and reaches a reviewer; the pathway may sit red
for the reviewer to audit by hand. Presence of an uploaded offer document is still required; only
the *genuineness* block is lifted, and only for STPM.

## What Went Well

- **Precise diagnosis before touching code.** The owner first framed it as "train the AI to accept
  the letter" / a verdict-colour issue. Reading the gate showed the real block was
  `offer_not_official` in `consent_blockers` — a *submission* gate keyed on the pathway verdict band,
  not the verdict card. Fixing the actual gate (not the AI model) was a one-function change with no
  model retraining, no migration, no doc-recognition MODEL_VERSION bump.
- **Contained blast radius.** `_offer_blocks` is defined once and called once; a single early-return
  solved it. The completeness gate is presence-only, so no second site needed changing.
- **Kept the guardrail.** Presence is still enforced — the test asserts an STPM student with nothing
  uploaded is still gated — so the change opens the door for genuine cases without letting empty
  applications through.

## What Went Wrong

- Nothing broke. One process note: the first response over-focused on the offer-genuineness / verdict
  machinery (green/blue bands) before confirming what the owner actually wanted. **Root cause:** I
  answered the literal "train the AI" question before locating the concrete blocker. **Prevention:**
  for a "this is blocking X" report, find and read the actual gate code first, then advise — the fix
  is often a policy gate, not the model the question names.

## Design Decisions

- **Exempt STPM only, keep presence** — see `docs/decisions.md`. Matriculation deliberately stays
  strict (it gets a recognisable official offer); presence stays required so the reviewer always has
  a document to audit.

## Numbers

- Files touched: 2 (`services.py`, `test_consent.py`). Commit `2acb84a3`.
- Tests: full scholarship suite 2908 pass (1 new consent test). No migration.
- Deploy: api-only Cloud Build (backend change; web trigger path-filtered out).
