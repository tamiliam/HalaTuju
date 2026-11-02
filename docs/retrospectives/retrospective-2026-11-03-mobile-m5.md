# Retrospective — Mobile M5: the sponsor portal on phones (2026-11-03)

## What was built
- **A sponsor tab bar** (`SponsorTabBar.tsx`, mounted only by `SponsorShell`): My Giving · Students · My Account on
  phones, reusing the student bar's CSS (`data-tab-bar="sponsor"`). Before M5 the portal's only navigation was a top row
  needing 536 px in English and 688 px in Tamil, so every signed-in sponsor page scrolled sideways on a phone.
- **A slim phone header**; theme, language and Log out at the end of My Account (owner). The portal had no language
  control on a phone before.
- **Funding:** a sticky fund bar plus ONE confirm Sheet that cannot be swiped or Escaped away, locked while sending,
  one request per burst of taps. The desktop "Fully fund" now opens the same Sheet (owner, 2026-11-03: one money path).
- **Rule 15 and 12 px** across the portal, sign-in screens and landing; filters in a Sheet; the terms wizard full width
  with a sticky quiz bar; a stepped journey line instead of 9 px words.

## Numbers (measured)
- Jest 6,144 → 6,163 (396 suites). mobile-check: 24 sponsor cells better, eight new surfaces at 0, none worse.
- Bundle: median 145.182 → 145.218 kB; `/sponsor/students` and `/sponsor/students/[id]` +3.3 kB each (the Sheet, eager
  on purpose). No line raised. `/scholarship/apply` was left with 0.19 kB of room (TD-470).
- Deploys: 1 (web only; build a5559432).

## What went well
- **The adversarial review found a shared-phone gap the build did not:** on browsers without `:has()` the sponsor had
  no navigation and no Log out. Fixed before the push.
- **The builder bite-checked every guard** (19 mutations in all); one test that passed with the lock removed was
  rewritten until it failed.

## What went wrong
- **A copied fallback did not fit its new home.** The student bar's "no `:has()`, no bar" rule is safe for students
  (their header menu remains) but left a sponsor with the logo alone. *Why:* the component was copied without asking
  what else its users have when it is gone. *Prevention:* lesson added; a guard pins the sponsor fallback.
- **A sticky "Start the quiz" let a sponsor skip the terms.** *Why:* reach was put before reading on a consent page.
  *Prevention:* Start is inline after the terms; guards check it is not pinned and comes after the privacy line.
- **The apply route's room was spent without anyone noticing.** The gate passed, so only the Maintenance session's own
  measurement showed it fell under the 0.25 kB near-line rule. *Why:* M5 checked the sponsor routes and the median,
  not the student routes that share the menus chunk. *Prevention:* TD-470; when a sprint touches a shared component,
  read the near-line list for every route, not only the routes in scope.

## Close review
- **Adversarial review (before the push):** no blockers; one should-fix (old-phone navigation) and four minor items
  (Start pinned, Sheet font, a stale student on an address change, the registration stash surviving Log out). All
  fixed in 93afa27c with guards and tests.

## Carried forward
- **TD-469:** the desktop sponsor has no language control; admin-side sponsor labels at 10–11 px (M7).
- **TD-470:** take weight off `/scholarship/apply` before anything adds to it.
- **Next:** M6 admin shell and reviewer cockpit (may split), M7, M8.
