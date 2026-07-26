# Programme Layer — Roadmap (Organisation → Programme → Year → award)

**Status:** owner-approved model, 2026-07-26. Sprint briefs below are ready for `sprint-start.md`.
**Supersedes:** the sequencing of Phase 3 in `docs/plans/2026-07-14-platform-roadmap-draft.md` (see "How this re-bases the platform roadmap" below). The PRD's §2 org/module model still stands; its implicit assumption that a tenant runs exactly ONE programme does not.
**Decision records:** `docs/decisions.md`, five entries dated 2026-07-26 (hierarchy; funds/sponsor attachment; award vocabulary; gift-not-loan; reviewer scoping).

---

## Why now — the scenario that forced it

Two prospects arrived in the same week:

1. **Inspire Society** (`inspiresociety.org`) — financial assistance for STPM students. A separate legal entity → a genuine second **Organisation**, and the trigger for a DPA (which makes Sprint E erasure hard-blocking, not conditional).
2. **BrightPath Sabah** — a benefactor found by Suresh, ~**RM100,000**, targeting Sabah students. Same organisation, same team, same brand; different rules and a **restricted fund**. This is a second **Programme**, not a second Organisation.

The owner's model (stated 2026-07-26, mirroring Supabase's Organisation → Project shape):

> **HalaTuju → Organisations → Programmes/Projects → Year (intake) → the student's individual award**

Sponsors onboard and are accepted **per Programme** — "and that is not a given". Funds given to one programme are **not visible in another**.

### Terminology (settled 2026-07-26 — read this before building)

"Award" was doing two jobs and briefly caused a false disagreement about the ordering of the levels. Settled:

| Term | Means | Durable? |
|---|---|---|
| **Programme** | **the gift offering itself** — "the BrightPath Bursary", "the Sabah Bursary". Holds the rules, the amounts and the fund. | **Yes — never lapses** |
| **Year (intake)** | the annual cohort of students entering that gift | No — cycles annually |
| **the student's individual award** | one student's grant: application → award → payment | leaf |

**One gift per programme** (owner ruling, 2026-07-26). A Programme is not a container *for* a gift — it **is** the gift. BrightPath Bursary does not lapse; only its intakes cycle. An Award level between Programme and Year was considered and rejected: every known case (flagship, Sabah, Inspire) has exactly one offering per programme, and a level that distinguishes nothing must still be carried by every query, fence check and config screen.

**Consequence for the build:** "create a programme and the bursary" is **ONE** durable object (the Programme), followed by opening an **intake Year** beneath it. Do not build two creation steps for the gift itself. The award *noun* remains per-organisation wording (see the vocabulary decision record) — "bursary", "scholarship" or "assistance" is what a Programme is *called*, never what it *is*.

## What the schema conflates today

`ScholarshipCohort` is doing two jobs at once: it is the **programme** (rules, funding envelope, eligibility thresholds) *and* the **intake year** (`b40-2026`, `year=2026`). One programme hides the conflation; two end it.

| Level | Model | State |
|---|---|---|
| Platform | the deployment | ✅ |
| Organisation | `courses.PartnerOrganisation` — **the security fence** | ✅ BrightPath = org #11 |
| **Programme** — *the durable gift* | **new** | ✗ this roadmap |
| Year (intake) | `scholarship.ScholarshipCohort` | ✅ but doing double duty |
| The student's individual award | `ScholarshipApplication` → award → `PaymentRun` | ✅ 143 applications |

Rule **defaults on the Programme, overrides on the Year**. The cohort tunables (`min_spm_a_count`, `min_spm_bplus_count`, `min_stpm_pngk`, `income_ceiling`, `per_capita_ceiling`, `funding_envelope`, the delay/SLA fields) become overrides — nullable, falling back to the programme.

## Production state at planning time (verified 2026-07-26)

