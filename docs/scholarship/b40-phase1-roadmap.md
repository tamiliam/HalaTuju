# Phase 1 Sprint Roadmap — B40 Assistance Programme

**Status:** APPROVED (21 May 2026) · Companion to [b40-assistance-prd.md](b40-assistance-prd.md)
**Phase 1 = Intake & Profile Engine (no sponsor money).** Serves the existing ~51 applicants and
replaces the manual ~20-min-per-profile bottleneck.

## Locked decisions (this session)
- **Custodian:** MyNadi Foundation (tentative). Platform is matchmaker + ledger; never holds cash.
- **Funding model:** 1 sponsor adopts 1 student.
- **Application form:** native in HalaTuju (not Google Forms).
- **Payouts:** prepared automatically, released only on human (MyNadi staff) approval.
- **Apply flow:** apply first; HalaTuju account auto-created for fresh students via NRIC gate;
  course quiz is a required-to-proceed gate at STEP 1A (post-shortlist), never a barrier to apply.
- **Comms (Phase 1):** email (verified Google address) + in-app dashboard. WhatsApp deferred to
  Phase 2, bundled with the planned phone-login work. (~600 students already auth via Google.)
- **No financial return to sponsors, ever** — keeps us a charity, not SC-regulated P2P.

## Sprints

### Sprint 1 — Scholarship app scaffold + application intake API ✅ DONE (2026-05-21)
Intake API + `ScholarshipCohort`/`ScholarshipApplication` models + trilingual ack email + RLS SQL.
17 tests; full suite 1023 green. Branch `feature/b40-assistance` (not merged/deployed; Supabase
migration + RLS not yet applied). See `docs/retrospective-b40-sprint1.md`.

### Sprint 2 — Native application form + single front door (frontend) ✅ DONE (2026-05-21)
`/scholarship/apply` trilingual form; single front door reusing Google + NRIC auth via a new
`'apply'` AuthGateReason; pre-fill from profile; `lib/scholarship.ts` helpers + 13 tests; EN/MS/TA
i18n (793 keys). check-i18n + 30 frontend tests + `next build` green. Not browser-smoke-tested
against a live backend yet. See `docs/retrospective-b40-sprint2.md`.

### Sprint 3 — Shortlisting rules engine + Bucket A/B + pass/fail notifications ✅ DONE (2026-05-21)
Pure `shortlisting.py` engine (A/B/FAIL, cohort-configured thresholds, STR income anchor + 1.15×
marginal band); synchronous shortlist on submit (pass email immediate); trilingual pass/fail
emails; `send_pending_decision_emails` command (delayed fail email); migration 0002 (4 fields).
25 new tests; backend suite 1048 green. Scheduler not yet wired. See
`docs/retrospective-b40-sprint3.md`.

### Sprint 4 — STEP 1A quiz gate + deeper-info capture (split into 4a + 4b)

**Sprint 4a — backend ✅ DONE (2026-05-21):** `FundingNeed` model (OneToOne, computed total) +
deeper-info fields (aspirations/plans/fears/justification) + `PATCH` details endpoint
(own, shortlisted-only) + `completeness` block (`quiz_done`/`details_done`/`funding_done`/`complete`)
on the read serializer. Migration 0003. 11 tests; backend suite 1059 green. See
`docs/retrospective-b40-sprint4a.md`.

**Sprint 4b — frontend ✅ DONE (2026-05-21):** `ScholarshipNextSteps` component — 3-step checklist
(quiz gate → existing `/quiz`, about-you textareas, funding-need form with live RM total) driven by
the `completeness` block; apply page routes shortlisted apps to it; `updateScholarshipDetails` PATCH;
EN/MS/TA i18n (819 keys). 5 helper tests (frontend suite 35); check-i18n + `next build` green. Not
browser-smoke-tested against a live backend yet. See `docs/retrospective-b40-sprint4b.md`.

### Sprint 5 — Document vault + referee + e-consent (PDPA) (split into 5a + 5b)

