# Programme Overview phase 2 — roadmap (2026-09-18)

Owner rulings: the layout is **per organisation**, set by the org admin; order of work = intake-year
filter, widgets on/off, then drag-and-drop order. The approved plan (settled design, file lists,
tests, bites) lived in `.claude/plans/` during the build and is summarised here so it survives the
sprint close.

**Status 2026-09-19: BOTH SPRINTS ARE SHIPPED. The phase is complete.**

| Sprint | Goal | Status |
|---|---|---|
| **A** | Intake-year filter + widgets on/off, per organisation | ✅ **SHIPPED 2026-09-18** — live in production, backend migrate-first (`0161_overview_layout`). Retro: `docs/retrospective-2026-09-18-overview-phase-2-sprint-a.md`. (The row said IN PROGRESS until 2026-09-19; it was stale.) |
| **B** | Widget ORDER | ✅ **SHIPPED 2026-09-19 — up/down arrows only; DRAG-AND-DROP WAS NOT BUILT** (see below). No backend change, no migration: the stored list was already ordered and validated as a permutation in A. Retro: `docs/retrospective-2026-09-19-overview-sprint-b.md`. |

### Sprint B — what was built, and what was not

**Built:** an Up and a Down arrow on every card of the existing Customise screen, reusing the pure
`overviewLayout.moveItem`; the ends disabled; every arrow a 44px square named for its panel AND its
direction; the moved row keeps the keyboard, including the end case where the arrow just pressed
becomes disabled; three new locale keys × three languages; three rendered tests on the real page
and five on the editor; five bite-checks, five bit.

**Not built — native HTML5 drag-and-drop, and the reason is not cost.** Five rows do not earn a
drag gesture, and a dragged card is the one arrangement a test cannot honestly prove: jsdom's
drag-and-drop is a stub, so a `drop` the test fires itself shows the handler ran and says nothing
about the order the pointer promised. `overviewLayout.ts` had recorded exactly that since Sprint A,
one paragraph above the helper the drag would have used. Buttons a person can tab to are testable
end to end, work on a phone, and work for somebody who never uses a mouse. **`reorderByDrop` stays
in the module, unused and still unit-tested, with a comment saying why** — so a later sprint that
adds a drag on top has the arithmetic, and nobody deletes it as dead weight.

**Not built — a live region announcing the new position.** The quality bar asked for one *if the
codebase already had a pattern*. It does not: the single `aria-live` in the tree is an assertive
error alert on the apply page, and `SaveBar` has no `role="status"`. Inventing a polite-live-region
convention inside a five-row editor would have made this sprint the author of a platform pattern
nobody reviewed. Recorded here rather than done. **Focus retention is what carries the news
instead** — the moved row keeps the keyboard, so the next thing read is that row.

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
- **Sprint B:** ~~up/down buttons are the keyboard/touch path; native DnD for the mouse~~ —
  **revised on the build: up/down buttons ONLY** (see "what was built, and what was not" above).
  One pure helper module (`src/lib/overviewLayout.ts`) does the arithmetic and carries the tests.

## Out of scope (named so nobody guesses)

Per-role layouts; per-person layouts; an intake filter on the Applications list; pathway/stage
filters.
