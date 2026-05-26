# B40 Apply-form — "Your Plans" step redesign (context-aware, progressive disclosure)

**Status:** DRAFT roadmap — awaiting user approval. Do not start Sprint 1 until approved.
**Date:** 2026-05-26

## Goal
Rebuild Step 4 ("Your Plans") of the B40 apply form into a context-aware, progressive-disclosure
flow where every control generates a decision OR profile signal. Programme pickers show **only what
the student is eligible for**, reusing HalaTuju's live eligibility engine.

## Locked design decisions (agreed with user)
- **Progressive disclosure** — step opens with one question; each control appears only when the
  answer above it makes it relevant. Nothing shown until its trigger.
- **Top split: "Do you know your pathway?" → Sure / Still deciding.** Sure is the expected path.
- **Eligible-only pathway picker** — show only pathways the student qualifies for (reuse the live
  engine + `course_pathway_map` `pathway_type`: matric, stpm, asasi, university, poly, kkom, pismp,
  iljtm, ilkbs — ILJTM/ILKBS already cleanly separated via institution category).
- **Sure → pathway → sub-flow → field:**
  - Form 6 (STPM): stream (Sains / Sains Sosial / Not sure) → school (STPM_SCHOOLS by stream) → field
  - Matriculation: track (Science/Eng/CompSci/Accounting, eligible via /calculate/pathways/) → college (MATRIC_COLLEGES by track) → field
  - Asasi / University / Poly / Kolej Komuniti / PISMP / ILJTM / ILKBS: programme (eligible only) → field
  - post-STPM student: degree programme (stream + eligibility) → field
- **Uncertain branch:** optional "leaning towards?" pathway chips + "Where are you right now?"
  reason chips (each routes follow-up; guidance/family → `mentoring_candidate`) + one free-text line.
- **Every control earns its place** by generating a decision-gate or profile signal.

## Reused infrastructure (already exists — no rebuild)
- Eligibility: `/eligibility/check/` (SPM), `/stpm/eligibility/check/`, `/calculate/pathways/` (matric/stpm tracks).
- `course_pathway_map` (pathway_type incl. iljtm/ilkbs split) computed at app startup.
- Data: `STPM_SCHOOLS` (584, has streams), `MATRIC_COLLEGES` (15, has tracks), `FieldTaxonomy` (47).
- Application model: `intends_tertiary_2026`, `field_of_study`, `pathways_considered`, `top_choices`,
  `upu_status`, `anything_else`, **`mentoring_candidate`**, `form_data`.
- Engine gate unchanged: `intends_tertiary_2026` + `upu_status=='ipts'` still drive shortlisting.

## Sprint roadmap (6 sprints)

