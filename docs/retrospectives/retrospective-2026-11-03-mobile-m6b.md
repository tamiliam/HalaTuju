# Retrospective — Mobile M6b: the reviewer's case page on phones (2026-11-03)

## What was built
- **Split first, moves only:** the decision card left `view.tsx` (on the oversize ledger) for `view/DecisionCard.tsx`;
  all 255 lines checked by machine and by the review; the ledger line went 1338 → 1109.
- **The cockpit on a phone:** the 23 cards are sections below `md`; 74 controls get a 44 px hit area; body text 12 px;
  Back on its own line and Previous / Next as two 44 px buttons. Desktop unchanged.
- **The decision bar** (owner): sticky, phones only; the chosen outcome, ready or not, and one button that scrolls to
  the decision section. It sends nothing; Save stays in the card. The card and the bar share ONE rule
  (`decisionBarShows`).
- **Documents and viewer:** the 28rem inner scroll box is desktop-only; below `md` a PDF is a 44 px Open link to the
  phone's own viewer (owner); images stay inline.
- **Payments read-only on a phone** (owner): the tranche actions and the Schedule form hide below `md`, with a "use a
  computer" note.
- **Layout only, proven:** every cockpit file diffed with class strings and comments removed; no onClick, disabled
  rule, request, confirm, order of steps or server check changed.

## Numbers (measured)
- Jest 6,202 → 6,266 on the branch; 6,318 on the merged tree (404 suites). mobile-check 552 cells; 24 new cockpit
  cells at 0; the old case-page cells 227 / 257 px of sideways scroll → 0, 19 small targets → 0.
- Bundle: no line raised; `/scholarship/apply` 1.79 kB of room; the case route 220.4 → 222.6 kB (no line; 250 ceiling).
- Deploys: 1 (web only; build 2a8b33cd).

## What went well
- **The approved answers came before the build.** The owner answered the M6b questions at phase 1, so the build ran
  straight through with no stop for design.
- **The adversarial review read every door against main** and confirmed the move commit had no stale closure, the
  classic break when a component is lifted out.
- **Cross-session order held.** Cockpit, profile (offer-read S6) and Maintenance agreed who owns which file before the
  build; S6 rebases onto M6b.

## What went wrong
- **"Phone" first meant narrow OR touch**, so iPads and touch desktops lost the PDF preview, and the shared
  `DocViewer` carried the change to five other screens nobody had briefed. *Why:* a device test written for one screen
  inside a shared component. *Prevention:* one breakpoint (below `md` by width) decides "phone" across the sprint; a
  test checks the other callers render on desktop as on main. A change to a shared component lists its callers in the
  brief.
- **A TD number was taken twice.** M6b drafted TD-477 after checking main; R1 took TD-477 (and 478, 479) before M6b
  merged. *Why:* checking a free number is a snapshot, and three streams raise debt on one day. *Prevention:*
  re-check the number at the merge, not only at the commit; M6b's leftovers are TD-480.

## Close review
- **Adversarial review (before the push):** no blockers; two should-fix (the touch rule above; one breakpoint for
  payments too) and four minor (the bar said Ready while a save was in flight; a copied show-rule; a test that could
  pass without testing; maintenance status on a phone left as an owner question). All handled in 979baefb.

## Carried forward
- **TD-480:** four cockpit doors still ask with `window.confirm` (move to Sheets, its own reviewed change); the
  referral name is hover-only on a phone; no Previous / Next inside the viewer; **owner question:** should the
  maintenance status buttons (On hold stops a student's money) be read-only on a phone like payments?
- **TD-477 (R1's):** the cockpit adopts the shared list Previous / Next hook now that M6b has landed.
- **Next:** M7 (admin "Can" screens + the desktop-only gate), M8 (close-out, owner iPhone walkthrough).