| Fact | Value | Why it matters |
|---|---|---|
| Cohorts | **1** (`b40-2026`, org #11, 143 apps) | The layer lands against a single row |
| `is_open` | **false** | **Nothing is accepting applications** — the routing fix (below) can land before anything reopens |
| Sponsors / donations | 9 / 6, RM172,000 recorded | Small enough to backfill cleanly today |
| Staff | 21 | All keep working unchanged (NULL = org-wide) |
| Documents | keyed by org **id** (`storage.build_doc_key`) | **No document re-keying** — the programme layer does not touch storage keys |

This is the cheapest this change will ever be.

---

## Pre-flight (must land before, or inside, Sprint P1)

**PF-1 — Cohort routing has no organisation context.** `services.resolve_open_cohort()` (`services.py:188`) returns *the single most recent active+open cohort platform-wide*, and the public "are applications open?" endpoint (`views.py:103-115`) does the same. With two open programmes, a student arriving without an explicit cohort code is silently routed into whichever sorts first by `-year, code` — i.e. into the wrong organisation's fence. **Not currently live** (`is_open = false`), and it **must not reopen until this is fixed**. Folded into Sprint P1.

**PF-2 — Module flags contradict production.** Migration `0098` seeded BrightPath `module_payout = False`, but the payout stack (payments, Vircle, contracts, the Sprint-14 finance chain) shipped afterwards and `VIRCLE_SETUP_ENABLED = 1` on the live service. The four flags (`models.py:451-454`) are currently **read by nothing**, so this is latent — but any sprint that starts enforcing them must reconcile first, or BrightPath's payout surfaces go dark in production. A data migration, applied migrate-first and verified, **before** any enforcing code ships. (Carried from Sprint 10b of the platform roadmap; not otherwise part of this layer.)

---

## Sprint P1 — The Programme layer

**SPLIT 2026-07-26 into P1a (structural) and P1b (behaviour-sensitive).** The original single
sprint mixed two very different risk profiles: creating the level and hanging existing data off it
is provably behaviour-neutral, whereas moving the rule tunables up to the programme changes the
inputs to the verification engine, and routing changes where a live applicant lands. Splitting
keeps the foundation shippable without putting either of those in the same review.

### P1a — Structural foundation — ✅ **SHIPPED 2026-07-26 (migrations APPLIED + verified on prod)**

Delivered: `Programme` model (`scholarship_programmes`); `ScholarshipCohort.programme`;
`ScholarshipApplication.programme` denormalised in `save()` (set-once, both copies derived in a
single query on the uncached path); migrations `0118` (schema, with hand-written Postgres DDL in
its docstring) + `0119` (seed Programme #1 from the org's own branding, backfill cohort + 143
applications, both reversible); `tests/test_programme_layer.py` (16 tests). **Full suite green:
4593 passed, 0 failed.** Fence-proof suite and `FENCED_OR_EXEMPT` map pass **unmodified**.
Serializers use explicit field lists → **no API surface change**. No admin surface needed
(cohorts were never in Django admin). CHANGELOG written.

**✅ PROD MIGRATE-FIRST DONE 2026-07-26** (Supabase MCP, per the `2026-07-15-sprint1-migrate-first.md`
runbook pattern). Pre-checks clean (no prior migration rows, no table, last scholarship migration
`0117` → no sequence gap). Post-checks verified: **1 programme** (`brightpath-flagship | BrightPath
Bursary | Bursari BrightPath | org=11`), **0 cohorts unassigned**, **143/143 applications carrying
it**, **0 drifted** (`programme.organisation` agrees with `owning_organisation` on every row), RLS
enabled with the sibling-matching single `Backend service role only` policy, both
`django_migrations` rows present. Supabase security advisor: the new table appears in **neither**
the `rls_enabled_no_policy` nor the anonymous-access list. Retro:
`docs/retrospective-2026-07-26-platform-p1a-programme-layer.md`.

**▶ DEPLOY: not required by this sprint** — nothing reads the new column, and the schema is ahead of
the code (the safe direction: additive columns the live code ignores). The next functional push
carries it. **Owner-gated, as every HalaTuju deploy is.**

### P1b — Rule defaults + routing + reviewer scoping (NOT started)

- **Goal:** Move the rule tunables up to become programme-level defaults with per-intake overrides, make routing programme-aware, and add reviewer programme scoping.
- **Scope:**
  - Rule-default columns on `Programme` mirroring the cohort tunables; cohort tunables become **overrides** (nullable, resolved programme → cohort-override). **Behaviour-sensitive — these feed the verification engine.**
  - **PF-1 routing:** `resolve_open_cohort()` takes a programme (or an org+programme pair); the public open-check becomes programme-aware. No implicit "most recent open cohort anywhere".
  - Reviewer scoping: nullable `programme` on `PartnerAdmin`, **NULL = organisation-wide** (see decision record). Assignment lists filter by the application's programme when the reviewer is bound. `org_admin` / `finance` unaffected.
  - Also worth picking up: `management/commands/bursary_e2e.py:142` sets `cohort.owning_organisation` but not `programme` — harmless today (nullable, dev-only command) but it should set both once routing reads the column.
- **Migrations:** 1–2 additive (tunable columns on `Programme`, `programme` on `PartnerAdmin`). **Migrate-first**, per the project runbook.
- **Note:** Sabah does **not** need the rule-defaults half — a new programme's first intake can author its thresholds directly on its own cohort, which already carries every tunable. P1b's defaults earn themselves at Sabah's *second* intake.
- **Test plan:** programme→cohort→application chain resolves; the drift guard catches a mismatched denormalised programme; routing sends an applicant to the named programme and **never** to another organisation's open cohort; a programme-bound reviewer sees only that programme's assignable cases while a NULL reviewer is unchanged; all 143 existing applications resolve to Programme #1; the org fence suite stays green untouched.
- **Risk + mitigation:** *Risk:* the org fence is the proven wall and this adds a second dimension beside it. *Mitigation:* programme is a **narrowing inside** the org filter, never a replacement — `_org_scoped` / `_org_allows` keep their current semantics and gain no programme logic; programme filtering is applied on top, and the existing fence-proof suite must pass unmodified.
- **How we know BrightPath still works:** one programme, one cohort, 143 applications — every query returns exactly what it does today; `is_open` stays false throughout.
- **Complexity:** Medium–High. ~20 files.

## Sprint P2 — Funds per Programme

**SPLIT 2026-07-26 into P2a (sponsor wallet) and P2b (payment runs).** The original scope bundled
the sponsor wallet with `PaymentRun.programme`. Payments is a **live** module — prod holds an open
draft run (PR-2026-08-01) and the Sprint-14 maker-checker chain runs through it — so changing
payment-run eligibility does not belong in the same sprint as a wallet rewrite. The wallet is the
piece Sabah actually needs; payment-run scoping is reporting hygiene and can follow safely.

### P2a — The sponsor wallet becomes per-programme — ✅ **SHIPPED 2026-07-26 (migrations APPLIED + verified on prod)**

Delivered: `Donation.programme`; `sponsor_balance(sponsor, programme)` with **programme required —
no default**, so forgetting it is a `TypeError` rather than a silent cross-programme read;
`sponsor_programme_balances()` and `sponsor_available_total()` (display only, documented as never a
spend authority); all seven call sites updated — the four spend paths (`fund_student`,
reinstatement, `standing_gift.matching_gifts`, batch award) authorise against **the programme of the
student being funded**, the display paths use the total. Migrations `0120` (schema, with hand-written
Postgres DDL) + `0121` (backfill, with a no-money-moved invariant). New
`tests/test_programme_funds.py` (11 tests) plus a **source guard** asserting no spend path consults
the cross-programme total — the same class of mechanical check as the org-fence static guard.

**✅ PROD MIGRATE-FIRST DONE 2026-07-26.** Pre-check captured the baseline (6 donations,
**RM172,000.00**; last migration `0119`, no gap). Post-check confirmed the **no-money-moved
invariant held exactly**: 6 donations / **RM172,000.00** after, **0 unattributed**, all under
`brightpath-flagship`, **0** attributed to the wrong organisation, both `django_migrations` rows
present. Retro: `docs/retrospective-2026-07-26-platform-p2a-funds-per-programme.md`.

**▶ DEPLOY: still not required.** Schema is ahead of code on both P1a and P2a — the safe direction.
The next functional push carries them together. Owner-gated, as every HalaTuju deploy is.

### P2b — Payment runs carry their programme (NOT started)

- **Goal:** A payment run carries its programme, so a run can never pay students from more than one gift and a benefactor can be reported to per programme.
- **Scope:** `PaymentRun.programme` FK (additive, nullable → backfill → read); `payments.eligible_rows` narrows by programme alongside its existing org filter; the funding summary becomes programme-aware. **The Sprint-14 maker-checker chain is untouched** — only the run's candidate set narrows.
- **Migrations:** 1 additive + 1 data.
- **Test plan:** a run cannot include an application from another programme; the existing 139 payments + fence tests pass unmodified; the open draft run is unaffected by the backfill.
- **Risk + mitigation:** *Risk:* prod holds an OPEN DRAFT run (PR-2026-08-01) and this is the live payout path. *Mitigation:* additive-then-read, backfill the existing run to the flagship explicitly, and verify the draft's item set is identical before and after.
- **Complexity:** Medium. ~10 files.

**Owner gate — RESTATED 2026-07-26, this supersedes the earlier technical-only wording.** The
RM100,000 is a **possibility, not a commitment**. Nothing is inked and no money has moved. It is
**not** to be recorded until **BOTH** conditions hold:

1. the **Sabah programme is inked** (agreement signed), and
2. the **money has actually changed hands** (funds in the Foundation's account, with a bank
   reference to cite).

Shipping P2a, P4a or P4b does **not** satisfy either — those only make the recording *expressible
and auditable* when the day comes. Until both hold there is nothing to ring-fence, because there
is nothing to record. **Do not create a Sabah `Programme`, membership or credit row in
anticipation** — a seeded-but-unfunded programme is indistinguishable, downstream, from a real
one, and it would put a fictitious restricted balance into a financial surface.

## Sprint P3 — Sponsor Programme membership — ✅ **SHIPPED 2026-07-26 (migrations `0122`+`0123` APPLIED + verified on prod, DEPLOYED)**

Shipped as scoped, with one addition the plan below missed: the **weekly digest and the real-time
alert** (`sponsor_notifications.py`) selected from the unfenced queryset and had to be narrowed
too — fencing the API surface alone would have leaked, by email, that other programmes' students
exist. A source guard now asserts every sponsor-facing pool read AND both notification paths
narrow by membership. Prod verify: 9 sponsors → 9 memberships (approved 8, rejected 1),
**0 status mismatches**. The sponsor-facing programme picker is **deferred** — every live sponsor
holds exactly one membership, so there is nothing to pick between until Sabah opens.

- **Goal:** A sponsor's vetting and acceptance attach to a programme; the anonymised pool shows only the programmes they are accepted into.
- **Scope:**
  - `SponsorProgrammeMembership` (sponsor, programme, status `pending`/`approved`/`rejected`, vetted_by, timestamps) — the sponsor ACCOUNT stays platform-level.
  - Vetting UI and the pool feed (`pool.py`, `sponsor_feed.py`) filter by approved memberships.
  - Backfill: the 9 existing sponsors get a membership row against Programme #1 mirroring their current status — no sponsor loses access.
  - Sponsor-facing programme picker where they hold more than one membership (same pattern as the staff organisation switcher).
- **Migrations:** 1 model + 1 data. **Test plan:** a sponsor approved for Sabah sees no flagship students and vice versa; a pending membership grants nothing; the 9 backfilled sponsors see exactly what they see today; anonymity assertions in the existing sponsor suites stay green.
- **Risk + mitigation:** *Risk:* the pool is the platform's strictest privacy surface (permanently anonymous, both ways). *Mitigation:* membership filtering is additive to the existing anonymity allowlist — the allowlist is not touched, and its tests must pass unmodified.
- **Complexity:** Medium. ~12 files.

## Sprint P4 — Org-admin wallet credit (off-platform gift)

**SPLIT 2026-07-26 into P4a (record + chain) and P4b (endpoint + statement).**

### P4a — the credit record and its sign-off chain — ✅ **SHIPPED 2026-07-26 (migration `0124` APPLIED + verified on prod, DEPLOYED)**

`Donation` gains `source` / `external_reference` and the chain (`draft → admin_signed →
[finance_checked] → confirmed`), driven by `sponsorship.record_admin_credit` /
`sign_admin_credit` / `finance_check_admin_credit` / `confirm_admin_credit`. Calls the EXISTING
`payments.finance_check_required()` — so retroactive arming and graceful degradation are
inherited, not reimplemented, and both are pinned by tests. Only a `confirmed` credit raises
spendable balance. Defaults (`legacy` / `confirmed`) leave every existing balance unchanged, so
**no data migration**. Migration `0124`. 19 tests + two source guards. Full suite 4635 green.

### P4b — the credit endpoints + identity on the chain — ✅ **CODE COMPLETE 2026-07-26** (migration `0125` NOT yet applied; branch `feat/p4b-credit-endpoint`)

**SPLIT on investigation.** P4b as scoped bundled the credit endpoints with programme-grouping
`sponsor_statement`. The grouping is consumed by the sponsor account page — a **sponsor-facing
layout change** owing a Stitch pass — and is a **visual no-op today** (every live sponsor holds
exactly one membership, so the grouped page renders what it renders now). It is deferred to
**P4b-ii**, to be designed when a second programme makes it visible.

Delivered: three org-fenced endpoints (`credits/` list+record, `<pk>/sign/`, `<pk>/cancel/`);
**TD-176 closed** — one `sign_admin_credit(credit, admin, typed_name)` mirroring `payments.sign`,
with the typed-name match and the maker `admin` / checker `finance` / approver `org_admin` gates,
placed in the SERVICE rather than the endpoint so a shell caller cannot bypass it; distinctness
re-keyed onto **email** (migration `0125`) because prod carries two active admins sharing the name
"Ve. Elanjelian". **Also fixed a P4a defect the channel sweep found:** draft and cancelled credits
were visible on the sponsor's own statement and could conjure a wallet — all sponsor-facing reads
now narrow through `sponsorship.visible_donations`, with a source guard. 4678 pytest.

**▶ AT DEPLOY: apply `0125` migrate-first, THEN merge/push.** Post-check: all three email columns
empty on every row; confirmed-donation total per programme unchanged.

### P4b-ii — programme-grouped statement (DEFERRED, trigger-parked)

The admin HTTP surface to drive the chain, and `sponsor_statement` grouped by programme (it
already renders both ledgers). Returns (lapsed/cancelled allocations) must show as their own
entries, not a silently shrinking total.

**Why it is worth doing, stated accurately:** every wallet credit on this platform today —
including the RM172,000 already recorded — was written by a **developer touching the database**.
P4a built the sign-off chain but gave it no surface, so it is currently a control on paper: the
people it names (`admin` maker, `org_admin` approver) have no way to execute their own steps.
P4b removes the developer from the money path and makes the chain real. **It is not gated by,
and does not gate, the Sabah RM100,000** — that is gated on the agreement being inked and the
money moving (see the owner gate under P2b).

**Role gates — mirror `payments.sign` exactly** (owner 2026-07-26; verified against live roles):

| Step | Gate | BrightPath today |
|---|---|---|
| Record + sign | `role == 'admin'` or super | **Poongulali Veeran** (`admin`) |
| Finance check | `role == 'finance'` or super | *dark — none appointed* |
| Confirm | `role == 'org_admin'` or super | **Suresh Thirugnanam** (`org_admin`) |

⚠ **Do NOT gate the maker on `org_admin`** — Poongulali is a plain `admin`, so that would lock
the actual operator out. Same pairing as the student payment chain, deliberately.

**⚠ P4b MUST close a gap carried from P4a:** the service functions take `signer` as a free string
— distinctness is enforced, identity and role are not. Add the payments chain's **typed-name
match** against `PartnerAdmin.name` (`name_mismatch`) **and** the role gate at the endpoint.
Until both land, the service alone is not a complete control.

### Original P4 scope (kept for reference)

**Re-scoped 2026-07-26** — see the ⚠ box below. This is **not** an accommodation for one benefactor;
it is how *every* sponsor's money enters the platform until BrightPath's CLBG is registered.

- **Goal:** Record an off-platform gift into a sponsor's programme-scoped wallet, under two-person
  control, with provenance strong enough to (a) reconcile against the receiving bank account today
  and (b) migrate cleanly into the CLBG's books once it exists.
- **Why it is new:** the ONLY donation path today is `SponsorDonateView` (`views_sponsor.py:409`) — a
  sponsor **self-service MOCK** writing `reference='mock'`. No gateway is wired and no admin path
  exists. The owner's actual funding flow cannot be executed with what is in the codebase.
- **The record shape (the load-bearing decision).** One `Donation`-shaped row, gaining:
  - `source` — `admin_recorded` (today) / `gateway` (post-CLBG) / `mock` (dev only). A gateway
    donation later is **the same row with a different source**, never a second money system.
  - `external_reference` — the bank-transfer reference. **Mandatory** when `source='admin_recorded'`;
    this is the only thread back to real money, and what makes the balance auditable.
  - `recorded_by` / `recorded_at`, plus `checked_by` / `checked_at` for the second signature.
  - `programme` (from P2) — a credit always lands in exactly one programme's wallet.
  - `mock` must be **unusable in production** — the dev-only self-service path can never mint a row
    that reads as real money.
- **✅ Sign-off: REUSE the payments chain (owner, 2026-07-26) — do not build a second control model.**
  Adopt `draft → admin_signed → [finance_checked] → completed` and call the EXISTING
  `payments.finance_check_required(organisation)` — do not reimplement or store the requirement.
  A credit is **recorded+signed by a maker**, optionally **checked by finance** when the org has ≥1
  active finance admin, then **countersigned by an approver** before it becomes spendable.
  BrightPath runs the two-step degraded chain today (maker → approver; *"the checker is dark. It
  only has maker and approver"*) and the check **arms itself retroactively** the moment a finance
  admin is invited — including for credits already mid-chain. Inherits the **three-distinct-signers
  pairwise** rule and the **stand-in rule** (super may fill one slot, never both), which is what
  answers the second-signer question. **⚠ Currency rule: a change to the payment-run chain must
  update this one in the same commit — they are deliberately one design.**
- **Balance semantics:** only a **confirmed** credit counts toward spendable balance. A recorded-but-
  unconfirmed credit is visible to admins and invisible to the sponsor — so an unconfirmed credit can
  never be allocated to a student.
- **Depends on:** P2 (per-programme balances) and P3 (the sponsor must be a member of the programme).
- **Migrations:** 2 additive (source/reference/audit columns on `Donation`; the confirmation pair).
- **Test plan:** a credit lands only in the named programme's wallet and is invisible in another; a
  credit against a sponsor with no membership in that programme is refused; `external_reference` is
  required when `source='admin_recorded'`; an unconfirmed credit does not raise spendable balance and
  cannot fund a student; one person cannot both record and confirm; the mock path cannot run in prod;
  and a **reconciliation assertion** — the sum of confirmed credits per programme equals the wallet
  total the sponsor sees.
- **Risk + mitigation:** *Risk:* the first path that puts real money into the system on an admin's
  say-so, while the actual cash sits in a personal account. *Mitigation:* two-person control, a
  mandatory external reference, unconfirmed-is-unspendable, and provenance fields designed for the
  CLBG hand-over rather than retrofitted to it.
- **Complexity:** Medium–High (money-touching). ~14 files.

**⚠ P4 IS THE PRIMARY FUNDING PATH, NOT AN EDGE CASE (owner, 2026-07-26).** BrightPath has no
registered legal entity yet — a CLBG is with a company secretary, some months away. Until it exists,
**every** sponsor pays into Suresh's personal account and he credits their wallet by hand: *"Real
money is off the platform, but the consequences aren't."* Build it as a first-class audited flow.
**Architectural instruction:** an admin-recorded credit and a future gateway donation are **the same
record with different provenance** (one `source` field + external reference) — never two parallel
money systems. See the decision record "Money is OFF-platform until the CLBG exists".

**Owner decisions on P4:**
1. **✅ ANSWERED 2026-07-26 — reuse the payments sign-off chain**, finance checker dormant until the
   role is filled. See the scope bullet above and the decision record "The wallet credit reuses the
   payments sign-off chain". No bespoke control model, no new second-signer rule.
2. **✅ ANSWERED 2026-07-26 — the benefactor SELF-SERVES allocation.** They browse the anonymised, programme-scoped pool and fund students **on need**, never learning any identity (decision record: "Benefactor anonymity is absolute"). The org admin does **not** allocate on their behalf — no additional admin scope. The admin's only money action is crediting the wallet.
3. **✅ ANSWERED 2026-07-26 — ONE ROW PER BANK TRANSFER.** The wallet is a two-sided ledger: credits
   in (one per transfer, each carrying its bank reference) and allocations out (one per student,
   anonymous ref only); the balance is the running sum, never stored. **This shrinks P4** — the
   "how has my money been spent" view already exists as `sponsorship.sponsor_statement()` (R4),
   which renders both ledgers. P4 therefore adds credits-with-real-references and makes the
   statement **programme-grouped** (wallets became per-programme in P2a); it does not build a
   ledger. Returns (lapsed/cancelled allocations) must appear as their own entries — money coming
   back should be visible, not a silently shrinking total. See the decision record "One credit row
   per bank transfer".

**Anonymity constraint binding P2/P3/P4:** programme scoping filters WHICH cards a funder sees; it must never touch the allowlist governing WHAT a card shows (`pool.py` + the allowlist serializers — students appear only as a salted-hash alias). The existing anonymity assertions must pass **unmodified** through all three sprints.

---

## How this re-bases the platform roadmap

| Platform roadmap item | Effect |
|---|---|
| Phase 3 S10a/S11 (superadmin portal) | **Moves out.** Both tenants will be hand-configured by the owner; a portal is for onboarding at scale, and there is no tenant #3 in view. Revisit when there is. |
| Phase 3 S10b (module enforcement) | Survives as **PF-2**; still worth doing, still needs the flag reconciliation first. |
| Phase 2 S7–S9 (rules extraction) | Now **gates Inspire**, whose programme is shaped differently (STPM-only, own document set). The "month of rule stability" gate will likely never close naturally now that two new programmes are arriving — take the split-gate option and extract deliberately. |
| Phase 2 branding | Absorbs the **award-noun** work (scholarship/bursary/assistance), ≈90–110 render sites, same pile as the 22 BrightPath literals in `emails.py`. |
| Sprint E (erasure) | **Promoted from conditional to hard-blocking** — Inspire is a separate legal entity, so a DPA is required before their applicants' data is processed. |
| Phase 6 (independence ladder) | Unchanged, still gated. |

**Suggested order:** PF-2 → P1 → P2 → P3 → P4 → nav/IA shell (organisation switcher, Administration as a section with sub-navigation) → Phase 2 extraction → Sprint E + DPA → portal, if ever.

**Two critical paths.** *Sabah (possibly late 2026):* P1 → P2 → P3 → P4 — and **Sabah needs none of Phase 2's extraction sprints**, because its rules are authored directly into the Programme columns P1 creates. *Inspire (after the meeting):* P1 → Phase 2 S7/S8a/S8b/S9 (re-targeted to Programme) → Sprint E + DPA, with their organisation created by hand.

**Timing (owner, 2026-07-26):** the flagship 2026 intake is **closed** and takes no new students this year; it reopens ~**May/June 2027**. Sabah is uncertain, **possibly later in 2026**. So PF-1's hard deadline is May/June 2027 — the first moment two programmes could be open at once — and the whole Sabah chain (P1–P4) is needed before Sabah can take a ringgit.

## Risks

| # | Risk | Mitigation |
|---|---|---|
| 1 | Two scoping dimensions (org + programme) double the authorisation surface | Programme narrows **inside** the org wall; the fence-proof suite and `FENCED_OR_EXEMPT` completeness map (`test_org_fence.py:194`) pass unmodified |
| 2 | Financial backfill on live donation data | Additive-then-read, sample verification, total-unchanged reconciliation assertion |
| 3 | Applications reopen before PF-1 lands → silent cross-org misrouting | `is_open` stays false until P1 ships; a test asserts routing never crosses an organisation |
| 4 | The Sprint-14 finance signature chain is live | `PaymentRun` gains a column only; the maker-checker logic is not touched |
| 5 | Award-noun interpolation produces ungrammatical Tamil | Shrink the surface first, then supply inflected sets — never a single token (decision record) |
| 6 | Scope creep from "Administration should do everything" | The nav shell ships empty slots; each extraction sprint fills one — no second redesign |
| 7 | **P4 puts real money in on an admin's say-so** — the first such path in the system | Maker-checker (recommended), a mandatory external bank reference, a source type that can never be confused with the `reference='mock'` self-service path |

## Verification

Per sprint: full `pytest` + `jest` green (baseline 4486 pytest / 719 jest at 2026-07-25), `next build` clean, migrate-first applied and verified on prod **before** the code that reads it deploys, live smoke of the affected surface, one deploy per sprint (deploy-twice cap), CHANGELOG entry, retrospective, and `wat_lint --project .` at close.
