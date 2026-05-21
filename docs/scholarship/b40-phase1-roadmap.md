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
Sprints 1-2 complete on branch `feature/b40-assistance` (committed; not merged/deployed). Start
Sprint 3 (shortlisting rules engine + Bucket A/B + pass/fail emails) via
`Settings/_workflows/sprint-start.md`. Pending before Phase 1 ships: apply Supabase migration + RLS,
and a browser smoke test of the apply OAuth round-trip.
