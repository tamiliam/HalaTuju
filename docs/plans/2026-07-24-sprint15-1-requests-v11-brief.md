# Sprint 15.1 — Requests v1.1: role-correct components, B40 sub-components, screenshot attachments

**Date:** 2026-07-24 · **Owner-approved** (component scoping + two-level B40 selector + images-only attachments ×5) · **Executor:** Opus 4.8 agent · **Coordinator:** applies migrations migrate-first, pushes, closes.

Feature is LIVE (`REQUESTS_ENABLED=1`); all changes are additive and must not disturb live behaviour beyond the intended UI/API additions. `org_requests` prod table is empty or near-empty (launched today) — value-set changes are safe.

## A. Role-correct component choices (verified 2026-07-24)

- org_admin's reachable surfaces: B40 Applications + Administration (hub cards: Sponsors, Payments, Contracts, Sources, Requests) + sign-in/profile. **`students` and `course_data` are super-only (FE nav layout.tsx:110/114 + backend 403s) — REMOVE both** from `COMPONENT_CHOICES` (models.py:1742-1753), `VALID_COMPONENTS` (org_requests.py:52-55), the FE `COMPONENT_OPTIONS` (requests/page.tsx:27-28), and the `admin.requests.component.*` i18n keys ×3 locales. Table empty ⇒ clean removal, no data concern.

## B. Two-level B40 selector (hierarchical values, same column)

- **Stored values use underscore separator** (dot breaks the nested i18n lookup): parent `applications` stays; sub-values `applications_<sub>`, all ≤30 chars (varchar(30); no DB CHECK constraint exists — app-level clamp only, so `_clean_choice`/`VALID_COMPONENTS` MUST include every new value or it silently drops to '').
- Sub-components (owner-approved; labels en below, ms/ta first-drafts by executor):
  | value | en label |
  |---|---|
  | `applications_student_details` | Student details |
  | `applications_documents` | Documents |
  | `applications_ai_prediction` | AI Prediction & verdicts |
  | `applications_queries` | Queries & blockers |
  | `applications_interview` | Interview |
  | `applications_decision` | Recommendation & QC |
  | `applications_agreement` | Bursary agreement |
  | `applications_student_profile` | Student profile (sponsor-facing) |
- Parent alone remains selectable (plain `applications` = "B40 Applications — general").
- **FE pattern = the codebase's canonical dependent select** (PathwayPicker.tsx: parent selection in state → child options from a pure helper → child keyed `key={parent}` and cleared on parent change). Put the component tree in a pure helper (e.g. `REQUEST_COMPONENT_TREE` in a lib module or the page) so the i18n guard + a unit test can derive from it. Child select renders only when parent = `applications`.
- Detail chip already renders `t('admin.requests.component.' + value)` — works with underscore values; verify both pages.
- Model choices change ⇒ Django emits a **choices-only migration 0113** (no DDL on Postgres). AI prompt (`_build_review_prompt` org_requests.py:362) passes the raw value — fine as-is.

## C. Screenshot attachments (closes TD-172) — images only, 5/request

- **Model `OrgRequestAttachment`** (migration **0114**): `org_request` FK CASCADE `related_name='attachments'`; `storage_path` CharField(500); `original_filename` (255); `content_type` (100); `size` IntegerField; `uploaded_by` FK `courses.PartnerAdmin` PROTECT; `created_at`. Table `org_request_attachments`. Mirrors ApplicantDocument's metadata shape (models.py:924+).
- **Storage (Rule 5 — writes only via storage.py helpers):** new `storage.build_request_attachment_key(org_id, request_id, uuid_hex)` → `requests/<org_id>/<request_id>/<uuid>`; extend `resolve_org_for_path` to parse the `requests/<org_id>/...` scheme (returns org id). Same private bucket `b40-documents`; bytes go browser→Supabase via the existing signed-URL flow (`create_signed_upload_url`), NEVER through Django.
- **Endpoints under `_OrgRequestsBase`** (flag-gated 404-first, org-fenced, classify every new view in test_org_fence.py FENCED_OR_EXEMPT):
  - `POST <pk>/attachments/sign-upload/` — org_admin (own org) + super; request status must be non-terminal (not done/declined); enforce count cap BEFORE signing (≤5 recorded attachments); returns `{upload_url, storage_path}`.
  - `POST <pk>/attachments/` — records the row after the PUT; validates: content_type/extension in the IMAGE allowlist (reuse `_is_allowed_upload`'s image subset — jpg/jpeg/png/gif/bmp/webp/tif/tiff/heic/heif; NO pdf), `size ≤ settings.MAX_DOC_SIZE_BYTES`, count ≤5 (`400 attachment_limit` else), storage_path must match THIS request's expected prefix (reject foreign paths).
  - `DELETE <pk>/attachments/<att_id>/` — uploader's own org while the request is non-terminal; delete row + best-effort `storage.delete_objects`.
- **Serving:** both serializers gain `attachments` (list of {id, original_filename, content_type, size, created_at, download_url}) — `download_url` = signed URL with the org assertion mirroring `ApplicantDocumentSerializer.get_download_url` (`resolve_org_for_path(path) != request.organisation_id` → None). Update the org-payload exact-key snapshot DELIBERATELY (19 → 20 keys) with a comment.
- **HEIC:** reuse `imaging.convert_heic_to_jpeg`'s approach if trivially applicable to the new model, else record a one-line TD (don't over-build; HEIC screenshots are rare from desktops).
- **FE:** attach control ON THE SUBMIT FORM (create request → chain sign→PUT→record per ActionCentre.tsx:187 pattern → then navigate; failures after create show a non-blocking warning "request created; attachment failed — add it from the request page") AND an add/remove control on the detail page while non-terminal (submitter org only). Thumbnails render inline via the signed URL (`<img>`, DocViewer-style); filename + size caption. i18n ×3.
- **AI:** v1 prompt stays text-only (note "attachments: N image(s)" in the prompt when present so the reviewer knows they exist); Gemini-vision on screenshots = future TD note.

## Rails (unchanged from Sprint 15)

- NEVER `git push`; NEVER touch remote DBs — generate 0113 + 0114 locally, hand the coordinator the exact Postgres DDL (0113 = choices-only ⇒ django_migrations INSERT only; 0114 = CREATE TABLE + indexes + FKs + ENABLE ROW LEVEL SECURITY, same-transaction).
- Full gates per commit: pytest (current baseline ~4458+, 0 fail 0 skip), jest (712 baseline; 1 known local Node-26 fail held constant), next build, lint, `makemigrations --check` clean (exactly TWO new migrations).
- Org-fence suite: new views classified; `OrgRequestAttachment.objects` raw queries in views_admin.py need pragmas (add to WATCHED if queried raw).
- Zero brand literals; en.json duplicate-block rule (exact key paths); British English; ms/ta first-drafts per the Tamil style guide; parity/resolution/brand/placeholder guards green.
- Suggested commits: (1) components A+B backend+FE+i18n+tests; (2) attachments backend (model/storage/endpoints/serializers/tests); (3) attachments FE + i18n; (4) docs/CHANGELOG prep. Each green.

## Report back

Commits; test counts before→after; the two DDL blocks for migrate-first; confirmation: fence suite green with new classifications, org-payload snapshot 20 keys with no ai_*/triage_* leak, attachment path-prefix rejection tested, count-cap tested, flag-off still 404s everything incl. new routes; component tree ↔ i18n ↔ VALID_COMPONENTS consistency test present; deviations; anything red verbatim.
