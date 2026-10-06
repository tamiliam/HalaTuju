# Retrospective — Layer 1 F2a: the shared student-journey components (2026-08-31)

Branch `feat/layer1-f2a-shared-components` (worktree `.worktrees/layer1-f2a`). No migration.
Web only, 34 files. jest 1482 → 1493.

## What Was Built

- **27 components repainted** onto the theme tokens — the student-journey half of
  `src/components`. 386 utilities converted mechanically, every line read afterwards.
- **Two hand corrections the codemod could not make**: the funding bar is brand, not a tone; the
  verified tick's white stroke is a literal, not a ground stop.
- **Three shared dark-mode defects fixed** — the ground ramp, `body`, and `.input` (below).
- **Guards**: a reusable per-surface conversion check (F1's portal and F2a's list), a ratchet over
  F2b's half, two ground-role guards, and a guard over the stylesheet itself.
- **Three sandbox surfaces** so this and every later repaint sprint can be looked at.

## What Went Well

- **The codemod did its 88% and the review found the other 12%,** exactly as F1 predicted. 386
  utilities, one file needing a note (`slate` → ground), two semantic corrections. Budgeting review
  time as a first-class part of the sprint is what made those two visible.
- **The browser pass earned its place three times over.** All three of the defects below were found
  by looking at a screen, not by a failing test — and two of them (`body`, `.input`) would have
  shipped a broken dark mode across the entire product, not just this sprint's files.
- **Bite-checking four guards at once** took about a minute and proved each one independently.
- **The `.input` fix is a one-line change with product-wide reach**, which is the whole argument
  for `@layer components` existing. Finding it here rather than in F6 saved five sprints of
  reviewing screens with white boxes in them.

## What Went Wrong

1. **The dark ground was a reversal where it needed to be a design.**
   *What:* every card, input and modal rendered pure black on a `#111827` page — they read as holes
   punched through the page rather than objects resting on it.
   *Why:* F1 derived the whole dark set by reversing the light one, which is correct for the four
   tones (a signal only has to stay legible) and wrong for the ground. In light the raised surface
   is white — the EXTREME of the ramp; reversing puts it at the extreme of the other end, which is
   the bottom. The ramp's stops carry ROLES (raised / page / well / border), and a reversal
   preserves values while destroying roles. F1's own retro flagged "saturated mid-stops want an
   eye" and carried a tone-tuning pass into F2a — but it named the tones, and the real casualty was
   the ground.
   *System change:* the ground ramp is now written as roles with the reversal deliberately broken
   at `ground-0`, and `theme.test.ts` pins the PROPERTY (`raised` is lighter than `page`, in both
   modes; every role holds a distinct value) instead of the derivation. A future tuning pass can
   pick any numbers it likes and still cannot reintroduce this.

2. **`body` and `.input` were raw colour in the stylesheet, where no scan was looking.**
   *What:* `body { @apply bg-white text-gray-900 }` — a white page in dark mode, product-wide. And
   `.input` had no background at all, so every text control fell back to the browser's own white.
   *Why:* every conversion guard in the project reads `.tsx`. `globals.css` is not a component and
   not a surface, so it belonged to no sprint's file list and was never scanned. The `.input` case
   is worse than an oversight: nothing was *wrong* with the markup — the colour was coming from the
   user agent, so there was no line of code anywhere to find.
   *System change:* a guard over `@layer base` and `@layer components` for raw colour, plus one
   asserting every text control declares a background. F1's lesson said "enumerate the ways the old
   thing can be spelled" and listed inline styles, SVG fills and lib constants; **the stylesheet
   and the user-agent default are now on that list.**

3. **The guards flagged their own documentation, twice.**
   *What:* the hex scan reported `#15a`/`#15b` (audit references in `ActionCentre`'s comments,
   three valid hex digits) and `#fff` — from the comment explaining why `#fff` had been removed.
   Then the stylesheet scan reported `bg-white`/`text-gray-900` from the comment explaining why
   `body` no longer says them.
   *Why:* a guard that greps source text cannot tell code from prose, and the most likely place to
   *write* a forbidden string is the note explaining why it is forbidden.
   *System change:* one shared `withoutComments()` helper, applied before every text scan in the
   file. Without it the only way to pass the guard is to stop explaining yourself.

4. **A fresh worktree had no `node_modules` — again.** Same as Layer 0 Sprint 5, same junction fix.
   The lesson was written and did not prevent it, because it lives in `docs/lessons.md` and nothing
   reads that at worktree-creation time. *System change:* raised as a line in the sprint-start
   note below rather than a fourth lesson nobody will read at the right moment.

## Design Decisions

- **The ground is designed; the tones stay reversed.** Recorded in `docs/decisions.md`.
- **A progress fill is brand, not a tone.** It carries no semantic state, and a tenant's colour
  should reach it. The mirror rule holds: the "done" medallions and the toast keep their tones,
  because those DO carry state and a tenant must never repaint "this succeeded".
- **`orange` stays literal on the grade badges.** The vocabulary has four tones; the badges are a
  ramp of six. Inventing a fifth tone for one badge would be a worse lie than a colour that does
  not follow the theme. Flagged for F6 to settle.
- **The F2b ratchet is scoped to `src/components/*` only.** `components/admin` belongs to F4 and is
  under active feature work — freezing its colours now would fail the next ordinary admin page with
  no sanctioned way to pass.
- **`ScholarshipDocuments.tsx` deferred to F3**, per the roadmap. At 293 utilities it is a third of
  the directory and would have swamped the review this sprint depended on.

## Numbers

- Web: 1482 → **1493** jest (+11). `next build` clean (81 routes); `next lint` 0 errors; i18n
  parity 4581 × 3. `tsc --noEmit` 24 errors — unchanged from main, all pre-existing (TD-221).
- Files: 27 components + `globals.css` + `theme.test.ts` + 3 sandbox files + 2 sandbox chrome files.
- Raw colour: 386 utilities converted; F2b's remaining half measured at **659** and ratcheted.
- Deploys: 0. Dark mode is still unreachable in production; this sprint changes nothing a visitor
  sees except the page ground going from `#ffffff` to `#f9fafb`.
