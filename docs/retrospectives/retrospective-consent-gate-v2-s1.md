# Retrospective — TD-085 Sprint 1: Consent gate v2 (route-aware, strict)

**Date:** 2026-06-05 · **Migration:** none (pure logic) · **Status:** SHIPPED + DEPLOYED.
**Spec:** `docs/scholarship/consent-gate-v2-plan.md`.

## What was built
The consent/submission gate (`consent_blockers` + `application_completeness`) became **route-aware and strict**:
- **Offer letter compulsory** for everyone (`offer_letter_missing`).
- **STR route** → STR doc + earner IC + (mother→birth cert / guardian→guardianship letter; father via patronymic).
- **Salary route** → for EACH selected working member: their IC + their **salary slip** (EPF no longer substitutes) +
  the relationship doc.
- Replaced the old flat "any one of {str, salary_slip, epf}" rule with `services.income_doc_blockers`, sourced from the
  wizard's own `income_engine.income_requirements` — ONE source of truth, so the consent blockers and the student's
  checklist can never disagree.
- The per-member salary slip was promoted optional→compulsory in both the backend (`salary_member_blocks`) and the FE
  mirror (`incomeWizard.ts`).
- **"Never-block" moved to the officer/interview verdict only** — submission now hard-blocks.
- **Grandfathered:** the strict bar applies only to not-yet-submitted apps (keyed on `profile_completed_at`); the 6
  already-submitted apps keep the old looser bar, so `revert_if_profile_incomplete` never rolls them back on the new
  rules. They're resolved at Check 2 / interview.

## What went well
- **One source of truth held.** Building the gate off `income_requirements` (lesson #115) means the gate, the student
  wizard checklist, and the eventual officer panel (S2) all render the same requirement logic — no parallel re-derivation
  to drift.
- **The grandfather mechanism is a single clean predicate** (`profile_completed_at is None` → strict, else lenient)
  inside `application_completeness`, so every caller (confirm, consent, revert) gets the right behaviour for free.
- **Running the FULL suite caught the drift.** A new-tests-only run would have looked green; the full run surfaced 14
  failures in older test helpers immediately (lesson #48 working as intended).

## What went wrong
1. **Changing the completeness gate broke 14 tests across 4 files at once** — `_make_ready` (test_consent), `_make_complete`
   (test_details), `_complete` (test_phase_c), `_complete_app` (test_admin_scholarship), plus the income-proof and
   salary-block assertions.
   - *Root cause:* "a complete application" is encoded **independently in many test helpers**, each hard-coding the old
     document set (`ic + results_slip + parent_ic + str`). There's no single shared fixture, so a gate change invalidates
     all of them simultaneously and there's no compile-time link to find them.
   - *System change (lesson added):* when changing the completeness/consent gate, **grep for every "complete-app"
     builder** (`_complete`, `_make_complete`, `_make_ready`, `_complete_app`, any helper that creates the compulsory
     doc set) and update them in lockstep in the same sprint — and always run the full suite, never new-tests-only. This
     sharpens lesson #48 with the concrete smell (many parallel fixture builders for one concept).

## Design decisions (settled with the user this session)
1. **Hard-block to submit; "never-block" lives only at the interview verdict.** Supersedes the *income never-block*
   decision (decisions.md, Income Check-1) at the **submission** layer; the principle still holds at the verdict layer.
2. **Salary slip only — EPF does not substitute** (EPF = accumulated savings, not current income).
3. **Offer letter compulsory for everyone.**
4. **Grandfather already-submitted apps** via `profile_completed_at` (no flag/migration needed).
5. **Document-first verdict DROPPED — the route stays authoritative.** The strict gate + manual slotting prevent the
   route/doc mismatch document-first was meant to fix; reversing the (2026-06-05) "verdict must become document-first"
   reframe deliberately.

## Numbers
- **697** scholarship pytest (+10 new `TestIncomeGateV2`) · **1037** courses/reports pytest (no drift) = **1734** total.
- **250** jest · `next build` EXIT=0 · i18n parity **1985 × 3**. No migration. 13 files.

## Residual
- **S2** — the officer Documents-panel redesign (the visual half of TD-085).
- The consent `income_proof_missing` i18n key is now an orphan (no longer emitted) — harmless; drop in a future cleanup.
- Parked future feature (not TD-085): the post-consent summary page + "lock at Continue".
