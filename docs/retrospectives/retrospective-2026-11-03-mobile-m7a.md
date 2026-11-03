# Retrospective — Mobile M7a: admin "Can" screens on phones, decided doors read-only (2026-11-03)

## What was built
- **Phase 1 (owner, TD-480 item 4):** the maintenance status buttons (On track, Probation, On hold, Ready to close) are
  read-only on a phone — on the scholar file and on the cockpit's no-file control — with a "use a computer" note.
- **Owner answers:** split M7a / M7b; a desktop-only page is REPLACED by a panel on a phone (M7b); more than four tabs
  become one chooser; Close file, Delete student and a sponsor's gift membership are read-only on a phone like money.
- **Shared tabs:** 44 px chips up to four tabs, one chooser above that (`usePhoneWidth`, below `md` by width).
- **Tables as rows by CSS, never a second copy:** `TableFrame phoneRows` + `data-label` cells (or a `data-phone-rows`
  wrapper), so no door is rendered twice; ARIA roles stamped so a screen reader still reads a table.
- **Rule 15** on the scholar file, student detail, payment run and request detail.
- **Every decided door read-only on a phone** (moved into M7a by its review): payment run sign-offs, Cancel run, the
  phone include toggle, New payment run, billable hours, Close file, Delete student, gift membership Accept / Take back.
  Desktop, handlers, requests and confirms unchanged; guarded door by door.

## Numbers (measured)
- Jest 6,325 → 6,353 (409 suites). mobile-check 606 cells; 54 new `m7-*` cells at 0, none worse.
- Bundle: no line raised; median 143.978 (1.0 kB room). The admin-only classes moved out of the student-shipped file
  (`lib/phoneConsole.ts`) after the first build showed them on every student route (−0.13 kB each).
- Deploys: 1 (web only; build fb8e6c43).

## What went well
- **The review caught an order-of-shipping risk, not a code bug:** M7a made the money doors BIGGER on a phone while
  M7b would hide them later. Moving the owner's rule into M7a closed the window before it opened.
- **Cross-session sequencing worked:** Maintenance chose option (a) for the membership door in a file its T5d owns;
  the wrapper is 2 buttons, the file stayed at 600 lines, and nothing else in it changed (verified by the re-review).

## What went wrong
- **A branch switch and a builder's edits landed while the lead's live mobile-check was running in the same worktree**,
  failing 6 cells for no product reason. *Why:* one worktree served two jobs. *Prevention:* the lead runs live checks
  and writes close docs in a SEPARATE worktree (done for this close: `.worktrees/m7a-close`).
- **The build-wait loop matched older builds** (the SHORT_SHA filter returned other triggers' rows) and reported
  "done" while M7a was still building. *Why:* a list filter trusted without checking the row. *Prevention:* wait on
  the build's own ID, then confirm the serving revision changed.
- **A hidden button is not a hidden form:** the hours form, once open at desktop width, kept a usable Save after the
  window narrowed. *Prevention:* a read-only-on-a-phone door hides what OPENS it and closes what is already open.

## Close review
- **Adversarial review, two rounds:** no blockers. Fixed: doors read-only in M7a; table ARIA roles; wider guards;
  old-Safari listener; the open hours form (881e5465). Accepted: the payments note shows to any viewer; no sr-only
  "Included" on phone cards; no `aria-colspan` on single empty cells; the `td:empty` blank line; the divider colour.

## Carried forward
- **M7b:** the `DesktopOnly` panel (owner: replaces the page) on billing-rates, billing, course-data, contracts,
  contracts/[id], sponsors/terms/[id]; Team / Invitations / Mentors tables if they fit.
- `IntakeYearTab.tsx` (oversize, 3 small targets) needs a split before its sweep.
- Sequenced with Maintenance (T5): PermissionEditor, the person page, GiftProgrammes, Sponsors credits, Overview.
