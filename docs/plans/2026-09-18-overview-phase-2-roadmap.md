# Programme Overview phase 2 — roadmap (2026-09-18)

Owner rulings: the layout is **per organisation**, set by the org admin; order of work = intake-year
filter, widgets on/off, then drag-and-drop order. The approved plan (settled design, file lists,
tests, bites) lived in `.claude/plans/` during the build and is summarised here so it survives the
sprint close.

| Sprint | Goal | Status |
|---|---|---|
| **A** | Intake-year filter + widgets on/off, per organisation | IN PROGRESS (backend shipped to production migrate-first: `0161_overview_layout`) |
| **B** | Widget ORDER: up/down buttons + native HTML5 drag-and-drop, no library | Not started — no backend change needed (the stored list is ordered and validated as a permutation in A) |

## Settled design (do not re-litigate)

- **Storage:** `OrganisationOverviewLayout` (scholarship; `organisation` OneToOne, `sections` JSON
  = ordered `[{key, on}]`, `updated_by_email`). Not an `org_config` JSON kind: that module is "a
  catalogue, not a form builder". `save()` validates through `overview_layout.validate_sections`.
- **Applied in `programme_overview.build()`** as a NARROWING of the role's sections, in layout
  order; never a widening. `mine` / `qc` are pages, not widgets — outside the catalogue, never
  switchable. Everything hidden → `sections: []` with a 200.
- **Who customises:** `org_admin` + super. `layout` (keys + flags, never data) rides on the payload
  for them only; the page shows the Customise button by its PRESENCE.
- **Intake filter:** `?intake=<cohort id>`; wrong tenant / wrong gift / unknown / non-integer → 404
  (`_AdminBase._intake_narrowing`, on the base so the Applications list can follow). EVERYTHING
  narrows, the money strip included; the byte-equality reconciliation tests run unfiltered.
  `intakes` (name, year, state) rides on every role's payload — a date, not a person or a sum.
- **Sprint B:** up/down buttons are the keyboard/touch path; native DnD for the mouse; one pure
  helper module (`src/lib/overviewLayout.ts`) does the arithmetic and carries the tests.

## Out of scope (named so nobody guesses)

Per-role layouts; per-person layouts; an intake filter on the Applications list; pathway/stage
filters.
