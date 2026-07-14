# Draft Multi-Sprint Roadmap — HalaTuju Multi-Tenant Platform (Route A)

**Date:** 2026-07-14
**Author:** Research analyst (drafting engineer) — for architect + owner review
**Status:** DRAFT roadmap. Nothing has been built. Follows `Settings/_workflows/implementation-planning.md` conventions.
**Reads with:** `2026-07-14-tenancy-audit.md` (evidence) and `2026-07-14-platform-prd-draft.md` (requirements).

---

## How this roadmap is organised

The **phasing is fixed** (owner's decision):
1. **Phase 1 — Organisation layer + data fencing**, with BrightPath as the sole tenant, **invisible to users** (every change leaves BrightPath behaving exactly as today, because org #1 is the only org).
2. **Phase 2 — Extract hard-coded rules into per-org settings**, branding/email first, eligibility last.
3. **Phase 3 — Platform superadmin portal.**
4. **Phase 4 — Second-tenant onboarding rehearsal.**

Sprints live *inside* these phases. Each sprint is sized to be **reviewable** — a coherent, single deliverable, ≤ ~40 files touched — not to fit in context. **BrightPath must stay live and unbroken after every sprint** (it is in production with real applicants).

**Total: 13 sprints.** Rationale for the count: the two hardest coupling knots (the overloaded `StudentProfile` and the dual-hatted `PartnerAdmin`, audit §6 #1/#3) plus the "prove the fence" safety requirement force the fencing work (Phase 1) into four separate, individually-verifiable sprints rather than one big-bang. Phase 2 is naturally four sprints because branding, timing, documents, and eligibility are independent extraction jobs that ship one at a time. Phase 3 is three (backend org-management, superadmin UI, org-admin scoped UI). Phase 4 is two (metering, then the full rehearsal + rollback drill). Honest sizing — not crammed; if a sprint below looks tight in review, split it rather than overload it.

**A recurring "invisible today" property:** through Phases 1–2, there is exactly one organisation (BrightPath). Scoping every query to "the caller's org" therefore returns *identical results to today*. This is what makes the risky fencing work safe to ship incrementally — the behaviour doesn't change until a second org exists (Phase 4).

---

## Phase 1 — Organisation layer + data fencing (BrightPath sole tenant, invisible)

### Sprint 1 — The Organisation record + BrightPath as org #1
- **Goal:** Establish the tenant spine by growing `courses.PartnerOrganisation` into the platform Organisation record and linking the programme config (`ScholarshipCohort`) to it. (Decision D-6/D-8.)
- **Scope:** `apps/courses/models.py` (`PartnerOrganisation` — add identity/branding/module-flag columns), `apps/scholarship/models.py` (`ScholarshipCohort` — add `organisation` FK), admin serializers, a data migration seeding BrightPath as organisation #1 and pointing the existing cohort(s) at it.
- **Migrations expected:** 2 (additive columns on `partner_organisations`; additive FK on `scholarship_cohorts`) + 1 data migration (seed org #1, backfill cohort→org). All additive/backward-compatible → migrate-first, zero downtime.
- **Test plan:** model tests for the new columns/FK; a migration test that the existing cohort ends up owned by org #1; full existing scholarship suite green (2,400+ pytest per project history).
- **Main risk + mitigation:** *Risk:* the org record diverges from the eventual config surface. *Mitigation:* land only the columns the PRD §3 config surface names; leave editing UI to Phase 3.
- **How we know BrightPath still works:** no runtime behaviour changes (nothing reads the new FK yet); golden masters + full suite pass; a live smoke of the applicant flow.
- **Complexity:** Low.

### Sprint 2 — Owning-org on the application
- **Goal:** Give every `ScholarshipApplication` a durable owning-organisation, so queries can be fenced (audit §3: today there is none).
- **Scope:** `apps/scholarship/models.py` (denormalised `organisation` FK on the application, populated from its cohort per D-8), the create path (`ApplicationCreateSerializer`/`services`), a data migration backfilling every existing application to org #1.
- **Migrations expected:** 1 additive FK (`scholarship_applications.organisation_id`) + 1 data migration (backfill all rows → org #1). Additive → migrate-first, zero downtime.
- **Test plan:** every new application gets an org; backfill covers 100% of existing rows; suite green.
- **Main risk + mitigation:** *Risk:* an application created without an org slips the fence later. *Mitigation:* make the column non-null after backfill; a create-path test asserts org is always set.
- **How we know BrightPath still works:** the column is written but not yet *read* for authorisation (that's Sprint 3), so behaviour is unchanged; live smoke of a new application.
- **Complexity:** Low–Medium.

### Sprint 3 — Org-scoped query layer + fence the admin gates + PROVE it (the #1-risk sprint)
- **Goal:** Enforce the organisation wall on every admin read/write, and ship a test that *proves* one org cannot see another's applicants. This is the security heart of the project.
- **Scope:** `apps/scholarship/views_admin.py` — add an org predicate to the shared gates `_b40_scope` (`:89-103`), `_scoped_application` (`:105-119`), `_can_review_app` (`:121-132`), `_require_app_write` (`:134-148`), `_require_qc` (`:150-175`), and the list query (`:186-189`); an org-scoped model manager / queryset helper so the fence is centralised (mirroring the courses `get_partner_students` pattern, `courses/views_admin.py:80-104`). Super stays global.
- **Migrations expected:** 0 (code-only).
- **Test plan:** **the fence-proof test** — seed two organisations with an applicant each; assert every admin endpoint (list/detail/write/QC) returns/permits only the caller-org's applicant and 403/404s the other's, for each role; a static guard test that no admin queryset omits the org filter (mirroring the existing superseded-docs guard pattern, `models.py:943-948`).
- **Main risk + mitigation:** *Risk (this IS risk #1):* a missed query path leaks cross-tenant data. *Mitigation:* centralise the filter in one manager; the static guard test fails CI if any admin read bypasses it; a second reviewer signs off the query audit.
- **How we know BrightPath still works:** with one org, every scoped query returns exactly today's rows — the full existing suite passes unchanged; live smoke of the reviewer/QC cockpit against real BrightPath data.
- **Complexity:** High. (If review finds >40 files or the gate audit balloons, split into 3a "gates + manager" and 3b "fence-proof test + static guard".)

### Sprint 4 — Document storage org-prefix + fence
- **Goal:** Fence uploaded documents per organisation (audit §4: keys are `<app_id>/<doc_type>/<uuid>` with no org element).
- **Scope:** `apps/scholarship/views.py:666` (add org prefix at the single generation site), `apps/scholarship/storage.py` (list/delete/backup helpers to carry the prefix), a dual-read shim so existing objects (old keys) still resolve, and a backfill plan for `storage_path` values; `serializers.py:692-694` (assert the caller's org owns the path before signing a view URL).
- **Migrations expected:** 0 schema (the `storage_path` column is already `CharField(500)`); 1 data/backfill *operation* (re-key or dual-read existing objects — owner-gated, done on the live service, never a local re-extract per `halatuju_never_reextract_locally.md`).
- **Test plan:** new uploads land under `<org>/…`; a cross-org signed-URL request is refused; backup/OCR paths carry the prefix; existing docs still viewable via the shim.
- **Main risk + mitigation:** *Risk:* re-keying breaks access to existing documents. *Mitigation:* dual-read (try new key, fall back to old) so no object is orphaned; verify against a sample of live BrightPath docs before any bulk re-key.
- **How we know BrightPath still works:** every existing BrightPath document opens in the cockpit; a new upload round-trips; the reviewer sees the doc drawer intact.
- **Complexity:** Medium–High.

*(Phase 1 exit criterion: a hypothetical second org would already be fully isolated at the data + document layer, even though none exists yet.)*

---

## Phase 2 — Extract hard-coded rules into per-org settings (branding/email first, eligibility last)

### Sprint 5 — Per-org branding & email sender identity (backend)
- **Goal:** Move the hard-coded programme name, team sign-off, personas, and sender/reply-to identities off code constants onto the organisation record (audit §2d).
- **Scope:** `apps/scholarship/emails.py` (replace the `_REVIEWER_SIGNOFF`, alias constants `:16-20`, programme-name literals `:429-1035`, HTML shell `:2032-2060` with per-org lookups), the Organisation config read seam, "Cikgu Gopal" persona name (`help_engine.py`, `verdict_narrative.py`).
- **Migrations expected:** 0 (columns landed in Sprint 1) — this sprint *reads* them.
- **Test plan:** an email rendered for org #1 is byte-identical to today's (BrightPath name/sign-off/aliases); an email rendered for a fixture org #2 shows org #2's name/sender; i18n parity intact.
- **Main risk + mitigation:** *Risk:* a missed literal ships a BrightPath name to another org later. *Mitigation:* grep-guard test that no user-facing email string contains a hard-coded "BrightPath"/"Cikgu Gopal" literal.
- **How we know BrightPath still works:** every BrightPath email (reviewer, student, award, decline) renders identically to today — snapshot the templates before/after.
- **Complexity:** Medium.

### Sprint 6 — Per-org branding (frontend)
- **Goal:** De-hard-code the programme name, theme, and logo in the web app (audit §2d / frontend audit).
- **Scope:** `halatuju-web/src/messages/{en,ms,ta}.json` (introduce a `{programmeName}` interpolation variable replacing the ~7 literals: `en.json:414,720,258,290,401,1748,2992` and consent `:1562-1563`), the legal-page JSX literals (`terms/page.tsx:52,55`, `privacy/page.tsx:21,29,42`), theme (`tailwind.config.ts:12-27` → CSS-variable brand colour), logo slot (`AppHeader.tsx:78`), and a programme-config fetch from the backend.
- **Migrations expected:** 0.
- **Test plan:** `next build` clean; i18n parity ×3; BrightPath renders "BrightPath Bursary" everywhere it does today; a fixture second-org theme swaps colour+logo+name.
- **Main risk + mitigation:** *Risk:* consent legal text with an interpolated name loses legal precision. *Mitigation:* legal review of the interpolated consent string before flipping (it's the artefact a lawyer vets).
- **How we know BrightPath still works:** visual diff of every scholarship/sponsor page against today; the consent text reads identically.
- **Complexity:** Medium.

### Sprint 7 — Per-org timing, reminders & consent version
- **Goal:** Move the hard-coded reminder cadence and consent version onto per-org config (audit §2c).
- **Scope:** `apps/scholarship/services.py:342-343` (`REMINDER_THRESHOLDS_DAYS`, grace → cohort config), `CONSENT_VERSION` (`:1993`) per-org, the reminder job reads org config.
- **Migrations expected:** 1 additive (cadence/consent-version columns on the cohort, if not folded into Sprint 1).
- **Test plan:** the reminder job fires on the org's configured cadence; BrightPath's cadence unchanged (2,9,23,53); consent version resolves per-org.
- **Main risk + mitigation:** *Risk:* changing the cadence source re-fires reminders to live applicants. *Mitigation:* seed org #1 with the exact current constants; a test asserts no change in due-dates for existing applications.
- **How we know BrightPath still works:** reminder due-dates for the live cohort are identical before/after; no duplicate sends.
- **Complexity:** Low–Medium.

### Sprint 8 — Per-org document checklist selection (shared engine, org-selectable)
- **Goal:** Let each programme select *which* documents/routes/facts apply, while the verification engine stays one shared service (PRD §3c; audit §2b).
- **Scope:** a per-org document/route/fact configuration read by `income_engine.income_requirements` (`:1884`), `services.income_doc_blockers`/`application_completeness`/`document_red_blockers`, and the fact set in `verdict_engine.build_verdict` (`:1072`). The `ApplicantDocument.DOC_TYPES` catalogue stays the master list; the org config selects a subset.
- **Migrations expected:** 1 additive (org document/fact config, likely JSON on the org/cohort).
- **Test plan:** org #1 selects BrightPath's exact current set → checklist + gates identical to today; a fixture org #2 with a different set (e.g. no STR route, requires school-leaving letter) produces a different checklist; the engine maths is untouched (genuineness/STR/EPF tests unchanged).
- **Main risk + mitigation:** *Risk:* the engine accidentally becomes org-editable (violating the safety promise). *Mitigation:* config selects *inputs* (which docs/facts), never *algorithm*; a test asserts the verdict maths is identical for the same inputs regardless of org.
- **How we know BrightPath still works:** the four-fact verdict + submission gates for live BrightPath applicants are unchanged (snapshot a sample of real verdicts before/after).
- **Complexity:** High. (Candidate to split into 8a "document/route selection" and 8b "fact selection" if >40 files.)

### Sprint 9 — Per-org eligibility thresholds & funding amounts
- **Goal:** Finish the extraction — lift the stray hard-coded eligibility constants and per-pathway funding amounts onto per-org config (audit §2a/§2d). (The headline income/academic thresholds are *already* on the cohort — this sprint mops up the baked constants.)
- **Scope:** `income_engine.py:1274` (`_HEADROOM_THIN_RM` → derive from cohort's per-capita ceiling), the IPTS/UPU-scope gates (`shortlisting.py:111-116`), soft utility proxies (`income_engine.py:1443-1444`), award amounts (`award.py:30-78`) and funding-estimate table (`funding_estimate.py:24-156`) → per-org config.
- **Migrations expected:** 1 additive (funding-amounts + soft-threshold config on the org/cohort).
- **Test plan:** BrightPath's numbers reproduce today's outcomes exactly (shortlisting + award-amount snapshots); a fixture org #2 with different amounts produces different award proposals; golden-master-style regression on a sample of real applicants.
- **Main risk + mitigation:** *Risk:* the duplicated `_HEADROOM_THIN_RM` constant and the cohort ceiling drift. *Mitigation:* derive one from the other; a test asserts they agree.
- **How we know BrightPath still works:** shortlisting verdicts + proposed award amounts for the live cohort are identical before/after.
- **Complexity:** Medium.

---

## Phase 3 — Platform superadmin portal

### Sprint 10 — Superadmin organisation management (backend)
- **Goal:** Backend for the superadmin to create organisations, toggle modules, edit config, and invite an org admin (PRD §1/§2).
- **Scope:** superadmin-only endpoints (org CRUD, module toggles, config edit), reusing the invite path (`AdminInviteView`, `courses/views_admin.py:352-461`) to invite an org admin bound to the org; module-flag enforcement so a disabled module 404s (PRD §2, D-5 suspend behaviour).
- **Migrations expected:** 0–1 (any remaining config columns).
- **Test plan:** superadmin creates/suspends an org; toggling a module hides its surfaces; an org-admin invite lands scoped to that org; non-super is refused every endpoint.
- **Main risk + mitigation:** *Risk:* module-off leaves an orphaned surface reachable. *Mitigation:* a test enumerates every module's endpoints and asserts each 404s when off.
- **How we know BrightPath still works:** BrightPath = org #1 with all its modules on → unchanged; toggles are only exercised on a fixture org.
- **Complexity:** Medium–High.

### Sprint 11 — Superadmin portal UI
- **Goal:** The superadmin-facing web portal for the Sprint-10 backend.
- **Scope:** `halatuju-web/src/app/admin/…` new superadmin section (org list, create/edit, module toggles, config forms, invite). **Stitch-prototype first** (project rule). Reuses the admin auth/nav split.
- **Migrations expected:** 0.
- **Test plan:** `next build` clean; render + interaction tests; a superadmin can create org #2 and configure it end-to-end in the UI.
- **Main risk + mitigation:** *Risk:* config forms expose the "not configurable" engine internals. *Mitigation:* the UI only surfaces PRD §3 settings; a review checklist item.
- **How we know BrightPath still works:** the existing admin surfaces are untouched; the new section is additive and superadmin-gated.
- **Complexity:** Medium.

### Sprint 12 — Org-admin scoped portal
- **Goal:** The organisation admin's own dashboard — sees only their programme, edits their own config, invites their own staff (PRD §1, the central new persona).
- **Scope:** org-admin landing + scoped applicant list (reuses the Sprint-3 fenced queries), the org-scoped config editing UI (branding request, eligibility, funding, documents, timing), org-scoped invite. Nav split so an org admin never sees platform/course-data surfaces.
- **Migrations expected:** 0.
- **Test plan:** an org admin sees only their org's applicants + config; cannot reach another org's data or the superadmin surfaces; can invite a reviewer bound to their org.
- **Main risk + mitigation:** *Risk:* the org-admin role accidentally inherits the old "admin sees all" behaviour (audit §3). *Mitigation:* the Sprint-3 fence + a test that an org admin is 403/404'd on every cross-org and platform path.
- **How we know BrightPath still works:** you (super) still see everything; a BrightPath-scoped org-admin fixture sees exactly BrightPath.
- **Complexity:** Medium–High.

---

## Phase 4 — Second-tenant onboarding rehearsal

### Sprint 13a — Per-org cost metering (tagging)
- **Goal:** Tag every billable call with its organisation so per-tenant costs can be metered (PRD §5 Option A; audit §5 cost-attribution points).
- **Scope:** a usage-log wrapper at the billable seams — `vision._call_gemini_json` (`vision.py:1490`), `profile_engine._call_gemini_text` (`:261`), `report_engine` (`:331,367`), Twilio (`whatsapp.py:224,112`), Brevo (`emails.py` `_send*`) — recording `(organisation, service, model, units)`; a simple per-org usage report.
- **Migrations expected:** 1 (a `usage_event` table, additive + RLS).
- **Test plan:** each billable path writes a tenant-tagged usage row; a per-org total reconciles against a scripted run; no double-count.
- **Main risk + mitigation:** *Risk:* the wrapper adds latency/cost to hot paths. *Mitigation:* fire-and-forget logging, no blocking; measure the added latency.
- **How we know BrightPath still works:** all BrightPath calls succeed and are now tagged to org #1; no behaviour change.
- **Complexity:** Medium.

### Sprint 13b — Second-tenant ("Inspire") rehearsal + rollback drill
- **Goal:** Prove the whole thing end-to-end by onboarding a *rehearsal* organisation with dummy data, and validate the migration/rollback story.
- **Scope:** no new features — an *exercise*: superadmin creates "Inspire", configures branding/eligibility/documents/funding, invites an admin + reviewer, runs a dummy applicant through apply→review→verdict, and **proves isolation** (Inspire staff cannot see BrightPath, and vice-versa); run the rollback drill (below).
- **Migrations expected:** 0 (uses the machinery built in Phases 1–3).
- **Test plan:** the full isolation test suite (Sprint 3's fence-proof, extended to documents + comms + cost); a dummy Inspire applicant completes end-to-end; BrightPath continues untouched throughout.
- **Main risk + mitigation:** *Risk:* a real gap only surfaces with two live orgs. *Mitigation:* this whole sprint IS the mitigation — a rehearsal on dummy data before any real second tenant; keep BrightPath the only *real* tenant until sign-off.
- **How we know BrightPath still works:** BrightPath applicants + reviewers operate normally while Inspire's dummy cohort runs alongside; the fence-proof suite is green.
- **Complexity:** Medium.

---

## Migration strategy note (re-homing BrightPath under organisation #1, zero downtime)

**Principle:** every schema change in Phases 1–2 is **additive** and applied **migrate-first** (the project convention — deploy does not run migrations; they are applied to prod before the code that reads them ships). Additive columns are backward-compatible: the live old code keeps working because it never references the new column until the sprint that reads it deploys.

**The re-homing sequence (zero downtime):**
1. **Sprint 1** adds the Organisation columns + the `cohort.organisation` FK (nullable) and seeds BrightPath as org #1, pointing the live cohort at it. Old code ignores it → no downtime.
2. **Sprint 2** adds `application.organisation` (nullable), backfills every existing application to org #1, *then* tightens to non-null. Backfill runs against the live DB (a data migration); until the fence turns on (Sprint 3) nothing reads it.
3. **Sprint 3** turns on the read-side fence. Because there is exactly one org, every scoped query returns the same rows as before → invisible to users.
4. **Sprint 4** re-keys documents behind a **dual-read shim** (new key first, old key fallback), so no object is ever orphaned; the bulk re-key runs on the live service, verified against a doc sample first.

**Rollback story (per sprint):**
- **Code rollback:** every sprint is a revertable deploy; because the new columns are additive and the old code never required them, reverting the code leaves the DB in a working state (the extra columns are simply unused).
- **Data rollback:** the seed/backfill migrations are written with a reverse (or a documented "leave the column, it's harmless" note) — no destructive change until an explicit, separate off-boarding action (D-5). The Sprint-3 fence can be reverted by removing the org predicate; with one org that is a no-op behaviourally.
- **Document rollback (Sprint 4):** the dual-read shim means a revert falls back to old keys; the bulk re-key is the only irreversible-ish step, so it is done last, gated by the owner, and verified on a sample before the full run.
- **The rollback drill (Sprint 13b)** exercises: revert the fence, confirm BrightPath still reads; restore; confirm isolation holds.

---

## Risk register (top 10 across the programme)

| # | Risk | Likelihood × Impact | Mitigation |
|---|---|---|---|
| **1** | **Data leak between tenants** — one org sees/edits another's applicants or documents. | Med × Critical | **The core mitigation:** a centralised org-scoped query manager (Sprint 3) + org-prefixed document keys (Sprint 4); a **fence-proof test** that seeds two orgs and asserts every admin endpoint returns only the caller-org's data; a **static guard test** that fails CI if any admin queryset omits the org filter. Remember the DB superuser bypasses RLS (audit intro) — the fence MUST live in Django, tested, never assumed from the DB. |
| **2** | **Breaking BrightPath in production** while refactoring the app it lives in. | Med × High | Every sprint leaves behaviour identical (one org = today); before/after snapshots of verdicts, award amounts, emails, reminders; the full existing suite + golden masters must stay green; live smoke each sprint. |
| **3** | **Overloaded `StudentProfile`** (audit hot-spot #1) — splitting/scoping the shared god-model corrupts course-selector OR scholarship data. | Med × High | Do NOT split the table in v1; keep it the shared account and fence at the *application* level (Sprint 2). The two-way sync stays as-is; a test covers course-selector reads unchanged. |
| **4** | **Missed authorisation path** — one of the ~25 admin endpoints skips the fence. | Med × High | Centralise the filter in one manager (Sprint 3); enumerate every `_AdminBase` subclass; the static guard test; second-reviewer query audit. |
| **5** | **Document re-keying orphans live files** (Sprint 4). | Low × High | Dual-read shim; verify on a live sample before bulk; re-key last, owner-gated, on the live service only. |
| **6** | **Consent/legal text loses precision** when the programme name is interpolated (Sprint 6). | Low × High | Lawyer review of the interpolated consent string before flipping; consent is the artefact being legally vetted. |
| **7** | **Verification engine accidentally becomes org-editable**, violating the "no bespoke logic" safety promise. | Low × High | Config selects *inputs* (which docs/facts), never the algorithm (Sprint 8); a test asserts identical verdict maths for identical inputs across orgs. |
| **8** | **Cost blow-out** from a second tenant's cohort (breaks the <$10/month baseline). | Med × Med | Per-org metering (Sprint 13a) before any real second tenant; visibility first, billing policy decided on real numbers (PRD §5). |
| **9** | **External-service identity bleed** — org B's emails send from org A's identity, or Twilio/Meet cross-wires. | Med × Med | Per-org sender identity (Sprint 5); grep-guard against hard-coded names; each external service's per-tenant separation is designed in audit §5 (some, e.g. Workspace/Vircle, stay single-tenant in v1 — documented, not silently assumed). |
| **10** | **Scope creep from the coupling knots** (`PartnerAdmin` dual role, reverse `courses→scholarship` imports, audit #3/#5). | Med × Med | Org-scope the role rather than split the table (D-2); leave the reverse-import course endpoints working (they operate on org #1 unchanged); split any >40-file sprint (3, 8 flagged as candidates). |

---

## Review checklist for the architect (the 10 questions to challenge me on)

1. **Is fencing at the *application* level (a denormalised `organisation` FK) the right cut — or should the wall be at `StudentProfile`?** I argue the profile is the shared account and must stay shared (audit #1); the fence belongs on the application. Push on this.
2. **Is one org-scoped query manager + a static guard test genuinely sufficient to prevent a cross-tenant leak, given the DB superuser bypasses RLS?** Or do we also want a defence-in-depth DB layer (org-scoped JWTs to Storage/PostgREST)?
3. **`cohort → organisation` with a denormalised org on the application (D-8) — right, or should the application own the org FK directly?** Trade-off: denormalisation risk vs cheap fenced queries.
4. **Are sponsors platform-level or tenant-level (D-1)?** This changes whether `Sponsor`/`Donation`/`Sponsorship` get an org fence or stay global. I deferred it; is that safe?
5. **Suspend-not-delete on module-off (D-5) — acceptable for PDPA, or does a real org need guaranteed erasure on off-boarding before we onboard them?**
6. **Is "config selects inputs, never algorithm" a strong enough guarantee that the verification engine stays safe/shared?** Is there a checklist item or type-level guard that enforces it?
7. **Document re-keying (Sprint 4): dual-read shim + bulk re-key — or should we leave old keys and only prefix new ones?** (Simpler, but the old objects stay unfenced by path.)
8. **Is 13 sprints honest, or are Sprints 3 and 8 (flagged High) actually two sprints each?** Where would you split them?
9. **Cost metering as tagging (Option A) — enough, or do we need per-org keys (Option B) before a real second tenant to guarantee billing isolation?**
10. **Have we correctly kept "referring organisation" (the existing `referred_by_org` marker) distinct from "owning organisation" (the new tenant boundary)?** They overlap ambiguously in the code (audit #9) — is the separation clean in this plan?

---

## Appendix — sprint summary table

| Phase | Sprint | Deliverable | Migrations | Complexity |
|---|---|---|---|---|
| 1 | 1 | Organisation record + BrightPath as org #1 | 2 + 1 data | Low |
| 1 | 2 | Owning-org on the application | 1 + 1 data | Low–Med |
| 1 | 3 | Org-scoped gates + fence-proof test | 0 | **High** |
| 1 | 4 | Document storage org-prefix + fence | 0 schema + 1 backfill op | Med–High |
| 2 | 5 | Per-org branding + email identity (backend) | 0 | Med |
| 2 | 6 | Per-org branding (frontend) | 0 | Med |
| 2 | 7 | Per-org timing/reminders/consent version | 1 | Low–Med |
| 2 | 8 | Per-org document checklist selection | 1 | **High** |
| 2 | 9 | Per-org eligibility thresholds + funding amounts | 1 | Med |
| 3 | 10 | Superadmin org management (backend) | 0–1 | Med–High |
| 3 | 11 | Superadmin portal UI | 0 | Med |
| 3 | 12 | Org-admin scoped portal | 0 | Med–High |
| 4 | 13a | Per-org cost metering (tagging) | 1 | Med |
| 4 | 13b | Second-tenant rehearsal + rollback drill | 0 | Med |

**Could not verify / assumptions to confirm before Sprint 1:** the exact count of `_AdminBase` subclasses (Sprint 3 sizing); whether any billable call site was missed in the audit's cost table (Sprint 13a); the full `application_completeness`/`document_red_blockers` bodies (Sprint 8 sizing) — all noted in the audit's "Could not verify" lists. Confirm these during Sprint 0 planning.
