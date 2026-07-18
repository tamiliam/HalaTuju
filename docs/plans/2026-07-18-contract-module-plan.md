# Contract Module — Implementation Plan

## Context

The bursary agreement (contract text, quiz, payment schedule, signatory, party rules) is hard-coded in `apps/scholarship/bursary.py` constants and a static frontend quiz file. Every org or lawyer change is a code change. This module makes the contract an **org-owned, versioned, self-help artifact**: the org admin authors it, records the lawyer vetting, and submits it for deployment; a super deploys it. The existing signing flow (`BursaryAgreement`, dark behind `BURSARY_AGREEMENT_ENABLED`) stays — only its source of truth changes. PRD: `Production/HalaTuju/docs/scholarship/contract-module-brief.md` (committed).

Repo: `C:\Users\tamil\Python\Production\HalaTuju` (API `halatuju_api/apps/scholarship/`, web `halatuju-web/src/`). Prod reality: zero signed agreements; 30 awarded students being paid monthly by the live payments module — **the monthly runs must not regress**.

## Owner decisions (locked)

1. **Deployment language, not approval**: `draft → pending_deployment → active → archived`. Org admin authors, records the lawyer-vetting attestation (who + date), submits for deployment; a **super deploys** (previous active auto-archives).
2. **English is authoritative** — lawyer vets English only; ms/ta are courtesy translations. Publish requires complete English; a language is offered only when fully translated. Renderer auto-injects an "English version is authoritative" notice.
3. **Schedule is part of the template and versioned with it.** A student is governed by the version they signed, forever. On execution, the signed PDF is emailed to student + witness + org admin AND stored in Google Drive (Supabase bucket copy stays).
4. **Quiz is Gemini-constructed, self-help**: the author selects (flags) clauses; **Gemini 2.5 Pro or better** generates each question in en/ms/ta (from the clause's own translation when present, else from English); the author **reviews/edits/regenerates** before deployment. Deploy validation still enforces structure. No silent downgrade to a lesser model — if the configured model is unavailable, error, don't degrade.

## Data model — migration `scholarship/0103_contract_module.py` (next after 0102)

**`ContractTemplate`** (db `contract_templates`): `organisation` FK PROTECT · `version` (unique per org) · `status` (draft/pending_deployment/active/archived) · localised `title_/preamble_/progress_standard_` `en/ms/ta` (en required) · flow config: `counterparty_name/title/nric` (NRIC never in fixtures), `counterparty_notify_emails`, `parent_role` (co_signer_all|minor_only), `parent_pin_required`, `witness_policy` (none|optional|required) · attestation: `vetted_by_name`, `vetted_on`, `vetting_attested_by_email/_at` · lifecycle stamps: `created_by_email`, `submitted_by_email/_at`, `deployed_by_email/_at`, `archived_at`. Property `languages_available` (en + each fully-translated language).

**`ContractClause`** (db `contract_clauses`): `template` FK CASCADE · `order` (unique per template, contiguous 1..N) · `heading_en/body_en` (authoritative) + `_ms/_ta` blank · `is_quiz_candidate` · `quiz_en/quiz_ms/quiz_ta` JSON `{tag, plain, question, options[3], correct:0-2, why}` (matches FE `QuizCheckpoint`) · `quiz_generated_model` CharField blank (audit: which Gemini model drafted it; blank = hand-written/seeded). Bodies are **plain text** (blank line = paragraph) — no rich text in v1 (xhtml2pdf safety).

**`PaymentScheduleRow`** (db `contract_payment_schedule_rows`): `template` FK · `pathway` + `variant` ('' | 'continuing', unique together per template) · `label_en/ms/ta` · `monthly_amount` · `start_month` (1-12) · `paid_offsets` JSON (sorted 0-based month offsets — covers start, count, and gap/exam months in one field) · `sort_order`. Total = `len(paid_offsets) × monthly_amount`, derived never stored. Seed rows reproduce today exactly: RM200; start months stpm/matric/asasi=7, poly/university=8, pismp=9; stpm 15 paid months (with Dec+Jun gaps), continuing-stpm 5, default 10.

**Existing models**: `BursaryAgreement.template` FK PROTECT null (keep `version` CharField, filled from template) + `executed_pdf_emailed_at` + `drive_file_url`. `ScholarshipApplication.comprehension_template` FK SET_NULL null — pins which version the quiz pass covered.

## Service — new `apps/scholarship/contracts.py` (mirror `payments.py` + `PaymentsError` shape)

- Authoring (all refuse `status != 'draft'` → `not_draft` — the immutability guarantee): `create_template` (with `copy_from` clone), `update_config`, `replace_clauses` (atomic PUT, shape+order validated), `replace_schedule`, `record_vetting`.
- **Quiz generation**: `generate_quiz(clause)` — calls Gemini via the existing seam pattern in `apps/reports/report_engine.py` (settings `GEMINI_API_KEY`, base.py:121); new setting `CONTRACT_QUIZ_MODEL` default `gemini-2.5-pro` (no downgrade fallback); strict-JSON prompt returns all three languages; output validated (Q2–Q4 below) before saving to the clause; draft-only; billable → on-demand endpoint, never automatic. Mocked in tests like the reports tests.
- Lifecycle: `validate_for_deployment` → `submit_for_deployment` (draft→pending_deployment) → `revert_to_draft` → `deploy` (SUPER only; atomic: archive previous active).
- Readers (the seams): `active_template_for(org)` · `template_for_application(app)` (signed agreement's pinned template, else org's active) · `schedule_row_for(template, app)` (pathway + 'continuing' via `award._stpm_continuing`, fallback variant='' then 'default') · `is_paid_month(row, cohort_year, month)` · `schedule_summary_text` / `schedule_table(locale)` · `quiz_checkpoints(template, locale)` (whole-quiz en fallback) · `resolve_locale`.
- `render_preview_html(template, locale)` (sample particulars, PREVIEW banner) · `distribute_executed_agreement(agreement)` (below).

## Deploy validations (`validate_for_deployment`)

Errors: T1 version/status/counterparty present · T2 attestation recorded (the lawyer gate) · C1 clauses contiguous · C2 English complete on every clause · Q1 ≥1 quiz candidate · Q2 every candidate's `quiz_en` structurally valid (3 options, one correct — the old jest invariants moved server-side) · Q3 no quiz payload on a non-candidate clause (question can't outlive its clause) · Q4 per-language quiz parity + same `correct` index · S1 rows exist incl. `('default','')` · S2 row shapes valid, no dupes · S3 each row total ∈ `award.ALLOWED_AMOUNTS` · S4 totals cross-check `award.py` (stpm=3000, continuing=1000, default=2000) — kills "signs one schedule, paid another" · P1 v1 fence: `minor_only` / `witness_policy='required'` → `unsupported_in_v1`.
Warnings (deploy panel): W1 term-scan (e.g. "guarantor" text while co_signer_all) · W2 per-language missing-field list (drives `languages_available`) · W3 RM literal in a clause body contradicting the schedule.

