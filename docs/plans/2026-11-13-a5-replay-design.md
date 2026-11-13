# Advisor action 5 — replay real past cases through the old and new engines (DESIGN, no build)

- **Date:** 2026-11-13. **Status:** design for owner review. Nothing is built, nothing has been run.
- **Gate:** finished and reported before features resume (about 4 December 2026).
- **Asked by:** the advisor, after the v3.1.0 audit (`docs/audits/2026-11-05-project-audit.md`) and its fix
  roadmap (`docs/plans/2026-11-05-audit-fix-roadmap.md`).
- **Question it answers:** "Did the audit changes (5 to 12 November) change the outcome for any real past case,
  other than where the owner ruled that they should?"

---

## 0. In one paragraph

We take every real past case. We run it through the engines as they were at **v3.1.0** (old) and as they are on
**live main** (new). Both runs read the **same frozen copy of the database at the same moment**, so the only
thing that differs is the code. We compare the answers field by field. Each difference is either **(A)**
expected, because an owner ruling says so (we cite it), or **(B)** unexplained. The owner gets a short report:
plain English, counts, and a table of the B items. The run is a **read-only Cloud Run job** inside the HalaTuju
GCP project. It holds no AI key, reads no document file, writes nothing, and costs well under RM5.

---

## 1. Which engines

Every engine below is a **reader**: it takes stored data and returns an answer. None of them needs a document
image or an AI call; they read the stored reads (`vision_fields`, `vision_*` columns) that are already in the
database. All of them are **DB-bound** (they take a model row and follow its relations), so they need a real
database, not a fixture. Writers (pay, release, withdraw) are not replayed: see section 6.

### 1(a) Verdict and genuineness

| Entry point | Input | What we compare |
|---|---|---|
| `verdict_engine.build_verdict(application)` (calls `verdict_academic`, `verdict_identity`, `verdict_pathway`, `verdict_income_str`, `verdict_caps`, `verdict_ladder`, `higher_results.verdict_academic`) | one application | per fact: present or omitted, `status`, the sorted list of `unresolved` codes, the sorted list of `evidence` codes, and a hash of the `params` (never the params themselves: they can hold names) |
| `award.verdict_disqualifier(verdict)` | the verdict above | the code, or blank |
| `resolution.doc_match_verdict` (now `resolution_doc_match`) | one document | the match verdict word |
| `higher_results.match_verdict(doc)` | one higher-results document | the verdict word |
| `academic_engine.student_slip_check(doc)`, `semester_check(doc)`, `student_school_leaving_check(doc)`; `higher_results.student_higher_check(doc)` | one document | the result dict, keys sorted, text values hashed |
| `help_engine.verdict_for_document` (now partly `help_verdict`) | one document | the help verdict code |
| `gap_engine` (the gap list it builds from `build_verdict`) | one application | the sorted gap codes |

`academic_compare.compare_academics` and `spm_slip_compare` are reached through `build_verdict`; we do not call
them on their own. `higher_results.extract` and everything under `vision/` are **reading** (they call OCR and
Gemini), so they are out of scope by rule.

### 1(b) Eligibility

