# Retrospective — Sponsor spending S5: the card a sponsor actually sees

**2026-09-10.** Worktree `.worktrees/spending-ingest`, branch `feat/spending-ingest`.
Roadmap `docs/plans/2026-09-10-sponsor-spending-roadmap.md`. **THE ARC IS COMPLETE.**
**api + web. NO MIGRATION. Not merged, not deployed.**

## What was built

The reserved panel on `sponsor/(portal)/my-students/[id]` — the dashed box whose own comment had
said *"Reserved for the Vircle spending panel (a later sprint)"* since the page was written. Four
numbers as one bar, a hand-drawn SVG donut beside a ranked list, the assumptions note, and an
"as at" stamp. Backed by `apps/scholarship/spend_sponsor.py` and one new serializer field. en/ms/ta.
33 new backend tests, 24 new frontend tests.

**This is the only sponsor-visible part of the whole arc.** Everything in S1–S4b was internal.

## What went well

- **The Stitch prototype earned its place by being WRONG in a way only the rules could catch.** It
  drew "Today, 2:14 pm" under Last seen — pixel-perfect, and a quiet breach of a privacy decision
  three sprints old. Reading the mockup against the feature's own must-nots (rather than against
  the layout) also produced the second correction: the stamp now reads the last IMPORT, not the
  last purchase, because the newest `txn_date` is *the day this student last bought something*
  wearing a different hat.
- **The owner's two changes were both improvements to the RULES, not the pixels.** `transfer` and
  `unsorted` are never folded into "Other" — the two honest categories, the ones that stop the
  other nine reading as complete. Written into the code as `NEVER_FOLDED` and tested at both the
  function and the component.
- **A separate module for a separate audience.** `spend_sponsor.py` shares nothing with
  `spend_report.py`, which names merchants and students deliberately. Two audiences that different
  must not share a payload; the moment they do, a field added for the officer arrives on the
  sponsor card by accident.
- **No new dependency for the chart.** One SVG circle per slice with `strokeDasharray`, about
  thirty lines, on the repo's existing category swatches.

## What went wrong

### 1. Money reached the sponsor as a FLOAT, and the unit test could not see it

**Symptom.** `test_the_field_is_served_at_all` — the first test to drive the real endpoint —
failed with `30.0 != '30.00'`.

**Root cause.** A bare `Decimal` in a plain dict is encoded by DRF's JSON renderer as a **float**.
Inside `sponsor_card` the values genuinely ARE Decimals, so my unit assertion
(`assertIsInstance(..., Decimal)`) was green the whole time and would have stayed green for ever.
The conversion happens at a boundary the unit test never crosses.

**Why it matters beyond tidiness.** This is money on a donor's screen. A float is where
`1120.00` quietly becomes `1120.0000000000001` — and the repo's standing rule (`Decimal`, never
float, `payments._money`) exists for exactly that.

**System change.** Money crosses the boundary as a **string**, matching every other money-bearing
payload in the feature. The unit test now asserts the WIRE shape and walks the whole payload
asserting no float appears anywhere, however nested. The comment on the return block says why, in
full, so the next person does not "simplify" it back.

### 2. A line of code that pretended to be a safeguard, with a comment vouching for it

**Symptom.** Bite 2 — deleting a post-loop `kept.sort(...)` — changed no assertion.

**Root cause.** It could never have changed anything. `ranked` is already sorted and the loop
appends in that order, so `kept` is ordered by construction. The comment above it explained that it
re-ranked "a never-folded category rescued from below the cut", which sounds right and is not: a
rescued row is below the cut precisely *because* it is smaller than everything kept.

**The real defect it was hiding.** The two sorts used **different tie-breaks** — `ranked` on the
code, the re-sort on the label — so two categories on the same amount could order differently
depending on which sort won. That is a genuine wobble, and the dead line was masking the question
rather than answering it.

**System change.** One sort, tie-broken on the LABEL (what a reader sees), and the dead line
deleted. Two tests replace it: the kept rows are ordered, and two equal amounts produce the same
order whatever order they arrive in. **Dead code that looks like a guard is worse than none,
because it invites trust** — that is in `lessons.md`.

### 3. The card had tests; the DECISION NOT TO SHOW IT had none

**Symptom.** Bite 12 — making the panel render unconditionally — failed nothing.

