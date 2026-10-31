# Retrospective — Offer realignment (2026-10-31 → 2026-11-01)

Live: main `f908d5ba`, api-01223-8xk (no migration, no web build). Repair applied on live 2026-11-01 (owner yes).

## What Was Built

- **The offer matcher sees the degree catalogue.** `apps/scholarship/offer_course_match.py` (new) searches
  `StpmCourse` beside `CourseInstitution`, reads a printed course code only when its catalogue name agrees with the
  printed programme, strips UiTM's local code, a faculty tail, the catalogue " #" and campus parenthetical, and
  returns one course or none. Institutions are named in tiers: exact name or a unique acronym first, then the
  letterhead (issuer), then words, where the institution's own words (two or more, not only place words) must sit
  inside the line. A campus is returned only when the letter names exactly one.
- **The issuer stands in for a hostel line** (`letter_place`), shared by `sync_institution_from_catalogue`,
  `institution_agreement`, `offer_contradicts_course_institution` and the offer confirm.
- **Owner rule: a genuine, own offer for a Bumiputera-only course replaces a student-made pick** on an undecided
  case (`plan_bumi_realign` / `realign_bumi_only_pick`), sets the pathway the course belongs to, and refreshes the
  following profile. Reads the COURSE's flag only; one guard exception by path (owner option A).
- **`realign_bumi_offers`** (report by default, `--apply`): 13 picks realigned, 3 hostel institutions filled.

## What Went Well

- The owner's question ("build the course corpus first?") was checked against live data before answering: the
  catalogue already held the courses, and the real gap was the matcher never reading the degree table. That turned
  a data project into a code fix.
- A pre-deploy dry run on live strings (read-only) gave exact before/after numbers for every record: 46 → 153 offers
  resolve, 7 real new clashes, 13 realign candidates. The numbers did not move between the dry run and the live
  report.
- Two adversarial review rounds caught every wrong-course path before the push.

## What Went Wrong

1. **The first build would have written wrong UiTM/MARA courses onto students.** Symptom: the round-1 review found
   that "UNIVERSITI TEKNOLOGI MARA" named MARA's division (acronym MARA), that a UTM letter matched a UiTM degree
   (shared word "teknologi"), and that a multi-campus match returned whichever campus the loop saw last. Root
   cause: the matcher widened the SEARCH (1,112 more courses) but kept the old, loose idea of "this line names that
   institution" (shared words, either direction), which had been safe only while the search space was small. The
   live dry run could not show it, because no live letter happened to hit those rows. Fix: tiered naming (exact
   name / unique acronym before words; institution ⊆ line, never line ⊆ institution), and a lesson (below) that a
   widened matcher is reviewed against COUNTERFACTUAL catalogue rows, not only today's data.
2. **A Pause arrived after the apply had already run.** Symptom: the owner said "Pause" while `--apply` was
   running under `--wait`; it finished before the message was read. Root cause: a live write was started as one
   blocking call with no point at which a pause could land. Nothing went wrong (the owner then said continue), but
   an undo plan was offered only after the fact. Fix: before any live `--apply`, state the undo path in the same
   message that asks for the yes (here: the AUDIT log carries every old course id).

## Design Decisions

- One guard exception by path (owner option A) rather than keeping the Bumi-blind guard and fixing records by hand;
  `is_bumiputera_only` is pinned to one reader and one caller (decisions.md 2026-10-31).
- `interviewing` with no submitted interview session is still realigned (owner): the letter is a fact, and the
  officer sees the right course.
- A realign the matcher cannot pin to one campus is skipped (`campus_unpinned`), never guessed.
- No MODEL_VERSION bump: nothing about reading or genuineness changed.

## Code review / bite checks (sprint-close 4b)

The two adversarial rounds stand in for `/code-review`; every finding was fixed (round 1: 3 blockers + 6
should-fix/nits; round 2: 2 should-fix) or logged: TD-447 (stale-id confirm can keep a hostel), TD-448 (a late
genuineness score waits for a re-read), TD-449 (offer-check queries outside the budget). Each fix was bite-checked
by disabling it alone and watching its own test fail; restores verified by checksum.

## Numbers

- pytest (gate command `pytest -n auto`): 11,071 passed / 3 skipped before → 11,277 passed / 3 skipped after
  (includes other sessions' work rebased in; this sprint added 2 test files and ~130 tests).
- jest: 5,816 passed / 354 suites; `tsc --noEmit` clean (no web change this sprint; run per sprint-close 1a).
- Live dry run: 251 live offers; resolutions 46 → 153; realign 13; institution fills 4 (one filled itself before
  the apply).
- Live apply: 13 realigned, 3 filled, 0 errors.
