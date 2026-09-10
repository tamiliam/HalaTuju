# Retrospective — Sponsor spending S3: every payment gets a category

**2026-09-10.** Worktree `.worktrees/spending-ingest`, branch `feat/spending-ingest`.
Roadmap `docs/plans/2026-09-10-sponsor-spending-roadmap.md`.
**Backend only. NO MIGRATION. Not merged, not deployed. No sponsor-visible change.**

## What was built

`apps/scholarship/spend_category.py` — the four-rung ladder, the ten-code vocabulary, the keyword
rules, the per-transaction spend-pattern inference and the Gemini rung. `manage.py sort_spending
[--apply] [--all] [--no-ai]`. `--no-sort` on `ingest_spending`, which otherwise finishes an
`--apply` run by sorting what it stored. Cron entry `spending-sort` — **a door, not a schedule**.
57 new tests, **6236 in the full suite**.

Measured over the eight real exports, rungs 1–3 only:

    288 merchants: 126 by keyword rule, 60 by spend pattern, 102 left for the model
    food 976 rows RM5,383.60 · unsorted 173 rows RM3,182.33 · groceries 55 rows RM1,030.60
    study 139 rows RM578.70 · transport 21 rows RM336.54 · clothing 1 · health 1 · transfer 2
    1,368 rows, RM10,662.72 — the RM10,650.22 spent plus RM12.50 received

## What went well

- **The rules were written FROM the data, not from domain knowledge, and it changed the answer.**
  The plan predicted "~100 merchants" for rung 2 from an earlier sample. Dumping all 288 real
  merchant names with their visit counts and medians first produced **126**, and it produced the
  two rules that were not guessable — `KOPERASI`/`KOOP` is the campus shop, `KTMB` is the national
  railway. It also produced the trap: `DUNKIN' - BHP KARAK` is a doughnut counter inside a petrol
  station, which a transport-first rule order would have filed as a bus fare.
- **The two named regression cases came from the corpus and are asserted against the corpus.** The
  ceiling's tests do not say "returns None above RM20". They say `AL HUDHA ENTERPRISE`'s RM200 and
  `TEGUH ENIGMA (MATRIK 1)`'s RM97.70 must not be food **while their small rows still are** — and
  the corpus test re-derives both from the real files rather than from a fixture. Running the
  ladder over the real data then found four MORE such payments nobody had named (`RAMLI BIN
  SURATMAN` RM50.60 and RM24.20, `MES IBAS ENTERPRISE` RM30, `TEGUH ENIGMA` RM21.80): **six
  payments, RM424, that a merchant-level verdict would have called campus meals.**
- **Thirteen bite-checks, thirteen bit, none silent.** After S2's two silent bites, each guard's
  test was written from the harm before the guard was considered done. The newline was derived from
  the file in every anchor (`nl = '\r\n' if '\r\n' in raw else '\n'`) and no anchor missed.
- **The one gap found this sprint was found by asking the S2 question, not by a failure.** See below.

## What went wrong

### 1. The sorter was written with no way to run it, and I did not notice until I went looking

**Symptom.** `sort_spending` was finished, tested and green — and reachable only from a laptop that
has no database. On production it could not have been run at all.

**Root cause.** I reasoned about the *daily* path (`ingest_spending --apply` sorts what it stores,
so the schedule stays one entry) and stopped there, because that path was covered. The command's
whole reason for existing is the OTHER path — the owner tunes a keyword rule and every already
sorted row must be reconsidered — and that path had no route to the data. I had chosen "a separate
command" as the sprint's one design decision and then not asked how the separate command would ever
run.

**Why this stings.** `test_repair_commands_have_a_door.py` exists in this repo *for exactly this*,
and its docstring is the story of `backfill_untagged_income_docs` sitting finished and unreachable
for a fortnight. It did not catch this one because it scans `backfill_*` / `repair_*` by name and
`sort_spending` is neither — correctly, since it is not a repair. **The guard's NAME SCAN is its
strength and its blind spot at once**, and I read the file this sprint (to check my `JOBS` change
had not broken it) without asking whether its question applied to what I was building.

