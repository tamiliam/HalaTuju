# Implementation Plan — HalaTuju Platform Phase 1 completion (Sprints 2, 3a, 3b, 4)

**For:** the implementing agent (Opus 4.8), working in `c:\Users\tamil\Python\Production\HalaTuju`
**Authority:** roadmap `docs/plans/2026-07-14-platform-roadmap-draft.md` (plan of record) + architect review + this plan. Owner decisions D-1…D-10 are all settled — do not reopen them.

## Context

HalaTuju is becoming a multi-tenant platform: course selector = shared base, scholarship programmes = org-owned tenants, BrightPath = org #1 (shipped as Platform Sprint 1, 2026-07-15: `PartnerOrganisation` tenant columns + `ScholarshipCohort.owning_organisation` + seed migration 0098, commit `a473a171`). This plan completes **Phase 1 — the foundation**: give every application an owning organisation (S2), enforce and prove the organisation wall on the admin surface (S3a/S3b), and org-prefix new document uploads (S4). Everything is behaviourally invisible while BrightPath is the only organisation; after Phase 1 the owner pauses platform work and returns to BrightPath features, protected by the S3b CI guard.

**Deploy cadence (owner decision):** TWO checkpoints. Checkpoint 1 after S3b (migrate-first the accumulated S2+S3a DDL → push → smoke). Checkpoint 2 after S4 (no migrations → push → smoke). Build each sprint as its own commit with the full suite green; do not push between checkpoints.

## Ground rules (from CLAUDE.md + docs/lessons.md — non-negotiable)

1. Follow `Settings/_workflows/sprint-start.md` / `sprint-close.md` per sprint; one commit per sprint, full pytest suite green before each commit (3,664+ tests, ~6½ min; on this 8GB machine never run two heavy suites at once).
2. **Deploys do NOT run migrations.** All DDL goes to prod MIGRATE-FIRST via the Supabase MCP before the push that needs it. Write a runbook per checkpoint modelled exactly on `docs/plans/2026-07-15-sprint1-migrate-first.md` (hand-written Postgres DDL — never `sqlmigrate` output; pre-checks incl. the legacy-table trap and already-applied check; `django_migrations` rows; post-checks). If the Supabase MCP is unavailable in the session, STOP at the checkpoint and hand over — do not push.
3. Follow `docs/build-for-tenancy-conventions.md`. The tenant FK name is `owning_organisation` — never `org` (that means *referring* organisation; access control must never key off `PartnerAdmin.org`/`referred_by_org`, with the ONE grandfathered exception noted in S3a).
4. Check `max(migration)` on main before numbering (currently: courses 0061, scholarship 0098 → next: courses 0062, scholarship 0099). `makemigrations --check --dry-run` before committing any hand-edited migration.
5. After push: anchor build monitoring on YOUR commit's SHORT_SHA via `gcloud builds list --project gen-lang-client-0871147736 --account tamiliam@gmail.com` — never "latest N builds".

---

## Sprint 2 — Owning-org on the application (+ drift guard)

**Scope facts (verified by exploration):**
- Applications are created in exactly ONE production path: `services.create_application` (`apps/scholarship/services.py:235`), called only by `ApplicationListCreateView.post` (`views.py:181-184`), which hard-guards a non-null open cohort (`views.py:152-166` via `resolve_open_cohort`, `services.py:187-199`). Non-prod creators: `management/commands/bursary_e2e.py:121`, `_test_fixtures.py:48,106`.
- `cohort` FK is non-null, PROTECT (`models.py:151-154`) and **write-once** — nothing ever reassigns it. Meta at `models.py:762-774` already has a `constraints = [...]` list (UniqueConstraint `unique_application_per_cohort`).
- Test fixtures create applications DIRECTLY with bare cohorts in dozens of files (no shared factory, no conftest) — so the new column must be **derived, not required at call sites**.

**Changes:**
1. `apps/scholarship/models.py` — add to `ScholarshipApplication`:
   `owning_organisation = models.ForeignKey('courses.PartnerOrganisation', on_delete=models.PROTECT, null=True, blank=True, related_name='owned_applications', help_text=...)` — docstring: denormalised copy of `cohort.owning_organisation` (D-8); source of truth is the cohort; set automatically in `save()`.
