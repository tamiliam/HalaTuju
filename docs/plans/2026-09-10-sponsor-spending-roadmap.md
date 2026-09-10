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

## S1 — Read a spending report correctly (from a local file)

**Goal.** Turn a Vircle report file into stored transactions, joined to the right student, with no
double-counting — proven against all eight real reports.

**Scope.**
- Models `BursarySpendTxn` + `MerchantCategory` (per the July brief, plus a `decided_by` column so
  §4c's four rungs are distinguishable from day one — that is why S3 needs no migration).
- `apps/scholarship/spending_import.py` — header resolution by NAME across the three known variants;
  the amount parser (number **or** `"RM26.90"`); `transaction_id` dedup; `TX Type`/`Status` gating.
- The wallet join: `wallet_id → ScholarshipApplication.vircle_id`; **a populated `Child User` means
  the child is the spender** (28 real rows).
- `ingest_spending --file <path> [--apply]`, report-first.
- Fixtures shaped like each of the three real header variants, with invented names and wallets.

**Acceptance.** All eight real reports ingest to **1,368 transactions / RM10,029.03**, matching the
measured figures in brief §0b. Re-running is a no-op. An unknown header **fails loudly**. A repeated
`transaction_id` whose fields DISAGREE is reported, never silently dropped. Unknown wallets listed.

**Complexity: HIGH.** ~14 files. **Has a migration — migrate-first, two new tables, RLS + one
`service_role` policy each.** **No sponsor-visible change.**

---

## S2 — Fetch the reports from Drive, weekly

**Goal.** The same ingest, fed by Drive instead of a path, on a schedule.

**Scope.**
- `VIRCLE_SPENDING_FOLDER` setting (default matching the live shape — see brief §3).
- `sheets.py`: list a folder's files + download one, reusing `_drive_for_upload` + `_find_folder_path`
  and the already-granted `drive` scope.
- `--drive` mode on the command; register in `CronRunView.JOBS`; a weekly Cloud Scheduler job.

**Acceptance.** A `--report` run on the LIVE service lists the eight files and re-derives the same
totals. Ingest is idempotent across runs. A missing folder logs and does nothing.

**⚠ EXTERNAL BLOCKER: this cannot be verified locally.** The proof is a live report-mode run.
**⚠ Do not let a Drive failure break anything** — best-effort, the same contract as the guide fetch.

**Complexity: LOW–MEDIUM.** ~5 files. **No migration. No sponsor-visible change.**

---

## S3 — Sort the spending

**Goal.** Every transaction carries one of the ten categories, decided by brief §4c's four rungs.

**Scope.**
- `apps/scholarship/spend_category.py` — the ten-code vocabulary; rung 1 (`duitnow_type`), rung 2
  (keyword rules), rung 3 (the spend-pattern inference **per transaction**, with the RM20 ceiling).
- Rung 4: a batched Gemini call over **merchant name strings only** — no amount, no student, no date
  — through the existing seam, metered by `usage_context`, answers outside the vocabulary discarded.
  A name once answered is stored and never asked again.
- Wire into the weekly job, after ingest.

**Acceptance.** Over the real corpus: rung 2 places ~100 merchants, rung 3 ~62 merchants / 681 rows.
**Two regression tests pinned by name** — `AL HUDHA ENTERPRISE`'s single RM200 and
`TEGUH ENIGMA (MATRIK 1)`'s RM119.50 must NOT be food (brief §4c). An `owner` verdict survives a
re-run. Rung 4 is never asked about a merchant already decided.

**Complexity: MEDIUM–HIGH.** ~10 files. **No migration.** **No sponsor-visible change.**

---

## S4 — The officer view, and the correction

**Goal.** The owner can see every transaction, see what the AI decided, and correct it — **before a
sponsor sees anything**.

**Scope.** An admin surface: per-student spending, the **merchant-level** table (oversight is their
job), this week's AI decisions, unknown wallets, and a one-click `owner` override that outranks every
rung. Reuses the existing admin gates.

**Acceptance.** Correcting a merchant changes the totals on a re-read and is never overwritten.
Person-to-person transactions are flagged. Nothing here is reachable by a sponsor.

**Complexity: MEDIUM.** ~9 files. **No migration.**

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
1. **The 2026-07-19 report is missing.** A week with no spending, or an export nobody ran? Worth
   asking Vircle, because the answer decides whether a gap is an error or normal.
2. **How far back do we ingest?** All eight files, or from a chosen date?
3. **Does an unknown wallet need chasing?** S1 lists them; nothing acts on them.

---

## Deliberately NOT in scope

Vircle API integration (none exists). Per-month views (owner ruled all-time, weekly refresh).
Merchant names, dates or times reaching a sponsor — ever. Any consent-version change (§4: the live
consent already covers an anonymised summary).
