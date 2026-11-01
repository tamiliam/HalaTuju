# Retrospective — Mobile M2: one student header, onboarding that fits (2026-11-01)

## What was built
- **One student header on every student page, Home included** (`AppHeader.tsx`). Phones: logo, one button
  (signed out: Log in — the student gate, or the sponsor login on `/sponsor*`; signed in: the avatar) and a 44 px
  menu button. Home's own three-row bar (raw theme and language dropdowns) is gone.
- **The phone menu is the shared `Sheet`**: each destination once (Saved / "My Applications" were two links to
  `/saved`; Profile appeared twice), 44 px rows, its own scroll, theme and language inside, Log out pinned. Desktop
  keeps its row; BrightPath opens on a click (no iPad sticky-hover dependency); theme and language sit in the avatar
  dropdown, or a "Language" button when signed out.
- **Weight:** the menus, the desktop row, the nav lists and the theme/language controls load lazily
  (`StudentMenus.tsx`, an owned `import()`), with an eager fallback (Log in / Log out) if that chunk cannot load.
- **Onboarding:** one `FlowHeader` replaces five copies; `ProgressStepper` stacks its words over the bars so the
  logo never shrinks (Malay "Langkah 2 daripada 3" squashed it to 44 px at 360); STPM rows restack (`StpmSubjectRow`);
  remove/clear buttons, grade pickers, MUET bands and quiz links 44 px; stream buttons stack icon over label.
- **Student sign-out is one eager helper** (`src/lib/studentSignOut.ts`) that also forgets the session on the device
  when the server cannot be reached.
- Sandbox surfaces (synthetic `AuthContext`, never a real sign-in): header signed out / menu, signed in menu (with and
  without a bursary file), onboarding stepper, STPM rows.

## Numbers (measured)
- Jest 5,896 → 5,919 (365 → 367 suites). mobile-check 229 → 265 cells, all passing; 84 existing cells better; the 36
  new cells all 0/0/0.
- Bundle: every page with the student header 1.3–2.3 kB lighter; `/scholarship/application` 211.823 → 210.050
  (budget 212 → 211), `/profile` 198.416 → 196.088 (199 → 198); `/scholarship/apply` 186.269 → 186.291; median
  147.530 → 147.556 (0.44 under 148); `/` 146.855 → 147.843 (unbudgeted; it gained the shared header).
- Deploys: 1.

## What went well
- **Stitch first paid for itself:** the audit found the real onboarding problem was Malay, not Tamil, and that two
  buttons cannot fit a Tamil/Malay phone bar at 360 — both settled by the owner from drafts before any code.
- **The adversarial review found a shared-phone identity leak older than this sprint**, exactly where it was asked to
  look: a failed `signOut()` (network or 5xx) returned `{ error }`, auth-js kept the stored session, the page reloaded
  as if signed out, and the next person on the phone was signed in as her. Fixed before the push.

## What went wrong
- **A lazy split created a new way for the header to be empty.** On desktop a failed menus chunk left only the logo —
  no nav, no Log in, no Log out — and on phones a dead button. *Why:* the split was designed for weight, and the
  "what if the import rejects" path was not on the plan. *Prevention:* an eager fallback (Log in / Log out) and
  retry, pinned by `AppHeader.fallback.test.tsx`; lesson added — every owned `import()` that carries a way in or out
  needs an eager fallback.
- **Sign-out trusted a call that reports failure by return value.** `signOutStudent` ignored `{ error }`. *Why:*
  auth-js returns, rather than throws, on a failed sign-out, and the old header code (copied forward) never checked.
  *Prevention:* `studentSignOut.ts` checks the error and removes the student session keys itself (named from the
  client's own `defaultStorageKey`); `studentSignOut.test.ts` covers refused, thrown, successful and written-mid-flight.
- **First build put the desktop row in the eager bar** and pushed the median over 148 (+2 kB on Home). *Why:* the
  weight was measured after the build, not planned per route. *Prevention:* none new — `npm run bundle-budget` caught
  it before commit, which is the existing rail working.

## Close review
- **Adversarial + code review (before the push):** no blockers. Fixed in 7fd9410b: chunk-failure fallback; failed
  sign-out forgets the session; desktop 4 px jump (the row's height is reserved). Accepted: signed-out "My Profile"
  removed (Log in → Student opens the same gate); About only in the footer; a Google-signed-in student without a
  verified NRIC sees the signed-out header (pre-existing, **TD-454**). `hoverOnlyWhenSupported`: its named blocker
  is gone; adoption waits for a sweep (**TD-453**).
- **Bite checks:** 12 faults injected into the M2 build and 11 into the review fixes; every one turned a test red;
  restores verified by checksum.

## Carried forward
- M3 (student discovery: search filters in a sheet, course page scroll trap, saved compare on phones), Stitch first.
- Unmeasured: the phone bar with the fallback Log out at 360 in Tamil/Malay (~321–326 of 328 px, estimated).
- Tablets (`md`–`lg`) show the menu as a centred dialog, not a bottom sheet — acceptable, noted.