**Root cause.** `SpendingCard.test.tsx` proves the card once it has data. Nothing tested the page's
`detail.spending ? … : …`, because I had written no page test at all. The harm is specific and
unpleasant: a student we have received no report for would show four zeroes and an empty donut,
which reads to a donor as *"they have spent nothing"*. That is a claim about a real person that we
cannot make; the likelier truth is that no report has reached us.

**System change.** A page test with three cases — panel present with data, panel ABSENT without,
and no "coming soon" copy surviving. Writing it immediately found a fourth thing: the scanner
below.

### 4. My own test named retired i18n keys, and the existing scanner failed the build

**Symptom.** `sponsor-i18n.test.ts` — untouched, years old — went red on
`sponsorPortal.myStudents.detail.soon`.

**Root cause, and it is the guard working.** I retired the "coming soon" copy (it stops being true
the day this ships — copy asserting a capability's ABSENCE has bitten this repo three times), then
wrote a test asserting those keys no longer render, spelling them out in full. The scanner reads
every literal `sponsorPortal.…` key in the source and demands each resolve. It could not tell an
assertion about a dead key from a use of one.

**Resolution.** The test now names PARTIAL paths (`.detail.soon`), which is precise enough to
assert and invisible to a scanner looking for whole keys — with a comment saying why, so it is not
"tidied" back into a full path.

### 5. Raw hex in an SVG, in a product that has none

**Symptom.** `theme.test.ts` failed with ten offenders, all mine.

**Root cause.** I picked six pleasant colours by hand. The whole product runs on tokens, and that
guard reads inline styles, SVG fills and lib constants *precisely because colour hides there* — its
own comment cites two earlier escapes of the same shape.

**What the repo already had.** A `category-N` family: eight swatches, three roles each, built so
one arbitrary category can be told from the next, with a warning never to use a TONE for a
category. Exactly this job, already designed, already dark-mode correct. **Reading the guard's
failure led to the right primitive; reading the guard beforehand would have been quicker.**

## Design decisions

In `docs/decisions.md`: a separate module for the sponsor payload; money crosses as a string;
`transfer` and `unsorted` are never folded; the stamp is the import, not the purchase; no card at
all rather than an empty one; and the donut is hand-drawn on category tokens with no chart library.

## Numbers

| | |
|---|---|
| Files touched | 14 (5 new) |
| pytest, full `apps/` | **6381 passed** (+33) |
| jest | **2044 passed** (+24), 128 suites |
| `tsc --noEmit` | **24** — the documented baseline, unchanged |
| `next lint` | **0 errors** |
| `next build` | compiled successfully |
| `makemigrations --check` | clean — **no migration** |
| Migration ledger vs production | unchanged: scholarship **154/155**, courses **74/74** |
| Bite-checks | **14 injected, 2 silent (both real defects), 1 harness fault, all resolved** |
| New dependencies | **none** |

## The arc, finished

| | |
|---|---|
| S1 | read a Vircle report correctly — 1,368 payments, RM10,650.22 |
| S2 | fetch new reports from Drive when they arrive |
| S3 | sort every payment into one of ten categories |
| S4a | the officer sees it, and corrects it |
| S4b | a written summary files itself back to Drive |
| S5 | the sponsor card — **the only sponsor-visible part** |

**⚠ FOUR PATHS HAVE STILL NEVER RUN ANYWHERE:** the Drive fetch, the Gemini sorting rung, the Drive
write, and now every screen against real data. All four need the live service.

## At deploy (owner-gated, NOT done)

1. **`scholarship/0155` MIGRATE-FIRST** + its ledger row, before the push.
2. Security Advisor; merge + push — **TWO BUILDS**.
3. `VIRCLE_SPENDING_FOLDER` and `VIRCLE_SPENDING_SUMMARY_FOLDER` from
   `gcloud run services describe`. The summary folder's PARENT must exist.
4. `ingest_spending --drive` without `--apply`, once, and read it.
5. `sort_spending` without `--apply`, once, and read it.
6. The DAILY Cloud Scheduler job on `spending-ingest`.
7. Open the Drive folder: the summary must be in `Summaries/`, not beside the exports.
8. **⚠ ONLY NOW DOES A SPONSOR SEE ANYTHING.** Before the migration and the first import, the
   officer screen shows empty states and the sponsor panel is ABSENT — both correct, neither a bug.
   Check one real student's card yourself before telling any sponsor it exists.
