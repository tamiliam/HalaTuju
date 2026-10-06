# Retrospective — Post-award lifecycle Sprint 1: rename `accepted` → `recommended` (2026-06-28)

Roadmap `docs/scholarship/post-award-lifecycle-plan.md`. Commits `76a7ae06` (mask, folded in) +
`6a9ddc58` (rename). Deployed to `main`; 23 prod rows migrated; migration `0073` recorded.

## What Was Built
First slice of the post-award lifecycle. The application status `accepted` was renamed to
`recommended` — a more honest label (the reviewer *recommends*; no award is guaranteed until a funder
commits at `awarded`, a later sprint). Behaviour-neutral. Done as **expand-contract**: `recommended`
is canonical (verify-&-accept write, reopen-restore, every status set/label/colour/the student mask),
while legacy `accepted` is **tolerated** for one release (choices, mask, the behaviour frozensets) so
the deploy was order-independent for the 23 live rows. Migration `0073` is **state-only** (choices are
app-level — no DDL). Folds in the just-built student-masking change (now masks `recommended`).

## What Went Well
- The expand-contract approach made the deploy a non-event: code (tolerant of both) went live first,
  then the 23 rows were migrated via MCP `RETURNING` (confirmed 0 `accepted` / 23 `recommended`) — no
  window where the live site misread a real student.
- Surveying the blast radius up front (a `'accepted'` grep across prod + tests) caught the three
  non-status `accepted` usages (sponsor-feed event type, `OutcomeStatus`, `award.status`) that must
  NOT be renamed, and the frozen migration snapshots that must NOT be edited.
- Delegating the ~16-file test-fixture sweep to one focused agent (pytest-gated, production untouched)
  kept the mechanical bulk off the critical path; reviewed via the diff.

## What Went Wrong
- **`makemigrations` swept in an unrelated pre-existing drift** (a `ScholarshipCohort.name` help_text
  change someone left un-migrated). *Symptom:* my rename migration `0073` contained a third, foreign
  `AlterField`. *Root cause:* a model edit on `main` was never migrated, so the next `makemigrations`
  attributed it to my change. *Fix:* removed the foreign operation from `0073` so it's purely the
  status-choices change. *System change:* lesson added — after `makemigrations`, read the generated
  file and drop operations you didn't author (model/migration drift attaches to the next migration).
- **`next build` hit the known static-worker OOM** on the 8 GB box (first run crashed at static-page
  generation; type-check had already passed). Not new — re-ran clean. (Already a known local-resource
  transient; Cloud Build has more memory.)

## Design Decisions
- Rename the status *value* (not just the display label) `accepted → recommended`, via expand-contract
  with a one-release legacy tolerance. (Logged in decisions.md.)

## Numbers
- Backend `pytest apps/scholarship/tests/`: **1629 passed**. jest **373**. `next build` clean.
  i18n parity **2877 × 3**. 1 migration (state-only). 2 commits. 23 prod rows migrated. 1 deploy
  (api + web), both SUCCESS.
