# Retrospective — Sponsor spending S4a: the officer can see it, and correct it

**2026-09-10.** Worktree `.worktrees/spending-ingest`, branch `feat/spending-ingest`.
Roadmap `docs/plans/2026-09-10-sponsor-spending-roadmap.md`.
**api + web. NO MIGRATION. Not merged, not deployed. Nothing a sponsor or student sees changes.**

## What was built

`/admin/spending` — a console page next to Payments. One row per **shop**, not per payment: four
computed figures, the merchant table with a category control, the per-student table, what the model
decided in the last fortnight, and the two wallet gaps that are derivable. Backed by
`apps/scholarship/spend_report.py` (the read model + the one write) and two endpoints on
`views_admin.py`. en/ms/ta. 42 new backend tests, 27 new frontend tests.

**The sprint was SPLIT before it began.** The roadmap bundled the officer screen with a
Gemini-written summary filed back to Drive. Owner chose the split: the screen is what unblocks S5
and is fully testable here, while the summary writes to Drive — the same wall the fetch hit — and
is a text generator rather than a page. S4b carries it.

## What went well

- **Merging `main` FIRST was the right call and cost nothing to decide.** S1–S3 were backend-only,
  so a stale branch had been free; `main` had since moved eight commits, all web. Writing a console
  page on top of stale web code is how a merge becomes a rewrite. Both conflicts were the same
  shape — each side had added a section at the top — and the CLAUDE.md one mattered: only ONE
  `## Next Sprint` may exist, so main's was demoted and **its still-standing pointer carried into
  ours** rather than buried.
- **Skipping Stitch for the table, and using it for the one new thing, was the honest reading of
  the rule.** The console already has an approved table standard (`TableFrame`, one page width),
  and the Stitch note in memory says explicitly: where an approved design of record exists, build
  from it. What was genuinely new was the **correction control**, so that is what was prototyped —
  one pattern, not a whole cockpit, per the lesson that a dense all-in-one prompt times out twice.
  It rendered first try, synchronously.
- **Reading the mockup against the rules caught a privacy slip in the design.** Stitch drew
  "Today, 2:14 pm" under LAST SEEN. We discard the time of day at import, on purpose, so that no
  surface can ever show what hour a student ate. The column ships date-only and a test asserts no
  `\d{1,2}:\d{2}` appears anywhere on the page.
- **The repo's own guards did most of the reviewing**, and each one that fired found something
  real rather than something cosmetic. See below.

## What went wrong

### 1. A silent bite-check found a REAL defect, not just a missing test

**Symptom.** Injecting `decided_by='ai'` into the correction's merchant write changed no assertion.
Eleven other bites bit; this one reported green while genuinely broken.

**Root cause, and it is worth stating precisely.** `set_owner_category` does two things: it writes a
`MerchantCategory` verdict, and it updates every existing row of that shop. **Every test I had
written observed the second one.** The rows move, and they survive a re-sort, because
`decided_by='owner'` takes them out of the sweep — all true with the merchant verdict corrupted.

What the merchant verdict actually buys is the payments that **have not arrived yet**. The shop is
visited weekly. With the verdict wrong, next week's payment lands undecided, the ladder re-decides
it from a keyword rule, and the officer's answer quietly stops applying — at a shop they had
already fixed, with nothing failing and nothing to see.

**The tell I missed.** I tested the change I had just made (rows move) rather than the promise the
screen makes (*"anything you change here is kept for good"*). Those look identical for exactly as
long as no new data arrives.

**System change.** `test_a_correction_also_claims_the_payments_THAT_HAVE_NOT_ARRIVED_YET` — correct
a shop, let a NEW payment arrive at it, run the sorter, and assert the new row inherits the
correction. It failed on first run for a second reason (a shop can only be corrected once it has
been visited — the fence on the write), which is itself worth knowing. The bite then bit.

### 2. I moved admin queries into a new module and the fence guard could not see them

**Symptom.** `TestOrgFenceStaticGuard` passed the whole time I was writing `spend_report.py`, which
queries `ScholarshipApplication` and `BursarySpendTxn` for an admin surface.

**Root cause.** The guard scans `views_admin.py` **by filename**. That scope is its strength — it
is why it cannot be argued with — and its blind spot in the same sentence. S3's lesson was the same
shape one layer up (the repair-door guard scans `backfill_*`/`repair_*` by NAME and could not see
`sort_spending`), and I wrote that lesson six hours earlier.

**What widening it found, immediately, three times over:**
1. My own deliberate cross-organisation write, explained in prose but without the pragma the guard
   reads — so it was a decision in my head, not on the record.
2. `spend_category.py` and `spending_import.py`, which query unfenced **correctly** (they are a
   nightly cron for every tenant, not an admin surface) and had never had to say so.
3. **`views_sponsor.py`, which has never been scanned and pre-dates all of this by months.** Logged
   as **TD-240** with the reason it was not done blind inside a spending sprint, and named in a
   `NOT_YET_SCANNED` ledger modelled on `NO_DOOR` — a decision written down, not a silence.

