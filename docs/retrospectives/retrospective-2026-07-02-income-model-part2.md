# Retrospective — Income Model, Part 2 (Phases 2A + 2B + 2C)

**Date:** 2026-07-02
**Worktree:** `.worktrees/str-salary`
**Commits on `main`:** 2A `630c5528` (+ UX fix `c1aef662`) · 2B `62816882` · 2C `3a45f850`
**Migrations:** `0086_income_declared`, `0087_income_nonearning` (both additive, migrate-first via Supabase MCP)
**Live revisions at close:** api `halatuju-api-00612-sgj`, web `halatuju-web-00529-ll9`
**Tests:** 1943 scholarship pytest + 404 jest (both green); `next build` clean
**Plan:** `.claude/plans/robust-jingling-fountain.md` — Part 2 (this closes it; Part 1 = query re-notification, shipped earlier in the arc)

## What Was Built

The B40 income model was extended so a genuinely-poor household is assessed on more than the parents' payslips, without ever gating a decision (P3: trust the student; the officer always decides at interview).

- **2A — Declared informal income.** A salary-route working member with no payslip may declare an average monthly wage. It counts toward per-capita **only** when a valid STR is on file (the STR is the means-test) OR a supporting document backs it (`income_support_doc`: employer/wage letter, bank statements, or a community/penghulu letter — D1 flexible evidence, any one); otherwise it stays *Unsure* and Check 2 raises a flexible doc-request. The single funnel `income_engine.earner_monthly_income` gained a declared branch, so it flows through per-capita → the B40 headroom band with no downstream change. Wizard: a per-member RM field behind a "can't get a payslip?" opt-in (see the UX-fix note below).
- **2B — Unemployment detail.** For an `unemployed` roster member, capture *why* + *since when* (`income_nonearning`), and let an EPF statement corroborate (employer-number all-zeros, or a lapsed last-contribution when that date reads). Soft `unemployment_epf_corroborated` verdict evidence + a Check-2 "why/since" clarify + an optional EPF doc-request. Roster sub-panel (Stitch-approved) gated to the Story context.
- **2C — Household completeness.** Income-proof requests generalised from parents to **every** working roster member (`household_status_gaps`), so a working guardian/sibling with no payslip is chased too. Plus a soft reviewer-only `household_size_confirm` flag when the described people **outnumber** the stated household size (a too-small denominator overstates per-capita).

## What Went Well

- **The single-funnel seam paid off.** Because all income flows through `earner_monthly_income → income_per_capita → income_headroom`, 2A's declared branch and 2B/2C's signals slotted in with zero structural change to the verdict placement logic. Adding inputs at one seam kept the blast radius tiny.
- **Migrate-first was clean both times.** 0086 and 0087 applied additive-then-DROP-DEFAULT via Supabase MCP, verified on the right table (`scholarship_applications`, not the legacy `student_profiles`) with a sibling-column check; the pre-push live code was unaffected. No 500s.
- **Rebasing past a parallel agent worked without incident** — 2B rebased cleanly past the assignment-permission push (no migration collision, auto-merged `services.py`/`CHANGELOG.md`); the pre-push `max(migration)` + merge-base checks (L10/L78) caught it before the push, not after.
- **Investigating before building narrowed 2C by half.** D4 (studying sibling double-counting) turned out already-satisfied by the existing stepper-vs-earner separation — surfaced to the owner instead of building a no-op.

## What Went Wrong

1. **The 2A declared-income field shipped showing too eagerly, needing a same-day 2nd web deploy.**
   - *Symptom:* the RM field appeared the instant a salary-route member was ticked, beside the empty payslip/EPF cards — inviting a student with a payslip to just type a number, inverting the evidence hierarchy.
   - *Root cause:* I gated it only on `!memberHasProof`, conflating "no payslip uploaded yet" with "can't get a payslip." I didn't model the *sequence* a student moves through (they upload, THEN fall back to declaring).
   - *Fix applied:* put it behind an explicit "can't get a payslip or EPF?" opt-in. **System change:** when adding a fallback input beside a primary one, gate it on explicit intent, not on the mere absence of the primary — added as a lesson.

2. **A unit test silently passed a false assumption because the fake test QS ignores `household_member`.**
   - *Symptom:* the 2C `test_working_guardian_surfaces_proof` first failed — a father's salary slip was cross-attributed to the guardian by the fake `_FakeDocs`, so the guardian read as "satisfied".
   - *Root cause:* the `SimpleTestCase` fake QS filters only by `doc_type`, not `household_member` — so any per-member document logic is untestable against it with a shared doc present.
   - *Fix applied:* test the per-member gap path with **no** competing doc on file. **System change:** lesson added — with the fake QS, per-member doc logic must be exercised without a same-type doc for another member, or use a DB `TestCase`.

## Design Decisions

Logged in `docs/decisions.md` (income-model Part 2 block): the accept-on-STR-else-evidence rule for declared income (D1/D2); EPF all-zeros as the deterministic unemployment signal with a best-effort date clause (D3, `statement_date` deliberately excluded); the household-size flag firing **only** on the over-count (applicant-harming) direction (P4); and D4 confirmed already-satisfied (studying sibling never an earner).

## Numbers

- 3 phases, ~2.5 additive columns of schema (2 JSON cols), 0 structural verdict changes.
- Deploys: 2A api+web + 1 web UX fix; 2B api+web; 2C api+web. Each phase owner-gated; 2A used its 2-deploy budget (feature + fix).
- 1943 scholarship pytest (+~49 across the arc) + 404 jest. i18n en/ms/ta throughout.