| Entry point | Input | What we compare |
|---|---|---|
| `shortlisting.evaluate(application, cohort)` (the programme's own gates: consent, birth state, public diploma, academic floor, SPM bars, income and per-capita rescue) | one application and its intake | `verdict`, `bucket`, `category`; the reason text hashed (it carries income figures) |
| `courses.engine.check_eligibility(student, req)` over the whole SPM catalogue, plus `eligibility_service.compute_student_merit` | one student profile with SPM grades | the set of eligible course codes, and the merit figure |
| `courses.stpm_engine.check_stpm_eligibility(...)` over the STPM catalogue | one profile with STPM grades | the set of eligible course codes |
| `requirements.required_documents` / `required_questions` | one application | the sorted code sets |

`income_engine/` is eligibility under the house rules. It is reached through `build_verdict`'s income fact and
`shortlisting`, so it is covered there.

### 1(c) Money

| Entry point | Input | What we compare |
|---|---|---|
| `award.proposed_award_amount(application)` and `award.course_start_unknown(application)` | one application | the amount (or None), and the yes/no |
| `funding_estimate.classify_pathway` and `estimate_funding(application)` | one application | the pathway class and the estimate dict (amounts as 2-decimal strings) |
| `payments._schedule_row` (template row through `contracts.pick_schedule_row`, else `default_schedule.row_for`) | one application | which row (template id and row key, or "default"), its monthly amount, gap months and end |
| `payments.eligibility(application, date, period_month)` and `payments.default_amount(application)` | one payable application, for **two pinned months** (the next run's month and the one after) | `eligible`, the sorted `reasons`, `remaining`, and the amount due |
| `payments.paid_to_date(application)` | one application | the sum (a control: it must never differ) |
| `sponsorship.wallet.sponsor_balance(sponsor, programme)` and `sponsor_available_total(sponsor)` | each sponsor and gift | the balances |
| `contracts.schedule_calendar(row, cohort_year)` | the row above | the list of paid months |

Credit steps (`credit_steps`) decide **who** may sign, not **how much**. Action 4 (the access matrix) covers them.

### The adapter

Some of these functions moved between files after v3.1.0 (A3.4, A3.6, A3.8 split files; for example
`contracts.py` became `contracts/`, `sponsorship.py` became `sponsorship/`). The harness keeps one small **engine
map**: for each engine, the import path in the old tree and in the new tree. The image build fails if any path
does not resolve in its tree, so a moved name can never be compared against nothing.

---

## 2. Which "old"

**Baseline: the `v3.1.0` tag, commit `442b21f4d` (2026-11-05 10:00 MYT).**

Why this one:

- It is the release the audit measured. The audit and the roadmap start from it.
- The first audit fix to an engine (`b0bedd549`, TD-465, money) came at 14:46 the same day. Nothing in the
  engines changed between the tag and that fix.
- It holds exactly the api code that was live on 5 November: `3c39489b` (the last live api deploy before the tag)
  is its ancestor, and there is no api change between them. The tag only adds a web dependency floor.
- The old verdict engine says `VERDICT_ENGINE_VERSION = '2026-11-04.1'`; the new one says `'2026-11-07.2'`.
  Every version note in between is an owner ruling (section 4 uses them).

**New:** live main `70a51cdc7` (2026-11-12), or whatever main is live on the day of the run. The report prints
the exact commit of each side.

One baseline, not one per wave. Per-wave baselines would tell us *which* sprint caused a difference. We do not
need that up front: a B item is traced afterwards with `git log` on the engine it came from.

### Can the old code run on today's database?

Mostly yes. Between v3.1.0 and live main the migrations are:

- **Added only (old code simply does not see them):** courses 0092, 0095, 0096, 0097; scholarship 0203 (an index),
  0204 to 0210 (new tables and columns).
- **0211 (A3.17):** three fields left Django's state, but the **columns still exist** in the database (step 2,
  the drop, is not written yet). Old code reads them happily.
- **courses 0093 / 0094 (TD-064): the `is_super_admin` column was DROPPED.** The old `PartnerAdmin` model still
  names it, so any old-code query that loads a `PartnerAdmin` row fails.

How we handle it:

1. None of the engines in section 1 should load `PartnerAdmin`. Expect zero cases.
2. If one does, the case is put in class **C (could not run)** with the engine name. It is not guessed.
3. If C is more than a handful, the old side gets one documented shim: the old `PartnerAdmin` queries defer that
   one field. Nothing else in the old tree is touched.

**Library versions also moved** (A1.2 changed 10 lines of `requirements.lock`). So the image carries **two
virtual environments**: the old tree runs on v3.1.0's lock, the new tree on main's. A library change is then
part of "old" or "new", as it was in production.

We do **not** need a schema-matched snapshot, and we do **not** need to fall back to stored historical
outputs for the main comparison. Stored outputs are used as a second, separate lens (section 4.4).

---

## 3. Which cases, which data, where it runs

### 3.1 The cases

All real rows, every organisation, every gift, every intake. No sampling: the counts are small enough.

| Engine family | Cases |
|---|---|
| Verdict, per-document checks | every application past draft (submitted or later, including closed and declined), and every live document on them |
| Programme eligibility | every application past draft, with its own intake |
| Course eligibility | every student profile with SPM or STPM grades (course guide users included) |
| Award and funding estimate | every application past draft |
| Schedule, payment eligibility, amount due | every application in `PAYABLE_STATUSES` |
| Sponsor balances | every sponsor and gift pair |

We do not count them now (no live query in a design). R1's first step on the live job prints the counts only.

### 3.2 The data rules (hard)

- **No re-extraction, ever.** No Gemini, no Vision, no Storage read, no file opened. The job is given **no**
  Gemini key, no Vision credentials, no Storage key, no Brevo key, no Vircle settings. A code path that tries to
  read a document fails at once and the case is recorded as C, with the engine name.
- **No paid call.** Same reason: the keys are not there. On top of that, a socket guard allows outgoing
  connections to the database host only; anything else raises.
- **No personal data leaves.** The job prints only: case number, engine name, field name, old value, new value,
  where values are codes, statuses, yes/no, amounts or course codes. Names, IC numbers, addresses, income figures
  in text, and `params` are never printed: they are compared by hash. An error is logged as its **class name
  only**, never its message or traceback (a message can quote a field). A test proves each of these.
- **Nothing in the repo or the report holds personal data.** The report lists case numbers (the cockpit's
  application id, already used in `decisions.md`, for example "app 278"), never a name.
- **No write to production.** See 3.4.
- **Not the same as `rescore_pending_decisions`.** The replay never stores a verdict, never touches
  `ai_verdict_snapshot`, and sends no email.

### 3.3 Where it runs — the options

| Option | For | Against | Cost |
|---|---|---|---|
| **(i) Read-only Cloud Run job against production** | Data never leaves Google and Supabase (same project, same region as the live api). Real data, untouched. No copy to look after or delete. | It reads the live database, so the read-only guard must be strong (3.4). | Build about 2 minutes of Cloud Build (free tier); one job run about 30 minutes on 2 vCPU: under USD 0.50. |
| (ii) Local run on a sanitised snapshot | No load on production. | A full copy of personal data lands on a home machine or laptop, which the rules forbid. Sanitising breaks the engines we want to test: identity and academic compare names (look-alike letters, patronymics, reversed names), so fake names change the answers. | Free, but a high data risk. |
| (iii) A restored copy in a new Supabase project | Production untouched. | A second paid project (about USD 10 a month while it lives), a full copy of personal data to manage and delete, and a restore the owner must run. | Over budget for one run. |

**Pick: (i), the read-only Cloud Run job.** It is the only option where personal data stays where it already is,
and the engines see real names, so identity results are honest. The load is small: a few connections, reads only,
run off-peak (02:00 to 05:00 MYT).

### 3.4 How "read-only" is enforced (five layers, each enough on its own for writes)

1. **A read-only database role** (owner step). A new Postgres role, `replay_ro`, with `SELECT` on the `public`
   tables only and no other grant. Its connection string goes into Secret Manager as its own secret. The job
   mounts **that secret only**. This is the strongest layer: the database itself refuses a write.
2. **Every transaction is read-only, at transaction level.** The first statement is
   `SET TRANSACTION READ ONLY` (or `BEGIN ... READ ONLY`), then `SHOW transaction_read_only` must answer `on`, or
   the job stops. **Never** a session-level setting through the Supabase pooler (memory rule: it leaks onto the
   shared backend). The job connects through the **session pooler (port 5432), never the transaction pooler
   (6543)**.
3. **Always rolled back.** The transaction is marked for rollback whatever happens.
4. **A statement filter.** A `connection.execute_wrapper` refuses any statement that is not a read (INSERT,
   UPDATE, DELETE, DDL, `SELECT ... FOR UPDATE`). This is the pattern already used and reviewed in
   `apps/scholarship/eval/offer_s4_dry_run.py`; the harness reuses it.
5. **Nothing to write with.** No email backend (a refusing backend is set), no Storage key, no AI key, no cron
   secret.

If an engine *tries* to write (for example a cache save), layer 4 refuses it, the case is put in C with the
engine name, and the run goes on. Each case runs inside its own savepoint, so one refusal does not end the run.

### 3.5 Same data for old and new

The parent process opens one `REPEATABLE READ READ ONLY` transaction and exports its snapshot
(`pg_export_snapshot()`). Each child (old, new, and a second new run) opens its own read-only transaction and
joins that snapshot (`SET TRANSACTION SNAPSHOT`). So all three see exactly the same rows, even if a reviewer saves
a case during the run. R1 proves this works through the Supabase session pooler on a local Postgres first. The
fallback, if it does not: run old and new back to back, then re-run every differing case once; a difference that
vanishes on re-run is data movement, not code.

### 3.6 Same clock for old and new

Some engines read today's date (income document freshness, course start against the intake year, payment
months). Both trees run with the clock pinned to one instant (the snapshot time), patched in the harness for
`django.utils.timezone.now` and the date helpers the engines use. The two payment months are fixed in the job's
arguments.