**Sprint 5a — backend ✅ DONE (2026-05-22):** `ApplicantDocument`/`Referee`/`Consent` models
(migration 0004, RLS); `storage.py` signed upload/download URLs for a private bucket (stdlib urllib,
service key); endpoints (documents sign-upload/list/record/delete, referees, consent); consent
guardian gate (minor <18 from NRIC → guardian required), versioned + superseding. 18 tests; backend
suite 1077 green. See `docs/retrospective-b40-sprint5a.md`.

**Sprint 5b — frontend ✅ DONE (2026-05-22):** `ScholarshipDocuments` (sign → PUT to Storage →
record + list/delete), `ScholarshipReferee`, `ScholarshipConsent` (guardian fields for minors),
wired as next-steps steps 4–6; 10 API client functions; EN/MS/TA i18n (856 keys). 2 helper tests
(frontend suite 37); check-i18n + `next build` green. Upload/consent round-trip not
browser-smoke-tested (needs the live bucket). See `docs/retrospective-b40-sprint5b.md`.

**Deploy carry-forwards:** create the `b40-documents` private bucket; swap the DRAFT consent text
(`CONSENT_VERSION`) for the lawyer-reviewed version.
- **Complexity:** High

### Sprint 6 — AI-drafted sponsor profile + admin console (split into 6a + 6b)

**Sprint 6a — backend ✅ DONE (2026-05-22):** `SponsorProfile` model (draft/edited/status; migration
0005, RLS); `profile_engine.py` (Gemini sponsor-profile drafting from application data); MyNadi admin
API (list/detail/generate/edit/publish) reusing `PartnerAdminMixin`. 9 tests; backend suite 1086.
See `docs/retrospective-b40-sprint6a.md`.

**Sprint 6b — frontend ✅ DONE (2026-05-22):** MyNadi admin console UI — `/admin/scholarship`
(list + status/bucket filter) + `/admin/scholarship/[id]` (full detail + AI profile
generate/edit/publish panel); admin API client functions; admin nav link; EN/MS/TA i18n (894 keys).
Frontend suite 37; check-i18n + `next build` green. See `docs/retrospective-b40-sprint6b.md`.

---

## ✅ Phase 1 build COMPLETE (2026-05-22) — all 6 sprints

Full applicant→admin loop built and locally green (backend 1086, frontend 37, golden masters intact,
migrations 0001–0005), on branch `feature/b40-assistance`, **not deployed**.

## Dependencies
S1→S2 (form needs API); S1→S3 (shortlist needs application model); S3→S4 (quiz gate is post-pass);
S1→S5 (docs attach to application); S4+S5→S6 (profile draft needs deeper info + docs).

## Open items feeding later sprints
- Exact Bucket A/B thresholds incl. "marginal miss" definition (Sprint 3).
- Funding-envelope size + line items (Sprint 4).
- Lawyer-reviewed consent text (Sprint 5).
- Programme naming/branding within HalaTuju.

## Next step
All 6 Phase-1 sprints complete on branch `feature/b40-assistance` (committed; not merged/deployed).
**Next is the single Phase-1 deploy**, gated on these carry-forwards:
1. Apply Supabase migrations 0001–0005 + run the RLS SQL (`apps/scholarship/sql/rls_policies.sql`); confirm Security Advisor 0 errors.
2. Create the `b40-documents` private Storage bucket.
3. Swap the DRAFT consent text (`CONSENT_VERSION`) for the lawyer-reviewed version.
4. Wire the fail-email scheduler (Cloud Scheduler → `send_pending_decision_emails`).
5. Browser smoke-test every flow: apply OAuth, details PATCH, quiz return, upload, consent, admin generate/edit/publish.
6. Merge to `main` (triggers CI/CD deploy).

**Public launch** additionally gated on Phase 0 (confirm MyNadi entity, fundraising permit, lawyer sign-off). **Phase 2** (sponsor portal) follows.