**System change.** `spending-sort` registered in `CronRunView.JOBS`, with three tests: the entry
exists with its flags, the endpoint actually invokes it, and — the one that matters — **the
registered `--all` still leaves an `owner` row untouched**. The general form is in `lessons.md`:
the door question is owed by every command that writes, not only by the ones the scan is named for.

### 2. The plan's own acceptance numbers were an estimate presented as a measurement

**Symptom.** The roadmap said rung 2 reaches "~100 merchants" and rung 3 "62 merchants / 681 rows".
The shipped rules reach **126** and **60 / 689**. Nothing was wrong — the earlier figures came from
a smaller draft rule set — but they had been written into the plan in the same shape as the corpus
figures (1,368 / RM10,650.22) that ARE measurements, and the sprint's acceptance criterion was
therefore a number that could only be met by accident.

**Root cause.** I did not distinguish, when writing the roadmap, between *"this is what the data
says"* and *"this is what I expect my not-yet-written code to do"*. Both were stated as bare
figures with no hedge and no source.

**System change.** The corpus test now asserts the numbers the SHIPPED rules actually produce
(288 / 126 / 60 / 102), with the date they were measured, so the assertion is a regression pin
rather than a target. The habit is in `lessons.md`: a predicted figure and a measured figure must
never be written in the same shape.

### 3. Two rungs had no test asserting where their INPUT comes from

**Symptom.** Nothing pinned that the visit history is read from the whole table. Replacing it with
`merchant_stats([])` — which is what "optimise it to only look at the batch" would amount to —
would have passed every test except the two I only wrote after going looking.

**Root cause.** I tested what each rung DECIDES and not what it decides FROM. The harm is
specific and quiet: the weekly job sorts a handful of new rows, so a stall visited forty times would
look like a first visit **every single week** and nothing would ever be inferred. The category
totals would simply drift toward `unsorted` with nothing failing.

**System change.** `test_the_pattern_is_read_from_every_row_we_hold_not_from_this_batch` — four
rows sorted, then ONE new row at the same shop, which must still be `inferred`. Bitten and it bit.

## Design decisions

In `docs/decisions.md`: a separate `sort_spending` command with its own cron door; the sorter runs
inside `ingest_spending --apply` so the schedule stays one entry; the model answers per MERCHANT and
never per transaction; `transfer` is unreachable from the model's vocabulary; a keyword rule is
re-derived every run while a stored `ai` answer never is; and the ceiling lives on the transaction.

## Numbers

| | |
|---|---|
| Files touched | 7 (3 new) |
| pytest, full `apps/` | **6236 passed** (+57) |
| `makemigrations --check` | clean — **no migration this sprint** |
| Migration ledger vs production | unchanged: scholarship **154/155** (`0155` still unapplied, **both its tables confirmed ABSENT**), courses **74/74** |
| Bite-checks | **13 injected, 13 bit, 0 silent** |
| Billable AI calls in CI | **zero** — the whole surface mocks at `vision._call_gemini_json` |
| Frontend gates | not run — no web file changed |

## At deploy (owner-gated, NOT done)

Unchanged from S1/S2, plus one:

1. S1's **`scholarship/0155` MIGRATE-FIRST** — still the first step, still unapplied.
2. Security Advisor shows no new finding; merge + push (**api only**).
3. Set **`VIRCLE_SPENDING_FOLDER`** if the live tree differs (read it from
   `gcloud run services describe`, never from the settings default).
4. **⚠ RUN `ingest_spending --drive` WITHOUT `--apply` ONCE AND READ IT** — the Drive hop has still
   never run anywhere.
5. Create the DAILY Cloud Scheduler job hitting `spending-ingest`.
6. **⚠ NEW: THE MODEL RUNG HAS NEVER RUN EITHER.** Every test mocks the seam, so rung 4 is exactly
   as unproven as the Drive hop was. First real run asks about ~102 merchants in 3 batched calls,
   then near zero for ever. **Run `sort_spending` WITHOUT `--apply` first and read which merchants
   it proposes to ask about** before letting it write anything.
7. **Nothing a student or sponsor sees changes.**
