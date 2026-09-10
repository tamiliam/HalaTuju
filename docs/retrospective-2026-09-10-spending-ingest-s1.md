# Retrospective — Sponsor spending S1: a Vircle report becomes stored transactions

**2026-09-10.** Worktree `.worktrees/spending-ingest`, branch `feat/spending-ingest`.
Roadmap `docs/plans/2026-09-10-sponsor-spending-roadmap.md`; requirements
`docs/plans/2026-09-09-sponsor-spending-reports-brief.md`.
**Backend only. Not merged, not deployed. Migration `0155` NOT applied.**

## What was built

`apps/scholarship/spending_import.py` — the parser and the ingest. Two models
(`BursarySpendTxn`, `MerchantCategory`) + migration `0155`. `manage.py ingest_spending
--file/--dir [--apply]`, report-only by default. 32 tests.

Verified against the eight real exports: **1,368 unique transactions, 1,366 `SPEND`,
RM10,650.22**, 0 unparsed amounts, 0 unparsed dates, 0 unknown columns, 28 parent-held wallets,
2 person-to-person rows, coverage 1 Jul → 30 Aug 2026.

## What went well

- **The whole sprint was testable on a laptop, which was the point of splitting it out.** The
  roadmap separated parsing from the Drive fetch precisely because the service-account key lives
  only on the live service. That decision paid immediately: every drift rule was proven against
  real data before a single line of Drive code exists.
- **The corpus test asserts the acceptance criterion and skips when the data is absent.** It runs
  the full path — parse → wallet join → store — by building applications FROM the wallets found in
  the files, so no real identity is needed to prove the join. CI is unaffected.
- **Five bite-checks, five bites.** Report-mode-cannot-write, string amounts, the missing-column
  refusal, the shared-wallet guard and the old date format. Each injection was verified on disk
  before the run and restored by writing the original bytes back.
- **Reading `lessons.md` at sprint-start changed the code.** "A fix that depends on every future
  caller remembering is a convention, not a fix" is why a missing column RAISES instead of falling
  back, and "a unit test on a helper does not prove the helper is called" is why the load-bearing
  test drives the real command rather than the parser.

## What went wrong

### 1. I reported a total that was RM621 short, from a script with the exact bug it was measuring

**Symptom.** I told the owner the corpus totalled **RM10,029.03**, three times across three turns,
and wrote it into two plan documents as the sprint's acceptance criterion. The real figure is
**RM10,650.22** — 5.8% higher.

**Root cause.** My first analysis script summed `isinstance(v, (int, float))` and skipped
everything else. 88 of the 1,368 rows carry their amount as the STRING `"RM26.90"`. I had already
*found* that fact and written a warning about it — *"handle both or 88 real payments vanish"* — in
the same document, two paragraphs from the wrong number. The script never reported a skip, so the
total looked entirely plausible and nothing prompted a re-check.

**Why it survived.** A silent skip produces a smaller number, not an error. There is no shape to
notice. It was caught only because building the real parser produced a different total and I
compared them.

**System change.** `IngestReport` counts and NAMES every skip (`unparsed_amount`, `unparsed_date`),
`needs_attention` is true when any exists, and the corpus test asserts `unparsed_amount == []`
rather than merely checking the total. The general form is in `lessons.md`.

### 2. Twice I stated a finding from a weaker signal than the one available, and the owner corrected both

**Symptom (a).** I wrote that "the weekly exports overlap" as a property of the feed. **Symptom
(b).** I wrote that the 2026-07-19 report was "MISSING" and built it into the plan as an open
question for Vircle.

**Root cause.** (a) repeated the July brief's general claim as though it were this corpus's
finding; (b) inferred coverage from FILENAMES. In both cases the stronger signal was one query
away in data I already had on disk. Measured: exactly **one** pair of files overlaps (a date range
started a week early by hand), and the 26 July report covers **fourteen days**, so nothing is
missing at all.

**What it would have cost.** (b) was about to become code: a "did we get a file this week?" check
that would have alarmed on a gap that does not exist and stayed quiet the next time two weeks
arrive in one file.

**System change.** Coverage is derived from `transaction_date` values, asserted by
`test_coverage_comes_from_the_dates_inside_not_the_file_name`. Both plan documents corrected. The
general form is in `lessons.md`.

### 3. A large append via a bash heredoc failed on quoting and cost a round trip

**Symptom.** Appending ~145 lines of model code with `cat >> … <<'PYEOF'` died with
*"unexpected EOF while looking for matching `'`"*.

**Root cause.** Reaching for a shell heredoc to write code, when an editing tool anchored on the
file's last two lines does the same job with no shell in the path — the same class as the standing
"no `$()`, no inline `VAR=`" rule in the workspace CLAUDE.md.

**System change.** Minor and already covered by the Bash-hygiene rule; noted here so the next
session does not rediscover it. Use the editing tools for code, the shell for commands.

## Design decisions

Logged in full in `docs/decisions.md`: non-`SPEND` rows are stored rather than filtered at import;
the parser seam takes plain lists so S2 reuses it unchanged and openpyxl stays out of the service
image; a missing required column refuses the file while an unknown extra column only reports; a
wallet claimed by two students is skipped rather than guessed; `WALLET_EXPECTED_STATES` is its own
constant despite currently equalling `pool.RECENTLY_FUNDED_STATES`; and the corpus test skips
rather than committing fixtures derived from real student data.

## Numbers

| | |
|---|---|
| Files touched | 8 (3 new modules/tests, 1 migration, models, CHANGELOG, 2 plan docs) |
| pytest, full `apps/` | **6156 passed** (+32) |
| `makemigrations --check` | clean |
| Migration ledger vs production | scholarship **154/155** (only `0155`, deliberately unapplied; both its tables confirmed ABSENT), courses **74/74** |
| Bite-checks | 5 injected, 5 bit, all restored |
| Frontend gates | not run — no web file changed |

## At deploy (owner-gated, NOT done)

1. Apply **`scholarship/0155` MIGRATE-FIRST** via Supabase MCP — the hand-written Postgres DDL for
   both tables, **including `ENABLE ROW LEVEL SECURITY` + one `service_role` policy each**, is in
   the migration's own docstring. Record the `django_migrations` row BEFORE the push.
2. Confirm the Security Advisor reports no new finding.
3. Merge and push (**api only** — no web file changed, so expect one build).
4. **Nothing a student or sponsor sees changes.** Nothing runs on its own: the command is manual
   until S2 adds the Drive fetch and the schedule.
