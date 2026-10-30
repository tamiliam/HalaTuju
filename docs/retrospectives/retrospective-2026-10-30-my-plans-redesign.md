# Retrospective — Scholarship "My Plans" redesign (offer question, institution first, unfiltered) — 2026-10-30

Live in `53706f21` (api-01212-lr2 / web-01035-m7b), pushed ~17:30 UTC; both builds SUCCESS, no 5xx on the new api
revision. No migration. Commits: `ceb547fc` (offerings endpoint), `c34519cb` (web), `7053e72e` (docs),
`53706f21` (review fixes).

## What Was Built

- **The Plans step asks about an offer:** "Have you received an offer for your next step of study?" — "Yes, I have
  an offer" / "Not yet, I'm waiting". Labels only: `pathway_certainty` stays `sure` / `uncertain`, with the same
  branches, validation, reminders, ~58-day auto-close, verdicts and award rules (owner: we award only on a firm,
  documented offer letter with a reporting date; no fast track, no upload in the form).
- **Institution first, then course.** University and Asasi: University → Course. Polytechnic, community college,
  MARA, ILJTM, ILKBS and other public skills training: State → Campus → Course. STPM and third-route holders:
  University → Degree. PISMP, matriculation and Form 6 keep their two steps.
- **Unfiltered by default.** An "Eligible only" switch (the site `Toggle`, off by default) is the only route to the
  eligibility endpoints on the scholarship side. The course guide is unchanged.
- **`chosen_programme` records the place:** `institution` (catalogue spelling) and `institution_id`.
- **New public endpoint:** `GET /api/v1/courses/offerings/?pathway=`.
- **One picker serves both `/scholarship/apply` and `/profile`.** The apply page went from 1,074 to 732 lines;
  `lib/scholarship.ts` went from 1,092 to 1,005.
- **Documents page:** the never-drawn section notes went, including the one that called the offer letter
  optional.

## What Went Well

- **Design before code.** The owner approved a two-board design canvas, so the build had no UI rework.
- **The catalogue numbers shaped the design:** at most 29 universities per pathway, but 101 to 233 campuses for
  the skills pathways. That is why only the campus-heavy pathways ask for the state first.
- **The pages got lighter, not heavier.** The median went from 147.543 to 147.431 kB on the branch, and to
  147.698 kB after rebasing onto source sign-in (main was at 147.751). `/scholarship/apply`'s line was lowered
  from 189 to 187.
- **The adversarial review paid for itself.** It found three real faults and one cache hazard before the push.
- **Its "plausible" items were settled on live data, not argued:**
  - no institution with courses has a blank state;
  - no degree has a blank university;
  - no institution id carries two spellings;
  - no TVET course spans two categories or falls back to `tvet`;
  - the only courses with no campus are the 2 Bumi-only matric tracks.
- **The builder bite-checked its guards** (`planPicker.scope.test.ts`, `bumiputera.scope.test.ts`) and each
  review fix, restoring files by digest.

## What Went Wrong

- **Stitch could not produce the mock-up.** `generate_screen_from_text` timed out twice, and `list_screens` never
  showed the new screens.
  - *Cause:* the Stitch-first rule has no fallback. A generate that "times out" is assumed to have succeeded, and
    nothing says how long to wait before switching tools.
  - *Fix:* when Stitch times out twice and the screen is not listed, switch to a design canvas artifact (two
    boards, one per branch) and get approval there. That is what happened here, at the cost of about one round of
    waiting. The lesson already existed (lessons.md, clause hierarchy, 2026-07-19: fall back to an Artifact mockup)
    and was followed, so nothing new was added. The cost is the two timed-out attempts before switching.
- **The builder's first build put ~3 kB on EVERY route.**
  - *Cause:* a top-level `new Map()` in the new `lib/api/offerings.ts`. The bundler treats a module-level
    constructor call as a side effect, so it could not drop the module from the `@/lib/api` barrel, and the
    barrel's chunk split changed for every importer.
  - *Fix:* the map is now made on first use, with a comment at the site. The general rule (no module-level
    side-effectful constructors in anything the `@/lib/api` barrel re-exports) is now in lessons.md (2026-10-30). The bundle gate
    caught it locally, before any push, which is the gate working.
- **The writers of the new keys were not walked.** The brief and the build checked every server READER of
  `chosen_programme`, but no WRITER. The offer confirm merged a new `institution` over the student's pick and left
  her old `institution_id` beside it, so /profile, which re-opens by id, would have shown the wrong campus.
  - *Cause:* adding a field to a JSON blob was treated as a read-side change. Every code path that rewrites a
    sibling key also has to keep the new key true.
  - *Fix:* there is now one writer, `card_display.with_institution`, used by all eight write sites. The rule for
    future briefs is in lessons.md: when a stored shape gains a key, walk its writers as well as its readers.
- **A new test could not fail.**
  - *Cause:* `test_the_catalogue_fill_never_overwrites_her_pick` passed `offer_check={}`, so nothing could resolve
    and the function returned False with or without the guard. Its author did not bite-check it, and the builder's
    report described bite-checks on the two scope guards only.
  - *Fix:* the test now feeds the other campus's letter, and it turns red when the guard is removed. The workflow
    rule (sprint-close step 4b: a guard is a hypothesis until an injected fault turns it red) already existed. The
    gap is that it was applied to some new tests and not all of them. The review brief now asks for "a guard test
    that cannot fail" as a named hunt item, which is how this one was found.

## Design Decisions (decisions.md, 2026-10-30)

- **Unfiltered by default.** Requirements change from year to year, and an enrolled student may have entered
  under older rules. Filtering is opt-in, and only in the browser.
- **One endpoint per pathway rather than one catalogue download.** The browser fetches only what it draws, and the
  response is cacheable for an hour.
- **Institution names use the CATALOGUE spelling,** because that is what `offer_pathway._campus_rows` compares an
  offer letter against.
- **Owner answers at deploy:**
  - a wrong-campus pick may raise a clash, with a red ladder chip, until she confirms;
  - PISMP has no campus step;
  - the STPM top-3 slots search all degrees unfiltered.

## Numbers

| Gate | Result |
|---|---|
| api (pytest) | 10,861 passed / 3 skipped (`pytest -n auto`, final rebased branch) |
| web (jest) | 5,432 tests / 340 suites; tsc, lint and i18n ok (6,256 keys per locale) |
| Bundle median | 147.698 kB against 148 |
| `makemigrations --check` | clean |

**Live smoke** (courses / institutions per pathway):

| Pathway | Courses | Institutions |
|---|---|---|
| asasi | 57 | 24 |
| university | 180 | 12 |
| poly | 85 | 35 |
| kkom | 54 | 101 |
| pismp | 49 | 27 |
| iljtm | 59 | 30 |
| ilkbs | 51 | 22 |
| mara | 181 | 233 |
| tvet_other | 8 | 3 |
| degree | 1,112 | 20 |

There are no duplicate ids and no blank states. An unknown pathway returns 400.

## Follow-ups

- **TD-434 (latent):** the TVET pathway map's first-category-wins rule decides which picker lists a course. Check
  it again after any TVET ingest.
- **TD-427:** the median has 0.302 kB of room.
- **Not driven live:** the signed-in apply form (no test account). Jest covers it.
- **Revisit if** students name the wrong campus often (decisions.md).
