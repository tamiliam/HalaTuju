# Retrospective — Layer 1 F3: the student surfaces (2026-08-31)

Branch `feat/layer1-f3-student-surfaces` (worktree `.worktrees/layer1-f3`). No migration.
Web only, 24 files, ~1205 utilities. jest 1509 → 1515.

## What Was Built

- **Every surface a student sees, on the theme tokens** — the whole scholarship journey, profile,
  onboarding, dashboard, saved, settings, verify-email, report, and `ScholarshipDocuments.tsx`
  (288 utilities, the largest single file in the product).
- **The three app shells** (`error`, `loading`, `not-found`) folded in, because they carried the
  same hidden page ground.
- **Two hiding places closed**: arbitrary-value colour classes, and raw hex in SVG props.
- **Two semantic corrections**, and the `src/components` ceiling retired.

## What Went Well

- **Hunting before converting is now the highest-value half hour of a repaint sprint.** The
  pre-conversion scan found `bg-[#f8fafc]` in six files and hex SVG props in two, before the
  codemod ran. Three sprints ago that scan did not exist; it has now found something every time.
- **The biggest file was the easiest.** `ScholarshipDocuments.tsx` (288 utilities) converted
  mechanically with one human note, because its only colour table is a genuine STATE map
  (match / partial / mismatch / unreadable → positive / caution / critical / ground). Size was
  never the risk — ambiguity is.
- **The `graduated` problem resolved inside the vocabulary.** A set needing two "good" states
  looked at first like a case for a fifth tone or a category swatch. Both would have been wrong;
  weight (filled vs tinted) said the same thing with what already existed. Worth remembering
  before reaching for a new token: **the ramp has stops, and a stop is a legitimate axis.**
- **A directory walk instead of a file list.** F2a and F2b both used hand-lists, which cannot fail
  on a page that does not exist yet. F3's guard walks the student routes, so a new page under any
  of them is caught the day it is added.

## What Went Wrong

1. **The roadmap's F3 scope was 16 files; the real surface was 18, plus 3 shells.**
   *What:* the plan said "16 files, 234 chromatic and 636 ground". The measurement found 18 student
   files totalling ~1193, plus three app shells carrying the same defect.
   *Why:* the roadmap measured on 2026-07-29 and the product has had five sprints since. This is
   the Layer 0 Sprint 4 lesson repeating — a plan's file table is a hypothesis about where the work
   lives, and it ages.
   *System change:* none needed; re-deriving at sprint start is already the rule and it worked.
   Recording it because it is now the second time the rule has paid.

2. **A near-white patch in dark mode that no test can fail on.** `bg-primary-50` used as a surface
   stays pale in dark, because `--brand-*` deliberately has no dark variant. Readable, and wrong
   looking. **Not fixed** — it is product-wide (101 uses, 40 files) and resolving it means
   revisiting an owner ruling. Raised, with the same shape as F2b's category question.
   *System change:* recorded in `docs/decisions.md` as an open question with the trigger written
   down (before F7), so it cannot be discovered again from scratch.

## Design Decisions

- **`graduated` is distinguished by WEIGHT, not hue** — same tone, filled instead of tinted.
- **The app shells belong to whichever sprint finds their defect**, not to a sprint of their own.
- **The ceiling retires when its last file converts** rather than lingering at zero: a ratchet that
  guards nothing is noise in the suite.

## Numbers

- Web: 1509 → **1515** jest (+6). `next build` clean; `next lint` 0 errors; `tsc --noEmit` 24
  (unchanged, TD-221); i18n 4581 × 3.
- 24 files, ~1205 utilities. 6 arbitrary-value page grounds and 6 SVG hex props tokenised.
- Both modes reviewed in the browser; mid-session flip test passed.
- Deploys: 0 so far. Nothing a visitor sees changes.
