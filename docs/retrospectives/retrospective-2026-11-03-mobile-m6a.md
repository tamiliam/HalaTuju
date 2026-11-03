# Retrospective — Mobile M6a: the console shell, case list and everyday pages on phones (2026-11-03)

## What was built
- **Phase 1 — TD-470 closed first.** `/scholarship/apply` had 0.24 kB under its line. The weight was not M5's: three
  `NEXT_PUBLIC_` names a build may leave unset stayed live `process.env` reads, so webpack copied its `process`
  polyfill (~0.8 kB gz) onto 89 of 102 routes. `next.config.js` now defines each as `''` when unset; a guard
  (`publicEnv.test.ts`) fails on any client read of an undefined public name. Every student route lost ~1.5 kB; lines
  lowered (median 147 → 145, `/profile` 194 → 193, `/scholarship/application` 208 → 206).
- **M6 split (owner):** M6a now, M6b (the case page, documents and viewer) next. Owner answers for M6b are recorded:
  PDFs open in the phone's own viewer; the decision bar jumps to the decision section and never saves; tranche and
  payment actions are read-only on a phone.
- **The console on a phone:** one pinned 44 px row; a phone menu with the account row, the switchers, Guide, FAQ,
  Profile, the theme and Log out (the account menu's own `signOut`, guarded word for word).
- **The case list:** rows that open the case; filters in a Sheet (the desktop's own controls); Sort on phones; why an
  Assign is disabled written under it; the assign error shown on phones too.
- **Rule 15** on the sign-in screens, Guide, FAQ, Organisation, the Profile cards and the 404; 44 px Pagination arrows
  on all 11 screens that use it.

## Numbers (measured)
- Jest 6,189 → 6,202 (399 suites). mobile-check 498 → 528 cells; 30 new admin cells at 0, 24 better, none worse.
- Bundle: no line raised; `/scholarship/apply` 185.206 kB (1.79 kB room); median 143.752.
- Deploys: 1 (web only; build c112c758).

## What went well
- **Measuring before blaming.** The M5 retro guessed M5 had spent the apply route's room; phase 1 measured M5 at 0 and
  found an older, wider cost that every route had paid since the public names were added.
- **The adversarial review checked production, not just the diff:** it traced the Turnstile key and the version through
  the Dockerfile and `cloudbuild.yaml` before accepting the `''` defines.

## What went wrong
- **The M5 retro named a cause it had not measured** (the StudentMenus → DisplaySegments move). *Why:* the number was
  a peer's and the cause was inferred. *Prevention:* a retro states a cause only with a measurement; otherwise "not yet
  traced".
- **The filter Sheet's footer showed the previous count while a new filter loaded** (review, minor). Fixed in 2ef29328.

## Close review
- **Adversarial review (before the push):** no blockers; sign-in, scope, production env and role visibility clean.
  One minor fixed (stale count). Accepted: both filter copies showing if a phone rotates to `md` with the Sheet open
  (shared state); the English "Manual" label (the manual is English-only).

## Carried forward
- **TD-471:** four Must pages have no sandbox surface yet (Overview, Organisation's gift list, Profile, the mentor
  pages). **TD-472:** the console has no language control at any width (an owner call).
- `admin/scholarship/page.tsx` is at 599 lines: split before adding to it.
- **Next:** M6b (the case page, documents, viewer; adversarial review on every decision door), M7, M8.
