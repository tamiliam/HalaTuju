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

### Sprint 2 — Native application form + single front door (frontend)
- **Goal:** The "Apply" page works end-to-end for returning and fresh students.
- **Scope:** trilingual form (EN/MS/TA); login pre-fill path; fresh-student submit →
  anonymous-sign-in → link-by-NRIC (reuse NRIC hard gate); wire to Sprint 1 API; frontend tests.
- **Acceptance:** returning user sees pre-filled form; fresh user's submit creates account +
  application; no double NRIC entry.
- **Complexity:** Medium

### Sprint 3 — Shortlisting rules engine + Bucket A/B + pass/fail notifications
- **Goal:** Applications auto-sort into FAIL / BUCKET_A / BUCKET_B with the right emails.
- **Scope:** configurable rules engine reading thresholds from `ScholarshipCohort` (grades,
  income band, intent, consent); delayed fail email; pass email; golden-master-style tests using
  the 3 B40 PDF candidates as fixtures.
- **Acceptance:** Priya/Nathiyaa/Theresa fixtures land in expected buckets; emails fire; thresholds
  tunable without code changes.
- **Complexity:** Medium

### Sprint 4 — STEP 1A quiz gate + deeper-info capture
- **Goal:** Passed students complete their course profile (quiz) and submit aspirations + a
  quantified funding need.
- **Scope:** incompleteness-badge gate (reuse) routing to existing quiz; `FundingNeed` model +
  breakdown form; deeper-info fields (aspirations/plans/fears); backend + frontend + tests.
- **Acceptance:** passed student can't reach sponsor stage until quiz done; funding envelope sums
  correctly; returning quiz-completers skip ahead.
- **Complexity:** Medium

### Sprint 5 — Document vault + referee + e-consent (PDPA)
- **Goal:** Students upload supporting docs and give written, age-appropriate consent.
- **Scope:** Supabase private Storage bucket + signed URLs; `ApplicantDocument`, `Referee`,
  `Consent` models; upload UI; versioned consent flow (EN/MS/TA) with guardian gate for under-18s;
  tests.
- **Acceptance:** docs stored privately (no public URL); consent recorded with version/timestamp;
  minor without guardian consent blocked from sponsor exposure.
- **Complexity:** High · *External dependency: lawyer-approved consent wording — build with draft,
  swap before go-live.*

### Sprint 6 — AI-drafted sponsor profile + admin review console
- **Goal:** MyNadi staff review Bucket B, approve AI-drafted profiles, and publish.
- **Scope:** extend `apps/reports/report_engine.py` (Gemini) to draft a sponsor-ready profile from
  intake + deeper-info + notes; admin queues (Bucket B review, profile approval); publish/unpublish
  action; tests.
- **Acceptance:** profile auto-drafted, admin edits/approves, reaches "published" state; full audit
  trail.
- **Complexity:** High

## Dependencies
S1→S2 (form needs API); S1→S3 (shortlist needs application model); S3→S4 (quiz gate is post-pass);
S1→S5 (docs attach to application); S4+S5→S6 (profile draft needs deeper info + docs).

## Open items feeding later sprints
- Exact Bucket A/B thresholds incl. "marginal miss" definition (Sprint 3).
- Funding-envelope size + line items (Sprint 4).
- Lawyer-reviewed consent text (Sprint 5).
- Programme naming/branding within HalaTuju.

## Next step
Sprint 1 complete (17 tests, full suite 1023 green, on branch `feature/b40-assistance`, not yet
committed/pushed). Start Sprint 2 (native application form) via `Settings/_workflows/sprint-start.md`.
