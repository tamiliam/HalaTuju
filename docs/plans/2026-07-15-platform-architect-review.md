# Architect Review — Multi-Tenant Platform Deliverables

**Date:** 2026-07-15
**Reviewer:** Architect (senior-consultant pass over the 2026-07-14 research deliverables)
**Reviewed:** `2026-07-14-tenancy-audit.md`, `2026-07-14-platform-prd-draft.md`, `2026-07-14-platform-roadmap-draft.md` (produced against `2026-07-14-platform-multitenancy-research-brief.md`)
**Verdict:** **APPROVED WITH AMENDMENTS.** Evidence spot-checked first-hand and it holds. The amendments below are binding on the roadmap.
**Update 2026-07-15 (later the same day):** the owner accepted ALL recommendations (D-1…D-10). The amendments + decisions are folded into the PRD/roadmap (now the plan of record), Sprint-0 verification is done (43 `_AdminBase` endpoints; gate-body subtleties catalogued; billable-site list confirmed complete), and the build-for-tenancy conventions (`docs/build-for-tenancy-conventions.md`) are in force for all ongoing work.

---

## 1. Evidence verification

Load-bearing citations checked directly against the code — all confirmed:

- `docs/incident-001-rls-disabled.md` states verbatim that Django connects as the `postgres` superuser and bypasses RLS → the tenant wall must live in Django query code. Confirmed.
- `scholarship/views_admin.py` `_b40_scope` grants super/admin/qc `'all'` visibility; the list query narrows only by `assigned_to`; `?source=` is an optional filter, never an enforced scope. Confirmed.
- `ScholarshipApplication` has **no owning-org column** (the only "organisation" field is a free-text referee employer, `models.py:1271`). Confirmed.
- Storage keys are `f"{app.id}/{doc_type}/{uuid4().hex}"` (`views.py:666`) in one bucket `b40-documents` accessed with the service-role key (`storage.py:21,29`). Confirmed.
- `PartnerOrganisation` is a thin referral registry; `PartnerAdmin` carries the role choices + nullable `org` FK. Confirmed.

## 2. Binding amendments to the roadmap

1. **D-10 (new owner decision) — the shared-profile consent gap.** The student's means-test + family-roster data lives on the shared `StudentProfile` (audit hot-spot #1), so a second application automatically carries data entered for the first programme — the PRD's "only what you consented to share" walkthrough over-promises. v1 position: profile means-test data is **student-owned and follows the student**, clearly disclosed in the apply flow ("we've pre-filled this from your profile — review and update"). Do NOT split the god-model in v1. The PRD §4 must be corrected to say this.
2. **Erasure routine must be built before a real second tenant.** PRD §6 promises per-org erasure but no sprint builds it. Add it to Phase 4 (or as an explicit precondition to onboarding tenant #2); the DPA depends on it existing.
3. **Sprint 4 de-risked — NO bulk re-key of existing documents.** All existing objects belong to BrightPath by definition; the fence treats "no org prefix" as org #1 legacy. Prefix **new uploads only**. Bulk re-keying live PII documents is removed from scope (revisit only if an off-boarding/erasure demand requires it). Sprint 4 drops to Medium complexity.
4. **Pre-split the two High sprints now:** Sprint 3 → 3a (gates + org-scoped manager) / 3b (fence-proof + static guard tests); Sprint 8 → 8a (document/route selection) / 8b (fact selection). Plan of record = **15 sprints**.
5. **Naming rule for Sprint 1:** the new tenant FK must not be called `org` — `PartnerAdmin.org` already means *referring* organisation. Use an unambiguous name (e.g. `owning_organisation`), keeping referrer ≠ owner visible in the schema.
6. **Drift guard for D-8:** a constraint or test asserting `application.organisation == application.cohort.organisation` at all times.
7. **PRD §1/§3 inconsistency resolved:** superadmin sets a programme's initial configuration at creation; the org admin may adjust thereafter (within the whitelisted catalogue).
8. **Engine-safety guarantee made mechanical:** per-org config is a whitelisted schema — enums for selectable documents/routes/facts plus the named numeric thresholds only — so there is structurally nowhere to inject bespoke logic (risk #7).

## 3. Positions on the analyst's 10 review questions

1. Fence at the **application** level, profile stays shared — agreed (with amendment #1 above).
2. Django-only fencing is sufficient for v1 (centralised manager + fence-proof test + CI static guard). DB-level defence-in-depth (non-superuser role + per-request org session variable + RLS) is post-v1 hardening — noted, not built.
3. D-8 cohort→org with denormalised org on the application — agreed, with amendment #6.
4. D-1 sponsors — platform-level identity, tenant-scoped pool visibility; build nothing cross-programme in v1.
5. D-5 suspend-not-delete — agreed; erasure is a deliberate off-boarding action and must exist before tenant #2 (amendment #2).
6. Engine guarantee — agreed; enforced per amendment #8.
7. Document re-keying — **overruled**; no bulk re-key (amendment #3).
8. 13 sprints → **15** (amendment #4).
9. Cost metering Option A (platform-metered + tenant tag) — agreed for v1; config designed to hold optional per-org keys later.
10. Referrer vs owner kept distinct — agreed; guarded by amendment #5.

## 4. Open owner decisions (blocking Sprint 1 approval, not Sprint 1 prep)

D-1 (sponsors), D-4 (cost fronting/metering), D-5 (suspend + erasure timing), D-7 (copy documents on reuse), D-10 (profile data follows the student, disclosed) — recommendations for each are in the PRD §8 plus §2.1 above. D-2/D-3/D-6/D-8/D-9 are endorsed as recommended and need no further owner input.

## 5. Sequencing

This programme starts only after the currently queued HalaTuju work is done, via `sprint-start.md`, with the PRD updated for the owner's D-answers first. Roadmap Sprint 1 (Organisation record) is the entry point.