### 3.7 The image

One image, built by hand with Cloud Build (no trigger; it is not the api image and deploys nothing):

- `/replay/new`: the api tree at the live main commit, with its own venv.
- `/replay/old`: `git archive v3.1.0 halatuju_api`, with its own venv from v3.1.0's lock.
- the harness, run as a parent plus three child processes (old, new, new again).

The harness code lives at `halatuju_api/apps/scholarship/eval/replay/` (the `eval/` folder already holds the
reviewed dry-run precedent), so the api's code standards and tests apply to it. It is inert without the job's
settings: it refuses to start unless the read-only proof in 3.4 passes. Merging it into main changes no live
behaviour and can ride any later deploy group; the run itself does not need a deploy.

---

## 4. How to compare and classify

### 4.1 Normalising

- Each engine's answer becomes a canonical JSON record: keys sorted; amounts as 2-decimal strings; code lists
  sorted where order means nothing (the verdict's four facts keep their fixed order); free text and `params`
  replaced by a short hash; an exception becomes `{"error": "<ClassName>"}`.
- A record is keyed by (engine, case number, document number if any, month if any).

### 4.2 The four outcomes per record

| Class | Meaning |
|---|---|
| **Same** | old and new records are identical |
| **A — expected** | they differ, and the difference matches a ruling in the catalogue (4.3) |
| **B — unexplained** | they differ and no ruling matches |
| **C — could not run** | one side raised (old schema gap, refused write, refused network) |

Plus a control: **N — noise**, where "new" and "new again" differ. Any N means an engine is not deterministic.
That is a finding on its own, and those cases are left out of A/B.

### 4.3 The ruling catalogue (what makes a difference "expected")

One small file in the harness. Each entry has: an id, the citation, which engine and field it touches, and a
**narrow** test on (old value, new value, and non-personal case facts such as pathway code or degree-bound yes/no).
A broad test ("any academic change") is not allowed: it would hide a real regression. A difference that two
entries both match is listed once, under both.

Starting list, from the version notes and `docs/decisions.md` (headings named so they survive line moves):

| Id | Expected difference | Citation |
|---|---|---|
| R-TD465 | STPM, start year unknown: award RM3,000 becomes None; `course_start_unknown` yes | decisions.md "TD-465 hotfix: an unknown STPM course-start year gives NO automatic amount — 2026-11-05"; roadmap A0.1, A1.13 (TD-465 part 2: one course-start read point, `course_start.recorded_date`) |
| R-DEG7 | degree-bound student under a stale `stpm` code: award RM3,000 / RM1,000 / None becomes RM2,000; university schedule row; degree funding estimate; TVET and skills courses estimated | decisions.md "A degree student gets a degree funding estimate; every skills / TVET course is estimated — 2026-11-07" (decision 7; app 251, 278); commit `6c58efae5` (a stored STPM award keeps the STPM row) |
| R-56 | results name one look-alike letter off: Identity / Academic red becomes amber | decisions.md "Request #56 ... — 2026-11-05"; verdict version 11-05.1 |
| R-62 | a typed SPM subject not on a fully read slip: a new Academic unresolved item; English slip names fold to Malay | decisions.md "2026-11-06 — Request #62 ..."; versions 11-06.1, 11-06.4, 11-06.5 |
| R-3ROUTES | a tertiary holder's SPM slip compared with her SPM prerequisite only, not her `grades`; programme SPM bars read `spm_grades_for` | decisions.md "2026-11-06 — Three exclusive routes for SPM grades"; versions 11-06.2, 11-06.3; `shortlisting.py` change |
| R-388 | a university student owing higher results with none on file: Academic Probable becomes Unsure | decisions.md "2026-11-06 — Missing higher results cap Academic at Unsure ..."; version 11-06.6 |
| R-OWED | a degree-bound student who declared SPM only owes higher results: Academic Unsure, `higher_results_not_declared` | decisions.md "2026-11-07 — Every degree student must have higher results on file ..."; version 11-07.1 |
| R-278 | an undeclared higher upload is not compared; typo-tolerant STPM subject names | decisions.md "2026-11-07 — Undeclared higher results compare nothing; typo-tolerant STPM subject names"; version 11-07.2 |
| R-54 | a declared informal wage the STR vouches for counts toward the household total and the #54 tick | decisions.md "2026-11-08 — A declared informal wage the STR vouches for ..."; "Household income on the card ... (owner 2026-11-06)" |
| R-A28B | anomaly routing and the STR non-earner IC check add items | roadmap A2.8b (TD-111, TD-119, TD-121, CO-10) |
| R-IIUM | an IIUM English offer reads as a public-university offer (only where the rule runs on stored fields) | decisions.md "2026-11-08 — IIUM's English offer letters ..." (request #66) |

**No entry exists for A3.4, A3.6, A3.8, A3.1 or any other "moves only" refactor.** Those sprints promised no
behaviour change, so any difference in their scope is B by definition. Money writers' locking (A1.4, A1.5) changes
no amount, so it has no entry either.

R2 completes this list by reading every engine commit between the two baselines (about 40 engine-touching
commits) and every decisions.md entry dated 5 to 12 November. A commit with behaviour change and no owner ruling
gets no entry: its differences land in B for the owner to see.

### 4.4 A second lens: the record against today's rule (money and shortlist only)

Separate from the old/new comparison. For each case: the **stored** `award_amount` against
`proposed_award_amount` (new), and the stored shortlist `verdict` against `evaluate` (new). This does not prove a
regression. It answers a different question: "which money already committed, or which shortlist already stored,
would today's rule give differently?" It feeds the owner's open decision D2 (cases already given RM3,000 with an
unknown start year). It is reported in its own short table, never mixed into A/B.

We do **not** compare stored `ai_verdict_snapshot` with today's verdict as a regression test: documents were
added and re-read since each snapshot, so most differences would be new evidence, not code.

### 4.5 The report the owner reads

One page, plain English, written by the lead from the job's output. Shape:

1. **The answer in three sentences.** For example: "We ran N real cases through the old and new engines. X
   answers changed. Y of them are what you ruled; Z are not explained and are listed below."
2. **Counts table:** one row per engine family (verdict, per-document, programme eligibility, course
   eligibility, award, funding estimate, schedule, payment, sponsor balance). Columns: cases, same, A, B, C, N.
3. **A, by ruling:** one line per ruling: how many cases, and two example case numbers so the owner can open
   them in the cockpit.
4. **The B table:** case number, engine, field, old value, new value, the commit that most likely caused it, and
   the lead's first reading. Each row ends as one of: *fix the engine*, *owner rules it is right* (then it becomes
   a decisions.md entry and an A rule), or *data, not code*.
5. **C and N:** counts and engine names, with what was done about them.
6. **The second lens (4.4):** its own small table.
7. **What this does not prove:** section 6, in two lines.

The report goes to `docs/audits/2026-11-xx-a5-replay-report.md`. The raw job output stays in Cloud Logging
(30-day retention) and is not copied into the repo.

---

## 5. Size, people and steps

### Sprints

| Sprint | What | Model | Files (about) | Review |
|---|---|---|---|---|
| **R1 — harness and safety** | the parent and child runner, snapshot export and join, the five read-only layers, the socket guard, the clock pin, the log scrubber, the two-venv image recipe, the engine map with its build-time resolve check; tests on factory data (never copied production data) proving: a write is refused, a non-DB socket is refused, an error logs its class only, names and params never reach output | **Opus** (it guards production and personal data) | 12 | fresh Sonnet diff review; **Opus adversarial review of the safety layers** |
| **R2 — engines, normalising, rulings, report** | an adapter per engine in section 1; the normaliser; the ruling catalogue (4.3) completed from the commit log and decisions.md, one test per rule (a matching and a non-matching pair); the comparer; the report writer | **Opus** (money and eligibility) | 12 | fresh Sonnet diff review; **Opus adversarial review of the ruling catalogue** (is any rule too broad?) |
| **R3 — run and triage** | build the image, owner runs the job, read the output, trace each B item to a commit, write the report; any engine fix found becomes its own sprint, not part of R3 | lead, plus one Opus triage agent if B is large | 3 (docs only) | owner reads the report |

About **27 files across 3 sprints**, well inside the 40-file cap each. Targeted tests while building; the full api
suite once before R2 is merged. No live behaviour changes, so **no phone check** is needed.

### Timeline to 4 December

R1 by about 20 November; R2 by about 26 November; the run about 27 or 28 November; triage and report by
2 December. That leaves two days for any B item that needs an owner ruling.

### Owner steps (each needs the owner's yes)

1. **Create the read-only role** (one SQL block the lead writes and the owner runs in the Supabase SQL editor:
   `CREATE ROLE replay_ro ...; GRANT SELECT ...`), and put its connection string into Secret Manager. The lead
   never sees the password.
2. **Run the image build and create the job** (`gcloud` commands with `--account` and `--project` on each, given
   to the owner in full).
3. **Execute the job once** (and once more only if R3 needs a re-run).
4. **Read the report** and rule on each B item.
5. **Afterwards:** drop the role (`DROP ROLE replay_ro`), delete the secret and the job. The lead writes those
   commands too.

### Cost

Cloud Build about 2 to 4 minutes (inside the free tier). One job run about 30 minutes at 2 vCPU and 4 GB:
under USD 0.50. Artifact Registry storage for one image for a month: a few cents. **Total well under USD 1.**
No AI call, no paid API.

---

## 6. Risks, and what this replay cannot prove

### Risks and how we hold them

| Risk | Hold |
|---|---|
| A write reaches production | five layers (3.4); the database role alone refuses it |
| Personal data in logs | output is codes, amounts and hashes only; errors log class names only; a test for each |
| A too-broad ruling hides a regression | narrow rules on old value, new value and a case fact; an Opus adversarial review of the catalogue; two example cases per rule in the report |
| Load on the live database | a few connections, reads only, off-peak, `statement_timeout` set; one snapshot held for about 30 minutes |
| A long-held snapshot slows housekeeping (vacuum) | short run, off-peak; the job has a hard time limit |
| Old code meets new-shaped stored reads (documents re-read since 5 November carry newer `vision_fields` keys) | such differences show as B and are traced; the trace names "input shape, not rule" when that is the cause |
| The snapshot join does not work through the session pooler | proved in R1 on local Postgres first; fallback in 3.5 |
| Nobody reads a long B list | the lead groups B items by the commit that caused them before the owner sees them |

### What this replay cannot prove

- **Reading changes.** Anything in how a document is **read** is not replayed, because re-reading is forbidden:
  the `vision/` split (A3.1), the offer reader's campus and town lines (A2.7a), results reader `MODEL_VERSION`
  1.25.0 to 1.27.0, and the switch to Gemini 3.8 Flash (2026-11-10). Both sides use the same stored reads. Those
  changes rest on their own pinning tests and the doc-recognition eval.
- **Writers and races.** Paying, releasing tranches, withdrawing an award, QC accept and the new row locks (A1.4,
  A1.5, A1.13) are not run. Their proof is the concurrency and chain tests.
- **Permissions.** Who may do what is action 4's job (the access matrix), not this one.
- **The web.** Mirrors in the browser (`incomeWizard.ts`, cockpit display) are not run.
- **Cases we have never seen.** Real data only covers what real students did. The golden fixtures (A3.4, A3.6,
  A3.8) cover made-up edge cases; the two together are the evidence.
- **Other dates.** Each answer is at one pinned instant and two pinned payment months.
- **Ranking** of courses (the Matric and Form 6 ranking fix of 10 November) is out of scope: it changes order, not
  eligibility or money. It can be added as one more adapter if the owner wants it.
- **Whether a ruling was right.** An A item only shows the code does what the owner ruled.

---

## 7. Owner decisions needed

1. **Where it runs.** Read-only Cloud Run job against production (option i). *Recommended:* yes. A local or
   restored copy puts a full set of personal data somewhere new, and fake names would change identity results.
2. **A read-only database role** (`replay_ro`, SELECT only), created by the owner and dropped after the run.
   *Recommended:* yes. It is the one layer the database enforces itself; without it the job relies on code-level
   guards only.
3. **Case numbers in the report.** The report names application ids (as `decisions.md` already does), never
   names. *Recommended:* yes, so the owner can open a B case in the cockpit; a hash would make each one a lookup.

Baseline `v3.1.0` and the case scope (every real case past draft, all gifts and intakes) are the lead's
recommendation in sections 2 and 3; the owner may change either.

> **OWNER RULING 2026-11-13: APPROVED.** The owner said "proceed" to "A5: yes to all". Decisions 1 to 3 are
> yes, and the baseline and case scope stand. The owner still creates and drops `replay_ro`, builds and runs
> the job, and reads the report (R3); none of that happens without a fresh yes at the time.
