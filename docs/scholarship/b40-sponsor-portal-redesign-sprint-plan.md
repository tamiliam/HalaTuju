# Sprint plan — Sponsor Portal Redesign (B40 Assistance Programme)

> **Source:** approved interactive prototype at `prototypes/sponsor-portal-redesign/` (owner-approved 2026-06-19) + `b40-phase-ef-prd.md`.
> **Relationship to existing plan:** the Phase E/F backend + a basic portal frontend are **already built and merged on `main`** (Sprints 0–11 of `b40-phase-ef-sprint-plan.md`, all done, shipping **dark** behind `SPONSOR_POOL_ENABLED`). This redesign is a **frontend refit of the signed-in `/sponsor` portal** plus a few small new aggregation endpoints. It sequences **after Sprint 11, before the lawyer-gated Sprint 12 go-live** — the redesigned portal becomes what goes live.
> **Status:** approved-in-principle 2026-06-19; per-sprint build to follow. No feature code until a sprint starts.

## Owner decisions (2026-06-19)
- **Standing gift (AutoSponsor):** keep it in scope (R6).
- **Assurance model:** **layered** — institutions confirm enrolment + an independent auditor attests on the money + a trustee board signs off.
- **Assurance cadence:** **annual** published statement.
- **Donation history = two separate ledgers:** donations *into the trust* (`Donation`) and gifts *out to students* (`Sponsorship`) — both shown with amount + date.
- **Long-lead governance task (owner-driven, start now in parallel with R1):** appoint the independent auditor + trustee body and define what they attest to. The software (R5) only surfaces their attestation.
- **Trust & Transparency is an IR-style hub (R5), not just assurance:** add *Who we are* (governance/background) + *Sources & uses of funds* (programme-wide). Build the **scaffold with honest placeholders now** ("we don't even have an organisation yet"); fill content in over time via small changes as the org formalises — never fabricate a board or accounts.

## Hard constraints (unchanged, every sprint)
- **Allowlist only** — every student field rendered comes from `SponsorPoolCardSerializer`/`SponsorPoolDetailSerializer`; never name/IC/address/photo/contact (student *or* parents); institution only for `is_trusted` sponsors. Leak test per sprint.
- **Ship dark** behind `SPONSOR_POOL_ENABLED`; nothing reaches real sponsors until the lawyer-gated go-live.
- **No sponsor↔student channel.** Progress is a coarse band, never grades. Giving is *redirected*, never *withdrawn*.
- **i18n parity** en/ms/ta (Tamil per `tamil-style-guide.md`). **Local-first**, `pytest`+`jest` green, ≤2 deploys/feature. Design already owner-approved via the prototype (substitutes for Stitch on these screens).

---

## Sprint sequence

| # | Sprint | New backend | Complexity |
|---|--------|-------------|------------|
| R1 | Portal shell + nav + **Students** marketplace tab | none | Medium |
| R2 | **My Giving** dashboard — impact numbers, donut, student journeys | small | Medium |
| R3 | Activity feed + community strip | small | Medium |
| R4 | **My Account** tab + **giving statement** (two ledgers) | tiny | Low–Med |
| R5 | **🆕 Trust & Assurance** | small | Medium |
| R6 | Standing gift / AutoSponsor | yes (new model + cron) | High |
| R7 | Polish + i18n parity + fold into go-live | none | Low–Med |

---

### R1 — Portal shell + Students tab · FE (no new backend)
**Goal:** replace the flat `/sponsor` scroll with the three-tab shell (My Giving · Students · My Account) and ship the Students marketplace.
**Scope:** tabbed nav + routing — `/sponsor` → My Giving when signed in; `/sponsor/students`, `/sponsor/students/[id]`, `/sponsor/account`; keep the public `SponsorLanding` (signed-out) untouched; 301 old `/sponsor/pool/[id]` → `/sponsor/students/[id]`. Students tab = filterable pool grid (`getSponsorPool`) + detail + "Support this student" (`fund`).
**Acceptance:** browse → filter → view → fund works in the new design; leak test green; ships dark; jest green.

### R2 — My Giving dashboard · BE(small) + FE
**Goal:** lead with impact, not chores.
**Scope:** impact-number strip + giving donut + "students you support" cards with the Matched→Onboarded→Sem→Graduated journey tracker.
**New backend:** `GET /sponsor/impact/` aggregate (total given, supported, active, graduated, semesters completed, balance breakdown committed/completed/available) + a coarse `journey`/`stage` field on `SponsorSponsorshipSerializer` — all derived from existing models, allowlist-safe.
**Acceptance:** figures reconcile with wallet; journey leaks nothing; aggregate tested.

