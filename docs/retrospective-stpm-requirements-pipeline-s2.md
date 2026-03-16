# Retrospective — STPM Requirements Pipeline Rebuild Sprint 2

**Date:** 2026-03-16
**Sprint:** Backend Integration (fixture converter + model + engine + API + data load)

## What Was Built

1. **Fixture converter** (`Settings/_tools/stpm_requirements/stpm_json_to_fixture.py`) — converts structured JSON to Django fixture format, handles deduplication (1,680 entries → 1,113 unique)
2. **Django migration 0031** — 4 new boolean fields on StpmRequirement: `req_male`, `req_female`, `single`, `no_disability`
3. **List-aware engine** — `check_stpm_subject_group()` and `check_spm_prerequisites()` handle both single dict (legacy) and list of dicts (new pipeline) with AND semantics
4. **Exclusion list support** — SPM prereqs can now exclude specific subjects from "any N subjects" groups
5. **Demographic checks** — engine enforces gender/disability requirements
6. **API updates** — STPM detail response includes new boolean fields
7. **Frontend** — SpecialConditions component, i18n keys, search page grades fix, dashboard report sync
8. **Data loaded** — 1,113 StpmRequirement records from new pipeline

## What Went Well

- **Backward compatibility via `isinstance(group, list)`** — clean pattern that lets old and new data coexist without migration
- **Subagent-Driven Development** — 5 tasks completed efficiently with spec + quality review
- **UM6724001 spot-check** — verified the 4 original bugs are all fixed (2 STPM groups, 2 SPM groups, exclusion list, MUET Band 4)
- **Golden master increase** (1811 → 2103) is correct — richer requirements data means more students qualify

## What Went Wrong

1. **Fixture converter null-safety not caught by tool tests**
   - *Symptom:* `loaddata` would fail or produce incorrect defaults for courses without CGPA/MUET data
   - *Root cause:* The fixture converter was designed in Sprint 1 without checking the Django model's non-nullable field constraints. Tests used `None` as expected values.
   - *Fix:* Subagent fixed during Task 14. One fixture test (`test_no_stpm_min_subjects_when_empty`) updated to match model defaults. Future: when building fixture converters, always check the target model's field defaults first.

## Design Decisions

- **List format for subject groups** — multi-tier requirements ("A in 2 AND A- in 1") stored as list of dicts rather than inventing a nested structure. Simple, extensible, backward-compatible.
- **AND semantics** — all groups in the list must be satisfied. Matches how MOHE requirements work (they're cumulative, not alternatives).
- **Model defaults over None** — `stpm_min_subjects=2`, `min_muet_band=1`, `min_cgpa=2.0` as safe defaults for courses missing those fields.

## Numbers

| Metric | Value |
|--------|-------|
| Tasks completed | 5 (Tasks 10-14) |
| Django tests | 590 pass, 0 fail |
| Pipeline tool tests | 199 pass, 0 fail |
| STPM golden master | 1811 → 2103 |
| SPM golden master | 5319 (unchanged) |
| Courses loaded | 1,113 |
| Files modified (backend) | 7 |
| Files created (tools) | 1 |
