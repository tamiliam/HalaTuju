# Retrospective — Sponsor Portal Redesign, R5 (Trust & Transparency hub)

**Date:** 2026-06-20 · **Branch:** `sprint/r5-trust` (off `origin/main`, worktree `.worktrees/r5`)
**Scope:** BE (one new model + one read-only endpoint + one allowlist field) + FE, **migration `scholarship/0065`**,
ships dark behind `SPONSOR_POOL_ENABLED`.

## Goal
Surface the full trust story — because the whole model runs on trust. Build the **scaffold now with honest
placeholders**; content drops in over time as the organisation formalises (small-change lane, not sprints).

## What shipped
- **Trust & Transparency page** (`/sponsor/(portal)/trust`) — four sections mirroring the approved prototype:
  *Who we are* · *Governance* (3 placeholder trustee slots) · *Sources & uses of funds* (IR-style bars + totals,
  "illustrative" pill) · *Independent assurance* (FY / verified / disbursed stats + auditor line + optional report
  link). Reached from the My Giving assurance strip + a portal footer link (not a 4th tab — matches the prototype).
- **Assurance strip** on My Giving + **trust bar** on the public sponsor landing (static, honest copy — no live figures
  leaked publicly).
- **"Enrolment independently verified" badge** on student cards + detail — renders only when true.
- **Backend:** new `enrolment_verified` boolean on `ScholarshipApplication` (a BARE allowlist boolean on
  `SponsorPoolCardSerializer`); new `TrustContent` model (one active row, seeded with illustrative placeholders) read by
  a new `trust.py` service; `GET /api/v1/sponsor/trust/` (`SponsorTrustView`, flag + approved-sponsor gated). Migration
  `0065` (additive col + new table + seed RunPython).

## Design decisions (see docs/decisions.md)
- **`enrolment_verified` is a distinct field from `nric_verified`.** Identity (the person is real) ≠ enrolment (the
  place is real) — the institution-confirmation layer of the layered assurance stack. Honest default `False` until that
  process exists.
- **Editable content split: language-neutral DATA in the DB, trilingual CHROME in i18n.** The roadmap wanted "editable
  without a deploy", but the hard i18n-parity constraint forbids English-only DB copy. Resolution: `TrustContent` holds
  only owner-authored, language-neutral data (legal entity, trustee names, figures, auditor); all headings /
  placeholders / explanatory copy live in trilingual i18n. Best of both — no deploy to fill in data, parity never broken.

## Lessons applied (from docs/lessons.md)
- **Allowlist is the hard boundary:** `enrolment_verified` is a bare boolean; the leak test asserts no identity field
  (incl. school) appears even with the new field on the card.
- **Display logic in the FE:** the serializer/endpoint return raw data; the badge + bars are derived client-side (pure
  `sponsorTrust.ts`, node-env jest).
- **`next build` is the TS gate** (EXIT captured unmasked, not piped to grep): EXIT=0, `/sponsor/trust` compiled.
- **Migration numbered off `origin/main`** (0064 → 0065); read code from the worktree (`main`), never the primary
  checkout (it's on the other agent's `feature/doc-eval-harness`).
- **Own `node_modules` via `npm ci`** (the shared junction stays broken while the other agent's branch deps diverge).

## What went wrong
- **Hand-written `CreateModel` migration used `AutoField` for `id`, but the project's `DEFAULT_AUTO_FIELD` is
  `BigAutoField`.** Symptom: `makemigrations --check` wanted an extra `0066_alter_trustcontent_id`. Root cause: writing
  the migration by hand (to control the seed RunPython) and defaulting the PK type from memory. Fix: matched a recent
  `CreateModel` migration's `BigAutoField` line; added a lessons.md entry. Caught pre-commit by the `--check` gate — no
  prod impact. (Tests passed either way; this was schema-state drift, not a runtime bug.)

## Verification
- `pytest` — **8 new** (`test_sponsor_trust.py`) + **1399 scholarship green** (no regression); migration matches models
  (`makemigrations --check` clean).
- `jest` — **361** (+8, pure `sponsorTrust.ts` helpers).
- `next build` — **EXIT=0**, ✓ Compiled successfully (`/sponsor/trust` 4.13 kB).
- i18n parity — **2733 × 3** (en/ms/ta), zero diff; 40 new trust keys.
- No interactive smoke (needs an approved sponsor session; ships dark — click-through at go-live).

## Tech debt / follow-ups
- **Owner long-lead (gating real content):** appoint the independent auditor + trustee board + define attestation scope.
  The scaffold ships with placeholders; content arrives via the small-change lane (who-we-are copy + legal entity once
  registered · trustee names/bios · first real sources-and-uses figures · first auditor's report).
- **Editing path:** `TrustContent` is a DB row — editable via Supabase (no deploy). A small super-only admin editor is a
  later nicety; not built (Django admin is not exposed on this project).
- **Tamil refinement (TD-132):** the new `sponsorPortal.trust.*` + `sponsorLanding.trustBar.*` Tamil strings are
  first-drafts for the owner's refine pass.

## Next
R6 — **Standing gift / AutoSponsor** (the AutoInvest-style innovation): a new `StandingGift` model + cron allocation
hook (reuses `fund_student`; still produces an *offered* sponsorship the student must accept). The first R-sprint with a
non-trivial new model + scheduled job — open questions (cadence semantics, zero-balance behaviour, lawyer-bundle line)
to settle at sprint start.
