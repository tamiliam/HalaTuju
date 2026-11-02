# Retrospective — Mobile M4: scholarship apply, documents and award on a phone (2026-11-02)

## What was built
- **Part 0 — shared-phone privacy fix (1c6ecf40, shipped first on the owner's call):** the apply form stashed the
  whole form (IC, income, parent name and phone, typed signature) in the tab's `sessionStorage`, and sign-out
  reloaded the same tab, so the next student on a shared phone opened the form pre-filled with the last student's
  details. Sign-out and any `SIGNED_OUT` now wipe the tab; the dashboard drops an abandoned stash.
- **Apply form:** a draft in this tab only (owner option 1) — never the IC, the typed signature or the consent
  switch; keyed to the user id that FILLED it, the programme, a version and 24 h; written on change and when the tab
  is hidden; cleared on submit, already-applied, closed programme, sign-out and any `SIGNED_OUT`. One step per
  screen with a sticky Back / Continue; a second submit while sending does nothing; Enter before the last step means
  Next.
- **Documents:** 44 px Replace / Remove; Remove asks in a sheet first and sends one delete; per-card busy; the
  camera-friendly picker. Action Centre refuses an oversize or wrong-type file before uploading (lazy check).
- **Award:** "Read the full agreement" opens the server's agreement in a phone-readable sheet (only a phone
  stylesheet is added; the text and the server-stamped signing are unchanged); the agree ticks and Sign stay off
  until it has been shown; one in-flight lock for accept / sign / decline; Decline asks in a sheet. After a reload a
  passed quiz and a still-valid parent PIN are not asked again (two read-only API fields from the server's own
  records — owner's call), so no second paid SMS.
- **Rule 15 — one box level on phones** (owner, from the Grab app): 16 px gutter; an outer card becomes a full-width
  section; no bordered box inside a box; tighter vertical rhythm. Applied to every M4 screen; the rest of the student
  pages follow in the next sprint with the bottom tab bar.
- mobile-check counts a file picker's `<label>` as a tap target (the 20 px Choose / Replace links were invisible to it).

## Numbers (measured)
- Jest 5,998 → 6,079; api 11,479 (whole suite) / 9,584 scholarship after the last merge, all passing.
- mobile-check 331 cells, all passing; 30 better, none worse.
- Bundle: no line raised; `/scholarship/application` 210.201 → 210.472 (0.528 room after making the Action Centre
  check lazy), median 147.639 → 147.719 (0.281 room).
- Deploys: part 0 = 1; M4 = 2 (the first web build was refused by the gate — see below; the API went live then).

## What went well
- **Two audits found two real privacy leaks before any student did:** the stashed form surviving sign-out (part 0),
  and — in the adversarial review of the draft — an account switch in another tab relabelling student A's typed form
  as student B's. Both fixed and tested before the push.
- **Owner design input mid-sprint** (the Grab comparison) was cheap to absorb because the screens were not yet live.

## What went wrong
- **The deploy gate refused the first M4 web build on a test race.** `ScholarshipDocuments.test.tsx` waited only for
  the headings, not for `listDocuments`; on the slower gate one income-tick assertion ran first. *Why:* the helper
  asserted on async-loaded state after waiting for unrelated sync state, and local runs were too fast to show it.
  *Prevention:* the helper waits for the list; proved by a 150 ms delayed list (old helper: 7 failures; new: 0).
  Lesson added.
- **Stitch returned nothing three sprints running** (M3 partly, M4 entirely). *Why:* the tool, not our use of it.
  *Prevention:* HTML mock-ups in the same style plus build screenshots are now the standing fallback.
- **A history rewrite went wrong in the builder's hands** (rewording a WIP commit rewrote main's commits locally);
  restored from git's backup at once, final tree identical. *Prevention:* never rewrite a branch that contains merges
  of main; amend only the tip, or add a new commit.

## Close review
- **Adversarial review (before the push):** no blockers. Fixed in 8717b111: the account-switch draft relabel (F1);
  the onboarding peek pre-filling school while sign-in loads (F2); agree ticks before the agreement was shown (M1); a
  second answer during navigation (M2); a refused sign's error out of sight (M3). Earlier part-0 review gaps: TD-458.
- **Bite checks:** every new guard and test went red on its injected fault; restores verified by checksum.

## Carried forward
- **Next sprint (owner, 2026-11-02): the student bottom tab bar** (context-aware: a page's own action bar replaces
  it where there is one) **and the rule-15 sweep** of the other student pages — Stitch / mock first.
- TD-458 (back-button cache; grades surviving a session that ends without the button), TD-460 (income wizard writes
  on open, silent failures), TD-461 (shortlist step wizard still has its icon tab bar), TD-462 (bank statement has no
  early file check), TD-463 (the award's payment schedule is served in English).