2. Same model: derive in `save()` — if `self.owning_organisation_id is None and self.cohort_id`: copy from `self.cohort.owning_organisation_id` (use `cohort_id`-based lookup only when the relation isn't loaded, to avoid extra queries on hot paths). This covers production, e2e, and every test fixture with zero call-site churn.
3. Migration `scholarship/0099` (schema, additive) + `scholarship/0100` (data: backfill `owning_organisation_id` from each row's cohort).
4. **DEVIATION from roadmap, with reason — do NOT tighten to NOT NULL.** Test fixtures across the suite create bare cohorts (`owning_organisation=None`), so derived application values are legitimately NULL in tests. NULL semantics are safe: Django `.filter(field=None)` → `IS NULL`, so the S3a fence still partitions correctly (None-staff see None-apps only), and prod has no NULLs (backfill + seeded cohort). Record "tighten to NOT NULL once a shared test factory exists" as a technical-debt entry.
5. Drift guard (app-layer — a DB CheckConstraint cannot reference the cohort row): a test asserting `app.owning_organisation_id == app.cohort.owning_organisation_id` for created-and-saved applications, incl. after the backfill migration; plus a note in the cohort model docstring that any future "move cohort between orgs" flow must cascade to its applications.

**Tests (new file `apps/scholarship/tests/test_application_owning_org.py`):** derivation on create via the real service path; derivation for bare-cohort fixtures (stays None, no crash); backfill covers 100% of pre-existing rows; drift invariant; PROTECT on delete.
**Suite:** full pytest green. **Commit** `feat(platform): Sprint 2 — owning-org on the application + drift guard`.

---

## Sprint 3a — Org-scope the admin gates (the #1-risk sprint)

**Scope facts:** the entire scholarship admin surface is `apps/scholarship/views_admin.py` (verified: no admin-scope scholarship reads anywhere else; student/sponsor surfaces are separately scoped). 44 classes inherit `_AdminBase` (line 63). Shared gates: `_b40_scope` (:89), `_scoped_application` (:105), `_can_review_app` (:121), `_require_app_write` (:134), `_require_qc` (:150), `_get_application` (:86), main list queryset (:186-189).

**Changes:**
1. **Admin→tenant binding (migration the roadmap missed — courses/0062 + data migration).** Add `PartnerAdmin.owning_organisation` FK (`courses/models.py`, nullable, PROTECT, related_name `staff`): NULL = platform-level. Backfill: every active admin with role in {admin, reviewer, qc} → org #1 (BrightPath); `super` and `partner` stay NULL (super is global; partner has no B40 access — `_b40_scope` returns `'none'`). Do NOT touch `PartnerAdmin.org` (referral semantics, used for display + partner-students + bursary witness).
2. **Central fence on `_AdminBase`:** one helper, e.g. `_org_scoped(self, qs, admin)` → `qs` unchanged if `has_role(admin,'super')`, else `qs.filter(owning_organisation_id=admin.owning_organisation_id)` (Django turns None into IS NULL — safe degenerate bucket for legacy test fixtures). And one row-level check `_org_allows(self, admin, app)` used by `_scoped_application`, `_can_review_app`, `_require_qc` (super bypasses; else `app.owning_organisation_id == admin.owning_organisation_id`).
3. Wire it in: the main list queryset (:186), `_get_application`-based gates (row check after fetch → return 404, not 403, for cross-org — don't leak existence), and the invite path so a super creating a non-super admin sets `owning_organisation` explicitly (`courses/views_admin.py` `AdminInviteView` :497,522 area — default org #1 for now; the real picker is Sprint 10).
4. **Fence the three bypass surfaces found in exploration** (they read applicant data cohort-wide with only `get_admin`):
   - `AdminSponsorshipListView` (:888 — `Sponsorship.objects.select_related('application','application__profile')`) → `_org_scoped` on the application join.
   - `AdminVerdictMetricsView` (:1396 — raw `ScholarshipApplication.objects...`) → `_org_scoped`.
   - `AdminGraduationMessageListView` (:1556 — `GraduationMessage.objects.select_related('application')`) → `_org_scoped` via application.
   Leave `AdminSponsorListView`/`AdminAssignableAdminsView` (Sponsor/PartnerAdmin lists) as-is with a `# tenancy: cross-org by design until Sprint 10 (D-1)` comment.
5. **Grandfathered exception (document, don't change):** `AdminBursaryWitnessView` (:1647-1652) intentionally uses referral-org (`admin.org_id == profile.referred_by_org.id`) — witness authority is referral semantics, orthogonal to ownership. Add the comment.
6. Views known to be already safe via secondary-pk + `_can_review_app` re-gate (`AdminDisbursementActionView` :934→940, `AdminResolutionItemActionView` :1096→1100) inherit the fence through `_can_review_app` — verify, don't restructure.

**Behaviour check:** with one org, every backfilled staff admin's org equals every backfilled application's org → all scoped queries return today's rows; the existing suite must pass with NO test edits except where a test creates a PartnerAdmin AND an application in different implicit orgs (bare fixtures are both None → still match).
**Tests:** unit tests per amended gate (same-org pass, cross-org 404/exclusion, super global, partner still `none`); the 44-endpoint audit table goes in the sprint's plan/retro doc as the review artefact.
**Suite green → commit** `feat(platform): Sprint 3a — org-scoped admin gates + staff tenant binding`.

---

## Sprint 3b — Prove the fence (fence-proof suite + CI static guard)

**Test auth pattern to reuse** (no conftest exists): per-file HS256 JWT stub + `APIClient.credentials`, exactly as `apps/scholarship/tests/test_qc_gate.py:23-81` (TEST_JWT_SECRET, `_token(uid)`, `@override_settings(SUPABASE_JWT_SECRET=...)`, PartnerAdmin rows keyed by `supabase_user_id`).

**Changes (all new tests, no production code):**
1. **Fence-proof suite** `apps/scholarship/tests/test_org_fence.py`: seed TWO organisations, each with a cohort, an application (with documents/sponsorship/graduation-message rows for the bypass surfaces), and one admin per role. Drive the REAL endpoints and assert: org-A admin/qc sees only org-A in the list; org-A detail/write/QC on org-B's app → 404; super sees both; reviewer stays assignment-scoped within their org; the three formerly-bypassing list views return only caller-org rows.
2. **Coverage-completeness check** (new pattern — none exists; `__subclasses__` grep = zero hits): a test that enumerates `_AdminBase.__subclasses__()` at runtime and asserts every subclass name appears in an explicit `FENCED_OR_EXEMPT` map maintained in the test (each entry: fenced-by-gate / exempt-with-reason). A new endpoint that nobody classified fails CI.
3. **Static source guard**, modelled on `TestStaticReadGuard` (`apps/scholarship/tests/test_superseded_documents.py:155-194` — source-regex scan + pragma allowlist): scan `views_admin.py` for raw `ScholarshipApplication.objects`, `Sponsorship.objects`, `GraduationMessage.objects`, `ApplicantDocument.objects` outside the shared helpers; a match without an `# org-fence:` pragma fails.

**Suite green → commit** `test(platform): Sprint 3b — fence-proof suite + org-fence CI guards`.

### ── CHECKPOINT 1 (after 3b) ──
Write `docs/plans/<date>-phase1-checkpoint1-migrate-first.md` covering scholarship/0099+0100 and courses/0062+data (pattern: Sprint-1 runbook, incl. already-applied pre-check — a parallel session once applied a runbook first; the pre-check is what makes that safe). Apply via Supabase MCP → post-checks (0 NULL owning-org applications in prod; staff backfill counts) → push → match build by SHORT_SHA → smoke (student flow, reviewer cockpit list/detail, QC action) → interim close notes.

---

## Sprint 4 — Org-prefix for NEW document uploads (legacy = org #1)

**Scope facts:** TWO key-generation sites — `apps/scholarship/views.py:666` (`f"{app.id}/{doc_type}/{uuid4().hex}"`) and `apps/scholarship/bursary.py:504` (`f"{application.id}/bursary_agreement_{version}_{ts}.pdf"` → `pdf_storage_path`, second write at `bursary.py:636` reuses the stored path). NO code derives ownership by parsing the path (FK is the source of truth). Prefix-safe already: `storage.object_exists` (rsplit from right), `backup_documents._walk_files` (recursive). **Breaks:** `cleanup_orphan_blobs._walk_bucket` (`cleanup_orphan_blobs.py:30-45`) — hard-coded 3-level walk; with a 4-segment layout it would flag live blobs as orphans (`--apply` could delete them).

**Changes:**
1. Key generation: prefix both sites with the application's org id → `f"{org_id}/{app.id}/..."` where `org_id = app.owning_organisation_id` (skip prefix if None — bare test fixtures). One shared helper (e.g. `storage.build_doc_key(app, *segments)` or a small function in views) used by BOTH sites so the scheme has one home.
2. **Signing fence:** before `create_signed_download_url`, assert the caller's org owns the path — central helper `resolve_org_for_path(path)`: 4-segment/prefixed → first segment is the org id; unprefixed legacy → org #1. Enforce at the two signing seams: `ApplicantDocumentSerializer.get_download_url` (`serializers.py:693`) and `BursaryAgreementSerializer.get_pdf_url` (`serializers.py:234`) — via the row's application FK (cheap and already loaded), with the path-prefix assertion as belt-and-braces.
3. Fix `cleanup_orphan_blobs._walk_bucket` to walk BOTH shapes (3-level legacy + 4-level prefixed); update its fixture (`test_cleanup_orphan_blobs.py:36-56`, hard-codes the 3-level dict). Note in the command docstring that 2-segment bursary PDFs were never covered by the walk (pre-existing; do not fix here — record as TD).
4. Upload confirm path: `object_exists` guard at `views.py:858` and the HEIC re-upload (`imaging.py:42-56`) operate on the stored path — verify they pass through unchanged (they treat the key as opaque).
5. Update the sentinel test `test_documents.py:49` (`startswith(f'{app.id}/ic/')`) and any test reconstructing expected keys; storage mocks are Python-level patches of `apps.scholarship.storage.*` (existing pattern — keep it).

**Tests:** new uploads carry the org prefix; legacy unprefixed resolves to org #1; cross-org signing refused; orphan sweep correct on a mixed bucket fixture (legacy + prefixed, none falsely orphaned); bursary PDF round-trip.
**Suite green → commit** `feat(platform): Sprint 4 — org-prefixed document keys (new uploads), signing fence, mixed-shape orphan walk`.

### ── CHECKPOINT 2 (after 4) ──
No migrations. Push → match build by SHORT_SHA → smoke: upload a doc on the live student flow (verify the new key shape in the DB), open an EXISTING legacy document in the reviewer cockpit (must still render), bursary PDF link works. Then run the full **sprint-close workflow** for Phase 1 (retro, CHANGELOG, roadmap prune S2–S4, CLAUDE.md Next Sprint → "platform paused; Phase 2 gated on rule stability", memory update, `wat_lint.py`).

---

## Verification (end-to-end, after Checkpoint 2)

1. Full pytest suite green (expect ~3,700+), jest untouched (no frontend changes in Phase 1).
2. Prod queries: 0 applications with NULL `owning_organisation_id`; staff backfill = expected counts; a fresh live upload's `storage_path` starts with the org id.
3. Live smoke both checkpoints as specified above; zero new error logs (`gcloud`/Supabase logs).
4. The fence-proof suite and both CI guards run in the normal suite — they are the durable deliverable protecting the owner's feature-work period.

## Sizing & risks

S2 ≈ 6–8 files (Low-Med). S3a ≈ 10–14 files (High — the 44-endpoint audit is the bulk). S3b ≈ 3 test files (Med). S4 ≈ 8–10 files (Med). All within the 40-file cap. Top risks: a missed bypass queryset (mitigated by the S3b completeness check + static guard), the orphan-sweep walk regression (mitigated by the mixed-bucket fixture), and NULL-org semantics (mitigated by Django's `=None → IS NULL` partitioning + prod post-checks).
