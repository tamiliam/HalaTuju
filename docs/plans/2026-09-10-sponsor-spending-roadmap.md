# Sponsor spending reporting — the sprint roadmap

**Written 2026-09-10** via `Settings/_workflows/implementation-planning.md`. **Not yet approved.**

**The requirements live in `docs/plans/2026-09-09-sponsor-spending-reports-brief.md`** — read it first,
especially §0 (the July brief + the real column shape), §0b (the whole corpus measured), §4 (the
owner's rulings) and §4c/§4d (the sorting ladder + the assumptions note). This document is only the
decomposition; it deliberately repeats no reasoning.

**Also required reading:** `docs/plans/2026-07-18-bursary-spend-reporting-brief.md` (the July
implementation brief — models, ingest shape, risks).

---

## The shape of the work

A sponsor sees, on a student they fund: **promised · released · spent · left**, then a donut of ten
categories with a ranked list, then a note stating our assumptions. Weekly, for years.

**Five sprints.** The division is driven by three things:

1. **The Drive read cannot be tested on a laptop.** The service account credentials live only on the
   live service. So the parsing work — the genuinely hard part, with three header variants and a
   money column that is sometimes a string — is separated from the Drive fetch, and is developed
   against the **eight real reports already downloaded** to `Downloads/spending/`.
2. **The owner validates the sorting before any sponsor sees it.** The officer surface is its own
   sprint, ahead of the sponsor card, so a wrong category is caught by a human first.
3. **Riskiest first.** Ingest correctness, then the untestable Drive hop, then the sorter, then the
   two surfaces.

**Every sprint ships tested. Only S1 has a migration.**

---

## S1 — Read a spending report correctly ✅ SHIPPED 2026-09-10

**Done.** Retro `docs/retrospective-2026-09-10-spending-ingest-s1.md`; the rules a later reader must
not tidy away are in `halatuju_api/CLAUDE.md` under Next Sprint and in the modules' own docstrings.
`apps/scholarship/spending_import.py` + `BursarySpendTxn` + `MerchantCategory` + migration `0155`
(**NOT YET APPLIED — migrate-first**) + `manage.py ingest_spending`, report-only by default.

**The measured baseline S2 must keep reproducing**, from the eight real exports:

    1,368 unique transactions · 1,366 SPEND · RM10,650.22
    0 unparsed amounts · 0 unparsed dates · 0 unknown columns
    28 parent-held wallets · 2 person-to-person rows · coverage 1 Jul -> 30 Aug 2026

**⚠ The two things S2 inherits rather than rebuilds:** `rows_from_values(header, value_rows, source)`
is the ONE parser and takes plain lists — hand it Sheets API values and every drift rule comes free;
and `spending_import.ingest(sources, apply=False)` is the whole store-and-report half, unchanged.

---

## S2 — Fetch the reports from Drive ✅ SHIPPED 2026-09-10

**Done.** Retro `docs/retrospective-2026-09-10-spending-drive-s2.md`; the rules a later reader must not tidy away are in `halatuju_api/CLAUDE.md` under Next Sprint and in the modules' docstrings. **No migration.**

**⚠ THE ONE THING S2 COULD NOT PROVE, AND S3 MUST NOT ASSUME:** the Drive hop has never run. The service-account key exists nowhere but the live service, so `--drive --report` on production is still owed and is the only real verification.

**What S3 inherits:** `spending-ingest` (daily, `--drive --apply`) already imports whatever arrives, and `BursarySpendTxn.category` / `decided_by` are stored and blank. S3 fills them; it adds no ingest, no schedule and no migration.

---

## S3 — Sort the spending ✅ SHIPPED 2026-09-10

**Done.** Retro `docs/retrospective-2026-09-10-spending-sorter-s3.md`; the rules a later reader must not tidy away are in `halatuju_api/CLAUDE.md` under Next Sprint and in `spend_category.py`'s own docstring. **No migration.**

**Measured over the eight real exports with the SHIPPED rules** (a regression pin, not a target — the plan had estimated ~100 for rung 2):

    288 merchants: 126 by keyword rule, 60 by spend pattern, 102 left for the model
    food 976 rows RM5,383.60 · unsorted 173 rows RM3,182.33 · groceries 55 rows RM1,030.60
    study 139 rows RM578.70 · transport 21 rows RM336.54 · clothing 1 · health 1 · transfer 2

**⚠ THE TWO THINGS S3 COULD NOT PROVE, AND S4 MUST NOT ASSUME:** the Drive hop has still never run, and **now neither has the model rung** — every test mocks `vision._call_gemini_json`, so rung 4 is exactly as unproven as the Drive fetch. Both are owed on the live service.

**What S4 inherits:** every stored row carries `category` and `decided_by`, and `decided_by='owner'` already outranks all four rungs and survives a full `--all` re-sort — so the correction screen has nothing to build in the sorter, only a way to write that verdict.

---
## S4 — The officer view, and the correction

**Goal.** The owner can see every transaction, see what the AI decided, and correct it — **before a
sponsor sees anything**.

**Scope.** An admin surface: per-student spending, the **merchant-level** table (oversight is their
job), this week's AI decisions, unknown wallets, and a one-click `owner` override that outranks every
rung. Reuses the existing admin gates.

**Acceptance.** Correcting a merchant changes the totals on a re-read and is never overwritten.
Person-to-person transactions are flagged. Nothing here is reachable by a sponsor.

### S4 — the summary report written back to Drive (owner, 2026-09-10)

> *"Instead of an email, or perhaps in addition to an email, Gemini creates a summary report … and
> saves it in the same folder."*

**Both, because they do different jobs.** An **alert is PUSH** — nobody discovers a broken import by
opening a folder, so a fault still emails. A **summary is PULL** — it belongs where the data lives,
next to the file it describes, for whoever goes looking. Neither replaces the other.

**Written after every successful ingest of a new file**, not on a schedule — same trigger as S2.

**⚠ WE COMPUTE THE NUMBERS; GEMINI ONLY WRITES THE PROSE AROUND THEM.** This is the house pattern
already proven in `verdict_narrative.py` (*"the LLM only narrates the deterministic band … forbidden
to invent/change the band"*). Every figure in the report — totals, category splits, per-student
lines, coverage dates — is computed in Python and handed over. Gemini may not calculate, may not
add a figure, and may not draw a conclusion the numbers do not carry.

**⚠ THE REPORT IS INTERNAL, SO IT MAY NAME MERCHANTS — and it must still never leave that folder.**
It is written for the officer and the owner: merchant names, unknown wallets and this week's AI
category decisions are exactly what makes it useful. **It is not the sponsor's document and no part
of it is reused on the sponsor card.**

**⚠⚠ NEVER WRITE OUR OWN OUTPUT WHERE THE READER WILL PICK IT UP AS AN INPUT.** A summary dropped
beside the Vircle exports is a file the next ingest would try to parse as a report. Two independent
guards, both required: write into a **subfolder** (`06 Student Spending/Summaries/`), **and** have
the reader accept only filenames matching the Vircle export pattern. One guard is a convention; two
is a design.

Reuses `sheets.file_csv_to_folder`'s shape (proven by the payments CSV and the activation CSV).
Metered through `usage_context`.

**Complexity: MEDIUM.** ~14 files with the summary folded in. **No migration.**

---

## S5 — The sponsor card

**Goal.** Fill the reserved panel on `sponsor/(portal)/my-students/[id]` — the dashed card whose own
comment already says *"Reserved for the Vircle spending panel (a later sprint)"*.

**Scope.**
- **⚠ Stitch prototype approved BEFORE any page code** (house rule).
- The four numbers as one bar; the donut (top 6 + Other) beside a ranked list; the assumptions note
  from brief §4d; an "as at" stamp.
- **Allowlist serializer extension**, plus anonymity tests: a merchant name, a transaction id or a
  date appearing in the payload is a **test failure**.
- i18n en/ms/ta (ms/ta first drafts).

**Acceptance.** A sponsor sees categories and totals only. `spent > released` renders sensibly (brief
§4 — the wallet is the student's own). An empty `transfer` slice is absent, not "0". Nothing about
spending reaches the discovery/pool card.

**Complexity: MEDIUM.** ~11 files. **No migration.**

---

## Sequence, and what blocks what

    S1 ─→ S2 ─→ S3 ─→ S4 ─→ S5
    │      │      │      │      └─ Stitch approval
    │      │      │      └─ owner validates the sorting here
    │      │      └─ needs stored transactions
    │      └─ needs the live service to prove
    └─ needs nothing; fully testable on this laptop today

**Open questions for the owner (none block S1):**
1. ~~The 2026-07-19 report is missing.~~ **ANSWERED by the owner, 2026-09-10, and verified against
   the data: it is not missing.** The 26 July report covers fourteen days and holds that week.
   Coverage is unbroken 1 Jul → 30 Aug. **Consequence for S1: coverage is derived from the
   `transaction_date` values, NEVER from the filename or the file count** (brief §0b).
2. ~~How far back do we ingest?~~ **ANSWERED, 2026-09-10: from the start.** All eight reports,
   1 Jul 2026 onward. The corpus IS the history; there is no earlier data.
3. ~~Does an unknown wallet need chasing?~~ **ANSWERED, 2026-09-10 (owner): *"This shouldn't happen.
   If it did, we need to be alerted somehow."*** So the weekly job carries an alert.

### ✅ THE ALERT — owner ruling, 2026-09-10

**The weekly job emails `ADMIN_NOTIFY_EMAIL` when, and only when, a human is needed.** Four
conditions, all of them "this should not happen":

| Condition | Why it is an alert, not a log line |
|---|---|
| **A wallet in the report matches no student** | Money moved on an account we do not recognise. |
| **A funded student has no `vircle_id` recorded** | The opposite gap — we hold the student, not the wallet. A different fault with a different fix, so a **separate list** (lessons: *"never happened" and "failed" are different states*). |
| **An unrecognised column header** | The layout has already changed FOUR times (names, money format, date format, coverage span). This is the likeliest failure and the quietest. |
| **A repeated `transaction_id` whose fields DISAGREE** | Every repeat so far is identical, so a disagreement is a CORRECTION and must never be silently dropped (brief §0b). |

⚠ **SILENCE MUST MEAN "NOTHING TO REPORT" — no weekly "all clear" email.** A message that arrives
every week regardless is a message nobody opens, and the one week it matters it is skimmed with the
rest. This is the same reasoning that keeps the activation cron quiet when its list is empty.

⚠ **THE ALERT NAMES THE WALLET, NEVER THE STUDENT'S NAME.** It goes to staff, so it may carry the
wallet id and the application id — the two things needed to fix it. It carries no merchant and no
amount, because neither helps and both widen the blast radius of a forwarded email.

⚠ **AN ALERT NEVER STOPS THE INGEST.** Unknown-wallet rows are skipped and counted; everything else
still lands. The exception is the unrecognised header, which **must** stop that file — parsing on
past a header we cannot read is how wrong money gets attributed to a real student.

---

## Deliberately NOT in scope

Vircle API integration (none exists). Per-month views (owner ruled all-time, weekly refresh).
Merchant names, dates or times reaching a sponsor — ever. Any consent-version change (§4: the live
consent already covers an anonymised summary).
