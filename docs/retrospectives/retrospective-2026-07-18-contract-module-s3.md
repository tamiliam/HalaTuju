# Retrospective — Contract Module Sprint 3 (admin API + Stitch)

**Date:** 2026-07-18
**Plan:** `docs/plans/2026-07-18-contract-module-plan.md`
**Branch:** `feat/contract-module` (NOT pushed; single deploy at Sprint 5).
**Scope:** The admin authoring/deployment API + the Stitch UI prototype. Backend
only — the FE pages/components are Sprint 4, gated on the owner's Stitch approval.
NO deploy; no migration.

## What Was Built

- **`_ContractsBase(_AdminBase)` + 12 thin views** (`views_admin.py`) over the
  `contracts` service: list/create, detail/config PATCH, clauses PUT, generate-quiz
  POST, schedule PUT, vetting POST, validate GET, submit/revert/deploy POST,
  preview GET (HTML/PDF), quiz-preview GET. Response dict-builders mirror the
  payments module's style (`_contract_template_detail`, `_contract_validation_dict`,
  `_contracts_err`).
- **URLs** after the payments block; **org-fence classification** for the 12
  endpoints + base in `test_org_fence.py`.
- **Stitch prototype** on project `10844973747787673276` — the deploy panel
  rendered (auto-created design system "Administrative Clarity"); list + editor
  tabs generating under the same system.
- **`test_contract_admin_api.py` (+21)** covering the access gate, org fence, the
  full lifecycle over the API, generate-quiz (mocked + draft-only), and validate
  mirroring the service.

## What Went Well

- **The service did the heavy lifting; the views are thin.** Because Sprint 1's
  `contracts.py` owns the lifecycle + validation + the `ContractsError` codes, each
  view is a try/except wrapper — the API surface was fast to add and hard to get
  wrong (every error already has a machine code).
- **The org fence reused the established pattern.** `_template_for` mirrors
  `_PaymentsBase._run_for` (cross-org → 404), so the fence behaviour is consistent
  with the rest of the admin surface, and the CI guard (`test_org_fence.py`) forced
  me to classify every new endpoint — the coverage check is doing its job.
- **validate-mirrors-service is asserted, not assumed.** A test compares the API's
  error codes to `contracts.validate_for_deployment(t).errors` directly, so the
  endpoint can't drift from the service's rule list.

## What Went Wrong

1. **The `cat <<'EOF'` heredoc to append the views block failed** ("unexpected EOF")
   because the Python contained apostrophes/quotes the Windows Bash heredoc
   mishandled — the exact trap already in lessons/memory
   (`feedback_commit_message_backticks`). Root cause: reached for a heredoc to write
   a large code block instead of the file tools. Fix: used the Edit tool to append.
   **System reminder (already a lesson):** never pipe a large quoted code block
   through a Bash heredoc on this box — use Write/Edit.
2. **The org-fence CI guard failed on first run** — 13 new `_AdminBase` subclasses
   were unclassified. This is the guard working as designed (a new admin endpoint
   nobody classified fails CI), not a defect; fixed by adding them to
   `FENCED_OR_EXEMPT` with a `contract-org-fenced` note. Worth recording so the next
   admin-surface sprint expects it.
3. **Stitch `generate_screen_from_text` timed out on 5 of 6 screens and
   `list_screens` did not surface them within the sprint** (eventual consistency,
   exactly as the `stitch-mcp-workflow` memory warns). Only the last call (deploy
   panel) returned synchronously — because by then the shared design system had been
   created, so it rendered fast. Root cause: firing 6 fresh generations at once made
   the first 5 race the design-system creation. **Next time:** generate ONE screen
   first (let it mint the design system), then fire the rest referencing that
   `designSystem` id — they'll render faster and return node-ids. The 5 will still
   surface in the owner's Stitch UI; do not re-fire (that duplicates renders).

## Design Decisions

- **Response dict-builders, not DRF ModelSerializers.** The contract admin views
  build plain dicts (`_contract_template_detail`, etc.) exactly like the payments
  module, rather than introducing ModelSerializers. Keeps the two org-fenced admin
  modules idiomatically identical and avoids a serializer layer for what is a thin
  pass-through to the service.
- **Write bodies are flat model-field dicts** (`clauses: [{heading_en, body_en,
  quiz_en, …}]`, `rows: [{pathway, monthly_amount, paid_offsets, …}]`) matching the
  detail response shape and the `contracts.replace_*` service signatures — the FE
  round-trips the same shape it reads, no nested↔flat translation in the API.
- **The attesting admin's own email is stamped** on `record_vetting` (not a body
  field) — the audit trail records who clicked attest, which is the accountable fact.

## Numbers

- +21 admin API tests; +13 endpoint classifications in the fence guard. **2841
  scholarship pytest** green; org-fence guard green; 0 migration drift. 4 files
  (views_admin.py, urls.py, test_org_fence.py, test_contract_admin_api.py). 1 of 6
  Stitch screens confirmed rendered (deploy panel); 5 generating.
