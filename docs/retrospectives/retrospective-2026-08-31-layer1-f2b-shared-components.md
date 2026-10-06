# Retrospective — Layer 1 F2b: the rest of the shared components (2026-08-31)

Branch `feat/layer1-f2b-shared-components` (worktree `.worktrees/layer1-f2b`). No migration.
Web only, 29 files. jest 1493 → 1507. `src/components` is now converted except
`ScholarshipDocuments.tsx` (F3) and 48 deliberately-exempt category utilities.

## What Was Built

- **20 components fully repainted** (273 utilities), **4 more converted in their ground only**
  (81 utilities), leaving their category hues literal by design.
- **Three semantic corrections**: the sponsor landing's two CTAs and step numbers, and the sign-up
  submit → brand, not the info tone. The selected state in `SponsorNotifyPrefs` → brand.
- **A guarded exemption** for the category palettes, plus a ceiling that now names one file.
- **Two sandbox surfaces**, one of which exists to put an open question in front of the owner.

## What Went Well

- **Measuring before converting caught a silent data-destroying rename.** The plan was "run the
  codemod over 24 files". Reading the four files that reported out-of-vocabulary colours first
  showed that a blind run would have merged `poly` with `ILJTM` and `sains_komputer` with
  `sains_sosial`. Both would have looked like a clean conversion, passed every gate, and quietly
  removed a distinction students rely on to compare courses.
- **The protection was mechanical, not manual.** Rather than hand-editing four files after the
  fact, the conversion script snapshotted each categorical region, ran the codemod, and restored
  the regions by matching on the text the codemod itself would have produced — so a restore that
  did not find its target aborted the run instead of silently skipping.
- **The F1 rule held for a third sprint** and found three more mis-classified CTAs. It is now
  worth treating as a checklist item rather than a discovery: *every* repaint sprint should grep
  its surface for `bg-info-[567]00` next to `text-white`.
- **Bite-checking four guards took under a minute** and each fault was caught by exactly one.

## What Went Wrong

1. **I put JSX comments between element attributes — again, three times, having made the same
   mistake in Layer 0 Sprint 5.**
   *What:* `{/* … */}` placed inside an opening tag between `href` and `className`. `tsc` and
   `next lint` both failed with `'...' expected`.
   *Why:* it reads naturally — the comment explains the attribute below it — and it is invalid
   JSX. Knowing it once did not prevent it, because the mistake is made at the moment of writing a
   justification, when attention is on the reasoning rather than the syntax.
   *System change:* recorded in `docs/lessons.md` with the fix shape (the comment goes ABOVE the
   element, never inside the tag). The real safety net is that `tsc` catches it in seconds — the
   cost was one gate cycle, not a defect.

2. **`tsc` reported 3 errors and I nearly read it as good news.** The count had been 24
   (pre-existing, TD-221) for two sprints; a syntax error made the compiler stop early, so the
   number FELL. A dropping error count on a codebase with known debt is a signal to look, not to
   celebrate. *System change:* the gate is now run as "expect exactly 24", not "expect fewer".

3. **The category-colour problem was invisible until the fourth file.** The codemod's "left alone
   (outside the four tones)" report is what surfaced it, and only because purple/teal/lime are
   outside the vocabulary. Had those palettes used only green/blue/amber/red — as
   `SpecialConditions` half does — nothing would have flagged them and the collapse would have
   shipped. *System change:* the `CATEGORICAL` guard is a closed list, so the next repaint sprint
   has to consciously decide whether its surface contains one.

## Design Decisions

- **A category palette is not a tone, and is exempt until the product has a name for it.**
  Recorded in `docs/decisions.md`, with the two concrete collapses it prevents.
- **The exemption is for hues only.** Every exempt file's ground is still converted and tested, so
  none of them is a whole-file island — only its chips are.
- **A filled CTA is brand; a text link is a tone; a selected state is brand.** The rule now has
  three settled cases across three sprints.

## Numbers

- Web: 1493 → **1507** jest (+14). `next build` clean (81 routes); `next lint` 0 errors; i18n
  4581 × 3; `tsc --noEmit` 24 (unchanged, TD-221).
- 354 utilities converted; **48 deliberately exempt**; ceiling 659 → **287** (one file, F3's).
- Deploys: 0. Nothing a visitor sees changes.
