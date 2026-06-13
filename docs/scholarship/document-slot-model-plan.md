# Plan — Document slot model (27 fixed slots; route controls display, not storage)

**Status: PLANNED (spec, 2026-06-13).** Investigation complete; production data assessed safe to migrate.
Build not started — needs owner go-ahead. Tracked as **TD-115**. Supersedes ad-hoc per-document SQL fixes:
this is a coordinated **code + migration in one pass**, because the data and the engine must change together.

---

## Problem
A student can upload only a finite, enumerable set of documents — **27 slots**. Today there is no per-slot
identity: the model has `(doc_type, household_member)` but it is applied **inconsistently**, which causes two
live bugs (both reproduced on real data):

1. **Person-switch shares one slot.** On the STR route the FE stores the earner's IC as `(parent_ic, '')` —
   one blank slot for all earners — and only swaps the *label* (`icTitle.${earner}`) when you switch
   Father/Mother/Guardian. So one uploaded IC appears under all three people. (ScholarshipDocuments.tsx.)
2. **Duplicate rows.** Check-2/Action-Centre uploads land untagged because `ResolutionItem` has **no
   `household_member`** and `resolve_doc_items_for_upload` matches by `doc_type` only — so a query upload
   creates a second `parent_ic` row instead of overwriting the right slot (the "two Mother's IC" on #16).

## Target model
**Slot = where a document lives (one per person). Route = which slots count & display for income proof.**
They are orthogonal. Every document is tagged by person at upload; the income route only governs which slots
are required/shown — it never changes *where* a document is stored.

### Confirmed model (owner recap, 2026-06-13 — verified against the engine)
1. **27 fixed slots** = `(doc_type × applicable person)`.
2. **Every upload lands in a slot** — from the application wizard *or* the Action Centre (Check-2). (Today the
   Action-Centre path doesn't carry the person → the duplicate bug; this is the fix.)
3. **A re-upload to an occupied slot overwrites it** (single-instance; enforced by a new DB uniqueness constraint).
4. **The route (STR/salary) sets which *income* docs are required vs optional** (`income_requirements()` keys off
   `income_route`). Non-income slots (applicant IC, results slip, offer letter, statement, photo) are required
   regardless of route.
5. **The submission/consent gate checks the route's *compulsory* docs are present** (optional never blocks). The gate
   tests **presence, not validity** — an STR must be uploaded to pass the gate; whether it's a true approval (Lulus)
   is a downstream verdict/Check-1 concern ("a true STR must pass").
6. **Any uploaded income doc the required slots don't consume falls under Optional** (cockpit `incomeDocLayout`
   catch-all — includes off-route docs, e.g. a father's IC/salary on a mother-STR household). Officer-view behaviour;
   the student wizard's optional is a fixed set (unifying = optional S2 nicety).

### The 27 slots = `(doc_type, household_member)`
| Slot | doc_type | member |
|---|---|---|
| applicant_ic | ic | '' |
| applicant_bc | birth_certificate | '' |
| results_slip | results_slip | '' |
| offer_letter | offer_letter | '' |
| {father,mother,guardian}_str | str | father/mother/guardian |
| {father,mother,guardian,brother,sister}_ic | parent_ic | that member |
| {father,mother,guardian,brother,sister}_salary_slip | salary_slip | that member |
| {father,mother,guardian,brother,sister}_epf | epf | that member |
| guardian_letter | guardianship_letter | guardian |
| water_bill | water_bill | '' |
| electricity_bill | electricity_bill | '' |
| statement_of_intent | statement_of_intent | '' |
| photo | photo | '' |

= 4 single + 3 STR + 5 IC + 5 salary + 5 EPF + 1 guardian-letter + 4 utility/other = **27.**
(Siblings get no STR — they're not the STR household head. `reference_letter` exists in the enum but is
unused and not a slot — drop it.)

## The key blocker: the engine stores income docs by a route-dependent convention
`income_engine._cluster_docs` reads income docs differently per route:
- **STR route →** looks for `household_member = ''` (blank); the earner is read from `application.income_earner`.
- **Salary route →** looks for `household_member = <member>`.

This is exactly what the slot model removes — but it means **the data cannot be re-tagged ahead of the code**.
Tagging an STR-route doc to its person, or flipping a route, *before* the engine reads by person-slot, breaks
that application's income verdict. **Hence: one coordinated change, not piecemeal SQL.**

## Production data assessment (2026-06-13) — migration is safe
- **Every doc maps to one of the 27 slots; no orphans, no unexpected `household_member` values** (only
  blank/father/mother present in real data).
- **Deterministic for ~all docs:** single-instance types → fixed slot; member-tagged income docs → person slot
  by tag; STR-route blank income docs → person slot by `income_earner` (all have one clean earner). OCR/extracted
  names confirm attribution where needed.
- **Route-mismatch is rare and, on review, narrows to ~1 open case.** **Rule (owner): a *true* STR route requires a
  *passing* STR doc in the system (Lulus + current + genuine) — merely *having* an STR file is not enough; a faulty STR
  legitimately falls back to the salary route.** After owner review, the set collapses to **one genuine route correction (#12)**:
  - **#12** — passing STR (status `Lulus`, mother) → **STR route/mother (the one real flip).**
  - **#8** — STR is an *application form, not an approval* (blank status) → **not a true STR; correctly stays salary.**
    No flip. Its real issue is missing salary proof (father's salary/EPF) → income outstanding. (A live instance of the
    STR-application-form-vs-approval / SALINAN gap — a non-approval STR must never be accepted as B40 proof on the STR
    route; the wrong-type/currency check should reject a blank/"Permohonan" status.)
  - **#9** — genuine STR exists offline but isn't uploaded → STR route is correct; obtain the upload.
  So the route field is **reliable**; the other "anomalies" are faulty/missing *proof*, which the system already models
  as income-outstanding, not wrong routing. Corollary in the route logic: *"STR route + no (passing) STR doc"* = **proof
  outstanding**, never an automatic re-route. The one correction (#12) lands via the audited route-switch service in the migration.
- **Duplicate residue already cleaned by hand:** #16 strays deleted; #12's blank duplicates (348, 331) deleted.

## Build scope (code + migration, one coordinated pass)
1. **Storage convention** — always tag `household_member` by person at upload, regardless of route. STR docs get
   the recipient's member (not blank). `''` only for the genuinely person-less slots (applicant_ic/bc,
   results_slip, offer_letter, utilities, statement, photo).
2. **`income_engine._cluster_docs`** — read by person-slot regardless of route (drop the blank/tagged split).
3. **Display logic (cockpit)** — uniform, no special-casing: **Required = the route's mandatory slots** (STR route →
   recipient's STR + IC + relationship; salary route → each working member's IC + salary slip, with red "missing"
   placeholders); **Optional = literally everything else the student uploaded** (the existing `incomeDocLayout`
   catch-all). So under STR route the recipient's optional salary/EPF AND any non-recipient docs (e.g. the father's
   IC/salary on a mother-STR household) all surface under the **Optional** label — *not* specially hidden, kept in their
   slots, consistent with how off-route uploads already render. (Requires the cockpit's required-slot lookup to match
   **by person**, not the current blank-member `find('parent_ic','')`, or a person-tagged recipient IC wrongly reads as
   "missing".) The **student wizard** stays route-scoped (fixed slots); unifying it with an "other uploads" area is an
   optional S2 nicety.
4. **Upload tagging fixes (the two bugs):** (a) FE STR-route earner slot must pass `household_member` =
   the selected earner (Bug 1); (b) `ResolutionItem` carries `household_member`, and the resolve-on-upload +
   the slot it targets are member-aware so a query upload overwrites the right slot (Bug 2).
5. **DB uniqueness** — `UniqueConstraint(application, doc_type, household_member)` after reconciliation, so
   duplicates can't recur.
6. **Migration (migrate-first via Supabase MCP):** backfill `household_member` deterministically (tag stays;
   STR-route blank income docs ← `income_earner`); reconcile the 3 route-mismatch apps (#8/#9/#12) via the
   route-switch service; the manual dedup is already done.
7. **Route-switch service** — fix the same latent bug it shares: switching salary↔STR today doesn't re-tag the
   existing docs, so under the old convention they'd be orphaned. Under the new person-tagged model this is moot,
   but verify the switch leaves every doc correctly slotted.

## Sequencing (proposed)
Likely **2–3 reviewable sprints:** (S1) model + engine + migration + the 3 route corrections; (S2) FE per-person
slots + the STR/salary display rules; (S3) Check-2/ResolutionItem slot-tagging. Each no-migration except S1.

## Open decisions for owner
- App **#8**: RESOLVED — STR is an application form (not approval) → stays salary; chase father's salary/EPF (proof outstanding).
- App **#9**: obtain Theresa's STR upload (she has it offline) — route is already correct (STR); no flip needed.
- App **#12**: the one route flip → STR/mother (passing Lulus STR), via the audited switch service in the migration.
- Whether to also purge orphaned storage blobs from the hand-deletes (harmless if left).
- Guardianship-letter slot member: store as `guardian` (recommended) vs `''`.
