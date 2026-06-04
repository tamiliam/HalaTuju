# Retrospective — Income Check-1 (item 3: earner identity + relationship) — 2026-06-04

The fourth and final verification fact. Turned Income from a weak "is a document present?" check into a guided
wizard + a deterministic earner-identity/relationship verdict, in three sprints (I1 backend, I2 verdict, I3 wizard UI),
shipped as one migrate-first deploy.

## What Was Built
- **I1 — `income_engine.py`** (pure): `income_requirements` matrix (route × earner × work-status → compulsory/optional
  docs), `father_name_from_ic` (patronymic parser), `father/mother/guardian_relationship` checks; the **Birth
  Certificate** doc type + Gemini reader; migration `0039` (six additive wizard fields + the doc type). 28 tests.
- **I2 — verdict + reason codes.** `verdict_engine._verdict_income` rewritten onto `income_requirements` →
  verified / recommend / review / gap, with the **never-block** rule (informal/no-EPF → `recommend` +
  `income_unverified_needs_interview` interview flag). 11 new reason codes through the full four-link chain
  (verdict → `CODE_TO_TICKET` → officer i18n → student i18n + `KNOWN_CODES`), en/ms/ta. Officer Income tile renders
  them dynamically (no new component).
- **I3 — the student wizard.** `lib/incomeWizard.ts` (pure, mirrors the backend) + the `IncomeWizard` component under
  Documents → Household income (questions + burden steppers → dynamic checklist), saving via the details PATCH;
  `birth_certificate` doc-card copy; wizard i18n.

## What Went Well
- **The FE checklist and the officer verdict can't diverge** — `lib/incomeWizard.ts` mirrors `income_engine`
  one-to-one, with parallel test suites (Python 28 + jest 10) asserting the same scenarios.
- **The four-link reason-code lesson held** — all 11 new codes were verified to resolve on both the officer tile and
  the student Action Centre before commit (a scripted check), so no repeat of the `offer_no_identity` raw-key bug.
- **Never-block is structural, not a copy promise** — the verdict routes thin evidence to `recommend` + an interview
  flag, so a poor family with no payslip is reviewed by a human, never auto-rejected.

## What Went Wrong
1. **A TS union widened to `string` and broke `next build`.** *Symptom:* `incomeRequirements(ans)` failed type-check —
   `ans.income_route` was `string` (from `app.income_route || ''`), not the `'' | 'str' | 'salary'` union. *Root cause:*
   `x || ''` widens a string-literal union to `string` in inference. *Fix:* build a typed `answers` object with explicit
   `as IncomeRoute` casts at the call sites; caught by running the real `next build` (not just jest) before commit.
2. **`sqlmigrate` shows SQLite DDL, not the prod (Postgres) DDL.** *Symptom:* the local `sqlmigrate 0039` printed a full
   table-rebuild (SQLite's `ADD COLUMN` strategy), which is NOT what runs on Supabase Postgres. *Root cause:* dev is
   SQLite, prod is Postgres; the two backends emit different DDL. *Fix:* for migrate-first, apply the **Postgres**
   `ALTER TABLE ADD COLUMN`s directly via the Supabase MCP (verified the columns + the `django_migrations` row after),
   rather than trusting the local `sqlmigrate` output.

## Design Decisions
- **Two-track wizard (STR vs salary) with the relationship proof common to both** — the earner-identity + family-link
  proof is independent of how income is evidenced; only the income docs differ by route. (`decisions.md`.)
- **Never-block via `recommend` + interview flag** — informal-income families can't produce a payslip, so the
  deterministic layer surfaces the concern and a human decides, rather than a hard gate. (`decisions.md`.)

## Numbers
- 3 sprints, 4 local commits (`9fa5ffe` I1 · `d151bf6` I2 · `a8bcd75` I3 · + this close). **1680 pytest**
  (1037 courses/reports + 643 scholarship), **jest 40**, i18n parity **1900×3**, `next build` clean. Migration `0039`
  applied migrate-first via Supabase MCP. **Live click-through pending (TD-070).**
