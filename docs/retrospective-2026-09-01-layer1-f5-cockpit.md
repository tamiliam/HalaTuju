# Retrospective — Layer 1 F5: the officer cockpit (2026-09-01)

Branch `feat/layer1-f5-cockpit`. No migration. Web only, 2 files. jest 1531 → 1534.
One file, 3,490 lines, 537 utilities — the densest surface in the product.

## What Was Built

- **The cockpit on the theme tokens**, in one pass.
- **Four judgement calls** the codemod could not make, each pinned by a test.
- **The cockpit's ceiling retired**, folding it into the console's conversion walk.

## What Went Well

- **The hunt came back clean for the first time in six sprints.** No hex, no arbitrary-value
  classes, no gradients, no inline colour styles, no entities. Worth noting *why*: this file was
  written recently and in one idiom, where the ones that hid colour (`profile`, `onboarding`, the
  app shells) accreted over a long time. **Age, not size, predicts hiding places** — the biggest
  file in the product was the cleanest.
- **The vocabulary did the work.** 537 utilities, and only four decisions. Six sprints ago the same
  file would have produced dozens of open questions; positive/info/caution/critical, the ground
  roles and `category-N` between them now answer almost everything.
- **The four calls each had a precedent to lean on** — `suspended` (F4) for the HOLD badge, the
  state-versus-kind question (F2b) for the capture chip, the filled-control rule (F1) for the Save
  buttons. Only "unrelated name is critical, not caution" was genuinely new.
- **The F4 bite-check lesson worked immediately.** Injecting *and then verifying* each fault before
  running the suite took seconds and removed the whole class of "is the guard dead or did my
  injection miss?" confusion that cost fifteen minutes last sprint.
- **The "expect exactly 24" tsc rule caught a silent break.** Mid-sprint the count fell to 18 —
  the compiler had stopped early on a parse error that `jest` was happy to ignore. A "fewer is
  better" check would have called that progress.

## What Went Wrong

1. **JSX comments in an expression position, twice, in one sprint.**
   *What:* `{cond && (` followed by `{/* … */}` is a parse error. I did it at the Check-2 summary
   and again at the unrelated-name note.
   *Why:* this is the THIRD variant of the same mistake this session — between attributes (Sprint 5
   and F2b), and now inside a `&&` expression. The pull is always the same: the explanation wants
   to sit next to the thing it explains.
   *Rule, stated once and for all:* **a `{/* … */}` comment is only valid in CHILDREN position.**
   Anywhere else — between attributes, inside a conditional expression, in a ternary — it is a
   syntax error. Put it above the element, or make it a `//` comment inside a `${…}` block.

2. **The cockpit was not reviewed in a browser.** Every other repaint was. Mounting it needs a
   large `AdminApplicationDetail` fixture, which is a piece of work in its own right, and the
   sandbox's own rule forbids a hand-written approximation. **Recorded as a prerequisite for F7**,
   which cannot claim "every surface reviewed in both modes" while this one has never been seen.
   Not hidden in a retro line: it is in the CHANGELOG and the Next Sprint block too.

## Design Decisions

- **"Unrelated name" is `critical`; a generic vision warning stays `caution`.** Two notes in the
  same block, and orange used to separate them. Flattening them onto one tone would have cost the
  officer the distinction that matters most.
- **Provenance is a category where it is a chip, and info where it is prose.** The capture chip
  (deterministic vs model-derived) takes a swatch; the Check-2 briefing takes the info tone,
  because its job is to inform and its heading already says who wrote it.
- **`FactTileTone`'s values stay named `green`/`amber`/`blue`/`red`.** They are an exported library
  type used by the cockpit and its tests; renaming them to the vocabulary would ripple into
  `officerCockpit.ts` and a test file that already carries pre-existing type errors. Out of a
  repaint's scope — the keys are internal aliases, not colours on screen. Noted, not done.
- **No section extraction.** The roadmap allows it here "on readability alone", but the repaint did
  not need it and a 3,500-line restructure is a far larger blast radius than a recolour. Declined.

## Numbers

- Web: 1531 → **1534** jest (+3). `next build` clean; `next lint` 0 errors; `tsc --noEmit` 24
  (unchanged, TD-221); i18n 4581 × 3.
- 537 utilities in one file; 4 judgement calls; ceiling 544 → retired.
- Deploys: 0. Nothing a visitor sees changes.
