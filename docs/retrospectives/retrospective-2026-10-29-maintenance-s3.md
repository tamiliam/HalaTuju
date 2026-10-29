# Retrospective — Student maintenance Sprint 3: "My Bursary" and the controls move to the file (2026-10-29)

Roadmap: `docs/plans/2026-10-29-student-maintenance-roadmap.md` (Sprint 3). Design of record: the owner-approved phone
artboard (2026-10-29). Shipped as `1f78c76a` (feature) and `c007883e` (adversarial review fixes); live as api-01186-wgq
+ web (`/scholarship/in-programme` answers 307 → `/scholarship/bursary`, confirmed). No migration.

## What Was Built

- **`/scholarship/bursary` "My Bursary"** — the in-programme page moved in; a greeting, her gift (in her language)
  and course, one line of state; **Overview** (funds received of the award, a progress bar, the last payment; her
  latest result; the 18+ sharing toggle; the thank-you) and **Results** (the form only when the server allows).
  Later tabs hidden until their sprints. A non-404 failure offers a retry.
- **`GET scholarship/bursary/summary/`** — her own file only (404 `no_file`), money from the ledger with the funding
  summary's "remaining", `support_paused` the only maintenance signal.
- **"My Bursary" in the BrightPath menu** from a `localStorage` hint the pages that already read her applications
  leave (cleared on any sign-out; the header updates live), and a link-only card on `/scholarship/application`
  (route budget unchanged at 211 kB).
- **Admin** — the sub-state control and the post-award Close moved from the cockpit into the scholar file
  (`ScholarControls`, from a server `controls` offer): hold only with payments rights, the closure note and
  offboarding checklist before the confirm, and a plain "cannot be closed here" for an awarded case still holding
  the sponsor's offer (TD-366, S1 review L4). TD-419 resolved. The cockpit keeps a read-only status, the pre-award
  Close, the link — and, after review, the status control for a payable student who has no file.

## What Went Well

- The student payload was designed as an allow-list from the start, and a test greps it for every staff word
  (`probation`, an officer's email, a note, `maintenance_substate`, `nric`), so "nothing staff-side" is pinned.
- Moving rather than copying the in-programme page (`git mv`) kept its history and its tests, and the two
  path-reading guards (`theme.test.ts`, `sliceReach.test.ts`) named the move at once.
- The owner's open question was surfaced at the hand-off, not discovered after deploy: the hub shows the student her
  award, received and remaining — the owner ruled yes.

## What Went Wrong

1. **A payable student with no file became unholdable** (adversarial review, M1). Moving the control to the file left
   the awarded student with an eWallet ID but no activation stamp — paid by the runs, outside the file predicate —
   with no screen that could hold her. **Root cause:** "move the control to the file" was checked against who HAS a
   file, not against who the control serves; Sprint 1 had already widened `can_set_substate` beyond the file predicate
   precisely for this student, and the move undid that silently. **System change:** the cockpit payload serves
   `maintenance_controls` and draws the control only for a no-file case; tested from both sides. Review prompt kept
   for the roadmap: when a control moves, list the population each place served before and after.
2. **The close checklist was dropped in the move** (adversarial review, M2). The cockpit's funded-close note and
   offboarding checklist did not travel with the Close button. **Root cause:** the move copied the control, not the
   guidance around it. **System change:** the note and checklist precede the confirm in `ScholarControls`, with a
   test that asserts them before the confirm appears.
3. **Smaller review findings, all fixed:** the hint survived some sign-out paths; a server error read as "not in the
   programme"; the gift was English-only; "reached your wallet" wording; the header waited for a navigation. Shared
   root cause: the edges of a new client-held hint and a new student page were not walked once end to end.
4. **Process:** the lead's first push was rejected because another session pushed in the gap after the lane was
   declared. Already covered by `lessons.md` (re-fetch immediately before the push, Spending S6) and the memory rule
   that a push is a request whose result must be read — no new lesson; the habit held because the result was read
   before anything was announced.

## Design Decisions

- Two tabs for the student, later ones hidden (decisions.md, 2026-10-29); the admin file draws its future tabs
  disabled because staff need to know they are coming, a student does not.
- The header link is a client hint, not a fetch from the shared header (one request on ~90 routes for one link);
  the hub's endpoint is the gate.
- **Owner ruling (2026-10-29):** students see their award, what they have received and what remains.
- Left for Sprint 4: the results "graduated" tick box becomes the site Toggle (roadmap Sprint 4 row).

## Numbers

- Full api suite **10,112 pytest**; web **4,892 jest / 314 suites** (lead, after rebase on Bumi D1); `next build` OK;
  bundle budget OK (median 146.4 of 148 kB; `/scholarship/bursary` 189 kB, `/scholarship/application` 211 kB).
- Adversarial review: SHIP-WITH-FIXES, 0 HIGH, 2 MED (fixed), L1–L8 fixed or noted.
- Two commits (35 + 24 files).
