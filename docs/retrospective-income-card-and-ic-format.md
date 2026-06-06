# Retrospective — Income IC↔proof match + Gopal BC nudge + IC display format

**Date:** 2026-06-06
**Commits:** `b0d851d` (Piece A — income card + coach), `dbc8ac8` (Piece B — IC display format)
**Migration:** none (scholarship stays at `0041` on prod)
**Gates:** 1037 courses/reports + 758 scholarship pytest · 262 jest · `next build` clean · i18n parity 2024

This was a live-testing follow-up to the Income Check-1 + Gopal-cockpit work, driven by two screenshots the user
flagged on the **mother's-STR** income cluster, plus a cross-cutting request to standardise IC display.

## What Was Built

### Piece A — the earner IC now reports whether it MATCHES the income proof
The earner-IC card used to show *source* labels ("from your IC") and a *relationship-pending* name ("We'll review
this") — neither answered the only question that matters when you upload an earner's IC: **does it match the income
document?** It now cross-checks the IC against the cluster's income proof (STR recipient, or salary-slip/EPF name+NRIC):

- `income_engine._cluster_proof_identity(application, member)` → `(kind, name, nric)` of the cluster's proof.
- `student_income_ic_check` gains `proof_kind` / `proof_name_status` / `proof_nric_status` (using `vision.nric_match`
  + the existing name matcher).
- FE `IncomeIcChecklist` renders **"Matches the STR document" (green)** on IC No + Name when they agree, **red** on a
  clash; the relationship-to-student is no longer asserted here.

### Piece A — relationship moves to Gopal, anchored on the birth certificate
The link between earner and student is the **birth certificate** (mother) / **guardianship letter** (guardian) — not
something the IC card can prove. New cluster verdict **`income_rel_doc_needed`**: once the IC is in and matches the
proof, `income_cluster_advice` returns it so Cikgu Gopal nudges for the relationship doc as the *last* step, then goes
silent once it's uploaded. Father needs none (patronymic on the student's own IC).

### Piece A — coach copy: member-aware + gate-honest
`generate_document_help(doc_type, verdict, first_name, target_language)` could only see those four things, so the
income copy was a **hardcoded "father's payslip" example** even when the earner was the mother on the STR route, and it
still said uploads are "never blocked" — which **contradicts consent gate v2** (these income docs are compulsory). Fix:
- A new **non-sensitive** `context` param (`{member, income_doc, rel_doc}` *labels* — never a model object) feeds a
  `_specifics_block` in the prompt, so the AI names the real earner + document.
- `IncomeClusterHelpView` builds that context from `_cluster_proof_identity` + `relationship_doc_for`.
- `income_ic_needed` / `income_rel_doc_needed` guidance + fix-hints + fallbacks rewritten to be member-neutral and
  honest that the doc **is required**.
- Earner-IC label corrected "from **your** IC" → "from **their** IC".

### Piece B — IC numbers display as `XXXXXX-XX-XXXX` everywhere
A shared `formatNric()` already lived in `lib/scholarship.ts` (idempotent, display-only). The unformatted display sites
— student checklists (identity / income IC / income proof / STR) and the officer cockpit (header NRIC, NRIC verify-row,
Vision-extracted lines on the identity + parent IC drawers) — now wrap their raw value in it. Profile `maskIc` privacy
masking and consent NRIC-match validation are untouched; the admin students list/detail pages already formatted.

## What Went Well
- **The coach copy bug had a structural root cause, and we fixed the structure, not the words.** The wrong "father's
  payslip" text wasn't a typo — the engine literally couldn't know the earner. Adding a narrow, non-sensitive `context`
  channel fixes it for every income message at once, not just the one screenshot.
- **No new formatter.** The "standardise IC everywhere" request was already 90% solved by an existing shared helper;
  the work was finding the gaps, not writing code. Saved a duplicate.
- **TDD caught the firewall regression.** Adding `context` tripped the structural-firewall signature test immediately,
  forcing a deliberate decision (allow it, document why) rather than a silent weakening.

## What Went Wrong
1. **Four existing unit tests broke when the IC check started reading the cluster's documents.** *Symptom:* `student_income_ic_check`
   tests using `SimpleNamespace` fakes failed once `_cluster_proof_identity` called `application.documents.filter(...)`.
   *Root cause:* the fakes only modelled the fields the *old* relationship path read; a new code path reached for a
   relation they didn't stub. *Fix:* gave the fake app an empty `documents` (a lambda chain) so the proof lookup is a
   no-op for those relationship-only tests — and the real proof-match is covered by the DB-backed `test_verdict_engine`
   tests instead. **Lesson (added):** when a pure function starts touching the ORM, its `SimpleTestCase` fakes need the
   new relation stubbed, and the genuinely DB-dependent assertion belongs in a `TestCase`, not the fake.
2. **`tsc --noEmit` surfaced a wall of pre-existing errors that aren't on the deploy path.** *Symptom:* an isolated type
   check lit up `scholarship.test.ts` with `ApplicationPayload`→`Record` conversion errors. *Root cause:* `next build`
   (the real gate) excludes test files, so those have drifted; `tsc --noEmit` checks everything. *Fix:* confirmed they
   were neither mine nor the other agent's uncommitted work and not in any changed file; trusted `next build`
   "Compiled successfully" as the gate. **Lesson (added):** `next build` "Compiled successfully" is the FE type gate —
   `tsc --noEmit` is stricter and includes test files, so treat its test-file noise as out-of-scope unless it's in a
   file you touched.

## Design Decisions
See `decisions.md`: "Earner IC card asserts proof-match, not relationship — relationship is the birth cert's job (via
Gopal)" and "The doc-help engine gains a non-sensitive `context` param (member/doc labels, never a model object)".

## Numbers
- 2 commits, no migration.
- Files: `income_engine.py`, `help_engine.py`, `views.py`, 3 backend test files; `ScholarshipDocuments.tsx`, `api.ts`,
  `documentHelp.ts`, `admin/scholarship/[id]/page.tsx`, `messages/{en,ms,ta}.json`; `CHANGELOG.md`.
- Tests: 758 scholarship pytest (+5), 262 jest, i18n parity 2024 (+4 keys).
- Built alongside a parallel agent — explicit `git add <paths>` only, `AGENT-TERRITORY.log` coordination, fetch-before-push.