## Engine cutover (`bursary.py`)

- `particulars_for(app, template)`: schedule text from `schedule_summary_text`; progress standard + counterparty from template (settings fallback only when template is None). Frozen `BursaryAgreement` columns unchanged.
- `render_agreement_html(..., template, locale)`: title/preamble/clauses from template (per-field en fallback); Schedule 1 rendered as a **table** from schedule rows (gap months shown "exam month — no payment"); party-block wording driven by `parent_role` (engine strings, i18n in code → config and text agree by construction); auto-injected English-authoritative notice; footer shows version + "Vetted by {name}, {date}".
- `sign_agreement` (bursary.py:440): resolve template via `template_for_application`; flag-on + none → `BursaryError('no_active_template')`; **lockstep**: `app.comprehension_template_id == template.id` else `comprehension_stale` (runtime quiz↔contract guard); locale via `resolve_locale`; store `template` + `version`.
- `_regenerate_artefact` (bursary.py:600): passes `agreement.template` — safe because non-draft templates are immutable.
- `foundation_notify_emails`: prefer template `counterparty_notify_emails`.
- Constants (`AGREEMENT_TITLE/PREAMBLE/CLAUSES`, `DEFAULT_PAYMENT_SCHEDULE`, `DEFAULT_PROGRESS_STANDARD`) removed only in Sprint 5 after a render-diff parity test.

