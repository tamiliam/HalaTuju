# Retrospective — Code health H5: a test factory that only builds states the product can reach

**Date:** 2026-09-19 · **Roadmap:** `docs/plans/2026-09-18-code-health-roadmap.md` · **Sprint:** H5 of H19
**Built by:** an Opus 5 agent to a written brief; the lead spot-checked the diff and the finding,
re-ran the factory and standards suites, fixed the workspace tool, and closed.
**Freeze status:** in force. Five of the ten sprints to *stabilised*. Run under the owner's standing
word; no stop condition met. Test code only — no application source, no migration.

## What Was Built

- **`apps/scholarship/tests/factories.py`** — `make_org`, `make_admin(role)`, `make_programme`,
  `make_cohort` (always with a programme — since TD-258 a student with none can never be funded),
  `make_student`, `auth_token` / `authed_client` (one home for a JWT helper that **83 files** each
  defined for themselves), and **`make_application(stage=…, outcome=…)`**, which builds an
  application at a named stage with every field the product would have set by then and none it
  would not.
- **`test_factories.py` — the factory may not drift.** For every stage, a fresh application is
  walked there **through the real services and endpoints**, and the factory-built one must match it
  on the stage-defining fields. **No stage is unverified.** Both roads to QC are walked: Recommend
  leaves `verified_at`, `verified_by`, the checklist and the IC lock; Decline leaves **none** of them.
- **20 test files converted; 121 hand-built applications removed; every file's test count
  identical; no assertion changed.**
- **A new standard in the gate:** a test file outside the ledger may not hand-build a
  `ScholarshipApplication`; a listed file's count may not rise; tightness applies. Counted by
  **AST call**, never by text. Ledger: **154 files / 306 calls → 134 / 185.**

## What Went Well

- **The code overruled the brief six times, and the agent let it.** There is no `draft` stage (a
  row is only created at submit). `scored` is a real state with no status of its own. `assigned`
  does not move the status. `verdict_recorded` had to be added — `record-verdict` moves no status,
  and three suites depend on exactly that state. `expired` and `rejected` are *branches*, not points
  on the line, so they must not inherit the rest of the funnel. Had the lead's stage list been
  built as written, the factory would have been the next stale fixture on day one.
- **The suite got faster: 174.6 s → 122.9 s.** `setUpTestData` plus a cheap factory beat twenty
  files of per-test hand-building.
- **Eleven bite-checks, none silent** — including three that prove the converted files kept their
  teeth (`build_verdict` returning `[]` turns 125 tests red).

## What Went Wrong

**1. The factory found the #24 class again, on its first day.**
- *Symptom.* `test_usage_attribution.py::test_an_award_offer_bills_the_tenant` failed the moment
  its cohort was given a real programme.
- *Root cause.* The fixture ended `**({'programme': programme} if programme is not None else {})`
  on a `Sponsorship.objects.create(...)`. `Sponsorship` has **no `programme` column**. The branch
  raised `TypeError` the first time it ever ran — and it had never run, because the hand-built
  cohort had no programme, so the condition was always false. A branch a fixture could not reach:
  exactly what put request #24's bug into production.
- *System change.* The dead branch is removed (assertions untouched) with an `# H5-FINDING` comment
  in place. The lasting change is the factory itself: its default cohort always has a programme, so
  no future fixture can sit in that blind spot by accident.

**2. The lead's tool called a new standard a loosening.** `code_health.py`'s new `std` reading
(one day old) treated *any* new key in a budget as a new exemption, and FAILed on the new
`hand_built_application_fixtures` ledger. A new **standard** makes the rules stricter. Fixed: a new
key at the top of the budget is a new standard; a new key deeper is a new member of an exemption
list, and still fails. Tested both ways. *The agent was told to expect this and to report it
verbatim rather than work round it — which it did.*

**3. 134 files still hand-build.** Deliberate: H5 converts the twenty that matter most; the rest
move when next touched, and the gate makes sure the number only falls. Recorded, not regretted.

## Loopholes that remain (the agent's list, kept honest)

- A helper in a non-test module that wraps `objects.create` under another name is not counted.
- `bulk_create` / `get_or_create` / `update_or_create` are not counted (none exist today).
- The drift test compares a **declared** set of stage fields. A new column the product starts
  stamping is invisible until someone adds it to that set.
- `make_application(stage='rejected')` assumes the QC-decline road; a contractual reject from
  `recommended` needs `**overrides`.
- The org fence is now load-bearing in fixtures: a non-super admin needs the cohort's organisation
  or every request 404s. It bit four times during conversion; it is documented at `make_admin`.

## Numbers

| | Before | After |
|---|---|---|
| pytest `-n auto` | 6,760 passed · 3 skipped · 174.6 s | **6,803 passed · 3 skipped · 0 failed · 122.9 s** |
| Hand-built applications | 306 calls in 154 files | **185 in 134** |
| Files with a private JWT helper, of the 20 converted | 20 | 0 |
| `hot#1` reading | 290.6 | **273.5** (time moved the 90-day window; no source changed) |
| App source changed | | none |
