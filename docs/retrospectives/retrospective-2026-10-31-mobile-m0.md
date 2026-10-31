# Retrospective — Mobile M0: standard, harness, baseline (2026-10-31)

## What shipped
- `docs/mobile-standard.md` (14 rules), `docs/mobile-ledger.md` (generated), `src/lib/mobileClass.ts`
  (94 routes: 64 must / 24 can / 6 desktop).
- `mobileStandard.test.ts`: ratchets that may only go down — small-font fields 182, hidden file inputs 6,
  `fixed inset-0` overlays 18, vh heights 3, `min-h-screen` 71, icon-only `title=` 7.
- `npm run mobile-check`: Playwright, 360/390 px × en/ms/ta, 17 public pages + 18 sandbox surfaces = 210 cells,
  against a committed baseline. Default run measures this branch, with live API reads proxied through the test
  browser; writes, Supabase auth and Turnstile are blocked.
- `viewport` export (`viewportFit: 'cover'`, zoom never blocked), manifest + home-screen icons.
- Workflow lines in `Settings/_workflows/sprint-close.md` and `small-change-lane.md`.

## Numbers (measured)
- Jest 5,568 → 5,616 (18 new + the mentors merge). Gates green. Bundle unchanged.
- Baseline: 30 of 210 cells scroll sideways (Tamil `/` 99 px at 360; officer cockpit up to 257 px); 0 routes
  fully green yet.

## What went well
- The live probe and the browser baseline agreed (Tamil Home 458 px), so the tool measures what a phone sees.
- Blocking anonymous sign-in was caught by the builder before any run touched the real Supabase project.

## What to do differently
- **The first harness measured public pages from production.** A gate that measures the deployed site cannot
  check the change being made. Caught at review; fixed by proxying API reads into the local branch.
- **English measured a spinner.** The server already sends `lang="en"`, so a "language set" wait passed before
  hydration. The check now waits for boot, no spinner, and a quiet DOM.
- **`display: 'standalone'` would have broken iPhone sign-in links** (separate storage, no back button). Shipped
  as `'browser'`; standalone is an M8 decision.

## Carried forward
- M1: Tamil font Mukta Malar; 5.7 MB favicon `src/app/icon.png`; `viewportFit: 'cover'` needs safe-area padding
  on sticky bars (landscape notch).
- Screens not yet measurable (no anonymous route, no sandbox surface) get surfaces in the sprint that fixes them.
