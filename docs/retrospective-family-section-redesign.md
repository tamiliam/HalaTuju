# Retrospective — "About your family" section redesign (S1 backend + S2a)

**Branch:** `feature/family-section-redesign` (off `main`, 2026-06-08). NOT merged / NOT deployed.
**Status:** Partial sprint closed at a clean checkpoint — backend complete, frontend foundation laid; the
form rebuild (S2b–f) remains. 3 commits: `dbf19ba` (S1a), `2aa2bc4` (S1b), `55faf10` (S2a).
**Spec:** `docs/scholarship/family-section-redesign-plan.md`. Stitch mockup approved (`dd948b9b…`).

## What Was Built
- **The root-cause fix.** Family data was four overlapping fields across two tabs (`first_in_family` toggle,
  legacy `siblings_studying_count`, `siblings_in_school`/`tertiary` steppers on the *income* tab, free-text
  `parents_occupation`) that could contradict each other — driving the `first_in_family_with_siblings_studying`
  anomaly and the `sibling_level_unknown` clarify-email. Replaced (design) with ONE structured roster.
- **`apps/scholarship/family.py`** — a 40-option B40/lower-M40 profession taxonomy + pure derivations
  (`derive_first_in_family`, `parents_occupation_summary`, `earning_members`, `clean_other_members`). No Django
  imports, fully unit-tested.
- **Data model** — 7 additive fields (`father_/mother_` name + occupation + occupation_other,
  `other_family_members` JSON) + migration `0048_family_roster` (additive, no data loss).
- **Derive-on-save** — `services.save_application_details` makes the structured roster the INPUT;
  `first_in_family` (= no sibling in/through tertiary) and `parents_occupation` (= roster summary) are kept in
  sync as OUTPUTS. Every downstream reader (profile_engine, anomaly_engine, ledger, check2) keeps working with
  zero changes, because they read the derived legacy columns.
- **Serializers** accept + expose the roster (occupation validated against the codes); the admin serializer
  exposes it for the cockpit Family card.
- **`lib/familyRoster.ts`** — the frontend mirror (codes/groups/helpers) the S2 form will build on.

## What Went Well
- **Validating the taxonomy against the real database.** Pulled all 33 students who had filled
  `parents_occupation` and mapped each to the list. The data exposed four genuine gaps (insurance agent ×2,
  site engineer, generic "company worker", foreman ×2) that armchair design missed — added private / agent /
  professional / supervisor → ~95% coverage. Cheap, high-signal, and it's repeatable for any future taxonomy.
- **"Derive the legacy columns as outputs"** turned a scary multi-engine refactor into an additive,
  low-risk change: the consumers never had to be touched, and the now-impossible anomaly/clarify-query became
  inert-by-construction rather than needing risky deletion (kept as a safety net for legacy free text).

## What Went Wrong
- **The profession list churned through ~5 regenerate cycles of migration `0048`** as the owner added options
  mid-build (technician, store clerk, F&B, …). *Symptom:* repeated `rm migration && makemigrations`. *Root
  cause:* started writing the model/migration before the content (the option list) was settled — the list is a
  product decision, not an engineering one, and it wasn't locked first. *Fix:* for any enum/taxonomy field,
  lock the option list with the owner (ideally validated against real data) BEFORE generating the migration;
  added to `docs/lessons.md`.
- **A serializer reference to `PROFESSION_CODES` was written before its import**, which broke `makemigrations`
  with a `NameError`. *Symptom:* migration generation failed. *Root cause:* edited the consumer (serializer
  field) before wiring the import in the same file. *Fix:* when introducing a shared constant, add the import
  in the same edit as the first use (caught immediately here by running makemigrations).

## Design Decisions
See `docs/decisions.md` (3 logged this sprint): derive-legacy-columns-as-outputs; validate-taxonomy-against-prod;
compulsory-zero-able-stepper-via-null-default.

## Numbers
- 854 scholarship pytest (+9 family) · 1037 courses/reports (unchanged) · 276 jest (unchanged).
- 40 profession options; 7 new model fields; migration `0048` (additive, NOT applied to prod — prod at `0047`).
- ~95% coverage of real `parents_occupation` entries after the DB-validated additions.
- 3 commits; ~9 backend files + 1 frontend file + 1 plan + this retro.
