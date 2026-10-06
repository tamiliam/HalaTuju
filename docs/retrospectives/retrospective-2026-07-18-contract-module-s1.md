# Retrospective — Contract Module Sprint 1 (model + service + seed)

**Date:** 2026-07-18
**Plan:** `docs/plans/2026-07-18-contract-module-plan.md` (owner-settled)
**Scope:** Backend only, ~18 files. Module INERT (nothing reads it). NO deploy —
the feature's single prod deploy is Sprint 5.

## What Was Built

- **Migration `scholarship/0103_contract_module`** — 3 new models + 3 FK
  additions (applied to LOCAL sqlite only; prod migrate-first via Supabase MCP at
  Sprint 5):
  - `ContractTemplate` (`contract_templates`) — org-owned, versioned, lifecycle
    `draft → pending_deployment → active → archived`; localised chrome (en
    authoritative); flow config; lawyer-vetting attestation; lifecycle stamps;
    `languages_available` property.
  - `ContractClause` (`contract_clauses`) — contiguous ordered clauses, plain-text
    bodies, per-language quiz JSON, `quiz_generated_model` audit.
  - `PaymentScheduleRow` (`contract_payment_schedule_rows`) — `pathway`+`variant`,
    `paid_offsets` JSON (start/count/gap in one field), derived `total`.
  - `BursaryAgreement.template` (PROTECT) + `executed_pdf_emailed_at` +
    `drive_file_url`; `ScholarshipApplication.comprehension_template` (SET_NULL).
- **`contracts.py`** — service mirroring `payments.py`/`PaymentsError`: draft-only
  authoring, `generate_quiz` (single-model Gemini seam, no downgrade, mocked in
  tests), lifecycle, T/C/Q/S/P deploy validations + W warnings, reader seams.
- **`brightpath_contract_v1.json`** fixture (no PII) + `seed_contract_template`
  command (creates a DRAFT only) + `CONTRACT_QUIZ_MODEL` setting.
- **70 tests** across `test_contracts.py` / `test_contract_validation.py` /
  `test_contract_schedule.py`.

## What Went Well

- **Fixture generated from the two live sources, not hand-transcribed.** A Node
  extractor pulled the 8 quiz checkpoints (en/ms/ta, ~inc. Tamil) straight out of
  `awardComprehension.ts`; a Python generator combined them with the live
  `AGREEMENT_CLAUSES` (en+ms) from `bursary.py`. Zero risk of a transcription typo
  in legal copy or Tamil script.
- **Acceptance criteria mapped 1:1 to tests.** Every T/C/Q/S/P rule has an
  explicit failing→passing test; the schedule test asserts the exact offsets,
  start months, and totals, and cross-checks them against `award.py`.
- **Money guard is structural.** `PaymentScheduleRow.total` is derived
  (`len(paid_offsets) × monthly_amount`), never stored, and S3/S4 validate every
  row against `award.ALLOWED_AMOUNTS` and the exact award amounts — so a schedule
  can never silently diverge from what `award.py` would pay.

## What Went Wrong

1. **The seed command's `--version` flag collided with Django's built-in
   `--version`** (argparse `ArgumentError` on first run). Root cause: `--version`
   is reserved by `BaseCommand`. First fix (custom `dest='version'`) then broke
   `call_command` in the tests, because `call_command` maps kwargs to the option
   string via the parser's opt-mapping and can't resolve a custom dest whose
   option string differs. **Fix that stuck:** rename the flag to
   `--template-version` with its natural dest `template_version`, read
   `opts['template_version']`, and call it the same way in tests. **System change
   / lesson:** never reuse a Django-reserved management-command flag (`--version`,
   `--verbosity`, `--settings`, `--pythonpath`, `--traceback`, `--no-color`), and
   avoid a custom `dest` that differs from the option string when the command is
   also driven by `call_command`.

## Design Decisions

- **`is_paid_month(row, cohort_year, month, year=None)`** — the plan's 3-arg
  signature is ambiguous over the STPM 18-month, two-calendar-year span. Added an
  optional `year` (defaults to `cohort_year`) as a strict superset: the plan's
  `is_paid_month(row, cohort_year, month)` call form still works for the common
  in-cohort-year case, and a second-year month passes `year=`. Pure arithmetic
  over `paid_offsets` — no money data invented.
- **Quiz→clause 1:1 anchoring.** The FE header comment's mapping has collisions
  (CP1 & CP8 both cite Cl.10; CP3 cites Cl.4/5). Resolved to 8 distinct candidate
  clauses (orders 1,3,5,6,7,9,10,11), documented in the fixture's `_meta`. This is
  structural metadata (clause text + quiz content are both verbatim), owner-
  adjustable on the draft — so no owner sign-off was needed on legal text.
- **Fixture consumed via the service, not `loaddata`.** The seed command flattens
  the fixture's nested `{en,ms,ta}` shape and drives `create_template` /
  `update_config` / `replace_clauses` / `replace_schedule`, so the org is resolved
  at runtime and the seed path exercises (and tests) the real authoring code.
- **Counterparty name + NRIC left blank in the fixture** (PII discipline): the
  owner fills them in the UI before deployment; T1 correctly fails until they do.

## Numbers

- +70 tests; **2798 scholarship pytest** green; 0 migration drift; `manage.py
  check` clean. `bursary.py` and `payments.py` untouched (Sprint 2 owns the
  cutover, and another agent has a reconciliation in flight there).
- Files: 1 migration, `contracts.py`, fixture, seed command, `settings/base.py`
  (1 setting), `models.py` (3 models + 3 FKs), 3 test files + 1 test helper.
