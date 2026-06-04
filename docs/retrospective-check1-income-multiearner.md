# Retrospective — Income Check-1 salary route: single → multi-earner

**Date:** 2026-06-04 · **Migration:** `0040` (additive, migrate-first) · **Status:** built + gated green;
deploy held for the user's click-test (TD-070).

## What & why
The salary (non-STR) income route was single-earner (one of father/mother/guardian + a work-status question).
Real B40 households often have several earners (both parents, or a working elder sibling carrying the family). The
route was rebuilt as a **multi-select** — *tick everyone who works* (father/mother/guardian/elder brother/elder sister)
— each contributing their own IC + (optional) salary slip + EPF. The STR route is untouched.

## Key decisions (settled with the user before coding)
1. **Siblings verify for free via the shared patronymic.** An elder brother's IC carries the *same* father's name as
   the student ("…A/L MURUGAN" on both), so `income_engine.father_relationship(student, earner_ic)` works **unchanged**
   on siblings. This closed the "borrowed payslip" hole *without* a special rule and meant sibling ICs DO get OCR'd.
2. **Dropped the forced non-earner-parent EPF** (my recommendation, user agreed). EPF only exists for *formal* jobs;
   the informal B40 earner and the homemaker have none whether they earn or not — near-zero signal, real friction.
3. **Never-block by inference**, no work-status question: IC present + no payslip/EPF → informal → `recommend` +
   interview flag, never `gap`.
4. **"Verified" = the document DATA checks out** (identities + relationships). The income *amount* / per-capita B40
   test stays a later sprint (I4). Evolves decisions.md L1787 ("human owns the non-STR income verdict") — the
   document-data verdict can now go green; the amount judgement still can't (it's out of scope).

## Engineering notes
- **Storage:** a `household_member` tag on `ApplicantDocument` (reusing the existing `parent_ic`/`salary_slip`/`epf`
  types) rather than ~15 new per-member doc types — keeps the upload/OCR/verdict machinery intact. Single-instance is
  now per `(doc_type, household_member)`; a blank-member upload (STR IC, student IC) never sweeps the tagged income docs.
- **Resolution collision (the trap):** `_ticketable_unresolved` keys tickets by `code`, one per code per application.
  Emitting `earner_ic_missing` once per missing member would collide. Fix: **aggregate** per-member gaps into one item
  with a `members` list param; the STR route also passes `members=[earner]` so the copy is uniform.
- **Member labels in copy:** `localiseParams(params, t)` (shared by the student Action Centre + officer tile) renders
  the `members` code array as localized, joined labels ("Father, Elder brother") in en/ms/ta.
- **Migrate-first:** prod was at `0039`, both columns absent, **`salary_apps=0`** → no backfill needed (the 20 existing
  income docs are STR/minor-consent, correctly left at `household_member=''`). Applied the two additive `ALTER`s +
  recorded `0040` via Supabase MCP; verified columns on the right tables + a known sanity column (lesson #8).

## Gates
659 backend pytest · 248 jest · `next build` EXIT=0 (captured separately, lesson #80) · i18n parity 1930.

## Residual / tech debt
- `earner_work_status` + `household_other_earners` columns now unused by the salary route (STR untouched) — left in
  place (deprecated, no destructive migration); drop later. The `q2`/`q3`/`q4`/`work` wizard i18n keys are likewise
  orphaned (kept for parity; cleanup later).
- Two working elder brothers can't both be represented (one "brother" slot) — accepted as rare; logged.
- I4 (income amount → per-capita need test) still deferred. Gopal income doc-coach copy still deferred.
- **Not click-tested** (TD-070) — the salary multi-select + per-member upload + officer Income tile need a live walk.
