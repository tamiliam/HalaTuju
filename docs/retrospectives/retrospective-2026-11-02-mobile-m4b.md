# Retrospective — Mobile M4b: student bottom tab bar + rule-15 sweep (2026-11-02)

## What was built
- **A student bottom tab bar** (`StudentTabBar.tsx`, mounted only by `AppHeader`): Dashboard, Explore, Saved,
  BrightPath — owner's pick of four (a fifth does not fit Tamil at 360). Profile stays the header avatar; the header
  menu keeps every destination. No new strings. Eager (it is the way around); all behaviour in CSS via `:has()`: phones
  only, hidden while typing, page padded, toast lifted (`--bottom-bar`), and **swapped out** whenever a page bar marked
  `data-page-bar` is showing (course Save, saved compare, apply Back/Continue, award Sign, next-steps). Browsers without
  `:has()` get no bar; the header menu still works.
- **Paid for, not budgeted:** a real build put the bar at +0.47–0.71 kB per student route (over budget on
  `/scholarship/application`). `BrandLogo` moved off `next/image` to a plain `<img>` requesting the same optimiser URLs,
  removing ~4.5 kB from every student route. Lines were then LOWERED: median 148 → 147, `/profile` 198 → 194,
  `/scholarship/application` 211 → 208.
- **Rule-15 sweep** (16 px gutter, one box level on phones): Dashboard, Search, course and STPM pages, Profile, Saved,
  Settings. My Bursary moved to M4c (another session's Surveys work was not yet on main).
- **Guards and checks:** every bottom bar on a student page must carry the marker (static guard, any `bottom-*`, any
  tag); the bar may only be mounted by the header; rule 15 widened to the swept files; mobile-check fails on two bars
  drawn together (marked or not) and on content hidden under the bar at the page end.

## Numbers (measured)
- Jest 6,079 → 6,098. mobile-check 330 → 360 cells, all passing, none worse; the new bar rules pass everywhere.
- Bundle: median 147.718 → 145.34; `/` 148.06 → 143.63; `/dashboard` 166.99 → 162.47; `/search` 160.09 → 155.56;
  `/profile` 196.22 → 192.66; `/scholarship/application` 210.47 → 206.05.
- Deploys: 1.

## What went well
- **Measuring the bar for real before the sweep** caught that the estimate was low; paying for it by removing an
  unused dependency left every student page lighter than before the sprint.
- **The new mobile-check surfaces found four real phone bugs** in the swept pages before the review did.

## What went wrong
- **`md:divide-y-0` silently removed desktop borders.** Phone dividers written as `divide-y … md:divide-y-0` beat the
  boxes' own `md:border` (Tailwind's divide selector is stronger), so from `md` up later boxes lost their lines. *Why:*
  "undo at md" was assumed to restore the desktop, but a divide utility styles the CHILDREN, not the element. *Prevention:*
  phone-only dividers are written `max-md:divide-y`; a guard bans `md:divide-y-0` in the swept files. Lesson added.
- **The first "one bar at a time" check could not see an unmarked bar** — it counted only marked bars. *Why:* the check
  trusted the marker it was meant to police. *Prevention:* it now counts any sticky/fixed element resting on the bottom
  of the screen; bitten by removing a marker.
- **A cross-session push order was crossed twice** (both sessions yielded and claimed at once). *Prevention:* state the
  final order in one explicit message and wait for the other side's acknowledgement before pushing.

## Close review
- **Code review (before the push):** no blockers. Fixed in 6de6113d: desktop borders (above); "Show all institutions"
  inside the divided list; unmarked bars invisible to the runtime check (above); a focused `select` hiding the bar on
  Android; dashboard banner flush under the header; `BrandLogo` for `data:`/`blob:`/SVG and `fetchpriority`; tab
  prefetching; toast gap on home-bar iPhones; desktop spacing drift. Accepted: the bar is announced as "Menu" (no core
  key to reuse without a new string).
- **Bite checks:** every new guard and runtime rule went red on its injected fault.

## Carried forward
- **M4c:** My Bursary (now that Surveys is landing), Home, scholarship landing, report, About/Contact/legal/Get started,
  pathway pages, onboarding, quizzes — the M4b pattern, no new design.
- TD-464 (36 px shared Language/Theme selects; mobile-check names a fixed bar's child as the widest element).