**And the guard's own floor was missing.** Removing a file from `SCANNED` would have made the scan
quietly stop looking, with nothing failing. Two floor tests now assert that every scanned file
exists and actually carries a watched query, and that no candidate module queries one while absent
from the list.

**A smaller repeat inside the same fix:** my first two pragmas sat at the TOP of a long comment
block and the guard reads a 200-character window, so both failed. The repo's own note says this in
so many words. Explanation above, pragma last, on the line before the query.

### 3. Three console-standard guards fired on things I had not thought about at all

None of these were subtle, and none would have been caught by reading my own diff.

* **The keyboard chord `G`.** It is `CHORD_PREFIX` — the key that ARMS a chord — so it can never BE
  one. Changed to `X`.
* **No phone cards.** The owner's own September rule: a list surface owes a phone layout, and
  staying table-only has to be a decision somebody wrote down. Built them.
* **No glyph for the menu row**, which would have silently fallen back to a dot.

**The one I had to think about:** the phone-card guard is satisfied by ANY `md:hidden` in the file,
so one card block would have covered a page with three tables. That is the "a guard is only as
strong as the cheapest way to satisfy it" lesson pointing at me. The merchant list — the real list,
the one an officer scans — got cards; the student table stays table-only with the reason written
in the file, the same reasoning the billing page's exemption records.

### 4. A namespace with no key-existence scanner

**Symptom.** i18n parity passed with `admin.spending.*` newly added, and would have passed just as
happily if the page called keys that existed in no locale.

**Root cause.** Parity proves en == ms == ta; it says nothing about EXISTENCE. Every namespace here
has its own scanner for that reason (`admin-sources-i18n.test.ts` and six siblings) and I added a
seventh namespace without one. This page is worse than average for it: most of its keys are built
dynamically (`admin.spending.by.${decided_by}`), which a static scan cannot see at all, and the
surface is dark — there is no user to notice a raw dotted string. That is precisely how the sponsor
redesign shipped ~47 non-existent keys and nobody saw for four sprints.

**System change.** `admin-spending-i18n.test.ts`, which enumerates each dynamic family against the
values the code can actually produce (the six rungs, the four figures, the three refusal codes) and
carries a floor test so a path change cannot make it vacuous.

## Design decisions

In `docs/decisions.md`: the officer screen is fenced at the QUERY because it is a row question, not
a field one; a merchant verdict is global while the LIST is fenced; `finance` is refused though
Payments admits it; the payload is built key-by-key with a planted-identifier test instead of a
serializer layer; the category control is a native `<select>`; and a correction re-reads the whole
overview rather than patching a row.

## Numbers

| | |
|---|---|
| Files touched | **25** (6 new) — 19 modified, of which 6 are docs |
| pytest, full `apps/` | **6304 passed** (+42) |
| jest | **2015 passed** (+27), 124 suites |
| `tsc --noEmit` | **24** — the documented baseline, unchanged (two of mine found and fixed) |
| `next lint` | **0 errors** |
| `next build` | compiled successfully; `/admin/spending` 3.97 kB |
| `makemigrations --check` | clean — **no migration this sprint** |
| Migration ledger vs production | unchanged: scholarship **154/155** (`0155` still unapplied, **both tables re-confirmed ABSENT**), courses **74/74** |
| Bite-checks | **15 injected, 1 silent on the first pass, test written, 15 bit** |
| Billable AI calls | **zero** — this sprint adds no model call at all |

## At deploy (owner-gated, NOT done)

Unchanged from S1–S3, plus:

1. **`scholarship/0155` MIGRATE-FIRST** — still the first step, still unapplied.
2. Security Advisor; merge + push. **⚠ THIS PUSH BUILDS BOTH SERVICES** — S4a is the first sprint
   in this arc to touch web. Expect TWO builds, not one.
3. `VIRCLE_SPENDING_FOLDER` from `gcloud run services describe`, never from a settings default.
4. **⚠ `ingest_spending --drive` WITHOUT `--apply`, once, and read it.**
5. **⚠ `sort_spending` WITHOUT `--apply`, once, and read it.** The model rung has still never run.
6. The DAILY Cloud Scheduler job on `spending-ingest`.
7. **Only then does the officer screen have anything on it.** Until the migration is applied and one
   import has run, `/admin/spending` renders its empty states — which is correct, and worth knowing
   before somebody reports it as broken.
8. **Nothing a student or sponsor sees changes.**

## Local note, not a code issue

This worktree had no `node_modules` (S1–S3 never needed them). It is now a junction to the main
checkout — **remove it with `rmdir`, never `rm -rf`**. `next build` prints one EPERM warning about
symlinking that junction into `.next/standalone`; it is a laptop artefact of the junction and does
not exist on Cloud Build, where `node_modules` is real. The compile itself succeeded.