## Quiz becomes API-served

- New student GET `/scholarship/comprehension-quiz/?locale=` → `{template_version, locale_used, checkpoints}` (shape = existing `QuizCheckpoint`, awardComprehension.ts:23-33). Existing pass POST (views.py:1432) gains `{template_version}`; mismatch → 409 `version_changed` (re-take); pass stamps `comprehension_template`.
- `components/AwardComprehensionQuiz.tsx`: fetch on mount, same render. Static `CHECKPOINTS` deleted in Sprint 4 (content captured in the seed fixture first); jest guardrail file replaced by a slim component test — content invariants now live server-side (Q2–Q4 + pytest).

## Payments integration (no regression to live runs)

- New `_schedule_row(app)` in `payments.py`: pinned/active template row, `None` → legacy path byte-identical to today (`MONTHLY_RATE` 200, `PATHWAY_PAYMENT_START_MONTH` — both **stay** as fallback).
- `default_amount` (payments.py:94) uses `row.monthly_amount`; `_pathway_payment_start` (115) uses `row.start_month`; run build greys out `gap_month` / `schedule_complete` items with reasons.
- Seeded rows are behaviour-identical through Nov 2026; **first divergence = Dec 2026 STPM exam-month skip** — explicit owner-confirm item in the go-live runbook, visible as reviewable greyed skips before any run is signed.

## Execution distribution

Hook where `_notify_agreement_executed` fires (`countersign_foundation` bursary.py:560, `record_witness` :579): `distribute_executed_agreement` — best-effort, idempotent via stamps: (1) `storage.download_object(pdf_storage_path)`; (2) attach PDF: extend `send_agreement_executed_email` (emails.py:959) + new `send_executed_copy_email` to witness contact + org admins — pattern `_send_html(attachments=[(name, bytes, 'application/pdf')])` (emails.py:2267); (3) Drive: new `sheets.write_contract_pdf` cloning `write_payment_csv` (sheets.py:265), setting `CONTRACTS_DRIVE_FOLDER` (default `'04 Contracts'`), name `app{id}_bursary_agreement_{version}.pdf`, store `webViewLink` → `drive_file_url`; (4) `send_signing_reminders` cron (bursary.py:728) retries missing stamps.

## Admin API + frontend

Endpoints (new `_ContractsBase(_AdminBase)` cloning `_PaymentsBase` views_admin.py:1862; URLs after payments block urls.py:179; org fence 404 cross-org; gate super/org_admin, **deploy super-only**):
`contract-templates/` GET+POST · `<pk>/` GET+PATCH · `<pk>/clauses/` PUT · `<pk>/clauses/<order>/generate-quiz/` POST (Gemini, draft-only) · `<pk>/schedule/` PUT · `<pk>/vetting/` POST · `<pk>/validate/` GET · `<pk>/submit/` POST · `<pk>/revert/` POST · `<pk>/deploy/` POST · `<pk>/preview/?locale=&format=pdf` GET · `<pk>/quiz-preview/` GET.

Frontend (Stitch prototype first, owner approval before code): "Contracts" card in Administration ORGANISATION grid (`admin/administration/page.tsx`); `admin/contracts/page.tsx` (template list, status chips, New-version copy-from); `admin/contracts/[id]/page.tsx` tabs — `ContractConfigForm`, `ClauseEditor` (ordered, en|ms|ta tabs), `QuizEditor` (flag clause → "Generate with Gemini" → review/edit/regenerate per language), `ScheduleEditor` (month-grid → offsets, live total vs award check), `TemplatePreview` (iframe srcDoc, locale + PDF), `DeployPanel` (validation checklist, attestation form, Submit; Deploy button super-only). API fns in `lib/admin-api.ts`; i18n `admin.contracts.*` en/ms/ta.

