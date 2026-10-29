# Retrospective — Student maintenance Sprint 4a: results review and standing (2026-10-29)

Roadmap: `docs/plans/2026-10-29-student-maintenance-roadmap.md` (Sprint 4, first half). Shipped as `3d38f1f8`
(feature) and `10072c71` (adversarial review fixes plus the owner's slip ruling); live as api-01190-6cb plus web.
Migration `scholarship/0186_semester_result_review` was applied by hand, migrate-first.

## What Was Built

- **Recording results on the file predicate.** Every funded student (awarded and activated too) records a result
  with her slip: sign, PUT, then record. `results_review.record_slip` records the slip outside the pre-award
  document pipeline. "Graduated" is now the site Toggle, and the hub no longer judges a CGPA in the browser.
- **Review.** `SemesterResult` gained `review_status` (pending / accepted / queried), `reviewed_by`, `reviewed_at`,
  `review_note` and `term_index`. The admin **Results** tab on the scholar file shows each result with its slip in
  the DocViewer, and the officer can Accept, or Query with a note the student sees. Activity logs
  `result_submitted` and `result_reviewed`.
- **Standing.** `standing.py` gives performing / underperforming / failing / awaiting review / no result yet, from
  the latest ACCEPTED result only, measured against the organisation's new `maintenance` settings (minimum CGPA
  3.00 and failing CGPA 2.00, in a decimal unit, with a rule that failing stays below minimum).
  - The Scholars list has the standing chip and a server-side Underperforming filter and tile.
  - The settings page warns when a contract's wording states another CGPA.
- **Sponsors read accepted results only.** That covers the progress band (now on the predicate), the portfolio
  count, the feed and the impact figures. Its `needs_attention` is the staff `failing` line. A cross-reader test
  pins this, and so does a per-function doors fence.
- **Owner ruling (2026-10-29): "Students must upload at the portal. Emailed docs are not allowed."**
  - A result needs its uploaded slip.
  - A result with no slip cannot be accepted (Query asks her for it).
  - Staff cannot attach a slip for her.

## What Went Well

- The doors were listed before the code changed, every writer and every reader of `semester_results`. The review
  then hardened that list into a per-function AST fence, so a new reader cannot slip in unnoticed.
- The query budget held at 8 on the Scholars list: the summary became ONE aggregate, and each organisation's minimum
  is read in one query (`org_config.custom_values`).
- The owner's ruling arrived mid-fix and fitted into the same commit. The server is the gate, so the page only
  mirrors it.

## What Went Wrong

1. **HIGH: after acceptance, a student could still delete her slip** (adversarial review H1). The slip was a new
   kind of document, EVIDENCE, but it was stored in the same table as her application documents. The general
   document doors (list, delete, replace, the self-heal re-read sweeps) all served it as an ordinary upload.
   **Root cause:** the new document type was checked against the pipeline it should skip (OCR, Check-2), not
   against every door a student already has onto `applicant_documents`. **System change:**
   - `results_review.slip_locked` makes delete answer 409 `slip_locked`.
   - The list leaves `request_code='in_programme'` out, and the upload refuses that slot, so a slip cannot be
     superseded.
   - Both self-heal sweeps exclude slips. Each door has a test that would catch a regression.
   - Lesson recorded: a new evidence document type is checked against every existing student document door.
2. **M1: settings that nothing read were registered.** The 4b timing keys were registered "for later" and drawn on
   the settings tab. **Root cause:** registry entries were treated as cheap scaffolding, but each one is a promise
   to the person configuring it. **System change:** the keys were removed, and a test pins the maintenance group to
   the two keys that have readers. 4b registers its keys together with their readers.
3. **M2: two lines for one judgement.** The sponsor band kept its own fixed `<= 2.0` while staff standing used the
   organisation's settings, so a CGPA of exactly 2.00 meant two different things. **Root cause:** an old reader was
   moved onto accepted results, but its threshold was never questioned. **System change:** `standing.is_failing` is
   the one comparison (strictly below), with a test at 1.99, 2.00 and a custom 2.50 covering both readers.
4. **M3/M4: the fence was per FILE and "latest" could tie.** A file-level grep let any function in a listed file
   read the table unfiltered, and `derive_progress_state` ordered by `-created_at` alone. **System change:** judging
   readers go through `results_review.accepted`, the fence works per function across all of `apps/` (management
   commands included), and `-id` breaks ties.
5. **L1–L5** (the slip path shape, whole-number settings accepting floats, no daily cap on results, a contract check
   that read bare numbers and missed the clauses): all fixed with tests.
6. **Over the file budget.** The feature commit touched 51 files against the ~40 guide. About half were test updates
   forced by the accepted-only rule. Flagged at the hand-off, not split.

## Design Decisions

- The slip is recorded by `record_slip` (`request_code='in_programme'`), never by the pre-award pipeline.
- Only an accepted result counts, for staff and for sponsors alike. A sponsor sees a result only after an officer
  reviews it.
- The browser judges nothing. Standing and the Underperforming filter are computed on the server.
- "Latest" means latest submitted until 4b stamps `term_index`.
- **Owner ruling:** portal upload only (decisions.md, 2026-10-29). Pre-S4a typed-only results cannot be accepted;
  they can only be queried.

## Numbers

- Lead, after rebase on `616bc34a`: **10,243 pytest** (full api suite); web **4,931 jest / 317 suites**;
  `next build` OK; bundle budget OK.
- Adversarial review: SHIP-WITH-FIXES, 1 HIGH (H1) and M1–M4, all fixed with L1–L5. L4/L6 were replaced by the
  owner's ruling.
- Two commits (51 + 37 files). One migration (0186), applied by hand.
