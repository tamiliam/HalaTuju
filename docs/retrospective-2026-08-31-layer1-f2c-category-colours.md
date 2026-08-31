# Retrospective — Layer 1 F2c: the category colour family (2026-08-31)

Branch `feat/layer1-f2c-category-colours` (worktree `.worktrees/layer1-f2c`). No migration.
Web only, 8 files. jest 1507 → 1509. **The owner chose to build the family** — the option F2b
raised — so F7 is no longer blocked.

## What Was Built

- **A fifth token family**, `--category-1…8`, three roles each (`surface`, `ink`, `dot`), defined
  in both modes and wired through `tailwind.config.ts`.
- **The four category files converted** onto it, and two pre-existing colour collisions fixed
  along the way.
- **Three layers of guard**: the files must be fully converted; each file must use as many
  DISTINCT swatches as its set has members; and the family itself must stay distinct, readable and
  clear of the tone hues, in both modes.

## What Went Well

- **F2b's refusal to guess paid off exactly as intended.** The four files were left literal with a
  written reason and a guarded exemption, so this sprint was a conversion with a clear brief
  rather than an archaeology exercise. Had F2b "just converted them", the collapse would have been
  live and invisible, and no later sprint would have had a reason to look.
- **Two bugs fell out of the work that nobody was looking for.** `ua`/`pismp` (institution types)
  and `noColorblind`/`noDisability` (entry conditions) were each rendered in the same colour
  already — the sets were partly broken before any theming work started. Counting the swatches a
  set NEEDS is what surfaced them; reading the code never would have.
- **The guard tests the property, not the values.** "Eight swatches, all different, ink readable
  against its own surface, opposite way round per mode" holds through any future retune. The F2a
  ground lesson — pin the relationship, never the formula — transferred directly and was cheaper
  to apply here because it was applied from the first line rather than after a browser pass.
- **Values generated from `tailwindcss/colors`, not typed.** Same rule as the tone ramps; no
  hand-copied hex to mistype, and the choice of hue is auditable.

## What Went Wrong

1. **The sandbox surface still described the problem after the problem was solved.**
   *What:* `category-colours` kept its F2b note — *"they DO NOT follow dark mode: that is the
   gap"* — while the screenshot beside it showed the gap closed.
   *Why:* the note was written to make a case to the owner. Once the case is won, it is stale
   documentation sitting in front of the next person who opens the sandbox.
   *System change:* fixed in the same sprint, and worth generalising — **a surface note that argues
   for a decision has to be rewritten by whichever sprint acts on it.** Added to the sandbox's own
   header comment as part of what a surface owes.

2. **A third `Edit` failed on CRLF line endings, and I again fell back to a Python splice.**
   Three sprints, three times. It is not costly (about a minute each) but it is predictable, and
   the fix is known: multi-line edits against this repo's CRLF files should go through a script
   from the start rather than after a failed attempt.

## Design Decisions

- **A category is a fifth kind of colour, not a fifth tone.** Recorded in `docs/decisions.md`,
  superseding the F2b entry that deferred it.
- **Roles, not stops**, and **dark as a role swap, not a mirror** — both recorded, both guarded.
- **Hues avoid the tone families** so a category chip can never be misread as a status.
- **Numbers are arbitrary and carry no order.** `category-3` is not "worse" than `category-2`;
  a new field of study takes any unused number.

## Numbers

- Web: 1507 → **1509** jest (+2 net; the F2b exemption block was replaced by stronger checks, so
  the count understates the change — 4 exemption tests removed, 6 family tests added).
- Files: `globals.css`, `tailwind.config.ts`, 4 components, `theme.test.ts`, `surfaces.tsx`.
- 48 previously-exempt utilities converted; **0 raw colour left** in all four files.
- `next build` clean; `next lint` 0 errors; `tsc --noEmit` 24 (unchanged, TD-221); i18n 4581 × 3.
- Deploys: 0 so far. Nothing a visitor sees changes.
