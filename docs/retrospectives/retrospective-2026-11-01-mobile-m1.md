# Retrospective — Mobile M1: global foundations and the shared Sheet (2026-11-01)

## What was built
- **M0 tooling review fixes** (8d667133): the class reader resolves aliased imports and template holes, `//` in JSX
  text is not a comment, phone-applying small sizes and `calc(100vh …)` are seen, API 4xx/5xx refuse a cell, and the
  dev server is never silently reused.
- **M1a — global foundations** (225671b1, 22eb88cc, 9b3f3778): Tamil in Mukta Malar (the SJKT Connect files,
  Tamil-only unicode-range, first in every stack); text fields 16 px on phones by ONE rule at the end of
  `globals.css`; favicon 5.7 MB → 5.9 KB; safe-area padding on every fixed/sticky bar; InfoTip opens on a tap, is
  clamped and has a 44 px target (its bubble lazy-loaded to stay in budget); Toggle 44 px; Toast phone width; Menu
  and FilterPill clamp to the screen; file inputs `sr-only`; keyboard and autofill attributes; TD-311 closed (Home
  hero steps down on phones in all languages).
- **M1b — the shared Sheet** (fb710d8f, bb3d2722, 506df8d1, a59da58b): `src/components/Sheet.tsx` — bottom sheet on
  phones, centred dialog from `md`, focus trap and return, Escape/backdrop/×, `dismissible={false}`, `busy`, scroll
  lock that survives stacking, keyboard lift via `visualViewport`. The owner approved its look from phone
  screenshots of the sandbox before anything moved. 15 overlays moved onto it; DocViewer, the admin phone drawer and
  CommandPalette stay full-screen panels, exempt by name with a reason. The overlay floor became a positive guard.
- **mobile-check for busy machines:** every page warmed once, serially, before measuring; all waits poll on a timer;
  every step names itself when it times out.

## Numbers (measured)
- Jest 5,616 (M0) → 5,882 at the push; api 11,322 passed / 3 skipped (`pytest -n auto`, the gate's command line).
- mobile-check: 229 passed on the branch (5.0 min) and against the live site after the deploy (8.2 min).
- Phone cells: sideways scroll 30 → 22 (all staff screens, later sprints); small text fields 120 → 0; small tap
  targets 1,779 → 1,639; cells clean on all three measures 18 → 42.
- Static floors: hidden file inputs 6 → 0; icon-only `title=` 7 → 0; `fixed inset-0` 18 → 0 (3 named panels);
  vh heights 3 → 1. Bundle: median 147.069 → 147.52 kB (0.5 kB under 148); `/scholarship/application` 211.77 of 212.
- Deploys: 2 (M1 at 3ba3be3d → web-01049-tds; the close-review fixes).

## What went well
- **Approving the look from real build screenshots** (owner's choice) cost one round and no rework: the Sheet was
  migrated once.
- **The adversarial review found a real money/identity-adjacent bug the tests could not see**: the profile phone's
  new `autoComplete="tel"` filled "+60 …", which the page rejected and which cut a digit off an 011 number before an
  SMS code was sent to it. Fixed and guarded (rule 10) before the push.
- **Bite checks on every new guard and fix**: each new test was shown to fail on the old code, restored by checksum.

## What went wrong
- **A keyboard hint made the sign-in gate worse on phones.** The Sheet focuses the first field by default; in the
  gate that is the phone box, but phone sign-in is switched off, and the raised keyboard pushed the Google button —
  the only working way in — out of view. *Why:* a shared component's default (focus the first field) was applied
  to a screen whose first field is not the main action. *Prevention:* the gate now passes `initialFocus` and
  `AuthGateModal.focus.test.tsx` pins it; mobile-standard rule 5 says a Sheet whose first field is not its main
  action passes `initialFocus`.
- **The 16 px rule missed iPhones held sideways.** Most iPhones in landscape are 844–932 px, past `md`, so the
  rule's `max-width: 767.98px` let them zoom again. *Why:* the harness measures only 360/390 portrait, and "phone"
  was modelled as a width. *Prevention:* the rule also applies on `(pointer: coarse)`; the guard reads that media
  query. Landscape remains unmeasured by mobile-check (accepted; roadmap M8 walkthrough covers it).
- **`dvh` with no fallback** left the Sheet without any height limit on browsers that lack it (Safari < 15.4,
  Chrome < 108) — the old modal's `90vh` worked everywhere. *Why:* "use dvh, never vh" was applied as an absolute,
  without asking what an unknown unit does to the whole declaration. *Prevention:* the cap is computed in pixels
  from `visualViewport`; `Sheet.test.tsx` pins "pixels, no dvh".
- **Another session's typecheck broke on our new devDependency** (`@playwright/test`, M0): its node_modules junction
  predated it. *Why:* a new devDependency was pushed without telling the sessions that share the repo.
  *Prevention:* lesson added — announce new dependencies in the push message to other sessions, with `npm ci`.
- **One mobile-check run measured `/login` mid-redirect** and would have lowered its baseline to 0 targets. *Why:*
  "page ready" did not include "the URL has stopped changing". *Prevention:* the check waits for a redirect to land
  (22eb88cc). Still open: it does not compare the landed URL with the target (TD-450).

## Close review (sprint-close 4b)
- **Adversarial review** (sign-in, consent, award acceptance, identity, money; before the push): no blockers.
  Fixed in e0e0b7dd: gate focus (above); profile phone autofill `tel-national` (above); source-invite phone
  autofilled the admin's OWN number → `off`; payment-run sheet lost IBM Plex (portalled out of its `font-plex`
  wrapper → `Sheet` `className`); merchant flag sheet closable mid-request → `busy`; upload labels had no focus ring.
  Accepted as intended: sign-in and payments no longer close on a backdrop tap (a footer button does the same);
  VerifiedTick's 44 px area overlaps the last ~11 px of the value before it (never another control).
- **Code review** (everything else; after the push): no blockers. Fixed in bd872cd9: the 16 px rule on sideways
  iPhones; the Sheet's height cap without `dvh`; InfoTip closing on a tap on its own bubble in Chrome; Toast landscape
  insets. Accepted and recorded as **TD-450**: Escape reaches every open layer (no stacking today); admin drawer's
  `aria-modal` without a focus hold; Sheet title under the notch in landscape; mobile-check does not compare landed
  URL or orphaned baseline cells; rule 10 / overlay exemption / 16 px guard read text, not structure; `:is()` on very
  old browsers. The comment that overstated the rule's specificity was corrected.
- **Bite checks:** rule 10 and the gate-focus test fail on the old code; reverting each close-review fix turns its
  test red (3 of 3); the M1b overlay guard and Sheet behaviour tests were bitten by the builder (5 broken versions,
  all red). Restores verified by checksum.

## Carried forward
- M2 (student shell + onboarding), Stitch first for the header.
- `/scholarship/application` and the median have ≤ 0.5 kB of first-load room: lazy-load before adding weight.
- TD-450 (above).
