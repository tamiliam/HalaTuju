# Retrospective — Platform P4b: the credit endpoints, and identity on the chain

**Date:** 2026-07-26
**Sprint:** P4b of `docs/plans/2026-07-26-programme-layer-roadmap.md`
**Branch:** `feat/p4b-credit-endpoint` (worktree — another agent was working the same repo)
**Result:** 4678 pytest passed, 0 failed (baseline 4635). **Not deployed** — migration `0125` is
migrate-first and has not been applied.

## What was built

Three org-fenced admin endpoints that drive the P4a chain (record → sign → cancel), the typed-name
match and role gates that close TD-176, and a `visible_donations` seam that keeps unconfirmed money
off the sponsor's own surfaces.

## What went well

- **Re-scoping the sprint on evidence rather than on the plan.** The roadmap bundled the credit
  endpoints with programme-grouping `sponsor_statement`. Checking the consumers showed the statement
  feeds the sponsor account page, making it a sponsor-facing layout change that owes a Stitch pass —
  and that grouping is a visual no-op today, because every live sponsor holds exactly one membership.
  Splitting it kept this sprint backend-only and free of an FE deploy, at the cost of nothing anybody
  can currently see.
- **Verifying live roles caught the gate before it was written — again.** The natural gate for "an
  admin records a credit" is `org_admin`. Poongulali Veeran, who does the work, is a plain `admin`.
  This is the second sprint running where querying prod rather than trusting the note prevented
  locking out the actual operator.
- **The org-fence guard failed first, exactly as budgeted.** `docs/lessons.md` says to expect it, so
  the four unclassified classes were a checklist item rather than a surprise.

## What went wrong

- **P4a shipped unconfirmed money onto sponsor-facing surfaces, and I did not catch it in P4a.**
  *Symptom:* `sponsor_statement`, the sponsor wallet endpoint and `sponsor_programme_balances` each
  read `sponsor.donations` with no status filter. After P4a a `draft` credit — money nobody has
  signed off, possibly a typo — appeared on the sponsor's own giving statement as money we hold, and
  could conjure a wallet for a programme they had been given nothing in. *Root cause:* P4a reasoned
  about the credit chain as a **spend** control and proved the right thing about it (`is_spendable`,
  tested from four angles) — while *visibility* is a second, independent property that nothing
  asserted. "Unspendable" and "invisible" are different guarantees, and I checked only the first.
  This is the **P3 lesson recurring in a new domain**: P3's finding was that fencing the API surface
  is not fencing the data, because the same rows reach the same audience through several channels. I
  wrote that lesson, then two sprints later shipped the same shape of bug against money instead of
  students. *Fix:* one `visible_donations` seam (the `pool.for_sponsor()` pattern), all three
  surfaces narrowed through it, and a source guard that fails CI if a fourth reads donations
  directly. The generalisation — *when you add a state that means "not real yet", enumerate what
  displays the thing, not just what spends it* — is now in `docs/lessons.md`.
- **I stated "no migration" in the sprint plan and then needed one.** *Symptom:* the plan told the
  owner P4b was schema-free; identity work then required three email columns. *Root cause:* I scoped
  the sprint from P4a's column list without asking what a *correct* distinctness rule needs — and
  the answer (identity, not name) is only obvious once you look at the admin table and find two
  active accounts sharing the name "Ve. Elanjelian". *Fix:* the migration is additive, touches no
  existing row and moves no balance, and the reason is recorded in its docstring. But the estimate
  was wrong because I costed the change before checking the data it operates on.

## Design decisions

Recorded in `docs/decisions.md` (2026-07-26): one mirrored `sign_admin_credit` rather than three
step-functions; email as the identity key; cancel-not-delete for an unconfirmed credit; and the
deferral of the programme-grouped statement.

## Numbers

4678 pytest (from 4635: +19 net in the rewritten `test_wallet_credit.py`, +24 in the new
`test_credit_endpoints.py`). One additive migration. No frontend files changed.

## Follow-ups

- **Apply migration `0125` migrate-first, then deploy.** Post-check: all three columns empty on
  every row, and the confirmed-donation total per programme unchanged.
- **P4b-ii** — programme-grouped `sponsor_statement`, when a second programme makes it visible.
  Needs a Stitch pass first.
- **P2b** — `PaymentRun.programme`.
- Routing PF-1 (date-parked ~May/June 2027), reviewer programme scoping, Phase 2 S7–S9, Sprint E.
