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

### P1a — Structural foundation — ✅ **CODE COMPLETE 2026-07-26, migrations NOT yet applied to prod**

Delivered: `Programme` model (`scholarship_programmes`); `ScholarshipCohort.programme`;
`ScholarshipApplication.programme` denormalised in `save()` (set-once, both copies derived in a
single query on the uncached path); migrations `0118` (schema, with hand-written Postgres DDL in
its docstring) + `0119` (seed Programme #1 from the org's own branding, backfill cohort + 143
applications, both reversible); `tests/test_programme_layer.py` (16 tests). **Full suite green:
4593 passed, 0 failed.** Fence-proof suite and `FENCED_OR_EXEMPT` map pass **unmodified**.
Serializers use explicit field lists → **no API surface change**. No admin surface needed
(cohorts were never in Django admin). CHANGELOG written.

**▶ OWNER-GATED NEXT STEP:** apply `0118` + `0119` to prod **migrate-first** (before any deploy),
using the DDL in `0118`'s docstring, then insert the two `django_migrations` rows. Verify:
`scholarship_programmes` has 1 row; cohort `b40-2026` points at it; all 143 applications carry it.
**Not applied by the agent — this is a prod DDL change.**

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

- **Goal:** A donation carries the programme it was given to; a sponsor's balance becomes per-programme; a payment run can never pay out of another programme's money.
- **Scope:**
  - `Donation.programme` FK (additive) + backfill the 6 existing donations to Programme #1.
  - Balance computation moves from one pool per sponsor to **per (sponsor, programme)** — `donations − active allocations`, scoped. Every read of the balance goes through one helper (the `branding.py` precedent: one seam, not scattered reads).
  - `Sponsorship` already reaches a programme via `application`; assert consistency (an allocation may only draw on the balance of the programme its application belongs to) with a test, not a comment.
  - `PaymentRun.programme` FK (additive, nullable → backfill → read). The Sprint-14 maker-checker chain is untouched; only the run's funding source narrows.
  - Funding summary + any sponsor-facing balance display become programme-aware.
- **Migrations:** 2 additive + 1 data. Migrate-first; **financial data — verify the backfill on a sample before the full run.**
- **Test plan:** a donation to Sabah is invisible in the flagship balance and vice versa; an allocation against the wrong programme's balance is refused; the 6 backfilled donations reconcile to the same total (RM172,000) after the change; a payment run cannot include an application from another programme.
- **Risk + mitigation:** *Risk:* live financial records; a wrong backfill is expensive to unpick. *Mitigation:* additive-then-read (nothing reads the column until the reading code ships), sample verification, and a reconciliation assertion that total donations are unchanged before/after.
- **Owner gate:** do **not** record the RM100,000 as a platform donation before this sprint — with no programme column it would land in a platform-wide balance with no expressible restriction. Hold it in a documented manual ring-fence until P2 lands.
- **Complexity:** Medium–High. ~15 files.

## Sprint P3 — Sponsor Programme membership

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

Added 2026-07-26 after the owner described the actual Sabah funding flow: *benefactor donates to BrightPath Foundation off-platform → benefactor is onboarded into the Sabah programme → **org admin allocates RM100k into the benefactor's wallet under Sabah*** → the benefactor funds students from that wallet.

- **Goal:** Let an org admin record an off-platform gift into a sponsor's wallet, scoped to one programme, with an audit trail that reconciles to the money actually received.
- **Why it is new:** the ONLY donation path today is `SponsorDonateView` (`views_sponsor.py:409`) — a sponsor **self-service MOCK** writing `reference='mock'`. No gateway is wired and no admin path exists. The owner's flow cannot be executed with what is in the codebase.
- **Scope:**
  - Admin-recorded credit against **(sponsor, programme)** — depends on P2 (per-programme balances) and P3 (the sponsor must be a member of the programme first).
  - A real **external reference** (bank-transfer ref) and a **source type** distinguishing an admin-recorded gift from a gateway donation, so `reference='mock'` can never be confused with real money.
  - Audit trail: who recorded it, when, against which programme.
  - **Recommend maker-checker** — reuse the pattern already proven in the payments module (`draft → admin_signed → [finance_checked] → completed`). Crediting RM100,000 is the same class of action as approving a payment run, and the org already has the `finance` role built for exactly this weight of decision. **Owner decision outstanding** (see below).
- **Migrations:** 1–2 additive (source type + reference on `Donation`, or a dedicated credit model if maker-checker is adopted).
- **Test plan:** a credit lands only in the named programme's wallet and is invisible in another; a credit against a sponsor with no membership in that programme is refused; the external reference is required for an admin-recorded credit; a mock/self-service donation can never be created by the admin path; if maker-checker is adopted, one person cannot both record and approve.
- **Risk + mitigation:** *Risk:* this is the first path that puts real money into the system on an admin's say-so. *Mitigation:* two-person control, a mandatory external reference, and no reuse of the mock donation path.
- **Complexity:** Medium–High (money-touching). ~12 files.

**Owner decisions on P4:**
1. **OPEN — Maker-checker, or single-admin with an audit log?** (Recommended: maker-checker.)
2. **✅ ANSWERED 2026-07-26 — the benefactor SELF-SERVES allocation.** They browse the anonymised, programme-scoped pool and fund students **on need**, never learning any identity (decision record: "Benefactor anonymity is absolute"). The org admin does **not** allocate on their behalf — no additional admin scope. The admin's only money action is crediting the wallet.
3. **OPEN — One credit per bank transfer, or a running top-up ledger?** Affects reconciliation against the Foundation's bank account.

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