### Lessons applied (from docs/lessons.md)
- **Migration clash:** checked `max()` on main = 0009 → new migration is **0010** (no clash).
- **Backward-compatible:** all 7 new fields optional (blank/default) so older clients/tests keep working.
- **Serializer consumers:** `ApplicationCreateSerializer` (write) + `ApplicationReadSerializer` (read) + `serializers_admin` — update all three; changing one affects every endpoint that uses it.
- **Engine untouched:** no change to `shortlisting.py` or the `courses` eligibility engine; reuse `upu_status` for the IPTS gate (derived in P2). `scholarship` app stays separate from `courses`.
- **Migrate-first at P5 deploy** (Cloud Run triggers don't migrate): additive migration applied to prod *before* merging `main`.
- **Full suite** at close (not just new tests), since this touches the intake path.

### P1 — Foundation: storage (no new endpoint — reuse existing eligibility endpoints)  ✅ DONE (2026-05-26)
- Shipped: migration `0010_plans_redesign_fields` (7 optional fields) + serializers (intake/read/admin) +
  `services._APP_FIELDS`/`build_intake_snapshot` + 2 tests. Scholarship suite 95 passed. On branch, not deployed.
  Confirmed: no new endpoint needed — frontend will reuse `/eligibility/check/` + `/stpm/eligibility/check/`.
- **Goal:** backend ready. New application fields + one endpoint returning this student's eligible
  pathways and eligible programmes grouped by `pathway_type`.
- **Scope:** scholarship/models.py + migration (pathway_certainty, chosen_pathway, stpm_stream,
  stpm_school, matric_track, matric_college, chosen_programme, uncertainty_reasons; reuse
  anything_else + mentoring_candidate); a `/scholarship/plan-options/` view composing the existing
  engines; serializer; tests.
- **Acceptance:** endpoint returns correct eligible-only pathways+programmes for SPM and STPM test
  profiles; migration applies; model round-trips new fields. **Main risk lives here** (engine reuse).

### P2 — Shell: progressive-disclosure container + Sure/Uncertain + pathway picker  (medium)
- **Goal:** replace the current Plans tab with the reveal shell; Sure reveals eligible-only pathway
  buttons (from P1); Uncertain reveals a stub (built in P5). State + per-step validation.
- **Scope:** apply/page.tsx (Plans rewrite), PathwaySelect component, lib state, i18n shell ×3, tests.
- **Acceptance:** opens with one question; Sure shows only eligible pathways; reveal + validation +
  mobile work; nothing else visible until triggered.

### P3 — Sure: programme-list pathways  (medium)
- **Goal:** Asasi / University / Poly / Kolej Komuniti / PISMP / ILJTM / ILKBS → eligible programme picker → field.
- **Scope:** ProgrammePicker (eligible programmes for chosen pathway_type), field reveal, store
  chosen_programme, i18n ×3, tests.
- **Acceptance:** each pathway reveals only eligible programmes; field saved; round-trips.

### P4 — Sure: institution pathways (STPM + Matriculation)  (medium-high)
- **Goal:** Form 6 → stream → school(by stream) → field; Matriculation → track(eligible) → college(by track) → field.
- **Scope:** Stream/Track selectors + School/College pickers (reuse SchoolSelect pattern), reveal
  logic, store stpm_stream/school + matric_track/college, i18n ×3, tests.
- **Acceptance:** streams/tracks limited to eligible; schools/colleges filtered correctly; saved.

### P5 — STPM-student Sure branch + Uncertain branch + ship  (medium)
- **Goal:** (a) post-STPM Sure → degree programme picker (stream+eligibility) → field. (b) Uncertain:
  optional leanings + reason chips (route mentoring_candidate) + free text. (c) feature complete →
  merge branch → migrate-first → deploy.
- **Scope:** degree ProgrammePicker (reuse /stpm/eligibility), Uncertain UI, reason→mentoring mapping,
  i18n ×3, tests; final regression; merge + deploy.
- **Acceptance:** STPM student sees eligible degrees; uncertain reasons persist + set mentoring flag
  where mapped; free text saved; full suite green; live on halatuju.xyz.

## Absorbed into every sprint (NOT a separate sprint — was the old "P6")
- **Cleanup as-you-replace:** each sprint that ships a new control removes the old one + its dead i18n
  keys in the same change (standing rule: delete replaced code immediately).
- **Admin surfacing:** the admin serializer already exposes the Plans fields; whichever sprint adds a
  new field also adds the few lines to render it on the admin scholarship detail page.
- **Regression + deploy:** tests run at every sprint-close; the single migrate-first + deploy happens
  at the P5 close (built on a feature branch so prod never carries a half-built step).
- **Sponsor view:** does not exist yet — out of scope (future work).

## Rationale for the split (5 sprints)
Foundation first (P1 carries the only real risk — engine reuse + schema). Then vertical slices by
branch (P2 shell → P3 programme pathways → P4 institution pathways → P5 STPM+uncertain+ship), each
shipping a working, testable slice with its own cleanup + admin surfacing. Could merge P3+P4, but that
sprint would exceed the ~20-file budget — kept separate for reliable delivery.
