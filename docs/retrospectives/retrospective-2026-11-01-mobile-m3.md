# Retrospective — Mobile M3: student discovery on a phone (2026-11-01)

## What was built
- **Search:** a phone bar (search box, "Filters · N", removable chips, result count, the Eligible switch) replaces the
  258 px filter block; filters open in the shared `Sheet` (`SearchFilterSheet.tsx`: groups of 44 px chips, "Show all",
  sticky Clear / "Show N courses"). Desktop keeps its pill row. 44 px save button on `CourseCard`, translated label.
- **Course pages** (`course/[id]`, `stpm/[id]`): on phones, quick facts and requirements come first; the inner
  `max-h-[600px]` scroll box is gone ("Show all" instead); a sticky `CourseSaveBar` keeps Save on screen; the toast rises
  above it; the 8 px overflow at 375 (`min-w-0`) is fixed. The polytechnic diploma page went from 7,756 to 3,849 px.
- **Saved:** compare works on phones (layout B: two columns, each row's label above its two values, "Compare with" when
  three are picked; no "best" marks); 44 px checkboxes with visible labels; pills wrap; the hard-coded Malay compare
  words are translated.
- **Report:** phone width, 44 px print, the header on loading and error states.
- **Footer:** 44 px link targets on every student page (the footer got shorter, 782 → 739 px).
- **Words:** a `discovery` message slice loaded by the pages that read it (not the core every route downloads).
- **mobile-check:** `/stpm/[id]` is now measured (M0 had filed it as signed-in); a `stpm-sains` visit; four sandbox
  surfaces (filter sheet, saved list, saved compare, report) with a synthetic sign-in.

## Numbers (measured)
- Jest 5,919 → 5,981 (367 → 372 suites). mobile-check 264 → 301 cells, all passing; small targets `/search` 27 → 0,
  `/course/[id]` 31 → 0; 90 existing cells better (the footer). Ledger: `/search`, `/course/[id]`, `/stpm/[id]`,
  `/saved`, `/report/[id]` green.
- Bundle: median 147.556 → 147.572 kB after the merge (0.43 under 148); the five M3 pages sit above the median and grew
  on their own pages (`/search` 156.4 → 160.0, `/course/[id]` 185.1 → 186.6); budgeted lines rose by < 0.1 kB, all
  inside. Nothing lazy-loaded (each piece is the only way to do its job on a phone).
- Deploys: 1.

## What went well
- **The audit moved the target.** The plan said "remove the scroll box"; measuring said Save sat at y = 6,813 below 18
  institution cards — the sticky Save bar was the real fix.
- **Approving the search bar from the build** (Stitch failed to return it twice) cost no rework.

## What went wrong
- **Stitch lost two of six generations** (accepted, then never listed). *Why:* the tool's eventual-consistency gap,
  known from the memory notes, but here the screens never surfaced at all. *Prevention:* none in our code; the owner's
  "approve from build screenshots" path is now a standing fallback (used in M1 and M3).
- **Two guards kept reading files the code had left.** Moving the compare words into `SavedCompare.tsx` and the
  pre-U sections into `PreUInstitutions.tsx` left `discoveryLayout.test.ts` scanning only the page and `theme.test.ts`
  pointed only at the new file — a copy put back in the old place would have passed. *Why:* the move re-pointed each
  guard instead of extending it. *Prevention:* both guards now read both files; lesson added.

## Close review
- **Code review (before the push):** no blockers, no should-fix. Fixed in 56173595: the filter sheet's Clear also
  removes a hand-typed `?aliran=` (hidden group, no chip); "Show 1 course"; the two guards above. Accepted: the sandbox
  filter surface's English group titles; a 12 px gap above "Back to recommendations" on phones; "moved verbatim"
  corrected in the guard comments (page size 50 → 20, phone classes).
- **Bite checks:** 18 faults in the build and 3 in the review fixes, each red; restores verified by checksum.

## Carried forward
- M4 (scholarship apply, documents, award) — consent / PII, so the adversarial review is mandatory; owner pick due:
  apply-form draft storage (recommended: tab-only sessionStorage).
- TD-455 (saved-page toasts English only), TD-456 (course-page labels English only; card merit text 9–11 px), TD-457
  (compare sticky row assumes a 68 px header).
- The report renderer has no table support (`remark-gfm`); tables render as plain text.
