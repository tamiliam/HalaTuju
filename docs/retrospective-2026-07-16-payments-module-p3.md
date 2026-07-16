# Retrospective — Payments module Sprint P3 (production cutover) — 2026-07-16

Plan: `docs/plans/2026-07-16-payments-module-plan.md` (§8 Sprint P3). This closes the 3-sprint
Payments module (P1 ledger + backfill, P2 API + UI, P3 cutover) with the feature's single deploy.

## What Was Built / Done

- **D10 carry closed** — a per-language test (`test_sponsorship.py`) now guards the Vircle Wallet-ID
  mention in the award-offer email. The copy was already present in en/ms/ta (added in P2); the gap
  was only that nothing locked it in. Committed as its own change so it rode the same deploy.
- **Migrate-first (`scholarship/0101`)** — applied to prod via the Supabase MCP before the push, in
  one transaction: the two additive columns (`payment_credit`, `vircle_id`) backfilled onto the 143
  existing rows then DB-default-dropped (Django's Postgres pattern); `payment_runs` +
  `payment_run_items` with the exact Django-generated index/constraint names; RLS enabled with no
  policies (deny-by-default, mirroring `disbursements`); and the `django_migrations` ledger row.
- **One deploy** — the three held commits (P1 `fcbefe08`, P2 `2049d57a`, carry `22615bb3`) pushed
  together. Both Cloud Builds SUCCESS. Smoke: live `payment-runs` endpoint = 401 (not 500), web
  `/admin/payments` route serves.
- **Live backfill** (`import_vircle_csv` on prod via the session pooler): 30/30 matched, 30 Vircle
  IDs stamped, two completed backfill runs (26 released Disbursements = RM5,400; the two RM300
  overpayments preserved as history), three derived credits (100/100/200).
- **Verification (read-only)** — a simulated 1 Aug 2026 run: 28 payable, 0 greyed, 25×RM200 +
  app 10 RM100 + app 18 RM100 + app 61 RM0. No draft persisted — the real draft is left for the
  owner/admins to create in the UI.

## What Went Well

- **Migrate-first held the line.** The whole reason P1/P2 were kept unpushed for a sprint was the
  deploy hazard (code referencing columns not yet on prod → 500s). Applying `0101` first, then
  pushing, then seeing 401-not-500 on the live endpoint, confirmed the discipline worked end to end.
- **Derived credits reproduced the plan exactly** with zero hard-coded app IDs — the dry-run and the
  live run both produced 100/100/200 for apps 10/18/61 purely from the CSV amounts vs `MONTHLY_RATE`
  and the reporting dates.
- **Owner-gated STOP respected.** The dry-run was shown before any write; the live backfill only ran
  on explicit go-ahead.

## What Went Wrong

1. **`sqlmigrate` emitted SQLite table-rebuild DDL, not Postgres `ALTER`.** Symptom: the local
   `python manage.py sqlmigrate scholarship 0101` produced a full `CREATE new__… / INSERT … / DROP /
   RENAME` sequence — destructive-looking and wrong for prod. Root cause: the local dev DB is SQLite,
   whose backend can't `ALTER TABLE ADD COLUMN` in place, so Django rebuilds the table; prod is
   Postgres, where the same AddField is a simple `ADD COLUMN`. Fix / system change: for HalaTuju,
   never trust `sqlmigrate` output for the prod DDL — hand-write the Postgres DDL and mirror an
   existing sibling table's exact types (`disbursements`) via `information_schema`. Captured in
   `docs/lessons.md`.
2. **First dry-run attempt failed on host resolution, then on console encoding.** Symptom: `could
   not translate host name "db.…supabase.co"`, then `UnicodeEncodeError` on the `→` in the credit
   preview. Root causes: (a) the service's direct `DB_HOST` is IPv6-only and unroutable locally —
   the documented fix is the `aws-1` session pooler (supabase.md §8); (b) Windows console defaults to
   cp1252. Fix: used the pooler override + `PYTHONIOENCODING=utf-8`. Both are already documented; the
   lesson is to reach for supabase.md §8 first rather than debugging DNS.

## Design Decisions

- **No persisted draft run created during verification.** The plan's acceptance check ("a draft
  1 Aug run shows …") was satisfied by a read-only `eligible_rows`/`default_amount` computation
  rather than by creating a `PaymentRun`, because the owner wants to create the draft themselves in
  the UI (and may cancel/recreate as a test). Persisting one would leave a stray draft and bump the
  reference sequence. Trade-off: no live-DB draft row to eyeball, but the amounts are identical to
  what the UI will compute (same service functions).
- **Backfill run before the owner's UI test (owner's call).** Without the backfill, a UI draft run
  shows everyone greyed "no Vircle ID" and RM0 — the mechanism works but the amounts are invisible.
  The owner chose to run the backfill first so the test shows real figures. Trade-off recorded for
  the owner: the backfill writes permanent Disbursement/run rows + credits — "reversing" it is DB
  surgery, not a UI Cancel.

## Numbers

- Migration: `scholarship/0101` (2 columns + 2 tables + RLS), applied migrate-first, Security
  Advisor clean of new ERRORs/WARNs.
- Backfill: 30 Vircle IDs, 2 completed runs, 26 disbursements, RM5,400, 3 credits (100/100/200).
- 1 Aug 2026 simulation: 28 payable (25×200 + 2×100 + 1×0), 0 greyed.
- Tests at close: full suite green (P2 baseline 3896 pytest + 573 jest; P3 added 1 guard test).