## Seeding

Fixture `apps/scholarship/fixtures/brightpath_contract_v1.json`: clauses en+ms from the (concurrently reconciled) `AGREEMENT_CLAUSES` (no Tamil clauses exist today — fine, English-authoritative), the existing **hand-reconciled 8 quiz checkpoints en/ms/ta** from awardComprehension.ts mapped to their clauses (header comment documents the mapping) — do NOT regenerate these with Gemini; generation is for future versions/orgs. Schedule rows per the table above. No PII in the fixture.
Command `seed_contract_template --org brightpath --version 2026-v1 --fixture ...` creates a **draft only** — owner fills counterparty NRIC in the UI, records attestation, submits; super deploys. Runbook order: deploy code → migrate (Supabase MCP migrate-first) → seed draft → attest → deploy template → verify payment-run parity → (later, separate owner decision) flip `BURSARY_AGREEMENT_ENABLED`. `bursary_e2e` gains seed+deploy.

## Deferred from v1

PDF/Word upload as reference · `minor_only` + `witness_required` enforcement (config exists, P1 refuses) · rich text · `effective_from` scheduled activation · formal novation record (new version covers Suresh→Foundation) · Tamil PDF font (quiz/preview ta fine; contract PDF ta needs a font spike).

## Sprints (5; merge continuously — module inert; ONE prod deploy at end of Sprint 5)

1. **Model + service + seed** (~18 files): migration 0103, `contracts.py` (authoring, lifecycle, validations, readers, `generate_quiz` with mocked Gemini seam), fixture + seed command, `test_contracts.py` / `test_contract_validation.py` / `test_contract_schedule.py`. *Accept:* seeded BrightPath draft reproduces today's constants + schedule table; every validation rule has failing→passing test; non-draft mutation raises; deploy archives predecessor atomically.
2. **Engine cutover** (~20 files): bursary.py reads templates; quiz GET + pass version pin; payments diffs + gap_month; `bursary_e2e` seeds+deploys. *Sequenced after the other agent's bursary.py reconciliation merge.* *Accept:* e2e green on deployed template; **payment-run parity test** (template vs constants item-identical Jul–Nov); `no_active_template` + `comprehension_stale` raise correctly.
3. **Stitch + admin API** (~20 files): Stitch screens → owner approval; views/urls/serializers; generate-quiz endpoint; org-fence tests (cross-org 404, org_admin deploy 403). *Accept:* full author→generate→vet→submit→deploy lifecycle drivable via API.
4. **Admin FE + quiz FE** (~30 files): pages/components per Stitch; quiz fetch refactor; delete static CHECKPOINTS; slim jest replacement; i18n. *Accept:* browser walkthrough — author, flag clauses, Gemini-generate, edit a question, preview all locales, submit, super deploys; student quiz renders API content with en fallback.
5. **Distribution + constants removal + cutover** (~15 files): distribution emails + `write_contract_pdf` + cron retry; remove constants after render-diff parity; playbook update; **single deploy**; runbook incl. Dec-STPM-gap owner confirmation. *Accept:* e2e execution sends 3 PDF emails + Drive file + stamps; grep proves constants gone; prod payment run matches prior month's shape.

## Verification

- Per sprint: full `pytest` (halatuju_api) + `jest` + `next build`; new suites named above; Gemini + Drive + storage seams mocked (never live in CI).
- Sprint 2 parity test is the guard for the 30 live students; Sprint 5 runbook re-verifies on prod before the flag ever flips.
- End-to-end: `python manage.py bursary_e2e` (template-seeded) drives quiz → sign → countersign → distribution.

## Risks

Live payment regression (mitigated: legacy fallback + parity test + reviewable skips) · concurrent bursary.py edits (Sprint 1 avoids the file; Sprint 2 sequenced after merge) · template mutation after signing (draft-only writes + PROTECT FK) · Gemini output quality (author review + structural validation + no model downgrade) · xhtml2pdf (plain text only + preview-PDF) · PII (NRIC via UI only; fixtures clean) · org flag-on with no template (`no_active_template` hard error + runbook order).
