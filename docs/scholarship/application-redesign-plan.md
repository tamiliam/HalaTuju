# `/scholarship/application` (Step 4) Redesign — Plan

Post-shortlist "complete your profile" flow. Finalised with the user 2026-05-27 after a critical
signal-vs-burden review. Supersedes the narrow "Phase A/B" completeness polish.

## Guiding principle
Every field/document must (a) verify a fact the **decision** rests on, (b) be needed to make/administer the
**award**, or (c) materially help a **sponsor** decide to adopt. If none — cut it. The decision gate is
**income-based** and already computed at submit; it does **not** use funding amounts, photos, utility bills, or
referees. So most of this flow is for the *sponsor profile / verification*, and should be light or optional.

**Already on file — never re-ask:** household income, household size, receives STR/JKM, sibling count, disability
flag, school, full results, chosen course/pathway, "other scholarships". Pull from the profile; don't duplicate.

**Language:** every prompt is i18n'd (student reads in BM/EN/Tamil). All narrative answers are free-text — the
student writes in **BM, English, or Tamil**, whichever they're comfortable with; we never force a language and say so
visibly. **Requirement:** the AI sponsor-profile drafting (Gemini) must be language-aware — handle Tamil/BM input and
produce the profile in the target language (currently BM/EN only).

## Student-facing structure — 5 tabs (referee moved out; see below)
1. **Course quiz** — existing gate (unchanged).
2. **Your story** — two guided parts (A Family, B You); together they form the statement-of-intent basis.
3. **How you'd use the support** — reframed funding (tick + one rough total).
4. **Documents** — compulsory vs optional, clearly marked, with per-type explainers.
5. **Consent** — required (legal gate).

`complete` = quiz + story + funding + **compulsory docs (IC + results slip)** + consent.

### Locked decisions (2026-05-27)
- **Photo:** OPTIONAL (no verification value; minor privacy/safeguarding; barrier). Collect later at sponsor-profile
  stage if wanted.
- **Funding detail (revised 2026-05-27):** Assistance is **capped at RM3,000 — a *contribution*, not full
  funding** — so we do **NOT** ask for a total needed or "how you'd cover the balance" (that only manufactures a
  discouraging gap + uncertainty). Instead: (1) **tick the categories** the support would help with (living,
  transport, accommodation, books, device; tuition de-emphasised — ≈free at matriculation / low for B40 at IPTA);
  (2) a light **programme-length** field (factual: 1 yr vs 3 yrs of need); (3) an **open, optional box** — "Anything
  else you'd like us to know — e.g. how you're planning to fund your studies, or how you'd manage if this assistance
  doesn't come through." Frame the section as **"a contribution toward your costs"** and **state the ceiling plainly**: "Our assistance is
  **up to RM3,000** — the actual amount may be lower, depending on available funds and your needs." (Sets honest
  expectations without asking the student to compute a gap.) Final 3-language wording at the S3 Stitch step.
- **Referee:** moved to the **verify-&-accept (coordinator) stage** — NOT a student-facing gate. The existing
  admin flow records/confirms a referee at accept. Removed from student tabs + student completeness.
- **Documents:**
  - **Compulsory:** IC, results slip.
  - **Optional:** income proof = **any one** of {STR letter, salary slip, EPF statement}; water bill; electricity
    bill (both kept — proxy for family prosperity); statement of intent; offer letter; photo.
  - **Dropped:** reference letter (the named referee covers it).
  - Multi-file allowed for income proof (e.g. multiple salary slips if several earners) — optional.
  - Each type gets a one-line "what to upload / why" explainer.

### Your story — trimmed prompts (final in Stitch)
- **A) Family** (mostly optional, narrative): first-in-family-to-university (tick — strong equity signal);
  parents'/guardians' occupation (brief); a gentle optional box for household responsibilities + who supports the
  family + any serious illness/disability affecting finances; "are any siblings also studying?" (optional). Sibling
  count / income come from the profile — not re-asked.
- **B) You**: aspirations (keep); your plan to get there (keep); "your daily life & responsibilities" (optional —
  merges the old "typical day"/"hobbies", catches part-time work / caring duties); "what support would help / what
  worries you" (the mentoring signal).
- Note shown: *"Write in BM, English, or Tamil. If you have more to say, add a Statement of Intent in Documents."*

## Model changes (each additive, migrate-first)
- **ScholarshipApplication** — restructure deeper-info into the trimmed Family + You narrative fields (keep old
  `aspirations`/`plans`/`fears`/`justification` columns or remap; additive new fields preferred).
