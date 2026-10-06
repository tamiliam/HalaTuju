# Retrospective — Step-4 Redesign S4: Documents (v2.4.3)

**Date:** 2026-05-28
**Shipped:** web `halatuju-web-00216-6pt`, api `halatuju-api-00171-cjf` (both builds SUCCESS, 100% traffic, smoke green).
**Migration:** `scholarship 0014_more_doc_types` — choices-only, no DDL; `django_migrations` row recorded on prod via Supabase MCP before the push.

## What Was Built

The post-shortlist Documents tab, reworked so a B40 student isn't faced with an onerous-looking list:

- **Required** (amber pill, "We need these two to process your application"): Identity card (IC) + SPM/STPM results slip, each with a one-line explainer.
- **Optional** (muted pill, "These help us understand your situation — add what you have"):
  - One combined **"Proof of household income"** card accepting **any one of** STR letter / salary slip / EPF statement (a small type selector tags each file; multi-file for several earners).
  - Latest water bill, latest electricity bill (kept as a household-prosperity proxy), statement of intent, offer letter, photo — each its own card with an explainer.
- `reference_letter` removed from the student UI (referee now lives at the admin verify-&-accept stage); kept in model choices for back-compat.

**Backend:** 4 new `ApplicantDocument` doc types (`salary_slip`, `water_bill`, `electricity_bill`, `offer_letter`) via choices-only migration `0014`. `application_completeness` gains `documents_done` (IC + results slip both present). `complete` is **deliberately unchanged** (still quiz + story + funding) — a regression test locks that in; the docs/consent gate lands in S5.

**Frontend:** `ScholarshipDocuments` rewritten into Required/Optional sections with shared upload machinery; `scholarship.ts` gains `COMPULSORY_DOC_TYPES` / `INCOME_PROOF_TYPES` / `OTHER_OPTIONAL_DOC_TYPES` + a pure `documentsComplete()` helper (node-jest tested); i18n ×3 (parity 1227).

## What Went Well

- **Tighter Stitch prompt persisted on the retry.** After the first dense prompt timed out (below), trimming it to show the repeating pattern once produced the screen first try — fast visual sign-off, faithful to the locked plan.
- **Subagent delegation (4th use) stayed clean.** Tight spec → contained diff, all gates green (112 pytest, i18n parity, `next build`), no commit/push/deploy leakage; the orchestrator kept review + migrate-record + deploy.
- **Choices-only migration was friction-free.** Recognised it as no-op DDL up front, so it sidestepped TD-058 entirely — just record the `django_migrations` row via MCP, no `manage.py migrate`, no contenttypes failure.
- **One deploy.** Both services built and went 100%-live on the first push; no rework deploy needed.

## What Went Wrong

1. **The first Stitch generation timed out and didn't persist.**
   - *Symptom:* `generate_screen_from_text` timed out client-side; polling `list_screens` showed only the three prior screens — the Documents screen never appeared.
   - *Root cause:* the prompt was content-dense — eight upload cards each fully specced (label + helper + uploaded/empty state) plus the bottom tab bar. That density is the exact failure mode flagged in the S1/S3 lessons; "use FLASH" alone didn't save it.
   - *System change:* added a lesson — when prototyping a list/repeat-heavy screen, specify each repeating element **once** and summarise the rest ("…and three more rows: X, Y, Z") rather than enumerating every card. Reduces token/render density enough to persist.

2. **Wasted a wait cycle assuming PowerShell syntax in the Bash tool.**
   - *Symptom:* a background "wait 60s" using `Start-Sleep` failed with exit 127 (`command not found`); no wait happened.
   - *Root cause:* the environment's interactive shell is PowerShell, but the **Bash tool always runs bash** even on win32 — I reached for `Start-Sleep` instead of POSIX `sleep`.
   - *System change:* in the Bash tool, always use POSIX (`sleep`, not `Start-Sleep`) regardless of the host OS. (Harness-level; not added to `lessons.md` as it isn't HalaTuju-specific.)

3. **Subagent's JSON writes dropped the trailing newline on all three message files.**
   - *Symptom:* `git diff` flagged "No newline at end of file" on en/ms/ta.json.
   - *Root cause:* the subagent's file write didn't preserve the final newline.
   - *System change:* cheap orchestrator check (`tail -c1`) before commit; fixed in-place. Too minor for a standing lesson.

## Design Decisions

- **4 new doc types via a choices-only migration; `reference_letter` retained in the model.** Choices aren't enforced at the Postgres level, so the migration carries no DDL — recorded as a `django_migrations` row only. `reference_letter` stays a valid choice for back-compat even though it's gone from the student UI.
- **`documents_done` decoupled from `complete` until S5.** Adding the signal now without gating `complete` keeps each sprint independently shippable and avoids a half-built rollup; S5 owns the final `complete = quiz+story+funding+compulsory-docs+consent`. A regression test (`test_complete_not_affected_by_documents_done`) makes the intent explicit.
- **Income proof as one visual card with a per-file type selector.** Preserves the three distinct `doc_type`s (STR/salary/EPF) for downstream verification while presenting a single, low-friction "Proof of household income" card with multi-file upload.

(All three logged in `docs/decisions.md`.)

## Numbers

- Files changed: 10 (+ new migration `0014` + CHANGELOG).
- Backend: 112 pytest in the scholarship suite (full-suite count in `memory/halatuju.md`).
- i18n parity: 1227 keys × {en, ms, ta}.
- Frontend: `next build` clean (38 routes); `documentsComplete()` jest unit tests added.
- Deploys: 1 (web + api together).
- Tamil copy: first draft — flagged for the user's expert refinement (to fold into the S5 deploy).