### R3 — Activity feed + community strip · BE(small) + FE
**Scope:** "Recent activity" feed + "you're 1 of N sponsors, together supporting M students" strip.
**New backend:** `GET /sponsor/activity/` synthesised from existing events for *this sponsor's* students (offer accepted = `Sponsorship.decided_at`; semester completed = `SemesterResult.created_at`; graduated; new-students-published count), refs only; small community-count endpoint.
**Decision at sprint start:** synthesise on the fly (no migration — preferred) vs a lightweight event-log table.

### R4 — My Account tab + giving statement · BE(tiny) + FE
**Scope:** relocate + restyle existing pieces (profile + approved/trusted badges, notification cadence, thank-you wall, invite-a-friend) into the Account tab. Add the **giving statement as two ledgers**: *Donations to the trust* (in, `Donation`) and *Gifts to students* (out, `Sponsorship`), each amount + date, with a downloadable record. Framed as a *record*, not a tax receipt (Section 44(6) pending).
**New backend:** `GET /sponsor/statement/` assembling both ledgers (data already exists). Mostly relocation → light.

### R5 — Trust & Transparency hub · BE(small) + FE  🆕 (the load-bearing trust layer)
**Goal:** because the model runs on trust, surface the full trust story — who we are, where the money flows, and who independently checks it. **Build the scaffold now with honest placeholders; content drops in over time as the organisation formalises (via small changes, not sprints).**

**The four-layer trust stack:**
1. **Who we are** — organisation, background, legal entity/registration, the people behind it. *(Placeholder now — "we don't even have an organisation yet"; honest "to be published" copy, never fabricated.)*
2. **Sources & uses of funds** — programme-wide money at a glance (IR-style, tiny scale): total donated in, grants, gifts to students, held-for-committed, running costs. Published annually. *(Placeholder/illustrative figures now; real figures as accounts mature — editable content, not a code change.)*
3. **Independent assurance** — layered (institution enrolment confirmation + independent auditor on the money + trustee sign-off), published **annually**.
4. *(personal layer = the sponsor's own two-ledger statement, delivered in R4.)*

**Scope (surfacing):**
- **Trust & Transparency page** with the four sections above, each populated or showing a tasteful placeholder/"coming soon".
- **Verified badge** — *"Enrolment independently verified"* on student cards/detail.
- **Assurance panel** on My Giving — latest annual summary + audited cumulative figures, linking to the hub.
- **Trust bar** on the public sponsor landing (the "Regulated by…" equivalent).
**New backend (light):** store assurance statements + org-financials figures + governance/about content as **editable content (no deploy to update)**; a per-student `enrolment_verified` flag (set inside the identity wall; surfaced as a boolean badge only — never the verifier's evidence). Allowlist-safe.
**Gated on:** the owner naming the auditor/trustee + attestation scope (governance task started at R1) — but the scaffold ships without it (placeholders).
**Acceptance:** hub + badge + panel render; placeholders read honestly; flag never leaks identity; org/assurance content is editable without a deploy.

**Content backlog (post-R5, small-change lane — arrives piece by piece):** Who-we-are copy + legal entity once registered · trustee names/bios once appointed · first real sources-and-uses figures · first independent auditor's report.

### R6 — Standing gift / AutoSponsor · BE(new model + cron) + FE
**Goal:** the AutoInvest-style innovation — a sponsor's balance auto-supports the next matching student.
**Scope:** new `StandingGift(sponsor, cadence, field_pref, state_pref, max_amount, active, last_allocated_at)` + migration; allocation hook (reuses `fund_student`, still produces an *offered* sponsorship the student must accept — no real money moves) wired into the publish path / existing sponsor-realtime cron; the Account card.
**Open questions for sprint-start:** cadence semantics; zero-balance behaviour; whether auto-allocating a donation needs a line in the lawyer bundle.

### R7 — Polish + parity + go-live folding · FE + i18n
**Scope:** full en/ms/ta parity (Tamil per style guide), accessibility, empty states, mobile. Hands off to the existing **Sprint 12** flag-flip (lawyer-gated, unchanged).

---

## Expected new endpoints (all allowlist-safe, flag-gated)
`GET /sponsor/impact/` · `GET /sponsor/activity/` · `GET /sponsor/community/` · `GET /sponsor/statement/` · `GET /sponsor/assurance/` · `GET/PUT /sponsor/standing-gift/`

## Notes
- The interactive prototype (`prototypes/sponsor-portal-redesign/index.html`) is the design of record and includes the assurance strip, verified badges, and two-ledger statement.
- "There will likely be changes once we check with potential sponsors" (owner) — re-plan remaining sprints at each sprint-close.
