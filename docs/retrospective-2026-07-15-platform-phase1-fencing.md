# Retrospective — Platform Phase 1 completion (Sprints 2, 3a, 3b, 4)

**Date:** 2026-07-15
**Scope:** Finish Phase 1 of the multi-tenant platform — give every application an
owning organisation (S2), enforce + prove the organisation wall on the admin surface
(S3a/S3b), and org-prefix new document uploads (S4). Behaviourally invisible while
BrightPath is the only organisation.
**Commits:** `5ffcd493` (S2) · `f2c8c5ef` (S3a) · `171a6459` (S3b) · `1949c658` (checkpoint-1 runbook) · `200cbbd6` (S4).
**Migrations:** scholarship `0099`+`0100`, courses `0062`+`0063` — all additive, applied
migrate-first via Supabase MCP at Checkpoint 1 (runbook `docs/plans/2026-07-15-phase1-checkpoint1-migrate-first.md`).
**Tests:** 3713 pytest passing (was 3674 at Phase-1 start → +39). No frontend change.

## What shipped

- **S2 — owning-org on the application.** `ScholarshipApplication.owning_organisation`,
  a denormalised copy of `cohort.owning_organisation` (D-8), derived in `save()` (set-once,
  reads the loaded cohort from the field cache → no extra query on hot paths). NULL is
  tolerated (bare test fixtures); prod has none (backfill + seeded cohort). Drift guard +
  cohort docstring warning about the future "move-cohort" cascade.
- **S3a — the org fence.** `PartnerAdmin.owning_organisation` (the access-control boundary,
  distinct from the referral `org`). Central `_org_scoped` / `_org_allows` on `_AdminBase`,
  wired into every gate (list query, `_scoped_application`, `_can_review_app`,
  `_require_app_write`, `_require_qc`) and the three bypass list surfaces. Cross-org → 404.
  Staff backfill: admin/reviewer/qc → BrightPath; super/partner NULL. 44-endpoint audit
  (`docs/plans/2026-07-15-phase1-s3a-endpoint-audit.md`).
- **S3b — prove it, forever.** Fence-proof suite (two orgs, real endpoints), a
  `__subclasses__` coverage-completeness check (a new endpoint nobody classified fails CI),
  and a static source guard (a raw admin query without an `# org-fence:` pragma fails CI).
- **S4 — org-prefixed document keys.** New uploads → `<org>/<app>/<doc_type>/<uuid>` via a
  single `storage.build_doc_key`; signing seams refuse a key-org/row-org mismatch; the
  orphan-blob walk now recurses so it handles both legacy 3-level and prefixed 4-level keys.
  Legacy blobs keep their keys (no bulk re-key) and sign via the row FK.

## Live verification

- **Checkpoint 1** (S2+S3a DDL migrate-first → push): build `d5b2a3f5` SUCCESS; post-checks
  0/143 applications un-owned, staff bound as intended (admin 2 / reviewer 13 / qc 1 → org;
  super 1 / partner 2 → NULL); smoke web 200, gated admin list **401 not 500**, public 200,
  `/scholarship/intake/` 200; zero error logs.
- **Checkpoint 2** (S4, no migration → push): all 1114 existing docs are legacy 3-segment
  keys → sign via the row-FK fallback (no regression); new uploads carry the org prefix.

## What went well

- **Invisible-by-construction held.** With one org, every fenced query returns exactly
  today's rows — the full suite passed at every sprint with **no edits to existing tests**,
  which is the strongest evidence the refactor didn't change behaviour.
- **The pre-split was right.** Sprint-0 verification found **44** `_AdminBase` classes (not
  the ~25 project history suggested), so 3a/3b as separate sprints kept each reviewable.
- **The endpoint audit found a hole the plan's three-surfaces list missed:**
  `AdminGraduationMessageReviewView` (write) was role-only and cross-org-writable — now
  `_org_allows`-gated. The systematic 44-class sweep is what surfaced it.

## Lessons

- **Role gate fires before the org gate.** On QC/graduation-review endpoints the role check
  returns 403 before the org 404, so a cross-org test must use a caller with the right role
  (a qc/reviewer of org A), not just any admin. Tests were adjusted accordingly.
- **`resolve_org_for_path` must stay unambiguous.** A 3-segment key is ambiguous (legacy doc
  vs prefixed bursary), so the resolver only reads the org from an unambiguous 4-segment doc
  key and otherwise returns None → the row FK is the real fence. Keeping the belt-and-braces
  check conservative avoided false "cross-org" refusals on legacy blobs.
- **The seeded BrightPath org is present in the test DB** (migration 0098), so test fixtures
  must not reuse `code='brightpath'` — use unique codes.

## Carry / follow-ups

- **TD — tighten `ScholarshipApplication.owning_organisation` to NOT NULL** once a shared
  test factory exists (today bare-cohort fixtures legitimately produce NULL).
- **TD — bursary 2-segment PDFs were never reconciled by the orphan walk** (pre-existing; the
  fence + prefix now apply, but the orphan matcher's DB set doesn't include bursary paths).
- **TD — the two `_can_review_app`-gated action endpoints** (disbursement/resolution actions)
  return 403 (not 404) for cross-org — fenced, but a minor existence-leak the plan chose not
  to restructure. Revisit if it matters.
- **Platform work now PAUSES.** Phase 2 (extract hard-coded rules into per-org settings) is
  gated on rule stability — start only after ~a month with no `MODEL_VERSION` bump or new
  document family. Phases 3–4 are gated on a credible second-tenant prospect. The S3b CI
  guards protect the fence through the owner's BrightPath feature-work period.
