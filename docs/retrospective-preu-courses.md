# Retrospective — Pre-U Courses Sprint (2026-03-13)

## What Was Built

- 6 pre-university courses (4 matric tracks + 2 STPM bidangs) as first-class `Course` + `CourseRequirement` database entries
- `merit_type` field on `CourseRequirement` — drives separate merit calculation formulas (standard, matric grade-point, STPM mata gred)
- Merit calculation branching in eligibility endpoint using `pathways.py` formulas
- `merit_display_student`/`merit_display_cutoff` API fields for STPM raw mata gred display
- Badge consistency overhaul: TVET renamed to ILJTM/ILKBS (distinct colours), STPM → Tingkatan 6, University → ua, all source labels in Malay, Pra-U level badge for matric/stpm
- Removed synthetic matric/STPM pathway entries from eligibility endpoint

## What Went Well

- **Design-first approach**: Brainstorming skill → design doc → approved plan → implementation. Clean execution with no backtracking.
- **Reuse of existing formulas**: `pathways.py` already had the matric/STPM formulas with 32 tests. Views.py calls them directly — no duplication.
- **Engine untouched**: `engine.py` (golden master) was not modified. Pre-U courses pass through the same eligibility loop as all other courses, with `complex_requirements` JSON encoding track-specific subject rules.
- **Badge audit caught real bugs**: User identified TVET as a bug (should be ILJTM/ILKBS), missing Pra-U level badge, and language inconsistency (English labels mixed with Malay).
- **Supabase migration clean**: 0 security errors after migration.

## What Went Wrong

1. **Synthetic entries caused confusion for months**
   - Symptom: Matric/STPM courses didn't appear in search, had inconsistent badges, used separate code path
   - Root cause: Original design generated them on-the-fly in the API response instead of storing as real database entries. This was a shortcut during initial STPM work.
   - Fix: Made them real Course rows with `merit_type` field. No more synthetic entries.

2. **Badge inconsistency accumulated across sprints**
   - Symptom: SPM and STPM CourseCards had different colours for the same source types, mixed English/Malay labels, missing badge configs
   - Root cause: Badge configs were added incrementally per sprint without a holistic review. No single source of truth for badge labels/colours.
   - Fix: Comprehensive badge audit and normalisation in one pass. All labels now in Malay, all source types have distinct colours.

## Design Decisions

- **`merit_type` on CourseRequirement** (not a separate model): Keeps the data model flat. Only 3 formulas exist, and each course has exactly one. Adding a field is simpler than a polymorphic pattern.
- **Second-pass eligibility via pathways.py**: Engine checks basic requirements (credit_bm, pass_history, min_credits), then views.py calls `check_matric_track()`/`check_stpm_bidang()` for track-specific validation. If pathways says "not eligible", the course is skipped even though engine said "eligible". This avoids modifying the golden master engine.
- **`complex_requirements` JSON for subject gates**: Matric track requirements (e.g., math ≥ B, addmath ≥ C) are encoded as OR-groups in the existing `complex_requirements` JSON format. The engine already evaluates this format.

## Numbers

- Tests: 359 collected, 320 passing (9 pre-existing auth failures, 30 skipped)
- New tests: 9 (6 eligibility + 3 search)
- Files changed: 14 (6 backend + 6 frontend + 2 migrations)
- Supabase: 6 courses + 6 requirements + 1 column added
- Deploys: 0 (pending)