- **FundingNeed** — redesign (simplified): **category flags** + a free-text **`funding_note`** (how they'd use it /
  their plan / how they'd cope without) + `programme_months`. **No total amount** (assistance capped at RM3,000).
  Drop per-category amounts + `monthly_allowance`/`allowance_months` + any `estimated_total`. (Near-zero existing
  rows — pipeline dormant.)
- **ApplicantDocument** — add doc types `salary_slip`, `water_bill`, `electricity_bill`, `offer_letter`;
  required-set for completeness = {`ic`, `results_slip`}.
- **application_completeness** — rebuild to the 5-part model above; `complete` = all parts.

## Sprint roadmap
**Stitch gate (before any code):** prototype the 5-tab shell + Your story + How-you'd-use-support + Documents;
visual sign-off.

- **S1 — Tabbed shell (5 tabs) + port existing + live progress.** Frontend only; reuse `/apply` layout. No model change.
  **✅ DONE — shipped 2026-05-27 (v2.4.0, web `halatuju-web-00213-mvf`).** `ScholarshipNextSteps` rewritten to the
  5-tab shell; `NEXT_STEP_ORDER` + `defaultNextTab` in `scholarship.ts` (+9 jest); details form split across
  Story/Funding tabs (shared state, one PATCH); Documents/Consent ported as-is; Referee dropped from student flow;
  i18n 1177. Cosmetic carry-over: ported sections still show their old inner step headings (double-number) — cleared
  when S2/S3 rework the section content. **▶ NEXT: S2 — "Your story" (Family + You) guided section** (backend
  narrative fields + migration, migrate-first).
- **S2 — Your story (Family + You) guided section.** Backend narrative fields (+migration), serializers,
  completeness(story), tests; frontend section + i18n×3.
  **✅ DONE — shipped 2026-05-27 (v2.4.1; web `…00214-kr4`, api `…00167-lzl`; migration `0012` migrate-first).**
  5 additive narrative fields (`first_in_family`, `parents_occupation`, `siblings_studying`, `family_context`,
  `daily_life`); story-complete = aspirations+plans; guided two-card form; i18n 1190. **▶ NEXT: S3 — How you'd use
  the support** (Stitch-prototype first, then `FundingNeed` redesign + migration).
- **S3 — How you'd use the support (simplified funding).** Backend FundingNeed redesign (category flags +
  `funding_note` + `programme_months`, **no total**) (+migration), serializer, details-PATCH, completeness(funding),
  tests; frontend (tick categories + length + open box, "a contribution" framing) + lib helpers + i18n×3.
  **✅ DONE — shipped 2026-05-27 (v2.4.2; web `…00215-xsh`, api `…00169-tph`; migration `0013` migrate-first, 0 rows).**
  `categories`/`funding_note`/`programme_months`; funding-complete = ≥1 category; "up to RM3,000", tick-only, no total;
  legacy amount columns dead (TD-059). i18n 1209. **▶ NEXT: S4 — Documents** (Stitch-prototype first).
- **S4 — Documents (compulsory/optional + explainers + income "any one" + utility bills + multi-upload).** Backend
  doc types + required-set completeness + tests; frontend rework + i18n×3.
  **✅ DONE — shipped 2026-05-28 (v2.4.3; web `…00216-6pt`, api `…00171-cjf`; choices-only migration `0014`, no DDL,
  row recorded on prod via MCP).** Stitch-prototyped + signed off first. `ApplicantDocument` +4 doc types
  (`salary_slip`/`water_bill`/`electricity_bill`/`offer_letter`); `reference_letter` dropped from student UI (kept in
  model). `application_completeness` gains `documents_done` (IC + results slip); **`complete` left unchanged** (docs +
  consent fold in at S5). `ScholarshipDocuments` reworked: Required vs Optional sections, per-type explainers, combined
  income-proof card (STR/salary/EPF selector, multi-file); `scholarship.ts` doc-type groups + `documentsComplete()`
  (+jest). i18n parity 1227 (Tamil first-draft, pending user refine). Backend 112 pytest (scholarship); build clean.
  **▶ NEXT: S5 — Completeness finalise.**
- **S5 — Completeness finalise + progress ("X of 5") + "what happens next" + desktop polish + ship.** Plus: record
  referee at verify-&-accept (admin side) and make the AI sponsor-profile generator language-aware (Tamil), or note
  for Phase 2. **SPLIT into S5a (applicant-facing) + S5b (admin/AI).**
  - **S5a ✅ DONE — shipped 2026-05-28 (v2.4.4; web `…00217-7t7`, api `…00173-4nm`; NO migration).** Closed the
    completeness loop: `consent_done` + `complete` = quiz+story+funding+compulsory-docs+consent (supersedes S4's
    interim). Read serializer exposes `notify_email`. `ScholarshipNextSteps` wires the real Documents + Consent ticks
    (hardcoded false since S4) and, when complete, shows a green "You're all set!" banner + "What happens next" panel
    (3-step timeline + the comms email). Progress "X of 5" + per-step ticks + desktop rail were already delivered in S1.
    i18n 1235 (Tamil first-draft). Backend 1128 pytest; build clean. Stitch-prototyped + signed off first.
  - **S5b — queued (admin + AI):** record referee at the admin verify-&-accept stage; make the AI sponsor-profile
    generator **Tamil/BM-aware** (handle Tamil/BM input, produce profile in target language — currently BM/EN only).
    Then **TD-059** — drop the dead `FundingNeed` amount columns (one migration + serializer/lib cleanup).

Each sprint: tested, i18n-parity'd, migrate-first, deployed, live-verified.
