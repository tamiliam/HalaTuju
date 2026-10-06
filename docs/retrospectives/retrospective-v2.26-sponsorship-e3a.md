# Retrospective — v2.26.0 · Phase E Sprint E3a: sponsor wallet + match/consent (backend)

**Date:** 2026-06-01
**Scope:** The sponsorship match — a sponsor funds an anonymous student, the student/guardian accepts — built on
dummy data, behind the pool flag, with **no real money** (donations mocked; disbursement + tranches deferred). Money
is modelled as a **ledger**, not a custody/refund flow.

## What Was Built

- **Wallet/donation ledger** (`sponsorship.py`): `sponsor_balance` = total `Donation`s − `Sponsorship`s that still hold
  (offered/active). A lapsed/cancelled allocation stops holding → the amount returns to the balance to redirect (no
  money leaves myNADI; never a bank refund).
- **Models** (migration `0034`, migrate-first via MCP, prod-verified): `Donation`, `Sponsorship` (offered → active /
  lapsed / cancelled, amount, consent FK, accept deadline), `ScholarshipApplication.award_amount`, new `sponsored`
  status. DB partial-unique `uniq_holding_sponsorship_per_app` = one holding sponsor per student.
- **Flow:** admin sets the award amount → sponsor (balance ≥ amount) funds in full → `offered` → student/**guardian**
  (under-18 gate, reusing `record_consent`) accepts within the deadline → `active`, app `sponsored`, leaves the pool;
  decline/lapse → amount back to balance.
- **Endpoints:** sponsor wallet/donate(mock)/fund/sponsorships/cancel (flag + approved-sponsor gated); student
  `scholarship/award/` GET + accept/decline; admin award-amount + `admin/sponsorships/` oversight.
- **Anonymity both ways, leak-tested:** `SponsorSponsorshipSerializer` shows the anon student card (no identity);
  `StudentAwardSerializer` has **no sponsor field**; admin (back office) sees both. 17 tests.

## What Went Well

- **The pause-and-reframe loop produced a much cleaner, safer design.** I'd scoped E3 from the roadmap's "express
  interest" sketch (1:1, no money) and stubbed a `Sponsorship` model; the user paused and reframed it into a
  crowdfunding-then-wallet model. Re-planning *before* committing turned "hold sponsor money + refund to bank"
  (custody — regulated) into "**final donation to myNADI + an internal directed-giving balance**" (bookkeeping) —
  which sidesteps the fund-custody/refund regulatory problem almost entirely. Only one model stub was thrown away.
- **Money as a ledger, not a mutable balance.** Balance = donations − holding allocations, so "release on lapse" is
  just a status change (the allocation stops counting) — no refund transaction, no drift, fully auditable.
- **Reused the safety machinery.** Award acceptance reuses `is_minor` + `record_consent` (guardian gate), and the
  anonymity guarantee reuses the E2 allowlist card; the student-side serializer simply has no sponsor field.
- **Mocked money let the whole flow land + test on dummy data** without touching a regulated rail; toyyibPay +
  disbursement are a clean, separate, gated follow-on (TD-075).

## What Went Wrong

1. **I started designing/coding E3 from the roadmap sketch before confirming the money model with the user.**
   - *Symptom:* a `Sponsorship` stub was written (1:1, no amount) that had to be reverted and rebuilt around the wallet
     model.
   - *Root cause:* the roadmap had *deferred* money to "a later phase", so I assumed E3 = the match with no money — but
     the user's actual intent for E3 included the funding. For a phase whose value is fundamentally financial, the money
     model is the first thing to pin down, not an afterthought.
   - *System change:* lesson added — **for any sprint that touches money or legal/regulatory ground, surface that
     dimension and confirm the model with the user before designing the schema.** (The user's "pause" caught it with
     minimal waste; the lesson is to ask first rather than rely on the pause.)

## Design Decisions

(Logged in `docs/decisions.md`.) Wallet/donation model: (1) a donation is **final** (no bank refund) — "return to
balance" means redirect within the platform; (2) **balance = donations − holding allocations** (a ledger, not a mutable
field + refunds); (3) **1:1 full-or-nothing now, many-sponsor plumbing underneath**; (4) **anonymity both ways**
(student never sees the sponsor either); (5) **money is mocked** in E3a — real toyyibPay + disbursement + tranches are
a later, lawyer + gateway-gated slice (TD-075).

## Numbers

- **Tests:** 1452 backend pytest (+17 `test_sponsorship.py`) · 183 jest · golden masters intact · `manage.py check` clean.
- **Migration:** `scholarship/0034` (additive `award_amount` + new `sponsor_donations`/`sponsorships` tables + RLS,
  migrate-first via MCP, prod-verified).
- Backend only; flag OFF; mocked money — dark deploy. ~12 files.
